"""Conquistas ORGANIZACIONAIS verificáveis (gamificação responsável).

Regras: só critérios objetivos calculados de dados reais da plataforma; sem pontos acumuláveis, sem ranking, sem comparação entre
organizações, nunca sobre pessoas atendidas/beneficiários; o conjunto é privado à organização (ela decide se divulga)."""
from __future__ import annotations

from ..db.pq import Connection


def compute(c: Connection, org_id: str, kind: str) -> list[dict]:
    out: list[dict] = []

    def add(code, label, earned, how, progress=None):
        out.append({"code": code, "label": label, "earned": bool(earned), "how": how, "progress": progress})

    org = c.one("SELECT description, website, causes, territories, compliance_status FROM organizations WHERE id = $1", org_id)
    filled = sum(bool(org[k]) for k in ("description", "website", "causes", "territories"))
    add("profile_complete", "Perfil completo", filled == 4, "Preencha descrição, site, causas e territórios", f"{filled}/4")
    add("compliance_approved", "Compliance aprovado", org["compliance_status"] == "approved", "Conclua a verificação de compliance")
    if kind == "osc":
        docs = c.one("SELECT count(*) FILTER (WHERE status = 'clean' AND (valid_until IS NULL OR valid_until >= current_date)) AS ok,"
                     " count(*) FILTER (WHERE valid_until < current_date) AS expired FROM documents WHERE org_id = $1 AND deleted_at IS NULL", org_id)
        add("documents_up_to_date", "Documentos em dia", docs["ok"] >= 3 and docs["expired"] == 0, "Ao menos 3 documentos válidos e nenhum vencido", f"{docs['ok']} válidos, {docs['expired']} vencidos")
        ev = c.one("SELECT count(*) FILTER (WHERE status = 'accepted') AS ok, count(*) AS total FROM evidences WHERE org_id = $1", org_id)
        add("evidence_accepted", "Evidências aceitas", ev["ok"] >= 5, "5 evidências aceitas por financiadores", f"{ev['ok']}/5")
        iv = c.scalar("SELECT count(*) FROM indicator_values WHERE org_id = $1 AND status = 'validated'", org_id)
        add("validated_results", "Resultados validados", iv >= 3, "3 valores de indicador validados por outra organização", f"{iv}/3")
        prc = c.scalar("SELECT count(*) FROM procurement_requests WHERE org_id = $1 AND status = 'decided'", org_id)
        add("procurement_diligence", "Compras com cotações", prc >= 3, "3 compras decididas dentro da política de cotações", f"{prc}/3")
    elif kind in ("company", "government", "individual"):
        n = c.one("SELECT count(*) FILTER (WHERE status IN ('confirmed')) AS confirmed, count(*) AS total FROM commitments WHERE funder_org_id = $1", org_id)
        add("funding_confirmed", "Aportes confirmados", n["confirmed"] >= 1, "Ao menos 1 aporte confirmado pela OSC", f"{n['confirmed']}")
        rv = c.scalar("SELECT count(*) FROM evidences WHERE reviewed_by_org = $1", org_id)
        add("diligent_reviewer", "Revisão de evidências", rv >= 5, "5 evidências revisadas", f"{rv}/5")
    elif kind == "provider":
        done = c.scalar("SELECT count(*) FROM professional_reviews WHERE professional_org_id = $1 AND status IN ('approved','signed')", org_id)
        add("reviews_completed", "Revisões concluídas", done >= 3, "3 revisões concluídas", f"{done}/3")
        cred = c.scalar("SELECT count(*) FROM professional_credentials WHERE org_id = $1 AND verification_status = 'verified'", org_id)
        add("credential_verified", "Credencial verificada", cred >= 1, "Tenha ao menos uma credencial verificada")
    return out
