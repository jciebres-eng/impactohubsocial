-- 0002_security.sql — Funções de contexto, triggers de integridade, RLS e privilégios.
-- Modelo: a aplicação conecta como `impacto_app` (NOSUPERUSER, NOBYPASSRLS, não-dona das tabelas).
-- RLS é a 2ª camada (defesa em profundidade) — a 1ª é a autorização por objeto na API.

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'impacto_app') THEN
    RAISE EXCEPTION 'Papel impacto_app ausente: execute infra/db/bootstrap.sql antes das migrations';
  END IF;
END $$;

-- ===========================================================================================
-- Contexto da requisição (definido por transação em impacto/db/pool.py)
-- ===========================================================================================
CREATE FUNCTION app_uid() RETURNS uuid LANGUAGE sql STABLE AS
$$ SELECT nullif(current_setting('app.user_id', true), '')::uuid $$;
CREATE FUNCTION app_org() RETURNS uuid LANGUAGE sql STABLE AS
$$ SELECT nullif(current_setting('app.org_id', true), '')::uuid $$;
CREATE FUNCTION app_kind() RETURNS text LANGUAGE sql STABLE AS
$$ SELECT coalesce(current_setting('app.org_kind', true), '') $$;
CREATE FUNCTION app_admin() RETURNS boolean LANGUAGE sql STABLE AS
$$ SELECT coalesce(current_setting('app.platform_admin', true), 'off') = 'on' $$;
CREATE FUNCTION app_system() RETURNS boolean LANGUAGE sql STABLE AS
$$ SELECT coalesce(current_setting('app.system', true), 'off') = 'on' $$;
CREATE FUNCTION app_priv() RETURNS boolean LANGUAGE sql STABLE AS
$$ SELECT app_admin() OR app_system() $$;
CREATE FUNCTION app_authenticated() RETURNS boolean LANGUAGE sql STABLE AS
$$ SELECT app_uid() IS NOT NULL $$;

-- ===========================================================================================
-- Funções auxiliares SECURITY DEFINER (evitam recursão entre políticas; leem como dono)
-- ===========================================================================================
CREATE FUNCTION app_project_owner(pid uuid) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS
$$ SELECT EXISTS (SELECT 1 FROM projects p WHERE p.id = pid AND p.org_id = app_org()) $$;

CREATE FUNCTION app_project_party(pid uuid) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS
$$ SELECT EXISTS (SELECT 1 FROM applications a WHERE a.project_id = pid AND a.funder_org_id = app_org()
                  AND a.status <> 'withdrawn') $$;

CREATE FUNCTION app_project_investor(pid uuid) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS
$$ SELECT EXISTS (SELECT 1 FROM commitments c WHERE c.project_id = pid AND c.funder_org_id = app_org()
                  AND c.status <> 'cancelled') $$;

CREATE FUNCTION app_osc_counterparty(osc uuid) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS
$$ SELECT EXISTS (SELECT 1 FROM applications a WHERE a.osc_org_id = osc AND a.funder_org_id = app_org()
                  AND a.status <> 'withdrawn') $$;

CREATE FUNCTION app_review_access(stype text, sid uuid) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS
$$ SELECT EXISTS (SELECT 1 FROM professional_reviews r WHERE r.professional_org_id = app_org()
                  AND r.subject_type = stype AND r.subject_id = sid
                  AND r.status IN ('requested','accepted','changes_requested','approved','signed')) $$;

CREATE FUNCTION app_document_access(d_id uuid, d_org uuid, d_project uuid, d_application uuid, d_visibility text)
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
  SELECT
    -- financiador em diligência (ou etapa posterior) com a OSC dona do documento
    EXISTS (SELECT 1 FROM applications a
             WHERE a.funder_org_id = app_org() AND a.osc_org_id = d_org
               AND a.status IN ('due_diligence','approved','committed','in_execution','reporting','closed')
               AND (d_project IS NULL OR a.project_id = d_project))
    -- documento compartilhado com as partes do projeto (investidores)
    OR (d_visibility = 'parties' AND d_project IS NOT NULL AND app_project_investor(d_project))
    -- profissional parceiro com revisão ativa sobre o documento, projeto ou candidatura
    OR app_review_access('document', d_id)
    OR (d_project IS NOT NULL AND app_review_access('project', d_project))
    OR (d_application IS NOT NULL AND app_review_access('application', d_application))
$$;

