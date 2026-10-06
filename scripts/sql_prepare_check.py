"""Verifica cada consulta SQL de um módulo pedindo ao PostgreSQL para PREPARAR (não executar).

POR QUE ESTE SCRIPT EXISTE: na v0.16.0 escrevi nove consultas contra colunas que eu *achava* que existiam
(`organizations.name`, `calls.org_id`, `diagnosis_versions.project_id`, `max(uuid)`, `match_results`). Nenhuma
falharia no import, no ruff ou no type-check — só em produção, na primeira requisição. PREPARE resolve os nomes de
tabela, coluna, função e tipo sem rodar nada, então um defeito desses aparece em segundos.

Uso:
    DB="host=127.0.0.1 port=5432 dbname=impacto_dev user=postgres" \
      python3 scripts/sql_prepare_check.py backend/impacto/network

Campos interpolados: consultas montadas com f-string (nome de coluna variável, lista de SET) precisam de um valor
de teste em HOLES. Um campo novo sem valor PARA o script em vez de passar calado — é de propósito.
"""
import ast
import os
import pathlib
import re
import subprocess
import sys

DSN = os.environ.get("DB", "host=127.0.0.1 port=5432 dbname=impacto_dev user=postgres")
ROOT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "backend/impacto/network")

SQL_START = re.compile(r"^\s*(SELECT|INSERT|UPDATE|DELETE|WITH)\b", re.IGNORECASE)


#: Nome de coluna/identificador plausível para cada campo interpolado nas f-strings dos motores.
#: Sem isto, uma f-string vira pedaços e o verificador acusa erro de sintaxe onde não há.
HOLES = {
    "relationships.py": {"{col}": "target_org_id", "{', '.join(sets)}": "visibility = 'private'"},
    "marketplace.py": {"{col}": "project_id", "{', '.join(sets)}": "headline = 'x'"},
    "profiles.py": {"{owner_col}": "org_id", "{col}": "org_id", "{', '.join(sets)}": "bio = 'x'"},
    "proposals.py": {"{', '.join(sets)}": "title = 'x'"},
    "readiness.py": {}, "recommendation.py": {}, "notify.py": {}, "events.py": {}, "__init__.py": {},
    "workspace.py": {"{', '.join(sets)}": "status = 'x'"},
    "impact_report.py": {"{', '.join(sets)}": "summary = 'x'"},
    "messaging.py": {"{', '.join(sets)}": "subject = 'x'"},
    # camada econômica (0018+)
    "programs.py": {"{', '.join(sets)}": "title = 'x'", "{len(args) - 1}": "1", "{len(args)}": "2"},
    "value_ledger.py": {"{', '.join(sets)}": "note = 'x'"},
    "billable.py": {"{', '.join(sets)}": "active = false", "{', '.join(names)}": "rule_key",
                    "{ph}": "'premium.readiness_analysis'", "{len(args)}": "1"},
    "legal.py": {"{', '.join(sets)}": "status = 'yellow'"},
    "payments.py": {},
    # camada de impacto contextualizado (0025+)
    "equity.py": {}, "territory.py": {}, "frameworks.py": {},
    "claims.py": {"{owner_col}": "org_id", "{table}": "projects"},
    "reputation.py": {}, "seals.py": {}, "lookups.py": {}, "responsibility.py": {"{owner}": "org_id", "{table}": "projects"},
}


def _render(node, holes):
    """Reconstrói uma f-string (JoinedStr) trocando cada campo por um identificador plausível."""
    parts = []
    for v in node.values:
        if isinstance(v, ast.Constant):
            parts.append(str(v.value))
        else:
            src = ast.unparse(v)
            if src not in holes:
                raise SystemExit(f"campo interpolado sem valor de teste: {src} — acrescente a HOLES")
            parts.append(holes[src])
    return "".join(parts)


def literals(path):
    """Devolve cada consulta SQL do arquivo (literal ou f-string), com a linha onde começa."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out, inside = [], set()
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            head = next((str(v.value) for v in node.values if isinstance(v, ast.Constant)), "")
            if not SQL_START.match(head):
                continue
            txt = _render(node, HOLES.get(path.name, {}))
            if SQL_START.match(txt):
                out.append((node.lineno, txt))
            inside.update(id(v) for v in ast.walk(node))
    for node in ast.walk(tree):
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and id(node) not in inside and SQL_START.match(node.value)):
            out.append((node.lineno, node.value))
    return out


def prepare(sql, n):
    """Prepara a consulta trocando $n por cast genérico quando o tipo não é inferível."""
    body = sql
    # f-strings dos motores deixam {}: substitui por um nome plausível para que o parser aceite.
    body = re.sub(r"\{[^}]*\}", "x", body)
    stmt = f"PREPARE chk_{n} AS {body}"
    p = subprocess.run(["psql", DSN, "-v", "ON_ERROR_STOP=1", "-qAtc", stmt], check=False,
                       capture_output=True, text=True)
    return p.returncode == 0, (p.stderr or "").strip().splitlines()[:2]


fails = 0
checked = 0
for path in sorted(ROOT.glob("*.py")):
    for lineno, sql in literals(path):
        if "$1" not in sql and "FROM" not in sql.upper() and "INTO" not in sql.upper():
            continue
        checked += 1
        ok, err = prepare(sql, checked)
        if not ok:
            fails += 1
            print(f"\n✗ {path}:{lineno}")
            print("  " + " ".join(err))
            print("  SQL: " + " ".join(sql.split())[:220])
print(f"\n{checked} consultas verificadas, {fails} com erro")
sys.exit(1 if fails else 0)
