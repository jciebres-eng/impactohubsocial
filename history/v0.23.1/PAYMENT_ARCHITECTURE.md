# Arquitetura de pagamento da Plataforma (v0.17.0)

> **PRODUCTION PAYMENT NOT CONFIGURED.** Não há provedor, conta, chave nem identificador de preço nesta
> instalação. Nenhuma cobrança real foi processada por este código.
>
> Escrito a partir de `backend/migrations/0022_v0170_payments.sql` e
> `backend/impacto/economics/payments.py`. 29 testes em `backend/tests/test_v0170_payments.py`.

## 1. A distinção que não pode se perder

Isto é a cobrança **da Plataforma contra a organização que a usa**. Não confundir com `payment_records`,
que é o **registro de aporte declarado ao projeto** — ali o dinheiro nunca passa pela Plataforma
(ADR-022/031), e é por isso que aquela tabela já aceitava `pix` e `boleto` sem existir cobrança por PIX
nenhuma. A auditoria econômica registrou essa confusão como o achado mais fácil de cometer lendo o banco.

## 2. Como a honestidade é imposta

Não por aviso na tela. Por coluna derivada:

```sql
CREATE FUNCTION charge_simulated_flag() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_derived boolean := NEW.provider NOT IN ('stripe');
BEGIN
  IF TG_OP = 'UPDATE' AND NEW.is_simulated IS DISTINCT FROM OLD.is_simulated THEN
    RAISE EXCEPTION 'is_simulated é derivada do provedor (%): não se escreve à mão', NEW.provider;
  END IF;
  NEW.is_simulated := v_derived;  RETURN NEW;
END $$;
```

Três decisões dentro dessas seis linhas:

1. **A lista de provedores reais é explícita** (`'stripe'`), e não "todos menos sandbox". A versão
   permissiva faria qualquer provedor novo — inclusive um dublê de teste chamado de outro jeito — nascer
   marcado como real.
2. **A tentativa de mudar à mão é recusada, não sobrescrita em silêncio.** Sobrescrever resolveria o
   caso igual e deixaria quem tentou sem nenhum sinal de que a tentativa foi ignorada.
3. **`platform_revenue()` mantém o simulado em colunas próprias** e nunca o soma ao real.

### A lição que a suíte completa deu nesta fase

A primeira versão do relatório de receita classificava **fatura** como real pelo **nome** do provedor. Os
cenários da v0.11.0 gravam `provider = 'stripe'` com chave falsa — e apareceram **R$ 396,00 de receita
que não existe**. Coluna dizendo 'stripe' não é prova de chave ao vivo. Hoje, sem provedor configurado,
nenhuma fatura conta como real, e o relatório diz isso em letras.

## 3. Meios, e o estado de cada um

| Meio | Camada da Plataforma | Provedor |
|---|---|---|
| Cartão avulso | implementada e testada | **não configurado** |
| Cartão recorrente (assinatura) | implementada desde a v0.11.0 | **não configurado** |
| **Parcelamento** | implementado, modelado à parte | **não configurado** |
| PIX | instrução e prazo modelados | **não configurado** |
| Boleto | instrução e vencimento modelados | **não configurado** |

### Parcelamento não é assinatura

O pedido da rodada é explícito, e a diferença é concreta: parcelamento tem número fixo de parcelas,
vencimentos definidos, **não renova**, e a soma das parcelas tem de fechar com o total — há
`CONSTRAINT TRIGGER ... DEFERRABLE INITIALLY DEFERRED` conferindo isso no COMMIT, porque a conferência
precisa acontecer depois de todas as parcelas entrarem. Assinatura renova, não tem fim previsto e muda
de preço com aviso prévio.

Parcelamento só existe em cartão: tentar abrir parcelamento em boleto é recusado.

## 4. Máquina de estados

`charge_state_graph`, 27 arestas. Transição fora do grafo é recusada **e a resposta diz para onde a
cobrança pode ir**:

```
422 invalid_transition — {"possiveis": ["checkout_started", "cancelled", ...]}
```

A cobrança nasce em `created` mesmo por SQL direto (`charge_initial_state()`), `paid_at` e `settled_at`
são **derivados** da transição, e tentar escrevê-los levanta exceção. Devolução parcial exige valor
**entre zero e o total**; devolução integral marca o total por derivação, não por digitação.

## 5. Trilha

`charge_events` é escrita pelo gatilho `charge_record_event()` e por mais ninguém: o app **não tem
INSERT** nessa tabela, e por isso a função é `SECURITY DEFINER`. Conceder o INSERT ao app resolveria o
erro de permissão e abriria a porta para alguém inventar uma linha de trilha à mão.

Cada linha registra a **origem**: `user`, `admin`, `webhook` ou `system`. A trilha é append-only.

## 6. Cartão: o que a Plataforma guarda

Token do provedor, bandeira e **os quatro últimos dígitos**. Nada mais.

`last4` com mais de quatro caracteres é recusado por gatilho, e `holder_label` com sequência longa de
dígitos também. Parece exagero e é de propósito: é o campo em que alguém, um dia, grava o número inteiro
"só para depurar". Não existe coluna para número de cartão, CVV ou validade — há teste varrendo o
catálogo para garantir.

**A administração da Plataforma não lê o token do cliente**: a política de `payment_instruments` só
permite `org_id = app_org()`, sem exceção para privilégio.

## 7. Webhook

- Quem confirma pagamento é o **webhook assinado do provedor**. A tela nunca é fonte de verdade.
- Evento **sem assinatura conferida** é registrado com situação `rejected_signature` e **não produz
  efeito** — há CHECK no banco (`billing_events_signature_effect`) impedindo que ele chegue a
  `processed`. "Não aplicar" é a parte que ninguém lembra de testar quando a integração for ligada.
- Reentrega do mesmo evento não duplica efeito: o `UNIQUE (provider, event_id)` impede, e
  `duplicate_count` conta a reentrega para a reconciliação enxergar.
- O caminho da v0.11.0 passou a registrar `signature_verified`, que só é verdadeiro na função que
  realmente confere a assinatura.

## 8. Prazos

PIX exige `expires_at` e boleto exige `due_on` (CHECK no banco). O job `payment_deadlines`, registrado
no worker, fecha os vencidos **pela transição do grafo** (`pending → expired`), não por UPDATE solto.
Instrução de pagamento com prazo passado que continua "aguardando pagamento" é a pior mentira possível
neste módulo.

## 9. Reconciliação

`GET /v1/admin/payments/reconciliation` mostra cobrança parada e evento sem assinatura. A nota da
resposta diz o que ela não faz: não forja conciliação com provedor que não existe.

## 10. O que falta para cobrar de verdade

Nada disso é programação:

1. contratar o provedor e decidir o modelo (adquirência, subadquirência, instituição de pagamento) —
   muda quem responde por chargeback;
2. configurar chave, identificadores de preço e segredo de webhook;
3. decidir se o parcelamento terá juros (se sim, há dever de informar o CET);
4. definir a conta de recebimento do PIX (receber em conta de terceiro muda a natureza da operação);
5. contador para NFS-e: município, código de serviço e regime;
6. revisão jurídica do `payment` em `docs/legal/PAYMENT.md`.

Enquanto 1 e 2 não acontecerem, `GET /v1/payments/status` responde `configured: false`,
`methods_available_now: []` e o banner `PRODUCTION PAYMENT NOT CONFIGURED` — porque é o estado
verdadeiro.
