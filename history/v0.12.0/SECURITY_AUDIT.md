# SECURITY_AUDIT — v0.10.0 (2026-10-05)

Escopo: código do repositório + execução local. **Não é pentest.** Controles detalhados e testes: `docs/SECURITY.md`.
Resultado: **GREEN** = verificado por teste · **YELLOW** = implementado, depende de config/serviço real · **RED** = ausente.

## Achados do v0.6.0 (corrigidos)
| # | Achado | Severidade | Correção |
|---|---|---|---|
| S1 | RLS só em arquivo SQL, nunca aplicado/testado | Crítica | RLS aplicado, papel sem BYPASSRLS, teste via SQL direto — GREEN |
| S2 | Autenticação de demonstração | Crítica | scrypt + sessões + refresh rotativo + MFA — GREEN |
| S3 | Ausência de proteção CSRF/brute force/enumeração | Alta | implementados e testados — GREEN |
| S4 | Upload sem validação | Alta | allowlist, magic bytes, conteúdo ativo, zip bomb, antivírus — GREEN (clamd real: YELLOW) |
| S5 | Segredos/config sem validação | Alta | fail-fast em staging/production — GREEN |

## Bugs de segurança/autorização encontrados e corrigidos na construção
Body validado antes da autorização (vazava esquema) · UUID inválido gerava 500 · falta de política UPDATE · contadores de lockout/MFA/reuso revertidos por rollback (permitia tentativas ilimitadas) · plano sem preço comprável · voucher com falha de serialização.

## v0.8.0 / v0.9.0 — achados e correções na construção
| # | Achado | Gravidade | Correção / prova |
|---|---|---|---|
| S6 | `/v1/me` retornava 500 para a organização da plataforma (faltava `plan_names`) | Média (disponibilidade do admin) | corrigido; `test_regression_me_works_for_platform_org` |
| S7 | Opt-out de personalização não apagava o histórico de buscas (sem política DELETE) | Média (LGPD) | política `slog_delete`; teste |
| S8 | Rota literal capturada por `/{solution_id}` | Baixa | ordenação por especificidade; teste |
| S9 | Perfil de financiador vazio gerava recomendações "com base" inexistente | Baixa (honestidade) | `funder_profile_missing` |
| — | Função de metadados documentais negava financiador PF (v0.8.0) | Baixa | corrigida na 0004 |

## Controles da Biblioteca de Soluções (todos provados por teste, inclusive via SQL direto como `impacto_app`)
- **RLS em 20 tabelas novas**; rascunho só da organização; publicado visível a autenticados; bloqueio entre organizações respeitado em pedidos/mensagens.
- **Colunas protegidas por gatilho**: `trust_level`, `verified_*`, `is_demo`, `disputed`, `removed`, `generated_draft` só pela administração/sistema; evidência `status` e resultado `validated` só admin; tentativa do autor → 403/erro de banco.
- **Intenção**: etapas só via funções `SECURITY DEFINER` que validam pedido real/aceite do autor; `UPDATE` direto de etapa é bloqueado; eventos append-only.
- **Privacidade**: identidade do financiador/replicador privada por padrão; contagens por organizações distintas; log de busca sem texto.
- **Anti-manipulação**: avaliações só com relação real e fora do ranking; visualização ≠ intenção; dedupe diário; limite de 10 pedidos/dia/organização.
- **Entrada**: UUID validado, corpo `extra=forbid`, tamanhos máximos, URLs de evidência apenas `https`, consulta com `to_tsquery` construída a partir de tokens sanitizados (nunca texto cru), SQL só parametrizado.
- **Rate limit** de busca 120/10 min.
- Exportar/denunciar: `POST /v1/reports` aceita `target_type = solution`.
**Não testado:** abuso em escala (scraping distribuído), pentest, fuzzing de `to_tsquery` além dos casos de teste.

