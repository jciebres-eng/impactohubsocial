# Cobertura dos motores — Impacto Trust

Gerado por `impacto/engines/coverage.py`. **Nenhuma coluna é escrita à mão**: cada uma é
derivada do código, do roteador, da suíte de testes e do esquema do banco. Um motor não
ganha uma coluna sendo descrito como completo — ganha quando o fato existe.

| Coluna | O que ela afirma, exatamente |
| --- | --- |
| implemented | O módulo importa e a função declarada é chamável. |
| integrated | Pelo menos uma rota declarada existe no roteador, ou o módulo é chamado por tarefa agendada. |
| tested | Alguma suíte importa o módulo ou exercita uma de suas rotas. |
| e2e | Algum teste chama uma rota declarada pelo HTTP, atravessando roteador, autorização, RLS e serialização. |
| security | As rotas declaradas exigem autenticação (rota pública conta só se estiver na lista revisada). |
| observability | Deixa rastro durável: auditoria, evento de domínio, Value Ledger, `ops_job_runs` ou `engine_version` persistida. |

`n/a` = motor sem rota própria: herda a barreira de quem o chama. Não é falha.

**50 motores.** implemented: 50 sim / 0 não · integrated: 50 sim / 0 não · tested: 50 sim / 0 não · e2e: 45 sim / 2 não / 3 n/a · security: 47 sim / 0 não / 3 n/a · observability: 38 sim / 12 não

## busca

| motor | natureza | versão | implemented | integrated | tested | E2E | security | observability |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `help_assistant` — Assistente da Central de Conhecimento | grounded_retrieval | — | sim | sim | sim | sim | sim | sim |
| `help_search` — Busca na Central de Conhecimento | deterministic | help-search@1.0.0 | sim | sim | sim | sim | sim | sim |
| `solution_assistant` — Copiloto de soluções | grounded_retrieval | — | sim | sim | sim | sim | sim | sim |

## compatibilidade

| motor | natureza | versão | implemented | integrated | tested | E2E | security | observability |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `match` — Compatibilidade OSC ↔ oportunidade | deterministic | match-engine@1.2.0 | sim | sim | sim | sim | sim | sim |
| `professional_match` — Compatibilidade profissional ↔ necessidade | deterministic | professional-match@1.0.0 | sim | sim | sim | sim | sim | sim |
| `recommendation` — Próxima ação recomendada | deterministic | recommendation@1.0.0 | sim | sim | sim | sim | sim | sim |
| `solution_match` — Aderência da solução à tese do financiador | deterministic | solution-match@1.0.0 | sim | sim | sim | sim | sim | sim |

## confiança

| motor | natureza | versão | implemented | integrated | tested | E2E | security | observability |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `compliance_checks` — Conferências de conformidade | deterministic | — | sim | sim | sim | sim | sim | sim |
| `enforcement_ladder` — Escada de medidas de moderação | deterministic | — | sim | sim | sim | sim | sim | sim |
| `report_integrity` — Apuração de denúncia em quatro níveis | deterministic | report-integrity@1.0.0 | sim | sim | sim | sim | sim | sim |
| `risk_signals` — Sinais de risco operacional | deterministic | — | sim | sim | sim | sim | sim | sim |

## conformidade

| motor | natureza | versão | implemented | integrated | tested | E2E | security | observability |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `diagnostic` — Diagnóstico de lacunas | deterministic | diagnostic-engine@1.0.0 | sim | sim | sim | sim | sim | sim |
| `eligibility` — Elegibilidade institucional | deterministic | institutional-eligibility@1.0.0 | sim | sim | sim | sim | sim | sim |
| `lifecycle` — Ciclo de vida do projeto | deterministic | — | sim | sim | sim | sim | sim | sim |

## documento

| motor | natureza | versão | implemented | integrated | tested | E2E | security | observability |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `document_assembly` — Montagem de documento a partir de modelo | deterministic | document-assembly@1.0.0 | sim | sim | sim | sim | sim | sim |
| `document_classification` — Classificação de documento | deterministic | — | sim | sim | sim | sim | sim | **NÃO** |

## econômico

| motor | natureza | versão | implemented | integrated | tested | E2E | security | observability |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `contract_rules` — Contrato como regra de operação | deterministic | — | sim | sim | sim | sim | sim | sim |
| `control_tower` — Torres de controle (financiador e governo) | deterministic | — | sim | sim | sim | sim | sim | **NÃO** |
| `economic_layer` — Camada econômica da operação (matriz, repasses, participação, quitação) | deterministic | — | sim | sim | sim | sim | sim | sim |
| `master_tower` — Torre MASTER / financeira do proprietário | deterministic | — | sim | sim | sim | sim | sim | **NÃO** |
| `result_chain` — Cadeia de resultado | deterministic | — | sim | sim | sim | sim | sim | sim |
| `territorial_gap` — Lacuna territorial da carteira | deterministic | — | sim | sim | sim | sim | sim | sim |
| `value_ledger` — Registro de valor entregue | deterministic | — | sim | sim | sim | sim | sim | sim |

