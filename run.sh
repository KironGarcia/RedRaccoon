#!/usr/bin/env bash
# Launcher Racoon-Mask — inicia a janela desktop (PySide6).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
exec "${ROOT}/.venv/bin/python" "${ROOT}/app/main.py" "$@"
