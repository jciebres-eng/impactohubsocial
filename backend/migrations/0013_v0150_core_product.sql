-- 0013 — v0.15.0: NÚCLEO DO PRODUTO. Fecha as lacunas da auditoria PRE_DESIGN_AUDIT.md antes da camada de design.
-- CONSOLIDA (não duplica): `sdg_goals` criada na 0012 é REMOVIDA e `ods_goals` (que existe desde a 0001 e é referenciada
-- por indicator_catalog e ods_targets) ganha as colunas que faltavam. Duas fontes de verdade para ODS era defeito meu.
-- REUTILIZA: ledger_entries (append-only encadeada por hash) para a linha de tempo do projeto · application_transitions
-- como modelo da máquina de estados · indicator_catalog/project_indicators/indicator_values · documents e drafts ·
-- FieldCipher (MultiFernet) · guard_columns/forbid_mutation/touch_updated_at · RLS por organização.
-- PRINCÍPIOS: histórico nunca é sobrescrito (versão nova, nunca edição silenciosa) · elegibilidade nunca é compensada
-- por pontuação · declaração não é evidência verificada · provedor externo ausente produz indisponibilidade explícita.

-- ================================================================================================ 1. CONSOLIDAÇÃO ODS
ALTER TABLE ods_goals ADD COLUMN code text CHECK (code ~ '^ODS[0-9]{1,2}$');
ALTER TABLE ods_goals ADD COLUMN name_en text;
ALTER TABLE ods_goals ADD COLUMN color_hex char(7) CHECK (color_hex ~ '^#[0-9A-F]{6}$');
ALTER TABLE ods_goals ADD COLUMN active boolean NOT NULL DEFAULT true;
UPDATE ods_goals g SET code = s.code, name_en = s.name_en, color_hex = s.color_hex
  FROM sdg_goals s WHERE s.number = g.number;
ALTER TABLE ods_goals ALTER COLUMN code SET NOT NULL;
ALTER TABLE ods_goals ADD CONSTRAINT ods_goals_code_key UNIQUE (code);
DROP TABLE sdg_goals;   -- a validação de impact_tags passa a olhar ods_goals (gatilho recriado na seção 13)

-- ================================================================================================ 2. IDEIA → PROJETO
-- A ideia NUNCA é apagada quando vira projeto: o projeto guarda origin_idea_id e a ideia guarda promoted_project_id.
CREATE TABLE ideas (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  title         text NOT NULL CHECK (length(title) BETWEEN 3 AND 200),
  problem       text CHECK (length(problem) <= 6000),
  hypothesis    text CHECK (length(hypothesis) <= 4000),
  audience      text CHECK (length(audience) <= 2000),     -- descrição agregada; sem dado pessoal
  territory     text CHECK (length(territory) <= 200),
  solution_idea text CHECK (length(solution_idea) <= 6000),
  expected_impact text CHECK (length(expected_impact) <= 4000),
  stage         text NOT NULL DEFAULT 'raw' CHECK (stage IN ('raw','shaping','ready','promoted','archived')),
  causes        text[] NOT NULL DEFAULT '{}',
  ods           smallint[] NOT NULL DEFAULT '{}',
  promoted_project_id uuid REFERENCES projects(id) ON DELETE SET NULL,
  promoted_at   timestamptz,
  owner_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  created_by    uuid REFERENCES users(id),
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  CHECK ((stage = 'promoted') = (promoted_project_id IS NOT NULL))
);
CREATE INDEX ix_ideas_org ON ideas(org_id, stage, created_at DESC);
ALTER TABLE projects ADD COLUMN origin_idea_id uuid REFERENCES ideas(id) ON DELETE SET NULL;

-- ================================================================================================ 3. CICLO DE VIDA DO PROJETO
-- `projects.status` tinha 7 valores e era alterado por UPDATE solto. Agora existe máquina de estados com transições
-- registradas (append-only) e um gatilho que RECUSA transição fora da máquina.
ALTER TABLE projects DROP CONSTRAINT projects_status_check;
ALTER TABLE projects ADD CONSTRAINT projects_status_check CHECK (status IN (
  'draft','diagnosing','structuring','ready','published','funding','funded','submitted','approved',
  'in_execution','monitoring','completed','archived','blocked','paused','cancelled','rejected'));

