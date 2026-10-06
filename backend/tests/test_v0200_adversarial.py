"""v0.20.0 — §62 matriz por perfil, §64 abuso de perfil, §65 segurança, §70 gaming.

O QUE FALTAVA, E POR QUE IMPORTA MAIS DO QUE PARECE

A suíte já varria TODAS as rotas por `auth` — anônimo recusado, usuária comum recusada em rota de
administração, administrador sem segundo fator recusado. Varredura completa, sem amostragem.

Mas não havia varredura nenhuma por `min_role` nem por `kinds`. Em outras palavras: estava provado
que uma estranha não entra, e não estava provado que quem JÁ ESTÁ DENTRO não faz o que não deveria.
Numa plataforma em que a mesma organização tem pessoas com seis papéis diferentes, e em que seis
tipos de organização compartilham o mesmo produto, essa é a metade que falta — e é a metade de onde
vêm os incidentes reais, porque atacante de fora é bloqueado por acidente e colega de trabalho não.

As duas varreduras deste arquivo fecham isso, e fecham por varredura: operação nova nasce conferida.

GAMING (§70). A pergunta não é se alguém consegue invadir; é se alguém consegue PARECER melhor do
que é sem ser pego. Numa plataforma de reputação e evidência, esse é o ataque que importa, e é
silencioso: ninguém reclama, nada quebra, e a informação que a rede usa para decidir fica
sistematicamente errada a favor de quem manipulou.
"""
from __future__ import annotations

import uuid

import unittest

from tests.support import (Client, PASSWORD, db_system, last_token_for, new_account,
                           server)
from tests.test_v0120_hardening import all_routes, url_for

KINDS = ("osc", "company", "individual", "provider", "government")
ROLES_ABAIXO_DE_OWNER = ("viewer", "member", "analyst", "manager", "admin")


def _membro(owner: Client, role: str) -> Client:
    """Uma pessoa DENTRO da organização, com o papel pedido. É o atacante que faltava."""
    em = f"papel-{role}-{uuid.uuid4().hex[:8]}@teste.org"
    r = owner.post("/v1/org/invitations", {"email": em, "role": role})
    assert r.status == 201, r
    c = Client()
    c.post("/v1/auth/register", {"email": em, "password": PASSWORD, "full_name": f"Pessoa {role}",
                                 "accept_terms": True})
    c.login(em, PASSWORD)
    assert c.post("/v1/auth/accept-invite", {"token": last_token_for(em, "/convite")}).status == 200
    c.user = c.get("/v1/me").json["user"]
    c.org_id = owner.org_id
    return c


# ================================================================================================
# §62/§63 — as duas varreduras que não existiam
# ================================================================================================
class RoleSweepTests(unittest.TestCase):
    """Quem já está dentro não faz o que o papel dele não permite. Varredura, não amostra."""

    @classmethod
    def setUpClass(cls):
        server()
        cls.routes = all_routes()
        cls.owner = new_account("osc")
        cls.viewer = _membro(cls.owner, "viewer")

    def test_the_sweep_has_something_to_sweep(self):
        alvo = [r for r in self.routes if r.min_role in ("owner", "admin", "manager")
                and r.auth not in ("admin", "none")]
        self.assertGreater(len(alvo), 20,
                           "a varredura por papel estaria vazia — e um teste vazio passa sempre")

    def test_a_viewer_cannot_reach_any_route_that_demands_a_higher_role(self):
        """O papel mais baixo da organização contra TODA rota que exige papel acima dele.

        Antes desta rodada, a suíte varria por `auth` e nunca por `min_role`: estava provado que
        uma estranha não entra, não que a estagiária não cancela a assinatura.
        """
        passou = []
        for r in self.routes:
            if r.auth in ("admin", "none") or r.min_role in (None, "viewer"):
                continue
            resp = self.viewer.request(r.method, url_for(r.path))
            # 401/403 = barrado (certo). 404/409/422 = passou da autorização e morreu no dado,
            # o que também significa que a autorização NÃO barrou.
            if resp.status not in (401, 403):
                passou.append(f"{r.method} {r.path} (exige {r.min_role}) -> {resp.status}")
        self.assertEqual(passou, [],
                         "papel `viewer` atravessou a autorização em rota de papel superior:\n"
                         + "\n".join(passou))

    def test_no_financial_route_is_reachable_by_anyone_below_owner(self):
        """§64: membro de projeto executando ação financeira de administrador."""
        financeiras = [r for r in self.routes
                       if r.min_role == "owner" and any(
                           p in r.path for p in ("/billing", "/payments/charges"))]
        self.assertGreater(len(financeiras), 4, "não achei as rotas financeiras: o teste seria vazio")
        for papel in ("member", "analyst", "manager"):
            quem = _membro(self.owner, papel)
            for r in financeiras:
                resp = quem.request(r.method, url_for(r.path))
                self.assertIn(resp.status, (401, 403),
                              f"{papel} atravessou {r.method} {r.path} -> {resp.status}")


