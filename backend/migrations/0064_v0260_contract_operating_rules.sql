-- 0064 — v0.26.0 — CONTRATO COMO REGRA OPERACIONAL (não só PDF guardado)
--
-- O que muda, e por quê:
--   1. Acordo tem VERSÃO. Alterar um acordo depois de publicado não reescreve nada: cria uma versão
--      nova em rascunho, que precisa ser assinada de novo, e a anterior fica `superseded` — as
--      assinaturas antigas continuam no histórico, mas deixam de valer como aprovação do acordo.
--   2. Os TERMOS OPERACIONAIS ficam no acordo e congelam com ele: valor, taxa de serviço da
--      plataforma contratada (em pontos-base, paga por quem o contrato diz), e a POLÍTICA DE ACEITE
--      (prazo de análise, calendário, aceite tácito, janela de contestação). Nada de "7 dias" fixo.
--   3. Marcos têm valor, ordem, e um GRAFO de transição conferido pelo banco; quem entrega não
--      aceita a própria entrega (função `agreement_milestone_guard`).
--   4. OBRIGAÇÕES derivadas: ao ficar vigente, o acordo gera, para cada marco, quem deve entregar,
--      quem deve aceitar e em quanto tempo, e quem deve pagar quanto — a pessoa não reconstrói à mão
--      o que o contrato já diz.
--   5. MATRIZ DE DISTRIBUIÇÃO como retrato imutável (`agreement_allocations`): bruto, projeto, taxa
--      da plataforma, terceiros — com a regra comercial, a versão de preço e o hash do acordo que a
--      produziram. É CÁLCULO + INSTRUÇÃO + CONCILIAÇÃO (ADR-284). A plataforma NÃO custodia: cada
--      linha é paga por quem paga, pelo meio que as partes escolherem; a taxa da plataforma, quando
--      cobrável, vira uma cobrança da própria plataforma ao pagador (platform_charges), nunca um
--      desconto sobre dinheiro em trânsito. Se a regra comercial não estiver ativa (parecer jurídico
--      pendente), a linha da taxa é registrada como NÃO COBRÁVEL, com o motivo — não some.
-- O que NÃO muda: ADR-022/178 (taxa de êxito e take rate seguem recusadas pelo banco) e ADR-284.

-- ============================================================================ 1. versão e termos
ALTER TABLE signed_agreements DROP CONSTRAINT IF EXISTS signed_agreements_status_check;
ALTER TABLE signed_agreements ADD CONSTRAINT signed_agreements_status_check
  CHECK (status IN ('draft','awaiting_signatures','active','completed','canceled','expired','superseded'));
ALTER TABLE signed_agreements
  ADD COLUMN version          smallint NOT NULL DEFAULT 1 CHECK (version >= 1),
  ADD COLUMN supersedes_id    uuid REFERENCES signed_agreements(id) ON DELETE SET NULL,
  ADD COLUMN superseded_by_id uuid REFERENCES signed_agreements(id) ON DELETE SET NULL,
  ADD COLUMN version_reason   text CHECK (length(version_reason) <= 1000),
  -- taxa de serviço da plataforma CONTRATADA (pontos-base: 300 = 3,00%). NULA = o contrato não prevê.
  ADD COLUMN platform_fee_bps integer CHECK (platform_fee_bps IS NULL OR platform_fee_bps BETWEEN 0 AND 10000),
  -- quem paga a taxa: o papel da parte no acordo. Preferencialmente quem financia (ADR-284 §0).
  ADD COLUMN fee_payer_role   text CHECK (fee_payer_role IS NULL OR fee_payer_role IN ('funder','contractor','provider')),
  -- 'additional': a taxa é SOMADA ao valor do projeto (R$100.000 ao projeto + R$3.000 à plataforma);
  -- 'deducted': a taxa sai do bruto (R$97.000 ao projeto + R$3.000 à plataforma). O contrato decide.
  ADD COLUMN fee_mode         text NOT NULL DEFAULT 'additional' CHECK (fee_mode IN ('additional','deducted')),
  -- política de aceite (AcceptancePolicy): nada de prazo universal no código
  ADD COLUMN review_days      smallint NOT NULL DEFAULT 10 CHECK (review_days BETWEEN 1 AND 120),
  ADD COLUMN calendar_type    text NOT NULL DEFAULT 'calendar' CHECK (calendar_type IN ('calendar','business')),
  ADD COLUMN auto_accept      boolean NOT NULL DEFAULT false,
  ADD COLUMN dispute_days     smallint NOT NULL DEFAULT 5 CHECK (dispute_days BETWEEN 0 AND 60),
  ADD COLUMN activated_at     timestamptz;