CREATE TABLE project_transitions (
  id            bigserial PRIMARY KEY,
  project_id    uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  from_status   text NOT NULL,
  to_status     text NOT NULL,
  actor_user_id uuid REFERENCES users(id),
  actor_org_id  uuid REFERENCES organizations(id),
  reason        text CHECK (length(reason) <= 2000),
  evidence_document_id uuid REFERENCES documents(id) ON DELETE SET NULL,
  automatic     boolean NOT NULL DEFAULT false,   -- true quando o próprio sistema moveu (ex.: candidatura aprovada)
  at            timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_ptrans_project ON project_transitions(project_id, at DESC);

-- Máquina de estados como DADO (não como código espalhado): o gatilho consulta esta tabela.
CREATE TABLE project_status_graph (
  from_status  text NOT NULL,
  to_status    text NOT NULL,
  requires_reason boolean NOT NULL DEFAULT false,
  note         text,
  PRIMARY KEY (from_status, to_status)
);
INSERT INTO project_status_graph(from_status, to_status, requires_reason, note) VALUES
 -- TRANSIÇÕES QUE O PRODUTO JÁ FAZIA desde a v0.7.0 (compatibilidade: a máquina não pode quebrar o que funciona).
 -- O caminho rico (diagnosing/structuring/ready/submitted/approved/monitoring) é o NOVO, pela API de ciclo de vida.
 ('draft','published', false, 'publicação direta (caminho legado: POST /v1/projects/{id}/publish)'),
 ('published','draft', false, 'despublicação (caminho legado)'),
 ('published','funded', false, 'aporte cobriu o orçamento de uma vez'),
 ('funding','in_execution', false, 'execução iniciada pelo fluxo de candidatura'),
 ('funded','completed', false, 'conclusão sem etapa de execução registrada'),
 ('in_execution','archived', false, NULL),
 ('draft','diagnosing', false, 'começa o diagnóstico'),
 ('draft','structuring', false, 'estrutura direto, sem diagnóstico guiado'),
 ('draft','cancelled', true, NULL),
 ('diagnosing','structuring', false, 'diagnóstico suficiente para estruturar'),
 ('diagnosing','draft', false, 'volta para revisão'),
 ('diagnosing','cancelled', true, NULL),
 ('structuring','ready', false, 'estrutura mínima completa'),
 ('structuring','diagnosing', false, 'faltou diagnóstico'),
 ('structuring','blocked', true, NULL),
 ('structuring','cancelled', true, NULL),
 ('ready','published', false, 'publicado para captação'),
 ('ready','submitted', false, 'submetido a um edital'),
 ('ready','structuring', false, 'voltou para ajuste'),
 ('ready','blocked', true, NULL),
 ('ready','cancelled', true, NULL),
 ('published','funding', false, 'recebeu interesse/aporte'),
 ('published','submitted', false, NULL),
 ('published','ready', false, 'despublicado'),
 ('published','cancelled', true, NULL),
 ('funding','funded', false, 'captação concluída'),
 ('funding','published', false, NULL),
 ('funding','blocked', true, NULL),
 ('funding','cancelled', true, NULL),
 ('submitted','approved', false, NULL),
 ('submitted','rejected', true, NULL),
 ('submitted','ready', false, 'retirou a submissão'),
 ('approved','funded', false, NULL),
 ('approved','in_execution', false, NULL),
 ('funded','in_execution', false, 'execução iniciada'),
 ('funded','blocked', true, NULL),
 ('funded','cancelled', true, NULL),
 ('in_execution','monitoring', false, 'entrou em acompanhamento'),
 ('in_execution','paused', true, NULL),
 ('in_execution','blocked', true, NULL),
 ('in_execution','completed', false, NULL),
 ('monitoring','in_execution', false, NULL),
 ('monitoring','completed', false, NULL),
 ('monitoring','paused', true, NULL),
 ('monitoring','blocked', true, NULL),
 ('paused','in_execution', false, NULL),
 ('paused','monitoring', false, NULL),
 ('paused','cancelled', true, NULL),
 ('blocked','structuring', false, 'bloqueio resolvido'),
 ('blocked','ready', false, NULL),
 ('blocked','in_execution', false, NULL),
 ('blocked','cancelled', true, NULL),
 ('completed','archived', false, NULL),
 ('completed','monitoring', false, 'reabre acompanhamento de legado'),
 ('rejected','structuring', false, 'vai ajustar e tentar de novo'),
 ('rejected','archived', false, NULL),
 ('cancelled','archived', false, NULL),
 ('archived','monitoring', false, 'reabertura excepcional');

-- O gatilho recusa transição que não existe no grafo. `app_priv()` NÃO libera: a máquina vale para todos, porque o
-- objetivo é integridade do histórico, não permissão.
CREATE FUNCTION project_status_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.status = OLD.status THEN RETURN NEW; END IF;
  IF NOT EXISTS (SELECT 1 FROM project_status_graph WHERE from_status = OLD.status AND to_status = NEW.status) THEN
    RAISE EXCEPTION 'Transição de projeto não permitida: % → %', OLD.status, NEW.status USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_project_status BEFORE UPDATE OF status ON projects FOR EACH ROW EXECUTE FUNCTION project_status_guard();

-- ================================================================================================ 4. LINHA DE TEMPO
-- Reusa a trilha encadeada por hash do projeto (ledger_entries): só acrescenta os tipos de evento do ciclo de vida.
ALTER TABLE ledger_entries DROP CONSTRAINT ledger_entries_entry_type_check;
ALTER TABLE ledger_entries ADD CONSTRAINT ledger_entries_entry_type_check CHECK (entry_type IN (
  'need_published','budget_defined','milestone_defined','interest_registered','application_submitted',
  'application_approved','funding_committed','disbursement_reported','disbursement_confirmed','expense_recorded',
  'evidence_submitted','evidence_reviewed','result_reported','report_submitted','feedback_given',
  'professional_signature','project_completed','refund_completed','payment_disputed','indicator_validated',
  'procurement_decided',
  -- v0.15.0: ciclo de vida, diagnóstico, documento, match, risco e snapshot
  'project_created','idea_promoted','status_changed','diagnosis_created','diagnosis_revised','action_created',
  'action_completed','goal_created','document_generated','document_approved','document_signed','opportunity_matched',
  'match_feedback','partner_added','submission_created','submission_sent','risk_created','risk_resolved',
  'snapshot_taken','project_archived'));

CREATE TABLE project_snapshots (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id    uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  label         text NOT NULL CHECK (length(label) BETWEEN 2 AND 160),
  reason        text NOT NULL DEFAULT 'manual' CHECK (reason IN ('manual','scheduled','status_change','submission','closure')),
  -- estado do projeto no instante: metas, orçamento, cronograma, riscos, indicadores, documentos, partes, status
  state         jsonb NOT NULL,
  state_sha256  char(64) NOT NULL CHECK (state_sha256 ~ '^[0-9a-f]{64}$'),
  ledger_seq    bigint,                      -- última entrada da trilha no momento do snapshot
  taken_by      uuid REFERENCES users(id),
  taken_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_psnap_project ON project_snapshots(project_id, taken_at DESC);

-- ================================================================================================ 5. RISCO DO PROJETO
-- `risk_assessments`/`risk_signals` são ANTIFRAUDE por organização (domínio diferente). Este é o registro de risco do projeto.
CREATE TABLE project_risks (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id    uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  code          text CHECK (code ~ '^[a-z0-9_.]{2,60}$'),   -- preenchido quando o risco foi identificado por regra
  category      text NOT NULL CHECK (category IN ('financial','operational','legal','documentary','eligibility',
                   'reputational','technical','partnership','timeline','other')),
  title         text NOT NULL CHECK (length(title) BETWEEN 3 AND 200),
  description   text CHECK (length(description) <= 4000),
  probability   text NOT NULL DEFAULT 'medium' CHECK (probability IN ('low','medium','high')),
  impact        text NOT NULL DEFAULT 'medium' CHECK (impact IN ('low','medium','high')),
  severity      text NOT NULL DEFAULT 'medium' CHECK (severity IN ('low','medium','high','critical')),
  -- 'system_identified' deixa explícito que foi uma REGRA que apontou, não uma verdade absoluta
  origin        text NOT NULL DEFAULT 'declared' CHECK (origin IN ('declared','system_identified')),
  mitigation    text CHECK (length(mitigation) <= 4000),
  owner_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  status        text NOT NULL DEFAULT 'open' CHECK (status IN ('open','mitigating','accepted','resolved','materialized','dismissed')),
  review_date   date,
  resolved_at   timestamptz,
  resolution_note text CHECK (length(resolution_note) <= 2000),
  created_by    uuid REFERENCES users(id),
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (project_id, code)
);
CREATE INDEX ix_prisk_project ON project_risks(project_id, status, severity);

-- ================================================================================================ 6. DIAGNÓSTICO VERSIONADO
-- `diagnoses` continua sendo o diagnóstico CORRENTE (editável). Cada publicação congela uma VERSÃO imutável, e a
-- comparação entre versões é o que permite mostrar evolução.
CREATE TABLE diagnosis_versions (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  diagnosis_id  uuid NOT NULL REFERENCES diagnoses(id) ON DELETE CASCADE,
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  version       integer NOT NULL CHECK (version >= 1),
  -- retrato completo: estado atual, forças, lacunas, riscos, evidências ausentes, oportunidades, ações, confiança
  payload       jsonb NOT NULL,
  payload_sha256 char(64) NOT NULL CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
  -- o que mudou em relação à versão anterior (calculado no servidor, não declarado pela usuária)
  changes       jsonb NOT NULL DEFAULT '{}'::jsonb,
  completeness  numeric(5,2) CHECK (completeness BETWEEN 0 AND 100),
  confidence    numeric(5,2) CHECK (confidence BETWEEN 0 AND 100),
  engine_version text NOT NULL,
  created_by    uuid REFERENCES users(id),
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (diagnosis_id, version)
);
CREATE INDEX ix_dver_diag ON diagnosis_versions(diagnosis_id, version DESC);

-- Plano de ação: cada lacuna relevante pode gerar uma ação rastreável, ligada à evidência que a fecha.
CREATE TABLE diagnosis_actions (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  diagnosis_id  uuid NOT NULL REFERENCES diagnoses(id) ON DELETE CASCADE,
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  project_id    uuid REFERENCES projects(id) ON DELETE SET NULL,
  gap_code      text CHECK (gap_code ~ '^[a-z0-9_.]{2,60}$'),
  title         text NOT NULL CHECK (length(title) BETWEEN 3 AND 200),
  detail        text CHECK (length(detail) <= 2000),
  evidence_hint text CHECK (length(evidence_hint) <= 300),       -- que evidência fecha esta ação
  priority      text NOT NULL DEFAULT 'medium' CHECK (priority IN ('low','medium','high','critical')),
  origin        text NOT NULL DEFAULT 'system_identified' CHECK (origin IN ('declared','system_identified')),
  status        text NOT NULL DEFAULT 'open' CHECK (status IN ('open','in_progress','done','dismissed')),
  owner_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  due_on        date,
  document_id   uuid REFERENCES documents(id) ON DELETE SET NULL,
  done_at       timestamptz,
  dismissed_reason text CHECK (length(dismissed_reason) <= 500),
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (diagnosis_id, gap_code)
);
CREATE INDEX ix_dact_diag ON diagnosis_actions(diagnosis_id, status, priority);

-- ================================================================================================ 7. MONTAGEM DE DOCUMENTO
-- Documento deixa de ser só arquivo: existe modelo com campos e requisitos, a montagem calcula COMPLETUDE e a geração
-- é RECUSADA quando falta campo obrigatório, evidência ou aprovação. O arquivo gerado continua indo para o cofre.
CREATE TABLE document_templates (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code          text NOT NULL CHECK (code ~ '^[a-z0-9_.-]{3,60}$'),
  version       text NOT NULL CHECK (length(version) BETWEEN 1 AND 20),
  title         text NOT NULL CHECK (length(title) BETWEEN 3 AND 200),
  kind          text NOT NULL CHECK (kind IN ('project_technical','work_plan','budget','schedule','goal_matrix',
                   'indicator_matrix','monitoring_plan','report','accountability','presentation','term','contract',
                   'letter','form','annex','other')),
  description   text CHECK (length(description) <= 2000),
  -- de onde o modelo puxa dado do domínio: project, organization, diagnosis, indicators, budget, milestones, risks
  data_sources  text[] NOT NULL DEFAULT '{}',
  output_formats text[] NOT NULL DEFAULT '{pdf,docx,odt}',
  -- modelo publicado é imutável: alterar exige nova versão (mesmo princípio dos cursos e das regras fiscais)
  status        text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','published','archived')),
  owner_org_id  uuid REFERENCES organizations(id) ON DELETE CASCADE,   -- NULL = modelo da plataforma
  source_note   text CHECK (length(source_note) <= 500),
  published_by  uuid REFERENCES users(id),
  published_at  timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (code, version)
);

CREATE TABLE document_template_fields (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  template_id   uuid NOT NULL REFERENCES document_templates(id) ON DELETE CASCADE,
  section       text NOT NULL CHECK (length(section) BETWEEN 1 AND 120),
  position      smallint NOT NULL CHECK (position BETWEEN 1 AND 500),
  key           text NOT NULL CHECK (key ~ '^[a-z0-9_.]{2,60}$'),
  label         text NOT NULL CHECK (length(label) BETWEEN 2 AND 200),
  help          text CHECK (length(help) <= 500),
  field_type    text NOT NULL CHECK (field_type IN ('text','textarea','number','money','date','boolean','enum','list',
                   'table','ods','determinants','indicator_ref','document_ref')),
  options       jsonb NOT NULL DEFAULT '[]'::jsonb,
  required      boolean NOT NULL DEFAULT false,
  -- quando preenchido, o valor vem do domínio (ex.: project.title) e não é digitado
  derived_from  text CHECK (length(derived_from) <= 120),
  requires_evidence boolean NOT NULL DEFAULT false,
  UNIQUE (template_id, key),
  UNIQUE (template_id, section, position)
);

CREATE TABLE document_assemblies (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  template_id   uuid NOT NULL REFERENCES document_templates(id) ON DELETE RESTRICT,
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  project_id    uuid REFERENCES projects(id) ON DELETE SET NULL,
  diagnosis_id  uuid REFERENCES diagnoses(id) ON DELETE SET NULL,
  application_id uuid REFERENCES applications(id) ON DELETE SET NULL,
  title         text NOT NULL CHECK (length(title) BETWEEN 3 AND 200),
  values        jsonb NOT NULL DEFAULT '{}'::jsonb,
  evidence      jsonb NOT NULL DEFAULT '{}'::jsonb,      -- {campo: document_id}
  completeness  numeric(5,2) NOT NULL DEFAULT 0 CHECK (completeness BETWEEN 0 AND 100),
  missing       jsonb NOT NULL DEFAULT '[]'::jsonb,      -- o que falta, calculado pelo servidor
  status        text NOT NULL DEFAULT 'drafting' CHECK (status IN ('drafting','ready','blocked','generated',
                   'in_review','approved','rejected','signed','archived')),
  blocked_reason text CHECK (length(blocked_reason) <= 1000),
  generated_document_id uuid REFERENCES documents(id) ON DELETE SET NULL,
  generated_format text CHECK (generated_format IN ('pdf','docx','odt','xlsx','ods')),
  generated_sha256 char(64) CHECK (generated_sha256 IS NULL OR generated_sha256 ~ '^[0-9a-f]{64}$'),
  generated_at  timestamptz,
  reviewed_by   uuid REFERENCES users(id),
  reviewed_at   timestamptz,
  review_note   text CHECK (length(review_note) <= 2000),
  approved_by   uuid REFERENCES users(id),
  approved_at   timestamptz,
  created_by    uuid REFERENCES users(id),
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  -- quatro olhos: quem aprova não é quem criou
  CHECK (approved_by IS NULL OR approved_by <> created_by)
);
CREATE INDEX ix_dasm_org ON document_assemblies(org_id, status, created_at DESC);
CREATE INDEX ix_dasm_project ON document_assemblies(project_id, status);

-- ================================================================================================ 8. REALIMENTAÇÃO DO MATCH
CREATE TABLE match_feedback (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  match_run_id  uuid NOT NULL REFERENCES match_runs(id) ON DELETE CASCADE,
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  feedback      text NOT NULL CHECK (feedback IN ('accepted','rejected','ignored','not_relevant','contacted',
                   'converted','expired')),
  reason        text CHECK (length(reason) <= 1000),
  actor_user_id uuid REFERENCES users(id),
  at            timestamptz NOT NULL DEFAULT now(),
  UNIQUE (match_run_id, org_id)
);
CREATE INDEX ix_mfb_run ON match_feedback(match_run_id);
-- Versões adicionais no resultado do match: regras e taxonomia, para que um resultado antigo nunca mude de significado.
ALTER TABLE match_runs ADD COLUMN rules_version text;
ALTER TABLE match_runs ADD COLUMN taxonomy_version text;
ALTER TABLE match_runs ADD COLUMN evidence jsonb NOT NULL DEFAULT '{}'::jsonb;

-- ================================================================================================ 9. ASSINATURA: PROVEDOR E NÍVEL
-- O enum `signatures.method` existia desde a v0.7.0 com 'icp_brasil' e 'govbr', mas NENHUM código produzia esses
-- valores. Agora existe catálogo de provedores com estado real e política por organização — e o gatilho IMPEDE gravar
-- assinatura com método cujo provedor não esteja ativo em produção.
CREATE TABLE signature_providers (
  key           text PRIMARY KEY CHECK (key ~ '^[a-z0-9_]{3,40}$'),
  name          text NOT NULL CHECK (length(name) BETWEEN 2 AND 120),
  -- nível JURÍDICO que o provedor entrega (Lei 14.063/2020); 'qualified' exige certificado ICP-Brasil de verdade
  legal_level   text NOT NULL CHECK (legal_level IN ('simple','advanced','qualified')),
  -- nível CRIPTOGRÁFICO: o que a plataforma faz hoje é selo HMAC do servidor, não assinatura de chave assimétrica
  crypto_level  text NOT NULL CHECK (crypto_level IN ('server_hmac','asymmetric_pkcs7','asymmetric_pades','none')),
  method        text NOT NULL CHECK (method IN ('platform_advanced','icp_brasil','govbr')),
  identity_level_required text NOT NULL DEFAULT 'email'
                  CHECK (identity_level_required IN ('none','email','phone','document','professional','biometric')),
  supports_timestamp boolean NOT NULL DEFAULT false,
  supports_revocation_check boolean NOT NULL DEFAULT false,
  supports_certificate boolean NOT NULL DEFAULT false,
  -- estado REAL: 'unavailable' é o padrão de tudo que depende de contratação
  state         text NOT NULL DEFAULT 'unavailable' CHECK (state IN ('unavailable','configured','sandbox',
                   'homologation','production','degraded','disabled')),
  external_dependency text CHECK (length(external_dependency) <= 300),
  activation_note text CHECK (length(activation_note) <= 1000),
  health_state  text NOT NULL DEFAULT 'unknown' CHECK (health_state IN ('unknown','healthy','degraded','unavailable')),
  health_detail text CHECK (length(health_detail) <= 500),
  last_health_at timestamptz,
  updated_at    timestamptz NOT NULL DEFAULT now()
);
INSERT INTO signature_providers(key, name, legal_level, crypto_level, method, identity_level_required,
  supports_timestamp, supports_revocation_check, supports_certificate, state, external_dependency, activation_note) VALUES
 ('platform_advanced','Assinatura avançada da plataforma','advanced','server_hmac','platform_advanced','email',
  true, true, false, 'production', NULL,
  'Nativa: reautenticação por senha + código de uso único amarrado ao hash. Carimbo interno; revogação registrada na plataforma.'),
 ('icp_brasil','Assinatura qualificada ICP-Brasil','qualified','asymmetric_pades','icp_brasil','document',
  true, true, true, 'unavailable',
  'Certificado A1/A3 emitido por AC credenciada na ICP-Brasil + biblioteca de assinatura PAdES/CAdES + homologação',
  'Para ativar: contratar certificado, configurar o provedor, rodar a bateria de homologação e mudar o estado para production. Enquanto estiver unavailable, a plataforma RECUSA assinar com este método.'),
 ('govbr','Assinatura eletrônica gov.br','advanced','asymmetric_pkcs7','govbr','document',
  true, false, true, 'unavailable',
  'Credenciamento no gov.br (Conecta/Assinatura Eletrônica) com client_id e escopo aprovados',
  'Para ativar: obter credenciamento, cadastrar a conexão no Integration Hub e mudar o estado para production. O nível jurídico do gov.br é AVANÇADO, não qualificado — não confundir com ICP-Brasil.');

-- Política por organização: qual nível mínimo cada tipo de documento exige.
CREATE TABLE signature_policies (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        uuid REFERENCES organizations(id) ON DELETE CASCADE,   -- NULL = política padrão da plataforma
  doc_kind      text NOT NULL CHECK (length(doc_kind) BETWEEN 2 AND 60),
  min_legal_level text NOT NULL CHECK (min_legal_level IN ('simple','advanced','qualified')),
  min_identity_level text NOT NULL DEFAULT 'email'
                  CHECK (min_identity_level IN ('none','email','phone','document','professional','biometric')),
  require_timestamp boolean NOT NULL DEFAULT false,
  note          text CHECK (length(note) <= 500),
  created_by    uuid REFERENCES users(id),
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, doc_kind)
);
INSERT INTO signature_policies(org_id, doc_kind, min_legal_level, min_identity_level, require_timestamp, note) VALUES
 (NULL, 'default', 'advanced', 'email', true, 'Padrão da plataforma: assinatura avançada com carimbo interno.'),
 (NULL, 'contrato', 'advanced', 'document', true, 'Contrato: identidade conferida por documento.'),
 (NULL, 'prestacao_contas', 'advanced', 'document', true, NULL);

ALTER TABLE signatures ADD COLUMN provider_key text REFERENCES signature_providers(key);
ALTER TABLE signatures ADD COLUMN legal_level text CHECK (legal_level IN ('simple','advanced','qualified'));
ALTER TABLE signatures ADD COLUMN crypto_level text CHECK (crypto_level IN ('server_hmac','asymmetric_pkcs7','asymmetric_pades','none'));
UPDATE signatures SET provider_key = 'platform_advanced', legal_level = 'advanced', crypto_level = 'server_hmac'
  WHERE method = 'platform_advanced';

-- NINGUÉM grava assinatura com método cujo provedor não está em produção. É isto que impede "ICP-Brasil simulada".
CREATE FUNCTION signature_provider_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE st text; ll text; cl text;
BEGIN
  SELECT state, legal_level, crypto_level INTO st, ll, cl FROM signature_providers
    WHERE key = coalesce(NEW.provider_key, NEW.method);
  IF st IS NULL THEN
    RAISE EXCEPTION 'Provedor de assinatura desconhecido: %', coalesce(NEW.provider_key, NEW.method) USING ERRCODE = '23514';
  END IF;
  IF st <> 'production' THEN
    RAISE EXCEPTION 'Provedor de assinatura "%" não está em produção (estado: %). A plataforma não assina com provedor indisponível.',
      coalesce(NEW.provider_key, NEW.method), st USING ERRCODE = '23514';
  END IF;
  NEW.provider_key := coalesce(NEW.provider_key, NEW.method);
  NEW.legal_level := ll;
  NEW.crypto_level := cl;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_sig_provider BEFORE INSERT ON signatures FOR EACH ROW EXECUTE FUNCTION signature_provider_guard();

-- ================================================================================================ 10. CHAVE DE CIFRAGEM
-- `FieldCipher` usa MultiFernet (a primeira cifra, todas decifram), então a rotação já funcionava — mas sem METADADO,
-- sem recifragem e sem auditoria. Esta tabela registra as chaves ATIVAS por impressão digital (nunca a chave).
CREATE TABLE encryption_keys (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  purpose       text NOT NULL CHECK (purpose IN ('field','integration','signature_seal')),
  version       integer NOT NULL CHECK (version >= 1),
  -- SHA-256 dos primeiros bytes da chave: identifica sem revelar. A CHAVE NUNCA é gravada.
  fingerprint   char(16) NOT NULL CHECK (fingerprint ~ '^[0-9a-f]{16}$'),
  state         text NOT NULL DEFAULT 'active' CHECK (state IN ('active','decrypt_only','retired')),
  activated_at  timestamptz NOT NULL DEFAULT now(),
  retired_at    timestamptz,
  note          text CHECK (length(note) <= 500),
  UNIQUE (purpose, version),
  UNIQUE (purpose, fingerprint)
);

CREATE TABLE encryption_rotations (
  id            bigserial PRIMARY KEY,
  purpose       text NOT NULL,
  from_version  integer,
  to_version    integer NOT NULL,
  table_name    text NOT NULL CHECK (length(table_name) <= 60),
  rows_total    integer NOT NULL DEFAULT 0 CHECK (rows_total >= 0),
  rows_reencrypted integer NOT NULL DEFAULT 0 CHECK (rows_reencrypted >= 0),
  rows_failed   integer NOT NULL DEFAULT 0 CHECK (rows_failed >= 0),
  status        text NOT NULL DEFAULT 'running' CHECK (status IN ('running','completed','failed','partial')),
  actor_user_id uuid REFERENCES users(id),
  detail        text CHECK (length(detail) <= 2000),
  started_at    timestamptz NOT NULL DEFAULT now(),
  finished_at   timestamptz
);

-- ================================================================================================ 11. INDICADOR: PRODUTO × RESULTADO × IMPACTO
ALTER TABLE indicator_catalog ADD COLUMN result_kind text
  CHECK (result_kind IN ('output','outcome','impact'));
COMMENT ON COLUMN indicator_catalog.result_kind IS
  'output = o que foi entregue; outcome = mudança observada; impact = efeito atribuível. Meta atingida NÃO é impacto.';
UPDATE indicator_catalog SET result_kind = 'output' WHERE result_kind IS NULL;

-- ================================================================================================ 12. INTEGRIDADE E GUARDAS
DO $$ DECLARE t text; BEGIN
  FOREACH t IN ARRAY ARRAY['ideas','project_risks','diagnosis_actions','document_templates','document_assemblies'] LOOP
    EXECUTE format('CREATE TRIGGER trg_touch BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION touch_updated_at()', t);
  END LOOP;
END $$;

-- Append-only: transições, versões de diagnóstico, snapshots, realimentação de match e rotações de chave são HISTÓRIA.
CREATE TRIGGER trg_append_only BEFORE UPDATE OR DELETE ON project_transitions FOR EACH ROW
  WHEN (current_user::text = 'impacto_app') EXECUTE FUNCTION forbid_mutation();
CREATE TRIGGER trg_append_only BEFORE UPDATE OR DELETE ON diagnosis_versions FOR EACH ROW
  WHEN (current_user::text = 'impacto_app') EXECUTE FUNCTION forbid_mutation();
CREATE TRIGGER trg_append_only BEFORE UPDATE OR DELETE ON project_snapshots FOR EACH ROW
  WHEN (current_user::text = 'impacto_app') EXECUTE FUNCTION forbid_mutation();
CREATE TRIGGER trg_append_only BEFORE UPDATE OR DELETE ON match_feedback FOR EACH ROW
  WHEN (current_user::text = 'impacto_app') EXECUTE FUNCTION forbid_mutation();

-- Colunas que a organização NÃO altera por conta própria.
CREATE TRIGGER trg_guard BEFORE UPDATE ON document_assemblies FOR EACH ROW
  EXECUTE FUNCTION guard_columns('completeness','missing','generated_document_id','generated_sha256','generated_at',
                                 'reviewed_by','reviewed_at','approved_by','approved_at','template_id');
CREATE TRIGGER trg_guard BEFORE UPDATE ON document_templates FOR EACH ROW
  EXECUTE FUNCTION guard_columns('status','published_by','published_at','code','version');
CREATE TRIGGER trg_guard BEFORE UPDATE ON ideas FOR EACH ROW
  EXECUTE FUNCTION guard_columns('promoted_project_id','promoted_at');
CREATE TRIGGER trg_guard BEFORE UPDATE ON signature_providers FOR EACH ROW
  EXECUTE FUNCTION guard_columns('state','legal_level','crypto_level','method','health_state','health_detail','last_health_at');

-- Modelo publicado é imutável: alterar campo de modelo publicado exige nova versão.
CREATE FUNCTION template_field_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE st text;
BEGIN
  SELECT status INTO st FROM document_templates WHERE id = coalesce(NEW.template_id, OLD.template_id);
  IF st = 'published' AND current_user::text = 'impacto_app' THEN
    RAISE EXCEPTION 'Modelo publicado é imutável: crie uma nova versão do modelo' USING ERRCODE = '42501';
  END IF;
  RETURN coalesce(NEW, OLD);
END $$;
CREATE TRIGGER trg_tplfield_guard BEFORE INSERT OR UPDATE OR DELETE ON document_template_fields FOR EACH ROW
  EXECUTE FUNCTION template_field_guard();

-- Montagem nasce em 'drafting' e nunca "nasce aprovada".
CREATE FUNCTION assembly_initial_state() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF current_user::text <> 'impacto_app' OR app_priv() THEN RETURN NEW; END IF;
  NEW.status := 'drafting';
  NEW.completeness := 0;
  NEW.generated_document_id := NULL; NEW.generated_sha256 := NULL; NEW.generated_at := NULL;
  NEW.reviewed_by := NULL; NEW.reviewed_at := NULL; NEW.approved_by := NULL; NEW.approved_at := NULL;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_initial BEFORE INSERT ON document_assemblies FOR EACH ROW EXECUTE FUNCTION assembly_initial_state();

-- Validação de marcador: agora contra ods_goals (a tabela consolidada), esg_pillars e social_determinants.
DROP TRIGGER trg_itag_guard ON impact_tags;
DROP FUNCTION impact_tag_guard();
CREATE FUNCTION impact_tag_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.taxonomy = 'sdg' AND NOT EXISTS (SELECT 1 FROM ods_goals WHERE code = NEW.code AND active) THEN
    RAISE EXCEPTION 'ODS desconhecido: %', NEW.code USING ERRCODE = '23514';
  ELSIF NEW.taxonomy = 'esg' AND NOT EXISTS (SELECT 1 FROM esg_pillars WHERE code = NEW.code) THEN
    RAISE EXCEPTION 'Pilar ESG desconhecido: %', NEW.code USING ERRCODE = '23514';
  ELSIF NEW.taxonomy = 'determinant' AND NOT EXISTS (SELECT 1 FROM social_determinants WHERE code = NEW.code AND active) THEN
    RAISE EXCEPTION 'Determinante social desconhecido: %', NEW.code USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_itag_guard BEFORE INSERT OR UPDATE ON impact_tags FOR EACH ROW EXECUTE FUNCTION impact_tag_guard();

-- ================================================================================================ 13. RLS
ALTER TABLE ideas                    ENABLE ROW LEVEL SECURITY;
ALTER TABLE project_transitions      ENABLE ROW LEVEL SECURITY;
ALTER TABLE project_status_graph     ENABLE ROW LEVEL SECURITY;
ALTER TABLE project_snapshots        ENABLE ROW LEVEL SECURITY;
ALTER TABLE project_risks            ENABLE ROW LEVEL SECURITY;
ALTER TABLE diagnosis_versions       ENABLE ROW LEVEL SECURITY;
ALTER TABLE diagnosis_actions        ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_templates       ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_template_fields ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_assemblies      ENABLE ROW LEVEL SECURITY;
ALTER TABLE match_feedback           ENABLE ROW LEVEL SECURITY;
ALTER TABLE signature_providers      ENABLE ROW LEVEL SECURITY;
ALTER TABLE signature_policies       ENABLE ROW LEVEL SECURITY;
ALTER TABLE encryption_keys          ENABLE ROW LEVEL SECURITY;
ALTER TABLE encryption_rotations     ENABLE ROW LEVEL SECURITY;

CREATE POLICY ideas_rw ON ideas FOR ALL USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY ptrans_read ON project_transitions FOR SELECT USING (org_id = app_org() OR app_priv());
CREATE POLICY ptrans_insert ON project_transitions FOR INSERT WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY psgraph_read ON project_status_graph FOR SELECT USING (app_authenticated() OR app_priv());
CREATE POLICY psgraph_write ON project_status_graph FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY psnap_read ON project_snapshots FOR SELECT USING (org_id = app_org() OR app_priv());
CREATE POLICY psnap_insert ON project_snapshots FOR INSERT WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY prisk_rw ON project_risks FOR ALL USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY dver_read ON diagnosis_versions FOR SELECT USING (org_id = app_org() OR app_priv());
CREATE POLICY dver_insert ON diagnosis_versions FOR INSERT WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY dact_rw ON diagnosis_actions FOR ALL USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());
-- Modelo da plataforma (owner_org_id NULL) e publicado é lido por todas; rascunho só pela dona.
CREATE POLICY dtpl_read ON document_templates FOR SELECT
  USING (app_priv() OR (status = 'published' AND (owner_org_id IS NULL OR owner_org_id = app_org()))
         OR owner_org_id = app_org());
