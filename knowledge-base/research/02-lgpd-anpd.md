# LGPD, ANPD e proteção de dados — auditoria e controles para o release v0.26.0

**Data de corte da pesquisa:** 8 de outubro de 2026.  
**Escopo:** LGPD, ANPD e proteção de dados pessoais no produto Impacto. Este relatório é pesquisa de produto e governança; não é parecer jurídico personalizado e não declara conformidade.

## Escopo e regra de leitura

A análise cobre papéis de agentes, bases legais, dados sensíveis, crianças e adolescentes, direitos dos titulares, agentes de pequeno porte, encarregado, incidentes, RIPD, anonimização, transferência internacional, decisões automatizadas, segurança e retenção. A classificação abaixo é deliberada:

- **Lei/regulamento vigente:** obrigação jurídica ou ato normativo vinculante, sujeito ao texto oficial e às alterações posteriores.
- **Orientação administrativa:** guia, página de serviço, enunciado ou estudo da ANPD. Orienta a interpretação e a demonstração de diligência, mas não é uma lei nem substitui a análise do caso concreto.
- **Padrão voluntário/literatura:** prática técnica, norma voluntária ou literatura acadêmica. Pode apoiar a prestação de contas, mas não transforma o produto em “certificado LGPD”.
- **Hipótese de produto:** desenho proposto neste relatório. Só deve ser apresentado como entregue depois de implementado, testado e documentado.

A LGPD exige finalidade, adequação, necessidade, livre acesso, qualidade, transparência, segurança, prevenção, não discriminação e responsabilização/prestação de contas. A dispensa de consentimento não elimina esses princípios nem os direitos do titular. [1]

## Estado atual do release que precisa ser corrigido

O release v0.26.0 está tecnicamente descrito como **“BASE TÉCNICA FECHADA”**, não foi publicado em loja ou domínio, não possui cobrança real nem provedores reais de pagamento, fiscal, WhatsApp, mapas ou IA ligados. Isso é importante para o risco operacional atual, mas **não é prova de conformidade**: o código, os seeds, a demonstração e os contratos preparados já definem tratamentos que precisam estar governados antes da publicação ou de qualquer uso real.

### Auditoria dos arquivos internos

| Artefato auditado | O que existe | Correção necessária |
|---|---|---|
| `docs/LGPD.md` (v0.7.0) | Exportação, eliminação/anonimização de conta, consentimentos versionados, edição, agregação de beneficiários, ausência deliberada de campos sensíveis em formulários, logs sem corpo de IA, retenções técnicas, RLS, arquivos privados e compartilhamento controlado. | O texto ainda diz que bases legais, prazos de retenção jurídicos, RIPD, contrato de operador, canal do encarregado e crianças estão “pendentes”. Deve virar um inventário versionado por operação; não se pode afirmar que não há dado sensível porque documentos de OSC, mensagens, anexos e entradas livres podem contê-lo. “Anonimiza usuário” também precisa indicar quais registros permanecem, qual exceção legal justifica a conservação e qual teste impede reidentificação. |
| `PRIVACY_VISIBILITY_MATRIX.md` (v0.16.0) | Boa arquitetura de mínimo privilégio: visibilidade separada de relação, RLS + papel, projeção pública por allowlist, `NEVER_PUBLIC`, falha de gravação para chaves proibidas, 404 para perfil suspenso, vedação de filtro/inferência por grupo beneficiário e ocultação do denunciante. | A versão é anterior ao v0.26.0 e é uma matriz de autorização, não um ROPA. Acrescentar finalidade, base legal, controlador/operador, categoria de titulares, sensibilidade, retenção, compartilhamento, país/suboperador e evidência de exercício de direitos para cada exposição. Testar também anexos, exportações, busca, notificações, logs, backups e respostas de erro. |
| `docs/LEGAL_FRAMEWORK.md` | Onze documentos legais estão `draft`; aceite fica bloqueado enquanto não houver aprovação e versão imutável. A trilha guarda hash do texto e anonimiza IP/agente de usuário de aceite em certas hipóteses. O encarregado permanece como campo de minuta. | Não coletar aceite de textos não aprovados. Publicar política de privacidade e aviso por finalidade somente após revisão responsável, definir controlador e operadores por operação, formalizar encarregado ou canal substituto e registrar cláusulas de tratamento com fornecedores. |
| `KNOWLEDGE_HUB.md` | Conteúdo regulatório exige fonte e data; os seeds são `demo=true`; assistente é extrativo, ancorado e recusa quando não há base oficial. | Manter esse padrão. Artigos LGPD publicados devem separar lei, resolução, orientação e hipótese de produto, ter proprietário, data de revisão, URL oficial e alerta de que não constituem aconselhamento jurídico. |
| `docs/PROCUREMENT.md` | Benchmark usa cotações do pedido; o sinal é “preço possivelmente fora do padrão”, nunca “fraude”; exceção exige segunda aprovação. | Reaproveitar a disciplina contra claims excessivos. Se preço, risco ou readiness for calculado sobre pessoas identificáveis, catalogar a decisão, base, explicação, revisão humana e não discriminação. |

**Conclusão da auditoria:** há controles técnicos valiosos, mas o documento atual não sustenta as frases “LGPD compliant”, “sem dado sensível”, “sem transferência internacional”, “DPO/encarregado presente”, “RIPD concluído” ou “nenhum tratamento de criança”. O release deve usar linguagem de **controles implementados + pendências**, até que os gates abaixo estejam fechados.

## Atualização normativa e institucional

