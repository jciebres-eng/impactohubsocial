# Registro de pesquisa — fontes oficiais e decisões derivadas (Etapa 2)

**Acesso em:** 10/10/2026. **Regra:** cada requisito legal tem fonte oficial ou fica "a validar". Distinguimos: **requisito legal**,
**orientação oficial**, **regra institucional configurável** (a IES decide), **recomendação de produto** e **hipótese comercial**.
Nada aqui é parecer jurídico; a interpretação normativa é da IES e de profissionais habilitados.

**Limite do ambiente:** os portais `portal.mec.gov.br` e `gov.br/mec` recusaram leitura automatizada (robots e verificação
"você é humano?"). Onde isso aconteceu, o texto foi lido numa **cópia publicada por universidade** e está marcado como tal — conferir
no Diário Oficial antes de citar em contrato ou regulamento.

## F-01 — Resolução CNE/CES nº 7, de 18/12/2018 (Diretrizes para a Extensão na Educação Superior Brasileira)

- **Órgão:** MEC / CNE / Câmara de Educação Superior. **Publicação:** DOU de 19/12/2018, Edição 243, Seção 1, p. 49.
- **URL oficial:** https://www.in.gov.br/materia/-/asset_publisher/Kujrw0TZC2Mb/content/id/55877808 (leitura automatizada recusada);
  https://www.gov.br/mec/pt-br/cne/pdf/normas-classificadas-por-assunto/extensao-na-educacao-superior-brasileira/rces007_18.pdf
  (verificação anti-robô). **Texto lido em:** cópia da UFPB —
  https://prg.ufpb.br/proex/contents/documentos/curricularizacao-da-extensao-documentos/resolucao-cse-no-7-de-18-de-dezembro-de-2018.pdf
- **Tipo:** requisito legal (norma do CNE) para a IES; **não** para a plataforma.

| Artigo | Trecho (curto, literal) | Decisão de produto |
|---|---|---|
| 3º | extensão "é a atividade que se integra à matriz curricular e à organização da pesquisa" | ação de extensão liga-se a componente curricular/oferta, não a uma lista solta de horas |
| 4º | "devem compor, no mínimo, 10% (dez por cento) do total da carga horária curricular estudantil" | parâmetro por **curso**: carga horária total e percentual mínimo (padrão 10%), editável pela IES, com a fonte registrada; o painel mostra previsto × aprovado, nunca "cumprido perante o MEC" |
| 7º | "São consideradas atividades de extensão as intervenções que envolvam diretamente as comunidades externas" | ação de extensão exige comunidade/parceiro externo declarado |
| 8º | "I - programas; II - projetos; III - cursos e oficinas; IV - eventos; V - prestação de serviços" | modalidade obrigatória com estes 5 valores |
| 9º | na modalidade a distância, as atividades "devem ser realizadas, presencialmente" (em região compatível com o polo) | campo "presencial/remoto" registrado; a regra é da IES (ver F-02) |
| 10–11 | autoavaliação contínua; a IES explicita instrumentos e indicadores | indicadores com definição, fonte e limitação; painel institucional é apoio, não avaliação oficial |
| 12 | avaliação externa (Inep/Sinaes) considera a previsão e o cumprimento do mínimo de 10% | exportação estruturada para a IES usar no próprio processo; a plataforma não envia nada ao Inep |
| 15 | proposta, desenvolvimento e conclusão "devidamente registrados" | trilha de estados e de decisões da ação, do ciclo e das horas |
| 16 | atividades "devem ser também adequadamente registradas na documentação dos estudantes" | exportação de horas aprovadas por estudante; a plataforma **não** escreve no histórico escolar |
| 17 | extensão em parceria entre IES | ação pode ter IES parceira (vínculo, sem acesso cruzado automático) |
| 19 | prazo de até 3 anos a contar da homologação | informação histórica; nenhuma regra de prazo no código |

## F-02 — Parecer CNE/CES nº 576/2023 (revisão dos arts. 9º e 12 da Res. 7/2018)

- **Lido em:** cópia da Unicamp — https://ime.unicamp.br/~extensao/doc/pces576_23 (oficial: gov.br/mec, verificação anti-robô).
- **Data:** aprovado na CES em 09/08/2023; o documento traz **"AGUARDANDO HOMOLOGAÇÃO"**. **Situação atual: NÃO VERIFICADA.**
- **Conteúdo:** propõe permitir parte remota (até 20% em programas/projetos; até 30% em cursos, oficinas e eventos), "sem serem
  confundidas com a modalidade EaD", e faixa de 10% a 12% na avaliação externa.
- **Decisão:** **nada disso vira regra fixa.** Percentual remoto máximo e faixa do curso são **parâmetros configuráveis pela IES**,
  vazios por padrão, com aviso "conferir norma vigente".

## F-03 — Inep, perguntas frequentes do Censo da Educação Superior, Módulo Curso, pergunta 39

- **URL:** https://www.gov.br/inep/pt-br/acesso-a-informacao/perguntas-frequentes/censo-da-educacao-superior/modulo-curso/39-nossa-ies-procedeu-com
  — **publicado em 19/01/2024** (lido em 10/10/2026). **Tipo:** orientação oficial.
- **Conteúdo:** cita o art. 4º da Res. 7/2018; a extensão curricularizada "deve ser computada na carga horária integralizada pelo
  aluno"; atividades da curricularização previstas no PPC **não** devem ser informadas no campo "Atividades extracurriculares" –
  "Extensão".
