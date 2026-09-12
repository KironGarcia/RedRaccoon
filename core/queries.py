# core/queries.py
# Cômodo: parsing determinístico do Questions box (sem LLM).
# Por quê: wizard flexível — vários tipos na mesma linha; name com vírgulas.

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Any

from core import reconstruct as recon
from core.reconstruct import RE_PLACEHOLDER

# Lista confidencial grande cabe aqui; scan continua só via PAST INPUT
LIMITE_CHARS = 4000
# No Redactor, texto longo no Questions → PAST REPORT (não cabe hallazgo aqui)
LIMITE_QUESTIONS_REDACTOR = 220
# Muitas linhas sem ip=/host=/… → trata como tool output colado por engano
LINHAS_SUSPEITAS_SCAN = 8

MSG_SCAN_NO_QUESTIONS = (
    "Looks like you tried to paste a scan into this chat box.\n"
    "That option isn't valid — please use the PAST INPUT button."
)

# Campos aceitos na lista confidencial (email= no início — contatos conhecidos do eng)
TIPOS = ("email", "ip", "host", "domain", "name", "org")

# Assinaturas fortes de scan/tool output (não confundir com lista tipada)
RE_SCAN_FORTE = re.compile(
    r"(?i)("
    r"Nmap scan report"
    r"|Starting Nmap"
    r"|PORT\s+STATE\s+SERVICE"
    r"|Host is up"
    r"|Not shown:\s+\d+\s+closed"
    r"|Interesting ports"
    r"|Service Info:"
    r"|MAC Address:"
    r"|SF-Port\d+"
    r"|enum4linux"
    r"|smbclient\s+//"
    r"|masscan"
    r"|Nikto v"
    r")"
)

# Início de um campo tipado (permite vários na mesma linha)
RE_TIPO = re.compile(
    r"(?i)(?:^|(?<=\s))(?:type\s*=\s*)?(email|ip|host|domain|name|org)\b"
)

RE_LOOKUP = re.compile(
    r"(?i)^(?:lookup|what is|resolve)\s+"
    r"([A-Z0-9_]+)\s*$"
)
RE_REPLACE = re.compile(
    r"(?i)^(?:replace|unmask)\s+(?:in\s+)?(.+\.(?:md|txt))\s*$"
)
RE_REVEAL = re.compile(r"(?is)^(?:reveal|decode|real)\s+(.+)$")
# Calibração no preview: falso positivo / fuga
RE_ALLOWED = re.compile(r"(?is)^allowed\s*=\s*(.+)$")
RE_BLOCKED = re.compile(r"(?is)^blocked\s*=\s*(.+)$")
RE_IPV4_LEVE = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
)
# Pedido de “melhorar o texto” — Redactor não é LLM
RE_PEDIDO_LLM = re.compile(
    r"(?i)\b("
    r"improve|rewrite|rephrase|polish|paraphrase|"
    r"fix this|make (?:it |this )?(?:better|shorter|longer)|"
    r"help me write|can you (?:write|edit|improve)|"
    r"how (?:can|do) i|"
    r"melhorar|reescrev|mejora(?:r)? esta"
    r")\b"
)


class Intencao(Enum):
    VAZIO = auto()
    RECUSAR_SCAN = auto()
    MUITO_LONGO = auto()
    ITEM_CONFIDENCIAL = auto()
    ALLOWED_FEEDBACK = auto()
    BLOCKED_FEEDBACK = auto()
    LOOKUP = auto()
    REVEAL_TEXTO = auto()
    REPLACE_MD = auto()
    TEXTO_LIVRE = auto()


@dataclass
class PedidoQuery:
    intencao: Intencao
    mensagem_erro: str = ""
    itens: list[tuple[str, str]] | None = None
    termos: list[str] | None = None
    placeholder: str = ""
    caminho: str = ""
    texto: str = ""


def _pedido_muito_longo(tamanho: int) -> PedidoQuery:
    return PedidoQuery(
        intencao=Intencao.MUITO_LONGO,
        mensagem_erro=(
            f"Too long ({tamanho} chars). "
            f"This box max is {LIMITE_CHARS}. "
            "Split the confidential list or use PAST INPUT for scans."
        ),
    )


def parece_scan_cru(texto: str) -> bool:
    """
    Tool output real (nmap etc.) sem placeholders.
    Relatório mascarado que ainda diz “Nmap scan report” + TARGET_* NÃO entra aqui.
    """
    bruto = texto or ""
    if RE_PLACEHOLDER.search(bruto):
        return False
    if RE_SCAN_FORTE.search(bruto):
        return True
    if bruto.count("\n") >= LINHAS_SUSPEITAS_SCAN and RE_IPV4_LEVE.search(bruto):
        return True
    return False


