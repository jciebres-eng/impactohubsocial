# Motor de auditoria e rastreabilidade — v0.23.0

> Este documento descreve o que EXISTE. Onde algo não está implementado, o texto diz
> **NÃO IMPLEMENTADO**, o motivo, o risco e o que seria necessário.

## 0. O ponto de partida, que não é zero

A trilha de auditoria desta plataforma não nasceu nesta versão. Desde a v0.2.0:

| Já existia | Onde |
|---|---|
| `audit_events` append-only (gatilho `forbid_mutation`) | migração 0002 |
| Cadeia de hash por organização, calculada **no banco** | `chain_audit()`, `audit_verify()` |
| Redação de campo sensível antes de gravar | `services/audit.py::_clean()` |
| 319 chamadas de auditoria no código | varredura em `engines/coverage.py` |
| Trilha de entrada privilegiada, incluindo LEITURA | `privileged_access_log` (v0.22.0) |
| Impact Ledger encadeado por projeto | `chain_ledger()`, `ledger_verify()` |

O que faltava eram **campos e relações**, não a tabela. Esta versão os acrescenta.

## 1. Modelo do evento

```
audit_events
├─ id              bigserial            identidade
├─ seq             bigint               posição na cadeia da organização
├─ prev_hash       char(64)             hash do evento anterior
├─ event_hash      char(64)             hash deste evento
├─ chain_version   smallint             1 = fórmula anterior · 2 = com os campos novos
├─ org_id          uuid                 inquilino (nulo = evento da plataforma)
├─ actor_user_id   uuid                 QUEM
├─ actor_type      text                 O QUE o quem era            ← v0.23.0
├─ action          text                 `dominio.verbo`
├─ object_type     text                 recurso
├─ object_id       text                 identificador do recurso
├─ resource_name   text                 nome legível                ← v0.23.0
├─ status          text                 success · denied · failed   ← v0.23.0
├─ severity        text                 info · notice · warning · critical  ← v0.23.0
├─ source          text                 api · job · cli · webhook · migration · test  ← v0.23.0
├─ ip              inet                 origem
├─ user_agent      text                 agente                      ← v0.23.0
├─ session_id      uuid                 sessão                      ← v0.23.0
├─ request_id      text                 requisição
├─ correlation_id  text                 RASTRO (várias requisições) ← v0.23.0
├─ parent_event_id bigint               causa                       ← v0.23.0
├─ payload         jsonb                contexto (redigido)
├─ before_state    jsonb                de QUE                      ← v0.23.0
├─ after_state     jsonb                para QUE                    ← v0.23.0
└─ at              timestamptz          quando (truncado em microssegundos)
```

### `actor_type`

`user` · `admin` · `system` · `ai` · `automation` · `integration`.

Numa investigação, é a primeira pergunta depois de "quem". A trilha dizia QUEM e nunca O QUE o
quem era — e "a IA classificou" é um fato diferente de "uma pessoa classificou".

Derivado em `Ctx.audit()`, não pedido a cada chamador. Pedir a 319 chamadores garantiria que algum
esquecesse, e evento sem tipo de ator vale menos que nenhum porque engana. O padrão em `record()`
deriva da presença de ator: havendo ator é pessoa, não havendo é sistema. A primeira versão tinha
`"system"` fixo e marcava como SISTEMA o registro de conta que uma pessoa acabara de fazer.

### `status` e `severity`

`status` inclui `denied` e `failed` **de propósito**: trilha que só registra sucesso descreve um
sistema em que nada é recusado, e a tentativa recusada é o sinal que uma investigação procura.

`severity` é DERIVADA em um lugar só (`services/audit.py::severity_of`), da ação e do resultado.
Pedir gravidade a cada chamador produziria 319 critérios, e o mais provável é que quase tudo
ficasse em `info`, porque é o que se escreve sem pensar.

### `correlation_id` e `parent_event_id`

`request_id` identifica uma REQUISIÇÃO. Uma operação do produto costuma ser várias: enviar
documento, classificar, aprovar, gerar recibo. O cliente que quiser amarrá-las manda
`x-correlation-id`; quem não manda recebe o próprio `request_id` — e aí rastro e requisição
coincidem, que é o caso simples e não um caso perdido.

O cabeçalho é ENTRADA DO CLIENTE: é limpo (só alfanumérico, hífen e sublinhado) e cortado em 64
caracteres. Guardar o que vier nele é guardar o que o cliente quiser.

`parent_event_id` é a CAUSA. Sem ele, um rastro é uma lista ordenada por tempo e não diz o que
levou a quê. O gatilho `aa_trg_audit_parent` recusa pai de outra organização (a árvore de causa não
cruza inquilino) e pai de outra correlação.

### `before_state` / `after_state`

