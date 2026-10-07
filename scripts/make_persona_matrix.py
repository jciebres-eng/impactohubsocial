#!/usr/bin/env python3
"""Matriz de jornadas por persona, derivada dos testes que existem.

POR QUE DERIVADA, E NÃO ESCRITA À MÃO

Uma matriz de jornadas escrita à mão descreve o que alguém pretendia testar. Esta descreve o que a
suíte EXECUTA: cada passo aponta para o arquivo, a classe e o método que o exercitam, e um passo sem
teste aparece como `AUSENTE` em vez de ficar de fora da lista.

O mapeamento persona → jornada é declarado aqui porque é informação de produto: qual papel percorre
qual caminho. Os PASSOS, não — eles são lidos dos arquivos de teste, por nome de método e por
asserção, para que a matriz não possa afirmar cobertura que não existe.

A DISTINÇÃO QUE A PRIMEIRA VERSÃO DESTE INSTRUMENTO APAGAVA

A primeira versão só varria `test_e2e*.py` e declarou 11 passos AUSENTE. Os 11 tinham cobertura — em
`test_api_workflow.py` ("Jornada completa via API real"), `test_v0200_complaints.py`,
`test_v0230_kill_switch.py` e outros. Era defeito do INSTRUMENTO DE MEDIÇÃO, não do produto.

Mas a correção não é varrer tudo e chamar tudo de jornada: um teste que exercita UMA rota não é uma
jornada de persona. Então a coluna `coverage` distingue, por medida mecânica do corpo do teste:

  `navegador`  o teste dirige um navegador real (`.goto(`) — ponta a ponta pela TELA
  `travessia`  o teste alcança 5+ rotas distintas, OU faz 5+ chamadas contra 3+ rotas — pela API
  `rota`       menos que isso — prova a REGRA do passo, não o caminho até ele

A CONTA QUE MEDE ATOS, E NÃO ROTAS DISTINTAS

Medir só rotas distintas subestimava a travessia que REVISITA a mesma rota em estados diferentes — e
é isso que uma jornada de incidente faz: escreve antes da parada, tenta escrever durante, escreve
depois de liberar. São três atos na MESMA rota, e a repetição é justamente o que está sob teste.

Mas trocar rotas por atos subestimava o contrário: o teste que percorre doze rotas dentro de um laço
tem UM ponto de chamada. Os dois sinais são evidência de travessia, então vale qualquer um dos dois —
largura (5+ rotas distintas) ou profundidade (5+ atos sobre 3+ rotas, para não promover o teste que
bate dez vezes no mesmo lugar).

A JORNADA PARTIDA EM MÉTODOS NUMERADOS

`FullImpactJourney` percorre a jornada inteira da OSC, mas partida em `test_01_…` a `test_12_…` que
compartilham estado de classe e rodam em ordem alfabética. Medido método a método, cada um parece
uma unidade; o passo 7 só funciona porque o passo 6 rodou. Uma classe com 3 ou mais métodos
numerados é uma travessia POR CONSTRUÇÃO, e todos os seus métodos herdam essa classificação.

A MEDIDA QUE A SEGUNDA VERSÃO ERRAVA

A segunda versão media só o comprimento: 5+ passos era jornada, menos era unidade. Isso punia a
persona pública, cuja jornada é curta POR NATUREZA — um terceiro abre uma página e confere um
documento, e isso é ponta a ponta completo em dois passos. Comprimento não é o critério; o critério
é se o teste atravessa as camadas. Um teste de navegador atravessa todas, mesmo curto.

Um passo coberto só por `rota` NÃO é marcado PASS como jornada; recebe `PASS (rota)`, e o relatório
final conta os dois separadamente. O release não pode afirmar travessia onde só existe unidade.
"""

#: Destino. Aceita um caminho como argumento para que um teste possa gerar num diretório temporário e
#: comparar com o que está versionado, provando que a matriz não derivou do código — sem reescrever
#: arquivo do repositório durante a suíte.
from __future__ import annotations

import ast
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
TESTES = ROOT / "backend" / "tests"

#: Travessia por LARGURA: rotas distintas alcançadas. Por PROFUNDIDADE: chamadas sobre um piso de rotas.
LARGURA_PARA_SER_JORNADA = 5
ATOS_PARA_SER_JORNADA = 5
ROTAS_PARA_SER_JORNADA = 3

#: Ordem de preferência ao escolher a evidência de um passo: ponta a ponta antes de unidade.
FORTE = ("navegador", "travessia", "rota")

