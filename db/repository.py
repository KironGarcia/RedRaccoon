# db/repository.py
# Cômodo: acesso SQLite (CRUD) do engagement.
# Por quê: UI e pipeline nunca falam SQL direto — tudo passa por aqui.

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from db.schema import ALL_DDL


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_lista(valor: Any) -> str:
    if valor is None:
        return "[]"
    if isinstance(valor, str):
        return valor
    return json.dumps(list(valor), ensure_ascii=False)


def _ler_lista(texto: str | None) -> list[str]:
    if not texto:
        return []
    try:
        dados = json.loads(texto)
        return [str(x) for x in dados] if isinstance(dados, list) else []
    except json.JSONDecodeError:
        return []


class Repository:
    """Repositório de um workspace (um arquivo SQLite)."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._garantir_schema()

    def _garantir_schema(self) -> None:
        cur = self._conn.cursor()
        for ddl in ALL_DDL:
            cur.execute(ddl)
        # Workspaces antigos: coluna de calibração (allowed=)
        cols = {
            row[1]
            for row in cur.execute("PRAGMA table_info(engagement_config)").fetchall()
        }
        if "allow_list" not in cols:
            cur.execute(
                "ALTER TABLE engagement_config ADD COLUMN allow_list TEXT DEFAULT '[]'"
            )
        self._conn.commit()

    def fechar(self) -> None:
        self._conn.close()

    # --- engagement_config ---

    def criar_engagement(
        self,
        engagement_name: str,
        client_name: str = "",
        variants: list[str] | None = None,
        domains: list[str] | None = None,
        ip_ranges: list[str] | None = None,
        known_contacts: list[str] | None = None,
    ) -> int:
        self._conn.execute("UPDATE engagement_config SET active = 0")
        cur = self._conn.execute(
            """
            INSERT INTO engagement_config (
                engagement_name, client_name, client_name_variants,
                domains, ip_ranges, known_contacts, allow_list, created_at, active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                engagement_name,
                client_name,
                _json_lista(variants or []),
                _json_lista(domains or []),
                _json_lista(ip_ranges or []),
                _json_lista(known_contacts or []),
                _json_lista([]),
                _agora(),
            ),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def engagement_ativo(self) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM engagement_config WHERE active = 1 ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not row:
            row = self._conn.execute(
                "SELECT * FROM engagement_config ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "engagement_name": row["engagement_name"],
            "client_name": row["client_name"] or "",
            "client_name_variants": _ler_lista(row["client_name_variants"]),
            "domains": _ler_lista(row["domains"]),
            "ip_ranges": _ler_lista(row["ip_ranges"]),
            "known_contacts": _ler_lista(row["known_contacts"]),
            "allow_list": _ler_lista(row["allow_list"] if "allow_list" in row.keys() else None),
            "created_at": row["created_at"],
            "active": bool(row["active"]),
        }

    def adicionar_blocklist(
        self,
        engagement_id: int,
        *,
        ips: list[str] | None = None,
        hosts: list[str] | None = None,
        domains: list[str] | None = None,
        names: list[str] | None = None,
    ) -> None:
        eng = self._conn.execute(
            "SELECT * FROM engagement_config WHERE id = ?", (engagement_id,)
        ).fetchone()
        if not eng:
            raise ValueError("Engagement não encontrado.")

        ip_ranges = _ler_lista(eng["ip_ranges"])
        domain_list = _ler_lista(eng["domains"])
        contacts = _ler_lista(eng["known_contacts"])
        variants = _ler_lista(eng["client_name_variants"])

        for ip in ips or []:
            if ip and ip not in ip_ranges:
                ip_ranges.append(ip)
        for host in hosts or []:
            if host and host not in domain_list:
                domain_list.append(host)
        for domain in domains or []:
            if domain and domain not in domain_list:
                domain_list.append(domain)
        # name = pessoa/contato (PERSON). Não mistura com variantes de ORG.
        for name in names or []:
            if name and name not in contacts:
                contacts.append(name)

        self._conn.execute(
            """
            UPDATE engagement_config
            SET ip_ranges = ?, domains = ?, known_contacts = ?, client_name_variants = ?
            WHERE id = ?
            """,
            (
                _json_lista(ip_ranges),
                _json_lista(domain_list),
                _json_lista(contacts),
                _json_lista(variants),
                engagement_id,
            ),
        )
        self._conn.commit()

    def adicionar_allow_list(
        self, engagement_id: int, termos: list[str]
    ) -> list[str]:
        """Calibração: palavras que NÃO devem ser mascaradas (allowed=)."""
        eng = self._conn.execute(
            "SELECT allow_list FROM engagement_config WHERE id = ?",
            (engagement_id,),
        ).fetchone()
        if not eng:
            raise ValueError("Engagement não encontrado.")
        atual = _ler_lista(eng["allow_list"] if eng["allow_list"] is not None else None)
        adicionados: list[str] = []
        vistos = {a.casefold() for a in atual}
        for t in termos:
            limpo = (t or "").strip()
            if not limpo or limpo.casefold() in vistos:
                continue
            atual.append(limpo)
            vistos.add(limpo.casefold())
            adicionados.append(limpo)
        self._conn.execute(
            "UPDATE engagement_config SET allow_list = ? WHERE id = ?",
            (_json_lista(atual), engagement_id),
        )
        self._conn.commit()
        return adicionados

    # --- entity_mapping ---

    def buscar_por_valor_real(
        self, engagement_id: int, real_value: str
    ) -> dict[str, Any] | None:
        row = self._conn.execute(
            """
            SELECT * FROM entity_mapping
            WHERE engagement_id = ? AND real_value = ?
            """,
            (engagement_id, real_value),
        ).fetchone()
        return dict(row) if row else None

    def buscar_por_placeholder(
        self, engagement_id: int, placeholder: str
    ) -> dict[str, Any] | None:
        row = self._conn.execute(
            """
            SELECT * FROM entity_mapping
            WHERE engagement_id = ? AND placeholder = ?
            """,
            (engagement_id, placeholder),
        ).fetchone()
        return dict(row) if row else None

    def listar_mapeamentos(self, engagement_id: int) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT * FROM entity_mapping
            WHERE engagement_id = ?
            ORDER BY entity_type, id
            """,
            (engagement_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def contador_tipo(self, engagement_id: int, entity_type: str) -> int:
        row = self._conn.execute(
            """
            SELECT COUNT(*) AS c FROM entity_mapping
            WHERE engagement_id = ? AND entity_type = ?
            """,
            (engagement_id, entity_type),
        ).fetchone()
        return int(row["c"]) if row else 0

    def inserir_mapeamento(
        self,
        engagement_id: int,
        real_value: str,
        placeholder: str,
        entity_type: str,
        occurrence_count: int = 1,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO entity_mapping (
                engagement_id, real_value, placeholder, entity_type,
                first_seen, occurrence_count
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                engagement_id,
                real_value,
                placeholder,
                entity_type,
                _agora(),
                occurrence_count,
            ),
        )
        self._conn.commit()

    def incrementar_ocorrencia(self, mapping_id: int, delta: int) -> None:
        self._conn.execute(
            """
            UPDATE entity_mapping
            SET occurrence_count = occurrence_count + ?
            WHERE id = ?
            """,
            (delta, mapping_id),
        )
        self._conn.commit()

    def remover_mapeamentos_ids(self, ids: list[int]) -> None:
        if not ids:
            return
        placeholders = ",".join("?" * len(ids))
        self._conn.execute(
            f"DELETE FROM entity_mapping WHERE id IN ({placeholders})",
            ids,
        )
        self._conn.commit()

    def atualizar_ocorrencias_lote(
        self, ajustes: list[tuple[int, int]]
    ) -> None:
        """ajustes = [(mapping_id, delta), ...] — delta negativo reverte."""
        for mapping_id, delta in ajustes:
            self._conn.execute(
                """
                UPDATE entity_mapping
                SET occurrence_count = MAX(0, occurrence_count + ?)
                WHERE id = ?
                """,
                (delta, mapping_id),
            )
        self._conn.commit()

    # --- sanitization_log ---

    def registrar_log(
        self, engagement_id: int, action: str, entities_processed: int
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO sanitization_log (
                engagement_id, timestamp, action, entities_processed
            ) VALUES (?, ?, ?, ?)
            """,
            (engagement_id, _agora(), action, entities_processed),
        )
        self._conn.commit()