A Lei nº 13.709/2018 continua sendo a base. O texto compilado do Planalto define dado pessoal, sensível, anonimizado, controlador, operador, encarregado, tratamento, transferência internacional e RIPD; a versão atual também incorpora alterações da Lei nº 15.352/2026. [1] A Lei nº 15.352/2026 transformou a ANPD em autarquia de natureza especial vinculada ao Ministério da Justiça e Segurança Pública e alterou a estrutura normativa da Autoridade; o produto deve usar a identificação institucional vigente, sem tratar a mudança administrativa como dispensa de obrigações. [15]

A página oficial de regulamentações da ANPD marca como vigentes, entre outras, as Resoluções CD/ANPD nº 2/2022 (pequeno porte), nº 4/2023 (dosimetria), nº 15/2024 (incidentes), nº 18/2024 (encarregado) e nº 19/2024 (transferência internacional). A própria página registra a alteração/retificação aplicável à Resolução nº 19 e a alteração da Resolução nº 2 pela nº 15. [6]

## Mapa de obrigações e controles de produto

| Tema | Regra vigente ou orientação que sustenta | Requisito concreto no Impacto | Evidência/gate |
|---|---|---|---|
| Papéis | Controlador decide finalidades e elementos essenciais; operador trata em nome do controlador. A qualificação é funcional e depende da operação, não apenas do contrato. [1] [10] | Criar registro por tratamento com controlador, operador, suboperador, instruções, finalidade, elementos essenciais, categorias de dados e responsabilidade. No marketplace, cada fluxo deve dizer se a plataforma decide a finalidade ou apenas executa instruções. | `ROPA` versionado; contratos; teste que impede “operador” sem controlador e instrução; revisão humana por tratamento. |
| Bases legais | Arts. 7 e 11 trazem bases gerais e sensíveis; consentimento deve ser específico, demonstrável, revogável e não genérico. Interesse legítimo exige finalidade, necessidade, balanceamento, transparência e salvaguardas. [1] [9] | Campo obrigatório `legal_basis` por finalidade, separado de `consent`; consentimento guarda texto/versão/hash, finalidade, data, prova e revogação. Para legítimo interesse, anexar teste LIA, oposição e salvaguardas; não usar consentimento como checkbox universal. | Linter de tratamento sem base; teste de revogação; exportação do histórico; revisão do LIA/RIPD antes de ativar a finalidade. |
| Princípios | Finalidade, adequação, necessidade, livre acesso, qualidade, transparência, segurança, prevenção, não discriminação e accountability. [1] | Catálogo de dados mínimos; aviso por finalidade; política de qualidade/correção; log de justificativa de compartilhamento; indicador de dados desconhecidos que não vira zero. | Testes de minimização e finalidade; amostra de titulares; auditoria do log de decisão. |
| Sensíveis | Raça/etnia, religião, opinião política, sindicato, saúde, vida sexual, genética e biometria são sensíveis quando vinculados a pessoa; revelar sensível por combinação também importa. [1] | Classificar campos e conteúdo de upload como `unknown/personal/sensitive`; impedir filtro, segmentação, inferência ou anúncio por atributo sensível. `beneficiary_groups` só pode permanecer agregado e contextual; se vinculado a pessoa, aplicar art. 11 e controle de acesso reforçado. | Testes de schema, busca, exportação e projeção pública; teste de tentativa de usar grupo sensível como filtro; revisão de amostra de anexos. |
| Crianças e adolescentes | O art. 14 exige melhor interesse; o Enunciado ANPD nº 01/2023 orienta que bases dos arts. 7 e 11 podem ser usadas, sempre no melhor interesse, e preserva exigências específicas de consentimento quando aplicáveis. [1] [12] | Perguntar se o tratamento alcança criança/adolescente; marcar categoria sem exigir cadastro invasivo; bloquear publicidade/segmentação; avisos acessíveis; avaliação de melhor interesse; fluxo para responsável quando necessário. Não aceitar “a OSC é controladora” como motivo para ignorar dados inseridos em anexos. | Testes com usuário menor/representante; revisão de linguagem; registro de melhor interesse; bloqueio de perfilização para marketing. |
| ECA Digital | A Lei nº 15.211/2025, com vigência iniciada em 17/03/2026 por alteração da Lei nº 15.352/2026, exige proteção por padrão, gestão de riscos e proteção de dados para produtos direcionados ou de acesso provável por crianças/adolescentes; veda perfil comportamental para publicidade. [14] [15] | Fazer classificação de público e acesso provável. Se o produto entrar nesse escopo, aplicar default mais protetivo, gestão de riscos desde a concepção, verificação de idade proporcional, supervisão e registro de decisões. Isso é gate de escopo, não afirmação automática de incidência. | Documento de escopo; DPIA/RIPD; testes de default; revisão de publicidade e recomendação. |
| Direitos | A ANPD lista informação, confirmação, acesso, correção, anonimização/bloqueio/eliminação, portabilidade, oposição/informações, revogação e revisão/explicação de decisão automatizada. [7] | Um único portal `privacy_requests` com autenticação proporcional, tipo de direito, escopo, prazo, responsável, exceção do art. 16, resposta, exportação, anonimização e trilha. Responder também quando a informação está em documento/anexo ou fornecedor. | Testes E2E para cada direito; relógio de prazo; prova de entrega; teste de acesso sem revelar dados de outro titular. |
| Pequeno porte | Resolução nº 2 inclui micro/EPP, startups, entidades privadas sem fins lucrativos e outros agentes definidos; exclui alto risco, receita/grupo acima dos limites e mantém LGPD, bases e direitos. Permite ROPA simplificado, política simplificada e canal quando não houver encarregado; prazos em dobro se aplicáveis. [2] | Criar questionário de enquadramento por entidade e por operação: receita/grupo, escala, sensíveis, crianças, inovação, decisão automatizada e impacto significativo. Não ligar um botão “pequeno porte” global. | Evidência societária/econômica; decisão de alto risco; reavaliação anual e por mudança; teste de que flexibilização não remove direitos. |
| Encarregado | Resolução nº 18 exige ato formal, identidade e contato atualizados e públicos, substituto, recursos e autonomia; define atribuições e assistência em ROPA, incidentes, RIPD, riscos e segurança. Operador pode indicar facultativamente; pequeno porte dispensado deve manter canal. [2] [4] | Implementar `controller_contact`/`dpo_record`: ato, titular, pessoa jurídica/responsável natural, substituto, contato público, vigência, conflito, escalonamento e acesso hierárquico. A página deve apontar diretamente o canal de direitos. | Teste HTTP da página pública; ato assinado; teste de substituto; simulação de comunicação da ANPD e de titular. |
| Incidentes | Resolução nº 15: controlador comunica à ANPD e ao titular incidente com risco/dano relevante; critérios incluem impacto significativo e, cumulativamente, sensíveis, crianças/adolescentes/idosos, financeiros, autenticação, sigilo ou larga escala. Prazo geral é 3 dias úteis, contado do conhecimento de que dados pessoais foram afetados; pequeno porte tem prazo em dobro. Registro mínimo é mantido por 5 anos. [3] | Pipeline `detect → qualify → contain → controller → ANPD/titular`: timestamps de detecção/conhecimento, categorias, volume, crianças, risco, medidas, contato, operador, representante, comunicação preliminar/complementar e guarda de cinco anos. Contrato exige operador comunicar imediatamente ao controlador. | Exercício trimestral com relógio de 3/6 dias úteis; formulário completo; declaração ao titular; retenção de 5 anos; teste de segredo comercial no processo. |
| RIPD | RIPD é documentação do controlador para tratamento de alto risco; recomenda-se antes do início. Deve descrever tipos de dados, metodologia, segurança e mitigação; pode ser exigido pela ANPD, inclusive para sensíveis, legítimo interesse e poder público. [8] | Gating de projeto: ROPA → triagem de alto risco → RIPD aprovado antes de produção. Versão interna e resumo público separado; registrar riscos residuais, titulares, mitigação, consulta ao encarregado e revisão por mudança. | Teste que bloqueia ativação de tratamento alto risco sem RIPD aprovado; evidência de revisão; ligação a controles e incidentes. |
| Anonimização | Anonimização é processo baseado em meios razoáveis disponíveis; dados anonimizados não são pessoais salvo reversão com meios próprios/esforços razoáveis. Estudo técnico ANPD destaca identificadores indiretos, risco contextual e avaliação contínua de reidentificabilidade. [1] [13] | Não rotular `gov_territory_stats`, contagens ou hashes como anônimos por padrão. Aplicar supressão/agrupamento, avaliar unicidade, combinação com dados públicos, pequenos territórios, ataques de vinculação e capacidade do destinatário. Manter chave de pseudônimo separada e tratá-la como dado pessoal. | Testes de reidentificação e unicidade; relatório técnico por publicação; k-anonimato apenas como hipótese, não como garantia; revisão quando dimensão/território muda. |
| Transferência internacional | Resolução nº 19 exige finalidade/base legal e mecanismo válido: adequação reconhecida, cláusulas-padrão, cláusula específica, normas corporativas ou hipóteses legais. Cláusulas-padrão deveriam ter sido incorporadas em até 12 meses da publicação; regulamento consta como vigente com retificação de 2025. [5] [6] | Inventário de localidade de hosting, backups, suporte, analytics, e-mail, IA e suboperadores; país, exportador/importador, dados, base, mecanismo, versão da cláusula, transferência posterior, solicitação de acesso governamental e eliminação. Bloquear fornecedor sem mecanismo aprovado. | Registro de transferência; contrato/cláusulas; teste sem destino não catalogado; revisão anual e por mudança de país/suboperador. |
| Decisões automatizadas | Titular pode solicitar revisão e explicação de decisão tomada unicamente com base em tratamento automatizado que afete seus interesses; a ANPD destaca perfil pessoal, profissional, consumo e crédito. [1] [7] | Catalogar regras, scores, ranking, elegibilidade, recomendações, `Impacto Ready`, risco de preço e qualquer decisão que limite acesso/visibilidade. Guardar versão, entradas, saída, explicação compreensível, revisão humana, contestação e correção; nunca chamar uma regra de “humana” só porque foi configurada por pessoa. | Testes de reprodução, viés/disparate impact, override humano, explicação e contestação; gate para decisão de alto risco e sensíveis/crianças. |
| Segurança | Art. 46 exige medidas técnicas e administrativas; Guia ANPD para pequeno porte recomenda PSI, treinamento, contratos, autenticação/autorização/auditoria, menor privilégio, atualização, backup, proteção de fornecedores e resposta a incidentes. O Guia é orientação; a Resolução nº 2 considera sua adoção evidência de boas práticas. [1] [2] [11] | Manter TOTP cifrado, tokens em hash, RLS, arquivos privados, logs sem corpo e backup verificado; acrescentar revisão de acesso, MFA administrativo, rotação de chaves, gestão de vulnerabilidades, restauração testada, segregação de ambientes, NDA, cláusulas controlador-operador, monitoramento e treinamento. | CI de autorização/RLS; SAST/dependências/segredos; teste de restauração; revisão trimestral de acessos; exercícios de phishing/incidente; evidência de treinamento. |
| Retenção e eliminação | LGPD limita tratamento à finalidade e prevê eliminação ao término, ressalvadas hipóteses do art. 16; registros de incidente têm mínimo normativo de 5 anos. Contratos e obrigação legal podem justificar conservação, mas não retenção indefinida. [1] [3] | `retention_policy` por finalidade e categoria, prazo de ativo, evento de início, exceção legal, legal hold, ação de eliminação/anonimização, operador e prova. Separar conteúdo, índice, logs, IP, tokens, backups e trilha de auditoria; impedir que “backup” vire exceção ilimitada. | Job idempotente e observável; teste de expiração; reconciliação de órfãos; legal hold; prova de eliminação/anonimização; retenção de incidente por 5 anos. |
| Accountability e sanções | Resolução nº 4 classifica infrações e considera gravidade, boa-fé, dano, cooperação, políticas, correção e proporcionalidade; não regularizar medida pode agravar a atuação. [16] | Registro de riscos, decisões, testes, treinamento, incidentes, correções, exceções e justificativas. Alertas para claim sem evidência; não apagar a prova de governança junto com o dado pessoal quando houver fundamento para preservá-la, anonimizando o necessário. | Dossiê de prestação de contas por release; auditoria independente; log imutável com minimização; plano de correção e verificação. |

