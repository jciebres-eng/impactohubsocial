# DESIGN_HANDOFF — o que a próxima etapa (UI/UX) recebe

**Versão da baseline:** 0.15.0 · **Branch:** `chore/v0.15.0-final-pre-design-hardening` · **Documentos técnicos:** `FINAL_PRE_DESIGN_HARDENING_REPORT.md` (este ciclo) + `CORE_PRODUCT_ARCHITECTURE.md` + `FINAL_TECHNICAL_BASELINE.md` (base v0.12.1) + `FINAL_INTEGRATION_HARDENING_REPORT.md` (integração) + `FINAL_TRUST_HARDENING_REPORT.md` (confiança, identidade e assinatura).

> **Leitura mínima antes de começar:** este arquivo, `CORE_PRODUCT_ARCHITECTURE.md` (como as peças se ligam) e a
> seção 13 abaixo (**fluxos do produto A–I** e **invariantes de design**). O resto é referência.

A camada funcional está fechada e testada. Esta etapa é de **design**: identidade visual, sistema de design, componentes, layout, onboarding visual, dashboards, UI web e mobile. **Não é necessário reimplementar backend, banco, autenticação, permissões ou cobrança** — e, se algo parecer faltando, confira primeiro a seção “Pendências que NÃO são bugs”.

## 1. O que está pronto (e provado por teste)
| Camada | Estado | Onde está |
|---|---|---|
| API REST `/v1` | 574 operações, contrato estável, OpenAPI gerado do código | `docs/API.md`, `docs/openapi.json`, `GET /v1/openapi.json` |
| Banco | PostgreSQL 16, 191 tabelas, RLS em todas (exceto `schema_migrations`), 12 migrations forward-only | `KNOWLEDGE_DATA_MODEL.md`, `docs/DATABASE.md` |
| Autenticação | sessão por cookie httpOnly (web) **ou** Bearer (app nativo), refresh rotativo, MFA TOTP, OIDC opcional | `src/api.ts`, `src/session.tsx` |
| Autorização | por rota: `auth` (none/user/org/admin), tipo de organização, papel mínimo, papéis internos, entitlements | `backend/impacto/http.py` |
| Multi-tenant | isolamento por RLS no banco, provado inclusive por SQL direto | `tests/test_security_tenancy.py` |
| Cobrança/trial/vouchers | trial de 14 dias, tiers, vouchers, convênios, licenças, webhooks idempotentes (Stripe **dublê**) | `docs/billing.md` |
| Central de Conhecimento | busca, guias, biblioteca, FAQ, assistente ancorado, academia, eventos, suporte com SLA, parcerias, CMS editorial | `KNOWLEDGE_HUB.md` |
| Integração (hub) | 13 tabelas, 36 rotas, 9 provedores, webhooks (entrada e saída), importação/exportação, jobs com repetição e disjuntor — **sem tela** | `INTEGRATION_HUB.md` |
| Confiança/identidade/assinatura | verificação pública, assinatura em duas camadas, custódia, identidade, credenciais, acordos, cotas, taxonomia, idioma e tema — **com telas básicas já implementadas** | `TRUST_ARCHITECTURE.md` |
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

---

## 12. Camada de confiança (v0.14.0) — telas **existem**, mas são funcionais, não desenhadas
Diferente da camada de integração (§11, que continua **sem nenhuma tela**), a camada de confiança já tem interface
funcional construída com o kit atual, sem redesign, sem animação e sem token de cor novo. O que o designer recebe aqui é
**fluxo validado e invariantes travados por teste** — o trabalho é de linguagem visual, hierarquia e ritmo, não de
descobrir o que a tela precisa fazer.

