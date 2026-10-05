# Testes (v0.9.0)

Executar:
```bash
export TEST_ADMIN_DATABASE_URL="postgresql://postgres@127.0.0.1:5432/postgres"   # superusuário local para criar bancos temporários
cd backend
PASSWORD_SCRYPT_N=16384 RATE_LIMIT_MULTIPLIER=1000 python3 -m unittest discover -s tests -t . -v
```
Os parâmetros `PASSWORD_SCRYPT_N` e `RATE_LIMIT_MULTIPLIER` aceleram o ambiente de teste e **são recusados em staging/production**.
Cada módulo cria um banco `impacto_test_<pid>` com os papéis reais (`impacto_owner`/`impacto_app`), aplica as migrações, sobe o servidor uvicorn real em porta efêmera e o remove ao final.
Pré-requisitos: PostgreSQL 16 + `psql`, Python 3.12+, e (para E2E) Playwright + Chromium e `web/dist` compilado.

## Resultado da última execução (neste ambiente)
**111 testes, 0 falhas, 0 ignorados, ~24 s.** Log completo: `docs/evidence/test_run_v0.7.0.log`.

| Arquivo | Escopo |
|---|---|
| `test_api_auth.py` | cadastro, verificação de e-mail, login, bloqueio por força bruta, anti-enumeração, refresh com rotação e detecção de reuso, logout, reset de senha, MFA (TOTP/recuperação), CSRF/Origin, modo token vs cookie |
| `test_security_tenancy.py` | **RLS** (API e SQL direto como `impacto_app`), IDOR entre organizações, escalonamento de privilégio, colunas protegidas, append-only, adulteração do ledger detectada, upload malicioso (PDF ativo, macro, zip bomb, magic bytes), papel do banco não ignora RLS |
| `test_api_workflow.py` | jornada completa OSC → edital → candidatura → rascunho → revisão/assinatura; empresa → interesse → diligência → aporte → despesa/evidência → devolutiva |
| `test_api_features.py` | alertas/buscas salvas, governo (k-anonimato), IA (cota, estruturação), cobrança/vouchers (sandbox, dupla aprovação, webhook com assinatura inválida/duplicada), fiscal (só regras aprovadas), jobs/importação, privacidade/admin, contrato OpenAPI, invariância do match com/sem plano premium |
| `test_oidc.py` | SSO com IdP falso local (PKCE, JWKS, `nonce`, `amr`) |
| `test_unit.py` | senhas, TOTP (vetores RFC 6238), SigV4 (vetor oficial AWS), redação de PII, motor de match/território, motor fiscal, validadores (CNPJ), configuração fail-fast |
| `test_architecture.py` | match/directory não importam billing (AST); contexto de sistema só em módulos permitidos; nenhum segredo versionado; **toda tabela tem RLS**; todo handler declara autenticação; sem SQL montado por concatenação com entrada do usuário |
| `test_e2e_web.py` | Chromium real: cadastro → e-mail → login → projeto com assistência → publicar; feed da empresa no celular; cabeçalhos/CSP sem violações |

## Testes negativos cobertos
Sem permissão, tenant errado, UUID inválido, token expirado/reutilizado, webhook falsificado e duplicado, upload malicioso, recurso inexistente, voucher esgotado/duplicado, plano sem preço, aprovação pelo mesmo revisor, regra fiscal sem dupla aprovação.

## O que NÃO foi testado (honesto)
- Carga/performance (nenhum teste de carga executado); acessibilidade automatizada (axe) — apenas revisão manual de semântica/foco.
- Provedores reais: Stripe, SMTP, S3, ClamAV, OIDC corporativo, CNPJ/CEIS, Anthropic/OpenAI — só fakes locais e vetores oficiais.
- Docker/Compose, Nginx, CI no GitHub, apps Android/iOS.
- Typecheck com `@types/react` oficiais (o ambiente usa *shims* offline; o CI usa os oficiais).
- `pip-audit`/`npm audit` (rede bloqueada).

## Atualização v0.9.0
**182 testes, 0 falhas** — `docs/evidence/test_run_v0.9.0.log`; detalhes por área em `TEST_REPORT.md`. Novos arquivos: `test_v080.py`, `test_e2e_v080.py`, `test_v090_solutions.py`, `test_e2e_v090.py`. Scripts de evidência: `scripts/bench_solution_search.py`, `scripts/weights_sensitivity.py`, `scripts/loadtest.py`.
Observação: o banco de teste é compartilhado entre módulos do mesmo processo; testes de ranking devem avaliar apenas os próprios dados.
