# Auditoria final de execução — IMPACTO v0.34.0

**Data:** 10/10/2026 · **Ramo:** `ecossistema-v0340` · **Ponto de partida:** `103c643` (v0.33.0, ramo `doacoes-v0330`) · **Versão:** 0.34.0

Estados: **PASS** (feito e provado por execução nesta rodada) · **PARTIAL** (feito; o que falta está escrito) · **BLOCKED_EXTERNAL**
(depende de contrato, parecer, painel ou decisão do responsável; nada simulado) · **FAIL** (falhou e não foi corrigido — não há nenhum;
os que apareceram estão em §7). Nada aqui afirma invulnerabilidade.

## 1. O pedido → o que virou software e prova

Pedido (PROMPT MASTER FULL + complemento do responsável, 10/10): ecossistema financeiro com obrigações calculáveis e cobráveis,
"gratuito até gerar valor" com gatilhos auditáveis, exceções para recurso público, comunicação prévia, regras para iniciar a cobrança,
estado comercial separado da prestação de contas, reserva sem custódia, estados financeiros, conciliação com exceções, matrizes,
diagramas, modelo de 24 meses, 40 cenários de teste.

| Item | Estado | Evidência (arquivo · teste) | Resultado | Risco | Ação restante |
|---|---|---|---|---|---|
| Obrigações com cadeia de estados, valor congelado, histórico | PASS | `0073` · `remuneration.py` · `test_v0340.test_02/04` | 11 estados; gatilho recusa mudar valor; eventos só-inserção | — | ligar acordo/serviço/IA como fontes (previsto) |
| Gatilho auditável "gratuito até gerar valor" | PASS | `remuneration.evaluate` · `test_03` (passa pelo portão real: carta verde + regra validada) | nada devido sem as 5 condições; motivo registrado | parâmetros são hipótese | parecer; política v2 aprovada |
| Comunicação prévia registrada | PASS | `remuneration_notices` · `test_03` | texto, canal, versão, ciência | textos em rascunho | revisão jurídica |
| Recurso público isento salvo instrumento | PASS | `test_05` | `exempt` → autorização só com `finance.approve` + instrumento + justificativa | análise por instrumento | jurídico |
| Reserva/fundo sem custódia nem receita | PASS | motor `success_fee` inativável (ADR-022) · `test_v0340_release_docs` | banco recusa ativar | — | redação dos termos |
| Estado comercial separado da prestação de contas | PASS | `test_11` (varredura) · `test_04` (vencida não bloqueia) | nenhuma rota consulta o estado comercial | — | — |
| Liquidado ≠ confirmado; pendente ≠ arrecadado | PASS | `test_01` | `settled_at` não se desfaz; totais separados | — | — |
| Estorno parcial / total após parcial / chargeback | PASS | `test_06`, `test_12` | razão fecha em zero; comprovante anulado; obrigação estornada | tarifa do provedor no parcial depende do contrato | — |
| Compromissos e recursos externos fora da barra | PASS | `test_07` | nenhum lançamento; totais à parte; recurso público exige instrumento | — | — |
| Painel do financiador | PASS | `funder_view` · `test_07` · captura `04_financiador_contribuicoes.png` | doações em nome da organização e compromissos | — | — |
| Conciliação com fila de exceções | PASS | `reconciliation.py` · `test_08` · rotina `financial_ops` (E6) | 11 tipos; não duplica; histórico; periódica no worker | — | publicar o worker junto |
| Tarifa nova não altera operação antiga | PASS | `test_09` | versão congelada por obrigação | — | — |
| Limites, adulteração pelo cliente, concorrência | PASS | `test_10` | 422 fora dos limites/campo extra; 6 entregas → 1 confirmação | — | — |
| Meta atingida/ultrapassada | PASS | `test_13` | `target_reached` continua aceitando; contingência declarada | — | — |
| Segregação de funções | PASS | rotas com `finance.approve` · `test_04/05` (403 para `finance`) | — | — | — |
| Telas | PASS | 6 capturas em `docs/evidence/screens_v0340/`; `tsc` 0; build ok | — | — | conferir no demo |
| Matrizes, diagramas, modelo 24m, cobertura dos 40 cenários | PASS | `docs/finance/*` · `test_v0340_release_docs` | — | premissas sem histórico | — |
| Cartão no sandbox (cenário 2) | PASS | `test_v0340_open_scenarios.test_02` | confirmado pelo mesmo evento assinado; **antes da E6 toda doação por cartão era recusada** (faltava a tabela de tarifa) | — | — |
| Falha temporária do provedor (8) | PASS | `test_08` (falha injetada só no teste) | 503, nada gravado, a mesma chave repete | — | — |
| Evento que falha ao aplicar (33) e reprocessamento (35) | PASS | `test_33_35`, `test_33b` | duas fases; `failed` + exceção + 500; rotina reaplica; reentrega `duplicate` | — | — |
| Liquidação parcial (18) e falha de liquidação (17) | PASS | `test_17_18` | acumulada; exceções `settlement_partial`/`settlement_failed`; pagamento continua confirmado | — | — |
| Split (14) e split indisponível (15) | PASS (simulado) | `test_14_15` (trava e provedor que divide ligados só no teste) | só a contribuição voluntária é dividida; sem split, fatura à organização; razão equilibrado | split real depende do provedor | contrato e homologação |
| Recorrência (25) e cancelamento (38) | PASS (sandbox) | `test_25_38` | autorização ≠ tentativa ≠ confirmado; pausa após 3 falhas; cancelado/pausado não cobra | instrumento recorrente real | provedor |
| Reembolso do recebido (39) e fatura protegida | PASS | `test_39` | integral segregado; devolução pelo provedor reverte; organização recebe 403 ao mover a fatura | — | — |
| Split real, recorrência cobrada de verdade, cobrança real, NFS-e | BLOCKED_EXTERNAL | flags recusadas; regras inativas | — | — | contrato, parecer, ADR |