## Requisitos de produto

### 1. Registro de tratamentos e mapa de finalidades

Criar um módulo versionado de ROPA, com uma linha por finalidade e não uma linha genérica “a plataforma usa dados”. Campos mínimos: operação, controlador, operador e suboperadores; titulares; fonte; categorias e volume; dado sensível/criança; finalidade e compatibilidade; base do art. 7 ou 11; compartilhamentos; países; prazo; descarte; direitos; risco; RIPD; encarregado; versão e aprovadores.

O cadastro deve bloquear publicação de uma nova finalidade sem base, aviso, responsável e regra de retenção. A edição deve abrir nova versão; o histórico deve mostrar quem alterou, quando, qual dependência foi reavaliada e quais tratamentos derivados foram afetados.

### 2. Central de direitos do titular

Unificar exportação, correção, oposição, revogação, anonimização, bloqueio, eliminação, portabilidade e revisão automatizada. A tela deve explicar que o exercício é gratuito, permitir canal alternativo e emitir protocolo. A identificação deve ser proporcional: não pedir documento excessivo para um pedido de correção simples, mas impedir que uma pessoa veja o cadastro de outra.

A resposta deve distinguir: atendido; parcialmente atendido; inexistente; recusado com fundamento; encaminhado ao controlador; dependente de validação. Para eliminação, mostrar dados eliminados, dados anonimizados e dados conservados por obrigação ou exercício de direitos. Não destruir a trilha inteira automaticamente.

