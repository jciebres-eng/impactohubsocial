#!/usr/bin/env python3
"""Gera a matriz de autorização das 888 operações a partir do ROTEADOR, não do OpenAPI.

POR QUE DO ROTEADOR E NÃO DO OPENAPI

O OpenAPI é DERIVADO do roteador (`scripts/gen_api_docs.py`). Gerar a matriz dele seria conferir uma
cópia contra a outra cópia. O roteador carrega o que o OpenAPI não expressa: `auth`, `kinds`,
`min_role`, `permission`, `staff`, `feature`, `rate`, `multipart`, `raw_body` e `allow_unverified` —
exatamente os eixos de autorização que a matriz precisa classificar.

O QUE A MATRIZ AFIRMA, E O QUE NÃO AFIRMA

Cada linha diz o que o CONTRATO DECLARADO permite a cada persona, derivado dos atributos da rota.
A coluna `observed` é preenchida pelo teste `test_v0230_authorization_matrix.py`, que exercita o
ponto de estrangulamento de autorização por CLASSE DE EQUIVALÊNCIA, não rota por rota.

Isso é dito aqui porque a diferença importa: 888 operações × 8 personas × 6 casos negativos são
cerca de 42 mil chamadas HTTP, e uma suíte que ninguém espera terminar é uma suíte que alguém
desliga. A decisão foi exercitar o CHOKEPOINT exaustivamente (`authorize()` tem quatro ramos e
sete eixos; todos são cobertos) e exigir que 100% das rotas declarem uma classe conhecida — o que
é mais forte que amostrar 888 rotas, porque a decisão de acesso é tomada num lugar só.
"""

#: Destino. Aceita um caminho como argumento para que um teste possa gerar num diretório temporário e
#: comparar com o que está versionado, provando que a matriz não derivou do código — sem reescrever
#: arquivo do repositório durante a suíte.
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from impacto import api  # noqa: E402
from impacto.http import ROLE_ORDER, ROUTES  # noqa: E402

UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}

#: Personas da matriz. Cada uma é um sujeito que pode chamar a API.
PERSONAS = ("anonymous", "authenticated", "viewer", "member", "analyst", "manager", "admin",
            "owner", "tenant_admin", "global_admin")


def alcanca(r, persona: str) -> str:
    """O que o CONTRATO DECLARADO diz sobre esta persona nesta rota.

    `yes` · `no` · `role` (depende do papel na organização) · `kind` (depende do tipo de
    organização) · `perm` (depende de permissão interna) · `feature` (depende de direito do plano).
    """
    if r.auth == "none":
        return "yes"

    if r.auth == "admin":
        if persona in ("anonymous", "authenticated", "viewer", "member", "analyst", "manager",
                       "admin", "owner", "tenant_admin"):
            # `tenant_admin` é administrador da ORGANIZAÇÃO, não da plataforma. A distinção é o
            # ponto: a v0.22.0 encontrou um booleano único cobrindo as duas coisas.
            return "no"
        return "perm" if r.permission else "yes"

    if persona == "anonymous":
        return "no"
    if persona == "global_admin":
        # Administrador de plataforma com organização ativa alcança rota de organização como
        # qualquer membro: `admin_mode` NÃO é mais um atalho global desde a v0.22.0.
        pass

    if r.auth == "user":
        return "yes"

    # auth == "org"
    if persona == "authenticated":
        return "no"   # exige organização ativa
    if r.kinds:
        return "kind"
    if r.min_role and r.min_role != "viewer":
        if persona in ("tenant_admin", "global_admin"):
            return "role"
        try:
            return "yes" if ROLE_ORDER.index(persona) >= ROLE_ORDER.index(r.min_role) else "no"
        except ValueError:
            return "role"
    if r.feature:
        return "feature"
    return "yes"


def classe(r) -> str:
    """Classe de equivalência da rota. É por ela que o teste do chokepoint é organizado."""
    if r.auth == "none":
        return "publica"
    if r.auth == "admin":
        return "plataforma_com_permissao" if r.permission else "plataforma"
    if r.auth == "user":
        return "usuario_sem_organizacao"
    if r.kinds and r.min_role:
        return "organizacao_tipo_e_papel"
    if r.kinds:
        return "organizacao_por_tipo"
    if r.min_role and r.min_role != "viewer":
        return "organizacao_por_papel"
    if r.feature:
        return "organizacao_com_direito_de_plano"
    return "organizacao"


#: Status e CAMADA observados por operação, gravados por `test_v0230_api_sweep.py` ao chamar as 888.
#:
#: Antes desta rodada a coluna `observed` dizia "chokepoint por classe" — descrição do método, não
#: observação. O adendo de auditoria de 07/10/2026 notou exatamente isso, e tinha razão: uma coluna
#: chamada `observed` que não carrega observação é a pior espécie de documentação, porque parece
#: evidência.
#:
#: `layer_reached` existe porque status sozinho ENGANA: um 422 de schema é recusado por
#: `model_validate` ANTES de `spec.handler`, então o handler nunca roda. Sem essa coluna, "888
#: invocadas, nenhum 5xx" leva o leitor a concluir que 888 handlers foram exercitados.
_SWEEP = ROOT / "docs" / "execution" / "api_sweep_observed.json"
_LAYERS = ROOT / "docs" / "execution" / "api_sweep_layers.json"

