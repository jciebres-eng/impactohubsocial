# Relatório executivo — Engenharia econômica, monetização híbrida, projeções e valuation (IMPACTO v0.30.0)

> **Modo desta execução: ANÁLISE E PROPOSTA.** Nada do produto foi alterado: regra, catálogo, `config/plans.json`, banco e contratos
> continuam exatamente como na v0.30.0. Todo número abaixo é SIMULAÇÃO sobre premissas declaradas (planilha `IMPACTO_MODELO_120M.xlsx`,
> fórmulas abertas; motor em `scripts/analysis/economic_model_120m.py`; a planilha recalculada no LibreOffice reproduz o motor —
> diferença máxima de arredondamento R$ 0,03). Natureza de cada premissa: **FATO** (repositório) · **HIPÓTESE DO PROPRIETÁRIO** (já
> declarada no repositório) · **PREMISSA DE MERCADO** (não verificada, editável) · **DERIVADO** (cálculo). Receita real hoje: **R$ 0,00**.

## 1. Diagnóstico econômico da base (FATOS do repositório, v0.30.0)

| Item | Estado real | Onde está provado |
|---|---|---|
| Taxa de serviço | **350 bps (3,50 %)** sobre operação financiada, congelada no acordo; regra `contract.platform_service_fee` **INATIVA** (`review_required`, carta amarela) — nada é devido nem cobrado | `monetization_rules`, `config/economic_model.json`, `test_v0270_financial_model`, `test_v0150_upgrade` (11 regras, 0 ativas) |
| Participação de autoria | **150 bps (1,50 %)**, do proponente elegível, **não é receita da plataforma** | ADR-337, `test_v0270_economy` |
| Reconhecimento da receita transacional | só na **quitação** (entrega aceita + repasses confirmados por quem recebe); `allocation_payouts.state = 'awaiting_rule'` enquanto a regra estiver inativa | `MILESTONE_FUNDING_STATES_v0300.md`, `test_v0270_economy` |
| GMV ≠ receita | o valor financiado vai do financiador ao projeto; a plataforma não custodia (nenhuma tabela de saldo/escrow: teste de estrutura) | ADR-284, `test_the_platform_has_no_table_that_holds_third_party_money` |
| Assinaturas recorrentes | **não existem no código**: tabelas derrubadas na 0067; `GET /v1/plans` não publica preço recorrente; `config/plans.json` = pacotes de capacidades sem preço | ADR-341, `test_v0270_no_subscription` |
| Regras recusadas no catálogo | `saas.institutional.funder`, `b2g.territorial_governance`, `data.territorial_intelligence`, `marketplace.take_rate`, `success_fee.funding` — **refused** com carta vermelha | `MONETIZATION_LEGAL_MATRIX.md` |
| Regras em revisão | `contract.platform_service_fee`, `implementation.setup`, `enterprise.esg_portfolio`, `premium.readiness_analysis` (R$ 29 hipótese), `premium.document_preparation` (R$ 79 hipótese), `ai.credits_prepaid` (pacotes R$ 10 / 45 / 160, `hypothesis`; modo piloto) | catálogo; `ai_credit_packs`; ADR-349 |
| Gateway de pagamento | nenhum; webhook responde 404 sem segredo; nenhuma cobrança real possível | `EXTERNAL_INTEGRATIONS.md`, `test_v0280_ai_usage_control` |
| Custos | **não medidos**: sem folha, sem fatura de nuvem/provedor; `config/ai_economics.json` traz hipóteses (PIX 1 %, tributos 8,65 %, suporte R$ 0,30/usuário/mês, infra R$ 0,02/operação local) | `UNIT_ECONOMICS.md` (lado do custo `[PENDENTE]`) |
| Invariantes | plano não altera match/elegibilidade/ranking; rebaixar não apaga dado; pagamento não compra posição | `config/plans.json` invariants, `test_v0150_invariants`, `test_v0270_no_subscription` |

**Conflito encontrado (documento × decisão):** `UNIT_ECONOMICS.md` (v0.21.0) ainda descreve planos mensais (PRO R$ 299, BUSINESS R$ 799…). Está
**superado** pela ADR-341 e pelo código (0067); **prevalece o código + ADR**. Recomendação: marcar o documento como SUPERADO (rodada de limpeza).

**Conflito entre o pedido e a base:** a "Camada 1 — SaaS institucional / receita previsível" do pedido é, no repositório, a regra
`saas.institutional.funder` **recusada** e a ADR-341 ("não existe mais assinatura"). O modelo abaixo avalia essa camada **como proposta**
(desenho HÍBRIDO) sem confundi-la com o modelo vigente (desenho ATUAL). Ativar exige decisão do proprietário, ADR nova e parecer.

## 2. Dois desenhos avaliados, sem mistura

| Desenho | Fontes de receita | Base no repositório | O que muda |
|---|---|---|---|
| **ATUAL** | taxa 3,5 % sobre operações quitadas (quando a regra for ativada — premissa de mês de ativação) + serviços/inteligência avulsos (R$ 29/79, créditos) | catálogo vigente | nada — só precisa de parecer para ativar a taxa |
| **HÍBRIDO** (proposta) | ATUAL + contratos institucionais **anuais** de software (governança, portfólio, auditoria, relatórios) com implantação | **contraria ADR-341**; regra recusada; faixas-hipótese do catálogo (R$ 2–10 mil/mês funder; R$ 3–15 mil ESG; R$ 3–50 mil gov) | ADR nova, catálogo, cartas, contrato-modelo, B2G só por licitação/dispensa |

Diferença de natureza que o pedido exige preservar: contrato institucional **não é paywall** — o núcleo continua gratuito e nenhum
contrato altera match, elegibilidade ou ranking (invariantes testados). O que se vende é operação de portfólio/governança para quem
recebe valor econômico claro (financiador, governo, grande organização), nunca acesso para OSC.

