"""Interpretação INSTITUCIONAL de consultas livres ("OSCIP com projetos culturais", "OS saúde", "projetos com incentivo fiscal"...).

Determinístico e explicável: reconhece termos institucionais, devolve filtros estruturados + texto restante para o parser temático.
Qualificações viram filtro de qualificação VERIFICADA (declarada não basta). 'OS' só é reconhecido em maiúsculas e quando a consulta
não está inteira em maiúsculas (evita confundir com a palavra 'os')."""
from __future__ import annotations

import re
import unicodedata


def _n(t: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(ch) != "Mn")


QUALIFICATIONS = {
    "oscip": ["oscip", "oscips"],
    "cebas": ["cebas", "certificacao de entidade beneficente", "entidade beneficente"],
    "utilidade_publica_federal": ["utilidade publica federal"],
    "utilidade_publica_estadual": ["utilidade publica estadual"],
    "utilidade_publica_municipal": ["utilidade publica municipal"],
    "registro_cmas": ["cmas"],
    "registro_cmdca": ["cmdca"],
    "registro_cmi": ["conselho municipal do idoso"],
}
LEGAL_NATURES = {"association": ["associacao", "associacoes"], "foundation": ["fundacao", "fundacoes"], "cooperative": ["cooperativa", "cooperativas"],
                 "collective": ["coletivo", "coletivos"]}
MODALITIES = {"incentive_law": ["incentivo fiscal", "incentivos fiscais", "lei de incentivo", "lei rouanet", "renuncia fiscal"],
              "partnership_term": ["termo de colaboracao", "termo de fomento", "marco regulatorio"],
              "management_contract": ["contrato de gestao"], "agreement": ["convenio", "convenios"],
              "social_investment": ["investimento social"], "sponsorship": ["patrocinio"], "prize": ["premio", "premiacao"]}
READY = ["prontos para captacao", "prontas para captacao", "pronto para captacao", "pronta para captacao", "prontos para captar", "prontos para financiamento"]
APT = ["organizacoes aptas", "osc aptas", "entidades aptas", "organizacoes elegiveis"]


def parse(text: str) -> dict:
    raw = (text or "").strip()
    n = " " + _n(raw) + " "
    out = {"qualifications": [], "legal_natures": [], "modalities": [], "funding_ready": False, "osc": False, "matched": [], "remaining": raw}
    rem = n

    def eat(term: str) -> bool:
        nonlocal rem
        pat = " " + term + " "
        if pat in rem or (" " + term + "s ") in rem:
            rem = rem.replace(pat, " ").replace(" " + term + "s ", " ")
            return True
        return False

    for code, terms in QUALIFICATIONS.items():
        if any(eat(t) for t in terms):
            out["qualifications"].append(code)
            out["matched"].append({"filter": "qualification", "value": code})
    for code, terms in LEGAL_NATURES.items():
        if any(eat(t) for t in terms):
            out["legal_natures"].append(code)
            out["matched"].append({"filter": "legal_nature", "value": code})
    for code, terms in MODALITIES.items():
        if any(eat(t) for t in terms):
            out["modalities"].append(code)
            out["matched"].append({"filter": "modality", "value": code})
    if any(eat(t) for t in READY):
        out["funding_ready"] = True
        out["matched"].append({"filter": "funding_ready", "value": True})
    for t in APT:
        eat(t)
    # siglas curtas só em maiúsculas e se a consulta não estiver toda em maiúsculas
    letters = [ch for ch in raw if ch.isalpha()]
    mixed = any(ch.islower() for ch in letters)
    if mixed and re.search(r"(?<![A-Za-zÀ-ÿ])OS(?![A-Za-zÀ-ÿ])", raw):
        out["qualifications"].append("os")
        out["matched"].append({"filter": "qualification", "value": "os"})
        rem = re.sub(r"\bos\b", " ", rem, count=1)
    if re.search(r"(?<![A-Za-zÀ-ÿ])OSCs?(?![A-Za-zÀ-ÿ])", raw) and mixed:
        out["osc"] = True
        rem = re.sub(r"\boscs?\b", " ", rem, count=1)
    out["remaining"] = re.sub(r"\s+", " ", rem).strip()
    for k in ("qualifications", "legal_natures", "modalities"):
        out[k] = list(dict.fromkeys(out[k]))
    return out
