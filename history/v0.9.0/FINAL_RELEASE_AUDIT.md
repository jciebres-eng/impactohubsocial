# FINAL_RELEASE_AUDIT — Plataforma Impacto v0.9.0

Data: 2026-10-05 · Base auditada: `plataforma-impacto_docs_v0.6.0.zip` (preservada em `history/v0.6.0/`).
Método: leitura forense do pacote v0.6.0 (docs × código × testes × config), reconstrução da camada de execução e prova por testes.
**Nenhum item abaixo é "pronto" sem a evidência indicada.** Legenda: GREEN = implementado e validado por teste/execução neste ambiente · YELLOW = implementado, mas depende de ação/serviço externo ou não foi exercitado com o serviço real · RED = ausente.

## 1. O que o v0.6.0 realmente era
O v0.6.0 documentava PostgreSQL+RLS, MFA/OIDC, storage privado, etc., mas o **código executável era uma referência local**: SQLite, autenticação de demonstração, `app.py` único, 1 arquivo de teste, SQL de RLS **sem teste e sem aplicação** pela app, UI estática. Documentação ≠ código. Decisão (ADR-019): **reescrever** a execução sobre PostgreSQL, preservando como KEEP as ideias e artefatos corretos (pesos do match, planos, taxonomia, conceito do ledger, estrutura de docs).