-- Notificação entre organizações (ex.: financiador avisa OSC). Exige usuário autenticado.
CREATE FUNCTION app_notify(p_org uuid, p_user uuid, p_kind text, p_title text, p_body text, p_link text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE nid uuid;
BEGIN
  IF app_uid() IS NULL AND NOT app_system() THEN
    RAISE EXCEPTION 'notificação exige contexto autenticado' USING ERRCODE = '42501';
  END IF;
  INSERT INTO notifications(org_id, user_id, kind, title, body, link)
  VALUES (p_org, p_user, p_kind, left(p_title, 200), left(p_body, 2000), p_link) RETURNING id INTO nid;
  RETURN nid;
END $$;

-- Dados agregados e anonimizados para governo (k-anonimato mínimo por grupo).
CREATE FUNCTION gov_territory_stats(p_prefix text, p_min_group integer DEFAULT 3)
RETURNS TABLE(territory text, cause text, projects bigint, beneficiaries bigint, committed_cents bigint,
              accepted_evidences bigint)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
  IF NOT (app_kind() IN ('government','platform') OR app_priv()) THEN
    RAISE EXCEPTION 'acesso restrito a órgãos de governo' USING ERRCODE = '42501';
  END IF;
  IF p_min_group < 3 THEN p_min_group := 3; END IF;
  RETURN QUERY
  SELECT p.territory, c.cause, count(DISTINCT p.id), coalesce(sum(p.beneficiaries_count), 0)::bigint,
         coalesce(sum((SELECT coalesce(sum(cm.amount_cents),0) FROM commitments cm
                        WHERE cm.project_id = p.id AND cm.status <> 'cancelled')), 0)::bigint,
         coalesce(sum((SELECT count(*) FROM evidences e WHERE e.project_id = p.id AND e.status = 'accepted')), 0)::bigint
    FROM projects p CROSS JOIN LATERAL unnest(CASE WHEN cardinality(p.causes) = 0 THEN ARRAY['nao_informada'] ELSE p.causes END) AS c(cause)
   WHERE p.visibility = 'published' AND p.territory LIKE p_prefix || '%'
   GROUP BY p.territory, c.cause
  HAVING count(DISTINCT p.id) >= p_min_group;
END $$;

-- ===========================================================================================
-- Triggers de integridade
-- ===========================================================================================
CREATE FUNCTION touch_updated_at() RETURNS trigger LANGUAGE plpgsql AS
$$ BEGIN NEW.updated_at := now(); RETURN NEW; END $$;

DO $$ DECLARE t text; BEGIN
  FOREACH t IN ARRAY ARRAY['organizations','users','calls','projects','applications','subscriptions','drafts',
                           'professional_reviews','funder_profiles','provider_profiles','company_tax_profiles','plans'] LOOP
    EXECUTE format('CREATE TRIGGER trg_touch BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION touch_updated_at()', t);
  END LOOP;
END $$;

-- Tabelas append-only
CREATE FUNCTION forbid_mutation() RETURNS trigger LANGUAGE plpgsql AS
$$ BEGIN RAISE EXCEPTION '% é append-only', TG_TABLE_NAME USING ERRCODE = '42501'; END $$;
CREATE TRIGGER trg_append_only BEFORE UPDATE OR DELETE ON audit_events FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
CREATE TRIGGER trg_append_only BEFORE UPDATE OR DELETE ON ledger_entries FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
CREATE TRIGGER trg_append_only BEFORE UPDATE OR DELETE ON signatures FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
CREATE TRIGGER trg_append_only BEFORE UPDATE OR DELETE ON application_transitions FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

-- Encadeamento por hash: auditoria (por organização) e ledger de impacto (por projeto)
CREATE FUNCTION ts_canonical(t timestamptz) RETURNS text LANGUAGE sql IMMUTABLE AS
$$ SELECT to_char(t AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"') $$;

CREATE FUNCTION audit_material(e audit_events) RETURNS text LANGUAGE sql IMMUTABLE AS $$
  SELECT concat_ws('|', e.prev_hash, e.seq::text, coalesce(e.org_id::text,''), coalesce(e.actor_user_id::text,''),
                   e.action, coalesce(e.object_type,''), coalesce(e.object_id,''), e.payload::text, ts_canonical(e.at))
$$;
CREATE FUNCTION ledger_material(e ledger_entries) RETURNS text LANGUAGE sql IMMUTABLE AS $$
  SELECT concat_ws('|', e.prev_hash, e.seq::text, e.project_id::text, e.org_id::text, coalesce(e.actor_user_id::text,''),
                   e.entry_type, coalesce(e.amount_cents::text,''), coalesce(e.ref_type,''), coalesce(e.ref_id::text,''),
                   e.payload::text, ts_canonical(e.at))
$$;

CREATE FUNCTION chain_audit() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE k text; s bigint; prev char(64);
BEGIN
  k := 'audit:' || coalesce(NEW.org_id::text, 'platform');
  INSERT INTO chain_heads(chain_key, last_seq, last_hash) VALUES (k, 0, repeat('0', 64)) ON CONFLICT DO NOTHING;
  SELECT last_seq, last_hash INTO s, prev FROM chain_heads WHERE chain_key = k FOR UPDATE;
  NEW.at := date_trunc('microseconds', now());
  NEW.seq := s + 1; NEW.prev_hash := prev;
  NEW.event_hash := encode(digest(audit_material(NEW), 'sha256'), 'hex');
  UPDATE chain_heads SET last_seq = NEW.seq, last_hash = NEW.event_hash WHERE chain_key = k;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_chain BEFORE INSERT ON audit_events FOR EACH ROW EXECUTE FUNCTION chain_audit();

CREATE FUNCTION chain_ledger() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE k text; s bigint; prev char(64);
BEGIN
  k := 'ledger:' || NEW.project_id::text;
  INSERT INTO chain_heads(chain_key, last_seq, last_hash) VALUES (k, 0, repeat('0', 64)) ON CONFLICT DO NOTHING;
  SELECT last_seq, last_hash INTO s, prev FROM chain_heads WHERE chain_key = k FOR UPDATE;
  NEW.at := date_trunc('microseconds', now());
  NEW.seq := s + 1; NEW.prev_hash := prev;
  NEW.entry_hash := encode(digest(ledger_material(NEW), 'sha256'), 'hex');
  UPDATE chain_heads SET last_seq = NEW.seq, last_hash = NEW.entry_hash WHERE chain_key = k;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_chain BEFORE INSERT ON ledger_entries FOR EACH ROW EXECUTE FUNCTION chain_ledger();

-- Verificação (SECURITY INVOKER: só verifica o que o chamador pode ler)
CREATE FUNCTION ledger_verify(p_project uuid) RETURNS TABLE(entries bigint, valid boolean, first_broken_seq bigint)
LANGUAGE plpgsql STABLE AS $$
DECLARE r ledger_entries; expected_prev char(64) := repeat('0', 64); n bigint := 0; broken bigint := NULL;
BEGIN
  FOR r IN SELECT * FROM ledger_entries WHERE project_id = p_project ORDER BY seq LOOP
    n := n + 1;
    IF broken IS NULL AND (r.prev_hash <> expected_prev OR r.seq <> n
        OR r.entry_hash <> encode(digest(ledger_material(r), 'sha256'), 'hex')) THEN
      broken := r.seq;
    END IF;
    expected_prev := r.entry_hash;
  END LOOP;
  RETURN QUERY SELECT n, broken IS NULL, broken;
END $$;

CREATE FUNCTION audit_verify(p_org uuid) RETURNS TABLE(entries bigint, valid boolean, first_broken_seq bigint)
LANGUAGE plpgsql STABLE AS $$
DECLARE r audit_events; expected_prev char(64) := repeat('0', 64); n bigint := 0; broken bigint := NULL;
BEGIN
  FOR r IN SELECT * FROM audit_events WHERE org_id IS NOT DISTINCT FROM p_org ORDER BY seq LOOP
    n := n + 1;
    IF broken IS NULL AND (r.prev_hash <> expected_prev OR r.seq <> n
        OR r.event_hash <> encode(digest(audit_material(r), 'sha256'), 'hex')) THEN
      broken := r.seq;
    END IF;
    expected_prev := r.event_hash;
  END LOOP;
  RETURN QUERY SELECT n, broken IS NULL, broken;
END $$;

-- Colunas privilegiadas: só admin/sistema (ou funções SECURITY DEFINER) podem alterar.
CREATE FUNCTION guard_columns() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE col text;
BEGIN
  IF current_user::text <> 'impacto_app' OR app_priv() THEN RETURN NEW; END IF;
  FOREACH col IN ARRAY TG_ARGV LOOP
    IF TG_OP = 'INSERT' THEN
      CONTINUE;
    END IF;
    IF (to_jsonb(NEW) -> col) IS DISTINCT FROM (to_jsonb(OLD) -> col) THEN
      RAISE EXCEPTION 'coluna %.% só pode ser alterada pela administração', TG_TABLE_NAME, col USING ERRCODE = '42501';
    END IF;
  END LOOP;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_guard BEFORE UPDATE ON organizations FOR EACH ROW
  EXECUTE FUNCTION guard_columns('kind','status','compliance_status','compliance_risk','compliance_reviewed_at');
CREATE TRIGGER trg_guard BEFORE UPDATE ON users FOR EACH ROW
  EXECUTE FUNCTION guard_columns('is_platform_admin','status','email_verified_at','failed_login_count','locked_until');
CREATE TRIGGER trg_guard BEFORE UPDATE ON professional_credentials FOR EACH ROW
  EXECUTE FUNCTION guard_columns('verification_status','verified_by','verified_at','verification_note');
CREATE TRIGGER trg_guard BEFORE UPDATE ON calls FOR EACH ROW
  EXECUTE FUNCTION guard_columns('last_verified_at','verified_by','is_example','source_type');
CREATE TRIGGER trg_guard BEFORE UPDATE ON milestones FOR EACH ROW
  EXECUTE FUNCTION guard_columns('funded_cents');
CREATE TRIGGER trg_guard BEFORE UPDATE ON documents FOR EACH ROW
  EXECUTE FUNCTION guard_columns('status','scan_engine','scanned_at','sha256','storage_key','size_bytes');

-- Novos registros de credencial e documento nascem em estado não verificado.
CREATE FUNCTION force_initial_state() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF current_user::text <> 'impacto_app' OR app_priv() THEN RETURN NEW; END IF;
  IF TG_TABLE_NAME = 'professional_credentials' THEN
    IF NEW.verification_status NOT IN ('self_declared','document_submitted') THEN
      NEW.verification_status := 'self_declared';
    END IF;
    NEW.verified_by := NULL; NEW.verified_at := NULL;
  ELSIF TG_TABLE_NAME = 'organizations' THEN
    NEW.compliance_status := 'pending'; NEW.compliance_risk := NULL;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_initial BEFORE INSERT ON professional_credentials FOR EACH ROW EXECUTE FUNCTION force_initial_state();

-- Revisão de evidências/despesas: a própria OSC não aprova a si mesma.
CREATE FUNCTION guard_self_review() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF current_user::text <> 'impacto_app' OR app_priv() THEN RETURN NEW; END IF;
  IF NEW.status IS DISTINCT FROM OLD.status AND NEW.status IN ('accepted','rejected','needs_info','validated','questioned')
     AND app_org() = NEW.org_id THEN
    RAISE EXCEPTION 'a organização executora não pode revisar o próprio registro' USING ERRCODE = '42501';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_self_review BEFORE UPDATE ON evidences FOR EACH ROW EXECUTE FUNCTION guard_self_review();
CREATE TRIGGER trg_self_review BEFORE UPDATE ON expenses FOR EACH ROW EXECUTE FUNCTION guard_self_review();

-- Compromissos: valor total não excede o orçamento do projeto; marcos acompanham o captado.
CREATE FUNCTION commitments_integrity() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE budget bigint; total bigint; ms_amount bigint; ms_total bigint;
BEGIN
  SELECT budget_total_cents INTO budget FROM projects WHERE id = NEW.project_id FOR UPDATE;
  SELECT coalesce(sum(amount_cents), 0) INTO total FROM commitments
   WHERE project_id = NEW.project_id AND status <> 'cancelled' AND id <> NEW.id;
  IF NEW.status <> 'cancelled' THEN total := total + NEW.amount_cents; END IF;
  IF total > budget THEN
    RAISE EXCEPTION 'compromissos (%) excedem o orçamento do projeto (%)', total, budget USING ERRCODE = '23514';
  END IF;
  IF NEW.milestone_id IS NOT NULL THEN
    SELECT amount_cents INTO ms_amount FROM milestones WHERE id = NEW.milestone_id AND project_id = NEW.project_id;
    IF ms_amount IS NULL THEN
      RAISE EXCEPTION 'marco não pertence ao projeto' USING ERRCODE = '23503';
    END IF;
  END IF;
  -- Transições de status por parte: desembolso informado pelo financiador, confirmação pela OSC.
  IF TG_OP = 'UPDATE' AND current_setting('app.system', true) IS DISTINCT FROM 'on'
     AND current_setting('app.platform_admin', true) IS DISTINCT FROM 'on' THEN
    IF NEW.status IS DISTINCT FROM OLD.status THEN
      IF NEW.status = 'confirmed' AND app_org() <> NEW.osc_org_id THEN
        RAISE EXCEPTION 'apenas a OSC confirma o recebimento' USING ERRCODE = '42501';
      END IF;
      IF NEW.status IN ('disbursed','cancelled') AND app_org() <> NEW.funder_org_id THEN
        RAISE EXCEPTION 'apenas o financiador informa desembolso/cancelamento' USING ERRCODE = '42501';
      END IF;
    END IF;
    IF NEW.amount_cents <> OLD.amount_cents AND OLD.status <> 'pledged' THEN
      RAISE EXCEPTION 'valor não pode mudar após desembolso' USING ERRCODE = '42501';
    END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_commitments_integrity BEFORE INSERT OR UPDATE ON commitments FOR EACH ROW EXECUTE FUNCTION commitments_integrity();

CREATE FUNCTION commitments_rollup() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE mid uuid;
BEGIN
  FOR mid IN SELECT DISTINCT x FROM unnest(ARRAY[NEW.milestone_id, CASE WHEN TG_OP = 'UPDATE' THEN OLD.milestone_id END]) x WHERE x IS NOT NULL LOOP
    UPDATE milestones m SET funded_cents = (SELECT coalesce(sum(amount_cents), 0) FROM commitments
                                             WHERE milestone_id = mid AND status <> 'cancelled'),
                            status = CASE WHEN m.status IN ('planned','open','funded')
                                          THEN CASE WHEN (SELECT coalesce(sum(amount_cents), 0) FROM commitments
                                                          WHERE milestone_id = mid AND status <> 'cancelled') >= m.amount_cents
                                                    THEN 'funded' ELSE 'open' END
                                          ELSE m.status END
     WHERE m.id = mid;
  END LOOP;
  RETURN NULL;
END $$;
CREATE TRIGGER trg_commitments_rollup AFTER INSERT OR UPDATE ON commitments FOR EACH ROW EXECUTE FUNCTION commitments_rollup();

-- Orçamento total do projeto = soma dos itens (quando houver itens).
CREATE FUNCTION budget_rollup() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE pid uuid := coalesce(NEW.project_id, OLD.project_id);
BEGIN
  UPDATE projects SET budget_total_cents = (SELECT coalesce(sum(total_cents), 0) FROM budget_items WHERE project_id = pid)
   WHERE id = pid;
  RETURN NULL;
END $$;
CREATE TRIGGER trg_budget_rollup AFTER INSERT OR UPDATE OR DELETE ON budget_items FOR EACH ROW EXECUTE FUNCTION budget_rollup();

-- Filhos sempre pertencem à mesma organização do projeto.
CREATE FUNCTION child_org_matches_project() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM projects WHERE id = NEW.project_id AND org_id = NEW.org_id) THEN
    RAISE EXCEPTION 'registro deve pertencer à organização dona do projeto' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_child_org BEFORE INSERT OR UPDATE ON budget_items FOR EACH ROW EXECUTE FUNCTION child_org_matches_project();
CREATE TRIGGER trg_child_org BEFORE INSERT OR UPDATE ON milestones FOR EACH ROW EXECUTE FUNCTION child_org_matches_project();
CREATE TRIGGER trg_child_org BEFORE INSERT OR UPDATE ON expenses FOR EACH ROW EXECUTE FUNCTION child_org_matches_project();
CREATE TRIGGER trg_child_org BEFORE INSERT OR UPDATE ON evidences FOR EACH ROW EXECUTE FUNCTION child_org_matches_project();

-- ===========================================================================================
-- Row Level Security
-- ===========================================================================================
DO $$ DECLARE t text; BEGIN
  FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename <> 'schema_migrations' LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
  END LOOP;
END $$;

-- Identidade ------------------------------------------------------------------------------
CREATE POLICY org_read ON organizations FOR SELECT USING (app_authenticated() OR app_priv());
CREATE POLICY org_insert ON organizations FOR INSERT WITH CHECK (app_priv());
CREATE POLICY org_update ON organizations FOR UPDATE USING (id = app_org() OR app_priv()) WITH CHECK (id = app_org() OR app_priv());

CREATE POLICY users_read ON users FOR SELECT USING (
  id = app_uid() OR app_priv()
  OR EXISTS (SELECT 1 FROM memberships m WHERE m.user_id = users.id AND m.org_id = app_org()));
CREATE POLICY users_insert ON users FOR INSERT WITH CHECK (app_priv());
CREATE POLICY users_update ON users FOR UPDATE USING (id = app_uid() OR app_priv()) WITH CHECK (id = app_uid() OR app_priv());

CREATE POLICY memberships_read ON memberships FOR SELECT USING (org_id = app_org() OR user_id = app_uid() OR app_priv());
CREATE POLICY memberships_write ON memberships FOR ALL USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());

