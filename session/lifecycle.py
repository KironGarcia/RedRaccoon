# session/lifecycle.py
# Cômodo: abrir / fechar / burn / dirty da sessão.
# Por quê: retenção mínima — o X sempre passa por aqui.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from db.repository import Repository
from session import workspace as ws


@dataclass
class SessaoAtiva:
    nome: str
    pasta: Path
    repo: Repository
    engagement_id: int


class Lifecycle:
    """Controla o ciclo de vida de um engagement ativo."""

    def __init__(self) -> None:
        self.sessao: SessaoAtiva | None = None

    def detectar_dirty(self) -> list[Path]:
        return ws.listar_workspaces_sujos()

    def detectar_anterior(self) -> Path | None:
        return ws.detectar_workspace_anterior()

    def nome_anterior(self, pasta: Path) -> str:
        return ws.nome_workspace(pasta)

    def queimar_pasta(self, pasta: Path) -> None:
        if self.sessao and self.sessao.pasta.resolve() == pasta.resolve():
            self.sessao.repo.fechar()
            self.sessao = None
        ws.apagar_workspace(pasta)

    def queimar_todos_sujos(self) -> int:
        sujos = self.detectar_dirty()
        for pasta in sujos:
            self.queimar_pasta(pasta)
        return len(sujos)

    def queimar_anterior_e_limpar(self) -> None:
        """CANCEL no aviso de workspace antigo: queima e segue para wizard."""
        anterior = self.detectar_anterior()
        if anterior:
            self.queimar_pasta(anterior)
        # Garante limpeza de meta órfã
        ws.limpar_ativo()
        for pasta in list(ws.listar_workspaces_sujos()):
            self.queimar_pasta(pasta)

    def abrir_novo(self, nome: str) -> SessaoAtiva:
        if self.sessao:
            self.sessao.repo.fechar()
        pasta = ws.criar_workspace(nome)
        repo = Repository(ws.caminho_db(pasta))
        eng_id = repo.criar_engagement(engagement_name=nome)
        self.sessao = SessaoAtiva(
            nome=nome, pasta=pasta, repo=repo, engagement_id=eng_id
        )
        return self.sessao

    def reabrir_existente(self, pasta: Path) -> SessaoAtiva | None:
        db = ws.caminho_db(pasta)
        if not db.exists():
            return None
        if self.sessao:
            self.sessao.repo.fechar()
        repo = Repository(db)
        eng = repo.engagement_ativo()
        if not eng:
            repo.fechar()
            return None
        nome = eng["engagement_name"] or pasta.name
        ws.gravar_ativo(nome, pasta)
        ws.marcar_dirty(pasta)
        self.sessao = SessaoAtiva(
            nome=nome,
            pasta=pasta,
            repo=repo,
            engagement_id=eng["id"],
        )
        return self.sessao

    def burn_e_fechar(self) -> None:
        if not self.sessao:
            ws.limpar_ativo()
            return
        pasta = self.sessao.pasta
        self.sessao.repo.fechar()
        self.sessao = None
        ws.apagar_workspace(pasta)

    def manter_e_fechar(self) -> None:
        """NO no burn: mantém DB, marca clean e fecha."""
        if not self.sessao:
            return
        ws.marcar_clean(self.sessao.pasta)
        self.sessao.repo.fechar()
        # Mantém active_workspace.json para reabrir depois
        self.sessao = None
