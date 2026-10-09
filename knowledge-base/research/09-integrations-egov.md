# Integrações governamentais, APIs e interoperabilidade — pesquisa para o release v0.26.0

**Recorte da pesquisa:** 8 de outubro de 2026. **Domínio:** integrações governamentais, APIs e interoperabilidade, com foco em gov.br/Conecta gov.br, Transferegov, SICONV legado quando pertinente, PNCP, Portal da Transparência, eSocial quando houver hipótese de uso, LGPD no Poder Público, autenticidade, certificados, limites de taxa, contratos de dados e estado da integração.

Este relatório separa quatro camadas que não devem ser confundidas: **lei ou regulamento vigente**, **orientação administrativa oficial**, **padrão técnico ou administrativo voluntário**, e **hipótese de produto**. A última camada é proposta para a IMPACTO; não é uma afirmação de que algum órgão público a aprovou.

## 1. Estado atual que o release precisa corrigir

A v0.26.0 possui uma camada genérica de Integration Hub, mas **não possui integração governamental oficial conectada, homologada ou ativa**. O catálogo local classifica `government_api` como **SCAFFOLDED**, com `pull` parcial, sem `push`, webhook, lote ou assíncrono, e com autorização externa necessária. A própria matriz define que `production_active` somente pode ser promovido com evidência externa auditada. [24] [25]

Os testes existentes usam `FakeTransport`. Eles provam o lado da IMPACTO — contratos internos, montagem de autenticação, mapeamento, idempotência, retries, isolamento de organizações e segurança —, mas **não provam compatibilidade** com Gov.br, Conecta, Transferegov, PNCP, Portal da Transparência ou eSocial. [27] [28] [29]

A matriz de homologação registra `government_api` como bloqueada por falta de conta e credencial de fornecedor. A matriz sistêmica mantém como `BLOCKED_EXTERNAL` as integrações externas e declara que pagamento real, assinatura ICP-Brasil/gov.br e integrações governamentais continuam fora do que foi ligado. [26] [24]

O documento `LEGAL_FRAMEWORK.md` ainda é útil como inventário de limites, mas foi escrito em versão anterior e declara, corretamente, que a plataforma não tem integração com SICONV/Transferegov, SIAFI, Portal da Transparência, e-SIC ou sistema de compras. Esse texto deve ser atualizado para fazer referência a este relatório sem trocar “não conectado” por “integrado”. [31]

A verificação pública existente comprova **o registro, a versão, o hash e a situação que a própria IMPACTO registrou**. Ela não comprova que o conteúdo é verdadeiro, que um documento é oficial de governo, que houve assinatura qualificada ou que o dado foi validado por um órgão público. [30]

**Correção editorial obrigatória do release:** substituir qualquer formulação genérica como “integra com o governo” por um estado específico: `não iniciado`, `scaffolded`, `credenciamento solicitado`, `homologação em curso`, `homologado` ou `produção ativa`, sempre com órgão, ambiente, credencial, evidência, data de verificação e validade. Um adapter de dublê ou um endpoint público consultado não é homologação.

## 2. Base jurídica e administrativa aplicável

### 2.1 Normas vigentes

- A **Lei nº 13.726/2018** racionaliza atos administrativos, dispensa exigências documentais desnecessárias e impede que um órgão exija documento emitido por outro órgão do mesmo Poder, ressalvadas as hipóteses legais. Ela dá fundamento à simplificação, mas não cria por si só uma autorização técnica para qualquer terceiro acessar uma base. [7]
- A **Lei nº 14.129/2021 — Governo Digital** exige que dados não pessoais sejam, como regra, públicos, legíveis por máquina e em formato aberto, respeitando a LAI e a LGPD; também exige descrição suficiente da estrutura, semântica, qualidade e integridade, atualização periódica e histórico. A lei prevê intercâmbio entre órgãos e entidades, sempre respeitando a LGPD. [8]
- A mesma Lei nº 14.129/2021 determina que órgãos gestores considerem interoperabilidade, segurança, proteção de dados, custo-benefício e reaproveitamento de infraestrutura. Também atribui aos órgãos responsabilidade pela publicidade dos registros de referência e permite que pessoas verifiquem correção, exatidão, completude e acesso a seus dados. [8]
- A **LGPD — Lei nº 13.709/2018** autoriza o Poder Público a tratar e compartilhar dados necessários à execução de políticas públicas previstas em lei, regulamento, contrato, convênio ou instrumento congênere, sem dispensar princípios, transparência, segurança, registros e direitos dos titulares. O tratamento pelo Poder Público deve atender finalidade pública e interesse público; os dados devem ser mantidos em formato interoperável e estruturado para uso compartilhado; o compartilhamento deve ter finalidade específica e atribuição legal. [9]
- A **Lei nº 14.063/2020** classifica assinaturas eletrônicas em simples, avançada e qualificada. A qualificada usa certificado digital ICP-Brasil e possui o maior nível de confiabilidade, mas o nível mínimo exigido depende do ato e da regra aplicável ao ente público. Não é correto tratar todo login gov.br, aceite, token ou assinatura eletrônica como assinatura qualificada. [11]
- A **Lei nº 14.133/2021** tornou o PNCP o local de divulgação e manutenção do inteiro teor do edital e anexos. A lei também exige publicidade dos atos e prevê o PNCP como infraestrutura nacional de contratação pública. A obrigação de publicação do órgão não equivale a uma autorização para a IMPACTO publicar ou retificar dados em nome dele. [20]
- O **Decreto nº 11.271/2022** é a base administrativa indicada pelo próprio Transferegov para o Sigpar e para a evolução da Plataforma +Brasil para o Transferegov.br. [14]

### 2.2 Orientações administrativas oficiais

O **Conecta gov.br** é um programa federal de troca automática e segura de informações entre sistemas governamentais para evitar que o cidadão reapresente informação que a Administração já possua. A página oficial informa que a plataforma não está disponível para uso direto de cidadãos ou empresas privadas; o uso é entre órgãos e entidades públicas, com exceções e disponibilizações específicas para entes estaduais. [1]

A adesão ao Conecta requer autocadastro do dirigente de TI e do responsável técnico, validação do cadastro, solicitação de adesão à API, análise e aprovação pelo órgão responsável. A solicitação deve conter a finalidade e assinaturas dos responsáveis. Depois da aprovação, há credencial de homologação quando o serviço a oferecer e credencial de produção; algumas APIs não possuem homologação. [2]

