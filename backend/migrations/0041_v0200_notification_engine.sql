-- v0.20.0 — motor de notificação: um caminho só, e o que §23 pede (preferência, prioridade,
-- agrupamento, deduplicação, rate limit, quiet period, retry, delivery status).
--
-- O DEFEITO QUE ESTA MIGRAÇÃO CORRIGE, E QUE NÃO ERA VISÍVEL
--
-- Existiam TRÊS caminhos de notificação: `notify_team`, `notify_org_members` (v0.16.0, que respeitam
-- preferência, deduplicam e carregam prioridade) e `app_notify` (v0.2.0, que não faz nada disso).
-- As 29 chamadas diretas a `app_notify` espalhadas pelo produto usam 15 prefixos — `compliance`,
-- `application`, `payment`, `alert`, `execution`, `evidence`, `professional`, `agreement`,
-- `mentoring`, `solution`, `impact`, `interest`, `review`, `qualification`, `institutional` — e
-- NENHUM deles é um grupo de `notification_prefs`. A consequência prática: a pessoa desliga tudo o
-- que a tela de preferências oferece e continua recebendo esses avisos, porque a cláusula
-- `np.grp = split_part(kind,'.',1)` nunca casa. O interruptor existia e não estava ligado a nada.
--
-- A correção é um CATÁLOGO e um GATILHO, não 29 reescritas. O gatilho roda no INSERT da tabela, que
-- é por onde os três caminhos passam — então preferência, grupo, prioridade e janela de silêncio
-- valem para todos, inclusive para qualquer caminho futuro que alguém escreva sem ler isto.

-- ============================================================ catálogo de tipos de aviso
CREATE TABLE notification_kinds (
  kind             text PRIMARY KEY CHECK (kind ~ '^[a-z][a-z_]{2,40}$'),
  grp              text NOT NULL CHECK (grp IN (
                     'billing','content','events','support','partnerships','opportunities',
                     'network','proposal','message','funding','report','project','document',
                     'account','program')),
  label_pt         text NOT NULL CHECK (length(label_pt) BETWEEN 3 AND 120),
  default_priority text NOT NULL DEFAULT 'normal' CHECK (default_priority IN ('low','normal','high','critical')),
  emailable        boolean NOT NULL DEFAULT false,
  description      text NOT NULL CHECK (length(description) BETWEEN 10 AND 600)
);
COMMENT ON TABLE notification_kinds IS
  'Quais avisos existem e a qual interruptor de preferência cada um pertence. É catálogo, não CASE '
  'escondido em função: a pessoa só consegue silenciar o que está declarado aqui, e um tipo que '
  'não esteja declarado é um tipo que escapa da preferência dela.';
COMMENT ON COLUMN notification_kinds.emailable IS
  'Se este tipo PODE sair por e-mail — ainda sujeito à preferência de e-mail da pessoa. Nenhum '
  'tipo vira e-mail por ser importante: tem de estar declarado aqui.';

