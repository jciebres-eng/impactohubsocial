# Baseline da camada IES — auditoria somente leitura (Etapa 1)

**Data:** 10/10/2026 · **Base auditada:** ramo `seguranca-v0350`, commit `b50c4e0` (v0.35.0; pacote do commit `546e225`,
SHA-256 `37d9c1f1…87ec`) · **Ramo de trabalho:** `ies-v0360` · **Entradas lidas por inteiro:** `KIT_SUPERPROMPTS_IMPACTO_IES.md`
(SHA-256 `8f76a33b…`), `PROMPT_MESTRE_CLAUDE_PLATAFORMA_IMPACTO_IES.md`, `ADENDO_IMPACTO_LOGIN_PERFIS_IES.zip` (prompt + decisões),
`ADENDO_IMPACTO_INTEGRACOES_ERP_MOODLE.zip` (prompt + matriz inicial). O "Texto colado.txt" citado pelo kit **não foi anexado** —
nada dele foi presumido.

> O kit foi escrito para a 0.33.0. A base real é a 0.35.0 (duas versões depois: ecossistema financeiro e correções de segurança).
> Tudo abaixo foi conferido no código desta base, não nos documentos do kit.

## 1. O que é a base

| Item | Fato verificado |
|---|---|
| Nome e versão | Plataforma IMPACTO, `VERSION` = 0.35.0 |
| Arquivos versionados | 4.701 (`git ls-files`) |
| Backend | Python ≥ 3.11 (ambiente: 3.13.16), Starlette, driver libpq próprio, PostgreSQL 16 com RLS (`backend/impacto`) |
| Banco | 74 migrações SQL só para frente (`backend/migrations/0001…0074`), aplicadas por nome |
| Frontend | React 19.2.8 + TypeScript 6.0.3, esbuild 0.28.2; `web/dist` versionado (`web/src`) |
| Rotas de API | 994 operações classificadas em 9 classes (`docs/execution/API_AUTHORIZATION_MATRIX.csv`) |
| Telas | 235 rotas de tela (`docs/execution/screen_inventory.json`, `web/src/app.tsx`) |
| Testes | 143 módulos, 2.572 funções de teste (`backend/tests/test_*.py`) |
| Infra | Railway (backend, worker `pleasing-trust`, ClamAV, demo), Supabase (banco), Cloudflare R2 (arquivos e backup) — `CLAUDE.md` |
| CI | `.github/workflows/ci.yml` (no PR: suíte completa, E2E, pilha do zero com axe-core) |

**Comandos reais** (os mesmos do CI e dos fechamentos anteriores): `ruff check impacto tests`; `python3 -m unittest discover -s tests`
(em `backend/`, com `TEST_ADMIN_DATABASE_URL` de um PostgreSQL local); `tsc --noEmit`; `node build.mjs` (em `web/`);
`scripts/demo_stack.py` (pilha do zero); `scripts/make_release.py` + `verify_package_against_git.py` + `secrets_scan.py`.

**Baseline de testes:** CI do PR #8 no commit `546e225` (execução `38074835962`) — 6 de 6 jobs verdes, inclusive a suíte completa e
a pilha do zero; regressão local registrada em `docs/evidence/test_run_v0.35.0.log`. É contra isso que a v0.36.0 será comparada.

## 2. O que a camada IES pode reaproveitar (com evidência)

