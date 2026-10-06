-- 0020_v0170_monetization.sql — MOTOR DE MONETIZAÇÃO E A NOVA REGRA COMERCIAL
--
-- MUDANÇA DE REGRA COMERCIAL, POR DECISÃO DO PROPRIETÁRIO
--
-- A v0.16.0 cobrava US$ 1,99 → US$ 19,99/mês da organização que usa o produto, OSC inclusive. Esta
-- migração **aposenta essa regra como núcleo** e implementa a hierarquia dos documentos desta rodada:
--
--   1. SaaS institucional recorrente (fundação, instituto, financiador)  ← NÚCLEO
--   2. B2G (prefeitura, estado, secretaria, autarquia)                   ← NÚCLEO ESTRATÉGICO
--   3. Enterprise / ESG (empresa que precisa comprovar impacto)          ← EXPANSÃO
--   4. Implementação e integração                                         ← complementar
--   5. Marketplace / take rate                                            ← upside
--   6. Success fee                                                        ← upside CONDICIONADO
--   7. Premium para quem propõe                                           ← aquisição, NÃO núcleo
--
-- E a razão, nas palavras dos documentos: "o lado da oferta precisa crescer para aumentar o valor da
-- rede. Cobrar antecipadamente reduz a quantidade e diversidade de projetos."
--
-- POR QUE NENHUM PREÇO NOVO É FIXADO AQUI
--
-- Os documentos dão faixas (R$ 2.000–10.000/mês para financiador, R$ 10.000–50.000+ para órgão maior)
-- e as qualificam textualmente: "Esses valores são hipóteses de posicionamento, não preços finais".
-- Então as faixas entram como **hipótese declarada**, e `amount_cents` fica **nulo**. A plataforma já
-- recusa contratação online sem preço definido (`monetization.price_for`), e continua recusando.
--
-- O PORTÃO JURÍDICO É ESTRUTURAL
--
-- Os documentos exigem a cadeia `evento de valor → elegibilidade → monetização → VALIDAÇÃO JURÍDICA →
-- cobrança`. Aqui ela é um gatilho: uma regra de monetização **não pode ser ativada** sem carta legal
-- com status verde. E `success_fee` e `marketplace_take_rate` não podem ser ativadas de jeito nenhum
-- enquanto valer a ADR-022 (a plataforma não custodia nem processa aporte) — o gatilho recusa citando
-- a ADR pelo nome.

-- ============================================================================ 1. carta legal
CREATE TABLE monetization_legal_cards (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  rule_key      text NOT NULL CHECK (rule_key ~ '^[a-z][a-z0-9_.]{2,60}$'),
  payer         text NOT NULL CHECK (length(payer) BETWEEN 3 AND 200),
  beneficiary   text NOT NULL CHECK (length(beneficiary) BETWEEN 3 AND 200),
  billing_event text NOT NULL CHECK (length(billing_event) BETWEEN 5 AND 300),
  revenue_nature text NOT NULL CHECK (length(revenue_nature) BETWEEN 5 AND 300),
  contractual_relation text NOT NULL CHECK (length(contractual_relation) BETWEEN 5 AND 500),
  required_document text CHECK (length(required_document) <= 500),
  required_terms text CHECK (length(required_terms) <= 500),
  cancellation_policy text CHECK (length(cancellation_policy) <= 1000),
  refund_policy text CHECK (length(refund_policy) <= 1000),
  tax_notes     text CHECK (length(tax_notes) <= 4000),
  invoice_notes text CHECK (length(invoice_notes) <= 2000),
  regulatory_notes text CHECK (length(regulatory_notes) <= 4000),
  -- Base normativa COM fonte e data. Sem as duas, não é pesquisa: é opinião.
  legal_basis   text CHECK (length(legal_basis) <= 4000),
  source_name   text CHECK (length(source_name) BETWEEN 3 AND 300),
  source_url    text CHECK (source_url IS NULL OR source_url ~ '^https?://'),
  verified_on   date,
  -- Grau de certeza DA PESQUISA, não do parecer. Parecer não é coisa que a plataforma produza.
  certainty     text NOT NULL CHECK (certainty IN ('low','medium','high')),
  needs_lawyer    boolean NOT NULL DEFAULT true,
  needs_accountant boolean NOT NULL DEFAULT true,
  open_questions  text CHECK (length(open_questions) <= 4000),
  status        text NOT NULL CHECK (status IN ('green','yellow','red')),
  note          text CHECK (length(note) <= 4000),
  created_by    uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  -- Verde exige base, fonte e data. Ausência de proibição encontrada NÃO é base legal — e o CHECK
  -- impede que alguém marque verde só porque não achou vedação.
  CONSTRAINT green_needs_evidence CHECK (
    status <> 'green'
    OR (legal_basis IS NOT NULL AND source_name IS NOT NULL AND verified_on IS NOT NULL
        AND certainty = 'high' AND needs_lawyer = false)),
  -- Verde com pergunta aberta é contradição.
  CONSTRAINT green_has_no_open_questions CHECK (status <> 'green' OR open_questions IS NULL)
);
COMMENT ON TABLE monetization_legal_cards IS
  'Pesquisa de base normativa por receita, com fonte, data e grau de CERTEZA DA PESQUISA. NÃO é '
  'parecer jurídico e não substitui advogado nem contador. Verde exige base, fonte, data, certeza '
  'alta e needs_lawyer=false — e nunca pode ser atribuído por ausência de proibição encontrada.';
