# ui/window.py
# Cômodo: janela compacta + eventos (única orquestração da UI).
# Por quê: UI dispara; core/db/session fazem o trabalho pesado.
# Stack UI: PySide6 (Flet exigia libmpv incompatível neste host Kali).

from __future__ import annotations

from enum import Enum, auto
from pathlib import Path
from typing import Any

import pyperclip
from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, Qt
from PySide6.QtGui import (
    QGuiApplication,
    QMouseEvent,
    QResizeEvent,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QButtonGroup,
)

from core.queries import (
    Intencao,
    aplicar_itens_blocklist,
    classificar_blocked,
    executar_lookup,
    executar_replace_md,
    executar_reveal,
    interpretar,
    parece_pedido_llm,
    parece_scan_cru,
    texto_longo_para_questions,
)
from core.reconstruct import ResultadoReconstruct, reconstruir_relatorio
from core.sanitize import ResultadoSanitize, Sanitizer
from session import learning as learn
from session import prefs as ui_prefs
from session.lifecycle import Lifecycle
from ui import dialogs as D
from ui import theme as T
from ui.fonts import fonte_past
from ui.raccoon import AvatarRacoon, BotaoEnviar, CaudaBalao, icone_janela


class FaseUI(Enum):
    BOOT = auto()
    OLD_WORKSPACE = auto()
    WIZARD_NOME = auto()
    WIZARD_ITENS = auto()
    PRONTO = auto()
    PENDENTE_SANITIZE = auto()
    PENDENTE_RECONSTRUCT = auto()
    BURN = auto()


class ModoUI(Enum):
    MASK = auto()
    REDACTOR = auto()


