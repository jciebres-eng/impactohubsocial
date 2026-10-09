# Relatório final de execução — IMPACTO v0.29.0

**Data:** 09/10/2026 · **Ramo:** `main` · **Tag:** `v0.29.0` (a criar no GitHub pelo proprietário no
commit indicado em §3 — o proxy deste ambiente recusa envio de tag) · **Pacote:**
`IMPACTO_TRUST_FINAL_RELEASE_0.29.0.zip` (SHA-256 no `.sha256` ao lado) · **Auditoria:**
`FINAL_EXECUTION_AUDIT.md` · **Relatório técnico (DOCX):** `IMPACTO_v0.29.0_RELATORIO_TECNICO.docx`
(entregue ao lado do pacote; conteúdo derivado deste relatório e da auditoria)

## 1. Executive Summary

A rodada incorporou a **base de conhecimento v0.26.0** à release mais nova **sem retroceder nada** e deu à
Central de Conhecimento governança de ponta a ponta — fonte → direitos → citação → quatro olhos →
publicação imutável → retirada → busca → assistente → interface — mais um **sistema global de ajuda
contextual** (tooltip, popover, glossário) alimentado por um único catálogo de conceitos:

- **Reconciliação, não cópia** (`knowledge-base/` + `CONTROL-RECONCILIATION.json`): os 58 controles
  O/A/V/H/D classificados contra o código com os testes que os provam — IMPLEMENTED_TESTED 6 · PARTIAL
  27 · BLOCKED_EXTERNAL 13 · NOT_IMPLEMENTED 12 (237 referências de teste conferidas por AST). Nenhum
  controle foi declarado "em conformidade".
