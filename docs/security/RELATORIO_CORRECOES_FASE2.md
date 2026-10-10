# Correções de segurança e integridade financeira — Fase 2 (v0.35.0)

**Pacote seguido:** IMPACTO MASTER Security & Financial Integrity 1.0.0. **Fase 1:** auditoria somente leitura
(`docs/security/AUDITORIA_SEGURANCA_FASE1.md`). **Fase 2:** correções autorizadas pelo responsável em 10/10/2026 —
"Sim, lotes A a I" — numa branch própria (`seguranca-v0350`), um commit por lote, **nada publicado**. Das ações extras
oferecidas, o responsável autorizou **só** a nova cifra do backup; **não** autorizou: recusar a produção sem antivírus,
o teste de IP no demo e o diagnóstico do banco de produção — esses itens continuam abertos e estão marcados abaixo.

> Este documento **não** é certificação, pentest nem parecer jurídico. "Corrigido" quer dizer: há implementação e um teste
> que **falhava no código anterior e passa agora**, no escopo testado — não quer dizer "impossível de invadir".

---

## 0. Em linguagem simples

**O que mudou:** as três falhas provadas na fase 1 estão fechadas (o financiador não vê mais documentos internos da OSC; só
a dona autoriza cobrança; a conciliação passou a comparar com fonte independente). Também foram fechadas outras falhas
achadas no caminho — entre elas duas que a fase 2 **provou** no código anterior: (1) um evento de pagamento **sem
assinatura** enviado antes do verdadeiro fazia o verdadeiro ser ignorado e a doação nunca confirmar; (2) uma tabela
temporária criada pela conexão da aplicação fazia o banco responder que qualquer pessoa tinha identidade "biométrica".

**Como foi provado:** 84 testes novos (`backend/tests/test_v0350_security.py`). Para cada lote, os testes novos foram
rodados no código **anterior** e falharam (saídas em `docs/security/evidencias/`); depois da correção passam.
A regressão completa está no fim deste relatório (§7).

**O que continua dependendo de você** (nada disso o código resolve): trocar o token do backup exposto ("C2"), tornar o
repositório privado, proteger a `main`, ligar os alertas do Dependabot, configurar as variáveis novas no Railway antes de
publicar e publicar a cadeia de PRs. Lista completa no §6.

**Semáforo desta fase:** 🟡 **AMARELO** — código corrigido e provado localmente; produção ainda na v0.30.0, com pendências
P0 que só você executa. Decisão de publicar (GO/NO-GO) é humana.

---

## 1. Como foi feito

| Lote | Commit | Tema | Testes novos | No código anterior |
|---|---|---|---|---|
| A | `2b44b58` | documentos da diligência, papel mínimo nas rotas comerciais, nome civil na página pública | 7 | 5 falham (2 são guardas) |
| B | `82ed19e` | conciliação com fonte declarada, confirmação só pelo caminho normal, origem do recurso, verificação do beneficiário | 13 | falham na preparação + sonda confirma as 3 falhas |
| C | `4f8bcf6` | identidade e sessões da equipe | 13 | 13 falham |
| D | `a8ba87e` | webhook com carimbo de tempo, chave PIX de repasse | 10 | 10 falham |
| E | `b587bf3` | banco (search_path, EXECUTE, visão, TRUNCATE) | 6 | 5 falham (1 guarda) |
| F | `54e06dd` | PDF pela estrutura, antivírus fora do ar, arquivos pessoais na exclusão de conta | 7 | 6 falham (1 guarda) |
| G | `2e41dd9` | erros 4xx, readyz, SSRF, logs, política da IA | 8 | 8 falham |
| H | `3eecfea` | antifraude e identidade | 10 | 10 falham |
| I | `14b758b` | cadeia de entrega, cifra do backup, runbooks | 10 | 10 falham |

Regras seguidas: nenhum teste antigo foi enfraquecido ou apagado. Testes antigos que **codificavam o comportamento
inseguro** foram atualizados com o motivo escrito ao lado (ex.: helpers de teste passam a ativar o MFA como o produto, com o
código do e-mail; a assinatura do webhook passou a ter carimbo de tempo; o bloqueio de organização passou a ter duas
etapas). Dados sintéticos, banco descartável; nenhuma ação contra a produção.

