"""Contexto de equidade: barreira declarada, denominador com fonte e normalização rotulada.

A FRASE QUE ESTE MÓDULO IMPLEMENTA

"Impacto não é quantidade. Impacto é resultado contextualizado." Um projeto que atende 50 pessoas num
território remoto não tem automaticamente menos impacto que um que atende 5.000 num centro urbano.

O QUE ESTE MÓDULO **NÃO** FAZ, E É A DECISÃO MAIS IMPORTANTE

Não existe nota de equidade. Os documentos desta rodada propõem
`IMPACTO = RESULTADO × CONTEXTO × NECESSIDADE × EQUIDADE × ADICIONALIDADE × EVIDÊNCIA` e eles próprios
mandam não implementar a fórmula literalmente. Não implementei, porque multiplicar seis fatores
estimados produz um número com aparência de precisão, sem significado, e que esconde quem escolheu os
pesos.

O que existe no lugar:

1. **contexto declarado com fonte** — necessidade, adicionalidade, cenário-base e barreiras, cada um
   com escada de prova (declarada → documentada → evidenciada) cobrada pelo banco;
2. **normalização rotulada** — por população elegível, por população de referência, por domicílio, por
   matrícula, por área, por unidade de serviço e por recurso aplicado, cada uma dizendo qual
   denominador usou, de que fonte e de que data;
3. **a trava**: sem denominador vigente declarado com fonte, o método devolve `unavailable` com o
   motivo. Nunca uma estimativa.
4. **comparação que se RECUSA** — `compare()` devolve `comparable: false` com os motivos quando falta
   base, em vez de ranquear com dado faltante. E, mesmo quando comparável, **não declara vencedor**.

O numerador é SEMPRE escolhido por quem pergunta — um indicador do projeto, cujos valores validados
são somados — ou, na falta dele, o número de beneficiários DECLARADO, e aí a resposta vem marcada como
declarada. O módulo não adivinha qual número significa "alcance".
"""
from __future__ import annotations

from typing import Any

from ..core import evidence as EV
from ..db.pq import Connection
from ..http import ApiError, not_found, unprocessable

ENGINE_VERSION = "equity-context@1.0.0"

#: Método de normalização → (tipo de denominador exigido, rótulo, escala de apresentação).
#: A escala existe para a leitura humana: "por 1.000 habitantes" é legível, "0,0032" não é.
METHODS: dict[str, dict[str, Any]] = {
    "per_eligible_population": {
        "denominator": "eligible_population", "scale": 1000,
        "label": "por 1.000 pessoas da população elegível declarada"},
    "per_reference_population": {
        "denominator": "reference_population", "scale": 1000,
        "label": "por 1.000 pessoas da população de referência do território"},
    "per_household": {
        "denominator": "households", "scale": 1000,
        "label": "por 1.000 domicílios"},
    "per_enrolled": {
        "denominator": "enrolled", "scale": 100,
        "label": "por 100 matrículas ou cadastros do serviço"},
    "per_area_km2": {
        "denominator": "area_km2", "scale": 1,
        "label": "por km² do território"},
    "per_service_unit": {
        "denominator": "service_units", "scale": 1,
        "label": "por unidade de serviço existente no território"},
    "per_resource": {
        "denominator": "resource_cents", "scale": 100_000,
        "label": "por R$ 1.000 aplicados"},
}

STANDINGS = ("declared", "documented", "evidenced")
STANDING_LABEL = {
    "declared": "declarada",
    "documented": "documentada (documento no cofre ou fonte citada com data)",
    "evidenced": "evidenciada (evidência registrada)",
}
DENOMINATOR_KINDS = ("eligible_population", "reference_population", "households", "enrolled",
                     "area_km2", "service_units", "resource_cents")

_NOTE = ("Número normalizado NÃO é número absoluto, e a plataforma não converte um no outro. Cada "
         "método diz qual denominador usou, de que fonte e de que data. Método sem denominador "
         "vigente declarado com fonte devolve 'indisponível' com o motivo — nunca uma estimativa.")


