# Impacto social, ESG, ODS e avaliação — base de confiança para o IMPACTO

**Release analisado:** Plataforma Impacto v0.26.0  
**Data de corte da pesquisa:** 8 de outubro de 2026  
**Escopo:** teoria da mudança, avaliação de programas, SROI, IRIS+, GRI, ISSB/IFRS S1/S2 quando aplicável, ODS/ONU, direitos humanos, adicionalidade e sua tradução para `IMPACT_FRAMEWORK`, `IMPACT_REPORTING`, `SDG_ESG_TAXONOMY`, `VALUE_LEDGER` e `PROVENANCE_ENGINE`.  
**Natureza:** pesquisa informativa e especificação de controles de produto. Não é parecer jurídico personalizado, certificação, auditoria ou garantia de impacto.

## 1. Escopo e regra de leitura

O termo **impacto** é usado neste relatório em sentido técnico: mudança relevante para pessoas, comunidades, economia ou ambiente, observada em determinado contexto e período, com alguma base para relacioná-la à intervenção. Uma contagem de atividades, aportes, beneficiários cadastrados ou documentos não é, por si só, impacto.

A plataforma deve separar quatro perguntas que hoje são frequentemente misturadas:

1. **O que foi feito?** — insumos, atividades e outputs.
2. **O que mudou?** — outcomes e efeitos, positivos ou negativos, intencionais ou não.
3. **Quanto da mudança pode ser atribuído ou contribuído à intervenção?** — contribuição, adicionalidade e contrafactual.
4. **O que pode ser afirmado publicamente, para qual audiência e sob qual padrão?** — claim, relatório, padrão voluntário ou obrigação.

Os rótulos usados neste documento têm o seguinte significado:

- **Obrigação jurídica vigente:** lei, resolução ou ato normativo aplicável ao sujeito e ao fato. Pode gerar dever de informar, manter prova, proteger dados ou não fazer publicidade enganosa.
- **Orientação administrativa ou autorregulação:** orientação oficial, taxonomia pública ou código setorial que pode orientar conduta, mas não equivale, isoladamente, a lei.
- **Padrão voluntário:** referencial adotado por escolha, contrato, política de investidor ou regra de mercado. Depois de adotado por contrato ou incorporado por ato regulatório, a obrigação pode nascer da fonte que o incorporou.
- **Literatura ou norma de prática:** base metodológica para formular perguntas e avaliações; não prova automaticamente uma alegação.
- **Hipótese de produto:** decisão interna da plataforma sobre campos, estados, escadas, bloqueios e linguagem. Não deve ser apresentada como metodologia oficial de GRI, ISSB, ONU, CVM ou certificação.

## 2. Estado atual do release v0.26.0 que precisa ser corrigido

O README do release declara **BASE TÉCNICA FECHADA**, sem publicação em loja ou domínio, sem provedor de pagamento, fiscal, mapas, WhatsApp ou IA ligado. A execução v0.26.0 acrescentou contrato versionado, duas torres de controle, o estado verificável “Projeto IMPACTO Ready”, rastreabilidade e proveniência. Isso é estado técnico do software; não é comprovação de conformidade ESG, impacto ou certificação.

Há uma divergência documental que deve ser corrigida antes de qualquer comunicação externa:

- `FINAL_IMPACT_FRAMEWORK_REPORT.md` ainda se apresenta como v0.18.0.
- `IMPACT_FRAMEWORK_AUDIT.md` descreve a fase v0.18.0.
- `IMPACT_REPORTING.md` é identificado como v0.16.0.
- `PROVENANCE_ENGINE.md` é identificado como v0.23.0.
- `VALUE_LEDGER.md` é identificado como v0.17.0.
- `SDG_ESG_TAXONOMY.md` descreve ODS, ESG e determinantes, mas assume expressamente que as metas oficiais não estão carregadas e que ESG é classificação editorial.

Esses documentos continuam úteis como especificações históricas, mas não devem ser lidos como retrato completo da v0.26.0. A documentação atual precisa dizer, na mesma página e no mesmo número de release, o que está implementado, o que é apenas estrutura, o que está vazio e o que não pode ser afirmado.

O estado funcional verificável é mais limitado do que a expressão “framework de impacto” pode sugerir:

- O grafo de resultados já possui `impact_nodes` e `impact_edges`, com necessidade, atividade, output, outcome, impacto, população e contexto. Isso é uma **estrutura compatível com teoria da mudança**, não uma teoria causal validada.
- Há contexto de equidade, indicadores, linha de base, claims, materialidade, mapeamentos de frameworks e estados de proveniência. O relatório de auditoria anterior registra que a cadeia não deve ser chamada automaticamente de Teoria da Mudança e que a causalidade exige evidência e revisão independente.
- O registro de frameworks distingue `in_use`, `mappable` e `registry_only`. GRI, ISSB, TCFD, TNFD, IRIS+, SROI, LCA e contabilidade de carbono continuam registrados, mas não devem ser apresentados como relatórios implementados só por existirem no catálogo. A plataforma recusa a relação `certified` e não semeia mapeamentos externos sem código, fonte e data.
- `IMPACT_REPORTING.md` declara que o relatório colhe indicadores e evidências e **não** calcula SROI nem tem verificação independente automática. Essa limitação continua válida.
- ODS oficiais e dados do IBGE continuam fora da carga operacional. Testes do release mantêm `ods_targets` vazio e exigem que a documentação diga que as 169 metas não foram carregadas. O portal de prontidão também registra que dados oficiais de IBGE/ODS permanecem fora.
- O código atual já contém `additionality_standing` e um sinal numérico interno: `declared` = 0,4, `documented` = 0,7 e `evidenced` = 1,0. Isso é uma hipótese de produto, não uma escala reconhecida por ONU, GRI, ISSB, GIIN ou OECD. A escala deve ser tratada como sinal de completude documental, não como “score de impacto” ou prova de adicionalidade.
- `VALUE_LEDGER` mede eventos de valor entregue pela plataforma, separado de billing. Ele não mede mudança social e não deve virar SROI por multiplicação de eventos por uma linha de base de tempo.
- `PROVENANCE_ENGINE` protege uma cadeia específica de `indicator_values`: medição autodeclarada é permitida; estado validado exige evidência. A cadeia genérica de proveniência de qualquer entidade ainda não existe, e a própria documentação registra esse limite.

