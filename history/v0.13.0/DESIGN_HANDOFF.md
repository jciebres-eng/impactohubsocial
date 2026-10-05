# DESIGN_HANDOFF — o que a próxima etapa (UI/UX) recebe

**Versão da baseline:** 0.13.0 · **Branch:** `chore/integration-hub-foundation` · **Documento técnico completo:** `FINAL_TECHNICAL_BASELINE.md` (base v0.12.1) + `FINAL_INTEGRATION_HARDENING_REPORT.md` (camada de integração).

A camada funcional está fechada e testada. Esta etapa é de **design**: identidade visual, sistema de design, componentes, layout, onboarding visual, dashboards, UI web e mobile. **Não é necessário reimplementar backend, banco, autenticação, permissões ou cobrança** — e, se algo parecer faltando, confira primeiro a seção “Pendências que NÃO são bugs”.

## 1. O que está pronto (e provado por teste)
| Camada | Estado | Onde está |
|---|---|---|
| API REST `/v1` | 511 operações, contrato estável, OpenAPI gerado do código | `docs/API.md`, `docs/openapi.json`, `GET /v1/openapi.json` |
| Banco | PostgreSQL 16, 165 tabelas, RLS em todas (exceto `schema_migrations`), 11 migrations forward-only | `KNOWLEDGE_DATA_MODEL.md`, `docs/DATABASE.md` |
| Autenticação | sessão por cookie httpOnly (web) **ou** Bearer (app nativo), refresh rotativo, MFA TOTP, OIDC opcional | `src/api.ts`, `src/session.tsx` |
| Autorização | por rota: `auth` (none/user/org/admin), tipo de organização, papel mínimo, papéis internos, entitlements | `backend/impacto/http.py` |
| Multi-tenant | isolamento por RLS no banco, provado inclusive por SQL direto | `tests/test_security_tenancy.py` |
| Cobrança/trial/vouchers | trial de 14 dias, tiers, vouchers, convênios, licenças, webhooks idempotentes (Stripe **dublê**) | `docs/billing.md` |
| Central de Conhecimento | busca, guias, biblioteca, FAQ, assistente ancorado, academia, eventos, suporte com SLA, parcerias, CMS editorial | `KNOWLEDGE_HUB.md` |
| Integração (hub) | 13 tabelas, 36 rotas, 9 provedores, webhooks (entrada e saída), importação/exportação, jobs com repetição e disjuntor — **sem tela** | `INTEGRATION_HUB.md` |
| Frontend atual | React 19 + TypeScript, roteador próprio, PWA, build esbuild (180 KB gzip), 0 erros de console em 25 páginas/viewports | `web/src` |
| Acessibilidade base | rótulos, foco visível, `lang`, sem IDs duplicados, sem salto de cabeçalho, contraste **AA** em tema claro e escuro | `tests/test_e2e_knowledge.py` |

## 2. O que NÃO deve ser alterado (sem combinar antes)
1. **Contratos da API** (caminhos, nomes de campos, códigos de erro). O frontend é substituível; a API é o contrato.
2. **Fluxo editorial de conteúdo** (rascunho → revisão → aprovado → publicado) e o **princípio dos quatro olhos** — garantidos no banco, não na tela.
3. **Rótulos de honestidade**: selo “Exemplo / rascunho — não é documento oficial”, rótulo de origem, aviso “certificado não oficial”, aviso de “revisão necessária”, textos de recusa do assistente. Podem ser **restilizados**, nunca removidos nem suavizados.
4. **Avisos de limite**: “preço não definido”, “cobrança em modo de testes”, “meta interna, não é garantia contratual” (SLA), “não é parecer jurídico”.
5. **Decisões de segurança visíveis na UI**: MFA na administração, confirmação de e-mail para ações sensíveis, consentimento obrigatório nos formulários públicos, campo-isca anti-bot (`website`, invisível — manter), `noindex` em conteúdo privado/demo.
6. **Textos de erro vindos da API** (`describeError` em `src/api.ts`): a API já devolve mensagem em português pronta para exibir.