# ================================================================================================ catálogo
def catalog(conn: Connection) -> dict:
    rows = conn.query(
        "SELECT code, name_pt, dimension, description, source_note FROM equity_barrier_catalog"
        " WHERE active ORDER BY dimension, name_pt")
    return {
        "items": rows,
        "standings": [{"key": s, "label": STANDING_LABEL[s]} for s in STANDINGS],
        "denominator_kinds": list(DENOMINATOR_KINDS),
        "methods": [{"key": k, **v} for k, v in METHODS.items()],
        "note": ("A lista de barreiras é EDITORIAL da plataforma — a redação e o agrupamento são "
                 "nossos, não são classificação oficial de nenhum órgão, e cada linha carrega essa "
                 "ressalva. Barreira é atributo do contexto do projeto, nunca da pessoa atendida."),
    }


# ================================================================================================ contexto
def _project_org(conn: Connection, project_id: str) -> str:
    org = conn.scalar("SELECT org_id::text FROM projects WHERE id = $1", project_id)
    if not org:
        raise not_found("Projeto não encontrado")
    return org


def set_context(conn: Connection, *, project_id: str, org_id: str, actor: str | None,
                need_statement: str, additionality: str, counterfactual: str | None = None,
                additionality_standing: str = "declared",
                additionality_evidence_id: str | None = None,
                need_source_name: str | None = None, need_source_url: str | None = None,
                need_source_date: Any = None, context_note: str | None = None) -> dict:
    owner = _project_org(conn, project_id)
    if owner != org_id:
        raise ApiError(403, "forbidden", "O contexto é declarado pela organização dona do projeto.")
    row = conn.one(
        "INSERT INTO equity_contexts(project_id, org_id, need_statement, need_source_name,"
        " need_source_url, need_source_date, additionality, counterfactual,"
        " additionality_standing, additionality_evidence_id, context_note, updated_by)"
        " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)"
        " ON CONFLICT (project_id) DO UPDATE SET need_statement = excluded.need_statement,"
        " need_source_name = excluded.need_source_name, need_source_url = excluded.need_source_url,"
        " need_source_date = excluded.need_source_date, additionality = excluded.additionality,"
        " counterfactual = excluded.counterfactual,"
        " additionality_standing = excluded.additionality_standing,"
        " additionality_evidence_id = excluded.additionality_evidence_id,"
        " context_note = excluded.context_note, updated_by = excluded.updated_by"
        " RETURNING project_id::text AS project_id, need_statement, additionality, counterfactual,"
        " additionality_standing, need_source_name, need_source_date, updated_at",
        project_id, org_id, need_statement.strip(), need_source_name, need_source_url,
        need_source_date, additionality.strip(), (counterfactual or "").strip() or None,
        additionality_standing, additionality_evidence_id, context_note, actor)
    return {**row, "standing_label": STANDING_LABEL[row["additionality_standing"]]}


def context(conn: Connection, *, project_id: str) -> dict | None:
    row = conn.one(
        "SELECT project_id::text AS project_id, need_statement, need_source_name, need_source_url,"
        " need_source_date, additionality, counterfactual, additionality_standing,"
        " additionality_evidence_id::text AS additionality_evidence_id, context_note, updated_at"
        " FROM equity_contexts WHERE project_id = $1", project_id)
    if not row:
        return None
    return {**row, "standing_label": STANDING_LABEL[row["additionality_standing"]]}