CREATE INDEX ix_legal_cards_rule ON monetization_legal_cards(rule_key, created_at DESC);

-- Append-only: a carta de ontem explica a decisão de ontem.
CREATE TRIGGER trg_legal_cards_append BEFORE UPDATE OR DELETE ON monetization_legal_cards
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

-- ============================================================================ 2. regras de monetização
CREATE TABLE monetization_rules (
  key           text PRIMARY KEY CHECK (key ~ '^[a-z][a-z0-9_.]{2,60}$'),
  label_pt      text NOT NULL CHECK (length(label_pt) BETWEEN 5 AND 200),
  -- Os sete motores de receita dos documentos, na ordem de hierarquia declarada.
  revenue_engine text NOT NULL CHECK (revenue_engine IN (
    'saas_institutional', 'b2g', 'enterprise', 'implementation',
    'marketplace_take_rate', 'success_fee', 'proponent_premium', 'data_intelligence')),
  engine_rank   smallint NOT NULL CHECK (engine_rank BETWEEN 1 AND 8),
  payer_kind    text NOT NULL CHECK (payer_kind IN ('osc','company','government','provider','individual')),
  trigger_kind  text NOT NULL CHECK (trigger_kind IN ('value_event','subscription','contract','transaction')),
  value_event_type text REFERENCES value_event_types(key) ON DELETE RESTRICT,
  pricing_mode  text NOT NULL CHECK (pricing_mode IN (
    'included_in_plan', 'unit', 'subscription', 'contract', 'percentage')),
  -- NULO = preço não definido. A plataforma recusa cobrar; não inventa.
  amount_cents  bigint CHECK (amount_cents IS NULL OR amount_cents >= 0),
  percentage    numeric(5,2) CHECK (percentage IS NULL OR (percentage > 0 AND percentage <= 100)),
  currency      char(3) CHECK (currency IS NULL OR currency ~ '^[A-Z]{3}$'),
  -- A faixa dos documentos, explicitamente marcada como hipótese a validar.
  hypothesis_min_cents bigint CHECK (hypothesis_min_cents IS NULL OR hypothesis_min_cents >= 0),
  hypothesis_max_cents bigint CHECK (hypothesis_max_cents IS NULL OR hypothesis_max_cents >= 0),
  hypothesis_note text CHECK (length(hypothesis_note) <= 2000),
  -- O que o cliente recebe, em uma frase. "Não venda 20 funcionalidades por R$99; venda um problema
  -- caro resolvido" — então a regra é obrigada a dizer qual problema.
  problem_solved text NOT NULL CHECK (length(problem_solved) BETWEEN 20 AND 600),
  substitution_answer text NOT NULL CHECK (length(substitution_answer) BETWEEN 20 AND 1000),
  legal_status   text NOT NULL DEFAULT 'review_required'
                 CHECK (legal_status IN ('review_required','validated','refused')),
  legal_card_id  uuid REFERENCES monetization_legal_cards(id) ON DELETE SET NULL,
  active        boolean NOT NULL DEFAULT false,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT hypothesis_range CHECK (
    hypothesis_min_cents IS NULL OR hypothesis_max_cents IS NULL
    OR hypothesis_max_cents >= hypothesis_min_cents),
  CONSTRAINT value_event_needs_type CHECK (
    (trigger_kind = 'value_event') = (value_event_type IS NOT NULL)),
  -- Percentual só existe em modo percentual. Mas modo percentual PODE estar sem número: é o estado de
  -- success fee e take rate nesta rodada, em que a faixa (0,5%–2%) é hipótese dos documentos e
  -- escrevê-la como configuração vigente seria inventar a regra antes do parecer.
  CONSTRAINT percentage_only_in_percentage_mode CHECK (
    percentage IS NULL OR pricing_mode = 'percentage')
);
COMMENT ON TABLE monetization_rules IS
  'Cada forma de receita, com pagador, evento, preço (ou a ausência dele), problema resolvido, '
  'resposta ao teste de substituição e o portão jurídico. `active` só vira verdadeiro com carta legal '
  'verde — e nunca para success_fee nem take rate enquanto valer a ADR-022.';
