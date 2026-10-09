# Direito civil, contratos, consumidor e assinaturas — v0.26.0

**Data da pesquisa:** 08/10/2026. **Escopo exato:** Direito civil, contratos, consumidor e assinaturas, com foco em SaaS/B2B/B2G, prova digital, aceite, versionamento, cancelamento, reembolso, responsabilidade e cláusulas de limitação. Este documento é uma pesquisa de requisitos e riscos de produto; não é parecer jurídico personalizado.

## Escopo e classificação das fontes

O mapa abaixo separa quatro coisas que não devem ser misturadas no motor de contratos:

- **Lei ou regulamento vigente:** Código Civil, CDC, Decreto do comércio eletrônico, MP da ICP-Brasil, Lei de Assinaturas Eletrônicas, CPC, Marco Civil e Lei de Licitações. A obrigação jurídica decorre do texto normativo e do enquadramento do caso.
- **Orientação administrativa:** páginas do Governo Digital e do ITI explicam uso e validação de assinaturas, mas não substituem a lei nem o ato do órgão contratante.
- **Jurisprudência institucional:** notícias e informativos do STJ registram decisões e teses aplicadas a casos concretos. Servem como evidência interpretativa, não como autorização genérica para todos os fluxos.
- **Hipótese de produto:** classificação interna da assinatura da plataforma, desenho de quatro olhos, prazos de aceite, hash, ledger, política de sete dias e limites comerciais. Esses elementos precisam ser publicados apenas depois de revisão e decisão contratual.

O fato de uma lei não exigir certificado ICP-Brasil para todo contrato privado não significa que qualquer fluxo esteja automaticamente adequado. A força probatória depende da autoria identificável, integridade, aceitação do meio, contexto de formação e capacidade/poderes de quem assina. A prova também pode ser impugnada e submetida a perícia.

## Estado atual do release que precisa ser corrigido

O release **v0.26.0 está tecnicamente fechado, mas não está juridicamente liberado para publicação ou cobrança real**. O próprio `README.md` afirma que não há publicação em loja ou domínio, provedor de pagamentos, provedor fiscal ou cobrança real. O `docs/LEGAL_FRAMEWORK.md` registra onze documentos em `legal_documents`, todos como `draft`, e o banco recusa aceite de minuta. A lista de documentos é: `terms_of_use`, `privacy_policy`, `cookies`, `subscription`, `marketplace`, `intermediation`, `payment`, `cancellation`, `refund`, `b2b` e `b2g`.

Essa trava é correta como estado de lançamento: `acceptance_stamp()` exige documento aprovado e vigente; a aprovação exige revisor, data e referência; o texto aprovado é imutável; e uma versão nova deixa o aceite anterior pendente. O release deve, porém, corrigir a forma como o produto comunica esse estado: **não dizer que os termos estão aceitos, vigentes ou juridicamente conformes enquanto os onze continuam minutas**.

O release tem duas camadas que devem ser apresentadas separadamente:

1. **Documentos legais da plataforma:** Termos de Uso e Política de Privacidade são os únicos marcados como exigindo aceite no registro atual; não podem ser coletados enquanto estiverem em `draft`.
2. **Acordos comerciais do motor v0.26.0:** `signed_agreements` permite publicar um documento, definir partes, colher assinaturas, ativar o acordo após todas as partes obrigatórias assinarem, derivar obrigações de entregar/aceitar/pagar e abrir nova versão quando o conteúdo muda. O teste real também demonstra quatro olhos, hash da versão, matriz de distribuição e invalidação das aprovações antigas.

O motor comercial **não aprova as onze minutas, não transforma a assinatura `platform_advanced` em ICP-Brasil, não cria nota fiscal, não cria cobrança real e não substitui o procedimento de contratação pública**. A documentação interna descreve a assinatura como avançada, mas essa é uma hipótese de enquadramento apoiada na técnica implementada e na aceitação das partes; não deve virar claim jurídico universal. A Lei 14.063/2020 disciplina diretamente interações com entes públicos e exclui, no seu Capítulo II, interações exclusivamente privadas; para B2B privado, o eixo principal é Código Civil + MP 2.200-2/2001 + prova do caso concreto. [4] [5]

Há também divergência de versão documental que deve ser corrigida antes de produção: as onze minutas dizem que se aplicam ao software v0.17.0, enquanto o release é v0.26.0. O gerador deve receber uma versão legal efetiva independente da versão de software, com changelog e motivo, sem reescrever retroativamente o texto que já foi aceito.

## Mapa de obrigações normativas

### 1. Código Civil: formação, boa-fé, interpretação e execução

O negócio jurídico exige agente capaz, objeto lícito, possível e determinado ou determinável, e forma prescrita ou não proibida; a declaração de vontade não depende de forma especial salvo exigência legal. Isso permite contratos eletrônicos em muitos fluxos, mas não elimina a necessidade de provar poderes de representação, objeto, preço, prazo e manifestação de vontade. [1]

A liberdade contratual está limitada pela função social; contratos civis e empresariais presumem-se paritários e simétricos até que elementos concretos justifiquem afastar essa presunção; a alocação de riscos deve ser observada; e a revisão contratual é excepcional e limitada. A boa-fé objetiva vale na conclusão e na execução. Contratos de adesão com ambiguidade são interpretados a favor do aderente, e não se pode impor renúncia antecipada a direito decorrente da natureza do negócio. [1]

**Implicações para o motor:** guardar objeto, partes, poderes, versão, preço, moeda, calendário, condições suspensivas, matriz de risco, aceite e histórico; evitar alterar unilateralmente o conteúdo de contrato ativo; registrar a aceitação de anexos e políticas referenciadas; e distinguir proposta, contrato assinado, ato de execução e pagamento. Uma tela de “aceitar” não deve concluir sozinha que houve contrato se faltam partes obrigatórias ou se a proposta estava vencida.

