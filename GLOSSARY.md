# Glossário oficial — Impacto Trust v1.0

> Gerado por `scripts/sync_glossary.py` a partir de `config/glossary.json`. Não edite à mão.

VOCABULÁRIO OFICIAL do Impacto Trust. Este arquivo é a origem: o rótulo que a interface mostra, o termo que a API devolve e o texto de ajuda têm de sair daqui. Os rótulos são sincronizados para config/i18n.json (e de lá para a tabela translations) por scripts/sync_glossary.py. A definição em pt-BR é para quem desenha e para quem escreve texto de ajuda — não é texto de tela.

Idioma de origem: **pt-BR** · Idiomas: pt-BR, en, es

## Como ler

| Coluna | O que é |
| --- | --- |
| chave | o valor que a API devolve e o banco guarda |
| pt-BR / en / es | o rótulo que a interface mostra. Não invente sinônimo em tela |
| definição | para quem desenha e para quem escreve ajuda. Não é texto de tela |

## Situação da alegação

`claim_status` · aparece em: GET /v1/claims, GET /v1/claims/{id} — campo status (derivado, não armazenado)

> A situação é DERIVADA das conferências e revisões; não existe coluna de status que alguém possa editar.

| chave | pt-BR | en | es | definição |
| --- | --- | --- | --- | --- |
| `unchecked` | não verificada | not checked | no verificada | A alegação foi declarada e ainda não passou por nenhuma rodada de conferência automática. |
| `substantiated` | sustentada pelo que está registrado | supported by the record | sustentada por lo registrado | Nenhuma regra apontou problema: o texto encontra apoio nas medições, evidências e documentos já registrados. Não significa auditada nem certificada. |
| `attention` | pontos de atenção | points of attention | puntos de atención | As regras encontraram fragilidades de redação ou de base que não impedem a publicação, mas que um leitor atento vai questionar. |
| `flagged` | marcada — exige revisão humana de outra organização | flagged — needs human review by another organization | marcada — requiere revisión humana de otra organización | Pelo menos uma regra grave foi acionada. A marca só sai com revisão feita por pessoa de OUTRA organização, convidada para a rodada. |
| `flagged_accepted_by_review` | marcada e aceita em revisão, com a marca mantida | flagged and accepted in review, flag kept | marcada y aceptada en revisión, con la marca mantenida | Um revisor externo aceitou a alegação, mas a marca permanece visível: a aceitação humana não apaga o apontamento automático. |
| `needs_change` | revisão pediu alteração | review requested changes | la revisión solicitó cambios | Um revisor externo analisou e devolveu pedindo alteração no texto ou na base. |
| `rejected_by_review` | recusada em revisão | rejected in review | rechazada en revisión | Um revisor externo recusou a alegação. A recusa fica registrada de forma permanente. |
| `withdrawn` | retirada por quem a declarou | withdrawn by the declarant | retirada por quien la declaró | A própria organização retirou a alegação. O histórico da retirada permanece. |

## Tipo de alegação

`claim_kind` · aparece em: POST /v1/claims — campo claim_kind

| chave | pt-BR | en | es | definição |
| --- | --- | --- | --- | --- |
| `result` | resultado | result | resultado | Afirmação sobre um resultado alcançado pelo projeto ou programa. |
| `ods_contribution` | contribuição a ODS | SDG contribution | contribución a los ODS | Afirmação de que o trabalho contribui para um Objetivo de Desenvolvimento Sustentável. |
| `esg` | ASG | ESG | ASG | Afirmação relativa a desempenho ambiental, social ou de governança. |
| `environmental` | ambiental | environmental | ambiental | Afirmação sobre efeito ambiental. |
| `social` | social | social | social | Afirmação sobre efeito social. |
| `governance` | governança | governance | gobernanza | Afirmação sobre práticas de governança da organização. |
| `efficiency` | eficiência | efficiency | eficiencia | Afirmação sobre custo por resultado, produtividade ou aproveitamento de recurso. |
| `financial` | financeira | financial | financiera | Afirmação sobre valores aplicados, captados ou economizados. |
| `comparative` | comparativa | comparative | comparativa | Afirmação que se compara a outras organizações, projetos ou médias. |
| `certification` | certificação | certification | certificación | Afirmação de que algo é certificado, homologado ou reconhecido oficialmente. |

## Gravidade do apontamento

