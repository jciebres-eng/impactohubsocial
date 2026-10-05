-- 0006 — Camada institucional do terceiro setor (v0.10.0)
-- Natureza jurídica × qualificações × perfil de atuação × situação institucional × maturidade × elegibilidade.
-- Princípios: catálogos configuráveis com fluxo editorial; qualificação é relacionamento próprio (não array); só a administração
-- verifica; documento tem validação humana separada do antivírus; regras de elegibilidade versionadas, datadas e com fonte.

-- ===========================================================================================
-- 1. Catálogos governados (naturezas jurídicas, qualificações, perfis, situações, modalidades, badges)
-- ===========================================================================================
CREATE TABLE inst_catalog_items (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  catalog       text NOT NULL CHECK (catalog IN ('legal_nature','qualification_type','institutional_profile','institutional_status','funding_modality','badge')),
  code          text NOT NULL CHECK (code ~ '^[a-z0-9_]{2,60}$'),
  version       integer NOT NULL DEFAULT 1 CHECK (version >= 1),
  label         text NOT NULL CHECK (length(label) BETWEEN 2 AND 160),
  description   text CHECK (length(description) <= 2000),
  attributes    jsonb NOT NULL DEFAULT '{}',
  source_citation text CHECK (length(source_citation) <= 600),
  source_url    text CHECK (source_url IS NULL OR source_url ~ '^https://'),
  source_date   date,
  confidence    text NOT NULL DEFAULT 'medium' CHECK (confidence IN ('high','medium','low')),
  needs_professional_validation boolean NOT NULL DEFAULT true,
  status        text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','review','approved','published','archived')),
  created_by    uuid REFERENCES users(id),
  reviewed_by   uuid REFERENCES users(id),
  approved_by   uuid REFERENCES users(id),
  published_by  uuid REFERENCES users(id),
  published_at  timestamptz,
  archived_at   timestamptz,
  change_note   text CHECK (length(change_note) <= 1000),
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (catalog, code, version),
  -- quatro olhos: itens criados por pessoa só são aprovados por OUTRA pessoa (itens iniciais do sistema têm created_by nulo)
  CHECK (status NOT IN ('approved','published') OR created_by IS NULL OR (approved_by IS NOT NULL AND approved_by <> created_by))
);
CREATE UNIQUE INDEX ux_inst_catalog_published ON inst_catalog_items(catalog, code) WHERE status = 'published';
CREATE INDEX ix_inst_catalog ON inst_catalog_items(catalog, status);

CREATE TABLE eligibility_rules (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code          text NOT NULL CHECK (code ~ '^[A-Z0-9-]{3,60}$'),
  version       integer NOT NULL DEFAULT 1 CHECK (version >= 1),
  name          text NOT NULL CHECK (length(name) BETWEEN 3 AND 200),
  description   text CHECK (length(description) <= 2000),
  scope_type    text NOT NULL CHECK (scope_type IN ('global','modality','call','funder')),
  scope_ref     text CHECK (length(scope_ref) <= 80),             -- modalidade (código), id do edital ou da organização financiadora
  requirement   jsonb NOT NULL,                                    -- {"type": "...", ...parâmetros} (conjunto fechado, validado na API e no motor)
  mandatory     boolean NOT NULL DEFAULT true,
  how_to_fix    text CHECK (length(how_to_fix) <= 1000),
  source_citation text NOT NULL CHECK (length(source_citation) BETWEEN 5 AND 600),
  source_url    text CHECK (source_url IS NULL OR source_url ~ '^https://'),
  source_consulted_on date,
  confidence    text NOT NULL DEFAULT 'medium' CHECK (confidence IN ('high','medium','low')),
  needs_professional_validation boolean NOT NULL DEFAULT true,
  effective_from date,
  effective_to   date,
  status        text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','review','approved','published','archived')),
  created_by    uuid REFERENCES users(id),
  reviewed_by   uuid REFERENCES users(id),
  approved_by   uuid REFERENCES users(id),
  published_by  uuid REFERENCES users(id),
  published_at  timestamptz,
  archived_at   timestamptz,
  change_note   text CHECK (length(change_note) <= 1000),
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (code, version),
  CHECK ((scope_type = 'global') = (scope_ref IS NULL)),
  CHECK (effective_from IS NULL OR effective_to IS NULL OR effective_from <= effective_to),
  CHECK (status NOT IN ('approved','published') OR (approved_by IS NOT NULL AND approved_by <> created_by)),
  CHECK (status <> 'published' OR (source_consulted_on IS NOT NULL AND published_by IS NOT NULL))
);
CREATE INDEX ix_elig_rules_scope ON eligibility_rules(scope_type, scope_ref) WHERE status = 'published';

