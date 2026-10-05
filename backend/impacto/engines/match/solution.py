"""Match financiador ↔ solução (solution-match@1.0.0, pesos em config/match_weights.json → solution_funder).

Separado da relevância de busca (engines/solutions/scoring.relevance): aqui se mede aderência à TESE do financiador. Plano/assinatura/voucher/pagamento
NÃO entram (ADR-007/008; AST em tests/test_architecture.py). Sinal de apoio — não é recomendação de investimento.
"""
from __future__ import annotations

from dataclasses import dataclass

from .engine import DEFAULT_WEIGHTS, Signal, SIGNAL_LABELS, _finish, _pick

ENGINE_VERSION = "solution-match@1.0.0"
SIGNAL_LABELS.update({"causes": "Causas/temas", "ods_esg": "ODS/ESG", "ticket": "Faixa de investimento", "preferences": "Preferências da tese",
                      "maturity": "Maturidade do cadastro", "population": "População atendida"})
_F = ("causes", "ods", "esg_focus", "territories", "excluded_causes", "excluded_territories", "ticket_min_cents", "ticket_max_cents")
_S = ("themes", "ods", "esg", "uf", "budget_cents", "needed_cents", "seeking_funding", "population", "kind", "stage", "trust_level", "visibility", "maturity")
_P = ("populations", "kinds", "prefer_proven", "risk_tolerance")


@dataclass(frozen=True)
class SolutionMatchInput:
    funder: dict
    solution: dict
    prefs: dict

    @staticmethod
    def build(funder: dict, solution: dict, prefs: dict | None = None) -> "SolutionMatchInput":
        return SolutionMatchInput(_pick(funder, _F), _pick(solution, _S), _pick(prefs or {}, _P))


def evaluate(mi: SolutionMatchInput) -> dict:
    f, s, p = mi.funder, mi.solution, mi.prefs
    weights = dict(DEFAULT_WEIGHTS["solution_funder"])
    blockers, reqs, risks, missing, sig = [], [], [], [], []
    if s.get("visibility") != "published":
        blockers.append({"code": "not_published", "label": "Solução não publicada", "how_to_fix": "Aguardar publicação pelo autor"})
    themes = set(s.get("themes") or [])
    ex = set(f.get("excluded_causes") or []) & themes
    if ex:
        blockers.append({"code": "excluded_cause", "label": "Tema excluído pela política do financiador: " + ", ".join(sorted(ex)), "how_to_fix": "Ajustar a tese, se aplicável"})
    uf = s.get("uf")
    if uf and any(t in (f.get("excluded_territories") or []) for t in (f"BR-{uf}", "BR")):
        blockers.append({"code": "excluded_territory", "label": "Território excluído pela política do financiador", "how_to_fix": "Ajustar a tese, se aplicável"})
    fc = set(f.get("causes") or [])
    sig.append(Signal("causes", weights["causes"], None if not fc or not themes else len(fc & themes) / len(fc | themes) if len(fc & themes) else 0.0,
                      "temas em comum: %s" % (", ".join(sorted(fc & themes)) or "nenhum")))
    if not fc:
        missing.append({"field": "causes", "label": "Causas da tese do financiador", "owner": "funder"})
    if not themes:
        missing.append({"field": "themes", "label": "Temas da solução", "owner": "osc"})
    fo, fe = set(f.get("ods") or []), set(f.get("esg_focus") or [])
    so, se = set(s.get("ods") or []), set(s.get("esg") or [])
    parts = []
    if fo and so:
        parts.append(len(fo & so) / len(fo))
    if fe and se:
        parts.append(len(fe & se) / len(fe))
    sig.append(Signal("ods_esg", weights["ods_esg"], sum(parts) / len(parts) if parts else None, "ODS/ESG em comum"))
    ft = f.get("territories") or []
    if ft and uf:
        ok = any(t in ("INT", "BR") or t == f"BR-{uf}" or t.startswith(f"BR-{uf}-") for t in ft)
        sig.append(Signal("territory", weights["territory"], 1.0 if ok else 0.0, "solução atua em área de interesse" if ok else "fora das áreas de interesse"))
    else:
        sig.append(Signal("territory", weights["territory"], None, "território não comparável"))
    lo, hi = f.get("ticket_min_cents"), f.get("ticket_max_cents")
    need = s.get("needed_cents") if s.get("seeking_funding") else None
    if need is not None and (lo is not None or hi is not None):
        ok = (lo is None or need >= lo) and (hi is None or need <= hi)
        sig.append(Signal("ticket", weights["ticket"], 1.0 if ok else 0.3, "necessidade de captação dentro da faixa" if ok else "necessidade fora da faixa de investimento"))
        if not ok:
            risks.append({"code": "ticket_outside", "label": "Valor necessário fora da faixa do financiador"})
    else:
        sig.append(Signal("ticket", weights["ticket"], None, "faixa de investimento ou necessidade não informada"))
    pp = set(p.get("populations") or [])
    sp = set(s.get("population") or [])
    sig.append(Signal("population", weights["population"], None if not pp or not sp else len(pp & sp) / len(pp), "populações em comum"))
    pref_parts = []
    if p.get("kinds"):
        pref_parts.append(1.0 if s.get("kind") in p["kinds"] else 0.0)
    if p.get("prefer_proven"):
        pref_parts.append(1.0 if s.get("trust_level") in ("evidenced", "verified") else 0.2)
    if p.get("risk_tolerance") == "low" and s.get("stage") in ("idea", "proposal"):
        pref_parts.append(0.2)
        risks.append({"code": "early_stage", "label": "Tolerância baixa a risco e solução em estágio inicial"})
    sig.append(Signal("preferences", weights["preferences"], sum(pref_parts) / len(pref_parts) if pref_parts else None, "preferências da tese"))
    mat = s.get("maturity")
    sig.append(Signal("maturity", weights["maturity"], None if mat is None else mat / 100, "completude do cadastro"))
    if s.get("trust_level") in ("unverified", "self_declared", "in_review"):
        risks.append({"code": "unverified", "label": "Solução sem verificação independente (informações autodeclaradas)"})
    weights.setdefault("territory", 15)
    res = _finish(None, "solution_funder", weights, DEFAULT_WEIGHTS["version"], sig, blockers, reqs, risks, missing, False)
    res["engine_version"] = ENGINE_VERSION
    res["disclaimer"] = "Indicador de aderência à tese cadastrada; não é recomendação de investimento. Plano ou voucher não alteram este resultado."
    return res
