# Formulários inteligentes: sugestão com procedência — FASE 8 da v0.18.0

> Backend: `backend/impacto/impact/lookups.py`, `backend/impacto/api/lookup_routes.py`.
> Interface: `web/src/ui/suggest.tsx`. Testes: `backend/tests/test_v0180_lookups.py`.

## 1. As duas regras

**Toda sugestão diz de onde veio.** Cada linha devolvida carrega `origin`, `origin_label` e, quando
existem, `source_name` e `source_date`, mais `verified` (houve ato de terceiro por trás daquela
linha). Sugestão sem origem é sugestão que a pessoa não pode avaliar — e por isso não existe aqui.

**Sugestão nunca sobrescreve em silêncio.** O texto digitado é a verdade. O componente `Suggest`
preenche direto apenas quando o campo está vazio ou quando o que foi digitado é **prefixo** da
sugestão (a pessoa estava digitando aquilo). Em qualquer outro caso pergunta:

> Você escreveu **Cuiabá Velho**. Trocar por **Cuiabá**? · carga oficial (com fonte e data)
> [ Usar a sugestão ] [ Manter o que escrevi ]

Depois de aceitar, fica visível a etiqueta de origem, a fonte e o botão **"Voltar ao que eu havia
escrito"**.

## 2. As cinco origens

| Origem | Significa | Exemplo |
|---|---|---|
| `official_load` | entrou por carga oficial, com fonte e data | município carregado do IBGE |
| `platform_knowledge` | conhecimento da plataforma — **conferir na carga oficial** | as 27 UFs semeadas na FASE 3 |
| `platform_editorial` | lista editorial nossa | barreiras de equidade, temas de materialidade |
| `your_organization` | histórico da própria organização | fornecedor que já usei, meus projetos |
| `another_organization` | declarado por outra organização | reservado; nenhuma busca usa hoje |

A distinção entre as duas primeiras é a honestidade mais específica desta rodada: **27 unidades da
federação digitadas por mim não são dado do IBGE**, e o teste
`test_the_seeded_territories_are_platform_knowledge_not_official_load` falha se alguém as marcar
como carga oficial.

## 3. As treze buscas

`territories`, `ods`, `ods_targets`, `indicators`, `equity_barriers`, `determinants`,
`materiality_topics`, `frameworks`, `seal_rules`, `beneficiary_groups`, `legal_natures`,
`my_suppliers`, `my_projects`.

Cada chave é **uma consulta escrita à mão**, com colunas escolhidas. Não existe busca genérica
parametrizável: seria um caminho para ler o que não deve.

`ods_targets` devolve lista vazia, e isso está correto — as 169 metas oficiais não foram carregadas
(a rede do ambiente alcança só registros de pacote). A busca existe, o importador existe, o dado não.
Um teste fixa esse estado para que ele não passe por esquecimento.

## 4. Isolamento

`my_suppliers`, `my_projects` e os indicadores próprios da organização são filtrados por `org_id`,
e há um teste por caso provando que outra organização recebe lista vazia. **Autocomplete é uma das
formas mais silenciosas de vazar dado** — a sugestão aparece sem que ninguém tenha pedido por
aquele registro.

`%` e `_` digitados são texto, não curinga: sem escapar, quem digita `%` receberia o catálogo
inteiro como se fosse sugestão para o que escreveu.

## 5. Formulário em etapas (`Steps`)

Progressive disclosure com uma regra: **nunca esconder trabalho já feito.** Cada etapa diz por que
está fechada e oferece **"Abrir agora mesmo assim"**. Esconder campo preenchido é perda de trabalho,
e perda de trabalho em formulário longo é a causa mais comum de abandono.

## 6. Procedência que volta para o formulário

`onProvenance` entrega ao formulário `{filled_by: "typed" | "suggestion", origin, source_name,
source_date, accepted_value, replaced_text}`. É o que permite, mais adiante, gravar **como** um
campo foi preenchido — e é a razão de o componente guardar o texto substituído.

Hoje nenhum formulário persiste essa procedência: o contrato está pronto e a gravação é dívida
declarada, não feito.

## 7. O que esta fase NÃO faz

- **Não persiste a procedência** do preenchimento (§6).
- **Não usa IA** para sugerir. Nenhuma sugestão vem de modelo: são consultas aos catálogos.
- **Não aplicou o componente em todos os formulários.** Está em uso nos dois campos de território da
  busca de editais e da busca salva, como prova de ponta a ponta; espalhar pelo resto é trabalho da
  fase de design, que vai decidir onde cada busca aparece.
- **Não há busca por semelhança fonética** (sem `pg_trgm`/`unaccent`): a busca é `ILIKE`, então
  "Cuiaba" sem acento não encontra "Cuiabá". É dívida declarada, e a correção passa por extensão de
  banco.
