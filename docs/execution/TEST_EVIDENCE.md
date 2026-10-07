# EVIDÊNCIA DE TESTE — v0.23.0

Toda linha abaixo corresponde a uma execução real nesta rodada, com o comando que a produziu. Nenhum
número é estimado. Onde um teste não pôde rodar, está dito — não convertido em `PASS`.

**Ambiente da execução:** PostgreSQL 16.15 · Python 3.13.16 · Node com TypeScript 6.0.3 e esbuild
0.28.2 · Chromium (Playwright) presente · registry npm responde 403 · índice PyPI indisponível.

---

## Regressão completa

```
cd backend && TEST_ADMIN_DATABASE_URL=... PASSWORD_SCRYPT_N=16384 \
  RATE_LIMIT_MULTIPLIER=1000 LOG_LEVEL=ERROR python3 -m unittest discover -s tests -t .
```

| | |
|---|---|
| **Testes executados** | **2.184** |
| **Falhas** | **0** |
| **Erros** | **0** |
| Ignorados | 26 — os testes de volume, que rodam em passo próprio (`PERF=1`); executados à parte, ver abaixo |
| Duração | 585 s |

### As cinco falhas da primeira execução, e o que cada uma era

A primeira execução completa desta rodada teve 5 falhas. **Nenhuma era defeito do produto**, e
nenhuma foi resolvida enfraquecendo teste.

| Falha | Causa | Correção |
|---|---|---|
| `test_the_ledger_chain_verifies_for_every_project` | `test_ledger_tampering_is_detected` forja um ledger com privilégio de DBA para provar a detecção, e deixava a forja no banco | captura o valor original e restaura em `addCleanup` |
| `test_the_audit_chain_verifies_for_every_organization...` | dois testes do motor de auditoria forjam a cadeia (`after_state`, `correlation_id`) pelo mesmo motivo | idem, nos dois |
| `test_the_repository_carries_no_secret` | o controle negativo escrevia chave da AWS, token do GitHub, chave do Stripe e bloco PEM como **literais** neste repositório; a varredura acusou o próprio arquivo que a verifica | amostras passam a ser montadas em pedaços; isentar o arquivo abriria um buraco permanente num teste de segurança |
| `test_no_secrets_committed` | mesma causa | mesma correção |
| `test_every_tracked_file_is_either_in_the_manifest...` | 20 arquivos novos desta rodada ainda não estavam no manifesto | manifesto regenerado no empacotamento |

---

## Por portão

| Gate | Comando | Testes | Resultado |
|---|---|---|---|
| 2 · Release | `python3 -m unittest tests.test_v0230_release_gate` | 13 | **OK** |
| 3 · API | `… tests.test_v0230_authorization_matrix` | 33 | **OK** |
| 3-9 · Matrizes | `… tests.test_v0230_execution_matrices` | 14 | **OK** |
| 5 · Segurança (novos) | `… tests.test_v0230_security_gate` | 26 | **OK** |
| 5 · Segurança (existentes) | `… tests.test_security_tenancy tests.test_v0120_hardening tests.test_v0150_security tests.test_v0170_security tests.test_v0180_security tests.test_v0181_hardening tests.test_v0230_session_hardening tests.test_impact_core_hardening` | 139 | **OK** |
| 6 · Dados/Infra | `… tests.test_v0230_data_infra_gate` | 16 | **OK** |
| 6 · Observabilidade | `… tests.test_v0230_observability_gate` | 22 | **OK** |
| 7 · Integrações | `… tests.test_v0130_integrations tests.test_v0220_financial_engine` | 129 | **OK** |
| 8 · Frente | `… tests.test_v0230_frontend_gate` | 10 | **OK** |
| 9 · Jornadas (todas) | `… discover -p "test_e2e_*.py"` | 91 | **OK** |
| 9 · Travessia nova | `… tests.test_e2e_v0230_moderation_journey` | 3 | **OK** |

**Novos nesta rodada: 115 testes**, todos executados e verdes.

---

## Desempenho

Executado nas duas escalas que a suíte oferece.

### Escala cheia (`PERF_FULL=1`) — 10.000 soluções, 100.000 documentos, 100.000 avaliações

```
cd backend && PERF_FULL=1 … python3 -m unittest discover -s tests -t . -p "test_v0150_performance.py"
```

**17 testes, OK.** Volume criado em **1.072 s**. Orçamento declarado: **2.500 ms por consulta**.

| Consulta | ms | | Consulta | ms |
|---|---|---|---|---|
| feed do financiador | **1.552** | | propostas | 70 |
| projetos (100 por página) | **1.361** | | registro legal | 36 |
| projetos (5 por página) | **1.307** | | feed de programas | 32 |
| área da OSC | 329 | | marketplace público | 15 |
| área do investidor | 72 | | grafo (2 níveis) | 13 |
| linha do tempo | 9 | | relações | 9 |
| prontidão | 8 | | prontidão por finalidade | 8 |
| resumo de valor | 8 | | documentos | 7 |
| cobranças | 6 | | funções de catálogo (5) | 1–6 |

