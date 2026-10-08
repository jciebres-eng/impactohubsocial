"""As quatro matrizes obrigatórias não podem derivar do código, nem inventar estado.

O QUE UMA MATRIZ EM CSV VALE SEM ESTE ARQUIVO

Nada. Um CSV gerado uma vez e versionado é uma FOTOGRAFIA: no dia em que alguém adiciona uma rota, a
matriz continua dizendo 888 operações e continua parecendo completa. Foi assim que a divergência de
versão (0.14.0 em dois arquivos contra 0.23.0 no VERSION) sobreviveu nove versões sem ninguém notar.

Então aqui a matriz é tratada como código: o gerador roda num diretório temporário e o resultado é
comparado byte a byte com o que está versionado. Se divergir, a suíte reprova e diz qual matriz
regerar. É a mesma trava que `docs/openapi.json` já tinha.

E MAIS TRÊS COISAS QUE O CSV PODERIA MENTIR

* campo faltando — o pacote de execução declara os campos obrigatórios de cada matriz, e um campo
  ausente torna a matriz inútil para quem audita. O conjunto exigido está escrito aqui, verbatim.
* estado inventado — só os nove estados do pacote valem. `PASS (rota)` e `OK` não são estados.
* `OPEN` — a regra do pacote é que pendência não existe em release final. A conferência é do VALOR
  da célula, não de substring: um motor cuja descrição diz "ausência de regra produz PENDENTE, nunca
  'elegível'" está DESCREVENDO comportamento correto do produto, e a primeira versão deste teste
  reprovou essa frase. Pendência é a célula que VALE `OPEN`/`PENDENTE`, não a que fala sobre isso.
* `BLOCKED` sem bloqueio declarado — um bloqueio que não está em `BLOCKERS.md` é uma pendência
  disfarçada de bloqueio. Toda linha `BLOCKED` exige o arquivo e a causa escrita nele.
"""
from __future__ import annotations

import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.support import ROOT

EXEC = ROOT / "docs" / "execution"

#: Estados permitidos, verbatim de `EXECUTION_MATRICES.md` do pacote de execução.
ESTADOS = {"TODO", "IN_PROGRESS", "BLOCKED", "FAILED", "FIXED", "PASS", "REGRESSION", "DONE", "WAIVED"}

#: (arquivo, gerador, campos obrigatórios) — os campos saem verbatim de `EXECUTION_MATRICES.md`.
#: A matriz pode ter MAIS colunas que isso; não pode ter menos.
MATRIZES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("API_AUTHORIZATION_MATRIX.csv", "make_authorization_matrix.py",
     ("operation_id", "method", "path", "anonymous", "authenticated", "viewer", "member", "owner",
      "tenant_admin", "global_admin", "mfa_required", "cross_tenant", "invalid_payload", "not_found",
      "rate_limit", "audit", "ledger_effect", "expected", "observed", "status", "evidence")),
    ("ENGINE_VALIDATION_MATRIX.csv", "make_engine_matrix.py",
     ("engine_key", "engine_name", "type", "routes", "min_input", "expected_output",
      "missing_data_behavior", "human_review", "fallback", "security_test", "regression_test",
      "evidence", "status")),
    ("INTEGRATION_HOMOLOGATION_MATRIX.csv", "make_integration_matrix.py",
     ("provider", "capability", "state", "credentials", "contract_test", "sandbox_test",
      "negative_test", "idempotency", "webhook", "security", "observability", "recovery",
      "evidence", "status")),
    ("PERSONA_E2E_MATRIX.csv", "make_persona_matrix.py",
     ("persona", "journey", "step", "expected", "observed", "authorization", "audit", "evidence",
      "status")),
)

#: Estados de integração do pacote. `production_active` exige evidência real e NÃO pode aparecer aqui.
ESTADOS_DE_INTEGRACAO = {"scaffolded", "contract_tested", "sandbox", "homologated", "production_active"}


def _linhas(nome: str) -> list[dict[str, str]]:
    with (EXEC / nome).open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


class TheFourMandatoryMatricesExistAndCarryTheRequiredFieldsTests(unittest.TestCase):
    def test_each_matrix_exists_and_is_not_empty(self):
        for nome, _, _ in MATRIZES:
            with self.subTest(nome):
                caminho = EXEC / nome
                self.assertTrue(caminho.exists(), f"{nome} não existe em docs/execution/")
                self.assertTrue(_linhas(nome), f"{nome} não tem linha alguma")

    def test_no_required_field_is_missing(self):
        for nome, _, exigidos in MATRIZES:
            with self.subTest(nome):
                cabecalho = set(_linhas(nome)[0])
                faltando = [c for c in exigidos if c not in cabecalho]
                self.assertEqual(faltando, [], f"{nome} não declara {faltando}")


