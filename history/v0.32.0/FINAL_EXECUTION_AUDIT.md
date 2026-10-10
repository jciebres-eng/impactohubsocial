# Auditoria final de execução — IMPACTO v0.32.0

**Data:** 09/10/2026 · **Ramo:** `correcoes-auditoria` (PR #5 para a `main`) · **Ponto de partida:** `906d383` (main: v0.30.1 +
backup/monitor + `CLAUDE.md`) + `infra/v0.31.0` + `auditoria-inicial` · **Versão:** 0.32.0

Estados: **PASS** (feito e provado por execução nesta rodada) · **PARTIAL** (feito; o que falta está escrito) ·
**BLOCKED_EXTERNAL** (depende de painel, conta ou decisão do responsável; nada simulado) · **FAIL** (falhou e não foi
corrigido — não há nenhum; os que apareceram estão em §7). Nada aqui afirma "100% impossível de invadir".

## 1. O pedido → o que virou software e prova

Pedido do responsável (09/10, depois da auditoria inicial): desativar as 15 contas de demonstração da produção; demo aberto a
quem tiver o link; código privado; trazer a branch `infra/v0.31.0` e "resolver tudo".

| Item | Estado | Evidência (arquivo · teste · execução) | Resultado | Risco | Ação restante |
|---|---|---|---|---|---|
| Contas de demonstração desativadas na produção | PASS | `scripts/demo_accounts.py` · `test_v0320_demo_accounts` · execução 37996712177 | 15 contas `disabled`, sessões encerradas, 5 organizações `suspended`, auditoria | nenhum (reversível) | — |
| Conteúdo público fictício fora do ar na produção | PASS | execuções 37997211737 e 37997481695 | 11 itens (1 projeto, 7 soluções, 1 material, 2 editais); 0 em 10 tipos de conteúdo depois | conteúdo de nível "rede" (não público) continua visível a membros logados — o cadastro em produção está bloqueado pela trava jurídica | — |
| Restauração do backup cifrado do R2 | PASS | job `ensaio-restauracao` · execução 37997867650 | arquivo de 20:43 UTC conferido, decifrado, restaurado: 341 tabelas, verificadores íntegros, 4,1 s | — | — |
| Ensaio mensal de restauração | PASS | `backup-supabase.yml` (cron do dia 1º) · `test_v0320_release_docs.BackupDrillTests` | agendado | depende do agendamento do GitHub | conferir em 01/11 |
| Instruções de restauração corrigidas | PASS | cabeçalho do `backup-supabase.yml` · `BackupDrillTests` | apontam para o script que funciona | — | — |
| Worker com menor privilégio | PARTIAL | `backend/start_worker.sh` (ensaiado na v0.31.0: 18 tarefas OK) · `CLAUDE.md` | código na imagem | até a troca, o worker segue com a conexão administrativa | trocar o Start Command no Railway |
| Aviso de demonstração | PASS | `web/src/ui/demobanner.tsx` · `DemoBannerTests` · capturas claro/escuro em `development` | faixa em toda tela, só em `development` | — | conferir no demo depois do merge |
| CI de volta ao verde | PASS | teste de RLS atualizado; matriz regenerada; manifesto | ver §6 | — | — |
| Branch `infra/v0.31.0` trazida | PASS | merge `dc03db1` (só o CHANGELOG conflitou; resolvido mantendo as duas entradas) | — | — | — |
| Repositório privado | BLOCKED_EXTERNAL | o ambiente das sessões recusa alterar configurações do repositório (HTTP 403) | rotinas já ajustadas à cota | minutos de Actions | clique do responsável |
| Rotinas dentro da cota do Actions | PASS | `monitor.yml` horário; `backend`/`pilha-do-zero` só fora de push · `PrivateRepoBudgetTests` | — | plano da conta não verificado | — |
| Proteção 0071 na produção | BLOCKED_EXTERNAL | diagnóstico: 1 migração pendente | depende do "Deploy latest commit" | 3 alertas do Security Advisor seguem abertos até lá | publicar a produção |

## 2. Motores

50 motores, inalterados. `MOTOR_COVERAGE_MATRIX.md` VERDE 37 · AMARELO 13 · VERMELHO 0.

## 3. Perfis, rotas e jornadas

Inalterados: 940 operações, 227 telas. A faixa de demonstração não é tela nova.

## 4. Banco de dados

71 migrações (nenhuma nova nesta versão). Escritas feitas na produção, todas autorizadas e registradas na trilha de auditoria:
`users.status`, `sessions.revoked_at`, `organizations.status` e a visibilidade de 11 itens das organizações fictícias.

