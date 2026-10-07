"""Varredura funcional das 888 operações: cada uma é CHAMADA, e nenhuma pode responder 5xx.

A RESSALVA QUE ESTE ARQUIVO RESPONDE

Adendo de auditoria de 07/10/2026, ponto 3:

    "A matriz de API cobre as 888 operações por classificação e controle de autorização. O log relata
    221 chamadas HTTP contra endpoints sob teste por classe; não afirmar que '888 rotas foram todas
    exercitadas ponta a ponta individualmente'."

A crítica é correta e a resposta não é reescrever a frase. `API_AUTHORIZATION_MATRIX.csv` provava
duas coisas boas — que toda operação está classificada, e que o ponto de estrangulamento de cada
classe recusa quem não deve passar — e não provava uma terceira: que cada operação, uma a uma,
*responde*.

O QUE ESTA VARREDURA PROVA, EXATAMENTE

Cada uma das 888 operações é invocada por HTTP real, com o cliente da persona que a alcança, e a
resposta é registrada. A asserção central é **nenhum 5xx**. Um 500 significa exceção não tratada: a
rota quebrou antes de decidir qualquer coisa.

ATÉ ONDE A CHAMADA CHEGA — MEDIDO, NÃO PRESUMIDO

A primeira versão deste arquivo afirmava que uma resposta 422 prova que "a rota roda, a autorização
roda, **a busca roda** e o erro é tratado". Isso era falso, e uma auditoria independente apontou o
lugar exato: em `impacto/http.py`, `spec.body.model_validate(payload)` roda **antes** de
`spec.handler(*args)`. Nas operações recusadas por corpo incompleto, o handler **nunca é entrado** —
nenhuma linha dele é exercitada. Um `NameError` dentro de qualquer um deles passaria batido.

Então a varredura passou a registrar, por operação, **até qual camada a chamada chegou**:

  `roteamento`   a requisição não passou da autorização (401/403 de `authorize()`)
  `validacao`    o schema recusou o corpo: roteamento + autorização exercitados, handler NÃO entrado
  `handler`      a resposta veio do handler: o código da operação foi executado

A conta por camada está no relatório e é a afirmação honesta. O que esta varredura prova é que
**nenhuma das 888 operações levanta exceção não tratada na camada que ela alcança** — e diz quantas
alcançam cada camada. Não prova caminho feliz com dados válidos: isso é o que as jornadas por persona
e as suítes de domínio cobrem, com o escopo delas.

O QUE É DELIBERADAMENTE PULADO

Operações destrutivas ou que sequestram o ambiente da suíte, cada uma com motivo escrito em
`PULADAS`. Uma exclusão sem motivo é um buraco que ninguém lembra de ter aberto — e um teste abaixo
exige que toda exclusão tenha causa.
"""
from __future__ import annotations

import json
import re
import unittest

from tests.support import (Client, ROOT, grant_premium, make_admin, new_account, reauth,
                           server)

#: Identificador sintaticamente válido que não existe: a resposta correta é 404.
INEXISTENTE = "00000000-0000-4000-8000-000000000000"

#: Códigos levantados ANTES do handler, em `impacto/http.py`. Uma resposta com um destes prova que a
#: requisição foi roteada e autorizada (ou recusada ali), e NÃO que o handler rodou.
ANTES_DO_HANDLER_AUTORIZACAO = frozenset({
    "unauthenticated", "permission_denied", "admin_only", "mfa_required", "forbidden",
    "wrong_org_kind", "bad_origin", "csrf", "no_active_org",
})
#: O código que o próprio roteador usa quando o schema recusa o corpo ou a query.
ANTES_DO_HANDLER_VALIDACAO = "validation_error"