### Correção de linguagem do release

Até a correção documental e jurídica, a plataforma deve usar expressões como **“indicador informado”**, **“resultado reportado”**, **“evidência anexada”**, **“revisão registrada”**, **“alinhamento declarado”** e **“estado de prontidão derivado”**. Deve bloquear ou qualificar “impacto comprovado”, “ESG compliant”, “certificado”, “verificado pela ONU”, “aprovado pela CVM”, “relatório GRI/ISSB pronto” e “SROI” quando os requisitos correspondentes não estiverem presentes.

## 3. Bases teóricas e normativas

### 3.1 Teoria da mudança e cadeia de resultados

A teoria da mudança é uma explicitação das hipóteses que ligam contexto e necessidade a insumos, atividades, outputs, outcomes e impactos, incluindo pressupostos, riscos, atores e condições externas. O produto deve tratá-la como **modelo de causalidade sujeito a teste**, e não como prova da causalidade.

O Ipea descreve a avaliação ex ante como uma sequência que inclui diagnóstico do problema, caracterização da política, público-alvo, resultados esperados, desenho, implementação, monitoramento, avaliação e controle; o guia também separa avaliação ex ante da avaliação ex post de impactos.[14] A consequência para o produto é registrar, desde o desenho, a hipótese que será testada depois. Um projeto não deve preencher apenas “ODS” e “número de pessoas”; precisa dizer qual mudança pretende produzir, para quem, em que prazo e com qual mecanismo.

A cadeia mínima de dados deve ser:

`contexto/necessidade → atividade → output → outcome → impacto pretendido`,

com cada ligação acompanhada de:

- pressuposto e risco;
- população e território abrangidos;
- indicador, unidade, período e denominador;
- linha de base e fonte;
- resultado esperado e resultado observado;
- efeitos negativos ou não intencionais;
- método de medição;
- nível de evidência e revisão;
- hipótese de contribuição ou contrafactual.

A existência da ligação no grafo deve significar **“hipótese declarada”**, salvo quando uma avaliação específica sustentar uma conclusão mais forte.

### 3.2 Avaliação de programas

O OECD DAC define seis critérios: **relevância, coerência, eficácia, eficiência, impacto e sustentabilidade**. A OECD também adverte que os critérios não são uma metodologia e não devem ser aplicados mecanicamente; a pergunta de avaliação, o propósito, o contexto e os stakeholders devem orientar sua aplicação.[13]

No `IMPACT_FRAMEWORK`, esses critérios devem ser lentes e perguntas, não campos binários de aprovação:

- **Relevância:** o problema e a intervenção respondem ao contexto e às prioridades das pessoas afetadas?
- **Coerência:** há compatibilidade com políticas, programas, território e outras intervenções?
- **Eficácia:** os resultados esperados foram alcançados, para quais grupos e com quais efeitos diferenciais?
- **Eficiência:** recursos, tempo e capacidade foram usados de modo proporcional ao resultado?
- **Impacto:** que diferença ocorreu além do output imediato? Há evidência de efeitos positivos e negativos?
- **Sustentabilidade:** os benefícios, capacidades e condições tendem a permanecer?

Equidade não deve ser reduzida a um multiplicador único. A OECD orienta que equidade seja examinada nas perguntas de relevância, eficácia, impacto, sustentabilidade e coerência, com atenção a grupos marginalizados e resultados diferenciais.[13] Isso converge com a decisão do release de não ranquear projetos por uma nota única de reputação.

### 3.3 SROI

SROI é um método baseado em princípios que identifica stakeholders, pergunta o que mudou e quanto a mudança importa, seleciona indicadores, ajusta o resultado pelo que teria ocorrido sem a intervenção e atribui valores monetários ou proxies a resultados sociais, ambientais e econômicos.[9] A fonte de alinhamento GIIN/SROI deixa claro que o método deve considerar o que teria acontecido na ausência do trabalho da organização.[9]

O SROI pode ser útil para uma avaliação contratada e delimitada. Não deve ser o número padrão de todos os projetos, por quatro razões:

1. monetização exige escolha de proxies, premissas e fontes que podem não ser comparáveis;
2. o resultado é sensível a deadweight, atribuição, deslocamento, drop-off, período e taxa de desconto;
3. um índice “R$ X de valor por R$ 1” não prova causalidade e não é comparável sem método e fronteiras iguais;
4. o método não é certificação, selo da ONU, padrão CVM ou substituto de avaliação de direitos humanos.

O produto deve permitir um **estudo SROI versionado**, separado do indicador operacional. Deve guardar stakeholders consultados, outcomes, proxy, fonte, cálculo, deadweight, atribuição, deslocamento, drop-off, incerteza, período, revisão e limitações. Na ausência desses elementos, exibir “não calculado”, e não zero.

### 3.4 IRIS+

IRIS+ é um framework e catálogo de recursos e métricas do GIIN para converter intenção de impacto em estrutura de medição e gestão, escolher categorias, temas, objetivos, outcomes e conjuntos de métricas, e conectar intenções a ODS.[8] É um padrão de prática de mercado, não lei brasileira, certificação ou prova de adicionalidade.

A integração segura é usar IRIS+ como **referência de métrica**:

- registrar a versão, código e nome oficial da métrica;
- guardar definição, unidade, fonte e regra de cálculo;
- separar métrica IRIS+ de indicador próprio da organização;
- registrar se a relação é alinhada, mapeada, avaliada, reportada, verificada ou auditada;
- não escrever “IRIS+ compliant” quando houve apenas escolha de uma métrica.

### 3.5 GRI

Os Universal Standards da GRI (GRI 1, GRI 2 e GRI 3) foram revisados em 2021 e estão em vigor para relatórios desde 1º de janeiro de 2023. A GRI descreve os padrões como referência para transparência dos impactos da organização sobre economia, meio ambiente e pessoas.[7] GRI é relato orientado a impactos e stakeholders; ISSB é relato financeiro de sustentabilidade orientado a investidores. Eles podem ser usados de modo complementar, mas não são sinônimos.

