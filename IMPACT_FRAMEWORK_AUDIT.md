# Auditoria de equidade, frameworks e confiança — FASE 1 da v0.18.0

> Lida do código, não da intenção. Cada linha de "existe" tem caminho de arquivo, tabela ou função.
> Cada linha de "não existe" foi verificada por varredura, e a varredura está citada.

## 1. O que esta rodada pede, e por que a ordem mudou de novo

Os cinco documentos desta rodada pedem uma camada que o produto não tem: **equidade, determinantes
sociais, inteligência territorial, interoperabilidade entre frameworks de impacto (ODS, ESG, GRI,
ISSB, Teoria da Mudança, SROI e outros), integridade de alegação, reputação explicável, selos
verificáveis e formulários inteligentes** — com IA operacional e responsabilidade humana registrada.

A v0.17.0 havia declarado DESIGN como a próxima fase. Esta rodada reordena outra vez, e a razão é a
mesma da anterior: **o que o design vai representar ainda está sendo decidido.** Uma tela de
"impacto" desenhada antes de existir o modelo de equidade desenharia o número errado com capricho.

A frase que governa a rodada, e que é a mais difícil de implementar honestamente:

> **Impacto não é quantidade. Impacto é resultado contextualizado.**
> 50 pessoas numa comunidade indígena remota ≠ automaticamente menos impacto que 5.000 pessoas num
> centro urbano com infraestrutura.

## 2. O que JÁ EXISTE e só precisa ser declarado (verde)

| # | O que | Onde | Por que conta |
|---|---|---|---|
| 1 | **Tipologia de evidência com 9 fontes, pesos e decaimento** | `backend/impacto/core/evidence.py` (207 linhas) | `Source` (9 valores), `SOURCE_TRUST` (assinado 1,0 … declarado 0,4 … ausente 0,0), `FRESHNESS_HALF_LIFE_DAYS` por tipo, decaimento exponencial `0,5^(idade/meia-vida)`, `FRESHNESS_VERSION`. `Evidence.__post_init__` **sobrescreve** `verified` derivando-o da fonte: o chamador não consegue marcar declaração como verificada |
| 2 | **Cadeia de resultado funcionando — sem se chamar Teoria da Mudança** | `impact_nodes` (7 tipos: need, activity, output, outcome, impact, population, context) + `impact_edges` (6 tipos de ligação) | `CHECK` recusa `observed_evidence` sem evidência, e `validated_causality` sem evidência **E** revisor de **outra** organização **E** nota. É a trava anti-greenwashing central, e ela já existe |
| 3 | **Cadeia de indicador completa** | `indicator_catalog` → `project_indicators` → `indicator_values` | `unit` obrigatório, `result_kind` (output/outcome/impact), `baseline`, `method`, e `CHECK` exigindo que quem valida medição seja de organização **diferente** |
| 4 | **Lacuna territorial** | `territorial_gap()` (SQL) + `economics/programs.py` + rota + teste | Devolve `needs_with_source` à parte: lacuna apoiada em estimativa **sem fonte** não passa por fato |
| 5 | **Necessidade territorial com fonte obrigatória** | `territory_needs` | `CHECK`: `people_estimate` sem `source_name` é recusado. "A plataforma não inventa número de população" |
| 6 | **Prontidão multidimensional e versionada** | `readiness_snapshots` + `network/readiness.py` | 6 dimensões 0–100, `overall`, `detail`/`blockers` em jsonb, `engine_version`, pesos explícitos, histórico |
| 7 | **Assinatura amarrada ao conteúdo** | `signatures` + `signature_policies` + `signature_provider_guard()` | `subject_sha256`, `statement` obrigatório, append-only, e gatilho que **recusa** assinatura por provedor que não está em produção — é o que impede "ICP-Brasil simulada" |
| 8 | **Selo calculado, nunca estático** | `engines/institutional/badges.py` + `verifiable_records` + `GET /v1/public/verify/{code}` | A validade é a do último ato humano que sustenta o selo; `_FORBIDDEN_CLAIMS` recusa texto como "certificação oficial" |
| 9 | **Quatro-olhos** | ~8 pontos, com `CHECK` no banco em cada um | Montagem de documento, medição validada, causalidade, regra fiscal (dupla aprovação), contestação de sanção |
| 10 | **Determinantes sociais (11 códigos, 4 camadas)** | `social_determinants` + `config/determinants.json` + `GET /v1/determinants` | Modelo de Dahlgren & Whitehead, `source_note` obrigatório, e a rota agrega com **k-anonimato** (`min_group`), suprimindo grupo pequeno |
| 11 | **Motor fiscal com fonte e dupla aprovação** | `engines/fiscal/engine.py` + `fiscal_rules` | Avalia só regra aprovada por dois revisores distintos e vigente; quatro rótulos de saída; fora do score do Match |
| 12 | **Governança de taxonomia de público** | `taxonomies.sensitivity` + `usage_policy` | É uma **barreira contra** segmentar pessoas: "vulnerabilidade é atributo do PROJETO, não da pessoa" |

