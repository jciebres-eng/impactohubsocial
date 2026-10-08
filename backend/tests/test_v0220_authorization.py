"""Autorização: quem vê dinheiro, quem vê conteúdo, e quem não vê nada.

O DEFEITO QUE ESTE ARQUIVO TRAVA

Até a v0.21.0 existia UM booleano para toda a equipe interna — `users.is_platform_admin`. Quem o
tivesse alcançava as 193 rotas `auth="admin"`, incluindo receita apurada, custo de IA, fatura e
tabela de preços, **sem nenhum papel financeiro no caminho**. Os três papéis nomeados que existiam
(`editor`, `reviewer`, `support`) eram todos de conteúdo.

Numa equipe de uma pessoa isso não aparece. Na primeira contratação, aparece de uma vez — e a
correção às pressas é conceder tudo a todos.

O teste central deste arquivo é
`test_support_cannot_see_revenue_even_though_it_reaches_the_admin_area`.
"""
from __future__ import annotations

import unittest
import uuid

from tests.support import PASSWORD, db_system, make_admin, make_staff, new_account, reauth


# v0.27.0 (ADR-341): a rota representativa de `finance.approve` deixou de ser o preço de plano (não há assinatura) e
# passou a ser a PROPOSTA DE CONTRATO — valor com motivo, de quem tem alçada. O org_id é fictício de propósito:
# permissão e step-up são decididos antes de o corpo ser usado; quando passam, a resposta é 404 (organização), nunca 401/403.
PROPOSTA = {"org_id": "00000000-0000-4000-8000-000000000001", "plan_key": "osc_premium", "amount_cents": 120000,
            "amount_reason": "Proposta de contrato (arranjo de teste)", "billing_frequency": "one_time", "payment_method": "pix"}


