# Motor de proveniência e integridade relacional — v0.23.0

> A regra que este motor impõe:
>
> **"Nenhum indicador crítico deveria existir sem conseguir apontar para sua origem/evidência."**

## 0. A leitura que esta versão implementa

A leitura literal da regra — proibir medição sem evidência — **impediria trabalho**: muita medição
começa autodeclarada e ganha evidência depois. A leitura implementada é mais útil e mais honesta:

> Medição autodeclarada é permitida. **Medição autodeclarada apresentada como validada, não.**

E a trava está no banco, não na rota, porque rota se contorna.

## 1. O que existia e o que faltava

`indicator_values.evidence_id` era nulo permitido e a tabela **não tinha gatilho nenhum**. Um valor
chegava a `status = 'validated'` — o estado que o produto apresenta como conferido — sem apontar
documento algum. A trava que existia conferia QUEM validou (`validated_by`, de organização
diferente da medida), não **com base em quê**.

## 2. As travas (migração 0053)

```sql
-- origem declarada, não adivinhada
source_kind ∈ ('evidence_document','system_calculated','external_import','self_declared')

-- dizer "veio de documento" e não apontar o documento é pior que não dizer nada
CHECK (source_kind <> 'evidence_document' OR evidence_id IS NOT NULL)

-- A TRAVA CENTRAL
CHECK (status <> 'validated' OR evidence_id IS NOT NULL)

-- e a origem não se reescreve depois de validada
TRIGGER indicator_provenance_is_frozen_after_validation
```

`source_kind` é **derivado** na rota, não pedido ao cliente: perguntar "qual a origem?" num campo
livre convidaria a dizer "documento" sem documento. Quem anexa evidência tem
`evidence_document`; quem não anexa é `self_declared`.

### Implantação em banco com dados

A migração **recusa subir** se existir linha já validada sem evidência. É deliberado: aceitar em
silêncio um estado que a regra proíbe tornaria a regra decorativa. O procedimento é conferir

```sql
SELECT count(*) FROM indicator_values WHERE status = 'validated' AND evidence_id IS NULL;
```

e decidir caso a caso — rebaixar o estado de uma medição alheia sem avisar quem a validou seria
apagar trabalho de terceiro.

### Prevenção E detecção

O motor de alegação (`impact/claims.py`) tem a regra `measurement_without_evidence`, que detecta
esse estado. Ela **não foi removida** por ter virado impossível: virou detector de manipulação. Se
alguém com acesso ao banco remover a restrição e forjar a linha, o verificador continua acusando.
`test_a_forged_validated_measurement_without_evidence_is_still_detected` simula exatamente esse
caminho; `test_the_schema_is_what_prevents_it_in_the_first_place` é o par dele.

## 3. A cadeia

`GET /v1/indicator-values/{id}/provenance` devolve, numa consulta:

```
projeto                         (título, organização, criação)
  → indicador                   (código, nome, unidade)
  → linha de base               (valor, FONTE, data)
  → documento                   (arquivo, versão, sha256, quem enviou, substituições)
  → evidência                   (tipo, título, estado, quem enviou)
  → revisão                     (quem revisou, de qual organização, quando, parecer)
  → medição                     (valor, data, quem reportou, origem declarada)
  → validação                   (quem validou, de qual organização, INDEPENDENTE?)
  → Impact Ledger               (seq, tipo, hash — conferível por ledger_verify())
  → eventos de auditoria        (seq, ação, ator, ip, requisição)
```

### `gaps`: o que FALTA, nomeado

Cada elo ausente aparece com o efeito dele sobre o que o número prova:

| Elo | Efeito declarado |
|---|---|
| `evidencia` | "O número é autodeclarado. O banco impede que ele seja apresentado como validado." |
| `documento` | "Há descrição do que aconteceu, não há arquivo para conferir." |
| `hash` | "Não é possível provar que o arquivo guardado é o que foi enviado." |
| `revisao` | "O arquivo existe; ninguém atestou que ele sustenta o número." |
| `linha_de_base` | "A variação medida não tem ponto de partida conferível." |
| `metodo` | "Dois medidores podem chegar a números diferentes sem errar." |
| `independencia` | "Validação não independente. O banco recusa este estado; se aparecer, é indício de alteração direta no banco." |
| `ledger` | "A medição não entra na cadeia de hash do projeto, então não é coberta por `ledger_verify()`." |

**Por que isso importa.** Uma cadeia de proveniência que esconde o elo que falta transforma ausência
de prova em **aparência de prova** — e numa plataforma de prestação de contas isso é pior que não ter
a cadeia. `provenance_complete` é verdadeiro só quando todos os elos existem.

