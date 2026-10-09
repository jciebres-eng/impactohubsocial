# Checklist do proprietário — Railway, Supabase, R2, Cloudflare (v0.31.0)

Tudo aqui depende de conta, painel ou decisão sua. **Nenhum valor secreto vai para o chat, para o Git ou
para um relatório** — você cola o valor no painel e me diz só o **nome** da variável que configurou.
Detalhes técnicos de cada item: `docs/ops/INFRA_RAILWAY_SUPABASE_R2_v0310.md`.

## Agora (destrava a auditoria do que está no ar)

- [ ] **Diga se foi você que ligou o Railway ao GitHub em 09/10, por volta de 14:20 (Cuiabá).** O banco recebeu
      as migrações 0064–0070 nesse horário, fora do workflow do GitHub.
- [ ] **Envie a URL pública do serviço** no Railway (algo como `https://….up.railway.app`). Não é segredo.
- [ ] Se puder, no seu computador: `npm i -g @railway/cli` → `railway login` → `railway link` (escolha o projeto)
      → `railway config pull`. Envie o arquivo gerado: ele traz a configuração com os valores **ocultos**.
- [ ] No GitHub → *Actions* → **pos-deploy** → *Run workflow* com a URL. (Ou me passe a URL que eu disparo.)

## Decisão (P0): separar staging e produção

O projeto Supabase atual tem **15 contas de demonstração e 1 conta real**. Escolha:

- [ ] **(a) recomendado** — este projeto passa a ser **staging**; crie um **novo projeto Supabase para produção**
      (vazio; o primeiro deploy cria o esquema e `impacto_app`).
- [ ] (b) este projeto vira produção e as contas de demonstração são desativadas antes de abrir ao público.

## Railway (por ambiente: staging e production)

- [ ] Serviço `api`: repositório `jciebres-eng/impactohubsocial`, branch (`staging`/`main`), Dockerfile da raiz,
      *Healthcheck Path* `/readyz`, *Healthcheck Timeout* 300, 1 réplica.
- [ ] Serviço `worker`: mesmo repositório e branch, *Start Command* `sh /app/start_worker.sh`, sem healthcheck.
- [ ] Serviço `clamav`: *Deploy from Docker image* `clamav/clamav:stable`, sem domínio público.
- [ ] Variáveis da `api` conforme a tabela §3.1 do documento técnico; no `worker`, **referências** às da `api`.
- [ ] `IMPACTO_APP_ROTATE_PASSWORD=false` (se estiver `true`, volte para `false`).
- [ ] `DATABASE_URL` = *Session pooler* do Supabase (porta 5432) com `?sslmode=require` no fim.
- [ ] Alertas de uso/gasto no Railway (*Usage*), conforme o seu limite.

## GitHub

- [ ] *Settings → Secrets → Actions* → **`IMPACTO_APP_PASSWORD`**: atualize para o **mesmo valor** usado no Railway
      (hoje ele não confere com o banco).
- [ ] *Settings → Environments*: criar `staging` e `production`; em `production`, **Required reviewers** = você.
- [ ] Em cada ambiente: `R2_ENDPOINT`, `R2_BUCKET`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`; opcional
      `SMOKE_EMAIL`/`SMOKE_PASSWORD` de uma conta **de teste**.
- [ ] *Settings → Branches*: proteger `main` (PR obrigatório + CI verde) — o Railway publica o que entra no `main`.
- [ ] Criar as tags que faltam (o ambiente daqui não consegue empurrar tags): `v0.31.0` no commit indicado no
      relatório final.

## Cloudflare R2

- [ ] Criar **dois buckets privados**: um de staging, um de produção. Sem domínio público, sem acesso público.
- [ ] Criar um **token R2 por bucket** (*Object Read & Write*, restrito ao bucket).
- [ ] Endpoint: `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`; região: `auto`.
- [ ] Rodar *Actions* → **armazenamento** → ambiente `staging`. Precisa dar **PASS**.

## Cloudflare (domínio)

- [ ] Exportar a zona DNS atual antes de qualquer mudança (inclui MX/SPF/DKIM/DMARC).
- [ ] Domínio customizado no Railway → criar o registro indicado pelo Railway, **DNS-only** até o certificado sair.
- [ ] Depois: TLS *Full (strict)*; nada de cache em `/v1/*`.

## E-mail transacional

- [ ] Escolher o provedor SMTP e autenticar o domínio (SPF, DKIM, DMARC). Configurar `SMTP_*` no Railway.
- [ ] `EMAIL_CANARY_TO` = um endereço seu (o worker manda um canário e registra o resultado).

## Antes de abrir para o público (produção)

- [ ] `pos-deploy` contra a URL de produção: commit certo, `readyz` 200, `storage_durable: true`, antivírus `clamd`.
- [ ] `supabase` → `backup-restaurar` no projeto de produção: **PASS** (e conferir no painel do Supabase o backup
      gerenciado e a retenção do seu plano).
- [ ] Primeiro administrador: `python3 -m impacto.cli create-admin …` (no shell do serviço `api` do Railway); MFA no
      primeiro acesso.
- [ ] Portão jurídico: aprovar `terms_of_use` e `privacy_policy` com revisor nomeado (`docs/PUBLICACAO.md` §7) — o
      cadastro responde 503 até isso.
- [ ] **Aprovação explícita sua** para a produção. Cobrança real continua desligada (nenhuma regra ativa).