### 3. Encarregado e transparência pública

Antes da publicação, aprovar ato formal, nomear substituto, publicar nome e contato em local destacado e manter rota de saúde do canal. Se o controlador realmente se enquadrar na dispensa de pequeno porte, manter canal equivalente e registrar a decisão. O frontend não deve usar “DPO” como rótulo se o campo estiver vazio ou se houver apenas um placeholder.

A política de privacidade deve ser uma versão legal aprovada, imutável por versão, com finalidade, dados, bases, compartilhamentos, países, direitos, retenções, cookies e contato. O `LEGAL_FRAMEWORK` deve continuar bloqueando aceite de `draft`.

### 4. Tratamento de anexos e texto livre

Uploads, mensagens, descrições de projeto e documentos devem ser classificados como potenciais dados pessoais até triagem. O produto pode preferir contagens agregadas, mas não pode converter isso em promessa de que anexos não contêm saúde, religião, raça, biometria, dados de criança ou documentos de identificação. Criar aviso para a OSC: não enviar dados desnecessários; se enviar, a organização deve informar sua base e controlar a divulgação.

A projeção pública deve continuar fechada por allowlist. Acrescentar varredura de conteúdo e teste de exfiltração nos downloads, URLs temporárias, busca, exportação, notificações, relatórios e mensagens de erro.

### 5. Incidente e continuidade

Criar um relógio de incidente que começa quando o controlador toma conhecimento de que o evento afetou dados pessoais, não apenas quando a investigação terminou. O fluxo deve separar: evento técnico; incidente de segurança; incidente com dados pessoais; risco/dano relevante; decisão de comunicação; comunicação; complemento; registro.

Para controlador e pequeno porte, exibir o prazo aplicável sem esconder a regra geral de três dias úteis e o prazo em dobro. Registrar a justificativa se houver atraso. A comunicação ao titular deve ser simples, individualizada quando possível e ampla por ao menos três meses quando não for possível localizar todos.

### 6. RIPD e alto risco

A triagem deve considerar larga escala, impacto significativo, tecnologia emergente, vigilância de área pública, decisão exclusivamente automatizada e sensíveis/crianças/adolescentes/idosos. Um tratamento pode ser alto risco mesmo quando a empresa é pequena. O botão “pequeno porte” nunca deve reduzir a triagem.

O RIPD deve incluir desenho do fluxo, necessidades, alternativas menos intrusivas, base, riscos para direitos, probabilidade/impacto, controles, risco residual, consulta, decisão de aprovação e plano de revisão. Não publicar segredo comercial; produzir resumo público quando útil.

### 7. Transferências e fornecedores

Adicionar um registro de suboperadores e localidade efetiva. “Servidor no Brasil” não basta se suporte, backup, telemetria, e-mail ou IA acessarem dados no exterior. Nenhuma integração futura deve ser ligada sem a combinação `fornecedor aprovado + DPA/contrato + mecanismo da Resolução 19 + base + retenção + incidente + subcontratação`.

