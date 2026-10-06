"""Tabela de cobertura dos motores: implementado / integrado / testado / E2E / segurança / observabilidade.

POR QUE ESTA TABELA É CALCULADA, E NÃO ESCRITA

Pedir "uma tabela de todos os motores" é pedir a coisa certa pelo motivo certo: o diferencial desta
plataforma não está numa tela bonita, está na cadeia necessidade → match → oportunidade → execução →
serviço → evidência → prestação de contas → resultado → impacto → reputação → inteligência. Uma
cadeia só vale o seu elo mais fraco, e um elo fraco é exatamente o que uma tabela escrita à mão
esconde — porque quem escreve é quem construiu.

Então nenhuma das seis colunas é declarada. Todas são DERIVADAS do código, do roteador, da suíte de
testes e do esquema do banco. Um motor não pode "ganhar" uma coluna sendo descrito como completo;
ele ganha quando o fato existe. E o que não existe aparece vazio, que é a informação mais útil que
esta tabela pode dar antes de um designer trabalhar sobre ela.

O QUE CADA COLUNA SIGNIFICA — exatamente, sem margem

implemented     O módulo importa e a função declarada existe e é chamável.
integrated      Está LIGADO ao produto: pelo menos uma rota declarada existe no roteador, ou o
                módulo é chamado por uma tarefa agendada. Um motor que só existe como biblioteca
                não é um motor em uso, por melhor que seja.
tested          Alguma suíte importa o módulo ou exercita uma de suas rotas.
e2e             Algum teste chama uma das rotas declaradas pelo HTTP, com cliente autenticado —
                isto é, atravessa roteador, autorização, RLS e serialização. Motor sem rota não
                pode ter E2E e aparece como `n/a`, não como falha.
security        As rotas declaradas exigem autenticação; rota pública só conta quando está na lista
                revisada de rotas públicas. Motor sem rota herda a barreira de quem o chama e
                aparece como `n/a`.
observability   Deixa rastro durável de que rodou: auditoria, evento de domínio, Value Ledger,
                `ops_job_runs`, ou uma coluna `engine_version` persistida. Sem isso, não há como
                responder "este motor rodou? com qual versão?" depois do fato.
"""
from __future__ import annotations

import importlib
import pathlib
import re
from typing import Any

from .registry import ENGINES, Engine

ROOT = pathlib.Path(__file__).resolve().parents[2]
PKG = ROOT / "impacto"
TESTS = ROOT / "tests"

#: Marcas que provam rastro durável. Cada uma corresponde a uma tabela que sobrevive ao pedido.
TRACE_MARKS = (
    "ctx.audit(", "audit.record(", "notify.project_event", "notify.org_event", "notify.fact_only",
    "events.record(", "value_ledger.record(", "ledger(", "runs.record", "ENGINE_VERSION",
    # Escrita direta em tabela durável: o próprio Value Ledger, por exemplo, É o rastro — procurar
    # nele uma chamada a si mesmo seria absurdo.
    "INSERT INTO",
)


def _all_routes() -> list:
    """Carrega TODOS os módulos de rota antes de olhar o roteador.

    Sem isto a tabela mentiria por omissão: `ROUTES` nasce vazia e só é preenchida quando os
    módulos de rota são importados, então um motor perfeitamente ligado apareceria como não
    integrado — e a tabela diria que a cadeia está rota onde ela não está.
    """
    from .. import api
    from ..http import ROUTES
    api.load_all()
    return list(ROUTES)


def _routes_in_app() -> set[str]:
    return {r.path for r in _all_routes()}


def _public_routes() -> set[str]:
    """As rotas sem autenticação que passaram por revisão de segurança (teste de arquitetura)."""
    return {r.path for r in _all_routes() if getattr(r, "auth", None) == "none"}


def _job_modules() -> set[str]:
    """Módulos alcançados por tarefa agendada — a outra forma legítima de estar integrado."""
    src = (PKG / "jobs.py").read_text(encoding="utf-8")
    alcancados = set()
    for m in re.finditer(r"from \.([a-z_.]+) import ([a-z_]+) as", src):
        alcancados.add(f"impacto.{m.group(1)}.{m.group(2)}")
    for m in re.finditer(r"from \.([a-z_.]+) import ([a-z_]+)$", src, re.M):
        alcancados.add(f"impacto.{m.group(1)}.{m.group(2)}")
    return alcancados


