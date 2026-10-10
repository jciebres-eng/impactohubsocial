# Auditoria final de execução — IMPACTO v0.35.0

**Data:** 10/10/2026 · **Ramo:** `seguranca-v0350` (PR #8) · **Ponto de partida:** `16d837b` (v0.34.0, ramo `ecossistema-v0340`) · **Versão:** 0.35.0

Estados: **PASS** (feito e provado por execução nesta rodada — o teste novo falhou no código anterior e passa agora) · **PARTIAL**
(feito em parte; o que falta está escrito) · **BLOCKED_EXTERNAL** (depende de contrato, parecer, painel ou decisão/autorização do
responsável; nada simulado) · **FAIL** (falhou e não foi corrigido — não há nenhum; os que apareceram estão em §7). Nada aqui afirma
invulnerabilidade; isto não é certificação nem teste de intrusão.

## 1. O pedido → o que virou software e prova

Pedido (IMPACTO MASTER Security & Financial Integrity 1.0.0): fase 1 somente leitura; fase 2 com autorização. Autorizado em
10/10/2026: lotes A a I na branch `seguranca-v0350`, sem publicar; das ações extras, só a nova cifra do backup. Não autorizados:
recusar a produção sem antivírus, teste de IP no demo, diagnóstico do banco de produção.

| Item | Estado | Evidência (arquivo · teste) | Resultado | Risco | Ação restante |
|---|---|---|---|---|---|
| FILE-07 diligência vê só documentos institucionais | PASS | `0074` (`app_document_access`) · `DiligenceSeesOnlyInstitutionalDocumentsTests` · `evidencias/loteA_antes_16d837b.txt` | dirigente, identidade e exportação fora; acesso termina com a candidatura | — | — |
| AUTHZ-02 atos comerciais só pela dona | PASS | `CommercialActsNeedTheOwnerTests` (varredura de toda rota de escrita) | `min_role="owner"` | — | — |
| ID-01 nome civil do apoiador | PASS | `PublicBackersNeverShowACivilNameWithoutOptInTests` | mascarado até optar | — | — |
| PAY-07 conciliação com fonte e quatro olhos | PASS | `ReconciliationProvesSomethingTests` · `evidencias/probe_loteB_saida_2b44b58.txt` | provedor real exige extrato; manual só com aprovação de outra pessoa | — | — |
| PAY-08 origem pública prevalece | PASS | `PublicMoneyStaysPublicTests` + sonda | doador não muda público para privado | — | — |
| KYC-03 verificação do beneficiário revogável e com segunda pessoa | PASS | `BeneficiaryVerificationIsRevocableAndFourEyesTests` + sonda | recusa posterior tira campanhas do ar | verificação antiga sem confirmação bloqueia publicação | confirmar no demo |
| AUTH-05 identidade confirmada na escrita administrativa | PASS | `StaffWriteRoutesNeedFreshIdentityTests` | 69 rotas (+ `compliance.write`, chave PIX) | 35 rotas editoriais sem step-up, por decisão | — |
| AUTH-03/04/09/11 MFA da equipe, avisos, trilha | PASS | `StaffSecondFactorTests`, `ProductionRefusesStaffWithoutSecondFactorTests`, `SecondFactorBruteForceAndTrailTests`, `CreateAdminNeverSilentlyPromotesTests` | produção recusa MFA desligado; ativação com app + e-mail | — | — |
| AUTH-02 IP do cliente pela ponta confiável | PARTIAL | `ClientIpComesFromTheTrustedEndTests` | código pronto, desligado | limites por IP contornáveis até configurar | `TRUST_PROXY_HEADERS` + conferir saltos no demo |
| PAY-01 webhook com carimbo de tempo e segredos próprios | PASS | `WebhookSignatureHasATimeWindowTests` (7) | janela de 300 s; segredo ≥ 32; sandbox recusado em produção | — | variáveis no Railway |
| PAY-13 ocupação do `event_id` por evento não assinado | PASS | `test_an_unsigned_event_cannot_squat_the_event_id` · `evidencias/probe_pay01_saida_4f8bcf6.txt` | não assinado guardado sob identificador próprio | — | — |
| PAY-02/03/05/12 idempotência, adiados, permitir pelo caminho normal | PASS | `ConfirmationAndLedgerIntegrityTests`, `MalformedRequestsAreClientErrorsTests` | 409 com outro valor; adiado reaplicado; desiste após 10 | — | — |
| PAY-09 chave PIX de repasse | PASS | `PixKeyIsProtectedTests` (3) · gatilho `trg_party_pix_lock` | trava após assinatura; carência 24 h; avisos | cifra em repouso não feita (SEC-02) | versão futura |
| PAY-10 quatro olhos na remuneração | PASS | `RemunerationFourEyesTests` | quem registrou não liquida/estorna/decide | — | — |
| DB-03/04/05/06/07 catálogo do banco | PASS | `DatabaseCatalogHardeningTests` · `evidencias/loteE_antes_a8ba87e.txt` | `pg_temp` no fim do `search_path`; EXECUTE só `impacto_app`; TRUNCATE travado | vale na produção só depois da 0074 | publicar; diagnóstico (não autorizado) |
| DB-02 / DB-05 na produção | BLOCKED_EXTERNAL | diagnóstico `supabase verificar` não autorizado nesta fase | NÃO VERIFICÁVEL | — | autorização do responsável |
| FILE-02 PDF pela estrutura | PASS | `PdfActiveContentIsFoundByStructureTests` | nomes decodificados e fluxos de objetos | — | — |
| FILE-03 antivírus fora do ar | PARTIAL | `AntivirusOutageQuarantinesInsteadOfFailingTests` | quarentena em vez de 500 | produção sem antivírus aceita (decisão do responsável) | conferir variáveis |
| FILE-09 exclusão de conta | PARTIAL | `AccountDeletionRemovesPersonalFilesTests` | arquivos pessoais apagados | prazos por tipo de documento | jurídico/DPO |
| WEB-05/06/07 SSRF, erros 4xx, logs | PASS | `OutboundRequestsOnlyReachThePublicInternetTests`, `MalformedRequestsAreClientErrorsTests`, `LogsDoNotCarrySecretsOrPersonalDataTests` | endereço global; 400/409 sem detalhe interno; redação | demo aceita loopback (configuração) | — |
| AI-02 / AI-03 política da IA | PARTIAL | `AiPolicyIsEnforcedAndWhatLeavesIsRedactedTests` | esquema exigido; revisão humana marcada | nomes e endereços podem sair (nenhum provedor ligado) | — |
| FRAUD-02/04/05, KYC-01 | PASS | `RiskRulesComeFromTheFileTests`, `OrganizationBlockNeedsTwoPeopleTests`, `RiskCaseLifecycleTests`, `IdentityVerificationStatesTests` | regras do arquivo; bloqueio propõe/confirma; caso com recurso; estados | — | — |
| FRAUD-03 novos sinais | PARTIAL | `NewReviewSignalsTests` | fracionamento, PIX repetida, destino mudado | padrão de estorno aberto; anônimo não detectável | — |
| SDLC-05/06/07/08 cadeia de entrega | PARTIAL | `SupplyChainTests` | actions por SHA; gitleaks no push; SBOM e Trivy informativos; Dependabot | imagens por tag; sem hashes Python | alertas do Dependabot (responsável) |
| BCP-01 cifra autenticada do backup | PASS | `scripts/backup_crypt.py` · `BackupCipherIsAuthenticatedTests` | AES-256-GCM em blocos; adulterado/truncado recusado | ensaio real pendente | backup + `ensaio-restauracao` após o merge |
| IR-01 runbooks e alertas | PASS | `docs/security/runbooks/` · `IncidentRunbooksTests` | 7 runbooks; 9 alertas com link existente | coleta de alertas na produção | responsável |
| Acessibilidade das telas novas (achado do CI) | PASS | `test_e2e_v0350_admin_screens` · `evidencias/a11y_admin_identidade_antes_fd1c86c.txt` | seletor com nome acessível | — | axe no CI do commit final |
| KYC-02/04/05 provedor, poderes, beneficiário final | BLOCKED_EXTERNAL | — (contrato e parecer) | não simulado | — | contrato + jurídico |

## 2. Motores

Inalterados (50; VERDE 37 · AMARELO 13 · VERMELHO 0).

## 3. Perfis, rotas e jornadas

994 operações (+6: 4 da equipe, 2 da organização), 235 telas (inalteradas; 2 com conteúdo novo), 267 rotas de plataforma (+4),
122 permissões nomeadas (+3). Jornadas: 16, 274 passos na ordem da suíte (+5 na pilha do zero: confirmação de identidade antes da
chave PIX e confirmação do beneficiário por segunda pessoa), 0 falha.

## 4. Banco de dados

Migração `0074_v0350_security.sql`: acesso a documentos (`app_document_access`); verificação do beneficiário com segunda pessoa e
decisão mais recente; fonte da conciliação e aprovação de extrato; trava e carência da chave PIX (`trg_party_pix_lock`);
`search_path` com `pg_temp` em toda função SECURITY DEFINER (preservando `extensions` do Supabase); EXECUTE revogado de PUBLIC;
`security_invoker` na visão `project_baselines_without_source`; gatilho de TRUNCATE em toda tabela só-inclusão; sinais de risco
novos; bloqueio de organização em duas etapas (`risk_block_four_eyes`); ciclo do caso de risco; estado `suspended` e
`identity_decider_is_not_the_subject`. Aplicada em banco novo (74 migrações) e pelo caminho de atualização, inclusive no desenho do
Supabase (administrador sem superusuário). Só acrescenta.

## 5. Segurança e LGPD

Controle por controle em `docs/security/RELATORIO_CORRECOES_FASE2.md`; riscos residuais no §5 de lá. `secrets_scan.py` limpo.

## 6. CI

O CI completo roda no pull request (job a job; o log do job não é legível pela API neste ambiente — só as anotações).

| Execução | Commit | Resultado |
|---|---|---|
| PR #8, `38070321577` | `e9a892d` | auditoria, armazenamento, docker e segredos verdes; **backend vermelho** com as mesmas 9 falhas e 1 erro da regressão local (2570 testes; §7); **pilha-do-zero vermelho**: axe-core `select-name` em `/admin/identidade` |
| PR #8, `38071340835` | `fd1c86c` | auditoria, armazenamento, docker e segredos verdes; **backend**: 2570 testes, **0 erros** (a correção de `test_v0170_payments` confirmada no CI) e as 9 falhas de fechamento (documentos ainda não regenerados nesse commit); **pilha-do-zero vermelho** pela mesma tela |
| PR #8, commit da correção e dos documentos de fechamento | seguinte a `fd1c86c` | registrado no PR #8 e no relatório entregue ao responsável |

Reprodução local da pilha (sem Docker, com o MESMO roteiro): 16 jornadas, 280 passos, 0 falha; 235 rotas de tela, 857 visitas, 235
abertas com dado real; persistência igual após reiniciar (`docs/evidence/pilha_local_v0350.txt`). O axe-core real não é baixável
aqui; por isso o achado de acessibilidade só apareceu no CI — e agora tem teste local.

## 7. Regressão — o que esta rodada encontrou e o que foi feito

| Falha | Causa real | Correção |
|---|---|---|
| `test_v0170_payments` (regressão completa, 2570 testes): evento sem assinatura não encontrado pelo id alegado | o PAY-13 guarda o não assinado sob identificador próprio (`unverified:…`) de propósito; o teste antigo procurava pelo id que o atacante alegou | o teste passa a procurar pelo prefixo e continua exigindo "guardado e não aplicado" (`fd1c86c`); a asserção não foi afrouxada |
| `test_v0230_execution_matrices` [API_AUTHORIZATION_MATRIX.csv] | a matriz foi gerada antes da regressão, sem a observação das 6 rotas novas pela varredura | regenerada com `api_sweep_observed.json` da própria regressão |
| `test_v0230_release_gate` (manifesto da versão) | manifesto de rastreabilidade gerado só no fechamento | `IMPACTO_v0.35.0_TRACEABILITY.json` gerado |
| `test_v0250_cobertura` | matriz de cobertura gerada antes do relatório de jornadas da regressão | regenerada com `jornadas_v0250/relatorio.json` |
| `test_v0270_release_docs` (5): relatório, auditoria, manifesto e notas | documentos de fechamento ainda os da v0.34.0 | este relatório, esta auditoria e o manifesto final da v0.35.0 |
| `test_v0300_release_docs` (matriz de jornadas por perfil) | gerada com o relatório do ensaio da pilha (280 passos), a suíte produz 274 (sem os passos da academia que o seed da pilha tem) | regenerada com o relatório da regressão |
| `pilha-do-zero` (CI do PR #8): axe-core `select-name` em `/admin/identidade` | o filtro "Aguardando decisão / Já decididas" do lote H não tinha nome acessível; o axe não roda aqui | `aria-label`; `test_e2e_v0350_admin_screens` falha no front de `fd1c86c` e passa agora |
| `test_v0230_execution_matrices` [INTEGRATION_HOMOLOGATION_MATRIX.csv] (portões de fechamento, 246 testes) | a matriz de integrações lista os módulos de teste que exercitam cada integração e foi gerada antes do módulo E2E novo existir | regenerada com `make_integration_matrix.py`; portões reexecutados ao fim do log |
| `test_v0240_managed_db` (lote E): `digest()` não encontrada no desenho do Supabase | o primeiro laço do DB-03 trocava o `search_path` inteiro e perdia `extensions` | o laço preserva o caminho existente e só acrescenta `pg_temp` |
| `test_v0340_*` (lote H): receita conferida maior que a esperada | o teste de quatro olhos da remuneração deixava uma obrigação liquidada | a transação do teste é desfeita no fim |
| `test_e2e_v0101` (lote C): diálogo de identidade bloqueava o clique | escrita administrativa passou a pedir step-up | o teste confirma a identidade no diálogo, como a pessoa faria |
| `test_v0350_security` (visualizadora): sessão de administração em cache vencida na suíte completa | cache de sessão entre classes | a classe limpa o cache antes |
| `test_v0350_security` lote B no código anterior: preparação 405 | a rota de confirmação por segunda pessoa não existia | sonda com os helpers daquele commit (`probe_loteB_old.py`) mostra as três falhas |
| `test_v080` (lote H): bloqueio de organização em um passo | o bloqueio passou a ter proposta e confirmação | o teste propõe com uma pessoa e confirma com outra |
| `test_v0230_authorization_matrix` e `test_v0230_frontend_gate`: contagens 988/263/119 | 6 rotas e 3 permissões novas | 994/267/122, com o motivo ao lado |

## 8. Build e pacote

| Passo | Resultado |
|---|---|
| `ruff check impacto tests` | 0 avisos |
| `tsc --noEmit` (tipos oficiais do React, removidos após a checagem) | 0 erros |
| `node build.mjs` | ok |
| `IMPACTO_TRUST_FINAL_RELEASE_0.35.0.zip` | `make_release.py`; `verify_package_against_git.py` byte a byte; `secrets_scan.py`; `unzip -t`; SHA-256 no `.sha256` |

## 9. BLOCKED_EXTERNAL

Token "C2"; repositório privado; proteção da `main`; alertas do Dependabot; variáveis do checklist; merges e publicação (com o
worker); backup e ensaio no formato novo; diagnóstico do banco e antivírus da produção (não autorizados); KYC/KYB; jurídico/DPO;
tag.

## 10. Veredito desta auditoria

Nenhum FAIL em aberto. As correções fazem o que os lotes A–I autorizados pedem, cada uma com teste que falhava antes; o que
depende do responsável ou de autorização está marcado como tal. Detalhado em `FINAL_EXECUTION_REPORT.md` §27.
