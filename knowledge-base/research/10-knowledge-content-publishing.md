# Governança de conhecimento, publicação e acessibilidade

**Escopo pesquisado:** regras brasileiras sobre conteúdo oficial, direitos autorais, citações, revisão e atualização, acessibilidade digital, linguagem simples, SEO e responsabilidade por orientação. O recorte relaciona **KNOWLEDGE_HUB**, **KNOWLEDGE_DATA_MODEL**, **TRAINING_ACADEMY**, **PUBLICACAO**, **ACCESSIBILITY** e o assistente extrativo.

**Data do estado consultado:** 8 de outubro de 2026. Este documento é pesquisa informativa e requisito de produto; não é parecer jurídico personalizado, certificação de acessibilidade ou autorização para publicar conteúdo de terceiros.

## Escopo e classificação das fontes

A base deve separar cinco classes. Misturá-las faz uma recomendação administrativa parecer lei e faz uma hipótese editorial parecer fato.

1. **Lei ou regulamento vigente.** Inclui a Lei de Acesso à Informação (LAI), a Lei de Direitos Autorais, o Código de Defesa do Consumidor, a Lei Brasileira de Inclusão, a LGPD e a Política Nacional de Linguagem Simples. A obrigação depende do sujeito, do conteúdo e do contexto. A LAI e a Lei do Governo Digital têm incidência direta sobre a Administração Pública; a LAI alcança entidades privadas sem fins lucrativos que recebam recursos públicos somente na parcela e na destinação previstas em seu art. 2º. A LBI alcança, entre outros, sites mantidos por empresas com sede ou representação no Brasil.[1] [2] [3] [6]
2. **Orientação administrativa ou institucional.** eMAG, páginas do Governo Digital, guias da ENAP, Manual de Redação da Presidência e guia da ANPD orientam a implementação, mas não devem ser descritos como lei quando não houver ato que os incorpore ao caso concreto.[8] [9] [12] [15] [19]
3. **Padrão técnico voluntário, salvo adoção.** WCAG 2.2 e ABNT NBR 17225 são referências técnicas. Tornam-se requisito contratual, de edital, política interna ou regulamento quando forem adotados dessa forma. A conformidade WCAG é uma afirmação técnica que exige evidência da página inteira, não apenas de alguns componentes.[10] [11]
4. **Literatura e normalização acadêmica.** A ABNT NBR 10520:2023, divulgada em material institucional da FCEE, orienta a apresentação de citações e a rastreabilidade acadêmica; não cria, por si só, autorização autoral nem transforma uma página em fonte oficial.[16]
5. **Hipótese de produto.** Inclui pesos da busca, jornada editorial, prazo interno de revisão, classificação de risco, formato de resposta do assistente, meta WCAG 2.2 AA e escolha de campos de SEO. Deve ser marcado como decisão de produto, com proprietário e data de revisão, nunca como “exigência legal”.

## Estado atual do release que precisa ser corrigido

O v0.26.0 está tecnicamente fechado, mas não está pronto para alegar que oferece uma base pública, oficial, juridicamente revisada ou acessível em conformidade integral.

- O `README.md` informa que o release **não está publicado**, que Android/iOS não foram construídos e que provedores reais não estão ligados. Portanto, resultados de testes locais, staging ou seed não provam operação pública.
- O `KNOWLEDGE_HUB.md` informa que **não há conteúdo real publicado**: os 14 guias, 8 FAQs, 4 recursos, 1 curso e 1 evento do seed são `demo=true`, sem regras fiscal, jurídica ou de preço. O selo “Exemplo / rascunho — não é documento oficial” é correto e deve continuar sendo obrigatório.
- A busca, as jornadas e seus pesos são explicitamente hipóteses editoriais. O hub usa FTS, trigrama e sinônimos curados, sem embeddings. Isso é uma característica do produto, não uma prova de completude, neutralidade ou qualidade jurídica da recuperação.
- O assistente descrito no hub é **extrativo e ancorado**: somente devolve trechos de conteúdo publicado, cita fontes, marca revisão pendente e recusa quando não encontra informação suficiente. Esse desenho é adequado ao risco, mas precisa de uma trilha verificável de versão, fonte, trecho e estado de revisão para que a resposta não pareça uma orientação autônoma.
- O `KNOWLEDGE_DATA_MODEL.md` ainda se identifica como v0.12.0, assim como `TRAINING_ACADEMY.md`. O modelo contém bons controles — versões imutáveis, quatro olhos, fonte e data para conteúdo regulatório, histórico e RLS —, porém a identificação antiga pode induzir a leitura de que o documento é a especificação atual do v0.26.0. Deve ser reconciliada ou explicitamente marcada como histórico.
- O `docs/PUBLICACAO.md` é principalmente runbook de infraestrutura: banco, segredos, migrações, boot, smoke test, backup, observabilidade e portão das minutas jurídicas. Ele não é ainda um portão editorial completo que verifique direitos autorais, fonte, validade normativa, acessibilidade do documento, SEO, tradução, rebaixamento de conteúdo ou revisão por assunto.
- O `ACCESSIBILITY_REPORT.md` raiz é rotulado v0.18.1. Ele registra 12 verificações manuais positivas no Chromium, mas declara **axe-core, leitor de tela real, segundo navegador, zoom de texto a 200%, daltonismo e navegação por voz como não verificados**. O `README.md` relata que o v0.25.0 passou a travar axe-core no CI. Esses registros precisam apontar para o mesmo artefato e para a mesma versão antes de qualquer claim público. Até a reconciliação, a formulação segura é “subconjunto de verificações executadas”, não “conforme WCAG 2.2 AA”.
- O `docs/LEGAL_FRAMEWORK.md` informa que as onze minutas legais seguem em `draft` e que nenhum aceite deve ser registrado. O `docs/LGPD.md` também deixa pendentes base legal por tratamento, retenção definitiva, RIPD/DPIA, contratos com provedores e canal do encarregado. O produto não deve apresentar conteúdo jurídico ou política de privacidade como “aprovado” enquanto o próprio release diz o contrário.
- A academia já rotula o certificado como **não diploma nem certificação oficial/reconhecida pelo MEC**. Isso deve ser preservado. Há campos de legenda e transcrição para vídeos externos, mas a plataforma declara que não verifica se a legenda existe; o curso não deve ser chamado de acessível sem prova do ativo final.

