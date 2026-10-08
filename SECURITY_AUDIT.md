# SECURITY_AUDIT — v0.18.1 (2026-10-06)

## 0. Auditoria de dependências — **EXECUTADA NO CI na v0.24.1**

Até a v0.24.0 nenhuma auditoria de dependências tinha rodado em lugar nenhum: aqui o registry
responde 403, e no GitHub Actions o passo de auditoria vinha DEPOIS da suíte, que morria antes, no
primeiro passo (a action do gitleaks exigia licença). Na v0.24.1 a auditoria ganhou job próprio
(`auditoria`, em `.github/workflows/ci.yml`) e rodou pela primeira vez.

**O que ela achou** — execução `37720370295`, nas dependências de EXECUÇÃO do backend:

| Pacote | Versão | Vulnerabilidades | Corrigidas em | Onde o produto usa |
|---|---|---:|---|---|
| PyJWT | 2.14.0 | 2 | 2.15.0 | validação do `id_token` do login corporativo (`services/oidc.py`) |
| pypdf | 5.9.0 | 49 | 6.19.0 (a maior versão de correção entre as 49) | extração de texto de **PDF enviado por usuário** (`services/documents.py`) — exatamente o caminho que PDF malformado atinge |

As versões de destino vêm do relatório (`fix_versions`), não de escolha.

**Depois da atualização** — execução `37720482955`: `pip-audit` (requirements + opcionais) com 0 itens
relatados; `npm audit --omit=dev` com 0 itens relatados; a imagem Docker construiu com as versões
novas. Isso é o que as duas ferramentas relataram contra as bases públicas naquele momento — não é
prova de ausência de falha, e a auditoria roda de novo a cada push.

### Histórico: até a v0.24.0 — **BLOCKED BY ENVIRONMENT**


Classificação honesta, porque "não consegui executar" **não é** "sem vulnerabilidades":

| Ferramenta | Situação | Evidência colhida nesta rodada |
|---|---|---|
| `npm audit` | **BLOCKED BY ENVIRONMENT** | `npm error code ENOLOCK ... requires an existing lockfile`; e ao tentar gerar o lockfile: `npm error 403 403 Forbidden - GET https://registry.npmjs.org/@capacitor%2fandroid` |
| `pip-audit` | **BLOCKED BY ENVIRONMENT** | `ERROR: Could not find a version that satisfies the requirement pip-audit (from versions: none)` — e `pip download packaging` falha igual: o índice PyPI não responde neste ambiente |
| SBOM (CycloneDX/SPDX) | **NOT VERIFIED** | depende do mesmo registry; o inventário manual está em `THIRD_PARTY_DEPENDENCIES.md` |

**Nenhuma afirmação sobre CVE é feita nesta versão.** O que foi possível verificar offline, e está
coberto por teste (`test_v0181_hardening.py::DependencyControlTests`):

| Controle | Situação | Prova |
|---|---|---|
| Toda dependência de execução com versão exata (`==`) | 🟢 | `requirements.txt` sem faixa aberta |
| Dependência web instalada com versão exata **e igual à instalada** | 🟢 | lido de `node_modules/*/package.json` |
| Dependência declarada e **nunca instalada** marcada `NOT VERIFIED` no inventário | 🟢 | `@types/*` e `@capacitor/*` — faixa `^`, nunca baixadas aqui |
| Nenhum pacote de terceiro importado sem estar declarado | 🟢 | varredura de `import` em `impacto/**` contra os três `requirements*.txt` |
| O documento não afirma ausência de vulnerabilidade | 🟢 | teste procura a frase e reprova se ela aparecer |

**Condição para o GO de publicação:** rodar `npm audit` e `pip-audit` num ambiente com acesso aos
registries, anexar a saída em `docs/evidence/` e registrar exceção formal para cada achado que não
for corrigido. Sem isso, este item permanece condicionado — e nenhum relatório desta versão diz o
contrário.



Escopo: código do repositório + execução local. **Não é pentest.** Controles detalhados e testes: `docs/SECURITY.md`.
A lista linha a linha, com a prova de cada item e as **9 pendências honestas**, está em
**`SECURITY_FINAL_CHECKLIST.md`**.
Resultado: **GREEN** = verificado por teste · **YELLOW** = implementado, depende de config/serviço real · **RED** = ausente.

## v0.18.0 — a camada de impacto contextualizado sob auditoria