INSERT INTO notification_kinds(kind, grp, label_pt, default_priority, emailable, description) VALUES
  -- grupos que já eram grupos (os caminhos novos, v0.16.0+)
  ('billing','billing','Cobrança e assinatura','high',true,'Fatura, cobrança, teste terminando, mudança de plano.'),
  ('content','content','Conteúdo e biblioteca','low',false,'Novidades de conteúdo publicado na plataforma.'),
  ('events','events','Eventos','normal',true,'Inscrição, lembrete e mudança de evento.'),
  ('support','support','Suporte','high',true,'Resposta a chamado aberto por você.'),
  ('partnerships','partnerships','Parcerias','normal',false,'Andamento de pedido de parceria.'),
  ('opportunities','opportunities','Oportunidades','normal',false,'Chamada, edital ou oportunidade compatível com o seu perfil.'),
  ('network','network','Rede','normal',false,'Relação, anúncio, oferta profissional e experiência.'),
  ('proposal','proposal','Propostas','high',false,'Proposta recebida, respondida ou encerrada.'),
  ('message','message','Mensagens','normal',false,'Recado e conversa na plataforma.'),
  ('funding','funding','Financiamento','high',false,'Candidatura, aporte, desembolso e modelo de contribuição.'),
  ('report','report','Relatos e apuração','high',true,'Denúncia recebida, pedido de manifestação e conclusão de apuração.'),
  ('project','project','Projeto','normal',false,'Execução, marco, indicador, evidência, risco e diagnóstico.'),
  ('document','document','Documentos','normal',false,'Documento anexado, vencendo ou validado.'),
  ('account','account','Conta e conformidade','high',true,'Medida de moderação, conformidade, qualificação e situação institucional.'),
  ('program','program','Programas','normal',false,'Andamento de programa com vários projetos.'),
  -- os 15 prefixos legados, que até aqui não pertenciam a interruptor nenhum
  ('compliance','account','Conformidade','high',true,'Pendência ou restrição de conformidade da organização.'),
  ('application','funding','Candidatura','high',false,'Andamento da sua candidatura a uma chamada.'),
  ('payment','funding','Pagamento do aporte','high',false,'Mudança de estado de pagamento ou pedido de estorno.'),
  ('alert','opportunities','Alerta de oportunidade','normal',false,'Oportunidade nova compatível com o alerta que você salvou.'),
  ('execution','project','Execução','normal',false,'Despesa revisada e andamento de execução.'),
  ('evidence','project','Evidência','normal',false,'Evidência enviada ou revisada.'),
  ('professional','network','Oferta profissional','normal',false,'Oferta de profissional e resultado da análise.'),
  ('agreement','account','Instrumento institucional','high',false,'Decisão sobre instrumento ou convênio.'),
  ('mentoring','network','Mentoria','normal',false,'Andamento de mentoria.'),
  ('solution','project','Solução','normal',false,'Andamento do fluxo de solução.'),
  ('impact','project','Impacto','normal',false,'Indicador de impacto revisado.'),
  ('interest','network','Interesse','normal',false,'Alguém demonstrou interesse no seu projeto.'),
  ('review','document','Validação profissional','high',false,'Pedido e resultado de validação profissional de documento.'),
  ('qualification','account','Qualificação institucional','high',true,'Decisão sobre qualificação (OSCIP, CEBAS e afins).'),
  ('institutional','account','Situação institucional','high',true,'Mudança de situação institucional da organização.'),
  -- v0.20.0 — segurança da conta. Nasce CRÍTICO: atravessa janela de silêncio e limite diário,
  -- porque avisar amanhã de manhã que uma credencial pode ter sido copiada não é avisar.
  ('security','account','Segurança da conta','critical',true,
   'Sessões encerradas por precaução, reuso de credencial e outros sinais de acesso indevido.');

ALTER TABLE notification_kinds ENABLE ROW LEVEL SECURITY;
CREATE POLICY notification_kinds_read ON notification_kinds FOR SELECT USING (true);
GRANT SELECT ON notification_kinds TO impacto_app;

-- ============================================================ política declarada da plataforma
CREATE TABLE notification_policy (
  only_row         boolean PRIMARY KEY DEFAULT true CHECK (only_row),
  max_per_day      integer NOT NULL CHECK (max_per_day BETWEEN 1 AND 1000),
  quiet_from       time,
  quiet_to         time,
  digest_hour      smallint NOT NULL CHECK (digest_hour BETWEEN 0 AND 23),
  retry_max        smallint NOT NULL CHECK (retry_max BETWEEN 0 AND 10),
  retry_backoff_minutes integer NOT NULL CHECK (retry_backoff_minutes BETWEEN 1 AND 1440),
  note             text NOT NULL
);
COMMENT ON TABLE notification_policy IS
  'Os números do rate limit, da janela de silêncio e da repetição de envio ficam AQUI, em uma linha '
  'que se lê, e não espalhados por constantes no código. Cada pessoa sobrescreve os dela em '
  '`notification_prefs`; esta linha é o que vale para quem não configurou nada.';

INSERT INTO notification_policy(only_row, max_per_day, quiet_from, quiet_to, digest_hour,
                                retry_max, retry_backoff_minutes, note) VALUES
  (true, 50, '22:00', '07:00', 8, 3, 30,
   'Padrão da plataforma: até 50 avisos por pessoa por dia por grupo; nada chega entre 22h e 7h '
   '(fica retido e é entregue às 7h); aviso de prioridade CRÍTICA ignora a janela de silêncio e o '
   'limite diário, porque é exatamente o que trava o trabalho da pessoa — medida de moderação, '
   'prazo vencendo, decisão pendente. Envio por e-mail tenta 3 vezes, com 30 minutos entre as '
   'tentativas, e a falha fica registrada em notification_deliveries em vez de sumir.');

ALTER TABLE notification_policy ENABLE ROW LEVEL SECURITY;
CREATE POLICY notification_policy_read ON notification_policy FOR SELECT USING (true);
GRANT SELECT ON notification_policy TO impacto_app;

-- ============================================================ preferências por pessoa
ALTER TABLE notification_prefs
  ADD COLUMN quiet_from  time,
  ADD COLUMN quiet_to    time,
  ADD COLUMN max_per_day integer CHECK (max_per_day IS NULL OR max_per_day BETWEEN 1 AND 1000),
  ADD COLUMN digest      text NOT NULL DEFAULT 'off' CHECK (digest IN ('off','daily'));