`claim_severity` · aparece em: GET /v1/claims/{id} — checks[].severity; catálogo claim_rules.severity

| chave | pt-BR | en | es | definição |
| --- | --- | --- | --- | --- |
| `info` | informação | information | información | Observação registrada para quem lê; não altera a situação da alegação. |
| `attention` | atenção | attention | atención | Fragilidade real que um leitor crítico vai apontar. Leva a alegação para 'pontos de atenção'. |
| `serious` | grave | serious | grave | Problema que impede sustentar a alegação sem revisão humana externa. Leva a alegação para 'marcada'. |

## Decisão da revisão

`claim_review_decision` · aparece em: POST /v1/claims/{id}/reviews — campo decision

| chave | pt-BR | en | es | definição |
| --- | --- | --- | --- | --- |
| `accepted` | aceita | accepted | aceptada | O revisor externo considera a alegação sustentável. Se havia marca grave, a marca permanece visível. |
| `needs_change` | pede alteração | changes requested | solicita cambios | O revisor devolve para ajuste de texto, de base ou de período. |
| `rejected` | recusada | rejected | rechazada | O revisor conclui que a alegação não se sustenta com o que está registrado. |

## Banda de confiança

`reputation_band` · aparece em: GET /v1/reputation/{org} — dimensions[].band; coluna reputation_snapshots.band

> A banda qualifica a BASE do indício, não a qualidade da organização. Sem base suficiente não existe valor.

| chave | pt-BR | en | es | definição |
| --- | --- | --- | --- | --- |
| `high` | confiança alta | high confidence | confianza alta | Há observações suficientes e recentes para tratar o indício como estável. |
| `medium` | confiança média | medium confidence | confianza media | Há base, mas em quantidade ou atualidade que pede cautela na leitura. |
| `low` | confiança baixa — trate como indício | low confidence — treat as a hint | confianza baja — trátelo como indicio | A base é pequena ou antiga. O número serve para conversar, não para decidir. |
| `insufficient` (também: insufficient_data) | dados insuficientes — não é recomendação | insufficient data — not a recommendation | datos insuficientes — no es una recomendación | Não há observações suficientes para calcular. Nesta banda o valor é obrigatoriamente vazio — o banco recusa qualquer número. |

## Resultado da contestação de reputação

`reputation_dispute_outcome` · aparece em: POST /v1/reputation/disputes/{id}/resolve — campo outcome

| chave | pt-BR | en | es | definição |
| --- | --- | --- | --- | --- |
| `corrected` | corrigido | corrected | corregido | A contestação procedia e o dado de origem foi corrigido. |
| `partially_corrected` | corrigido em parte | partially corrected | corregido en parte | Parte do que foi contestado procedia e foi corrigida; o restante permanece. |
| `no_change` | sem alteração | no change | sin cambios | A análise não encontrou erro no dado de origem. A contestação continua registrada. |
| `needs_more_information` | falta informação | needs more information | falta información | Não foi possível concluir sem mais elementos de quem contestou. |

## Situação do selo concedido

`seal_status` · aparece em: GET /v1/seals/awards — status (derivado de seal_status())

| chave | pt-BR | en | es | definição |
| --- | --- | --- | --- | --- |
| `active` | ativo | active | activo | O selo está válido: não expirou, não foi revogado e a definição segue publicada. |
| `expired` | expirado | expired | expirado | Passou a data de validade do selo. Expirar não é revogar. |
| `revoked` | revogado | revoked | revocado | O selo foi retirado por um motivo registrado. |
| `superseded_definition` | definição superada por versão nova | definition superseded by a newer version | definición superada por una versión nueva | O selo foi concedido sob uma versão da definição que já tem substituta. O que foi concedido não muda. |
| `definition_retired` | definição aposentada | definition retired | definición retirada | A definição que originou o selo foi aposentada e não concede mais. |

## Motivo da revogação

`seal_revocation_reason` · aparece em: POST /v1/admin/seals/awards/{id}/revoke — campo reason

| chave | pt-BR | en | es | definição |
| --- | --- | --- | --- | --- |
| `criterion_no_longer_met` | critério deixou de ser satisfeito | criterion no longer met | el criterio dejó de cumplirse | O que sustentava o selo mudou: o critério conferido não vale mais. |
| `definition_retired` | definição aposentada | definition retired | definición retirada | A definição do selo saiu de uso. |
| `data_correction` | correção de dado | data correction | corrección de dato | Um dado usado na conferência estava errado e foi corrigido. |
| `request_of_holder` | pedido de quem recebeu | holder's request | a pedido de quien lo recibió | A própria organização pediu a retirada do selo. |
| `misconduct` | conduta | misconduct | conducta | Retirada por conduta apurada. O registro da revogação é permanente. |

