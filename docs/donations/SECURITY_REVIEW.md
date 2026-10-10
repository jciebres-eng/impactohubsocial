# Doações — revisão de segurança e modelo de ameaças (v0.33.0)

⚠️ Nada aqui afirma que o sistema é "impossível de invadir". Cada linha diz o que foi feito, como foi provado e o que
continua em aberto. Semáforo: 🟢 coberto por teste · 🟡 coberto por desenho, sem teste automatizado · 🔴 em aberto.

## Modelo de ameaças

| # | Ameaça | Controle | Prova | Estado |
|---|---|---|---|---|
| 1 | QR trocado por um que leva a outra chave Pix | o QR nunca contém chave Pix: aponta para `/campanha/{slug}?v={n}`; `rotate-qr` invalida o anterior; cabeçalho `X-Impacto-Qr-Target` | `test_02` | 🟢 |
| 2 | Campanha falsa publicada por quem a criou | `campaign_state_guard`: revisor ≠ criador, termos aceitos, `beneficiary_verified()`; `PATCH status=published` → 409 | `test_01` | 🟢 |
| 3 | Webhook forjado confirma doação sem pagamento | HMAC-SHA256 no `x-impacto-signature`; sem segredo a rota responde 404; assinatura inválida → 202 sem efeito | `test_03` | 🟢 |
| 4 | Reentrega do mesmo evento dobra o razão | `UNIQUE (provider, event_id)`; segunda entrega devolve `duplicate` | `test_03` | 🟢 |
| 5 | Evento de valor parcial confirma o total | valor do evento comparado ao esperado; divergência → `under_review` + caso de risco; `allow` só com evento assinado existente | `test_04` | 🟢 |
| 6 | Estorno repetido reverte duas vezes | reversão já lançada → `already_reversed` antes de qualquer outra regra | `test_06` | 🟢 |
| 7 | Alteração silenciosa do razão | só INSERT (`forbid_mutation`), partidas dobradas com restrição diferida de soma zero | `test_03`, `test_07` | 🟢 |
| 8 | Saldo custodiado por engano (fintech acidental) | nenhuma coluna de saldo; totais derivam do razão e são rotulados "estimado — não é dinheiro guardado"; `is_simulated` não gravável | `test_10` | 🟢 |
| 9 | Taxa cobrada sem base legal | regras INATIVAS com `review_required`; `platform_fee_due = 0`; versão congelada por doação | `test_10` | 🟢 |
| 10 | Vazamento de dado do doador | e-mail cifrado em repouso; doador anônimo nunca aparece em público nem para a organização; bruto do webhook redigido (CPF, e-mail, telefone, IP, cartão, nome) | `test_03`, `test_05` | 🟢 |
| 11 | Organização lê doações de outra | RLS por `beneficiary_org_id`; rotas de gestão exigem dono da campanha (`require_campaign_owner`) → 404 | `test_05` | 🟢 |
| 12 | Flag virada liga dinheiro real sem adaptador | `validate()` recusa `LIVE_PAYMENT_PROVIDER_ENABLED`, `SPLIT_ENABLED`, `RECURRING_DONATIONS_ENABLED`, `RISK_HOLD_ENABLED` = true | `test_09` | 🟢 |
| 13 | Abuso da rota pública de doação (spam de cobranças) | `rate=("donate_ip", 30, 3600)` por IP; idempotência por chave; regra `burst_attempts` abre caso | rate limit coberto pelo arcabouço (`RATE_LIMIT_MULTIPLIER`), regra em `test_04`/`_risk_screen` | 🟡 |
| 14 | Enumeração de doações pela URL pública `/doacao/{id}` | id UUID v4; página mostra valor e estado, nunca e-mail/nome do doador anônimo | `test_05` | 🟡 |
| 15 | Replay de webhook antigo após troca de segredo | assinatura é só do corpo (sem carimbo de tempo) no sandbox; provedores reais têm `ts` (Mercado Pago) ou token fixo (Asaas) — o adaptador real deve validar janela temporal | — | 🔴 (depende do adaptador real) |
| 16 | Lavagem via muitas doações pequenas | regras `burst_attempts` e `new_campaign_large_inflow` abrem caso; nada bloqueia dinheiro (não há custódia) — a obrigação de PLD é do provedor | `_risk_screen`, decisão em `test_04` | 🟡 |
| 17 | Comprovante adulterado | número sequencial + SHA-256 do conteúdo gravado; anulado em estorno | `test_03`, `test_06` | 🟢 |
| 18 | Campanha fraudulenta descoberta depois de publicada | administração tira do ar com justificativa (`under_review` → página 404); a organização não republica sozinha | `test_11` | 🟢 |
| 19 | Beneficiário "verificado" sem lastro | `org_kyb_verifications` registra quem verificou, com qual nota e validade de 12 meses; quem e com que documentos → pendente de provedor/parecer | `test_01` | 🟡 |

## Verificações de código

- `ruff check impacto tests`: sem achados.
- `secrets_scan.py` no pacote final: ver `FINAL_EXECUTION_REPORT.md` §22.
- Sem dependência nova (o QR usa `impacto/trust/qr.py` já existente; HMAC é `hmac`/`hashlib` da biblioteca padrão).

## Em aberto (precisa de pessoa ou contrato)

1. Validação temporal da assinatura no adaptador real (#15).
2. Teste de carga da rota pública de doação no demo com o limite por IP (#13).
3. Procedimento de resposta a chargeback com o provedor (quem avisa quem, prazo) — ver `RUNBOOK.md` §5.
