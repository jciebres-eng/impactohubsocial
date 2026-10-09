# Compras públicas, inovação e govtech: possibilidade abstrata e rota real

**Release analisado:** Plataforma Impacto v0.26.0  
**Data da pesquisa:** 8 de outubro de 2026  
**Natureza:** pesquisa jurídica, regulatória, de governança, dados e produto. Não é parecer personalizado nem substitui análise do órgão contratante, assessoria jurídica, área de TIC, autoridade competente ou controle interno.

## Escopo e chave de leitura

Este relatório cobre a relação entre a Plataforma Impacto, compras públicas, inovação e govtech. O recorte inclui a Lei nº 14.133/2021, a Lei Complementar nº 182/2021 e o Contrato Público para Solução Inovadora (CPSI), diálogo competitivo, contratação de TIC e nuvem, Portal Nacional de Contratações Públicas (PNCP), Plano de Contratações Anual (PCA), Documento de Formalização da Demanda (DFD), Estudo Técnico Preliminar (ETP), Termo de Referência (TR), critérios de aceite, dados, segurança, reversibilidade e continuidade.

A análise separa quatro planos que não devem ser misturados:

1. **Norma vigente:** lei, decreto ou ato normativo aplicável ao ente, órgão e procedimento concreto.
2. **Orientação administrativa ou material institucional:** guia do TCU, modelo do Governo Digital, curso, template ou página operacional. Pode orientar a instrução, mas não substitui a lei e nem é automaticamente aplicável a todo ente.
3. **Padrão voluntário ou hipótese editorial de produto:** desenho recomendado para tornar o processo auditável e mais seguro. Não é certificação nem autorização administrativa.
4. **Possibilidade abstrata versus rota real:** a lei pode permitir uma modalidade, mas a contratação só existe quando há demanda pública documentada, enquadramento, orçamento, autoridade competente, instrução processual, edital ou contratação direta cabível, seleção, contrato e publicação quando exigida.

A conclusão prática é direta: o release pode apoiar **estruturação, evidência, governança e acompanhamento** de um processo público, mas não pode se apresentar como PNCP, sistema oficial de compras, autoridade certificadora ou garantia de contratação.

## Estado atual do release que precisa ser corrigido

A documentação local descreve a v0.26.0 como **base técnica fechada**, não publicada em loja ou domínio, sem provedor ligado para pagamento, fiscal, WhatsApp, mapas ou IA; Android/iOS ainda não foram construídos e não há cobrança real possível. O release tem contrato versionado, obrigações derivadas, aceite a quatro olhos, matriz de distribuição e duas torres de controle. A torre governamental hoje é descrita como território → programas → editais → OSCs → projetos → recursos → indicadores → atrasos e riscos, e não como um fluxo jurídico completo de contratação pública. [1]

O `docs/PROCUREMENT.md` existente é um módulo de **compras, cotações e benchmark por organização**. Ele prevê política configurável, em regra três cotações, mediana, sinal de preço possivelmente fora do padrão e segunda aprovação. O próprio documento informa que não é base de preços de mercado nem validação de orçamento: compara apenas as cotações do pedido. [2] Isso é compatível com um controle interno privado ou preparatório, mas não equivale à pesquisa de preços exigida para a Administração Federal pela IN SEGES/ME nº 65/2021, que exige documento com objeto, responsáveis, fontes, série coletada, método, justificativas e memória de cálculo, priorizando sistemas oficiais e contratações similares. [16]

O `docs/LEGAL_FRAMEWORK.md` registra que os onze documentos legais são **minutas**, inclusive o documento B2G, sem aceite registrável enquanto não forem aprovados e vigentes. Também registra que o release não tem assinatura qualificada, ICP-Brasil, gov.br, certificado digital ou biometria, não integra SICONV/Transferegov, SIAFI, Portal da Transparência, e-SIC ou sistema de compras, e não possui SLA contratado ou disponibilidade medida. [3] O `docs/LGPD.md` registra controles técnicos e pendências jurídicas, como base legal, retenção efetiva, RIPD/DPIA, contrato de operador e canal do encarregado. [4]

### Correção de posicionamento

A descrição correta para este domínio é:

> **Espaço de preparação e acompanhamento de evidências para compras públicas e inovação, sujeito à validação do órgão e ao sistema oficial aplicável.**

Não é correto dizer que a plataforma “faz a contratação”, “homologa a solução”, “garante conformidade com a Lei nº 14.133/2021”, “publica no PNCP” ou “é a torre oficial do governo” sem que exista a integração, autorização, trilha de auditoria e teste operacional correspondentes. A alta administração do órgão é responsável pela governança das contratações, pelos riscos e pelos controles internos; uma interface privada não desloca essa responsabilidade. [5]

## Arquitetura jurídica da compra pública de inovação

### Lei nº 14.133/2021: regra geral, planejamento e governança

A Lei nº 14.133/2021 estabelece normas gerais de licitação e contratação para as Administrações Públicas diretas, autárquicas e fundacionais da União, dos Estados, do Distrito Federal e dos Municípios. [6] Seus princípios incluem planejamento, transparência, eficácia, segregação de funções, motivação, vinculação ao edital, julgamento objetivo, competitividade, economicidade e desenvolvimento nacional sustentável. [5]

A contratação pública tem, entre seus objetivos, selecionar proposta apta a gerar o resultado mais vantajoso considerando o ciclo de vida, assegurar tratamento isonômico e justa competição, evitar sobrepreço e superfaturamento e **incentivar a inovação e o desenvolvimento nacional sustentável**. A alta administração deve implantar processos, estruturas de gestão de riscos e controles internos para avaliar, direcionar e monitorar licitações e contratos. [5]

