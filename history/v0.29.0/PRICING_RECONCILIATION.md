# MATRIZ DE RECONCILIAÇÃO COMERCIAL — v0.21.0

**O que é:** o confronto literal entre a `PRICING_BIBLE.md` (decisão comercial do
proprietário) e o que o repositório realmente faz, apurado por auditoria de código, banco,
API e testes antes de qualquer alteração.

**Método:** DOCUMENTAÇÃO × CÓDIGO × BANCO × API × TESTES. Onde divergiram, o banco e o
código ganharam a descrição do estado, e a Bíblia ganhou a decisão do destino.

**Legenda de STATUS (estado ANTES desta rodada):**

| | |
| --- | --- |
| `EXISTE` | implementado e alcançável |
| `EXISTE VAZIO` | mecanismo construído, sem dado — não produz efeito |
| `NÃO EXISTE` | zero ocorrências no repositório |
| `DIVERGE` | documentação e código discordam |

---

## A. ACHADO CENTRAL DA AUDITORIA

> **Toda a infraestrutura comercial existe e está vazia.**

| Evidência | Medida |
| --- | --- |
| `plan_price_versions` | **0 linhas** |
| `plan_prices` | 10 linhas, **todas `amount_cents = NULL`** |
| `plans` (pagos) | 7 planos, **todos `price_cents = NULL`** |
| `subscriptions`, `invoices`, `platform_charges` | **0 linhas** |
| `price_change_notices` | **0 linhas** |
| `value_events`, `billable_events` | **0 linhas** |
| `monetization_rules` | 9 linhas, **todas `active = false`**, todas `amount_cents = NULL` |
| `legal_documents` | 11 minutas, **todas `status = 'draft'`**, `effective_from = NULL` |
| `legal_acceptances` | **0 linhas** |
| Preço codificado em Python/TSX | **0 ocorrências** — nenhum valor inventado |
| `"FULL FREE"`, `free_until`, `periodo_gratuito` | **0 ocorrências** |

Consequência hoje: todo plano pago exibe "Preço não divulgado" e o botão de contratar está
desabilitado (`web/src/pages/org.tsx:363`, `:456`). A plataforma **recusa** contratação em
vez de inventar valor — o que é o comportamento correto, e é o ponto de partida desta
rodada.

---

## B. MATRIZ

### B.1 — Catálogo e preço

| # | REGRA COMERCIAL | LOCALIZAÇÃO NO CÓDIGO | STATUS | GAP | IMPLEMENTAÇÃO NECESSÁRIA | TESTE |
| --- | --- | --- | --- | --- | --- | --- |
| R-01 | Preço de tabela por plano, intervalo e moeda | `plan_price_versions` (`0017:40`); sync em `db/migrate.py:129` | EXISTE VAZIO | nenhum valor cadastrado | popular `price_versions.items` em `config/plans.json` com a Pricing Version 2027.01 | `test_v0210_pricing_catalog` — catálogo bate com a Bíblia |
| R-02 | Preço nunca se sobrescreve; versão nova fecha a anterior | `_sync_price_versions` (`migrate.py:129-199`); gatilho `price_version_immutable()` (`0017`) | EXISTE | — | nenhuma — já imposto por gatilho | `test_v0210_pricing_catalog` — reajuste cria versão e preserva a anterior |
| R-03 | Nenhum preço codificado (299, 799, 1490, 3500, 49, 10%) | varredura em `backend/` e `web/src/` | EXISTE | — | manter; travar com teste | `test_v0210_pricing_catalog` — varredura falha se número de preço aparecer em código |
| R-04 | Plano "a partir de" não se contrata online | `migrate.py:168-171` exclui `interval = 'custom'`; `org.tsx:455` mostra "Solicitar proposta" | EXISTE | piso não é publicado em lugar nenhum | acrescentar `quote_floor_cents` em `config/plans.json` e exibir "a partir de R$ X — sob proposta" | `test_v0210_pricing_catalog` — plano com piso não tem linha em `plan_price_versions` |
| R-05 | Aumento exige aviso de 30 dias | `price_change_notices` (`0017:106`); gatilho `price_apply_guard()` (`0017:143`) | EXISTE VAZIO | nenhum job cria aviso; inserção é manual | manter manual (é decisão comercial, não automática); documentar | `test_v0210_pricing_catalog` — aumento sem aviso é recusado pelo banco |
| R-06 | Preço aceito fica congelado na assinatura | `record_accepted_price()` (`billing.py:198`) → `subscription_prices` | EXISTE | — | nenhuma | regressão v0.16.0 |