class OrgKindSweepTests(unittest.TestCase):
    """§62 — a matriz por tipo de organização, que não existia para nenhum dos seis."""

    @classmethod
    def setUpClass(cls):
        server()
        cls.routes = all_routes()
        cls.contas = {k: new_account(k) for k in KINDS}

    def test_every_organization_kind_is_exercised(self):
        self.assertEqual(set(self.contas), set(KINDS))
        for k, c in self.contas.items():
            self.assertEqual(c.get("/v1/me").json["active_org"]["kind"], k)

    def test_a_route_restricted_by_kind_refuses_every_other_kind(self):
        """Varredura: toda rota com `kinds` declarado recusa os tipos que não estão na lista."""
        restritas = [r for r in self.routes if r.kinds and r.auth not in ("admin", "none")]
        self.assertGreater(len(restritas), 20, "varredura por tipo estaria vazia")
        passou = []
        for r in restritas:
            for kind, cli in self.contas.items():
                if kind in r.kinds:
                    continue
                resp = cli.request(r.method, url_for(r.path))
                if resp.status not in (401, 403):
                    passou.append(f"{kind} atravessou {r.method} {r.path} (só {r.kinds}) "
                                  f"-> {resp.status}")
        self.assertEqual(passou, [],
                         "tipo de organização atravessou rota restrita a outro tipo:\n"
                         + "\n".join(passou[:40]))

    def test_no_kind_gets_a_server_error_where_another_gets_a_clean_refusal(self):
        """Recusa é resposta; 5xx é defeito. Um tipo que estoura onde outro é recusado é defeito."""
        ruins = []
        for r in self.routes:
            if r.auth in ("admin", "none") or not r.kinds:
                continue
            for kind, cli in self.contas.items():
                resp = cli.request(r.method, url_for(r.path))
                if resp.status >= 500:
                    ruins.append(f"{kind} {r.method} {r.path} -> {resp.status}")
        self.assertEqual(ruins, [], "erro de servidor por tipo de organização:\n" + "\n".join(ruins))


class ProviderAsAttackerTests(unittest.TestCase):
    """§64 — o perfil profissional como atacante cruzado. Nenhuma matriz o usava."""

    @classmethod
    def setUpClass(cls):
        cls.osc = new_account("osc")
        cls.provider = new_account("provider")
        r = cls.osc.post("/v1/projects", {
            "title": "Projeto que o profissional não deve enxergar",
            "problem": "Problema declarado para o teste de isolamento por perfil profissional.",
            "objectives": "Objetivo declarado para o teste de isolamento.",
            "methodology": "Metodologia declarada para o teste.", "territory": "MT"})
        assert r.status == 201, r
        cls.project_id = r.json["id"]

    def test_a_professional_cannot_read_another_organizations_project(self):
        r = self.provider.get(f"/v1/projects/{self.project_id}")
        self.assertIn(r.status, (403, 404),
                      "profissional leu projeto de outra organização")

    def test_a_professional_cannot_write_into_another_organizations_project(self):
        for caminho, corpo in (
                (f"/v1/projects/{self.project_id}/indicators", {"indicator_id": str(uuid.uuid4())}),
                (f"/v1/projects/{self.project_id}/risks", {"title": "x", "category": "operacional"}),
        ):
            r = self.provider.post(caminho, corpo)
            self.assertNotIn(r.status, (200, 201),
                             f"profissional escreveu em {caminho} de outra organização")

    def test_a_professional_cannot_read_another_organizations_documents(self):
        r = self.provider.get(f"/v1/documents?project_id={self.project_id}")
        itens = (r.json or {}).get("items", []) if r.status == 200 else []
        self.assertEqual(itens, [], "documentos de outra organização vazaram para o profissional")


