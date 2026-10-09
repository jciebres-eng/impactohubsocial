# IA, algoritmos, recomendação e conteúdo — governança e auditoria do release v0.26.0

**Data de corte da pesquisa:** 08/10/2026.  **Escopo:** Brasil; LGPD e decisões automatizadas; governança de IA; recomendação e conteúdo; direitos autorais e uso de modelos; referências OECD, UNESCO, NIST e ISO.  Este documento é pesquisa e especificação de controles de produto. Não é parecer jurídico personalizado.

## Escopo e método

Foram lidos o `README.md`, `docs/LGPD.md`, `docs/LEGAL_FRAMEWORK.md`, `KNOWLEDGE_HUB.md`, `docs/PROCUREMENT.md`, `docs/AI.md`, `docs/AI_ENGINES.md`, `AI_FINAL_AUDIT.md`, `INTENT_ENGINE.md`, `MATCH_ENGINE.md` e os módulos efetivos de matching, scoring, reputação, recomendação, busca e assistente. A análise separa o que é **lei ou regulamento vigente**, o que é **orientação administrativa**, o que é **projeto de lei**, o que é **padrão voluntário**, o que é **literatura** e o que é **hipótese de produto**.

As fontes externas foram abertas e lidas, não apenas identificadas por snippet. O estado legislativo foi conferido em 07–08/10/2026. A referência a projeto de lei não deve ser lida como obrigação atual.

## Estado atual do release que precisa ser corrigido

O `README.md` descreve o v0.26.0 como **BASE TÉCNICA FECHADA**, não publicado em loja ou domínio, sem cobrança real e sem provedor de IA ligado. O provedor local é o padrão descrito em `docs/AI.md`: regras determinísticas offline; não há envio externo quando ele está efetivamente configurado como `local`. As rotas de provedor externo existem como capacidade técnica, mas os próprios documentos informam que nenhum teste fez chamada real a Anthropic ou OpenAI, apenas a servidor HTTP falso. Portanto, o release não pode ser anunciado como uma implantação de IA em produção nem como conformidade jurídica concluída.

Há quatro correções documentais imediatas:

1. `AI.md` está em v0.7.0, `AI_ENGINES.md` em v0.17.0 e `AI_FINAL_AUDIT.md` em v0.23.0, enquanto o release é v0.26.0. Os três precisam declarar a mesma fotografia de release, com data de corte e commit.
2. `AI_ENGINES.md` registra 45 motores e descreve os acréscimos da v0.26.0; `AI_FINAL_AUDIT.md` ainda abre afirmando 42 motores. A contagem e a natureza de cada motor devem ser derivadas do registro atual, não copiadas de uma auditoria histórica.
3. `AI_FINAL_AUDIT.md` mistura “previsão de custo” inexistente com estimativa por chamada existente. O texto deve separar **estimativa ex ante**, **custo apurado somente com preço vigente** e **previsão histórica**, que não existe.
4. A palavra “oficial” do assistente deve ser corrigida. `knowledge.py` pode recuperar artigos e FAQs com origens `official`, `educational` e `third_party`, mas a mensagem de recusa diz “base oficial”. A resposta deve dizer “base publicada” ou restringir a consulta a conteúdo realmente oficial.

O estado jurídico também está explicitamente incompleto. `docs/LGPD.md` registra como pendentes: base legal por tratamento, RIPD/DPIA, contratos com provedores, prazos reais de retenção e canal do encarregado. `docs/LEGAL_FRAMEWORK.md` informa que os documentos legais são minutas e que não há aceite registrável enquanto não forem aprovados. Logo, os controles técnicos existentes são **evidência de engenharia**, não declaração de conformidade.

`KNOWLEDGE_HUB.md` informa que o seed contém somente material `demo=true`, sem conteúdo jurídico, fiscal ou de preço real. A presença de busca e assistente não autoriza chamar esse conteúdo de orientação oficial, nem permite que o produto apresente um resumo extraído como decisão ou aconselhamento profissional.

O veredito de produto é **amarelo para os motores determinísticos e vermelho para exposição externa de IA/modelos ou conteúdo de usuários sem gates jurídicos adicionais**. A razão não é a existência de modelo por si só: é a combinação de documentação histórica, ausência de provedor real, ausência de bases legais/RIPD/contratos concluídos, pesos não calibrados e cobertura ainda insuficiente para efeitos de alto impacto.

## Marco brasileiro vigente

### LGPD e decisões automatizadas

A **Lei nº 13.709/2018 — LGPD**, vigente, impõe finalidade, adequação, necessidade, qualidade, transparência, segurança, prevenção, não discriminação e responsabilização/prestação de contas; exige uma hipótese legal para o tratamento e prevê direitos de acesso, correção, eliminação, oposição quando cabível e demais direitos do titular [1]. O fato de o algoritmo ser determinístico ou de a saída não usar um LLM não retira o tratamento do âmbito da LGPD quando há dados pessoais ou inferências vinculadas a pessoa identificada ou identificável.

O art. 20 dá ao titular o direito de solicitar revisão de decisões tomadas **unicamente** com base em tratamento automatizado que afetem seus interesses, incluindo decisões de perfil pessoal, profissional, de consumo ou crédito e aspectos da personalidade. O controlador deve fornecer, quando solicitado, informações claras e adequadas sobre critérios e procedimentos, ressalvado segredo comercial e industrial; se negar informações por esse fundamento, a ANPD pode auditar aspectos discriminatórios [1]. O § 3º que previa revisão por pessoa natural foi vetado. Assim, “revisão humana obrigatória” é hoje uma **salvaguarda de produto** e uma referência de desenho responsável, não uma frase que possa ser atribuída diretamente à LGPD como obrigação geral.

A tomada de subsídios da ANPD sobre IA e revisão de decisões automatizadas esteve aberta de 06/11/2024 a 24/01/2025, recebeu 99 contribuições e trata art. 20, explicabilidade, legítimo interesse, dados sensíveis, crianças, revisão humana, auditoria e canais de titulares [2]. Ela é **participação regulatória encerrada**, não regulamento. Não deve ser usada para dizer que a ANPD já publicou uma regra geral sobre explicabilidade ou IA.