---

## 2. Controle por controle

Estado depois da fase 2: **CORRIGIDO** (implementado + teste que falhava antes) · **PARCIAL** (parte feita; o resto dito) ·
**ABERTO** (não feito nesta fase, com o motivo) · **NÃO VERIFICÁVEL** (depende de ambiente que não foi acessado).

### 2.1 Autorização e documentos

| ID | Antes (fase 1) | Depois | O que mudou | Prova |
|---|---|---|---|---|
| FILE-07 | falha provada | **CORRIGIDO** | diligência vê só tipos institucionais (lista fechada) ou `parties`; nunca exportação, documento de dirigente ou de identidade; acesso termina com a candidatura (`app_document_access`, 0074) | `DiligenceSeesOnlyInstitutionalDocumentsTests` (4) |
| AUTHZ-02 | falha | **CORRIGIDO** | `min_role="owner"` nas 3 rotas comerciais + varredura: toda rota de escrita da organização declara papel mínimo | `CommercialActsNeedTheOwnerTests` (2) |
| ID-01 | falha | **CORRIGIDO** | apoiador pessoa física aparece mascarado até optar por mostrar o nome | `PublicBackersNeverShowACivilNameWithoutOptInTests` |
| AUTHZ-06 | PARCIAL | **CORRIGIDO** nos fluxos de dinheiro e risco / **PARCIAL** na identidade | quatro olhos: confirmação do beneficiário, aprovação de extrato manual, obrigações de remuneração (liquidar/estornar/decidir/dispensar), recurso de caso de risco, restrição de organização. Identidade: decisor ≠ titular (banco confere), mas ainda uma pessoa decide | testes dos lotes B, C e H |

### 2.2 Autenticação e sessões

| ID | Antes | Depois | O que mudou | Prova |
|---|---|---|---|---|
| AUTH-05 | 103 rotas sem step-up | **CORRIGIDO** nas 69 rotas da administração / **PARCIAL** nas 35 editoriais | escrita administrativa sem permissão nomeada (69 rotas — 68 que existiam e a nova de estado da identidade: status de usuário, decisões de identidade, moderação…) exige identidade confirmada há < 15 min; `compliance.write` entrou no step-up; chave PIX de repasse também. As 35 rotas editoriais da equipe (base de conhecimento, revisão de conteúdo — `staff=`) seguem sem step-up, por decisão: não mexem em dinheiro, identidade nem permissão | `StaffWriteRoutesNeedFreshIdentityTests`, `PixKeyIsProtectedTests` |
| AUTH-02 | PARCIAL | **PARCIAL** | código errado do segundo fator conta no bloqueio da conta (8 falhas/15 min); IP do cliente pela ponta confiável do X-Forwarded-For (`TRUSTED_PROXY_HOPS`/`CLIENT_IP_HEADER`) — **falta você ligar `TRUST_PROXY_HEADERS=true` e conferir o número de saltos no demo** (§6) | `SecondFactorBruteForceAndTrailTests`, `ClientIpComesFromTheTrustedEndTests` |
| AUTH-03 | PARCIAL | **CORRIGIDO** | produção/staging recusam `REQUIRE_MFA_FOR_ADMINS=false`; a equipe não desativa o próprio MFA | `ProductionRefusesStaffWithoutSecondFactorTests`, `StaffSecondFactorTests` |
| AUTH-04 | PARCIAL | **CORRIGIDO** | equipe ativa o MFA com o código do aplicativo **e** um código enviado ao e-mail; `create-admin` recusa e-mail existente (promoção só com `--promote-existing`, que troca a senha, zera o MFA e encerra sessões) | `StaffSecondFactorTests`, `CreateAdminNeverSilentlyPromotesTests` |
| AUTH-09 | AUSENTE | **CORRIGIDO** | e-mail de aviso ao titular em troca/redefinição de senha e ligar/desligar MFA | `SecondFactorBruteForceAndTrailTests` |
| AUTH-11 | PARCIAL | **CORRIGIDO** | trilha de `auth.mfa_failed` e `auth.step_up_failed` (eventos de segurança) | idem |
| AUTH-07 (CSRF sem Origin em rota anônima), AUTH-08 (envio síncrono), AUTH-10 (OIDC), AUTH-12 | P2–P3 | **ABERTO** | fora do escopo dos lotes A–I | — |

