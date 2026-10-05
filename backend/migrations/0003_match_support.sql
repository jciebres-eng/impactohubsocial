-- 0003_match_support.sql — Funções de leitura restrita usadas pelo Match Engine.
-- Expõem SOMENTE metadados/agregados (nunca conteúdo de documento) a quem tem papel legítimo na avaliação.

CREATE FUNCTION org_document_metadata(p_org uuid, p_project uuid)
RETURNS TABLE(doc_type text, status text, valid_until date)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
  IF NOT (app_org() = p_org OR app_kind() IN ('company','government','platform') OR app_priv()) THEN
    RAISE EXCEPTION 'acesso negado aos metadados documentais' USING ERRCODE = '42501';
  END IF;
  RETURN QUERY
  SELECT d.doc_type, d.status, d.valid_until FROM documents d
   WHERE d.org_id = p_org AND d.deleted_at IS NULL
     AND (d.project_id IS NULL OR d.project_id = p_project);
END $$;

CREATE FUNCTION org_track_record(p_org uuid)
RETURNS TABLE(completed_projects bigint, evidences_total bigint, evidences_accepted bigint,
              expenses_validated bigint, expenses_questioned bigint)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
  SELECT (SELECT count(*) FROM projects WHERE org_id = p_org AND status = 'completed'),
         (SELECT count(*) FROM evidences WHERE org_id = p_org AND status IN ('accepted','rejected')),
         (SELECT count(*) FROM evidences WHERE org_id = p_org AND status = 'accepted'),
         (SELECT count(*) FROM expenses WHERE org_id = p_org AND status = 'validated'),
         (SELECT count(*) FROM expenses WHERE org_id = p_org AND status = 'questioned')
  WHERE app_uid() IS NOT NULL OR app_priv();
$$;

REVOKE EXECUTE ON FUNCTION org_document_metadata(uuid, uuid) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION org_track_record(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION org_document_metadata(uuid, uuid) TO impacto_app;
GRANT EXECUTE ON FUNCTION org_track_record(uuid) TO impacto_app;

-- Agregados financeiros de um projeto (sem detalhes por financiador). O chamador deve filtrar pela
-- visibilidade do projeto (EXISTS em projects sob RLS) — ver services/matching.py.
CREATE FUNCTION project_funding(p_project uuid)
RETURNS TABLE(committed_cents bigint, disbursed_cents bigint, confirmed_cents bigint, spent_cents bigint, accepted_evidences bigint,
              funders bigint)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
  SELECT coalesce(sum(amount_cents) FILTER (WHERE status <> 'cancelled'), 0)::bigint,
         coalesce(sum(amount_cents) FILTER (WHERE status IN ('disbursed','confirmed')), 0)::bigint,
         coalesce(sum(amount_cents) FILTER (WHERE status = 'confirmed'), 0)::bigint,
         (SELECT coalesce(sum(amount_cents), 0) FROM expenses e WHERE e.project_id = p_project)::bigint,
         (SELECT count(*) FROM evidences e WHERE e.project_id = p_project AND e.status = 'accepted'),
         count(DISTINCT funder_org_id) FILTER (WHERE status <> 'cancelled')
    FROM commitments WHERE project_id = p_project AND (app_uid() IS NOT NULL OR app_priv());
$$;
REVOKE EXECUTE ON FUNCTION project_funding(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION project_funding(uuid) TO impacto_app;

-- Nome de exibição de um usuário (sem e-mail ou outros dados) para assinaturas, linhas do tempo e revisões.
CREATE FUNCTION user_display_name(p_user uuid) RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
  SELECT CASE WHEN app_uid() IS NULL AND NOT app_priv() THEN NULL ELSE (SELECT full_name FROM users WHERE id = p_user) END
$$;
REVOKE EXECUTE ON FUNCTION user_display_name(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION user_display_name(uuid) TO impacto_app;