Para contratos continuados, o Código Civil trata o distrato pela mesma forma exigida para o contrato, a resilição unilateral mediante denúncia quando permitida e, havendo investimentos consideráveis, após prazo compatível; a cláusula resolutiva expressa opera de pleno direito; e o inadimplemento pode fundamentar resolução ou cumprimento com perdas e danos. A onerosidade excessiva exige contrato continuado ou diferido, acontecimento extraordinário e imprevisível e extrema vantagem para a outra parte. [1]

A cláusula penal pode ser prevista para inadimplemento total, obrigação específica ou mora. A execução pressupõe inadimplemento culposo ou mora, e o valor pode ser reduzido equitativamente quando a obrigação tiver sido cumprida em parte ou a penalidade for manifestamente excessiva. O produto não deve aplicar automaticamente multa sem identificar obrigação, vencimento, mora, culpa quando relevante, teto contratual e decisão revisável. [1]

Caso fortuito ou força maior afastam prejuízos quando não houver assunção expressa do risco; a parte em mora pode responder mesmo por evento posterior. Logo, uma cláusula de indisponibilidade, manutenção ou provedor deve mapear causa, aviso, mitigação, créditos, rescisão e retenção de dados, não apenas escrever “força maior”. [1]

### 2. CDC e contratação eletrônica: aplicar quando houver relação de consumo

O CDC define consumidor como pessoa física ou jurídica que adquire ou utiliza serviço como destinatária final e fornecedor como quem presta serviço mediante remuneração. Informação adequada e clara, proteção contra publicidade enganosa e reparação de danos são direitos básicos. Oferta precisa e publicidade integram o contrato; a apresentação deve ser correta, clara, precisa e ostensiva. [2]

Em SaaS, o enquadramento não é uniforme. Pessoa física que utiliza o serviço fora de uma atividade econômica tende a se enquadrar no conceito legal. Empresa, fundação ou OSC que compra a plataforma para uso como insumo da própria atividade pode estar fora do CDC; porém, o STJ adota teoria finalista mitigada: uma pessoa jurídica pode receber proteção se demonstrar vulnerabilidade técnica, fática, jurídica ou informacional capaz de desequilibrar a relação. A vulnerabilidade da pessoa jurídica é aferida no caso concreto; porte pequeno, isoladamente, não resolve a questão. [2] [13]

**Regra de produto:** não selecionar “CDC sim/não” apenas pelo tipo de conta (`company`, `osc`, `government`). O contrato deve guardar a finalidade do uso, comprador, usuário final, natureza do serviço como consumo ou insumo, evidências de vulnerabilidade quando alegadas e a decisão jurídica aplicável àquele produto/segmento. Enquanto isso não for decidido, a interface deve dizer “regime aplicável pendente de enquadramento”, e não prometer ou negar o CDC de forma universal.

Em relação de consumo, o fornecedor deve permitir conhecimento prévio e compreensão do contrato; cláusulas são interpretadas de modo mais favorável ao consumidor; declarações em escritos, recibos e pré-contratos vinculam o fornecedor. O art. 49 assegura sete dias para desistência de contratação fora do estabelecimento, com devolução imediata e monetariamente atualizada dos valores pagos. O Decreto 7.962/2013 exige informações do fornecedor, serviço, preço, pagamento, disponibilidade, execução e restrições; sumário antes da contratação; correção de erros; confirmação da aceitação; cópia conservável e reproduzível do contrato; atendimento eletrônico; resposta em até cinco dias; e meios eficazes para arrependimento pela mesma ferramenta utilizada. [2] [3]

Não se deve converter o prazo de sete dias em claim para toda relação B2B/B2G. Tampouco se deve omiti-lo quando o fluxo estiver dentro do CDC. Para consumidor, o arrependimento deve cancelar contratos acessórios sem ônus e, quando houver pagamento por cartão ou meio similar, o fornecedor deve comunicar imediatamente a instituição para evitar lançamento ou obter estorno. [3]

Cláusulas que excluam ou atenuem responsabilidade por vícios, eliminem reembolso previsto em lei, transfiram responsabilidade a terceiro, permitam variação unilateral de preço, autorizem alteração unilateral de conteúdo ou permitam cancelamento unilateral apenas pelo fornecedor são nulas no âmbito do CDC, com a ressalva legal de que, em relação de consumo com pessoa jurídica, a indenização pode ser limitada em situações justificáveis. Limitações de direitos devem ser redigidas com destaque e compreensão imediata em contrato de adesão. [2]

### 3. Assinatura eletrônica brasileira

A MP 2.200-2/2001 institui a ICP-Brasil e reconhece documentos eletrônicos. O art. 10, §1º, dá presunção de veracidade às declarações assinadas com certificação ICP-Brasil; o §2º preserva outros meios de comprovação de autoria e integridade, inclusive certificados não ICP, desde que admitidos pelas partes ou aceitos por quem receber o documento. [4]

A Lei 14.063/2020 classifica assinatura simples, avançada e qualificada. A avançada precisa estar associada univocamente ao signatário, usar dados sob controle exclusivo com elevado nível de confiança e permitir detectar qualquer alteração posterior; a qualificada usa certificado ICP-Brasil. A lei prevê revogação ou cancelamento definitivo do meio em caso de comprometimento. O Capítulo II trata de interações com entes públicos e não se aplica à interação exclusivamente privada entre pessoas físicas ou jurídicas. [5]

No release, senha + código de uso único por e-mail, desafio preso ao hash, HMAC do servidor, declaração, IP, agente, trilha encadeada e revogação são bons controles de identificação, integridade e auditabilidade. Ainda assim, **HMAC do servidor prova que a plataforma registrou um ato; não é certificado digital do signatário**. A categoria interna `platform_advanced` deve aparecer como “assinatura eletrônica da plataforma; nível jurídico sujeito ao contexto e à aceitação das partes”, nunca como “assinatura qualificada”, “ICP-Brasil”, “certificada pelo ITI” ou “Gov.br”.