## 2. Motores

Inalterados (50; VERDE 37 · AMARELO 13 · VERMELHO 0).

## 3. Perfis, rotas e jornadas

988 operações (+26: 2 pessoa, 6 organização, 18 equipe), 235 telas (+4), 60 rotas públicas (inalterado), 263 rotas de plataforma
(+17), 119 permissões nomeadas (+17). Jornada "Captação" ganhou os passos do ecossistema (empresa doa em nome da organização,
compromisso, recurso externo, painéis) — 269 passos, 0 falhas na ordem da suíte.

## 4. Banco de dados

Migração `0073_v0340_financial_ecosystem.sql`: 9 tabelas novas (`monetization_policy_versions`, `remuneration_notices`,
`remuneration_obligations`, `remuneration_obligation_events`, `external_resources`, `donation_pledges`, `reconciliation_exceptions`,
`reconciliation_exception_events`, `reconciliation_runs`), 4 funções/gatilhos (máquina de estados e log da obrigação, log da exceção,
guarda de doação com liquidação/estorno parcial), colunas em `campaigns` e `donations` (E6: contribuição, liquidação acumulada, parte dividida), contas novas no razão (contribuição),
colunas de tentativas na recorrência, tabela de tarifa do cartão no sandbox, 3 regras + cartas, 4 categorias de auditoria,
`polymorphic_refs` da obrigação, retenção declarada (`config/data_retention.json`),
GRANTs mínimos. Aplicada em banco novo (73 migrações) e pelo caminho de atualização. Só acrescenta.

## 5. Segurança e LGPD

Matriz de riscos com 28 linhas (`docs/finance/RISK_MATRIX.md`); E6 achou e fechou uma brecha (fatura da plataforma movida pela
própria organização). Contexto de sistema só nas rotas de equipe/pessoa/público (as de
organização usam RLS). Nenhuma função de bloqueio no módulo de remuneração. `secrets_scan.py` limpo.

## 6. CI

O CI completo roda no pull request (job a job; o log do job não é legível pela API neste ambiente — só as anotações).

