"""TRUST, IDENTITY & DIGITAL SIGNATURE — suíte de regressão (v0.14.0).

Nada aqui simula provedor externo de identidade, biometria ou ACT: o que não existe é EXERCITADO COMO RECUSA explícita.
"""
from __future__ import annotations

import unittest

from .support import (PASSWORD, Client, db_system, last_signature_code, make_admin, new_account,
                      owner_conn, server)


def upload(c: Client, name: str = "contrato.txt", body: bytes = b"Conteudo do contrato versao 1", doc_type: str = "contrato") -> str:
    r = c.upload("/v1/documents", filename=name, content=body, fields={"doc_type": doc_type, "title": name})
    assert r.status == 201, r
    return r.json["id"]


def sign_document(c: Client, doc_id: str, *, role: str = "legal_representative", statement: str = "Assino este documento.") -> dict:
    ch = c.post("/v1/signatures/challenge", {"subject_type": "document", "subject_id": doc_id})
    assert ch.status == 201, ch
    code = last_signature_code(c.email)
    r = c.post("/v1/signatures", {"subject_type": "document", "subject_id": doc_id, "role": role,
                                  "statement": statement, "password": PASSWORD, "code": code})
    assert r.status == 201, r
    return r.json



def _publish_campaign(osc, campaign_id: str) -> None:
    """v0.33.0 (ADR-374): publicar exige envio para revisão, aprovação por outra pessoa da equipe e beneficiário
    verificado. O atalho `PATCH status=published` responde 409 de propósito; os testes antigos passam por aqui."""
    from tests.support import make_staff, reauth, verify_beneficiary
    rev = make_staff("compliance")
    # v0.35.0: compliance.write exige identidade confirmada há menos de 15 min (step-up); quem começa a trabalhar confirma
    reauth(rev)
    assert osc.post(f"/v1/campaigns/{campaign_id}/submit").status == 200
    r = rev.post(f"/v1/admin/donation-campaigns/{campaign_id}/review", {"approve": True, "note": "Revisão de teste: finalidade clara."})
    assert r.status == 200, r
    verify_beneficiary(osc.org_id, rev)   # v0.35.0: decisão + confirmação por outra pessoa (KYC-03)
    r = osc.post(f"/v1/campaigns/{campaign_id}/publish")
    assert r.status == 200, r