Para o produto, o gatilho do art. 20 deve ser funcional, não nominal: se score, reputação, elegibilidade, recomendação, priorização ou perfil influenciar acesso a financiamento, oportunidade, contratação, exposição, benefício, suspensão ou tratamento diferenciado de uma pessoa ou organização identificável, deve ser tratado como potencial decisão ou perfilamento de impacto. “É só recomendação” não resolve o problema se o efeito prático for decisório.

### ANPD: atos vigentes e orientação administrativa

A página oficial de regulamentações da ANPD lista como vigentes, entre outros, a **Resolução CD/ANPD nº 15/2024**, sobre comunicação de incidente de segurança; a **Resolução CD/ANPD nº 18/2024**, sobre atuação do encarregado; e a **Resolução CD/ANPD nº 19/2024**, sobre transferência internacional e cláusulas-padrão [4]. A página de comunicação de incidentes explica que, havendo risco ou dano relevante, a comunicação à ANPD não substitui a comunicação aos titulares [20]. O produto precisa ter inventário de incidente, responsável, evidência de contenção, avaliação de risco e capacidade de comunicação; não basta registrar um erro no `ai_usage`.

A Resolução 19 exige que, quando usadas cláusulas-padrão, o texto aprovado seja adotado integralmente, e que o controlador publique informação em português, simples e acessível, sobre finalidade, duração, país de destino, agentes, responsabilidades, segurança e direitos do titular [5]. Enviar prompt ou documento a provedor estrangeiro é potencial transferência internacional; redação por regex não é dispensa automática. Antes de ativar `anthropic` ou `openai_compatible`, o release precisa ter qualificação de controlador/operador, finalidade, categorias, país, retenção, subprocessadores, instrução de não treinamento quando negociada, deleção, confidencialidade, mecanismo de transferência e canal do titular.

A **Agenda Regulatória 2025–2026 da ANPD** é instrumento de planejamento e transparência, não um ato que por si só crie obrigação [3]. IA, decisões automatizadas, segurança e ambiente digital devem ser acompanhados como temas regulatórios em evolução. A data de consulta precisa ser registrada no produto para conteúdo jurídico que possa vencer.

### Internet, conteúdo e recomendação

O **Marco Civil da Internet — Lei nº 12.965/2014**, vigente, protege privacidade e dados pessoais, exige informações claras sobre coleta/uso/armazenamento e políticas de uso, preserva liberdade de expressão e acessibilidade e disciplina guarda e fornecimento de registros [15]. Ele não é uma lei geral de ranking ou de recomendação; contudo, a plataforma que fornece aplicação de internet deve avaliar suas obrigações de acordo com a atividade concreta, conteúdo gerado por terceiro e alcance.

O **Decreto nº 12.975/2026**, vigente 60 dias após sua publicação, atualizou o regulamento do Marco Civil. Para provedores que intermediam conteúdo gerado por terceiros, prevê deveres de sede/representante no País, canal permanente e acessível de denúncia, medidas contra redes artificiais de distribuição de conteúdo ilícito, segurança, transparência e dever de cuidado em hipóteses definidas no decreto [16]. A ANPD informa que sua fiscalização será sistêmica: governança, canais, transparência, prevenção e mitigação de riscos, não análise isolada de cada publicação [17].

O v0.26.0 tem biblioteca, materiais, projetos publicados, busca, marketplace e assistentes. Deve ser feita uma classificação formal: (a) conteúdo institucional da plataforma; (b) documento privado de organização; (c) conteúdo público submetido por usuário; (d) anúncio ou impulsionamento; (e) conteúdo que a plataforma apenas indexa. Se existir intermediação de conteúdo de terceiros, não se deve assumir que o decreto é irrelevante só porque a plataforma não é uma rede social clássica.

A **Lei nº 15.211/2025 — Estatuto Digital da Criança e do Adolescente**, está em vigor desde 17/03/2026. Aplica-se a produto ou serviço direcionado a crianças/adolescentes ou de acesso provável por eles; “acesso provável” inclui atratividade, facilidade de acesso ou risco relevante à privacidade, segurança ou desenvolvimento [18]. Ela exige, conforme o caso, prevenção de exposição/recomendação de conteúdo nocivo, configuração mais protetiva por padrão, gerenciamento de riscos, adequação etária, canais de denúncia e mecanismos confiáveis de aferição de idade, vedada a autodeclaração para conteúdos impróprios. A anotação “a plataforma não coleta dados de crianças” não resolve o teste de escopo. Se o produto for público e acessível a menores, a equipe precisa documentar a análise de aplicabilidade antes de publicar.

O **Decreto nº 12.976/2026**, vigente, trata de violência contra mulheres em ambiente digital. Define conteúdo íntimo incluindo material produzido ou manipulado por IA; exige, entre outras medidas, indisponibilização de conteúdo íntimo não autorizado em até duas horas após notificação, marcação para bloquear reenvio e canal específico, gratuito, permanente e acompanhável [19]. Também veda geração/modificação por IA de conteúdo íntimo de terceiro e exige salvaguardas para bloquear solicitações proibidas. A plataforma atual não declara gerador de imagens íntimas nem ferramenta; isso deve virar teste de arquitetura, política de uso e cláusula contratual, e não apenas descrição editorial.

### Governança geral de IA: status do PL 2338/2023

O **PL nº 2.338/2023 — Marco Legal da IA** foi aprovado pelo Senado em 10/12/2024 e remetido à Câmara em 17/03/2025 [6]. O registro da Câmara consultado em 08/10/2026 mostra o projeto aguardando parecer do relator em Comissão Especial, com última ação de apensamento em 02/09/2026 [7]. Portanto, ele é **projeto em tramitação, não lei vigente**.

O texto da Câmara/Senado é útil como horizonte de arquitetura, sem ser usado como obrigação atual. Ele propõe informação sobre interação com IA, não discriminação, explicação, contestação e revisão humana para afetados por sistemas de alto risco [8]. Também propõe transparência sobre conteúdo protegido usado no desenvolvimento e regras específicas para mineração de textos e dados, inclusive requisitos de acesso lícito, finalidade, necessidade, ausência de concorrência com exploração normal, armazenamento seguro e não disseminação em certas hipóteses [8]. O texto pode mudar na Câmara e no Senado; toda referência do código deve dizer “PL 2338/2023, texto em tramitação”, nunca “a lei brasileira de IA”.

