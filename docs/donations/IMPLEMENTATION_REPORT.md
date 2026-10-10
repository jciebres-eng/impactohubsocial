# Doações — relatório de implementação (v0.33.0)

Tudo abaixo está no repositório e coberto por `backend/tests/test_v0330_donations.py` (11 testes) e
`test_v0330_release_docs.py`. O que não está implementado está dito como tal.

## Decisões que moldam o código

ADR-372 (sem custódia, sandbox único), ADR-373 (taxas inativas, congeladas por doação), ADR-374 (quatro olhos + QR
canônico), ADR-375 (webhook assinado e idempotente), ADR-376 (PLD proporcional sem retenção). Texto em `DECISIONS.md`.

## Banco — migração `0072_v0330_donations.sql`

- `campaigns` ganha: `kind`, `target_cents`, `currency`, `starts_on/ends_on`, `beneficiary_org_id` (NOT NULL, = `org_id`
  por padrão), `purpose`, `contingency_policy`, `refund_policy`, `policy_version`, `accepted_terms_at`,
  `review_note/reviewed_by/reviewed_at`, `qr_version`, `min_donation_cents`, `allow_recurring`; `project_id` opcional;
  `status` com 12 estados (draft → pending_review → approved → published → paused/target_reached/ended/closed;
  under_review/rejected/cancelled/refunding).
- 11 tabelas novas: `org_kyb_verifications`, `fee_rule_versions`, `provider_fee_schedules`, `donations`,
  `recurring_donation_agreements`, `payment_provider_events` (UNIQUE `provider, event_id`), `donation_ledger_entries`,
  `donation_risk_cases`, `donation_receipts`, `campaign_updates`, `campaign_expenses`.
- 5 funções/gatilhos: `beneficiary_verified(org)`, `campaign_state_guard` (transições permitidas; publicar exige revisor ≠
  criador, termos aceitos e beneficiário verificado), `donation_simulated_flag` (`is_simulated` derivado do nome do
  provedor — não é gravável pela aplicação), `donation_state_guard`, `donation_ledger_balanced` (restrição diferida:
  cada `txn_id` soma zero entre D e C).
- Razão: só INSERT (`forbid_mutation`); estorno é lançamento novo com `reversal_of`.
- Sem coluna de saldo em lugar algum (teste `test_10`).
- Regras `donation.platform_fee` (100 bps) e `donation.beneficiary_fund` (400 bps) inseridas INATIVAS com
  `review_required` e cartões jurídicos amarelos; `fee_rule_versions` guarda a versão aplicada a cada doação.
- GRANTs mínimos ao `impacto_app` por tabela (§13 da migração).

## Serviço — `impacto/services/donations.py`

| Função | O que faz |
|---|---|
| `compute_breakdown` / `platform_fee_due` | calcula taxa e fundo em pontos-base com a versão congelada; **devido = R$ 0,00** enquanto a regra estiver inativa |
| `SandboxProvider` | único `PaymentProvider`; gera cobrança `PIX-SANDBOX-NAO-PAGAVEL|…`, assina eventos com HMAC-SHA256 (`x-impacto-signature`) |
| `start_donation` | idempotente por `idempotency_key`; e-mail cifrado; triagem de risco; estado `awaiting_payment` |
| `record_provider_event` / `apply_provider_event` | guarda o bruto redigido (CPF, e-mail, telefone, IP, cartão, nome removidos) uma única vez; aplica confirmação (com conferência de valor), estorno/chargeback (uma vez só: `already_reversed`), expiração |
| `_post_confirmation` / `_post_reversal` | partidas dobradas: C `donor_payment` = D `beneficiary_receivable` + `provider_fee` + `platform_fee_accrued` + `beneficiary_fund`; reversão espelha com `reversal_of` |
| `campaign_totals` / `reconcile_campaign` | totais a partir do razão, rotulados "saldo contábil estimado — não é dinheiro guardado"; conciliação recalcula do razão |
| `_risk_screen` / `open_risk_case` / `decide_risk_case` | regras `donation-risk-2026-10.1` (ver `config/donation_risk_rules.json`); decisões allow/request_information/reject/report_to_provider com justificativa; `payout_hold` recusado |
| `issue_receipt` / `receipt_view` | comprovante `IMP-DOA-AAAA-NNNNNN` com SHA-256 do conteúdo; anulado em estorno; texto diz que NÃO é recibo dedutível |
| `submit_for_review` / `review` / `suspend` / `publish` / `rotate_qr` | fluxo quatro olhos; termos `campaign-terms-2026-10-draft`; suspensão administrativa com justificativa; QR versionado |
| `accountability` | totais, gastos declarados/validados, atualizações, doações (anônimas sem nome), casos de risco abertos |

## API — `impacto/api/donation_routes.py` (22 operações)

Públicas: `GET /v1/public/donation-campaigns/{slug}`, `GET …/qr.svg`, `POST …/donate` (30/h por IP),
`GET /v1/public/donations/{id}`, `GET …/receipt`. Webhook: `POST /v1/webhooks/donations/{provider}` (404 sem segredo;
202 em assinatura inválida; 200 aplicado/duplicado). Organização: `submit`, `publish`, `rotate-qr`, `accountability`,
`expenses`, `updates`. Pessoa: `GET /v1/me/donations`, `POST /v1/me/recurring-donations/{id}/cancel`. Administração
(`compliance.write`): lista/revisão de campanhas, suspensão/retorno ao ar com justificativa, verificação de beneficiário, casos de risco e decisão;
(`finance.read`): conciliação e razão. O `PATCH /v1/campaigns/{id}` com `status=published` responde 409
`campaign_review_required`.

## Interface — `web/src/pages/donations.tsx`

`/campanha/:slug` (pública: barra de arrecadação só com confirmados, formulário Pix com "cobrir custos" desmarcado,
preço total e aviso de hipótese antes de pagar, QR, regras, atualizações, gastos, "o que esta campanha NÃO é"),
`/doacao/:id` (situação e comprovante), `/minhas-doacoes`, gestão em `/campanha-gestao` (enviar à revisão, publicar,
renovar QR, declarar gasto, publicar atualização), `/admin/doacoes` (revisão com justificativa, verificação do
beneficiário) e `/admin/doacoes/risco`.

## Flags (`impacto/config.py`, `.env.example`)

`DONATIONS_ENABLED=true`, `CAMPAIGN_PUBLICATION_ENABLED=true`; `LIVE_PAYMENT_PROVIDER_ENABLED`, `SPLIT_ENABLED`,
`RECURRING_DONATIONS_ENABLED`, `RISK_HOLD_ENABLED` = false e **recusados** em `validate()` se `true` (teste `test_09`).

## O que NÃO foi implementado (e por quê)

| Item | Motivo |
|---|---|
| Provedor real (Asaas, Mercado Pago ou outro) | sem contrato, credenciais e parecer; `DONATIONS_PROVIDER_MATRIX.md` traz o levantamento |
| Split, recorrência cobrada, retenção de repasse | dependem do provedor; travas recusam ligar |
| Cobrança de taxa de serviço | regra inativa até parecer; `platform_fee_due = 0` |
| Recibo fiscal / dedutibilidade | comprovante explícito de que não é; parecer contábil pendente |
| Validação documental de gastos (`evidence_status = validated`) | o campo existe; a rotina de validação de documento fica para quando houver revisor definido |
| Notificação por e-mail ao doador | o e-mail é cifrado e nunca sai da base nesta versão; envio entra com o provedor real |
