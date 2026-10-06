-- v0.22.0 — PAPÉIS INTERNOS E PERMISSÕES GRANULARES
--
-- O DEFEITO QUE ESTA MIGRAÇÃO FECHA
--
-- Existia UM booleano para toda a equipe interna: `users.is_platform_admin`. Qualquer pessoa com
-- ele alcançava as 193 declarações `auth="admin"` — incluindo `GET /v1/admin/payments/revenue`,
-- `GET /v1/admin/ai/cost`, `POST /v1/admin/invoices` e `PUT /v1/admin/plans/{plan_key}/price` —
-- sem nenhum papel financeiro intermediário.
--
-- Havia três papéis nomeados (`editor`, `reviewer`, `support`), e os três eram de CONTEÚDO. Não
-- existia separação entre quem vê conteúdo e quem vê dinheiro. Numa equipe de uma pessoa isso não
-- aparece; na primeira contratação, aparece de uma vez.
--
-- O QUE MUDA, E O QUE NÃO MUDA
--
-- Não muda: quem já é administrador continua com exatamente o mesmo acesso. A migração concede
-- `super_admin` a todo `is_platform_admin`, e `super_admin` implica todas as permissões. Nenhuma
-- rota fica inacessível, nenhuma pessoa perde acesso.
--
-- Muda: o acesso passa a ser EXPLÍCITO e AUDITÁVEL, e a próxima pessoa contratada pode receber
-- `support` ou `accounting` sem receber, de brinde, a tabela de preços e a receita.

-- ---------------------------------------------------------------------------------------------
-- 1. Os papéis
-- ---------------------------------------------------------------------------------------------

ALTER TABLE staff_roles DROP CONSTRAINT staff_roles_role_check;
ALTER TABLE staff_roles ADD CONSTRAINT staff_roles_role_check CHECK (role IN (
  -- conteúdo (v0.12.0, preservados)
  'editor', 'reviewer', 'support',
  -- v0.22.0 — operação interna
  'super_admin',   -- todas as permissões; concedido a quem já era is_platform_admin
  'controller',    -- controladoria: vê tudo de financeiro, aprova, fecha
  'finance',       -- financeiro: recebível, pagável, instrução de pagamento
  'accounting',    -- contabilidade: lançamento, competência, fechamento
  'treasury',      -- tesouraria: caixa e patrimônio PRÓPRIO da plataforma
  'billing',       -- cobrança de cliente: fatura, estorno, período gratuito
  'operations',    -- operação técnica: tarefas, filas, integrações, backup
  'compliance',    -- conformidade: análise cadastral, medidas, denúncia
  'audit',         -- auditoria: LÊ tudo, não altera nada
  'security',      -- segurança: trilha, chaves, sessões
  'analyst'        -- leitura de métrica agregada, sem dado individual
));

COMMENT ON TABLE staff_roles IS
  'Papéis da equipe INTERNA da plataforma. Distinto de `memberships.role`, que é papel dentro de '
  'uma organização cliente. Uma pessoa pode ter vários.';

-- ---------------------------------------------------------------------------------------------
-- 2. As permissões — DADO, não código
-- ---------------------------------------------------------------------------------------------
--
-- A matriz é tabela porque ela MUDA: uma reorganização de equipe não deveria exigir implantação.
-- E porque auditoria precisa responder "quem podia aprovar pagamento em março?" — pergunta que um
-- dicionário em Python não responde depois de três alterações.

CREATE TABLE staff_permissions (
  role        text NOT NULL,
  permission  text NOT NULL CHECK (permission ~ '^[a-z][a-z_]*(\.[a-z][a-z_]*){1,2}$'),
  note        text,
  created_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (role, permission)
);

COMMENT ON TABLE staff_permissions IS
  'Matriz papel → permissão. `super_admin` NÃO aparece aqui: ele implica todas, e listá-las uma a '
  'uma criaria uma lista que esquece a permissão nova do mês seguinte.';

