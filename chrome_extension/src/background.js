/*
 * Service worker: coordinates popup requests, reads active tab URL,
 * and calls Azure/OpenAI with user-configured settings.
 * Pure front-end; no dependency on the Python CLI runtime.
 */

import { loadSettings, migrateOldTaskState } from "./storage.js";
import { summarizeUrl, inferDomainFromSummary } from "./summarize.js";
import { saveSummaryAsMarkdown, saveTimelineAsMarkdown } from "./fileSaver.js";
import { taskStateManager } from "./taskStateManager.js";
import { getSummaryLengthConfig } from "./config.js";
import { i18n } from "./i18n.js";

// AbortController management for cancellable tasks
const abortControllers = new Map(); // Map<tabId, AbortController>

/**
 * Create a new AbortController for a tab.
 * @param {number} tabId
 * @returns {AbortController}
 */
function createAbortController(tabId) {
  // Clean up existing controller if any
  const existing = abortControllers.get(tabId);
  if (existing) {
    existing.abort();
  }
  const controller = new AbortController();
  abortControllers.set(tabId, controller);
  return controller;
}

/**
 * Get AbortSignal for a tab.
 * @param {number} tabId
 * @returns {AbortSignal|undefined}
 */
function getAbortSignal(tabId) {
  return abortControllers.get(tabId)?.signal;
}

/**
 * Clean up AbortController for a tab.
 * @param {number} tabId
 */
function cleanupAbortController(tabId) {
  abortControllers.delete(tabId);
}

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

/**
 * 广播进度更新到 popup
 * @param {number} tabId - The tab ID this progress belongs to
 * @param {number} ratio - Progress ratio (0.0 - 1.0)
 * @param {string} label - Progress label text
 */
function broadcastProgress(tabId, ratio, label) {
  chrome.runtime.sendMessage({
    type: "SUMMARY_PROGRESS",
    payload: { tabId, ratio, label },
  }).catch(() => {
    // Ignore if no receivers
  });
}