### 12.1 Telas implementadas
| Rota | O que é | Observação para o design |
|---|---|---|
| `/verificar` e `/verificar/:code` | **página pública** de verificação (sem login) | é a tela mais exposta do produto: um terceiro que não conhece a marca vai cair direto nela. Merece o maior cuidado. |
| `/campanha/:slug` | campanha pública com "faltam N cotas" | idem: página de entrada para doador/apoiador |
| `/identidade` | nível de identidade, pedidos e documentos | |
| `/verificacoes` | códigos públicos da organização, com contador de consultas e revogação | |
| `/acordos`, `/acordos/novo`, `/acordos/:id` | acordos multiassinatura com partes, assinatura e entregas | |
| `/cotas`, `/cotas/:id/apoios`, `/campanha-gestao` | cotas e campanha | |
| `/minhas-atividades` | catálogo do profissional | |
| `/conta/preferencias` | idioma e tema | |
| `/admin/identidade`, `/admin/credenciais-profissionais`, `/admin/honorarios` | filas da equipe | |
| `/diagnosticos/:id/roteiro` | diagnóstico guiado em 8 etapas | |
| Componentes | `SignBox` (assinatura em duas camadas), `ImpactTags` (ODS/ESG/determinantes), `QuotaProgress` | reutilizáveis |

### 12.2 Estados a desenhar (listas fechadas)
- **Registro público:** `active` · `superseded` (existe versão mais nova) · `revoked` · `expired`.
- **Integridade:** intacta · hash diferente do registrado · **arquivo guardado não confere** (três mensagens diferentes).
- **Identidade:** `none` · `email` · `phone` · `document` · `professional` · `biometric`; pedido em `pending` ·
  `under_review` · `verified` · `rejected` · `expired` · `revoked`.
- **Credencial:** `self_declared` · `document_submitted` · `verified` · `rejected` · `expired`.
- **Acordo:** `draft` · `awaiting_signatures` · `active` · `completed` · `canceled` · `expired`; parte: pendente ·
  assinou · recusou.
- **Cota:** `draft` · `open` · `paused` · `closed`; apoio: `pledged` · `confirmed` · `canceled` · `refunded`.
- **Campanha:** `draft` · `published` · `closed`. **Etapa do diagnóstico:** `pending` · `in_progress` · `complete` · `skipped`.
- **Tema:** `system` · `light` · `dark`. **Idioma:** `pt-BR` (100%) · `en` e `es` (núcleo).

### 12.3 Invariantes que o design NÃO pode suavizar
1. **A página pública não ganha dado pessoal.** Nome de pessoa aparece só em assinatura profissional com credencial
   verificada. Há teste que falha se e-mail, identificador ou nome de representante aparecerem no corpo.
2. **"Credencial verificada" = documento conferido pela equipe.** A frase "a plataforma não consulta o conselho
   profissional on-line" precisa continuar visível. Não trocar por um selo verde sozinho.
3. **"Não é assinatura qualificada".** Toda tela de assinatura diz isso. Pode ser restilizado, nunca removido.
4. **Biometria, SMS e carimbo de ACT recusam.** As mensagens explicam a dependência externa — são informação, não erro
   feio para esconder.
5. **Revogado é revogado.** Estado visualmente inequívoco, com motivo e data. Nunca um aviso discreto.
6. **Versão assinada × versão atual.** Quando divergem, a tela precisa dizer que existe versão mais nova — é a diferença
   entre conferir o documento certo e o errado.
7. **"A plataforma não estima honorário"** e **"o valor da cota é definido pela organização"**: nada de sugestão de preço.
8. **Marcadores ODS usam a cor oficial, nunca o emblema da ONU** (marca protegida — ver `SDG_ESG_TAXONOMY.md`).
9. **Consentimento de localização** é explícito e datado; a precisão (exata/aproximada/cidade) precisa estar visível.
10. **Etapas do diagnóstico são hipótese editorial** — o aviso fica.

### 12.4 Onde o design agrega mais
- **Página pública de verificação**: hoje é uma lista de painéis. Merece um veredito visual imediato (genuíno/revogado/
  integridade) antes de qualquer detalhe, e uma versão de impressão.
- **Assinatura em duas camadas**: hoje é um modal com dois passos. É o momento mais tenso do produto e ganha muito com
  ritmo e microcopy.
