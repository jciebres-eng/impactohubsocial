# Plataforma Impacto — v0.15.0

Plataforma para **OSCs, empresas/fundações, profissionais parceiros e órgãos públicos**: do edital à prestação de contas, com compatibilidade explicável, candidatura assistida, documentos e rascunhos com IA validados por profissional habilitado, acompanhamento de aportes/despesas/evidências e trilha de integridade verificável.

> **Estado:** núcleo do produto fechado e **tecnicamente pronto para a etapa de design**; para piloto controlado, leia primeiro `RELEASE_READINESS.md` §5 (o que esta versão NÃO entrega). **Não publicado** em nenhuma loja ou domínio. Android/iOS: código pronto, **não construídos**. Leia `PRODUCTION_READINESS.md` e `FINAL_RELEASE_AUDIT.md` antes de qualquer decisão.

**Novo no v0.15.0 (Núcleo do produto):** as seis peças passaram a ser **um sistema**, não seis telas — ideia → diagnóstico → projeto → documento → match → acompanhamento compartilhando o mesmo vocabulário de evidência (com fonte, data e frescura), as mesmas versões de motor e a mesma trilha encadeada por hash. A **ideia não é apagada** ao virar projeto; a **máquina de 17 situações é dado no banco**, com gatilho que recusa transição inválida até em SQL direto; a **linha de tempo** é a trilha que já existia, verificável; **retratos comparáveis** respondem "o que mudou entre março e setembro"; o **diagnóstico** separa FATO, INFERÊNCIA, RECOMENDAÇÃO e **DESCONHECIDO**, com versões imutáveis e `o que mudou` calculado pelo servidor; a **montagem de documento** recusa gerar incompleto, dizendo o que falta, e exige **quatro olhos** para aprovar; o **match** carrega quatro versões e aceita retorno humano **sem treinar nada automaticamente**. 673 testes, 625 operações, 205 tabelas. **Não há assinatura qualificada (ICP-Brasil/Gov.br), KMS/HSM, integração contra sistema real nem teste de intrusão independente** — tudo isso está listado com nome e motivo. Comece por `CORE_PRODUCT_ARCHITECTURE.md`, `FINAL_PRE_DESIGN_HARDENING_REPORT.md` e `DESIGN_HANDOFF.md` §13.

**Novo no v0.14.0 (Confiança, identidade e assinatura digital):** **qualquer pessoa autorizada pode verificar um documento da plataforma sem ter conta** — pelo código impresso ou pelo QR, em `/verificar`: diz se é genuíno, **qual versão foi assinada**, se a integridade continua intacta, quem assinou e se foi revogado. Mais: assinatura eletrônica avançada em **duas camadas** (senha + código de uso único amarrado ao hash do conteúdo), cadeia de custódia encadeada por objeto, identidade por níveis com conferência humana, credencial profissional com catálogo de 20 conselhos, acordos multiassinatura com acompanhamento, carimbo de tempo interno, taxonomia ODS/ESG/determinantes sociais, idioma e tema por usuária, financiamento em cotas com campanha pública, honorários exigindo fonte, georreferência com consentimento, diagnóstico guiado em 8 etapas e exportação em docx/xlsx/odt/ods/xml/pdf. 564 testes. **Não há assinatura qualificada (ICP-Brasil/gov.br), biometria, SMS nem carimbo de ACT** — essas dependem de contratação externa e a plataforma **recusa explicitamente** em vez de simular. Comece por `PUBLIC_VERIFICATION.md`, `DIGITAL_SIGNATURE.md` e `FINAL_TRUST_HARDENING_REPORT.md`.

**Novo no v0.13.0 (Integration Hub):** camada de integração desacoplada — conexões por ambiente, credenciais cifradas que a API nunca devolve, mapeamento de campos, correspondência de ID externo com conflito explícito, jobs idempotentes com repetição e disjuntor, webhooks de entrada e saída assinados, importação CSV/XLSX com aprovação humana, exportação e painel de operação. 13 tabelas, 36 rotas, 9 provedores declarados com **maturidade honesta**, 468 testes. **Nenhuma integração foi executada contra sistema externo real** e **não há nenhuma tela** — comece por `INTEGRATION_HUB.md`, `FINAL_INTEGRATION_HARDENING_REPORT.md` e `DESIGN_HANDOFF.md` §11.

**Novo no v0.12.1 (baseline técnica):** endurecimento final antes da camada de design — varredura de autorização nas 475 operações, testes de concorrência, correção de vazamento de esquema em erros, do desconto de voucher que não aparecia, da perda de boletim em falha de SMTP e do contraste reprovado (WCAG AA). 392 testes. Comece por `FINAL_TECHNICAL_BASELINE.md` e `DESIGN_HANDOFF.md`.

**Novo no v0.12.0:** Central de Conhecimento — `/ajuda` (busca, guias, biblioteca, FAQ, assistente ancorado), Academia, eventos, suporte com SLA, parcerias, demonstração, solicitação de teste, boletim e CMS em `/admin/central`. Começa em `KNOWLEDGE_HUB.md`. **Sem conteúdo oficial real ainda (só exemplos rotulados).**

**Novo no v0.11.0:** monetização SaaS — trial de 14 dias FULL sem cartão, níveis FREE/PLUS/PREMIUM/GOV, cobrança mensal/anual (Stripe, só simulado em testes), vouchers, licenças e convênios. Comece por `docs/billing.md`. **Preços não definidos; Stripe não homologado.**