### 2.3 Pagamentos, doações e integridade financeira

| ID | Antes | Depois | O que mudou | Prova |
|---|---|---|---|---|
| PAY-01 | PARCIAL | **CORRIGIDO** (código) | assinatura `t=…,v1=HMAC(t.corpo)` com janela de 300 s nos dois webhooks; segredo próprio do webhook de doações (`DONATION_WEBHOOK_SECRET`); segredo curto (< 32) ou igual entre endpoints não serve; sem segredo de reserva fixo; **sandbox nunca em produção** (`PAYMENT_SANDBOX_ENABLED`) | `WebhookSignatureHasATimeWindowTests` (7) |
| **PAY-13 (novo)** | — | **CORRIGIDO** | evento sem assinatura válida ocupava o `event_id`; o verdadeiro chegava como "duplicado" e a doação nunca confirmava (**provado no código anterior**). Agora o não assinado fica guardado sob identificador próprio — nos dois webhooks | `test_an_unsigned_event_cannot_squat_the_event_id`, `test_an_unsigned_billing_event_does_not_squat_either` + sonda |
| PAY-02 | PARCIAL | **CORRIGIDO** | mesma chave de idempotência com outro valor → 409; corrida de criação não vira 500 | `ConfirmationAndLedgerIntegrityTests` |
| PAY-03 / PAY-12 | PARCIAL | **CORRIGIDO** | evento antes da confirmação fica `deferred` e é reaplicado; evento que falha para depois de 10 tentativas (fila de exceções); JSON do webhook com profundidade limitada | idem + `MalformedRequestsAreClientErrorsTests` |
| PAY-05 | PARCIAL | **CORRIGIDO** | "permitir" após revisão confirma pelo caminho normal (razão, obrigações, comprovante); confirmação sem valor não confirma; liquidação acima do esperado vira exceção | idem |
| PAY-07 | AUSENTE (provado) | **CORRIGIDO** | cada execução registra a fonte; provedor real exige extrato; extrato manual concilia só após aprovação de OUTRA pessoa (snapshot com hash conferido) | `ReconciliationProvesSomethingTests` + sonda |
| PAY-08 | falha (provado) | **CORRIGIDO** | a origem pública da campanha prevalece; contribuição à plataforma nunca em recurso público/misto | `PublicMoneyStaysPublicTests` + sonda |
| PAY-09 | PARCIAL | **CORRIGIDO** (cifra da chave: ABERTO) | identidade confirmada; aviso a todas as partes (plataforma + e-mail das donas); trava depois da primeira assinatura (serviço + gatilho no banco); carência de 24 h para chave informada depois de assinatura. **Cifra da chave em repouso não feita** (SEC-02) | `PixKeyIsProtectedTests` (3) |
| PAY-10 | PARCIAL | **CORRIGIDO** | obrigações de remuneração: quem registrou o recebimento não liquida, não estorna, não decide | `RemunerationFourEyesTests` |
| KYC-03 | falha (provado) | **CORRIGIDO** | vale a decisão mais recente; "verificado" exige titularidade e confirmação por segunda pessoa; recusa posterior tira campanhas do ar | `BeneficiaryVerificationIsRevocableAndFourEyesTests` + sonda |
| PAY-06 (índice), PAY-11 (rótulos da tela) | P2–P3 | **ABERTO** | — | — |

### 2.4 Banco de dados

