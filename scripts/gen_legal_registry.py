#!/usr/bin/env python3
"""Gera a migração do registro de documentos legais a partir de `docs/legal/*.md`.

Por que gerar em vez de digitar: o texto que o usuário aceita e o texto que está no repositório têm de
ser o MESMO texto. Digitar o contrato duas vezes é garantir que um dia os dois divirjam e que ninguém
descubra qual foi aceito. Aqui o arquivo é a fonte; o banco guarda o texto e o sha256 dele; e há teste
que recalcula o sha256 dos arquivos e compara com o banco.

Uso: python3 scripts/gen_legal_registry.py [--check]
"""
from __future__ import annotations

import hashlib
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
LEGAL = ROOT / "docs" / "legal"
OUT = ROOT / "backend" / "migrations" / "0023_v0170_legal.sql"

# (chave, arquivo, título, resumo, público, exige aceite)
DOCS: list[tuple[str, str, str, str, str, bool]] = [
    ("terms_of_use", "TERMS_OF_USE.md", "Termos de Uso",
     "Regras gerais de uso da Plataforma por qualquer pessoa ou organização.", "all", True),
    ("privacy_policy", "PRIVACY_POLICY.md", "Política de Privacidade",
     "Quais dados são tratados, com que base legal, por quanto tempo e quais são os direitos do titular.",
     "all", True),
    ("cookies", "COOKIES.md", "Política de Cookies",
     "Cookies e armazenamentos usados — todos estritamente necessários ao funcionamento.", "all", False),
    ("subscription", "SUBSCRIPTION.md", "Contrato de Assinatura (SaaS)",
     "Plano, preço, reajuste, vigência e encerramento da assinatura. Declara o que é e permanece gratuito.",
     "all", False),
    ("marketplace", "MARKETPLACE.md", "Termos do Marketplace de Serviços",
     "Regras para anunciar e contratar serviço profissional. Declara que não há comissão ativa.",
     "provider", False),
    ("intermediation", "INTERMEDIATION.md", "Termos de Intermediação e Conexão",
     "Natureza da conexão entre organizações. Declara que a Plataforma não custodia nem processa aporte.",
     "all", False),
    ("payment", "PAYMENT.md", "Contrato de Pagamento",
     "Meios de pagamento, parcelamento à parte da assinatura, confirmação por webhook assinado. "
     "Declara que nenhum provedor está configurado.", "all", False),
    ("cancellation", "CANCELLATION.md", "Política de Cancelamento",
     "Como cancelar, qual o efeito e por que cancelar não apaga dados.", "all", False),
    ("refund", "REFUND.md", "Política de Reembolso",
     "Hipóteses de devolução, devolução parcial e prazos. Depende de parecer sobre incidência do CDC.",
     "all", False),
    ("b2b", "B2B.md", "Contrato Institucional (B2B / Enterprise / ESG)",
     "Uso institucional para gestão de portfólio de investimento social. Lista o que NÃO está incluído.",
     "company", False),
    ("b2g", "B2G.md", "Contrato com o Poder Público (B2G)",
     "Uso por órgão público em chamamento. Declara a ausência de assinatura qualificada e de integrações "
     "governamentais.", "government", False),
]

