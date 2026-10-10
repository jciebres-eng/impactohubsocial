# Checklist de publicação — v0.35.0 (correções de segurança)

Ordem: **demo primeiro, produção depois** (CLAUDE.md). Nenhum passo aqui pede senha no chat: tudo é colado direto no
Railway, no GitHub ou no Cloudflare por você. Onde diz "conferir", é olhar — não é mudar.

## 0. Antes de tudo (P0, independentes da versão)

- [ ] Token do R2 do backup exposto ("C2") trocado — [RB-01](runbooks/RB-01-vazamento-de-segredo.md).
- [ ] Repositório privado (Settings → General → Danger Zone).

## 1. Variáveis no Railway (serviço `impactohubsocial`; o `pleasing-trust` herda por referência)

| Variável | Valor | Por quê | Se errar |
|---|---|---|---|
| `TRUST_PROXY_HEADERS` | `true` | o IP do cliente passa a vir da ponta confiável do X-Forwarded-For (limites por IP deixam de ser contornáveis por cabeçalho forjado) | sem ela, funciona como antes (e o log de início avisa) |
| `TRUSTED_PROXY_HOPS` | `1` para começar | quantos proxies confiáveis acrescentam ao cabeçalho (Railway; Cloudflare na frente pode somar mais um) | IP errado na trilha e nos limites — **conferir no demo** (passo 3) |
| `CLIENT_IP_HEADER` | deixe **vazio** | só use (`cf-connecting-ip`) se TODO acesso passar pelo Cloudflare e o domínio `*.up.railway.app` não for alcançável direto — isso não foi verificado | cabeçalho forjável por quem acessa o Railway direto |
| `FORWARDED_ALLOW_IPS` | deixe **vazio** | com `TRUST_PROXY_HEADERS=true` o padrão passa a ser `127.0.0.1` (o uvicorn não reescreve o IP) | — |
| `REQUIRE_MFA_FOR_ADMINS` | **não** pode ser `false` | a produção recusa subir com ele desligado | o serviço não sobe (o Railway mantém o deploy anterior) |
| `PAYMENT_SANDBOX_ENABLED` | **não** defina (ou `false`) | o provedor de teste nunca roda em produção | `true` em produção = o serviço não sobe |
| `PAYMENT_WEBHOOK_SECRET` | se existir, **≥ 32 caracteres** | segredo curto deixa o endpoint como "não configurado" | webhook de pagamentos responde 404 |
| `DONATION_WEBHOOK_SECRET` | deixe vazio na produção | sem provedor real de doações, o webhook de doações fica fechado (404) | — |
| `METRICS_TOKEN` | opcional | sem ele, `/readyz` público mostra só: status, banco, armazenamento durável, antivírus ligado/desligado | — |

Conferir (sem mudar): `ANTIVIRUS_PROVIDER` e `ALLOW_UNSCANNED_DOWNLOADS` — a versão **não** recusa subir sem antivírus
(decisão sua), mas `pos-deploy` avisa se estiver desligado.

## 2. Demo (publica sozinho a cada merge na `main`)

- [ ] Depois do merge, o demo aplica a migração **0074** sozinho (o `start_container.sh` migra antes de subir).
- [ ] O seed do demo dá à conta "controller" também o papel `compliance` (precisa de reseed para valer).
- [ ] Entrar com uma conta da equipe: confirmar identidade numa ação administrativa (a janela pede senha + código).
- [ ] Equipe sem MFA: ativar exige o código do aplicativo **e** o código enviado ao e-mail (o e-mail do demo vai para o console).

## 3. Conferir o IP no demo (antes da produção)

- [ ] Com `TRUST_PROXY_HEADERS=true` e `TRUSTED_PROXY_HOPS=1` no demo, faça login e abra a trilha (`/admin/rastro`):
      o IP do login tem de ser o **seu** IP público. Se aparecer um IP do Railway/Cloudflare, aumente para 2 e repita.

## 4. Produção

- [ ] Railway → `impactohubsocial` → Ctrl+K → "Deploy latest commit".
- [ ] Railway → `pleasing-trust` → "Deploy latest commit" (as rotinas `pending_scans` e `risk_scan` mudaram).
- [ ] GitHub → Actions → `pos-deploy` com o commit esperado: `/readyz` 200, cabeçalhos, smoke.
- [ ] GitHub → Actions → `backup-supabase` modo `backup` (primeiro backup no formato autenticado `.dump.aead`) e, em seguida,
      modo `ensaio-restauracao` — tem de terminar com `BACKUP_RESTORE_OK` e "Formato: AEAD".

## 5. O que muda para quem usa

- Equipe: ações administrativas de escrita pedem a confirmação de identidade a cada 15 minutos; ninguém da equipe desliga o próprio MFA.
- Bloqueio de organização: uma pessoa propõe, outra confirma.
- Verificação do beneficiário: precisa de uma segunda pessoa para confirmar. Se houver na produção verificação antiga sem
  confirmação, as campanhas dela não publicam até alguém confirmar (hoje não há campanhas na produção, que está na v0.30.0).
- Chave PIX de repasse: confirmar identidade; depois da primeira assinatura não muda (só por nova versão do acordo).

## 6. Voltar atrás (rollback)

- Código: Railway → Deployments → deploy anterior → "Redeploy".
- A migração 0074 é só para frente e **não é desfeita**; o código anterior convive com ela (colunas novas têm valor padrão;
  funções continuam executáveis por `impacto_app`). O que o código antigo tentar fazer contra as travas novas
  (ex.: marcar beneficiário como verificado sem titularidade conferida) **falha** em vez de gravar errado.
- Backup: os `.dump.aead` só abrem com `scripts/backup_crypt.py` (instruções no cabeçalho do workflow `backup-supabase`).
