# TEST_REPORT — v0.12.0 (2026-10-05)

**v0.12.0: 359 testes, 0 falhas, 0 ignorados** (290 herdados + **62** de domínio em `backend/tests/test_v0120_knowledge.py` + **7** E2E de navegador em `backend/tests/test_e2e_knowledge.py`). Log completo: `docs/evidence/test_run_v0.12.0.log` (`python3 -m unittest discover -s tests -t . -v`, PostgreSQL 16 real, servidor HTTP real, Chromium/Playwright). Lint: `ruff check impacto tests` → **All checks passed** (`docs/evidence/ruff_v0.12.0.log`); `tsc --noEmit` e `compileall` limpos.

**Domínio (62):** fluxo editorial e quatro olhos (inclusive UPDATE direto no banco), versões imutáveis, regulatório, papéis e MFA; visibilidade e sitemap; busca por sinônimos com explicação, vazio, entrada inválida e log só com hash; assistente ancorado/recusa/sem conteúdo não publicado; FAQ e votos; biblioteca (modelo→rascunho, versões, download temporário); checklists; “Comece aqui” e pendências por dados reais; suporte (ciclo, guardas, IDOR, anexos, SLA, escalonamento, recorrência, preferências); eventos (lista de espera, link privado, lembrete idempotente, presença/avaliação); academia (gabarito, progresso, certificado, revogação); captação (consentimento, honeypot, privacidade, demo, boletim duplo opt-in); pedido de teste; analytics/retenção; e-mails (uma vez, preferências, conta não verificada); seed só `demo`.
**E2E (7):** (1) visitante: busca→guia→assistente recusa→demonstração com consentimento (viewport 390 px); (2) OSC: checklist persiste, “Ajudou?”, chamado, resposta da equipe; (3) Academia: matrícula, aula, quiz reprovado/aprovado, certificado e verificação pública; (4) evento (inscrição + lista de espera) e pedido de teste ficando “Solicitada”; (5) CMS: editor com MFA cria guia, **não consegue aprovar o próprio**, revisor publica, visitante lê; (6) verificações básicas de acessibilidade (h1 único, `main`, rótulos, `lang`) em 8 páginas públicas; (7) página privada redireciona ao login.
**Limites:** verificações de acessibilidade são **próprias** (não substituem axe/leitor de tela); sem teste cross-browser; Stripe/SMTP/antivírus/S3 são dublês; sem carga concorrente nas rotas novas; auditoria de dependências (`npm audit`/`pip-audit`) **não executada** (rede bloqueada); apps móveis não testados; qualidade da busca só provada nas frases testadas.

---

# TEST_REPORT — v0.11.0 (anterior)
**v0.11.0: 290 testes, 0 falhas, 0 ignorados** (256 herdados + **34** em `backend/tests/test_v0110_monetization.py`). Log completo: `docs/evidence/test_run_v0.11.0.log` (comando: `python3 -m unittest discover -s tests -t . -v` em `backend/`, PostgreSQL 16 real).
Cobertura nova: trial (início/14 dias/FULL/avisos/cancelamento dia 1 e dia 13/FREE após o fim/anti-abuso/lembretes sem duplicar), tiers (FREE/PLUS/PREMIUM/GOV), vouchers (20%, expirado, esgotado, 100%, permanente, valor fixo), checkout com `trial_end`, webhooks (duplicado, assinatura inválida, replay, fora de ordem), mensal/anual, cancelar impede renovação e preserva histórico, upgrade/downgrade, falha de pagamento/ação requerida/portal, convênios (vagas, domínio, 2º admin, GOV, revogação), revogação de licença, isolamento entre organizações e escrita direta bloqueada no banco.
**Limite:** o Stripe é um **dublê HTTP** — prova o que a plataforma envia/decide/registra, não o comportamento da API real. **Não há E2E de navegador do fluxo de cobrança** (frontend validado por `tsc` + build). Sem linter Python.


**Resultado: 256 testes, 0 falhas, 0 ignorados** (233 herdados do v0.10.0 + 17 em `test_v0101_institutional.py` (instrumentos, perfis, trilha, mentoria, cruzamento fiscal) + 2 de rede da solução + 1 de tesauro + 3 E2E em `test_e2e_v0101.py`). Log integral: `docs/evidence/test_run_v0.10.1.log` (anteriores preservados). Ambiente: PostgreSQL 16 real, servidor HTTP real, Chromium (Playwright).

