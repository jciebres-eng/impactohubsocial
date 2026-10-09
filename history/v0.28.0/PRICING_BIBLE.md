# PRICING BIBLE — IMPACTO TRUST

**Pricing Version:** `2027.02` (v0.27.0) — a `2027.01` está **superada** no ponto da assinatura.
**Status do documento:** fonte de verdade COMERCIAL, fornecida pelo proprietário.

> ⚠️ **ADR-341 (v0.27.0, 08/10/2026): NÃO EXISTE MAIS ASSINATURA.** A Pricing Version 2027.01 publicou
> mensalidades (§3), três meses para assinatura nova (§4.2) e reajuste com aviso (§8). O proprietário
> retirou a assinatura do modelo econômico: o IMPACTO é infraestrutura de inteligência e operação de
> impacto, remunerada pela **camada econômica da operação financiada** — 5% do valor financiado, sendo
> **3,5% taxa de serviço contratada da plataforma** e **1,5% participação de autoria do proponente** quando
> contratualmente elegível — e por **contratos avulsos/parcelados** (implantação, módulo institucional,
> inteligência territorial, API). Os percentuais vivem em `economic_rules` (Pricing Version 2027.02) e são
> congelados em cada acordo; nunca em código. O que continua valendo desta Bíblia: §1 (núcleo gratuito por
> desenho), §2 (o que o pagamento nunca compra), §4.1 (FULL FREE 2026, agora como concessão), §4.4 (acesso
> gratuito ≠ autorização de cobrança), §5 (regras transacionais desligadas), §6, §7, §9 e §10. Os §3, §4.2,
> §4.3 (origem `2027_NEW_SUBSCRIPTION`) e §8 ficam como HISTÓRICO. Inventário completo:
> `docs/execution/SUBSCRIPTION_INVENTORY.md`.

**Status dos valores:** referência inicial de uma versão de preço — **não é verdade eterna**.
**Validação pendente:** jurídica, fiscal e operacional antes da publicação comercial definitiva.

---

## 0. O QUE ESTE DOCUMENTO É, E O QUE NÃO É

Este documento é a **decisão comercial do proprietário**. Ele diz quanto a plataforma
pretende cobrar, de quem, por quê e sob que condições.

Ele **não** é:

* uma declaração de que os valores estão implementados — a implementação está em
  `config/plans.json` (`price_versions.items`) e no banco (`plan_price_versions`), e o que
  vale para cobrança é o banco;
* uma declaração de conformidade jurídica ou fiscal — nenhum valor aqui foi validado por
  advogado ou contador;
* um contrato — o contrato é a minuta aprovada em `legal_documents`, e hoje **todas as 11
  minutas estão em `draft`** (ver `MONETIZATION_LEGAL_MATRIX.md`).

Toda alteração de valor **cria uma nova Pricing Version**. Preço não se sobrescreve: a
vigência da versão anterior é fechada e uma nova entra. Isso é imposto por gatilho de banco
(`price_version_immutable()`, migração `0017`), não por disciplina.

### Regra de reconciliação (AUDIT → RECONCILIATION → PRICING VERSION)

Quando este documento diverge do que já existe no código, a regra **não** é apagar o que
existe. É:

1. **AUDIT** — localizar a regra vigente no código, no banco e nos testes;
2. **RECONCILIATION** — registrar a divergência e a decisão, com o motivo;
3. **PRICING VERSION** — aplicar a decisão como versão nova, preservando o histórico.

A matriz de reconciliação desta rodada está em `PRICING_RECONCILIATION.md`.

---

## 1. PRINCÍPIO ECONÔMICO

```
CORE IMPACTO = GRATUITO
```

O núcleo — cadastro, perfil, entrada no ecossistema, projeto básico, ideia, participação,
descoberta de oportunidades, match básico, diagnóstico básico, evidência básica e acesso
básico a dados públicos — é gratuito **por desenho**, não por prazo.

A monetização vem de: escala, automação, IA, analytics, governança, integrações, API,
volume, serviços, marketplace, enterprise, governo e operações transacionais elegíveis.

---

## 2. O QUE O PAGAMENTO NUNCA COMPRA