# ================================================================================================ barreiras
def add_barrier(conn: Connection, *, project_id: str, org_id: str, actor: str | None,
                barrier_code: str, note: str, standing: str = "declared",
                source_name: str | None = None, source_url: str | None = None,
                source_date: Any = None, evidence_id: str | None = None,
                document_id: str | None = None) -> dict:
    owner = _project_org(conn, project_id)
    if owner != org_id:
        raise ApiError(403, "forbidden", "A barreira é declarada pela organização dona do projeto.")
    row = conn.one(
        "INSERT INTO project_barriers(project_id, org_id, barrier_code, standing, note,"
        " source_name, source_url, source_date, evidence_id, document_id, declared_by)"
        " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)"
        " ON CONFLICT (project_id, barrier_code) DO UPDATE SET standing = excluded.standing,"
        " note = excluded.note, source_name = excluded.source_name,"
        " source_url = excluded.source_url, source_date = excluded.source_date,"
        " evidence_id = excluded.evidence_id, document_id = excluded.document_id"
        " RETURNING id::text AS id, barrier_code, standing, note, source_name, source_date,"
        " evidence_id::text AS evidence_id, document_id::text AS document_id",
        project_id, org_id, barrier_code, standing, note.strip(), source_name, source_url,
        source_date, evidence_id, document_id, actor)
    return {**row, "standing_label": STANDING_LABEL[row["standing"]]}


def remove_barrier(conn: Connection, *, project_id: str, org_id: str, barrier_code: str) -> dict:
    n = conn.run("DELETE FROM project_barriers WHERE project_id = $1 AND org_id = $2"
                 " AND barrier_code = $3", project_id, org_id, barrier_code)
    if not n:
        raise not_found("Barreira não encontrada neste projeto")
    return {"removed": barrier_code}


def barriers(conn: Connection, *, project_id: str) -> list[dict]:
    return conn.query(
        "SELECT b.id::text AS id, b.barrier_code, c.name_pt, c.dimension, b.standing, b.note,"
        " b.source_name, b.source_url, b.source_date, b.evidence_id::text AS evidence_id,"
        " b.document_id::text AS document_id, b.created_at"
        " FROM project_barriers b JOIN equity_barrier_catalog c ON c.code = b.barrier_code"
        " WHERE b.project_id = $1 ORDER BY c.dimension, c.name_pt", project_id)


# ================================================================================================ denominador
def set_denominator(conn: Connection, *, scope: str, kind: str, value: float, unit: str,
                    reference_date: Any, source_name: str, source_date: Any, method_note: str,
                    project_id: str | None = None, program_id: str | None = None,
                    territory: str | None = None, org_id: str | None = None,
                    source_url: str | None = None, actor: str | None = None) -> dict:
    """Declara um denominador. Fonte, data de referência, data da fonte e método são obrigatórios.

    Versão nova fecha a vigência da anterior (gatilho `close_previous_denominator`), então o cálculo
    de ontem continua explicável pelo número de ontem.
    """
    if kind not in DENOMINATOR_KINDS:
        raise unprocessable(f"Tipo de denominador desconhecido: {kind}", code="unknown_denominator")
    row = conn.one(
        "INSERT INTO equity_denominators(scope, project_id, program_id, territory, org_id, kind,"
        " value, unit, reference_date, source_name, source_url, source_date, method_note,"
        " created_by) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)"
        " RETURNING id::text AS id, scope, kind, value, unit, reference_date, source_name,"
        " source_date, effective_from",
        scope, project_id, program_id, territory, org_id, kind, value, unit.strip(), reference_date,
        source_name.strip(), source_url, source_date, method_note.strip(), actor)
    return row


def denominators(conn: Connection, *, project_id: str | None = None, program_id: str | None = None,
                 territory: str | None = None, include_closed: bool = False) -> dict:
    rows = conn.query(
        "SELECT id::text AS id, scope, kind, value, unit, reference_date, source_name, source_url,"
        " source_date, method_note, effective_from, effective_until,"
        " project_id::text AS project_id, program_id::text AS program_id, territory"
        " FROM equity_denominators"
        " WHERE ($1::uuid IS NULL OR project_id = $1)"
        "   AND ($2::uuid IS NULL OR program_id = $2)"
        "   AND ($3::text IS NULL OR territory = $3)"
        "   AND ($4::bool OR effective_until IS NULL)"
        " ORDER BY kind, effective_from DESC",
        project_id, program_id, territory, include_closed)
    return {"items": rows, "note": ("Denominador é imutável: corrigir é declarar versão nova, que "
                                    "fecha a vigência da anterior.")}