CREATE POLICY invitations_all ON invitations FOR ALL USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY sessions_all ON sessions FOR ALL USING (user_id = app_uid() OR app_priv()) WITH CHECK (user_id = app_uid() OR app_priv());
CREATE POLICY auth_tokens_sys ON auth_tokens FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY rate_events_sys ON rate_events FOR ALL USING (app_system()) WITH CHECK (app_system());
CREATE POLICY oidc_states_sys ON oidc_states FOR ALL USING (app_system()) WITH CHECK (app_system());
CREATE POLICY consents_all ON consents FOR ALL USING (user_id = app_uid() OR app_priv()) WITH CHECK (user_id = app_uid() OR app_priv());
CREATE POLICY privacy_all ON privacy_requests FOR ALL USING (user_id = app_uid() OR app_priv()) WITH CHECK (user_id = app_uid() OR app_priv());

-- Perfis -------------------------------------------------------------------------------------
CREATE POLICY funder_profiles_read ON funder_profiles FOR SELECT USING (app_authenticated() OR app_priv());
CREATE POLICY funder_profiles_write ON funder_profiles FOR ALL USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY provider_profiles_read ON provider_profiles FOR SELECT USING (app_authenticated() OR app_priv());
CREATE POLICY provider_profiles_write ON provider_profiles FOR ALL USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY credentials_read ON professional_credentials FOR SELECT USING (app_authenticated() OR app_priv());
CREATE POLICY credentials_write ON professional_credentials FOR ALL USING (org_id = app_org() OR app_priv())
  WITH CHECK ((org_id = app_org() AND user_id = app_uid()) OR app_priv());