## 3. Matriz de monetização por fonte (FASE 2) — cada linha diz o que é fato e o que é hipótese

| Fonte | Pagador | Problema resolvido | Evento de cobrança | Preço proposto (HIPÓTESE salvo nota) | Frequência | Custo de entrega | Margem de contribuição | Riscos | Impacto em OSC/beneficiários |
|---|---|---|---|---|---|---|---|---|---|
| A. Contrato institucional (HÍBRIDO) | financiador, fundação, grande organização; governo **só** por licitação/dispensa (Lei 14.133) | gerir portfólio com evidência, diligência, dossiês, relatórios ESG/ODS | assinatura do contrato anual (faturado na assinatura; reconhecido pro rata) | R$ 36 mil/ano (cons.) · R$ 72 mil/ano (base) · R$ 120 mil/ano (agr.) + implantação R$ 10–30 mil — **ancorado nas faixas-hipótese do catálogo recusado; sem evidência de mercado** | anual | suporte, implantação, infra variável (hipóteses) | alta se o produto já existe (é o caso: torres, dossiê, relatórios) | adoção não validada; ADR-341; B2G sem checkout | nenhum: OSC não paga; dados de OSC continuam dela |
| B. Transacional (ATUAL) | financiador (pagador da cláusula) | operação rastreada até a quitação | **quitação** da operação | 3,50 % do valor financiado (**FATO**, catálogo); modo deducted/additional | por operação | registro; sem provedor | alta por operação; volume baixo nos tickets-hipótese | parecer (natureza da taxa; não é intermediação de pagamento — ADR-284/337); conflito de interesse mitigado por não-custódia e match sem pay-to-rank | em modo deducted o projeto recebe 95 %; em additional recebe 100 % |
| C. Serviços profissionais (marketplace) | — | — | — | **não modelado como receita**: `marketplace.take_rate` recusada (vitrine sem pagamento interno) | — | — | — | instituição de pagamento (Lei 12.865) | — |
| D. Inteligência (serviços avulsos) | OSC/pessoa/financiador que usa | prontidão, documento, créditos de IA, relatórios | entrega/execução bem-sucedida | R$ 29 / R$ 79 (hipóteses do catálogo); créditos R$ 0,10 (hipótese de teste); no modelo: R$ 1,50–8,00/OSC/mês e R$ 20–120/financiador/mês de adoção média (**PREMISSA DE MERCADO**) | por uso | provedor de IA (não contratado), horas | depende do provedor (`AI_COST_MODEL.md`: uma operação deficitária nomeada) | parecer (crédito pré-pago, CDC, NFS-e) | baixo preço; cota gratuita; patrocínio |

## 4. Catálogo de preços proposto por perfil (FASE 3) — proposta, não decisão

| Perfil | Núcleo gratuito | Contrato institucional (HÍBRIDO) | Módulos adicionais | Implantação/integração | Serviços avulsos | Transacional |
|---|---|---|---|---|---|---|
| Financiador / empresa / instituto | descoberta, candidaturas, diligência básica, acompanhamento | R$ 3–10 mil/mês (anual) — hipótese | ESG/ODS consolidado (R$ 3–15 mil/mês, hipótese do catálogo) | R$ 10–30 mil (hipótese) | relatórios/IA por uso | 3,5 % na quitação (fato; inativa) |
| Governo / fundo | torre territorial, editais públicos | **só por licitação/dispensa**; faixa R$ 3–50 mil/mês (hipótese); **sem checkout** | — | por contrato | — | — (recurso público: regras próprias) |
| Executora (OSC) | **tudo o que protege, corrige e presta contas** | nenhum (por desenho) | — | — | R$ 29 / R$ 79 / créditos (hipóteses); cota gratuita; patrocínio | não paga a taxa (quem paga é o financiador, modo additional) ou recebe 95 % (deducted) — definido no acordo |
| Prestador | perfil, ofertas, entregas, reputação | nenhum | — | — | créditos de IA | sem comissão (recusada) |
| Promotor de ideias | banco de ideias → projeto | nenhum | — | — | créditos de IA | — |

**Evidência de mercado:** nenhuma faixa acima tem pesquisa de disposição a pagar; as únicas referências são as faixas-hipótese já escritas no
catálogo (`hypothesis_note`) e os múltiplos externos citados em §6. Validar antes de desenvolver (roadmap §8).

## 5. Projeção de 120 meses (FASE 4) — três cenários × dois desenhos

Premissas comuns do repositório: 3 novos financiadores/mês (hipótese do proprietário); por cenário, ticket financiado, operações por
financiador/ano, fração quitada e prazo de quitação (os mesmos de `config/economic_model.json`). Premissas de mercado (editáveis): churn,
mês de ativação da taxa, inadimplência, prazo de recebimento, equipe, infra, marketing, CAC, contratos institucionais (só no HÍBRIDO).
Custos de pessoal crescem com a carteira (1 FTE adicional a cada 15/20/25 clientes). Caixa inicial: zero (não informado).

### 5.1 Desenho ATUAL (modelo vigente)

