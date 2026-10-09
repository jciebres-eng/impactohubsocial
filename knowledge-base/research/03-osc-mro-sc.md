# OSCs, terceiro setor, MROSC e parcerias — pesquisa para o IMPACTO

**Data de corte da pesquisa:** 08/10/2026.  
**Escopo:** organizações da sociedade civil (OSCs), terceiro setor, Lei nº 13.019/2014 (MROSC), Decreto nº 8.726/2016 e alterações federais, termos de colaboração, fomento e acordo de cooperação, chamamento público, seleção, execução, monitoramento, prestação de contas, transparência, qualificação, OSCIP quando pertinente, fundos patrimoniais e fundos públicos, além da implementação estadual e municipal. O relatório relaciona essas regras ao modelo do release: organizações, projetos, beneficiários, financiadores, evidências e prestação de contas.

Este documento é pesquisa informativa e requisito de produto. **Não é parecer jurídico personalizado**, não determina o enquadramento de uma organização e não substitui a conferência da norma setorial, do ente federativo e do instrumento concreto.

## 1. Escopo e hierarquia das fontes

A Lei nº 13.019/2014 estabelece normas gerais para parcerias entre Administração Pública e OSCs em regime de mútua cooperação. A parceria deve executar atividade ou projeto previsto em plano de trabalho e ser formalizada por termo de colaboração, termo de fomento ou acordo de cooperação. A própria lei exige que as normas setoriais e suas instâncias de pactuação sejam respeitadas. [5]

A lei federal é uma **norma vigente de aplicação nacional**, mas não é um manual único de todos os fluxos. Cada ente federativo edita regulamento, atos, editais, minutas, portais e parâmetros próprios. O Decreto nº 8.726/2016 é o regulamento da Administração Pública federal, atualmente lido com as alterações do Decreto nº 11.948/2024; ele não substitui o decreto estadual ou municipal do ente que celebrar a parceria. [5] [6] [7]

O Manual MROSC aprovado pela Portaria Interministerial SG/MGI/AGU nº 197/2025 é **orientação administrativa federal**, vinculante para o fluxo federal na medida de seus atos e instrumentos, mas não é lei geral nem transforma orientação administrativa em requisito nacional automático. O Manual organiza planejamento, seleção, celebração, execução, monitoramento e prestação de contas; recomenda que o plano seja construído de forma dialogada, mas não dispensa requisitos legais. [8] [9]

A Lei nº 9.790/1999 e seu regulamento tratam de **OSCIP e Termo de Parceria**, regime distinto. O MROSC expressamente não se aplica aos Termos de Parceria celebrados com OSCIP quando atendidos os requisitos da Lei nº 9.790/1999. Uma OSCIP pode aparecer como OSC em um termo de fomento ou colaboração se cumprir as regras aplicáveis, mas a qualificação OSCIP não é pré-requisito geral do MROSC. [5] [10] [11]

A Lei nº 13.800/2019 rege fundos patrimoniais privados e suas organizações gestoras, instituições apoiadas e organizações executoras. A Lei Complementar nº 187/2021 rege CEBAS e imunidade das entidades beneficentes de saúde, educação e assistência social. São regimes de qualificação, tributação ou governança que podem ser pertinentes, mas não equivalem à celebração de uma parceria MROSC. [12] [13]

## 2. Estado atual do release que precisa ser corrigido

O README descreve o v0.26.0 como **base técnica fechada**, não publicada, sem cobrança real e sem provedores de pagamento, fiscal, WhatsApp, mapas ou IA ligados. Também afirma uma arquitetura não custodial, em que eventual taxa da plataforma seria cobrança própria do financiador e não desconto de dinheiro em trânsito. [1] Isso é uma descrição técnica do release; não é comprovação de habilitação, parceria pública ou regularidade de uma OSC.

O release tem objetos genéricos para organização, projeto, financiador, evidência, contabilidade, despesas, compras, indicadores e uma “torre” governamental com estatísticas territoriais. Há contagem agregada de beneficiários por padrão, compartilhamento controlado de documentos e trilha de proveniência. [3] A modelagem é útil para o domínio, mas **não equivale a um processo MROSC**. Um projeto publicado no produto, um financiador interessado, uma evidência com hash ou um estado “Projeto IMPACTO Ready” não substituem edital, plano de trabalho, termo, publicação oficial, gestor público, comissão, análise de contas ou decisão administrativa.

O framework jurídico existente declara onze documentos como **minutas**, nenhum aprovado, e informa que não há integração com Transferegov/SICONV, SIAFI, Portal da Transparência, e-SIC, sistema de compras, assinatura qualificada ou ICP-Brasil. [2] Essa declaração deve continuar aparecendo em qualquer interface jurídica ou de parcerias. Ela impede claims como “contrato público válido”, “aceite oficial” ou “integração Transferegov”.

A documentação de compras implementa cotações e benchmark do próprio pedido, com sinal de possível preço fora do padrão, não de fraude. [4] Isso pode apoiar controles internos da OSC, mas o MROSC federal determina que as compras da OSC com recursos federais adotem métodos usualmente utilizados no setor privado, que a despesa seja compatível com o plano e que existam documentos fiscais ou recibos; não existe uma regra nacional de “três cotações” criada pelo MROSC. [6] [7] A política configurável do produto deve ser rotulada como **controle interno voluntário da organização** ou requisito específico de edital, nunca como obrigação universal.

### Correções de release prioritárias

