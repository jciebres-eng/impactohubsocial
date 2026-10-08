# MODELO ECONÔMICO DO IMPACTO — v0.27.0 (ADR-341)

**Uma frase:** o IMPACTO é infraestrutura de inteligência e operação de impacto, remunerada pelo valor econômico
que cria em cada operação financiada — **não por assinatura**. Estar no IMPACTO é a condição para alcançar
recursos e comprovar evidência; quem não está perde oportunidade de recurso e de melhoria real.

Este é o documento canônico do modelo. Os documentos de assinatura (PRICING_BIBLE §3/§4.2/§8, BILLING_V2,
TRIAL_SYSTEM, COMMERCIAL_TERMS, docs/billing.md, docs/BUSINESS_MODEL.md) estão marcados como SUPERADOS e
ficam como histórico. O inventário do que foi mantido, migrado, aposentado e removido está em
`docs/execution/SUBSCRIPTION_INVENTORY.md`.

## 1. De onde vem o valor — e de onde vem a receita

| Camada | O que é | É receita da plataforma? |
| --- | --- | --- |
| Núcleo | cadastro, perfil, projeto, diagnóstico, documentos, match, acordos, evidência, rede, torres | **Não.** Gratuito por desenho, sem prazo. |
| Camada econômica da operação financiada | 5% do valor financiado: **3,5%** taxa de serviço contratada da plataforma + **1,5%** participação de autoria do proponente | Só os 3,5%, e só quando PAGOS e com a regra comercial ativa. Os 1,5% vão ao proponente. |
| Contratos avulsos/parcelados | implantação, integração, módulo institucional, inteligência territorial, API | Sim, pelo valor do contrato aceito com autorização de cobrança. |
| Concessão, convênio, voucher | pacotes de capacidades por prazo | **Não.** Concedem; nunca cobram. |
| Marketplace | contratação entre partes | **Não.** Comissão recusada (ADR-022/178). |
| IA/API | uso medido | **Não** hoje: sem preço de excedente publicado, exceder o limite interrompe, não cobra. |

**GMV ≠ receita.** O valor financiado vai do financiador ao projeto; a plataforma não custodia (ADR-284).

## 2. Como a camada econômica nasce, se distribui e se quita

1. **Regra no catálogo versionado.** `economic_rules` (Pricing Version 2027.02): `funding.platform_service`
   350 bps (pagador: financiador → plataforma; portão jurídico `contract.platform_service_fee`) e
   `funding.proponent_participation` 150 bps (financiador → proponente). Percentual nunca em código.
2. **Congelada no acordo.** Ao nascer, o acordo de FINANCIAMENTO recebe `platform_fee_bps`,
   `proponent_participation_bps` e `economic_rule_version` do catálogo. O cliente não envia taxa (422
   `fee_determined_by_pricing_version`). Mudar o contrato cria versão nova; a anterior fica.
3. **Matriz de distribuição na ativação** (`agreement_allocations`, imutável, com hash): bruto; projeto;
   plataforma (3,5%); proponente (1,5% dividido pelas frações aceitas, resto na última); terceiros. Modo
   `deducted` (projeto = bruto − camada) ou `additional` (projeto cheio, financiador paga a camada à parte);
   a soma fecha nos dois por CHECK.
4. **Instruções de repasse** (`allocation_payouts`): uma por linha da matriz, com a **chave PIX informada no
   contrato por cada parte** (validada por tipo; a da plataforma vem de `PLATFORM_PIX_KEY`). O financiador faz
   **um aporte só, direcionado**: cada linha diz quem recebe, quanto e para qual chave. A linha da plataforma
   nasce `awaiting_rule` enquanto a regra comercial estiver inativa — registrada, não exigível.
5. **Transferência registrada por quem paga, confirmada por quem recebe** (`payout_transfers`): idempotente
   por referência, soma limitada ao valor da linha; recusa → `disputed`; conciliação com nota é passo
   separado. Nada vira "pago" por existir registro.
6. **Livro econômico** (`economic_events`, append-only, idempotente): `platform_service_registered` → `due`
   (regra ativa) → `paid` (confirmado pela plataforma); `proponent_participation_accrued` → `paid`;
   `project_funds_instructed` → `confirmed`; `operation_settled`; `reversal` (nova versão, cancelamento).
