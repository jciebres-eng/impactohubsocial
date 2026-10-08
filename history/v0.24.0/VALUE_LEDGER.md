# Registro de valor entregue (v0.17.0)

> Escrito a partir de `backend/migrations/0019_v0170_value_ledger.sql` e
> `backend/impacto/economics/value_ledger.py`. 16 testes em `backend/tests/test_v0170_value.py`.

## 1. Por que separado da cobrança

O pedido da rodada é explícito: **Value Ledger separado do Billing**. O motivo é prático, não estético.
Quando o registro do que foi entregue e o registro do que foi cobrado moram juntos, o número da entrega
começa a servir à conta — e ninguém percebe o momento em que isso acontece.

Separados, dá para responder duas perguntas diferentes com dois dados diferentes:

- **o que a Plataforma entregou?** → `value_events`
- **o que a Plataforma cobrou?** → `platform_charges` e `invoices`

E dá para responder uma terceira, que é a interessante: **o que foi entregue e NÃO foi cobrado?**

## 2. Os onze tipos de evento

Cada tipo em `value_event_types` tem um campo `what_counts` dizendo, em português, o que conta e o que
não conta:

| Tipo | O que conta |
|---|---|
| `readiness.evaluated` | retrato de prontidão gravado |
| `readiness.gap_found` | impedimento identificado com critério |
| `match.run_completed` | avaliação de compatibilidade persistida |
| `diagnosis.version_published` | versão de diagnóstico publicada |
| `document.assembled` | documento gerado a partir de modelo |
| `document.blocked_incomplete` | **a recusa**: documento que a Plataforma se negou a gerar porque faltava campo ou evidência |
| `impact_report.accepted` | prestação de contas aceita por quem apoiou |
| `program.projects_screened` | projeto triado para a carteira de um programa |
| `territorial_gap.computed` | lacuna territorial calculada |
| `risk.scan_completed` | varredura de risco concluída |
| `ai.analysis_completed` | análise assistida por IA concluída |

`document.blocked_incomplete` merece nota: **a recusa é valor entregue**. Quando a Plataforma se nega a
gerar uma prestação de contas incompleta, ela impediu um problema — e isso é registrado antes de a
exceção subir.

## 3. A trava que mais incomoda: a linha de base nasce SEM NÚMERO

Precisão importa aqui, e a primeira versão deste documento errou: `value_baselines` **tem** uma linha
por tipo de evento desde a migração — e todas nascem com `minutes_per_unit` **nulo**, com a nota
"Linha de referência não definida". A linha existe para que a ausência do número seja visível; o que não
existe é o número.

Enquanto ninguém declarar quanto tempo uma tarefa levava antes — com **fonte, data e método**, exigidos
pelo CHECK `baseline_needs_source` — nenhum evento produz estimativa de tempo economizado: o evento fica
com `estimate_status = 'no_baseline'`.

`summary()` devolve `events_without_baseline` para que a ausência seja visível em vez de silenciosa.

"Economizamos 40 horas por mês para cada OSC" sem linha de base é marketing com cara de métrica. Com
linha de base declarada, é uma conta que alguém pode conferir e contestar. A diferença entre as duas
coisas é `minutes_per_unit` estar nulo.

E a estimativa **não pode ser passada como parâmetro**: `app_record_value()` é a única porta de escrita
(o app não tem INSERT em `value_events`), e ela calcula `minutes_saved_estimate` a partir da linha de
base vigente — nunca do que o chamador disse.

## 4. Onde os eventos são registrados

Sempre na **ação durável**, nunca na leitura. Registrar na leitura faria uma tela aberta duas vezes
valer duas entregas:

| Gancho | Momento |
|---|---|
| `readiness.snapshot()` | retrato gravado |
| `lifecycle.scan_risks()` | varredura concluída |
| `diagnostic.publish_version()` | versão publicada |
| `assembly.generate()` | documento gerado |
| `assembly` (recusa por incompletude) | **antes** de levantar a exceção |
| `matching.persist()` | avaliação persistida |
| `impact_report.transition()` | ao chegar em `accepted` |
| `programs.set_project()` | projeto triado |
| `engines/ai/gateway._log` | uso de IA registrado |

## 5. Falha no registro não derruba a ação do usuário

Todo registro acontece dentro de `SAVEPOINT`. A razão é concreta e foi aprendida errando: capturar
exceção de banco **sem** SAVEPOINT deixa a transação abortada, e o trabalho do usuário desaparece no
COMMIT sem nenhuma mensagem.

```python
conn.run("SAVEPOINT value_ledger")
try:
    out = conn.scalar("SELECT app_record_value($1,...)", ...)
    ...
except Exception as exc:
    conn.run("ROLLBACK TO SAVEPOINT value_ledger")
    _LOG.warning("value_ledger_record_failed", extra={...})
    return None
conn.run("RELEASE SAVEPOINT value_ledger")
```

O `warning` existe porque o SAVEPOINT, sozinho, esconderia um defeito meu: na primeira versão eu passava
um `bigint` onde a função esperava `uuid`, e o registro falhava **em silêncio**. Trava que engole erro
sem avisar é trava que mente.

## 6. Custo de IA

`ai_usage` ganhou `cost_cents_estimate`, `cost_currency`, `price_id` e `cost_status`.
`app_price_ai_usage()` calcula o custo a partir de `ai_price_table` — que **nasce sem nenhuma linha**,
porque nenhum preço de provedor foi inventado (a de linhas de base tem linha sem número; esta não tem
linha). Sem
preço declarado, o custo fica `no_price` em vez de zero: zero é um número, e um número errado é pior que
a ausência dele.

## 7. Rotas

| Rota | Para quê |
|---|---|
| `GET /v1/value/types` | os onze tipos, com `what_counts` |
| `GET /v1/value/summary` | o que foi entregue, por tipo, com `events_without_baseline` |
| `GET /v1/value/events` | o extrato |
| `POST /v1/admin/value/baselines` | declarar uma linha de base (exige fonte) |
| `GET /v1/admin/ai/cost` | custo de IA, com `no_price` quando não há preço |