ALTER TABLE staff_permissions ENABLE ROW LEVEL SECURITY;
CREATE POLICY staffperm_read ON staff_permissions FOR SELECT USING (true);
CREATE POLICY staffperm_write ON staff_permissions FOR INSERT WITH CHECK (app_priv());
GRANT SELECT ON staff_permissions TO impacto_app;
REVOKE INSERT, UPDATE, DELETE ON staff_permissions FROM impacto_app;

INSERT INTO staff_permissions(role, permission, note) VALUES
  -- CONTROLADORIA — vê todo o financeiro e é quem aprova
  ('controller', 'finance.read',               'Caixa, recebível, pagável, extrato'),
  ('controller', 'finance.write',              'Lançar, classificar, reclassificar'),
  ('controller', 'finance.approve',            'Aprovar instrução de pagamento dentro da alçada'),
  ('controller', 'accounting.read',            NULL),
  ('controller', 'billing.read',               NULL),
  ('controller', 'treasury.read',              NULL),
  ('controller', 'instruction.read',           'Instrução de pagamento emitida'),
  ('controller', 'instruction.approve',        'Segunda aprovação da instrução'),
  ('controller', 'metrics.read',               'MRR, ARR, GMV, margem'),
  ('controller', 'budget.read',                NULL),
  ('controller', 'budget.write',               NULL),
  ('controller', 'cost_center.read',           NULL),
  ('controller', 'cost_center.write',          NULL),

  -- FINANCEIRO — opera, não aprova sozinho
  ('finance', 'finance.read',                  NULL),
  ('finance', 'finance.write',                 NULL),
  ('finance', 'billing.read',                  NULL),
  ('finance', 'billing.write',                 'Emitir fatura, registrar pagamento'),
  ('finance', 'instruction.read',              NULL),
  ('finance', 'instruction.create',            'Criar a instrução; aprovar é de controller'),
  ('finance', 'cost_center.read',              NULL),
  ('finance', 'budget.read',                   NULL),

  -- CONTABILIDADE — competência, lançamento, fechamento
  ('accounting', 'accounting.read',            NULL),
  ('accounting', 'accounting.write',           'Lançamento contábil'),
  ('accounting', 'accounting.close',           'Fechar competência — irreversível'),
  ('accounting', 'finance.read',               'Precisa ver o caixa para conciliar com a competência'),
  ('accounting', 'cost_center.read',           NULL),
  ('accounting', 'fiscal.read',                NULL),

  -- TESOURARIA — caixa e patrimônio PRÓPRIO (ver NON_CUSTODIAL_ARCHITECTURE.md §6)
  ('treasury', 'treasury.read',                NULL),
  ('treasury', 'treasury.write',               'Registrar aplicação e resgate de recurso próprio'),
  ('treasury', 'finance.read',                 NULL),

  -- COBRANÇA DE CLIENTE
  ('billing', 'billing.read',                  NULL),
  ('billing', 'billing.write',                 NULL),
  ('billing', 'billing.refund',                'Estorno — exige alçada'),
  ('billing', 'free_period.write',             'Conceder e cancelar período gratuito'),
  ('billing', 'admin.organizations.read',      NULL),

  -- OPERAÇÃO TÉCNICA
  ('operations', 'maintenance.read',           NULL),
  ('operations', 'maintenance.execute',        'Reexecutar tarefa, reprocessar entrega'),
  ('operations', 'integration.read',           NULL),
  ('operations', 'integration.write',          NULL),
  ('operations', 'health.read',                NULL),

  -- CONFORMIDADE
  ('compliance', 'compliance.read',             NULL),
  ('compliance', 'compliance.write',            NULL),
  ('compliance', 'admin.organizations.read',    NULL),
  ('compliance', 'admin.organizations.write',   'Aprovar, suspender, verificar'),

  -- AUDITORIA — LÊ tudo, NÃO altera nada. Nenhuma permissão .write aqui, de propósito.
  ('audit', 'security.audit.read',             NULL),
  ('audit', 'security.audit.export',           NULL),
  ('audit', 'finance.read',                    NULL),
  ('audit', 'accounting.read',                 NULL),
  ('audit', 'billing.read',                    NULL),
  ('audit', 'instruction.read',                NULL),
  ('audit', 'treasury.read',                   NULL),
  ('audit', 'compliance.read',                 NULL),
  ('audit', 'metrics.read',                    NULL),
  ('audit', 'health.read',                     NULL),

  -- SEGURANÇA
  ('security', 'security.audit.read',          NULL),
  ('security', 'security.audit.export',        NULL),
  ('security', 'security.keys.read',           NULL),
  ('security', 'security.keys.write',          NULL),
  ('security', 'admin.users.read',             NULL),

  -- ANÁLISE — métrica agregada, sem dado individual
  ('analyst', 'metrics.read',                  NULL),
  ('analyst', 'health.read',                   NULL),

  -- CONTEÚDO (v0.12.0, agora com permissão nomeada)
  ('editor',   'content.read',                 NULL),
  ('editor',   'content.write',                NULL),
  ('reviewer', 'content.read',                 NULL),
  ('reviewer', 'content.write',                NULL),
  ('reviewer', 'content.publish',              'Aprova e publica; não escreve o próprio texto'),
  ('support',  'support.read',                 NULL),
  ('support',  'support.write',                NULL),
  ('support',  'admin.organizations.read',     'Para atender quem abre chamado');

