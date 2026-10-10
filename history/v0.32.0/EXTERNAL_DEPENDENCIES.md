# Dependências externas — o que a plataforma NÃO faz sozinha

Este documento existe para que ninguém descubra em produção que algo "não estava integrado". Para cada dependência:
o que ela faz, o que acontece hoje sem ela, o que falta, e como a plataforma se comporta quando ela falha.

**Regra que vale para todas:** dependência ausente produz **indisponibilidade explícita** (erro nomeado, estado
`unavailable`, resposta 501/503 com a dependência citada). Nunca sucesso falso, nunca dado inventado, nunca
"funcionou em modo demonstração" sem dizer.

## 1. Identidade e assinatura

| Dependência | Para quê | Hoje | Falta | Comportamento |
|---|---|---|---|---|
| **Certificado ICP-Brasil** (A1/A3 + AC credenciada) | assinatura **qualificada** | `signature_providers.icp_brasil` = `unavailable` | certificado, biblioteca PAdES/CAdES, política, ACT, consulta de revogação, homologação | gatilho no banco **recusa** a assinatura; a rota de administração recusa promover a produção (409 `cannot_promote`) |
| **Gov.br** (Conecta / Assinatura Eletrônica) | assinatura **avançada** com certificado | `signature_providers.govbr` = `unavailable` | credenciamento com `client_id` e escopo aprovados, fluxo OIDC, guarda do PKCS#7 | mesma recusa do banco |
| **ACT / RFC 3161** | carimbo de tempo com validade externa | não contratado | contrato com Autoridade de Carimbo do Tempo + implementação do protocolo | `POST /v1/trust/timestamps` responde **501 `tsa_not_configured`**; o carimbo **interno** (HMAC do servidor) funciona e é identificado como interno |
| **Provedor de biometria** | verificação biométrica de identidade | não contratado | contrato + integração + política de retenção de dado biométrico | **501 `provider_not_configured`** |
| **Provedor de SMS** | confirmar telefone | não contratado | contrato + integração | **501 `channel_unavailable`** |

Detalhe completo em `SIGNATURE_VALIDATION_MATRIX.md`.

## 2. Infraestrutura da aplicação

| Dependência | Variável | Padrão | Sem ela | Exigida em produção? |
|---|---|---|---|---|
| **PostgreSQL 16** | `DATABASE_URL` | — | a aplicação não sobe | **sim** (é o núcleo, não um complemento) |
| **SMTP** | `MAIL_PROVIDER=smtp` + `SMTP_*` | `console` (escreve no diretório `outbox/`) | confirmação de e-mail, convite, código de assinatura e aviso não saem | **sim** — a validação de configuração **recusa** `console` em staging/produção |
| **Armazenamento S3** | `STORAGE_PROVIDER=s3` + `S3_*` | `local` (disco) | funciona em uma máquina só; não serve a mais de uma instância | recomendado; a validação exige bucket e credencial quando `s3` |
| **Antivírus (clamd)** | `ANTIVIRUS_PROVIDER=clamd` | `none` | documento fica `pending_scan` e **não é promovido a `clean`** | recomendado; sem ele, `ALLOW_UNSCANNED_DOWNLOADS` controla se o arquivo pode ser baixado |
| **Stripe** (cobrança PRÓPRIA: contratos avulsos/parcelados — não há assinatura, ADR-341) | `STRIPE_SECRET_KEY` + `STRIPE_WEBHOOK_SECRET` | vazias → provedor **simulado** (toda cobrança nasce `is_simulated`) | sem cobrança real; o simulado nunca entra na receita real | só se houver cobrança própria |
| **Chave PIX da plataforma** (linha "infraestrutura e inteligência" das instruções de repasse) | `PLATFORM_PIX_KEY` + `PLATFORM_PIX_KEY_TYPE` | vazias → a instrução sai como "NÃO CONFIGURADA" | o financiador não tem para onde transferir a camada da plataforma; a linha fica instruída sem chave | sim, quando a regra comercial for ativada |
| **Provedor de IA** | `AI_PROVIDER` + `AI_API_KEY` + `AI_MODEL` | `local` (motor próprio, sem rede) | o assistente usa o motor local, mais simples, e diz que é assistência | opcional |
| **OIDC** | `OIDC_*` | desligado | login só por senha + segundo fator | opcional |

A validação de configuração (`backend/impacto/config.py`) **falha na subida** quando o ambiente é staging ou
produção e algo acima está incoerente. É melhor não subir do que subir prometendo o que não entrega.