| Execução | Commit | Resultado |
|---|---|---|
| PR #6, `38021228652` (a última da v0.33.0) | `103c643` | auditoria, armazenamento e docker verdes; **backend vermelho** (1 falha: matriz de jornadas por perfil, dependente da ordem da suíte — verde no PR #7) e **pilha-do-zero vermelho**. O relatório da v0.33.0 dava as falhas do CI como corrigidas; esta execução, posterior ao fechamento, mostra que o `pilha-do-zero` não estava |
| PR #7, `38051419136` | `c81c6b7` | cancelada (duplicada da seguinte; poupa a cota de minutos do repositório privado) |
| PR #7, `38051432373` | `813a052` | auditoria, armazenamento, docker e **backend verdes** (suíte completa, E2E no navegador, backup e restauração); **pilha-do-zero vermelho** — mesma causa do PR #6 (§7, linha `pilha-do-zero`) |
| PR #7, execução após a correção | commit da correção (E7) | em execução quando este commit foi feito — resultado registrado no commit seguinte |

Reprodução local da pilha (sem Docker, que não alcança registro de imagens aqui, com o MESMO roteiro): banco novo com o desenho
do Supabase (administrador sem superusuário, `pgcrypto` em `extensions`), migrações como administrador, aplicação como
`impacto_app`, seed de demonstração, `scripts/demo_stack.py --telas`. Antes da correção: "Captação" interrompida por exceção.
Depois: 16 jornadas, 275 passos, 0 falha; 235 rotas de tela, 857 visitas, todas as 235 abertas com dado real, 0 falha; persistência após reiniciar a aplicação: contagens iguais (`docs/evidence/pilha_local_v0340.txt`). O axe-core real não é baixável aqui (registro npm bloqueado); no CI ele roda com `--axe-trava`.

## 7. Regressão — o que esta rodada encontrou e o que foi feito

