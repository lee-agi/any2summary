"""Shared helpers for Azure end-to-end tests.

These helpers gate live calls on presence of required secrets and pytest
marker expressions, preventing accidental runs without credentials and
ensuring secrets are never printed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import pytest


@dataclass(frozen=True)
class AzureE2ECredentials:
    api_key: str
    endpoint: str
    summary_deployment: str
    api_version: Optional[str]

    @property
    def masked_api_key(self) -> str:
        if not self.api_key:
            return ""
        head = self.api_key[:4]
        tail = self.api_key[-4:] if len(self.api_key) > 8 else "****"
        return f"{head}****{tail}"


def should_run_e2e(marker_expr: Optional[str]) -> bool:
    if not marker_expr:
        return False
    lower_expr = marker_expr.lower()
    if "not e2e" in lower_expr:
        return False
    return "e2e" in lower_expr


def require_azure_e2e_credentials() -> AzureE2ECredentials:
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    summary_deployment = os.getenv("AZURE_OPENAI_SUMMARY_DEPLOYMENT")
    api_version = os.getenv("AZURE_OPENAI_SUMMARY_API_VERSION")

    if not api_key or not endpoint or not summary_deployment:
        pytest.skip(
            "Skip Azure e2e: set AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, "
            "AZURE_OPENAI_SUMMARY_DEPLOYMENT."
        )

    return AzureE2ECredentials(
        api_key=api_key,
        endpoint=endpoint,
        summary_deployment=summary_deployment,
        api_version=api_version,
    )