## 2. Matriz de auditoria
| Área | Estado anterior (v0.6.0) | Problema | Decisão | Implementação (v0.7.0) | Teste / evidência | Resultado |
|---|---|---|---|---|---|---|
| Banco | SQLite local + rascunho SQL | não é produção; sem RLS efetivo | REPLACE | PostgreSQL 16, 3 migrações, 56 tabelas, checksum | suite roda em PG real; `restore_test.sh` | GREEN |
| Multi-tenant | arquivo `0001_rls.sql` não aplicado | isolamento só no papel | REPLACE | RLS em todas as tabelas + papel `impacto_app` sem BYPASSRLS + contexto por transação + boot recusa papel inseguro | `test_security_tenancy` (24+), `test_every_table_has_rls` | GREEN |
| Autenticação | login de demonstração | inseguro p/ produção | REPLACE | scrypt, tokens opacos hash, refresh rotativo c/ detecção de reuso, logout/revogação, lockout, rate limit DB, anti-enumeração, CSRF | `test_api_auth` (19) | GREEN |
| MFA | só documentado | ausente | MISSING | TOTP + recovery; obrigatório p/ admin | `test_api_auth`, `test_unit` (RFC 6238) | GREEN |
| SSO/OIDC | só documentado | ausente | MISSING | Code+PKCE, JWKS, nonce, amr | `test_oidc` (IdP **falso**) | YELLOW (IdP real não testado) |
| Autorização | checagens soltas | sem RBAC por objeto | REPLACE | RouteSpec (tipo de org, papel, MFA, feature) + RLS; autoriza antes de validar corpo | testes IDOR/escalonamento; `test_handlers_declare_auth` | GREEN |
| Match Engine | pesos em JSON, motor simples | sem bloqueadores/explicação completa | REFACTOR | 2 direções, blockers, why/why-not, riscos, dados faltantes, próxima ação, confiança mínima, features p/ ML | `test_unit`, `test_api_features` (invariância de plano) | GREEN (pesos = hipótese a calibrar) |
| Fiscal Engine | regras de exemplo | risco de inventar legislação | REPLACE | só regras aprovadas por 2 revisores; 4 rótulos; candidatas em rascunho | `test_api_features::Fiscal` | GREEN (regras reais: **pendente profissional**) |
| Compliance/KYB | texto | ausente | MISSING | checks (formato CNPJ, consulta CNPJ e CEIS/CNEP via adapter, docs, perfil, denúncias) + revisão humana | testes de fluxo | YELLOW (fontes externas `not_configured` até configurar) |
| Impact Ledger | conceito | sem integridade | REFACTOR | cadeia SHA-256 no banco por projeto, append-only, `ledger_verify` | `test_ledger_tampering_is_detected`, restore | GREEN |
| Auditoria | — | ausente | MISSING | `audit_events` encadeado por org + verificação admin | testes admin/restore | GREEN |
| IA | stub | acoplado/sem controles | REPLACE | gateway: local/anthropic/openai-compat/disabled, cota, redação PII, log sem conteúdo, fallback, timeout/retry | `test_unit`, `test_api_features` (**fakes**) | YELLOW (provedor real não testado) |
| Upload/arquivos | — | ausente | MISSING | allowlist, magic bytes, PDF ativo, macro, zip bomb, antivírus clamd, storage privado local/S3 SigV4, URLs assinadas curtas | `UploadTests`; SigV4 vetor AWS | YELLOW (clamd/S3 reais não testados) |
| Cobrança | planos em JSON | risco de pagamento falso | REPLACE | none/sandbox(não-prod)/stripe/manual; webhook assinado + idempotente; preço null → 409 | testes billing | YELLOW (Stripe real não testado; preços indefinidos) |
| Vouchers | doc | ausente | MISSING | HMAC, dupla aprovação, resgate transacional | testes | GREEN |
| OSC: catálogo/match/candidatura | doc | ausente | MISSING | `calls` (privado/federal/estadual/municipal/internacional), importação de fontes, busca, recomendados, candidatura assistida com trilha, rascunhos IA, revisão e assinatura profissional | `test_api_workflow` | GREEN |
| Premium OSC (buscas/alertas) | — | — | MISSING | saved_searches + job + notificações/e-mail, atrás de plano/flag | `AlertsTests` | GREEN |
| Execução/prestação de contas | — | ausente | MISSING | aportes (confirmação dupla), despesas, evidências, revisão, devolutivas, relatório, CSV | `test_api_workflow` | GREEN |
| Empresa | — | ausente | MISSING | feed c/ bloqueados explicados, comparação, interesse, conflito, carteira, fiscal | `test_api_workflow`, E2E | GREEN |
| Governo | — | ausente | MISSING | publicar editais/materiais; estatísticas agregadas (k-anonimato) | `GovernmentAndAiTests` | GREEN |
| Admin | — | ausente | MISSING | 33 operações (ver `docs/ADMIN.md`) | testes admin | GREEN |
| LGPD (técnico) | texto | sem mecanismo | MISSING | export, eliminação/anonimização, consentimentos, retenção por job, minimização | `PrivacyAndAdminTests` | YELLOW (base legal/RIPD/DPO: jurídico) |
| Textos legais | — | placeholders | MISSING | minutas completas | — | YELLOW (**[VALIDAR JURÍDICO]**) |
| Frontend/PWA | HTML estático | sem produto | REPLACE | React/TS, 5 portais, tema claro/escuro, SW, CSP self | build + `test_e2e_web` (3) | GREEN |
| Acessibilidade | — | não verificada | — | semântica/foco/labels, reduced-motion | revisão manual, sem axe | YELLOW |
| Observabilidade | — | ausente | MISSING | logs JSON, métricas Prometheus, health/ready | testes de contrato | YELLOW (sem traces/error tracking/alertas ativos) |
| DevOps/CI | Dockerfile/CI de exemplo | não executados | IMPROVE | Dockerfile multi-stage, compose, nginx, CI, deploy modelo | **não executados** | YELLOW |
| Backup/restore | — | ausente | MISSING | `backup.sh` + `restore_test.sh` verificando cadeias | executado OK | GREEN |
| Android/iOS | — | ausente | MISSING | Capacitor, ícones, deep links, `setup.sh` | **não construído** | YELLOW (CODE READY apenas) |
| Performance/carga | — | não medida | — | índices, paginação | sem teste de carga | RED (não medida) |
| Licenças/PI | rascunho | sem inventário | IMPROVE | `THIRD_PARTY_DEPENDENCIES.md`, `IP_REGISTER.md` | revisão manual | YELLOW |

