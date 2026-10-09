# Marketplace, parcerias, reputação e proteção contra fraude

## Escopo e método

Este relatório examina a intermediação de serviços, publicidade e parcerias, proteção de usuários, direito do consumidor quando aplicável, identificação proporcional, prevenção a fraude, denúncias, moderação, reputação, conflitos de interesses e responsabilidade de plataforma. O foco é a relação entre cinco componentes do produto:

- `MARKETPLACE`: cadastro, descoberta, oferta, contratação e acompanhamento de serviços entre organizações, profissionais, financiadores e parceiros;
- `PARTNERSHIP_SYSTEM`: parcerias comerciais, institucionais, conteúdo patrocinado, comissões, indicação, benefícios e possíveis conflitos;
- `MODERATION_LADDER`: denúncia, suspeita, infração apurada e consequência, com urgência, contraditório e recurso;
- `REPUTATION_ARCHITECTURE`: avaliações, histórico de execução, selos, ranqueamento, explicação de critérios e contestação;
- `RISK_FRAUD`: prevenção, detecção, investigação, bloqueio proporcional, recuperação e auditoria.

A classificação abaixo separa **lei ou regulamento vigente**, **interpretação jurisprudencial vigente**, **orientação administrativa**, **padrão voluntário**, **literatura** e **hipótese de produto**. Não é parecer personalizado nem conclusão sobre um caso concreto. A aplicação do Código de Defesa do Consumidor (CDC) depende do papel efetivamente desempenhado pela plataforma, do destinatário final e do desenho da contratação.

## Estado atual do release que precisa ser corrigido

O release v0.26.0 se declara tecnicamente fechado, mas ainda não está publicado, não tem provedor real de pagamento, fiscal ou comunicação conectado e não permite cobrança real. A tese econômica é não custodial: a taxa de serviço da plataforma é cobrança própria ao financiador, sem desconto de dinheiro em trânsito, sem carteira, custódia ou take rate. Essa fronteira deve ser preservada antes de abrir qualquer marketplace.

O `LEGAL_FRAMEWORK.md` registra onze documentos legais como `draft`, inclusive `marketplace`, `intermediation`, `payment`, `cancellation`, `refund` e `b2b`. Portanto, nenhum fluxo deve coletar aceite como se existisse termo de marketplace aprovado. O banco corretamente bloqueia aceite de minuta; liberar esse bloqueio sem revisão e aprovação criaria uma falsa prova de contratação.

A base de LGPD já prevê minimização, ausência de dados sensíveis solicitados, contagens agregadas de beneficiários, RLS e retenções técnicas. Permanecem pendentes a decisão documentada de base legal por finalidade, RIPD/DPIA quando o risco justificar, canal e nomeação do encarregado, contratos com operadores e a granularidade territorial pública. Isso é especialmente relevante para `RISK_FRAUD`: prevenção não autoriza uma coleta genérica de documentos, biometria, listas ou dados de terceiros.

A base de conhecimento marca conteúdo regulatório com fonte e data, mas o seed é todo `demo=true`. Não se pode apresentar guia, selo, avaliação ou parceria demonstrativa como oficial. O módulo de procurement também faz a distinção correta entre “preço possivelmente fora do padrão” e “fraude”; essa regra deve ser reutilizada em toda a arquitetura de risco.

### Correções bloqueadoras antes de qualquer piloto real

1. Aprovar, versionar e publicar os termos de uso, marketplace, intermediação, parceria, publicidade, cancelamento e privacidade; registrar texto, versão, hash, vigência e aceite. Sem isso, manter o fluxo em demonstração.
2. Definir no contrato e na interface se o IMPACTO apenas hospeda e conecta, se intermedeia a contratação ou se também comercializa o próprio serviço. A responsabilidade pode crescer com o controle econômico, informacional, publicitário e operacional exercido.
3. Identificar separadamente operador da plataforma, fornecedor/prestador, parceiro pagante e eventual provedor de pagamento. O comprador deve ver quem entrega o serviço e quem responde pelo canal.
4. Implementar denúncia, comunicação de motivo, contraditório, recurso e trilha de decisão. A remoção automática definitiva por simples denúncia deve ser proibida, salvo risco legal ou de segurança que justifique medida temporária.
5. Proibir a exibição de “fraude”, “irregular” ou “não confiável” antes de apuração concluída. Exibir, quando necessário, estado neutro e temporário (“em análise”, “oferta suspensa preventivamente”), com data e revisão humana.
6. Separar conteúdo editorial, publicidade, parceria paga, resultado orgânico e resultado patrocinado. O usuário precisa saber quem pagou e por que uma oferta aparece.
7. Preservar a arquitetura não custodial. Se o produto passar a receber, manter, liquidar, gerir conta ou instruir pagamento, fazer análise regulatória específica antes de ligar o fluxo.

## Mapa de obrigações e do estado normativo