| ID | Antes | Depois | O que mudou | Prova |
|---|---|---|---|---|
| DB-03 | PARCIAL | **CORRIGIDO** | toda função SECURITY DEFINER termina o `search_path` em `pg_temp` (laço no catálogo; preserva `extensions` do Supabase). Provado antes: tabela temporária fazia `identity_level()` devolver 'biometric' | `DatabaseCatalogHardeningTests` |
| DB-05 | PARCIAL / NÃO VERIFICÁVEL | **CORRIGIDO** (código) / **NÃO VERIFICÁVEL** (produção) | EXECUTE revogado de PUBLIC em toda função do esquema e concedido a `impacto_app`; no Supabase, `anon`/`authenticated` perdem o uso do esquema. Só vale na produção depois de publicar a 0074 — e conferir exige o diagnóstico que não foi autorizado | idem |
| DB-04 | PARCIAL | **CORRIGIDO** | `project_baselines_without_source` com `security_invoker`; `ai_prompt_public` mantida de propósito (projeção sem o texto de sistema) | idem |
| DB-06 | PARCIAL | **CORRIGIDO** | teste global de concessões | idem (já passava: fica como guarda) |
| DB-07 | COMPROVADO (parcial) | **CORRIGIDO** | toda tabela só-inclusão recusa TRUNCATE (20+ não recusavam) | idem |
| DB-02 | NÃO VERIFICÁVEL (produção) | **NÃO VERIFICÁVEL** | diagnóstico da produção não autorizado nesta fase | — |

### 2.5 Arquivos, web e IA

| ID | Antes | Depois | O que mudou | Prova |
|---|---|---|---|---|
| FILE-02 | PARCIAL | **CORRIGIDO** | conteúdo ativo de PDF conferido pelos nomes decodificados e dentro de fluxos de objetos comprimidos (teto contra bomba). Cabeçalhos extras na URL assinada do R2: **ABERTO** (download já vem como anexo; não verificável aqui) | `PdfActiveContentIsFoundByStructureTests` |
| FILE-03 | PARCIAL | **PARCIAL** | antivírus fora do ar → arquivo em quarentena (não mais erro 500) e a fila de varredura não para; teste do 409 `pending_scan`. **Não feito por decisão sua:** recusar a produção sem antivírus. Conferir as variáveis do antivírus na produção: NÃO VERIFICÁVEL | `AntivirusOutageQuarantinesInsteadOfFailingTests` |
| FILE-09 | PARCIAL / AUSENTE | **PARCIAL** | excluir a conta apaga os arquivos pessoais (identidade, dirigente, exportações); documentos institucionais ficam — prazo por tipo de documento é pergunta ao jurídico/DPO | `AccountDeletionRemovesPersonalFilesTests` |
| WEB-06 | PARCIAL | **CORRIGIDO** | JSON profundo e Content-Length inválido → 400; 409 sem nome de restrição; `/readyz` público resumido em produção | `MalformedRequestsAreClientErrorsTests` |
| WEB-05 | COMPROVADO (residual) | **CORRIGIDO** (código) | destino precisa ser endereço global (bloqueia 100.64.0.0/10 e IPv4 embutido em IPv6). Demo em `development` ainda aceita loopback: ABERTO (configuração) | `OutboundRequestsOnlyReachThePublicInternetTests` |
| WEB-07 | PARCIAL | **CORRIGIDO** | redação por pedaço do nome da chave e por padrão do valor (e-mail mascarado, CPF), inclusive em exceções | `LogsDoNotCarrySecretsOrPersonalDataTests` |
| AI-02 | PARCIAL | **CORRIGIDO** | faixa que exige esquema não chama o provedor externo sem esquema; resumo marca revisão humana | `AiPolicyIsEnforcedAndWhatLeavesIsRedactedTests` |
| AI-03 | PARCIAL | **PARCIAL** | teste do que de fato sai para o provedor (identificadores redigidos — já eram); **nomes e endereços continuam saindo** | idem |
| FILE-04, FILE-08, WEB-01..04, AI-01, PRIV-02 | P2–P3 | **ABERTO** | — | — |

### 2.6 Antifraude e identidade