## 3. Lacunas frente ao prompt-mestre — posição do v0.7.0 (histórica; ver §3-A para o estado atual)
Itens do briefing que **não existem** nesta versão: **Impact Graph** e relações entre ODS (ODS são códigos, não há metas/indicadores ODS normalizados); **rede social** (seguir, conexões, comentários, mensagens, reações); **gamificação**; **financiador PF** e **profissional ↔ projeto** com match próprio (há diretório e revisão sob demanda); **ProcurementPolicy / 3 cotações / benchmark de preço**; **camada Risk & Fraud**; **modelo de contribuição/cotas e fluxo de pagamento de aportes** (por decisão: aportes são *registrados e conferidos*, não intermediados — evita configurar instituição de pagamento/valor mobiliário sem parecer jurídico); **mapas/geolocalização com granularidade configurável**; **A/B de pesos e pesos por segmento**; **embeddings/OCR/visão**; **Redis/fila/WebSocket/busca dedicada** (jobs em banco; suficiente p/ piloto); **traces/error tracking**; **gráficos avançados/3D** (há barras de fluxo acessíveis com valores em texto); **WebP/AVIF**; **push**; **tenants** distintos de organizações.
Justificativa: o escopo pedido pelo proprietário na 2ª mensagem (OSC ↔ editais ↔ candidatura assistida ↔ execução ↔ empresa/governo) foi priorizado e entregue ponta a ponta; as demais áreas são roadmap (`docs/ROADMAP` em `CLAUDE_HANDOFF_FINAL.md`).

## 3-A. Evolução v0.8.0 → v0.9.0 (estado atual)
**Fechadas no v0.8.0 (testadas):** financiador PF, ODS/indicadores/ESG normalizados (metas oficiais **não** embutidas), Impact Graph tipado, compras/3 cotações/benchmark, risco e antifraude (sinais, não acusação), pagamentos como *registro* + conciliação, rede (seguir/bloquear/mensagens/moderação), mapa SVG com precisão de localização, match profissional, conquistas, central de relatórios, tracing W3C, teste de carga.
**Fechadas no v0.9.0:** Biblioteca de Soluções de Impacto (busca por intenção, relevância explicável, match financiador, replicabilidade, adaptação, combinação, comparador, intenção de financiamento, marketplace de replicação, proveniência/níveis de confiança, curadoria administrativa).
**Continuam abertas:** embeddings/OCR/visão · Redis/fila/WebSocket/busca dedicada · mapas com tiles externos · push · A/B de pesos · gráficos 3D · WebP/AVIF · tenants distintos de organizações · custódia/processamento de pagamentos (por decisão) · modelo de cotas (aguarda parecer jurídico) · refinamento de intenção por LLM · importação de fontes externas de projetos acadêmicos (Plataforma Brasil/Lattes).

### Matriz de auditoria §57 — módulos tocados pela Biblioteca (v0.9.0)
| Módulo | Existia | Problema encontrado | Decisão | Ação | Evidência | Resultado |
|---|---|---|---|---|---|---|
| Projetos | execução (`projects`, etapas, despesas) | não representava ideias/cases/metodologias | KEEP + EXTEND | `solutions` separado; `parent_id`/relação com projetos; ideia ≠ projeto | `test_v090_solutions` | GREEN |
| Match | org↔edital, financiador↔projeto, profissional | sem match com solução | EXTEND | `solution-match@1.0.0`, mesmo contrato (blockers, why, riscos, confiança mín. 50) | `test_solution_match_blocks_excluded_and_has_no_plan_input`, `test_funder_match_and_recommendations` | GREEN (pesos = hipótese) |
| ODS | catálogo 1–17 + indicadores | não ligado a soluções | EXTEND | `ods[]`/`esg[]` + conceito→ODS no tesauro | busca por ODS testada | GREEN |
| ESG | dimensões por indicador | idem | EXTEND | filtro/sinal ESG | idem | GREEN |
| Busca | busca de editais (FTS) | sem intenção/sinônimos/erro de digitação | EXTEND | pipeline híbrido; 9 consultas de qualidade | `test_search_quality`; `search_perf_v0.9.0.json` | GREEN (sem vetores) |
| Usuários | 5 tipos de organização | — | KEEP | todos cadastram/leem soluções com RLS | testes de tenancy | GREEN |
| Organizações | KYB/compliance | solução sem vínculo com a organização | KEEP | `org_id` + RLS por visibilidade | SQL direto nos testes | GREEN |
| Documentos | cofre/metadados | evidência de solução separada do cofre | EXTEND | `solution_evidence` (URL https, revisão admin) | testes de confiança | GREEN |
| Analytics | eventos agregados k≥3 | funil de intenção inexistente | EXTEND | `solution_events` dedupe + `solution_funnel` (só autor) | `test_view_never_creates_intent_and_events_are_deduplicated` | GREEN |
| Auditoria | cadeia por organização | ações novas | EXTEND | `ctx.audit()` em ações sensíveis | — | GREEN |

