#!/usr/bin/env python3
"""Fotografia do que a OSC de demonstração vê pela API — para provar que os dados SOBREVIVEM a reinício.

    DEMO_PASSWORD=... python3 scripts/stack_persistence.py --base http://127.0.0.1:8080 contar

Imprime uma linha estável ("projetos=3 candidaturas=2 ...") a partir das listas da própria API. O job
`pilha-do-zero` do CI roda isto antes e depois de reiniciar o contêiner da aplicação e exige as duas
linhas iguais: o que as jornadas criaram está no banco, não na memória do processo.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request

LISTAS = {"projetos": "/v1/projects", "candidaturas": "/v1/applications", "rascunhos": "/v1/drafts",
          "diagnosticos": "/v1/diagnoses", "conversas": "/v1/conversations", "propostas": "/v1/proposals?box=all",
          "ideias": "/v1/ideas"}


def _req(base: str, metodo: str, rota: str, corpo=None, token: str | None = None) -> dict:
    h = {"Accept": "application/json", "X-Auth-Mode": "token"}
    dados = None
    if corpo is not None:
        dados = json.dumps(corpo).encode()
        h["Content-Type"] = "application/json"
    if token:
        h["Authorization"] = f"Bearer {token}"
    with urllib.request.urlopen(urllib.request.Request(base + rota, data=dados, method=metodo, headers=h), timeout=30) as r:
        return json.loads(r.read() or b"{}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("acao", choices=["contar"])
    a = ap.parse_args()
    senha = os.getenv("DEMO_PASSWORD")
    if not senha:
        print("defina DEMO_PASSWORD", file=sys.stderr)
        return 2
    base = a.base.rstrip("/")
    tok = _req(base, "POST", "/v1/auth/login", {"email": "osc@demo.impacto.local", "password": senha})["access_token"]
    partes = []
    for nome, rota in LISTAS.items():
        d = _req(base, "GET", rota, token=tok)
        n = d.get("total", len(d.get("items", []))) if isinstance(d, dict) else len(d)
        partes.append(f"{nome}={n}")
    linha = " ".join(partes)
    if "projetos=0" in linha:
        print(f"nenhum projeto visível — a pilha não tem os dados das jornadas: {linha}", file=sys.stderr)
        return 1
    print(linha)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