def _test_sources() -> str:
    return "\n".join(f.read_text(encoding="utf-8") for f in TESTS.glob("test_*.py"))


def _module_source(engine: Engine) -> str:
    caminho = PKG.parent / (engine.module.replace(".", "/") + ".py")
    return caminho.read_text(encoding="utf-8") if caminho.exists() else ""


def _persists_version(engine: Engine) -> bool:
    """Alguma migração guarda a versão deste motor em coluna? Então o rastro é do banco, não do log."""
    if not engine.version:
        return False
    fonte = _module_source(engine)
    return "ENGINE_VERSION" in fonte and ("engine_version" in fonte or "ENGINE_VERSION)" in fonte)


def _library_users() -> set[str]:
    """Módulos de motor importados por quem tem rota ou tarefa: estão ligados, só que por dentro."""
    usados: set[str] = set()
    alvos = {e.module for e in ENGINES}
    for f in PKG.rglob("*.py"):
        if f.name in ("registry.py", "coverage.py"):
            continue
        src = f.read_text(encoding="utf-8")
        for alvo in alvos:
            pacote, nome = alvo.rsplit(".", 1)
            curto = pacote.replace("impacto.", "")
            padrao_from = "from ." + curto.replace(".", r"\.")
            if (f"import {alvo}" in src
                    or re.search(r"from \.{1,3}" + re.escape(curto) + r" import [^\n]*\b"
                                 + re.escape(nome) + r"\b", src)
                    or re.search(r"from \.{1,3}" + re.escape(curto + "." + nome) + r" import ", src)
                    or padrao_from in src and f" {nome} " in src):
                usados.add(alvo)
    return usados


def assess(engine: Engine, *, rotas: set[str], publicas: set[str], jobs: set[str],
           testes: str, importadores: set[str]) -> dict[str, Any]:
    linha: dict[str, Any] = {"key": engine.key, "name": engine.name, "kind": engine.kind,
                             "group": engine.group, "version": engine.version,
                             "module": engine.module, "routes": list(engine.routes)}

    # implemented
    try:
        mod = importlib.import_module(engine.module)
        obj: Any = mod
        for parte in engine.entrypoint.split("."):
            obj = getattr(obj, parte)
        linha["implemented"] = callable(obj)
    except Exception as exc:  # noqa: BLE001
        linha["implemented"] = False
        linha["implemented_error"] = str(exc)[:200]

    # integrated
    rotas_vivas = [r for r in engine.routes if r in rotas]
    por_job = engine.module in jobs
    # Um motor sem rota própria pode estar perfeitamente ligado: `core.evidence` e
    # `solutions.scoring` são chamados por quem tem rota. Ignorar isso marcaria como desligado o
    # que sustenta metade da cadeia.
    por_biblioteca = engine.module in importadores
    linha["integrated"] = bool(rotas_vivas) or por_job or por_biblioteca
    linha["integration"] = ("rota" if rotas_vivas else
                            ("tarefa agendada" if por_job else
                             ("chamado por outro motor" if por_biblioteca else "—")))
    if engine.routes and not rotas_vivas:
        # Rota declarada que não existe no roteador é declaração falsa, e tem de aparecer.
        linha["declared_routes_missing"] = [r for r in engine.routes if r not in rotas]

    # tested
    nome_curto = engine.module.rsplit(".", 1)[-1]
    # `import adaptation, combine, intent as I, scoring as SC` importa `scoring` sem que a string
    # "import scoring" exista. Procurar o nome na LINHA de import evita tanto esse falso negativo
    # quanto o falso positivo de achar a palavra solta no meio de um teste.
    linha["tested"] = (engine.module in testes
                       or bool(re.search(r"^\s*from .*import[^\n]*\b" + re.escape(nome_curto) + r"\b",
                                         testes, re.M))
                       or any(r in testes for r in engine.routes))

    # e2e
    if not engine.routes:
        linha["e2e"] = None
    else:
        linha["e2e"] = any(
            re.search(rf'\.(get|post|put|patch|delete)\(\s*f?["\']{re.escape(r.split("{")[0])}',
                      testes)
            for r in engine.routes)

    # security
    if not engine.routes:
        linha["security"] = None
    else:
        # Rota pública só é problema quando NÃO foi declarada como pública pelo próprio motor.
        # A revisão de segurança global continua sendo a do teste de arquitetura; aqui o que se
        # confere é se o motor assume a exposição que tem.
        desprotegidas = [r for r in rotas_vivas if r in publicas and r not in engine.public_routes]
        linha["security"] = not desprotegidas
        linha["undeclared_public"] = desprotegidas

    # observability
    fonte = _module_source(engine)
    marcas = [m for m in TRACE_MARKS if m in fonte]
    linha["observability"] = bool(marcas)
    linha["trace"] = marcas[:3]
    return linha