| ID | Antes | Depois | O que mudou | Prova |
|---|---|---|---|---|
| FRAUD-02 | PARCIAL | **CORRIGIDO** | limiares lidos de `config/donation_risk_rules.json` (versão 2026-10.2), que passou a ser a fonte | `RiskRulesComeFromTheFileTests` |
| FRAUD-03 | AUSENTE | **PARCIAL** | fracionamento (só alcança quem doa com conta); chave PIX repetida entre organizações; destino de repasse mudado há < 7 dias. Padrão de estorno: ABERTO | idem + `NewReviewSignalsTests` |
| FRAUD-04 | COMPROVADO (sem 4 olhos) | **CORRIGIDO** | restrição de organização: uma pessoa propõe, outra confirma em até 72 h | `OrganizationBlockNeedsTwoPeopleTests` |
| FRAUD-05 | PARCIAL | **CORRIGIDO** | caso com revisor atribuído, evidências, recurso da organização decidido por outra pessoa, encerramento | `RiskCaseLifecycleTests` |
| KYC-01 | PARCIAL | **CORRIGIDO** | sem autodecisão; decisão não é reescrita; suspensa/revogada/vencida | `IdentityVerificationStatesTests` |
| FRAUD-01 (versão das regras de organização), FRAUD-06 (teste de atributos protegidos) | P3 | **ABERTO** | — | — |
| KYC-02, KYC-04, KYC-05 | AUSENTE | **ABERTO** | exigem contrato com provedor de KYC/KYB e parecer jurídico (poderes de representação, beneficiário final) | — |

### 2.7 Cadeia de entrega, continuidade e incidentes

| ID | Antes | Depois | O que mudou | Prova |
|---|---|---|---|---|
| SDLC-05 | AUSENTE | **PARCIAL** | 25 referências de actions fixadas por SHA (resolvidos por `git ls-remote` em 10/10/2026). **Imagens por digest: não feito** — o Docker Hub é inacessível neste ambiente e fixar sem conferir seria inventar; o CI registra o digest de cada build e o Dependabot propõe atualizações | `SupplyChainTests` |
| SDLC-06 | PARCIAL | **CORRIGIDO** | gitleaks também no push; `.gitignore` amplo | idem |
| SDLC-07 | PARCIAL | **PARCIAL** | `npm audit` completo (informativo); Dependabot configurado. **Hashes Python: não feito**; **alertas do Dependabot: você liga** | idem |
| SDLC-08 | PARCIAL / AUSENTE | **CORRIGIDO** (informativo) | SBOM CycloneDX + varredura HIGH/CRITICAL da imagem (Trivy 0.74.0, binário conferido) — não bloqueia nesta versão; a primeira execução mede a linha de base | idem |
| BCP-01 | PARCIAL | **CORRIGIDO** (código) / ensaio na produção **pendente** | cifra AUTENTICADA (`scripts/backup_crypt.py`, `.dump.aead`); SHA-256 também fora do bucket; CI cifra/decifra/compara e exige recusa do adulterado. O ensaio real depende do merge e de você disparar o workflow (§6) | `BackupCipherIsAuthenticatedTests` |
| IR-01 / BCP-05 (links) | PARCIAL / AUSENTE | **CORRIGIDO** (documento) | 7 runbooks em `docs/security/runbooks/`; os 9 alertas apontam para arquivos que existem. Ativar a coleta de alertas na produção: ABERTO (você) | `IncidentRunbooksTests` |
| SDLC-01..04, SEC-01, BCP-02..04 | — | **ABERTO — só você** | ver §6 | — |
| SEC-02 (cifra da chave PIX) | PARCIAL | **ABERTO** | a chave PIX é dado para ser mostrado a quem paga; cifrar em repouso fica para versão futura | — |

---

## 3. Achados novos desta fase

1. **PAY-13 — ocupação do identificador do evento.** Quem conhecesse (ou adivinhasse) o `event_id` de um evento futuro do
   provedor podia enviá-lo antes, sem assinatura; o verdadeiro chegava depois como "duplicado" e não era aplicado.
   Provado no código anterior (`evidencias/probe_pay01_saida_4f8bcf6.txt`: doação ficou `awaiting_payment`). Corrigido.
2. **DB-03 concreto.** A fase 1 apontou o risco; a fase 2 provou: a conexão da aplicação (com privilégio de tabela temporária)
   criava `identity_verifications` temporária e `identity_level()` (SECURITY DEFINER) a lia no lugar da real. Exige executar
   SQL como `impacto_app` (por exemplo, por injeção de SQL — hoje mitigada por consultas parametrizadas), por isso é
   defesa em profundidade. Corrigido para todas as funções.