class PermissionMatrixIsDataTests(unittest.TestCase):
    """A matriz é tabela, não dicionário em Python — para que a auditoria possa consultá-la."""

    def test_the_matrix_separates_money_from_content(self):
        with db_system() as c:
            por_papel = {r["role"]: set(r["perms"]) for r in c.query(
                "SELECT role, array_agg(permission) AS perms FROM staff_permissions GROUP BY role")}
        # Papéis de CONTEÚDO não têm nenhuma permissão financeira. É a separação que não existia.
        for papel in ("editor", "reviewer", "support"):
            financeiras = {p for p in por_papel.get(papel, set())
                           if p.split(".")[0] in ("finance", "accounting", "treasury",
                                                  "instruction", "billing", "metrics")}
            self.assertEqual(financeiras, set(),
                             f"{papel} é papel de conteúdo e recebeu permissão financeira: {financeiras}")
        # E os papéis financeiros existem de fato.
        for papel in ("controller", "finance", "accounting", "treasury"):
            self.assertIn(papel, por_papel, f"papel {papel} não existe na matriz")

    def test_audit_can_read_everything_and_write_nothing(self):
        """Auditoria lê tudo e não altera nada. Um `.write` aqui seria um defeito de desenho."""
        with db_system() as c:
            perms = set(c.query("SELECT permission FROM staff_permissions WHERE role = 'audit'")
                        and [r["permission"] for r in c.query(
                            "SELECT permission FROM staff_permissions WHERE role = 'audit'")])
        escrita = {p for p in perms if p.split(".")[-1] not in ("read", "export")}
        self.assertEqual(escrita, set(), f"auditoria recebeu permissão de escrita: {escrita}")
        self.assertIn("finance.read", perms, "auditoria precisa ler o financeiro")
        self.assertIn("security.audit.export", perms)

    def test_super_admin_is_not_listed_in_the_matrix(self):
        """`super_admin` implica todas. Listá-las uma a uma criaria uma lista que esquece a próxima."""
        with db_system() as c:
            n = c.scalar("SELECT count(*) FROM staff_permissions WHERE role = 'super_admin'")
            catalogo = c.scalar("SELECT count(*) FROM permission_catalog")
        self.assertEqual(n, 0)
        # E a função resolve isso devolvendo o CATÁLOGO inteiro — que é maior do que a união do
        # mapeamento, porque inclui as permissões que nenhum papel concede.
        cli = make_staff("super_admin")
        perms = cli.get("/v1/me/context").json["staff"]["permissions"]
        self.assertEqual(len(perms), catalogo,
                         "super_admin deveria receber todas as permissões do catálogo")

    def test_every_permission_declared_on_a_route_exists_in_the_matrix(self):
        """Rota exigindo permissão que ninguém pode ter é rota inalcançável."""
        from impacto.http import ROUTES
        from impacto.api import load_all
        load_all()
        exigidas = {r.permission for r in ROUTES if r.permission}
        self.assertTrue(exigidas, "nenhuma rota declara permissão")
        with db_system() as c:
            existem = {r["permission"] for r in c.query("SELECT permission FROM staff_permissions")}
        # Permissão que nenhum papel concede É uma decisão legítima — "só super_admin" —, mas tem
        # de estar declarada no CATÁLOGO, com motivo escrito. A primeira versão disto mantinha a
        # lista num dicionário em Python, e ela discordou do banco na primeira revisão: ela dizia
        # que `admin.organizations.write` era exclusiva, e `compliance` já a tinha. Duas fontes de
        # verdade sobre segurança divergem, e a que ninguém consulta é a que fica errada.
        with db_system() as c:
            so_super = {r["permission"] for r in c.query(
                "SELECT permission FROM permission_catalog WHERE super_admin_only")}
            sem_motivo = [r["permission"] for r in c.query(
                "SELECT permission FROM permission_catalog"
                " WHERE super_admin_only AND coalesce(length(only_reason), 0) < 30")]
        self.assertEqual(sem_motivo, [],
                         "permissão exclusiva de super_admin sem motivo escrito: "
                         + ", ".join(sem_motivo))
        orfas = sorted(exigidas - existem - so_super)
        self.assertEqual(orfas, [],
                         "rota exige permissão que nenhum papel concede e que não está declarada "
                         "no catálogo como exclusiva de super_admin: " + ", ".join(orfas))

    def test_the_catalog_and_the_mapping_cannot_drift(self):
        """Mapear papel para permissão fora do catálogo é erro de digitação que só apareceria
        quando alguém tentasse usar a rota. A chave estrangeira recusa antes.

        Confere a restrição NOMEADA: `assertRaises(Exception)` em volta de um INSERT passaria por
        erro de privilégio, de RLS ou de tipo — qualquer coisa menos a chave estrangeira que o
        teste diz provar. Apontado por auditoria independente.
        """
        from tests.support import owner_conn
        # Duas camadas, e as duas conferidas. A primeira versão deste teste usava
        # `assertRaises(Exception)` no contexto da aplicação e passava por PRIVILÉGIO (42501), não
        # pela chave estrangeira — provava uma coisa e afirmava outra.
        with db_system() as c:
            with self.assertRaises(Exception) as cm:
                c.run("INSERT INTO staff_permissions(role, permission)"
                      " VALUES ('finance','finance.inventada')")
            self.assertEqual(getattr(cm.exception, "sqlstate", None), "42501",
                             "o papel da aplicação não deveria poder escrever na matriz")
        conn = owner_conn()
        try:
            with self.assertRaises(Exception) as cm:
                conn.run("INSERT INTO staff_permissions(role, permission)"
                         " VALUES ('finance','finance.inventada')")
            self.assertEqual(getattr(cm.exception, "sqlstate", None), "23503",
                             f"não foi a chave estrangeira que recusou: {cm.exception}")
        finally:
            conn.close()

    def test_super_admin_receives_the_catalog_including_its_exclusive_permissions(self):
        """O defeito que o teste da matriz encontrou: as exclusivas de super_admin não estavam no
        mapeamento (por definição), e `staff_permissions_of` lia o mapeamento — então nem ele as
        recebia, e a rota ficava inalcançável por todos."""
        with db_system() as c:
            catalogo = c.scalar("SELECT count(*) FROM permission_catalog")
            exclusivas = {r["permission"] for r in c.query(
                "SELECT permission FROM permission_catalog WHERE super_admin_only")}
        self.assertTrue(exclusivas, "nenhuma permissão exclusiva declarada")
        cli = make_staff("super_admin")
        perms = set(cli.get("/v1/me/context").json["staff"]["permissions"])
        self.assertEqual(len(perms), catalogo)
        self.assertTrue(exclusivas <= perms,
                        f"super_admin não recebeu as exclusivas: {exclusivas - perms}")


