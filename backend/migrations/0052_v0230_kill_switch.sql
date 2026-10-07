-- v0.23.0 — INTERRUPTOR DE EMERGÊNCIA (KILL SWITCH)
--
-- POR QUE ISTO NÃO É UMA FEATURE FLAG
--
-- `feature_flags` já existe e é editável por `maintenance.execute`. Serve para ligar e desligar
-- funcionalidade em condição normal. Um interruptor de emergência é outra coisa:
--
--   * é acionado DURANTE um incidente, por quem tem o papel mais alto, com motivo obrigatório;
--   * tem de valer em segundos, não no próximo deploy;
--   * NUNCA pode bloquear a trilha de auditoria — durante uma invasão, registrar o que está
--     acontecendo é a única coisa que não se pode perder;
--   * tem de poder ser DESLIGADO mesmo com ele ligado (vidro quebrado): um interruptor que se
--     tranca do lado de fora transforma incidente em indisponibilidade permanente.
--
-- MODELO: `kill_switch_events` é append-only (histórico do incidente, que é prova) e
-- `kill_switch_state` é o estado derivado, mantido por gatilho. Não há UPDATE em histórico:
-- desligar é um evento novo, como no Value Ledger.

CREATE TABLE IF NOT EXISTS kill_switch_events (
  id            bigserial PRIMARY KEY,
  scope         text NOT NULL CHECK (scope IN ('mutations','logins','uploads','integrations','maintenance')),
  action        text NOT NULL CHECK (action IN ('engage','release')),
  reason        text NOT NULL CHECK (length(btrim(reason)) >= 10),
  actor_user_id uuid REFERENCES users(id),
  request_id    text,
  ip            inet,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS kill_switch_state (
  scope       text PRIMARY KEY CHECK (scope IN ('mutations','logins','uploads','integrations','maintenance')),
  engaged     boolean NOT NULL DEFAULT false,
  reason      text,
  actor_user_id uuid REFERENCES users(id),
  since       timestamptz,
  updated_at  timestamptz NOT NULL DEFAULT now(),
  -- Ligado sem motivo e sem horário é estado impossível: quem investiga depois precisa dos dois.
  CONSTRAINT kill_switch_engaged_is_justified
    CHECK (NOT engaged OR (reason IS NOT NULL AND since IS NOT NULL))
);

INSERT INTO kill_switch_state (scope, engaged)
VALUES ('mutations', false), ('logins', false), ('uploads', false),
       ('integrations', false), ('maintenance', false)
ON CONFLICT (scope) DO NOTHING;

-- O histórico é prova: não se corrige, acrescenta-se.
DROP TRIGGER IF EXISTS trg_kill_switch_append_only ON kill_switch_events;
CREATE TRIGGER trg_kill_switch_append_only
  BEFORE UPDATE OR DELETE ON kill_switch_events
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

-- O estado deriva do histórico. Um gatilho, não N chamadores: é o que garante que não exista
-- caminho de código capaz de ligar o interruptor sem deixar o evento correspondente.
-- SECURITY DEFINER: o gatilho escreve `kill_switch_state`, que a aplicação não pode escrever. É o
-- que garante que o estado seja SEMPRE derivado do histórico, nunca escrito por fora dele.
CREATE OR REPLACE FUNCTION kill_switch_apply() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
  IF NEW.action = 'engage' THEN
    UPDATE kill_switch_state
       SET engaged = true, reason = NEW.reason, actor_user_id = NEW.actor_user_id,
           since = coalesce(since, NEW.created_at), updated_at = NEW.created_at
     WHERE scope = NEW.scope;
  ELSE
    UPDATE kill_switch_state
       SET engaged = false, reason = NULL, actor_user_id = NEW.actor_user_id,
           since = NULL, updated_at = NEW.created_at
     WHERE scope = NEW.scope;
  END IF;
  RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_kill_switch_apply ON kill_switch_events;
CREATE TRIGGER trg_kill_switch_apply AFTER INSERT ON kill_switch_events
  FOR EACH ROW EXECUTE FUNCTION kill_switch_apply();

ALTER TABLE kill_switch_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE kill_switch_state ENABLE ROW LEVEL SECURITY;

-- Leitura do ESTADO é aberta a qualquer sessão autenticada: o produto precisa poder dizer ao
-- usuário "a plataforma está em manutenção" em vez de devolver erro sem explicação. O MOTIVO não
-- vai nessa leitura (ver `core/killswitch.py`): motivo de incidente é informação de operação.
CREATE POLICY ks_state_read ON kill_switch_state FOR SELECT
  USING (app_system() OR app_authenticated() OR app_priv());
CREATE POLICY ks_state_write ON kill_switch_state FOR UPDATE
  USING (app_system()) WITH CHECK (app_system());

-- O HISTÓRICO do incidente é só para quem audita ou opera.
CREATE POLICY ks_events_read ON kill_switch_events FOR SELECT
  USING (app_system() OR app_priv());
CREATE POLICY ks_events_write ON kill_switch_events FOR INSERT
  WITH CHECK (app_system());

CREATE INDEX IF NOT EXISTS ix_kill_switch_events_recent ON kill_switch_events (created_at DESC);

-- Permissão nova: acionar o interruptor é operação de super-administrador, com motivo obrigatório.
INSERT INTO permission_catalog (permission, domain, verb, description, super_admin_only, only_reason)
VALUES ('security.kill_switch', 'security', 'execute',
        'Aciona e libera o interruptor de emergência. Bloqueia escrita, login, upload ou integração durante um incidente; nunca bloqueia a auditoria.',
        true,
        'Desligar a plataforma é a operação mais destrutiva disponível sem acesso ao banco: interrompe o trabalho de todas as organizações ao mesmo tempo. Fica com o papel mais alto e exige reautenticação, como as outras operações de super-administrador.')
ON CONFLICT (permission) DO NOTHING;

-- NÃO há linha em `staff_permissions` para esta permissão, e isso é deliberado: `super_admin`
-- implica todas as permissões e não aparece na matriz (ver `GET /v1/admin/permissions` e
-- `PermissionMatrixIsDataTests`). Uma lista explícita esqueceria a permissão criada no mês
-- seguinte — foi exatamente o que a primeira versão desta migração fez, e o teste da matriz
-- reprovou. Nenhum outro papel recebe esta permissão: parar a plataforma é só do papel mais alto.

-- Privilégios. Não há `ALTER DEFAULT PRIVILEGES` nesta base de propósito: cada tabela nova declara
-- o que a aplicação pode fazer com ela, e a RLS decide quem. Aqui a aplicação LÊ o estado (em toda
-- requisição) e ESCREVE o histórico; o estado em si ela não escreve — só o gatilho, que roda como
-- dono da função. É isso que torna impossível parar a plataforma sem deixar o evento.
GRANT SELECT ON kill_switch_state TO impacto_app;
GRANT SELECT, INSERT ON kill_switch_events TO impacto_app;
GRANT USAGE, SELECT ON SEQUENCE kill_switch_events_id_seq TO impacto_app;