1. **Separar parceria pública, doação privada, contrato SaaS, patrocínio e investimento social privado.** Somente o primeiro grupo, quando houver Administração Pública e objeto de interesse público, entra no núcleo MROSC. O contrato da plataforma com financiador não é termo de fomento ou colaboração.
2. **Criar um estado jurídico separado de “MROSC não verificado”.** “Projeto IMPACTO Ready” deve indicar apenas critérios do produto e nunca ser apresentado como qualificação legal ou aprovação pública.
3. **Registrar o ente e a jurisdição.** A regra federal não basta para Estado, Distrito Federal ou Município; o fluxo precisa apontar regulamento local, política setorial, edital e plataforma efetivamente utilizados.
4. **Impedir o uso da torre governamental como prova de transparência oficial.** A torre pode ser painel analítico derivado de dados recebidos ou declarados, com procedência e data; não é Portal da Transparência, Mapa das OSC ou Transferegov.
5. **Tratar beneficiários com finalidade e minimização.** A contagem agregada é compatível com exposição pública reduzida, mas a prestação de contas exige demonstrar metas, resultados, satisfação do público-alvo e, quando necessário, comprovação individual ou documental conforme plano e política setorial. Não coletar nominalmente por padrão não significa que toda prestação esteja comprovada.
6. **Não liberar “aceite” de termos MROSC a partir de minuta.** O produto já recusa aceites de documentos legais em rascunho; o mesmo controle deve valer para termos públicos e aditivos até que a fonte oficial e a versão assinada sejam anexadas ou referenciadas.
7. **Classificar taxa da plataforma fora do fluxo financeiro da parceria.** A taxa privada da plataforma não deve aparecer como custo elegível, despesa aprovada ou desconto de repasse, salvo previsão expressa no instrumento e validação do ente. A arquitetura não custodial não resolve, sozinha, a elegibilidade da despesa.

## 3. Mapa de obrigações por fase

### 3.1 Organização, objeto e elegibilidade

Para o MROSC, OSC é, em regra, entidade privada sem fins lucrativos que não distribui resultados, excedentes, dividendos ou parcelas do patrimônio e aplica seus recursos na finalidade social. A definição também alcança certas cooperativas e organizações religiosas quando executam atividade ou projeto de interesse público e social distinto de finalidade exclusivamente religiosa. [5]

A entidade precisa distinguir **existência jurídica**, **natureza organizacional**, **CNPJ**, **finalidade estatutária**, **experiência**, **capacidade técnica e operacional**, **regularidade fiscal** e **qualificações especiais**. Para termos de colaboração e fomento, o estatuto deve prever finalidade de relevância pública e social, destinação patrimonial em caso de dissolução, escrituração segundo princípios e normas contábeis e, salvo ajustes legais, existência mínima, experiência prévia e capacidade técnica. Os prazos legais de existência são, em regra, um ano para Município, dois para Distrito Federal e três para Estado ou União, admitida redução por ato específico quando nenhuma OSC atingir o prazo. [5]

Para acordo de cooperação, a lei reduz os requisitos do art. 33: em regra, exige-se o objetivo institucional de relevância pública e social. Isso não autoriza tratar qualquer memorando ou parceria privada como acordo MROSC; é necessário haver Administração Pública e finalidade pública recíproca. [5]

### 3.2 Escolha do instrumento

- **Termo de colaboração:** iniciativa ou concepção da Administração Pública e transferência de recursos financeiros. É adequado quando a Administração parametriza o projeto ou a atividade que deseja executar em cooperação com uma OSC. [5] [6]
- **Termo de fomento:** iniciativa ou concepção da OSC e transferência de recursos financeiros. É adequado quando a Administração fomenta projeto ou atividade criado ou desenvolvido pela sociedade civil. [5] [6]
- **Acordo de cooperação:** finalidade pública recíproca sem transferência de recursos financeiros. No regime federal, pode ser proposto pela Administração ou pela OSC. Se houver comodato, doação de bens ou compartilhamento patrimonial, aplicam-se controles adicionais e pode ser necessário chamamento. [5] [6] [14]
- **Termo de Parceria:** instrumento do regime OSCIP, não uma quarta modalidade MROSC. O produto deve impedir a mistura de campos, documentos, prazos e decisões desses regimes. [5] [10]

Atividade é contínua ou permanente; projeto é limitado no tempo e produz um resultado ou produto. Essa distinção deve ser armazenada, pois afeta vigência, metas, cronograma e prestação. [5] [14]

### 3.3 Planejamento e plano de trabalho

O plano de trabalho é o eixo da parceria. Deve descrever a realidade e o nexo com atividades, projetos e metas; metas e ações; receitas e despesas previstas; forma de execução; e parâmetros para aferir o cumprimento. [5] No fluxo federal, o Manual MROSC o trata como documento principal para execução, monitoramento, avaliação e prestação de contas e recomenda analisar a qualidade do nexo, não apenas a presença de campos. [9]

O plano precisa suportar, no mínimo:

- problema ou realidade territorial, público-alvo e justificativa;
- objeto, atividade ou projeto e sua classificação;
- metas, produtos, resultados, indicadores quantitativos e qualitativos;
- linha de base, fonte, periodicidade, método de coleta e meio de verificação;
- cronograma físico, equipe, papéis e capacidade operacional;
- receitas, despesas, custos indiretos, contrapartidas e cronograma de desembolso;
- acessibilidade e proteção de grupos vulneráveis;
- riscos, hipóteses, dependências e plano de continuidade;
- governança, monitoramento, visitas, pesquisa de satisfação e prestação de contas;
- tratamento dos bens remanescentes, propriedade intelectual, atuação em rede e encerramento.

O produto não deve preencher automaticamente metas ou “impactos” a partir de uma autodeclaração. Um número pode ser publicado como **declarado** se tiver fonte e data; só pode ser chamado de validado quando houver revisão ou verificação registrada com autoridade, método e escopo.

### 3.4 Chamamento público e seleção

A regra é que termo de colaboração ou fomento seja precedido de chamamento público, com edital amplamente divulgado. A Lei nº 13.019/2014 exige objeto, programação orçamentária, prazos e forma de proposta, critérios e metodologia de julgamento, valor, recursos, minuta do instrumento e acessibilidade. O edital deve respeitar isonomia, publicidade, julgamento objetivo, vinculação ao edital e competitividade; não pode exigir certificação ou titulação estatal como condição geral. [5] [7]

No regime federal, o edital é divulgado no sítio oficial e no Transferegov, o prazo de propostas é de no mínimo trinta dias e a comissão de seleção deve ser designada com ao menos um servidor efetivo ou empregado permanente. A comissão deve declarar impedimento se houver relação recente ou conflito de interesses com participante; o resultado preliminar admite recurso de cinco dias pela plataforma federal. [6] [9]

São exceções legalmente delimitadas:

- emendas parlamentares, conforme art. 29, nas condições legais e regulamentares;
- dispensa por urgência, guerra, calamidade, grave perturbação, programa de proteção ou serviços de educação, saúde e assistência social com credenciamento prévio, nos termos do art. 30;
- inexigibilidade por inviabilidade de competição ou entidade específica nas hipóteses do art. 31;
- acordo de cooperação sem recursos, com atenção ao compartilhamento patrimonial.

 A dispensa ou inexigibilidade **não é atalho sem motivação**. O administrador precisa justificar, publicar o extrato e permitir impugnação no prazo legal; os demais requisitos da lei continuam aplicáveis. [5] [6] O Procedimento de Manifestação de Interesse Social permite que OSCs, movimentos e cidadãos apresentem proposta, mas não garante chamamento nem parceria e não pode ser usado como condição obrigatória para chamamento. [5] [6]

Para fundos específicos, como fundos de direitos da criança e do adolescente, do idoso e de direitos difusos, a seleção pode ser conduzida por conselho gestor, conforme legislação específica e respeitando o MROSC. O produto deve guardar o fundo, conselho, ato de convocação e regra setorial, em vez de classificar tudo como “edital governamental” genérico. [6]

### 3.5 Celebração e execução

Antes da celebração de termo de colaboração ou fomento, a Administração deve verificar habilitação, dotação, compatibilidade do objeto e capacidade, aprovar plano de trabalho e emitir parecer técnico e jurídico. A OSC apresenta regularidade fiscal aplicável, estatuto ou certidão, ata de eleição, relação nominal de dirigentes e prova de funcionamento no endereço declarado. [5]

O instrumento e seu plano anexo precisam congelar objeto, obrigações, valor e desembolso quando houver, contrapartida, vigência, prestação, monitoramento, restituição, bens remanescentes, acesso a documentos e locais, responsabilidades, rescisão e solução administrativa. Só produzem efeitos jurídicos após publicação dos extratos no meio oficial do ente. [5]

A OSC responde pelo gerenciamento administrativo e financeiro e pelos encargos trabalhistas, previdenciários, fiscais e comerciais da execução. O recurso da parceria não pode ser usado para finalidade alheia ao objeto. São admitidos, se previstos e necessários, remuneração da equipe, diárias, custos indiretos, equipamentos e adequação de espaço; o atraso do repasse público não transforma a OSC em devedora de obrigação que ela não poderia pagar com recursos próprios. [5] [6]

No fluxo federal, recursos são vinculados ao plano e não constituem receita própria ou pagamento por serviço. A conta específica, a movimentação pela plataforma e a identificação do beneficiário final da despesa devem ser preservadas. Despesas devem ter nota, comprovante ou recibo com data, valor, dados da OSC e fornecedor; a documentação original deve ser guardada por dez anos. [6] [7]

Os pagamentos e documentos do produto precisam suportar rastreabilidade de fonte, conta, item do plano, fornecedor, beneficiário final, data, documento, valor, rendimento, saldo e eventual rateio. A política de compras do release pode gerar evidência de diligência, mas a aplicação automática de regra privada de três cotações não deve bloquear prestação quando o edital ou regulamento não a exigir.

A atuação em rede é permitida com responsabilidade integral da OSC celebrante, que deve ter mais de cinco anos de CNPJ e capacidade de supervisionar e orientar as executantes. A celebrante deve verificar a regularidade das não celebrantes e comprovar isso na prestação. [5] O produto deve modelar a OSC celebrante, as executantes, o termo de atuação em rede e os repasses internos sem confundir cada entidade com um beneficiário ou fornecedor.

### 3.6 Monitoramento, avaliação e prestação de contas

O MROSC prioriza controle de resultados. A Administração deve designar gestor e comissão de monitoramento e avaliação; o gestor acompanha, fiscaliza, comunica riscos e emite parecer técnico. [5] O monitoramento deve comparar execução física e financeira com plano, metas, indicadores, cronograma, público-alvo, benefícios, impacto econômico ou social, satisfação e sustentabilidade. Esses itens são campos de avaliação, não prova automática de causalidade ou de impacto permanente. [5] [6]

A prestação de contas tem duas responsabilidades: a OSC apresenta contas; a Administração analisa e manifesta conclusão, sem prejuízo dos controles. Deve demonstrar atividades, metas e resultados, com relatório de execução do objeto. Relatório financeiro é necessário quando houver descumprimento injustificado de metas ou indício de irregularidade, conforme a lei e o regulamento; uma plataforma não deve impor a mesma documentação para todos os valores, instrumentos ou entes. [5] [6] [7]

A OSC deve apresentar a prestação em até noventa dias após o término da parceria, ou ao fim de cada exercício quando a parceria exceder um ano, observado o instrumento e o regulamento. No federal, para parcerias superiores a um ano, o Decreto nº 8.726/2016 prevê prestação anual em até trinta dias após cada período de doze meses contado da primeira liberação; a prestação final e prazos de análise também são parametrizados no instrumento. [5] [6]

A conclusão administrativa deve ser registrada como aprovação, aprovação com ressalvas ou rejeição. Rejeição pode decorrer de omissão, descumprimento injustificado, dano ao erário, desfalque ou desvio. A lei prevê saneamento, recurso, ressarcimento e, em hipóteses sem dolo ou fraude, ações compensatórias de interesse público; o produto não pode converter “ressalva” em “fraude” nem “pendência” em “rejeição”. [5] [7]

No regime federal, a análise final é de até 150 dias, prorrogável justificadamente por igual período; a decisão deve ser notificada e admite recurso. A rejeição pode gerar devolução, ações compensatórias, tomada de contas especial, registro no Transferegov/Siafi e sanções. [6] [7] Esses prazos são controles de estado, não cronômetros para inferir aprovação por silêncio.

### 3.7 Transparência e publicidade

A Administração deve manter em seu sítio a relação das parcerias e planos de trabalho até 180 dias após o encerramento. A OSC deve divulgar na internet e em local visível de suas sedes e estabelecimentos as parcerias celebradas. A informação mínima inclui instrumento e data, órgão, OSC e CNPJ, objeto, valor e parcelas, situação da prestação e remuneração total da equipe quando paga com recursos da parceria. [5]