| Tema | Regra ou fonte | Status | Implicação para o produto |
|---|---|---|---|
| Consumidor, fornecedor e serviço | CDC, arts. 2º e 3º | Lei vigente | Verificar destinatário final e se a plataforma oferece serviço próprio ou participa da cadeia; não assumir que todo usuário organizacional é consumidor. |
| Oferta e publicidade | CDC, arts. 30–38 | Lei vigente | Oferta precisa, informação essencial, identificação da publicidade e prova de claims; ranking patrocinado não pode parecer orgânico. |
| Comércio eletrônico | Decreto nº 7.962/2013 | Regulamento vigente | Mostrar identidade, CNPJ/CPF quando houver, endereço, contato, características, riscos, preço e despesas; permitir correção, contrato conservável, atendimento e arrependimento quando aplicável. |
| Provedor e conteúdo de terceiro | Marco Civil, arts. 10, 15, 19–21; tese STF 2025 | Lei e interpretação constitucional vigente | Guardar logs de acesso a aplicações por seis meses quando enquadrado; proteger dados; aplicar a escada de denúncias e os gatilhos diferenciados após a decisão do STF. |
| Dados e fraude | LGPD, arts. 6º, 7º, 10, 18, 20, 44–48 | Lei vigente | Necessidade, transparência, segurança, prevenção, não discriminação, direitos, revisão de decisão automatizada e comunicação de incidente. |
| Legítimo interesse | Guia ANPD de 2024/2025 | Orientação administrativa, não lei nova | Documentar teste de finalidade, necessidade, balanceamento e salvaguardas para antifraude; repetir o teste por finalidade. |
| Incidente de segurança | Resolução CD/ANPD nº 15/2024 | Regulamento vigente | Comunicar à ANPD e aos titulares em até três dias úteis quando houver risco ou dano relevante; manter registro por pelo menos cinco anos. |
| KYC/PLD | Lei nº 9.613/1998, art. 9º; normas setoriais COAF | Lei vigente, com escopo setorial | Marketplace geral não é automaticamente sujeito a KYC/PLD da Lei nº 9.613; a obrigação nasce se a atividade se enquadrar em setor listado ou regulado. |
| Pagamentos | Lei nº 12.865/2013 e normas BCB | Regulação setorial vigente | Receber, gerir conta, emitir instrumento, credenciar, executar ou facilitar serviços de pagamento pode enquadrar a operação no SPB; não ligar sem desenho e parceiro autorizados. |
| Publicidade com influenciador/parceiro | Código do CONAR e guia de influenciadores | Padrão voluntário de autorregulação | Identificar parceria paga, benefício, comissão ou vínculo de forma imediata e compreensível; usar como controle adicional, sem tratá-lo como lei. |
| Reclamação extrajudicial | Consumidor.gov.br | Serviço público, adesão voluntária | Pode ser canal adicional; empresas participantes respondem em até dez dias. Não substitui Procon, Defensoria, MP ou Judiciário. |
| Reputação e rating | LGPD art. 20; Lei nº 12.414/2011 se houver cadastro de crédito | Lei vigente conforme o caso | Rating operacional não deve ser chamado de score de crédito; se houver banco de dados de adimplemento, aplicar regime próprio, acesso, correção e revisão. |

## 1. MARKETPLACE: intermediação, oferta e responsabilidade

### 1.1 Papéis que precisam ser explícitos

O CDC define consumidor como pessoa física ou jurídica que adquire ou utiliza serviço como destinatária final e fornecedor como quem presta ou comercializa produto ou serviço. A aplicação não é resolvida pelo rótulo “plataforma”. Uma OSC que contrata uma consultoria para sua atividade final pode merecer análise consumerista; uma empresa que compra insumo para revenda, em regra, apresenta outra relação. A vulnerabilidade concreta pode influenciar o enquadramento, que deve ser validado em cada modelo contratual. [1]

A plataforma deve manter uma matriz de papéis por fluxo:

- **hospedagem/descoberta**: o prestador cria a oferta e contrata diretamente; a plataforma vende somente seu serviço de anúncio ou conexão;
- **intermediação**: a plataforma organiza o encontro, conduz proposta, aceite, mensagens, agenda ou suporte, e recebe remuneração pela intermediação;
- **fornecimento próprio**: a plataforma promete a execução, controla o prestador ou apresenta a experiência como serviço seu;
- **publicidade**: o parceiro paga para ser destacado, independentemente de haver contratação;
- **pagamento**: o fluxo usa terceiro autorizado, ou a plataforma exerce atividade que pode ser serviço de pagamento.

Essa classificação não é apenas contratual. O CDC torna a oferta suficientemente precisa vinculante, exige informação correta e clara, e prevê consequências quando o fornecedor recusa a oferta. Se a interface da plataforma promete “prestador verificado”, “resultado garantido”, “impacto comprovado” ou “entrega em prazo X”, o sistema precisa ter evidência e dono da obrigação. Termos genéricos de “somos apenas tecnologia” não neutralizam comportamento ativo ou publicidade própria. [1]

### 1.2 Informações mínimas e atendimento

