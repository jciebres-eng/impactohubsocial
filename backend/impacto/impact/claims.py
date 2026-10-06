"""Integridade de alegação: confronta o que o relatório AFIRMA com o que o banco SABE.

O PROBLEMA

Um relatório de impacto é feito de alegações — "atendemos 1.200 pessoas", "contribuímos para o ODS 4",
"reduzimos 30% do consumo de água", "nosso projeto é neutro em carbono". Cada frase pode ser
verdadeira, exagerada ou inventada, e nada no produto confrontava a frase com o registro.

AS TRÊS DECISÕES DE DESENHO

1. **A situação da alegação não é uma coluna.** `claim_status()` deriva da última rodada de
   verificação. Coluna de situação é escrevível, e no dia em que alguém precisar que a alegação
   apareça como comprovada, ela apareceria.
2. **O verificador não acusa fraude.** As regras devolvem `attention` ou `serious`. Alegação
   `serious` exige revisão humana de OUTRA organização, e a revisão não apaga a marca — qualifica
   (`flagged_accepted_by_review`). Classificar alguém como fraudador a partir de heurística de texto
   seria pior que o problema.
3. **É determinístico.** Nenhuma regra chama modelo de linguagem: são consultas SQL e léxico
   declarado neste arquivo. Resultado de verificação precisa ser reproduzível e contestável, e saída
   de modelo não é nem uma nem outra.
"""
from __future__ import annotations

import re
from typing import Any

from ..db.pq import Connection, IntegrityError, InsufficientPrivilege
from ..http import ApiError, not_found, unprocessable
from ..network import notify

ENGINE_VERSION = "claim-integrity@1.0.0"

#: Léxicos declarados em código, não em configuração: mudar o que a plataforma considera linguagem
#: absoluta é mudança de comportamento e tem de aparecer em revisão de código e em teste.
#: Afirmação de PROVA. Uma medição validada com evidência sustenta a frase.
ABSOLUTE_TERMS = (
    "comprovado", "comprovada", "comprovadamente", "garantido", "garantida", "garantimos",
    "definitivamente", "assegurado", "assegura", "infalível", "indiscutível", "inquestionável",
)
#: Afirmação de TOTALIDADE. É a única classe que se confere por divisão — medido sobre elegível —,
#: e por isso tem regra própria: medição validada não basta, precisa COBRIR o denominador.
#: A separação nasceu de um achado da jornada de ponta a ponta da v0.18.1: "erradicamos" passava
#: por `absolute_language` porque havia uma medição validada de 32 pessoas no projeto.
TOTALITY_TERMS = (
    "100%", "cem por cento", "zero caso", "zero casos", "nenhum caso", "sem nenhum",
    "neutro", "neutra", "neutralidade", "erradicou", "erradicamos", "erradicada", "erradicação",
    "eliminou totalmente", "totalmente eliminado", "nunca mais", "universalizou",
    "universalizamos", "universalização", "todas as pessoas", "toda a população",
    "todos os beneficiários", "integralmente atendida", "cobertura total",
)
CERTIFICATION_TERMS = (
    "certificado", "certificada", "certificação", "homologado", "homologada",
    "aprovado pelo governo", "aprovada pelo governo", "selo oficial", "credenciado pelo",
    "reconhecido oficialmente", "auditado por", "atestado oficial",
)
CAUSALITY_TERMS = (
    # As flexões de plural estão listadas porque o léxico é literal de propósito: casamento por
    # radical pegaria "gerenciamos" em "gerou", e verificação que erra por regra frouxa não serve
    # para contestar nem para defender.
    "gerou", "geraram", "gerando", "resultou em", "resultaram em", "provocou", "provocaram",
    "causou", "causaram", "foi responsável por", "foram responsáveis por", "em razão do projeto",
    "graças ao projeto", "por causa do projeto", "produziu o resultado", "levou a", "levaram a",
    "fez com que", "fizeram com que",
)
COMPARATIVE_TERMS = (
    "maior que", "mais que", "o maior", "a maior", "lidera", "líder", "melhor que",
    "mais eficiente que", "acima da média", "referência nacional", "o único",
)
#: Elos que NÃO sustentam afirmação de causalidade (a lista forte é `validated_causality`).
WEAK_LINKS = ("hypothesis", "correlation", "association", "inference")

