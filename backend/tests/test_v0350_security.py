"""v0.35.0 — correções da auditoria de segurança e integridade financeira (docs/security/AUDITORIA_SEGURANCA_FASE1.md).

Cada classe cita o ID do controle da matriz da auditoria. Os testes foram escritos para FALHAR no código da v0.34.0
(a falha de cada um está descrita na auditoria) e passar depois da correção. Todos usam PostgreSQL e HTTP reais e dados
sintéticos.
"""
from __future__ import annotations

import unittest
import uuid

from tests.support import Client, db_system, grant_premium, new_account, server, set_role

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def _project(osc: Client) -> str:
    r = osc.post("/v1/projects", {"title": "Projeto da diligência", "summary": "Resumo do projeto de teste",
                                  "territory": "BR-MT-5105259", "causes": ["educacao"], "beneficiaries_count": 10,
                                  "budget_total_cents": 500000})
    assert r.status == 201, r
    assert osc.post(f"/v1/projects/{r.json['id']}/publish").status == 200
    return r.json["id"]


def _upload(osc: Client, doc_type: str, title: str, **fields) -> str:
    r = osc.upload("/v1/documents", f"{doc_type}.pdf", PDF, {"doc_type": doc_type, "title": title, **fields})
    assert r.status == 201, r
    return r.json["id"]


def _diligence(osc: Client, funder: Client, pid: str) -> str:
    app = funder.post("/v1/applications/interest", {"project_id": pid})
    assert app.status in (200, 201), app
    aid = app.json["id"]
    assert osc.post(f"/v1/applications/{aid}/transition", {"to_status": "due_diligence"}).status == 200
    return aid


class DiligenceSeesOnlyInstitutionalDocumentsTests(unittest.TestCase):
    """FILE-07 — antes: financiador em diligência lia e via listado todo documento da OSC sem projeto (inclusive a
    exportação de dados e documentos de identidade) e continuava lendo depois de encerrada a candidatura."""

    @classmethod
    def setUpClass(cls):
        server()
        cls.osc = new_account("osc")
        grant_premium(cls.osc)
        cls.pid = _project(cls.osc)
        cls.estatuto = _upload(cls.osc, "estatuto_social", "Estatuto social")
        cls.interno = _upload(cls.osc, "outro", "Documento interno privado")
        cls.compartilhado = _upload(cls.osc, "outro", "Carta compartilhada com as partes", visibility="parties")
        cls.do_projeto = _upload(cls.osc, "cnd_federal", "CND do projeto", project_id=cls.pid)
        cls.dirigente = _upload(cls.osc, "documento_dirigente", "Documento pessoal da presidente")
        # documento anexado a uma verificação de identidade — mesmo com tipo institucional, nunca pela diligência
        ver = cls.osc.post("/v1/trust/identity/verifications", {"level": "document"})
        assert ver.status == 201, ver
        cls.identidade = _upload(cls.osc, "comprovante_endereco", "Comprovante de endereço da pessoa")
        att = cls.osc.post(f"/v1/trust/identity/verifications/{ver.json['id']}/documents",
                           {"document_id": cls.identidade, "kind": "proof_of_address"})
        assert att.status == 201, att
        exp = cls.osc.post("/v1/integrations/exports", {"dataset": "projects", "format": "csv"})
        assert exp.status == 201, exp
        cls.exportacao = exp.json["document_id"]
        cls.funder = new_account("company")
        cls.aid = _diligence(cls.osc, cls.funder, cls.pid)

    def _status(self, doc: str, quem: Client | None = None) -> int:
        return (quem or self.funder).post(f"/v1/documents/{doc}/download-url").status

    def test_institutional_project_and_explicitly_shared_documents_stay_available(self):
        for doc in (self.estatuto, self.do_projeto, self.compartilhado):
            self.assertEqual(self._status(doc), 200, doc)

    def test_private_export_personal_and_identity_documents_are_refused(self):
        for nome, doc in (("interno", self.interno), ("exportação de dados", self.exportacao),
                          ("documento de dirigente", self.dirigente), ("documento de identidade", self.identidade)):
            self.assertEqual(self._status(doc), 404, nome)
        listados = {d["id"] for d in self.funder.get(f"/v1/applications/{self.aid}").json.get("documents", [])}
        self.assertIn(self.estatuto, listados)
        for doc in (self.interno, self.exportacao, self.dirigente, self.identidade):
            self.assertNotIn(doc, listados, "a tela da candidatura listava o documento privado")

    def test_the_owner_still_sees_everything(self):
        for doc in (self.estatuto, self.interno, self.exportacao, self.dirigente, self.identidade):
            self.assertEqual(self._status(doc, self.osc), 200)

    def test_access_ends_when_the_application_closes(self):
        outro = new_account("company")
        aid = _diligence(self.osc, outro, self.pid)
        self.assertEqual(self._status(self.estatuto, outro), 200)
        with db_system() as c:      # o ciclo inteiro, pela máquina de estados do banco (não há atalho para 'closed')
            for estado in ("approved", "committed", "in_execution", "reporting", "closed"):
                c.run("UPDATE applications SET status = $2 WHERE id = $1", aid, estado)
        self.assertEqual(self._status(self.estatuto, outro), 404, "candidatura encerrada ainda abria os documentos")


