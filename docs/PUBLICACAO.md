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
psql "$APP_URL" -tAc "SELECT count(*) FROM schema_migrations"   # 62 nesta versão
```

## 5. Build e publicação

```bash
docker build -t impacto:$(cat VERSION) .
```

O build roda o typecheck **oficial** (`tsconfig.json`, com `@types/react` instalado pela rede do
build) — é onde a limitação D-SUP1 do ambiente de desenvolvimento deixa de existir.

Suba o contêiner atrás do proxy TLS. `infra/nginx/impacto.conf` tem uma configuração de referência.

## 6. Verificação pós-publicação

```bash
curl -fsS https://SEU-DOMINIO/healthz    # {"status":"ok", …}
curl -fsS https://SEU-DOMINIO/readyz     # {"status":"ready", "database":"ok", …}
```

`/readyz` devolve **503** se o banco estiver fora ou se houver migração pendente, e nomeia quais
faltam. **Não direcione tráfego enquanto ele não devolver 200** — 503 por migração pendente significa
que o código espera um esquema que o banco não tem.

Depois, o caminho que prova que o conjunto funciona de verdade:

1. cadastro → **e-mail chega** → verificação → login
2. criar organização → enviar documento → ver o documento
3. administrador → login com MFA → painel

O passo 1 é o que falha se o SMTP estiver mal configurado, e é o mais comum de dar errado: confira
SPF, DKIM e DMARC no DNS, senão o e-mail sai e cai em spam.

## 7. Backup — antes de qualquer dado real

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

## 8. Observabilidade

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

## O que este guia não cobre

Publicar não é o mesmo que **abrir ao público**. Antes do primeiro dado pessoal real são necessários
os itens da seção B do documento de dependências: CNPJ do operador, encarregado de dados nomeado,
as 11 minutas jurídicas aprovadas, teste de intrusão independente e política de retenção validada.

Nada disso é código, e nenhum deles pode ser contornado por software.