O regulamento federal exige publicidade e transparência na seleção e execução; a Administração mantém dados abertos e relação dos instrumentos com planos, e a OSC divulga as informações até 180 dias depois da prestação final. O Mapa das OSC, gerido pelo Ipea, reúne bases públicas e informações complementares; ele é fonte de descoberta e transparência, não certificação de regularidade de cada projeto. [6] [16]

O release deve oferecer página pública por parceria com procedência, data de atualização, status oficial e link para o portal do ente. Não deve replicar CPF, endereço residencial, dados de saúde, crianças ou identificadores de beneficiários sem base e necessidade. A exceção legal de transparência para programas de proteção não autoriza ocultar toda a parceria: ela deve ser aplicada conforme risco e regulamento. [5] [6]

## 4. Qualificações e regimes correlatos

### OSCIP e Termo de Parceria

Para OSCIP, a pessoa jurídica privada sem fins lucrativos deve estar constituída e em funcionamento regular há pelo menos três anos e atender ao estatuto e finalidades da Lei nº 9.790/1999. O estatuto deve conter princípios de legalidade, impessoalidade, moralidade, publicidade, economicidade e eficiência, controles de gestão, conselho fiscal, regras de dissolução e prestação de contas. [10] O Ministério da Justiça informa que a qualificação é concedida após apresentação dos documentos e é útil para Termos de Parceria. [11]

**Requisito de produto:** guardar `qualification_type=OSCIP`, órgão emissor, número, data, vigência, escopo, situação e prova. O produto não deve exibir “OSCIP” apenas porque a entidade se declarou sem fins lucrativos. Deve mostrar a diferença entre “OSC”, “OSCIP”, “CEBAS” e “parceira em instrumento MROSC”.

### CEBAS

A LC nº 187/2021 define entidade beneficente como pessoa jurídica privada sem fins lucrativos que presta serviços de assistência social, saúde ou educação e é certificada. Entre os requisitos estão não distribuir resultados, aplicar recursos no país, manter regularidade fiscal, escrituração contábil, guarda documental por dez anos, auditoria quando ultrapassado o limite legal e destinação patrimonial compatível. [13]

CEBAS não deve ser inferido por uma parceria ou usado como promessa de imunidade. A plataforma pode armazenar a certificação e seus atos, com autoridade, área, período e processo, mas qualquer claim tributário depende da certificação vigente e da regra fiscal aplicada.

### Fundos patrimoniais e fundos públicos

A Lei nº 13.800/2019 permite constituir fundos patrimoniais para arrecadar, gerir e destinar doações privadas a finalidades de interesse público. A organização gestora é associação ou fundação privada sem fins lucrativos dedicada ao fundo; a instituição apoiada e a organização executora têm papéis próprios. O patrimônio deve ser contábil, administrativo e financeiramente segregado, com regras de governança, investimento, transparência e prestação. [12]

O produto deve separar `fundo_patrimonial`, `organização_gestora`, `instituição_apoiada`, `organização_executora`, `doação`, `principal`, `rendimento`, `instrumento_de_parceria` e `termo_de_execução`. Não deve tratar uma doação privada ao fundo como repasse MROSC nem tratar rendimento patrimonial como orçamento público.

Fundos públicos setoriais podem financiar chamamentos e ter conselho gestor, como previsto no regulamento federal; isso é diferente de fundo patrimonial privado. A fonte do dinheiro, o conselho, a lei orçamentária e o regime de prestação precisam ser registrados separadamente. [6]

## 5. Relação com o modelo de organizações, projetos, beneficiários, financiadores e contas

### Organização

A organização é o sujeito jurídico e operacional. O registro mínimo deve incluir razão social, nome, CNPJ, natureza jurídica, estatuto vigente, endereço institucional, dirigentes e poderes de representação, data de constituição, áreas de atuação, existência de filiais, OSCIP/CEBAS se houver, regularidade e documentos com validade. Relações em rede precisam de nós separados para celebrante e executantes.

A conta da pessoa usuária deve ser ligada à organização por função e mandato. Dirigente, representante legal, contador, gestor do projeto e financiador não são o mesmo papel. A aprovação em quatro olhos existente no release é uma boa prática interna, mas não substitui comissão de seleção, gestor público ou autoridade competente.

### Projeto e atividade

O projeto é a unidade de execução e evidência, mas, no MROSC, o projeto deve ser filho de uma parceria e de um plano de trabalho. Deve conter objeto, vigência, metas, indicadores, orçamento, desembolsos, público-alvo, território, equipe, fornecedores, evidências, riscos, alterações e resultado da prestação. Projetos privados podem existir sem parceria pública; nesse caso, o regime e o status precisam indicar “fora do MROSC”.

### Beneficiário

Há três conceitos que não devem ser misturados:

1. **Público-alvo ou beneficiário da política:** grupo que a parceria pretende alcançar, com definição de território, elegibilidade, quantidade e proteção.
2. **Pessoa atendida:** pode ser contagem agregada, unidade pseudonimizada ou registro nominal, conforme plano, finalidade e base legal.
3. **Beneficiário final de despesa:** pessoa física ou jurídica que recebeu pagamento, obrigação diferente da pessoa beneficiária da política.

O release hoje favorece contagem agregada. Essa deve continuar como padrão público, com campos de método, período, deduplicação, fonte, incerteza, consentimento ou outra base aplicável. Para prestação pública, o sistema deve permitir anexar lista ou documento protegido quando o edital ou órgão exigir, sem exibir esses dados em página pública. O produto não pode declarar “alcançou 1.000 pessoas” sem método e evidência compatíveis.

### Financiador

O financiador precisa ser classificado como Administração Pública, fundo público, empresa, fundação, fundo patrimonial, doador, patrocinador ou contratante. A mesma organização pode financiar um projeto privado e ser órgão concedente em outro contexto, mas cada relação tem instrumento, moeda, fonte, restrições e prestação próprios. A matriz econômica do release deve separar:

- valor autorizado no instrumento;
- parcelas efetivamente liberadas;
- rendimentos;
- recursos próprios e contrapartida voluntária ou exigida;
- outras fontes e rateios;
- despesas executadas e saldo;
- valores devolvidos ou compensados;
- taxa privada da plataforma, fora do recurso público salvo previsão válida.

### Prestação de contas

A conta é por parceria e plano de trabalho, não apenas por organização. O produto deve vincular cada evidência ao resultado ou à despesa e preservar o ciclo `preparação → seleção → celebração → execução → monitoramento → prestação → análise → decisão → recurso/saneamento → encerramento`.

A documentação deve registrar quem apresentou, quem analisou, qual autoridade decidiu, data, versão, parecer, diligência, resposta, recurso, sanção e resultado. “Prestação enviada” não é “prestação aprovada”; “aprovação com ressalva” não é “regular sem ressalva”; “dado autodeclarado” não é “validado”.

## 6. Requisitos de produto

### P0 — núcleo obrigatório antes de qualquer claim MROSC

- Cadastro de ente público, órgão, política setorial, jurisdição e portal oficial.
- Registro de parceria com tipo de instrumento, regime jurídico, base legal, objeto, vigência, valor, fonte, plano de trabalho e publicação oficial.
- Fluxo de chamamento com edital, programação orçamentária, critérios, pontuação, propostas, comissão, impedimentos, resultado, recurso e homologação.
- Fluxo separado de dispensa, inexigibilidade, emenda parlamentar e acordo de cooperação, com artigo, fato, motivação, decisão, publicidade e impugnação.
- Checklist de elegibilidade da OSC com regra de existência parametrizada por ente, experiência, capacidade, estatuto, dirigentes, certidões e endereço.
- Instrumento versionado e imutável após assinatura; aditivo como versão nova, com invalidade das aprovações anteriores quando o conteúdo relevante mudar.
- Plano de trabalho estruturado com metas, indicadores, orçamento, cronograma, meio de verificação, público-alvo e acessibilidade.
- Prestação de contas com relatório de objeto, relatório financeiro condicional, documentos, visita técnica, monitoramento, diligência, parecer e decisão.
- Transparência pública com snapshot, data de vigência, status e link à fonte oficial.
- Auditoria append-only com correção por evento, segregação de funções, revisão humana e exportação.

### P1 — dados e integração

- Integração ou importação verificável de Transferegov quando o âmbito for federal; até haver integração real, usar `fonte_externa_url`, `external_id`, data de coleta, hash e status “não sincronizado”.
- Conciliação de CNPJ e nomes de órgãos, OSCs, conselhos, fundos e programas sem substituir a confirmação da autoridade competente.
- Importação do Mapa das OSC e de portais estaduais/municipais como descoberta e referência, com indicação de fonte, periodicidade e conflito; nunca como prova única de habilitação.
- Exportação de dados abertos compatível com o formato do ente, sem expor dados pessoais ou material protegido.
- Validade e alertas para certidões, OSCIP, CEBAS, estatuto, mandato, instrumento, plano, aditivo, prestação, recurso e sanção.

### P2 — usabilidade e proteção

- Formulários que mostram a regra aplicável antes de exigir documento; acessibilidade e linguagem simples.
- Página pública separada do espaço restrito de prestação; anonimização ou agregação configurável por projeto e risco.
- Explicação de “declarado”, “documentado”, “revisado”, “validado”, “aprovado”, “com ressalva”, “rejeitado” e “não informado”.
- Exportação de dossiê por parceria, com índice, hash de arquivos, versões, linha do tempo e lista de lacunas.
- Canal de correção, contraditório e resposta da OSC; o produto não pode emitir sanção ou rejeição por algoritmo.

## 7. Requisitos de dados mínimos

O esquema deve conter, no mínimo, as entidades abaixo.

- `legal_regime`: MROSC, OSCIP, CEBAS, fundo patrimonial, contrato privado ou outro; fonte e validade.
- `jurisdiction`: União, Estado, DF, Município, órgão, política setorial, regulamento, portal oficial e plataforma.
- `organization`: CNPJ, natureza, estatuto, objetivos, dirigentes, mandato, endereço institucional, regularidade e capacidade.
- `qualification`: tipo, órgão emissor, ato, número, data inicial/final, situação e documentos.
- `fund`: fundo público ou patrimonial, lei/ato, conselho gestor, gestora, apoiada, executora e segregação patrimonial.
- `call`: edital, tipo, publicação, prazo mínimo, objeto, orçamento, critérios, metodologia, pesos, acessibilidade e regras de recurso.
- `proposal` e `selection`: OSC, plano proposto, notas, justificativas, comissão, impedimentos, resultado, recurso e homologação.
- `partnership`: instrumento, partes, objeto, atividade/projeto, plano, vigência, valor, fonte, desembolso, contrapartida, bens, propriedade intelectual e publicação.
- `network_execution`: celebrante, não celebrantes, termo de atuação em rede, regularidade, supervisão, repasses e responsabilidades.
- `milestone_indicator`: linha de base, meta, unidade, método, fonte, período, valor declarado, valor revisado, revisão e lacunas.
- `beneficiary_group`: público-alvo, território, faixa agregada, contagem, método, período, proteção, origem e nível de exposição.
- `expense_payment`: item do plano, fornecedor, beneficiário final da despesa, documento, banco/conta, data, valor, rateio, fonte, rendimento e evidência.
- `monitoring_report` e `visit`: gestor, comissão, data, achados, metas, riscos, satisfação, impactos, sustentabilidade, recomendação e resposta.
- `accountability`: tipo, período, apresentação, relatórios, documentos, diligências, análise, decisão, parecer, recurso, saneamento e restituição.
- `transparency_record`: conteúdo público, autoridade de publicação, URL, snapshot, data inicial/final, redaction_reason e exceção de segurança.
- `sanction`: infração apurada, defesa, decisão, autoridade, duração, recurso, ressarcimento e fonte oficial.
- `provenance`: órgão/autor, título, data, URL, artigo/página, hash, data de consulta, classificação e escopo do que a fonte sustenta.

Documentos legais, planos, editais, prestações e decisões devem ser imutáveis por versão. Metadados corrigíveis devem gerar evento; arquivo aceito deve manter hash. A tabela de beneficiários individuais, se necessária, deve ficar em área protegida, segregada do painel público e sujeita a retenção e eliminação conforme a finalidade.