### B.2 — Gratuidade temporal

| # | REGRA COMERCIAL | LOCALIZAÇÃO NO CÓDIGO | STATUS | GAP | IMPLEMENTAÇÃO NECESSÁRIA | TESTE |
| --- | --- | --- | --- | --- | --- | --- |
| R-07 | FULL FREE 2026 até 31/12/2026 23:59:59 | — | **NÃO EXISTE** | zero ocorrências de `full_free` no repositório | tabela `free_periods` + concessão por conta com `source='2026_CAMPAIGN'` | `test_v0210_free_period` — fronteira 23:59:58 / 23:59:59 / 00:00:00 / 00:00:01 |
| R-08 | 3 meses grátis para assinatura nova a partir de 2027 | — | **NÃO EXISTE** | — | concessão automática na criação da assinatura, `source='2027_NEW_SUBSCRIPTION'` | `test_v0210_free_period` — assinaturas em 01/01, 01/02, 15/02, 28/02 e 31/03/2027 |
| R-09 | "3 meses" = meses de calendário (não 90 dias) | — | **NÃO EXISTE** | semântica não decidida em lugar nenhum | decidir, documentar (ADR-268) e implementar com tratamento de dia inexistente | `test_v0210_free_period` — 31/01 + 3 meses = 30/04; 30/11 + 3 meses = 28/02 |
| R-10 | Nunca uma data global codificada | — | **NÃO EXISTE** | — | registro individual por conta, com `account_id`, `started_at`, `ends_at`, `source`, `reason`, `pricing_version`, `status` | `test_v0210_free_period` — varredura proíbe literal `2026-12-31` em código de produto |
| R-11 | FUNDER CORPORATE (a partir de R$ 3.500) | — | **NÃO EXISTE** como plano | sem `plan_key` próprio | **lacuna declarada** — tratado como escopo de proposta de `company_enterprise`; criar plano exige decisão do proprietário | documentado em `PRICING_BIBLE.md` §3 e §10 |
| R-12 | Trial de 14 dias existente | `start_trial()` (`monetization.py:51`); `org_trials` | EXISTE | convive com o período gratuito novo | **não apagar** — trial e período gratuito coexistem; o mais favorável vale | `test_v0210_free_period` — conta com trial e campanha usa o que terminar depois |

### B.3 — Aceite e autorização

| # | REGRA COMERCIAL | LOCALIZAÇÃO NO CÓDIGO | STATUS | GAP | IMPLEMENTAÇÃO NECESSÁRIA | TESTE |
| --- | --- | --- | --- | --- | --- | --- |
| R-13 | ACESSO GRATUITO ≠ AUTORIZAÇÃO DE COBRANÇA | — | **NÃO EXISTE** | nenhuma distinção modelada; `payment_method_required` tem 0 ocorrências | `offer_acceptances.consent_status` com `free_access` × `authorized`; estado `PAYMENT_METHOD_REQUIRED` | `test_v0210_offer` — fim do período sem autorização **não** cobra e **não** suspende |
| R-14 | Registrar os 14 campos do aceite de oferta | `legal_acceptances` guarda documento, não oferta | EXISTE PARCIAL | sem `offer_id`, `pricing_version`, `plan_id`, `price_id`, `free_period`, `billing_frequency`, `payment_method`, `commercial_terms_version`, `consent_status` | tabela `commercial_offers` + `offer_acceptances` com os 14 campos | `test_v0210_offer` — aceite grava os 14 campos; nenhum nulo onde é obrigatório |
| R-15 | Aceite legal com hash do corpo e IP | `legal_acceptances` + gatilho `acceptance_stamp()` (`0023:128`) | EXISTE | 11 minutas em `draft` → gatilho recusaria qualquer aceite | aprovar minutas é decisão humana; **não** aprovar automaticamente | `test_v0210_offer` — aceite de minuta não aprovada é recusado |
| R-16 | Sem cobrança surpresa | — | **NÃO EXISTE** garantia estrutural | — | cobrança exige `offer_acceptances` com `consent_status='authorized'` vigente | `test_v0210_offer` — cobrança sem autorização é recusada |