def _current_denominators(conn: Connection, *, project_id: str, territory: str | None) -> dict:
    """Denominadores vigentes que valem para este projeto: os dele e os do território dele.

    O do projeto ganha do territorial quando os dois existem para o mesmo tipo: quem declarou o
    número do próprio projeto conhece melhor o próprio público.
    """
    rows = conn.query(
        "SELECT kind, value, unit, reference_date, source_name, source_url, source_date, scope,"
        " method_note FROM equity_denominators"
        " WHERE effective_until IS NULL"
        "   AND ((scope = 'project' AND project_id = $1)"
        "     OR (scope = 'territory' AND $2::text IS NOT NULL AND territory = $2))"
        " ORDER BY kind, CASE scope WHEN 'project' THEN 0 ELSE 1 END",
        project_id, territory)
    out: dict[str, dict] = {}
    for row in rows:
        out.setdefault(row["kind"], row)
    return out


# ================================================================================================ numerador
def _numerator(conn: Connection, *, project_id: str, indicator_id: str | None) -> dict:
    """O numerador é escolhido por quem pergunta, nunca adivinhado.

    Com `indicator_id`, soma os valores **validados** daquele indicador — validados, não reportados,
    porque reportado é o que a organização disse e validado é o que quem apoia conferiu. Sem
    `indicator_id`, usa o número de beneficiários DECLARADO no projeto, e a resposta diz isso.
    """
    if indicator_id:
        row = conn.one(
            "SELECT i.name, i.unit, i.code,"
            " coalesce(sum(v.value) FILTER (WHERE v.status = 'validated'), 0) AS validated,"
            " count(*) FILTER (WHERE v.status = 'validated') AS validated_count,"
            " coalesce(sum(v.value) FILTER (WHERE v.status = 'reported'), 0) AS reported,"
            " count(*) FILTER (WHERE v.status = 'reported') AS reported_count,"
            " count(*) FILTER (WHERE v.status = 'validated' AND v.evidence_id IS NOT NULL)"
            "   AS with_evidence, max(v.measured_on) AS last_measured"
            " FROM project_indicators pi JOIN indicator_catalog i ON i.id = pi.indicator_id"
            " LEFT JOIN indicator_values v ON v.project_indicator_id = pi.id"
            " WHERE pi.project_id = $1 AND pi.indicator_id = $2"
            " GROUP BY i.name, i.unit, i.code", project_id, indicator_id)
        if not row:
            raise not_found("Indicador não encontrado neste projeto")
        return {
            "basis": "validated", "indicator": row["name"], "indicator_code": row["code"],
            "unit": row["unit"], "value": float(row["validated"] or 0),
            "measurements": int(row["validated_count"] or 0),
            "with_evidence": int(row["with_evidence"] or 0),
            "reported_not_validated": float(row["reported"] or 0),
            "last_measured": row["last_measured"],
            "note": ("Soma dos valores VALIDADOS. O que está apenas reportado aparece à parte e não "
                     "entra na conta."),
        }
    row = conn.one("SELECT beneficiaries_count, title FROM projects WHERE id = $1", project_id)
    if not row:
        raise not_found("Projeto não encontrado")
    return {
        "basis": "declared", "indicator": "beneficiários declarados no projeto",
        "indicator_code": None, "unit": "pessoas",
        "value": float(row["beneficiaries_count"] or 0), "measurements": 0, "with_evidence": 0,
        "reported_not_validated": 0.0, "last_measured": None,
        "note": ("Número DECLARADO pela organização, sem medição validada. Serve para dimensionar a "
                 "intenção do projeto, não para afirmar resultado."),
    }