## 8. Testes e controles de conformidade do produto

### Testes jurídicos determinísticos

- Termo de colaboração ou fomento sem plano, objeto, vigência, partes, valor quando aplicável, cronograma, prestação, monitoramento e publicação deve ser recusado.
- Acordo de cooperação com transferência financeira deve ser recusado ou reclassificado; com compartilhamento patrimonial, deve exigir o caminho correspondente.
- Seleção de termo de colaboração/fomento sem chamamento ou exceção fundamentada deve bloquear a celebração.
- Dispensa/inexigibilidade sem artigo, justificativa, publicação e janela de impugnação deve ficar pendente, não aprovada.
- Edital sem programação, objeto, prazo, critério, metodologia, valor, recurso, minuta e acessibilidade deve falhar no checklist.
- OSC sem estatuto/objetivo, CNPJ, existência aplicável, experiência, capacidade, dirigentes, certidões ou endereço deve ficar “não habilitada” ou “pendente”, nunca “qualificada”.
- OSCIP/CEBAS ausente não pode bloquear MROSC sem regra setorial expressa; presente não pode provar automaticamente elegibilidade.

### Testes de resultados e contas

- Uma despesa fora do objeto não pode ser marcada como elegível sem justificativa e decisão humana.
- Receita, rendimento, contrapartida, outra fonte e taxa devem reconciliar com o plano e o saldo; duplicidade de fonte no mesmo rateio deve falhar.
- Prestação apresentada, em análise, diligenciada, aprovada, aprovada com ressalvas, rejeitada e recurso são estados distintos e monotônicos por versão.
- Relatório financeiro deve ser solicitado quando houver descumprimento injustificado ou indício de irregularidade, conforme regime; não gerar rejeição automática.
- Prazos devem ser calculados pelo instrumento/regulamento: 90 dias legais como referência geral, 30 dias para prestação anual federal conforme decreto, 150 dias para análise federal, sempre com prorrogação, diligência e regra local explicitadas.
- “Resultado”, “impacto”, “satisfação” e “sustentabilidade” exigem fonte, método, período, escopo e incerteza; nunca transformar ausência em zero.

### Controles de integridade, transparência e privacidade

- Comissão de seleção, gestor, revisor e autoridade não podem ser a mesma pessoa quando o regime exigir segregação; conflito declarado remove o membro e registra substituto.
- URL pública deve mostrar versão, fonte, órgão, data, objeto, valores, parcelas, situação das contas e remuneração exigida, com redaction documentada.
- Snapshot público deve continuar disponível pelo período normativo; versão atualizada não apaga o registro histórico.
- Beneficiário individual não deve aparecer na página pública por padrão; a plataforma deve testar anonimização, controle de acesso, exportação e eliminação conforme finalidade.
- Toda evidência externa deve mostrar `fonte`, `capturado_em`, `autoridade`, `título`, `data`, `hash` e `o_que_sustenta`.
- Dado autodeclarado nunca pode receber selo de validado sem registro de revisão; OCR e IA, se implementados depois, devem gerar rascunho e pedir confirmação humana.
- Alertas de atraso, risco, denúncia e sanção devem distinguir denúncia, suspeita, irregularidade apurada e consequência. Não converter sinal de risco em acusação.

## 9. Claims proibidos ou que exigem comprovação específica

O produto e o material comercial não devem afirmar, sem fonte oficial, revisão competente e escopo:

- “a organização é regular, habilitada, qualificada, OSCIP, CEBAS ou apta a receber recursos”;
- “o projeto está aprovado”, “MROSC compliant”, “Projeto IMPACTO Ready é certificação” ou “a prestação foi aprovada”;
- “a plataforma é Transferegov, SICONV, Portal da Transparência, Mapa das OSC ou sistema oficial do governo”;
- “há integração oficial” quando o release ainda declara ausência dessa integração;
- “o chamamento foi dispensado corretamente”, “a parceria é inexigível” ou “a despesa é elegível” sem ato e decisão da Administração;
- “o impacto foi comprovado”, “o número de beneficiários é validado”, “não houve fraude” ou “há causalidade” a partir de autodeclaração, indicador ou benchmark;
- “há imunidade, isenção, benefício fiscal ou dedução para doador/OSC” sem enquadramento e ato vigentes;
- “a taxa da plataforma é custo de projeto, custo indireto ou despesa pública elegível” sem previsão e decisão do instrumento;
- “a prestação de contas está regular” apenas porque foi enviada, não há alerta ou o prazo administrativo terminou;
- “a plataforma garante a contratação, o repasse, o pagamento ou a continuidade de uma parceria”;
- “a OSC não precisa guardar originais, publicar parceria, abrir conta específica ou cumprir regra local”;
- “uma pesquisa de satisfação ou k-anonimato prova impacto” — são controles de proteção ou evidências parciais, não conclusão jurídica.

Claims permitidos, com qualificador, incluem: “organiza evidências para uma possível prestação”, “exibe dados declarados com procedência”, “aplica checklist configurável”, “não custodia recursos no release atual”, “oferece controle interno de cotações” e “não substitui o processo oficial”.

## 10. Lacunas e plano de correção

