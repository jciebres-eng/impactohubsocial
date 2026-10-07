# Match Engine — `match-engine@1.0.0` · pesos `weights@1.0`

Código: `backend/impacto/engines/match/engine.py` (puro, sem I/O) e `territory.py`; orquestração: `services/matching.py`.
Pesos: `config/match_weights.json` (**hipóteses a calibrar** — `status: hipotese_a_calibrar`; não há dado real de desempenho).

## Duas direções
| Direção | Pergunta | Quem usa |
|---|---|---|
| `osc_call` | "Esta OSC/projeto atende a este edital/fundo?" | OSC (catálogo de oportunidades) |
| `funder_project` | "Este projeto combina com o perfil/programa do financiador?" | Empresa (feed de projetos) |

## Pipeline (determinístico)
1. **Requisitos / bloqueadores duros (antes do score)** — cada requisito vira `met | unmet | unknown`, obrigatório ou não.
   Obrigatório `unmet` ⇒ **blocker** com `how_to_fix`. Exemplos `osc_call`: edital aberto, tipo de organização, compliance
   (rejeitado/suspenso bloqueia; pendente = risco), território, tempo mínimo de existência, documentos obrigatórios
   (ausentes, vencidos ou ainda não varridos pelo antivírus), certificações, contrapartida, requisitos customizados, faixa de valor.
2. **Sinais ponderados** — cada sinal tem `weight` e `value ∈ [0,1]` ou `None` (dado ausente).
   - `osc_call`: causa 25 · território 15 · orçamento 15 · prontidão 15 · ODS 10 · prazo 10 · histórico 10
   - `funder_project`: causa 20 · território 15 · orçamento 15 · ODS/ESG 10 · capacidade 10 · histórico de evidências 10 · impacto 10 · urgência 5 · preferência 5
3. **Confiança** = peso dos sinais conhecidos ÷ peso total. Se `< 50` (`min_confidence_for_score`) **não há nota** (`score = null`) — a plataforma diz que precisa de mais dados em vez de inventar um número.
4. **Estado**: `bloqueada` (qualquer blocker) · `revisao_humana` (sem nota) · `prioritaria` (≥75 e elegível) · `compativel` (≥55 e elegível) · `potencial_com_lacunas`.
5. **Elegibilidade**: `blocked | needs_review | eligible`.

## Saída (contrato)
`score`, `confidence`, `eligibility`, `recommended_state`, `blockers[]`, `requirements[]`, `why_match[]` (3 principais sinais), `why_not[]`,
`risks[]` (código, severidade, mensagem), `missing_data[]` (campo, rótulo, dono), `next_action`, `signals[]`, `features{}`
(vetor numérico pronto para ML futuro), `engine_version`, `weights_version`, `disclaimer`. Cada execução é gravada em `match_runs`
(entradas resumidas, versão, saída) para auditoria e para treino futuro — **não há modelo de ML treinado**.

## Território (`territory.py`)
Códigos hierárquicos `INT` › `BR` › `BR-UF` › `BR-UF-IBGE7`. `covers(edital, execução)` e `specificity` (município > UF > Brasil > internacional).
Cobre federal, estadual, municipal, local e internacional.

## Fracionamento
`_ticket_fit` aceita projetos maiores que o ticket máximo quando há **marcos** que permitem financiamento parcial; o texto explica a regra.

## Invariantes (testadas)
- Plano, voucher, pagamento e assinatura **não entram** no cálculo (`forbidden_inputs` + teste AST de arquitetura: `engines/match`, `services/matching` e `services/directory` não importam billing/entitlements).
- Ordenação do feed: elegibilidade → compatibilidade; o feed devolve também `hidden_blocked` (projetos bloqueados com motivos), nunca os descarta silenciosamente.
- Datas exibidas em dd/mm/aaaa; valores em R$.

## O que NÃO existe ainda (honesto)
Pesos por segmento/campanha/organização e A/B testing (há só `call.weights` por edital e um conjunto global versionado);
embeddings semânticos; população-alvo e capacidade financeira como sinais estruturados completos; calibração com dados reais.

## Motores adicionais (v0.8.0–v0.9.0)
- `professional-match@1.0.0` (v0.8.0): profissional ↔ necessidade de apoio; exige credencial verificada para categorias regulamentadas.
- `solution-match@1.0.0` (v0.9.0): financiador ↔ solução — ver `SOLUTION_MATCH_ENGINE.md`. A relevância de **busca** (aderência à consulta) é um cálculo separado — `SOLUTION_SEARCH.md`.
Todos: sem nota com confiança < 50, explicação completa, independência de plano (teste AST).
