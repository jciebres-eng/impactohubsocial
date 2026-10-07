# ENVIRONMENT_SETUP — ambiente de desenvolvimento

## Requisitos
Python 3.12+ · PostgreSQL 16 (`psql`, extensões `pgcrypto`, `citext` se aplicável — ver `infra/db/bootstrap.sql`) · libpq5 · Node 20+ (22 recomendado) · (E2E) Playwright + Chromium · (opcional) tesseract-ocr.

## Passo a passo
```bash
# 1. Dependências
python3 -m venv .venv && . .venv/bin/activate
pip install -r backend/requirements-dev.txt            # exige acesso ao PyPI
cd web && npm install && cd ..                          # exige acesso ao npm (traz @types oficiais)

# 2. Banco local (superusuário local apenas p/ dev)
export ADMIN_DATABASE_URL=postgresql://postgres@127.0.0.1:5432/postgres
bash scripts/dev_reset_db.sh                            # cria papéis/banco, aplica migrações (recusa nome contendo "prod"); imprime a DATABASE_URL de dev

# 3. Configuração
cp .env.example .env     # preencha (DATABASE_URL impressa acima); NUNCA versione .env
set -a; . ./.env; set +a
export IMPACTO_ENV=development IMPACTO_SEED_DEMO=true   # dados FICTÍCIOS (somente development/test)

# 4. Build e execução
make web && make dev                                    # http://localhost:8080
# usuários demo: osc@ / empresa@ / contador@ / governo@ / admin@demo.impacto.local — senha em DEMO_PASSWORD (padrão no seed_dev.py; só dev)

# 5. Testes
export TEST_ADMIN_DATABASE_URL=postgresql://postgres@127.0.0.1:5432/postgres
make test      # usa PASSWORD_SCRYPT_N=16384 e RATE_LIMIT_MULTIPLIER=1000 (apenas teste)
```
Detalhes dos testes: `docs/TESTING.md`. Variáveis: `.env.example`.

## Notas deste ambiente de construção (v0.7.0)
Não havia acesso a PyPI/npm: usaram-se pacotes pré-instalados nas versões pinadas; o typecheck rodou com `web/tsconfig.offline.json` (shims em `web/types/react`). **No seu ambiente use `tsconfig.json` com tipos oficiais.**
Sem Docker, Android SDK ou macOS: esses fluxos **não foram executados**.
