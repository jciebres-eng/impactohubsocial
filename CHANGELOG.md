# Changelog
Formato Keep a Changelog. Histórico anterior (v0.1–v0.6): `history/v0.6.0/CHANGELOG.md`; snapshot dos documentos do v0.7.0: `history/v0.7.0/`.

## [0.12.0] — 2026-10-05 — Central de Conhecimento (cumulativo; snapshot do v0.11.0 em `history/v0.11.0/`)
### Adicionado
- **Central de Conhecimento** (`/ajuda`): busca híbrida (FTS + trigrama + assuntos + tela + público, com “por que apareceu”), ajuda contextual, guias com checklist/passos/ação, biblioteca (modelos preenchíveis → rascunho, checklists, documentos, versões), FAQ com votos, **assistente extrativo e ancorado** (recusa quando não há base; sem IA generativa), “Comece aqui” e pendências **medidos por dados reais**, “Minhas atividades”.
- **Academia**: cursos, quiz corrigido no servidor (gabarito inacessível), trilhas, certificado **não oficial** com verificação pública e revogação.
- **Eventos** (vagas, lista de espera com promoção, link só para inscritas, presença, avaliação, gravação), **suporte** (chamados, SLA com escalonamento, notas internas, recorrência), **parcerias** (CRM) e **demonstração** (públicos, com consentimento e anti-bot), **solicitação de teste** (decisão humana com motivo; reaproveita `org_trials`), **boletim** (duplo opt-in), preferências de notificação.
- **Governança editorial**: fluxo rascunho→revisão→aprovado→publicado→arquivado, **quatro olhos no banco**, versões imutáveis, regulatório exige fonte+data, “Revisão necessária”, histórico, papéis `editor/reviewer/support`.
- **E-mail** para avisos de cobrança, suporte e eventos (job `hub_ops`, respeita preferências, sem repetição) — fecha o pendente “avisos de cobrança só in-app”.
- Migração `0009_v0120_knowledge_hub.sql` (32 tabelas; banco de desenvolvimento: 152). API: **475** operações (+102). Frontend: `/ajuda/*` (público e logado) e `/admin/central/*`.
- Testes: **357** (290 + 62 de domínio + 5 E2E de navegador, 4 jornadas). Documentos: `KNOWLEDGE_HUB`, `USER_GUIDES`, `TRAINING_ACADEMY`, `SUPPORT_SYSTEM`, `PARTNERSHIP_SYSTEM`, `TRIAL_SYSTEM`, `CONTENT_GOVERNANCE`, `KNOWLEDGE_DATA_MODEL`, `STORE_READINESS`.
### Alterado
- **Lint Python**: `ruff` instalado e executado (`docs/evidence/ruff_v0.12.0.log`); ~40 arquivos receberam correções que preservam o comportamento (suíte verde antes e depois).
- `Principal.staff_roles`, `RouteSpec.staff`; `/v1/me` devolve `staff_roles`; `jobs.py` ganhou `hub_ops`.
### Não feito / pendente (declarado)
- **Nenhum conteúdo real**: só exemplos `demo=true`; nenhuma regra fiscal/jurídica aprovada. Sem IA generativa; sem embeddings; pesos de busca e SLA inicial são **hipótese**. Preços, nota fiscal e Stripe real seguem pendentes. Editor de curso/recurso/FAQ/evento é JSON validado. Curso publicado não é editado no lugar. Botão de ajuda contextual ligado em 3 telas. Auditoria de dependências npm/pip **não executada** (rede bloqueada). Sem axe/leitor de tela; apps móveis não compilados.