-- Catálogo -----------------------------------------------------------------------------------
CREATE POLICY calls_read ON calls FOR SELECT USING (
  (app_authenticated() AND status IN ('open','closed')) OR owner_org_id = app_org() OR app_priv());
CREATE POLICY calls_insert ON calls FOR INSERT WITH CHECK (
  (owner_org_id = app_org() AND app_kind() IN ('company','government') AND source_type IN ('platform','government')) OR app_priv());
CREATE POLICY calls_update ON calls FOR UPDATE USING (owner_org_id = app_org() OR app_priv()) WITH CHECK (owner_org_id = app_org() OR app_priv());
CREATE POLICY calls_delete ON calls FOR DELETE USING (app_priv());
CREATE POLICY call_sources_admin ON call_sources FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY saved_searches_all ON saved_searches FOR ALL USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY saved_search_hits_all ON saved_search_hits FOR ALL USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY notifications_read ON notifications FOR SELECT USING (
  (org_id = app_org() AND (user_id IS NULL OR user_id = app_uid())) OR app_priv());
CREATE POLICY notifications_update ON notifications FOR UPDATE USING (
  (org_id = app_org() AND (user_id IS NULL OR user_id = app_uid())) OR app_priv());
CREATE POLICY notifications_insert ON notifications FOR INSERT WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY materials_read ON materials FOR SELECT USING ((app_authenticated() AND status = 'published') OR org_id = app_org() OR app_priv());
CREATE POLICY materials_write ON materials FOR ALL USING (org_id = app_org() OR app_priv())
  WITH CHECK ((org_id = app_org() AND app_kind() IN ('government','platform')) OR app_priv());

