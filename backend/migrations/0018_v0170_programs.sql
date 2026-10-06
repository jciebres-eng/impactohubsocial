-- 0018_v0170_programs.sql — A ENTIDADE PROGRAMA
--
-- POR QUE ESTA MIGRAÇÃO EXISTE
--
-- A auditoria econômica (SAAS_ECONOMIC_AUDIT.md §1 item 1) encontrou um defeito de produto: os planos
-- anunciam um limite chamado `programs`, e esse limite era aplicado contra `calls` (editais). Ou seja,
-- o produto vendia uma entidade que não existia.
--
-- E a razão econômica é mais importante que o defeito. O mapa de valor diz, textualmente: "projeto é
-- pequeno; programa conecta orçamento, oportunidades, projetos, organizações, território, contratos,
-- indicadores, evidências, resultados e impacto — e é o programa que financiadores e governos
-- realmente querem administrar". É a unidade de valor da receita institucional.
--
-- O QUE ESTA MIGRAÇÃO **NÃO** FAZ
--
--  * Não cria cobrança. Nenhuma linha aqui fala de preço, plano ou fatura. Programa é produto; a
--    monetização vem depois, na 0020, e só depois da auditoria legal (regra dos documentos: "não
--    implementar paywall antes de implementar o valor que justifica o paywall").
--  * Não duplica `calls`. O edital continua sendo o edital; o programa o REFERENCIA. Um programa pode
--    ter vários editais, e um edital pode existir sem programa (como todos os que já existem).
--  * Não duplica `projects`. O projeto continua sendo da OSC que o executa; o programa o referencia
--    com o papel que ele tem ali (financiado, acompanhado, candidato).
--  * Não cria `beneficiary_groups` aqui. Essa coluna existe em UMA tabela (`territory_needs`) e há
--    invariante que falha se aparecer em outra — ver PRIVACY_VISIBILITY_MATRIX.md.

-- ============================================================================ 1. programs
CREATE TABLE programs (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_org_id    uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  title           text NOT NULL CHECK (length(title) BETWEEN 5 AND 200),
  summary         text NOT NULL CHECK (length(summary) BETWEEN 10 AND 2000),
  description     text CHECK (length(description) <= 20000),
  -- O objetivo é o que o programa quer mudar. Exigido porque programa sem objetivo declarado não é
  -- programa: é uma pasta de projetos.
  objective       text NOT NULL CHECK (length(objective) BETWEEN 10 AND 2000),
  -- Orçamento é DECLARADO pela dona. O executado é apurado (ver program_financials()).
  budget_total_cents bigint CHECK (budget_total_cents IS NULL OR budget_total_cents >= 0),
  currency        char(3) NOT NULL DEFAULT 'BRL' CHECK (currency ~ '^[A-Z]{3}$'),
  territories     text[] NOT NULL DEFAULT '{}',
  causes          text[] NOT NULL DEFAULT '{}',
  ods             smallint[] NOT NULL DEFAULT '{}',
  sphere          text CHECK (sphere IN ('federal','state','municipal','private','mixed','international')),
  instrument      text,
  starts_on       date,
  ends_on         date,
  CHECK (ends_on IS NULL OR starts_on IS NULL OR ends_on >= starts_on),
  status          text NOT NULL DEFAULT 'draft',
  -- Visibilidade segue o mesmo vocabulário do resto da rede (ver RELATIONSHIP_MODEL.md).
  visibility      text NOT NULL DEFAULT 'organization'
                  CHECK (visibility IN ('organization','network','public')),
  -- Derivadas por gatilho: a dona não as escreve.
  published_at    timestamptz,
  published_by    uuid REFERENCES users(id) ON DELETE SET NULL,
  closed_at       timestamptz,
  closed_reason   text CHECK (closed_reason IS NULL OR length(closed_reason) BETWEEN 10 AND 2000),
  created_by      uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE programs IS
  'Programa: a unidade que financiador e governo administram. Agrega orçamento, editais, projetos, '
  'território, indicadores e evidências. Não substitui calls nem projects: referencia os dois.';
COMMENT ON COLUMN programs.budget_total_cents IS
  'Orçamento DECLARADO pela organização dona. O valor comprometido e o executado são APURADOS por '
  'program_financials() a partir de commitments e payment_records — nunca digitados aqui.';

CREATE INDEX ix_programs_owner ON programs(owner_org_id);
CREATE INDEX ix_programs_status ON programs(status) WHERE status IN ('open','in_execution');
CREATE INDEX ix_programs_public ON programs(published_at DESC) WHERE visibility = 'public';
CREATE INDEX ix_programs_territories ON programs USING gin(territories);
CREATE INDEX ix_programs_causes ON programs USING gin(causes);

-- ---------------------------------------------------------------- máquina de estados como DADO
-- Mesmo princípio do ADR-116 e do ADR-147: a transição válida é linha de tabela, e um gatilho recusa
-- o que não está no grafo — inclusive em SQL direto e no contexto privilegiado.
CREATE TABLE program_status_graph (
  from_status   text NOT NULL,
  to_status     text NOT NULL,
  -- `either` existe porque suspender é ato que a dona pode praticar no próprio programa E que a
  -- administração pode praticar por medida de moderação. Mesmo vocabulário de proposal_status_graph.
  actor         text NOT NULL CHECK (actor IN ('owner','platform','either')),
  requires_note boolean NOT NULL DEFAULT false,
  note          text NOT NULL,
  PRIMARY KEY (from_status, to_status)
);
INSERT INTO program_status_graph(from_status, to_status, actor, requires_note, note) VALUES
  ('draft','open','owner',false,'Abre o programa para receber editais e candidaturas'),
  ('draft','archived','owner',true,'Desiste do programa antes de abrir'),
  ('open','in_execution','owner',false,'Começou a executar: há projeto financiado'),
  ('open','closed','owner',true,'Encerra sem execução'),
  ('open','archived','owner',true,'Arquiva o programa aberto'),
  ('in_execution','closed','owner',true,'Encerra a execução'),
  ('suspended','closed','owner',true,'Encerra a partir da suspensão'),
  ('closed','archived','owner',false,'Arquiva programa encerrado'),
  -- Suspender e retomar: a dona no próprio programa, ou a administração por medida de moderação.
  ('open','suspended','either',true,'Suspende, com motivo'),
  ('in_execution','suspended','either',true,'Suspende a execução, com motivo'),
  ('suspended','in_execution','either',false,'Retoma a execução');
ALTER TABLE programs ADD CONSTRAINT programs_status_check CHECK (
  status IN ('draft','open','in_execution','suspended','closed','archived'));

-- ---------------------------------------------------------------- 2. o que o programa agrega
-- Edital DENTRO do programa. O edital continua existindo sozinho; esta tabela é a ligação.
CREATE TABLE program_calls (
  program_id  uuid NOT NULL REFERENCES programs(id) ON DELETE CASCADE,
  call_id     uuid NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
  org_id      uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  added_by    uuid REFERENCES users(id) ON DELETE SET NULL,
  added_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (program_id, call_id)
);
CREATE INDEX ix_program_calls_call ON program_calls(call_id);
CREATE INDEX ix_program_calls_org ON program_calls(org_id);

-- Projeto DENTRO do programa, com o papel que ele tem ali.
CREATE TABLE program_projects (
  program_id  uuid NOT NULL REFERENCES programs(id) ON DELETE CASCADE,
  project_id  uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  org_id      uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  role        text NOT NULL CHECK (role IN ('candidate','selected','funded','monitored','declined','withdrawn')),
  -- Quanto o programa destinou a este projeto. Declarado; o pago é apurado.
  allocated_cents bigint CHECK (allocated_cents IS NULL OR allocated_cents >= 0),
  note        text CHECK (length(note) <= 2000),
  added_by    uuid REFERENCES users(id) ON DELETE SET NULL,
  added_at    timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (program_id, project_id)
);
CREATE INDEX ix_program_projects_project ON program_projects(project_id);
CREATE INDEX ix_program_projects_org ON program_projects(org_id);
COMMENT ON COLUMN program_projects.allocated_cents IS
  'Valor que o programa DESTINOU. Não é o pago: o pago vem de payment_records, apurado.';

-- Indicadores que o programa acompanha. Referenciam o catálogo que já existe, com result_kind
-- (output/outcome/impact) — a hierarquia de resultado não é reinventada aqui.
CREATE TABLE program_indicators (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  program_id    uuid NOT NULL REFERENCES programs(id) ON DELETE CASCADE,
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  indicator_id  uuid NOT NULL REFERENCES indicator_catalog(id) ON DELETE RESTRICT,
  target_value  numeric,
  target_date   date,
  baseline_value numeric,
  baseline_date date,
  baseline_source text CHECK (length(baseline_source) <= 200),
  -- Linha de base sem fonte é número inventado. Mesmo princípio de territory_needs.people_estimate.
  CHECK (baseline_value IS NULL OR baseline_source IS NOT NULL),
  note          text CHECK (length(note) <= 2000),
  created_by    uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (program_id, indicator_id)
);
CREATE INDEX ix_program_indicators_program ON program_indicators(program_id);
CREATE INDEX ix_program_indicators_org ON program_indicators(org_id);
CREATE INDEX ix_program_indicators_indicator ON program_indicators(indicator_id);

-- Necessidades de território que o programa diz atender. Liga a oferta (programa) à demanda
-- (territory_needs) — é isso que permite a análise de lacuna.
CREATE TABLE program_needs (
  program_id uuid NOT NULL REFERENCES programs(id) ON DELETE CASCADE,
  need_id    uuid NOT NULL REFERENCES territory_needs(id) ON DELETE CASCADE,
  org_id     uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  added_by   uuid REFERENCES users(id) ON DELETE SET NULL,
  added_at   timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (program_id, need_id)
);
CREATE INDEX ix_program_needs_need ON program_needs(need_id);
CREATE INDEX ix_program_needs_org ON program_needs(org_id);


-- ============================================================================ 3. gatilhos

-- Situação inicial não é escolhida pelo cliente: todo programa nasce em rascunho.
CREATE FUNCTION program_initial_state() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.status IS DISTINCT FROM 'draft' THEN
    RAISE EXCEPTION 'programa nasce em rascunho' USING ERRCODE = '23514';
  END IF;
  IF NEW.published_at IS NOT NULL OR NEW.closed_at IS NOT NULL THEN
    RAISE EXCEPTION 'datas de publicação e encerramento são derivadas' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_program_initial BEFORE INSERT ON programs
  FOR EACH ROW EXECUTE FUNCTION program_initial_state();

-- Transição fora do grafo é recusada. Vale para rota nova, job, script e SQL direto.
-- As colunas derivadas são preenchidas AQUI, não pelo cliente — por isso não estão em guard_columns
-- (a dona legitimamente muda o status do próprio programa; o que ela não faz é escrever a data).
CREATE FUNCTION program_status_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_edge record;
BEGIN
  IF NEW.status IS DISTINCT FROM OLD.status THEN
    SELECT * INTO v_edge FROM program_status_graph
     WHERE from_status = OLD.status AND to_status = NEW.status;
    IF v_edge IS NULL THEN
      RAISE EXCEPTION 'transição de programa % -> % não existe', OLD.status, NEW.status
        USING ERRCODE = '23514';
    END IF;
    IF v_edge.requires_note AND coalesce(length(NEW.closed_reason), 0) < 10 THEN
      RAISE EXCEPTION 'transição % -> % exige motivo', OLD.status, NEW.status USING ERRCODE = '23514';
    END IF;
    IF v_edge.actor = 'platform' AND NOT app_priv() THEN
      RAISE EXCEPTION 'transição % -> % é da administração', OLD.status, NEW.status USING ERRCODE = '42501';
    END IF;
    IF NEW.status = 'open' THEN
      NEW.published_at := now();
      NEW.published_by := app_uid();
    END IF;
    IF NEW.status IN ('closed','archived') THEN
      NEW.closed_at := now();
    END IF;
  ELSE
    -- Fora de transição, as derivadas não se movem. E a tentativa é RECUSADA, não revertida em
    -- silêncio: reverter calado esconderia de quem escreveu a rota que ele estava fazendo algo
    -- errado, e o defeito reapareceria em outro lugar.
    IF NEW.published_at IS DISTINCT FROM OLD.published_at
       OR NEW.published_by IS DISTINCT FROM OLD.published_by
       OR NEW.closed_at IS DISTINCT FROM OLD.closed_at THEN
      RAISE EXCEPTION 'datas de publicação e encerramento são derivadas da transição'
        USING ERRCODE = '42501';
    END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_program_status BEFORE UPDATE ON programs
  FOR EACH ROW EXECUTE FUNCTION program_status_guard();
CREATE TRIGGER trg_programs_touch BEFORE UPDATE ON programs
  FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER trg_program_projects_touch BEFORE UPDATE ON program_projects
  FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- Programa suspenso não pode ser TORNADO público. Mas suspender um programa que já era público tem de
-- funcionar — é justamente o que a moderação precisa fazer.
--
-- A primeira versão desta função recusava qualquer linha com `visibility='public' AND
-- status='suspended'`, e com isso **bloqueava a suspensão** de um programa publicado: a medida de
-- moderação respondia erro. O feed público já exclui suspenso, então a proteção certa é mais estreita:
-- recusar apenas a transição PARA público enquanto suspenso.
CREATE FUNCTION program_visibility_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.visibility = 'public' AND NEW.status = 'suspended'
     AND (TG_OP = 'INSERT' OR OLD.visibility IS DISTINCT FROM 'public') THEN
    RAISE EXCEPTION 'programa suspenso não pode ser tornado público' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_program_visibility BEFORE INSERT OR UPDATE ON programs
  FOR EACH ROW EXECUTE FUNCTION program_visibility_guard();

-- O edital e o projeto que entram num programa têm de ser da MESMA organização dona do programa (no
-- caso do edital) — senão uma organização penduraria o edital de outra no programa dela.
CREATE FUNCTION program_link_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_owner uuid; v_call_owner uuid;
BEGIN
  SELECT owner_org_id INTO v_owner FROM programs WHERE id = NEW.program_id;
  IF v_owner IS DISTINCT FROM NEW.org_id THEN
    RAISE EXCEPTION 'o vínculo tem de ser da organização dona do programa' USING ERRCODE = '42501';
  END IF;
  IF TG_TABLE_NAME = 'program_calls' THEN
    SELECT owner_org_id INTO v_call_owner FROM calls WHERE id = NEW.call_id;
    IF v_call_owner IS DISTINCT FROM v_owner THEN
      RAISE EXCEPTION 'o edital tem de ser da mesma organização do programa' USING ERRCODE = '42501';
    END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_program_calls_guard BEFORE INSERT OR UPDATE ON program_calls
  FOR EACH ROW EXECUTE FUNCTION program_link_guard();
CREATE TRIGGER trg_program_projects_guard BEFORE INSERT OR UPDATE ON program_projects
  FOR EACH ROW EXECUTE FUNCTION program_link_guard();
CREATE TRIGGER trg_program_indicators_guard BEFORE INSERT OR UPDATE ON program_indicators
  FOR EACH ROW EXECUTE FUNCTION program_link_guard();
CREATE TRIGGER trg_program_needs_guard BEFORE INSERT OR UPDATE ON program_needs
  FOR EACH ROW EXECUTE FUNCTION program_link_guard();


-- ============================================================================ 4. RLS

ALTER TABLE programs ENABLE ROW LEVEL SECURITY;
ALTER TABLE program_calls ENABLE ROW LEVEL SECURITY;
ALTER TABLE program_projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE program_indicators ENABLE ROW LEVEL SECURITY;
ALTER TABLE program_needs ENABLE ROW LEVEL SECURITY;
ALTER TABLE program_status_graph ENABLE ROW LEVEL SECURITY;

-- Quem enxerga um programa:
--  * a dona, sempre;
--  * a organização de um projeto que está DENTRO do programa — porque quem executa precisa saber de
--    que programa faz parte; é a mesma lógica de app_project_supporter() da v0.16.0;
--  * quem tem conta, se `network`;
--  * qualquer pessoa, se `public` e já publicado.
CREATE FUNCTION program_has_project_of(p_program uuid, p_org uuid) RETURNS boolean
  LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT EXISTS (
    SELECT 1 FROM program_projects pp JOIN projects pr ON pr.id = pp.project_id
     WHERE pp.program_id = p_program AND pr.org_id = p_org
       AND pp.role <> 'declined')
$$;
COMMENT ON FUNCTION program_has_project_of IS
  'SECURITY DEFINER porque a política de programs precisa consultar program_projects e projects; '
  'política que consulta outra tabela diretamente produz recursão infinita (ADR-104).';

CREATE POLICY programs_read ON programs FOR SELECT USING (
  owner_org_id = app_org()
  OR (visibility = 'public' AND published_at IS NOT NULL AND status <> 'suspended')
  OR (visibility = 'network' AND app_authenticated())
  OR program_has_project_of(id, app_org())
  OR app_priv());
CREATE POLICY programs_insert ON programs FOR INSERT WITH CHECK (
  (owner_org_id = app_org() AND app_kind() = ANY (ARRAY['company','government','osc','individual']))
  OR app_priv());
CREATE POLICY programs_update ON programs FOR UPDATE
  USING (owner_org_id = app_org() OR app_priv())
  WITH CHECK (owner_org_id = app_org() OR app_priv());
CREATE POLICY programs_delete ON programs FOR DELETE USING (app_priv());

-- As tabelas de vínculo seguem o programa: a dona escreve, e quem executa um projeto do programa lê.
CREATE POLICY pcalls_read ON program_calls FOR SELECT USING (
  org_id = app_org() OR program_has_project_of(program_id, app_org()) OR app_priv());
CREATE POLICY pcalls_write ON program_calls FOR INSERT WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY pcalls_del ON program_calls FOR DELETE USING (org_id = app_org() OR app_priv());

CREATE POLICY pprojects_read ON program_projects FOR SELECT USING (
  org_id = app_org()
  OR EXISTS (SELECT 1 FROM projects p WHERE p.id = project_id AND p.org_id = app_org())
  OR app_priv());
CREATE POLICY pprojects_write ON program_projects FOR INSERT WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY pprojects_update ON program_projects FOR UPDATE
  USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY pprojects_del ON program_projects FOR DELETE USING (org_id = app_org() OR app_priv());

CREATE POLICY pind_read ON program_indicators FOR SELECT USING (
  org_id = app_org() OR program_has_project_of(program_id, app_org()) OR app_priv());
CREATE POLICY pind_write ON program_indicators FOR INSERT WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY pind_update ON program_indicators FOR UPDATE
  USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY pind_del ON program_indicators FOR DELETE USING (org_id = app_org() OR app_priv());

CREATE POLICY pneeds_read ON program_needs FOR SELECT USING (
  org_id = app_org() OR program_has_project_of(program_id, app_org()) OR app_priv());
CREATE POLICY pneeds_write ON program_needs FOR INSERT WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY pneeds_del ON program_needs FOR DELETE USING (org_id = app_org() OR app_priv());

-- O grafo de estados é vocabulário: quem tem conta lê, ninguém pela aplicação escreve.
CREATE POLICY pgraph_read ON program_status_graph FOR SELECT USING (app_authenticated() OR app_priv());

GRANT SELECT, INSERT, UPDATE, DELETE ON programs, program_projects, program_indicators TO impacto_app;
GRANT SELECT, INSERT, DELETE ON program_calls, program_needs TO impacto_app;
GRANT SELECT ON program_status_graph TO impacto_app;

-- A dona não troca a propriedade do programa.
--
-- POR QUE `published_at`, `published_by` E `closed_at` **NÃO** ESTÃO AQUI: elas são DERIVADAS por
-- `program_status_guard()`, que roda no mesmo BEFORE UPDATE. Gatilhos disparam em ordem alfabética de
-- nome, então `trg_program_status` grava a data e `trg_programs_guard` a acusaria de alteração
-- indevida — a transição legítima da própria dona responderia 403.
--
-- É exatamente o defeito que a v0.16.0 teve com `marketplace_listings` e `impact_updates`, e a
-- correção é a mesma: coluna derivada por gatilho não entra em `guard_columns`. E não fica
-- desprotegida: o ramo ELSE de `program_status_guard()` restaura os valores antigos quando a situação
-- não muda, de modo que um UPDATE que tente só reescrever a data é desfeito em silêncio — inclusive
-- em SQL direto.
CREATE TRIGGER trg_programs_guard BEFORE UPDATE ON programs
  FOR EACH ROW EXECUTE FUNCTION guard_columns('owner_org_id');


-- ============================================================================ 5. apuração
-- Três funções que COLHEM números. Nenhuma delas aceita número digitado — o mesmo princípio de
-- app_impact_metrics() da v0.16.0, e pela mesma razão: "atendemos 400 pessoas" sem lastro destrói a
-- credibilidade de toda a prestação de contas.

-- ---------------------------------------------------------------- 5.1 dinheiro do programa
-- Declarado: `programs.budget_total_cents` e `program_projects.allocated_cents`.
-- Apurado: tudo o que esta função devolve. A diferença entre os dois é o que o painel precisa mostrar.
CREATE FUNCTION program_financials(p_program uuid)
  RETURNS TABLE (
    projects_total     bigint,
    projects_funded    bigint,
    allocated_cents    bigint,
    committed_cents    bigint,
    disbursed_cents    bigint,
    confirmed_cents    bigint,
    spent_cents        bigint,
    evidenced_cents    bigint)
  LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  WITH pp AS (
    SELECT project_id, allocated_cents, role FROM program_projects WHERE program_id = p_program
  ), f AS (
    SELECT pp.project_id, pf.* FROM pp CROSS JOIN LATERAL project_funding(pp.project_id) pf
  )
  SELECT
    (SELECT count(*) FROM pp),
    (SELECT count(*) FROM pp WHERE role = 'funded'),
    coalesce((SELECT sum(allocated_cents) FROM pp), 0),
    coalesce((SELECT sum(committed_cents) FROM f), 0),
    coalesce((SELECT sum(disbursed_cents) FROM f), 0),
    coalesce((SELECT sum(confirmed_cents) FROM f), 0),
    coalesce((SELECT sum(spent_cents) FROM f), 0),
    -- Executado COM comprovante anexado E validado por alguém. A diferença entre `spent_cents` e
    -- `evidenced_cents` é exatamente a pergunta que o mapa de valor manda a plataforma conseguir
    -- responder: "R$ 84.000 foram executados, mas apenas R$ 61.000 possuem evidência associada".
    --
    -- `expenses.status = 'validated'` é conferência humana; `document_id IS NOT NULL` é o comprovante
    -- no cofre. Despesa registrada sem comprovante conta em `spent` e NÃO conta em `evidenced` — que
    -- é o ponto.
    coalesce((SELECT sum(ex.amount_cents)
         FROM expenses ex JOIN pp ON pp.project_id = ex.project_id
        WHERE ex.status = 'validated' AND ex.document_id IS NOT NULL), 0)
$$;
COMMENT ON FUNCTION program_financials IS
  'Apura o dinheiro do programa a partir de commitments, payment_records, expenses e evidences. '
  'Nenhum destes números é digitável. `evidenced_cents` existe para separar executado de comprovado.';

-- ---------------------------------------------------------------- 5.2 cadeia de resultado
-- Percorre a teoria da mudança que já existe (`impact_nodes`, 7 tipos; `impact_edges`, 6 tipos de
-- ligação) e devolve a cadeia com a FORÇA da ligação declarada em cada elo.
--
-- A honestidade está em `link_type`: `hypothesis` e `inference` não são `observed_evidence`, e
-- `validated_causality` exige evidência MAIS revisor de outra organização MAIS nota (CHECK na tabela
-- desde a v0.15.0). A função não promove nenhum elo: devolve o que está declarado, e quem lê vê a
-- diferença.
CREATE FUNCTION result_chain(p_project uuid, p_max_depth int DEFAULT 4)
  RETURNS TABLE (
    depth        int,
    from_kind    text,
    from_label   text,
    to_kind      text,
    to_label     text,
    link_type    text,
    has_evidence boolean,
    externally_reviewed boolean,
    path         text[])
  LANGUAGE sql STABLE AS $$
  WITH RECURSIVE n AS (
    SELECT id, kind, label FROM impact_nodes WHERE project_id = p_project
  ), walk AS (
    SELECT 1 AS depth, e.from_node, e.to_node, e.link_type, e.evidence_id,
           e.reviewed_by, a.kind AS from_kind, a.label AS from_label,
           b.kind AS to_kind, b.label AS to_label,
           ARRAY[a.label, b.label] AS path
      FROM impact_edges e
      JOIN n a ON a.id = e.from_node
      JOIN n b ON b.id = e.to_node
     WHERE e.project_id = p_project AND a.kind IN ('need','activity')
    UNION ALL
    SELECT w.depth + 1, e.from_node, e.to_node, e.link_type, e.evidence_id,
           e.reviewed_by, a.kind, a.label, b.kind, b.label, w.path || b.label
      FROM walk w
      JOIN impact_edges e ON e.from_node = w.to_node AND e.project_id = p_project
      JOIN n a ON a.id = e.from_node
      JOIN n b ON b.id = e.to_node
     WHERE w.depth < p_max_depth AND NOT (b.label = ANY (w.path))
  )
  SELECT depth, from_kind, from_label, to_kind, to_label, link_type,
         evidence_id IS NOT NULL, reviewed_by IS NOT NULL, path
    FROM walk ORDER BY depth, from_label, to_label
$$;
COMMENT ON FUNCTION result_chain IS
  'Percorre a teoria da mudança do projeto (atividade -> output -> outcome -> impacto) devolvendo o '
  'tipo de ligação de cada elo. Não promove hipótese a evidência: devolve link_type como declarado.';

-- ---------------------------------------------------------------- 5.3 lacuna territorial
-- A pergunta que o mapa de valor chama de diferenciadora para o governo: "onde NÃO estamos
-- investindo?" — demanda registrada contra oferta de projeto e de programa, por território.
--
-- Limite declarado na própria saída: `needs_with_source` conta quantas necessidades daquele
-- território têm fonte citada. Território cuja demanda foi estimada sem fonte produz lacuna que não
-- se deve tratar como fato — e a consulta diz isso em vez de esconder.
CREATE FUNCTION territorial_gap(p_territory_prefix text DEFAULT NULL)
  RETURNS TABLE (
    territory          text,
    needs_open         bigint,
    needs_critical     bigint,
    needs_with_source  bigint,
    people_estimate    bigint,
    projects_published bigint,
    programs_open      bigint,
    committed_cents    bigint)
  LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  WITH t AS (
    SELECT DISTINCT territory FROM territory_needs
     WHERE p_territory_prefix IS NULL OR territory LIKE p_territory_prefix || '%'
  )
  SELECT t.territory,
    (SELECT count(*) FROM territory_needs n
      WHERE n.territory = t.territory AND n.status IN ('open','partially_served')),
    (SELECT count(*) FROM territory_needs n
      WHERE n.territory = t.territory AND n.status IN ('open','partially_served')
        AND n.priority = 'critical'),
    (SELECT count(*) FROM territory_needs n
      WHERE n.territory = t.territory AND n.source_name IS NOT NULL),
    (SELECT coalesce(sum(n.people_estimate), 0) FROM territory_needs n
      WHERE n.territory = t.territory AND n.people_estimate IS NOT NULL),
    (SELECT count(*) FROM projects p
      WHERE p.territory = t.territory AND p.visibility = 'published'),
    (SELECT count(*) FROM programs g
      WHERE t.territory = ANY (g.territories) AND g.status IN ('open','in_execution')),
    (SELECT coalesce(sum(pf.committed_cents), 0) FROM projects p
       CROSS JOIN LATERAL project_funding(p.id) pf
      WHERE p.territory = t.territory)
  FROM t ORDER BY 2 DESC, 3 DESC
$$;
COMMENT ON FUNCTION territorial_gap IS
  'Demanda registrada contra oferta, por território. SECURITY DEFINER porque cruza necessidades, '
  'projetos e programas de ORGANIZAÇÕES DIFERENTES — é leitura agregada, sem dado de pessoa. '
  '`needs_with_source` existe para que lacuna apoiada em estimativa sem fonte não passe por fato.';


-- ============================================================================ 6. grupo de notificação
-- `program` é grupo PRÓPRIO, e não um apelido de `project`: quem administra um programa com dezenas de
-- projetos não quer o mesmo interruptor das notificações de execução de cada um deles.
--
-- Há um invariante (`test_v0160_invariants.test_python_vocabularies_match_the_database_checks`) que
-- compara as listas Python aos CHECKs reais do banco. Ele existe porque `notify.PRIORITIES` já divergiu
-- do banco uma vez, passou por lint e por toda a suíte, e só apareceria na primeira notificação de
-- prioridade máxima. Então as duas pontas mudam na mesma migração, ou o teste quebra.
ALTER TABLE notification_prefs DROP CONSTRAINT IF EXISTS notification_prefs_grp_check;
ALTER TABLE notification_prefs ADD CONSTRAINT notification_prefs_grp_check CHECK (
  grp = ANY (ARRAY['billing','content','events','support','partnerships','opportunities',
                   'network','proposal','message','funding','report','project','document','account',
                   'program']));
