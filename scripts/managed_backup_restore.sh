#!/usr/bin/env bash
# Ciclo REAL de backup e restauração de um PostgreSQL gerenciado (Supabase) — v0.31.0.
#
# O que faz, nesta ordem, e o que NÃO faz:
#   1. pg_dump SOMENTE do schema `public` (o do IMPACTO). Os schemas internos do Supabase (auth, storage,
#      realtime, vault…) não são do produto e não restauram num PostgreSQL comum. Leitura apenas: o
#      dump não escreve na origem.
#   2. Prepara um PostgreSQL DESCARTÁVEL (nunca o de origem): papéis impacto_owner/impacto_app e o
#      pgcrypto no mesmo schema em que está na origem (no Supabase, `extensions`).
#   3. Restaura com scripts/restore_test.sh — o MESMO verificador do CI: hash do dump, cadeias de hash
#      (ledger e auditoria), camada econômica desligada, travas de impacto, camada de operação.
#   4. Compara a contagem de linhas de TODA tabela da origem com a restaurada.
#   5. Apaga o dump. Nenhum arquivo sai daqui: a origem pode ter dado pessoal real.
# Mede o tempo de cada etapa (base do RTO medido). Nunca imprime URL, senha ou conteúdo de linha.
#
# Uso: SOURCE_DATABASE_URL=… TARGET_ADMIN_URL=postgresql://postgres:…@localhost:5432/postgres \
#        bash scripts/managed_backup_restore.sh
#
# v0.32.0 — DUMP_FILE=<arquivo .dump já existente> (p.ex. o backup diário decifrado, baixado do R2): não faz
# dump; restaura ESSE arquivo. A origem continua sendo lida (só leitura) para saber em que schema estão as
# extensões e quais tabelas existem; as CONTAGENS de linhas não são comparadas (o banco mudou desde o
# backup) — compara-se o CONJUNTO de tabelas, e os verificadores de integridade rodam do mesmo jeito.
set -euo pipefail
: "${SOURCE_DATABASE_URL:?SOURCE_DATABASE_URL (origem, só leitura) é obrigatória}"
: "${TARGET_ADMIN_URL:?TARGET_ADMIN_URL (PostgreSQL DESCARTÁVEL) é obrigatória}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
log() { printf '%s\n' "[backup-restore] $*"; }
agora() { date +%s.%N; }
dur() { python3 -c "print(f'{float(\"$2\") - float(\"$1\"):.1f}')"; }

src_host=$(python3 -c "import os,urllib.parse as u; print(u.urlsplit(os.environ['SOURCE_DATABASE_URL']).hostname or '')")
tgt_host=$(python3 -c "import os,urllib.parse as u; print(u.urlsplit(os.environ['TARGET_ADMIN_URL']).hostname or '')")
if [ "$src_host" = "$tgt_host" ] && [ "${ALLOW_SAME_HOST:-false}" != "true" ]; then
  echo "RECUSADO: origem e destino no mesmo host — a restauração nunca roda por cima da origem"; exit 2
fi

log "versões: pg_dump $(pg_dump --version | awk '{print $3}') · origem $(psql "$SOURCE_DATABASE_URL" -tAc 'SHOW server_version' | awk '{print $1}') · destino $(psql "$TARGET_ADMIN_URL" -tAc 'SHOW server_version' | awk '{print $1}')"
# Extensões que os objetos de `public` usam e que um PostgreSQL comum tem (contrib). As do próprio
# Supabase (pg_graphql, pg_net, vault…) não são do produto e ficam de fora. Cada uma é recriada no
# destino NO MESMO schema da origem — o dump referencia `extensions.digest`, `public.citext` etc.
EXT_PERMITIDAS="'pgcrypto','citext','unaccent','pg_trgm'"
EXTS=$(psql "$SOURCE_DATABASE_URL" -tAc "SELECT string_agg(e.extname || ':' || n.nspname, ' ') FROM pg_extension e JOIN pg_namespace n ON n.oid=e.extnamespace WHERE e.extname IN ($EXT_PERMITIDAS)")
log "extensões do produto na origem: ${EXTS:-nenhuma}"

# Contagem de linhas da origem, em transação READ ONLY (o servidor recusa qualquer escrita).
contar() {
  psql "$1" -v ON_ERROR_STOP=1 -tA <<'SQL'
BEGIN TRANSACTION READ ONLY;
SELECT string_agg(format('%s=%s', c.relname,
         (xpath('/row/n/text()', query_to_xml(format('SELECT count(*) AS n FROM public.%I', c.relname), false, true, '')))[1]::text),
       E'\n' ORDER BY c.relname)
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p');
ROLLBACK;
SQL
}
contar "$SOURCE_DATABASE_URL" | sed '/^$/d;/^BEGIN$/d;/^ROLLBACK$/d' > "$WORK/origem.txt"
log "origem: $(wc -l < "$WORK/origem.txt") tabelas em public"