## Referências internacionais e seu status

- **OCDE — padrão intergovernamental/orientação.** Os Princípios de IA foram adotados em 2019 e atualizados em 2024; promovem IA inovadora e confiável, respeito a direitos humanos e valores democráticos, transparência, explicabilidade, robustez, segurança e responsabilização, incluindo rastreabilidade de dados, processos e decisões [9]. São uma referência de governança e interoperabilidade; não substituem LGPD, decreto brasileiro ou contrato.
- **UNESCO — recomendação internacional.** A Recomendação sobre a Ética da IA foi adotada pelos 193 Estados-membros em 2021. Seus dez princípios incluem proporcionalidade, segurança, privacidade, governança colaborativa, responsabilidade/auditabilidade, transparência, supervisão humana, sustentabilidade, letramento e não discriminação [10]. É referência de direitos humanos e política pública; não é automaticamente norma brasileira de aplicação privada.
- **NIST AI RMF — padrão voluntário estrangeiro.** O AI RMF 1.0, publicado em 26/01/2023, é expressamente destinado a uso voluntário e organiza a gestão em Govern, Map, Measure e Manage [11]. Pode estruturar o sistema de controles do release, mas não prova conformidade LGPD.
- **ISO/IEC 42001:2023 — norma técnica internacional.** Publicada em dezembro de 2023, especifica requisitos para sistema de gestão de IA e melhoria contínua, com rastreabilidade, transparência e gestão de riscos [12]. É norma técnica e pode ser contratual ou certificável; não é lei brasileira nem selo automático de conformidade.

A política recomendada é usar os quatro referenciais como uma matriz de boas práticas: `Govern`/contexto e responsabilidades (NIST/ISO), direitos e não discriminação (LGPD/OECD/UNESCO), rastreabilidade (OECD/UNESCO/ISO), avaliação e monitoramento (NIST/ISO), intervenção humana e contestação (LGPD como direito de revisão; PL como horizonte), e sustentabilidade/impacto (UNESCO/OECD). Cada controle deve ter fonte normativa ou rótulo de “hipótese de produto”.

## Direitos autorais, conteúdo e uso de modelos

A **Lei nº 9.610/1998 — Lei de Direitos Autorais**, vigente, protege textos, obras artísticas e científicas, fotografias, audiovisual, programas de computador e bases de dados cuja seleção/organização seja criação intelectual; exclui ideias, métodos, sistemas, conceitos matemáticos e atos oficiais, sem eliminar direitos sobre a forma protegida [13]. O autor é pessoa física criadora e os direitos morais e patrimoniais pertencem ao autor nos termos da lei. A reprodução, adaptação, distribuição, comunicação e outras formas de exploração dependem da análise dos direitos exclusivos e das limitações legais aplicáveis.

A lei vigente não contém uma autorização geral e específica para raspar a internet e treinar modelos com todo conteúdo protegido. As exceções não devem ser ampliadas por uma frase de produto como “conteúdo público é livre para treino”. O ponto é controverso e dependente de finalidade, acesso, cópia, quantidade, transformação, saída e exploração econômica. A literatura acadêmica brasileira registra os impactos da IA/ChatGPT e as lacunas interpretativas como tema de pesquisa, não como conclusão normativa fechada [14].

O PL 2338/2023 propõe transparência por sumário de conteúdo protegido usado no desenvolvimento e regras de mineração de textos e dados; isso é **proposta legislativa**, ainda não obrigação atual [8]. Até haver regra definitiva ou licença válida, o produto deve:

- registrar titular/origem, licença, condições de uso, data, escopo territorial, prazo e se treinamento/embeddings/transformação são permitidos;
- tratar conteúdo de usuário como protegido ou restrito por padrão, não como “domínio público” por estar publicado;
- impedir que o gateway envie documento a modelo externo quando a finalidade, base legal, licença ou contrato não cobrir o uso;
- evitar reproduzir trechos extensos de terceiros; respostas do assistente devem citar e extrair apenas o que a licença e a finalidade permitem;
- separar conteúdo oficial, educacional, terceiro, demo e privado, com RLS e política de publicação;
- manter proveniência e hash, mas reconhecer que hash é mecanismo de integridade/pseudonimização, não autorização autoral nem anonimização automática;
- não prometer que uma saída de modelo é obra autoral da plataforma, nem atribuir autoria humana sem revisão e contribuição efetiva; a alocação de direitos deve ser contratual e validada para o caso concreto.

## Auditoria dos motores e limites vinculantes de produto

Os limites abaixo são **controles de produto**. Os números atuais são parâmetros de engenharia e, salvo quando a seção jurídica disser o contrário, não são limites legais.

### Gateway e motores de IA

O desenho provider-agnostic é adequado como isolamento técnico: `local` determinístico; provedores externos opcionais; `disabled`; cota, redação de CPF/CNPJ/e-mail/telefone/CEP/RG/números longos; hash de entrada sem corpo; timeout/retry; fallback para local; rejeição de JSON inválido; rótulo `draft` e revisão humana. A redação por regex é insuficiente para nomes, endereços, contexto, dados indiretos, segredos comerciais, documentos de terceiros e material protegido. Antes de cada chamada, o gateway deve fazer classificação de dados, base legal/finalidade, licença/proveniência, transferência internacional, retenção e autorização da organização.

Os três pontos que chamam modelo (`structure_need`, `draft_document`, `summarize_project`) podem somente produzir rascunho sobre base determinística. Devem permanecer sem ferramenta, sem escrita no banco, sem assinatura, sem aprovação, sem envio, sem elegibilidade e sem cálculo de compatibilidade. As faixas 0–4 da auditoria são uma classificação de risco interna; não devem ser descritas como classificação legal brasileira.

O CI deve bloquear qualquer rota de IA sem `prompt_key`, `prompt_version`, modelo/provedor, classificação de entrada, `legal_basis_ref`, consentimento ou instrução aplicável, destino internacional e resultado de revisão. O registro deve diferenciar `local_only`, `fallback_local`, `invalid_output`, `provider_error`, `blocked_policy`, `quota_exceeded` e `budget_exceeded`; “ok” não pode ser gravado quando a resposta externa foi descartada.

### INTENT_ENGINE

