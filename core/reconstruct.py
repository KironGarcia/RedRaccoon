# core/reconstruct.py
# Cômodo: placeholder → valor real (lookup e replace em texto/arquivo).
# Por quê: a IA trabalha com máscara; o relatório final volta ao real.

from __future__ import annotations

import re
from dataclasses import dataclass, field
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


def _tipo_placeholder(chave: str) -> str:
    """TARGET_IP_1 → IP; PERSON_1 → PERSON — rótulo da tabela."""
    u = (chave or "").upper()
    if u.startswith("CLIENT_NAME"):
        return "ORG"
    if u.startswith("PERSON_"):
        return "PERSON"
    m = re.match(r"TARGET_([A-Z]+)_\d+$", u)
    if m:
        return m.group(1)
    return "OTHER"


@dataclass
class ResultadoReconstruct:
    """Rodada de relatório: texto reconstruído + resumo (não persiste mapa novo)."""

    texto_original: str
    texto_reconstruido: str
    resumo: list[dict] = field(default_factory=list)
    nao_mapeados: list[str] = field(default_factory=list)

    @property
    def teve_troca(self) -> bool:
        return any(int(r.get("times") or 0) > 0 for r in self.resumo)


def reconstruir_relatorio(
    texto: str, repo: Any, engagement_id: int
) -> ResultadoReconstruct:
    """Clipboard de relatório → placeholders conhecidos viram valor real."""
    original = texto or ""
    mapa = mapa_placeholders(repo, engagement_id)
    achados = RE_PLACEHOLDER.findall(original)
    ordem: list[str] = []
    vistos: set[str] = set()
    for ph in achados:
        if ph not in vistos:
            vistos.add(ph)
            ordem.append(ph)

    resumo: list[dict] = []
    nao_mapeados: list[str] = []
    for ph in ordem:
        n = original.count(ph)
        real = mapa.get(ph)
        if real is None:
            nao_mapeados.append(ph)
            continue
        resumo.append(
            {
                "type": _tipo_placeholder(ph),
                "placeholder": ph,
                "real": real,
                "times": n,
            }
        )

    novo = reconstruir_texto(original, mapa) if mapa else original
    return ResultadoReconstruct(
        texto_original=original,
        texto_reconstruido=novo,
        resumo=resumo,
        nao_mapeados=nao_mapeados,
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
