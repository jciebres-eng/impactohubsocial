-- 0023_v0170_legal.sql — registro versionado de documento legal e aceite com prova
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
-- TERMS_OF_USE.md · sha256 db8ff200940b5b08d7e5a39362405c7c837821d959618ca1daebd562f552cc72
INSERT INTO legal_documents(doc_key, version, title, summary, source_path, body_md,
       audience, requires_acceptance, status, software_version)
VALUES ('terms_of_use', 1, 'Termos de Uso', 'Regras gerais de uso da Plataforma por qualquer pessoa ou organização.', 'docs/legal/TERMS_OF_USE.md',
        $doc_terms_of_use$# Termos de Uso — Plataforma Impacto

> **MINUTA — DRAFT FOR LEGAL REVIEW — [VALIDAR JURÍDICO]**. Rascunho técnico preparado a partir do funcionamento real do software (v0.7.0).
> Não é aconselhamento jurídico e **não pode ser publicado sem revisão de advogado(a)**. Campos entre `{{ }}` dependem
> de decisão do proprietário (razão social, CNPJ, foro, contato do encarregado).
> Registrada em `legal_documents` como MINUTA: enquanto não houver aprovação com revisor nomeado, o banco
> **recusa registrar aceite** deste documento (ver `docs/LEGAL_FRAMEWORK.md`).

Versão da minuta: 2026-10-04 · Aplica-se à versão de software 0.7.0

## 1. Quem somos
A Plataforma Impacto é operada por `{{RAZÃO SOCIAL}}`, CNPJ `{{CNPJ}}`, com sede em `{{ENDEREÇO}}` ("Plataforma").
Contato: `{{E-MAIL DE CONTATO}}`. Encarregado(a) de dados (LGPD art. 41): `{{NOME / E-MAIL DO ENCARREGADO}}`.

## 2. O que a Plataforma faz
2.1. Conecta **organizações da sociedade civil (OSCs)**, **empresas, institutos e fundações**, **profissionais parceiros**
(contadores, advogados, elaboradores de projetos) e **órgãos públicos**.
2.2. Funcionalidades: catálogo de editais, fundos e chamamentos (federais, estaduais, municipais, locais e internacionais);
cálculo de compatibilidade explicável; candidatura assistida passo a passo; cofre de documentos; rascunhos assistidos por IA;
revisão e assinatura por profissional habilitado; acompanhamento de aportes, despesas, evidências e prestação de contas;
relatórios para financiadores; estimativas fiscais informativas; publicação de editais e materiais por órgãos públicos.
2.3. **A Plataforma não é parte** dos acordos de financiamento entre OSCs e financiadores, **não intermedeia pagamentos de
aportes** (os valores circulam fora da Plataforma; aqui são apenas registrados e conferidos pelas partes) e **não garante
aprovação** em nenhum edital.

## 3. Natureza informativa de compatibilidade, IA e estimativas fiscais
3.1. A **compatibilidade** é um cálculo automatizado e explicável (motivos, impeditivos, riscos e dados faltantes) com base
nas informações cadastradas. Não substitui a leitura integral do edital, que prevalece sempre.
3.2. Textos gerados com **assistência de IA** são **rascunhos**. O usuário é responsável por revisar, corrigir e aprovar o
conteúdo antes de qualquer uso. Peças que exigem responsabilidade técnica devem ser revisadas e assinadas por profissional
habilitado no respectivo conselho.
3.3. **Estimativas fiscais** são classificadas como ESTIMATIVA, REGRA, ELEGIBILIDADE PROVÁVEL ou VALIDAÇÃO PROFISSIONAL
NECESSÁRIA. **Não constituem aconselhamento tributário** nem garantia de benefício. Somente regras revisadas por dois
especialistas são exibidas; a decisão final é do contribuinte e de seu contador.

## 4. Cadastro e conta
4.1. É preciso ter capacidade civil e poderes para representar a organização cadastrada.
4.2. O usuário deve manter dados verdadeiros e atualizados, inclusive documentos e certidões.
4.3. Credenciais são pessoais. Ative a verificação em duas etapas (obrigatória para administradores da Plataforma).
4.4. Comunique imediatamente qualquer uso não autorizado.

## 5. Verificação de organizações e profissionais
5.1. A Plataforma pode solicitar documentos e realizar verificações (KYB) antes de liberar funcionalidades.
5.2. Credenciais profissionais (CRC, OAB etc.) são verificadas por administradores; o selo "verificado" indica apenas que a
conferência documental foi feita na data indicada.
5.3. Posição no diretório, compatibilidade e elegibilidade **não podem ser compradas** (nenhum plano altera esses resultados).

## 6. Planos, cobrança e vouchers
6.1. Há planos gratuitos e pagos. Preços, periodicidade e limites são exibidos antes da contratação.
6.2. Pagamentos são processados por provedor terceirizado `{{PROVEDOR — ex.: Stripe}}`; a Plataforma não armazena dados de cartão.
6.3. Rebaixamento de plano **não apaga dados**; há período de carência de 60 dias para exportação.
6.4. Vouchers são pessoais, limitados e auditáveis; não são convertíveis em dinheiro.
6.5. Regras de cancelamento, arrependimento (CDC art. 49, quando aplicável), reembolso e emissão de nota fiscal: `{{DEFINIR}}` **[VALIDAR JURÍDICO/CONTÁBIL]**.

## 7. Conteúdo e documentos do usuário
7.1. O usuário mantém a titularidade do conteúdo que envia e concede à Plataforma licença limitada para armazená-lo,
processá-lo e exibi-lo **apenas a quem o usuário autorizar** (por exemplo, financiadores em diligência).
7.2. Arquivos são verificados (tipo, conteúdo ativo, antivírus) e podem ser recusados.
7.3. É proibido enviar conteúdo ilícito, de terceiros sem autorização, ou dados pessoais sensíveis desnecessários.

## 8. Registro de impacto (ledger) e auditoria
8.1. Eventos relevantes (aportes, confirmações, evidências, assinaturas) são gravados em registro encadeado por hash, sem
blockchain, para permitir verificação de integridade. **Esses registros não podem ser editados nem apagados**; correções são
feitas por novos lançamentos.
8.2. Em pedidos de eliminação de dados pessoais, dados identificáveis são anonimizados quando a retenção não for exigida
por lei ou necessária à prestação de contas (ver Política de Privacidade).

## 9. Condutas proibidas
Fraude documental; declaração falsa de aporte ou despesa; tentativa de acessar dados de outra organização; engenharia
reversa para burlar limites; automação abusiva; uso para lavagem de dinheiro ou financiamento ilícito.

## 10. Responsabilidades e limitações
10.1. A Plataforma emprega medidas técnicas razoáveis (ver Política de Privacidade, item Segurança), mas não garante
disponibilidade ininterrupta.
10.2. A Plataforma não responde por decisões de financiadores, resultados de editais, informações falsas prestadas por
usuários ou por conteúdo de editais publicados por terceiros (o catálogo indica a fonte oficial de cada edital).
10.3. Limites de responsabilidade: `{{DEFINIR}}` **[VALIDAR JURÍDICO]**.

## 11. Suspensão e encerramento
A Plataforma pode suspender contas que violem estes Termos, com notificação, salvo risco imediato. O usuário pode
encerrar a conta a qualquer tempo pela área "Minha conta" (exportação e eliminação de dados).

## 12. Alterações
Mudanças relevantes serão comunicadas com antecedência mínima de `{{N}}` dias por e-mail e na Plataforma.

## 13. Lei e foro
Lei brasileira. Foro: `{{COMARCA}}`, ressalvado o foro do consumidor quando aplicável. **[VALIDAR JURÍDICO]**
$doc_terms_of_use$,
        'all', true, 'draft', '0.17.0');