`INTENT_ENGINE.md` e `engines/solutions/intent.py` descrevem parser determinístico versionado, gramática/tesauro, correção fuzzy exibida ao usuário, território, orçamento, prazo, população, ODS/ESG e intenção (`find_solution`, `explore_idea`, `invest`, `replicate` etc.). Isso é uma interpretação de consulta, não IA generativa. A correção deve sempre ser reversível e confirmável.

Limites:

- não transformar `intent`, `population`, `invest`, território ou orçamento inferidos em atributo permanente de pessoa sem finalidade, base legal, retenção e possibilidade de correção;
- não inferir dado sensível, condição de saúde, opinião política, vulnerabilidade ou crédito a partir de termos;
- não usar uma correção fuzzy como fato declarado;
- não usar etapa de funil, favorito, visualização ou intenção privada como reputação, elegibilidade ou ranking público;
- manter identidade privada por padrão, como o motor já propõe, e exibir contagens agregadas apenas quando o risco de reidentificação for aceitável;
- guardar versão do parser, termos aceitos, correção exibida, ação do usuário e possibilidade de apagar o histórico;
- impedir que `invest` seja promessa de financiamento, indicação de solvência ou decisão de crédito.

### MATCH_ENGINE: elegibilidade separada de score

O núcleo atual tem boa separação: requisitos determinísticos antes dos sinais; bloqueadores com código e correção; obrigatório desconhecido não vira elegível; certificação declarada não satisfaz certificação exigida; saída `eligible | needs_review | blocked`; plano, voucher, pagamento e atributos sensíveis estão na lista proibida.

Os limites atuais são:

- **elegibilidade:** `blocked` se qualquer requisito obrigatório estiver `unmet`; `needs_review` se faltar dado obrigatório ou não houver nota confiável; `eligible` somente quando os requisitos aplicáveis estiverem atendidos e verificados. Elegibilidade não significa aprovação, financiamento ou contratação;
- **score de compatibilidade:** faixa numérica 0–100, somente se a confiança dos sinais conhecidos for pelo menos 50. Abaixo de 50, `score=null` e `missing_data` deve explicar a lacuna;
- **estado de feed:** `prioritaria` para score ≥75 e elegível; `compativel` para score ≥55 e elegível; abaixo disso, estado de potencial com lacunas. Os limiares 50/55/75 são hipóteses de produto, não presunções legais;
- **pesos:** `match_weights.json` está marcado `hipotese_a_calibrar`; qualquer override por chamada precisa de aprovação, versão, justificativa, registro de quem alterou, teste de impacto e comparação com a régua anterior;
- **proibição de efeito automático:** a saída não pode bloquear cadastro, negar benefício, selecionar vencedor, criar obrigação financeira ou ordenar exposição sem ato humano autorizado, explicação e canal de contestação;
- **fairness:** não usar proxies de raça, gênero, deficiência, religião, orientação sexual, saúde, idade, renda ou território como substitutos indevidos de atributo sensível; medir taxas de bloqueio, `needs_review`, score e erro por grupos somente quando houver base legítima, governança e proteção adequada;
- **auditoria:** `match_runs` deve preservar entradas minimizadas, versão das regras/pesos/taxonomia, evidências, `computed_at`, resultado e revisão humana. Não converter o vetor `features` em treino futuro por default; isso é nova finalidade e exige governança de dados.

### Scoring de soluções e busca

O motor de soluções distingue:

- `maturity`: completude estrutural do cadastro, 0–100; **não mede qualidade, eficácia ou impacto**;
- `evidence`: 0–100 ou `None`; ausência de evidência é ausência, não zero disfarçado;
- `replicability`: score somente com confiança mínima 50; fatores incluem declarações do autor, documentação e evidência;
- `relevance`: busca com pesos iniciais de texto 30, ODS/ESG 20, população 15, território 10, orçamento 10, maturidade 5, replicabilidade 5 e evidência 5; bônus de 5 e penalidade de 10 são hipóteses da configuração.

A implementação renormaliza sinais conhecidos. Há uma lacuna: a configuração explicita `min_confidence` para replicabilidade, mas não um limiar equivalente para `relevance`; assim, uma relevância pode ser exibida mesmo com base estreita. Antes de usar relevância para ordenar feed, adicionar `min_confidence_for_relevance` (recomendação inicial: 50, sujeita a validação), retornar `score=null` abaixo dele e mostrar os dados faltantes. A ordenação por relevância deve ser explicável e nunca se converter em reputação, elegibilidade, prova de impacto ou garantia de replicação.

A busca da Central usa FTS, similaridade de título, vocabulário de tópicos, contexto e audiência; pesos 0,40/0,20/0,25/0,10/0,05, `MIN_SCORE=0,18` e `ANSWER_MIN=0,30` são hipóteses iniciais. Não há embeddings. Esses números devem aparecer como versão/configuração e ser calibrados com avaliação de qualidade, sem aprender silenciosamente de cliques.

### Reputação

O módulo `impact/reputation.py` corretamente rejeita nota única. Ele calcula dimensões, separa observação, verificação e autodeclaração, não usa plano/assinatura/pagamento ou LLM, não pontua órgão público, não expõe perfil público de pessoa física, não publica valor quando a base ou confiança é insuficiente e oferece contestação visível.

Esses limites devem ser normativos do produto:

- nenhuma dimensão de reputação entra em busca, match, recomendação, elegibilidade, exposição ou preço;
- `band` e `confidence` significam confiança na base observada, não qualidade moral, solvência, risco de fraude, impacto causal ou “nota da organização”;
- `COUNT_ONLY` fica como contagem, sem denominador inventado;
- organização nova começa sem medida, não com nota baixa;
- autodeclaração é exibida como autodeclaração; validação por terceiro tem fonte, data, escopo e vencimento;
- correção/contestação pausa ou sinaliza o uso da dimensão contestada em qualquer tela comparativa;
- snapshots append-only preservam o histórico, mas não devem eternizar dado pessoal além da finalidade e retenção aprovadas.

É proibido chamar esse mecanismo de `rating`, `score de confiança`, `selo de integridade`, “ranking das melhores OSCs” ou “reputação alta” sem explicar a dimensão, a base, as limitações e a ausência de efeito automático.

### Recommendation Engine

