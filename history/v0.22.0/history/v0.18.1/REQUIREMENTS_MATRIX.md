# Matriz de requisitos — reconciliação histórica (v0.7.0 → v0.18.1)

> Esta matriz responde à pergunta do pedido: **"tudo que foi pedido ao longo da evolução do Impacto
> está realmente implementado, integrado e funcionando?"** — e não apenas "o que existe agora".
>
> Classificação do pedido: **A** implementado+testado+validado · **B** implementado, testado
> parcialmente · **C** implementado parcialmente · **D** apenas visual · **E** existe e está
> quebrado · **F** ausente · **G** não verificável · **H** implementado e inadequado para produção ·
> **I** dependência externa pendente.
>
> Toda linha **A** aponta o arquivo de teste que a sustenta. Nenhuma linha diz A por documento.

**Estado medido nesta rodada:** 285 tabelas · 34 migrações · 309 funções SQL · 593 políticas de RLS
· 815 operações de API · 28 motores declarados · 1.298 testes (0 falhas, 26 em passo próprio).

## 1. Núcleo do produto (ciclo de impacto)

| # | Requisito (origem) | Classe | Onde está | Prova |
|---|---|---|---|---|
| 1 | Identidade, conta, MFA, sessão, SSO/OIDC | **A** | `auth_routes` (20 rotas), `security/`, `services/oidc.py` | `test_api_auth.py`, `test_oidc.py`, smoke `login`/`session` |
| 2 | Organização, membros, papéis, compliance | **A** | `org_routes`, `memberships` | `test_api_features.py`, matriz de isolamento |
| 3 | Programa (entidade de 1ª classe) | **A** | `programs` + 13 rotas | `test_v0170_programs.py` (19) |
| 4 | Projeto, orçamento, marcos, execução | **A** | `projects`, `budget_items`, `milestones` | `test_api_workflow.py`, `test_e2e_v0181_journeys.py` |
| 5 | Oportunidade/edital e candidatura | **A** | `calls`, `applications` (25+7 rotas) | `test_e2e_v0181_journeys.py` passo 08 |
| 6 | Aporte registrado sem custódia | **A** | `commitments` (ADR-022) | `test_v0150_core.py`, jornada da rede |
| 7 | Contrato/instrumento e assinatura | **A** | `signed_agreements`, `signatures` | `test_v0140_trust.py`, `test_e2e_v0140_trust.py` |
| 8 | Evidência, medição reportada × validada | **A** | `evidences`, `indicator_values` (CHECK de separação de funções) | `test_v080.py`, jornada passo 07 |
| 9 | Resultado, impacto, série longitudinal | **A** | `impact_nodes/edges`, `impact/longitudinal.py` | jornada passos 07 e 17 |
| 10 | Inteligência (match, diagnóstico, recomendação) | **A** | `engines/match`, `core/diagnostic.py` | `test_unit.py` (match), jornada passos 03 e 08 |
| 11 | Governança (auditoria, trilha, moderação) | **A** | `audit_events` encadeado, `moderação` (8 rotas) | `test_security_tenancy.py`, jornada passo 18 |
| 12 | **Os módulos conversam** (não são ilhas) | **A** | a jornada percorre 18 passos sem atalho de banco | `test_e2e_v0181_journeys.py` — 1 projeto, 18 etapas, 1 trilha |

## 2. Impacto contextualizado (v0.18.0–v0.18.1)

| # | Requisito | Classe | Prova |
|---|---|---|---|
| 13 | Equidade ≠ igualdade; quantidade não é impacto | **A** | `test_v0180_equity.py` (30), `test_v0180_security.py::BiasTests` |
| 14 | Normalização só com denominador declarado com fonte | **A** | 7 métodos; resposta "indisponível" com motivo |
| 15 | UNKNOWN ≠ ZERO ≠ FALHA ≠ SUCESSO | **A** | `contextual_impact` devolve `None`; `test_impact_core_hardening.py` |
| 16 | Comparação sem veredito | **A** | `compare()` → `comparable:false` + motivos |
| 17 | Determinantes sociais | **B** | 15 definições editoriais; `territory_indicators` **vazia** (dado oficial não entrou) |
| 18 | Território e perfil territorial | **B** | catálogo com `from_official_load`; **I** para a carga do IBGE |
| 19 | ODS: projeto→meta→indicador→evidência→resultado | **B** | cadeia implementada; **as 169 metas oficiais não carregadas** (classe **I**) |
| 20 | ODS alinhado ≠ alcançado ≠ certificado | **A** | `alignment_level`; jornada passo 05 |
| 21 | ESG separado em E/S/G | **A** | `esg_dimension` no catálogo de indicadores |
| 22 | Materialidade (financeira, impacto, dupla) | **A** | `materiality_*`; `is_material` derivada |
| 23 | Interoperabilidade de referenciais | **B** | 19 registrados; **mapeamento GRI/ISSB/IRIS+ pendente de decisão** (classe **I**) |
| 24 | Escada aligned→…→audited, sem `certified` | **A** | gatilho `framework_relation_gate()` |
| 25 | Integridade de alegação (anti-greenwashing) | **A** | 12 regras determinísticas; `test_v0180_claims.py` (42) |
| 26 | FLAGGED + revisão humana, nunca "fraude" | **A** | revisão por convite; `flagged_accepted_by_review` |
| 27 | Reputação multidimensional, explicável | **A** | 6 dimensões; `test_v0180_reputation.py` (30) |
| 28 | Sem pay-to-rank | **A** | varredura AST + teste de plano pago |
| 29 | Órgão público sem nota; pessoa física sem perfil | **A** | `NO_SCORE_KINDS`, 403 `no_public_profile_for_person` |
| 30 | Contestação e correção | **A** | contestação aparece no perfil; correção gera ponto novo |
| 31 | Selo por regra, nunca comprável | **A** | critério em SQL; app sem INSERT; `test_v0180_seals.py` (23) |
| 32 | Selo com definição/versão/validade/revogação/trilha | **A** | `seal_definitions` imutável, `seal_revocations` |
| 33 | Smart forms com origem da sugestão | **A** | 13 buscas; `test_v0180_lookups.py` (17) |
| 34 | Nunca sobrescrever o que a pessoa escreveu | **A** | `Suggest` pergunta e oferece desfazer |
| 35 | Responsabilidade × papel × escopo × versão × decisão | **A** | `test_v0180_responsibility.py` (25) |
| 36 | Quatro-olhos onde a regra exige | **A** | `requires_two` em dado + gatilho; 8+ pontos no produto |
| 37 | Assinatura amarrada a DOCUMENTO+VERSÃO | **A** | `subject_sha256` (v0.14.0) + decisão aponta versão (v0.18.0) |
| 38 | Proveniência por campo no documento | **A** | `assembly.py` devolve `provenance` por campo |
| 39 | Oito prontidões do diagnóstico | **A** | `READINESS_MAP`; jornada passo 03 |
| 40 | IA assistida com revisão humana; IA não decide | **A** | registro de 28 motores + varredura de chamadas |