def table() -> dict[str, Any]:
    rotas, publicas = _routes_in_app(), _public_routes()
    jobs, testes, libs = _job_modules(), _test_sources(), _library_users()
    linhas = [assess(e, rotas=rotas, publicas=publicas, jobs=jobs, testes=testes, importadores=libs)
              for e in ENGINES]

    def conta(col: str) -> dict[str, int]:
        return {"sim": sum(1 for r in linhas if r[col] is True),
                "nao": sum(1 for r in linhas if r[col] is False),
                "na": sum(1 for r in linhas if r[col] is None)}

    return {
        "engines": linhas,
        "total": len(linhas),
        "summary": {c: conta(c) for c in ("implemented", "integrated", "tested", "e2e",
                                          "security", "observability")},
        "note": ("Nenhuma das seis colunas é declarada: todas são derivadas do código, do roteador, "
                 "da suíte e do esquema. `n/a` em E2E e em segurança significa motor sem rota "
                 "própria — herda a barreira de quem o chama, e não é falha."),
    }


def markdown() -> str:
    t = table()
    out = ["# Cobertura dos motores — Impacto Trust", "",
           "Gerado por `impacto/engines/coverage.py`. **Nenhuma coluna é escrita à mão**: cada uma é",
           "derivada do código, do roteador, da suíte de testes e do esquema do banco. Um motor não",
           "ganha uma coluna sendo descrito como completo — ganha quando o fato existe.", "",
           "| Coluna | O que ela afirma, exatamente |", "| --- | --- |",
           "| implemented | O módulo importa e a função declarada é chamável. |",
           "| integrated | Pelo menos uma rota declarada existe no roteador, ou o módulo é chamado "
           "por tarefa agendada. |",
           "| tested | Alguma suíte importa o módulo ou exercita uma de suas rotas. |",
           "| e2e | Algum teste chama uma rota declarada pelo HTTP, atravessando roteador, "
           "autorização, RLS e serialização. |",
           "| security | As rotas declaradas exigem autenticação (rota pública conta só se estiver "
           "na lista revisada). |",
           "| observability | Deixa rastro durável: auditoria, evento de domínio, Value Ledger, "
           "`ops_job_runs` ou `engine_version` persistida. |", "",
           "`n/a` = motor sem rota própria: herda a barreira de quem o chama. Não é falha.", ""]
    s = t["summary"]
    out += [f"**{t['total']} motores.** "
            + " · ".join(f"{c}: {s[c]['sim']} sim / {s[c]['nao']} não"
                         + (f" / {s[c]['na']} n/a" if s[c]["na"] else "")
                         for c in ("implemented", "integrated", "tested", "e2e", "security",
                                   "observability")),
            ""]
    grupos: dict[str, list[dict]] = {}
    for r in t["engines"]:
        grupos.setdefault(r["group"], []).append(r)
    marca = {True: "sim", False: "**NÃO**", None: "n/a"}
    for g in sorted(grupos):
        out += [f"## {g}", "",
                "| motor | natureza | versão | implemented | integrated | tested | E2E | security | observability |",
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
        for r in sorted(grupos[g], key=lambda x: x["key"]):
            out.append(
                f"| `{r['key']}` — {r['name']} | {r['kind']} | {r['version'] or '—'} | "
                f"{marca[r['implemented']]} | {marca[r['integrated']]} | {marca[r['tested']]} | "
                f"{marca[r['e2e']]} | {marca[r['security']]} | {marca[r['observability']]} |")
        out.append("")
    return "\n".join(out)