O Decreto nº 7.962/2013 exige, em meio eletrônico de oferta ou contratação, identidade e registro do fornecedor quando houver, endereço físico e eletrônico, características essenciais, riscos, preço e despesas acessórias, condições de pagamento, disponibilidade, prazo e restrições. Exige ainda sumário contratual antes da contratação, correção de erros, confirmação da aceitação, cópia conservável do contrato, atendimento eletrônico eficaz e confirmação da demanda; a manifestação do fornecedor deve ser encaminhada em até cinco dias. [2]

No marketplace, a tela precisa distinguir “operador da plataforma” de “fornecedor do serviço”. A ficha deve congelar a versão da oferta, o preço, a taxa da plataforma, quem paga a taxa, prazo, aceite, cancelamento, escopo, premissas e documentos. A taxa deve aparecer antes do aceite e nunca ser escondida como desconto de recurso de terceiro.

O direito de arrependimento do art. 49 do CDC deve ser tratado por tipo de contratação. Não é seguro prometer que ele sempre se aplica a todo serviço digital, nem excluí-lo genericamente. A política precisa reconhecer as exceções e o momento de início da execução, com revisão jurídica dos contratos.

### 1.3 Marketplace de serviços e prova

Cada contratação deve formar um pacote de prova: identidade das partes, versão da oferta, evidências de habilitação declaradas, contrato, aceite, mensagens essenciais, entregáveis, incidentes, reclamações, resposta e encerramento. A prova não deve incorporar dados pessoais além do necessário. Hash e versão preservam integridade; não transformam documento em “validado” se a fonte nunca foi verificada.

A jurisprudência do STJ reconheceu, em 2024, que sites intermediadores de comércio eletrônico são provedores de aplicações, que termos de uso são contratos de adesão e que não existe, para toda denúncia de violação contratual, obrigação automática de excluir anúncio. O caso também destacou a necessidade de contraditório antes da remoção por mera violação de termos, quando não havia direito de personalidade ou outra exceção legal. Esse entendimento é útil para desenhar a escada, mas não autoriza inércia em risco de crime, fraude, segurança, consumo ou publicidade ilícita. [5]

Em junho de 2025, o STF declarou parcialmente inconstitucional a regra do art. 19 do Marco Civil e fixou parâmetros transitórios até nova lei. Para crimes contra a honra, a regra de responsabilização continua ligada a ordem judicial, sem impedir remoção voluntária após notificação. Para crimes graves, o Tribunal tratou de deveres imediatos e falha sistêmica; para crimes em geral, atos ilícitos e contas falsas, a omissão após pedido de retirada pode gerar responsabilidade. A decisão também exige autorregulação com notificações, devido processo, relatórios anuais e canais permanentes. A aplicação exata a cada categoria de anúncio e serviço deve ser validada pelo jurídico, mas a arquitetura não pode continuar baseada apenas no antigo modelo “só removo com ordem judicial”. [3] [4]

## 2. PARTNERSHIP_SYSTEM: publicidade, conflitos e transparência

### 2.1 Publicidade identificável

O CDC exige que a publicidade seja imediatamente reconhecível e proíbe comunicação enganosa ou abusiva, inclusive por omissão de dado essencial. O ônus da prova da veracidade e correção da mensagem cabe a quem a patrocina. No produto, “parceiro”, “apoio institucional”, “conteúdo recomendado” e “oferta em destaque” são rótulos insuficientes quando existe pagamento, comissão, permuta, benefício, vínculo empregatício, embaixador ou incentivo de conteúdo. [1]

O guia do CONAR para influenciadores é padrão voluntário, mas fornece regra operacional útil: usar funcionalidade de conteúdo pago ou linguagem como “publicidade”, “#publi”, “parceria paga” ou equivalente compreensível, em primeiro plano, sem exigir clique, rolagem ou botão “mais conteúdo”. A parceria paga deve ser identificada também em vídeo, imagem, newsletter, evento, webinar, ranking e página de conhecimento. [13]

`PARTNERSHIP_SYSTEM` deve guardar: patrocinador, beneficiário, tipo de benefício, valor ou faixa, período, público, conteúdo aprovado, claim e evidência que o sustenta. A publicidade não pode ser indexada como “informação oficial” ou “recomendação neutra”. O motor deve separar resultado orgânico de publicidade, ordenar sem manipulação oculta e exibir quem paga.

O precedente do STJ sobre links patrocinados reforça o risco: em 2024, o Tribunal afastou a proteção do art. 19 para a forma de comercialização de publicidade que usava marca concorrente como palavra-chave, entendendo que o provedor não era mero hospedeiro, mas fornecedor ativo do serviço publicitário e tinha controle técnico sobre a prática. A consequência para o release é simples: monetizar a distribuição aumenta a responsabilidade sobre critérios, conflitos e claims. [6]

### 2.2 Conflito de interesses

A plataforma deve manter registro de conflitos de interesse e recusa. São sinais mínimos: parceiro que paga pelo destaque, avaliador que recebeu benefício, administrador que escolhe fornecedor relacionado, financiador com participação econômica no prestador, auditor que também vende o serviço auditado e usuário que avalia a própria oferta. O conflito deve aparecer para quem decide ou contrata; não basta ficar em log interno.

