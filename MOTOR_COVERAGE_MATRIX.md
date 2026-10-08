# MOTOR COVERAGE MATRIX — IMPACTO TRUST (v0.27.0)

Gerada por `scripts/make_motor_coverage_matrix.py` a partir de `impacto/engines/coverage.py` e das jornadas
(`tests/demo_journeys.py`, `tests/test_e2e_*.py`). **Nenhuma coluna é escrita à mão.** Conferida por
`backend/tests/test_v0270_release_docs.py`.

**48 motores** — VERDE 35 · AMARELO 13 · VERMELHO 0.

| Coluna | O que afirma |
| --- | --- |
| implementado | módulo importa e a função declarada é chamável |
| integrado | rota no roteador ou chamada por tarefa agendada |
| testado | alguma suíte importa o módulo ou exercita uma rota dele |
| E2E | algum teste chama uma rota pelo HTTP (roteador, autorização, RLS, serialização) |
| jornada | alguma rota do motor aparece numa jornada demo ou E2E de interface (n/a = sem rota própria) |
| segurança | rotas exigem autenticação (pública só se revisada) |
| rastro | auditoria, evento de domínio, Value Ledger, `ops_job_runs` ou versão persistida |
| status | VERDE = tudo; AMARELO = sem E2E ou sem rastro; VERMELHO = falha estrutural |

| motor | grupo | natureza | rotas | implementado | integrado | testado | E2E | jornada | segurança | rastro | status |
| --- | --- | --- | ---: | --- | --- | --- | --- | --- | --- | --- | --- |
| `help_assistant` — Assistente da Central de Conhecimento | busca | grounded_retrieval | 1 | sim | sim | sim | sim | não | sim | sim | VERDE |
| `help_search` — Busca na Central de Conhecimento | busca | deterministic | 2 | sim | sim | sim | sim | não | sim | sim | VERDE |
| `solution_assistant` — Copiloto de soluções | busca | grounded_retrieval | 2 | sim | sim | sim | sim | não | sim | sim | VERDE |
| `match` — Compatibilidade OSC ↔ oportunidade | compatibilidade | deterministic | 4 | sim | sim | sim | sim | sim | sim | sim | VERDE |
| `professional_match` — Compatibilidade profissional ↔ necessidade | compatibilidade | deterministic | 2 | sim | sim | sim | sim | não | sim | sim | VERDE |
| `recommendation` — Próxima ação recomendada | compatibilidade | deterministic | 2 | sim | sim | sim | sim | sim | sim | sim | VERDE |
| `solution_match` — Aderência da solução à tese do financiador | compatibilidade | deterministic | 2 | sim | sim | sim | sim | não | sim | sim | VERDE |
| `compliance_checks` — Conferências de conformidade | confiança | deterministic | 3 | sim | sim | sim | sim | não | sim | sim | VERDE |
| `enforcement_ladder` — Escada de medidas de moderação | confiança | deterministic | 3 | sim | sim | sim | sim | sim | sim | sim | VERDE |
| `report_integrity` — Apuração de denúncia em quatro níveis | confiança | deterministic | 4 | sim | sim | sim | sim | sim | sim | sim | VERDE |
| `risk_signals` — Sinais de risco operacional | confiança | deterministic | 4 | sim | sim | sim | sim | sim | sim | sim | VERDE |
| `diagnostic` — Diagnóstico de lacunas | conformidade | deterministic | 3 | sim | sim | sim | sim | sim | sim | sim | VERDE |
| `eligibility` — Elegibilidade institucional | conformidade | deterministic | 1 | sim | sim | sim | sim | não | sim | sim | VERDE |
| `lifecycle` — Ciclo de vida do projeto | conformidade | deterministic | 3 | sim | sim | sim | sim | sim | sim | sim | VERDE |
| `document_assembly` — Montagem de documento a partir de modelo | documento | deterministic | 3 | sim | sim | sim | sim | sim | sim | sim | VERDE |
| `document_classification` — Classificação de documento | documento | deterministic | 2 | sim | sim | sim | sim | sim | sim | não | AMARELO |
| `contract_rules` — Contrato como regra de operação | econômico | deterministic | 3 | sim | sim | sim | sim | sim | sim | sim | VERDE |
| `control_tower` — Torres de controle (financiador e governo) | econômico | deterministic | 2 | sim | sim | sim | sim | sim | sim | não | AMARELO |
| `economic_layer` — Camada econômica da operação (matriz, repasses, participação, quitação) | econômico | deterministic | 10 | sim | sim | sim | sim | sim | sim | sim | VERDE |
| `master_tower` — Torre MASTER / financeira do proprietário | econômico | deterministic | 1 | sim | sim | sim | sim | não | sim | não | AMARELO |
| `result_chain` — Cadeia de resultado | econômico | deterministic | 1 | sim | sim | sim | sim | não | sim | sim | VERDE |
| `territorial_gap` — Lacuna territorial da carteira | econômico | deterministic | 1 | sim | sim | sim | sim | não | sim | sim | VERDE |
| `value_ledger` — Registro de valor entregue | econômico | deterministic | 2 | sim | sim | sim | sim | não | sim | sim | VERDE |
| `evidence` — Evidência, frescor e confiança | evidência | deterministic | 0 | sim | sim | sim | n/a | n/a | n/a | não | AMARELO |
| `impact_report` — Relatório de impacto por período | evidência | deterministic | 3 | sim | sim | sim | sim | sim | sim | sim | VERDE |
| `report_center` — Central de relatórios | evidência | deterministic | 2 | sim | sim | sim | sim | não | sim | não | AMARELO |
| `fiscal` — Estimativa fiscal | fiscal | deterministic | 2 | sim | sim | sim | sim | não | sim | sim | VERDE |
| `retention_policy` — Conferência da política de retenção | governança | deterministic | 1 | sim | sim | sim | não | não | sim | não | AMARELO |
| `risk_levels` — Inventário de risco por operação | governança | deterministic | 1 | sim | sim | sim | não | não | sim | sim | AMARELO |
| `ai_draft` — Reescrita de rascunho (IA) | ia | llm_assisted | 1 | sim | sim | sim | sim | não | sim | sim | VERDE |
| `ai_structure_need` — Estruturação de necessidade (IA) | ia | llm_assisted | 1 | sim | sim | sim | sim | não | sim | sim | VERDE |
| `ai_summarize` — Resumo de projeto (IA) | ia | llm_assisted | 1 | sim | sim | sim | sim | não | sim | sim | VERDE |
| `claim_integrity` — Integridade de afirmação de impacto | impacto | deterministic | 4 | sim | sim | sim | sim | sim | sim | sim | VERDE |
| `data_quality` — Qualidade do dado declarado | impacto | deterministic | 2 | sim | sim | sim | sim | não | sim | sim | VERDE |
| `equity_context` — Contexto de equidade e normalização | impacto | deterministic | 4 | sim | sim | sim | sim | sim | sim | sim | VERDE |
| `reputation` — Reputação por dimensão observada | impacto | deterministic | 4 | sim | sim | sim | sim | sim | sim | sim | VERDE |
| `seals` — Selos: regra pública, concessão e revogação | impacto | deterministic | 4 | sim | sim | sim | sim | sim | sim | sim | VERDE |
| `deadline_sweep` — Varredura de prazos | operação | deterministic | 0 | sim | sim | sim | n/a | n/a | n/a | sim | VERDE |
| `firstrun` — Primeiro acesso: o que já existe e o que falta | orientação | deterministic | 2 | sim | sim | sim | sim | não | sim | sim | VERDE |
| `funding_readiness` — Prontidão de captação de uma solução | prontidão | deterministic | 2 | sim | sim | sim | sim | sim | sim | não | AMARELO |
| `impacto_ready` — Estado verificável 'Projeto IMPACTO Ready' | prontidão | deterministic | 1 | sim | sim | sim | sim | não | sim | não | AMARELO |
| `readiness` — Prontidão da organização e do projeto | prontidão | deterministic | 3 | sim | sim | sim | sim | sim | sim | sim | VERDE |
| `today_cards` — Para você hoje (cartões e contadores do menu) | rede | deterministic | 1 | sim | sim | sim | sim | não | sim | não | AMARELO |
| `intent_parser` — Interpretação de intenção de busca | soluções | deterministic | 1 | sim | sim | sim | sim | não | sim | não | AMARELO |
| `solution_adaptation` — Adaptação de solução a outro território | soluções | deterministic | 1 | sim | sim | sim | sim | não | sim | sim | VERDE |
| `solution_combine` — Combinação de soluções | soluções | deterministic | 2 | sim | sim | sim | sim | não | sim | sim | VERDE |
| `solution_scoring` — Pontuação de solução | soluções | deterministic | 0 | sim | sim | sim | n/a | n/a | n/a | não | AMARELO |
| `glossary_drift` — Detector de divergência de vocabulário | vocabulário | deterministic | 1 | sim | sim | sim | sim | não | sim | não | AMARELO |

