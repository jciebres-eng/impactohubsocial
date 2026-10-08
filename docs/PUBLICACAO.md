# Publicação — do zero a um ambiente no ar

Procedimento na ordem em que precisa acontecer, com a verificação de cada passo. Serve para
**staging** (restrito, dados fictícios) e para **produção**; onde houver diferença, está dito.

**Antes de começar**, tenha em mãos os itens da seção A de
`Dependencias_de_terceiros_e_pessoas_IMPACTO_v0.23.0.docx`: domínio, banco gerenciado, provedor
SMTP, hospedagem de contêiner e cofre de segredos. Sem SMTP a aplicação **recusa subir** — não é
possível contornar.

---

## 1. Banco

Crie a instância PostgreSQL 16 gerenciada, com PITR habilitado e rede privada. Depois, os dois papéis:

```bash
psql "$ADMIN_URL" -f infra/db/bootstrap.sql
```

Isso cria `impacto_owner` (dono do schema, usado só por migração e backup) e `impacto_app` (a
aplicação, **sem** bypass de RLS). A separação é o que torna o isolamento entre organizações
verificável — não a comprometa usando o mesmo papel para os dois.

**Verificação:**

```bash
psql "$APP_URL" -tAc "SELECT current_user, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"
# tem de devolver: impacto_app | f | f
```

## 2. Segredos

```bash
cd backend && python3 -m impacto.cli gen-secrets
```

Guarde a saída no cofre do provedor. **Nunca** em arquivo versionado. Três são obrigatórios e a
aplicação recusa subir sem eles: `SECRET_KEY`, `VOUCHER_HMAC_KEY`, `FIELD_ENCRYPTION_KEY`.

`FIELD_ENCRYPTION_KEY` aceita rotação no formato `"nova,antiga"` — a antiga continua decifrando o que
já estava cifrado.

## 3. Configuração

Copie `.env.example` e preencha. Os campos que **bloqueiam o boot** se estiverem errados:

| Variável | Valor | Por quê |
|---|---|---|
| `IMPACTO_ENV` | `staging` ou `production` | **Sem isto, a isenção de loopback do bloqueio de SSRF continua valendo** — é a porta para todo serviço interno da máquina |
| `PUBLIC_BASE_URL` | `https://…` | cookie seguro só trafega em https |
| `COOKIE_SECURE` | `true` | obrigatório fora de desenvolvimento |
| `MAIL_PROVIDER` | `smtp` | `console` é **recusado** |
| `SMTP_HOST` | o do seu provedor | exigido quando `MAIL_PROVIDER=smtp` |
| `IMPACTO_SEED_DEMO` | **ausente** | dados fictícios são recusados fora de desenvolvimento |
| `RATE_LIMIT_MULTIPLIER` | `1` | qualquer outro valor é recusado |
| `PASSWORD_SCRYPT_N` | ≥ `131072` | abaixo disso é recusado |
| `TRUST_PROXY_HEADERS` | `true` **só** atrás de proxy | se marcar true sem proxy, o IP do cliente passa a ser forjável |

**Verificação, antes de subir qualquer coisa:**

```bash
cd backend && python3 -c "from impacto.config import load_settings; load_settings(); print('configuração válida')"
```

Se faltar algo, a saída lista item por item o que está errado. Esse é o comportamento esperado — o
produto prefere não subir a subir inseguro.

## 4. Migração

```bash
MIGRATION_DATABASE_URL="…impacto_owner…" python3 -m impacto.db.migrate
```

As migrações são **avanço-somente** e cada arquivo tem o sha256 registrado. Uma migração que mude de
conteúdo depois de aplicada é recusada.

**Verificação:**

```bash
psql "$APP_URL" -tAc "SELECT count(*) FROM schema_migrations"   # 63 nesta versão
```

## 5. Build e publicação

```bash
docker build -t impacto:$(cat VERSION) .
```

O build roda o typecheck **oficial** (`tsconfig.json`, com `@types/react` instalado pela rede do
build) — é onde a limitação D-SUP1 do ambiente de desenvolvimento deixa de existir.

Suba o contêiner atrás do proxy TLS. `infra/nginx/impacto.conf` tem uma configuração de referência.

**Suba também o processo de tarefas.** Ele não é opcional:

```bash
python3 -m impacto.jobs loop          # laço contínuo (JOBS_INTERVAL_SECONDS, padrão 900)
# ou, por cron / CronJob:
python3 -m impacto.jobs once          # executa as 21 tarefas uma vez
```