## 3. O que existe PARCIALMENTE (amarelo)

| # | O que falta | Evidência do estado atual |
|---|---|---|
| 1 | **As 169 metas oficiais de ODS** | `ods_targets` existe e está **vazia**; não há `INSERT` nenhum no repositório. Por desenho: "metas/indicadores oficiais NÃO são embutidos: carga por importação" |
| 2 | **Indicadores oficiais (ONU/IBGE)** | `indicator_catalog.origin` aceita `'official'` e **nenhuma linha oficial foi semeada**. Os 13 indicadores existentes são `'platform'` |
| 3 | **Contribuição ao ODS quantificada** | Existe `project_ods_targets.alignment_level` (declarado / apoiado por evidência / revisado por profissional) e `impact_tags.is_primary`. Não existe peso, percentual nem contribuição direta × indireta |
| 4 | **ESG estruturado** | `esg_pillars` tem **3 linhas** (E, S, G) e `indicator_catalog.esg_dimension` tem 1 letra. Sem subtema, sem indicador por pilar. `docs/ESG_ODS.md` já declara isso como vermelho |
| 5 | **Fonte do indicador** | `indicator_catalog` tem `origin` (procedência institucional) e **não** tem citação de fonte. `ods_targets.source` existe; o catálogo de indicadores, não |
| 6 | **`baseline_source` em `project_indicators`** | Existe em `program_indicators` (v0.17.0, com `CHECK`) e **falta** em `project_indicators` — inconsistência minha, da v0.17.0 |
| 7 | **Evidência persistida com procedência** | A tipologia rica de `core/evidence.py` é calculada **em memória a cada requisição**. A tabela `evidences` não tem coluna de fonte, de validade nem de instante de observação com semântica de frescor. `solution_evidence.source_type` (9 valores) é o protótipo a generalizar |
| 8 | **Catálogo de territórios** | O código territorial é validado por **regex** (`BR-MT-5105150`), e a hierarquia é derivada por prefixo em Python (`covers`, `specificity`). **Não há tabela de municípios**, nem FK, nem população |
| 9 | **Busca para autocompletar** | Existem full-text de soluções (`tsvector` com `pt_unaccent`), tesauro de conceitos com correção de digitação e `ILIKE` de organizações — **nada exposto como rota de busca incremental** |
| 10 | **Diagnóstico → integridade de alegação** | `GAPS` já detecta "nenhuma fonte citada para o problema" e "nenhuma medição validada". Falta o confronto alegação × indicador × evidência |

## 4. O que NÃO EXISTE (vermelho) — e cada varredura que prova

| # | O que | Varredura |
|---|---|---|
| 1 | **Equidade** | `equity`/`equidade`: **0 ocorrências**. `barrier`/`barreira`: **0**. `additionality`/`adicionalidade`: **0**. `per_capita`: **0**. "população elegível": **0** |
| 2 | **Normalização** | 39 ocorrências de `normaliz`, **todas** irrelevantes (`unicodedata.normalize`, `normalize_email`, renormalização de pesos). Nenhuma normalização estatística |
| 3 | **Materialidade** | `materialidade`/`materiality`: **0 ocorrências**. Os 46 hits de "material" são material didático e `seal_material()` |
| 4 | **População e indicadores territoriais** | Nenhuma tabela. Nenhum dado IBGE/Censo — a própria rota de determinantes declara: "NÃO são estatísticas populacionais" |
| 5 | **Reputação da organização** | `reputation`: 4 hits, todos prosa. `trust_score`: **0**. Nenhum nível agregado, nenhuma contestação **de score** (a de sanção existe e serve de molde) |
| 6 | **Detector de alegação sem evidência** | `greenwash`/`washing`: **0 ocorrências**. Não existe entidade de alegação nem confronto |
| 7 | **Autocomplete** | `typeahead`: 0. `combobox`: 0. `datalist`: 0. Os 5 hits de `autocomplete` são o atributo HTML do navegador |
| 8 | **CEP, consulta de CNPJ, municípios** | Rota de CEP: **0**. Consulta externa de CNPJ: **0** (só validação de dígito local). Rota de municípios: **0** |
| 9 | **Atribuição de responsabilidade** | `ResponsibilityAssignment`/`responsibility`: **0** em `backend/` e `web/src`. Existe `signatures.role` com 3 valores e quatro-olhos; falta a entidade |
| 10 | **GRI, ISSB, TCFD, IRIS+, SROI, Teoria da Mudança, Marco Lógico** | `\bGRI\b`: 4 menções, **todas de exclusão** nas minutas legais. `ISSB`: 1, idem. `TCFD`, `IRIS`, `SROI`, `theory_of_change`, `logical_framework`: **0** |