## Motores AMARELOS e por quê

* `funding_readiness` — sem rastro durável detectado (auditoria/evento/ledger/versão).
* `document_classification` — sem rastro durável detectado (auditoria/evento/ledger/versão).
* `evidence` — sem rastro durável detectado (auditoria/evento/ledger/versão).
* `report_center` — sem rastro durável detectado (auditoria/evento/ledger/versão).
* `solution_scoring` — sem rastro durável detectado (auditoria/evento/ledger/versão).
* `intent_parser` — sem rastro durável detectado (auditoria/evento/ledger/versão).
* `control_tower` — sem rastro durável detectado (auditoria/evento/ledger/versão).
* `master_tower` — sem rastro durável detectado (auditoria/evento/ledger/versão).
* `today_cards` — sem rastro durável detectado (auditoria/evento/ledger/versão).
* `impacto_ready` — sem rastro durável detectado (auditoria/evento/ledger/versão).
* `glossary_drift` — sem rastro durável detectado (auditoria/evento/ledger/versão).
* `retention_policy` — sem teste E2E pelo HTTP; sem rastro durável detectado (auditoria/evento/ledger/versão).
* `risk_levels` — sem teste E2E pelo HTTP.

## Motores VERMELHOS

Nenhum.

Nenhum motor é declarado 'completo' por descrição: a cor nasce das colunas, e as colunas nascem do código.
