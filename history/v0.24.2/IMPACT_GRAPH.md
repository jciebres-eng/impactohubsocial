# Grafo de impacto: as entidades e como elas se ligam (v0.16.0)

O pedido desta rodada listou 24 entidades do "grafo de impacto" e pediu que fossem **relacionais**, sem banco de
grafos sem necessidade comprovada. Esta é a tradução entre o vocabulário do pedido e o que existe no banco — incluindo
os casos em que a entidade pedida **já existia com outro nome**, e aqueles em que ela **não é uma tabela de
propósito**.

## As 24 entidades pedidas

| Entidade pedida | Onde vive | Observação |
|---|---|---|
| Person | `users` + `public_profiles` (user_id) | A pessoa atua pela organização dela; o perfil público é dela. |
| Organization | `organizations` (6 tipos) | Já existia desde a v0.7.0. |
| Professional | `organizations(kind='provider')` + `professional_credentials` + `professional_experiences` | **Não** é tabela nova: profissional é uma organização `provider` com credenciais e experiências. Criar uma tabela `professionals` duplicaria identidade, cobrança e permissão. |
| Investor | `organizations(kind='company'/'individual')` + `org_personas(persona='investor')` | Investir é uma forma de ATUAR, declarada como persona. |
| GovernmentEntity | `organizations(kind='government')` | — |
| Project | `projects` + `project_status_graph` | v0.15.0. |
| Idea | `ideas` | v0.15.0. A ideia não é apagada ao virar projeto. |
| Need | `project_needs` (do projeto) e `territory_needs` (do território) | Duas tabelas porque são duas coisas: a necessidade de um projeto e a demanda de um lugar. |
| Solution | `solutions` | v0.9.0. |
| Opportunity | `calls` | Edital/programa. Já existia. |
| Document | `documents` + `document_assemblies` + `signatures` | v0.7.0–v0.15.0. |
| Proposal | `proposals` + `proposal_events` + `proposal_status_graph` | **Novo.** |
| Investment | `investment_intents` → `commitments` → `transactions`/`disbursements` | **Três etapas separadas de propósito.** Ver abaixo. |
| Service | `professional_services` + `proposals(kind='service')` | — |
| Partnership | `relationships(kind='partnership')` + `partnerships` (legado) | A relação nova cobre; a tabela antiga continua para não quebrar rota. |
| Conversation | `conversations` (com contexto, desde a 0016) | — |
| Message | `messages` (com tipo e referência) | — |
| Milestone | `milestones` | — |
| Indicator | `indicator_catalog` + `project_indicators` + `indicator_values` | `result_kind` separa produto/resultado/impacto. |
| Evidence | `evidences` + `core/evidence.py` | `verified` deriva da fonte. |
| Credential | `professional_credentials` | Verificação com estado real. |
| ODS | `ods_goals` (17) | — |
| ESGTheme | `projects.esg_tags`, `marketplace_listings.esg_tags` + taxonomia `esg_theme` | Atributo, não entidade com ciclo de vida próprio. |
| Territory | `projects.territory`, `territory_needs.territory` (padrão `INT`/`UF`/`UF-XX`/IBGE) | **Não é tabela.** Território é um código normalizado, e transformá-lo em tabela exigiria sincronizar a malha territorial brasileira inteira — dependência externa que a plataforma não tem e não inventa. |

## As arestas: uma tabela, não trinta

Antes desta versão, "relação" estava espalhada em seis tabelas improvisadas (`follows`, `favorites`, `org_blocks`,
`need_offers`, `solution_intents`, `partnership_requests`), cada uma com suas colunas e sua ideia de estado. Não havia
como responder "com quem esta organização se relaciona?" sem seis consultas, e cada motor novo criaria a sétima.

Agora existe `relationships`, com **22 tipos** e chave estrangeira de verdade para cada ponta:

* **origem**: exatamente uma de `source_org_id` ou `source_user_id` (CHECK soma = 1);
* **destino**: exatamente uma de sete — organização, pessoa, projeto, solução, edital, necessidade, ideia (CHECK soma = 1);
* **contexto**: `context_project_id` (a relação quase sempre existe POR CAUSA de algo);
* **visibilidade**: cinco níveis, com teto por tipo;
* **situação**: seis estados, com máquina explícita;
* **procedência**: `origin_proposal_id` quando a relação nasceu do aceite de uma proposta;
* **autoria e evidência**: `created_by`, `evidence_document_id`.

Por que colunas de chave estrangeira em vez de `target_type` + `target_id`: porque com FK declarada **não existe linha
órfã possível**, e são 627 chaves estrangeiras no banco sem nenhuma referência por convenção. Um `target_id` solto
seria a primeira.

Detalhe que importa: `ux_rel_identity` é um índice único sobre `coalesce(...)` das pontas e do contexto, de modo que
"favoritar" duas vezes não cria duas linhas — e o motor devolve a relação existente em vez de erro.

## A cadeia financeira, em três etapas que nunca se confundem

```
InvestmentIntent          Commitment                    Transaction/Disbursement
"quero apoiar"            "assumo o compromisso"        "o dinheiro saiu/entrou"
investment_intents        commitments                   transactions, disbursements
  ↑ nasce do aceite         ↑ exige candidatura            ↑ exige compromisso
    de uma proposta           (application_id NOT NULL)
```

O CHECK `(status = 'committed') = (commitment_id IS NOT NULL)` em `investment_intents` torna impossível uma intenção
dizer-se comprometida sem compromisso. `project_funding()` soma **compromissos**, não intenções — por isso aceitar uma
proposta de investimento de R$ 15 milhões deixa `committed_cents` em zero, e há um invariante que verifica exatamente
isso. A plataforma nunca escreve "investido" quando houve apenas interesse.

## Os fatos do grafo

`domain_events` registra **o fato**, uma vez, na transação em que aconteceu — 37 tipos de evento no formato
`Entidade.fato`. É a fonte única que alimenta aviso, linha de tempo, auditoria e recomendação. A escrita passa por
`app_record_event()` (SECURITY DEFINER) e não por INSERT direto, porque um fato da rede envolve **duas** organizações
e uma política de inquilino recusaria exatamente o registro que interessa; em troca, a função amarra a autoria a
`app_uid()`. `INSERT` em `domain_events` está revogado para o papel da aplicação, então esse é o único caminho.
