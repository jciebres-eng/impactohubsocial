"""v0.25.0 — a pilha de demonstração do zero é construída como o Supabase e testada no CI de ponta a ponta.

Este teste não sobe Docker (o ambiente de desenvolvimento não alcança registro de imagens); ele trava
a ESTRUTURA que o job `pilha-do-zero` do CI executa, para que ninguém a esvazie sem que a suíte acuse.
A prova de execução é o próprio job no GitHub (e o ensaio local registrado em docs/evidence).
"""
from __future__ import annotations

import re
import unittest

from tests.support import ROOT

DEMO = ROOT / "infra" / "compose" / "demo"
CI = ROOT / ".github" / "workflows" / "ci.yml"


class TheFromZeroStackIsShapedLikeSupabaseTests(unittest.TestCase):
    def test_the_admin_is_not_a_superuser_and_pgcrypto_lives_in_extensions(self):
        init = (DEMO / "db-init-supabase-like.sh").read_text(encoding="utf-8")
        self.assertIn("CREATEROLE NOSUPERUSER", init)
        self.assertIn("CREATE EXTENSION pgcrypto WITH SCHEMA extensions", init)
        self.assertIn("WITH GRANT OPTION", init)
        self.assertNotRegex(init, r"PASSWORD\s+'[^:]", "senha escrita no script de inicialização")

    def test_the_app_migrates_as_admin_and_runs_as_impacto_app(self):
        c = (DEMO / "compose.yml").read_text(encoding="utf-8")
        self.assertIn("DATABASE_URL: postgresql://impacto_admin:", c)
        self.assertIn('IMPACTO_BOOTSTRAP_EXTERNAL: "true"', c)
        self.assertIn("IMPACTO_ENV: development", c, "demonstração é development, e diz isso")
        self.assertIn("pg_isready -h 127.0.0.1", c, "saúde do banco por TCP: o socket diz pronto antes da hora")
        for var in ("POSTGRES_SUPERUSER_PASSWORD", "IMPACTO_ADMIN_PASSWORD", "IMPACTO_APP_PASSWORD",
                    "DEMO_PASSWORD", "DEMO_TOTP_SECRET"):
            self.assertRegex(c, r"\$\{" + var + r":\?", f"{var} tem de ser obrigatória, sem valor padrão")

    def test_the_ci_runs_journeys_screens_and_a_restart_against_the_stack(self):
        ci = CI.read_text(encoding="utf-8")
        job = ci[ci.index("  pilha-do-zero:"):]
        self.assertIn("docker compose -f infra/compose/demo/compose.yml", job)
        self.assertIn("scripts/demo_stack.py", job)
        self.assertIn("--telas", job)
        self.assertIn("--axe", job)
        self.assertIn("axe-core@4.10.2", job, "versão do axe fixada")
        self.assertIn("restart app", job)
        self.assertIn('test "$antes" = "$depois"', job)
        self.assertIn("::add-mask::", job, "segredos gerados na hora precisam ser mascarados")
        self.assertIsNone(re.search(r"\$\{\{\s*(github\.event|inputs)\.", job), "entrada externa interpolada no shell")

    def test_the_journeys_used_by_the_stack_never_touch_the_database(self):
        fonte = (ROOT / "backend" / "tests" / "demo_journeys.py").read_text(encoding="utf-8")
        corpo = fonte[fonte.index("class Jornadas"):fonte.index("def run(base")]
        for proibido in ("db_system", "owner_conn", "INSERT INTO", "UPDATE "):
            self.assertNotIn(proibido, corpo)