class MoneyIsSeparatedFromContentTests(unittest.TestCase):
    """O teste central: quem atende chamado não vê a receita."""

    def test_support_cannot_see_revenue_even_though_it_reaches_the_admin_area(self):
        sup = make_staff("support")
        # Alcança a área administrativa: a rota de suporte responde.
        self.assertEqual(sup.get("/v1/admin/support/tickets").status, 200)
        # E NÃO alcança o dinheiro.
        for rota in ("/v1/admin/payments/revenue", "/v1/admin/ai/cost",
                     "/v1/admin/price-benchmark", "/v1/admin/monetization/pipeline"):
            r = sup.get(rota)
            self.assertEqual(r.status, 403, f"{rota} respondeu {r.status} para suporte")
            self.assertEqual(r.json["code"], "permission_denied")
            # A recusa diz QUAL permissão faltou — para a pessoa saber a quem pedir. Isto só vale
            # para quem JÁ é da equipe; a um cliente qualquer a resposta é "área restrita", sem
            # confirmar o que a rota exige (ver `authorize()` em http.py).
            self.assertTrue(r.json["details"]["required_permission"],
                            "a recusa não disse qual permissão faltou")

    def test_finance_sees_money_and_not_content_governance(self):
        fin = make_staff("finance")
        self.assertEqual(fin.get("/v1/admin/payments/revenue").status, 200)
        # Publicar conteúdo é de `reviewer`, e dinheiro não compra essa permissão.
        r = fin.get("/v1/admin/permissions")
        self.assertEqual(r.status, 403, "financeiro alcançou a matriz de permissões")

    def test_accounting_cannot_approve_a_price_change(self):
        """Contabilidade registra; aprovar mudança comercial é de controladoria."""
        cont = make_staff("accounting")
        self.assertEqual(cont.get("/v1/admin/payments/revenue").status, 200)  # finance.read
        r = cont.post("/v1/admin/commercial/offers", PROPOSTA)
        self.assertEqual(r.status, 403)
        self.assertEqual(r.json["details"]["required_permission"], "finance.approve")

    def test_analyst_sees_aggregate_and_not_individual_money(self):
        an = make_staff("analyst")
        self.assertEqual(an.get("/v1/admin/ops/health").status, 200)      # health.read
        self.assertEqual(an.get("/v1/admin/payments/revenue").status, 403)
        # As duas rotas, sem condicional morta: a primeira versão escrevia
        # `"/v1/admin/invoices" if False else "/v1/admin/free-periods"`, e a rota de faturas nunca
        # era exercitada.
        # `/v1/admin/invoices` existe só em POST (emissão de cobrança manual): a condicional
        # morta da primeira versão escondia que a rota não respondia a GET.
        self.assertEqual(an.post("/v1/admin/invoices", {"org_id": str(uuid.uuid4()),
                                                        "amount_cents": 1000,
                                                        "description": "tentativa"}).status, 403)
        self.assertEqual(an.get("/v1/admin/free-periods").status, 403)

    def test_a_platform_admin_keeps_everything_because_the_migration_said_so(self):
        """Nenhuma pessoa perdeu acesso com a v0.22.0. É isto que torna a mudança implantável."""
        adm, _ = make_admin()
        for rota in ("/v1/admin/payments/revenue", "/v1/admin/ai/cost",
                     "/v1/admin/permissions", "/v1/admin/privileged-access"):
            self.assertEqual(adm.get(rota).status, 200, f"{rota} recusou um administrador")

    def test_losing_platform_admin_loses_super_admin_too(self):
        """Revogar a administração e manter o privilégio dela seria o pior dos dois mundos."""
        adm, _ = make_admin()
        with db_system() as c:
            uid = c.scalar("SELECT id::text FROM users WHERE email = $1", adm.email)
            self.assertTrue(c.one("SELECT 1 FROM staff_roles WHERE user_id = $1"
                                  " AND role = 'super_admin'", uid))
            c.run("UPDATE users SET is_platform_admin = false WHERE id = $1", uid)
            self.assertIsNone(c.one("SELECT 1 FROM staff_roles WHERE user_id = $1"
                                    " AND role = 'super_admin'", uid),
                              "o papel super_admin sobreviveu à perda da administração")


