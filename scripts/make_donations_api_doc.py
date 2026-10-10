"""Regenera a tabela "## Operações" de docs/finance/DONATIONS_API.md a partir das rotas registradas em
impacto/api/donation_routes.py — método, caminho, quem pode e o resumo da PRÓPRIA rota.

v0.34.0 (E6): a tabela tinha sido escrita uma vez à mão, com as descrições deslocadas uma linha em relação aos caminhos.
Agora é gerada; `test_v0340_release_docs` confere cada linha contra o resumo da rota. Não edite a tabela à mão.

Uso: python3 scripts/make_donations_api_doc.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

DOC = ROOT / "docs" / "finance" / "DONATIONS_API.md"
START = "## Operações\n"
END = "## Webhook do provedor"


def quem(r) -> str:
    if r.auth == "none":
        return "público"
    if r.auth == "user":
        return "pessoa com conta"
    if r.auth == "admin":
        return r.permission or "administração"
    papel = {"viewer": "leitura", "member": "membro", "manager": "gestor", "owner": "dono"}.get(r.min_role or "", r.min_role or "membro")
    return f"organização ({papel})"


def rows() -> list[str]:
    from impacto import api
    from impacto.http import ROUTES
    api.load_all()
    out = []
    for r in ROUTES:
        if getattr(r.handler, "__module__", "").endswith("donation_routes"):
            resumo = " ".join((r.summary or "").split()).replace("|", "/")
            out.append(f"| `{r.method}` | `{r.path}` | {quem(r)} | {resumo} |")
    return out


def main() -> int:
    texto = DOC.read_text(encoding="utf-8")
    ini = texto.index(START) + len(START)
    fim = texto.index(END)
    tabela = "\n| Método | Caminho | Quem | O que faz |\n|---|---|---|---|\n" + "\n".join(rows()) + "\n\n"
    novo = texto[:ini] + tabela + texto[fim:]
    DOC.write_text(novo, encoding="utf-8")
    print(f"{DOC.relative_to(ROOT)}: {len(rows())} operações")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