**Correção de release recomendada:** congelar qualquer claim de “oficial”, “vigente”, “acessível”, “validado”, “certificado” ou “conforme” até que a publicação editorial seja tratada como um release separado, com evidências versionadas e responsabilidade nominal.

## Mapa de obrigações e efeitos

| Tema | Natureza e aplicabilidade | O que sustenta | Consequência para o IMPACTO |
|---|---|---|---|
| Informação oficial, integridade e atualização | A LAI é lei vigente. Para órgãos e entidades públicas, publicidade é regra, informação deve ser transparente, clara, primária, íntegra, autêntica e atualizada. O art. 8º, §3º exige pesquisa, formatos abertos, autenticidade, atualização e acessibilidade. Entidades privadas sem fins lucrativos que recebem recursos públicos entram no regime quanto à parcela e destinação desses recursos.[1] | O sistema precisa mostrar origem, data de verificação, estado, jurisdição e versão. Conteúdo sem fonte ou vencido não pode aparecer como oficial, atual ou regulatório. | Criar um `publication_gate` além do boot de infraestrutura. Conteúdo regulatório vencido deve ser rebaixado, não silenciosamente mantido como vigente. |
| Governo Digital e linguagem clara | A Lei nº 14.129/2021 estabelece princípios para a Administração Pública, incluindo serviços acessíveis, transparência, linguagem clara e compreensível, dados abertos e proteção de dados. A Lei nº 15.263/2025 institui a Política Nacional de Linguagem Simples para os órgãos e entidades da Administração Pública de todos os Poderes e entes; exige frases diretas e curtas, uma ideia por parágrafo, explicação de siglas, voz ativa, acessibilidade e teste com o público-alvo.[2] [3] | Para um produto privado, são referências e podem virar requisito contratual ou de projeto. Em fluxos destinados a órgão público, a aplicabilidade deve ser confirmada no contrato e no ente. | O editor deve ter campo de público-alvo e teste de compreensão. “Linguagem simples” não significa remover ressalvas jurídicas, fontes, condições ou exceções. |
| Acessibilidade web | A LBI torna obrigatória a acessibilidade de sites mantidos por empresas com sede ou representação no Brasil e por órgãos de governo. Também exige informação correta e clara em canais virtuais e recursos acessíveis em publicidade e divulgação; livros e publicações públicas devem ser produzidos em formatos acessíveis.[6] O Decreto nº 5.296/2004 contém a obrigação histórica para portais públicos; o prazo original não deve ser reapresentado como prazo atual.[7] | A obrigação legal não é satisfeita por uma declaração no rodapé. Acessibilidade deve existir no conteúdo, no documento baixável, na mídia, no fluxo e na interface. | Aplicar controles de acessibilidade a HTML, PDF/DOCX, vídeo, áudio, tabelas, imagens e formulários. Manter declaração de acessibilidade honesta e canal para barreiras. |
| eMAG | O eMAG 3.1 é orientação brasileira para sites governamentais e foi alinhado à WCAG, adaptado a prioridades locais. Ele orienta texto legível, uma ideia por parágrafo, frases curtas, explicação de siglas e tratamento de erros. O eMAG não deve ser apresentado como uma lei universal para todo site privado.[9] | É baseline administrativo útil para conteúdo público e contratação governamental, junto com a LBI e a LAI. | Adotar eMAG 3.1 como checklist editorial para conteúdos públicos, registrando onde a regra é legal e onde é orientação. |
| WCAG 2.2 | Padrão técnico do W3C. Tem quatro princípios, critérios de sucesso testáveis e níveis A, AA e AAA. A conformidade é da página completa, não de um componente isolado; AA exige todos os critérios A e AA aplicáveis. Técnicas são meios informativos e não substituem o critério.[10] | WCAG 2.2 AA pode ser meta contratual/produto, mas não deve ser afirmada sem testes automatizados e manuais suficientes. AAA não é meta geral recomendada pelo próprio W3C. | Definir escopo: páginas, estados, documentos, vídeos, autenticação e conteúdo incorporado. Guardar versão da WCAG, ambiente e evidência do teste. |
| ABNT NBR 17225 | Norma técnica brasileira lançada em 2025 para acessibilidade em conteúdo e aplicações web. A página da ABNT anuncia seu escopo, mas a norma completa é documento técnico sujeito a acesso/licença. Norma ABNT não é automaticamente lei.[11] | Pode ser adotada em contratação, política interna ou especificação. Não se deve alegar “conforme ABNT” apenas por usar alguns requisitos ou uma cópia não controlada. | Registrar edição/licença da norma adotada, escopo e auditoria. Se não houver auditoria integral, usar “meta baseada em” ou “itens verificados”, nunca “conforme”. |
| Direitos autorais | A Lei nº 9.610/1998 protege textos e outras obras exteriorizadas. Reprodução, edição, adaptação, tradução, distribuição e armazenamento dependem em regra de autorização prévia e expressa. O art. 46, III permite citação, em qualquer meio, para estudo, crítica ou polêmica, na medida justificada, com autor e origem. O art. 46 não cria uma licença geral para copiar conteúdo da internet.[4] [5] [17] | A existência de URL pública, órgão público, PDF ou acesso gratuito não prova domínio público nem licença de reutilização. Direitos morais de autoria e integridade permanecem relevantes; domínio público resolve direitos patrimoniais dentro dos limites legais, não autoria.[4] [17] | Guardar base de direitos: titular, licença, escopo, território, prazo, atribuição, autorização de tradução/adaptação e prova. O assistente deve preferir trechos curtos e links, não reproduzir obras inteiras. |
| Citações e referências | A NBR 10520:2023 é normalização técnica para apresentação de citações; material institucional da FCEE resume autor-data, citação direta/indireta, localização em documentos não paginados, `et al.` e indicação de tradução/grifo. É orientação de normalização, não uma exceção autoral.[16] | A referência precisa permitir identificação e conferência. Para conteúdo web, incluir autor/órgão, título, data, URL, data de acesso quando relevante, versão e trecho/localização. | O modelo deve separar `citation_display` de `rights_basis`: citar não é licenciar. Exigir citação humana legível e URL estável, inclusive no assistente. |
| Responsabilidade por orientação e publicidade | O CDC é aplicável quando houver relação de consumo. Informação clara é direito básico; oferta e publicidade podem vincular o fornecedor. É proibida publicidade enganosa inclusive por omissão; o patrocinador deve guardar os dados fáticos, técnicos e científicos que sustentam a mensagem, e o ônus de provar veracidade é dele.[5] A LBI reforça informação correta e clara e recursos acessíveis em canais virtuais.[6] | Um guia que promove plano, curso, captação, preço, benefício ou resultado pode ser entendido como comunicação comercial, ainda que se apresente como “conteúdo”. Disclaimers não corrigem afirmação falsa, incompleta ou desatualizada. | Separar conteúdo educativo, orientação operacional, publicidade e contrato. Toda claim comercial deve apontar evidência, validade, responsável e condições. |
| LGPD e assistente | A LGPD exige finalidade, necessidade, qualidade/atualização e transparência. Programas de governança devem ser publicados e atualizados periodicamente. O art. 20 trata de decisões automatizadas sobre perfil; não há base para converter toda resposta extrativa em “decisão automatizada” nem para afirmar um direito geral a explicação de qualquer resposta.[14] O guia da ANPD é orientação administrativa para papéis e governança.[15] | Consultas, feedback, progresso de curso e logs podem ser dados pessoais. O conteúdo recuperado pode conter dados pessoais ou informações inseridas por organizações. | Minimizar logs, separar telemetria de conteúdo, aplicar RLS, limitar retenção e informar finalidade. O assistente não deve expor dados privados nem usar conteúdo de rascunho. |
| SEO e indexação | A documentação do Google é orientação técnica, não lei e não promessa de posicionamento. Recomenda páginas rastreáveis, URLs descritivas, canonical para duplicatas, sitemap opcional, conteúdo original, legível, útil e atualizado. Não existe garantia de primeiro lugar.[13] | SEO não pode vencer privacidade, direitos autorais, acessibilidade ou exatidão. Conteúdo `demo`, privado, personalizado ou com dados pessoais não deve ser indexado. | SSR/crawlabilidade, `canonical`, `robots`, sitemap público, metadados de autor/data/versão e JSON-LD somente para fatos visíveis. Testar também `noindex` e remoção de versão superseded. |