### 8. Decisões, IA e explicação

Catalogar toda saída que possa afetar acesso, reputação, financiamento, visibilidade, preço, risco, elegibilidade ou atendimento. A arquitetura atual declara que a busca da Central é extrativa e que o provedor de IA padrão é local; ainda assim, regras de risco, readiness, preço e recomendações podem ser decisões automatizadas. O catálogo deve registrar se há intervenção humana real e documentada.

A contestação deve reabrir o caso, preservar a decisão original e permitir decisão humana independente. Remover atributos sensíveis e proxies; testar diferenças por território, grupo beneficiário, idioma, deficiência, idade e outros fatores pertinentes sem inferir categorias proibidas.

## Requisitos de dados e modelo mínimo

1. **`ropa_treatments`:** `purpose`, `purpose_version`, `legal_basis`, `sensitive`, `children`, `subjects`, `categories`, `source`, `controller_id`, `operator_id`, `suboperator_id`, `countries`, `transfer_mechanism`, `retention_rule`, `deletion_action`, `risk_level`, `ripd_id`, `notice_version`, `owner`, `approved_at`.
2. **`privacy_requests`:** titular, organização, direito, escopo, método de verificação, prazo legal, prazo diferenciado, status, resposta, exceção, dados afetados, entrega, revisão e auditoria. Guardar o mínimo necessário para provar atendimento.
3. **`consents`:** finalidade determinada, texto/versionamento/hash, ato de vontade, data, canal, prova, revogação e efeitos. Não misturar consentimento de marketing, termos e política em uma autorização genérica.
4. **`documents` e texto livre:** classificação inicial “potencialmente pessoal”, proprietário/controlador, finalidade, visibilidade, prazo, localização, criptografia, download e suboperador. `beneficiaries_count` só é agregado se não puder ser ligado a pessoa; `beneficiary_groups` deve ser contextualizado e nunca servir de filtro ou inferência individual.
5. **`incidents`:** data de ocorrência, detecção, conhecimento pelo controlador, dados e titulares afetados, crianças/adolescentes/idosos, risco, causa, medidas, operador, contato, comunicações, motivo de atraso e prazo de guarda de cinco anos.
6. **`dpo_record`:** ato, titular, substituto, pessoa jurídica/responsável natural, contato público, escopo, recursos, conflitos, escalonamento e vigência.
7. **`ripd`:** tratamento, versão, metodologia, alternativas, riscos, probabilidade, impacto, mitigação, risco residual, consulta, aprovação, resumo público e revisão por mudança.
8. **`transfer_registry`:** exportador, importador, suboperador, país, categorias, finalidade, base, mecanismo, cláusula/versionamento, transferência posterior, solicitação de acesso, eliminação e auditoria.
9. **`decision_registry`:** decisão, regra/modelo, versão, dados de entrada, atributos excluídos, finalidade, impacto, explicação, humano responsável, override, contestação, teste de viés e data de revisão.
10. **`retention_ledger`:** objeto, categoria, propósito, evento inicial, prazo, destruição/anonimização, legal hold, backup, operador, execução, erro e prova. IP, agente de usuário, tokens, logs de segurança, conteúdo de negócio e dados de incidente não devem compartilhar um prazo fictício.
11. **`visibility_policy`:** entidade, campo, audiência, finalidade, base, papel, RLS, projeção, evento de divulgação e teto. A matriz de visibilidade deve ser derivada do ROPA e não existir como documento isolado.

## Testes e controles de aceite

### Gates de cada release

- **LGPD-G01 — inventário:** falha se uma rota, job, tabela, evento ou integração tratar dado pessoal sem tratamento correspondente no ROPA.
- **LGPD-G02 — base/finalidade:** falha se `legal_basis`, finalidade, aviso ou retenção estiver ausente; consentimento genérico é rejeitado.
- **LGPD-G03 — autorização:** matriz de 100% das rotas sensíveis com RLS, papel, allowlist, resposta de erro e teste de cross-tenant.
- **LGPD-G04 — sensíveis:** banco, API, busca, exportação e UI rejeitam filtro/segmentação por categoria sensível ou proxy; anexos não são classificados como “não sensíveis” por default.
- **LGPD-G05 — crianças:** cenário de titular criança/adolescente verifica melhor interesse, aviso e bloqueio de perfilização/publicidade; nenhuma rota exige coleta excessiva para “verificar idade”.
- **LGPD-G06 — direitos:** cada direito tem teste E2E, protocolo, prazo, resposta e prova de não vazamento; eliminação preserva somente exceções documentadas.
- **LGPD-G07 — encarregado:** página pública, ato, substituto, contato em português e simulação de comunicação funcionam; canal de pequeno porte não fica vazio.
- **LGPD-G08 — pequeno porte:** evidência de receita/grupo/escala e triagem de alto risco; nenhuma flexibilização é aplicada por flag sem aprovação e data de expiração.
- **LGPD-G09 — incidente:** exercício dispara contenção, qualificação, comunicação ANPD/titular, complemento, registro e guarda de cinco anos; prazo em dobro só para agente comprovadamente elegível.
- **LGPD-G10 — RIPD:** tratamento classificado de alto risco não entra em produção sem RIPD aprovado e medidas vinculadas.
- **LGPD-G11 — anonimização:** publicação agregada passa por teste de unicidade, vinculação, small-cell suppression e ataque com dados públicos; resultado e risco residual são arquivados.
- **LGPD-G12 — internacional:** CI bloqueia endpoint/fornecedor com país não registrado, cláusula ausente, suboperador desconhecido ou mecanismo expirado.
- **LGPD-G13 — decisões:** mesma entrada reproduz a versão registrada; explicação é acessível; contestação chega a revisor humano; teste não usa sensíveis nem proxies proibidos.
- **LGPD-G14 — retenção:** jobs são idempotentes, observáveis e testam exclusão de índices, arquivos, logs e cópias; legal hold impede destruição legítima e tem expiração.
- **LGPD-G15 — segurança:** MFA admin, menor privilégio, revisão de acessos, rotação de segredo, restauração de backup, dependências, gitleaks, RLS e ausência de corpo de requisição passam no CI.
- **LGPD-G16 — claims:** pipeline de documentação e frontend falha em “100% conforme”, “certificado”, “anonimizado”, “sem sensíveis”, “sem transferência” ou “decisão humana” sem evidência e aprovação.

