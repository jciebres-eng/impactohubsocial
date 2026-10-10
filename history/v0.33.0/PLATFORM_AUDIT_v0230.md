# Auditoria de segurança, auditoria, integridade e proveniência — v0.23.0

> FASE 01 dos prompts de segurança, auditoria, infraestrutura e proveniência. Medido no código e no
> banco em 2026-10-07. **Nenhuma linha aqui é declaração: cada uma tem evidência ou diz AUSENTE.**
>
> Base medida: **745 rotas**, **1.806 testes** em 87 arquivos, **50 migrações**, **313 tabelas**
> (312 com RLS; a exceção é `schema_migrations`), **653 políticas**, **41 tabelas append-only**,
> **316 chamadas reais de `ctx.audit(`**, **60 testes adversariais**.

## 0. Sobre a arquitetura que os prompts pressupõem

Um dos prompts descreve a pilha-alvo como **Supabase + Vercel + Next.js + Cloudflare R2**. Esta
plataforma **não usa nenhum desses quatro**: o backend é Python 3.13 com Starlette e um driver
libpq próprio, o banco é PostgreSQL 16 auto-hospedado com dois papéis não-superusuário, o frontend é
React compilado por esbuild e servido pela própria aplicação, e o armazenamento é abstrato
(`adapters/storage.py`) com implementação local e S3-compatível.

O mesmo prompt diz, na primeira regra: *"Não invente tecnologias sem necessidade. Não substitua
componentes que já estejam funcionando corretamente apenas por preferência."* Então a leitura
correta é aplicar os **princípios** — RLS, migrações reprodutíveis, segredos, separação de
ambientes, backup com restauração testada, observabilidade, armazenamento com URL assinada,
recuperação de desastre, rate limiting, idempotência, auditoria — à pilha que existe. Quase todos
já estão implementados; esta auditoria mede quais e aponta os que não estão.

Trocar a pilha por Supabase/Vercel significaria reescrever 745 rotas, 50 migrações e 653 políticas
de RLS que hoje funcionam e estão sob 1.806 testes. Isso não é um ganho de segurança; é um risco.

## 1. Segurança — o que JÁ está implementado

Registrado para que não seja reimplementado por engano:

| controle | evidência |
| --- | --- |
| Senha com scrypt N=2¹⁷, r=8, p=1, salt 16B; re-hash no login; trabalho equivalente para conta inexistente | `security/passwords.py:15,32-59` |
| Rotação de refresh com **detecção de reuso** que revoga a família inteira, audita e avisa a titular | `services/auth.py:290-330` |
| Cookies `HttpOnly`+`Secure`+`SameSite`, prefixos `__Secure-`/`__Host-`, refresh preso a `/v1/auth` | `services/auth.py:59-66` |
| MFA TOTP com segredo cifrado, 8 códigos de recuperação de uso único, MFA obrigatório para administração | `security/totp.py:29-52`; `config.py:64` |
| Step-up em 24 permissões, janela de 15 min | `core/access.py:46-66` |
| RLS em 312 de 313 tabelas, 653 políticas; aplicação conecta como papel **não-dono** e o processo **não sobe** em produção se isso mudar | `app.py:64-77,245-249` |
| CSP sem `unsafe-inline`/`unsafe-eval`; HSTS em produção; 6 cabeçalhos de segurança | `app.py:93-106` |
| CSRF por HMAC de sessão com `compare_digest` | `http.py:279-296` |
| CORS por allowlist explícita, sem curinga | `app.py:123-149` |
| Guarda de SSRF: só HTTPS, bloqueia IP privado/loopback/link-local, **não segue redirecionamento** | `adapters/http_client.py:28-46` |
| Upload: allowlist de extensão + **magic bytes** + recusa de PDF com JavaScript e DOCX com macro + nome aleatório + download com CSP `sandbox` | `services/documents.py:29-74`; `api/document_routes.py:215` |
| Limite de corpo por `Content-Length` **e** por leitura em fluxo | `http.py:359-410` |
| Cadeia de hash verificável em `audit_events`, `ledger_entries` e `trust_events`, com `audit_verify()`/`ledger_verify()`/`trust_verify()` | `migrations/0002_security.sql:127-163` |
| Trilha de acesso privilegiado, incluindo **leitura** e **tentativa recusada** | `migrations/0046`; `core/access.py:304-333` |
| Fail-fast de segredos em produção (ausente, curto ou com marcador impede o boot), **conferido no CI** | `config.py:210-223`; `.github/workflows/ci.yml:42` |
| 60 testes adversariais: escalada de papel, cross-tenant, limites, gaming de métrica, upload malicioso | `test_v0200_adversarial.py` (35), `test_security_tenancy.py` (25) |
| LGPD: exportação, anonimização com gatilho que permite só a limpeza prevista, consentimento com hash do texto aceito, retenção conferida contra o banco | `api/privacy_routes.py`; `migrations/0035` |