## Requisitos de produto

### 1. Taxonomia e autoridade do conteúdo

Cada item deve ter um rótulo obrigatório, visível ao usuário e transportado pela API:

- **Oficial:** publicado ou expedido pelo órgão/titular indicado, com URL ou documento verificável. “Oficial do IMPACTO” não significa “oficial do governo”.
- **Regulatório:** lei, decreto, resolução, portaria, decisão ou ato com autoridade identificada, jurisdição e vigência. Deve indicar “texto consultado em” e não apenas “atual”.
- **Orientação administrativa:** guia, manual, FAQ ou página institucional que recomenda uma conduta, sem equiparação automática a norma.
- **Padrão técnico:** WCAG, ABNT ou outro padrão adotado. Exibir edição e escopo.
- **Literatura/normalização:** material acadêmico, biblioteca ou guia de citação.
- **Educativo, comunidade, parceiro ou hipótese de produto:** não pode aparecer em busca ou assistente como base oficial sem rótulo.
- **Demo/rascunho:** bloqueado de indexação e de recuperação pelo assistente de produção; precisa do selo já previsto pelo hub.

O rótulo deve ser acompanhado de `responsible_publisher`, `author`, `reviewer`, `review_reference` e canal de correção. Se a fonte for de terceiro, “fonte” não deve ser confundida com “autor do artigo”.