-- ===========================================================================================
-- 2. Organizações: dimensões institucionais separadas
-- ===========================================================================================
ALTER TABLE organizations
  ADD COLUMN legal_nature_code      text CHECK (legal_nature_code ~ '^[a-z0-9_]{2,60}$'),
  ADD COLUMN institutional_profile  text CHECK (institutional_profile ~ '^[a-z0-9_]{2,60}$'),
  ADD COLUMN institutional_status   text NOT NULL DEFAULT 'registered'
       CHECK (institutional_status IN ('in_structuring','registered','documents_pending','regular','partially_regular','irregular','under_review','suspended','archived')),
  ADD COLUMN institutional_status_note text CHECK (length(institutional_status_note) <= 1000),
  ADD COLUMN institutional_status_by uuid REFERENCES users(id),
  ADD COLUMN institutional_status_at timestamptz,
  ADD COLUMN mission           text CHECK (length(mission) <= 3000),
  ADD COLUMN vision            text CHECK (length(vision) <= 3000),
  ADD COLUMN geographic_scope  text CHECK (geographic_scope IN ('local','municipal','regional','state','national','international')),
  ADD COLUMN operating_regions text[] NOT NULL DEFAULT '{}';

CREATE FUNCTION org_inst_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF current_user::text = 'impacto_app' AND NOT app_priv() THEN
    IF TG_OP = 'INSERT' THEN
      NEW.institutional_status := CASE WHEN NEW.cnpj IS NULL THEN 'in_structuring' ELSE 'registered' END;
      NEW.institutional_status_note := NULL; NEW.institutional_status_by := NULL; NEW.institutional_status_at := NULL;
    ELSE
      IF NEW.institutional_status IS DISTINCT FROM OLD.institutional_status OR NEW.institutional_status_note IS DISTINCT FROM OLD.institutional_status_note
         OR NEW.institutional_status_by IS DISTINCT FROM OLD.institutional_status_by OR NEW.institutional_status_at IS DISTINCT FROM OLD.institutional_status_at THEN
        RAISE EXCEPTION 'situação institucional só pode ser alterada pela administração' USING ERRCODE = '42501';
      END IF;
    END IF;
  ELSIF TG_OP = 'INSERT' AND NEW.cnpj IS NULL AND NEW.institutional_status = 'registered' THEN
    NEW.institutional_status := 'in_structuring';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_org_inst_guard BEFORE INSERT OR UPDATE ON organizations FOR EACH ROW EXECUTE FUNCTION org_inst_guard();

-- ===========================================================================================
-- 3. Qualificações e certificações (relacionamento próprio; novos tipos = novo item de catálogo, sem refatoração)
-- ===========================================================================================
CREATE TABLE organization_qualifications (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id              uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  qualification_type  text NOT NULL CHECK (qualification_type ~ '^[a-z0-9_]{2,60}$'),
  issuing_authority   text CHECK (length(issuing_authority) <= 300),
  protocol            text CHECK (length(protocol) <= 120),
  certificate_number  text CHECK (length(certificate_number) <= 120),
  issue_date          date,
  expiration_date     date,
  verification_url    text CHECK (verification_url IS NULL OR verification_url ~ '^https://'),
  verification_status text NOT NULL DEFAULT 'declared' CHECK (verification_status IN ('declared','document_submitted','under_review','verified','rejected','revoked')),
  document_id         uuid REFERENCES documents(id) ON DELETE SET NULL,
  validation_date     date,
  validated_by        uuid REFERENCES users(id),
  validation_note     text CHECK (length(validation_note) <= 1000),
  notes               text CHECK (length(notes) <= 2000),
  declared_by         uuid REFERENCES users(id),
  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now(),
  CHECK (expiration_date IS NULL OR issue_date IS NULL OR expiration_date >= issue_date),
  CHECK (verification_status <> 'verified' OR (validated_by IS NOT NULL AND validation_date IS NOT NULL))
);
CREATE UNIQUE INDEX ux_org_qualification ON organization_qualifications(org_id, qualification_type, coalesce(certificate_number, ''))
  WHERE verification_status NOT IN ('rejected','revoked');
CREATE INDEX ix_org_qualification_org ON organization_qualifications(org_id);
CREATE INDEX ix_org_qualification_queue ON organization_qualifications(verification_status) WHERE verification_status IN ('document_submitted','under_review');

