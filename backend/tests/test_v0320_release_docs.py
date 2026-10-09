"""v0.32.0 — o que a versão afirma sobre operação está no repositório.

* Worker com menor privilégio: o `CLAUDE.md` manda usar `sh /app/start_worker.sh` (ADR-365/368).
* Backup: ensaio de restauração do arquivo cifrado, mensal e manual, sem publicar artefato (ADR-369); as instruções de
  restauração não mandam mais um `pg_restore` direto.
* Contas de demonstração: modos no workflow `supabase`, com frase de confirmação (ADR-368).
* Demo: a faixa está na raiz do app e depende do modo que o servidor informa (ADR-370).
* Repositório privado: monitor horário; suíte completa fora do push na main (ADR-371).
"""
import re
import unittest

import yaml

from tests.support import ROOT

WF = ROOT / ".github" / "workflows"


def _wf(nome: str) -> dict:
    return yaml.safe_load((WF / nome).read_text(encoding="utf-8"))


class OperationDocTests(unittest.TestCase):
    def test_claude_md_tells_the_worker_to_drop_privileges(self):
        txt = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn("sh /app/start_worker.sh", txt)
        self.assertIn("ensaio-restauracao", txt)
        self.assertIn("contas-demo", txt)
        self.assertNotRegex(txt, r"(?i)(senha|password|secret|token)\s*[:=]\s*\S{8,}")


class BackupDrillTests(unittest.TestCase):
    def test_monthly_and_manual_restore_drill_of_the_encrypted_file(self):
        txt = (WF / "backup-supabase.yml").read_text(encoding="utf-8")
        d = _wf("backup-supabase.yml")
        crons = [c["cron"] for c in d[True]["schedule"]]
        self.assertIn("47 7 1 * *", crons)
        self.assertIn("ensaio-restauracao", d["jobs"])
        passos = " ".join(str(p.get("run", "")) for p in d["jobs"]["ensaio-restauracao"]["steps"])
        for trecho in ("sha256sum -c", "openssl enc -d", "managed_backup_restore.sh", "BACKUP_RESTORE_OK"):
            self.assertIn(trecho, passos)
        self.assertNotIn("upload-artifact", txt, "o backup tem dado pessoal: nada sai do job")
        cabecalho = txt.split("on:", 1)[0]
        self.assertNotRegex(cabecalho, r"(?m)^#\s+pg_restore --no-owner", "instrução antiga (falha) não pode voltar")


class DemoAccountsWorkflowTests(unittest.TestCase):
    def test_modes_exist_and_writes_need_the_phrase(self):
        d = _wf("supabase.yml")
        opcoes = d[True]["workflow_dispatch"]["inputs"]["modo"]["options"]
        for m in ("contas-demo-listar", "contas-demo-desativar", "contas-demo-reativar"):
            self.assertIn(m, opcoes)
        script = (ROOT / "scripts" / "demo_accounts.py").read_text(encoding="utf-8")
        self.assertIn('"DESATIVAR CONTAS DEMO"', script)
        self.assertIn('"REATIVAR CONTAS DEMO"', script)
        self.assertIn("kind <> 'platform'", script, "a organização da plataforma nunca é tocada")
        self.assertNotRegex(script, r"\bDELETE FROM\b", "desativar não apaga")


class DemoBannerTests(unittest.TestCase):
    def test_banner_is_mounted_at_the_root_and_follows_the_server_mode(self):
        main = (ROOT / "web" / "src" / "main.tsx").read_text(encoding="utf-8")
        self.assertIn("<DemoBanner />", main)
        comp = (ROOT / "web" / "src" / "ui" / "demobanner.tsx").read_text(encoding="utf-8")
        self.assertIn("/v1/meta/config", comp)
        self.assertIn('env === "development"', comp)
        self.assertIn("Não cadastre dados pessoais reais", comp)


class PrivateRepoBudgetTests(unittest.TestCase):
    def test_monitor_is_hourly_and_heavy_ci_skips_push(self):
        crons = [c["cron"] for c in _wf("monitor.yml")[True]["schedule"]]
        self.assertTrue(all(re.match(r"^\d+ \* \* \* \*$", c) for c in crons), crons)
        jobs = _wf("ci.yml")["jobs"]
        for nome in ("backend", "pilha-do-zero"):
            self.assertEqual(jobs[nome].get("if"), "github.event_name != 'push'", nome)


if __name__ == "__main__":
    unittest.main()
