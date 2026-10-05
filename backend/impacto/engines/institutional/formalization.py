"""Trilha de formalização (puro): do coletivo/iniciativa à organização formal. Etapas AUTOMÁTICAS são derivadas de fatos; as MANUAIS são só
DECLARADAS pela própria organização (nunca contam como verificadas). Não é parecer jurídico e concluir etapas não garante elegibilidade."""
from __future__ import annotations

import json
from datetime import date
from functools import lru_cache
from pathlib import Path

from .documents import best_state

CFG = Path(__file__).resolve().parents[4] / "config" / "formalization_path.json"
BASIS = {"verified": "VERIFICADO", "derived": "DERIVADO DOS DADOS", "declared": "DECLARADO PELA ORGANIZAÇÃO", "pending": "AGUARDANDO VALIDAÇÃO", "none": "NÃO INICIADO"}


@lru_cache(maxsize=1)
def path_config() -> dict:
    return json.loads(CFG.read_text(encoding="utf-8"))


def manual_codes() -> set[str]:
    return {s["code"] for s in path_config()["steps"] if s["kind"] == "manual"}


def _auto(check: str, facts: dict, has_project: bool, today: date) -> tuple[str, str]:
    if check == "cnpj_present":
        ok = bool(facts.get("cnpj_present"))
        return ("done", "derived") if ok else ("todo", "none")
    if check == "compliance_approved":
        return ("done", "verified") if facts.get("compliance_status") == "approved" else ("todo", "none")
    if check == "has_project":
        return ("done", "derived") if has_project else ("todo", "none")
    if check.startswith("doc:"):
        dt = check[4:]
        docs = [{"doc_type": d.get("doc_type"), "scan_status": d.get("scan_status"), "validation_status": d.get("validation_status"), "valid_until": d.get("valid_until")}
                for d in facts.get("documents") or []]
        st = best_state(docs, dt, today)[0]
        if st == "validated":
            return "done", "verified"
        if st == "pending_validation":
            return "in_progress", "pending"
        if st in ("expired", "rejected"):
            return "todo", "none"
        return "todo", "none"
    return "todo", "none"


def compute(facts: dict, manual: dict[str, dict], has_project: bool, today: date | None = None) -> dict:
    today = today or date.today()
    cfg = path_config()
    steps, done = [], 0
    for s in cfg["steps"]:
        if s["kind"] == "auto":
            state, basis = _auto(s["check"], facts, has_project, today)
        else:
            m = manual.get(s["code"]) or {}
            raw = m.get("state", "not_started")
            state = {"done_declared": "done", "in_progress": "in_progress"}.get(raw, "todo")
            basis = "declared" if raw in ("done_declared", "in_progress") else "none"
        if state == "done":
            done += 1
        steps.append({"code": s["code"], "label": s["label"], "kind": s["kind"], "state": state, "basis": basis, "basis_label": BASIS[basis], "help": s["help"],
                      "note": (manual.get(s["code"]) or {}).get("note")})
    nxt = next((s for s in steps if s["state"] != "done"), None)
    total = len(steps)
    return {"version": cfg["version"], "status_note": cfg["status"], "disclaimer": cfg["disclaimer"], "steps": steps,
            "progress": {"done": done, "total": total, "percent": round(100 * done / total) if total else None,
                         "note": "Etapas declaradas pela própria organização contam como concluídas só para este acompanhamento; não são verificação."},
            "next_step": {"code": nxt["code"], "label": nxt["label"], "help": nxt["help"]} if nxt else None}