# ================================================================================================ normalização
def normalize(conn: Connection, *, project_id: str, indicator_id: str | None = None) -> dict:
    territory = conn.scalar("SELECT territory FROM projects WHERE id = $1", project_id)
    num = _numerator(conn, project_id=project_id, indicator_id=indicator_id)
    dens = _current_denominators(conn, project_id=project_id, territory=territory)
    out: dict[str, dict] = {}
    for method, spec in METHODS.items():
        den = dens.get(spec["denominator"])
        if not den:
            out[method] = {
                "available": False,
                "reason": (f"nenhum denominador vigente do tipo '{spec['denominator']}' foi "
                           f"declarado com fonte para este projeto nem para o território"),
                "label": spec["label"],
            }
            continue
        denom = float(den["value"])
        out[method] = {
            "available": True,
            "label": spec["label"],
            "basis": num["basis"],
            "numerator": num["value"],
            "numerator_unit": num["unit"],
            "denominator_kind": den["kind"],
            "denominator_value": denom,
            "denominator_unit": den["unit"],
            "denominator_scope": den["scope"],
            "value": round(num["value"] / denom * spec["scale"], 4),
            "scale": spec["scale"],
            "source_name": den["source_name"],
            "source_url": den.get("source_url"),
            "source_date": den["source_date"],
            "reference_date": den["reference_date"],
        }
    return {
        "project_id": project_id, "territory": territory, "numerator": num,
        "methods": out,
        "available": [m for m, v in out.items() if v["available"]],
        "unavailable": [m for m, v in out.items() if not v["available"]],
        "engine_version": ENGINE_VERSION,
        "note": _NOTE,
    }


# ================================================================================================ retrato
def _confidence(conn: Connection, *, project_id: str, ctx: dict | None, bars: list[dict],
                dens: dict, num: dict) -> tuple[float | None, str, dict]:
    """Confiança pela régua que já existe (`core/evidence.py`), não por régua nova.

    O que entra: a necessidade tem fonte? a adicionalidade subiu da declaração? as barreiras têm
    documento ou evidência? há denominador com fonte? o numerador é validado?
    """
    es = EV.EvidenceSet()
    es.add(EV.Evidence(
        key="equity.need", kind="need",
        source=(EV.Source.OFFICIAL_CATALOG if (ctx or {}).get("need_source_name")
                else EV.Source.DECLARED if ctx else EV.Source.ABSENT),
        value=(ctx or {}).get("need_statement"),
        observed_at=(ctx or {}).get("need_source_date")))
    add_standing = (ctx or {}).get("additionality_standing")
    es.add(EV.Evidence(
        key="equity.additionality", kind="diagnosis",
        source=(EV.Source.VALIDATED_MEASUREMENT if add_standing == "evidenced"
                else EV.Source.VERIFIED_DOCUMENT if add_standing == "documented"
                else EV.Source.DECLARED if ctx else EV.Source.ABSENT),
        value=(ctx or {}).get("additionality")))
    best = "declared" if bars else None
    for b in bars:
        if b["standing"] == "evidenced":
            best = "evidenced"
        elif b["standing"] == "documented" and best != "evidenced":
            best = "documented"
    es.add(EV.Evidence(
        key="equity.barriers", kind="project_activity",
        source=(EV.Source.VALIDATED_MEASUREMENT if best == "evidenced"
                else EV.Source.VERIFIED_DOCUMENT if best == "documented"
                else EV.Source.DECLARED if best else EV.Source.ABSENT),
        value=len(bars) or None))
    es.add(EV.Evidence(
        key="equity.denominator", kind="indicator",
        source=EV.Source.OFFICIAL_CATALOG if dens else EV.Source.ABSENT,
        value=sorted(dens) or None,
        observed_at=min((d["source_date"] for d in dens.values()), default=None)))
    es.add(EV.Evidence(
        key="equity.numerator", kind="indicator",
        source=(EV.Source.VALIDATED_MEASUREMENT if num["basis"] == "validated" and num["value"]
                else EV.Source.DECLARED if num["value"] else EV.Source.ABSENT),
        value=num["value"] or None, observed_at=num.get("last_measured")))
    summary = es.summary()
    # `EvidenceSet.confidence()` é POR CHAVE; a confiança do conjunto é a média das presentes, que o
    # próprio `summary()` calcula (em 0–100). Reaproveitar a régua existente em vez de criar outra é
    # o ponto: a banda sai de `core.evidence.band()`, a mesma que o diagnóstico usa.
    # `band()` recebe a confiança em 0–100 (é a escala que o diagnóstico usa); a coluna do banco
    # guarda em 0–1. Converter num lugar só evita o erro de passar a escala errada.
    pct = summary["mean_confidence"]
    return pct / 100.0, str(EV.band(pct, summary["known"], summary["total"])), summary


