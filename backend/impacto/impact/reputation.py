"""Reputação explicável, em dimensões, sem nota única.

A frase dos documentos desta rodada que governa este arquivo:

    "NUNCA transformar o score em uma caixa-preta que determina automaticamente acesso a
     financiamento, contratação, benefícios, oportunidades ou exposição pública."

Então:

* **Não existe nota única.** É divergência consciente dos prompts, que falam de "score". Nota única
  é o que vira ranking, e ranking é o que vira critério de acesso. A saída é por dimensão, com
  valor, confiança, observações, quanto foi verificado por terceiro e a lista do que entrou.
* **Dimensão sem base suficiente não tem valor** (`value = None`, faixa `insufficient`).
  Organização nova não começa ruim: começa sem medida. Nota baixa por ausência de histórico seria
  barreira de entrada construída por acidente, e cairia sobre a OSC pequena.
* **Nada de plano, assinatura ou pagamento entra na conta** — reafirma a ADR-042. Há teste de
  varredura neste módulo.
* **Órgão público não recebe nota**, recebe perfil de governança e transparência em contagens.
* **Pessoa física não tem perfil público de reputação.**
* **Tudo é calculado na leitura.** O snapshot existe para a linha do tempo, é append-only e só é
  escrito por `app_record_reputation()`.
"""
from __future__ import annotations

import json
from typing import Any

from ..core.evidence import BAND_LABEL, ConfidenceBand, band
from ..db.pq import Connection
from ..http import ApiError, forbidden, not_found, unprocessable
from ..network import notify

ENGINE_VERSION = "reputation-dimensions@1.0.0"

#: Dimensão sem denominador: reporta contagem e NÃO produz valor de 0 a 100. Inventar uma escala
#: para "quantos atos de revisão são muitos" seria exatamente a arbitrariedade que o resto do
#: arquivo evita.
COUNT_ONLY = ("contribution_to_others",)

#: Órgão público recebe os mesmos fatos sem valor: pontuar ente público é pontuar política pública.
NO_SCORE_KINDS = ("government",)
#: Pessoa física não tem perfil público de reputação — nem agregado, nem dimensão.
NO_PUBLIC_PROFILE_KINDS = ("individual",)

_BAND_TO_DB = {
    ConfidenceBand.HIGH: "high", ConfidenceBand.MEDIUM: "medium", ConfidenceBand.LOW: "low",
    ConfidenceBand.INSUFFICIENT_DATA: "insufficient",
}

NO_SINGLE_SCORE_NOTE = (
    "Não existe nota única de reputação nesta plataforma, por decisão registrada (ADR-201). Nota "
    "única é o que vira ranking, e ranking é o que vira critério de acesso a financiamento. Compor "
    "estas dimensões numa nota só é possível fora da plataforma, assinando a escolha dos pesos."
)
NO_AUTOMATIC_DECISION_NOTE = (
    "Nenhum valor desta resposta bloqueia, libera ou ordena nada: não entra em busca, match, "
    "recomendação, elegibilidade nem exposição pública. Reputação aqui é informação para decisão "
    "humana, com direito a contestação registrada."
)


# ================================================================================================ catálogo
def dimensions(conn: Connection) -> dict:
    rows = conn.query(
        "SELECT code, name_pt, what_it_measures, why_it_is_fair, what_it_does_not_measure,"
        " signals_note, min_observations FROM reputation_dimensions WHERE active"
        " ORDER BY position")
    return {
        "items": [{**r, "count_only": r["code"] in COUNT_ONLY} for r in rows],
        "no_single_score": NO_SINGLE_SCORE_NOTE,
        "no_automatic_decision": NO_AUTOMATIC_DECISION_NOTE,
        "excluded_signals": [
            "plano, assinatura, pagamento ou qualquer sinal comercial (ADR-042 e ADR-203)",
            "autodeclaração sem ato de terceiro (entra contada à parte, como self_declared)",
            "tamanho da organização, orçamento e número absoluto de projetos",
            "qualquer saída de modelo de linguagem",
        ],
        "bands": [{"key": k, "label": v} for k, v in
                  ((_BAND_TO_DB[b], BAND_LABEL[b]) for b in ConfidenceBand)],
    }


# ================================================================================================ sinais
def _ratio(num: int, den: int) -> float | None:
    return None if not den else 100.0 * num / den