class AiCannotActPrivilegedTests(unittest.TestCase):
    """§64 — IA executando ação privilegiada.

    A trava estrutural já existia (`test_only_the_declared_places_call_the_language_model`), e ela
    responde "quem chama o modelo". Esta aqui responde a outra pergunta: a saída do modelo consegue
    virar ato? A resposta tem de ser não por construção — o que sai é rascunho marcado, e todo ato
    continua exigindo papel, tipo de organização e, quando é decisão sobre terceiro, pessoa.
    """

    @classmethod
    def setUpClass(cls):
        cls.osc = new_account("osc")

    def test_the_ai_routes_are_not_reachable_without_a_role(self):
        from tests.test_v0120_hardening import all_routes
        ia = [r for r in all_routes() if "/v1/ai/" in r.path]
        self.assertTrue(ia, "não achei as rotas de IA")
        anon = Client()
        for r in ia:
            self.assertEqual(anon.request(r.method, url_for(r.path)).status, 401, r.path)

    def test_no_ai_route_can_publish_approve_sign_or_charge(self):
        """Nenhuma rota de IA aparece entre as que mudam estado de terceiro."""
        from tests.test_v0120_hardening import all_routes
        for r in all_routes():
            if "/v1/ai/" not in r.path:
                continue
            for proibido in ("publish", "approve", "sign", "charge", "award", "enforce",
                             "validate", "revoke"):
                self.assertNotIn(proibido, r.path,
                                 f"rota de IA com verbo de ato privilegiado: {r.path}")

    def test_the_ai_output_is_always_marked_as_a_draft_needing_review(self):
        import pathlib
        gw = (pathlib.Path(__file__).resolve().parents[1] / "impacto" / "engines" / "ai"
              / "gateway.py").read_text(encoding="utf-8")
        self.assertIn("human_review_required", gw)
        self.assertIn("draft", gw)


# ================================================================================================
# §70 — GAMING: a pergunta não é se dá para invadir, é se dá para PARECER melhor sem ser pego
# ================================================================================================
class DeclaredDataNeverBuysScoreTests(unittest.TestCase):
    """O ataque que importa numa plataforma de evidência: inflar o que se declara.

    Não há cadeado possível contra alguém digitar um número maior — e não deveria haver, porque a
    organização tem direito de declarar o que ela sabe. A defesa certa é outra: o que é apenas
    DECLARADO não pode comprar nota, selo nem reputação. Quem inflar fica com um número grande e
    com a mesma leitura de antes, e a diferença entre declarado e verificado aparece na resposta.
    """

    @classmethod
    def setUpClass(cls):
        cls.honesta = new_account("osc")
        cls.inflada = new_account("osc")
        base = {
            "problem": "Mesmo problema declarado nos dois projetos, para a comparação ser justa.",
            "objectives": "Mesmo objetivo declarado nos dois projetos.",
            "methodology": "Mesma metodologia declarada nos dois projetos.",
            "territory": "MT",
        }
        cls.p_honesta = cls.honesta.post("/v1/projects", {
            "title": "Projeto com números modestos", "beneficiaries_count": 50,
            "budget_total_cents": 500000, **base}).json["id"]
        cls.p_inflada = cls.inflada.post("/v1/projects", {
            "title": "Projeto com números inflados", "beneficiaries_count": 500000,
            "budget_total_cents": 900000000, **base}).json["id"]

    def test_inflating_beneficiaries_and_budget_does_not_raise_reputation(self):
        rep_h = self.honesta.get("/v1/reputation/me").json
        rep_i = self.inflada.get("/v1/reputation/me").json
        por_dim_h = {d["dimension"]: d for d in rep_h["dimensions"]}
        por_dim_i = {d["dimension"]: d for d in rep_i["dimensions"]}
        for dim, di in por_dim_i.items():
            dh = por_dim_h.get(dim)
            if dh is None or di["value"] is None or dh["value"] is None:
                continue
            self.assertLessEqual(
                di["value"], dh["value"] + 0.001,
                f"declarar números maiores subiu a dimensão '{dim}': "
                f"{dh['value']} → {di['value']}")

    def test_reputation_separates_what_was_verified_from_what_was_merely_declared(self):
        """A defesa só funciona se a diferença for VISÍVEL. Senão, é promessa."""
        rep = self.inflada.get("/v1/reputation/me").json
        for d in rep["dimensions"]:
            self.assertIn("verified_observations", d)
            self.assertIn("self_declared_observations", d)

    def test_a_seal_cannot_be_bought_with_declared_numbers(self):
        """A definição é CRIADA aqui: `seal_definitions` nasce vazia, e um teste que depende de
        dado pré-existente é um teste que pula para sempre — quase tão ruim quanto não existir."""
        from tests.support import make_admin
        admin, _ = make_admin()
        r = admin.post("/v1/admin/seals/definitions", {
            "code": f"gaming_{uuid.uuid4().hex[:8]}", "scope": "organization",
            "title": "Selo que exige conformidade aprovada",
            "what_it_attests": "Que a organização passou pelas conferências de conformidade da "
                               "plataforma na data da concessão.",
            "what_it_does_not_attest": "Não atesta qualidade do trabalho, idoneidade dos sócios "
                                       "nem resultado de projeto algum.",
            "validity_days": 365, "criteria": [{"rule_code": "compliance_approved"}]})
        self.assertEqual(r.status, 201, r)
        did = r.json["id"]
        self.assertEqual(admin.post(f"/v1/admin/seals/definitions/{did}/publish", {}).status, 200)

        aval = self.inflada.post("/v1/seals/evaluate",
                                 {"definition_id": did, "subject_id": self.inflada.org_id})
        self.assertEqual(aval.status, 200, aval)
        self.assertFalse(aval.json.get("all_met"),
                         "selo saiu cumprido para quem só declarou números grandes")
        self.assertTrue(aval.json.get("unmet"), "a avaliação não disse qual critério faltou")
        self.assertTrue([c for c in aval.json["criteria"] if not c["met"]],
                        "a avaliação não trouxe o critério não satisfeito com o detalhe")

        concessao = admin.post("/v1/admin/seals/awards",
                               {"definition_id": did, "subject_id": self.inflada.org_id})
        self.assertNotEqual(concessao.status, 201,
                            "a concessão passou mesmo com critério não satisfeito")


