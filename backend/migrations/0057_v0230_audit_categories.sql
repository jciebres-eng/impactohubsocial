-- v0.23.0 — CATEGORIA DE EVENTO COMO DADO, E PROTEÇÃO CONTRA TRUNCATE
--
-- POR QUE A CATEGORIA SAIU DO CÓDIGO PARA UMA TABELA
--
-- A migração 0056 derivava a categoria com um CASE sobre o prefixo da ação. Parecia suficiente: o
-- prompt pede nove categorias (AUTH, USERS, ORGS, DOCUMENTS, PROJECTS, WORKFLOWS, FINANCE, AI,
-- SECURITY) e o CASE cobria as nove. O teste mostrou o problema: a base tem 86 prefixos de ação e
-- 68 caíam em OTHER. Um filtro de categoria que joga 79% dos eventos em "outros" não é um filtro.
--
-- Com a tabela, a taxonomia é dado: revisável numa consulta, extensível por migração, e — o que
-- importa — CONFERÍVEL. `test_every_action_prefix_has_a_category` reprova se um domínio novo
-- aparecer no código sem categoria, em vez de deixá-lo cair em OTHER silenciosamente.

CREATE TABLE IF NOT EXISTS audit_action_categories (
  prefix   text PRIMARY KEY,
  category text NOT NULL,
  note     text
);

ALTER TABLE audit_action_categories DROP CONSTRAINT IF EXISTS audit_category_known;
ALTER TABLE audit_action_categories ADD CONSTRAINT audit_category_known CHECK (category IN (
  -- As nove do prompt
  'AUTH','USERS','ORGS','DOCUMENTS','PROJECTS','WORKFLOWS','FINANCE','AI','SECURITY',
  -- E as cinco que esta base tem de verdade. Forçar tudo nas nove colocaria "central de
  -- conhecimento" em DOCUMENTS e "integração de origem externa" em WORKFLOWS, o que faria o
  -- filtro devolver coisas que quem investiga não pediu.
  'CONTENT','NETWORK','ADMIN','INTEGRATIONS','OPS'));

INSERT INTO audit_action_categories (prefix, category, note) VALUES
  ('auth','AUTH','sessão, senha, MFA, OIDC'),
  ('identity','AUTH','verificação de identidade para operação sensível'),

  ('user','USERS',NULL),
  ('member','USERS','vínculo de pessoa com organização'),
  ('staff','USERS','papel interno da plataforma'),
  ('persona','USERS','perfil de uso declarado pela pessoa'),
  ('prefs','USERS','preferência de interface'),
  ('profile','USERS','perfil público'),

  ('org','ORGS',NULL),
  ('organization','ORGS',NULL),
  ('inst','ORGS','dados institucionais'),

  ('document','DOCUMENTS',NULL),
  ('document_assembly','DOCUMENTS','geração a partir de modelo'),
  ('document_template','DOCUMENTS',NULL),
  ('draft','DOCUMENTS','minuta assistida'),
  ('signature','DOCUMENTS',NULL),
  ('signature_policy','DOCUMENTS',NULL),
  ('signature_provider','DOCUMENTS',NULL),
  ('legal','DOCUMENTS','texto legal e aceite'),
  ('credential','DOCUMENTS','credencial profissional apresentada'),
  ('verifiable','DOCUMENTS','registro verificável publicamente'),
  ('material','DOCUMENTS','material de apoio anexado'),

  ('project','PROJECTS',NULL),
  ('indicator','PROJECTS',NULL),
  ('evidence','PROJECTS',NULL),
  ('diagnosis','PROJECTS',NULL),
  ('execution','PROJECTS',NULL),
  ('idea','PROJECTS','ideia antes de virar projeto'),
  ('need','PROJECTS','necessidade publicada'),
  ('territory_need','PROJECTS',NULL),
  ('impact_update','PROJECTS',NULL),
  ('impact_tag','PROJECTS',NULL),
  ('dataset','PROJECTS','base de referência usada em medição'),
  ('materiality','PROJECTS','matriz de materialidade'),
  ('graph','PROJECTS','grafo de impacto'),
  ('risk','PROJECTS',NULL),
  ('experience','PROJECTS','experiência confirmada em projeto'),

  ('application','WORKFLOWS',NULL),
  ('approval','WORKFLOWS',NULL),
  ('compliance','WORKFLOWS',NULL),
  ('call','WORKFLOWS','edital'),
  ('call_source','WORKFLOWS','origem de edital'),
  ('proposal','WORKFLOWS',NULL),
  ('agreement','WORKFLOWS',NULL),
  ('claim','WORKFLOWS','alegação sob verificação'),
  ('report','WORKFLOWS','denúncia e apuração'),
  ('review','WORKFLOWS',NULL),
  ('moderation','WORKFLOWS',NULL),
  ('enforcement','WORKFLOWS','medida aplicada'),
  ('procurement','WORKFLOWS',NULL),
  ('responsibility','WORKFLOWS',NULL),
  ('seal','WORKFLOWS','selo concedido ou revogado'),
  ('reputation','WORKFLOWS',NULL),
  ('trust','WORKFLOWS',NULL),
  ('match','WORKFLOWS','compatibilidade avaliada'),

  ('billing','FINANCE',NULL),
  ('payment','FINANCE',NULL),
  ('invoice','FINANCE',NULL),
  ('expense','FINANCE',NULL),
  ('instruction','FINANCE','instrução de pagamento (sem custódia)'),
  ('accounting','FINANCE',NULL),
  ('funding','FINANCE',NULL),
  ('refund','FINANCE',NULL),
  ('statement','FINANCE','extrato importado'),
  ('contribution_model','FINANCE',NULL),
  ('fee_table','FINANCE','tabela de honorários'),
  ('monetization','FINANCE',NULL),
  ('commercial','FINANCE',NULL),
  ('voucher','FINANCE',NULL),
  ('trial','FINANCE',NULL),
  ('quota','FINANCE',NULL),
  ('service','FINANCE','serviço contratado'),
  ('fiscal','FINANCE',NULL),

  ('ai','AI',NULL),

  ('security','SECURITY',NULL),
  ('audit','SECURITY',NULL),
  ('encryption','SECURITY',NULL),
  ('privacy','SECURITY','LGPD: exportação e apagamento a pedido do titular'),

  ('content','CONTENT',NULL),
  ('help','CONTENT','central de conhecimento'),
  ('kb','CONTENT',NULL),
  ('campaign','CONTENT',NULL),
  ('newsletter','CONTENT',NULL),
  ('demo','CONTENT','pedido de demonstração'),
  ('partnership','CONTENT',NULL),
  ('solution','CONTENT','catálogo de soluções'),
  ('support','CONTENT','atendimento'),
  ('program','CONTENT',NULL),

  ('listing','NETWORK','vitrine'),
  ('relationship','NETWORK',NULL),
  ('conversation','NETWORK',NULL),
  ('network','NETWORK',NULL),

  ('admin','ADMIN',NULL),
  ('internal','ADMIN','painéis da própria plataforma'),
  ('free_period','ADMIN','gratuidade concedida'),

  ('integration','INTEGRATIONS',NULL),
  ('import','INTEGRATIONS',NULL),
  ('export','INTEGRATIONS',NULL),

  ('job','OPS',NULL),
  ('worker','OPS',NULL),
  ('metric','OPS',NULL),
  ('alerts','OPS',NULL),
  ('error_event','OPS',NULL),
  ('notification','OPS',NULL),
  ('feedback','OPS',NULL),
  ('dispute','OPS',NULL),
  ('template','OPS',NULL),
  ('readiness','PROJECTS',NULL),
  ('value','PROJECTS','trilha de valor gerado'),
  ('equity','PROJECTS',NULL),
  ('framework','PROJECTS',NULL),
  ('territory','PROJECTS',NULL),
  ('teste','OPS','prefixo usado só por teste automatizado')