3. **Teste que vazava estado.** O teste de quatro olhos da remuneração deixava uma obrigação liquidada que somava na receita
   conferida por outro módulo; passou a desfazer a própria transação.

---

## 4. O que não foi feito e por quê

| Item | Motivo |
|---|---|
| Produção recusar subir sem antivírus (FILE-03) | **decisão do responsável** nesta fase |
| Teste de IP no demo; diagnóstico do banco de produção | **não autorizados** nesta fase |
| Imagens por digest (SDLC-05) | Docker Hub inacessível neste ambiente; nenhum digest é escrito sem ter sido conferido |
| Hashes de pacotes Python (SDLC-07) | exige resolver a árvore inteira para a plataforma da imagem; risco de quebrar o build sem como conferir aqui |
| Cifra da chave PIX em repouso (SEC-02) | baixo ganho frente a RLS + trava + carência; versão futura |
| KYC/KYB por provedor, poderes de representação, beneficiário final | dependem de contrato e de parecer jurídico |
| Itens P3 da fase 1 (CSRF sem Origin em rota anônima, OIDC, índices, rótulos, testes extras) | fora do escopo autorizado (lotes A–I) |

---

## 5. Riscos residuais (honestos)

- **IP do cliente na produção:** sem `TRUST_PROXY_HEADERS=true` e o número certo de saltos, os limites por IP continuam
  contornáveis por cabeçalho forjado (a correção está no código, desligada até você configurar).
- **Antivírus:** se a produção estiver com `ANTIVIRUS_PROVIDER=none` ou `ALLOW_UNSCANNED_DOWNLOADS=true`, arquivos não são
  varridos — NÃO VERIFICÁVEL daqui.
- **Arquivos do R2 sem cópia** (BCP-03): arquivo apagado não volta.
- **Fracionamento por doador anônimo** não é detectável sem identificar a pessoa (escolha de privacidade).
- **Nomes e endereços** podem sair para um provedor de IA externo (hoje nenhum está ligado).
- **Imagens de base por tag**: uma tag reapontada no Docker Hub muda a imagem construída (o CI registra o digest usado).
- **SBOM e varredura de imagem não bloqueiam** nesta versão.
- Nenhum teste de intrusão externo foi feito. Nada aqui é certificação.

---

## 6. O que só você pode fazer (em ordem)

| Prioridade | Ação | Onde |
|---|---|---|
| **P0** | Trocar o token do R2 do backup exposto ("C2") e atualizar os segredos `R2_BACKUP_*` | Cloudflare → R2 → Manage API tokens; GitHub → Secrets ([RB-01](runbooks/RB-01-vazamento-de-segredo.md)) |
| **P0** | Tornar o repositório privado (decisão de 09/10 ainda não aplicada) | GitHub → Settings → General → Danger Zone |
| **P0** | Antes de publicar a v0.35.0 na produção: seguir o checklist `PUBLICATION_CHECKLIST_v0350.md` (variáveis novas) | Railway |
| P1 | Proteger a `main` (PR obrigatório, CI obrigatório) e criar o environment `production` com revisor | GitHub → Settings → Branches / Environments |
| P1 | Ligar os alertas do Dependabot | GitHub → Settings → Code security |
| P1 | Publicar a cadeia de PRs (#5 → #6 → #7 → #8) e testar no demo antes da produção | GitHub; Railway (demo publica sozinho) |
| P1 | Depois do merge: rodar `backup-supabase` no modo `backup` e depois `ensaio-restauracao` (primeiro backup no formato novo) | GitHub → Actions |
| P1 | Monitor externo com dois contatos; ativar coleta de alertas | UptimeRobot/Better Stack; Prometheus/Grafana |
| P1 | Versionamento ou replicação do bucket de arquivos | Cloudflare → R2 |
| P2 | Perguntas ao jurídico/DPO: prazos de guarda por tipo de documento; comunicação de incidente; KYC/KYB | — |

---

## 7. Regressão

Ver `FINAL_EXECUTION_REPORT.md` (seção da v0.35.0) e o log em `docs/evidence/`.