-- Projetos -----------------------------------------------------------------------------------
CREATE POLICY projects_read ON projects FOR SELECT USING (
  org_id = app_org() OR (visibility = 'published' AND app_authenticated())
  OR app_project_party(id) OR app_review_access('project', id) OR app_priv());
CREATE POLICY projects_insert ON projects FOR INSERT WITH CHECK ((org_id = app_org() AND app_kind() = 'osc') OR app_priv());
CREATE POLICY projects_update ON projects FOR UPDATE USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY projects_delete ON projects FOR DELETE USING ((org_id = app_org() AND status = 'draft') OR app_priv());

CREATE POLICY budget_items_read ON budget_items FOR SELECT USING (EXISTS (SELECT 1 FROM projects p WHERE p.id = project_id));
CREATE POLICY budget_items_write ON budget_items FOR ALL USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY milestones_read ON milestones FOR SELECT USING (EXISTS (SELECT 1 FROM projects p WHERE p.id = project_id));
CREATE POLICY milestones_write ON milestones FOR ALL USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());

-- Candidaturas -------------------------------------------------------------------------------
CREATE POLICY applications_read ON applications FOR SELECT USING (
  osc_org_id = app_org() OR funder_org_id = app_org() OR app_review_access('application', id) OR app_priv());