O STJ decidiu em 2024 que a ausência de credenciamento da entidade certificadora na ICP-Brasil, por si só, não invalida assinatura eletrônica. O fundamento foi a admissão de outros meios pela MP 2.200-2, a autonomia das partes e o conjunto de elementos que confirmava a autenticidade no caso; a própria notícia ressalta que a assinatura avançada tem menor presunção que a qualificada. A decisão é apoio jurisprudencial para desenho probatório, não uma garantia de resultado em qualquer litígio. [12]

Para B2G, o nível não é decidido apenas pelo fornecedor. A Lei 14.063 deixa ao titular do Poder ou órgão o nível mínimo por ato próprio e admite assinatura simples em interações de menor impacto, avançada em hipóteses permitidas e qualificada em qualquer interação, com obrigatoriedade em hipóteses legais. O Decreto 10.543/2020 disciplina a Administração Pública Federal direta, autárquica e fundacional e admite assinatura avançada para manifestação de vontade em contratos, convênios e instrumentos bilaterais; níveis superiores podem ser exigidos pelo órgão. Estados, municípios, empresas estatais e órgãos autônomos podem ter regras próprias. [5] [6]

A página do Governo Digital é **orientação administrativa**, não fonte de dispensa: ela explica que Gov.br é assinatura avançada e que contas prata/ouro podem ser utilizadas para esse nível, enquanto qualificada usa certificado digital. O release atual não tem integração Gov.br nem ICP-Brasil. [10]

### 4. Prova digital, aceite e força executiva

O CPC admite todos os meios legais e moralmente legítimos; o juiz aprecia a prova e fundamenta seu convencimento. Documento particular é autêntico quando a autoria é identificada por meio legal, inclusive eletrônico, ou quando não há impugnação. Fotografias digitais, páginas da internet e mensagens eletrônicas podem provar os fatos representados, mas, se impugnadas, devem ser autenticadas eletronicamente ou periciadas. Ata notarial pode documentar a existência e o modo de existir de fatos, inclusive dados de imagem ou som em arquivo eletrônico. [7]

A Lei 14.620/2023 acrescentou ao CPC a regra de que, em título executivo constituído ou atestado por meio eletrônico, qualquer modalidade de assinatura prevista em lei pode ser usada e testemunhas podem ser dispensadas quando a integridade for conferida por provedor de assinatura. O Informativo 871 do STJ, sobre o REsp 2.205.708-PR, registra que certificado não ICP não é requisito exclusivo e que a integridade conferida pelo provedor é central. Isso não significa que todo contrato SaaS se tornou automaticamente título executivo: obrigação certa, líquida e exigível, forma do instrumento e demais requisitos continuam sendo avaliados. [7] [15]

O aceite robusto deve provar, em conjunto: texto integral ou referência reprodutível; versão; hash do conteúdo; identidade e autenticação; papel e poderes; data e hora com fuso; ação afirmativa; tela ou sumário apresentado; anexos; canal; resultado; e trilha de mudanças. IP e user-agent são contexto e dado pessoal, não prova isolada de autoria. Hash comprova correspondência do conteúdo, não que determinada pessoa o leu ou quis contratá-lo.

O ITI descreve o VALIDAR como serviço que confere autoria da assinatura eletrônica e integridade do documento conforme padrões técnicos, mas declara que não se responsabiliza pelo conteúdo nem recomenda o aceite. Assim, o produto não deve afirmar que um documento foi “validado pelo ITI” quando apenas possui hash/HMAC interno. [11]

O Marco Civil exige guarda sigilosa, em ambiente controlado e seguro, dos registros de acesso a aplicações por seis meses para provedor de aplicações constituído como pessoa jurídica, profissional e com fins econômicos; a disponibilização depende de ordem judicial, ressalvados dados cadastrais nas hipóteses legais. Essa retenção é distinta da retenção probatória do contrato e deve ser reconciliada com LGPD, finalidade, minimização, anonimização e legal hold. [8]

## Aplicação por tipo de contrato e por documento