### B.4 — Pagamento

| # | REGRA COMERCIAL | LOCALIZAÇÃO NO CÓDIGO | STATUS | GAP | IMPLEMENTAÇÃO NECESSÁRIA | TESTE |
| --- | --- | --- | --- | --- | --- | --- |
| R-17 | Cartão, recorrência | `platform_charges.method` (`0022`); `StripeBilling` (`billing.py:85`) | EXISTE | — | nenhuma | regressão v0.17.0 |
| R-18 | Parcelamento ≠ recorrência | `platform_charges.installments 2..24` só para cartão (`0022`) | EXISTE PARCIAL | parcelamento não é distinguido de recorrência na oferta | `billing_frequency` na oferta com `one_time`/`installment`/`recurring` separados | `test_v0210_offer` — oferta parcelada não vira assinatura recorrente |
| R-19 | Boleto | `platform_charges.method` inclui `boleto` | EXISTE | — | nenhuma | regressão |
| R-20 | Boleto parcelado SÓ para CNPJ | — | **NÃO EXISTE** | `installments` hoje é restrito a cartão, e não há regra de CNPJ | validação no **backend**: boleto parcelado exige organização com CNPJ válido | `test_v0210_offer` — CPF pedindo boleto parcelado é recusado (422), CNPJ é aceito |
| R-21 | `idempotency_key` em evento financeiro | idempotência por UNIQUE: `billing_events(provider,event_id)`, `platform_charges(provider,provider_charge_id)` | EXISTE PARCIAL | sem chave de idempotência fornecida pelo cliente | coluna `idempotency_key` com UNIQUE por organização | `test_v0210_offer` — mesma chave duas vezes cria um registro só |

### B.5 — Uso

| # | REGRA COMERCIAL | LOCALIZAÇÃO NO CÓDIGO | STATUS | GAP | IMPLEMENTAÇÃO NECESSÁRIA | TESTE |
| --- | --- | --- | --- | --- | --- | --- |
| R-22 | Medição de uso para fins comerciais | contagem ao vivo em 7 chamadores de `check_limit()` (`entitlements.py:88`) | EXISTE PARCIAL | sem contador persistido, sem período, sem histórico | `usage_counters` por organização/métrica/período | `test_v0210_usage` — contador bate com a contagem ao vivo |
| R-23 | Alertas de 70% / 90% / 100% | — | **NÃO EXISTE** | corte é binário e silencioso: HTTP 402 sem aviso prévio | alertas nos três limiares, uma vez por período | `test_v0210_usage` — cada limiar notifica uma vez só |
| R-24 | `monthly_spend_limit` | — | **NÃO EXISTE** | — | teto por organização, com ação `warn` ou `hard_stop` | `test_v0210_usage` — `hard_stop` bloqueia antes de gerar custo |
| R-25 | `hard_stop` | — | **NÃO EXISTE** | — | idem | idem |
| R-26 | Cota de IA conta o mesmo nos dois lugares | `gateway.py:93` usa `status <> 'rejected'`; `ai_routes.py:57` **não** usa | **DIVERGE** | o painel pode mostrar consumo maior do que o que realmente bloqueia | unificar numa função única usada pelos dois | `test_v0210_usage` — leitura do painel e do bloqueio devolvem o mesmo número |

### B.6 — Avisos e interface

