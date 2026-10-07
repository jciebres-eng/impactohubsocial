"""Telas da v0.23.0: as rotas que elas chamam existem, e cada perfil alcança as que lhe cabem.

POR QUE ESTE ARQUIVO EXISTE

A v0.22.0 descobriu, por auditoria independente, que o menu prometia o que a porta recusava: quatro
papéis via item de menu para rota que lhes devolvia 403. E descobriu também que a tela de
instruções lia sete chaves de resposta que o servidor não devolvia — porque nada ligava o que a
tela pede ao que a rota entrega.

As duas lições viraram testes, e estes são os equivalentes para as telas desta versão:

  * toda rota citada no código do frontend existe no roteador do backend;
  * nenhuma chave lida pelas telas novas falta na resposta real;
  * cada item de menu é alcançável por quem o recebe.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from tests.support import db_system, make_staff, new_account

WEB = Path(__file__).parent.parent.parent / "web" / "src"
TELAS = ("pages/security.tsx", "pages/traceability.tsx")


def _fonte(*nomes: str) -> str:
    return "\n".join((WEB / n).read_text(encoding="utf-8") for n in nomes)


class TheScreensCallRoutesThatExistTests(unittest.TestCase):
    """O defeito que a v0.22.0 encontrou: a tela chamava `/v1/administrativo/budget` e a rota era
    `/v1/administrativo/orcamento`. Nada acusava até alguém abrir a tela."""

    @classmethod
    def setUpClass(cls):
        from impacto import api
        from impacto.http import ROUTES
        api.load_all()
        cls.rotas = {(r.method, r.path) for r in ROUTES}
        cls.caminhos = {r.path for r in ROUTES}

    def _casa(self, chamado: str) -> bool:
        """Compara ignorando parâmetro: `/v1/x/abc/provenance` casa `/v1/x/{id}/provenance`."""
        partes = chamado.strip("/").split("/")
        for caminho in self.caminhos:
            molde = caminho.strip("/").split("/")
            if len(molde) != len(partes):
                continue
            if all(m.startswith("{") or m == p for m, p in zip(molde, partes)):
                return True
        return False

    def test_every_route_the_new_screens_call_exists(self):
        codigo = _fonte(*TELAS)
        # Chamadas literais e por gabarito. O gabarito entra com o parâmetro substituído por `x`
        # para que a comparação por molde funcione.
        chamadas = set(re.findall(r'["\'`](/v1/[a-zA-Z0-9/_\-{}$.?=&]+)["\'`]', codigo))
        chamadas |= {re.sub(r"\$\{[^}]+\}", "x", c)
                     for c in re.findall(r'`(/v1/[^`]+)`', codigo)}
        self.assertTrue(chamadas, "a varredura não encontrou chamadas nas telas novas")
        faltando = []
        for c in sorted(chamadas):
            caminho = c.split("?")[0]
            if "${" in caminho:
                caminho = re.sub(r"\$\{[^}]+\}", "x", caminho)
            if not self._casa(caminho):
                faltando.append(c)
        self.assertEqual([], faltando, f"tela chama rota que não existe: {faltando}")

    def test_every_new_app_route_points_at_a_component_that_exists(self):
        """Rota registrada apontando para componente inexistente quebra só ao navegar."""
        app = _fonte("app.tsx")
        for rota, componente in re.findall(r'\["(/admin/(?:linha-do-tempo|rastro|proveniencia|'
                                           r'integridade|interruptor)|/conta/seguranca|/ia)",'
                                           r'\s*\(\)\s*=>\s*<(\w+\.\w+)', app):
            with self.subTest(rota=rota):
                modulo, nome = componente.split(".")
                arquivo = "pages/security.tsx" if modulo == "Sec" else "pages/traceability.tsx"
                self.assertIn(f"export function {nome}", _fonte(arquivo),
                              f"{rota} aponta para {componente}, que não existe")

    def test_the_new_menu_items_point_at_registered_routes(self):
        app = _fonte("app.tsx")
        registradas = set(re.findall(r'\["(/[a-z0-9/\-]+)",\s*\(\)\s*=>', app))
        novos = ["/ia", "/conta/seguranca", "/admin/linha-do-tempo", "/admin/rastro",
                 "/admin/proveniencia", "/admin/integridade", "/admin/interruptor"]
        for item in novos:
            with self.subTest(item=item):
                self.assertIn(f'["{item}", "', app, "item não está em nenhum menu")
                self.assertIn(item, registradas, "item de menu sem rota registrada")


class TheResponseKeysTheScreensReadAreActuallyReturnedTests(unittest.TestCase):
    """A tela lia sete chaves que o servidor não devolvia. Isto é o teste que faltava."""

    def test_the_security_center_returns_every_section_the_screen_reads(self):
        c = new_account("osc", compliance="approved")
        r = c.get("/v1/me/security")
        self.assertEqual(200, r.status, r.json)
        for chave in ("account", "sessions", "session_limits", "recent_events", "attention",
                      "access_changes", "api_keys", "api_keys_available", "integrations", "note"):
            with self.subTest(chave=chave):
                self.assertIn(chave, r.json)
        for campo in ("email", "mfa_enabled", "recovery_codes_left", "last_login_at",
                      "failed_login_count", "locked", "email_verified_at"):
            with self.subTest(campo=f"account.{campo}"):
                self.assertIn(campo, r.json["account"])

    def test_the_ai_panel_returns_the_three_controls_separately(self):
        c = new_account("osc", compliance="approved")
        r = c.get("/v1/ai/usage")
        self.assertEqual(200, r.status, r.json)
        self.assertIn("used_this_month", r.json["quota"])
        self.assertIn("limit", r.json["quota"])
        self.assertIn("balance", r.json["credits"])
        self.assertIn("outcomes_30d", r.json)
        self.assertIn("prompt_versions_30d", r.json)

    def test_the_ai_policies_screen_gets_tiers_and_guarantees(self):
        c = new_account("osc", compliance="approved")
        d = c.get("/v1/ai/policies").json
        self.assertTrue(d["guarantees"])
        for t in d["tiers"]:
            for campo in ("tier", "label", "allow_external", "requires_human_review", "note"):
                self.assertIn(campo, t)

    def test_the_kill_switch_screen_gets_scopes_history_and_exemptions(self):
        c, _ = __import__("tests.support", fromlist=["make_admin"]).make_admin()
        r = c.get("/v1/admin/kill-switch")
        self.assertEqual(200, r.status, r.json)
        for chave in ("scopes", "history", "exempt", "propagation_seconds", "note"):
            self.assertIn(chave, r.json)
        for s in r.json["scopes"]:
            for campo in ("scope", "engaged", "reason", "since", "effect"):
                self.assertIn(campo, s)

    def test_the_integrity_screen_gets_every_block_it_renders(self):
        c = make_staff("audit")
        d = c.get("/v1/admin/integrity").json
        for chave in ("state", "orphan_rows", "broken_chains", "polymorphic_columns_catalogued",
                      "polymorphic_columns_checked", "provenance", "chains", "catalog_drift",
                      "orphans", "unresolved_refs", "note"):
            with self.subTest(chave=chave):
                self.assertIn(chave, d)
        for cadeia in ("audit", "ledger", "value"):
            self.assertIn("scopes", d["chains"][cadeia])
            self.assertIn("broken", d["chains"][cadeia])
        self.assertIn("rows_without_chain", d["chains"]["value"])
        for campo in ("measurements", "with_evidence", "validated",
                      "validated_without_evidence", "coverage_pct", "rule"):
            self.assertIn(campo, d["provenance"])

    def test_the_timeline_screen_gets_the_fields_it_renders(self):
        from impacto.services.audit import record
        c = make_staff("audit")
        org = new_account("osc", compliance="approved").org_id
        with db_system() as conn:
            record(conn, org_id=org, actor=None, action="document.uploaded",
                   object_type="document", object_id="tela-1", resource_name="contrato.pdf",
                   correlation_id="tela-rastro-1", before={"a": 1}, after={"a": 2})
        d = c.get("/v1/admin/audit/timeline?object_type=document&object_id=tela-1").json
        self.assertEqual(1, d["count"])
        e = d["events"][0]
        for campo in ("action", "actor_type", "severity", "status", "source", "at",
                      "resource_name", "correlation_id", "before_state", "after_state", "category"):
            with self.subTest(campo=campo):
                self.assertIn(campo, e)

    def test_the_trail_screen_gets_depth_and_completeness(self):
        from impacto.services.audit import record
        c = make_staff("audit")
        org = new_account("osc", compliance="approved").org_id
        with db_system() as conn:
            raiz = record(conn, org_id=org, actor=None, action="document.uploaded",
                          object_type="document", object_id="tela-2", correlation_id="tela-rastro-2")
            record(conn, org_id=org, actor=None, action="document.approved",
                   object_type="document", object_id="tela-2", correlation_id="tela-rastro-2",
                   parent_event_id=raiz)
        d = c.get("/v1/admin/audit/trail?correlation_id=tela-rastro-2").json
        self.assertIn("complete", d)
        self.assertIn("events_in_trail", d)
        self.assertIn("events_in_tree", d)
        self.assertEqual([0, 1], [n["depth"] for n in d["tree"]])

    def test_the_provenance_screen_gets_chain_gaps_and_document(self):
        """Os três blocos da tela: a cadeia, as lacunas e o documento com hash."""
        from tests.support import grant_premium
        import datetime as dt
        c = new_account("osc", compliance="approved")
        grant_premium(c)
        pid = c.post("/v1/projects", {
            "title": "Projeto para a tela de proveniência",
            "summary": "Criado por teste para conferir o que a tela lê.",
            "problem": "p", "objectives": "o", "territory": "BR-AC-1200013",
            "causes": ["educacao"], "beneficiaries_count": 10, "budget_total_cents": 100_000,
            "starts_on": (dt.date.today() - dt.timedelta(days=5)).isoformat(),
            "ends_on": (dt.date.today() + dt.timedelta(days=60)).isoformat()}).json["id"]
        cat = c.get("/v1/indicators/catalog?ods=4").json["items"]
        ind = next(i for i in cat if i["code"] == "trained_people")
        pi = c.post(f"/v1/projects/{pid}/indicators", {
            "indicator_id": ind["id"], "baseline": 0, "target": 10,
            "baseline_source": "Lista inicial", "baseline_date": dt.date.today().isoformat(),
            "method": "Lista de presença"}).json["id"]
        vid = c.post(f"/v1/project-indicators/{pi}/values",
                     {"value": 5, "measured_on": dt.date.today().isoformat()}).json["id"]
        d = c.get(f"/v1/indicator-values/{vid}/provenance").json
        for chave in ("value", "indicator", "project", "evidence", "document", "validation",
                      "ledger", "audit", "chain", "gaps", "provenance_complete"):
            with self.subTest(chave=chave):
                self.assertIn(chave, d)
        for p in d["chain"]:
            for campo in ("step", "what", "who", "when", "present"):
                self.assertIn(campo, p)
        for g in d["gaps"]:
            for campo in ("link", "what", "effect"):
                self.assertIn(campo, g)


class EachRoleReachesWhatItsMenuPromisesTests(unittest.TestCase):
    """A lição da v0.22.0: item de menu que devolve 403 é promessa quebrada na cara de quem clica."""

    def test_a_client_organization_reaches_its_own_security_and_ai_screens(self):
        c = new_account("osc", compliance="approved")
        for caminho in ("/v1/me/security", "/v1/ai/usage", "/v1/ai/policies"):
            with self.subTest(caminho=caminho):
                self.assertEqual(200, c.get(caminho).status)

    def test_a_client_organization_does_not_reach_the_admin_screens(self):
        c = new_account("osc", compliance="approved")
        for caminho in ("/v1/admin/integrity", "/v1/admin/kill-switch",
                        "/v1/admin/audit/timeline?object_type=a&object_id=b"):
            with self.subTest(caminho=caminho):
                self.assertIn(c.get(caminho).status, (401, 403))

    def test_the_audit_role_reaches_the_traceability_screens(self):
        c = make_staff("audit")
        for caminho in ("/v1/admin/integrity",
                        "/v1/admin/audit/timeline?object_type=document&object_id=x",
                        "/v1/admin/audit/trail?correlation_id=x"):
            with self.subTest(caminho=caminho):
                self.assertEqual(200, c.get(caminho).status)

    def test_the_audit_role_does_not_reach_the_kill_switch(self):
        """Ler a trilha e PARAR a plataforma são poderes diferentes."""
        c = make_staff("audit")
        self.assertEqual(403, c.get("/v1/admin/kill-switch").status)


class TheScreensDoNotShipFakeDataTests(unittest.TestCase):
    """Tela de auditoria com dado de exemplo treina quem opera a confiar no que está vendo."""

    def test_no_screen_contains_a_hard_coded_uuid_or_hash(self):
        codigo = _fonte(*TELAS)
        uuids = re.findall(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", codigo)
        self.assertEqual([], uuids, f"identificador fixo no código da tela: {uuids}")
        hashes = re.findall(r"\b[0-9a-f]{40,}\b", codigo)
        self.assertEqual([], hashes, f"hash fixo no código da tela: {hashes}")

    def test_no_screen_invents_a_number_for_an_empty_state(self):
        """Estado vazio tem de dizer "nenhum", não mostrar zero como se fosse medição."""
        codigo = _fonte(*TELAS)
        self.assertIn("Nenhuma integração externa conectada", codigo)
        self.assertIn("Nenhum evento registrado", codigo)
        self.assertIn("nunca foi acionado", codigo)

    def test_the_screens_never_use_colour_as_the_only_signal(self):
        """Quem confere acesso suspeito pode ser daltônico, ou estar num celular ao sol."""
        codigo = _fonte(*TELAS)
        # Cada estado grave tem palavra junto: "atenção", "crítico", "ausente", "acionado".
        for palavra in ("atenção", "crítico", "ausente", "acionado", "não independente"):
            with self.subTest(palavra=palavra):
                self.assertIn(palavra, codigo)

    def test_the_provenance_screen_shows_the_gaps_not_only_the_chain(self):
        codigo = _fonte("pages/traceability.tsx")
        self.assertIn("O que falta para provar este número", codigo)
        self.assertIn("ausência de prova em aparência de prova", codigo)


if __name__ == "__main__":
    unittest.main()