## 5. Segurança e LGPD

| Item | Estado | Evidência | Resultado | Risco | Ação |
|---|---|---|---|---|---|
| Nenhum segredo no repositório | PASS | `secrets_scan.py`; gitleaks no CI | 0 achados | — | — |
| Backup e ensaio não publicam artefato | PASS | `BackupDrillTests`, `test_v0310_release_docs.BackupRestoreTests` | — | — | — |
| Desativação não apaga e não toca conta real | PASS | `test_v0320_demo_accounts` | conta real de administração segue entrando | — | — |
| Chaves do backup expostas num chat | BLOCKED_EXTERNAL | informação do responsável | — | quem tiver as chaves lê/apaga backups | trocar o token |

## 6. CI

| Job | Estado | Evidência |
|---|---|---|
| CI do PR #5 (suíte completa, pilha do zero, imagem, auditoria, armazenamento) | PASS | execução 38002549412 no commit candidato `8aec7d1`: os cinco verdes |

## 7. Regressão — o que esta rodada encontrou e o que foi feito

| Falha | Causa real | Correção |
|---|---|---|
| `test_every_table_but_the_declared_exception_has_rls_enabled` (main) | a 0071 ligou RLS na tabela que o teste listava como exceção | exceção declarada passa a ser nenhuma, com o motivo escrito |
| `test_regenerating_each_matrix_reproduces_what_is_committed` (main) | teste novo da v0.30.1 sem regenerar a matriz de integrações | `make_integration_matrix.py` |
| `test_every_tracked_file_is_either_in_the_manifest_or_excluded_with_a_reason` (main) | arquivos novos desde a análise econômica fora de qualquer manifesto | manifesto da v0.32.0 |
| `test_disable_is_complete_reversible_and_never_touches_real_accounts` (1ª versão: 16 ≠ 15) | o seed atual cria 16 contas de demonstração (as 15 personas + "coletivo"); a produção foi semeada antes | o teste usa a contagem do banco |
| `test_disable_is_complete_reversible_and_never_touches_real_accounts` (404) | eu usei uma rota inexistente para "quem sou eu" | `/v1/me` |
| `demo_accounts.py` contava 0 soluções públicas | eu usei `visibility = 'public'`; soluções usam `'published'` | tabela de conteúdo com os valores reais de cada tipo, conferidos no esquema; a recontagem achou 7 soluções, 1 material e 2 editais |
| `CHANGELOG.md` em conflito no merge | as duas branches acrescentaram uma entrada no topo | as duas mantidas, em ordem |
| `contas-demo.yml` com disparo respondendo 404 | o GitHub só dispara workflow que já existe na `main` | modos acrescentados ao workflow `supabase`, que existe na `main` |
| `gh api PATCH visibility` respondendo 403 | o ambiente das sessões não altera configurações do repositório | clique do responsável; rotinas ajustadas antes |
| `test_regenerating_the_map_reproduces_what_is_committed` (CI do PR #5) | a faixa do demo chama `/v1/meta/config` a partir de um arquivo novo do front; o mapa tela × API não foi regenerado | `make_screen_backend_map.py` |
| `pkill` derrubou o próprio terminal | o padrão casava com o comando em execução | servidor de teste parado e commit refeito separadamente |

## 8. Build e pacote

| Passo | Resultado |
|---|---|
| `ruff check impacto tests` | 0 avisos |
| `tsc --noEmit` (tipos oficiais do React, removidos após a checagem) | 0 erros |
| `node build.mjs` | ok |
| `IMPACTO_TRUST_FINAL_RELEASE_0.32.0.zip` | `make_release.py`; `verify_package_against_git.py` byte a byte; `secrets_scan.py`; `unzip -t`; SHA-256 no `.sha256` |

## 9. BLOCKED_EXTERNAL

Publicar a produção (aplica a 0071 e o worker novo); trocar o Start Command do `pleasing-trust`; trocar o token do backup;
tornar o repositório privado; monitor externo; senha de `impacto_app` no GitHub; domínio; e-mail autenticado; revisão jurídica e
encarregado de dados; tags v0.31.0/v0.32.0 no GitHub.

## 10. Veredito desta auditoria

Nenhum FAIL em aberto. Os dois críticos internos da auditoria inicial (contas de demonstração na produção; backup sem
restauração provada) estão resolvidos com prova na própria produção. O que falta é clique ou decisão do responsável.
Detalhado em `FINAL_EXECUTION_REPORT.md` §27.