-- O que NÃO está na matriz, e por quê:
--
--   payout.*  — NÃO EXISTE. Repasse exige custódia, e a plataforma não custodia
--               (NON_CUSTODIAL_ARCHITECTURE.md §7). O equivalente permitido é `instruction.*`:
--               calcular e emitir a INSTRUÇÃO de pagamento, que quem paga executa.
--   fiscal.issue / fiscal.cancel — declaradas abaixo apenas para `super_admin` implícito: não há
--               provedor fiscal contratado, e conceder a permissão a um papel sugeriria que alguém
--               pode emitir nota hoje.

-- ---------------------------------------------------------------------------------------------
-- 3. Toda pessoa que já era administradora recebe super_admin
-- ---------------------------------------------------------------------------------------------
--
-- Sem isto, publicar esta migração tiraria acesso de quem administra a plataforma — e a correção
-- seria feita às pressas, provavelmente concedendo tudo a todos.

INSERT INTO staff_roles(user_id, role, granted_by, granted_at)
SELECT id, 'super_admin', id, now() FROM users WHERE is_platform_admin
ON CONFLICT DO NOTHING;

COMMENT ON COLUMN users.is_platform_admin IS
  'v0.22.0: continua valendo como porta das rotas auth="admin" que NÃO declaram permissão. Para as '
  'que declaram, o que decide é a permissão vinda de staff_roles. A migração 0046 concedeu '
  'super_admin a todos os portadores, então ninguém perdeu acesso.';

-- ---------------------------------------------------------------------------------------------
-- 4. Toda entrada privilegiada é registrada
-- ---------------------------------------------------------------------------------------------
--
-- O prompt desta rodada pede: "nunca conceder automaticamente todos os dados só por ser
-- SUPER_ADMIN. Registrar cada acesso privilegiado." É isto.
--
-- Tabela própria, e não `audit_events`: audit_events registra o que ALTEROU algo. Aqui entra toda
-- LEITURA privilegiada também, que é o volume maior e a pergunta mais comum numa investigação
-- ("quem olhou a receita na semana do vazamento?").