SEVERITY_ORDER = {"info": 0, "attention": 1, "serious": 2}

STATUS_LABEL = {
    "unchecked": "não verificada",
    "substantiated": "sustentada pelo que está registrado",
    "attention": "pontos de atenção",
    "flagged": "marcada — exige revisão humana de outra organização",
    "flagged_accepted_by_review": "marcada e aceita em revisão, com a marca mantida",
    "needs_change": "revisão pediu alteração",
    "rejected_by_review": "recusada em revisão",
    "withdrawn": "retirada por quem a declarou",
}


# ================================================================================================ catálogo
def rules(conn: Connection) -> dict:
    rows = conn.query(
        "SELECT code, name_pt, severity, what_it_detects, why_it_matters, deterministic"
        " FROM claim_rules WHERE active ORDER BY"
        " CASE severity WHEN 'serious' THEN 0 WHEN 'attention' THEN 1 ELSE 2 END, name_pt")
    return {
        "items": rows,
        "lexicons": {
            "absolute": list(ABSOLUTE_TERMS),
            "totality": list(TOTALITY_TERMS),
            "certification": list(CERTIFICATION_TERMS),
            "causality": list(CAUSALITY_TERMS),
            "comparative": list(COMPARATIVE_TERMS),
        },
        "statuses": [{"key": k, "label": v} for k, v in STATUS_LABEL.items()],
        "note": ("Todas as regras são determinísticas: consulta ao banco e léxico declarado em "
                 "código. Nenhuma chama modelo de linguagem, porque verificação precisa ser "
                 "reproduzível para poder ser contestada. Os léxicos estão expostos aqui de "
                 "propósito — quem é marcado tem direito de saber por qual palavra."),
    }


# ================================================================================================ declaração
def declare(conn: Connection, *, org_id: str, subject_type: str, subject_id: str, claim_kind: str,
            statement: str, actor: str | None = None, scope_note: str | None = None,
            period_start: Any = None, period_end: Any = None, indicator_id: str | None = None,
            evidence_id: str | None = None) -> dict:
    _assert_subject(conn, subject_type=subject_type, subject_id=subject_id, org_id=org_id)
    row = conn.one(
        "INSERT INTO claims(org_id, subject_type, subject_id, claim_kind, statement, scope_note,"
        " period_start, period_end, indicator_id, evidence_id, declared_by)"
        " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)"
        " RETURNING id::text AS id, subject_type, subject_id::text AS subject_id, claim_kind,"
        " statement, created_at",
        org_id, subject_type, subject_id, claim_kind, statement.strip(), scope_note, period_start,
        period_end, indicator_id, evidence_id, actor)
    return {**row, "status": "unchecked", "status_label": STATUS_LABEL["unchecked"]}


def _assert_subject(conn: Connection, *, subject_type: str, subject_id: str, org_id: str) -> None:
    table, owner_col = {
        "project": ("projects", "org_id"),
        "program": ("programs", "owner_org_id"),   # programas usam owner_org_id, não org_id
        "organization": ("organizations", "id"),
        "solution": ("solutions", "org_id"),
        "impact_update": ("impact_updates", "org_id"),
    }[subject_type]
    row = conn.one(f"SELECT {owner_col}::text AS owner FROM {table} WHERE id = $1",  # noqa: S608
                   subject_id)
    # 404 e não 403 quando o sujeito é de outra organização: a RLS não devolve a linha, e dizer
    # "existe, mas não é seu" já seria informação sobre o que não se pode ver.
    if not row:
        raise ApiError(404, "not_found", "Sujeito da alegação não encontrado.")
    if row["owner"] != org_id:
        raise ApiError(403, "forbidden", "A alegação é declarada por quem é dono do sujeito dela.")


