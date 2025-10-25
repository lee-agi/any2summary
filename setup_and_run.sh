#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}"
VENV_DIR="${PROJECT_ROOT}/.venv"

PYTHON_BIN="${PYTHON_BIN:-python3}"

if [ ! -d "${VENV_DIR}" ]; then
  echo "[setup] Creating virtual environment at ${VENV_DIR}" >&2
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

source "${VENV_DIR}/bin/activate"

pip install --upgrade pip >/dev/null
pip install -r "${PROJECT_ROOT}/requirements.txt" >/dev/null

if printf '%s\n' "$@" | grep -F -q -- "--azure-diarization"; then
  if [ -z "${AZURE_OPENAI_API_KEY:-}" ] || [ -z "${AZURE_OPENAI_ENDPOINT:-}" ]; then
    echo "[error] AZURE_OPENAI_API_KEY 或 AZURE_OPENAI_ENDPOINT 未设置。" >&2
    exit 1
  fi
fi

exec "${VENV_DIR}/bin/python" -m podcast_transformer.cli "$@"
