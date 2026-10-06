# Matriz de requisitos — reconciliação histórica (v0.7.0 → v0.19.0)

> Esta matriz responde à pergunta do pedido: **"tudo que foi pedido ao longo da evolução do Impacto
> está realmente implementado, integrado e funcionando?"** — e não apenas "o que existe agora".
>
> Classificação do pedido: **A** implementado+testado+validado · **B** implementado, testado
> parcialmente · **C** implementado parcialmente · **D** apenas visual · **E** existe e está
> quebrado · **F** ausente · **G** não verificável · **H** implementado e inadequado para produção ·
> **I** dependência externa pendente.
>
> Toda linha **A** aponta o arquivo de teste que a sustenta. Nenhuma linha diz A por documento.

**Estado medido na v0.19.0:** 287 tabelas · 36 migrações · 309 funções SQL · 598 políticas de RLS ·
802 índices · 819 operações de API · 65 arquivos de teste. Contagem de testes e resultado da suíte:
`FINAL_PRE_DESIGN_RELEASE_REPORT.md` (medidos, não repetidos de memória).

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

## 1-A. Vocabulário, primeiro acesso e operação (v0.19.0)

| # | Requisito (origem: PROMPT MASTER pré-designer, §6–§12, §33–§39) | Classe | Onde está | Prova |
|---|---|---|---|---|
| 61 | Dicionário central de termos, com terminologia consistente | **A** | `config/glossary.json` (123 termos, 23 domínios), `GLOSSARY.md` | `test_v0190_glossary.py` (13) |
| 62 | I18N central com namespaces coerentes, sem refatoração destrutiva | **A** | 29 namespaces, 221 chaves por idioma; os 6 do núcleo intactos | `test_v0190_glossary.py::test_i18n_tem_os_namespaces...` |
| 63 | Teste que detecta enum/status/origem/banda/revogação **sem rótulo** | **A** | `core/glossary.py::missing()` nas duas direções | `test_todo_valor_vivo_tem_rotulo...` + `test_o_detector_realmente_reprova` |
| 64 | A interface consome o vocabulário em vez de copiá-lo | **A** | `web/src/glossary.ts` gerado; `core.tsx` importa | `sync_glossary.py --check` dentro da suíte |
| 65 | Primeiro acesso: toda área vazia responde as nove perguntas | **A** | `GET /v1/firstrun`, 12 áreas | `test_v0190_firstrun.py` (16) |
| 66 | Nenhum dado inventado para encher tela | **A** | contagem real; `counted:false` quando não há o que contar | `test_nenhuma_area_devolve_dado_inventado` |
| 67 | Próxima ação por tela, sem CTA comercial artificial | **A** | `next_action` com método, rota e tela reais | `test_toda_rota_de_proximo_passo_existe_no_roteador` |
| 68 | Valor devolvido por declarar contexto, **sem ranking** | **A** | `GET /v1/projects/{id}/context-return`, 8 chaves | `test_declarar_contexto_nao_mexe_na_reputacao` |
| 69 | Exclusão (LGPD) ponta a ponta sobre as tabelas novas | **A** | varredura de todas as colunas de texto após a exclusão | `test_v0190_lgpd_deletion.py` (13) |
| 70 | Classificação DELETABLE / RETAINABLE / ANONYMIZABLE / AUDIT_ONLY | **A** | `config/data_retention.json` + classe `append_only`; `DATA_RETENTION.md` gerado | `test_classe_declarada_bate_com_a_regra_real_da_chave` |
| 71 | Trilha que precisa ser preservada **não** é destruída | **A** | remoção de organização recusada por evidência e por append-only | `OrganizationNotRemovableTests` (3) |
| 72 | Backup com agendador de verdade | **A** | tarefa `backup` em `impacto/jobs.py`, com janela própria | `test_v0190_ops.py::BackupJobTests` (7), com `pg_dump` real |
| 73 | Backup conferido, não apenas gerado | **A** | tamanho + sha256 + `pg_restore --list` | `test_o_backup_roda_de_verdade_e_o_dump_e_valido` |
| 74 | RPO/RTO | **I** | runbook §4-A: o que a configuração ENTREGA está escrito; os **alvos** são decisão do proprietário | `DATA_TO_CONFIRM` declarado |
| 75 | Backup externo (offsite) | **I** | gancho `BACKUP_OFFSITE_CMD` pronto; destino depende de conta e credencial | `BLOCKED_EXTERNAL` declarado; a rota de saúde devolve `offsite: false` |
| 76 | Canário de e-mail | **A** | tarefa `email_canary`, envio real pelo mailer configurado | `test_o_canario_envia_de_verdade_e_registra_o_resultado` |
| 77 | Observabilidade de e-mail (evento, id, status, provedor, erro, tentativas) | **A** | `email_events`, ligado no mailer e não nos 8 pontos de envio | `EmailObservabilityTests` (6) |
| 78 | Não declarar entrega quando houve apenas aceitação SMTP | **A** | `accepted_by_smtp`; o CHECK do banco não aceita `delivered` | `test_o_estado_de_sucesso_se_chama_aceitacao_e_nao_entrega` |
| 79 | Sem armazenar conteúdo sensível de e-mail | **A** | guarda o domínio; nunca endereço nem corpo | `test_o_registro_guarda_o_dominio_e_nunca_o_endereco` |
| 80 | As seis telas que faltam são declaradas, não escondidas | **A** | `screen_status: to_be_designed` + `DESIGN_HANDOFF_FINAL.md` §3 | `test_area_sem_tela_declara_que_a_tela_sera_desenhada` |

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
| 47 | Suíte PostgreSQL real, banco do zero | **A** | v0.19.0: ver `docs/evidence/test_run_v0.19.0.log` |
| 48 | Caminho de atualização v0.17.0 → v0.18.x com dado | **A** | `test_v0181_migrations.py` (8) |
| 49 | Migration que falha não deixa metade aplicada | **A** | mesmo arquivo, teste próprio |
| 50 | Concorrência e corrida nas entidades novas | **A** | `test_v0181_concurrency.py` (9) |
| 51 | E2E de jornada completa | **A** | `test_e2e_v0181_journeys.py` (18) |
| 52 | E2E de navegador (SPA, desktop e mobile) | **B** | `test_e2e_web.py` cobre cadastro→projeto→publicação; **as seis telas da camada v0.18.0 não existem** — declaradas uma a uma em `DESIGN_HANDOFF_FINAL.md` §3 e verificadas por teste |
| 53 | Smoke de publicação | **A** | `scripts/smoke_test.py` (20 verificações) + `test_v0181_smoke.py` |
| 54 | Carga concorrente | **B** | 12 threads, 3.207 req, 160 rps, 0 erro — **mesma máquina**, não é capacidade de produção |
| 55 | Acessibilidade formal | **B** | 12 verificações no navegador; **axe e leitor de tela: NOT VERIFIED** |
| 56 | Auditoria de dependências | **G** | **BLOCKED BY ENVIRONMENT** (npm 403, PyPI indisponível) — controles offline verificados |
| 57 | Docker: build, run, healthcheck | **G** | `Dockerfile` com usuário não-root e `--no-server-header`; **docker não disponível neste ambiente** |
| 58 | Backup → restore → aplicação | **A** | `restore_test.sh` com 6 conferidores novos da camada de impacto |
| 59 | Observabilidade | **B** | `/metrics`, logs com `request_id`/`trace_id`, `job_runs`, e na v0.19.0 `ops_job_runs` + `email_events` + `GET /v1/admin/ops/health`; **sem coletor configurado** |
| 60 | Integrações externas (Stripe, SMTP, S3, ClamAV, IA, fiscal, OIDC) | **I** | todas em modo simulado/declarado; o `/readyz` **diz qual provedor está ligado** |

## 5. O que esta matriz NÃO afirma

- Não afirma conformidade com GRI, ISSB, IRIS+, CVM ou qualquer referencial de terceiro: os três
  primeiros estão **registrados**, sem mapeamento, por decisão pendente de produto e jurídico.
- Não afirma que a plataforma emite documento fiscal, nem que processa pagamento real.
- Não afirma ausência de vulnerabilidade em dependência: a auditoria está **bloqueada pelo
  ambiente**, e isso está escrito como bloqueio, não como aprovação.
- Não afirma conformidade WCAG completa: o que foi verificado está na tabela 1 de
  `ACCESSIBILITY_REPORT.md`, e o que não foi está na tabela 2.