-- PRIVACY_POLICY.md · sha256 cd13d5e7566f62d32b7d1278d7934556c629bc86703550589fdc04c0c6f2189f
INSERT INTO legal_documents(doc_key, version, title, summary, source_path, body_md,
       audience, requires_acceptance, status, software_version)
VALUES ('privacy_policy', 1, 'Política de Privacidade', 'Quais dados são tratados, com que base legal, por quanto tempo e quais são os direitos do titular.', 'docs/legal/PRIVACY_POLICY.md',
        $doc_privacy_policy$# Política de Privacidade — Plataforma Impacto

> **MINUTA — DRAFT FOR LEGAL REVIEW — [VALIDAR JURÍDICO]**. Redigida a partir do tratamento de dados que o código v0.7.0 efetivamente realiza.
> Bases legais, prazos de retenção e transferências internacionais **precisam ser confirmados por advogado(a)/DPO** antes da
> publicação. Campos `{{ }}` dependem do proprietário.
> Registrada em `legal_documents` como MINUTA: enquanto não houver aprovação com revisor nomeado, o banco
> **recusa registrar aceite** deste documento (ver `docs/LEGAL_FRAMEWORK.md`).

Versão da minuta: 2026-10-04

Esta política explica como tratamos dados pessoais conforme a **LGPD (Lei nº 13.709/2018)**.

## 1. Controlador e encarregado
Controlador: `{{RAZÃO SOCIAL}}`, CNPJ `{{CNPJ}}`. Encarregado(a): `{{NOME}}` — `{{E-MAIL}}`.
Para dados de beneficiários e equipes inseridos por uma OSC, **a OSC é controladora** e a Plataforma atua como operadora.

## 2. Dados tratados (inventário real)
| Categoria | Exemplos | Origem | Finalidade | Base legal proposta [VALIDAR] |
|---|---|---|---|---|
| Conta | nome, e-mail, hash de senha (scrypt), segredo TOTP cifrado, códigos de recuperação (hash) | usuário | autenticação e segurança | execução de contrato (art. 7º, V) |
| Sessão e segurança | hash de tokens, IP, user-agent, tentativas de login, eventos de auditoria | sistema | prevenção a fraude, auditoria | legítimo interesse (art. 7º, IX) / obrigação legal |
| Organização | razão social, CNPJ, endereço, causas, certificações | usuário | perfil, compatibilidade, KYB | execução de contrato |
| Documentos | estatutos, certidões, atas, comprovantes | usuário | candidatura, diligência, prestação de contas | execução de contrato |
| Projetos e execução | orçamento, marcos, despesas, evidências, indicadores | usuário | acompanhamento e relatórios | execução de contrato |
| Credenciais profissionais | conselho, número, UF, nome do titular | profissional | verificação e assinatura | execução de contrato |
| Cobrança | plano, status, identificadores do provedor de pagamento (sem dados de cartão) | provedor de pagamento | faturamento | execução de contrato / obrigação legal |
| Uso de IA | contagem de caracteres e de tokens, provedor, modelo, latência, **hash** do conteúdo (o texto não é registrado em log) | sistema | controle de custo e cota | legítimo interesse |

Dados de **beneficiários** devem ser inseridos de forma agregada (contagens), sem identificação individual. A Plataforma
**não solicita** dados sensíveis (art. 5º, II); se um documento os contiver, a OSC é responsável pela base legal.

## 3. Compartilhamento
- **Entre organizações**: somente o que o titular publica (projeto publicado) ou libera em diligência (documentos).
  O isolamento entre organizações é aplicado no banco de dados (Row-Level Security do PostgreSQL), não apenas na interface.
- **Operadores (suboperadores)** — apenas os ativados pelo proprietário na configuração:
  hospedagem `{{PROVEDOR CLOUD/REGIÃO}}`; armazenamento de arquivos S3-compatível `{{PROVEDOR}}`; e-mail transacional
  `{{PROVEDOR SMTP}}`; pagamentos `{{Stripe ou outro}}`; login corporativo OIDC (opcional, do cliente); IA generativa
  `{{Anthropic / compatível OpenAI / nenhum}}`. O padrão da instalação é **IA local por regras, sem envio a terceiros**.
- **IA de terceiros**: quando ativada, o texto é enviado **após remoção automática por padrões** de CPF, e-mail, telefone, CEP e RG (a remoção automática é
  uma camada de proteção, não garantia absoluta; nomes próprios não são removidos).
- Autoridades: mediante obrigação legal ou ordem judicial.

## 4. Transferência internacional
Ocorre se o proprietário ativar provedores fora do Brasil (ex.: IA, pagamentos). Mecanismo (art. 33): `{{cláusulas-padrão ANPD / outro}}` **[VALIDAR]**.

## 5. Retenção
| Dado | Prazo proposto [VALIDAR] |
|---|---|
| Conta ativa | enquanto durar a conta |
| Conta eliminada | anonimização imediata dos dados pessoais; registros de auditoria/ledger mantidos de forma pseudonimizada |
| Registros de acesso | 6 meses (Marco Civil, art. 15) |
| Documentos fiscais/prestação de contas | `{{5 a 10 anos conforme o instrumento}}` |
| Rascunhos e uploads abandonados | `{{N}}` dias |

## 6. Direitos do titular (art. 18)
Na área **Minha conta → Privacidade**: exportar dados (JSON), solicitar eliminação. Demais pedidos (correção, informação
sobre compartilhamento, revogação de consentimento, oposição) pelo e-mail do encarregado. Prazo de resposta: `{{15 dias}}`.

## 7. Segurança (medidas implementadas no código)
Senhas com scrypt; verificação em duas etapas (TOTP); sessões com cookies httpOnly e proteção CSRF; bloqueio após
tentativas falhas; limitação de taxa; isolamento por organização no banco (RLS); arquivos privados com antivírus e
bloqueio de conteúdo ativo; trilha de auditoria encadeada por hash; cabeçalhos de segurança (CSP). Incidentes serão
comunicados à ANPD e aos titulares conforme art. 48 e Resolução CD/ANPD nº 15/2024 **[VALIDAR]**.

## 8. Cookies
Ver `COOKIES.md`. A Plataforma usa apenas cookies estritamente necessários; não há cookies de publicidade nem de análise de terceiros.

## 9. Crianças e adolescentes
O cadastro é destinado a maiores de 18 anos que representam organizações. Projetos podem beneficiar crianças, mas
os dados devem ser agregados.

## 10. Alterações
Mudanças serão comunicadas por e-mail e na Plataforma. Data da última atualização no topo.
$doc_privacy_policy$,
        'all', true, 'draft', '0.17.0');