## Situação da definição de selo

`seal_definition_status` · aparece em: GET /v1/seals/definitions — status

| chave | pt-BR | en | es | definição |
| --- | --- | --- | --- | --- |
| `draft` | rascunho | draft | borrador | Em elaboração: ainda pode ter critério alterado e não concede selo. |
| `published` | publicada | published | publicada | Em vigor e imutável: critérios não podem mais ser alterados, só aposentados por uma versão nova. |
| `retired` | aposentada | retired | retirada | Saiu de uso e não concede mais. Os selos já concedidos permanecem. |

## Abrangência do selo

`seal_scope` · aparece em: seal_definitions.scope, seal_awards.scope

| chave | pt-BR | en | es | definição |
| --- | --- | --- | --- | --- |
| `organization` | organização | organization | organización | O selo se refere à organização como um todo. |
| `project` | projeto | project | proyecto | O selo se refere a um projeto específico, não à organização. |

## Firmeza da declaração de contexto

`equity_standing` · aparece em: PUT /v1/projects/{id}/equity/context — additionality_standing; GET /v1/projects/{id}/equity

> Firmeza NÃO é nota: diz com que apoio a afirmação foi feita, não se ela é boa.

| chave | pt-BR | en | es | definição |
| --- | --- | --- | --- | --- |
| `declared` | declarada | declared | declarada | A organização afirmou, sem documento nem evidência anexada. Vale como declaração própria. |
| `documented` | documentada (documento no cofre ou fonte citada com data) | documented (document in the vault or a dated cited source) | documentada (documento en la bóveda o fuente citada con fecha) | A afirmação aponta para um documento guardado na plataforma ou para uma fonte externa com nome e data. |
| `evidenced` | evidenciada (evidência registrada) | evidenced (evidence on record) | evidenciada (evidencia registrada) | A afirmação tem evidência registrada na plataforma, com origem e data verificáveis. |

## Tipo de denominador

`equity_denominator` · aparece em: POST /v1/equity/denominators — kind; GET /v1/equity/denominators

> Sem denominador vigente com fonte, o número normalizado devolve 'indisponível' — nunca uma estimativa.

| chave | pt-BR | en | es | definição |
| --- | --- | --- | --- | --- |
| `eligible_population` | população elegível | eligible population | población elegible | Quantas pessoas se enquadram nos critérios do projeto no território. |
| `reference_population` | população de referência | reference population | población de referencia | População total do território usada como referência, de fonte oficial citada. |
| `households` | domicílios | households | hogares | Número de domicílios do território. |
| `enrolled` | matrículas ou cadastros | enrolled | matrículas o registros | Quantas pessoas estão matriculadas ou cadastradas no serviço. |
| `area_km2` | área em km² | area in km² | área en km² | Extensão territorial considerada. |
| `service_units` | unidades de serviço | service units | unidades de servicio | Equipamentos ou pontos de atendimento existentes no território. |
| `resource_cents` | recurso aplicado | resources applied | recurso aplicado | Valor efetivamente aplicado, em centavos, usado como denominador. |

## Método de normalização

`equity_method` · aparece em: GET /v1/projects/{id}/equity/normalization — method

> Número normalizado não é número absoluto, e a plataforma não converte um no outro.

| chave | pt-BR | en | es | definição |
| --- | --- | --- | --- | --- |
| `per_eligible_population` | por 1.000 pessoas da população elegível declarada | per 1,000 people in the declared eligible population | por 1.000 personas de la población elegible declarada | Divide o resultado medido pela população elegível e apresenta por mil pessoas. |
| `per_reference_population` | por 1.000 pessoas da população de referência do território | per 1,000 people in the territory's reference population | por 1.000 personas de la población de referencia del territorio | Divide o resultado pela população total do território, de fonte oficial. |
| `per_household` | por 1.000 domicílios | per 1,000 households | por 1.000 hogares | Divide o resultado pelo número de domicílios do território. |
| `per_enrolled` | por 100 matrículas ou cadastros do serviço | per 100 enrolments or registrations | por 100 matrículas o registros del servicio | Divide o resultado pelo número de pessoas matriculadas ou cadastradas. |
| `per_area_km2` | por km² do território | per km² of territory | por km² del territorio | Divide o resultado pela área do território. |
| `per_service_unit` | por unidade de serviço existente no território | per existing service unit in the territory | por unidad de servicio existente en el territorio | Divide o resultado pelo número de equipamentos ou pontos de atendimento. |
| `per_resource` | por R$ 1.000 aplicados | per BRL 1,000 applied | por R$ 1.000 aplicados | Divide o resultado pelo recurso aplicado e apresenta por mil reais. |

