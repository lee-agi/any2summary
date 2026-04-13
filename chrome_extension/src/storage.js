const SETTINGS_KEY = "any2summary_settings";

export async function loadSettings() {
  console.log("[Storage] loadSettings: reading from chrome.storage.local");
  const { [SETTINGS_KEY]: saved } = await chrome.storage.local.get(SETTINGS_KEY);
  if (saved) {
    console.log("[Storage] loadSettings: found saved settings");
    return saved;
  }
  console.log("[Storage] loadSettings: no saved settings, loading defaults");
  const response = await fetch(chrome.runtime.getURL("config/default_settings.json"));
  return response.json();
}

export async function saveSettings(settings) {
  console.log("[Storage] saveSettings: saving to chrome.storage.local");
  await chrome.storage.local.set({ [SETTINGS_KEY]: settings });
  console.log("[Storage] saveSettings: saved successfully");
}

/**
 * Migrate old global task state key to per-tab states.
 * Called once on service worker startup to clean up legacy data.
 */
export async function migrateOldTaskState() {
  const OLD_KEY = "any2summary_task_state";
  try {
    const { [OLD_KEY]: oldState } = await chrome.storage.local.get(OLD_KEY);
    if (oldState) {
      console.log("[Storage] migrateOldTaskState: removing old global task state");
      await chrome.storage.local.remove(OLD_KEY);
      console.log("[Storage] migrateOldTaskState: migration completed");
    }
  } catch (error) {
    console.error("[Storage] migrateOldTaskState failed:", error.message);
  }
}
