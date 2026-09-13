# core/placeholders.py
# Cômodo: geração consistente de placeholders (TARGET_IP_1, etc.).
# Por quê: mesmo valor real → mesmo placeholder dentro do engagement.

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from db.repository import Repository

# Prefixo por tipo de entidade (auditável e legível no relatório)
PREFIXOS = {
    "IP": "TARGET_IP",
    "HOST": "TARGET_HOST",
    "DOMAIN": "TARGET_DOMAIN",
    "ORG": "CLIENT_NAME",
    "PERSON": "PERSON",
    "EMAIL": "TARGET_EMAIL",
    "APIKEY": "TARGET_APIKEY",
    "USER": "TARGET_USER",
    "PASSWORD": "TARGET_PASS",
    "SID": "TARGET_SID",
    "ID": "TARGET_ID",
    "PHONE": "TARGET_PHONE",
    "ADDRESS": "TARGET_ADDR",
}


def tipo_para_prefixo(entity_type: str) -> str:
    return PREFIXOS.get(entity_type.upper(), f"TARGET_{entity_type.upper()}")


def gerar_placeholder(
    repo: "Repository",
    engagement_id: int,
    entity_type: str,
) -> str:
    """
    Cria o próximo placeholder do tipo.
    ORG usa CLIENT_NAME sem número se for o primeiro; depois CLIENT_NAME_2...
    """
    tipo = entity_type.upper()
    prefixo = tipo_para_prefixo(tipo)
    n = repo.contador_tipo(engagement_id, tipo) + 1

    if tipo == "ORG" and n == 1:
        return "CLIENT_NAME"
    if tipo == "ORG":
        return f"CLIENT_NAME_{n}"
    return f"{prefixo}_{n}"


def obter_ou_criar(
    repo: "Repository",
    engagement_id: int,
    real_value: str,
    entity_type: str,
) -> tuple[str, bool, int | None]:
    """
    Retorna (placeholder, foi_criado_agora, mapping_id_se_existia).
    Não incrementa occurrence aqui — o sanitize decide após ACEPT.
    """
    tipo = entity_type.upper()
    # Domínio/e-mail: o DNS não distingue maiúscula (NYXLYNX.IO = nyxlynx.io)
    tipo_ci = tipo in {"DOMAIN", "HOST", "EMAIL", "ORG"}
    existente = repo.buscar_por_valor_real(
        engagement_id, real_value, ignore_case=tipo_ci
    )
    if existente:
        return existente["placeholder"], False, existente["id"]

    placeholder = gerar_placeholder(repo, engagement_id, entity_type)
    return placeholder, True, None