ON CONFLICT (prefix) DO UPDATE SET category = EXCLUDED.category, note = EXCLUDED.note;

CREATE OR REPLACE FUNCTION audit_category(p_action text) RETURNS text LANGUAGE sql STABLE AS $$
  SELECT coalesce((SELECT c.category FROM audit_action_categories c
                    WHERE c.prefix = split_part(p_action, '.', 1)), 'OTHER')
$$;

ALTER TABLE audit_action_categories ENABLE ROW LEVEL SECURITY;
CREATE POLICY auditcat_read ON audit_action_categories FOR SELECT
  USING (app_system() OR app_priv());
GRANT SELECT ON audit_action_categories TO impacto_app;

-- ── TRUNCATE ─────────────────────────────────────────────────────────────────────────────────────
--
-- `forbid_mutation` é um gatilho DE LINHA: protege UPDATE e DELETE e não vê TRUNCATE, que não
-- dispara gatilho de linha nenhum. Quem tiver privilégio de dono apagava a trilha inteira numa
-- instrução, sem quebrar hash nenhum porque não sobrava hash para quebrar. Gatilho de TRUNCATE é
-- a única forma de fechar essa porta dentro do banco.
CREATE OR REPLACE FUNCTION forbid_truncate() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION '% não aceita TRUNCATE: é uma trilha append-only', TG_TABLE_NAME
    USING ERRCODE = '42501',
          HINT = 'Retenção se aplica por recorte de data com DELETE autorizado, não apagando tudo.';
END $$;

DROP TRIGGER IF EXISTS trg_no_truncate_audit ON audit_events;
CREATE TRIGGER trg_no_truncate_audit BEFORE TRUNCATE ON audit_events
  FOR EACH STATEMENT EXECUTE FUNCTION forbid_truncate();

DROP TRIGGER IF EXISTS trg_no_truncate_ledger ON ledger_entries;
CREATE TRIGGER trg_no_truncate_ledger BEFORE TRUNCATE ON ledger_entries
  FOR EACH STATEMENT EXECUTE FUNCTION forbid_truncate();

DROP TRIGGER IF EXISTS trg_no_truncate_value ON value_events;
CREATE TRIGGER trg_no_truncate_value BEFORE TRUNCATE ON value_events
  FOR EACH STATEMENT EXECUTE FUNCTION forbid_truncate();

DROP TRIGGER IF EXISTS trg_no_truncate_kill_switch ON kill_switch_events;
CREATE TRIGGER trg_no_truncate_kill_switch BEFORE TRUNCATE ON kill_switch_events
  FOR EACH STATEMENT EXECUTE FUNCTION forbid_truncate();

DROP TRIGGER IF EXISTS trg_no_truncate_privileged ON privileged_access_log;
CREATE TRIGGER trg_no_truncate_privileged BEFORE TRUNCATE ON privileged_access_log
  FOR EACH STATEMENT EXECUTE FUNCTION forbid_truncate();
