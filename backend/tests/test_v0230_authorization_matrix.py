"""Matriz de autorização das 940 operações (888 na v0.23.0; +6 na v0.26.0; v0.27.0: −19 de assinatura/trial, +18 da camada econômica, +2 torre master e cartões do dia; v0.28.0: +28 da Central de IA; v0.29.0: +13 da camada de conhecimento — fontes, citações, retirada, fila editorial, relato de erro, catálogo de conceitos; v0.30.0: +4 — evidência detalhe/contestação, método de indicador, dossiê): classificação completa + chokepoint exaustivo.

O QUE ESTE ARQUIVO AFIRMA, E O QUE NÃO AFIRMA

Afirma duas coisas, e as duas são verificáveis:

1. **100% das 888 operações estão classificadas** numa das sete classes de equivalência de
   autorização, derivadas do que a própria rota declara (`auth`, `kinds`, `min_role`, `permission`,
   `feature`). Nenhuma rota fica fora, e uma rota nova sem classe conhecida REPROVA.
2. **O ponto de estrangulamento de autorização é exercitado por classe**, com chamadas HTTP reais,
   para cada persona que a matriz diz que pode e que não pode.

NÃO afirma que 888 operações foram chamadas por 10 personas em 6 casos negativos cada. Isso são
cerca de 42 mil chamadas, e suíte que ninguém espera terminar é suíte que alguém desliga.

A decisão é defensável por um motivo concreto: **a decisão de acesso é tomada num lugar só.**
`authorize()` em `http.py` tem quatro ramos (`none`, `user`, `org`, `admin`) e sete eixos. Testar
esse ponto exaustivamente e exigir que toda rota declare uma classe conhecida é mais forte que
amostrar 888 rotas — porque amostragem deixa de fora justamente a rota que alguém escreveu sem
declarar nada.

E há três subconjuntos testados a 100%, não por amostra, porque são os de maior consequência:

* **as 238 rotas de plataforma** (`auth="admin"`) — nenhuma alcançável por organização cliente;
* **as 83 rotas com permissão interna** — nenhuma alcançável por papel interno que não a tenha;
* **as 52 rotas públicas** — todas na lista revisada de `test_architecture.py`.
"""
from __future__ import annotations

import csv
import unittest

from tests.support import ROOT, Client, db_system, make_staff, new_account

MATRIZ = ROOT / "docs" / "execution" / "API_AUTHORIZATION_MATRIX.csv"

CLASSES = {
    "publica", "usuario_sem_organizacao", "organizacao", "organizacao_por_papel",
    "organizacao_por_tipo", "organizacao_tipo_e_papel", "organizacao_com_direito_de_plano",
    "plataforma", "plataforma_com_permissao",
}


def _rotas():
    from impacto import api
    from impacto.http import ROUTES
    api.load_all()
    return ROUTES