No produto, “mapeado para GRI” deve significar que existe correspondência documentada entre indicador e código GRI, com fonte, escopo, período, versão e justificativa. “Relatório GRI” exige a aplicação do conjunto de requisitos que a organização declarou seguir, e não apenas uma lista de códigos.

### 3.6 ISSB / IFRS S1 e S2 e aplicabilidade brasileira

A IFRS Foundation afirma que IFRS S1 exige divulgação de riscos e oportunidades relacionados à sustentabilidade que possam razoavelmente afetar fluxos de caixa, acesso a financiamento ou custo de capital, no curto, médio ou longo prazo.[5] A arquitetura envolve governança, estratégia, gestão de riscos e métricas e metas; a informação é dirigida a investidores, credores e outros provedores de capital.[6] A avaliação de materialidade é financeira e relacionada às perspectivas da entidade; não substitui, por si só, o relato de impactos da GRI ou a avaliação de resultados sociais.

IFRS S2 trata especificamente de riscos e oportunidades climáticos. O CBPS 02, aprovado pela CVM na Resolução CVM 218/2024, correlaciona-se à IFRS S2 e trouxe, no texto da resolução, aplicação para exercícios iniciados a partir de 1º de janeiro de 2026, com divulgação de governança, estratégia, gestão de riscos, métricas e metas.[4]

O estado regulatório precisa ser atualizado no produto. A Resolução CVM 193 original estabelecia opção voluntária e depois previa obrigatoriedade para companhias abertas. O texto consolidado registra que o art. 2º foi **revogado pela Resolução CVM 244, de 29 de maio de 2026**; a CVM anunciou que a adoção passou a ser voluntária, condicionada à observância dos padrões CBPS/ISSB quando escolhida.[1][2][3]

Na leitura do texto consolidado, a entidade que optar por reportar deve:

- declarar adesão explícita e sem reservas aos padrões CBPS e ISSB;
- publicar por no mínimo três exercícios seguidos;
- comunicar a interrupção no exercício anterior àquele em que deixará de reportar;
- observar, para companhia aberta que optar por não arquivar relatório a partir de 2027, a justificativa por comunicado ao mercado prevista no texto consolidado.[2]

A Resolução CVM 218 e o regime reformado da Resolução CVM 193 devem ser lidos em conjunto pelo jurídico responsável pelo emissor, fundo ou securitizadora. O produto **não pode** codificar uma regra simplista “toda companhia aberta é obrigada” nem a regra oposta “ninguém tem obrigação”. Deve perguntar entidade, tipo de valor mobiliário, exercício, ato normativo e opção formal declarada, e exigir fonte normativa atualizada.

### 3.7 ODS/ONU e indicadores brasileiros

A ONU Brasil apresenta os ODS como 17 objetivos interconectados da Agenda 2030, destinados a enfrentar pobreza, proteção ambiental e climática, paz e prosperidade.[11] Eles são objetivos globais de política pública. Não são selo de projeto, certificado de empresa, métrica causal ou autorização para afirmar que um projeto “entregou o ODS”.

O portal ODS Brasil, operado no ecossistema estatístico brasileiro pelo IBGE, mostra 326 indicadores, com estados distintos: produzidos, em análise/construção, sem dados e não aplicáveis ao Brasil.[12] Essa distinção é essencial: “sem dados” não equivale a zero; indicador nacional também não é automaticamente a linha de base de um projeto.

`SDG_ESG_TAXONOMY` deve, portanto, manter três camadas separadas:

1. **ODS:** objetivo, meta e indicador oficial, com publicação, versão, fonte e licença;
2. **ESG:** classificação editorial ou referencial escolhido, com pilar, tema e audiência;
3. **contribuição do projeto:** afirmação da organização, sustentada por resultado e evidência, com escopo e incerteza.

### 3.8 Taxonomia Sustentável Brasileira

A página oficial do Ministério da Fazenda define a Taxonomia Sustentável Brasileira como sistema que classifica atividades econômicas, ativos e projetos que contribuem para objetivos ambientais, econômicos e sociais, com critérios e indicadores. A página lista sete objetivos ambientais/climáticos e quatro econômico-sociais, além de objetivos estratégicos de mobilizar capital, adensar tecnologia e produzir informação confiável.[16]

A TSB é uma referência institucional e de política pública. A página consultada não autoriza, por si só, o produto a declarar que um projeto é “certificado pela Taxonomia”. O produto deve registrar:

- edição e caderno aplicável;
- atividade econômica elegível;
- critério técnico e limiar;
- contribuição substancial e salvaguardas, quando exigidas pelo caderno;
- fonte, data, versão e responsável pela análise;
- conclusão “alinhado”, “não alinhado”, “não avaliado” ou “informação insuficiente”.

O vínculo a um ODS ou a um código da TSB não prova impacto realizado. É uma classificação ou hipótese de contribuição até que resultados e evidências sustentem a afirmação.

### 3.9 Direitos humanos

Os Princípios Orientadores da ONU sobre Empresas e Direitos Humanos foram endossados pelo Conselho de Direitos Humanos em 2011. Eles articulam três pilares: dever do Estado de proteger, responsabilidade empresarial de respeitar e acesso a reparação.[15] O documento afirma que a responsabilidade empresarial inclui evitar causar ou contribuir para impactos adversos e tratar tais impactos; também prevê due diligence e mecanismos de reclamação acessíveis.

Os Princípios Orientadores não criam, sozinhos, uma nova obrigação internacional para cada empresa. São orientação institucional e referência de conduta responsável. A plataforma deve, contudo, tratá-los como requisito de desenho porque uma medição de “beneficiários” que não escuta pessoas afetadas pode apagar dano, discriminação, deslocamento ou coerção.

Requisitos mínimos:

- identificar titulares de direitos e grupos potencialmente vulneráveis;
- registrar impactos adversos, não somente benefícios;
- permitir participação e feedback sem expor dados pessoais;
- manter canal de reclamação e resposta;
- não transformar reclamação em nota de reputação sem apuração;
- registrar remediação, correção e aprendizado;
- separar alegação da organização, evidência da plataforma e juízo de terceiro.

### 3.10 Adicionalidade e contribuição

Adicionalidade não é sinônimo de necessidade, volume de recurso, número de beneficiários ou alinhamento a ODS. A orientação da Impact Frontiers explica que a contribuição deve considerar o que provavelmente teria acontecido sem a atividade, isto é, o resultado contrafactual; também diferencia a diferença entre outcome observado e baseline da influência de outros atores.[21]

