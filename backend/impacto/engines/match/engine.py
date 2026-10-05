"""Match Engine explicável (match-engine@1.0.0).

Duas direções sobre o mesmo núcleo:
* ``funder_project`` — empresa/instituto avalia um projeto de OSC (feed de projetos).
* ``osc_call``       — OSC avalia uma chamada/edital/fundo (banco de oportunidades).

Saídas SEPARADAS (nunca fundidas num número só):
1. elegibilidade determinística (eligible | needs_review | blocked) — hard blockers e requisitos;
2. compatibilidade 0–100 calculada SÓ sobre sinais com dados (``score``) ou None se a confiança for baixa;
3. confiança 0–100 = peso dos sinais com dados / peso total;
4. estado recomendado + por que combina, por que não, riscos, dados ausentes e próxima ação.

Invariantes (testadas):
* entradas passam por extratores com lista branca de campos — plano, voucher, pagamento e atributos
  sensíveis NÃO entram no cálculo (ADR-008);
* este pacote não importa billing/entitlements (teste de dependência por AST);
* determinístico: mesmas entradas + mesmas versões ⇒ mesmo resultado (exceto ``computed_at``).
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date, datetime, UTC
from pathlib import Path
from typing import Any

from ...core.evidence import Evidence, EvidenceSet, Source, band
from .territory import covers, specificity

ENGINE_VERSION = "match-engine@1.2.0"
# Regras de elegibilidade e taxonomia versionadas SEPARADAMENTE dos pesos: um resultado antigo nunca muda de
# significado quando a régua muda. As quatro versões viajam com o resultado e ficam gravadas em match_runs.
RULES_VERSION = "match-rules@1.1"
_CONFIG = Path(__file__).resolve().parents[4] / "config" / "match_weights.json"
DEFAULT_WEIGHTS: dict = json.loads(_CONFIG.read_text(encoding="utf-8"))
_TAX = json.loads((_CONFIG.parent / "taxonomy.json").read_text(encoding="utf-8"))
TAXONOMY_VERSION = _TAX.get("version", "taxonomy@unknown")


def _doc_label(code: str) -> str:
    return (_TAX["document_types"].get(code) or {}).get("label", code)


def _cert_label(code: str) -> str:
    return _TAX["certifications"].get(code, code)

LIVE_DOC_STATUSES = {"clean"}
DD_STATES = ("approved", "committed", "in_execution", "reporting", "closed")

SIGNAL_LABELS = {
    "cause": "Causa", "territory": "Território", "budget": "Orçamento / ticket", "ods_esg": "ODS e ESG", "ods": "ODS",
    "capacity": "Capacidade e documentação", "evidence_history": "Histórico de execução e evidências", "impact": "Impacto esperado",
    "urgency": "Urgência", "preference": "Preferências do financiador", "readiness": "Prontidão para candidatura",
    "deadline": "Prazo disponível", "history": "Histórico da organização",
}


# ------------------------------------------------------------------------------------------------
# Extratores com lista branca (garantem a invariante de entradas permitidas)
# ------------------------------------------------------------------------------------------------
def _pick(d: dict | None, keys: tuple[str, ...]) -> dict:
    d = d or {}
    return {k: d.get(k) for k in keys}


ORG_FIELDS = ("id", "kind", "founded_on", "territories", "causes", "ods", "certifications", "team_size",
              "compliance_status", "uf", "ibge_code", "legal_nature")
PROJECT_FIELDS = ("id", "org_id", "title", "causes", "ods", "esg_tags", "territory", "beneficiaries_count", "budget_total_cents",
                  "status", "visibility", "urgency", "ends_on", "indicators", "milestones", "funded_cents")
CALL_FIELDS = ("id", "status", "opens_at", "closes_at", "causes", "ods", "territories", "eligible_org_types", "ticket_min_cents",
               "ticket_max_cents", "budget_total_cents", "required_document_types", "required_certifications",
               "min_org_age_months", "counterpart_pct", "requirements", "weights", "criteria_version", "sphere")
FUNDER_FIELDS = ("causes", "ods", "esg_focus", "territories", "excluded_causes", "excluded_territories", "ticket_min_cents",
                 "ticket_max_cents", "required_document_types", "min_org_age_months", "accepts_fractioning")
DOC_FIELDS = ("doc_type", "status", "valid_until")
HISTORY_FIELDS = ("completed_projects", "evidences_total", "evidences_accepted", "expenses_validated", "expenses_questioned")
BEHAVIOR_FIELDS = ("saved_causes", "dismissed_causes")
INST_FIELDS = ("code", "label", "status", "detail", "mandatory", "how_to_fix", "source_citation")


@dataclass
class MatchInput:
    direction: str
    org: dict                      # OSC avaliada (funder_project) ou OSC que avalia (osc_call)
    project: dict | None = None
    call: dict | None = None
    funder: dict | None = None
    documents: list[dict] | None = None
    history: dict | None = None
    behavior: dict | None = None
    conflict: bool = False
    today: date | None = None
    inst: list[dict] | None = None   # requisitos institucionais já avaliados (camada institucional); sem plano/voucher

    @classmethod
    def build(cls, direction: str, **raw: Any) -> MatchInput:
        """Único ponto de entrada: descarta qualquer campo fora da lista branca."""
        proj = _pick(raw.get("project"), PROJECT_FIELDS) if raw.get("project") else None
        if proj and proj.get("milestones"):
            proj["milestones"] = [_pick(m, ("amount_cents", "funded_cents", "status")) for m in proj["milestones"]]
        return cls(
            direction=direction,
            org=_pick(raw.get("org"), ORG_FIELDS),
            project=proj,
            call=_pick(raw.get("call"), CALL_FIELDS) if raw.get("call") else None,
            funder=_pick(raw.get("funder"), FUNDER_FIELDS) if raw.get("funder") else None,
            documents=[_pick(d, DOC_FIELDS) for d in (raw.get("documents") or [])],
            history=_pick(raw.get("history"), HISTORY_FIELDS) if raw.get("history") else None,
            behavior=_pick(raw.get("behavior"), BEHAVIOR_FIELDS) if raw.get("behavior") else None,
            conflict=bool(raw.get("conflict", False)),
            today=raw.get("today"),
            inst=[_pick(r, INST_FIELDS) for r in (raw.get("inst") or [])] or None,
        )


# ------------------------------------------------------------------------------------------------
# Utilitários
# ------------------------------------------------------------------------------------------------
def _today(mi: MatchInput) -> date:
    return mi.today or datetime.now(UTC).date()


def _as_date(v) -> date | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return datetime.fromisoformat(str(v)).date()
    except ValueError:
        return None


def _overlap(a, b) -> float | None:
    a, b = set(a or []), set(b or [])
    if not a or not b:
        return None
    return len(a & b) / len(b) if b else 0.0


def _months_between(d0: date, d1: date) -> int:
    return (d1.year - d0.year) * 12 + (d1.month - d0.month) - (1 if d1.day < d0.day else 0)


def _br(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def _money(c: int | None) -> str:
    if c is None:
        return "—"
    s = f"{c / 100:,.2f}"
    return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")


def _live_docs(mi: MatchInput, at: date) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for d in mi.documents or []:
        if d["status"] not in LIVE_DOC_STATUSES:
            continue
        vu = _as_date(d.get("valid_until"))
        if vu is not None and vu < at:
            continue
        cur = out.get(d["doc_type"])
        if cur is None or (_as_date(cur.get("valid_until")) or date.max) < (vu or date.max):
            out[d["doc_type"]] = d
    return out


def _remaining_need(project: dict) -> int | None:
    total = project.get("budget_total_cents")
    if total is None:
        return None
    return max(0, int(total) - int(project.get("funded_cents") or 0))


def _ticket_fit(project: dict, tmin: int | None, tmax: int | None, fractioning: bool = True) -> tuple[float | None, str, bool]:
    """(nota 0–1, explicação, há alguma forma de caber?). Considera fracionamento em marcos."""
    need = _remaining_need(project)
    if need is None or need == 0:
        return None, "Projeto sem necessidade de recursos informada", True
    candidates = [("projeto inteiro", need)]
    if fractioning:
        for i, m in enumerate(project.get("milestones") or []):
            rem = max(0, int(m["amount_cents"]) - int(m.get("funded_cents") or 0))
            if rem > 0:
                candidates.append((f"marco {i + 1}", rem))
    if tmin is None and tmax is None:
        return 0.6, f"Necessidade de {_money(need)}; financiador sem faixa de ticket definida", True
    lo, hi = tmin or 0, tmax or math.inf
    fits = [(label, v) for label, v in candidates if lo <= v <= hi]
    if fits:
        label, v = fits[0]  # o projeto inteiro vem primeiro; senão, o primeiro marco que cabe
        whole = label == "projeto inteiro"
        return (1.0 if whole else 0.8), f"{label.capitalize()} ({_money(v)}) cabe na faixa {_money(tmin)}–{_money(tmax)}", True
    closest = min(candidates, key=lambda x: min(abs(x[1] - lo), abs(x[1] - hi) if hi != math.inf else math.inf))
    return 0.0, f"Nenhuma parcela cabe na faixa {_money(tmin)}–{_money(tmax)} (mais próxima: {closest[0]} {_money(closest[1])})", False


@dataclass
class Signal:
    key: str
    weight: float
    value: float | None
    detail: str
    # Evidência que sustenta o sinal. Quando presente, o resultado mostra DE ONDE veio o dado, se foi VERIFICADO e
    # quão FRESCO é. Sem isso, "a organização declarou" e "a equipe conferiu" entrariam no motor como o mesmo número.
    evidence: Evidence | None = None

    def as_dict(self) -> dict:
        out = {"key": self.key, "label": SIGNAL_LABELS.get(self.key, self.key), "weight": self.weight,
               "value": None if self.value is None else round(self.value, 4),
               "contribution": None if self.value is None else round(self.weight * self.value, 4), "detail": self.detail}
        if self.evidence is not None:
            ed = self.evidence.as_dict()
            out["evidence"] = {"source": ed["source"], "verified": ed["verified"], "observed_at": ed["observed_at"],
                               "expires_at": ed["expires_at"], "freshness": ed["freshness"],
                               "confidence": ed["confidence"], "reference": ed["reference"]}
        return out


def _weights_for(direction: str, override: dict | None) -> tuple[dict, str]:
    base = dict(DEFAULT_WEIGHTS[direction])
    version = DEFAULT_WEIGHTS["version"]
    if override:
        clean = {k: float(v) for k, v in override.items() if k in base and isinstance(v, (int, float)) and v >= 0}
        if clean:
            base.update(clean)
            version = version + "+custom:" + ",".join(f"{k}={clean[k]:g}" for k in sorted(clean))
    return base, version


# ------------------------------------------------------------------------------------------------
# Direção 1: OSC avalia chamada / edital / fundo
# ------------------------------------------------------------------------------------------------
def evaluate_osc_call(mi: MatchInput) -> dict:
    call, org, project = mi.call or {}, mi.org, mi.project
    today = _today(mi)
    weights, wver = _weights_for("osc_call", call.get("weights"))
    reqs: list[dict] = []
    risks: list[dict] = []
    missing: list[dict] = []

    def req(code, label, status, detail, mandatory=True, how=None):
        reqs.append({"code": code, "label": label, "status": status, "detail": detail, "mandatory": mandatory, "how_to_fix": how})

    # -- Requisitos determinísticos --------------------------------------------------------
    closes = _as_date(call.get("closes_at"))
    opens = _as_date(call.get("opens_at"))
    if call.get("status") != "open":
        req("call_open", "Chamada aberta", "unmet", "A chamada não está aberta", how="Acompanhe a próxima edição (salve uma busca)")
    elif closes and closes < today:
        req("call_open", "Chamada aberta", "unmet", f"Inscrições encerradas em {_br(closes)}")
    elif opens and opens > today:
        req("call_open", "Chamada aberta", "unknown", f"Inscrições abrem em {_br(opens)}", mandatory=False,
            how="Prepare a documentação antes da abertura")
    else:
        req("call_open", "Chamada aberta", "met", f"Aberta{f' até {_br(closes)}' if closes else ''}")

    types = call.get("eligible_org_types") or ["osc"]
    req("org_type", "Tipo de organização elegível", "met" if org.get("kind") in types else "unmet",
        f"Aceita: {', '.join(types)}", how="Verifique se sua natureza jurídica é aceita pelo edital")

    if org.get("compliance_status") in ("rejected", "suspended"):
        req("compliance", "Cadastro regular na plataforma", "unmet", "Cadastro com pendência de compliance",
            how="Fale com a administração da plataforma")
    elif org.get("compliance_status") != "approved":
        req("compliance", "Cadastro regular na plataforma", "unknown", "Compliance ainda não concluído", mandatory=False,
            how="Envie documentos e solicite a análise de compliance")
        risks.append({"code": "COMPLIANCE_PENDING", "severity": "medium", "message": "Compliance da OSC ainda não aprovado"})
    else:
        req("compliance", "Cadastro regular na plataforma", "met", "Compliance aprovado")

    terr_target = (project or {}).get("territory") or (f"BR-{org['uf']}-{org['ibge_code']}" if org.get("uf") and org.get("ibge_code")
                                                        else (f"BR-{org['uf']}" if org.get("uf") else None))
    call_terrs = call.get("territories") or []
    if not call_terrs:
        req("territory", "Território de atuação", "met", "Sem restrição territorial")
    elif not terr_target:
        req("territory", "Território de atuação", "unknown", "Informe o município/UF de atuação",
            how="Complete o perfil (UF e código IBGE) ou vincule um projeto")
        missing.append({"field": "territory", "label": "Território de execução", "owner": "osc"})
    else:
        ok = any(covers(t, terr_target) for t in call_terrs)
        req("territory", "Território de atuação", "met" if ok else "unmet",
            f"Execução em {terr_target}; edital aceita {', '.join(call_terrs)}")

    min_age = call.get("min_org_age_months")
    if min_age:
        founded = _as_date(org.get("founded_on"))
        if not founded:
            req("org_age", f"Tempo mínimo de existência ({min_age} meses)", "unknown", "Data de fundação não informada",
                how="Informe a data de fundação no perfil (conforme cartão CNPJ)")
            missing.append({"field": "founded_on", "label": "Data de fundação", "owner": "osc"})
        else:
            age = _months_between(founded, today)
            req("org_age", f"Tempo mínimo de existência ({min_age} meses)", "met" if age >= min_age else "unmet",
                f"Organização com {age} meses")

    live = _live_docs(mi, today)
    for dt in call.get("required_document_types") or []:
        d = live.get(dt)
        if d:
            vu = _as_date(d.get("valid_until"))
            req(f"doc:{dt}", f"Documento: {_doc_label(dt)}", "met", f"Válido{f' até {_br(vu)}' if vu else ''}")
            if vu and closes and vu < closes:
                risks.append({"code": "DOC_EXPIRES_BEFORE_DEADLINE", "severity": "medium",
                              "message": f"{_doc_label(dt)} vence ({_br(vu)}) antes do fim das inscrições"})
        else:
            req(f"doc:{dt}", f"Documento: {_doc_label(dt)}", "unmet", "Ausente, vencido ou não verificado (antivírus)",
                how="Envie o documento atualizado no cofre de documentos")

    certs = set(org.get("certifications") or [])
    for c in call.get("required_certifications") or []:
        req(f"cert:{c}", f"Certificação: {_cert_label(c)}", "met" if c in certs else "unmet",
            "Qualificação verificada pela plataforma" if c in certs else "Não comprovada (declaração sem verificação não basta)",
            how="Registre a qualificação em Instituição e anexe o comprovante para verificação")

    if call.get("counterpart_pct"):
        req("counterpart", f"Contrapartida de {call['counterpart_pct']}%", "unknown",
            "Confirme a capacidade de contrapartida", mandatory=True, how="Registre a contrapartida no orçamento do projeto")

    for item in call.get("requirements") or []:
        if not isinstance(item, dict) or not item.get("code"):
            continue
        req(f"custom:{item['code']}", str(item.get("label") or item["code"])[:200], "unknown",
            str(item.get("detail") or "Requisito específico do edital — confirmação manual"),
            mandatory=bool(item.get("mandatory", True)), how=item.get("how_to_fix"))

    for r in mi.inst or []:
        st = {"met": "met", "unmet": "unmet", "expired": "unmet"}.get(r.get("status"), "unknown")
        req(f"inst:{r['code']}", r.get("label") or r["code"], st, r.get("detail") or "", mandatory=bool(r.get("mandatory", True)), how=r.get("how_to_fix"))

    if project:
        sc, txt, ok = _ticket_fit(project, call.get("ticket_min_cents"), call.get("ticket_max_cents"))
        if sc is not None:
            req("ticket", "Valor solicitado dentro da faixa", "met" if ok else "unmet", txt,
                how="Ajuste o orçamento ou fracione o projeto em marcos")
    elif call.get("ticket_min_cents") or call.get("ticket_max_cents"):
        req("ticket", "Valor solicitado dentro da faixa", "unknown", "Vincule um projeto para comparar valores", mandatory=False)

    blockers = [{"code": r["code"].upper().replace(":", "_"),
                 "message": (f"Match bloqueado porque o requisito '{r['label']}' não foi comprovado. {r['detail']}".strip() if r["code"].startswith("inst:")
                             else f"{r['label']}: {r['detail']}"), "how_to_fix": r["how_to_fix"]}
                for r in reqs if r["mandatory"] and r["status"] == "unmet"]
    unknown_mandatory = [r for r in reqs if r["mandatory"] and r["status"] == "unknown"]

    # -- Sinais de compatibilidade ---------------------------------------------------------
    sig: list[Signal] = []
    causes = (project or {}).get("causes") or org.get("causes")
    ov = _overlap(causes, call.get("causes"))
    if not call.get("causes"):
        sig.append(Signal("cause", weights["cause"], 0.7, "Edital sem causa específica (amplo)"))
    elif ov is None:
        sig.append(Signal("cause", weights["cause"], None, "Causas da OSC/projeto não informadas"))
        missing.append({"field": "causes", "label": "Causas de atuação", "owner": "osc"})
    else:
        inter = sorted(set(causes) & set(call["causes"]))
        sig.append(Signal("cause", weights["cause"], min(1.0, ov * 1.5) if inter else 0.0,
                          f"Causas em comum: {', '.join(inter)}" if inter else "Nenhuma causa em comum"))

    if call_terrs and terr_target:
        best = max((specificity(t, terr_target) for t in call_terrs), default=0.0)
        sig.append(Signal("territory", weights["territory"], best, "Território coberto" if best else "Fora do território do edital"))
    elif not call_terrs:
        sig.append(Signal("territory", weights["territory"], 0.6, "Edital sem foco territorial"))
    else:
        sig.append(Signal("territory", weights["territory"], None, "Território de execução não informado"))

    if project:
        sc, txt, _ = _ticket_fit(project, call.get("ticket_min_cents"), call.get("ticket_max_cents"))
        sig.append(Signal("budget", weights["budget"], sc, txt))
    else:
        sig.append(Signal("budget", weights["budget"], None, "Sem projeto vinculado para comparar valores"))

    total_req = [r for r in reqs if r["mandatory"]]
    met = sum(1 for r in total_req if r["status"] == "met")
    # Procedência do sinal: documento no cofre e vigente é VERIFIED_DOCUMENT; requisito atendido por declaração é
    # DECLARED. O sinal mais fraco manda, porque prontidão por autodeclaração não é prontidão comprovada.
    doc_based = [r for r in total_req if r["status"] == "met" and r.get("kind") in (None, "document", "certification")]
    newest_doc = max((d.get("created_at") for d in (mi.documents or []) if d.get("created_at")), default=None)
    rd_source = Source.VERIFIED_DOCUMENT if doc_based and newest_doc else (Source.DECLARED if total_req else Source.ABSENT)
    sig.append(Signal("readiness", weights["readiness"], (met / len(total_req)) if total_req else 1.0,
                      f"{met} de {len(total_req)} requisitos obrigatórios atendidos",
                      evidence=Evidence("readiness", rd_source, met if total_req else None, observed_at=newest_doc,
                                        kind="document", detail=f"{len(doc_based)} requisito(s) sustentado(s) por documento")))

    ods_ov = _overlap((project or {}).get("ods") or org.get("ods"), call.get("ods"))
    sig.append(Signal("ods", weights["ods"], None if ods_ov is None and call.get("ods") else (ods_ov if ods_ov is not None else 0.6),
                      "ODS em comum" if ods_ov else ("ODS não informados" if call.get("ods") else "Edital sem ODS específicos")))

    if closes:
        days = (closes - today).days
        pending = sum(1 for r in reqs if r["status"] != "met")
        need_days = 7 + 5 * pending
        val = 0.0 if days < 0 else min(1.0, days / need_days)
        sig.append(Signal("deadline", weights["deadline"], val, f"{max(days, 0)} dias até o encerramento; {pending} pendência(s)"))
        if 0 <= days < need_days:
            risks.append({"code": "TIGHT_DEADLINE", "severity": "high" if days < 7 else "medium",
                          "message": f"Prazo curto: {days} dias para resolver {pending} pendência(s)"})
    else:
        sig.append(Signal("deadline", weights["deadline"], 0.7, "Fluxo contínuo / sem prazo final informado"))

    h = mi.history or {}
    if h:
        ev_t, ev_a = int(h.get("evidences_total") or 0), int(h.get("evidences_accepted") or 0)
        comp = int(h.get("completed_projects") or 0)
        val = min(1.0, 0.4 * min(comp, 3) / 3 + (0.6 * ev_a / ev_t if ev_t else 0.3))
        sig.append(Signal("history", weights["history"], val, f"{comp} projeto(s) concluído(s); {ev_a}/{ev_t} evidências aceitas",
                          evidence=Evidence("history", Source.PLATFORM_RECORD, comp, observed_at=_today(mi),
                                            kind="project_activity", detail="histórico medido na própria plataforma")))
    else:
        sig.append(Signal("history", weights["history"], None, "Sem histórico na plataforma"))

    for r in unknown_mandatory:
        missing.append({"field": r["code"], "label": r["label"], "owner": "osc"})

    return _finish(mi, "osc_call", weights, wver, sig, blockers, reqs, risks, missing, unknown_mandatory)


# ------------------------------------------------------------------------------------------------
# Direção 2: financiador avalia projeto de OSC
# ------------------------------------------------------------------------------------------------
def evaluate_funder_project(mi: MatchInput) -> dict:
    p, org, f, call = mi.project or {}, mi.org, mi.funder or {}, mi.call
    today = _today(mi)
    weights, wver = _weights_for("funder_project", (call or {}).get("weights"))
    blockers: list[dict] = []
    risks: list[dict] = []
    missing: list[dict] = []

    def block(code, msg, how=None):
        blockers.append({"code": code, "message": msg, "how_to_fix": how})

    if p.get("visibility") != "published" and not call:
        block("PROJECT_NOT_PUBLISHED", "Projeto não publicado pela OSC")
    if org.get("compliance_status") in ("rejected", "suspended"):
        block("OSC_COMPLIANCE_BLOCKED", "OSC com compliance reprovado ou suspenso")
    if mi.conflict:
        block("CONFLICT_OF_INTEREST", "Conflito de interesse declarado por membro da equipe", "Registrar abstenção e designar outro avaliador")
    excl = set(f.get("excluded_causes") or []) & set(p.get("causes") or [])
    if excl:
        block("EXCLUDED_CAUSE", f"Causa excluída pela política do financiador: {', '.join(sorted(excl))}")
    terr = p.get("territory")
    if terr and any(covers(t, terr) for t in (f.get("excluded_territories") or [])):
        block("EXCLUDED_TERRITORY", f"Território {terr} excluído pela política do financiador")
    if call:
        closes = _as_date(call.get("closes_at"))
        if call.get("status") != "open" or (closes and closes < today):
            block("CALL_NOT_OPEN", "Programa/chamada não está aberto")
        if call.get("territories") and terr and not any(covers(t, terr) for t in call["territories"]):
            block("TERRITORY_OUT_OF_SCOPE", f"Território {terr} fora do escopo do programa")
    tmin = (call or {}).get("ticket_min_cents") or f.get("ticket_min_cents")
    tmax = (call or {}).get("ticket_max_cents") or f.get("ticket_max_cents")
    fit, fit_txt, fit_ok = _ticket_fit(p, tmin, tmax, f.get("accepts_fractioning", True) is not False)
    if not fit_ok:
        block("TICKET_INCOMPATIBLE", fit_txt, "OSC pode fracionar o projeto em marcos compatíveis")
    live = _live_docs(mi, today)
    req_docs = sorted(set((call or {}).get("required_document_types") or []) | set(f.get("required_document_types") or []))
    absent = [d for d in req_docs if d not in live]
    if absent:
        block("MISSING_CRITICAL_DOCUMENT", f"Documentos obrigatórios ausentes/vencidos: {', '.join(_doc_label(d) for d in absent)}",
              "Solicitar à OSC o envio dos documentos")
    inst_unknown: list[dict] = []
    for r in mi.inst or []:
        if r.get("mandatory", True) and r.get("status") in ("unmet", "expired"):
            block("INST_" + r["code"].upper().replace(":", "_"), f"Match bloqueado porque o requisito '{r.get('label') or r['code']}' não foi comprovado. {r.get('detail') or ''}".strip(),
                  r.get("how_to_fix") or "Solicitar à organização a comprovação do requisito")
        elif r.get("mandatory", True) and r.get("status") in ("unknown", "pending_validation"):
            missing.append({"field": "inst:" + r["code"], "label": r.get("label") or r["code"], "owner": "osc"})
            inst_unknown.append(r)
    min_age = (call or {}).get("min_org_age_months") or f.get("min_org_age_months")
    founded = _as_date(org.get("founded_on"))
    if min_age and founded and _months_between(founded, today) < min_age:
        block("ORG_TOO_NEW", f"OSC com menos de {min_age} meses de existência")
    elif min_age and not founded:
        missing.append({"field": "founded_on", "label": "Data de fundação da OSC", "owner": "osc"})

    sig: list[Signal] = []
    pref_causes = (call or {}).get("causes") or f.get("causes")
    ov = _overlap(p.get("causes"), pref_causes)
    if not pref_causes:
        sig.append(Signal("cause", weights["cause"], None, "Financiador sem causas prioritárias definidas"))
        missing.append({"field": "funder.causes", "label": "Causas prioritárias do financiador", "owner": "funder"})
    elif ov is None:
        sig.append(Signal("cause", weights["cause"], None, "Projeto sem causa informada"))
        missing.append({"field": "project.causes", "label": "Causas do projeto", "owner": "osc"})
    else:
        inter = sorted(set(p["causes"]) & set(pref_causes))
        sig.append(Signal("cause", weights["cause"], 1.0 if inter else 0.0,
                          f"Alinhado às causas prioritárias: {', '.join(inter)}" if inter else "Fora das causas prioritárias"))

    pref_terr = (call or {}).get("territories") or f.get("territories")
    if terr and pref_terr:
        best = max(specificity(t, terr) for t in pref_terr)
        sig.append(Signal("territory", weights["territory"], best, f"Execução em {terr}"))
    elif not pref_terr:
        sig.append(Signal("territory", weights["territory"], 0.6, "Financiador sem território prioritário"))
    else:
        sig.append(Signal("territory", weights["territory"], None, "Território do projeto não informado"))

    sig.append(Signal("budget", weights["budget"], fit, fit_txt))

    ods_ov = _overlap(p.get("ods"), (call or {}).get("ods") or f.get("ods"))
    esg_ov = _overlap(p.get("esg_tags"), f.get("esg_focus"))
    parts = [x for x in (ods_ov, esg_ov) if x is not None]
    sig.append(Signal("ods_esg", weights["ods_esg"], (sum(parts) / len(parts)) if parts else None,
                      f"ODS {round((ods_ov or 0) * 100)}% · ESG {round((esg_ov or 0) * 100)}%" if parts else "ODS/ESG não informados"))

    required_base = req_docs or ["estatuto_social", "cartao_cnpj", "ata_eleicao_diretoria", "cnd_federal"]
    doc_ratio = sum(1 for d in required_base if d in live) / len(required_base)
    age_score = None
    if founded:
        months = _months_between(founded, today)
        age_score = min(1.0, months / 36)
    cap = doc_ratio * 0.6 + (age_score if age_score is not None else 0.3) * 0.25 + (0.15 if org.get("compliance_status") == "approved" else 0)
    approved = org.get("compliance_status") == "approved"
    newest = max((d.get("created_at") for d in (mi.documents or []) if d.get("created_at")), default=None)
    cap_source = (Source.PLATFORM_RECORD if approved else (Source.VERIFIED_DOCUMENT if live else Source.DECLARED))
    sig.append(Signal("capacity", weights["capacity"], cap,
                      f"Documentação básica {round(doc_ratio * 100)}% · compliance {org.get('compliance_status') or 'pendente'}",
                      evidence=Evidence("capacity", cap_source, round(cap, 4), observed_at=newest, kind="compliance",
                                        detail="cadastro aprovado pela plataforma" if approved
                                               else f"{len(live)} documento(s) vigente(s) no cofre")))
    if org.get("compliance_status") != "approved":
        risks.append({"code": "COMPLIANCE_PENDING", "severity": "medium", "message": "Compliance da OSC não concluído"})

    h = mi.history or {}
    if h and (h.get("evidences_total") or h.get("completed_projects")):
        ev_t, ev_a = int(h.get("evidences_total") or 0), int(h.get("evidences_accepted") or 0)
        q = int(h.get("expenses_questioned") or 0)
        val = (ev_a / ev_t if ev_t else 0.5) * 0.7 + min(int(h.get("completed_projects") or 0), 3) / 3 * 0.3
        if q:
            val = max(0.0, val - 0.1 * q)
            risks.append({"code": "EXPENSES_QUESTIONED", "severity": "medium", "message": f"{q} despesa(s) questionada(s) em projetos anteriores"})
        sig.append(Signal("evidence_history", weights["evidence_history"], min(1.0, val), f"{ev_a}/{ev_t} evidências aceitas",
                          evidence=Evidence("evidence_history", Source.PLATFORM_RECORD, ev_a, observed_at=_today(mi),
                                            kind="project_activity", detail="evidências avaliadas na plataforma")))
    else:
        sig.append(Signal("evidence_history", weights["evidence_history"], None, "Sem histórico de execução na plataforma"))
        risks.append({"code": "NO_TRACK_RECORD", "severity": "low", "message": "OSC sem histórico de execução registrado na plataforma"})

    ben, need = p.get("beneficiaries_count"), _remaining_need(p) or p.get("budget_total_cents")
    has_ind = bool(p.get("indicators"))
    if ben and need:
        per_k = ben / max(1.0, need / 100_000)   # beneficiários por R$ 1.000
        val = min(1.0, math.log10(1 + per_k) / 2) * 0.7 + (0.3 if has_ind else 0)
        sig.append(Signal("impact", weights["impact"], val, f"{ben} beneficiários · {per_k:.1f} por R$ 1.000 · indicadores {'definidos' if has_ind else 'ausentes'}"))
    else:
        sig.append(Signal("impact", weights["impact"], None, "Beneficiários ou orçamento não informados"))
        missing.append({"field": "project.beneficiaries_count", "label": "Número de beneficiários", "owner": "osc"})
    if not has_ind:
        missing.append({"field": "project.indicators", "label": "Indicadores e metas de resultado", "owner": "osc"})

    urg = {"high": 1.0, "medium": 0.6, "low": 0.3}.get(p.get("urgency") or "", None)
    sig.append(Signal("urgency", weights["urgency"], urg, f"Urgência {p.get('urgency') or 'não informada'}"))

    b = mi.behavior or {}
    if b.get("saved_causes") or b.get("dismissed_causes"):
        pc = set(p.get("causes") or [])
        s, d = len(pc & set(b.get("saved_causes") or [])), len(pc & set(b.get("dismissed_causes") or []))
        sig.append(Signal("preference", weights["preference"], max(0.0, min(1.0, 0.5 + 0.25 * s - 0.25 * d)),
                          "Semelhante a projetos salvos" if s > d else ("Semelhante a projetos descartados" if d else "Neutro")))
    else:
        sig.append(Signal("preference", weights["preference"], None, "Sem histórico de preferências"))

    need_total = p.get("budget_total_cents") or 0
    if call and call.get("budget_total_cents") and need_total > 0.5 * call["budget_total_cents"]:
        risks.append({"code": "BUDGET_CONCENTRATION", "severity": "medium", "message": "Projeto consome mais de 50% do orçamento do programa"})
    if p.get("ends_on") and _as_date(p["ends_on"]) and _as_date(p["ends_on"]) < today:
        risks.append({"code": "PROJECT_ENDED", "severity": "high", "message": "Data de término do projeto já passou"})

    return _finish(mi, "funder_project", weights, wver, sig, blockers, [], risks, missing, inst_unknown)


# ------------------------------------------------------------------------------------------------
def _finish(mi, direction, weights, wver, sig, blockers, reqs, risks, missing, unknown_mandatory) -> dict:
    th = DEFAULT_WEIGHTS["thresholds"]
    total_w = sum(s.weight for s in sig) or 1.0
    known = [s for s in sig if s.value is not None]
    known_w = sum(s.weight for s in known)
    coverage = round(100 * known_w / total_w, 1)
    score = round(100 * sum(s.weight * s.value for s in known) / known_w, 1) if known_w else None
    # Confiança = cobertura dos sinais AJUSTADA pela frescura/procedência das evidências. Dado velho ou apenas
    # declarado não reduz a PONTUAÇÃO (o fato pode ser verdade), reduz a CERTEZA.
    evid = EvidenceSet()
    for s in sig:
        if s.evidence is not None:
            evid.add(s.evidence)
    confidence, conf_detail = (coverage, "sem evidências datadas")
    if evid.items:
        from ...core.evidence import decay_confidence
        confidence, conf_detail = decay_confidence(coverage, evid)
    if confidence < th["min_confidence_for_score"]:
        score = None
    if blockers:
        eligibility = "blocked"
    elif unknown_mandatory or confidence < th["min_confidence_for_score"]:
        eligibility = "needs_review"
    else:
        eligibility = "eligible"
    if eligibility == "blocked":
        state = "bloqueada"
    elif score is None:
        state = "revisao_humana"
    elif score >= th["priority_score"] and eligibility == "eligible":
        state = "prioritaria"
    elif score >= th["compatible_score"]:
        state = "compativel" if eligibility == "eligible" else "potencial_com_lacunas"
    else:
        state = "potencial_com_lacunas"

    ranked = sorted(known, key=lambda s: s.weight * s.value, reverse=True)
    why = [s.as_dict() for s in ranked if s.value >= 0.6][:3]
    why_not = [s.as_dict() for s in sorted(known, key=lambda s: s.weight * (1 - s.value), reverse=True) if s.value < 0.5][:3]
    seen = set()
    missing = [m for m in missing if not (m["field"] in seen or seen.add(m["field"]))]

    if blockers:
        nxt = {"code": "resolve_blockers", "label": blockers[0].get("how_to_fix") or "Resolver os bloqueios listados"}
    elif missing:
        owner = missing[0]["owner"]
        nxt = {"code": "complete_data", "label": f"Completar: {missing[0]['label']}" + (" (solicitar à OSC)" if owner == "osc" and direction == "funder_project" else "")}
    elif direction == "osc_call":
        nxt = {"code": "start_application", "label": "Iniciar candidatura assistida (checklist passo a passo)"}
    elif state == "prioritaria":
        nxt = {"code": "shortlist", "label": "Adicionar à shortlist e iniciar diligência"}
    else:
        nxt = {"code": "human_review", "label": "Revisar manualmente e registrar decisão"}

    features = {s.key: (None if s.value is None else round(s.value, 4)) for s in sig}
    features.update({"blockers": len(blockers), "confidence": confidence})
    evidence_summary = evid.summary() if evid.items else {"known": 0, "total": 0, "verified": 0,
                                                          "declared_only": 0, "mean_confidence": 0.0, "stale": 0}
    conf_band = band(confidence, len(known), len(sig))
    return {
        "engine_version": ENGINE_VERSION, "weights_version": wver, "rules_version": RULES_VERSION,
        "taxonomy_version": TAXONOMY_VERSION, "direction": direction,
        "eligibility": eligibility, "recommended_state": state, "score": score,
        "coverage": coverage, "confidence": confidence, "confidence_detail": conf_detail,
        "confidence_band": conf_band.value,
        "blockers": blockers, "requirements": reqs, "why_match": why, "why_not": why_not, "risks": risks,
        "missing_data": missing, "next_action": nxt, "signals": [s.as_dict() for s in sig], "features": features,
        "evidence": evid.as_dict() if evid.items else {}, "evidence_summary": evidence_summary,
        "stale_evidence": evid.stale() if evid.items else [],
        "disclaimer": "Indicador de apoio à decisão. Decisão final é humana; plano ou voucher não alteram este resultado. "
                      "Pontuação alta com confiança baixa NÃO é recomendação: confira a faixa de confiança.",
    }


def evaluate(mi: MatchInput) -> dict:
    if mi.direction == "osc_call":
        return evaluate_osc_call(mi)
    if mi.direction == "funder_project":
        return evaluate_funder_project(mi)
    raise ValueError("direção inválida")
