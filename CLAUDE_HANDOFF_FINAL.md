# CLAUDE_HANDOFF_FINAL — continuação a partir do v0.16.0

> **Estado em v0.16.0:** a rede de impacto está fechada. A cadeia inteira existe como dado — Pessoa/Organização →
> Contexto → Necessidade → Rede → Match → Proposta → Relação → Projeto → Execução → Evidência → Resultado → Novo
> Match — e as dez personas percorrem o **mesmo** núcleo. A próxima etapa é **DESIGN**, não engenharia.
>
> **Comece por:** `FINAL_IMPACT_NETWORK_HARDENING_REPORT.md` (o relatório honesto desta rodada, seções A–N),
> `IMPACT_NETWORK_ARCHITECTURE.md` (a cadeia e os onze motores), `DESIGN_HANDOFF_FINAL.md` (o que o designer recebe,
> incluindo §1: **o pacote "Convergência" não chegou**), `INFORMATION_ARCHITECTURE.md` e `NAVIGATION_MODEL.md`.
>
> **Se for continuar engenharia**, nesta ordem de valor:
> 1. **E2E de navegador nas 27 telas novas** — a lacuna mais relevante; siga o padrão de `test_e2e_v0150_web.py`.
> 2. **Verificação de viewport e contraste** nessas telas (o padrão existe e cobre 25 combinações nas antigas).
> 3. **Exportação de dados pessoais** cobrindo as entidades novas da rede — leia `LGPD_AUDIT.md` primeiro: a
>    pergunta "o que de uma proposta entre duas organizações pertence ao titular pessoa física" é jurídica antes de
>    ser técnica.
> 4. **Prontidão em lote** para baixar o workspace da OSC (341–436 ms) — mesmo padrão de carregador em lote que
>    resolveu o feed, e o mesmo cuidado: foi em `SECURITY DEFINER` que apareceram os defeitos de RLS (ADR 103–105).
> 5. **Carregadores em lote do feed** (`PERFORMANCE_REPORT.md` §5), que continua sendo o caminho mais caro.
>
> **Ferramentas desta rodada que valem reusar:**
> * `scripts/sql_prepare_check.py` — roda `PREPARE` em todo SQL extraído por AST. Rode **antes** de confiar em
>   consulta nova; achou 5 defeitos de nome de coluna que a revisão de código não pegou.
> * `backend/impacto/clock.py` — **nunca** use `date.today()`; há teste de arquitetura que falha.
> * `backend/impacto/network/notify.py` — todo aviso sai por aqui, com chave de idempotência. Motor nunca notifica
>   direto (teste de arquitetura).
>
> **Armadilhas de PostgreSQL aprendidas aqui, para não repetir:**
> 1. `AND` em plpgsql **não** faz curto-circuito: `TG_TABLE_NAME = 'x' AND NEW.coluna_de_x` quebra nas outras
>    tabelas que compartilham o gatilho. Use `IF` aninhado.
> 2. Variável plpgsql com o nome de uma coluna dá "column reference is ambiguous". Prefixe com `v_`.
> 3. `INSERT ... RETURNING` exige que a política de **SELECT** passe, não só a de INSERT.
> 4. `max(uuid)`/`min(uuid)` não existem. Use `ORDER BY ... LIMIT 1`.
> 5. **GRANT de coluna adiciona privilégio e não consegue restringir.** Para restringir, gatilho.
> 6. `guard_columns` isenta `app_priv()` — é inútil em tabela onde só o contexto privilegiado escreve.
>
> **Ambiente:** o PostgreSQL morre quando o contêiner recicla (`pg_ctlcluster 16 main start`). O envio de **tag**
> ao remoto é recusado pelo proxy com 403 — use branch de savepoint (`savepoint/v0.16.0-impact-network-core`). Os
> registros npm e PyPI estão bloqueados, então `npm audit` e `pip-audit` **precisam** rodar em CI.
>
> **Regras do proprietário que continuam valendo:** não inventar teste, integração, publicação, segurança,
> compliance nem benefício fiscal — **PROVE**. Nada de segredo em entregável. Sem ZIP dentro de ZIP. Relatório
> final em português com VERDE/AMARELO/VERMELHO honesto. Versão sempre sobe, documentos anteriores vão para
> `history/vX/`, nada é sobrescrito em silêncio. Nunca enfraquecer nem apagar teste para ficar verde. Nunca
> simular biometria, assinatura qualificada, ICP-Brasil, gov.br, SMS, ACT, Stripe real, provedor fiscal real, KYC
> real ou identidade governamental real.

