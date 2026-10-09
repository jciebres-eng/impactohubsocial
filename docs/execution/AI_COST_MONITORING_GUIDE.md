# Guia de monitoramento de custos da IA — v0.28.0

Para quem opera o piloto (administração com `finance.read`). Tudo o que está aqui lê registros reais;
onde não há medição o painel escreve **NÃO MEDIDO** e deixa o campo nulo — nunca estima.

## 1. Onde olhar

| O quê | Onde | Permissão |
|---|---|---|
| Painel financeiro da IA: execuções por operação (sucesso/falha/parcial), créditos por lote (concedidos, comprados, consumidos, reservados, a vencer), custo externo MEDIDO × NÃO MEDIDO, receita recebida × reconhecida, obrigações (créditos vendidos não consumidos), margem parcial, alertas, contestações abertas | `/admin/ia/financeiro` (menu Controladoria) · `GET /v1/admin/ai/finance` | `finance.read` |
| Pedidos de crédito de todas as organizações (piloto e real) | `GET /v1/admin/ai/credit-orders` | `billing.read` |
| Prompts, faixas de risco, uso e tabela de preço do provedor (desde a v0.23.0) | `GET /v1/admin/ai` (API; sem tela própria) | `metrics.read` |
| Orçamento em dinheiro por organização e política por faixa | `/ia/orcamento` (cada organização) | membro |
| Extrato de execuções e razão de créditos de UMA organização | `/ia` → "Histórico" e "Extrato" · `GET /v1/ai/executions`, `GET /v1/ai/center` | membro |
| Prestação de contas de um patrocínio (agregada, sem texto dos projetos) | `/ia/patrocinios/:id` | patrocinador |
| Contestações de similaridade para revisão humana | `GET /v1/admin/ai/disputes` → `POST …/review` | `support.read` / `support.write` |
| Custo e latência no banco | `ai_executions` (`cost_status`, `estimated_cost_cents`, `actual_cost_cents`, `latency_ms`, `input_chars`, `tokens_in/out`), `ai_usage` | administração do banco |

## 2. Os alertas do painel e o que fazer

| Alerta | Significado | Ação |
|---|---|---|
| "execuções externas sem preço vigente na tabela do provedor: custo NÃO MEDIDO" | há provedor configurado e `ai_price_table` não tem o modelo | cadastrar o preço em `ai_price_table` (administração do banco, com fonte e data — não há rota de escrita, de propósito); até lá o custo externo é desconhecido, não zero |
| "N crédito(s) comprado(s) ainda não consumido(s): obrigação com clientes, não receita" | créditos vendidos ≠ lucro | não tratar o recebido como receita reconhecida; acompanhar vencimento |
| "N contestação(ões) de similaridade aguardando revisão humana" | alguém discorda de uma análise | revisar em até 5 dias úteis (prazo do piloto); registrar `reviewed_upheld` ou `reviewed_corrected` com justificativa |
| "`<operação>`: mais de 20% de falhas/parciais" | provedor instável, entrada grande demais ou defeito | ver `ai_execution_events` da operação; se for provedor, `AI_PROVIDER=local` ou `disabled` até normalizar — falha e parcial **não cobram**, logo o custo do provedor que falhou é da plataforma |

## 3. Rotina sugerida do piloto

**Diária (5 min):** abrir `/admin/ia/financeiro`; conferir alertas; conferir que "Receita recebida" é
R$ 0,00 enquanto a regra `ai.credits_prepaid` estiver inativa (qualquer valor diferente de zero sem
regra ativa é defeito — reportar).

**Semanal:** exportar de `ai_executions` o agregado por operação (contagem, p50/p95 de `latency_ms`,
soma de `charged_credits`, soma de `actual_cost_cents` onde `cost_status = measured`) e comparar com as
hipóteses de `config/ai_economics.json` (`tokens_in/out`, `free_share`). Quando a medição divergir
mais de 30% da hipótese, atualizar o arquivo e regenerar `AI_COST_MODEL.md`
(`python3 scripts/make_ai_cost_model.py`; `test_v0280_ai_cost_model` confere).

**Mensal:** (1) consumo da cota gratuita × teto de subsídio do piloto (`subsidy_cap_cents_month`,
hipótese R$ 500/mês — o modelo §3 mostra quanto a gratuidade custa por cenário); se o custo medido da
gratuidade passar do teto, reduzir `monthly.light.v1` (`PUT /v1/admin/ai/quota-policies/monthly.light.v1`,
`finance.approve`) antes de cortar a cota de boas-vindas; (2) créditos promocionais a vencer; (3)
patrocínios próximos do fim (`ai_sponsorships.status = exhausted`); (4) conjunto de avaliação da
similaridade: acrescentar os casos contestados e revisados como pares rotulados
(`tests/test_v0280_similarity.py::EVAL`) e reexecutar para recalcular precisão/recall.

## 4. Botões de emergência

| Situação | Ação | Efeito |
|---|---|---|
| custo do provedor fora de controle | `AI_PROVIDER=disabled` (ou `local`) e reiniciar | nenhuma chamada externa; similaridade e classificação continuam (locais); `assist.*` cai para o motor local ou responde indisponível |
| orçamento de uma organização | `/ia/orcamento` → limite em dinheiro (`ai_budgets`) | a organização para quando atingir o limite |
| operação específica | publicar versão nova com `status = planned` | prévia responde 501; execuções autorizadas terminam |
| cota gratuita | `PUT /v1/admin/ai/quota-policies/{key}` com `active = false` | nenhuma concessão nova; concessões feitas valem até vencer |
| pedidos de crédito | regra `ai.credits_prepaid` inativa (padrão) | pedidos só em modo piloto, sem dinheiro |

## 5. O que este guia NÃO cobre

Custo de infraestrutura por operação, tarifa de PIX, impostos e custo de provedor sem tabela de preço
— o painel diz NÃO MEDIDO para cada um. Nenhum provedor de pagamento ou de modelo está configurado
nesta instalação de referência.
