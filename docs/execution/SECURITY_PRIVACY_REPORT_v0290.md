# Relatório de segurança e privacidade — v0.29.0 (camada de conhecimento e ajuda contextual)

Escopo: o que a v0.29.0 acrescentou (migração 0069, 13 rotas, assistente, busca medida, catálogo de conceitos,
componentes de ajuda). O que já existia continua coberto pelos relatórios anteriores. **Nada aqui afirma que o
sistema é "100% impossível de invadir"** (regra absoluta do proprietário).

## 1. Superfície nova

| Superfície | Autenticação | Limite de taxa | Dados expostos | Prova |
|---|---|---|---|---|
| `GET /v1/help/sources`, `GET /v1/help/sources/{key}` | nenhuma (público) | 300/h por IP | metadados de fonte (lei, norma, padrão, documento interno **sem texto**), classe, direitos, verificação; conteúdos publicados que a citam | revisadas em `test_architecture` (lista pública com justificativa); RLS leitura aberta de propósito |
| `GET /v1/public/concepts` | nenhuma | 120/h por IP | arquivo estático versionado (`config/concepts.json`); sem banco | idem |
| `POST /v1/help/report-incorrect` | usuário autenticado | 20/h por IP | grava `target_type/target_id`, `what` (≤ 2000) e `ctx` na fila; **não** grava o conteúdo | `test_unhelpful_feedback_and_incorrect_reports_become_work_items`; auditoria `kb.incorrect_report` |
| `/v1/admin/content/*` (9 rotas) | admin + papel editorial (`editor`/`reviewer`/`support`) + MFA | padrão admin | fontes, citações, retirada, fila | matriz de autorização (238 de plataforma); `test_v0230_api_sweep` prova 403 para cliente |

## 2. Controles no banco (não só na API)

* Quatro olhos na verificação de fonte (`verified_by ≠ created_by`) e na publicação (já existia) — gatilho, não tela.
* Citação com trecho só se `rights.excerpt = allowed`; hash SHA-256 do trecho conferido pelo banco; append-only.
* Retirada exige motivo, autor e data (CHECK) e é terminal (gatilho): não há "des-retirar" silencioso.
* `kb_sources`: identidade imutável (chave, URL, tipo, data de publicação, hash); DELETE proibido.
* `kb_work_open()` é SECURITY DEFINER com portão fechado: só os 8 tipos previstos; detalhes jsonb limitados.
* RLS em todas as 4 tabelas novas (`test_every_table_has_rls`); grants mínimos a `impacto_app`.

## 3. Privacidade (LGPD)

* **Texto de busca e pergunta ao assistente nunca são guardados** (ADR-043 mantido): a fila editorial recebe só
  `q_hash` (SHA-256 truncado) e os tópicos do tesauro. Teste: `test_search_without_result_opens_one_deduplicated_item_per_topic_without_free_text`,
  `test_without_any_base_it_says_so_and_opens_a_gap_item_without_the_text`.
* As tabelas novas **não têm `org_id`/`user_id` como dado do titular**: `reporter_id`/`verified_by`/`retracted_by`
  são referências a pessoas da equipe ou ao relator, com finalidade de trilha editorial; a exclusão de conta
  (`test_v0190_lgpd_deletion`) continua verde — nada novo a declarar em `config/data_retention.json`.
* Nenhum dado sai da instalação: o assistente é extrativo (`ai_used = false`); não há embeddings nem provedor
  envolvido na camada de conhecimento. Os direitos `send_external/embed/train` das fontes legais estão `unknown`
  **justamente** para que, se algum dia houver provedor, a operação fique bloqueada até conferência.
* O catálogo de conceitos e as fontes são públicos por natureza (são referências), não dados pessoais.

## 4. Injeção de prompt e conteúdo malicioso

* Sem modelo de linguagem no caminho: conteúdo da base nunca é interpretado como instrução. Quando/se um
  provedor for ligado ao assistente, a revisão deste item é obrigatória (anotado no checklist D e em ADR-357).
* Trecho citado é texto armazenado com limite (600) e hash; a interface renderiza como texto (React escapa).
* Fontes com URL: a interface abre com `rel="noopener noreferrer"` e `target="_blank"`; a URL é imutável após o
  registro (um editor não pode trocar o destino de uma fonte conferida).

## 5. Front-end

* Componentes sem biblioteca nova (sem dependência de terceiro adicionada ao `package.json`); sem `innerHTML`.
* Nenhum segredo, chave ou URL interna no catálogo (`secrets_scan.py` no fechamento).
* Acessibilidade conferida no navegador (A11Y_JS + contraste) nas páginas tocadas, claro e escuro.

## 6. Achados e correções desta rodada

| Achado | Gravidade | Correção |
|---|---|---|
| `.pill-muted` a 1,27:1 no tema escuro (pré-existente; `--linha-2` era neutro claro fixo) | acessibilidade (WCAG 1.4.3) | sobrescrita por tema; provado pelo E2E |
| Path param `{item_id}` na fila forçava UUID e devolvia 404 para id inteiro | funcional | renomeado `{item}` com validação própria |
| Assistente anterior respondia com conteúdo DEMO/vencido/terceiros sem dizer a origem | integridade da informação | reescrito (ADR-357) |
| Baseline anônimo da busca "ruim" na primeira medição | falso positivo: anônimo não vê conteúdo `authenticated` — comportamento correto | medição como OSC autenticada; anônimo medido à parte para provar que o restrito **não** vaza |

## 7. O que não foi testado

Teste de penetração externo; carga sobre as rotas novas (são leituras leves e limitadas por taxa); revisão
jurídica das definições e das fontes (pessoa, não software).
