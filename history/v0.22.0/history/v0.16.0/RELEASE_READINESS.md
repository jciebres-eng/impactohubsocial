# Prontidão da liberação — v0.16.0

Este documento responde a uma pergunta por vez, com GREEN / YELLOW / RED e o motivo. Não há "parcialmente verde".

## 1. Portões de liberação

| # | Portão | Situação | Prova |
|---|---|---|---|
| 1 | Suíte completa verde, banco criado do zero | 🟢 | **788** testes, 0 falhas, 12 pulados · `docs/evidence/test_run_v0.16.0.log` |
| 2 | Lint do backend sem apontamento | 🟢 | `ruff`, "All checks passed" · `docs/evidence/ruff_v0.16.0.log` |
| 3 | Tipos do frontend sem erro | 🟢 | `tsc --noEmit` limpo |
| 4 | Build do frontend | 🟢 | `node build.mjs` · 14 arquivos no pré-cache |
| 5 | Compilação de todo o Python | 🟢 | `python3 -m compileall impacto` |
| 6 | OpenAPI gerado do código | 🟢 | **704** operações · `docs/openapi.json` |
| 7 | Migrações só para frente, com checksum | 🟢 | **17** migrações, nenhuma liberada foi editada |
| 8 | Caminho de atualização v0.12.1 → **v0.16.0** com dado dentro | 🟢 | `test_v0150_upgrade.py` (10 testes, ampliado com as 26 estruturas novas) |
| 9 | Esquema atualizado **idêntico** ao criado do zero | 🟢 | `test_10_schema_matches_a_database_built_from_scratch` |
| 10 | RLS em toda tabela de dado de organização | 🟢 | **229 de 231** com política; exceções nomeadas |
| 11 | Matriz de isolamento A → recurso de B | 🟢 | varredura automática de todas as rotas de escrita + matriz explícita + SQL direto |
| 12 | Nenhum segredo no repositório nem no ZIP | 🟢 | teste estático + varredura no empacotador |
| 13 | Jornadas de ponta a ponta | 🟢 | 8 + **7** jornadas · `test_e2e_v0150_journeys.py`, `test_e2e_v0160_journeys.py` |
| 14 | Navegador real nas telas novas | 🟡 | 6 testes cobrem as telas da v0.15.0; **as 27 telas da v0.16.0 não têm Playwright** |
| 15 | Invariantes do produto | 🟢 | 21 + **28** testes · `test_v0150_invariants.py`, `test_v0160_invariants.py` |
| 16 | Desempenho medido com volume de alvo | 🟢 | medido; o feed é 🟡 e está declarado |
| 17 | Compatibilidade: nada que existia quebrou | 🟢 | suíte inteira anterior continua verde |
| 18 | Dependência externa ausente produz recusa explícita | 🟢 | 501/estado `unavailable`, nunca sucesso falso |
| 19 | Nenhum `TODO`/`FIXME`/`MOCK`/`STUB` no caminho de produção | 🟢 | ver §3 |
| 20 | Dado de demonstração separado de dado de produção | 🟢 | ver §4 |
| 21 | Documentação da versão completa e versionada | 🟢 | **18 documentos novos** + 15 atualizados + snapshot em `history/v0.15.0/` |
| 22 | ZIP completo, sem ZIP aninhado, validado por extração | 🟢 | `scripts/make_release.py` + `--verify` |
| 23 | **Pacote sem despejo de banco nem dado local**, garantido por teste | 🟢 | `test_architecture.ReleasePackageTests` (2 testes) |

| 24 | **SQL do código conferido por `PREPARE`** contra o esquema real | 🟢 | `scripts/sql_prepare_check.py` · 185 consultas, 0 erros |
| 25 | **Preço nunca em literal de código** | 🟢 | `test_prices_are_not_hard_coded` lê `config/plans.json` e varre backend e frontend |
| 26 | **Nenhuma rota duplicada** (a segunda ficaria inalcançável em silêncio) | 🟢 | `test_no_duplicate_routes` |
| 27 | **Todo destino de recomendação existe no roteador** | 🟢 | `test_recommendation_links_exist_in_the_app` |
| 28 | **Datas de produto em UTC**, não no fuso do processo | 🟢 | `test_product_dates_are_utc` · `backend/impacto/clock.py` |
| 29 | Backup e **teste de restauração** com ledger íntegro | 🟢 | `scripts/backup.sh` + `scripts/restore_test.sh` executados nesta rodada |
| 30 | **Nenhuma rota pública nova sem revisão** | 🟢 | `test_handlers_declare_auth` com lista de permissão explícita (7 rotas públicas novas) |