## OWASP Top 10 (mapa)
| Risco | Estado |
|---|---|
| A01 Broken Access Control | GREEN — RLS + RouteSpec + testes IDOR/escalonamento |
| A02 Cryptographic Failures | GREEN/YELLOW — scrypt, Fernet, HMAC, TLS depende do proxy; criptografia em repouso do disco/S3 é da infraestrutura |
| A03 Injection | GREEN — somente consultas parametrizadas (`PQexecParams`); teste de arquitetura contra SQL concatenado; CSP; saída escapada pelo React |
| A04 Insecure Design | YELLOW — threat model informal; v0.9.0 acrescenta modelo de abuso da intenção/avaliação (acima); sem STRIDE formal |
| A05 Security Misconfiguration | GREEN — fail-fast, headers, CORS allowlist |
| A06 Vulnerable Components | **YELLOW — sem varredura (rede bloqueada)**; pip-audit/npm audit no CI |
| A07 Identification & Auth Failures | GREEN — ver S2/S3; WebAuthn ausente |
| A08 Integrity Failures | GREEN — cadeias de hash, webhook assinado; supply chain de CI não endurecida |
| A09 Logging & Monitoring | YELLOW — logs JSON/métricas/auditoria; sem SIEM, traces ou alertas ativos |
| A10 SSRF | GREEN/YELLOW — `HttpClient` só aceita https, bloqueia IPs privados/link-local (metadados de nuvem)/reservados/loopback e **não segue redirecionamentos** (teste `SsrfTests`); risco residual de DNS rebinding → restringir *egress* na rede |

## Camada institucional (v0.10.0)
| Controle | Estado | Evidência |
|---|---|---|
| RLS em todas as tabelas novas (`inst_catalog_items`, `eligibility_rules`, `organization_qualifications`, `organization_qualification_events`, `proponent_needs`, `eligibility_evaluations`) | GREEN | `test_every_table_has_rls` + testes de RLS por papel |
| Verificação de qualificação/documento só por admin da plataforma (+MFA) | GREEN | testes de autorização (403 para membros) |
| Quatro olhos em catálogos/regras (criador ≠ aprovador) | GREEN | `RuleWorkflowTests` |
| Situação institucional e validação de documento/qualificação não alteráveis pelo papel da aplicação (gatilhos); avaliações de elegibilidade append-only; solução confidencial invisível a terceiros (RLS) | GREEN | gatilhos `org_inst_guard`, `qualification_guard`, `document_validation_guard`, `trg_append_only`; testes |
| Eventos de qualificação não alteráveis pelo papel da aplicação | YELLOW | RLS só com política de leitura (escrita só por contexto privilegiado); o papel dono do esquema pode alterar — sem cadeia de hash nesta tabela |
| Todo handler declara autorização | GREEN | `test_handlers_declare_auth` (inclui 37 rotas novas) |
| Avaliação de elegibilidade com limite de taxa | GREEN | `rate=("elig_eval", 120, 600)` |
| Requisitos de regra validados contra conjunto fechado (sem execução de código/expressão) | GREEN | `validate_requirement` + testes |
| Perfil público institucional expõe só dados públicos/verificados | YELLOW | testado para campos principais; revisar com o jurídico |
| Titularidade/IP declarada não é verificada | YELLOW (limite assumido) | aviso na publicação; ADR-051 |
Sem pentest. Nenhum segredo no pacote (varredura em `make_release.py`).

## Pendências institucionais (v0.10.1)
| Controle | Estado | Evidência |
|---|---|---|
| RLS nas 3 tabelas novas (`organization_agreements`, `formalization_steps`, `mentoring_requests`) | GREEN | `test_every_table_has_rls` + isolamento entre organizações |
| Org não promove verificação de instrumento (API e SQL direto); mentoria: org só cancela | GREEN | gatilhos `agreement_guard`, `mentoring_guard`; testes |
| Verificação de instrumento exige admin + MFA e critérios | GREEN | testes (403/422) e E2E admin com MFA real |
| Limites de taxa e de pedidos abertos de mentoria | GREEN | 429 testado |
| Rede da solução sem identidades de interessados/replicadores; rascunho de outra org inacessível | GREEN | `NetworkGraphTests` |
| Terceiros autenticados só enxergam instrumentos VERIFICADOS (RLS `oa_read`); declarados ficam privados | GREEN | `AgreementTests` (SQL direto como financiador) |
Sem pentest. Não há linter Python nesta construção.