def parece_pedido_llm(texto: str) -> bool:
    return bool(RE_PEDIDO_LLM.search(texto or ""))


def texto_longo_para_questions(texto: str) -> bool:
    bruto = texto or ""
    if len(bruto) > LIMITE_QUESTIONS_REDACTOR:
        return True
    if bruto.count("\n") >= 3:
        return True
    return False


def validar_tamanho_e_anti_scan(texto: str) -> PedidoQuery | None:
    """
    Ordem: scan forte → lista tipada (limite alto) → multilinha suspeita → tamanho.
    Assim lista grande de ip=/host= entra; nmap colado por engano é recusado.
    """
    bruto = texto or ""
    limpo = bruto.strip()

    # 1) Parece scan de verdade → avisa e manda pro PAST INPUT
    if RE_SCAN_FORTE.search(bruto):
        return PedidoQuery(
            intencao=Intencao.RECUSAR_SCAN,
            mensagem_erro=MSG_SCAN_NO_QUESTIONS,
        )

    # 1b) Calibração allowed=/blocked= (preview) — não é scan
    if RE_ALLOWED.match(limpo) or RE_BLOCKED.match(limpo):
        if len(bruto) > LIMITE_CHARS:
            return _pedido_muito_longo(len(bruto))
        return None

    # 2) Formato de tabela confidencial: permite lista grande
    if limpo and parse_linhas_confidential(limpo):
        if len(bruto) > LIMITE_CHARS:
            return _pedido_muito_longo(len(bruto))
        return None

    # 3) Muitas linhas sem tipagem → quase certamente tool output no box errado
    if bruto.count("\n") >= LINHAS_SUSPEITAS_SCAN:
        return PedidoQuery(
            intencao=Intencao.RECUSAR_SCAN,
            mensagem_erro=MSG_SCAN_NO_QUESTIONS,
        )

    # 4) Demais comandos curtos (lookup, replace, etc.)
    if len(bruto) > LIMITE_CHARS:
        return _pedido_muito_longo(len(bruto))
    return None


def _limpar_valor_campo(bruto: str) -> str:
    v = bruto.strip()
    v = re.sub(r"^[=:\s]+", "", v)
    v = v.strip()
    if v.startswith("{") and v.endswith("}"):
        v = v[1:-1].strip()
    return v.strip(" ,")


def _partir_valores(tipo: str, bloco: str) -> list[str]:
    """
    Separa valores do campo.
    name/org: vírgula = outro nome (espaços ok dentro do nome).
    ip/host/domain: vírgula ou espaço separa itens.
    """
    bloco = _limpar_valor_campo(bloco)
    if not bloco:
        return []
    if tipo in {"name", "org", "email"} or "," in bloco:
        return [p.strip() for p in bloco.split(",") if p.strip()]
    return [p.strip() for p in bloco.split() if p.strip()]


def parse_linhas_confidential(texto: str) -> list[tuple[str, str]]:
    """
    Extrai ip/host/domain/name — um ou vários campos por linha.
    Ex.: ip=1.2.3.4 host=db01 name=jorge, ana, pedro domain=acme.corp
    """
    itens: list[tuple[str, str]] = []
    for linha in (texto or "").strip().splitlines():
        linha = linha.strip()
        if not linha:
            continue
        matches = list(RE_TIPO.finditer(linha))
        if not matches:
            continue
        for i, m in enumerate(matches):
            tipo = m.group(1).lower()
            inicio_valor = m.end()
            fim_valor = matches[i + 1].start() if i + 1 < len(matches) else len(linha)
            bruto = linha[inicio_valor:fim_valor]
            tipo_repo = "name" if tipo == "org" else tipo
            for valor in _partir_valores(tipo_repo, bruto):
                # Evita lixo tipo "ip=pedro" dentro de name (já cortado por RE_TIPO)
                if valor.lower() in TIPOS:
                    continue
                itens.append((tipo_repo, valor))
    return itens


def _partir_feedback(bloco: str) -> list[str]:
    """allowed=/blocked= — vírgula separa vários termos; um termo pode ter espaços."""
    bruto = (bloco or "").strip()
    if not bruto:
        return []
    return [p.strip() for p in bruto.split(",") if p.strip()]


def classificar_blocked(valor: str) -> tuple[str, str]:
    """Heurística leve: ip / email / domain / name para a blocklist tipada."""
    v = (valor or "").strip()
    try:
        ipaddress.ip_address(v)
        return ("ip", v)
    except ValueError:
        pass
    if "@" in v:
        return ("email", v)
    if "." in v and " " not in v:
        return ("domain", v)
    return ("name", v)


