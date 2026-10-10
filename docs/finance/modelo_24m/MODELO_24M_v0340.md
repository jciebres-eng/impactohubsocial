# Modelo econômico de 24 meses — ecossistema financeiro (v0.34.0)

> Gerado por `scripts/analysis/financial_model_24m_v0340.py`. Toda regra comercial está INATIVA; nenhuma doação real existe.
> Os números abaixo são HIPÓTESES abertas (ver aba *Premissas* da planilha), não previsão nem dado de mercado.

## Resumo por cenário (24 meses)

| Cenário | Bruto doado | Liquidado | Taxa calculada (doações) | Taxas DEVIDAS (doação + aporte + acordo) | RECEBIDO (taxas após inadimplência + créditos de IA pré-pagos) | Resultado líquido | Ponto de equilíbrio | Capital de giro |
|---|---|---|---|---|---|---|---|---|
| conservador | R$ 112.557,79 | R$ 102.295,73 | R$ 613,64 | R$ 5.512,50 | R$ 5.076,24 | R$ -21.487,44 | não atinge | R$ 21.487,44 |
| base | R$ 2.002.942,66 | R$ 1.790.262,86 | R$ 12.531,72 | R$ 46.305,00 | R$ 46.606,39 | R$ 3.869,27 | mês 7 | R$ 5.532,28 |
| otimista | R$ 30.247.741,63 | R$ 29.945.264,33 | R$ 239.561,99 | R$ 371.684,76 | R$ 385.174,43 | R$ 265.437,70 | mês 5 | R$ 3.810,94 |

## O que o modelo diz (e o que não diz)

- A taxa sobre doações comunitárias, sozinha, **não sustenta a operação** em nenhum cenário: a franquia, a isenção de recurso público e o aviso prévio
  reduzem a parcela devida, e a tarifa fixa do provedor pesa nos tíquetes baixos. Isso confirma a recomendação do pacote: não depender só das taxas sobre doações.
- O que aproxima o equilíbrio são a taxa do acordo e os aportes institucionais (regras hoje INATIVAS) e os créditos de IA — e, fora do modelo, licenças institucionais
  (contrárias à ADR-341; só com decisão do responsável).
- Tudo depende do mês de ativação (parecer + contrato): antes dele, a plataforma calcula e mostra, mas não recebe.

## Sensibilidade (cenário base, ±25 % em uma premissa por vez, recebido acumulado em 24 meses)

| Premissa | Variação | Recebido 24m | Δ |
|---|---|---|---|
| orgs_growth | -25% | R$ 45.649,44 | -2.1 % |
| orgs_growth | +25% | R$ 47.910,32 | +2.8 % |
| ticket_cents | -25% | R$ 46.606,39 | +0.0 % |
| ticket_cents | +25% | R$ 46.606,39 | +0.0 % |
| donors_per_campaign | -25% | R$ 46.606,39 | +0.0 % |
| donors_per_campaign | +25% | R$ 46.606,39 | +0.0 % |
| provider_pix_pct | -25% | R$ 46.606,39 | +0.0 % |
| provider_pix_pct | +25% | R$ 46.606,39 | +0.0 % |
| default_pct | -25% | R$ 47.532,49 | +2.0 % |
| default_pct | +25% | R$ 45.680,29 | -2.0 % |
| public_share_pct | -25% | R$ 51.170,65 | +9.8 % |
| public_share_pct | +25% | R$ 42.041,95 | -9.8 % |
| activation_pct | -25% | R$ 35.956,15 | -22.9 % |
| activation_pct | +25% | R$ 57.256,45 | +22.9 % |

## Premissas