-- COOKIES.md · sha256 71e1da22595ce38426231742a0574a8b0da2021c054e592224ebbc59e2d8f03c
INSERT INTO legal_documents(doc_key, version, title, summary, source_path, body_md,
       audience, requires_acceptance, status, software_version)
VALUES ('cookies', 1, 'Política de Cookies', 'Cookies e armazenamentos usados — todos estritamente necessários ao funcionamento.', 'docs/legal/COOKIES.md',
        $doc_cookies$# Política de Cookies — Plataforma Impacto

> **MINUTA — DRAFT FOR LEGAL REVIEW — [VALIDAR JURÍDICO]**. Lista extraída do código v0.7.0 (`backend/impacto/api/auth_routes.py`, `web/sw.template.js`).

A Plataforma usa **somente cookies e armazenamentos estritamente necessários** ao funcionamento e à segurança.
Não há cookies de publicidade, rastreamento ou análise de terceiros; por isso não exibimos banner de consentimento.
Se o proprietário adicionar ferramentas de análise no futuro, esta política e um mecanismo de consentimento deverão ser atualizados.

| Nome | Tipo | Finalidade | Duração | Acessível por JavaScript |
|---|---|---|---|---|
| `__Host-impacto_at` | cookie de sessão | token de acesso opaco | 15 minutos | não (httpOnly, Secure, SameSite=Lax) |
| `__Secure-impacto_rt` | cookie | token de renovação, restrito ao caminho `/v1/auth` | 30 dias, rotativo | não (httpOnly, Secure, SameSite=Strict) |
| `__Host-impacto_csrf` | cookie | proteção contra CSRF (vinculado à sessão) | 30 dias (igual ao token de renovação) | sim (necessário para o cabeçalho X-CSRF-Token) |
| Cache do Service Worker | Cache Storage | funcionamento offline da interface (HTML/CSS/JS/fontes) | até nova versão | — (nunca armazena respostas da API `/v1`) |

Em ambiente de desenvolvimento sem HTTPS os cookies usam nomes sem os prefixos `__Host-`/`__Secure-`.

No aplicativo móvel (Android/iOS) não há cookies: os tokens ficam no armazenamento do dispositivo
(`@capacitor/preferences`); para produção recomenda-se armazenamento seguro (Keychain/Keystore) — ver `docs/MOBILE.md`.
$doc_cookies$,
        'all', false, 'draft', '0.17.0');

-- SUBSCRIPTION.md · sha256 85b7301dd899ad7f7e96fc141ab76add9fbea1112db0d598ede7f2141c8b1a1a
INSERT INTO legal_documents(doc_key, version, title, summary, source_path, body_md,
       audience, requires_acceptance, status, software_version)