COMMENT ON COLUMN notification_prefs.quiet_from IS
  'Janela de silêncio DESTA pessoa; nula significa "use a da plataforma". O aviso não é descartado: '
  'ele é retido e entregue quando a janela fecha. Descartar seria perder o fato.';
COMMENT ON COLUMN notification_prefs.digest IS
  '`daily` agrupa os avisos deste grupo em uma entrega por dia, no horário da política. Serve a '
  'quem quer o fato sem a interrupção.';

-- ============================================================ a notificação em si
ALTER TABLE notifications
  ADD COLUMN grp           text,
  ADD COLUMN deliver_after timestamptz NOT NULL DEFAULT now(),
  ADD COLUMN throttled     boolean NOT NULL DEFAULT false,
  ADD COLUMN unmapped_kind boolean NOT NULL DEFAULT false;
COMMENT ON COLUMN notifications.grp IS
  'Grupo de preferência resolvido no INSERT pelo catálogo. Materializado de propósito: a preferência '
  'da pessoa é lida em consulta quente, e `split_part(kind, ...)` em cada leitura foi exatamente o '
  'que permitiu que 15 prefixos passassem anos fora de qualquer interruptor.';
COMMENT ON COLUMN notifications.deliver_after IS
  'Quando este aviso pode sair da caixa para um canal externo. Janela de silêncio e agrupamento '
  'diário mexem aqui; o aviso aparece na caixa na hora, o que muda é a entrega.';
COMMENT ON COLUMN notifications.unmapped_kind IS
  'VERDADEIRO quando o tipo não estava no catálogo e o aviso caiu no grupo `account` por falta de '
  'declaração. Uma notificação nunca é perdida por isso — mas a lacuna fica contada e visível em '
  'vez de silenciosa. Um teste exige que este contador seja zero.';

CREATE INDEX ix_notifications_pending_delivery ON notifications(deliver_after)
  WHERE emailed_at IS NULL;

-- ============================================================ entrega: tentativa, falha, repetição
CREATE TABLE notification_deliveries (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  notification_id uuid NOT NULL REFERENCES notifications(id) ON DELETE CASCADE,
  channel         text NOT NULL CHECK (channel IN ('email','in_app')),
  status          text NOT NULL CHECK (status IN ('pending','sent','failed','skipped','given_up')),
  attempts        smallint NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  last_error      text CHECK (last_error IS NULL OR length(last_error) <= 500),
  skipped_reason  text CHECK (skipped_reason IS NULL OR skipped_reason IN
                    ('preference','quiet_period','rate_limit','not_emailable','no_verified_email')),
  next_retry_at   timestamptz,
  sent_at         timestamptz,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (notification_id, channel)
);
COMMENT ON TABLE notification_deliveries IS
  'Estado REAL de entrega por canal. `sent` significa aceito pelo servidor de e-mail — jamais '
  '"lido" nem "entregue na caixa da pessoa", que são coisas que a plataforma não tem como saber. '
  '`skipped` com motivo é informação: diz POR QUE o aviso não saiu, em vez de deixar quem suporta '
  'adivinhar entre preferência, silêncio e limite.';
CREATE INDEX ix_notification_deliveries_retry ON notification_deliveries(next_retry_at)
  WHERE status = 'failed';

ALTER TABLE notification_deliveries ENABLE ROW LEVEL SECURITY;
CREATE POLICY notification_deliveries_read ON notification_deliveries FOR SELECT
  USING (EXISTS (SELECT 1 FROM notifications n WHERE n.id = notification_id
                   AND (n.user_id = app_uid() OR app_priv())));
CREATE POLICY notification_deliveries_write ON notification_deliveries FOR ALL
  USING (app_system() OR app_priv()) WITH CHECK (app_system() OR app_priv());
GRANT SELECT, INSERT, UPDATE ON notification_deliveries TO impacto_app;
CREATE TRIGGER trg_notification_deliveries_touch BEFORE UPDATE ON notification_deliveries
  FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- ============================================================ O caminho único
CREATE FUNCTION notification_fill() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
  pol      notification_policy%ROWTYPE;
  cat      notification_kinds%ROWTYPE;
  pref     notification_prefs%ROWTYPE;
  prefixo  text := split_part(NEW.kind, '.', 1);
  q_de     time;
  q_ate    time;
  teto     integer;
  hoje     integer;
  agora    timestamptz := now();