---

## Estado anterior (v0.15.0)

> **Estado em v0.15.0:** o núcleo do produto está fechado (ideia → diagnóstico → projeto → documento → match →
> acompanhamento). A próxima etapa é **DESIGN**, não engenharia. Comece por `FINAL_PRE_DESIGN_HARDENING_REPORT.md`,
> `CORE_PRODUCT_ARCHITECTURE.md` e `DESIGN_HANDOFF.md` §13 (fluxos A–I e os 20 invariantes de design).
>
> **Se for continuar engenharia**, a lista do que falta está em `RELEASE_READINESS.md` §5 e a próxima otimização
> mapeada está em `PERFORMANCE_REPORT.md` §5 (carregadores em lote para o feed — com o aviso de que foi exatamente
> em `SECURITY DEFINER` que apareceram os defeitos de RLS das versões anteriores: ADR 103, 104, 105).
>
> **Regras do proprietário que continuam valendo:** não inventar teste, integração, publicação, segurança,
> compliance nem benefício fiscal — **PROVE**. Nada de segredo em entregável. Sem ZIP dentro de ZIP. Relatório
> final em português com GREEN/YELLOW/RED honesto. Versão sempre sobe, documentos anteriores vão para
> `history/vX/`, nada é sobrescrito em silêncio.

---

## Continuação original (a partir do v0.10.0)

## Objetivo desta etapa
Receba este pacote como base. **Não assuma que está pronto para produção** (veja `PRODUCTION_READINESS.md`). Primeiro **reproduza**: `ENVIRONMENT_SETUP.md` → `make test` (esperado: suíte verde; log de referência em `docs/evidence/`). Audite o código real, não os documentos.

## Regras (mantidas)
1. Não inventar testes, integrações, publicação, segurança, compliance, benefícios fiscais, dados ou impacto. 2. Dados de demonstração sempre rotulados. 3. Match independente de plano/voucher (teste AST). 4. Fiscal só com regras aprovadas por 2 revisores. 5. IA = rascunho + revisão humana. 6. Aportes não são processados pela plataforma (ADR-022). 7. Nada de segredos no repositório.

