#!/usr/bin/env bash
# Teste de restauração em banco DESCARTÁVEL: verifica hash, restaura, confere migrations e a integridade das cadeias de hash.
# Uso: ADMIN_DATABASE_URL=postgresql://postgres@host/postgres scripts/restore_test.sh backups/impacto-....dump
set -euo pipefail
: "${ADMIN_DATABASE_URL:?defina ADMIN_DATABASE_URL}"; F="$1"
sha256sum -c "$F.sha256"
DB="impacto_restore_$(date +%s)"
psql "$ADMIN_DATABASE_URL" -v ON_ERROR_STOP=1 -q -c "CREATE DATABASE $DB OWNER impacto_owner"
TARGET="${ADMIN_DATABASE_URL%/*}/$DB"
pg_restore --no-owner --role=impacto_owner -d "$TARGET" "$F"
psql "$TARGET" -tA -c "SELECT count(*) || ' migrations' FROM schema_migrations"
BROKEN=$(psql "$TARGET" -v ON_ERROR_STOP=1 -tA -c "SELECT p.id FROM projects p CROSS JOIN LATERAL ledger_verify(p.id) v WHERE NOT v.valid")
AUDIT=$(psql "$TARGET" -v ON_ERROR_STOP=1 -tA -c "SELECT count(*) FROM (SELECT DISTINCT org_id FROM audit_events) o CROSS JOIN LATERAL audit_verify(o.org_id) v WHERE NOT v.valid")
if [ -n "$BROKEN" ] || [ "$AUDIT" != "0" ]; then echo "FALHA: cadeia de hash inconsistente ($BROKEN / audit=$AUDIT)"; exit 1; fi
echo "ledger e auditoria íntegros"

# v0.17.0: um restore que ligasse uma receita ou aprovasse uma minuta em silêncio seria pior que um
# restore que falha. Então o estado DESLIGADO também é conferido — é parte da integridade.
ACTIVE=$(psql "$TARGET" -v ON_ERROR_STOP=1 -tA -c "SELECT count(*) FROM monetization_rules WHERE active")
GREEN=$(psql "$TARGET" -v ON_ERROR_STOP=1 -tA -c "SELECT count(*) FROM monetization_legal_cards WHERE status = 'green'")
APPROVED=$(psql "$TARGET" -v ON_ERROR_STOP=1 -tA -c "SELECT count(*) FROM legal_documents WHERE status = 'approved'")
REALCHARGE=$(psql "$TARGET" -v ON_ERROR_STOP=1 -tA -c "SELECT count(*) FROM platform_charges WHERE NOT is_simulated")
BASELINE=$(psql "$TARGET" -v ON_ERROR_STOP=1 -tA -c "SELECT count(*) FROM value_baselines WHERE minutes_per_unit IS NOT NULL AND source_name IS NULL")
if [ "$ACTIVE" != "0" ] || [ "$GREEN" != "0" ] || [ "$APPROVED" != "0" ] || [ "$REALCHARGE" != "0" ] || [ "$BASELINE" != "0" ]; then
  echo "FALHA: o restore trouxe estado que não deveria existir (regra ativa=$ACTIVE, cartão verde=$GREEN, minuta aprovada=$APPROVED, cobrança real=$REALCHARGE, linha de base sem fonte=$BASELINE)"
  exit 1
fi
echo "camada econômica restaurada DESLIGADA: nenhuma receita ativa, nenhum cartão verde, nenhuma minuta aprovada, nenhuma cobrança real"