class OnlyTheNineDeclaredStatesAreUsedTests(unittest.TestCase):
    def test_every_status_is_one_of_the_nine(self):
        for nome, _, _ in MATRIZES:
            for i, linha in enumerate(_linhas(nome), start=2):
                with self.subTest(nome=nome, linha=i):
                    self.assertIn(linha["status"], ESTADOS,
                                  f"{nome}:{i} usa estado fora do vocabulário do pacote")

    def test_no_cell_is_open_or_pendente(self):
        """A regra do pacote: pendência não pode existir no release final."""
        proibidos = {"OPEN", "PENDENTE", "PENDENCIA", "PENDÊNCIA", "ABERTO", "TBD", "???"}
        for nome, _, _ in MATRIZES:
            for i, linha in enumerate(_linhas(nome), start=2):
                for campo, valor in linha.items():
                    with self.subTest(nome=nome, linha=i, campo=campo):
                        self.assertNotIn((valor or "").strip().upper(), proibidos,
                                         f"{nome}:{i} campo {campo}: {valor!r}")

    def test_no_integration_claims_production_active(self):
        """`production_active` sem evidência real é vedado pelo pacote — e não há evidência real."""
        for linha in _linhas("INTEGRATION_HOMOLOGATION_MATRIX.csv"):
            self.assertIn(linha["state"], ESTADOS_DE_INTEGRACAO, linha["provider"])
            self.assertNotEqual(linha["state"], "production_active",
                                f"{linha['provider']} declara produção ativa sem homologação real")

    def test_no_provider_ships_above_contract_tested(self):
        """A trava na FONTE, não só na matriz.

        `maturity` é promovível pela administração, e um teste de integração promove `totvs` a
        `homologated` no meio da suíte. A matriz passou a ler o catálogo de produto
        (`config/integration_providers.json`) exatamente por isso — e aqui se confere que o catálogo
        EMBARCADO não declara homologação que nunca houve. Promover no arquivo exige evidência
        externa real, e é o que esta asserção obriga alguém a enfrentar.
        """
        import json
        catalogo = json.loads((ROOT / "config" / "integration_providers.json").read_text(encoding="utf-8"))
        for prov in catalogo["providers"]:
            with self.subTest(prov["key"]):
                self.assertIn(prov["maturity"], ("scaffolded", "contract_tested"),
                              f"{prov['key']} embarca como {prov['maturity']}: homologação declarada "
                              "no catálogo exige evidência externa real anexada ao release")

    def test_every_blocked_row_has_a_written_blocker(self):
        bloqueadas = [(n, l) for n, _, _ in MATRIZES for l in _linhas(n) if l["status"] == "BLOCKED"]
        if not bloqueadas:
            return
        arquivo = EXEC / "BLOCKERS.md"
        self.assertTrue(arquivo.exists(),
                        f"{len(bloqueadas)} linhas BLOCKED e nenhum BLOCKERS.md: bloqueio sem causa "
                        "escrita é pendência disfarçada")
        texto = arquivo.read_text(encoding="utf-8")
        for termo in ("Causa:", "Quem desbloqueia:", "Risco de seguir sem ele:"):
            self.assertIn(termo, texto, f"BLOCKERS.md não declara '{termo}'")
        # Cada matriz com linha BLOCKED precisa ser nomeada no documento.
        for nome in {n for n, _ in bloqueadas}:
            self.assertIn(nome, texto, f"BLOCKERS.md não explica os bloqueios de {nome}")


class TheMatricesStillAgreeWithTheCodeTests(unittest.TestCase):
    """A trava que impede a fotografia: regerar e comparar.

    O gerador escreve num diretório temporário — a suíte NUNCA reescreve arquivo do repositório, para
    que rodar os testes não possa ser confundido com corrigir a matriz.
    """

    def _regera(self, gerador: str) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            saida = Path(tmp) / "m.csv"
            r = subprocess.run([sys.executable, str(ROOT / "scripts" / gerador), str(saida)],
                               capture_output=True, text=True, cwd=ROOT / "backend", timeout=300)
            self.assertEqual(r.returncode, 0, f"{gerador} falhou:\n{r.stderr[-2000:]}")
            return saida.read_text(encoding="utf-8")

    def test_regenerating_each_matrix_reproduces_what_is_committed(self):
        for nome, gerador, _ in MATRIZES:
            with self.subTest(nome):
                versionado = (EXEC / nome).read_text(encoding="utf-8")
                self.assertEqual(self._regera(gerador), versionado,
                                 f"{nome} divergiu do código. Regere com: "
                                 f"python3 scripts/{gerador}")

    def test_the_authorization_matrix_covers_every_route_the_router_serves(self):
        from impacto import api
        from impacto.http import ROUTES
        api.load_all()  # as rotas se registram no import de cada módulo; sem isto, ROUTES está vazia
        linhas = _linhas("API_AUTHORIZATION_MATRIX.csv")
        self.assertEqual(len(linhas), len(ROUTES),
                         f"a matriz tem {len(linhas)} operações e o roteador serve {len(ROUTES)}")
        do_codigo = {(r.method, r.path) for r in ROUTES}
        da_matriz = {(l["method"], l["path"]) for l in linhas}
        self.assertEqual(da_matriz, do_codigo)

    def test_the_engine_matrix_covers_every_registered_engine(self):
        from impacto.engines.registry import ENGINES
        linhas = _linhas("ENGINE_VALIDATION_MATRIX.csv")
        self.assertEqual({l["engine_key"] for l in linhas}, {e.key for e in ENGINES})

    def test_the_persona_matrix_covers_the_five_personas_the_pack_names(self):
        linhas = _linhas("PERSONA_E2E_MATRIX.csv")
        personas = {l["persona"] for l in linhas}
        self.assertEqual(len(personas), 5, f"personas declaradas: {sorted(personas)}")
        for termo in ("OSC", "Financiador", "Profissional", "Administração", "Público"):
            self.assertTrue(any(termo in p for p in personas), f"persona ausente: {termo}")
        # Toda jornada tem mais de um passo: uma "jornada" de um passo é uma rota com outro nome.
        for persona in personas:
            for jornada in {l["journey"] for l in linhas if l["persona"] == persona}:
                passos = [l for l in linhas if l["persona"] == persona and l["journey"] == jornada]
                self.assertGreater(len(passos), 1, f"{persona} · {jornada} tem um passo só")


