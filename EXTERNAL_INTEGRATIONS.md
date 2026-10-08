# EXTERNAL_INTEGRATIONS — o que depende de terceiros, e o estado REAL de cada item (v0.27.0)

Exigido pelo PROMPT MASTER FINAL. Este documento responde, para cada integração externa: **existe?**, **está
simulada?** (nunca), **o que a plataforma faz sem ela**, **o que falta** e o **status objetivo**. A regra absoluta
da rodada vale aqui: **nada é simulado como se fosse real** — biometria, assinatura qualificada, ICP-Brasil,
gov.br, SMS, ACT, Stripe ao vivo, provedor fiscal, KYC, identidade governamental, banco e PIX real. Onde falta o
terceiro, a resposta é explícita (`501`/`503` nomeado, estado `unavailable`, `BLOCKED_EXTERNAL_DEPENDENCY`).

Fontes derivadas: `docs/execution/INTEGRATION_HOMOLOGATION_MATRIX.csv` (gerada por
`scripts/make_integration_matrix.py`), `EXTERNAL_DEPENDENCIES.md`, `SIGNATURE_VALIDATION_MATRIX.md`,
`backend/impacto/config.py`.

| Integração | Para quê | Estado nesta instalação | Comportamento sem ela | O que falta (externo) | Status |
| --- | --- | --- | --- | --- | --- |
| PostgreSQL 16 | núcleo | **ativo** (local/CI) | a aplicação não sobe | — | VERDE |
| SMTP | e-mail transacional | `console` (outbox em disco) | mensagens não saem; produção recusa `console` | credencial SMTP | BLOCKED_EXTERNAL_DEPENDENCY |
| S3 | armazenamento de objeto | `local` | uma instância só | bucket + credencial | BLOCKED_EXTERNAL_DEPENDENCY |
| ClamAV | antivírus de upload | `none` | documento fica `pending_scan` | serviço clamd | BLOCKED_EXTERNAL_DEPENDENCY |
| Stripe (cobrança PRÓPRIA) | contratos avulsos/parcelados da plataforma — **não há assinatura (ADR-341)** | chaves vazias → **simulado** por construção | cobrança nasce `is_simulated`; nunca entra na receita real | chave ao vivo + webhook + homologação | BLOCKED_EXTERNAL_DEPENDENCY |
| Banco / extrato | conciliação bancária | **não existe** | torre MASTER diz `DADO FINANCEIRO NÃO CONECTADO`; conciliação é manual com nota | integração bancária (Open Finance) + parecer | BLOCKED_EXTERNAL_DEPENDENCY |
| PIX (chave da plataforma) | destino da linha "infraestrutura e inteligência" nas instruções de repasse | `PLATFORM_PIX_KEY` vazia → instrução "NÃO CONFIGURADA" | a chave das OUTRAS partes vem do contrato (informada por cada parte, validada por tipo) e funciona | chave PIX real da pessoa jurídica titular | BLOCKED_EXTERNAL_DEPENDENCY |
| Provedor de pagamento PIX/boleto | gerar cobrança PIX/boleto real | **não contratado** | `charge_pix`/`charge_boleto` só com provedor simulado | contrato + homologação | BLOCKED_EXTERNAL_DEPENDENCY |
| Nota fiscal de serviço (NFS-e) | faturar a taxa de serviço | **não implementado** | carta legal diz "obrigatória e não implementada" | provedor fiscal + município + regime | BLOCKED_EXTERNAL_DEPENDENCY |
| Parecer jurídico/contábil da taxa de serviço | ativar `contract.platform_service_fee` | carta AMARELA | camada registrada e instruída; **nada devido, nada cobrado** | parecer (Lei 12.865/2013, ISS) | BLOCKED_EXTERNAL_DEPENDENCY |
| ICP-Brasil (A1/A3) | assinatura qualificada | `unavailable` | banco recusa assinar com provedor indisponível | certificado + AC + ACT | BLOCKED_EXTERNAL_DEPENDENCY |
| Gov.br (assinatura/identidade) | assinatura avançada e identidade governamental | `unavailable` | mesma recusa; identidade governamental não é simulada | credenciamento OIDC gov.br | BLOCKED_EXTERNAL_DEPENDENCY |
| ACT / RFC 3161 | carimbo de tempo externo | não contratado | `501 tsa_not_configured`; carimbo interno identificado como interno | contrato ACT | BLOCKED_EXTERNAL_DEPENDENCY |
| Biometria | verificação biométrica | não contratado | `501 provider_not_configured` | contrato + política de retenção | BLOCKED_EXTERNAL_DEPENDENCY |
| KYC / validação de identidade | identidade documental com terceiro | não contratado | validação documental interna com fila humana; **nunca** marcada como KYC externo | contrato KYC | BLOCKED_EXTERNAL_DEPENDENCY |
| SMS | confirmar telefone | não contratado | `501 channel_unavailable` | contrato | BLOCKED_EXTERNAL_DEPENDENCY |
| OIDC corporativo (Google/Microsoft) | login federado | desligado | senha + segundo fator | `OIDC_*` | opcional |
| Modelo de linguagem externo | assistência | `local` (motor próprio) | assistente local, dito como assistência | `AI_API_KEY` + `AI_MODEL` | opcional |
| APIs governamentais (dados públicos, Conecta) | acompanhamento longitudinal com dado governamental | **só importação por arquivo/feed**; nenhuma API ao vivo | dados territoriais vêm de importação declarada com fonte e data | credencial Conecta / APIs | BLOCKED_EXTERNAL_DEPENDENCY |
| ERPs (TOTVS, Senior), SFTP, BI | Integration Hub | adaptadores `contract_tested`/`scaffolded` contra duplo | sem credencial, nenhuma conexão ao vivo | credencial por conexão | BLOCKED_EXTERNAL_DEPENDENCY |

## Regras que valem para toda a tabela

1. **Nenhuma linha está "em produção" por otimismo.** `production_active` só existe com credencial configurada
   E teste de contrato — hoje, zero (`make_integration_matrix.py`).
2. **Simulado nunca entra no real.** `platform_charges.is_simulated` é derivada do provedor por gatilho; a receita
   real desta instalação é **R$ 0,00** por construção e a torre MASTER diz isso.
3. **Dependência ausente = indisponibilidade explícita.** Erro nomeado, estado `unavailable`, ou
   `BLOCKED_EXTERNAL_DEPENDENCY` neste documento. Nunca sucesso falso.
4. **O que é da plataforma funciona sem terceiro:** matriz de distribuição, instruções de repasse com a chave PIX
   informada no contrato, registro e confirmação de transferência entre as partes, conciliação com nota, livro
   econômico, reconhecimentos, torres. É a camada de orquestração — não de custódia (ADR-284).

## O que NÃO será simulado nem "ligado" nesta rodada

Biometria, assinatura qualificada, ICP-Brasil, gov.br, SMS, ACT, Stripe real, provedor fiscal, KYC, identidade
governamental, banco e PIX real. Qualquer um deles aparece em produção só depois de contrato, credencial em
segredo (nunca no repositório) e homologação registrada em `INTEGRATION_HOMOLOGATION_MATRIX.csv`.
