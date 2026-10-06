"""v0.18.1 — as travas que esta rodada acrescentou, e o inventário de dependências (FASES 5 e 6).

Três grupos:

* **`project_impact_context()`** — a função que faz o sinal contextual atravessar a RLS. Ela é
  `SECURITY DEFINER`, então o que ela NÃO devolve é tão importante quanto o que devolve.
* **A regra de totalidade** — a dozena regra de integridade de alegação, nascida de um achado da
  jornada: "erradicamos" passava quando havia qualquer medição validada.
* **Dependências** — a auditoria de vulnerabilidade está BLOQUEADA PELO AMBIENTE (os registries não
  respondem), e isso não pode virar "sem vulnerabilidades". O que é verificável offline — fixação
  de versão, inventário declarado, ausência de faixa aberta em dependência de execução — é
  verificado aqui.
"""
from __future__ import annotations

import json
import pathlib
import re
import unittest

from tests.support import app_tx, grant_premium, new_account, owner_conn, server

RAIZ = pathlib.Path(__file__).resolve().parents[2]


# ================================================================ a função do contexto agregado
class ImpactContextFunctionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.osc = new_account("osc", compliance="approved")
        cls.funder = new_account("company", compliance="approved")
        cls.stranger = new_account("osc", compliance="approved")
        grant_premium(cls.osc)
        cls.project = cls.osc.post("/v1/projects", {
            "title": "Projeto do teste da função de contexto",
            "summary": "Projeto criado para conferir o que a função agregada devolve e o que não.",
            "problem": "O problema declarado pelo projeto, com extensão suficiente para o CHECK.",
            "objectives": "Os objetivos declarados pelo projeto, com extensão suficiente.",
            "territory": "BR-MT-5105259", "causes": ["educacao"],
            "beneficiaries_count": 40, "budget_total_cents": 900_000}).json["id"]
        cls.osc.put(f"/v1/projects/{cls.project}/equity/context", {
            "need_statement": "SEGREDO-NARRATIVA: a comunidade não tem oferta de contraturno, e "
                              "este texto não pode sair da organização por caminho de agregado.",
            "additionality": "SEGREDO-ADICIONALIDADE: nenhuma outra organização atua aqui.",
            "counterfactual": "SEGREDO-CONTRAFACTUAL: sem o projeto, nada acontece no contraturno."})

    def test_an_unpublished_project_returns_no_row_at_all(self):
        """Contexto de projeto que ninguém pode ver não influencia o ranking de ninguém.

        Projeto PRÓPRIO: os métodos da classe rodam em ordem alfabética, e
        `test_a_published_project…` publicaria o projeto da classe antes deste rodar.
        """
        privado = self.osc.post("/v1/projects", {
            "title": "Projeto que permanece privado",
            "summary": "Projeto criado para conferir que o agregado não sai de projeto privado.",
            "problem": "O problema declarado pelo projeto, com extensão suficiente para o CHECK.",
            "objectives": "Os objetivos declarados pelo projeto, com extensão suficiente.",
            "territory": "BR-MT-5105259", "causes": ["educacao"],
            "beneficiaries_count": 10, "budget_total_cents": 100_000}).json["id"]
        self.osc.put(f"/v1/projects/{privado}/equity/context", {
            "need_statement": "Necessidade declarada num projeto que não foi publicado.",
            "additionality": "Adicionalidade declarada num projeto que não foi publicado."})
        with app_tx(self.funder, readonly=True) as c:
            rows = c.query("SELECT * FROM project_impact_context($1)", privado)
        self.assertEqual(rows, [], "projeto não publicado devolveu contexto agregado")

    def test_a_published_project_gives_the_funder_the_numbers(self):
        self.assertEqual(self.osc.post(f"/v1/projects/{self.project}/publish", {}).status, 200)
        with app_tx(self.funder, readonly=True) as c:
            row = c.one("SELECT * FROM project_impact_context($1)", self.project)
        self.assertTrue(row and row["has_context"])
        self.assertIsNotNone(row["additionality_score"])
        self.assertTrue(row["has_counterfactual"])

    def test_the_function_never_returns_narrative_text(self):
        """A trava de privacidade: o financiador recebe números, não a narrativa da comunidade."""
        with app_tx(self.funder, readonly=True) as c:
            row = c.one("SELECT * FROM project_impact_context($1)", self.project)
        texto = json.dumps(row, default=str)
        for segredo in ("SEGREDO-NARRATIVA", "SEGREDO-ADICIONALIDADE", "SEGREDO-CONTRAFACTUAL"):
            self.assertNotIn(segredo, texto, "a função agregada vazou texto livre")
        self.assertEqual(
            sorted(row),
            sorted(["has_context", "need_level", "barrier_burden", "additionality_score",
                    "outcome_evidence_score", "impact_evidence_score", "denominator_quality",
                    "has_counterfactual"]),
            "a função passou a devolver campo novo: confira se ele é agregado e não sensível")

    def test_the_narrative_itself_stays_unreadable_to_outsiders(self):
        """A função não afrouxou a política: a tabela continua fechada."""
        with app_tx(self.funder, readonly=True) as c:
            self.assertEqual(c.scalar("SELECT count(*) FROM equity_contexts WHERE project_id = $1",
                                      self.project), 0)
        with app_tx(self.stranger, readonly=True) as c:
            self.assertEqual(c.scalar("SELECT count(*) FROM equity_contexts WHERE project_id = $1",
                                      self.project), 0)
        # A rota responde 200 — e devolve VAZIO, porque a RLS não entrega a linha. O invariante é
        # a ausência do texto, não o código de status: 200 com nada é a política funcionando.
        ficha = self.funder.get(f"/v1/projects/{self.project}/equity")
        self.assertEqual(ficha.status, 200, ficha)
        corpo = json.dumps(ficha.json, default=str)
        for segredo in ("SEGREDO-NARRATIVA", "SEGREDO-ADICIONALIDADE", "SEGREDO-CONTRAFACTUAL"):
            self.assertNotIn(segredo, corpo, "a rota de equidade vazou a narrativa para terceiro")

    def test_need_without_a_source_weighs_less_than_need_with_a_source(self):
        with app_tx(self.funder, readonly=True) as c:
            sem_fonte = c.one("SELECT need_level::float AS n FROM project_impact_context($1)",
                              self.project)["n"]
        self.assertEqual(sem_fonte, 0.4, "necessidade sem fonte não pode valer como declarada com fonte")
        self.osc.put(f"/v1/projects/{self.project}/equity/context", {
            "need_statement": "A comunidade não tem oferta pública de contraturno, conforme o "
                              "levantamento citado na fonte declarada.",
            "additionality": "Nenhuma outra organização atua no contraturno desta comunidade.",
            "need_source_name": "Levantamento da Secretaria Municipal de Educação, 2025",
            "need_source_date": "2025-03-01"})
        with app_tx(self.funder, readonly=True) as c:
            com_fonte = c.one("SELECT need_level::float AS n FROM project_impact_context($1)",
                              self.project)["n"]
        self.assertGreater(com_fonte, sem_fonte)