class RepeatedClaimsDoNotPayTests(unittest.TestCase):
    """§70 — afirmações repetidas. Reenviar a mesma coisa não pode limpar nem inflar nada."""

    @classmethod
    def setUpClass(cls):
        cls.c = new_account("osc")
        cls.texto = ("Atendemos quinhentas famílias com segurança alimentar no período declarado "
                     "neste teste de repetição de afirmação.")
        base = {"problem": "Problema declarado para o teste de afirmações repetidas.",
                "objectives": "Objetivo declarado para o teste.",
                "methodology": "Metodologia declarada.", "territory": "MT"}
        cls.project_id = cls.c.post("/v1/projects",
                                    {"title": "Projeto das afirmações", **base}).json["id"]
        cls.corpo = {"subject_type": "project", "subject_id": cls.project_id,
                     "claim_kind": "result", "statement": cls.texto,
                     "period_start": "2026-01-01", "period_end": "2026-06-30"}

    def test_1_declaring_the_same_claim_twice_does_not_create_two_supported_claims(self):
        a = self.c.post("/v1/claims", self.corpo)
        b = self.c.post("/v1/claims", self.corpo)
        self.assertEqual(a.status, 201, a)
        if b.status == 201:
            # Se a plataforma aceita a repetição, ela NÃO pode contar como duas afirmações
            # sustentadas: ambas nascem sem verificação nenhuma.
            itens = self.c.get("/v1/claims").json["items"]
            iguais = [i for i in itens if i["statement"] == self.texto]
            self.assertTrue(all(i["status"] in ("unchecked", "unsupported", "flagged")
                                for i in iguais),
                            "afirmação repetida nasceu sustentada")
        else:
            self.assertIn(b.status, (409, 422), b)

    def test_2_many_unchecked_claims_do_not_improve_the_integrity_reading(self):
        antes = self.c.get("/v1/reputation/me").json
        dim_antes = {d["dimension"]: d["value"] for d in antes["dimensions"]}
        for i in range(5):
            self.c.post("/v1/claims", {**self.corpo,
                                       "statement": f"{self.texto} Variação número {i}."})
        depois = self.c.get("/v1/reputation/me").json
        for d in depois["dimensions"]:
            v_antes = dim_antes.get(d["dimension"])
            if v_antes is None or d["value"] is None:
                continue
            self.assertLessEqual(d["value"], v_antes + 0.001,
                                 f"declarar afirmações não verificadas subiu '{d['dimension']}'")