| Cenário | Marco | Financiadores | Contratos inst. | ARR software | Receita 12 m | — taxa | — software | — serviços | GMV originado 12 m | GMV quitado 12 m | EBITDA 12 m | Caixa | Mínimo de caixa até aqui |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| conservador | M6 | 17.1 | 0.0 | R$ 0 | R$ 1.582 | R$ 0 | R$ 0 | R$ 1.582 | R$ 182.157 | R$ 0 | R$ -368.485 | R$ -369.365 | R$ -369.365 |
| conservador | M12 | 32.1 | 0.0 | R$ 0 | R$ 5.643 | R$ 0 | R$ 0 | R$ 5.643 | R$ 832.842 | R$ 109.294 | R$ -816.046 | R$ -817.979 | R$ -817.979 |
| conservador | M24 | 57.1 | 0.0 | R$ 0 | R$ 35.427 | R$ 21.014 | R$ 0 | R$ 14.413 | R$ 2.309.803 | R$ 990.815 | R$ -1.076.854 | R$ -1.906.018 | R$ -1.906.018 |
| conservador | M48 | 91.6 | 0.0 | R$ 0 | R$ 107.416 | R$ 80.898 | R$ 0 | R$ 26.517 | R$ 4.249.571 | R$ 2.311.385 | R$ -1.409.007 | R$ -4.596.608 | R$ -4.596.608 |
| conservador | M120 | 132.5 | 0.0 | R$ 0 | R$ 176.645 | R$ 135.760 | R$ 0 | R$ 40.885 | R$ 6.552.020 | R$ 3.878.863 | R$ -1.817.899 | R$ -14.856.228 | R$ -14.856.228 |
| base | M6 | 17.4 | 0.0 | R$ 0 | R$ 5.677 | R$ 0 | R$ 0 | R$ 5.677 | R$ 1.356.264 | R$ 14.062 | R$ -535.370 | R$ -537.138 | R$ -537.138 |
| base | M12 | 33.6 | 0.0 | R$ 0 | R$ 33.847 | R$ 13.275 | R$ 0 | R$ 20.571 | R$ 5.403.737 | R$ 1.396.486 | R$ -1.133.936 | R$ -1.151.003 | R$ -1.151.003 |
| base | M24 | 62.5 | 0.0 | R$ 0 | R$ 348.484 | R$ 293.672 | R$ 0 | R$ 54.812 | R$ 14.894.455 | R$ 8.390.635 | R$ -1.160.203 | R$ -2.347.098 | R$ -2.347.098 |
| base | M48 | 108.8 | 0.0 | R$ 0 | R$ 819.218 | R$ 709.645 | R$ 0 | R$ 109.572 | R$ 29.775.085 | R$ 20.275.577 | R$ -1.231.720 | R$ -4.869.413 | R$ -4.869.413 |
| base | M120 | 187.0 | 0.0 | R$ 0 | R$ 1.614.959 | R$ 1.412.818 | R$ 0 | R$ 202.141 | R$ 54.929.734 | R$ 40.366.228 | R$ -1.352.613 | R$ -13.116.534 | R$ -13.116.534 |
| agressivo | M6 | 17.6 | 0.0 | R$ 0 | R$ 13.421 | R$ 0 | R$ 0 | R$ 13.421 | R$ 7.267.574 | R$ 529.479 | R$ -880.566 | R$ -884.567 | R$ -884.567 |
| agressivo | M12 | 34.4 | 0.0 | R$ 0 | R$ 376.377 | R$ 327.346 | R$ 0 | R$ 49.031 | R$ 27.875.635 | R$ 10.830.526 | R$ -1.531.599 | R$ -1.631.363 | R$ -1.631.363 |
| agressivo | M24 | 65.5 | 0.0 | R$ 0 | R$ 1.963.259 | R$ 1.829.760 | R$ 0 | R$ 133.499 | R$ 77.256.117 | R$ 52.278.856 | R$ -429.106 | R$ -2.223.551 | R$ -2.223.551 |
| agressivo | M48 | 119.1 | 0.0 | R$ 0 | R$ 4.698.927 | R$ 4.419.934 | R$ 0 | R$ 278.994 | R$ 161.454.703 | R$ 126.283.821 | R$ 1.471.214 | R$ -558.863 | R$ -2.227.267 |
| agressivo | M120 | 228.1 | 0.0 | R$ 0 | R$ 10.265.128 | R$ 9.690.099 | R$ 0 | R$ 575.029 | R$ 332.771.559 | R$ 276.859.962 | R$ 5.337.751 | R$ 21.506.932 | R$ -2.227.267 |

| Cenário | Receita acumulada 120 m | Ponto de equilíbrio (mês, EBITDA > 0 sustentado) | Necessidade de capital (pior caixa) |
|---|---:|---:|---:|
| conservador | R$ 1.166.309 | não alcança em 120 m | R$ 14.856.228 |
| base | R$ 9.849.033 | não alcança em 120 m | R$ 13.116.534 |
| agressivo | R$ 59.733.770 | 24 | R$ 2.227.267 |

### 5.2 Desenho HÍBRIDO (proposta — contraria ADR-341)