HEAD = """-- 0023_v0170_legal.sql — registro versionado de documento legal e aceite com prova
--
-- ARQUIVO GERADO por scripts/gen_legal_registry.py a partir de docs/legal/*.md. Não editar à mão: o
-- texto que o usuário aceita e o texto do repositório têm de ser o mesmo, e há teste que confere o
-- sha256 dos dois lados.
--
-- A TRAVA CENTRAL DESTA MIGRAÇÃO
--
-- Nenhuma das onze minutas foi revisada por advogado(a). Então nenhuma delas pode ser aceita: o
-- gatilho `acceptance_requires_effective()` RECUSA aceite de documento que não esteja aprovado e
-- vigente, e `legal_doc_status_guard()` recusa aprovação sem quem revisou, quando revisou e sob qual
-- referência. O efeito prático é que o produto NÃO consegue coletar aceite de minuta — que é
-- exatamente o que se quer impedir, porque "o usuário aceitou os termos" dito sobre um rascunho é
-- afirmação falsa com aparência de prova.

CREATE TABLE legal_documents (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  doc_key       text NOT NULL CHECK (doc_key ~ '^[a-z][a-z0-9_]{2,40}$'),
  version       integer NOT NULL CHECK (version > 0),
  title         text NOT NULL CHECK (length(btrim(title)) BETWEEN 3 AND 200),
  summary       text NOT NULL CHECK (length(btrim(summary)) BETWEEN 10 AND 500),
  source_path   text NOT NULL,
  body_md       text NOT NULL CHECK (length(btrim(body_md)) > 200),
  body_sha256   text NOT NULL DEFAULT '',
  audience      text NOT NULL DEFAULT 'all'
                  CHECK (audience IN ('all','osc','company','provider','government')),
  requires_acceptance boolean NOT NULL DEFAULT true,
  status        text NOT NULL DEFAULT 'draft'
                  CHECK (status IN ('draft','in_legal_review','approved','superseded')),
  reviewed_by   text,
  reviewed_at   timestamptz,
  review_reference text,
  effective_from date,
  software_version text NOT NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  created_by    uuid REFERENCES users(id) ON DELETE SET NULL,
  UNIQUE (doc_key, version),
  -- Aprovar sem dizer QUEM revisou, QUANDO e sob qual referência é o mesmo que não revisar. A regra
  -- fica aqui pelo mesmo motivo de `green_needs_evidence` nos cartões de monetização (0020).
  CONSTRAINT approved_needs_review CHECK (
    status <> 'approved' OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL
                             AND review_reference IS NOT NULL)),
  -- Vigência é consequência da aprovação, nunca antecede.
  CONSTRAINT effective_needs_approved CHECK (
    effective_from IS NULL OR status IN ('approved','superseded'))
);
COMMENT ON TABLE legal_documents IS
  'Documento legal versionado. Versão nova é LINHA nova; o texto de uma versão nunca muda, porque a '
  'prova de aceite aponta para o sha256 do texto aceito.';
COMMENT ON COLUMN legal_documents.body_sha256 IS
  'Derivado do texto por gatilho. É o que a prova de aceite guarda: sem ele, "aceitou os termos" não '
  'diz QUAIS termos.';
COMMENT ON COLUMN legal_documents.status IS
  'draft -> in_legal_review -> approved -> superseded. Só approved+vigente aceita aceite.';

CREATE UNIQUE INDEX ux_legal_current ON legal_documents(doc_key) WHERE status = 'approved';
CREATE INDEX ix_legal_docs_key ON legal_documents(doc_key, version DESC);

-- O sha256 é derivado, não informado: valor informado por quem insere pode mentir sobre o texto.
CREATE FUNCTION legal_doc_hash() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.body_sha256 := encode(digest(NEW.body_md, 'sha256'), 'hex');
  RETURN NEW;
END $$;
CREATE TRIGGER trg_legal_doc_hash BEFORE INSERT OR UPDATE ON legal_documents
  FOR EACH ROW EXECUTE FUNCTION legal_doc_hash();

-- Texto de versão existente é imutável. Correção de texto é versão nova — e é assim que o aceite de
-- ontem continua provando o que foi aceito ontem.
CREATE FUNCTION legal_doc_text_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.doc_key <> OLD.doc_key OR NEW.version <> OLD.version
     OR NEW.body_md <> OLD.body_md OR NEW.source_path <> OLD.source_path THEN
    RAISE EXCEPTION 'texto de documento legal é imutável: corrigir é publicar versão nova de %',
      OLD.doc_key USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_legal_doc_immutable BEFORE UPDATE ON legal_documents
  FOR EACH ROW EXECUTE FUNCTION legal_doc_text_immutable();

-- Situação anda para frente e só para frente, e aprovar supera a versão aprovada anterior.
CREATE FUNCTION legal_doc_status_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  v_rank jsonb := '{"draft":0,"in_legal_review":1,"approved":2,"superseded":3}'::jsonb;
BEGIN
  IF NEW.status <> OLD.status THEN
    IF (v_rank->>NEW.status)::int < (v_rank->>OLD.status)::int THEN
      RAISE EXCEPTION 'situação de documento legal não volta: % -> %', OLD.status, NEW.status
        USING ERRCODE = '23514';
    END IF;
    IF NEW.status = 'approved' THEN
      UPDATE legal_documents SET status = 'superseded'
       WHERE doc_key = NEW.doc_key AND id <> NEW.id AND status = 'approved';
      IF NEW.effective_from IS NULL THEN
        NEW.effective_from := current_date;
      END IF;
    END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_legal_doc_status BEFORE UPDATE ON legal_documents
  FOR EACH ROW EXECUTE FUNCTION legal_doc_status_guard();

-- ============================================================================ aceite
CREATE TABLE legal_acceptances (
  id           bigserial PRIMARY KEY,
  document_id  uuid NOT NULL REFERENCES legal_documents(id) ON DELETE RESTRICT,
  user_id      uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  org_id       uuid REFERENCES organizations(id) ON DELETE SET NULL,
  doc_key      text NOT NULL DEFAULT '',
  version      integer NOT NULL DEFAULT 0,
  body_sha256  text NOT NULL DEFAULT '',
  accepted_at  timestamptz NOT NULL DEFAULT now(),
  ip           text,
  user_agent   text,
  source       text NOT NULL DEFAULT 'web' CHECK (source IN ('web','mobile','api','admin_import')),
  UNIQUE (document_id, user_id)
);
COMMENT ON TABLE legal_acceptances IS
  'Prova de aceite: quem, quando, de onde, e o sha256 do texto aceito. Append-only. Coexiste com '
  '`consents` (v0.1.0), que registra consentimento por tipo e versão em texto livre e segue valendo '
  'para o fluxo de cadastro; esta tabela é a que aponta para o documento.';
CREATE INDEX ix_legal_acc_user ON legal_acceptances(user_id, accepted_at DESC);
CREATE INDEX ix_legal_acc_doc ON legal_acceptances(document_id);

-- Chave, versão e hash do aceite são COPIADOS do documento, não informados: cliente que informa o
-- hash pode informar o hash de outro texto.
CREATE FUNCTION acceptance_stamp() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  d record;
BEGIN
  SELECT doc_key, version, body_sha256, status, effective_from, title
    INTO d FROM legal_documents WHERE id = NEW.document_id;
  IF d IS NULL THEN
    RAISE EXCEPTION 'documento legal inexistente' USING ERRCODE = '23503';
  END IF;
  IF d.status <> 'approved' OR d.effective_from IS NULL OR d.effective_from > current_date THEN
    RAISE EXCEPTION 'não é possível registrar aceite de "%" v%: o documento está em "%" (MINUTA / '
                    'DRAFT FOR LEGAL REVIEW). Aceite de minuta não é prova de nada e seria afirmação '
                    'falsa com aparência de prova.', d.title, d.version, d.status
      USING ERRCODE = '23514';
  END IF;
  NEW.doc_key := d.doc_key;
  NEW.version := d.version;
  NEW.body_sha256 := d.body_sha256;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_acceptance_stamp BEFORE INSERT ON legal_acceptances
  FOR EACH ROW EXECUTE FUNCTION acceptance_stamp();
CREATE TRIGGER trg_acceptance_append BEFORE UPDATE ON legal_acceptances
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

-- ============================================================================ consultas
CREATE FUNCTION legal_pending(p_user uuid, p_audience text DEFAULT 'all')
  RETURNS TABLE (id uuid, doc_key text, version integer, title text, summary text,
                 effective_from date)
  LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT d.id, d.doc_key, d.version, d.title, d.summary, d.effective_from
    FROM legal_documents d
   WHERE d.status = 'approved' AND d.requires_acceptance
     AND d.effective_from IS NOT NULL AND d.effective_from <= current_date
     AND (d.audience = 'all' OR d.audience = p_audience)
     AND NOT EXISTS (SELECT 1 FROM legal_acceptances a
                      WHERE a.document_id = d.id AND a.user_id = p_user)
   ORDER BY d.doc_key
$$;
COMMENT ON FUNCTION legal_pending IS
  'Documento vigente que esta pessoa ainda não aceitou. Hoje retorna VAZIO para todo mundo, porque '
  'nenhuma minuta foi aprovada — e isso é o estado verdadeiro, não um erro.';

CREATE FUNCTION legal_overview()
  RETURNS TABLE (doc_key text, title text, latest_version integer, status text,
                 effective_from date, acceptances bigint, blocks_product boolean)
  LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  WITH latest AS (
    SELECT DISTINCT ON (doc_key) * FROM legal_documents ORDER BY doc_key, version DESC)
  SELECT l.doc_key, l.title, l.version, l.status, l.effective_from,
         (SELECT count(*) FROM legal_acceptances a WHERE a.doc_key = l.doc_key),
         l.requires_acceptance AND l.status <> 'approved'
    FROM latest l ORDER BY l.doc_key
$$;
-- O texto de QUALQUER versão, inclusive minuta, é servível pela API: a minuta já carrega o aviso
-- "DRAFT FOR LEGAL REVIEW" na primeira linha, e esconder o rascunho de quem vai conviver com ele não
-- protege ninguém. O que a RLS impede é a minuta aparecer onde só documento aprovado deveria estar.
CREATE FUNCTION legal_text(p_key text)
  RETURNS TABLE (doc_key text, version integer, title text, status text, body_md text,
                 body_sha256 text, effective_from date, source_path text)
  LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT d.doc_key, d.version, d.title, d.status, d.body_md, d.body_sha256, d.effective_from,
         d.source_path
    FROM legal_documents d
   WHERE d.doc_key = p_key AND d.status <> 'superseded'
   ORDER BY d.version DESC LIMIT 1
$$;

COMMENT ON FUNCTION legal_overview IS
  '`blocks_product` verdadeiro significa: este documento exige aceite e NÃO está aprovado, logo o '
  'produto não pode exigir aceite dele. É a lista de pendências jurídicas do lançamento.';

-- ============================================================================ RLS
ALTER TABLE legal_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE legal_acceptances ENABLE ROW LEVEL SECURITY;

-- Leitura é aberta, de propósito, inclusive de minuta. Três razões concretas:
--   1. quem vai aceitar um documento precisa poder lê-lo ANTES de ter conta;
--   2. a minuta se identifica como minuta na primeira linha dela, e esconder o rascunho de quem vai
--      conviver com ele não protege ninguém — o repositório é aberto de qualquer forma;
--   3. o que precisa ser impedido não é a LEITURA da minuta: é o ACEITE dela, e isso está travado em
--      `acceptance_stamp()`, que é onde o dano aconteceria.
-- Esconder a minuta por RLS daria a sensação de proteção e teria um efeito perverso: a recusa de
-- aceite voltaria "documento não encontrado" em vez de dizer que o documento é um rascunho.
CREATE POLICY legal_docs_read ON legal_documents FOR SELECT USING (true);
CREATE POLICY legal_docs_write ON legal_documents FOR INSERT WITH CHECK (app_priv());
CREATE POLICY legal_docs_update ON legal_documents FOR UPDATE
  USING (app_priv()) WITH CHECK (app_priv());

CREATE POLICY legal_acc_read ON legal_acceptances FOR SELECT
  USING (user_id = app_uid() OR app_priv());
CREATE POLICY legal_acc_write ON legal_acceptances FOR INSERT
  WITH CHECK (user_id = app_uid() OR app_priv() OR app_system());

GRANT SELECT, INSERT, UPDATE ON legal_documents TO impacto_app;
GRANT SELECT, INSERT ON legal_acceptances TO impacto_app;
GRANT USAGE, SELECT ON SEQUENCE legal_acceptances_id_seq TO impacto_app;
REVOKE UPDATE, DELETE ON legal_acceptances FROM impacto_app;

-- ============================================================================ as onze minutas
"""