def withdraw(conn: Connection, *, claim_id: str, org_id: str, reason: str) -> dict:
    row = conn.one(
        "UPDATE claims SET withdrawn_at = now(), withdrawn_reason = $3"
        " WHERE id = $1 AND org_id = $2 AND withdrawn_at IS NULL"
        " RETURNING id::text AS id, withdrawn_at", claim_id, org_id, reason.strip())
    if not row:
        raise unprocessable("Alegação não encontrada ou já retirada.", code="not_withdrawable")
    return {**row, "status": "withdrawn"}


# ================================================================================================ fatos
def _facts(conn: Connection, claim: dict) -> dict:
    """Tudo o que o banco sabe sobre o sujeito. Uma consulta por fato, nenhuma inferência."""
    st, sid = claim["subject_type"], claim["subject_id"]
    f: dict[str, Any] = {"subject_type": st}
    if st == "project":
        f["ods"] = conn.scalar("SELECT count(*) FROM project_ods_targets WHERE project_id = $1", sid)
        f["indicators"] = conn.scalar("SELECT count(*) FROM project_indicators"
                                      " WHERE project_id = $1", sid)
        f["values_validated"] = conn.scalar(
            "SELECT count(*) FROM indicator_values WHERE project_id = $1"
            "   AND status = 'validated'", sid)
        f["values_with_evidence"] = conn.scalar(
            "SELECT count(*) FROM indicator_values WHERE project_id = $1"
            "   AND status = 'validated' AND evidence_id IS NOT NULL", sid)
        f["validated_numbers"] = [float(r["value"]) for r in conn.query(
            "SELECT value FROM indicator_values WHERE project_id = $1"
            "   AND status = 'validated'", sid)]
        f["edges"] = conn.query(
            "SELECT link_type, count(*) AS n FROM impact_edges WHERE project_id = $1"
            " GROUP BY link_type", sid)
        f["evidences"] = conn.scalar("SELECT count(*) FROM evidences WHERE project_id = $1"
                                     " AND status = 'accepted'", sid)
        f["expenses"] = conn.one(
            "SELECT count(*) AS total, count(*) FILTER (WHERE document_id IS NULL) AS no_receipt"
            " FROM expenses WHERE project_id = $1", sid)
        f["denominators"] = conn.scalar(
            "SELECT count(*) FROM equity_denominators WHERE effective_until IS NULL"
            "   AND ((scope = 'project' AND project_id = $1)"
            "     OR (scope = 'territory' AND territory ="
            "         (SELECT territory FROM projects WHERE id = $1)))", sid)
        # Para conferir TOTALIDADE: o menor denominador vigente (o mais exigente) e a maior
        # medição validada. A divisão de um pelo outro é a cobertura que a frase afirma ter.
        f["denominator_value"] = conn.scalar(
            "SELECT min(value)::float FROM equity_denominators WHERE effective_until IS NULL"
            "   AND kind IN ('eligible_population','target_population','affected_population')"
            "   AND ((scope = 'project' AND project_id = $1)"
            "     OR (scope = 'territory' AND territory ="
            "         (SELECT territory FROM projects WHERE id = $1)))", sid)
        f["max_validated"] = conn.scalar(
            "SELECT max(value)::float FROM indicator_values WHERE project_id = $1"
            "   AND status = 'validated'", sid)
        f["execution"] = conn.one("SELECT starts_on, ends_on FROM projects WHERE id = $1", sid)
    else:
        # Para os outros sujeitos a plataforma sabe menos, e o verificador diz isso em vez de
        # inventar uma base que não existe.
        f["ods"] = f["indicators"] = f["values_validated"] = f["values_with_evidence"] = 0
        f["validated_numbers"] = []
        f["edges"] = []
        f["evidences"] = conn.scalar("SELECT count(*) FROM evidences WHERE org_id = $1"
                                     "   AND status = 'accepted'", claim["org_id"])
        f["expenses"] = {"total": 0, "no_receipt": 0}
        f["denominator_value"] = None
        f["max_validated"] = None
        f["denominators"] = conn.scalar(
            "SELECT count(*) FROM equity_denominators WHERE effective_until IS NULL"
            "   AND org_id = $1", claim["org_id"])
        f["execution"] = None
    return f