| # | REGRA COMERCIAL | LOCALIZAÇÃO NO CÓDIGO | STATUS | GAP | IMPLEMENTAÇÃO NECESSÁRIA | TESTE |
| --- | --- | --- | --- | --- | --- | --- |
| R-27 | Avisos em 90/60/30/7/1 dia + semanal | lembretes de trial em `(1,7,11,13,14)` (`monetization.py:21`) | EXISTE PARCIAL | janelas do trial, não do período gratuito | janelas comerciais a partir de `free_periods.ends_at` | `test_v0210_free_period` — cada janela dispara uma vez |
| R-28 | `FREE_PERIOD_END` como fonte única | — | **NÃO EXISTE** | — | backend publica o estado; frontend consome | `test_v0210_free_period` — varredura proíbe cálculo de data de fim no frontend |
| R-29 | i18n comercial | `config/i18n.json` | **NÃO EXISTE** | **zero** chaves `billing.*`, `pricing.*`, `subscription.*`, `checkout.*`, `invoice.*`, `payment.*`, `usage.*` nos 3 idiomas; UI comercial 100% em português codificado | criar os namespaces nos 3 idiomas | `test_v0210_free_period` — os 3 idiomas têm o mesmo conjunto de chaves |
| R-30 | Página pública de preços | — | **NÃO EXISTE** | API pública existe (`billing_routes.py:17`), nenhuma tela a consome | página pública lendo o catálogo | `test_v0210_commercial_ui` |
| R-31 | Contagem regressiva do período gratuito | — | **NÃO EXISTE** | — | ler `FREE_PERIOD_END` do backend | `test_v0210_commercial_ui` |
| R-32 | Checkout mostra R$ 0,00 hoje e o preço futuro | modal mostra "Preço do plano" e "Primeira fatura" (`org.tsx:462-487`) | EXISTE PARCIAL | não contempla período gratuito | acrescentar "hoje você paga R$ 0,00" e a data da primeira cobrança | `test_v0210_commercial_ui` |
| R-33 | Códigos de erro comerciais tratados na UI | — | **NÃO EXISTE** | `price_not_defined`, `plan_limit_reached`, `ai_quota_exceeded` caem no tratador genérico | mensagens específicas | `test_v0210_commercial_ui` |

### B.7 — Fuso e tempo

| # | REGRA COMERCIAL | LOCALIZAÇÃO NO CÓDIGO | STATUS | GAP | IMPLEMENTAÇÃO NECESSÁRIA | TESTE |
| --- | --- | --- | --- | --- | --- | --- |
| R-34 | Fronteira comercial em `America/Sao_Paulo` | projeto é 100% UTC (`clock.py`); 529 colunas `timestamptz`, 0 sem fuso | EXISTE PARCIAL | `America/Sao_Paulo` tem **0 ocorrências** | armazenar em UTC (manter) e **converter na fronteira comercial**; nunca trocar a convenção interna | `test_v0210_free_period` — 31/12/2026 21:00 UTC ainda é 2026 em São Paulo |
| R-35 | Formatação de data dos avisos | offset **fixo** `-04:00` comentado como `America/Cuiaba` (`monetization.py:366`) | **DIVERGE** | offset fixo não acompanha mudança de regra de fuso | usar `ZoneInfo('America/Sao_Paulo')` | `test_v0210_free_period` — data formatada bate com o fuso declarado |
| R-36 | Teste de fronteira temporal | — | **NÃO EXISTE** | nenhum teste de meia-noite, virada de mês ou de ano | os casos do §9 do prompt | `test_v0210_free_period` |

### B.8 — Invariantes de produto

| # | REGRA COMERCIAL | LOCALIZAÇÃO NO CÓDIGO | STATUS | GAP | IMPLEMENTAÇÃO NECESSÁRIA | TESTE |
| --- | --- | --- | --- | --- | --- | --- |
| R-37 | Pagamento não compra reputação, selo, impacto, evidência, verdade, elegibilidade nem qualidade de match | `never_sellable` (`config/plans.json`) | EXISTE declarado | declaração sem varredura que a imponha | teste que varre o código em busca de qualquer caminho de plano para pontuação | `test_v0210_pricing_catalog` |
| R-38 | Take rate de 10% | `monetization_rules` + gatilho citando ADR-022 | EXISTE VAZIO, **inativo por decisão** | a Bíblia pede 10%; a arquitetura recusa percentual sem custódia | **declarar a regra com 10%, manter `active = false`** — a própria Bíblia §20 exige `service + contract + transaction` | `test_v0210_pricing_catalog` — ativar sem custódia é recusado pelo banco |
| R-39 | Success fee 2–3%, transaction fee 1–3% | idem | EXISTE VAZIO, inativo | idem | declarar a faixa, manter desligado | idem |

