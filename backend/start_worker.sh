#!/bin/sh
# Entrypoint do WORKER (v0.31.0): as tarefas periódicas de `impacto.jobs` (antivírus pendente, prazos,
# retenção LGPD, canário de e-mail, backup lógico, expirações, selos…) num serviço separado da API.
#
# Mesma imagem da API, outro comando (no Railway: serviço "worker" com Start Command
# `sh /app/start_worker.sh`). Diferenças deliberadas em relação a start_container.sh:
#   - NÃO migra e NÃO faz bootstrap: migrar é da API (um único dono do esquema, com lock consultivo).
#     O worker ESPERA o esquema ficar em dia (`migrate --check`, somente leitura) — subir antes da API
#     num deploy rodaria tarefas contra um esquema velho.
#   - NÃO rotaciona a senha de impacto_app: dois serviços rotacionando a mesma senha derrubam um ao outro.
#   - Roda como impacto_app (menor privilégio), igual à API.
# Rodar duas réplicas é inofensivo: `jobs.run_once` pega um lock consultivo e a segunda pula a rodada.
set -eu

log() { printf '%s\n' "[impacto-worker] $*"; }

: "${DATABASE_URL:?DATABASE_URL (conexão ADMINISTRATIVA, só para conferir o esquema) é obrigatória}"
: "${IMPACTO_APP_PASSWORD:?IMPACTO_APP_PASSWORD (senha do papel impacto_app) é obrigatória}"

tentativas="${WORKER_SCHEMA_WAIT_TRIES:-60}"
i=0
until python3 -m impacto.db.migrate --check >/tmp/impacto-schema.json 2>&1; do
  i=$((i + 1))
  if [ "$i" -ge "$tentativas" ]; then
    log "esquema ainda com migrações pendentes depois de $tentativas tentativas — saindo para o orquestrador reiniciar"
    cat /tmp/impacto-schema.json
    exit 1
  fi
  log "esquema com migrações pendentes (a API migra no deploy); nova conferência em 10 s ($i/$tentativas)"
  sleep 10
done
log "esquema em dia"

export DATABASE_URL="$(python3 -m impacto.db.app_url)"
log "worker conectará como impacto_app; intervalo ${JOBS_INTERVAL_SECONDS:-900} s"
exec python3 -m impacto.jobs loop
