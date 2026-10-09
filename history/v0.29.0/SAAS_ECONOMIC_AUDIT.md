# Auditoria econômica do SaaS — FASE 1 (v0.16.0)

Primeira fase da ordem obrigatória do prompt mestre: **inspecionar o estado real antes de modificar
qualquer código.** Nada aqui vem de leitura de documento: cada linha foi conferida por consulta ao
banco (`impacto_dev`, 231 tabelas, 17 migrações) ou ao código (704 rotas).

Legenda: **🟢 FUNCIONAL** (existe e é provado por teste) · **🟡 PARCIAL** (existe, incompleto para o
papel econômico) · **🔴 INEXISTENTE** · **⚠️ ANUNCIADO SEM LASTRO** (o produto promete, o código não
entrega).

---

## 1. Matriz dos 16 itens que o mapa de valor aponta como possíveis lacunas

| # | Item | Estado | Evidência real | Problema econômico | P | Ação |
|---|---|---|---|---|---|---|
| 1 | **Program Management** | 🟡 | `calls` (editais) + `funding_quotas`; o limite `programs` do plano é aplicado contra `calls` (`call_routes.py:167`) | **Não existe entidade Programa** que agregue orçamento + oportunidades + projetos + organizações + território + contratos + indicadores + evidências + resultados. É exatamente a unidade que o mapa diz que financiador e governo compram | **P1** | criar `programs` como entidade de primeira classe |
| 2 | **Project Readiness Score** | 🟢 | `readiness@1.0.0`, 6 dimensões, cada verificação com explicação e o que falta; `readiness_snapshots` append-only | nenhum — está pronto e é monetizável como está | — | ligar a evento de valor |
| 3 | **Opportunity Matching** | 🟢 | `match-engine@1.2.0` com 4 versões viajando no resultado, explicável, com retorno humano e **sem treino automático** | nenhum | — | ligar a evento de valor |
| 4 | **Funding Lifecycle** | 🟡 | `applications` → `commitments` → `payment_records` → `project_funding()`; `investment_intents`, `quota_pledges` | falta **cronograma de desembolso** e **obrigações** como objetos; hoje o desembolso é um registro, não uma agenda com vencimento e evidência exigida | **P2** | modelar `disbursements` e `obligations` |
| 5 | **Evidence Management** | 🟢 | `evidences` + `core/evidence.py`: 9 fontes, `verified` **derivado da fonte**, frescura com meia-vida, decaimento que reduz confiança e não pontuação, `insufficient_data` como faixa própria | nenhum — é o ativo mais forte do produto | — | expor como diferencial comercial |
| 6 | **Outcome / Impact Engine** | 🟡 | `indicator_catalog.result_kind` ∈ (output, outcome, impact) com COMMENT "Meta atingida NÃO é impacto"; `impact_nodes`/`impact_edges` (teoria da mudança); `impact_updates` | a hierarquia **existe no catálogo** mas nenhum motor a percorre e agrega: não há como responder "10 oficinas → 300 participantes → 240 concluíram → indicador X subiu Y%" numa consulta | **P1** | motor que percorre a cadeia atividade→output→outcome→impacto |
| 7 | **Decision Room** | 🔴 | `applications.status` + `decided_at` + `decision_note`: **um** decisor, uma nota. Existem `compliance_reviews`, `professional_reviews`, `eligibility_evaluations` — nenhum é comitê | sem comitê, voto, justificativa por avaliador e comparação lado a lado, o financiador não consegue **governar a decisão** — e governança da decisão é o que ele paga | **P2** | comitê com voto registrado e justificativa |
| 8 | **Territorial Intelligence** | 🟡 | `territory_needs`, dados territoriais, determinantes sociais, mapa, `/dados-territoriais`, `/determinantes` | falta a análise que o mapa chama de diferenciadora: **"onde NÃO estamos investindo"** — lacuna entre demanda registrada e oferta de projetos por território | **P1** | motor de lacuna territorial (é o argumento B2G) |
| 9 | **Billable Event Engine** | 🔴 | não existe tabela nem conceito | sem evento faturável não há como ligar valor a cobrança; hoje a cobrança é só assinatura por organização | **P0** | `billable_events` com regra de elegibilidade separada da cobrança |
| 10 | **Usage Metering** | 🟡 | `ai_usage` (tokens in/out, latência, provedor, modelo) + limites por plano. **5 das 7 chaves de limite são aplicadas**: `active_projects`, `programs`, `saved_searches`, `seats`, `storage_mb`, mais `ai_requests_month` no gateway e `open_reviews` no match | `ai_usage` **não registra custo**: sem custo não existe margem por evento de valor, que é o cálculo central do prompt | **P1** | custo por chamada de IA |
| 11 | **Transaction Ledger** | 🟡 | `payment_records` + `payment_events` (append-only) + `invoices` (assinatura da plataforma) | **ADR-022/031: a plataforma não custodia nem processa aporte.** Portanto não há transação da plataforma sobre a qual cobrar take rate ou success fee. Isto é decisão tomada, não lacuna | — | ver §4 |
| 12 | **Enterprise Reporting** | 🟡 | relatórios por projeto, prestação de contas, exportação em 8 formatos | falta relatório **de portfólio** consolidado (vários projetos, vários territórios, um investidor) — que é o entregável que a área de ESG compra | **P2** | relatório de portfólio |
| 13 | **Audit Trail** | 🟢 | `audit_events` + `ledger_entries` encadeados por hash, `ledger_verify`/`audit_verify`, 22 tabelas append-only, 15 guardas que o contexto privilegiado não atravessa | nenhum | — | expor como diferencial |
| 14 | **Error Reporting** | 🟢 | `error_id`, `request_id`, `correlation`, RFC 7807, `/admin/erros`, sem vazar segredo | nenhum | — | — |
| 15 | **Feedback / Feature Requests** | 🟡 | `feedbacks`, `kb_feedback`, suporte com SLA | sem acompanhamento de status pelo autor da sugestão | P3 | — |
| 16 | **Account / Data Deletion** | 🟡 | `/v1/privacy/export`, `/v1/privacy/delete-account` (anonimiza, preserva cadeia pseudonimizada) | a exportação **não cobre as entidades novas da rede** (relações, propostas, recados, perfil público) — pendência já declarada em `LGPD_AUDIT.md` | P2 | decisão jurídica antes de técnica |