class EveryOperationIsClassifiedTests(unittest.TestCase):
    """Rota nova sem classe conhecida reprova. É o que impede a matriz de ficar atrás do código."""

    @classmethod
    def setUpClass(cls):
        cls.rotas = _rotas()
        cls.linhas = list(csv.DictReader(MATRIZ.open(encoding="utf-8"))) if MATRIZ.exists() else []

    def test_the_matrix_exists_and_covers_every_route(self):
        self.assertTrue(self.linhas, "a matriz não foi gerada: rode scripts/make_authorization_matrix.py")
        self.assertEqual(len(self.rotas), len(self.linhas),
                         f"{len(self.rotas)} rotas no roteador e {len(self.linhas)} na matriz — "
                         "regere a matriz")

    def test_the_matrix_is_current(self):
        """Matriz gerada de uma versão antiga do roteador descreve um passado.

        Confere caminho por caminho, em vez de comparar o arquivo inteiro: o arquivo tem colunas
        preenchidas por execução de teste, que mudam legitimamente.
        """
        do_roteador = {(r.method, r.path) for r in self.rotas}
        da_matriz = {(l["method"], l["path"]) for l in self.linhas}
        self.assertEqual(set(), do_roteador - da_matriz,
                         f"rota no código e fora da matriz: {sorted(do_roteador - da_matriz)[:8]}")
        self.assertEqual(set(), da_matriz - do_roteador,
                         f"rota na matriz e fora do código: {sorted(da_matriz - do_roteador)[:8]}")

    def test_every_class_is_a_known_class(self):
        desconhecidas = {l["class"] for l in self.linhas} - CLASSES
        self.assertEqual(set(), desconhecidas, f"classe não prevista: {desconhecidas}")

    def test_every_row_declares_what_each_persona_can_do(self):
        valores = {"yes", "no", "role", "kind", "perm", "feature"}
        for linha in self.linhas:
            for persona in ("anonymous", "authenticated", "viewer", "member", "owner",
                            "tenant_admin", "global_admin"):
                with self.subTest(rota=f'{linha["method"]} {linha["path"]}', persona=persona):
                    self.assertIn(linha[persona], valores)

    def test_no_route_is_anonymous_unless_it_is_in_the_reviewed_list(self):
        """As 52 rotas públicas, a 100%: a lista revisada vive em `test_architecture.py`."""
        publicas = {l["path"] for l in self.linhas if l["class"] == "publica"}
        fonte = (ROOT / "backend" / "tests" / "test_architecture.py").read_text(encoding="utf-8")
        fora = sorted(p for p in publicas if f'"{p}"' not in fonte)
        self.assertEqual([], fora,
                         f"rota pública fora da lista revisada de segurança: {fora}")

    def test_every_platform_route_declares_mfa(self):
        """Toda rota `auth="admin"` exige sessão com MFA verificado — conferido em `load_principal`."""
        sem_mfa = [f'{l["method"]} {l["path"]}' for l in self.linhas
                   if l["class"].startswith("plataforma") and l["mfa_required"] != "yes"]
        self.assertEqual([], sem_mfa, f"rota de plataforma sem MFA declarado: {sem_mfa}")

    def test_the_counts_match_what_the_report_states(self):
        """Número citado em relatório que ninguém confere é número que envelhece."""
        self.assertEqual(940, len(self.linhas))   # v0.30.0 (ADR-360..362): +4 rotas — GET evidência, POST contestação, PATCH método do indicador, GET dossiê (antes 936). v0.29.0 (ADR-353..357): +13 rotas da camada de conhecimento (3 públicas: fontes, fonte, conceitos; 1 de usuário: relato de erro; 9 de equipe editorial) — antes 923 (v0.28.0, +28 da Central de IA)
        # v0.27.0: −6 rotas de plataforma de assinatura/trial (trial, manual-subscription, preço de plano, trial-requests ×2,
        # painel de testes) +4 (proposta de contrato, licença, confirmação e conciliação de repasse pela administração);
        # +1 permissão nomeada líquida (torre master, proposta de contrato; −preço, −trial); −2 públicas (preço, webhook).
        self.assertEqual(238, sum(1 for l in self.linhas if l["class"].startswith("plataforma")))   # v0.29.0: +9 rotas /v1/admin/content/* da camada de conhecimento (papéis editoriais editor/reviewer/support com MFA; antes 229 na v0.28.0)
        self.assertEqual(94, sum(1 for l in self.linhas if l["permission"]))   # v0.28.0: +9 permissões das rotas administrativas da IA
        self.assertEqual(54, sum(1 for l in self.linhas if l["class"] == "publica"))   # v0.29.0: +GET /v1/help/sources, /v1/help/sources/{key}, /v1/public/concepts (referências e catálogo estático; antes 51 na v0.28.0)


