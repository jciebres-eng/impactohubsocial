# Gratuito até gerar valor — política, gatilhos e exceções (v0.34.0, ADR-377 a ADR-381)

> O que está aqui é o que o código faz hoje (`impacto/services/remuneration.py`, migração 0073, `test_v0340_financial_ecosystem`).
> Os NÚMEROS da política são HIPÓTESES registradas em `monetization_policy_versions` (versão 1, `legal_status = hypothesis`);
> mudam por versão nova, nunca por edição. Nenhuma regra comercial está ativa; nada é devido a ninguém nesta versão.

## 1. A regra em uma frase

A plataforma **calcula e mostra** a sua remuneração em cada operação; ela só fica **devida** quando um gatilho auditável fecha; só é
**faturada à parte** (nunca descontada do dinheiro de terceiros); só é **receita** quando recebida e liquidada; e **nada do que a
organização deve condiciona a prestação de contas, as exportações, as evidências ou a página pública**.

## 2. A cadeia de estados de uma obrigação

| Estado | Significa | Quem muda | Receita? |
|---|---|---|---|
| `calculated` | taxa calculada pela versão de regra congelada na operação | sistema (confirmação da doação) | não |
| `exempt` | isenta: recurso público sem autorização; valor zero; dispensa de política | sistema / `finance.approve` | não |
| `due` | devida: as cinco condições do §3 fecharam | rotina `evaluate` (`finance.write`) | não |
| `invoiced` | faturada numa cobrança própria da plataforma (`platform_charges`, provedor manual/sandbox) | `finance.write` | não |
| `charged` | cobrança enviada ao pagador | `finance.write` | não |
| `received` | pagamento recebido com referência (parcial fica registrado sem mudar o estado) | `finance.write` | ainda não |
| `settled` | conciliado com extrato — segregado: `finance.approve` | `finance.approve` | **sim** |
| `reversed` | base estornada antes do recebimento | sistema (webhook de estorno) | não |
| `overdue` | vencida após carência — **nenhum bloqueio** | rotina `mark-overdue` | não |
| `disputed` | contestada pela organização; decisão com justificativa | organização / `finance.approve` | não |
| `waived` | dispensada por decisão registrada | `finance.approve` | não |

Valor, base e versão da regra são congelados na criação (gatilho do banco recusa alteração); correção é obrigação nova. Toda
transição vai para `remuneration_obligation_events` (só inserção).

## 3. O gatilho auditável (as cinco condições)

`evaluate(org)` só muda `calculated → due` quando TODAS valem; senão registra o motivo (`rule_inactive`, `public_funding_exempt`,
`within_allowance`, `notice_pending`, `notice_period_running`, `fee_share_cap`):

1. **Regra ativa** no catálogo — e o portão do banco só ativa com carta legal verde (base, fonte, data, certeza alta, sem advogado
   pendente, sem pergunta aberta) e `legal_status = validated`. Hoje: nenhuma.
2. **Origem do recurso** não é pública/mista — ou tem instrumento identificado e autorização registrada (§5).
3. **Franquia**: o valor **LIQUIDADO** (não confirmado) ao favor da organização nos últimos 12 meses passou de
   `allowance_settled_cents_12m` (v1: R$ 20.000,00 — hipótese).
4. **Aviso prévio** `charging_starts` enviado há pelo menos `notice_days` (v1: 30) — o texto enviado fica guardado.
5. **Teto**: o total devido no período não passa de `max_fee_share_of_settled_bps` do liquidado (v1: 5 %).

Depois disso: fatura só acima de `min_invoice_cents` (v1: R$ 20,00; abaixo acumula); vencimento em `due_days_after_invoice`
(30); carência antes de "vencida" `overdue_grace_days` (15).

## 4. Comunicação prévia (registrada)

Tipos de aviso: `free_until_value_intro` (ao entrar), `allowance_approaching`, `charging_starts` (o único que conta para o
gatilho), `invoice_issued`, `overdue`, `dispute_received`, `waived`. Cada aviso guarda o texto, a versão da política, o canal
e a ciência da organização (`ack`). Os textos padrão estão em `remuneration.NOTICE_TEXTS` e são RASCUNHO para revisão jurídica.

## 5. Recursos públicos (ADR-379 — correção do pacote)

Não se presume que todo repasse público veda pagar licença de software, nem que o permite. **Por padrão, a obrigação nasce
`exempt`** quando a campanha/doação declara origem pública ou mista. Ela só volta a `calculated` (e pode virar devida) quando
alguém com `finance.approve` registra o **instrumento** (termo de fomento/colaboração, convênio, edital) e a **justificativa**
de elegibilidade da despesa (`authorize-public`). O que decide é o instrumento, o regulamento do ente e a natureza da despesa —
análise caso a caso, fora do código.

## 6. O que a política NUNCA faz (ADR-381)

`never_blocks`: prestação de contas, exportações, página pública, evidências, relatórios. O teste
`test_11_no_accountability_route_consults_commercial_state` varre as rotas de doações, prestação de contas e relatórios e
falha se alguma consultar o estado comercial. O módulo de remuneração não expõe nenhuma função de bloqueio.

## 7. Como a cobrança começaria (passos fora do código)

1. Parecer jurídico/contábil → carta legal VERDE nova (as cartas são append-only) → `legal_status = validated` → `active = true`
   (o portão do banco confere tudo isso; `success_fee` nunca passa — fundo e reserva são do beneficiário).
2. Contrato/termos aceitos pela organização com a política e a tarifa.
3. Aviso `charging_starts` registrado; 30 dias.
4. `evaluate` por organização (rotina ou à mão) → `due` → fatura própria → recebimento com referência → liquidação segregada.
5. Recurso público: só com instrumento e autorização registrados.

## 8. Reserva institucional (ADR-380 — correção do pacote)

A "reserva de 1,5 %" e o "fundo de 4 %" são **destinação contábil/contratual da organização beneficiária**, calculados e exibidos
para transparência. A plataforma **não retém, não guarda, não investe e não remunera** esses valores. No catálogo ambas estão no
motor `success_fee`, que o banco recusa ativar por desenho (ADR-022): não existe caminho para virarem receita da plataforma.