O produto deve distinguir:

- **necessidade:** por que o problema existe;
- **baseline:** o que foi observado antes ou em referência;
- **outcome:** mudança observada no período;
- **contribuição:** parcela plausível associada à intervenção em meio a outros fatores;
- **adicionalidade financeira ou de mercado:** se o recurso, instrumento ou intervenção alterou escala, timing, alcance ou viabilidade;
- **evidência de contrafactual:** comparação experimental, quase-experimental, teoria de contribuição, pesquisa de mercado, série temporal ou evidência qualitativa estruturada.

O `additionality_score` atual deve ser substituído na apresentação por um **nível de suporte** (`declarado`, `documentado`, `evidenciado`, `não avaliado`) e acompanhado do método. Um número 0,4/0,7/1,0 sugere uma precisão que o dado não tem e pode ser usado como ranking ou claim de impacto.

## 4. Relação dos cinco componentes

### 4.1 `IMPACT_FRAMEWORK`

**Papel:** estruturar a hipótese de mudança e a avaliação.  
**Entradas:** contexto, necessidade, população, território, atividades, outputs, outcomes, impactos pretendidos, pressupostos, riscos, indicadores, linha de base, metas, método e efeitos adversos.  
**Saídas legítimas:** cadeia de resultados, perguntas de avaliação, lacunas e nível de suporte.  
**Não deve produzir:** nota única de impacto, causalidade automática, certificação, ranking de organizações ou claim de ODS.

A implementação atual já possui elementos de cadeia, equidade, materialidade e claims. A melhoria necessária é ligar cada aresta a uma hipótese, fonte e teste; permitir outcome negativo; distinguir descrição do projeto de conclusão avaliativa; e nunca tratar uma cadeia preenchida como evidência causal.

### 4.2 `IMPACT_REPORTING`

**Papel:** gerar prestação de contas por projeto e período, com métricas colhidas de indicadores e evidências.  
**Implementação atual:** ciclo `draft → submitted → under_review → accepted → published`, uma linha por projeto/período, métrica colhida pelo banco, revisão por apoiador diferente do autor, campos de limitações e riscos, publicação somente após aceite.  
**Limite atual:** não é relatório GRI, ISSB ou SROI; não possui verificação independente automática.

O produto deve ter perfis de relatório diferentes:

- **impacto/programa:** outputs, outcomes, contribuição, stakeholders, equidade e efeitos adversos;
- **GRI:** impactos da organização, temas materiais e divulgações aplicáveis;
- **ISSB/CBPS:** riscos e oportunidades financeiros relacionados à sustentabilidade, dirigidos a provedores de capital;
- **ODS:** contribuição declarada a metas oficiais, sem transformar o ODS em selo;
- **SROI:** estudo monetizado com premissas e ajustes próprios.

Um relatório pode citar mais de um referencial, mas a interface deve mostrar qual pergunta cada referencial responde.

### 4.3 `SDG_ESG_TAXONOMY`

**Papel:** catálogo e classificação.  
**Implementação atual:** ODS 1–17, pilares ESG e determinantes editoriais; marcadores com integridade relacional; metas oficiais não carregadas; sem prova de que um projeto cumpre ODS ou ESG.  
**Correção:** importar metas/indicadores somente de fonte oficial com dataset, versão, data de consulta, licença e hash; marcar “em análise”, “sem dados” e “não aplicável”; guardar código oficial e não apenas texto.

A TSB deve ser um referencial separado de ESG editorial. ODS, ESG, GRI, ISSB, IRIS+ e TSB não devem compartilhar uma coluna genérica `framework_code` sem tipo, versão, steward e regra de uso.

### 4.4 `VALUE_LEDGER`

**Papel:** registrar valor operacional entregue pela plataforma, separado de cobrança.  
**Implementação atual:** eventos como prontidão avaliada, lacuna encontrada, documento montado, relatório aceito e varredura concluída; linha de base de tempo exige fonte, data e método; sem baseline, a estimativa fica nula.

**Regra de confiança:** valor operacional entregue pela plataforma não é valor social criado pelo projeto. Um documento montado, uma triagem ou uma prestação de contas aceita pode ser serviço entregue, mas não outcome social. Nunca converter `value_events` em SROI sem desenho SROI próprio.

### 4.5 `PROVENANCE_ENGINE`

**Papel:** permitir que um número mostre sua origem, evidência, revisão, validação e integridade histórica.  
**Implementação atual:** `source_kind` derivado, validação exige `evidence_id`, origem congelada após validação, documentos com SHA-256, cadeia de revisão, ledger, auditoria e `gaps` explícitos; correção entra como novo lançamento que aponta ao lançamento revertido.

**Limites:** a cadeia genérica de qualquer entidade não foi implementada; evidência sem arquivo não tem hash; há ambiguidade potencial se mais de um documento substituir o mesmo antecessor; mapeamentos externos ainda dependem de fontes e revisão.

**Extensão necessária:** claims, metas ODS, códigos GRI/IRIS+, TSB e regras de materialidade devem ter sua própria proveniência: autoridade publicadora, título, URL, data, versão, licença, hash do arquivo, trecho ou página, revisor, vigência e motivo de substituição.

## 5. Mapa de obrigações, orientações e claims