A regra de quatro olhos já presente no release deve cobrir, no mínimo, aprovação de parceiro de alto risco, alteração de ranking patrocinado, remoção definitiva por acusação de fraude, liberação de conta suspensa e decisão sobre compensação. Quem abriu a denúncia, recebeu o benefício ou tomou a decisão comercial não deve ser o único aprovador.

Essa seção é principalmente **hipótese de governança de produto**, apoiada por deveres gerais de transparência, boa-fé, não discriminação e prestação de contas. Não se deve apresentá-la como um “cadastro legal de conflitos” universal fora de regimes específicos.

## 3. MODERATION_LADDER: denúncias, apuração e recurso

A escada recomendada é:

1. **Denúncia**: recebimento com protocolo, categoria, URL/ID do anúncio, relação do denunciante com o fato e evidência mínima. Denúncia não é prova.
2. **Suspeita/triagem**: priorização por risco e medida temporária. Pode limitar visibilidade, impedir nova contratação ou pedir esclarecimento, sem rotular publicamente como fraude.
3. **Infração apurada**: investigação documentada, oportunidade de resposta e decisão fundamentada. O motor deve separar falsidade de claim, descumprimento contratual, risco à segurança, abuso, conteúdo ilícito e fraude.
4. **Consequência**: correção, despublicação, suspensão, encerramento, retenção de benefício não pago por terceiro, encaminhamento à autoridade ou comunicação a afetados, com proporcionalidade e recurso.

Há duas trilhas que não devem ser confundidas. A primeira é moderação por termos privados; nela, o STJ exige contraditório quando a denúncia só afirma violação contratual. A segunda é segurança e ilícito manifesto, incluindo fraude operacional, produto proibido, ameaça, exploração de crianças, intimidade ou crime; nela, medida temporária imediata pode ser necessária, seguida de apuração e notificação compatíveis. [4] [5]

Cada decisão deve gravar regra aplicada, evidência, data, agente ou modelo, risco, ação, comunicação, resposta e recurso. O usuário afetado deve conhecer o motivo em linguagem simples, o que precisa corrigir e como recorrer. A plataforma deve medir falso positivo, falso negativo, tempo de resposta, reincidência, taxa de reversão e impacto por grupo, sem transformar métricas de moderação em prova de ausência de risco.

## 4. REPUTATION_ARCHITECTURE: avaliação verificável sem punição opaca

A reputação deve ser construída sobre eventos verificáveis, não sobre impressão agregada sem contexto. O mínimo recomendado é vincular avaliação a contratação concluída ou interação autenticada, impedir autoavaliação e duplicidade, registrar data, relação entre avaliador e avaliado, permitir resposta e tratar avaliações fraudulentas em fluxo de denúncia.

A interface deve mostrar volume de avaliações, período, distribuição, critérios, data de atualização, avaliações removidas por motivo e diferença entre “avaliação de usuário”, “verificação documental” e “selo editorial”. Uma média sem tamanho da amostra pode induzir erro. “Verificado” deve ter escopo: “CNPJ consultado em data X”, “documento recebido”, “transação concluída” ou “referência confirmada”. Nunca deve significar “sem risco” ou “qualidade garantida” sem prova.

O ranqueamento precisa separar critérios objetivos de publicidade. Se taxa paga, comissão, disponibilidade comercial ou afinidade de parceiro altera a ordem, o usuário deve saber. A própria plataforma precisa auditar se resultados patrocinados ou parceiros recebem vantagem que parece avaliação independente.

Se o rating decidir sozinho a suspensão, acesso ao marketplace, preço, convite ou elegibilidade, ele se aproxima de decisão automatizada que afeta interesses. A LGPD art. 20 assegura pedido de revisão de decisão baseada unicamente em tratamento automatizado e acesso a informações claras sobre critérios e procedimentos, respeitados segredos comerciais. O fluxo deve oferecer revisão humana, correção de dado-fonte e registro da decisão final. [7]

A Lei nº 12.414/2011, por sua vez, disciplina cadastro positivo e histórico de adimplemento. Um índice de execução ou confiança de marketplace não deve ser chamado de “score de crédito” nem compartilhado como cadastro de crédito sem analisar o regime próprio, finalidades, direitos de acesso, correção, cancelamento e revisão. Reputação de serviço, risco antifraude e crédito são produtos distintos. [17] [7]

## 5. RISK_FRAUD: KYC proporcional, prevenção e resposta

### 5.1 KYC não é requisito universal de marketplace

A Lei nº 9.613/1998 sujeita aos deveres de identificação, cadastro, registros e comunicação os setores enumerados no art. 9º, como intermediação de recursos financeiros, valores mobiliários, cartões, imóveis, bens de alto valor, ativos virtuais e outros. Um marketplace geral de serviços, sem intermediar recursos regulados e sem atuar em setor listado, não deve declarar que está “obrigado ao KYC/PLD” apenas por ser digital. [10]

A Resolução COAF nº 41/2022 é dirigida a empresas de factoring. Ela ilustra uma abordagem baseada em risco — identificação e qualificação de clientes, beneficiário final, propósito, PEP, sanções, registros e controles reforçados —, mas não deve ser copiada como obrigação geral do IMPACTO. Se o modelo mudar para pagamento, investimento, crédito, ativos, imóveis ou outro setor regulado, será necessária nova análise de enquadramento e parceiro/autoridade competente. [11]