CREATE INDEX ix_agreements_supersedes ON signed_agreements(supersedes_id) WHERE supersedes_id IS NOT NULL;

-- Os termos congelam ao sair do rascunho. `guard_columns` é incondicional; aqui a condição é o status.
CREATE FUNCTION agreement_terms_frozen() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.status <> 'draft' AND NOT app_priv() THEN
    IF NEW.value_cents IS DISTINCT FROM OLD.value_cents OR NEW.platform_fee_bps IS DISTINCT FROM OLD.platform_fee_bps
       OR NEW.fee_payer_role IS DISTINCT FROM OLD.fee_payer_role OR NEW.fee_mode IS DISTINCT FROM OLD.fee_mode
       OR NEW.review_days IS DISTINCT FROM OLD.review_days OR NEW.calendar_type IS DISTINCT FROM OLD.calendar_type
       OR NEW.auto_accept IS DISTINCT FROM OLD.auto_accept OR NEW.dispute_days IS DISTINCT FROM OLD.dispute_days
       OR NEW.version IS DISTINCT FROM OLD.version OR NEW.supersedes_id IS DISTINCT FROM OLD.supersedes_id THEN
      RAISE EXCEPTION 'os termos de um acordo publicado são imutáveis: crie uma nova versão (POST .../new-version)'
        USING ERRCODE = '42501';
    END IF;
  END IF;
  -- Um acordo substituído nunca volta: suas assinaturas são história, não aprovação.
  IF OLD.status = 'superseded' AND NEW.status <> 'superseded' THEN
    RAISE EXCEPTION 'acordo substituído por versão nova não volta a valer' USING ERRCODE = '42501';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_terms_frozen BEFORE UPDATE ON signed_agreements FOR EACH ROW EXECUTE FUNCTION agreement_terms_frozen();

-- Histórico de versões: uma linha por versão PUBLICADA (hash + termos), append-only.
CREATE TABLE agreement_versions (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  agreement_id     uuid NOT NULL REFERENCES signed_agreements(id) ON DELETE CASCADE,
  lineage_id       uuid NOT NULL,            -- id do acordo original da linhagem (v1)
  version          smallint NOT NULL CHECK (version >= 1),
  content_sha256   char(64) NOT NULL,
  document_id      uuid REFERENCES documents(id) ON DELETE SET NULL,
  terms            jsonb NOT NULL,           -- value_cents, fee, política de aceite, marcos, partes
  reason           text CHECK (length(reason) <= 1000),
  created_by       uuid REFERENCES users(id),
  created_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (lineage_id, version)
);
CREATE TRIGGER trg_append_only BEFORE UPDATE OR DELETE ON agreement_versions FOR EACH ROW
  WHEN (current_user::text = 'impacto_app') EXECUTE FUNCTION forbid_mutation();
CREATE INDEX ix_agreement_versions_agreement ON agreement_versions(agreement_id);
ALTER TABLE agreement_versions ENABLE ROW LEVEL SECURITY;
CREATE POLICY agver_read ON agreement_versions FOR SELECT
  USING (app_priv() OR agreement_owner_org(agreement_id) = app_org() OR agreement_has_party(agreement_id, app_org()));
