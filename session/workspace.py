# session/workspace.py
# Cômodo: caminhos e flags do workspace do engagement.
# Por quê: um eng por vez; DB + dirty/clean moram juntos no disco.

from __future__ import annotations

import json
import shutil
from pathlib import Path

# Raiz do projeto Racoon-Mask (pasta pai de session/)
ROOT = Path(__file__).resolve().parent.parent
WORKSPACES_DIR = ROOT / "workspaces"
META_FILE = WORKSPACES_DIR / "active_workspace.json"
FLAG_DIRTY = "session.flag"
DB_NAME = "engagement.db"


def garantir_raiz() -> None:
    WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)


def slug_seguro(nome: str) -> str:
    limpo = "".join(c if c.isalnum() or c in "-_" else "_" for c in nome.strip())
    return limpo[:80] or "engagement"


def caminho_workspace(nome: str) -> Path:
    return WORKSPACES_DIR / slug_seguro(nome)


def caminho_db(workspace: Path) -> Path:
    return workspace / DB_NAME


def caminho_flag(workspace: Path) -> Path:
    return workspace / FLAG_DIRTY


def ler_ativo() -> dict | None:
    garantir_raiz()
    if not META_FILE.exists():
        return None
    try:
        return json.loads(META_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def gravar_ativo(nome: str, caminho: Path) -> None:
    garantir_raiz()
    META_FILE.write_text(
        json.dumps(
            {"engagement_name": nome, "path": str(caminho)},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def limpar_ativo() -> None:
    if META_FILE.exists():
        META_FILE.unlink()


def criar_workspace(nome: str) -> Path:
    garantir_raiz()
    pasta = caminho_workspace(nome)
    pasta.mkdir(parents=True, exist_ok=True)
    gravar_ativo(nome, pasta)
    marcar_dirty(pasta)
    return pasta


def marcar_dirty(workspace: Path) -> None:
    caminho_flag(workspace).write_text("dirty\n", encoding="utf-8")


def marcar_clean(workspace: Path) -> None:
    flag = caminho_flag(workspace)
    if flag.exists():
        flag.unlink()


def esta_dirty(workspace: Path) -> bool:
    return caminho_flag(workspace).exists()


def apagar_workspace(workspace: Path) -> None:
    """Queima: remove pasta do engagement e metadado ativo."""
    if workspace.exists() and workspace.resolve().is_relative_to(WORKSPACES_DIR.resolve()):
        shutil.rmtree(workspace, ignore_errors=True)
    limpar_ativo()


def listar_workspaces_sujos() -> list[Path]:
    garantir_raiz()
    sujos: list[Path] = []
    for pasta in WORKSPACES_DIR.iterdir():
        if pasta.is_dir() and esta_dirty(pasta):
            sujos.append(pasta)
    return sujos


def detectar_workspace_anterior() -> Path | None:
    """
    Workspace a oferecer na reabertura:
    1) qualquer dirty (crash)
    2) active_workspace.json com DB intacta (CANCEL no burn = retenção)
    """
    sujos = listar_workspaces_sujos()
    if sujos:
        return sujos[0]

    meta = ler_ativo()
    if not meta:
        return None
    pasta = Path(meta.get("path", ""))
    if pasta.is_dir() and caminho_db(pasta).exists():
        return pasta
    return None


def nome_workspace(pasta: Path) -> str:
    meta = ler_ativo()
    if meta and Path(meta.get("path", "")).resolve() == pasta.resolve():
        return str(meta.get("engagement_name") or pasta.name)
    return pasta.name