O próprio Conecta informa que a credencial de produção pode exigir conta gov.br e, para assinatura do termo, selo Prata/Ouro ou certificado ICP-Brasil e-CPF do gestor cadastrado. Também prevê liberação de IP e documentação por ambiente. O gestor da API pode liberar ou revogar acesso, acompanhar consumidores e obter relatórios de consumo. [3]

As regras de usabilidade do Conecta são **orientação administrativa de gestão de volumetria**, não um rate limit universal de todas as APIs brasileiras. Para órgãos com planos acima de 500 mil consultas, o monitoramento do consumo é responsabilidade do órgão; há revisão de volumetria e cancelamento/suspensão por inatividade de 12 meses. [4]

O catálogo do Conecta apresenta APIs documentadas, versionadas e monitoradas, com separação entre APIs disponíveis pela plataforma, APIs externas, registros de referência e catálogo nacional. O catálogo consultado listava 96 APIs, mas esse número é um retrato da página na data da pesquisa e não uma promessa de disponibilidade ou autorização para a IMPACTO. [5]

A **ePING** define um conjunto mínimo de premissas, políticas e especificações para TIC do Poder Executivo Federal. Órgãos e entidades do Sisp devem observá-la no planejamento de contratação, aquisição e atualização de sistemas; a adoção por outros Poderes e entes é facultativa. A ePING prioriza padrões abertos e aceita padrões proprietários de forma transitória no legado ou quando não houver padrão aberto. Ela é padrão administrativo de interoperabilidade, não certificado de conformidade do produto. [6]

A **ANPD**, em seu guia sobre tratamento pelo Poder Público, recomenda que compartilhamentos sejam formalizados e registrados em processo administrativo, com análise técnica e jurídica, motivação, finalidade, base legal, duração, transparência, direitos, segurança e definição de responsabilidades. O guia recomenda contrato, convênio, instrumento congênere ou decisão administrativa; é orientação oficial derivada da LGPD, e não substitui a análise do caso concreto. [10]

### 2.3 Padrões técnicos e literatura

Para este domínio, as fontes primárias e institucionais acima são suficientes para as conclusões normativas. OAuth/OIDC, HTTPS/TLS, SOAP, XML Signature, OpenAPI, JSON e PostgREST são padrões técnicos de implementação ou de documentação. Eles não criam, sozinhos, base legal, autorização de órgão, autenticidade de dado ou validade de ato administrativo.

## 3. Mapa do ecossistema e dos estados de acesso

### 3.1 gov.br e Conecta gov.br

O gov.br deve ser dividido em pelo menos três superfícies diferentes:

1. **Login Único / identidade:** autenticação de usuário por fluxo de autorização. O roteiro oficial exige HTTPS, `state`, `nonce`, PKCE, URI de retorno cadastrada e separação entre `access_token` (autorização) e `id_token` (identificação). A própria documentação recomenda guardar tokens no backend e manter sessão própria da aplicação. [13]
2. **Assinatura eletrônica gov.br:** serviço sujeito ao nível de assinatura aplicável ao ato. O fato de um usuário ter conta ou selo de confiabilidade não transforma toda operação em assinatura qualificada ICP-Brasil. [11] [3]
3. **Conecta gov.br:** interoperabilidade governo-a-governo, mediante catálogo, adesão, finalidade, credenciais, IP e autorização. Não deve ser modelado como API aberta para empresas privadas. [1] [2] [3]

**Requisito:** o produto deve guardar `surface_type` (`login`, `signature`, `conecta_data_api`) e impedir que a identidade do usuário seja apresentada como autorização de dados ou como assinatura do documento.

### 3.2 Transferegov e SICONV legado

O Transferegov.br é a evolução da Plataforma +Brasil e do SICONV. O histórico oficial informa que o SICONV começou em 2008 para o ciclo de convênios, contratos de repasse e termos de parceria; a Plataforma +Brasil foi criada em 2019 para abranger outros tipos de transferência; em 2022, a Plataforma +Brasil passou a se chamar Transferegov.br. [14]

Logo, “SICONV” é principalmente uma referência histórica e de registros legados. Para o produto, a regra deve ser: **não criar um falso provedor SICONV atual**. Dados antigos podem ser importados como registros históricos, com fonte e identificador original; novas integrações devem ser avaliadas contra o módulo e a API vigentes do Transferegov.

O Transferegov mantém APIs de integração direcionadas sobretudo a sistemas da Administração Pública Federal, Distrital, Estadual e Municipal. A página de APIs diferencia integração de sistemas e painéis de acesso livre para dados das transferências. [15]

Em julho de 2026, o Transferegov publicou novo ambiente de **APIs de Dados Abertos**, começando por Gestão de Parcerias e Transferências Especiais e por arquivos CSV do módulo Discricionárias e Legais. A própria página publicou um cronograma incremental: atos preparatórios entre julho e outubro de 2026; instrumentos entre novembro de 2026 e fevereiro de 2027; execução financeira entre março e junho de 2027; obras entre julho e outubro de 2027. Isso indica que a cobertura está em expansão e não autoriza dizer que todo o Transferegov está disponível por uma API pública. [16]

A documentação pública das Transferências Especiais expõe API em HTTPS, modelos estruturados e operadores de filtro/ordenação. Ela não apresenta, no trecho consultado, uma política geral de rate limit; o produto deve tratar o limite como **desconhecido até contrato ou documentação específica**. [16] [17]

A API de integração legada documentada no manual v1.16 separa validação, homologação e produção. Validação não exige token, não persiste dados e retorna objetos de teste; homologação e produção exigem token específico. As chamadas usam `Authorization: Bearer`; o manual documenta códigos 400, 401, 422 e 500 e descreve que o acesso depende de cadastro prévio pelo Ministério. O manual também registra a dependência do número do instrumento do módulo SICONV em operação, o que reforça que uma API histórica não deve ser tratada como contrato universal atual. [17]

### 3.3 PNCP

O PNCP é o sítio oficial criado pela Lei nº 14.133/2021 para centralizar informações de contratações. O fornecimento das informações é responsabilidade dos órgãos e entidades que realizam compras ou contratos; o portal oferece consulta pública e integração de plataformas. [18]

A consulta ao PNCP é pública. As APIs de manutenção — inserção, retificação e exclusão — exigem autenticação/autorização. O manual v2.6 informa que a plataforma que envia dados deve ser credenciada pelo Ministério da Gestão e da Inovação em Serviços Públicos, guardar as credenciais e usar login e senha para obter JWT com validade de uma hora. A plataforma informa os CNPJs que representa e assume responsabilidade jurídica pelos equívocos do envio. [19]

