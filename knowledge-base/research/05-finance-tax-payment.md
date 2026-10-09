# Pesquisa 05 — Fiscal, financeiro, pagamentos e arquitetura não custodial

**Release analisado:** Plataforma Impacto — v0.26.0  
**Data da pesquisa:** 08/10/2026  
**Natureza:** pesquisa regulatória e de requisitos de produto; não é parecer jurídico, contábil ou tributário personalizado.

## Escopo

Esta pesquisa trata somente do domínio **fiscal, financeiro, pagamentos e arquitetura não custodial** para um SaaS brasileiro que cobra assinatura, serviço de plataforma ou taxa própria. O foco é a relação entre contratos, preço, emissão de nota, ISS, obrigações fiscais eletrônicas, meios de pagamento, Pix, arranjos de pagamento, instituições de pagamento, CVM e prevenção à lavagem de dinheiro (PLD/FTP).

A premissa funcional do release é que a plataforma pode registrar contratos, calcular valores, emitir instruções, cobrar sua própria assinatura ou taxa e conciliar evidências, mas **não precisa receber, segregar, manter, repassar ou investir dinheiro de terceiros**. Essa premissa é uma decisão de arquitetura, não uma conclusão jurídica automática: a classificação regulatória acompanha o comportamento efetivo, a estrutura contratual e o papel exercido, e não apenas o rótulo “não custodial”.

As fontes abaixo são separadas em quatro categorias:

- **Lei/regulamento vigente:** Constituição e leis complementares ou ordinárias, normas do Banco Central e da CVM vigentes na consulta.
- **Orientação administrativa:** páginas de serviço, FAQ, manuais e ofícios dos órgãos; orientam a aplicação e a operação, mas não substituem a lei.
- **Padrão técnico/voluntário:** leiautes, APIs, padrões de integração e controles que dependem de adesão ou contratação.
- **Hipótese de produto:** desenho proposto para o release, que precisa de validação profissional antes de ser ativado.

## Estado atual do release e correções necessárias

O README do v0.26.0 informa corretamente que a versão está em **base técnica fechada**, não publicada, sem provedor de pagamento, fiscal ou de cobrança ligado; Android/iOS não foram construídos e nenhuma cobrança real é possível no estado atual [19]. O mesmo README registra que o contrato passou a ser regra de operação: a taxa e quem paga são definidos no acordo, a matriz de distribuição é imutável e a cobrança da taxa é própria da plataforma, sem descontar dinheiro em trânsito [19].

Há, portanto, quatro correções de linguagem e governança que devem permanecer explícitas:

1. **“Cobrança implementada” não significa cobrança real.** O PAYMENT_ARCHITECTURE modela cartão, recorrência, parcelamento, Pix e boleto, mas declara que não há provedor, chave, conta, identificador de preço ou cobrança real configurados. O Financial Engine também declara que não há NFS-e nem provedor fiscal ligado [26] [25].
2. **A taxa de plataforma não é take rate sobre fluxo custodiado.** O desenho v0.26.0 permite, como hipótese de produto, uma cobrança própria ao pagador do acordo somente se `contract.platform_service_fee` estiver ativa e houver contrato aprovado. O dinheiro financiado continua fora da plataforma. Isso ainda requer definição do serviço tributável, município, código de serviço, regime, documento fiscal e contrato definitivo.
3. **As minutas legais não estão vigentes.** O LEGAL_FRAMEWORK informa que as onze minutas estão em `draft`; nenhum aceite legal pode ser registrado enquanto não houver aprovação e vigência [28]. A ativação comercial não pode transformar uma minuta em contrato apenas por configuração.
4. **“Não custodial” não autoriza qualquer fluxo de pagamentos.** A NON_CUSTODIAL_ARCHITECTURE proíbe wallet, saldo de terceiro, payout, split e escrow no núcleo; aceita cálculo, instrução e conciliação. Se a plataforma começar a iniciar transações, habilitar recebedores, participar da liquidação, gerir contas ou captar/intermediar recursos, uma nova análise regulatória será obrigatória [27].

O FISCAL_RULE_ENGINE está melhor posicionado do que o README antigo sugeria: é dirigido por dados, exige fonte, vigência, confiança e aprovação, e separa **estimativa**, **regra identificada**, **possível elegibilidade**, **elegibilidade documental** e **validação profissional**. Ele não deve afirmar direito a benefício fiscal sem regra publicada e validação humana [24].

### Correção executiva do estado

| Área | O que existe no v0.26.0 | O que não pode ser afirmado | Correção necessária antes de produção |
|---|---|---|---|
| Contrato e preço | Versionamento, aceite com hash, preço congelado, taxa própria condicionada a regra | “Contrato vigente” ou “aceite válido” para as onze minutas | Aprovação jurídica, publicação, vigência, razão social/CNPJ/foro e matriz de papéis |
| FINANCIAL_ENGINE | Calcula, instrui e concilia; competência e partida dobrada da própria plataforma | “A plataforma pagou”, “repassou” ou “liquidou” terceiro | Manter evidência externa e separar caixa/receita própria de dinheiro de terceiro |
| FISCAL_RULE_ENGINE | Regras com fonte e data; estimativas qualificadas | “ISS correto”, “benefício fiscal” ou “nota emitida” sem integração | Classificar serviço, município, regime, retenção e NFS-e com contador e provedor |
| PAYMENT_ARCHITECTURE | Máquina de estados, webhooks e idempotência modelados | “Pix/cartão/boleto processado” | Contratar PSP, configurar credenciais e homologar produção; sem isso, status é simulado |
| NON_CUSTODIAL_ARCHITECTURE | Nenhum wallet/split/payout/escrow/saldo de terceiro | “Instituição de pagamento” ou “arranjo Pix” | Rejeitar funções que mudem o papel econômico; se necessário, ADR e análise BCB |
| CVM/PLD | Nenhuma oferta de investimento nem operação de pagamento de terceiro declarada | “Plataforma de investimento”, “PLD compliant” | Gatilhos de triagem e bloqueio de linguagem; escalar se houver valor mobiliário, captação ou intermediação |

## Mapa normativo de obrigações e gatilhos

### 1. SaaS, contrato, assinatura e taxa de plataforma

O Código Civil disciplina a prestação de serviços e fornece o enquadramento geral para contratação, execução, boa-fé e remuneração; a prestação que não estiver submetida à legislação trabalhista ou a lei especial segue o capítulo próprio do Código Civil [9]. No produto, isso se traduz em identificação das partes, objeto, preço, prazo, aceite, renovação, cancelamento, inadimplemento, tributos, evidências e responsabilidades.

O CDC não deve ser presumido nem afastado no banco. Se houver consumidor nos termos da relação concreta, o Código garante informação adequada e clara sobre preço, características e tributos, vincula a oferta ao contrato e proíbe publicidade enganosa e cobrança com afirmação falsa ou enganosa [10]. Em B2B ou B2G, a incidência depende dos fatos e do contrato; a plataforma deve guardar o papel da parte e deixar a decisão jurídica registrada, sem automatizar uma conclusão genérica.