class EvidenceCannotBeRecycledTests(unittest.TestCase):
    """§70 — evidência reaproveitada: o mesmo arquivo servindo de prova para coisas diferentes."""

    @classmethod
    def setUpClass(cls):
        cls.c = new_account("osc")
        base = {"problem": "Problema declarado para o teste de reaproveitamento de evidência.",
                "objectives": "Objetivo declarado para o teste.",
                "methodology": "Metodologia declarada para o teste.", "territory": "MT"}
        cls.p1 = cls.c.post("/v1/projects", {"title": "Projeto um", **base}).json["id"]
        cls.p2 = cls.c.post("/v1/projects", {"title": "Projeto dois", **base}).json["id"]

    def test_the_same_file_hash_is_detected_as_duplicate(self):
        """O mesmo conteúdo enviado duas vezes tem o mesmo sha256, e isso é visível.

        A plataforma NÃO proíbe reusar um documento — às vezes o mesmo comprovante serve mesmo a
        dois marcos. O que ela não pode é deixar o reuso invisível: o sinal de risco
        `duplicate_document_hash` existe exatamente para que alguém olhe.
        """
        from impacto.services import risk as RISK
        regras = [r for r in dir(RISK) if "duplicate" in r.lower()]
        fonte = (__import__("pathlib").Path(__file__).resolve().parents[1]
                 / "impacto" / "services" / "risk.py").read_text(encoding="utf-8")
        self.assertIn("duplicate_document_hash", fonte,
                      f"não há detecção de documento repetido (encontrei: {regras})")
        self.assertIn("evidence_reuse", fonte,
                      "não há detecção de evidência reaproveitada")

    def test_an_evidence_belongs_to_one_project_and_cannot_be_moved(self):
        with db_system() as c:
            colunas = c.query("SELECT column_name FROM information_schema.columns"
                              " WHERE table_name = 'evidences' AND column_name = 'project_id'")
        self.assertTrue(colunas, "evidência sem projeto seria evidência de qualquer coisa")


class FeedbackCannotBeFarmedTests(unittest.TestCase):
    """§70 — retorno artificial. Muita gente dizendo a mesma coisa não pode mover nada."""

    def test_feedback_does_not_feed_any_score(self):
        """A defesa aqui é estrutural e já existia: o retorno humano não realimenta o motor.

        É a decisão de projeto que torna 'fazenda de feedback' inútil — não há o que farmar. Este
        teste existe para que a decisão não seja revertida por conveniência numa rodada futura.
        """
        import pathlib
        m = (pathlib.Path(__file__).resolve().parents[1] / "impacto" / "services"
             / "matching.py").read_text(encoding="utf-8")
        i = m.index("def record_feedback")
        trecho = m[i:i + 2500]
        for proibido in ("UPDATE match_runs SET score", "weights[", "recalibrat"):
            self.assertNotIn(proibido, trecho,
                             "o retorno humano passou a realimentar o motor: vira alvo de fazenda")

    def test_the_same_actor_cannot_record_feedback_twice(self):
        import pathlib
        m = (pathlib.Path(__file__).resolve().parents[1] / "impacto" / "services"
             / "matching.py").read_text(encoding="utf-8")
        self.assertIn("already_recorded", m, "retorno repetido do mesmo ator tem de ser recusado")


