# ARQUITETURA NÃO-CUSTODIAL — A REGRA ACIMA DE TODAS AS OUTRAS

**Versão:** v0.22.0 · **ADR-284** · **Status:** vinculante

---

## 0. A REGRA

> **Não implemente uma fintech dentro do IMPACTO só porque isso parece aumentar a monetização.
> Primeiro prove que a mesma receita e garantia operacional podem ser obtidas com uma arquitetura
> de software/orquestração muito mais simples.**

Esta regra está **acima** de qualquer pedido de funcionalidade, inclusive dos prompts desta rodada.
Quando um pedido e esta regra discordarem, a regra ganha e a divergência é registrada — não
silenciada.

O que ela proíbe não é cobrar. É **passar dinheiro pela plataforma** sem necessidade.

---

## 1. O DESENHO

```
                 IMPACTO TRUST
                      │
       ┌──────────────┼──────────────┐
       │              │              │
    GOVERNANÇA     INTELIGÊNCIA    EXECUÇÃO
       │              │              │
       └──────────────┼──────────────┘
                      │
               FINANCIAL ENGINE
                      │
       ┌──────────────┼──────────────┐
       │              │              │
   CALCULA         INSTRUI       CONCILIA
       │              │              │
       └──────────────┼──────────────┘
                      │
             PAGAMENTOS EXTERNOS
                      │
          ┌───────────┴───────────┐
          ▼                       ▼
      BENEFICIÁRIO           PROFISSIONAL
          │                       │
          └───────────┬───────────┘
                      ▼
                  EVIDÊNCIA
                      │
                      ▼
                   IMPACTO
```

O `FINANCIAL ENGINE` faz **três** coisas, e nenhuma delas é mover dinheiro:

| Verbo | O que é | O que NÃO é |
| --- | --- | --- |
| **CALCULA** | quanto é devido, a quem, por qual regra, com qual base | não debita, não credita saldo |
| **INSTRUI** | emite a instrução de pagamento para quem paga executar | não executa o pagamento |
| **CONCILIA** | confronta o esperado com o que de fato aconteceu | não corrige o extrato de ninguém |

O dinheiro vai **direto** de quem paga a quem recebe. A plataforma sabe o que deveria acontecer,
registra o que aconteceu, e aponta a diferença.

---

## 2. A PROVA, COM NÚMEROS DO PRÓPRIO CÓDIGO

A regra pede que se **prove** que a arquitetura simples basta. A prova é que ela **já é** esta
arquitetura, e as ausências não são lacunas — são decisões registradas.

### 2.1 O que não existe, e nunca existiu

Varredura literal no repositório (fora de `history/` e `.git/`), em 325 arquivos Python e 45 TSX:

| Mecanismo de fintech | Ocorrências |
| --- | ---: |
| `split` (no sentido de divisão de pagamento) | **0** — todas as ~30 ocorrências são `str.split()` |
| `payout` | **0** |
| `recipient` (beneficiário de repasse) | **0** |
| `repasse` | **0** |
| `escrow` | **0** |
| `wallet` / `carteira` | **0** |
| `balance` / `saldo` de cliente | **0** — a única ocorrência de "saldo" é a mensagem de erro de estorno |
| Tabela de crédito, carteira ou saldo | **0** de 298 tabelas |

Não há código a remover. A arquitetura não-custodial não é uma meta desta rodada: é o estado atual,
e esta rodada a **trava**.

### 2.2 As decisões que produziram isso

| ADR | Decisão | Consequência no código |
| --- | --- | --- |
| **ADR-003** | a plataforma não custodia valores | `services/billing.py:1` declara; nenhuma tabela de saldo existe |
| **ADR-022 / ADR-178** | `success_fee` e `marketplace_take_rate` são **recusadas por arquitetura**, não adiadas | gatilho `monetization_rule_gate` (migração 0020) recusa `active = true` citando a ADR na mensagem |
| **v0.20.0 §54** | `attach_pix()` e `attach_boleto()` **removidas** | *"as duas GRAVAVAM instrução de pagamento que só um provedor brasileiro pode produzir. Sem provedor, a única forma de chamá-las seria passando valor inventado. Isso não é código incompleto: é código que, se ligado, mente."* |
| **ADR-271** (v0.21.0) | acesso gratuito ≠ autorização de cobrança | gatilho `charge_requires_authorization` (migração 0043) |

### 2.3 O que a plataforma já faz sem tocar em dinheiro

