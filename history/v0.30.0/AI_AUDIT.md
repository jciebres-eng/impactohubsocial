# Auditoria da camada de IA — Impacto Trust

> FASE 01 do prompt mestre de IA. Medido no código e no banco em 2026-10-07, versão 0.22.0.
> Cada linha tem evidência. Onde não há, está escrito AUSENTE.

## 0. O achado principal

A camada de IA desta plataforma é **deliberadamente pequena e honestamente documentada**. Entre os
**42 motores declarados**, apenas **3 chamam modelo de linguagem**; 37 são determinísticos e 2 são
recuperação ancorada que responde `ai_used: false`. Existe **um** ponto de chamada
(`engines/ai/gateway.py`), e um teste de arquitetura reprova a suíte se aparecer outro.

Isso não é lacuna: é a aplicação da mesma regra que governou a v0.22.0 — não construir o que não se
pode provar. O prompt desta rodada pede o contrário do que seria tentador: **a IA não deve
substituir motor determinístico**, e aqui ela não substitui.

O que falta é o que torna a camada **governável quando ela crescer**: registro de prompt com versão,
política de modelo, validação de esquema na saída, crédito separado de token, orçamento, defesa
contra injeção e avaliação.

## 1. Situação item por item

| componente | situação | evidência |
| --- | --- | --- |
| AI Gateway (ponto único) | **EXISTE** | `engines/ai/gateway.py:76`; instanciado 1× em `app.py:45`; `AI_CALL_SITES` com 1 item em `engines/registry.py:452`; guarda em `test_architecture.py:194`. **0 módulos chamam provedor direto** |
| Abstração de provedor | **PARCIAL** | só `complete()` (`gateway.py:47`). 4 provedores em `config.py:105`: `local`, `anthropic`, `openai_compatible`, `disabled`. Os dois externos fazem POST real e **nunca foram exercitados contra provedor real** |
| `embed` / `classify` / `countTokens` / `estimateCost` / `healthCheck` | **AUSENTE** | nenhum existe no pacote |
| Model Router / tiers / roteamento por risco | **AUSENTE** | um único `AI_MODEL` de ambiente (`config.py:108`) |
| Prompt Registry | **AUSENTE** | 4 prompts literais em `gateway.py:70,161,190,202` |
| `prompt_version` | **AUSENTE** | 0 ocorrências no repositório |
| Validação de esquema na saída | **PARCIAL** | `json.loads` de substring + allowlist de 5 chaves (`gateway.py:166-174`); descarta inválido e marca a resposta como local |
| RAG / embeddings / pgvector | **AUSENTE — e declarado** | extensões do banco: `citext, pg_trgm, pgcrypto, plpgsql, unaccent`. `AI_SEARCH_ARCHITECTURE.md` já afirma a ausência; a busca é FTS + trigrama + tesouro de 67 conceitos |
| `ai_usage` (trilha de uso) | **EXISTE — 19 colunas, 0 linhas** | `migrations/0001_schema.sql:899` + custo em `0019:176-183`; um único INSERT, `gateway.py:103` |
| Cálculo de custo por token | **EXISTE no banco, sem preço** | `app_price_ai_usage()`; `ai_price_table` com **0 linhas** → `cost_status='no_price_table'`, custo NULL (nunca 0) |
| Cota por plano | **EXISTE** | `ai_requests_month` em 12 planos (`config/plans.json`); bloqueio 402 em `gateway.py:86-99`; função `ai_usage_this_month()` usada em 3 lugares |
| Crédito separado de token | **AUSENTE** | nenhuma tabela nem campo de crédito de IA |
| Orçamento (R$) de IA por organização | **AUSENTE** | `spend_limits` existe e soma apenas `platform_charges` |
| Redação de PII antes do envio | **PARCIAL** | 5 padrões (CPF, e-mail, telefone, CEP, RG) em `gateway.py:24-38`. **CNPJ está fora** e o template de minuta envia CNPJ e razão social (`engines/ai/local.py:103`) |
| Defesa contra injeção de prompt | **AUSENTE** | texto do usuário entra no prompt sem delimitação nem detecção |
| Classificação de sensibilidade antes do envio | **AUSENTE** | a decisão é binária: provedor local ou externo |
| Allowlist de ferramentas / tool use | **N/A** | não há function calling (0 ocorrências) |
| Timeout / retry / fallback | **EXISTE** | 30 s (`config.py:109`); 2 retentativas com backoff (`adapters/http_client.py:75`); qualquer exceção cai para a base determinística (`gateway.py:147`) |
| Rate limit | **PARCIAL** | 3 de 4 rotas têm `rate=`; `POST /v1/ai/classify-document/{id}` não tem (`ai_routes.py:42`) |
| Execução assíncrona / fila | **AUSENTE** | as 3 chamadas são síncronas **com transação de banco aberta** por até 30 s (`gateway.py:157,188,199`) |
| Evals / golden dataset / teste de alucinação | **AUSENTE** | 4 testes tocam IA, todos de unidade |
| `status` de `ai_usage` | **PARCIAL** | os 3 pontos gravam literal `"ok"`; `'rejected'` e erro nunca são escritos, embora a cota os exclua |
| UI de IA | **PARCIAL** | 2 telas chamam IA, ambas rotulam a saída como rascunho. `GET /v1/ai/usage` **existe e nenhuma tela o consome**. Sem estimativa de custo antes da operação |
| Documentação | **CONFERE** | `docs/AI.md`, `AI_SEARCH_ARCHITECTURE.md` e `docs/AI_ENGINES.md` afirmam o que o código faz, inclusive as ausências |

## 2. O que esta rodada implementa

Na ordem de prioridade do próprio prompt (regra determinística primeiro, IA depois):

1. **Prompt registry versionado em banco**, com `prompt_version` gravado em `ai_usage` — sem
   rastreabilidade de qual prompt gerou qual análise, nenhuma avaliação é comparável.
2. **ModelPolicy por tier**, como dado: a escolha de modelo sai do ambiente e passa a ser política.
3. **Validação de esquema na saída**, substituindo a allowlist de 5 chaves.
4. **Guardrails**: delimitação do conteúdo não confiável, CNPJ na redação, classificação de
   sensibilidade antes do envio externo.
5. **Crédito ≠ token**, com reserva atômica e idempotência, e **orçamento** em reais.
6. **Status real** em `ai_usage` e rate limit na quarta rota.
7. **Evals com golden dataset** sobre os motores **determinísticos** — que é o que se pode avaliar
   sem provedor contratado, e é honesto chamar de avaliação.

## 3. O que esta rodada NÃO implementa, e por quê

- **Embeddings, pgvector, busca vetorial, cache semântico.** Exigiriam um provedor de embedding
  contratado para produzir vetor real. Construir a tabela e o índice sem nada para indexar seria
  infraestrutura que não se pode exercitar — e o próprio prompt recusa "IA de demonstração".
- **Fallback entre provedores distintos.** Há fallback para a base determinística, que é o caminho
  seguro. Encaminhar dado a um segundo provedor externo exige política de privacidade por provedor
  e dois contratos; sem eles, o fallback automático violaria §63 do prompt.
- **Processamento em lote.** Só é economicamente vantajoso com volume e preço reais; não há nenhum
  dos dois.
- **Tool use / agentes.** Não há function calling, e introduzi-lo com a IA podendo chamar
  ferramenta do sistema é exatamente o que §78 e §111 mandam governar antes de existir.