#: Operações puladas, com motivo. Cada uma sequestraria o ambiente dos testes seguintes.
PULADAS: dict[str, str] = {
    "POST /v1/admin/kill-switch": "acionaria o interruptor e pararia a escrita para o resto da suíte; "
                                  "tem travessia própria em test_e2e_v0230_moderation_journey.py",
    "POST /v1/auth/logout": "encerraria a sessão do cliente da varredura no meio dela, e as "
                            "operações seguintes mediriam ausência de sessão em vez da rota",
    "POST /v1/auth/logout-all": "idem, e em todas as sessões abertas — inclusive as das outras "
                                "personas construídas para esta varredura",
    "POST /v1/privacy/delete-account": "remove a conta; tem suíte própria em test_v0190_lgpd_deletion.py",
    "POST /v1/admin/integrations/run-worker": "dispara o trabalhador de integrações e muda estado "
                                              "observado por outros testes",
}

#: Parâmetros de caminho que a varredura resolve com objeto REAL, para ir além do 404.
#: O resto recebe `INEXISTENTE` — e um 404 limpo é exercício válido da rota.
_REAIS: dict[str, str] = {}


def _principal(r, clientes: dict) -> Client:
    """O cliente da persona que ALCANÇA esta rota, segundo a declaração da própria rota."""
    if r.auth == "none":
        return clientes["anonimo"]
    if r.auth == "admin":
        return clientes["admin"]
    if r.auth == "user":
        return clientes["osc"]
    if r.kinds:
        # `provider` e `platform` faltavam na primeira versão, e as 6 rotas de `kinds=("provider",)`
        # caíam no cliente OSC e recebiam 403 `wrong_org_kind` — a persona Profissional, uma das
        # cinco, simplesmente não existia na varredura. Uma auditoria independente apontou isso.
        for k in ("osc", "company", "government", "individual", "provider"):
            if k in r.kinds and k in clientes:
                return clientes[k]
        if "platform" in r.kinds:
            return clientes["admin"]
    return clientes["osc"]


def _camada(status: int, codigo: str | None) -> str:
    """Até qual camada a chamada chegou. Decidido pelo `code` da resposta, que o roteador declara."""
    if codigo == ANTES_DO_HANDLER_VALIDACAO:
        return "validacao"
    if status in (401, 403) and (codigo in ANTES_DO_HANDLER_AUTORIZACAO or codigo is None):
        return "roteamento"
    return "handler"


def _caminho(path: str) -> str:
    def troca(m):
        nome = m.group(1)
        return _REAIS.get(nome, INEXISTENTE)
    return re.sub(r"\{(\w+)\}", troca, path)


