"""Vocabulário oficial: um termo, um rótulo, em todas as camadas.

PROBLEMA QUE ESTE MÓDULO RESOLVE. Um valor de enum nasce na migração, ganha um rótulo em português
dentro de um dicionário Python de algum módulo, e chega à interface sem passar por nenhum catálogo.
O resultado é previsível: a API devolve ``flagged``, a tela escreve "marcada", o texto de ajuda diz
"sinalizada" — três palavras para a mesma coisa, e ninguém sabe qual é a oficial.

COMO ESTE MÓDULO RESOLVE. ``config/glossary.json`` passa a ser a ORIGEM do rótulo. Este módulo declara,
para cada domínio do glossário, DE ONDE saem os valores que existem de verdade (um atributo Python, uma
coluna de migração, uma varredura de código-fonte). Com isso, ``missing()`` compara o que existe com o
que está documentado — e o teste ``tests/test_v0190_glossary.py`` reprova quando um valor novo aparece
sem rótulo nos três idiomas.

O QUE ESTE MÓDULO NÃO FAZ. Não traduz nada em tempo de execução, não substitui os dicionários de rótulo
que já existem nos módulos (eles continuam servindo a API) e não toca em conteúdo editorial que já vive
em tabela de catálogo no banco. Para esses, a origem é o banco: ver ``CATALOGS``.
"""
from __future__ import annotations

import importlib
import json
import re
from pathlib import Path
from typing import Any

#: Raiz do repositório (backend/impacto/core/glossary.py -> backend/impacto/core -> ... -> raiz).
ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "config" / "glossary.json"
MIGRATIONS = ROOT / "backend" / "migrations"
BACKEND = ROOT / "backend"


# ============================================================================= de onde vêm os valores
class Source:
    """Como obter os valores que EXISTEM de verdade para um domínio."""

    def __init__(self, kind: str, **spec: Any):
        self.kind, self.spec = kind, spec

    # ---- python: chaves de um dicionário, itens de uma tupla, valores de um Enum
    def _python(self) -> set[str]:
        mod = importlib.import_module(self.spec["module"])
        obj = getattr(mod, self.spec["attr"])
        if isinstance(obj, dict):
            return {k.value if hasattr(k, "value") else str(k) for k in obj}
        if isinstance(obj, (tuple, list, set, frozenset)):
            return {x.value if hasattr(x, "value") else str(x) for x in obj}
        # Enum (classe)
        return {m.value for m in obj}

    # ---- migração: CHECK (coluna IN ('a','b')) dentro de um arquivo específico
    def _migration(self) -> set[str]:
        prefix, column = self.spec["file_prefix"], self.spec["column"]
        files = sorted(p for p in MIGRATIONS.glob("*.sql") if p.name.startswith(prefix))
        if not files:
            raise AssertionError(f"migração {prefix}* não encontrada para a coluna {column}")
        found: set[str] = set()
        pat = re.compile(rf"\b{column}\s+text[^,\n]*?check\s*\(\s*{column}\s+in\s*\(([^)]*)\)", re.I)
        for path in files:
            for m in pat.finditer(path.read_text(encoding="utf-8")):
                found |= set(re.findall(r"'([^']+)'", m.group(1)))
        if not found:
            raise AssertionError(f"nenhum valor de {column} encontrado em {prefix}*")
        return found

    # ---- varredura de código: o próprio código é a origem (ex.: Signal("territory", ...))
    def _scan(self) -> set[str]:
        text = (BACKEND / self.spec["path"]).read_text(encoding="utf-8")
        found = set(re.findall(self.spec["pattern"], text))
        if not found:
            raise AssertionError(f"padrão {self.spec['pattern']!r} não encontrou nada em {self.spec['path']}")
        return found

    def values(self) -> set[str] | None:
        """Valores vivos, ou ``None`` quando o domínio é vocabulário declarado sem origem única."""
        if self.kind == "python":
            return self._python()
        if self.kind == "migration":
            return self._migration()
        if self.kind == "scan":
            return self._scan()
        if self.kind == "vocabulary":
            return None
        raise AssertionError(f"origem desconhecida: {self.kind}")


def _py(module: str, attr: str) -> Source:
    return Source("python", module=module, attr=attr)


def _mig(file_prefix: str, column: str) -> Source:
    return Source("migration", file_prefix=file_prefix, column=column)


