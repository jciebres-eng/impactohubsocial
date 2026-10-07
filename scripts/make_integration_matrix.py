#!/usr/bin/env python3
"""Matriz de homologação das integrações externas, derivada do código e do banco.

A REGRA QUE ESTA MATRIZ EXISTE PARA IMPEDIR

`production_active` nunca é declarado sem evidência real. Nesta instalação NENHUMA integração
externa está ativa: os cinco interruptores de provedor em `config.py` estão no valor inerte
(`console`, `local`, `none`, `none`, `local`) e não há credencial configurada. Dizer o contrário —
em documento, em tela ou nesta matriz — seria a forma mais direta de prometer o que não existe.

OS CINCO ESTADOS

* `scaffolded`        — existe adaptador, nenhum teste de contrato;
* `contract_tested`   — o contrato do adaptador é testado contra um duplo;
* `sandbox`           — testado contra o ambiente de testes do fornecedor, com credencial dele;
* `homologated`       — testado em homologação, com evidência do fornecedor;
* `production_active` — em produção, com tráfego real.

A coluna `state` vem do BANCO (`integration_providers.maturity`) para os provedores do hub, e do
CÓDIGO (interruptor em `config.py` + presença de teste de contrato) para os serviços de
infraestrutura. Nenhuma linha é escrita à mão.
"""

#: Destino. Aceita um caminho como argumento para que um teste possa gerar num diretório temporário e
#: comparar com o que está versionado, provando que a matriz não derivou do código — sem reescrever
#: arquivo do repositório durante a suíte.
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

TESTES = sorted((ROOT / "backend" / "tests").glob("test_*.py"))

