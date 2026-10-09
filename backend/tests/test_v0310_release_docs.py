"""v0.31.0 — a documentação de infraestrutura diz a verdade sobre o repositório.

* Um caminho de publicação (ADR-364): não há `deploy.yml` nem `railway.json`/`railway.toml`; `pos-deploy.yml` só verifica.
* O worker (ADR-365) não migra, não faz bootstrap e não rotaciona senha; a imagem o carrega.
* Backup (ADR-366): o modo `backup-restaurar` não publica artefato (pode haver dado pessoal real).
* `INFRA_RAILWAY_SUPABASE_R2_v0310.md`: todo workflow citado existe; toda variável da tabela §3.1 é lida pelo código.
* O checklist do proprietário não pede segredo no chat.
"""
import re
import unittest

from tests.support import ROOT

WF = ROOT / ".github" / "workflows"
OPS = ROOT / "docs" / "ops"


class OnePublicationPathTests(unittest.TestCase):
    def test_no_parallel_deploy_workflow_and_no_deprecated_railway_config(self):
        self.assertFalse((WF / "deploy.yml").exists(), "deploy.yml era modelo com echo; o Railway publica pelo Git")
        for f in ("railway.json", "railway.toml"):
            self.assertFalse((ROOT / f).exists(), f"{f}: Config as Code do Railway está descontinuado (ADR-364)")

    def test_post_deploy_only_verifies(self):
        txt = (WF / "pos-deploy.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch", txt)
        for proibido in ("railway up", "railway deploy", "docker push", "impacto.db.migrate", "RAILWAY_TOKEN"):
            self.assertNotIn(proibido, txt, f"pos-deploy não publica nem migra: {proibido}")
        self.assertNotRegex(txt, r"(?m)^\s*push:", "pos-deploy não roda em push")

    def test_healthz_reports_the_deployed_commit(self):
        app = (ROOT / "backend" / "impacto" / "app.py").read_text(encoding="utf-8")
        self.assertIn("RAILWAY_GIT_COMMIT_SHA", app)
        self.assertIn('"commit": commit', app)


class WorkerTests(unittest.TestCase):
    sh = (ROOT / "backend" / "start_worker.sh").read_text(encoding="utf-8")

    def test_worker_never_migrates_bootstraps_or_rotates(self):
        codigo = "\n".join(l for l in self.sh.splitlines() if not l.lstrip().startswith("#"))
        self.assertIn("impacto.db.migrate --check", codigo)
        self.assertEqual(codigo.count("impacto.db.migrate"), 1, "o worker só CONFERE o esquema")
        for proibido in ("bootstrap_external", "IMPACTO_APP_ROTATE_PASSWORD", "seed-demo"):
            self.assertNotIn(proibido, codigo)
        self.assertIn("exec python3 -m impacto.jobs loop", codigo)
        self.assertIn("impacto.db.app_url", codigo, "o worker roda como impacto_app")

    def test_the_image_carries_the_worker_entrypoint(self):
        self.assertIn("COPY backend/start_worker.sh /app/start_worker.sh", (ROOT / "Dockerfile").read_text(encoding="utf-8"))


class BackupRestoreTests(unittest.TestCase):
    def test_managed_restore_mode_publishes_no_artifact_and_never_targets_the_source(self):
        wf = (WF / "supabase.yml").read_text(encoding="utf-8")
        self.assertIn("backup-restaurar", wf)
        self.assertNotIn("upload-artifact", wf, "o dump pode conter dado pessoal real")
        sh = (ROOT / "scripts" / "managed_backup_restore.sh").read_text(encoding="utf-8")
        self.assertIn("RECUSADO: origem e destino no mesmo host", sh)
        self.assertIn("--schema=public", sh)
        self.assertIn("trap 'rm -rf", sh)


class InfraDocTests(unittest.TestCase):
    txt = (OPS / "INFRA_RAILWAY_SUPABASE_R2_v0310.md").read_text(encoding="utf-8")

    def test_every_cited_workflow_exists(self):
        citados = set(re.findall(r"`(supabase|armazenamento|pos-deploy|ci)`", self.txt))
        self.assertGreaterEqual(len(citados), 3)
        for w in citados:
            self.assertTrue((WF / f"{w}.yml").exists(), w)

    def test_every_variable_in_the_service_table_is_read_by_the_code(self):
        sec = self.txt.split("### 3.1", 1)[1].split("## 4.", 1)[0]
        nomes = set(re.findall(r"`([A-Z][A-Z0-9_]{3,})`", sec))
        self.assertGreaterEqual(len(nomes), 20)
        fontes = "\n".join(p.read_text(encoding="utf-8") for p in [
            *(ROOT / "backend" / "impacto").rglob("*.py"), ROOT / "backend" / "start_container.sh", ROOT / "backend" / "start_worker.sh"])
        nao_lidas = sorted(n for n in nomes if n not in fontes)
        self.assertEqual(nao_lidas, [], "variável documentada que o código não lê")

    def test_it_states_what_is_proven_and_what_is_not(self):
        for frase in ("**comprovado por leitura**", "**não comprovado**", "RTO medido", "37975650545", "Hipótese a confirmar"):
            self.assertIn(frase, self.txt)


class OwnerChecklistTests(unittest.TestCase):
    def test_the_checklist_never_asks_for_a_secret_in_chat(self):
        txt = (OPS / "CHECKLIST_PROPRIETARIO_v0310.md").read_text(encoding="utf-8")
        self.assertIn("Nenhum valor secreto vai para o chat", txt)
        self.assertNotRegex(txt.lower(), r"(me envie|mande|cole aqui).{0,40}(senha|chave|token|secret)")


class BaselineDiffTests(unittest.TestCase):
    def test_the_baseline_identity_is_recorded_with_its_proof(self):
        txt = (ROOT / "docs" / "release" / "REPO_BASELINE_DIFF.md").read_text(encoding="utf-8")
        self.assertIn("d8aec4241bc1f5a5d09d2da63b2e8434a1ccf96972c14f47f4c2f23970a940c3", txt)
        self.assertIn("verify_package_against_git.py", txt)
        self.assertIn("dd2f8c3", txt)


if __name__ == "__main__":
    unittest.main()