## 2. Segurança — lacunas, por gravidade

### ALTA

| # | lacuna | consequência concreta |
| --- | --- | --- |
| S1 | **Sem timeout absoluto de sessão.** Cada rotação grava `refresh_expires_at = now()+30d` sem olhar a idade da família (`services/auth.py:325`) | um refresh roubado e renovado dentro da janela sobrevive **indefinidamente** |
| S2 | **Sem idle timeout.** `sessions.last_seen_at` é escrito e nunca lido (`http.py:259`) | sessão esquecida em máquina compartilhada vale 30 dias |
| S3 | **Replay de código TOTP.** `totp.verify()` devolve o contador aceito "para impedir reuso" e **nenhum dos 4 chamadores o persiste** | o mesmo código de 6 dígitos vale ~90 s e serve mais de uma vez |
| S4 | **Nenhuma varredura de segredo** em CI, pre-commit ou teste | o fail-fast protege o boot, não o histórico do git |
| S5 | **Sem `package-lock.json`**; o CI roda `npm install` | build não reprodutível, e `npm audit` audita árvore que pode diferir da de produção |
| S6 | **`scripts/restore_test.sh` nunca é executado** — não está no CI, no Makefile nem na suíte | é o ativo de recuperação mais forte do repositório, e repete o defeito que `ops/backup.py:1` critica |
| S7 | **Nenhum alerta de segurança.** As 4 regras são de 5xx, latência, `up` e fallback de IA | `refresh_reuse_detected` — o sinal mais forte de roubo de sessão — é auditado e **ninguém da operação é avisado** |

### MÉDIA

| # | lacuna |
| --- | --- |
| S8 | Rate limit chaveado **só por IP** e em 68 de 745 rotas (9,1%): tenant atrás de NAT compartilha o limite; atacante autenticado rotando IP não é contido |
| S9 | RPO e RTO estão literalmente `_a medir_` / `_a decidir_` no runbook |
| S10 | Bloqueio de conta fixo (8 falhas → 15 min) e **`LOGIN_MAX_ATTEMPTS` é configuração morta** — nenhum leitor |
| S11 | Sem SBOM |
| S12 | **Sem kill switch global, modo manutenção ou somente-leitura** — há suspensão por organização e por usuário, nenhuma alavanca de plataforma |
| S13 | Antivírus com provedor default `none`; em produção o download de arquivo não escaneado é bloqueado, o que converte a lacuna em indisponibilidade |
| S14 | Sem detecção de novo dispositivo nem aviso de "novo acesso à sua conta" |
| S15 | `deploy.yml` tem o rollout como `echo` |

### BAIXA

S16 75 de 358 rotas de escrita sem `body=` · S17 política de senha com 12 senhas comuns, sem lista
grande · S18 `feature_flags` com `USING (true)` expõe o estado de flags · S19 sem `FORCE ROW LEVEL
SECURITY` (mitigado pelo gate de runtime) · S20 sem `cross-origin-embedder-policy`,
`cross-origin-resource-policy` e sem `report-to` na CSP · S21 traces sem exportador · S22 sem papel
de banco somente-leitura · S23 sem API keys (a feature de plano `api.access` aparece na UI sem
mecanismo) · S24 último login e histórico de segurança não exibidos à titular · S25 sem `SAVEPOINT`.

## 3. Motor de auditoria — lacunas