CREATE POLICY dtpl_write ON document_templates FOR ALL USING (app_priv() OR owner_org_id = app_org())
  WITH CHECK (app_priv() OR owner_org_id = app_org());
CREATE POLICY dtplf_read ON document_template_fields FOR SELECT
  USING (app_priv() OR EXISTS (SELECT 1 FROM document_templates t WHERE t.id = document_template_fields.template_id
         AND (t.status = 'published' OR t.owner_org_id = app_org() OR t.owner_org_id IS NULL)));
CREATE POLICY dtplf_write ON document_template_fields FOR ALL
  USING (app_priv() OR EXISTS (SELECT 1 FROM document_templates t WHERE t.id = document_template_fields.template_id AND t.owner_org_id = app_org()))
  WITH CHECK (app_priv() OR EXISTS (SELECT 1 FROM document_templates t WHERE t.id = document_template_fields.template_id AND t.owner_org_id = app_org()));
CREATE POLICY dasm_rw ON document_assemblies FOR ALL USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY mfb_read ON match_feedback FOR SELECT USING (org_id = app_org() OR app_priv());
CREATE POLICY mfb_insert ON match_feedback FOR INSERT WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY sigprov_read ON signature_providers FOR SELECT USING (app_authenticated() OR app_priv());
CREATE POLICY sigprov_write ON signature_providers FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY sigpol_read ON signature_policies FOR SELECT USING (org_id IS NULL OR org_id = app_org() OR app_priv());
CREATE POLICY sigpol_write ON signature_policies FOR ALL USING (app_priv() OR org_id = app_org())
  WITH CHECK (app_priv() OR org_id = app_org());
