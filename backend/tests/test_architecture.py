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
                   "billing_routes.py", "monetization.py", "monetization_routes.py", "privacy_routes.py", "pool.py", "oidc.py", "ops_routes.py", "knowledge_routes.py", "content_admin_routes.py", "integration_routes.py", "hub.py"}
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
        sql = "\n".join(p.read_text(encoding="utf-8") for p in sorted((BACKEND / "migrations").glob("*.sql")))
        tables = set(re.findall(r"CREATE TABLE (\w+)", sql))
        self.assertIn("ENABLE ROW LEVEL SECURITY", sql)
        with_policy = set(re.findall(r"CREATE POLICY \w+ ON (\w+)", sql))
        self.assertEqual(tables - with_policy - {"chain_heads"}, set(), "Tabelas sem política RLS")

    def test_handlers_declare_auth(self):
        from impacto import api
        from impacto.http import ROUTES
        api.load_all()
        public = {r.path for r in ROUTES if r.auth == "none"}
        expected_public = {"/v1/auth/register", "/v1/auth/login", "/v1/auth/mfa/verify", "/v1/auth/refresh", "/v1/auth/verify-email",
                           "/v1/auth/forgot-password", "/v1/auth/reset-password", "/v1/plans", "/v1/files/{token}",
                           "/v1/billing/webhooks/stripe", "/v1/legal/{doc}",
                           "/v1/auth/oidc/start", "/v1/auth/oidc/callback",
                           "/v1/help/search", "/v1/help/context", "/v1/help/categories", "/v1/help/articles", "/v1/help/articles/{slug}", "/v1/help/faqs",
                           "/v1/help/resources", "/v1/help/resources/{slug}", "/v1/help/assistant", "/v1/help/events", "/v1/help/events/{slug}",
                           "/v1/help/courses", "/v1/help/courses/{slug}", "/v1/help/certificates/{code}", "/v1/help/partnerships", "/v1/help/demo-requests",
                           "/v1/help/newsletter", "/v1/help/newsletter/confirm", "/v1/help/newsletter/unsubscribe", "/v1/help/sitemap", "/v1/integrations/inbound/{connection_id}"}
        self.assertEqual(public, expected_public, "Nova rota pública precisa de revisão de segurança")
        for r in ROUTES:
            if r.path.startswith("/v1/admin/"):
                self.assertEqual(r.auth, "admin", r.path)

    def test_no_string_formatted_sql_with_user_input(self):
        """Só nomes de tabela/coluna de listas fixas podem ser interpolados em SQL (f-strings revisadas)."""
        risky = re.compile(r'c\.(query|one|scalar|run)\(f".*\{(body|q|ctx\.path|form)\.')
        for f in PKG.rglob("*.py"):
            for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                self.assertIsNone(risky.search(line), f"{f}:{i} interpola entrada do usuário em SQL")


if __name__ == "__main__":
    unittest.main()