---

## 2. As camadas que os documentos acrescentam, e que não existem

| Camada | Estado | O que falta, exatamente |
|---|---|---|
| **Value Ledger** | 🔴 | Conceito novo. Hoje `ledger_entries` registra **o que aconteceu no projeto**; `audit_events` registra **quem fez o quê**. Nenhum dos dois registra **quanto trabalho o sistema evitou**. Sem isso não há ROI demonstrável, e o argumento de venda institucional fica sem lastro |
| **Billable Event** | 🔴 | ver §1 item 9 |
| **Eligibility Rule → Monetization Rule → Legal Validation → Billing Rule** | 🔴 | hoje o caminho é `plans → entitlements → feature`. Falta a cadeia intermediária que os documentos exigem, em que um evento de valor **não** implica cobrança automática |
| **Custo de IA por evento** | 🔴 | `ai_usage` tem tokens, não tem custo; sem custo, a margem por evento é indeterminada |
| **Matriz "quem pode ser cobrado"** | 🔴 | não existe no código nem em documento. Hoje a resposta está implícita nos 12 planos |
| **Monetization Legal Card** | 🔴 | não existe. `LGPD_AUDIT.md` cobre dado pessoal, não natureza da receita |

---

## 3. Pagamentos — o estado é mais restrito do que parece

Esta é a correção mais importante desta auditoria, porque uma leitura superficial do banco dá a
impressão errada.

`payment_records.method` aceita `bank_transfer`, **`pix`**, **`boleto`**, `check`, `other`.

**Isso não é meio de pagamento da plataforma.** É o **registro declarado** de um aporte que o
financiador informa e a OSC confirma — ADR-022: *"aportes são registrados e conferidos; a plataforma
não custodia nem processa"*. O dinheiro nunca passa pela plataforma.

A cobrança **da plataforma** é outra coisa, e o estado dela é:

| Meio | Estado | Evidência |
|---|---|---|
| Cartão recorrente | 🟡 arquitetura pronta, **provedor não configurado** | `StripeBilling`, `needs_price_id=True`, checkout responde 503 `provider_price_missing` |
| Cartão avulso | 🟡 mesma arquitetura | idem |
| **Cartão parcelado** | 🔴 | não modelado. E, como os documentos observam, parcelamento **não** é assinatura: precisa de modelagem própria |
| **PIX** como cobrança da plataforma | 🔴 | não existe |
| **Boleto** como cobrança da plataforma | 🔴 | não existe |
| Webhook idempotente | 🟢 | `billing_events` com `UNIQUE(provider, event_id)`, contador de entrada com `least(...)` |
| Máquina de estados do pagamento | 🟡 | existe para `payment_records` (aporte); a da **assinatura** é mais simples que a lista dos documentos (sem `CHARGEBACK`, `DISPUTED`, `PARTIALLY_REFUNDED`) |
| Nota fiscal | 🔴 | não existe emissão |