#: domínio do glossário -> origem dos valores vivos.
#: Acrescentar um domínio ao glossário SEM declarar a origem aqui é reprovado pelo teste: um glossário que
#: não pode ser conferido contra o código é documentação, não contrato.
SURFACES: dict[str, Source] = {
    "claim_status": _py("impacto.impact.claims", "STATUS_LABEL"),
    "claim_kind": _mig("0028", "claim_kind"),
    "claim_severity": _mig("0028", "severity"),
    "claim_review_decision": _mig("0028", "decision"),
    "reputation_band": _mig("0029", "band"),
    "reputation_dispute_outcome": _mig("0029", "outcome"),
    "seal_status": _py("impacto.impact.seals", "STATUS_LABEL"),
    "seal_revocation_reason": _mig("0030", "reason"),
    "seal_definition_status": _mig("0030", "status"),
    "seal_scope": _mig("0030", "scope"),
    "equity_standing": _py("impacto.impact.equity", "STANDINGS"),
    "equity_denominator": _py("impacto.impact.equity", "DENOMINATOR_KINDS"),
    "equity_method": _py("impacto.impact.equity", "METHODS"),
    "responsibility_scope": _mig("0031", "scope"),
    "framework_relation": _py("impacto.impact.frameworks", "RELATIONS"),
    "framework_lens": _py("impacto.impact.frameworks", "LENSES"),
    "evidence_source": _py("impacto.core.evidence", "Source"),
    "confidence_band": _py("impacto.core.evidence", "BAND_LABEL"),
    "suggestion_origin": _py("impacto.impact.lookups", "ORIGIN_LABEL"),
    "readiness": _py("impacto.core.diagnostic", "READINESS_MAP"),
    "readiness_status": Source("scan", path="impacto/core/diagnostic.py",
                               pattern=r'"(ready|needs_review|unknown)"'),
    "match_signal": Source("scan", path="impacto/engines/match/engine.py",
                           pattern=r'Signal\("([a-z_]+)"'),
    # Vocabulário transversal: não tem um enum único no código porque descreve a AUSÊNCIA de dado, que
    # aparece como None em dezenas de lugares. Fica declarado para que a interface use as mesmas palavras.
    "data_availability": Source("vocabulary"),
}

#: Termos que JÁ vivem em catálogo no banco, com rótulo e explicação próprios. A origem é o banco:
#: duplicar no glossário criaria duas verdades. O teste exige rótulo e explicação não vazios em cada linha.
CATALOGS: dict[str, dict[str, str]] = {
    "claim_rules": {"label": "name_pt", "explains": "what_it_detects", "rows": "12"},
    "seal_rules": {"label": "name_pt", "explains": "what_it_checks", "rows": "12"},
    "reputation_dimensions": {"label": "name_pt", "explains": "what_it_measures", "rows": "6"},
    "responsibility_roles": {"label": "name_pt", "explains": "answers_for", "rows": "8"},
    "responsibility_decision_kinds": {"label": "name_pt", "explains": "what_it_is", "rows": "6"},
    "equity_barrier_catalog": {"label": "name_pt", "explains": "description", "rows": "varia"},
}


# ============================================================================= leitura do glossário
def load() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def documented(doc: dict | None = None) -> dict[str, set[str]]:
    """Domínio -> chaves documentadas, contando apelidos (``aliases``) como a mesma chave."""
    doc = doc or load()
    out: dict[str, set[str]] = {}
    for name, domain in doc["domains"].items():
        keys: set[str] = set()
        for key, term in domain["terms"].items():
            keys.add(key)
            keys |= set(term.get("aliases") or ())
        out[name] = keys
    return out


def missing(doc: dict | None = None) -> dict[str, dict[str, list[str]]]:
    """Diferença entre o que existe no código e o que está documentado.

    Devolve, por domínio, ``undocumented`` (existe no código, falta no glossário) e ``stale``
    (está no glossário, não existe mais no código). As duas direções importam: rótulo órfão
    envelhece e volta a aparecer em tela depois de o valor ter sido removido.
    """
    doc = doc or load()
    docd, out = documented(doc), {}
    for name, source in SURFACES.items():
        live = source.values()
        if live is None:
            continue
        have = docd.get(name, set())
        undocumented = sorted(live - have)
        stale = sorted(have - live - set(_alias_union(doc, name)))
        if undocumented or stale:
            out[name] = {"undocumented": undocumented, "stale": stale}
    return out


def _alias_union(doc: dict, name: str) -> set[str]:
    terms = doc["domains"].get(name, {}).get("terms", {})
    return {a for t in terms.values() for a in (t.get("aliases") or ())}


def labels(locale: str, doc: dict | None = None) -> dict[str, dict[str, str]]:
    """``{domínio: {chave: rótulo}}`` em um idioma. Sem silêncio: idioma faltante estoura."""
    doc = doc or load()
    if locale not in doc["locales"]:
        raise AssertionError(f"idioma {locale} não está no glossário")
    return {name: {key: term["label"][locale] for key, term in domain["terms"].items()}
            for name, domain in doc["domains"].items()}


def catalog(locale: str = "pt-BR") -> dict:
    """Glossário para a interface: rótulo no idioma pedido e definição em pt-BR."""
    doc = load()
    if locale not in doc["locales"]:
        locale = doc["source_locale"]
    return {
        "version": doc["version"],
        "locale": locale,
        "source_locale": doc["source_locale"],
        "note": doc["note"],
        "domains": [
            {
                "key": name,
                "title": domain["title"],
                "appears_in": domain["appears_in"],
                "note": domain.get("note"),
                "terms": [
                    {"key": key,
                     "label": term["label"][locale],
                     "label_source": term["label"][doc["source_locale"]],
                     "definition": term["definition"],
                     "aliases": list(term.get("aliases") or ())}
                    for key, term in domain["terms"].items()
                ],
            }
            for name, domain in doc["domains"].items()
        ],
        "catalogs": [
            {"table": table, "label_column": spec["label"], "explanation_column": spec["explains"],
             "note": ("Termo editorial que vive no banco, em pt-BR. A tradução para en/es está adiada para "
                      "depois do design (DEFER_POST_DESIGN) e a cobertura real está em locales.coverage_note.")}
            for table, spec in CATALOGS.items()
        ],
    }