| Capacidade | Onde | Custódia? |
| --- | --- | --- |
| Máquina de 13 estados de cobrança, 27 transições validadas por gatilho | `charge_state_graph`, `economics/payments.py` | **não** |
| Trilha de cobrança append-only, escrita **só** por gatilho | `charge_events`, migração 0022 | **não** |
| Idempotência em três camadas (webhook, provedor, cliente) | `billing_events`, `platform_charges` | **não** |
| Conciliação: cobrança presa há >2 dias, evento sem assinatura verificada | `economics/payments.py:349` | **não** |
| Conciliação de extrato bancário do cliente × pagamentos | `services/payments.py:182` | **não** |
| Versionamento de preço imutável, aviso de 30 dias imposto por gatilho | `plan_price_versions`, migração 0017 | **não** |
| Trilha encadeada por hash, com verificação de cadeia | `ledger_entries`, `ledger_verify()`, migração 0002 | **não** |
| Medição de uso com teto de gasto e `hard_stop` | `usage_counters`, `spend_limits` | **não** |

**Toda a garantia operacional acima é de software.** Nenhuma delas melhora se o dinheiro passar
pela plataforma.

---

## 3. O QUE CUSTARIA DESVIAR

A regra pede a comparação. Aqui está, em termos que não dependem de opinião.

### 3.1 Custódia ou intermediação de pagamento

| Exigência que apareceria | Natureza |
| --- | --- |
| Autorização do Banco Central como instituição de pagamento, ou contrato com instituição autorizada | **regulatória** (Lei 12.865/2013) |
| Capital mínimo, governança e reporte regulatório, ou dependência de quem os tem | regulatória |
| PLD/FT: identificação, monitoramento, comunicação de operação suspeita | regulatória |
| KYC/KYB de **toda** parte que recebe | operacional contínua |
| Segregação patrimonial dos recursos de terceiros | contábil e jurídica |
| Conciliação diária obrigatória, com responsabilidade sobre a diferença | operacional contínua |
| Tratamento de chargeback com risco financeiro próprio | financeira |
| Responsabilidade solidária por fraude no fluxo | jurídica |

Nenhuma dessas é um problema de engenharia. Todas são custo fixo, permanente e difícil de reverter.

### 3.2 O que a receita ganharia

**Nada que a orquestração não entregue.** A mesma receita é obtida assim:

| Receita | Com custódia | Sem custódia (atual) |
| --- | --- | --- |
| Assinatura | cobrança via provedor | **igual** — cobrança via provedor |
| Uso medido | cobrança via provedor | **igual** |
| Serviços e implantação | fatura | **igual** |
| Enterprise e B2G | contrato | **igual** |
| Marketplace take rate | retido no fluxo | **cobrado de quem contrata, como fatura da plataforma** — ver §4 |
| Success fee | retido no fluxo | **faturado após o evento de sucesso comprovado** |

A diferença entre "retido no fluxo" e "faturado" é **risco de inadimplência**, não arquitetura. E
inadimplência se trata com crédito, cadastro e cobrança — não com uma licença de instituição de
pagamento.

### 3.3 A conclusão

> Custódia compra **conveniência de cobrança** e paga com **regulação permanente**.

Para uma plataforma cuja receita principal é SaaS institucional e B2G, essa troca é ruim. Para uma
cujo moat é workflow, dados, evidência, regra, histórico e inteligência — que é o caso — ela é
irrelevante.

**O moat do IMPACTO é o que ele sabe, não por onde o dinheiro passa.**

---

## 4. O TAKE RATE SEM CUSTÓDIA

A `PRICING_BIBLE.md` §18 pede 10% de take rate no marketplace. **No banco não há alíquota
nenhuma**: `monetization_rules.marketplace.take_rate` tem `percentage = NULL`, `active = false` e
`legal_status = refused`. Os 10% são um pedido comercial, não um dado do produto — e confundir os
dois fez a documentação da v0.22.0 afirmar que "a regra de 10% existe" até uma auditoria
independente conferir o banco. A ADR-022 recusa cobrar percentual
sobre valor que a plataforma não vê. As duas coisas são conciliáveis, e a conciliação **não** exige
custódia:

```
SERVIÇO CONTRATADO DENTRO DA PLATAFORMA
            │
            ▼
   CALCULA  → base = valor do contrato registrado na plataforma
            → fee  = percentual da PricingVersion vigente
            │
            ▼
   INSTRUI  → o contratante paga o PRESTADOR direto (fora da plataforma)
            → a plataforma emite FATURA PRÓPRIA do fee ao contratante
            │
            ▼
   CONCILIA → confronta: contrato registrado × evidência de pagamento × fatura do fee
            → divergência fica visível, não corrigida em silêncio
```