A Lei nº 14.063/2020 classifica assinaturas simples, avançadas e qualificadas e exige assinatura qualificada em hipóteses específicas, inclusive em emissões de notas fiscais eletrônicas, com exceção de pessoas físicas e MEIs; mas seu capítulo sobre assinaturas em interações com o poder público **não se aplica, em regra, a relações privadas entre pessoas naturais ou pessoas jurídicas privadas** [11]. Logo, a lei não deve ser usada como promessa de que toda assinatura simples de SaaS tem o mesmo efeito de uma assinatura qualificada ou de que um contrato privado exige ICP-Brasil. O produto deve registrar evidências de autoria, integridade, versão e manifestação de vontade e, para atos públicos ou quando a norma/contrato exigir, exigir o nível apropriado.

**Obrigação de produto:** nenhum preço deve ser cobrado sem oferta e contrato identificáveis; nenhum aceite deve apontar para minuta; mudança de preço ou taxa deve gerar nova versão e novo registro de aceite quando necessário. A taxa própria precisa indicar: serviço prestado pela plataforma, base de cálculo contratual, percentual ou valor fixo, pagador, fato gerador comercial, momento de cobrança, tributos, cancelamento e ausência de retenção de recursos de terceiros.

### 2. ISS e classificação do serviço

A LC nº 116/2003 estabelece que o ISS incide sobre a prestação dos serviços constantes da lista anexa e que a incidência não depende do nome dado ao serviço [1]. A lista inclui, entre outros, processamento, armazenamento ou hospedagem de dados e sistemas (subitem 1.03), elaboração de programas (1.04), licenciamento ou cessão de direito de uso de programas (1.05), assessoria/consultoria e suporte em informática [1]. Um SaaS pode combinar mais de um elemento; a classificação final deve considerar a prestação efetiva, contrato, município e regime, não o rótulo “software” isoladamente.

A regra geral da LC nº 116/2003 considera o imposto devido no local do estabelecimento prestador, ressalvadas as hipóteses legais específicas do art. 3º [1]. A plataforma deve, por isso, manter endereço/estabelecimento, município de incidência, código do serviço, alíquota vigente, regime tributário e eventuais regras de retenção como dados versionados. Não é seguro transformar o município do cliente ou o local do servidor em regra universal para todo SaaS.

A LC nº 175/2020 criou obrigação acessória nacional para os subitens 4.22, 4.23, 5.09, 15.01 e 15.09, com declaração eletrônica padronizada e prazo até o dia 25 do mês seguinte, além de regras específicas de emissão, pagamento e fornecimento de dados pelos municípios [2]. A norma **não deve ser aplicada por analogia** a uma assinatura SaaS classificada nos subitens 1.03 ou 1.05. O motor deve perguntar qual subitem é efetivamente aplicável antes de selecionar a obrigação.

O Portal da NFS-e informa que a NFS-e padrão nacional formaliza a prestação de serviços, tem validade jurídica nacional e, quando aplicável, substitui a emissão municipal; o uso depende do contribuinte e do município conveniado. Para integração por API há credenciamento prévio no Painel do Contribuinte [3] [4]. Isso é orientação operacional, não prova de que o release já emite documentos. Sem emissor, credenciamento, certificado/credencial e parâmetros municipais, a tela deve dizer **“NFS-e não configurada”**.

A LC nº 214/2025, que institui a reforma do consumo, exige documento fiscal eletrônico para operações com bens ou serviços sujeitas ao IBS/CBS e prevê compartilhamento padronizado de dados; também disciplina o procedimento padrão de split payment e a vinculação entre documento fiscal e transação de pagamento [8]. A produção de efeitos, leiautes, atos conjuntos e transição precisam ser acompanhados. No v0.26.0, a LC 214 deve entrar como **dependência de roadmap e monitoramento**, não como alegação de que a plataforma já está pronta para IBS/CBS ou split payment.

### 3. Obrigações fiscais eletrônicas e retenções

A EFD-Reinf não é uma obrigação automática para toda nota emitida ou recebida. A orientação atual da Receita Federal informa que devem ser enviados, por competência, estabelecimento e prestador, os documentos fiscais de serviços tomados que possuam retenção previdenciária nos termos do art. 31 da Lei nº 8.212/1991 [5] [6]. O mesmo FAQ distingue fatos geradores: retenção previdenciária pode ser vinculada à emissão da nota; IRRF, ao crédito ou pagamento; CSLL, PIS e Cofins, ao pagamento, conforme a situação [5].

O Manual da DCTFWeb explica que eventos da EFD-Reinf alimentam a DCTFWeb; retenções sobre notas de serviços tomados geram débitos e retenções sofridas podem gerar créditos, conforme o caso [7]. Portanto, o produto precisa separar **nota emitida**, **nota tomada**, **serviço com cessão de mão de obra/empreitada**, **retenção previdenciária**, **IRRF/CSLL/PIS/Cofins**, **competência**, **pagamento**, **crédito** e **transmissão**. Não deve afirmar que “toda NFS-e entra na EFD-Reinf” nem que o SaaS substitui a escrituração do contribuinte.

A plataforma deve oferecer exportação estruturada para o contador e trilha de documentos, mas não escolher sozinha se há retenção. A regra deve ser parametrizável por serviço, fornecedor, regime e fundamento, com revisão profissional registrada. A contratação de um fornecedor pessoa jurídica não torna, por si só, toda despesa da plataforma sujeita a retenção; o fato depende da legislação e dos fatos da operação.

### 4. Meios de pagamento, Pix e arranjos

A Lei nº 12.865/2013 define arranjo de pagamento como conjunto de regras e procedimentos que disciplina serviço de pagamento aceito por mais de um recebedor; define instituição de pagamento e inclui executar/facilitar instrução de pagamento, gerir conta de pagamento, emitir instrumento, credenciar aceitação, remeter fundos e gerir moeda eletrônica [12]. O Banco Central resume que IP é pessoa jurídica que viabiliza compra, venda e movimentação de recursos no âmbito de arranjo, sem poder conceder empréstimos ou financiamentos como instituição financeira [13].

A Resolução BCB nº 80/2021, em versão vigente atualizada em 06/11/2025, classifica IPs como emissor de moeda eletrônica, emissor pós-pago, credenciador e iniciador de transação. O iniciador inicia a transação sem gerir conta e sem deter os fundos, mas continua sendo uma modalidade regulada de IP; entre outras vedações, não pode guardar credenciais do usuário nem usar dados para finalidade diversa [14]. **Não custódia, isoladamente, não retira o iniciador do campo regulatório.**