O manual v2.6 está datado de 31/08/2026 e seu histórico de versões deve ser tratado como parte do contrato técnico: schemas e endpoints podem evoluir. O manual documenta limites de payload, como pelo menos um item e no máximo 1.000 itens para PCA e no máximo 2.000 itens em determinadas contratações, além de respostas 400, 422 e 500. [19]

Não foi localizada no manual consultado uma política geral de requisições por minuto equivalente à do Portal da Transparência. Portanto, `rate_limit_pncp = unknown` deve permanecer no catálogo até ser confirmado com o PNCP; não se deve inventar uma quota.

### 3.4 Portal da Transparência

A API do Portal da Transparência é uma API REST para consulta dos mesmos dados disponíveis nas telas, sem necessidade de robôs. O cadastro de e-mail gera um token para as consultas. A documentação recomenda API para consultas pontuais e planilhas de dados abertos para grandes volumes. [21]

A restrição oficial publicada é de **400 requisições por minuto entre 6h e 23h59** e **700 requisições por minuto entre 0h e 5h59**. Esse limite é da API do Portal, não uma regra para todos os serviços de governo. [21]

A integração deve ser somente de leitura, com token fora de logs, cache controlado e preferência por downloads incrementais ou planilhas para cargas extensas. Como os dados da API são os mesmos exibidos em tela, a fonte é boa para consulta e cruzamento, mas o produto deve guardar data de atualização, origem, filtro e limitações da fonte.

### 3.5 eSocial, somente se houver caso de uso trabalhista

O eSocial não é uma API genérica de governança de OSCs ou de projetos. Deve entrar no escopo somente se o produto realmente tratar eventos trabalhistas e tiver controlador, finalidade e operador definidos.

A documentação técnica do eSocial exige Web Services em HTTPS/TLS com autenticação mútua, SOAP 1.1 e XML. O certificado deve ser emitido por AC credenciada na ICP-Brasil, série A, tipo A1 ou A3, como e-CPF/e-PF ou e-CNPJ/e-PJ. Os documentos são assinados por XML Digital Signature, com RSA/SHA-256 e canonicalização indicada no manual. [23]

A Produção Restrita serve para testes funcionais, não tem efeito jurídico, limita vínculos por empregador e não é ambiente de carga ou performance. A página oficial indica URLs específicas de envio e consulta e separa a Produção Restrita da produção efetiva. [22]

**Implicação de produto:** não reutilizar o adapter REST de `government_api` para eSocial. Seria necessário adapter SOAP/XML próprio, mTLS, gestão de certificado, assinatura de evento, consulta assíncrona, controle de schema e evidência de ambiente. No release atual, eSocial permanece `não iniciado / fora do escopo`, salvo aprovação de um caso de uso específico.

## 4. INTEGRATION_ARCHITECTURE — arquitetura proposta para governo

A arquitetura interna já é adequada como fundação: o núcleo não conhece fornecedor; cada fornecedor é adapter atrás de contratos canônicos; o hub centraliza jobs, IDs externos, mapeamento, saúde, auditoria, outbox, entrada e exportação. [27]

```text
Núcleo IMPACTO
  projetos · organizações · documentos · contratos · indicadores · evidências
       │ contrato canônico + proveniência + autorização de finalidade
       ▼
Integration Hub
  catálogo · data contracts · credenciais · jobs · idempotência · rate budget
  auditoria · saúde · retries · circuit breaker · conflitos · retenção
       │
       ├── govbr_login / govbr_signature       (identidade e assinatura; separado)
       ├── conecta_data_api                    (G2G, adesão e IP allowlist)
       ├── transferegov_open_data              (pull público, por módulo e versão)
       ├── transferegov_maintenance            (pull/push autorizado, se aprovado)
       ├── pncp_public_query                   (consulta pública)
       ├── pncp_maintenance                   (push/retificação autorizado)
       ├── transparencia_api                   (pull tokenizado + bulk)
       └── esocial_soap                       (condicional; mTLS + XMLDSig)
```

### 4.1 Contratos internos obrigatórios

Cada conexão deve conter:

- organização titular da conexão, órgão/provedor, ambiente, finalidade específica, base legal declarada e papel controlador/operador;
- URL de documentação, endpoint efetivo, versão de API/schema, versão do adapter, data da última verificação e prazo de revisão;
- tipo de credencial, escopos, CNPJs/entes autorizados, certificado e validade, IPs autorizados e ambiente;
- limite de taxa conhecido, fonte do limite, janela, resposta esperada para 429/503 e orçamento local de chamadas;
- política de paginação, cursor, ordenação, idempotência, retificação, exclusão e reconciliação;
- campos pessoais, dados sensíveis, retenção, exportação, compartilhamento e canal de incidente;
- contato oficial, procedimento de suporte, janela de indisponibilidade, versão e changelog do provedor;
- evidência: request/response redigidos, status HTTP, hash do payload, `correlation_id`, timestamp e resultado do teste.

O `data_contract_id` deve ser uma entidade própria e versionada. Atualizar schema, finalidade, conjunto de campos ou interpretação sem criar nova versão invalida a evidência anterior.

### 4.2 Política de autorização e ambientes

O estado da conexão deve ser monotônico e explícito:

`draft → purpose_review → access_requested → approved → sandbox_or_homologation → homologated → production_active → paused/revoked`.

Nenhum job de leitura ou escrita pode executar se a autorização externa não estiver no estado compatível com o ambiente. `technically_ready` significa somente que a configuração interna passou; não significa que o órgão autorizou. A promoção para produção deve criar conexão e credencial próprias, nunca “promover” o segredo de homologação no lugar.

### 4.3 Resiliência e rate limits

O cliente resiliente existente já prevê timeout, retries limitados, jitter, disjuntor e trabalho fora da requisição. Para governo, acrescentar:

- rate budget por provedor, conexão, órgão e endpoint, com relógio monotônico e fila;
- respeitar `Retry-After` quando publicado; tratar 429 como temporário, mas não repetir em avalanche;
- separar 401/403 (credencial ou autorização) de 400/422 (payload ou regra de negócio);
- não inferir que ausência de 429 significa ausência de limite;
- circuit breaker que proteja o serviço público e não apenas a IMPACTO;
- backfill de dados grandes por bulk/download, nunca por varredura agressiva da API;
- métricas de chamada, taxa de erro, latência, volume, freshness e atraso de ingestão sem registrar token, CPF, XML bruto ou corpo pessoal.

### 4.4 Identidade, autenticidade e certificados

Autenticação do usuário, autorização de sistema, assinatura de documento e autenticidade de dado são objetos diferentes:

- `user_authenticated`: usuário foi autenticado pelo provedor;
- `client_authorized`: sistema recebeu credencial e autorização para uma API;
- `payload_integrity`: transporte e/ou assinatura permitiram detectar alteração;
- `source_attested`: o órgão respondeu por canal oficial e a resposta foi preservada;
- `document_signed`: documento possui assinatura conforme nível exigido;
- `content_truth`: afirmação substantiva foi validada por procedimento competente.

Somente os quatro primeiros podem ser derivados de uma chamada técnica. `content_truth` exige regra ou fonte de validação própria. A ICP-Brasil é uma cadeia hierárquica de confiança, supervisionada pelo ITI, que permite emissão de certificados digitais; sua existência não torna qualquer integração da IMPACTO certificada. [12]

## 5. CAPABILITY_MATRIX — capacidades e estado real

A tabela abaixo combina a capacidade publicada pelo órgão com o estado verificável do release. **“Disponível no órgão” não significa “ligado na IMPACTO”.**

| Superfície | Leitura/consulta | Escrita/retificação | Autenticação/condição | Estado v0.26.0 | Decisão de produto |
|---|---|---|---|---|---|
| Login gov.br | identidade do usuário, conforme escopos | não é API de dados | OAuth/OIDC, HTTPS, state, nonce, PKCE, redirect cadastrado | `CONTRACT_TESTED` só contra IdP dublê; real não homologado | manter separado de dados e assinatura |
| Assinatura gov.br | validação conforme serviço e nível aplicável | assinatura de ato/documento | conta/selo ou mecanismo aceito pelo serviço; nível jurídico depende do ato | `BLOCKED_EXTERNAL`; não há assinatura gov.br/ICP ligada | não exibir “assinatura qualificada” |
| Conecta gov.br | APIs de órgãos, após adesão; algumas sem homologação | depende da API e do papel do órgão | cadastro, finalidade, assinaturas, aprovação, credencial, IP | `SCAFFOLDED`; `government_api` recusa ação sem autorização | primeiro adapter read-only e órgão parceiro definido |
| Transferegov Dados Abertos | API pública por módulo e CSV, com cobertura incremental | não confundir com API de manutenção | documentação/endpoint por módulo; limite geral não identificado | `NOT_CONNECTED`; nenhum endpoint real testado | snapshot, paginação e proveniência por módulo |
| Transferegov integração | consulta/atualização para sistemas autorizados | sim, por operação e módulo | bearer token, cadastro e ambiente; manual antigo separa validação/homologação/produção | `BLOCKED_EXTERNAL` | não chamar SICONV legado como API atual |
| SICONV legado | registros históricos, se fonte oficial permitir | não criar/alterar registros legados | contrato e fonte oficial específica | `NOT_IMPLEMENTED` | somente importação histórica read-only e rotulada |
| PNCP consulta | pública, contratações, PCA, editais, atas e contratos | não | consulta pública | `NOT_CONNECTED` | pull público com freshness e versão do manual |
| PNCP manutenção | dados de publicação, retificação e exclusão | sim, mas só com credenciamento/autorização | login/senha para JWT de 1h; CNPJs/entes autorizados | `BLOCKED_EXTERNAL` | escrita exige aprovação do órgão e trilha jurídica |
| Portal da Transparência API | consultas REST tokenizadas; bulk por planilha | não | e-mail cadastrado gera token | `NOT_CONNECTED` | somente leitura; 400/700 rpm; preferir bulk |
| eSocial | consulta de eventos e retornos | transmissão de eventos trabalhistas | WS SOAP, HTTPS/mTLS, ICP-Brasil A1/A3, XMLDSig | `OUT_OF_SCOPE`; nenhum adapter | só iniciar com caso de uso e certificado reais |

O catálogo deve permitir `unknown` como valor legítimo. Por exemplo, o rate limit geral do PNCP e do novo ambiente de dados abertos do Transferegov não foi encontrado na documentação consultada; não deve ser preenchido com um número estimado.

## 6. PROVIDER_GUIDE — guia de provedor e contrato de dados

Antes de implementar adapter, o responsável deve completar a ficha abaixo e anexar evidências. A ficha é requisito de produto, não apenas documentação de engenharia.

### 6.1 Ficha mínima

1. **Provedor e fonte:** órgão, sistema, módulo, URL oficial, responsável, título e data da documentação.
2. **Finalidade:** serviço público ou processo interno que justifica a chamada; finalidade proibida e usos secundários.
3. **Atores LGPD:** controlador, operador, suboperador, órgão cedente, órgão recebedor, encarregado e canal do titular.
4. **Dados:** campos, tipos, identificadores, dados pessoais/sensíveis, unidade, semântica, código de domínio e transformação.
5. **Contrato:** versão do schema, OpenAPI/WSDL, endpoint por ambiente, método, paginação, lote, cursor, idempotência, ordenação e changelog.
6. **Acesso:** credencial, escopo, certificado, mTLS, CNPJ/ente autorizado, IP allowlist, validade, rotação, revogação e recuperação.
7. **Operação:** rate limit, `Retry-After`, timeout, manutenção, SLA publicado ou ausência de SLA, suporte, contato e janela.
8. **Proveniência:** data de publicação, data de atualização, data de coleta, query/filtro, payload hash, status, resposta e confirmação de fonte.
9. **Retenção:** prazo do payload bruto, campos derivados, logs, tokens, certificado, auditoria, dead-letter e cópia de backup.
10. **Evidência:** teste em ambiente oficial, conta utilizada, escopo, request/response redigido, resultado, data e responsável.

### 6.2 Regras por família

- **Conecta:** anexar pedido de adesão, finalidade, assinatura do dirigente de TI e responsável técnico, aprovação do órgão cedente, IPs liberados, credencial e ambiente. A empresa privada não pode ser cadastrada como consumidor direto sem base oficial que permita isso.
- **Transferegov:** identificar módulo (`Gestão de Parcerias`, `Transferências Especiais`, `Discricionárias e Legais`, `Obras`) e se é API de dados abertos ou API de integração. Guardar número do instrumento e, quando for legado, `legacy_system = SICONV` sem afirmar que o endpoint é atual.
- **PNCP:** separar consumidor público da plataforma privada prestadora de serviço. Para manutenção, guardar credenciamento, CNPJs autorizados, JWT emitido/expirado e prova de responsabilidade do remetente. A plataforma privada não deve usar `entesAutorizados` sem observar a restrição documentada desde 18/08/2025. [19]
- **Portal da Transparência:** token somente para leitura, sem tentativa de escrita; orçamento de chamadas por janela; bulk para grandes volumes; fonte e atualização por consulta.
- **eSocial:** certificado em cofre externo ou módulo de chave apropriado, mTLS e rotação; nunca guardar chave privada em log, payload, teste ou resposta; separar Produção Restrita de produção efetiva e impedir que teste gere claim jurídico.