VALUES ('subscription', 1, 'Contrato de Assinatura (SaaS)', 'Plano, preço, reajuste, vigência e encerramento da assinatura. Declara o que é e permanece gratuito.', 'docs/legal/SUBSCRIPTION.md',
        $doc_subscription$# Contrato de Assinatura (SaaS) — Plataforma Impacto

> **MINUTA — DRAFT FOR LEGAL REVIEW — [VALIDAR JURÍDICO]**. Rascunho técnico escrito a partir do funcionamento real do
> software (v0.17.0), não de um modelo de contrato. **Não é aconselhamento jurídico e não pode ser publicado, exibido como
> vigente nem aceito por nenhum usuário sem revisão de advogado(a).** Campos entre `{{ }}` dependem de decisão do
> proprietário. Enquanto esta minuta não for aprovada, o banco se recusa a registrar aceite dela (ver
> `docs/LEGAL_FRAMEWORK.md`).

Versão da minuta: 2026-10-06 · Aplica-se à versão de software 0.17.0 · Chave: `subscription`

## 1. Objeto
1.1. Licença de uso, não exclusiva e não transferível, da Plataforma Impacto em regime de software como serviço, no plano
contratado, pelo prazo e pelo preço vigentes no momento da contratação.
1.2. A assinatura é **da organização**, não da pessoa que a contratou. A saída da pessoa não encerra o contrato.

## 2. O que é gratuito e permanece gratuito
2.1. Cadastro, perfil, criação de projeto, descoberta de oportunidades, participação na rede e acompanhamento básico são
**gratuitos e permanecem gratuitos** (plano `osc_basic`, "OSC — gratuito", declarado em `config/plans.json`).
2.2. A gratuidade acima não é promoção nem cortesia por prazo determinado: é o modelo econômico da Plataforma. A OSC
proponente não é a pagadora principal.
2.3. O plano gratuito tem limites técnicos declarados (projetos ativos, requisições de IA por mês, armazenamento, assentos e
buscas salvas). Limite técnico não é cobrança: ao atingi-lo, a organização continua com acesso ao que já criou.

## 3. Planos, preço e reajuste
3.1. O preço vigente de cada plano é o registrado em `plan_price_versions`, com início de vigência, moeda e motivo.
**Nenhum preço está embutido no código**; há teste automatizado que falha se alguém embutir.
3.2. Alteração de preço **não atinge vigência em curso**: abre nova versão, com vigência futura.
3.3. Aviso prévio de reajuste: `{{PRAZO — a minuta sugere 30 dias}}`, por notificação na Plataforma e por e-mail.
3.4. Moeda: BRL.

## 4. Pagamento
4.1. **Nenhum provedor de pagamento está configurado nesta instalação.** Não há conta, chave nem identificador de preço de
provedor. Em consequência, **a Plataforma não pode, hoje, receber pagamento de assinatura**, e toda cobrança existente no
sistema está marcada como simulada (`platform_charges.is_simulated`).
4.2. Enquanto 4.1 for verdadeiro, a contratação de plano pago depende de acerto fora da Plataforma e de registro manual pela
administração, com fatura em provedor `manual`.
4.3. Quando houver provedor, aplicam-se as condições do **Contrato de Pagamento** (`payment`).

## 5. Vigência, renovação e encerramento
5.1. Ciclo: `{{mensal | anual}}`, com renovação automática, salvo cancelamento.
5.2. O cancelamento segue a **Política de Cancelamento** (`cancellation`) e a **Política de Reembolso** (`refund`).
5.3. Encerrada a assinatura, a organização **não perde os dados**: volta ao plano gratuito, com os limites dele. Exclusão de
dados só ocorre por pedido do titular (LGPD) ou pela política de retenção documentada.

## 6. Disponibilidade
6.1. **Não há SLA contratado.** A Plataforma não promete percentual de disponibilidade, janela de manutenção nem prazo de
restabelecimento, porque nenhum desses números foi medido em operação real nem contratado com fornecedor de infraestrutura.
6.2. Afirmar disponibilidade que não foi medida seria falso. Qualquer compromisso de SLA exige decisão do proprietário,
contrato de infraestrutura e instrumentação — e deve entrar como anexo a este contrato.

## 7. Suporte
7.1. Canal: `{{E-MAIL / CANAL}}`. **Sem prazo de resposta contratado** pelo mesmo motivo da cláusula 6.

## 8. Obrigações da contratante
8.1. Manter dados e documentos verdadeiros e atualizados.
8.2. Responder pelo conteúdo que publica, inclusive por projetos, prestações de contas e evidências.
8.3. Não usar a Plataforma para fraude, nem inserir dado falso em prestação de contas.

## 9. Limites de responsabilidade
9.1. A Plataforma **não garante aprovação** em edital, chamamento ou processo de seleção.
9.2. A Plataforma **não é parte** dos acordos entre organizações e financiadores e **não custodia nem processa aportes**.
9.3. Textos gerados com assistência de IA são **rascunhos** sob responsabilidade de quem os aprova.
9.4. Estimativas fiscais são informativas e não substituem contador.

## 10. Perguntas abertas para o jurídico
1. A OSC/empresa contratante é **consumidora** para fins do CDC? A resposta muda cláusulas 5, 9 e toda a política de
   reembolso. A minuta **não** assume a resposta.
2. Limite de responsabilidade por valor (teto) é admissível no cenário escolhido em (1)?
3. Foro e cláusula de mediação: `{{DECISÃO DO PROPRIETÁRIO}}`.
4. A gratuidade permanente declarada em 2.2 cria direito adquirido? Como redigir sem criar obrigação perpétua e sem
   enganar a OSC?
$doc_subscription$,
        'all', false, 'draft', '0.17.0');

-- MARKETPLACE.md · sha256 0da9ea491bf02465e6978683b53e662224235d42a369edbe3df35a8101c61dc5
INSERT INTO legal_documents(doc_key, version, title, summary, source_path, body_md,
       audience, requires_acceptance, status, software_version)
VALUES ('marketplace', 1, 'Termos do Marketplace de Serviços', 'Regras para anunciar e contratar serviço profissional. Declara que não há comissão ativa.', 'docs/legal/MARKETPLACE.md',
        $doc_marketplace$# Termos do Marketplace de Serviços — Plataforma Impacto

> **MINUTA — DRAFT FOR LEGAL REVIEW — [VALIDAR JURÍDICO]**. Rascunho técnico escrito a partir do funcionamento real do
> software (v0.17.0), não de um modelo de contrato. **Não é aconselhamento jurídico e não pode ser publicado, exibido como
> vigente nem aceito por nenhum usuário sem revisão de advogado(a).** Campos entre `{{ }}` dependem de decisão do
> proprietário. Enquanto esta minuta não for aprovada, o banco se recusa a registrar aceite dela (ver
> `docs/LEGAL_FRAMEWORK.md`).

Versão da minuta: 2026-10-06 · Aplica-se à versão de software 0.17.0 · Chave: `marketplace`

## 1. Objeto
1.1. Regras de uso do espaço em que **profissionais e empresas parceiras** (contadores, advogados, elaboradores de projeto,
auditores, avaliadores) publicam serviços, e organizações os encontram e os contratam.
1.2. A navegação no marketplace é **gratuita** para quem procura.

## 2. O que a Plataforma é e o que não é
2.1. A Plataforma é **espaço de anúncio e de contato**. O contrato de prestação de serviço é entre a organização
contratante e o profissional.
2.2. A Plataforma **não presta** os serviços anunciados, **não garante** resultado, **não arbitra** disputa contratual e
**não recebe** o pagamento do serviço.
2.3. **Não há comissão (take rate) ativa.** A infraestrutura de cálculo existe e está **desligada por decisão
arquitetural** (ADR-022): cobrar percentual sobre transação que a Plataforma não processa exigiria custodiar ou processar
valor, o que a Plataforma não faz. Ligar isso depende de parecer jurídico e de revisão daquela decisão.

## 3. Quem pode anunciar
3.1. Profissional com registro em conselho, quando a atividade exigir (CRC, OAB), com o número do registro declarado.
3.2. A Plataforma **confere o que é conferível automaticamente** e exibe o estado da conferência. Conferência automática
não é atestado de idoneidade nem de capacidade técnica.
3.3. Anúncio com registro vencido ou inválido é despublicado.

## 4. Conteúdo do anúncio
4.1. Preço, escopo, prazo e forma de contratação são declarados pelo anunciante, que responde por eles.
4.2. É vedado: prometer aprovação em edital; prometer benefício fiscal; usar o nome de órgão público de modo a sugerir
credenciamento; anunciar serviço que exija registro que o anunciante não tem.
4.3. A Plataforma pode despublicar anúncio que viole 4.2, pela escada de moderação documentada.

## 5. Avaliações
5.1. Avaliação só pode ser feita por quem teve relação registrada na Plataforma. Avaliação inventada é fraude.

## 6. Responsabilidade
6.1. Pela execução do serviço: do profissional.
6.2. Pela escolha do profissional: da contratante.
6.3. Da Plataforma: pelo funcionamento do espaço de anúncio, nos limites do Contrato de Assinatura.

## 7. Perguntas abertas para o jurídico
1. A Plataforma é **marketplace** ou **portal de classificados**? A resposta muda o grau de responsabilidade solidária.
2. Se o CDC incidir, qual o dever de retirada de anúncio após notificação?
3. Take rate: existe desenho em que a Plataforma cobre percentual **sem** processar o valor (cobrança do profissional pelo
   serviço de intermediação, e não sobre a transação)? É a pergunta que destrava ou enterra essa receita.
$doc_marketplace$,
        'provider', false, 'draft', '0.17.0');