def _signals(conn: Connection, org_id: str) -> dict[str, dict]:
    """Uma consulta por sinal, sobre tabelas de fato. Nenhuma inferência, nenhum sinal comercial."""
    v = conn.one(
        "SELECT count(*) AS total,"
        " count(*) FILTER (WHERE status = 'validated') AS validated,"
        " count(*) FILTER (WHERE status = 'validated' AND evidence_id IS NOT NULL) AS with_evidence"
        " FROM indicator_values WHERE org_id = $1", org_id)
    ev = conn.one(
        "SELECT count(*) AS total, count(*) FILTER (WHERE status = 'accepted') AS accepted"
        " FROM evidences WHERE org_id = $1", org_id)
    ex = conn.one(
        "SELECT count(*) AS total, count(*) FILTER (WHERE document_id IS NOT NULL) AS with_receipt"
        " FROM expenses WHERE org_id = $1", org_id)
    cm = conn.one(
        "SELECT count(*) FILTER (WHERE status IN ('disbursed','confirmed')) AS moved,"
        " count(*) FILTER (WHERE status = 'confirmed') AS confirmed"
        " FROM commitments WHERE project_id IN (SELECT id FROM projects WHERE org_id = $1)", org_id)
    cl = conn.one(
        "SELECT count(*) FILTER (WHERE s.check_round > 0) AS checked,"
        " count(*) FILTER (WHERE s.status = 'substantiated') AS substantiated,"
        " count(*) FILTER (WHERE s.status = 'flagged_accepted_by_review') AS flagged_accepted,"
        " count(*) FILTER (WHERE s.status = 'flagged') AS flagged_open,"
        " count(*) FILTER (WHERE s.status = 'attention') AS attention"
        " FROM claims c CROSS JOIN LATERAL claim_status(c.id) s"
        " WHERE c.org_id = $1 AND c.withdrawn_at IS NULL", org_id)
    doc = conn.one(
        "SELECT count(*) AS total, count(*) FILTER (WHERE validation_status = 'validated'"
        "   AND (valid_until IS NULL OR valid_until >= current_date)) AS validated"
        " FROM documents WHERE org_id = $1 AND deleted_at IS NULL", org_id)
    qual = conn.one(
        "SELECT count(*) AS total, count(*) FILTER (WHERE verification_status = 'verified'"
        "   AND (expiration_date IS NULL OR expiration_date >= current_date)) AS verified"
        " FROM organization_qualifications WHERE org_id = $1", org_id)
    comp = conn.scalar("SELECT compliance_status FROM organizations WHERE id = $1", org_id)
    ms = conn.one(
        "SELECT count(*) FILTER (WHERE status <> 'planned') AS started,"
        " count(*) FILTER (WHERE status = 'accepted') AS accepted"
        " FROM milestones WHERE project_id IN (SELECT id FROM projects WHERE org_id = $1)", org_id)
    pr = conn.one(
        "SELECT count(*) FILTER (WHERE status <> 'draft') AS published,"
        " count(*) FILTER (WHERE status = 'completed') AS completed"
        " FROM projects WHERE org_id = $1", org_id)
    # Atos em que a organização serviu de TERCEIRO para outra.
    third = conn.one(
        "SELECT (SELECT count(*) FROM indicator_values WHERE validated_by_org = $1"
        "          AND org_id <> $1) AS measurements_validated,"
        " (SELECT count(*) FROM impact_edges WHERE reviewed_by_org = $1 AND org_id <> $1)"
        "   AS causalities_reviewed,"
        " (SELECT count(*) FROM claim_reviews WHERE reviewer_org_id = $1) AS claims_reviewed",
        org_id)
    return {"values": v, "evidences": ev, "expenses": ex, "commitments": cm, "claims": cl,
            "documents": doc, "qualifications": qual, "compliance": comp, "milestones": ms,
            "projects": pr, "third_party_acts": third}


def _mean(parts: list[float | None]) -> float | None:
    got = [p for p in parts if p is not None]
    return None if not got else sum(got) / len(got)


