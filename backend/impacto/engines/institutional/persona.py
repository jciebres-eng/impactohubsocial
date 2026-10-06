"""Visões por perfil institucional (puro): OS, OSCIP, OSC e iniciativa em estruturação. Só organiza o que está cadastrado e rotula a base de cada
informação (VERIFICADO / DECLARADO). Nunca afirma qualificação, contrato ou elegibilidade que não conste."""
from __future__ import annotations

from datetime import date

from .common import as_date, config
from ...clock import today as _hoje_utc  # data do produto é UTC; ver impacto/clock.py

AGREEMENT_LABELS = {"management_contract": "Contrato de gestão", "partnership_term": "Termo de parceria", "collaboration_term": "Termo de colaboração",
                    "fomento_term": "Termo de fomento", "cooperation_agreement": "Acordo de cooperação", "other": "Outro instrumento"}
AGREEMENT_STATUS = {"draft": "Rascunho", "active": "Vigente (declarado)", "completed": "Concluído", "terminated": "Encerrado", "suspended": "Suspenso"}
VERIFY = {"declared": "DECLARADO (não verificado)", "document_submitted": "COMPROVANTE ENVIADO — aguarda análise", "verified": "VERIFICADO", "rejected": "REJEITADO"}
# quais instrumentos importam para cada perfil (apenas relevância de exibição; não é regra legal)
FOCUS = {"os": ("management_contract",), "oscip": ("partnership_term",), "osc": ("collaboration_term", "fomento_term", "cooperation_agreement")}
WARN_DAYS = (30, 60, 90)


def agreement_view(a: dict, today: date) -> dict:
    end = as_date(a.get("end_date"))
    left = (end - today).days if end else None
    status = a.get("agreement_status")
    alert = None
    if status == "active" and left is not None:
        if left < 0:
            alert = {"level": "expired", "message": "Vigência informada já terminou, mas o instrumento consta como vigente: atualize o status."}
        elif left <= WARN_DAYS[0]:
            alert = {"level": "30", "message": f"Vigência termina em {left} dia(s)."}
        elif left <= WARN_DAYS[2]:
            alert = {"level": "90", "message": f"Vigência termina em {left} dia(s)."}
    return {**a, "type_label": AGREEMENT_LABELS.get(a["agreement_type"], a["agreement_type"]), "status_label": AGREEMENT_STATUS.get(status, status),
            "verification_label": VERIFY.get(a.get("verification_status"), a.get("verification_status")), "days_left": left, "alert": alert}


def profile_of(facts: dict, quals: list[dict]) -> list[str]:
    """Perfis aplicáveis (podem ser vários). Baseia-se em qualificações registradas (em qualquer estado, rotuladas) e na estrutura da organização."""
    held = {q["qualification_type"] for q in quals if q["verification_status"] not in ("rejected", "revoked")}
    out = [p for p in ("os", "oscip") if p in held]
    if facts.get("kind") == "osc":
        if facts.get("legal_nature_code") == "collective" or not facts.get("cnpj_present"):
            out.append("structuring")
        elif not out:
            out.append("osc")
        else:
            out.append("osc")
    return out


def view(profile: str, facts: dict, quals: list[dict], agreements: list[dict], today: date | None = None) -> dict:
    today = today or _hoje_utc()
    w = config()["qualification_warning_days"]
    mine = [q for q in quals if q["qualification_type"] == profile and q["verification_status"] not in ("rejected", "revoked")]
    ag = [agreement_view(a, today) for a in agreements]
    focus = [a for a in ag if a["agreement_type"] in FOCUS.get(profile, ())]
    alerts, next_steps = [], []
    for q in mine:
        exp = as_date(q.get("expiration_date"))
        if q["verification_status"] == "verified" and exp:
            d = (exp - today).days
            if d < 0:
                alerts.append({"scope": "qualification", "level": "expired", "message": f"Qualificação {profile.upper()} verificada, mas com validade vencida em {exp.isoformat()}."})
            elif d <= max(w, WARN_DAYS[2]):
                alerts.append({"scope": "qualification", "level": "soon", "message": f"Qualificação {profile.upper()} vence em {d} dia(s)."})
        if q["verification_status"] == "declared":
            next_steps.append("Anexe o comprovante da qualificação para a administração verificar.")
        if not q.get("issuing_authority"):
            next_steps.append("Informe a autoridade qualificadora/emissora.")
        if not q.get("certificate_number") and not q.get("protocol"):
            next_steps.append("Informe o número do ato ou o protocolo da qualificação.")
    for a in focus:
        if a["alert"]:
            alerts.append({"scope": "agreement", "level": a["alert"]["level"], "message": f"{a['type_label']} {a.get('instrument_number') or ''}: {a['alert']['message']}".replace("  ", " ")})
        if a["verification_status"] == "declared":
            next_steps.append(f"Anexe o documento do {a['type_label'].lower()} {a.get('instrument_number') or ''}".strip() + " para verificação.")
    if not mine:
        next_steps.insert(0, f"Nenhuma qualificação {profile.upper()} registrada. Se a organização a possui, registre em Qualificações com autoridade, número e comprovante; se não, esta visão não se aplica.")
    areas = sorted({a for q in mine for a in (q.get("areas") or [])})
    authorities = sorted({q["issuing_authority"] for q in mine if q.get("issuing_authority")})
    return {"profile": profile, "qualifications": [{"id": q["id"], "status": q["verification_status"], "status_label": VERIFY.get(q["verification_status"], q["verification_status"]) if q["verification_status"] in VERIFY else q["verification_status"],
                                                      "issuing_authority": q.get("issuing_authority"), "certificate_number": q.get("certificate_number"), "expiration_date": q.get("expiration_date"),
                                                      "areas": q.get("areas") or []} for q in mine],
            "qualifying_authorities": authorities, "areas": areas, "agreements": focus, "other_agreements": [a for a in ag if a not in focus],
            "alerts": alerts, "next_steps": list(dict.fromkeys(next_steps)),
            "disclaimer": "Visão derivada de dados declarados e das verificações da plataforma. Não confirma a qualificação perante o órgão competente."}
