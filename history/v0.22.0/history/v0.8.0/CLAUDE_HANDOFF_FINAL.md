# CLAUDE_HANDOFF_FINAL — continuação a partir do v0.7.0

## Objetivo desta etapa
Receba este pacote como base. **Não assuma que está pronto para produção** (veja `PRODUCTION_READINESS.md`). Primeiro **reproduza**: `ENVIRONMENT_SETUP.md` → `make test` (esperado: suíte verde; log de referência em `docs/evidence/`). Audite o código real, não os documentos.

## Regras (mantidas)
1. Não inventar testes, integrações, publicação, segurança, compliance, benefícios fiscais, dados ou impacto. 2. Dados de demonstração sempre rotulados. 3. Match independente de plano/voucher (teste AST). 4. Fiscal só com regras aprovadas por 2 revisores. 5. IA = rascunho + revisão humana. 6. Aportes não são processados pela plataforma (ADR-022). 7. Nada de segredos no repositório.

## Mapa do código
`backend/impacto/` (config, db, http, services, engines, api, adapters, jobs, cli) · `backend/migrations/` · `backend/tests/` · `web/src/` (api, router, session, ui/kit, pages/*) · `config/` (plans, taxonomy, match_weights, fiscal_rules.candidates) · `infra/` · `mobile/` · `docs/`. Decisões: `DECISIONS.md`. Auditoria: `FINAL_RELEASE_AUDIT.md`.

## Próximos passos em ordem de valor
**A. Fechar o piloto (depende do proprietário):** contas/domínio/provedores (`DEPLOYMENT_CHECKLIST.md` §A–C); revisão jurídica das minutas; tributarista aprova regras fiscais; curadoria de editais reais; definir preços.
**B. Validar o que não pôde ser executado:** `docker build` e compose; CI no GitHub (typecheck com `@types` oficiais, pip-audit, npm audit); Stripe em modo teste; clamd e S3 reais; OIDC real; SMTP real; teste de carga (k6/Locust) e índices sob volume; axe + leitor de tela.
**C. Mobile:** `mobile/setup.sh`; token em Keychain/Keystore; push (FCM/APNs) se necessário; assinatura e lojas.
**D. Produto (lacunas do prompt-mestre — ver auditoria §3), sugerida:**
1. Perfil **Financiador PF** e **Profissional** com match próprio (profissional ↔ projeto/OSC).
2. **ODS normalizado** (metas/indicadores) + dimensões ESG + relatório ESG/ODS; depois **Impact Graph** (marcando hipótese × evidência).
3. **Compras**: ProcurementPolicy, 3 cotações configuráveis, benchmark (mediana/outlier — “preço fora do padrão”, nunca “fraude”).
4. **Risk & Fraud** (duplicidade de documento/evidência por hash, contas relacionadas) com revisão humana.
5. **Mapas** com granularidade configurável e agregações pré-calculadas.
6. **Mensageria/rede social** com moderação e anti-abuso (só após D1–D4).
7. Pesos por segmento/campanha + A/B + calibração com dados reais (`match_runs` já guarda features).
8. Traces/OpenTelemetry, Sentry, filas (se o volume exigir), cache.
9. Assinatura qualificada ICP-Brasil (se editais exigirem), modelo formal de contribuição (após parecer).
**E. Dívidas técnicas conhecidas:** driver libpq próprio (avaliar psycopg 3); rotação de `FIELD_ENCRYPTION_KEY` sem recriptografia automática; `compliance` rules em código; consolidar `docs/API.md` no CI (`scripts/gen_api_docs.py`); `frontend` sem testes unitários de componentes.

## Como validar rapidamente
`make db && make web && make test` · `python3 scripts/make_release.py --verify` · `curl localhost:8080/readyz`.