| # | Verificação | Situação | Prova |
|---|---|---|---|
| 1 | RLS habilitada nas **33 tabelas** das migrações 0025–0031 | 🟢 | lido de `pg_class` · `test_v0180_security.py` |
| 2 | Política em cada uma (RLS ligada sem política nega tudo e quebra em silêncio) | 🟢 | lido de `pg_policies` |
| 3 | Inventário **declarado** das tabelas de leitura aberta, com o motivo de cada uma | 🟢 | `OPEN_ON_PURPOSE` (19 tabelas) + teste que falha se aparecer uma nova sem motivo |
| 4 | Escrita de reputação e de selo **fora do alcance da aplicação** | 🟢 | sem `INSERT` em `reputation_snapshots`, `seal_awards`, `seal_evaluations`; só `app_record_reputation()` e `app_award_seal()`, `SECURITY DEFINER` com `search_path` fixo |
| 5 | Onde o `INSERT` existe, a **política** exige contexto privilegiado | 🟢 | teste lê `with_check` de `pg_policies` procurando `app_priv` (7 tabelas) |
| 6 | Trilhas append-only sem `UPDATE` nem `DELETE` para o papel da aplicação | 🟢 | 10 trilhas conferidas uma a uma |
| 7 | Recursão entre políticas de RLS resolvida sem afrouxar nenhuma | 🟢 | `app_claim_invited()` responde só "fui convidado?", sem devolver conteúdo |
| 8 | Isolamento entre organizações, linha a linha, **com o teste par** | 🟢 | 9 tabelas; o teste par prova que o cenário escreveu dado |
| 9 | Nenhuma coluna de CPF, RG ou documento nas tabelas novas | 🟢 | `information_schema`, casamento por **palavra** (`LIKE '%rg%'` acusava `org_id`) |
| 10 | Único nome de pessoa é `responsibility_assignments.external_name`, sem documento ao lado | 🟢 | teste explícito |
| 11 | Busca incremental sem vazamento: fornecedor, projeto e indicador próprio são da organização | 🟢 | três testes de isolamento · autocomplete é a forma mais silenciosa de vazar dado |
| 12 | `%` e `_` digitados tratados como texto, não curinga | 🟢 | sem escapar, quem digita `%` recebia o catálogo inteiro |
| 13 | Nenhuma decisão automática sobre pessoa a partir de nota | 🟢 | reputação não alimenta busca, match, recomendação, elegibilidade nem selo (varredura no SQL da migração de selos) |

## v0.17.0 — a camada econômica sob auditoria

A rodada acrescentou **22 tabelas** (253 no total) que tratam de dinheiro, de regra de receita e de prova de aceite.
A revisão foi feita **lendo o catálogo do PostgreSQL**, não o código, porque o que vale é o estado real do banco:

| Verificação | Resultado |
|---|---|
| RLS ligada nas 22 tabelas novas | 🟢 todas |
| Pelo menos uma política em cada | 🟢 todas (RLS ligada sem política nega tudo: parece seguro e quebra o produto em silêncio) |
| `value_events` e `charge_events` sem INSERT para a aplicação | 🟢 escrita só por gatilho ou função `SECURITY DEFINER` |
| `SECURITY DEFINER` sem `search_path` fixo | 🟢 nenhuma das 75 funções |
| FK quente sem índice | 🟢 nenhuma (a revisão achou uma, `legal_acceptances.org_id`, e ela foi criada) |
| Coluna nova com cara de dado pessoal sem justificativa | 🟢 nenhuma; as quatro exceções são declaradas uma a uma com o motivo |
| Isolamento entre organizações nas tabelas novas | 🟢 matriz linha a linha, **com o teste par** que falha se o filtro do próprio teste não achar nada |
| Token de cartão legível pela administração da plataforma | 🟢 **não**: a política de `payment_instruments` não tem exceção para privilégio |
| Coluna para número de cartão, CVV ou validade | 🟢 **não existe**, e há teste varrendo o catálogo |

### Três travas que valem destaque nesta auditoria

1. **`is_simulated` é derivada do provedor** e a tentativa de alterá-la é **recusada**, não sobrescrita em silêncio.
   Sobrescrever resolveria o caso igual e deixaria quem tentou marcar cobrança de teste como real sem nenhum sinal.
2. **A trilha de cobrança é escrita por gatilho `SECURITY DEFINER`** porque a aplicação não tem INSERT em
   `charge_events`. A saída fácil — conceder o INSERT — resolveria o erro de permissão e abriria a porta para
   inventar linha de trilha à mão.
3. **Webhook sem assinatura conferida é registrado e não produz efeito**, com CHECK no banco impedindo que ele
   chegue a "processado". "Não aplicar" é a parte que ninguém lembra de testar quando a integração for ligada.

