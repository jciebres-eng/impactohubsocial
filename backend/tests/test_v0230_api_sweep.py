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

O QUE ELA NÃO PROVA — e é importante que fique escrito aqui, não só no relatório

Não é teste funcional de caminho feliz. Um `404` para um identificador que não existe, ou um `422`
para um corpo vazio, **é resposta correta** e conta como exercício: prova que a rota roda, que a
autorização roda, que a busca roda e que o erro é tratado. Não prova que a operação faz a coisa certa
quando recebe dados válidos — isso é o que as jornadas por persona e as suítes de domínio cobrem, e
com o escopo delas.

Dizendo de outro jeito: esta varredura prova que **nenhuma das 888 operações está quebrada**; não
prova que todas as 888 foram exercitadas com dados reais de ponta a ponta. A distinção é exatamente a
que o adendo pediu que não fosse apagada.

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
        for k in ("osc", "company", "government", "individual"):
            if k in r.kinds and k in clientes:
                return clientes[k]
    return clientes["osc"]


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
        cls.rotas = sorted(ROUTES, key=lambda r: (r.path, r.method))

        osc = new_account("osc", compliance="approved")
        grant_premium(osc)
        empresa = new_account("company", compliance="approved")
        grant_premium(empresa)
        governo = new_account("government", compliance="approved")
        individuo = new_account("individual")
        admin, _ = make_admin()
        reauth(admin)
        cls.clientes = {"anonimo": Client(), "osc": osc, "company": empresa,
                        "government": governo, "individual": individuo, "admin": admin}

        # Objetos reais para os parâmetros mais frequentes, de modo que a varredura vá além do 404
        # nas rotas que mais importam. Onde não houver objeto, o 404 limpo é o exercício.
        proj = osc.post("/v1/projects", {
            "title": "Projeto da varredura", "summary": "Resumo", "problem": "Problema declarado",
            "objectives": "Objetivo declarado", "methodology": "Método declarado",
            "territory": "BR-MT", "causes": ["educacao"], "ods": [4],
            "beneficiaries_count": 10, "budget_total_cents": 100_000})
        if proj.status in (200, 201):
            _REAIS["project_id"] = proj.json["id"]
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
        doc = osc.upload("/v1/documents", "varredura.pdf", b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n",
                         {"doc_type": "outro", "title": "Documento da varredura"})
        if doc.status in (200, 201):
            _REAIS["document_id"] = doc.json["id"]
        sol = osc.post("/v1/solutions", {
            "kind": "methodology", "title": "Solução da varredura", "summary": "Resumo declarado",
            "stage": "running", "themes": ["educacao"], "ods": [4], "uf": "MT"})
        if sol.status in (200, 201):
            _REAIS["solution_id"] = sol.json["id"]
        edital = empresa.post("/v1/calls", {
            "title": "Edital da varredura", "causes": ["educacao"], "territories": ["BR-MT"],
            "ticket_min_cents": 100000, "ticket_max_cents": 3000000, "status": "open"})
        if edital.status in (200, 201):
            _REAIS["call_id"] = edital.json["id"]

        cls.resultados: dict[str, int] = {}

    @classmethod
    def tearDownClass(cls):
        """Grava o observado para a matriz consumir — a coluna `observed` passa a ter o status REAL."""
        destino = ROOT / "docs" / "execution" / "api_sweep_observed.json"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps(cls.resultados, indent=1, sort_keys=True) + "\n",
                           encoding="utf-8")

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
                continue
            self.resultados[chave] = resp.status
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

    def test_the_observed_statuses_are_recognisable_http_answers(self):
        """Nenhum status estranho: tudo tem de ser resposta HTTP compreensível."""
        for chave, status in self.resultados.items():
            if status < 0:
                continue
            with self.subTest(chave):
                self.assertTrue(100 <= status < 500,
                                f"{chave} devolveu {status}")