Isso permite que uma solução govtech seja objeto de contratação comum quando o objeto e seus padrões de desempenho podem ser definidos objetivamente, ou de contratação com técnica e preço quando a qualidade técnica além do mínimo for relevante. Não autoriza, por si só, transformar qualquer software inovador em contratação direta, diálogo competitivo ou CPSI. A escolha do instrumento depende da necessidade, do mercado, do grau de definição do objeto, do risco e da instrução.

O caminho regular deve conectar DFD, PCA, ETP, pesquisa de preços, TR, edital, avaliação, contrato, execução, recebimento, pagamento e publicidade. O Decreto nº 10.947/2022 determina, no âmbito federal regulamentado, que o PCA racionalize contratações, evite fracionamento, alinhe a demanda ao planejamento e sinalize intenções ao mercado. O PCA aprovado é disponibilizado automaticamente no PNCP; demandas não previstas exigem revisão justificada. [10]

O ETP é a primeira etapa do planejamento. Deve evidenciar o problema público e a melhor solução, avaliar viabilidade técnica, socioeconômica e ambiental, alinhar-se ao PCA e conter, entre outros elementos, necessidade, requisitos, levantamento de mercado, alternativas, solução, quantidades e memórias de cálculo, valor estimado, parcelamento, contratações correlatas, resultados, providências prévias, impactos ambientais e posicionamento conclusivo. O levantamento pode considerar contratações similares, tecnologias novas, audiência ou consulta pública. [11]

O TR traduz o planejamento para uma contratação executável. Deve definir objeto e prazo, requisitos de qualidade, rendimento, compatibilidade, durabilidade e segurança, locais e regras de recebimento, garantia, manutenção, solução no ciclo de vida, requisitos, modelo de execução, modelo de gestão, medição e pagamento, critério de seleção, estimativa de valor e adequação orçamentária. A IN SEGES/ME nº 81/2022 é regra federal para Administração direta, autárquica e fundacional, e também alcança estados, Distrito Federal e municípios quando executem recursos da União decorrentes de transferências voluntárias. [12]

O contrato deve estabelecer objeto, vinculação ao edital e proposta, preço e pagamento, medição, prazos de execução e recebimento, matriz de riscos quando cabível, garantias, manutenção, responsabilidades, penalidades e outras cláusulas necessárias. A divulgação no PNCP é condição de eficácia do contrato e dos aditamentos, nos prazos legais de 20 dias úteis para licitação e 10 dias úteis para contratação direta. [5]

### Diálogo competitivo: rota excepcional para incerteza qualificada

O diálogo competitivo é modalidade de licitação em que a Administração seleciona licitantes por critérios objetivos, dialoga para desenvolver uma ou mais alternativas e recebe proposta final após o encerramento do diálogo. A Lei restringe seu uso a contratações que envolvam inovação tecnológica ou técnica, adaptação de soluções disponíveis, ou impossibilidade de definir especificações com precisão suficiente; também o admite quando é necessário definir a solução técnica, requisitos técnicos ou estrutura jurídica/financeira do contrato. [8]

A rota real tem três fases: pré-seleção, diálogo e fase competitiva. O edital deve informar necessidade e exigências, assegurar prazo mínimo de 25 dias úteis para manifestação, admitir todos os interessados que cumpram critérios objetivos e evitar vantagem por divulgação discriminatória. A Administração não pode revelar solução ou informação sigilosa de um licitante sem consentimento. Reuniões devem ser registradas em ata e gravadas em áudio e vídeo. Ao encerrar o diálogo, a Administração junta registros e gravações aos autos, publica o edital da fase competitiva e abre prazo mínimo de 60 dias úteis para propostas dos pré-selecionados. [8]

**Possibilidade abstrata:** uma plataforma pode ajudar a registrar perguntas, versões, atas, matriz de requisitos e critérios de solução. **Rota real:** órgão competente, comissão de contratação com pelo menos três servidores efetivos ou empregados públicos permanentes, edital, publicidade oficial, proteção da confidencialidade, registros integrais, decisão fundamentada e fase competitiva. A plataforma não pode selecionar um diálogo competitivo apenas porque o produto é “inovador”.

### LC nº 182/2021 e CPSI: teste remunerado com risco tecnológico

A LC nº 182/2021 institui o Marco Legal das Startups e do Empreendedorismo Inovador. No capítulo de contratação pública, o regime visa resolver demandas públicas que exijam solução inovadora com emprego de tecnologia e promover inovação pelo poder de compra do Estado. Aplica-se à Administração direta, autárquica e fundacional de qualquer Poder e ente; empresas estatais podem adotar o regime no que couber, conforme regulamento interno. [7]

O CPSI é uma licitação especial para testar soluções inovadoras desenvolvidas ou a desenvolver, com ou sem risco tecnológico. O edital pode descrever o problema e resultados esperados, inclusive desafios tecnológicos, sem descrever solução técnica previamente escolhida. Deve ser divulgado com antecedência mínima de 30 dias corridos. A comissão especial tem pelo menos três pessoas de reputação ilibada e conhecimento reconhecido, incluindo um servidor do órgão e um professor de instituição pública de educação superior na área relacionada. [7]

A avaliação deve considerar potencial de resolver o problema e eventual economia, grau de desenvolvimento, viabilidade e maturidade do modelo de negócio, viabilidade econômica e comparação de custo-benefício. Preço não pode ser o único critério de julgamento; a lei admite mais de uma proposta. A habilitação é posterior ao julgamento e a Administração pode dispensar parte da documentação e garantia mediante justificativa, respeitadas as restrições constitucionais. [7]

O CPSI tem vigência de até 12 meses, prorrogável por até mais 12 meses. Deve conter metas e metodologia de aferição do êxito, relatórios de andamento e final, matriz de riscos incluindo risco tecnológico, titularidade de propriedade intelectual e participação em resultados de exploração. O pagamento pode usar preço fixo, preço fixo com incentivo, reembolso de custos ou combinações legais. Em risco tecnológico, o pagamento acompanha o trabalho executado; mesmo que o resultado não seja atingido por risco tecnológico, a remuneração contratada, salvo parcela variável por meta, deve ser paga conforme o critério adotado, sem impedir extinção antecipada se comprovada inviabilidade técnica ou econômica. [7]