### 6.3 Contrato de dados proposto

O contrato de dados da IMPACTO deve conter `contract_id`, `version`, `provider`, `dataset`, `schema_url`, `legal_basis`, `specific_purpose`, `controller`, `operator`, `allowed_fields`, `prohibited_fields`, `refresh_policy`, `retention`, `quality_rules`, `rate_policy`, `security_profile`, `incident_contact`, `effective_at`, `supersedes`, `evidence_uri` e `status`.

A alteração de finalidade, escopo de campos, órgão cedente, endpoint ou interpretação semântica deve criar nova versão e reabrir a aprovação. O hash do schema e dos termos deve ser guardado, seguindo a lógica já adotada pelo release para documentos versionados; isso é **hipótese de produto**, não obrigação específica de um órgão.

## 7. Requisitos de dados

### 7.1 Identificadores e chaves

- CNPJ pode ser chave de órgão, entidade, plataforma ou fornecedor, mas deve preservar máscara/normalização e fonte.
- CPF somente deve ser usado quando indispensável à finalidade e autorizado; para painéis de impacto, preferir agregação, contagem e k-anonimato.
- Guardar chaves nativas do sistema: número do instrumento Transferegov, identificadores do PNCP, código de unidade compradora, código IBGE, identificador do evento e versão do schema.
- Nunca substituir o ID interno pelo externo. Manter tabela de correspondência, versão, origem, conflito, data e estado (`linked`, `stale`, `conflict`, `deleted_externally`). Essa regra já existe na arquitetura interna. [27]

### 7.2 Proveniência e freshness

Todo registro importado deve guardar, no mínimo:

```json
{
  "source_system": "PNCP|Transferegov|PortalTransparencia|Conecta|eSocial",
  "source_org": "órgão cedente",
  "dataset": "nome do conjunto",
  "endpoint": "URL sem segredo",
  "request_fingerprint": "hash da requisição sem token",
  "external_id": "id nativo",
  "schema_version": "versão",
  "published_at": "quando a fonte publicou",
  "source_updated_at": "quando a fonte atualizou",
  "fetched_at": "quando a IMPACTO coletou",
  "http_status": 200,
  "payload_sha256": "hash do payload preservado",
  "quality_status": "received|validated|partial|stale|rejected",
  "evidence_level": "source_response|cross_checked|human_validated"
}
```

`fetched_at` nunca deve ser apresentado como `source_updated_at`. Ausência de data não significa “atual”. Dado indisponível, atrasado, parcial ou não verificável deve permanecer nesses estados; nunca virar zero ou “validado”.

### 7.3 Minimização e transparência

O envio a terceiro deve usar allowlist de campos e finalidade. Proibir payload livre baseado em `SELECT *`. O usuário deve poder ver qual organização, API, finalidade, campo e data de acesso foram utilizados. A LGPD exige transparência da finalidade pública e do procedimento; a ANPD recomenda registro formal, duração e divulgação compreensível do compartilhamento. [9] [10]

Para a torre de governo, a saída padrão deve ser agregada. Se uma API retornar CPF, benefício, remuneração, dado de saúde ou dado trabalhista, o dado não entra automaticamente na ficha de projeto. É necessário decidir finalidade, base, retenção, acesso, risco e eventual RIPD.

## 8. Testes e controles de aceitação

### 8.1 Antes de qualquer chamada oficial

- validar que o órgão e a organização estão autorizados;
- validar finalidade, base legal, controlador/operador e data de vigência;
- validar ambiente, endpoint oficial, certificado, IP e escopo;
- comprovar que o adapter não chama produção em modo de teste;
- executar health check somente leitura;
- registrar evidência redigida e hash, sem segredo ou dado pessoal desnecessário.

### 8.2 Testes técnicos por provedor

- **Gov.br/OIDC:** redirect exato, state, nonce, PKCE, code de uso único, expiração, sessão local e separação de ID/access token. [13]
- **Conecta:** rejeição sem adesão, rejeição com finalidade ausente, validade de credencial, IP não liberado, ausência de homologação, revogação e limite de consumo. [2] [3] [4]
- **Transferegov:** Bearer ausente/inválido, 400 estrutural, 401 autorização, 422 regra de negócio, paginação/filtro, idempotência de instrumento, separação entre validação/homologação/produção e perda de conexão. [17]
- **PNCP:** JWT expirado, CNPJ não autorizado, payload fora do limite, schema de manual atual, 400/422, retificação concorrente, reenvio idempotente e auditoria do remetente. [19]
- **Portal da Transparência:** token ausente, 401/403, respeito às janelas 400/700 rpm, backoff em 429, paginação, bulk e distinção de data de atualização. [21]
- **eSocial:** cadeia ICP, mTLS, assinatura XMLDSig, certificado expirado/revogado, schema inválido, `tpAmb=2` em Produção Restrita, retorno assíncrono, consulta de lote e bloqueio de claim jurídico no ambiente de testes. [22] [23]

### 8.3 Controles transversais

A suíte existente já cobre SSRF, XXE, injeção XML, HMAC, replay, vazamento de segredo, isolamento de tenant, idempotência concorrente, retries, disjuntor e trabalho assíncrono. [28] [29] Para governo, acrescentar:

1. teste de autorização externa: sem evidência, nenhum adapter executa;
2. teste de data contract: schema/finalidade vencidos bloqueiam ingestão;
3. teste de freshness: fonte sem atualização não recebe selo “atual”;
4. teste de rate budget: nenhum retry ignora quota ou `Retry-After`;
5. teste de proveniência: todo valor público exibe fonte, data e nível de evidência;
6. teste de conflito: dados divergentes não são sobrescritos silenciosamente;
7. teste de retenção e eliminação: logs, payload, token, certificado e dead-letter obedecem prazo aprovado;
8. teste de incidente: revogação de credencial e chave interrompe chamadas e marca a conexão como `revoked`;
9. teste de auditoria: quem aprovou, em nome de qual organização, qual finalidade e qual ambiente;
10. teste de publicação: `PUBLIC_VERIFICATION` nunca afirma “oficial”, “verdadeiro”, “validado pelo governo” ou “ICP-Brasil” sem evidência específica.