## 3. Rotas da interface (todas já implementadas)
- **Públicas (sem login):** `/entrar`, `/cadastro`, `/verificar-email`, `/esqueci-senha`, `/redefinir-senha`, `/convite`, `/legal/termos`, `/legal/privacidade`.
- **Central, pública:** `/ajuda`, `/ajuda/busca`, `/ajuda/:slug`, `/ajuda/biblioteca[/:slug]`, `/ajuda/faq[/:id]`, `/ajuda/academia[/:slug]`, `/ajuda/certificado/:code`, `/ajuda/eventos[/:slug]`, `/ajuda/parcerias`, `/ajuda/demonstracao`, `/ajuda/boletim[/confirmar|/cancelar]`.
- **Central, com login:** `/ajuda/comece-aqui`, `/ajuda/pendencias`, `/ajuda/atividades`, `/ajuda/preferencias`, `/ajuda/suporte[/novo|/:id]`, `/ajuda/academia/aula/:id`, `/ajuda/teste`.
- **Produto:** início, projetos, editais/oportunidades, candidaturas, documentos, rascunhos, instituição, compliance, equipe, conta, plano, pagamentos, extratos, relatórios, mapa, mensagens, soluções, diagnósticos, impacto, conquistas.
- **Administração:** `/admin*` (compliance, credenciais, editais, fiscal, vouchers, convênios, cobrança, usuários, organizações, denúncias, auditoria, risco, erros) e `/admin/central/*` (CMS, suporte, parcerias, testes, indicadores, equipe editorial).
A navegação (`NAV` em `src/app.tsx`) é **por tipo de organização** (osc, company, individual, provider, government, platform). A administração aparece quando a organização ativa é a plataforma; papéis internos (editor/revisor/suporte) veem o atalho “Central (equipe)”.

## 4. Componentes e padrões existentes
`src/ui/kit.tsx`: `useLoad` (dados), `useAction` (ação + toast + erro), `StateView` (carregando/erro/vazio), `Button`, `Field`, `Group`, `Input`, `TextArea`, `Select`, `Chips`, `Pill`, `Panel`, `PageHead`, `Modal`, `KeyValue`, `Pager`, `Bars`, `MoneyFlow`, `useForm`, `ToastProvider`.
`src/format.ts`: `money` (centavos → BRL), `date`, `dateTime`, `pct`, `label` (estado → rótulo em português), `MATCH_STATE`.
`src/pages/help.tsx` exporta `ContextHelp` (botão “Preciso de ajuda” por tela) e `PublicFrame` (moldura das páginas públicas).
Tokens visuais em `src/styles.css` (`:root` + bloco `prefers-color-scheme: dark`). **Trocar tokens é o caminho natural do redesign**; `--texto-3` precisa manter contraste ≥ 4.5:1 sobre `--papel` (há teste automático).

## 5. Estados que a UI já trata (preserve-os)
- **Carregando**: `StateView loading` (esqueleto de três pontos).
- **Erro**: `StateView error` com mensagem da API + “Tentar novamente”.
- **Vazio**: `StateView empty` com texto específico por tela (não inventar dado).
- **Sessão expirada**: `api.ts` tenta renovar uma vez em 401; se falhar, `onSessionLost` → volta para `/entrar?proximo=…`.
- **Sem organização ativa**: tela de criar/entrar em organização.
- **Área indisponível para o perfil** e **404 de rota**: componente `NotHere`.
- **E-mail não confirmado**: faixa fixa com reenvio de link.
- **Ação sem permissão**: a API devolve 403 com código (`insufficient_role`, `wrong_org_kind`, `email_not_verified`, `mfa_required`) — o toast já mostra o motivo.

## 6. Dados esperados pela UI (formatos)
- **Dinheiro**: inteiro em **centavos** (`amount_cents`), nunca float. Use `money()`.
- **Datas**: ISO 8601 **com fuso** (`2026-10-05T16:59:32+00:00`). Use `date()`/`dateTime()`.
- **Listas paginadas**: `{items, limit, offset, has_more, next_offset}` → componente `Pager`. Limite máximo 100 por página.
- **Erros**: `{type, title, status, code, request_id}` (+ `details`, + `error_id` em erro interno). Exiba `title`; `request_id`/`error_id` servem ao suporte.
- **Estados de domínio** chegam como chave técnica (`in_review`, `past_due`…) — traduza com `label()`/`Pill`.