Portões 24 a 30 são desta rodada. O 24 nasceu de um achado real: a revisão de código **não** pegava nome de coluna
errado, e cinco defeitos só apareceram quando o SQL passou a ser conferido por `PREPARE`.

Portão 23 foi acrescentado depois de um achado real: `backups/` não estava excluído do empacotamento, e o despejo do banco de desenvolvimento entraria no ZIP na próxima construção. Corrigido no `.gitignore`, no empacotador e com teste.

## 2. Veredito por camada

| Camada | Veredito | Observação |
|---|---|---|
| Banco e integridade | 🟢 | `DATABASE_INTEGRITY_REPORT.md` |
| Núcleo do produto (6 motores) | 🟢 | `CORE_PRODUCT_ARCHITECTURE.md` |
| API | 🟢 | **704** operações, contrato estável, erro RFC 7807 |
| Segurança da aplicação | 🟢 | `SECURITY_FINAL_CHECKLIST.md` §1–8 |
| Validação de segurança por terceiro | 🔴 | **nenhuma** — nunca houve teste de intrusão independente |
| Chaves e cifragem | 🟡 | funciona e é auditado; **KMS/HSM não existe** e isso está declarado |
| Assinatura digital | 🟡 | avançada funciona; **qualificada (ICP-Brasil) e Gov.br indisponíveis** |
| Integrações externas | 🟡 | o mais maduro é `contract_tested`; **nenhuma em produção real** |
| Desempenho | 🟡 | caminhos da rede entre 9 e 82 ms; workspace da OSC 341–436 ms; feed do financiador 1,5–1,7 s — limite declarado na resposta |
| Frontend funcional | 🟢 | sem erro de console, um `<h1>` por página, caminhos críticos testados no navegador |
| Frontend visual | 🔴 | **não existe camada de design** — é propositalmente a próxima etapa; e o pacote "Convergência" **não foi recebido** (`DESIGN_HANDOFF_FINAL.md` §1) |
| Mobile nativo | 🔴 | não iniciado; PWA funciona (`STORE_READINESS.md`) |
| LGPD | 🟡 | matriz de retenção escrita, direitos do titular funcionam; **RIPD e DPO pendentes** |
| Benefício fiscal | 🟡 | motor funciona; tabelas nascem **vazias** e exigem fonte, URL e data |

**Nenhum 🔴 é de engenharia interna.** Os três são: validação externa que não foi contratada, design que é a etapa
seguinte, e aplicativo nativo que não foi iniciado.

## 3. Limpeza de arquitetura

| Verificação | Resultado |
|---|---|
| `TODO` / `FIXME` em `backend/impacto` | **0** |
| `MOCK` / `STUB` / `FAKE` em caminho de produção | **0** (os duplos de teste estão em `backend/tests`, onde devem estar) |
| `except Exception` em `backend/impacto` | **35 ocorrências, todas com comentário dizendo por quê**. 11 relançam depois de limpar (apagar objeto órfão, desfazer transação, devolver vaga do pool). 24 devolvem valor seguro de propósito, em três famílias: (a) recurso **opcional** falhou e o fluxo principal continua — OCR, extração de texto, resumo por IA, busca auxiliar da Central; (b) entrada **malformada** é entrada inválida, não erro do servidor — hash legado, token, corpo JSON; (c) efeito **secundário** não pode derrubar o principal — envio de e-mail, camada institucional no match, registro de analytics, adaptador de integração (que registra a falha na própria conexão). Nenhuma das 24 esconde falha do caminho crítico: todas registram ou expõem o estado. |
| `except` com `pass` nu | 1 ocorrência, **justificada em comentário** (`migrate.py`): `ROLLBACK` de melhor esforço, com a exceção original relançada em seguida |
| Rota duplicada | **0** (conferido no registro de rotas) |
| Rota sem declaração de autenticação | **0** (`test_handlers_declare_auth`, com lista fechada de rotas públicas) |
| Uso de contexto de sistema fora dos módulos revisados | **0** (`test_system_context_only_in_allowed_modules`, lista explícita) |
| Importação de cobrança por módulo de match/diretório | **0** (`test_match_and_directory_never_import_billing`) |

## 4. Dado de demonstração × dado de produção

| Tipo | Como é separado |
|---|---|
| **Dado de referência** (planos, ODS, catálogo de indicadores, provedores de integração, provedores de assinatura, modelos de documento, traduções) | sincronizado por `sync_reference_data` em toda migração; é dado do produto, não demonstração |
| **Dado de demonstração** | só por `impacto.seed_dev`, que **não roda** em staging nem produção; soluções de exemplo têm a coluna `is_demo` |
| **Conteúdo editorial** | fluxo rascunho → revisão → aprovado → publicado, com quatro olhos; nada é publicado por migração |
| **Regras fiscais** | nascem em `draft`, exigem **duas** aprovações distintas e fonte com URL e data |
| **Tabelas de honorários** | nascem **vazias**; exigem fonte, URL e data de publicação |