| Tema | Classificação correta | Quando se aplica | Requisito para o produto | Situação v0.26.0 |
|---|---|---|---|---|
| Publicidade/claim para consumidor | **Lei vigente**: CDC | Oferta ou publicidade de produto/serviço em relação de consumo | informação clara; manter dados fáticos, técnicos e científicos; não omitir dado essencial; ônus da prova da veracidade com patrocinador; bloquear claim sem suporte | A arquitetura de claims e proveniência ajuda, mas cada claim de marketing ainda precisa de revisão e contexto de destinatário [18] |
| Proteção de dados pessoais | **Lei vigente**: LGPD | Coleta de pessoas, beneficiários, avaliadores, contatos, documentos ou logs identificáveis | finalidade, adequação, necessidade, transparência, segurança, não discriminação, prestação de contas, base legal, direitos, retenção e incidente | `LGPD.md` reconhece pendências de base legal, RIPD/DPIA, contrato com operadores, retenção real e encarregado; não declarar conformidade integral [19] |
| Anticorrupção | **Lei vigente**: Lei 12.846/2013 | Atos contra administração pública nacional/estrangeira, licitações, contratos e relações com agentes públicos | trilha de integridade, segregação, denúncia, investigação e evidência; não permitir que claim de impacto esconda beneficiário real ou vantagem indevida | Há trilhas e controles internos, mas a aplicação concreta depende do caso e de política de integridade [20] |
| Reporte de sustentabilidade por entidade regulada | **Regulação CVM vigente, com aplicabilidade condicional** | Companhia aberta, fundo ou securitizadora que opte pelo regime; atos e exercício aplicáveis; leitura conjunta de CVM 193/244 e CBPS | entidade, período, opção formal, adesão sem reservas, padrão CBPS/ISSB, mínimo de três exercícios, comunicação de interrupção e arquivamento | As minutas legais do release excluem relatório pronto para CVM/GRI/ISSB; não liberar claim de reporte regulatório [1][2][3][4] |
| IFRS S1/S2 fora de incorporação regulatória | **Padrão internacional voluntário** | Escolha contratual, política de mercado ou adoção jurisdicional | materialidade financeira, quatro áreas, métricas/metas, governança, estratégia e riscos; manter versão oficial | Registro `registry_only`; não há tradução automática ou declaração de aderência [5][6] |
| GRI | **Padrão voluntário** salvo incorporação contratual/regulatória | Relato de impactos da organização | requisitos GRI aplicáveis, temas materiais, fonte, período, escopo e declaração de aplicação | Registro sem mapeamento oficial semeado; não usar “GRI compliant” [7] |
| IRIS+ | **Framework voluntário de métricas** | Gestão e relato de impacto, especialmente investimento de impacto | código, versão, definição, unidade, fonte, método e escopo; não confundir métrica com certificação | `registry_only`; não há relação externa validada [8] |
| SROI | **Método voluntário/literatura de prática** | Avaliação específica com outcomes monetizados | stakeholders, outcomes, proxy, baseline, deadweight, atribuição, deslocamento, drop-off, incerteza e revisão | Declaradamente não implementado como cálculo automático [9][10] |
| ODS/Agenda 2030 | **Marco internacional de política pública** | Alinhamento de estratégia, programa ou relato; uso de metas oficiais | código e meta oficial, fonte, versão e linguagem de contribuição; não afirmar “entregou ODS” sem evidência | ODS 1–17 existem como catálogo; metas oficiais e indicadores nacionais não estão carregados [11][12] |
| Taxonomia Sustentável Brasileira | **Referência institucional/política pública**, não certificação automática | Classificação de atividade, ativo ou projeto segundo caderno e critério aplicável | edição, atividade elegível, critério, limiar, salvaguardas, evidência, conclusão e responsável | Não há motor de alinhamento TSB; classificação editorial não substitui análise técnica [16] |
| Direitos humanos | **Princípios Orientadores/soft law institucional** e deveres jurídicos nacionais aplicáveis conforme o caso | Operações que possam afetar pessoas e comunidades | due diligence, consulta, impactos adversos, canal de reclamação, remediação e atenção a grupos vulneráveis | Há agregação e minimização; falta jornada completa de grievance, due diligence e remediação [15] |
| Publicidade socioambiental autorregulada | **Código CONAR/autorregulação**, não lei | Publicidade submetida ao ecossistema CONAR | qualificadores, clareza de escopo, distinção entre redução/remoção/compensação, metas com plano e informação acessível | Deve ser gate de marketing, acompanhado sempre do CDC e da prova guardada [17][18] |

### Regra para entidades públicas e contratos

Uma obrigação pode nascer não somente de lei geral, mas de edital, contrato, instrumento de parceria, política do financiador ou regulamento setorial. O produto deve guardar a **fonte da obrigação** e não rotular todo requisito contratual como “lei”. A `PROCUREMENT.md` existente, por exemplo, é política interna de três cotações e benchmark do próprio pedido; ela não é base de preços de mercado nem validação de orçamento. Do mesmo modo, uma exigência de GRI em contrato é exigência contratual, não prova de que GRI seja lei.

## 6. Requisitos de produto

### 6.1 Modelo de impacto

1. Criar uma versão imutável de teoria da mudança por projeto/programa.
2. Separar `need`, `activity`, `output`, `outcome`, `impact`, `population` e `context`.
3. Exigir pressuposto, risco, responsável, período e fonte em cada relação causal.
4. Permitir resultado negativo, não intencional e distribuição desigual por grupo.
5. Proibir “impacto” quando só há output, desembolso ou atividade.
6. Exigir linha de base ou declarar `baseline_unavailable` com motivo.
7. Exigir unidade e denominador para taxa, per capita ou cobertura; desconhecido não vira zero.
8. Registrar método de coleta, frequência, população elegível, amostra e limitações.
9. Separar resultado observado de contribuição atribuída ou adicionalidade.
10. Permitir avaliação ex ante, de processo, de resultado e ex post, cada uma com pergunta e método próprios.

### 6.2 Relatórios por audiência

Cada relatório deve declarar `audience` e `purpose`:

- comunidade e participantes;
- doador/financiador;
- órgão público;
- gestão do projeto;
- investidor/credor;
- consumidor ou público de marketing.

O sistema deve impedir que um relatório de outputs seja exportado com cabeçalho “IFRS S1” ou “GRI” só porque há tags ODS/ESG. A exportação deve mostrar a matriz de requisitos atendidos, não apenas logotipos.

### 6.3 Claims

Cada claim precisa ter:

- texto original e texto qualificado;
- tipo: fato, resultado, impacto, previsão, meta, comparação, certificação, alinhamento ODS, ESG, TSB, redução/remoção/compensação climática;
- sujeito, projeto, produto, território e período;
- audiência e canal;
- indicador(es), evidência(s) e método;
- data de validade e condição de expiração;
- revisão humana, independência e decisão;
- padrão ou lei invocado, quando houver;
- limitações e linguagem proibida.

O estado não deve ser uma coluna livre. Deve ser derivado dos checks, da revisão e da validade, como a arquitetura atual já faz para a integridade de claims.