## 5. Onde eu discordo dos prompts, e o que proponho no lugar

Os prompts mandam explicitamente melhorar o que estiver abaixo da melhor solução. Quatro pontos:

### 5.1. A fórmula de impacto contextual não deve ser implementada como multiplicação

Os documentos propõem `IMPACT = OUTCOME × CONTEXT × NEED × EQUITY × ADDITIONALITY × EVIDENCE ×
SUSTAINABILITY` — e eles próprios dizem para não implementá-la literalmente. Concordo, e o motivo é
concreto: **multiplicar sete fatores estimados produz um número com aparência de precisão e sem
significado**. Pior, esconde a decisão: quem escolheu o peso decide o resultado, e ninguém vê.

**Proposta implementada:** o contexto de equidade é **descritivo e declarado com fonte**, não um
multiplicador. O produto passa a registrar barreira, necessidade, adicionalidade e denominador — cada
um com fonte e data — e a **normalização é explícita e rotulada**: absoluto, per capita, por recurso,
por população elegível. E a trava: **sem denominador declarado com fonte, não há número normalizado**
— a mesma disciplina das linhas de base da v0.17.0, que nascem sem número.

### 5.2. A comparação entre dois projetos deve poder se RECUSAR

O teste que os documentos pedem (projeto A com 5.000 beneficiários × projeto B com 120 em território
remoto) tem uma resposta melhor que "contextualizar e ranquear": **declarar que não são comparáveis**
quando faltam os denominadores e a evidência. A função de comparação devolve as dimensões lado a lado
com a fonte de cada uma e `comparable: false` + o motivo quando não há base. Ranquear com dado
faltante é o erro que a contextualização deveria evitar, não maquiar.

### 5.3. "Certificado" não entra como estado possível

A escada pedida é `aligned → mapped → assessed → reported → verified → audited → certified`.
Implemento os seis primeiros e **o banco recusa `certified`**: a Plataforma não é organismo
certificador, e deixar o estado disponível é convidar o erro. Mesma trava de v0.17.0 nos cartões
legais.

### 5.4. Reputação de pessoa física e de governo recebe tratamento diferente

Os documentos pedem perfil de profissional e de governo, e ao mesmo tempo alertam contra ranking
político e contra decisão automatizada sobre pessoas. A conciliação:

- **organização (pessoa jurídica)**: perfil multidimensional com nota por dimensão, confiança,
  contagem de evidências, versão de modelo, contestação e correção;
- **órgão público**: perfil de transparência e governança **sem número agregado** — só os indicadores
  que o originaram, porque "Prefeitura X tem nota 78" é indefensável e os documentos dizem isso;
- **pessoa física (profissional)**: as dimensões existem a partir de fatos verificados da plataforma,
  e **não há nota agregada pública**. O titular vê o seu perfil; terceiros veem contagens
  verificáveis, não um número que decide contratação.

## 6. O que depende de decisão ou contratação do proprietário