def _hits(text: str, terms: tuple[str, ...]) -> list[str]:
    low = text.lower()
    return [t for t in terms if t in low]


_NUMBER = re.compile(r"\b\d{1,3}(?:[.\s]\d{3})+(?:,\d+)?\b|\b\d+(?:[.,]\d+)?\b")


def _numbers(text: str) -> list[float]:
    out: list[float] = []
    for raw in _NUMBER.findall(text):
        cleaned = raw.replace(" ", "").replace(".", "").replace(",", ".")
        try:
            out.append(float(cleaned))
        except ValueError:
            continue
    return out


# ================================================================================================ regras
def _run_rules(claim: dict, f: dict) -> list[dict]:
    text = claim["statement"]
    strong = any(e["link_type"] == "validated_causality" for e in f["edges"])
    weak = [e for e in f["edges"] if e["link_type"] in WEAK_LINKS]
    out: list[dict] = []

    def add(code: str, passed: bool, severity: str, detail: str) -> None:
        out.append({"rule_code": code, "passed": passed, "severity": severity, "detail": detail})

    add("ods_without_indicator", not (f["ods"] and not f["indicators"]), "attention",
        (f"o sujeito declara {f['ods']} vínculo(s) com ODS e não tem indicador vinculado"
         if f["ods"] and not f["indicators"] else
         "ODS declarado tem indicador vinculado, ou não há ODS declarado"))

    add("indicator_without_measurement", not (f["indicators"] and not f["values_validated"]),
        "attention",
        (f"há {f['indicators']} indicador(es) e nenhum valor validado"
         if f["indicators"] and not f["values_validated"] else
         f"{f['values_validated']} valor(es) validado(s) para {f['indicators']} indicador(es)"))

    sem_ev = f["values_validated"] - f["values_with_evidence"]
    add("measurement_without_evidence", sem_ev <= 0, "attention",
        (f"{sem_ev} medição(ões) validada(s) sem evidência anexada" if sem_ev > 0 else
         "toda medição validada aponta para evidência"))

    abs_hits = _hits(text, ABSOLUTE_TERMS)
    base_forte = f["values_with_evidence"] > 0
    add("absolute_language", not (abs_hits and not base_forte), "serious",
        (f"o texto usa termo absoluto ({', '.join(abs_hits[:4])}) e não há medição validada com "
         f"evidência no sujeito" if abs_hits and not base_forte else
         (f"termo absoluto presente ({', '.join(abs_hits[:4])}), e há medição validada com evidência"
          if abs_hits else "o texto não usa termo absoluto")))

    tot_hits = _hits(text, TOTALITY_TERMS)
    den, medido = f["denominator_value"], f["max_validated"]
    cobertura = (medido / den) if (den and medido is not None and den > 0) else None
    coberto = cobertura is not None and cobertura >= 0.99
    add("totality_claim_without_coverage", not (tot_hits and not coberto), "serious",
        (f"o texto afirma totalidade ({', '.join(tot_hits[:3])}) e "
         + ("não há denominador vigente com fonte para conferir" if not den else
            ("não há medição validada para dividir pelo denominador" if medido is None else
             f"a cobertura medida é {cobertura:.0%} de {den:g} elegíveis"))
         if tot_hits and not coberto else
         (f"afirmação de totalidade com cobertura medida de {cobertura:.0%}" if tot_hits else
          "o texto não afirma totalidade")))

    cert_hits = _hits(text, CERTIFICATION_TERMS)
    add("certification_language", not cert_hits, "serious",
        (f"o texto afirma certificação ou homologação ({', '.join(cert_hits[:4])}); a plataforma não "
         f"certifica nada e não é organismo certificador" if cert_hits else
         "o texto não afirma certificação"))

    caus_hits = _hits(text, CAUSALITY_TERMS)
    add("causality_from_weak_link", not (caus_hits and weak and not strong), "serious",
        (f"o texto afirma causalidade ({', '.join(caus_hits[:3])}) e a cadeia de resultado só tem "
         f"elo de {', '.join(sorted({e['link_type'] for e in weak}))}"
         if caus_hits and weak and not strong else
         ("afirmação de causalidade com elo de causalidade validada na cadeia"
          if caus_hits and strong else "o texto não afirma causalidade")))

    comp_hits = _hits(text, COMPARATIVE_TERMS)
    add("comparative_without_denominator", not (comp_hits and not f["denominators"]), "attention",
        (f"o texto compara ({', '.join(comp_hits[:3])}) e não há denominador declarado com fonte"
         if comp_hits and not f["denominators"] else
         ("comparação com denominador declarado disponível" if comp_hits else
          "o texto não faz comparação")))

    nums = [n for n in _numbers(text) if n >= 10]
    medidos = {round(v, 2) for v in f["validated_numbers"]}
    orfaos = [n for n in nums if round(n, 2) not in medidos]
    add("number_not_in_measurements", not (orfaos and f["values_validated"] > 0), "attention",
        (f"o texto traz {len(orfaos)} número(s) sem correspondência em valor validado "
         f"({', '.join(str(n) for n in orfaos[:4])})" if orfaos and f["values_validated"] > 0 else
         ("não há valor validado para confrontar os números do texto" if orfaos else
          "os números do texto correspondem a valores validados")))

    ex = f["execution"]
    fora = bool(ex and claim.get("period_start") and ex.get("starts_on")
                and claim["period_start"] < ex["starts_on"])
    add("period_outside_execution", not fora, "attention",
        ("o período declarado começa antes da execução do projeto" if fora else
         "o período declarado não contradiz a execução registrada"))

    sem_comp = f["expenses"]["no_receipt"] or 0
    financeira = claim["claim_kind"] == "financial" or "aplicad" in text.lower()
    add("financial_claim_without_receipt", not (financeira and sem_comp), "serious",
        (f"alegação financeira com {sem_comp} despesa(s) sem comprovante no cofre"
         if financeira and sem_comp else
         "não é alegação financeira, ou toda despesa tem comprovante"))

    nenhuma_base = not (f["indicators"] or f["evidences"] or f["edges"])
    add("no_basis_at_all", not nenhuma_base, "serious",
        ("o sujeito não tem indicador, evidência nem elo de cadeia de resultado" if nenhuma_base else
         "o sujeito tem ao menos uma base registrada"))
    return out