### 6.4 Controles de padrões

A escada recomendada é:

`alinhado → mapeado → avaliado → relatado → verificado → auditado`.

- **Alinhado:** relação declarada e explicada.
- **Mapeado:** há código oficial e fonte do referencial.
- **Avaliado:** alguém examinou pertinência, escopo e método.
- **Relatado:** o número foi publicado, com fonte e qualificação.
- **Verificado:** revisor de outra organização conferiu.
- **Auditado:** auditoria independente registrada, com escopo.

`certificado` deve continuar inexistente salvo contratação e atuação de organismo certificador competente. A plataforma não deve emprestar esse status.

## 7. Requisitos de dados e esquema de evidência

### 7.1 Indicador

Campos mínimos: `indicator_id`, código, nome, definição, unidade, tipo de resultado, fórmula, população, denominador, período, data de observação, baseline, meta, método, responsável, fonte, versão, qualidade, incerteza e estado.

### 7.2 Fonte e dataset

Para toda fonte externa: órgão/autor, título, URL, data de publicação, data de consulta, versão, licença, hash do arquivo, página/trecho, idioma e status de vigência. Para dados oficiais ODS/IBGE, guardar dataset e transformação. Para GRI/IRIS+/TSB, guardar edição e steward. Para legislação, guardar número, redação consolidada, data de vigência e norma que alterou ou revogou.

### 7.3 Evidência

A cadeia deve registrar documento, versão, SHA-256, quem enviou, período coberto, revisão, independência, medição, validação, ledger e auditoria. Se um elo faltar, `gaps` deve dizer o que o número não prova. Documento sem hash não prova imutabilidade; resultado autodeclarado não prova validação.

### 7.4 Direitos humanos e dados pessoais

Evitar lista nominal de beneficiários quando a decisão pode ser tomada com contagem agregada. Quando dados identificáveis forem indispensáveis, guardar finalidade, base legal, minimização, acesso, retenção, anonimização/pseudonimização, canal de titular e incidente. Dados de vulnerabilidade não devem virar atributo público da pessoa nem ranking. A plataforma deve manter a distinção já existente: vulnerabilidade pode ser contexto do projeto, não rótulo da pessoa.

### 7.5 Adicionalidade

Guardar `counterfactual_method`, `counterfactual_source`, `comparison_group_or_reference`, `other_actors`, `uncertainty`, `contribution_statement`, `additionality_standing` e `review`. Não expor `additionality_score` como nota de impacto enquanto não houver método e validação adequados.

### 7.6 SROI

Guardar tabela de stakeholders, outcomes, indicador, valor observado, baseline, proxy, unidade monetária, fonte do proxy, deadweight, atribuição, deslocamento, drop-off, período, taxa de desconto quando aplicável, sensibilidade, intervalo e decisão de incluir/excluir outcome. Relatar a razão somente junto com premissas e limitações.

## 8. Testes e controles obrigatórios

### 8.1 Checks de banco

- `validated` exige `evidence_id`.
- `evidence_document` exige documento.
- origem de indicador congela após validação.
- linha de base numérica exige fonte, data e método.
- relação `verified` exige revisor de outra organização.
- referencial `registry_only` não aceita relação verificada/auditada.
- `certified` é recusado.
- relatório só chega a `published` depois de aceite.
- correção de ledger aponta lançamento anterior, usa valor oposto e tem motivo.
- claim retirado não apaga o histórico da checagem.
- ODS inexistente, meta não carregada ou código externo sem fonte é recusado.
- nenhum dado ausente é convertido em zero.

### 8.2 Testes de produto

1. **Claim sem evidência:** tela e API recusam “impacto comprovado”.
2. **Claim com medição autodeclarada:** permite publicar somente com qualificador “autodeclarado”.
3. **ODS sem meta oficial:** permite “ODS relacionado declarado”, mas não “meta ODS atingida”.
4. **GRI/ISSB/IRIS+ sem mapping:** exportação mostra “não reportável neste referencial”.
5. **Adicionalidade declarada:** mostra método ausente e não gera score de contribuição.
6. **SROI incompleto:** estado “não calculado” ou “rascunho”, nunca razão zero.
7. **Resultado positivo com dano adverso:** impede selo ou status global de impacto positivo sem exibir o dano.
8. **Revisor autor do dado:** recusa em SQL e API.
9. **Fonte revogada ou desatualizada:** relatório mostra alerta e versão usada.
10. **Reprodução:** mesma versão de fonte e mesmo input reproduzem o mesmo resultado; diferenças produzem nova versão.
11. **Direito do titular:** exportar/corrigir/anonimizar dados pessoais sem apagar indevidamente a integridade do ledger.
12. **Cross-tenant:** organização não lê dados, reclamações ou evidências de outra sem autorização.
13. **Marketing:** cada claim público abre a prova, escopo, data e limitações.
14. **Regulação CVM:** entidade, exercício e comunicado são campos obrigatórios antes de exportar um reporte CBPS/ISSB.
15. **Auditoria:** qualquer decisão de revisão, verificação, rejeição ou correção tem ator, data, escopo, versão e correlação.

### 8.3 Controles humanos

A plataforma deve exigir quatro olhos para:

- alterar teoria da mudança publicada;
- declarar causalidade ou adicionalidade evidenciada;
- aprovar relatório externo;
- marcar aderência a GRI/ISSB/CBPS/TSB;
- liberar claim ambiental ou social para marketing;
- corrigir ou suspender evidência;
- aceitar metodologia SROI;
- resolver reclamação de direitos humanos.

A aprovação humana não transforma dado fraco em dado forte. Ela deve registrar o que foi lido, qual padrão foi usado e quais limitações permanecem.

## 9. Claims proibidos ou bloqueados

A lista abaixo é de **bloqueio de produto**. A qualificação jurídica depende do contexto, do destinatário, do contrato e da norma aplicável.

### Bloquear sempre sem fonte e escopo

