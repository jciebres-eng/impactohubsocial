# Checklist de validação de produção — v0.29.0

Estado de cada item nesta instalação de referência (sem produção): **FEITO** (provado por teste ou execução
registrada), **PENDENTE DO PROPRIETÁRIO** (credencial, conta, parecer, decisão) ou **PENDENTE DA EQUIPE EDITORIAL**
(só pessoa da área responde). Nada aqui foi marcado FEITO por suposição.

## A. Antes de subir a v0.29.0

| # | Item | Estado | Como conferir |
|---|---|---|---|
| A1 | Backup da base anterior guardado fora do host (`pg_dump -Fc`) | PENDENTE DO PROPRIETÁRIO | `docs/execution/ROLLBACK_v0290.md` §0 |
| A2 | Migração 0069 aplicada do zero e sobre cópia da v0.28.0 com ROLLBACK (dry-run) | FEITO | suíte (`tests/support`) e `impacto_m69` (template de m68 + 0068, 0069 em BEGIN/ROLLBACK); `test_v0230_data_infra_gate` (nenhum DROP de tabela) |
| A3 | Regressão completa (2 passagens: 2379/2380 testes, 0 erro na 2ª; 5 falhas só de fechamento) e portões 184/184 | FEITO | `docs/evidence/test_run_v0.29.0.log`; `FINAL_EXECUTION_REPORT.md` §24 |
| A4 | CI do GitHub (auditoria, backend, docker, pilha-do-zero) verde no commit final | FEITO (`dd2f8c3`, run `37935603837`, 4/4 verdes; a run anterior `37932633056` reprovou e foi corrigida — auditoria §7) | `FINAL_EXECUTION_REPORT.md` §3 |
| A5 | Pacote confere byte a byte com o git; sem segredo; sem ZIP aninhado | FEITO no fechamento | `verify_package_against_git.py`, `secrets_scan.py`, `unzip -t` |
| A6 | Tag `v0.29.0` no commit de fechamento | PENDENTE DO PROPRIETÁRIO (proxy recusa push de tag) | GitHub → Releases |
| A7 | `web/src/concepts.ts` em sincronia com `config/concepts.json` | FEITO | `python3 scripts/sync_concepts.py --check` (também no teste) |

## B. Configuração de ambiente (nenhum valor novo no repositório)

| # | Variável / item | Estado | Regra |
|---|---|---|---|
| B1 | Nenhuma variável nova nesta versão | — | a camada de conhecimento não liga provedor algum; o assistente continua extrativo (`ai_used = false`) |
| B2 | Papéis editoriais (`staff_roles`: editor, reviewer, support) com MFA | PENDENTE DO PROPRIETÁRIO (quem são as pessoas) | `POST /v1/admin/staff-roles`; sem reviewer, nenhuma fonte é conferida e nenhuma retirada acontece |
| B3 | Itens da v0.27.0/v0.28.0 (`PLATFORM_PIX_KEY`, aceite de termos, SMTP, hospedagem, `AI_PROVIDER`, `PAYMENT_WEBHOOK_SECRET`) | PENDENTE DO PROPRIETÁRIO | `EXTERNAL_INTEGRATIONS.md`, checklists anteriores |

## C. Fumaça após subir (10 minutos)

| # | Passo | Esperado | Estado |
|---|---|---|---|
| C1 | `GET /readyz` | `status = ready`, sem `pending_migrations` (última: 0069) | FEITO na suíte |
| C2 | `GET /v1/help/sources` (sem login) | 11 fontes, todas `verification = unverified`, `review_due = 2026-11-07`, aviso de que classe não é parecer | FEITO (`test_v0290_knowledge_base`) |
| C3 | `GET /v1/public/concepts` (sem login) | 33 conceitos, versão `concepts@1.0` | FEITO |
| C4 | Abrir `/ajuda/glossario` | lista com busca e filtro; cada termo com "Como o IMPACTO usa", "Limites" e "Fontes"; sem erro de console; contraste ok em claro e escuro | FEITO (`test_e2e_v0290_contextual_help`) |
| C5 | Entrar como OSC → `/oportunidades` → passar o mouse em "compatibilidade" → Enter | dica curta no hover/foco; cartão com título, limites ("não é aprovação") e fonte; Escape fecha e devolve o foco | FEITO (E2E) |
| C6 | Buscar "capital da Mongólia" na Central e perguntar ao assistente | busca vazia; assistente: "Não encontrei informação suficiente na base publicada da plataforma."; item `assistant_gap` na fila | FEITO (`test_v0290_search_eval`, `test_v0290_knowledge_base`) |
| C7 | Como reviewer: retirar um conteúdo publicado com motivo | some da busca, do assistente e do sitemap; motivo e autor gravados; reativar exige versão nova | FEITO |
| C8 | Como editor: citar fonte com trecho numa fonte com `rights.excerpt = unknown` | 409/422 — recusado pelo banco | FEITO |
| C9 | Outra organização tenta ler a fila editorial ou citar | 403 (só papéis editoriais com MFA) | FEITO (`test_v0230_api_sweep`, matriz de autorização) |

## D. Trabalho editorial antes de chamar qualquer conteúdo de "oficial"

| # | Passo | Estado | Evidência exigida |
|---|---|---|---|
| D1 | Conferir as 11 fontes (vigência na fonte oficial, licença, direitos de uso) — por pessoa diferente de quem registrou | PENDENTE DA EQUIPE EDITORIAL | `POST /v1/admin/content/sources/{key}/verify` (reviewer); `verification = verified` com nota |
| D2 | Revisar as 33 definições do glossário por área (jurídico, contábil, impacto) | PENDENTE DA EQUIPE EDITORIAL | `status` de `needs_review` → `published` no catálogo; versão nova do arquivo |
| D3 | Escrever conteúdo oficial (origem `official`) com citações a fontes conferidas; a semente continua DEMO/educacional | PENDENTE DA EQUIPE EDITORIAL | artigos `demo = false`, `origin = official`, citações em `kb_citations` |
| D4 | Ampliar o conjunto de avaliação da busca com consultas reais (anônimas: só hash + tópicos da fila `search_gap`) e rotular por mais de uma pessoa | PENDENTE DO PILOTO | `config/search_eval.json` com mais de 35 consultas; piso recalculado |
| D5 | Decidir, com parecer, os 13 controles `BLOCKED_EXTERNAL` e os 12 `NOT_IMPLEMENTED` da reconciliação | PENDENTE DO PROPRIETÁRIO | `knowledge-base/CONTROL-RECONCILIATION.json` atualizado com teste por controle |

## E. O que esta lista NÃO afirma

Que algum conteúdo está "em conformidade" com lei; que as fontes estão vigentes (0 conferidas); que a busca tem
"qualidade" além do que o conjunto pequeno e sintético mediu; que o sistema é "100% impossível de invadir".
