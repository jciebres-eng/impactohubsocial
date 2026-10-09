# Auditoria final da camada de IA — v0.23.0

> **O que este documento não faz:** não descreve uma camada de IA que a plataforma não tem. O
> prompt desta rodada pede 170 seções de arquitetura de IA; abaixo está o que existe, o que foi
> acrescentado, e o que **NÃO foi feito** com o motivo de cada recusa.

## 0. A decisão que organiza tudo o resto

A camada de IA desta plataforma é **pequena de propósito**. Dos 42 motores, **3 chamam modelo**:

| Motor | Faixa | Chama modelo? |
|---|---|---|
| `structure_need` | 2 | sim, com esquema de saída |
| `draft_document` | 1 | sim, texto livre |
| `summarize_project` | 1 | sim, texto livre |
| `classify_document` | 2 | **não** — regra local sobre palavra-chave |
| diagnóstico, prontidão, compatibilidade, equidade, reputação, selo, alegação, fiscal, institucional, longitudinal, replicação, e outros 28 | 0 | **não** — regra, cálculo e consulta |

Isso é desenho, não lacuna. Um motor de diagnóstico que *inventa* a nota é pior que um que a
calcula: o número inventado é uma afirmação falsa com aparência de medição, e esta é uma plataforma
de prestação de contas.

**Portanto: o que faltava não era mais IA. Era governança da que existe.**

## 1. O que a auditoria encontrou

| # | Achado | Gravidade |
|---|---|---|
| 1 | O prompt vivia em literal dentro do gateway. Mudar uma frase mudava o resultado de todo cliente, sem registro. Nada ligava uma saída guardada à instrução que a produziu. | 🔴 |
| 2 | `ai_usage.status` aceitava qualquer texto e o código gravava `'ok'` **sempre** — inclusive quando a resposta externa era descartada por inválida. A tabela dizia que o provedor externo funcionou. | 🔴 |
| 3 | Não havia política por risco. A mesma chamada que redige um resumo poderia afirmar sobre terceiro, com o mesmo limite. | 🔴 |
| 4 | Cota contava CHAMADAS. Chamada não é unidade de custo: uma de 200 caracteres e uma de 200 mil consomem o mesmo da cota. | 🟠 |
| 5 | Custo era registrado e **não limitava nada**. | 🟠 |
| 6 | CRÉDITO e TOKEN eram a mesma coisa. Amarrar os dois obriga a reprecificar o produto a cada mudança de tabela do provedor. | 🟠 |
| 7 | `POST /v1/ai/classify-document/{id}` era a única rota de IA **sem limite de taxa**. | 🟠 |
| 8 | CPF era redigido antes do envio externo; **CNPJ não** — e CNPJ aparece em todo documento desta plataforma. | 🟠 |
| 9 | `GET /v1/ai/usage` devolvia três números que **nenhuma tela consumia**. | 🟡 |
| 10 | Não havia estimativa de custo antes de operação paga. | 🟡 |
| 11 | Não havia conjunto de referência nem avaliação de regressão. | 🟡 |

## 2. O que foi implementado

### Registro de prompt com versão

`ai_prompts`: chave, versão, faixa, texto do sistema, esquema de saída, nota obrigatória. Uma versão
ativa por chave (índice único parcial); texto congelado por gatilho; `ai_usage.prompt_key` e
`prompt_version` registram qual rodou.

Os cinco prompts foram publicados com o texto **exato** que estava no código. Nada foi reescrito na
mudança de lugar — se o texto mudasse junto, uma diferença de resultado não poderia ser atribuída
entre "arquitetura nova" e "instrução nova".

**O texto não chega a rota de cliente.** A RLS de `ai_prompts` é privilegiada; a visão
`ai_prompt_public` expõe metadados sem a coluna do texto; `ai_active_prompt()` é SECURITY DEFINER
com escopo de uma chave, porque o **processo** precisa do texto e a **sessão** não. Esta função
nasceu de um defeito que o teste encontrou: o gateway lê o prompt dentro da transação da
organização (é lá que cota, orçamento e registro de uso acontecem), e na primeira versão **toda rota
de IA devolvia 500**.

### Política por faixa de risco