## 7. Cobrança, trial e Central (o que a tela pode e não pode afirmar)
- O **servidor** calcula preço, desconto, trial e direitos. O cliente envia `plan_key`/`interval`/`voucher`; campos extras são **rejeitados com 422** (não tente mandar preço).
- **Planos pagos estão sem preço** (`price_not_defined`): a UI deve oferecer proposta comercial/voucher, nunca um valor inventado.
- **Stripe real nunca foi chamado**: o modo atual é dublê/sandbox. A faixa “cobrança em modo de testes” existe por isso.
- **Conteúdo da Central é todo de exemplo** (`demo=true`): 14 guias, 8 FAQs, 4 materiais, 1 curso, 1 evento. O selo de exemplo precisa continuar visível.
- **Assistente não usa IA generativa**: responde com trecho publicado + fonte, ou recusa. Não o apresente como “IA”.
- **Certificados não são oficiais**: o aviso aparece no curso e na verificação pública.

## 8. Mobile / app
A API está pronta para cliente nativo: Bearer token (`X-Auth-Mode: token`), refresh rotativo, CORS por allowlist (`CORS_ORIGINS`), upload/download por URL temporária assinada, paginação e erros previsíveis. Capacitor está configurado em `mobile/` (`setup.sh`), com armazenamento de token em `src/native.ts`. **Nenhum app foi compilado, assinado ou publicado** — isso é etapa posterior.

## 9. Pendências que NÃO devem ser confundidas com bugs
1. **Sem conteúdo oficial real** na Central e **sem regra fiscal aprovada** — depende de redação e revisão humana/jurídica.
2. **Planos sem preço** e **sem nota fiscal** — decisão comercial/fiscal do proprietário.
3. **Sem IA generativa e sem embeddings** — decisão de produto; a busca usa vocabulário de assuntos.
4. **SLA inicial é hipótese** (ajustável pela administração) e **SMTP real não foi exercitado** (outbox provado).
5. **Editor do CMS por JSON** para curso/material/FAQ/evento (guias têm formulário completo) — candidato natural a melhoria de UX nesta próxima etapa.
6. **Curso publicado não é editado no lugar** (nova versão) — regra editorial, não defeito.
7. **Botão de ajuda contextual (`ContextHelp`) ligado em 3 telas** (Documentos, Novo projeto, Verificação do cadastro); as chaves das demais telas já existem no conteúdo e na API — ligar as outras é trabalho de UI.
8. **Bundle único de 180 KB gzip, sem code splitting** — aceitável hoje; se o design crescer, divida por rota.
9. **Auditoria de dependências (`npm audit`/`pip-audit`) não executada**: os registries npm e PyPI estão bloqueados neste ambiente (403/sem versões). Rode em CI.
10. **Sem axe nem leitor de tela**: a verificação de acessibilidade é própria (rótulos, foco, contraste, cabeçalhos, IDs). Uma auditoria formal continua necessária.

## 10. Como rodar e como não quebrar
```
make db                  # recria o banco de desenvolvimento (migrations do zero)
make test                # suíte completa (Postgres real + HTTP real + navegador)
cd web && node build.mjs # build da SPA/PWA
cd web && node node_modules/typescript/bin/tsc -p tsconfig.offline.json --noEmit
cd backend && ruff check impacto tests
```
Antes de abrir um PR de design: `tsc` + build + `make test` verdes. Se um teste de acessibilidade ou de contraste falhar, **o design mudou um invariante** — ajuste o token, não o teste.

## 11. Camada de integração (v0.13.0) — **API pronta, interface inexistente**
A v0.13.0 acrescentou o hub de integrações **sem nenhuma tela**. É o maior bloco de UI novo desta próxima etapa. Detalhes em `INTEGRATION_HUB.md` (conceitos, estados, rotas) e `INTEGRATION_OPERATIONS.md` (painel de operação).

### 11.1 Entidades que a UI precisa representar
Provedor · Conexão (organização × provedor × ambiente) · Credencial (só a dica, `••••4f2a`) · Mapeamento de campos · Correspondência de ID externo · Job · Evento · Assinatura de webhook · Entrega · Entrada (webhook recebido) · Importação de arquivo · Exportação.

