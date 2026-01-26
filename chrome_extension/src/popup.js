import { loadSettings } from "./storage.js";
import { taskStateManager } from "./taskStateManager.js";
import { applyI18n, i18n } from "./i18n.js";

// Track current tab ID for filtering messages
let currentTabId = null;

/**
 * 初始化 Popup 页面
 * 使用 DOMContentLoaded 确保 DOM 完全加载后再执行
 */
async function initializePopup() {
  console.log("[Popup] Initializing popup...");

  // Get current tab ID first
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  currentTabId = tab?.id;
  if (!currentTabId) {
    console.error("[Popup] Cannot get current tab ID");
    return;
  }
  console.log("[Popup] Current tab ID:", currentTabId);

  // 获取 DOM 元素
  const runButton = document.getElementById("run");
  const cancelButton = document.getElementById("cancel");
  const statusEl = document.getElementById("status");
  const resultEl = document.getElementById("result");
  const progressContainer = document.getElementById("progressContainer");
  const progressBar = document.getElementById("progressBar");
  const progressLabel = document.getElementById("progressLabel");

  // 检查 DOM 元素是否存在
  if (!runButton || !cancelButton || !statusEl || !resultEl) {
    console.error("[Popup] Critical DOM elements missing:", {
      runButton: !!runButton,
      cancelButton: !!cancelButton,
      statusEl: !!statusEl,
      resultEl: !!resultEl,
    });
    return;
  }
  console.log("[Popup] DOM elements loaded successfully");

  // Apply i18n translations
  applyI18n();

  // 辅助函数：设置运行状态（切换按钮显示）
  function setRunningState(isRunning) {
    if (isRunning) {
      runButton.style.display = "none";
      cancelButton.style.display = "inline-flex";
      if (progressContainer) {
        progressContainer.classList.add("show");
      }
    } else {
      runButton.style.display = "inline-flex";
      cancelButton.style.display = "none";
      runButton.disabled = false;
      if (progressContainer) {
        progressContainer.classList.remove("show");
      }
    }
  }

  // 辅助函数：更新进度条
  function updateProgress(ratio, label) {
    if (progressBar) {
      progressBar.style.width = `${Math.round(ratio * 100)}%`;
    }
    if (progressLabel) {
      progressLabel.textContent = label || "";
    }
  }

  // 辅助函数：设置状态
  function setStatus(text) {
    console.log("[Popup] setStatus:", text);
    statusEl.textContent = text;
  }

  // 辅助函数：设置结果
  function setResult(text, isError = false) {
    console.log("[Popup] setResult:", text?.slice?.(0, 50) || text, "isError:", isError);
    resultEl.textContent = text;
    resultEl.className = isError ? "result error" : "result";
  }

  // 辅助函数：广播状态到 sidepanel (包含 tabId)
  function broadcastStatus(status, message = "", isError = false) {
    console.log("[Popup] broadcastStatus:", currentTabId, status);
    chrome.runtime.sendMessage({
      type: "SUMMARY_STATUS_UPDATE",
      payload: { tabId: currentTabId, status, message, isError },
    });
  }

  // 恢复之前的状态（只恢复当前 tab 的状态）
  async function restoreState() {
    console.log("[Popup] restoreState: loading task state for tab:", currentTabId);
    const state = await taskStateManager.getState(currentTabId);

    if (!state) {
      console.log("[Popup] restoreState: no saved state found for this tab");
      setRunningState(false);
      return;
    }

    console.log("[Popup] restoreState: found state:", state.status);
    switch (state.status) {
      case "running":
        setStatus(i18n.statusRunning());
        setResult(state.message || i18n.statusRunning());
        setRunningState(true);
        break;
      case "completed":
        setStatus(i18n.statusComplete());
        setResult(state.message);
        setRunningState(false);
        break;
      case "failed":
        setStatus(i18n.statusFailed());
        setResult(state.message, true);
        setRunningState(false);
        break;
      case "cancelled":
        setStatus(i18n.statusCancelled());
        setResult(state.message || i18n.statusCancelled());
        setRunningState(false);
        break;
    }
  }

  // 监听来自 background 的状态更新消息（只处理当前 tab）
  chrome.runtime.onMessage.addListener((message) => {
    // Handle progress updates
    if (message?.type === "SUMMARY_PROGRESS") {
      if (message.payload.tabId !== currentTabId) return;
      updateProgress(message.payload.ratio, message.payload.label);
      return;
    }

    if (message?.type !== "SUMMARY_STATUS_UPDATE") {
      return;
    }
    // Only handle messages for current tab
    if (message.payload.tabId !== currentTabId) {
      console.log("[Popup] Ignoring status update for different tab:", message.payload.tabId);
      return;
    }
    console.log("[Popup] Received status update:", message.payload.status);
    setStatus(message.payload.status);
    setResult(message.payload.message || "", message.payload.isError);

    // Update button state based on status
    const isRunning = message.payload.status === i18n.statusRunning();
    setRunningState(isRunning);
  });

  // 确保已配置 API Key
  async function ensureConfigured() {
    const settings = await loadSettings();
    if (!settings.api_key) {
      throw new Error(i18n.pleaseConfigureApiKey());
    }
    return settings;
  }

  // 恢复状态
  await restoreState();

  // 绑定运行按钮点击事件
  runButton.addEventListener("click", async () => {
    console.log("[Popup] Run button clicked");
    setRunningState(true);
    setStatus(i18n.statusRunning());
    setResult("");
    broadcastStatus(i18n.statusRunning(), i18n.statusRunning());

    try {
      await ensureConfigured();
      const response = await chrome.runtime.sendMessage({ type: "RUN_SUMMARY", options: {} });

      // Check if task was cancelled
      if (response?.cancelled) {
        console.log("[Popup] Task was cancelled");
        setStatus(i18n.statusCancelled());
        setResult(i18n.statusCancelled());
        setRunningState(false);
        return;
      }

      if (!response?.ok) {
        throw new Error(response?.error || i18n.unknownError());
      }

      const data = response.result;
      const text = data?.output_text || data?.summary || JSON.stringify(data, null, 2);
      const finalText = text || i18n.summaryComplete();
      setResult(finalText);
      setStatus(i18n.statusComplete());
      setRunningState(false);

      broadcastStatus(i18n.statusComplete(), finalText);

      chrome.notifications.create({
        type: "basic",
        iconUrl: "icon128.png",
        title: "any2summary",
        message: i18n.summaryComplete(),
        contextMessage: finalText.slice(0, 80),
      });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      console.error("[Popup] Error:", errorMessage);
      setStatus(i18n.statusFailed());
      setResult(errorMessage, true);
      setRunningState(false);
      broadcastStatus(i18n.statusFailed(), errorMessage, true);
      chrome.notifications.create({
        type: "basic",
        iconUrl: "icon128.png",
        title: "any2summary",
        message: i18n.statusFailed(),
        contextMessage: errorMessage.slice(0, 80),
      });
    }
  });

  // 绑定取消按钮点击事件
  cancelButton.addEventListener("click", async () => {
    console.log("[Popup] Cancel button clicked");
    try {
      await chrome.runtime.sendMessage({
        type: "CANCEL_TASK",
        tabId: currentTabId,
      });
      setStatus(i18n.statusCancelled());
      setResult(i18n.statusCancelled());
      setRunningState(false);
      broadcastStatus(i18n.statusCancelled(), i18n.statusCancelled());
    } catch (error) {
      console.error("[Popup] Cancel error:", error);
    }
  });

  console.log("[Popup] Initialization complete");
}

// 确保 DOM 完全加载后再执行初始化
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initializePopup);
} else {
  // DOM 已经加载完成，直接执行
  initializePopup();
}
