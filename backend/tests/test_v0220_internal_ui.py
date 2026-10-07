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

    def test_every_item_offered_is_an_item_the_api_grants(self):
        for papeis in (("support",), ("finance",), ("accounting",), ("controller",),
                       ("treasury",), ("operations",), ("audit",), ("compliance",),
                       ("security",), ("billing",), ("analyst",), ("editor",)):
            with self.subTest(papeis=papeis):
                ctx = self._contexto(*papeis)
                tem = set(ctx["staff"]["permissions"])
                for g in ctx["menu"]:
                    for item in g["items"]:
                        self.assertIn(item["permission"], tem,
                                      f"{papeis} recebe '{item['label']}' sem a permissão")

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
        """A lista fixa só pode sobrar para quem tem o booleano — e o resto vem do servidor."""
        texto = APP_TSX.read_text(encoding="utf-8")
        self.assertIn("ctx?.menu", texto, "a barra lateral não consome o menu do servidor")
        self.assertIn("is_platform_admin ? NAV.platform.filter", texto,
                      "a lista fixa da plataforma precisa estar limitada a quem tem o booleano")


if __name__ == "__main__":
    unittest.main()


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
        from pathlib import Path
        texto = (Path(ROOT) / "backend" / "impacto" / "seed_dev.py").read_text(encoding="utf-8")
        trecho = texto[texto.index("_seed_internal_finance"):]
        self.assertGreater(trecho.lower().count("exemplo"), 10,
                           "todo registro da demonstração tem de se identificar como fictício")


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