`network/recommendation.py` faz uma pergunta diferente de match: “qual próxima ação?” Lê diagnóstico, prontidão, riscos, propostas e dados públicos; herda confiança; informa `rationale`, evidência, versão e link. Não usa favorito privado. Isso é uma boa fronteira.

Os limiares de implementação — prontidão de projeto <70, documentação <80, funding readiness ≥60, evidência <60, risco alto/crítico e prioridades 70–100 — são **hipóteses de UX/operação**, não decisão regulatória. `priority` deve ser rotulada como prioridade de tarefa, não valor da organização ou chance de receber financiamento.

A recomendação de conteúdo da Central inclui “muito consultado por organizações como a sua”, baseada em `view_count`. É recomendação de popularidade, ainda que não use favorito privado. Deve informar o motivo, oferecer controles de personalização/opt-out quando houver perfilamento, impor limites de frequência, excluir conteúdo vencido/demonstrativo de trilhas oficiais e testar diferenças de exposição entre perfis. Nenhuma recomendação pode ser ordenada por reputação, plano pago, assinatura, preço ou atributo sensível.

### Assistente extrativo

O assistente de `knowledge.py` é extrativo: pesquisa somente artigos/FAQs publicados, exige `ANSWER_MIN=0,30`, devolve no máximo a resposta montada do melhor item e fontes dos três primeiros, informa `grounded=true`, `ai_used=false`, versão, origem, demo e revisão pendente; abaixo do limiar recusa e oferece chamado. Isso é mais seguro que um chatbot, mas a palavra “grounded” não significa que o conteúdo seja juridicamente correto.

Limites obrigatórios:

- usar apenas conteúdo publicado, aprovado por quatro olhos, dentro da validade e autorizado para o público e contexto; bloquear resposta baseada em `demo=true` quando a pergunta pedir regra oficial;
- se origem for `third_party` ou `educational`, dizer isso; não chamar de “base oficial”;
- conteúdo regulatório vencido deve ser bloqueado ou fortemente sinalizado antes de compor resposta, não apenas avisado depois;
- fonte, título, versão, autor/revisor, data de revisão e URL devem ser clicáveis e preservados;
- não resumir uma fonte para além do que a licença permite nem reproduzir trecho substancial;
- não responder sobre elegibilidade, financiamento, conformidade, impacto comprovado, direito autoral ou segurança como conclusão; encaminhar para fonte e revisão humana;
- registrar hash da pergunta, fontes usadas, versão, score, motivo de recusa e feedback, sem corpo livre desnecessário; permitir correção e eliminação conforme LGPD;
- incluir teste que confirme que pergunta com prompt injection dentro do conteúdo não vira instrução e que a resposta nunca contém texto fora dos campos extraídos.

## Mapa de obrigações para o release

| Tema | Classificação da fonte | Obrigação/risco | Requisito mínimo do produto |
|---|---|---|---|
| Base legal, finalidade, necessidade e transparência | Lei vigente: LGPD [1] | Cada chamada, perfil, log, recomendação e transferência é tratamento com finalidade e hipótese legal | Registro de tratamento por feature; notice; base legal; minimização; prazo; controlador/operador |
| Decisão automatizada | Lei vigente: LGPD art. 20 [1] | Revisão solicitável e informação sobre critérios/procedimentos; auditoria possível por discriminação | Endpoint de revisão; razão e versões; resposta em linguagem simples; contestação; preservação do caso |
| Segurança e incidente | Lei/regulamento vigente: LGPD art. 46–48, Res. ANPD 15/2024 [1][4][20] | Prevenir dano e comunicar risco/dano relevante | IRP, detecção, classificação, responsável, evidência, prazos e templates para ANPD/titulares |
| Encarregado | Lei/regulamento vigente: LGPD art. 41, Res. ANPD 18/2024 [1][4] | Canal e atribuições do encarregado | Nome/contato publicados; fila de titulares e escalonamento |
| Modelo externo e transferência | Regulamento vigente: Res. ANPD 19/2024 [4][5] | Provedor externo pode envolver transferência internacional e operador/suboperador | Contrato, país, cláusula/mecanismo, retenção/deleção, subprocessadores, transparência em português |
| Conteúdo intermediado | Lei/decreto vigente: Marco Civil, Dec. 12.975/2026 [15][16][17] | Se houver conteúdo de terceiros, deveres de transparência, canal e cuidado podem incidir | Classificação de atividade, canal permanente, gestão de denúncias, regras públicas, logs e relatório |
| Violência digital e conteúdo íntimo | Decreto vigente: Dec. 12.976/2026 [19] | Remoção acelerada, canal, contestação e bloqueio de geração vedada se aplicável | Política e rota de emergência; marcação/reenvio; preservação sem revitimização; teste de bloqueio |
| Crianças/adolescentes | Lei vigente: Lei 15.211/2025 [18] | Aplica-se a acesso provável; recomendações de conteúdo e perfilamento recebem risco reforçado | Análise de escopo; idade/experiência apropriada; privacidade por padrão; proteção de recomendação; canal |
| Direitos autorais | Lei vigente: Lei 9.610/1998 [13] | Não presumir licença para treino, reprodução ou saída | Ledger de direitos; licença/condições; bloqueio de uso incompatível; atribuição/proveniência; takedown |
| PL 2338/2023 | Projeto não vigente [6][7][8] | Horizonte de alto risco, explicação, revisão humana e conteúdo protegido; texto pode mudar | Feature flags e arquitetura preparada, sempre rotulada como requisito futuro/hipótese |
| OECD/UNESCO/NIST/ISO | Referências voluntárias [9][10][11][12] | Princípios não substituem direito brasileiro | Matriz de controles e evidências; não usar “certificado/conforme” sem base contratual/certificação |

## Requisitos de produto antes de qualquer publicação