CREATE TABLE organization_qualification_events (
  id          bigserial PRIMARY KEY,
  qualification_id uuid NOT NULL,
  org_id      uuid NOT NULL,
  event       text NOT NULL,
  from_status text,
  to_status   text,
  actor_user_id uuid,
  actor_is_admin boolean NOT NULL DEFAULT false,
  note        text,
  at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_oqe ON organization_qualification_events(qualification_id, at);

CREATE FUNCTION qualification_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF current_user::text = 'impacto_app' AND NOT app_priv() THEN
    IF TG_OP = 'INSERT' THEN
      NEW.verification_status := CASE WHEN NEW.document_id IS NOT NULL THEN 'document_submitted' ELSE 'declared' END;
      NEW.validated_by := NULL; NEW.validation_date := NULL; NEW.validation_note := NULL;
    ELSE
      IF NEW.verification_status IS DISTINCT FROM OLD.verification_status OR NEW.validated_by IS DISTINCT FROM OLD.validated_by
         OR NEW.validation_date IS DISTINCT FROM OLD.validation_date OR NEW.validation_note IS DISTINCT FROM OLD.validation_note
         OR NEW.org_id IS DISTINCT FROM OLD.org_id THEN
        -- única mudança permitida ao dono: declared→document_submitted ao anexar documento (feita abaixo, por derivação), nunca por valor direto
        RAISE EXCEPTION 'verificação de qualificação só pode ser alterada pela administração' USING ERRCODE = '42501';
      END IF;
      -- conteúdo comprobatório alterado derruba a verificação (volta a "em análise") e anexar documento sinaliza envio
      IF OLD.verification_status = 'verified' AND (NEW.qualification_type IS DISTINCT FROM OLD.qualification_type OR NEW.certificate_number IS DISTINCT FROM OLD.certificate_number
         OR NEW.issue_date IS DISTINCT FROM OLD.issue_date OR NEW.expiration_date IS DISTINCT FROM OLD.expiration_date
         OR NEW.document_id IS DISTINCT FROM OLD.document_id OR NEW.issuing_authority IS DISTINCT FROM OLD.issuing_authority) THEN
        NEW.verification_status := 'under_review'; NEW.validated_by := NULL; NEW.validation_date := NULL;
      ELSIF OLD.verification_status = 'declared' AND NEW.document_id IS NOT NULL AND OLD.document_id IS NULL THEN
        NEW.verification_status := 'document_submitted';
      END IF;
    END IF;
  END IF;
  NEW.updated_at := now();
  RETURN NEW;
END $$;
CREATE TRIGGER trg_qualification_guard BEFORE INSERT OR UPDATE ON organization_qualifications FOR EACH ROW EXECUTE FUNCTION qualification_guard();

CREATE FUNCTION qualification_log() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    INSERT INTO organization_qualification_events(qualification_id, org_id, event, to_status, actor_user_id, actor_is_admin)
    VALUES (NEW.id, NEW.org_id, 'created', NEW.verification_status, app_uid(), app_priv());
  ELSIF NEW.verification_status IS DISTINCT FROM OLD.verification_status
     OR NEW.expiration_date IS DISTINCT FROM OLD.expiration_date OR NEW.certificate_number IS DISTINCT FROM OLD.certificate_number
     OR NEW.document_id IS DISTINCT FROM OLD.document_id THEN
    INSERT INTO organization_qualification_events(qualification_id, org_id, event, from_status, to_status, actor_user_id, actor_is_admin, note)
    VALUES (NEW.id, NEW.org_id, CASE WHEN NEW.verification_status IS DISTINCT FROM OLD.verification_status THEN 'status_changed' ELSE 'edited' END,
            OLD.verification_status, NEW.verification_status, app_uid(), app_priv(), NEW.validation_note);
  END IF;
  RETURN NULL;
END $$;
CREATE TRIGGER trg_qualification_log AFTER INSERT OR UPDATE ON organization_qualifications FOR EACH ROW EXECUTE FUNCTION qualification_log();
CREATE TRIGGER trg_append_only BEFORE UPDATE OR DELETE ON organization_qualification_events FOR EACH ROW WHEN (current_user::text = 'impacto_app') EXECUTE FUNCTION forbid_mutation();

-- ===========================================================================================
-- 4. Documentos: validação humana separada do antivírus; emissão e origem
-- ===========================================================================================
ALTER TABLE documents
  ADD COLUMN validation_status text NOT NULL DEFAULT 'pending' CHECK (validation_status IN ('pending','validated','rejected')),
  ADD COLUMN validated_by      uuid REFERENCES users(id),
  ADD COLUMN validated_at      timestamptz,
  ADD COLUMN validation_note   text CHECK (length(validation_note) <= 1000),
  ADD COLUMN issued_on         date,
  ADD COLUMN origin_source     text CHECK (length(origin_source) <= 200),
  ADD CONSTRAINT ck_doc_validated CHECK (validation_status = 'pending' OR (validated_by IS NOT NULL AND validated_at IS NOT NULL));
CREATE INDEX ix_documents_validation ON documents(validation_status) WHERE deleted_at IS NULL AND validation_status = 'pending';

CREATE FUNCTION document_validation_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF current_user::text = 'impacto_app' AND NOT app_priv() THEN
    IF TG_OP = 'INSERT' THEN
      NEW.validation_status := 'pending'; NEW.validated_by := NULL; NEW.validated_at := NULL; NEW.validation_note := NULL;
    ELSE
      IF NEW.validation_status IS DISTINCT FROM OLD.validation_status OR NEW.validated_by IS DISTINCT FROM OLD.validated_by
         OR NEW.validated_at IS DISTINCT FROM OLD.validated_at OR NEW.validation_note IS DISTINCT FROM OLD.validation_note THEN
        RAISE EXCEPTION 'validação documental só pode ser alterada pela administração' USING ERRCODE = '42501';
      END IF;
      -- mudar tipo, validade ou emissão de documento já validado volta a validação para "pendente"
      IF OLD.validation_status = 'validated' AND (NEW.doc_type IS DISTINCT FROM OLD.doc_type OR NEW.valid_until IS DISTINCT FROM OLD.valid_until
         OR NEW.issued_on IS DISTINCT FROM OLD.issued_on OR NEW.title IS DISTINCT FROM OLD.title) THEN
        NEW.validation_status := 'pending'; NEW.validated_by := NULL; NEW.validated_at := NULL;
      END IF;
    END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_document_validation_guard BEFORE INSERT OR UPDATE ON documents FOR EACH ROW EXECUTE FUNCTION document_validation_guard();

-- ===========================================================================================
-- 5. Editais, financiadores e projetos: requisitos institucionais, modalidade, propriedade intelectual
-- ===========================================================================================
ALTER TABLE calls
  ADD COLUMN funding_modality text CHECK (funding_modality ~ '^[a-z0-9_]{2,60}$'),
  ADD COLUMN accepted_legal_natures text[] NOT NULL DEFAULT '{}',
  ADD COLUMN min_maturity smallint CHECK (min_maturity BETWEEN 0 AND 6);
ALTER TABLE funder_profiles
  ADD COLUMN accepted_legal_natures text[] NOT NULL DEFAULT '{}',
  ADD COLUMN required_qualifications text[] NOT NULL DEFAULT '{}',
  ADD COLUMN min_maturity smallint CHECK (min_maturity BETWEEN 0 AND 6),
  ADD COLUMN funding_modalities text[] NOT NULL DEFAULT '{}';

ALTER TABLE solutions
  ADD COLUMN compatible_modalities text[] NOT NULL DEFAULT '{}',
  ADD COLUMN legal_requirements text CHECK (length(legal_requirements) <= 3000),
  ADD COLUMN rights_holder text CHECK (length(rights_holder) <= 300),
  ADD COLUMN ownership_type text NOT NULL DEFAULT 'unknown' CHECK (ownership_type IN ('author','organization','joint','institution','third_party','unknown')),
  ADD COLUMN confidentiality text NOT NULL DEFAULT 'public' CHECK (confidentiality IN ('public','shareable','shareable_on_request','confidential','restricted_use')),
  ADD COLUMN authorization_publish boolean NOT NULL DEFAULT false,
  ADD COLUMN authorization_contact boolean NOT NULL DEFAULT true,
  ADD COLUMN ip_declared_at timestamptz,
  ADD COLUMN ip_declared_by uuid REFERENCES users(id);
CREATE INDEX ix_solutions_confidentiality ON solutions(confidentiality) WHERE visibility = 'published';

-- confidencial nunca é descoberto por terceiros (só a própria organização e a administração); filhos seguem a mesma regra
DROP POLICY solutions_read ON solutions;
CREATE POLICY solutions_read ON solutions FOR SELECT USING (
  (app_authenticated() AND visibility = 'published' AND confidentiality <> 'confidential') OR org_id = app_org() OR app_priv());
CREATE OR REPLACE FUNCTION app_solution_visible(sid uuid) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
  SELECT EXISTS (SELECT 1 FROM solutions s WHERE s.id = sid AND ((s.visibility = 'published' AND s.confidentiality <> 'confidential') OR s.org_id = app_org()))
$$;

-- ===========================================================================================
-- 6. Necessidades do proponente (intencionalidade do proponente) e avaliações de elegibilidade
-- ===========================================================================================
CREATE TABLE proponent_needs (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id      uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  solution_id uuid REFERENCES solutions(id) ON DELETE CASCADE,
  need_type   text NOT NULL CHECK (need_type IN ('financing','partner','replication','technical','institutional','territorial_expansion')),
  detail      text CHECK (length(detail) <= 1500),
  amount_cents bigint CHECK (amount_cents >= 0),
  territory   text CHECK (length(territory) <= 40),
  status      text NOT NULL DEFAULT 'open' CHECK (status IN ('open','met','closed')),
  created_by  uuid REFERENCES users(id),
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_proponent_needs ON proponent_needs(org_id, status);
CREATE INDEX ix_proponent_needs_solution ON proponent_needs(solution_id) WHERE solution_id IS NOT NULL;

CREATE TABLE eligibility_evaluations (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id      uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  viewer_org_id uuid REFERENCES organizations(id) ON DELETE SET NULL,
  subject_type text NOT NULL CHECK (subject_type IN ('call','modality','funder','solution')),
  subject_ref  text NOT NULL CHECK (length(subject_ref) <= 80),
  state        text NOT NULL CHECK (state IN ('eligible','probably_eligible','pending','not_eligible','needs_professional_validation')),
  result       jsonb NOT NULL,
  engine_version text NOT NULL,
  rules_digest jsonb NOT NULL DEFAULT '[]',
  created_by   uuid REFERENCES users(id),
  created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_elig_eval ON eligibility_evaluations(org_id, subject_type, subject_ref, created_at DESC);
CREATE TRIGGER trg_append_only BEFORE UPDATE OR DELETE ON eligibility_evaluations FOR EACH ROW WHEN (current_user::text = 'impacto_app') EXECUTE FUNCTION forbid_mutation();

-- ===========================================================================================
-- 7. Fatos institucionais de outra organização (somente metadados; mesma regra de visibilidade de org_document_metadata)
-- ===========================================================================================
CREATE FUNCTION org_institutional_facts(p_org uuid) RETURNS jsonb LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE r jsonb;
BEGIN
  IF NOT (app_org() = p_org OR app_kind() IN ('company','government','platform','individual') OR app_priv()) THEN
    RAISE EXCEPTION 'acesso negado aos fatos institucionais' USING ERRCODE = '42501';
  END IF;
  SELECT jsonb_build_object(
    'org_id', o.id, 'kind', o.kind, 'legal_nature_code', o.legal_nature_code, 'institutional_profile', o.institutional_profile,
    'institutional_status', o.institutional_status, 'cnpj_present', o.cnpj IS NOT NULL, 'founded_on', o.founded_on,
    'compliance_status', o.compliance_status, 'compliance_reviewed_at', o.compliance_reviewed_at, 'uf', o.uf, 'causes', to_jsonb(o.causes),
    'has_description', coalesce(length(o.description), 0) > 0, 'kind_is_proponent', o.kind IN ('osc','provider','individual'),
    'qualifications', coalesce((SELECT jsonb_agg(jsonb_build_object('id', q.id, 'type', q.qualification_type, 'status', q.verification_status,
         'issuing_authority', q.issuing_authority, 'expiration_date', q.expiration_date, 'validation_date', q.validation_date, 'has_document', q.document_id IS NOT NULL))
         FROM organization_qualifications q WHERE q.org_id = o.id AND q.verification_status NOT IN ('rejected','revoked')), '[]'::jsonb),
    'documents', coalesce((SELECT jsonb_agg(jsonb_build_object('doc_type', d.doc_type, 'scan_status', d.status, 'validation_status', d.validation_status, 'valid_until', d.valid_until, 'validated_at', d.validated_at, 'issued_on', d.issued_on))
         FROM documents d WHERE d.org_id = o.id AND d.deleted_at IS NULL), '[]'::jsonb))
  INTO r FROM organizations o WHERE o.id = p_org;
  RETURN r;
END $$;

-- ===========================================================================================
-- 8. Catálogo inicial (itens publicados pelo sistema; fonte = classificação da plataforma; revisão jurídica pendente)
-- ===========================================================================================
INSERT INTO inst_catalog_items(catalog, code, label, description, attributes, source_citation, confidence, needs_professional_validation, status, published_at) VALUES
('legal_nature','association','Associação privada','Pessoa jurídica de direito privado sem fins lucrativos constituída por pessoas.','{"allowed_kinds":["osc"],"requires_cnpj":true}','Classificação inicial da plataforma — revisar com assessoria jurídica','medium',true,'published',now()),
('legal_nature','foundation','Fundação privada','Entidade formada por patrimônio destinado a finalidade específica.','{"allowed_kinds":["osc"],"requires_cnpj":true}','Classificação inicial da plataforma — revisar com assessoria jurídica','medium',true,'published',now()),
('legal_nature','cooperative','Cooperativa (incl. cooperativa social)','Sociedade cooperativa; a aplicabilidade a cada edital deve ser conferida.','{"allowed_kinds":["osc"],"requires_cnpj":true}','Classificação inicial da plataforma — revisar com assessoria jurídica','low',true,'published',now()),
('legal_nature','religious_organization','Organização religiosa','Organização religiosa; a aplicabilidade a cada edital deve ser conferida.','{"allowed_kinds":["osc"],"requires_cnpj":true}','Classificação inicial da plataforma — revisar com assessoria jurídica','low',true,'published',now()),
('legal_nature','academic_institution','Instituição acadêmica ou de pesquisa','Universidade, instituto ou centro de pesquisa (pública ou privada).','{"allowed_kinds":["osc"],"requires_cnpj":true}','Classificação inicial da plataforma — revisar com assessoria jurídica','medium',true,'published',now()),
('legal_nature','collective','Coletivo ou iniciativa em estruturação','Grupo sem personalidade jurídica própria ainda; pode participar do Banco de Ideias e seguir o caminho de formalização.','{"allowed_kinds":["osc"],"requires_cnpj":false}','Classificação inicial da plataforma','high',false,'published',now()),
('legal_nature','company','Empresa / empresa social','Pessoa jurídica com fins lucrativos (inclui empresas sociais).','{"allowed_kinds":["company","osc"],"requires_cnpj":true}','Classificação inicial da plataforma','medium',true,'published',now()),
('legal_nature','public_body','Órgão ou entidade pública','Poder público (federal, estadual, municipal).','{"allowed_kinds":["government"],"requires_cnpj":true}','Classificação inicial da plataforma','medium',true,'published',now()),
('legal_nature','professional','Profissional autônomo','Profissional prestador de serviços (credencial própria).','{"allowed_kinds":["provider"],"requires_cnpj":false}','Classificação inicial da plataforma','high',false,'published',now()),
('legal_nature','researcher','Pesquisador','Pessoa física pesquisadora que publica ideias, estudos e metodologias.','{"allowed_kinds":["individual","provider"],"requires_cnpj":false}','Classificação inicial da plataforma','high',false,'published',now()),
('legal_nature','individual','Pessoa física','Pessoa física apoiadora ou autora de ideias.','{"allowed_kinds":["individual"],"requires_cnpj":false}','Classificação inicial da plataforma','high',false,'published',now()),
('legal_nature','other','Outra natureza','Registre na descrição livre; a administração pode propor nova categoria.','{"allowed_kinds":["osc","company","government","provider","individual"],"requires_cnpj":false}','Classificação inicial da plataforma','low',true,'published',now()),

('qualification_type','osc','OSC — enquadramento (Lei 13.019/2014, MROSC)','Enquadramento como organização da sociedade civil para parcerias com a administração pública. Conferir texto e requisitos vigentes.','{"issuing_authority_hint":"conforme edital/ente público"}','Lei nº 13.019/2014 (conferir texto vigente)','medium',true,'published',now()),
('qualification_type','oscip','OSCIP — Organização da Sociedade Civil de Interesse Público (Lei 9.790/1999)','Qualificação concedida pelo poder público; informar autoridade, protocolo e número.','{"issuing_authority_hint":"autoridade qualificadora"}','Lei nº 9.790/1999 (conferir texto vigente)','medium',true,'published',now()),
('qualification_type','os','OS — Organização Social (Lei 9.637/1998)','Qualificação concedida pelo ente público; costuma associar-se a contrato de gestão. Informar autoridade qualificadora e área de atuação.','{"issuing_authority_hint":"autoridade qualificadora (ente público)","requires_area":true}','Lei nº 9.637/1998 (conferir texto vigente)','medium',true,'published',now()),
('qualification_type','cebas','CEBAS — Certificação de Entidade Beneficente (LC 187/2021)','Certificação de entidade beneficente nas áreas aplicáveis; tem validade e depende de requisitos e do ministério competente.','{"issuing_authority_hint":"ministério competente da área"}','Lei Complementar nº 187/2021 (conferir texto vigente)','medium',true,'published',now()),
('qualification_type','utilidade_publica_federal','Utilidade pública (federal)','Declaração de utilidade pública na esfera federal; informar ato legal e vigência. Conferir a legislação aplicável.','{}','Legislação do ente declarante (informar no cadastro)','low',true,'published',now()),
('qualification_type','utilidade_publica_estadual','Utilidade pública (estadual)','Declaração de utilidade pública estadual; informar ato legal e vigência.','{}','Legislação do ente declarante (informar no cadastro)','low',true,'published',now()),
('qualification_type','utilidade_publica_municipal','Utilidade pública (municipal)','Declaração de utilidade pública municipal; informar ato legal e vigência.','{}','Legislação do ente declarante (informar no cadastro)','low',true,'published',now()),
('qualification_type','registro_cmdca','Registro no CMDCA','Registro no Conselho Municipal dos Direitos da Criança e do Adolescente.','{}','Normas do conselho (informar no cadastro)','low',true,'published',now()),
('qualification_type','registro_cmas','Registro no CMAS','Registro no Conselho Municipal de Assistência Social.','{}','Normas do conselho (informar no cadastro)','low',true,'published',now()),
('qualification_type','registro_cmi','Registro no Conselho da Pessoa Idosa','Registro no conselho de direitos da pessoa idosa.','{}','Normas do conselho (informar no cadastro)','low',true,'published',now()),
('qualification_type','other','Outra qualificação ou certificação','Descreva no campo de notas; a administração pode propor novo tipo no catálogo.','{}','Classificação inicial da plataforma','low',true,'published',now()),

('institutional_profile','ong_initiative','ONG / iniciativa social','Termo usual para iniciativa social; não é natureza jurídica.','{}','Classificação inicial da plataforma','high',false,'published',now()),
('institutional_profile','osc','OSC','Organização da sociedade civil (perfil de atuação).','{}','Classificação inicial da plataforma','high',false,'published',now()),
('institutional_profile','cultural','Organização cultural','','{}','Classificação inicial da plataforma','high',false,'published',now()),
('institutional_profile','health','Organização de saúde','','{}','Classificação inicial da plataforma','high',false,'published',now()),
('institutional_profile','education','Organização educacional','','{}','Classificação inicial da plataforma','high',false,'published',now()),
('institutional_profile','environmental','Organização ambiental','','{}','Classificação inicial da plataforma','high',false,'published',now()),
('institutional_profile','institute','Instituto','','{}','Classificação inicial da plataforma','high',false,'published',now()),
('institutional_profile','research_center','Centro de pesquisa','','{}','Classificação inicial da plataforma','high',false,'published',now()),
('institutional_profile','collective','Coletivo','','{}','Classificação inicial da plataforma','high',false,'published',now()),
('institutional_profile','impact_professional','Empreendedor/profissional de impacto','','{}','Classificação inicial da plataforma','high',false,'published',now()),
('institutional_profile','academic_institution','Universidade / instituição acadêmica','','{}','Classificação inicial da plataforma','high',false,'published',now()),
('institutional_profile','social_enterprise','Empresa social','','{}','Classificação inicial da plataforma','high',false,'published',now()),
('institutional_profile','other','Outro','','{}','Classificação inicial da plataforma','high',false,'published',now()),

('institutional_status','in_structuring','Em estruturação','Iniciativa ainda sem formalização completa.','{}','Classificação inicial da plataforma','high',false,'published',now()),
('institutional_status','registered','Cadastrada','Cadastro feito; situação ainda não revisada.','{}','Classificação inicial da plataforma','high',false,'published',now()),
('institutional_status','documents_pending','Documentação pendente','Há documentos exigidos ausentes, vencidos ou rejeitados.','{}','Classificação inicial da plataforma','high',false,'published',now()),
('institutional_status','regular','Regular','Documentação básica validada e sem pendências conhecidas, conforme revisão da administração.','{}','Classificação inicial da plataforma','high',false,'published',now()),
('institutional_status','partially_regular','Parcialmente regular','Parte dos requisitos cumprida; pendências conhecidas.','{}','Classificação inicial da plataforma','high',false,'published',now()),
('institutional_status','irregular','Irregular','Pendência relevante registrada pela administração.','{}','Classificação inicial da plataforma','high',false,'published',now()),
('institutional_status','under_review','Em análise','Revisão em andamento.','{}','Classificação inicial da plataforma','high',false,'published',now()),
('institutional_status','suspended','Suspensa','Participação suspensa por decisão da administração.','{}','Classificação inicial da plataforma','high',false,'published',now()),
('institutional_status','archived','Arquivada','Cadastro arquivado.','{}','Classificação inicial da plataforma','high',false,'published',now()),

('funding_modality','grant','Fomento / doação','Repasse não reembolsável conforme o instrumento do financiador.','{}','Classificação inicial da plataforma','medium',true,'published',now()),
('funding_modality','partnership_term','Parceria com a administração pública (termo de colaboração / fomento)','Instrumentos de parceria com OSC; requisitos conforme legislação vigente e edital.','{}','Lei nº 13.019/2014 (conferir texto vigente)','medium',true,'published',now()),
('funding_modality','management_contract','Contrato de gestão','Instrumento associado a organizações sociais; requisitos conforme legislação do ente.','{}','Lei nº 9.637/1998 (conferir texto vigente)','medium',true,'published',now()),
('funding_modality','agreement','Convênio','Instrumento de cooperação; requisitos conforme legislação do ente.','{}','Legislação do ente (informar)','low',true,'published',now()),
('funding_modality','incentive_law','Lei de incentivo (fiscal)','Mecanismos de incentivo fiscal; regras só valem quando publicadas e revisadas (ver motor fiscal).','{}','Legislação específica de cada mecanismo','low',true,'published',now()),
('funding_modality','sponsorship','Patrocínio','Patrocínio privado.','{}','Classificação inicial da plataforma','high',false,'published',now()),
('funding_modality','prize','Prêmio','Premiação.','{}','Classificação inicial da plataforma','high',false,'published',now()),
('funding_modality','social_investment','Investimento social privado','Investimento de empresas e fundações.','{}','Classificação inicial da plataforma','high',false,'published',now()),
('funding_modality','technical_cooperation','Cooperação técnica','Apoio sem repasse financeiro.','{}','Classificação inicial da plataforma','high',false,'published',now()),

('badge','org_verified','Organização verificada','Cadastro com compliance aprovado pela administração da plataforma.','{"scope":"organization","criterion":"compliance_approved","validity_days":365}','Critério interno da plataforma','high',false,'published',now()),
('badge','cnpj_validated','CNPJ validado','Comprovante de CNPJ enviado, aprovado no antivírus e validado por revisor.','{"scope":"organization","criterion":"document_validated","params":{"doc_types":["cartao_cnpj"]},"validity_days":365}','Critério interno da plataforma','high',false,'published',now()),
('badge','documents_verified','Documentação básica verificada','Estatuto/contrato social e comprovante de CNPJ validados e dentro da validade.','{"scope":"organization","criterion":"document_validated","params":{"doc_types":["estatuto_social","cartao_cnpj"]},"validity_days":365}','Critério interno da plataforma','high',false,'published',now()),
('badge','qualification_osc','OSC — qualificação verificada','Qualificação registrada, comprovada por documento e validada por revisor; dentro da validade, quando houver.','{"scope":"organization","criterion":"qualification_verified","params":{"type":"osc"},"validity_days":365}','Critério interno da plataforma','high',false,'published',now()),
('badge','qualification_oscip','OSCIP — qualificação verificada','Idem, para OSCIP.','{"scope":"organization","criterion":"qualification_verified","params":{"type":"oscip"},"validity_days":365}','Critério interno da plataforma','high',false,'published',now()),
('badge','qualification_os','OS — qualificação verificada','Idem, para OS.','{"scope":"organization","criterion":"qualification_verified","params":{"type":"os"},"validity_days":365}','Critério interno da plataforma','high',false,'published',now()),
('badge','certification_cebas','CEBAS — certificação verificada','Idem, para CEBAS (com validade).','{"scope":"organization","criterion":"qualification_verified","params":{"type":"cebas"},"validity_days":365}','Critério interno da plataforma','high',false,'published',now()),
('badge','eligibility_analyzed','Elegibilidade analisada','Organização com avaliação de elegibilidade registrada nos últimos 30 dias (não significa elegível).','{"scope":"organization","criterion":"eligibility_evaluated","validity_days":30}','Critério interno da plataforma','high',false,'published',now()),
('badge','project_verified','Projeto verificado','Solução com nível de confiança "verificado" concedido pela administração.','{"scope":"solution","criterion":"solution_trust","params":{"levels":["verified"]},"validity_days":365}','Critério interno da plataforma','high',false,'published',now()),
('badge','impact_proven','Impacto comprovado','Solução executada com evidência aceita e resultado validado por revisor independente.','{"scope":"solution","criterion":"solution_impact_proven","validity_days":365}','Critério interno da plataforma','high',false,'published',now()),
('badge','replicable_project','Projeto replicável','Solução executada, com replicação autorizada e perfil de replicabilidade com confiança suficiente.','{"scope":"solution","criterion":"solution_replicable","validity_days":365}','Critério interno da plataforma','high',false,'published',now()),
('badge','open_funding','Captação aberta','Solução publicada com busca de financiamento ativa.','{"scope":"solution","criterion":"solution_seeking_funding","validity_days":90}','Critério interno da plataforma','high',false,'published',now());

-- ===========================================================================================
-- 9. RLS
-- ===========================================================================================
DO $$ DECLARE t text; BEGIN
  FOREACH t IN ARRAY ARRAY['inst_catalog_items','eligibility_rules','organization_qualifications','organization_qualification_events','proponent_needs','eligibility_evaluations'] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
  END LOOP;
END $$;

CREATE POLICY catalog_read   ON inst_catalog_items FOR SELECT USING ((app_authenticated() AND status = 'published') OR app_priv());
CREATE POLICY catalog_insert ON inst_catalog_items FOR INSERT WITH CHECK (app_priv());
CREATE POLICY catalog_update ON inst_catalog_items FOR UPDATE USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY catalog_delete ON inst_catalog_items FOR DELETE USING (app_priv() AND status = 'draft');

CREATE POLICY elig_rules_read   ON eligibility_rules FOR SELECT USING ((app_authenticated() AND status = 'published') OR app_priv());
CREATE POLICY elig_rules_insert ON eligibility_rules FOR INSERT WITH CHECK (app_priv());
CREATE POLICY elig_rules_update ON eligibility_rules FOR UPDATE USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY elig_rules_delete ON eligibility_rules FOR DELETE USING (app_priv() AND status = 'draft');

-- qualificações verificadas são informação institucional pública; o restante é da organização e da administração
CREATE POLICY oq_read   ON organization_qualifications FOR SELECT USING (org_id = app_org() OR app_priv() OR (app_authenticated() AND verification_status = 'verified'));
CREATE POLICY oq_insert ON organization_qualifications FOR INSERT WITH CHECK ((org_id = app_org() AND declared_by = app_uid()) OR app_priv());
CREATE POLICY oq_update ON organization_qualifications FOR UPDATE USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY oq_delete ON organization_qualifications FOR DELETE USING ((org_id = app_org() AND verification_status IN ('declared','document_submitted','rejected')) OR app_priv());
CREATE POLICY oqe_read ON organization_qualification_events FOR SELECT USING (org_id = app_org() OR app_priv());

CREATE POLICY pn_read   ON proponent_needs FOR SELECT USING (org_id = app_org() OR app_priv() OR (solution_id IS NOT NULL AND status = 'open' AND app_solution_visible(solution_id)));
CREATE POLICY pn_insert ON proponent_needs FOR INSERT WITH CHECK ((org_id = app_org() AND created_by = app_uid()) OR app_priv());
CREATE POLICY pn_update ON proponent_needs FOR UPDATE USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY pn_delete ON proponent_needs FOR DELETE USING (org_id = app_org() OR app_priv());

CREATE POLICY ee_read   ON eligibility_evaluations FOR SELECT USING (org_id = app_org() OR viewer_org_id = app_org() OR app_priv());
CREATE POLICY ee_insert ON eligibility_evaluations FOR INSERT WITH CHECK ((viewer_org_id = app_org() AND created_by = app_uid()) OR app_priv());

-- Privilégios (mesmo modelo)
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO impacto_app;
REVOKE UPDATE, DELETE, TRUNCATE ON audit_events, ledger_entries, signatures, application_transitions, payment_events, solution_versions, solution_intent_events,
  organization_qualification_events, eligibility_evaluations FROM impacto_app;
REVOKE INSERT ON solution_versions, organization_qualification_events FROM impacto_app;
REVOKE ALL ON chain_heads FROM impacto_app;
REVOKE ALL ON schema_migrations FROM impacto_app;
GRANT SELECT ON schema_migrations TO impacto_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO impacto_app;
DO $$ DECLARE f regprocedure; BEGIN
  FOR f IN SELECT p.oid::regprocedure FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'public' AND pg_get_userbyid(p.proowner) = current_user LOOP
    EXECUTE format('REVOKE EXECUTE ON FUNCTION %s FROM PUBLIC', f);
    EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO impacto_app', f);
  END LOOP;
END $$;
