# INTEGRATION_ARCHITECTURE — como a IMPACTO conversa com sistemas externos

## 1. Princípio
O núcleo da IMPACTO **não conhece fornecedor**. Ele depende de contratos internos (`backend/impacto/integrations/contracts.py`).
Cada fornecedor é um **adapter** que traduz entre o formato externo e o **modelo canônico** do domínio.

```
            NÚCLEO (projetos, documentos, cursos, cobrança, suporte…)
                              │  contratos internos
                              ▼
                     ┌─────────────────┐
                     │ INTEGRATION HUB │  jobs · eventos · mapeamento · IDs externos · saúde · auditoria
                     └─────────────────┘
                              │  IntegrationAdapter (Protocol)
        ┌────────────┬────────┴────────┬────────────┬───────────┐
        ▼            ▼                 ▼            ▼           ▼
   REST genérico  Senior/Sapiens    TOTVS       Governo     BI/exportação
                  (REST + SOAP)  (Protheus/RM/  (Gov.br/
                                   Datasul)      Conecta)
```
Adicionar um fornecedor novo = criar um adapter + uma linha no catálogo. **Nenhum arquivo do núcleo muda.**

## 2. O que foi PRESERVADO (não reescrito)
A auditoria (`INTEGRATION_INVENTORY.md`) mostrou mecanismos já maduros. Eles foram reutilizados:
| Já existia | Como o hub usa |
|---|---|
| `adapters/http_client.py` — HTTPS obrigatório, bloqueio de IP privado/loopback/link-local (metadados de nuvem), sem seguir redirecionamento | é o transporte de TODA chamada externa; o hub só acrescentou classificação de erro, jitter, disjuntor e correlação |
| `defusedxml` | leitura de XML/SOAP (XXE, entidade externa e "billion laughs" recusados) |
| `security/crypto.FieldCipher` (Fernet com rotação, usado no MFA) | cifra das credenciais de integração e do segredo de assinatura de webhook |
| `services/documents` (tamanho, extensão, assinatura binária, zip bomb, antivírus) | todo arquivo importado vem de um documento JÁ validado pelo cofre |
| `adapters/storage` + URL temporária assinada | entrega dos arquivos exportados |
| `services/audit` (`audit_events`, com cadeia de hash) | auditoria de toda operação de integração |
| `job_runs` + `jobs.py` | o trabalhador `integration_ops` roda no agendador existente |
| RLS por organização | isolamento de conexões, credenciais, jobs, eventos, correspondências, importações |
| Padrão de idempotência do `billing_events` (UNIQUE no banco) | dedupe de mensagens de entrada e unicidade de jobs |

## 3. Peças novas
| Peça | Tabela | Para quê |
|---|---|---|
| Catálogo de provedores | `integration_providers` | matriz de capacidades e **maturidade real**; sincronizado de `config/integration_providers.json` |
| Conexão | `integration_connections` | uma configuração por organização × provedor × ambiente (development/sandbox/homologation/production), com estado de saúde e disjuntor |
| Credencial | `integration_credentials` | cifrada; o papel da aplicação **não tem SELECT** na coluna do segredo (leitura só pela função `integration_secret()`), ou apenas a referência para um gerenciador externo |
| Mapeamento | `integration_mappings` | campo externo → campo canônico, com 12 transformações declaradas (sem `eval`) |
| ID externo | `external_entity_links` | correspondência interno ↔ externo com versão e **estado de conflito** |
| Job | `integration_jobs` | idempotente por `(org_id, idempotency_key)`, com tentativas, erro classificado e correlação |
| Evento (outbox) | `integration_events` | eventos REAIS do domínio, gravados na mesma transação do fato |
| Assinatura / entrega | `integration_subscriptions`, `integration_deliveries` | webhook de saída assinado (HMAC), com backoff, dead-letter e replay |
| Entrada | `integration_inbound` | dedupe por `(conexão, id do evento externo)` garantido pelo banco |
| Importação | `integration_imports`, `integration_import_rows` | pipeline com pré-visualização e **aprovação humana** |
| Exportação | `integration_exports` | datasets fixos por organização (BI sem acesso ao banco) |

## 4. Fluxos
**Entrada por API (pull):** job enfileirado → trabalhador → adapter `pull` → mapeamento → canônico → correspondência de ID externo (conflito registrado) → resultado + auditoria.
**Saída por API (push):** registros canônicos → `map_outbound` → adapter `push` → ID externo devolvido é registrado.
**Entrada por webhook:** `POST /v1/integrations/inbound/{connection_id}` → adapter verifica assinatura → dedupe no banco → **enfileira job** (a requisição nunca processa negócio) → `202`.
**Saída por webhook:** o núcleo chama `events.emit()` na transação do fato → entregas pendentes → trabalhador assina (`t=…,v1=…`) e entrega → retry/dead-letter/replay.
**Arquivo:** upload no cofre → `validate` → `parse` → `map` → `preview` → **approve** (papel `owner`) → `import` → auditoria.
**Exportação:** dataset → transformação (CSV com fórmula neutralizada) → documento gerado → URL temporária.

## 5. Resiliência
Teto de tempo por chamada; 3 tentativas com espera exponencial **e jitter**; erro **temporário** (408/425/429/5xx, rede, timeout) é repetido, **permanente** (4xx de conteúdo) não; **disjuntor** por conexão abre após 5 falhas consecutivas e corta chamadas por 5 minutos (protege o sistema externo e o nosso); dead-letter após 6 tentativas de entrega; replay só de dead-letter e só pela própria organização. Nada disso roda dentro da requisição HTTP: sincronização é sempre job.

## 6. Modelo canônico
Entidades do domínio REAL: `person`, `organization`, `document`, `course`, `certificate`, `event`, `invoice`, `payment`, `partner`, `call`. Dinheiro sempre inteiro em centavos; datas ISO 8601 com fuso. O **ID interno nunca é substituído** pelo externo: a correspondência vive em `external_entity_links`.

## 7. Conflitos (nunca sobrescrever em silêncio)
`links.detect_conflict` decide: mesma versão externa → `unchanged` (idempotente); versão externa mais nova → `apply`; alterado **dos dois lados** → `conflict` registrado com os dois carimbos de tempo, e o dado interno é preservado. Registro apagado no sistema externo → `deleted_externally` (a IMPACTO **não** apaga nada por isso). Conflitos aparecem em `GET /v1/integrations/links?sync_status=conflict`.

## 8. Limites declarados
Nenhuma integração está homologada. SFTP é contrato reservado (**SCAFFOLDED / NOT IMPLEMENTED**). Governo exige **EXTERNAL AUTHORIZATION REQUIRED**. SAML e LDAP/AD: não implementados. WhatsApp/SMS/push: não implementados. Importação por upload aceita `.csv` e `.xlsx` (JSON/XML entram por conexão REST/SOAP) porque a allowlist do cofre de documentos **não foi enfraquecida**. Acesso direto ao banco de ERP não é estratégia suportada.