### 2. Fluxo de revisão e publicação

Propor o seguinte fluxo como **hipótese de produto**, com alçadas configuráveis:

`draft → editorial_review → subject_review → legal_review (quando aplicável) → rights_review → accessibility_review → factual/source_check → seo_check → approved → scheduled → published → superseded/retired/retracted`.

Regras mínimas:

- o autor não aprova sozinho; o controle de quatro olhos já existente deve ser preservado;
- versão publicada é imutável; correção cria nova versão, novo hash e novo registro de transição;
- publicação exige fonte, autor, licença/base jurídica, jurisdição, data de vigência quando houver, data de verificação, revisão prevista, acessibilidade e estado de indexação;
- atualização de fonte oficial, mudança legal, link quebrado, contradição material, denúncia autoral ou barreira de acessibilidade pode disparar revisão/rebaixamento;
- retirada não apaga silenciosamente a trilha: guarda-se motivo, quem decidiu, quando, versão afetada e versão substituta, observando LGPD e retenção necessária;
- conteúdo regulatório vencido não deve ser retornado como regra vigente. Pode permanecer em arquivo histórico, com aviso claro de não vigência;
- “revisão pendente” deve aparecer na interface, na API e no assistente. Não basta existir em uma tabela administrativa.

### 3. Conteúdo e linguagem

O editor deve exigir público-alvo, objetivo, ação esperada, pré-requisitos e termos que precisam ser explicados. Aplicar Lei nº 15.263/2025 quando o conteúdo for comunicação de órgão público e adotar as mesmas técnicas como baseline nos demais conteúdos: ordem direta, frases curtas, uma ideia por parágrafo, palavras comuns, siglas explicadas na primeira ocorrência, voz ativa, listas e informação importante primeiro.[3] O texto simples não pode apagar a fonte, a condição, o risco ou a exceção jurídica.

Para conteúdo jurídico ou regulatório, exibir um bloco de escopo: **o que a fonte diz**, **qual é a jurisdição**, **qual é a data/versão**, **o que não foi verificado** e **qual ação institucional é necessária**. Proibir frases genéricas como “a lei garante” quando a fonte apenas oferece uma orientação administrativa.

### 4. Direitos autorais e citação

O CMS deve impedir publicação sem seleção de um dos caminhos:

1. obra própria, com autor e titular definidos;
2. licença identificada, incluindo escopo de cópia, adaptação, tradução, comercialização, duração, território e atribuição;
3. autorização arquivada, com titular, data, versão e finalidade;
4. domínio público verificado, sem apagar autoria e integridade;
5. citação ou pequeno trecho com finalidade, extensão justificada, autor e origem, sujeito à revisão humana;
6. conteúdo que não deve ser publicado até esclarecimento de direitos.

Não usar a palavra “citação” para justificar cópia extensa, mirror de PDF, tradução automática integral, resumo que substitui o original ou indexação de conteúdo restrito. Para o assistente, armazenar o identificador da fonte e devolver trecho mínimo necessário, título, autor/órgão, data e link original.

### 5. Acessibilidade de conteúdo

Adotar WCAG 2.2 AA como **meta de produto**, não como fato jurídico automático. Para páginas e componentes, exigir pelo menos:

- estrutura semântica, cabeçalhos coerentes, idioma `pt-BR`, título e landmarks;
- texto alternativo que transmita função, descrição longa ou tabela equivalente quando a imagem for informativa;
- contraste e foco visível, operação por teclado, ordem de foco e ausência de armadilha;
- zoom de texto a 200%, reflow a 320 CSS px, sem dependência exclusiva de cor, tamanho de alvo, mensagens de erro e status acessíveis;
- tabelas com cabeçalhos programáticos e alternativa textual/dados para gráficos;
- vídeo com legenda sincronizada, transcrição e, quando pertinente, audiodescrição e Libras; o URL externo não prova que o recurso exista;
- PDF/DOCX acessível, com ordem de leitura, marcação, idioma, títulos, tabela, texto alternativo e ausência de imagem de texto sem alternativa;
- canal acessível para reportar barreira e prazo interno de resposta.

O componente “acessibilidade” não deve ser apenas um símbolo. A LBI exige acesso às informações, e o art. 68 trata de arquivos reconhecíveis por leitores de tela, ampliação, contraste e Braille para formatos acessíveis.[6] O eMAG acrescenta recomendações úteis de compreensão, siglas, formulários e erros.[9]

### 6. SEO e acesso público

Para conteúdo público e não pessoal:

- renderizar título, descrição, autor/órgão, data de publicação, data de atualização, versão, assunto e canonical no HTML acessível ao crawler;
- gerar sitemap apenas para URLs públicas e vigentes; retirar ou redirecionar superseded/retracted segundo o motivo;
- aplicar `noindex` a demo, privado, personalizado, rascunho, conteúdo de exemplo e página de resultado de busca;
- usar JSON-LD apenas quando os dados também estiverem visíveis e forem verdadeiros; schema.org não cria autoridade nem certificação;
- evitar conteúdo duplicado, URLs opacas e páginas que dependam apenas de JavaScript quando a descoberta pública for necessária;
- não coletar ou expor dados pessoais para “melhorar SEO”.