A trilha registrava que algo mudou, não de QUE para QUE. Os dois campos passam pela MESMA redação
recursiva do `payload` — é a mesma tabela imutável, e o que entra não sai.

Eles são preenchidos pelo CHAMADOR, não por ponto central: só quem leu a linha antes de mudá-la
sabe o estado anterior.

## 2. A cadeia de hash e a mudança de esquema

Acrescentar coluna ao material do hash invalidaria o hash de **toda** linha existente, e a
verificação passaria a acusar manipulação onde não houve — pior que não verificar.

O material é **versionado**:

```sql
CREATE FUNCTION audit_material(e audit_events) RETURNS text AS $$
  SELECT CASE WHEN e.chain_version <= 1 THEN
    -- literalmente a fórmula anterior; nenhum hash antigo muda
    concat_ws('|', e.prev_hash, e.seq::text, ..., ts_canonical(e.at))
  ELSE
    -- a mesma, mais os campos novos
    concat_ws('|', ..., e.actor_type, e.severity, e.status, e.source,
              e.session_id, e.user_agent, e.correlation_id, e.parent_event_id,
              e.resource_name, e.before_state, e.after_state)
  END
$$;
```

Linha nova nasce na versão 2 por gatilho (`ab_trg_audit_chain_version`). Calcular o material novo
sobre linhas antigas seria reescrever a história para que ela feche.

**Provas:** `test_an_old_row_and_a_new_row_verify_together` (cadeia mista fecha),
`test_the_version_one_formula_was_not_touched` (a fórmula antiga é imutável),
`test_the_before_and_after_are_protected_by_the_hash_chain` (alterar `after_state` com o gatilho
desligado quebra a verificação).

## 3. Categoria do evento

`audit_action_categories` mapeia 113 prefixos em catorze categorias: as nove do prompt
(AUTH, USERS, ORGS, DOCUMENTS, PROJECTS, WORKFLOWS, FINANCE, AI, SECURITY) mais CONTENT, NETWORK,
ADMIN, INTEGRATIONS e OPS.

**Por que catorze e não nove.** A primeira versão derivava a categoria de um `CASE` no código e
cobria as nove. O teste mostrou que a base tem 86 prefixos de ação e **68 caíam em OTHER** — filtro
que joga 79% dos eventos em "outros" não é filtro. Forçar tudo nas nove colocaria "central de
conhecimento" em DOCUMENTS e "integração de origem externa" em WORKFLOWS, e o filtro devolveria
coisas que quem investiga não pediu.

`test_every_action_prefix_in_the_codebase_has_a_category` reprova se um domínio novo aparecer sem
categoria, e há contraprova de que uma tabela toda em OTHER não passaria.

## 4. Consultas

| Rota | Pergunta que responde |
|---|---|
| `GET /v1/admin/audit` | Treze filtros: pessoa, tipo de ator, recurso, rastro, gravidade, resultado, origem, categoria, período |
| `GET /v1/admin/audit/timeline` | "Tudo o que aconteceu com ESTE documento" |
| `GET /v1/admin/audit/trail` | "Que acontecimento levou a qual" — árvore com `depth` |
| `GET /v1/admin/audit/verify` | A cadeia fecha? |
| `POST /v1/admin/audit/export` | Exportação — **que se registra na própria trilha** |
| `GET /v1/me/security` | O que a PESSOA vê sobre a própria conta |

Antes desta versão havia dois filtros (organização e prefixo de ação). Quem investiga pergunta
outras coisas, e nenhuma tinha filtro — a resposta era paginar milhares de linhas.

`ix_audit_object (object_type, object_id, id DESC)` existe para a linha do tempo, que antes fazia
varredura sequencial na tabela que mais cresce no banco. Mais: `ix_audit_correlation`,
`ix_audit_actor`, `ix_audit_severity` (parcial) e `ix_audit_not_success` (parcial).

### A exportação se audita

Levar a trilha para fora é a operação que mais interessa a quem pretende apagar rastro depois, e era
a única leitura privilegiada sem registro NA PRÓPRIA TRILHA. Agora grava `audit.log_exported` com o
número de linhas e os filtros usados, exige `security.audit.export` (permissão separada de leitura,
com reautenticação) e devolve o id do evento para quem recebe o arquivo conferir a origem.

### A árvore é conferida, não prometida

A primeira versão da rota devolvia um campo `unlinked` com "eventos do rastro fora da árvore". Ele é
vazio **por construção** — `audit_trail_of()` traz como raiz todo evento sem pai, e o banco recusa
pai de outra correlação. Campo que não pode ter conteúdo sugere que informa sem informar.

Foi trocado por conferência de COMPLETUDE: `events_in_trail`, `events_in_tree` e `complete`. Se a
árvore tem menos eventos que o rastro, uma das duas garantias caiu, e aí ela mente por omissão.

## 5. O que NÃO pode acontecer com a trilha