def assess(conn: Connection, *, project_id: str, org_id: str, actor: str | None = None,
           indicator_id: str | None = None) -> dict:
    """Grava o retrato append-only do contexto de equidade. NÃO devolve nota."""
    owner = _project_org(conn, project_id)
    if owner != org_id:
        raise ApiError(403, "forbidden", "O retrato é gravado pela organização dona do projeto.")
    ctx = context(conn, project_id=project_id)
    bars = barriers(conn, project_id=project_id)
    territory = conn.scalar("SELECT territory FROM projects WHERE id = $1", project_id)
    dens = _current_denominators(conn, project_id=project_id, territory=territory)
    norm = normalize(conn, project_id=project_id, indicator_id=indicator_id)
    conf, band, summary = _confidence(conn, project_id=project_id, ctx=ctx, bars=bars, dens=dens,
                                      num=norm["numerator"])
    declared = {
        "need": bool(ctx), "need_has_source": bool((ctx or {}).get("need_source_name")),
        "additionality_standing": (ctx or {}).get("additionality_standing"),
        "has_counterfactual": bool((ctx or {}).get("counterfactual")),
        "territory": territory,
        "numerator_basis": norm["numerator"]["basis"],
    }
    row = conn.one(
        "INSERT INTO equity_assessments(project_id, org_id, engine_version, barriers_total,"
        " barriers_documented, barriers_evidenced, methods_available, normalization, declared,"
        " evidence_confidence, confidence_band, detail, computed_by)"
        " VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9::jsonb,$10,$11,$12::jsonb,$13)"
        " RETURNING id::text AS id, computed_at",
        project_id, org_id, ENGINE_VERSION, len(bars),
        sum(1 for b in bars if b["standing"] in ("documented", "evidenced")),
        sum(1 for b in bars if b["standing"] == "evidenced"),
        norm["available"], _json(norm["methods"]), _json(declared),
        round(conf, 3) if conf is not None else None, band,
        _json({"evidence": summary, "denominators": sorted(dens)}), actor)
    return {
        "id": row["id"], "computed_at": row["computed_at"], "engine_version": ENGINE_VERSION,
        "context": ctx, "barriers": bars, "normalization": norm,
        "confidence": round(conf, 3) if conf is not None else None, "confidence_band": band,
        "evidence": summary,
        "score": None,
        "note": ("Não há nota de equidade, de propósito: multiplicar fatores estimados produz número "
                 "com aparência de precisão e esconde quem escolheu os pesos. O que existe é o "
                 "contexto declarado com fonte e a normalização rotulada. " + _NOTE),
    }


def history(conn: Connection, *, project_id: str, limit: int = 24) -> dict:
    return {"items": conn.query(
        "SELECT id::text AS id, engine_version, barriers_total, barriers_documented,"
        " barriers_evidenced, methods_available, evidence_confidence, confidence_band, computed_at"
        " FROM equity_assessments WHERE project_id = $1 ORDER BY computed_at DESC LIMIT $2",
        project_id, limit)}


