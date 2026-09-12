# core/reconstruct.py
# Cômodo: placeholder → valor real (lookup e replace em texto/arquivo).
# Por quê: a IA trabalha com máscara; o relatório final volta ao real.

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


RE_PLACEHOLDER = re.compile(
    r"\b("
    r"TARGET_IP_\d+"
    r"|TARGET_HOST_\d+"
    r"|TARGET_DOMAIN_\d+"
    r"|TARGET_EMAIL_\d+"
    r"|CLIENT_NAME(?:_\d+)?"
    r"|PERSON_\d+"
    r"|TARGET_[A-Z]+_\d+"
    r")\b"
)


def mapa_placeholders(repo: Any, engagement_id: int) -> dict[str, str]:
    """placeholder → real_value."""
    mapa: dict[str, str] = {}
    for row in repo.listar_mapeamentos(engagement_id):
        mapa[row["placeholder"]] = row["real_value"]
    return mapa


def reconstruir_texto(texto: str, mapa: dict[str, str]) -> str:
    if not mapa:
        return texto

    def trocar(m: re.Match) -> str:
        chave = m.group(1)
        return mapa.get(chave, chave)

    return RE_PLACEHOLDER.sub(trocar, texto)


def lookup_placeholder(
    repo: Any, engagement_id: int, placeholder: str
) -> str | None:
    row = repo.buscar_por_placeholder(engagement_id, placeholder.strip())
    return row["real_value"] if row else None


def replace_arquivo_md(
    caminho: Path, repo: Any, engagement_id: int
) -> tuple[bool, str, int]:
    """
    Substitui placeholders em arquivo .md / texto.
    Retorna (ok, mensagem, quantidade_trocada).
    """
    path = Path(caminho).expanduser()
    if not path.exists():
        return False, f"File not found: {path}", 0
    if path.suffix.lower() not in {".md", ".txt", ".text", ".log"}:
        return False, "v1 supports .md / .txt only (Word later).", 0

    original = path.read_text(encoding="utf-8", errors="replace")
    mapa = mapa_placeholders(repo, engagement_id)
    if not mapa:
        return True, "No mappings to apply.", 0

    novo = reconstruir_texto(original, mapa)
    # Conta trocas aproximadas
    trocas = 0
    for ph_key in mapa:
        trocas += original.count(ph_key)

    if novo == original:
        return True, "No placeholders found in file.", 0

    path.write_text(novo, encoding="utf-8")
    return True, f"Replaced placeholders in {path.name}.", trocas
