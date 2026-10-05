-- 0007 — v0.10.1: perfis OS/OSCIP (instrumentos de parceria/contratos de gestão, áreas de atuação), trilha de formalização e pedidos de mentoria.
-- Mesmos princípios da 0006: declarado ≠ verificado; só a administração verifica; nada de regra legal embutida.

ALTER TABLE organization_qualifications
  ADD COLUMN areas text[] NOT NULL DEFAULT '{}';       -- áreas de atuação autorizadas/declaradas na qualificação (ex.: saude, educacao, cultura)

-- Instrumentos firmados com o poder público ou parceiros (contrato de gestão, termo de parceria, termo de fomento/colaboração, acordo de cooperação)
CREATE TABLE organization_agreements (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id              uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  agreement_type      text NOT NULL CHECK (agreement_type IN ('management_contract','partnership_term','collaboration_term','fomento_term','cooperation_agreement','other')),
  counterpart_name    text NOT NULL CHECK (length(counterpart_name) BETWEEN 2 AND 300),
  counterpart_authority text CHECK (length(counterpart_authority) <= 300),     -- ente/autoridade (ex.: Secretaria Estadual de Saúde)
  instrument_number   text CHECK (length(instrument_number) <= 120),
  object_summary      text CHECK (length(object_summary) <= 2000),
  start_date          date,
  end_date            date,
  value_cents         bigint CHECK (value_cents IS NULL OR value_cents >= 0),
  agreement_status    text NOT NULL DEFAULT 'active' CHECK (agreement_status IN ('draft','active','completed','terminated','suspended')),
  qualification_id    uuid REFERENCES organization_qualifications(id) ON DELETE SET NULL,
  verification_url    text CHECK (verification_url IS NULL OR verification_url ~ '^https://'),
  document_id         uuid REFERENCES documents(id) ON DELETE SET NULL,
  verification_status text NOT NULL DEFAULT 'declared' CHECK (verification_status IN ('declared','document_submitted','verified','rejected')),
  validated_by        uuid REFERENCES users(id),
  validation_date     date,
  validation_note     text CHECK (length(validation_note) <= 1000),
  created_by          uuid REFERENCES users(id),
  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now(),
  CHECK (end_date IS NULL OR start_date IS NULL OR end_date >= start_date),
  CHECK (verification_status <> 'verified' OR (validated_by IS NOT NULL AND validation_date IS NOT NULL))
);
CREATE INDEX ix_org_agreements_org ON organization_agreements(org_id, agreement_status);
CREATE INDEX ix_org_agreements_queue ON organization_agreements(verification_status) WHERE verification_status = 'document_submitted';

CREATE FUNCTION agreement_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF current_user::text = 'impacto_app' AND NOT app_priv() THEN
    IF TG_OP = 'INSERT' THEN
      NEW.verification_status := CASE WHEN NEW.document_id IS NOT NULL THEN 'document_submitted' ELSE 'declared' END;
      NEW.validated_by := NULL; NEW.validation_date := NULL; NEW.validation_note := NULL;
    ELSE
      IF NEW.verification_status IS DISTINCT FROM OLD.verification_status OR NEW.validated_by IS DISTINCT FROM OLD.validated_by
         OR NEW.validation_date IS DISTINCT FROM OLD.validation_date OR NEW.validation_note IS DISTINCT FROM OLD.validation_note
         OR NEW.org_id IS DISTINCT FROM OLD.org_id THEN
        RAISE EXCEPTION 'verificação de instrumento só pode ser alterada pela administração' USING ERRCODE = '42501';
      END IF;
      IF OLD.verification_status = 'verified' AND (NEW.instrument_number IS DISTINCT FROM OLD.instrument_number OR NEW.counterpart_name IS DISTINCT FROM OLD.counterpart_name
         OR NEW.start_date IS DISTINCT FROM OLD.start_date OR NEW.end_date IS DISTINCT FROM OLD.end_date OR NEW.value_cents IS DISTINCT FROM OLD.value_cents
         OR NEW.document_id IS DISTINCT FROM OLD.document_id OR NEW.agreement_type IS DISTINCT FROM OLD.agreement_type) THEN
        NEW.verification_status := CASE WHEN NEW.document_id IS NOT NULL THEN 'document_submitted' ELSE 'declared' END;
        NEW.validated_by := NULL; NEW.validation_date := NULL;
      ELSIF OLD.verification_status = 'declared' AND NEW.document_id IS NOT NULL AND OLD.document_id IS NULL THEN
        NEW.verification_status := 'document_submitted';
      END IF;
    END IF;
  END IF;
  NEW.updated_at := now();
  RETURN NEW;
END $$;
CREATE TRIGGER trg_agreement_guard BEFORE INSERT OR UPDATE ON organization_agreements FOR EACH ROW EXECUTE FUNCTION agreement_guard();