| Faixa | Uso | Entrada | Saída | Sai da instalação? | Esquema | Revisão humana |
|---|---|---|---|---|---|---|
| 0 | Determinístico (sem modelo) | 100 000 | 1 | não | não | não |
| 1 | Apoio à redação | 20 000 | 2 000 | **sim** | não | **sim** |
| 2 | Classificação com esquema | 20 000 | 800 | **sim** | **sim** | **sim** |
| 3 | Decisão sobre TERCEIRO | 8 000 | 800 | **não** | **sim** | **sim** |
| 4 | Efeito jurídico ou financeiro | 1 | 1 | não | sim | sim |

A faixa é do **uso**, não do modelo: classificar por modelo amarraria a política ao catálogo do
provedor e envelheceria a cada lançamento.

A faixa 0 está na tabela para que o inventário MOSTRE que a maioria do produto é determinística, em
vez de deixar isso implícito.

A faixa 4 existe para **dizer** que nenhum uso com efeito jurídico ou financeiro está implementado,
e os limites de 1 a tornam inoperante por construção: se alguém declarar um uso nela, ele falha na
primeira chamada em vez de funcionar sem a decisão humana que a faixa exige. Prova:
`test_no_prompt_is_declared_in_tier_four`.

### `status` que diz a verdade

Nove valores com CHECK: `ok` · `local_only` · `fallback_local` · `invalid_output` ·
`blocked_policy` · `quota_exceeded` · `budget_exceeded` · `provider_error` · `rejected`.

`test_every_status_value_in_the_constraint_is_reachable_or_declared` exige que todo valor tenha
produtor no código **ou** motivo escrito de por que ainda não tem. Valor de estado que nenhum
caminho produz é valor que engana quem lê a tabela.

### Conferência de esquema da saída

Validador pequeno e **deliberadamente** pequeno: tipo, obrigatoriedade, tamanho, conjunto de
valores. Devolve LISTA de problemas, não booleano — `status='invalid_output'` sem dizer o que estava
errado deixa quem opera sem ação possível.

`test_the_validator_covers_every_construct_the_schemas_use` reprova se um esquema usar construção
que o validador não entende, em vez de deixá-la passar sem conferência. **Esquema não conferido é
pior que esquema ausente, porque promete.**

### Crédito ≠ token

`ai_credit_ledger` append-only; saldo é a SOMA dos lançamentos (nunca coluna que alguém atualiza —
lição do Value Ledger); sinal travado por restrição (consumo positivo criaria crédito);
`ai_credit_consume()` com bloqueio consultivo por organização e idempotência.

**O defeito que o bloqueio evita:** ler o saldo, decidir e gravar em três passos deixa a janela em
que duas chamadas simultâneas leem o mesmo saldo e as duas passam. Prova:
`test_concurrent_consumption_never_spends_more_than_the_balance` — dez consumos de 10 contra saldo
de 50 deixam passar exatamente cinco, e o saldo fecha em zero sem ficar negativo.

### Orçamento em dinheiro

`ai_budgets` por organização e competência, com `warn_at_pct` e `hard_stop`. Padrão é **avisar**:
parar o trabalho sem a organização pedir seria a plataforma escolhendo por ela.

`ai_budget_state()` declara a ressalva que importa: chamada sem preço vigente **não entra** no gasto
apurado, e `unpriced_calls` diz quantas são. Sem isso o orçamento diria "zero gasto" sobre uso real.

### Preço como configuração

`ai_price_table` tem provedor, modelo, preço por milhão de tokens de entrada e saída, moeda,
**fonte, URL e data da fonte**, e vigência. Ela nasce **VAZIA**: nenhum preço de provedor foi
inventado neste pacote. Sem linha vigente, a chamada fica com `cost_status = 'no_price_table'` e
custo **nulo** — nunca zero, porque zero pareceria custo apurado.

### Defesa contra injeção de prompt

`wrap_user_content()` separa instrução de conteúdo com delimitador, remove o delimitador de dentro
do próprio texto (sem isso bastaria escrevê-lo para sair do bloco e continuar como instrução) e o
texto do sistema diz ao modelo que o bloco é DADO.

Isso **reduz** a superfície. Não a elimina, e o código não finge que elimina. A proteção que de fato
vale é arquitetural, e está escrita na resposta de `GET /v1/ai/policies`:

* nenhuma saída de IA vira estado do sistema sozinha — toda faixa exige revisão humana;
* a IA **não tem ferramenta** para chamar nem acesso de escrita ao banco;
* a faixa 3 não sai da instalação;
* nenhum dado desta plataforma é usado para treinar modelo.

### Redação de dado pessoal

CPF · **CNPJ** · e-mail · telefone · CEP · RG · **número longo** (cartão, chave PIX). A contagem de
redações entra em `ai_usage.redactions`, que é o que permite notar que um campo novo passou a vazar.

### Avaliação

`backend/tests/golden/ai_golden.json` — 10 casos sobre os motores **determinísticos**, que são os
que rodam por padrão nesta instalação.

Fixa **invariantes**, não saída exata: fixar texto palavra por palavra transformaria qualquer
melhoria de redação em reprovação, e aí alguém atualiza o arquivo sem ler. A invariante central é a
mais barata de conferir e a mais caruaro de violar: **número na saída que não estava na entrada** —
alucinação na forma que mais importa aqui.

Cada invariante tem **contraprova** que a faz reprovar. `test_the_hallucination_check_would_catch_a_real_one`
existe porque, sem ele, uma mudança em `_digitos` que devolvesse sempre conjunto vazio deixaria a
avaliação verde sem conferir nada.

Uma correção que o próprio conjunto provocou: a primeira versão reprovava por causa de `ods: [4,16]`
— códigos de catálogo derivados por regra de palavra-chave, não afirmação numérica sobre o projeto.
A invariante passou a valer sobre os campos de TEXTO LIVRE, porque pedir ao motor que não
classificasse seria pedir que ele não funcionasse.

### Telas

`/ia` (organização): três controles como três, resultados reais por `status`, versões de prompt
usadas, definição de orçamento, faixas de risco e garantias.
`/v1/admin/ai` (operação): catálogo de prompt, faixas, resultados, custo, tabela de preço,
orçamentos, crédito — e a lista do que **não está implementado**, com motivo.

## 3. O que NÃO foi implementado, e por quê

### Embeddings e busca semântica (RAG por similaridade)

**NÃO IMPLEMENTADO.**
**Motivo:** exigiria provedor de embedding contratado e `pgvector`. A recuperação hoje é por
consulta relacional com a RLS da organização: mais lenta e **não vaza entre inquilinos**.
**Risco:** a recuperação não encontra documento por semelhança de sentido, só por termo e relação.
**O que seria necessário:** provedor contratado, `pgvector`, decisão sobre onde o vetor é calculado
(enviar o documento para gerar embedding é tratamento de dado que a organização precisa autorizar) e
isolamento por inquilino no índice vetorial.

### Cache semântico de resposta

**NÃO IMPLEMENTADO.**
**Motivo:** depende de embeddings. E há uma razão independente: servir resposta guardada de outro
pedido exige decidir quando duas perguntas são a mesma — **errar isso é entregar o dado de um
projeto na resposta de outro**.
**Risco:** chamadas repetidas custam de novo.
**O que seria necessário:** embeddings, limiar de similaridade, e escopo de cache por organização
com prova de isolamento.

### Fallback entre provedores externos

**NÃO IMPLEMENTADO.**
**Motivo:** exige política de privacidade e base legal **por provedor**. Mandar o dado para um
segundo provedor porque o primeiro caiu é tratamento que a organização não autorizou.
**Risco:** queda do provedor único derruba a assistência externa. Mitigação implementada: o
fallback é para o **motor local**, que produz resultado degradado mas real, com
`status = 'fallback_local'` registrado.

### Processamento em lote

**NÃO IMPLEMENTADO.**
**Motivo:** exige volume e preço de lote reais para valer a pena. Nenhum dos dois existe nesta
instalação.
**Risco:** nenhum hoje.

### Uso de ferramenta (tool calling) e agentes

**NÃO IMPLEMENTADO, e recusado por desenho.**
**Motivo:** dar ferramenta à IA é dar a ela a capacidade de MUDAR estado. A garantia central desta
camada é que nenhuma saída de IA vira estado do sistema sozinha, e ferramenta a derruba.
**O que seria necessário:** uma decisão de produto diferente, não uma implementação.