| Documento em `docs/legal/` | Regime principal e incidência provável | Requisitos e correção do produto |
|---|---|---|
| `terms_of_use` — Termos de Uso | Código Civil; CDC se o usuário for consumidor; Decreto 7.962 se houver contratação eletrônica de consumo. | Identificar fornecedor, CNPJ, endereço e canal; sumário; oferta, limites, suspensão e alteração; destaque de limitações; consentimento/aceite versionado. Campos `{{ }}` impedem publicação. |
| `privacy_policy` — Política de Privacidade | LGPD e Marco Civil; CDC quando houver relação de consumo. | Não chamar aviso de “consentimento” para toda base legal. Relacionar finalidade, controlador/operador, retenção, compartilhamento, transferências e direitos. O aceite registra ciência quando cabível, sem substituir base legal. DPO, prazos e transferências continuam pendentes. |
| `cookies` — Cookies | LGPD/Marco Civil e orientação administrativa aplicável ao tratamento; hoje a minuta declara apenas cookies estritamente necessários. | Manter inventário e finalidade. Se adicionar analytics, publicidade ou terceiros, publicar nova versão, avaliar base legal e mecanismo de escolha. Não usar o log de aceite como autorização genérica para rastreamento. |
| `subscription` — SaaS | Código Civil; CDC conforme finalidade/vulnerabilidade; Decreto 7.962 no checkout de consumo. | Definir plano, preço, ciclo, renovação, reajuste, limites, downgrade, suporte, disponibilidade e dados. Aviso de preço deve respeitar contrato e não pode virar alteração unilateral abusiva. Separar assinatura de parcelamento. |
| `marketplace` — Marketplace | Código Civil; CDC pode alcançar consumidor do serviço anunciado ou o próprio marketplace conforme atuação; responsabilidade depende do papel efetivo. | Declarar se é vitrine, intermediação ou fornecedor. Identificar anunciante, preço, escopo e prazo; retirada/moderação; reclamações; não prometer resultado. Não usar “não somos parte” para apagar deveres que a operação real criar. |
| `intermediation` — Intermediação | Código Civil e regras do contrato efetivamente celebrado; CDC quando houver consumidor. | Distinguir apresentação, proposta e contrato. Registrar data/autoria e que proposta não obriga até instrumento próprio, salvo termos que configurem oferta. Não cobrar taxa de êxito sem carta jurídica específica. |
| `payment` — Pagamento | Código Civil; CDC no fornecimento ao consumidor; regras do provedor e, se tocar em recursos de terceiros, regulação de pagamentos. | Webhook assinado é fonte de verdade; idempotência; token, últimos quatro dígitos, chargeback; preço, multa, juros e nota fiscal definidos. Hoje não há provedor, webhook válido, nota fiscal nem pagamento real. |
| `cancellation` — Cancelamento | Código Civil para denúncia/distrato/resolução; CDC art. 49 e Decreto 7.962 quando aplicáveis. | Cancelamento autosserviço, protocolo, autor, data, situação anterior, fim da renovação, efeito no ciclo, exportação e retenção. Não universalizar sete dias nem prometer pro rata sem regra aprovada. |
| `refund` — Reembolso | CDC art. 49 e restituição quando aplicáveis; contrato civil para hipóteses negociadas. | Motivo codificado, valor, total/parcial, método, data da decisão, comunicação e confirmação. Não prometer prazo de crédito sem provedor. Hoje todas as cobranças são simuladas e não há reembolso real. |
| `b2b` — Institucional | Código Civil, boa-fé, alocação de riscos e eventual CDC mitigado. | Definir objeto, anexos, preço, implantação, dados, auditoria, IP, SLA, responsabilidade, teto e seguro. Separar dado declarado de comprovado; não vender atestado independente ou conformidade ESG/regulatória automática. |
| `b2g` — Poder Público | Lei 14.133/2021; Lei 14.063/2020 e regulamento do órgão; LGPD/LAI e regras locais conforme o caso. | Não oferecer checkout de órgão. Guardar edital/processo, autoridade, proposta, contrato, versão, publicação, fiscal, medições, pagamentos, aditivos e penalidades. Exigir nível de assinatura aprovado pelo órgão. A plataforma não é SEI, Transferegov, SIAFI nem diário oficial. |

### B2B, SaaS e limites de responsabilidade

Em relação empresarial paritária, é possível alocar riscos, definir teto e disciplinar perdas, desde que a cláusula seja clara, coerente com o objeto, compatível com boa-fé e não seja utilizada para legitimar dolo, fraude ou violação de regime especial. Em notícia de 2024 sobre o REsp 1.989.291, o STJ manteve limite de indenização de US$ 1 milhão entre empresas, considerando porte, contexto contratual, ausência de dolo demonstrado e inexistência de indenização suplementar prevista. Isso é orientação jurisprudencial contextual, não modelo automático para a plataforma. [14]

Se o CDC incidir, a proteção é mais restritiva: não é válido excluir ou atenuar genericamente responsabilidade por vício nem retirar reembolso legal. O teto deve ser separado por cenário: contrato B2B negociado, contrato de adesão B2B com possível vulnerabilidade, relação de consumo pessoa física, pessoa jurídica destinatária final e contrato administrativo. A interface deve mostrar a redação integral e destacar limitações, sem esconder a cláusula em link secundário.

O desenho recomendado para o motor é registrar, em cada contrato, a versão da cláusula, a categoria de relação, a base do teto, os riscos excluídos, os riscos não limitáveis segundo a revisão jurídica, o seguro exigido, o procedimento de aviso e mitigação e a regra de indenização suplementar. Isso é requisito de produto, não conclusão de validade.

### B2G e contratação pública

A Lei 14.133/2021 alcança contratações de tecnologia da informação e comunicação. Ela exige princípios de legalidade, publicidade, planejamento, transparência, segregação de funções, vinculação ao edital e segurança jurídica. Contratos administrativos são regidos por suas cláusulas e pelo direito público, com aplicação supletiva da teoria geral dos contratos e do direito privado. Devem indicar partes e representantes, finalidade, ato autorizador, processo de licitação/contratação direta e condições claras de execução, direitos, obrigações e responsabilidades. [9]

Contratos e aditivos devem ser escritos, juntados ao processo e disponibilizados em sítio oficial, admitida forma eletrônica conforme regulamento. O art. 92 exige, entre outros itens, objeto, vínculo ao edital/proposta, legislação, preço e pagamento, reajuste, medição, prazos, matriz de risco quando cabível, garantias, direitos, responsabilidades e penalidades. O art. 117 exige fiscal do contrato. [9]

**Correção exigida:** o `b2g` não pode dar ao órgão a impressão de que o autosserviço da plataforma é uma contratação pública completa. Não afirmar dispensa, inexigibilidade, economicidade, regularidade, adesão a ata ou compatibilidade com edital sem ato e análise do órgão. A plataforma pode fornecer descrição técnica verdadeira e preservar documentos; não pode substituir a assessoria jurídica, o processo administrativo, o sistema oficial, a publicação ou a decisão do órgão.

## Requisitos de produto para o motor de contratos e aceites

### A. Identidade, capacidade e representação

1. Antes de aceitar ou assinar, mostrar parte, razão social, CNPJ, endereço, papel, finalidade do contrato e poderes requeridos.
2. Registrar se a pessoa assina em nome próprio ou da organização, sua função, delegação/procuração e data da verificação. O tipo de conta não prova poder de representação.
3. Bloquear assinatura quando a organização, parte, documento ou versão não estiver visível ao signatário autorizado.
4. Separar `acceptance` de política legal, `signature` de acordo comercial e `approval` interno. Um aceite de privacidade não é assinatura de contrato de financiamento.