class ClientsCannotReachTheBackofficeTests(unittest.TestCase):

    def test_an_ordinary_organization_cannot_reach_any_internal_panel(self):
        cli = new_account("osc")
        for rota in ("/v1/admin/payments/revenue", "/v1/admin/permissions",
                     "/v1/admin/privileged-access", "/v1/admin/ops/health",
                     "/v1/admin/users", "/v1/admin/organizations"):
            r = cli.get(rota)
            self.assertIn(r.status, (403,), f"{rota} respondeu {r.status} para um cliente")
            self.assertEqual(r.json["code"], "admin_only")

    def test_a_client_cannot_see_another_organizations_commercial_state(self):
        a, b = new_account("osc"), new_account("osc")
        with db_system() as c:
            b_org = c.scalar("SELECT id::text FROM organizations WHERE id = $1", b.org_id)
        self.assertIsNotNone(b_org)
        # O estado comercial é sempre o da organização ATIVA da sessão; não há parâmetro de org.
        estado = a.get("/v1/commercial/state")
        self.assertEqual(estado.status, 200)
        self.assertEqual(a.get("/v1/commercial/offers").json["items"], [])

    def test_switching_to_an_organization_one_does_not_belong_to_is_refused(self):
        a, b = new_account("osc"), new_account("osc")
        r = a.post("/v1/me/switch-org", {"org_id": b.org_id})
        self.assertNotEqual(r.status, 200, "trocou para organização de outra pessoa")
        # E a organização ativa continua a dela.
        self.assertEqual(a.get("/v1/me").json["active_org"]["id"], a.org_id)


class StepUpTests(unittest.TestCase):
    """Reautenticação: uma implementação, janela de 15 minutos, MFA quando houver."""

    def test_a_step_up_permission_is_refused_without_fresh_reauth(self):
        ctl = make_staff("controller")
        # `finance.approve` está em STEP_UP_PERMISSIONS.
        r = ctl.post("/v1/admin/commercial/offers", PROPOSTA)
        self.assertEqual(r.status, 401, r.body)
        self.assertEqual(r.json["code"], "step_up_required")
        self.assertTrue(r.json["details"]["step_up_required"])

    def test_after_reauth_the_same_operation_is_allowed(self):
        ctl = make_staff("controller")
        reauth(ctl)
        r = ctl.post("/v1/admin/commercial/offers", PROPOSTA)
        self.assertNotEqual(r.status, 401, f"reautenticação não foi reconhecida: {r.body}")
        self.assertNotEqual(r.status, 403, f"permissão recusada após reautenticar: {r.body}")

    def test_reauth_with_the_wrong_password_is_refused(self):
        ctl = make_staff("controller")
        r = ctl.post("/v1/auth/reauth", {"password": "senha-errada-de-proposito"})
        self.assertEqual(r.status, 401)
        self.assertEqual(r.json["code"], "reauth_failed")

    def test_whoever_has_mfa_must_use_it_to_reauth(self):
        """Aceitar só a senha de quem tem segundo fator ofereceria o fator mais fraco na operação
        mais perigosa."""
        ctl = make_staff("controller")      # make_staff liga MFA
        r = ctl.post("/v1/auth/reauth", {"password": PASSWORD})
        self.assertEqual(r.status, 401, r.body)
        self.assertEqual(r.json["code"], "mfa_code_required")

    def test_a_read_permission_does_not_require_step_up(self):
        """Pedir senha para LER o relatório faria a pessoa digitá-la vinte vezes por dia."""
        fin = make_staff("finance")
        self.assertEqual(fin.get("/v1/admin/payments/revenue").status, 200)

    def test_there_is_only_one_implementation_of_identity_verification(self):
        """Ninguém mais confere senha no próprio handler.

        A primeira versão procurava a string `reauth_failed` fora de `core/access.py`: uma cópia
        nova que levantasse outro código de erro passaria. Agora a varredura é pelo ATO — conferir
        senha — e não pela mensagem. Apontado por auditoria independente.
        """
        import pathlib
        raiz = pathlib.Path(__file__).resolve().parents[1] / "impacto"
        culpados = []
        for f in raiz.rglob("*.py"):
            if f.name in ("access.py", "passwords.py", "auth.py", "oidc.py"):
                continue   # auth.py é o login; oidc.py é o provedor externo; passwords.py é a cifra
            texto = f.read_text(encoding="utf-8")
            if "verify_password(" in texto or "reauth_failed" in texto:
                culpados.append(str(f.relative_to(raiz)))
        self.assertEqual(culpados, [],
                         "voltou a existir cópia da verificação de identidade fora de "
                         "core/access.py: " + ", ".join(culpados))

    def test_the_three_routes_that_had_copies_delegate_to_the_single_one(self):
        """E as três que tinham cópia chamam a implementação única, nominalmente."""
        import pathlib
        raiz = pathlib.Path(__file__).resolve().parents[1] / "impacto" / "api"
        for arquivo in ("privacy_routes.py", "trust_routes.py", "document_routes.py"):
            texto = (raiz / arquivo).read_text(encoding="utf-8")
            self.assertIn("verify_identity", texto,
                          f"{arquivo} deixou de delegar a confirmação de identidade")


