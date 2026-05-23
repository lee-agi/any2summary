"""Public package interface for any2summary.

The package keeps CLI imports lazy so ``python -m any2summary.cli`` can execute
without preloading the same module from package initialisation.
"""

from __future__ import annotations

from typing import Any

__all__ = ["main", "run"]


def __getattr__(name: str) -> Any:
    """Lazily expose CLI entry points at package level."""

    if name in __all__:
        from . import cli

        return getattr(cli, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
