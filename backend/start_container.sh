#!/bin/sh
# Entrypoint do contêiner: bootstrap (opcional) → migrações → seed (só onde o produto permite) → ASGI.
#
# Veio de fora como parte de uma publicação no Supabase e entrou com três correções:
#   1. IMPACTO_APP_PASSWORD é OBRIGATÓRIA. A versão recebida, sem ela, reaproveitava a senha do
#      administrador para o papel da aplicação — o papel separado existe para que a aplicação NÃO
#      tenha a credencial administrativa; reusar a senha anula isso em silêncio.
#   2. O bootstrap do papel só roda quando IMPACTO_BOOTSTRAP_EXTERNAL=true (banco gerenciado onde o
#      infra/db/bootstrap.sql não pode rodar). No Compose o bootstrap é do próprio banco.
#   3. O seed não é decidido aqui: `impacto.cli seed-demo` recusa fora de development/test, e o
#      Dockerfile voltou a IMPACTO_ENV=production. Quem quiser demo sobe com IMPACTO_ENV=development
#      e aceita o que isso desliga — e isso fica escrito no log de inicialização.
set -eu

log() { printf '%s\n' "[impacto-start] $*"; }

: "${DATABASE_URL:?DATABASE_URL (conexão ADMINISTRATIVA, usada só para migrar) é obrigatória}"
: "${IMPACTO_APP_PASSWORD:?IMPACTO_APP_PASSWORD (senha do papel impacto_app) é obrigatória}"

if [ "${IMPACTO_BOOTSTRAP_EXTERNAL:-false}" = "true" ]; then
  log "bootstrap do papel impacto_app no banco gerenciado"
  python3 -m impacto.db.bootstrap_external
fi

log "migrações (como a conexão administrativa)"
if ! python3 -m impacto.db.migrate >/tmp/impacto-migrate.log 2>&1; then
  cat /tmp/impacto-migrate.log
  exit 1
fi
tail -n 3 /tmp/impacto-migrate.log || true
log "migrações concluídas"

# A aplicação NÃO roda com a conexão administrativa: troca o usuário da URL por impacto_app.
export DATABASE_URL="$(python3 - <<'PY'
import os
from urllib.parse import quote, urlsplit, urlunsplit
u = urlsplit(os.environ["DATABASE_URL"])
if not u.netloc or "@" not in u.netloc:
    raise SystemExit("DATABASE_URL precisa ser uma URI PostgreSQL com usuário e host")
host = u.netloc.rsplit("@", 1)[1]
netloc = "impacto_app:" + quote(os.environ["IMPACTO_APP_PASSWORD"], safe="") + "@" + host
print(urlunsplit((u.scheme, netloc, u.path, u.query, u.fragment)))
PY
)"
log "aplicação conectará como impacto_app"

if [ "${IMPACTO_SEED_DEMO:-false}" = "true" ]; then
  log "IMPACTO_SEED_DEMO=true: pedindo seed de demonstração (o produto recusa fora de development/test)"
  python3 -m impacto.cli seed-demo
fi

log "servidor ASGI em IMPACTO_ENV=${IMPACTO_ENV:-?}"
exec python3 -m uvicorn impacto.main:app --host 0.0.0.0 --port "${PORT}" \
  --proxy-headers --forwarded-allow-ips='*' --no-server-header --workers "${WEB_CONCURRENCY:-2}"
