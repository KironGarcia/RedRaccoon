# app/main.py
# Cômodo: porta de entrada do Racoon-Mask.
# Por quê: um único ponto para iniciar a janela desktop local.

from __future__ import annotations

import os
import sys
from pathlib import Path

# Garante imports a partir da raiz do projeto (Racoon-Mask/)
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Cache local do tldextract (evita escrita fora do projeto)
_cache_tld = ROOT / ".cache" / "tldextract"
_cache_tld.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("TLDEXTRACT_CACHE", str(_cache_tld))

from PySide6.QtWidgets import QApplication

from ui.fonts import carregar_fontes_app
from ui.raccoon import icone_janela
from ui.window import construir_app


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Racoon-Mask")
    app.setQuitOnLastWindowClosed(True)
    carregar_fontes_app()
    icone = icone_janela()
    app.setWindowIcon(icone)
    janela = construir_app()
    janela.setWindowIcon(icone)
    janela.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