def _dimension(code: str, s: dict) -> dict:
    """Uma função por dimensão, em vez de pesos numa tabela.

    Peso em tabela parece configurável e é, na prática, cálculo escondido: ninguém revisa um número
    numa linha. Aqui a conta está no código, aparece em diff e tem teste.
    """
    if code == "evidence_discipline":
        v = s["values"]
        value = _ratio(v["with_evidence"], v["total"])
        return {"value": value, "observations": v["total"], "verified": v["validated"],
                "self_declared": v["total"] - v["validated"],
                "inputs": {"reported_values": v["total"], "validated_values": v["validated"],
                           "validated_with_evidence": v["with_evidence"],
                           "accepted_evidences": s["evidences"]["accepted"]},
                "how": "medições validadas COM evidência sobre medições reportadas"}
    if code == "financial_transparency":
        ex, cm = s["expenses"], s["commitments"]
        value = _mean([_ratio(ex["with_receipt"], ex["total"]),
                       _ratio(cm["confirmed"], cm["moved"])])
        obs = ex["total"] + cm["moved"]
        return {"value": value, "observations": obs,
                "verified": ex["with_receipt"] + cm["confirmed"],
                "self_declared": obs - (ex["with_receipt"] + cm["confirmed"]),
                "inputs": {"expenses": ex["total"], "expenses_with_receipt": ex["with_receipt"],
                           "commitments_moved": cm["moved"],
                           "commitments_confirmed": cm["confirmed"]},
                "how": "média das razões disponíveis: despesa com comprovante, aporte confirmado "
                       "pelas duas pontas"}
    if code == "claim_integrity":
        c = s["claims"]
        # Alegação marcada e ainda não revisada conta como zero; marcada e aceita em revisão conta
        # metade, porque a revisão qualifica a marca sem apagá-la.
        favour = c["substantiated"] + 0.5 * c["flagged_accepted"] + 0.5 * c["attention"]
        value = None if not c["checked"] else 100.0 * favour / c["checked"]
        return {"value": value, "observations": c["checked"],
                "verified": c["substantiated"] + c["flagged_accepted"],
                "self_declared": c["flagged_open"],
                "inputs": {"checked": c["checked"], "substantiated": c["substantiated"],
                           "attention": c["attention"], "flagged_open": c["flagged_open"],
                           "flagged_accepted_by_review": c["flagged_accepted"]},
                "how": "alegações sustentadas (mais metade das em atenção e das marcadas aceitas "
                       "em revisão) sobre alegações verificadas"}
    if code == "institutional_formality":
        d, q = s["documents"], s["qualifications"]
        comp = 100.0 if s["compliance"] == "approved" else (None if not s["compliance"] else 0.0)
        value = _mean([_ratio(d["validated"], d["total"]), _ratio(q["verified"], q["total"]), comp])
        obs = d["total"] + q["total"] + (1 if s["compliance"] else 0)
        ver = d["validated"] + q["verified"] + (1 if s["compliance"] == "approved" else 0)
        return {"value": value, "observations": obs, "verified": ver,
                "self_declared": obs - ver,
                "inputs": {"documents": d["total"], "documents_validated": d["validated"],
                           "qualifications": q["total"], "qualifications_verified": q["verified"],
                           "compliance_status": s["compliance"]},
                "how": "média das razões disponíveis: documento validado, qualificação verificada "
                       "e vigente, compliance aprovado"}
    if code == "delivery_record":
        m, p = s["milestones"], s["projects"]
        value = _mean([_ratio(m["accepted"], m["started"]), _ratio(p["completed"], p["published"])])
        obs = m["started"] + p["published"]
        return {"value": value, "observations": obs,
                "verified": m["accepted"] + p["completed"],
                "self_declared": obs - (m["accepted"] + p["completed"]),
                "inputs": {"milestones_started": m["started"],
                           "milestones_accepted": m["accepted"],
                           "projects_published": p["published"],
                           "projects_completed": p["completed"]},
                "how": "média das razões disponíveis: marco com evidência aceita, projeto concluído."
                       " Projeto cancelado NÃO conta contra: a plataforma não sabe de quem foi a "
                       "decisão"}
    if code == "contribution_to_others":
        t = s["third_party_acts"]
        total = t["measurements_validated"] + t["causalities_reviewed"] + t["claims_reviewed"]
        return {"value": None, "observations": total, "verified": total, "self_declared": 0,
                "inputs": dict(t),
                "how": "CONTAGEM, sem valor de 0 a 100: não existe denominador para 'quantas "
                       "revisões são muitas', e inventar a escala seria arbitrário"}
    raise ValueError(f"dimensão desconhecida: {code}")


