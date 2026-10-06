-- 0034_v0181_impact_context_fn.sql — O SINAL CONTEXTUAL PRECISA ATRAVESSAR A RLS SEM ABRIR O TEXTO
--
-- ACHADO DA JORNADA DE PONTA A PONTA (v0.18.1)
--
-- A v0.18.0 (pacote CORE_HARDENED) passou a calcular o sinal de impacto do match a partir do
-- contexto de equidade do projeto, lendo `equity_contexts`, `project_barriers` e
-- `equity_assessments` direto na transação de quem pede o match.
--
-- Isso NUNCA funcionaria em produção, e a jornada provou: quem pede o match do projeto é o
-- FINANCIADOR, e a RLS dessas três tabelas (corretamente) só devolve linha para a organização dona
-- do projeto. Resultado silencioso: para todo financiador o contexto chegava vazio, o sinal virava
-- UNKNOWN e a tese da rodada — impacto é resultado contextualizado — simplesmente não se aplicava
-- a ninguém de fora. Nenhum teste pegava porque nenhum teste pedia o match como terceiro.
--
-- A SAÍDA, E POR QUE ELA É ESTREITA
--
-- O financiador precisa dos NÚMEROS para o ranking, não da narrativa. Esta função devolve só
-- agregados — booleanos e escalas de 0 a 1 — e **nunca** o texto da necessidade, o contrafactual,
-- a nota da barreira ou qualquer campo livre. É a mesma estratégia de `app_claim_invited()`:
-- responder uma pergunta estreita com `SECURITY DEFINER` em vez de afrouxar a política.
--
-- Só responde sobre projeto PUBLICADO. Projeto privado continua invisível, inclusive em agregado:
-- contexto de projeto que ninguém pode ver não deveria influenciar o ranking de ninguém.
CREATE FUNCTION project_impact_context(p_project uuid)
  RETURNS TABLE (
    has_context boolean,
    need_level numeric,
    barrier_burden numeric,
    additionality_score numeric,
    outcome_evidence_score numeric,
    impact_evidence_score numeric,
    denominator_quality numeric,
    has_counterfactual boolean)
  LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = public AS $$
DECLARE
  v_vis text;
  ctx record;
  bar record;
  av record;
BEGIN
  SELECT visibility INTO v_vis FROM projects WHERE id = p_project;
  IF v_vis IS DISTINCT FROM 'published' THEN
    RETURN;                       -- projeto não publicado: nenhuma linha, nem agregada
  END IF;

  SELECT additionality_standing,
         (need_source_name IS NOT NULL) AS has_need_source,
         (counterfactual IS NOT NULL) AS has_counterfactual
    INTO ctx FROM equity_contexts WHERE project_id = p_project;
  IF ctx IS NULL THEN
    RETURN;
  END IF;

  SELECT count(*) AS total,
         count(*) FILTER (WHERE standing IN ('documented','evidenced')) AS documented
    INTO bar FROM project_barriers WHERE project_id = p_project;

  SELECT evidence_confidence, methods_available, barriers_total
    INTO av FROM equity_assessments WHERE project_id = p_project
   ORDER BY computed_at DESC LIMIT 1;

  has_context := true;
  -- Necessidade declarada COM fonte vale mais que necessidade declarada sem fonte. Sem fonte o
  -- campo fica em 0,4: é declaração, e declaração não é evidência (mesma escala de SOURCE_TRUST).
  need_level := CASE WHEN ctx.has_need_source THEN 0.8 ELSE 0.4 END;
  barrier_burden := CASE WHEN bar.total > 0
                         THEN least(1.0, (bar.total + bar.documented)::numeric / 8) ELSE NULL END;
  additionality_score := CASE ctx.additionality_standing
                           WHEN 'evidenced' THEN 1.0 WHEN 'documented' THEN 0.7
                           WHEN 'declared' THEN 0.4 ELSE NULL END;
  outcome_evidence_score := CASE WHEN av.methods_available IS NOT NULL
                                  AND cardinality(av.methods_available) > 0 THEN 0.8 ELSE NULL END;
  impact_evidence_score := av.evidence_confidence;
  denominator_quality := CASE WHEN EXISTS (
      SELECT 1 FROM equity_denominators d WHERE d.effective_until IS NULL
        AND ((d.scope = 'project' AND d.project_id = p_project)
          OR (d.scope = 'territory' AND d.territory =
              (SELECT territory FROM projects WHERE id = p_project))))
    THEN 0.8 ELSE NULL END;
  has_counterfactual := ctx.has_counterfactual;
  RETURN NEXT;
END $$;
COMMENT ON FUNCTION project_impact_context IS
  'Contexto de impacto AGREGADO de um projeto publicado, para o sinal explicável do match. '
  'SECURITY DEFINER porque quem pede o match é o financiador, e a RLS das tabelas de equidade '
  '(corretamente) só devolve linha para a organização dona. Devolve apenas números e booleanos: '
  'nunca o texto da necessidade, o contrafactual ou a nota da barreira. Projeto não publicado não '
  'devolve linha nenhuma.';
GRANT EXECUTE ON FUNCTION project_impact_context(uuid) TO impacto_app;