1. **Gate de ativação:** `AI_PROVIDER=local` ou `disabled` por padrão. Ativação externa exige decisão registrada, base legal, RIPD quando o risco justificar, contrato, transferência, política de retenção, responsável e teste de deleção.
2. **Inventário único:** todo motor, rota, versão, entrada, saída, risco, fonte de dados, “nunca decide”, revisão e efeito deve sair do registry e ser conferido pelo CI.
3. **Decisão vs. assistência:** cada tela deve indicar se o resultado é dado, inferência, sugestão, ranking, recomendação de ação ou decisão humana. “Recomendação” que produz efeito de acesso deve migrar para fluxo de revisão e art. 20.
4. **Explicação e contestação:** mostrar entradas efetivamente usadas, dados ausentes, pesos/versão, regras bloqueadoras, fonte, data, confiança, responsável e como contestar. Segredo comercial não autoriza apagar toda explicação.
5. **Revisão humana real:** revisor não pode ser o próprio decisor automático; deve ter autoridade, prazo, motivo, trilha e possibilidade de alterar o resultado. Não chamar registro de conferência de assinatura digital ICP-Brasil.
6. **No-write boundary:** saídas de modelo não escrevem estado, não alteram score, não mudam elegibilidade, não publicam conteúdo e não acionam cobrança sem transação humana autorizada.
7. **Recomendação sem manipulação:** remover plano/pagamento/reputação de sinais; justificar cada item; não usar atributo sensível/proxy; permitir não personalizar quando o tratamento não for necessário; limitar exposição repetitiva.
8. **Conteúdo confiável:** fluxo draft → review → approved → published; quatro olhos; versão imutável; origem, licença, autor/revisor, data, validade, demo e público; bloqueio de conteúdo regulatório vencido.
9. **Proveniência e direitos:** cada documento/modelo deve ter fonte, titular, licença, finalidade, acesso, transformação, retenção e possibilidade de revogação. Sem isso, não enviar a provedor, não treinar, não indexar publicamente e não afirmar “livre para uso”.
10. **Crianças e conteúdo ilícito:** concluir análise de Lei 15.211/2025 e Decretos 12.975/12.976 antes de publicação pública; não usar “não coletamos crianças” como única conclusão; manter canal de emergência e preservação de prova sem reexposição.
11. **Contrato e transparência:** corrigir minutas jurídicas, publicar política de IA/conteúdo/privacidade, informar provedores e países, responder titulares e manter encarregado.
12. **Rótulos permitidos:** “aderência à tese declarada”, “completude do cadastro”, “evidência cadastrada”, “autodeclarado”, “requer revisão”, “ação sugerida”, “extraído de fonte publicada”.

## Requisitos de dados

- Manter um registro de tratamento com finalidade, categorias, origem, base legal, titularidade, controlador, operador, país, retenção, descarte, perfilamento, compartilhamento e direitos.
- Separar dados de organização, pessoa física, usuário que pesquisou, documento, conteúdo público, conteúdo privado e saída de modelo. Não assumir que CNPJ, nome institucional, projeto ou orçamento são anônimos.
- Não coletar ou inferir dados sensíveis para match, reputação ou recomendação. Se um documento inserido contiver dado sensível, o pipeline deve detectar, restringir, redigir ou pedir base específica.
- Guardar somente hash/tamanho da entrada de IA quando suficiente; se for necessário guardar texto para auditoria, limitar finalidade, acesso, prazo e criptografia. Hash de consulta não elimina o tratamento da consulta.
- `match_runs`, `ai_usage`, `recommendations`, `solution_intents`, visualizações e contestação devem ter retenção explícita, dono, acesso RLS, exportação, correção e eliminação/anonymização compatíveis com obrigação de prova.
- Para provedores externos, guardar identificação da transferência, payload classificado, redações, destino, versão do contrato, resposta de deleção e subprocessadores. Não aceitar “não treinamos” sem evidência contratual/configuração verificável.
- Para conteúdo, registrar licença e condições de uso em formato estruturado; `all_rights_reserved`, ausência de licença ou origem desconhecida devem ser conservadores.
- Para avaliação de fairness, usar somente dados de grupo que tenham finalidade e base legítimas, acesso restrito, agregação e proteção contra reidentificação; não criar atributos proibidos apenas para produzir um gráfico.
- Para crianças, aplicar privacidade por padrão, minimização, sinal de idade somente para finalidade necessária e nenhum perfilamento/segmentação de recomendação não autorizado.

## Testes e controles de aceitação

**Arquitetura e segurança:** CI deve reprovar motor determinístico importando gateway; rota não registrada; motor sem versão; modelo fora de `llm_assisted`; escrita de modelo no banco; uso de billing, plano, pagamento ou sinal sensível no match/reputação; provider externo sem gate; conteúdo fora de RLS; cache cruzando organização.

**LGPD e direitos:** testes de acesso, correção, exclusão/anonymização, revisão art. 20, exportação, oposição quando aplicável, canal do encarregado, retenção e incidente. O caso de revisão deve preservar entrada, versão e razão, mas não expor segredo comercial além do necessário.

**Match/scoring:** casos de blocker obrigatório; unknown; certificação declarada; score exatamente 49/50/54/55/74/75; confiança baixa; peso zero; override customizado; ausência de dado; projeto grande com marco; plano pago idêntico ao gratuito; proxy sensível; igualdade de resultado para entradas iguais; contraprovas que detectem nota inventada.

**Reputação:** organização nova sem número; confiança insuficiente; órgão público; pessoa física; dimensão count-only; autodeclaração vs validação; contestação aberta; mudança de faixa; tentativa de usar reputação em ranking/match/recomendação; snapshot com versão.

**Recomendação:** ausência de projeto; thresholds 60/70/80; risco crítico; proposta aguardando; link inexistente; popularidade vs favorito privado; opt-out; conteúdo vencido/demo; não influência por plano, pagamento ou reputação; explicação e evidência em cada item.

**Assistente:** `score=0,299`, `0,30` e fonte stale; origem `third_party`; `demo=true`; pergunta sobre lei; prompt injection em artigo; texto fora dos campos extraídos; no answer quando não houver base; fontes e versão; resposta que tenta declarar “conformidade” ou “elegibilidade”. O teste deve impedir a frase “base oficial” quando a fonte não for oficial.

**Modelos externos:** servidor falso para protocolo, mas também teste controlado de cada provedor contratado antes de habilitar; invalid JSON; números não presentes; prompt injection; exfiltração; timeout/retry; fallback local; deleção; treinamento desativado; país/subprocessador; custo sem preço; concorrência de crédito; falha que não transforma erro em `ok`.

**Qualidade e impacto:** conjunto ouro separado por idioma, território, porte, tipo de organização e conteúdo; métricas de precisão/recall para busca e intenção; calibração de score; taxa de `needs_review`; taxa de bloqueio; falsos positivos/negativos; reclamações; contestação; distribuição de exposição; drift. Não chamar dez invariantes determinísticas de validação de modelo de produção.

