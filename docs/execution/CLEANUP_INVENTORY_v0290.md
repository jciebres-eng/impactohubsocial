# LIMPEZA v0.29.0 — o que saiu, o que ficou e por quê

Regra (a mesma da v0.28.0): remover só o que não serve mais E cuja remoção é provada segura pela suíte (nenhum teste
enfraquecido — ADR-340); tudo o mais fica, com o motivo escrito. Classificação: **REMOVIDO**, **MOVIDO**, **UNIFICADO**,
**MANTIDO**.

| Item | Classificação | Motivo / prova |
| --- | --- | --- |
| Assistente antigo (`assistant()` que respondia a partir de qualquer resultado da busca, inclusive DEMO/vencido/terceiros, sem dizer a origem) | **UNIFICADO** (reescrito no lugar) | uma única função; a antiga mensagem de abstenção ("Não encontrei na base…") foi substituída e as DUAS expectativas que a citavam (`test_v0120_knowledge`, `test_e2e_knowledge`) foram atualizadas com o motivo escrito ao lado — nenhuma asserção removida |
| `web/src/glossary.ts` / `config/glossary.json` (vocabulário de rótulos de enum) | **MANTIDO** e separado do catálogo de conceitos | são coisas diferentes: rótulo de status × conceito explicado. `scripts/sync_glossary.py` e `test_v0190_glossary` continuam valendo; `/ajuda/glossario` aponta para o glossário básico de rótulos |
| `ContextHelp({ctxKey})` em `web/src/pages/help.tsx` (ajuda por tela: lista guias/FAQ da tela) | **MANTIDO** | é ajuda POR TELA (vem da API, conteúdo editorial); a ajuda contextual nova é POR CONCEITO (catálogo estático). Usado em 7 telas; os dois coexistem sem duplicar texto |
| `.pill-muted` com `--linha-2` fixo | **CORRIGIDO** (não removido) | 1,27:1 no tema escuro, achado pelo E2E do glossário; sobrescrita por tema no mesmo padrão já usado em `.flow-fill`; `test_e2e_v0290_contextual_help` prova |
| Texto de ajuda duplicado em componentes | **nenhum** | `concepts.json` é a única origem; teste `test_every_concept_used_on_pages_exists_in_the_catalog` acusa id órfão; o validador do sync acusa promessa, short longo e referência inexistente |
| Código morto / flags sem leitor / funções sem chamador | **nenhum encontrado** | `test_v0200_cleanup` verde; todas as funções de `kb_provenance.py` têm chamador (rota ou serviço); todos os exports de `ui/help.tsx` são consumidos |
| `backend/.tmp_entry_storage*` | **REMOVIDO** do disco antes do pacote (não versionado) | lixo de execução de teste |
| `web/dist/assets/app-*.js` / `styles-*.css` antigos | **REMOVIDOS** pelo build (hash novo) | `build.mjs` substitui; `build-info.json` aponta os atuais |
| Pasta `knowledge-base/` (ZIP v0.26.0) | **MANTIDA INTACTA** + reconciliação ao lado | o pedido proíbe copiar um ZIP sobre o outro e retroceder; a base é fonte, a release é implementação (ADR-353) |
| Documentos SUPERADO da assinatura (lista da v0.28.0) | **MANTIDO** (com banner) | mesmo motivo da rodada anterior: rastreabilidade de manifestos históricos |
| Fontes `kb_sources` com `rights.embed/send_external/train = unknown` | **MANTIDO** de propósito | `unknown` bloqueia a operação até conferência humana; marcar `allowed` sem conferir seria inventar licença |

O que NÃO foi feito: apagar tabelas/colunas aposentadas (migrações forward-only); mover documentos SUPERADO;
traduzir o catálogo de conceitos (en/es) — fica como trabalho editorial, não técnico.