7. **Operação quitada** = toda entrega aceita E todo repasse devido confirmado. Só então nascem os
   **reconhecimentos** (OSC `operation_settled`, financiador `funding_settled`, proponente
   `participation_paid`) — nunca por pagar a plataforma, plano ou voucher. A trajetória pública é cumulativa
   (contagens e datas; nunca valores).

## 3. Participação de autoria (1,5%) — nunca automática

proposta (executora) → aceita (**só o proponente**) → consolidada (projeto publicado) → elegível (acordo em
vigor com a parte `proponent`) → na matriz → paga (repasse confirmado pelo proponente). Frações somam até
100% (gatilho). Ideia referenciada por `solutions` (kind idea, publicada) ou `ideas` da organização. Não
domina a experiência nem é o modelo de cobrança: é uma linha da matriz quando há autoria contratada.

## 4. O que é de quem, e como o contrato diz

| Linha | Quem recebe | Chave PIX | Quando |
| --- | --- | --- | --- |
| Projeto | OSC executora (parte `contractor`) | informada pela OSC no acordo | instrução na ativação; confirmação pela OSC |
| Plataforma (3,5%) | pessoa jurídica titular do IMPACTO | `PLATFORM_PIX_KEY` (configuração; "NÃO CONFIGURADA" quando vazia) | `awaiting_rule` até carta verde; depois instrução → confirmação pela administração (`billing.write`) |
| Proponente (1,5%) | parte `proponent` elegível | informada pelo proponente no acordo | instrução na ativação; confirmação pelo proponente |
| Terceiros | prestador/profissional, se houver no contrato | informada pela parte | idem |

Tudo isto está discriminado na tela do acordo ("Matriz de distribuição", "Repasses", "O que o IMPACTO fez
nesta operação") e na pré-visualização antes da assinatura.

## 5. Estados de pagamento (instrução)

`awaiting_rule` → `instruction_created` → `payment_pending` → `confirmed` → `reconciled`; ramos `failed`,
`disputed`, `cancelled`, `refund_pending` → `refunded`. Transições no banco (`payout_state_guard`);
instrução imutável nos campos de valor e destino (`payout_immutable_guard`).

## 6. Anti-bypass (o que o banco e as rotas recusam)

* cliente define taxa (422); catálogo imutável para a aplicação;
* transferência duplicada por referência (idempotente); soma acima da linha (gatilho);
* pagador "confirma" a própria transferência (403); plataforma confirma linha que não é sua (409);
* operação quitada sem confirmações (não acontece: derivada);
* nova versão/cancelamento sem estorno econômico (não acontece: `reversal` obrigatório);
* cobrança própria real sem autorização (gatilho: contrato aceito OU acordo de financiamento assinado pelo
  pagador com taxa — ADR-342).
Provas: `backend/tests/test_v0270_economy.py` (cenários A–O), `test_v0260_contract_rules.py`,
`test_v0270_no_subscription.py`.

## 7. Captura de valor e torre MASTER

`GET /v1/control-tower/master` (`finance.read`): GMV × camada (registrado/devido/pago por mês), participação,
marketplace sem percentual, uso de IA/API, contratos, a receber, **banco: DADO FINANCEIRO NÃO CONECTADO**,
captura de valor (`value_capture_ratio` = camada paga ÷ recursos de projeto confirmados; **NÃO MEDIDO** sem
denominador). Cadeia: `value_events` (contract.activated, allocation.instructed, payout.confirmed,
operation.settled) → `economic_events` → `platform_charges`.

## 8. Simulação de 24 meses

`24_MONTH_FINANCIAL_MODEL.md`, gerado por `scripts/make_24_month_model.py` a partir de
`config/economic_model.json` (3 cenários, 3 clientes/mês, sensibilidade R$ 50 mil → R$ 10 milhões, GMV
necessário para R$ 1/5/10 milhões). Tudo [PREMISSA]; receita real desta instalação: R$ 0,00.

## 9. O que ainda depende de fora (BLOCKED_EXTERNAL_DEPENDENCY)

Parecer jurídico/contábil para ativar `contract.platform_service_fee` (Lei 12.865/2013, ISS, nota fiscal);
chave PIX real da plataforma; provedor de pagamento/banco para conciliação automática. Até lá: registrado e
instruído, **nada devido, nada cobrado** — `EXTERNAL_INTEGRATIONS.md`.
