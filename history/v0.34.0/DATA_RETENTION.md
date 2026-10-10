# Retenção de dados — Impacto Trust (política v1.0)

> Gerado por `python3 -m impacto.core.retention` contra o banco real. Não edite à mão.

CLASSIFICAÇÃO DE RETENÇÃO. Para cada tabela com vínculo a organização ou a titular, diz o que acontece quando a conta é excluída e por quê. A origem da verdade é o banco: a classe declarada aqui é CONFERIDA contra a regra real da chave estrangeira por tests/test_v0190_lgpd_deletion.py. Declarar uma coisa e o banco fazer outra reprova.

Conferido em 2026-10-07 · 194 vínculos a organização ou titular.

## Classes

| classe | ação da chave | o que acontece | base |
| --- | --- | --- | --- |
| `deletable_with_parent` | `c` | A linha morre junto com a organização ou o titular (ON DELETE CASCADE). É o padrão. | Dado operacional sem obrigação de guarda própria. |
| `anonymizable` | `n` | A linha SOBREVIVE sem o vínculo (ON DELETE SET NULL): o registro continua, o apontamento para a pessoa ou a organização cai. | O registro tem valor coletivo (histórico de evento, trilha de uso, aceite) e deixa de ser pessoal quando perde o vínculo. |
| `retainable` | `a|r` | A linha IMPEDE a remoção do pai (NO ACTION/RESTRICT). Exclusão só acontece depois de tratar esses registros de forma explícita. | Obrigação legal de guarda (financeiro, fiscal) ou integridade que não pode ser desfeita em silêncio (evidência, revogação de assinatura, responsabilidade designada). |
| `audit_only` | `none` | Guarda o identificador SEM chave estrangeira, de propósito, para que a trilha sobreviva à remoção do registro de origem. | Trilha de auditoria precisa resistir à exclusão do que ela audita; com FK em cascata, apagar o objeto apagaria a prova de que ele existiu. |
| `append_only` | `c + gatilho append-only` | A chave diz CASCADE, mas a tabela tem gatilho append-only (forbid_mutation) que recusa DELETE — inclusive para o papel proprietário do banco, porque gatilho não olha papel. Na prática a linha é INDELÉVEL e, com ela, a organização também. | Trilha que sustenta o que terceiros leram: conferência de alegação, revisão, retrato de reputação, concessão e revogação de selo, decisão registrada. Apagar seria reescrever o passado que outra organização usou para decidir. |

## Distribuição real

| classe | vínculos |
| --- | --- |
| `anonymizable` | 21 |
| `append_only` | 19 |
| `audit_only` | 3 |
| `deletable_with_parent` | 138 |
| `retainable` | 13 |

Regra padrão: Toda coluna org_id/user_id que não esteja declarada abaixo DEVE ser deletable_with_parent (CASCADE). Uma coluna nova que não seja cascata reprova o teste: é exatamente assim que uma obrigação de guarda, ou um bloqueio de exclusão, entra sem ninguém decidir.

## Vínculos declarados