Esta é uma **invariante do produto**, não uma política comercial. Está travada por teste
(`backend/tests/test_v0210_pricing_catalog.py`) e declarada em
`config/plans.json` → `never_sellable`.

| Nunca vendável | Por quê |
| --- | --- |
| Reputação | reputação é consequência de conduta registrada, não de fatura |
| Verificação / selo | selo atesta documento conferido; dinheiro não confere documento |
| Impacto | `impact_score += payment` é falsificação de resultado social |
| Evidência | evidência é prova; prova comprada não é prova |
| Verdade | nenhuma afirmação fica mais verdadeira porque o autor pagou |
| Elegibilidade | elegibilidade vem de regra pública (edital, lei), não de plano |
| Qualidade do match | o match explica por que casou; pagar não muda a razão |
| Posição em ranking | `provider_rank`, `provider_featured`, `provider_badge`, `match_boost` |

O que o pagamento compra: **capacidade, volume, automação, suporte e ferramenta**.

---

## 3. CATÁLOGO — PRICING VERSION 2027.01

Valores em reais (BRL). "A partir de" significa **proposta comercial**, não contratação
online: a plataforma recusa checkout para esses planos em vez de inventar um valor.

| Plano (Bíblia) | `plan_key` | Público | Mensal | Anual | Contratação |
| --- | --- | --- | ---: | ---: | --- |
| FREE — Pessoa | `individual_basic` | pessoa física | R$ 0 | — | online |
| FREE — OSC | `osc_basic` | organização da sociedade civil | R$ 0 | — | online |
| FREE — Profissional | `provider_basic` | profissional / prestador | R$ 0 | — | online |
| FREE — Empresa | `company_basic` | empresa / financiador | R$ 0 | — | online |
| FREE — Governo | `government_basic` | órgão público | R$ 0 | — | online |
| PROFESSIONAL PRO | `provider_premium` | profissional autônomo | R$ 49 | — | online |
| PRO | `osc_plus` | OSC pequena, consultor, gestor | R$ 299 | R$ 2.990 | online |
| BUSINESS — OSC | `osc_premium` | OSC média, operação de captação | R$ 799 | R$ 7.990 | online |
| BUSINESS — Empresa | `company_plus` | empresa média, fundação, equipe | R$ 799 | R$ 7.990 | online |
| FUNDER PRO | `company_premium` | financiador com programa próprio | R$ 1.490 | — | online |
| ENTERPRISE | `company_enterprise` | grande volume, SLA, ambiente dedicado | a partir de R$ 2.500 | — | **proposta** |
| GOV | `gov_institutional` | governo, B2G | a partir de R$ 3.500 | — | **proposta** |

### Notas de mapeamento (por que cada plano recebeu este valor)

* **`osc_plus` → PRO.** A Bíblia (§12) destina o PRO a "profissionais, pequenas
  organizações, consultores, gestores". `osc_plus` é o primeiro degrau pago da OSC.
* **`osc_premium` e `company_plus` → BUSINESS, ambos R$ 799.** A Bíblia (§13) destina o
  BUSINESS a "organizações médias, empresas, fundações, equipes, operações com múltiplos
  projetos". Uma OSC com operação de captação e uma empresa média compram a mesma
  capacidade; o preço é o mesmo porque o custo de servir é o mesmo. O **papel** muda as
  funcionalidades, não o preço do degrau.
* **`company_premium` → FUNDER PRO (§24), R$ 1.490/mês.** A Bíblia não publica valor anual
  para este plano. **Nenhum valor anual foi criado** — inventar um desconto anual seria
  inventar preço. Fica mensal até o proprietário decidir.
* **`provider_premium` → PROFESSIONAL PRO (§17), R$ 49/mês.** Mesma regra: sem anual
  publicado, sem anual criado.
* **FUNDER CORPORATE (§25, a partir de R$ 3.500)** não tem `plan_key` próprio. É tratado
  como **escopo de proposta** dentro de `company_enterprise`, cujo piso publicado é
  R$ 2.500: propostas de escopo corporate de financiador partem de R$ 3.500. Registrado
  como lacuna em `PRICING_RECONCILIATION.md` (R-11) — criar um plano separado exige
  decisão do proprietário, e esta rodada não inventa planos.