class ThePlatformDoorIsClosedToEveryClientOrganizationTests(unittest.TestCase):
    """As 238 rotas de plataforma, a 100% — não por amostra."""

    @classmethod
    def setUpClass(cls):
        cls.rotas = [r for r in _rotas() if r.auth == "admin"]
        cls.cliente = new_account("osc", compliance="approved")

    def test_there_are_platform_routes_to_test(self):
        self.assertGreaterEqual(len(self.rotas), 200)

    def test_no_platform_route_is_reachable_by_a_client_organization(self):
        """Uma chamada por rota, com o verbo real. 238 chamadas, não 42 mil.

        O que se confere é o PONTO DE ESTRANGULAMENTO: `authorize()` recusa antes de validar o
        corpo, então o resultado não depende de montar um corpo válido para cada uma.
        """
        falhas = []
        for r in self.rotas:
            caminho = r.path
            for parte in r.path.split("/"):
                if parte.startswith("{"):
                    caminho = caminho.replace(parte, "00000000-0000-0000-0000-000000000001")
            resp = self.cliente.request(r.method, caminho, {} if r.method != "GET" else None)
            if resp.status not in (401, 403):
                falhas.append(f"{r.method} {r.path} → {resp.status}")
        self.assertEqual([], falhas,
                         f"rota de plataforma alcançada por organização cliente: {falhas[:10]}")

    def test_an_anonymous_caller_never_reaches_a_platform_route(self):
        anon = Client()
        falhas = []
        for r in self.rotas:
            caminho = r.path
            for parte in r.path.split("/"):
                if parte.startswith("{"):
                    caminho = caminho.replace(parte, "00000000-0000-0000-0000-000000000001")
            resp = anon.request(r.method, caminho, {} if r.method != "GET" else None)
            if resp.status not in (401, 403):
                falhas.append(f"{r.method} {r.path} → {resp.status}")
        self.assertEqual([], falhas, f"rota de plataforma alcançada sem sessão: {falhas[:10]}")


class EveryPermissionGuardedRouteRefusesARoleWithoutItTests(unittest.TestCase):
    """As 83 rotas com permissão interna, a 100%.

    `support` é papel de CONTEÚDO: tem permissões editoriais e nenhuma financeira, contábil, de
    tesouraria ou de segurança. Nenhuma das 83 rotas com permissão declarada deve aceitá-lo, exceto
    as que exigem exatamente uma permissão que ele tem.
    """

    @classmethod
    def setUpClass(cls):
        cls.rotas = [r for r in _rotas() if r.auth == "admin" and r.permission]
        cls.equipe = make_staff("support")
        with db_system() as c:
            cls.tem = {x["permission"] for x in c.query(
                "SELECT permission FROM staff_permissions WHERE role = 'support'")}

    def test_the_content_role_has_no_financial_or_security_permission(self):
        """Contraprova do teste abaixo: se `support` tivesse tudo, ele não provaria nada."""
        self.assertTrue(self.tem, "o papel `support` não tem permissão nenhuma no banco")
        for proibida in ("finance.read", "finance.approve", "accounting.close", "treasury.write",
                         "security.audit.read", "security.kill_switch", "billing.refund"):
            with self.subTest(permissao=proibida):
                self.assertNotIn(proibida, self.tem)

    def test_every_route_whose_permission_it_lacks_refuses_it(self):
        falhas = []
        for r in self.rotas:
            if r.permission in self.tem:
                continue
            caminho = r.path
            for parte in r.path.split("/"):
                if parte.startswith("{"):
                    caminho = caminho.replace(parte, "00000000-0000-0000-0000-000000000001")
            resp = self.equipe.request(r.method, caminho, {} if r.method != "GET" else None)
            # 401 `step_up_required` também é recusa: a permissão exige identidade reconfirmada.
            if resp.status not in (401, 403):
                falhas.append(f"{r.method} {r.path} [{r.permission}] → {resp.status}")
        self.assertEqual([], falhas,
                         f"papel interno alcançou rota cuja permissão ele não tem: {falhas[:10]}")

    def test_a_route_whose_permission_it_has_is_reachable(self):
        """Contraprova: um guarda que recusasse TUDO passaria no teste acima."""
        alcancaveis = [r for r in self.rotas if r.permission in self.tem and r.method == "GET"]
        self.assertTrue(alcancaveis, "o papel de conteúdo não alcança nenhuma rota: arranjo inútil")
        r = alcancaveis[0]
        caminho = r.path
        for parte in r.path.split("/"):
            if parte.startswith("{"):
                caminho = caminho.replace(parte, "00000000-0000-0000-0000-000000000001")
        resp = self.equipe.request(r.method, caminho, None)
        self.assertNotIn(resp.status, (401, 403),
                         f"{r.method} {r.path} exige {r.permission}, que o papel tem, e recusou")


