-- v0.26.0 — Torres de controle (financiador e governo) e o estado verificável "Projeto IMPACTO Ready".
--
-- Nada aqui é selo pago nem opinião: são CONTAGENS de registros que já existem no banco, lidas por
-- funções SECURITY DEFINER com o mesmo portão das funções irmãs (project_funding, gov_territory_stats):
--   * project_ready_facts: só devolve fatos de projeto que o chamador ENXERGA sob a RLS de `projects`
--     (dono, parte, investidor, projeto publicado). Devolve contagens, nunca linhas — o financiador
--     vê "há 3 evidências aceitas", não as evidências.
--   * gov_territory_overview: só para governo/plataforma, agregado por território com k-anonimato
--     (grupos menores que 3 projetos não saem), como gov_territory_stats.
-- "Desconhecido" é devolvido como NULL, nunca como 0: o motor em Python distingue UNKNOWN de zero.

CREATE FUNCTION project_ready_facts(p_project uuid) RETURNS jsonb
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
  v_org uuid;
  v_ods int;
  v_out jsonb;
BEGIN
  IF app_uid() IS NULL AND NOT app_priv() THEN
    RETURN NULL;
  END IF;
  -- SECURITY DEFINER corre como dono do banco, que não está sob a RLS de projects: a regra de visibilidade
  -- da política projects_read é repetida aqui, literalmente. Sem visibilidade, nada sai.
  SELECT org_id, cardinality(ods) INTO v_org, v_ods FROM projects p WHERE p.id = p_project
     AND (p.org_id = app_org() OR (p.visibility = 'published' AND app_authenticated())
          OR app_project_party(p.id) OR app_review_access('project', p.id) OR app_priv());
  IF v_org IS NULL THEN
    RETURN NULL;
  END IF;
  SELECT jsonb_build_object(
    'org_compliance_status', (SELECT compliance_status FROM organizations WHERE id = v_org),
    'org_institutional_status', (SELECT institutional_status FROM organizations WHERE id = v_org),
    'owner_identity_level', (
        SELECT max(CASE identity_level(m.user_id) WHEN 'biometric' THEN 5 WHEN 'professional' THEN 4 WHEN 'document' THEN 3
                                                  WHEN 'phone' THEN 2 WHEN 'email' THEN 1 ELSE 0 END)
          FROM memberships m WHERE m.org_id = v_org AND m.role IN ('owner','admin')),
    'docs_validated', (SELECT count(*) FROM documents d WHERE d.org_id = v_org AND d.deleted_at IS NULL
                          AND d.validation_status = 'validated' AND (d.valid_until IS NULL OR d.valid_until >= current_date)),
    'docs_required_present', (SELECT count(DISTINCT d.doc_type) FROM documents d WHERE d.org_id = v_org AND d.deleted_at IS NULL
                          AND d.validation_status = 'validated' AND d.doc_type IN ('estatuto_social','cnpj_card','ata_eleicao_diretoria')),
    'diagnoses_complete', (SELECT count(*) FROM diagnoses x WHERE x.project_id = p_project AND x.status IN ('complete','applied')),
    'diagnoses_any', (SELECT count(*) FROM diagnoses x WHERE x.project_id = p_project OR (x.org_id = v_org AND x.project_id IS NULL)),
    'budget_items', (SELECT count(*) FROM budget_items b WHERE b.project_id = p_project),
    'budget_total_cents', (SELECT budget_total_cents FROM projects WHERE id = p_project),
    'needs', (SELECT count(*) FROM project_needs n WHERE n.project_id = p_project),
    'problem_declared', (SELECT length(coalesce(problem, '')) >= 40 FROM projects WHERE id = p_project),
    'ods', v_ods,
    'indicators', (SELECT count(*) FROM project_indicators i WHERE i.project_id = p_project),
    'indicators_with_baseline', (SELECT count(*) FROM project_indicators i WHERE i.project_id = p_project AND i.baseline IS NOT NULL),
    'indicator_values_reported', (SELECT count(*) FROM indicator_values v WHERE v.project_id = p_project),
    'indicator_values_validated', (SELECT count(*) FROM indicator_values v WHERE v.project_id = p_project AND v.status = 'validated'),
    'evidences_accepted', (SELECT count(*) FROM evidences e WHERE e.project_id = p_project AND e.status = 'accepted'),
    'evidences_submitted', (SELECT count(*) FROM evidences e WHERE e.project_id = p_project AND e.status = 'submitted'),
    'responsibles', (SELECT count(*) FROM responsibility_assignments r WHERE r.scope = 'project' AND r.subject_id = p_project AND r.ended_on IS NULL),
    'team', (SELECT count(*) FROM project_team(p_project)),
    'professionals', (SELECT count(*) FROM project_team(p_project) t WHERE t.relation <> 'owner'),
    'leaders', (SELECT count(*) FROM memberships m WHERE m.org_id = v_org AND m.role IN ('owner','admin','manager')),
    'risks', (SELECT count(*) FROM project_risks r WHERE r.project_id = p_project),
    'risks_open_critical', (SELECT count(*) FROM project_risks r WHERE r.project_id = p_project
                               AND r.status IN ('open','materialized') AND r.severity IN ('high','critical')),
    'milestones', (SELECT count(*) FROM milestones m WHERE m.project_id = p_project),
    'milestones_overdue', (SELECT count(*) FROM milestones m WHERE m.project_id = p_project
                              AND m.due_on < current_date AND m.status NOT IN ('accepted','rejected')),
    'ledger_entries', (SELECT count(*) FROM ledger_entries l WHERE l.project_id = p_project),
    'ledger_first_at', (SELECT min(at) FROM ledger_entries l WHERE l.project_id = p_project),
    'impact_updates', (SELECT count(*) FROM impact_updates u WHERE u.project_id = p_project),
    'impact_updates_reviewed', (SELECT count(*) FROM impact_updates u WHERE u.project_id = p_project AND u.status IN ('accepted','published')),
    'expenses', (SELECT count(*) FROM expenses e WHERE e.project_id = p_project),
    'expenses_documented', (SELECT count(*) FROM expenses e WHERE e.project_id = p_project AND e.document_id IS NOT NULL),
    'agreements_active', (SELECT count(*) FROM signed_agreements a WHERE a.project_id = p_project AND a.status = 'active'),
    'computed_at', now()
  ) INTO v_out;
  RETURN v_out;