def interpretar(texto: str) -> PedidoQuery:
    erro = validar_tamanho_e_anti_scan(texto)
    if erro:
        return erro

    limpo = (texto or "").strip()
    if not limpo:
        return PedidoQuery(intencao=Intencao.VAZIO)

    m = RE_ALLOWED.match(limpo)
    if m:
        termos = _partir_feedback(m.group(1))
        if termos:
            return PedidoQuery(intencao=Intencao.ALLOWED_FEEDBACK, termos=termos)
        return PedidoQuery(
            intencao=Intencao.TEXTO_LIVRE,
            texto=limpo,
        )

    m = RE_BLOCKED.match(limpo)
    if m:
        termos = _partir_feedback(m.group(1))
        if termos:
            return PedidoQuery(intencao=Intencao.BLOCKED_FEEDBACK, termos=termos)
        return PedidoQuery(intencao=Intencao.TEXTO_LIVRE, texto=limpo)

    itens = parse_linhas_confidential(limpo)
    if itens:
        return PedidoQuery(intencao=Intencao.ITEM_CONFIDENCIAL, itens=itens)

    m = RE_LOOKUP.match(limpo)
    if m:
        return PedidoQuery(intencao=Intencao.LOOKUP, placeholder=m.group(1))

    m = RE_REPLACE.match(limpo)
    if m:
        return PedidoQuery(
            intencao=Intencao.REPLACE_MD, caminho=m.group(1).strip()
        )

    # Só o placeholder sozinho → lookup
    if re.fullmatch(r"[A-Z][A-Z0-9_]+", limpo):
        return PedidoQuery(intencao=Intencao.LOOKUP, placeholder=limpo)

    # reveal <texto>  OU  qualquer texto que já traga placeholder
    m = RE_REVEAL.match(limpo)
    if m:
        return PedidoQuery(intencao=Intencao.REVEAL_TEXTO, texto=m.group(1).strip())
    if RE_PLACEHOLDER.search(limpo):
        return PedidoQuery(intencao=Intencao.REVEAL_TEXTO, texto=limpo)

    return PedidoQuery(intencao=Intencao.TEXTO_LIVRE, texto=limpo)


def _formatar_resumo_blocklist(itens: list[tuple[str, str]]) -> str:
    """Agrupa por tipo — legível no balão (sem parede de vírgulas)."""
    ordem = ("ip", "host", "domain", "name", "email")
    grupos: dict[str, list[str]] = {t: [] for t in ordem}
    for tipo, valor in itens:
        if tipo in grupos:
            grupos[tipo].append(valor)
    linhas = [f"Confidential items saved ({len(itens)}):"]
    for tipo in ordem:
        valores = grupos[tipo]
        if not valores:
            continue
        linhas.append(f"  {tipo}:")
        for v in valores:
            linhas.append(f"    • {v}")
    return "\n".join(linhas)


def aplicar_itens_blocklist(
    repo: Any, engagement_id: int, itens: list[tuple[str, str]]
) -> str:
    ips, hosts, domains, names, emails = [], [], [], [], []
    for tipo, valor in itens:
        if tipo == "ip":
            ips.append(valor)
        elif tipo == "host":
            hosts.append(valor)
        elif tipo == "domain":
            domains.append(valor)
        elif tipo == "email":
            emails.append(valor)
        elif tipo == "name":
            names.append(valor)
    # Emails conhecidos vivem junto dos contatos; o sanitize tipa EMAIL se tiver @
    repo.adicionar_blocklist(
        engagement_id,
        ips=ips,
        hosts=hosts,
        domains=domains,
        names=names + emails,
    )
    return _formatar_resumo_blocklist(itens)


def executar_lookup(repo: Any, engagement_id: int, placeholder: str) -> str:
    real = recon.lookup_placeholder(repo, engagement_id, placeholder)
    if real is None:
        return f"No mapping for {placeholder}."
    return f"{placeholder} → {real}"


def executar_reveal(repo: Any, engagement_id: int, texto: str) -> str:
    """Troca placeholders do texto pelos valores reais do eng."""
    mapa = recon.mapa_placeholders(repo, engagement_id)
    if not mapa:
        return "No mappings in this engagement yet."
    novo = recon.reconstruir_texto(texto, mapa)
    if novo == texto:
        return "No known placeholders found in that text."
    return novo


def executar_replace_md(
    repo: Any, engagement_id: int, caminho: str
) -> str:
    ok, msg, n = recon.replace_arquivo_md(Path(caminho), repo, engagement_id)
    if ok and n:
        return f"{msg} ({n} occurrences)."
    return msg
