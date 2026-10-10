# Matriz de riscos — jurídicos, fiscais, financeiros e de segurança (v0.34.0)

> Probabilidade/impacto são juízo da equipe, não medição. "Mitigação no código" é o que existe e tem teste; "mitigação
> pendente" depende de pessoa, contrato ou parecer. Nada aqui afirma invulnerabilidade: todo sistema ligado à internet pode ser atacado, e este não é exceção.

| # | Categoria | Risco | Prob. | Impacto | Mitigação no código (teste) | Mitigação pendente | Dono |
|---|---|---|---|---|---|---|---|
| J1 | Jurídico | Plataforma enquadrada como participante de arranjo de pagamento / custódia | média | alto | nenhuma coluna de saldo; nenhum repasse; split e retenção recusados na configuração (`test_v0330.test_10`, `test_v0340.test_11`, `test_v0220_financial_engine`) | parecer sobre o modelo de titularidade (conta do beneficiário no provedor) | jurídico |
| J2 | Jurídico | Taxa cobrada sem base contratual/legal | baixa | alto | regras INATIVAS; portão do banco (carta verde + validada); obrigação só devida por gatilho auditável (`test_v0340.test_02/03`) | parecer; contrato/termos | jurídico |
| J3 | Jurídico | Dedução de taxa de recurso público sem previsão no instrumento | média | alto | origem pública → `exempt` por padrão; elegível só com instrumento + autorização `finance.approve` (`test_05`) | análise por instrumento/ente/despesa (MROSC, convênios, Lei 14.133) | jurídico |
| J4 | Jurídico/LGPD | Dados do doador exigidos pelo provedor (CPF, e-mail) sem base legal | média | médio | e-mail cifrado; anônimo nunca exposto; bruto do webhook redigido (`test_v0330.test_03/05`) | registro de operações; aviso de privacidade; escolha de provedor | DPO |
| J5 | Jurídico | Comprovante tomado por recibo dedutível | média | médio | texto explícito "não é recibo dedutível" (`test_v0330.test_03`) | parecer contábil; modelo por tipo de beneficiário | contábil |
| J6 | Jurídico | Plataforma reter prestação de contas para forçar pagamento (vedado) | baixa | alto | ADR-381: varredura de rotas (`test_v0340.test_11`); `never_blocks` na política | — | — |
| J7 | Jurídico | "Reserva" entendida como custódia/rendimento | baixa | alto | ADR-380: destinação contábil; motor `success_fee` inativável (`test_v0340._set_rule_active` prova o portão) | redação dos termos | jurídico |
| F1 | Fiscal | Documento fiscal errado por tipo de receita (doação × serviço × patrocínio × aporte) | alta | médio | cartas legais por regra com `tax_notes`/`invoice_notes` | NFS-e (não implementada); parecer por receita | contábil |
| F2 | Fiscal | ISS/retenções em serviços profissionais do marketplace | média | médio | `marketplace.take_rate` recusada; contratos registrados | enquadramento por serviço | contábil |
| $1 | Financeiro | Reconhecer receita calculada como recebida | baixa | alto | estados separados; `platform_revenue_view` nunca soma (`test_04`) | — | — |
| $2 | Financeiro | Estorno/chargeback depois de taxa recebida | média | médio | obrigação → `disputed` com motivo (`reverse_for_source`) | processo com o provedor (prazos, quem avisa) | operação |
| $3 | Financeiro | Tíquete baixo × tarifa fixa do provedor torna a taxa negativa/irrelevante | alta | médio | tarifa por tabela congelada; modelo 24m mostra | contrato com o provedor; mínimo por doação | responsável |
| $4 | Financeiro | Inadimplência das faturas próprias | média | médio | `overdue` sem bloqueio; disputa; dispensa; teto de 5 % do liquidado | política de cobrança | financeiro |
| $5 | Financeiro | Divergência razão × provedor não vista | média | alto | fila de exceções tipada; índice único; `unreconciled_overdue` (`test_08`) | rotina periódica no worker (não agendada ainda) | operação |
| S1 | Segurança | Webhook forjado | baixa | alto | HMAC obrigatório; 404 sem segredo; 202 sem efeito (`test_v0330.test_03`) | validação temporal no adaptador real | engenharia |
| S2 | Segurança | Replay/duplicidade de eventos | baixa | alto | UNIQUE `(provider,event_id)`; concorrência provada (`test_v0340.test_10`) | — | — |
| S3 | Segurança | Cliente altera valor/estado/taxa | baixa | alto | esquema recusa campo extra (422); valor conferido no webhook (`test_10`, `test_v0330.test_04`) | — | — |
| S4 | Segurança | Acesso a painel financeiro de outra organização | baixa | alto | RLS + `require_campaign_owner` → 404 (`test_07`, `test_v0330.test_05`) | — | — |
| S5 | Segurança | Decisão financeira crítica sem segregação | baixa | alto | liquidar/decidir/dispensar/autorizar público exigem `finance.approve` + step-up (`test_04/05`) | — | — |
| S6 | Segurança | Snapshot do provedor adulterado (ferramenta de operação) | média | médio | só `finance.write`; trilha por execução; exceções nunca "fecham" doação sem evento assinado | adaptador real consulta a API | engenharia |
| O1 | Operacional | Fila de webhooks do provedor pausada (Asaas: 15 falhas) | média | alto | 200 em aplicado/duplicado; 202 em assinatura inválida | monitor do provedor | operação |
| O2 | Operacional | Sandbox tomado por produção | baixa | alto | `is_simulated` derivado por gatilho; aviso na página; `LIVE_PAYMENT_PROVIDER_ENABLED` recusado | — | — |