A lei estabelece valor máximo nominal de R$ 1,6 milhão por CPSI, mas prevê atualização por ato do Poder Executivo federal. O produto não deve hardcodar esse valor sem registrar a data e a atualização aplicável. Encerrado o CPSI, a Administração **pode** contratar a mesma contratada, sem nova licitação, para fornecimento ou integração da solução, observados os limites, a justificativa, a avaliação de custo-benefício e as condições do art. 15. Isso não é uma assinatura automática nem promessa de escala. [7]

O CPSI do TCU ilustra a diferença entre lei e operação. O TCU publicou documentos de consulta, edital, TR, minuta, confidencialidade, proteção de dados e segurança, resultados de julgamento, contratos e avaliação. A execução teve testes comparativos e critérios de escala, tempestividade, periodicidade, abrangência, acurácia/automação e custo. É evidência institucional de uma rota executada, não licença para qualquer fornecedor declarar que está “aprovado pelo TCU”. [18]

A literatura do Ipea explica o CPSI como instrumento para testar inovação sem exigir que gestor ou contratado garanta sucesso, porque fracasso pode ser etapa aceitável do processo inovativo. A literatura acadêmica recente, porém, mostra adoção estadual ainda incipiente: em levantamento de 579.303 objetos, foram identificadas 11 contratações de soluções inovadoras por CPSI ou ETEC, com barreiras de cultura, capacitação, burocracia e aversão a risco. Esses achados são literatura e evidência empírica, não norma vinculante. [19] [20]

## Contratação de TIC e nuvem

### Âmbito da IN SGD/ME nº 94/2022

A IN SGD/ME nº 94/2022 disciplina o processo de contratação de soluções de TIC pelos órgãos e entidades integrantes do SISP do Poder Executivo Federal. Ela define equipe de planejamento com integrante técnico, administrativo e requisitante, e equipe de fiscalização com gestor, fiscal técnico, fiscal administrativo, fiscal requisitante e, quando aplicável, fiscal setorial. Essa arquitetura de papéis é uma orientação normativa federal para seu âmbito, não um mapa automático de cargos de todo município ou estado. [13]

O TR de TIC deve conter definição do objeto, Catmat/Catser, solução, justificativa, requisitos, responsabilidades, modelos de execução e gestão, estimativa de preços, adequação orçamentária, cronograma, regime de execução e critérios técnicos de seleção. Amostra, se houver, deve ter procedimentos e critérios objetivos. A definição deve ser precisa, suficiente e clara, sem especificações excessivas, irrelevantes ou desnecessárias que limitem a competição. [13]

O modelo de execução deve explicar como o contrato produzirá resultados do início ao encerramento, com rotinas, prazos, documentação, papéis, volumes, comunicações formais, pagamento por resultados quando aplicável e termos de compromisso e ciência de sigilo. O modelo de gestão deve fixar métricas, indicadores, níveis mínimos de serviço, testes e inspeções, fontes de informação, listas de verificação, recursos humanos, glosas e sanções. [13]

Para a Plataforma Impacto, isso significa que “torre do governo” deve ser tratada como **painel de gestão e evidência do contrato**, nunca como substituição do gestor, fiscal, autoridade, comissão ou sistema oficial. O produto precisa ter registros de histórico, responsabilidades, ordens de serviço, critérios de aceite, evidências, ocorrências, glosas e decisão humana.

### Portaria SGD/MGI nº 5.950/2023 e nuvem

A Portaria SGD/MGI nº 5.950/2023 estabelece o Modelo de Contratação de Software e Serviços de Computação em Nuvem para órgãos e entidades do SISP. A página oficial informa que sua observância é obrigatória em processos iniciados após 30 de abril de 2024, facultativa para processos anteriores e não aplicável a contratos celebrados antes de 1º de novembro de 2023. O modelo abrange software permanente, cessão temporária, SaaS, IaaS, PaaS, suporte, operação, migração, integração e consultoria. [14] [15]

A estratégia deve considerar negócio, resultados, segurança e privacidade, com classificação prévia da informação. O modelo admite nuvem para informação sem restrição, mantém em nuvem de governo, salvo decisão de governança, cargas que tratem informações com restrição legal e veda nuvem pública para informação classificada em grau de sigilo e documentos preparatórios que possam originá-la. Os dados devem ser armazenados em data centers no Brasil; tratamento fora do país só é admitido nos casos e condições previstos, inclusive cópia de segurança atualizada em território brasileiro. [14]

O modelo exige avaliação de dependência e ações de continuidade. Exemplos são padrões interoperáveis, contêineres, evitar banco proprietário, considerar mais de um provedor e infraestrutura própria como contingência. Na contratação de nuvem, o TR deve conter requisitos de privacidade e segurança adequados ao objeto e aos riscos. O contrato deve deixar claros os direitos do órgão sobre dados, cópias, backups, logs e acesso, canais de incidentes, controles de acesso e transferência. [14]

A IN GSI/PR nº 5/2021, fonte normativa federal de segurança para nuvem, exige, em seu âmbito, registros de acessos, incidentes e eventos cibernéticos mantidos em ambiente próprio por cinco anos, capacitação da equipe, segregação lógica, matriz de responsabilidades, processo de incidentes, tratamento de dados em território brasileiro e cláusulas de devolução integral e eliminação ao fim do contrato, observada a retenção legal. Também requer continuidade de negócios, recuperação de desastres, criptografia, canal seguro e notificação imediata de incidente, entre outros controles. [17]

