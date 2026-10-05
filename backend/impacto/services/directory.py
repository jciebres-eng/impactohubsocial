"""Diretório de profissionais parceiros.

INVARIANTE (ADR-007): a posição NUNCA depende de plano, assinatura, voucher ou pagamento. Este módulo não
importa billing/entitlements (verificado em tests/test_architecture.py) e a ordenação é documentada:
1) credencial verificada e vigente, 2) aderência de categoria/território, 3) nome (desempate determinístico).
"""
from __future__ import annotations

from ..db.pq import Connection


def search_professionals(c: Connection, *, category: str | None, territory: str | None, text: str | None, limit: int, offset: int) -> list[dict]:
    return c.query(
        "SELECT o.id::text AS org_id, coalesce(o.trade_name, o.legal_name) AS name, o.city, o.uf, p.services, p.categories,"
        " p.remote, p.territories, p.price_info, p.accepting_requests,"
        " (SELECT coalesce(json_agg(json_build_object('council', pc.council, 'uf', pc.uf, 'number', pc.number,"
        "   'status', pc.verification_status, 'valid_until', pc.valid_until) ORDER BY pc.council), '[]'::json)"
        "   FROM professional_credentials pc WHERE pc.org_id = o.id) AS credentials,"
        " EXISTS (SELECT 1 FROM professional_credentials pc WHERE pc.org_id = o.id AND pc.verification_status = 'verified'"
        "   AND (pc.valid_until IS NULL OR pc.valid_until >= current_date)) AS has_verified_credential"
        " FROM organizations o JOIN provider_profiles p ON p.org_id = o.id"
        " WHERE o.kind = 'provider' AND o.status = 'active' AND p.accepting_requests"
        "   AND ($1::text IS NULL OR $1 = ANY(p.categories))"
        "   AND ($2::text IS NULL OR p.remote OR EXISTS (SELECT 1 FROM unnest(p.territories) t WHERE $2 LIKE t || '%' OR t = 'BR'))"
        "   AND ($3::text IS NULL OR o.legal_name ILIKE '%' || $3 || '%' OR o.trade_name ILIKE '%' || $3 || '%'"
        "        OR array_to_string(p.services, ' ') ILIKE '%' || $3 || '%')"
        " ORDER BY has_verified_credential DESC,"
        "   (CASE WHEN $1::text IS NOT NULL THEN 1 ELSE 0 END) DESC,"
        "   (CASE WHEN $2::text IS NOT NULL AND $2 = ANY(p.territories) THEN 1 ELSE 0 END) DESC,"
        "   lower(coalesce(o.trade_name, o.legal_name)), o.id"
        " LIMIT $4 OFFSET $5",
        category, territory, (text or None) and text[:80], limit, offset)
