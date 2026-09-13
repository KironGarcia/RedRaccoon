# ui/raccoon.py
# Cômodo: avatar do Racoon + cauda do balão de conversa.
# Por quê: normal só no boot/X; após animar, pausa no último frame; triângulo = “fala”.

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRect, QSize, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QIcon,
    QImage,
    QPaintEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    qAlpha,
)
from PySide6.QtWidgets import QPushButton, QWidget

from ui import theme as T

# Assets na pasta do projeto (não MemCodex)
_ASSETS = Path(__file__).resolve().parent.parent / "assets"
_PATH_NORMAL = _ASSETS / "racon-normal.png"
_PATH_PENSANDO = _ASSETS / "Racoon-pensando.png"
# Tamanhos típicos de taskbar / alt-tab
_ICON_LADOS = (16, 24, 32, 48, 64, 128, 256)
# Pixel quase invisível (anti-alias) não conta como desenho
_LIMIAR_ALPHA_ICONE = 8
# ~0,1 mm na barra (~1,5 % do lado do ícone; mínimo 1 px)
_MARGEM_ICONE_FRACAO = 0.015


def _bbox_objeto(img: QImage) -> QRect | None:
    """Onde o Racoon começa: primeiro pixel não-nulo em cada um dos quatro lados."""
    w, h = img.width(), img.height()
    minx, miny, maxx, maxy = w, h, -1, -1
    for y in range(h):
        for x in range(w):
            if qAlpha(img.pixel(x, y)) > _LIMIAR_ALPHA_ICONE:
                if x < minx:
                    minx = x
                if x > maxx:
                    maxx = x
                if y < miny:
                    miny = y
                if y > maxy:
                    maxy = y
    if maxx < minx:
        return None
    return QRect(minx, miny, maxx - minx + 1, maxy - miny + 1)


