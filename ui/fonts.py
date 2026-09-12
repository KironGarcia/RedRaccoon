# ui/fonts.py
# Cômodo: registro de fontes empacotadas (cyberpunk do PAST).
# Por quê: Kali não traz Orbitron/Audiowide; vivem em assets/fonts/.

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase

_ASSETS_FONTS = Path(__file__).resolve().parent.parent / "assets" / "fonts"

# Preferência: Audiowide (mais “arcade/cyber”) → Orbitron → fallback sistema
_ARQUIVOS = (
    "Audiowide-Regular.ttf",
    "Orbitron-Bold.ttf",
)

_familia_past: str | None = None


def carregar_fontes_app() -> None:
    """Registra TTFs locais uma vez no boot do QApplication."""
    global _familia_past
    for nome in _ARQUIVOS:
        caminho = _ASSETS_FONTS / nome
        if not caminho.is_file():
            continue
        fid = QFontDatabase.addApplicationFont(str(caminho))
        if fid < 0:
            continue
        familias = QFontDatabase.applicationFontFamilies(fid)
        if familias and _familia_past is None:
            _familia_past = familias[0]


def fonte_past(tamanho: int = 14) -> QFont:
    """Fonte do botão PAST INPUT — cyberpunk se carregou; senão mono bold."""
    if _familia_past:
        f = QFont(_familia_past, tamanho)
        f.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        return f
    f = QFont("DejaVu Sans Mono", tamanho)
    f.setBold(True)
    return f