## evidência

| motor | natureza | versão | implemented | integrated | tested | E2E | security | observability |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `evidence` — Evidência, frescor e confiança | deterministic | — | sim | sim | sim | n/a | n/a | **NÃO** |
| `impact_report` — Relatório de impacto por período | deterministic | — | sim | sim | sim | sim | sim | sim |
| `report_center` — Central de relatórios | deterministic | — | sim | sim | sim | sim | sim | **NÃO** |

## fiscal

| motor | natureza | versão | implemented | integrated | tested | E2E | security | observability |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `fiscal` — Estimativa fiscal | deterministic | fiscal-engine@1.0.0 | sim | sim | sim | sim | sim | sim |

## governança

| motor | natureza | versão | implemented | integrated | tested | E2E | security | observability |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `retention_policy` — Conferência da política de retenção | deterministic | — | sim | sim | sim | **NÃO** | sim | **NÃO** |
| `risk_levels` — Inventário de risco por operação | deterministic | — | sim | sim | sim | **NÃO** | sim | sim |

## ia

| motor | natureza | versão | implemented | integrated | tested | E2E | security | observability |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `ai_draft` — Reescrita de rascunho (IA) | llm_assisted | — | sim | sim | sim | sim | sim | sim |
| `ai_structure_need` — Estruturação de necessidade (IA) | llm_assisted | — | sim | sim | sim | sim | sim | sim |
| `ai_summarize` — Resumo de projeto (IA) | llm_assisted | — | sim | sim | sim | sim | sim | sim |
| `ai_usage_control` — Controle de uso e custo da IA (autoriza → reserva → executa → liquida) | deterministic | usage-control@1.0 | sim | sim | sim | sim | sim | sim |
| `similarity` — Originalidade, similaridade, complementaridade e integridade do financiamento | deterministic | similarity@1.0 | sim | sim | sim | sim | sim | sim |

## impacto

| motor | natureza | versão | implemented | integrated | tested | E2E | security | observability |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `claim_integrity` — Integridade de afirmação de impacto | deterministic | claim-integrity@1.0.0 | sim | sim | sim | sim | sim | sim |
| `data_quality` — Qualidade do dado declarado | deterministic | data-quality@1.0.0 | sim | sim | sim | sim | sim | sim |
| `equity_context` — Contexto de equidade e normalização | deterministic | equity-context@1.0.0 | sim | sim | sim | sim | sim | sim |
| `reputation` — Reputação por dimensão observada | deterministic | reputation-dimensions@1.0.0 | sim | sim | sim | sim | sim | sim |
| `seals` — Selos: regra pública, concessão e revogação | deterministic | seal-rules@1.0.0 | sim | sim | sim | sim | sim | sim |

## operação

| motor | natureza | versão | implemented | integrated | tested | E2E | security | observability |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `deadline_sweep` — Varredura de prazos | deterministic | deadline-sweep@1.0.0 | sim | sim | sim | n/a | n/a | sim |

## orientação

| motor | natureza | versão | implemented | integrated | tested | E2E | security | observability |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `firstrun` — Primeiro acesso: o que já existe e o que falta | deterministic | firstrun@1.0.0 | sim | sim | sim | sim | sim | sim |

## prontidão

| motor | natureza | versão | implemented | integrated | tested | E2E | security | observability |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `funding_readiness` — Prontidão de captação de uma solução | deterministic | — | sim | sim | sim | sim | sim | **NÃO** |
| `impacto_ready` — Estado verificável 'Projeto IMPACTO Ready' | deterministic | impacto-ready@1.0.0 | sim | sim | sim | sim | sim | **NÃO** |
| `readiness` — Prontidão da organização e do projeto | deterministic | readiness@1.0.0 | sim | sim | sim | sim | sim | sim |

## rede

| motor | natureza | versão | implemented | integrated | tested | E2E | security | observability |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `today_cards` — Para você hoje (cartões e contadores do menu) | deterministic | — | sim | sim | sim | sim | sim | **NÃO** |

## soluções

| motor | natureza | versão | implemented | integrated | tested | E2E | security | observability |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `intent_parser` — Interpretação de intenção de busca | deterministic | intent-parser@1.0.0 | sim | sim | sim | sim | sim | **NÃO** |
| `solution_adaptation` — Adaptação de solução a outro território | deterministic | adaptation@1.0.0 | sim | sim | sim | sim | sim | sim |
| `solution_combine` — Combinação de soluções | deterministic | combine@1.0.0 | sim | sim | sim | sim | sim | sim |
| `solution_scoring` — Pontuação de solução | deterministic | — | sim | sim | sim | n/a | n/a | **NÃO** |

## vocabulário

| motor | natureza | versão | implemented | integrated | tested | E2E | security | observability |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `glossary_drift` — Detector de divergência de vocabulário | deterministic | — | sim | sim | sim | sim | sim | **NÃO** |

