# Financiamento por marcos — cada estado pedido, mapeado ao que o código faz (v0.30.0)

O superprompt 04 pede estados e responsabilidades nomeados. A plataforma já os tem, distribuídos em objetos que **separam decisão
interna, instrução ao pagador e confirmação por quem recebe** (ADR-284, 337, 338). Esta tabela diz, para cada estado pedido, onde ele
vive, quem age, que prova existe — ou "não existe", quando não existe. Conferido por `test_v0300_release_docs` (toda tabela/coluna
citada existe no esquema).

| Estado pedido | Objeto · coluna/valor | Quem age | Como é garantido | Teste que prova |
|---|---|---|---|---|
| Oportunidade publicada | `calls.status = 'published'` | financiador / governo | só quem é dono publica; visibilidade por `kb`/RLS | `test_api_workflow`, jornada "Financiador" |
| Candidatura | `applications.status` ∈ interest → draft → submitted → screening → due_diligence → approved/rejected/withdrawn | OSC (até submitted), financiador (depois) | máquina de estados no banco (`trg_application_status_graph`); `not_your_turn` para quem não é a vez | `test_api_workflow` (nascer aprovada é recusado) |
| Diligência | `applications.status = 'due_diligence'`; `conflict_declarations` obrigatória antes de aprovar | financiador | `conflict_declaration_required` / `conflict_of_interest` (409) | `test_api_workflow` |
| Decisão documentada | `applications.status = 'approved'` + nota; auditoria `application.transition` | financiador | append-only de transições; hash encadeado | `test_v0230_audit_engine` |
| Acordo | `signed_agreements.status` draft → awaiting_signatures → active (cláusulas congeladas; versão nova = `superseded`) | partes | `agreement_versions` imutável; assinatura exige termos aceitos (ADR-336) | `test_v0260_contract_rules` |
| Aporte confirmado pelo parceiro | **não existe parceiro financeiro.** O que existe: `commitments.status` pledged → disbursed (quem paga informa) → confirmed (**só a OSC confirma**) | financiador informa, OSC confirma | 403 se a OSC tenta informar desembolso; 403 se o financiador tenta confirmar | `test_api_workflow` |
| Marco em execução | `milestones.status` planned → open → funded → in_progress → evidence_submitted → accepted/rejected; `signed_agreement_milestones.status` planned → in_progress → delivered → accepted/rejected | OSC executa; quem financia aceita | `agreement_milestone_guard`: quem reporta não aceita (quatro olhos) | `test_v0260_contract_rules` |
| Evidência submetida / revisão / aprovação / rejeição | `evidences.status` submitted → needs_info/accepted/rejected → contested → under_review → accepted/rejected; superseded (v0.30.0) | OSC envia e contesta; financiador/governo decide | máquina de estados + motivo obrigatório + histórico append-only (0070) | `test_v0300_evidence_object` |
| Autorização de liberação | `allocation_payouts.state = 'instruction_created'` (instrução: quem paga → quem recebe → chave PIX do contrato); `agreement_obligations.kind = 'pay'` | gerada na ativação do acordo e na quitação de entrega | a plataforma **instrui**; não autoriza débito em conta de ninguém | `test_v0270_economy` |
| Liquidação confirmada | `payout_transfers.status` registered (quem paga, com referência) → confirmed (**quem recebe**) → `allocation_payouts.state = 'confirmed'`/`'reconciled'`; ledger `operation_settled` | pagador registra; recebedor confirma | idempotência por referência (mesma referência = mesma transferência); nunca há saldo | `test_v0270_economy`, jornada "Caminho dourado" |
| Prestação de contas | `impact_updates` (submitted → accepted/changes_requested → published), `expenses` com comprovante, `report_submitted` no ledger | OSC envia; financiador analisa | separação de funções (`guard_self_review`) | `test_api_workflow`, `test_v0230_claims` |
| Timeout | `agreement_obligations.status = 'overdue'` (varredura `deadline_sweep`), `obligation_overdue` no ledger | sistema | job idempotente | `test_v0260_contract_rules` |
| Retry idempotente | `economic_events.idempotency_key` (UNIQUE; `ON CONFLICT DO NOTHING`); transferência por referência | sistema | chave repetida não gera segundo evento | `test_v0270_economy` |
| Reconciliação | `allocation_payouts.state = 'reconciled'`; `payout_reconciled` no ledger | administração (`billing.write`) | conciliação manual auditada; não há extrato automático (sem provedor) | `test_v0270_economy` |
| Disputa | `allocation_payouts.state = 'disputed'`; `payment_disputed`; contestação de evidência (0070); `reputation_disputes` | partes | registrada com motivo; revisão humana | `test_v0300_evidence_object`, `test_v0230_moderation` |
| Pausa de emergência | `kill_switch_events` por capacidade (ex.: cobranças, IA) — `killswitch.py` | administração (MFA, motivo) | API recusa a capacidade desligada; append-only | `test_v0230_security_gate` |
| Escrow / conta gráfica / retenção automática | **não existe e não existirá dentro do IMPACTO** (ADR-284/337) | — | teste de estrutura recusa tabela de saldo de terceiros | `test_the_platform_has_no_table_that_holds_third_party_money` |

**Leitura:** aprovar uma evidência muda `evidences.status` e, se for a evidência de um marco, `milestones.status`; **não** cria instrução
de pagamento nem confirma transferência (provado em `test_v0300_evidence_object.test_another_org_never_sees_the_evidence_and_accepting_moves_no_money`).
A instrução nasce do contrato (obrigação `pay`), a liquidação só existe quando quem recebe confirma.