| Necessidade do kit | O que já existe | Onde | Estado |
|---|---|---|---|
| Login central, recuperação, verificação de e-mail, MFA, sessão, step-up | completo, com limites de taxa e respostas que não revelam conta (com 1 exceção, §4) | `api/auth_routes.py`, `services/auth.py`, `http.py`, `core/access.py` | IMPLEMENTADO E TESTADO |
| Uma conta, vários vínculos | `memberships (user_id, org_id)` com 6 papéis; troca de organização ativa revalidada a cada requisição | `0001`, `http.py::load_principal`, `/v1/me/switch-org` | IMPLEMENTADO E TESTADO |
| Escolha de contexto depois do login | `/portal` + `dashboard_for()` no servidor; `/portal?escolher=1`; seletor no menu | `access_routes.py`, `web/src/pages/portal.tsx` | IMPLEMENTADO E TESTADO |
| Convites com token | `invitations` (hash, 7 dias, revogação, uso único com `FOR UPDATE`) | `services/auth.py::invite/accept_invite` | IMPLEMENTADO; reuso/expiração **sem teste** |
| SSO institucional | OIDC (code + PKCE, JWKS) com UM provedor por instalação; SAML ausente | `services/oidc.py` | CONTRACT TEST (provedor falso) |
| Trilha de auditoria | `audit_events` encadeada por hash, só inclusão, por organização | `services/audit.py`, `0002`, `0056` | IMPLEMENTADO E TESTADO |
| Isolamento entre organizações | RLS em toda tabela + testes de "muro" | `test_security_tenancy`, `test_v0230_authorization_matrix` | IMPLEMENTADO E TESTADO |
| Licença institucional | convênios com assentos (por ORGANIZAÇÃO), concessões (`entitlement_grants` com origem license/contract/convention), vouchers de concessão | `0008`, `0067`, `services/entitlements.py` | IMPLEMENTADO E TESTADO; assento por PESSOA **ausente** |
| Quem paga a IA | prévia de custo antes da operação, cotas, patrocínio por organização, revisão humana | `0068`, `engines/ai/gateway.py`, `ai_center.py` | IMPLEMENTADO E TESTADO; nenhum provedor externo ligado |
| Projetos e programas | `projects` (17 estados), `programs` + `program_projects` + `program_indicators` | `0013`, `0018` | projetos: TESTADO; programas: back-end testado, **sem tela** |
| Evidência | `evidences` com versão, método, acesso, base legal, retenção declarada, contestação, histórico | `0070` | back-end TESTADO; a tela não envia método/acesso/base; `access_level` não é aplicado pela RLS |
| Dossiê | `services/dossier.py` (proveniência, lacunas, "o que isto não é"), só para as partes | `impact_routes.py` | IMPLEMENTADO E TESTADO; exportação só JSON |
| Indicadores e comparabilidade | reportado × validado (validador de outra organização), linha de base com fonte, mudança de método com quebra de série | `0004`, `0053`, `0070` | IMPLEMENTADO E TESTADO |
| Entrega com aceite por outra pessoa | marcos de acordo (aceite ≠ quem entregou); relatório periódico com "pedir ajuste" | `0012`/`0064`; `network/impact_report.py` | IMPLEMENTADO E TESTADO |
| Responsável que passa a função | `responsibility_assignments` (encerra com motivo, um corrente por papel) | `0031` | IMPLEMENTADO E TESTADO |
| Demandas reais | `territory_needs`, `calls`, `project_needs`, propostas; match explicável | `0016`, `engines/match` | IMPLEMENTADO E TESTADO |
| Registro verificável e QR | `verifiable_records` (código público, validade, revogação) | `trust/verifiable.py` | IMPLEMENTADO E TESTADO |
| Formulário público sem conta | padrão anti-robô (campo-armadilha), limite por IP, consentimento | `knowledge_routes.py` (parceria/demonstração) | IMPLEMENTADO E TESTADO (não para retorno de comunidade) |
| Importação com prévia | CSV/XLSX, erro por linha, limites, idempotência por SHA-256, aprovação | `integrations/files.py` | TESTADO — **mas só vincula IDs a registros existentes** (ADR-093) |
| Hub de integração | adapters, credencial cifrada por organização, maturidade (scaffolded → production_active), retentativas, disjuntor, idempotência | `integrations/`, `adapters/`, `0011` | TESTADO por contrato; sem cursor/paginação; sem nenhum sistema acadêmico |
| Exportação | pdf, docx, odt, xlsx, ods, csv, xml, json | `services/formats.py` | IMPLEMENTADO; neutralização de fórmula em 3 implementações diferentes (§4) |
| Editais com proveniência | `calls` + `call_sources` (json/csv/rss), verificação, match explicável (só OSC) | `0001`, `jobs.py` | PARCIAL para fomento à pesquisa (§3) |

## 3. O que NÃO existe (verificado)

- **Nenhum conceito acadêmico no código:** curso de graduação, componente curricular, período letivo, oferta/turma, matrícula,
  estudante, docente, coordenação, carga horária de extensão, rubrica, competência. "semestre" só aparece em texto de seed.
- **IES como cliente:** cabe hoje como organização `osc` com natureza jurídica `academic_institution` (`0006`, linhas 332 e 363) — o
  que é **errado para IES pública** (é órgão/entidade pública) e para IES privada com fins lucrativos (empresa).
- **Papel com escopo menor que a organização** (curso, turma, grupo, projeto): ausente. Os papéis só existem por organização, e a
  RLS trabalha com UMA organização ativa (`app.org_id`).
- **Pessoa sem organização** não usa o produto: a tela obriga a criar uma (`web/src/app.tsx`, `CreateOrg`).
- **Acesso de terceiro temporário, com escopo e revogação** (avaliador externo): ausente como mecanismo genérico.
- **Registro de horas** com submissão, revisão e aprovação por outra pessoa: ausente.
- **Ciclo/semestre e continuidade entre ciclos (passagem de bastão):** ausente.
- **Retorno da comunidade por link/QR sem conta:** ausente.
- **Consentimento de participante** (termo de uso de imagem, assentimento): ausente (só `evidences.consent_basis` declarado).
- **Moodle, LTI, SAML, Lyceum, Sophia, SIGAA, Gennera, Unimestre, Jacad, Sponte, Sagres:** zero ocorrência no código. O adapter
  `totvs` existente fala de CRM/RH/financeiro, não do TOTVS Educacional.