A Lei nº 12.865/2013 define instituição de pagamento e inclui disponibilizar aporte ou saque em conta, executar ou facilitar instrução de pagamento, gerir conta, emitir instrumento, credenciar aceitação, executar remessa e moeda eletrônica. Portanto, a arquitetura não custodial é uma barreira de escopo, não um slogan: qualquer mudança no fluxo financeiro exige revisão antes da implementação. [12]

### 5.2 Modelo proporcional sugerido

**Baixo risco**: cadastro mínimo, e-mail verificado, telefone ou fator adicional, aceite de termos aprovados, CNPJ/identificação quando necessário, declaração do papel e controles de abuso. Não solicitar documento sensível ou biometria por padrão.

**Risco intermediário**: validar existência e situação cadastral, representante e domínio de contato; exigir evidência de experiência ou execução; limitar volume e velocidade; revisar conflitos e duplicidade de contas.

**Alto risco**: escalada humana para operação de alto valor, pagamento, repetição de chargeback, múltiplas contas relacionadas, denúncia consistente, incompatibilidade documental, PEP/sanção quando legalmente pertinente ou atividade regulada. A escalada deve informar a finalidade, o dado necessário, prazo de retenção e como contestar.

A ANPD orienta que legítimo interesse requer teste de finalidade, necessidade, balanceamento e salvaguardas, com análise específica para cada finalidade. “Prevenir fraude” não autoriza guardar tudo para sempre, criar lista negra universal ou compartilhar dados com parceiros sem finalidade, base, necessidade e transparência. Para dados sensíveis, o legítimo interesse não é a base geral; a solução deve evitar pedir dado sensível ou encontrar base legal adequada. [8] [7]

### 5.3 Dados e evidências

O modelo mínimo deve separar:

- identificadores e papel do usuário;
- evidência de verificação, com fonte, data, resultado, método e validade;
- sinais de risco, com regra, versão e explicação curta;
- denúncia e apuração, sem converter suspeita em fato;
- decisão, aprovadores, recurso e desfecho;
- retenção e acesso por finalidade;
- compartilhamento com parceiro, provedor de pagamento ou autoridade.

Não armazenar documento bruto se hash, campos mínimos ou confirmação de terceiro bastarem. Criptografar, limitar acesso, registrar consulta, aplicar segregação por organização, apagar ou anonimizar quando a finalidade terminar e manter cópia auditável apenas quando obrigação ou defesa de direitos justificar. A retenção deve reconciliar LGPD, registros do Marco Civil, provas contratuais e o prazo de cinco anos do registro de incidentes da ANPD; prazos internos não podem ser tratados como lei universal.

A Resolução CD/ANPD nº 15/2024 considera especialmente relevantes incidentes que envolvam, entre outros, dados financeiros, autenticação, crianças, dados sensíveis ou larga escala, inclusive quando possam causar fraude financeira ou roubo de identidade. O controlador deve comunicar ANPD e titulares em três dias úteis a partir do conhecimento de que o incidente afetou dados, complementar informações quando necessário e manter o registro do incidente por pelo menos cinco anos. O produto precisa de playbook, responsável, relógio de prazo e modelo de comunicação. [9]

## Requisitos de produto

### Antes da contratação

- Ficha separada de plataforma, fornecedor, parceiro pagante e eventual processador de pagamento.
- Oferta versionada com escopo, preço, taxa, tributos quando aplicáveis, prazo, risco, disponibilidade, cancelamento, arrependimento e canal de suporte.
- Etiqueta visível para publicidade, parceria paga, benefício, comissão e conteúdo de demonstração.
- Critérios de ordenação resumidos e indicação de resultado patrocinado.
- Verificação com escopo e data; nenhum selo de qualidade absoluta.
- Aviso de privacidade por finalidade e controle de preferências não essenciais.

### Durante e após a contratação

- Contrato conservável, aceite com hash e confirmação.
- Mensageria e suporte com protocolo, prazo e resposta; meta interna igual ou mais protetiva que o prazo legal aplicável.
- Botão de denúncia por oferta, avaliação, parceiro e usuário; classificação de risco.
- Escada de moderação com triagem, medida temporária, apuração, consequência e recurso.
- Registro de quem paga, quem se beneficia e quem aprovou decisão.
- Avaliação só após interação elegível, com direito de resposta e correção.
- Exportação e acesso a dados, critérios de decisão automatizada, correção e eliminação conforme finalidade e obrigações de retenção.

## Requisitos de dados e governança

