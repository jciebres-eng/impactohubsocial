-- v0.23.0 — a sessão passa a ter IDADE MÁXIMA e INATIVIDADE; o código TOTP deixa de servir duas vezes.
--
-- TRÊS DEFEITOS, TODOS ENCONTRADOS POR AUDITORIA
--
-- S1 — SEM TIMEOUT ABSOLUTO. `issue_session()` grava `refresh_expires_at = now() + 30 dias` a cada
-- rotação, inclusive nas rotações da MESMA família. O efeito é que um refresh token roubado e
-- renovado dentro da janela sobrevive INDEFINIDAMENTE: 30 dias contados sempre do último uso nunca
-- vencem para quem está usando. Só senha trocada, reset, logout global ou detecção de reuso o
-- encerravam. A idade da FAMÍLIA é o que precisa vencer, não a da linha.
--
-- S2 — SEM TIMEOUT DE INATIVIDADE. `sessions.last_seen_at` era escrito a cada minuto e NUNCA lido
-- para expirar nada. Sessão esquecida em máquina compartilhada valia 30 dias.
--
-- S3 — REPLAY DO CÓDIGO TOTP. `security/totp.py::verify()` devolve o contador aceito, com o
-- comentário "para impedir reuso" — e nenhum dos quatro chamadores guardava esse contador. Com
-- janela de ±1 passo, o mesmo código de 6 dígitos valia cerca de 90 segundos e podia ser usado mais
-- de uma vez. Quem lê o código por cima do ombro, ou o intercepta numa página falsa, o usa de novo.

-- 1) A família de sessão ganha nascimento próprio. É ele que vence.
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS family_started_at timestamptz;

-- Famílias existentes herdam a data da sessão mais antiga da família — e não `now()`, porque isso
-- daria 30 dias novos a toda sessão em curso no momento da migração.
UPDATE sessions s SET family_started_at = f.inicio
  FROM (SELECT family_id, min(created_at) AS inicio FROM sessions GROUP BY family_id) f
 WHERE s.family_id = f.family_id AND s.family_started_at IS NULL;

ALTER TABLE sessions ALTER COLUMN family_started_at SET DEFAULT now();
UPDATE sessions SET family_started_at = created_at WHERE family_started_at IS NULL;
ALTER TABLE sessions ALTER COLUMN family_started_at SET NOT NULL;

CREATE INDEX IF NOT EXISTS ix_sessions_family_age ON sessions (family_id, family_started_at);

COMMENT ON COLUMN sessions.family_started_at IS
  'Nascimento da FAMÍLIA de sessão, propagado em cada rotação. A idade máxima conta daqui, não de '
  'created_at da linha: contar da linha renovava a validade a cada uso e a sessão nunca vencia.';

-- 2) O contador do último código TOTP aceito, para que ele não sirva duas vezes.
ALTER TABLE users ADD COLUMN IF NOT EXISTS mfa_last_counter bigint;

COMMENT ON COLUMN users.mfa_last_counter IS
  'Contador de passo do último código TOTP aceito. Um código com contador menor ou igual é '
  'recusado como reuso. Zerado ao desligar o MFA, para que religar não herde a trava.';

-- 3) A trava é do BANCO, não da aplicação: o avanço do contador é monotônico por restrição.
--    Uma segunda via de verificação que esquecesse de gravar o contador não quebraria a trava —
--    ela não conseguiria regredir o valor nem por engano.
CREATE OR REPLACE FUNCTION totp_counter_moves_forward() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.mfa_last_counter IS NOT NULL AND OLD.mfa_last_counter IS NOT NULL
     AND NEW.mfa_last_counter < OLD.mfa_last_counter
     -- Desligar o MFA zera (NULL) e é o único caminho de volta; está coberto pelo IS NOT NULL.
     AND NEW.mfa_enabled_at IS NOT NULL THEN
    RAISE EXCEPTION 'contador de TOTP não retrocede: aceitar um código já usado é permitir reuso'
      USING ERRCODE = '42501';
  END IF;
  RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_totp_counter ON users;
CREATE TRIGGER trg_totp_counter BEFORE UPDATE OF mfa_last_counter ON users
  FOR EACH ROW EXECUTE FUNCTION totp_counter_moves_forward();