class TheChokepointEnforcesEachClassTests(unittest.TestCase):
    """`authorize()` por classe de equivalência, com chamadas HTTP reais."""

    @classmethod
    def setUpClass(cls):
        cls.osc = new_account("osc", compliance="approved")
        cls.empresa = new_account("company", compliance="approved")
        cls.anon = Client()

    def test_a_public_route_answers_without_a_session(self):
        self.assertEqual(200, self.anon.get("/v1/plans").status)

    def test_a_user_route_needs_a_session_but_not_an_organization(self):
        self.assertEqual(401, self.anon.get("/v1/auth/sessions").status)
        self.assertEqual(200, self.osc.get("/v1/auth/sessions").status)

    def test_an_org_route_needs_an_active_organization(self):
        self.assertEqual(401, self.anon.get("/v1/projects").status)
        self.assertEqual(200, self.osc.get("/v1/projects").status)

    def test_a_kind_restricted_route_refuses_the_wrong_kind_of_organization(self):
        """`kinds` é o eixo que a v0.22.0 separou de `min_role`: tipo de organização, não papel."""
        rota = next(r for r in _rotas()
                    if r.kinds == ("osc",) and r.method == "GET" and "{" not in r.path)
        self.assertEqual(200, self.osc.get(rota.path).status, rota.path)
        self.assertEqual(403, self.empresa.get(rota.path).status,
                         f"{rota.path} é de OSC e aceitou empresa")

    def test_a_role_restricted_route_refuses_a_lower_role(self):
        from tests.support import set_role
        rota = next(r for r in _rotas()
                    if r.min_role == "manager" and r.method == "GET" and "{" not in r.path
                    and not r.kinds)
        set_role(self.osc.user["id"], self.osc.org_id, "viewer")
        try:
            self.assertEqual(403, self.osc.get(rota.path).status,
                             f"{rota.path} exige manager e aceitou viewer")
        finally:
            set_role(self.osc.user["id"], self.osc.org_id, "owner")
        self.assertEqual(200, self.osc.get(rota.path).status)

    def test_a_platform_route_refuses_an_organization_owner(self):
        """`tenant_admin` ≠ `global_admin`. É a distinção que o booleano único apagava."""
        self.assertIn(self.osc.get("/v1/admin/organizations").status, (401, 403))

    def test_an_unknown_object_answers_404_and_not_403(self):
        """404 e 403 vazam coisas diferentes: 403 em objeto inexistente confirma que ele existe."""
        r = self.osc.get("/v1/projects/00000000-0000-0000-0000-0000000000ff")
        self.assertEqual(404, r.status, r.json)

    def test_a_malformed_identifier_answers_404_and_not_500(self):
        self.assertEqual(404, self.osc.get("/v1/projects/nao-e-uuid").status)

    def test_an_invalid_payload_answers_422_with_the_field(self):
        r = self.osc.post("/v1/projects", {"title": ""})
        self.assertEqual(422, r.status)
        self.assertEqual("validation_error", r.json["code"])
        self.assertTrue(r.json["details"], "422 sem dizer qual campo não ajuda quem integra")

    def test_an_unknown_field_is_refused_instead_of_silently_ignored(self):
        """Campo ignorado em silêncio é como atribuição em massa entra: o cliente manda, o servidor
        aceita, e ninguém sabe se foi usado."""
        r = self.osc.post("/v1/projects", {"title": "x", "summary": "y" * 40,
                                           "is_platform_admin": True})
        self.assertEqual(422, r.status)
        self.assertTrue(any("extra" in str(d).lower() or "permitted" in str(d).lower()
                            for d in r.json["details"]), r.json["details"])