class PrivilegedAccessIsLoggedTests(unittest.TestCase):

    def test_reading_the_revenue_leaves_a_trace(self):
        """Numa investigação a pergunta é "quem olhou", e `audit_events` só registra quem mudou."""
        fin = make_staff("finance")
        self.assertEqual(fin.get("/v1/admin/payments/revenue").status, 200)
        with db_system() as c:
            row = c.one("SELECT p.permission, p.method, p.path, p.roles_used FROM privileged_access_log p"
                        " JOIN users u ON u.id = p.user_id WHERE u.email = $1"
                        " ORDER BY p.id DESC LIMIT 1", fin.email)
        self.assertIsNotNone(row, "a leitura privilegiada não deixou rastro")
        self.assertEqual(row["permission"], "finance.read")
        self.assertEqual(row["method"], "GET")
        self.assertIn("finance", row["roles_used"])

    def test_the_trail_cannot_be_rewritten_or_deleted(self):
        fin = make_staff("finance")
        fin.get("/v1/admin/payments/revenue")
        with db_system() as c:
            rid = c.scalar("SELECT id FROM privileged_access_log ORDER BY id DESC LIMIT 1")
        for sql in ("UPDATE privileged_access_log SET permission = 'alterado' WHERE id = $1",
                    "DELETE FROM privileged_access_log WHERE id = $1"):
            with self.assertRaises(Exception, msg=f"a trilha aceitou: {sql}"):
                with db_system() as c:
                    c.run(sql, rid)

    def test_only_audit_and_security_read_the_trail(self):
        fin = make_staff("finance")
        self.assertEqual(fin.get("/v1/admin/privileged-access").status, 403,
                         "financeiro leu a trilha de quem olhou o financeiro")
        aud = make_staff("audit")
        self.assertEqual(aud.get("/v1/admin/privileged-access").status, 200)


    def test_a_refused_attempt_is_logged_too(self):
        """Sondagem recusada deixava rastro em lugar NENHUM.

        O registro só acontecia depois de a conferência passar: alguém da equipe batendo em
        cinquenta rotas financeiras e levando 403 em todas não aparecia aqui (não chegava) nem em
        `audit_events` (que só registra alteração). Uma tentativa de olhar também é um olhar, e uma
        sequência de tentativas recusadas é o sinal que uma investigação procura. Encontrado por
        auditoria independente.
        """
        suporte = make_staff("support")
        r = suporte.get("/v1/controladoria/summary")
        self.assertEqual(r.status, 403, r)
        with db_system() as c:
            linha = c.one(
                "SELECT roles_used, permission, path FROM privileged_access_log"
                " WHERE user_id = (SELECT id FROM users WHERE email = $1)"
                "   AND path = '/v1/controladoria/summary' ORDER BY id DESC LIMIT 1",
                suporte.email)
        self.assertIsNotNone(linha, "a tentativa recusada não entrou na trilha")
        self.assertIn("DENIED", linha["roles_used"],
                      "a trilha não distingue tentativa recusada de acesso concedido")
        self.assertEqual(linha["permission"], "metrics.read")