O Google recomenda conteúdo útil, original, legível e atualizado, mas afirma que não há segredo que garanta primeiro lugar. Portanto, “otimizado para SEO” deve significar controles técnicos executados, não promessa de posição.[13]

### 7. Assistente extrativo

O contrato do assistente deve ser explícito:

- recuperar somente versões `published` e autorizadas para aquele usuário/tenant;
- excluir `draft`, `demo`, `superseded`, `retracted`, privado, pendente de revisão material ou fora da jurisdição solicitada;
- retornar trechos literais com `source_id`, título, autor/órgão, data, URL, versão, hash e localização quando houver;
- não completar lacunas, concatenar frases de fontes incompatíveis, traduzir/adaptar sem marcar ou inventar uma conclusão;
- responder “não encontrei informação suficiente na base oficial” quando não houver fonte adequada e oferecer abertura de chamado;
- colocar aviso de escopo para conteúdo jurídico, fiscal, de preço, saúde, segurança ou elegibilidade: informação geral, não decisão nem parecer personalizado;
- revelar “revisão pendente”, “fonte não oficial”, “fonte histórica” e “conteúdo educativo” antes do trecho, não apenas em tela secundária;
- registrar consulta, IDs dos documentos recuperados, versão e resultado de abstinência sem registrar texto livre ou dados excessivos;
- ter teste de isolamento entre organizações e de resistência a instruções embutidas em conteúdo recuperado. Mesmo sem modelo generativo, conteúdo de fonte pode conter texto enganoso ou instruções não confiáveis;
- não exibir certificado de academia, selo de impacto, validação de indicador ou badge como prova jurídica/educacional sem a base correspondente.

A afirmação `ai_used:false` é válida somente se o caminho de produção realmente não chamar modelo generativo. “Extrativo” não significa automaticamente correto, oficial, atualizado ou licenciado.

## Requisitos de dados

O `KNOWLEDGE_DATA_MODEL` já oferece boas fundações: versões imutáveis, `content_history`, quatro olhos, `live_version_id`, exigência de fonte/data em regulatório, FTS, RLS, analytics sem texto livre, gabarito de quiz protegido e certificados revogáveis. Para o v0.26.0, acrescentar ou tornar explícitos estes campos:

| Grupo | Campos/relacionamentos mínimos | Controle esperado |
|---|---|---|
| Identidade | `content_id`, `version_id`, slug, tipo, classe da fonte, idioma, região/jurisdição, público-alvo, `demo`, `visibility` | Classe não pode ser inferida apenas pelo slug; demo não entra no conjunto público. |
| Proveniência | `source_url`, `source_title`, órgão/autor, tipo de fonte, data de publicação, data de acesso, `source_version`, `effective_from`, `effective_to`, `verified_at`, `verification_method`, `source_hash` | “Atual” somente com verificação registrada; registrar fonte histórica e fonte substituta. |
| Responsabilidade | autor, editor, revisor de assunto, revisor jurídico, revisor de direitos, revisor de acessibilidade, aprovador, organização, `review_reference` | Autor não aprova; cada alçada deixa evidência e data. |
| Direitos | titular, licença, `rights_basis`, autorização, escopo, território, prazo, regra de atribuição, permissão de tradução/adaptação, referência ao arquivo-prova | Publicação sem licença ou exceção classificada é bloqueada. `citation` não substitui `rights_basis`. |
| Conteúdo | corpo estruturado, resumo, ação, riscos, exceções, claims, citações, glossário, leitura fácil, versão em Libras/idioma adicional | Claims relevantes ligam-se a evidências. Texto simplificado mantém ressalvas. |
| Acessibilidade | alt text, descrição longa, idioma, ordem de leitura, status de PDF/DOCX, legenda, transcrição, audiodescrição, Libras, testes, barreiras conhecidas | Mídia externa exige prova de legenda/transcrição; status “não verificado” é visível. |
| Publicação | estado, agendamento, `published_at`, `supersedes_id`, `retraction_reason`, `canonical_url`, `robots`, `sitemap_eligible`, JSON-LD version, `content_sha256` | Um live por slug/jurisdição/idioma; superseded não é indexável nem recuperável pelo assistente. |
| Revisão | `review_due`, motivo, criticidade, evento disparador, última decisão, próxima ação, responsável | `review_due` é prazo interno de produto, não prazo legal; vencimento gera tarefa/alerta. |
| Assistente | query hash, tenant/user scope, IDs/versões retornados, offsets dos trechos, abstention reason, timestamp, política aplicada | Reprodutibilidade, ausência de dados privados e prova do que foi exibido. |
| Academia | versão de curso/aula, fonte/licença de material, legendas/transcrição verificadas, acessibilidade do quiz, regra de certificado, `revoked_at` e motivo | Certificado continua “não oficial”; não afirmar acessibilidade sem teste do vídeo e material. |
| LGPD/telemetria | finalidade, base definida pelo responsável, retenção, acesso, anonimização/pseudonimização, pedido de titular, incidente | Não usar analytics com texto livre; separar conteúdo público de dados de usuário. |

A cadeia de fonte deve ser um objeto próprio, não só dois campos em `kb_article_versions`. Isso permite apontar que uma frase usa a lei, outra usa o regulamento e outra é hipótese editorial. Também permite tratar conflito entre fonte primária atual, fonte histórica e guia secundário.

## Testes e controles antes de publicação

### Portão de conteúdo e evidência

