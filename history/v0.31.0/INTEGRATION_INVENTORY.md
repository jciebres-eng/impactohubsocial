# INTEGRATION_INVENTORY — o que REALMENTE existe (auditoria do repositório)

Auditoria feita sobre o código, as migrations e o banco — não sobre a documentação anterior.
Classificação: **IMPLEMENTED** (funciona e é testado) · **PARTIAL** (funciona com limite relevante) · **SCAFFOLDED** (contrato/estrutura pronta, sem integração real) · **PLANNED** · **BLOCKED** (depende de terceiro) · **NOT_APPLICABLE**.
Regra de honestidade: **dublê de HTTP, mock ou gravação local nunca é classificado como IMPLEMENTED.**

## 1. Integrações e mecanismos que já existiam (preservados)
| Nome | Categoria | Status | Código | Autenticação | Entrada → Saída | Riscos | Testes | Homologação | Produção |
|---|---|---|---|---|---|---|---|---|---|
| **Importador de editais (feeds)** | Dados externos | **IMPLEMENTED** (mecanismo) / BLOCKED (fontes reais) | `jobs.py: import_source/parse_feed/import_all`, tabela `call_sources` | nenhuma (feeds públicos) | JSON/CSV/RSS → `calls` (upsert idempotente por `source_id+source_reference`) | fonte muda formato; termos de uso da fonte | job testado; parsing testado | n/a | fontes precisam ser ativadas manualmente após revisão dos termos |
| **Webhook Stripe (entrada)** | Pagamentos | **PARTIAL** (dublê HTTP; nunca chamou o Stripe real) | `services/billing.py`, `api/billing_routes.py`, tabela `billing_events` | HMAC `Stripe-Signature` + janela de 300 s | evento assinado → assinatura/fatura | provedor real não homologado | assinatura inválida, duplicado, replay, fora de ordem, **duplicado concorrente** | **HOMOLOGATION REQUIRED** | **EXTERNAL AUTHORIZATION REQUIRED** |
| **Cliente HTTP de saída** | Infraestrutura | **IMPLEMENTED** | `adapters/http_client.py` | por chamador | retries em 429/5xx, backoff exponencial, **sem seguir redirecionamento**, **guarda de SSRF** (só HTTPS; bloqueia IP privado/loopback/link-local/reservado/multicast) | DNS rebinding residual (mitigar no egress) | testado | n/a | n/a |
| **Storage de objetos** | Arquivos | **PARTIAL** (local real; S3 por assinatura SigV4 sem bucket real) | `adapters/storage.py` | SigV4 | upload/download por URL temporária | credenciais de nuvem ausentes | SigV4 com vetor público oficial | **INFRASTRUCTURE DEPENDENCY** | pendente |
| **Antivírus** | Arquivos | **SCAFFOLDED** | `adapters/antivirus.py` | n/a | clamd | sem clamd real | dublê | **INFRASTRUCTURE DEPENDENCY** | pendente |
| **E-mail** | Comunicação | **PARTIAL** (outbox real; SMTP nunca exercitado) | `adapters/mail.py` | SMTP user/pass | mensagem → .eml/SMTP | SPF/DKIM/DMARC ausentes | outbox, reenvio sem duplicar | **INFRASTRUCTURE DEPENDENCY** | pendente |
| **SSO OIDC** | Identidade | **PARTIAL** (IdP falso nos testes) | `services/oidc.py` | OIDC code flow + PKCE | provedor → sessão | IdP real não testado | fluxo testado com IdP dublê | **HOMOLOGATION REQUIRED** | pendente |
| **Importação de extrato bancário** | Arquivos | **IMPLEMENTED** | `api/finance_routes.py`, `statement_imports`/`statement_lines` | sessão da organização | CSV/OFX → linhas conciliáveis | formato por banco | testado | n/a | uso interno |
| **Gateway de IA** | IA | **SCAFFOLDED/PARTIAL** | `engines/ai/gateway.py` | chave por provedor | provedor local por padrão | provedor externo não escolhido | dublê | **LEGAL VALIDATION REQUIRED** (DPA) | pendente |
| **Jobs agendados** | Infraestrutura | **IMPLEMENTED** | `jobs.py` + `job_runs` | n/a | execução periódica com histórico e lock | sem fila distribuída | testado | n/a | exige agendador no deploy |
| **Auditoria** | Governança | **IMPLEMENTED** | `services/audit.py` + `audit_events` | n/a | ação → registro (ator, org, objeto, IP, request_id) | — | testado | n/a | ok |
| **Observabilidade** | Operação | **IMPLEMENTED** | `observability.py` | n/a | logs estruturados com **redação de segredos**, métricas, trace/correlation ID | sem coletor em produção | testado | n/a | **INFRASTRUCTURE DEPENDENCY** |

## 2. Lacunas encontradas (o que NÃO existia antes desta etapa)
1. **Conexões por organização**: todas as integrações eram globais da plataforma (`call_sources`, provedor de cobrança, storage, e-mail). Um cliente com TOTVS e outro com Sapiens não tinham como ter configurações próprias.
2. **Credenciais de integração**: só variáveis de ambiente. Sem cofre por conexão, sem rotação, sem expiração.
3. **Mapeamento de ID externo**: só `calls.source_reference`. Nenhuma entidade do domínio (pessoa, organização, documento, certificado, fatura) tinha correspondência com sistema externo.
4. **Jobs de integração**: `job_runs` é histórico de job da plataforma, sem conexão, direção, entidade, tentativa, correlação nem chave de idempotência.
5. **Eventos de domínio e webhooks de saída**: não existiam (só o webhook de entrada do Stripe). Nenhum parceiro podia ser notificado.
6. **Deduplicação genérica de entrada**: existia só para o Stripe (`billing_events`).
7. **Catálogo de provedores e matriz de capacidades**: inexistente.
8. **Estado de saúde por conexão**: só `call_sources.last_status`.
9. **Mapeamento como dado** (campo→campo, enum, data, moeda): o importador tinha mapa fixo em código.
10. **Pipeline de importação com pré-visualização e aprovação**: `import_source` grava direto; `statement_imports` não tem etapa de aprovação.
11. **Exportação/datasets para BI**: inexistente (só relatórios prontos).
12. **SOAP/XML**: havia leitura de RSS com defusedxml, mas nenhum envelope SOAP.
13. **Dead-letter, replay controlado e disjuntor (circuit breaker)**: inexistentes.

## 3. Decisão de arquitetura (o que foi preservado em vez de reescrito)
Seguindo a regra "não substituir por dogma": `HttpClient` (com a guarda de SSRF), `defusedxml`, `audit_events`, `job_runs`, `documents` (validação de upload, magic bytes, zip bomb), `storage`, RLS por organização e o padrão de idempotência do `billing_events` **foram reutilizados** pelo Integration Hub. O que foi criado é a camada que faltava: contratos, conexões, credenciais, mapeamentos, IDs externos, jobs, eventos/outbox, webhooks de saída, dedupe de entrada, saúde, importação com aprovação e exportação. Detalhe em `INTEGRATION_ARCHITECTURE.md`.