class RacoonWindow(QMainWindow):
    """Janela única do Racoon-Mask — móvel, tamanho fixo, sem always-on-top."""

    def __init__(self) -> None:
        super().__init__()
        self.life = Lifecycle()
        self.sanitizer = Sanitizer()
        self.fase = FaseUI.BOOT
        self.modo = ModoUI.MASK
        self.pendente: ResultadoSanitize | None = None
        self.pendente_recon: ResultadoReconstruct | None = None
        self._pasta_anterior: Path | None = None
        self._drag_pos: QPoint | None = None

        self.setWindowTitle("Racoon-Mask")
        self.setWindowIcon(icone_janela())
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(T.LARGURA_JANELA, T.ALTURA_JANELA)
        self.setStyleSheet(T.STYLESHEET)

        self._montar_layout()
        self._restaurar_geometria()
        self._boot()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _montar_layout(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        root.setMouseTracking(True)
        self.setCentralWidget(root)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        # Respiro do X no canto (antes era a faixa do grip de resize)
        outer.addSpacing(T.MARGEM_FECHAR + 6)

        self.btn_fechar = QPushButton("✕", root)
        self.btn_fechar.setObjectName("fechar")
        self.btn_fechar.setFixedSize(20, 20)
        self.btn_fechar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_fechar.clicked.connect(self._on_fechar)
        self.btn_fechar.raise_()

        col = QVBoxLayout()
        col.setContentsMargins(12, 0, 8, 4)
        col.setSpacing(4)
        outer.addLayout(col, 1)

        topo = QHBoxLayout()
        # Pouco espaço avatar→cauda; cauda colada no balão
        topo.setSpacing(4)
        self.avatar = AvatarRacoon(T.AVATAR_TAM)
        self.btn_mask = QPushButton("MASK")
        self.btn_mask.setObjectName("modo")
        self.btn_mask.setCheckable(True)
        self.btn_mask.setChecked(True)
        self.btn_mask.setFixedSize(T.MODO_BTN_LARGURA, T.MODO_BTN_ALTURA)
        self.btn_mask.setFont(fonte_past(13))
        self.btn_mask.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mask.setToolTip("Mask mode — sanitize tool output")
        self.btn_mask.clicked.connect(lambda: self._on_modo(ModoUI.MASK))
        self.btn_redactor = QPushButton("REDACTOR")
        self.btn_redactor.setObjectName("modo")
        self.btn_redactor.setCheckable(True)
        self.btn_redactor.setFixedSize(T.MODO_BTN_LARGURA, T.MODO_BTN_ALTURA)
        self.btn_redactor.setFont(fonte_past(13))
        self.btn_redactor.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_redactor.setToolTip("Redactor mode — restore real values in reports")
        self.btn_redactor.clicked.connect(lambda: self._on_modo(ModoUI.REDACTOR))
        self.grp_modo = QButtonGroup(self)
        self.grp_modo.setExclusive(True)
        self.grp_modo.addButton(self.btn_mask)
        self.grp_modo.addButton(self.btn_redactor)

        col_avatar = QVBoxLayout()
        col_avatar.setContentsMargins(0, 0, 0, 0)
        col_avatar.setSpacing(T.MODO_BTN_ESPACO)
        col_avatar.addWidget(self.avatar, 0, Qt.AlignmentFlag.AlignHCenter)
        col_avatar.addWidget(self.btn_mask, 0, Qt.AlignmentFlag.AlignHCenter)
        col_avatar.addWidget(self.btn_redactor, 0, Qt.AlignmentFlag.AlignHCenter)
        col_avatar.addStretch(1)

        self.lbl_balao = QTextEdit()
        self.lbl_balao.setObjectName("balao")
        self.lbl_balao.setReadOnly(True)
        self.lbl_balao.setFrameStyle(0)
        self.lbl_balao.setMinimumHeight(T.BALAO_ALTURA_MIN)
        self.lbl_balao.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.lbl_balao.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        # Cauda alinhada ao meio do rosto do Racoon
        cauda_col = QVBoxLayout()
        cauda_col.setContentsMargins(0, 0, 0, 0)
        cauda_col.setSpacing(0)
        cauda_topo = max(0, (T.AVATAR_TAM - T.CAUDA_ALTURA) // 2)
        cauda_col.addSpacing(cauda_topo)
        cauda_col.addWidget(CaudaBalao(), 0, Qt.AlignmentFlag.AlignLeft)
        cauda_col.addStretch(1)

        balao_row = QHBoxLayout()
        balao_row.setContentsMargins(0, 0, 0, 0)
        balao_row.setSpacing(0)
        balao_row.addLayout(cauda_col)
        balao_row.addWidget(self.lbl_balao, 1)

        topo.addLayout(col_avatar, 0)
        topo.setAlignment(col_avatar, Qt.AlignmentFlag.AlignTop)
        topo.addLayout(balao_row, 1)
        topo.addSpacing(T.MARGEM_BALAO_DIR)
        col.addLayout(topo, 1)

        acoes_bar = QWidget()
        acoes_bar.setFixedHeight(T.ACOES_ALTURA)
        acoes = QHBoxLayout(acoes_bar)
        acoes.setContentsMargins(0, 0, 0, 0)
        acoes.setSpacing(0)
        acoes.addStretch(1)
        self.btn_acept = QPushButton("ACEPT")
        self.btn_acept.setObjectName("acept")
        self.btn_acept.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_acept.clicked.connect(self._on_acept)
        self.btn_cancel = QPushButton("CANCEL")
        self.btn_cancel.setObjectName("cancel")
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.clicked.connect(self._on_cancel)
        self.btn_back = QPushButton("BACK")
        self.btn_back.setObjectName("voltar")
        self.btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_back.clicked.connect(self._on_back)
        acoes.addWidget(self.btn_acept)
        acoes.addWidget(self.btn_cancel)
        acoes.addWidget(self.btn_back)
        acoes.addSpacing(T.MARGEM_BALAO_DIR)
        col.addWidget(acoes_bar, 0)
        self._mostrar_decisao(False)

        barra = QFrame()
        barra.setObjectName("barra")
        barra_lay = QHBoxLayout(barra)
        barra_lay.setContentsMargins(6, 6, 6, 6)
        barra_lay.setSpacing(6)

        self.txt_questions = QLineEdit()
        self.txt_questions.setObjectName("questions")
        self.txt_questions.setPlaceholderText(T.PLACEHOLDER_QUESTIONS)
        self.txt_questions.setMaxLength(T.LIMITE_QUESTIONS)
        self.txt_questions.setFixedHeight(T.BARRA_CTRL_ALTURA)
        self.txt_questions.returnPressed.connect(self._on_enviar)

        self.btn_send = BotaoEnviar(T.BARRA_CTRL_ALTURA)
        self.btn_send.clicked.connect(self._on_enviar)

        self.btn_past = QPushButton("PAST INPUT")
        self.btn_past.setObjectName("past")
        self.btn_past.setFixedHeight(T.BARRA_CTRL_ALTURA)
        self.btn_past.setFont(fonte_past(17))
        self.btn_past.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_past.setToolTip("Paste scan / sensitive output from clipboard")
        self.btn_past.clicked.connect(self._on_past_input)
        self._past_opacidade = QGraphicsOpacityEffect(self.btn_past)
        self._past_opacidade.setOpacity(1.0)
        self.btn_past.setGraphicsEffect(self._past_opacidade)
        self._past_anim: QPropertyAnimation | None = None

        # Mesma altura + AlignVCenter = barra alinhada (PAST não “desce”)
        barra_lay.addWidget(
            self.txt_questions, T.QUESTIONS_STRETCH, Qt.AlignmentFlag.AlignVCenter
        )
        barra_lay.addWidget(self.btn_send, 0, Qt.AlignmentFlag.AlignVCenter)
        barra_lay.addWidget(
            self.btn_past, T.PAST_STRETCH, Qt.AlignmentFlag.AlignVCenter
        )
        col.addWidget(barra)
        outer.addSpacing(6)

        self._posicionar_fechar()

    def _posicionar_fechar(self) -> None:
        """X equidistante do topo e da direita (sketch azul)."""
        root = self.centralWidget()
        if root is None:
            return
        m = T.MARGEM_FECHAR
        self.btn_fechar.move(
            root.width() - self.btn_fechar.width() - m,
            m,
        )
        self.btn_fechar.raise_()

    def _restaurar_geometria(self) -> None:
        """Tamanho de fábrica; só restaura o canto se o usuário já moveu a janela."""
        self.setFixedSize(T.LARGURA_JANELA, T.ALTURA_JANELA)
        p = ui_prefs.carregar()
        screen = QGuiApplication.primaryScreen()
        if "x" in p and "y" in p:
            self.move(int(p["x"]), int(p["y"]))
        elif screen:
            geo = screen.availableGeometry()
            x = geo.x() + geo.width() - T.LARGURA_JANELA - T.MARGEM_DIREITA
            y = geo.y() + geo.height() - T.ALTURA_JANELA - T.MARGEM_INFERIOR
            self.move(max(geo.x(), x), max(geo.y(), y))

    def _salvar_geometria(self) -> None:
        ui_prefs.salvar(
            {
                "x": self.x(),
                "y": self.y(),
            }
        )

    def _falar(
        self,
        texto: str,
        *,
        mostrar_decisao: bool = False,
        mostrar_voltar: bool = False,
    ) -> None:
        self.lbl_balao.setPlainText(texto)
        self.lbl_balao.moveCursor(QTextCursor.MoveOperation.Start)
        if mostrar_voltar:
            self._mostrar_decisao(False, mostrar_voltar=True)
            return
        if mostrar_decisao and self.fase == FaseUI.BURN:
            # Fechar app: YES/NO (scan continua com ACEPT/CANCEL)
            self._mostrar_decisao(True, rotulos=("YES", "NO"))
        elif mostrar_decisao:
            self._mostrar_decisao(True, rotulos=("ACEPT", "CANCEL"))
        else:
            self._mostrar_decisao(False)

    def _aviso_e_voltar(self, texto: str) -> None:
        """Aviso de passo errado — BACK devolve o diálogo anterior."""
        self._falar(texto, mostrar_voltar=True)

    def _mostrar_decisao(
        self,
        visivel: bool,
        *,
        rotulos: tuple[str, str] = ("ACEPT", "CANCEL"),
        mostrar_voltar: bool = False,
    ) -> None:
        self.btn_acept.setText(rotulos[0])
        self.btn_cancel.setText(rotulos[1])
        # YES/NO (burn) um pouco maior que ACEPT/CANCEL (scan)
        if rotulos == ("YES", "NO"):
            px = T.FONTE_YES_NO
        else:
            px = T.FONTE_ACEPT_CANCEL
        for btn in (self.btn_acept, self.btn_cancel, self.btn_back):
            f = btn.font()
            f.setPixelSize(px)
            f.setBold(False)
            btn.setFont(f)
        self.btn_back.setVisible(mostrar_voltar)
        if mostrar_voltar:
            self.btn_acept.setVisible(False)
            self.btn_cancel.setVisible(False)
            return
        self.btn_acept.setVisible(visivel)
        self.btn_cancel.setVisible(visivel)

    def _limpar_input(self) -> None:
        self.txt_questions.clear()

    # ------------------------------------------------------------------
    # Arrastar a janela (tamanho fixo — sem resize)
    # ------------------------------------------------------------------

    def _widget_bloqueia_drag(self, filho: QWidget | None) -> bool:
        if filho is None:
            return False
        if isinstance(filho, (QPushButton, QLineEdit, QTextEdit)):
            return True
        nome = filho.objectName()
        return nome in {
            "acept",
            "cancel",
            "voltar",
            "past",
            "send",
            "fechar",
            "questions",
            "balao",
            "modo",
        }

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        pos = event.position().toPoint()
        filho = self.childAt(pos)
        if self._widget_bloqueia_drag(filho):
            super().mousePressEvent(event)
            return
        self._drag_pos = (
            event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        )
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if (
            self._drag_pos is not None
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            if self._drag_pos is not None:
                self._salvar_geometria()
            self._drag_pos = None
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._posicionar_fechar()

    # ------------------------------------------------------------------
    # Boot
    # ------------------------------------------------------------------

    def _boot(self) -> None:
        anterior = self.life.detectar_anterior()
        if anterior:
            self._pasta_anterior = anterior
            self.fase = FaseUI.OLD_WORKSPACE
            nome = self.life.nome_anterior(anterior)
            self._falar(D.msg_old_workspace(nome), mostrar_decisao=True)
            return
        self.fase = FaseUI.WIZARD_NOME
        self._falar(D.MSG_WELCOME_NAME)

    def _eng(self) -> dict[str, Any] | None:
        if not self.life.sessao:
            return None
        eng = self.life.sessao.repo.engagement_ativo()
        if not eng:
            return None
        # Allow dinâmica = aprendizado global (não queima com o eng)
        # Merge com allow antiga do SQLite (migração suave de calibragens pré-split)
        global_allow = learn.carregar_allow()
        local_allow = eng.get("allow_list") or []
        fundidos: list[str] = []
        vistos: set[str] = set()
        for t in global_allow + local_allow:
            k = t.casefold()
            if k in vistos:
                continue
            vistos.add(k)
            fundidos.append(t)
        eng = dict(eng)
        eng["allow_list"] = fundidos
        return eng

    def _eng_pronto(self) -> bool:
        """Wizard fechado + sessão com engagement — mapa local existe."""
        if self.fase not in (
            FaseUI.PRONTO,
            FaseUI.PENDENTE_SANITIZE,
            FaseUI.PENDENTE_RECONSTRUCT,
        ):
            return False
        return self.life.sessao is not None and self._eng() is not None

    def _descartar_pendentes(self) -> None:
        """Troca de modo / novo PAST — não deixa rascunho órfão."""
        if self.fase == FaseUI.PENDENTE_SANITIZE and self.pendente:
            if self.pendente.teve_sensivel and self.life.sessao:
                self.sanitizer.descartar_rodada(
                    self.life.sessao.repo, self.pendente
                )
        self.pendente = None
        self.pendente_recon = None
        if self.fase in (
            FaseUI.PENDENTE_SANITIZE,
            FaseUI.PENDENTE_RECONSTRUCT,
        ):
            self.fase = FaseUI.PRONTO

    def _aplicar_chrome_modo(self) -> None:
        """PAST muda de nome com o modo — o olho vê em que mundo está."""
        mask = self.modo == ModoUI.MASK
        self.btn_mask.setChecked(mask)
        self.btn_redactor.setChecked(not mask)
        if mask:
            self.btn_past.setText("PAST INPUT")
            self.btn_past.setToolTip(
                "Paste scan / sensitive output from clipboard"
            )
        else:
            self.btn_past.setText("PAST REPORT")
            self.btn_past.setToolTip(
                "Paste masked report text — restore real client values"
            )

    def _fala_mask_atual(self) -> None:
        if self.fase == FaseUI.OLD_WORKSPACE:
            nome = (
                self.life.nome_anterior(self._pasta_anterior)
                if self._pasta_anterior
                else ""
            )
            self._falar(D.msg_old_workspace(nome), mostrar_decisao=True)
            return
        if self.fase == FaseUI.WIZARD_ITENS:
            self._falar(D.MSG_CONFIDENTIAL_FORMAT)
            return
        if self.fase == FaseUI.PRONTO:
            self._falar(D.MSG_READY)
            return
        self._falar(D.MSG_WELCOME_NAME)

    def _on_modo(self, modo: ModoUI) -> None:
        if self.fase == FaseUI.BURN:
            self._aplicar_chrome_modo()
            return
        self._descartar_pendentes()
        self.modo = modo
        self._aplicar_chrome_modo()
        if modo == ModoUI.MASK:
            self._fala_mask_atual()
            return
        if not self._eng_pronto():
            self._aviso_e_voltar(D.MSG_REDACTOR_SEM_ENG)
            return
        self._falar(D.MSG_WELCOME_REDACTOR)

    # ------------------------------------------------------------------
    # Eventos
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:  # noqa: N802
        self._salvar_geometria()
        if self.fase == FaseUI.BURN:
            event.accept()
            return
        event.ignore()
        self._on_fechar()

    def _on_fechar(self) -> None:
        if self.fase == FaseUI.BURN:
            return
        # X / saída: interrompe 'pensando' e volta ao asset normal
        self.avatar.estatico()
        self.fase = FaseUI.BURN
        self._falar(D.MSG_BURN, mostrar_decisao=True)

    def _on_enviar(self) -> None:
        texto = self.txt_questions.text().strip()
        self._limpar_input()

        if self.fase == FaseUI.BURN:
            self._tratar_burn_texto(texto)
            return
        if self.modo == ModoUI.REDACTOR and not self._eng_pronto():
            self._aviso_e_voltar(D.MSG_REDACTOR_SEM_ENG)
            return
        if self.fase == FaseUI.OLD_WORKSPACE:
            self._falar(
                D.msg_old_workspace(
                    self.life.nome_anterior(self._pasta_anterior)
                    if self._pasta_anterior
                    else ""
                ),
                mostrar_decisao=True,
            )
            return
        if self.fase == FaseUI.WIZARD_NOME:
            self._tratar_wizard_nome(texto)
            return
        if self.fase == FaseUI.WIZARD_ITENS:
            self._tratar_wizard_itens(texto)
            return
        if self.fase == FaseUI.PENDENTE_SANITIZE:
            self._tratar_calibracao_pendente(texto)
            return
        if self.fase == FaseUI.PENDENTE_RECONSTRUCT:
            self._falar(
                "Decide with ACEPT or CANCEL.",
                mostrar_decisao=True,
            )
            return
        if self.fase == FaseUI.PRONTO:
            self._tratar_questions(texto)

    def _on_acept(self) -> None:
        if self.fase == FaseUI.BURN:
            self._burn_yes()
            return
        if self.fase == FaseUI.OLD_WORKSPACE:
            self._continuar_anterior()
            return
        if self.fase == FaseUI.PENDENTE_SANITIZE and self.pendente:
            self._acept_sanitize()
            return
        if self.fase == FaseUI.PENDENTE_RECONSTRUCT and self.pendente_recon:
            self._acept_reconstruir()

    def _on_cancel(self) -> None:
        if self.fase == FaseUI.BURN:
            self._burn_no()
            return
        if self.fase == FaseUI.OLD_WORKSPACE:
            self._queimar_anterior_novo()
            return
        if self.fase == FaseUI.PENDENTE_SANITIZE and self.pendente:
            self._cancel_sanitize()
            return
        if self.fase == FaseUI.PENDENTE_RECONSTRUCT and self.pendente_recon:
            self._cancel_reconstruir()

    def _on_back(self) -> None:
        """Sai do aviso e devolve o passo do wizard / ACEPT do workspace."""
        if self.fase == FaseUI.BURN:
            self._falar(D.MSG_BURN, mostrar_decisao=True)
            return
        # Sem eng pronto, Mask é o único sítio onde o wizard / ACEPT funciona
        if self.modo == ModoUI.REDACTOR and not self._eng_pronto():
            self.modo = ModoUI.MASK
            self._aplicar_chrome_modo()
        self._fala_mask_atual()

    def _continuar_anterior(self) -> None:
        pasta = self._pasta_anterior
        if not pasta:
            self.fase = FaseUI.WIZARD_NOME
            self._falar(D.MSG_WELCOME_NAME)
            return
        sess = self.life.reabrir_existente(pasta)
        self._pasta_anterior = None
        if sess:
            self.fase = FaseUI.PRONTO
            if self.modo == ModoUI.REDACTOR:
                self._falar(D.MSG_WELCOME_REDACTOR)
            else:
                self._falar(D.MSG_RETAINED_REOPEN)
        else:
            self.life.queimar_anterior_e_limpar()
            self.fase = FaseUI.WIZARD_NOME
            self._falar(D.MSG_WELCOME_NAME)

    def _queimar_anterior_novo(self) -> None:
        self.life.queimar_anterior_e_limpar()
        self._pasta_anterior = None
        self.fase = FaseUI.WIZARD_NOME
        self._falar(D.MSG_WELCOME_NAME)

    def _feedback_past_click(self) -> None:
        """Micro-animação no clique: pulso de opacidade (sem glow)."""
        if self._past_anim is not None:
            self._past_anim.stop()
        anim = QPropertyAnimation(self._past_opacidade, b"opacity", self)
        anim.setDuration(180)
        anim.setStartValue(1.0)
        anim.setKeyValueAt(0.35, 0.55)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._past_anim = anim
        anim.start()

    def _on_past_input(self) -> None:
        self._feedback_past_click()
        if self.modo == ModoUI.REDACTOR:
            self._on_past_report()
            return
        if self.fase == FaseUI.BURN:
            self._falar(D.MSG_BURN, mostrar_decisao=True)
            return
        # PAST INPUT livre quantas vezes quiser após o eng pronto
        # (também com rodada pendente — a nova substitui a anterior).
        if self.fase not in (FaseUI.PRONTO, FaseUI.PENDENTE_SANITIZE):
            self._aviso_e_voltar(D.MSG_SETUP_THEN_PAST_INPUT)
            return
        if not self.life.sessao:
            self._falar(D.MSG_NEED_ENGAGEMENT)
            return
        try:
            bruto = pyperclip.paste() or ""
        except Exception:
            bruto = ""
        if not bruto.strip():
            self._falar(D.MSG_CLIPBOARD_EMPTY)
            return

        eng = self._eng()
        if not eng:
            self._falar(D.MSG_NEED_ENGAGEMENT)
            return

        # Nova cola com pendente aberto → descarta rascunho da rodada anterior
        if self.fase == FaseUI.PENDENTE_SANITIZE and self.pendente:
            if self.pendente.teve_sensivel:
                self.sanitizer.descartar_rodada(
                    self.life.sessao.repo, self.pendente
                )
            self.pendente = None

        # Scan no clipboard → uma passagem do Racoon pensando
        self.avatar.pensar()

        resultado = self.sanitizer.sanitizar(
            bruto,
            self.life.sessao.repo,
            self.life.sessao.engagement_id,
            eng,
            persistir_rascunho=True,
        )
        self.pendente = resultado
        self.fase = FaseUI.PENDENTE_SANITIZE

        if not resultado.teve_sensivel:
            self._falar(D.MSG_NO_SENSITIVE, mostrar_decisao=True)
            return
        self._falar(D.formatar_resumo(resultado.resumo), mostrar_decisao=True)

    def _tratar_calibracao_pendente(self, texto: str) -> None:
        """allowed=/blocked= durante o preview — recalibra e regenera o resumo."""
        if not texto or not self.pendente or not self.life.sessao:
            self._falar("Decide with ACEPT or CANCEL, or type allowed=/blocked=.")
            return

        pedido = interpretar(texto)
        if pedido.intencao in (Intencao.RECUSAR_SCAN, Intencao.MUITO_LONGO):
            self._falar(pedido.mensagem_erro, mostrar_decisao=True)
            return

        if pedido.intencao not in (
            Intencao.ALLOWED_FEEDBACK,
            Intencao.BLOCKED_FEEDBACK,
        ):
            self._falar(
                D.MSG_CALIBRATION
                + "\nOr press ACEPT / CANCEL.",
                mostrar_decisao=True,
            )
            return

        # Descarta rascunho da rodada atual antes de recalcular
        if self.pendente.teve_sensivel:
            self.sanitizer.descartar_rodada(
                self.life.sessao.repo, self.pendente
            )

        original = self.pendente.texto_original
        nota = ""

        if pedido.intencao == Intencao.ALLOWED_FEEDBACK and pedido.termos:
            add = learn.adicionar_allow(pedido.termos)
            nota = (
                "Allowed: "
                + (", ".join(add) if add else "(already listed)")
            )
        elif pedido.intencao == Intencao.BLOCKED_FEEDBACK and pedido.termos:
            itens = [classificar_blocked(t) for t in pedido.termos]
            aplicar_itens_blocklist(
                self.life.sessao.repo,
                self.life.sessao.engagement_id,
                itens,
            )
            nota = "Blocked (will mask): " + ", ".join(
                f"{t}={v}" for t, v in itens
            )

        eng = self._eng()
        if not eng:
            self._falar(D.MSG_NEED_ENGAGEMENT)
            return

        self.avatar.pensar()
        resultado = self.sanitizer.sanitizar(
            original,
            self.life.sessao.repo,
            self.life.sessao.engagement_id,
            eng,
            persistir_rascunho=True,
        )
        self.pendente = resultado
        self.fase = FaseUI.PENDENTE_SANITIZE

        if not resultado.teve_sensivel:
            self._falar(
                nota + "\n\n" + D.MSG_NO_SENSITIVE,
                mostrar_decisao=True,
            )
            return
        self._falar(
            nota + "\n\n" + D.formatar_resumo(resultado.resumo),
            mostrar_decisao=True,
        )

    # ------------------------------------------------------------------
    # Sanitize
    # ------------------------------------------------------------------

    def _acept_sanitize(self) -> None:
        assert self.pendente and self.life.sessao
        r = self.pendente
        if r.teve_sensivel:
            self.sanitizer.confirmar_rodada(self.life.sessao.repo, r)
            self.life.sessao.repo.registrar_log(
                self.life.sessao.engagement_id,
                "sanitize",
                len(r.resumo),
            )
            texto = r.texto_sanitizado
        else:
            texto = r.texto_original
        try:
            pyperclip.copy(texto)
        except Exception:
            self._falar("Could not write clipboard, but round was accepted.")
            self.pendente = None
            self.fase = FaseUI.PRONTO
            return
        self.pendente = None
        self.fase = FaseUI.PRONTO
        self._falar(D.MSG_COPIED)

    def _cancel_sanitize(self) -> None:
        assert self.pendente and self.life.sessao
        if self.pendente.teve_sensivel:
            self.sanitizer.descartar_rodada(
                self.life.sessao.repo, self.pendente
            )
        self.pendente = None
        self.fase = FaseUI.PRONTO
        self._falar(D.MSG_CANCELLED)

    def _on_past_report(self) -> None:
        """Clipboard de relatório → preview invertido; ACEPT copia o real."""
        if not self._eng_pronto():
            self._aviso_e_voltar(D.MSG_REDACTOR_SEM_ENG)
            return
        if self.fase not in (
            FaseUI.PRONTO,
            FaseUI.PENDENTE_SANITIZE,
            FaseUI.PENDENTE_RECONSTRUCT,
        ):
            self._aviso_e_voltar(D.MSG_SETUP_THEN_PAST_REPORT)
            return
        if not self.life.sessao:
            self._aviso_e_voltar(D.MSG_REDACTOR_SEM_ENG)
            return
        try:
            bruto = pyperclip.paste() or ""
        except Exception:
            bruto = ""
        if not bruto.strip():
            self._falar(D.MSG_CLIPBOARD_EMPTY_REPORT)
            return

        if parece_scan_cru(bruto):
            self._descartar_pendentes()
            self._falar(D.MSG_REDACTOR_SCAN_CRU)
            return

        self._descartar_pendentes()
        self.avatar.pensar()
        resultado = reconstruir_relatorio(
            bruto,
            self.life.sessao.repo,
            self.life.sessao.engagement_id,
        )
        if not resultado.teve_troca and not resultado.nao_mapeados:
            self._falar(D.MSG_REDACTOR_SEM_PLACEHOLDER)
            return

        self.pendente_recon = resultado
        self.fase = FaseUI.PENDENTE_RECONSTRUCT
        self._falar(
            D.formatar_resumo_reconstrucao(
                resultado.resumo, resultado.nao_mapeados
            ),
            mostrar_decisao=True,
        )

    def _acept_reconstruir(self) -> None:
        assert self.pendente_recon and self.life.sessao
        r = self.pendente_recon
        if not r.teve_troca:
            self.pendente_recon = None
            self.fase = FaseUI.PRONTO
            self._falar(D.MSG_REDACTOR_SEM_PLACEHOLDER)
            return
        try:
            pyperclip.copy(r.texto_reconstruido)
        except Exception:
            self._falar("Could not write clipboard. Round discarded.")
            self.pendente_recon = None
            self.fase = FaseUI.PRONTO
            return
        self.life.sessao.repo.registrar_log(
            self.life.sessao.engagement_id,
            "reconstruct",
            len(r.resumo),
        )
        self.pendente_recon = None
        self.fase = FaseUI.PRONTO
        self._falar(D.MSG_COPIED_REPORT)

    def _cancel_reconstruir(self) -> None:
        self.pendente_recon = None
        self.fase = FaseUI.PRONTO
        self._falar(D.MSG_CANCELLED)

    # ------------------------------------------------------------------
    # Wizard / questions / burn
    # ------------------------------------------------------------------

    def _tratar_wizard_nome(self, texto: str) -> None:
        if not texto:
            self._falar(D.MSG_WELCOME_NAME)
            return
        pedido = interpretar(texto)
        if pedido.intencao in (Intencao.RECUSAR_SCAN, Intencao.MUITO_LONGO):
            self._aviso_e_voltar(pedido.mensagem_erro)
            return
        self.life.abrir_novo(texto)
        self.fase = FaseUI.WIZARD_ITENS
        self._falar(D.MSG_CONFIDENTIAL_FORMAT)

    def _tratar_wizard_itens(self, texto: str) -> None:
        if not self.life.sessao:
            self.fase = FaseUI.WIZARD_NOME
            self._falar(D.MSG_WELCOME_NAME)
            return
        if texto.lower() in {"done", "skip", "pronto", "listo"}:
            self.fase = FaseUI.PRONTO
            self._falar(D.MSG_READY)
            return

        pedido = interpretar(texto)
        if pedido.intencao in (Intencao.RECUSAR_SCAN, Intencao.MUITO_LONGO):
            self._aviso_e_voltar(pedido.mensagem_erro)
            return
        if pedido.intencao == Intencao.ITEM_CONFIDENCIAL and pedido.itens:
            msg = aplicar_itens_blocklist(
                self.life.sessao.repo,
                self.life.sessao.engagement_id,
                pedido.itens,
            )
            self.fase = FaseUI.PRONTO
            self._falar(msg + "\n\n" + D.MSG_READY)
            return
        self._aviso_e_voltar(D.MSG_FORMAT_HINT)

    def _tratar_questions(self, texto: str) -> None:
        if not texto:
            return
        if not self.life.sessao:
            self._falar(D.MSG_NEED_ENGAGEMENT)
            return

        # Pergunta no box → mesma animação (uma passagem), depois pausa no normal
        self.avatar.pensar()

        if self.modo == ModoUI.REDACTOR:
            self._tratar_questions_redactor(texto)
            return

        pedido = interpretar(texto)
        if pedido.intencao in (Intencao.RECUSAR_SCAN, Intencao.MUITO_LONGO):
            self._falar(pedido.mensagem_erro)
            return
        if pedido.intencao == Intencao.ALLOWED_FEEDBACK and pedido.termos:
            add = learn.adicionar_allow(pedido.termos)
            self._falar(
                "Allowed: "
                + (", ".join(add) if add else "(already listed)")
            )
            return
        if pedido.intencao == Intencao.BLOCKED_FEEDBACK and pedido.termos:
            itens = [classificar_blocked(t) for t in pedido.termos]
            msg = aplicar_itens_blocklist(
                self.life.sessao.repo,
                self.life.sessao.engagement_id,
                itens,
            )
            self._falar(msg)
            return
        if pedido.intencao == Intencao.ITEM_CONFIDENCIAL and pedido.itens:
            msg = aplicar_itens_blocklist(
                self.life.sessao.repo,
                self.life.sessao.engagement_id,
                pedido.itens,
            )
            self._falar(msg)
            return
        if pedido.intencao == Intencao.LOOKUP:
            self._falar(
                executar_lookup(
                    self.life.sessao.repo,
                    self.life.sessao.engagement_id,
                    pedido.placeholder,
                )
            )
            return
        if pedido.intencao == Intencao.REVEAL_TEXTO:
            self._falar(
                executar_reveal(
                    self.life.sessao.repo,
                    self.life.sessao.engagement_id,
                    pedido.texto,
                )
            )
            return
        if pedido.intencao == Intencao.REPLACE_MD:
            self._falar(
                executar_replace_md(
                    self.life.sessao.repo,
                    self.life.sessao.engagement_id,
                    pedido.caminho,
                )
            )
            return
        self._falar(
            "Commands: ip=/host=/…, allowed=/blocked=, "
            "lookup PLACEHOLDER, cmd <command with TARGET_*>, "
            "replace file.md — or PAST INPUT."
        )

    def _tratar_questions_redactor(self, texto: str) -> None:
        """Redactor: reconstruct via PAST REPORT. Questions só lookup curto / recusas."""
        if not self._eng_pronto():
            self._aviso_e_voltar(D.MSG_REDACTOR_SEM_ENG)
            return
        if texto_longo_para_questions(texto):
            self._falar(D.MSG_QUESTIONS_USE_PAST_REPORT)
            return
        if parece_pedido_llm(texto):
            self._falar(D.MSG_REDACTOR_NO_LLM)
            return
        pedido = interpretar(texto)
        if pedido.intencao == Intencao.LOOKUP:
            self._falar(
                executar_lookup(
                    self.life.sessao.repo,
                    self.life.sessao.engagement_id,
                    pedido.placeholder,
                )
            )
            return
        if pedido.intencao == Intencao.REPLACE_MD:
            self._falar(
                executar_replace_md(
                    self.life.sessao.repo,
                    self.life.sessao.engagement_id,
                    pedido.caminho,
                )
            )
            return
        if pedido.intencao == Intencao.REVEAL_TEXTO:
            self._falar(D.MSG_QUESTIONS_USE_PAST_REPORT)
            return
        if pedido.intencao in (Intencao.RECUSAR_SCAN, Intencao.MUITO_LONGO):
            self._falar(D.MSG_QUESTIONS_USE_PAST_REPORT)
            return
        self._falar(D.MSG_REDACTOR_NO_LLM)

    def _tratar_burn_texto(self, texto: str) -> None:
        t = texto.strip().upper()
        if t in {"YES", "Y"}:
            self._burn_yes()
        elif t in {"NO", "N"}:
            self._burn_no()
        else:
            self._falar(D.MSG_BURN, mostrar_decisao=True)

    def _burn_yes(self) -> None:
        self.life.burn_e_fechar()
        self.fase = FaseUI.BURN
        self.close()

    def _burn_no(self) -> None:
        self._falar(D.MSG_BURN_NO_WARN)
        self.life.manter_e_fechar()
        self.fase = FaseUI.BURN
        self.close()


def construir_app() -> RacoonWindow:
    return RacoonWindow()