O Banco Central descreve o subcredenciador como participante que habilita recebedores para aceitar instrumento de pagamento, sem ser credor perante o emissor no processo de liquidação [15]. A plataforma não deve chamar seu catálogo, contrato ou instrução de “subcredenciamento” apenas porque conecta financiador e projeto. Se habilitar estabelecimentos para aceitar cartão, integrar a liquidação, cobrar em nome do recebedor ou participar do fluxo, o papel deve ser analisado com o PSP e com advogado regulatório.

O Banco Central também explica que arranjos podem incluir cartões, transferências e remessas e que alguns arranjos de propósito limitado não estão sujeitos à supervisão do BC; a exceção deve ser conferida conforme volume, abrangência, natureza e finalidade do arranjo [16]. Ela não é uma dispensa genérica para uma plataforma aberta que conecta múltiplos recebedores.

O Pix é um arranjo do Banco Central com regras próprias. A arquitetura segura para o release é: o pagador usa sua instituição/PSP, o beneficiário recebe em sua própria conta e a plataforma guarda apenas identificadores, status e evidência necessários. Uma futura integração via API deve dizer se o parceiro é provedor de conta, iniciador, PSP ou outro participante, quem autoriza a transação, quem liquida, quem responde por fraude/chargeback e quem emite os documentos. Gerar um QR ou código “Pix” sem conta, provedor e transação correspondente criaria aparência de operação inexistente; por isso, o release corretamente removeu o gerador sem provedor [13] [14] [26] [27].

**Regra de fronteira:** cobrar a assinatura da própria plataforma pelo checkout de um PSP, ou instruir que o contratante pague diretamente um terceiro fora da plataforma, não transforma automaticamente o SaaS em IP. Já executar/facilitar instrução de pagamento de terceiros, gerir conta, emitir instrumento, credenciar recebedores, iniciar transação ou participar da liquidação aciona análise BCB. O contrato com o PSP não elimina a necessidade de mapear o papel real.

### 5. CVM e valores mobiliários

A Lei nº 6.385/1976 dá à CVM competência sobre o mercado de valores mobiliários e disciplina emissão, distribuição pública, negociação e intermediários [17]. A plataforma deve separar financiamento não financeiro, doação, patrocínio, contrato de prestação e compra de serviço de qualquer oferta que prometa participação, dívida, conversão, retorno ou remuneração derivada de empreendimento.

A CVM define crowdfunding de investimento como captação de recursos por oferta pública de distribuição de valores mobiliários dispensada de registro, de sociedade empresária de pequeno porte, distribuída exclusivamente por plataforma eletrônica de investimento participativo [18]. A Resolução CVM 88 exige, entre outras condições, sociedade de pequeno porte, prazo e limites de captação, período mínimo de desistência e escrituração ou controle de titularidade; a plataforma deve verificar condições da oferta e atuar com diligência [18]. A CVM continua emitindo orientações operacionais para plataformas, inclusive sobre cadastro, demonstrações financeiras, capital mínimo, identificação de administradores, material didático, auditoria de TI e relatório anual [19].

O produto atual não deve usar “investidor”, “rentabilidade”, “retorno”, “equity”, “debênture”, “participação societária” ou “valor mobiliário” em fluxos de financiamento de impacto sem uma decisão regulatória específica. Se a intenção futura for uma oferta de investimento participativo, o caminho não é acrescentar um campo à ficha do projeto: é um produto regulado, com plataforma registrada, regras de oferta, informações, controles, contratos e compliance próprios.

### 6. PLD/FTP e Lei nº 9.613/1998

A Lei nº 9.613/1998 sujeita a obrigações de identificação, registros e comunicações as pessoas que, entre outras atividades, captem, intermedeiem ou apliquem recursos financeiros de terceiros; operem custódia, emissão, distribuição, liquidação ou intermediação de valores mobiliários; administrem cartões ou meios eletrônicos de transferência de fundos; ou exerçam atividades sujeitas a órgão regulador [20]. O fato de uma plataforma possuir um módulo de projetos ou registrar um pagamento declarado não basta, sozinho, para enquadrá-la como sujeito obrigado; o gatilho depende da atividade efetiva prevista no art. 9º e das normas setoriais.

O Banco Central afirma que regulamenta a Lei nº 9.613/1998 para que entidades supervisionadas implementem políticas, procedimentos, controles e comunicações ao Coaf [21]. A Circular BCB nº 3.978/2020 trata de política, procedimentos e controles internos de PLD/FTP para instituições autorizadas a funcionar pelo BC [22]. Ela não deve ser apresentada como obrigação direta do SaaS comum apenas porque o SaaS cobra sua fatura. Ela se torna diretamente relevante se a plataforma for IP, instituição autorizada ou exercer atividade que a coloque em outro grupo de sujeitos obrigados.

Mesmo fora do enquadramento automático, o produto deve ter um **gatilho de triagem**: captação ou intermediação de recursos de terceiros, carteira ou saldo, liquidação/repasse, cartão, iniciação de pagamento, oferta de valor mobiliário, ativos virtuais, alto volume de espécie ou parceria que atribua ao Impacto papel operacional. Ao disparar, a operação deve ficar em revisão, sem promessa de PLD/FTP, até definição do sujeito obrigado, responsável, KYC/KYB, monitoramento, retenção e comunicação.

## Relação entre os quatro motores

```text
CONTRATO APROVADO + PREÇO/TAXA VERSIONADOS
                    │
                    ▼
        FISCAL_RULE_ENGINE
  município · serviço · regime · retenção
                    │
                    ▼
          FINANCIAL_ENGINE
   calcula · instrui · concilia (não move)
          │                    │
          ▼                    ▼
 PAYMENT_ARCHITECTURE     NFS-e/obrigações
 adapter PSP externo      fiscais por adapter
          │
          ▼
 NON_CUSTODIAL_ARCHITECTURE
 dinheiro de terceiro direto entre as partes;
 nenhum saldo, wallet, split, payout ou escrow no núcleo
```

### FINANCIAL_ENGINE

O motor financeiro deve continuar limitado a três verbos: **calcular** a obrigação com base no contrato e na regra vigente; **instruir** quem paga sobre valor, destino, referência e vencimento; e **conciliar** a evidência externa com o esperado. A própria contabilidade da plataforma — receita de assinatura, taxa faturada, despesa e competência — é distinta do dinheiro de terceiros. GMV ou valor financiado não entra na receita da plataforma apenas porque está registrado no contrato [25] [27].

A taxa `contract.platform_service_fee` só pode abrir cobrança própria quando houver: contrato aprovado e vigente; cláusula de taxa identificando pagador e base; regra comercial ativa; classificação fiscal aprovada; emissor e município configurados; autorização de cobrança válida; e trilha de versão/hash. A matriz de distribuição é prova do acordo econômico, não prova de liquidação. Se o projeto recebeu ou não recebeu dinheiro fora da plataforma, o sistema registra evidência ou desconhecimento; não inventa baixa.

### FISCAL_RULE_ENGINE

O motor fiscal deve usar regras efetivas por data, fonte, órgão, município, código de serviço, alíquota, regime e nível de confiança. A resposta deve distinguir:

- **estimativa:** valor aproximado, sem afirmar obrigação final;
- **regra identificada:** fonte publicada aplicável, ainda sem conclusão sobre os fatos;
- **pendência de dados:** município, CNPJ, regime, serviço ou documento ausente;
- **validação profissional:** contador/advogado responsável e data;
- **documento emitido:** somente após autorização do emissor e protocolo verificável.

A regra fiscal não deve usar o nome “taxa”, “comissão” ou “take rate” como classificação automática. Ela deve identificar se a taxa é remuneração do SaaS, intermediação, serviço de pagamento, comissão, licença, serviço técnico ou outra prestação e encaminhar classificações ambíguas para revisão.

### PAYMENT_ARCHITECTURE

O adapter de pagamento deve ser opcional. Sem PSP configurado, o estado é `configured: false`, os métodos reais disponíveis são vazios e a receita é simulada ou inexistente. Com PSP, o sistema deve armazenar apenas token/referência do provedor, últimos quatro dígitos quando necessários, identificador do evento, valor, moeda, status, timestamps, assinatura verificada e motivo de rejeição; nunca PAN, CVV, senha, credencial bancária ou chave privada.

A confirmação de pagamento deve vir de webhook assinado do provedor, com idempotência, rejeição de assinatura inválida e reconciliação. O usuário não deve conseguir marcar a cobrança como paga pela interface. O contrato do PSP deve mapear papéis BCB, emissão de NFS-e, chargeback, fraude, dados, subcontratação, incidentes e encerramento.

### NON_CUSTODIAL_ARCHITECTURE

A regra vinculante é: o dinheiro de terceiro vai do pagador ao beneficiário por fora da plataforma; a plataforma pode saber o que deveria acontecer, guardar evidência proporcional e apontar divergência, mas não guardar o dinheiro. Não usar `escrow` como metáfora de uma simples pendência; não criar `recipient`, `wallet`, `balance`, `payout` ou `split` apenas para facilitar uma tela.

Se um PSP oferecer split, o adapter pode existir apenas após decisão específica, mas o split não deve virar dependência do núcleo. A decisão precisa responder: quem é o credenciador/subcredenciador, quem é o recebedor perante o arranjo, quem liquida, quem arca com chargeback, quem emite nota, quem faz KYC/KYB, onde ficam recursos e se a plataforma recebe qualquer valor de terceiro. Sem isso, o fluxo permanece externo e não custodial.

## Mapa de obrigações para o produto

| Cenário | Regra/órgão principal | Dados e documento | Estado correto no release | Gatilho de escalonamento |
|---|---|---|---|---|
| Assinatura SaaS paga à plataforma | CC; CDC se relação de consumo; LC 116 | contrato, preço, aceite, NFS-e conforme classificação, pagamento próprio | Permitido como cobrança própria, mas não configurado em produção | B2C, cláusula abusiva, preço sem informação ou mudança sem aviso |
| Taxa de serviço da plataforma ao financiador | CC/CDC conforme relação; LC 116; regra municipal | cláusula, base, pagador, matriz hash, NFS-e da plataforma, competência e retenções | `contract.platform_service_fee` nasce desligada; cobrança só após gates | taxa como percentual do fluxo sem contrato; taxa que pareça comissão financeira |
| Valor do financiamento entre financiador e projeto | contrato entre partes; nenhuma custódia pelo SaaS | valor declarado, instrução externa, evidência e status de desconhecido | Não é receita/caixa da plataforma | plataforma recebe, repassa, segura ou promete liquidação |
| Pagamento da assinatura por PSP | Lei 12.865/BCB conforme papel do PSP | provider, contrato, token, webhook, chargeback | Adapter opcional; sem PSP, nenhum pagamento real | plataforma opera como IP, credenciador ou iniciador |
| Pix | Regulamento Pix e instituição participante | PSP/participante, txid, conta/beneficiário externo, status, webhook | Não gerar Pix sem provedor/conta | iniciação própria, conta de pagamento, liquidação ou participação |
| Cartão, boleto ou parcelamento | arranjo e contrato PSP; possível crédito conforme desenho | instrumento externo, vencimentos, autorização e evidência | Apenas cobrança própria, sem custódia | antecipação, crédito, recebível, split ou cobrança em nome de terceiro |
| Serviço tomado com retenção | Receita/EFD-Reinf/DCTFWeb; legislação aplicável | NF, prestador, estabelecimento, competência, base, retenção, evento e recibo | Exportação para contador; não declarar automaticamente sem regra | cessão de mão de obra, empreitada ou retenção não classificada |
| Oferta de participação/retorno | Lei 6.385 e CVM 88 | oferta, emissor, investidor, riscos, contrato e controles específicos | Bloqueado no produto atual | promessa de retorno, dívida, equity, conversão ou captação pública |
| Captação/intermediação/transferência de terceiros | Lei 9.613; BCB/Coaf conforme sujeito | KYC/KYB, risco, transações, alertas e comunicações quando aplicável | Triagem; não afirmar compliance | plataforma passa a ser sujeito obrigado ou IP |
| NFS-e padrão nacional | Portal NFS-e; município; LC 116/175 | CNPJ/CPF, tomador, serviço, valor, município, credencial, XML, protocolo | Não configurada | município não conveniado, código ambíguo, falha de credenciamento |
| IBS/CBS e documento fiscal eletrônico | LC 214 e atos de transição | leiaute, vínculo documento-pagamento, destaque e status de produção | Monitoramento/roadmap | ato de produção exigir novo leiaute ou split payment |

## Requisitos de produto

### Contratos e cobrança

1. Separar no modelo os papéis **plataforma**, **contratante/pagador**, **projeto/beneficiário**, **prestador** e **PSP**. Não permitir que “recebedor” seja interpretado como saldo ou conta da plataforma.
2. Congelar versão de contrato, preço e taxa com hash do texto, data de vigência, autor, aprovadores, CNPJ/CPF, representação e escopo. Um novo preço ou cláusula cria versão nova.
3. Registrar separadamente acesso gratuito e autorização de cobrança. Fim de trial não é autorização de débito.
4. Exigir quatro olhos para ativar taxa de plataforma, alterar matriz de distribuição ou trocar o pagador; a pessoa que cria não aprova.
5. Bloquear cobrança quando a minuta jurídica está `draft`, a regra fiscal está sem fonte/validade, a NFS-e não está configurada ou o meio de pagamento real não está ligado.
6. Mostrar no checkout preço, periodicidade, tributos quando aplicável, cancelamento, renovação, taxa, titular da cobrança e o que **não** está incluído. Não misturar preço do SaaS com valor de terceiros.
7. Emitir a cobrança da taxa própria contra o pagador definido no contrato. Não retirar taxa do valor destinado ao projeto nem chamar o desconto de “repasse” ou “split”.
8. Para contratos com o poder público, parametrizar exigências do ente, assinatura e formalização próprias; não presumir que a assinatura eletrônica simples do SaaS basta.