### §62 — Autoavaliação de qualidade (honesta, 1–10)
| Critério | Nota | Justificativa |
|---|---|---|
| Produto | 7 | jornadas completas ponta a ponta; sem usuários reais |
| UX | 6 | 7 modos de visão e persona; **sem teste de usabilidade com pessoas** |
| Busca | 7 | híbrida e explicável; sem embeddings; tesauro curado à mão |
| IA | 3 | opcional e **não usada**; gateway existe, sem provedor real testado |
| Match | 6 | explicável e invariante ao plano; pesos não calibrados |
| Dados | 7 | modelo rico, versionado e auditável; **sem dados reais** (só DEMO) |
| Segurança | 8 | RLS testada via SQL direto, guards no banco; **sem pentest** |
| Performance | 5 | p95 474 ms local com 5.000 sintéticas; sem carga concorrente nem cache |
| Mobile | 4 | PWA responsivo; apps não construídos |
| Acessibilidade | 5 | verificações próprias (rótulos/h1/landmark); **sem axe/leitor de tela** |
| Escalabilidade | 5 | índices adequados a ~10⁵; passo vetorial e particionamento previstos, não feitos |
| Negócio | 5 | planos sem preço; nenhuma monetização da biblioteca ativa |
| Diferenciação | 7 | proveniência/verdade + intenção com privacidade + replicação confirmada |

### §63 — Melhorias autônomas feitas (além do pedido)
Correção do 500 em `/v1/me` para a organização da plataforma · ordenação de rotas por especificidade · opt-out que de fato apaga histórico de buscas · `funder_profile_missing` · componente `Group` (fieldset/legend) para nomes acessíveis · rótulos de tema com acento · benchmark de busca e análise de sensibilidade de pesos reproduzíveis · dedupe diário de eventos · limite de pedidos por dia.

## 4. Estados de publicação
| Alvo | READY | BUILT | TESTED | SIGNED | SUBMITTED | APPROVED | PUBLISHED |
|---|---|---|---|---|---|---|---|
| Web/PWA | ✅ | ✅ (`web/dist`) | ✅ (E2E local) | n/a | ❌ | ❌ | ❌ |
| Backend/API | ✅ | ⚠️ imagem Docker não construída | ✅ (processo local) | n/a | ❌ | ❌ | ❌ |
| Android | ✅ código | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| iOS | ✅ código | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
**Nada foi publicado.**

## 5. Evidência de testes
`182 testes, 0 falhas` — `docs/evidence/test_run_v0.9.0.log` (histórico: 111 no v0.7.0, 144 no v0.8.0). Detalhes: `TEST_REPORT.md`. Comando em `docs/TESTING.md`.
Também verificados: build web, restauração de backup com cadeias íntegras, checagem de pacote (`scripts/make_release.py --verify`).

## 6. Dependências externas pendentes
Conta/domínio/TLS · PostgreSQL gerenciado · S3 · ClamAV · SMTP · Stripe (e preços) · IdP OIDC · API de CNPJ · chave Portal da Transparência · provedor de IA + política de dados · lojas (Google Play/Apple) · parecer jurídico (termos, privacidade, assinatura, aportes) · tributarista (regras fiscais) · contador/advogado parceiros · calibração do match com dados reais.

## 7. Riscos principais
1. Pesos do match são hipóteses. 2. Regras fiscais ainda inexistentes (só candidatas). 3. Driver de banco próprio (ctypes) — substituível por psycopg 3, mas é código a manter. 4. Tokens do app móvel em armazenamento simples. 5. Sem teste de carga. 6. Textos legais não validados. 7. Assinatura profissional ≠ ICP-Brasil. 8. Tipagem TS validada só com *shims* offline (CI valida com tipos oficiais).