- Teste de banco: impossível publicar sem classe, autor/órgão, fonte, data de verificação, jurisdição, licença/base autoral, revisão e aprovação separada.
- Teste de imutabilidade: alterar corpo, fonte, licença ou hash de versão publicada deve falhar; correção cria nova versão.
- Teste de um único `live_version_id` por combinação de conteúdo, idioma e jurisdição.
- Teste de conflito: fonte vencida, link quebrado ou ato revogado deve gerar alerta e impedir rótulo “vigente”.
- Linter de citações: autor/órgão, título, data, URL, localização e atribuição presentes; indicar fonte não paginada e tradução própria quando aplicável.[16]
- Revisão humana de direitos para trechos extensos, imagens, gráficos, logotipos, músicas, vídeos, traduções e conteúdo de terceiros. Não tentar decidir a exceção do art. 46 somente por limite de caracteres.
- Teste de rebaixamento: `demo`, `draft`, `superseded`, `retracted` e `review_pending` não aparecem na busca pública nem no assistente de produção.
- Auditoria de quatro olhos e registro de quem aprovou, quando e com qual referência.

### Acessibilidade

- axe-core ou equivalente no CI para todas as rotas e estados, sem tratá-lo como prova suficiente.
- Teste manual de teclado, foco, zoom 200%, reflow 320 CSS px, alto contraste, redução de movimento, formulários, tabelas, gráficos e documentos.
- Pelo menos um ciclo com leitor de tela real e navegador adicional; teste em dispositivo móvel quando o fluxo for móvel.
- Teste de conteúdo: alt text, ordem de cabeçalhos, siglas, linguagem compreensível, links descritivos, legenda sincronizada, transcrição e acessibilidade de PDF/DOCX.
- Relatório por página completa, ambiente, versão de WCAG/eMAG/ABNT adotada, defeitos, severidade, exceções e data. Automatizado positivo não autoriza claim de conformidade total.[10]
- Teste com pessoas usuárias de tecnologia assistiva ou avaliação especializada antes de declaração pública ampla; registrar barreiras ainda conhecidas.

### SEO e publicação pública

- HTML inicial contém título, conteúdo principal, autor/órgão, data, canonical e metadados; validar sem login.
- Sitemap contém somente URLs elegíveis; `robots` e `noindex` não entram em conflito.
- JSON-LD é válido, coincide com texto visível e não inventa avaliação, autoridade, certificado ou data.
- Conteúdo privado, demo, exemplo, resultado de busca, personalizado e retracted não é indexável.
- Verificar links quebrados, redirecionamentos, duplicidade e páginas que ficaram órfãs.
- Medir apenas descoberta, rastreabilidade e erros técnicos. Não converter impressão, posição no Google ou clique em prova de qualidade jurídica.

### Assistente extrativo

- Dado teste com resposta suportada por uma única fonte: conferir igualdade do trecho e da versão.
- Dado teste com fontes conflitantes: mostrar conflito/jurisdição/data ou abster-se; nunca escolher silenciosamente.
- Dado teste sem fonte: resposta obrigatória de insuficiência, sem inferência.
- Dado teste com conteúdo `demo`, `draft`, privado, superseded ou retracted: zero recuperação.
- Dado teste de tenant: um usuário não recupera recurso, curso, ticket ou documento de outra organização.
- Dado teste de revisão: fonte vencida mostra “revisão necessária” e não é tratada como regra atual.
- Dado teste de link de origem e direitos: o assistente retorna atribuição e URL sem copiar obra integral.
- Dado teste de prompt/instrução dentro do documento: texto recuperado é tratado como conteúdo, não como comando de sistema.
- Log de auditoria permite reconstruir resposta sem armazenar a pergunta em texto aberto quando ela contiver dado pessoal desnecessário.

## Claims proibidos ou que exigem prova específica

Sem evidência e escopo documentados, o produto não deve publicar:

- “100% acessível”, “WCAG 2.2 AA conforme”, “conforme ABNT NBR 17225” ou “acessível para todas as deficiências”. A declaração deve identificar páginas, versão, testes, limitações e data.
- “Conteúdo oficial”, “posição oficial do governo”, “lei atualizada” ou “orientação jurídica” para demo, guia de parceiro, hipótese editorial, fonte histórica ou texto sem revisão e jurisdição.
- “Certificado reconhecido”, “certificação profissional”, “validado pelo MEC” ou equivalente para o certificado da academia, que o próprio produto define como não oficial.
- “Garantia de aprovação, financiamento, elegibilidade, conformidade, impacto, economia, segurança, resultado ou direito” quando a fonte não sustentar exatamente a afirmação e suas condições.
- “Citação autorizada”, “uso livre porque está na internet”, “domínio público” sem verificação dos direitos patrimoniais e sem preservação de autoria/direitos morais.
- “SEO garantido”, “primeiro no Google”, “melhor ranqueamento” ou claim de rich result. A documentação do Google não oferece essa garantia.[13]
- “Resposta correta”, “parecer”, “decisão”, “análise completa” ou “fonte definitiva” para resposta extrativa. Usar “trecho recuperado da base publicada”, com data e escopo.
- “Sem IA” ou `ai_used:false` se qualquer caminho de fallback chamar modelo; “extrativo” não deve ser usado como sinônimo de infalível.
- “Sem retenção” ou “sem dados pessoais” quando houver logs, progresso, feedback, tokens, IP, matrícula ou documentos, salvo delimitação precisa e verificável.