CREATE POLICY applications_insert ON applications FOR INSERT WITH CHECK (
  (osc_org_id = app_org() AND origin IN ('osc_application','external_tracking'))
  OR (funder_org_id = app_org() AND origin = 'funder_interest') OR app_priv());
CREATE POLICY applications_update ON applications FOR UPDATE USING (osc_org_id = app_org() OR funder_org_id = app_org() OR app_priv())
  WITH CHECK (osc_org_id = app_org() OR funder_org_id = app_org() OR app_priv());

CREATE POLICY app_steps_read ON application_steps FOR SELECT USING (EXISTS (SELECT 1 FROM applications a WHERE a.id = application_id));
CREATE POLICY app_steps_write ON application_steps FOR ALL
  USING (EXISTS (SELECT 1 FROM applications a WHERE a.id = application_id AND (a.osc_org_id = app_org() OR a.funder_org_id = app_org())) OR app_priv())
  WITH CHECK (EXISTS (SELECT 1 FROM applications a WHERE a.id = application_id AND (a.osc_org_id = app_org() OR a.funder_org_id = app_org())) OR app_priv());
CREATE POLICY app_transitions_read ON application_transitions FOR SELECT USING (EXISTS (SELECT 1 FROM applications a WHERE a.id = application_id));
CREATE POLICY app_transitions_insert ON application_transitions FOR INSERT WITH CHECK (
  (actor_org_id = app_org() AND EXISTS (SELECT 1 FROM applications a WHERE a.id = application_id)) OR app_priv());