COMMENT ON COLUMN monetization_rules.substitution_answer IS
  'Por que isto não se resolve com planilha, e-mail, Drive, Notion ou ChatGPT. Os documentos são '
  'explícitos: "Tem IA" NÃO é argumento suficiente.';

CREATE TRIGGER trg_mon_rules_touch BEFORE UPDATE ON monetization_rules
  FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- ---------------------------------------------------------------- o portão
CREATE FUNCTION monetization_rule_gate() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_card record;
BEGIN
  IF NEW.active THEN
    -- 1) A ADR-022 é barreira ESTRUTURAL, não recomendação: a plataforma não custodia nem processa
    --    aporte, logo não existe transação dela sobre a qual cobrar percentual. Ativar success fee ou
    --    take rate exige antes DESFAZER a ADR-022, que é decisão jurídica e não técnica.
    IF NEW.revenue_engine IN ('success_fee','marketplace_take_rate') THEN
      RAISE EXCEPTION 'ADR-022: a plataforma não custodia nem processa aporte, então % não pode ser '
                      'ativada. A infraestrutura de cálculo existe e fica desligada até haver parecer '
                      'e revisão da ADR-022.', NEW.revenue_engine
        USING ERRCODE = '42501';
    END IF;
    -- 2) Sem carta legal verde, não ativa.
    IF NEW.legal_status <> 'validated' OR NEW.legal_card_id IS NULL THEN
      RAISE EXCEPTION 'regra de monetização % exige carta legal validada antes de ser ativada', NEW.key
        USING ERRCODE = '42501';
    END IF;
    SELECT status, needs_lawyer INTO v_card FROM monetization_legal_cards WHERE id = NEW.legal_card_id;
    IF v_card IS NULL OR v_card.status <> 'green' OR v_card.needs_lawyer THEN
      RAISE EXCEPTION 'a carta legal de % não está verde (ou ainda exige advogado)', NEW.key
        USING ERRCODE = '42501';
    END IF;
    -- 3) Sem preço, não cobra. Preço inventado é o que esta trava existe para impedir.
    IF NEW.pricing_mode IN ('unit','subscription') AND NEW.amount_cents IS NULL THEN
      RAISE EXCEPTION 'regra % não tem preço definido: a plataforma recusa cobrar em vez de inventar',
        NEW.key USING ERRCODE = '23514';
    END IF;
    IF NEW.pricing_mode IN ('unit','subscription') AND NEW.currency IS NULL THEN
      RAISE EXCEPTION 'regra % não tem moeda definida', NEW.key USING ERRCODE = '23514';
    END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_mon_rule_gate BEFORE INSERT OR UPDATE ON monetization_rules
  FOR EACH ROW EXECUTE FUNCTION monetization_rule_gate();

-- `legal_status` e `active` são da administração. A guarda normal não serve (só a administração
-- escreve esta tabela, e `guard_columns` isenta `app_priv()`), então o portão acima é a trava.

