# Economia do SaaS — IMPACTO v0.30.0

Resposta ao superprompt de monetização ("pagador → valor entregue → evento de cobrança → preço/intervalo de hipótese → custo → margem →
alternativa → vantagem defensável") **a partir do catálogo real** (`monetization_rules`, 11 regras, **0 ativas**; ADR-341, ADR-337, ADR-349).
Tudo que é número é **[PREMISSA]** (hipótese declarada); nada aqui é preço aprovado, pesquisa de mercado ou projeção. Receita real desta
instalação: **R$ 0,00**.

## 0. O que o pacote propôs e o que o repositório decidiu

| Proposta (contexto do pacote) | Decisão do proprietário | Onde |
|---|---|---|
| Take rate 2–5 % retido automaticamente na liberação | Taxa de serviço **3,5 %** + participação de autoria **1,5 %**, do catálogo, congelados no acordo, **nunca descontados de dinheiro em trânsito**; regra inativa até parecer | ADR-337, `MONETIZATION_LEGAL_MATRIX.md` |
| Assinatura corporativa (SaaS B2B/B2G mensal) | **Não existe assinatura**; pacotes de capacidades por concessão/convênio/contrato avulso; `saas.institutional.funder` e `b2g.territorial_governance` estão **recusadas** no catálogo | ADR-341 |
| Selo pago de replicabilidade | Selo só por critério e fato; nunca por pagamento | ADR (selos) |
| Escrow / conta gráfica | Não custodial; nenhuma fintech dentro do produto | ADR-284 |

## 1. Mapa pagador → valor → evento → preço-hipótese → custo → margem → alternativa → vantagem

| Regra (catálogo) | Pagador | Valor entregue | Evento de cobrança | Preço / intervalo [PREMISSA] | Custo variável | Custo fixo | Margem | Alternativa ao IMPACTO | Vantagem defensável | Estado |
|---|---|---|---|---|---|---|---|---|---|---|
| `contract.platform_service_fee` | financiador (empresa/instituto; governo quando cabível) | operação financiada rastreada: acordo como regra, evidência por marco, instrução e confirmação de repasse, quitação, reconhecimento | **quitação** da operação (entrega aceita + repasses confirmados) | 3,5 % do valor financiado (catálogo; congelado no acordo) | ~0 (registro; sem provedor) | hospedagem, suporte, equipe editorial | [PREMISSA] — custo não medido (`UNIT_ECONOMICS.md`) | planilha + e-mail + auditoria manual | evidência com proveniência, quatro olhos no banco, trilha encadeada, contestação | review_required · **inativa** |
| participação de autoria (1,5 %) | financiador | reconhecimento do proponente que estruturou a proposta | quitação | 1,5 % (catálogo) — **não é receita da plataforma** | — | — | — | — | — | inativa |
| `implementation.setup` | financiador / governo | implantação com histórico integrado | contrato avulso | valor negociado por quem tem alçada (`finance.approve`) | horas de implantação | — | [PREMISSA] | consultoria | dado já estruturado no produto | review_required |
| `enterprise.esg_portfolio` | empresa | prova rastreável do investimento social (ESG/ODS) com evidência | contrato avulso | negociado | relatório/consolidação | — | [PREMISSA] | consultoria ESG | mesma base de evidência das operações | review_required |
| `ai.credits_prepaid` | OSC/pessoa/financiador (quem usa IA) | operação de inteligência executada (prévia, custo, débito só em sucesso) | execução `succeeded` (créditos) | pacotes-hipótese (`ai_credit_packs`, status `hypothesis`); modo **piloto** | custo do provedor (não medido: `AI_PROVIDER=local`) | — | `AI_COST_MODEL.md` (operação deficitária nomeada) | ferramenta genérica de IA | custo mostrado antes, cota gratuita, patrocínio | review_required · piloto |
| `premium.readiness_analysis` / `premium.document_preparation` | OSC | análise de prontidão / documento montado a partir do domínio | evento de valor (unidade) | hipótese | — | — | [PREMISSA] | consultor | 8 dimensões, versões imutáveis, origem por campo | review_required |
| `marketplace.take_rate` | OSC | encontrar e contratar prestador | transação | — | — | — | — | — | — | **recusada** (onerar OSC) |
| `success_fee.funding` | OSC | custo alinhado ao momento de valor | transação | — | — | — | — | — | — | **recusada** (pay-to-win) |
| `saas.institutional.funder` / `b2g.territorial_governance` / `data.territorial_intelligence` | financiador / governo | painéis, governança territorial, inteligência de dados | contrato | — | — | — | — | — | — | **recusadas** (assinatura; dado público não se vende) |

**Gratuidade:** acesso ao núcleo (cadastro, diagnóstico, projeto, candidatura, evidência, prestação de contas) é gratuito por desenho
(`FREE_ACCESS`), e nenhuma função de proteção, correção ou prestação de contas fica atrás de pagamento (`test_v0270_no_subscription`).
Não há "transição de campanha" com data: a regra efetivamente aprovada é "sem assinatura" (ADR-341) — o conflito apontado pelo
superprompt (gratuidade × transição) **não existe** no repositório porque não há cobrança recorrente a transicionar.

## 2. Mapa tela/ação → ator → valor → evento → regra → comprovante → estorno/contestação

| Tela / ação | Ator | Valor | Evento | Regra | Comprovante | Estorno / contestação |
|---|---|---|---|---|---|---|
| `/acordos` → ativar acordo de financiamento | financiador + OSC (assinaturas) | cláusulas viram regra | `agreement_activated` (ledger) | `contract.platform_service_fee` (registrada, **não exigível** com regra inativa: `allocation_payouts.state = 'awaiting_rule'`) | versão do acordo com hash | nova versão do acordo (`superseded`) |
| ficha do acordo → matriz e instruções | partes | quem paga → quem recebe → chave PIX | `allocation_computed`, `payout_instructed` | — | matriz com hash | `cancelled`/`refund_pending` por decisão das partes |
| registrar transferência / confirmar | pagador / recebedor | repasse rastreado | `payout_registered` → `payout_confirmed` → `operation_settled` | — | referência + documento | `disputed`; conciliação (`billing.write`) |
| Central de IA → prévia → confirmar | quem usa | operação de inteligência | `ai.analysis_completed` (valor) / consumo de crédito | `ai.credits_prepaid` | extrato de créditos | falha/parcial não cobra; contestação de análise (`similarity_disputes`) |
| pedido de créditos (piloto) | organização | créditos promocionais | `ai_credit_orders` (pilot) | — | pedido + aprovação `billing.write` | cancelamento do pedido |
| proposta comercial avulsa → aceite | quem tem alçada / cliente | pacote de capacidades | `offer_acceptances` | `implementation.setup` etc. | aceite com termos | contrato encerrado; pacote volta a FREE_ACCESS |

## 3. Projeção e sensibilidade

`24_MONTH_FINANCIAL_MODEL.md` (gerado, conferido por teste): 3 cenários × 24 meses sobre 3,5 %, com **sensibilidade do take rate em
2 / 3 / 3,5 / 4 / 5 %** (quem suporta nos dois modos `deducted`/`additional`, efeito no líquido do projeto, receita possível). Custo,
churn, CAC, inadimplência, impostos e taxa de gateway **não estão modelados**: não há provedor, nem histórico, nem pesquisa — pôr número
seria inventar (`UNIT_ECONOMICS.md` diz o que falta medir e como).

## 4. Matriz de elegibilidade de cobrança por ator e evento (para revisão jurídica/contábil antes de ativar)

| Ator | Evento | Pode ser cobrado? | Condição | Carta |
|---|---|---|---|---|
| Financiador | quitação de operação | sim, por contrato assinado com cláusula de taxa | regra ativa + parecer (natureza: serviço de software; ISS; NFS-e) | amarela |
| Financiador / governo | contrato avulso (implantação, ESG) | sim | proposta por quem tem alçada + aceite | amarela |
| OSC | acesso ao núcleo | **não** (por desenho) | — | — |
| OSC | prontidão/documento premium | hipótese | preço publicado + parecer | amarela |
| Qualquer um | créditos de IA | só em modo real com regra ativa + provedor + webhook | hoje: piloto, promocional, R$ 0,00 | amarela |
| OSC | take rate de marketplace / success fee | **não** | recusado | vermelha |
| Governo | assinatura / venda de dado territorial | **não** | recusado | vermelha |

Fiscal: quem presta é a plataforma (serviço de software); quem fatura é a plataforma ao pagador do contrato; documento fiscal: NFS-e
(**não emitida**: sem provedor fiscal, `BLOCKED_EXTERNAL`); a plataforma **nunca** emite documento em nome de terceiro nem fatura o
repasse projeto ↔ OSC (não é parte dele).
