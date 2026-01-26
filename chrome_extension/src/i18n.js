/**
 * Internationalization utilities for any2summary Chrome extension.
 * Uses Chrome's i18n API to support multiple languages.
 */

/**
 * Get localized message by key
 * @param {string} key - Message key from messages.json
 * @param {string|string[]} [substitutions] - Optional substitution values
 * @returns {string} Localized message or key if not found
 */
export function getMessage(key, substitutions) {
  const message = chrome.i18n.getMessage(key, substitutions);
  return message || key;
}

/**
 * Apply i18n translations to all elements with data-i18n attribute
 * Supports:
 * - data-i18n="key" - Sets textContent
 * - data-i18n-placeholder="key" - Sets placeholder attribute
 * - data-i18n-title="key" - Sets title attribute
 */
export function applyI18n() {
  // Translate textContent
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.getAttribute("data-i18n");
    if (key) {
      el.textContent = getMessage(key);
    }
  });

  // Translate placeholder
  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    const key = el.getAttribute("data-i18n-placeholder");
    if (key) {
      el.placeholder = getMessage(key);
    }
  });

  // Translate title
  document.querySelectorAll("[data-i18n-title]").forEach((el) => {
    const key = el.getAttribute("data-i18n-title");
    if (key) {
      el.title = getMessage(key);
    }
  });
}

// Common message keys for easy access
export const i18n = {
  // Status messages
  statusRunning: () => getMessage("statusRunning"),
  statusComplete: () => getMessage("statusComplete"),
  statusFailed: () => getMessage("statusFailed"),
  statusCancelled: () => getMessage("statusCancelled"),

  // Background messages
  processingUrl: (url) => getMessage("processingUrl", url),
  shortcutTriggered: (url) => getMessage("shortcutTriggered", url),
  summaryComplete: () => getMessage("summaryComplete"),
  cannotGetTabUrl: () => getMessage("cannotGetTabUrl"),

  // Options messages
  settingsSaved: () => getMessage("settingsSaved"),
  errorSavingSettings: () => getMessage("errorSavingSettings"),
  serverOnline: () => getMessage("serverOnline"),
  serverOffline: () => getMessage("serverOffline"),

  // Error messages
  pleaseConfigureApiKey: () => getMessage("pleaseConfigureApiKey"),
  unknownError: () => getMessage("unknownError"),

  // Server connection messages
  serverConnecting: () => getMessage("serverConnecting"),
  serverConnectSuccess: (version, services) =>
    getMessage("serverConnectSuccess", [version, services]),
  serverConnectFailed: () => getMessage("serverConnectFailed"),
};