1. **Módulo jurídico MROSC ausente:** implementar o ciclo de parceria e os estados acima antes de vender o produto a órgãos ou OSCs como solução de prestação.
2. **Regra local incompleta:** criar catálogo versionado por União, Estado, DF e Município, incluindo decreto, órgão, política setorial, portal, plataforma e minuta. O exemplo mineiro diferencia instrumentos e seleção; o guia municipal de São Paulo alerta para regras setoriais e adota rotinas próprias de prestação. [14] [15]
3. **Transferegov ausente:** decidir se haverá integração real, exportação compatível ou apenas organização documental. Até lá, manter rótulo “sem integração”.
4. **Fonte oficial e status de publicação:** ingerir ato, edital, resultado, termo, aditivo, contas e sanção com hash e URL; não usar cópia do usuário como única prova de publicação.
5. **Beneficiários e proteção:** formalizar modelo de agregação, finalidade, base jurídica, autorização de acesso, retenção e exceções para dados protegidos, especialmente crianças, saúde, violência e vulnerabilidade.
6. **Qualificação e certidões:** separar declaração da OSC, consulta automática, documento válido e decisão humana; implementar validade e histórico.
7. **Contabilidade:** alinhar exportação e relatórios às normas contábeis aplicáveis e à ITG 2002 para entidades sem finalidade de lucros; o CFC informa que essas entidades devem manter contabilidade regular e evidenciação das informações exigidas. [17]
8. **Legal review:** as minutas do release continuam sem revisão jurídica, e textos específicos de MROSC, termos públicos, privacidade, taxa e responsabilidades precisam de revisão antes de aceite ou cobrança. [2]
9. **Claims e treinamento:** criar catálogo de linguagem proibida, teste de interface e revisão humana de conteúdo regulatório; conteúdo oficial deve ter fonte e data, coerente com o próprio hub do release. [2] [3]
10. **Cobertura de fundos:** modelar fundo patrimonial privado, fundo público setorial e fundo de direitos separadamente; impedir que toda captação seja exibida como repasse público.

## 11. Síntese operacional

O MROSC é um regime de **parceria pública baseada em plano, seleção, execução, controle de resultados e prestação**, não um selo de impacto nem um contrato privado de financiamento. Para o IMPACTO, o caminho seguro é usar a capacidade existente de organizações, projetos, indicadores, despesas, documentos, proveniência, governança e painéis como infraestrutura de evidência, mas adicionar jurisdição, instrumento oficial, chamamento/exceção, plano de trabalho, papéis públicos, publicação, contas e decisões.

A regra de produto deve ser: **nenhuma afirmação jurídica além daquilo que a fonte oficial e o estado do processo comprovam**. O painel pode tornar o ciclo legível e auditável; não pode substituir a Administração, o conselho gestor, a comissão, o contador, o advogado, o órgão de controle ou o portal oficial.

## Referências

[1]: file:///home/ubuntu/impacto-trust-knowledge-v0.26.0/README.md "Plataforma Impacto — v0.26.0, README do release"

**Órgão/autor:** equipe do release Impacto. **Título:** “Plataforma Impacto — v0.26.0”. **Data:** release v0.26.0, sem data editorial única; consultado em 08/10/2026. **Natureza:** documentação técnica interna. **Sustenta:** estado declarado do release, ausência de publicação e provedores, arquitetura não custodial, torres, beneficiários agregados e critérios “Impacto Ready”.

[2]: file:///home/ubuntu/impacto-trust-knowledge-v0.26.0/docs/LEGAL_FRAMEWORK.md "Arcabouço legal: onze minutas, nenhuma vigente"

**Órgão/autor:** equipe do release Impacto. **Título:** “Arcabouço legal: onze minutas, nenhuma vigente”. **Data:** v0.17.0, consultado em 08/10/2026. **Natureza:** documentação técnica interna. **Sustenta:** documentos legais em rascunho, bloqueio de aceite, ausência de ICP-Brasil e de integrações oficiais e limites contratuais declarados.

[3]: file:///home/ubuntu/impacto-trust-knowledge-v0.26.0/docs/LGPD.md "LGPD — como o código implementa privacidade"

**Órgão/autor:** equipe do release Impacto. **Título:** “LGPD — como o código implementa privacidade”. **Data:** v0.7.0, consultado em 08/10/2026. **Natureza:** documentação técnica interna; não declaração de conformidade. **Sustenta:** contagem agregada de beneficiários, controles de acesso, compartilhamento com financiador, estatísticas territoriais, retenção e lacunas de base legal/RIPD.

[4]: file:///home/ubuntu/impacto-trust-knowledge-v0.26.0/docs/PROCUREMENT.md "Compras, cotações e benchmark"

**Órgão/autor:** equipe do release Impacto. **Título:** “Compras, cotações e benchmark”. **Data:** v0.8.0, consultado em 08/10/2026. **Natureza:** documentação técnica interna; controle voluntário da plataforma. **Sustenta:** política configurável de cotações, benchmark interno e rótulo de preço possivelmente fora do padrão, sem alegação de fraude.

[5]: https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2014/lei/l13019compilado.htm "Lei nº 13.019, de 31 de julho de 2014 — texto compilado"

**Órgão/autor:** Presidência da República, Casa Civil, Subchefia para Assuntos Jurídicos. **Título:** “Lei nº 13.019, de 31 de julho de 2014”. **Data:** 31/07/2014; texto consultado em 08/10/2026. **Natureza:** lei federal vigente, com alterações compiladas. **Sustenta:** definição de OSC, instrumentos, atividade/projeto, princípios, transparência, requisitos, chamamento e exceções, plano, formalização, despesas, monitoramento, prestação, sanções, plataforma e exclusão do Termo de Parceria OSCIP.

[6]: https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2016/decreto/d8726.htm "Decreto nº 8.726, de 27 de abril de 2016 — texto atualizado"

**Órgão/autor:** Presidência da República, Casa Civil, Subchefia para Assuntos Jurídicos. **Título:** “Decreto nº 8.726, de 27 de abril de 2016”. **Data:** 27/04/2016; texto consultado em 08/10/2026. **Natureza:** regulamento federal vigente, lido com alterações posteriores. **Sustenta:** Transferegov, fluxos federais, chamamento, comissão, recursos, pagamentos, beneficiário final, atuação em rede, monitoramento, contas, sanções, transparência, Mapa das OSC e fundos específicos.

[7]: https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2024/Decreto/D11948.htm "Decreto nº 11.948, de 12 de março de 2024"

**Órgão/autor:** Presidência da República, Casa Civil, Secretaria Especial para Assuntos Jurídicos. **Título:** “Decreto nº 11.948, de 12 de março de 2024”. **Data:** 12/03/2024; consultado em 08/10/2026. **Natureza:** decreto federal vigente que altera o Decreto nº 8.726/2016. **Sustenta:** alterações de 2024 em instrumentos, chamamento, acessibilidade, contrapartida, Transferegov, pagamentos, monitoramento, relatório financeiro, prazos e sanções.