-- INTERMEDIATION.md · sha256 10e6bf8ece06132ecdf3101df71a9ce52f10c3137ca93d2c012e6f8c12754df2
INSERT INTO legal_documents(doc_key, version, title, summary, source_path, body_md,
       audience, requires_acceptance, status, software_version)
VALUES ('intermediation', 1, 'Termos de Intermediação e Conexão', 'Natureza da conexão entre organizações. Declara que a Plataforma não custodia nem processa aporte.', 'docs/legal/INTERMEDIATION.md',
        $doc_intermediation$# Termos de Intermediação e Conexão — Plataforma Impacto

> **MINUTA — DRAFT FOR LEGAL REVIEW — [VALIDAR JURÍDICO]**. Rascunho técnico escrito a partir do funcionamento real do
> software (v0.17.0), não de um modelo de contrato. **Não é aconselhamento jurídico e não pode ser publicado, exibido como
> vigente nem aceito por nenhum usuário sem revisão de advogado(a).** Campos entre `{{ }}` dependem de decisão do
> proprietário. Enquanto esta minuta não for aprovada, o banco se recusa a registrar aceite dela (ver
> `docs/LEGAL_FRAMEWORK.md`).

Versão da minuta: 2026-10-06 · Aplica-se à versão de software 0.17.0 · Chave: `intermediation`

## 1. Objeto
Regras da conexão entre organizações: descoberta, compatibilidade explicável, proposta, relação e projeto.

## 2. Natureza da conexão
2.1. A Plataforma **apresenta** organizações e oportunidades, com os motivos do cálculo expostos.
2.2. A Plataforma **não é parte** de nenhum acordo celebrado entre as organizações apresentadas.
2.3. A Plataforma **não custodia e não processa aporte**. Valor combinado entre as partes circula fora da Plataforma; aqui
o aporte é **registrado e conferido pelas partes**, com comprovante anexado por quem o detém.
2.4. Em consequência de 2.3, **não há success fee ativa**: cobrar percentual sobre aporte que a Plataforma não processa não
é verificável nem é o que a Plataforma faz (ADR-022). A infraestrutura existe e está desligada.

## 3. Compatibilidade
3.1. O cálculo de compatibilidade é automatizado e **explicável**: mostra motivos, impedimentos, riscos e dados faltantes.
3.2. **Não substitui a leitura do edital**, que prevalece sempre.
3.3. Compatibilidade alta não é promessa de aprovação nem de aporte.

## 4. Proposta e relação
4.1. A proposta registrada na Plataforma vale como **manifestação de interesse documentada**, com data e autoria.
4.2. A proposta só se torna obrigação entre as partes se e quando elas celebrarem instrumento próprio.
4.3. Toda alteração de etapa, documento ou situação da relação é **notificada a toda a equipe envolvida**, e a trilha é
append-only: quem mudou, quando, de qual estado para qual.

## 5. Evidência e prestação de contas
5.1. Despesa **registrada** e despesa **comprovada** são números distintos na Plataforma, e nunca somados.
5.2. Resultado **declarado** e resultado **medido** também são distintos. A Plataforma não promove hipótese a evidência.
5.3. Quem declara responde pelo que declarou.

## 6. Perguntas abertas para o jurídico
1. A Plataforma, ao apresentar partes e registrar proposta, pratica **corretagem** ou **agenciamento**? A resposta muda
   obrigação de registro e tributação.
2. O registro de aporte com comprovante anexado cria **dever de guarda** para a Plataforma? Por quanto tempo?
3. Em caso de desvio de recurso entre as partes, qual é o dever de informar autoridade?
$doc_intermediation$,
        'all', false, 'draft', '0.17.0');

-- PAYMENT.md · sha256 9c7db30e07ccf310fdaa69475ac8e2f4a6fc2afbad56c97bebd4b79fc4e09481
INSERT INTO legal_documents(doc_key, version, title, summary, source_path, body_md,
       audience, requires_acceptance, status, software_version)