## 9. PUBLIC_VERIFICATION — o que pode ser verificado publicamente

A página pública pode mostrar:

- sistema de origem e órgão cedente informado no contrato de dados;
- identificador externo, dataset, versão do schema, data de coleta e data declarada pela fonte;
- hash do payload ou do documento preservado;
- estado da conexão no momento da coleta;
- nível de evidência (`resposta da fonte`, `checagem cruzada`, `validação humana`);
- eventuais lacunas, atraso, erro parcial ou revogação da conexão.

A página **não deve** mostrar token, certificado, chave privada, CPF integral, XML bruto, endereço IP ou campos pessoais desnecessários. O resultado precisa dizer “a IMPACTO recebeu esta resposta da fonte X em tal data”, não “o governo garante que esta afirmação é verdadeira”. Isso segue a limitação já registrada na verificação pública da plataforma. [30]

Para um documento que tenha sido assinado fora da IMPACTO, o produto pode verificar assinatura segundo o mecanismo contratado e preservar o resultado, mas deve identificar o tipo: simples, avançada, qualificada ICP-Brasil, ou outro. Sem serviço oficial de validação e evidência de cadeia, não usar “assinatura válida” como sinônimo de “conteúdo verdadeiro”. A Lei nº 14.063 diferencia os níveis. [11]

## 10. Claims proibidos

Enquanto não houver evidência externa específica, são proibidas as seguintes afirmações em tela, marketing, contrato, API, release note ou atendimento:

- “A IMPACTO é integrada ao gov.br, Conecta gov.br, Transferegov, PNCP, Portal da Transparência ou eSocial.”
- “Integração homologada”, “produção ativa”, “credenciada” ou “autorizada pelo órgão” com base apenas em mock, FakeTransport, documentação lida ou endpoint público.
- “O Conecta está disponível para empresas privadas” como consumidor direto.
- “SICONV é o sistema atual” ou “a plataforma está conectada ao SICONV” sem fonte e módulo histórico identificados.
- “Consulta pública do PNCP autoriza publicar, corrigir ou excluir dados.”
- “Token Bearer, login gov.br ou selo Prata/Ouro é certificado ICP-Brasil.”
- “Documento oficial”, “fé pública”, “assinatura qualificada”, “autenticidade governamental” ou “não repúdio” sem a cadeia e o nível jurídico aplicáveis.
- “Conforme a LGPD”, “LGPD compliant” ou “compartilhamento legal” sem base legal, finalidade, controlador, operador, registro, retenção e revisão.
- “Dados em tempo real”, “dados completos”, “dados validados” ou “ausência de fraude” sem definição de freshness, cobertura e método de validação.
- “Rate limit de X requisições” para PNCP, Transferegov ou Conecta quando a documentação específica não publicar a quota.
- “eSocial testado em produção” quando a evidência for Produção Restrita; a Produção Restrita não tem efeito jurídico e não serve para teste de carga.
- “A verificação pública prova a verdade do conteúdo.” Ela prova a integridade e o registro que a IMPACTO conseguiu preservar, não a verdade substantiva. [30]

## 11. Mapa de obrigações e controles do produto

| Fonte/obrigação | Quem deve cumprir | Requisito para a IMPACTO | Controle/evidência | Estado |
|---|---|---|---|---|
| Lei 13.726: racionalização e dispensa de documento repetido | Poder Público | não pedir ao usuário documento que possa ser obtido por integração legalmente disponível | finalidade, órgão cedente, trilha de consulta e fallback por declaração | vigente; produto pendente |
| Lei 14.129: dados legíveis por máquina, semântica, qualidade, integridade e histórico | órgãos abrangidos | armazenar schema, qualidade, atualização, histórico e fonte; não vender “API” sem contrato | data contract, source snapshot, quality status | vigente; fundação parcial |
| Lei 14.129: interoperabilidade com segurança e LGPD | órgãos gestores; parceiros devem respeitar | autorização por finalidade, minimização, segurança, custo e acesso auditável | policy gate, RLS, auditoria, logs redigidos | vigente; controle técnico parcial |
| LGPD arts. 23, 25, 26, 37, 39, 40 e 46 | controlador/operador | finalidade pública, base legal, formalização, registro, segurança, interoperabilidade e direitos | processo/registro, contrato de dados, DPO, retenção, incidente | vigente; decisão jurídica pendente |
| Guia ANPD: formalização, duração, transparência e responsabilidade | órgãos e entidades como orientação | contrato/convênio/ato ou decisão; publicar informação compreensível; definir controlador/operador | `data_contract`, aprovação e página pública | orientação; implementar |
| Lei 14.063: nível de assinatura | ente e partes do ato | guardar tipo de assinatura e não elevar o claim | verificador e metadata de cadeia | vigente; assinatura gov.br/ICP bloqueada |
| ePING | órgãos Sisp; demais adoção facultativa | priorizar padrões abertos e documentar exceção de legado | checklist de contratação/adapter | padrão administrativo |
| Conecta: adesão, finalidade, assinaturas, credencial e IP | órgão recebedor/cedente | impedir acesso direto sem aprovação e expor ambiente | evidência de adesão, IP, credencial, health check | não iniciado |
| PNCP: divulgação no portal; manutenção autenticada | órgão e plataforma autorizada | separar consulta pública de escrita em nome de órgão | credenciamento, JWT 1h, CNPJ autorizado, logs de envio | não conectado |
| Portal Transparência: token e 400/700 rpm | consumidor da API | controlar quota, preferir bulk, proteger token | rate budget e bulk job | não conectado |
| Transferegov: APIs por módulo e autorização | órgão/sistema autorizado | distinguir dados abertos, integração e legado | módulo, versão, ambiente, token e suporte | não conectado |
| eSocial: mTLS, ICP, XMLDSig e ambiente sem efeito jurídico | empregador/sistema transmissor | somente caso de uso aprovado; adapter próprio | certificado, assinatura, tpAmb, retorno | fora do escopo |

## 12. Lacunas, decisões e próximos passos

