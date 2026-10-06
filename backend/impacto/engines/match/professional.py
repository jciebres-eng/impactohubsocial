"""Match profissional ↔ necessidade de projeto (professional-match@1.0.0, pesos em config/match_weights.json → professional_need).

Mesma filosofia do núcleo (engine.py): elegibilidade determinística separada do score; score só com confiança suficiente;
explicação (por que combina / por que não / riscos / dados ausentes / próxima ação). Entradas por lista branca — plano,
assinatura, voucher e pagamento NÃO entram (ADR-007/008; verificado por AST em tests/test_architecture.py).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .engine import DEFAULT_WEIGHTS, Signal, SIGNAL_LABELS, _finish, _pick
from .territory import specificity
from ...clock import today as _hoje_utc  # data do produto é UTC; ver impacto/clock.py

ENGINE_VERSION = "professional-match@1.0.0"
# Categorias cujo exercício depende de registro em conselho (credencial verificada passa a ser requisito).
REGULATED = {"contador": "CRC", "advogado": "OAB", "auditor": "CRC", "engenheiro": "CREA", "assistente_social": "CRESS"}
SIGNAL_LABELS.update({"category": "Categoria profissional", "credential": "Credencial profissional", "experience": "Experiência na plataforma",
                      "availability": "Disponibilidade", "language": "Idioma"})

_PROF_KEYS = ("categories", "services", "remote", "territories", "languages", "accepting_requests", "credentials", "open_reviews", "open_reviews_limit",
              "completed_reviews")
_NEED_KEYS = ("category", "remote_ok", "language", "status", "territory")


@dataclass(frozen=True)
class ProfessionalInput:
    professional: dict
    need: dict
    today: date

    @staticmethod
    def build(professional: dict, need: dict, today: date | None = None) -> ProfessionalInput:
        return ProfessionalInput(_pick(professional, _PROF_KEYS), _pick(need, _NEED_KEYS), today or _hoje_utc())


def _valid_credential(creds: list[dict], today: date, council: str | None) -> str:
    """verified | pending | none — considera validade e (se informado) o conselho esperado."""
    best = "none"
    for c in creds or []:
        if council and c.get("council") != council:
            continue
        vu = c.get("valid_until")
        if isinstance(vu, str):
            vu = date.fromisoformat(vu)
        if vu is not None and vu < today:
            continue
        if c.get("status") == "verified":
            return "verified"
        if c.get("status") in ("self_declared", "document_submitted"):
            best = "pending"
    return best


def evaluate(mi: ProfessionalInput) -> dict:
    p, n = mi.professional, mi.need
    weights = dict(DEFAULT_WEIGHTS["professional_need"])
    blockers, reqs, risks, missing, sig = [], [], [], [], []

    if n.get("status") != "open":
        blockers.append({"code": "need_closed", "label": "A necessidade não está aberta", "how_to_fix": "Escolher uma necessidade aberta"})
    if p.get("accepting_requests") is False:
        blockers.append({"code": "not_accepting", "label": "Profissional não está aceitando solicitações", "how_to_fix": "Ativar 'aceitando solicitações' no perfil"})
    cats = p.get("categories") or []
    if n.get("category") and cats and n["category"] not in cats:
        blockers.append({"code": "category_mismatch", "label": "A categoria da necessidade não está entre as do profissional",
                         "how_to_fix": "Incluir a categoria no perfil, se for atuação real"})
    sig.append(Signal("category", weights["category"], None if not cats else (1.0 if n.get("category") in cats else 0.0),
                      "categoria compatível" if n.get("category") in cats else "categoria não declarada pelo profissional"))
    if not cats:
        missing.append({"field": "categories", "label": "Categorias de atuação do profissional", "owner": "professional"})

    council = REGULATED.get(n.get("category") or "")
    unknown_mandatory = False
    if council:
        st = _valid_credential(p.get("credentials") or [], mi.today, council)
        sig.append(Signal("credential", weights["credential"], {"verified": 1.0, "pending": 0.3, "none": 0.0}[st],
                          {"verified": "credencial verificada e vigente", "pending": "credencial ainda não verificada pela administração",
                           "none": "sem credencial válida cadastrada"}[st]))
        if st != "verified":
            reqs.append({"code": "credential_required", "label": f"Categoria regulamentada ({council}): exige credencial verificada e vigente",
                         "status": "not_met" if st == "none" else "pending"})
            unknown_mandatory = True
            risks.append({"code": "credential_unverified", "label": "Credencial não verificada: validação/assinatura profissional ficará indisponível"})
    else:
        weights.pop("credential")

    pt, nt = p.get("territories") or [], n.get("territory")
    if n.get("remote_ok") and p.get("remote"):
        sig.append(Signal("territory", weights["territory"], 0.9, "atendimento remoto aceito por ambos"))
    elif nt and pt:
        best = max((specificity(t, nt) for t in pt), default=0.0)
        sig.append(Signal("territory", weights["territory"], best, "área de atuação cobre o território" if best else "fora da área de atuação"))
    else:
        sig.append(Signal("territory", weights["territory"], None, "sem território/atendimento remoto comparável"))
        missing.append({"field": "territories", "label": "Territórios de atuação ou atendimento remoto", "owner": "professional"})

    done = p.get("completed_reviews")
    sig.append(Signal("experience", weights["experience"], None if done is None else min(1.0, done / 5), f"revisões concluídas na plataforma: {done}"))
    lim, load = p.get("open_reviews_limit"), p.get("open_reviews")
    sig.append(Signal("availability", weights["availability"], None if not lim or load is None else max(0.0, 1 - load / lim),
                      "carga atual de revisões em aberto"))
    langs = p.get("languages") or []
    sig.append(Signal("language", weights["language"], None if not langs else (1.0 if (n.get("language") or "pt-BR") in langs else 0.0), "idioma"))

    res = _finish(None, "professional_need", weights, DEFAULT_WEIGHTS["version"], sig, blockers, reqs, risks, missing, unknown_mandatory)
    res["engine_version"] = ENGINE_VERSION
    if not blockers:
        res["next_action"] = ({"code": "send_offer", "label": "Enviar proposta ao projeto"} if not missing else res["next_action"])
    res["disclaimer"] = "Indicador de apoio. A contratação é livre entre as partes, fora da plataforma; plano ou voucher não alteram este resultado."
    return res
