"""v0.17.0 — os documentos afirmam números e chaves; aqui eles são conferidos contra o banco.

Documento com número errado é pior que documento sem número: dá a impressão de auditoria. Esta rodada
já corrigiu três afirmações falsas minhas descobertas por leitura (a tabela de regras de monetização
com chaves inventadas entre elas), então a conferência passou a ser automática.
"""
from __future__ import annotations

import pathlib
import re
import unittest

from tests.support import db_system

ROOT = pathlib.Path(__file__).resolve().parents[2]


def doc(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


class MonetizationDocTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with db_system() as c:
            cls.rules = c.query("SELECT key, revenue_engine, legal_status, active"
                                " FROM monetization_rules ORDER BY engine_rank, key")
            cls.cards = c.query("SELECT rule_key, status FROM monetization_legal_cards")

    def test_every_rule_key_in_the_document_exists_in_the_database(self):
        text = doc("MONETIZATION.md")
        keys = set(re.findall(r"`([a-z_]+\.[a-z_.]+)`", text))
        real = {r["key"] for r in self.rules}
        invented = {k for k in keys if "." in k and k.count(".") <= 2
                    and k not in real and not k.endswith(".md")
                    and k.split(".")[0] in {"saas", "b2g", "enterprise", "implementation",
                                            "marketplace", "success_fee", "premium", "data",
                                            "certification"}}
        self.assertEqual(invented, set(),
                         f"o documento cita chave de regra que não existe: {invented}")

    def test_the_table_in_the_document_has_one_line_per_rule(self):
        """Conta as LINHAS da tabela, não a palavra: "nove" e "9" dizem a mesma coisa."""
        text = doc("MONETIZATION.md")
        lines = re.findall(r"^\| \d \| `([a-z0-9_.]+)` \|", text, re.MULTILINE)
        self.assertEqual(sorted(lines), sorted(r["key"] for r in self.rules),
                         "a tabela do documento e as regras do banco discordam")

    def test_no_legal_card_is_green(self):
        green = [c["rule_key"] for c in self.cards if c["status"] == "green"]
        self.assertEqual(green, [], f"cartão legal verde: todo documento desta rodada afirma que não "
                                    f"há nenhum e precisa ser reescrito antes de qualquer entrega "
                                    f"({green})")
        self.assertIn("Zero verdes", doc("MONETIZATION.md"))

    def test_no_rule_is_active(self):
        """Se uma regra ficar ativa, a frase "nenhuma está ativa" dos documentos fica falsa."""
        active = [r["key"] for r in self.rules if r["active"]]
        self.assertEqual(active, [], f"regra ativa sem o documento dizer: {active}")

    def test_the_refused_ones_are_the_four_the_documents_name(self):
        refused = {r["key"] for r in self.rules if r["legal_status"] == "refused"}
        self.assertEqual(refused, {"b2g.territorial_governance", "marketplace.take_rate",
                                   "success_fee.funding", "data.territorial_intelligence"})
        for key in refused:
            self.assertIn(key, doc("MONETIZATION.md"),
                          f"receita recusada ausente do documento: {key}")


class LegalDocTests(unittest.TestCase):
    def test_the_framework_lists_exactly_the_registered_documents(self):
        with db_system() as c:
            keys = {r["doc_key"] for r in c.query("SELECT DISTINCT doc_key FROM legal_documents")}
        text = doc("docs/LEGAL_FRAMEWORK.md")
        # Só a tabela do §1 (a que tem a coluna "Exige aceite"), não qualquer célula do documento: a
        # tabela de campos da prova de aceite também casa com o padrão e trouxe `body_sha256`.
        bloco = text[text.index("| Chave | Documento |"):text.index("## 2.")]
        cited = set(re.findall(r"\| `([a-z0-9_]+)` \|", bloco))
        self.assertEqual(cited, keys, "o arcabouço legal e o banco discordam sobre quais documentos há")

    def test_the_framework_does_not_claim_any_document_is_in_force(self):
        with db_system() as c:
            approved = c.scalar("SELECT count(*) FROM legal_documents WHERE status = 'approved'")
        self.assertEqual(approved, 0,
                         "há documento aprovado: docs/LEGAL_FRAMEWORK.md afirma que não há e precisa "
                         "ser reescrito antes de qualquer entrega")
        self.assertIn("nenhum aceite é registrável", doc("docs/LEGAL_FRAMEWORK.md"))


class ProgramDocTests(unittest.TestCase):
    def test_the_document_states_the_real_number_of_status_edges(self):
        """Dizia 12; são 11. Número errado em documento é o defeito que não quebra nada e mente."""
        with db_system() as c:
            n = c.scalar("SELECT count(*) FROM program_status_graph")
        self.assertIn(f"{n} arestas", doc("PROGRAM_ARCHITECTURE.md"))
        self.assertIn(f"{n} arestas", doc("DATABASE_SCHEMA.md"))

    def test_the_document_lists_the_real_project_roles(self):
        from impacto.economics.programs import PROJECT_ROLES
        text = doc("PROGRAM_ARCHITECTURE.md")
        for role in PROJECT_ROLES:
            self.assertIn(f"`{role}`", text, f"papel de carteira ausente do documento: {role}")


class PaymentDocTests(unittest.TestCase):
    def test_the_document_and_the_code_agree_on_which_providers_are_real(self):
        from impacto.economics.payments import REAL_PROVIDERS
        text = doc("PAYMENT_ARCHITECTURE.md")
        for provider in REAL_PROVIDERS:
            self.assertIn(f"`'{provider}'`", text,
                          f"provedor real {provider} não está declarado no documento")

    def test_the_document_states_the_real_number_of_graph_edges(self):
        with db_system() as c:
            n = c.scalar("SELECT count(*) FROM charge_state_graph")
        self.assertIn(f"{n} arestas", doc("PAYMENT_ARCHITECTURE.md"))

    def test_the_banner_is_in_the_document_because_it_is_in_the_code(self):
        from impacto.economics.payments import NOT_CONFIGURED
        self.assertIn(NOT_CONFIGURED, doc("PAYMENT_ARCHITECTURE.md"))


class ValueLedgerDocTests(unittest.TestCase):
    def test_the_document_lists_every_value_event_type(self):
        with db_system() as c:
            keys = {r["key"] for r in c.query("SELECT key FROM value_event_types")}
        text = doc("VALUE_LEDGER.md")
        missing = {k for k in keys if f"`{k}`" not in text}
        self.assertEqual(missing, set(), f"tipo de evento de valor ausente do documento: {missing}")
        self.assertIn(f"{len(keys)} tipos" if len(keys) != 11 else "onze tipos", text)

    def test_no_shipped_baseline_carries_a_number(self):
        """A afirmação é sobre a INSTALAÇÃO, e é mais fina do que "a tabela está vazia".

        Duas versões anteriores deste par teste+documento estavam erradas. A primeira contava linhas no
        banco de teste e falhava, porque as suítes de valor declaram linhas de base de propósito. A
        segunda procurava INSERT na migração e descobriu que a 0019 **semeia** uma linha por tipo de
        evento — todas com `minutes_per_unit` NULO, para que a ausência do número seja visível. O
        documento foi corrigido para dizer exatamente isso, e o teste passou a conferir o que importa:
        nenhuma linha semeada traz número.
        """
        mig = (ROOT / "backend" / "migrations" / "0019_v0170_value_ledger.sql").read_text()
        seed = mig[mig.index("INSERT INTO value_baselines"):]
        seed = seed[:seed.index(";")]
        self.assertIn("method_note", seed)
        self.assertNotIn("minutes_per_unit", seed,
                         "a migração passou a semear linha de base COM número: os documentos afirmam "
                         "que nenhuma estimativa é produzida de fábrica")
        for sql in (ROOT / "backend" / "migrations").glob("*.sql"):
            self.assertNotIn("INSERT INTO ai_price_table", sql.read_text(encoding="utf-8"),
                             f"{sql.name} semeia preço de IA: nenhum preço de provedor foi inventado")

    def test_the_documents_say_without_a_number_not_without_a_row(self):
        for name in ("VALUE_LEDGER.md", "ECONOMICS.md"):
            text = doc(name)
            self.assertNotIn("linhas de base nasce vazia", text, f"{name}: afirmação imprecisa")
            self.assertIn("minutes_per_unit", text,
                          f"{name} precisa dizer que o que nasce nulo é o número, não a linha")



class ApiDocTests(unittest.TestCase):
    """Cada rota citada no documento da API tem de existir no roteador.

    Este teste nasceu pegando um erro meu: o documento citava
    `/v1/admin/monetization/billable/{billable_seq}/waive`, e o caminho real é
    `/v1/admin/monetization/pipeline/{billable_seq}/waive`. Caminho errado em documentação de API é
    defeito entregue: quem integra tenta, recebe 404 e não sabe se o erro é dele.
    """

    def test_every_route_cited_in_the_v0170_section_exists(self):
        from impacto import api
        from impacto.http import ROUTES
        api.load_all()
        paths = {r.path for r in ROUTES}
        text = doc("API_DOCUMENTATION.md")
        section = text[text.index("## Camada econômica"):text.index("## Rede de impacto")]
        cited = set(re.findall(r"`(?:GET|POST|PUT|PATCH|DELETE)(?:·(?:GET|POST|PUT|PATCH|DELETE))* "
                               r"(/v1/[^`]+)`", section))
        self.assertGreater(len(cited), 30, "a varredura não achou as rotas: o padrão mudou?")
        missing = sorted(p for p in cited if p not in paths)
        self.assertEqual(missing, [], f"o documento cita rota que não existe: {missing}")

    def test_the_section_covers_the_new_route_groups(self):
        text = doc("API_DOCUMENTATION.md")
        section = text[text.index("## Camada econômica"):text.index("## Rede de impacto")]
        for prefix in ("/v1/programs", "/v1/value/", "/v1/payments/", "/v1/legal/", "/v1/engines",
                       "/v1/monetization/"):
            self.assertIn(prefix, section, f"grupo de rotas ausente do documento: {prefix}")

if __name__ == "__main__":
    unittest.main()