1. **Definir o primeiro caso de uso público:** leitura de contratos/transferências, consulta de contratações ou integração de identidade. Não iniciar por “governo” genérico.
2. **Escolher órgão, módulo e ambiente:** Conecta, Transferegov e PNCP têm superfícies e autorizadores distintos; não há um credenciamento único.
3. **Nomear controlador, operador e encarregado:** a LGPD e o guia da ANPD exigem uma decisão documentada; a minuta atual ainda tem pendências de DPO e base legal. [9] [10] [31]
4. **Criar registro de contrato de dados:** finalidade, campos, versão, retenção, qualidade, rate limit e evidência.
5. **Separar adapters governamentais:** `conecta`, `transferegov_open_data`, `transferegov_maintenance`, `pncp_query`, `pncp_maintenance`, `transparencia_api`; não manter tudo em `government_api` genérico.
6. **Implementar governança de autorização:** bloquear produção, exibir estado de adesão e impedir “maturity promotion” sem evidência externa.
7. **Confirmar limites ausentes:** obter documentação ou contato oficial para quotas do PNCP, Transferegov Dados Abertos e cada API Conecta; registrar `unknown` até lá.
8. **Adicionar freshness e proveniência:** separar data da fonte, coleta e validação, com hash e nível de evidência.
9. **Decidir se eSocial é necessário:** se não houver evento trabalhista no produto, manter fora do release; se houver, fazer projeto próprio de certificado/mTLS/SOAP.
10. **Atualizar release e telas:** README, `LEGAL_FRAMEWORK.md`, `INTEGRATION_CAPABILITY_MATRIX.md`, `PUBLIC_VERIFICATION.md` e telas de conexão devem repetir “não conectado” e “autorização externa necessária”.
11. **Executar homologação real por um provedor de cada vez:** conta de sandbox/homologação, teste oficial, teste de erro e observabilidade; só depois promover estado.
12. **Fazer teste de carga antes de produção:** a suíte atual não mede volume real, rate limit de órgão, concorrência de chamadas ou tamanho de backfill. [29]

## 13. Registro de fontes

| Ref. | Órgão/autor | Título | Data | O que sustenta |
|---|---|---|---|---|
| [1] | Secretaria de Governo Digital/MGI | Conecta gov.br | página consultada em 08/10/2026; data de publicação não indicada | finalidade, G2G, limites de uso por cidadãos/empresas e relação com Leis 13.726 e 14.129 |
| [2] | Secretaria de Governo Digital/MGI | Quero acessar as APIs do Conecta | página consultada em 08/10/2026 | cadastro, dirigente de TI, responsável técnico, adesão, aprovação e ambientes |
| [3] | Secretaria de Governo Digital/MGI | Quero acessar os serviços do Conecta | página consultada em 08/10/2026 | credenciais, conta gov.br/ICP, IP allowlist, suspensão e gerenciador |
| [4] | Secretaria de Governo Digital/MGI | Regras de usabilidade do Conecta gov.br | página consultada em 08/10/2026 | volumetria acima de 500 mil, revisão e suspensão por inatividade |
| [5] | Secretaria de Governo Digital/MGI | Catálogo das APIs governamentais | página consultada em 08/10/2026 | APIs catalogadas, versionadas, monitoradas e categorias |
| [6] | Secretaria de Governo Digital/MGI | Padrões de Interoperabilidade — ePING | publicado 28/11/2019; atualizado 04/09/2026 | alcance obrigatório para Sisp, adoção facultativa fora dele e padrões abertos |
| [7] | Presidência da República | Lei nº 13.726/2018 | 08/10/2018 | racionalização, dispensa e não exigência de documentos repetidos |
| [8] | Presidência da República | Lei nº 14.129/2021 — Governo Digital | 2021 | dados abertos, semântica, qualidade, histórico, interoperabilidade e segurança |
| [9] | Presidência da República | Lei nº 13.709/2018 — LGPD | 14/08/2018, texto atualizado | bases, Poder Público, interoperabilidade, compartilhamento, registros e segurança |
| [10] | ANPD | Guia orientativo Tratamento de dados pessoais pelo Poder Público | publicado 22/11/2024; modificado 23/01/2025 | formalização, processo, finalidade, base legal, duração, transparência e papéis |
| [11] | Presidência da República | Lei nº 14.063/2020 — Assinaturas eletrônicas | 23/09/2020 | níveis simples, avançada e qualificada e exigência conforme ato |
| [12] | ITI | ICP-Brasil | atualizado 07/05/2025 | cadeia hierárquica, AC-Raiz, certificados e supervisão |
| [13] | Secretaria de Governo Digital/MGI | Passo-a-passo para integrar o Login Único gov.br | página consultada em 08/10/2026 | HTTPS, state, nonce, PKCE, tokens, redirect e sessão própria |
| [14] | Ministério da Gestão e da Inovação | Sobre o Transferegov.br — Evolução da Plataforma +Brasil | publicado 30/01/2023; modificado 03/07/2025 | histórico SICONV → +Brasil → Transferegov e Decreto 11.271/2022 |
| [15] | Ministério da Gestão e da Inovação | APIs de integração ao Transferegov.br | página consultada em 08/10/2026 | público-alvo das APIs e separação de painéis de acesso livre |
| [16] | Ministério da Gestão e da Inovação | API de Dados Abertos Transferegov.br | publicado 10/07/2026; modificado 13/07/2026 | novo ambiente, módulos iniciais, CSV, cronograma e cobertura incremental |
| [17] | Ministério da Gestão e da Inovação | Manual da Integração da API Transferegov — v1.16 | manual legado com revisões registradas até 2022 | ambientes, bearer token, validação sem persistência, homologação/produção e erros |
| [18] | Comitê Gestor da RNCP/MGI | Portal Nacional de Contratações Públicas | página consultada em 08/10/2026 | finalidade, responsabilidade dos órgãos, consulta e integração |
| [19] | PNCP/MGI | Manual de Integração do PNCP — v2.6 | 31/08/2026 | consulta pública, manutenção autenticada, JWT 1h, CNPJs, limites de payload e erros |
| [20] | Presidência da República | Lei nº 14.133/2021 | 01/04/2021, texto atualizado | publicidade e divulgação no PNCP |
| [21] | Controladoria-Geral da União | API de Dados do Governo Federal — Portal da Transparência | página consultada em 08/10/2026 | token, REST, 400/700 rpm, consultas pontuais e bulk |
| [22] | Comitê Gestor eSocial | Produção Restrita — Ambiente de Testes | página consultada em 08/10/2026 | ausência de efeito jurídico, limite de vínculos, URLs e não uso para performance |
| [23] | Comitê Gestor eSocial | Manual de Orientação do Desenvolvedor eSocial v1.9 | 09/08/2020 | SOAP 1.1, HTTPS/mTLS, ICP-Brasil A1/A3, XMLDSig e SHA-256 |
| [24] | Projeto IMPACTO | README.md — Plataforma Impacto v0.26.0 | release v0.26.0 | estado fechado, não publicado, dependências externas e ausência de integrações reais |
| [25] | Projeto IMPACTO | INTEGRATION_CAPABILITY_MATRIX.md / config/integration_providers.json | estado do repositório v0.26.0 | `government_api` scaffolded, maturidade e capacidades internas |
| [26] | Projeto IMPACTO | SYSTEM_INTEGRATION_MATRIX.md / INTEGRATION_HOMOLOGATION_MATRIX.csv | estado do repositório v0.26.0 | BLOCKED_EXTERNAL, credenciais ausentes e testes de contrato |
| [27] | Projeto IMPACTO | INTEGRATION_ARCHITECTURE.md / INTEGRATION_PROVIDER_GUIDE.md | estado do repositório v0.26.0 | adapters, modelo canônico, jobs, IDs externos e regras de provedor |
| [28] | Projeto IMPACTO | INTEGRATION_SECURITY.md | estado do repositório v0.26.0 | SSRF, XXE, HMAC, replay, credenciais, RLS, rate limits locais e riscos |
| [29] | Projeto IMPACTO | INTEGRATION_TESTING.md | estado do repositório v0.26.0 | 76 testes, FakeTransport, escopo provado e limites de evidência |
| [30] | Projeto IMPACTO | PUBLIC_VERIFICATION.md | estado do repositório v0.26.0 | o que a verificação pública prova e o que não prova |
| [31] | Projeto IMPACTO | LEGAL_FRAMEWORK.md e LGPD.md | documentos existentes do release | minutas não vigentes, ausência de integrações, pendências de DPO, base legal e retenção |