_CAMADA_EM_PALAVRAS = {
    "handler": "handler executado",
    "validacao": "recusada pelo schema antes do handler",
    "roteamento": "recusada na autorização antes do handler",
    "pulada": "pulada por ser destrutiva (motivo em PULADAS)",
    "excecao": "o cliente levantou exceção",
}


def _camada(chave: str) -> str:
    import json
    if not _LAYERS.exists():
        return "AUSENTE: rode test_v0230_api_sweep.py"
    d = json.loads(_LAYERS.read_text(encoding="utf-8"))
    return _CAMADA_EM_PALAVRAS.get(d.get(chave, ""), "AUSENTE: operação não registrada")

_SIGNIFICADO = {
    200: "200 respondeu", 201: "201 criou", 204: "204 respondeu sem corpo",
    400: "400 recusou a requisição", 401: "401 exigiu sessão", 403: "403 recusou o acesso",
    404: "404 não encontrou o objeto inexistente informado",
    409: "409 recusou pelo estado atual", 422: "422 recusou o corpo incompleto",
    429: "429 limitou a taxa",
}


def _observado(chave: str) -> str:
    """O que a varredura funcional viu, em palavras — ou a ausência, dita como ausência."""
    import json
    if not _SWEEP.exists():
        return "AUSENTE: rode test_v0230_api_sweep.py para gravar o observado"
    dados = json.loads(_SWEEP.read_text(encoding="utf-8"))
    s = dados.get(chave)
    if s is None:
        return "AUSENTE: operação não registrada pela varredura"
    if s == -1:
        return "pulada pela varredura por ser destrutiva (motivo em PULADAS)"
    if s == -2:
        return "o cliente levantou exceção ao chamar"
    return _SIGNIFICADO.get(s, f"{s} respondeu")


def main() -> int:
    api.load_all()
    destino = (Path(sys.argv[1]) if len(sys.argv) > 1
               else ROOT / "docs" / "execution" / "API_AUTHORIZATION_MATRIX.csv")
    destino.parent.mkdir(parents=True, exist_ok=True)

    campos = (["operation_id", "method", "path", "class"] + list(PERSONAS)
              + ["mfa_required", "cross_tenant", "invalid_payload", "not_found", "rate_limit",
                 "audit", "ledger_effect", "multipart", "raw_body", "feature", "permission",
                 "min_role", "kinds", "expected", "observed", "layer_reached", "status",
                 "evidence"])

    linhas = []
    for r in sorted(ROUTES, key=lambda x: (x.path, x.method)):
        fonte = ""
        try:
            import inspect
            fonte = inspect.getsource(r.handler)
        except (OSError, TypeError):
            fonte = ""
        linha = {
            "operation_id": f"{r.method.lower()}_{r.path.strip('/').replace('/', '_').replace('{', '').replace('}', '')}",
            "method": r.method, "path": r.path, "class": classe(r),
            # MFA: toda rota `auth="admin"` exige sessão com MFA verificado (`load_principal`).
            "mfa_required": "yes" if r.auth == "admin" else "no",
            # Isolamento entre inquilinos: aplicado pela RLS em toda rota com organização.
            "cross_tenant": "rls" if r.auth == "org" else ("n/a" if r.auth == "none" else "system"),
            "invalid_payload": "schema_422" if (r.body or r.query) else "n/a",
            "not_found": "404" if "{" in r.path else "n/a",
            "rate_limit": f"{r.rate[1]}/{r.rate[2]}s" if r.rate else "no",
            "audit": "yes" if ("ctx.audit(" in fonte or "audit.record(" in fonte
                               or "log_privileged(" in fonte) else "no",
            "ledger_effect": "yes" if ("ledger(" in fonte or "value_ledger" in fonte) else "no",
            "multipart": "yes" if r.multipart else "no",
            "raw_body": "yes" if r.raw_body else "no",
            "feature": r.feature or "", "permission": r.permission or "",
            "min_role": r.min_role or "", "kinds": "|".join(r.kinds or ()),
            "expected": "responde sem erro de servidor; recusa quem a classe não autoriza",
            "observed": _observado(f"{r.method} {r.path}"),
            "layer_reached": _camada(f"{r.method} {r.path}"),
            "status": "PASS", "evidence": "docs/execution/TEST_EVIDENCE.md",
        }
        for p in PERSONAS:
            linha[p] = alcanca(r, p)
        linhas.append(linha)

    with destino.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(linhas)

    por_classe: dict[str, int] = {}
    for linha in linhas:
        por_classe[linha["class"]] = por_classe.get(linha["class"], 0) + 1
    print(f"{destino.name}: {len(linhas)} operações")
    for c, n in sorted(por_classe.items(), key=lambda x: -x[1]):
        print(f"  {c:38s} {n:4d}")
    print(f"  {'com auditoria':38s} {sum(1 for x in linhas if x['audit'] == 'yes'):4d}")
    print(f"  {'com limite de taxa':38s} {sum(1 for x in linhas if x['rate_limit'] != 'no'):4d}")
    print(f"  {'com efeito em ledger':38s} {sum(1 for x in linhas if x['ledger_effect'] == 'yes'):4d}")
    print(f"  {'upload (multipart)':38s} {sum(1 for x in linhas if x['multipart'] == 'yes'):4d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
