# RB-01 — Segredo exposto (senha, chave de API, token, frase do backup)

**Sinais:** a chave apareceu num chat, num print, num commit, num e-mail; o gitleaks do CI acusou; o GitHub
avisou ("secret scanning"); um provedor avisou uso estranho.

## Conter (nos primeiros minutos)

1. **Descubra QUAL segredo é** (pelo nome, nunca copiando o valor de novo para outro lugar).
2. **Gere um segredo NOVO no provedor dono dele** e só depois apague o antigo:
   | Segredo | Onde trocar | Onde atualizar depois |
   |---|---|---|
   | Token do R2 do backup (`R2_BACKUP_*`) | Cloudflare → R2 → Manage API tokens | GitHub → Settings → Secrets → Actions |
   | Token do R2 dos arquivos (`S3_*`) | Cloudflare → R2 → Manage API tokens | Railway → serviço `impactohubsocial` e `pleasing-trust` → Variables |
   | Senha administrativa do Supabase | Supabase → Project Settings → Database → Reset password | GitHub (`SUPABASE_ADMIN_URL`) e Railway (`DATABASE_URL`) |
   | Senha do papel `impacto_app` | (rotação pelo bootstrap, ver `docs/DEPLOYMENT.md`) | Railway `IMPACTO_APP_PASSWORD` |
   | `SECRET_KEY` / `VOUCHER_HMAC_KEY` | gerar valor novo (≥ 32 caracteres) | Railway — **derruba todas as sessões** (todos entram de novo) |
   | `FIELD_ENCRYPTION_KEY` | **NÃO troque sozinho**: a chave antiga é necessária para ler o que já está cifrado. Siga a rotação de `core/keys.py` (chave nova primeiro, antiga mantida para leitura) | Railway |
   | Chave SMTP do Brevo | Brevo → SMTP & API | Railway `SMTP_PASSWORD` |
   | Segredos de webhook (`PAYMENT_WEBHOOK_SECRET`, `DONATION_WEBHOOK_SECRET`) | gerar novo (≥ 32 caracteres) | Railway e no provedor que assina |
   | `BACKUP_PASSPHRASE` | gerar nova | GitHub. **Guarde a antiga** até a retenção de 30 dias apagar os backups feitos com ela — sem ela eles não abrem |
3. Faça o deploy (Railway → Ctrl+K → "Deploy latest commit") onde a variável mudou.
4. Confira que o segredo antigo **não funciona mais** (o provedor mostra o token como revogado).

## Investigar

- Desde quando o segredo estava exposto? Quem poderia ter visto?
- Registros do provedor (Cloudflare R2 → métricas do bucket; Supabase → logs; Railway → logs) no período.
- Se o segredo dava acesso a dados pessoais e há sinal de uso → siga também o [RB-02](RB-02-vazamento-de-dados-pessoais.md).

## Se estava num commit

Trocar o segredo é o que resolve. Reescrever o histórico do git **não** desfaz a exposição (cópias já existem);
só faça se o responsável decidir, e depois da troca.

## Pendência conhecida na data desta versão

O token do backup no R2 citado como "C2" na auditoria de 09/10/2026 **ainda precisa ser trocado** pelo responsável.