class EveryOneOfTheEightHundredEightyEightOperationsAnswersTests(unittest.TestCase):
    """888 chamadas HTTP reais. Nenhuma pode devolver 5xx."""

    @classmethod
    def setUpClass(cls):
        server()
        from impacto import api
        from impacto.http import ROUTES
        api.load_all()
        # DELETE POR ÚLTIMO. Ordenando só por (path, method), `DELETE /v1/projects/{project_id}`
        # roda ANTES de `GET /v1/projects/{project_id}` — o objeto do arranjo era apagado e todos os
        # GETs seguintes do mesmo recurso respondiam 404, desperdiçando o arranjo que a varredura
        # acabara de construir. Uma auditoria independente mediu isso: dos quatro objetos criados,
        # só um sobrevivia até ser usado.
        cls.rotas = sorted(ROUTES, key=lambda r: (r.method == "DELETE", r.path, r.method))

        osc = new_account("osc", compliance="approved")
        grant_premium(osc)
        empresa = new_account("company", compliance="approved")
        grant_premium(empresa)
        governo = new_account("government", compliance="approved")
        individuo = new_account("individual")
        profissional = new_account("provider")
        admin, _ = make_admin()
        reauth(admin)
        cls.clientes = {"anonimo": Client(), "osc": osc, "company": empresa,
                        "government": governo, "individual": individuo,
                        "provider": profissional, "admin": admin}

        # Objetos reais para os parâmetros mais frequentes, de modo que a varredura vá além do 404
        # nas rotas que mais importam. Onde não houver objeto, o 404 limpo é o exercício.
        _REAIS["org_id"] = osc.org_id
        _REAIS["user_id"] = osc.user["id"]

        # Objetos construídos PELA PRÓPRIA varredura, nunca lidos do banco com `LIMIT 1`.
        #
        # A primeira versão procurava uma solução, um documento e um edital quaisquer que já
        # existissem. Isso tornava o resultado função de QUAIS TESTES rodaram antes: numa execução
        # isolada a busca devolvia nada e a rota respondia 404; na suíte completa, outro arquivo já
        # havia criado o objeto e a mesma rota respondia 200. A matriz passaria a divergir de si
        # mesma entre execuções, e a trava de deriva acusaria uma diferença que não é do produto.
        #
        # Construir aqui custa quatro chamadas e torna a varredura reprodutível.
        # `assert`, não `if status in (200, 201)`. A primeira versão silenciava a falha: o
        # `summary` da solução tinha 16 caracteres contra o mínimo de 20 do schema, a criação
        # devolvia 422, e TODAS as 32 rotas de `{solution_id}` rodavam contra um id inexistente —
        # enquanto o comentário dizia "ir além do 404 nas rotas que mais importam". Arranjo que
        # falha em silêncio é pior que arranjo ausente, porque mente sobre a cobertura.
        def _criar(resp, oque: str) -> str:
            assert resp.status in (200, 201), f"arranjo da varredura falhou em {oque}: {resp.body}"
            return resp.json["id"]

        _REAIS["project_id"] = _criar(osc.post("/v1/projects", {
            "title": "Projeto da varredura", "summary": "Resumo declarado do projeto da varredura",
            "problem": "Problema declarado", "objectives": "Objetivo declarado",
            "methodology": "Método declarado", "territory": "BR-MT", "causes": ["educacao"],
            "ods": [4], "beneficiaries_count": 10, "budget_total_cents": 100_000}), "projeto")
        _REAIS["document_id"] = _criar(osc.upload(
            "/v1/documents", "varredura.pdf", b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n",
            {"doc_type": "outro", "title": "Documento da varredura"}), "documento")
        _REAIS["solution_id"] = _criar(osc.post("/v1/solutions", {
            "kind": "methodology", "title": "Solução da varredura",
            "summary": "Resumo declarado da solução criada para a varredura funcional das operações.",
            "stage": "running", "themes": ["educacao"], "ods": [4], "uf": "MT"}), "solução")
        _REAIS["call_id"] = _criar(empresa.post("/v1/calls", {
            "title": "Edital da varredura", "causes": ["educacao"], "territories": ["BR-MT"],
            "ticket_min_cents": 100000, "ticket_max_cents": 3000000, "status": "open"}), "edital")

        cls.resultados: dict[str, int] = {}
        cls.camadas: dict[str, str] = {}

    @classmethod
    def tearDownClass(cls):
        """Grava o observado para a matriz consumir — a coluna `observed` passa a ter o status REAL."""
        destino = ROOT / "docs" / "execution" / "api_sweep_observed.json"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps(cls.resultados, indent=1, sort_keys=True) + "\n",
                           encoding="utf-8")
        (destino.parent / "api_sweep_layers.json").write_text(
            json.dumps(cls.camadas, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    def _corpo(self, r):
        """Corpo mínimo. Vazio é suficiente: 422 por campo obrigatório ausente é resposta CORRETA e
        exercita a camada de validação, que é parte da operação."""
        return {} if r.body else None

    def test_every_operation_is_invoked_and_none_returns_a_server_error(self):
        falhas: list[str] = []
        pulou = 0
        for r in self.rotas:
            chave = f"{r.method} {r.path}"
            if chave in PULADAS:
                pulou += 1
                self.resultados[chave] = -1
                self.camadas[chave] = "pulada"
                continue
            cliente = _principal(r, self.clientes)
            caminho = _caminho(r.path)
            try:
                if r.multipart:
                    resp = cliente.upload(caminho, "varredura.pdf", b"%PDF-1.4\n%%EOF\n",
                                          {"doc_type": "outro", "title": "Varredura"})
                elif r.raw_body:
                    resp = cliente.request(r.method, caminho, raw=b"{}",
                                           ctype="application/json")
                else:
                    resp = cliente.request(r.method, caminho, self._corpo(r))
            except Exception as exc:  # noqa: BLE001 - exceção do cliente também é falha da operação
                falhas.append(f"{chave} → exceção {type(exc).__name__}: {exc}")
                self.resultados[chave] = -2
                self.camadas[chave] = "excecao"
                continue
            codigo = None
            try:
                codigo = (resp.json or {}).get("code")
            except Exception:  # noqa: BLE001 - resposta sem JSON é normal (204, texto)
                codigo = None
            self.resultados[chave] = resp.status
            self.camadas[chave] = _camada(resp.status, codigo)
            if resp.status >= 500:
                falhas.append(f"{chave} → {resp.status} {(resp.body or b'')[:200]!r}")

        invocadas = len(self.rotas) - pulou
        self.assertEqual(falhas, [],
                         f"{len(falhas)} operação(ões) responderam 5xx de {invocadas} invocadas:\n"
                         + "\n".join(falhas[:40]))
        self.assertGreaterEqual(invocadas, 880,
                                f"só {invocadas} operações foram invocadas: a varredura mediria pouco")

    def test_the_sweep_reached_every_route_the_router_serves(self):
        """Contraprova: a varredura não pode ter deixado rota de fora em silêncio."""
        self.assertEqual(len(self.resultados), len(self.rotas),
                         "há rota servida pelo roteador que a varredura não registrou")

    def test_every_skipped_operation_has_a_written_reason(self):
        from impacto.http import ROUTES
        servidas = {f"{r.method} {r.path}" for r in ROUTES}
        for chave, motivo in PULADAS.items():
            with self.subTest(chave):
                self.assertIn(chave, servidas, f"{chave} está em PULADAS e não existe mais")
                self.assertGreater(len(motivo), 40, f"{chave} pulada sem motivo auditável")

    def test_the_sweep_says_how_far_each_call_got_and_does_not_overstate_it(self):
        """A conta por camada é a afirmação honesta — e tem de existir para TODAS as operações.

        Sem esta conta, a varredura diz "888 invocadas, nenhum 5xx" e o leitor conclui que 888
        handlers foram exercitados. Não foram: os recusados pela validação de schema param antes do
        handler, e isso é propriedade do roteador (`model_validate` roda antes de `spec.handler`),
        não escolha da varredura.
        """
        self.assertEqual(set(self.camadas), set(self.resultados),
                         "há operação com status registrado e sem camada")
        conta = {}
        for camada in self.camadas.values():
            conta[camada] = conta.get(camada, 0) + 1
        # O que não pode acontecer: nenhuma operação chegar ao handler, ou a classificação colapsar
        # numa única categoria — nos dois casos a medida deixaria de informar.
        self.assertGreater(conta.get("handler", 0), 300,
                           f"poucas operações chegaram ao handler: {conta}")
        self.assertGreater(conta.get("validacao", 0), 100,
                           f"a varredura deixou de reconhecer recusa de schema: {conta}")
        self.assertEqual(conta.get("excecao", 0), 0, f"houve exceção de cliente: {conta}")

    def test_the_professional_persona_actually_reaches_its_own_routes(self):
        """Contraprova da correção: as rotas de `kinds=("provider",)` não podem responder
        `wrong_org_kind`, porque agora existe cliente dessa persona."""
        from impacto import api
        from impacto.http import ROUTES
        api.load_all()
        so_provider = [f"{r.method} {r.path}" for r in ROUTES if r.kinds == ("provider",)]
        self.assertTrue(so_provider, "nenhuma rota exclusiva de provider: o teste mediria nada")
        for chave in so_provider:
            with self.subTest(chave):
                self.assertNotEqual(self.camadas.get(chave), "roteamento",
                                    f"{chave} parou na autorização: a persona Profissional não "
                                    "está alcançando a própria rota")

    def test_the_observed_statuses_are_recognisable_http_answers(self):
        """Nenhum status estranho: tudo tem de ser resposta HTTP compreensível."""
        for chave, status in self.resultados.items():
            if status < 0:
                continue
            with self.subTest(chave):
                self.assertTrue(100 <= status < 500,
                                f"{chave} devolveu {status}")