Essas regras não permitem a claim “nuvem segura” por simples uso de provedor conhecido. A prova real exige classificação da carga, desenho de responsabilidades, controles contratados, localização e cópia, testes de restauração, logs disponíveis, exercício de saída e decisão sobre dados pessoais e informações restritas.

## PNCP e integração pública

O PNCP é o sítio oficial destinado à divulgação centralizada e obrigatória dos atos exigidos pela Lei nº 14.133/2021. É gerido pelo Comitê Gestor da Rede Nacional de Contratações Públicas. A própria página do PNCP informa que a adequação, fidedignidade e corretude das informações e arquivos são responsabilidade estrita dos órgãos e entidades contratantes. O portal oferece consulta a PCA, editais, atas, contratos, painéis e dados abertos com APIs/documentação. [9]

O PNCP não é apenas um repositório que a plataforma possa imitar. Uma integração real precisa identificar o órgão, credenciais e perfil de acesso quando necessário, contratos de interface, esquema de dados, idempotência, retorno de protocolo, tratamento de erro, atualização, retificação, publicação de anexos, logs e reconciliação com o processo administrativo. Até que isso seja implementado e testado em ambiente autorizado, o produto deve oferecer exportação estruturada e checklist de publicação, e não dizer “publicado no PNCP”.

A torre territorial do release também não equivale à integração pública. Ela pode organizar informações autorizadas, agregadas e provenientes de fontes verificadas. Não pode expor proposta sigilosa, dados pessoais, preço reservado, conteúdo de diálogo competitivo ou informações classificadas. A lei determina publicidade, mas preserva sigilos legais; publicidade não significa publicação indiscriminada de todo artefato.

## Mapa de obrigações, rota e produto

| Etapa | Obrigação ou decisão pública | Evidência mínima a preservar | Requisito de produto | Estado atual / correção |
|---|---|---|---|---|
| Demanda e PCA | Problema, prioridade, alinhamento, orçamento e previsão no PCA; revisão justificada se fora do plano | DFD, aprovação, PCA, justificativa | Workflow de demanda com ente, jurisdição, autoridade, orçamento e versão | **Lacuna:** a torre não é PCA nem PGC oficial |
| ETP | Problema, requisitos, alternativas, mercado, quantidades, preço, parcelamento, resultados, riscos e conclusão | ETP versionado, fontes, memórias e consulta | Editor com campos obrigatórios, justificativas e rastreabilidade | **Lacuna:** `PROCUREMENT.md` não cobre ETP público |
| Pesquisa de preços | Fontes oficiais e contratações similares priorizadas; três fornecedores apenas uma das fontes, com justificativa | Série, fonte, data/hora, proposta, método, memória e exclusões | Benchmark por fonte e comparabilidade, não apenas mediana de três cotações | **Correção urgente:** rotular benchmark atual como interno |
| Escolha de rota | Pregão/concorrência, contratação direta, diálogo, CPSI ou outro instrumento conforme fatos e lei | Matriz de enquadramento e decisão motivada | Roteador que exige evidência; nunca classificar “inovação” automaticamente | **Lacuna:** inexistente no módulo atual |
| TR e edital | Objeto preciso, requisitos, execução, gestão, medição, pagamento, aceite, sanções, dados e segurança | TR, anexos, matriz de riscos, minuta, parecer quando cabível | Templates por âmbito e revisão de escopo | **Lacuna:** B2G é minuta, não TR/edital oficial |
| Diálogo | Pré-seleção objetiva, confidencialidade, ata/gravação, decisão fundamentada, fase competitiva | Editais, atas, gravações, consentimentos, critérios | Cofre de acesso, logs e exportação auditável | **Hipótese de produto**, sem uso oficial comprovado |
| CPSI | Problema, comissão, critérios, risco tecnológico, metas, IP, remuneração e relatórios | Edital, propostas, julgamento, negociação, contrato e testes | Módulo de desafio, metas, risco e avaliação comparativa | **Lacuna:** não afirmar capacidade CPSI até implementar e validar |
| Contrato | Cláusulas legais, obrigações, mudanças, garantias, riscos e publicação PNCP | Contrato imutável, aditivos, hash, publicação e protocolo | Versionamento, hash, alçadas e bloqueio de pagamento sem aceite | **Parcial:** engine contratual existe, sem contrato administrativo validado |
| Execução e aceite | Recebimento provisório e definitivo; testes, medição, glosa, sanções e autorização de faturamento | OS, evidência, checklist, termos, notas, ocorrências e decisão | Aceite técnico/funcional/administrativo, dupla checagem e trilha | **Parcial:** aceite genérico do contrato não prova aceite público |
| Dados e continuidade | Classificação, LGPD, segurança, logs, backup, portabilidade, reversibilidade, recuperação | Inventário, matriz de acesso, logs, RTO/RPO, teste de restore, plano de saída | Data lineage, exportação, exercício de saída e reconciliação | **Lacuna:** pendências LGPD e ausência de integração/continuidade contratada |
| PNCP e transparência | Publicação legal, fidedignidade, anexos e correções pelo órgão | Protocolo, payload, resposta, data, hash e reconciliação | Conector autorizado ou exportação claramente rotulada | **Ausente:** não alegar integração atual |

## Requisitos de produto

### 1. Porta de entrada jurídica e de governança

O produto deve exigir, antes de iniciar um fluxo, ente federativo, órgão, entidade, poder, fonte de recurso, jurisdição, âmbito de aplicação, sistema oficial usado, responsável, autoridade competente e data de abertura do processo. Deve marcar se o usuário está em SISP federal, em órgão sujeito a transferência voluntária da União, em empresa estatal ou em Administração estadual/municipal com regulamentação própria.

Deve haver uma matriz de aplicabilidade com os estados **vigente**, **aplicável ao âmbito**, **orientação**, **modelo**, **pendente de validação** e **não aplicável**. Uma lei federal não transforma automaticamente uma instrução normativa do SISP em obrigação de um município. O produto deve exigir revisão humana quando a resposta depender de regulamentação local, fonte de recurso, contrato anterior, sigilo ou interpretação.