### B. Formação e aceite informado

1. Apresentar texto integral em formato legível, sumário e cláusulas limitativas destacadas quando CDC puder incidir.
2. Exibir preço, tributos/encargos quando definidos, ciclo, renovação, limites, condições de execução, cancelamento e reembolso antes da ação final.
3. Exigir ação afirmativa inequívoca, sem caixas pré-marcadas, e registrar a versão exata apresentada.
4. Permitir corrigir dados antes da conclusão, confirmar recebimento imediatamente e entregar cópia conservável e reproduzível.
5. Para documento `draft`, retornar bloqueio explicando que não há aceite registrável. Não trocar o bloqueio por um aviso na interface.
6. Para novos termos, apontar diferenças relevantes, prazo de aviso contratual e exigência de novo aceite. Não revogar retroativamente direitos já adquiridos.

### C. Assinatura e prova

1. Manter `subject_sha256`, `body_sha256`/hash de documento, versão, identificação do signatário, org, papel, declaração, desafio, método, nível de identidade, IP, user-agent, hora/fuso, resultado e cadeia de auditoria.
2. Invalidar desafio quando conteúdo mudar; limitar tentativas; impedir reuso; registrar expiração, recusa e revogação como fatos novos.
3. Manter documento e assinatura imutáveis; corrigir por nova versão, revogação ou supersessão, nunca por UPDATE destrutivo.
4. Exibir publicamente apenas campos curados: versão assinada, hash, signatário/papel e estado. Não expor e-mail, chave de armazenamento ou dados de outra organização.
5. Separar nível jurídico de mecanismo criptográfico. `platform_advanced` não pode ser promovido para `icp_brasil` por configuração administrativa.
6. Exigir `qualified` ou provedor exigido pelo órgão/edital quando o tipo de ato assim determinar; bloquear a operação se o provedor não estiver disponível.
7. Para título executivo eletrônico, adicionar verificação da integridade pelo provedor e guardar o fundamento da dispensa de testemunhas; não classificar todo contrato como título executivo.

### D. Versionamento e efeito operacional

1. Um contrato publicado/ativo é imutável.
2. Alteração cria `version = n+1`, hash novo, motivo, data, autor, cópia dos marcos e estado `draft`.
3. A versão anterior fica `superseded`; aprovações e obrigações da versão anterior não devem ser reutilizadas sem regra expressa de transição.
4. Nova versão exige novas assinaturas das partes obrigatórias e recalcula preço, taxa, marcos, vencimentos e obrigações.
5. Preservar comparação entre versões e qual versão foi usada em cada entrega, aceite, cobrança, cancelamento ou reembolso.
6. Diferenciar correção editorial sem efeito material de alteração de obrigação. A primeira pode ter fluxo próprio; a segunda exige novo aceite/assinatura.

### E. Obrigações, aceitação e pagamento

1. Cada marco deve derivar `deliver`, `accept` e `pay` com credor, devedor, valor, prazo, condição de ativação e evidência.
2. Quem entrega não pode aceitar a própria entrega; quatro olhos devem ser uma restrição no banco, não apenas uma instrução.
3. Aceite/rejeição exige ator, data, nota e, na recusa, motivo; prazo pode ser em dias corridos ou úteis, mas o contrato deve dizer qual calendário.
4. O pagamento deve ficar sem vencimento enquanto a condição de aceite não ocorrer, se essa for a regra contratual.
5. Valor contratado, taxa de serviço e receita reconhecida devem permanecer distintos. A taxa do v0.26.0 é cobrança própria ao financiador apenas quando carta legal estiver ativa; sem provedor continua simulada.
6. Nunca usar a matriz de distribuição para sugerir custódia, saldo de terceiro, repasse ou processamento de aporte.

### F. Cancelamento e reembolso

1. Cancelamento pelo mesmo canal da contratação quando CDC/decreto forem aplicáveis; confirmação imediata; protocolo e estado anterior.
2. Separar cancelamento da renovação, rescisão imediata, distrato, suspensão por inadimplência, encerramento por fraude e arrependimento.
3. Guardar início/fim do ciclo, uso do serviço, valor pago, valor devido, pro rata, créditos e justificativa.
4. Para CDC, oferecer sete dias e restituição conforme art. 49 quando o enquadramento existir; para B2B/B2G, aplicar regra contratual aprovada, sem afirmar que o CDC incide ou não incide automaticamente.
5. Não apagar dados no cancelamento por padrão; garantir exportação, retenção legal/probatória e eliminação/anonimização conforme LGPD e instrumento.
6. Em pagamento real, comunicar provedor, guardar idempotência e confirmação de estorno; antes disso, marcar tudo como simulado e não prometer crédito.

## Requisitos de dados e retenção

### Dados mínimos do contrato e do aceite

- `document_id`, `doc_key`, tipo de documento, versão efetiva, versão do software, status, início/fim de vigência, motivo de supersessão e `body_sha256`.
- Partes, CNPJ/identificador, org, usuário, papel, poderes e fonte da verificação.
- Texto/arquivo conservável, anexos e lista de cláusulas incorporadas por referência.
- Aceite/assinatura: ação, declaração, desafio, método, nível, IP, user-agent, timestamp, fuso, HMAC/prova, revogação, estado e trilha de eventos.
- Contrato operacional: objeto, preço, moeda, taxa, pagador, modo adicional/descontado, matriz de distribuição, marcos, calendário, aceite, pagamento, penalidades, matriz de riscos e evidências.
- Cancelamento/reembolso: solicitação, canal, autor, motivo, regime aplicável, elegibilidade, valor, decisão, comunicação ao provedor e crédito.

### Minimização e governança