// Listen for tab close to clean up state
chrome.tabs.onRemoved.addListener(async (tabId) => {
  console.log("[Background] Tab closed, clearing state:", tabId);
  await taskStateManager.clearState(tabId);
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  // Handle CANCEL_TASK message
  if (message?.type === "CANCEL_TASK") {
    const tabId = message.tabId;
    console.log("[Background] Received CANCEL_TASK for tab:", tabId);

    const controller = abortControllers.get(tabId);
    if (controller) {
      controller.abort();
      cleanupAbortController(tabId);
    }

    // Update state to cancelled
    (async () => {
      await taskStateManager.setState(tabId, {
        status: "cancelled",
        message: i18n.statusCancelled(),
        isError: false,
        url: "",
      });
      broadcastStatus(tabId, i18n.statusCancelled(), i18n.statusCancelled());
    })();

    sendResponse({ ok: true });
    return true;
  }

  if (message?.type !== "RUN_SUMMARY") {
    return false;
  }

  console.log("[Background] Received RUN_SUMMARY request");

  (async () => {
    let tab;
    try {
      [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab?.url) {
        console.error("[Background] Cannot get active tab URL");
        sendResponse({ ok: false, error: i18n.cannotGetTabUrl() });
        return;
      }

      console.log("[Background] Processing URL:", tab.url);

      // Create AbortController for this task
      const controller = createAbortController(tab.id);

      await taskStateManager.setState(tab.id, {
        status: "running",
        message: i18n.processingUrl(tab.url),
        isError: false,
        url: tab.url,
      });
      broadcastStatus(tab.id, i18n.statusRunning(), i18n.processingUrl(tab.url));
      broadcastProgress(tab.id, 0.1, "检测内容类型...");

      const settings = await loadSettings();
      console.log("[Background] Calling summarizeUrl...");
      broadcastProgress(tab.id, 0.3, "获取内容...");

      // 根据 summary_length 设置获取 max_tokens
      const lengthConfig = getSummaryLengthConfig(settings.summary_length);
      const maxOutputTokens = lengthConfig.max_tokens || settings.max_output_tokens || 8192;

      const options = {
        ...message?.options,
        preferredLanguages: settings.preferred_languages,
        useHttpDetection: settings.use_http_detection,
        max_output_tokens: maxOutputTokens,
        summary_length: settings.summary_length,  // 传递 summary_length 用于 prompt 修饰
        tabId: tab.id,  // Pass tabId for DOM parsing via scripting API
        signal: controller.signal,  // Pass abort signal
      };
      broadcastProgress(tab.id, 0.6, "生成摘要...");
      const result = await summarizeUrl(tab.url, settings, options);
      const text = result?.output_text || result?.summary || "";

      console.log("[Background] Summary completed successfully");
      broadcastProgress(tab.id, 0.9, "处理完成...");

      // Clean up AbortController
      cleanupAbortController(tab.id);

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
          broadcastProgress(tab.id, 0.95, "保存文件...");
          // 与 CLI 一致：清理标题中的特殊字符，并添加 fallback
          const titleRaw = String(result?.metadata?.title || "").replace(/[:\/\\`]/g, "");
          const title = titleRaw.trim() || "未知标题";
          const metadata = { ...result?.metadata } || {};

          // 添加 generatedAt 作为日期备选（与 CLI 一致）
          const now = new Date();
          metadata.generatedAt = now.toISOString().slice(0, 10);  // YYYY-MM-DD 格式

          // 如果启用了 domain 推断，且 metadata 中没有 category，尝试从摘要内容推断
          const shouldInferDomain = settings.infer_domain !== false;  // 默认启用
          if (shouldInferDomain && !metadata.category && text) {
            try {
              const inferredDomain = await inferDomainFromSummary(text, settings);
              if (inferredDomain) {
                metadata.category = inferredDomain;
                console.log("[Background] Inferred domain:", inferredDomain);
              }
            } catch (inferError) {
              console.warn("[Background] Failed to infer domain:", inferError.message);
            }
          }

          // 保存摘要文件
          await saveSummaryAsMarkdown(
            tab.url,
            text,
            title,
            settings.save_subdirectory || "any2summary",
            metadata
          );
          console.log("[Background] Summary saved to local file");

          // 如果启用了 timeline 保存，且有 segments 数据，同时保存 timeline 文件
          const shouldSaveTimeline = settings.save_timeline !== false;  // 默认启用
          const segments = result?.segments;
          if (shouldSaveTimeline && segments && segments.length > 0) {
            await saveTimelineAsMarkdown(
              tab.url,
              segments,
              title,
              settings.save_subdirectory || "any2summary",
              metadata
            );
            console.log("[Background] Timeline saved to local file");
          }
        } catch (saveError) {
          console.error("[Background] Failed to save summary:", saveError);
        }
      }

      broadcastProgress(tab.id, 1.0, "完成");
      sendResponse({ ok: true, result });
    } catch (error) {
      // Clean up AbortController
      if (tab?.id) {
        cleanupAbortController(tab.id);
      }

      // Check if this is an abort error
      if (error.name === "AbortError") {
        console.log("[Background] Task was cancelled");
        sendResponse({ ok: false, error: i18n.statusCancelled(), cancelled: true });
        return;
      }

      const messageText = error instanceof Error ? error.message : String(error);
      console.error("[Background] Error:", messageText);

      // Use try-catch to ensure sendResponse is always called
      try {
        if (tab?.id) {
          await taskStateManager.setState(tab.id, {
            status: "failed",
            message: messageText,
            isError: true,
            url: tab?.url || "",
          });
          broadcastStatus(tab.id, i18n.statusFailed(), messageText, true);
        }
      } catch (stateError) {
        console.error("[Background] Failed to update state:", stateError);
      }

      // Always call sendResponse to close the message channel properly
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

  let tab;
  try {
    [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.url || !tab?.id) {
      console.error("[Background] Cannot get active tab URL or ID");
      return;
    }

    console.log("[Background] Processing URL via shortcut:", tab.url);

    // Create AbortController for this task
    const controller = createAbortController(tab.id);

    await taskStateManager.setState(tab.id, {
      status: "running",
      message: i18n.shortcutTriggered(tab.url),
      isError: false,
      url: tab.url,
    });
    broadcastStatus(tab.id, i18n.statusRunning(), i18n.shortcutTriggered(tab.url));

    const settings = await loadSettings();
    console.log("[Background] Calling summarizeUrl via shortcut...");

    // 根据 summary_length 设置获取 max_tokens
    const lengthConfig = getSummaryLengthConfig(settings.summary_length);
    const maxOutputTokens = lengthConfig.max_tokens || settings.max_output_tokens || 8192;

    const options = {
      preferredLanguages: settings.preferred_languages,
      useHttpDetection: settings.use_http_detection,
      max_output_tokens: maxOutputTokens,
      summary_length: settings.summary_length,
      tabId: tab.id,  // Pass tabId for DOM parsing via scripting API
      signal: controller.signal,  // Pass abort signal
    };
    const result = await summarizeUrl(tab.url, settings, options);
    const text = result?.output_text || result?.summary || "";

    console.log("[Background] Summary completed successfully");

    // Clean up AbortController
    cleanupAbortController(tab.id);

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
        // 与 CLI 一致：清理标题中的特殊字符，并添加 fallback
        const titleRaw = String(result?.metadata?.title || "").replace(/[:\/\\`]/g, "");
        const title = titleRaw.trim() || "未知标题";
        const metadata = { ...result?.metadata } || {};

        // 添加 generatedAt 作为日期备选（与 CLI 一致）
        const now = new Date();
        metadata.generatedAt = now.toISOString().slice(0, 10);  // YYYY-MM-DD 格式

        // 如果启用了 domain 推断，且 metadata 中没有 category，尝试从摘要内容推断
        const shouldInferDomain = settings.infer_domain !== false;
        if (shouldInferDomain && !metadata.category && text) {
          try {
            const inferredDomain = await inferDomainFromSummary(text, settings);
            if (inferredDomain) {
              metadata.category = inferredDomain;
              console.log("[Background] Inferred domain via shortcut:", inferredDomain);
            }
          } catch (inferError) {
            console.warn("[Background] Failed to infer domain:", inferError.message);
          }
        }

        // 保存摘要文件
        await saveSummaryAsMarkdown(
          tab.url,
          text,
          title,
          settings.save_subdirectory || "any2summary",
          metadata
        );
        console.log("[Background] Summary saved to local file");

        // 如果启用了 timeline 保存，且有 segments 数据，同时保存 timeline 文件
        const shouldSaveTimeline = settings.save_timeline !== false;
        const segments = result?.segments;
        if (shouldSaveTimeline && segments && segments.length > 0) {
          await saveTimelineAsMarkdown(
            tab.url,
            segments,
            title,
            settings.save_subdirectory || "any2summary",
            metadata
          );
          console.log("[Background] Timeline saved to local file");
        }
      } catch (saveError) {
        console.error("[Background] Failed to save summary:", saveError);
      }
    }
  } catch (error) {
    // Clean up AbortController
    if (tab?.id) {
      cleanupAbortController(tab.id);
    }

    // Check if this is an abort error
    if (error.name === "AbortError") {
      console.log("[Background] Task was cancelled via shortcut");
      return;
    }

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