### 2. Planejamento e inovação

O módulo de demanda deve separar problema público, resultado esperado, hipótese de solução, tecnologia e fornecedor. Deve permitir consulta prévia ao mercado sem criar preferência, registrar contribuições, conflitos de interesse, perguntas e respostas, critérios de igualdade e versão final. O ETP deve conter alternativas, inclusive não contratar, solução própria, solução disponível adaptada, parceria, compartilhamento e rota de inovação.

O roteador deve comparar fatos com requisitos legais:

- **Contratação regular:** objeto definível, requisitos objetivos e disputa apropriada.
- **Diálogo competitivo:** inovação/adaptação/incerteza qualificada ou necessidade de definir solução, requisitos ou estrutura jurídica/financeira, com fases e registros legais.
- **CPSI:** teste de solução inovadora, com risco tecnológico possível, edital e contrato especial da LC nº 182/2021.

O roteador pode sugerir perguntas e alertas; não pode emitir decisão de enquadramento ou dispensar parecer, autorização, comissão, justificativa ou publicação.

### 3. TR, edital e critérios de seleção

O TR deve ser editável por campo, não apenas texto livre. Cada requisito deve guardar fonte, necessidade, teste, métrica, tolerância, consequência e responsável pelo aceite. O sistema deve impedir requisito sem justificativa, critério subjetivo sem escala, fornecedor citado sem análise de competitividade e promessa de resultado sem baseline.

No diálogo competitivo, deve existir segregação por licitante, confidencialidade, termo de acesso, registro de reunião, gravação, decisão de encerramento e fase competitiva. No CPSI, deve haver metas, metodologia de aferição, relatório de andamento, matriz de risco tecnológico, propriedade intelectual, critérios de julgamento e negociação.

### 4. Contrato administrativo e execução

O contrato deve ser imutável por versão, com aditivo como nova versão, hash do texto, vigência, vínculo ao edital, preço, medição, pagamento, riscos, propriedade intelectual, dados, segurança, continuidade, garantias, sanções, aceite e prazo de resposta. O engine atual de contrato e quatro olhos é reutilizável como mecanismo técnico, mas a redação da cláusula administrativa depende de modelo aprovado e do órgão.

A execução deve separar: ordem de serviço; entrega; recebimento provisório; testes; correção; recebimento definitivo; medição; glosa; nota fiscal; liquidação; autorização de pagamento; pagamento e avaliação de desempenho. O sistema deve impedir que “aceite do usuário” seja tratado como termo de recebimento definitivo sem papel, competência, critério e evidência.

### 5. PNCP e integrações

A primeira entrega segura é exportar pacote estruturado, com validação de campos, hash e checklist para publicação pelo órgão. Uma entrega posterior pode integrar PNCP, mas somente após especificação oficial, autenticação, testes de homologação, idempotência, reconciliação e autorização. Compras.gov.br, Transferegov, SIAFI, Portal da Transparência, e-SIC e outros sistemas devem ser tratados como integrações separadas; não devem aparecer como “conectados” por existir um campo de URL.

### 6. Torre do governo

A torre deve ser descrita como painel de governança do **processo e do contrato**: necessidade, PCA, ETP, TR, edital, fornecedor, riscos, pendências, aceite, pagamento, atrasos, dados e decisão. A torre deve mostrar origem, data, versão, responsável, grau de prova e lacunas. “Não encontrado” deve ser diferente de zero, conforme a regra já adotada no release para indicadores.

O painel não deve expor por padrão dados pessoais, propostas sigilosas, informações protegidas, dados de outro fornecedor, documentos não publicados ou informação classificada. Deve permitir visões públicas agregadas e visões internas com segregação de funções.

## Requisitos de dados

### Registro mínimo de proveniência jurídica

Toda regra, alerta, template e texto regulatório deve guardar:

- URL oficial; órgão ou autor; título; data de publicação e atualização;
- tipo de fonte: lei, decreto, IN, portaria, orientação, jurisprudência, literatura ou hipótese de produto;
- âmbito: União, estado, município, órgão, SISP, transferência voluntária ou contrato específico;
- dispositivo ou seção que sustenta a regra;
- data de consulta, versão do conteúdo e hash do arquivo;
- status: vigente, revogado, substituído, consulta pública, minuta ou revisão necessária;
- relação entre regra e requisito de produto;
- revisão humana, responsável e próxima data de atualização.

O assistente deve responder com trecho e fonte ou recusar com “não encontrei informação suficiente na base oficial”. Conteúdo regulatório vencido deve ser marcado como revisão necessária, sem aparecer como regra vigente.

### Dados do processo e do contrato

As entidades mínimas são: órgão; unidade; ente; jurisdição; usuário e papel; demanda/DFD; PCA; ETP; consulta de mercado; pesquisa de preços; TR; edital; lote/item; fornecedor; comissão; conflito de interesse; proposta; avaliação; diálogo; CPSI; contrato; aditivo; ordem; entrega; teste; aceite; medição; glosa; nota; pagamento; risco; incidente; publicação PNCP; recurso; decisão e auditoria.

Cada documento deve ser versionado e ter hash, autor, data, origem, status, escopo e relação com o documento anterior. O produto deve conservar correção por nova versão, nunca sobrescrever a prova histórica. Para atos de diálogo e CPSI, acesso por fornecedor deve ser restrito e a exportação pública deve retirar segredo comercial e dados pessoais sem apagar a existência da etapa.

### Dados pessoais, sigilo e nuvem

O sistema deve marcar controlador, operador, finalidade, base legal pendente, categorias de titulares, retenção, transferência, acesso e descarte. Deve separar dado público, restrito por lei, pessoal, segredo comercial, propriedade intelectual e informação classificada. O fato de o dado aparecer em um edital não torna todos os anexos públicos.

