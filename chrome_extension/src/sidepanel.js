import { taskStateManager } from "./taskStateManager.js";

// Track current tab ID for filtering messages
let currentTabId = null;

/**
 * 初始化 SidePanel 页面
 * 使用 DOMContentLoaded 确保 DOM 完全加载后再执行
 */
async function initializeSidePanel() {
  console.log("[SidePanel] Initializing sidepanel...");

  // 获取 DOM 元素
  const statusEl = document.getElementById("status");
  const resultEl = document.getElementById("result");

  // 检查 DOM 元素是否存在
  if (!statusEl || !resultEl) {
    console.error("[SidePanel] Critical DOM elements missing:", {
      statusEl: !!statusEl,
      resultEl: !!resultEl,
    });
    return;
  }
  console.log("[SidePanel] DOM elements loaded successfully");

  // 辅助函数：渲染状态
  function render(payload) {
    console.log("[SidePanel] render:", payload.status);
    statusEl.textContent = payload.status;
    resultEl.textContent = payload.message || "";
    resultEl.className = payload.isError ? "result error" : "result";
  }

  // 恢复之前的状态（只恢复当前 tab 的状态）
  async function restoreState() {
    if (!currentTabId) {
      console.log("[SidePanel] restoreState: no current tab ID");
      render({ status: "等待任务...", message: "" });
      return;
    }

    console.log("[SidePanel] restoreState: loading task state for tab:", currentTabId);
    const state = await taskStateManager.getState(currentTabId);

    if (state) {
      console.log("[SidePanel] restoreState: found state:", state.status);
      render({
        status: state.status === "running" ? "运行中..." : state.status === "completed" ? "完成" : "失败",
        message: state.message,
        isError: state.isError,
      });
    } else {
      console.log("[SidePanel] restoreState: no saved state found for this tab");
      render({ status: "等待任务...", message: "" });
    }
  }

  // Get current tab ID
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  currentTabId = tab?.id;
  console.log("[SidePanel] Current tab ID:", currentTabId);

  // 监听 tab 切换，更新显示对应 tab 的状态
  chrome.tabs.onActivated.addListener(async (activeInfo) => {
    console.log("[SidePanel] Tab activated:", activeInfo.tabId);
    currentTabId = activeInfo.tabId;
    await restoreState();
  });

  // 监听来自 popup 或 background 的状态更新消息（只处理当前 tab）
  chrome.runtime.onMessage.addListener((message) => {
    if (message?.type !== "SUMMARY_STATUS_UPDATE") {
      return;
    }
    // Only handle messages for current tab
    if (message.payload.tabId !== currentTabId) {
      console.log("[SidePanel] Ignoring status update for different tab:", message.payload.tabId);
      return;
    }
    console.log("[SidePanel] Received status update:", message.payload.status);
    render(message.payload);
  });

  // 恢复状态
  await restoreState();

  console.log("[SidePanel] Initialization complete");
}

// 确保 DOM 完全加载后再执行初始化
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initializeSidePanel);
} else {
  // DOM 已经加载完成，直接执行
  initializeSidePanel();
}