- **Fontes com direitos de uso** (migração 0069): classe O/A/V/H/D, jurisdição, vigência, licença,
  direitos por operação (allowed/denied/**unknown = bloqueado**), verificação por pessoa diferente de
  quem registrou (gatilho), revisão marcada. 11 fontes semeadas, **0 conferidas** — a interface diz
  "fonte ainda não conferida por outra pessoa" em cada citação.
- **Citação, retirada e fila editorial:** citação só em rascunho, trecho só com direito permitido e
  hash conferido pelo banco; retirada terminal com motivo que some da busca, do assistente e do
  sitemap no mesmo instante; buscas sem resultado, "não ajudou", vencidos, relatos de erro e fontes a
  revisar viram itens de trabalho deduplicados — **só hash e tópicos, nunca o texto** (ADR-043).
- **Assistente que cita e se abstém:** extrativo (sem modelo), só publicado + oficial/educacional +
  não DEMO + não vencido; devolve a **única** fonte usada com citações, o que excluiu e por quê;
  em empate pergunta; sem base diz "Não encontrei informação suficiente na base publicada da
  plataforma." Nunca se chama "base oficial".
- **Busca medida antes de mudada:** 35 consultas rotuladas, 8 métricas, baseline gravado como piso
  que reprova regressão (hit@1 0,875 · MRR 0,94 · nDCG@5 0,93 · abstenção 3/3 · p95 ≈ 25 ms). A única
  mudança (tesauro 1.1) foi feita porque a medição mostrou ganho. **Sem embeddings** — sem ganho
  demonstrado, não entra. Conjunto pequeno e sintético: o arquivo de evidência diz isso.
- **Ajuda contextual:** 33 conceitos definidos UMA vez (`config/concepts.json`: definição, por que
  importa, como o IMPACTO usa, limites, fontes) → `concepts.ts` gerado → `Tooltip`/`InfoPopover`/
  `GlossaryTerm`/`ContextualHelp` sem biblioteca nova → `/ajuda/glossario`; aplicado em 11 telas;
  mouse, teclado e toque; claro/escuro; movimento reduzido; `GET /v1/public/concepts`. As 33
  definições estão **`needs_review`** (escritas a partir do código; revisão por área pendente) e a
  interface avisa.
- **Contagens** (ADR-340): 936 operações (+13), 238 de plataforma, 54 públicas, 226 telas (+1), 69
  migrações, 50 motores (nenhum novo).
- Tudo provado por HTTP e PostgreSQL reais (38 testes novos em 3 módulos), por 7 jornadas no
  Chromium (mouse, teclado, toque, escuro, movimento reduzido, a11y, contraste), pelas 226 telas por
  perfil e pela regressão completa, cuja primeira passagem acusou 10 falhas e 1 erro — todas com
  causa e correção escritas (auditoria §7), nenhuma resolvida afrouxando teste; duas eram **achados
  reais** (nome acessível de título com termos; medição da busca dependente da ordem dos testes).

**Decisão: GO WITH CONDITIONS** (§27) — as condições são editoriais (conferir fontes, revisar
definições, escrever conteúdo oficial) e externas (parecer, DPO, provedores), não técnicas.

## 2. Version

0.29.0 — `VERSION`, `backend/pyproject.toml`, `web/package.json`, `web/package-lock.json`,
`README.md`, `docs/openapi.json`. Documentos da v0.28.0 preservados em `history/v0.28.0/` (166
arquivos de `1c3114f`); manifestos anteriores em `history/manifests/`.

## 3. Commit

Commits da rodada (sobre `1c3114f`, v0.28.0): `aa2785c` (F1–F3: versão, snapshot, base de
conhecimento versionada e reconciliada, migração 0069, serviço e rotas de proveniência, assistente
reescrito, 22 testes), `bf0c3e4` (F4: conjunto de avaliação da busca, métricas, baseline, tesauro 1.1,
4 testes), `4107b08` (F5: catálogo de conceitos, componentes de ajuda, glossário, 11 telas, E2E,
contagens), `859efdc` (documentos: ADR-353..359, changelog, notas, KNOWLEDGE_*, checklist, rollback,
rastreabilidade, segurança, limpeza; correções da 1ª regressão), o commit de fechamento (auditoria,
relatório, evidência da regressão) e o **commit final dos manifestos**, para o qual a tag `v0.29.0`
deve apontar e do qual o pacote é construído byte a byte (`verify_package_against_git.py`); o hash
desse commit é registrado no `.sha256` do pacote e não cabe dentro do próprio commit.
`FINAL_RELEASE_MANIFEST.json` registra o último commit de conteúdo.

**GitHub Actions:** a run `37932633056` do primeiro commit de manifestos (`9043b5a`) reprovou 3 de 4
trabalhos — gitleaks (falso positivo no campo `source_key` do catálogo de conceitos) e o typecheck
oficial (7 importações não usadas), que derrubou também a pilha do zero; causas e correções na
auditoria §7 (3ª rodada). **Run `37935603837` do commit candidato à tag `dd2f8c3`: `auditoria`, `docker`
(typecheck oficial), `pilha-do-zero` (banco vazio → imagem → migrações → seed → jornadas → 226 telas → axe →
reinício) e `backend` (gitleaks + suíte oficial completa) — os quatro verdes.** Este parágrafo foi acrescentado
depois da run, no commit seguinte; a tag `v0.29.0` aponta para `dd2f8c3`.

## 4. Architecture Status

Starlette + PostgreSQL 16 com RLS em toda tabela (exceção: `schema_migrations`; nenhuma FORCE), hash
encadeado em auditoria/razão/valor/confiança, sem custódia. Mudanças: 4 tabelas novas
(`kb_sources`, `kb_citations`, `kb_work_items` + funções), estado `retracted` em 3 tabelas da Central;
`services/kb_provenance.py`, `api/kb_provenance_routes.py` (12 rotas), `GET /v1/public/concepts`,
`engines/knowledge/evaluation.py` novos; `services/knowledge.py` (busca abre lacuna; assistente
reescrito); `knowledge-base/` versionada; `config/concepts.json`, `config/search_eval.json`;
`web/src/ui/help.tsx`, `web/src/concepts.ts` (gerado). Documentos canônicos:
`docs/execution/KNOWLEDGE_ARCHITECTURE_v0290.md`, `CONTENT_GOVERNANCE.md`, `KNOWLEDGE_DATA_MODEL.md`,
`AI_SEARCH_ARCHITECTURE.md`, `docs/execution/TRACEABILITY_MATRIX_v0290.md`.

## 5. Engines Status

50 motores: implemented/integrated/tested 50/50; `MOTOR_COVERAGE_MATRIX.md` (gerado) VERDE 37 ·
AMARELO 13 · VERMELHO 0. Nenhum motor novo: a avaliação da busca é módulo de métricas, não decide
nada em produção. `ENGINE_COVERAGE.md`, `docs/execution/ENGINE_VALIDATION_MATRIX.csv`, `docs/AI_ENGINES.md`.

## 6. Contract Intelligence

PASS (inalterado da v0.26.0–v0.28.0). A camada de conhecimento não lê nem escreve no contrato.

## 7. Match

PASS (inalterado): a busca da Central e o assistente **não leem** reputação, planos, pagamento nem
match (`test_knowledge_search_and_match_never_read_reputation_or_plans`, guarda por AST). O conceito
"compatibilidade" do glossário diz, em cada tela, que não é aprovação nem elegibilidade.

## 8. Diagnostic

PASS (inalterado): `diagnostic-engine@1.0.0`, 8 dimensões — agora nomeadas no conceito
`diagnostico_prontidao` do glossário, com o aviso de que "IMPACTO Ready" é estado, não selo.

## 9. Equity

PASS (inalterado): sem nota única, denominador com fonte. Conceito `equidade` aplicado nas telas.

## 10. Evidence

PASS (inalterado). Novo: evidência **editorial** — citação com hash de trecho e fonte verificada por
outra pessoa é o mesmo princípio aplicado ao conteúdo da Central.

## 11. Responsibility

PARTIAL (inalterado): atribuição formal continua opcional.

## 12. Reputation

PASS (inalterado). A fila editorial e as retiradas não produzem efeito reputacional.

## 13. Seals

PASS (inalterado): selos só na quitação.

## 14. Government Data

Inalterado: torre territorial com k-anonimato ≥ 3. Dados IBGE/ODS oficiais continuam fora — e o
conceito `ods` do glossário diz que as **metas** numeradas não estão carregadas até haver fonte,
versão e licença registradas (controle LEG-024 continua PARTIAL).

## 15. Marketplace

Inalterado.

## 16. Payments

Inalterado (PASS / BLOCKED_EXTERNAL): nenhum pagamento real; camada 3,5 % / 1,5 % independente e
inativa; o glossário explica "não custodial", "quitação" e "taxa de serviço" com os limites.

## 17. Distribution

PASS (inalterado).

## 18. Billing

Inalterado: sem assinatura (ADR-341); créditos de IA em modo piloto (ADR-349).

## 19. Fiscal

BLOCKED_EXTERNAL (inalterado): NFS-e não implementada; a reconciliação da base lista os controles
fiscais como BLOCKED_EXTERNAL/NOT_IMPLEMENTED com o teste que falta.

## 20. Vouchers

Inalterado.

## 21. Identity

PARTIAL (inalterado): biometria, KYC, gov.br BLOCKED_EXTERNAL.

## 22. Security

Revisada (`docs/execution/SECURITY_PRIVACY_REPORT_v0290.md`): RLS nas 4 tabelas novas; quatro olhos
na verificação de fonte e na publicação **no banco**; citações append-only com hash; retirada
terminal; rotas editoriais com papel + MFA; 3 rotas públicas de referência revisadas e limitadas por
taxa; texto de busca/pergunta nunca guardado; assistente sem modelo (sem superfície de injeção nesta
versão; revisão obrigatória se um modelo for ligado); nenhum segredo em código, catálogo, documento
ou pacote (`secrets_scan.py`, gitleaks no CI); sem `innerHTML`; URL de fonte imutável após o
registro. **Nenhum sistema ligado à internet é "impossível de invadir", e este não é exceção.**

## 23. LGPD

As tabelas novas não guardam dado do titular além de referências editoriais (quem registrou,
verificou, retirou, relatou); nada a declarar em `config/data_retention.json`;
`test_v0190_lgpd_deletion` verde. A fila editorial guarda só `q_hash` + tópicos. Os direitos
`embed/send_external/train` das fontes legais estão `unknown` de propósito: se um provedor externo
for ligado, a operação fica bloqueada até conferência. Controles LGPD da base (ROPA, RIPD, DPO)
continuam BLOCKED_EXTERNAL na reconciliação.

## 24. Tests

```text
PRIMEIRA REGRESSÃO COMPLETA (código novo, antes das correções, scratchpad/suite/full_v0290_a.log):
  Ran 2379 tests in 1915.199s — 10 falhas, 1 erro, 29 pulados
  → causas e correções em FINAL_EXECUTION_AUDIT.md §7 (2 achados reais: nome acessível de título com termos
    de glossário; medição da busca dependente da ordem dos testes — ambos corrigidos no produto/medição, não
    no teste; 1 cartão 2 px fora da janela no celular; o resto: contagem 226, matrizes, openapi, documentos de
    fechamento e manifesto gerados no fechamento)
SEGUNDA REGRESSÃO COMPLETA (após correções, docs/evidence/test_run_v0.29.0.log):
  Ran 2380 tests in 1953.947s — 0 erro, 29 pulados (dependem de credencial), 5 falhas, TODAS de fechamento:
    4× test_v0270_release_docs (lê auditoria, relatório e manifesto no início da execução — ainda os da v0.28.0
       naquele instante; reescritos durante a execução), test_v0230_release_gate.test_the_manifest_exists_for_this_version
       (manifesto é gerado no fechamento). Manifestos gerados em seguida; portões de fechamento reexecutados (saída
       anexada ao fim do mesmo log).
MÓDULOS NOVOS: test_v0290_knowledge_base (27) · test_v0290_search_eval (4) · test_e2e_v0290_contextual_help (7)
JORNADAS: 16 jornadas, 256 passos, 0 falha · TELAS: 226 rotas, 0 falha · TELEFONE: no CI (pilha do zero)
LINT: ruff 0 · BUILD: esbuild ok · SYNC: concepts.ts em sincronia · TYPECHECK: tsc --noEmit 0 erros (local, tipos do DefinitelyTyped; oficial no CI)
```

Testes que fixam contagem foram atualizados com a razão escrita ao lado (936 operações, 238 de
plataforma, 54 públicas, 226 telas): ADR-340. Expectativas atualizadas com motivo: mensagem de
abstenção do assistente (`test_v0120_knowledge`, `test_e2e_knowledge`), lista de rotas públicas
revisadas (`test_architecture`). Nenhum teste foi removido ou enfraquecido.

## 25. External Dependencies

BLOCKED_EXTERNAL_DEPENDENCY, com o que cada uma exige (tabela completa em `EXTERNAL_INTEGRATIONS.md`):

| Dependência | Exige | Efeito hoje |
|---|---|---|
| Conferência das 11 fontes (vigência, licença, direitos) | pessoa com papel `reviewer`, diferente de quem registrou | todas `unverified`; a interface avisa em cada citação; direitos `embed/send_external/train` bloqueados |
| Revisão das 33 definições do glossário | jurídico, contábil, especialista em impacto | todas `needs_review`; a interface avisa em cada cartão |
| Conteúdo oficial com citações | equipe editorial (editor + reviewer) | a semente continua DEMO/educacional; o assistente responde com origem "educacional" e avisa |
| Decisão sobre 13 controles BLOCKED_EXTERNAL e 12 NOT_IMPLEMENTED da reconciliação | parecer jurídico, DPO, provedores (fiscal, pagamento, identidade) | continuam P0/P1 na matriz; nada declarado conforme |
| Conjunto de avaliação com consultas reais | piloto + rotulagem por mais de uma pessoa | piso atual vale para o corpus sintético |
| Parecer, provedores, minutas, hospedagem, chave PIX, tag no GitHub | como na v0.27.0/v0.28.0 | inalterado |

## 26. Known Limitations

- 0 de 11 fontes conferidas; 33 de 33 definições em revisão; nenhum conteúdo `official` — tudo dito
  na interface.
- A busca é léxica (FTS + trigram + tesauro); sem embeddings: paráfrase profunda pode não ser
  encontrada. O conjunto de avaliação é pequeno, sintético e rotulado por uma pessoa.
- O assistente é extrativo: responde com trechos de UM conteúdo; não sintetiza vários.
- Retirar uma fonte não retira o conteúdo que a cita (decisão editorial por desenho).
- Conceitos só em pt-BR; não aplicados em telas administrativas internas.
- `examples` por conceito não foi incluído (as definições usam "como o IMPACTO usa").
- Documentos SUPERADO da assinatura continuam com banner; typecheck oficial do front só no CI;
  defeitos pré-existentes B1/B2 (`TECHNICAL_BASELINE_BEFORE_EXECUTION.md` §4) fora do escopo.

## 27. GO / GO WITH CONDITIONS / NO-GO

```text
GO WITH CONDITIONS
```

Nenhuma falha técnica interna crítica em aberto: base reconciliada sem retrocesso, fontes com direitos
e verificação por outra pessoa, citações com hash só em rascunho, retirada terminal que propaga, fila
editorial sem texto livre, assistente que cita e se abstém, busca medida com piso, catálogo único de
conceitos com ajuda acessível, autorização, tenancy, persistência e regressão têm teste executado e
verde na segunda rodada. As condições são **editoriais e externas** (§25): conferir fontes, revisar
definições, escrever conteúdo oficial, decidir os controles bloqueados, tag no GitHub. Nenhuma falha
crítica foi convertida em "condição". Checklist operacional:
`docs/execution/PRODUCTION_CHECKLIST_v0290.md`; rollback: `docs/execution/ROLLBACK_v0290.md`.

## 28. Exact Next Step

1. Criar a tag `v0.29.0` no GitHub (Releases → nova tag no commit de fechamento) e anexar
   `IMPACTO_TRUST_FINAL_RELEASE_0.29.0.zip` + `.sha256` + o relatório DOCX.
2. Nomear editor(a) e reviewer (papéis `staff_roles` com MFA) e conferir as 11 fontes
   (`POST /v1/admin/content/sources/{key}/verify`) — a primeira tarefa editorial, sem a qual nada é
   "oficial".
3. Revisar as 33 definições do glossário por área (`config/concepts.json` → `status = published`,
   `scripts/sync_concepts.py`) e escrever os primeiros guias `official` com citações.
4. Próxima rodada técnica (sem dependência externa): ampliar o conjunto de avaliação com consultas
   reais (só hash/tópicos da fila `search_gap`) rotuladas por mais de uma pessoa; tela interna da fila
   editorial; conceitos nas telas administrativas; tradução en/es do catálogo.