## 3. Integration Hub — maturidade declarada por provedor

`integration_providers.maturity` tem cinco estados, e nenhum deles é "integrado" por otimismo:

| Provedor | Categoria | Maturidade |
|---|---|---|
| `oidc_identity` | identidade (Google, Microsoft, Gov.br, Keycloak) | `contract_tested` |
| `stripe_payments` | pagamento | `contract_tested` |
| `email_smtp` | comunicação | `contract_tested` |
| `totvs` | ERP (Protheus, RM, Datasul) | `contract_tested` |
| `senior_sapiens` | ERP | `contract_tested` |
| `bi_export` | exportação de dataset | `contract_tested` |
| `generic_rest` | API REST própria da organização | `contract_tested` |
| `government_api` | governo (Gov.br, Conecta, APIs federais/estaduais/municipais) | `scaffolded` |
| `sftp_batch` | arquivo em lote por SFTP | `scaffolded` |

O que cada estado significa:

- **`scaffolded`** — existe a estrutura (conexão, credencial, job, evento), **não há** teste contra o sistema real.
- **`contract_tested`** — o contrato foi testado contra um duplo local que segue a especificação. **Não** significa
  que já rodou contra o sistema do cliente.
- **`sandbox`**, **`homologated`**, **`production_active`** — só a administração promove, com evidência. Um deploy
  **nunca** promove: o arquivo de configuração só pode manter ou rebaixar.

**Nenhum provedor está em `production_active` nesta versão.** Dizer o contrário seria afirmar integração que não
foi exercitada contra o sistema de ninguém.

Detalhe em `INTEGRATION_CAPABILITY_MATRIX.md` e `INTEGRATION_OPERATIONS.md`.

## 4. Como a plataforma se comporta quando a dependência falha

| Mecanismo | O que faz | Onde |
|---|---|---|
| **Verificação de saúde** | cada conexão tem `health_state` e detalhe, com data | `integration_connections` |
| **Disjuntor** | após 5 falhas seguidas, a conexão abre o circuito e para de tentar | `integrations/jobs.py` |
| **Nova tentativa com espera crescente** | entrega de webhook tenta com intervalo progressivo | `integrations/events.py` |
| **Carta morta** | depois do limite, a entrega vira `dead_letter` e aparece para a administração | `integration_deliveries` |
| **Estado de indisponibilidade** | provedor com problema vira `degraded`/`unavailable`, visível na interface | `signature_providers`, `integration_providers` |
| **Erro explícito** | 501 com a dependência nomeada; 503 quando o banco está indisponível | `http.py` |
| **Sem sucesso falso** | nenhuma rota devolve 200 simulando o que não aconteceu | testado em `test_v0130_integrations.py`, `test_v0140_trust.py` |

## 5. Bibliotecas de terceiros em execução

| Camada | Dependência | Por quê |
|---|---|---|
| Backend | Python 3.13 (biblioteca padrão) + Starlette + `cryptography` + `libpq` via ctypes | tudo que não é padrão está em `THIRD_PARTY_DEPENDENCIES.md` com licença |
| Frontend | React 19 + TypeScript + esbuild | sem biblioteca de componentes de terceiro: o `kit` é próprio |
| Documentos | **nenhuma** | DOCX/XLSX/ODT/ODS/PDF/QR são escritos pela plataforma (`DOCUMENT_FORMATS.md`) |

A ausência de biblioteca de documento não é purismo: os registros de pacote (npm e PyPI) estão **bloqueados** neste
ambiente de construção, e a decisão foi escrever o mínimo necessário em vez de depender de algo que não pode ser
instalado aqui. O custo está registrado em `DECISIONS.md`.

## 6. Resumo honesto

| Pergunta | Resposta |
|---|---|
| A plataforma funciona sozinha, ponta a ponta, em um servidor? | **Sim**, com PostgreSQL. E-mail cai no diretório `outbox/`. |
| Ela pode ir a produção sem nenhuma contratação externa? | **Não**: precisa de SMTP real. O resto é opcional ou degrada com aviso. |
| Alguma assinatura com validade qualificada funciona hoje? | **Não.** Avançada da plataforma funciona; ICP-Brasil e Gov.br estão indisponíveis. |
| Algum ERP, banco ou órgão público está integrado de verdade? | **Não.** O mais maduro é `contract_tested`. |
| A plataforma finge em algum lugar? | Não que tenhamos encontrado — e é por isso que este documento existe e é testado. |