## [0.11.0] — 2026-10-05 — Monetização SaaS (cumulativo; snapshot do v0.10.1 em `history/v0.10.1/`)
### Adicionado
- **Níveis FREE / PLUS / PREMIUM(FULL) / GOV** (`plans.tier`, `config/plans@1.1`; planos `osc_plus`, `company_plus`, `gov_institutional`) e função central de direitos (`entitlements.effective/get_entitlements/has_access`). Preços **não definidos** (nunca inventados).
- **Trial de 14 dias FULL por organização**, iniciado no cadastro, sem cartão; cancelar mantém o acesso até o fim e não cobra; nada é apagado. Anti-abuso por HMAC de e-mail normalizado e CNPJ (`trial_claims`). Avisos nos dias 1/7/11/13/14, fim, conversão, falha e cancelamento (in-app, sem repetição).
- **Cobrança mensal/anual** com economia real (`plan_prices`), cotação calculada no servidor (`POST /v1/billing/quote`), checkout Stripe com `trial_end` (nunca cobra antes do fim do trial), troca de plano com proration (`/change-plan`), portal do provedor (`/portal`), cancelar/reativar.
- **Webhooks Stripe** idempotentes, assinados e tolerantes a eventos fora de ordem; estados TRIALING/ACTIVE/PAST_DUE/CANCELED/INCOMPLETE/EXPIRED + `payment_issue` (`payment_failed`/`action_required`).
- **Vouchers** de desconto percentual e valor fixo (duração única/recorrente/permanente), 100% = licença, sem duração = permanente, por plano e por organização. **Licenças** com origem e revogação com motivo. **Convênios/GOV** (código, vagas, período, plano e/ou desconto; domínio só restringe; ativação por 2º admin).
- Admin: vouchers estendidos, convênios, cobrança por organização (licença, revogação, trial, preço do plano). Frontend: `/conta/plano` (alias `/settings/billing`) reescrita — alternância mensal/anual, cotação, trial, cancelamento com confirmação, voucher, convênio, faturas.
- Migração `0008_v0110_monetization.sql` (6 tabelas: `plan_prices`, `org_trials`, `trial_claims`, `billing_notices`, `agreements`, `agreement_members`; colunas novas; RLS e gatilho `billing_guard`). API: **373** operações. Banco de desenvolvimento: **120** tabelas.
- +34 testes (290 no total) em `test_v0110_monetization.py`. Documentação: `docs/billing.md`.
### Alterado (comportamento)
- Cancelar assinatura (sandbox/manual) mantém o acesso até o fim do período pago (antes: imediato). `invoice.paid` com valor > 0 converte o trial e confirma o plano.
- Job `billing_lifecycle` (lembretes, fim de trial, conversão de assinaturas sandbox, fim de períodos cancelados, limpeza de `trial_claims` > 24 meses).
### Não feito / pendente (declarado)
- **Stripe nunca foi chamado de verdade** (só dublê): conta, preços, endpoint do webhook, Billing Portal e homologação são externos. O mínimo de `trial_end` do Checkout (~48 h) **não foi verificado** na API real. Divisão PLUS × PREMIUM é **hipótese**. Avisos só in-app (sem e-mail). Sem nota fiscal/reembolso/chargeback. Sem linter Python.

## [0.10.1] — 2026-10-05 — Pendências institucionais (cumulativo; snapshot do v0.10.0 em `history/v0.10.0/`)
### Adicionado
- **Cruzamento fiscal × elegibilidade institucional**: `GET /v1/insights/fiscal-estimates` aceita `osc_org_id` e devolve `institutional_eligibility` (estado, resumo, o que falta, camadas fiscais) como camada **separada** da estimativa; aviso quando a OSC é NÃO ELEGÍVEL.
- **Perfis OS / OSCIP / OSC / iniciativa em estruturação** (`GET /v1/institutional/persona`): qualificações, autoridade qualificadora, **áreas de atuação** (`areas` em qualificações), instrumentos, alertas de validade (30/90 dias) e próximos passos.
- **Instrumentos** (contrato de gestão, termo de parceria/colaboração/fomento, acordo de cooperação): cadastro **declarado**; verificação só pela administração (número + comprovante validado ou URL oficial + nota).
- **Trilha de formalização** (11 etapas; automáticas derivadas dos dados, manuais só declaradas; `config/formalization_path.json`, hipótese a validar) e **pedidos de mentoria** (limite de taxa e de abertos; atendimento humano).
- **Rede da solução** (`GET /v1/solutions/{id}/network`): autor, território, ODS, temas, soluções relacionadas e demanda **agregada** (sem identidades); visão em lista acessível.
- **Tesauro** de 44 → 67 conceitos (`concepts@1.0+0.10.1`). Alguns termos comuns continuam resolvendo para conceitos mais amplos já existentes (ex.: "creche" → crianças; "primeira infância" → crianças; "teatro" → artes; "alfabetização" → educação) — termos conflitantes foram retirados dos conceitos novos de propósito.
- **Dados DEMO institucionais** no seed (rotulados `[DEMO]`, qualificação **fictícia**; coletivo sem CNPJ).
- Frontend: abas Instituição "OS / OSCIP", "Instrumentos", "Formalização e mentoria"; campo "Áreas de atuação"; admin Institucional "Instrumentos" e "Mentoria"; botão "Ver rede de relações" na solução.
- Migração `0007_v0101_institutional_extras.sql` (3 tabelas: `organization_agreements`, `formalization_steps`, `mentoring_requests`; coluna `areas`; RLS e gatilhos de proteção). API: **358** operações; **114** tabelas.
- +23 testes (256 no total): 17 institucionais, 2 de rede, 1 de tesauro, 3 E2E (inclui **painel admin com MFA real** no Chromium).
### Alterado (comportamento)
- Verificar instrumento sem número/comprovante validado/URL oficial é recusado (422).
### Não feito / pendente (inalterado ou declarado)
- Validação jurídica de catálogos/regras/trilha; **IA sobre documentos não implementada** (só regras); Android/iOS não construídos; sem linter (só `tsc` e `compileall`); embeddings, intenção por LLM, tiles de mapa externos e importação Lattes/Plataforma Brasil dependem de infraestrutura externa.

