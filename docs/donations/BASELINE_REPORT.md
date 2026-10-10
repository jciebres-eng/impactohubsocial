# Doações — relatório de base (o que existia antes da v0.33.0)

Inspeção feita no commit `24793bb` (v0.32.0, ramo `correcoes-auditoria`) antes de escrever qualquer linha do módulo.
Objetivo: reaproveitar o que já existe e não criar uma segunda versão de nada.

## O que já existia e foi reaproveitado

| Peça | Onde | Como entrou no módulo |
|---|---|---|
| `campaigns` (campanha de divulgação de cotas: slug, título, resumo, história, `show_backers`, `published_at`) | migração 0012 (camada de confiança) e `platform_routes.py` | virou a mesma tabela com `kind = 'quota' \| 'donation'`; colunas novas em 0072; `project_id` passou a opcional |
| `monetization_rules` + `monetization_legal_cards` (catálogo de regras com `active`, `review_required`, cartões jurídicos) | migração 0020 | as duas regras de doação entraram no catálogo, inativas |
| `payment_records` (migração 0004) e webhook `/v1/webhooks/payments/{provider}` (compra de créditos de IA, v0.28.0) | `ai_center` | o padrão de assinatura HMAC e o `payment_webhook_secret` foram seguidos; o webhook de doações é rota própria para não misturar créditos com doações |
| `risk_signals` (migração 0004) / tela "Sinais de risco" | `ops` | padrão de caso aberto → decisão com justificativa reproduzido em `donation_risk_cases` |
| `impacto.trust.qr.svg` (QR SVG sem dependência externa) | `impacto/trust/qr.py` | reutilizado para o QR da campanha |
| cifra de campo (`FIELD_ENCRYPTION_KEY`) | `impacto/security/crypto.py` | e-mail do doador guardado cifrado |
| RLS, `app_priv()`, `forbid_mutation`, `touch_updated_at`, GRANTs explícitos ao `impacto_app` | convenções do banco | aplicados em todas as 11 tabelas novas |
| `permission="compliance.write"` e `"finance.read"` | `staff_permissions` | revisão de campanhas e casos de risco usam a primeira; razão e conciliação a segunda |

## O que NÃO existia (confirmado por busca no código)

- nenhuma tabela de doação, razão contábil de doações, comprovante de doação ou verificação de beneficiário;
- nenhum provedor de pagamento real integrado (o `payment_records` da v0.28.0 também só tem sandbox);
- nenhuma coluna de saldo em lugar algum (`grep -ri balance backend/migrations` → só comentários proibindo);
- nenhuma regra de taxa sobre doações no catálogo;
- nenhuma tela pública de doação (a `/campanha/:slug` mostrava cotas).

## Restrições herdadas que o módulo respeita

- ADR-284 (não há fintech dentro do IMPACTO) e `NON_CUSTODIAL_ARCHITECTURE.md`.
- Migrações só para frente, numeradas (`0072`), testadas em banco novo.
- Produção limpa (v0.32.0): nada do módulo semeia dados; o demo é o lugar de testar.
- Segredos só em variáveis (Railway/GitHub); `.env.example` documenta os nomes.

## Pacote recebido (`IMPACTO_TRUST_v0.31.0_MONETIZACAO_DOACOES_MASTER_FULL.zip`)

Base byte-idêntica à v0.31.0 + 13 documentos de instrução. Os pontos do pacote que **não** viraram código, com o motivo:

| Pedido do pacote | Situação | Motivo |
|---|---|---|
| taxa 3,5 % / 1,5 % institucional; 1 % / ≤ 4 % microdoações | catálogo, INATIVO | sem parecer e contrato é hipótese; cobrar seria inventar preço |
| “carteira visual” | totais a partir do razão, rotulados “saldo contábil estimado — não é dinheiro guardado” | carteira com saldo próprio seria custódia |
| split automático | trava `split_enabled = false` | depende do provedor e do enquadramento |
| recorrência | tabela e cancelamento pelo doador; cobrança recorrente desligada | exige instrumento do provedor e consentimento |
| KYC/PLD | KYB do beneficiário registrado pela plataforma + 3 regras de triagem | a obrigação regulatória de PLD é do provedor; a plataforma coopera e documenta |
| provedor real | matriz com 2 provedores (Asaas, Mercado Pago) a partir das docs oficiais | contrato, sandbox oficial e parecer ainda não existem |