### Controles operacionais

- Revisão mensal de tratamentos novos e trimestral de acesso privilegiado.
- Revisão de suboperadores e localidades antes de cada integração e pelo menos anual.
- Simulação de incidente a cada trimestre; teste de restauração e eliminação a cada release maior.
- Revisão de notices e guias regulatórios quando a fonte oficial mudar; conteúdo expirado recebe “Revisão necessária” no Knowledge Hub.
- Dossiê por release com ROPA, RIPD quando aplicável, testes, exceções, incidentes, decisões, claims publicados e aprovação humana.
- Canal de vulnerabilidade e incidentes com roteamento para segurança, controlador, encarregado e jurídico responsável; não usar a central de denúncia da ANPD como canal de incidente próprio.

## Claims proibidos ou condicionados

Estas frases devem ser proibidas no site, pitch, documentação comercial, seed, selo e resposta automática, salvo se o texto for qualificado e houver evidência aprovada:

1. **“Somos 100% conformes à LGPD”, “produto certificado pela ANPD” ou “risco zero”.** A ANPD fiscaliza e sanciona; teste interno não é certificação.
2. **“Não coletamos dados sensíveis.”** O produto pode não solicitar campos sensíveis, mas uploads, mensagens e documentos de terceiros podem contê-los.
3. **“Não tratamos dados de crianças/adolescentes.”** Só usar após escopo, controles de anexos e evidência de que nenhum fluxo provável alcança esses titulares.
4. **“Todos os dados estão anonimizados.”** Agregação, hash, pseudonimização ou k-anonimato isolado não demonstram irreversibilidade contextual.
5. **“Não há transferência internacional.”** Hosting, backup, suporte, telemetria, e-mail e IA devem ser inventariados antes de afirmar isso.
6. **“Temos encarregado/DPO” ou “o titular fala diretamente com a ANPD pela plataforma.”** Só publicar depois de ato, substituto, contato e fluxo reais.
7. **“Eliminamos todos os dados quando o usuário apaga a conta.”** Art. 16 e obrigações probatórias podem justificar conservação; declarar exatamente o que é eliminado, anonimizado ou retido.
8. **“Toda decisão é humana” ou “IA não afeta decisões.”** Regras, ranking, scores e readiness podem afetar interesses mesmo sem modelo generativo.
9. **“RIPD concluído”, “incidente resolvido” ou “incidente comunicado no prazo.”** Claims só após documento aprovado, comunicação e evidência temporal.
10. **“Grupo beneficiário é dado público/estatístico e nunca sensível.”** O caráter pessoal depende da possibilidade de associação ou inferência; não filtrar, segmentar ou inferir pessoa.
11. **“O selo Impacto Ready prova o impacto, a segurança ou a conformidade.”** O selo é uma hipótese de produto e deve indicar critérios, contagens, lacunas e data; não substitui auditoria ou obrigação jurídica.
12. **“Preço fora do padrão é fraude” ou “denúncia é infração.”** A disciplina interna já usa “possivelmente fora do padrão” e separa denúncia, suspeita, infração apurada e consequência; manter essa distinção.

## Lacunas priorizadas

### P0 — bloqueiam publicação ou claim de proteção

- Política de privacidade, termos e demais textos ainda são `draft`; não coletar aceite até revisão e aprovação.
- Ausência de ROPA legal por finalidade, base, papéis, localização e retenção.
- Encarregado/canal público e substituto não formalizados.
- Fluxo de incidente com prazo, comunicação a titulares, formulário ANPD e registro de cinco anos não demonstrado.
- Nenhum RIPD conectado a triagem de alto risco.
- Transferências e suboperadores não inventariados; qualquer futura IA, e-mail, analytics, backup ou suporte pode alterar o resultado.

### P1 — alto risco de exposição ou de afirmação enganosa

- Conteúdo livre e anexos ainda não possuem classificação e política de minimização.
- Matriz de visibilidade é v0.16.0 e não contém base, finalidade, retenção, país ou evidência de direitos.
- `beneficiary_groups`, estatísticas territoriais e k-anonimato não têm avaliação contemporânea de reidentificação.
- Retenções técnicas existem, mas falta justificativa por tratamento, legal hold, backup e reconciliação com arts. 16 e 18.
- Catalogação de decisões automatizadas, explicação, revisão humana e testes de viés não está evidenciada.
- Enquadramento de pequeno porte e exclusão por alto risco não está implementado como decisão documentada.
- Segurança técnica é forte em vários pontos, mas falta o dossiê operacional: revisão de acesso, chaves, fornecedores, restauração, vulnerabilidades e exercício de incidente.

### P2 — governança e comunicação