| Cenário | Marco | Financiadores | Contratos inst. | ARR software | Receita 12 m | — taxa | — software | — serviços | GMV originado 12 m | GMV quitado 12 m | EBITDA 12 m | Caixa | Mínimo de caixa até aqui |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| conservador | M6 | 17.1 | 0.0 | R$ 0 | R$ 1.582 | R$ 0 | R$ 0 | R$ 1.582 | R$ 182.157 | R$ 0 | R$ -368.485 | R$ -369.365 | R$ -369.365 |
| conservador | M12 | 32.1 | 1.5 | R$ 53.105 | R$ 29.543 | R$ 0 | R$ 23.900 | R$ 5.643 | R$ 832.842 | R$ 109.294 | R$ -819.417 | R$ -824.090 | R$ -824.090 |
| conservador | M24 | 57.1 | 6.7 | R$ 240.665 | R$ 253.256 | R$ 21.014 | R$ 217.828 | R$ 14.413 | R$ 2.309.803 | R$ 990.815 | R$ -1.014.734 | R$ -1.800.383 | R$ -1.800.383 |
| conservador | M48 | 91.6 | 14.4 | R$ 519.270 | R$ 631.346 | R$ 80.898 | R$ 523.930 | R$ 26.517 | R$ 4.249.571 | R$ 2.311.385 | R$ -1.155.878 | R$ -3.995.261 | R$ -3.995.261 |
| conservador | M120 | 132.5 | 25.4 | R$ 912.811 | R$ 1.132.955 | R$ 135.760 | R$ 956.310 | R$ 40.885 | R$ 6.552.020 | R$ 3.878.863 | R$ -1.294.964 | R$ -11.520.330 | R$ -11.520.330 |
| base | M6 | 17.4 | 0.0 | R$ 0 | R$ 5.677 | R$ 0 | R$ 0 | R$ 5.677 | R$ 1.356.264 | R$ 14.062 | R$ -535.370 | R$ -537.138 | R$ -537.138 |
| base | M12 | 33.6 | 5.9 | R$ 421.343 | R$ 277.767 | R$ 13.275 | R$ 243.921 | R$ 20.571 | R$ 5.403.737 | R$ 1.396.486 | R$ -1.004.053 | R$ -823.441 | R$ -823.441 |
| base | M24 | 62.5 | 16.5 | R$ 1.191.501 | R$ 1.434.680 | R$ 293.672 | R$ 1.086.197 | R$ 54.812 | R$ 14.894.455 | R$ 8.390.635 | R$ -438.451 | R$ -1.017.805 | R$ -1.087.401 |
| base | M48 | 108.8 | 34.4 | R$ 2.479.254 | R$ 3.267.173 | R$ 709.645 | R$ 2.447.956 | R$ 109.572 | R$ 29.775.085 | R$ 20.275.577 | R$ 539.220 | R$ 6.690 | R$ -1.087.401 |
| base | M120 | 187.0 | 68.2 | R$ 4.910.479 | R$ 6.633.861 | R$ 1.412.818 | R$ 5.018.902 | R$ 202.141 | R$ 54.929.734 | R$ 40.366.228 | R$ 2.399.148 | R$ 11.150.786 | R$ -1.087.401 |
| agressivo | M6 | 17.6 | 6.0 | R$ 715.211 | R$ 312.888 | R$ 0 | R$ 299.468 | R$ 13.421 | R$ 7.267.574 | R$ 529.479 | R$ -682.201 | R$ -397.669 | R$ -610.534 |
| agressivo | M12 | 34.4 | 17.5 | R$ 2.103.287 | R$ 1.800.562 | R$ 327.346 | R$ 1.424.185 | R$ 49.031 | R$ 27.875.635 | R$ 10.830.526 | R$ -503.092 | R$ 324.959 | R$ -610.534 |
| agressivo | M24 | 65.5 | 39.3 | R$ 4.717.771 | R$ 6.220.089 | R$ 1.829.760 | R$ 4.256.831 | R$ 133.499 | R$ 77.256.117 | R$ 52.278.856 | R$ 2.890.991 | R$ 4.060.508 | R$ -610.534 |
| agressivo | M48 | 119.1 | 78.0 | R$ 9.357.319 | R$ 13.770.455 | R$ 4.419.934 | R$ 9.071.527 | R$ 278.994 | R$ 161.454.703 | R$ 126.283.821 | R$ 8.766.481 | R$ 20.326.280 | R$ -610.534 |
| agressivo | M120 | 228.1 | 162.8 | R$ 19.540.426 | R$ 29.904.186 | R$ 9.690.099 | R$ 19.639.058 | R$ 575.029 | R$ 332.771.559 | R$ 276.859.962 | R$ 21.357.914 | R$ 123.876.647 | R$ -610.534 |

| Cenário | Receita acumulada 120 m | Ponto de equilíbrio (mês, EBITDA > 0 sustentado) | Necessidade de capital (pior caixa) |
|---|---:|---:|---:|
| conservador | R$ 7.223.322 | não alcança em 120 m | R$ 11.520.330 |
| base | R$ 40.017.584 | 29 | R$ 1.087.401 |
| agressivo | R$ 175.126.816 | 9 | R$ 610.534 |

**Leitura honesta:** no desenho ATUAL, com os tickets-hipótese do repositório, a taxa de 3,5 % sobre operações quitadas **não sustenta uma
equipe** nos cenários conservador e base (o custo de pessoal cresce com a carteira mais rápido que a receita por financiador); só o
cenário agressivo (ticket R$ 500 mil, 3 operações/ano) atinge equilíbrio. No HÍBRIDO, o contrato institucional é o que paga a operação;
a taxa vira crescimento adicional. Isso é o que o pedido chamou de "base de receita contratada para financiar a operação" — e é exatamente
o que a ADR-341 recusou como assinatura. **A decisão é do proprietário**, e o modelo mostra o preço de cada escolha.

Modelagem separada que o pedido exige: **contratos assinados** (novos + renovações), **receita faturada** (anual na assinatura; taxa na
quitação; serviços na entrega), **receita recebida** (prazo + inadimplência), **receita reconhecida** (software pro rata; taxa só na
quitação e só após a ativação da regra), **GMV** (originado e quitado; nunca somado à receita), **participação de autoria** (coluna
própria; nunca somada), **taxas e custos** (PIX sobre o recebido; tributos sobre o reconhecido — hipótese 8,65 %).

## 6. Valuation e patrimônio do fundador (FASE 6) — faixas, com as premissas à vista

Método: soma das partes — ARR de software × múltiplo SaaS + receita transacional líquida 12 m × múltiplo de marketplace + serviços 12 m ×
múltiplo baixo — tudo × (1 − desconto por concentração, risco regulatório, iliquidez e dependência do fundador). EV/EBITDA só como
cruzamento quando EBITDA > 0. **Nenhum múltiplo é aplicado a GMV.** Múltiplos por cenário: SaaS 2,5× / 4,0× / 6,0×; transacional 1,5× / 2,3× / 4,0×;
serviços 1,0× / 1,5× / 2,0×; desconto 45 % / 35 % / 25 %. Diluição (premissa): 100 % → 85 % (M12) → 70 % (M24) → 55 % (M48) → 45 % (M120).

