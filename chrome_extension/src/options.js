import { loadSettings, saveSettings } from "./storage.js";
import { checkLocalServerHealth } from "./summarize.js";
import { applyI18n, i18n } from "./i18n.js";

// 表单元素
const endpointEl = document.getElementById("endpoint");
const apiVersionEl = document.getElementById("apiVersion");
const deploymentEl = document.getElementById("deployment");
const apiKeyEl = document.getElementById("apiKey");
const useResponsesEl = document.getElementById("useResponses");
const cacheEnabledEl = document.getElementById("cacheEnabled");
const cacheTtlEl = document.getElementById("cacheTtl");
const cacheMaxEl = document.getElementById("cacheMax");
const localServerEnabledEl = document.getElementById("localServerEnabled");
const localServerUrlEl = document.getElementById("localServerUrl");
const serverStatusEl = document.getElementById("serverStatus");
// 摘要配置
const summaryLengthEl = document.getElementById("summaryLength");
// 语言偏好配置
const preferredLanguageEl = document.getElementById("preferredLanguage");
const fallbackLanguagesEl = document.getElementById("fallbackLanguages");
// 自动保存配置
const autoSaveSummaryEl = document.getElementById("autoSaveSummary");
const saveTimelineEl = document.getElementById("saveTimeline");
const inferDomainEl = document.getElementById("inferDomain");
const saveSubdirectoryEl = document.getElementById("saveSubdirectory");
// Toast 元素
const toastEl = document.getElementById("toast");

/**
 * 显示 Toast 提示
 */
function showToast(message, type = "default") {
  toastEl.textContent = message;
  toastEl.className = "toast show";
  if (type === "success") {
    toastEl.classList.add("success");
  } else if (type === "error") {
    toastEl.classList.add("error");
  }
  setTimeout(() => {
    toastEl.className = "toast";
  }, 2500);
}

/**
 * 显示服务器状态
 */
function setServerStatus(text, isSuccess) {
  serverStatusEl.textContent = text;
  serverStatusEl.style.display = "block";
  serverStatusEl.className = "server-status " + (isSuccess ? "success" : "error");
}

/**
 * 测试本地服务器连接
 */
async function testLocalServer() {
  const url = localServerUrlEl.value.trim() || "http://127.0.0.1:8765";
  setServerStatus(i18n.serverConnecting(), false);

  const health = await checkLocalServerHealth(url);
  if (health && health.status === "ok") {
    const services = health.services || {};
    const serviceList = Object.entries(services)
      .map(([k, v]) => `${k}: ${v ? "✓" : "✗"}`)
      .join(", ");
    setServerStatus(i18n.serverConnectSuccess(health.version, serviceList), true);
  } else {
    setServerStatus(i18n.serverConnectFailed(), false);
  }
}

/**
 * 恢复保存的设置
 */
async function restore() {
  const settings = await loadSettings();
  endpointEl.value = settings.azure_endpoint || "";
  apiVersionEl.value = settings.azure_api_version || "";
  deploymentEl.value = settings.deployment || "";
  apiKeyEl.value = settings.api_key || "";
  // Toggle 开关使用 checked 属性
  useResponsesEl.checked = settings.use_responses_api ?? true;
  cacheEnabledEl.checked = settings.cache_enabled ?? true;
  cacheTtlEl.value = settings.cache_ttl_minutes ?? 60;
  cacheMaxEl.value = settings.cache_max_entries ?? 50;
  localServerEnabledEl.checked = settings.local_server_enabled ?? false;
  localServerUrlEl.value = settings.local_server_url || "http://127.0.0.1:8765";
  // 摘要配置
  summaryLengthEl.value = settings.summary_length || "standard";
  // 语言偏好配置
  preferredLanguageEl.value = settings.preferred_language || "en";
  fallbackLanguagesEl.value = (settings.fallback_languages || ["zh-Hans", "zh-Hant", "ja", "ko"]).join(",");
  // 自动保存配置
  autoSaveSummaryEl.checked = settings.auto_save_summary ?? true;
  saveTimelineEl.checked = settings.save_timeline ?? true;
  inferDomainEl.checked = settings.infer_domain ?? true;
  saveSubdirectoryEl.value = settings.save_subdirectory || "any2summary";
}

/**
 * 保存设置
 */
async function persist() {
  // 解析备选语言列表
  const fallbackLangsRaw = fallbackLanguagesEl.value.trim();
  const fallbackLanguages = fallbackLangsRaw
    ? fallbackLangsRaw.split(",").map(s => s.trim()).filter(Boolean)
    : ["zh-Hans", "zh-Hant", "ja", "ko"];

  // 构建首选语言列表（首选 + 备选）
  const preferredLanguage = preferredLanguageEl.value || "en";
  const preferredLanguages = [preferredLanguage, ...fallbackLanguages.filter(l => l !== preferredLanguage)];

  const settings = {
    azure_endpoint: endpointEl.value.trim(),
    azure_api_version: apiVersionEl.value.trim(),
    deployment: deploymentEl.value.trim(),
    api_key: apiKeyEl.value.trim(),
    use_responses_api: useResponsesEl.checked,
    cache_enabled: cacheEnabledEl.checked,
    cache_ttl_minutes: Number(cacheTtlEl.value) || 60,
    cache_max_entries: Number(cacheMaxEl.value) || 50,
    local_server_enabled: localServerEnabledEl.checked,
    local_server_url: localServerUrlEl.value.trim() || "http://127.0.0.1:8765",
    // 摘要配置
    summary_length: summaryLengthEl.value || "standard",
    // 语言偏好配置
    preferred_language: preferredLanguage,
    fallback_languages: fallbackLanguages,
    preferred_languages: preferredLanguages,  // 合并后的列表，供 summarize 使用
    // 自动保存配置
    auto_save_summary: autoSaveSummaryEl.checked,
    save_timeline: saveTimelineEl.checked,
    infer_domain: inferDomainEl.checked,
    save_subdirectory: saveSubdirectoryEl.value.trim() || "any2summary",
  };
  await saveSettings(settings);
  showToast(i18n.settingsSaved(), "success");
}

// 绑定事件
document.getElementById("save").addEventListener("click", persist);
document.getElementById("testServer").addEventListener("click", testLocalServer);

// 初始化
applyI18n();
restore();