## Lacunas prioritárias

1. **Lacuna de status e documentação:** headers v0.12.0/v0.18.1 convivem com release v0.26.0; atualizar ou marcar como histórico e ligar cada claim ao teste/artefato correto.
2. **Lacuna de conteúdo real:** o hub tem apenas seed demo. Não liberar regra fiscal, jurídica, preço, impacto ou elegibilidade como conteúdo oficial sem redação e revisão humanas.
3. **Lacuna de portão editorial:** `PUBLICACAO.md` prova infraestrutura, não direitos autorais, fonte atual, acessibilidade, SEO, revisão de claim e retirada. Criar `CONTENT_RELEASE_CHECKLIST` com bloqueio de publicação.
4. **Lacuna de responsabilidade:** faltam proprietário por domínio, revisor de assunto, responsável por atualização, canal de correção e matriz de escalonamento para fonte revogada, denúncia autoral ou risco de dano.
5. **Lacuna de proveniência:** `source + date` apenas para regulatório é insuficiente para claims comerciais, educativos, acadêmicos e resultados do assistente. Exigir cadeia para todo claim material.
6. **Lacuna autoral:** não há no documento atual prova de licença para imagens, vídeos, ícones, fontes, traduções ou materiais de cursos. O controle precisa existir por arquivo e por versão.
7. **Lacuna de acessibilidade integral:** manual Chromium não cobre leitor de tela, navegador, zoom, documentos, vídeo, voz e testes com usuários. O relatório não autoriza WCAG AA; reconciliar a alegação de axe do README com o artefato atual.
8. **Lacuna de padrão:** eMAG 3.1 é baseado em WCAG 2.0; a meta declarada é WCAG 2.2 AA e a ABNT NBR 17225 é de 2025. Definir uma matriz de equivalência e a edição normativa adotada, sem declarar equivalência automática.
9. **Lacuna da academia:** legenda/transcrição são campos, não evidência. Verificar o ativo externo, o quiz por teclado, o PDF do certificado, a revogação e a acessibilidade da página de verificação.
10. **Lacuna de SEO:** há sitemap/JSON-LD projetados para conteúdo público, mas o release deve testar canonical, metadados de autoria/data/versão, remoção de superseded, SSR e ausência de dados pessoais; schema.org não prova autoridade.
11. **Lacuna de privacidade:** `docs/LGPD.md` deixa pendentes base legal, retenção definitiva, RIPD/DPIA, contratos com provedores e canal do encarregado. Resolver antes de ampliar analytics, personalização ou assistente.
12. **Lacuna jurídica de publicação:** `LEGAL_FRAMEWORK.md` mantém onze minutas em draft e bloqueia aceite. Não usar o hub para dar aparência de aprovação ou de orientação jurídica enquanto o próprio portão legal estiver fechado.
13. **Lacuna de conflito de fontes:** não há regra explícita de precedência entre lei, regulamento, órgão emissor, guia, literatura e hipótese; criar política de fontes e revisão de divergência.
14. **Lacuna de retirada:** implementar retração visível, preservação da trilha, notificação interna, remoção de sitemap/canonical e bloqueio imediato no assistente quando houver erro material, revogação ou risco.

## Decisões que exigem proprietário responsável

- qual entidade será responsável pela publicação e pelo canal de correção;
- quais domínios terão revisor jurídico, revisor de assunto e revisor de acessibilidade;
- qual escopo contratual adota WCAG 2.2 AA, e se a ABNT NBR 17225 será licenciada/adotada;
- quais conteúdos poderão ser chamados de “oficiais” e com que prova;
- qual prazo interno `review_due` será usado por classe de fonte, deixando claro que ele não substitui prazo legal;
- qual política de direitos autorais e licenças será aplicada à biblioteca, academia, ícones, vídeos e traduções;
- qual base legal, retenção e canal do encarregado regerão consultas, feedback, progresso e logs do assistente;
- quem autoriza rebaixamento/retração e como a decisão será comunicada a usuários afetados;
- quais páginas, documentos e integrações compõem qualquer futura declaração pública de acessibilidade.

## Referências