Para nuvem, o inventário deve conter localização, provedor, serviço IaaS/PaaS/SaaS, subcontratados, data centers, criptografia, chaves, logs, backup, RTO, RPO, plano de recuperação, exportação, formato, custo de saída, dependências proprietárias e data do último teste de restauração. Em órgãos sujeitos à Portaria SGD/MGI nº 5.950/2023 e à IN GSI/PR nº 5/2021, o fluxo deve validar os requisitos específicos de classificação, território, logs, segurança e devolução; em outros entes, deve identificar a regra local em vez de assumir aplicação federal.

## Testes e controles obrigatórios antes de qualquer claim público

1. **Teste de aplicabilidade:** mesma demanda submetida a União/SISP, município e empresa estatal deve produzir escopos e pendências diferentes quando a norma for diferente.
2. **Teste de ETP/TR:** faltar requisito essencial, memória de cálculo, alternativa, parcelamento ou conclusão deve bloquear “pronto para licitar”.
3. **Teste de pesquisa de preços:** três cotações próprias não podem ser rotuladas como pesquisa oficial completa sem fontes, série, justificativa e memória; o benchmark atual deve produzir alerta “interno”.
4. **Teste de rota:** a palavra “inovador” sozinha não abre diálogo nem CPSI; a decisão exige fatos, dispositivo, responsável e justificativa.
5. **Teste de diálogo:** prazo mínimo de pré-seleção, critérios objetivos, confidencialidade por licitante, ata, gravação, encerramento fundamentado e fase competitiva precisam estar presentes.
6. **Teste de CPSI:** metas, metodologia, risco tecnológico, IP, relatórios, comissão, critérios e valores versionados; falha de resultado por risco tecnológico não pode ser convertida automaticamente em inadimplemento.
7. **Teste de aceite:** entrega sem teste, teste sem critério, critério sem evidência e aceite por pessoa sem papel devem impedir recebimento definitivo e autorização de faturamento.
8. **Teste de glosa:** não atingir nível mínimo, resultado ou recurso contratado deve gerar cálculo reproduzível e decisão humana, sem apagar o termo de recebimento.
9. **Teste de quatro olhos:** quem demanda não pode sozinho aprovar, receber definitivamente e autorizar o faturamento em faixa que exige segregação.
10. **Teste PNCP:** exportação deve validar campos, anexos, hash, data, órgão e vínculo do contrato; integração só pode ser “publicada” com protocolo e reconciliação reais.
11. **Teste de segurança:** simular incidente, revogar acesso, preservar evidência, copiar logs, restaurar backup e reportar evento sem publicar dados sigilosos.
12. **Teste de continuidade:** restaurar dados em ambiente alternativo, exportar formato aberto, medir RTO/RPO e ensaiar saída sem depender apenas do fornecedor.
13. **Teste de transparência:** a visão pública deve mostrar o que é publicado e ocultar dados pessoais, segredo comercial, proposta protegida e informação classificada, com motivo registrado.
14. **Teste de claim:** cada texto de marketing deve apontar para fonte, versão, âmbito e teste; ausência de fonte transforma claim em hipótese ou deve bloqueá-lo.

## Claims proibidos ou condicionados

O release não deve publicar nem vender, sem prova específica, os seguintes claims:

- “Plataforma em conformidade com a Lei nº 14.133/2021.” A lei tem âmbito, regulamentações e processo; software não recebe conformidade geral por autodeclaração.
- “CPSI pronto, aprovado ou elegível.” É necessário problema público, edital, comissão, critérios, contrato e rota da LC nº 182/2021.
- “Diálogo competitivo automático.” A modalidade exige hipótese legal, comissão, publicidade, fases, confidencialidade, gravações e decisão fundamentada.
- “Integração ou publicação no PNCP.” Só após conector autorizado, protocolo, payload aceito, anexos e reconciliação.
- “Torre oficial do governo”, “sistema de compras do governo”, “homologado pelo TCU”, “auditado pelo controle externo” ou “certificado pelo órgão.” Nenhum documento interno atual sustenta isso.
- “LGPD garantida”, “dados soberanos” ou “nuvem segura.” É preciso base legal, contratos, classificação, controles, testes e avaliação do contexto.
- “Continuidade assegurada”, “zero lock-in” ou “recuperação garantida.” Só é defensável com contrato, arquitetura, RTO/RPO, backup e exercício de restauração/saída.
- “Aceite legal” ou “pagamento público automatizado.” O produto pode apoiar evidências; recebimento, liquidação e pagamento dependem de competência e processo do órgão.
- “Preço de mercado validado” porque existem três cotações, ou “fraude” porque um preço diverge da mediana. O módulo atual só sinaliza possível outlier de seu pedido.
- “Impacto validado” quando há apenas declaração, estimativa, proxy ou documento sem cadeia de evidência. Usar estado desconhecido quando a prova faltar.

## Lacunas e backlog de correção

### Lacunas de enquadramento

- O release não mantém matriz de aplicabilidade por ente, órgão, SISP, transferência voluntária e regulamentação local.
- A torre territorial não é PCA, ETP, TR, PNCP, processo administrativo nem sistema de fiscalização.
- O B2G permanece minuta legal pendente; não é contrato administrativo, edital ou autorização de cobrança pública. [3]

### Lacunas de processo

- Não há rota completa de DFD → PCA → ETP → pesquisa formal → TR → edital → seleção → contrato → PNCP → execução → recebimento → pagamento.
- Não há módulo comprovado de diálogo competitivo ou CPSI com comissão, confidencialidade, gravações, metas, risco tecnológico, IP e avaliação.
- Não há integração comprovada com PNCP, Compras.gov.br, Transferegov, SIAFI, Portal da Transparência ou e-SIC. [3]

