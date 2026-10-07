"""Testes de arquitetura (estáticos): invariantes de dependência, uso restrito do contexto de sistema, ausência de
segredos no repositório, migrations forward-only e cobertura de RLS em todas as tabelas."""
import ast
import re
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
PKG = BACKEND / "impacto"
ROOT = BACKEND.parent


def imports_of(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            out.add(("." * node.level) + mod)
            out |= {(("." * node.level) + mod + "." + a.name) for a in node.names}
    return out


class ArchitectureTests(unittest.TestCase):
    def test_match_and_directory_never_import_billing(self):
        """ADR-007/008: ranking/match não podem depender de plano, assinatura ou voucher."""
        targets = list((PKG / "engines" / "match").glob("*.py")) + [PKG / "services" / "matching.py", PKG / "services" / "directory.py"] \
            + list((PKG / "engines" / "solutions").glob("*.py")) + [PKG / "services" / "solutions.py", PKG / "api" / "solution_routes.py", PKG / "api" / "solution_flow_routes.py"]
        for f in targets:
            for imp in imports_of(f):
                self.assertNotRegex(imp, r"billing|entitlements|voucher", f"{f.name} importa {imp}")

    def test_system_context_only_in_allowed_modules(self):
        allowed = {"auth.py", "billing.py", "compliance.py", "workflow.py", "ratelimit.py", "http.py", "jobs.py", "cli.py", "seed_dev.py",
                   "app.py", "auth_routes.py", "org_routes.py", "application_routes.py", "execution_routes.py", "document_routes.py",
                   "billing_routes.py", "monetization.py", "monetization_routes.py", "privacy_routes.py", "pool.py", "oidc.py", "ops_routes.py", "complaint_routes.py", "knowledge_routes.py", "content_admin_routes.py", "integration_routes.py", "hub.py", "trust_routes.py", "platform_routes.py", "identity.py", "credentials.py",
                   "challenges.py", "agreements.py",
                   # v0.17.0: program_routes serve o programa PÚBLICO a quem não tem sessão. O contexto de
                   # sistema ali não é atalho — é o que permite responder sem organização ativa. A proteção
                   # vem de a consulta exigir visibility='public' AND published_at IS NOT NULL.
                   "program_routes.py",
                   "lifecycle_routes.py", "assembly_routes.py",
                   # v0.16.0 — camada de rede. Cada uso foi revisado e tem razão nomeada no próprio arquivo:
                   #   network_core_routes.py  → leitura de relações PÚBLICAS para quem não tem conta
                   #                             (passa por relationships.visible_to, que filtra por visibility)
                   #   network_hub_routes.py   → feed público do marketplace, perfil público (lê só public_fields),
                   #                             unicidade GLOBAL de @identificador (ADR 105) e moderação de anúncio
                   "network_core_routes.py", "network_hub_routes.py",
                   # v0.21.0 — camada comercial. Dois usos, ambos revisados:
                   #   GET /v1/commercial/usage  → a leitura SINCRONIZA o contador do período, e
                   #       `usage_counters` é escrita pela plataforma, não pela organização: se a
                   #       organização pudesse escrever nele, o histórico de consumo deixaria de ser
                   #       prova de consumo. O org_id continua preso ao da sessão.
                   #   GET /v1/admin/free-periods → painel de administração: precisa ver as
                   #       concessões de TODAS as organizações, que é justamente o que a RLS por
                   #       organização impede. A rota é auth="admin".
                   "commercial_routes.py",
                   # v0.22.0 — motor de acesso. Três usos, todos revisados:
                   #   GET /v1/me/context → lê `staff_permissions_of()` e o carimbo de
                   #       reautenticação da sessão; são dados da PRÓPRIA pessoa, e `staff_roles`
                   #       não é visível pelo contexto de organização.
                   #   POST /v1/auth/reauth → lê o hash de senha e o segredo de MFA do próprio
                   #       usuário e carimba a sessão dele; nenhum desses é alcançável por RLS de
                   #       organização, e é o mesmo caminho que `services/auth.py` já usa.
                   #   GET /v1/admin/privileged-access e /v1/admin/permissions → painel de
                   #       auditoria: precisa ver a trilha de TODAS as pessoas, que é exatamente o
                   #       que a RLS por organização impede. As duas são auth="admin" com
                   #       permissão declarada.
                   "access_routes.py",
                   #   core/access.py → monta o AccessContext. Precisa de contexto de sistema por
                   #       duas razões: `staff_permissions_of()` lê `staff_roles`, que a RLS de
                   #       organização não alcança; e o registro de acesso privilegiado escreve
                   #       numa trilha que a própria pessoa registrada não pode escrever pelo
                   #       contexto dela. O `user_id` vem sempre do principal da sessão.
                   "access.py",
                   #   api/internal_routes.py → painéis da PRÓPRIA plataforma (controladoria,
                   #       financeiro, contabilidade, tesouraria, operações). Não há organização
                   #       cliente a que a RLS pudesse restringir: o sujeito do dado é a
                   #       plataforma. Restringir ao `org_id` da sessão esconderia exatamente o
                   #       dado que o painel existe para mostrar, e prendê-lo à organização
                   #       `platform` faria o acesso depender de qual organização a pessoa tem
                   #       ativa — quem é da controladoria continua sendo da controladoria com a
                   #       própria OSC ativa. A porta é a PERMISSÃO declarada na rota
                   #       (`permission=`), conferida em test_v0220_authorization.py e
                   #       test_v0220_internal_ui.py, e cada entrada fica em
                   #       `privileged_access_log`.
                   "internal_routes.py"}
        for f in PKG.rglob("*.py"):
            src = f.read_text(encoding="utf-8")
            if "system_tx(" in src or "system=True" in src:
                self.assertIn(f.name, allowed, f"Contexto de sistema usado em módulo não revisado: {f}")

    def test_no_secrets_committed(self):
        patterns = [r"sk_live_[0-9a-zA-Z]{10,}", r"AKIA[0-9A-Z]{16}", r"-----BEGIN (RSA |EC )?PRIVATE KEY-----", r"xox[baprs]-[0-9a-zA-Z-]{10,}",
                    r"ghp_[0-9A-Za-z]{30,}", r"sk-ant-[0-9A-Za-z-]{20,}"]
        allow = {"test_unit.py", "test_architecture.py", "storage.py"}   # vetor público oficial da AWS (EXAMPLE)
        for f in ROOT.rglob("*"):
            if f.is_dir() or any(p in f.parts for p in ("node_modules", ".git", "dist", "data")) or f.suffix in (".png", ".pdf", ".zip", ".ico"):
                continue
            if f.name in allow:
                continue
            try:
                txt = f.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for p in patterns:
                self.assertIsNone(re.search(p, txt), f"Possível segredo em {f}")

    def test_every_table_has_rls(self):
        """Toda tabela tem política de RLS — e o guarda não se derrota com espaço em branco.

        A v0.22.0 descobriu que este teste lia `CREATE POLICY \\w+ ON (\\w+)`: uma declaração
        alinhada com dois espaços antes do `ON` não era encontrada, e a tabela aparecia como "sem
        política" mesmo tendo uma. O inverso é pior e era igualmente possível: alinhar o
        `CREATE TABLE` fazia a tabela desaparecer da conferência inteira, e uma tabela sem RLS
        passaria sem ninguém ver. Guarda que depende de formatação não é guarda.
        """
        sql = "\n".join(p.read_text(encoding="utf-8") for p in sorted((BACKEND / "migrations").glob("*.sql")))
        tables = set(re.findall(r"CREATE TABLE\s+(?:IF NOT EXISTS\s+)?(\w+)", sql))
        self.assertIn("ENABLE ROW LEVEL SECURITY", sql)
        with_policy = set(re.findall(r"CREATE POLICY\s+\w+\s+ON\s+(\w+)", sql))
        self.assertGreater(len(tables), 250, "a conferência precisa ver TODAS as tabelas")
        self.assertEqual(tables - with_policy - {"chain_heads"}, set(), "Tabelas sem política RLS")

    def test_handlers_declare_auth(self):
        from impacto import api
        from impacto.http import ROUTES
        api.load_all()
        public = {r.path for r in ROUTES if r.auth == "none"}
        expected_public = {"/v1/public/verify/{code}", "/v1/public/verify/{code}/qr", "/v1/public/campaigns/{slug}",
                           "/v1/public/locales", "/v1/public/translations", "/v1/public/glossary", "/v1/auth/register", "/v1/auth/login", "/v1/auth/mfa/verify", "/v1/auth/refresh", "/v1/auth/verify-email",
                           "/v1/auth/forgot-password", "/v1/auth/reset-password", "/v1/plans", "/v1/files/{token}",
                           "/v1/billing/webhooks/stripe", "/v1/legal/{doc}",
                           "/v1/auth/oidc/start", "/v1/auth/oidc/callback",
                           "/v1/help/search", "/v1/help/context", "/v1/help/categories", "/v1/help/articles", "/v1/help/articles/{slug}", "/v1/help/faqs",
                           "/v1/help/resources", "/v1/help/resources/{slug}", "/v1/help/assistant", "/v1/help/events", "/v1/help/events/{slug}",
                           "/v1/help/courses", "/v1/help/courses/{slug}", "/v1/help/certificates/{code}", "/v1/help/partnerships", "/v1/help/demo-requests",
                           "/v1/help/newsletter", "/v1/help/newsletter/confirm", "/v1/help/newsletter/unsubscribe", "/v1/help/sitemap", "/v1/integrations/inbound/{connection_id}",
                           # v0.16.0 — rede. Cada uma lê SÓ projeção pública ou estado de publicação:
                           # o feed lê marketplace_listings publicados; o perfil lê public_profiles.public_fields;
                           # as relações passam por relationships.visible_to, que filtra por visibility.
                           "/v1/marketplace/feed", "/v1/marketplace/listings/{listing_id}",
                           "/v1/public/profiles/{handle}", "/v1/public/profiles/{handle}/open-graph",
                           "/v1/public/relationships/{subject_type}/{subject_id}",
                           "/v1/public/projects/{project_id}/impact",
                           # tabela de preços: é pública por natureza, e o valor vem do servidor (nunca do cliente)
                           "/v1/plans/price",
                           # v0.17.0 — programa que a dona escolheu publicar. `programs_read` exige
                           # visibility='public' AND published_at IS NOT NULL AND status<>'suspended', e
                           # programs.public_feed() repete o filtro num único lugar.
                           "/v1/programs/feed", "/v1/programs/{program_id}",
                           # v0.17.0 — texto legal e situação dele. É público por obrigação: quem vai
                           # aceitar um documento precisa poder lê-lo ANTES de ter conta, e a minuta
                           # já se identifica como minuta na primeira linha. `legal_text()` nunca
                           # devolve versão superada, e aceite de minuta é recusado pelo banco.
                           "/v1/legal/registry", "/v1/legal/documents/{doc_key}"}
        self.assertEqual(public, expected_public, "Nova rota pública precisa de revisão de segurança")
        for r in ROUTES:
            if r.path.startswith("/v1/admin/"):
                self.assertEqual(r.auth, "admin", r.path)

    def test_every_declared_engine_resolves_to_real_code(self):
        """O registro de motores é declaração; este teste é o que a torna verificável."""
        from impacto.engines.registry import ENGINES, KINDS, resolve
        self.assertGreater(len(ENGINES), 20)
        keys = [e.key for e in ENGINES]
        self.assertEqual(len(keys), len(set(keys)), "chave de motor duplicada")
        for e in ENGINES:
            self.assertIn(e.kind, KINDS, e.key)
            self.assertTrue(callable(resolve(e)), f"{e.key}: {e.module}.{e.entrypoint}")
            self.assertTrue(e.produces.strip() and e.never.strip(),
                            f"{e.key}: motor sem 'o que produz' e 'o que nunca faz' não serve")

    def test_declared_engine_versions_match_the_modules(self):
        import importlib
        from impacto.engines.registry import ENGINES
        for e in ENGINES:
            real = getattr(importlib.import_module(e.module), e.version_attr, None)
            self.assertEqual(e.version, real,
                             f"{e.key}: versão declarada no registro difere da do módulo")

    def test_declared_engine_routes_exist(self):
        from impacto import api
        from impacto.engines.registry import ENGINES
        from impacto.http import ROUTES
        api.load_all()
        paths = {r.path for r in ROUTES}
        for e in ENGINES:
            for path in e.routes:
                self.assertIn(path, paths, f"{e.key} declara rota inexistente: {path}")

    def test_only_the_declared_places_call_the_language_model(self):
        """A trava que impede um chatbot novo entrar de carona.

        Se alguém acrescentar uma chamada ao modelo em outro módulo, esta varredura falha e obriga a
        declarar o ponto no registro — onde é preciso escrever o que ele nunca decide.
        """
        import re
        from pathlib import Path

        from impacto.engines.registry import AI_CALL_SITES
        root = Path(__file__).resolve().parents[1] / "impacto"
        call = re.compile(r"\.ai\.(structure_need|draft|summarize|complete)\s*\(")
        found = set()
        for py in root.rglob("*.py"):
            rel = py.relative_to(root.parent).as_posix()
            if rel.startswith("impacto/engines/ai/"):
                continue                       # o próprio gateway e o provedor local
            if call.search(py.read_text(encoding="utf-8")):
                found.add(rel)
        self.assertEqual(found, set(AI_CALL_SITES),
                         "chamada ao modelo fora dos pontos declarados em registry.AI_CALL_SITES")

    def test_deterministic_engines_do_not_import_the_ai_gateway(self):
        from pathlib import Path

        from impacto.engines.registry import ENGINES
        root = Path(__file__).resolve().parents[1]
        for e in ENGINES:
            if e.kind != "deterministic" or e.module.startswith("impacto.engines.ai"):
                continue
            src = (root / (e.module.replace(".", "/") + ".py"))
            if not src.exists():
                src = root / e.module.replace(".", "/") / "__init__.py"
            text = src.read_text(encoding="utf-8")
            self.assertNotIn("ai.gateway", text,
                             f"{e.key} é declarado determinístico mas importa o gateway de IA")

    def test_product_dates_are_utc(self):
        """`date.today()` usa o fuso LOCAL do processo; o banco opera em UTC. Misturar os dois erra por um dia.

        Encontrado na v0.16.0: com o servidor em UTC-4, às 00:40 UTC um documento vencido ontem era tratado como
        válido. O erro aparece numa janela de poucas horas por dia, então teste de meio-dia não o pega. A regra é
        usar `impacto.clock.today()`, que devolve a data UTC — a mesma que `current_date` no PostgreSQL.
        """
        offenders = []
        for f in PKG.rglob("*.py"):
            if f.name == "clock.py":
                continue
            src = f.read_text(encoding="utf-8")
            for i, line in enumerate(src.splitlines(), 1):
                if "date.today()" in line and not line.lstrip().startswith("#"):
                    offenders.append(f"{f.relative_to(PKG)}:{i}")
        self.assertEqual(offenders, [], f"Use impacto.clock.today() (UTC) em vez de date.today(): {offenders}")

    def test_recommendation_links_exist_in_the_app(self):
        """Toda recomendação leva a uma tela que existe.

        Encontrado na jornada 1 da v0.16.0: eu apontei uma recomendação para `/equipe`, rota que não existe (a
        gestão de equipe fica em `/organizacao`). O item apareceria no workspace e o clique cairia em "página não
        encontrada" — pior do que não recomendar nada.
        """
        from impacto.network.recommendation import ACTIONS, LINKS
        app = (PKG.parents[1] / "web" / "src" / "app.tsx").read_text(encoding="utf-8")
        declared = set(re.findall(r'\["(/[^"]*)",', app))
        self.assertEqual(sorted(set(ACTIONS) - set(LINKS)), [], "ação sem destino declarado")
        missing = []
        for action, link in LINKS.items():
            # `{id}` é substituído pelo identificador do sujeito; comparo o padrão com `:param`.
            pat = link.replace("{id}", ":id")
            if pat not in declared and pat.replace("/:id", "") not in declared:
                missing.append(f"{action} -> {link}")
        self.assertEqual(missing, [], f"recomendação apontando para tela inexistente: {missing}")

    def test_no_duplicate_routes(self):
        """Duas rotas com o mesmo método e caminho: a segunda fica inalcançável, em silêncio.

        Aconteceu na v0.16.0: `/v1/readiness` da camada de rede colidiu com a do diagnóstico (0013), e nada acusou —
        nem o lint, nem o type-check, nem o arranque. Só a ordenação de especificidade decidia qual respondia.
        """
        from collections import Counter

        from impacto import api
        from impacto.http import ROUTES
        api.load_all()
        dups = [k for k, n in Counter((r.method, r.path) for r in ROUTES).items() if n > 1]
        self.assertEqual(dups, [], f"Rotas duplicadas: {dups}")

    def test_network_engines_never_notify_directly(self):
        """Aviso sai SÓ por `network.notify`, que tem chave de idempotência.

        `app_notify` direto num motor da rede significa aviso repetido em reprocessamento de job ou webhook — o
        defeito que a v0.16.0 existe para corrigir. As rotas e motores da rede não chamam app_notify nem notify_user.
        """
        base = Path(__file__).resolve().parents[1] / "impacto"
        offenders = []
        for f in list((base / "network").glob("*.py")) + [base / "api" / "network_core_routes.py",
                                                          base / "api" / "network_hub_routes.py"]:
            src = f.read_text(encoding="utf-8")
            if f.name in ("notify.py",):
                continue
            for bad in ("app_notify", "notify_user(", "notify_once("):
                if bad in src:
                    offenders.append(f"{f.name}: {bad}")
        self.assertEqual(offenders, [], f"Aviso fora de network.notify: {offenders}")

    def test_prices_are_not_hard_coded(self):
        """Preço mora no banco (`plan_price_versions`, `monetization_rules`), nunca em código.

        A primeira versão deste teste lia os valores declarados em `config/plans.json` e procurava por
        eles no código. Deixou de valer na v0.17.0: o produto passou a NÃO declarar preço nenhum (as
        faixas institucionais são hipóteses, e sem preço a plataforma recusa cobrar), então a lista
        ficava vazia e o teste passava sem verificar nada.

        Agora a verificação é estática e não depende de haver preço declarado: nenhum literal monetário
        pode ser atribuído a um nome terminado em `_cents` no código de produção. Valor de centavos em
        teste é legítimo e fica fora do escopo.
        """
        # `x_cents = 1999`, `"amount_cents": 1999`, `amountCents: 1999` — com 3 ou mais dígitos, para
        # não acusar índice, limite ou multiplicador pequeno.
        pat = re.compile(r"""[A-Za-z_]*[cC]ents"?'?\s*[:=]\s*(\d{3,})""")
        offenders = []
        files = list(PKG.rglob("*.py")) + list((ROOT / "web" / "src").rglob("*.ts")) \
            + list((ROOT / "web" / "src").rglob("*.tsx"))
        for f in files:
            for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                if "#" in line and line.strip().startswith("#"):
                    continue
                for m in pat.finditer(line):
                    # Zero e valores de teste explicitamente marcados não contam.
                    if int(m.group(1)) == 0 or "noqa: price" in line:
                        continue
                    offenders.append(f"{f.relative_to(ROOT)}:{i}: {line.strip()[:120]}")
        self.assertEqual(offenders, [], "preço fixado em código:\n" + "\n".join(offenders))

    def test_the_commercial_rule_is_declared_in_configuration(self):
        """A regra comercial é dado versionado em git, não decisão espalhada pelo código."""
        import json
        cfg = json.loads((ROOT / "config" / "plans.json").read_text(encoding="utf-8"))
        self.assertIn("price_versions", cfg, "o bloco de regra comercial não pode desaparecer")
        self.assertTrue(cfg["price_versions"].get("_rule"),
                        "a regra vigente tem de estar escrita, para que mudá-la seja um ato explícito")
        # E a aposentadoria da regra anterior fica registrada, em vez de a linha simplesmente sumir.
        self.assertTrue(any(i.get("retire") for i in cfg["price_versions"]["items"]),
                        "aposentar um preço é um item com `retire`, não a remoção silenciosa da linha")

    def test_no_string_formatted_sql_with_user_input(self):
        """Só nomes de tabela/coluna de listas fixas podem ser interpolados em SQL (f-strings revisadas)."""
        risky = re.compile(r'c\.(query|one|scalar|run)\(f".*\{(body|q|ctx\.path|form)\.')
        for f in PKG.rglob("*.py"):
            for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                self.assertIsNone(risky.search(line), f"{f}:{i} interpola entrada do usuário em SQL")


if __name__ == "__main__":
    unittest.main()


class ReleasePackageTests(unittest.TestCase):
    """O pacote de entrega não pode levar dado local nem despejo de banco.

    Isto já aconteceu: `scripts/backup.sh` escreve em `backups/`, e `collect()` recolhia o `.dump` do banco de
    desenvolvimento — com o dado de quem usou o ambiente — para dentro do ZIP. Passou a ser teste.
    """

    @staticmethod
    def _collect() -> list[str]:
        import importlib.util
        spec = importlib.util.spec_from_file_location("make_release", ROOT / "scripts" / "make_release.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return [p.relative_to(mod.ROOT).as_posix() for p in mod.collect()]

    def test_package_has_no_database_dump_or_local_data(self):
        files = self._collect()
        self.assertTrue(files, "collect() não devolveu arquivo nenhum")
        forbidden = [f for f in files
                     if f.startswith(("backups/", "data/", "dist-release/"))
                     or f.endswith((".dump", ".bak", ".sqlite", ".sqlite3", ".db", ".tar", ".gz", ".zip",
                                    ".pem", ".key", ".p12", ".jks", ".keystore"))]
        self.assertEqual(forbidden, [], f"o pacote levaria dado local ou despejo de banco: {forbidden}")

    def test_package_has_no_nested_archive(self):
        self.assertEqual([f for f in self._collect() if f.endswith(".zip")], [],
                         "ZIP dentro de ZIP é proibido pela regra de entrega")


class EngineDocumentationTests(unittest.TestCase):
    """O documento `docs/AI_ENGINES.md` afirma números. Este teste os confere.

    Documento com número errado é pior que documento sem número: dá a impressão de auditoria.
    """

    def test_the_counts_in_the_document_match_the_registry(self):
        import re
        from pathlib import Path

        from impacto.engines.registry import describe
        d = describe()
        doc = (Path(__file__).resolve().parents[2] / "docs" / "AI_ENGINES.md").read_text(
            encoding="utf-8")
        self.assertIn(f"{d['total']} motores", doc)
        for kind, n in d["by_kind"].items():
            self.assertRegex(doc, rf"`{kind}` \| {n} \|",
                             f"o documento diz outro número para {kind} (real: {n})")
        declared_sites = re.findall(r"`backend/impacto/api/(\w+\.py)`", doc)
        self.assertIn("ai_routes.py", declared_sites)