- **QR e código no PDF**: o layout atual é funcional; o documento impresso é peça de comunicação.
- **Filas da equipe** (identidade, credenciais): trabalho repetitivo que pede densidade e atalhos.
- **Campanha pública**: é peça de captação — hoje é honesta e sem graça.

### 12.5 Pedido do proprietário registrado para esta etapa
O proprietário pediu, para a etapa de design: **menus suspensos retráteis selecionáveis horizontais** e **uma grande área
de trabalho em vez de menus laterais**. Isso **não foi implementado de propósito** — é reestruturação de navegação, ou
seja, design, e esta etapa era de engenharia (o próprio escopo dizia "não faça redesign"). A navegação atual
(`NAV` em `web/src/app.tsx`, por tipo de organização) está pronta para ser reorganizada: as rotas são independentes do
menu, então mudar a estrutura de navegação não exige tocar em página nenhuma.
Observação técnica para quem for fazer: a lista de itens por perfil já passou de 15 em alguns casos (OSC tem 20), o que
é um argumento real a favor do agrupamento horizontal com submenus.



---

# 13. v0.15.0 — o núcleo do produto (telas FUNCIONAIS, ainda sem design)

A v0.15.0 fechou o núcleo: ideia → diagnóstico → projeto → documento → match → acompanhamento, com evidência,
versões e trilha. As telas existem, funcionam e estão testadas no navegador — mas foram escritas com o mesmo kit e
os mesmos tokens das anteriores, **sem nenhuma decisão de design**. É exatamente aqui que a designer entra.

**O que a engenharia deliberadamente NÃO fez nesta etapa** (e não é esquecimento): identidade visual, sistema de
design, paleta, tipografia, animação, reorganização de navegação, dashboards, ilustração, onboarding visual.

## 13.1 Telas novas (e o estado em que estão)

| Rota | O que faz | Estado |
|---|---|---|
| `/ideias` | lista e anota ideias; "Transformar em projeto" | funcional, sem desenho |
| `/prontidao` | leitura de prontidão da organização (FATO / INFERÊNCIA / RECOMENDAÇÃO / DESCONHECIDO) | funcional — **candidata número 1 a dashboard** |
| `/projetos/:id/situacao` | situação atual, transições possíveis, histórico | funcional — **candidata a diagrama de fluxo** |
| `/projetos/:id/linha-do-tempo` | trilha encadeada, com integridade | funcional — **candidata a linha de tempo visual** |
| `/projetos/:id/retratos` | retratos e comparação campo a campo | funcional — comparação hoje é lista |
| `/projetos/:id/riscos` | riscos declarados e apontados por regra | funcional — **candidata a matriz probabilidade × impacto** |
| `/diagnosticos/:id/versoes` | versões imutáveis, o que mudou, ações | funcional — **candidata a evolução no tempo** |
| `/documentos/montagens` | montagens abertas, com completude | funcional |
| `/documentos/montagens/:id` | preenchimento seção a seção, bloqueio, geração, revisão | funcional — **a tela mais importante do produto para a OSC** |
| `/documentos/modelos` | modelos disponíveis e a fonte de cada um | funcional |
| `/assinatura/provedores` | provedores e o estado real de cada um | funcional |
| `/assinatura/politica` | política de assinatura por tipo de documento | funcional |
| `/admin/chaves` | inventário de chaves e rotação | funcional |

Links de entrada já existem: do projeto (bloco "Aprofundar"), do diagnóstico (cabeçalho) e do cofre de documentos.

## 13.2 FLUXOS CENTRAIS DO PRODUTO (A–I)

São os caminhos que a designer precisa desenhar como **um percurso**, não como telas soltas. Cada um já funciona
ponta a ponta e tem jornada de teste correspondente (`backend/tests/test_e2e_v0150_journeys.py`).

### A. Da ideia ao projeto
`/ideias` → anotar → amadurecer (`raw` → `shaping` → `ready`) → **Transformar em projeto** → `/projetos/:id`

