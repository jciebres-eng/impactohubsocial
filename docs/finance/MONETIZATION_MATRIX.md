# Matriz de monetização por perfil, operação, pagador e evento de cobrança (v0.34.0)

> Classificação honesta de cada oportunidade do pacote (PARTE VII e XII). "Implementado" quer dizer: existe no código, com teste.
> "Receita" aqui é sempre HIPÓTESE: nenhuma regra está ativa. O modelo de 24 meses (`modelo_24m/`) usa os mesmos itens.
> Prioridade segue a recomendação estratégica do responsável: **não depender só das taxas sobre doações; monetizar o valor
> operacional, financeiro e institucional entregue a quem pode pagar; proteger as organizações pequenas.**

Legenda da classificação: **AGORA** (implementar agora — feito nesta versão como infraestrutura, inativo) · **PREPARAR** (arquitetura
pronta, ativar depois) · **COMERCIAL** (validar comercialmente) · **JURÍDICO** (validar juridicamente antes) · **NÃO** (não implementar
nas condições atuais).

| Oportunidade | Pagador | Valor entregue | Evento de cobrança | Modelo de preço (hipótese) | Custo direto | Risco | Prioridade | Classificação | Estado no código |
|---|---|---|---|---|---|---|---|---|---|
| Taxa de serviço sobre doação comunitária | organização beneficiária (ou doador por contribuição voluntária explícita) | página pública, QR, confirmação, razão, comprovante, prestação de contas | doação LIQUIDADA acima da franquia, após aviso | 1 % (100 bps), `enterprise`, faturada à parte | tarifa do provedor é do beneficiário; suporte | tíquete baixo × tarifa fixa; parecer; LGPD do doador | média | **JURÍDICO** | implementado: cálculo, obrigação, gatilho, fatura própria — regra INATIVA |
| Contribuição voluntária do doador para a plataforma (ADR-384) | doador, por escolha | manutenção da plataforma, sem tirar nada da causa | doação confirmada com contribuição informada antes de pagar | valor livre, começa em R$ 0, teto = menor entre o valor doado e R$ 500; separada no total | tarifa sobre o valor a mais | indução enganosa (vedada: nunca sugerida nem pré-marcada); natureza tributária | média | **PREPARAR + JURÍDICO** | implementado (E6): campo só com a regra ativa; obrigação devida; split SIMULADO testado; sem split, fatura à organização — regra `donation.platform_contribution` INATIVA |
| Taxa sobre aporte institucional (campanha `institutional_fund`) | financiador institucional (empresa/fundação) por contrato | originação, triagem, due diligence documental, acompanhamento | aporte confirmado + gatilho | 3,5 % (350 bps), `enterprise`, faturada à parte | suporte, análise | enquadramento; recurso público isento salvo instrumento | alta | **JURÍDICO** | regra `donation.institutional_fee` INATIVA; obrigação por doação com `funding_source` |
| Reserva institucional do beneficiário | — (não é receita da plataforma) | transparência da reserva ao financiador | — | 1,5 % destinação contábil | — | confundir com custódia (vedado) | — | **NÃO (como receita)** | regra no motor `success_fee`, inativável por desenho |
| Taxa de serviço do acordo de financiamento | pagador definido no acordo | matriz de distribuição imutável, instrução de repasse, conciliação | acordo ativado e quitado | 3,5 %, `contract.platform_service_fee` | — | parecer | alta | **JURÍDICO** | implementado na v0.26/0.27, INATIVO |
| Marketplace de serviços profissionais (ex.: R$ 1.000, 90/10) | contratante | catálogo, proposta, aceite, entregáveis, evidências, disputa | contrato registrado e evidência de pagamento | 10 % sobre contrato REGISTRADO, fatura própria (sem custódia) | suporte a disputas | ADR-022; tributos; CDC; regras profissionais | média | **JURÍDICO + COMERCIAL** | propostas/acordos/honorários existem; `marketplace.take_rate` RECUSADA pelo responsável; liberação por entregável NÃO (custódia) |
| Serviços premium de campanha (comunicação, análise, relatórios, gestão de doadores) | organização | ferramentas além do essencial | assinatura de módulo/uso | por uso ou módulo | IA, suporte | assinatura contraria ADR-341; LGPD (gestão de doadores) | média | **COMERCIAL** | não implementado; essencial é gratuito |
| Licenças corporativas / ESG / portfólio / due diligence | empresa | portfólio, matching contextual, relatórios rastreáveis, comparação meta×execução, due diligence | contrato anual | contrato (`enterprise`) | análise, suporte | prometer impacto garantido (vedado); matching íntegro | alta | **COMERCIAL** | torre, relatórios e matching existem; `enterprise.esg_portfolio` INATIVA |
| Governos: editais, convênios, diagnósticos, prestação de contas, painéis | ente público por contratação própria | gestão de editais, diagnóstico territorial, prestação de contas, auditoria | contrato (Lei 14.133) | licença/contrato, nunca dedução de repasse | implantação, suporte | contratação pública; `b2g` RECUSADO como mecanismo de taxa | média | **JURÍDICO** | funcionalidades existem; cobrança por instrumento próprio; taxa sobre repasse NÃO |
| Banco de Ideias: diagnóstico avançado, prontidão, documentos assistidos | promotor (quando pode pagar) | assistência para virar projeto | operação entregue | créditos de IA / serviço | IA | cobrar de vulnerável (vedado); submissão inicial gratuita | baixa | **PREPARAR** | submissão e avaliação inicial gratuitas; créditos de IA existem |
| Créditos pré-pagos de operações de IA | organização | relatórios, diagnósticos, documentos, análises | operação ENTREGUE (não a tentativa) | `ai.credits_prepaid` (R$ 0,10/crédito, piloto) | custo do modelo | cobrar operação não entregue (vedado) | alta | **PREPARAR** | implementado na v0.28 (cotas, créditos, medição, falhas) — venda em modo piloto |
| Assinaturas por perfil | organização/financiador/empresa/prestador/governo | planos | mensal | — | — | ADR-341 (não existe assinatura); vantagem indevida no matching (vedado) | — | **NÃO** (decisão vigente) | removido na v0.27.0; só por decisão do responsável |
| Licenças de API / integrações / implantação / suporte especializado | empresa/governo | integração com sistemas próprios, implantação, suporte | contrato | contrato (`implementation.setup`) | engenharia | — | média | **COMERCIAL** | `implementation.setup` INATIVA; hub de integrações existe |
| Relatórios institucionais sob demanda / análise de risco de projetos | financiador/empresa | relatório rastreável | entrega | por relatório | análise | vender declarado como verificado (vedado) | média | **COMERCIAL** | relatórios e dossiê existem; cobrança não |
| Capacitação e certificações próprias | pessoas/organizações | cursos | inscrição | por curso | conteúdo | estrutura legítima para certificar | baixa | **JURÍDICO** | cursos e certificado de conclusão existem; cobrança não |