| Tentativa | O que recusa | Teste |
|---|---|---|
| `UPDATE` | gatilho `forbid_mutation` | `test_an_organization_cannot_delete_or_rewrite_its_own_trail` |
| `DELETE` | o mesmo gatilho | idem |
| `TRUNCATE` | gatilho `forbid_truncate` **← v0.23.0** | `test_even_the_database_owner_cannot_truncate_the_trail_without_disabling_a_trigger` |
| Forjar evento | RLS de INSERT (`actor_user_id` tem de ser quem chama) | `test_an_organization_cannot_forge_an_event_in_its_own_trail` |
| Ler trilha de outra organização | RLS de SELECT | `test_an_organization_session_cannot_read_the_table_through_rls` |
| Alterar linha como dono do banco | a cadeia de hash acusa | `test_tampering_with_a_row_breaks_the_chain_and_the_check_finds_it` |

**TRUNCATE era o buraco.** `forbid_mutation` é gatilho DE LINHA: protege UPDATE e DELETE e não vê
TRUNCATE, que não dispara gatilho de linha nenhum. Quem tivesse privilégio de dono apagava a trilha
inteira numa instrução **sem quebrar hash algum, porque não sobrava hash para quebrar**. Agora há
gatilho `BEFORE TRUNCATE` em `audit_events`, `ledger_entries`, `value_events`,
`kill_switch_events`, `privileged_access_log` e `ai_credit_ledger`.

## 6. Redação recursiva

`_clean()` só olhava o primeiro nível: um segredo em `{"webhook": {"secret": "..."}}` era gravado em
claro numa tabela append-only. Agora:

* recursiva, com teto de profundidade 6 (mais fundo que isso é dado, não contexto);
* pega variantes por FRAGMENTO de nome: `refresh_token`, `access_token`, `client_secret`,
  `api_key`, `private_key`, `credential`, `authorization`, `cookie`, `session_token`, `senha`;
* atravessa listas de objetos;
* vale para `payload`, `before_state` e `after_state`.

O teste que importa lê a linha de volta do banco e exige que o segredo não esteja lá.

## 7. Alerta, não só registro

**O defeito que a auditoria desta versão nomeou:** a plataforma DETECTAVA reuso de refresh token —
o sinal mais forte de roubo de sessão que ela sabe produzir —, revogava a família de sessões,
auditava e notificava o TITULAR. **Ninguém da operação era alertado.**

Duas séries, emitidas em dois pontos de estrangulamento:

```
impacto_security_events_total{action}   ← services/audit.py::record() + core/access.py
impacto_audit_events_total{categoria}   ← services/audit.py::record()
```

Emitir no ponto de passagem — e não em cada chamador — é o que garante que nenhum evento de
segurança novo nasça invisível para o alerta.

São 16 regras em `infra/monitoring/alerts.yml`, com catraca provando que toda série citada existe,
que todo rótulo `action` é ação declarada e que todo nome em `SECURITY_ACTIONS` tem produtor no
código (nome morto é o defeito de `LOGIN_MAX_ATTEMPTS`: configuração que parece ligada e não tem
leitor).

## 8. Desempenho

| Medida | Estado |
|---|---|
| Índices | 7, três deles parciais (gravidade, resultado, objeto) |
| Paginação | `page()` em todas as rotas de listagem, com `limit` e `offset` |
| Exportação | teto de 10 000 linhas, declarado na resposta (`limit_applied`) |
| Linha do tempo | teto configurável, com `truncated` e aviso de que nada se perdeu |
| Escrita | síncrona, na mesma transação do fato |
| Retenção | classificada por coluna em `config/data_retention.json`, conferida por teste |
| Particionamento | **NÃO IMPLEMENTADO** |

### NÃO IMPLEMENTADO: particionamento de `audit_events`

**Motivo:** a tabela não tem volume que justifique. Particionar por mês acrescenta complexidade de
manutenção (criar partição futura, destino do `DEFAULT`) e **quebra a cadeia de hash** se a
verificação não for reescrita para percorrer partições em ordem de `seq`.

**Risco de não fazer:** a partir de alguma dezena de milhões de linhas, a varredura dos relatórios
agregados fica lenta. As consultas por entidade, por ator e por rastro continuam rápidas, porque
têm índice.

**O que seria necessário:** definir a chave de particionamento (`at` por mês), reescrever
`audit_verify()` para percorrer partições, criar a rotina de criação antecipada de partição e
provar a verificação atravessando o limite de duas partições.

### NÃO IMPLEMENTADO: escrita assíncrona

**Motivo deliberado.** A escrita é síncrona, na mesma transação do fato. Se a transação é desfeita,
o evento também — e é isso que se quer: auditoria de operação que não aconteceu é ruído. Fila
tornaria a trilha *eventualmente* consistente com o fato, e numa trilha de auditoria "eventualmente"
é a palavra errada.