## [0.10.0] — 2026-10-05 — Camada institucional do terceiro setor (cumulativo; snapshot do v0.9.0 em `history/v0.9.0/`)
### Adicionado
- **Modelo em 5 camadas** (natureza jurídica × qualificações × perfil de atuação × situação institucional × elegibilidade calculada) — `THIRD_SECTOR_MODEL.md`. Migração `0006_v0100_institutional.sql` (6 tabelas novas: `inst_catalog_items`, `eligibility_rules`, `organization_qualifications`, `organization_qualification_events`, `proponent_needs`, `eligibility_evaluations`; colunas novas em `organizations`, `documents`, `calls`, `funder_profiles`, `solutions`; RLS em todas).
- **Motor de Elegibilidade Institucional** `institutional-eligibility@1.0.0` (5 estados, explicação, fonte, data; ausência de regra ⇒ PENDENTE) e **maturidade 0–6** (`config/institutional_maturity.json`, hipótese a calibrar).
- **Fluxo editorial** de catálogos e regras DRAFT→REVIEW→APPROVED→PUBLISHED→ARCHIVED com quatro olhos; **importação de regras candidatas em rascunho** (`config/institutional_rules.candidates.json`).
- **Qualificações** declaradas × verificadas (verificar exige autoridade, número, comprovante validado ou URL, vigência, justificativa); **documentos institucionais** com 5 estados; **badges** calculados com critério/fonte/validade.
- **Match Engine 1.1.0**: hard blockers explicados, natureza jurídica/maturidade/modalidade; **camadas fiscais** (estimativa, regra identificada, possível elegibilidade, elegibilidade documental, validação profissional).
- **Banco de Ideias**: IP/confidencialidade/titularidade, portão de publicação, rótulos de compartilhamento, acesso limitado, proponente e prontidão para financiamento nos resultados, filtros institucionais.
- Frontend: páginas Instituição (OSC/financiador/governo/profissional), perfil público, painel admin institucional, cadastro com natureza jurídica (coletivos sem CNPJ), formulários de edital/financiador/solução e filtros da Biblioteca.
- +37 operações de API (343 no total). +51 testes (233 no total).
### Alterado (comportamento)
- **Requisito de certificação no match agora exige qualificação VERIFICADA e vigente**; certificação apenas declarada não satisfaz. O campo legado `certifications` (PATCH `/v1/org`) passa a criar qualificações **declaradas** e nunca apaga existentes.
- Publicar solução exige titularidade declarada e autorização de publicação.
- `.content` do layout com `min-width: 0` (corrige rolagem horizontal em celular em páginas com abas).
### Corrigido
- Teste instável `test_signed_tokens` (adulteração podia gerar o mesmo token).
### Não feito / pendente
- Rota de estimativa fiscal sem cruzamento com `osc_org_id`; dados DEMO institucionais no seed; E2E do painel admin institucional (exige fluxo MFA no navegador); validação jurídica de todos os catálogos/regras iniciais; integração com bases governamentais (inexistente).