## Alcance da responsabilidade

`responsibility_scope` · aparece em: POST /v1/responsibility/assignments — scope

| chave | pt-BR | en | es | definição |
| --- | --- | --- | --- | --- |
| `organization` | organização | organization | organización | A pessoa responde pela organização inteira naquele papel. |
| `program` | programa | programme | programa | A responsabilidade vale para um programa. |
| `project` | projeto | project | proyecto | A responsabilidade vale para um projeto. |
| `document` | documento | document | documento | A responsabilidade vale para um documento específico e sua versão. |

## Relação com o referencial

`framework_relation` · aparece em: POST /v1/frameworks/mappings — relation

> A escada vai até 'auditado'. A plataforma NÃO é organismo certificador: 'certificado' é recusado pela API.

| chave | pt-BR | en | es | definição |
| --- | --- | --- | --- | --- |
| `aligned` | alinhado — o indicador conversa com o referencial, sem conferência | aligned — the indicator speaks to the framework, unchecked | alineado — el indicador dialoga con el referencial, sin verificación | Degrau mais baixo: alguém afirma que há afinidade temática, e ninguém conferiu. |
| `mapped` | mapeado — há correspondência declarada com um código do referencial | mapped — a declared correspondence to a framework code | mapeado — hay correspondencia declarada con un código del referencial | Existe correspondência explícita a um código, declarada por quem mapeou. |
| `assessed` | avaliado — alguém analisou a correspondência e registrou a análise | assessed — someone analysed the correspondence and recorded it | evaluado — alguien analizó la correspondencia y registró el análisis | A correspondência foi analisada e a análise ficou registrada, com autor e data. |
| `reported` | relatado — o número foi publicado citando o referencial, com fonte | reported — the figure was published citing the framework, with a source | reportado — el número fue publicado citando el referencial, con fuente | O número foi efetivamente publicado em relatório citando o referencial. |
| `verified` | verificado — conferido por revisor de OUTRA organização | verified — checked by a reviewer from ANOTHER organization | verificado — verificado por un revisor de OTRA organización | Uma pessoa de outra organização conferiu e assinou a conferência. |
| `audited` | auditado — conferido por auditoria independente, com registro | audited — checked by independent audit, on record | auditado — verificado por auditoría independiente, con registro | Degrau mais alto: auditoria independente, com registro de quem auditou e quando. |

## Lente de materialidade

`framework_lens` · aparece em: POST /v1/materiality/assessments — lens

| chave | pt-BR | en | es | definição |
| --- | --- | --- | --- | --- |
| `impact_only` | só impacto — quanto a organização afeta o mundo | impact only — how the organization affects the world | solo impacto — cuánto la organización afecta al mundo | Avalia apenas o efeito da organização para fora. |
| `financial_only` | só financeira — quanto o tema afeta a organização | financial only — how the topic affects the organization | solo financiera — cuánto el tema afecta a la organización | Avalia apenas o risco e a oportunidade que o tema traz para a organização. |
| `double` | dupla materialidade — os dois eixos | double materiality — both axes | doble materialidad — los dos ejes | Avalia os dois sentidos: o efeito para fora e o risco para dentro. |

## Origem da evidência

`evidence_source` · aparece em: Montagem de evidência (core/assembly.py) — provenance.source por campo

> A origem nunca é inferida da aparência do dado: ela é registrada no momento em que o dado entra.

