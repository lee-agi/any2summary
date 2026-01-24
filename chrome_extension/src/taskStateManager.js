/**
 * Tab-level task state manager for parallel summarization.
 * Stores states keyed by tabId to allow multiple tabs to run summaries concurrently.
 */

const TASK_STATES_KEY = "any2summary_task_states";

export class TaskStateManager {
  /**
   * Get state for a specific tab.
   * @param {number} tabId - The tab ID
   * @returns {Promise<Object|null>} The state object or null if not found
   */
  async getState(tabId) {
    const states = await this._loadAllStates();
    return states[tabId] || null;
  }

  /**
   * Set state for a specific tab.
   * @param {number} tabId - The tab ID
   * @param {Object} state - The state object (status, message, isError, url)
   */
  async setState(tabId, state) {
    const states = await this._loadAllStates();
    states[tabId] = { ...state, timestamp: Date.now(), tabId };
    await this._saveAllStates(states);
  }

  /**
   * Clear state for a specific tab.
   * @param {number} tabId - The tab ID
   */
  async clearState(tabId) {
    const states = await this._loadAllStates();
    delete states[tabId];
    await this._saveAllStates(states);
  }

  /**
   * Get all tab states (useful for debugging).
   * @returns {Promise<Object>} Map of tabId -> state
   */
  async getAllStates() {
    return this._loadAllStates();
  }

  /**
   * Clean up states for tabs that have been closed.
   */
  async cleanupClosedTabs() {
    const tabs = await chrome.tabs.query({});
    const activeTabIds = new Set(tabs.map((t) => t.id));
    const states = await this._loadAllStates();

    let changed = false;
    for (const tabId of Object.keys(states)) {
      if (!activeTabIds.has(parseInt(tabId, 10))) {
        console.log("[TaskStateManager] Cleaning up closed tab:", tabId);
        delete states[tabId];
        changed = true;
      }
    }

    if (changed) {
      await this._saveAllStates(states);
    }
  }

  /**
   * Clean up stale states (non-running states older than 30 minutes).
   */
  async cleanupStaleStates() {
    const states = await this._loadAllStates();
    const now = Date.now();
    const maxAge = 30 * 60 * 1000; // 30 minutes

    let changed = false;
    for (const [tabId, state] of Object.entries(states)) {
      const age = now - (state.timestamp || 0);
      if (state.status !== "running" && age > maxAge) {
        console.log("[TaskStateManager] Cleaning up stale state for tab:", tabId);
        delete states[tabId];
        changed = true;
      }
    }

    if (changed) {
      await this._saveAllStates(states);
    }
  }

  /**
   * Load all states from storage.
   * @private
   */
  async _loadAllStates() {
    try {
      const { [TASK_STATES_KEY]: states } =
        await chrome.storage.local.get(TASK_STATES_KEY);
      return states || {};
    } catch (error) {
      console.error("[TaskStateManager] Failed to load states:", error.message);
      return {};
    }
  }

  /**
   * Save all states to storage.
   * @private
   */
  async _saveAllStates(states) {
    try {
      await chrome.storage.local.set({ [TASK_STATES_KEY]: states });
    } catch (error) {
      console.error("[TaskStateManager] Failed to save states:", error.message);
    }
  }
}

// Export singleton instance
export const taskStateManager = new TaskStateManager();
