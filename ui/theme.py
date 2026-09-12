# ui/theme.py
# Cômodo: cores e medidas do esqueleto retro/minimal (sketch).
# Por quê: pele depois; agora proporção estável e auditável.

# Máscaras de borda para resize (ints simples — Qt.Edge quebra com int() no PySide6)
EDGE_L = 1
EDGE_R = 2
EDGE_T = 4
EDGE_B = 8

LARGURA_JANELA = 600
ALTURA_JANELA = 300
LARGURA_MIN = 480
ALTURA_MIN = 260
MARGEM_DIREITA = 28
MARGEM_INFERIOR = 56
BORDA_RESIZE = 8
# Espaço à direita do balão (X no canto + respiro)
MARGEM_BALAO_DIR = 40
# X equidistante do topo e da direita (círculo azul do sketch)
MARGEM_FECHAR = 10
# Avatar (círculo vermelho do sketch)
AVATAR_TAM = 118
BALAO_ALTURA_MIN = 148
# Cauda do balão (triângulo → Racoon)
CAUDA_LARGURA = 14
CAUDA_ALTURA = 22
# Barra inferior: PAST CTA (um pouco mais curto que o sketch cheio)
QUESTIONS_STRETCH = 3
PAST_STRETCH = 2
# Faixa ACEPT/CANCEL / YES/NO
ACOES_ALTURA = 32
# ~1 mm e ~2 mm acima da base 12px (≈4 px/mm @96dpi)
FONTE_ACEPT_CANCEL = 16
FONTE_YES_NO = 20
# Altura única da barra (box / seta / PAST alinhados)
BARRA_CTRL_ALTURA = 44

COR_FUNDO = "#1a1d24"
COR_BARRA = "#12151a"
COR_BALAO = "#f2f4f7"
COR_TEXTO_BALAO = "#1a1d24"
COR_TEXTO_CLARO = "#e8eaed"
COR_MARCO = "#2a5a72"
COR_AZUL = "#3a7a96"
COR_AZUL_HOVER = "#2f6880"
COR_BORDA_INPUT = "#3a7a96"
COR_AVATAR = "#2d3340"
COR_OLHO = "#e8eaed"
COR_CINZA_BOTAO = "#94a3b8"
# ACEPT / YES — ciano mais iluminado (antes #3a7a96 apagado no fundo escuro)
COR_ACEPT = "#5ec8f0"
COR_ACEPT_HOVER = "#9ae0ff"
# CANCEL / NO — cinza claro legível
COR_CANCEL = "#d0dae6"
COR_CANCEL_HOVER = "#ffffff"

# Alinhado com core.queries.LIMITE_CHARS (lista confidencial grande)
LIMITE_QUESTIONS = 4000
PLACEHOLDER_QUESTIONS = "Enter confidential information or questions here..."
FONTE_BALAO = "DejaVu Sans Mono, Consolas, monospace"

STYLESHEET = f"""
QMainWindow {{
    background: transparent;
}}
QWidget#root {{
    background-color: {COR_FUNDO};
    border: 2px solid {COR_MARCO};
    border-radius: 14px;
}}
QTextEdit#balao {{
    background-color: {COR_BALAO};
    color: {COR_TEXTO_BALAO};
    border: none;
    border-radius: 12px;
    padding: 12px 14px 10px 12px;
    font-family: {FONTE_BALAO};
    font-size: 15px;
    font-weight: 600;
}}
QPushButton#acept {{
    background-color: transparent;
    color: {COR_ACEPT};
    border: none;
    font-weight: 400;
    font-size: {FONTE_ACEPT_CANCEL}px;
    padding: 4px 10px;
}}
QPushButton#acept:hover {{
    color: {COR_ACEPT_HOVER};
}}
QPushButton#cancel {{
    background-color: transparent;
    color: {COR_CANCEL};
    border: none;
    font-weight: 400;
    font-size: {FONTE_ACEPT_CANCEL}px;
    padding: 4px 10px;
}}
QPushButton#cancel:hover {{
    color: {COR_CANCEL_HOVER};
}}
QPushButton#past {{
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 #2f6880,
        stop:0.5 #254f63,
        stop:1 #1a3a4a
    );
    color: #e8eef2;
    border: 1px solid #3a7a96;
    border-radius: 7px;
    font-weight: 400;
    font-size: 18px;
    letter-spacing: 1px;
    padding: 0px 10px;
    min-width: 149px;
}}
QPushButton#past:hover {{
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 #3a7a96,
        stop:0.5 #2f6880,
        stop:1 #254f63
    );
    border: 1px solid #4a8fb0;
    color: #ffffff;
}}
QPushButton#past:pressed {{
    background: #1a3a4a;
    border: 1px solid #254f63;
    padding-top: 2px;
    color: #d0d8de;
}}
QPushButton#send {{
    background-color: transparent;
    color: transparent;
    border: 2px solid #2a5a72;
    border-radius: 22px;
    padding: 0px;
}}
QPushButton#send:hover {{
    background-color: rgba(42, 90, 114, 0.25);
    border: 2px solid #3a7a96;
}}
QPushButton#fechar {{
    background-color: transparent;
    color: {COR_CINZA_BOTAO};
    border: 1px solid {COR_CINZA_BOTAO};
    border-radius: 10px;
    font-size: 11px;
    font-weight: 700;
    padding: 0px;
}}
QPushButton#fechar:hover {{
    color: #fff;
    border-color: #fff;
}}
QLineEdit#questions {{
    background-color: {COR_BARRA};
    color: {COR_TEXTO_CLARO};
    border: 1px solid {COR_BORDA_INPUT};
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 13px;
    min-height: 22px;
    selection-background-color: {COR_AZUL};
}}
QFrame#barra {{
    background-color: {COR_BARRA};
    border-radius: 8px;
}}
QSizeGrip {{
    background: transparent;
    width: 14px;
    height: 14px;
}}
/* Scroll do balão — azul da app, sem setas nem bordas cinza */
QTextEdit#balao QScrollBar:vertical {{
    background: transparent;
    width: 7px;
    margin: 10px 3px 10px 0;
    border: none;
}}
QTextEdit#balao QScrollBar::handle:vertical {{
    background: {COR_AZUL};
    border: none;
    border-radius: 3px;
    min-height: 28px;
}}
QTextEdit#balao QScrollBar::handle:vertical:hover {{
    background: {COR_AZUL_HOVER};
}}
QTextEdit#balao QScrollBar::add-line:vertical,
QTextEdit#balao QScrollBar::sub-line:vertical {{
    height: 0px;
    width: 0px;
    background: none;
    border: none;
}}
QTextEdit#balao QScrollBar::add-page:vertical,
QTextEdit#balao QScrollBar::sub-page:vertical {{
    background: none;
    border: none;
}}
QScrollBar:horizontal {{
    height: 0px;
}}
"""
