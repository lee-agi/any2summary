"""Tests for Chrome extension TaskStateManager module.

Verifies that the task state manager module exists, has the correct structure,
and that related modules have been properly updated for tab-level state management.
"""

from __future__ import annotations

import re
from pathlib import Path


CHROME_EXT_SRC = Path("chrome_extension/src")


def test_task_state_manager_module_exists() -> None:
    """Verify taskStateManager.js exists and exports required class/functions."""
    module_path = CHROME_EXT_SRC / "taskStateManager.js"
    assert module_path.is_file(), "taskStateManager.js should exist"

    content = module_path.read_text(encoding="utf-8")

    # Check for TaskStateManager class export
    assert "export class TaskStateManager" in content, (
        "taskStateManager.js should export TaskStateManager class"
    )

    # Check for singleton instance export
    assert "export const taskStateManager" in content, (
        "taskStateManager.js should export taskStateManager singleton"
    )


def test_task_state_manager_has_required_methods() -> None:
    """Verify TaskStateManager class has all required methods."""
    module_path = CHROME_EXT_SRC / "taskStateManager.js"
    content = module_path.read_text(encoding="utf-8")

    required_methods = [
        "getState",
        "setState",
        "clearState",
        "getAllStates",
        "cleanupClosedTabs",
        "cleanupStaleStates",
        "_loadAllStates",
        "_saveAllStates",
    ]

    for method in required_methods:
        assert f"async {method}(" in content, (
            f"TaskStateManager should have {method} method"
        )


def test_task_state_manager_uses_tab_keyed_storage() -> None:
    """Verify TaskStateManager uses tab-keyed storage structure."""
    module_path = CHROME_EXT_SRC / "taskStateManager.js"
    content = module_path.read_text(encoding="utf-8")

    # Should use a different key than the old global state key
    assert "any2summary_task_states" in content, (
        "Should use 'any2summary_task_states' key for tab-level storage"
    )
    # Should NOT use the old single-state key
    assert 'TASK_STATE_KEY' not in content or '"any2summary_task_state"' not in content, (
        "Should not use the old global 'any2summary_task_state' key"
    )


def test_storage_module_has_migration_function() -> None:
    """Verify storage.js has migration function and removed old task functions."""
    module_path = CHROME_EXT_SRC / "storage.js"
    content = module_path.read_text(encoding="utf-8")

    # Should have migration function
    assert "migrateOldTaskState" in content, (
        "storage.js should have migrateOldTaskState function"
    )

    # Should NOT export old task state functions
    assert "export async function saveTaskState" not in content, (
        "storage.js should not export saveTaskState"
    )
    assert "export async function loadTaskState" not in content, (
        "storage.js should not export loadTaskState"
    )
    assert "export async function clearTaskState" not in content, (
        "storage.js should not export clearTaskState"
    )


def test_background_imports_task_state_manager() -> None:
    """Verify background.js imports and uses TaskStateManager."""
    module_path = CHROME_EXT_SRC / "background.js"
    content = module_path.read_text(encoding="utf-8")

    # Should import taskStateManager
    assert 'import { taskStateManager }' in content or \
           'import { TaskStateManager }' in content, (
        "background.js should import taskStateManager"
    )

    # Should use taskStateManager.setState
    assert "taskStateManager.setState" in content, (
        "background.js should use taskStateManager.setState"
    )

    # Should NOT use old saveTaskState
    assert "saveTaskState(" not in content, (
        "background.js should not use old saveTaskState"
    )


def test_background_broadcasts_with_tab_id() -> None:
    """Verify background.js broadcastStatus includes tabId."""
    module_path = CHROME_EXT_SRC / "background.js"
    content = module_path.read_text(encoding="utf-8")

    # broadcastStatus should accept tabId as first parameter
    assert re.search(r"function broadcastStatus\(tabId", content), (
        "broadcastStatus should accept tabId as first parameter"
    )

    # Payload should include tabId
    assert "payload: { tabId," in content or "payload: {tabId," in content, (
        "broadcastStatus payload should include tabId"
    )


