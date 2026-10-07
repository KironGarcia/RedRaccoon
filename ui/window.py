# ui/window.py
# Cômodo: janela compacta + eventos (única orquestração da UI).
# Por quê: UI dispara; core/db/session fazem o trabalho pesado.
# Stack UI: PySide6 (Flet exigia libmpv incompatível neste host Kali).

from __future__ import annotations

from enum import Enum, auto
from pathlib import Path
from typing import Any

import pyperclip
from PySide6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPoint,
    QPropertyAnimation,
    Qt,
)
from PySide6.QtGui import (
    QFontMetrics,
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
        col.setContentsMargins(12, 0, 8, 0)
        col.setSpacing(4)
        outer.addLayout(col, 1)
        self._col = col

        # Avatar fora da coluna que encolhe: ACEPT/YES não sobem o MASK.
        miolo = QHBoxLayout()
        miolo.setContentsMargins(0, 0, 0, 0)
        miolo.setSpacing(4)
        col.addLayout(miolo, 1)
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
        balao_row.addSpacing(T.MARGEM_BALAO_DIR)

        miolo.addLayout(col_avatar, 0)
        miolo.setAlignment(col_avatar, Qt.AlignmentFlag.AlignTop)
        direita = QVBoxLayout()
        direita.setContentsMargins(0, 0, 0, 0)
        direita.setSpacing(4)
        direita.addLayout(balao_row, 1)
        miolo.addLayout(direita, 1)
        self._direita = direita

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
        # Fora do layout: o vão é de 2 mm e o texto não pode ser cortado.
        for botao in (self.btn_acept, self.btn_cancel, self.btn_back):
            botao.setParent(self.centralWidget())
        # Faixa sob o balão, não sob o raccoon. A largura segue o balão.
        acoes.setContentsMargins(T.CAUDA_LARGURA, 0, T.MARGEM_BALAO_DIR, 0)
        acoes.setAlignment(Qt.AlignmentFlag.AlignBottom)
        self._acoes_bar = acoes_bar
        direita.addWidget(acoes_bar, 0)
        self._mostrar_decisao(False)

        barra = QFrame()
        barra.setObjectName("barra")
        barra_lay = QHBoxLayout(barra)
        self._barra_lay = barra_lay
        barra_lay.setContentsMargins(6, 12, 6, 0)
        barra_lay.setSpacing(6)

        self.txt_questions = QLineEdit()
        self.txt_questions.setObjectName("questions")
        self.txt_questions.setPlaceholderText(T.PLACEHOLDER_QUESTIONS)
        self.txt_questions.setMaxLength(T.LIMITE_QUESTIONS)
        self.txt_questions.setFixedHeight(T.ALTURA_CAMPO)
        self.txt_questions.returnPressed.connect(self._on_enviar)

        self.btn_send = BotaoEnviar(T.BARRA_CTRL_ALTURA)
        self.btn_send.clicked.connect(self._on_enviar)

        self.btn_past = QPushButton("Mask sensitive input")
        self.btn_past.setObjectName("past")
        self.btn_past.setFixedHeight(T.BARRA_CTRL_ALTURA)
        self.btn_past.setMinimumWidth(0)
        self.btn_past.setMaximumWidth(0)
        self.btn_past.setFont(fonte_past(13))
        self.btn_past.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_past.setToolTip("Mask clipboard — scan and sensitive output")
        self.btn_past.clicked.connect(self._on_past_input)
        self._past_opacidade = QGraphicsOpacityEffect(self.btn_past)
        self._past_opacidade.setOpacity(0.0)
        self.btn_past.setGraphicsEffect(self._past_opacidade)
        self.btn_past.setVisible(False)

        self.btn_unmask = QPushButton("Unmask model output")
        self.btn_unmask.setObjectName("unmask")
        self.btn_unmask.setFixedHeight(T.BARRA_CTRL_ALTURA)
        self.btn_unmask.setMinimumWidth(0)
        self.btn_unmask.setMaximumWidth(0)
        self.btn_unmask.setFont(fonte_past(13))
        self.btn_unmask.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_unmask.setToolTip(
            "Unmask clipboard — model reply back to real values"
        )
        self.btn_unmask.clicked.connect(self._on_unmask)
        self._unmask_opacidade = QGraphicsOpacityEffect(self.btn_unmask)
        self._unmask_opacidade.setOpacity(0.0)
        self.btn_unmask.setGraphicsEffect(self._unmask_opacidade)
        self.btn_unmask.setVisible(False)

        self._questions_opacidade = QGraphicsOpacityEffect(self.txt_questions)
        self._questions_opacidade.setOpacity(1.0)
        self.txt_questions.setGraphicsEffect(self._questions_opacidade)
        self.txt_questions.setMinimumWidth(0)
        self._send_opacidade = QGraphicsOpacityEffect(self.btn_send)
        self._send_opacidade.setOpacity(1.0)
        self.btn_send.setGraphicsEffect(self._send_opacidade)

        self._past_anim: QPropertyAnimation | None = None
        self._unmask_anim: QPropertyAnimation | None = None
        self._barra_operacao = False
        self._barra_grupo: QParallelAnimationGroup | None = None
        self._mask_grupo: QParallelAnimationGroup | None = None
        self._barra_geracao = 0
        self._mask_geracao = 0

        # Campo esticado no setup; Enter fica ao lado. Botões nascem com largura 0.
        barra_lay.addWidget(
            self.txt_questions, T.QUESTIONS_STRETCH, Qt.AlignmentFlag.AlignVCenter
        )
        barra_lay.addWidget(self.btn_send, 0, Qt.AlignmentFlag.AlignVCenter)
        barra_lay.addWidget(
            self.btn_past, T.PAST_STRETCH, Qt.AlignmentFlag.AlignVCenter
        )
        self.entre_botoes = QWidget()
        self.entre_botoes.setMinimumWidth(0)
        self.entre_botoes.setMaximumWidth(0)
        barra_lay.addWidget(self.entre_botoes, 0, Qt.AlignmentFlag.AlignVCenter)
        barra_lay.addWidget(
            self.btn_unmask, T.PAST_STRETCH, Qt.AlignmentFlag.AlignVCenter
        )
        col.addWidget(barra)
        # Setup cola na base (2 mm). Com os botões, a folga volta a ser maior.
        self._folga_baixo = QWidget()
        self._folga_baixo.setFixedHeight(T.FOLGA_SETUP)
        outer.addWidget(self._folga_baixo)

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
        self._sincronizar_barra()

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
        else:
            self.btn_acept.setVisible(visivel)
            self.btn_cancel.setVisible(visivel)
        self._decisao_visivel = visivel or mostrar_voltar
        self._aplicar_faixa()

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
        self._posicionar_decisao()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._posicionar_decisao()

    def _medida_opcao(self, botao: QPushButton) -> tuple[int, int]:
        """Largura pelo texto. sizeHint inchava e empilhava ACEPT em cima de CANCEL."""
        fonte = QFontMetrics(botao.font())
        return fonte.horizontalAdvance(botao.text()) + 28, fonte.height() + 8

    def _posicionar_decisao(self) -> None:
        """YES/ACEPT no vão entre o balão e os botões, sem mudar o tamanho deles."""
        if not getattr(self, "_decisao_visivel", False):
            return
        root = self.centralWidget()
        if root is None or not hasattr(self, "lbl_balao"):
            return
        bal_b = self.lbl_balao.mapTo(root, QPoint(0, self.lbl_balao.height())).y()
        ancora = self.btn_past if getattr(self, "_barra_operacao", False) else self.txt_questions
        btn_t = ancora.mapTo(root, QPoint(0, 0)).y()
        meio = (bal_b + btn_t) // 2
        # Não usar isVisible(): no boot a janela ainda não abriu e a lista saía vazia.
        if self.btn_back.isVisible() and not self.btn_acept.isVisible():
            visiveis = [self.btn_back]
        elif self._decisao_visivel:
            visiveis = [self.btn_acept, self.btn_cancel]
        else:
            return
        medidas = [self._medida_opcao(b) for b in visiveis]
        total = sum(w for w, _ in medidas) + 10 * (len(medidas) - 1)
        bal_r = self.lbl_balao.mapTo(root, QPoint(self.lbl_balao.width(), 0)).x()
        x = max(0, bal_r - total - 10)
        for b, (wdt, h) in zip(visiveis, medidas):
            # Dentro da faixa escura, sem montar um no outro nem no balão.
            y = min(meio - h // 2, btn_t - h - 2)
            y = max(y, bal_b + 2)
            b.setFixedSize(wdt, h)
            b.setGeometry(x, y, wdt, h)
            b.raise_()
            x += wdt + 10

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
        """Mask mostra os dois botões; Redactor só o Unmask."""
        mask = self.modo == ModoUI.MASK
        self.btn_mask.setChecked(mask)
        self.btn_redactor.setChecked(not mask)
        self.btn_past.setText("Mask sensitive input")
        self.btn_past.setToolTip("Mask clipboard — scan and sensitive output")
        self.btn_unmask.setText("Unmask model output")
        self.btn_unmask.setToolTip(
            "Unmask clipboard — model reply back to real values"
        )
        if self._barra_operacao:
            self._animar_so_mask()

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

    def _aplicar_faixa(self) -> None:
        """ACEPT/YES ocupam um vão já aberto sob o balão. O raccoon não sobe."""
        if not hasattr(self, "_acoes_bar"):
            return
        aberta = getattr(self, "_barra_operacao", False) or getattr(
            self, "_decisao_visivel", False
        )
        self._acoes_bar.setVisible(True)
        # Botões: 2 mm. Tela inicial: mais 3 mm para ACEPT/CANCEL não montarem na barra.
        if not aberta:
            altura_faixa = 0
        elif getattr(self, "_barra_operacao", False):
            # 2 mm a menos de balão, mais o que os botões descem: o YES cabe no meio.
            altura_faixa = 32
        else:
            altura_faixa = 20
        self._acoes_bar.setFixedHeight(altura_faixa)
        if hasattr(self, "_direita") and hasattr(self, "_col"):
            self._direita.setSpacing(0 if aberta else 4)
            self._col.setSpacing(0 if aberta else 4)
        self._posicionar_decisao()

    def _fonte_botoes(self) -> None:
        """Maior fonte que cabe nos dois rótulos, com 1 mm longe da borda."""
        texto = "Unmask model output"
        folga = 4
        largo = max(self.btn_past.width(), self.btn_unmask.width())
        if largo < 80:
            return
        # Margem lateral do estilo + padding + borda + 1 mm de cada lado.
        util_w = largo - 20 - 16 - 2 - (folga * 2)
        util_h = T.BARRA_CTRL_ALTURA - (folga * 2)
        escolhida = 13
        for px in range(util_h, 12, -1):
            fonte = fonte_past(12)
            fonte.setPixelSize(px)
            caixa = QFontMetrics(fonte).boundingRect(texto)
            if caixa.width() <= util_w and caixa.height() <= util_h:
                escolhida = px
                break
        # Pedido fechado: 19 px. O resto da janela não muda.
        escolhida = 19
        fonte = fonte_past(12)
        fonte.setPixelSize(escolhida)
        self.btn_past.setFont(fonte)
        self.btn_unmask.setFont(fonte)

    def _margem_botoes(self, operar: bool) -> None:
        """Área dos botões na largura do balão. O campo de setup continua largo."""
        if not hasattr(self, "_barra_lay"):
            return
        topo = 0 if getattr(self, "_decisao_visivel", False) or operar else 12
        if operar:
            esquerda = T.AVATAR_TAM + 4 + T.CAUDA_LARGURA
            self._barra_lay.setContentsMargins(esquerda, topo, T.MARGEM_BALAO_DIR, 0)
        else:
            self._barra_lay.setContentsMargins(6, topo, 6, 0)

    def _sincronizar_barra(self) -> None:
        """Setup = campo. Pronto = botões. Burn não mexe na barra."""
        if self.fase == FaseUI.BURN:
            return
        operar = self.fase in (
            FaseUI.PRONTO,
            FaseUI.PENDENTE_SANITIZE,
            FaseUI.PENDENTE_RECONSTRUCT,
        )
        if operar == self._barra_operacao:
            return
        self._barra_operacao = operar
        self._animar_barra(operar)

    def _largura_util_barra(self) -> int:
        barra = self.txt_questions.parentWidget()
        lay = barra.layout()
        if lay is None:
            return max(80, barra.width())
        m = lay.contentsMargins()
        return max(80, barra.width() - m.left() - m.right())

    def _animar_barra(self, operar: bool) -> None:
        """Campo e Enter somem enquanto os botões crescem — sem corte seco."""
        self._barra_geracao += 1
        geracao = self._barra_geracao
        if self._barra_grupo is not None:
            antigo = self._barra_grupo
            self._barra_grupo = None
            antigo.blockSignals(True)
            antigo.stop()
            antigo.deleteLater()

        self._margem_botoes(operar)
        self._aplicar_faixa()
        if operar:
            self.txt_questions.setVisible(True)
            self.btn_send.setVisible(True)
            self.btn_unmask.setVisible(True)
            self.btn_past.setVisible(self.modo == ModoUI.MASK)
        else:
            self.txt_questions.setVisible(True)
            self.btn_send.setVisible(True)
            self.txt_questions.setMaximumWidth(0)
            self._questions_opacidade.setOpacity(0.0)
            self.btn_send.setMaximumWidth(0)
            self._send_opacidade.setOpacity(0.0)

        grupo = QParallelAnimationGroup(self)
        duracao = 280
        curva = QEasingCurve.Type.InOutCubic

        def largura(widget: QWidget, destino: int) -> None:
            atual = widget.maximumWidth()
            if atual >= 16777215:
                atual = max(widget.width(), 0)
            anim = QPropertyAnimation(widget, b"maximumWidth", grupo)
            anim.setDuration(duracao)
            anim.setStartValue(atual)
            anim.setEndValue(destino)
            anim.setEasingCurve(curva)
            grupo.addAnimation(anim)

        def altura(widget: QWidget, destino: int) -> None:
            for prop in (b"minimumHeight", b"maximumHeight"):
                anim = QPropertyAnimation(widget, prop, grupo)
                anim.setDuration(duracao)
                anim.setStartValue(widget.height())
                anim.setEndValue(destino)
                anim.setEasingCurve(curva)
                grupo.addAnimation(anim)

        def opacidade(efeito: QGraphicsOpacityEffect, destino: float) -> None:
            anim = QPropertyAnimation(efeito, b"opacity", grupo)
            anim.setDuration(duracao)
            anim.setStartValue(efeito.opacity())
            anim.setEndValue(destino)
            anim.setEasingCurve(curva)
            grupo.addAnimation(anim)

        mostrar_mask = operar and self.modo == ModoUI.MASK
        util = self._largura_util_barra()
        espaco = 6
        lay = self.txt_questions.parentWidget().layout()
        if lay is not None:
            espaco = lay.spacing()
        if operar:
            n = 2 if mostrar_mask else 1
            vão = T.ENTRE_BOTOES if mostrar_mask else 0
            alvo = max(80, (util - espaco * (n - 1) - vão) // n)
            destino_mask = alvo if mostrar_mask else 0
            destino_unmask = alvo
            destino_campo = 0
            destino_send = 0
            destino_vão = vão
        else:
            destino_mask = 0
            destino_unmask = 0
            destino_campo = max(80, util - self.btn_send._lado - espaco)
            destino_send = self.btn_send._lado
            destino_vão = 0
        opacidade(self._questions_opacidade, 0.0 if operar else 1.0)
        opacidade(self._send_opacidade, 0.0 if operar else 1.0)
        largura(self.txt_questions, destino_campo)
        largura(self.btn_send, destino_send)
        opacidade(self._past_opacidade, 1.0 if mostrar_mask else 0.0)
        largura(self.btn_past, destino_mask)
        opacidade(self._unmask_opacidade, 1.0 if operar else 0.0)
        largura(self.entre_botoes, destino_vão)
        largura(self.btn_unmask, destino_unmask)
        altura(self._folga_baixo, T.FOLGA_BOTOES if operar else T.FOLGA_SETUP)

        def _fim() -> None:
            if geracao != self._barra_geracao:
                return
            if operar:
                self.txt_questions.setVisible(False)
                self.btn_send.setVisible(False)
                self.txt_questions.setMaximumWidth(0)
                self.btn_send.setMaximumWidth(0)
                if not mostrar_mask:
                    self.btn_past.setVisible(False)
                    self.btn_past.setMaximumWidth(0)
            else:
                self.btn_past.setVisible(False)
                self.btn_unmask.setVisible(False)
                self.btn_past.setMaximumWidth(0)
                self.btn_unmask.setMaximumWidth(0)
                self.entre_botoes.setMaximumWidth(0)
                self.txt_questions.setMaximumWidth(destino_campo)
                self.btn_send.setMaximumWidth(self.btn_send._lado)
            self._folga_baixo.setFixedHeight(
                T.FOLGA_BOTOES if operar else T.FOLGA_SETUP
            )
            if operar:
                self._fonte_botoes()

        grupo.finished.connect(_fim)
        self._barra_grupo = grupo
        grupo.start()

    def _animar_so_mask(self) -> None:
        """Troca Mask/Redactor com a barra já em botões: só o botão Mask entra ou sai."""
        mostrar = self.modo == ModoUI.MASK
        self._mask_geracao += 1
        geracao = self._mask_geracao
        self.btn_past.setVisible(True)
        if self._mask_grupo is not None:
            antigo = self._mask_grupo
            self._mask_grupo = None
            antigo.blockSignals(True)
            antigo.stop()
            antigo.deleteLater()
        grupo = QParallelAnimationGroup(self)
        duracao = 220
        curva = QEasingCurve.Type.InOutCubic
        util = self._largura_util_barra()
        espaco = 6
        lay = self.txt_questions.parentWidget().layout()
        if lay is not None:
            espaco = lay.spacing()
        if mostrar:
            alvo = max(80, (util - espaco - T.ENTRE_BOTOES) // 2)
            fim_mask = alvo
            fim_unmask = alvo
            fim_vão = T.ENTRE_BOTOES
        else:
            fim_mask = 0
            fim_unmask = util
            fim_vão = 0

        def _trilho(widget: QWidget, destino: int) -> None:
            atual = widget.maximumWidth()
            if atual >= 16777215:
                atual = max(widget.width(), 0)
            anim = QPropertyAnimation(widget, b"maximumWidth", grupo)
            anim.setDuration(duracao)
            anim.setStartValue(atual)
            anim.setEndValue(destino)
            anim.setEasingCurve(curva)
            grupo.addAnimation(anim)

        _trilho(self.btn_past, fim_mask)
        _trilho(self.entre_botoes, fim_vão)
        _trilho(self.btn_unmask, fim_unmask)
        opacidade = QPropertyAnimation(self._past_opacidade, b"opacity", grupo)
        opacidade.setDuration(duracao)
        opacidade.setStartValue(self._past_opacidade.opacity())
        opacidade.setEndValue(1.0 if mostrar else 0.0)
        opacidade.setEasingCurve(curva)
        grupo.addAnimation(opacidade)

        def _fim() -> None:
            if geracao != self._mask_geracao:
                return
            if not mostrar:
                self.btn_past.setVisible(False)
                self.btn_past.setMaximumWidth(0)

        grupo.finished.connect(_fim)
        self._mask_grupo = grupo
        grupo.start()

    def _feedback_click(self, efeito: QGraphicsOpacityEffect, slot: str) -> None:
        """Micro-animação no clique: pulso de opacidade (sem glow)."""
        atual = getattr(self, slot)
        if atual is not None:
            atual.stop()
        anim = QPropertyAnimation(efeito, b"opacity", self)
        anim.setDuration(180)
        anim.setStartValue(1.0)
        anim.setKeyValueAt(0.35, 0.55)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        setattr(self, slot, anim)
        anim.start()

    def _on_past_input(self) -> None:
        self._feedback_click(self._past_opacidade, "_past_anim")
        if self.modo == ModoUI.REDACTOR:
            return
        if self.fase == FaseUI.BURN:
            self._falar(D.MSG_BURN, mostrar_decisao=True)
            return
        # PAST INPUT livre quantas vezes quiser após o eng pronto
        # (também com rodada pendente — a nova substitui a anterior).
        if self.fase not in (
            FaseUI.PRONTO,
            FaseUI.PENDENTE_SANITIZE,
            FaseUI.PENDENTE_RECONSTRUCT,
        ):
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
        self._descartar_pendentes()

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

    def _on_unmask(self) -> None:
        """Mesmo caminho do Mask: clipboard → tabela → ACEPT copia o real."""
        self._feedback_click(self._unmask_opacidade, "_unmask_anim")
        self._on_past_report()

    def _on_past_report(self) -> None:
        """Clipboard com placeholder → preview invertido; ACEPT copia o real."""
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