VALUES ('payment', 1, 'Contrato de Pagamento', 'Meios de pagamento, parcelamento à parte da assinatura, confirmação por webhook assinado. Declara que nenhum provedor está configurado.', 'docs/legal/PAYMENT.md',
        $doc_payment$# Contrato de Pagamento — Plataforma Impacto

> **MINUTA — DRAFT FOR LEGAL REVIEW — [VALIDAR JURÍDICO]**. Rascunho técnico escrito a partir do funcionamento real do
> software (v0.17.0), não de um modelo de contrato. **Não é aconselhamento jurídico e não pode ser publicado, exibido como
> vigente nem aceito por nenhum usuário sem revisão de advogado(a).** Campos entre `{{ }}` dependem de decisão do
> proprietário. Enquanto esta minuta não for aprovada, o banco se recusa a registrar aceite dela (ver
> `docs/LEGAL_FRAMEWORK.md`).

Versão da minuta: 2026-10-06 · Aplica-se à versão de software 0.17.0 · Chave: `payment`

## 0. ESTADO REAL, HOJE: PRODUCTION PAYMENT NOT CONFIGURED
0.1. **Não há provedor de pagamento configurado.** Sem conta, sem chave, sem identificador de preço, sem webhook assinado.
0.2. Logo: **nenhuma cobrança real foi processada por este software**. Todas as cobranças existentes no banco nascem
marcadas como simuladas, por coluna derivada do provedor (`is_simulated`), que ninguém consegue escrever à mão.
0.3. O relatório de receita mantém o simulado em colunas próprias e **nunca** o soma ao real.
0.4. Esta minuta descreve as condições que valerão **quando** o provedor for contratado e ligado. Até então, ela não pode
ser exibida como contrato vigente.

## 1. Objeto
Condições de cobrança da Plataforma contra a organização usuária: assinatura, cobrança avulsa, parcelamento, PIX e boleto.

## 2. Meios previstos na arquitetura
| Meio | Situação técnica | Observação |
|---|---|---|
| Cartão (avulso) | implementado na camada da Plataforma, **sem provedor** | token do provedor; a Plataforma não guarda número de cartão |
| Cartão recorrente (assinatura) | implementado desde a v0.11.0, **sem provedor** | ciclo e fatura em `invoices` |
| **Parcelamento** | implementado, **sem provedor** | modelado **à parte** da assinatura: número fixo de parcelas, vencimentos próprios, não renova, e a soma das parcelas tem de fechar com o total |
| PIX | instrução e prazo modelados, **sem provedor** | sem provedor não há cobrança de PIX: QR/copia-e-cola vem do provedor |
| Boleto | instrução e vencimento modelados, **sem provedor** | linha digitável vem do provedor |

2.1. Parcelamento **não é assinatura**, e a diferença é contratual, não só técnica: assinatura renova por prazo
indeterminado e pode reajustar; parcelamento é preço fechado dividido em parcelas, sem renovação.

## 3. Dados de cartão
3.1. A Plataforma **não armazena número de cartão, CVV nem validade**. Guarda apenas o token do provedor, a bandeira e os
**quatro últimos dígitos** — e há trava no banco que recusa qualquer tentativa de gravar mais que quatro dígitos nesse campo.
3.2. A administração da Plataforma **não lê** o token de cartão do cliente.

## 4. Confirmação de pagamento
4.1. Quem confirma pagamento é o **webhook assinado do provedor**. A tela nunca é fonte de verdade.
4.2. Evento sem assinatura conferida é **registrado e não produz efeito** (há restrição no banco impedindo que ele chegue a
"processado").
4.3. Reentrega do mesmo evento não duplica efeito; apenas conta a reentrega para a reconciliação.

## 5. Nota fiscal
5.1. **A Plataforma não emite nota fiscal hoje.** Não há provedor fiscal contratado nem integração com prefeitura.
5.2. Emissão de NFS-e sobre a assinatura é obrigação a cumprir pelo proprietário e depende de inscrição municipal, regime
tributário e provedor — decisões que não são de software.

## 6. Inadimplência
6.1. Fatura em aberto após o vencimento: `{{PRAZO DE TOLERÂNCIA}}`.
6.2. Consequência prevista: suspensão de recursos pagos, **com preservação do acesso gratuito e dos dados já criados**.
6.3. Multa e juros: `{{DECISÃO — limites legais aplicáveis}}`.

## 7. Perguntas abertas para o jurídico
1. Qual provedor será contratado, e sob qual contrato (adquirência, subadquirência, instituição de pagamento)? A resposta
   muda quem é responsável por chargeback.
2. Parcelamento com juros exige informação de CET — a Plataforma pretende cobrar juros? Se sim, há dever de informação
   específico.
3. PIX: a conta de recebimento é do proprietário ou de terceiro? Receber em conta de terceiro muda a natureza da operação.
4. Nota fiscal: município, código de serviço e regime — `{{CONTADOR}}`.
$doc_payment$,
        'all', false, 'draft', '0.17.0');

-- CANCELLATION.md · sha256 49297f644913a13a10a1444e0ee5c953c76be0b33b86a13dec0932042ef73a69
INSERT INTO legal_documents(doc_key, version, title, summary, source_path, body_md,
       audience, requires_acceptance, status, software_version)
VALUES ('cancellation', 1, 'Política de Cancelamento', 'Como cancelar, qual o efeito e por que cancelar não apaga dados.', 'docs/legal/CANCELLATION.md',
        $doc_cancellation$# Política de Cancelamento — Plataforma Impacto

> **MINUTA — DRAFT FOR LEGAL REVIEW — [VALIDAR JURÍDICO]**. Rascunho técnico escrito a partir do funcionamento real do
> software (v0.17.0), não de um modelo de contrato. **Não é aconselhamento jurídico e não pode ser publicado, exibido como
> vigente nem aceito por nenhum usuário sem revisão de advogado(a).** Campos entre `{{ }}` dependem de decisão do
> proprietário. Enquanto esta minuta não for aprovada, o banco se recusa a registrar aceite dela (ver
> `docs/LEGAL_FRAMEWORK.md`).

Versão da minuta: 2026-10-06 · Aplica-se à versão de software 0.17.0 · Chave: `cancellation`

## 1. Como cancelar
1.1. Pela própria Plataforma, pela organização, sem precisar falar com ninguém e sem retenção por telefone.
1.2. O cancelamento é registrado com data, autoria e situação anterior, em trilha append-only.

## 2. Efeito
2.1. O cancelamento encerra a **renovação**. O acesso ao plano pago segue até o fim do ciclo já pago.
2.2. Ao fim do ciclo, a organização **volta ao plano gratuito** e continua com acesso ao que já criou, nos limites do plano
gratuito. Cancelar **não apaga dados**.
2.3. Recurso pago acima do limite gratuito deixa de aceitar **nova** criação; o que já existe continua legível e exportável.

## 3. Exportação antes de sair
3.1. A organização pode exportar seus dados antes e depois do cancelamento, pelos recursos de exportação e de pedido de
titular (LGPD).

## 4. Direito de arrependimento (CDC art. 49)
4.1. **Questão aberta, não decidida nesta minuta**: o art. 49 garante 7 dias para desistir de contratação feita fora do
estabelecimento, **ao consumidor**. Se a contratante for OSC ou empresa usando a Plataforma como insumo da própria
atividade, pode não ser consumidora, e o prazo pode não incidir.
4.2. Enquanto o jurídico não responder, a Plataforma **não afirma** ter nem não ter esse prazo. A regra operacional
provisória proposta é a mais favorável à contratante: 7 dias, com devolução integral — ver Política de Reembolso.

## 5. Cancelamento pela Plataforma
5.1. Hipóteses: fraude, inserção de dado falso em prestação de contas, uso para fim ilícito, inadimplência após o prazo de
tolerância.
5.2. Em qualquer hipótese: aviso com motivo, prazo para exportar os dados e preservação do acervo pelo prazo de retenção.

## 6. Perguntas abertas para o jurídico
1. A resposta de 4.1 (consumidora ou não).
2. Cancelamento imediato com pro rata é obrigatório em algum cenário?
3. Qual prazo de guarda após o encerramento — e como ele se concilia com a minimização da LGPD?
$doc_cancellation$,
        'all', false, 'draft', '0.17.0');

