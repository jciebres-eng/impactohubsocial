"""PROVA DESCARTÁVEL (fora do repositório) do achado FILE-07: financiador em diligência lê documentos privados da OSC
sem projeto — inclusive a exportação de dados gerada pela plataforma — e continua lendo depois de a candidatura ser encerrada?"""
import sys, unittest
sys.path.insert(0, "/home/claude/impactohubsocial/backend")
from tests.support import Client, grant_premium, new_account, server

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


class Probe(unittest.TestCase):
    def test_funder_reads_private_org_documents(self):
        server()
        osc, funder = new_account("osc"), new_account("company")
        grant_premium(osc)
        pid = osc.post("/v1/projects", {"title": "Projeto sonda", "summary": "Resumo", "territory": "BR-MT-5105259",
                                        "causes": ["educacao"], "beneficiaries_count": 3, "budget_total_cents": 100000}).json["id"]
        self.assertEqual(osc.post(f"/v1/projects/{pid}/publish").status, 200)
        priv = osc.upload("/v1/documents", "interno.pdf", PDF, {"doc_type": "outro", "title": "Documento interno privado"})
        self.assertEqual(priv.status, 201, priv)
        exp = osc.post("/v1/integrations/exports", {"dataset": "projects", "format": "csv"})
        print("\nexport:", exp.status, (exp.json or {}).get("document_id"))
        app = funder.post("/v1/applications/interest", {"project_id": pid}).json["id"]
        antes = funder.post(f"/v1/documents/{priv.json['id']}/download-url").status
        self.assertEqual(osc.post(f"/v1/applications/{app}/transition", {"to_status": "due_diligence"}).status, 200)
        r1 = funder.post(f"/v1/documents/{priv.json['id']}/download-url")
        print("doc privado sem projeto: antes da diligência", antes, "· em diligência", r1.status)
        if exp.status == 201:
            r2 = funder.post(f"/v1/documents/{exp.json['document_id']}/download-url")
            print("exportação de dados da OSC em diligência:", r2.status)
            if r2.status == 200:
                print("  conteúdo baixado (bytes):", len(Client().get(r2.json["url"]).body))
        det = funder.get(f"/v1/applications/{app}").json
        print("documentos listados ao financiador na candidatura:", sorted(d["doc_type"] for d in det.get("documents", [])))
        self.assertEqual(osc.post(f"/v1/applications/{app}/transition", {"to_status": "declined"}).status in (200, 409, 422), True)
        lst = funder.get("/v1/documents").json
        print("lista de documentos visível ao financiador:", sorted({d.get("doc_type") for d in lst.get("items", [])}))


if __name__ == "__main__":
    unittest.main(verbosity=2)