| # | Item | Por que não é decisão de engenharia |
|---|---|---|
| 1 | **Carga das 169 metas oficiais de ODS e dos indicadores globais** | O texto oficial precisa vir de fonte oficial. A rede deste ambiente alcança só registros de pacote, e o pedido de permissão para buscar na ONU não foi respondido. **Não vou transcrever de memória**: a tabela continua vazia, e esta rodada entrega o **importador** (`scripts/import_ods_targets.py`) que carrega o arquivo oficial com nome de fonte, URL e data de consulta |
| 2 | **Dados do IBGE (população por município, indicadores territoriais)** | Mesma razão. Esta rodada entrega a **estrutura** e o importador; o dado entra quando houver o arquivo |
| 3 | **Licença de uso dos emblemas oficiais dos ODS** | Número, nome e cor oficial estão em `ods_goals`; a arte depende de autorização de uso de marca da ONU |
| 4 | **Decisão sobre frameworks de terceiros (GRI, ISSB, IRIS+)** | As minutas legais da v0.17.0 **excluem** expressamente relatório pronto para CVM, GRI, SASB e ISSB. Mapear indicador para esses códigos muda o que as minutas prometem, e isso é decisão de produto **e** de jurídico, não só técnica. Esta rodada entrega o registro de frameworks **capaz** de receber esses mapeamentos, com os três primeiros cadastrados como `registry_only` e **nenhum mapeamento inventado** |
| 5 | **Revisão técnica da lista de determinantes sociais** | A própria migração declara: "lista EDITORIAL… a redação é nossa e precisa de revisão técnica" |

## 7. Backlog desta rodada, em ordem de dependência

| Fase | Entrega | Depende de |
|---|---|---|
| 2 | Contexto de equidade + normalização rotulada + comparação que se recusa | — |
| 3 | Território como catálogo (com população por fonte) + determinantes com indicador | 2 |
| 4 | Registro de frameworks + mapeamento de indicador + escada sem `certified` + materialidade | — |
| 5 | Evidência persistida com procedência (generalizando `solution_evidence.source_type`) | — |
| 6 | Integridade de alegação: entidade `claims` + confronto determinístico + FLAGGED | 4, 5 |
| 7 | Reputação explicável, com contestação e correção | 5 |
| 8 | Selo de impacto (estendendo o motor de selos existente) | 6, 7 |
| 9 | Rotas de busca incremental + componente de autocomplete | 3 |
| 10 | Atribuição de responsabilidade (escopo, período, ato) | — |
| 11 | Segurança, LGPD e QA das tabelas novas | 2–10 |
| 12 | Desempenho | 2–10 |
| 13 | Documentação, release, pacote | tudo |

## PHASE STATUS — FASE 1

- **Entregue:** este documento, com 12 itens verdes, 10 amarelos e 10 vermelhos, cada um com a
  varredura que o sustenta.
- **Decidido:** quatro divergências dos prompts, declaradas no §5, com o motivo de cada uma.
- **Bloqueado por terceiro:** carga de dado oficial (ODS e IBGE) — estrutura e importador entram
  nesta rodada; o dado depende de arquivo oficial.
- **Próxima:** FASE 2 — contexto de equidade, normalização rotulada e comparação que se recusa a
  ranquear sem base.

## PHASE STATUS — FASES 2 a 5

| Fase | Entregue | Prova |
|---|---|---|
| 2 | Contexto de equidade, 12 barreiras editoriais, denominador versionado com fonte obrigatória, 7 métodos de normalização, comparação que se recusa | `0025_v0180_equity.sql`, `impact/equity.py`, 12 rotas, `test_v0180_equity.py` (30 testes) |
| 3 | Território como catálogo com `from_official_load`, 15 definições de indicador de determinante, perfil territorial que mostra o que **não** é medido, dois importadores que exigem fonte | `0026_v0180_territory.sql`, `impact/territory.py`, 5 rotas, `test_v0180_territory.py` (20 testes) |
| 4 | Registro de 19 referenciais, mapeamento de indicador com escada de seis degraus **sem** `certified`, cobertura ("consigo relatar?"), materialidade com `is_material` derivada | `0027_v0180_frameworks.sql`, `impact/frameworks.py`, 11 rotas, `test_v0180_frameworks.py` (24 testes) |
| 5 | Integridade de alegação: 11 regras determinísticas, situação **derivada** (sem coluna), revisão humana por convite nomeado de outra organização | `0028_v0180_claims.sql`, `impact/claims.py`, 9 rotas, `test_v0180_claims.py` (42 testes), `CLAIM_INTEGRITY.md` |

- **Suíte:** 1.077 testes, 0 falhas, 17 ignorados (eram 961 ao fim da v0.17.0).
- **Decisões registradas:** ADR-191 a ADR-200.
- **Bloqueado por terceiro, sem contorno:** 169 metas oficiais dos ODS e dados do IBGE (a rede do
  ambiente alcança só registros de pacote); mapeamento para GRI/ISSB/IRIS+ depende de decisão de
  produto **e** jurídica, porque as minutas da v0.17.0 excluem esses relatórios.
- **Próxima:** FASE 6 — reputação explicável, com contestação e correção, sem transformar a nota em
  caixa-preta que determina acesso.
