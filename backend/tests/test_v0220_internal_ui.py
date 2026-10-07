"""O menu interno não promete o que a porta recusa, nem o que não existe.

TRÊS DEFEITOS QUE ESTES TESTES TRAVAM

1. MENU QUE MENTE. Até a v0.21.0 a barra lateral da administração era uma lista fixa no frontend,
   igual para toda a equipe interna. Quem atendia chamado via "Cobrança por organização",
   "Organizações" e "Auditoria" no menu e levava 403 ao clicar. A regra de acesso existia em dois
   lugares e um deles estava errado.

2. MENU QUE APONTA PARA O VAZIO. Um item de menu com caminho que não é rota é um 404 com convite.

3. FUNCIONALIDADE INVISÍVEL. 224 das 848 rotas não tinham tela nenhuma — a saúde do sistema, a
   receita apurada, as tarefas agendadas, o hub de integrações. Construído, funcionando, invisível.
   Funcionalidade permitida que ninguém alcança não existe para quem usa.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from tests.support import ROOT, db_system, make_admin, make_staff, new_account

APP_TSX = Path(ROOT) / "web" / "src" / "app.tsx"


def _rotas_do_frontend() -> set[str]:
    """Os caminhos declarados no roteador da aplicação web."""
    texto = APP_TSX.read_text(encoding="utf-8")
    return set(re.findall(r'\["(/[^"]*)",\s*\(', texto))


class TheMenuCannotPromiseWhatIsNotThereTests(unittest.TestCase):

    def test_every_menu_entry_points_to_a_real_page(self):
        from impacto.api.access_routes import STAFF_MENU
        rotas = _rotas_do_frontend()
        self.assertGreater(len(rotas), 100, "não consegui ler o roteador web")
        faltando = [caminho for caminho, *_ in STAFF_MENU if caminho not in rotas]
        self.assertEqual(faltando, [], f"itens de menu sem página no roteador: {faltando}")

    def test_every_menu_entry_requires_a_permission_that_exists(self):
        from impacto.api.access_routes import STAFF_MENU
        with db_system() as c:
            catalogo = {r["permission"] for r in c.query("SELECT permission FROM permission_catalog")}
        declaradas = {p for *_, p in STAFF_MENU if p}
        self.assertEqual(declaradas - catalogo, set(),
                         "o menu exige permissão que não existe no catálogo")

    def test_no_menu_entry_is_open_to_everyone(self):
        """Item sem permissão apareceria para qualquer pessoa da equipe, inclusive suporte."""
        from impacto.api.access_routes import STAFF_MENU
        sem_permissao = [caminho for caminho, _, _, p in STAFF_MENU if not p]
        self.assertEqual(sem_permissao, [])


class TheMenuMatchesTheDoorTests(unittest.TestCase):
    """Para cada papel: tudo que o menu oferece, a API concede; nada mais."""

    def _contexto(self, *papeis: str) -> dict:
        c = make_staff(*papeis)
        r = c.get("/v1/me/context")
        self.assertEqual(r.status, 200, r)
        return r.json

    def test_support_sees_no_money_in_the_menu(self):
        ctx = self._contexto("support")
        grupos = {g["group"] for g in ctx["menu"]}
        for proibido in ("Controladoria", "Financeiro", "Contabilidade", "Tesouraria",
                         "Auditoria", "Segurança"):
            self.assertNotIn(proibido, grupos, f"suporte não deveria ver {proibido}")
        self.assertIn("Suporte", grupos)

    def test_every_menu_permission_is_actually_declared_on_a_route(self):
        """O teste que FALTAVA — e cuja ausência deixou o defeito aberto por uma versão inteira.

        A primeira versão desta classe conferia `item["permission"]` contra
        `ctx["staff"]["permissions"]`. Mas `menu_for()` FILTRA por exatamente essa mesma lista: o
        teste não podia falhar, e a documentação o citava como prova de que "o menu casa com a
        porta". Auditoria independente mostrou quatro papéis recebendo item que a API recusa.

        A conferência real é esta: a permissão que o menu exige tem de ser a permissão que ALGUMA
        rota exige. Item de menu guardado por permissão que nenhuma rota declara é item que só o
        booleano de administrador alcança — e o menu o oferece a quem não o tem.
        """
        from impacto import api
        from impacto.api.access_routes import STAFF_MENU
        from impacto.http import ROUTES
        api.load_all()
        em_rota = {r.permission for r in ROUTES if r.permission}
        orfas = sorted({p for *_, p in STAFF_MENU if p} - em_rota)
        self.assertEqual(orfas, [],
                         "o menu exige permissão que nenhuma rota declara: " + ", ".join(orfas))

    def test_a_role_that_lacks_the_permission_does_not_receive_the_item(self):
        """O lado que o teste tautológico cobria de verdade, mantido explicitamente."""
        for papeis, proibidas in ((("support",), {"finance.read", "accounting.read",
                                                  "treasury.read", "security.audit.read"}),
                                  (("editor",), {"finance.read", "billing.read", "health.read"}),
                                  (("analyst",), {"finance.approve", "accounting.close"})):
            with self.subTest(papeis=papeis):
                ctx = self._contexto(*papeis)
                oferecidas = {i["permission"] for g in ctx["menu"] for i in g["items"]}
                self.assertEqual(oferecidas & proibidas, set())

    def test_the_menu_items_are_reachable_by_the_role_that_receives_them(self):
        """Exercita a PORTA de verdade: cada papel chama uma rota de cada permissão que recebeu.

        É o teste que a auditoria usou para encontrar o defeito, virado ratchet: ele não lê
        permissão nenhuma do contexto — ele bate na API e confere que não leva 403.
        """
        from impacto import api
        from impacto.http import ROUTES
        api.load_all()
        # Uma rota GET por permissão, sem parâmetro de caminho, para poder ser chamada direto.
        por_permissao: dict[str, str] = {}
        for r in ROUTES:
            if r.permission and r.method == "GET" and "{" not in r.path:
                por_permissao.setdefault(r.permission, r.path)
        for papeis in (("support",), ("finance",), ("accounting",), ("controller",),
                       ("treasury",), ("operations",), ("audit",), ("compliance",),
                       ("security",), ("billing",), ("analyst",), ("editor",)):
            cliente = make_staff(*papeis)
            ctx = cliente.get("/v1/me/context").json
            for g in ctx["menu"]:
                for item in g["items"]:
                    rota = por_permissao.get(item["permission"])
                    if not rota:
                        continue   # permissão só usada em escrita; coberta pelo teste de órfãs
                    with self.subTest(papeis=papeis, item=item["label"]):
                        r = cliente.get(rota)
                        self.assertNotEqual(
                            r.status, 403,
                            f"{papeis} recebe '{item['label']}' no menu e leva 403 em {rota}")

    def test_an_auditor_gets_a_read_only_menu_and_is_told_so(self):
        ctx = self._contexto("audit")
        self.assertTrue(ctx["staff"]["read_only"])
        oferecidas = {i["permission"] for g in ctx["menu"] for i in g["items"]}
        for escrita in ("finance.write", "accounting.write", "billing.write", "treasury.write",
                        "admin.users.write", "maintenance.execute"):
            self.assertNotIn(escrita, oferecidas)

    def test_a_client_organization_gets_no_internal_menu_at_all(self):
        cliente = new_account("osc")
        r = cliente.get("/v1/me/context")
        self.assertEqual(r.status, 200, r)
        self.assertEqual(r.json["menu"], [], "cliente não tem menu interno — nem vazio com títulos")
        self.assertEqual(r.json["staff"]["roles"], [])

    def test_the_super_admin_sees_every_group(self):
        """Quem tem o booleano recebe o catálogo inteiro, incluindo a permissão criada amanhã."""
        from impacto.api.access_routes import STAFF_MENU
        c, _ = make_admin()
        r = c.get("/v1/me/context")
        self.assertEqual(r.status, 200, r)
        grupos_vistos = {g["group"] for g in r.json["menu"]}
        self.assertEqual(grupos_vistos, {g for _, _, g, _ in STAFF_MENU})


class NothingBuiltStaysInvisibleTests(unittest.TestCase):
    """Toda permissão declarada em rota tem de ter um caminho de tela que a use.

    É o teste que transforma "224 rotas sem tela" num defeito que reprova, em vez de uma descoberta
    de auditoria. Confere por DOMÍNIO da permissão (`finance`, `accounting`, `health`…): exigir uma
    entrada de menu por permissão faria o menu ter uma linha por verbo, o que não é um menu.
    """

    def test_every_permission_domain_used_by_a_route_appears_in_the_menu(self):
        from impacto.api.access_routes import STAFF_MENU
        from impacto.http import ROUTES
        dominios_em_rota = {r.permission.split(".")[0] for r in ROUTES if r.permission}
        dominios_no_menu = {p.split(".")[0] for *_, p in STAFF_MENU if p}
        self.assertGreater(len(dominios_em_rota), 8)
        orfaos = dominios_em_rota - dominios_no_menu
        self.assertEqual(orfaos, set(),
                         f"domínios com rota e sem nenhuma tela: {sorted(orfaos)}")

    def test_the_dashboard_each_role_receives_is_a_page_that_exists(self):
        rotas = _rotas_do_frontend()
        for papeis in (("controller",), ("accounting",), ("treasury",), ("finance",),
                       ("operations",), ("audit",), ("security",), ("support",), ("editor",)):
            with self.subTest(papeis=papeis):
                c = make_staff(*papeis)
                destino = c.get("/v1/me/context").json["dashboard"]
                self.assertIn(destino, rotas, f"{papeis} é mandado para {destino}, que não existe")

    def test_a_client_is_sent_to_a_page_that_exists(self):
        rotas = _rotas_do_frontend()
        cliente = new_account("osc")
        self.assertIn(cliente.get("/v1/me/context").json["dashboard"], rotas)


class TheResolverSendsPeopleHomeTests(unittest.TestCase):
    """O destino do login. Quatro testes de ponta a ponta encontraram três erros aqui.

    1. Cliente ia para `/area` (a área de trabalho da persona) quando a casa dele é `/`. Foi uma
       mudança de produto que esta rodada não precisava fazer.
    2. `super_admin` ia para `/controladoria`, porque tem TODAS as permissões e casava com a
       primeira regra de especialidade. Quem tem tudo não tem especialidade: a casa dele é a torre
       de controle.
    3. A torre de controle exige que a organização ATIVA seja a plataforma — regra da interface.
       Quem administra e tem também uma OSC ativa ia para uma tela de "área não disponível".
    """

    def test_a_client_goes_to_the_home_of_its_organization(self):
        cliente = new_account("osc")
        self.assertEqual(cliente.get("/v1/me/context").json["dashboard"], "/")

    def test_a_platform_admin_with_a_client_org_active_goes_to_that_org(self):
        from tests.support import make_admin_without_reauth
        adm = make_admin_without_reauth()
        ctx = adm.get("/v1/me/context").json
        destino = ctx["dashboard"]
        if ctx["organization"]["kind"] == "platform":
            self.assertEqual(destino, "/admin")
        else:
            self.assertEqual(destino, "/", "administrador com OSC ativa mandado para /admin")

    def test_a_platform_admin_on_the_platform_goes_to_the_control_tower(self):
        c, _ = make_admin()
        ctx = c.get("/v1/me/context").json
        self.assertEqual(ctx["organization"]["kind"], "platform")
        self.assertEqual(ctx["dashboard"], "/admin",
                         "quem tem todas as permissões não tem especialidade: a casa é a torre")

    def test_a_specialized_role_goes_to_its_own_panel(self):
        for papel, destino in (("controller", "/controladoria"), ("accounting", "/contabilidade"),
                               ("treasury", "/tesouraria"), ("finance", "/financeiro"),
                               ("operations", "/operacoes"), ("audit", "/auditoria")):
            with self.subTest(papel=papel):
                c = make_staff(papel)
                self.assertEqual(c.get("/v1/me/context").json["dashboard"], destino)

    def test_the_portal_forwards_instead_of_interrupting(self):
        """A tela do portal não pode voltar a parar todo login.

        Ela parava quem tem mais de uma organização para oferecer a troca de contexto — mas o
        contexto JÁ está resolvido, e a pessoa passava a ver uma tela intermediária todos os dias
        para confirmar o que o servidor decidiu. O encaminhamento é condicionado a existir
        organização ativa; a cadeia aparece quando a pessoa abre o portal de propósito.
        """
        texto = (Path(ROOT) / "web" / "src" / "pages" / "portal.tsx").read_text(encoding="utf-8")
        self.assertIn("escolher", texto,
                      "o portal precisa distinguir 'cheguei do login' de 'abri de propósito'")
        self.assertIn("navigate(ctx.dashboard, true)", texto,
                      "o portal deixou de encaminhar ao painel resolvido")
        # E a porta de entrada deliberada existe no menu, senão a tela só é alcançada uma vez.
        self.assertIn("/portal?escolher=1", APP_TSX.read_text(encoding="utf-8"))


class TheScreensCallRoutesThatExistTests(unittest.TestCase):
    """Toda chamada de API das telas internas tem de existir no roteador.

    A tela de Orçamento chamava `/v1/administrativo/orcamento` e a rota era
    `/v1/administrativo/budget`: a tela SEMPRE mostrava erro, e nenhum teste pegava — o teste de
    menu confere o caminho do roteador WEB, não a chamada de API. Encontrado por auditoria
    independente.
    """

    def test_every_api_path_called_by_the_internal_pages_is_a_real_route(self):
        from impacto import api
        from impacto.http import ROUTES
        api.load_all()

        def casa(padrao: str, caminho: str) -> bool:
            """O padrão do roteador com `{param}` casando um segmento qualquer."""
            regex = "^" + re.sub(r"\{[^}]+\}", r"[^/]+", re.escape(padrao)
                                 .replace(r"\{", "{").replace(r"\}", "}")) + "$"
            return re.match(regex, caminho) is not None
        paginas = [Path(ROOT) / "web" / "src" / "pages" / nome
                   for nome in ("internal.tsx", "portal.tsx")]
        paginas.append(Path(ROOT) / "web" / "src" / "access.tsx")
        chamadas: set[str] = set()
        for f in paginas:
            texto = f.read_text(encoding="utf-8")
            # `useLoad("/v1/...")`, `api.get("/v1/...")`, `api.post(\`/v1/...\`)`
            chamadas |= set(re.findall(r'["`](/v1/[^"`?\s]+)', texto))
        self.assertGreater(len(chamadas), 10, "não consegui ler as chamadas das telas")
        caminhos = {r.path for r in ROUTES}
        faltando = []
        for chamada in sorted(chamadas):
            if chamada in caminhos:
                continue
            # Caminho com interpolação (`${id}`) casa contra o padrão com parâmetro.
            alvo = re.sub(r"\$\{[^}]+\}", "x", chamada)
            if any(casa(r.path, alvo) for r in ROUTES):
                continue
            faltando.append(chamada)
        self.assertEqual(faltando, [],
                         "a tela chama rota que não existe: " + ", ".join(faltando))


class EveryPermissionInTheCatalogGuardsSomethingTests(unittest.TestCase):
    """Permissão que não guarda rota nenhuma é permissão que não protege nada.

    Ela é pior do que inútil: aparece na matriz, pode ser concedida, dá a impressão de que a área
    está protegida por ela — e a rota correspondente, se existir, está atrás de outra coisa (ou só
    do booleano de administrador). Auditoria independente encontrou 19 permissões nesse estado.

    A lista abaixo é o que RESTA, cada uma com o motivo. Uma permissão nova que não guarde rota
    reprova a suíte: é assim que a lista encolhe em vez de crescer.
    """

    # permissão → por que ainda não guarda rota
    SEM_ROTA = {
        # Escrita cuja rota existe e ainda está atrás do booleano de administrador. Declará-la
        # agora exigiria rever cada handler; a dívida está nomeada em AUTHORIZATION.md §12.
        "admin.organizations.write": "rota de organização ainda exige is_platform_admin",
        "content.write": "CMS da Central ainda usa `staff=` (editor/revisor), da v0.12.0",
        "content.publish": "idem: o fluxo editorial tem quatro olhos próprios",
        "support.write": "fila de suporte ainda usa `staff=('support',)`",
        "security.audit.export": "a exportação da trilha não tem rota: hoje se lê, não se exporta",
        # Escrita de recurso que EXISTE no banco e ainda não tem rota de escrita — e não deveria
        # ganhar uma sem decisão: mexer nestes muda a régua de todas as medições.
        "budget.write": "orçamento é carregado por migração/seed; não há rota que o edite",
        "cost_center.read": "centros de custo saem junto do plano de contas (accounting.read)",
        "cost_center.write": "idem: não há rota que crie ou altere centro de custo",
        "treasury.write": "tesouraria é LEITURA do patrimônio próprio; não há escrita a oferecer",
        # Recusadas por decisão de arquitetura, não por falta de tempo.
        "billing.refund": "não há rota de estorno: nenhum provedor de pagamento está ligado, e "
                          "estornar o que não foi cobrado não existe. A faixa de alçada está "
                          "cadastrada e inerte, esperando a rota (FINANCIAL_ENGINE.md §9)",
        "fiscal.issue": "nenhum provedor fiscal ligado: a permissão existe, a emissão não",
        "fiscal.cancel": "idem: cancelar documento fiscal exige provedor fiscal contratado",
    }

    def test_the_list_of_permissions_without_a_route_does_not_grow(self):
        from impacto import api
        from impacto.http import ROUTES
        api.load_all()
        with db_system() as c:
            catalogo = {r["permission"] for r in c.query(
                "SELECT permission FROM permission_catalog")}
        em_rota = {r.permission for r in ROUTES if r.permission}
        orfas = catalogo - em_rota
        novas = sorted(orfas - set(self.SEM_ROTA))
        self.assertEqual(novas, [],
                         "permissão nova que não guarda rota nenhuma: " + ", ".join(novas)
                         + ". Declare-a numa rota, ou acrescente-a a SEM_ROTA com o motivo.")
        # E o inverso: entrada na lista que JÁ ganhou rota tem de sair, senão a lista passa a
        # descrever um passado.
        resolvidas = sorted(set(self.SEM_ROTA) & em_rota)
        self.assertEqual(resolvidas, [],
                         "estas já guardam rota e podem sair de SEM_ROTA: "
                         + ", ".join(resolvidas))

    def test_every_reason_is_written(self):
        for permissao, motivo in self.SEM_ROTA.items():
            with self.subTest(permissao=permissao):
                self.assertGreaterEqual(len(motivo), 30,
                                        "motivo curto demais para ser um motivo")


class TheInternalPagesExistInTheBuildTests(unittest.TestCase):
    """As telas internas estão no pacote que vai para produção, não só no repositório."""

    def test_the_internal_panels_are_wired_into_the_router(self):
        texto = APP_TSX.read_text(encoding="utf-8")
        for pagina in ("Int.Controladoria", "Int.Financeiro", "Int.Contabilidade",
                       "Int.Tesouraria", "Int.Operacoes", "Int.Alertas", "Int.Aprovacoes",
                       "Int.Orcamento", "Int.AcessoPrivilegiado", "Int.MatrizPermissoes",
                       "Portal.Portal"):
            self.assertIn(pagina, texto, f"{pagina} não está no roteador")

    def test_the_platform_sidebar_is_no_longer_a_fixed_list_for_everyone(self):
        """Dois papéis diferentes recebem menus DIFERENTES — a conferência de comportamento.

        A primeira versão deste teste procurava a string `"is_platform_admin ? NAV.platform.filter"`
        no fonte: afirmava sobre o código, não sobre o produto. A conferência que importa é que o
        servidor realmente devolve menus distintos, e que a barra lateral os consome.
        """
        suporte = make_staff("support").get("/v1/me/context").json["menu"]
        contabil = make_staff("accounting").get("/v1/me/context").json["menu"]
        self.assertNotEqual(
            {g["group"] for g in suporte}, {g["group"] for g in contabil},
            "dois papéis com funções diferentes receberam o mesmo menu")
        self.assertIn("ctx?.menu", APP_TSX.read_text(encoding="utf-8"),
                      "a barra lateral não consome o menu do servidor")




class OneJobTrailTests(unittest.TestCase):
    """Uma tabela de execução de tarefa, com duração e erro — não duas com respostas diferentes.

    Havia `job_runs` (22 tarefas, sem duração, sem campo de erro) e `ops_job_runs` (2 tarefas, com
    as duas coisas). Perguntar "o backup rodou?" dava respostas diferentes dependendo de onde se
    olhava, e a tabela que cobria mais tarefas era a que sabia menos sobre elas.
    """

    def test_the_old_table_is_gone_from_the_schema(self):
        with db_system() as c:
            self.assertEqual(
                c.scalar("SELECT count(*) FROM information_schema.tables"
                         " WHERE table_schema = 'public' AND table_name = 'job_runs'"), 0,
                "deixar a tabela antiga vazia no esquema garante que alguém volte a escrever nela")

    def test_only_one_module_writes_the_trail(self):
        from pathlib import Path
        pkg = Path(ROOT) / "backend" / "impacto"
        escritores = sorted(
            str(f.relative_to(pkg)) for f in pkg.rglob("*.py")
            if "INSERT INTO ops_job_runs" in f.read_text(encoding="utf-8"))
        self.assertEqual(escritores, ["ops/runs.py"],
                         "duas pessoas escrevendo a mesma trilha é como ela volta a divergir")

    def test_a_failing_job_keeps_its_error_and_its_duration(self):
        from impacto.ops import runs as RUNS
        with db_system() as c:
            with self.assertRaises(ValueError):
                with RUNS.record(c, "teste_falho") as r:
                    r["detail"] = {"etapa": "meio"}
                    raise ValueError("estourou de propósito")
            ultimo = RUNS.last(c, "teste_falho")
            self.assertEqual(ultimo["status"], "failed")
            self.assertIn("estourou de propósito", ultimo["error"])
            self.assertIsNotNone(ultimo["duration_ms"])
            self.assertIsNotNone(ultimo["finished_at"])

    def test_an_open_run_is_running_and_not_skipped(self):
        """Execução em curso não é "pulada": o painel de operações precisa poder distinguir."""
        from impacto.ops import runs as RUNS
        with db_system() as c:
            with RUNS.record(c, "teste_em_curso") as r:
                self.assertEqual(
                    c.scalar("SELECT status FROM ops_job_runs WHERE job = 'teste_em_curso'"
                             " ORDER BY id DESC LIMIT 1"), "running")
                r["status"] = "ok"

    def test_due_counts_from_the_last_success_not_the_last_attempt(self):
        from impacto.ops import runs as RUNS
        with db_system() as c:
            with RUNS.record(c, "teste_vencimento") as r:
                r["status"] = "ok"
            self.assertFalse(RUNS.due(c, "teste_vencimento", every_seconds=86400))
            with self.assertRaises(RuntimeError):
                with RUNS.record(c, "teste_vencimento"):
                    raise RuntimeError("falhou depois do sucesso")
            # Depois de uma FALHA, a tarefa continua "não vencida" porque o último SUCESSO é
            # recente. Contar da última tentativa faria a falha repetida parecer "já rodou".
            self.assertFalse(RUNS.due(c, "teste_vencimento", every_seconds=86400))
            # E uma tarefa que nunca rodou está vencida — senão ela nunca começa.
            self.assertTrue(RUNS.due(c, "teste_nunca_rodou", every_seconds=86400))
            # (A janela não é exercitada com segundos: dentro de uma transação `now()` está
            # congelado no início dela, então qualquer janela positiva daria o mesmo resultado.)


class TheDemoSeedFillsTheInternalScreensTests(unittest.TestCase):
    """A demonstração interna RODA. Um seed que quebra em silêncio não demonstra nada.

    Até a v0.21.0 era impossível abrir qualquer tela financeira e ver algo: a demonstração criava
    um administrador único e nenhum lançamento. E, sem uma conta por FUNÇÃO, a separação entre quem
    atende chamado e quem vê receita existia no banco e não aparecia para ninguém.
    """

    def test_the_internal_finance_seed_runs_against_the_real_triggers(self):
        with self.assertRaises(_Rollback):
            self._cenario()

    def _cenario(self):
        import uuid
        from datetime import datetime, UTC
        from impacto.api.access_routes import STAFF_MENU
        sufixo = uuid.uuid4().hex[:8]
        with db_system() as c:
            plat = c.scalar("SELECT id::text FROM organizations WHERE kind = 'platform' LIMIT 1") \
                or c.scalar("INSERT INTO organizations(kind, legal_name, compliance_status)"
                            " VALUES ('platform','Plataforma','approved') RETURNING id::text")

            def criar(email, nome, oid, admin=False):
                uid = c.scalar("INSERT INTO users(email, full_name, email_verified_at)"
                               " VALUES ($1,$2, now()) RETURNING id::text",
                               email.replace("@", f"+{sufixo}@"), nome)
                c.run("INSERT INTO memberships(user_id, org_id, role) VALUES ($1,$2,'viewer')",
                      uid, oid)
                return uid

            from impacto import seed_dev
            seed_dev._seed_internal_finance(c, plat, criar, datetime.now(UTC))

            # O que cada tela interna precisa encontrar para poder ser conferida por uma pessoa.
            self.assertGreater(c.scalar("SELECT count(*) FROM accounting_entries"), 0)
            self.assertGreater(c.scalar("SELECT count(*) FROM platform_expenses"), 0)
            self.assertGreater(c.scalar("SELECT count(*) FROM platform_budget_items"), 0)
            self.assertGreater(c.scalar("SELECT count(*) FROM payment_instructions"), 0)
            self.assertGreater(c.scalar("SELECT count(*) FROM approval_requests"
                                        " WHERE state = 'pending'"), 0)
            # Todo lote DO SEED tem de fechar: um seed que deixa a contabilidade torta impede o
            # fechamento e ensina que "não fecha" é normal. A conferência é escopada aos lotes
            # criados aqui — outro teste desta suíte grava um lote torto de propósito, para provar
            # que o fechamento o recusa, e uma conferência global acusaria aquele lote.
            self.assertEqual(c.scalar(
                "SELECT count(*) FROM (SELECT batch_is_balanced(a.batch_id) ok"
                "  FROM accounting_entries a JOIN users u ON u.id = a.created_by"
                "  WHERE u.email LIKE $1 GROUP BY a.batch_id) q WHERE NOT q.ok",
                f"%+{sufixo}@%"), 0)
            self.assertGreater(c.scalar(
                "SELECT count(DISTINCT a.batch_id) FROM accounting_entries a"
                "  JOIN users u ON u.id = a.created_by WHERE u.email LIKE $1",
                f"%+{sufixo}@%"), 0, "o seed não lançou nada")
            # Uma instrução executada, com evidência: é o estado final do fluxo não-custodial.
            self.assertGreater(c.scalar("SELECT count(*) FROM payment_instructions"
                                        " WHERE state = 'executed'"
                                        "   AND evidence_doc IS NOT NULL"), 0)
            # E uma competência fechada, para a tela poder mostrar a diferença entre mês fechado
            # (citável) e mês aberto (em movimento).
            self.assertGreater(c.scalar("SELECT count(*) FROM accounting_periods"
                                        " WHERE status = 'closed'"), 0)
            # Cada grupo do menu interno tem alguém capaz de abri-lo na demonstração.
            papeis = {r["role"] for r in c.query(
                "SELECT DISTINCT role FROM staff_roles r JOIN users u ON u.id = r.user_id"
                " WHERE u.email LIKE $1", f"%+{sufixo}@%")}
            for esperado in ("controller", "finance", "accounting", "treasury", "operations",
                             "audit"):
                self.assertIn(esperado, papeis)
            self.assertGreater(len({g for _, _, g, _ in STAFF_MENU}), 5)
            raise _Rollback()

    def test_the_seed_identifies_every_record_it_creates_as_fictional(self):
        """Confere os REGISTROS no banco, não a contagem da palavra no fonte.

        A primeira versão contava ocorrências de "exemplo" em `seed_dev.py` — afirmava "todo
        registro" no nome e não olhava registro nenhum.
        """
        with self.assertRaises(_Rollback):
            self._cenario_marcacao()

    def _cenario_marcacao(self):
        import uuid
        from datetime import datetime, UTC
        sufixo = uuid.uuid4().hex[:8]
        with db_system() as c:
            plat = c.scalar("SELECT id::text FROM organizations WHERE kind = 'platform' LIMIT 1")

            def criar(email, nome, oid, admin=False):
                uid = c.scalar("INSERT INTO users(email, full_name, email_verified_at)"
                               " VALUES ($1,$2, now()) RETURNING id::text",
                               email.replace("@", f"+{sufixo}@"), nome)
                c.run("INSERT INTO memberships(user_id, org_id, role) VALUES ($1,$2,'viewer')",
                      uid, oid)
                return uid

            from impacto import seed_dev
            seed_dev._seed_internal_finance(c, plat, criar, datetime.now(UTC))
            # Escopado aos registros DESTE seed: outros testes desta suíte gravam nas mesmas
            # tabelas, e uma varredura global acusaria os registros deles.
            texto_livre = [
                ("platform_expenses", "description"),
                ("payment_instructions", "payee_name"),
                ("accounting_entries", "description"),
            ]
            for tabela, coluna in texto_livre:
                sem_marca = c.query(
                    f"SELECT t.{coluna} AS t FROM {tabela} t"
                    f" JOIN users u ON u.id = t.created_by"
                    f" WHERE u.email LIKE $1"
                    f"   AND t.{coluna} NOT ILIKE '%exemplo%' AND t.{coluna} NOT ILIKE '%fict%'"
                    f" LIMIT 5", f"%+{sufixo}@%")
                self.assertEqual(
                    [r["t"] for r in sem_marca], [],
                    f"{tabela}.{coluna} tem registro de demonstração sem se identificar")
            # E a varredura tem de ter encontrado registros, senão passaria vazia.
            self.assertGreater(c.scalar(
                "SELECT count(*) FROM platform_expenses e JOIN users u ON u.id = e.created_by"
                " WHERE u.email LIKE $1", f"%+{sufixo}@%"), 0)
            raise _Rollback()


class _Rollback(Exception):
    """Desfaz o cenário do seed: ele cria organização, usuários e contabilidade, e deixar isso no
    banco de teste mudaria a contagem de outros testes que leem as mesmas tabelas."""



class JobNamesAreIdentitiesNotSentencesTests(unittest.TestCase):
    """O nome da tarefa cabe na trilha e não carrega parâmetro dentro.

    `ops_job_runs.job` exige `^[a-z0-9_]{2,40}$`. A tabela antiga não exigia nada, e por isso uma
    tarefa se chamava `import:<nome da fonte do cadastro>` — identidade misturada com parâmetro, em
    texto livre vindo do banco. Ao unificar as duas trilhas, essa tarefa passou a estourar na
    restrição. O defeito não era a restrição: era o nome.
    """

    PADRAO = re.compile(r"^[a-z0-9_]{2,40}$")

    def test_every_registered_job_name_fits_the_trail(self):
        from impacto.jobs import JOBS
        for nome, _ in JOBS:
            self.assertRegex(nome, self.PADRAO, f"'{nome}' não cabe em ops_job_runs.job")

    def test_no_job_name_is_built_from_data(self):
        """Nome montado com f-string vem de dado e não é enumerável: a trilha deixa de ser trilha."""
        from pathlib import Path
        pkg = Path(ROOT) / "backend" / "impacto"
        suspeitos = []
        for f in pkg.rglob("*.py"):
            for i, linha in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                if re.search(r"(_run\(app,|RUNS\.record\([^,]+,|runs\.record\([^,]+,)\s*f[\"']", linha):
                    suspeitos.append(f"{f.name}:{i}: {linha.strip()[:90]}")
        self.assertEqual(suspeitos, [], "nome de tarefa montado a partir de dado:\n"
                                        + "\n".join(suspeitos))

    def test_every_literal_job_name_in_code_fits_the_trail(self):
        from pathlib import Path
        pkg = Path(ROOT) / "backend" / "impacto"
        for f in pkg.rglob("*.py"):
            for nome in re.findall(r'(?:_run\(app,|RUNS\.record\([^,]+,|runs\.record\([^,]+,)\s*"([^"]+)"',
                                   f.read_text(encoding="utf-8")):
                self.assertRegex(nome, self.PADRAO, f"{f.name}: '{nome}'")




class SystemContextNeverTravelsWithoutAPermissionTests(unittest.TestCase):
    """A isenção do guarda de arquitetura é por ARQUIVO, e isso precisa de um segundo guarda.

    `test_system_context_only_in_allowed_modules` lista `internal_routes.py` como revisado. Com o
    arquivo na lista, QUALQUER rota futura acrescentada a ele recebe contexto de sistema através do
    helper `_sys()` sem nada acender — e o guarda original existia justamente para forçar revisão
    caso a caso. Apontado por auditoria independente.

    Este teste é a revisão caso a caso, automatizada: naquele arquivo, toda rota tem de declarar
    `auth="admin"` e `permission=`. Contexto de sistema ignora a RLS; a permissão é a única porta
    que sobra.
    """

    def test_every_route_in_the_internal_module_declares_a_permission(self):
        from impacto import api
        from impacto.http import ROUTES
        api.load_all()
        from impacto.api import internal_routes as MOD
        nomes = {getattr(v, "__name__", None) for v in vars(MOD).values() if callable(v)}
        rotas = [r for r in ROUTES if getattr(r.handler, "__name__", None) in nomes
                 and getattr(r.handler, "__module__", "").endswith("internal_routes")]
        self.assertGreaterEqual(len(rotas), 15, "não consegui ler as rotas do módulo interno")
        for r in rotas:
            with self.subTest(rota=f"{r.method} {r.path}"):
                self.assertEqual(r.auth, "admin", "rota de operação interna sem auth=admin")
                self.assertTrue(r.permission,
                                "rota com contexto de sistema e SEM permissão declarada: a RLS "
                                "está desligada e não sobrou porta nenhuma")

    def test_the_write_routes_require_a_write_permission(self):
        """Rota que escreve exigindo permissão de leitura seria privilégio concedido por descuido."""
        from impacto import api
        from impacto.http import ROUTES
        api.load_all()
        for r in ROUTES:
            if not r.permission or r.method in ("GET", "HEAD"):
                continue
            with self.subTest(rota=f"{r.method} {r.path}"):
                self.assertFalse(
                    r.permission.endswith((".read", ".export")),
                    f"{r.method} {r.path} escreve e exige apenas `{r.permission}`")

    def test_no_read_route_requires_a_write_permission(self):
        """E o inverso: leitura pedindo permissão de escrita obriga a conceder escrita para ler."""
        from impacto import api
        from impacto.http import ROUTES
        api.load_all()
        escrita = (".write", ".approve", ".close", ".refund", ".issue", ".cancel", ".execute")
        for r in ROUTES:
            if not r.permission or r.method not in ("GET", "HEAD"):
                continue
            with self.subTest(rota=f"{r.method} {r.path}"):
                self.assertFalse(r.permission.endswith(escrita),
                                 f"GET {r.path} exige `{r.permission}`, uma permissão de escrita")


# A chamada direta do arquivo tinha `unittest.main()` NO MEIO: as classes definidas depois dele
# ainda não existiam quando ele rodava, e 9 testes não eram executados. Sob `unittest discover` o
# arquivo inteiro é importado primeiro, então o defeito só aparecia na execução direta — que é
# exatamente como se roda um arquivo ao investigar uma falha.
if __name__ == "__main__":
    unittest.main()
