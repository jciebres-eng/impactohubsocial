# Procedimento de rollback — v0.29.0 → v0.28.0

Vale para a instalação que já aplicou `0069_v0290_knowledge_provenance.sql`. As migrações do IMPACTO são
**forward-only** (`impacto/db/migrate.py` só aplica; não há "down"), portanto o rollback é de **código** com o
banco mantido, ou de **banco por restauração de backup**. Nada aqui foi executado em produção — não existe
produção desta versão; o procedimento foi conferido contra o conteúdo da 0069 (o que ela cria e o que ela altera)
e contra o dry-run `impacto_m69`.

## 0. Antes de atualizar (pré-condição do rollback)

1. `pg_dump -Fc` da base (ou snapshot do volume) **antes** de aplicar a 0069, guardado fora do host.
2. Anotar o commit da imagem anterior (`ff31622`, v0.28.0) e o hash da imagem em execução.

## 1. Rollback de código (banco mantido) — o caminho normal

Quando usar: defeito no backend/front da v0.29.0, sem corrupção de dados.

1. Reimplantar a imagem/commit `ff31622` (v0.28.0). O backend da v0.28.0 **não** conhece `kb_sources`,
   `kb_citations` e `kb_work_items` e não as toca; a 0069 fica registrada em `schema_migrations`. O que a 0069
   alterou em tabelas pré-existentes é compatível com o código antigo:
   * `kb_article_versions`, `kb_faqs`, `kb_resources`: o CHECK de `status` só ganhou o valor `retracted`; as
     três colunas novas (`retraction_reason`, `retracted_by`, `retracted_at`) são nulas. **Conteúdo retirado na
     v0.29.0 continua invisível** na v0.28.0: `kb_visible`/`live_version_id`/`search_doc` já foram anulados na
     retirada, e o código antigo só lista `published`. O gatilho `kb_retraction_terminal` impede que o código
     antigo "reative" um retirado por engano (409 no banco).
   * `kb_unpublish_article` (`CREATE OR REPLACE`): a versão nova é um superconjunto da anterior (trata `archived`
     e `retracted`); o comportamento para `archived` é o mesmo.
   * `content_history.object_type`: CHECK ganhou `'source'`; linhas antigas intactas.
   * `audit_action_categories` (`kb`) e `polymorphic_refs`: linhas a mais, sem efeito no código antigo.
2. Verificar `GET /readyz` e `GET /v1/help/search?q=orcamento` com uma conta de teste; abrir `/ajuda`.
3. O que se perde no período em v0.28.0: fontes/citações/fila editorial (rotas 404), glossário conceitual
   (`/ajuda/glossario` cai no catch-all `/ajuda/:slug` → "não encontrado"), tooltips/popovers (não existem no
   bundle antigo), assistente com citação (volta ao assistente anterior, que responde a partir de qualquer
   resultado — inclusive DEMO — sem dizer a origem). Nada é apagado: fontes, citações e itens de trabalho
   continuam no banco e voltam a valer na reimplantação da v0.29.0.

## 2. Rollback de banco (restauração) — só se houver corrupção de dados

1. Parar o backend. 2. Restaurar o dump do passo 0 numa base nova e trocar o apontamento (ou restaurar o
snapshot). 3. Reimplantar `ff31622`. 4. **Perda:** tudo o que foi escrito após o dump — inclusive dados que não
são da Central. Último recurso; prefira o §1.

## 3. Rollback parcial sem reimplantar

* **Fila editorial inundando**: os itens são deduplicados enquanto abertos (uma linha por chave, contador de
  ocorrências); se mesmo assim incomodar, dispense em lote com resolução (`POST …/work-items/{id}`,
  `status = dismissed`). Nada bloqueia a busca ou o assistente: `kb_work_open()` nunca lança.
* **Definição errada no glossário**: corrija `config/concepts.json`, rode `scripts/sync_concepts.py`, rebuild do
  front; ou marque o termo `status = needs_review` (a interface passa a avisar "definição em revisão"). Não há
  dado no banco a reverter.
* **Fonte errada**: não apague (DELETE é proibido); retire com motivo (`…/sources/{key}/retract`, reviewer) — o
  conteúdo que a cita vira item `retraction_followup` para decisão humana.
* **Conteúdo retirado por engano**: a retirada é terminal por desenho; publique uma versão nova do artigo
  (quatro olhos) — é o caminho previsto, não um contorno.

## 4. Como voltar a avançar

Reimplantar a v0.29.0: a 0069 já está registrada (checksum conferido por `migrate.py`); nenhuma migração roda de
novo; fontes, citações e itens de trabalho criados continuam válidos.

## 5. O que NÃO fazer

* Não executar `DROP TABLE` das tabelas da 0069 à mão: `kb_citations` referencia `kb_sources`; `polymorphic_refs`
  e `audit_action_categories` apontam para elas; `schema_migrations` ficaria com checksum de algo que não existe.
* Não apagar citações (append-only por gatilho) nem alterar chave/URL/hash de fonte (gatilho `kb_source_guard`).
* Não "reativar" conteúdo retirado por UPDATE direto: o gatilho recusa; use versão nova.