### Fiscal

1. Criar cadastro versionado de estabelecimento, município, inscrição municipal, regime, código/subitem, alíquota, retenção, emissor NFS-e, credencial, ambiente e responsável profissional.
2. Ter `fiscal_preflight` antes de ativar produto ou taxa: serviço efetivo, tomador, local de incidência, documento, regime, retenções, competência e base legal.
3. Separar NFS-e emitida, NFS-e recebida, RPS/evento, cancelamento, substituição, autorização, rejeição e protocolo. Um PDF de cobrança não é prova de NFS-e autorizada.
4. Adaptar-se ao município/conveniado e à API nacional somente após credenciamento; guardar leiaute e versão do parâmetro municipal.
5. Exportar dados para o contador para EFD-Reinf/DCTFWeb, sem prometer transmissão ou apuração se o adapter não existir.
6. Criar monitor de mudança de LC 116, LC 175, LC 214, normas municipais e leiautes; nenhuma alteração deve sobrescrever regra histórica.

### Pagamentos

1. Definir por escrito o papel da plataforma e do parceiro: merchant da própria assinatura, facilitador técnico, iniciador, credenciador, subcredenciador ou nenhum desses.
2. Exigir contrato com PSP/IP autorizado quando a integração usar serviços de pagamento, identificando conta, liquidação, chargeback, fraude, atendimento, dados e responsabilidade.
3. Guardar somente identificadores e tokens do provedor; manter PCI/segurança do parceiro como dependência contratual, sem armazenar dados de cartão.
4. Implementar webhook assinado, idempotência, replay protection, estado derivado e reconciliação; nunca aceitar “pago” digitado pela interface.
5. Para Pix, armazenar `txid`, PSP, participante, valor, recebedor externo, status, horário e evidência; não guardar credenciais, nem produzir código de cobrança fora do PSP.
6. Bloquear parcelamento que, na prática, seja crédito concedido pela plataforma. Se houver juros, antecipação, recebíveis, crédito ou financiamento, abrir análise própria.

### BCB, CVM e PLD/FTP

1. Implementar questionário de gatilhos antes de publicar qualquer fluxo financeiro: há captação, intermediação, conta, custódia, liquidação, cartão, iniciação, recebedores múltiplos, promessa de retorno, valor mobiliário, moeda eletrônica ou ativo virtual?
2. Se qualquer resposta for positiva ou desconhecida, o produto fica em `regulatory_review`; não pode lançar a feature com texto comercial genérico.
3. Proibir no catálogo de financiamento linguagem de investimento ou retorno, salvo produto CVM separado e validado.
4. Guardar decisão, fonte, data, responsável e escopo da análise; um rótulo “não custodial” sem descrição de fluxo não é controle.
5. Se a plataforma se tornar sujeito obrigado, ativar política, responsável, identificação, avaliação de risco, registros, monitoramento, sanções e comunicações adequadas ao órgão competente. Até lá, não prometer “KYC/PLD completo” nem “regulado pelo BC”.

## Requisitos de dados

| Entidade | Campos mínimos | Controle |
|---|---|---|
| `legal_document`/contrato | chave, versão, texto/hash, status, aprovação, vigência, partes, representação | imutabilidade; aceite somente de versão aprovada e vigente |
| `commercial_offer` | plano, preço, periodicidade, taxa, pagador, autorização, versão e vigência | acesso gratuito separado de autorização de cobrança |
| `agreement_allocation` | contrato, base, valor/percentual, modo, partes, versão, hash e data | append-only; não é saldo nem liquidação |
| `fiscal_rule` | órgão, fonte/URL, título, data, vigência inicial/final, município, serviço, regime, alíquota, confiança, aprovadores | regra efetiva por competência; histórico preservado |
| `tax_document` | emitente/tomador, CNPJ/CPF, município, subitem, valor, tributos, XML/PDF, protocolo, status, cancelamento | hash do arquivo e validação de autoridade/emissor |
| `withholding_event` | prestador, estabelecimento, nota, competência, fato gerador, base, tributo, retenção, evento EFD-Reinf, recibo DCTFWeb | somente com fundamento e revisão profissional |
| `payment_provider` | PSP/IP, CNPJ, papel regulatório declarado, contrato, ambiente, conta do recebedor, credencial, vigência | impedir configuração de parceiro sem due diligence |
| `payment_event` | provider, event_id, charge_id, assinatura verificada, origem, payload mínimo, status, timestamps | append-only, idempotência e retenção mínima |
| `external_payment_evidence` | contrato, pagador, beneficiário, valor, data, referência externa, documento, fonte e confiança | evidência declarada não equivale a pagamento verificado |
| `regulatory_review` | gatilho, fluxo, órgão possível, fonte, hipótese, decisão, responsável, data e expiração | bloqueio de release quando decisão está pendente |
| `aml_cvm_case` | motivo, entidade, operação, risco, documentos, decisão e encaminhamento | acesso restrito; só ativar quando gatilho real existir |

Dados pessoais devem seguir minimização, finalidade, acesso por tenant, criptografia e retenção definida. A base de LGPD existente já evita listas nominais de beneficiários e mantém arquivos privados, RLS e trilhas de auditoria; a inclusão de dados fiscais e de pagamento não autoriza coletar conta bancária, documento pessoal ou KYC completo sem finalidade e base legal registradas [25]. IP, agente, documentos fiscais, webhooks e evidências precisam de política de retenção baseada em obrigação legal, contrato e segurança, com eliminação ou anonimização quando possível.

## Testes e controles obrigatórios

1. **Teste de estado de release:** sem provedor e sem credencial real, `configured=false`, métodos reais vazios, nenhum valor classificado como receita real e nenhum NFS-e como emitido.
2. **Teste de minuta:** aceite de documento `draft`, sem aprovação, sem revisão ou fora da vigência deve ser recusado no banco.
3. **Teste de taxa:** ativação deve falhar sem contrato vigente, pagador, cláusula, fonte fiscal, regra ativa, NFS-e configurada e autorização de cobrança. A cobrança nunca deve ser criada a partir de GMV ou valor de terceiro sem a base contratual correspondente.
4. **Teste de não custódia:** varredura do esquema e do código reprova reaparecimento de wallet, saldo de terceiro, escrow, payout, split ou recipient sem ADR e revisão regulatória; nenhum job deve ter permissão de débito/crédito em conta de terceiros.
5. **Teste de contabilidade:** GMV/valor financiado não entra em receita; lote desequilibrado, competência fechada, conta sintética ou conta inativa são recusados; receita própria e dinheiro externo têm caminhos distintos.
6. **Teste fiscal:** regra sem fonte, vigência ou aprovador não calcula; regra municipal expirada não é usada; mudança de código gera versão; NFS-e depende de protocolo; município do tomador não é usado como regra geral sem base.
7. **Teste EFD-Reinf:** evento só é proposto quando serviço, retenção e competência satisfazem a regra; eventos de serviços sem retenção não são incluídos automaticamente apenas por terem NFS-e; retificação preserva o evento anterior.
8. **Teste de pagamento:** webhook não assinado ou duplicado não produz efeito; `paid_at` e `settled_at` são derivados; confirmação manual não baixa cobrança; evento de PSP fora do contrato é rejeitado.
9. **Teste Pix/BCB:** qualquer modo `initiator`, `credenciador`, `subcredenciador`, conta de pagamento, split ou liquidação em nome de terceiro exige `regulatory_review=true` e parceiro identificado.
10. **Teste CVM:** palavras ou campos de retorno, juros, participação, conversão, valor mobiliário, investidor e oferta pública bloqueiam o fluxo não regulado e exigem revisão.
11. **Teste PLD/FTP:** captação/intermediação/custódia/conta/meio eletrônico de transferência não deve liberar feature sem classificar sujeito obrigado e responsável por controles.
12. **Teste de desligamento:** desligar PSP, NFS-e ou adapter não apaga histórico, não muda contratos e não transforma evidência externa em pagamento confirmado.
13. **Controle de comunicação:** toda tela e API expõe se o estado é real, simulado, declarado, pendente ou validado; “desconhecido” nunca vira zero ou sucesso.
14. **Controle periódico:** revisão mensal de fontes, normativos, municipalidade, leiautes e contratos de PSP; revisão de lançamento sempre conserva fonte e data de consulta.