### Memória de agente e IA longitudinal

**NÃO IMPLEMENTADO.** Decorre do item acima.

### Fila assíncrona com prioridade

**NÃO IMPLEMENTADO.**
**Motivo:** as três operações que chamam modelo respondem em segundos e são síncronas. Fila
acrescentaria estado intermediário ("processando") que a interface precisaria exibir e o usuário
acompanhar, para ganhar nada no volume atual.
**Risco:** operação longa (documento muito grande) ocupa um trabalhador. Mitigado pelo limite de
entrada da faixa e pelo tempo limite do cliente HTTP.

### Painel de margem e economia unitária por chamada de IA

**PARCIAL.** O custo por chamada existe (`ai_usage.cost_cents_estimate`, derivado da tabela de
preço) e entra na apuração de despesa da plataforma (`economics/metrics.py`). **Margem por evento de
valor não é calculada** enquanto a tabela de preço estiver vazia — e ela está, porque nenhum preço
foi inventado.

## 4. Lista de conferência

| Item do prompt | Estado |
|---|---|
| Gateway de IA com abstração de provedor | ✅ `anthropic`, `openai_compatible`, `local`, `disabled` |
| `generate` | ✅ |
| `embed` | ❌ NÃO IMPLEMENTADO (§3) |
| `classify` | ✅ determinístico + faixa 2 com esquema |
| `stream` | ❌ NÃO IMPLEMENTADO — resposta curta, sem ganho |
| `estimateCost` | ✅ `GET /v1/ai/estimate` |
| `countTokens` | ⚠️ aproximação de 4 caracteres por token, **declarada como aproximação** |
| `healthCheck` | ✅ via `/v1/admin/ai` (`external_configured`) |
| Roteador de modelo + política por faixa | ✅ 5 faixas |
| Roteamento por risco | ✅ a faixa decide saída externa, esquema e revisão |
| RAG com recuperação por permissão | ⚠️ relacional com RLS; sem similaridade (§3) |
| Cache de várias camadas | ❌ NÃO IMPLEMENTADO (§3) |
| Registro de prompt com versão | ✅ |
| Saída estruturada por JSON Schema | ✅ validador próprio, com teste de cobertura de construção |
| Copiloto por perfil | ❌ NÃO IMPLEMENTADO — seria chat, e a decisão é não ter chat |
| Motor híbrido de compatibilidade | ✅ determinístico (faixa 0) |
| Motor de diagnóstico | ✅ determinístico (faixa 0) |
| Inteligência de documento | ✅ classificação + extração de CNPJ e validade, determinística |
| Assistência de conformidade com linguagem "POTENCIAL CONFORMIDADE" | ✅ anterior a esta versão |
| Razão de uso de IA | ✅ `ai_usage` com 7 campos novos |
| Motor de custo | ✅ derivado de tabela de preço com fonte e data |
| Motor de crédito (CRÉDITO ≠ TOKEN) | ✅ razão append-only, consumo atômico, idempotente |
| Cotas | ✅ por plano |
| Orçamento | ✅ em dinheiro, com avisar/parar |
| Limite rígido e brando | ✅ `hard_stop` |
| Chaves de funcionalidade | ✅ anterior (`feature_flags`) |
| Fila assíncrona com prioridade | ❌ NÃO IMPLEMENTADO (§3) |
| Lote | ❌ NÃO IMPLEMENTADO (§3) |
| Novas tentativas | ✅ `HttpClient(retries=2)` |
| Fallback | ✅ para o motor LOCAL |
| Tempo limite | ✅ configurável |
| Limite de taxa | ✅ nas quatro rotas de IA |
| Controle de margem | ⚠️ depende de preço cadastrado |
| Painel de lucratividade | ⚠️ idem |
| Guarda de custo | ✅ orçamento com parada rígida |
| Orçamento de token e contexto | ✅ limite por faixa |
| Cache de prompt | ❌ NÃO IMPLEMENTADO |
| Classificação de dado | ✅ a faixa É a classificação |
| Redação de dado pessoal | ✅ 7 padrões, CNPJ incluído nesta versão |
| LGPD | ✅ nada treina modelo; redação antes do envio |
| Defesa contra injeção de prompt | ✅ delimitação + garantia arquitetural declarada |
| Defesa contra exfiltração | ✅ faixa 3 não sai; redação; sem ferramenta |
| Governança de chamada de ferramenta | ✅ **não há ferramenta** — é a governança mais forte possível |
| Agentes com escopo limitado | ❌ NÃO IMPLEMENTADO, recusado (§3) |
| Memória de agente | ❌ idem |
| IA longitudinal | ❌ idem |
| Recomendação com validade | ✅ anterior (`recommendations`) |
| Confiança da IA | ✅ `confidence` na classificação, com zero obrigatório sem sinal |
| Humano no circuito | ✅ obrigatório em todas as faixas |
| Grafo de evidência de IA | ✅ via `correlation_id` na trilha |
| Registro de auditoria de IA | ✅ `ai_usage` + `audit_events` |
| Avaliação com conjunto de referência | ✅ 10 casos, invariantes, contraprovas |
| Teste de alucinação | ✅ número na saída que não está na entrada |
| Teste de contradição | ✅ resumo não acrescenta número; classificação não inventa validade |
| Atualidade | ⚠️ não aplicável: os motores não consultam fonte externa |
| Regressão de avaliação | ✅ roda na suíte |
| Portão de liberação de IA | ✅ a suíte de avaliação é bloqueante no CI |
| Central de controle de IA | ✅ `/v1/admin/ai` |
| Saúde do modelo | ⚠️ parcial: `external_configured` e distribuição de `status` |
| Fallback de provedor | ❌ NÃO IMPLEMENTADO (§3) |
| Previsão de custo | ❌ NÃO IMPLEMENTADO — exigiria série histórica que não existe |
| Economia unitária | ⚠️ depende de preço cadastrado |
| `ProviderPricing` configurável, não congelado | ✅ tabela com fonte, data e vigência |
| Recibos de IA integrados à arquitetura financeira | ✅ `app_price_ai_usage()` + Value Ledger |
| Análise de uso de IA | ✅ `/v1/ai/usage` e `/v1/admin/ai` |
| Retorno de qualidade | ❌ NÃO IMPLEMENTADO |
| Sem treino automático em dado de cliente | ✅ declarado e verdadeiro: não há caminho de treino |
| Observabilidade e traços | ✅ `impacto_ai_requests_total`, `trace_id`, latência por chamada |
| Equipe vermelha | ✅ injeção de prompt, delimitador do atacante, esquema forjado |
| Testes de concorrência (sem consumo duplo de crédito) | ✅ dez simultâneos contra saldo de cinco |
| Testes de cache | ❌ não aplicável (não há cache) |
| Testes de roteamento | ✅ faixa recusa entrada grande e saída externa proibida |
| Testes de fallback | ✅ `fallback_local` registrado |
| Testes de privacidade | ✅ CNPJ, CPF, cartão, contagem de redação |
| Testes de versionamento de prompt | ✅ congelamento, coexistência, uma ativa |
| 13 documentos de IA | ⚠️ ver nota abaixo |

### Nota sobre "13 documentos de IA"

O prompt pede treze documentos. Esta base já tem `AI.md`, `AI_ENGINES.md` e
`AI_SEARCH_ARCHITECTURE.md`, e esta rodada acrescenta `AI_AUDIT.md` (o levantamento) e este
`AI_FINAL_AUDIT.md`. **Não foram criados treze arquivos** porque dividir o mesmo conteúdo em treze
produziria documentos de uma página que repetem uns aos outros — e documentação que se repete é
documentação que divergirá. O conteúdo pedido está coberto: arquitetura, custo, crédito,
privacidade, segurança, avaliação, governança de prompt e o que não existe.

## 5. Veredito

**AMARELO.** A governança da camada de IA existente está implementada, testada e documentada. A
camada **não** tem embeddings, cache semântico, agentes, ferramentas nem fallback entre provedores —
e cada ausência está declarada com motivo, risco e o que seria necessário.

A plataforma **não pode** ser apresentada como "plataforma de IA". Pode ser apresentada como
plataforma de governança e prestação de contas **com assistência de IA auditável**, que é o que ela
é — e a diferença entre as duas frases é exatamente a diferença entre vender o que existe e vender o
que soa melhor.