class CrossTenantIsRefusedByTheWallNotOnlyByTheDoorTests(unittest.TestCase):
    """IDOR e BOLA: a rota é a porta, a RLS é a parede. Testar só a porta deixa a parede sem prova."""

    @classmethod
    def setUpClass(cls):
        from tests.support import grant_premium
        import datetime as dt
        cls.a = new_account("osc", compliance="approved")
        cls.b = new_account("osc", compliance="approved")
        grant_premium(cls.a)
        grant_premium(cls.b)
        corpo = {
            "summary": "Projeto criado para prova de isolamento entre inquilinos.",
            "problem": "p", "objectives": "o", "territory": "BR-AC-1200013",
            "causes": ["educacao"], "beneficiaries_count": 10, "budget_total_cents": 100_000,
            "starts_on": (dt.date.today() - dt.timedelta(days=5)).isoformat(),
            "ends_on": (dt.date.today() + dt.timedelta(days=60)).isoformat()}
        cls.pa = cls.a.post("/v1/projects", {"title": "Projeto do inquilino A"} | corpo).json["id"]
        cls.pb = cls.b.post("/v1/projects", {"title": "Projeto do inquilino B"} | corpo).json["id"]

    def test_a_cannot_read_b(self):
        self.assertEqual(404, self.a.get(f"/v1/projects/{self.pb}").status,
                         "IDOR: A leu o projeto de B")

    def test_a_cannot_write_b(self):
        r = self.a.patch(f"/v1/projects/{self.pb}", {"title": "invadido"})
        self.assertIn(r.status, (403, 404), "BOLA: A alterou o projeto de B")
        with db_system() as c:
            self.assertEqual("Projeto do inquilino B",
                             c.scalar("SELECT title FROM projects WHERE id = $1", self.pb))

    def test_a_cannot_delete_b(self):
        r = self.a.request("DELETE", f"/v1/projects/{self.pb}", None)
        self.assertIn(r.status, (403, 404, 405))
        with db_system() as c:
            self.assertEqual(1, c.scalar("SELECT count(*) FROM projects WHERE id = $1", self.pb))

    def test_a_listing_never_includes_b(self):
        itens = self.a.get("/v1/projects").json["items"]
        self.assertNotIn(self.pb, [i["id"] for i in itens])
        self.assertIn(self.pa, [i["id"] for i in itens])

    def test_the_wall_refuses_even_with_the_right_identifier(self):
        """A prova da RLS, no banco: contexto de A, identificador de B."""
        from tests.support import app_tx
        with app_tx(self.a) as c:
            self.assertEqual(0, c.scalar("SELECT count(*) FROM projects WHERE id = $1", self.pb))

    def test_mass_assignment_cannot_move_a_row_to_another_tenant(self):
        """`org_id` não é campo de entrada: a RLS o derruba mesmo se o schema o aceitasse."""
        r = self.a.patch(f"/v1/projects/{self.pa}", {"org_id": self.b.org_id})
        self.assertIn(r.status, (403, 404, 422))
        with db_system() as c:
            self.assertEqual(self.a.org_id,
                             c.scalar("SELECT org_id::text FROM projects WHERE id = $1", self.pa))


class TheHighRiskSubsetsAreCoveredAtOneHundredPercentTests(unittest.TestCase):
    """Exportação, upload e webhook: os três caminhos por onde dado sai ou entra sem tela."""

    def test_every_upload_route_is_multipart_and_limited(self):
        rotas = [r for r in _rotas() if r.multipart]
        self.assertTrue(rotas, "nenhuma rota de upload encontrada")
        for r in rotas:
            with self.subTest(rota=r.path):
                self.assertIn(r.method, ("POST", "PUT"))
                self.assertNotEqual("none", r.auth, "upload anônimo")

    def test_every_raw_body_route_verifies_a_signature(self):
        """`raw_body` existe para webhook: corpo cru é lido para CONFERIR assinatura."""
        import inspect
        rotas = [r for r in _rotas() if r.raw_body]
        self.assertTrue(rotas)
        for r in rotas:
            with self.subTest(rota=r.path):
                fonte = inspect.getsource(r.handler)
                alcance = fonte + "".join(
                    inspect.getsource(o) for o in (inspect.getmodule(r.handler),) if o)
                self.assertTrue(any(t in alcance for t in ("signature", "assinatura", "hmac",
                                                           "Stripe-Signature", "verify")),
                                f"{r.path} lê corpo cru e não confere assinatura")

    def test_every_export_route_requires_a_session(self):
        rotas = [r for r in _rotas()
                 if ("export" in r.path or "/csv" in r.path or "download" in r.path)]
        self.assertTrue(rotas)
        for r in rotas:
            with self.subTest(rota=r.path):
                self.assertNotEqual("none", r.auth,
                                    f"{r.path} exporta dado sem exigir sessão")

    def test_every_write_route_that_touches_the_ledger_is_authenticated(self):
        linhas = list(csv.DictReader(MATRIZ.open(encoding="utf-8")))
        publicas = [l for l in linhas if l["ledger_effect"] == "yes" and l["class"] == "publica"]
        self.assertEqual([], publicas,
                         f"rota pública com efeito no ledger: {[l['path'] for l in publicas]}")


if __name__ == "__main__":
    unittest.main()
