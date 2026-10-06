# Motores operacionais — e por que a IA aqui não é um chatbot

> Escrito na v0.17.0, a partir do código. Cada afirmação deste documento tem um teste correspondente em
> `backend/tests/test_architecture.py`; se o código mudar e o documento ficar falso, a suíte quebra.

## A exigência desta rodada

Os documentos pedem **IA como motor operacional, não como conversa**. A frase é fácil de escrever e
impossível de conferir depois — então ela virou dado: `backend/impacto/engines/registry.py` declara cada
motor com módulo, função, natureza, versão, rotas, **o que produz** e **o que nunca decide**.

Cinco testes transformam a declaração em compromisso:

| Teste | O que ele impede |
|---|---|
| `test_every_declared_engine_resolves_to_real_code` | motor declarado que não existe no código |
| `test_declared_engine_versions_match_the_modules` | versão no documento diferente da versão no código |
| `test_declared_engine_routes_exist` | rota citada que ninguém pode chamar |
| `test_only_the_declared_places_call_the_language_model` | **um chatbot novo entrar de carona** |
| `test_deterministic_engines_do_not_import_the_ai_gateway` | motor "determinístico" que chama modelo |

`GET /v1/engines` devolve o registro inteiro, com a mesma informação que está aqui.

## O estado real

40 motores. Três naturezas, e a distinção muda o que se pode prometer:

| Natureza | Quantos | O que significa |
|---|---|---|
| `deterministic` | 35 | mesma entrada, mesma saída; auditável linha a linha; pesos em arquivo de configuração, não embutidos |
| `grounded_retrieval` | 2 | responde por **extração** do conteúdo cadastrado; nenhum texto é gerado por modelo |
| `llm_assisted` | 3 | um modelo reescreve ou complementa **sobre base determinística**, como rascunho |

> **v0.20.0 — o registro estava incompleto, e isso era pior que não ter registro.** A auditoria desta
> rodada encontrou **doze** módulos que decidem algo sobre organização ou projeto e não apareciam
> aqui, entre eles a camada de impacto INTEIRA: afirmações, equidade, reputação e selos — justamente
> os motores que sustentam a promessa da plataforma. Um inventário incompleto dá a impressão de
> inventário. O teste `test_every_module_with_its_own_engine_version_is_declared` passou a reprovar
> a suíte quando um módulo com `ENGINE_VERSION` fica de fora, e o critério é objetivo: declarar-se
> motor é entrar no registro.

### Os dois "assistentes" não são chatbots

`POST /v1/help/assistant` e `POST /v1/solutions/assistant` devolvem `ai_used: false` e `grounded: true`.
A resposta é concatenação de campos do banco — título, resumo e passos de um artigo, ou pergunta e
resposta de uma FAQ — prefixada por «Segundo o guia…». Abaixo da confiança mínima (0,30) a resposta é
**nula**, com a frase "Não encontrei informação suficiente na base oficial" e a oferta de abrir chamado.
Um chatbot responderia qualquer coisa; estes se recusam.

### Os três pontos que chamam modelo

Todos em `backend/impacto/api/ai_routes.py`:

| Rota | O que o modelo faz | O que acontece se ele falhar ou mentir |
|---|---|---|
| `POST /v1/ai/structure-need` | sobrescreve **apenas campos de texto** do projeto estruturado | JSON inválido é descartado; vale a base de regras `local.structure_need()` |
| `POST /v1/ai/draft` | reescreve para clareza um rascunho já montado localmente | saída com ≤200 caracteres é descartada; a instrução proíbe alterar número, nome ou marcação `[COMPLETAR]` |
| `POST /v1/ai/summarize-project` | resume o projeto em até quatro frases | qualquer exceção cai no resumo local |

Em todos: saída marcada `draft: true` e `human_review_required: true`.

### Controles que valem para toda chamada

Implementados em `engines/ai/gateway.py`: cota mensal por organização (402 ao estourar); **redação de
dado pessoal — CPF, e-mail, telefone, CEP, RG — antes de qualquer envio externo**; limite de tamanho de
contexto; timeout com duas retentativas e queda para o provedor local; registro de uso **sem conteúdo**
(só hash da entrada, tamanhos, tokens, latência e número de redações); e custo estimado somente quando
há preço declarado — a tabela de preços de IA **nasce vazia**, então nenhum custo é inventado.

A instrução de sistema proíbe inventar número, fonte, lei ou meta, e exige `[COMPLETAR: …]` no lugar do
dado que falta.

### O que a IA nunca faz, em nenhum dos três pontos

Não decide elegibilidade, não aprova, não assina, não envia, não calcula compatibilidade, não classifica
documento (a classificação é regra local, apesar de morar no pacote `engines/ai/`) e não escreve número
de prestação de contas — esses são colhidos pelo banco e protegidos por `guard_columns`.

## Onde cada motor mora

Agrupados como no registro: **prontidão** (2), **compatibilidade** (4), **conformidade** (3),
**documento** (2), **evidência** (3), **fiscal** (1), **busca** (3), **soluções** (4), **econômico** (3),
**IA** (3), **impacto** (4), **confiança** (4), **orientação** (1), **operação** (1), **governança** (1),
**vocabulário** (1). A lista completa, com caminho de módulo e função, está em `engines/registry.py` — e
é a mesma que a rota devolve, porque é a mesma fonte.

## Cobertura: onde a cadeia é forte, e onde não é

`ENGINE_COVERAGE.md` traz os 40 motores com seis colunas — **implemented, integrated, tested, E2E,
security, observability** — e `GET /v1/engines/coverage` devolve o mesmo cálculo.

**Nenhuma das seis colunas é declarada.** Todas são derivadas do código, do roteador, da suíte de testes
e do esquema do banco. Isso importa porque o diferencial desta plataforma não está numa tela: está na
cadeia necessidade → match → oportunidade → execução → serviço → evidência → prestação de contas →
resultado → impacto → reputação → inteligência. Uma cadeia vale o seu elo mais fraco, e um elo fraco é
exatamente o que uma tabela escrita à mão esconde — porque quem escreve é quem construiu. Um motor não
ganha uma coluna sendo descrito como completo; ganha quando o fato existe.

A tabela devolve `false`, e devolve de propósito: oito motores calculam e **não deixam rastro durável**,
isto é, depois do fato não há como responder "este motor rodou? com qual versão?". Isso aparece como
`NÃO` em vez de ficar escondido atrás de uma boa descrição. `n/a` em E2E e em segurança significa motor
sem rota própria — herda a barreira de quem o chama, e não é falha.

## Uma correção que esta fase produziu

O comentário de `engines/solutions/intent.py` citava `services/solutions.refine_with_ai` como um
refinador opcional por IA. **Essa função nunca existiu.** Referência órfã em comentário vira prova
documental falsa no dia em que alguém a lê como implementada. Corrigida, com o motivo registrado no
próprio comentário.