1. **Catálogo de finalidades**: contratação, segurança, antifraude, suporte, reputação, publicidade, métricas e obrigação legal não podem compartilhar a mesma base genérica.
2. **Matriz de agentes**: controlador, operador, controlador independente e destinatário; incluir fornecedor, parceiro, provedor de verificação e pagamento.
3. **Proveniência**: cada selo, risco, avaliação e claim deve apontar para fonte, data, método e estado (`declarado`, `recebido`, `verificado`, `invalidado`, `em apuração`).
4. **Direitos**: acesso, correção, contestação, exclusão quando possível e revisão humana de decisão automatizada; a auditoria deve alcançar o dado que alimentou a reputação.
5. **Segurança**: autenticação forte para administração, criptografia, logs de consulta, RLS/multitenancy, segregação de documentos e monitoramento de abuso.
6. **Compartilhamento**: finalidade, base, necessidade, destinatário, prazo, país, contrato e registro da transferência; nunca compartilhar lista de “suspeitos” com parceiro por conveniência.
7. **Conflitos**: registro de relação material, recusa, aprovador e comunicação ao usuário afetado.
8. **Retenção**: tabela única que reconcilie LGPD, MCI, prova contratual, defesa de direitos, KYC setorial e incidente; apagar o que não precisa persistir.

## Testes e controles de aceitação

- **Oferta**: teste de contrato exibindo operador, fornecedor, preço, taxa, prazo, risco, versão e política; confirmar que uma alteração invalida aceite anterior.
- **Publicidade**: teste visual e automatizado que bloqueie publicação sem etiqueta quando houver pagamento, comissão, permuta ou vínculo; verificar primeira tela e mobile.
- **Ranqueamento**: executar o mesmo conjunto com e sem patrocínio e provar que a etiqueta e o motivo aparecem; auditar conflito de interesse.
- **Denúncia**: testar denúncia falsa, duplicada, maliciosa, urgente, de marca, de privacidade e de fraude; nenhuma gera “fraude” pública sem apuração.
- **Contraditório**: provar notificação, prazo, resposta, decisão, reversão e justificativa; medida urgente deve ter revisão posterior.
- **Reputação**: bloquear autoavaliação, duplicidade, avaliação sem interação elegível e manipulação por conta relacionada; mostrar amostra e data.
- **Decisão automatizada**: para suspensão por risco, gerar razão em categorias compreensíveis, encaminhar a humano e registrar o resultado da revisão.
- **KYC proporcional**: verificar que usuário de baixo risco não recebe coleta de alto risco; gatilhos de escalada devem ser reproduzíveis e revisáveis.
- **Fraude**: simular account takeover, documento falsificado, duplicidade, chargeback, conluio de avaliações, phishing e parceiro conflitante; medir falso positivo, falso negativo e tempo de recuperação.
- **Incidente**: simular vazamento de autenticação/financeiro e provar relógio de três dias úteis, comunicação individual, complemento e registro de cinco anos.
- **Não custodial**: testes negativos para carteira, saldo, split, payout, retenção e desconto de dinheiro de terceiro; tentativa deve falhar sem provedor e autorização regulatória.
- **Claims**: varredura que rejeite “seguro”, “sem fraude”, “homologado”, “verificado”, “oficial”, “impacto comprovado” e equivalentes quando a evidência ou o escopo não existir.

## Claims proibidos ou condicionados

Não publicar, sem evidência, escopo e revisão:

- “A plataforma é legalmente responsável apenas pelo fornecedor” ou “não temos qualquer responsabilidade”.
- “Marketplace seguro contra fraude”, “fraude zero”, “KYC completo” ou “todos os parceiros verificados”.
- “Selo oficial”, “homologado”, “certificado”, “impacto validado” ou “projeto IMPACTO Ready” fora do conjunto de critérios e evidências que o estado realmente mede.
- “Avaliações imparciais” ou “ranking neutro” quando houver publicidade, comissão, regras comerciais ou amostra limitada.
- “Parceiro recomendado” sem revelar vínculo, benefício, critério e período.
- “Denunciado por fraude” ou “fraudador” antes de apuração concluída e decisão fundamentada.
- “LGPD compliant”, “CDC compliant”, “PLD compliant” ou “aprovado pela ANPD/COAF/BCB” sem base verificável, aprovação ou enquadramento que permita o claim.
- “Pagamento processado pela plataforma”, “valor garantido”, “repasse” ou “custódia” enquanto o release permanecer não custodial e sem provedor ligado.

## Lacunas e decisões pendentes

1. Parecer interno sobre quando OSC, empresa, financiador, profissional e órgão público são destinatários finais e quando o CDC incide.
2. Classificação jurídica final de cada experiência: anúncio, intermediação, serviço próprio, parceria, doação, financiamento ou pagamento.
3. Revisão e aprovação dos documentos legais; hoje o release só contém minutas.
4. Definição do encarregado, bases legais, RIPD/DPIA, contratos de operador e política de retenção.
5. Decisão sobre verificação de CNPJ/representante, sanções, PEP e beneficiário final, limitada ao risco e à finalidade.
6. Plano para STF pós-2025: taxonomia de ilícitos, notificações, autorregulação, devido processo, canal permanente e relatório de transparência.
7. Critério de escalada e responsabilidade para produtos/serviços regulados, incluindo telecomunicações, pagamentos, ativos, imóveis e publicidade de alto risco.
8. Política de avaliações: elegibilidade, amostra mínima, resposta, remoção, reversão, transparência e prevenção de conluio.
9. Separação comercial/editorial no Knowledge Hub e revisão de todo conteúdo `demo=true` antes de publicação.
10. Integração com Consumidor.gov.br, se desejada: adesão é voluntária, resposta em até dez dias e não substitui canais estatais.
11. Auditoria de acessibilidade e leitura em primeira tela para etiquetas de publicidade, denúncia, motivo e recurso.
12. Validação de claims em todas as telas e APIs, inclusive respostas de IA, PDFs, notificações e exportações.