A ideia **não desaparece**: fica marcada como "Virou projeto" e aponta para ele; o projeto guarda a origem.
O desenho precisa deixar isso visível — é a diferença entre "um lixo de anotações" e "a história do projeto".

### B. Diagnóstico como processo, não formulário
`/diagnosticos` → `/diagnosticos/:id/roteiro` (etapas) → `/diagnosticos/:id/versoes` → congelar versão → ações

O que o desenho precisa resolver: mostrar **completude por dimensão** (8 dimensões com peso diferente), separar
lacuna de desconhecido, e dar peso visual ao "o que mudou desde a última versão".

### C. Estruturar o projeto
`/projetos/:id` → orçamento e marcos → indicadores (`/projetos/:id/impacto`) → riscos → situação

Hoje são abas e links. O percurso natural é um progresso guiado com o que falta sempre à vista.

### D. Montar documento
`/documentos/montagens` → escolher modelo → preencher por seção → anexar evidência → **gerar** → revisão (4 olhos) → assinar

A tela de montagem é onde a OSC passa mais tempo. Pontos de atenção para o desenho:
- **campo derivado** (vem do projeto) tem que parecer diferente de campo digitado, e dizer onde se corrige;
- **o que falta** precisa estar visível ao lado do que foi feito, não em uma aba separada;
- **o botão de gerar desabilitado** precisa dizer por quê sem a pessoa precisar procurar.

### E. Publicar e captar
`/projetos/:id` → publicar → `/projetos/:id/situacao` (`published` → `funding`) → `/cotas`, `/campanha-gestao`

### F. Match nas duas direções
- OSC: `/oportunidades` → detalhe → candidatura assistida
- Financiador: `/explorar` → detalhe do projeto → retorno sobre a recomendação

O desenho do resultado de match é delicado e está detalhado em 13.3: pontuação, confiança, bloqueio, porquê,
o que falta e próxima ação são **seis coisas diferentes** e hoje aparecem no mesmo bloco.

### G. Executar e comprovar
`/projetos/:id` → execução → evidências → despesas → indicadores medidos e validados → relatórios

### H. Acompanhar no tempo
`/projetos/:id/retratos` (congelar) → comparar dois retratos → `/projetos/:id/linha-do-tempo` → integridade

Este é o fluxo que vende a plataforma para um financiador: "o que mudou entre março e setembro, com prova".
Hoje é funcional e feio; é onde o desenho tem mais a ganhar.

### I. Provar para terceiro
documento → assinatura em duas camadas → `/verificacoes` → código → `/verificar/:code` (**sem login**)

A página pública é a única que uma pessoa de fora vê. Hoje funciona e é sóbria; merece ser a mais bem desenhada do
produto.

## 13.3 Invariantes de design — o que o desenho NÃO pode fazer

Não são preferências. São afirmações que a plataforma sustenta com código e teste, e que a interface pode
**restilizar à vontade** mas não pode suavizar, esconder nem contradizer. Os testes de navegador em
`backend/tests/test_e2e_v0150_web.py` conferem parte disto, e a lista inteira vale como contrato.

1. **Não esconder bloqueio.** Montagem bloqueada mostra o que falta; transição recusada mostra para onde é
   possível ir; match bloqueado mostra o bloqueio. Botão desabilitado sem motivo visível é defeito.
2. **Não esconder risco.** Risco apontado por regra aparece marcado como **apontado por regra**, nunca como
   veredito, e nunca sumido porque "deixa a tela feia".
3. **Não esconder evidência que falta.** `missing_data`, `missing_evidence` e `unknown` são conteúdo, não ruído.
4. **"Não sei" ≠ "está ruim".** `unknown` precisa ficar visualmente separado de lacuna. Pintar desconhecido de
   vermelho é mentir sobre a organização.
5. **Pontuação alta com confiança baixa NÃO é recomendação.** Quando `confidence < 50`, a API já devolve
   `score: null`. O desenho não pode reintroduzir um número onde a API recusou dar um.