t0=$(agora)
F="$WORK/impacto-managed.dump"
if [ -n "${DUMP_FILE:-}" ]; then
  cp "$DUMP_FILE" "$F"
  log "restaurando arquivo existente (DUMP_FILE): $(du -h "$F" | cut -f1)"
else
  pg_dump --format=custom --schema=public --no-owner --no-privileges "$SOURCE_DATABASE_URL" -f "$F"
fi
sha256sum "$F" > "$F.sha256"
t1=$(agora)
log "dump: $(du -h "$F" | cut -f1) em $(dur "$t0" "$t1") s (sha256 $(cut -c1-16 "$F.sha256")…)"

# Destino descartável: papéis (sem senha: o restore usa SET ROLE pela conexão administrativa) e a
# extensão onde a origem a tem. Em template1, para o banco que o
# restore_test.sh cria já nascer com eles.
psql "$TARGET_ADMIN_URL" -v ON_ERROR_STOP=1 -q <<SQL
DO \$\$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'impacto_owner') THEN CREATE ROLE impacto_owner NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'impacto_app') THEN CREATE ROLE impacto_app NOLOGIN; END IF;
END \$\$;
SQL
TEMPLATE_URL="${TARGET_ADMIN_URL%/*}/template1"
for par in $EXTS; do
  ext="${par%%:*}"; sch="${par##*:}"
  psql "$TEMPLATE_URL" -v ON_ERROR_STOP=1 -q -c "CREATE SCHEMA IF NOT EXISTS $sch" \
    -c "CREATE EXTENSION IF NOT EXISTS $ext WITH SCHEMA $sch" -c "GRANT USAGE ON SCHEMA $sch TO PUBLIC"
done
# O dump de `public` traz `CREATE SCHEMA public`, que colide com o schema que todo banco já tem (e
# onde as extensões acima já estão). A lista de restauração pula só essa entrada e o comentário dela.
pg_restore -l "$F" | grep -vE ' SCHEMA - public |COMMENT - SCHEMA public' > "$WORK/lista.toc"

t2=$(agora)
ADMIN_DATABASE_URL="$TARGET_ADMIN_URL" RESTORE_KEEP_DB=1 RESTORE_TOC_LIST="$WORK/lista.toc" RESTORE_DB_NAME_FILE="$WORK/db.txt" \
  bash "$ROOT/scripts/restore_test.sh" "$F"
t3=$(agora)
DB=$(cat "$WORK/db.txt")
log "restauração + verificações: $(dur "$t2" "$t3") s"

contar "${TARGET_ADMIN_URL%/*}/$DB" | sed '/^$/d;/^BEGIN$/d;/^ROLLBACK$/d' > "$WORK/destino.txt"
psql "$TARGET_ADMIN_URL" -q -c "DROP DATABASE $DB WITH (FORCE)"
if [ -n "${DUMP_FILE:-}" ]; then
  cut -d= -f1 "$WORK/origem.txt" > "$WORK/origem.tabelas"; cut -d= -f1 "$WORK/destino.txt" > "$WORK/destino.tabelas"
  if diff -q "$WORK/origem.tabelas" "$WORK/destino.tabelas" >/dev/null; then
    total=$(awk -F= '{s+=$2} END {print s}' "$WORK/destino.txt")
    log "tabelas: $(wc -l < "$WORK/destino.tabelas") — o MESMO conjunto da origem; $total linhas restauradas (contagens não comparadas: o banco mudou desde o backup)"
  else
    log "FALHA: conjunto de tabelas diferente (< origem | > restaurado):"
    diff "$WORK/origem.tabelas" "$WORK/destino.tabelas" | grep '^[<>]' | head -20
    exit 1
  fi
elif diff -q "$WORK/origem.txt" "$WORK/destino.txt" >/dev/null; then
  total=$(awk -F= '{s+=$2} END {print s}' "$WORK/origem.txt")
  log "contagens: $(wc -l < "$WORK/origem.txt") tabelas, $total linhas — IDÊNTICAS entre origem e restauração"
else
  log "FALHA: contagens diferentes (tabela=origem | tabela=restaurado):"
  diff "$WORK/origem.txt" "$WORK/destino.txt" | grep '^[<>]' | head -20
  exit 1
fi
log "RTO medido (dump + restauração verificada): $(dur "$t0" "$t3") s · dump apagado, nenhum arquivo exportado"
echo "BACKUP_RESTORE_OK"