## 3. Economia, legal e pagamento (v0.17.0)

| # | Requisito | Classe | Prova |
|---|---|---|---|
| 41 | Proponente não é o pagador principal | **A** | ADR-173; entrada gratuita permanente |
| 42 | Value Ledger separado da cobrança | **A** | `test_v0170_value.py` (16) |
| 43 | Monetização com portão legal | **A** | 9 regras, **zero verdes, nenhuma ativa** |
| 44 | Arquitetura de pagamento sem provedor real | **A/I** | `PRODUCTION PAYMENT NOT CONFIGURED`; provedor real é **I** |
| 45 | Documentos legais versionados com aceite+sha256 | **A/I** | 11 minutas, **nenhuma aprovada** — aprovação jurídica é **I** |
| 46 | Motor fiscal com fonte e dupla aprovação | **A/I** | regras candidatas; emissão real é **I** |

## 4. Operação e publicação

| # | Requisito | Classe | Prova / pendência |
|---|---|---|---|
| 47 | Suíte PostgreSQL real, banco do zero | **A** | 1.298 testes; `docs/evidence/test_run_v0.18.1.log` |
| 48 | Caminho de atualização v0.17.0 → v0.18.x com dado | **A** | `test_v0181_migrations.py` (8) |
| 49 | Migration que falha não deixa metade aplicada | **A** | mesmo arquivo, teste próprio |
| 50 | Concorrência e corrida nas entidades novas | **A** | `test_v0181_concurrency.py` (9) |
| 51 | E2E de jornada completa | **A** | `test_e2e_v0181_journeys.py` (18) |
| 52 | E2E de navegador (SPA, desktop e mobile) | **B** | `test_e2e_web.py` cobre cadastro→projeto→publicação; **as telas da camada v0.18.0 não existem ainda** (fase de design) |
| 53 | Smoke de publicação | **A** | `scripts/smoke_test.py` (20 verificações) + `test_v0181_smoke.py` |
| 54 | Carga concorrente | **B** | 12 threads, 3.207 req, 160 rps, 0 erro — **mesma máquina**, não é capacidade de produção |
| 55 | Acessibilidade formal | **B** | 12 verificações no navegador; **axe e leitor de tela: NOT VERIFIED** |
| 56 | Auditoria de dependências | **G** | **BLOCKED BY ENVIRONMENT** (npm 403, PyPI indisponível) — controles offline verificados |
| 57 | Docker: build, run, healthcheck | **G** | `Dockerfile` com usuário não-root e `--no-server-header`; **docker não disponível neste ambiente** |
| 58 | Backup → restore → aplicação | **A** | `restore_test.sh` com 6 conferidores novos da camada de impacto |
| 59 | Observabilidade | **B** | `/metrics`, logs estruturados com `request_id`/`trace_id`, `job_runs`; **sem coletor configurado** |
| 60 | Integrações externas (Stripe, SMTP, S3, ClamAV, IA, fiscal, OIDC) | **I** | todas em modo simulado/declarado; o `/readyz` **diz qual provedor está ligado** |

## 5. O que esta matriz NÃO afirma

- Não afirma conformidade com GRI, ISSB, IRIS+, CVM ou qualquer referencial de terceiro: os três
  primeiros estão **registrados**, sem mapeamento, por decisão pendente de produto e jurídico.
- Não afirma que a plataforma emite documento fiscal, nem que processa pagamento real.
- Não afirma ausência de vulnerabilidade em dependência: a auditoria está **bloqueada pelo
  ambiente**, e isso está escrito como bloqueio, não como aprovação.
- Não afirma conformidade WCAG completa: o que foi verificado está na tabela 1 de
  `ACCESSIBILITY_REPORT.md`, e o que não foi está na tabela 2.