### Pendência que esta rodada NÃO fechou

O **segredo de assinatura do webhook** não existe porque não há conta de provedor. O caminho de verificação está
implementado e testado contra assinatura inválida; contra assinatura **válida de provedor real**, não — e não há como
testar isso aqui. Fica 🟡 declarado.

## v0.16.0 — a rede de impacto sob auditoria

A rodada acrescentou 26 tabelas, 79 rotas e um grafo de relações entre organizações. Isso muda o problema de
segurança de forma qualitativa: até aqui quase todo dado pertencia a **uma** organização, e a política de RLS
comparava `org_id = app_org()`. Uma relação, uma proposta e uma conversa pertencem a **duas**.

| Risco novo | Como está tratado | Prova |
|---|---|---|
| **Fato de rede forjado** (gravar evento em nome da contraparte) | `REVOKE INSERT ON domain_events`; a gravação passa por `app_record_event()` (SECURITY DEFINER), que deriva a autoria de `app_uid()`/`app_org()` | `test_v0160_invariants.test_history_is_never_rewritten` |
| **Contraparte reescrevendo o convite** | `rel_update` foi estendida para o alvo poder aceitar, e `counterpart_columns()` limita a contraparte a `status`, `ended_at` e `ended_reason` | `test_v0160_network` |
| **Travessia do grafo vazando terceiro** | a CTE recursiva só segue arestas cuja `visibility` alcança quem consulta; profundidade máxima 2, declarada | `test_v0160_invariants.test_b_never_sees_a_private_relationship_of_a`; `PRIVACY_VISIBILITY_MATRIX.md` |
| **Projeto privado na vitrine** | `PUBLIC_STATES = ("published",)` em **um** lugar + `listing_publish_guard()` no banco | jornada 5 de ponta a ponta, sem sessão |
| **Página pública lendo tabela privada** | a rota lê **só** `public_fields`; lista fechada de 18 campos projetáveis; `_assert_no_private()` falha na gravação | `test_v0160_network`; `profiles.NEVER_PUBLIC` |
| **Alvo de moderação anulando a própria punição** | a GRANT de coluna deixava o alvo escrever `status` (GRANT de coluna *adiciona* privilégio e não restringe) → `enforcement_target_guard()` | achado desta auditoria, corrigido |
| **Denunciante exposto ao alvo** | `target_view()` não seleciona coluna de denunciante; `reporter_anonymous` verdadeiro por padrão | teste que confere a ausência na resposta |
| **Abordagem em massa por conversa sem assunto** | conversa profissional exige contexto (proposta, projeto, anúncio ou relação) | `messaging.PROFESSIONAL` |
| **Seguir unilateral abrindo conversa** | `app_related()` passou a listar **explicitamente** os tipos que criam relação, em vez de "todos menos bloqueio" | achado por **teste de regressão da v0.8.0**, não por revisão |
| **Mudança silenciosa de preço** | `price_notice_guard()` (30 dias) + `price_apply_guard()` (aumento exige aviso) + `price_version_immutable()` | `test_v0160_billing` |
| **SQL inválido chegando a produção** | `scripts/sql_prepare_check.py` roda `PREPARE` em todo literal de SQL extraído por AST: **185 consultas, 0 erros** | achou 5 defeitos reais de nome de coluna no primeiro uso |
| **Erro de fuso gravando data errada** | `impacto/clock.py` em UTC; 28 usos de `date.today()` substituídos | `test_product_dates_are_utc` |

### Números de segurança atualizados

| Medida | v0.15.0 | v0.16.0 |
|---|---|---|
| Políticas de RLS | 408 | **466** |
| Funções `SECURITY DEFINER` | 53 | **63** — **todas** com `search_path` fixo |
| Gatilhos que o contexto privilegiado não atravessa | 5 | **15** |
| Tabelas append-only | 17 | **22** |
| Tabelas com coluna guardada | 20 | **26** |
| Tabelas sem RLS | 1 (`schema_migrations`) | **1** |

### O que esta auditoria NÃO cobre (inalterado e honesto)

Não é teste de intrusão; nunca houve um. A auditoria de dependências (`npm audit`, `pip-audit`) continua
**bloqueada neste ambiente** pelo registro de pacotes, e é obrigatória em CI antes de publicar. Stripe, SMTP,
antivírus, S3 e IdP continuam dublês. Não há classificador automático de conteúdo ilícito — a fila de moderação é
alimentada por denúncia humana (e isso é decisão, não lacuna: ver ADR-161).