## [0.9.0] — 2026-10-05 — Biblioteca de Soluções de Impacto (cumulativo com 0.8.0, que não foi lançado separadamente)
### Adicionado
- **Banco de ideias, projetos, metodologias, tecnologias sociais e projetos acadêmicos** (`/v1/solutions`, 60 operações; migração `0005_v090_solutions.sql`: 20 tabelas, RLS em todas, gatilhos de regra de verdade).
- **Busca por intenção** híbrida sem IA (tesauro de 44 conceitos, FTS `pt_unaccent`, trigramas, filtros estruturados), relevância 0–100 **explicável** com pesos configuráveis (`config/solution_weights.json`, hipótese) e análise de sensibilidade (`docs/evidence/weights_sensitivity_v0.9.0.json`).
- **Match financiador↔solução** (`solution-match@1.0.0`), recomendações por tese ou por opt-in, independente do plano (teste AST).
- **Replicabilidade** (score só com confiança ≥ 50), **adaptação para território**, **desenvolver ideia** (rascunho por regras, revisão humana obrigatória no banco), **combinar soluções**, **comparador** (2–4), 7 modos de visão, "Quero algo como este", copiloto ancorado (sem IA).
- **Intenção de financiamento** em 10 etapas com privacidade e anti-manipulação (funções `SECURITY DEFINER`, gatilhos, eventos append-only), pedidos ao autor, **marketplace de replicação** com confirmação do autor, avaliações restritas, contestação de autoria.
- **Níveis de confiança** (não verificado → verificado) só pela administração; evidências/resultados com revisão; dados DEMO marcados.
- Frontend: Biblioteca, Perfil com proveniência, Comparar, Combinar, Minhas soluções, Pedidos, Replicações, Preferências, Admin de soluções; componente acessível `Group`.
### Alterado
- API 246 → **306** operações; banco 85 → **105** tabelas, 163 → **207** políticas RLS; 53 gatilhos.
- Roteamento ordenado por especificidade (literal antes de `{param}`) em `app.py`.
### Corrigido (descoberto na construção)
- `/v1/me` retornava 500 para a organização da plataforma (faltava `plan_names`) — bug pré-existente; teste de regressão.
- Opt-out de personalização não apagava o histórico de buscas (faltava política DELETE).
- Perfil de financiador vazio (PF/empresa) gerava recomendações sem base; agora `funder_profile_missing`.
- Chips dentro de `<label>` poluíam nomes acessíveis; temas exibiam slug sem acento.
### Testes
182 testes (31 + 3 E2E novos da Biblioteca), 0 falhas — `docs/evidence/test_run_v0.9.0.log`. Busca: p50 ≈ 181 ms / p95 ≈ 474 ms com 5.000 soluções sintéticas (local).
### Observação de versão
O v0.8.0 foi desenvolvido na mesma sessão mas não foi empacotado; seus documentos estão em `history/v0.8.0/`. O v0.9.0 é o primeiro pacote a incluí-lo.

## [0.8.0] — 2026-10-05 — Impacto, compras, pagamentos registrados, risco, rede, mapa, relatórios
### Adicionado
- **Financiador pessoa física** (`organizations.kind = individual`, sem CNPJ): nome mascarado para as OSCs por padrão (`org_display`), opt-in explícito para mostrar o nome.
- **ODS 1–17** normalizados e **catálogo de indicadores** (13 da plataforma; metas oficiais ODS NÃO são embutidas — importar de fonte oficial). Valores **reportados × validados** (validação por outra organização, com evidência; o banco recusa auto-validação). Dimensões ESG por indicador.
- **Impact Graph**: relações tipadas (hipótese, associação, correlação, inferência, evidência observada, causalidade validada); só a última afirma causa e exige evidência + revisão externa (CHECK no banco).
- **Diagnóstico social** (problema → causas → metas → plano) aplicável ao projeto; **determinantes sociais** (mapeamento próprio, k≥3, sem estatística populacional).
- **Compras**: política configurável (padrão 3 cotações), benchmark por mediana, sinal "preço possivelmente fora do padrão" (nunca "fraude"), exceção com 2ª aprovação, vínculo despesa↔compra.
- **Modelos de contribuição** (portão jurídico: só admin aprova; termos aprovados imutáveis) e **pagamentos** como *registro* (máquina de estados no banco, estorno com dupla parte, eventos append-only, ledger), **extrato CSV + conciliação**. A plataforma continua sem custódia (ADR-022).
- **Risco e antifraude** (8 detectores → sinais para revisão humana; bloqueio só por decisão humana com justificativa).
- **Rede**: seguir, bloquear, mensagens entre organizações com relação, moderação por denúncia, necessidades de apoio profissional + **Match profissional** (professional-match@1.0.0, plano não interfere), conquistas objetivas sem ranking.
- **Mapa** sem provedor externo (SVG) e localização com precisão configurável (região/município/aproximada/bairro/exata); coordenadas exatas nunca vazam.
- **Central de relatórios** (8 tipos, impressão/PDF pelo navegador, CSV com proteção contra injeção de fórmula).
- **Observabilidade**: `traceparent` W3C, spans de banco, agregação de erros sem PII (`/v1/admin/errors`), job `risk_scan`; `scripts/loadtest.py` com medição real.
- 15+ páginas novas no frontend; `ErrorBoundary` (evita tela em branco).
### Alterado
- API: 165 → 246 operações; banco: 56 → 85 tabelas, 163 políticas RLS. Migração `0004_v080_modules.sql` (a 0003 não foi editada; `org_document_metadata` redefinida na 0004 para `individual`).
### Corrigido durante a construção
Função de metadados documentais negava o financiador PF; página em branco por uso incorreto da taxonomia (hoje há ErrorBoundary); rótulo duplicado quebrava o seletor do E2E de cadastro.
### Testes
144 testes (34 novos de domínio + 3 E2E novos), 0 falhas — `docs/evidence/test_run_v0.8.0.log`; carga: `docs/evidence/loadtest_v0.8.0.json`.