- “impacto comprovado”, “impacto garantido” ou “causou X” sem método de contribuição/causalidade;
- “beneficiou X pessoas” se X é apenas público-alvo, cadastro ou alcance sem indicador e período;
- “adicionalidade comprovada” quando há somente declaração da organização ou valor investido;
- “atingiu o ODS X”, “entregou a meta ODS X” ou “projeto da ONU” sem meta oficial, resultado, evidência e autorização;
- “ESG compliant”, “100% ESG”, “ESG certificado” ou “empresa ESG” sem padrão, escopo, versão, auditoria e base;
- “GRI compliant”, “relatório GRI” ou “ISSB compliant” quando houve somente tag ou mapeamento parcial;
- “CVM aprovado”, “CBPS aprovado”, “IFRS certificado” ou “ONU verificado” sem ato e escopo que sustentem a expressão;
- “certificado”, “certificação oficial”, “selo independente” ou “auditado” sem organismo, escopo e documento de auditoria;
- “SROI de 3:1” sem stakeholders, proxy, baseline, deadweight, atribuição, período, cálculo, sensibilidade e limitações;
- “neutralidade climática”, “carbono neutro”, “zero emissão” ou “redução de emissões” sem fronteira, escopo, período, metodologia e distinção entre redução, remoção e compensação;
- “reciclável”, “compostável”, “biodegradável” ou “destinação garantida” sem atributos, sistema, capacidade e limitações;
- “sem dano”, “não causa impacto negativo” ou “direitos humanos respeitados” sem due diligence, escopo e tratamento de reclamações.

### Fundamento jurídico da proibição de claims de marketing

O CDC garante informação adequada e proteção contra publicidade enganosa e abusiva; exige que o fornecedor mantenha dados fáticos, técnicos e científicos que sustentem a mensagem; considera enganosa a informação falsa ou capaz de induzir erro, inclusive por omissão; e atribui a quem patrocina a publicidade o ônus da prova da veracidade e correção.[18] A lei também tipifica afirmação falsa/enganosa, publicidade enganosa e ausência de organização dos dados de sustentação.

O CONAR atualizou, em 27 de outubro de 2025, o art. 36 e o Anexo U de seu código para exigir qualificação, transparência de metas, informação sobre modalidade e abrangência de alegações climáticas e limites de atributos ambientais.[17] O código é autorregulação e não substitui o CDC; deve ser usado como controle adicional de revisão e linguagem.

## 10. Lacunas prioritárias e critérios de aceite

### P0 — impedir claim falso

1. Atualizar todos os documentos de impacto para v0.26.0, com versão, data e links internos.
2. Remover ou esconder `additionality_score` numérico; expor nível de suporte e método.
3. Criar gate único de claims ambientais, sociais, ODS, ESG e padrões.
4. Fazer o exportador mostrar sempre escopo, período, fonte, evidência, revisão e gaps.
5. Proibir “certified”, “CVM approved”, “GRI/ISSB compliant” e “impacto comprovado” sem prova específica.

### P1 — tornar o catálogo confiável

6. Importar metas ODS e indicadores oficiais somente por dataset versionado, com fonte e licença.
7. Completar fonte e versão do catálogo de indicadores.
8. Adicionar TSB como referencial separado, com cadernos e critérios, sem linguagem de certificação.
9. Implementar mapeamentos GRI/IRIS+/ISSB somente após conferir códigos oficiais; cada mapeamento deve ser revisável e reversível.
10. Resolver a matriz CVM 193/244 e CVM 218 para entidades, exercício e opção, com revisão jurídica.

### P1 — causalidade e direitos

11. Adicionar método de contrafactual/contribuição e múltiplos atores.
12. Adicionar outcomes negativos, deslocamento e reclamações.
13. Implementar due diligence e remediação de direitos humanos sem ranking de pessoas.
14. Separar resultado de programa, valor operacional do produto e cobrança.

### P2 — interoperabilidade auditável

15. Implementar proveniência genérica para claims, mappings, datasets e relatórios.
16. Criar perfis de exportação distintos para impacto, GRI, ISSB/CBPS, ODS, TSB e SROI.
17. Criar estudo SROI como módulo opt-in, com sensibilidade e revisão, sem cálculo automático por padrão.
18. Construir teste de regressão que falhe se documentação disser “oficial”, “validado” ou “certificado” quando a base estiver vazia.

## 11. Conclusão operacional

O release v0.26.0 já tem uma base valiosa: dados agregados, estados explícitos, revisão humana, ledger com hash, proveniência de indicadores, recusas estruturais e separação entre valor entregue e billing. O risco principal não é a ausência de telas; é a distância entre a linguagem de “impacto/ESG/ODS” e o que cada dado realmente sustenta.

A arquitetura deve ser corrigida para seguir esta regra:

> **ODS, ESG, TSB, GRI, ISSB, IRIS+ e SROI são referenciais diferentes. Nenhum deles converte, por si só, uma atividade em impacto comprovado. O produto só pode publicar a alegação que a cadeia de dados, o método, a fonte, a revisão e o escopo conseguem sustentar.**

Enquanto as lacunas acima permanecerem, a posição correta do produto é: **estrutura de impacto e prestação de contas com indicadores reportados, proveniência e controles de claims; não certificador, não auditor independente, não organismo de validação, não emissor de reporte CVM/GRI/ISSB e não calculadora automática de SROI.**

## 12. Registro de fontes externas

[1]: https://conteudo.cvm.gov.br/legislacao/resolucoes/resol193.html "CVM — Resolução CVM 193, 20 de outubro de 2023; página oficial, com alterações pelas Resoluções 219/2024, 227/2025 e 244/2026. Sustenta a identificação da norma e seu histórico de alterações."

[2]: https://conteudo.cvm.gov.br/export/sites/cvm/legislacao/resolucoes/anexos/100/resol193consolid.pdf "CVM — Resolução CVM 193, texto consolidado, 20 de outubro de 2023, consolidado até a Resolução 244/2026. Sustenta adoção voluntária, adesão CBPS/ISSB, mínimo de três exercícios, comunicação de interrupção e revogação do art. 2º."

[3]: https://www.gov.br/cvm/pt-br/assuntos/noticias/2026/cvm-altera-resolucao-193-para-revogar-obrigatoriedade-da-divulgacao-de-informacoes-financeiras-relacionadas-a-sustentabilidade "Comissão de Valores Mobiliários — CVM altera Resolução 193 para revogar obrigatoriedade da divulgação de informações financeiras relacionadas à sustentabilidade, 29 de maio de 2026. Sustenta a mudança para regime voluntário e o comunicado de pratique ou explique."