-- REFUND.md · sha256 a84eb84702d50d99ad114cbc091c347bb794419d0d042a28d7c97fb88d85e658
INSERT INTO legal_documents(doc_key, version, title, summary, source_path, body_md,
       audience, requires_acceptance, status, software_version)
VALUES ('refund', 1, 'Política de Reembolso', 'Hipóteses de devolução, devolução parcial e prazos. Depende de parecer sobre incidência do CDC.', 'docs/legal/REFUND.md',
        $doc_refund$# Política de Reembolso — Plataforma Impacto

> **MINUTA — DRAFT FOR LEGAL REVIEW — [VALIDAR JURÍDICO]**. Rascunho técnico escrito a partir do funcionamento real do
> software (v0.17.0), não de um modelo de contrato. **Não é aconselhamento jurídico e não pode ser publicado, exibido como
> vigente nem aceito por nenhum usuário sem revisão de advogado(a).** Campos entre `{{ }}` dependem de decisão do
> proprietário. Enquanto esta minuta não for aprovada, o banco se recusa a registrar aceite dela (ver
> `docs/LEGAL_FRAMEWORK.md`).

Versão da minuta: 2026-10-06 · Aplica-se à versão de software 0.17.0 · Chave: `refund`

## 0. Aviso indispensável
**Nenhum provedor de pagamento está configurado.** Não há, hoje, pagamento real a devolver: toda cobrança existente no
sistema é simulada. Esta minuta descreve a regra que valerá quando houver pagamento de verdade.

## 1. Hipóteses de devolução
| Hipótese | Proposta da minuta | Situação |
|---|---|---|
| Arrependimento em 7 dias (se o CDC incidir) | devolução integral | **depende de parecer** |
| Cobrança em duplicidade | devolução integral, sem discussão | regra clara |
| Cobrança de valor diferente do preço vigente | devolução da diferença | regra clara |
| Indisponibilidade prolongada | `{{DECISÃO}}` — sem SLA contratado, não há parâmetro | **depende de decisão** |
| Insatisfação após uso do ciclo | sem devolução; cancelamento encerra a renovação | regra clara |

## 2. Devolução parcial
2.1. O sistema registra devolução parcial com valor **entre zero e o total**, e recusa valor fora desse intervalo.
2.2. Devolução integral marca o valor devolvido como o total, por derivação — não por digitação.

## 3. Prazo
3.1. Da decisão: `{{PRAZO}}` a contar do pedido.
3.2. Do crédito: depende do meio e do provedor. A Plataforma **não promete** prazo de estorno de cartão, que não é dela.

## 4. Como pedir
Pela Plataforma, com registro de data, autoria e motivo. A decisão é registrada com fundamento, não com "negado".

## 5. Perguntas abertas para o jurídico
1. Incidência do CDC (a mesma pergunta das demais minutas, e a mais importante de todas).
2. Devolução por indisponibilidade sem SLA contratado: existe parâmetro legal supletivo?
3. Retenção de valor por uso proporcional é admissível?
$doc_refund$,
        'all', false, 'draft', '0.17.0');

-- B2B.md · sha256 e71a21c7881404ecfcb5563fd6d9ba4e71f83967fa5ace3a38567947d15eaacb
INSERT INTO legal_documents(doc_key, version, title, summary, source_path, body_md,
       audience, requires_acceptance, status, software_version)
VALUES ('b2b', 1, 'Contrato Institucional (B2B / Enterprise / ESG)', 'Uso institucional para gestão de portfólio de investimento social. Lista o que NÃO está incluído.', 'docs/legal/B2B.md',
        $doc_b2b$# Contrato Institucional (B2B / Enterprise / ESG) — Plataforma Impacto

> **MINUTA — DRAFT FOR LEGAL REVIEW — [VALIDAR JURÍDICO]**. Rascunho técnico escrito a partir do funcionamento real do
> software (v0.17.0), não de um modelo de contrato. **Não é aconselhamento jurídico e não pode ser publicado, exibido como
> vigente nem aceito por nenhum usuário sem revisão de advogado(a).** Campos entre `{{ }}` dependem de decisão do
> proprietário. Enquanto esta minuta não for aprovada, o banco se recusa a registrar aceite dela (ver
> `docs/LEGAL_FRAMEWORK.md`).

Versão da minuta: 2026-10-06 · Aplica-se à versão de software 0.17.0 · Chave: `b2b`

## 1. Objeto
Uso institucional da Plataforma por empresa, instituto, fundação ou financiador para **gerir o próprio portfólio de
investimento social**: programas, chamadas, carteira de projetos apoiados, indicadores, prestação de contas recebida e
relatório de impacto consolidado.

## 2. O problema que este contrato resolve
2.1. A contratante compra **a gestão do portfólio e a prestação de contas auditável**, não um pacote de telas. A Plataforma
substitui planilha paralela, pasta de e-mail e relatório montado à mão no fim do ano.
2.2. O que a contratante leva: programa com chamadas e carteira; indicadores com linha de base **e fonte**; distinção
mantida entre valor **declarado** e valor **medido**, e entre despesa **registrada** e despesa **comprovada**; cadeia de
resultado com a força de cada elo declarada; lacuna territorial da carteira; trilha append-only de cada mudança, com
notificação a toda a equipe envolvida.

## 3. O que este contrato NÃO inclui
3.1. **Não inclui** repasse, custódia ou processamento de aporte. O dinheiro circula fora da Plataforma.
3.2. **Não inclui** auditoria independente, parecer contábil nem atestado de impacto. A Plataforma organiza a evidência;
não assina laudo.
3.3. **Não inclui** SLA: não há disponibilidade contratada (ver Contrato de Assinatura, cláusula 6).
3.4. **Não inclui** emissão de nota fiscal automatizada: não há provedor fiscal integrado.
3.5. **Não inclui** relatório regulatório pronto para CVM, GRI, SASB ou ISSB. A Plataforma exporta dado estruturado e
rastreável; a conformidade do relatório com um referencial específico depende de trabalho adicional e de decisão da
contratante. Afirmar aderência a referencial não implementado seria falso.

## 4. Preço
4.1. Por contrato, com base em escopo: número de programas, carteira, assentos, integrações e necessidade de implantação.
4.2. **Nenhum preço institucional está declarado no sistema**, e nenhum está embutido no código. O preço de contrato é
decisão comercial do proprietário e entra como anexo.
4.3. Implantação (migração de carteira histórica, modelagem de indicadores, treinamento) é escopo **separado**, com preço
próprio.

## 5. Dados e LGPD
5.1. Cada organização enxerga os próprios dados. O isolamento é imposto pelo banco (RLS), não pela interface, e há teste
automatizado de isolamento entre organizações.
5.2. A contratante é controladora dos dados que insere; a Plataforma é operadora quanto a esses dados. O inverso vale para
os dados de cadastro da própria contratante.
5.3. Subcontratação de infraestrutura e transferência internacional: `{{DECLARAR — depende da hospedagem escolhida}}`.

## 6. Propriedade
6.1. O dado da contratante é da contratante, exportável em formato aberto a qualquer momento, durante e após o contrato.
6.2. O software é da Plataforma. Nada aqui transfere código.

## 7. Perguntas abertas para o jurídico
1. Quem é controlador e quem é operador em cada fluxo? A minuta propõe 5.2 e precisa de conferência.
2. É necessário Acordo de Processamento de Dados anexo? A minuta assume que sim.
3. Cláusula de auditoria pela contratante: até onde vai (log? ambiente? código?).
4. Teto de responsabilidade e seguro: `{{DECISÃO DO PROPRIETÁRIO}}`.
$doc_b2b$,
        'company', false, 'draft', '0.17.0');