Fontes externas (âncoras, não comparáveis diretos; nenhuma brasileira nem do terceiro setor): Software Equity Group, SaaS Index 2Q26 —
mediana pública EV/Receita TTM **3,2×** (2Q25: 5,7×), M&A privado mediana **4,0×** e média 6,2× (lido via peony.ink em 09/10/2026);
Aventis Advisors, SaaS Valuation Multiples 2015–2026 (abr/2026) — M&A privado mediana Q1 2026 3,1×, período 4,5×, negócios US$ 0–5 M ≈ 3,3×;
SaaS Capital 2025 — múltiplo de ARR **modelado** 4,8–5,3×; Aventis, Marketplace Valuation Multiples 2025 (S&P Capital IQ, mar/2025) —
público mediana EV/Receita **2,3×**, média histórica 5,6×, EV/EBITDA mediana 18×.

### 6.1 Desenho ATUAL

| Cenário | Marco | EV software | EV transacional | EV serviços | Desconto | **EV (faixa do cenário)** | Cruzamento EV/EBITDA | Participação do fundador | Patrimônio teórico | Participação necessária para R$ 100 mi / 500 mi / 1 bi / US$ 1 bi |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| conservador | M6 | R$ 0 | R$ 0 | R$ 1.582 | 45% | **R$ 870** | — | 100% | R$ 870 | 11490753% (>100%: inalcançável) / 57453764% (>100%: inalcançável) / 114907528% (>100%: inalcançável) / 631991405% (>100%: inalcançável) |
| conservador | M12 | R$ 0 | R$ 0 | R$ 5.643 | 45% | **R$ 3.103** | — | 85% | R$ 2.638 | 3222253% (>100%: inalcançável) / 16111263% (>100%: inalcançável) / 32222526% (>100%: inalcançável) / 177223894% (>100%: inalcançável) |
| conservador | M24 | R$ 0 | R$ 28.795 | R$ 14.413 | 45% | **R$ 23.764** | — | 70% | R$ 16.635 | 420799% (>100%: inalcançável) / 2103997% (>100%: inalcançável) / 4207994% (>100%: inalcançável) / 23143967% (>100%: inalcançável) |
| conservador | M48 | R$ 0 | R$ 110.851 | R$ 26.517 | 45% | **R$ 75.553** | — | 55% | R$ 41.554 | 132358% (>100%: inalcançável) / 661790% (>100%: inalcançável) / 1323580% (>100%: inalcançável) / 7279692% (>100%: inalcançável) |
| conservador | M120 | R$ 0 | R$ 186.025 | R$ 40.885 | 45% | **R$ 124.801** | — | 45% | R$ 56.160 | 80128% (>100%: inalcançável) / 400639% (>100%: inalcançável) / 801279% (>100%: inalcançável) / 4407033% (>100%: inalcançável) |
| base | M6 | R$ 0 | R$ 0 | R$ 8.515 | 35% | **R$ 5.535** | — | 100% | R$ 5.535 | 1806743% (>100%: inalcançável) / 9033715% (>100%: inalcançável) / 18067430% (>100%: inalcançável) / 99370865% (>100%: inalcançável) |
| base | M12 | R$ 0 | R$ 27.892 | R$ 30.857 | 35% | **R$ 38.187** | — | 85% | R$ 32.459 | 261871% (>100%: inalcançável) / 1309356% (>100%: inalcançável) / 2618712% (>100%: inalcançável) / 14402917% (>100%: inalcançável) |
| base | M24 | R$ 0 | R$ 617.020 | R$ 82.217 | 35% | **R$ 454.504** | — | 70% | R$ 318.153 | 22002% (>100%: inalcançável) / 110010% (>100%: inalcançável) / 220020% (>100%: inalcançável) / 1210109% (>100%: inalcançável) |
| base | M48 | R$ 0 | R$ 1.491.000 | R$ 164.358 | 35% | **R$ 1.075.983** | — | 55% | R$ 591.791 | 9294% (>100%: inalcançável) / 46469% (>100%: inalcançável) / 92938% (>100%: inalcançável) / 511160% (>100%: inalcançável) |
| base | M120 | R$ 0 | R$ 2.968.401 | R$ 303.212 | 35% | **R$ 2.126.549** | — | 45% | R$ 956.947 | 4702% (>100%: inalcançável) / 23512% (>100%: inalcançável) / 47025% (>100%: inalcançável) / 258635% (>100%: inalcançável) |
| agressivo | M6 | R$ 0 | R$ 0 | R$ 26.841 | 25% | **R$ 20.131** | — | 100% | R$ 20.131 | 496750% (>100%: inalcançável) / 2483751% (>100%: inalcançável) / 4967503% (>100%: inalcançável) / 27321264% (>100%: inalcançável) |
| agressivo | M12 | R$ 0 | R$ 1.196.122 | R$ 98.063 | 25% | **R$ 970.639** | — | 85% | R$ 825.043 | 10302% (>100%: inalcançável) / 51512% (>100%: inalcançável) / 103025% (>100%: inalcançável) / 566637% (>100%: inalcançável) |
| agressivo | M24 | R$ 0 | R$ 6.685.943 | R$ 266.997 | 25% | **R$ 5.214.705** | — | 70% | R$ 3.650.293 | 1918% (>100%: inalcançável) / 9588% (>100%: inalcançável) / 19177% (>100%: inalcançável) / 105471% (>100%: inalcançável) |
| agressivo | M48 | R$ 0 | R$ 16.150.438 | R$ 557.987 | 25% | **R$ 12.531.319** | R$ 22.068.215 | 55% | R$ 6.892.225 | 798,0% / 3990% (>100%: inalcançável) / 7980% (>100%: inalcançável) / 43890% (>100%: inalcançável) |
| agressivo | M120 | R$ 0 | R$ 35.407.620 | R$ 1.150.058 | 25% | **R$ 27.418.259** | R$ 80.066.272 | 45% | R$ 12.338.217 | 364,7% / 1824% (>100%: inalcançável) / 3647% (>100%: inalcançável) / 20060% (>100%: inalcançável) |