### Lacunas de dados e continuidade

- A documentação LGPD ainda marca pendentes base legal, retenção efetiva, RIPD/DPIA, operador e encarregado. [4]
- A plataforma precisa de classificação de informação, segregação de segredo comercial e exercício de exportação/restore antes de prometer governança de nuvem.
- O módulo deve guardar fonte oficial, versão, data, escopo e hash de toda regra e separar literatura, orientação e norma.

### Prioridade de implementação

1. Corrigir textos e labels para “apoio à estruturação e acompanhamento”, removendo claims oficiais.
2. Criar matriz de âmbito e rota com bloqueios de aplicabilidade.
3. Reescrever o módulo de benchmark com fontes da IN 65/2021 e manter o controle de três cotações como política interna separada.
4. Implementar ETP/TR versionados, critérios de aceite e trilha de execução.
5. Implementar pacote de exportação PNCP antes de qualquer conector.
6. Implementar cofres de diálogo/CPSI somente com revisão jurídica, segurança e testes de confidencialidade.
7. Implementar inventário de dados, logs, backup, restauração e plano de saída.
8. Atualizar a documentação B2G somente depois de revisão jurídica e decisão empresarial sobre escopo, preço, suporte, segurança e responsabilidade.

## Conclusão operacional

A Lei nº 14.133/2021 e a LC nº 182/2021 oferecem rotas reais para inovação, mas não oferecem atalho. O diálogo competitivo é excepcional e procedimental; o CPSI é teste remunerado com risco tecnológico e possível contrato posterior de fornecimento; a contratação regular de TIC exige planejamento, requisitos, execução, gestão e aceite; o modelo de nuvem exige classificação, segurança, território, portabilidade e continuidade; e o PNCP exige publicidade oficial cuja correção é responsabilidade do órgão.

A Plataforma Impacto pode ocupar uma posição útil como camada de **proveniência, planejamento, colaboração, risco, evidência, aceite e acompanhamento**. O produto deve assumir que a decisão pública continua sendo do órgão, que o edital continua sendo o instrumento convocatório, que a publicação oficial continua sendo do sistema competente e que o sucesso inovador não pode ser prometido antes do teste. Essa distinção entre possibilidade abstrata e rota real é o requisito de confiança central deste domínio.

## Referências

[1]: file:///home/ubuntu/impacto-trust-knowledge-v0.26.0/README.md "Plataforma Impacto, README do release v0.26.0, versão do repositório consultada em 08/10/2026. Sustenta: estado fechado, não publicação, ausência de provedores reais, engine de contratos, torres e limites operacionais."

[2]: file:///home/ubuntu/impacto-trust-knowledge-v0.26.0/docs/PROCUREMENT.md "Plataforma Impacto, PROCUREMENT.md v0.8.0, versão do repositório consultada em 08/10/2026. Sustenta: política interna de cotações, mediana, outlier e a ressalva de que não é base de preços de mercado nem validação de orçamento."

[3]: file:///home/ubuntu/impacto-trust-knowledge-v0.26.0/docs/LEGAL_FRAMEWORK.md "Plataforma Impacto, LEGAL_FRAMEWORK.md v0.17.0, versão do repositório consultada em 08/10/2026. Sustenta: minutas legais não aprovadas, B2G em draft, ausência de assinatura qualificada e de integrações públicas."

[4]: file:///home/ubuntu/impacto-trust-knowledge-v0.26.0/docs/LGPD.md "Plataforma Impacto, LGPD.md v0.7.0, versão do repositório consultada em 08/10/2026. Sustenta: controles técnicos existentes e pendências de base legal, retenção, RIPD/DPIA, operador e encarregado."

[5]: https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2021/lei/l14133.htm "Presidência da República/Planalto, Lei nº 14.133, de 1º de abril de 2021, texto legal atualizado consultado em 08/10/2026. Sustenta: princípios, objetivos, governança, planejamento, edital, contratos, critérios, recebimento, pagamento e eficácia pelo PNCP."

[6]: https://www.gov.br/compras/pt-br/nllc "Ministério da Gestão e da Inovação em Serviços Públicos, Portal de Compras — Nova Lei de Licitações, página atualizada em 15/01/2026. Sustenta: âmbito geral da Lei nº 14.133/2021, página oficial de regulamentações e definição institucional do PNCP."

[7]: https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp182.htm "Presidência da República/Planalto, Lei Complementar nº 182, de 1º de junho de 2021, texto consultado em 08/10/2026. Sustenta: finalidade do capítulo, licitação especial, edital, comissão, critérios, CPSI, risco tecnológico, IP, remuneração, limites e contrato de fornecimento."

[8]: https://licitacoesecontratos.tcu.gov.br/3-6-5-dialogo-competitivo-2/ "Tribunal de Contas da União, Licitações e Contratos — 3.6.5 Diálogo Competitivo, s.d., consultado em 08/10/2026. Sustenta: hipóteses do art. 32, fases, prazos, comissão, confidencialidade, atas e gravações; é orientação institucional, não lei autônoma."

[9]: https://www.gov.br/pncp/pt-br/pncp "Comitê Gestor da Rede Nacional de Contratações Públicas/PNCP, Sobre o PNCP, s.d., consultado em 08/10/2026. Sustenta: finalidade e obrigatoriedade de divulgação, governança, responsabilidade do órgão pela fidedignidade, PCA, contratos, dados abertos e APIs."

[10]: https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2022/decreto/d10947.htm "Presidência da República/Planalto, Decreto nº 10.947, de 25 de janeiro de 2022, texto consultado em 08/10/2026. Sustenta: PCA, PGC, objetivos de planejamento, consolidação, aprovação, divulgação no PNCP, revisão e gestão de riscos no âmbito regulamentado."