* **Planos "a partir de"** gravam o piso em `quote_floor_cents` (`config/plans.json`), que
  a interface exibe como "a partir de R$ X — sob proposta". Piso publicado **não é preço
  contratável**: não existe linha em `plan_price_versions` para eles, e o checkout recusa.

### Desconto anual

R$ 2.990/ano contra R$ 299 × 12 = R$ 3.588 → **16,7%**.
R$ 7.990/ano contra R$ 799 × 12 = R$ 9.588 → **16,7%**.

O desconto anual é **consequência dos dois valores publicados**, não um percentual
configurável à parte. Não há "desconto de X%" em lugar nenhum do código.

---

## 4. GRATUIDADE TEMPORAL — FULL FREE 2026 E OS 3 MESES DE 2027

### 4.1 FULL FREE 2026

Todo o produto é **integralmente gratuito até `2026-12-31 23:59:59` (America/Sao_Paulo)**.
A partir de `2027-01-01 00:00:00` (America/Sao_Paulo) vale a tabela desta versão.

Isto **não** é um prazo global escrito no código. Cada conta elegível recebe um **registro
individual** em `free_periods` com `source = '2026_CAMPAIGN'`. A razão é operacional: uma
data global no código não sabe responder "esta conta específica está paga ou gratuita, e
até quando, e por quê" — e é essa pergunta que a cobrança, o suporte e a auditoria fazem.

### 4.2 Três meses para novas assinaturas a partir de 2027

Toda assinatura elegível criada a partir de `2027-01-01` recebe **3 meses gratuitos**,
registrados individualmente com `source = '2027_NEW_SUBSCRIPTION'`.

**"3 meses" significa 3 MESES DE CALENDÁRIO, não 90 dias.** A decisão e o motivo estão em
`FULL_FREE_2026.md` §3 e em ADR-268. Em resumo: o cliente compara o fim do período com a
data em que assinou ("assinei dia 15, acaba dia 15"); 90 dias quebra essa expectativa em
todo trimestre que contenha um mês de 31 dias. O tratamento de dia inexistente
(31/01 + 1 mês) é o último dia do mês de destino, e há teste para cada caso.

### 4.3 Fontes de período gratuito

`2026_CAMPAIGN`, `2027_NEW_SUBSCRIPTION`, `PROMOTION`, `GRANT`, `PARTNERSHIP`,
`MANUAL_EXCEPTION`. Toda concessão manual exige motivo e fica no registro de auditoria.

### 4.4 ACESSO GRATUITO ≠ AUTORIZAÇÃO DE COBRANÇA

São dois atos distintos, com dois registros distintos:

| | Acesso gratuito | Autorização de cobrança |
| --- | --- | --- |
| O que é | direito de usar sem pagar | permissão para debitar um meio de pagamento |
| Exige meio de pagamento | **não** | sim |
| Registro | `free_periods` | `offer_acceptances` com `consent_status = 'authorized'` |
| Fim do período gratuito sem autorização | conta cai para o plano gratuito | — |

**Nenhuma cobrança ocorre sem autorização explícita.** O fim do período gratuito não
autoriza nada: sem autorização, a conta **não é cobrada e não é suspensa** — ela volta ao
plano gratuito, que é permanente. Nenhum dado é apagado.

---

## 5. RECEITA TRANSACIONAL — DECLARADA, DESLIGADA

Estas regras existem no catálogo e estão **inativas**. Não é esquecimento: é a conclusão da
auditoria jurídica registrada em ADR-178.

| Regra | Faixa | Estado | Por quê |
| --- | --- | --- | --- |
| Marketplace take rate | 10% (faixa 8–12%) | **inativa** | ver §5.1 |
| Success fee | 2–3% | **inativa** | exige contrato, evento de sucesso definido, base de cálculo, limite, tratamento fiscal e consentimento (§22 da Bíblia) |
| Transaction fee de financiamento | 1–3% | **inativa** | `TRANSACTION_FEE_ENABLED = false` até validação jurídica/fiscal da operação específica (§26 da Bíblia) |

### 5.1 Take rate: por que 10% está declarado e não cobrado