-- ============================================================================ 3. eventos faturáveis
-- A ponte entre valor e cobrança — e ela é deliberadamente uma ponte com pedágio, não um atalho.
CREATE TABLE billable_events (
  id            bigserial PRIMARY KEY,
  value_event_id bigint NOT NULL REFERENCES value_events(id) ON DELETE CASCADE,
  rule_key      text NOT NULL REFERENCES monetization_rules(key) ON DELETE RESTRICT,
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  -- `candidate` é o estado mais importante: houve valor, há regra, e **não** há cobrança — porque a
  -- regra não está ativa. É a fila do que PODERIA ser monetizado, visível sem cobrar ninguém.
  status        text NOT NULL CHECK (status IN (
    'candidate', 'blocked_legal', 'blocked_no_price', 'eligible', 'billed', 'waived')),
  reason        text NOT NULL CHECK (length(reason) BETWEEN 5 AND 500),
  amount_cents  bigint CHECK (amount_cents IS NULL OR amount_cents >= 0),
  currency      char(3) CHECK (currency IS NULL OR currency ~ '^[A-Z]{3}$'),
  invoice_id    uuid REFERENCES invoices(id) ON DELETE SET NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (value_event_id, rule_key)
);
COMMENT ON TABLE billable_events IS
  'Candidatos a cobrança derivados de value_events por monetization_rules. Um evento de valor NÃO '
  'produz cobrança: produz um candidato, cujo estado diz por que ainda não é cobrado.';
CREATE INDEX ix_billable_org ON billable_events(org_id, created_at DESC);
CREATE INDEX ix_billable_status ON billable_events(status) WHERE status IN ('eligible','candidate');
CREATE INDEX ix_billable_rule ON billable_events(rule_key);
CREATE INDEX ix_billable_value ON billable_events(value_event_id);

CREATE TRIGGER trg_billable_append BEFORE DELETE ON billable_events
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

-- Avalia um evento de valor contra as regras e registra o candidato com o MOTIVO do estado.
CREATE FUNCTION app_promote_billable(p_value_event bigint) RETURNS integer
  LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE v_ev record; v_rule record; v_status text; v_reason text; v_amount bigint; v_n integer := 0;
BEGIN
  SELECT id, event_type, org_id, units INTO v_ev FROM value_events WHERE id = p_value_event;
  IF v_ev IS NULL THEN RETURN 0; END IF;
  FOR v_rule IN
    SELECT r.*, o.kind AS org_kind
      FROM monetization_rules r
      JOIN organizations o ON o.id = v_ev.org_id
     WHERE r.trigger_kind = 'value_event' AND r.value_event_type = v_ev.event_type
       AND r.payer_kind = o.kind
  LOOP
    v_amount := NULL;
    IF NOT v_rule.active THEN
      IF v_rule.legal_status <> 'validated' THEN
        v_status := 'blocked_legal';
        v_reason := 'Regra existe, mas a carta legal não está validada. Nada é cobrado.';
      ELSIF v_rule.pricing_mode IN ('unit','subscription') AND v_rule.amount_cents IS NULL THEN
        v_status := 'blocked_no_price';
        v_reason := 'Regra validada, mas sem preço definido. A plataforma recusa cobrar em vez de inventar.';
      ELSE
        v_status := 'candidate';
        v_reason := 'Regra pronta e desativada por decisão comercial. Nada é cobrado.';
      END IF;
    ELSIF v_rule.pricing_mode = 'included_in_plan' THEN
      v_status := 'waived';
      v_reason := 'Incluído no plano contratado: o valor foi entregue e não gera cobrança adicional.';
    ELSE
      v_status := 'eligible';
      v_reason := 'Regra ativa com preço definido e carta legal verde.';
      v_amount := v_rule.amount_cents * greatest(v_ev.units, 1);
    END IF;
    INSERT INTO billable_events(value_event_id, rule_key, org_id, status, reason, amount_cents, currency)
    VALUES (p_value_event, v_rule.key, v_ev.org_id, v_status, v_reason, v_amount, v_rule.currency)
    ON CONFLICT (value_event_id, rule_key) DO NOTHING;
    v_n := v_n + 1;
  END LOOP;
  RETURN v_n;
END $$;
COMMENT ON FUNCTION app_promote_billable IS
  'Deriva candidatos a cobrança de um evento de valor. SECURITY DEFINER porque cruza regras de '
  'monetização (que a organização não lê) com o evento dela. Registra o MOTIVO de cada estado, de '
  'modo que "por que isto não foi cobrado" tenha resposta consultável.';

-- ============================================================================ 4. RLS
ALTER TABLE monetization_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE monetization_legal_cards ENABLE ROW LEVEL SECURITY;
ALTER TABLE billable_events ENABLE ROW LEVEL SECURITY;

-- As regras são públicas para quem tem conta: quem paga tem direito de ver a regra que o cobra, o
-- problema que ela diz resolver e se a carta legal está verde.
CREATE POLICY mon_rules_read ON monetization_rules FOR SELECT USING (app_authenticated() OR app_priv());
CREATE POLICY mon_rules_write ON monetization_rules FOR INSERT WITH CHECK (app_priv());
CREATE POLICY mon_rules_update ON monetization_rules FOR UPDATE USING (app_priv()) WITH CHECK (app_priv());