-- Chaves e rotações: SOMENTE administração. A impressão digital não é segredo, mas o inventário de chaves é informação de ataque.
CREATE POLICY enckeys_priv ON encryption_keys FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY encrot_priv ON encryption_rotations FOR ALL USING (app_priv()) WITH CHECK (app_priv());

-- ================================================================================================ 14. GRANTS
GRANT SELECT, INSERT, UPDATE, DELETE ON ideas, project_risks, diagnosis_actions, document_templates,
  document_template_fields, document_assemblies, signature_policies TO impacto_app;
GRANT SELECT, INSERT ON project_transitions, project_snapshots, diagnosis_versions, match_feedback TO impacto_app;
GRANT SELECT ON project_status_graph, signature_providers TO impacto_app;
GRANT UPDATE (state, health_state, health_detail, last_health_at, activation_note, updated_at) ON signature_providers TO impacto_app;
GRANT SELECT, INSERT, UPDATE ON encryption_keys TO impacto_app;
GRANT SELECT, INSERT, UPDATE ON encryption_rotations TO impacto_app;
GRANT USAGE, SELECT ON SEQUENCE project_transitions_id_seq, encryption_rotations_id_seq TO impacto_app;

-- ================================================================================================ 15. ÍNDICES DE DESEMPENHO
-- Cada índice cita a consulta real que o justifica (mesma disciplina da 0010).
-- "meus projetos por situação" (lista de projetos, filtro por status) — projects(org_id, status) já existe? não: criamos.
CREATE INDEX IF NOT EXISTS ix_projects_org_status ON projects(org_id, status, updated_at DESC);
-- "linha de tempo do projeto" (ledger por projeto, mais recentes primeiro)
CREATE INDEX IF NOT EXISTS ix_ledger_project_at ON ledger_entries(project_id, at DESC);
-- "histórico de match de uma organização" e "realimentação pendente"
CREATE INDEX IF NOT EXISTS ix_matchruns_org_at ON match_runs(viewer_org_id, created_at DESC);
-- "indicadores de um projeto com a última medição" (indicator_values por indicador e data)
CREATE INDEX IF NOT EXISTS ix_indvalues_pi_date ON indicator_values(project_indicator_id, measured_on DESC);
-- "documentos de um projeto": ix_documents_project JÁ EXISTIA (conferido no banco); mantido aqui como IF NOT EXISTS
CREATE INDEX IF NOT EXISTS ix_documents_project ON documents(project_id) WHERE project_id IS NOT NULL AND deleted_at IS NULL;
-- "ações abertas do diagnóstico por prioridade" já coberto por ix_dact_diag; "riscos abertos" por ix_prisk_project.