| Chave | Rótulo | Natureza | Fonte | conservador | base | otimista |
|---|---|---|---|---|---|---|
| `donation_fee_bps` | Taxa de serviço sobre doação (bps) | FATO (regra INATIVA) | fee_rule_versions donation.platform_fee v1 | 100 | 100 | 100 |
| `institutional_fee_bps` | Taxa sobre aporte institucional (bps) | FATO (regra INATIVA) | fee_rule_versions donation.institutional_fee v1 | 350 | 350 | 350 |
| `contract_fee_bps` | Taxa de serviço do acordo (bps) | FATO (regra INATIVA) | contract.platform_service_fee | 350 | 350 | 350 |
| `allowance_cents` | Franquia liquidada por organização/12 meses (centavos) | FATO (política v1, hipótese) | monetization_policy_versions free_until_value v1 | 2000000 | 2000000 | 2000000 |
| `notice_days` | Aviso prévio (dias) | FATO (política v1) | monetization_policy_versions | 30 | 30 | 30 |
| `ai_credit_price_cents` | Preço por crédito de IA (centavos) | HIPÓTESE DO PROPRIETÁRIO | ai_credit_packs pack.100 | 10 | 10 | 10 |
| `orgs_m1` | Organizações ativas no mês 1 | PREMISSA DE MERCADO | sem histórico; editar | 20 | 40 | 80 |
| `orgs_growth` | Crescimento mensal de organizações ativas (%) | PREMISSA DE MERCADO | sem histórico | 4.0 | 8.0 | 12.0 |
| `campaigns_per_org` | Campanhas ativas por organização | PREMISSA DE MERCADO | sem histórico | 0.3 | 0.5 | 0.8 |
| `donors_per_campaign` | Doações confirmadas por campanha/mês | PREMISSA DE MERCADO | sem histórico | 12 | 25 | 50 |
| `ticket_cents` | Tíquete médio da doação (centavos) | PREMISSA DE MERCADO | sem histórico | 4000 | 6000 | 8000 |
| `refund_pct` | Estornos/chargebacks sobre o bruto (%) | PREMISSA DE MERCADO | sem histórico | 3.0 | 2.0 | 1.0 |
| `public_share_pct` | Parcela do volume com recurso público (isento, %) | PREMISSA DE MERCADO | ADR-379 | 40.0 | 30.0 | 20.0 |
| `settle_lag_m` | Meses entre confirmação e liquidação | PREMISSA DE MERCADO | depende do provedor | 1 | 1 | 0 |
| `inst_deals_m` | Aportes institucionais confirmados por mês (plataforma inteira) | PREMISSA DE MERCADO | sem histórico | 0.5 | 1.0 | 2.0 |
| `inst_ticket_cents` | Tíquete do aporte institucional (centavos) | PREMISSA DE MERCADO | sem histórico | 2000000 | 5000000 | 10000000 |
| `contracts_m` | Acordos de financiamento ativados por mês | PREMISSA DE MERCADO | sem histórico | 0.5 | 1.0 | 2.0 |
| `contract_gross_cents` | Valor médio do acordo (centavos) | PREMISSA DE MERCADO | sem histórico | 5000000 | 10000000 | 20000000 |
| `ai_ops_per_org` | Operações de IA pagas por organização/mês | PREMISSA DE MERCADO | sem histórico | 5 | 15 | 30 |
| `provider_pix_pct` | Tarifa do provedor sobre Pix (%) | PREMISSA DE MERCADO | tabela comercial, não lida (DONATIONS_PROVIDER_MATRIX) | 1.2 | 1.0 | 0.8 |
| `provider_fixed_cents` | Tarifa fixa do provedor por transação (centavos) | PREMISSA DE MERCADO | idem | 50 | 30 | 0 |
| `default_pct` | Inadimplência sobre as obrigações devidas (%) | PREMISSA DE MERCADO | sem histórico | 15.0 | 8.0 | 4.0 |
| `tax_pct` | Tributos sobre receita (%) — não é parecer | HIPÓTESE DO PROPRIETÁRIO | config/ai_economics.json | 8.65 | 8.65 | 8.65 |
| `support_cents_org` | Suporte por organização ativa/mês (centavos) | HIPÓTESE DO PROPRIETÁRIO | config/ai_economics.json (escala) | 1500 | 1000 | 800 |
| `infra_cents_m` | Infraestrutura fixa/mês (centavos) | FATO APROXIMADO | Railway Pro + Supabase Pro + R2 + Brevo (faixas públicas; não é fatura) | 60000 | 50000 | 45000 |
| `rule_activation_m` | Mês em que as regras são ATIVADAS (parecer + contrato) | PREMISSA DE DECISÃO | sem parecer hoje | 9 | 6 | 4 |
| `activation_pct` | Organizações acima da franquia que aceitam contrato (%) | PREMISSA DE MERCADO | sem histórico | 50.0 | 70.0 | 85.0 |

Gráficos: `g1_resultado_acumulado.png`, `g2_calculada_devida_recebida.png`. Planilha: `IMPACTO_MODELO_24M_v0340.xlsx` (fórmulas abertas por linha).
