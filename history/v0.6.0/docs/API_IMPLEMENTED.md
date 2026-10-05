# API implementada — Plataforma Impacto v0.4

## Visão geral

A API é um servidor HTTP Python baseado na biblioteca padrão, implementado em `src/impacto/app.py`. Ela serve também o painel web local em `web/`.

```bash
./run_local.sh
# http://localhost:8080
```

Para outro banco/porta:

```bash
IMPACTO_DB=./data/dev.sqlite3 PORT=8080 ./run_local.sh
```

## Autenticação

O cadastro e login são locais para desenvolvimento. Senhas são armazenadas com PBKDF2-HMAC-SHA256 e salt individual. O login retorna um bearer token de sessão com validade de 24 horas.

```bash
TOKEN=$(curl -s -X POST http://localhost:8080/v1/auth/login \
  -H 'content-type: application/json' \
  -d '{"email":"admin@impacto.local","password":"Admin@123"}' | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])')
export AUTH="Authorization: Bearer $TOKEN"
```

Conta de demonstração: `admin@impacto.local` / `Admin@123`. Não usar em produção.

## Endpoints implementados

| Método | Rota | Autenticação | Função |
|---|---|---:|---|
| `GET` | `/healthz` | Não | Health check |
| `GET` | `/` | Não | Painel web |
| `POST` | `/v1/auth/register` | Não | Criar organização e usuário owner |
| `POST` | `/v1/auth/login` | Não | Criar sessão |
| `GET` | `/v1/me` | Sim | Identidade e tenant atual |
| `GET` | `/v1/plans` | Sim | Catálogo de planos |
| `GET` | `/v1/entitlements` | Sim | Plano e direitos ativos do tenant |
| `POST` | `/v1/subscriptions` | Sim | Criar assinatura sandbox |
| `GET` | `/v1/dashboard/summary` | Sim | Resumo operacional do tenant |
| `GET` | `/v1/programs` | Sim | Listar programas do tenant |
| `POST` | `/v1/programs` | Sim | Criar programa |
| `GET` | `/v1/opportunities` | Sim | Listar oportunidades do tenant |
| `POST` | `/v1/opportunities` | Sim | Criar oportunidade |
| `POST` | `/v1/matches/evaluate` | Sim | Avaliar e persistir match explicável |
| `GET` | `/v1/documents` | Sim | Listar metadados de documentos do tenant |
| `POST` | `/v1/documents` | Sim | Registrar documento por hash SHA-256 |
| `POST` | `/v1/vouchers/redeem` | Sim | Resgatar voucher de uso único |
| `GET` | `/v1/audit-events` | Sim | Ler auditoria do tenant |
| `GET` | `/v1/admin/overview` | Admin | Métricas administrativas locais |
| `GET` | `/v1/fiscal/mechanisms` | Sim | Retorna estado `pending_review`, sem inventar regra |

## Exemplos

### Criar programa

```bash
curl -s -X POST http://localhost:8080/v1/programs \
  -H "$AUTH" -H 'content-type: application/json' \
  -d '{"name":"Programa Comunidades","cause":"educação","territory":"Brasil","budget_cents":5000000,"status":"open"}'
```

### Criar oportunidade

```bash
curl -s -X POST http://localhost:8080/v1/opportunities \
  -H "$AUTH" -H 'content-type: application/json' \
  -d '{"program_id":"PROGRAM_ID","title":"Biblioteca comunitária","description":"Acervo local","requested_cents":100000,"territory":"Brasil","cause":"educação"}'
```

### Avaliar match

```bash
curl -s -X POST http://localhost:8080/v1/matches/evaluate \
  -H "$AUTH" -H 'content-type: application/json' \
  -d '{"program_id":"PROGRAM_ID","opportunity_id":"OPPORTUNITY_ID","requested_cents":100000,"territory":"Brasil","signals":{"cause_alignment":1,"territory":0.9,"budget_ticket":0.8}}'
```

A resposta contém `eligibility`, `compatibility`, `confidence`, `blockers`, `why_match`, `why_not`, `risks`, `missing_information`, `next_action` e `engine_version`. Plano, assinatura e voucher não entram no cálculo.

### Registrar documento

```bash
curl -s -X POST http://localhost:8080/v1/documents \
  -H "$AUTH" -H 'content-type: application/json' \
  -d '{"filename":"estatuto.pdf","sha256":"0000000000000000000000000000000000000000000000000000000000000000","object_type":"organization","object_id":""}'
```

Este endpoint registra metadados e hash. Upload binário privado, antivírus e S3/KMS são adapters preparados separadamente e não estão ativos no servidor local.

### Assinatura sandbox

```bash
curl -s -X POST http://localhost:8080/v1/subscriptions \
  -H "$AUTH" -H 'content-type: application/json' \
  -d '{"plan_key":"funder_basic"}'
```

O retorno informa `status: sandbox_active` e `requires_external_gateway: true`. Isso habilita o fluxo de direitos local, mas não cobra nem cria uma assinatura financeira real.

## Isolamento e segurança

Toda consulta de negócio usa `org_id` derivado da sessão, nunca um tenant arbitrário enviado pelo cliente. O banco local habilita foreign keys. Para produção, use a migration PostgreSQL em `database/postgres/0001_rls.sql` com RLS forçada e configure `SET LOCAL app.org_id` após verificar a identidade.

Erros usam JSON com `title` e `status`. O endpoint de voucher não revela se um código inválido existe. A auditoria armazena uma cadeia de hashes, mas hash não comprova a veracidade do conteúdo.

## Testes

```bash
PYTHONPATH=. python3 -m unittest discover -s tests -v
python3 -m py_compile src/impacto/app.py src/impacto/providers.py
```

O cenário E2E validado cobre login, programa, oportunidade, match, documento, auditoria e painel.

## Não implementado neste servidor local

OIDC/MFA real, PostgreSQL conectado, storage S3/KMS, engine antivírus externo, billing real, IA com provedor, regras fiscais aprovadas, compliance/KYB, observabilidade remota, domínio e publicação de lojas. Essas áreas estão descritas como adapters/checklists e não como funcionalidades ativas.