class RecommendationAndMatchCannotBeSteeredTests(unittest.TestCase):
    """§70 — manipulação de recomendação e de match."""

    @classmethod
    def setUpClass(cls):
        cls.c = new_account("osc")

    def test_no_match_or_recommendation_write_can_target_another_organization(self):
        """O ataque que §70 chama de manipulação de recomendação tem um alvo preciso: aparecer na
        recomendação DOS OUTROS.

        Recalcular as próprias recomendações, ou marcar uma como resolvida, é agir na própria
        caixa — não muda o que ninguém mais vê. O que não pode existir é rota que escreva
        recomendação ou match para organização ALHEIA. A conferência é no código: toda escrita
        nessa família tem de ser amarrada a `ctx.org_id`, e nenhuma pode aceitar organização de
        destino vinda do corpo.
        """
        import inspect
        from tests.test_v0120_hardening import all_routes
        suspeitas = []
        for r in all_routes():
            if r.method not in ("POST", "PUT", "PATCH") or r.auth == "admin":
                continue
            if "match" not in r.path and "recommend" not in r.path:
                continue
            fonte = inspect.getsource(r.handler)
            if "readonly=True" in fonte:
                continue                       # calcula e devolve, não grava
            amarrada = "ctx.org_id" in fonte or "ctx.user_id" in fonte
            aceita_alvo = any(x in fonte for x in ("body.org_id", "body.target_org",
                                                   "body.organization_id"))
            if not amarrada or aceita_alvo:
                suspeitas.append(f"{r.method} {r.path}")
        self.assertEqual(suspeitas, [],
                         "escrita de match/recomendação não amarrada à própria organização: "
                         + ", ".join(suspeitas))

    def test_the_match_engine_has_no_write_path_at_all(self):
        """O motor calcula; quem grava é a fachada, e só o registro da execução."""
        import pathlib
        eng = (pathlib.Path(__file__).resolve().parents[1] / "impacto" / "engines" / "match"
               / "engine.py").read_text(encoding="utf-8")
        for proibido in ("INSERT INTO", "UPDATE ", "DELETE FROM"):
            self.assertNotIn(proibido, eng,
                             "o motor de compatibilidade escreve no banco: aí ele pode ser movido")

    def test_the_match_weights_live_in_a_file_no_organization_can_write(self):
        import pathlib
        pesos = pathlib.Path(__file__).resolve().parents[2] / "config" / "match_weights.json"
        self.assertTrue(pesos.exists())
        from tests.test_v0120_hardening import all_routes
        for r in all_routes():
            if r.method in ("POST", "PUT", "PATCH") and "weight" in r.path.lower():
                self.assertEqual(r.auth, "admin",
                                 f"peso de match alterável fora da administração: {r.path}")

    def test_a_recommendation_always_says_where_it_came_from(self):
        """Recomendação sem origem declarada é recomendação que ninguém consegue auditar."""
        r = self.c.get("/v1/recommendations")
        if r.status != 200:
            self.skipTest("rota de recomendação indisponível neste perfil")
        for item in (r.json.get("items") or [])[:5]:
            self.assertTrue(item.get("rationale") or item.get("why"),
                            "recomendação sem explicação")


class DuplicateProjectsAndBeneficiariesTests(unittest.TestCase):
    """§70 — projetos e beneficiários duplicados.

    ACHADO HONESTO DESTA RODADA: a plataforma NÃO deduplica nenhum dos dois, e não é descuido —
    é consequência de duas decisões anteriores.

    Projetos: duas organizações podem legitimamente tocar projetos quase idênticos (é o que
    replicação de solução significa), e a mesma organização pode ter edições por ano. Recusar o
    parecido produziria falso positivo em cima de quem está certo.

    Beneficiários: a plataforma NÃO cadastra pessoa atendida. `beneficiaries_count` é um NÚMERO
    declarado, e não existe lista de nomes para deduplicar — decisão de privacidade tomada lá atrás
    e registrada em `test_beneficiary_group_is_never_a_filter_on_people`.

    O que estes testes travam é a consequência: se não há deduplicação, então o número duplicado
    não pode valer nota. É o mesmo princípio de `DeclaredDataNeverBuysScoreTests`, aplicado ao caso
    que §70 cita por nome.
    """

    def test_the_platform_does_not_store_individual_beneficiaries_so_there_is_nothing_to_dedupe(self):
        with db_system() as c:
            pessoais = c.query(
                "SELECT table_name FROM information_schema.tables"
                " WHERE table_schema = 'public' AND table_name LIKE '%%beneficiar%%'")
        self.assertEqual(pessoais, [],
                         "existe tabela de beneficiário individual: aí a deduplicação passa a ser "
                         "exigível, e este teste tem de mudar junto")

    def test_the_beneficiary_count_is_a_declared_number_and_is_reported_as_such(self):
        c = new_account("osc")
        pid = c.post("/v1/projects", {
            "title": "Projeto com contagem declarada", "beneficiaries_count": 999999,
            "problem": "Problema declarado para o teste de contagem de beneficiários.",
            "objectives": "Objetivo declarado para o teste.",
            "methodology": "Metodologia declarada.", "territory": "MT"}).json["id"]
        q = c.get(f"/v1/projects/{pid}/data-quality")
        self.assertEqual(q.status, 200, q)
        self.assertIn("NÃO É AVALIAÇÃO DO PROJETO", q.json["not_a_performance_score"])

    def test_two_identical_projects_are_allowed_but_neither_gains_anything_from_it(self):
        c = new_account("osc")
        corpo = {"title": "Projeto idêntico ao outro",
                 "problem": "Problema declarado duas vezes, de propósito, neste teste.",
                 "objectives": "Objetivo declarado duas vezes.",
                 "methodology": "Metodologia declarada duas vezes.", "territory": "MT",
                 "beneficiaries_count": 100}
        antes = {d["dimension"]: d["value"] for d in c.get("/v1/reputation/me").json["dimensions"]}
        self.assertEqual(c.post("/v1/projects", corpo).status, 201)
        self.assertEqual(c.post("/v1/projects", corpo).status, 201)
        depois = c.get("/v1/reputation/me").json["dimensions"]
        for d in depois:
            v = antes.get(d["dimension"])
            if v is None or d["value"] is None:
                continue
            self.assertLessEqual(d["value"], v + 0.001,
                                 f"duplicar projeto subiu '{d['dimension']}'")