## Mecanismos de garantia de receita (pacote PARTE IX) — situação

| Mecanismo | Estado |
|---|---|
| Identificadores exclusivos de transação/operação | ✅ `donations.id`, `provider_charge_id`, `event_id` único por provedor |
| Contrato e versão de tarifa vinculados à operação | ✅ `fee_rule_version_id` congelado; `policy_version_id` na obrigação |
| Cálculo determinístico | ✅ `apply_bps` (Decimal, arredondamento declarado); conciliação acusa `fee_miscalculated` |
| Split automático | 🟡 só para a contribuição voluntária do doador (nada sai da doação, ADR-384); caminho testado com provedor SIMULADO (`test_v0340_open_scenarios.test_14_15`); `split_enabled = false` recusado na configuração até contrato e homologação |
| Faturamento sem split | ✅ `invoice` → `platform_charges` (manual/sandbox) |
| Registro de obrigações | ✅ `remuneration_obligations` + eventos |
| Conciliação com o provedor | ✅ `run_for_campaign` com snapshot; sandbox deriva dos eventos assinados; periódica pela rotina `financial_ops` (E6) |
| Alertas de divergência | ✅ fila de exceções tipada com prioridade |
| Recursos recebidos externamente | ✅ `external_resources` (nunca receita) |
| Auditoria de operações e exceções | ✅ `audit_log` (categorias novas) + históricos só-inserção |
| Inadimplência | ✅ `overdue` sem bloqueio; disputa; dispensa; rotina `financial_ops` marca vencidas a cada ciclo (E6) |
| Reembolso do que a plataforma recebeu | ✅ integral com `finance.approve` (parcial é ajuste); devolução da cobrança pelo provedor reverte a obrigação; organização não move a própria fatura (E6) |
| Indicadores prevista × faturada × recebida × líquida | ✅ `platform_revenue_view` (nunca somados) |
| Isenções, descontos, ajustes | ✅ `exempt`, `waived`, autorização por instrumento; ajuste = obrigação nova |
| Aprovação segregada | ✅ liquidar/decidir/dispensar/autorizar exigem `finance.approve` |
| Proteção contra tarifa retroativa | ✅ gatilho do banco; `test_09` |