## v0.15.0 — o que mudou nesta auditoria

| Item | Antes | Agora |
|---|---|---|
| Matriz de isolamento A → recurso de B | testes pontuais por recurso | **varredura automática do registro de rotas**: toda rota de escrita com identificador é chamada com identificador inexistente, e nenhuma pode responder 2xx nem 5xx. Rota nova sem conferência de dona falha sem ninguém escrever teste para ela |
| Fuga por `SECURITY DEFINER` | revisada caso a caso | teste dedicado (`test_security_definer_helpers_do_not_leak_other_tenant`) + verificação de que **as 53 funções têm `search_path` fixo** |
| Imutabilidade do arquivo | hash conferido na verificação | `document_identity_guard()` recusa alterar hash, tamanho, tipo e chave de armazenamento para **todo** papel da aplicação, privilegiado incluído |
| Máquina de estados do projeto | regra na camada HTTP | gatilho no banco que recusa transição fora do grafo até em SQL direto |
| Assinatura com provedor indisponível | checagem no código | **gatilho no banco** (`signature_provider_guard`): não existe caminho que produza assinatura ICP-Brasil simulada |
| Inventário de chaves | não existia | `encryption_keys` com impressão digital de 16 hex (a chave nunca é gravada), tabelas invisíveis para a organização, recifragem auditada |
| Expressão em modelo de documento | — | `derived_from` é **lista fechada** de 14 caminhos; teste tenta `users.password_hash` e recebe 422 |
| `except Exception` sem explicação | 10 ocorrências | **0** — todas as 35 têm comentário dizendo por quê |
| Índice em chave estrangeira de inquilino | 92 faltando | 0 faltando (migração 0015) — importa para segurança porque toda política de RLS compara `org_id = app_org()` |

**Continua RED:** nenhum teste de intrusão independente, nenhuma revisão de segurança externa, nenhum programa de
recompensa por vulnerabilidade, nenhum KMS/HSM. Ver `SECURITY_FINAL_CHECKLIST.md` §9.

---


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

## Endurecimento final — v0.12.1 (baseline técnica)
Método: varredura automatizada de autorização sobre **todas as 475 operações**, testes de IDOR de leitura e escrita, concorrência com threads, sondas de injeção/travessia/erro e revisão de contexto de sistema (RLS). **Não é pentest.**

| Achado | Gravidade | Correção / prova |
|---|---|---|
| **Vazamento de esquema nas respostas de erro**: violações de CHECK/FK/NOT NULL devolviam o texto interno do PostgreSQL (tabela, constraint; em unicidade o texto pode conter valores → enumeração/PII) | Média | Resposta genérica + `error_id`; detalhe só no log; mensagens autoradas pelos gatilhos preservadas. Teste: `ErrorHygiene.test_database_schema_details_never_reach_the_client` |
| **Contexto de sistema com JOIN bloqueado por RLS** devolvia lista vazia em `/v1/billing` (desconto reservado) | Baixa (funcional) | Leitura em contexto de sistema **restrita ao `org_id` da sessão**, sem expor código/hash; teste de isolamento entre organizações incluído |
| Toda rota não pública recusa anônimo (401) | — | GREEN — varredura de 475 operações |
| Toda rota administrativa recusa usuária comum (403 `admin_only`) e administrador **sem MFA** (403 `mfa_required`) | — | GREEN — varredura de 475 operações |
| Nenhuma rota devolve 5xx a entrada anônima/placeholder | — | GREEN — varredura |
| IDOR de **escrita** entre organizações (responder/avaliar/encerrar chamado alheio) | — | GREEN — 404 em todos os verbos; mensagem alheia não entra na thread |
| Capacidade de evento, certificado, voucher de uso único, webhook duplicado e decisão de trial sob **concorrência real** | — | GREEN — 6 testes com threads; garantias por `FOR UPDATE`/`ON CONFLICT` no banco |
| Injeção SQL/XSS em busca, chamado e checklist | — | GREEN — armazenado literalmente; nada reinterpretado; frontend não usa `innerHTML` |
| Travessia de caminho em download | — | GREEN — token HMAC curto + conferência de `storage_key` contra a linha do documento |
| Segredos no repositório | — | GREEN — varredura de padrões; a única ocorrência é o vetor de exemplo público da documentação oficial da AWS (sufixo `…EXAMPLE`), usado no teste de assinatura SigV4 em `tests/test_unit.py` |
| Segredos em log | — | GREEN — `_REDACT_KEYS` em `observability.py` oculta senha/token/segredo/cookie/código |
| Pendente | YELLOW | pentest externo; auditoria de dependências (registries bloqueados neste ambiente); privilégio amplo do modo administrativo segue como disciplina de código revisada |