def main() -> int:
    check = "--check" in sys.argv
    rows: list[str] = []
    for key, fname, title, summary, audience, requires in DOCS:
        path = LEGAL / fname
        if not path.exists():
            print(f"FALTA: {path}", file=sys.stderr)
            return 2
        body = path.read_text(encoding="utf-8")
        sha = hashlib.sha256(body.encode()).hexdigest()
        tag = f"$doc_{key}$"
        if tag in body:
            print(f"delimitador colide com o texto de {fname}", file=sys.stderr)
            return 2
        rows.append(
            f"-- {fname} · sha256 {sha}\n"
            f"INSERT INTO legal_documents(doc_key, version, title, summary, source_path, body_md,\n"
            f"       audience, requires_acceptance, status, software_version)\n"
            f"VALUES ('{key}', 1, {_q(title)}, {_q(summary)}, 'docs/legal/{fname}',\n"
            f"        {tag}{body}{tag},\n"
            f"        '{audience}', {str(requires).lower()}, 'draft', '0.17.0');\n")
    sql = HEAD + "\n".join(rows) + """
-- Nenhuma linha acima é 'approved', e nenhuma tem revisor. É o estado verdadeiro: as onze são
-- minutas técnicas escritas a partir do funcionamento do software, e nenhuma passou por advogado(a).
-- Enquanto isso não mudar, `legal_pending()` devolve vazio e nenhum aceite é registrável.
"""
    if check:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != sql:
            print("0023_v0170_legal.sql está dessincronizado de docs/legal/*.md", file=sys.stderr)
            return 1
        print("ok: migração em sincronia com docs/legal/*.md")
        return 0
    OUT.write_text(sql, encoding="utf-8")
    print(f"escrito {OUT.relative_to(ROOT)} ({len(sql.splitlines())} linhas, {len(DOCS)} documentos)")
    return 0


def _q(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


if __name__ == "__main__":
    raise SystemExit(main())