class TheSixNamedIntegrationsAreCoveredAndInertTests(unittest.TestCase):
    """Gate 7 do pacote: Stripe, SMTP, S3, ClamAV, OIDC e APIs governamentais.

    O pacote de execução nomeia seis integrações. A matriz prova que existem e têm teste de
    contrato; o que FALTA provar é que estão DESLIGADAS — porque uma integração que sai do pacote
    apontando para um fornecedor real cobra dinheiro, manda e-mail e grava arquivo em nome de alguém,
    e ninguém pediu. Os cinco interruptores de provedor são a trava, e aqui se confere o valor de
    fábrica de cada um.
    """

    #: Interruptor → valor inerte de fábrica, e o que ele desliga.
    INERTES: tuple[tuple[str, str, str], ...] = (
        ("mail_provider", "console", "e-mail vai para o log, não para a caixa de ninguém"),
        ("storage_provider", "local", "arquivo fica em disco local, nenhum bucket de terceiro"),
        ("antivirus_provider", "none", "sem ClamAV configurado; o download de não escaneado é "
                                       "governado por allow_unscanned_downloads"),
        ("stripe_secret_key", "", "nenhuma cobrança real é possível (v0.27.0: sem assinatura; provedor derivado da chave)"),
        ("ai_provider", "local", "nenhuma chamada a modelo de terceiro"),
    )

    def test_the_pack_names_six_integrations_and_the_matrix_covers_all_six(self):
        linhas = _linhas("INTEGRATION_HOMOLOGATION_MATRIX.csv")
        for chave, nome in (("stripe", "Stripe"), ("smtp", "SMTP"), ("s3", "S3"),
                            ("clamav", "ClamAV"), ("oidc", "OIDC"),
                            ("government", "APIs governamentais")):
            with self.subTest(nome):
                casos = [r for r in linhas if chave in r["provider"]]
                self.assertTrue(casos, f"{nome} não aparece na matriz de homologação")
                for r in casos:
                    self.assertEqual(r["contract_test"], "sim",
                                     f"{r['provider']} sem teste de contrato")
                    self.assertIn("ausentes", r["credentials"],
                                  f"{r['provider']} declara credencial presente")

    def test_every_provider_switch_ships_inert(self):
        """Lê o PADRÃO da dataclass, não `load_settings()`: o que importa é o valor de fábrica, e
        exigir um banco configurado para conferir isso seria conferir o ambiente, não o produto."""
        from impacto.config import Settings
        campos = Settings.__dataclass_fields__
        for interruptor, inerte, efeito in self.INERTES:
            with self.subTest(interruptor):
                self.assertIn(interruptor, campos, f"{interruptor} não existe mais em Settings")
                self.assertEqual(campos[interruptor].default, inerte,
                                 f"{interruptor} embarca como {campos[interruptor].default!r} e não "
                                 f"como {inerte!r}; efeito do valor inerte: {efeito}")

    def test_no_credential_variable_has_a_value_in_the_repository(self):
        """A regra permanente: nenhuma senha, chave, token ou segredo em entregável.

        `scripts/secrets_scan.py` já varre o repositório inteiro; aqui a conferência é dirigida às
        variáveis que ATIVARIAM cada integração — é o caminho mais curto entre um descuido e uma
        cobrança real no cartão de alguém.
        """
        from impacto.config import Settings
        campos = Settings.__dataclass_fields__
        # `access_token_ttl` e `refresh_token_ttl` contêm "token" e NÃO são credenciais: são
        # tempos de vida, e têm valor de fábrica por obrigação. A primeira versão desta conferência
        # as acusou — o nome do campo não diz o que ele é, e casar por substring solta mede a
        # palavra em vez da coisa.
        sensiveis = [n for n in campos
                     if any(m in n for m in ("secret", "token", "key", "password", "credential"))
                     and not n.endswith(("_ttl", "_seconds", "_minutes", "_days", "_rotation"))]
        self.assertTrue(sensiveis, "nenhum campo sensível encontrado: a conferência mediria nada")
        for nome in sensiveis:
            with self.subTest(nome):
                padrao = campos[nome].default
                self.assertIn(padrao, (None, "", 0, False),
                              f"{nome} embarca com valor de fábrica {padrao!r}")