| chave | pt-BR | en | es | definição |
| --- | --- | --- | --- | --- |
| `absent` | ausente | absent | ausente | Não há dado. Ausência não é zero nem falha: é desconhecido. |
| `declared` | declarada pela organização | declared by the organization | declarada por la organización | A própria organização informou, sem comprovação anexada. |
| `inferred` | inferida pela plataforma | inferred by the platform | inferida por la plataforma | Derivada de outros dados por regra explícita. Nunca se apresenta como verificada. |
| `platform_record` | registro da plataforma | platform record | registro de la plataforma | Produzida pelo próprio funcionamento da plataforma, com data e autor. |
| `official_catalog` | catálogo oficial | official catalogue | catálogo oficial | Vem de carga oficial com fonte e data registradas. |
| `signed_document` | documento assinado | signed document | documento firmado | Documento com assinatura registrada na plataforma, ligada a versão. |
| `verified_document` | documento verificado | verified document | documento verificado | Documento conferido por quem tem competência para conferir, com registro. |
| `verified_credential` | credencial verificada | verified credential | credencial verificada | Registro profissional ou habilitação conferida junto à fonte. |
| `validated_measurement` | medição validada | validated measurement | medición validada | Medição conferida por organização diferente de quem mediu. |

## Banda de confiança da evidência

`confidence_band` · aparece em: Diagnóstico, match e reputação — band

> Mesmo vocabulário em todas as telas: a banda fala da BASE, não do mérito.

| chave | pt-BR | en | es | definição |
| --- | --- | --- | --- | --- |
| `high` | confiança alta | high confidence | confianza alta | Base suficiente, recente e de origem forte. |
| `medium` | confiança média | medium confidence | confianza media | Base existente, com ressalva de quantidade ou de data. |
| `low` | confiança baixa — trate como indício | low confidence — treat as a hint | confianza baja — trátelo como indicio | Base fraca: serve para conversar, não para decidir. |
| `insufficient_data` (também: insufficient) | dados insuficientes — não é recomendação | insufficient data — not a recommendation | datos insuficientes — no es una recomendación | Sem base para calcular. Nesta banda não existe valor. |

## Origem da sugestão em formulário

`suggestion_origin` · aparece em: GET /v1/lookups/{key} — items[].origin; componente Suggest

> Toda sugestão diz de onde veio e nunca sobrescreve texto digitado sem confirmação.

| chave | pt-BR | en | es | definição |
| --- | --- | --- | --- | --- |
| `official_load` | carga oficial (com fonte e data) | official load (with source and date) | carga oficial (con fuente y fecha) | Vem de uma carga de dado oficial, com fonte e data registradas. |
| `platform_knowledge` | conhecimento da plataforma — conferir na carga oficial | platform knowledge — check against the official load | conocimiento de la plataforma — verificar en la carga oficial | A plataforma conhece o termo, mas ele não veio de carga oficial: precisa ser conferido. |
| `platform_editorial` | lista editorial da plataforma | platform editorial list | lista editorial de la plataforma | Redação e agrupamento são da plataforma, não classificação oficial de nenhum órgão. |
| `your_organization` | histórico da sua organização | your organization's history | historial de su organización | Vem do que a sua própria organização já registrou antes. |
| `another_organization` | declarado por outra organização | declared by another organization | declarado por otra organización | Outra organização declarou este valor. Serve como pista, não como verificação. |

## Prontidão

`readiness` · aparece em: GET /v1/diagnoses/{id}/analysis — readiness.{chave}

> Cada prontidão diz QUAIS dimensões olhou. Nenhuma é nota geral do projeto.

| chave | pt-BR | en | es | definição |
| --- | --- | --- | --- | --- |
| `project_readiness` | prontidão do projeto | project readiness | preparación del proyecto | Olha problema, território, solução, orçamento e medição. |
| `organization_readiness` | prontidão da organização | organization readiness | preparación de la organización | Olha identidade e governança. |
| `funding_readiness` | prontidão para captar | funding readiness | preparación para captar | Olha orçamento e conformidade. |
| `evidence_readiness` | prontidão de evidência | evidence readiness | preparación de evidencia | Olha problema e medição: há com o que sustentar o que se afirma? |
| `compliance_readiness` | prontidão de conformidade | compliance readiness | preparación de conformidad | Olha identidade e conformidade documental. |
| `data_readiness` | prontidão de dado | data readiness | preparación de datos | Olha problema, território e medição. |
| `governance_readiness` | prontidão de governança | governance readiness | preparación de gobernanza | Olha governança e conformidade. |
| `impact_readiness` | prontidão de impacto | impact readiness | preparación de impacto | Olha problema, território e medição — o que permite falar de impacto sem confundir com alcance. |