-- B2G.md · sha256 70f1a06f2d3b367f0aeedd782c31a7433d49cc9bb0c118d97ddde76b1a9e7fa1
INSERT INTO legal_documents(doc_key, version, title, summary, source_path, body_md,
       audience, requires_acceptance, status, software_version)
VALUES ('b2g', 1, 'Contrato com o Poder Público (B2G)', 'Uso por órgão público em chamamento. Declara a ausência de assinatura qualificada e de integrações governamentais.', 'docs/legal/B2G.md',
        $doc_b2g$# Contrato com o Poder Público (B2G) — Plataforma Impacto

> **MINUTA — DRAFT FOR LEGAL REVIEW — [VALIDAR JURÍDICO]**. Rascunho técnico escrito a partir do funcionamento real do
> software (v0.17.0), não de um modelo de contrato. **Não é aconselhamento jurídico e não pode ser publicado, exibido como
> vigente nem aceito por nenhum usuário sem revisão de advogado(a).** Campos entre `{{ }}` dependem de decisão do
> proprietário. Enquanto esta minuta não for aprovada, o banco se recusa a registrar aceite dela (ver
> `docs/LEGAL_FRAMEWORK.md`).

Versão da minuta: 2026-10-06 · Aplica-se à versão de software 0.17.0 · Chave: `b2g`

## 1. Objeto
Uso da Plataforma por órgão ou entidade pública para **publicar chamamento, receber e analisar proposta, acompanhar
execução e receber prestação de contas** de organizações da sociedade civil.

## 2. O problema que este contrato resolve
2.1. O órgão compra **trilha auditável de chamamento público**: edital publicado com data, propostas recebidas com hora,
análise com motivo registrado, execução acompanhada com evidência anexada e prestação de contas organizada.
2.2. O que o órgão leva: trilha append-only de cada ato; distinção entre o que foi declarado e o que foi comprovado;
lacuna territorial do conjunto de projetos apoiados; notificação a toda a equipe envolvida em cada etapa.

## 3. O que este contrato NÃO inclui — e aqui está a parte que não pode ser maquiada
3.1. **Não inclui assinatura digital qualificada, ICP-Brasil, integração gov.br, certificado digital nem biometria.** Nada
disso está implementado, e nada disso será simulado. Ato que exija assinatura qualificada **tem de ser praticado fora da
Plataforma** enquanto isso for verdade.
3.2. **Não inclui** integração com SICONV/Transferegov, SIAFI, Portal da Transparência, e-SIC nem sistema de compras
governamental. Não há credencial, convênio técnico nem documentação de integração contratada.
3.3. **Não inclui** processo eletrônico oficial (SEI ou equivalente). A Plataforma não é sistema de processo administrativo.
3.4. **Não inclui** publicação em diário oficial.
3.5. **Não inclui** parecer jurídico nem de controle interno.
3.6. **Não inclui** SLA nem plano de continuidade contratado.
3.7. A Plataforma **não substitui** o procedimento legal do chamamento. Ela o organiza e o documenta.

## 4. Contratação pelo órgão
4.1. A contratação depende do procedimento da Lei 14.133/2021 aplicável ao caso, cuja escolha é do órgão e de sua
assessoria jurídica. **A Plataforma não afirma caber em dispensa, em inexigibilidade nem em qualquer hipótese específica**:
essa afirmação, feita por quem vende, é exatamente o tipo de alegação que compromete o processo.
4.2. A Plataforma fornece, quando solicitada, descrição técnica verdadeira do que o software faz e do que não faz —
inclusive esta cláusula 3 inteira.

## 5. Dados públicos e acesso à informação
5.1. Dado de chamamento é público por natureza e assim é tratado.
5.2. Dado pessoal de proponente segue a LGPD, inclusive o art. 7º, III (execução de política pública), cuja aplicação ao
caso concreto é decisão do órgão.
5.3. Pedido de acesso à informação é respondido pelo órgão. A Plataforma fornece o dado ao órgão.

## 6. Preço
6.1. `{{DEFINIR}}`. Não há preço de B2G declarado no sistema e nenhum embutido no código.
6.2. Referência pública de preço, quando usada, é citada com fonte e data — nunca estimada de cabeça.

## 7. Perguntas abertas para o jurídico
1. Qual o enquadramento da contratação na Lei 14.133/2021 para cada perfil de órgão? Pergunta para a assessoria do órgão,
   não para o fornecedor.
2. A ausência de assinatura qualificada (3.1) impede qual ato, exatamente, em qual etapa do chamamento?
3. É necessário Acordo de Cooperação Técnica em vez de contrato de serviço em algum cenário?
4. Guarda e eliminação de documento público na Plataforma: qual tabela de temporalidade se aplica?
$doc_b2g$,
        'government', false, 'draft', '0.17.0');

-- Nenhuma linha acima é 'approved', e nenhuma tem revisor. É o estado verdadeiro: as onze são
-- minutas técnicas escritas a partir do funcionamento do software, e nenhuma passou por advogado(a).
-- Enquanto isso não mudar, `legal_pending()` devolve vazio e nenhum aceite é registrável.