## Referências

[1]: https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm "Lei nº 8.078/1990 — Código de Defesa do Consumidor, Presidência da República, 11/09/1990". Sustenta definições de consumidor e fornecedor, direitos básicos, oferta vinculante, informação, responsabilidade por prepostos, publicidade identificável, proibição de publicidade enganosa/abusiva, ônus da prova e cláusulas abusivas.

[2]: https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2013/decreto/d7962.htm "Decreto nº 7.962/2013 — contratação no comércio eletrônico, Presidência da República, 15/03/2013". Sustenta informações obrigatórias, identificação do fornecedor, sumário contratual, correção de erros, confirmação, atendimento eletrônico, resposta em até cinco dias, segurança e arrependimento.

[3]: https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2014/lei/l12965.htm "Lei nº 12.965/2014 — Marco Civil da Internet, Presidência da República, 23/04/2014". Sustenta proteção de registros e dados, guarda de registros de aplicações por seis meses para pessoa jurídica organizada e econômica, regra legal de responsabilidade por conteúdo de terceiros, contraditório e exceção de intimidade.

[4]: https://noticias.stf.jus.br/postsnoticias/stf-define-parametros-para-responsabilizacao-de-plataformas-por-conteudos-de-terceiros/ "STF define parâmetros para responsabilização de plataformas por conteúdos de terceiros, Supremo Tribunal Federal, 26/06/2025". Sustenta o estado atual da interpretação do art. 19, a distinção entre honra, crimes graves e ilícitos em geral, remoção após notificação em hipóteses definidas, devido processo, autorregulação, canais e relatórios de transparência.

[5]: https://www.stj.jus.br/sites/portalp/Paginas/Comunicacao/Noticias/2024/16092024-Mercado-Livre-nao-e-obrigado-a-excluir-anuncios-denunciados-por-violacao-dos-termos-de-uso-do-site.aspx "Mercado Livre não é obrigado a excluir anúncios denunciados por violação dos termos de uso do site, Superior Tribunal de Justiça, 16/09/2024 (REsp 2.088.236)". Sustenta a qualificação de intermediadores como provedores de aplicações, natureza contratual dos termos, ausência de dever automático de remoção por violação contratual e necessidade de contraditório no caso analisado.

[6]: https://www.stj.jus.br/sites/portalp/Paginas/Comunicacao/Noticias/2024/09072024-Terceira-Turma-mantem-condenacao-do-Google-em-caso-de-concorrencia-desleal-com-links-patrocinados.aspx "Terceira Turma mantém condenação do Google em caso de concorrência desleal com links patrocinados, Superior Tribunal de Justiça, 09/07/2024 (REsp 2.096.417)". Sustenta que a limitação do art. 19 não cobre automaticamente a forma ativa de comercialização publicitária e que o provedor pode responder quando controla palavra-chave e fomenta confusão/concorrência desleal.

[7]: https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm "Lei nº 13.709/2018 — Lei Geral de Proteção de Dados Pessoais, Presidência da República, 14/08/2018". Sustenta princípios de finalidade, necessidade, transparência, segurança, prevenção, não discriminação e prestação de contas; bases legais; direitos; revisão de decisões automatizadas; segurança; responsabilidade e incidentes.

[8]: https://www.gov.br/anpd/pt-br/centrais-de-conteudo/materiais-educativos-e-publicacoes/guia_orientativo_hipoteses_legais_tratamento_de_dados_pessoais_legitimo_interesse "Guia Orientativo: Hipóteses legais de tratamento de dados pessoais — Legítimo Interesse, ANPD, publicado em 22/11/2024 e modificado em 23/01/2025". Sustenta o teste de finalidade, necessidade, balanceamento e salvaguardas, a minimização por finalidade e a necessidade de reavaliar nova finalidade.

[9]: https://www.in.gov.br/en/web/dou/-/resolucao-cd/anpd-n-15-de-24-de-abril-de-2024-556243024 "Resolução CD/ANPD nº 15/2024 — Regulamento de Comunicação de Incidente de Segurança, ANPD, 24/04/2024". Sustenta critérios de risco relevante, comunicação à ANPD e aos titulares em três dias úteis, conteúdo mínimo, complemento e registro do incidente por cinco anos.

[10]: https://www.planalto.gov.br/ccivil_03/leis/l9613.htm "Lei nº 9.613/1998 — prevenção e repressão à lavagem de dinheiro, Presidência da República, 03/03/1998, com alterações". Sustenta o caráter setorial do art. 9º e os deveres de identificação, cadastro e registros para pessoas sujeitas ao mecanismo de controle; não sustenta KYC universal para marketplace geral.