Na cadeia desenhada (`chain`), o passo ausente aparece como ausente (`present: false`), não omitido:
omitir faria a cadeia parecer completa com um passo a menos.

## 4. Correção no Impact Ledger, sem reescrever

`ledger_entries` é append-only e encadeada por hash, e **não havia caminho para corrigir**: só
restava o `UPDATE` que a tabela recusa, ou deixar o erro.

O tipo `correction` aponta o lançamento que corrige (`reverses_id`) e o gatilho
`ledger_correction_is_well_formed` exige:

| Regra | Por quê |
|---|---|
| aponta um lançamento | correção sem alvo é lançamento novo com outro nome |
| mesmo projeto | correção entre projetos moveria valor sem rastro |
| valor **oposto exato** | correção parcial é ajuste disfarçado, e o total deixa de ser somável |
| motivo em `payload.reason` | sem motivo, a correção é indistinguível de erro novo |
| uma correção por lançamento | índice único em `reverses_id` |
| correção de correção recusada | corrija o lançamento original |

O passado continua lá e o total passa a estar certo. Prova:
`test_the_correction_keeps_the_hash_chain_intact_and_the_sum_right`.

## 5. Cadeia de hash no Value Ledger

`value_events` sustenta o número principal do posicionamento do produto e era **a única das três
tabelas de trilha sem encadeamento**: um administrador de banco reescrevia uma linha e nada acusava.

Agora tem `seq`, `prev_hash`, `entry_hash`, `chain_value_event()` e `value_verify(org_id)`, no mesmo
molde de `audit_events` e `ledger_entries`.

**Linhas anteriores ficam sem cadeia (`seq IS NULL`), de propósito, e isso é relatado.** Calcular
hash para trás produziria uma cadeia que *parece* verificada sem nunca ter protegido nada.
`integrity.chains()` devolve `rows_without_chain` com a nota explicando.

## 6. Motor de integridade relacional

### O que havia antes

`scripts/db_integrity_report.py` publicava, como resultado da verificação de órfãos:

```python
"orphan_rows_check": """SELECT 'nenhuma verificação de órfão aplicável:
                        toda referência é FK declarada'""",
```

Uma **string literal**. Não consultava nada, e a afirmação é falsa: há **25 colunas de referência
polimórfica** no banco — `audit_events.object_id`, `ledger_entries.ref_id`,
`value_events.subject_id`, `approval_requests.object_id`, `accounting_entries.source_id` e outras
20 — e nenhuma pode ter chave estrangeira, porque aponta para tabelas diferentes conforme o tipo.
Eram exatamente as referências que precisavam de verificação e as únicas que não tinham.

### Como funciona (migração 0054)

Não há enumeração manual de tipo → tabela. Há três peças:

1. **`polymorphic_refs`** — o catálogo das triplas (tabela, coluna de tipo, coluna de id). São 26.
2. **Convenção de resolução** — `project` → `projects`, `indicator_value` → `indicator_values`,
   conferida contra o catálogo do PostgreSQL. Tipo que não resolve entra como NÃO RESOLVIDO em vez
   de ser pulado.
3. **`polymorphic_ref_exceptions`** — valores de tipo que não são referência a entidade, cada um
   com motivo escrito (`kill_switch`, onde `object_id` guarda o nome do escopo; `manual`, lançamento
   contábil digitado por pessoa; `period`, competência contábil).

### Três relatórios, três perguntas

| Função | Pergunta |
|---|---|
| `integrity_orphans()` | há linha apontando para nada? |
| `integrity_unresolved_refs()` | há valor de tipo que o motor não sabe resolver? |
| `integrity_catalog_drift()` | há coluna polimórfica fora do catálogo, ou catalogada e já inexistente? |

**O terceiro é o que mantém os dois primeiros honestos.** Verificador que não percebe quando o
esquema muda devolve "nada a declarar" para sempre. Ele já provou o próprio valor: acusou
`ai_credit_ledger.ref_id` no instante em que a coluna nasceu, na mesma rodada.

### O relatório

`GET /v1/admin/integrity` devolve **VERDE · AMARELO · VERMELHO**:

* **VERMELHO** — há órfão, cadeia quebrada, ou medição validada sem evidência. Dado quebrado.
* **AMARELO** — catálogo possivelmente atrás do esquema. Não é dado quebrado.
* **VERDE** — nada dos dois.

Relatório que fica verde com ressalva não serve para decidir nada.

## 7. Máquina de estados da candidatura (migração 0055)