## Claims proibidos ou condicionados

Não publicar, no estado atual, os seguintes claims sem evidência específica e revisão jurídica/técnica:

- “Plataforma de IA”, “IA confiável”, “IA ética”, “IA sem viés”, “IA em conformidade com LGPD” ou “certificada pela ISO/NIST/UNESCO/OCDE”. O que existe é plataforma de governança/impacto com assistência determinística e pontos opcionais de modelo em rascunho.
- “Elegível”, “aprovado”, “financiável”, “tem alta chance”, “melhor organização”, “reputação alta”, “baixo risco”, “impacto comprovado”, “resultado validado” ou “matching objetivo” quando a saída for score, banda, recomendação ou autodeclaração.
- “A recomendação é neutra/imparcial”, “o algoritmo não discrimina” ou “o score é científico”. Pesos são hipóteses e ainda não têm calibração real; ausência de atributo sensível não prova ausência de viés.
- “O modelo não usa dados do cliente”, “nenhum dado sai do Brasil”, “conteúdo não é armazenado” ou “não há transferência internacional” sem configuração, contrato, logs e provedor efetivamente auditados.
- “Conteúdo público é livre para treinar”, “temos licença para todos os dados”, “saída de IA é de nossa autoria” ou “resumo é uso permitido” sem ledger de direitos e análise da Lei 9.610/1998.
- “Assistente oficial”, “resposta correta”, “parecer”, “decisão jurídica”, “fonte verificada” ou “resposta completa”. O assistente é extração de conteúdo publicado e pode estar desatualizado ou ser terceiro.
- “Seguro”, “anônimo”, “100% auditável” ou “sem risco”. Hash, RLS, logs e testes reduzem risco; não eliminam dado pessoal, copyright, incidente, viés ou erro.
- “Revisão humana garantida” quando houver apenas `human_review_required=true` no payload sem fila, revisor, decisão, prazo e trilha implementados.

## Lacunas prioritárias

**P0 — bloquear publicação/ativação externa:** (i) atualizar documentos e registry para v0.26.0; (ii) decidir e registrar papéis LGPD; (iii) aprovar política, RIPD/DPIA quando aplicável, bases legais, encarregado e contratos; (iv) gate de transferência internacional; (v) ledger de direitos autorais/proveniência; (vi) classificação de conteúdo de terceiros e escopo dos Decretos 12.975/12.976 e Lei 15.211; (vii) corrigir “base oficial” do assistente; (viii) impedir score de relevância sem confiança mínima; (ix) criar revisão/contestação real para efeitos relevantes.

**P1 — antes de liberar uso amplo:** (i) benchmark real de intenção, busca, match e recomendações; (ii) testes de fairness e impacto; (iii) monitoramento de drift e qualidade; (iv) age/safety assessment se houver acesso provável por menores; (v) canais de denúncia e incident response; (vi) política de copyright para uploads, saída e modelos; (vii) retenção e eliminação verificadas; (viii) contrato com provedor e teste de deleção/sem treino.

**P2 — melhoria contínua:** (i) calibração de pesos com dados reais e governança de mudança; (ii) feedback de qualidade sem usar clique como proxy automático de mérito; (iii) auditoria independente; (iv) alinhamento documentado com NIST/ISO/OECD/UNESCO; (v) atualização diante do PL 2338/2023 e atos da ANPD.

## Questões abertas que impedem claims definitivos

1. Qual é a finalidade e base legal separada para intent, visualização, recomendação, reputação, match_runs, uso de IA e conteúdo público?
2. A plataforma será provedora que intermedeia conteúdo de terceiros para fins dos Decretos 12.975/12.976 e da Lei 15.211/2025? Qual é o público provável e há menores?
3. Quais provedores, países, subprocessadores e contratos existirão quando `anthropic` ou `openai_compatible` forem habilitados? Haverá treinamento, retenção ou revisão humana do provedor?
4. Quem é titular/controlador de documentos e saídas? O contrato permite resumo, indexação, embedding, treinamento, compartilhamento e remoção?
5. Que decisões concretas podem ser influenciadas por `eligible`, `score`, `band`, `priority` ou recomendação? Quem revisa, em quanto tempo e com que poder de alterar?
6. Quais conjuntos reais serão usados para calibrar pesos e medir disparidade? Quais grupos podem ser avaliados legalmente sem criar novo risco?
7. Como o produto identifica conteúdo jurídico/regulatório vencido e impede resposta sem revisão? Como diferencia `official`, `educational`, `third_party` e `demo` na API pública?
8. Quais prazos de retenção e rotinas de exclusão se aplicam a `ai_usage`, logs de intenção, match_runs, snapshots de reputação, contestação, documentos e backups?

## Referências numeradas

[1]: https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm "Lei nº 13.709, de 14 de agosto de 2018 — Lei Geral de Proteção de Dados Pessoais" — Presidência da República/Planalto; 14/08/2018, texto vigente consultado em 08/10/2026; sustenta princípios, bases legais, direitos do titular, art. 20 sobre decisões automatizadas, segurança, RIPD, encarregado e responsabilização.

[2]: https://www.gov.br/participamaisbrasil/tomada-de-subsidios-inteligencia-artificial-e-revisao-de-decisoes-automatizadas "Tomada de Subsídios: Inteligência Artificial e Revisão de Decisões Automatizadas" — Autoridade Nacional de Proteção de Dados; abertura 06/11/2024, encerramento 24/01/2025; sustenta o escopo da consulta sobre art. 20, explicabilidade, legítimo interesse, dados sensíveis, crianças, revisão e canais, sem criar regra normativa.

[3]: https://www.gov.br/anpd/pt-br/assuntos/regulacao/agenda-regulatoria-1 "Agenda Regulatória" — ANPD; agenda 2025–2026 aprovada em 09/12/2024 e alterada em 22/12/2025; sustenta a natureza de planejamento, acompanhamento e transparência da agenda, não de lei geral de IA.

[4]: https://www.gov.br/anpd/pt-br/acesso-a-informacao/institucional/atos-normativos/regulamentacoes_anpd "Regulamentações da ANPD" — ANPD; página consultada em 08/10/2026; sustenta a vigência listada das Resoluções 15/2024 (incidente), 18/2024 (encarregado) e 19/2024 (transferência internacional), entre outras.