### 6.2 Desenho HÍBRIDO

| Cenário | Marco | EV software | EV transacional | EV serviços | Desconto | **EV (faixa do cenário)** | Cruzamento EV/EBITDA | Participação do fundador | Patrimônio teórico | Participação necessária para R$ 100 mi / 500 mi / 1 bi / US$ 1 bi |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| conservador | M6 | R$ 0 | R$ 0 | R$ 1.582 | 45% | **R$ 870** | — | 100% | R$ 870 | 11490753% (>100%: inalcançável) / 57453764% (>100%: inalcançável) / 114907528% (>100%: inalcançável) / 631991405% (>100%: inalcançável) |
| conservador | M12 | R$ 132.763 | R$ 0 | R$ 5.643 | 45% | **R$ 76.123** | — | 85% | R$ 64.704 | 131367% (>100%: inalcançável) / 656833% (>100%: inalcançável) / 1313666% (>100%: inalcançável) / 7225163% (>100%: inalcançável) |
| conservador | M24 | R$ 601.663 | R$ 28.795 | R$ 14.413 | 45% | **R$ 354.679** | — | 70% | R$ 248.275 | 28195% (>100%: inalcançável) / 140973% (>100%: inalcançável) / 281945% (>100%: inalcançável) / 1550698% (>100%: inalcançável) |
| conservador | M48 | R$ 1.298.176 | R$ 110.851 | R$ 26.517 | 45% | **R$ 789.550** | — | 55% | R$ 434.252 | 12665% (>100%: inalcançável) / 63327% (>100%: inalcançável) / 126654% (>100%: inalcançável) / 696600% (>100%: inalcançável) |
| conservador | M120 | R$ 2.282.027 | R$ 186.025 | R$ 40.885 | 45% | **R$ 1.379.915** | — | 45% | R$ 620.962 | 7247% (>100%: inalcançável) / 36234% (>100%: inalcançável) / 72468% (>100%: inalcançável) / 398575% (>100%: inalcançável) |
| base | M6 | R$ 0 | R$ 0 | R$ 8.515 | 35% | **R$ 5.535** | — | 100% | R$ 5.535 | 1806743% (>100%: inalcançável) / 9033715% (>100%: inalcançável) / 18067430% (>100%: inalcançável) / 99370865% (>100%: inalcançável) |
| base | M12 | R$ 1.685.372 | R$ 27.892 | R$ 30.857 | 35% | **R$ 1.133.678** | — | 85% | R$ 963.627 | 8821% (>100%: inalcançável) / 44104% (>100%: inalcançável) / 88208% (>100%: inalcançável) / 485146% (>100%: inalcançável) |
| base | M24 | R$ 4.766.004 | R$ 617.020 | R$ 82.217 | 35% | **R$ 3.552.407** | — | 70% | R$ 2.486.685 | 2815% (>100%: inalcançável) / 14075% (>100%: inalcançável) / 28150% (>100%: inalcançável) / 154825% (>100%: inalcançável) |
| base | M48 | R$ 9.917.015 | R$ 1.491.000 | R$ 164.358 | 35% | **R$ 7.522.042** | R$ 6.470.635 | 55% | R$ 4.137.123 | 1329% (>100%: inalcançável) / 6647% (>100%: inalcançável) / 13294% (>100%: inalcançável) / 73118% (>100%: inalcançável) |
| base | M120 | R$ 19.641.915 | R$ 2.968.401 | R$ 303.212 | 35% | **R$ 14.893.793** | R$ 28.789.779 | 45% | R$ 6.702.207 | 671,4% / 3357% (>100%: inalcançável) / 6714% (>100%: inalcançável) / 36928% (>100%: inalcançável) |
| agressivo | M6 | R$ 4.291.264 | R$ 0 | R$ 26.841 | 25% | **R$ 3.238.579** | — | 100% | R$ 3.238.579 | 3088% (>100%: inalcançável) / 15439% (>100%: inalcançável) / 30878% (>100%: inalcançável) / 169828% (>100%: inalcançável) |
| agressivo | M12 | R$ 12.619.722 | R$ 1.196.122 | R$ 98.063 | 25% | **R$ 10.435.430** | — | 85% | R$ 8.870.116 | 958,3% / 4791% (>100%: inalcançável) / 9583% (>100%: inalcançável) / 52705% (>100%: inalcançável) |
| agressivo | M24 | R$ 28.306.624 | R$ 6.685.943 | R$ 266.997 | 25% | **R$ 26.444.673** | R$ 43.364.864 | 70% | R$ 18.511.271 | 378,1% / 1891% (>100%: inalcançável) / 3781% (>100%: inalcançável) / 20798% (>100%: inalcançável) |
| agressivo | M48 | R$ 56.143.915 | R$ 16.150.438 | R$ 557.987 | 25% | **R$ 54.639.255** | R$ 131.497.217 | 55% | R$ 30.051.590 | 183,0% / 915,1% / 1830% (>100%: inalcançável) / 10066% (>100%: inalcançável) |
| agressivo | M120 | R$ 117.242.555 | R$ 35.407.620 | R$ 1.150.058 | 25% | **R$ 115.350.176** | R$ 320.368.703 | 45% | R$ 51.907.579 | 86,7% / 433,5% / 866,9% / 4768% (>100%: inalcançável) |