---

## C. DIVERGÊNCIAS DE DOCUMENTAÇÃO CORRIGIDAS NESTA RODADA

| Documento | Divergência | Decisão |
| --- | --- | --- |
| `BILLING_V2.md` | descreve a regra da v0.16.0 (US$ 1,99 → US$ 19,99) que `config/plans.json` **aposentou na v0.17.0** | reescrever para a Pricing Version 2027.01, preservando o histórico das regras aposentadas |
| `config/plans.json` `_rule` | diz "nenhum preço institucional foi fixado" | passa a ser falso quando a 2027.01 entrar — atualizar o texto junto com os valores |
| `MONETIZATION.md` | não menciona período gratuito temporal | acrescentar a seção de gratuidade com remissão a `FULL_FREE_2026.md` |

---

## C-bis. RECONCILIAÇÃO v0.27.0 — A ASSINATURA SAIU (ADR-341)

| # | REGRA COMERCIAL | LOCALIZAÇÃO NO CÓDIGO | STATUS | GAP | IMPLEMENTAÇÃO NECESSÁRIA | TESTE |
| --- | --- | --- | --- | --- | --- | --- |
| R-40 | Não existe assinatura: nenhuma mensalidade, trial, checkout, reajuste ou cancelamento | migração `0067`; `services/entitlements.py`, `services/monetization.py`, `api/billing_routes.py`; `config/plans.json` (`plans@4.0`) | FEITO | — | — | `test_v0210_pricing_catalog` (estrutura ausente), `test_v0110_monetization` (rotas ausentes), `test_api_features` |
| R-41 | Receita da plataforma = camada econômica da operação (3,5%) + contratos avulsos; GMV ≠ receita | `economic_rules` 2027.02, `trust/economy.py`, `economics/metrics.py::operation_revenue` | FEITO (registro e instrução); cobrança própria só com carta verde | regra `contract.platform_service_fee` continua amarela | parecer jurídico/contábil (externo) | `test_v0270_economy`, `test_v0220_financial_engine` |
| R-42 | Contrato avulso/parcelado: valor de quem tem alçada, com motivo; aceite com autorização concede pacote | `api/commercial_routes.py`, `services/offers.py` | FEITO | — | — | `test_v0210_offer` |
| R-43 | Regra de assinatura `saas.institutional.funder` RECUSADA com carta vermelha | migração `0067` §7 | FEITO | — | — | `test_v0210_pricing_catalog` |

## D. O QUE NÃO SERÁ FEITO NESTA RODADA, E POR QUÊ

| Pedido | Decisão | Motivo |
| --- | --- | --- |
| Ativar take rate de 10% | **não** | sem custódia do valor, a cobrança não é verificável e pode exigir autorização do Bacen (ADR-178, Lei 12.865/2013). Declarado e desligado. |
| Aprovar as minutas jurídicas | **não** | aprovação de minuta é ato humano com responsabilidade profissional. Ficam em `draft`, visíveis. |
| Criar valor anual para `provider_premium` e `company_premium` | **não** | a Bíblia não publica esses valores. Criar um desconto seria inventar preço. |
| Criar o plano FUNDER CORPORATE | **não** | exige decisão do proprietário sobre separar ou não de `company_enterprise`. Registrado como R-11. |
| Cobrar excedente de uso | **não** | sem preço de excedente publicado, o excedente é bloqueado ou avisado — nunca cobrado. |
| Integração real com provedor fiscal / Stripe de produção | **não** | exige credencial e contrato. O modo sandbox continua explícito na interface. |