BEGIN
  SELECT * INTO pol FROM notification_policy LIMIT 1;
  SELECT * INTO cat FROM notification_kinds WHERE kind = prefixo;

  IF cat.kind IS NULL THEN
    -- Nunca perder o aviso por falta de declaração; mas também nunca esconder a lacuna.
    NEW.grp := 'account';
    NEW.unmapped_kind := true;
  ELSE
    NEW.grp := cat.grp;
    IF NEW.priority IS NULL OR NEW.priority = 'normal' THEN
      NEW.priority := cat.default_priority;
    END IF;
  END IF;

  -- Aviso CRÍTICO não é retido nem limitado: é o que trava o trabalho da pessoa.
  IF NEW.priority = 'critical' OR NEW.user_id IS NULL THEN
    RETURN NEW;
  END IF;

  SELECT * INTO pref FROM notification_prefs WHERE user_id = NEW.user_id AND grp = NEW.grp;
  q_de  := coalesce(pref.quiet_from, pol.quiet_from);
  q_ate := coalesce(pref.quiet_to,   pol.quiet_to);
  teto  := coalesce(pref.max_per_day, pol.max_per_day);

  -- rate limit por pessoa e por grupo, nas últimas 24 horas
  SELECT count(*) INTO hoje FROM notifications n
   WHERE n.user_id = NEW.user_id AND n.grp = NEW.grp AND n.created_at > agora - interval '24 hours';
  IF hoje >= teto THEN
    NEW.throttled := true;
    NEW.deliver_after := date_trunc('day', agora) + interval '1 day'
                         + make_interval(hours => pol.digest_hour);
    RETURN NEW;
  END IF;

  -- agrupamento diário pedido pela pessoa
  IF pref.digest = 'daily' THEN
    NEW.deliver_after := date_trunc('day', agora) + interval '1 day'
                         + make_interval(hours => pol.digest_hour);
    RETURN NEW;
  END IF;

  -- janela de silêncio: retém, não descarta
  IF q_de IS NOT NULL AND q_ate IS NOT NULL THEN
    IF (q_de < q_ate AND agora::time >= q_de AND agora::time < q_ate)
       OR (q_de > q_ate AND (agora::time >= q_de OR agora::time < q_ate)) THEN
      NEW.deliver_after := CASE
        WHEN agora::time < q_ate THEN date_trunc('day', agora) + q_ate
        ELSE date_trunc('day', agora) + interval '1 day' + q_ate END;
    END IF;
  END IF;

  RETURN NEW;
END $$;
CREATE TRIGGER trg_notification_fill BEFORE INSERT ON notifications
  FOR EACH ROW EXECUTE FUNCTION notification_fill();
COMMENT ON FUNCTION notification_fill IS
  'Grupo, prioridade, limite diário, agrupamento e janela de silêncio em UM lugar: o INSERT da '
  'tabela, por onde os três caminhos de notificação passam. Posto em qualquer um dos três, o quarto '
  'caminho que alguém escrever amanhã escaparia.';

-- `app_notify` reescrita: mesma assinatura de seis argumentos (as 29 chamadas existentes continuam
-- valendo) e, pela primeira vez, respeitando a preferência da pessoa.
CREATE OR REPLACE FUNCTION app_notify(p_org uuid, p_user uuid, p_kind text, p_title text,
                                      p_body text, p_link text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE nid uuid; v_grp text;
BEGIN
  IF app_uid() IS NULL AND NOT app_system() THEN
    RAISE EXCEPTION 'notificação exige contexto autenticado' USING ERRCODE = '42501';
  END IF;
  v_grp := coalesce((SELECT grp FROM notification_kinds WHERE kind = split_part(p_kind, '.', 1)),
                    'account');
  -- A correção central desta migração. Até aqui esta função ignorava `notification_prefs`, e por
  -- isso 15 tipos de aviso não podiam ser silenciados por ninguém.
  IF p_user IS NOT NULL AND EXISTS (SELECT 1 FROM notification_prefs np
                                     WHERE np.user_id = p_user AND np.grp = v_grp AND NOT np.in_app) THEN
    RETURN NULL;
  END IF;
  INSERT INTO notifications(org_id, user_id, kind, title, body, link)
  VALUES (p_org, p_user, p_kind, left(p_title, 200), left(p_body, 2000), p_link) RETURNING id INTO nid;
  RETURN nid;
END $$;
COMMENT ON FUNCTION app_notify(uuid, uuid, text, text, text, text) IS
  'Aviso dirigido a UMA pessoa ou a uma organização. Desde a v0.20.0 respeita notification_prefs e '
  'passa pelo gatilho que resolve grupo, prioridade, limite e janela de silêncio. Quando p_user é '
  'nulo o aviso é da organização e não há preferência pessoal a consultar.';

-- Quem já tem notificação gravada recebe o grupo resolvido, para a caixa não ficar com metade das
-- linhas sem grupo. Nenhuma linha muda de conteúdo.
UPDATE notifications SET grp = coalesce(
  (SELECT k.grp FROM notification_kinds k WHERE k.kind = split_part(notifications.kind, '.', 1)),
  'account') WHERE grp IS NULL;