6. **Confiança e pontuação são eixos diferentes.** Não podem virar uma estrela só.
7. **Não esconder revogação.** Assinatura revogada aparece como revogada, com o motivo, na verificação pública.
8. **Versão assinada ≠ versão atual.** Documento com versão nova mostra `superseded` e as duas versões.
9. **Não chamar declaração de verificada.** "Informado pela organização" e "conferido pela plataforma" precisam ser
   visualmente distintos — a API já entrega `source` e `verified` em toda evidência.
10. **Não chamar assinatura simples de qualificada.** O rótulo vem de `legal_level`; a plataforma entrega
    **avançada**. Ver `SIGNATURE_VALIDATION_MATRIX.md`.
11. **Não chamar Gov.br de ICP-Brasil.** São níveis jurídicos diferentes, e os dois estão **indisponíveis** hoje.
12. **Não esconder indisponibilidade de provedor.** `unavailable` aparece com a dependência que falta.
13. **Não esconder erro de integração.** Falha de conexão, circuito aberto e carta morta são estado do sistema que a
    organização precisa ver.
14. **Não mostrar dado privado na verificação pública.** A página pública mostra só `public_fields`.
15. **Meta atingida não é impacto.** Produto, resultado e impacto são três níveis (`result_kind`) e não podem virar
    um só número "de impacto".
16. **Não apresentar estimativa fiscal como garantia.** O aviso "não é parecer jurídico" fica.
17. **Não inventar preço.** Tabela de honorário sem fonte não existe; o desenho não preenche o vazio com faixa
    plausível.
18. **Ação apontada por regra vem marcada como tal** e nunca se confunde com ação que a equipe criou.
19. **Documento gerado mostra a completude do momento da geração.** O rodapé já traz isso.
20. **Retorno sobre recomendação não muda a nota.** O desenho não pode sugerir que "curtir" melhora o match.

## 13.4 Onde o desenho agrega mais nesta versão

Em ordem de retorno:

1. **`/documentos/montagens/:id`** — é onde a OSC passa mais tempo e onde o produto mais se diferencia. Resolver
   "o que falta × o que está feito × o que vem do projeto" em uma tela é o maior ganho disponível.
2. **`/prontidao`** — hoje são painéis empilhados. É o melhor candidato a dashboard de verdade, com as 8 dimensões.
3. **Resultado de match** — seis informações diferentes em um bloco. Separar pontuação, confiança, bloqueio, porquê,
   o que falta e próxima ação muda a qualidade da decisão de quem financia.
4. **`/projetos/:id/retratos` + linha de tempo** — a narrativa "o que mudou" é o argumento de venda para
   financiador, e hoje é uma lista de campos.
5. **`/projetos/:id/situacao`** — 17 situações e 58 transições pedem um diagrama, não um `select`.
6. **Riscos** — matriz probabilidade × impacto é um padrão conhecido e a plataforma já tem os dois eixos.
7. **Navegação** — o pedido do proprietário (menus horizontais retráteis, grande área de trabalho) continua
   pendente de propósito, e a lista por perfil cresceu de novo nesta versão (OSC tem 24 itens).

## 13.5 O que o desenho pode mudar sem pedir

- Qualquer coisa visual: cor, tipografia, espaçamento, ícone, ilustração, animação, sombra, raio.
- Estrutura de navegação, agrupamento, ordem dos itens, hierarquia de páginas.
- Como um estado é **apresentado** (chip, cor, ícone, posição), desde que o estado continue visível.
- Texto de interface escrito por nós (não os textos de erro que vêm da API, que já são em português).
- Layout de qualquer tela, inclusive quebrar uma em várias ou juntar várias em uma.

## 13.6 O que exige combinar antes

- Mudar contrato da API (caminho, nome de campo, código de erro).
- Remover ou suavizar qualquer um dos 20 invariantes de 13.3.
- Mudar rótulo de nível jurídico, de origem de evidência ou de maturidade de integração.
- Apresentar como pronto algo que `HOMOLOGATION_MATRIX.md` lista como `scaffolded` ou `contract_tested`.