[4]: https://conteudo.cvm.gov.br/cvm_institucional/export/sites/cvm/legislacao/resolucoes/anexos/200/resol218.pdf "CVM — Resolução CVM 218, 29 de outubro de 2024, que aprova o Pronunciamento Técnico CBPS 02 — Divulgações Relacionadas ao Clima. Sustenta a correlação com IFRS S2, conteúdo e redação original de vigência para companhias abertas."

[5]: https://www.ifrs.org/issued-standards/ifrs-sustainability-standards-navigator/ifrs-s1-general-requirements/ "IFRS Foundation/ISSB — IFRS S1 General Requirements for Disclosure of Sustainability-related Financial Information, Standard 2026. Sustenta objetivo, riscos e oportunidades que afetam perspectivas financeiras, vigência internacional e requisitos gerais."

[6]: https://www.ifrs.org/sustainability/knowledge-hub/introduction-to-issb-and-ifrs-sustainability-disclosure-standards/ "IFRS Foundation/ISSB — Introduction to the ISSB and IFRS Sustainability Disclosure Standards, s.d., consulta em 8 de outubro de 2026. Sustenta usuários investidores/credores, materialidade, quatro áreas e aplicação conjunta de S1/S2."

[7]: https://www.globalreporting.org/standards/standards-development/universal-standards/ "Global Reporting Initiative/GSSB — Universal Standards (GRI 1, GRI 2, GRI 3), revisão 2021, vigência para relatos desde 1º de janeiro de 2023. Sustenta foco em impactos sobre economia, ambiente e pessoas e natureza modular dos padrões."

[8]: https://iris.thegiin.org/ "Global Impact Investing Network — Welcome to IRIS+, s.d., consulta em 8 de outubro de 2026. Sustenta finalidade de transformar intenção de impacto em framework, métricas e conexão com ODS."

[9]: https://iris.thegiin.org/document/iris-and-social-return-on-investment/ "GIIN e SROI Network — IRIS+ and Social Return on Investment, alinhamento original de 2011. Sustenta definição de SROI, identificação de stakeholders, indicadores, ajustes por ausência da intervenção e valoração de outcomes."

[10]: https://socialvalueint.org/what-is-social-value/ "Social Value International — What is social value?, s.d., consulta em 8 de outubro de 2026. Sustenta que valor social depende do que importa às pessoas afetadas e que envolver stakeholders é princípio central."

[11]: https://brasil.un.org/pt-br/sdgs "Nações Unidas Brasil — Sobre o nosso trabalho para alcançar os Objetivos de Desenvolvimento Sustentável no Brasil, s.d., consulta em 8 de outubro de 2026. Sustenta os 17 objetivos interconectados e a natureza de marco global da Agenda 2030."

[12]: https://odsbrasil.gov.br/relatorio/sintese "IBGE/ODS Brasil — Indicadores Brasileiros para os Objetivos de Desenvolvimento Sustentável, s.d., consulta em 8 de outubro de 2026. Sustenta o catálogo brasileiro de 326 indicadores e seus estados de produção, análise/construção, ausência de dados e não aplicação."

[13]: https://www.oecd.org/en/topics/sub-issues/development-co-operation-evaluation-and-effectiveness/evaluation-criteria.html "OECD Development Assistance Committee — Evaluation Criteria, critérios revisados em 2019 e página institucional atual. Sustenta as seis lentes de avaliação e a regra de não aplicação mecânica."

[14]: https://repositorio.ipea.gov.br/entities/book/40676951-eabf-494c-8aea-348c820eeebd "Instituto de Pesquisa Econômica Aplicada/Casa Civil — Avaliação de políticas públicas: guia prático de análise ex ante, volume 1, 2018. Sustenta diagnóstico, público-alvo, resultados esperados, desenho, implementação, monitoramento, avaliação e distinção entre ex ante e ex post."

[15]: https://www.ohchr.org/sites/default/files/documents/publications/guidingprinciplesbusinesshr_en.pdf "OHCHR/Nações Unidas — Guiding Principles on Business and Human Rights: Implementing the UN Protect, Respect and Remedy Framework, 2011. Sustenta dever estatal, responsabilidade empresarial de respeitar, due diligence, impactos adversos, reclamação e reparação."

[16]: https://www.gov.br/fazenda/pt-br/orgaos/spe/taxonomia-sustentavel-brasileira "Ministério da Fazenda, Secretaria de Política Econômica — Taxonomia Sustentável Brasileira, s.d., consulta em 8 de outubro de 2026. Sustenta definição, objetivos estratégicos, 11 objetivos ambientais/econômico-sociais e caráter de classificação de atividades/projetos."

[17]: https://www.conar.org.br/noticias/conar-aprova-regras-eticas-para-coibir-i-greenwashing-i-na-publicidade "CONAR — CONAR aprova regras éticas para coibir Greenwashing na publicidade, 27 de outubro de 2025. Sustenta qualificadores, transparência de metas, distinção entre redução/remoção/compensação e limites de alegações ambientais; é autorregulação."

[18]: https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm "Presidência da República — Lei nº 8.078/1990, Código de Defesa do Consumidor, texto compilado. Sustenta informação clara, publicidade enganosa/abusiva, manutenção de dados técnicos e científicos, ônus da prova e crimes relacionados a claims falsos."

[19]: https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709compilado.htm "Presidência da República — Lei nº 13.709/2018, Lei Geral de Proteção de Dados Pessoais, texto compilado. Sustenta finalidade, adequação, necessidade, transparência, segurança, não discriminação, responsabilização, direitos e comunicação de incidentes."

[20]: https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2013/lei/l12846.htm "Presidência da República — Lei nº 12.846/2013, Lei Anticorrupção, texto vigente. Sustenta responsabilidade objetiva de pessoas jurídicas por atos contra a administração pública, atos lesivos, integridade, denúncia e auditoria como fatores relevantes."

[21]: https://impactfrontiers.org/norms/five-dimensions-of-impact/enterprise-contribution/ "Impact Frontiers — Five dimensions of impact: Contribution, atualização após consulta pública de 2024. Sustenta contrafactual, contribuição, adicionalidade, deadweight, diferença entre outcome e baseline e métodos experimentais, quase-experimentais e baseados em teoria."