A validação de configuração **recusa a subida** em staging/produção com `MAIL_PROVIDER=console` ou
`BILLING_PROVIDER=sandbox`.

## 5. O que esta liberação NÃO entrega

Lista fechada, para que ninguém descubra depois:

1. Assinatura qualificada (ICP-Brasil) e assinatura via Gov.br — ambas `unavailable`, recusadas no banco.
2. Carimbo de tempo com validade externa (RFC 3161) — 501 explícito.
3. Verificação biométrica de identidade e confirmação por SMS — 501 explícito.
4. Qualquer integração exercitada contra sistema real de cliente ou órgão.
5. KMS/HSM.
6. Camada de design.
7. Aplicativo nativo em loja.
8. Teste de intrusão independente.
9. RIPD e DPO nomeado.
10. Operação em múltiplas instâncias com armazenamento local.
11. Desempenho verificado sob concorrência em ambiente dimensionado.
12. Feed do financiador abaixo de 1 s sem filtro, em base de 10.000 projetos.

**Acrescentado na v0.16.0:**

13. **Cobrança real.** Não há conta no provedor, chave, nem preço criado. `provider_price_id` é nulo e o checkout
    responde 503 `provider_price_missing` em vez de tentar com valor inventado. Toda a camada da plataforma —
    versão de preço, vigência, aviso de 30 dias, aceite registrado, cotação, imposto, idempotência de webhook —
    está pronta e testada.
14. **O pacote de Design System "Convergência"**, que não foi recebido: as seções que dependiam dele não foram
    executadas, e nada foi inventado no lugar (`DESIGN_HANDOFF_FINAL.md` §1).
15. **Navegação horizontal retrátil com área de trabalho ampla**, pedida em rodada anterior: é entrega de design, e
    está especificada item a item em `NAVIGATION_MODEL.md`.
16. **E2E de navegador nas 27 telas novas** e verificação de viewport/contraste nelas.
17. **Push nativo no aparelho.** A notificação existe dentro do produto (14 grupos, fan-out para a equipe); FCM e
    APNs não existem.
18. **Exportação de dados pessoais cobrindo as entidades novas da rede** — decisão jurídica antes de técnica.
19. **Logotipos oficiais dos ODS.** Número, nome e cor oficial estão em `sdg_goals`; a arte depende de autorização
    de uso de marca.
20. **Decisão sobre compra dentro do app** (Apple/Google) — comercial e jurídica, do proprietário.

## 6. Para subir

`DEPLOYMENT_CHECKLIST.md` tem o procedimento. O mínimo:

```bash
# 1. banco
MIGRATION_DATABASE_URL=... python3 -m impacto.db.migrate          # aplica as 15, com lock e checksum
MIGRATION_DATABASE_URL=... python3 -m impacto.db.migrate --check  # falha se sobrou pendência

# 2. configuração (a validação recusa a subida se algo essencial faltar)
#    obrigatório em produção: DATABASE_URL, SECRET_KEY, MAIL_PROVIDER=smtp + SMTP_*
#    recomendado: FIELD_ENCRYPTION_KEY, STORAGE_PROVIDER=s3 + S3_*, ANTIVIRUS_PROVIDER=clamd

# 3. frontend
cd web && node build.mjs

# 4. depois de subir
POST /v1/admin/encryption/keys {"purpose": "field"}   # registra a chave em uso no inventário
GET  /v1/admin/encryption/keys                        # confere impressão digital e estado
GET  /v1/signature-providers                          # confere que só platform_advanced está em produção
```

## 7. Veredito

A versão está **tecnicamente pronta para receber a designer**: a rede de impacto está fechada, nada do que já
existia quebrou, o caminho de atualização está testado, não há 🔴 de engenharia interna e todo limite está
declarado em documento e, quando cabe, na própria resposta da API.

Um limite que vale repetir no veredito: o pacote de Design System **não chegou**, então as seções que dependiam
dele não foram executadas. O que foi feito no lugar é o insumo que ele consome — a arquitetura da informação e o
modelo de navegação, em `INFORMATION_ARCHITECTURE.md` e `NAVIGATION_MODEL.md`.

Para **produção com cliente pagante**, falta o que está em §5 — e nada disso é surpresa: está escrito aqui, em
`EXTERNAL_DEPENDENCIES.md` e em `HOMOLOGATION_MATRIX.md`.