- Knowledge Hub ainda tem conteúdo demo; conteúdo regulatório precisa de responsável, fonte, data de corte e expiração.
- Integrar a revisão de Resoluções e leis recentes, incluindo Lei nº 15.352/2026 e ECA Digital, ao processo de release.
- Definir se qualquer futura adoção de ISO/IEC 27001, ISO/IEC 27701, NIST ou outra referência será apenas padrão voluntário de governança; nunca apresentá-la como requisito legal ou certificação ANPD.
- Atribuir proprietário, data de revisão e evidência a cada claim público.

## Perguntas abertas para decisão documentada

1. Qual entidade é controladora em cada fluxo e quais clientes/OSCs são controladores independentes ou conjuntos?
2. O Impacto será oferecido a crianças/adolescentes ou é de acesso provável por eles? Qual escopo do ECA Digital será adotado?
3. A plataforma se enquadra como startup/agente de pequeno porte por entidade, grupo econômico e operação? Há tratamento de alto risco que exclua a flexibilização?
4. Qual é a base de cada finalidade comercial, de recomendação, publicação pública, torre de controle, notificações e IA?
5. Quais fornecedores, países, suboperadores, backups e canais de suporte serão usados em produção?
6. Que tratamentos exigem RIPD antes do lançamento e quem aprova risco residual?
7. Quais retenções são obrigação legal, exercício de direitos, segurança, auditoria ou apenas conveniência técnica?
8. Quais scores, selos, torres e readiness afetam materialmente pessoas ou organizações e que revisão humana será independente?
9. Quem assina a política de privacidade, o ato de encarregado, contratos de operador e cláusulas de transferência?
10. Qual evidência de restauração, eliminação, resposta a direitos e incidente será exigida no gate de publicação?

## Referências numeradas

[1]: https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709compilado.htm "Lei nº 13.709, de 14 de agosto de 2018 — Lei Geral de Proteção de Dados Pessoais (texto compilado vigente)" — Órgão: Presidência da República/Planalto; data: 14/08/2018, texto consultado em 08/10/2026; sustenta definições, princípios, bases legais, dados sensíveis, crianças, direitos, decisões automatizadas, segurança, governança, RIPD, eliminação e ANPD.

[2]: https://www.gov.br/anpd/pt-br/documentos-e-publicacoes/regulamentacoes-da-anpd/resolucao-cd-anpd-no-2-de-27-de-janeiro-de-2022 "Resolução CD/ANPD nº 2, de 27 de janeiro de 2022 — Regulamento para agentes de tratamento de pequeno porte" — Órgão: Autoridade Nacional de Proteção de Dados; data: 27/01/2022, com alteração indicada pela Resolução nº 15/2024; sustenta definição e exclusões de pequeno porte, alto risco, ROPA simplificado, canal/encarregado, política de segurança e prazos diferenciados.

[3]: https://www.in.gov.br/en/web/dou/-/resolucao-cd/anpd-n-15-de-24-de-abril-de-2024-556243024 "Resolução CD/ANPD nº 15, de 24 de abril de 2024 — Regulamento de Comunicação de Incidente de Segurança" — Órgão: ANPD/Diário Oficial da União; data: 24/04/2024; sustenta critérios de risco relevante, prazo de três dias úteis, prazo em dobro para pequeno porte, conteúdo das comunicações, comunicação aos titulares e registro por cinco anos.

[4]: https://www.in.gov.br/en/web/dou/-/resolucao-cd/anpd-n-18-de-16-de-julho-de-2024-572632074 "Resolução CD/ANPD nº 18, de 16 de julho de 2024 — Regulamento sobre a atuação do encarregado" — Órgão: ANPD/Diário Oficial da União; data: 16/07/2024; sustenta ato formal, substituto, identidade e contato públicos, recursos, autonomia, atribuições e assistência em ROPA, incidentes, RIPD e segurança.

[5]: https://www.gov.br/anpd/pt-br/acesso-a-informacao/institucional/atos-normativos/regulamentacoes_anpd/resolucao-cd-anpd-no-19-de-23-de-agosto-de-2024 "Resolução CD/ANPD nº 19, de 23 de agosto de 2024 — Regulamento de Transferência Internacional de Dados e cláusulas-padrão" — Órgão: ANPD; data: 23/08/2024; sustenta mecanismos de transferência, adequação, cláusulas-padrão/específicas, normas corporativas, finalidade, base legal, transferência posterior, acesso governamental e eliminação.

[6]: https://www.gov.br/anpd/pt-br/acesso-a-informacao/institucional/atos-normativos/regulamentacoes_anpd "Regulamentações da ANPD — lista de atos e status" — Órgão: ANPD; data: página consultada em 08/10/2026, com registros de alterações/retificação de 2025; sustenta a vigência das Resoluções nº 2, 4, 15, 18 e 19 e diferencia atos vigentes de materiais de apoio.

[7]: https://www.gov.br/anpd/pt-br/assuntos/titular-de-dados/direito-dos-titulares "Direito dos Titulares" — Órgão: ANPD; data: página consultada em 08/10/2026; sustenta a apresentação administrativa de informação, confirmação, acesso, correção, anonimização/bloqueio/eliminação, portabilidade, revogação, informações e revisão/explicação de decisões automatizadas.

[8]: https://www.gov.br/anpd/pt-br/canais_atendimento/agente-de-tratamento/relatorio-de-impacto-a-protecao-de-dados-pessoais-ripd "Relatório de Impacto à Proteção de Dados Pessoais (RIPD) — perguntas e respostas" — Órgão: ANPD; data: página consultada em 08/10/2026; sustenta responsabilidade do controlador, elaboração preferencialmente prévia, alto risco, conteúdo mínimo, solicitação pela ANPD e publicidade não obrigatória em regra.