IP, user-agent, e-mail e identificadores de sessão são dados pessoais. O release já prevê anonimização seletiva após 18 meses para IP/user-agent da prova de aceite e preservação pseudonimizada do registro, mas esse prazo é proposta de produto e precisa ser alinhado à finalidade, Marco Civil, obrigações legais, litígio e política de retenção. A alteração permitida pelo gatilho deve continuar limitada a anonimização; não permitir apagar hash, versão, ator pseudonimizado ou sequência de eventos sem base legal.

Guardar hash não substitui o arquivo. O hash deve ser derivado pelo servidor da versão apresentada, e o arquivo deve poder ser exportado junto do manifesto de integridade. Hash também não é anonimização: se o texto ou identificador puder ser reidentificado, ele continua sujeito a controles de dados.

Para acesso público, devolver somente o mínimo necessário à verificação. Para terceiros, liberar documento e trilha por autorização da organização e escopo; para autoridades, respeitar ordem judicial e canal formal. Registros de acesso do Marco Civil devem ficar segregados de evidências contratuais, com acesso controlado e auditoria. [8]

A retenção deve ter matriz separando: (a) prova do contrato; (b) registro de acesso à aplicação; (c) faturamento e obrigação fiscal; (d) dados de conta; (e) anexos com dados de terceiros; (f) legal hold. A política não deve usar “append-only” como justificativa para reter indefinidamente dado pessoal identificável.

## Testes e controles obrigatórios antes de liberar

### Bloqueios de publicação

- Documento `draft`, expirado, sem revisor, sem referência ou sem texto não pode ser aceito.
- Documento aprovado sem data de vigência ou com vigência anterior à aprovação deve ser recusado.
- Texto, hash e arquivo não podem ser editados depois de publicados.
- Gerador de registro legal deve recalcular hash dos onze arquivos e falhar se banco e repositório divergirem.
- Versão nova deve aparecer como pendente e não reaproveitar aceite antigo.

### Identidade e assinatura

- Desafio inexistente, código errado, expirado, reutilizado, excesso de tentativas, senha errada e conteúdo alterado devem produzir estados distintos e auditáveis.
- A organização estranha não pode visualizar, pedir desafio, assinar ou aceitar.
- O mesmo signatário não pode cumprir dois olhos; todas as partes obrigatórias devem assinar para ativar.
- Assinatura revogada permanece verificável como revogada; versão supersedida permanece verificável como supersedida.
- Tentativa de usar `icp_brasil`, `govbr`, carimbo RFC 3161, biometria ou SMS sem provedor deve ser bloqueada com erro explícito, não simulada.
- Testar exportação e reprodução do documento, hash e manifesto em outro ambiente.

### Prova e consumidor

- Testar fluxo de pré-visualização, sumário, destaque de limitações, correção de erro, aceite, confirmação e cópia.
- Testar pessoa física, empresa destinatária final, empresa usando SaaS como insumo, OSC e órgão público em cenários distintos.
- Testar sete dias apenas quando a regra `consumer_applicable` estiver ativa; testar cancelamento fora do prazo e reembolso parcial conforme contrato.
- Testar impugnação de IP/user-agent sem apagar o restante da prova.
- Testar cláusula de limitação que não pode ser aplicada ao consumidor, que deve exigir revisão humana ou aplicar fallback mais protetivo.

### Contrato operacional e finanças

- Publicar acordo sem duas partes, com partes duplicadas ou sem marcos deve falhar.
- Transição de marco fora do grafo, aceite pelo entregador e recusa sem motivo devem falhar.
- Aceite deve abrir pagamento somente se a condição contratual estiver cumprida.
- Reprocessamento não pode duplicar matriz, obrigação ou cobrança.
- Alterar valor ou conteúdo deve criar nova versão, invalidar aprovação antiga e recalcular taxa.
- Nenhum valor de terceiro pode aparecer como saldo, carteira, escrow, payout ou receita da plataforma.
- Sem provedor, checkout, webhook, estorno e nota fiscal reais devem permanecer indisponíveis.

### B2G

- Impedir checkout de órgão sem processo, autoridade, base de contratação e regra do órgão.
- Exigir registro de edital/proposta/contrato, representantes, fiscal, publicação, medição, pagamento, aditivo e extinção.
- Configurar nível de assinatura por ente e tipo de ato; não assumir que o Decreto 10.543 vale para município ou estado.
- Reprovar claim de “contratação pública conforme”, “dispensa” ou “inexigibilidade” sem fonte e aprovação do órgão.

## Claims proibidos ou que devem ser reescritos

1. **“Aceite válido/vigente dos Termos”** enquanto qualquer documento legal estiver `draft` ou sem aprovação/revisão registrada.
2. **“Assinatura ICP-Brasil”, “assinatura qualificada”, “certificada pelo ITI” ou “Gov.br”** para `platform_advanced`.
3. **“O hash prova quem assinou”**. O hash prova correspondência/integridade do conteúdo; autoria depende do conjunto probatório.
4. **“Assinatura eletrônica sempre vale como assinatura manuscrita”** sem ressalva de contexto, aceitação, impugnação, órgão e exigência legal.
5. **“Todo contrato é título executivo”** ou **“não precisa de testemunhas”** sem verificar CPC, obrigação e integridade conferida pelo provedor.
6. **“CDC não se aplica a empresas/OSCs”** ou **“CDC se aplica a todos os clientes”**. O enquadramento depende da finalidade e, para pessoa jurídica, da vulnerabilidade demonstrada.
7. **“Arrependimento de sete dias para qualquer contrato”** ou **“não há direito de arrependimento”** sem a regra de aplicabilidade do fluxo.
8. **“Reembolso garantido em X horas”**, **“estorno automático”** ou **“pagamento processado”** enquanto não houver provedor real e política aprovada.
9. **“SLA de X%”, “disponibilidade garantida”** ou promessa de prazo de suporte sem medição, infraestrutura e cláusula vigente.
10. **“Responsabilidade zero”, “não respondemos por nenhuma perda”** ou limite que elimine direitos legais, vícios, fraude ou deveres inderrogáveis.
11. **“B2G conforme à Lei 14.133”, “dispensa garantida”, “inexigibilidade” ou “substitui SEI/Transferegov/SIAFI”**.
12. **“Não custodiamos recursos, logo não existe risco regulatório”**. A arquitetura não custodial é um fato técnico; o enquadramento jurídico da cobrança, intermediação e taxa ainda exige revisão.
13. **“Ledger comprova impacto, despesa ou verdade”**. Ledger prova registro e integridade do registro; não transforma declaração em validação, auditoria ou laudo.
14. **“Verificado” como atestado de idoneidade, capacidade técnica, aprovação pública ou conformidade** quando a plataforma só conferiu documento ou registro em uma data.