### 11.2 Estados a desenhar (lista fechada — não inventar outros)
- **Conexão:** `draft`, `active`, `paused`, `revoked`.
- **Saúde:** `unconfigured`, `unknown`, `healthy`, `degraded`, `unauthorized`, `unavailable` (+ “disjuntor aberto até HH:MM”).
- **Job:** `pending`, `running`, `succeeded`, `partial`, `retrying`, `failed`, `canceled` — com distinção visível entre erro **temporário** (vai repetir sozinho) e **permanente** (exige ação humana).
- **Entrega:** `pending`, `delivered`, `retrying`, `dead_letter`, `skipped`.
- **Entrada:** `received`, `processed`, `ignored`, `rejected`, `duplicate`.
- **Correspondência:** `linked`, `pending`, `conflict`, `stale`, `deleted_externally`.
- **Importação:** `uploaded`, `validated`, `parsed`, `previewed`, `approved`, `imported`, `rejected`, `failed`.
- **Maturidade do provedor:** `scaffolded`, `contract_tested`, `sandbox_validated`, `homologated`, `production_active`.
- **Ambiente:** `development`, `sandbox`, `homologation`, `production`.

### 11.3 Telas necessárias (nenhuma existe hoje)
1. **Catálogo de provedores** — cartões com capacidades e **selo de maturidade honesto**.
2. **Lista de conexões** — por ambiente, com saúde, última execução e “o que está quebrado”.
3. **Nova conexão / configuração** — formulário dirigido por `config_problems` (a API devolve os problemas em português).
4. **Credencial** — formulário que escreve e nunca lê; exibir apenas a dica, com “substituir” e “remover”. Nunca mostrar campo preenchido com o segredo.
5. **Mapeamento de campos** — campo externo → canônico, transformação escolhida numa lista fechada de 12, obrigatoriedade, prévia.
6. **Saúde e diagnóstico** — botão “Testar conexão” (não destrutivo), histórico, detalhe do erro.
7. **Jobs** — lista filtrável, detalhe com tentativas, tipo de erro, correlação e **trilha de auditoria**; ações: cancelar, reenfileirar.
8. **Correspondências e conflitos** — fila de conflitos com decisão humana explícita (**nada é sobrescrito em silêncio**).
9. **Webhooks de saída** — assinaturas, eventos (catálogo de 26), segredo, teste de entrega, fila de dead-letter com “reenviar”.
10. **Importação de arquivo** — enviar (CSV/XLSX), prévia com erro linha a linha, aprovação explícita; JSON/XML respondem 422 com explicação (mostrar a mensagem, não escondê-la).
11. **Exportação** — escolher dataset e baixar pelo documento gerado.
12. **Painel de operação (administração)** — saúde agregada, conexões quebradas, jobs 24 h, dead-letters, profundidade da fila, importações aguardando aprovação, latência p50/p95 por provedor.

### 11.4 Padrões obrigatórios nessas telas
- **Segredo nunca aparece.** Nem em formulário, nem em log, nem em “copiar configuração”.
- **Ambiente sempre visível.** `production` deve ser visualmente distinto; promover = criar outra conexão, nunca “mudar a chave”.
- **Erro temporário × permanente** precisa ser legível sem abrir detalhe: um vai se resolver sozinho, o outro não.
- **Maturidade não pode ser maquiada.** `scaffolded` e `technically_ready` não podem parecer “pronto”. O adapter de governo **recusa agir** fora de `production_active` — a tela deve explicar isso, não escondê-lo.
- **Conflito exige decisão.** Nunca um botão “resolver tudo” que sobrescreve.
- **Aprovação de importação é humana** (papel `owner`) e só aplica linhas válidas.
- Estados de carregando/vazio/erro/repetindo já têm equivalente no `StateView` do kit atual.

### 11.5 O que NÃO desenhar como pronto
SFTP (não implementado), SAML/LDAP, WhatsApp/SMS/push, integração oficial Gov.br/Conecta (exige credenciamento), qualquer provedor como “homologado”. Nenhuma integração foi executada contra sistema externo real — só contra dublê.