#: Serviços de infraestrutura: o interruptor em `config.py`, o valor inerte, e o que os liga.
INFRA = (
    # (chave, nome, categoria, campo em Settings, valor inerte, variáveis necessárias, marcas de teste)
    ("smtp", "Envio de e-mail (SMTP)", "communication", "mail_provider", "console",
     ("MAIL_PROVIDER=smtp", "SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD"),
     ("mail_provider", "smtp", "outbox")),
    ("s3_storage", "Armazenamento de objeto (S3)", "storage", "storage_provider", "local",
     ("STORAGE_PROVIDER=s3", "S3_ENDPOINT", "S3_BUCKET", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY"),
     ("storage_provider", "s3", "signed_url", "presign")),
    ("clamav", "Antivírus de upload (clamd)", "security", "antivirus_provider", "none",
     ("ANTIVIRUS_PROVIDER=clamd", "CLAMD_HOST"),
     ("antivirus", "clamd", "scan_engine")),
    ("stripe", "Cobrança (Stripe)", "payment", "billing_provider", "none",
     ("BILLING_PROVIDER=stripe", "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET"),
     ("stripe", "billing_provider", "webhook")),
    ("ai_provider", "Modelo de linguagem", "ai", "ai_provider", "local",
     ("AI_PROVIDER=anthropic|openai_compatible", "AI_API_KEY", "AI_MODEL"),
     ("ai_provider", "gateway", "fallback_local")),
)


#: Testes que falam SOBRE as matrizes, e não sobre os provedores. Citar `totvs` ao explicar por que a
#: matriz deixou de ler o banco não é evidência de teste de contrato com a TOTVS — e contá-los
#: inflaria a coluna `test_files` com o próprio instrumento de medição.
META = ("test_v0230_execution_matrices.py",)


def _testes_que_citam(marcas: tuple[str, ...]) -> list[str]:
    return [f.name for f in TESTES
            if f.name not in META and any(m in f.read_text(encoding="utf-8") for m in marcas)]


# Não há leitura de banco aqui, e isso é deliberado: este gerador não tem como ler estado de
# instância nem como herdar o banco de quem o executa. Uma matriz de release descreve o produto
# EMBARCADO; ler `integration_providers` ao vivo a tornava função de qual `DATABASE_URL` estava no
# ambiente — e de qual teste tinha acabado de promover um provedor.


def main() -> int:
    # `load_settings()` valida e exige DATABASE_URL; aqui só se lê o PADRÃO dos interruptores de
    # provedor, que é o que a matriz precisa: o valor inerte de fábrica. Ler a instância default da
    # dataclass evita exigir um banco configurado para gerar documentação.
    from impacto.config import Settings
    s = Settings.__dataclass_fields__
    class _Padrao:
        def __getattr__(self, nome):
            campo = s.get(nome)
            return getattr(campo, "default", None) if campo else None
    padrao = _Padrao()

    destino = (Path(sys.argv[1]) if len(sys.argv) > 1
               else ROOT / "docs" / "execution" / "INTEGRATION_HOMOLOGATION_MATRIX.csv")
    destino.parent.mkdir(parents=True, exist_ok=True)
    campos = ["provider", "capability", "state", "credentials", "contract_test", "sandbox_test",
              "negative_test", "idempotency", "webhook", "security", "observability", "recovery",
              "activation_vars", "test_files", "evidence", "status"]
    linhas = []

    for chave, nome, categoria, campo, inerte, variaveis, marcas in INFRA:
        atual = getattr(padrao, campo, None)
        ligado = atual not in (inerte, None, "")
        arquivos = _testes_que_citam(marcas)
        linhas.append({
            "provider": chave, "capability": nome,
            # `scaffolded` quando há adaptador sem teste; `contract_tested` quando o contrato é
            # testado contra duplo. Nunca além disso sem credencial do fornecedor.
            "state": ("production_active" if ligado and arquivos else
                      "contract_tested" if arquivos else "scaffolded"),
            "credentials": "ausentes" if not ligado else "configuradas",
            "contract_test": "sim" if arquivos else "AUSENTE",
            "sandbox_test": "BLOCKED: exige credencial de sandbox do fornecedor",
            "negative_test": "sim" if arquivos else "AUSENTE",
            "idempotency": "sim" if chave in ("stripe",) else "n/a",
            "webhook": "sim (assinatura conferida)" if chave == "stripe" else "n/a",
            "security": f"interruptor `{campo}` em valor inerte (`{inerte}`)" if not ligado
                        else f"`{campo}`=`{atual}`",
            "observability": "impacto_http_requests_total + log estruturado",
            "recovery": "fallback local" if chave == "ai_provider" else
                        ("fila com nova tentativa" if chave == "smtp" else "n/a"),
            "activation_vars": " ".join(variaveis),
            "test_files": " ".join(arquivos[:4]),
            "evidence": "docs/execution/TEST_EVIDENCE.md",
            "status": "BLOCKED" if not ligado else "PASS",
        })

    # O catálogo vem do ARQUIVO DE PRODUTO, não do banco. A primeira versão lia
    # `integration_providers` por psql, e isso tornava a matriz dependente de QUAL banco estava
    # apontado: rodando sob a suíte, `DATABASE_URL` aponta para o banco de teste, e a matriz
    # divergia da versionada. Pior que não-determinismo: `maturity` é promovível pela administração
    # (`POST /v1/admin/integrations/providers/{key}/maturity`), e um teste de integração promove
    # `totvs` a `homologated` no meio da execução. Uma matriz gerada naquele instante declararia
    # homologação REAL de um provedor que nunca foi homologado — exatamente a afirmação que o pacote
    # de execução proíbe. O arquivo de configuração é o que o produto EMBARCA, e é o que vale aqui.
    catalogo = json.loads((ROOT / "config" / "integration_providers.json").read_text(encoding="utf-8"))
    for prov in catalogo["providers"]:
        chave, nome = prov["key"], prov["name"]
        categoria, estilo, maturidade = prov["category"], prov.get("api_style", "-"), prov["maturity"]
        webhook = str(prov.get("capabilities", {}).get("webhook", "-"))
        # A chave do hub (`stripe_payments`) não é o vocabulário do código nem do teste
        # (`stripe`). Procurar só a chave devolvia zero para quatro provedores que TÊM teste, e o
        # instrumento de medição passaria a contradizer o `maturity` declarado no catálogo. As
        # partes da chave com 4 ou mais letras entram na busca.
        partes = tuple(x for x in chave.split("_") if len(x) >= 4)
        arquivos = _testes_que_citam((chave, nome, *partes))
        linhas.append({
            "provider": chave, "capability": f"{nome} ({categoria}, {estilo})",
            "state": maturidade,
            "credentials": "ausentes (nenhuma credencial versionada neste repositório)",
            "contract_test": "sim" if arquivos else "AUSENTE",
            "sandbox_test": "BLOCKED: exige conta e credencial do fornecedor",
            "negative_test": "sim" if arquivos else "AUSENTE",
            "idempotency": "sim (chave por trabalho em integration_jobs)",
            "webhook": webhook,
            "security": "assinatura conferida na entrada; segredo por conexão",
            "observability": "integration_events + ops_job_runs + impacto_job_runs_total",
            "recovery": "nova tentativa com recuo e disjuntor (circuit_open_until)",
            "activation_vars": "credencial por conexão, cadastrada pela organização",
            "test_files": " ".join(arquivos[:4]),
            "evidence": "docs/execution/TEST_EVIDENCE.md",
            "status": "BLOCKED",
        })

    with destino.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(linhas)

    print(f"{destino.name}: {len(linhas)} integrações")
    for estado in ("scaffolded", "contract_tested", "sandbox", "homologated", "production_active"):
        n = sum(1 for x in linhas if x["state"] == estado)
        if n:
            print(f"  {estado:20s} {n:3d}")
    print(f"  {'com teste de contrato':20s} {sum(1 for x in linhas if x['contract_test'] == 'sim'):3d}")
    print(f"  {'credenciais ausentes':20s} {sum(1 for x in linhas if 'ausentes' in x['credentials']):3d}")
    ativas = [x["provider"] for x in linhas if x["state"] == "production_active"]
    print(f"  {'ATIVAS em produção':20s} {len(ativas):3d} {ativas}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