## Lacunas prioritárias

1. **Aprovação jurídica das onze minutas:** razão social, CNPJ, endereço, foro, canais, DPO, controlador/operador, suboperadores, transferências, retenções, preços, nota fiscal, limites, SLA, cancelamento e reembolso ainda são campos ou perguntas abertas.
2. **Regime por cliente e fluxo:** implementar matriz de incidência do CDC por finalidade, destinatário final e vulnerabilidade, com revisão por tipo de contratação.
3. **Matriz de assinatura por ato:** indicar quando a assinatura da plataforma é suficiente, quando o contrato deve aceitar expressamente o método e quando o órgão/lei/edital exige Gov.br, ICP-Brasil, testemunhas ou outro mecanismo.
4. **Poderes de representação:** o motor guarda papel, mas a evidência de procuração/delegação e sua validade precisam ser tratadas como dados e condição de assinatura.
5. **Oferta e checkout:** ainda não há pagamento real, emissão de nota fiscal nem preço institucional B2B/B2G; não publicar uma simulação como contrato vigente.
6. **Cancelamento e reembolso:** falta decisão sobre pro rata, uso proporcional, indisponibilidade sem SLA, prazo de crédito e comunicação ao provedor.
7. **Responsabilidade e seguro:** faltam teto por cenário, carve-outs, indenização, limite de danos, seguro, continuidade, recuperação e procedimento de incidentes.
8. **B2G:** falta integração e governança com processo oficial, regras locais, publicação, fiscal, matriz de risco, aditivos, dados públicos e tabela de temporalidade.
9. **Prova e retenção:** falta manifesto exportável, carimbo de tempo externo, legal hold, política de perícia/ata notarial e decisão de retenção compatível com Marco Civil, LGPD e obrigações do contrato.
10. **Conhecimento jurídico no produto:** cada item regulatório publicado no Knowledge Hub deve ter fonte, órgão, título, data de consulta e data de revisão; ao vencer, deve virar “Revisão necessária”, não continuar como regra atual.
11. **Divergência de versão:** atualizar as minutas v0.17.0 para o estado funcional v0.26.0 ou declarar, de forma visível, que o texto se refere à versão histórica e não ao release atual.
12. **Separação entre lei, orientação e hipótese:** a interface e o banco precisam exibir a natureza da afirmação. Uma recomendação do STJ, uma página do ITI e uma hipótese de UX não podem aparecer como “lei”.

## Registro das fontes consultadas

| Ref. | Órgão/autor; título; data | Natureza | O que sustenta |
|---|---|---|---|
| [1] | Presidência da República/Planalto, **Lei nº 10.406/2002 — Código Civil**, publicada em 10/01/2002, texto compilado consultado em 08/10/2026 | Lei vigente | validade e forma do negócio; boa-fé; contratos de adesão; paridade e alocação de risco; força maior; cláusula penal; distrato, denúncia, resolução e onerosidade excessiva. |
| [2] | Presidência da República/Planalto, **Lei nº 8.078/1990 — Código de Defesa do Consumidor**, publicada em 11/09/1990, texto compilado consultado em 08/10/2026 | Lei vigente | conceitos de consumidor/fornecedor; informação e oferta; interpretação; arrependimento; cláusulas abusivas; contratos de adesão e limites de responsabilidade. |
| [3] | Presidência da República/Planalto, **Decreto nº 7.962/2013 — contratação no comércio eletrônico**, de 15/03/2013 | Regulamento vigente | informação do fornecedor e oferta; sumário; correção; confirmação; cópia conservável; atendimento; arrependimento, confirmação e estorno. |
| [4] | Presidência da República/Planalto, **MP nº 2.200-2/2001 — ICP-Brasil**, de 24/08/2001 | Medida provisória com força de lei, vigente | documentos eletrônicos; presunção de certificação ICP-Brasil; admissão de outros meios de autoria e integridade aceitos pelas partes. |
| [5] | Presidência da República/Planalto, **Lei nº 14.063/2020 — assinaturas eletrônicas**, de 23/09/2020 | Lei vigente | classificações simples, avançada e qualificada; alcance público; requisitos de avançada; revogação; níveis definidos pelo ente público. |
| [6] | Presidência da República/Planalto, **Decreto nº 10.543/2020 — assinaturas na Administração Pública Federal**, de 13/11/2020 | Regulamento vigente no âmbito federal indicado | escopo federal; assinatura simples/avançada/qualificada; contratos e instrumentos bilaterais; validação de identidade e exigência de nível superior. |
| [7] | Presidência da República/Planalto, **Lei nº 13.105/2015 — Código de Processo Civil**, de 16/03/2015, texto atualizado consultado em 08/10/2026 | Lei vigente | meios de prova; autenticidade eletrônica; reprodução digital; ata notarial; prova impugnada; títulos eletrônicos e integridade. |
| [8] | Presidência da República/Planalto, **Lei nº 12.965/2014 — Marco Civil da Internet**, de 23/04/2014, texto atualizado consultado em 08/10/2026 | Lei vigente | guarda sigilosa de registros de acesso por seis meses; ordem judicial; privacidade, segurança e aplicação territorial. |
| [9] | Presidência da República/Planalto, **Lei nº 14.133/2021 — Licitações e Contratos Administrativos**, de 01/04/2021, texto atualizado consultado em 08/10/2026 | Lei vigente | contratações de TIC; princípios; forma eletrônica; conteúdo obrigatório; publicidade; fiscalização; matriz de riscos; alterações e extinção. |
| [10] | Ministério da Gestão/Governo Digital, **Saiba mais sobre a Assinatura Eletrônica**, página institucional consultada em 08/10/2026 | Orientação administrativa | explica que Gov.br é assinatura avançada, diferencia níveis e remete à Lei 14.063 e à MP 2.200-2; não substitui ato do órgão. |
| [11] | Instituto Nacional de Tecnologia da Informação (ITI), **VALIDAR — Sobre**, versão indicada na página 2.4, consultada em 08/10/2026 | Serviço/orientação institucional | escopo de validação de autoria e integridade, sem validar conteúdo nem recomendar aceite. |
| [12] | Superior Tribunal de Justiça, **Falta de credenciamento da entidade certificadora na ICP-Brasil, por si só, não invalida assinatura eletrônica**, notícia de 03/12/2024, REsp 2.159.442 | Jurisprudência institucional | validade contextual de assinatura não ICP quando aceita e corroborada por elementos de autenticidade; menor presunção que qualificada. |
| [13] | Superior Tribunal de Justiça, **Consumidor pessoa jurídica: quando as empresas podem ter a proteção do CDC?**, notícia de 08/09/2024 | Jurisprudência institucional | teoria finalista mitigada; vulnerabilidade da pessoa jurídica deve ser demonstrada e analisada concretamente. |
| [14] | Superior Tribunal de Justiça, **É válida cláusula que limita responsabilidade contratual entre multinacional e representante brasileira**, notícia de 06/02/2024, REsp 1.989.291 | Jurisprudência institucional | manutenção contextual de teto entre empresas, considerando porte, ausência de dolo demonstrado e redação contratual. |
| [15] | Superior Tribunal de Justiça, **Informativo nº 871**, de 18/11/2025, REsp 2.205.708-PR | Informativo de jurisprudência | assinatura não ICP pode comprovar autoria/integridade se aceita; CPC art. 784, §4º e integridade conferida pelo provedor. |