class CommercialActsNeedTheOwnerTests(unittest.TestCase):
    """AUTHZ-02 — antes: aceitar oferta com autorização de cobrança, revogar a autorização e mudar o teto de gasto
    aceitavam qualquer membro da organização, até quem só tinha leitura."""

    def test_a_viewer_cannot_authorize_billing_revoke_or_change_the_spend_limit(self):
        from tests.test_v0210_offer import _oferta
        server()
        cli = new_account("osc")
        oferta = _oferta(cli)
        set_role(cli.user["id"], cli.org_id, "viewer")
        try:
            for metodo, rota, corpo in (
                    ("post", f"/v1/commercial/offers/{oferta['id']}/accept", {"consent_status": "authorized"}),
                    ("post", "/v1/commercial/consent/revoke", {"reason": "Teste de papel insuficiente"}),
                    ("put", "/v1/commercial/spend-limit", {"limit_cents": 10000, "action": "notify"})):
                r = getattr(cli, metodo)(rota, corpo)
                self.assertEqual((r.status, r.json["code"]), (403, "insufficient_role"), rota)
        finally:
            set_role(cli.user["id"], cli.org_id, "owner")
        r = cli.post(f"/v1/commercial/offers/{oferta['id']}/accept", {"consent_status": "authorized"})
        self.assertEqual(r.status, 200, r)

    def test_every_organization_write_route_declares_a_minimum_role(self):
        from impacto import api
        from impacto.http import ROUTES
        api.load_all()
        sem_papel = sorted(f"{r.method} {r.path}" for r in ROUTES
                           if r.auth == "org" and r.method in ("POST", "PUT", "PATCH", "DELETE") and not r.min_role)
        self.assertEqual(sem_papel, [], "rota de escrita da organização sem papel mínimo: qualquer membro (até leitura) passa")


class PublicBackersNeverShowACivilNameWithoutOptInTests(unittest.TestCase):
    """ID-01 — antes: a página pública da campanha por cotas mostrava o nome civil de apoiador pessoa física (último
    recurso do `coalesce`), sem passar pela regra de opt-in de `org_display()`."""

    def test_an_individual_backer_appears_masked_until_they_opt_in(self):
        from tests.test_v0140_trust import _publish_campaign
        server()
        osc = new_account("osc", compliance="approved")
        pr = osc.post("/v1/projects", {"title": "Projeto com cotas", "summary": "Projeto para financiamento em cotas.",
                                       "causes": ["educacao"], "territory": "MT"})
        pid = pr.json["id"]
        q = osc.post("/v1/funding-quotas", {"project_id": pid, "label": "Cota", "quota_cents": 20000, "total_quotas": 5}).json["id"]
        self.assertEqual(osc.patch(f"/v1/funding-quotas/{q}", {"status": "open"}).status, 200)
        nome_civil = f"Maria Civil {uuid.uuid4().hex[:6]}"
        pessoa = new_account("individual", legal_name=nome_civil)
        p = pessoa.post(f"/v1/funding-quotas/{q}/pledges", {"quantity": 1})
        self.assertEqual(p.status, 201, p)
        with db_system() as c:
            c.run("UPDATE quota_pledges SET status = 'confirmed' WHERE id = $1", p.json["id"])
        slug = f"cotas-{uuid.uuid4().hex[:8]}"
        camp = osc.post("/v1/campaigns", {"project_id": pid, "slug": slug, "title": "Campanha com apoiadores",
                                          "summary": "Campanha com a lista de apoiadores visível.", "show_backers": True,
                                          "purpose": "Atividades.", "contingency_policy": "Sem a meta, vai para as atividades.",
                                          "refund_policy": "Estorno pelo provedor."})
        self.assertEqual(camp.status, 201, camp)
        _publish_campaign(osc, camp.json["id"])
        nomes = [b["name"] for b in Client().get(f"/v1/public/campaigns/{slug}").json["backers"]]
        self.assertNotIn(nome_civil, nomes, "nome civil exposto sem opt-in")
        self.assertIn("Apoiador pessoa física", nomes)
        with db_system() as c:
            c.run("INSERT INTO funder_profiles(org_id, public_name) VALUES ($1, true)"
                  " ON CONFLICT (org_id) DO UPDATE SET public_name = true", pessoa.org_id)
        nomes = [b["name"] for b in Client().get(f"/v1/public/campaigns/{slug}").json["backers"]]
        self.assertIn(nome_civil, nomes, "com opt-in, o nome aparece")


if __name__ == "__main__":
    unittest.main()