# v0.18.0: a mesma lógica aplicada à camada de impacto. Um restore que trouxesse denominador sem
# fonte, selo concedido sem evidência ou linha de base sem fonte apagaria em silêncio travas que o
# produto aplica em tempo de escrita — e a restauração é exatamente o momento em que ninguém olha.
DENOM=$(psql "$TARGET" -v ON_ERROR_STOP=1 -tA -c "SELECT count(*) FROM equity_denominators WHERE source_name IS NULL OR source_date IS NULL OR method_note IS NULL")
SEALNOEV=$(psql "$TARGET" -v ON_ERROR_STOP=1 -tA -c "SELECT count(*) FROM seal_awards WHERE jsonb_array_length(evidence) = 0")
SEALDRAFT=$(psql "$TARGET" -v ON_ERROR_STOP=1 -tA -c "SELECT count(*) FROM seal_awards a JOIN seal_definitions d ON d.id = a.definition_id WHERE d.status = 'draft'")
BASENOSRC=$(psql "$TARGET" -v ON_ERROR_STOP=1 -tA -c "SELECT count(*) FROM project_indicators WHERE baseline IS NOT NULL AND baseline_source IS NULL")
REPNOOBS=$(psql "$TARGET" -v ON_ERROR_STOP=1 -tA -c "SELECT count(*) FROM reputation_snapshots WHERE value IS NOT NULL AND observations = 0")
CERTREL=$(psql "$TARGET" -v ON_ERROR_STOP=1 -tA -c "SELECT count(*) FROM framework_mappings WHERE relation NOT IN ('aligned','mapped','assessed','reported','verified','audited')")
if [ "$DENOM" != "0" ] || [ "$SEALNOEV" != "0" ] || [ "$SEALDRAFT" != "0" ] || [ "$BASENOSRC" != "0" ] || [ "$REPNOOBS" != "0" ] || [ "$CERTREL" != "0" ]; then
  echo "FALHA: o restore trouxe estado que as travas da v0.18.0 recusariam (denominador sem fonte=$DENOM, selo sem evidência=$SEALNOEV, selo de rascunho=$SEALDRAFT, linha de base sem fonte=$BASENOSRC, reputação sem observação=$REPNOOBS, relação fora da escada=$CERTREL)"
  exit 1
fi
echo "camada de impacto restaurada ÍNTEGRA: nenhum denominador sem fonte, nenhum selo sem evidência ou de rascunho, nenhuma linha de base sem fonte, nenhuma reputação sem observação, nenhuma relação fora da escada"

# v0.19.0: a restauração precisa trazer de volta a camada de OPERAÇÃO. Um restore sem ops_job_runs
# deixaria a plataforma sem a resposta para "quando foi o último backup?" exatamente depois de um
# incidente — o momento em que a pergunta mais importa. E o vocabulário de e-mail é conferido aqui
# também: um banco restaurado não pode passar a aceitar um estado chamado "entrega", que a
# plataforma não sabe afirmar.
OPSJOBS=$(psql "$TARGET" -v ON_ERROR_STOP=1 -tA -c "SELECT count(*) FROM pg_tables WHERE schemaname='public' AND tablename IN ('ops_job_runs','email_events')")
MAILDELIV=$(psql "$TARGET" -v ON_ERROR_STOP=1 -tA -c "SELECT count(*) FROM pg_constraint WHERE conrelid='email_events'::regclass AND pg_get_constraintdef(oid) LIKE '%delivered%'")
MAILADDR=$(psql "$TARGET" -v ON_ERROR_STOP=1 -tA -c "SELECT count(*) FROM email_events WHERE to_domain LIKE '%@%'")
GLOSS=$(psql "$TARGET" -v ON_ERROR_STOP=1 -tA -c "SELECT count(DISTINCT namespace) FROM translations WHERE namespace LIKE 'g\\_%'")
if [ "$OPSJOBS" != "2" ] || [ "$MAILDELIV" != "0" ] || [ "$MAILADDR" != "0" ] || [ "$GLOSS" -lt "20" ]; then
  echo "FALHA: a restauração não trouxe a camada de operação íntegra (tabelas de operação=$OPSJOBS de 2, estado 'delivered' no banco=$MAILDELIV, endereço de e-mail guardado=$MAILADDR, namespaces de glossário=$GLOSS)"
  exit 1
fi
echo "camada de operação restaurada ÍNTEGRA: $GLOSS namespaces de glossário, registro de tarefa e de e-mail presentes, nenhum endereço guardado, nenhum estado de entrega inventado"
psql "$ADMIN_DATABASE_URL" -q -c "DROP DATABASE $DB WITH (FORCE)"
echo "restore OK"