| # | lacuna | evidência |
| --- | --- | --- |
| A1 | `audit_events` tem 13 colunas e **faltam** `user_agent`, `session_id`, `actor_type`, `correlation_id`, `before`/`after`, `severity`, `trace_id`, `parent_event_id` | catálogo; `migrations/0001_schema.sql:924` |
| A2 | **`actor_type` não existe no repositório inteiro** — distinguir "João fez" de "o sistema fez" de "a IA propôs" é por convenção (`actor_user_id IS NULL`) | 0 ocorrências |
| A3 | `before`/`after` só em **6 payloads ad-hoc** com `{"from","to"}` | `services/workflow.py:168` e 5 outros |
| A4 | **157 de 463 handlers mutantes (34%) sem nenhuma chamada de auditoria** | contagem por varredura |
| A5 | **Redação do audit não é recursiva** (`services/audit.py:11`) — segredo em payload aninhado entra na trilha **imutável**. A dos logs é recursiva e tem outra lista | 6 chaves × 9 chaves |
| A6 | **Nenhuma exportação de auditoria** e, por consequência, nenhum evento `AUDIT_LOG_EXPORTED` | nenhuma rota |
| A7 | `GET /v1/admin/audit` filtra só por `org_id` e prefixo de ação — sem ator, objeto, IP, `request_id` nem intervalo | `admin_routes.py:539` |
| A8 | **Sem índice por recurso** (`object_type, object_id`) — timeline por entidade não escala | `ix_audit_org`, `ix_audit_action` |
| A9 | Não existe timeline de auditoria por **documento** nem por **organização** (a de projeto lê `ledger_entries`) | — |
| A10 | `request_id` vem do **header do cliente** e pode ser forjado ou colidido | `http.py:382` |
| A11 | `trace_id` existe no log e em `error_events` e **não** em `audit_events` — o elo audit↔trace está quebrado | — |
| A12 | **Sem teste de isolamento cross-tenant de `audit_events`**; a política `audit_read` nunca é exercitada contra uma segunda organização | — |
| A13 | **Sem teste de adulteração de `audit_events`** com privilégio de DBA (existe para `ledger_entries` e `trust_events`) | `test_security_tenancy.py:235` |
| A14 | `TRUNCATE` não é bloqueado por gatilho em nenhuma das 41 tabelas append-only | `tgtype=27`, sem o bit de TRUNCATE |
| A15 | Tela de auditoria descarta `payload`, `actor` e `request_id` que a API devolve | `web/src/pages/admin.tsx:363` |
| A16 | Sem prazo de retenção declarado para `audit_events` — "mantido, pseudonimizado" indefinidamente | `DATA_RETENTION_MATRIX.md:76` |

## 4. Integridade e proveniência — lacunas

| # | lacuna | gravidade |
| --- | --- | --- |
| I1 | **`indicator_values.evidence_id` é nullable e a tabela tem ZERO gatilhos** — o número que o relatório de impacto publica pode não ter origem nenhuma. A exigência de fonte protege só a *linha de base* | ALTA |
| I2 | **Nenhuma verificação de órfãos.** `scripts/db_integrity_report.py:83` declara, como string literal, que "nenhuma verificação de órfão é aplicável porque toda referência é FK declarada" — e isso é **falso** para `project_ods_targets.ods`/`target_code` (texto sem FK), `value_events.subject_type/subject_id` e `ledger_entries.ref_type/ref_id` (ponteiros polimórficos) | ALTA |
| I3 | **Nenhum caminho de correção no ledger.** 61 tipos de lançamento e nenhum de estorno/reversão. Append-only + hash sem estorno = valor errado fica errado para sempre | ALTA |
| I4 | **27 gatilhos valem só para o papel `impacto_app`** (`current_user` no corpo) — inclusive imutabilidade de identidade de arquivo, anti-auto-revisão e estado inicial forçado | MÉDIA |
| I5 | **Duas máquinas de estado sem gatilho**: `applications` (`services/workflow.py:14`) e `kb_articles` — e `applications` é a entidade que move dinheiro | MÉDIA |
| I6 | **`value_events` sem `seq`/`prev_hash`/`entry_hash`** — append-only por gatilho, mas sem cadeia: remoção não deixa lacuna detectável | MÉDIA |
| I7 | **Sem proveniência do número do indicador de projeto.** Existe para território (`territory_indicator_current`) e para a cadeia causal (`result_chain`), não para `indicator_values.value` | MÉDIA |
| I8 | `project_snapshots` tem checkpoint com hash e `ledger_seq` e **nenhum restore** o consome | MÉDIA |
| I9 | `dataset_id` nullable nas 4 tabelas que o referenciam | BAIXA |
| I10 | `evidences.document_id` nullable e sem hash próprio | BAIXA |
| I11 | Sem UNIQUE que impeça dois documentos apontando o mesmo `supersedes_id` | BAIXA |

## 5. Ordem de execução desta rodada

A ordem é a do §85 do próprio prompt de segurança — **segurança, integridade de dado, controle de
acesso, integridade financeira, privacidade, disponibilidade, observabilidade, performance, UX**:

1. S1, S2, S3 (sessão e TOTP) · S4, S5, S6 (cadeia de suprimentos e restauração) · S7 (alertas)
2. S12 (kill switch) — é o que permite responder a um incidente em curso
3. I1, I2, I3, I5, I6 (integridade de dado)
4. A1–A5, A6, A8, A12, A13, A14 (auditoria)
5. IA: ver `AI_AUDIT.md` §2
6. I7 (proveniência do número)
7. UI: centro de segurança, uso de IA, timeline, proveniência
