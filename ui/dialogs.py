# ui/dialogs.py
# Cômodo: textos fixos do Racoon (wizard, avisos, burn) em English.
# Por quê: UI fala inglês; lógica de fluxo fica em window.py.

MSG_WELCOME_NAME = (
    "Hey. I'm Racoon-Mask — local confidentiality filter.\n"
    "What is the workspace / engagement name?"
)

MSG_CONFIDENTIAL_FORMAT = (
    "Add confidential items:\n"
    "  ip=…\n"
    "  host=…\n"
    "  domain=…\n"
    "  name=…\n"
    "  email=…\n\n"
    "Example: name=jorge, ana, pedro\n"
    "         email=ana@acme.corp, sec@acme.corp\n"
    "Type 'done' to leave blank."
)

MSG_READY = "Ready to start — paste your first input to mask when you want."

MSG_NO_SENSITIVE = (
    "No sensitive data found. Safe to share.\n"
    "Missed something?  blocked=word\n"
)

MSG_COPIED = (
    "Copied to clipboard.\n\n"
    "Need the real values back?\n"
    "  paste cmd with TARGET_*/PERSON_* → fills real data\n"
    "  lookup PLACEHOLDER → show one real value\n"
)

MSG_CANCELLED = "Round discarded. Nothing copied."

MSG_CLIPBOARD_EMPTY = "Clipboard is empty. Copy scan output first, then PAST INPUT."

MSG_NEED_ENGAGEMENT = "No active engagement. Tell me the workspace name to begin."

MSG_OLD_WORKSPACE = (
    "Found a previous workspace: {nome}\n\n"
    "ACEPT = continue with it\n"
    "CANCEL = burn it and start a new one"
)

MSG_BURN = (
    "Burn database?\n"
    "Strongly recommended: YES — avoid retaining client data.\n\n"
    "YES → deletes workspace and quits.\n"
    "NO → keeps data for another day; you stay responsible."
)

MSG_BURN_NO_WARN = (
    "Kept. Client data remains on disk. Be careful.\n"
    "Closing now."
)

MSG_RETAINED_REOPEN = (
    "Workspace restored. Client mappings are on disk — burn when you finish."
)

MSG_CALIBRATION = (
    "Wrong mask or missed sensitive? Type:\n"
    "  allowed=word   → do not mask\n"
    "  blocked=word   → always mask\n"
)

MSG_FORMAT_HINT = (
    "Could not read that. Use: ip=…  host=…  domain=…  name=…  email=…\n"
    "Or type 'done' to leave blank."
)

FMT_RESUMO_LINHA = "{real} → {placeholder} ({times}×)"

# Larguras do preview alinhado (mono no balão — denso, sem “um por página”)
_W_TIPO = 7
_W_BEFORE = 20
_W_AFTER = 16

_ORDEM_TIPO = {
    "EMAIL": 0,
    "IP": 1,
    "HOST": 2,
    "DOMAIN": 3,
    "USER": 4,
    "PASSWORD": 5,
    "ORG": 6,
    "PERSON": 7,
    "APIKEY": 8,
}


def _corta(texto: str, largura: int) -> str:
    t = (texto or "").replace("\n", " ").strip()
    if len(t) <= largura:
        return t
    return t[: max(0, largura - 1)] + "…"


def formatar_resumo(resumo: list[dict]) -> str:
    if not resumo:
        return MSG_NO_SENSITIVE

    ordenado = sorted(
        resumo,
        key=lambda r: (
            _ORDEM_TIPO.get(str(r.get("type", "")).upper(), 99),
            str(r.get("real", "")),
        ),
    )

    cab = (
        f"{'type':<{_W_TIPO}} "
        f"{'before':<{_W_BEFORE}} "
        f"{'after':<{_W_AFTER}} "
        f"{'times':>5}"
    )
    sep = "─" * len(cab)
    linhas = [cab, sep]
    for r in ordenado:
        tipo = _corta(str(r.get("type", "?")).lower(), _W_TIPO)
        before = _corta(str(r.get("real", "")), _W_BEFORE)
        after = _corta(str(r.get("placeholder", "")), _W_AFTER)
        n = int(r.get("times", 0) or 0)
        linhas.append(
            f"{tipo:<{_W_TIPO}} {before:<{_W_BEFORE}} {after:<{_W_AFTER}} {n:>5}"
        )

    return (
        "Sanitization preview:\n"
        + "\n".join(linhas)
        + "\n\n"
        + MSG_CALIBRATION
        + "\nACEPT to copy / CANCEL to discard."
    )


def msg_old_workspace(nome: str) -> str:
    return MSG_OLD_WORKSPACE.format(nome=nome or "(unknown)")
