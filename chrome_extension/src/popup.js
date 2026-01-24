import { loadSettings } from "./storage.js";
import { taskStateManager } from "./taskStateManager.js";

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
  const statusEl = document.getElementById("status");
  const resultEl = document.getElementById("result");

  // 检查 DOM 元素是否存在
  if (!runButton || !statusEl || !resultEl) {
    console.error("[Popup] Critical DOM elements missing:", {
      runButton: !!runButton,
      statusEl: !!statusEl,
      resultEl: !!resultEl,
    });
    return;
  }
  console.log("[Popup] DOM elements loaded successfully");

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
      return;
    }

    console.log("[Popup] restoreState: found state:", state.status);
    switch (state.status) {
      case "running":
        setStatus("运行中...");
        setResult(state.message || "正在处理中，请稍候...");
        runButton.disabled = true;
        break;
      case "completed":
        setStatus("完成");
        setResult(state.message);
        runButton.disabled = false;
        break;
      case "failed":
        setStatus("失败");
        setResult(state.message, true);
        runButton.disabled = false;
        break;
    }
  }

  // 监听来自 background 的状态更新消息（只处理当前 tab）
  chrome.runtime.onMessage.addListener((message) => {
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
    runButton.disabled = message.payload.status === "运行中...";
  });

  // 确保已配置 API Key
  async function ensureConfigured() {
    const settings = await loadSettings();
    if (!settings.api_key) {
      throw new Error("请先在 Options 页填写 API Key");
    }
    return settings;
  }

  // 恢复状态
  await restoreState();

  // 绑定按钮点击事件
  runButton.addEventListener("click", async () => {
    console.log("[Popup] Run button clicked");
    runButton.disabled = true;
    setStatus("运行中...");
    setResult("");
    broadcastStatus("运行中...", "正在请求 Azure/OpenAI");

    try {
      await ensureConfigured();
      const response = await chrome.runtime.sendMessage({ type: "RUN_SUMMARY", options: {} });
      if (!response?.ok) {
        throw new Error(response?.error || "未知错误");
      }

      const data = response.result;
      const text = data?.output_text || data?.summary || JSON.stringify(data, null, 2);
      const finalText = text || "未返回内容";
      setResult(finalText);
      setStatus("完成");
      runButton.disabled = false;

      broadcastStatus("完成", finalText);

      chrome.notifications.create({
        type: "basic",
        iconUrl: "src/icon128.png",
        title: "any2summary",
        message: "摘要已完成",
        contextMessage: finalText.slice(0, 80),
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      console.error("[Popup] Error:", message);
      setStatus("失败");
      setResult(message, true);
      runButton.disabled = false;
      broadcastStatus("失败", message, true);
      chrome.notifications.create({
        type: "basic",
        iconUrl: "src/icon128.png",
        title: "any2summary",
        message: "摘要失败",
        contextMessage: message.slice(0, 80),
      });
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