CREATE POLICY agver_insert ON agreement_versions FOR INSERT
  WITH CHECK (app_priv() OR agreement_owner_org(agreement_id) = app_org());

-- ============================================================================ 2. marcos
ALTER TABLE signed_agreement_milestones
  ADD COLUMN seq               smallint,
  ADD COLUMN amount_cents      bigint CHECK (amount_cents IS NULL OR amount_cents >= 0),
  ADD COLUMN source            text NOT NULL DEFAULT 'manual' CHECK (source IN ('manual','derived')),
  ADD COLUMN delivered_at      timestamptz,
  ADD COLUMN acceptance_due_on date,
  ADD COLUMN accepted_at       timestamptz,
  ADD COLUMN accepted_by_org   uuid REFERENCES organizations(id) ON DELETE SET NULL,
  ADD COLUMN accepted_by       uuid REFERENCES users(id) ON DELETE SET NULL,
  ADD COLUMN rejection_reason  text CHECK (length(rejection_reason) <= 1000);

-- Grafo de transição do marco, conferido pelo banco; quem entrega não aceita a própria entrega.
CREATE FUNCTION agreement_milestone_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_ok boolean;
BEGIN
  IF app_priv() THEN RETURN NEW; END IF;
  IF NEW.status IS DISTINCT FROM OLD.status THEN
    v_ok := (OLD.status, NEW.status) IN (('planned','in_progress'), ('planned','delivered'), ('in_progress','delivered'),
                                         ('delivered','accepted'), ('delivered','rejected'), ('rejected','in_progress'),
                                         ('rejected','delivered'));
    IF NOT v_ok THEN
      RAISE EXCEPTION 'transição de marco % → % não é permitida', OLD.status, NEW.status USING ERRCODE = '23514';
    END IF;
    IF NEW.status = 'delivered' THEN
      NEW.delivered_at := now();
    END IF;
    IF NEW.status IN ('accepted','rejected') THEN
      -- quem entregou (reported_by) não pode ser quem aceita; e quem aceita tem de ser parte do acordo
      IF NEW.accepted_by IS NULL OR NEW.accepted_by_org IS NULL THEN
        RAISE EXCEPTION 'aceite ou recusa de marco exige quem decidiu (accepted_by, accepted_by_org)' USING ERRCODE = '23514';
      END IF;
      IF OLD.reported_by IS NOT NULL AND NEW.accepted_by = OLD.reported_by THEN
        RAISE EXCEPTION 'quem reportou a entrega não aceita a própria entrega' USING ERRCODE = '42501';
      END IF;
      IF NOT agreement_has_party(NEW.agreement_id, NEW.accepted_by_org) THEN
        RAISE EXCEPTION 'só uma parte do acordo aceita ou recusa um marco' USING ERRCODE = '42501';
      END IF;
      NEW.accepted_at := now();
    END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_milestone_guard BEFORE UPDATE ON signed_agreement_milestones FOR EACH ROW
  EXECUTE FUNCTION agreement_milestone_guard();

-- Até aqui a RLS deixava só a organização que CRIOU o marco alterá-lo (WITH CHECK org_id = app_org()):
-- quem entregava também "aceitava". Agora qualquer parte do acordo atualiza o marco; quem pode aceitar
-- é decidido pelo gatilho acima e pelo serviço.
DROP POLICY agrms_rw ON signed_agreement_milestones;
CREATE POLICY agrms_read ON signed_agreement_milestones FOR SELECT
  USING (org_id = app_org() OR app_priv() OR agreement_owner_org(agreement_id) = app_org()
         OR agreement_has_party(agreement_id, app_org()));
CREATE POLICY agrms_insert ON signed_agreement_milestones FOR INSERT
  WITH CHECK (app_priv() OR agreement_owner_org(agreement_id) = app_org() OR agreement_has_party(agreement_id, app_org()));
