-- v0.20.0 — correção do guarda de fluxo da denúncia, encontrada pelo próprio teste.
--
-- A primeira versão de `report_flow_guard()` (migração 0038) começava assim:
--
--     IF NEW.status = OLD.status THEN RETURN NEW; END IF;
--
-- ou seja: quando a SITUAÇÃO não mudava, a função devolvia a linha sem conferir mais nada — e a
-- proteção que impede REESCREVER A CONCLUSÃO ficava inalcançável nesse caminho. Um UPDATE que
-- trocasse `finding` mantendo o `status` passava pelo gatilho; quem recusava era o CHECK
-- `report_status_matches_finding`, com uma mensagem que não explica nada a quem lê o erro.
--
-- A ordem agora é a certa: a conclusão é conferida ANTES do atalho de situação inalterada.
CREATE OR REPLACE FUNCTION report_flow_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE allowed text[];
BEGIN
  -- A conclusão, uma vez registrada, não se reescreve em silêncio: muda por recurso (`appealed`).
  -- Esta conferência vem PRIMEIRO de propósito — ver o comentário no topo da migração.
  IF OLD.finding IS NOT NULL AND NEW.finding IS DISTINCT FROM OLD.finding
     AND OLD.status <> 'appealed' THEN
    RAISE EXCEPTION 'a conclusão só muda por recurso (appealed), nunca por reescrita'
      USING ERRCODE = '23514';
  END IF;
  IF NEW.status = OLD.status THEN
    RETURN NEW;
  END IF;
  allowed := CASE OLD.status
    WHEN 'reported'              THEN ARRAY['under_review','information_requested','dismissed']
    WHEN 'under_review'          THEN ARRAY['information_requested','substantiated','unsubstantiated','dismissed']
    WHEN 'information_requested' THEN ARRAY['under_review','substantiated','unsubstantiated','dismissed']
    WHEN 'substantiated'         THEN ARRAY['appealed','resolved']
    WHEN 'unsubstantiated'       THEN ARRAY['appealed','resolved']
    WHEN 'appealed'              THEN ARRAY['substantiated','unsubstantiated','resolved']
    ELSE ARRAY[]::text[] END;
  IF NOT (NEW.status = ANY(allowed)) THEN
    RAISE EXCEPTION 'transição de denúncia não permitida: % -> %', OLD.status, NEW.status
      USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$;

-- ============================================================ o denunciado precisa PODER responder
-- A política de escrita de `reports` era `app_priv()` apenas. Com isso, a manifestação e o recurso de
-- quem foi denunciado faziam um UPDATE que afetava ZERO linhas — sem erro, sem aviso — e a rota
-- devolvia 500 ao tentar ler o resultado. O direito de resposta existia só no papel.
--
-- A primeira tentativa de correção foi uma política de UPDATE estreita para a organização alvo. Ela
-- continuou sendo recusada pela RLS mesmo com a expressão do WITH CHECK avaliando verdadeira para a
-- linha — e insistir nela custaria tempo para chegar a uma solução pior. Esta base já tem um padrão
-- para escrita que atravessa fronteira de visibilidade: função `SECURITY DEFINER` estreita, que
-- valida o que precisa validar e não abre nada além (`app_claim_invited`, `app_award_seal`,
-- `app_record_reputation`). É o padrão usado aqui.
--
-- O que estas funções PODEM fazer é deliberadamente mínimo: duas transições, na denúncia da própria
-- organização, com o gatilho de fluxo continuando a valer por cima.

CREATE FUNCTION app_report_respond(p_report uuid, p_org uuid, p_body text, p_document uuid,
                                   p_actor uuid)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE v_id uuid; v_status text; v_target uuid;
BEGIN
  SELECT status, target_org_id INTO v_status, v_target FROM reports WHERE id = p_report;
  IF v_target IS NULL OR v_target <> p_org THEN
    RAISE EXCEPTION 'denúncia não encontrada' USING ERRCODE = '42501';
  END IF;
  IF v_status NOT IN ('information_requested','under_review') THEN
    RAISE EXCEPTION 'esta denúncia não está aberta para manifestação' USING ERRCODE = '23514';
  END IF;
  INSERT INTO report_responses(report_id, org_id, body, document_id, created_by)
    VALUES (p_report, p_org, p_body, p_document, p_actor) RETURNING id INTO v_id;
  UPDATE reports SET status = 'under_review'
    WHERE id = p_report AND status = 'information_requested';
  RETURN v_id;
END $$;
COMMENT ON FUNCTION app_report_respond IS
  'Manifestação de quem foi denunciado. Só na denúncia da própria organização, só quando aberta a '
  'manifestação, e a única mudança de situação possível é devolvê-la para análise.';

CREATE FUNCTION app_report_appeal(p_report uuid, p_org uuid, p_note text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE v_id uuid; v_status text; v_target uuid;
BEGIN
  SELECT status, target_org_id INTO v_status, v_target FROM reports WHERE id = p_report;
  IF v_target IS NULL OR v_target <> p_org THEN
    RAISE EXCEPTION 'denúncia não encontrada' USING ERRCODE = '42501';
  END IF;
  IF v_status NOT IN ('substantiated','unsubstantiated') THEN
    RAISE EXCEPTION 'só se recorre de uma conclusão' USING ERRCODE = '23514';
  END IF;
  INSERT INTO report_responses(report_id, org_id, body, created_by)
    VALUES (p_report, p_org, '[RECURSO] ' || p_note, NULL) RETURNING id INTO v_id;
  UPDATE reports SET status = 'appealed' WHERE id = p_report;
  RETURN v_id;
END $$;
COMMENT ON FUNCTION app_report_appeal IS
  'Recurso da conclusão. A conclusão em si NÃO muda aqui: muda a situação para `appealed`, e quem '
  'reanalisa é a plataforma — por pessoa diferente de quem concluiu.';

GRANT EXECUTE ON FUNCTION app_report_respond(uuid, uuid, text, uuid, uuid) TO impacto_app;
GRANT EXECUTE ON FUNCTION app_report_appeal(uuid, uuid, text) TO impacto_app;