## 14. Referências

[1]: https://www.gov.br/governodigital/pt-br/infraestrutura-nacional-de-dados/interoperabilidade/conecta-gov.br "Conecta gov.br"
[2]: https://www.gov.br/governodigital/pt-br/infraestrutura-nacional-de-dados/interoperabilidade/conecta-gov.br/quero-acessar-as-apis-do-conecta "Quero acessar as APIs do Conecta"
[3]: https://www.gov.br/governodigital/pt-br/infraestrutura-nacional-de-dados/interoperabilidade/conecta-gov.br/acessar-os-servicos-do-conecta "Quero acessar os serviços do Conecta"
[4]: https://www.gov.br/governodigital/pt-br/infraestrutura-nacional-de-dados/interoperabilidade/conecta-gov.br/regras-de-usabilidade-do-conecta-gov.br "Regras de usabilidade do Conecta gov.br"
[5]: https://www.gov.br/conecta/catalogo/ "Catálogo das APIs governamentais"
[6]: https://www.gov.br/governodigital/pt-br/infraestrutura-nacional-de-dados/interoperabilidade/padroes-de-interoperabilidade "Padrões de Interoperabilidade — ePING"
[7]: https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13726.htm "Lei nº 13.726, de 8 de outubro de 2018"
[8]: https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2021/lei/l14129.htm "Lei nº 14.129, de 29 de março de 2021"
[9]: https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm "Lei nº 13.709, de 14 de agosto de 2018 — LGPD"
[10]: https://www.gov.br/anpd/pt-br/centrais-de-conteudo/materiais-educativos-e-publicacoes/guia-poder-publico-anpd-versao-final.pdf/@@display-file/file "Guia orientativo Tratamento de dados pessoais pelo Poder Público"
[11]: https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2020/lei/l14063.htm "Lei nº 14.063, de 23 de setembro de 2020"
[12]: https://www.gov.br/iti/pt-br/assuntos/icp-brasil "ICP-Brasil"
[13]: https://acesso.gov.br/roteiro-tecnico/iniciarintegracao.html "Passo-a-passo para integrar o Login Único gov.br"
[14]: https://www.gov.br/transferegov/pt-br/sobre/transferegov "Sobre o Transferegov.br — Evolução da Plataforma +Brasil"
[15]: https://www.gov.br/transferegov/pt-br/sobre/apis-integracao "APIs de integração ao Transferegov.br"
[16]: https://www.gov.br/transferegov/pt-br/ferramentas-gestao/api-de-dados-abertos-transferegov.br "API de Dados Abertos Transferegov.br"
[17]: https://www.gov.br/transferegov/pt-br/comunicados/comunicados-gerais/2020/ManualdaIntegraodaAPITransferegovVerso1.16.pdf/@@download/file "Manual da Integração da API Transferegov — versão 1.16"
[18]: https://www.gov.br/pncp/ "Portal Nacional de Contratações Públicas"
[19]: https://pncp.gov.br/manual/pt-br/latest/singlehtml/ "Manual de Integração do PNCP — versão 2.6"
[20]: https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2021/lei/l14133.htm "Lei nº 14.133, de 1º de abril de 2021"
[21]: https://portaldatransparencia.gov.br/api-de-dados "API de Dados do Governo Federal — Portal da Transparência"
[22]: https://www.gov.br/esocial/pt-br/acesso-ao-sistema/ambiente-de-producao-restrita "Produção Restrita — Ambiente de Testes do eSocial"
[23]: https://www.gov.br/esocial/pt-br/documentacao-tecnica/manuais/manualorientacaodesenvolvedoresocialv1-9.pdf "Manual de Orientação do Desenvolvedor eSocial v1.9"
[24]: file:///home/ubuntu/impacto-trust-knowledge-v0.26.0/README.md "README do release Plataforma Impacto v0.26.0"
[25]: file:///home/ubuntu/impacto-trust-knowledge-v0.26.0/INTEGRATION_CAPABILITY_MATRIX.md "Matriz de capacidades de integração da IMPACTO"
[26]: file:///home/ubuntu/impacto-trust-knowledge-v0.26.0/docs/execution/SYSTEM_INTEGRATION_MATRIX.md "Matriz de integração sistêmica da IMPACTO"
[27]: file:///home/ubuntu/impacto-trust-knowledge-v0.26.0/INTEGRATION_ARCHITECTURE.md "Arquitetura de integração da IMPACTO"
[28]: file:///home/ubuntu/impacto-trust-knowledge-v0.26.0/INTEGRATION_SECURITY.md "Segurança da camada de integração da IMPACTO"
[29]: file:///home/ubuntu/impacto-trust-knowledge-v0.26.0/INTEGRATION_TESTING.md "Testes da camada de integração da IMPACTO"
[30]: file:///home/ubuntu/impacto-trust-knowledge-v0.26.0/PUBLIC_VERIFICATION.md "Verificação pública da IMPACTO"
[31]: file:///home/ubuntu/impacto-trust-knowledge-v0.26.0/docs/LEGAL_FRAMEWORK.md "Arcabouço legal e limitações declaradas da IMPACTO"