**E há um conflito de moeda a resolver.** A v0.16.0 moveu a cobrança para **USD** (US$ 1,99 → US$
19,99). PIX, boleto, nota fiscal, prefeitura e contratação pública são **BRL**. Os dois não convivem
sem decisão explícita — está em §5.

---

## 4. Success fee e take rate — o que a própria arquitetura já decidiu

Os documentos pedem cautela aqui, e a arquitetura **já é mais restritiva** do que a cautela pedida:

ADR-022 e ADR-031 estabelecem que a plataforma **não custodia nem processa** aporte, justamente
*"para evitar enquadramento como instituição de pagamento ou oferta de valor mobiliário"*. Não existe
split, não existe custódia, não existe conta de pagamento.

Consequência direta: **não há transação da plataforma sobre a qual cobrar percentual.** Implementar
success fee exigiria **antes** desfazer a ADR-022 — o que é decisão jurídica, não técnica.

O que cabe fazer sem tocar nisso: a infraestrutura de **cálculo e registro** (`fee_rules`,
`fee_calculations`) desligada por padrão, configurável, para que a regra exista e possa ser ativada
*depois* de parecer. É exatamente o que os documentos recomendam ("implementar somente a
infraestrutura técnica de cálculo/ledger em modo desativado").

O mesmo vale para o marketplace: hoje `marketplace_listings` é **vitrine** (anúncio e contato), não
contratação com pagamento. Take rate exige contratação e pagamento dentro da plataforma — que é a
mesma barreira.

---

## 5. O conflito que esta auditoria encontrou, e que não é técnico

A v0.16.0 implementou, por instrução direta: **14 dias de teste · US$ 1,99/mês nos 3 primeiros meses
pagos · depois US$ 19,99/mês ou US$ 179,88/ano**, cobrados da organização que usa o produto —
inclusive da OSC proponente.

Os cinco documentos desta rodada argumentam o contrário, textualmente:

> *"Eu não colocaria o seu SaaS para cobrar principalmente do proponente."*
> *"O proponente não é o principal pagador"* — cadastro, perfil, projeto, descoberta e acompanhamento
> básico a R$ 0, porque *"o lado da oferta precisa crescer para aumentar o valor da rede"*.
> Hierarquia proposta: **SaaS institucional → B2G → Enterprise → implementação → marketplace →
> success fee → premium para proponentes (aquisição/expansão, não núcleo)**.

Os dois não são compatíveis como estão. E a diferença não é de preço: muda **quem** é o cliente, logo
muda plano, entitlement, tela de cobrança, moeda, meio de pagamento, documento fiscal e o que precisa
ser construído primeiro.

**Não implementei nada dessa reestruturação.** A decisão é comercial e é do proprietário — está
colocada em §7.

---

## 6. Backlog executável (Master Execution Backlog)

Ordenado pelo critério dos documentos: *valor × frequência × dor × dificuldade de substituição ×
dados gerados × potencial de expansão ÷ custo de implementação*.

| ID | Item | P | Depende de | Critério de aceitação |
|---|---|---|---|---|
| EC-01 | **Value Ledger** — registra valor operacional criado, separado de cobrança | P0 | — | evento de prontidão concluída registra inconsistências achadas, documentos faltantes e tempo estimado evitado; nada disso aparece em fatura |
| EC-02 | **Custo por operação de IA** em `ai_usage` | P0 | — | toda chamada grava custo estimado; existe consulta "custo de IA por evento de valor" |
| EC-03 | **Billable Event** + cadeia elegibilidade → monetização → **validação jurídica** → cobrança | P0 | EC-01 | evento de valor **não** gera cobrança sem regra ativa e marcada como juridicamente validada |
| EC-04 | **Entidade Programa** (orçamento, oportunidades, projetos, território, indicadores, evidências) | P1 | decisão §7 | financiador cria programa, recebe candidaturas, acompanha execução e extrai relatório consolidado |
| EC-05 | **Motor de cadeia de resultado** atividade → output → outcome → impacto | P1 | — | uma consulta devolve a cadeia inteira com a evidência de cada elo |
| EC-06 | **Lacuna territorial** — demanda registrada × oferta de projetos | P1 | — | responde "quais territórios têm demanda alta e investimento baixo", com a fonte de cada número |
| EC-07 | **Matriz "quem pode ser cobrado"** + Monetization Legal Card por receita | P1 | decisão §7 | cada receita tem pagador, evento, natureza, documento, base, risco e status 🟢/🟡/🔴 |
| EC-08 | **PIX e boleto como cobrança da plataforma** | P1 | decisão de moeda §7 | adaptador, estados, webhook, expiração — com `PRODUCTION PAYMENT NOT CONFIGURED` visível |
| EC-09 | **Cartão parcelado**, modelado separado de assinatura | P1 | EC-08 | parcelas, vencimentos, falha e reembolso próprios |
| EC-10 | **Infra de fee desligada** (`fee_rules`, `fee_calculations`) | P2 | EC-03 | calcula e registra; **não** cobra; só ativável com parecer registrado |
| EC-11 | **Decision Room** (comitê, voto, justificativa, comparação) | P2 | EC-04 | decisão tem mais de um avaliador e cada voto tem justificativa |
| EC-12 | **Relatório de portfólio** (investidor/ESG) | P2 | EC-05 | vários projetos e territórios num relatório com evidência rastreável |
| EC-13 | **Desembolsos e obrigações** como objetos | P2 | EC-04 | agenda de desembolso com evidência exigida por parcela |
| EC-14 | **Exportação LGPD cobrindo a rede** | P2 | decisão jurídica | ver `LGPD_AUDIT.md` |
| EC-15 | **Simulador de economia unitária** (MRR, margem, CAC, LTV, payback) | P3 | EC-02 | parâmetros alteráveis, nada fixado em código |
| EC-16 | Acompanhamento de status de sugestão pelo autor | P3 | — | — |

---

## 7. Decisões que não são minhas

Três, e todas bloqueiam parte do backlog:

1. **Quem é o cliente principal** — manter o plano individual de US$ 19,99 como núcleo, ou rebaixá-lo
   a camada de aquisição e construir o núcleo institucional/B2G/Enterprise (§5)?
2. **Moeda** — USD para o individual e BRL para o institucional brasileiro (que precisa de PIX,
   boleto e nota fiscal)? Ou tudo em BRL?
3. **Escopo desta rodada** — o prompt mestre tem 20 fases; o backlog acima tem 16 itens. Quais entram
   agora?

E duas constatações que não são decisão, são limite do ambiente:

* **Não é possível fazer go-live aqui.** Não há domínio, não há credencial de provedor, e a rede de
  saída do contêiner só alcança registros de pacote. A FASE 15 (deploy) e a 16 (smoke test em
  produção) do prompt mestre **não podem ser executadas neste ambiente** — o que é entregável é a
  configuração parametrizada e o runbook.
* **Pesquisa de base legal não é parecer.** Posso pesquisar fonte oficial e registrar data e grau de
  certeza em cada Monetization Legal Card, marcando o que exige advogado e contador. Não posso
  concluir que uma estrutura é lícita — e os próprios documentos dizem para não tratar opinião do
  modelo como parecer.

---

## PHASE STATUS — FASE 1

**Completed:** auditoria do estado real contra o mapa de valor; 16 itens classificados com evidência
de banco e de código; 6 camadas novas identificadas; estado real de pagamentos corrigido (PIX e
boleto existem como registro de aporte, **não** como cobrança); backlog de 16 itens priorizado.

**Implemented:** nada — a FASE 1 é diagnóstico, e o prompt mestre proíbe implementar monetização antes
de identificar valor, pagador e base jurídica.

**Tested:** as consultas desta auditoria foram executadas contra `impacto_dev` (231 tabelas); a suíte
da v0.16.0 continua em 788 testes, 0 falhas.

**Failed:** nada.

**Risks:** 🔴 `programs` é anunciado como limite de plano e aplicado contra `calls` — o plano promete
uma entidade que não existe. 🔴 Sem custo de IA não há margem calculável. 🟡 A ADR-022 impede success
fee e take rate por desenho, e desfazê-la é decisão jurídica.

**Legal:** success fee, take rate, intermediação, nota fiscal e contratação pública **não foram
tocados** e exigem parecer. Nenhuma afirmação de licitude foi feita.

**Economic:** o conflito do §5 (quem é o pagador principal) precisa ser resolvido antes da FASE 5.

**Git:** branch `chore/v0.16.0-impact-network-core`; esta auditoria é o primeiro arquivo da rodada
seguinte.

**Next:** aguardando as três decisões do §7. Enquanto isso, os itens EC-01, EC-02 e EC-05 não dependem
de nenhuma delas e podem começar.
