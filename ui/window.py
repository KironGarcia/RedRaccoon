# ui/window.py
# Cômodo: janela compacta + eventos (única orquestração da UI).
# Por quê: UI dispara; core/db/session fazem o trabalho pesado.
# Stack UI: PySide6 (Flet exigia libmpv incompatível neste host Kali).

from __future__ import annotations

from enum import Enum, auto
from pathlib import Path
from typing import Any

import pyperclip
from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, Qt
from PySide6.QtGui import (
    QCursor,
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
    QSizeGrip,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.queries import (
    Intencao,
    aplicar_itens_blocklist,
    classificar_blocked,
    executar_lookup,
    executar_replace_md,
    executar_reveal,
    interpretar,
)
from core.sanitize import ResultadoSanitize, Sanitizer
from session import learning as learn
from session import prefs as ui_prefs
from session.lifecycle import Lifecycle
from ui import dialogs as D
from ui import theme as T
from ui.fonts import fonte_past
from ui.raccoon import AvatarRacoon, BotaoEnviar, CaudaBalao


class FaseUI(Enum):
    BOOT = auto()
    OLD_WORKSPACE = auto()
    WIZARD_NOME = auto()
    WIZARD_ITENS = auto()
    PRONTO = auto()
    PENDENTE_SANITIZE = auto()
    BURN = auto()


class RacoonWindow(QMainWindow):
    """Janela única do Racoon-Mask — móvel, redimensionável, sem always-on-top."""

    def __init__(self) -> None:
        super().__init__()
        self.life = Lifecycle()
        self.sanitizer = Sanitizer()
        self.fase = FaseUI.BOOT
        self.pendente: ResultadoSanitize | None = None
        self._pasta_anterior: Path | None = None
        self._drag_pos: QPoint | None = None
        self._resize_edges: int = 0  # bitmask EDGE_L/R/T/B
        self._resize_origin: QPoint | None = None
        self._resize_geo: QRect | None = None

        self.setWindowTitle("Racoon-Mask")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumSize(T.LARGURA_MIN, T.ALTURA_MIN)
        self.setMouseTracking(True)
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

        # Topo: só grip esquerdo — o X fica no canto (círculo azul)
        top_grips = QHBoxLayout()
        top_grips.setContentsMargins(2, 2, 2, 0)
        top_grips.setSpacing(2)
        grip_tl = QSizeGrip(root)
        grip_tl.setFixedSize(14, 14)
        top_grips.addWidget(
            grip_tl, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        top_grips.addStretch(1)
        top_grips.addSpacing(T.MARGEM_FECHAR * 2 + 20)
        outer.addLayout(top_grips)

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

        topo.addWidget(self.avatar, 0, Qt.AlignmentFlag.AlignTop)
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
        acoes.addWidget(self.btn_acept)
        acoes.addWidget(self.btn_cancel)
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

        bot_grips = QHBoxLayout()
        bot_grips.setContentsMargins(2, 0, 2, 2)
        grip_bl = QSizeGrip(root)
        grip_bl.setFixedSize(14, 14)
        grip_br = QSizeGrip(root)
        grip_br.setFixedSize(14, 14)
        bot_grips.addWidget(grip_bl, 0, Qt.AlignmentFlag.AlignLeft)
        bot_grips.addStretch(1)
        bot_grips.addWidget(grip_br, 0, Qt.AlignmentFlag.AlignRight)
        outer.addLayout(bot_grips)

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
        p = ui_prefs.carregar()
        w = int(p.get("width", T.LARGURA_JANELA))
        h = int(p.get("height", T.ALTURA_JANELA))
        w = max(T.LARGURA_MIN, w)
        h = max(T.ALTURA_MIN, h)
        self.resize(w, h)

        screen = QGuiApplication.primaryScreen()
        if "x" in p and "y" in p:
            self.move(int(p["x"]), int(p["y"]))
        elif screen:
            geo = screen.availableGeometry()
            x = geo.x() + geo.width() - w - T.MARGEM_DIREITA
            y = geo.y() + geo.height() - h - T.MARGEM_INFERIOR
            self.move(max(geo.x(), x), max(geo.y(), y))

    def _salvar_geometria(self) -> None:
        ui_prefs.salvar(
            {
                "width": self.width(),
                "height": self.height(),
                "x": self.x(),
                "y": self.y(),
            }
        )

    def _falar(self, texto: str, *, mostrar_decisao: bool = False) -> None:
        self.lbl_balao.setPlainText(texto)
        self.lbl_balao.moveCursor(QTextCursor.MoveOperation.Start)
        if mostrar_decisao and self.fase == FaseUI.BURN:
            # Fechar app: YES/NO (scan continua com ACEPT/CANCEL)
            self._mostrar_decisao(True, rotulos=("YES", "NO"))
        elif mostrar_decisao:
            self._mostrar_decisao(True, rotulos=("ACEPT", "CANCEL"))
        else:
            self._mostrar_decisao(False)

    def _mostrar_decisao(
        self, visivel: bool, *, rotulos: tuple[str, str] = ("ACEPT", "CANCEL")
    ) -> None:
        self.btn_acept.setText(rotulos[0])
        self.btn_cancel.setText(rotulos[1])
        # YES/NO (burn) um pouco maior que ACEPT/CANCEL (scan)
        if rotulos == ("YES", "NO"):
            px = T.FONTE_YES_NO
        else:
            px = T.FONTE_ACEPT_CANCEL
        for btn in (self.btn_acept, self.btn_cancel):
            f = btn.font()
            f.setPixelSize(px)
            f.setBold(False)
            btn.setFont(f)
        self.btn_acept.setVisible(visivel)
        self.btn_cancel.setVisible(visivel)

    def _limpar_input(self) -> None:
        self.txt_questions.clear()

    # ------------------------------------------------------------------
    # Bordas: cursor + resize (esqueleto inteiro, não só canto)
    # ------------------------------------------------------------------

    def _edges_em(self, pos: QPoint) -> int:
        m = T.BORDA_RESIZE
        edges = 0
        if pos.x() <= m:
            edges |= T.EDGE_L
        if pos.x() >= self.width() - m:
            edges |= T.EDGE_R
        if pos.y() <= m:
            edges |= T.EDGE_T
        if pos.y() >= self.height() - m:
            edges |= T.EDGE_B
        return edges

    def _cursor_para_edges(self, edges: int) -> Qt.CursorShape:
        left = bool(edges & T.EDGE_L)
        right = bool(edges & T.EDGE_R)
        top = bool(edges & T.EDGE_T)
        bottom = bool(edges & T.EDGE_B)
        if (top and left) or (bottom and right):
            return Qt.CursorShape.SizeFDiagCursor
        if (top and right) or (bottom and left):
            return Qt.CursorShape.SizeBDiagCursor
        if left or right:
            return Qt.CursorShape.SizeHorCursor
        if top or bottom:
            return Qt.CursorShape.SizeVerCursor
        return Qt.CursorShape.ArrowCursor

    def _widget_bloqueia_drag(self, filho: QWidget | None) -> bool:
        if filho is None:
            return False
        if isinstance(filho, (QPushButton, QLineEdit, QTextEdit, QSizeGrip)):
            return True
        nome = filho.objectName()
        return nome in {
            "acept",
            "cancel",
            "past",
            "send",
            "fechar",
            "questions",
            "balao",
        }

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        pos = event.position().toPoint()
        edges = self._edges_em(pos)
        if edges:
            self._resize_edges = edges
            self._resize_origin = event.globalPosition().toPoint()
            self._resize_geo = QRect(self.geometry())
            event.accept()
            return
        filho = self.childAt(pos)
        if self._widget_bloqueia_drag(filho):
            super().mousePressEvent(event)
            return
        self._drag_pos = (
            event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        )
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        pos = event.position().toPoint()
        if self._resize_edges and self._resize_origin and self._resize_geo:
            delta = event.globalPosition().toPoint() - self._resize_origin
            g = QRect(self._resize_geo)
            if self._resize_edges & T.EDGE_L:
                g.setLeft(g.left() + delta.x())
            if self._resize_edges & T.EDGE_R:
                g.setRight(g.right() + delta.x())
            if self._resize_edges & T.EDGE_T:
                g.setTop(g.top() + delta.y())
            if self._resize_edges & T.EDGE_B:
                g.setBottom(g.bottom() + delta.y())
            if g.width() >= T.LARGURA_MIN and g.height() >= T.ALTURA_MIN:
                self.setGeometry(g)
            event.accept()
            return
        if (
            self._drag_pos is not None
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
            return
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            edges = self._edges_em(pos)
            self.setCursor(QCursor(self._cursor_para_edges(edges)))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            if self._drag_pos is not None or self._resize_edges:
                self._salvar_geometria()
            self._drag_pos = None
            self._resize_edges = 0
            self._resize_origin = None
            self._resize_geo = None
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._posicionar_fechar()
        self._salvar_geometria()

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

    def _on_cancel(self) -> None:
        if self.fase == FaseUI.BURN:
            self._burn_no()
            return
        if self.fase == FaseUI.OLD_WORKSPACE:
            self._queimar_anterior_novo()
            return
        if self.fase == FaseUI.PENDENTE_SANITIZE and self.pendente:
            self._cancel_sanitize()

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
        # PAST INPUT livre quantas vezes quiser após o eng pronto
        # (também com rodada pendente — a nova substitui a anterior).
        if self.fase not in (FaseUI.PRONTO, FaseUI.PENDENTE_SANITIZE):
            self._falar("Finish setup first, then use PAST INPUT.")
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

    # ------------------------------------------------------------------
    # Wizard / questions / burn
    # ------------------------------------------------------------------

    def _tratar_wizard_nome(self, texto: str) -> None:
        if not texto:
            self._falar(D.MSG_WELCOME_NAME)
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
            self._falar(pedido.mensagem_erro)
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
        self._falar(D.MSG_FORMAT_HINT)

    def _tratar_questions(self, texto: str) -> None:
        if not texto:
            return
        if not self.life.sessao:
            self._falar(D.MSG_NEED_ENGAGEMENT)
            return

        # Pergunta no box → mesma animação (uma passagem), depois pausa no normal
        self.avatar.pensar()

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
            "lookup PLACEHOLDER, reveal <cmd>, replace file.md — "
            "or PAST INPUT."
        )

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