# ================================================================================================ verificação
def check(conn: Connection, *, claim_id: str) -> dict:
    claim = conn.one(
        "SELECT id::text AS id, org_id::text AS org_id, subject_type, subject_id::text AS"
        " subject_id, claim_kind, statement, period_start, period_end, withdrawn_at"
        " FROM claims WHERE id = $1", claim_id)
    if not claim:
        raise not_found("Alegação não encontrada")
    if claim["withdrawn_at"]:
        raise unprocessable("Alegação retirada não é verificada.", code="withdrawn")
    f = _facts(conn, claim)
    results = _run_rules(claim, f)
    round_n = (conn.scalar("SELECT coalesce(max(check_round), 0) FROM claim_checks"
                           " WHERE claim_id = $1", claim_id) or 0) + 1
    for r in results:
        conn.run(
            "INSERT INTO claim_checks(claim_id, check_round, rule_code, passed, severity, detail,"
            " engine_version) VALUES ($1,$2,$3,$4,$5,$6,$7)",
            claim_id, round_n, r["rule_code"], r["passed"], r["severity"], r["detail"],
            ENGINE_VERSION)
    return {**status(conn, claim_id=claim_id), "check_round": round_n,
            "checks": results, "facts_used": _public_facts(f),
            "engine_version": ENGINE_VERSION}


def _public_facts(f: dict) -> dict:
    return {
        "ods_links": f["ods"], "indicators": f["indicators"],
        "values_validated": f["values_validated"],
        "values_with_evidence": f["values_with_evidence"],
        "accepted_evidences": f["evidences"],
        "result_chain_links": {e["link_type"]: e["n"] for e in f["edges"]},
        "expenses_without_receipt": f["expenses"]["no_receipt"],
        "denominators_available": f["denominators"],
        "denominator_value": f["denominator_value"],
        "max_validated_value": f["max_validated"],
    }