class AccessContextTests(unittest.TestCase):

    def test_the_context_answers_everything_the_screen_needs(self):
        cli = new_account("osc")
        r = cli.get("/v1/me/context")
        self.assertEqual(r.status, 200, r.body)
        for chave in ("user", "staff", "organization", "commercial", "entitlements",
                      "dashboard", "step_up_window_seconds"):
            self.assertIn(chave, r.json)
        self.assertEqual(r.json["organization"]["id"], cli.org_id)
        self.assertEqual(r.json["dashboard"], "/")
        self.assertFalse(r.json["staff"]["is_platform_admin"])
        self.assertEqual(r.json["staff"]["permissions"], [])

    def test_the_dashboard_is_decided_by_the_server_not_the_screen(self):
        casos = [("controller", "/controladoria"), ("accounting", "/contabilidade"),
                 ("finance", "/financeiro"), ("operations", "/operacoes"),
                 ("audit", "/auditoria"), ("support", "/admin")]
        for papel, esperado in casos:
            cli = make_staff(papel)
            got = cli.get("/v1/me/context").json["dashboard"]
            self.assertEqual(got, esperado, f"{papel} recebeu {got}")

    def test_asking_before_trying_gives_a_reason(self):
        cli = new_account("osc")
        r = cli.post("/v1/access/check", {"permission": "finance.read"})
        self.assertEqual(r.status, 200, r.body)
        self.assertFalse(r.json["allowed"])
        self.assertEqual(r.json["reason"], "permission_denied")
        self.assertEqual(r.json["required_permission"], "finance.read")

    def test_a_denied_feature_says_which_plan_has_it(self):
        cli = new_account("osc")
        r = cli.post("/v1/access/check", {"feature": "reports.advanced"})
        self.assertEqual(r.status, 200, r.body)
        self.assertFalse(r.json["allowed"])
        self.assertEqual(r.json["reason"], "feature_not_in_plan")
        self.assertTrue(r.json.get("required_plan"),
                        "a recusa não disse qual plano inclui o recurso")

    def test_checking_nothing_is_refused_instead_of_answering_yes(self):
        cli = new_account("osc")
        r = cli.post("/v1/access/check", {})
        self.assertEqual(r.status, 422, r.body)
        self.assertEqual(r.json["code"], "nothing_to_check")


class StepUpBlocksEvenAnAdministratorTests(unittest.TestCase):
    """O arranjo `make_admin` confirma a identidade. Este teste prova que a exigência é real.

    Sem ele, alguém poderia remover `STEP_UP_PERMISSIONS` e a suíte inteira continuaria verde —
    porque o arranjo passou a reautenticar. Então aqui o administrador é criado SEM confirmação.
    """

    def test_an_administrator_without_fresh_reauth_cannot_approve_a_price(self):
        from tests.support import make_admin_without_reauth
        adm = make_admin_without_reauth()
        r = adm.post("/v1/admin/commercial/offers", PROPOSTA)
        self.assertEqual(r.status, 401, f"a exigência de reautenticação desapareceu: {r.body}")
        self.assertEqual(r.json["code"], "step_up_required")

    def test_but_reading_is_allowed_without_reauth(self):
        from tests.support import make_admin_without_reauth
        adm = make_admin_without_reauth()
        self.assertEqual(adm.get("/v1/admin/payments/revenue").status, 200)

    def test_the_step_up_list_is_not_empty_and_covers_the_dangerous_verbs(self):
        from impacto.core.access import STEP_UP_PERMISSIONS
        self.assertGreaterEqual(len(STEP_UP_PERMISSIONS), 10)
        # Toda permissão de aprovação, fechamento, estorno e emissão precisa estar na lista.
        from tests.support import db_system
        with db_system() as c:
            todas = {r["permission"] for r in c.query("SELECT permission FROM permission_catalog")}
        perigosas = {p for p in todas
                     if p.split(".")[-1] in ("approve", "close", "refund", "issue", "cancel",
                                             "execute", "write")}
        faltando = sorted(perigosas - STEP_UP_PERMISSIONS)
        # A isenção é ESTREITA e cada entrada diz por que está aqui. A primeira versão desta lista
        # isentava `billing.write` e `free_period.write` sob um comentário que dizia "o resto sim" —
        # auditoria independente mostrou a contradição: `billing.write` dá baixa em fatura de
        # cliente e `free_period.write` concede gratuidade. As duas entraram na lista de step-up.
        permitidas_fora = {
            # Conteúdo editorial não move dinheiro nem concede privilégio, e já exige quatro olhos
            # próprios (autor ≠ revisor) no fluxo de publicação.
            "content.write", "content.publish",
            # Atendimento escreve em chamado e resposta, não em conta nem em permissão.
            "support.write",
            # Apuração de conformidade registra decisão sobre organização; a medida que dela
            # decorre tem o seu próprio fluxo de apuração, com gatilho no banco.
            "compliance.write",
            # Conexão de integração não transfere valor; a credencial é cifrada e nunca devolvida.
            "integration.write",
        }
        self.assertEqual(sorted(set(faltando) - permitidas_fora), [],
                         "permissão perigosa fora de STEP_UP_PERMISSIONS: " + ", ".join(faltando))
        # E a isenção não pode crescer em silêncio: toda permissão de escrita que não está no
        # step-up tem de estar nomeada acima, com motivo escrito.
        self.assertLessEqual(len(permitidas_fora), 8,
                             "isenção de step-up grande demais: cada entrada precisa de motivo")