CREATE POLICY conflicts_read ON conflict_declarations FOR SELECT USING (org_id = app_org() OR app_priv());
CREATE POLICY conflicts_write ON conflict_declarations FOR INSERT WITH CHECK (
  (org_id = app_org() AND user_id = app_uid() AND EXISTS (SELECT 1 FROM applications a WHERE a.id = application_id AND a.funder_org_id = app_org())) OR app_priv());
CREATE POLICY conflicts_update ON conflict_declarations FOR UPDATE USING (org_id = app_org() AND user_id = app_uid())
  WITH CHECK (org_id = app_org() AND user_id = app_uid());
CREATE POLICY favorites_all ON favorites FOR ALL USING (org_id = app_org()) WITH CHECK (org_id = app_org());
CREATE POLICY feed_feedback_all ON feed_feedback FOR ALL USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org());

-- Recursos e execução ----------------------------------------------------------------------
CREATE POLICY commitments_read ON commitments FOR SELECT USING (funder_org_id = app_org() OR osc_org_id = app_org() OR app_priv());
CREATE POLICY commitments_insert ON commitments FOR INSERT WITH CHECK (
  (funder_org_id = app_org() AND EXISTS (SELECT 1 FROM applications a WHERE a.id = application_id AND a.funder_org_id = app_org()
     AND a.osc_org_id = commitments.osc_org_id AND a.project_id = commitments.project_id)) OR app_priv());
CREATE POLICY commitments_update ON commitments FOR UPDATE USING (funder_org_id = app_org() OR osc_org_id = app_org() OR app_priv());

CREATE POLICY expenses_read ON expenses FOR SELECT USING (org_id = app_org() OR app_project_investor(project_id) OR app_priv());
CREATE POLICY expenses_insert ON expenses FOR INSERT WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY expenses_update ON expenses FOR UPDATE USING (org_id = app_org() OR app_project_investor(project_id) OR app_priv());
CREATE POLICY evidences_read ON evidences FOR SELECT USING (
  org_id = app_org() OR app_project_investor(project_id) OR app_project_party(project_id) OR app_priv());
CREATE POLICY evidences_insert ON evidences FOR INSERT WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY evidences_update ON evidences FOR UPDATE USING (org_id = app_org() OR app_project_investor(project_id) OR app_priv());
CREATE POLICY feedbacks_read ON feedbacks FOR SELECT USING (
  author_org_id = app_org() OR app_project_owner(project_id) OR app_project_investor(project_id) OR app_priv());
CREATE POLICY feedbacks_insert ON feedbacks FOR INSERT WITH CHECK (
  (author_org_id = app_org() AND (app_project_owner(project_id) OR app_project_investor(project_id))) OR app_priv());

-- Documentos, rascunhos, revisões, assinaturas ------------------------------------------------
CREATE POLICY documents_read ON documents FOR SELECT USING (
  org_id = app_org() OR (visibility = 'public' AND app_authenticated())
  OR app_document_access(id, org_id, project_id, application_id, visibility) OR app_priv());
CREATE POLICY documents_insert ON documents FOR INSERT WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY documents_update ON documents FOR UPDATE USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());

CREATE POLICY drafts_read ON drafts FOR SELECT USING (org_id = app_org() OR app_review_access('draft', id) OR app_priv());
CREATE POLICY drafts_write ON drafts FOR ALL USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());

CREATE POLICY reviews_read ON professional_reviews FOR SELECT USING (org_id = app_org() OR professional_org_id = app_org() OR app_priv());
CREATE POLICY reviews_insert ON professional_reviews FOR INSERT WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY reviews_update ON professional_reviews FOR UPDATE USING (org_id = app_org() OR professional_org_id = app_org() OR app_priv());

CREATE POLICY signatures_read ON signatures FOR SELECT USING (
  signer_org_id = app_org() OR app_priv()
  OR (subject_type = 'document' AND EXISTS (SELECT 1 FROM documents d WHERE d.id = subject_id))
  OR (subject_type = 'draft' AND EXISTS (SELECT 1 FROM drafts d WHERE d.id = subject_id)));
CREATE POLICY signatures_insert ON signatures FOR INSERT WITH CHECK (
  (signer_user_id = app_uid() AND signer_org_id = app_org()) OR app_priv());

