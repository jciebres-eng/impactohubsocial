# INVENTÁRIO DA IA — estado inicial (v0.27.0) e o que a v0.28.0 fez com cada item

Inspeção feita no código, não no README: `grep` de toda chamada a modelo (`ExternalLLM`, `AiGateway`), SDKs
(nenhum: HTTP direto por `HttpClient`), embeddings/reranking (nenhum), OCR (`pytesseract`, local, opcional),
tarefas agendadas (`jobs.py`: nenhuma chama modelo), billing/créditos/pagamentos/webhooks existentes.

## 1. Diagnóstico do estado inicial

| O que existia (v0.27.0) | Onde | Situação encontrada |
| --- | --- | --- |
| Gateway provider-agnostic (`local` / `anthropic` / `openai_compatible` / `disabled`) | `engines/ai/gateway.py` | chave e modelo por ambiente; redação de dado pessoal antes de sair; fallback para motor local; **nenhum SDK**, HTTP direto |
| Prompt versionado, faixa de risco (0–4), esquema de saída conferido | `ai_prompts`, `ai_model_policies`, `engines/ai/policy.py` | ok (v0.23.0) |
| Uso registrado com tokens e custo derivado da tabela de preço | `ai_usage`, `ai_price_table`, `app_price_ai_usage()` | tabela de preço VAZIA de propósito → `cost_status = no_price_table` |
| Cota | `plans.json → limits.ai_requests_month` (20/50/300) | número FIXO por pacote; conta chamadas, não custo; sem cota configurável, sem anti-abuso |
| Orçamento em dinheiro por organização | `ai_budgets`, `ai_budget_state()` | ok, mas só limita onde há preço |
| Razão de créditos | `ai_credit_ledger`, `ai_credit_consume()` | **append-only e atômico, mas NUNCA chamado pela aplicação**: `credits_charged` sempre nulo |
| Pagamentos | `platform_charges`, `charge_state_graph`, `billing_events`, `record_webhook()` | máquina de estados e dedup de webhook prontos; **nenhuma rota de webhook** (a de assinatura saiu na v0.27.0); PIX/boleto sem provedor (instrução nunca gravada) |
| Similaridade | `solutions` (trigramas de título), busca da Central de Conhecimento | só para soluções/artigos; **nenhum motor de originalidade de projetos** |
| Patrocínio, pedido de crédito, prévia de custo, execução com estado, catálogo de operações | — | **inexistentes** |

## 2. Inventário das chamadas de IA

| Módulo | Perfil | Operação | Provedor/modelo | Custo externo | Frequência esperada | Cache | Risco de abuso | Controle (v0.28.0) | Status | Implementação |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `ai_routes.structure_need` | OSC (member) | estruturar necessidade (cat. B) | externo se configurado, senão local | desconhecido (sem preço) | baixa | não (texto livre) | médio: 20k chars × 60/h | `assist.structure_need` 5 créditos; faixa 1; rate; cota; `Run` | integrado | feito |
| `ai_routes.draft` | OSC (member) | rascunho de documento (cat. B) | idem | desconhecido | baixa | não | médio | `assist.draft_document` 10 créditos | integrado | feito |
| `ai_routes.summarize` | todos (viewer) | resumo do projeto (cat. A) | idem | desconhecido | média | parcial (hash da entrada no `ai_usage`) | médio | `assist.summarize_project` 1 crédito; cota | integrado | feito; cache por versão de projeto: próxima rodada |
| `ai_routes.classify` + `document_routes` upload | OSC (member) | classificar documento (cat. A) | **local** | zero | média | n/a | baixo (rate 60/h) | gratuita (`free`) no catálogo | integrado | feito (sem execução registrada: determinística) |
| `services/documents` OCR | OSC | OCR de upload | tesseract local | zero (CPU) | baixa | n/a | baixo | fora do catálogo (não é IA generativa) | ok | — |
| `engines/similarity` (NOVO) | todos | originalidade, par, conjunto, complementaridade, despesas (cat. D) | **local** (faixa 3: não sai) | zero (CPU: par < 1 ms, 200 cand. ~150 ms medidos) | média | **sim** (hash dos insumos + versão) | médio: até 300 candidatos por análise, 20 por conjunto | créditos por operação; prévia; cota/patrocínio/comprado | integrado | feito |
| `similarity.batch`, `similarity.monitoring`, `report.institutional_portfolio` | empresa/governo | lote, monitoramento, relatório (cat. E/F) | — | — | — | — | alto (volume) | declaradas `planned`; rota responde 501 | **não implementadas** | próxima rodada (fila, orçamento por tarefa, cancelamento) |
| `jobs.py` | sistema | — | nenhuma chamada a modelo | — | — | — | — | — | ok | — |

Loops/retries: `HttpClient(retries=2)` só em erro de rede; nenhuma repetição automática de operação cara (idempotência por chave; cache por insumo).

## 3. Inventário de billing, créditos, pagamentos e razão (o que ficou, o que entrou)

| Item | Antes | v0.28.0 |
| --- | --- | --- |
| `ai_credit_ledger` | sem lote, sem validade, sem consumidor | `bucket` (purchased/promotional), `expires_at`, `execution_id`; motivos `purchase`, `sponsor_commit`, `release`; escrita só por `ai_credit_post`/`ai_credit_consume_bucket` com portão |
| cota | fixa no pacote | `ai_quota_policies` configuráveis + `ai_quota_grants` (boas-vindas 60 uma vez por org e por pessoa; mensal leve 10) |
| execução | inexistente | `ai_executions` + `ai_execution_events` + grafo de estados |
| catálogo | inexistente | `ai_operations` versionado (12 operações: 9 executáveis, 3 planejadas) |
| pedido de crédito / PIX | inexistente | `ai_credit_packs` (3 hipóteses), `ai_credit_orders` (piloto/real), `platform_charges.kind = 'ai_credits'`, webhook HMAC |
| patrocínio | inexistente | `ai_sponsorships` + funções SECURITY DEFINER de consumo e prestação de contas |
| regra comercial | — | `ai.credits_prepaid` (review_required, carta amarela) — 11ª regra do catálogo |
| painel | `GET /v1/admin/ai` (prompts, faixas, resultados) | + `GET /v1/admin/ai/finance` (medido × NÃO MEDIDO, obrigações, margem parcial, alertas) |

## 4. Lacunas encontradas e tratadas

* Crédito existia e não era consumido → toda operação cobrável passa por `usage_control.Run`.
* Rotas de IA sem fonte de custeio explícita → prévia obrigatória com custo, fonte e saldo.
* Cota por pacote (`ai_requests_month`) **mantida** como teto de chamadas do pacote de capacidades; a cota de créditos é outra régua (ADR-331).
* `i18n`: textos da Central de IA são literais em `aicenter.tsx` (como as demais telas desta base).
* Operações de lote declaradas e não implementadas — por escolha: sem volume e preço reais, implementar fila seria infraestrutura inexercitável (AI_AUDIT.md §3 continua válido).