## [0.7.0] — 2026-10-05 — Execução real sobre PostgreSQL
### Adicionado
- Backend Python (Starlette) com 165 operações `/v1`, OpenAPI e `docs/API.md` gerados do código.
- PostgreSQL 16: 56 tabelas, RLS em todas, triggers de integridade, cadeias de hash (auditoria e ledger), papéis `impacto_owner`/`impacto_app`.
- Autenticação de produção: scrypt, sessões opacas, refresh rotativo com detecção de reuso, MFA TOTP, OIDC (PKCE), lockout, rate limit, CSRF.
- Catálogo unificado de editais/fundos (privado, federal, estadual, municipal, internacional), importação de fontes, busca, buscas salvas e alertas (premium).
- Match Engine 1.0 (duas direções, bloqueadores, explicabilidade, confiança mínima), Fiscal Engine 1.0 (somente regras aprovadas), compliance/KYB, IA provider-agnostic.
- Candidatura assistida passo a passo, rascunhos com IA, revisão e assinatura de profissional habilitado, cofre de documentos com antivírus/storage privado.
- Execução: aportes (confirmação dupla), despesas, evidências, marcos, devolutivas, relatório de projeto, CSV; carteira da empresa; portal do governo (agregados k-anônimos).
- Cobrança (none/sandbox/Stripe/manual), planos, vouchers com dupla aprovação, entitlements.
- Frontend React/TS (PWA), cinco portais, tema claro/escuro; Capacitor (Android/iOS) preparado.
- LGPD técnico: exportação, eliminação, consentimentos, retenção; minutas legais [VALIDAR JURÍDICO].
- DevOps: Dockerfile, compose, nginx, CI, backup/restore verificado, métricas Prometheus.
- 111 testes automatizados (unit, integração, RLS/segurança, OIDC, E2E em Chromium).
### Segurança adicional
- Cliente HTTP com proteção SSRF (destinos internos bloqueados, sem redirecionamentos); verificação no boot de que o papel do banco respeita RLS.
### Alterado
- Match: sem nota quando a confiança < 50; datas dd/mm/aaaa; projetos bloqueados aparecem com motivos (`hidden_blocked`).
### Removido / substituído
- SQLite e autenticação de demonstração do v0.6.0 (preservados em `history/v0.6.0/`).
### Corrigido durante a construção (cada um com teste de regressão)
Corpo validado antes da autorização; UUID inválido → 500; falta de política UPDATE em `conflict_declarations`; nomes de assinantes ocultos pela RLS;
voucher sob SERIALIZABLE retornava 500; plano sem preço era comprável no sandbox; contadores de falha de login revertidos por rollback; raízes de palavras de segurança alimentar ausentes.
### Limites conhecidos
Ver `FINAL_RELEASE_AUDIT.md` §3 e `PRODUCTION_READINESS.md`.
