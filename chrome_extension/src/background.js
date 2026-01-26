/*
 * Service worker: coordinates popup requests, reads active tab URL,
 * and calls Azure/OpenAI with user-configured settings.
 * Pure front-end; no dependency on the Python CLI runtime.
 */

import { loadSettings, migrateOldTaskState } from "./storage.js";
import { summarizeUrl } from "./summarize.js";
import { saveSummaryAsMarkdown } from "./fileSaver.js";
import { taskStateManager } from "./taskStateManager.js";
import { i18n } from "./i18n.js";

// Service Worker startup: clean up old states
(async () => {
  console.log("[Background] Service Worker starting, running cleanup...");
  await migrateOldTaskState();
  await taskStateManager.cleanupClosedTabs();
  await taskStateManager.cleanupStaleStates();
  console.log("[Background] Cleanup completed");
})();

/**
 * 广播状态到 popup 和 sidepanel
 * 注意：Service Worker 中的 sendMessage 只能发送给其他页面（popup/sidepanel），
 * 不能发送给自己。如果没有活跃的接收者，会产生错误（这是正常的）。
 * @param {number} tabId - The tab ID this status belongs to
 * @param {string} status - Status text
 * @param {string} message - Status message
 * @param {boolean} isError - Whether this is an error status
 */
function broadcastStatus(tabId, status, message = "", isError = false) {
  console.log("[Background] broadcastStatus:", tabId, status);
  chrome.runtime.sendMessage({
    type: "SUMMARY_STATUS_UPDATE",
    payload: { tabId, status, message, isError },
  }).catch(() => {
    // 如果没有活跃的接收者（如 popup 已关闭），这里会报错，这是正常的
    console.log("[Background] broadcastStatus: no active receivers (normal if popup is closed)");
  });
}

// Listen for tab close to clean up state
chrome.tabs.onRemoved.addListener(async (tabId) => {
  console.log("[Background] Tab closed, clearing state:", tabId);
  await taskStateManager.clearState(tabId);
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type !== "RUN_SUMMARY") {
    return false;
  }

  console.log("[Background] Received RUN_SUMMARY request");

  (async () => {
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab?.url) {
        console.error("[Background] Cannot get active tab URL");
        sendResponse({ ok: false, error: i18n.cannotGetTabUrl() });
        return;
      }

      console.log("[Background] Processing URL:", tab.url);

      await taskStateManager.setState(tab.id, {
        status: "running",
        message: i18n.processingUrl(tab.url),
        isError: false,
        url: tab.url,
      });
      broadcastStatus(tab.id, i18n.statusRunning(), i18n.processingUrl(tab.url));

      const settings = await loadSettings();
      console.log("[Background] Calling summarizeUrl...");
      const options = {
        ...message?.options,
        preferredLanguages: settings.preferred_languages,
        useHttpDetection: settings.use_http_detection,
        max_output_tokens: settings.max_output_tokens,
        tabId: tab.id,  // Pass tabId for DOM parsing via scripting API
      };
      const result = await summarizeUrl(tab.url, settings, options);
      const text = result?.output_text || result?.summary || "";

      console.log("[Background] Summary completed successfully");
      await taskStateManager.setState(tab.id, {
        status: "completed",
        message: text || i18n.summaryComplete(),
        isError: false,
        url: tab.url,
      });
      broadcastStatus(tab.id, i18n.statusComplete(), text || i18n.summaryComplete());

      // 自动保存摘要到本地
      if (settings.auto_save_summary && text) {
        try {
          const title = result?.metadata?.title || "";
          const metadata = result?.metadata || {};
          await saveSummaryAsMarkdown(
            tab.url,
            text,
            title,
            settings.save_subdirectory || "any2summary",
            metadata
          );
          console.log("[Background] Summary saved to local file");
        } catch (saveError) {
          console.error("[Background] Failed to save summary:", saveError);
        }
      }

      sendResponse({ ok: true, result });
    } catch (error) {
      const messageText = error instanceof Error ? error.message : String(error);
      console.error("[Background] Error:", messageText);
      // Use tab.id if available, otherwise skip state update
      if (tab?.id) {
        await taskStateManager.setState(tab.id, {
          status: "failed",
          message: messageText,
          isError: true,
          url: tab?.url || "",
        });
        broadcastStatus(tab.id, i18n.statusFailed(), messageText, true);
      }
      sendResponse({ ok: false, error: messageText });
    }
  })();

  return true; // keep the message channel open for async response
});

chrome.commands.onCommand.addListener(async (command) => {
  if (command !== "run-summary") {
    return;
  }

  console.log("[Background] Keyboard shortcut triggered: run-summary");

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.url || !tab?.id) {
      console.error("[Background] Cannot get active tab URL or ID");
      return;
    }

    console.log("[Background] Processing URL via shortcut:", tab.url);

    await taskStateManager.setState(tab.id, {
      status: "running",
      message: i18n.shortcutTriggered(tab.url),
      isError: false,
      url: tab.url,
    });
    broadcastStatus(tab.id, i18n.statusRunning(), i18n.shortcutTriggered(tab.url));

    const settings = await loadSettings();
    console.log("[Background] Calling summarizeUrl...");
    const options = {
      preferredLanguages: settings.preferred_languages,
      useHttpDetection: settings.use_http_detection,
      max_output_tokens: settings.max_output_tokens,
      tabId: tab.id,  // Pass tabId for DOM parsing via scripting API
    };
    const result = await summarizeUrl(tab.url, settings, options);
    const text = result?.output_text || result?.summary || "";

    console.log("[Background] Summary completed successfully");
    await taskStateManager.setState(tab.id, {
      status: "completed",
      message: text || i18n.summaryComplete(),
      isError: false,
      url: tab.url,
    });
    broadcastStatus(tab.id, i18n.statusComplete(), text || i18n.summaryComplete());

    // 自动保存摘要到本地
    if (settings.auto_save_summary && text) {
      try {
        const title = result?.metadata?.title || "";
        const metadata = result?.metadata || {};
        await saveSummaryAsMarkdown(
          tab.url,
          text,
          title,
          settings.save_subdirectory || "any2summary",
          metadata
        );
        console.log("[Background] Summary saved to local file");
      } catch (saveError) {
        console.error("[Background] Failed to save summary:", saveError);
      }
    }
  } catch (error) {
    const messageText = error instanceof Error ? error.message : String(error);
    console.error("[Background] Error:", messageText);
    if (tab?.id) {
      await taskStateManager.setState(tab.id, {
        status: "failed",
        message: messageText,
        isError: true,
        url: tab?.url || "",
      });
      broadcastStatus(tab.id, i18n.statusFailed(), messageText, true);
    }
  }
});
