-- 0016 — v0.16.0: IMPACT NETWORK CORE. A camada de REDE em cima do núcleo que a v0.15.0 fechou.
--
-- ACHADO QUE ORIGINOU ESTA MIGRAÇÃO (RECONSTRUCTION_AUDIT.md §2.1): o relacionamento estava espalhado em seis
-- tabelas ad-hoc de duas ou três colunas (`follows`, `favorites`, `org_blocks`, `need_offers`, `solution_intents`,
-- `partnership_requests`), nenhuma com visibilidade, contexto, estado uniforme ou trilha. Acrescentar investimento,
-- mentoria, voluntariado e apoio governamental naquele modelo criaria dez tabelas novas de duas colunas.
--
-- O QUE ESTA MIGRAÇÃO FAZ: cria o modelo unificado de relação, o motor de proposta, a conversa COM CONTEXTO, o
-- alcance de notificação para a EQUIPE, a publicação governada do marketplace, o relatório periódico de impacto,
-- persona/capacidade, taxonomia versionada, perfil público com @identificador, escada de sanção e território.
--
-- O QUE ESTA MIGRAÇÃO **NÃO** FAZ: não apaga nem quebra nada do que existe. `follows`, `favorites` e `org_blocks`
-- continuam existindo e funcionando (as rotas atuais dependem delas); o dado delas é ESPELHADO em `relationships`
-- por gatilho, nos dois sentidos, para que a rede veja tudo sem que a camada antiga pare de funcionar.
--
-- REUSA: guard_columns · forbid_mutation · touch_updated_at · app_org/app_uid/app_priv/app_authenticated ·
-- ledger_entries (trilha encadeada) · documents (cofre) · app_notify · app_related · app_blocked_between.

-- ================================================================================================ 1. RELAÇÃO
-- Origem é SEMPRE uma organização ou uma pessoa; destino é uma de sete coisas. As colunas são chave estrangeira de
-- verdade (não `target_id` solto) para que a propriedade "não existe linha órfã possível" continue valendo — são
-- 529 chaves estrangeiras no banco e nenhuma referência por convenção.
CREATE TABLE relationships (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  kind          text NOT NULL CHECK (kind IN (
                  -- descoberta e acompanhamento (unilateral, não exige consentimento do outro lado)
                  'favorite','watchlist','follow','block',
                  -- aproximação e negociação
                  'contact','proposal',
                  -- relação formalizada
                  'partnership','investment','sponsorship','service','mentorship','volunteer','collaboration',
                  'support','government_support',
                  -- participação em projeto
                  'project_member','project_partner','project_sponsor','project_investor',
                  -- procedência
                  'referral','verified_by')),
  source_org_id  uuid REFERENCES organizations(id) ON DELETE CASCADE,
  source_user_id uuid REFERENCES users(id) ON DELETE CASCADE,
  target_org_id      uuid REFERENCES organizations(id) ON DELETE CASCADE,
  target_user_id     uuid REFERENCES users(id) ON DELETE CASCADE,
  target_project_id  uuid REFERENCES projects(id) ON DELETE CASCADE,
  target_solution_id uuid REFERENCES solutions(id) ON DELETE CASCADE,
  target_call_id     uuid REFERENCES calls(id) ON DELETE CASCADE,
  target_need_id     uuid REFERENCES project_needs(id) ON DELETE CASCADE,
  target_idea_id     uuid REFERENCES ideas(id) ON DELETE CASCADE,
  -- EXATAMENTE uma origem e EXATAMENTE um destino
  CONSTRAINT rel_one_source CHECK ((source_org_id IS NOT NULL)::int + (source_user_id IS NOT NULL)::int = 1),
  CONSTRAINT rel_one_target CHECK ((target_org_id IS NOT NULL)::int + (target_user_id IS NOT NULL)::int
                                 + (target_project_id IS NOT NULL)::int + (target_solution_id IS NOT NULL)::int
                                 + (target_call_id IS NOT NULL)::int + (target_need_id IS NOT NULL)::int
                                 + (target_idea_id IS NOT NULL)::int = 1),
  -- o inquilino dono da relação (quem a criou); a RLS usa esta coluna
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  -- contexto: a relação quase sempre existe POR CAUSA de algo
  context_project_id uuid REFERENCES projects(id) ON DELETE SET NULL,
  role          text CHECK (role IS NULL OR role ~ '^[a-z0-9_]{2,40}$'),
  -- "o fato de a relação existir não significa que ela seja pública" (prompt §4)
  visibility    text NOT NULL DEFAULT 'private'
                  CHECK (visibility IN ('private','participants','organization','network','public')),
  status        text NOT NULL DEFAULT 'active'
                  CHECK (status IN ('pending','active','paused','ended','declined','revoked')),
  -- evidência que sustenta a relação, quando houver (ex.: termo assinado de parceria)
  evidence_document_id uuid REFERENCES documents(id) ON DELETE SET NULL,
  metadata      jsonb NOT NULL DEFAULT '{}'::jsonb,
  note          text CHECK (length(note) <= 2000),
  mirrored_from text CHECK (mirrored_from IN ('follows','favorites','org_blocks')),  -- espelho da camada antiga
  created_by    uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  ended_at      timestamptz,
  ended_reason  text CHECK (length(ended_reason) <= 500),
  CHECK (status NOT IN ('ended','declined','revoked') OR ended_at IS NOT NULL)
);
-- Uma relação por (tipo, origem, destino, contexto). Sem isto, "favoritar" duas vezes cria duas linhas.
CREATE UNIQUE INDEX ux_rel_identity ON relationships(
  kind,
  coalesce(source_org_id, source_user_id),
  coalesce(target_org_id, target_user_id, target_project_id, target_solution_id, target_call_id, target_need_id,
           target_idea_id),
  coalesce(context_project_id, '00000000-0000-0000-0000-000000000000'::uuid));
CREATE INDEX ix_rel_org ON relationships(org_id, kind, status);
CREATE INDEX ix_rel_target_org ON relationships(target_org_id) WHERE target_org_id IS NOT NULL;
CREATE INDEX ix_rel_target_project ON relationships(target_project_id) WHERE target_project_id IS NOT NULL;
CREATE INDEX ix_rel_target_user ON relationships(target_user_id) WHERE target_user_id IS NOT NULL;
CREATE INDEX ix_rel_context ON relationships(context_project_id) WHERE context_project_id IS NOT NULL;
COMMENT ON TABLE relationships IS
  'Relação única da rede. A existência da relação NÃO implica que ela seja visível: visibility decide.';

-- Espelho da camada antiga: `follows`, `favorites` e `org_blocks` continuam sendo a fonte das rotas atuais, e cada
-- linha delas aparece aqui como relação. Assim a rede enxerga tudo sem que nada existente pare de funcionar.
CREATE FUNCTION rel_mirror() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE v_kind text; v_src uuid; v_tgt_org uuid; v_tgt_proj uuid;
BEGIN
  IF TG_TABLE_NAME = 'follows' THEN
    v_kind := 'follow';
    v_src := coalesce(NEW.follower_org_id, OLD.follower_org_id);
    v_tgt_org := coalesce(NEW.followed_org_id, OLD.followed_org_id);
  ELSIF TG_TABLE_NAME = 'org_blocks' THEN
    v_kind := 'block';
    v_src := coalesce(NEW.org_id, OLD.org_id);
    v_tgt_org := coalesce(NEW.blocked_org_id, OLD.blocked_org_id);
  ELSE
    v_kind := 'favorite';
    v_src := coalesce(NEW.org_id, OLD.org_id);
    v_tgt_proj := coalesce(NEW.project_id, OLD.project_id);
  END IF;
  IF TG_OP = 'DELETE' THEN
    DELETE FROM relationships r WHERE r.kind = v_kind AND r.source_org_id = v_src
      AND r.mirrored_from = TG_TABLE_NAME
      AND (v_tgt_org IS NULL OR r.target_org_id = v_tgt_org)
      AND (v_tgt_proj IS NULL OR r.target_project_id = v_tgt_proj);
    RETURN OLD;
  END IF;
  INSERT INTO relationships(kind, source_org_id, target_org_id, target_project_id, org_id, visibility, status,
                            mirrored_from, created_by)
  VALUES (v_kind, v_src, v_tgt_org, v_tgt_proj, v_src,
          CASE WHEN v_kind = 'follow' THEN 'network' ELSE 'private' END, 'active', TG_TABLE_NAME, app_uid())
  ON CONFLICT DO NOTHING;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_rel_mirror AFTER INSERT OR DELETE ON follows FOR EACH ROW EXECUTE FUNCTION rel_mirror();
CREATE TRIGGER trg_rel_mirror AFTER INSERT OR DELETE ON org_blocks FOR EACH ROW EXECUTE FUNCTION rel_mirror();
CREATE TRIGGER trg_rel_mirror AFTER INSERT OR DELETE ON favorites FOR EACH ROW EXECUTE FUNCTION rel_mirror();

-- Travessia por função SECURITY DEFINER (ADR 104: política que consulta outra tabela diretamente causa recursão).
CREATE FUNCTION rel_is_party(p_rel uuid, p_org uuid, p_user uuid)
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
  SELECT EXISTS (SELECT 1 FROM relationships r WHERE r.id = p_rel
                   AND (r.org_id = p_org OR r.source_org_id = p_org OR r.target_org_id = p_org
                        OR r.source_user_id = p_user OR r.target_user_id = p_user
                        OR EXISTS (SELECT 1 FROM projects p WHERE p.id = r.target_project_id AND p.org_id = p_org)));
$$;
REVOKE EXECUTE ON FUNCTION rel_is_party(uuid, uuid, uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION rel_is_party(uuid, uuid, uuid) TO impacto_app;

-- ================================================================================================ 2. PROPOSTA
-- Proposta NÃO é contrato, NÃO é investimento, NÃO é pagamento. Esta tabela existe para que essa distinção seja
-- estrutural e não uma frase na documentação.
CREATE TABLE proposals (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  kind          text NOT NULL CHECK (kind IN ('investment','sponsorship','service','partnership','mentorship',
                                              'volunteer','collaboration','project_support','government_support')),
  -- quem propõe
  sender_org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  sender_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  -- quem recebe (organização; pessoa física participa pela organização dela, como no resto da plataforma)
  receiver_org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  CHECK (sender_org_id <> receiver_org_id),
  -- contexto: proposta sem contexto é spam
  project_id    uuid REFERENCES projects(id) ON DELETE SET NULL,
  need_id       uuid REFERENCES project_needs(id) ON DELETE SET NULL,
  call_id       uuid REFERENCES calls(id) ON DELETE SET NULL,
  solution_id   uuid REFERENCES solutions(id) ON DELETE SET NULL,
  relationship_id uuid REFERENCES relationships(id) ON DELETE SET NULL,
  title         text NOT NULL CHECK (length(title) BETWEEN 3 AND 200),
  purpose       text NOT NULL CHECK (length(purpose) BETWEEN 10 AND 4000),
  terms         text CHECK (length(terms) <= 8000),
  -- valor PROPOSTO, em centavos. NÃO é dinheiro recebido, NÃO é compromisso.
  amount_cents  bigint CHECK (amount_cents IS NULL OR amount_cents BETWEEN 0 AND 1000000000000),
  currency      char(3) NOT NULL DEFAULT 'BRL' CHECK (currency ~ '^[A-Z]{3}$'),
  -- modalidade do apoio proposto, para que "apoio" não signifique só dinheiro
  support_mode  text CHECK (support_mode IS NULL OR support_mode IN ('financial','service','equipment','knowledge',
                                                                     'volunteer','sponsorship','mentorship','other')),
  compensation  text CHECK (compensation IS NULL OR compensation IN ('paid','pro_bono','volunteer','partnership',
                                                                     'mentorship')),
  version       integer NOT NULL DEFAULT 1 CHECK (version >= 1),
  status        text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','sent','viewed','in_review',
                  'changes_requested','accepted','declined','expired','withdrawn','cancelled')),
  decided_at    timestamptz,
  decided_by    uuid REFERENCES users(id) ON DELETE SET NULL,
  decision_note text CHECK (length(decision_note) <= 2000),
  viewed_at     timestamptz,
  sent_at       timestamptz,
  expires_at    timestamptz,
  created_by    uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  -- recusar e pedir mudança exigem explicação: decisão sem motivo não é devolutiva
  CHECK (status NOT IN ('declined','changes_requested') OR coalesce(length(trim(decision_note)), 0) >= 3),
  CHECK (status NOT IN ('accepted','declined','changes_requested') OR decided_at IS NOT NULL)
);
CREATE INDEX ix_prop_receiver ON proposals(receiver_org_id, status, created_at DESC);
CREATE INDEX ix_prop_sender ON proposals(sender_org_id, status, created_at DESC);
CREATE INDEX ix_prop_project ON proposals(project_id) WHERE project_id IS NOT NULL;
COMMENT ON TABLE proposals IS
  'Proposta. NÃO é contrato, NÃO é compromisso financeiro, NÃO é pagamento. amount_cents é valor PROPOSTO.';

