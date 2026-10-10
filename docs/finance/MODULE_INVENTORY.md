# Inventário de módulos — existentes, alterados e novos (v0.34.0)

| Módulo / arquivo | Situação | O que mudou |
|---|---|---|
| `backend/migrations/0073_v0340_financial_ecosystem.sql` | **novo** | obrigações, política, avisos, recursos externos, compromissos, exceções/execuções de conciliação; `donations` (+`settled_at`, `refunded_cents`, `donor_org_id`, `funding_source`, estado `partially_refunded`); `campaigns` (+`funding_source`, `public_instrument_ref`); 2 regras + cartas; 4 categorias de auditoria; GRANTs |
| `backend/impacto/services/remuneration.py` | **novo** | política, registro, gatilho (`evaluate`), avisos, fatura (`platform_charges`), cobrada/recebida/liquidada, vencidas, disputa/decisão/dispensa, autorização de recurso público, visões |
| `backend/impacto/services/reconciliation.py` | **novo** | snapshot do sandbox, execução por campanha, 9 tipos de exceção, assumir/resolver/histórico |
| `backend/impacto/services/donations.py` | alterado | liquidação, estorno parcial (e total após parcial), obrigações na confirmação/reversão, totais por estado, recursos externos, compromissos, painel do financiador, `donor_org_id`/`funding_source` |
| `backend/impacto/api/donation_routes.py` | alterado | +26 operações (ver `DONATIONS_API.md`); webhook em duas fases (E6) |
| `backend/impacto/api/trust_schemas.py` | alterado | esquemas novos; `CampaignIn` (+origem do recurso); `DonationStartIn` (+`as_organization`, `funding_source`) |
| `backend/impacto/api/platform_routes.py` | alterado | criação de campanha grava origem do recurso; recurso público exige instrumento |
| `backend/tests/test_v0340_financial_ecosystem.py` | **novo** | 13 cenários |
| `backend/tests/test_v0340_open_scenarios.py` | **novo (E6)** | 8 testes: cartão, falha do provedor, evento falho e reprocessado, liquidação parcial/falha, contribuição com split simulado e sem split, recorrência, reembolso e fatura protegida |
| `backend/impacto/jobs.py` | alterado (E6) | rotina `financial_ops`: reprocessa eventos, marca vencidas, concilia campanhas recentes, cria tentativas de recorrência (se ligada) |
| `backend/impacto/economics/payments.py` | alterado (E6) | organização não move fatura de remuneração da plataforma; devolução por sistema/administração reverte a obrigação |
| `config/data_retention.json` | alterado (E6) | `remuneration_obligations.org_id` (retida) e `reconciliation_exceptions.org_id` (anonimizável) declaradas |
| `backend/tests/test_v0340_release_docs.py` | **novo** | documentos, política e contagens da versão |
| `web/src/pages/donations.tsx` | alterado | remuneração (org), contribuições (financiador), obrigações e conciliação (admin), recursos externos/compromissos/estados na gestão e na página pública |
| `web/src/app.tsx`, `web/src/ui/icon.tsx` | alterado | rotas `/remuneracao`, `/contribuicoes`, `/admin/remuneracao`, `/admin/conciliacao` |
| `scripts/analysis/financial_model_24m_v0340.py` | **novo** | modelo de 24 meses, 3 cenários, sensibilidade |
| `docs/finance/*` | **novo** | política, razão/estados, matriz de monetização, riscos, jurídico/fiscal, API, cobertura de testes, diagramas, modelo, checklist |
| `MONETIZATION.md`, `DECISIONS.md`, `CHANGELOG.md`, `RELEASE_NOTES.md`, `README.md` | alterado | regras 13 → 15; ADR-377..383 |
| Inalterados (reaproveitados) | — | `platform_charges`/`invoices` (0022/0001), `monetization_rules` + cartas (0020/0021), `agreement_allocations`/`allocation_payouts`/`payout_transfers` (0064/0066), `free_periods`, `billing_notices`, `ai_credit_*`, razão de doações (0072) |
