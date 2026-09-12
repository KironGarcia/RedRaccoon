# session/learning.py
# Cômodo: allowlist dinâmica PERMANENTE (aprendizado entre engagements).
# Por quê: allowed= são palavras NÃO confidenciais — sobrevive ao burn.
# blocked=/dados de cliente ficam só no SQLite do workspace (queimam).

from __future__ import annotations

import json
from pathlib import Path

from session.workspace import ROOT

# Fora de workspaces/ — burn do eng NÃO apaga isto
ALLOW_PATH = ROOT / ".cache" / "global_allow.json"


def carregar_allow() -> list[str]:
    if not ALLOW_PATH.exists():
        return []
    try:
        dados = json.loads(ALLOW_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(dados, list):
        return []
    return [str(x).strip() for x in dados if str(x).strip()]


def _salvar_allow(termos: list[str]) -> None:
    ALLOW_PATH.parent.mkdir(parents=True, exist_ok=True)
    ALLOW_PATH.write_text(
        json.dumps(termos, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def adicionar_allow(termos: list[str]) -> list[str]:
    """
    Acrescenta termos à allow global (sem duplicata, casefold).
    Retorna só os que entraram agora.
    """
    atual = carregar_allow()
    vistos = {a.casefold() for a in atual}
    adicionados: list[str] = []
    for t in termos:
        limpo = (t or "").strip()
        if not limpo or limpo.casefold() in vistos:
            continue
        atual.append(limpo)
        vistos.add(limpo.casefold())
        adicionados.append(limpo)
    if adicionados:
        _salvar_allow(atual)
    return adicionados