[9]: https://www.gov.br/anpd/pt-br/centrais-de-conteudo/materiais-educativos-e-publicacoes/guia_orientativo_hipoteses_legais_tratamento_de_dados_pessoais_legitimo_interesse "Guia Orientativo — Hipóteses legais de tratamento de dados pessoais: legítimo interesse" — Órgão: ANPD; data: publicado em 22/11/2024, modificado em 23/01/2025; sustenta a necessidade de teste de finalidade, necessidade, balanceamento, transparência, salvaguardas e atenção a sensíveis/crianças; é orientação administrativa, não lei.

[10]: https://www.gov.br/anpd/pt-br/centrais-de-conteudo/materiais-educativos-e-publicacoes/guia-orientativo-para-definicoes-dos-agentes-de-tratamento-de-dados-pessoais-e-do-encarregado "Guia orientativo para definições dos agentes de tratamento de dados pessoais e do encarregado" — Órgão: ANPD; data: página publicada em 22/11/2024 e modificada em 23/01/2025; guia original de abril de 2022; sustenta a distinção funcional controlador/operador, controlador conjunto, suboperador e a importância das decisões reais; orientação administrativa não vinculante isoladamente.

[11]: https://www.gov.br/anpd/pt-br/centrais-de-conteudo/materiais-educativos-e-publicacoes/guia-orientativo-sobre-seguranca-da-informacao-para-agentes-de-tratamento-de-pequeno-porte "Guia orientativo sobre segurança da informação para agentes de tratamento de pequeno porte" — Órgão: ANPD; data: publicado em 21/06/2024, modificado em 23/01/2025; guia técnico original de outubro de 2021; sustenta PSI, treinamento, contratos, controle de acesso, menor privilégio, backup, fornecedores e resposta; é boa prática/orientação.

[12]: https://www.gov.br/anpd/pt-br/assuntos/noticias/anpd-divulga-enunciado-sobre-o-tratamento-de-dados-pessoais-de-criancas-e-adolescentes/Enunciado1ANPD.pdf "Enunciado ANPD nº 01/2023 sobre tratamento de dados pessoais de crianças e adolescentes" — Órgão: ANPD; data: criado em 24/05/2023; sustenta melhor interesse em qualquer base aplicável e a leitura administrativa das bases dos arts. 7 e 11; enunciado não substitui o texto legal nem análise contextual.

[13]: http://www.gov.br/anpd/pt-br/centrais-de-conteudo/documentos-tecnicos-orientativos/estudo_tecnico_sobre_anonimizacao_de_dados_na_lgpd___analise_juridica.pdf/@@display-file/file "Estudo técnico sobre anonimização de dados na LGPD — análise jurídica" — Órgão/autor: ANPD; data: 06/04/2023; sustenta anonimização como processo, identificadores diretos/indiretos, risco de reidentificação e modelo baseado em riscos; estudo técnico, não garantia automática.

[14]: https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2025/lei/l15211.htm "Lei nº 15.211, de 17 de setembro de 2025 — Estatuto Digital da Criança e do Adolescente" — Órgão: Presidência da República/Planalto; data: 17/09/2025; sustenta proteção por padrão, gestão de riscos, privacidade, segurança e vedação de perfil comportamental para publicidade quando o produto é direcionado ou de acesso provável por crianças/adolescentes.

[15]: https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2026/lei/l15352.htm "Lei nº 15.352, de 25 de fevereiro de 2026" — Órgão: Presidência da República/Planalto; data: 25/02/2026; sustenta alterações institucionais da ANPD e a vigência do Estatuto Digital da Criança e do Adolescente a partir de 17/03/2026.

[16]: https://www.in.gov.br/en/web/dou/-/resolucao-cd/anpd-n-4-de-24-de-fevereiro-de-2023-466146077 "Resolução CD/ANPD nº 4, de 24 de fevereiro de 2023 — Regulamento de Dosimetria e Aplicação de Sanções Administrativas" — Órgão: ANPD/Diário Oficial da União; data: 24/02/2023; sustenta classificação de infrações, critérios de dosimetria, agravantes/atenuantes, medidas corretivas e relevância da cooperação e das boas práticas.

### Fontes internas auditadas

- `/home/ubuntu/impacto-trust-knowledge-v0.26.0/README.md` — estado do v0.26.0, ausência de publicação e de provedores reais, arquitetura não custodial, governança e limites do release.
- `/home/ubuntu/impacto-trust-knowledge-v0.26.0/docs/LGPD.md` — controles técnicos existentes, retenções técnicas e pendências expressas de base, RIPD, encarregado, crianças, contratos e retenção jurídica.
- `/home/ubuntu/impacto-trust-knowledge-v0.26.0/PRIVACY_VISIBILITY_MATRIX.md` — matriz v0.16.0 de visibilidade, allowlist pública, RLS/papel, grupo beneficiário e não exposição do denunciante.
- `/home/ubuntu/impacto-trust-knowledge-v0.26.0/docs/LEGAL_FRAMEWORK.md` — onze minutas `draft`, bloqueio de aceite, hash de texto, anonimização limitada de prova e placeholder do encarregado.
- `/home/ubuntu/impacto-trust-knowledge-v0.26.0/KNOWLEDGE_HUB.md` — conteúdo demo, assistente extrativo e exigência de fonte/data para material regulatório.
- `/home/ubuntu/impacto-trust-knowledge-v0.26.0/docs/PROCUREMENT.md` — benchmark de cotações e linguagem que não converte outlier em fraude.