# ================================================================ a regra de totalidade
class TotalityRuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.osc = new_account("osc", compliance="approved")
        cls.validator = new_account("company", compliance="approved")
        grant_premium(cls.osc)

    def _project_with_measurement(self, *, denominador: int | None, medido: int) -> str:
        pid = self.osc.post("/v1/projects", {
            "title": f"Projeto de totalidade {denominador}/{medido}",
            "summary": "Projeto criado para conferir a regra de afirmação de totalidade.",
            "problem": "O problema declarado pelo projeto, com extensão suficiente para o CHECK.",
            "objectives": "Os objetivos declarados pelo projeto, com extensão suficiente.",
            "territory": "BR-MT-5105259", "causes": ["educacao"],
            "beneficiaries_count": medido, "budget_total_cents": 800_000}).json["id"]
        cat = self.osc.get("/v1/indicators/catalog?ods=4").json["items"]
        ind = next(i for i in cat if i["code"] == "trained_people")
        pi = self.osc.post(f"/v1/projects/{pid}/indicators", {
            "indicator_id": ind["id"], "baseline": 0,
            "baseline_source": "Lista de presença do primeiro encontro", "target": 100}).json["id"]
        ev = self.osc.post(f"/v1/projects/{pid}/evidences", {
            "kind": "attendance", "title": "Lista de presença"}).json["id"]
        oc = owner_conn()
        oc.run("UPDATE evidences SET status = 'accepted' WHERE id = $1", ev)
        oc.run("INSERT INTO indicator_values(project_indicator_id, project_id, org_id, value,"
               " measured_on, evidence_id, status, validated_by, validated_by_org)"
               " VALUES ($1,$2,$3,$4,current_date,$5,'validated',"
               " (SELECT id FROM users LIMIT 1), $6)",
               pi, pid, self.osc.org_id, medido, ev, self.validator.org_id)
        if denominador is not None:
            self.osc.post("/v1/equity/denominators", {
                "project_id": pid, "kind": "eligible_population", "value": denominador,
                "unit": "pessoas", "reference_date": "2025-01-01",
                "source_name": "Censo escolar municipal 2024", "source_date": "2025-03-01",
                "method_note": "Matriculados na faixa atendida, conforme censo escolar."})
        return pid

    def _check(self, pid: str, texto: str) -> dict:
        cid = self.osc.post("/v1/claims", {
            "subject_type": "project", "subject_id": pid, "claim_kind": "result",
            "statement": texto}).json["id"]
        out = self.osc.post(f"/v1/claims/{cid}/check", {}).json
        return next(c for c in out["checks"]
                    if c["rule_code"] == "totality_claim_without_coverage") | {"status": out["status"]}

    def test_eradication_with_partial_coverage_is_serious(self):
        """O achado: 32 de 60 elegíveis não é erradicação, e uma medição validada não basta."""
        pid = self._project_with_measurement(denominador=60, medido=32)
        r = self._check(pid, "Erradicamos a defasagem de leitura na comunidade atendida.")
        self.assertFalse(r["passed"])
        self.assertEqual(r["severity"], "serious")
        self.assertIn("53%", r["detail"])
        self.assertEqual(r["status"], "flagged")

    def test_eradication_without_a_denominator_cannot_even_be_checked(self):
        pid = self._project_with_measurement(denominador=None, medido=50)
        r = self._check(pid, "Zero casos de defasagem: universalizamos a leitura na turma.")
        self.assertFalse(r["passed"])
        self.assertIn("não há denominador", r["detail"])

    def test_full_coverage_passes_because_the_division_sustains_the_sentence(self):
        pid = self._project_with_measurement(denominador=50, medido=50)
        r = self._check(pid, "Atendemos toda a população elegível: cobertura total da turma.")
        self.assertTrue(r["passed"], r["detail"])
        self.assertIn("100%", r["detail"])

    def test_a_sentence_without_totality_terms_is_not_touched_by_this_rule(self):
        pid = self._project_with_measurement(denominador=60, medido=32)
        r = self._check(pid, "Atendemos 32 pessoas em oficinas de leitura, conforme medição.")
        self.assertTrue(r["passed"])
        self.assertIn("não afirma totalidade", r["detail"])

    def test_the_lexicon_of_totality_is_public_like_the_others(self):
        lex = self.osc.get("/v1/claims/rules").json["lexicons"]
        self.assertIn("totality", lex)
        for termo in ("100%", "erradicamos", "neutro", "cobertura total"):
            self.assertIn(termo, lex["totality"])
        self.assertNotIn("erradicamos", lex["absolute"],
                         "termo de totalidade não pode continuar na lista de prova")