A Bíblia (§20) autoriza take rate **somente quando existir** `service + contract +
transaction`. A plataforma hoje **não custodia nem intermedeia o pagamento do serviço**:
ela registra a contratação, e o dinheiro vai direto do contratante ao prestador.

Disso decorrem dois impedimentos, ambos registrados em ADR-178:

1. **Verificabilidade** — cobrar percentual sobre um valor que a plataforma não vê não é
   verificável. O valor seria o declarado por uma das partes, e a fatura da plataforma
   estaria apoiada em declaração, não em fato.
2. **Regulação** — receber para repassar pode caracterizar arranjo de pagamento e exigir
   autorização do Banco Central (Lei 12.865/2013).

Há um gatilho de banco que recusa ativar `marketplace_take_rate` e `success_fee` citando a
ADR-022 na mensagem de erro. **Este documento não o remove.** O percentual de 10% fica
registrado como regra da Pricing Version 2027.01, com `active = false`, e passa a ser
cobrável quando — e somente quando — a custódia existir e a validação jurídica for
concluída. A Bíblia e a arquitetura dizem a mesma coisa; a arquitetura apenas a impõe.

A plataforma **não cobra take rate** por perfil, visualização, busca, candidatura ou
proposta não contratada.

---

## 6. MEDIÇÃO DE USO

| Alerta | Gatilho |
| --- | --- |
| Aviso | 70% da franquia |
| Alerta | 90% da franquia |
| Esgotado | 100% da franquia |

O cliente pode definir um **teto de gasto mensal** (`monthly_spend_limit`) e escolher o que
acontece ao atingi-lo: avisar ou **parar** (`hard_stop`). Com `hard_stop`, a plataforma
interrompe o consumo excedente em vez de gerar fatura surpresa.

**O excedente não é cobrado automaticamente.** Sem preço de excedente publicado e sem
autorização, a plataforma bloqueia ou avisa — nunca cobra.

---

## 7. AVISOS COMERCIAIS

Antes do fim de qualquer período gratuito, a plataforma avisa em
**90, 60, 30, 7 e 1 dia**, mais um lembrete semanal nos últimos 30 dias.

A fonte única de verdade da data é o backend (`free_periods.ends_at`, exposto como
`FREE_PERIOD_END`). **A interface nunca calcula essa data** — ela lê o estado que o backend
publica. Isso elimina a classe inteira de defeitos em que a tela mostra um prazo e a
cobrança usa outro.

---

## 8. REAJUSTE

Aumento de preço para quem já assina exige **aviso prévio de 30 dias** registrado em
`price_change_notices`. Isto é imposto por gatilho de banco (`price_apply_guard()`,
migração `0017`): a tentativa de aplicar aumento sem aviso vigente é recusada pelo banco,
não pela aplicação.

O preço que a organização aceitou fica **congelado** em `subscription_prices` com a data e
o autor do aceite. Responder "quanto esta organização contratou em março?" é consulta, não
arqueologia.

---

## 9. LIMITES DE CONFORMIDADE

A arquitetura comercial respeita dignidade, direitos humanos, igualdade, não discriminação,
proporcionalidade, bioética, LGPD, legislação consumerista, contratual e fiscal, regras de
arranjos de pagamento e regras de contratação pública quando aplicáveis.

**O sistema não declara conformidade jurídica definitiva.** Onde é preciso parecer
profissional, o estado é `[VALIDAR JURÍDICO]` e fica visível — não escondido.

---

## 10. O QUE AINDA NÃO ESTÁ DECIDIDO

Honestidade de fechamento: estes pontos **não** têm resposta nesta versão.

1. Valor anual de `provider_premium` e `company_premium` — não publicado, não inventado.
2. `FUNDER CORPORATE` como plano próprio ou escopo de proposta (R-11).
3. Preço de excedente por unidade — sem isso, excedente não é cobrado, é bloqueado.
4. Aprovação das 11 minutas jurídicas, hoje todas em `draft`.
5. Validação fiscal do enquadramento de cada receita (nota, tributo, retenção).
6. Autorização regulatória para qualquer modelo com custódia de valores.

Nenhum destes impede a operação gratuita de 2026. Todos impedem cobrança.