| Falha | Causa real | Correção |
|---|---|---|
| ativar `donation.platform_fee` no teste → `InsufficientPrivilege` ADR-022 | a regra estava no motor `success_fee`, que o banco recusa ativar por desenho | reclassificada para `enterprise` (fatura à parte sobre base registrada, como a taxa do acordo); fundo e reserva ficam no motor inativável de propósito (ADR-378/380) |
| ativar regra no teste → carta legal não verde | cartas são append-only; não se "edita" para verde | o teste emite carta VERDE nova (como uma revisão real faria) e devolve a original no `finally` |
| `finance.write` → 401 `step_up_required` | permissões de escrita financeira exigem confirmação de identidade | `reauth()` nos clientes de equipe do teste |
| `CampaignIn` recusa `funding_source` | esquema não tinha o campo | campo + instrumento obrigatório para público na criação |
| teste de recurso externo contava lançamentos "dos últimos 2 s" | asserção frouxa | compara a contagem antes/depois |
| captura das telas de administração → "área não disponível" | a conta de administração do harness tem uma organização OSC como primeira associação | só na captura: associação removida; nada muda no produto |
| contagens fixadas (986/262/118/235), docs com números, matrizes | módulo novo | atualizadas com a razão; regeneradas |
| `test_v0330_release_docs` pinava VERSION = 0.33.0 | pin de versão absoluta | passa a exigir ≥ 0.33.0 e a entrada no CHANGELOG |
| `RISK_MATRIX.md` continha a frase proibida (negada) | o teste de documentos procura a afirmação | reescrita sem a frase |
| `test_v0190_lgpd_deletion` (regressão da E5, 2.470 testes): retenção sem classe para `remuneration_obligations.org_id` e `reconciliation_exceptions.org_id` | colunas novas que não são cascata, sem decisão registrada | declaradas em `config/data_retention.json` (retida; anonimizável) com motivo |
| `test_v0230_provenance` (idem): `remuneration_obligations.source_id` fora do catálogo polimórfico | coluna polimórfica nova | registrada em `polymorphic_refs` na 0073 |
| `test_v0200_cleanup` (idem): `forbid_blocking_use` inalcançável | eu tinha escrito uma função "documentação viva" que só levantava erro — não era guarda | removida; a guarda real é `test_11` (varredura) e `never_blocks` |
| `test_v0340_open_scenarios.test_02` (E6): doação por cartão → 422 `provider_fee_unknown` | o sandbox só tinha tabela de tarifa para Pix; **a nota da cobertura dizia "cartão aceito" sem teste** | tabela do cartão no sandbox; cenário 2 com teste |
| `test_v0340_open_scenarios.test_25_38` (E6): recorrência não criava tentativa | consequência do cartão; depois, a chave por data colidia quando o teste repunha a data | tarifa do cartão; chave por número da tentativa (atômica com o contador) |
| `test_v0340_financial_ecosystem.test_02` (E6): devido global ≠ 0 | a contribuição do cenário 15 fica legitimamente devida | o teste novo fecha o ciclo (dispensa com motivo); a asserção antiga não foi afrouxada |
| `test_v0340_open_scenarios.test_39` (E6): organização movia a fatura da plataforma pela rota de cobranças | `PAY.transition` só conferia a aresta do grafo, não a origem | 403 `platform_invoice` para fatura ligada a obrigação; só administração/provedor |
| `test_v0340_release_docs` (E6): `DONATIONS_API.md` com descrições deslocadas uma linha | tabela escrita à mão na E4 | gerador `scripts/make_donations_api_doc.py`; teste confere linha a linha |
| `test_v0200_cleanup` (E6): `apply_provider_event` inalcançável | o webhook passou a usar as duas fases | removida |
| `test_v0230_authorization_matrix` (E6): contagens (988/263/119/16) | duas rotas e uma regra novas | atualizadas com a razão |
| `test_v0170_monetization` (regressão da E6, 2.478 testes): regra da contribuição com preço fixado (`amount_cents = 0`) | hipótese de motor de rank ≤ 3 não pode declarar preço; e `unit` exige preço para ativar | modo `contract` sem preço: o valor é o que o doador escolhe nos termos da doação |
| `pilha-do-zero` (CI do PR #6 e do PR #7): jornada "Captação" interrompida por `CalledProcessError` em `psql … naousado` | na v0.33.0 a pessoa anônima que doa virou `Client()` — o cliente que sobe o servidor DE TESTE (banco descartável); na pilha Docker não há servidor de teste. Passava na suíte local, que tem esse servidor, e o job só dizia "exit code 1" | `Http(self.base)`; teste-guarda `test_the_journeys_never_start_the_test_server` (falha no código antigo, linha 413); `scripts/demo_stack.py` põe cada falha de jornada/tela nas anotações do job; reproduzido e conferido localmente numa pilha montada como a do CI (§6) |
| `test_e2e_web` (regressão da E6): tempo esgotado ao preencher campo | eu reconstruí o pacote do front enquanto a suíte rodava (arquivos trocados no meio do teste de navegador) | módulo reexecutado com o front estável: verde; nenhum código mudou |

## 8. Build e pacote

| Passo | Resultado |
|---|---|
| `ruff check impacto tests` | 0 avisos |
| `tsc --noEmit` (tipos oficiais do React, removidos após a checagem) | 0 erros |
| `node build.mjs` | ok |
| `IMPACTO_TRUST_FINAL_RELEASE_0.34.0.zip` | `make_release.py`; `verify_package_against_git.py` byte a byte; `secrets_scan.py`; `unzip -t`; SHA-256 no `.sha256` |

## 9. BLOCKED_EXTERNAL

Parecer e cartas verdes; contrato com provedor (split e instrumento recorrente); termos; NFS-e; merges e publicação (com o worker);
pendências da v0.32.0; tag.

## 10. Veredito desta auditoria

Nenhum FAIL em aberto. A camada faz o que o pacote e as correções do responsável pedem dentro do que é permitido sem contrato e sem
parecer — e recusa, por código e por banco, o que não é. Detalhado em `FINAL_EXECUTION_REPORT.md` §27.