## Claims proibidos ou condicionados

Enquanto as lacunas abaixo não forem fechadas, o produto, site, proposta e API não devem afirmar:

- “instituição de pagamento”, “credenciadora”, “subcredenciadora”, “iniciador de Pix”, “arranjo Pix” ou “regulado pelo Banco Central” sem o papel, autorização/parceiro e escopo reais;
- “custódia”, “escrow”, “carteira”, “saldo disponível”, “repasse automático”, “split”, “payout” ou “liquidação garantida” para dinheiro de terceiros;
- “Pix processado”, “cartão aprovado”, “boleto pago”, “chargeback protegido” ou “cobrança real” sem PSP configurado, evento verificável e reconciliação;
- “nota fiscal emitida”, “ISS calculado corretamente”, “tributação regular”, “benefício fiscal”, “isenção”, “imunidade” ou “obrigação acessória entregue” sem NFS-e/protocolo/regra e validação correspondente;
- “conforme a LC 116”, “pronto para IBS/CBS” ou “split payment compatível” como afirmação geral sem município, leiaute, ato de produção e teste;
- “investimento”, “investidor”, “rentabilidade”, “retorno”, “equity”, “debênture”, “valor mobiliário”, “oferta pública” ou “crowdfunding de investimento” no fluxo atual de financiamento;
- “PLD/FT compliant”, “KYC aprovado”, “sem risco de lavagem”, “antifraude garantida” ou “CVM compliant” sem sujeito obrigado, escopo, controles e revisão;
- “receita de marketplace”, “take rate recebido” ou “GMV realizado” quando há apenas valor contratual/declarado;
- “contrato válido”, “termos aceitos” ou “assinatura qualificada” enquanto as minutas estão em `draft` ou quando o nível de assinatura exigido não foi atendido.

A linguagem permitida deve ser factual: **“taxa própria da plataforma prevista em contrato, com cobrança condicionada à configuração fiscal e comercial”**, **“pagamento externo declarado pelo usuário”**, **“NFS-e não configurada”**, **“regra identificada; validação profissional pendente”** e **“fluxo não custodial: a plataforma não recebe nem movimenta o valor de terceiros”**.

## Lacunas e plano de fechamento

### Bloqueadores vermelhos

- Aprovação jurídica e publicação das onze minutas, incluindo contrato de assinatura, pagamento, marketplace, intermediação, cancelamento e reembolso [28].
- Definição pelo contador do serviço efetivo, subitem, município, regime, emissão e retenções para assinatura e taxa de plataforma.
- Contratação e homologação de PSP, com papel BCB, conta de recebimento, webhook, chargeback, dados e encerramento; até lá não existe cobrança real.
- Decisão documentada de que o valor financiado nunca passará pela plataforma; remover qualquer copy ou UX que sugira custódia, repasse ou garantia.
- Gatilho CVM/PLD com revisão antes de usar linguagem de investimento ou criar qualquer fluxo de captação/intermediação.

### Lacunas amarelas

- Adapter NFS-e com credenciamento, parâmetros municipais, XML, cancelamento, contingência e protocolo.
- Matriz de EFD-Reinf/DCTFWeb por tipo de serviço, fato gerador, retenção, estabelecimento e competência.
- Monitor da reforma tributária e de mudanças em leiautes/documentos fiscais, incluindo eventual vinculação de pagamento prevista na LC 214.
- Política de retenção e base legal para documentos fiscais, webhooks, evidências externas, IP e dados de prestadores.
- Contratos B2B/B2G que definam CDC quando aplicável, assinatura exigida, aceite, reajuste, responsabilidade e auditoria.
- Testes de saída: exportar a trilha para contador, auditor e PSP sem expor credenciais ou dados excessivos.

### Hipóteses que não devem ser tratadas como norma

- A regra `platform_service_fee` e a matriz de distribuição são **hipótese de monetização/arquitetura** até aprovação contratual e fiscal.
- O uso de API NFS-e é **capacidade técnica**, não autorização municipal nem prova de emissão.
- O adapter PSP é **integração comercial**, não autorização para a plataforma atuar como IP.
- A varredura de ausência de wallet/split/payout é **controle interno**, não certificação externa de não sujeição regulatória.
- Os rótulos de `FISCAL_RULE_ENGINE` são **governança de incerteza**, não decisão final do Fisco.

## Conclusão operacional

O release pode cobrar **o próprio SaaS e serviço próprio** sem construir uma fintech: contrato aprovado, preço versionado, NFS-e configurada, PSP externo e contabilidade da própria plataforma são suficientes para o caminho básico. A taxa sobre o acordo de financiamento deve continuar sendo uma fatura própria da plataforma ao pagador, baseada no contrato, e nunca um desconto de dinheiro que transitou pela plataforma.

A fronteira não custodial é útil, mas deve ser testada pelo fluxo real. Se o Impacto apenas registra, instrui e concilia pagamentos executados por terceiros, não há motivo para chamá-lo de IP, subcredenciador, iniciador, arranjo Pix ou plataforma de investimento. Se passar a iniciar, habilitar, liquidar, custodiar, captar ou prometer retorno, a arquitetura e a análise regulatória mudam de categoria. O produto deve bloquear essa mudança, em vez de escondê-la em termos de marketing.

## Referências

[1]: https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp116.htm "Lei Complementar nº 116, de 31 de julho de 2003 — Presidência da República/Planalto" — **Data:** 31/07/2003, texto compilado consultado em 08/10/2026. **Sustenta:** fato gerador do ISS, regra de local do serviço, não prevalência do nome dado ao serviço e subitens 1.03, 1.04 e 1.05 da lista.

