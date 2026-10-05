"""Correspondência entre o ID interno da IMPACTO e o ID do sistema externo.

Regra: o ID interno NUNCA é substituído pelo externo. A correspondência é um registro à parte, por conexão, com
versão externa e estado. Divergência de versão vira CONFLITO registrado — nada é sobrescrito em silêncio.
"""
from __future__ import annotations

from datetime import UTC, datetime

from ..db.pq import Json


def link(c, *, org_id: str, connection_id: str, entity: str, internal_id: str, external_id: str,
         external_version: str | None = None) -> dict:
    """Cria ou atualiza a correspondência. Se o mesmo ID externo já aponta para OUTRO registro interno, é conflito."""
    existing = c.one("SELECT id::text AS id, internal_id::text AS internal_id, external_version, sync_status"
                     " FROM external_entity_links WHERE connection_id = $1 AND entity = $2 AND external_id = $3",
                     connection_id, entity, external_id)
    if existing and existing["internal_id"] != internal_id:
        c.run("UPDATE external_entity_links SET sync_status = 'conflict', conflict_detail = $2::jsonb, updated_at = now() WHERE id = $1",
              existing["id"], Json({"reason": "external_id_aponta_para_outro_registro_interno",
                                    "internal_id_atual": existing["internal_id"], "internal_id_recebido": internal_id,
                                    "detected_at": datetime.now(UTC).isoformat()}))
        return {"status": "conflict", "id": existing["id"], "reason": "external_id_ja_vinculado"}
    row = c.one("INSERT INTO external_entity_links(org_id, connection_id, entity, internal_id, external_id, external_version,"
                " last_synced_at, sync_status) VALUES ($1,$2,$3,$4,$5,$6, now(), 'linked')"
                " ON CONFLICT (connection_id, entity, internal_id) DO UPDATE SET external_id = EXCLUDED.external_id,"
                " external_version = EXCLUDED.external_version, last_synced_at = now(),"
                " sync_status = CASE WHEN external_entity_links.sync_status = 'conflict' THEN 'conflict' ELSE 'linked' END,"
                " updated_at = now() RETURNING id::text AS id, sync_status", org_id, connection_id, entity, internal_id,
                external_id, external_version)
    return {"status": row["sync_status"], "id": row["id"]}


def resolve_internal(c, *, connection_id: str, entity: str, external_id: str) -> str | None:
    return c.scalar("SELECT internal_id::text FROM external_entity_links WHERE connection_id = $1 AND entity = $2"
                    " AND external_id = $3 AND sync_status <> 'deleted_externally'", connection_id, entity, external_id)


def resolve_external(c, *, connection_id: str, entity: str, internal_id: str) -> str | None:
    return c.scalar("SELECT external_id FROM external_entity_links WHERE connection_id = $1 AND entity = $2 AND internal_id = $3",
                    connection_id, entity, internal_id)


def detect_conflict(c, *, connection_id: str, entity: str, external_id: str, incoming_version: str | None,
                    internal_updated_at: datetime | None = None) -> dict:
    """Decide o que fazer com um registro que chegou do sistema externo. NUNCA sobrescreve em silêncio.

    - versão externa igual à registrada → `unchanged` (ignora, idempotente)
    - versão externa diferente E registro interno alterado depois da última sincronização → `conflict` (registra e para)
    - caso contrário → `apply`
    """
    row = c.one("SELECT id::text AS id, external_version, last_synced_at FROM external_entity_links"
                " WHERE connection_id = $1 AND entity = $2 AND external_id = $3", connection_id, entity, external_id)
    if not row:
        return {"action": "apply", "reason": "novo"}
    if incoming_version and row["external_version"] == incoming_version:
        return {"action": "unchanged", "reason": "mesma_versao_externa"}
    if internal_updated_at and row["last_synced_at"] and internal_updated_at > row["last_synced_at"]:
        c.run("UPDATE external_entity_links SET sync_status = 'conflict', conflict_detail = $2::jsonb, updated_at = now() WHERE id = $1",
              row["id"], Json({"reason": "alterado_dos_dois_lados", "internal_updated_at": internal_updated_at.isoformat(),
                               "last_synced_at": row["last_synced_at"].isoformat(),
                               "external_version_registrada": row["external_version"], "external_version_recebida": incoming_version}))
        return {"action": "conflict", "reason": "alterado_dos_dois_lados", "link_id": row["id"]}
    return {"action": "apply", "reason": "versao_externa_mais_nova"}


def mark_deleted_externally(c, *, connection_id: str, entity: str, external_id: str) -> bool:
    """Registro apagado no sistema externo: marca o estado, mas NÃO apaga dado da IMPACTO (decisão humana)."""
    return bool(c.run("UPDATE external_entity_links SET sync_status = 'deleted_externally', updated_at = now()"
                      " WHERE connection_id = $1 AND entity = $2 AND external_id = $3", connection_id, entity, external_id))


def overview(c, *, org_id: str) -> dict:
    return {"by_status": c.query("SELECT sync_status, count(*) AS n FROM external_entity_links WHERE org_id = $1 GROUP BY 1 ORDER BY 1", org_id),
            "conflicts": c.query("SELECT id::text AS id, entity, internal_id::text AS internal_id, external_id, conflict_detail, updated_at"
                                 " FROM external_entity_links WHERE org_id = $1 AND sync_status = 'conflict' ORDER BY updated_at DESC LIMIT 50", org_id)}