# ================================================================================================ comparação
def compare(conn: Connection, *, project_ids: list[str], indicator_code: str | None = None) -> dict:
    """Compara contextos — e se RECUSA quando não há base.

    É o teste que os documentos desta rodada pedem: projeto com 5.000 beneficiários contra projeto
    com 120 em território remoto. A resposta certa não é "contextualizar e ranquear": é dizer que
    **não são comparáveis** quando faltam os denominadores e a medição validada. Ranquear com dado
    faltante é exatamente o erro que a contextualização deveria evitar.

    Mesmo quando comparável, esta função **não declara vencedor**. Ela mostra os números lado a lado,
    com o denominador e a fonte de cada um, e avisa quando as fontes são diferentes.
    """
    if len(project_ids) < 2:
        raise unprocessable("Comparar exige dois projetos ou mais.", code="need_two_projects")
    sides: list[dict] = []
    for pid in project_ids:
        row = conn.one("SELECT title, territory FROM projects WHERE id = $1", pid)
        if not row:
            raise not_found("Projeto não encontrado")
        ind = None
        if indicator_code:
            ind = conn.scalar(
                "SELECT pi.indicator_id::text FROM project_indicators pi"
                " JOIN indicator_catalog i ON i.id = pi.indicator_id"
                " WHERE pi.project_id = $1 AND i.code = $2", pid, indicator_code)
        norm = normalize(conn, project_id=pid, indicator_id=ind)
        sides.append({
            "project_id": pid, "title": row["title"], "territory": row["territory"],
            "context": context(conn, project_id=pid),
            "barriers": barriers(conn, project_id=pid),
            "normalization": norm,
            "has_indicator": bool(ind),
        })

    reasons: list[str] = []
    common = set(sides[0]["normalization"]["available"])
    for s in sides[1:]:
        common &= set(s["normalization"]["available"])
    if not common:
        reasons.append("não há método de normalização disponível para TODOS os projetos: falta "
                       "denominador declarado com fonte em pelo menos um deles")
    declared_only = [s["project_id"] for s in sides
                     if s["normalization"]["numerator"]["basis"] != "validated"]
    if declared_only:
        reasons.append("pelo menos um projeto tem apenas número DECLARADO, sem medição validada: "
                       "comparar declaração com medição validada compara coisas diferentes")
    if indicator_code and any(not s["has_indicator"] for s in sides):
        reasons.append(f"o indicador '{indicator_code}' não está em todos os projetos comparados")

    comparison: dict[str, Any] = {}
    source_warning: list[str] = []
    for method in sorted(common):
        entries = []
        for s in sides:
            m = s["normalization"]["methods"][method]
            entries.append({"project_id": s["project_id"], "title": s["title"],
                            "value": m["value"], "label": m["label"],
                            "denominator_value": m["denominator_value"],
                            "source_name": m["source_name"], "source_date": m["source_date"]})
        comparison[method] = entries
        if len({e["source_name"] for e in entries}) > 1:
            source_warning.append(method)

    return {
        "sides": sides,
        "comparable": not reasons,
        "reasons": reasons,
        "common_methods": sorted(common),
        "comparison": comparison,
        "different_sources": source_warning,
        "verdict": None,
        "note": ("A plataforma NÃO declara qual projeto tem mais impacto. Escala absoluta não é "
                 "impacto: 50 pessoas atendidas num território remoto não são menos que 5.000 num "
                 "centro urbano com infraestrutura. O que esta resposta entrega são os números lado "
                 "a lado, o denominador e a fonte de cada um, as barreiras declaradas de cada "
                 "projeto e os motivos pelos quais a comparação pode não se sustentar. A decisão é "
                 "de quem lê."
                 + (" Atenção: em "
                    + ", ".join(source_warning)
                    + " os denominadores vêm de FONTES DIFERENTES, então a razão entre eles carrega "
                      "a diferença de método das duas fontes." if source_warning else "")),
    }


def _json(value: Any) -> str:
    import json
    return json.dumps(value, default=str, ensure_ascii=False)
