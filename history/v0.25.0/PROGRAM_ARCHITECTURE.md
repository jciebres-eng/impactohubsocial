# Programa: a entidade que faltava para o cliente institucional (v0.17.0)

> Escrito a partir de `backend/migrations/0018_v0170_programs.sql` e
> `backend/impacto/economics/programs.py`. 19 testes em `backend/tests/test_v0170_programs.py`.

## 1. Por que Programa existe

A auditoria econômica que abriu esta rodada achou o vazio: a Plataforma sabia representar **projeto**
(da OSC) e **edital** (da chamada), mas não sabia representar **programa** — a unidade com que um
instituto, uma fundação ou uma secretaria pensa o próprio dinheiro. Sem ela, o cliente institucional
tinha telas de projeto alheio e nenhum lugar para a sua carteira.

Programa é o que torna o institucional vendável, e é por isso que ele é a primeira entrega da camada
econômica: o problema caro que o B2B compra é **gestão de portfólio com prestação de contas
auditável**, não um pacote de funcionalidades.

## 2. O que um Programa tem

| Tabela | Conteúdo |
|---|---|
| `programs` | dono, título, resumo, **objetivo (obrigatório)**, orçamento, territórios, causas, ODS, esfera, instrumento, prazos, visibilidade, situação |
| `program_calls` | as chamadas (editais) do programa |
| `program_projects` | a carteira: projeto + papel (`candidate`, `selected`, `funded`, `monitored`, `declined`, `withdrawn`) |
| `program_indicators` | indicadores do programa, com meta e linha de base |
| `program_needs` | necessidades territoriais que o programa se propõe a atender |

`objective` é **NOT NULL**: programa sem objetivo declarado não é programa, é uma pasta de projetos.

## 3. As travas, e o que cada uma impede

**Situação é grafo no banco** (`program_status_graph`, 11 arestas com ator `owner`, `platform` ou
`either`). `program_status_guard()` recusa transição que não esteja no grafo e **deriva** `published_at`
e `closed_at` — e levanta exceção se alguém tentar escrever essas datas fora de uma transição.

> Lição aplicada aqui: `published_at` e `closed_at` **não** entram em `guard_columns`. Gatilhos disparam
> em ordem alfabética, e guardar uma coluna que outro gatilho deriva faz a transição legítima do próprio
> dono voltar 403. Esse erro foi cometido na v0.16.0 com `marketplace_listings` e `impact_updates`, e de
> novo na primeira versão desta migração. Só `owner_org_id` é guardado.

**Visibilidade não contradiz moderação.** `program_visibility_guard()` recusa tornar público um programa
suspenso — mas **não** impede suspender um programa que já está público, que foi o defeito da primeira
versão: a trava bloqueava a própria moderação.

**Vínculo é da organização dona.** `program_link_guard()` recusa anexar chamada, projeto, indicador ou
necessidade que não pertença ao programa da organização.

**Linha de base exige fonte.** CHECK no banco: `baseline_value` sem `baseline_source` é recusado. Número
de partida sem fonte é número inventado, e o programa inteiro passa a medir contra ele.

## 4. As três funções que separam o declarado do medido

### `program_financials(program_id)`

Devolve, em colunas distintas: orçamento declarado, comprometido, **gasto** e **comprovado**. A
diferença entre os dois últimos é o ponto:

```sql
-- `expenses.status = 'validated'` é conferência humana; `document_id IS NOT NULL` é o comprovante
-- no cofre. Despesa registrada sem comprovante conta em `spent` e NÃO conta em `evidenced`.
```

Somar as duas daria um número maior e mais bonito que não corresponde a nada.

### `result_chain(program_id)`

Insumo → atividade → produto → resultado, com a **força declarada de cada elo**, separando elo forte de
elo fraco. A resposta carrega uma nota dizendo que elo declarado não é resultado comprovado: a função
não promove hipótese a evidência, e é justamente essa promoção que faz relatório de impacto virar
ficção.

### `territorial_gap(prefixo)`

Onde a carteira não chega, com `evidence_quality` por território: lacuna apontada por necessidade **sem
fonte citada** vem marcada como tal. A nota da resposta diz, em letras, que isto não é censo.

## 5. Notificação a toda a equipe

Pedido explícito da rodada anterior e mantido aqui: toda mudança de etapa, de vínculo ou de documento
notifica **toda a equipe envolvida**, pelas funções `notify_team()` e `notify_org_members()` já
existentes. Quando um projeto entra na carteira de um programa, a organização executora é notificada —
há teste para isso. O grupo de preferência `program` foi acrescentado a `notification_prefs`, que agora
tem 15 grupos.

## 6. Visibilidade

| Valor | Quem vê |
|---|---|
| `private` | só a organização dona |
| `network` | qualquer organização autenticada |
| `public` | qualquer pessoa, **e somente se** publicado e não suspenso |

A política `programs_read` exige `visibility = 'public' AND published_at IS NOT NULL AND status <>
'suspended'` para o acesso anônimo, e `programs.public_feed()` repete o mesmo filtro num único lugar.
`GET /v1/programs/feed` e `GET /v1/programs/{id}` são as duas rotas públicas novas, e estão na lista
revisada de rotas públicas do teste de arquitetura.

Um detalhe que custou um defeito: `ctx.org_id` **levanta 409** quando não há organização ativa, então
ler um programa sem sessão devolvia "selecione uma organização" — vazamento de existência. O acesso
anônimo usa `ctx.principal.org_id if ctx.principal else None`.

## 7. Desempenho

Na escala cheia (10.000 programas, 10.000 vínculos): feed público 40 ms, `program_financials` 3–4 ms,
`result_chain` 2 ms. Todos os acessos quentes por índice. Números e método em `PERFORMANCE_REPORT.md`
§7.
