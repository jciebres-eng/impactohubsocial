-- v0.19.0 — observabilidade operacional: execução de tarefa e evento de e-mail.
--
-- POR QUE ISTO EXISTE. Duas lacunas reais de publicação, as duas do mesmo tipo: a plataforma fazia (ou
-- deixava de fazer) algo importante e ninguém tinha como saber.
--
-- 1. BACKUP. `scripts/backup.sh` existia e a restauração era testada, mas NADA agendava a execução —
--    nenhum cron, nenhum serviço, nenhum passo de CI. Script que ninguém executa não é backup.
-- 2. E-MAIL. O cadastro depende do e-mail de verificação. Com falha silenciosa de SMTP, o funil vai a
--    zero e a primeira pessoa a descobrir é quem não conseguiu entrar.
--
-- A resposta das duas é a mesma: registrar a execução, com resultado, e deixar o alerta olhar para o
-- registro. Sem tabela, "o backup rodou ontem?" é uma pergunta sem resposta.

-- ============================================================ execução de tarefa operacional
CREATE TABLE ops_job_runs (
  id          bigserial PRIMARY KEY,
  job         text NOT NULL CHECK (job ~ '^[a-z0-9_]{2,40}$'),
  status      text NOT NULL CHECK (status IN ('ok','failed','skipped','not_configured')),
  started_at  timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz,
  duration_ms integer CHECK (duration_ms IS NULL OR duration_ms >= 0),
  detail      jsonb NOT NULL DEFAULT '{}'::jsonb,
  error       text CHECK (error IS NULL OR length(error) <= 2000)
);
COMMENT ON TABLE ops_job_runs IS
  'Trilha de execução das tarefas operacionais (backup, canário de e-mail). O status not_configured é '
  'tão importante quanto failed: ele diz que a tarefa NÃO rodou por falta de configuração, em vez de '
  'deixar a ausência de linha parecer sucesso.';
COMMENT ON COLUMN ops_job_runs.status IS
  'ok | failed | skipped (não estava na hora) | not_configured (falta credencial ou destino — '
  'dependência externa, não defeito de código)';

CREATE INDEX ix_ops_job_runs_job_at ON ops_job_runs (job, started_at DESC);

ALTER TABLE ops_job_runs ENABLE ROW LEVEL SECURITY;
-- Só a administração da plataforma lê: é dado de operação, não de organização.
CREATE POLICY ops_job_runs_read ON ops_job_runs FOR SELECT USING (app_priv() OR app_system());
CREATE POLICY ops_job_runs_write ON ops_job_runs FOR INSERT WITH CHECK (app_system());
CREATE POLICY ops_job_runs_finish ON ops_job_runs FOR UPDATE USING (app_system()) WITH CHECK (app_system());
GRANT SELECT, INSERT, UPDATE ON ops_job_runs TO impacto_app;
GRANT USAGE ON SEQUENCE ops_job_runs_id_seq TO impacto_app;

-- ============================================================ evento de e-mail
-- Guarda o DOMÍNIO, nunca o endereço: para responder "o provedor está aceitando nossas mensagens?"
-- o domínio basta, e endereço é dado pessoal que não precisa estar aqui.
CREATE TABLE email_events (
  id          bigserial PRIMARY KEY,
  message_id  text CHECK (message_id IS NULL OR length(message_id) <= 200),
  kind        text NOT NULL CHECK (kind ~ '^[a-z0-9_]{2,40}$'),
  to_domain   text NOT NULL CHECK (length(to_domain) BETWEEN 1 AND 255),
  status      text NOT NULL CHECK (status IN ('accepted_by_smtp','written_to_outbox','failed')),
  provider    text NOT NULL CHECK (provider IN ('smtp','console')),
  retry_count smallint NOT NULL DEFAULT 0 CHECK (retry_count BETWEEN 0 AND 10),
  duration_ms integer CHECK (duration_ms IS NULL OR duration_ms >= 0),
  error       text CHECK (error IS NULL OR length(error) <= 1000),
  at          timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE email_events IS
  'Um registro por tentativa de envio. Guarda domínio do destinatário, nunca o endereço nem o corpo.';
COMMENT ON COLUMN email_events.status IS
  'accepted_by_smtp = o servidor ACEITOU a mensagem. NÃO é entrega: entrega só se afirma com retorno '
  'do provedor (webhook de bounce/delivery), que esta plataforma ainda não recebe. '
  'written_to_outbox = ambiente de desenvolvimento/teste, nada foi enviado.';

CREATE INDEX ix_email_events_at ON email_events (at DESC);
CREATE INDEX ix_email_events_kind_status ON email_events (kind, status, at DESC);

ALTER TABLE email_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY email_events_read ON email_events FOR SELECT USING (app_priv() OR app_system());
CREATE POLICY email_events_write ON email_events FOR INSERT WITH CHECK (app_system());
GRANT SELECT, INSERT ON email_events TO impacto_app;
GRANT USAGE ON SEQUENCE email_events_id_seq TO impacto_app;
