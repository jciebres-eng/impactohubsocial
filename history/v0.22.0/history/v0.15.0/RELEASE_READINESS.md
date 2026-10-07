# Prontidão da liberação — v0.15.0

Este documento responde a uma pergunta por vez, com GREEN / YELLOW / RED e o motivo. Não há "parcialmente verde".

## 1. Portões de liberação

| # | Portão | Situação | Prova |
|---|---|---|---|
| 1 | Suíte completa verde, banco criado do zero | 🟢 | 673 testes, 0 falhas, 7 pulados · `docs/evidence/test_run_v0.15.0.log` |
| 2 | Lint do backend sem apontamento | 🟢 | `ruff 0.16.8`, "All checks passed" · `docs/evidence/ruff_v0.15.0.log` |
| 3 | Tipos do frontend sem erro | 🟢 | `tsc --noEmit` limpo |
| 4 | Build do frontend | 🟢 | `node build.mjs` · 14 arquivos no pré-cache |
| 5 | Compilação de todo o Python | 🟢 | `python3 -m compileall impacto` |
| 6 | OpenAPI gerado do código | 🟢 | 625 operações · `docs/openapi.json` |
| 7 | Migrações só para frente, com checksum | 🟢 | 15 migrações, nenhuma liberada foi editada |
| 8 | Caminho de atualização v0.12.1 → v0.15.0 com dado dentro | 🟢 | `test_v0150_upgrade.py` (10 testes) |
| 9 | Esquema atualizado **idêntico** ao criado do zero | 🟢 | `test_10_schema_matches_a_database_built_from_scratch` |
| 10 | RLS em toda tabela de dado de organização | 🟢 | 203 de 205 com política; exceções nomeadas |
| 11 | Matriz de isolamento A → recurso de B | 🟢 | varredura automática de todas as rotas de escrita + matriz explícita + SQL direto |
| 12 | Nenhum segredo no repositório nem no ZIP | 🟢 | teste estático + varredura no empacotador |
| 13 | Jornadas de ponta a ponta | 🟢 | 8 jornadas · `test_e2e_v0150_journeys.py` |
| 14 | Navegador real nas telas novas | 🟢 | 6 testes · `test_e2e_v0150_web.py` |
| 15 | Invariantes do produto | 🟢 | 21 testes · `test_v0150_invariants.py` |
| 16 | Desempenho medido com volume de alvo | 🟢 | medido; o feed é 🟡 e está declarado |
| 17 | Compatibilidade: nada que existia quebrou | 🟢 | suíte inteira anterior continua verde |
| 18 | Dependência externa ausente produz recusa explícita | 🟢 | 501/estado `unavailable`, nunca sucesso falso |
| 19 | Nenhum `TODO`/`FIXME`/`MOCK`/`STUB` no caminho de produção | 🟢 | ver §3 |
| 20 | Dado de demonstração separado de dado de produção | 🟢 | ver §4 |
| 21 | Documentação da versão completa e versionada | 🟢 | 16 documentos novos/atualizados + snapshot em `history/v0.14.0/` |
| 22 | ZIP completo, sem ZIP aninhado, validado por extração | 🟢 | `scripts/make_release.py` + `--verify` |
| 23 | **Pacote sem despejo de banco nem dado local**, garantido por teste | 🟢 | `test_architecture.ReleasePackageTests` (2 testes) |

Portão 23 foi acrescentado depois de um achado real: `backups/` não estava excluído do empacotamento, e o despejo do banco de desenvolvimento entraria no ZIP na próxima construção. Corrigido no `.gitignore`, no empacotador e com teste.

## 2. Veredito por camada

| Camada | Veredito | Observação |
|---|---|---|
| Banco e integridade | 🟢 | `DATABASE_INTEGRITY_REPORT.md` |
| Núcleo do produto (6 motores) | 🟢 | `CORE_PRODUCT_ARCHITECTURE.md` |
| API | 🟢 | 625 operações, contrato estável, erro RFC 7807 |
| Segurança da aplicação | 🟢 | `SECURITY_FINAL_CHECKLIST.md` §1–8 |
| Validação de segurança por terceiro | 🔴 | **nenhuma** — nunca houve teste de intrusão independente |
| Chaves e cifragem | 🟡 | funciona e é auditado; **KMS/HSM não existe** e isso está declarado |
| Assinatura digital | 🟡 | avançada funciona; **qualificada (ICP-Brasil) e Gov.br indisponíveis** |
| Integrações externas | 🟡 | o mais maduro é `contract_tested`; **nenhuma em produção real** |
| Desempenho | 🟡 | tudo ≤ 11 ms, exceto o feed do financiador a 1,6 s — limite declarado na resposta |
| Frontend funcional | 🟢 | sem erro de console, um `<h1>` por página, caminhos críticos testados no navegador |
| Frontend visual | 🔴 | **não existe camada de design** — é propositalmente a próxima etapa |
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

A versão está **tecnicamente pronta para receber a designer**: o núcleo do produto está fechado, nada do que já
existia quebrou, o caminho de atualização está testado, não há RED de engenharia interna e todo limite está
declarado em documento e, quando cabe, na própria resposta da API.

Para **produção com cliente pagante**, falta o que está em §5 — e nada disso é surpresa: está escrito aqui, em
`EXTERNAL_DEPENDENCIES.md` e em `HOMOLOGATION_MATRIX.md`.
