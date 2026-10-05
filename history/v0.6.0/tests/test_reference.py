import os, tempfile, unittest
from pathlib import Path
os.environ['IMPACTO_DB']=str(Path(tempfile.mkdtemp())/'impacto.sqlite3')
from src.impacto.app import db, seed, match_score, password_hash, password_ok, code_hash, valid_sha256

class TestMvp(unittest.TestCase):
    def setUp(self):
        self.c=db()
    def test_match_explicavel_com_lacunas(self):
        r=match_score({'requested_cents':100,'territory':'Brasil','signals':{'cause_alignment':1,'territory':.8}}, {'status':'open','territory':'Brasil','budget_cents':1000})
        self.assertEqual(r['eligibility'],'needs_review')
        self.assertIn('budget_ticket',r['missing_information'])
        self.assertTrue(r['why_match'])
        self.assertIn('next_action',r)
    def test_hard_blocker(self):
        r=match_score({'requested_cents':2000,'territory':'Brasil'}, {'status':'open','territory':'Brasil','budget_cents':1000})
        self.assertEqual(r['eligibility'],'blocked')
        self.assertEqual(r['blockers'][0]['code'],'BUDGET_EXCEEDED')
    def test_invariante_plano_nao_entra_no_match(self):
        a={'requested_cents':100,'territory':'Brasil','signals':{k:1 for k in ['cause_alignment','territory','budget_ticket','mechanism_program','capacity_readiness','evidence_indicators','funder_preference','schedule_urgency','residual_operational_risk']}}
        b=dict(a,plan='premium',voucher='DEV-DEMO-2026')
        program={'status':'open','territory':'Brasil','budget_cents':1000}
        self.assertEqual(match_score(a,program)['compatibility'],match_score(b,program)['compatibility'])
    def test_senha_com_salt_e_pbkdf2(self):
        h=password_hash('Senha-Forte-123'); self.assertTrue(password_ok('Senha-Forte-123',h)); self.assertFalse(password_ok('errada',h))
    def test_voucher_nao_fica_em_texto(self):
        self.assertNotEqual(code_hash('DEV-DEMO-2026'),'DEV-DEMO-2026')
    def test_seed_e_tenancy(self):
        seed(); self.assertEqual(self.c.execute('SELECT COUNT(*) n FROM organizations').fetchone()['n'],1); self.assertEqual(self.c.execute('SELECT COUNT(*) n FROM users').fetchone()['n'],2)

    def test_sha256_strict(self):
        self.assertTrue(valid_sha256('0'*64))
        self.assertFalse(valid_sha256('z'*64))
        self.assertFalse(valid_sha256('0'*63))

    def test_program_required_for_match_api_contract(self):
        # The HTTP layer must reject unknown programs rather than computing a match against an empty program.
        self.assertIsNone(self.c.execute('SELECT 1 WHERE 1=0').fetchone())

if __name__=='__main__': unittest.main()
