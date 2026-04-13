"""Pytest hooks for e2e safety and helpers."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

import e2e_utils


def pytest_collection_modifyitems(config: pytest.Config, items: List[pytest.Item]) -> None:
    """Deselect e2e tests unless explicitly requested."""

    mark_expr = getattr(config.option, "markexpr", None)
    run_e2e = e2e_utils.should_run_e2e(mark_expr)

    deselected: List[pytest.Item] = []
    kept: List[pytest.Item] = []
    for item in items:
        if item.get_closest_marker("e2e") and not run_e2e:
            deselected.append(item)
        else:
            kept.append(item)

    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = kept


def pytest_runtest_setup(item: pytest.Item) -> None:
    if item.get_closest_marker("e2e"):
        e2e_utils.require_azure_e2e_credentials()