[11]: https://www.gov.br/coaf/pt-br/acesso-a-informacao/Institucional/a-atividade-de-supervisao/regulacao/supervisao/normas-1/resolucao-coaf-no-041-de-08-08.2022 "Resolução COAF nº 41/2022, Conselho de Controle de Atividades Financeiras, 08/08/2022". Sustenta, no setor de factoring, política e avaliação interna proporcionais ao risco, diligência sobre clientes/beneficiário final, PEP, sanções, registros e controles reforçados; é exemplo setorial, não regra geral do produto.

[12]: https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2013/lei/l12865.htm "Lei nº 12.865/2013 — arranjos e instituições de pagamento, Presidência da República, 09/10/2013". Sustenta definições de instituição, conta e serviço de pagamento, competências do BCB e o gatilho de análise regulatória quando a plataforma recebe, gere, credencia ou facilita pagamentos.

[13]: https://conar.wpenginepowered.com/wp-content/uploads/2026/05/260525_GUIA_INFLUENCIADORES_CONAR_v6.pdf "Guia de Marketing e Publicidade por Influenciadores Digitais, CONAR, versão 6, 2026". Sustenta como padrão voluntário a transparência de vínculo, identificação imediata de publicidade/parceria paga e uso de linguagem compreensível e visível em diferentes formatos.

[14]: https://www.consumidor.gov.br/pages/conteudo/publico/1 "Conheça o Consumidor.gov.br, Secretaria Nacional do Consumidor/Ministério da Justiça, página consultada em 2026". Sustenta a natureza pública e gratuita do canal, adesão voluntária, resposta empresarial em até dez dias, avaliação em até vinte dias e não substituição dos órgãos tradicionais.

[15]: https://www.ipea.gov.br/cts/pt/central-de-conteudo/artigos/artigos/417-uniao-europeia-contra-big-techs "União Europeia contra as big techs, Ipea/CTS, 13/03/2024". Sustenta literatura institucional comparada sobre notificação de conteúdo ilegal, reclamação, declarações de motivos, transparência de anúncios, avaliação de riscos e o caráter não automaticamente vigente do DSA no Brasil.

[16]: https://www.gov.br/mj/pt-br/assuntos/sua-protecao/combate-a-pirataria/relatorio-anual/relatorio-anual_final_-2021-editorado.pdf "Relatório Anual 2021 do Conselho Nacional de Combate à Pirataria, Ministério da Justiça/CNCP, 2021". Sustenta orientação administrativa sobre prevenção em marketplaces de produtos não homologados, cooperação com titulares e possibilidade de responsabilidade administrativa quando a plataforma participa ativa e decisivamente da cadeia; não é regra geral para todo serviço.

[17]: https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2011/lei/l12414.htm "Lei nº 12.414/2011 — cadastro positivo, Presidência da República, 09/06/2011". Sustenta a distinção entre reputação operacional e banco de dados de adimplemento/crédito, além de acesso, correção, cancelamento e revisão de decisões automatizadas no regime próprio.

[18]: https://revistaeletronicaoabrj.emnuvens.com.br/revista/article/view/898 "Responsabilidade civil das plataformas de marketplace pela oferta de produtos contrafeitos e falsificados, Flávia Lira da Silva/OAB-RJ, 2026". Sustenta literatura jurídica sobre controle econômico e informacional, ranqueamento, gestão reputacional e hipótese de responsabilidade maior conforme a participação ativa; é literatura, não fonte normativa vinculante.

[19]: https://cesaf.mpto.mp.br/revista/index.php/revistampto/article/view/52 "O impacto dos marketplaces digitais na responsabilidade civil, Vico Barbosa Casson e Vinicius Pinheiro Marques, Revista Jurídica do Ministério Público do Estado do Tocantins, 2021". Sustenta literatura institucional/acadêmica sobre limites da intermediação, aplicação casuística do CDC e jurisprudência de marketplaces; não substitui lei ou decisão vinculante.

## Evidências internas consultadas

- `/home/ubuntu/impacto-trust-knowledge-v0.26.0/README.md`: estado não publicado, sem provedor real e arquitetura não custodial; contrato como regra de operação e taxa própria da plataforma.
- `/home/ubuntu/impacto-trust-knowledge-v0.26.0/docs/LEGAL_FRAMEWORK.md`: onze documentos legais em minuta, incluindo marketplace e intermediação; aceite bloqueado enquanto não aprovados.
- `/home/ubuntu/impacto-trust-knowledge-v0.26.0/docs/LGPD.md`: minimização, ausência de dados sensíveis solicitados, controles de acesso e pendências de base legal, RIPD/DPIA, encarregado e operadores.
- `/home/ubuntu/impacto-trust-knowledge-v0.26.0/KNOWLEDGE_HUB.md`: conteúdo seed em demonstração, origem e data para conteúdo regulatório, revisão humana e ausência de IA generativa.
- `/home/ubuntu/impacto-trust-knowledge-v0.26.0/docs/PROCUREMENT.md`: benchmark interno não é preço de mercado e “preço possivelmente fora do padrão” não é “fraude”.