A máquina existe desde a v0.13.0 em `services/workflow.py` (`PLATFORM` / `EXTERNAL`) e é conferida
em `transition()`. Isso protege **uma** rota. Um `UPDATE applications SET status = 'closed'` vindo
de outra rota, de um script de operação, ou de uma rota futura escrita sem lembrar da regra passava
direto — e `rascunho → encerrada` é exatamente o estado impossível que o prompt nomeia.

Agora o grafo vale no banco: `application_status_graph` + `trg_application_status_graph`. O erro diz
quais transições são permitidas (erro que só nega não ajuda quem está no fluxo), e candidatura
**não nasce aprovada** — nascer aprovada pularia o processo inteiro sem deixar uma transição.

### A duplicação é consciente

O grafo está em dois lugares (Python e banco) porque migração não importa Python. O que torna isso
aceitável é `TheGraphInTheDatabaseIsTheGraphInTheCodeTests`, que compara **aresta por aresta** e
reprova se divergirem em uma. A única diferença permitida — `approved → committed`, executada pela
rota de registro de aporte e não pela rota genérica — está declarada, com motivo no banco e teto de
uma entrada.

## 8. Relação com o resto da plataforma

```
ORGANIZAÇÃO ─ RLS por inquilino em 312 de 313 tabelas, 653 políticas
    │
PROJETO ─ máquina de estados em project_status_graph (58 arestas)
    │
INDICADOR ─ linha de base com FONTE obrigatória (desde v0.18.0)
    │
MEDIÇÃO ─ origem declarada · validada EXIGE evidência · congelada após validação  ← v0.23.0
    │
EVIDÊNCIA ─ revisão por organização diferente da medida
    │
DOCUMENTO ─ sha256 do conteúdo · versão · supersedes_id
    │
IMPACT LEDGER ─ append-only · cadeia de hash por projeto · correção por lançamento novo  ← v0.23.0
    │
VALUE LEDGER ─ append-only · cadeia de hash por organização  ← v0.23.0
    │
AUDITORIA ─ append-only · cadeia de hash · correlation_id · parent_event_id  ← v0.23.0
```

O `correlation_id` é o que atravessa tudo: dado um documento, a cadeia reconstrói
usuário → acesso → alteração → versão → aprovação → evidência → Value Ledger → relatório.

## 9. Testes

`backend/tests/test_v0230_provenance.py` — 35 testes · `test_v0230_state_machine.py` — 14 testes.

O teste que mais importa não é nenhum dos positivos: é
`test_an_orphan_is_actually_detected`, que **cria um órfão de propósito** e exige que o motor o
encontre, com a contraprova `test_a_real_reference_is_not_reported_as_an_orphan` ao lado — um motor
que reportasse tudo como órfão passaria no primeiro e falharia no segundo.

## 10. O que NÃO está implementado

### Grafo de proveniência genérico (qualquer entidade)

**NÃO IMPLEMENTADO.** A cadeia é específica de `indicator_values`, que é onde a regra morde: é o
número que vai para relatório de impacto.

**Motivo:** um motor genérico exigiria declarar, para cada tipo de entidade, qual é a cadeia de
origem dela — e inventar essas cadeias sem o caso de uso produziria um grafo que ninguém consulta.

**Risco:** perguntar "de onde veio este valor de aporte?" ainda exige percorrer a linha do tempo da
entidade em vez de uma consulta só.

**O que seria necessário:** uma declaração por tipo (`documento → upload → validação`,
`aporte → candidatura → aprovação`) e uma rota que a percorresse. A infraestrutura já está pronta:
`correlation_id` e `parent_event_id` fazem a ligação.

### Hash de conteúdo de evidência sem documento

**NÃO IMPLEMENTADO.** Evidência sem documento anexado não tem hash, porque não há arquivo. A lacuna
aparece em `gaps` como `documento`, com o efeito escrito.

### UNIQUE impedindo dois documentos substituírem o mesmo

**NÃO IMPLEMENTADO.** `documents.supersedes_id` não tem índice único, então dois documentos podem
declarar substituir o mesmo antecessor.

**Risco:** a versão "atual" de uma cadeia de substituição fica ambígua. A tela de proveniência
expõe `superseded_by_count`, então a ambiguidade é VISÍVEL em vez de silenciosa.

**O que seria necessário:** `CREATE UNIQUE INDEX ... ON documents (supersedes_id) WHERE
supersedes_id IS NOT NULL AND deleted_at IS NULL` — e antes disso conferir se algum dado existente
já viola, porque a migração recusaria subir (o que é o comportamento correto).