# ================================================================================================
# §65 — as três lacunas da suíte de segurança
# ================================================================================================
class OversizedPayloadTests(unittest.TestCase):
    """Corpo gigante fora de upload. O único 413 da suíte era de arquivo."""

    @classmethod
    def setUpClass(cls):
        cls.c = new_account("osc")

    def test_a_json_body_over_the_limit_is_refused_with_413(self):
        """Pouco acima do teto: o cliente termina de enviar e LÊ a recusa.

        v0.21.0 — o teste ficou DETERMINÍSTICO sem ficar mais frouxo.

        Acima do teto, o servidor responde 413 e encerra enquanto o cliente ainda empurra bytes.
        Quem ganha essa corrida depende da carga da máquina: isolado o cliente lia a resposta, na
        suíte completa a conexão às vezes caía antes. O teste reprovava por causa da corrida, não
        por causa do produto.

        As duas garantias continuam exigidas, e nenhuma foi trocada por `assertLess` ou por um
        `try/except` que engole qualquer resultado:
          1. QUANDO há resposta, ela é 413 `payload_too_large` — um 201 aqui reprova;
          2. SEMPRE, nada é criado.
        A primeira é tentada mais de uma vez justamente para não virar letra morta nas máquinas em
        que a conexão quase sempre cai.
        """
        import urllib.error
        from impacto.config import load_settings
        limite = load_settings().max_body_bytes
        antes = len(self.c.get("/v1/projects").json["items"])
        respostas = []
        for _ in range(3):
            try:
                r = self.c.post("/v1/projects", {
                    "title": "Projeto com corpo acima do limite", "problem": "A" * (limite + 50_000),
                    "objectives": "Objetivo declarado.", "methodology": "Metodologia declarada.",
                    "territory": "MT"})
            except (urllib.error.URLError, ConnectionError, OSError):
                continue    # servidor cortou antes de o cliente terminar: é a recusa, na forma crua
            respostas.append(r)
            self.assertEqual(r.status, 413, f"corpo acima do teto não recusado: {r.status}")
            self.assertEqual((r.json or {}).get("code"), "payload_too_large")
            break
        depois = len(self.c.get("/v1/projects").json["items"])
        self.assertEqual(depois, antes, "corpo acima do teto criou projeto")
        if not respostas:
            self.skipTest("as três tentativas tiveram a conexão cortada antes da resposta; "
                          "a garantia de que nada foi criado continua verificada acima")

    def test_a_body_far_over_the_limit_never_becomes_work(self):
        """Muito acima do teto: o servidor recusa e fecha; o cliente pode nem ler a resposta.

        Conexão derrubada no meio de um envio de 6 MB é comportamento CORRETO — o servidor
        respondeu 413 e encerrou enquanto o cliente ainda empurrava bytes. A primeira versão deste
        teste exigia um código HTTP e quebrava por isso; o que importa não é ler a resposta, é que
        nada tenha sido criado.
        """
        import urllib.error
        antes = len(self.c.get("/v1/projects").json["items"])
        try:
            self.c.post("/v1/projects", {
                "title": "Projeto com corpo gigante", "problem": "A" * (6 * 1024 * 1024),
                "objectives": "Objetivo declarado.", "methodology": "Metodologia declarada.",
                "territory": "MT"})
        except (urllib.error.URLError, ConnectionError, OSError):
            pass        # servidor cortou: é a recusa, na forma mais crua
        depois = len(self.c.get("/v1/projects").json["items"])
        self.assertEqual(depois, antes, "corpo gigante criou projeto")

    def test_a_deeply_nested_json_does_not_crash_the_parser(self):
        aninhado: dict = {"x": 1}
        for _ in range(200):
            aninhado = {"x": aninhado}
        r = self.c.post("/v1/projects", {"title": "t", "problem": "p", "objectives": "o",
                                         "methodology": "m", "territory": "MT",
                                         "extra": aninhado})
        self.assertLess(r.status, 500, "JSON profundo virou erro de servidor")

    def test_a_long_string_in_every_text_field_is_refused_by_validation_not_by_the_database(self):
        """Limite de tamanho tem de estar no esquema: chegar ao banco já é tarde."""
        r = self.c.post("/v1/projects", {
            "title": "T" * 5000, "problem": "p" * 50, "objectives": "o" * 50,
            "methodology": "m" * 50, "territory": "MT"})
        self.assertEqual(r.status, 422, "texto longo passou da validação")
        self.assertEqual((r.json or {}).get("code"), "validation_error")


