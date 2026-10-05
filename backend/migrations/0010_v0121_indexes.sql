-- 0010_v0121_indexes.sql — índices de cobertura para consultas reais da Central de Conhecimento e do CRM.
-- Motivo: a auditoria da baseline técnica encontrou consultas que filtram tabelas de CRESCIMENTO por coluna
-- sem índice líder (varredura sequencial à medida que a tabela cresce). Cada índice abaixo cita a consulta que o justifica.
-- Forward-only: a 0009 já foi liberada e NÃO é editada (ver VERSIONING.md). Nenhuma alteração de dados, RLS ou contrato.

-- content_admin_routes.course_list: "(SELECT count(*) FROM course_enrollments e WHERE e.course_id = k.id)"
-- e a contagem de conclusões; a chave primária é (user_id, course_id), logo course_id não é coluna líder.
CREATE INDEX IF NOT EXISTS ix_course_enroll_course ON course_enrollments (course_id);

-- content_admin_routes.partnership_get: "FROM partnership_activities WHERE request_id = $1 ORDER BY created_at"
-- (a própria política RLS de leitura também filtra por request_id). Não havia nenhum índice sobre request_id.
CREATE INDEX IF NOT EXISTS ix_partnership_act_request ON partnership_activities (request_id, created_at);

-- knowledge_routes.trial_requests_mine: "WHERE org_id = $1 ORDER BY created_at DESC"
-- (o índice existente ux_trial_requests_open é parcial: só status = 'requested').
CREATE INDEX IF NOT EXISTS ix_trial_requests_org ON trial_requests (org_id, created_at DESC);

-- hub.my_activities ("Minhas atividades", carregada a cada visita à Central): três listas por user_id.
CREATE INDEX IF NOT EXISTS ix_trial_requests_user ON trial_requests (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_partnership_req_user ON partnership_requests (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_demo_requests_user ON demo_requests (user_id, created_at DESC);