def _confidence(obs: int, verified: int, min_obs: int) -> float:
    """Confiança explícita e simples, para poder ser explicada a quem é avaliado.

    Dois fatores: COBERTURA (quantas observações, saturando em 3× o mínimo da dimensão) e
    VERIFICAÇÃO (quanto das observações tem ato de terceiro). Confiança nunca passa de 100 e nunca
    é alta só por volume.
    """
    if not obs:
        return 0.0
    coverage = min(1.0, obs / (3.0 * min_obs))
    verification = 0.5 + 0.5 * (verified / obs if obs else 0)
    return round(100.0 * coverage * verification, 2)


# ================================================================================================ perfil
def profile(conn: Connection, *, org_id: str, viewer_org_id: str | None = None,
            privileged: bool = False) -> dict:
    org = conn.one("SELECT kind, coalesce(trade_name, legal_name) AS display_name,"
                   " compliance_status FROM organizations WHERE id = $1",
                   org_id)
    if not org:
        raise not_found("Organização")
    own = viewer_org_id == org_id or privileged
    if org["kind"] in NO_PUBLIC_PROFILE_KINDS and not own:
        raise forbidden(
            "Pessoa física não tem perfil público de reputação nesta plataforma — nem agregado, "
            "nem por dimensão.", code="no_public_profile_for_person")
    defs = conn.query(
        "SELECT code, name_pt, min_observations, what_it_does_not_measure FROM"
        " reputation_dimensions WHERE active ORDER BY position")
    s = _signals(conn, org_id)
    no_score = org["kind"] in NO_SCORE_KINDS
    out = []
    for d in defs:
        calc = _dimension(d["code"], s)
        obs, ver = calc["observations"], calc["verified"]
        conf = _confidence(obs, ver, d["min_observations"])
        enough = obs >= d["min_observations"]
        b = band(conf, ver, max(obs, d["min_observations"])) if enough \
            else ConfidenceBand.INSUFFICIENT_DATA
        value = calc["value"] if (enough and d["code"] not in COUNT_ONLY) else None
        # Faixa insuficiente NÃO publica número, mesmo com observações bastando. A restrição
        # `insufficient_has_no_value` pegou exatamente este caso: havia observações suficientes e
        # verificação por terceiro baixa, e o perfil publicaria um valor que a própria faixa dizia
        # não sustentar. O banco recusou, e a recusa estava certa.
        if b is ConfidenceBand.INSUFFICIENT_DATA:
            value = None
        if no_score:
            value = None
        out.append({
            "dimension": d["code"], "name_pt": d["name_pt"],
            "value": None if value is None else round(value, 2),
            "confidence": conf, "band": _BAND_TO_DB[b], "band_label": BAND_LABEL[b],
            "observations": obs, "verified_observations": ver,
            "self_declared_observations": calc["self_declared"],
            "min_observations": d["min_observations"],
            "count_only": d["code"] in COUNT_ONLY,
            "inputs": calc["inputs"], "how": calc["how"],
            "what_it_does_not_measure": d["what_it_does_not_measure"],
            "reason_without_value": _reason(value, enough, d, no_score, b),
        })
    disputes = _open_disputes(conn, org_id)
    for row in out:
        row["contested"] = [d for d in disputes if d["dimension"] == row["dimension"]]
    body: dict[str, Any] = {
        "org_id": org_id, "org_kind": org["kind"], "display_name": org["display_name"],
        "dimensions": out, "engine_version": ENGINE_VERSION,
        "no_single_score": NO_SINGLE_SCORE_NOTE,
        "no_automatic_decision": NO_AUTOMATIC_DECISION_NOTE,
        "open_disputes": len(disputes),
    }
    if no_score:
        body["profile_type"] = "governance_and_transparency"
        body["note"] = (
            "Órgão público recebe PERFIL DE GOVERNANÇA E TRANSPARÊNCIA, não nota: os mesmos fatos "
            "aparecem em contagem, sem valor de 0 a 100 e sem faixa comparável. Pontuar ente "
            "público seria pontuar política pública, e esta plataforma não tem mandato para isso.")
    else:
        body["profile_type"] = "organization_dimensions"
    if org["kind"] in NO_PUBLIC_PROFILE_KINDS:
        body["private"] = True
        body["note"] = ("Este perfil é visível apenas para a própria pessoa: pessoa física não tem "
                        "reputação pública nesta plataforma.")
    return body


