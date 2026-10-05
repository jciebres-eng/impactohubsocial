# Estratégia de testes (alvo)

| Tipo | Foco |
|---|---|
| Unit | match (pesos, bloqueios, dado ausente), regras fiscais, entitlements, vouchers |
| Property-based | elegibilidade, soma de alocações ≤ orçamento |
| Integração/API | autenticação, RLS, storage, webhooks de billing |
| Permissões | acesso cruzado entre tenants/OSCs/prestadores (negativos) |
| Concorrência | resgate simultâneo de voucher; compromissos simultâneos |
| Segurança | upload malicioso, brute-force de voucher, injeção, prompt injection |
| Invariantes | `no_plan_affects_match`, `provider_search_rank_invariance`, regra fiscal expirada nunca ativa |
| E2E | cadastro → programa → candidatura → decisão → evidência → relatório; assinatura + voucher |
| Acessibilidade/Performance | WCAG, orçamento de bundle, carga |
| Operação | restore de backup, tabletop de incidente |
| IA | amostra rotulada, viés por porte/território/causa |

Dados: sintéticos primeiro; reais somente de-identificados e consentidos. Critério: nenhum teste crítico falhando para marcar GREEN.