**Novo no v0.10.1:** fecha pendências da camada institucional — perfis OS/OSCIP, instrumentos, trilha de formalização e mentoria, cruzamento fiscal × elegibilidade, rede da solução, tesauro de 67 conceitos. Veja `CHANGELOG.md` e `FINAL_RELEASE_AUDIT.md` §3-C.

**Novo no v0.10.0:** camada institucional do terceiro setor — natureza jurídica × qualificações × situação × elegibilidade por oportunidade, com explicação e fonte. Comece por `THIRD_SECTOR_MODEL.md`, `INSTITUTIONAL_ELIGIBILITY_ENGINE.md` e `FINAL_RELEASE_AUDIT.md` §3-B.

**Novo no v0.9.0:** Biblioteca de Soluções de Impacto — busca por intenção, relevância/match explicáveis, replicação, intenção de financiamento com privacidade. Comece por `SOLUTION_LIBRARY.md`.

## Comece aqui
| Biblioteca de Soluções | `SOLUTION_LIBRARY.md`, `SOLUTION_SEARCH.md`, `SOLUTION_MATCH_ENGINE.md`, `REPLICATION_ENGINE.md`, `INTENT_ENGINE.md`, `AI_SEARCH_ARCHITECTURE.md`, `SOLUTION_DATA_MODEL.md`, `API_DOCUMENTATION.md`, `TEST_REPORT.md` |
| Quero… | Leia |
|---|---|
| rodar localmente | `ENVIRONMENT_SETUP.md` |
| saber o que funciona e o que falta | `FINAL_RELEASE_AUDIT.md`, `PRODUCTION_READINESS.md` |
| publicar (Web, Google Play, App Store) | `DEPLOYMENT_CHECKLIST.md`, `docs/DEPLOYMENT.md`, `docs/MOBILE.md` |
| continuar o desenvolvimento | `CLAUDE_HANDOFF_FINAL.md`, `DECISIONS.md` |
| entender o núcleo do produto | `CORE_PRODUCT_ARCHITECTURE.md`, `MATCH_ENGINE_FINAL.md`, `DIAGNOSTIC_ENGINE.md`, `PROJECT_LIFECYCLE.md`, `DOCUMENT_ASSEMBLY.md`, `LONGITUDINAL_TRACKING.md` |
| fazer o design | `DESIGN_HANDOFF.md` §13 (fluxos A–I + 20 invariantes) |
| saber o que depende de terceiro | `EXTERNAL_DEPENDENCIES.md`, `HOMOLOGATION_MATRIX.md`, `SIGNATURE_VALIDATION_MATRIX.md` |
| auditar segurança, banco e desempenho | `SECURITY_FINAL_CHECKLIST.md`, `DATABASE_INTEGRITY_REPORT.md`, `PERFORMANCE_REPORT.md` |
| rotacionar chave de cifragem | `KEY_ROTATION.md` |
| saber o que é guardado e por quanto tempo | `DATA_RETENTION_MATRIX.md` |
| segurança / LGPD | `SECURITY_AUDIT.md`, `docs/SECURITY.md`, `LGPD_AUDIT.md`, `docs/LGPD.md`, `docs/legal/` |
| licenças e PI | `THIRD_PARTY_DEPENDENCIES.md`, `IP_REGISTER.md` |
| integridade do pacote | `RELEASE_MANIFEST.sha256` (`python3 scripts/make_release.py --verify .`) |

## Estrutura
```
backend/     API (Starlette), serviços, engines (match, fiscal, IA), adapters, jobs, migrações SQL, testes
web/         SPA/PWA React+TypeScript (src/), build esbuild (dist/ já construído), Capacitor (Android/iOS)
mobile/      scripts, ícones/splash e modelos de deep link
config/      planos, taxonomia, pesos do match, regras fiscais candidatas (rascunho)
infra/       bootstrap do banco, compose, nginx, alertas
scripts/     backup/restore, reset do banco de dev, gerador de API docs, make_release
docs/        arquitetura, banco, API (gerada), segurança, LGPD, match, fiscal, IA, compliance, pagamentos, operação, mobile, testes, admin, negócio, a11y, ESG/ODS, legal/, evidence/
history/     v0.6.0, v0.7.0 e v0.8.0 preservados (sem sobrescrever)
```
Mapa dos documentos pedidos: `AI_ARCHITECTURE` = `docs/AI.md` · `MATCH_ENGINE`, `DATABASE`, `API` (gerada de 306 operações), `SECURITY`, `LGPD`, `DEPLOYMENT`, `TESTING`, `ADMIN`, `BUSINESS_MODEL` em `docs/`.

## Princípios (verificáveis no código)
- **Isolamento no banco** (RLS) — não só na API. · **Match independe de plano/voucher** (teste AST). · **Sem nota sem dados suficientes.**
- **IA só rascunha**; revisão e assinatura por profissional verificado. · **Fiscal só com regra aprovada por dois revisores.**
- **Aportes não passam pela plataforma** (registrados e conferidos). · **Sem pagamento falso**; **sem segredos** no repositório.

## Início rápido (dev)
```bash
make db && make web && IMPACTO_SEED_DEMO=true make dev     # http://localhost:8080 — dados FICTÍCIOS
make test                                                   # suíte completa (Postgres + navegador)
```
Licença do código: **a definir pelo proprietário** (ver `IP_REGISTER.md`). Dependências: `THIRD_PARTY_DEPENDENCIES.md`.