**Novo no v0.10.1:** o E2E do **painel administrativo** (antes não testado no navegador) agora roda com **login MFA real (TOTP)** e prova que verificar um instrumento sem comprovante é recusado pelo servidor e que a fila de mentoria atualiza o estado no banco. Verificações de acessibilidade são **próprias** (não substituem axe/leitor de tela).
**Verificações estáticas:** `tsc --noEmit` (frontend) e `python -m compileall` — **não há linter Python instalado** (ruff/pyflakes ausentes); não afirmar lint.
**Ainda não testado:** Android/iOS; carga concorrente das novas rotas; axe/leitor de tela; validade jurídica de catálogos/regras/trilha; qualidade da busca fora das frases testadas (conceitos novos não passaram por avaliação com usuários).

---
# TEST_REPORT — v0.10.0 (anterior, 2026-10-05)

**Resultado: 233 testes, 0 falhas** (182 herdados do v0.9.0 + 48 de `test_v0100_institutional.py` + 3 E2E em `test_e2e_v0100.py`) — log integral em `docs/evidence/test_run_v0.10.0.log` (v0.9.0 preservado em `docs/evidence/test_run_v0.9.0.log`). Descrição do ambiente do v0.9.0 (ainda válida): Banco PostgreSQL 16 **real** descartável + servidor HTTP real (uvicorn) + Chromium (Playwright) para E2E. Nada é simulado exceto onde indicado.

## Como reproduzir
```
cd backend && TEST_ADMIN_DATABASE_URL="postgresql://postgres@127.0.0.1:5432/postgres" PASSWORD_SCRYPT_N=16384 RATE_LIMIT_MULTIPLIER=1000 python3 -m unittest discover -s tests -t . -v
```
(`RATE_LIMIT_MULTIPLIER` apenas afrouxa limites para a suíte; o teste de rate limit da busca usa o limite real.)

## Evolução da suíte
v0.7.0: 111 · v0.8.0: 144 · v0.9.0: **182** (31 de domínio da Biblioteca em `test_v090_solutions.py`, 3 E2E em `test_e2e_v090.py`, ampliações em `test_architecture.py`, +1 regressão `/v1/me`).

## Cobertura da Biblioteca de Soluções (v0.9.0)
| Área | Testes (nomes reais) |
|---|---|
| Motores puros | `test_intent_parser_examples`, `test_replicability_and_evidence_never_invented`, `test_truth_labels`, `test_adaptation_rules`, `test_combine_bounds`, `test_solution_match_blocks_excluded_and_has_no_plan_input` |
| Cadastro/publicação | `test_create_defaults_and_validation`, `test_publish_gates_and_owner_only`, `test_idea_is_not_a_case_and_has_no_results`, `test_develop_idea_requires_authorization_and_human_review` |
| Verdade/confiança | `test_trust_progression_needs_accepted_evidence_and_resets_on_edit`, `test_owner_cannot_forge_trust_demo_or_verification`, `test_evidence_and_results_status_cannot_be_set_by_owner`, `test_demo_seed_is_marked_demo_and_never_proven` |
| Busca | `test_search_quality` (artes caps · arte saúde mental · arte e centro de atenção psicossocial · projeto idosos · educação rural · mulheres violência · PcD tecnologia · erro de digitação · singular/plural · filtros · penalidade), `test_search_is_plan_independent_and_log_has_no_raw_text`, `test_search_rate_limited_and_validates`, `test_aggregates_and_vocabulary` |
| Análise | `test_profile_similar_compare_adapt_combine`, `test_funder_match_and_recommendations`, `test_personalization_is_opt_in_and_deletable` |
| Intenção/fluxos | `test_view_never_creates_intent_and_events_are_deduplicated`, `test_intent_privacy_and_stage_forging`, `test_intent_stage_cannot_be_forged_in_database`, `test_requests_antispam_and_permissions`, `test_replication_flow_reviews_and_disputes` |
| Multi-tenant/RLS | `test_cross_tenant_writes_blocked`, `test_other_org_cannot_modify_or_see_drafts`, `test_append_only_and_rls_on_events_and_requests` (+ `test_every_table_has_rls` do núcleo, agora sobre 105 tabelas) |
| Admin | `test_admin_only_and_removal` |
| Regressão | `test_regression_me_works_for_platform_org` |
| E2E navegador | busca → perfil → comparar → salvar/pedir; autor cadastra; administração verifica (3 testes, sem erros de console/CSP e com verificações próprias de acessibilidade) |