**O que esses números significam e o que não significam.** *Valuation* é o que a empresa poderia valer numa negociação sob estas premissas;
*patrimônio teórico* é a participação do fundador vezes esse valor — **não é dinheiro disponível** (só vira caixa numa venda secundária ou
saída, com desconto de iliquidez e tributos). Onde a participação necessária é > 100 %, a meta é **inalcançável** naquele marco e cenário.
Marco em que cada meta de patrimônio do fundador cabe dentro da participação que a diluição-premissa deixa (DERIVADO):

| Cenário / desenho | R$ 100 milhões | R$ 500 milhões | R$ 1 bilhão | US$ 1 bilhão |
|---|---|---|---|---|
| conservador / atual | não alcança em 120 m | não alcança em 120 m | não alcança em 120 m | não alcança em 120 m |
| conservador / hibrido | não alcança em 120 m | não alcança em 120 m | não alcança em 120 m | não alcança em 120 m |
| base / atual | não alcança em 120 m | não alcança em 120 m | não alcança em 120 m | não alcança em 120 m |
| base / hibrido | não alcança em 120 m | não alcança em 120 m | não alcança em 120 m | não alcança em 120 m |
| agressivo / atual | não alcança em 120 m | não alcança em 120 m | não alcança em 120 m | não alcança em 120 m |
| agressivo / hibrido | não alcança em 120 m | não alcança em 120 m | não alcança em 120 m | não alcança em 120 m |

Nenhuma meta cabe em nenhum cenário do repositório. Com 45% de participação em M120, R$ 100 milhões de patrimônio
teórico exigiriam valuation de R$ 222.222.222; o melhor cenário modelado (agressivo híbrido) chega a R$ 115.350.176 em M120 — ou seja,
faltam 1.9× em valor, e R$ 1 bilhão exigiria 10× isso. A resposta à pergunta "qual ritmo é necessário" é: tickets,
volumes e contratos acima do cenário agressivo (ou diluição muito menor), para os quais **não há evidência hoje**. A planilha permite testar
que combinação de contratos, operações, preços e custos chegaria lá — mas um número que a planilha calcula não é uma previsão.

## 7. Sensibilidade e testes de estresse (FASE 7) — cenário Base, desenho HÍBRIDO

| Choque | Receita acumulada 120 m | Necessidade de capital | Ponto de equilíbrio | Caixa em M120 | EV em M48 |
|---|---:|---:|---:|---:|---:|
| (referência: Base híbrido) | R$ 40.017.584 | R$ 1.087.401 | 29 | R$ 11.150.786 | R$ 7.522.042 |
| crescimento 50 % menor (financiadores e contratos) | -50.0% | R$ 1.798.959 | 53 | R$ 1.135.393 | R$ 3.761.021 |
| metade das operações por financiador | -10.7% | R$ 1.210.679 | 36 | R$ 7.511.320 | R$ 7.037.467 |
| ticket médio financiado 50 % menor | -10.7% | R$ 1.210.681 | 36 | R$ 7.511.297 | R$ 7.037.467 |
| quitação 3 meses mais lenta | -0.9% | R$ 1.144.133 | 30 | R$ 10.841.249 | R$ 7.460.050 |
| churn dobrado | -24.3% | R$ 1.061.028 | 31 | R$ 7.322.921 | R$ 6.227.658 |
| CAC dobrado | +0.0% | R$ 1.511.948 | 35 | R$ 8.882.786 | R$ 7.522.042 |
| pessoal e infra 30 % maiores | +0.0% | R$ 1.938.736 | 44 | R$ 4.644.049 | R$ 7.522.042 |
| inadimplência 15 % | +0.0% | R$ 1.374.500 | 29 | R$ 6.430.744 | R$ 7.522.042 |
| ausência de contratos institucionais | -75.4% | R$ 13.116.534 | não alcança | R$ -13.116.534 | R$ 1.075.983 |
| taxa transacional nunca ativada | -21.4% | R$ 1.441.914 | 48 | R$ 3.871.807 | R$ 6.552.892 |
| concentração: 3 financiadores saem no mês 13 (churn 40 % no ano 2) | -10.0% | R$ 1.052.136 | 28 | R$ 12.588.197 | R$ 7.214.440 |

**Variáveis que mais afetam caixa, sobrevivência e valuation:** (1) existência e ritmo dos **contratos institucionais** — sem eles o desenho
volta ao ATUAL e não há equilíbrio nos cenários conservador/base; (2) **ticket financiado** e **operações por financiador** (a taxa é
percentual de um volume que a plataforma não controla); (3) **ativação da taxa** (parecer) — se nunca ativar, resta software + serviços;
(4) **custo de pessoal por cliente**; (5) churn/concentração. Inadimplência e prazo de quitação pesam menos que os cinco acima.

## 8. Riscos, conformidade e o que precisa de parecer (FASE 8)