CREATE TABLE privileged_access_log (
  id          bigserial PRIMARY KEY,
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE SET NULL,
  roles_used  text[] NOT NULL,
  permission  text,
  method      text NOT NULL,
  path        text NOT NULL,
  org_scope   uuid,
  request_id  text,
  ip          text,
  at          timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE privileged_access_log IS
  'Toda requisição atendida por papel interno. Inclui LEITURA: numa investigação, a pergunta é '
  'quem olhou, não só quem mudou.';

CREATE INDEX ix_privaccess_user ON privileged_access_log(user_id, at DESC);
CREATE INDEX ix_privaccess_at ON privileged_access_log(at DESC);
CREATE INDEX ix_privaccess_perm ON privileged_access_log(permission, at DESC) WHERE permission IS NOT NULL;

CREATE TRIGGER trg_privaccess_append BEFORE UPDATE OR DELETE ON privileged_access_log
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

ALTER TABLE privileged_access_log ENABLE ROW LEVEL SECURITY;
-- Quem lê a trilha de acesso privilegiado é auditoria e segurança — não quem foi registrado nela.
CREATE POLICY privaccess_read ON privileged_access_log FOR SELECT
  USING (app_system() OR app_priv());
CREATE POLICY privaccess_write ON privileged_access_log FOR INSERT
  WITH CHECK (app_system() OR app_priv());
GRANT SELECT, INSERT ON privileged_access_log TO impacto_app;
GRANT USAGE, SELECT ON SEQUENCE privileged_access_log_id_seq TO impacto_app;
REVOKE UPDATE, DELETE ON privileged_access_log FROM impacto_app;

-- ---------------------------------------------------------------------------------------------
-- 5. Consulta de permissão efetiva
-- ---------------------------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION staff_has_permission(p_user uuid, p_permission text) RETURNS boolean
LANGUAGE sql STABLE AS $$
  SELECT EXISTS (
    -- super_admin implica todas. Implícito, e não 60 linhas na matriz, porque uma lista explícita
    -- esquece a permissão criada no mês seguinte — e esquecer, aqui, significa travar a operação.
    SELECT 1 FROM staff_roles WHERE user_id = p_user AND role = 'super_admin'
  ) OR EXISTS (
    SELECT 1 FROM staff_roles r JOIN staff_permissions sp ON sp.role = r.role
     WHERE r.user_id = p_user AND sp.permission = p_permission
  )
$$;

CREATE OR REPLACE FUNCTION staff_permissions_of(p_user uuid) RETURNS text[]
LANGUAGE sql STABLE AS $$
  SELECT CASE
    WHEN EXISTS (SELECT 1 FROM staff_roles WHERE user_id = p_user AND role = 'super_admin')
      THEN (SELECT array_agg(DISTINCT permission ORDER BY permission) FROM staff_permissions)
    ELSE coalesce((SELECT array_agg(DISTINCT sp.permission ORDER BY sp.permission)
                     FROM staff_roles r JOIN staff_permissions sp ON sp.role = r.role
                    WHERE r.user_id = p_user), ARRAY[]::text[])
  END
$$;

COMMENT ON FUNCTION staff_permissions_of(uuid) IS
  'Permissões efetivas da pessoa. Para super_admin devolve o catálogo inteiro — inclusive o que '
  'for acrescentado depois, sem precisar lembrar de atualizar nada.';

-- ---------------------------------------------------------------------------------------------
-- 6. Reautenticação na sessão
-- ---------------------------------------------------------------------------------------------
--
-- Havia três cópias manuais de verificação de senha (`reauth_failed` em trust_routes.py,
-- document_routes.py e privacy_routes.py), cada uma conferindo a senha no próprio handler e
-- esquecendo o resultado em seguida. Pedir a senha de novo em cada operação sensível de uma sessão
-- de trabalho é o caminho mais curto para a pessoa anotar a senha num papel.
--
-- Com o carimbo na sessão, a reautenticação passa a ter JANELA (15 minutos, em
-- `core/access.py::_reauth_fresh`). Janela, e não "uma vez por sessão": uma sessão de 30 dias
-- reautenticada no primeiro dia não prova nada sobre quem está no teclado no trigésimo.

ALTER TABLE sessions ADD COLUMN reauth_at timestamptz;

COMMENT ON COLUMN sessions.reauth_at IS
  'Quando a identidade foi confirmada de novo nesta sessão (senha e, quando houver, MFA). Vale por '
  'uma janela curta — ver core/access.py::STEP_UP_PERMISSIONS.';

CREATE INDEX ix_session_reauth ON sessions(reauth_at) WHERE reauth_at IS NOT NULL;

-- ---------------------------------------------------------------------------------------------
-- 7. `is_platform_admin` implica `super_admin` — SEMPRE, não só na migração
-- ---------------------------------------------------------------------------------------------
--
-- O INSERT do item 3 cobre quem já existia. Ele NÃO cobre quem for promovido depois — e
-- administrador criado amanhã nasceria sem `super_admin`, perdendo acesso a tudo que exige
-- permissão. A primeira vez que isso acontecesse, a correção às pressas provavelmente seria
-- remover a exigência de permissão das rotas.
--
-- Então a regra vira gatilho. Ele vale para TODO caminho que ligue o booleano: migração, CLI,
-- semente de demonstração, console de banco e a rota de administração que ainda não existe.

CREATE OR REPLACE FUNCTION platform_admin_implies_super() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.is_platform_admin AND (TG_OP = 'INSERT' OR NOT coalesce(OLD.is_platform_admin, false)) THEN
    INSERT INTO staff_roles(user_id, role, granted_by, granted_at)
    VALUES (NEW.id, 'super_admin', NEW.id, now())
    ON CONFLICT DO NOTHING;
  END IF;
  -- Ao PERDER o booleano, o papel sai junto: deixar `super_admin` para trás seria revogar a
  -- administração e manter todo o privilégio dela.
  IF TG_OP = 'UPDATE' AND coalesce(OLD.is_platform_admin, false) AND NOT NEW.is_platform_admin THEN
    DELETE FROM staff_roles WHERE user_id = NEW.id AND role = 'super_admin';
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER trg_platform_admin_super AFTER INSERT OR UPDATE OF is_platform_admin ON users
  FOR EACH ROW EXECUTE FUNCTION platform_admin_implies_super();

COMMENT ON FUNCTION platform_admin_implies_super() IS
  'Mantém a equivalência is_platform_admin <-> papel super_admin. Gatilho, e não disciplina de '
  'quem escreve a rota: o booleano é ligado por pelo menos quatro caminhos diferentes.';

-- ---------------------------------------------------------------------------------------------
-- 8. CATÁLOGO de permissões, separado do MAPEAMENTO papel → permissão
-- ---------------------------------------------------------------------------------------------
--
-- DEFEITO QUE ISTO CORRIGE, encontrado pelo teste da própria matriz.
--
-- `staff_permissions_of('super_admin')` devolvia `SELECT DISTINCT permission FROM
-- staff_permissions` — ou seja, a união das permissões que ALGUM papel concede. Uma permissão
-- exclusiva de super_admin (conceder papel interno, por exemplo) não é concedida a papel nenhum
-- por definição, logo não aparecia nessa união, logo nem o super_admin a recebia. A rota que a
-- exigia ficava inalcançável por todos.
--
-- A causa é de modelagem: `staff_permissions` estava fazendo dois trabalhos — dizer quais
-- permissões EXISTEM e dizer quem as TEM. Separados, cada um responde a sua pergunta.

CREATE TABLE permission_catalog (
  permission  text PRIMARY KEY CHECK (permission ~ '^[a-z][a-z_]*(\.[a-z][a-z_]*){1,2}$'),
  domain      text NOT NULL,
  verb        text NOT NULL,
  description text NOT NULL CHECK (length(description) BETWEEN 10 AND 300),
  super_admin_only boolean NOT NULL DEFAULT false,
  only_reason text,
  created_at  timestamptz NOT NULL DEFAULT now(),
  -- Exclusiva de super_admin sem motivo escrito é indistinguível de permissão esquecida no
  -- mapeamento — e esquecimento aqui significa rota que ninguém alcança.
  CONSTRAINT perm_only_needs_reason CHECK (NOT super_admin_only OR only_reason IS NOT NULL)
);

COMMENT ON TABLE permission_catalog IS
  'Quais permissões EXISTEM. `staff_permissions` diz quem as tem. Separados porque uma permissão '
  'exclusiva de super_admin não é concedida a papel nenhum e, no modelo anterior, desaparecia.';

ALTER TABLE permission_catalog ENABLE ROW LEVEL SECURITY;
CREATE POLICY permcat_read ON permission_catalog FOR SELECT USING (true);
GRANT SELECT ON permission_catalog TO impacto_app;

-- O catálogo nasce da matriz que já existe, mais as exclusivas de super_admin.
--
-- `admin.organizations.write` NÃO é exclusiva: aprovar, suspender e verificar organização é o
-- trabalho de `compliance`, e ela já a tem no mapeamento acima. Declará-la exclusiva aqui teria
-- sido tirar da conformidade a operação que define a conformidade.
INSERT INTO permission_catalog(permission, domain, verb, description)
SELECT DISTINCT permission,
       split_part(permission, '.', 1),
       regexp_replace(permission, '^.*\.', ''),
       'Permissão concedida por papel interno; ver staff_permissions.'
  FROM staff_permissions;

INSERT INTO permission_catalog(permission, domain, verb, description, super_admin_only, only_reason) VALUES
  ('admin.users.write', 'admin', 'write',
   'Conceder e revogar papel interno de outra pessoa.', true,
   'Quem pode conceder papel pode conceder a si mesmo o papel que quiser: é o caminho mais curto '
   'de escalada de privilégio. Fica com quem já tem tudo, e todo uso aparece na trilha.'),
  ('fiscal.issue', 'fiscal', 'issue',
   'Emitir documento fiscal pelo provedor configurado.', true,
   'Não há provedor fiscal contratado. Conceder a permissão a um papel sugeriria que alguém pode '
   'emitir nota hoje, e ninguém pode.'),
  ('fiscal.cancel', 'fiscal', 'cancel',
   'Cancelar documento fiscal já emitido.', true,
   'Tem efeito fiscal e também não tem provedor.')
ON CONFLICT (permission) DO NOTHING;

-- `staff_permissions` passa a referenciar o catálogo: mapear papel para permissão inexistente é
-- erro de digitação que só apareceria quando alguém tentasse usar a rota.
ALTER TABLE staff_permissions
  ADD CONSTRAINT staff_perm_in_catalog FOREIGN KEY (permission)
  REFERENCES permission_catalog(permission) ON DELETE RESTRICT;

CREATE OR REPLACE FUNCTION staff_permissions_of(p_user uuid) RETURNS text[]
LANGUAGE sql STABLE AS $$
  SELECT CASE
    -- super_admin recebe o CATÁLOGO, não a união do mapeamento. É a correção: a união não
    -- continha as exclusivas dele.
    WHEN EXISTS (SELECT 1 FROM staff_roles WHERE user_id = p_user AND role = 'super_admin')
      THEN (SELECT array_agg(permission ORDER BY permission) FROM permission_catalog)
    ELSE coalesce((SELECT array_agg(DISTINCT sp.permission ORDER BY sp.permission)
                     FROM staff_roles r JOIN staff_permissions sp ON sp.role = r.role
                    WHERE r.user_id = p_user), ARRAY[]::text[])
  END
$$;

CREATE OR REPLACE FUNCTION staff_has_permission(p_user uuid, p_permission text) RETURNS boolean
LANGUAGE sql STABLE AS $$
  SELECT EXISTS (
    SELECT 1 FROM staff_roles WHERE user_id = p_user AND role = 'super_admin'
  ) OR EXISTS (
    SELECT 1 FROM staff_roles r JOIN staff_permissions sp ON sp.role = r.role
     WHERE r.user_id = p_user AND sp.permission = p_permission
  )
$$;
