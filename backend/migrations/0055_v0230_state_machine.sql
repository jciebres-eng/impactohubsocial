-- v0.23.0 — MÁQUINA DE ESTADOS DA CANDIDATURA NO BANCO
--
-- O QUE EXISTIA E O QUE FALTAVA
--
-- A máquina de estados existe desde a v0.13.0, em Python, nas tabelas `PLATFORM` e `EXTERNAL` de
-- `services/workflow.py`, e é conferida em `transition()`: transição fora do grafo devolve 409
-- `invalid_transition`, e cada aresta diz de quem é a vez (`osc`, `funder`, `any`).
--
-- O que faltava é o que o prompt desta rodada pede: **a validação no BACKEND, no sentido de que
-- nenhum caminho a contorne**. A conferência em Python protege UMA rota. Um `UPDATE applications
-- SET status = 'closed'` vindo de outra rota, de um script de operação ou de uma rota futura
-- escrita sem lembrar da regra passava direto — e `rascunho → encerrada` é exatamente o estado
-- impossível que o prompt nomeia.
--
-- UMA FONTE DE VERDADE, DUAS CÓPIAS CONFERIDAS
--
-- O grafo abaixo é a MESMA coisa que as tabelas Python, não uma segunda regra. Migração não importa
-- Python, então a cópia existe — e `TheGraphInTheDatabaseIsTheGraphInTheCodeTests` reprova se as
-- duas divergirem em uma aresta. É o mesmo arranjo usado para o menu e as permissões na v0.22.0:
-- duplicar é aceitável quando um teste prova que as duas cópias são iguais.

CREATE TABLE IF NOT EXISTS application_status_graph (
  origin      text NOT NULL CHECK (origin IN ('osc_application','funder_interest','external_tracking')),
  from_status text NOT NULL,
  to_status   text NOT NULL,
  side        text NOT NULL CHECK (side IN ('osc','funder','any')),
  note        text,
  PRIMARY KEY (origin, from_status, to_status)
);

-- Fluxo da plataforma. `osc_application` e `funder_interest` percorrem o mesmo grafo; o que muda
-- entre eles é o estado inicial (`draft` e `interest`), não as arestas.
INSERT INTO application_status_graph (origin, from_status, to_status, side, note) VALUES
  ('osc_application','draft','submitted','osc',NULL),
  ('osc_application','draft','withdrawn','osc',NULL),
  ('osc_application','interest','due_diligence','osc',NULL),
  ('osc_application','interest','withdrawn','any',NULL),
  ('osc_application','submitted','screening','funder',NULL),
  ('osc_application','submitted','rejected','funder',NULL),
  ('osc_application','submitted','withdrawn','osc',NULL),
  ('osc_application','screening','due_diligence','funder',NULL),
  ('osc_application','screening','rejected','funder',NULL),
  ('osc_application','screening','withdrawn','osc',NULL),
  ('osc_application','due_diligence','approved','funder',NULL),
  ('osc_application','due_diligence','rejected','funder',NULL),
  ('osc_application','due_diligence','withdrawn','osc',NULL),
  ('osc_application','approved','rejected','funder',NULL),
  ('osc_application','committed','in_execution','osc',NULL),
  ('osc_application','in_execution','reporting','osc',NULL),
  ('osc_application','reporting','closed','funder',NULL),
  ('osc_application','reporting','in_execution','funder',NULL),
  -- Esta aresta NÃO está em `PLATFORM` e isso é correto: ela não passa pela rota genérica de
  -- transição. `POST /v1/applications/{id}/commitments` a executa ao registrar o aporte, chamando
  -- `workflow.record_transition()` antes do UPDATE. O teste de equivalência a declara como exceção.
  ('osc_application','approved','committed','funder',
   'executada por POST /v1/applications/{id}/commitments, não pela rota genérica de transição')
ON CONFLICT DO NOTHING;

INSERT INTO application_status_graph (origin, from_status, to_status, side, note)
SELECT 'funder_interest', from_status, to_status, side, note
  FROM application_status_graph WHERE origin = 'osc_application'
ON CONFLICT DO NOTHING;

-- Edital externo: a OSC acompanha o próprio processo, então toda aresta é dela.
INSERT INTO application_status_graph (origin, from_status, to_status, side, note) VALUES
  ('external_tracking','draft','submitted','osc',NULL),
  ('external_tracking','draft','withdrawn','osc',NULL),
  ('external_tracking','submitted','approved','osc',NULL),
  ('external_tracking','submitted','rejected','osc',NULL),
  ('external_tracking','submitted','withdrawn','osc',NULL),
  ('external_tracking','approved','in_execution','osc',NULL),
  ('external_tracking','in_execution','reporting','osc',NULL),
  ('external_tracking','reporting','closed','osc',NULL)
ON CONFLICT DO NOTHING;

CREATE OR REPLACE FUNCTION application_status_follows_the_graph() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE permitidos text;
BEGIN
  IF TG_OP = 'INSERT' THEN
    -- Estado inicial. Nascer em 'approved' pularia o processo inteiro sem deixar transição.
    IF NEW.status NOT IN ('draft','interest') THEN
      RAISE EXCEPTION 'candidatura nasce em rascunho ou interesse, nunca em %', NEW.status
        USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
  END IF;

  IF NEW.status = OLD.status THEN RETURN NEW; END IF;

  IF NOT EXISTS (SELECT 1 FROM application_status_graph g
                  WHERE g.origin = NEW.origin AND g.from_status = OLD.status
                    AND g.to_status = NEW.status) THEN
    SELECT coalesce(string_agg(g.to_status, ', ' ORDER BY g.to_status), 'nenhuma (estado terminal)')
      INTO permitidos
      FROM application_status_graph g
     WHERE g.origin = NEW.origin AND g.from_status = OLD.status;
    RAISE EXCEPTION 'transição de candidatura não permitida: % → % (origem %). Permitidas: %',
      OLD.status, NEW.status, NEW.origin, permitidos USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_application_status_graph ON applications;
CREATE TRIGGER trg_application_status_graph
  BEFORE INSERT OR UPDATE OF status ON applications
  FOR EACH ROW EXECUTE FUNCTION application_status_follows_the_graph();

ALTER TABLE application_status_graph ENABLE ROW LEVEL SECURITY;
-- Leitura aberta a sessão autenticada: o produto mostra "próximos passos possíveis" na tela da
-- candidatura, e esconder o grafo faria a interface adivinhar o que o banco já sabe.
CREATE POLICY appgraph_read ON application_status_graph FOR SELECT
  USING (app_system() OR app_authenticated() OR app_priv());

GRANT SELECT ON application_status_graph TO impacto_app;
