-- v0.22.0 — UMA trilha de execução de tarefa, com duração e erro.
--
-- O DEFEITO
--
-- Havia DUAS tabelas registrando a mesma coisa:
--
--   `job_runs`      — escrita por `impacto/jobs.py`, 22 tarefas, SEM duração e SEM campo de erro
--                     (o erro ia dentro de `details`, como texto, quando ia);
--   `ops_job_runs`  — escrita por `impacto/ops/runs.py`, 2 tarefas, COM duração, erro e detalhe.
--
-- Duas trilhas da mesma coisa não são redundância: são duas respostas diferentes para "o backup
-- rodou?". E a tabela que registrava 22 tarefas era justamente a que não sabia quanto tempo levou
-- nem por que falhou — então "rodou" era tudo que se podia saber das tarefas que importam.
--
-- A CORREÇÃO
--
-- Uma tabela (`ops_job_runs`), um gravador (`ops/runs.py::record`), o histórico da outra migrado
-- para dentro dela, e a tabela antiga removida — porque deixá-la vazia no esquema garante que
-- alguém volte a escrever nela em seis meses.

-- 1) 'running' passa a ser estado válido: a execução aberta não é "pulada".
ALTER TABLE ops_job_runs DROP CONSTRAINT IF EXISTS ops_job_runs_status_check;
ALTER TABLE ops_job_runs ADD CONSTRAINT ops_job_runs_status_check
  CHECK (status IN ('running', 'ok', 'failed', 'skipped', 'not_configured'));

-- 2) O histórico vem junto. A duração entra NULA de propósito: a tabela antiga não a media, e
--    inventar um número aqui seria fabricar medição retroativa.
INSERT INTO ops_job_runs(job, status, started_at, finished_at, duration_ms, detail, error)
SELECT j.job,
       CASE WHEN j.status = 'running' AND j.finished_at IS NULL THEN 'failed' ELSE j.status END,
       j.started_at, j.finished_at, NULL,
       coalesce(j.details, '{}'::jsonb) || jsonb_build_object('migrated_from', 'job_runs'),
       CASE WHEN j.status = 'failed' THEN left(coalesce(j.details->>'error', 'erro não registrado'), 2000)
            WHEN j.status = 'running' AND j.finished_at IS NULL
              THEN 'execução interrompida sem conclusão (migrada de job_runs)'
            ELSE NULL END
  FROM job_runs j
 WHERE j.job ~ '^[a-z0-9_]{2,40}$'
   AND NOT EXISTS (SELECT 1 FROM ops_job_runs o WHERE o.job = j.job AND o.started_at = j.started_at);

DROP TABLE IF EXISTS job_runs;

-- 3) Índice para a leitura que o painel de operações faz: a última execução de cada tarefa.
CREATE INDEX IF NOT EXISTS ix_ops_job_runs_job_recent ON ops_job_runs (job, started_at DESC);
