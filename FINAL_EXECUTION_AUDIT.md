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
| Conciliação com fila de exceções | PASS | `reconciliation.py` · `test_08` | 9 tipos; não duplica; histórico; sandbox snapshot | rotina não agendada | agendar no worker (decisão) |
| Tarifa nova não altera operação antiga | PASS | `test_09` | versão congelada por obrigação | — | — |
| Limites, adulteração pelo cliente, concorrência | PASS | `test_10` | 422 fora dos limites/campo extra; 6 entregas → 1 confirmação | — | — |
| Meta atingida/ultrapassada | PASS | `test_13` | `target_reached` continua aceitando; contingência declarada | — | — |
| Segregação de funções | PASS | rotas com `finance.approve` · `test_04/05` (403 para `finance`) | — | — | — |
| Telas | PASS | 6 capturas em `docs/evidence/screens_v0340/`; `tsc` 0; build ok | — | — | conferir no demo |
| Matrizes, diagramas, modelo 24m, cobertura dos 40 cenários | PASS | `docs/finance/*` · `test_v0340_release_docs` | — | premissas sem histórico | — |
| Split, recorrência cobrada, cobrança real, NFS-e | BLOCKED_EXTERNAL | flags recusadas; regras inativas | — | — | contrato, parecer, ADR |

## 2. Motores

Inalterados (50; VERDE 37 · AMARELO 13 · VERMELHO 0).

## 3. Perfis, rotas e jornadas

986 operações (+24: 1 pessoa, 6 organização, 17 equipe), 235 telas (+4), 60 rotas públicas (inalterado), 262 rotas de plataforma
(+16), 118 permissões nomeadas (+16). Jornada "Captação" ganhou os passos do ecossistema (empresa doa em nome da organização,
compromisso, recurso externo, painéis) — 269 passos, 0 falhas na ordem da suíte.

## 4. Banco de dados

Migração `0073_v0340_financial_ecosystem.sql`: 9 tabelas novas (`monetization_policy_versions`, `remuneration_notices`,
`remuneration_obligations`, `remuneration_obligation_events`, `external_resources`, `donation_pledges`, `reconciliation_exceptions`,
`reconciliation_exception_events`, `reconciliation_runs`), 4 funções/gatilhos (máquina de estados e log da obrigação, log da exceção,
guarda de doação com liquidação/estorno parcial), colunas em `campaigns` e `donations`, 2 regras + cartas, 4 categorias de auditoria,
GRANTs mínimos. Aplicada em banco novo (73 migrações) e pelo caminho de atualização. Só acrescenta.

## 5. Segurança e LGPD

Matriz de riscos com 23 linhas (`docs/finance/RISK_MATRIX.md`). Contexto de sistema só nas rotas de equipe/pessoa/público (as de
organização usam RLS). Nenhuma função de bloqueio no módulo de remuneração. `secrets_scan.py` limpo.

## 6. CI

O CI completo roda no pull request. Resultado da execução do PR deste ramo: a registrar no PR; local: §7 e
`docs/evidence/test_run_v0.34.0.log`.

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

## 8. Build e pacote

| Passo | Resultado |
|---|---|
| `ruff check impacto tests` | 0 avisos |
| `tsc --noEmit` (tipos oficiais do React, removidos após a checagem) | 0 erros |
| `node build.mjs` | ok |
| `IMPACTO_TRUST_FINAL_RELEASE_0.34.0.zip` | `make_release.py`; `verify_package_against_git.py` byte a byte; `secrets_scan.py`; `unzip -t`; SHA-256 no `.sha256` |

## 9. BLOCKED_EXTERNAL

Parecer e cartas verdes; contrato com provedor; termos; NFS-e; rotina agendada; merges e publicação; pendências da v0.32.0; tag.

## 10. Veredito desta auditoria

Nenhum FAIL em aberto. A camada faz o que o pacote e as correções do responsável pedem dentro do que é permitido sem contrato e sem
parecer — e recusa, por código e por banco, o que não é. Detalhado em `FINAL_EXECUTION_REPORT.md` §27.