def status(conn: Connection, *, claim_id: str) -> dict:
    row = conn.one("SELECT status, check_round, serious, attention, reviewed, review_decision"
                   " FROM claim_status($1)", claim_id)
    if not row:
        raise not_found("Alegação não encontrada")
    return {
        "claim_id": claim_id, **row,
        "status_label": STATUS_LABEL.get(row["status"], row["status"]),
        "note": ("A situação é DERIVADA da última rodada de verificação: não existe coluna de "
                 "situação em `claims`, justamente para que não haja o que falsificar. Alegação "
                 "`flagged` exige revisão humana de OUTRA organização, e a revisão não apaga a "
                 "marca — qualifica."),
    }


def get(conn: Connection, *, claim_id: str) -> dict:
    claim = conn.one(
        "SELECT id::text AS id, org_id::text AS org_id, subject_type,"
        " subject_id::text AS subject_id, claim_kind, statement, scope_note, period_start,"
        " period_end, indicator_id::text AS indicator_id, evidence_id::text AS evidence_id,"
        " withdrawn_at, withdrawn_reason, created_at FROM claims WHERE id = $1", claim_id)
    if not claim:
        raise not_found("Alegação não encontrada")
    st = status(conn, claim_id=claim_id)
    checks = conn.query(
        "SELECT check_round, rule_code, passed, severity, detail, engine_version, checked_at"
        " FROM claim_checks WHERE claim_id = $1 ORDER BY check_round DESC, rule_code", claim_id)
    reviews = conn.query(
        "SELECT check_round, decision, note, reviewer_org_id::text AS reviewer_org_id, reviewed_at"
        " FROM claim_reviews WHERE claim_id = $1 ORDER BY reviewed_at DESC", claim_id)
    return {**claim, **st, "checks": checks, "reviews": reviews}


def listing(conn: Connection, *, org_id: str | None = None, subject_type: str | None = None,
            subject_id: str | None = None, limit: int = 50, offset: int = 0) -> dict:
    rows = conn.query(
        "SELECT c.id::text AS id, c.subject_type, c.subject_id::text AS subject_id, c.claim_kind,"
        " c.statement, c.created_at, c.withdrawn_at, s.status, s.serious, s.attention,"
        " s.check_round FROM claims c"
        " CROSS JOIN LATERAL claim_status(c.id) s"
        " WHERE ($1::uuid IS NULL OR c.org_id = $1)"
        "   AND ($2::text IS NULL OR c.subject_type = $2)"
        "   AND ($3::uuid IS NULL OR c.subject_id = $3)"
        " ORDER BY c.created_at DESC LIMIT $4 OFFSET $5",
        org_id, subject_type, subject_id, limit, offset)
    return {"items": [{**r, "status_label": STATUS_LABEL.get(r["status"], r["status"])}
                      for r in rows]}