def _reason(value: float | None, enough: bool, d: dict, no_score: bool,
            b: ConfidenceBand) -> str | None:
    if value is not None:
        return None
    if no_score:
        return "Órgão público não recebe valor: o perfil é de governança e transparência."
    if d["code"] in COUNT_ONLY:
        return ("Dimensão de contagem: não existe denominador, então não existe valor de 0 a 100. "
                "O número de atos está em observations.")
    if not enough:
        return (f"Base insuficiente: a dimensão exige pelo menos {d['min_observations']} "
                "observação(ões). Organização sem histórico não começa com nota baixa — começa SEM "
                "medida, de propósito.")
    if b is ConfidenceBand.INSUFFICIENT_DATA:
        return ("Confiança insuficiente: há observações bastando, mas pouca delas tem ato de "
                "terceiro. Publicar o número aqui seria dar aparência de medida a algo que a "
                "própria faixa de confiança diz não sustentar.")
    return "Não há denominador disponível para calcular esta dimensão no período."


# ================================================================================================ linha do tempo
def snapshot(conn: Connection, *, org_id: str) -> dict:
    """Congela a leitura atual na linha do tempo. Append-only, por `app_record_reputation()`.

    v0.20.0 — avisa a organização quando uma dimensão MUDA DE FAIXA, e só então. Avisar a cada
    snapshot transformaria a reputação em ruído diário; não avisar nunca, que era o estado anterior,
    faz a organização descobrir que caiu de faixa quando alguém de fora comenta. A faixa é o que a
    rede efetivamente lê, e por isso é o que merece aviso.
    """
    anterior = {r["dimension"]: r["band"] for r in conn.query(
        "SELECT DISTINCT ON (dimension) dimension, band FROM reputation_snapshots"
        " WHERE org_id = $1 ORDER BY dimension, created_at DESC", org_id)}
    prof = profile(conn, org_id=org_id, viewer_org_id=org_id)
    ids = []
    mudancas = []
    for d in prof["dimensions"]:
        ids.append(conn.scalar(
            "SELECT app_record_reputation($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb,$10)",
            org_id, d["dimension"], d["value"], d["confidence"], d["band"], d["observations"],
            d["verified_observations"], d["self_declared_observations"],
            json.dumps({"inputs": d["inputs"], "how": d["how"]}), ENGINE_VERSION))
        antes = anterior.get(d["dimension"])
        if antes is not None and antes != d["band"]:
            mudancas.append({"dimension": d["dimension"], "from": antes, "to": d["band"]})
    for m in mudancas:
        notify.org_event(
            conn, event="Reputation.band_changed", org_id=org_id,
            title=f"Faixa de reputação alterada: {m['dimension']}",
            body=(f"De {m['from']} para {m['to']}. A faixa vem do que foi OBSERVADO e verificado; "
                  "nenhuma faixa é atribuída por decisão da plataforma, e a leitura corrente "
                  "continua sendo calculada, não armazenada."),
            link="/organizacao/reputacao", priority="high", min_role="admin",
            ref_type="reputation_dimension", action_label="Ver como foi calculada",
            payload=m, dedupe_parts=("Reputation.band_changed", org_id, m["dimension"],
                                     m["from"], m["to"]))
    return {"recorded": len(ids), "band_changes": mudancas, "engine_version": ENGINE_VERSION,
            "note": ("O snapshot não substitui a leitura: a reputação corrente continua sendo "
                     "CALCULADA. Ele existe para mostrar evolução e para que uma correção não "
                     "apague o que foi publicado antes dela.")}


def timeline(conn: Connection, *, org_id: str, dimension: str | None = None,
             limit: int = 120) -> dict:
    rows = conn.query(
        "SELECT dimension, value, confidence, band, observations, verified_observations,"
        " self_declared_observations, engine_version, created_at FROM reputation_snapshots"
        " WHERE org_id = $1 AND ($2::text IS NULL OR dimension = $2)"
        " ORDER BY created_at DESC, dimension LIMIT $3", org_id, dimension, limit)
    return {"items": rows,
            "note": ("Linha do tempo append-only: valor antigo não é reescrito quando o cálculo "
                     "muda. `engine_version` diz com qual motor cada ponto foi medido, porque "
                     "comparar pontos de motores diferentes é comparar coisas diferentes.")}


