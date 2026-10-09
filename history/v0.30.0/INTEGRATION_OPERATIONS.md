# INTEGRATION_OPERATIONS — como operar as integrações

## 1. "Qual integração está quebrada agora?"
`GET /v1/admin/integrations/overview` (administração com MFA). Devolve, em uma resposta:
- `health`: contagem por estado de saúde.
- `broken`: conexões `degraded`/`unauthorized`/`unavailable` com organização, provedor, ambiente, sequência de falhas, detalhe e **disjuntor aberto até**.
- `jobs_24h`: jobs por estado nas últimas 24 h.
- `recent_failures`: últimas falhas com código, tipo (`temporary`/`permanent`) e tentativas.
- `deliveries`: entregas por estado; `dead_letters`: as 20 últimas.
- `queue_depth`: jobs pendentes/em repetição e entregas pendentes (indicador de saturação).
- `pending_imports`: importações aguardando aprovação humana.
- `latency`: p50/p95/máximo e amostra por provedor nos últimos 7 dias.

## 2. Diagnóstico por sintoma
| Sintoma | Primeira verificação | Causa comum | Ação |
|---|---|---|---|
| Saúde `unauthorized` | `health_detail` | credencial expirada/revogada no sistema externo | repor credencial (`PUT …/credential`), rodar `POST …/health` |
| Saúde `unavailable` + disjuntor aberto | `circuit_open_until` | sistema externo fora do ar | aguardar o fim da janela (300 s) ou `POST …/health` depois que o parceiro confirmar |
| Jobs em `retrying` crescendo | `error_kind` = `temporary` | instabilidade/limite de taxa do parceiro | nada a fazer: repetição com espera crescente; se não cessar, pausar a conexão |
| Job `failed` com `permanent` | `error_code` | configuração, mapeamento ou payload inválido | corrigir mapeamento/configuração e **reenfileirar** (novo job com nova chave de idempotência) |
| Entrega em `dead_letter` | `response_status`/`error` | endpoint do parceiro recusou | parceiro corrige e `POST /v1/integrations/deliveries/{id}/replay` |
| Entrada com `duplicate` | normal | reenvio do parceiro | nada: dedupe por `(conexão, id do evento)` |
| Entrada `403 bad_signature` | relógio e segredo | segredo divergente ou carimbo fora de ±300 s | alinhar NTP, repor segredo |
| Importação travada em `previewed` | `invalid_rows` | linhas inválidas | corrigir o arquivo ou aprovar (só linhas válidas entram) |
| Correspondência em `conflict` | `conflict_detail` | o mesmo ID externo passou a apontar para outro registro | decisão humana; **nada é sobrescrito em silêncio** |
| `queue_depth` sempre alto | agendador | ciclo do trabalhador insuficiente | reduzir intervalo do `integration_ops` ou adotar fila dedicada |

## 3. Rotina
- **Diária**: painel (`broken`, `dead_letters`, `pending_imports`).
- **Semanal**: `latency` por provedor; jobs `permanent` repetidos (sinal de mapeamento errado).
- **Mensal**: revisar credenciais com `expires_at` próximo; conferir maturidade declarada dos provedores contra a realidade.
- **Retenção**: automática (entregas concluídas > 180 dias). Jobs e eventos ainda **sem expurgo** — definir prazo com o DPO.

## 4. Mudanças de ambiente
Cada conexão é de UM ambiente. Promover significa **criar outra conexão** em `production` com credencial própria; nada é "promovido no lugar". Governo exige, além disso, maturidade `production_active` registrada pela administração com evidência (`POST /v1/admin/integrations/providers/{code}/maturity`, evidência ≥ 20 caracteres, gravada em auditoria).

## 5. Trabalhador
`integration_ops` roda no agendador do processo: executa jobs devidos (`FOR UPDATE SKIP LOCKED` — vários processos não duplicam execução), entrega webhooks pendentes, verifica conexões sem checagem há 30 min e aplica retenção. `POST /v1/admin/integrations/run-worker` força um ciclo (diagnóstico). **Não há fila distribuída**: é uma dependência de infraestrutura declarada, não um defeito escondido.

## 6. Recomendações registradas (fora do escopo técnico desta etapa)
- Base legal para enviar eventos a terceiros: hoje a organização que cria a assinatura responde por ela. Recomenda-se registro explícito de finalidade por assinatura — **LEGAL VALIDATION REQUIRED**.
- Egress controlado na infraestrutura (bloqueio de rede interna na camada de rede) para fechar o risco residual de DNS rebinding.
- Rotação programada de segredos de assinatura (hoje é manual, `PUT` sobre a assinatura).