## Situação da prontidão

`readiness_status` · aparece em: GET /v1/diagnoses/{id}/analysis — readiness.*.status

| chave | pt-BR | en | es | definição |
| --- | --- | --- | --- | --- |
| `ready` | pronto | ready | listo | Todas as dimensões olhadas estão em 80% ou mais. |
| `needs_review` | precisa de revisão | needs review | necesita revisión | Há preenchimento parcial: parte das dimensões tem dado, parte não. |
| `unknown` | desconhecido | unknown | desconocido | Não há dado nas dimensões olhadas. Desconhecido não é reprovado. |

## Sinal do match

`match_signal` · aparece em: GET /v1/projects/{id} e /v1/matches — signals[].key

> Cada sinal é explicável e pode valer UNKNOWN. Sinal UNKNOWN não conta como zero.

| chave | pt-BR | en | es | definição |
| --- | --- | --- | --- | --- |
| `cause` | causa | cause | causa | Afinidade entre a causa do projeto e o interesse declarado de quem financia. |
| `territory` | território | territory | territorio | Compatibilidade entre o território do projeto e o do edital ou do financiador. |
| `budget` | orçamento | budget | presupuesto | Compatibilidade entre o valor pedido e a faixa oferecida. |
| `readiness` | prontidão | readiness | preparación | O quanto o projeto está pronto para receber o recurso. |
| `ods` | ODS | SDG | ODS | Correspondência entre os ODS do projeto e os da oportunidade. |
| `deadline` | prazo | deadline | plazo | Se o prazo do edital é compatível com o momento do projeto. |
| `history` | histórico | history | historial | O que já aconteceu entre as duas partes na plataforma. |
| `ods_esg` | ODS e ASG | SDG and ESG | ODS y ASG | Correspondência combinada de ODS e temas ASG. |
| `capacity` | capacidade | capacity | capacidad | Capacidade registrada de executar o que se propõe. |
| `evidence_history` | histórico de evidência | evidence history | historial de evidencia | Como a organização costuma sustentar o que afirma. |
| `impact` | impacto | impact | impacto | Contexto agregado de necessidade, barreiras e evidência. Alcance declarado NÃO é impacto: sem contexto este sinal é UNKNOWN, mesmo havendo número de beneficiários. |
| `urgency` | urgência | urgency | urgencia | Urgência declarada da necessidade atendida. |
| `preference` | preferência | preference | preferencia | Preferências explícitas registradas por quem busca. |

## Disponibilidade do dado

`data_availability` · aparece em: Vocabulário transversal de todas as telas

> Este é o vocabulário que impede o erro mais comum do produto: tratar ausência como zero.

| chave | pt-BR | en | es | definição |
| --- | --- | --- | --- | --- |
| `known` | informado | known | informado | O dado existe, com origem registrada. |
| `unknown` | não informado | not informed | no informado | O dado não existe ainda. Não equivale a zero, nem a falha, nem a sucesso. |
| `unavailable` | indisponível | unavailable | no disponible | O cálculo existe, mas falta um insumo obrigatório — e a tela diz qual. |
| `not_applicable` | não se aplica | not applicable | no aplica | A pergunta não cabe neste caso. Diferente de não informado. |

## Termos que vivem no banco

Termo que já vive em tabela de catálogo no banco, com name_pt e texto explicativo próprios (claim_rules, seal_rules, reputation_dimensions, responsibility_roles, responsibility_decision_kinds, equity_barrier_catalog). A origem desses termos é o banco, não este arquivo: duplicar aqui criaria duas verdades. O teste exige name_pt e explicação não vazios em todas as linhas. Tradução de catálogo é DEFER_POST_DESIGN — é conteúdo editorial longo e pt-BR é o idioma de origem declarado em locales.coverage_note.

| tabela | rótulo | explicação |
| --- | --- | --- |
| `claim_rules` | `name_pt` | `what_it_detects` |
| `seal_rules` | `name_pt` | `what_it_checks` |
| `reputation_dimensions` | `name_pt` | `what_it_measures` |
| `responsibility_roles` | `name_pt` | `answers_for` |
| `responsibility_decision_kinds` | `name_pt` | `what_it_is` |
| `equity_barrier_catalog` | `name_pt` | `description` |

Total: **123 termos** em 23 domínios, 369 rótulos, mais 6 catálogos no banco.