Sem ele **não há backup agendado, não há canário de e-mail, não há retenção de dados e a tabela
`rate_events` nunca é limpa**. O produto continua respondendo — e vai acumulando dívida silenciosa
até alguém perguntar por que o último backup é de três semanas atrás.

## 6. Primeiro administrador

```bash
python3 -m impacto.cli create-admin --email voce@dominio --name "Seu Nome"
# a senha é lida do stdin, nunca por argumento
```

É o único caminho para o primeiro administrador: sem ele não há MFA, não há aprovação das minutas
jurídicas e não há painel. O comando é idempotente — rodar de novo com o mesmo e-mail promove em vez
de duplicar.

**No primeiro acesso à área administrativa, o MFA é exigido.** Não é possível pular: toda rota
`auth="admin"` recusa sessão sem MFA verificado.

## 7. Portão jurídico — o cadastro responde 503 até você abrir

> **Isto é desenho, não defeito.** Enquanto `terms_of_use` e `privacy_policy` não estiverem
> **aprovados**, `POST /v1/auth/register` responde **503 `legal_documents_not_published`**. O produto
> recusa coletar aceite de documento que ninguém aprovou.

```bash
python3 -m impacto.cli legal-list      # situação das 11 minutas, com o id de cada uma
python3 -m impacto.cli legal-approve --doc-key terms_of_use \
        --reviewed-by "Fulana de Tal, OAB/UF 1234" --review-reference "Parecer 12/2026"
python3 -m impacto.cli legal-approve --doc-key privacy_policy \
        --reviewed-by "Fulana de Tal, OAB/UF 1234" --review-reference "Parecer 12/2026"
```

A aprovação **exige revisor nomeado e referência da revisão** — o comando não aceita sem, e o banco
também não. Isto não é atalho para aprovar sem revisão: é o registro de que alguém com nome assumiu
a revisão. Se o nome for inventado, a mentira passa a ter autor, que é o máximo que software pode
fazer a respeito.

As outras nove minutas só bloqueiam quando o recurso correspondente entrar em uso (cobrança,
marketplace, contrato público). Veja o documento de dependências para quando cada uma é necessária.

## 8. Verificação pós-publicação

```bash
python3 scripts/smoke_test.py --base https://SEU-DOMINIO \
        --email conta-de-teste@dominio --password '…' --out /tmp/smoke.json
```

São **27 verificações** com veredito ao final: `GO`, `GO WITH CONDITIONS` ou `NO-GO`, e código de
saída diferente de zero quando alguma obrigatória falha — dá para usar em automação.

Quatro delas merecem atenção porque falham em silêncio no mundo real:

| Verificação | O que pega |
|---|---|
| `hardened_env` | alvo em https com `IMPACTO_ENV` esquecido — a isenção de loopback do SSRF continua ativa e o HSTS não é emitido |
| `session_ip_is_real` | proxy sem `X-Forwarded-For`, ou `TRUST_PROXY_HEADERS` desligado: o limite por IP vira **coletivo** (um pico derruba o login de todo mundo) e a auditoria grava o IP do proxy |
| `legal_gate` | diz, em vez de deixar você descobrir, que o cadastro está em 503 por desenho |
| `rate_limit_present` | só com `--exercise-rate-limit`, e **por último**: exercitá-la bloqueia o seu IP por ~15 minutos |

Rode com uma conta de **organização cliente** (OSC ou empresa), não com o administrador da
plataforma — a organização dele é do tipo `platform` e não tem projetos, então a leitura de banco
aparece como ignorada.

`/readyz` devolve **503** se o banco estiver fora ou se houver migração pendente, e nomeia quais
faltam. **Não direcione tráfego enquanto ele não devolver 200** — 503 por migração pendente significa
que o código espera um esquema que o banco não tem.

Depois do smoke, o caminho que só uma pessoa confirma:

1. cadastro → **o e-mail chega de verdade** → verificação → login
2. criar organização → enviar documento → ver o documento
3. administrador → login com MFA → painel

O passo 1 é o que mais falha, e por motivo de DNS, não de código: sem SPF, DKIM e DMARC o e-mail sai
e cai em spam. O produto registra a tentativa em `email_events`; se houver linha com `status='failed'`,
o problema é do provedor ou da rede, não da aplicação.

## 9. Backup — antes de qualquer dado real

```bash
BACKUP_DATABASE_URL="…impacto_owner…" bash scripts/backup.sh /caminho/backups
```

E **teste a restauração antes de precisar dela**, em banco descartável:

```bash
ADMIN_DATABASE_URL="…" bash scripts/restore_test.sh /caminho/backups/impacto-*.dump
```

O script confere o sha256, conta as migrações, verifica as quatro cadeias de hash e recusa um
restore que traga estado que não deveria existir. Um backup cuja restauração nunca foi testada não é
um backup.

**Os arquivos do cofre de documentos não estão no dump do PostgreSQL.** Se `STORAGE_PROVIDER=s3`,
use o versionamento do bucket; se for local, inclua o volume no snapshot.

## 10. Observabilidade

- `/metrics` exige `METRICS_TOKEN`; sem token em produção, a rota responde 404 de propósito.
- `infra/monitoring/alerts.yml` traz 16 regras prontas, entre elas **backup falhou** e **backup sem
  sucesso há tempo demais** — as duas que mais importam e as que ninguém lembra de criar.
- `ops_job_runs` e `GET /v1/operacoes/health` respondem "quando foi o último backup bem-sucedido",
  que é a pergunta que aparece no meio de um incidente.

---

## Reversão

1. **Antes de qualquer mudança**, backup com o `.sha256` guardado.
2. O código volta por `git checkout` da tag anterior e novo deploy.
3. **As migrações não têm volta**: são avanço-somente, sem `down`. Reverter esquema é restaurar
   backup — e primeiro em banco descartável, nunca direto em produção.
4. Depois de restaurar, `/readyz` acusa se o banco ficou à frente ou atrás do código.

## 1-A. Banco gerenciado sem acesso de superusuário (Supabase e similares) — v0.24.0

Num PostgreSQL gerenciado você não roda `infra/db/bootstrap.sql`: não há `impacto_owner`, o dono do
schema é o usuário administrativo do projeto, e o pgcrypto fica na schema `extensions`, não em
`public`. O contêiner cobre esse caso com três variáveis:

| Variável | Para quê |
|---|---|
| `DATABASE_URL` | a conexão **administrativa** do projeto — usada só para bootstrap e migrações |
| `IMPACTO_APP_PASSWORD` | senha do papel `impacto_app`, **obrigatória** (≥16 caracteres). Nunca é derivada da URL administrativa: o papel separado existe para que a aplicação não carregue a credencial do administrador |
| `IMPACTO_BOOTSTRAP_EXTERNAL=true` | cria `impacto_app` (idempotente; nunca altera senha de papel existente) antes de migrar |

O entrypoint (`backend/start_container.sh`) faz, nesta ordem e com log por etapa: bootstrap →
migrações como administrador → **troca a URL para `impacto_app`** → ASGI. A aplicação em pé nunca
está conectada como administrador — isso é conferido em `test_v0240_container_entrypoint.py`, que
executa o script de verdade contra um banco limpo.

A migração `0063` fixa `search_path = public, extensions, pg_temp` nas nove funções que chamam
`digest()` (cadeias de auditoria, ledger, confiança e valor; verificações; hash de documento legal).
Sem isso, num banco gerenciado a plataforma não sobe: o primeiro INSERT em `audit_events` falha com
"function digest(text, unknown) does not exist".

**O que foi provado e o que não foi.** Provado aqui, sem Docker: migrações como administrador, troca
de papel, seed e login. **Não provado aqui:** o comportamento com o pgcrypto efetivamente em
`extensions` — neste ambiente ele está em `public` desde a migração 0001, então a schema
`extensions` fica vazia e o teste só prova que nada quebrou. A prova positiva só vem do primeiro
`readyz` contra o banco gerenciado. A construção da imagem Docker também continua sem prova aqui.

**Demonstração num banco gerenciado NÃO é produção.** Para ter seed e contas de demonstração o
contêiner tem de subir com `IMPACTO_ENV=development`, e isso desliga: custo mínimo de senha, limite
de tentativas sem folga, e-mail real, proibição de seed. Uma instância assim, com HTTPS num domínio
público, é um ambiente de teste e precisa dizer isso na URL e na tela — nunca receber dado pessoal
real. A imagem desta versão sobe em `production` por padrão; quem quiser demonstração escolhe
`development` ao subir, e assume o que isso significa.

## O que este guia não cobre

Publicar não é o mesmo que **abrir ao público**. Antes do primeiro dado pessoal real são necessários
os itens da seção B do documento de dependências: CNPJ do operador, encarregado de dados nomeado,
as 11 minutas jurídicas aprovadas, teste de intrusão independente e política de retenção validada.

Nada disso é código, e nenhum deles pode ser contornado por software.