#: Persona → jornada → (passo, marcas que o identificam nos testes).
#: A marca é o nome do método, da classe, ou um trecho que o teste escreve.
JORNADAS: dict[str, dict[str, tuple[tuple[str, tuple[str, ...]], ...]]] = {
    "OSC": {
        "Da ideia ao documento verificado": (
            ("cadastro e sessão", ("test_01_register_verify_and_login", "visitor_signup_login")),
            ("compliance aprovado", ("/v1/compliance/request-review",)),
            ("projeto", ("test_02_create_project", "/v1/projects")),
            ("diagnóstico", ("diagnostic", "diagnostico", "J1Idea")),
            ("prontidão", ("readiness", "prontidao")),
            ("evidência", ("test_07_evidence", "evidences")),
            ("indicador com fonte", ("test_06_indicator_requires_a_sourced_baseline",)),
            ("candidatura", ("/v1/applications",)),
            ("checklist e transições", ("/transition",)),
            ("execução", ("in_execution", "execution")),
            ("prestação de contas", ("relatorio", "impact", "report")),
            ("verificação pública", ("verificar", "J1IdeaToVerifiedDocument")),
        ),
        "Cofre e montagem de documento": (
            ("envio de documento", ("/v1/documents",)),
            ("montagem por modelo", ("assembly", "montagem", "J4Assembly")),
            ("revisão profissional", ("professional_review", "J4AssemblyReviewAndSignature")),
            ("assinatura em duas camadas", ("two_layer_signature", "/v1/signatures/challenge")),
        ),
    },
    "Financiador / empresa": {
        "Da tese à decisão": (
            ("cadastro", ("company",)),
            ("tese e filtros", ("/v1/org/funder-profile",)),
            ("edital próprio", ("/v1/calls",)),
            ("triagem de candidaturas", ("/applications",)),
            ("conflito de interesse", ("/conflict",)),
            ("decisão e aporte", ("/commitments",)),
            ("desembolso declarado", ("/v1/commitments/", "disbursed")),
            ("validação de indicador", ("review_value", "indicator-values")),
        ),
    },
    "Profissional": {
        "Do perfil à atuação": (
            ("perfil", ("provider", "profissional")),
            ("credencial submetida", ("/v1/org/credentials",)),
            ("credencial decidida pela plataforma", ("/v1/admin/trust/credentials",)),
            ("oportunidade", ("marketplace", "oportunidade")),
            ("parecer / atuação", ("professional_review", "parecer")),
        ),
    },
    "Administração / moderação": {
        "Da denúncia à medida": (
            ("entrada com MFA", ("test_admin_logs_in_with_mfa",)),
            ("denúncia recebida", ("/v1/reports",)),
            ("apuração", ("/v1/admin/reports",)),
            ("manifestação do denunciado", ("/manifestacao",)),
            ("conclusão", ("/conclude",)),
            ("medida", ("/v1/admin/enforcement",)),
            ("recurso", ("/recurso", "appeal-decision")),
            ("sinais de risco", ("/v1/admin/risk",)),
            ("auditoria", ("/v1/admin/audit",)),
        ),
        "Operação interna": (
            ("controladoria", ("/v1/controladoria",)),
            ("financeiro e aprovação", ("/v1/aprovacoes", "/v1/financeiro")),
            ("contabilidade", ("/v1/contabilidade",)),
            ("integridade dos dados", ("/v1/admin/integrity",)),
            ("interruptor de emergência", ("/v1/admin/kill-switch",)),
        ),
    },
    "Público (sem sessão)": {
        "Transparência": (
            ("páginas públicas", ("test_private_pages_redirect_visitor_to_login", "PUBLIC")),
            ("busca na central", ("test_visitor_search_guide_assistant_and_demo",)),
            ("verificação de documento", ("test_third_party_verifies_without_logging_in",)),
            ("revogação visível", ("test_public_page_shows_revocation",)),
            ("código inexistente", ("test_unknown_code_shows_friendly_error",)),
            ("campanha e cotas", ("test_public_campaign_shows_remaining_quotas",)),
        ),
    },
}

_ROTA = re.compile(r"/v1/[A-Za-z0-9_\-{}/]+")
_NAVEGA = re.compile(r"\.goto\(")
_NUMERADO = re.compile(r"^test_\d+_")
_ATO = re.compile(r"\.(?:get|post|put|patch|del|upload|request)\(")

#: Métodos numerados a partir dos quais a CLASSE conta como jornada sequencial de estado compartilhado.
NUMERADOS_PARA_SER_JORNADA = 3