CREATE TABLE proposal_events (
  id            bigserial PRIMARY KEY,
  proposal_id   uuid NOT NULL REFERENCES proposals(id) ON DELETE CASCADE,
  from_status   text,
  to_status     text NOT NULL,
  actor_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  actor_org_id  uuid REFERENCES organizations(id) ON DELETE SET NULL,
  note          text CHECK (length(note) <= 2000),
  at            timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_propev_proposal ON proposal_events(proposal_id, id DESC);

CREATE TABLE proposal_attachments (
  proposal_id   uuid NOT NULL REFERENCES proposals(id) ON DELETE CASCADE,
  document_id   uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  label         text CHECK (length(label) <= 200),
  added_by      uuid REFERENCES users(id) ON DELETE SET NULL,
  added_at      timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (proposal_id, document_id)
);

-- Máquina de estados da proposta, como DADO (mesmo princípio do projeto na 0013).
CREATE TABLE proposal_status_graph (
  from_status   text NOT NULL,
  to_status     text NOT NULL,
  actor         text NOT NULL CHECK (actor IN ('sender','receiver','either','system')),
  requires_note boolean NOT NULL DEFAULT false,
  note          text,
  PRIMARY KEY (from_status, to_status)
);
INSERT INTO proposal_status_graph(from_status, to_status, actor, requires_note, note) VALUES
  ('draft','sent','sender', false, NULL),
  ('draft','cancelled','sender', false, NULL),
  ('sent','viewed','receiver', false, 'marcada como vista ao abrir'),
  ('sent','withdrawn','sender', true, NULL),
  ('sent','expired','system', false, 'prazo da proposta venceu'),
  ('viewed','in_review','receiver', false, NULL),
  ('viewed','accepted','receiver', false, NULL),
  ('viewed','declined','receiver', true, NULL),
  ('viewed','changes_requested','receiver', true, NULL),
  ('viewed','withdrawn','sender', true, NULL),
  ('viewed','expired','system', false, NULL),
  ('in_review','accepted','receiver', false, NULL),
  ('in_review','declined','receiver', true, NULL),
  ('in_review','changes_requested','receiver', true, NULL),
  ('in_review','withdrawn','sender', true, NULL),
  ('in_review','expired','system', false, NULL),
  ('changes_requested','sent','sender', false, 'proposta revisada e reenviada (nova versão)'),
  ('changes_requested','withdrawn','sender', true, NULL),
  ('changes_requested','expired','system', false, NULL);

-- Guarda de transição E origem dos carimbos de tempo.
--
-- Os carimbos `sent_at`, `viewed_at`, `decided_at` e `decided_by` são DERIVADOS da transição, nunca enviados pelo
-- cliente — por isso estão na lista de `guard_columns` logo abaixo. A diferença é prática: "quando esta proposta foi
-- vista" deixa de ser um campo que alguém pode preencher e passa a ser consequência de a proposta ter sido aberta.
-- Mesma escolha de Evidence.verified na 0013: o fato deriva da origem, não da declaração.
CREATE FUNCTION proposal_status_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.status = OLD.status THEN RETURN NEW; END IF;
  IF NOT EXISTS (SELECT 1 FROM proposal_status_graph g
                  WHERE g.from_status = OLD.status AND g.to_status = NEW.status) THEN
    RAISE EXCEPTION 'Transição de proposta % → % não é permitida', OLD.status, NEW.status USING ERRCODE = '42501';
  END IF;
  IF NEW.status = 'sent' THEN
    NEW.sent_at := now();
    IF OLD.status = 'changes_requested' THEN   -- reenvio após ajuste: nova VERSÃO, e o que já foi visto/decidido cai
      NEW.version := OLD.version + 1;          -- versão também é derivada: ninguém pode reescrever o número da versão
      NEW.viewed_at := NULL; NEW.decided_at := NULL; NEW.decided_by := NULL;
    END IF;
  END IF;
  IF NEW.status = 'viewed' AND NEW.viewed_at IS NULL THEN NEW.viewed_at := now(); END IF;
  IF NEW.status IN ('accepted','declined','changes_requested') THEN
    NEW.decided_at := now();
    NEW.decided_by := coalesce(app_uid(), NEW.decided_by);
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_prop_status BEFORE UPDATE OF status ON proposals FOR EACH ROW
  EXECUTE FUNCTION proposal_status_guard();

CREATE FUNCTION proposal_is_party(p_prop uuid, p_org uuid)
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
  SELECT EXISTS (SELECT 1 FROM proposals p WHERE p.id = p_prop
                   AND (p.sender_org_id = p_org OR p.receiver_org_id = p_org));
$$;
REVOKE EXECUTE ON FUNCTION proposal_is_party(uuid, uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION proposal_is_party(uuid, uuid) TO impacto_app;

-- ================================================================================================ 3. CONVERSA COM CONTEXTO
-- `conversations(org_a, org_b)` fica como está: as rotas atuais dependem dela e a RLS de `messages` se apoia na RLS
-- dela (um recado só é legível se a conversa for legível — mecanismo correto, preservado).
-- Pessoa física participa pela organização dela (`individual`/`provider`), que é o modelo que a plataforma já usa.
ALTER TABLE conversations ADD COLUMN subject text CHECK (subject IS NULL OR length(subject) <= 200);
ALTER TABLE conversations ADD COLUMN context_project_id uuid REFERENCES projects(id) ON DELETE SET NULL;
ALTER TABLE conversations ADD COLUMN context_proposal_id uuid REFERENCES proposals(id) ON DELETE SET NULL;
ALTER TABLE conversations ADD COLUMN context_need_id uuid REFERENCES project_needs(id) ON DELETE SET NULL;
ALTER TABLE conversations ADD COLUMN context_call_id uuid REFERENCES calls(id) ON DELETE SET NULL;
ALTER TABLE conversations ADD COLUMN status text NOT NULL DEFAULT 'open'
  CHECK (status IN ('open','archived','closed'));
ALTER TABLE conversations ADD COLUMN last_message_at timestamptz;
ALTER TABLE conversations ADD COLUMN created_by uuid REFERENCES users(id) ON DELETE SET NULL;
CREATE INDEX ix_conv_context_project ON conversations(context_project_id) WHERE context_project_id IS NOT NULL;
CREATE INDEX ix_conv_context_proposal ON conversations(context_proposal_id) WHERE context_proposal_id IS NOT NULL;
COMMENT ON COLUMN conversations.context_project_id IS
  'Contexto da conversa. Negociação profissional sem contexto não é tratada como conversa da rede.';

-- Recado pode ser texto da pessoa, fato do sistema ou referência a uma proposta/documento.
ALTER TABLE messages ADD COLUMN kind text NOT NULL DEFAULT 'text'
  CHECK (kind IN ('text','system','event','proposal_ref','document_ref'));
ALTER TABLE messages ADD COLUMN ref_type text CHECK (ref_type IS NULL OR ref_type IN ('proposal','document',
  'project','relationship','impact_update','milestone'));
ALTER TABLE messages ADD COLUMN ref_id uuid;
CREATE INDEX ix_msg_conv_at ON messages(conversation_id, created_at DESC);

CREATE TABLE message_attachments (
  message_id    uuid NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
  document_id   uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  PRIMARY KEY (message_id, document_id)
);
COMMENT ON TABLE message_attachments IS
  'O arquivo continua governado pelo cofre (documents). Não há segundo armazenamento.';

-- ================================================================================================ 4. NOTIFICAÇÃO PARA A EQUIPE
-- PEDIDO EXPLÍCITO DESTA RODADA: notificar TODA A EQUIPE envolvida a cada evolução de etapa ou documento juntado.
-- `app_notify(org, NULL, …)` grava UMA linha com user_id nulo — aparece na lista da organização, mas não chega a
-- ninguém em particular. Aqui o alcance é por PESSOA, respeitando a preferência de cada uma.
ALTER TABLE notifications ADD COLUMN actor_user_id uuid REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE notifications ADD COLUMN priority text NOT NULL DEFAULT 'normal'
  CHECK (priority IN ('low','normal','high','critical'));
ALTER TABLE notifications ADD COLUMN project_id uuid REFERENCES projects(id) ON DELETE CASCADE;
ALTER TABLE notifications ADD COLUMN ref_type text CHECK (ref_type IS NULL OR length(ref_type) <= 40);
ALTER TABLE notifications ADD COLUMN ref_id uuid;
-- chave de idempotência: o mesmo fato notificado duas vezes (reprocessamento de job, duplo clique) não duplica
ALTER TABLE notifications ADD COLUMN dedupe_key text CHECK (dedupe_key IS NULL OR length(dedupe_key) <= 200);
ALTER TABLE notifications ADD COLUMN action_label text CHECK (action_label IS NULL OR length(action_label) <= 60);
CREATE UNIQUE INDEX ux_notif_dedupe ON notifications(coalesce(user_id, '00000000-0000-0000-0000-000000000000'::uuid),
  dedupe_key) WHERE dedupe_key IS NOT NULL;
CREATE INDEX ix_notif_user_unread ON notifications(user_id, created_at DESC) WHERE read_at IS NULL;
CREATE INDEX ix_notif_project ON notifications(project_id) WHERE project_id IS NOT NULL;

-- Quem é "a equipe envolvida" em um projeto: quem é membro da organização dona, mais quem é membro de organização
-- com relação ATIVA de participação naquele projeto (parceiro, financiador, patrocinador, prestador).
-- SECURITY DEFINER porque atravessa inquilinos de propósito, e por isso NÃO recebe parâmetro de quem chama:
-- devolve sempre o time do projeto, e quem usa decide o que fazer com isso.
CREATE FUNCTION project_team(p_project uuid)
RETURNS TABLE(user_id uuid, org_id uuid, relation text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
  SELECT m.user_id, m.org_id, 'owner'::text
    FROM memberships m JOIN projects p ON p.id = p_project AND p.org_id = m.org_id
   UNION
  SELECT m.user_id, m.org_id, r.kind
    FROM relationships r
    JOIN memberships m ON m.org_id = r.source_org_id
   WHERE r.target_project_id = p_project AND r.status = 'active'
     AND r.kind IN ('project_member','project_partner','project_sponsor','project_investor','investment',
                    'sponsorship','service','partnership','support','government_support')
   UNION
  SELECT m.user_id, m.org_id, 'funder'::text
    FROM applications a
    JOIN memberships m ON m.org_id = a.funder_org_id
   WHERE a.project_id = p_project AND a.status NOT IN ('withdrawn','rejected');
$$;
REVOKE EXECUTE ON FUNCTION project_team(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION project_team(uuid) TO impacto_app;

-- Alcance: uma notificação por PESSOA da equipe, com idempotência e respeitando a preferência de canal.
-- Devolve quantas pessoas foram efetivamente notificadas.
CREATE FUNCTION notify_team(p_project uuid, p_kind text, p_title text, p_body text, p_link text,
                            p_actor uuid DEFAULT NULL, p_priority text DEFAULT 'normal',
                            p_dedupe text DEFAULT NULL, p_ref_type text DEFAULT NULL, p_ref_id uuid DEFAULT NULL,
                            p_action_label text DEFAULT NULL)
RETURNS integer LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE n integer := 0; grp text;
BEGIN
  IF app_uid() IS NULL AND NOT app_system() THEN
    RAISE EXCEPTION 'notificação exige contexto autenticado' USING ERRCODE = '42501';
  END IF;
  grp := split_part(p_kind, '.', 1);
  WITH team AS (SELECT DISTINCT t.user_id, t.org_id FROM project_team(p_project) t)
  INSERT INTO notifications(org_id, user_id, kind, title, body, link, actor_user_id, priority, project_id,
                            ref_type, ref_id, dedupe_key, action_label)
  SELECT t.org_id, t.user_id, p_kind, left(p_title, 200), left(p_body, 2000), p_link, p_actor, p_priority,
         p_project, p_ref_type, p_ref_id,
         CASE WHEN p_dedupe IS NULL THEN NULL ELSE p_dedupe END, p_action_label
    FROM team t
   WHERE t.user_id IS DISTINCT FROM p_actor          -- quem fez a ação não é avisado da própria ação
     AND NOT EXISTS (SELECT 1 FROM notification_prefs np
                      WHERE np.user_id = t.user_id AND np.grp = grp AND NOT np.in_app)
  ON CONFLICT DO NOTHING;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n;
END $$;
REVOKE EXECUTE ON FUNCTION notify_team(uuid, text, text, text, text, uuid, text, text, text, uuid, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION notify_team(uuid, text, text, text, text, uuid, text, text, text, uuid, text) TO impacto_app;
COMMENT ON FUNCTION notify_team(uuid, text, text, text, text, uuid, text, text, text, uuid, text) IS
  'Avisa cada PESSOA da equipe do projeto (organização dona + organizações com relação ativa + financiadores).
   Idempotente por dedupe_key. Respeita notification_prefs. Não avisa quem praticou a ação.';

-- Alcance para as duas partes de uma proposta (sem projeto envolvido).
CREATE FUNCTION notify_org_members(p_org uuid, p_kind text, p_title text, p_body text, p_link text,
                                   p_actor uuid DEFAULT NULL, p_priority text DEFAULT 'normal',
                                   p_dedupe text DEFAULT NULL, p_ref_type text DEFAULT NULL,
                                   p_ref_id uuid DEFAULT NULL, p_min_role text DEFAULT 'viewer')
RETURNS integer LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE n integer := 0; grp text; ord text[] := ARRAY['viewer','member','analyst','manager','admin','owner'];
BEGIN
  IF app_uid() IS NULL AND NOT app_system() THEN
    RAISE EXCEPTION 'notificação exige contexto autenticado' USING ERRCODE = '42501';
  END IF;
  grp := split_part(p_kind, '.', 1);
  INSERT INTO notifications(org_id, user_id, kind, title, body, link, actor_user_id, priority, ref_type, ref_id,
                            dedupe_key)
  SELECT m.org_id, m.user_id, p_kind, left(p_title, 200), left(p_body, 2000), p_link, p_actor, p_priority,
         p_ref_type, p_ref_id, p_dedupe
    FROM memberships m
   WHERE m.org_id = p_org
     AND array_position(ord, m.role) >= array_position(ord, p_min_role)
     AND m.user_id IS DISTINCT FROM p_actor
     AND NOT EXISTS (SELECT 1 FROM notification_prefs np
                      WHERE np.user_id = m.user_id AND np.grp = grp AND NOT np.in_app)
  ON CONFLICT DO NOTHING;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n;
END $$;
REVOKE EXECUTE ON FUNCTION notify_org_members(uuid, text, text, text, text, uuid, text, text, text, uuid, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION notify_org_members(uuid, text, text, text, text, uuid, text, text, text, uuid, text) TO impacto_app;

-- Grupos de preferência: a pessoa precisa poder silenciar "propostas" sem silenciar "cobrança". Os seis grupos da
-- 0009 não cobrem a rede, então o CHECK é reescrito somando os sete grupos novos. Nenhuma linha existente é afetada
-- (os valores antigos continuam válidos) e a ausência de linha continua significando "quero receber".
ALTER TABLE notification_prefs DROP CONSTRAINT notification_prefs_grp_check;
ALTER TABLE notification_prefs ADD CONSTRAINT notification_prefs_grp_check CHECK (grp IN (
  'billing','content','events','support','partnerships','opportunities',
  'network','proposal','message','funding','report','project','document','account'));
COMMENT ON COLUMN notification_prefs.grp IS
  'Grupo de aviso. Sem linha = recebe. Os grupos da rede (network, proposal, message, funding, report, project, '
  'document, account) foram somados na 0016; silenciar um grupo não apaga o fato em domain_events.';

-- ================================================================================================ 5. MARKETPLACE
-- ACHADO E6: hoje a visibilidade do projeto é `visibility` + `status`, e o feed filtra por consulta. Um WHERE errado
-- expõe rascunho. O anúncio passa a ser uma ENTIDADE com estado de publicação próprio, e a consulta pública lê
-- `marketplace_listings`, não a tabela do domínio.
CREATE TABLE marketplace_listings (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  -- o que está sendo anunciado
  subject_type  text NOT NULL CHECK (subject_type IN ('project','opportunity','need','service','solution',
                                                      'partnership','sponsorship')),
  project_id    uuid REFERENCES projects(id) ON DELETE CASCADE,
  call_id       uuid REFERENCES calls(id) ON DELETE CASCADE,
  need_id       uuid REFERENCES project_needs(id) ON DELETE CASCADE,
  solution_id   uuid REFERENCES solutions(id) ON DELETE CASCADE,
  service_id    uuid REFERENCES professional_services(id) ON DELETE CASCADE,
  CONSTRAINT listing_one_subject CHECK ((project_id IS NOT NULL)::int + (call_id IS NOT NULL)::int
    + (need_id IS NOT NULL)::int + (solution_id IS NOT NULL)::int + (service_id IS NOT NULL)::int = 1),
  -- o que se busca com o anúncio
  seeking       text[] NOT NULL DEFAULT '{}'
                  CHECK (seeking <@ ARRAY['investment','sponsorship','partner','professional','volunteer',
                                          'mentorship','equipment','knowledge','quota']::text[]),
  headline      text NOT NULL CHECK (length(headline) BETWEEN 10 AND 200),
  summary       text CHECK (length(summary) <= 2000),
  -- faixa pedida, quando aplicável. NULO quando não há valor — a plataforma não inventa número.
  amount_target_cents bigint CHECK (amount_target_cents IS NULL OR amount_target_cents >= 0),
  currency      char(3) NOT NULL DEFAULT 'BRL' CHECK (currency ~ '^[A-Z]{3}$'),
  territory     text CHECK (territory IS NULL OR territory ~ '^(INT|[A-Z]{2}(-[A-Z]{2}(-[0-9]{7})?)?)$'),
  causes        text[] NOT NULL DEFAULT '{}',
  ods           smallint[] NOT NULL DEFAULT '{}',
  esg_tags      text[] NOT NULL DEFAULT '{}',
  stage         text CHECK (stage IS NULL OR stage IN ('idea','building','ready','seeking','executing','completed')),
  -- ESTADO DE PUBLICAÇÃO: é isto que decide o que aparece em público, não uma condição de consulta
  publication_state text NOT NULL DEFAULT 'draft'
                  CHECK (publication_state IN ('draft','review','approved','published','paused','expired','archived',
                                               'suspended')),
  published_at  timestamptz,
  published_by  uuid REFERENCES users(id) ON DELETE SET NULL,
  expires_at    timestamptz,
  suspended_reason text CHECK (length(suspended_reason) <= 500),
  views         integer NOT NULL DEFAULT 0 CHECK (views >= 0),
  created_by    uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  CHECK ((publication_state = 'published') = (published_at IS NOT NULL)),
  CHECK (publication_state <> 'suspended' OR coalesce(length(trim(suspended_reason)), 0) >= 3)
);
CREATE UNIQUE INDEX ux_listing_subject ON marketplace_listings(
  subject_type, coalesce(project_id, call_id, need_id, solution_id, service_id));
CREATE INDEX ix_listing_public ON marketplace_listings(publication_state, published_at DESC)
  WHERE publication_state = 'published';
CREATE INDEX ix_listing_org ON marketplace_listings(org_id, publication_state);
CREATE INDEX ix_listing_territory ON marketplace_listings(territory) WHERE publication_state = 'published';
COMMENT ON TABLE marketplace_listings IS
  'Anúncio do marketplace. A consulta pública lê SÓ publication_state = published: projeto privado não aparece por
   erro de WHERE porque a publicação é um estado da entidade, não uma condição de consulta.';

-- Publicar exige que o SUJEITO também esteja publicável. Projeto em rascunho não gera anúncio publicado.
CREATE FUNCTION listing_publish_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE ok boolean;
BEGIN
  IF NEW.publication_state <> 'published' THEN RETURN NEW; END IF;
  IF NEW.project_id IS NOT NULL THEN
    SELECT p.visibility = 'published' AND p.status NOT IN ('draft','diagnosing','structuring','archived','cancelled',
                                                           'rejected')
      INTO ok FROM projects p WHERE p.id = NEW.project_id;
    IF NOT coalesce(ok, false) THEN
      RAISE EXCEPTION 'O projeto precisa estar publicado antes de o anúncio ir ao ar' USING ERRCODE = '42501';
    END IF;
  END IF;
  IF NEW.solution_id IS NOT NULL THEN
    SELECT s.visibility = 'published' INTO ok FROM solutions s WHERE s.id = NEW.solution_id;
    IF NOT coalesce(ok, false) THEN
      RAISE EXCEPTION 'A solução precisa estar publicada antes de o anúncio ir ao ar' USING ERRCODE = '42501';
    END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_listing_publish BEFORE INSERT OR UPDATE OF publication_state ON marketplace_listings
  FOR EACH ROW EXECUTE FUNCTION listing_publish_guard();

-- ================================================================================================ 6. RELATÓRIO DE IMPACTO
CREATE TABLE impact_updates (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id    uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  period_start  date NOT NULL,
  period_end    date NOT NULL,
  CHECK (period_end >= period_start),
  summary       text NOT NULL CHECK (length(summary) BETWEEN 20 AND 8000),
  -- o que o período entregou, com os três níveis separados (produto ≠ resultado ≠ impacto)
  outputs       text CHECK (length(outputs) <= 4000),
  outcomes      text CHECK (length(outcomes) <= 4000),
  -- dizer o que o dado NÃO prova faz parte do relatório
  limitations   text CHECK (length(limitations) <= 2000),
  risks_note    text CHECK (length(risks_note) <= 2000),
  -- medições e marcos do período, apuradas pelo servidor ao submeter
  metrics       jsonb NOT NULL DEFAULT '{}'::jsonb,
  milestones    jsonb NOT NULL DEFAULT '[]'::jsonb,
  evidence_count integer NOT NULL DEFAULT 0 CHECK (evidence_count >= 0),
  document_id   uuid REFERENCES documents(id) ON DELETE SET NULL,
  status        text NOT NULL DEFAULT 'draft'
                  CHECK (status IN ('draft','submitted','under_review','changes_requested','accepted','published')),
  review_note   text CHECK (length(review_note) <= 2000),
  reviewed_by   uuid REFERENCES users(id) ON DELETE SET NULL,
  reviewed_by_org uuid REFERENCES organizations(id) ON DELETE SET NULL,
  reviewed_at   timestamptz,
  submitted_at  timestamptz,
  published_at  timestamptz,
  created_by    uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (project_id, period_start, period_end),
  -- quem revisa não é quem escreveu, e recusar exige motivo (mesmo princípio da montagem de documento)
  CHECK (reviewed_by IS NULL OR reviewed_by <> created_by),
  CHECK (status <> 'changes_requested' OR coalesce(length(trim(review_note)), 0) >= 3)
);
CREATE INDEX ix_impupd_project ON impact_updates(project_id, period_end DESC);
CREATE INDEX ix_impupd_org ON impact_updates(org_id, status);
COMMENT ON TABLE impact_updates IS
  'Prestação de contas periódica. metrics/milestones são apurados pelo SERVIDOR ao submeter, não digitados.';

-- ------------------------------------------------------------------------------------------------ máquina de estados
-- de anúncio e de relatório, como DADO (mesma escolha do projeto na 0013 e da proposta acima).
--
-- POR QUE NÃO `guard_columns` EM `publication_state` E `status`: a organização publica o ANÚNCIO DELA e envia o
-- RELATÓRIO DELA — isso é o produto, não privilégio de administração. O que ela não pode é carimbar quando publicou,
-- quem revisou, nem se suspender/dessuspender a si mesma. Então a coluna de estado fica livre, a transição é validada
-- por grafo, os carimbos são DERIVADOS pelo gatilho e a suspensão exige contexto privilegiado.
CREATE TABLE network_status_graph (
  entity        text NOT NULL CHECK (entity IN ('listing','impact_update')),
  from_status   text NOT NULL,
  to_status     text NOT NULL,
  actor         text NOT NULL CHECK (actor IN ('owner','reviewer','either','admin','system')),
  requires_note boolean NOT NULL DEFAULT false,
  note          text,
  PRIMARY KEY (entity, from_status, to_status)
);
INSERT INTO network_status_graph(entity, from_status, to_status, actor, requires_note, note) VALUES
  -- anúncio: a organização leva do rascunho ao ar e pode pausar/arquivar; só a administração suspende e libera
  ('listing','draft','review','owner', false, 'enviado para conferência interna da própria organização'),
  ('listing','draft','published','owner', false, 'publicação direta quando o sujeito já está publicado'),
  ('listing','draft','archived','owner', false, NULL),
  ('listing','review','approved','owner', false, NULL),
  ('listing','review','draft','owner', false, NULL),
  ('listing','approved','published','owner', false, NULL),
  ('listing','approved','draft','owner', false, NULL),
  ('listing','published','paused','owner', false, NULL),
  ('listing','published','archived','owner', false, NULL),
  ('listing','published','expired','system', false, 'prazo do anúncio venceu'),
  ('listing','published','suspended','admin', true, 'medida de moderação; exige motivo'),
  ('listing','paused','published','owner', false, NULL),
  ('listing','paused','archived','owner', false, NULL),
  ('listing','expired','draft','owner', false, 'reabre para atualizar e republicar'),
  ('listing','expired','archived','owner', false, NULL),
  ('listing','suspended','draft','admin', true, 'liberado pela administração para correção'),
  ('listing','suspended','archived','admin', true, NULL),
  -- relatório de impacto: quem executa envia, quem apoia revisa, e publicar é decisão de quem executa
  ('impact_update','draft','submitted','owner', false, NULL),
  ('impact_update','submitted','under_review','reviewer', false, NULL),
  ('impact_update','submitted','changes_requested','reviewer', true, NULL),
  ('impact_update','submitted','accepted','reviewer', false, NULL),
  ('impact_update','submitted','draft','owner', false, 'retirado para ajuste antes da análise'),
  ('impact_update','under_review','accepted','reviewer', false, NULL),
  ('impact_update','under_review','changes_requested','reviewer', true, NULL),
  ('impact_update','changes_requested','submitted','owner', false, 'reenviado após ajuste'),
  ('impact_update','accepted','published','owner', false, 'resultado aceito passa a aparecer no projeto');
ALTER TABLE network_status_graph ENABLE ROW LEVEL SECURITY;
CREATE POLICY read ON network_status_graph FOR SELECT USING (app_authenticated());
GRANT SELECT ON network_status_graph TO impacto_app;
COMMENT ON TABLE network_status_graph IS
  'Transições de anúncio e de relatório de impacto. A máquina é dado: a interface desenha os botões a partir daqui e
   o gatilho recusa transição fora do grafo mesmo em SQL direto.';

CREATE FUNCTION listing_state_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE g record;
BEGIN
  IF NEW.publication_state = OLD.publication_state THEN RETURN NEW; END IF;
  SELECT * INTO g FROM network_status_graph
   WHERE entity = 'listing' AND from_status = OLD.publication_state AND to_status = NEW.publication_state;
  IF g IS NULL THEN
    RAISE EXCEPTION 'Anúncio: transição % → % não é permitida', OLD.publication_state, NEW.publication_state
      USING ERRCODE = '42501';
  END IF;
  IF g.actor IN ('admin','system') AND current_user::text = 'impacto_app' AND NOT app_priv() THEN
    RAISE EXCEPTION 'Anúncio: transição % → % é da administração da plataforma',
      OLD.publication_state, NEW.publication_state USING ERRCODE = '42501';
  END IF;
  -- carimbos derivados: a organização não escolhe a data em que publicou nem quem publicou
  IF NEW.publication_state = 'published' THEN
    NEW.published_at := now();
    NEW.published_by := coalesce(app_uid(), NEW.published_by);
  ELSE
    NEW.published_at := NULL;      -- o CHECK exige published_at NULO fora de "published"
  END IF;
  IF NEW.publication_state <> 'suspended' AND OLD.publication_state = 'suspended' THEN
    NEW.suspended_reason := OLD.suspended_reason;   -- o motivo da suspensão não se apaga ao liberar
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_listing_state BEFORE UPDATE OF publication_state ON marketplace_listings FOR EACH ROW
  EXECUTE FUNCTION listing_state_guard();

CREATE FUNCTION impact_update_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE g record;
BEGIN
  IF NEW.status = OLD.status THEN RETURN NEW; END IF;
  SELECT * INTO g FROM network_status_graph
   WHERE entity = 'impact_update' AND from_status = OLD.status AND to_status = NEW.status;
  IF g IS NULL THEN
    RAISE EXCEPTION 'Relatório de impacto: transição % → % não é permitida', OLD.status, NEW.status
      USING ERRCODE = '42501';
  END IF;
  -- carimbos e autoria da revisão são DERIVADOS. É isto que faz "quem revisou" ser um fato e não um campo.
  IF NEW.status = 'submitted' THEN NEW.submitted_at := now(); END IF;
  IF NEW.status IN ('under_review','changes_requested','accepted') THEN
    NEW.reviewed_at := now();
    NEW.reviewed_by := coalesce(app_uid(), NEW.reviewed_by);
    NEW.reviewed_by_org := coalesce(app_org(), NEW.reviewed_by_org);
    -- quatro olhos: o CHECK da tabela recusa reviewed_by = created_by, inclusive em SQL direto
  END IF;
  IF NEW.status = 'published' THEN NEW.published_at := now(); END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_impupd_state BEFORE UPDATE OF status ON impact_updates FOR EACH ROW
  EXECUTE FUNCTION impact_update_guard();

-- ================================================================================================ 7. PERSONA E CAPACIDADE
-- Hoje a experiência é decidida por (tipo de organização × papel × entitlement). Isso cobre OSC/empresa/governo/
-- profissional, mas não representa DOADOR, MENTOR, VOLUNTÁRIO, PESQUISADOR — que são formas de ATUAR, não tipos
-- de organização. Persona é declarada e pode ser mais de uma.
CREATE TABLE personas (
  key           text PRIMARY KEY CHECK (key ~ '^[a-z_]{3,30}$'),
  label_pt      text NOT NULL,
  label_en      text,
  -- a quais tipos de organização esta persona se aplica
  org_kinds     text[] NOT NULL DEFAULT '{}',
  -- o que esta persona procura na plataforma (orienta o workspace, não concede permissão)
  primary_job   text NOT NULL CHECK (length(primary_job) BETWEEN 5 AND 200),
  active        boolean NOT NULL DEFAULT true,
  position      smallint NOT NULL DEFAULT 100
);
INSERT INTO personas(key, label_pt, label_en, org_kinds, primary_job, position) VALUES
  ('organization','Organização executora','Implementing organization','{osc}',
   'Estruturar projeto, captar apoio, executar e prestar contas', 10),
  ('investor','Investidor social / financiador','Social investor','{company,individual}',
   'Encontrar projeto compatível, apoiar e acompanhar resultado', 20),
  ('professional','Profissional','Professional','{provider,individual}',
   'Encontrar oportunidade de atuação, propor, entregar e comprovar', 30),
  ('government','Poder público','Government','{government}',
   'Mapear território, publicar política, acompanhar e avaliar impacto', 40),
  ('donor','Doador','Donor','{individual,company}',
   'Apoiar causa com recurso ou cota, com prestação de contas', 50),
  ('mentor','Mentor','Mentor','{provider,individual,company}',
   'Oferecer mentoria a organizações e projetos', 60),
  ('volunteer','Voluntário','Volunteer','{individual,provider}',
   'Oferecer tempo e competência sem remuneração', 70),
  ('researcher','Pesquisador','Researcher','{provider,individual,government}',
   'Estudar soluções, resultados e evidências de impacto', 80),
  ('educator','Educador','Educator','{provider,individual,osc}',
   'Formar pessoas e organizações', 90),
  ('admin','Administração da plataforma','Platform administration','{platform}',
   'Operar, moderar e auditar a plataforma', 999);

CREATE TABLE org_personas (
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  persona       text NOT NULL REFERENCES personas(key) ON DELETE RESTRICT,
  is_primary    boolean NOT NULL DEFAULT false,
  declared_by   uuid REFERENCES users(id) ON DELETE SET NULL,
  declared_at   timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (org_id, persona)
);
CREATE UNIQUE INDEX ux_org_primary_persona ON org_personas(org_id) WHERE is_primary;
COMMENT ON TABLE org_personas IS
  'Persona é DECLARADA e orienta o workspace. Não concede permissão: isso continua sendo papel + entitlement.';

-- ================================================================================================ 8. TAXONOMIA VERSIONADA
-- ACHADO L15: rótulos espalhados entre frontend, serviços e CHECKs. Aqui fica o registro central, versionado, e com
-- a política de uso de cada conjunto — necessária para o cuidado com grupo vulnerável (§55 do prompt).
CREATE TABLE taxonomies (
  key           text PRIMARY KEY CHECK (key ~ '^[a-z_.]{3,60}$'),
  label_pt      text NOT NULL,
  version       text NOT NULL DEFAULT '1.0',
  -- para que serve: orienta quem usa e impede uso indevido
  purpose       text NOT NULL CHECK (length(purpose) BETWEEN 10 AND 500),
  -- sensibilidade do conjunto. 'beneficiary_group' NÃO pode ser usado para filtrar PESSOAS.
  sensitivity   text NOT NULL DEFAULT 'public'
                  CHECK (sensitivity IN ('public','internal','beneficiary_group','sensitive')),
  usage_policy  text NOT NULL CHECK (length(usage_policy) BETWEEN 10 AND 1000),
  source_name   text,
  source_url    text CHECK (source_url IS NULL OR source_url ~ '^https?://'),
  source_date   date,
  active        boolean NOT NULL DEFAULT true,
  updated_at    timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE taxonomy_terms (
  taxonomy      text NOT NULL REFERENCES taxonomies(key) ON DELETE CASCADE,
  code          text NOT NULL CHECK (code ~ '^[a-z0-9_]{2,60}$'),
  label_pt      text NOT NULL,
  label_en      text,
  description   text CHECK (length(description) <= 500),
  position      smallint NOT NULL DEFAULT 100,
  active        boolean NOT NULL DEFAULT true,
  PRIMARY KEY (taxonomy, code)
);
CREATE INDEX ix_taxterm_active ON taxonomy_terms(taxonomy, position) WHERE active;

INSERT INTO taxonomies(key, label_pt, purpose, sensitivity, usage_policy, source_name) VALUES
  ('relationship_kind','Tipos de relação','Classificar a relação entre partes da rede','public',
   'Uso livre na interface e na API.','Plataforma Impacto'),
  ('proposal_kind','Tipos de proposta','Classificar o que está sendo proposto','public',
   'Uso livre na interface e na API.','Plataforma Impacto'),
  ('support_mode','Modalidades de apoio','Dizer que tipo de apoio está em jogo (não só dinheiro)','public',
   'Uso livre.','Plataforma Impacto'),
  ('listing_seeking','O que o anúncio busca','Orientar o marketplace','public','Uso livre.','Plataforma Impacto'),
  ('beneficiary_group','Públicos beneficiários do projeto','Descrever QUEM O PROJETO ATENDE',
   'beneficiary_group',
   'ATRIBUTO DO PROJETO, NUNCA DA PESSOA. É proibido usar este conjunto para filtrar, segmentar ou inferir '
   'característica de usuária ou usuário da plataforma. "Este projeto atende mulheres em situação de '
   'vulnerabilidade" é atributo do projeto; "esta pessoa é mulher e pertence a grupo vulnerável" é dado pessoal '
   'sensível e não é coletado.','Plataforma Impacto'),
  ('enforcement_measure','Medidas de moderação','Registrar a medida aplicada e o motivo','internal',
   'Só a administração aplica. Toda medida exige motivo, regra e responsável.','Plataforma Impacto');

INSERT INTO taxonomy_terms(taxonomy, code, label_pt, position) VALUES
  ('support_mode','financial','Recurso financeiro',10),
  ('support_mode','service','Serviço profissional',20),
  ('support_mode','equipment','Equipamento ou material',30),
  ('support_mode','knowledge','Conhecimento e formação',40),
  ('support_mode','volunteer','Trabalho voluntário',50),
  ('support_mode','sponsorship','Patrocínio',60),
  ('support_mode','mentorship','Mentoria',70),
  ('support_mode','other','Outro',99),
  ('listing_seeking','investment','Busca investimento',10),
  ('listing_seeking','sponsorship','Busca patrocínio',20),
  ('listing_seeking','partner','Busca parceiro',30),
  ('listing_seeking','professional','Busca profissional',40),
  ('listing_seeking','volunteer','Busca voluntário',50),
  ('listing_seeking','mentorship','Busca mentoria',60),
  ('listing_seeking','equipment','Busca equipamento',70),
  ('listing_seeking','knowledge','Busca conhecimento',80),
  ('listing_seeking','quota','Busca apoiadores por cota',90),
  ('beneficiary_group','children','Crianças',10),
  ('beneficiary_group','adolescents','Adolescentes',20),
  ('beneficiary_group','youth','Juventude',30),
  ('beneficiary_group','elderly','Pessoas idosas',40),
  ('beneficiary_group','women','Mulheres',50),
  ('beneficiary_group','pwd','Pessoas com deficiência',60),
  ('beneficiary_group','indigenous','Povos indígenas',70),
  ('beneficiary_group','quilombola','Comunidades quilombolas',80),
  ('beneficiary_group','homeless','População em situação de rua',90),
  ('beneficiary_group','migrants','Migrantes e refugiados',100),
  ('beneficiary_group','rural','População rural',110),
  ('beneficiary_group','families','Famílias em vulnerabilidade',120),
  ('beneficiary_group','students','Estudantes',130),
  ('beneficiary_group','workers','Trabalhadores',140),
  ('beneficiary_group','caregivers','Pessoas cuidadoras',150);

-- ================================================================================================ 9. PERFIL PÚBLICO
-- @identificador único e página pública que lê SÓ uma projeção curada — o mesmo princípio de
-- `verifiable_records.public_fields`: a página pública nunca consulta tabela privada.
CREATE TABLE public_profiles (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  -- de quem é o perfil: organização OU pessoa
  org_id        uuid REFERENCES organizations(id) ON DELETE CASCADE,
  user_id       uuid REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT profile_one_owner CHECK ((org_id IS NOT NULL)::int + (user_id IS NOT NULL)::int = 1),
  handle        citext NOT NULL CHECK (handle ~ '^[a-z0-9](?:[a-z0-9_.-]{1,28}[a-z0-9])$'),
  display_name  text NOT NULL CHECK (length(display_name) BETWEEN 2 AND 120),
  headline      text CHECK (length(headline) <= 160),
  bio           text CHECK (length(bio) <= 4000),
  -- a projeção PÚBLICA, montada pelo servidor. É isto que a página pública lê.
  public_fields jsonb NOT NULL DEFAULT '{}'::jsonb,
  -- controle granular por campo: o que entra na projeção
  show_territory boolean NOT NULL DEFAULT true,
  show_projects  boolean NOT NULL DEFAULT true,
  show_credentials boolean NOT NULL DEFAULT true,
  show_organizations boolean NOT NULL DEFAULT true,
  show_impact_history boolean NOT NULL DEFAULT true,
  show_contact  boolean NOT NULL DEFAULT false,     -- contato é privado por padrão
  links         jsonb NOT NULL DEFAULT '[]'::jsonb, -- [{label, url}] só http(s)
  visibility    text NOT NULL DEFAULT 'public' CHECK (visibility IN ('public','network','private')),
  -- perfil de conta suspensa não é servido
  suspended     boolean NOT NULL DEFAULT false,
  verified_badge text CHECK (verified_badge IS NULL OR verified_badge IN ('identity','professional','organization')),
  views         integer NOT NULL DEFAULT 0 CHECK (views >= 0),
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX ux_profile_handle ON public_profiles(handle);
CREATE UNIQUE INDEX ux_profile_org ON public_profiles(org_id) WHERE org_id IS NOT NULL;
CREATE UNIQUE INDEX ux_profile_user ON public_profiles(user_id) WHERE user_id IS NOT NULL;
COMMENT ON COLUMN public_profiles.public_fields IS
  'Projeção curada montada pelo servidor. A rota pública lê SÓ esta coluna — nunca tabela privada.';

-- Histórico de @identificador: trocar é permitido, apagar o rastro não. Impede sequestro de identidade por troca.
CREATE TABLE handle_history (
  id            bigserial PRIMARY KEY,
  profile_id    uuid NOT NULL REFERENCES public_profiles(id) ON DELETE CASCADE,
  handle        citext NOT NULL,
  changed_by    uuid REFERENCES users(id) ON DELETE SET NULL,
  at            timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_handlehist_handle ON handle_history(handle);

-- Identificador reservado: evita que alguém registre @admin, @impacto, @suporte e se passe pela plataforma.
CREATE TABLE reserved_handles (
  handle        citext PRIMARY KEY,
  reason        text NOT NULL
);
INSERT INTO reserved_handles(handle, reason) VALUES
  ('admin','identidade da plataforma'), ('administrador','identidade da plataforma'),
  ('impacto','marca da plataforma'), ('impactohub','marca da plataforma'), ('plataforma','marca da plataforma'),
  ('suporte','canal oficial'), ('support','canal oficial'), ('ajuda','canal oficial'),
  ('seguranca','canal oficial'), ('security','canal oficial'), ('contato','canal oficial'),
  ('oficial','sugere oficialidade'), ('official','sugere oficialidade'), ('verificado','sugere verificação'),
  ('verified','sugere verificação'), ('equipe','sugere equipe da plataforma'), ('team','sugere equipe da plataforma'),
  ('api','rota reservada'), ('www','rota reservada'), ('app','rota reservada'), ('verificar','rota reservada'),
  ('legal','rota reservada'), ('sobre','rota reservada'), ('null','valor reservado'), ('undefined','valor reservado');

CREATE FUNCTION handle_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM reserved_handles h WHERE h.handle = NEW.handle) THEN
    RAISE EXCEPTION 'O identificador "%" é reservado', NEW.handle USING ERRCODE = '23514';
  END IF;
  IF TG_OP = 'UPDATE' AND NEW.handle <> OLD.handle THEN
    INSERT INTO handle_history(profile_id, handle, changed_by) VALUES (OLD.id, OLD.handle, app_uid());
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_handle_guard BEFORE INSERT OR UPDATE OF handle ON public_profiles FOR EACH ROW
  EXECUTE FUNCTION handle_guard();

-- Experiência profissional: declarada ≠ confirmada. A organização confirma; ninguém confirma a si mesmo.
CREATE TABLE professional_experiences (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  -- organização onde atuou (quando está na plataforma) ou nome livre (quando não está)
  org_id        uuid REFERENCES organizations(id) ON DELETE SET NULL,
  org_name      text CHECK (length(org_name) <= 200),
  CHECK (org_id IS NOT NULL OR coalesce(length(trim(org_name)), 0) >= 2),
  project_id    uuid REFERENCES projects(id) ON DELETE SET NULL,
  role          text NOT NULL CHECK (length(role) BETWEEN 2 AND 120),
  description   text CHECK (length(description) <= 2000),
  started_on    date,
  ended_on      date,
  CHECK (ended_on IS NULL OR started_on IS NULL OR ended_on >= started_on),
  -- estado da confirmação. 'declared' é o padrão e a interface tem de dizer isso.
  state         text NOT NULL DEFAULT 'declared'
                  CHECK (state IN ('declared','pending_confirmation','confirmed','disputed','revoked')),
  confirmed_by  uuid REFERENCES users(id) ON DELETE SET NULL,
  confirmed_at  timestamptz,
  dispute_note  text CHECK (length(dispute_note) <= 1000),
  evidence_document_id uuid REFERENCES documents(id) ON DELETE SET NULL,
  visibility    text NOT NULL DEFAULT 'public' CHECK (visibility IN ('public','network','private')),
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  -- ninguém confirma a própria experiência
  CHECK (confirmed_by IS NULL OR confirmed_by <> user_id),
  CHECK (state <> 'confirmed' OR (confirmed_by IS NOT NULL AND confirmed_at IS NOT NULL)),
  CHECK (state <> 'disputed' OR coalesce(length(trim(dispute_note)), 0) >= 3)
);
CREATE INDEX ix_profexp_user ON professional_experiences(user_id, state);
CREATE INDEX ix_profexp_org ON professional_experiences(org_id) WHERE org_id IS NOT NULL;
COMMENT ON TABLE professional_experiences IS
  'Experiência declarada pela pessoa. "confirmed" só com confirmação de OUTRA pessoa da organização citada.';

-- Confirmar exige ser da organização citada, e não ser a própria pessoa (ADR: declarado ≠ verificado).
CREATE FUNCTION experience_confirm_guard() RETURNS trigger LANGUAGE plpgsql
SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
  IF NEW.state = 'confirmed' AND (OLD.state IS DISTINCT FROM 'confirmed') THEN
    IF NEW.org_id IS NULL THEN
      RAISE EXCEPTION 'Só experiência vinculada a organização da plataforma pode ser confirmada'
        USING ERRCODE = '42501';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM memberships m WHERE m.org_id = NEW.org_id AND m.user_id = NEW.confirmed_by
                     AND m.role IN ('manager','admin','owner')) THEN
      RAISE EXCEPTION 'Quem confirma precisa ser gestor, administrador ou proprietário da organização citada'
        USING ERRCODE = '42501';
    END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_exp_confirm BEFORE UPDATE OF state ON professional_experiences FOR EACH ROW
  EXECUTE FUNCTION experience_confirm_guard();

-- ================================================================================================ 10. MODERAÇÃO
-- `reports` já existe e resolve denúncia. Falta a MEDIDA aplicada, proporcional, com motivo, regra e revisão.
ALTER TABLE reports ADD COLUMN category text CHECK (category IS NULL OR category IN ('fraud','abuse','harassment',
  'impersonation','spam','non_payment','unethical_conduct','conflict_of_interest','false_information',
  'data_misuse','illegal_content','other'));
ALTER TABLE reports ADD COLUMN priority text NOT NULL DEFAULT 'normal'
  CHECK (priority IN ('low','normal','high','urgent'));
ALTER TABLE reports ADD COLUMN evidence_document_id uuid REFERENCES documents(id) ON DELETE SET NULL;
ALTER TABLE reports ADD COLUMN reporter_anonymous boolean NOT NULL DEFAULT true;
COMMENT ON COLUMN reports.reporter_anonymous IS
  'A identidade de quem denuncia NÃO é revelada ao denunciado. A administração vê; o alvo não.';

CREATE TABLE enforcement_actions (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  -- alvo da medida
  target_org_id uuid REFERENCES organizations(id) ON DELETE CASCADE,
  target_user_id uuid REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT enf_one_target CHECK ((target_org_id IS NOT NULL)::int + (target_user_id IS NOT NULL)::int = 1),
  report_id     uuid REFERENCES reports(id) ON DELETE SET NULL,
  -- escada proporcional: nada de banimento como primeira medida
  measure       text NOT NULL CHECK (measure IN ('guidance','warning','formal_notice','partial_restriction',
                  'temporary_suspension','precautionary_freeze','unlinking','cancellation','ban','referral')),
  severity      smallint NOT NULL CHECK (severity BETWEEN 1 AND 10),
  -- a regra aplicada e o motivo: medida sem regra é arbítrio
  rule_ref      text NOT NULL CHECK (length(rule_ref) BETWEEN 3 AND 200),
  reason        text NOT NULL CHECK (length(reason) BETWEEN 10 AND 4000),
  evidence_note text CHECK (length(evidence_note) <= 2000),
  starts_at     timestamptz NOT NULL DEFAULT now(),
  ends_at       timestamptz,
  status        text NOT NULL DEFAULT 'active'
                  CHECK (status IN ('active','expired','lifted','under_appeal','upheld','overturned')),
  -- direito de contestação
  appeal_note   text CHECK (length(appeal_note) <= 4000),
  appeal_at     timestamptz,
  appeal_decided_by uuid REFERENCES users(id) ON DELETE SET NULL,
  appeal_decision text CHECK (appeal_decision IS NULL OR length(appeal_decision) <= 2000),
  decided_by    uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  -- medida temporária precisa de prazo
  CHECK (measure NOT IN ('temporary_suspension','partial_restriction','precautionary_freeze') OR ends_at IS NOT NULL),
  -- quem decide a contestação não é quem aplicou a medida
  CHECK (appeal_decided_by IS NULL OR appeal_decided_by <> decided_by)
);
CREATE INDEX ix_enf_target_org ON enforcement_actions(target_org_id, status) WHERE target_org_id IS NOT NULL;
CREATE INDEX ix_enf_target_user ON enforcement_actions(target_user_id, status) WHERE target_user_id IS NOT NULL;
CREATE INDEX ix_enf_report ON enforcement_actions(report_id) WHERE report_id IS NOT NULL;
COMMENT ON TABLE enforcement_actions IS
  'Medida de moderação proporcional. Exige regra, motivo e responsável; quem julga a contestação não é quem aplicou.
   A plataforma NÃO aplica medida automática irreversível por heurística.';

-- ================================================================================================ 11. TERRITÓRIO
-- Hoje território é a string BR-UF-IBGE. Governo precisa de necessidade e lacuna POR território.
CREATE TABLE territory_needs (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  territory     text NOT NULL CHECK (territory ~ '^(INT|[A-Z]{2}(-[A-Z]{2}(-[0-9]{7})?)?)$'),
  -- quem declarou a necessidade do território (órgão público ou organização que atua nele)
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  title         text NOT NULL CHECK (length(title) BETWEEN 5 AND 200),
  description   text CHECK (length(description) <= 4000),
  cause         text CHECK (cause ~ '^[a-z0-9_]{2,60}$'),
  ods           smallint[] NOT NULL DEFAULT '{}',
  beneficiary_groups text[] NOT NULL DEFAULT '{}',
  -- estimativa de alcance, com a FONTE declarada (sem fonte não é dado, é palpite)
  people_estimate integer CHECK (people_estimate IS NULL OR people_estimate >= 0),
  source_name   text CHECK (length(source_name) <= 200),
  source_url    text CHECK (source_url IS NULL OR source_url ~ '^https?://'),
  source_date   date,
  CHECK (people_estimate IS NULL OR source_name IS NOT NULL),
  priority      text NOT NULL DEFAULT 'medium' CHECK (priority IN ('low','medium','high','critical')),
  status        text NOT NULL DEFAULT 'open' CHECK (status IN ('open','partially_served','served','archived')),
  visibility    text NOT NULL DEFAULT 'public' CHECK (visibility IN ('public','network','organization')),
  created_by    uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_terrneed_territory ON territory_needs(territory, status);
CREATE INDEX ix_terrneed_org ON territory_needs(org_id);
COMMENT ON COLUMN territory_needs.people_estimate IS
  'Estimativa só é aceita com fonte declarada (CHECK). A plataforma não inventa número de população.';

-- ================================================================================================ 12. INVESTIMENTO
-- ADR-022/031 preservado: a plataforma REGISTRA e CONFERE, não custodia nem processa aporte. `commitments` já faz
-- isso para projeto com candidatura. Falta a etapa ANTERIOR — a intenção — e ela não pode ser confundida com
-- dinheiro. Por isso tabela separada, com o caminho explícito até o compromisso.
CREATE TABLE investment_intents (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  investor_org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  project_id    uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  proposal_id   uuid REFERENCES proposals(id) ON DELETE SET NULL,
  -- valor PRETENDIDO. Não é compromisso, não é pagamento, não é dinheiro recebido.
  amount_cents  bigint CHECK (amount_cents IS NULL OR amount_cents BETWEEN 0 AND 1000000000000),
  currency      char(3) NOT NULL DEFAULT 'BRL' CHECK (currency ~ '^[A-Z]{3}$'),
  support_mode  text NOT NULL DEFAULT 'financial'
                  CHECK (support_mode IN ('financial','service','equipment','knowledge','volunteer','sponsorship',
                                          'mentorship','other')),
  note          text CHECK (length(note) <= 2000),
  status        text NOT NULL DEFAULT 'interest'
                  CHECK (status IN ('interest','intent','in_negotiation','committed','declined','withdrawn',
                                    'expired')),
  -- quando vira compromisso, aponta para o registro que JÁ EXISTE no domínio financeiro
  commitment_id uuid REFERENCES commitments(id) ON DELETE SET NULL,
  CHECK ((status = 'committed') = (commitment_id IS NOT NULL)),
  visibility    text NOT NULL DEFAULT 'participants'
                  CHECK (visibility IN ('private','participants','network','public')),
  created_by    uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (investor_org_id, project_id)
);
CREATE INDEX ix_intent_project ON investment_intents(project_id, status);
CREATE INDEX ix_intent_investor ON investment_intents(investor_org_id, status);
COMMENT ON TABLE investment_intents IS
  'INTENÇÃO de apoio. amount_cents é valor pretendido. "committed" só existe apontando para commitments — e nem
   compromisso é dinheiro recebido: isso é confirmado em disbursements/payment_records (ADR-022).';

-- ================================================================================================ 13. RECOMENDAÇÃO
-- "Match" responde "há compatibilidade". "Recomendação" responde "considerando compatibilidade + contexto +
-- estágio, esta é a ação recomendada". São coisas diferentes e passam a ser tabelas diferentes.
CREATE TABLE recommendations (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id       uuid REFERENCES users(id) ON DELETE CASCADE,
  -- o que se recomenda FAZER
  action        text NOT NULL CHECK (action IN ('complete_diagnosis','complete_project','add_indicator',
                  'add_milestone','upload_document','publish_project','create_listing','send_proposal',
                  'review_proposal','find_professional','find_investor','apply_to_call','submit_impact_update',
                  'resolve_risk','renew_document','confirm_experience','measure_indicator','review_match')),
  -- sobre o quê
  subject_type  text NOT NULL CHECK (subject_type IN ('project','diagnosis','proposal','organization','call',
                                                      'document','listing','relationship','indicator')),
  subject_id    uuid,
  title         text NOT NULL CHECK (length(title) BETWEEN 5 AND 200),
  rationale     text NOT NULL CHECK (length(rationale) BETWEEN 10 AND 1000),
  -- a recomendação herda a confiança da evidência que a sustenta, e diz qual é
  confidence    numeric(5,2) CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 100),
  confidence_band text CHECK (confidence_band IS NULL OR confidence_band IN ('high','medium','low',
                                                                             'insufficient_data')),
  evidence      jsonb NOT NULL DEFAULT '{}'::jsonb,
  match_run_id  uuid REFERENCES match_runs(id) ON DELETE SET NULL,
  diagnosis_version_id uuid REFERENCES diagnosis_versions(id) ON DELETE SET NULL,
  priority      smallint NOT NULL DEFAULT 50 CHECK (priority BETWEEN 1 AND 100),
  engine_version text NOT NULL,
  status        text NOT NULL DEFAULT 'open'
                  CHECK (status IN ('open','done','dismissed','expired','superseded')),
  dismissed_reason text CHECK (length(dismissed_reason) <= 500),
  expires_at    timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  -- uma recomendação aberta por (organização, ação, sujeito)
  CHECK (status <> 'dismissed' OR coalesce(length(trim(dismissed_reason)), 0) >= 3)
);
CREATE UNIQUE INDEX ux_rec_open ON recommendations(org_id, action,
  coalesce(subject_id, '00000000-0000-0000-0000-000000000000'::uuid)) WHERE status = 'open';
CREATE INDEX ix_rec_org ON recommendations(org_id, status, priority DESC);
COMMENT ON TABLE recommendations IS
  'Recomendação ≠ match ≠ aprovação. É ação sugerida, com razão, confiança e evidência. A decisão é humana.';

-- ================================================================================================ 14. PRONTIDÃO
-- O diagnóstico já calcula 8 dimensões. Falta a agregação POR FINALIDADE: "estou pronto para captar?" é diferente
-- de "estou pronto para executar?". Snapshot, porque a resposta muda com o tempo e precisa ser comparável.
CREATE TABLE readiness_snapshots (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  project_id    uuid REFERENCES projects(id) ON DELETE CASCADE,
  -- as seis prontidões do prompt §43
  document_readiness numeric(5,2) NOT NULL CHECK (document_readiness BETWEEN 0 AND 100),
  project_readiness numeric(5,2) NOT NULL CHECK (project_readiness BETWEEN 0 AND 100),
  funding_readiness numeric(5,2) NOT NULL CHECK (funding_readiness BETWEEN 0 AND 100),
  governance_readiness numeric(5,2) NOT NULL CHECK (governance_readiness BETWEEN 0 AND 100),
  execution_readiness numeric(5,2) NOT NULL CHECK (execution_readiness BETWEEN 0 AND 100),
  evidence_readiness numeric(5,2) NOT NULL CHECK (evidence_readiness BETWEEN 0 AND 100),
  overall       numeric(5,2) NOT NULL CHECK (overall BETWEEN 0 AND 100),
  -- POR QUÊ cada número é esse. Percentual sem explicação é número mágico.
  detail        jsonb NOT NULL DEFAULT '{}'::jsonb,
  blockers      jsonb NOT NULL DEFAULT '[]'::jsonb,
  engine_version text NOT NULL,
  computed_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_readiness_org ON readiness_snapshots(org_id, computed_at DESC);
CREATE INDEX ix_readiness_project ON readiness_snapshots(project_id, computed_at DESC)
  WHERE project_id IS NOT NULL;
COMMENT ON TABLE readiness_snapshots IS
  'Prontidão por finalidade, com detail explicando CADA número. "Captação 72%" sem explicação não é informação.';

-- ================================================================================================ 15. EVENTO DE DOMÍNIO
-- ACHADO L4: hoje cada chamador decide se notifica, e três módulos fazem isso de três maneiras. O evento passa a
-- ser o registro único do fato; notificação, trilha e recomendação LEEM dele.
-- Não substitui transação: o evento é gravado NA MESMA transação do fato.
CREATE TABLE domain_events (
  id            bigserial PRIMARY KEY,
  event         text NOT NULL CHECK (event ~ '^[A-Za-z]+\.[A-Za-z_]+$'),
  org_id        uuid REFERENCES organizations(id) ON DELETE CASCADE,
  actor_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  project_id    uuid REFERENCES projects(id) ON DELETE CASCADE,
  subject_type  text CHECK (subject_type IS NULL OR length(subject_type) <= 40),
  subject_id    uuid,
  payload       jsonb NOT NULL DEFAULT '{}'::jsonb,
  -- quantas pessoas foram avisadas por causa deste evento (0 = ninguém, e isso é visível)
  notified      integer NOT NULL DEFAULT 0 CHECK (notified >= 0),
  at            timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_devent_project ON domain_events(project_id, id DESC) WHERE project_id IS NOT NULL;
CREATE INDEX ix_devent_org ON domain_events(org_id, id DESC);
CREATE INDEX ix_devent_event ON domain_events(event, id DESC);
COMMENT ON TABLE domain_events IS
  'Fato do domínio, gravado na MESMA transação do fato. Fonte de notificação, trilha e recomendação.';

-- ================================================================================================ 16. TRILHA
-- Tipos de entrada novos da camada de rede, acrescentados ao CHECK existente (não há segunda tabela de histórico).
ALTER TABLE ledger_entries DROP CONSTRAINT ledger_entries_entry_type_check;
ALTER TABLE ledger_entries ADD CONSTRAINT ledger_entries_entry_type_check CHECK (entry_type IN (
  'need_published','budget_defined','milestone_defined','interest_registered','application_submitted',
  'application_approved','funding_committed','disbursement_reported','disbursement_confirmed','expense_recorded',
  'evidence_submitted','evidence_reviewed','result_reported','report_submitted','feedback_given',
  'professional_signature','project_completed','refund_completed','payment_disputed','indicator_validated',
  'procurement_decided',
  -- v0.15.0
  'project_created','idea_promoted','status_changed','diagnosis_created','diagnosis_revised','action_created',
  'action_completed','goal_created','document_generated','document_approved','document_signed',
  'opportunity_matched','match_feedback','partner_added','submission_created','submission_sent','risk_created',
  'risk_resolved','snapshot_taken','project_archived',
  -- v0.16.0 — rede
  'relationship_created','relationship_ended','proposal_sent','proposal_viewed','proposal_accepted',
  'proposal_declined','proposal_changes_requested','proposal_withdrawn','listing_published','listing_paused',
  'investment_intent','investment_committed','impact_update_submitted','impact_update_accepted',
  'impact_update_published','conversation_started','team_member_added','team_member_removed',
  'experience_confirmed','enforcement_applied'));

-- ================================================================================================ 17. GATILHOS
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['relationships','proposals','marketplace_listings','impact_updates','public_profiles',
                           'professional_experiences','enforcement_actions','territory_needs','investment_intents',
                           'recommendations','taxonomies','conversations']
  LOOP
    EXECUTE format('CREATE TRIGGER trg_touch BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION touch_updated_at()', t);
  END LOOP;
END $$;

-- Append-only: histórico de proposta, de identificador e evento de domínio não se reescrevem.
CREATE TRIGGER trg_append_only BEFORE UPDATE OR DELETE ON proposal_events FOR EACH ROW
  WHEN (current_user::text = 'impacto_app') EXECUTE FUNCTION forbid_mutation();
CREATE TRIGGER trg_append_only BEFORE UPDATE OR DELETE ON handle_history FOR EACH ROW
  WHEN (current_user::text = 'impacto_app') EXECUTE FUNCTION forbid_mutation();
CREATE TRIGGER trg_append_only BEFORE UPDATE OR DELETE ON domain_events FOR EACH ROW
  WHEN (current_user::text = 'impacto_app') EXECUTE FUNCTION forbid_mutation();
CREATE TRIGGER trg_append_only BEFORE UPDATE OR DELETE ON readiness_snapshots FOR EACH ROW
  WHEN (current_user::text = 'impacto_app') EXECUTE FUNCTION forbid_mutation();

-- Colunas que a organização NÃO escreve por conta própria.
CREATE TRIGGER trg_guard BEFORE UPDATE ON proposals FOR EACH ROW
  EXECUTE FUNCTION guard_columns('kind','sender_org_id','receiver_org_id','sent_at','viewed_at',
                                 'decided_at','decided_by','version');
-- `publication_state` NÃO entra: publicar o próprio anúncio é o produto. O que a organização não escreve é o
-- carimbo de publicação (derivado), o contador de visualizações e o motivo de suspensão (moderação).
CREATE TRIGGER trg_guard BEFORE UPDATE ON marketplace_listings FOR EACH ROW
  EXECUTE FUNCTION guard_columns('published_at','published_by','views','suspended_reason');
CREATE TRIGGER trg_guard BEFORE UPDATE ON public_profiles FOR EACH ROW
  EXECUTE FUNCTION guard_columns('public_fields','views','verified_badge','suspended');
-- `status` NÃO entra: enviar o próprio relatório e publicá-lo depois de aceito é o produto. O que não se escreve
-- é a apuração do servidor (metrics/milestones/evidence_count) e a autoria da revisão, que o gatilho deriva.
CREATE TRIGGER trg_guard BEFORE UPDATE ON impact_updates FOR EACH ROW
  EXECUTE FUNCTION guard_columns('metrics','milestones','evidence_count','reviewed_by','reviewed_at',
                                 'reviewed_by_org','submitted_at','published_at');
CREATE TRIGGER trg_guard BEFORE UPDATE ON investment_intents FOR EACH ROW
  EXECUTE FUNCTION guard_columns('commitment_id');
CREATE TRIGGER trg_guard BEFORE UPDATE ON relationships FOR EACH ROW
  EXECUTE FUNCTION guard_columns('kind','source_org_id','source_user_id','org_id','mirrored_from');

-- Proposta nasce em rascunho; anúncio nasce em rascunho. Nada "nasce publicado" ou "nasce aceito".
CREATE FUNCTION network_initial_state() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_TABLE_NAME = 'proposals' AND NEW.status <> 'draft' AND current_user::text = 'impacto_app'
     AND NOT app_priv() THEN
    RAISE EXCEPTION 'Proposta nasce em rascunho' USING ERRCODE = '42501';
  END IF;
  IF TG_TABLE_NAME = 'marketplace_listings' AND NEW.publication_state <> 'draft'
     AND current_user::text = 'impacto_app' AND NOT app_priv() THEN
    RAISE EXCEPTION 'Anúncio nasce em rascunho' USING ERRCODE = '42501';
  END IF;
  IF TG_TABLE_NAME = 'impact_updates' AND NEW.status <> 'draft' AND current_user::text = 'impacto_app'
     AND NOT app_priv() THEN
    RAISE EXCEPTION 'Relatório de impacto nasce em rascunho' USING ERRCODE = '42501';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_initial BEFORE INSERT ON proposals FOR EACH ROW EXECUTE FUNCTION network_initial_state();
CREATE TRIGGER trg_initial BEFORE INSERT ON marketplace_listings FOR EACH ROW
  EXECUTE FUNCTION network_initial_state();
CREATE TRIGGER trg_initial BEFORE INSERT ON impact_updates FOR EACH ROW EXECUTE FUNCTION network_initial_state();

-- ================================================================================================ 18. RLS
ALTER TABLE relationships ENABLE ROW LEVEL SECURITY;
ALTER TABLE proposals ENABLE ROW LEVEL SECURITY;
ALTER TABLE proposal_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE proposal_attachments ENABLE ROW LEVEL SECURITY;
ALTER TABLE proposal_status_graph ENABLE ROW LEVEL SECURITY;
ALTER TABLE message_attachments ENABLE ROW LEVEL SECURITY;
ALTER TABLE marketplace_listings ENABLE ROW LEVEL SECURITY;
ALTER TABLE impact_updates ENABLE ROW LEVEL SECURITY;
ALTER TABLE personas ENABLE ROW LEVEL SECURITY;
ALTER TABLE org_personas ENABLE ROW LEVEL SECURITY;
ALTER TABLE taxonomies ENABLE ROW LEVEL SECURITY;
ALTER TABLE taxonomy_terms ENABLE ROW LEVEL SECURITY;
ALTER TABLE public_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE handle_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE reserved_handles ENABLE ROW LEVEL SECURITY;
ALTER TABLE professional_experiences ENABLE ROW LEVEL SECURITY;
ALTER TABLE enforcement_actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE territory_needs ENABLE ROW LEVEL SECURITY;
ALTER TABLE investment_intents ENABLE ROW LEVEL SECURITY;
ALTER TABLE recommendations ENABLE ROW LEVEL SECURITY;
ALTER TABLE readiness_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE domain_events ENABLE ROW LEVEL SECURITY;

-- Relação: a organização vê a relação que criou, a que aponta para ela, e a que aponta para projeto dela.
-- A relação PÚBLICA/de rede é visível a quem está autenticado — e é `visibility` que decide, nunca a existência.
CREATE POLICY rel_read ON relationships FOR SELECT USING (
  org_id = app_org() OR target_org_id = app_org() OR source_org_id = app_org()
  OR target_user_id = app_uid() OR source_user_id = app_uid()
  OR (visibility IN ('network','public') AND app_authenticated())
  OR (target_project_id IS NOT NULL AND app_project_party(target_project_id))
  OR app_priv());
CREATE POLICY rel_write ON relationships FOR INSERT WITH CHECK (
  (org_id = app_org() AND (source_org_id IS NULL OR source_org_id = app_org())
   AND (source_user_id IS NULL OR source_user_id = app_uid())) OR app_priv());
CREATE POLICY rel_update ON relationships FOR UPDATE USING (org_id = app_org() OR app_priv())
  WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY rel_delete ON relationships FOR DELETE USING (org_id = app_org() OR app_priv());

-- Proposta: só as duas partes. Travessia por função SECURITY DEFINER (ADR 104).
CREATE POLICY prop_read ON proposals FOR SELECT USING (
  sender_org_id = app_org() OR receiver_org_id = app_org() OR app_priv());
CREATE POLICY prop_insert ON proposals FOR INSERT WITH CHECK (
  (sender_org_id = app_org() AND NOT app_blocked_between(sender_org_id, receiver_org_id)) OR app_priv());
CREATE POLICY prop_update ON proposals FOR UPDATE
  USING (sender_org_id = app_org() OR receiver_org_id = app_org() OR app_priv())
  WITH CHECK (sender_org_id = app_org() OR receiver_org_id = app_org() OR app_priv());
CREATE POLICY propev_read ON proposal_events FOR SELECT
  USING (proposal_is_party(proposal_id, app_org()) OR app_priv());
CREATE POLICY propev_insert ON proposal_events FOR INSERT
  WITH CHECK (proposal_is_party(proposal_id, app_org()) OR app_priv());
CREATE POLICY propatt_rw ON proposal_attachments FOR ALL
  USING (proposal_is_party(proposal_id, app_org()) OR app_priv())
  WITH CHECK (proposal_is_party(proposal_id, app_org()) OR app_priv());
CREATE POLICY propgraph_read ON proposal_status_graph FOR SELECT USING (app_authenticated() OR app_priv());
CREATE POLICY propgraph_write ON proposal_status_graph FOR ALL USING (app_priv()) WITH CHECK (app_priv());

-- Anexo de recado: segue a legibilidade do recado, que segue a da conversa.
CREATE POLICY msgatt_rw ON message_attachments FOR ALL
  USING (EXISTS (SELECT 1 FROM messages m WHERE m.id = message_attachments.message_id) OR app_priv())
  WITH CHECK (EXISTS (SELECT 1 FROM messages m WHERE m.id = message_attachments.message_id) OR app_priv());

-- Anúncio: a organização vê os seus; qualquer autenticado vê os PUBLICADOS. A rota pública usa contexto de sistema
-- e filtra publication_state = 'published' — ver api/network_routes.py.
CREATE POLICY listing_read ON marketplace_listings FOR SELECT USING (
  org_id = app_org() OR (publication_state = 'published' AND app_authenticated()) OR app_priv());
CREATE POLICY listing_write ON marketplace_listings FOR ALL USING (org_id = app_org() OR app_priv())
  WITH CHECK (org_id = app_org() OR app_priv());

-- Relatório de impacto: a organização dona e quem é parte do projeto (financiador com candidatura).
CREATE POLICY impupd_read ON impact_updates FOR SELECT USING (
  org_id = app_org() OR app_project_party(project_id)
  OR (status = 'published' AND app_authenticated()) OR app_priv());
CREATE POLICY impupd_write ON impact_updates FOR ALL USING (org_id = app_org() OR app_priv())
  WITH CHECK (org_id = app_org() OR app_priv());

-- Catálogos de referência: leitura para quem está autenticado, escrita só privilegiada.
CREATE POLICY personas_read ON personas FOR SELECT USING (app_authenticated() OR app_priv());
CREATE POLICY personas_write ON personas FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY orgpersona_read ON org_personas FOR SELECT
  USING (org_id = app_org() OR app_authenticated() OR app_priv());
CREATE POLICY orgpersona_write ON org_personas FOR ALL USING (org_id = app_org() OR app_priv())
  WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY tax_read ON taxonomies FOR SELECT USING (app_authenticated() OR app_priv());
CREATE POLICY tax_write ON taxonomies FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY taxterm_read ON taxonomy_terms FOR SELECT USING (app_authenticated() OR app_priv());
CREATE POLICY taxterm_write ON taxonomy_terms FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY reserved_read ON reserved_handles FOR SELECT USING (app_authenticated() OR app_priv());
CREATE POLICY reserved_write ON reserved_handles FOR ALL USING (app_priv()) WITH CHECK (app_priv());

-- Perfil: a dona escreve; perfil público não suspenso é legível por quem está autenticado. A página PÚBLICA (sem
-- login) é servida em contexto de sistema lendo SÓ `public_fields`.
CREATE POLICY profile_read ON public_profiles FOR SELECT USING (
  org_id = app_org() OR user_id = app_uid()
  OR (visibility = 'public' AND NOT suspended AND app_authenticated())
  OR (visibility = 'network' AND app_authenticated()) OR app_priv());
CREATE POLICY profile_write ON public_profiles FOR ALL
  USING (org_id = app_org() OR user_id = app_uid() OR app_priv())
  WITH CHECK (org_id = app_org() OR user_id = app_uid() OR app_priv());
CREATE POLICY handlehist_read ON handle_history FOR SELECT USING (app_priv());
CREATE POLICY handlehist_insert ON handle_history FOR INSERT WITH CHECK (true);

-- Experiência: a pessoa escreve a dela; a organização citada vê e confirma; pública quando a pessoa deixa.
CREATE POLICY profexp_read ON professional_experiences FOR SELECT USING (
  user_id = app_uid() OR org_id = app_org()
  OR (visibility = 'public' AND app_authenticated())
  OR (visibility = 'network' AND app_authenticated()) OR app_priv());
CREATE POLICY profexp_insert ON professional_experiences FOR INSERT
  WITH CHECK (user_id = app_uid() OR app_priv());
CREATE POLICY profexp_update ON professional_experiences FOR UPDATE
  USING (user_id = app_uid() OR org_id = app_org() OR app_priv())
  WITH CHECK (user_id = app_uid() OR org_id = app_org() OR app_priv());
CREATE POLICY profexp_delete ON professional_experiences FOR DELETE USING (user_id = app_uid() OR app_priv());

-- Moderação: o alvo vê a medida aplicada a si (direito de saber e contestar); o resto é da administração.
CREATE POLICY enf_read ON enforcement_actions FOR SELECT USING (
  target_org_id = app_org() OR target_user_id = app_uid() OR app_priv());
CREATE POLICY enf_write ON enforcement_actions FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY enf_appeal ON enforcement_actions FOR UPDATE
  USING (target_org_id = app_org() OR target_user_id = app_uid())
  WITH CHECK (target_org_id = app_org() OR target_user_id = app_uid());

-- Necessidade de território: pública por padrão (é informação de interesse público).
CREATE POLICY terrneed_read ON territory_needs FOR SELECT USING (
  org_id = app_org() OR (visibility IN ('public','network') AND app_authenticated()) OR app_priv());
CREATE POLICY terrneed_write ON territory_needs FOR ALL USING (org_id = app_org() OR app_priv())
  WITH CHECK (org_id = app_org() OR app_priv());

-- Intenção de apoio: investidor e organização dona do projeto. A intenção de um investidor NÃO é visível a outro.
CREATE POLICY intent_read ON investment_intents FOR SELECT USING (
  investor_org_id = app_org() OR app_project_party(project_id)
  OR EXISTS (SELECT 1 FROM projects p WHERE p.id = investment_intents.project_id AND p.org_id = app_org())
  OR app_priv());
CREATE POLICY intent_write ON investment_intents FOR ALL USING (investor_org_id = app_org() OR app_priv())
  WITH CHECK (investor_org_id = app_org() OR app_priv());

-- Recomendação e prontidão: só da própria organização.
CREATE POLICY rec_read ON recommendations FOR SELECT USING (org_id = app_org() OR app_priv());
CREATE POLICY rec_write ON recommendations FOR ALL USING (org_id = app_org() OR app_priv())
  WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY readiness_read ON readiness_snapshots FOR SELECT USING (org_id = app_org() OR app_priv());
CREATE POLICY readiness_insert ON readiness_snapshots FOR INSERT WITH CHECK (org_id = app_org() OR app_priv());

-- Evento de domínio: a organização vê os seus; quem é parte do projeto vê os do projeto.
CREATE POLICY devent_read ON domain_events FOR SELECT USING (
  org_id = app_org() OR (project_id IS NOT NULL AND app_project_party(project_id)) OR app_priv());
CREATE POLICY devent_insert ON domain_events FOR INSERT WITH CHECK (
  org_id = app_org() OR org_id IS NULL OR app_priv());

-- ================================================================================================ 19. GRANTS
GRANT SELECT, INSERT, UPDATE, DELETE ON relationships, proposals, proposal_attachments, marketplace_listings,
  impact_updates, org_personas, public_profiles, professional_experiences, territory_needs, investment_intents,
  recommendations TO impacto_app;
GRANT SELECT, INSERT ON proposal_events, handle_history, readiness_snapshots, domain_events TO impacto_app;
GRANT SELECT ON personas, taxonomies, taxonomy_terms, reserved_handles, proposal_status_graph TO impacto_app;
GRANT SELECT ON enforcement_actions TO impacto_app;
-- o alvo pode registrar a contestação, e só isso
GRANT UPDATE (appeal_note, appeal_at, status, updated_at) ON enforcement_actions TO impacto_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON message_attachments TO impacto_app;
GRANT USAGE, SELECT ON SEQUENCE proposal_events_id_seq, handle_history_id_seq, domain_events_id_seq TO impacto_app;

-- ================================================================================================ 20. ÍNDICES DA MEDIÇÃO
-- Cada índice abaixo cita a consulta que o justifica (mesma regra da 0015).
-- "propostas que eu recebi, não decididas" — caixa de entrada do investidor e da organização
CREATE INDEX ix_prop_inbox ON proposals(receiver_org_id, created_at DESC)
  WHERE status IN ('sent','viewed','in_review','changes_requested');
-- "anúncios publicados por causa e território" — consulta central do marketplace
CREATE INDEX ix_listing_causes ON marketplace_listings USING gin(causes) WHERE publication_state = 'published';
CREATE INDEX ix_listing_seeking ON marketplace_listings USING gin(seeking) WHERE publication_state = 'published';
-- "minhas recomendações abertas por prioridade" — home de toda persona
CREATE INDEX ix_rec_home ON recommendations(org_id, priority DESC, created_at DESC) WHERE status = 'open';
-- "relatórios do projeto por período"
CREATE INDEX ix_impupd_period ON impact_updates(project_id, period_start DESC);
-- "experiências confirmadas de uma pessoa" — perfil público
CREATE INDEX ix_profexp_public ON professional_experiences(user_id, state)
  WHERE state = 'confirmed' AND visibility = 'public';
-- "necessidades abertas de um território" — workspace do governo
CREATE INDEX ix_terrneed_open ON territory_needs(territory, priority DESC) WHERE status = 'open';

-- Chave estrangeira de caminho de acesso sem índice próprio (mesma regra da 0015, conferida por
-- scripts/db_integrity_report.py). O índice único de assunto do anúncio usa coalesce, então não serve ao
-- ON DELETE CASCADE de cada pai nem à busca "anúncios deste projeto".
CREATE INDEX ix_fk_marketplace_listings_project_id ON marketplace_listings(project_id)
  WHERE project_id IS NOT NULL;
CREATE INDEX ix_fk_marketplace_listings_call_id ON marketplace_listings(call_id) WHERE call_id IS NOT NULL;
CREATE INDEX ix_fk_marketplace_listings_solution_id ON marketplace_listings(solution_id)
  WHERE solution_id IS NOT NULL;
CREATE INDEX ix_fk_professional_experiences_project_id ON professional_experiences(project_id)
  WHERE project_id IS NOT NULL;
CREATE INDEX ix_fk_proposals_call_id ON proposals(call_id) WHERE call_id IS NOT NULL;
CREATE INDEX ix_fk_proposals_solution_id ON proposals(solution_id) WHERE solution_id IS NOT NULL;