A base de cálculo passa a ser **o contrato que as partes registraram**, com aceite, valor e
evidência — não um fluxo financeiro que a plataforma precisaria ver passar.

**Isto continua desligado nesta rodada.** O que falta não é arquitetura: é a validação jurídica e
fiscal do enquadramento do fee, e a decisão comercial de cobrá-lo. A regra `marketplace.take_rate`
continua `active = false`, recusada pelo banco.

---

## 5. CAMADA OPCIONAL, NUNCA DEPENDÊNCIA

Se um dia houver decisão de usar split/BaaS, ela entra como **adapter**, atrás da mesma interface:

```
FINANCIAL ENGINE  (calcula · instrui · concilia)
        │
        ├── PaymentInstruction ──► instrução para quem paga executar   ← padrão
        │
        └── SplitAdapter ────────► provedor com split/BaaS             ← opcional
```

Requisitos para que essa camada seja opcional de verdade, e não dependência disfarçada:

1. nenhum cálculo de receita depende do adapter existir;
2. nenhuma tela quebra sem ele;
3. nenhum estado de cobrança é alcançável só por ele;
4. a conciliação funciona com evidência declarada, sem o provedor;
5. desligar o adapter não perde histórico.

**Teste que trava isso:** `test_v0220_non_custodial.py` varre o código em busca dos mecanismos da
§2.1 e reprova se qualquer um deles reaparecer sem ADR que o autorize.

---

## 6. O QUE ESTA REGRA NÃO PROÍBE

Para não virar desculpa para não fazer nada:

| Permitido | Por quê |
| --- | --- |
| Calcular quanto é devido a quem | é software |
| Emitir instrução de pagamento (valor, destino, referência, vencimento) | é documento, não transferência |
| Registrar evidência de pagamento feito fora | é registro |
| Conciliar e apontar divergência | é conferência |
| Cobrar assinatura, uso, serviço e fee via provedor | é faturamento |
| Contabilidade da própria plataforma (plano de contas, centro de custo, competência) | é a contabilidade **dela**, não de terceiros |
| Painel de controladoria com caixa, recebível e pagável **da plataforma** | é gestão própria |

A distinção que vale: **a plataforma pode saber e dizer tudo sobre dinheiro. Ela não pode guardar o
dinheiro de outra pessoa.**

---

## 7. CONSEQUÊNCIAS PARA ESTA RODADA

Os prompts desta rodada pedem `payout`, `split`, `tesouraria`, `investimentos` e `escrow`. Decisão,
item por item:

| Pedido | Decisão | Motivo |
| --- | --- | --- |
| `Payouts` como módulo | **não** | repasse exige custódia. O equivalente permitido é **instrução de pagamento** + conciliação |
| `create_split`, `create_recipient` no provedor | **não** | §5: entra como adapter opcional quando houver decisão; não nesta rodada |
| `ESCROW` | **não** | o próprio prompt (§19) já manda não chamar de escrow sem a estrutura jurídica. Estados usados: `payment_authorized`, `settlement_pending`, `payout_pending` |
| `Tesouraria` / `Investimentos` da plataforma | **sim, como registro** | é patrimônio **próprio**, não de terceiros — §6. Entra como controle e acompanhamento, sem nenhuma operação financeira |
| `Controladoria`, `Financeiro`, `Contabilidade` da plataforma | **sim** | gestão própria |
| Take rate 10% ativo | **não** | §4: a arquitetura fica pronta, a regra continua desligada por falta de validação jurídica e fiscal |
| PIX dinâmico via API | **adapter + contrato, sem gerador** | sem provedor, gerar carga "copia e cola" seria inventar. O gerador foi removido na v0.20.0 por essa razão e não volta |

---

## 8. COMO ESTA REGRA É VERIFICADA

| Verificação | Onde |
| --- | --- |
| Mecanismos de custódia não reaparecem no código | `test_v0220_non_custodial.py` |
| `marketplace.take_rate` e `success_fee` não podem ser ativadas | gatilho `monetization_rule_gate`, migração 0020 |
| Cobrança real exige autorização vigente | gatilho `charge_requires_authorization`, migração 0043 |
| `is_simulated` é derivada do provedor, não escrita à mão | gatilho `charge_simulated_flag`, migrações 0022 e 0043 |
| Nenhum módulo de impacto/reputação/match lê estado comercial | `test_v0210_pricing_catalog.py` |

Se alguma dessas verificações for removida, a regra deixou de valer — e isso tem de aparecer no
diff, não na operação.