[5]: https://www.gov.br/anpd/pt-br/acesso-a-informacao/institucional/atos-normativos/regulamentacoes_anpd/resolucao-cd-anpd-no-19-de-23-de-agosto-de-2024 "Resolução CD/ANPD nº 19, de 23 de agosto de 2024 — Regulamento de Transferência Internacional de Dados" — ANPD; 23/08/2024, com retificação de 18/08/2025; sustenta cláusulas-padrão, adoção integral, transparência em português, países, finalidades, agentes, segurança e direitos.

[6]: https://www25.senado.leg.br/web/atividade/materias/-/materia/157233 "PL 2338/2023 — Marco Legal da Inteligência Artificial" — Senado Federal; matéria aprovada pelo Plenário, remetida à Câmara em 17/03/2025, situação consultada em 07/10/2026; sustenta que o projeto foi aprovado no Senado e não é lei vigente.

[7]: https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao=2487262 "PL 2338/2023 — ficha de tramitação" — Câmara dos Deputados; apresentação 17/03/2025, status consultado em 08/10/2026; sustenta que aguardava parecer na Comissão Especial e que seguia em tramitação na Câmara.

[8]: https://www.camara.leg.br/proposicoesWeb/prop_mostrarintegra?codteor=2881712&filename=Avulso%20PL%202338/2023 "Avulso/inteiro teor do PL 2338/2023" — Câmara dos Deputados; apresentação do texto na Câmara em 17/03/2025; sustenta, como texto proposto não vigente, direitos de informação, não discriminação, explicação, contestação, revisão humana e disposições projetadas sobre conteúdo protegido/mineração de textos e dados

[9]: https://www.oecd.org/en/topics/sub-issues/ai-principles.html "AI Principles" — Organisation for Economic Co-operation and Development; princípios adotados em 2019 e atualizados em 2024; sustenta direitos humanos, valores democráticos, transparência, explicabilidade, robustez, segurança, accountability e rastreabilidade como referência intergovernamental.

[10]: https://www.unesco.org/en/artificial-intelligence/recommendation-ethics "Recommendation on the Ethics of Artificial Intelligence" — UNESCO; adotada pela Conferência Geral em 23/11/2021; sustenta proporcionalidade, segurança, privacidade, governança, responsabilidade/auditabilidade, transparência, supervisão humana, sustentabilidade, letramento e não discriminação como recomendação internacional, não lei brasileira.

[11]: https://www.nist.gov/itl/ai-risk-management-framework "AI Risk Management Framework (AI RMF 1.0)" — National Institute of Standards and Technology; 26/01/2023; sustenta um framework voluntário organizado em Govern, Map, Measure e Manage para riscos de IA.

[12]: https://www.iso.org/standard/81230.html "ISO/IEC 42001:2023 — Information technology — Artificial intelligence — Management system" — International Organization for Standardization/IEC; publicada em dezembro de 2023; sustenta requisitos de sistema de gestão de IA, melhoria contínua, responsabilidades, avaliação e gestão de riscos como norma técnica, não como lei brasileira.

[13]: https://www.planalto.gov.br/ccivil_03/leis/l9610.htm "Lei nº 9.610, de 19 de fevereiro de 1998 — Lei de Direitos Autorais" — Presidência da República/Planalto; 19/02/1998, texto vigente consultado em 08/10/2026; sustenta direitos patrimoniais/morais, autor, obras protegidas, limitações, reprodução, distribuição e ausência de licença geral para tratar conteúdo protegido como livre para treinamento.

[14]: https://revistas.ufpr.br/rrddis/article/view/93903 "Mineração de dados, inteligência artificial e direitos autorais no Brasil" — Revista de Direito, Estado e Telecomunicações/UFPR; artigo acadêmico consultado em 08/10/2026; sustenta a controvérsia e as lacunas da literatura sobre mineração de textos/dados, IA generativa e direitos autorais, sem constituir norma vigente.

[15]: https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2014/lei/l12965.htm "Lei nº 12.965, de 23 de abril de 2014 — Marco Civil da Internet" — Presidência da República/Planalto; 23/04/2014, texto vigente consultado em 08/10/2026; sustenta privacidade, proteção de dados, transparência, liberdade de expressão, guarda e fornecimento de registros e regras gerais de aplicações de internet.

[16]: https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2026/decreto/d12975.htm "Decreto nº 12.975, de 20 de maio de 2026" — Presidência da República/Planalto; 20/05/2026; sustenta a atualização do regulamento do Marco Civil e deveres condicionais de provedores de aplicações que intermedeiam conteúdo de terceiros, transparência, segurança, gestão de riscos e canais.

[17]: https://www.gov.br/anpd/pt-br/assuntos/marco-civil-da-internet "Marco Civil da Internet" — ANPD; página institucional consultada em 08/10/2026; sustenta a apresentação administrativa dos Decretos 12.975/2026 e 12.976/2026, sua aplicação a provedores de aplicações e o enfoque de fiscalização/governança, transparência, prevenção e mitigação.

[18]: https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2025/lei/l15211.htm "Lei nº 15.211, de 17 de setembro de 2025 — Estatuto Digital da Criança e do Adolescente" — Presidência da República/Planalto; 17/09/2025, entrada em vigor fixada para 17/03/2026; sustenta o âmbito de produtos direcionados ou de acesso provável por crianças/adolescentes, perfilamento, mediação parental, segurança, classificação, canais e obrigações proporcionais.

[19]: https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2026/decreto/d12976.htm "Decreto nº 12.976, de 20 de maio de 2026" — Presidência da República/Planalto; 20/05/2026, vigência 60 dias após publicação; sustenta definição de conteúdo íntimo inclusive gerado/modificado por IA, remoção em até duas horas após notificação, marcação contra reenvio, canal permanente e bloqueio de solicitações proibidas.

[20]: https://www.gov.br/anpd/pt-br/assuntos/comunicacao-de-incidentes-de-seguranca-cis "Comunicação de Incidentes de Segurança" — ANPD; página administrativa consultada em 08/10/2026; sustenta orientação sobre avaliação de risco/dano relevante, comunicação à ANPD e aos titulares, canal, responsável e evidências de resposta a incidentes.
