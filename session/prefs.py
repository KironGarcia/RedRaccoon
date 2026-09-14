# session/prefs.py
# Cômodo: preferências da UI (só posição da janela).
# Por quê: o tamanho é fixo de fábrica; guardar o canto em que o usuário deixou.

from __future__ import annotations

import json
from pathlib import Path

from session.workspace import ROOT

PREFS_PATH = ROOT / ".cache" / "ui_prefs.json"


def carregar() -> dict:
    if not PREFS_PATH.exists():
        return {}
    try:
        dados = json.loads(PREFS_PATH.read_text(encoding="utf-8"))
        return dados if isinstance(dados, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def salvar(dados: dict) -> None:
    PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
    atuais = carregar()
    atuais.update(dados)
    PREFS_PATH.write_text(
        json.dumps(atuais, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