CREATE POLICY agrms_update ON signed_agreement_milestones FOR UPDATE
  USING (app_priv() OR agreement_owner_org(agreement_id) = app_org() OR agreement_has_party(agreement_id, app_org()))
  WITH CHECK (app_priv() OR agreement_owner_org(agreement_id) = app_org() OR agreement_has_party(agreement_id, app_org()));
CREATE POLICY agrms_delete ON signed_agreement_milestones FOR DELETE
  USING (app_priv() OR (agreement_owner_org(agreement_id) = app_org() AND agreement_is_draft(agreement_id)));

-- ============================================================================ 3. obrigações derivadas
CREATE TABLE agreement_obligations (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  agreement_id   uuid NOT NULL REFERENCES signed_agreements(id) ON DELETE CASCADE,
  milestone_id   uuid REFERENCES signed_agreement_milestones(id) ON DELETE CASCADE,
  obligor_org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  kind           text NOT NULL CHECK (kind IN ('deliver','accept','pay','report')),
  title          text NOT NULL CHECK (length(title) BETWEEN 3 AND 300),
  due_on         date,
  amount_cents   bigint CHECK (amount_cents IS NULL OR amount_cents >= 0),
  status         text NOT NULL DEFAULT 'open' CHECK (status IN ('open','done','overdue','waived')),
  done_at        timestamptz,
  derived_from   text NOT NULL DEFAULT 'contract' CHECK (derived_from IN ('contract','manual')),
  created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_obligations_agreement ON agreement_obligations(agreement_id);
CREATE INDEX ix_obligations_obligor ON agreement_obligations(obligor_org_id, status, due_on);
ALTER TABLE agreement_obligations ENABLE ROW LEVEL SECURITY;
CREATE POLICY obl_read ON agreement_obligations FOR SELECT
  USING (app_priv() OR obligor_org_id = app_org() OR agreement_owner_org(agreement_id) = app_org()
         OR agreement_has_party(agreement_id, app_org()));
-- Só a derivação (contexto privilegiado) cria; a parte muda o status do que é dela.
CREATE POLICY obl_insert ON agreement_obligations FOR INSERT WITH CHECK (app_priv());
CREATE POLICY obl_update ON agreement_obligations FOR UPDATE
  USING (app_priv() OR obligor_org_id = app_org()) WITH CHECK (app_priv() OR obligor_org_id = app_org());
CREATE TRIGGER trg_guard BEFORE UPDATE ON agreement_obligations FOR EACH ROW
  EXECUTE FUNCTION guard_columns('agreement_id','milestone_id','obligor_org_id','kind','amount_cents','derived_from');

-- ============================================================================ 4. matriz de distribuição
CREATE TABLE agreement_allocations (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  agreement_id       uuid NOT NULL REFERENCES signed_agreements(id) ON DELETE CASCADE,
  version            smallint NOT NULL,
  content_sha256     char(64) NOT NULL,
  gross_cents        bigint NOT NULL CHECK (gross_cents >= 0),
  project_cents      bigint NOT NULL CHECK (project_cents >= 0),
  platform_fee_cents bigint NOT NULL DEFAULT 0 CHECK (platform_fee_cents >= 0),
  third_party_cents  bigint NOT NULL DEFAULT 0 CHECK (third_party_cents >= 0),
  fee_mode           text NOT NULL CHECK (fee_mode IN ('additional','deducted')),
  fee_bps            integer CHECK (fee_bps IS NULL OR fee_bps BETWEEN 0 AND 10000),
  fee_payer_org_id   uuid REFERENCES organizations(id) ON DELETE SET NULL,
  fee_rule_key       text REFERENCES monetization_rules(key) ON DELETE RESTRICT,
  fee_chargeable     boolean NOT NULL DEFAULT false,
  fee_reason         text NOT NULL CHECK (length(fee_reason) BETWEEN 3 AND 300),
  pricing_version    text,
  platform_charge_id uuid REFERENCES platform_charges(id) ON DELETE SET NULL,
  lines              jsonb NOT NULL,         -- [{kind, to_org_id, role, cents, basis, note}]
  allocation_hash    char(64) NOT NULL,      -- sha256 do material (hash do acordo + linhas)
  computed_by        uuid REFERENCES users(id),
  computed_at        timestamptz NOT NULL DEFAULT now(),
  -- A soma fecha: no modo 'deducted' projeto + taxa + terceiros = bruto; no 'additional' projeto + terceiros = bruto.
  CONSTRAINT allocation_sums CHECK (
    (fee_mode = 'deducted'   AND project_cents + platform_fee_cents + third_party_cents = gross_cents) OR
    (fee_mode = 'additional' AND project_cents + third_party_cents = gross_cents))
);
CREATE INDEX ix_allocations_agreement ON agreement_allocations(agreement_id, computed_at DESC);
ALTER TABLE agreement_allocations ENABLE ROW LEVEL SECURITY;
CREATE POLICY alloc_read ON agreement_allocations FOR SELECT
  USING (app_priv() OR agreement_owner_org(agreement_id) = app_org() OR agreement_has_party(agreement_id, app_org()));
CREATE POLICY alloc_insert ON agreement_allocations FOR INSERT WITH CHECK (app_priv());
CREATE TRIGGER trg_append_only BEFORE UPDATE OR DELETE ON agreement_allocations FOR EACH ROW
  WHEN (current_user::text = 'impacto_app') EXECUTE FUNCTION forbid_mutation();

-- ============================================================================ 5. regra comercial da taxa
-- A taxa de serviço contratada no acordo de financiamento, PAGA PELO FINANCIADOR à plataforma pela
-- orquestração (cálculo, instrução, conciliação, evidência, governança). Não é taxa de êxito nem
-- take rate: não incide sobre transação da plataforma, e sim sobre serviço contratado; o pagador é
-- quem contrata o serviço. Nasce DESLIGADA: só a administração a ativa, e o banco exige carta legal
-- verde e parecer (gatilho `monetization_rule_gate`). O percentual vem do CONTRATO, não daqui.
INSERT INTO monetization_rules(
    key, label_pt, revenue_engine, engine_rank, payer_kind, trigger_kind, value_event_type,
    pricing_mode, currency, hypothesis_min_cents, hypothesis_max_cents, hypothesis_note,
    problem_solved, substitution_answer)
VALUES ('contract.platform_service_fee', 'Taxa de serviço contratada no acordo de financiamento', 'enterprise', 3,
        'company', 'contract', NULL, 'percentage', 'BRL', NULL, NULL,
        'HIPÓTESE comercial: o percentual não é fixado pela plataforma — vem do próprio acordo assinado (platform_fee_bps) e é '
        'pago por quem financia. Nenhum valor é descontado de dinheiro em trânsito: a plataforma não custodia (ADR-284). '
        'Só vira cobrança após carta legal verde.',
        'Quem financia quer saber onde o recurso está, o que foi executado, que evidência existe e o que precisa da sua '
        'decisão — e pagar pela infraestrutura que responde isso, sem que a OSC precise desembolsar para pagar a plataforma.',
        'Planilha e e-mail não derivam obrigações do contrato, não cobram evidência no prazo, não conciliam aporte com '
        'execução nem registram quem decidiu o quê com hash encadeado.');
WITH c AS (
  INSERT INTO monetization_legal_cards(rule_key, status, certainty, payer, beneficiary, billing_event, revenue_nature,
      contractual_relation, required_document, required_terms, cancellation_policy, refund_policy, tax_notes,
      invoice_notes, regulatory_notes, legal_basis, source_name, source_url, verified_on, open_questions, note)
  VALUES ('contract.platform_service_fee', 'yellow', 'medium',
    'Organização financiadora (empresa, fundação ou pessoa física) que contrata a orquestração do acordo',
    'A plataforma (pessoa jurídica titular do software)',
    'Acordo de financiamento vigente (todas as partes assinaram) com cláusula de taxa de serviço; exigível conforme o acordo (vigência ou desembolso)',
    'Receita de prestação de serviço de software: orquestração, derivação de obrigações, instrução e conciliação, evidência e governança do acordo — percentual do valor contratado como BASE DE CÁLCULO, não participação no valor',
    'Contrato de prestação de serviço entre a plataforma e o financiador, acessório ao acordo de financiamento assinado na plataforma',
    'Cláusula de taxa de serviço no acordo assinado; Termos de Uso com a modalidade; nota fiscal de serviço',
    'Base de cálculo, momento da exigibilidade, tratamento de cancelamento, de financiamento parcial e de devolução',
    'Acordo cancelado antes de qualquer desembolso: taxa não exigível',
    'Devolução proporcional em caso de cancelamento após desembolso parcial, conforme o acordo',
    'ISS sobre serviço; a base tributável é a taxa, não o valor financiado. Alíquota, município e regime NÃO analisados',
    'Emissão de nota fiscal de serviço é obrigatória e NÃO está implementada na plataforma',
    'A plataforma NÃO recebe o valor financiado: o financiador paga o projeto diretamente e paga a taxa à plataforma em instrução separada (ADR-284). Precisa de parecer confirmando que o desenho não configura arranjo de pagamento (Lei 12.865/2013) nem intermediação',
    'LC 116/2003 (ISS sobre serviço de software e suporte); Lei 12.865/2013 (arranjos de pagamento — parecer pendente)',
    'Planalto — LC 116/2003 e Lei 12.865/2013', 'https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp116.htm', '2026-10-08',
    'Parecer sobre não configuração de arranjo de pagamento; alíquota e município do ISS; redação da cláusula no acordo; nota fiscal',
    'Modalidade desenhada para que a OSC nunca desembolse para pagar a plataforma e para que nenhum valor de terceiro passe por ela. Fica AMARELA até parecer jurídico e contábil.')
  RETURNING id, rule_key
)
UPDATE monetization_rules r SET legal_card_id = c.id, legal_status = 'review_required' FROM c WHERE r.key = c.rule_key;

-- ============================================================================ 6. livro do projeto
ALTER TABLE ledger_entries DROP CONSTRAINT IF EXISTS ledger_entries_entry_type_check;
ALTER TABLE ledger_entries ADD CONSTRAINT ledger_entries_entry_type_check CHECK (entry_type IN (
  'need_published','budget_defined','milestone_defined','interest_registered','application_submitted',
  'application_approved','funding_committed','disbursement_reported','disbursement_confirmed',
  'expense_recorded','evidence_submitted','evidence_reviewed','result_reported','report_submitted',
  'feedback_given','professional_signature','project_completed','refund_completed','payment_disputed',
  'indicator_validated','procurement_decided','project_created','idea_promoted','status_changed',
  'diagnosis_created','diagnosis_revised','action_created','action_completed','goal_created',
  'document_generated','document_approved','document_signed','opportunity_matched','match_feedback',
  'partner_added','submission_created','submission_sent','risk_created','risk_resolved','snapshot_taken',
  'project_archived','relationship_created','relationship_ended','proposal_sent','proposal_viewed',
  'proposal_accepted','proposal_declined','proposal_changes_requested','proposal_withdrawn',
  'listing_published','listing_paused','investment_intent','investment_committed',
  'impact_update_submitted','impact_update_accepted','impact_update_changes_requested','impact_update_published',
  'conversation_started','enforcement_applied','experience_confirmed','team_member_added','team_member_removed','correction',
  -- v0.26.0
  'agreement_activated','allocation_computed','milestone_delivered','milestone_accepted','milestone_rejected',
  'obligation_overdue'));

GRANT SELECT, INSERT ON agreement_versions, agreement_allocations TO impacto_app;
GRANT SELECT, INSERT, UPDATE ON agreement_obligations TO impacto_app;
