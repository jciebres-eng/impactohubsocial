# Doações — runbook de operação (v0.33.0, sandbox)

Linguagem simples, passo a passo. Enquanto não houver provedor real, tudo aqui acontece com dinheiro de mentira.

## 1. Testar o fluxo inteiro no demo

1. Entre no demo como organização (OSC) → **Campanha** → *Criar campanha* com tipo **Doação**, finalidade, "se a meta
   não for atingida" e política de estorno preenchidos.
2. Clique **Enviar para revisão** (os termos são aceitos nesse momento).
3. Entre como administração → **Campanhas de doação** → escreva a justificativa (≥ 10 caracteres) → **Registrar
   beneficiário como verificado** → **Aprovar**. Quem criou a campanha não consegue aprová-la.
4. Volte como organização → **Publicar**. O endereço `/campanha/<slug>` fica aberto sem login.
5. Na página pública, informe um valor e clique **Gerar Pix**: aparece um código `PIX-SANDBOX-NAO-PAGAVEL|…`. Nada é
   pagável.
6. Para "confirmar" no sandbox é preciso um evento assinado no webhook `POST /v1/webhooks/donations/sandbox` com o
   segredo `PAYMENT_WEBHOOK_SECRET` do ambiente (o teste `test_03` mostra o formato). Não há botão na tela para isso —
   é proposital: a confirmação vem sempre de fora.
7. Depois do evento: a barra de arrecadação muda, `/doacao/<id>` mostra o comprovante, e **Campanha → Arrecadação**
   mostra os totais a partir do razão.

## 2. Variáveis (Railway)

| Variável | Produção hoje | Observação |
|---|---|---|
| `DONATIONS_ENABLED` | `true` (padrão) | `false` faz `POST …/donate` responder 503 `donations_disabled`; as páginas continuam visíveis e nada é apagado |
| `CAMPAIGN_PUBLICATION_ENABLED` | `true` (padrão) | `false` faz **Publicar** responder 503 `campaign_publication_disabled` |
| `PAYMENT_WEBHOOK_SECRET` | já existe desde a v0.28.0 | sem ele, o webhook responde 404 e nenhuma doação é confirmada |
| `LIVE_PAYMENT_PROVIDER_ENABLED`, `SPLIT_ENABLED`, `RECURRING_DONATIONS_ENABLED`, `RISK_HOLD_ENABLED` | `false` | **o serviço recusa subir com `true`** — não mude sem ADR |

Nenhuma variável nova é obrigatória para o deploy da v0.33.0.

## 3. Publicar a versão

Mesmo caminho do `CLAUDE.md`: merge na `main` → demo publica sozinho → produção com "Deploy latest commit" no serviço
`impactohubsocial` (migração 0072 roda no `start_container.sh`) → `pleasing-trust` também (o worker não muda nesta
versão, mas a imagem sim). Depois: workflow `pos-deploy`.

Verificação rápida: `GET /v1/public/donation-campaigns/qualquer-coisa` deve responder 404 (rota existe, campanha não);
`POST /v1/webhooks/donations/sandbox` sem assinatura deve responder 202 (segredo configurado) ou 404 (sem segredo).

## 4. Rotinas de conciliação (administração com `finance.read`)

- `POST /v1/admin/donation-campaigns/{id}/reconcile` recebe a lista do que o provedor confirma, marca essas doações
  como `reconciled` e aponta divergências. No sandbox a lista vem dos próprios eventos assinados. É idempotente.
- `GET /v1/admin/donation-ledger/{campaign_id}` lista as partidas (cada `txn_id` soma zero).

## 5. Incidentes

| Sintoma | O que fazer |
|---|---|
| Doação `under_review` | **Risco em doações**: ler a explicação, decidir com justificativa. `Liberar` só confirma se existir evento assinado do provedor com o valor certo; `Recusar` cancela |
| Estorno/chargeback chegou | o razão lança reversão e o comprovante é anulado sozinho; avisar o beneficiário é manual (processo pendente — checklist item 12) |
| Webhook devolvendo 404 | `PAYMENT_WEBHOOK_SECRET` ausente no serviço |
| QR antigo circulando com campanha mudada | **Renovar QR** na gestão da campanha; o anterior deixa de valer (a página avisa a versão) |
| Suspeita de campanha fraudulenta | **Campanhas de doação** → filtro *Publicadas* → justificativa → **Tirar do ar (em análise)**: a página pública responde 404 e a organização não republica sozinha; **Devolver ao ar** quando apurado |

## 6. Reverter

`DONATIONS_ENABLED=false` para novas doações na hora (503). A migração 0072 só acrescenta (colunas e tabelas); reverter o código para
v0.32.0 mantém o banco compatível, porque as colunas novas têm padrão. Não apagar tabelas: o razão é trilha.