- **CAPES, CNPq, FINEP, FAPs, Lattes:** zero ocorrência no código.
- **Chave de API / conta de serviço** para sistema externo chamar o IMPACTO: ausente (`api_keys_available` responde que não há).

## 4. Achados laterais (fora do escopo IES, registrados com prioridade)

| Achado | Evidência | Risco | Prioridade |
|---|---|---|---|
| Conta bloqueada responde `429 account_locked` só para conta real | `services/auth.py` (login) | enumeração de contas | P2 — registrar; não muda nesta versão |
| Neutralização de fórmula em 3 implementações; `services/reports.py::_safe` ignora TAB/CR e não trata cabeçalhos | `integrations/files.py`, `execution_routes.py`, `services/reports.py` | injeção de fórmula em planilha exportada | **P1 — a camada IES usará uma função única e testada** |
| Linhas brutas de importação (`integration_import_rows`) fora da rotina de retenção | `jobs.py::retention` | dado pessoal guardado sem prazo | P1 — a importação acadêmica terá retenção própria |
| Conexão em `production` permitida para provedor só `contract_tested` (exceto governo) | `integration_routes.py` | rótulo de produção sem homologação | P1 — o catálogo acadêmico recusa isso por desenho |
| Tela de evidência não envia método/acesso/base; `access_level` não é aplicado pela RLS | `web/src/pages/projects.tsx`, `0002` | evidência com acesso declarado e não aplicado | P1 — evidências acadêmicas terão acesso aplicado no banco |
| Tela de indicador envia linha de base sem fonte (o gatilho recusaria) | `web/src/pages/impact.tsx` | erro na tela | P2 — NÃO VERIFICADO em execução |
| Programas sem tela; "Programa" na interface é o edital | `0018`; `web/src/pages/calls.tsx` | confusão de termo | P2 |
| Testes de reuso/expiração/revogação de convite | ausentes | regressão silenciosa | P1 — os convites acadêmicos terão esses testes |

## 5. Riscos da camada IES (antes de desenhar)

- **Duplicação de núcleo:** criar segunda tabela de usuários, de organizações ou de projetos. Mitigação: IES é organização; pessoas
  são `users`; papel acadêmico é um vínculo com escopo; projeto de extensão referencia `programs`/`projects` quando houver.
- **Vazamento entre IES ou entre papéis:** estudantes não podem virar membros da organização IES (a RLS daria acesso a tudo o que
  um membro vê: projetos, documentos, finanças). Mitigação: papéis acadêmicos separados, RLS própria por escopo, testes negativos.
- **Dado de menor de idade:** há calouros com 16–17 anos. A Lei 15.211/2025 (ECA Digital) e o art. 14 da LGPD pedem configurações
  mais protetivas por padrão. Mitigação: nada público por padrão, sem geolocalização, sem perfilamento; a IES informa se a turma
  pode ter menores (§ requisitos).
- **Regulação:** o kit exige não prometer conformidade. A plataforma organiza e documenta; a validação é da IES.
- **Comercial:** ADR-341 proíbe assinatura/mensalidade. A licença institucional precisa caber no que existe (convênio + concessão
  + contrato avulso/parcelado), sem preço inventado.
- **Integrações:** nenhum sistema acadêmico foi avaliado. Nada pode aparecer como "conectado".
- **Tamanho:** o pedido cobre o equivalente a vários módulos grandes. Ver o plano em incrementos (`DECISIONS_IES.md`, D-12).

## 6. O que será reutilizado, ampliado, criado ou deixado de fora

Detalhe linha a linha em `GAP_MATRIX_IES.csv`; decisões e alternativas em `DECISIONS_IES.md`.

- **Reutilizar:** login, MFA, step-up, sessões, convites (padrão de token), auditoria, RLS, documentos (antivírus, PDF, URL assinada),
  evidências, dossiê, indicadores, programas/projetos, registro verificável/QR, padrão anti-robô, concessões/convênios, controle de IA.
- **Ampliar:** `/portal` e `dashboard_for` (área acadêmica), menu por contexto, catálogo de natureza jurídica, concessões (assento
  por pessoa), exportação (função única contra fórmula).
- **Criar:** perfil institucional IES, licença acadêmica com assentos, estrutura acadêmica (campus, curso, período, componente,
  oferta), vínculos acadêmicos com escopo, convite acadêmico, avaliador externo temporário, importação acadêmica de roteiro
  (roster) com prévia, ação de extensão, equipe, horas, entregas com pedido de ajuste, dossiê do estudante, retorno da comunidade
  por link/QR, ciclo e passagem de bastão, catálogo de conectores acadêmicos com status honesto.
- **Fora do escopo da v0.36.0 (planejado, não esquecido):** conectores reais com ERP/Moodle (exigem acesso e homologação),
  LTI e SAML, Radar de Pesquisa e Fomento (v0.38.0+), IA assistiva sobre plano de ensino (exige provedor real autorizado).
