# Ciclo de relatório de impacto (v0.16.0)

O elo que diferencia a plataforma de um marketplace: **quem apoiou recebe prestação de contas no mesmo lugar onde
apoiou**, e os números não são digitados — são colhidos.

Motor: `backend/impacto/network/impact_report.py` · Tabela: `impact_updates` · Rotas: `/v1/impact-updates*`
Tela: `web/src/pages/impactreport.tsx`

## O ciclo

```
rascunho ──enviar──> enviado ──assumir──> em análise ──┬──pedir ajuste──> ajuste solicitado ──┐
                                                       │                                      │ (volta)
                                                       └──aceitar──> aceito ──publicar──> publicado
```

| Estado | Quem move | Exige nota | O que muda de verdade |
|---|---|---|---|
| `draft` → `submitted` | a organização dona | — | o gatilho **colhe os números** e grava `metrics`, `milestones`, `evidence_count` |
| `submitted` → `under_review` | quem apoia o projeto | — | `reviewed_by` derivado de `app_uid()` |
| `under_review` → `changes_requested` | quem apoia | **sim** | volta para a dona com o pedido escrito |
| `changes_requested` → `submitted` | a dona | — | recolhe os números outra vez (o período pode ter avançado) |
| `under_review` → `accepted` | quem apoia | — | aceite registrado no ledger |
| `accepted` → `published` | a dona | — | entra na projeção pública do perfil |

Um relatório por `(projeto, período)` — `UNIQUE` na tabela. Tentar abrir outro devolve **409** com o id do existente,
não um segundo relatório do mesmo trimestre.

## Quatro decisões que sustentam a honestidade

### 1. A apuração é do banco

`metrics`, `milestones` e `evidence_count` estão em `guard_columns(...)`: **nem o motor** consegue escrevê-las. Quem
grava é o gatilho `impact_update_guard()`, na transição para `submitted`, a partir de `app_impact_metrics(project_id,
period_start, period_end)` — uma função SQL que lê `indicator_values`, `milestones` e `evidences`.

Consequência: "atendemos 400 pessoas" **não é digitável**. Se não houver valor de indicador lançado no período, o
relatório sai com a métrica vazia e o texto fica sozinho — o que é a leitura honesta da situação.

`gather()` chama a **mesma** função para a prévia na tela, para que o que a organização vê antes de enviar nunca
divirja do que fica registrado. Antes dessa correção os números eram calculados em Python e gravados em coluna
guardada — o que simplesmente não passava (ver §Erros, FINAL_IMPACT_NETWORK_HARDENING_REPORT).

### 2. Quem revisa não é quem escreveu

CHECK na tabela: `reviewed_by <> created_by`. Recusado **em SQL direto**, não só na rota. E `_can_review()` exige que
a organização revisora seja parte do projeto como apoiadora (`app_project_supporter()`), investidora ou parte de
relação ativa — autorrevisão não é um caminho que exista.

### 3. Limitações são campo do relatório

`limitations` e `risks_note` são colunas de primeira classe. Dizer **o que o dado não prova** é parte de relatar com
honestidade; a plataforma oferece o campo em vez de deixar o silêncio parecer certeza. A tela mostra os dois em
destaque igual ao dos resultados, não escondidos num rodapé.

### 4. Publicar é decisão de quem executa, e só depois do aceite

Não há caminho de `draft` ou `submitted` para `published`. O relatório publicado alimenta a página pública; publicar
sem aceite seria a plataforma emprestando credibilidade a um texto que ninguém de fora conferiu.

## Notificação a toda a equipe

Toda transição chama `notify.project_event()`, que avisa `project_team()` — quem é da organização dona com papel
relevante **mais** quem apoia o projeto — com `action_label` e destino. Não é um aviso ao dono: é a equipe inteira
envolvida naquela etapa, que é o que o pedido manda (§"notificações para toda a equipe envolvida em cada evolução").

Uma transição gera **um** aviso por pessoa (`notify.dedupe()`, sha256 dos 40 primeiros caracteres do fato). O defeito
de aviso duplicado — um pela organização, outro pela equipe — foi corrigido ao fazer cada fato emitir um único
anúncio.

## O que fica no ledger

`created`, `submitted`, `accepted` e `published` entram no ledger de auditoria encadeado (`services/audit.ledger`),
com hash do estado anterior. `ledger_verify` continua válido depois das novas escritas — e as políticas
`ledger_insert`/`ledger_read` foram estendidas com `app_project_supporter()`, porque quem apoia precisa poder registrar
o próprio aceite.

## O que NÃO existe aqui

* **Não há** cálculo de impacto social agregado ("ROI social", "SROI"). A plataforma colhe indicadores declarados e
  evidências anexadas; não converte isso num número único que ninguém poderia auditar.
* **Não há** verificação independente automática. Aceitar um relatório é ato de quem apoia, humano e registrado.
* **Não há** publicação automática por decurso de prazo.