# ================================================================ dependências
class DependencyControlTests(unittest.TestCase):
    """O que é verificável SEM registry. A auditoria de CVE está bloqueada e é declarada como tal."""

    def test_every_runtime_dependency_is_pinned_to_an_exact_version(self):
        req = (RAIZ / "backend" / "requirements.txt").read_text(encoding="utf-8")
        linhas = [l.strip() for l in req.splitlines()
                  if l.strip() and not l.strip().startswith("#")]
        self.assertTrue(linhas)
        soltas = [l for l in linhas if "==" not in l]
        self.assertEqual(soltas, [], f"dependência de execução sem versão exata: {soltas}")

    def test_the_installed_web_dependencies_are_pinned_and_match_what_is_installed(self):
        """Do que está instalado, exigimos versão exata E igual à instalada.

        Para o que está declarado e NUNCA foi instalado (os registries não respondem neste
        ambiente), exigir versão exata seria fixar um número que ninguém baixou. Esse caso é
        coberto pelo teste seguinte, que exige a declaração honesta de NOT VERIFIED.
        """
        pkg = json.loads((RAIZ / "web" / "package.json").read_text(encoding="utf-8"))
        declaradas = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
        problemas = []
        for nome, faixa in declaradas.items():
            manifesto = RAIZ / "web" / "node_modules" / nome / "package.json"
            if not manifesto.exists():
                continue
            instalada = json.loads(manifesto.read_text(encoding="utf-8"))["version"]
            if re.match(r"^[\^~>=<]", faixa):
                problemas.append(f"{nome}: instalada {instalada}, declarada em faixa {faixa}")
            elif faixa != instalada:
                problemas.append(f"{nome}: instalada {instalada} ≠ declarada {faixa}")
        self.assertEqual(problemas, [], f"fixação de dependência web inconsistente: {problemas}")

    def test_what_was_never_installed_is_declared_as_not_verified(self):
        pkg = json.loads((RAIZ / "web" / "package.json").read_text(encoding="utf-8"))
        declaradas = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
        doc = (RAIZ / "THIRD_PARTY_DEPENDENCIES.md").read_text(encoding="utf-8")
        ausentes = [n for n in declaradas
                    if not (RAIZ / "web" / "node_modules" / n / "package.json").exists()]
        self.assertTrue(ausentes, "o cenário mudou: tudo está instalado, reveja este teste")
        self.assertIn("NOT VERIFIED", doc)
        for nome in ausentes:
            raiz_pacote = nome.split("/")[0]
            self.assertIn(raiz_pacote, doc,
                          f"{nome} está declarado no package.json e não aparece no inventário")

    def test_the_inventory_declares_every_runtime_dependency(self):
        doc = (RAIZ / "THIRD_PARTY_DEPENDENCIES.md").read_text(encoding="utf-8")
        nomes = []
        for arquivo in ("requirements.txt", "requirements-optional.txt"):
            texto = (RAIZ / "backend" / arquivo).read_text(encoding="utf-8")
            nomes += [l.split("==")[0].strip() for l in texto.splitlines()
                      if "==" in l and not l.strip().startswith("#")]
        faltando = [n for n in nomes if n.lower() not in doc.lower()]
        self.assertEqual(faltando, [], f"dependência sem inventário declarado: {faltando}")

    def test_the_blocked_audit_is_declared_as_blocked_and_not_as_clean(self):
        """A regra do pedido: "não consegui executar" nunca é "sem vulnerabilidades"."""
        doc = (RAIZ / "SECURITY_AUDIT.md").read_text(encoding="utf-8")
        self.assertIn("BLOCKED BY ENVIRONMENT", doc)
        self.assertIn("npm audit", doc)
        self.assertIn("pip-audit", doc)
        proibido = re.search(r"(sem vulnerabilidades|nenhuma vulnerabilidade)[^.]{0,80}\.", doc,
                             re.IGNORECASE)
        if proibido:
            self.assertIn("não", proibido.group(0).lower(),
                          f"o documento afirma ausência de vulnerabilidade: {proibido.group(0)}")

    def test_no_runtime_dependency_was_added_without_being_declared(self):
        """Dependência nova sem inventário é a forma mais fácil de crescer a superfície de ataque."""
        import importlib.metadata as md
        req = (RAIZ / "backend" / "requirements.txt").read_text(encoding="utf-8")
        opc = (RAIZ / "backend" / "requirements-optional.txt").read_text(encoding="utf-8")
        dev = (RAIZ / "backend" / "requirements-dev.txt").read_text(encoding="utf-8")
        declaradas = {l.split("==")[0].strip().lower().replace("-", "_")
                      for texto in (req, opc, dev) for l in texto.splitlines()
                      if "==" in l and not l.strip().startswith("#")}
        # o que o código realmente importa, no topo dos módulos do produto
        importados = set()
        for py in (RAIZ / "backend" / "impacto").rglob("*.py"):
            for m in re.finditer(r"^\s*(?:from|import)\s+([a-zA-Z_][\w]*)", py.read_text(
                    encoding="utf-8"), re.MULTILINE):
                importados.add(m.group(1).lower())
        terceiros = []
        for nome in importados:
            if nome in ("impacto", "tests"):
                continue
            try:
                dist = md.distribution(nome)
            except Exception:  # noqa: BLE001, S112 — módulo da biblioteca padrão ou import relativo
                continue  # noqa: S112
            canonico = (dist.metadata["Name"] or nome).lower().replace("-", "_")
            if canonico not in declaradas and canonico not in ("pip", "setuptools", "wheel"):
                terceiros.append(canonico)
        self.assertEqual(sorted(set(terceiros)), [],
                         f"pacote de terceiro importado e não declarado: {sorted(set(terceiros))}")