-- Etapas manuais da trilha de formalização (as automáticas são derivadas dos fatos; nada aqui vira "verificado" sem a administração)
CREATE TABLE formalization_steps (
  org_id     uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  step_code  text NOT NULL CHECK (step_code ~ '^[a-z0-9_]{2,60}$'),
  state      text NOT NULL DEFAULT 'in_progress' CHECK (state IN ('not_started','in_progress','done_declared')),
  note       text CHECK (length(note) <= 1000),
  updated_by uuid REFERENCES users(id),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (org_id, step_code)
);

-- Pedidos de mentoria (atendimento humano; sem promessa de prazo)
CREATE TABLE mentoring_requests (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id      uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  topic       text NOT NULL CHECK (topic IN ('formalization','documentation','project','fundraising','accountability','institutional','other')),
  message     text NOT NULL CHECK (length(message) BETWEEN 10 AND 2000),
  status      text NOT NULL DEFAULT 'open' CHECK (status IN ('open','in_progress','scheduled','done','cancelled')),
  admin_note  text CHECK (length(admin_note) <= 2000),
  handled_by  uuid REFERENCES users(id),
  created_by  uuid REFERENCES users(id),
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_mentoring_org ON mentoring_requests(org_id, status);
CREATE INDEX ix_mentoring_queue ON mentoring_requests(status) WHERE status IN ('open','in_progress');

CREATE FUNCTION mentoring_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF current_user::text = 'impacto_app' AND NOT app_priv() THEN
    IF TG_OP = 'INSERT' THEN
      NEW.status := 'open'; NEW.admin_note := NULL; NEW.handled_by := NULL;
    ELSE
      IF NEW.admin_note IS DISTINCT FROM OLD.admin_note OR NEW.handled_by IS DISTINCT FROM OLD.handled_by OR NEW.org_id IS DISTINCT FROM OLD.org_id
         OR (NEW.status IS DISTINCT FROM OLD.status AND NEW.status <> 'cancelled') THEN
        RAISE EXCEPTION 'andamento do pedido de mentoria só pode ser alterado pela administração (a organização pode cancelar)' USING ERRCODE = '42501';
      END IF;
    END IF;
  END IF;
  NEW.updated_at := now();
  RETURN NEW;
END $$;
CREATE TRIGGER trg_mentoring_guard BEFORE INSERT OR UPDATE ON mentoring_requests FOR EACH ROW EXECUTE FUNCTION mentoring_guard();

-- RLS
ALTER TABLE organization_agreements ENABLE ROW LEVEL SECURITY;
ALTER TABLE formalization_steps ENABLE ROW LEVEL SECURITY;
ALTER TABLE mentoring_requests ENABLE ROW LEVEL SECURITY;

-- instrumento verificado é informação institucional pública; o restante é da organização e da administração
CREATE POLICY oa_read   ON organization_agreements FOR SELECT USING (org_id = app_org() OR app_priv() OR (app_authenticated() AND verification_status = 'verified'));
CREATE POLICY oa_insert ON organization_agreements FOR INSERT WITH CHECK ((org_id = app_org() AND created_by = app_uid()) OR app_priv());
CREATE POLICY oa_update ON organization_agreements FOR UPDATE USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY oa_delete ON organization_agreements FOR DELETE USING ((org_id = app_org() AND verification_status IN ('declared','document_submitted','rejected')) OR app_priv());

CREATE POLICY fs_read   ON formalization_steps FOR SELECT USING (org_id = app_org() OR app_priv());
CREATE POLICY fs_insert ON formalization_steps FOR INSERT WITH CHECK ((org_id = app_org() AND updated_by = app_uid()) OR app_priv());
CREATE POLICY fs_update ON formalization_steps FOR UPDATE USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY fs_delete ON formalization_steps FOR DELETE USING (org_id = app_org() OR app_priv());

CREATE POLICY mr_read   ON mentoring_requests FOR SELECT USING (org_id = app_org() OR app_priv());
CREATE POLICY mr_insert ON mentoring_requests FOR INSERT WITH CHECK ((org_id = app_org() AND created_by = app_uid()) OR app_priv());
CREATE POLICY mr_update ON mentoring_requests FOR UPDATE USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());

-- Privilégios (mesmo modelo da 0006)
GRANT SELECT, INSERT, UPDATE, DELETE ON organization_agreements, formalization_steps, mentoring_requests TO impacto_app;
DO $$ DECLARE f regprocedure; BEGIN
  FOR f IN SELECT p.oid::regprocedure FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'public' AND pg_get_userbyid(p.proowner) = current_user LOOP
    EXECUTE format('REVOKE EXECUTE ON FUNCTION %s FROM PUBLIC', f);
    EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO impacto_app', f);
  END LOOP;
END $$;
