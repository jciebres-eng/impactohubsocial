# SDG_ESG_TAXONOMY — ODS, ESG e determinantes sociais

## 1. ODS (Objetivos de Desenvolvimento Sustentável, Agenda 2030 da ONU)
A plataforma traz os **17 objetivos** com número, código (`ODS1`…`ODS17`), nome em português e inglês e a **cor oficial**
da identidade visual dos ODS. Catálogo em `sdg_goals`, exposto em `GET /v1/impact-taxonomy`.

### Marcas e emblemas — leia antes de desenhar
**Os emblemas/logos dos ODS, a roda colorida e o emblema das Nações Unidas são marcas protegidas e NÃO acompanham esta
plataforma.** Nenhum arquivo de imagem da ONU está no repositório ou no pacote de release. O que a plataforma distribui é
dado factual: número, nome e o valor hexadecimal da cor.
Para usar os emblemas oficiais em material da plataforma é necessário seguir as diretrizes de uso da ONU e obter a
autorização aplicável. **AUTORIZAÇÃO EXTERNA NECESSÁRIA** — decisão do proprietário, não de engenharia.
Na interface, os marcadores são desenhados como etiquetas com a cor oficial e o nome do objetivo — sem emblema.

**Não incluímos as 169 metas** dos ODS. Transcrevê-las de memória produziria texto impreciso; se forem necessárias, o
caminho é importar da fonte oficial com data de consulta registrada (mesmo padrão das regras fiscais).

## 2. ESG
Três pilares (`E`, `S`, `G`) com nome e descrição próprias da plataforma, em `esg_pillars`. ESG não é norma única: há
vários referenciais (GRI, SASB, ISSB). O que está aqui é **classificação editorial** para organizar o que a organização
declara, não aderência a um padrão de relato. Relato em padrão GRI/ISSB é trabalho de consultoria, não de catálogo.

## 3. Determinantes sociais da saúde
Onze determinantes em `social_determinants`, organizados em quatro camadas (`individual`, `social_community`,
`living_working`, `socioeconomic`): renda, educação, trabalho, moradia e saneamento, segurança alimentar, ambiente e
território, acesso a serviços de saúde, rede e apoio social, violência e segurança, discriminação e desigualdade, curso
de vida.
**Base e limite:** inspirado no modelo de Dahlgren e Whitehead, adotado pela Comissão Nacional sobre Determinantes
Sociais da Saúde (CNDSS). **A redação e o agrupamento são da plataforma, e a revisão técnica está pendente** — cada linha
carrega esse aviso no campo `source_note`, e a API repete na resposta. Não é classificação oficial de nenhum órgão.

## 4. Marcadores (`impact_tags`)
Ligam qualquer objeto do domínio (`project`, `solution`, `diagnosis`, `need`, `call`, `organization`, `agreement`) a um
item de taxonomia, com indicação de principal e observação.
Integridade garantida por gatilho: um código que não existe na taxonomia correspondente é **recusado pelo banco**
(`ODS99`, pilar `X`, determinante inventado → erro). Isso vale também para quem escreve direto no banco.

**Convivência com o que já existia:** `organizations.ods`, `projects.ods`, `solutions.ods` e `calls.ods` são arrays de
`smallint` que existem desde a v0.7.0 e **continuam funcionando**. Os marcadores não os substituem: eles acrescentam
ESG e determinantes (que os arrays não cobrem) e o objeto `diagnosis`/`agreement` (que não tinha array). O catálogo agora
dá nome e cor para os números que os arrays já guardavam.

## 5. API
| Rota | O que faz |
|---|---|
| `GET /v1/impact-taxonomy` | catálogo completo: 17 ODS com cor, 3 pilares ESG, 11 determinantes, mais os avisos de marca e de revisão pendente |
| `POST /v1/impact-tags` | aplica marcador (idempotente: reaplicar atualiza) |
| `GET /v1/impact-tags?subject_type=&subject_id=` | marcadores do objeto, já com nome e cor |
| `DELETE /v1/impact-tags/{id}` | remove |

Na interface, o componente `ImpactTags` (`web/src/pages/taxonomy.tsx`) é reutilizável e já está ligado no detalhe do
projeto e na campanha pública.