def _pixmap_icone_preenchido(recorte: QPixmap, lado: int) -> QPixmap:
    """Amplia o recorte do Racoon até ocupar o ícone, com filete nulo nas bordas."""
    margem = max(1, round(lado * _MARGEM_ICONE_FRACAO))
    interno = max(1, lado - 2 * margem)
    scaled = recorte.scaled(
        interno,
        interno,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    saida = QPixmap(lado, lado)
    saida.fill(Qt.GlobalColor.transparent)
    p = QPainter(saida)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    p.drawPixmap((lado - scaled.width()) // 2, (lado - scaled.height()) // 2, scaled)
    p.end()
    return saida


def icone_janela() -> QIcon:
    """Ícone da janela/taskbar: Racoon preenchido, não o PNG com padding nulo."""
    icone = QIcon()
    origem = QImage(str(_PATH_NORMAL))
    if origem.isNull():
        return icone
    caixa = _bbox_objeto(origem)
    if caixa is None:
        return icone
    recorte = QPixmap.fromImage(origem.copy(caixa))
    if recorte.isNull():
        return icone
    for lado in _ICON_LADOS:
        icone.addPixmap(_pixmap_icone_preenchido(recorte, lado))
    return icone

# Sprite horizontal: largura ÷ 340 = N frames (hoje 680×350 → 2 frames)
_LARGURA_FRAME = 340
_ALTURA_FRAME = 350
_FPS = 1
_INTERVALO_MS = 1000 // _FPS  # 1000 ms por frame


class CaudaBalao(QWidget):
    """Triângulo branco à esquerda do balão — aponta para o Racoon."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(T.CAUDA_LARGURA, T.CAUDA_ALTURA)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(T.CAUDA_LARGURA, T.CAUDA_ALTURA)

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        path = QPainterPath()
        # Ponta à esquerda (pro Racoon); base colada no balão
        path.moveTo(0, h / 2)
        path.lineTo(w, 0)
        path.lineTo(w, h)
        path.closeSubpath()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(T.COR_BALAO))
        p.drawPath(path)
        p.end()


class BotaoEnviar(QPushButton):
    """Círculo Enter: triângulo só contorno, grande e opticamente centrado."""

    def __init__(self, tamanho: int = 44, parent=None) -> None:
        super().__init__("", parent)
        self.setObjectName("send")
        self.setFixedSize(tamanho, tamanho)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Send")

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self.isDown():
            cor = QColor("#2f6880")
        elif self.underMouse():
            cor = QColor("#3a7a96")
        else:
            cor = QColor("#2a5a72")

        pen = QPen(cor)
        pen.setWidthF(2.2)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)

        # ~38% do diâmetro (−1 mm); +0.5 mm à direita do centro geométrico
        s = min(self.width(), self.height()) * 0.33
        # Largura/altura do path: base em x0, ponta em x1
        x0 = -s * 0.45
        x1 = s * 0.65
        y0 = -s * 0.55
        y1 = s * 0.55
        # Centro do bbox + meio milímetro à direita (antes era +1 mm)
        cx = self.width() / 2 - (x0 + x1) / 2 + 2
        cy = self.height() / 2 - (y0 + y1) / 2
        path = QPainterPath()
        path.moveTo(cx + x0, cy + y0)
        path.lineTo(cx + x0, cy + y1)
        path.lineTo(cx + x1, cy)
        path.closeSubpath()
        p.drawPath(path)
        p.end()

    def enterEvent(self, event) -> None:  # noqa: N802
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event) -> None:  # noqa: N802
        super().leaveEvent(event)
        self.update()


class AvatarRacoon(QWidget):
    """Racoon na UI: normal só no boot/X; scan/pergunta anima e pausa no último frame."""

    def __init__(self, tamanho: int = 72, parent=None) -> None:
        super().__init__(parent)
        self._tam = tamanho
        self.setFixedSize(QSize(tamanho, tamanho))
        self.setToolTip("Racoon-Mask")

        self._pix_normal = QPixmap(str(_PATH_NORMAL))
        self._frames_pensando = self._carregar_frames_pensando()
        self._indice = 0
        self._modo_pensando = False
        self._pix_atual = self._pix_normal

        self._timer = QTimer(self)
        self._timer.setInterval(_INTERVALO_MS)
        self._timer.timeout.connect(self._avancar_frame)

        self.estatico()

    def sizeHint(self) -> QSize:  # noqa: N802 — API Qt
        return QSize(self._tam, self._tam)

    def estatico(self) -> None:
        """Asset normal — só boot e X / saída."""
        self._timer.stop()
        self._modo_pensando = False
        self._indice = 0
        self._pix_atual = self._pix_normal
        self.update()

    def pensar(self) -> None:
        """Uma passagem do sprite @ 1 FPS; ao terminar, pausa no último frame."""
        if not self._frames_pensando:
            return
        self._modo_pensando = True
        self._indice = 0
        self._pix_atual = self._frames_pensando[0]
        self.update()
        self._timer.start()

    def _pausar_ultimo_frame(self) -> None:
        """Fim da passagem: para o timer e mantém o último frame do sprite."""
        self._timer.stop()
        self._modo_pensando = False
        ultimo = self._frames_pensando[-1]
        self._indice = len(self._frames_pensando) - 1
        self._pix_atual = ultimo
        self.update()

    def _carregar_frames_pensando(self) -> list[QPixmap]:
        folha = QPixmap(str(_PATH_PENSANDO))
        if folha.isNull():
            return []
        n = max(1, folha.width() // _LARGURA_FRAME)
        frames: list[QPixmap] = []
        for i in range(n):
            frames.append(
                folha.copy(i * _LARGURA_FRAME, 0, _LARGURA_FRAME, _ALTURA_FRAME)
            )
        return frames

    def _avancar_frame(self) -> None:
        if not self._modo_pensando or not self._frames_pensando:
            self._pausar_ultimo_frame()
            return
        proximo = self._indice + 1
        if proximo >= len(self._frames_pensando):
            self._pausar_ultimo_frame()
            return
        self._indice = proximo
        self._pix_atual = self._frames_pensando[self._indice]
        self.update()

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if self._pix_atual.isNull():
            p.end()
            return
        scaled = self._pix_atual.scaled(
            self._tam,
            self._tam,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = (self._tam - scaled.width()) // 2
        y = (self._tam - scaled.height()) // 2
        p.drawPixmap(x, y, scaled)
        p.end()


AvatarPlaceholder = AvatarRacoon