class RateLimitIsActuallyEnforcedTests(unittest.TestCase):
    """O limite de taxa DISPARANDO, não apenas declarado no catálogo.

    A suíte conferia `spec.rate is not None` em rota pública — o que prova que alguém escreveu a
    declaração, não que ela funciona. São coisas diferentes, e a diferença só aparece num incidente.
    """

    def test_the_limiter_actually_raises_429_at_the_declared_limit(self):
        """O limitador DISPARANDO, exercitado direto.

        O servidor de teste é iniciado com `RATE_LIMIT_MULTIPLIER=1000` em `tests/support.py`, de
        propósito: sem isso, a suíte inteira bateria no próprio limite e os testes ficariam
        intermitentes. A consequência é que martelar uma rota pela HTTP nunca produz 429 aqui — e
        um teste que depende disso seria pulado para sempre, o que é quase tão ruim quanto não
        existir.

        Então o limitador é exercitado onde ele decide: `ratelimit.hit`, com o multiplicador
        neutralizado só dentro deste teste.
        """
        import os
        from unittest import mock

        from impacto.http import ApiError
        from impacto.services import ratelimit
        from tests.support import server

        estado = server()["state"]

        class _Ctx:
            pool = estado.pool

        chave = f"teste-{uuid.uuid4().hex[:12]}"
        with mock.patch.dict(os.environ, {"RATE_LIMIT_MULTIPLIER": "1"}):
            self.assertEqual(ratelimit._multiplier(), 1)
            for i in range(3):
                ratelimit.hit(_Ctx(), "teste_bucket", chave, 3, 3600)
                self.assertLess(i, 3)
            with self.assertRaises(ApiError) as e:
                ratelimit.hit(_Ctx(), "teste_bucket", chave, 3, 3600)
        self.assertEqual(e.exception.status, 429)
        self.assertEqual(e.exception.code, "rate_limited")

    def test_the_multiplier_is_refused_outside_development(self):
        """A folga que torna a suíte estável NÃO pode acompanhar o produto até produção."""
        import pathlib
        cfg = (pathlib.Path(__file__).resolve().parents[1] / "impacto"
               / "config.py").read_text(encoding="utf-8")
        self.assertIn("RATE_LIMIT_MULTIPLIER deve ser 1 em staging/production", cfg)

    def test_every_public_write_route_declares_a_rate_limit(self):
        """A declaração continua sendo exigida de TODAS — o disparo é conferido em uma."""
        from tests.test_v0120_hardening import all_routes
        sem = [f"{r.method} {r.path}" for r in all_routes()
               if r.auth == "none" and r.method in ("POST", "PUT", "PATCH", "DELETE")
               and r.rate is None]
        self.assertEqual(sem, [], "escrita pública sem limite de taxa declarado: " + ", ".join(sem))