def request_review(conn: Connection, *, claim_id: str, org_id: str, reviewer_org_id: str,
                   note: str | None = None, actor: str | None = None) -> dict:
    """Convida uma organização nomeada a revisar a última rodada.

    O convite é o que abre a leitura: sem ele, alegação marcada não é visível fora de quem a
    declarou, e não existe revisão não solicitada (que seria canal para pressionar concorrente).
    """
    claim = conn.one("SELECT org_id::text AS org_id FROM claims WHERE id = $1", claim_id)
    if not claim:
        raise not_found("Alegação não encontrada")
    if claim["org_id"] != org_id:
        raise ApiError(403, "forbidden", "O convite para revisar parte de quem declarou a alegação.")
    round_n = _last_round(conn, claim_id)
    if not round_n:
        raise unprocessable("Alegação ainda não foi verificada: não há rodada para revisar.",
                            code="not_checked")
    try:
        row = conn.one(
            "INSERT INTO claim_review_requests(claim_id, check_round, requested_org_id, note,"
            " requested_by) VALUES ($1,$2,$3,$4,$5)"
            " ON CONFLICT (claim_id, check_round, requested_org_id) DO NOTHING"
            " RETURNING id::text AS id, check_round, created_at",
            claim_id, round_n, reviewer_org_id, (note or None), actor)
    except (IntegrityError, InsufficientPrivilege) as exc:
        raise ApiError(422, "claim_review_request_rule", str(exc).split("\n")[0][:400]) from exc
    if not row:
        raise unprocessable("Esta organização já foi convidada para esta rodada.",
                            code="already_requested")
    # v0.20.0: o convite abria a leitura e NÃO avisava a convidada. Ela só descobriria puxando a
    # própria fila — isto é, adivinhando que havia uma fila. Um convite que ninguém vê é um convite
    # que não foi feito.
    notify.org_event(
        conn, event="Claim.review_requested", org_id=reviewer_org_id,
        title="Convite para revisar uma afirmação de impacto",
        body=((note or "").strip()[:900]
              or "Uma organização pediu que você revise a última rodada de verificação."),
        link="/impacto/revisoes", priority="normal", min_role="member", actor_user_id=actor,
        ref_type="claim", ref_id=claim_id, action_label="Revisar",
        payload={"check_round": row["check_round"]}, dedupe_parts=("Claim.review_requested",
                                                                   claim_id, row["check_round"],
                                                                   reviewer_org_id))
    return {"claim_id": claim_id, "reviewer_org_id": reviewer_org_id, **row,
            "note": (f"O convite vale para a RODADA {round_n}. Verificar de novo abre uma rodada "
                     "nova, e a rodada nova precisa de convite próprio — pelo mesmo princípio que "
                     "faz assinatura não valer para versão nova de documento.")}


def review_requests(conn: Connection, *, org_id: str) -> dict:
    """Convites recebidos pela organização — a fila de revisão de quem é convidado."""
    rows = conn.query(
        "SELECT r.id::text AS id, r.claim_id::text AS claim_id, r.check_round, r.note,"
        " r.created_at, c.statement, c.claim_kind, c.subject_type, s.status, s.serious,"
        " s.attention, (SELECT count(*) FROM claim_reviews v WHERE v.claim_id = r.claim_id"
        "    AND v.check_round = r.check_round AND v.reviewer_org_id = $1) AS my_reviews"
        " FROM claim_review_requests r JOIN claims c ON c.id = r.claim_id"
        " CROSS JOIN LATERAL claim_status(c.id) s"
        " WHERE r.requested_org_id = $1 ORDER BY r.created_at DESC LIMIT 100", org_id)
    return {"items": [{**r, "status_label": STATUS_LABEL.get(r["status"], r["status"]),
                       "pending": r["my_reviews"] == 0} for r in rows]}


def _last_round(conn: Connection, claim_id: str) -> int:
    return conn.scalar("SELECT coalesce(max(check_round), 0) FROM claim_checks"
                       " WHERE claim_id = $1", claim_id) or 0


def review(conn: Connection, *, claim_id: str, reviewer_org_id: str, decision: str, note: str,
           reviewer_user_id: str | None = None) -> dict:
    round_n = conn.scalar(
        "SELECT coalesce(max(r.check_round), 0) FROM claim_review_requests r"
        " WHERE r.claim_id = $1 AND r.requested_org_id = $2", claim_id, reviewer_org_id) or 0
    if not round_n:
        raise unprocessable(
            "Não há convite para revisar esta alegação: a revisão é solicitada por quem a "
            "declarou, e o convite vale para uma rodada.", code="not_invited")
    try:
        conn.run(
            "INSERT INTO claim_reviews(claim_id, check_round, decision, note, reviewer_org_id,"
            " reviewer_user_id) VALUES ($1,$2,$3,$4,$5,$6)",
            claim_id, round_n, decision, note.strip(), reviewer_org_id, reviewer_user_id)
    except (IntegrityError, InsufficientPrivilege) as exc:
        raise ApiError(422, "claim_review_rule", str(exc).split("\n")[0][:400]) from exc
    return status(conn, claim_id=claim_id)