[11]: https://www.gov.br/compras/pt-br/acesso-a-informacao/legislacao/instrucoes-normativas/instrucao-normativa-seges-no-58-de-8-de-agosto-de-2022 "Secretaria de Gestão/Ministério da Economia, IN SEGES nº 58, de 8 de agosto de 2022, página oficial consultada em 08/10/2026. Sustenta: definição e conteúdo do ETP, alinhamento ao PCA, levantamento de mercado, alternativas, quantidades, valor, riscos e conclusão; âmbito federal e usos em transferências conforme aplicável."

[12]: https://www.gov.br/compras/pt-br/acesso-a-informacao/legislacao/instrucoes-normativas/instrucao-normativa-seges-me-no-81-de-25-de-novembro-de-2022 "Secretaria de Gestão/Ministério da Economia, IN SEGES/ME nº 81, de 25 de novembro de 2022, publicada em 28/11/2022, consultada em 08/10/2026. Sustenta: TR, objeto, ciclo de vida, execução, gestão, medição, pagamento, recebimento e âmbito federal/transferências voluntárias."

[13]: https://www.gov.br/governodigital/pt-br/contratacoes-de-tic/legislacao/processo-de-contratacao-de-solucoes-de-tic-regido-pela-lei-ndeg-14-133-de-2021 "Secretaria de Governo Digital, IN SGD/ME nº 94, de 23 de dezembro de 2022, página oficial atualizada em 19/06/2026, consultada em 08/10/2026. Sustenta: equipes, ETP/TR de TIC, requisitos, execução, gestão, métricas, testes, aceite, glosas, riscos e histórico contratual no SISP."

[14]: https://www.gov.br/governodigital/pt-br/contratacoes-de-tic/legislacao/modelo-de-contratacao-de-software-e-servicos-em-nuvem/vigentes/portaria-sgd-mgi-no-5-950-de-26-de-outubro-de-2023 "Secretaria de Governo Digital/MGI, Portaria SGD/MGI nº 5.950, de 26 de outubro de 2023, publicada em 27/03/2024 e atualizada em 19/06/2026, consultada em 08/10/2026. Sustenta: modelo de software/nuvem, vigência de aplicação, classificação, território, continuidade, lock-in, dados, logs, segurança, aceitação e pagamento."

[15]: https://www.gov.br/governodigital/pt-br/contratacoes-de-tic/legislacao/modelo-de-contratacao-de-software-e-servicos-em-nuvem/vigentes/modelo-de-contratacao-de-software-e-nuvem "Secretaria de Governo Digital/MGI, Modelo de Contratação de Software e Serviços de Computação em Nuvem, s.d., consultado em 08/10/2026. Sustenta: escopo do modelo, obrigatoriedade após 30/04/2024 e diretrizes de segurança, privacidade, TCO, risco e continuidade; é material operacional do SISP."

[16]: https://www.gov.br/compras/pt-br/acesso-a-informacao/legislacao/instrucoes-normativas/instrucao-normativa-seges-me-no-65-de-7-de-julho-de-2021 "Secretaria de Gestão/Ministério da Economia, IN SEGES/ME nº 65, de 7 de julho de 2021, página oficial consultada em 08/10/2026. Sustenta: formalização da pesquisa de preços, fontes, prioridade, três fornecedores como um parâmetro, metodologia, memória, análise crítica e TIC."

[17]: https://www.in.gov.br/en/web/dou/-/instrucao-normativa-n-5-de-30-de-agosto-de-2021-341649684 "Gabinete de Segurança Institucional da Presidência da República, IN nº 5, de 30 de agosto de 2021, Diário Oficial da União, consultada em 08/10/2026. Sustenta: requisitos mínimos federais de segurança em nuvem, logs, segregação, território, devolução, eliminação, continuidade, recuperação, criptografia e incidentes."

[18]: https://sites.tcu.gov.br/cpsi/ "Tribunal de Contas da União, CPSI — Desafio TCU de fiscalização de obras urbanas de pavimentação, página do caso consultada em 08/10/2026. Sustenta: exemplo institucional de consulta, edital, TR, contratos, testes comparativos, critérios e avaliação; não constitui aprovação de terceiros."

[19]: https://repositorio.ipea.gov.br/items/4b3ec95c-8de3-4608-a8c7-aa2dc8667e51 "Hudson Mendonça, Bruno Monteiro Portela e Adalberto do Rego Maciel Neto/Ipea, Contrato público de soluções inovadoras: racionalidade fundamental e posicionamento no mix de políticas de inovação que atuam pelo lado da demanda, 2022. Sustenta: racionalidade, risco tecnológico, segurança jurídica e posição do CPSI nas políticas de inovação; literatura institucional, não norma."

[20]: https://www.scielo.br/j/rbi/a/HQ4XRQMLQxRN7FnYnCSfSYk/?lang=pt "Izabel Sabino de Sousa e James Batista Vieira, Contratos públicos de inovação: uma análise da implementação nos estados brasileiros, Revista Brasileira de Inovação, v. 24, 2025, DOI 10.20396/rbi.v24i00.8675525. Sustenta: adoção incipiente de CPSI/ETEC nos estados, 11 contratações identificadas no recorte e barreiras de cultura, capacitação, burocracia e aversão a risco; literatura acadêmica."

[21]: https://repositorio.enap.gov.br/handle/1/8072 "Nelson da Cruz Monteiro Fernandes/Escola Nacional de Administração Pública, Cidades inovadoras: compras públicas como motor de inovação, 2024. Sustenta: práticas municipais, inovação aberta e uso de compras públicas para problemas locais; material institucional/educativo, não regra vinculante."

[22]: https://www.worldbank.org/en/programs/govtech/projects "Banco Mundial, Global Program on GovTech & Public Sector Innovation — Projects, página consultada em 08/10/2026. Sustenta: uso de GovTech para modernizar serviços, administração, transparência e procurement; fonte multilateral de contexto, não norma brasileira."