[8]: https://www.gov.br/transferegov/pt-br/legislacao/portarias/portaria-interministerial-sg-mgi-agu-no-197-de-11-de-agosto-de-2025 "Portaria Interministerial SG/MGI/AGU nº 197, de 11 de agosto de 2025"

**Órgãos/autores:** Secretaria-Geral da Presidência da República, Ministério da Gestão e da Inovação em Serviços Públicos e Advocacia-Geral da União. **Título:** “Portaria Interministerial SG/MGI/AGU nº 197, de 11 de agosto de 2025”. **Data:** 11/08/2025; publicada em 12/08/2025; consultada em 08/10/2026. **Natureza:** ato administrativo federal. **Sustenta:** aprovação, divulgação e alcance orientador do Manual MROSC federal.

[9]: https://www.gov.br/transferegov/pt-br/legislacao/portarias/MANUALMROSCDoPlanejamentoPrestaodeContasreduzido13082025.pdf "Manual MROSC — Do Planejamento à Prestação de Contas"

**Órgãos/autores:** Secretaria-Geral da Presidência da República, Ministério da Gestão e da Inovação em Serviços Públicos e Advocacia-Geral da União. **Título:** “Manual MROSC — Do Planejamento à Prestação de Contas”. **Data:** edição aprovada em agosto de 2025; consultada em 08/10/2026. **Natureza:** manual/orientação administrativa federal. **Sustenta:** etapas federais, construção dialogada do plano, seleção, recursos, documentação de habilitação e distinção entre presença formal e qualidade do plano.

[10]: https://www.planalto.gov.br/ccivil_03/leis/l9790.htm "Lei nº 9.790, de 23 de março de 1999 — OSCIP e Termo de Parceria"

**Órgão/autor:** Presidência da República, Casa Civil, Subchefia para Assuntos Jurídicos. **Título:** “Lei nº 9.790, de 23 de março de 1999”. **Data:** 23/03/1999; texto consultado em 08/10/2026. **Natureza:** lei federal vigente, com alterações compiladas. **Sustenta:** qualificação OSCIP, prazo de três anos, finalidades, estatuto, prestação de contas e Termo de Parceria como regime distinto.

[11]: https://www.gov.br/mj/pt-br/assuntos/seus-direitos/entidades-sociais/oscip-1 "OSCIP — Organização da Sociedade Civil de Interesse Público"

**Órgão/autor:** Ministério da Justiça e Segurança Pública. **Título:** “OSCIP”. **Data:** sem data editorial única visível; consultado em 08/10/2026. **Natureza:** orientação institucional/serviço público. **Sustenta:** procedimento de qualificação, exigência de três anos e finalidade prática da certidão para Termos de Parceria.

[12]: https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2019/lei/l13800.htm "Lei nº 13.800, de 4 de janeiro de 2019 — fundos patrimoniais"

**Órgão/autor:** Presidência da República, Casa Civil, Subchefia para Assuntos Jurídicos. **Título:** “Lei nº 13.800, de 4 de janeiro de 2019”. **Data:** 04/01/2019; texto consultado em 08/10/2026. **Natureza:** lei federal vigente. **Sustenta:** fundo patrimonial, organização gestora, instituição apoiada, organização executora, segregação patrimonial, governança, transparência e prestação.

[13]: https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp187.htm "Lei Complementar nº 187, de 16 de dezembro de 2021 — CEBAS"

**Órgão/autor:** Presidência da República, Casa Civil, Subchefia para Assuntos Jurídicos. **Título:** “Lei Complementar nº 187, de 16 de dezembro de 2021”. **Data:** 16/12/2021; texto consultado em 08/10/2026. **Natureza:** lei complementar federal vigente. **Sustenta:** entidade beneficente, CEBAS, áreas de saúde/educação/assistência, requisitos contábeis, guarda documental, auditoria e limites da certificação/imunidade.

[14]: https://manual.sigconsaida.mg.gov.br/definicoes-gerais/tipos-de-instrumentos/parcerias-mrosc/o-que-sao-parcerias "O que são parcerias? — Manual SIGCON-Saída"

**Órgão/autor:** Governo do Estado de Minas Gerais. **Título:** “O que são parcerias?”. **Data:** página atualizada em 30/04/2024; consultada em 08/10/2026. **Natureza:** orientação administrativa estadual. **Sustenta:** implementação local, distinção de instrumentos, regra de chamamento e peculiaridade do acordo de cooperação com compartilhamento patrimonial.

[15]: https://prefeitura.sp.gov.br/documents/d/assistencia_social/guia-de-parcerias-mrosc-pdf-1 "Guia de Parcerias MROSC"

**Órgão/autor:** Prefeitura do Município de São Paulo. **Título:** “Guia de Parcerias MROSC”. **Data:** edição sem data editorial única visível; consultada em 08/10/2026. **Natureza:** guia administrativo municipal. **Sustenta:** necessidade de consultar regras setoriais locais, rotinas municipais de monitoramento, transparência, prestação e análise simplificada conforme valor e instrumento.

[16]: https://mapaosc.ipea.gov.br/sobre "Sobre o Mapa das OSC"

**Órgão/autor:** Instituto de Pesquisa Econômica Aplicada (Ipea). **Título:** “Sobre o Mapa”. **Data:** sem data editorial única visível; consultado em 08/10/2026. **Natureza:** plataforma institucional e base pública colaborativa. **Sustenta:** finalidade de transparência, integração de bases, apoio a gestores e pesquisas, e distinção entre transparência/cadastro e certificação jurídica.

[17]: https://cfc.org.br/tecnica/perguntas-frequentes/entidades-sem-finalidade-de-lucros/ "Entidades sem Finalidade de Lucros — perguntas frequentes"

**Órgão/autor:** Conselho Federal de Contabilidade. **Título:** “Entidades sem Finalidade de Lucros”. **Data:** sem data editorial única visível; consultado em 08/10/2026. **Natureza:** orientação técnica institucional sobre normas contábeis. **Sustenta:** contabilidade regular, observância das Normas Brasileiras de Contabilidade e ITG 2002, evidenciação e prestação de contas de entidades sem finalidade de lucros.
