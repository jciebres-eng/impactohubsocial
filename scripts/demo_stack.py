#!/usr/bin/env python3
"""Executa as JORNADAS e o ROBÔ DE TELAS contra uma pilha já em pé (Docker do zero, ou outra).

    DEMO_PASSWORD=... DEMO_TOTP_SECRET=... python3 scripts/demo_stack.py \\
        --base http://127.0.0.1:8080 --mailpit http://127.0.0.1:8025 \\
        --dsn postgresql://ADMIN:SENHA@127.0.0.1:5432/impacto --telas --saida dist-stack

É o mesmo roteiro dos testes `test_v0250_jornadas` e `test_v0250_todas_as_telas`, sem o servidor de
teste: a pilha é a que a imagem Docker sobe, com banco novo, migrações, seed de demonstração e
o papel `impacto_app`. O que muda é só de onde vêm:
  - o código de assinatura (e-mail): Mailpit (`--mailpit`) ou pasta de e-mails (`--outbox`);
  - o segredo do segundo fator das contas internas: DEMO_TOTP_SECRET, o mesmo que o seed usou;
  - a consulta que escolhe registros reais para as telas com `:id`: conexão `--dsn` (somente leitura).

Sai com código 1 se algum passo de jornada ou alguma tela falhar. Nunca imprime senha.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from collections import Counter
from email import message_from_bytes
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))


def codigo_por_pasta(pasta: Path):
    def ler(email: str) -> str:
        for arq in sorted(pasta.glob("*.eml"), reverse=True):
            msg = message_from_bytes(arq.read_bytes())
            if msg["To"] == email and "assinar" in (msg["Subject"] or "").lower():
                achado = re.search(r"\b(\d{6})\b", msg.get_payload(decode=True).decode())
                if achado:
                    return achado.group(1)
        raise AssertionError(f"código de assinatura não encontrado em {pasta} para {email}")
    return ler


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--mailpit")
    ap.add_argument("--outbox")
    ap.add_argument("--dsn", help="conexão (leitura) para escolher registros das telas com parâmetro")
    ap.add_argument("--telas", action="store_true", help="roda também o robô das 218 telas (Playwright)")
    ap.add_argument("--saida", default="dist-stack")
    ap.add_argument("--sem-jornadas", action="store_true", help="só o robô de telas (dados já criados)")
    ap.add_argument("--axe", help="caminho do axe.min.js: roda a auditoria WCAG A/AA em cada tela (uma vez por rota)")
    ap.add_argument("--axe-trava", action="store_true",
                    help="violação crítica ou grave do axe reprova (sem isto, o axe só relata)")
    a = ap.parse_args()
    senha, segredo = os.getenv("DEMO_PASSWORD", ""), os.getenv("DEMO_TOTP_SECRET", "")
    if not senha or not segredo:
        print("defina DEMO_PASSWORD e DEMO_TOTP_SECRET (os mesmos usados no seed)", file=sys.stderr)
        return 2
    os.environ.setdefault("TEST_ADMIN_DATABASE_URL", "postgresql://naousado@127.0.0.1:1/naousado")
    from tests import demo_journeys
    from tests.support import fresh_totp
    if a.mailpit:
        codigo = demo_journeys.codigo_por_mailpit(a.mailpit.rstrip("/"))
    elif a.outbox:
        codigo = codigo_por_pasta(Path(a.outbox))
    else:
        print("informe --mailpit ou --outbox (de onde ler o código de assinatura)", file=sys.stderr)
        return 2
    saida = Path(a.saida)
    saida.mkdir(parents=True, exist_ok=True)

    if a.sem_jornadas:
        res = {"passos": [], "falhas": [], "atalhos": [], "ids": {}}
    else:
        res = demo_journeys.Jornadas(a.base.rstrip("/"), senha, codigo, lambda _email: segredo).run()
    (saida / "jornadas.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    por = Counter(p["jornada"] for p in res["passos"])
    print(f"jornadas: {len(por)} · passos: {len(res['passos'])} · falhas: {len(res['falhas'])}")
    for p in res["falhas"]:
        print(f"  FALHA [{p['jornada']}] {p['passo']}: {p['metodo']} {p['rota']} → {p['status']} {p['erro'][:200]}")
    falhou = bool(res["falhas"])

    if a.telas:
        if not a.dsn:
            print("--telas exige --dsn", file=sys.stderr)
            return 2
        from playwright.sync_api import sync_playwright

        from impacto import seed_dev
        from impacto.db.pq import Connection
        from tests import screen_crawler as robo
        conn = Connection(a.dsn)
        conn.execute_script("SET default_transaction_read_only = on;")

        def consulta(sql):
            return conn.scalar(sql)
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            try:
                axe_src = Path(a.axe).read_text(encoding="utf-8") if a.axe else None
                linhas = robo.rodar(browser, a.base.rstrip("/"), senha, seed_dev.DEMO_EMAILS, consulta,
                                    lambda: fresh_totp(segredo), axe_src=axe_src)
            finally:
                browser.close()
        campos = ["rota", "persona", "deve_ver", "url", "estado", "detalhe", "chamadas_api", "api_4xx", "ms"]
        with (saida / "telas.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=campos, extrasaction="ignore")
            w.writeheader()
            for x in linhas:
                w.writerow({**x, "api_4xx": " | ".join(x["api_4xx"])})
        sucesso = {robo.OK, robo.VAZIA, robo.RECUSA_CERTA}
        falhas = [x for x in linhas if x["estado"] not in sucesso
                  and not (x["estado"] == "SEM_REGISTRO" and "não participa" in x["detalhe"])]
        rotas = {x["rota"] for x in linhas}
        ok = {x["rota"] for x in linhas if x["deve_ver"] and x["estado"] in (robo.OK, robo.VAZIA)}
        print(f"telas: {len(rotas)} rotas · {len(linhas)} visitas · {len(ok)} abertas com dado real · "
              f"estados {dict(Counter(x['estado'] for x in linhas))}")
        for x in falhas:
            print(f"  FALHA {x['estado']} {x['persona']} {x['url'] or x['rota']} {x['detalhe'][:160]}")
        falhou = falhou or bool(falhas) or rotas != ok
        if a.axe:
            auditadas = [x for x in linhas if x.get("axe") is not None]
            regras: dict[str, dict] = {}
            for x in auditadas:
                for v in x["axe"]:
                    r = regras.setdefault(v["id"], {"impacto": v["impact"], "ajuda": v["help"], "telas": [], "elementos": 0})
                    r["telas"].append(x["rota"])
                    r["elementos"] += v["nodes"]
            (saida / "axe.json").write_text(json.dumps({"versao_wcag": "2.0/2.1 A e AA", "telas_auditadas": len(auditadas),
                                                        "telas_sem_violacao": sum(1 for x in auditadas if not x["axe"]),
                                                        "regras": regras}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            print(f"axe-core: {len(auditadas)} telas auditadas · {sum(1 for x in auditadas if not x['axe'])} sem violação · "
                  f"{len(regras)} regra(s) violada(s)")
            ordem = {"critical": 0, "serious": 1, "moderate": 2, "minor": 3}
            for rid, r in sorted(regras.items(), key=lambda kv: (ordem.get(kv[1]["impacto"], 9), -len(kv[1]["telas"]))):
                exemplo = ", ".join(sorted(set(r["telas"]))[:4])
                nivel = "error" if a.axe_trava and r["impacto"] in ("critical", "serious") else "warning"
                print(f"::{nivel} title=axe {r['impacto']}: {rid}::{len(set(r['telas']))} tela(s), {r['elementos']} elemento(s) — "
                      f"{r['ajuda']} — ex.: {exemplo}")
            graves = [rid for rid, r in regras.items() if r["impacto"] in ("critical", "serious")]
            nao_rodou = [x["rota"] for x in auditadas if any(v["id"] == "axe-nao-rodou" for v in x["axe"])]
            if a.axe_trava and (graves or nao_rodou):
                print(f"axe: {len(graves)} regra(s) crítica(s)/grave(s); axe não rodou em {len(nao_rodou)} tela(s)")
                falhou = True
    return 1 if falhou else 0


if __name__ == "__main__":
    raise SystemExit(main())