-- A carta legal também: é a transparência que torna a cobrança defensável.
CREATE POLICY legal_cards_read ON monetization_legal_cards FOR SELECT USING (app_authenticated() OR app_priv());
CREATE POLICY legal_cards_write ON monetization_legal_cards FOR INSERT WITH CHECK (app_priv());

CREATE POLICY billable_read ON billable_events FOR SELECT USING (org_id = app_org() OR app_priv());
CREATE POLICY billable_update ON billable_events FOR UPDATE USING (app_priv()) WITH CHECK (app_priv());

GRANT SELECT ON monetization_rules, monetization_legal_cards TO impacto_app;
GRANT INSERT, UPDATE ON monetization_rules TO impacto_app;
GRANT INSERT ON monetization_legal_cards TO impacto_app;
GRANT SELECT, UPDATE ON billable_events TO impacto_app;
REVOKE INSERT, DELETE ON billable_events FROM impacto_app;

-- ============================================================================ 5. as regras, semeadas
-- Todas nascem `active = false` e `legal_status = 'review_required'`. As faixas são as DOS DOCUMENTOS
-- desta rodada, registradas como hipótese com a atribuição explícita — não são preços da plataforma.
INSERT INTO monetization_rules(
    key, label_pt, revenue_engine, engine_rank, payer_kind, trigger_kind, value_event_type,
    pricing_mode, currency, hypothesis_min_cents, hypothesis_max_cents, hypothesis_note,
    problem_solved, substitution_answer) VALUES

-- 1 — NÚCLEO
('saas.institutional.funder', 'SaaS institucional para quem financia', 'saas_institutional', 1,
 'company', 'subscription', NULL, 'subscription', 'BRL', 200000, 1000000,
 'Faixa de posicionamento declarada nos documentos da rodada (R$ 2.000–10.000+/mês para fundação e '
 'financiador), qualificada por eles como hipótese e não preço final. Preço final em aberto.',
 'Receber, triar, avaliar, selecionar, contratar, acompanhar e comprovar centenas de projetos por ano '
 'sem planilha, e-mail e pasta compartilhada — e conseguir prestar contas do que foi financiado.',
 'Planilha armazena; não orquestra etapa, não registra quem decidiu o quê, não cobra evidência no '
 'prazo e não liga recurso a resultado comprovado. A trilha encadeada por hash e a RLS por '
 'organização não existem em Drive nem em Notion, e nenhuma delas é "ter IA".'),

-- 2 — NÚCLEO ESTRATÉGICO
('b2g.territorial_governance', 'Governança territorial para governo', 'b2g', 2,
 'government', 'contract', NULL, 'contract', 'BRL', 300000, 5000000,
 'Faixa declarada nos documentos (R$ 3.000–10.000/mês para prefeitura pequena; R$ 10.000–50.000+ para '
 'órgão maior), qualificada por eles como hipótese. Contratação pública tem regime próprio: ver carta '
 'legal antes de qualquer proposta.',
 'Responder "o que está acontecendo no meu território, onde o dinheiro está indo, o que está '
 'funcionando e onde existe lacuna" com dado rastreável até a evidência.',
 'O dado hoje está fragmentado entre secretarias, fundos, editais e prestações de contas em formatos '
 'diferentes. O que a plataforma faz e a planilha não faz é cruzar demanda registrada com oferta por '
 'território e sustentar cada número com a fonte dele.'),

-- 3 — EXPANSÃO
('enterprise.esg_portfolio', 'Portfólio e comprovação de impacto para empresa', 'enterprise', 3,
 'company', 'contract', NULL, 'contract', 'BRL', 300000, 1500000,
 'Faixa declarada nos documentos (R$ 3.000–15.000+/mês), qualificada por eles como hipótese.',
 'Provar, com evidência rastreável, que o investimento social e ambiental da empresa produziu '
 'resultado — e não apenas que houve atividade.',
 'Relatório de ESG montado à mão não permite auditar da afirmação até o documento que a sustenta. '
 'A cadeia atividade → output → outcome → impacto com a FORÇA de cada elo declarada é o que distingue '
 'comprovação de narrativa.'),