def test_background_handles_tab_close() -> None:
    """Verify background.js cleans up state when tab is closed."""
    module_path = CHROME_EXT_SRC / "background.js"
    content = module_path.read_text(encoding="utf-8")

    # Should listen for tab removal
    assert "chrome.tabs.onRemoved.addListener" in content, (
        "background.js should listen for tab removal"
    )

    # Should clear state on tab close
    assert "taskStateManager.clearState" in content, (
        "background.js should clear state when tab closes"
    )


def test_popup_imports_task_state_manager() -> None:
    """Verify popup.js imports and uses TaskStateManager."""
    module_path = CHROME_EXT_SRC / "popup.js"
    content = module_path.read_text(encoding="utf-8")

    # Should import taskStateManager
    assert 'import { taskStateManager }' in content, (
        "popup.js should import taskStateManager"
    )

    # Should use taskStateManager.getState
    assert "taskStateManager.getState" in content, (
        "popup.js should use taskStateManager.getState"
    )

    # Should NOT import old loadTaskState
    assert "loadTaskState" not in content, (
        "popup.js should not import old loadTaskState"
    )


def test_popup_tracks_current_tab_id() -> None:
    """Verify popup.js tracks and uses current tab ID."""
    module_path = CHROME_EXT_SRC / "popup.js"
    content = module_path.read_text(encoding="utf-8")

    # Should have currentTabId variable
    assert "currentTabId" in content, (
        "popup.js should have currentTabId variable"
    )

    # Should query for active tab
    assert "chrome.tabs.query" in content, (
        "popup.js should query for active tab"
    )


def test_popup_filters_messages_by_tab_id() -> None:
    """Verify popup.js filters status update messages by tab ID."""
    module_path = CHROME_EXT_SRC / "popup.js"
    content = module_path.read_text(encoding="utf-8")

    # Should check message payload tabId
    assert "message.payload.tabId" in content, (
        "popup.js should check message.payload.tabId"
    )

    # Should compare with currentTabId
    assert "currentTabId" in content and "tabId" in content, (
        "popup.js should compare tabId with currentTabId"
    )


def test_sidepanel_imports_task_state_manager() -> None:
    """Verify sidepanel.js imports and uses TaskStateManager."""
    module_path = CHROME_EXT_SRC / "sidepanel.js"
    content = module_path.read_text(encoding="utf-8")

    # Should import taskStateManager
    assert 'import { taskStateManager }' in content, (
        "sidepanel.js should import taskStateManager"
    )

    # Should use taskStateManager.getState
    assert "taskStateManager.getState" in content, (
        "sidepanel.js should use taskStateManager.getState"
    )

    # Should NOT import old loadTaskState
    assert "loadTaskState" not in content, (
        "sidepanel.js should not import old loadTaskState"
    )


def test_sidepanel_tracks_current_tab_id() -> None:
    """Verify sidepanel.js tracks and updates current tab ID."""
    module_path = CHROME_EXT_SRC / "sidepanel.js"
    content = module_path.read_text(encoding="utf-8")

    # Should have currentTabId variable
    assert "currentTabId" in content, (
        "sidepanel.js should have currentTabId variable"
    )

    # Should listen for tab activation
    assert "chrome.tabs.onActivated" in content, (
        "sidepanel.js should listen for tab activation"
    )


def test_sidepanel_filters_messages_by_tab_id() -> None:
    """Verify sidepanel.js filters status update messages by tab ID."""
    module_path = CHROME_EXT_SRC / "sidepanel.js"
    content = module_path.read_text(encoding="utf-8")

    # Should check message payload tabId
    assert "message.payload.tabId" in content, (
        "sidepanel.js should check message.payload.tabId"
    )


def test_task_state_manager_has_jsdoc() -> None:
    """Verify taskStateManager.js has JSDoc comments for methods."""
    module_path = CHROME_EXT_SRC / "taskStateManager.js"
    content = module_path.read_text(encoding="utf-8")

    # Check for JSDoc comments
    assert "/**" in content and "*/" in content, (
        "taskStateManager.js should have JSDoc comments"
    )

    # Key methods should have @param documentation
    assert "@param" in content, (
        "taskStateManager.js should have @param in JSDoc"
    )