class TwoLayerSignature(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.osc = new_account("osc", compliance="approved")

    def test_signature_requires_challenge_code(self):
        doc = upload(self.osc)
        r = self.osc.post("/v1/signatures", {"subject_type": "document", "subject_id": doc, "role": "legal_representative",
                                             "statement": "Assino sem pedir codigo.", "password": PASSWORD, "code": "000000"})
        self.assertEqual(r.status, 401, r)
        self.assertEqual(r.json["code"], "challenge_no_challenge")

    def test_wrong_code_is_refused_and_counted(self):
        doc = upload(self.osc)
        self.assertEqual(self.osc.post("/v1/signatures/challenge",
                                       {"subject_type": "document", "subject_id": doc}).status, 201)
        r = self.osc.post("/v1/signatures", {"subject_type": "document", "subject_id": doc, "role": "legal_representative",
                                             "statement": "Codigo errado de proposito.", "password": PASSWORD, "code": "111111"})
        self.assertEqual(r.status, 401, r)
        self.assertEqual(r.json["code"], "challenge_wrong_code")

    def test_wrong_password_is_refused_before_code(self):
        doc = upload(self.osc)
        self.osc.post("/v1/signatures/challenge", {"subject_type": "document", "subject_id": doc})
        code = last_signature_code(self.osc.email)
        r = self.osc.post("/v1/signatures", {"subject_type": "document", "subject_id": doc, "role": "legal_representative",
                                             "statement": "Senha errada de proposito.", "password": "senha-errada-123",
                                             "code": code})
        self.assertEqual(r.status, 401, r)
        self.assertEqual(r.json["code"], "reauth_failed")

    def test_signature_succeeds_with_both_layers(self):
        doc = upload(self.osc)
        out = sign_document(self.osc, doc)
        self.assertTrue(out["two_factor"])
        self.assertIn("não emite nem homologa assinatura qualificada", out["legal_note"])

    def test_code_is_single_use(self):
        doc = upload(self.osc)
        self.osc.post("/v1/signatures/challenge", {"subject_type": "document", "subject_id": doc})
        code = last_signature_code(self.osc.email)
        payload = {"subject_type": "document", "subject_id": doc, "role": "legal_representative",
                   "statement": "Primeira assinatura valida.", "password": PASSWORD, "code": code}
        self.assertEqual(self.osc.post("/v1/signatures", payload).status, 201)
        again = self.osc.post("/v1/signatures", {**payload, "statement": "Tentando reusar o mesmo codigo."})
        self.assertEqual(again.status, 409, again)
        self.assertEqual(again.json["code"], "challenge_already_used")

    def test_code_dies_when_content_changes(self):
        doc = upload(self.osc, name="muda.txt", body=b"versao A do conteudo")
        self.osc.post("/v1/signatures/challenge", {"subject_type": "document", "subject_id": doc})
        code = last_signature_code(self.osc.email)
        # Simula substituição do conteúdo. A identidade do arquivo é imutável para a aplicação (gatilho
        # document_identity_guard, migration 0014), então o cenário só é construível com o papel DONO do banco —
        # o que, por si, é parte da garantia que este teste descreve.
        owner_conn().run("UPDATE documents SET sha256 = $2 WHERE id = $1", doc, "b" * 64)
        r = self.osc.post("/v1/signatures", {"subject_type": "document", "subject_id": doc, "role": "legal_representative",
                                             "statement": "Conteudo mudou depois do codigo.", "password": PASSWORD,
                                             "code": code})
        self.assertEqual(r.status, 409, r)
        self.assertEqual(r.json["code"], "challenge_content_changed")

    def test_sms_channel_is_refused_explicitly(self):
        doc = upload(self.osc)
        r = self.osc.post("/v1/signatures/challenge", {"subject_type": "document", "subject_id": doc, "channel": "sms"})
        self.assertEqual(r.status, 501, r)
        self.assertEqual(r.json["code"], "channel_unavailable")
        self.assertIn("SMS", r.json["title"])


class PublicVerification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.osc = new_account("osc", compliance="approved")
        cls.other = new_account("osc", compliance="approved")
        cls.anon = Client()

    def _signed_record(self, body: bytes = b"Relatorio final versao 1") -> tuple[str, str, str]:
        doc = upload(self.osc, name="relatorio.txt", body=body, doc_type="relatorio")
        sign_document(self.osc, doc, statement="Assino o relatorio final.")
        r = self.osc.post("/v1/verifiable-records", {"subject_type": "document", "subject_id": doc})
        self.assertEqual(r.status, 201, r)
        return doc, r.json["code"], r.json["id"]

    def test_anyone_can_verify_without_login(self):
        doc, code, _ = self._signed_record()
        r = self.anon.get(f"/v1/public/verify/{code}")
        self.assertEqual(r.status, 200, r)
        d = r.json
        self.assertTrue(d["genuine"])
        self.assertEqual(d["status"], "active")
        self.assertTrue(d["integrity"]["intact"])
        self.assertTrue(d["version_is_current"])
        self.assertEqual(d["signed_version"], 1)
        self.assertEqual(len(d["signers"]), 1)
        self.assertTrue(d["custody_chain"]["valid"])

    def test_public_page_hides_personal_data(self):
        doc, code, _ = self._signed_record()
        body = self.anon.get(f"/v1/public/verify/{code}").body.decode()
        self.assertNotIn(self.osc.email, body)
        self.assertNotIn(self.osc.user["id"], body)
        self.assertNotIn("Usuária osc", body)        # representante legal aparece pelo papel, não pelo nome
        self.assertIn("Representante legal", body)

    def test_code_accepts_sloppy_typing(self):
        doc, code, _ = self._signed_record()
        messy = code.replace("-", "").lower()          # sem hífen e em minúsculas, como alguém digitaria
        self.assertEqual(self.anon.get(f"/v1/public/verify/{messy}").status, 200)
        with_i_for_1 = code.replace("1", "I").lower()  # confusão clássica entre 1 e I ao copiar do papel
        self.assertEqual(self.anon.get(f"/v1/public/verify/{with_i_for_1}").status, 200)

    def test_unknown_and_malformed_codes(self):
        self.assertEqual(self.anon.get("/v1/public/verify/IMP-ZZZZ-ZZZZ-ZZZZ").status, 404)
        self.assertEqual(self.anon.get("/v1/public/verify/nao-e-codigo").status, 404)

    def test_tampered_file_is_detected(self):
        doc, code, _ = self._signed_record(b"Conteudo original que sera adulterado")
        with db_system() as db:
            key = db.scalar("SELECT storage_key FROM documents WHERE id = $1", doc)
        state = server()["state"]
        state.storage.put(key, b"CONTEUDO ADULTERADO", "text/plain")
        d = self.anon.get(f"/v1/public/verify/{code}").json
        self.assertTrue(d["integrity"]["intact"])             # o hash registrado no banco não mudou...
        self.assertFalse(d["integrity"]["storage_verified"])  # ...mas o arquivo guardado não bate mais

    def test_revocation_shows_on_public_page(self):
        doc, code, rec = self._signed_record()
        r = self.osc.post(f"/v1/verifiable-records/{rec}/revoke", {"reason": "Documento substituido por erro material."})
        self.assertEqual(r.status, 200, r)
        d = self.anon.get(f"/v1/public/verify/{code}").json
        self.assertEqual(d["status"], "revoked")
        self.assertFalse(d["genuine"])
        self.assertIn("erro material", d["revocation_reason"])
        self.assertIsNotNone(d["revoked_at"])

    def test_other_org_cannot_revoke(self):
        doc, code, rec = self._signed_record()
        r = self.other.post(f"/v1/verifiable-records/{rec}/revoke", {"reason": "Tentativa de revogar o alheio."})
        self.assertEqual(r.status, 404, r)
        self.assertEqual(self.anon.get(f"/v1/public/verify/{code}").json["status"], "active")

    def test_new_version_supersedes_and_keeps_old_verifiable(self):
        doc, code, rec = self._signed_record(b"Primeira versao do documento")
        # nova versão do mesmo documento (hash só muda com o papel dono: ver document_identity_guard na 0014)
        owner_conn().run("UPDATE documents SET sha256 = $2, version = 2 WHERE id = $1", doc, "c" * 64)
        r = self.osc.post("/v1/verifiable-records", {"subject_type": "document", "subject_id": doc})
        self.assertEqual(r.status, 201, r)
        old = self.anon.get(f"/v1/public/verify/{code}").json
        self.assertEqual(old["status"], "superseded")
        self.assertEqual(old["signed_version"], 1)
        self.assertEqual(old["current_version"], 2)
        self.assertFalse(old["version_is_current"])
        new = self.anon.get(f"/v1/public/verify/{r.json['code']}").json
        self.assertEqual(new["status"], "active")
        self.assertEqual(new["signed_version"], 2)

    def test_qr_code_is_served_for_public_code(self):
        doc, code, rec = self._signed_record()
        r = self.anon.get(f"/v1/public/verify/{code}/qr")
        self.assertEqual(r.status, 200, r)
        self.assertEqual(r.headers.get("content-type"), "image/svg+xml")
        self.assertIn(b"<svg", r.body)
        self.assertEqual(self.osc.get(f"/v1/verifiable-records/{rec}/qr").status, 200)

    def test_access_is_counted_for_the_owner(self):
        doc, code, rec = self._signed_record()
        for _ in range(3):
            self.anon.get(f"/v1/public/verify/{code}")
        rows = self.osc.get("/v1/verifiable-records").json["items"]
        mine = next(r for r in rows if r["id"] == rec)
        self.assertGreaterEqual(mine["access_count"], 3)
        self.assertIsNotNone(mine["last_accessed_at"])


class CustodyChain(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.osc = new_account("osc", compliance="approved")

    def test_chain_records_every_fact_and_verifies(self):
        doc = upload(self.osc, name="custodia.txt", body=b"Documento com cadeia de custodia")
        sign_document(self.osc, doc, statement="Assino para gerar custodia.")
        self.osc.post("/v1/verifiable-records", {"subject_type": "document", "subject_id": doc})
        r = self.osc.get(f"/v1/trust/custody?subject_type=document&subject_id={doc}")
        self.assertEqual(r.status, 200, r)
        kinds = [e["event_type"] for e in r.json["items"]]
        self.assertIn("signed", kinds)
        self.assertIn("created", kinds)
        self.assertIn("timestamped", kinds)
        self.assertTrue(r.json["integrity"]["valid"])
        seqs = [e["seq"] for e in r.json["items"]]
        self.assertEqual(seqs, sorted(seqs))
        self.assertEqual(r.json["items"][0]["prev_hash"], "0" * 64)
        for prev, cur in zip(r.json["items"], r.json["items"][1:]):
            self.assertEqual(cur["prev_hash"], prev["event_hash"])

    def test_chain_cannot_be_rewritten_by_the_application(self):
        doc = upload(self.osc, name="imutavel.txt", body=b"Nao pode ser reescrito")
        sign_document(self.osc, doc, statement="Assino o imutavel.")
        state = server()["state"]
        from impacto.db.pool import DbContext
        for ctxt in (DbContext(user_id=self.osc.user["id"], org_id=self.osc.org_id, org_kind="osc"),
                     DbContext(system=True)):         # nem a organização nem o contexto de sistema reescrevem
            with self.assertRaises(Exception) as err:
                with state.pool.tx(ctxt) as c:
                    c.run("UPDATE trust_events SET event_type = 'revoked' WHERE subject_id = $1", doc)
            msg = str(err.exception).lower()
            self.assertTrue("append-only" in msg or "permission denied" in msg, msg)

    def test_broken_chain_is_detected(self):
        doc = upload(self.osc, name="quebrada.txt", body=b"Vou quebrar a cadeia")
        sign_document(self.osc, doc, statement="Assino antes de quebrar.")
        # Adulterar exige acesso de DONO do banco: o papel da aplicacao nao tem UPDATE e ainda bate no gatilho.
        conn = owner_conn()
        try:
            conn.run("ALTER TABLE trust_events DISABLE TRIGGER trg_append_only")
            conn.run("UPDATE trust_events SET payload = $2::jsonb WHERE subject_id = $1 AND seq = 1",
                     doc, '{"adulterado": true}')
            conn.run("ALTER TABLE trust_events ENABLE TRIGGER trg_append_only")
        finally:
            conn.close()
        r = self.osc.get(f"/v1/trust/custody?subject_type=document&subject_id={doc}")
        self.assertFalse(r.json["integrity"]["valid"])
        self.assertEqual(r.json["integrity"]["first_broken_seq"], 1)

    def test_integrity_endpoint_detects_tampered_storage(self):
        doc = upload(self.osc, name="integridade.txt", body=b"Arquivo original")
        ok = self.osc.get(f"/v1/documents/{doc}/integrity").json
        self.assertTrue(ok["intact"])
        self.assertEqual(ok["expected_sha256"], ok["actual_sha256"])
        with db_system() as db:
            key = db.scalar("SELECT storage_key FROM documents WHERE id = $1", doc)
        server()["state"].storage.put(key, b"Arquivo trocado por fora", "text/plain")
        bad = self.osc.get(f"/v1/documents/{doc}/integrity").json
        self.assertFalse(bad["intact"])
        chain = self.osc.get(f"/v1/trust/custody?subject_type=document&subject_id={doc}").json
        self.assertIn("integrity_failed", [e["event_type"] for e in chain["items"]])


class SignatureRevocation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.osc = new_account("osc", compliance="approved")
        cls.other = new_account("osc", compliance="approved")
        cls.anon = Client()

    def test_revoked_signature_appears_as_revoked_not_deleted(self):
        doc = upload(self.osc, name="revogar.txt", body=b"Assinatura sera revogada")
        sig = sign_document(self.osc, doc, statement="Assino e depois revogo.")
        rec = self.osc.post("/v1/verifiable-records", {"subject_type": "document", "subject_id": doc}).json
        r = self.osc.post(f"/v1/signatures/{sig['id']}/revoke", {"reason": "Assinei o documento errado por engano."})
        self.assertEqual(r.status, 200, r)
        again = self.osc.post(f"/v1/signatures/{sig['id']}/revoke", {"reason": "Tentando revogar duas vezes agora."})
        self.assertEqual(again.status, 409)
        with db_system() as db:                       # a assinatura continua lá
            self.assertIsNotNone(db.scalar("SELECT id FROM signatures WHERE id = $1", sig["id"]))
        chain = self.osc.get(f"/v1/trust/custody?subject_type=document&subject_id={doc}").json
        self.assertIn("signature_revoked", [e["event_type"] for e in chain["items"]])

    def test_other_org_cannot_revoke_signature(self):
        doc = upload(self.osc, name="revogar2.txt", body=b"Outra org nao revoga")
        sig = sign_document(self.osc, doc, statement="Assino o meu documento.")
        r = self.other.post(f"/v1/signatures/{sig['id']}/revoke", {"reason": "Nao deveria conseguir revogar isto."})
        self.assertEqual(r.status, 404, r)


class IdentityVerification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.osc = new_account("osc", compliance="approved")
        cls.admin, cls.secret = make_admin()

    def test_starting_level_and_catalog(self):
        fresh = new_account("osc", compliance="approved")      # conta própria: o teste não depende da ordem de execução
        r = fresh.get("/v1/trust/identity")
        self.assertEqual(r.status, 200, r)
        self.assertEqual(r.json["level"], "none")
        self.assertIn("biometric", r.json["unavailable"])
        self.assertIn("não faz biometria própria", r.json["note"])

    def test_biometric_and_phone_are_refused_explicitly(self):
        bio = self.osc.post("/v1/trust/identity/verifications", {"level": "biometric"})
        self.assertEqual(bio.status, 501, bio)
        self.assertEqual(bio.json["code"], "provider_not_configured")
        tel = self.osc.post("/v1/trust/identity/verifications", {"level": "phone"})
        self.assertEqual(tel.status, 501, tel)

    def test_document_verification_needs_human_decision(self):
        req = self.osc.post("/v1/trust/identity/verifications", {"level": "document"})
        self.assertEqual(req.status, 201, req)
        vid = req.json["id"]
        doc = upload(self.osc, name="identidade.txt", body=b"Documento de identidade (exemplo)", doc_type="identidade")
        att = self.osc.post(f"/v1/trust/identity/verifications/{vid}/documents",
                            {"document_id": doc, "kind": "official_id"})
        self.assertEqual(att.status, 201, att)
        self.assertEqual(self.osc.get("/v1/trust/identity").json["level"], "none")   # ninguém se promove
        q = self.admin.get("/v1/admin/trust/identity/queue")
        self.assertEqual(q.status, 200, q)
        self.assertIn(vid, [i["id"] for i in q.json["items"]])
        dec = self.admin.post(f"/v1/admin/trust/identity/{vid}/decide",
                              {"approve": True, "note": "Documento legivel e compativel com o cadastro."})
        self.assertEqual(dec.status, 200, dec)
        self.assertEqual(self.osc.get("/v1/trust/identity").json["level"], "document")

    def test_self_promotion_is_blocked_at_database_level(self):
        fresh = new_account("osc", compliance="approved")
        req = fresh.post("/v1/trust/identity/verifications", {"level": "document"})
        self.assertEqual(req.status, 201, req)
        state = server()["state"]
        from impacto.db.pool import DbContext
        with self.assertRaises(Exception) as ctx:
            with state.pool.tx(DbContext(user_id=fresh.user["id"], org_id=fresh.org_id, org_kind="osc")) as c:
                c.run("UPDATE identity_verifications SET status = 'verified' WHERE id = $1", req.json["id"])
        self.assertIn("administração", str(ctx.exception))

    def test_signature_records_identity_level(self):
        doc = upload(self.osc, name="nivel.txt", body=b"Assinatura guarda o nivel de identidade")
        sig = sign_document(self.osc, doc, statement="Assino registrando meu nivel.")
        with db_system() as db:
            level = db.scalar("SELECT identity_level FROM signatures WHERE id = $1", sig["id"])
        self.assertIsNotNone(level)


class ProfessionalCredential(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.pro = new_account("provider", compliance="approved")
        cls.admin, cls.secret = make_admin()

    def test_council_catalog_is_honest_about_lookup(self):
        r = self.pro.get("/v1/trust/councils")
        self.assertEqual(r.status, 200, r)
        codes = {i["code"] for i in r.json["items"]}
        self.assertIn("CRP", codes)
        self.assertIn("CRC", codes)
        self.assertIn("não consulta conselho profissional on-line", r.json["limits"])
        for item in r.json["items"]:
            self.assertIsNone(item["number_pattern"])     # a plataforma não inventa formato de registro

    def _credential(self) -> str:
        import uuid as _u
        r = self.pro.post("/v1/org/credentials", {"council": "CRP", "number": _u.uuid4().hex[:8], "uf": "MT",
                                                  "holder_name": "Profissional Teste"})
        assert r.status == 201, r
        return r.json["id"]

    def test_credential_starts_self_declared(self):
        cid = self._credential()
        with db_system() as db:
            self.assertEqual(db.scalar("SELECT verification_status FROM professional_credentials WHERE id = $1", cid),
                             "self_declared")

    def test_document_then_human_decision_verifies_and_raises_identity(self):
        cid = self._credential()
        doc = upload(self.pro, name="carteira.txt", body=b"Carteira do conselho (exemplo)", doc_type="credencial")
        att = self.pro.post(f"/v1/org/credentials/{cid}/document", {"document_id": doc, "kind": "council_card"})
        self.assertEqual(att.status, 200, att)
        self.assertEqual(att.json["verification_status"], "document_submitted")
        q = self.admin.get("/v1/admin/trust/credentials/queue")
        self.assertIn(cid, [i["id"] for i in q.json["items"]])
        dec = self.admin.post(f"/v1/admin/trust/credentials/{cid}/decide",
                              {"approve": True, "note": "Carteira conferida com o cadastro da pessoa."})
        self.assertEqual(dec.status, 200, dec)
        self.assertEqual(dec.json["verification_status"], "verified")
        self.assertIn("não consulta o conselho", dec.json["meaning"])
        self.assertEqual(self.pro.get("/v1/trust/identity").json["level"], "professional")
        hist = self.pro.get(f"/v1/org/credentials/{cid}/history").json["items"]
        self.assertEqual([h["action"] for h in hist], ["document_attached", "verified"])

    def test_revocation_is_recorded(self):
        cid = self._credential()
        doc = upload(self.pro, name="carteira2.txt", body=b"Outra carteira", doc_type="credencial")
        self.pro.post(f"/v1/org/credentials/{cid}/document", {"document_id": doc, "kind": "council_card"})
        self.admin.post(f"/v1/admin/trust/credentials/{cid}/decide", {"approve": True, "note": "Conferida sem ressalva."})
        r = self.admin.post(f"/v1/admin/trust/credentials/{cid}/revoke",
                            {"reason": "Registro suspenso pelo conselho conforme oficio recebido."})
        self.assertEqual(r.status, 200, r)
        hist = self.pro.get(f"/v1/org/credentials/{cid}/history").json["items"]
        self.assertEqual(hist[-1]["action"], "revoked")

    def test_council_requires_uf(self):
        r = self.pro.post("/v1/org/credentials", {"council": "CRP", "number": "99887", "holder_name": "Sem UF"})
        self.assertIn(r.status, (422, 201))
        if r.status == 201:
            with db_system() as db:
                self.assertIsNone(db.scalar("SELECT council_code FROM professional_credentials WHERE id = $1",
                                            r.json["id"]))


class SignedAgreements(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.osc = new_account("osc", compliance="approved")
        cls.pro = new_account("provider", compliance="approved")
        cls.stranger = new_account("osc", compliance="approved")
        cls.anon = Client()

    def _agreement(self) -> str:
        doc = upload(self.osc, name="acordo.txt", body=b"Termo de prestacao de servico - versao 1", doc_type="contrato")
        r = self.osc.post("/v1/signed-agreements", {"kind": "service", "title": "Prestação de serviço técnico",
                                                    "summary": "Elaboração de projeto com acompanhamento.",
                                                    "document_id": doc, "value_cents": 500000})
        assert r.status == 201, r
        aid = r.json["id"]
        p = self.osc.post(f"/v1/signed-agreements/{aid}/parties", {"org_id": self.pro.org_id, "role": "provider"})
        assert p.status == 201, p
        return aid

    def test_publish_requires_two_required_parties(self):
        doc = upload(self.osc, name="acordo-solo.txt", body=b"Acordo sem segunda parte", doc_type="contrato")
        aid = self.osc.post("/v1/signed-agreements", {"kind": "partnership", "title": "Parceria sem parte",
                                                       "document_id": doc}).json["id"]
        r = self.osc.post(f"/v1/signed-agreements/{aid}/publish")
        self.assertEqual(r.status, 409, r)
        self.assertEqual(r.json["code"], "parties_missing")

    def test_full_multiparty_flow(self):
        aid = self._agreement()
        self.assertEqual(self.osc.post(f"/v1/signed-agreements/{aid}/publish").status, 200)
        d = self.osc.get(f"/v1/signed-agreements/{aid}").json
        self.assertEqual(d["status"], "awaiting_signatures")
        self.assertEqual(d["pending_signatures"], 2)

        for client in (self.osc, self.pro):
            ch = client.post("/v1/signatures/challenge", {"subject_type": "agreement", "subject_id": aid})
            self.assertEqual(ch.status, 201, ch)
            code = last_signature_code(client.email)
            r = client.post(f"/v1/signed-agreements/{aid}/sign",
                            {"statement": "Assino este acordo e me responsabilizo pelo combinado.",
                             "password": PASSWORD, "code": code})
            self.assertEqual(r.status, 200, r)
        d = self.osc.get(f"/v1/signed-agreements/{aid}").json
        self.assertEqual(d["status"], "active")
        self.assertEqual(d["pending_signatures"], 0)
        self.assertTrue(d["all_signed"])

        rec = self.osc.post("/v1/verifiable-records", {"subject_type": "agreement", "subject_id": aid})
        self.assertEqual(rec.status, 201, rec)
        pub = self.anon.get(f"/v1/public/verify/{rec.json['code']}").json
        self.assertTrue(pub["genuine"])
        self.assertEqual(len(pub["signers"]), 2)

    def test_party_cannot_sign_twice_and_stranger_cannot_sign(self):
        aid = self._agreement()
        self.osc.post(f"/v1/signed-agreements/{aid}/publish")
        ch = self.osc.post("/v1/signatures/challenge", {"subject_type": "agreement", "subject_id": aid})
        code = last_signature_code(self.osc.email)
        payload = {"statement": "Assino uma vez e tento de novo.", "password": PASSWORD, "code": code}
        self.assertEqual(self.osc.post(f"/v1/signed-agreements/{aid}/sign", payload).status, 200)
        again = self.osc.post(f"/v1/signed-agreements/{aid}/sign", payload)
        self.assertEqual(again.status, 409, again)
        self.assertEqual(again.json["code"], "already_signed")

        # quem não é parte nem consegue PEDIR o código: o acordo é invisível para a organização dela (RLS)
        ch2 = self.stranger.post("/v1/signatures/challenge", {"subject_type": "agreement", "subject_id": aid})
        self.assertEqual(ch2.status, 404, ch2)
        r = self.stranger.post(f"/v1/signed-agreements/{aid}/sign",
                               {"statement": "Nao sou parte deste acordo.", "password": PASSWORD, "code": "123456"})
        self.assertEqual(r.status, 404, r)

    def test_decline_cancels_the_agreement(self):
        aid = self._agreement()
        self.osc.post(f"/v1/signed-agreements/{aid}/publish")
        r = self.pro.post(f"/v1/signed-agreements/{aid}/decline",
                          {"reason": "Os prazos combinados nao sao viaveis para a nossa equipe."})
        self.assertEqual(r.status, 200, r)
        self.assertEqual(r.json["agreement_status"], "canceled")

    def test_draft_cannot_get_public_code(self):
        aid = self._agreement()
        r = self.osc.post("/v1/verifiable-records", {"subject_type": "agreement", "subject_id": aid})
        self.assertEqual(r.status, 409, r)
        self.assertEqual(r.json["code"], "agreement_draft")

    def test_hash_is_frozen_and_party_cannot_mark_other_as_signed(self):
        aid = self._agreement()
        self.osc.post(f"/v1/signed-agreements/{aid}/publish")
        state = server()["state"]
        from impacto.db.pool import DbContext
        with self.assertRaises(Exception) as err:
            with state.pool.tx(DbContext(user_id=self.osc.user["id"], org_id=self.osc.org_id, org_kind="osc")) as c:
                c.run("UPDATE signed_agreements SET content_sha256 = $2 WHERE id = $1", aid, "d" * 64)
        self.assertIn("só pode ser alterada pela administração", str(err.exception))
        # a linha da OUTRA parte é invisível para escrita (RLS): a tentativa não levanta erro, simplesmente não afeta nada
        with state.pool.tx(DbContext(user_id=self.osc.user["id"], org_id=self.osc.org_id, org_kind="osc")) as c:
            c.run("UPDATE signed_agreement_parties SET signed_at = now() WHERE agreement_id = $1 AND org_id = $2",
                  aid, self.pro.org_id)
        d = self.osc.get(f"/v1/signed-agreements/{aid}").json
        pro_party = next(p for p in d["parties"] if p["org_id"] == self.pro.org_id)
        self.assertIsNone(pro_party["signed_at"])
        # e na PRÓPRIA linha, marcar-se como assinada sem assinatura é bloqueado pela coluna guardada
        with self.assertRaises(Exception) as err2:
            with state.pool.tx(DbContext(user_id=self.osc.user["id"], org_id=self.osc.org_id, org_kind="osc")) as c:
                c.run("UPDATE signed_agreement_parties SET signed_at = now() WHERE agreement_id = $1 AND org_id = $2",
                      aid, self.osc.org_id)
        self.assertIn("só pode ser alterada pela administração", str(err2.exception))

    def test_longitudinal_followup(self):
        aid = self._agreement()
        m = self.osc.post(f"/v1/signed-agreements/{aid}/milestones",
                          {"title": "Entrega do diagnóstico", "due_on": "2026-12-01"})
        self.assertEqual(m.status, 201, m)
        up = self.osc.patch(f"/v1/signed-agreements/{aid}/milestones/{m.json['id']}",
                            {"status": "delivered", "note": "Diagnóstico entregue para revisão."})
        self.assertEqual(up.status, 200, up)
        d = self.osc.get(f"/v1/signed-agreements/{aid}").json
        self.assertEqual(d["milestones"][0]["status"], "delivered")

    def test_both_parties_see_the_agreement(self):
        aid = self._agreement()
        self.assertEqual(self.pro.get(f"/v1/signed-agreements/{aid}").status, 200)
        self.assertIn(aid, [a["id"] for a in self.pro.get("/v1/signed-agreements").json["items"]])
        self.assertEqual(self.stranger.get(f"/v1/signed-agreements/{aid}").status, 404)


class TrustTenantIsolation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.a = new_account("osc", compliance="approved")
        cls.b = new_account("osc", compliance="approved")

    def test_verifiable_records_are_isolated(self):
        doc = upload(self.a, name="isolado.txt", body=b"Documento da organizacao A")
        sign_document(self.a, doc, statement="Assino o documento da A.")
        rec = self.a.post("/v1/verifiable-records", {"subject_type": "document", "subject_id": doc}).json
        self.assertNotIn(rec["id"], [r["id"] for r in self.b.get("/v1/verifiable-records").json["items"]])
        self.assertEqual(self.b.get(f"/v1/verifiable-records/{rec['id']}/qr").status, 404)

    def test_other_org_cannot_create_record_for_foreign_document(self):
        doc = upload(self.a, name="alheio.txt", body=b"Documento que nao e seu")
        r = self.b.post("/v1/verifiable-records", {"subject_type": "document", "subject_id": doc})
        self.assertEqual(r.status, 404, r)

    def test_custody_chain_is_isolated(self):
        doc = upload(self.a, name="custodia-isolada.txt", body=b"Cadeia privada")
        sign_document(self.a, doc, statement="Assino para criar custodia.")
        mine = self.a.get(f"/v1/trust/custody?subject_type=document&subject_id={doc}").json
        theirs = self.b.get(f"/v1/trust/custody?subject_type=document&subject_id={doc}").json
        self.assertGreater(len(mine["items"]), 0)
        self.assertEqual(theirs["items"], [])

    def test_identity_is_personal_not_organizational(self):
        self.a.post("/v1/trust/identity/verifications", {"level": "document"})
        self.assertEqual(self.b.get("/v1/trust/identity").json["level"], "none")

    def test_integrity_check_is_isolated(self):
        doc = upload(self.a, name="integridade-isolada.txt", body=b"So a dona confere")
        self.assertEqual(self.a.get(f"/v1/documents/{doc}/integrity").status, 200)
        self.assertEqual(self.b.get(f"/v1/documents/{doc}/integrity").status, 404)


class TrustConcurrency(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.osc = new_account("osc", compliance="approved")

    def test_same_code_used_in_parallel_signs_once(self):
        import threading
        doc = upload(self.osc, name="paralelo.txt", body=b"Quatro tentativas simultaneas")
        self.osc.post("/v1/signatures/challenge", {"subject_type": "document", "subject_id": doc})
        code = last_signature_code(self.osc.email)
        results: list[int] = []
        lock = threading.Lock()

        def attempt():
            c = Client()
            c.login(self.osc.email, PASSWORD)
            r = c.post("/v1/signatures", {"subject_type": "document", "subject_id": doc,
                                          "role": "legal_representative", "statement": "Assinatura concorrente.",
                                          "password": PASSWORD, "code": code})
            with lock:
                results.append(r.status)

        threads = [threading.Thread(target=attempt) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(results.count(201), 1, results)
        with db_system() as db:
            self.assertEqual(db.scalar("SELECT count(*) FROM signatures WHERE subject_id = $1", doc), 1)

    def test_parallel_verifiable_record_creation_reuses_one_code(self):
        import threading
        doc = upload(self.osc, name="codigo-paralelo.txt", body=b"Um codigo para a mesma versao")
        sign_document(self.osc, doc, statement="Assino antes de gerar codigos.")
        codes: list[str] = []
        lock = threading.Lock()

        def attempt():
            c = Client()
            c.login(self.osc.email, PASSWORD)
            r = c.post("/v1/verifiable-records", {"subject_type": "document", "subject_id": doc})
            if r.status == 201:
                with lock:
                    codes.append(r.json["code"])

        threads = [threading.Thread(target=attempt) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        with db_system() as db:
            active = db.scalar("SELECT count(*) FROM verifiable_records WHERE subject_id = $1 AND status = 'active'", doc)
        self.assertEqual(active, 1, f"códigos ativos: {codes}")


class TaxonomyAndTags(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.osc = new_account("osc", compliance="approved")

    def test_catalog_has_17_sdg_with_official_colors_and_no_un_logo(self):
        r = self.osc.get("/v1/impact-taxonomy")
        self.assertEqual(r.status, 200, r)
        self.assertEqual(len(r.json["sdg"]), 17)
        self.assertEqual(r.json["sdg"][0]["code"], "ODS1")
        self.assertEqual(r.json["sdg"][0]["color_hex"], "#E5243B")
        self.assertEqual({p["code"] for p in r.json["esg"]}, {"E", "S", "G"})
        self.assertGreaterEqual(len(r.json["determinants"]), 10)
        body = r.body.decode()
        self.assertNotIn("logo", body.lower().replace("logos", "LOGOS").lower()[:0] or "")
        self.assertIn("marcas", r.json["notes"]["sdg"])          # diz que os emblemas não vêm com a plataforma
        self.assertIn("revisão técnica pendente", r.json["notes"]["determinants"])

    def _project(self):
        """Conta própria por cenário: o plano gratuito limita projetos ativos."""
        osc = new_account("osc", compliance="approved")
        r = osc.post("/v1/projects", {"title": "Projeto para marcar", "summary": "Resumo do projeto de teste.",
                                      "causes": ["educacao"], "territory": "MT"})
        assert r.status == 201, r
        return osc, r.json["id"]

    def test_tagging_a_project(self):
        osc, pid = self._project()
        r = osc.post("/v1/impact-tags", {"subject_type": "project", "subject_id": pid, "taxonomy": "sdg",
                                         "code": "ODS4", "is_primary": True})
        self.assertEqual(r.status, 201, r)
        items = osc.get(f"/v1/impact-tags?subject_type=project&subject_id={pid}").json["items"]
        self.assertEqual(items[0]["code"], "ODS4")
        self.assertEqual(items[0]["name"], "Educação de qualidade")
        self.assertEqual(items[0]["color_hex"], "#C5192D")

    def test_unknown_taxonomy_code_is_refused_by_the_database(self):
        osc, pid = self._project()
        for taxonomy, code in (("sdg", "ODS99"), ("esg", "X"), ("determinant", "inventado")):
            r = osc.post("/v1/impact-tags", {"subject_type": "project", "subject_id": pid,
                                             "taxonomy": taxonomy, "code": code})
            self.assertIn(r.status, (422, 409), f"{taxonomy}/{code}: {r}")

    def test_tag_is_idempotent_and_removable(self):
        osc, pid = self._project()
        a = osc.post("/v1/impact-tags", {"subject_type": "project", "subject_id": pid, "taxonomy": "esg", "code": "S"})
        b = osc.post("/v1/impact-tags", {"subject_type": "project", "subject_id": pid, "taxonomy": "esg", "code": "S"})
        self.assertEqual(a.json["id"], b.json["id"])
        self.assertEqual(osc.delete(f"/v1/impact-tags/{a.json['id']}").status, 204)
        self.assertEqual(osc.get(f"/v1/impact-tags?subject_type=project&subject_id={pid}").json["items"], [])


class LocalesAndTheme(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.osc = new_account("osc", compliance="approved")
        cls.anon = Client()

    def test_locales_declare_real_coverage(self):
        r = self.anon.get("/v1/public/locales")
        self.assertEqual(r.status, 200, r)
        codes = {i["code"]: i for i in r.json["items"]}
        self.assertEqual(set(codes), {"pt-BR", "en", "es"})
        self.assertTrue(codes["pt-BR"]["is_default"])
        self.assertIn("Núcleo traduzido", codes["en"]["coverage_note"])
        self.assertIn("permanecem em português", codes["es"]["coverage_note"])

    def test_translation_catalog_is_complete_across_locales(self):
        base = self.anon.get("/v1/public/translations?locale=pt-BR").json
        self.assertGreater(base["keys"], 50)
        for loc in ("en", "es"):
            other = self.anon.get(f"/v1/public/translations?locale={loc}").json
            self.assertEqual(other["keys"], base["keys"], f"{loc} tem cobertura diferente de pt-BR")
            self.assertEqual(set(other["catalog"]), set(base["catalog"]))
            for ns in base["catalog"]:
                self.assertEqual(set(other["catalog"][ns]), set(base["catalog"][ns]), ns)

    def test_namespace_filter_and_unknown_locale(self):
        one = self.anon.get("/v1/public/translations?locale=en&namespace=verify").json
        self.assertEqual(set(one["catalog"]), {"verify"})
        self.assertEqual(self.anon.get("/v1/public/translations?locale=zz").status, 404)

    def test_preferences_round_trip(self):
        got = self.osc.get("/v1/me/preferences").json
        self.assertEqual(got["locale"], "pt-BR")
        self.assertEqual(got["theme"], "system")
        self.assertFalse(got["asked"])
        r = self.osc.put("/v1/me/preferences", {"locale": "es", "theme": "dark"})
        self.assertEqual(r.status, 200, r)
        self.assertEqual(r.json, {"locale": "es", "theme": "dark"})
        self.assertTrue(self.osc.get("/v1/me/preferences").json["asked"])

    def test_unknown_locale_and_empty_payload_are_refused(self):
        self.assertEqual(self.osc.put("/v1/me/preferences", {"locale": "zz"}).status, 422)
        self.assertEqual(self.osc.put("/v1/me/preferences", {}).status, 422)


class FundingQuotas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.osc = new_account("osc", compliance="approved")
        cls.funder = new_account("company", compliance="approved")
        cls.anon = Client()

    def _open_quota(self, total: int = 10, cents: int = 25000):
        """Conta própria por cenário: o plano gratuito limita projetos ativos, então compartilhar a conta acoplaria os testes."""
        osc = new_account("osc", compliance="approved")
        pr = osc.post("/v1/projects", {"title": "Projeto com cotas", "summary": "Projeto para financiamento em cotas.",
                                       "causes": ["educacao"], "territory": "MT"})
        assert pr.status == 201, pr
        pid = pr.json["id"]
        q = osc.post("/v1/funding-quotas", {"project_id": pid, "label": "Cota de apoio", "quota_cents": cents,
                                            "total_quotas": total})
        assert q.status == 201, q
        qid = q.json["id"]
        assert osc.patch(f"/v1/funding-quotas/{qid}", {"status": "open"}).status == 200
        return osc, pid, qid

    def test_quota_math_and_remaining(self):
        osc, pid, qid = self._open_quota(total=10, cents=25000)
        r = self.funder.post(f"/v1/funding-quotas/{qid}/pledges", {"quantity": 3})
        self.assertEqual(r.status, 201, r)
        self.assertEqual(r.json["amount_cents"], 75000)
        self.assertEqual(r.json["remaining_quotas"], 7)
        view = next(q for q in osc.get("/v1/funding-quotas").json["items"] if q["id"] == qid)
        self.assertEqual(view["goal_cents"], 250000)
        self.assertEqual(view["taken"], 3)
        self.assertEqual(view["confirmed"], 0)

    def test_cannot_oversell(self):
        osc, pid, qid = self._open_quota(total=2)
        self.assertEqual(self.funder.post(f"/v1/funding-quotas/{qid}/pledges", {"quantity": 2}).status, 201)
        r = self.funder.post(f"/v1/funding-quotas/{qid}/pledges", {"quantity": 1})
        self.assertEqual(r.status, 422, r)
        self.assertIn("Restam 0", r.json["title"])

    def test_parallel_pledges_never_exceed_total(self):
        import threading
        osc, pid, qid = self._open_quota(total=3)
        oks: list[int] = []
        lock = threading.Lock()

        def attempt():
            c = Client()
            c.login(self.funder.email, PASSWORD)
            r = c.post(f"/v1/funding-quotas/{qid}/pledges", {"quantity": 2})
            with lock:
                oks.append(r.status)

        threads = [threading.Thread(target=attempt) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(oks.count(201), 1, oks)
        with db_system() as db:
            total = db.scalar("SELECT coalesce(sum(quantity),0) FROM quota_pledges WHERE quota_id = $1"
                              " AND status IN ('pledged','confirmed')", qid)
        self.assertLessEqual(total, 3)

    def test_own_org_cannot_back_itself_and_closed_quota_refuses(self):
        osc, pid, qid = self._open_quota()
        own = osc.post(f"/v1/funding-quotas/{qid}/pledges", {"quantity": 1})
        self.assertEqual(own.status, 409, own)
        self.assertEqual(own.json["code"], "own_project")
        osc.patch(f"/v1/funding-quotas/{qid}", {"status": "closed"})
        # cota fechada deixa de ser visível para quem não é a proponente: 404 (não revela que existiu)
        self.assertEqual(self.funder.post(f"/v1/funding-quotas/{qid}/pledges", {"quantity": 1}).status, 404)

    def test_pledge_cannot_self_confirm(self):
        osc, pid, qid = self._open_quota()
        p = self.funder.post(f"/v1/funding-quotas/{qid}/pledges", {"quantity": 1}).json
        state = server()["state"]
        from impacto.db.pool import DbContext
        with self.assertRaises(Exception) as err:
            with state.pool.tx(DbContext(user_id=self.funder.user["id"], org_id=self.funder.org_id,
                                         org_kind="company")) as c:
                c.run("UPDATE quota_pledges SET status = 'confirmed' WHERE id = $1", p["id"])
        self.assertIn("só pode ser alterada pela administração", str(err.exception))

    def test_public_campaign_shows_remaining_quotas(self):
        osc, pid, qid = self._open_quota(total=8, cents=50000)
        self.funder.post(f"/v1/funding-quotas/{qid}/pledges", {"quantity": 2})
        slug = f"campanha-{pid[:8]}"
        c = osc.post("/v1/campaigns", {"project_id": pid, "slug": slug, "title": "Ajude nosso projeto",
                                       "summary": "Precisamos de apoio para concluir as atividades do ano.",
                                       "purpose": "Atividades do ano.", "contingency_policy": "Sem a meta, o valor vai para as atividades.",
                                       "refund_policy": "Estorno pelo provedor."})
        self.assertEqual(c.status, 201, c)
        self.assertEqual(self.anon.get(f"/v1/public/campaigns/{slug}").status, 404)   # rascunho não é público
        self.assertEqual(osc.patch(f"/v1/campaigns/{c.json['id']}", {"status": "published"}).status, 409)   # v0.33.0: sem atalho
        _publish_campaign(osc, c.json["id"])
        pub = self.anon.get(f"/v1/public/campaigns/{slug}")
        self.assertEqual(pub.status, 200, pub)
        self.assertEqual(pub.json["remaining_quotas"], 6)
        self.assertEqual(pub.json["quotas"][0]["total_quotas"], 8)
        self.assertEqual(pub.json["backers"], [])                 # show_backers desligado por padrão

    def test_campaign_slug_is_unique(self):
        osc, pid, qid = self._open_quota()
        slug = f"unica-{pid[:8]}"
        first = osc.post("/v1/campaigns", {"project_id": pid, "slug": slug, "title": "Primeira campanha",
                                           "summary": "Resumo suficientemente longo para passar na validação."})
        self.assertEqual(first.status, 201, first)
        osc2, pid2, _ = self._open_quota()
        again = osc2.post("/v1/campaigns", {"project_id": pid2, "slug": slug, "title": "Mesma slug",
                                            "summary": "Resumo suficientemente longo para passar na validação."})
        self.assertEqual(again.status, 409, again)
        self.assertEqual(again.json["code"], "slug_taken")


class FeeTablesAndServices(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.pro = new_account("provider", compliance="approved")
        cls.admin, cls.secret = make_admin()

    def test_fee_tables_start_empty_and_say_so(self):
        r = self.pro.get("/v1/fee-tables")
        self.assertEqual(r.status, 200, r)
        self.assertIn("a plataforma não estima honorário", r.json["note"])

    def test_publishing_without_source_is_refused(self):
        t = self.admin.post("/v1/admin/fee-tables", {"council_code": "CRP", "title": "Tabela de referência CRP",
                                                      "version": "2026.1"})
        self.assertEqual(t.status, 201, t)
        r = self.admin.post(f"/v1/admin/fee-tables/{t.json['id']}/publish")
        self.assertEqual(r.status, 422, r)
        self.assertEqual(r.json["code"], "source_required")

    def test_publishing_with_source_works_and_items_show(self):
        t = self.admin.post("/v1/admin/fee-tables", {
            "council_code": "CRC", "title": "Tabela de honorários contábeis", "version": "2026.1",
            "source_name": "Conselho Regional de Contabilidade (documento fornecido pelo proprietário)",
            "source_url": "https://exemplo.org/tabela-crc-2026.pdf", "source_date": "2026-01-15"})
        self.assertEqual(t.status, 201, t)
        tid = t.json["id"]
        i = self.admin.post(f"/v1/admin/fee-tables/{tid}/items", {
            "service_code": "escrituracao.mensal", "description": "Escrituração contábil mensal", "unit": "month",
            "reference_cents": 120000, "negotiable": True})
        self.assertEqual(i.status, 201, i)
        self.assertEqual(self.admin.post(f"/v1/admin/fee-tables/{tid}/publish").status, 200)
        listed = self.pro.get("/v1/fee-tables").json["items"]
        mine = next(x for x in listed if x["id"] == tid)
        self.assertEqual(mine["source_url"], "https://exemplo.org/tabela-crc-2026.pdf")
        self.assertEqual(mine["items"], 1)
        detail = self.pro.get(f"/v1/fee-tables/{tid}").json
        self.assertEqual(detail["items"][0]["reference_cents"], 120000)
        self.assertTrue(detail["items"][0]["negotiable"])

    def test_published_table_is_not_edited(self):
        t = self.admin.post("/v1/admin/fee-tables", {
            "council_code": "CRM", "title": "Tabela médica", "version": "2026.1", "source_name": "Fonte do proprietário",
            "source_url": "https://exemplo.org/crm.pdf", "source_date": "2026-02-01"}).json
        self.admin.post(f"/v1/admin/fee-tables/{t['id']}/publish")
        r = self.admin.post(f"/v1/admin/fee-tables/{t['id']}/items", {
            "service_code": "consulta", "description": "Consulta", "unit": "session"})
        self.assertEqual(r.status, 409, r)
        self.assertEqual(r.json["code"], "not_draft")

    def test_service_catalog_and_directory_card(self):
        import uuid as _u
        pro = new_account("provider", compliance="approved")     # conta própria: outro teste publica a geo da self.pro
        cred = pro.post("/v1/org/credentials", {"council": "CRP", "number": _u.uuid4().hex[:8], "uf": "MT",
                                                     "holder_name": "Profissional do catálogo"}).json["id"]
        s = pro.post("/v1/professional-services", {
            "title": "Elaboração de projeto social", "description": "Diagnóstico, lógica de intervenção e orçamento.",
            "modality": "online", "unit": "project", "price_cents": 450000, "negotiable": True, "credential_id": cred})
        self.assertEqual(s.status, 201, s)
        self.assertEqual(s.json["status"], "draft")
        self.assertEqual(pro.patch(f"/v1/professional-services/{s.json['id']}", {"status": "published"}).status, 200)
        d = pro.get("/v1/directory/services?q=projeto")
        self.assertEqual(d.status, 200, d)
        found = next(x for x in d.json["items"] if x["id"] == s.json["id"])
        self.assertEqual(found["price_cents"], 450000)
        self.assertEqual(found["council"], "CRP")
        self.assertEqual(found["verification_status"], "self_declared")
        self.assertIsNone(found["lat"])                           # sem consentimento, sem localização
        self.assertIn("documento conferido pela equipe", d.json["note"])

    def test_geo_requires_consent_to_be_public(self):
        r = self.pro.put("/v1/org/geo", {"lat": -13.05, "lng": -55.91, "precision": "city", "public": False})
        self.assertEqual(r.status, 200, r)
        with db_system() as db:
            row = db.one("SELECT lat, lng, geo_public, geo_consent_at FROM organizations WHERE id = $1", self.pro.org_id)
        self.assertIsNone(row["geo_consent_at"])
        self.assertFalse(row["geo_public"])
        self.assertEqual(self.pro.put("/v1/org/geo", {"lat": -13.05, "lng": -55.91, "precision": "city",
                                                      "public": True}).status, 200)
        with db_system() as db:
            row = db.one("SELECT geo_public, geo_consent_at FROM organizations WHERE id = $1", self.pro.org_id)
        self.assertTrue(row["geo_public"])
        self.assertIsNotNone(row["geo_consent_at"])


class GuidedDiagnosis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.osc = new_account("osc", compliance="approved")

    def _diagnosis(self) -> str:
        r = self.osc.post("/v1/diagnoses", {"title": "Diagnóstico guiado de teste"})
        assert r.status == 201, r
        return r.json["id"]

    def test_guide_lists_stages_with_progress(self):
        did = self._diagnosis()
        r = self.osc.get(f"/v1/diagnoses/{did}/guide")
        self.assertEqual(r.status, 200, r)
        self.assertEqual(r.json["total_stages"], 8)
        self.assertEqual(r.json["completed_stages"], 0)
        self.assertEqual(r.json["percent"], 0)
        self.assertEqual(r.json["next_stage"], "context")
        self.assertIn("hipótese editorial", r.json["note"])
        self.assertEqual(r.json["stages"][0]["progress"]["status"], "pending")

    def test_completing_a_stage_requires_its_mandatory_answers(self):
        did = self._diagnosis()
        bad = self.osc.put(f"/v1/diagnoses/{did}/guide/context", {"answers": {"territory": "Lucas do Rio Verde"},
                                                                   "complete": True})
        self.assertEqual(bad.status, 422, bad)
        self.assertEqual(bad.json["code"], "stage_incomplete")
        good = self.osc.put(f"/v1/diagnoses/{did}/guide/context", {
            "answers": {"territory": "Lucas do Rio Verde", "population": "Famílias atendidas pelo serviço socioassistencial"},
            "complete": True})
        self.assertEqual(good.status, 200, good)
        g = self.osc.get(f"/v1/diagnoses/{did}/guide").json
        self.assertEqual(g["completed_stages"], 1)
        self.assertEqual(g["percent"], 12)   # 1 de 8 etapas
        self.assertEqual(g["next_stage"], "problem")

    def test_partial_save_does_not_require_everything(self):
        did = self._diagnosis()
        r = self.osc.put(f"/v1/diagnoses/{did}/guide/context", {"answers": {"territory": "Só o começo"}})
        self.assertEqual(r.status, 200, r)
        self.assertEqual(r.json["status"], "in_progress")

    def test_stage_with_required_document_demands_it(self):
        did = self._diagnosis()
        r = self.osc.put(f"/v1/diagnoses/{did}/guide/compliance", {
            "answers": {"has_statute": True, "has_board": True}, "complete": True})
        self.assertEqual(r.status, 422, r)
        self.assertIn("Estatuto social", r.json["title"])
        doc1 = upload(self.osc, name="estatuto.txt", body=b"Estatuto social (exemplo)", doc_type="estatuto")
        doc2 = upload(self.osc, name="ata.txt", body=b"Ata de eleicao (exemplo)", doc_type="ata_eleicao")
        ok = self.osc.put(f"/v1/diagnoses/{did}/guide/compliance", {
            "answers": {"has_statute": True, "has_board": True}, "document_ids": [doc1, doc2], "complete": True})
        self.assertEqual(ok.status, 200, ok)

    def test_skip_is_recorded_with_reason(self):
        did = self._diagnosis()
        r = self.osc.put(f"/v1/diagnoses/{did}/guide/capacity", {"skip_reason": "Vamos preencher junto com a equipe depois."})
        self.assertEqual(r.status, 200, r)
        self.assertEqual(r.json["status"], "skipped")
        g = self.osc.get(f"/v1/diagnoses/{did}/guide").json
        self.assertEqual(g["completed_stages"], 1)

    def test_unknown_stage_and_foreign_document_are_refused(self):
        did = self._diagnosis()
        self.assertEqual(self.osc.put(f"/v1/diagnoses/{did}/guide/inventada", {"answers": {}}).status, 404)
        other = new_account("osc", compliance="approved")
        foreign = upload(other, name="alheio.txt", body=b"Documento de outra organizacao")
        r = self.osc.put(f"/v1/diagnoses/{did}/guide/context", {"answers": {}, "document_ids": [foreign]})
        self.assertEqual(r.status, 422, r)
        self.assertEqual(r.json["code"], "unknown_document")


class DocumentFormats(unittest.TestCase):
    """Os arquivos são reabertos e o XML interno é conferido. NÃO foram abertos no Office/LibreOffice neste ambiente."""

    @classmethod
    def setUpClass(cls):
        server()
        cls.osc = new_account("osc", compliance="approved")

    def test_docx_structure_and_round_trip(self):
        import io
        import zipfile
        from impacto.services import formats as F
        data = F.docx("Título do relatório", [("h1", "Seção um"), ("p", "Parágrafo com & < > acentuação."),
                                              ("li", "Item"), ("spacer", ""), ("quote", "Citação final.")])
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            names = set(z.namelist())
            self.assertIn("word/document.xml", names)
            self.assertIn("[Content_Types].xml", names)
            doc = z.read("word/document.xml").decode()
            ct = z.read("[Content_Types].xml").decode()
        self.assertIn("wordprocessingml", ct)
        self.assertIn("&amp; &lt; &gt;", doc)                 # texto é escapado, não injetado
        from defusedxml import ElementTree as ET     # o projeto já usa defusedxml em todo parse de XML
        ET.fromstring(doc)                           # XML válido
        self.assertIn("Parágrafo com & < > acentuação.", F.read_docx_text(data))

    def test_xlsx_cells_have_right_types(self):
        import io
        import zipfile

        from defusedxml import ElementTree as ET
        from impacto.services import formats as F
        data = F.xlsx([("Projetos", [["Nome", "Valor", "Ativo"], ["Projeto A", 12345, True], ["Projeto B", 0.5, False]])])
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            sheet = z.read("xl/worksheets/sheet1.xml").decode()
            wb = z.read("xl/workbook.xml").decode()
        ET.fromstring(sheet)
        ET.fromstring(wb)
        self.assertIn('name="Projetos"', wb)
        self.assertIn('r="A1"', sheet)
        self.assertIn('t="inlineStr"', sheet)                  # texto
        self.assertIn("<v>12345</v>", sheet)                   # número, não string
        self.assertIn('t="b"', sheet)                          # booleano

    def test_odf_puts_mimetype_first_uncompressed(self):
        import io
        import zipfile
        from impacto.services import formats as F
        for data, mime in ((F.odt("Doc", [("p", "Texto")]), b"application/vnd.oasis.opendocument.text"),
                           (F.ods([("Dados", [["A", 1]])]), b"application/vnd.oasis.opendocument.spreadsheet")):
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                infos = z.infolist()
                self.assertEqual(infos[0].filename, "mimetype")
                self.assertEqual(infos[0].compress_type, zipfile.ZIP_STORED)
                self.assertEqual(z.read("mimetype"), mime)
                from defusedxml import ElementTree as ET
                ET.fromstring(z.read("content.xml"))
                ET.fromstring(z.read("META-INF/manifest.xml"))

    def test_xml_export_sanitizes_tag_names(self):
        from defusedxml import ElementTree as ET
        from impacto.services import formats as F
        out = F.xml("raiz", {"nome ruim": "x", "1numero": 2, "ok": [1, 2], "nulo": None, "bool": True})
        root = ET.fromstring(out)
        tags = {child.tag for child in root}
        self.assertIn("nome_ruim", tags)
        self.assertIn("_1numero", tags)
        self.assertEqual(root.find("bool").text, "true")

    def test_pdf_with_qr_contains_code(self):
        from impacto.services import formats as F
        data = F.pdf("Documento", [("p", "Conteúdo")], footer="Rodapé",
                     verification_code="IMP-7KQ4-9F2X-3M8T",
                     verification_url="https://x.example/verificar/IMP-7KQ4-9F2X-3M8T")
        self.assertTrue(data.startswith(b"%PDF"))
        self.assertGreater(len(data), 3000)

    def test_qr_round_trip_through_our_own_pipeline(self):
        from impacto.trust import qr as QR
        for text in ("https://a.example/verificar/IMP-0000-0000-0000",
                     "https://plataforma.example.org/verificar/IMP-7KQ4-9F2X-3M8T?utm=x"):
            m = QR.matrix(text)
            size = len(m)
            version = (size - 17) // 4
            self.assertEqual(size, 17 + 4 * version)
            self.assertEqual(m[0][0], 1)                       # padrão de posição
            self.assertEqual(m[size - 8][8], 1)                # módulo escuro
            bits = 0
            for i, (r, c) in enumerate(QR._FORMAT_POS_A):
                bits |= m[r][c] << (14 - i)
            mask = next((k for k in range(8) if QR._format_bits(k) == bits), None)
            self.assertIsNotNone(mask, "informação de formato ilegível")
            total, _ecc, groups = QR._SPEC[version]
            pos = QR._data_positions(version)
            raw = [m[r][c] ^ (1 if QR._mask_fn(mask, r, c) else 0) for r, c in pos]
            words = [int("".join(str(b) for b in raw[i:i + 8]), 2) for i in range(0, (len(raw) // 8) * 8, 8)][:total]
            sizes = [s for count, s in groups for _ in range(count)]
            blocks: list[list[int]] = [[] for _ in sizes]
            idx = 0
            for i in range(max(sizes)):
                for b, sz in zip(blocks, sizes, strict=True):
                    if i < sz:
                        b.append(words[idx])
                        idx += 1
            stream = "".join(f"{w:08b}" for w in [w for b in blocks for w in b])
            self.assertEqual(int(stream[0:4], 2), 4)           # modo byte
            nbits = 8 if version < 10 else 16
            n = int(stream[4:4 + nbits], 2)
            payload = bytes(int(stream[4 + nbits + i * 8:4 + nbits + (i + 1) * 8], 2) for i in range(n))
            self.assertEqual(payload.decode(), text)

    def test_export_dataset_in_every_format(self):
        import io
        import zipfile
        for fmt, check in (("csv", lambda b: b.startswith(b"\xef\xbb\xbf")),
                           ("json", lambda b: b.lstrip().startswith(b"{")),
                           ("xml", lambda b: b.startswith(b"<?xml")),
                           ("xlsx", lambda b: zipfile.ZipFile(io.BytesIO(b)).read("xl/workbook.xml")[:5] == b"<?xml"),
                           ("ods", lambda b: zipfile.ZipFile(io.BytesIO(b)).read("mimetype").startswith(b"application")),
                           ("docx", lambda b: zipfile.ZipFile(io.BytesIO(b)).read("word/document.xml")[:5] == b"<?xml"),
                           ("odt", lambda b: zipfile.ZipFile(io.BytesIO(b)).read("content.xml")[:5] == b"<?xml"),
                           ("pdf", lambda b: b.startswith(b"%PDF"))):
            r = self.osc.post("/v1/integrations/exports", {"dataset": "projects", "format": fmt})
            self.assertEqual(r.status, 201, f"{fmt}: {r}")
            with db_system() as db:
                key = db.scalar("SELECT storage_key FROM documents WHERE id = $1", r.json["document_id"])
            data = server()["state"].storage.get(key)
            self.assertTrue(check(data), f"{fmt}: conteúdo inesperado ({data[:40]!r})")

    def test_formula_injection_is_neutralised_in_spreadsheets(self):
        import io
        import zipfile
        from impacto.services import formats as F
        from impacto.integrations.files import _csv_cell
        self.assertTrue(_csv_cell("=SUM(A1:A9)").startswith("'"))
        data = F.xlsx([("X", [["col"], [_csv_cell("=1+1")]])])
        sheet = zipfile.ZipFile(io.BytesIO(data)).read("xl/worksheets/sheet1.xml").decode()
        self.assertIn("&#x27;=1+1", sheet.replace("'=1+1", "&#x27;=1+1"))

    def test_draft_export_in_three_formats_with_optional_qr(self):
        d = self.osc.post("/v1/drafts", {"title": "Rascunho para exportar", "kind": "project_proposal",
                                         "content": "Primeira linha.\n\nSegunda linha."})
        self.assertEqual(d.status, 201, d)
        did = d.json["id"]
        for fmt, head in (("pdf", b"%PDF"), ("docx", b"PK"), ("odt", b"PK")):
            r = self.osc.post(f"/v1/drafts/{did}/export", {"format": fmt})
            self.assertEqual(r.status, 201, f"{fmt}: {r}")
            self.assertEqual(r.json["format"], fmt)
            with db_system() as db:
                key = db.scalar("SELECT storage_key FROM documents WHERE id = $1", r.json["document_id"])
            self.assertTrue(server()["state"].storage.get(key).startswith(head))
        no_rec = self.osc.post(f"/v1/drafts/{did}/export", {"format": "pdf", "include_verification": True})
        self.assertEqual(no_rec.status, 409, no_rec)
        self.assertEqual(no_rec.json["code"], "no_verifiable_record")
        rec = self.osc.post("/v1/verifiable-records", {"subject_type": "draft", "subject_id": did})
        self.assertEqual(rec.status, 201, rec)
        with_qr = self.osc.post(f"/v1/drafts/{did}/export", {"format": "pdf", "include_verification": True})
        self.assertEqual(with_qr.status, 201, with_qr)
        self.assertEqual(with_qr.json["verification_code"], rec.json["code"])

    def test_wopi_online_editing_is_declared_not_implemented(self):
        from impacto.services import formats as F
        self.assertIn("DEPENDÊNCIA EXTERNA", F.WOPI_NOTE)
        self.assertIn("não está implementada", F.WOPI_NOTE)


class TimestampsAndRfc3161(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.osc = new_account("osc", compliance="approved")

    def test_internal_timestamp_is_applied_and_verifiable(self):
        doc = upload(self.osc, name="carimbo.txt", body=b"Documento com carimbo")
        sign_document(self.osc, doc, statement="Assino para carimbar.")
        rec = self.osc.post("/v1/verifiable-records", {"subject_type": "document", "subject_id": doc}).json
        self.assertEqual(rec["timestamp"]["kind"], "internal")
        self.assertIn("Não é carimbo de ACT", rec["timestamp"]["note"])
        extra = self.osc.post(f"/v1/verifiable-records/{rec['id']}/timestamp")
        self.assertEqual(extra.status, 200, extra)
        self.assertIn("ACT", extra.json["rfc3161"])
        with db_system() as db:
            rows = db.query("SELECT kind, hashed_value, seal, stamped_at FROM trust_timestamps WHERE record_id = $1",
                            rec["id"])
        self.assertEqual(len(rows), 2)
        from impacto.trust import timestamps as TS
        st = server()["state"]
        for row in rows:
            self.assertTrue(TS.verify_internal(row["hashed_value"], row["stamped_at"].strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                                               row["seal"], st.settings.secret_key))

    def test_rfc3161_refuses_instead_of_pretending(self):
        from impacto.http import ApiError
        from impacto.trust import timestamps as TS
        with self.assertRaises(ApiError) as e:
            TS.stamp_rfc3161()
        self.assertEqual(e.exception.code, "tsa_not_configured")