## Lacunas / recomendações antes de produção
1. Pentest independente e varredura de dependências. 2. Restrição de *egress* de rede do contêiner (complementa o bloqueio SSRF da aplicação). 3. KMS/cofre de segredos e rotação. 4. Armazenamento seguro de tokens no app móvel. 5. WAF/CDN e DDoS. 6. Revisão do CSP quando adicionar mapas/analytics. 7. Política de retenção de logs e acesso. 8. Teste de carga e de resiliência. 9. Plano de resposta a incidentes (ANPD art. 48). 10. Revisão do usuário `postgres`/rede do banco (somente rede privada).

## Declaração
Nenhuma afirmação de "seguro" é feita além do que os testes provam. Os testes cobrem os controles listados; **ausência de falhas nos testes não implica ausência de vulnerabilidades**.

## Monetização (v0.11.0)
| Controle | Estado | Evidência |
|---|---|---|
| Cliente não define plano/preço/desconto/direito (422 em campos extras; RLS + `billing_guard` impedem escrita direta como papel da aplicação) | GREEN | `BillingSecurityTests` |
| Isolamento entre organizações (trial, assinatura, faturas, licenças, avisos; `agreements`/`trial_claims` invisíveis) | GREEN | idem |
| Webhook: HMAC, tolerância 300 s, idempotência, replay antigo recusado, evento fora de ordem ignorado | GREEN (dublê) | `StripeFlowTests` |
| Checkout/cancelar/trocar/portal só `owner`; admin com MFA, motivo e auditoria; quatro olhos para convênio/lote | GREEN | testes |
| Códigos de voucher/convênio só como HMAC; respostas genéricas; limite de taxa | GREEN | testes |
| Sem dados de cartão no esquema | GREEN | teste de esquema |
| Segredos: apenas placeholders em `.env.example`; teste de arquitetura de segredos verde | GREEN | `test_architecture` |
Pendente: pentest; verificação da assinatura com segredo real do Stripe; revisão do contexto de sistema nas rotas de cotação (rodam em `system_tx` com `org_id` da sessão, por RLS de vouchers/convênios).

## Central de Conhecimento (v0.12.0)
| Controle | Estado | Evidência |
|---|---|---|
| Rascunho/aprovado/arquivado nunca público; visibilidade `public/authenticated/audience` aplicada no banco (`kb_visible`) | GREEN | `Editorial`, `Visibility` |
| Quatro olhos (autor ≠ aprovador) inclusive para administrador; banco recusa UPDATE direto | GREEN | `test_author_cannot_approve_even_as_platform_admin_and_db_enforces_it` |
| Versão publicada imutável; regulatório exige fonte+data | GREEN | `test_published_version_is_immutable…`, `test_regulatory_content_…` |
| Rotas internas exigem papel + MFA; só administrador concede papéis | GREEN | `test_roles_are_enforced`, `test_staff_routes_require_mfa`, `test_admin_grants_and_revokes_staff_roles` |
| Chamado privado (IDOR), pessoa não define prioridade/estado/SLA, nota interna invisível, anexo só de documento da própria organização | GREEN | `test_tickets_are_private_…`, `test_user_cannot_set_priority_…`, `test_attachment_must_be_own_org_document` |
| Quiz: gabarito nunca sai do banco (nem por SQL como aplicação) | GREEN | `test_quiz_key_never_leaves_the_server` |
| Link de acesso de evento só para inscrita confirmada | GREEN | `test_registration_waitlist_promotion_and_private_join_link` |
| Endpoints públicos com limite de taxa; validação de entrada (tamanhos, URLs https, e-mail) | GREEN | `test_public_endpoints_are_rate_limited_in_spec`, `test_search_validates_input` |
| Captação: consentimento obrigatório, honeypot, pedido de outra pessoa ilegível, boletim com duplo opt-in e token em hash | GREEN | `Captation` |
| Pedido de teste nunca concede acesso; só dono pede, só administrador decide | GREEN | `TrialRequests` |
| XSS: conteúdo renderizado como **texto** (sem `dangerouslySetInnerHTML`/`innerHTML` no frontend); JSON-LD via `textContent`; CSP mantida (E2E sem violações) | GREEN (por inspeção + E2E) | `grep` + `test_e2e_*` |
| Assistente não usa conteúdo não publicado e não inventa | GREEN | `test_assistant_*` |
| Pendente | YELLOW | pentest; privilégio amplo do modo administrativo (disciplina de código); auditoria de dependências npm/pip **não executada** (rede bloqueada neste ambiente); SMTP real |