-- Match, fiscal, compliance ---------------------------------------------------------------
CREATE POLICY match_runs_all ON match_runs FOR ALL USING (viewer_org_id = app_org() OR app_priv()) WITH CHECK (viewer_org_id = app_org() OR app_priv());
CREATE POLICY fiscal_rules_read ON fiscal_rules FOR SELECT USING ((status = 'approved' AND app_authenticated()) OR app_priv());
CREATE POLICY fiscal_rules_write ON fiscal_rules FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY tax_profiles_all ON company_tax_profiles FOR ALL USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY compliance_checks_read ON compliance_checks FOR SELECT USING (org_id = app_org() OR app_osc_counterparty(org_id) OR app_priv());
CREATE POLICY compliance_checks_write ON compliance_checks FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY compliance_reviews_read ON compliance_reviews FOR SELECT USING (org_id = app_org() OR app_priv());
CREATE POLICY compliance_reviews_write ON compliance_reviews FOR ALL USING (app_priv()) WITH CHECK (app_priv());

-- Billing -------------------------------------------------------------------------------------
CREATE POLICY plans_read ON plans FOR SELECT USING (true);
CREATE POLICY plans_write ON plans FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY subscriptions_read ON subscriptions FOR SELECT USING (org_id = app_org() OR app_priv());
CREATE POLICY subscriptions_write ON subscriptions FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY invoices_read ON invoices FOR SELECT USING (org_id = app_org() OR app_priv());
CREATE POLICY invoices_write ON invoices FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY billing_events_sys ON billing_events FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY flags_read ON feature_flags FOR SELECT USING (true);
CREATE POLICY flags_write ON feature_flags FOR ALL USING (app_admin()) WITH CHECK (app_admin());
CREATE POLICY voucher_batches_admin ON voucher_batches FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY vouchers_admin ON vouchers FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY redemptions_read ON voucher_redemptions FOR SELECT USING (org_id = app_org() OR app_priv());
CREATE POLICY redemptions_write ON voucher_redemptions FOR INSERT WITH CHECK (app_priv());
CREATE POLICY grants_read ON entitlement_grants FOR SELECT USING (org_id = app_org() OR app_priv());
CREATE POLICY grants_write ON entitlement_grants FOR ALL USING (app_priv()) WITH CHECK (app_priv());

-- Operação --------------------------------------------------------------------------------------
CREATE POLICY reports_read ON reports FOR SELECT USING (reporter_user_id = app_uid() OR app_priv());
CREATE POLICY reports_insert ON reports FOR INSERT WITH CHECK (reporter_user_id = app_uid() OR app_priv());
CREATE POLICY reports_update ON reports FOR UPDATE USING (app_priv());
CREATE POLICY ai_usage_all ON ai_usage FOR ALL USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY audit_read ON audit_events FOR SELECT USING (org_id = app_org() OR app_priv());
CREATE POLICY audit_insert ON audit_events FOR INSERT WITH CHECK (
  (org_id = app_org() AND actor_user_id IS NOT DISTINCT FROM app_uid()) OR app_priv());
CREATE POLICY ledger_read ON ledger_entries FOR SELECT USING (
  app_project_owner(project_id) OR app_project_investor(project_id) OR app_project_party(project_id) OR app_priv());
CREATE POLICY ledger_insert ON ledger_entries FOR INSERT WITH CHECK (
  (org_id = app_org() AND (app_project_owner(project_id) OR app_project_party(project_id) OR app_project_investor(project_id))) OR app_priv());
CREATE POLICY job_runs_sys ON job_runs FOR ALL USING (app_priv()) WITH CHECK (app_priv());
-- chain_heads: RLS habilitada e SEM política → inacessível ao papel da aplicação (só triggers SECURITY DEFINER).

-- ===========================================================================================
-- Privilégios (least privilege)
-- ===========================================================================================
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO impacto_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO impacto_app;
REVOKE UPDATE, DELETE, TRUNCATE ON audit_events, ledger_entries, signatures, application_transitions FROM impacto_app;
REVOKE ALL ON chain_heads FROM impacto_app;
REVOKE ALL ON schema_migrations FROM impacto_app;
GRANT SELECT ON schema_migrations TO impacto_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO impacto_app;
-- Apenas funções do próprio projeto (extensões pertencem ao DBA e mantêm seus privilégios).
DO $$ DECLARE f regprocedure; BEGIN
  FOR f IN SELECT p.oid::regprocedure FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'public' AND pg_get_userbyid(p.proowner) = current_user LOOP
    EXECUTE format('REVOKE EXECUTE ON FUNCTION %s FROM PUBLIC', f);
    EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO impacto_app', f);
  END LOOP;
END $$;
