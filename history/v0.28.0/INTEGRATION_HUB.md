# INTEGRATION_HUB — guia operacional da camada de integração

Arquitetura: `INTEGRATION_ARCHITECTURE.md` · Inventário real: `INTEGRATION_INVENTORY.md` · Capacidades: `INTEGRATION_CAPABILITY_MATRIX.md` · Segurança: `INTEGRATION_SECURITY.md` · Operação: `INTEGRATION_OPERATIONS.md` · Testes: `INTEGRATION_TESTING.md` · Como criar adapter: `INTEGRATION_PROVIDER_GUIDE.md`.

## 1. Conceitos em uma frase cada
- **Provedor**: entrada do catálogo (`generic_rest`, `senior_sapiens`, `totvs`, `government_api`, …) com capacidades e **maturidade real**.
- **Conexão**: a configuração de UMA organização para UM provedor em UM ambiente (`development`, `sandbox`, `homologation`, `production`).
- **Credencial**: o segredo da conexão, cifrado; a API só devolve a dica (`••••4f2a`).
- **Mapeamento**: campo externo → campo canônico, com transformação declarada.
- **Correspondência (link)**: ID interno ↔ ID externo, com versão e estado (`linked`, `conflict`, `deleted_externally`…).
- **Job**: uma execução de integração, idempotente, com tentativas e correlação.
- **Evento**: fato do domínio que a plataforma emite (26 tipos reais).
- **Assinatura**: webhook de saída de um parceiro (URL + eventos + segredo HMAC).
- **Entrada**: webhook que um sistema externo manda para nós, deduplicado.

## 2. Estados (o que a interface precisa mostrar)
| Objeto | Estados |
|---|---|
| Conexão | `draft` → `active` → `paused` → `revoked` |
| Saúde | `unconfigured`, `unknown`, `healthy`, `degraded`, `unauthorized`, `unavailable` |
| Job | `pending` → `running` → `succeeded` \| `partial` \| `retrying` → `failed` \| `canceled` |
| Erro do job | `temporary` (repete) \| `permanent` (não repete) |
| Entrega | `pending` → `delivered` \| `retrying` → `dead_letter` \| `skipped` |
| Entrada | `received` → `processed` \| `ignored` \| `rejected` \| `duplicate` |
| Correspondência | `linked`, `pending`, `conflict`, `stale`, `deleted_externally` |
| Importação | `uploaded` → `validated` → `parsed` → `previewed` → `approved` → `imported` \| `rejected` \| `failed` |
| Exportação | `pending` → `running` → `ready` \| `failed` \| `expired` |

## 3. Caminho feliz (receita)
1. `GET /v1/integrations/providers` — escolher o provedor (ver maturidade).
2. `POST /v1/integrations/connections` — nasce em `draft`; a resposta já lista `config_problems`.
3. `PUT /v1/integrations/connections/{id}/credential` — grava o segredo (papel `owner`).
4. `PUT /v1/integrations/connections/{id}/mappings` — campo externo → canônico.
5. `PATCH /v1/integrations/connections/{id}` com `{"status": "active"}` — só ativa com configuração válida e credencial.
6. `POST /v1/integrations/connections/{id}/health` — confirma a conversa (somente leitura).
7. `POST /v1/integrations/connections/{id}/jobs` — enfileira `pull`/`push`; o trabalhador executa.
8. `GET /v1/integrations/jobs/{id}` — resultado, erro classificado e **trilha de auditoria**.
9. `GET /v1/integrations/links` — correspondências e conflitos.

## 4. Webhooks
**Saída:** `POST /v1/integrations/subscriptions` (HTTPS obrigatório, eventos do catálogo, segredo ≥ 16). Cada entrega leva
`X-Impacto-Signature: t=<unix>,v1=<hmac_sha256(segredo, "<t>." + corpo)>`, `X-Impacto-Event-Id`, `X-Impacto-Event-Type` e `X-Correlation-Id`.
O parceiro deve: verificar a assinatura, recusar `t` fora de ±300 s e **ignorar id de evento repetido**. Responder 2xx. Falha 4xx vai direto a dead-letter; 5xx/timeout tenta até 6 vezes com espera crescente. `POST /v1/integrations/deliveries/{id}/replay` reenvia dead-letter.
**Entrada:** `POST /v1/integrations/inbound/{connection_id}` com a mesma assinatura e `X-Event-Id`. Respostas: `202` aceito (job enfileirado), `200 duplicate_ignored`, `403 bad_signature`, `400 missing_event_id|malformed_payload`, `409 connection_inactive`, `404 unknown_connection` (resposta genérica: não revela organização).

## 5. Arquivos
Importar: enviar o arquivo em `POST /v1/documents` (cofre valida tamanho, extensão, assinatura binária, zip bomb, antivírus) → `POST /v1/integrations/imports` (`csv` ou `xlsx`) → conferir em `GET /v1/integrations/imports/{id}` (linhas válidas, inválidas e o erro de cada uma) → `POST /v1/integrations/imports/{id}/approve` (papel `owner`).
A importação **aplica correspondências de ID externo a registros existentes**; ela não cria usuários nem organizações (cadastro e consentimento têm processo próprio). Mesmo arquivo (mesmo SHA-256) não entra duas vezes.
Exportar: `POST /v1/integrations/exports` com um dos datasets de `GET /v1/integrations/datasets` → baixar pelo `document_id` com a URL temporária de documentos.

## 6. Operação
`GET /v1/admin/integrations/overview` responde "qual integração está quebrada agora": saúde por estado, conexões quebradas com sequência de falhas e disjuntor, jobs das últimas 24 h, falhas recentes, entregas, dead-letters, profundidade das filas, importações aguardando aprovação e latência por provedor nos últimos 7 dias.
O trabalhador roda no agendador (`integration_ops`): executa jobs devidos, entrega webhooks, verifica conexões sem checagem há 30 min e aplica retenção (entregas concluídas com mais de 180 dias). `POST /v1/admin/integrations/run-worker` força um ciclo.

## 7. Limites
Nenhuma integração homologada. Governo depende de credenciamento. SFTP não implementado. SAML/LDAP, WhatsApp/SMS/push não implementados. JSON/XML por upload não (só por conexão). Sem fila distribuída: o trabalhador é o agendador do processo (suficiente para o volume atual; `queue_depth` é o indicador para decidir trocar).