-- 4 — COMPLEMENTAR
('implementation.setup', 'Implantação, integração e migração', 'implementation', 4,
 'company', 'contract', NULL, 'contract', 'BRL', NULL, NULL,
 'Os documentos citam implantação como receita complementar de alta margem, sem faixa. Em aberto.',
 'Entrar em operação com o histórico que a organização já tem, integrado aos sistemas que ela já usa, '
 'sem recomeçar o cadastro de tudo.',
 'É serviço humano sobre a plataforma, não função de software: migração de dado legado, mapeamento de '
 'campo e configuração de integração.'),

-- 5 e 6 — UPSIDE BLOQUEADO PELA ADR-022
('marketplace.take_rate', 'Comissão sobre contratação no marketplace', 'marketplace_take_rate', 5,
 'osc', 'transaction', NULL, 'percentage', 'BRL', NULL, NULL,
 'Os documentos sugerem take rate (exemplo de 10% sobre contrato) e mandam tratá-lo como condicionado. '
 'NÃO há percentual configurado: a ADR-022 impede que a plataforma intermedeie pagamento, logo não '
 'existe transação dela sobre a qual cobrar. Infraestrutura presente e DESLIGADA.',
 'Encontrar e contratar quem presta serviço especializado para o projeto, com reputação e entrega '
 'verificável.',
 'Hoje o marketplace é VITRINE: anúncio e contato. Contratação com pagamento dentro da plataforma não '
 'existe, e é pré-requisito para qualquer comissão.'),

('success_fee.funding', 'Taxa de êxito sobre operação financiada', 'success_fee', 6,
 'osc', 'transaction', NULL, 'percentage', 'BRL', NULL, NULL,
 'Os documentos sugerem 0,5%–2% e mandam NÃO presumir que seja permitido. NÃO há percentual '
 'configurado. A ADR-022 e a ADR-031 estabelecem que a plataforma não custodia nem processa aporte '
 'justamente para evitar enquadramento como instituição de pagamento; ativar esta regra exige antes '
 'desfazer a ADR-022, que é decisão jurídica e não técnica.',
 'Alinhar o custo da plataforma ao momento em que existe valor econômico real para a organização.',
 'Nenhum software substitui aqui: é modelo de remuneração, não função. E o modelo depende de estrutura '
 'jurídica que a plataforma deliberadamente não tem.'),

-- 7 — AQUISIÇÃO, NÃO NÚCLEO
('premium.readiness_analysis', 'Análise avançada de prontidão', 'proponent_premium', 7,
 'osc', 'value_event', 'readiness.evaluated', 'unit', 'BRL', 2900, 2900,
 'Os documentos citam R$ 29 para análise avançada, como exemplo hipotético. Preço final em aberto; '
 'a análise BÁSICA de prontidão é e continua gratuita.',
 'Saber, antes de submeter, o que falta para o projeto estar pronto — com o item, a razão e o que '
 'fazer, em vez de descobrir na recusa depois do prazo.',
 'ChatGPT opina sobre o texto; não confere se o documento está no cofre, se o indicador tem valor '
 'lançado, se a evidência foi aceita e se o orçamento fecha. A prontidão é calculada contra o estado '
 'real do projeto no banco.'),

('premium.document_preparation', 'Preparação completa de documento', 'proponent_premium', 7,
 'osc', 'value_event', 'document.assembled', 'unit', 'BRL', 7900, 7900,
 'Os documentos citam R$ 79 para preparação completa, como exemplo hipotético. Preço final em aberto.',
 'Chegar com o documento montado a partir do domínio, completo e revisto a quatro olhos, em vez de '
 'recomeçar do zero a cada edital.',
 'Modelo em editor de texto não deriva campo do projeto, não recusa gerar incompleto dizendo o que '
 'falta, não exige aprovação de segunda pessoa e não congela o hash do que foi assinado.'),

-- 8 — EXPANSÃO DE ALTO VALOR
('data.territorial_intelligence', 'Inteligência territorial agregada', 'data_intelligence', 8,
 'government', 'contract', NULL, 'contract', 'BRL', NULL, NULL,
 'Os documentos citam BI e inteligência territorial como o maior ticket potencial, sem faixa. Em '
 'aberto, e condicionado a tratamento agregado: dado pessoal não é produto.',
 'Decidir onde investir a partir de onde a demanda registrada não encontra oferta.',
 'É dado que só existe porque a operação acontece na plataforma. Nenhuma planilha tem a série, e '
 'comprá-la de fora não traz a ligação com a evidência de cada projeto.');