## Mapa do código
`backend/impacto/` (engines/solutions, services/solutions.py, api/solution_*.py; config, db, http, services, engines, api, adapters, jobs, cli) · `backend/migrations/` · `backend/tests/` · `web/src/` (api, router, session, ui/kit, pages/*) · `config/` (plans, taxonomy, match_weights, fiscal_rules.candidates) · `infra/` · `mobile/` · `docs/`. Decisões: `DECISIONS.md`. Auditoria: `FINAL_RELEASE_AUDIT.md`.

## Estado no v0.10.0 (leia primeiro)
Camada institucional implementada e testada (233 testes). Próximos passos, em ordem: (1) **revisão jurídica** dos catálogos e das regras candidatas e publicação com 2 aprovadores; (2) E2E do painel administrativo institucional (exige MFA no navegador); (3) cruzar a rota de estimativas fiscais com `osc_org_id` e `fiscal_layers`; (4) seed DEMO institucional (marcado DEMO); (5) calibrar `config/institutional_maturity.json`. Documentos: `THIRD_SECTOR_MODEL.md`, `INSTITUTIONAL_ELIGIBILITY_ENGINE.md`, `FISCAL_RULE_ENGINE.md`, `MATCH_ENGINE.md`, `REPOSITORY_PROJECTS.md`, `DATABASE_SCHEMA.md`.

## Estado no v0.9.0
Itens D1–D6 abaixo (PF/profissional, ODS/Impact Graph, compras, risco, mapas, rede) **foram feitos no v0.8.0**; a **Biblioteca de Soluções** foi feita no v0.9.0. Leia `SOLUTION_LIBRARY.md` e `FINAL_RELEASE_AUDIT.md` §3-A.
**Próximos passos específicos da Biblioteca:** (1) curadoria real + remoção de DEMO; (2) coletar sinais de uso (`solution_events`, `unmatched_terms`) e **calibrar** `config/solution_weights.json`/`match_weights.json` com conjunto de relevância rotulado; (3) avaliar pgvector (ou serviço equivalente) para o passo vetorial (`AI_SEARCH_ARCHITECTURE.md`); (4) refinamento de intenção por LLM restrito ao tesauro, via gateway; (5) importadores de fontes externas; (6) axe + usabilidade; (7) cache/particionamento quando o volume pedir; (8) mapa com tiles após decidir provedor/CSP.
Dívidas: `search()` pontua em Python até 200 candidatos; tesauro curado à mão; `solution_events` sem particionamento.

## Próximos passos em ordem de valor (lista original v0.7.0 — itens D já entregues, mantida por rastreabilidade)
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

## Estado após o v0.10.1
Fechadas as pendências institucionais factíveis (ver `FINAL_RELEASE_AUDIT.md` §3-C). **Próximo:** v0.11.0 — Central de Conhecimento, Operação, Capacitação, Suporte, Eventos, Parcerias e Trial (auditar notificações/documentos/materiais/suporte/eventos/planos antes de criar; migração `0008`). Fluxo de trabalho: `docs/WORKFLOW_GIT.md`; savepoints são **branches** (`savepoint/…`), pois tags não sobem pelo proxy.

## Como validar rapidamente
`make db && make web && make test` · `python3 scripts/make_release.py --verify` · `curl localhost:8080/readyz`.

## Atualização v0.11.0 — monetização
Leia `docs/billing.md`. Estado: backend/frontend/testes completos (290 verdes); **pendente externo**: conta Stripe e homologação, definição dos preços (`PUT /v1/admin/plans/{plan_key}/price`), e-mail transacional, jurídico (termos de assinatura/reembolso, RIPD), validação PLUS×PREMIUM. Não invente preços, price IDs ou chaves. Próximo incremento planejado: Central de Conhecimento (v0.12.0). Snapshot do estado anterior: `history/v0.10.1/`.

## Atualização v0.12.0 (Central de Conhecimento)
Base: `KNOWLEDGE_HUB.md` (auditoria do que já existia, entrega e limites). Código: `backend/impacto/services/{knowledge,hub,kb_seed}.py`, `engines/knowledge/search.py`, `api/{knowledge_routes,content_admin_routes,hub_schemas}.py`, migração `0009`, `web/src/pages/{help,helpAdmin}.tsx`. Testes: `tests/test_v0120_knowledge.py` (62) e `tests/test_e2e_knowledge.py` (5). **Próximos passos honestos:** (1) redigir e publicar conteúdo oficial pelo fluxo de quatro olhos; (2) ligar `ContextHelp` nas demais telas (hoje 3); (3) escolher provedor de IA **só se** desejado; (4) calibrar pesos de busca e SLA com dados reais; (5) preços/NF/Stripe real; (6) auditoria de dependências em CI; (7) camada de design (ver `STORE_READINESS.md`). Cuidados: curso publicado não é editado no lugar; editor de curso/recurso/FAQ/evento é JSON; papéis `editor/reviewer/support` ainda vivem em contas de organização com MFA.