[2]: https://www.planalto.gov.br/ccivil_03/leis/lcp/Lcp175.htm "Lei Complementar nº 175, de 23 de setembro de 2020 — Presidência da República/Planalto" — **Data:** 23/09/2020. **Sustenta:** obrigação acessória nacional do ISS para os subitens específicos, declaração eletrônica, prazo, dados municipais e limites de aplicação.

[3]: https://www.gov.br/nfse/pt-br/municipios/produtos-disponiveis/api-de-integracao "API de integração — Portal da Nota Fiscal de Serviço eletrônica" — **Órgão:** Secretaria Especial da Receita Federal/Portal NFS-e. **Data:** publicado 22/07/2022, atualizado 31/10/2023. **Sustenta:** APIs, Ambiente de Dados Nacional, parâmetros municipais e integração de software próprio.

[4]: https://www.gov.br/pt-br/servicos/emitir-nota-fiscal-de-servico-eletronica "Emitir Nota Fiscal de Serviço Eletrônica (NFS-e) — Padrão Nacional" — **Órgão:** Receita Federal/Portal Gov.br. **Data:** última modificação 23/02/2026. **Sustenta:** validade jurídica da NFS-e padrão nacional, municípios conveniados, dados de emissão e credenciamento prévio para API.

[5]: https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/perguntas-frequentes/sped/efd-reinf/efdr "EFD-Reinf — Perguntas frequentes" — **Órgão:** Receita Federal. **Data:** página consultada em 08/10/2026, com atualizações de 2026. **Sustenta:** competências, fatos geradores e hipóteses de informação/retensão na EFD-Reinf.

[6]: https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/perguntas-frequentes/sped/efd-reinf/efdr/2-eventos-da-efd-reinf/2-3-9-quanto-as-notas "2.3.9 — Notas fiscais de serviços tomados na EFD-Reinf" — **Órgão:** Receita Federal. **Data:** publicado 02/04/2026, atualizado 13/04/2026. **Sustenta:** informação por competência, estabelecimento e prestador dos documentos com retenção previdenciária aplicável.

[7]: https://www.gov.br/receitafederal/pt-br/centrais-de-conteudo/publicacoes/manuais/manual-dctfweb/manual-dctfweb-atualizacao-janeiro2025_versao_final.pdf "Manual da DCTFWeb — janeiro de 2025" — **Órgão:** Receita Federal. **Data:** janeiro/2025. **Sustenta:** fluxo EFD-Reinf–DCTFWeb, débitos de retenções sobre serviços tomados e créditos de retenções sofridas.

[8]: https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp214.htm "Lei Complementar nº 214, de 16 de janeiro de 2025 — Presidência da República/Planalto" — **Data:** 16/01/2025, texto vigente consultado em 08/10/2026. **Sustenta:** documento fiscal eletrônico para IBS/CBS, vínculo com pagamento, split payment e necessidade de acompanhar produção de efeitos/leiautes.

[9]: https://www.planalto.gov.br/ccivil_03/leis/2002/l10406compilada.htm "Código Civil — Lei nº 10.406, de 10 de janeiro de 2002" — **Órgão:** Presidência da República/Planalto. **Data:** 10/01/2002. **Sustenta:** regime geral de contratos e prestação de serviços.

[10]: https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm "Código de Defesa do Consumidor — Lei nº 8.078, de 11 de setembro de 1990" — **Órgão:** Presidência da República/Planalto. **Data:** 11/09/1990, texto compilado consultado em 08/10/2026. **Sustenta:** informação clara, oferta vinculante, proteção contra publicidade enganosa e limites de cobrança, quando a relação for de consumo.

[11]: https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2020/lei/l14063.htm "Lei nº 14.063, de 23 de setembro de 2020 — Assinaturas eletrônicas" — **Órgão:** Presidência da República/Planalto. **Data:** 23/09/2020. **Sustenta:** classificação de assinaturas, escopo público e hipóteses de assinatura qualificada, inclusive emissão de NF-e com exceções legais.

[12]: https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2013/lei/l12865.htm "Lei nº 12.865, de 9 de outubro de 2013 — Arranjos e instituições de pagamento" — **Órgão:** Presidência da República/Planalto. **Data:** 09/10/2013, texto compilado consultado em 08/10/2026. **Sustenta:** definições de arranjo, IP, conta, instrumento, serviços e competência do BCB.

[13]: https://www.bcb.gov.br/estabilidadefinanceira/instituicaopagamento "Instituições de pagamento" — **Órgão:** Banco Central do Brasil. **Data:** página institucional consultada em 08/10/2026. **Sustenta:** modalidades, serviços, supervisão, vedação de empréstimos/financiamentos e distinção entre IP e instituição financeira.

[14]: https://www.bcb.gov.br/estabilidadefinanceira/exibenormativo?tipo=Resolu%C3%A7%C3%A3o%20BCB&numero=80 "Resolução BCB nº 80, de 25 de março de 2021" — **Órgão:** Banco Central do Brasil. **Data:** 25/03/2021; versão vigente atualizada em 06/11/2025. **Sustenta:** modalidades de IP, iniciador sem gerir conta/deter fundos e controles/vedações da iniciação.

[15]: https://www.bcb.gov.br/meubc/faqs/s/operacao-com-recebiveis "FAQ — Operação com recebíveis" — **Órgão:** Banco Central do Brasil. **Data:** atualizado 31/01/2023. **Sustenta:** definição de credenciador, recebível e subcredenciador no arranjo de pagamento.

[16]: https://www.bcb.gov.br/estabilidadefinanceira/arranjospagamento "Arranjos de Pagamento" — **Órgão:** Banco Central do Brasil. **Data:** página institucional consultada em 08/10/2026. **Sustenta:** conceito de arranjo, exemplos, papel de IPs e existência de arranjos não sujeitos ao BC em hipóteses específicas.

[17]: https://www.planalto.gov.br/ccivil_03/leis/l6385compilada.htm "Lei nº 6.385, de 7 de dezembro de 1976 — Mercado de valores mobiliários" — **Órgão:** Presidência da República/Planalto. **Data:** 07/12/1976, texto compilado consultado em 08/10/2026. **Sustenta:** competência da CVM, emissão/distribuição pública e intermediação de valores mobiliários.

[18]: https://conteudo.cvm.gov.br/export/sites/cvm/legislacao/resolucoes/anexos/001/resol088consolid.pdf "Resolução CVM nº 88, de 27 de abril de 2022 — texto consolidado" — **Órgão:** Comissão de Valores Mobiliários. **Data:** 27/04/2022. **Sustenta:** crowdfunding de investimento, limites/condições de oferta, plataforma, diligência e controles de titularidade.