## Referências

[1]: https://www.planalto.gov.br/ccivil_03/leis/2002/l10406compilada.htm "Presidência da República — Lei nº 10.406/2002, Código Civil — 10/01/2002; texto compilado consultado em 08/10/2026."
[2]: https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm "Presidência da República — Lei nº 8.078/1990, Código de Defesa do Consumidor — 11/09/1990; texto compilado consultado em 08/10/2026."
[3]: https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2013/decreto/d7962.htm "Presidência da República — Decreto nº 7.962/2013, contratação no comércio eletrônico — 15/03/2013."
[4]: https://www.planalto.gov.br/ccivil_03/mpv/antigas_2001/2200-2.htm "Presidência da República — MP nº 2.200-2/2001, ICP-Brasil e documentos eletrônicos — 24/08/2001."
[5]: https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2020/lei/l14063.htm "Presidência da República — Lei nº 14.063/2020, assinaturas eletrônicas — 23/09/2020."
[6]: https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2020/decreto/d10543.htm "Presidência da República — Decreto nº 10.543/2020, assinaturas eletrônicas na Administração Pública Federal — 13/11/2020."
[7]: https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2015/lei/l13105.htm "Presidência da República — Lei nº 13.105/2015, Código de Processo Civil — 16/03/2015."
[8]: https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2014/lei/l12965.htm "Presidência da República — Lei nº 12.965/2014, Marco Civil da Internet — 23/04/2014."
[9]: https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2021/lei/l14133.htm "Presidência da República — Lei nº 14.133/2021, Licitações e Contratos Administrativos — 01/04/2021."
[10]: https://www.gov.br/governodigital/pt-br/identidade/assinatura-eletronica/saiba-mais-sobre-a-assinatura-eletronica "Ministério da Gestão/Governo Digital — Saiba mais sobre a Assinatura Eletrônica — página institucional consultada em 08/10/2026."
[11]: https://validar.iti.gov.br/sobre.html "Instituto Nacional de Tecnologia da Informação — VALIDAR, serviço de validação de assinaturas eletrônicas — versão 2.4 indicada na página, consultada em 08/10/2026."
[12]: https://www.stj.jus.br/sites/portalp/Paginas/Comunicacao/Noticias/2024/03122024-Falta-de-credenciamento-da-entidade-certificadora-na-ICP-Brasil--por-si-so--nao-invalida-assinatura-eletronica-.aspx "Superior Tribunal de Justiça — Falta de credenciamento da entidade certificadora na ICP-Brasil, por si só, não invalida assinatura eletrônica — 03/12/2024."
[13]: https://www.stj.jus.br/sites/portalp/Paginas/Comunicacao/Noticias/2024/08092024-Consumidor-pessoa-juridica-quando-as-empresas-podem-ter-a-protecao-do-CDC.aspx "Superior Tribunal de Justiça — Consumidor pessoa jurídica: quando as empresas podem ter a proteção do CDC? — 08/09/2024."
[14]: https://www.stj.jus.br/sites/portalp/Paginas/Comunicacao/Noticias/2024/06022024-E-valida-clausula-que-limita-responsabilidade-contratual-entre-multinacional-e-representante-brasileira.aspx "Superior Tribunal de Justiça — É válida cláusula que limita responsabilidade contratual entre multinacional e representante brasileira — 06/02/2024."
[15]: https://scon.stj.jus.br/jurisprudencia/externo/informativo/?aplicacao=informativo&acao=pesquisar&livre=@CNOT='021938' "Superior Tribunal de Justiça — Informativo nº 871, REsp 2.205.708-PR, documentos eletrônicos e assinatura não ICP-Brasil — 18/11/2025."