END $$;
REVOKE EXECUTE ON FUNCTION project_ready_facts(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION project_ready_facts(uuid) TO impacto_app;

-- Visão territorial do governo: programas → editais → OSCs → projetos → recursos → indicadores
-- declarados × validados → atrasos. Uma linha por projeto PUBLICADO do território (publicado é
-- público por definição); os indicadores saem como contagens, nunca como valores individuais.
CREATE FUNCTION gov_territory_overview(p_prefix text, p_min_group integer DEFAULT 3)
RETURNS TABLE(project_id uuid, title text, status text, territory text, causes text[], ods smallint[],
              osc_id uuid, osc_name text, osc_compliance text, budget_total_cents bigint,
              committed_cents bigint, disbursed_cents bigint, confirmed_cents bigint, spent_cents bigint, validated_spent_cents bigint,
              indicators bigint, values_reported bigint, values_validated bigint,
              evidences_accepted bigint, milestones bigint, milestones_overdue bigint,
              professionals bigint, updates_reviewed bigint, last_activity timestamptz)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
  IF NOT (app_kind() IN ('government','platform') OR app_priv()) THEN
    RAISE EXCEPTION 'acesso restrito a órgãos de governo' USING ERRCODE = '42501';
  END IF;
  IF p_min_group < 3 THEN p_min_group := 3; END IF;
  IF (SELECT count(*) FROM projects p WHERE p.visibility = 'published' AND p.territory LIKE p_prefix || '%') < p_min_group THEN
    RETURN;   -- k-anonimato: território com menos de 3 projetos publicados não sai linha a linha
  END IF;
  RETURN QUERY
  SELECT p.id, p.title, p.status, p.territory, p.causes, p.ods, o.id, o.legal_name, o.compliance_status, p.budget_total_cents,
         (SELECT coalesce(sum(cm.amount_cents),0) FROM commitments cm WHERE cm.project_id = p.id AND cm.status <> 'cancelled')::bigint,
         (SELECT coalesce(sum(cm.amount_cents),0) FROM commitments cm WHERE cm.project_id = p.id AND cm.status IN ('disbursed','confirmed'))::bigint,
         (SELECT coalesce(sum(cm.amount_cents),0) FROM commitments cm WHERE cm.project_id = p.id AND cm.status = 'confirmed')::bigint,
         (SELECT coalesce(sum(e.amount_cents),0) FROM expenses e WHERE e.project_id = p.id)::bigint,
         (SELECT coalesce(sum(e.amount_cents),0) FROM expenses e WHERE e.project_id = p.id AND e.status = 'validated')::bigint,
         (SELECT count(*) FROM project_indicators i WHERE i.project_id = p.id),
         (SELECT count(*) FROM indicator_values v WHERE v.project_id = p.id),
         (SELECT count(*) FROM indicator_values v WHERE v.project_id = p.id AND v.status = 'validated'),
         (SELECT count(*) FROM evidences e WHERE e.project_id = p.id AND e.status = 'accepted'),
         (SELECT count(*) FROM milestones m WHERE m.project_id = p.id),
         (SELECT count(*) FROM milestones m WHERE m.project_id = p.id AND m.due_on < current_date AND m.status NOT IN ('accepted','rejected')),
         (SELECT count(*) FROM project_team(p.id) t WHERE t.relation <> 'owner'),
         (SELECT count(*) FROM impact_updates u WHERE u.project_id = p.id AND u.status IN ('accepted','published')),
         (SELECT max(l.at) FROM ledger_entries l WHERE l.project_id = p.id)
    FROM projects p JOIN organizations o ON o.id = p.org_id
   WHERE p.visibility = 'published' AND p.territory LIKE p_prefix || '%'
   ORDER BY p.territory, p.title;
END $$;
REVOKE EXECUTE ON FUNCTION gov_territory_overview(text, integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION gov_territory_overview(text, integer) TO impacto_app;