# ================================================================================================ contestação
def open_dispute(conn: Connection, *, org_id: str, dimension: str, what_is_contested: str,
                 expected_correction: str, evidence_id: str | None = None,
                 actor: str | None = None) -> dict:
    if not conn.one("SELECT 1 FROM reputation_dimensions WHERE code = $1 AND active", dimension):
        raise unprocessable("Dimensão de reputação desconhecida.", code="unknown_dimension")
    snap = conn.scalar("SELECT id FROM reputation_snapshots WHERE org_id = $1 AND dimension = $2"
                       " ORDER BY created_at DESC LIMIT 1", org_id, dimension)
    row = conn.one(
        "INSERT INTO reputation_disputes(org_id, dimension, snapshot_id, what_is_contested,"
        " expected_correction, evidence_id, opened_by) VALUES ($1,$2,$3,$4,$5,$6,$7)"
        " RETURNING id::text AS id, dimension, created_at",
        org_id, dimension, snap, what_is_contested.strip(), expected_correction.strip(),
        evidence_id, actor)
    return {**row, "status": "open",
            "note": ("A contestação aberta aparece NO PERFIL, ao lado da dimensão contestada, e "
                     "não numa fila interna: direito de contestar que ninguém vê não é direito.")}


def _open_disputes(conn: Connection, org_id: str) -> list[dict]:
    return conn.query(
        "SELECT d.id::text AS id, d.dimension, d.created_at, s.status"
        " FROM reputation_disputes d CROSS JOIN LATERAL dispute_status(d.id) s"
        " WHERE d.org_id = $1 AND s.status <> 'resolved' ORDER BY d.created_at DESC", org_id)


def disputes(conn: Connection, *, org_id: str | None = None, only_open: bool = False) -> dict:
    rows = conn.query(
        "SELECT d.id::text AS id, d.org_id::text AS org_id, d.dimension, d.what_is_contested,"
        " d.expected_correction, d.created_at, s.status, s.outcome, s.resolved_at,"
        " r.rationale, r.what_changed"
        " FROM reputation_disputes d CROSS JOIN LATERAL dispute_status(d.id) s"
        " LEFT JOIN reputation_dispute_resolutions r ON r.dispute_id = d.id"
        " WHERE ($1::uuid IS NULL OR d.org_id = $1)"
        "   AND (NOT $2::boolean OR s.status <> 'resolved')"
        " ORDER BY d.created_at DESC LIMIT 200", org_id, only_open)
    return {"items": rows}


def resolve_dispute(conn: Connection, *, dispute_id: str, outcome: str, rationale: str,
                    what_changed: str | None = None, actor: str | None = None) -> dict:
    d = conn.one("SELECT org_id::text AS org_id, dimension FROM reputation_disputes WHERE id = $1",
                 dispute_id)
    if not d:
        raise not_found("Contestação")
    if conn.one("SELECT 1 FROM reputation_dispute_resolutions WHERE dispute_id = $1", dispute_id):
        raise unprocessable("Esta contestação já foi resolvida, e a resolução é append-only.",
                            code="already_resolved")
    if outcome in ("corrected", "partially_corrected") and not what_changed:
        raise unprocessable(
            "Resolução que diz ter corrigido precisa dizer O QUE mudou no produto.",
            code="what_changed_required")
    row = conn.one(
        "INSERT INTO reputation_dispute_resolutions(dispute_id, outcome, rationale, what_changed,"
        " resolved_by) VALUES ($1,$2,$3,$4,$5) RETURNING id::text AS id, outcome, resolved_at",
        dispute_id, outcome, rationale.strip(), (what_changed or None), actor)
    if outcome in ("corrected", "partially_corrected"):
        # A correção não reescreve o passado: produz um ponto NOVO na linha do tempo.
        snapshot(conn, org_id=d["org_id"])
    return {**row, "org_id": d["org_id"], "dimension": d["dimension"],
            "note": ("Correção não reescreve snapshot antigo: registra ponto novo. O que foi "
                     "publicado antes da correção continua legível, e é assim que se prova que a "
                     "correção aconteceu.")}


def me(conn: Connection, *, org_id: str) -> dict:
    if not org_id:
        raise ApiError(409, "no_active_org", "Sem organização ativa.")
    return profile(conn, org_id=org_id, viewer_org_id=org_id)