**Nota de desenho (não defeito):** a URL assinada de download (`/v1/files/{token}`, 5 min) é uma *capability* — quem tiver o link acessa, como em URLs pré-assinadas de S3. O token é HMAC, expira e é conferido contra a linha do documento.

## Camada de integração (v0.13.0)
Revisão completa, vetor a vetor, com o que é **PROVADO por teste** e o que é **POR INSPEÇÃO**: `INTEGRATION_SECURITY.md`. Resumo:

| Controle | Estado |
|---|---|
| SSRF na gravação (forma) e na chamada (resolução + sem redirecionamento) | **GREEN** — testado com 169.254.169.254 |
| XXE, entidade externa e bomba XML (`defusedxml`, 8 MB, profundidade 40) | **GREEN** |
| Injeção de XML em envelope SOAP (escape + operação validada) | **GREEN** |
| Falsificação de webhook (HMAC-SHA256, comparação em tempo constante) | **GREEN** |
| Reenvio (carimbo ±300 s **+** deduplicação no banco) | **GREEN** — provado com 4 entradas simultâneas |
| Vazamento de credencial (cifrada, sem SELECT para o papel da aplicação, só dica na API, redação em log) | **GREEN** |
| IDOR / escape de organização nas 13 tabelas novas | **GREEN** |
| Escalonamento de privilégio (credencial e aprovação exigem `owner`; progresso de job/entrega é escrita privilegiada) | **GREEN** |
| Arquivo malicioso (cofre existente **não** enfraquecido; limites de XLSX) e injeção de fórmula na exportação | **GREEN** |
| Negação de serviço por sistema externo (teto de tempo, tentativas, disjuntor, trabalho fora da requisição) | **GREEN** |
| Injeção em log e travessia de caminho | **YELLOW** — por inspeção, sem teste dedicado |
| DNS rebinding (resolução e conexão são passos separados) | **YELLOW** — risco residual declarado; mitigar no egress da infraestrutura |
| Auditoria de dependências | **RED** — registries npm/PyPI bloqueados neste ambiente; obrigatória em CI |
| Pentest da camada de integração | **RED** — não executado |

## Camada de confiança (v0.14.0)
Revisão vetor a vetor, com o que é provado por teste e o que é por inspeção: `TRUST_SECURITY.md`. Resumo:

| Controle | Estado |
|---|---|
| Autopromoção de identidade e de credencial bloqueada no banco (coluna guardada) | **GREEN** |
| Assinatura em duas camadas; código de uso único amarrado ao hash; 4 usos simultâneos ⇒ 1 assinatura | **GREEN** |
| Cadeia de custódia irreescrevível pela aplicação e pelo contexto de sistema; adulteração detectada | **GREEN** |
| Integridade do arquivo recontada na verificação pública e no endpoint próprio | **GREEN** |
| Página pública sem dado pessoal (payload curado na criação, não filtrado na saída) | **GREEN** |
| Falsificação de assinatura de outra parte; hash do acordo congelado | **GREEN** |
| Supervenda de cotas, inclusive sob concorrência | **GREEN** (bug real corrigido — ver abaixo) |
| Publicação de honorário sem fonte | **GREEN** |
| IDOR entre organizações nas 26 tabelas novas | **GREEN** |
| Injeção em XML/OOXML/ODF gerado e injeção de fórmula em planilha | **GREEN** |
| Enumeração de código público (~60 bits + limite por IP) | **GREEN** |
| Injeção em log e leitura de docx/odt enviado | **YELLOW** — por inspeção, sem teste dedicado |
| Rotação da chave do servidor invalida selos antigos | **YELLOW** — **DEPENDÊNCIA DE INFRAESTRUTURA** (gerenciador de segredos + versionamento de chave) |
| Pentest da camada | **RED** — não executado |
| Auditoria de dependências | **RED** — registros npm/PyPI bloqueados; obrigatória em CI |

**Bug de segurança encontrado e corrigido:** o gatilho que impede vender mais cotas do que existem passava em silêncio,
porque `SELECT ... FOR UPDATE` aplica também a política de UPDATE da tabela travada — a cota desaparecia para quem apoia
e os `NULL` resultantes anulavam todas as comparações. Correção: função SECURITY DEFINER com checagem explícita de `NULL`.
Lição generalizada em ADR 103: **guarda de integridade não pode depender de visibilidade por RLS.**