[19]: https://www.gov.br/cvm/pt-br/assuntos/noticias/2025/area-tecnica-da-cvm-orienta-sobre-cumprimento-de-dispositivos-da-resolucao-cvm-88-referentes-a-plataformas-de-crowdfunding "Ofício Circular CVM/SSE 4/2025 — orientação sobre Resolução CVM 88" — **Órgão:** CVM, Superintendência de Securitização e Agronegócio. **Data:** 03/07/2025. **Sustenta:** cadastro, documentos, capital mínimo, auditoria de TI e relatórios de plataformas de crowdfunding.

[20]: https://www.planalto.gov.br/ccivil_03/leis/l9613.htm "Lei nº 9.613, de 3 de março de 1998 — Prevenção à lavagem de dinheiro" — **Órgão:** Presidência da República/Planalto. **Data:** 03/03/1998, texto compilado consultado em 08/10/2026. **Sustenta:** sujeitos obrigados, identificação, registros e comunicações nos arts. 9º a 11.

[21]: https://www.bcb.gov.br/estabilidadefinanceira/lavagemdinheiro "Prevenção à lavagem de dinheiro e ao financiamento do terrorismo" — **Órgão:** Banco Central do Brasil. **Data:** página institucional consultada em 08/10/2026. **Sustenta:** papel regulatório/supervisório do BCB e deveres das entidades supervisionadas.

[22]: https://www.bcb.gov.br/estabilidadefinanceira/exibenormativo?tipo=Circular&numero=3978 "Circular BCB nº 3.978, de 23 de janeiro de 2020" — **Órgão:** Banco Central do Brasil. **Data:** 23/01/2020, texto vigente e alterações indicadas na página consultada em 08/10/2026. **Sustenta:** política, procedimentos e controles internos de PLD/FTP das instituições autorizadas pelo BCB.

[23]: https://www.gov.br/nfse/pt-br "Portal da Nota Fiscal de Serviço eletrônica — referência institucional" — **Órgão:** Receita Federal/Portal NFS-e. **Data:** consulta em 08/10/2026. **Sustenta:** contexto institucional do padrão nacional de NFS-e e materiais técnicos citados no relatório.

[24]: file:///home/ubuntu/impacto-trust-knowledge-v0.26.0/FISCAL_RULE_ENGINE.md "FISCAL_RULE_ENGINE.md — release v0.10.0/v0.10.1" — **Fonte interna:** repositório Impacto. **Data:** versão do documento no release. **Sustenta:** regras fiscais dirigidas por dados, níveis de certeza e exigência de validação profissional.

[25]: file:///home/ubuntu/impacto-trust-knowledge-v0.26.0/FINANCIAL_ENGINE.md "FINANCIAL_ENGINE.md — release v0.22.0" — **Fonte interna:** repositório Impacto. **Data:** versão do documento no release. **Sustenta:** cálculo/instrução/conciliação, separação de GMV e receita, ausência de provedor fiscal e ausência de custódia.

[26]: file:///home/ubuntu/impacto-trust-knowledge-v0.26.0/PAYMENT_ARCHITECTURE.md "PAYMENT_ARCHITECTURE.md — release v0.17.0" — **Fonte interna:** repositório Impacto. **Data:** versão do documento no release. **Sustenta:** estado sem provedor, máquina de cobrança, webhooks e limites do pagamento próprio.

[27]: file:///home/ubuntu/impacto-trust-knowledge-v0.26.0/NON_CUSTODIAL_ARCHITECTURE.md "NON_CUSTODIAL_ARCHITECTURE.md — ADR-284, v0.22.0" — **Fonte interna:** repositório Impacto. **Data:** versão do documento no release. **Sustenta:** regra vinculante de não custódia, ausência de wallet/split/payout/escrow e taxa própria condicionada a contrato.

[28]: file:///home/ubuntu/impacto-trust-knowledge-v0.26.0/docs/LEGAL_FRAMEWORK.md "LEGAL_FRAMEWORK.md — onze minutas em draft" — **Fonte interna:** repositório Impacto. **Data:** documento da v0.17.0 presente no release. **Sustenta:** estado de minuta, bloqueio de aceite e pendências de advogado, contador e dados cadastrais.

[29]: file:///home/ubuntu/impacto-trust-knowledge-v0.26.0/README.md "README.md — Plataforma Impacto v0.26.0" — **Fonte interna:** repositório Impacto. **Data:** release v0.26.0. **Sustenta:** ausência de publicação, provedores e cobrança real, e implementação da regra de taxa contratual própria.
O README do v0.26.0 informa corretamente que a versão está em **base técnica fechada**, não publicada, sem provedor de pagamento, fiscal ou de cobrança ligado; Android/iOS não foram construídos e nenhuma cobrança real é possível no estado atual [29]. O mesmo README registra que o contrato passou a ser regra de operação: a taxa e quem paga são definidos no acordo, a matriz de distribuição é imutável e a cobrança da taxa é própria da plataforma, sem descontar dinheiro em trânsito [29].
O Pix é um arranjo do Banco Central com regras próprias. A arquitetura segura para o release é: o pagador usa sua instituição/PSP, o beneficiário recebe em sua própria conta e a plataforma guarda apenas identificadores, status e evidência necessários. Uma futura integração via API deve dizer se o parceiro é provedor de conta, iniciador, PSP ou outro participante, quem autoriza a transação, quem liquida, quem responde por fraude/chargeback e quem emite os documentos. Gerar um QR ou código “Pix” sem conta, provedor e transação correspondente criaria aparência de operação inexistente; por isso, o release corretamente removeu o gerador sem provedor [13] [14] [26] [27].
O motor financeiro deve continuar limitado a três verbos: **calcular** a obrigação com base no contrato e na regra vigente; **instruir** quem paga sobre valor, destino, referência e vencimento; e **conciliar** a evidência externa com o esperado. A própria contabilidade da plataforma — receita de assinatura, taxa faturada, despesa e competência — é distinta do dinheiro de terceiros. GMV ou valor financiado não entra na receita da plataforma apenas porque está registrado no contrato [25] [27].
O Pix é um arranjo do Banco Central com regras próprias. A arquitetura segura para o release é: o pagador usa sua instituição/PSP, o beneficiário recebe em sua própria conta e a plataforma guarda apenas identificadores, status e evidência necessários. Uma futura integração via API deve dizer se o parceiro é provedor de conta, iniciador, PSP ou outro participante, quem autoriza a transação, quem liquida, quem responde por fraude/chargeback e quem emite os documentos. Gerar um QR ou código “Pix” sem conta, provedor e transação correspondente criaria aparência de operação inexistente; por isso, o release corretamente removeu o gerador sem provedor [13] [14] [26] [27].
O motor financeiro deve continuar limitado a três verbos: **calcular** a obrigação com base no contrato e na regra vigente; **instruir** quem paga sobre valor, destino, referência e vencimento; e **conciliar** a evidência externa com o esperado. A própria contabilidade da plataforma — receita de assinatura, taxa faturada, despesa e competência — é distinta do dinheiro de terceiros. GMV ou valor financiado não entra na receita da plataforma apenas porque está registrado no contrato [25] [27].
