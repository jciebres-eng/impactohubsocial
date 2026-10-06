"""Retenção de dados: a classe declarada é conferida contra a regra real do banco.

Um documento de retenção que ninguém executa é uma intenção. Aqui a classe de cada vínculo
(``org_id``/``user_id``) sai de ``config/data_retention.json`` e é comparada com a ação real da chave
estrangeira no PostgreSQL. Se alguém mudar uma migração e transformar guarda obrigatória em cascata —
ou criar um vínculo novo que BLOQUEIA exclusão sem ninguém decidir — o teste reprova.

    python3 -m impacto.core.retention        # escreve DATA_RETENTION.md
"""
from __future__ import annotations

import json
from pathlib import Path

from ..db.pq import Connection

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "config" / "data_retention.json"
MARKDOWN = ROOT / "DATA_RETENTION.md"

#: ação da FK no banco -> classe de retenção
BY_ACTION = {"c": "deletable_with_parent", "n": "anonymizable",
             "a": "retainable", "r": "retainable", "none": "audit_only"}

#: Gatilhos que RECUSAM remoção da linha. Quando um deles existe, ele vence a cascata da chave: o
#: gatilho não olha papel, então nem o proprietário do banco apaga. A classe efetiva passa a ser
#: `append_only` — e, por consequência, a organização inteira deixa de ser removível.
APPEND_ONLY_TRIGGERS = ("forbid_mutation",)

SQL_LINKS = (
    "SELECT c.relname AS tabela, a.attname AS coluna,"
    "       coalesce(con.confdeltype::text, 'none') AS acao,"
    "       coalesce(cf.relname, '') AS referencia"
    "  FROM pg_class c"
    "  JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped"
    "  LEFT JOIN pg_constraint con ON con.conrelid = c.oid AND con.contype = 'f'"
    "       AND a.attnum = ANY(con.conkey) AND array_length(con.conkey, 1) = 1"
    "  LEFT JOIN pg_class cf ON cf.oid = con.confrelid"
    " WHERE c.relkind = 'r' AND c.relnamespace = 'public'::regnamespace"
    "   AND a.attname IN ('org_id', 'user_id')"
    " ORDER BY c.relname, a.attname"
)


def load() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


SQL_APPEND_ONLY = (
    "SELECT DISTINCT c.relname AS tabela"
    "  FROM pg_trigger tg"
    "  JOIN pg_class c ON c.oid = tg.tgrelid"
    "  JOIN pg_proc p ON p.oid = tg.tgfoid"
    " WHERE NOT tg.tgisinternal AND c.relnamespace = 'public'::regnamespace"
    "   AND p.proname = ANY($1::text[])"
)


def links(conn: Connection) -> list[dict]:
    """Todos os vínculos a organização/titular, com a classe EFETIVA.

    Efetiva, não nominal: a ação da chave estrangeira diz o que o PostgreSQL faria, e o gatilho
    append-only diz se ele consegue. Classificar pela chave sozinha produziria uma política que
    promete cascata onde a remoção é impossível — que é exatamente o erro que a v0.19.0 encontrou.
    """
    indeleveis = {r["tabela"] for r in conn.query(SQL_APPEND_ONLY, list(APPEND_ONLY_TRIGGERS))}
    saida = []
    for r in conn.query(SQL_LINKS):
        classe = BY_ACTION[r["acao"]]
        if r["tabela"] in indeleveis and classe == "deletable_with_parent":
            classe = "append_only"
        saida.append({**r, "key": f"{r['tabela']}.{r['coluna']}", "class": classe,
                      "append_only": r["tabela"] in indeleveis})
    return saida


def audit(conn: Connection, doc: dict | None = None) -> dict:
    """Compara declaração com realidade.

    * ``mismatched``: a classe declarada não é a que o banco implementa — o pior caso, porque a
      política diz uma coisa e o produto faz outra.
    * ``undeclared_non_cascade``: vínculo que NÃO é cascata e ninguém declarou. Pode ser uma guarda
      legítima recém-criada ou um bloqueio acidental de exclusão; os dois precisam de decisão humana.
    * ``declared_but_absent``: declaração que aponta para coluna que não existe mais.
    """
    doc = doc or load()
    declarado = doc["declared"]
    reais = {item["key"]: item for item in links(conn)}
    mismatched, undeclared = [], []
    for key, item in reais.items():
        esperado = declarado.get(key, {}).get("class")
        if esperado is None:
            if item["class"] != "deletable_with_parent":
                undeclared.append({"key": key, "actual": item["class"], "fk_action": item["acao"]})
        elif esperado != item["class"]:
            mismatched.append({"key": key, "declared": esperado, "actual": item["class"],
                               "fk_action": item["acao"]})
    return {
        "links": len(reais),
        "mismatched": sorted(mismatched, key=lambda x: x["key"]),
        "undeclared_non_cascade": sorted(undeclared, key=lambda x: x["key"]),
        "declared_but_absent": sorted(set(declarado) - set(reais)),
        "by_class": {cls: sum(1 for i in reais.values() if i["class"] == cls)
                     for cls in sorted(set(BY_ACTION.values()) | {"append_only"})},
    }


def markdown(conn: Connection) -> str:
    from ..clock import today
    doc, resultado = load(), audit(conn)
    reais = {i["key"]: i for i in links(conn)}
    out = [f"# Retenção de dados — Impacto Trust (política v{doc['version']})", "",
           "> Gerado por `python3 -m impacto.core.retention` contra o banco real. Não edite à mão.", "",
           doc["note"], "", f"Conferido em {today().isoformat()} · "
           f"{resultado['links']} vínculos a organização ou titular.", "",
           "## Classes", "", "| classe | ação da chave | o que acontece | base |", "| --- | --- | --- | --- |"]
    for nome, c in doc["classes"].items():
        out.append(f"| `{nome}` | `{c['fk_action']}` | {c['meaning']} | {c['basis']} |")
    out += ["", "## Distribuição real", "", "| classe | vínculos |", "| --- | --- |"]
    for cls, n in resultado["by_class"].items():
        out.append(f"| `{cls}` | {n} |")
    out += ["", f"Regra padrão: {doc['default_rule']}", "",
            "## Vínculos declarados", "",
            "| vínculo | classe | ação real | motivo |", "| --- | --- | --- | --- |"]
    for key, d in sorted(doc["declared"].items()):
        real = reais.get(key, {}).get("acao", "—")
        out.append(f"| `{key}` | `{d['class']}` | `{real}` | {d['reason']} |")
    fluxo = doc["account_deletion_flow"]
    out += ["", "## Exclusão de conta", "", f"Rota: `{fluxo['route']}`", "", "**O que faz:**", ""]
    out += [f"* {x}" for x in fluxo["does"]]
    out += ["", "**O que NÃO faz:**", ""] + [f"* {x}" for x in fluxo["does_not"]]
    out += ["", "## Divergências encontradas na conferência", ""]
    if resultado["mismatched"] or resultado["undeclared_non_cascade"] or resultado["declared_but_absent"]:
        out.append("```json")
        out.append(json.dumps({k: resultado[k] for k in
                               ("mismatched", "undeclared_non_cascade", "declared_but_absent")},
                              ensure_ascii=False, indent=2))
        out.append("```")
    else:
        out.append("Nenhuma: cada vínculo declarado é o que o banco implementa, e todo vínculo não "
                   "declarado é cascata.")
    out.append("")
    return "\n".join(out)