| Tema | Risco | Estado no repositório | Para parecer |
|---|---|---|---|
| Cobrança por intermediação / taxa de êxito | enquadramento como instituição de pagamento (Lei 12.865/2013, art. 6º) e conflito de interesse | `success_fee.funding` e `marketplace.take_rate` **recusadas**; não custodial (ADR-284) | não reabrir sem advogado de meios de pagamento |
| Natureza da taxa de serviço (3,5 %) | serviço de software (ISS/NFS-e) × intermediação; base de cálculo; modo deducted (projeto recebe menos) | carta amarela; regra inativa; `fee_mode` no acordo | parecer jurídico + contábil antes da carta verde |
| Contratos com entes públicos | Lei 14.133/2021: licitação / dispensa / inexigibilidade não analisadas | `b2g.territorial_governance` recusada; **sem checkout para governo** | advogado de contratações públicas; modelo de edital/termo |
| Contrato institucional anual (HÍBRIDO) | reintroduz receita recorrente que a ADR-341 retirou; tributação (ISS, Simples/Presumido), reajuste, cancelamento, CDC não se aplica a B2B mas aplica-se a pessoa física | não existe | decisão do proprietário + ADR + parecer contábil |
| Créditos de IA pré-pagos | reconhecimento (obrigação até consumo), validade/devolução (CDC), NFS-e | piloto; carta amarela | parecer antes de venda real |
| Recursos de terceiros | nunca tratados como caixa próprio; nenhuma tabela de saldo; conciliação manual | provado por teste | manter; qualquer parceiro de pagamento exige revisão |
| Dados territoriais como produto | LGPD (reidentificação em agregados pequenos); DPO inexistente | `data.territorial_intelligence` recusada | RIPD + DPO antes de qualquer produto de dado |
| Tributos no modelo | 8,65 % é **hipótese** (não é regime definido) | `config/ai_economics.json` | contador define regime e alíquotas |

## 9. Roadmap de execução (FASE 9) — validação comercial antes de funcionalidade cara

| Horizonte | Iniciativa | Valor esperado | Custo | Responsável | Dependências | Risco | Métrica de sucesso | Critério de interrupção |
|---|---|---|---|---|---|---|---|---|
| 0–90 dias | Parecer jurídico/contábil da taxa de serviço (carta verde) e da matriz de elegibilidade de cobrança | destravar a única receita transacional já construída | honorários (não estimados) | proprietário | advogado(a), contador(a) | parecer negativo | carta verde registrada; regra ativável | parecer contrário à natureza de serviço de software |
| 0–90 dias | **Validação comercial** do contrato institucional: 10 conversas com financiadores/fundações, 3 cartas de intenção com preço | evidência de disposição a pagar (hoje zero) | tempo do fundador | proprietário | dossiê e torres já existem (v0.26–0.30) | ninguém paga | ≥ 3 LOIs com valor ≥ R$ 3 mil/mês | 0 LOIs em 90 dias → não reabrir ADR-341 |
| 0–90 dias | Medir custos reais (folha planejada, nuvem, suporte) e substituir as premissas de mercado da planilha | modelo deixa de ser hipótese sobre hipótese | baixo | proprietário | faturas | — | `UNIT_ECONOMICS.md` sem `[PENDENTE]` de custo | — |
| 3–6 meses | Se houver LOIs: ADR nova + catálogo (regra `enterprise.esg_portfolio`/implantação ativáveis por contrato avulso) + contrato-modelo | primeiros contratos | desenvolvimento pequeno (proposta/aceite já existem: `offer_acceptances`) | proprietário + dev | ADR, parecer | reintroduzir paywall por descuido | 3 contratos assinados e faturados | invariantes quebrados (teste) |
| 3–6 meses | Piloto da taxa de serviço em 3 operações reais com carta verde | primeira receita transacional reconhecida | — | proprietário + 1 financiador âncora | parecer; `PLATFORM_PIX_KEY` | quitação não acontece | 3 operações quitadas e taxa paga | nenhuma quitação em 6 meses |
| 6–12 meses | B2G por procedimento (dispensa/inexigibilidade) com 1 órgão | contrato público | jurídico | proprietário | Lei 14.133 | prazo público | 1 contrato | — |
| 12–24 meses | Reavaliar múltiplos e cenários com 12 meses de dados reais; decidir capital (ou não) | plano de capital baseado em fato | — | proprietário | histórico | — | modelo recalibrado | — |

## 10. Decisões que dependem do proprietário

1. **Reabrir ou não a ADR-341** para contratos institucionais anuais (desenho HÍBRIDO). O modelo mostra que, nos cenários conservador e base, sem eles não há equilíbrio.
2. **Ativar a taxa de serviço** (carta verde) — depende de parecer; definir modo padrão (`deducted`/`additional`) e quem paga.
3. **Preços**: aceitar as faixas-hipótese (R$ 36/72/120 mil por ano; implantação R$ 10–30 mil; R$ 29/79; créditos) como preços de **teste** com validação comercial, ou pesquisar antes.
4. **B2G**: investir em procedimento de contratação pública ou adiar.
5. **Capital**: aceitar necessidade de capital estimada (hipótese) ou crescer com caixa (menos FTE) — a planilha permite testar.
6. **Regime tributário** e estrutura societária (diluição-premissa) — contador(a).
7. **UNIT_ECONOMICS.md** superado: marcar e substituir pelo modelo de 120 meses quando os custos forem medidos.

## 11. Lacunas e como medi-las

| Lacuna | Como medir | Prazo sugerido |
|---|---|---|
| Disposição a pagar por contrato institucional | 10 entrevistas + 3 LOIs com preço | 90 dias |
| Ticket e frequência reais de operações | 3 operações piloto quitadas | 6 meses |
| Custo de pessoal, nuvem, suporte | folha planejada + 3 faturas | 30 dias |
| Churn e concentração | 12 meses de carteira | 12 meses |
| Alíquotas | parecer contábil | 30 dias |
| Múltiplos aplicáveis ao Brasil/terceiro setor | comparáveis privados (não encontrados nesta rodada) | contínuo |

## 12. Entregáveis desta análise

`IMPACTO_MODELO_120M.xlsx` (premissas editáveis, 6 abas mensais com fórmulas abertas, marcos, fontes; recalculada e conferida), `resultados_120m.json`,
gráficos `g1`–`g9` (PNG), este relatório (MD e DOCX), `scripts/analysis/economic_model_120m.py` (motor) e `make_economic_report.py` (este texto).
**Nenhuma alteração no produto.** A FASE 10 (implementação) só começa com a aprovação explícita das decisões do §10.