| vínculo | classe | ação real | motivo |
| --- | --- | --- | --- |
| `ai_budgets.org_id` | `retainable` | `a` | Orçamento de IA é decisão comercial da organização e sustenta a conferência de cobrança: quanto a organização autorizou gastar num mês é o que explica a fatura daquele mês. Some com a organização, não com a pessoa. |
| `ai_credit_ledger.org_id` | `retainable` | `a` | Razão de crédito de IA: o saldo é a SOMA dos lançamentos, então apagar um lançamento mudaria o saldo sem deixar rastro. A tabela é append-only por gatilho e o vínculo é NO ACTION — some com a organização por decisão explícita, nunca em cascata. Concessão, consumo e devolução são fatos sobre a ORGANIZAÇÃO. |
| `ai_usage.user_id` | `anonymizable` | `n` | Contabilidade de uso de IA é agregada; perde o vínculo e continua somando. |
| `audit_events.org_id` | `audit_only` | `none` | Trilha de auditoria sem FK de propósito: apagar a organização não pode apagar a prova do que ela fez. |
| `billable_events.org_id` | `append_only` | `c` | Evento faturável: base do que foi cobrado. Append-only por obrigação de prestação de contas. |
| `claims.org_id` | `deletable_with_parent` | `c` | A linha da alegação é removível (o gatilho claim_statement_frozen congela o TEXTO, não impede remoção). Mas a trilha filha claim_checks é append-only, então na prática a remoção falha no filho — o que mantém a conclusão: a organização não é removível. |
| `conflict_declarations.org_id` | `retainable` | `a` | Declaração de conflito de interesse protege decisão de outras partes. |
| `conflict_declarations.user_id` | `retainable` | `a` | Mesma razão: a declaração é sobre uma decisão, não sobre o perfil. |
| `course_certificates.org_id` | `anonymizable` | `n` | Certificado emitido continua verificável pelo código. |
| `course_enrollments.org_id` | `anonymizable` | `n` | Matrícula vira registro histórico sem vínculo. |
| `credential_verifications.org_id` | `append_only` | `c` | Conferência de credencial: alguém assumiu a verificação, com data. |
| `demo_requests.org_id` | `anonymizable` | `n` | Pedido de demonstração é contato comercial. |
| `demo_requests.user_id` | `anonymizable` | `n` | Idem. |
| `diagnosis_versions.org_id` | `append_only` | `c` | Versão de diagnóstico: o histórico é o que permite comparar antes e depois. |
| `domain_events.org_id` | `append_only` | `c` | Fato de domínio registrado; a trilha é o que reconstrói a história. |
| `eligibility_evaluations.org_id` | `append_only` | `c` | Conferência de elegibilidade lida por quem decidiu. |
| `equity_assessments.org_id` | `append_only` | `c` | Avaliação de equidade registrada com método e data. |
| `equity_contexts.org_id` | `deletable_with_parent` | `c` | Contexto declarado é do projeto da organização. |
| `equity_denominators.org_id` | `deletable_with_parent` | `c` | Denominador declarado pela organização sai com ela; denominador de território é bem comum e tem org_id nulo. |
| `evidences.org_id` | `retainable` | `a` | Evidência sustenta medição e alegação de terceiros; remover orfanaria o que foi validado. |
| `expenses.org_id` | `retainable` | `a` | Despesa com comprovante. Base de prestação de contas a quem financiou. |
| `framework_mappings.org_id` | `deletable_with_parent` | `c` | Mapeamento declarado pela organização. |
| `hub_event_registrations.org_id` | `anonymizable` | `n` | Inscrição em evento vira contagem histórica. |
| `kb_events.user_id` | `audit_only` | `none` | Trilha de uso da central de conhecimento, sem FK. |
| `kb_feedback.org_id` | `anonymizable` | `n` | Retorno sobre conteúdo tem valor coletivo e deixa de ser pessoal sem o vínculo. |
| `ledger_entries.org_id` | `retainable` | `a` | Lançamento contábil. Guarda obrigatória; apagar reescreveria o histórico financeiro. |
| `legal_acceptances.org_id` | `anonymizable` | `n` | A prova de aceite sobrevive por obrigação legal; o gatilho acceptance_anonymize_only() permite apenas limpar IP e agente. |
| `match_feedback.org_id` | `append_only` | `c` | Retorno das duas pontas sobre o match; apagar reescreveria o que a outra parte disse. |
| `materiality_assessments.org_id` | `deletable_with_parent` | `c` | Avaliação de materialidade é da organização. |
| `organization_qualification_events.org_id` | `audit_only` | `none` | Histórico de qualificação institucional, sem FK. |
| `partnership_requests.org_id` | `anonymizable` | `n` | Pedido de parceria envolve duas partes; a outra conserva o registro. |
| `partnership_requests.user_id` | `anonymizable` | `n` | Idem. |
| `price_change_notices.org_id` | `append_only` | `c` | Aviso de reajuste: prova de que a mudança foi comunicada. |
| `privileged_access_log.user_id` | `anonymizable` | `n` | Trilha de acesso PRIVILEGIADO, inclusive de leitura. Precisa sobreviver à exclusão da conta de quem foi registrado: a pergunta de uma investigação é "quem olhou a receita na semana do vazamento?", e ela deixaria de ter resposta justamente quando a pessoa apagasse a própria conta. ON DELETE SET NULL mantém a linha e derruba o apontamento — o que já basta, porque a trilha também guarda os papéis usados, a rota e o momento. |
| `professional_experiences.org_id` | `anonymizable` | `n` | Experiência declarada perde o vínculo com a organização encerrada. |
| `professional_services.user_id` | `anonymizable` | `n` | Serviço anunciado perde o vínculo com o titular. |
| `project_barriers.org_id` | `deletable_with_parent` | `c` | Barreira é atributo do contexto do projeto. |
| `project_snapshots.org_id` | `append_only` | `c` | Retrato do projeto num instante; é o que sustenta comparação longitudinal. |
| `project_transitions.org_id` | `append_only` | `c` | Transição de estado do projeto, com autor e data. |
| `readiness_snapshots.org_id` | `append_only` | `c` | Retrato de prontidão: a série temporal é a informação. |
| `report_responses.org_id` | `append_only` | `c` | Manifestação de quem foi denunciado. A tabela é append-only por gatilho (v0.20.0, migração 0038): o que a parte respondeu na apuração NÃO se apaga, porque é a prova de que ela teve direito de resposta. Se pudesse ser removida, a plataforma perderia exatamente o registro que a protege de ter decidido sem ouvir. |
| `reputation_disputes.org_id` | `append_only` | `c` | Contestação acompanha a organização contestante. A trilha é append-only: o gatilho recusa remoção, então a organização também não é removível enquanto houver linha aqui. |
| `reputation_snapshots.org_id` | `append_only` | `c` | Retrato de reputação é derivado; sem a organização não tem sujeito. A trilha é append-only: o gatilho recusa remoção, então a organização também não é removível enquanto houver linha aqui. |
| `responsibility_assignments.org_id` | `append_only` | `c` | A designação é da organização, e a trilha é append-only: responsabilidade registrada não se apaga. |
| `responsibility_assignments.user_id` | `retainable` | `r` | Responsabilidade designada não se transfere em silêncio: a remoção do titular é recusada enquanto houver mandato. |
| `seal_awards.org_id` | `append_only` | `c` | Selo concedido a uma organização que deixa de existir não tem portador. A trilha é append-only: o gatilho recusa remoção, então a organização também não é removível enquanto houver linha aqui. |
| `seal_evaluations.org_id` | `append_only` | `c` | Avaliação de critério acompanha a organização avaliada. A trilha é append-only: o gatilho recusa remoção, então a organização também não é removível enquanto houver linha aqui. |
| `sessions.org_id` | `anonymizable` | `n` | Sessão é revogada e tem IP e agente limpos na exclusão da conta. |
| `signature_revocations.org_id` | `retainable` | `a` | Revogação de assinatura é prova de que algo deixou de valer. Nunca desaparece. |
| `signed_agreement_parties.user_id` | `anonymizable` | `n` | Parte de acordo assinado: o acordo permanece, o apontamento pessoal cai. |
| `solution_adaptations.user_id` | `retainable` | `a` | Adaptação publicada é contribuição para a rede; sobrevive por integridade do que outros replicaram. |
| `solution_combinations.user_id` | `retainable` | `a` | Idem adaptação. |
| `solution_events.user_id` | `anonymizable` | `n` | Evento de solução vira histórico sem autor. |
| `solution_intents.user_id` | `retainable` | `a` | Intenção registrada em negociação entre partes. |
| `solution_people.org_id` | `anonymizable` | `n` | Pessoa ligada a solução perde o vínculo. |
| `solution_people.user_id` | `anonymizable` | `n` | Idem. |
| `solution_reviews.user_id` | `retainable` | `a` | Avaliação lida por terceiros ao decidir replicar. |
| `solution_search_log.user_id` | `anonymizable` | `n` | Registro de busca perde o vínculo e continua servindo a métrica agregada. |
| `support_tickets.org_id` | `anonymizable` | `n` | Atendimento permanece para histórico de suporte. |
| `trial_claims.org_id` | `anonymizable` | `n` | Controle de uso de teste gratuito, para impedir reuso indevido. |
| `trust_events.org_id` | `append_only` | `c` | Evento de confiança (verificação, assinatura, revogação) lido por terceiros. |
| `value_events.org_id` | `append_only` | `c` | Evento de valor entregue, base do ledger de valor. |

## Exclusão de conta

Rota: `POST /v1/privacy/delete-account`

**O que faz:**

* exige senha e confirmação (reautenticação)
* recusa quando o titular é o único proprietário de organização com outras pessoas (409 transfer_ownership_first)
* fecha a organização quando o titular é o único membro (status closed), sem apagar o histórico dela
* anonimiza users: e-mail substituído, nome trocado, senha e segredo de MFA removidos
* revoga sessões e limpa IP e agente de usuário
* apaga auth_tokens
* limpa IP e agente dos aceites legais, mantendo a prova (gatilho acceptance_anonymize_only)
* registra privacy_requests(kind=deletion, status=completed) e evento de auditoria

**O que NÃO faz:**

* não apaga a organização nem o histórico institucional dela: organização é pessoa jurídica e seus registros servem a terceiros (quem financiou, quem revisou, quem replicou)
* não apaga trilha de auditoria nem registro financeiro
* não remove a linha da organização: além das guardas legais (evidência, financeiro), a camada de impacto é append-only e recusa remoção — e é essa a decisão de arquitetura, não um efeito colateral

## Divergências encontradas na conferência

Nenhuma: cada vínculo declarado é o que o banco implementa, e todo vínculo não declarado é cascata.