- **Decisão:** a exportação distingue "extensão curricularizada (prevista no PPC)" de "atividade extracurricular"; o preenchimento do
  Censo continua sendo da IES (a plataforma não declara nada ao Inep).

## F-04 — Lei 13.709/2018 (LGPD), texto compilado

- **URL:** https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709compilado.htm (lido em 10/10/2026; última alteração
  indicada no texto: Lei 15.352/2026). **Tipo:** requisito legal.

| Artigo | Ponto | Decisão de produto |
|---|---|---|
| 4º, II, b | tratamento para fins acadêmicos fica fora da lei, **mas** aplicam-se os arts. 7º e 11 | não usar "fins acadêmicos" como dispensa geral: a operação da extensão é tratamento comum |
| 5º | dado sensível; anonimização; controlador; operador | a IES é **controladora** dos dados acadêmicos; a plataforma atua como **operadora** — a validar em contrato **[IES/jurídico]** |
| 6º, I–III | finalidade, adequação, necessidade | roteiro mínimo (ID institucional, e-mail institucional, nome de exibição); sem CPF, sem data de nascimento |
| 7º | bases legais (consentimento, obrigação legal, políticas públicas, estudos por órgão de pesquisa, contrato, interesse legítimo) | a base de cada tratamento é **declarada pela IES**; o sistema não presume consentimento como base única |
| 11 | dado sensível só nas hipóteses da lei | evidência com rosto/saúde marcada como sensível; acesso restrito |
| 14 e §1º | crianças e adolescentes: melhor interesse; criança exige consentimento de um dos pais | ver F-05; a plataforma não coleta idade |
| 15–16 | término do tratamento e eliminação; exceções de conservação | classes de retenção por tabela nova; anonimização após o prazo da IES |
| 18 | direitos do titular | exportação e correção do próprio vínculo; pedidos à IES (controladora) |
| 23 | poder público: finalidade pública | IES pública: base de políticas públicas/obrigação legal a validar |
| 37 | registro das operações | trilha de auditoria das ações acadêmicas |
| 46 / 48 | segurança; comunicação de incidente | reuso dos controles e do runbook RB-02 |

## F-05 — Lei 15.211/2025 (Estatuto Digital da Criança e do Adolescente)

- **URL:** https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2025/lei/l15211.htm (lido em 10/10/2026). **Data:** 17/09/2025;
  **vigência:** 17/03/2026 (art. 41-A, redação atual). **Tipo:** requisito legal; **aplicabilidade a uma plataforma acadêmica
  institucional: a validar [jurídico]**.
- **Pontos usados:** configuração mais protetiva por padrão (art. 7º); vedação de perfilamento para publicidade (arts. 22 e 26);
  restrição de comunicação com não autorizados e de geolocalização (arts. 17–18).
- **Decisão:** padrões protetivos para **todo** estudante (D-14): perfil acadêmico não público, sem geolocalização, sem
  publicidade/perfilamento, retorno da comunidade nunca identifica estudante, contato externo só por canal da ação.

## F-06 — Ética em pesquisa: Resolução CNS 510/2016, art. 1º, parágrafo único, e Ofício-Circular nº 17/2022/CONEP/SECNS/MS

- **Lido em:** https://www.propq.ufscar.br/pt-br/assets/arquivos/etica/oficio-conep-orientacoes-acerca-do-artigo-1-o-da-resolucao-cns-n-o-510-de-7-de-abril-de-2016.pdf
  (ofício da Conep de 05/07/2022, publicado por universidade). **Tipo:** orientação oficial.
- **Conteúdo:** o inciso VIII dispensa de registro no Sistema CEP/Conep atividade "com o intuito exclusivamente de educação, ensino
  ou treinamento sem finalidade de pesquisa científica"; **TCC e monografias não se enquadram** (§1º); se houver intenção de usar os
  resultados em pesquisa, a submissão é obrigatória (§2º); a instituição pode exigir análise própria mesmo nos dispensados.
- **Decisão:** **triagem ética** com perguntas objetivas (há intenção de pesquisa ou publicação? é TCC? há coleta com identificação
  de pessoas? há público vulnerável?). Qualquer "sim" ou "não sei" → "encaminhar ao CEP/instância da IES". O sistema **nunca** decide
  que uma ação está dispensada.

## F-07 — Decisões internas que limitam o desenho

| Fonte | Conteúdo | Efeito |
|---|---|---|
| ADR-341 (`DECISIONS.md`) | não existe assinatura; núcleo gratuito; receita por contrato avulso/parcelado | licença IES sem mensalidade nem preço no sistema (D-04) |
| ADR-342 | cobrança só com contrato aceito/acordo assinado | nenhuma cobrança automática por assento |
| ADR-093 | importação nunca cria pessoa nem organização | roteiro + convite (D-06) |
| ADR-063 | convênio: código obrigatório; domínio só restringe | domínio de e-mail institucional só restringe convite, nunca autentica |
| ADR-381 | estado comercial não bloqueia prestação de contas | licença vencida não bloqueia entregas em curso nem exportação |

## Pendências que dependem de pessoas (não do código)

- **[IES/jurídico]** papel de controladora/operadora em contrato; bases legais por tratamento; aplicabilidade da Lei 15.211/2025;
  prazos de retenção acadêmica; regulamento de extensão de cada curso (PPC).
- **[RESPONSÁVEL]** modelo comercial da licença institucional; texto dos termos para IES.
- **[Conferir]** situação atual do Parecer CNE/CES 576/2023 e qualquer norma posterior no portal do CNE.