**Custo:** cada operação paga uma inserção. Medido em `test_v0150_performance`.

## 9. LGPD

* A trilha é classificada em `config/data_retention.json`: `audit_events.org_id` é `audit_only`,
  `audit_events.actor_user_id` é `audit_only`. Conferido por `retention.audit()` contra a ação real
  da chave estrangeira — política que promete cascata onde a remoção é impossível foi o defeito que
  a v0.19.0 encontrou.
* O apagamento a pedido do titular ANONIMIZA o vínculo e preserva o evento. O evento é fato sobre a
  organização; o vínculo com a pessoa é o que sai.
* `GET /v1/me/security` dá ao titular acesso aos eventos DELE, incluindo as mudanças do próprio
  acesso feitas por administradores — o titular tem direito de saber quando o acesso dele muda, e o
  que se mostra é o fato, nunca quem o fez.
* Nenhum segredo entra na trilha: redação recursiva, com teste que lê a linha de volta do banco.

## 10. Testes

`backend/tests/test_v0230_audit_engine.py` — 37 testes:

| Classe | O que fecha |
|---|---|
| `TheStandardFieldsExistAndAreFilledWithoutTouchingCallersTests` | os campos novos chegam sem alterar os 319 chamadores |
| `BeforeAndAfterSayFromWhatToWhatTests` | antes/depois existe, é redigido e está dentro do hash |
| `TheChainStaysValidAcrossTheSchemaChangeTests` | cadeia mista fecha; a fórmula antiga é imutável |
| `TheCausalTreeAnswersWhatLedToWhatTests` | árvore com profundidade; pai de outra organização ou rastro é recusado |
| `TheAuditApiIsHardAgainstTheUsualAttacksTests` | IDOR, BOLA, escalada, cruzamento de inquilino, forja, apagamento, TRUNCATE, injeção em filtro |
| `ExportingTheTrailIsItselfAuditedTests` | a exportação deixa a própria linha |
| `ConcurrentWritersDoNotBreakTheChainTests` | 6 escritores, 60 eventos, cadeia válida, zero buraco de sequência |

## 11. Lista de conferência

| # | Item | Estado |
|---|---|---|
| 1 | Modelo padrão de evento com todos os campos | ✅ |
| 2 | Categorias de evento | ✅ 113 prefixos, 14 categorias |
| 3 | Antes/depois | ✅ |
| 4 | Sem senha, token, cookie ou segredo | ✅ redação recursiva, provada contra o banco |
| 5 | Redação | ✅ |
| 6 | Linha do tempo por entidade | ✅ rota + índice |
| 7 | Correlação (`correlation_id`, `request_id`, `parent_event_id`) | ✅ |
| 8 | `actor_type` com os seis valores | ✅ |
| 9 | Append-only | ✅ UPDATE, DELETE e TRUNCATE |
| 10 | Encadeamento de hash | ✅ versionado, com cadeia mista provada |
| 11 | Área `/audit` com filtros | ✅ 13 filtros, valores fechados no esquema |
| 12 | Exportação gerando `AUDIT_LOG_EXPORTED` | ✅ `audit.log_exported` |
| 13 | Nunca confiar no frontend para evento crítico | ✅ `actor_user_id` vem da sessão; RLS recusa divergência |
| 14 | Índices | ✅ 7 |
| 15 | Particionamento | ❌ **NÃO IMPLEMENTADO** (§8) |
| 16 | Retenção | ✅ classificada e conferida |
| 17 | Escrita assíncrona | ❌ **recusada por desenho** (§8) |
| 18 | Paginação | ✅ |
| 19 | LGPD | ✅ §9 |
| 20 | Alerta separado do evento | ✅ 16 regras, séries em dois pontos de estrangulamento |
| 21 | API segura com paginação | ✅ permissão por rota, entrada privilegiada registrada |
| 22 | Teste de IDOR/BOLA | ✅ |
| 23 | Teste de escalada de privilégio | ✅ |
| 24 | Teste de cruzamento de inquilino | ✅ pela rota E pela RLS |
| 25 | Teste de forja de evento | ✅ |
| 26 | Teste de apagamento da trilha | ✅ incluindo TRUNCATE e dono do banco |
| 27 | Cenário com vários usuários simultâneos | ✅ 6 escritores concorrentes |
| 28 | Simulação de falha | ✅ dump adulterado no CI; cadeia quebrada detectada |

**Teste de carga da trilha: parcial.** O teste de concorrência cobre 60 eventos em 6 escritores, o
que prova a ausência de corrida na cadeia. Não há teste de volume (milhões de linhas) porque ele
mediria o PostgreSQL desta máquina, não a plataforma — e um número medido em máquina de
desenvolvimento publicado como capacidade seria pior que número nenhum.