Todas abaixo do orçamento. A mais lenta (feed do financiador, 1.552 ms) usa 62% dele.

Um teste confere ainda que **a lista não cresce linearmente com o tamanho da página**: uma página
20× maior não pode custar mais de 8× — é o indício de consulta por linha.

### A primeira execução em escala cheia media 401, não consulta

Vale registrar porque o engano era convincente. Antes da correção descrita em `IMPLEMENTATION_LOG.md`,
a execução em escala cheia imprimia números **melhores** que a escala reduzida: feed do financiador
6 ms, projetos (100) 5 ms. Pareciam excelentes.

Eram respostas **401**. A construção do volume cheio leva ~1.072 s e `access_token_ttl` é 900 s: a
sessão do arranjo morria durante a própria preparação, e o que estava sendo cronometrado era o tempo
de o servidor recusar uma sessão expirada. Depois da correção, os números verdadeiros são os da
tabela acima — três deles acima de um segundo.

### Escala reduzida (`PERF=1`)

**17 testes, OK**, volume em 1,6 s. Serve para a suíte rodar rápido; **não** serve para afirmar
desempenho, e os números divergem dos de escala cheia nos dois sentidos, porque com estatísticas
reais o planejador usa índices onde antes varria sequencialmente.

A suíte **declara quando a escala não conclui**: imprimiu *"inconclusivo nesta escala: aceites do
titular (legal_acceptances com menos de 500 linhas)"* em vez de dar o item por verificado — e um
teste recusa a escala baixa demais para conferir algo de verdade.

---

## Verificações executadas fora da suíte

| Verificação | Comando | Resultado |
|---|---|---|
| Lint / **SAST** (regras `S` = flake8-bandit) | `ruff check impacto tests` | **limpo** |
| **Varredura de segredo** | `python3 scripts/secrets_scan.py` | **0 achados** em 737 arquivos rastreados |
| …e seu **controle negativo** | teste planta 4 segredos reais | **4 de 4 acusados** |
| Typecheck da frente | `tsc -p tsconfig.offline.json --noEmit` | **0 erros** |
| Build da frente | `node build.mjs` | 972,6 kB JS · 33,3 kB CSS · 203 ms |
| Documentação da API | `python3 ../scripts/gen_api_docs.py` | 888 operações |
| Cobertura de motores | `python3 ../scripts/make_engine_coverage.py` | 39 com segurança · 34 com observabilidade |
| Glossário | `python3 scripts/sync_glossary.py` | 123 termos, 23 domínios |
| **Migração do zero** | `python3 -m impacto.db.migrate` em banco novo | 62 migrações · 322 tabelas · 321 com RLS · 667 políticas · 0 com `FORCE RLS` |
| Migração incremental | reexecução | inócua: 62 antes, 62 depois |
| Semente | `python3 -m impacto.cli seed-demo` | 14 usuários |
| **Backup** | `scripts/backup.sh` | 2,1 MB de um banco de 32 MB em **515 ms** |
| **Restauração em banco limpo** | `scripts/restore_test.sh` | **OK** em **5,68 s**, com sha256, cadeias de hash e 15 invariantes de estado |
| …e seu **controle negativo** | dump adulterado em 1 byte | **recusado**, código de saída 1, nenhum banco criado |
| Integridade do banco | `scripts/db_integrity_report.py` | 1.550 CHECK · 426 UNIQUE · 926 índices · 0 órfãos · 0 deriva de catálogo |
| Manifesto da versão | `scripts/make_version_manifest.py` | 1.802 arquivos, 28 categorias, 32,24 MB |

---

## O que NÃO foi executado

| Verificação | Por quê | Estado |
|---|---|---|
| **SCA** (`pip-audit`, `npm audit`) | nenhuma base de vulnerabilidade alcançável: ferramentas ausentes, PyPI indisponível, GraphQL do GitHub recusado, `/advisories` recusado | **BLOCKED** · D-SUP2 |
| `npm ci` / typecheck pelo `tsconfig.json` oficial | registry npm 403; sem `@types/react` | **BLOCKED** · D-SUP1 |
| Homologação de integração (`sandbox`, `homologated`) | exige credencial real de fornecedor; simular é proibido pela regra permanente | **BLOCKED** · D-INT1..14 |
| `axe-core` | registry npm 403 | **BLOCKED** |
| Leitor de tela real, segundo navegador, zoom 200%, daltonismo, navegação por voz | exigem dispositivo, sistema operacional ou operação manual | **BLOCKED** |
| Teste de intrusão por terceiro | exige contratação; nenhum teste automatizado substitui | **BLOCKED** |
