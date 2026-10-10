# INTEGRATION_CAPABILITY_MATRIX — o que cada provedor faz HOJE

Valores: **YES** · **PARTIAL** · **NO** · **NOT_IMPLEMENTED** · **UNKNOWN**. Fonte: `config/integration_providers.json` (sincronizado para `integration_providers`) e os adapters em `backend/impacto/integrations/adapters/`.
Maturidade: **SCAFFOLDED** (contrato pronto, sem execução real) · **CONTRACT TEST** (provado contra dublê identificado) · **SANDBOX** · **HOMOLOGATED** · **PRODUCTION ACTIVE** — os três últimos exigem evidência externa e só a administração os registra (`POST /v1/admin/integrations/providers/{key}/maturity`, com evidência auditada).

| Provedor | Connect | Pull | Push | Webhook | Batch | Async | Health | Maturidade | Observação |
|---|---|---|---|---|---|---|---|---|---|
| `generic_rest` (API própria da organização) | YES | YES | YES | PARTIAL | NO | NO | YES | **CONTRACT TEST** | caminhos e mapeamento vêm da conexão; webhook exige HMAC compartilhado |
| `senior_sapiens` (ERP) | YES | PARTIAL | PARTIAL | NOT_IMPLEMENTED | PARTIAL | NOT_IMPLEMENTED | YES | **CONTRACT TEST** | híbrido REST/SOAP; operações SOAP reais dependem do módulo/versão contratados (configuráveis). **Não homologado** |
| `totvs` (Protheus, RM, Datasul) | YES | PARTIAL | PARTIAL | NOT_IMPLEMENTED | NOT_IMPLEMENTED | NOT_IMPLEMENTED | YES | **CONTRACT TEST** | variante por `config.product`; caminhos de fundação sobrescrevíveis. **Não homologado** |
| `government_api` (Gov.br, Conecta, federais/estaduais/municipais) | YES | PARTIAL | NOT_IMPLEMENTED | NOT_IMPLEMENTED | NOT_IMPLEMENTED | NOT_IMPLEMENTED | PARTIAL | **SCAFFOLDED** | `pull` recusa enquanto `authorization_status = technically_ready`; produção exige `production_active`. **EXTERNAL AUTHORIZATION REQUIRED** |
| `oidc_identity` (Google, Microsoft, Gov.br, Keycloak) | YES | NO | NO | NO | NO | NO | PARTIAL | **CONTRACT TEST** | implementado em `services/oidc.py` (code flow + PKCE), testado com IdP dublê. IdP real: **HOMOLOGATION REQUIRED**. SAML/LDAP: NOT_IMPLEMENTED |
| `stripe_payments` | YES | PARTIAL | YES | YES | NO | YES | PARTIAL | **CONTRACT TEST** | domínio de cobrança separado do provedor (`services/billing.py`); webhook assinado e idempotente. Stripe real nunca chamado |
| `email_smtp` | YES | NO | YES | NO | YES | YES | NO | **CONTRACT TEST** | `adapters/mail.py` (outbox e SMTP com 3 tentativas). SMTP real não exercitado. WhatsApp/SMS/push: NOT_IMPLEMENTED |
| `bi_export` | YES | YES | NO | NO | YES | YES | YES | **CONTRACT TEST** | 6 datasets fixos por organização, CSV/JSON, fórmula neutralizada |
| `sftp_batch` | NOT_IMPLEMENTED | NOT_IMPLEMENTED | NOT_IMPLEMENTED | NO | NOT_IMPLEMENTED | NOT_IMPLEMENTED | NOT_IMPLEMENTED | **SCAFFOLDED** | contrato reservado; a fundação de arquivos seria reutilizada |

## Canais por tipo
| Canal | Estado | Onde |
|---|---|---|
| REST/JSON de saída | **PRONTO** (provado) | `transport.ResilientCaller` + `adapters/rest.py` |
| SOAP/XML de saída | **PRONTO** (provado contra dublê) | `xmlsafe.soap_envelope` + `adapters/erp.py` |
| Webhook de entrada | **PRONTO** (provado) | `POST /v1/integrations/inbound/{connection_id}` |
| Webhook de saída | **PRONTO** (provado) | `integration_subscriptions` + `events.deliver_pending` |
| Eventos de domínio | **PRONTO** (26 eventos reais) | `events.CATALOG` |
| Arquivo CSV/XLSX (upload) | **PRONTO** (provado) | `files.create_import` |
| Arquivo JSON/XML (conexão) | **PRONTO** no interpretador | `files.parse_rows` — upload limitado pela allowlist do cofre |
| Exportação/BI | **PRONTO** (provado) | `files.generate_export` |
| SFTP / lote agendado | **NOT IMPLEMENTED** | contrato reservado |