[1]: https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2011/lei/l12527.htm "Lei nº 12.527, de 18 de novembro de 2011 — Lei de Acesso à Informação" — Presidência da República; vigente; sustenta publicidade ativa, linguagem clara, autenticidade, integridade, primariedade, atualização, formatos abertos e acessibilidade.
[2]: https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2021/lei/l14129.htm "Lei nº 14.129, de 29 de março de 2021 — Governo Digital" — Presidência da República; vigente; sustenta acessibilidade, linguagem clara, transparência, dados abertos e proteção de dados na Administração Pública.
[3]: https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2025/lei/l15263.htm "Lei nº 15.263, de 14 de novembro de 2025 — Política Nacional de Linguagem Simples" — Presidência da República; vigente desde 17 de novembro de 2025; sustenta técnicas de linguagem simples, acessibilidade e teste com público-alvo.
[4]: https://www.planalto.gov.br/ccivil_03/leis/l9610.htm "Lei nº 9.610, de 19 de fevereiro de 1998 — Direitos Autorais" — Presidência da República; vigente; sustenta proteção de obras, autoria, direitos morais, autorização de reprodução e limites de citação.
[5]: https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm "Lei nº 8.078, de 11 de setembro de 1990 — Código de Defesa do Consumidor, texto compilado" — Presidência da República; vigente; sustenta informação clara, vinculação da oferta, publicidade enganosa/omissiva e ônus da prova.
[6]: https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2015/lei/l13146.htm "Lei nº 13.146, de 6 de julho de 2015 — Lei Brasileira de Inclusão da Pessoa com Deficiência" — Presidência da República; vigente; sustenta acessibilidade de sites, formatos acessíveis e informação clara em canais virtuais.
[7]: https://www.planalto.gov.br/ccivil_03/_ato2004-2006/2004/decreto/d5296.htm "Decreto nº 5.296, de 2 de dezembro de 2004" — Presidência da República; vigente como regulamento histórico; sustenta a obrigação de acessibilidade em portais e sítios da Administração Pública e o símbolo de acessibilidade, sem transformar o prazo original em prazo atual.
[8]: https://www.gov.br/governodigital/pt-br/legislacao/acessibilidade "Acessibilidade — legislação" — Governo Digital; página institucional consultada em 8 de outubro de 2026, sem data editorial visível; sustenta o mapa administrativo de leis, decretos, convenção e portarias aplicáveis.
[9]: https://emag.governoeletronico.gov.br/ "Modelo de Acessibilidade em Governo Eletrônico — eMAG 3.1" — Governo Digital/SISP; data editorial não visível; sustenta recomendações brasileiras para marcação, conteúdo, compreensão, multimídia, formulários e processo de acessibilidade.
[10]: https://www.w3.org/TR/WCAG22/ "Web Content Accessibility Guidelines (WCAG) 2.2" — W3C/WAI; recomendação de 12 de dezembro de 2024; sustenta princípios, critérios de sucesso, níveis A/AA/AAA e requisitos de declaração de conformidade.
[11]: https://abnt.org.br/lancamento-da-abnt-nbr-17225/ "Lançamento da ABNT NBR 17225 — Acessibilidade Digital na Prática" — ABNT; evento de 11 de março de 2025; sustenta o lançamento e o escopo institucional anunciado da norma técnica brasileira.
[12]: https://repositorio.enap.gov.br/handle/1/5258 "Guia de linguagem simples: como posso simplificar meu documento?" — Laboratório de inovação em governo da Prefeitura de São Paulo/ENAP; 2019; sustenta orientação institucional em quatro passos para simplificação de documentos.
[13]: https://developers.google.com/search/docs/fundamentals/seo-starter-guide "SEO Starter Guide" — Google Search Central; data editorial não visível; sustenta rastreabilidade, URLs, canonical, sitemap, conteúdo útil/atualizado e ausência de garantia de ranking.
[14]: https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm "Lei nº 13.709, de 14 de agosto de 2018 — Lei Geral de Proteção de Dados Pessoais" — Presidência da República; vigente; sustenta finalidade, necessidade, qualidade/atualização, transparência e governança em dados pessoais.
[15]: https://www.gov.br/anpd/pt-br/documentos-e-publicacoes/Segunda_Versao_do_Guia_de_Agentes_de_Tratamento_retificada.pdf "Segunda versão do Guia de Agentes de Tratamento" — ANPD; criado em 27 de abril de 2022, modificado em 23 de janeiro de 2025; sustenta orientação administrativa sobre controlador, operador e encarregado.
[16]: https://www.fcee.sc.gov.br/downloads/biblioteca-virtual/educacao-especial/temas-gerais/1977-atualizacao-da-norma-de-citacoes-da-abnt-nbr-10520-principais-mudancas/file "Atualização da norma de citações da ABNT NBR 10520: principais mudanças" — Fundação Catarinense de Educação Especial; 2024; sustenta orientação institucional sobre citação direta/indireta, autor-data, localização e atribuição.
[17]: https://www.gov.br/cultura/pt-br/assuntos/direitos-autorais/perguntas-frequentes/perguntas-frequentes "Perguntas Frequentes — Direitos Autorais" — Ministério da Cultura; página institucional com registro de 19 de julho de 2021; sustenta autorização prévia como regra, limitações dos arts. 46–48, citação com autor/origem e distinção entre domínio público e direitos morais.
[18]: https://www.gov.br/governodigital/pt-br/acessibilidade-e-usuario/acessibilidade-digital "Acessibilidade Digital" — Governo Digital; página institucional consultada em 8 de outubro de 2026, sem data editorial visível; sustenta definição de eliminação de barreiras e objetivo de permitir perceber, entender, navegar e interagir.
[19]: https://www4.planalto.gov.br/centrodeestudos/assuntos/manual-de-redacao-da-presidencia-da-republica/manual-de-redacao.pdf "Manual de Redação da Presidência da República" — Presidência da República; 3ª edição, 2018; sustenta orientação oficial de redação e comunicação, embora o PDF tenha exigido desafio anti-automação nesta consulta.

## Documentos internos consultados

`README.md`; `KNOWLEDGE_HUB.md`; `KNOWLEDGE_DATA_MODEL.md`; `TRAINING_ACADEMY.md`; `docs/PUBLICACAO.md`; `ACCESSIBILITY_REPORT.md`; `web/brand/ACCESSIBILITY_GUIDELINES.md`; `docs/LGPD.md`; `docs/LEGAL_FRAMEWORK.md`; `docs/PROCUREMENT.md`. Esses arquivos sustentam o diagnóstico do release; não substituem fonte normativa externa.