def _indice() -> tuple[dict[str, list[str]], dict[str, str]]:
    """(marca → onde aparece) e (onde → `jornada`|`rota`), varrendo TODOS os testes."""
    onde_de: dict[str, list[str]] = {}
    tipo_de: dict[str, str] = {}
    for f in sorted(TESTES.glob("test_*.py")):
        texto = f.read_text(encoding="utf-8")
        try:
            arvore = ast.parse(texto)
        except SyntaxError:
            continue
        for no in ast.walk(arvore):
            if not isinstance(no, ast.ClassDef):
                continue
            # Preparação compartilhada conta para todos os métodos da classe.
            comum = "".join(ast.get_source_segment(texto, m) or "" for m in no.body
                            if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                            and not m.name.startswith("test"))
            metodos = [m for m in no.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                       and m.name.startswith("test")]
            sequencial = sum(1 for m in metodos if _NUMERADO.match(m.name)) >= NUMERADOS_PARA_SER_JORNADA
            for m in metodos:
                trecho = (ast.get_source_segment(texto, m) or "") + comum
                onde = f"{f.name}::{no.name}::{m.name}"
                rotas = len(set(_ROTA.findall(trecho)))
                largura = rotas >= LARGURA_PARA_SER_JORNADA
                profundidade = (len(_ATO.findall(trecho)) >= ATOS_PARA_SER_JORNADA
                                and rotas >= ROTAS_PARA_SER_JORNADA)
                if _NAVEGA.search(trecho):
                    tipo_de[onde] = "navegador"
                elif sequencial or largura or profundidade:
                    tipo_de[onde] = "travessia"
                else:
                    tipo_de[onde] = "rota"
                for marca in {m.name, no.name, *re.findall(r'["\']([^"\']{4,80})["\']', trecho), *_ROTA.findall(trecho)}:
                    onde_de.setdefault(marca, []).append(onde)
    return onde_de, tipo_de


def main() -> int:
    idx, tipo = _indice()
    marcas = list(idx)
    destino = (Path(sys.argv[1]) if len(sys.argv) > 1
               else ROOT / "docs" / "execution" / "PERSONA_E2E_MATRIX.csv")
    destino.parent.mkdir(parents=True, exist_ok=True)
    campos = ["persona", "journey", "step", "expected", "observed", "coverage", "authorization",
              "audit", "evidence", "status"]
    linhas = []
    for persona, jornadas in JORNADAS.items():
        for jornada, passos in jornadas.items():
            for passo, procuradas in passos:
                achados: list[str] = []
                for marca in procuradas:
                    achados += idx.get(marca, [])
                    if marca not in idx:  # marca como prefixo/substring de outra
                        achados += [o for m in marcas if marca in m for o in idx[m]]
                achados = sorted(dict.fromkeys(achados))
                cobertura = "nenhuma"
                escolhidos: list[str] = []
                for kind in FORTE:
                    desse = [o for o in achados if tipo[o] == kind]
                    if desse:
                        cobertura, escolhidos = kind, desse[:3]
                        break
                linhas.append({
                    "persona": persona, "journey": jornada, "step": passo,
                    "expected": "passo percorrido com sucesso e recusado quando sem permissão",
                    "observed": " ".join(escolhidos) if escolhidos else "AUSENTE",
                    "coverage": cobertura,
                    "authorization": "classe da rota conferida em API_AUTHORIZATION_MATRIX.csv",
                    "audit": "evento em audit_events quando o passo altera estado",
                    "evidence": "docs/execution/TEST_EVIDENCE.md",
                    # O vocabulário de estados é o do pacote (TODO…WAIVED) e não admite variação:
                    # `PASS (rota)` seria estado inventado. O passo passou — a coluna `coverage` diz
                    # COMO, e o relatório final conta travessia e rota separadamente.
                    "status": "FAILED" if cobertura == "nenhuma" else "PASS",
                })

    with destino.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(linhas)

    print(f"{destino.name}: {len(linhas)} passos")
    conta = {k: sum(1 for o in tipo.values() if o == k) for k in FORTE}
    print(f"testes varridos: {len(tipo)} "
          f"({conta['navegador']} de navegador, {conta['travessia']} travessias de API, {conta['rota']} de rota)")
    for persona in JORNADAS:
        da = [x for x in linhas if x["persona"] == persona]
        c = {k: sum(1 for x in da if x["coverage"] == k) for k in FORTE}
        print(f"  {persona:28s} navegador {c['navegador']:2d}  travessia {c['travessia']:2d}  "
              f"rota {c['rota']:2d}  ausente {len(da) - sum(c.values()):2d}")
    pontas = sum(1 for x in linhas if x["coverage"] in ("navegador", "travessia"))
    print(f"  {'PONTA A PONTA':28s} {pontas}/{len(linhas)}")
    falhos = [f'{x["persona"]} · {x["step"]}' for x in linhas if x["coverage"] == "nenhuma"]
    print(f"  {'SEM COBERTURA ALGUMA':28s} {len(falhos)}")
    for x in falhos:
        print(f"      {x}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