## Cobertura da camada institucional (v0.10.0)
| Classe de teste | O que prova |
|---|---|
| ModelTests | catálogos publicados, natureza jurídica no cadastro (incl. coletivo sem CNPJ), perfil institucional, RLS das tabelas novas |
| QualificationTests | declarada ≠ verificada; verificar exige autoridade/número/comprovante/vigência/justificativa; só admin verifica; eventos registrados |
| DocumentStateTests | 5 estados com rótulos exatos; aprovado no antivírus ≠ validado; expirado/rejeitado |
| RuleWorkflowTests | DRAFT→REVIEW→APPROVED→PUBLISHED→ARCHIVED; criador ≠ aprovador; publicar exige fonte consultada; nova versão arquiva a anterior; tipo de requisito inválido recusado |
| EligibilityMatchTests | cinco estados; ausência de regra ⇒ PENDENTE; regra jurídica ⇒ REQUER VALIDAÇÃO PROFISSIONAL; hard blockers explicados no match; certificação declarada não satisfaz |
| MaturityBadgeTests | maturidade 0–6 com listas "pode / ainda precisa"; badges com critério, fonte, validade e aviso |
| SolutionIPTests | portão de publicação (titularidade + autorização), confidencialidade/`summary_only`, filtros, prontidão |
| StatementAndCandidatesTests | declaração só afirma o cadastrado; candidatas importam como rascunho |
| ArchitectureInstitutionalTests | rotas declaram autorização; plano não influencia match |
| E2E (Chromium) | página Instituição sem erros de console e com verificações próprias de acessibilidade; viewport de 375 px sem rolagem horizontal; cadastro exibe natureza jurídica |

**Bugs achados pelos testes e corrigidos nesta versão:** política RLS com espaçamento fora do padrão do teste de arquitetura; schema duplicado `NeedIn` (422 em necessidades de rede); portão de publicação quebrando helpers de teste; rolagem horizontal em celular (grid `1fr` sem `min-width: 0`); rótulo do campo de natureza jurídica que continha "CNPJ" e tornava o seletor ambíguo; teste instável `test_signed_tokens` (pré-existente).

**Não testado nesta versão (não afirmar):** E2E do painel administrativo institucional no navegador (exige MFA no fluxo web; a API admin é testada); carga/concorrência da avaliação de elegibilidade; axe e leitor de tela; calibração dos limiares de maturidade com dados reais; validade jurídica dos catálogos e regras.

## Bugs encontrados *pelos testes* e corrigidos
Rota literal capturada por parâmetro · perfil de financiador vazio · opt-out sem DELETE · `why` vs `why_match` · 500 em `/v1/me` da plataforma · botões ocultos no perfil · nomes acessíveis poluídos por chips.
**Teste frágil corrigido:** `test_search_quality` falhou uma vez na suíte completa porque outros módulos publicam soluções quase idênticas no banco compartilhado; a asserção de ranking passou a considerar só as soluções criadas pelo próprio teste (produto inalterado).

## Desempenho e sensibilidade (scripts reproduzíveis)
- `scripts/bench_solution_search.py` → `docs/evidence/search_perf_v0.9.0.json`: 5.000 soluções sintéticas, 54 consultas: **p50 180,6 ms · p95 473,9 ms · máx 526,8 ms** (1 processo, local, sem cache, ponta a ponta). Não é projeção de produção; sem concorrência.
- `scripts/weights_sensitivity.py` → `docs/evidence/weights_sensitivity_v0.9.0.json`: 16/16 perturbações mantêm o esperado no top 3 (pesos achatados também em 1º) ⇒ robusto no corpus sintético, **pesos não discriminados**; calibrar com dados reais.

## O que NÃO foi testado (não afirmar)
Carga concorrente · pentest/fuzzing · axe e leitor de tela · navegadores além do Chromium · dispositivos móveis reais · clamd/S3/SMTP/Stripe/IdP/provedor de IA reais · build Docker · apps Android/iOS · qualidade de relevância com usuários reais · tipos oficiais TS (typecheck offline com *shims*; CI deve validar).
