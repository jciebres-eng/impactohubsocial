# Arquitetura — v0.7.0

Este documento descreve **o que o código faz hoje**. Itens não implementados aparecem marcados como tal.

## Visão geral

```
 Navegador / PWA            App Android/iOS (Capacitor — gerar com mobile/setup.sh)
   cookies httpOnly + CSRF    Bearer (X-Auth-Mode: token)
            \                     /
             v                   v
        nginx (infra/nginx/impacto.conf: TLS, gzip, limites)   [template — não executado aqui]
                     |
                     v
   uvicorn + Starlette  ── backend/impacto/app.py
     ├─ middlewares: SecurityHeaders (CSP self-only, HSTS, XFO DENY), CORS allowlist, request_id, métricas
     ├─ /v1/*  rotas declarativas (RouteSpec) → make_endpoint:
     │      autentica → autoriza (tipo de organização, papel, MFA admin, feature do plano) → valida corpo (pydantic)
     │      → abre transação com contexto RLS → serviço/engine → resposta JSON / erro RFC 7807
     ├─ /healthz /readyz /metrics(token) /v1/meta/config
     └─ SPA estática (web/dist) com fallback para index.html
                     |
                     v
   PostgreSQL 16  (papel impacto_app: NOBYPASSRLS, não é dono das tabelas)
     RLS em todas as tabelas · triggers de integridade · cadeias de hash (auditoria/ledger)
                     |
   Adapters: storage (local | S3 SigV4) · antivírus (clamd INSTREAM | none) · e-mail (console | SMTP)
             cobrança (none | sandbox | stripe | manual) · IA (local | anthropic | openai_compatible | disabled)
             OIDC (Authorization Code + PKCE) · HTTP client com timeout/retry
   Jobs: python -m impacto.jobs once|loop — encerrar editais, importar fontes, buscas salvas/alertas,
         reprocessar antivírus pendente, vencimento de documentos, retenção
```

## Decisões estruturais (detalhes em `DECISIONS.md`)
- **Python/Starlette** em vez de NestJS (ADR-017): o ambiente de construção só tinha o ecossistema Python/Node pré-instalado
  sem acesso a registros; a stack escolhida está pinada em `backend/requirements.txt` e é madura.
- **Driver libpq via ctypes** (ADR-016): sem psycopg disponível; usa apenas `PQexecParams` (parâmetros sempre separados do SQL),
  exceções tipadas por SQLSTATE e pool próprio. Substituível por psycopg 3 sem mudar serviços (interface `Connection`).
- **Segurança no banco, não só na API**: toda transação define `app.user_id`, `app.org_id`, `app.org_kind`,
  `app.platform_admin`, `app.system` via `set_config(..., true)`; as políticas RLS leem essas variáveis.
- **Engines puras** (`engines/match`, `engines/fiscal`, `engines/ai/local`): funções sem I/O, testáveis isoladamente,
  versionadas (`match-engine@1.0.0`, `fiscal-engine@1.0.0`).
- **Billing isolado do match**: teste de arquitetura (AST) garante que `engines/match`, `services/matching` e `services/directory`
  não importam billing/entitlements.

## Módulos do backend (`backend/impacto/`)
| Caminho | Responsabilidade |
|---|---|
| `config.py` | Settings a partir de env; `validate()` falha no boot com configuração insegura em staging/production |
| `db/pq.py`, `db/pool.py`, `db/migrate.py` | driver, pool + contexto RLS, migrações e sincronização de planos/flags/regras candidatas |
| `http.py` | RouteSpec, autenticação, autorização, validação, mapeamento de erros |
| `security/` | senhas (scrypt + PBKDF2 legado), tokens opacos, TOTP, cifra Fernet |
| `services/` | auth, oidc, billing, entitlements, matching, workflow, documents, compliance, directory, audit, ratelimit, validators |
| `engines/` | match, fiscal, IA (local + gateway) |
| `adapters/` | mail, storage, antivirus, http_client |
| `api/*_routes.py` | 165 operações HTTP (ver `docs/API.md`, gerado por `scripts/gen_api_docs.py`) |
| `jobs.py`, `cli.py`, `seed_dev.py` | tarefas agendadas, CLI administrativa, dados fictícios de desenvolvimento |

## Frontend (`web/`)
React 19 + TypeScript, sem biblioteca de roteamento (roteador próprio sobre History API), build com esbuild
(`build.mjs`, assets com hash), Service Worker gerado no build (precache do shell; **nunca** cacheia `/v1`).
CSP sem `unsafe-inline`: estilos dinâmicos aplicados via CSSOM. Fontes locais (Lora e Inter, OFL).
Portais por tipo de organização: OSC, Empresa, Profissional parceiro, Governo e Administração.

## Mobile (`mobile/`)
Capacitor 7 (declarado em `web/package.json`, ainda não instalado/executado) envolvendo o mesmo build web. O projeto nativo **não está gerado no pacote** (exige SDKs e rede);
`mobile/setup.sh` gera Android/iOS, copia ícones/splash e aplica deep links. Ver `docs/MOBILE.md`.

## Fluxos principais
1. **OSC → edital**: catálogo unificado (`calls`: edital, fundo, chamamento, grant; esferas federal/estadual/municipal/local/internacional)
   → match explicável → candidatura assistida (`applications` + `application_steps`) → rascunhos IA → revisão/assinatura
   profissional → submissão (externa ou na plataforma) → acompanhamento.
2. **Empresa → projeto**: feed de projetos publicados ordenado por elegibilidade e compatibilidade → interesse → diligência
   (documentos liberados) → aporte (`commitments`) → execução (despesas, evidências, marcos) → devolutivas e relatórios.
3. **Governo**: publica editais e materiais; consulta dados agregados por território.
4. **Admin**: compliance/KYB, credenciais profissionais, regras fiscais (dupla aprovação), vouchers (dupla aprovação), denúncias,
   flags, verificação das cadeias de auditoria.
