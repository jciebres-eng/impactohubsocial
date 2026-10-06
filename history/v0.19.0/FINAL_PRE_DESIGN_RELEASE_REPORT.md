# Relatório final — v0.19.0 · vocabulário, primeiro acesso e gates de publicação

**Data:** 2026-10-06 · **Versão:** 0.19.0 (snapshot da anterior em `history/v0.18.1/`)
**Pedido atendido:** PROMPT MASTER — execução autônoma (implementar → testar → depurar → corrigir →
validar → git → ZIP), com os três itens pré-designer e os gates de publicação transformados em
portões executáveis.

---

## Decisão de release

# GO WITH CONDITIONS

**O que isso significa aqui, exatamente:** a base técnica está pronta para receber a camada de design
e **nada técnico** impede a publicação. As condições que restam são **externas** — credencial, conta,
infraestrutura e decisão jurídica — e cada uma está nomeada abaixo com o que já foi preparado em
código para recebê-la.

**Não é GO** porque três coisas que só se provam fora deste ambiente continuam não provadas:
auditoria de dependências (registry bloqueado), imagem Docker (docker indisponível) e carga com rede
real. **Não é NO-GO** porque nenhuma delas é defeito do software, e a infraestrutura para todas está
pronta e declarada.

---

## A · O que foi implementado

### A1 · Vocabulário oficial (item prioritário #1 do pedido)

| Entregue | Onde |
|---|---|
| Dicionário central: 123 termos, 23 domínios, 369 rótulos (pt-BR/en/es) + definição em pt-BR | `config/glossary.json` |
| Tabela que quem desenha lê | `GLOSSARY.md` (gerado) |
| Catálogo de tradução: de 98 para **221 chaves por idioma**, de 6 para **29 namespaces** | `config/i18n.json` (os 23 `g_*` são gerados) |
| A interface **consome** o vocabulário em vez de copiá-lo | `web/src/glossary.ts` (gerado), importado por `web/src/pages/core.tsx` |
| Rota pública | `GET /v1/public/glossary?locale=…&domain=…` |
| Sincronizador com modo de conferência | `scripts/sync_glossary.py` e `--check` |
| Registro de origem dos valores vivos | `backend/impacto/core/glossary.py` (`SURFACES`, `CATALOGS`) |

**Dois níveis, declarados.** Nível `enum` (valor que a tela mostra e não tem tabela de catálogo):
cobertura obrigatória nos três idiomas, conferida contra o código. Nível `catalog` (regra de alegação,
regra de selo, dimensão de reputação, papel, tipo de decisão, barreira): a origem é o **banco**, com
nome e explicação próprios — duplicar no glossário criaria duas verdades. Tradução do nível `catalog`
é `DEFER_POST_DESIGN`, declarado.

### A2 · Primeiro acesso (item prioritário #2)

`GET /v1/firstrun` devolve, para 12 áreas, as nove respostas que um estado vazio precisa dar: o que é,
por que está vazia, próximo passo (método, rota e tela reais), o que se ganha, obrigatório, opcional,
de onde vem o dado, como se verifica e — quando falta pré-requisito — **qual**.

Tudo sai de **contagem real no banco**. Nenhum dado de demonstração, nenhum valor de exemplo. Área sem
projeto escolhido devolve `counted: false`, nunca zero.

`EmptyArea` e `FirstRunPanel` (`web/src/ui/kit.tsx`, montados no painel inicial) são a referência de
como o contrato se desenha.

### A3 · Retorno por declarar contexto (item prioritário #3)

`GET /v1/projects/{id}/context-return`, com oito chaves: `CONTEXT_COMPLETENESS`,
`NORMALIZATION_METHODS_AVAILABLE`, `MATCH_EXPLAINABILITY`, `EVIDENCE_READINESS`, `SEAL_READINESS`,
`DIAGNOSTIC_READINESS`, `FUNDER_VISIBILITY`, `ELIGIBILITY_VISIBILITY`. Cada uma com `available`,
`total` e, para o que falta, `would_open`: a peça que falta e o que ela abre.

**Sem ranking.** O payload carrega `no_ranking_note` e um teste compara os retratos de reputação antes
e depois de declarar contexto, exigindo que sejam idênticos.

### A4 · Exclusão e retenção (LGPD)

* `config/data_retention.json`: 184 vínculos a organização ou titular, **58 declarados**, cinco classes
  (`deletable_with_parent`, `anonymizable`, `retainable`, `audit_only`, `append_only`).
* `backend/impacto/core/retention.py`: calcula a classe **efetiva** (chave estrangeira **mais** gatilho
  append-only) e compara com a declarada.
* `DATA_RETENTION.md`: gerado contra o banco real por `scripts/make_retention_doc.py`.
* Regra padrão que fecha o buraco futuro: **todo vínculo não declarado tem de ser CASCADE**; um novo
  que não seja reprova o teste.

### A5 · Backup agendado

* Tarefas `backup` e `email_canary` no executor que já existe (`backend/impacto/jobs.py`), com janela
  própria — e **não** um timer novo que ninguém exercitaria.
* Conferência em três níveis: tamanho, `sha256` contra o arquivo `.sha256` gravado, e
  `pg_restore --list`.
* Poda com retenção, gancho de cópia externa, e recusa explícita em chamar backup local de recuperação
  de desastre.
* Tabela `ops_job_runs` com quatro resultados, incluindo **`not_configured`** — o mais importante,
  porque é ele que impede falta de credencial de parecer sucesso.

### A6 · Canário de e-mail e observabilidade de envio

* Tabela `email_events`: um registro por tentativa, com identificador, tipo, **domínio** (nunca o
  endereço, nunca o corpo), provedor, tentativas, duração e erro.
* O registro é ligado **no mailer** (`adapters/mail.py` + `AppState`), não nos oito pontos que enviam
  e-mail.
* Estado de sucesso: **`accepted_by_smtp`**. O CHECK do banco não aceita um estado chamado entrega.
* `GET /v1/admin/ops/health`: veredito por tarefa e falhas de e-mail na janela.

### A7 · Banco

| Migração | O que faz |
|---|---|
| `0035_v0190_acceptance_org_anonymization.sql` | corrige o gatilho da prova de aceite |
| `0036_v0190_ops_observability.sql` | `ops_job_runs` e `email_events`, com RLS restrita à administração |

---

## B · O que foi corrigido (defeitos reais, achados por teste)

| # | Defeito | Como apareceu | Correção |
|---|---|---|---|
| B1 | **`/v1/firstrun` devolvia 500** | `match_runs.org_id` não existe — a coluna é `viewer_org_id` | consulta corrigida; o teste que exige que toda rota de próximo passo exista no roteador pegou o resto |
| B2 | **Rota de ODS anunciada com método errado** (`POST` em vez de `PUT`) | mesmo teste | método corrigido |
| B3 | **Denominador de um projeto vazava para os outros projetos da mesma organização** | o teste do projeto *sem* contexto encontrou um método de normalização disponível | `equity.methods_available()` passou a usar a mesma resolução do cálculo (`_current_denominators`) — uma verdade só |
| B4 | **Remover organização era impossível e o erro apontava para o lugar errado** | a primeira execução real de exclusão com registro em todas as áreas | o gatilho da prova de aceite recusava o `SET NULL` que a própria chave promete (migração 0035) |
| B5 | **A primeira versão da correção B4 ainda quebrava** | teste de exclusão com IP preenchido | a regra de IP confundia "não pode trocar" com "tem de ficar sem IP"; passou a ser o que sempre quis dizer: só pode apagar |
| B6 | **Terceira cópia do vocabulário em TypeScript** | varredura do próprio glossário | `core.tsx` passou a importar de `web/src/glossary.ts` |
| B7 | **`date.today()` no gerador de documento** | guarda arquitetural `test_product_dates_are_utc` | `impacto.clock.today()` (UTC) |
| B8 | **Contexto de sistema em módulo não revisado** | guarda `test_system_context_only_in_allowed_modules` | o gerador de documento saiu de `impacto/` e virou `scripts/make_retention_doc.py` |

### B9 · O que a conferência automática DESCOBRIU

Treze tabelas append-only em todo o sistema, com a trava certa e **nenhuma política que as
reconhecesse**: `billable_events`, `credential_verifications`, `diagnosis_versions`, `domain_events`,
`eligibility_evaluations`, `equity_assessments`, `match_feedback`, `price_change_notices`,
`project_snapshots`, `project_transitions`, `readiness_snapshots`, `trust_events`, `value_events`.

E a conclusão que ninguém havia escrito: **a plataforma não remove organização — ela fecha.** A
remoção é recusada duas vezes (guarda legal da evidência; trilha append-only da conferência de
alegação, cujo gatilho não olha papel, nem o do dono do banco). A política passou a dizer isso.

---

## C · Testes executados

| Teste | Comando | Resultado | Evidência |
|---|---|---|---|
| Suíte completa (PostgreSQL 16 real, banco do zero) | `python3 -m unittest discover -s tests -t .` | **1.355 testes · 0 falhas · 26 pulados · 484 s** | `docs/evidence/test_run_v0.19.0.log` |
| Glossário (contrato + banco) | `… tests.test_v0190_glossary` | 13 · OK | inclui prova de que o detector reprova |
| Primeiro acesso e retorno de contexto | `… tests.test_v0190_firstrun` | 16 · OK | — |
| Exclusão e retenção (LGPD) | `… tests.test_v0190_lgpd_deletion` | 13 · OK | varredura em todas as colunas de texto |
| Backup e canário de e-mail | `… tests.test_v0190_ops` | 15 · OK | `pg_dump` real, conferido por `pg_restore --list` |
| Lint | `ruff check impacto tests` | All checks passed | — |
| Tipos (web) | `tsc -p tsconfig.offline.json --noEmit` | sem erro | — |
| Build (web) | `node build.mjs` | ok | — |
| Documentação de API | `python3 ../scripts/gen_api_docs.py` | **819 operações** | `docs/openapi.json` |
| Integridade do banco | `python3 scripts/db_integrity_report.py` | 287 tabelas · 36 migrações · 598 políticas · 802 índices | `docs/evidence/db_integrity_v0.19.0.txt` |
| Backup → restauração → migração → validação | `scripts/backup.sh` + `scripts/restore_test.sh` | **restore OK**, com os conferidores novos da camada de operação | `docs/evidence/restore_test_v0.19.0.log` |
| Smoke de publicação (24 verificações) | `scripts/smoke_test.py --base … --email …` | **19 passaram · 0 falharam · 5 puladas · required_failed = 0** | `docs/evidence/smoke_v0.19.0.json` |

**Crescimento da suíte:** 1.298 (v0.18.1) → **1.355** (v0.19.0), +57 testes.

### C1 · Guardas que reprovaram durante a rodada (e que não foram enfraquecidas)

Cinco testes reprovaram na primeira regressão. **Nenhum foi relaxado:**

1. `test_handlers_declare_auth` — rota pública nova exige revisão; a revisão foi feita e a rota entrou
   na lista (`/v1/public/glossary` serve apenas o arquivo versionado de vocabulário).
2. `test_product_dates_are_utc` — defeito real meu, corrigido (B7).
3. `test_system_context_only_in_allowed_modules` — defeito real meu, corrigido movendo o utilitário (B8).
4. `test_the_ip_cannot_be_swapped_for_another_one` — a mensagem do gatilho mudou de propósito; a
   asserção acompanhou o texto, a **recusa continua sendo exigida**.
5. `test_import_json_feed_and_run_once` — `not_configured` é resultado legítimo; o teste ficou **mais
   forte**: além de aceitar o novo estado, passou a exigir zero tarefas falhas e a presença das duas
   tarefas novas no ciclo.

---

## D · Testes NÃO executados, e por quê

| Teste | Motivo | Classificação |
|---|---|---|
| `npm audit`, `pip-audit` | o registry npm responde **403** e o índice do PyPI está indisponível neste ambiente | `BLOCKED_EXTERNAL` — e **não** se escreve "0 vulnerabilidades" |
| `docker build` / `run` / healthcheck | docker não disponível neste ambiente | `BLOCKED_EXTERNAL` |
| axe-core, leitor de tela real, segundo navegador, zoom 200%, daltonismo | pacote indisponível (registry) e ferramentas que exigem pessoa | `BLOCKED_EXTERNAL` / verificação humana |
| Carga com rede real | cliente, API e banco na mesma máquina | medição feita, **não** é capacidade de produção |
| Entrega real de e-mail | exige provedor SMTP com domínio e credencial | `BLOCKED_EXTERNAL` — por isso o estado se chama `accepted_by_smtp` |
| Restauração a partir de cópia externa | não há destino externo configurado | `BLOCKED_EXTERNAL` |

---

## E · DATA_TO_CONFIRM (decisão humana, não técnica)

| # | Item | Quem decide |
|---|---|---|
| E1 | **RPO alvo** (quanto de dado se aceita perder) e se haverá PITR contratado | proprietário |
| E2 | **RTO alvo** (quanto tempo até voltar) e onde fica o ambiente de recuperação | proprietário |
| E3 | Endereço do canário de e-mail (`EMAIL_CANARY_TO`) — caixa monitorada por pessoa | operação |
| E4 | Destino da cópia externa de backup | proprietário |
| E5 | Aprovação jurídica das 11 minutas legais (sem isso o banco recusa aceite, e ninguém se cadastra) | advogado(a) |
| E6 | Regime tributário, município emissor e provedor fiscal | contabilidade |
| E7 | Domínio, certificado e credenciais de SMTP, armazenamento, antivírus, pagamento e IdP | proprietário |
| E8 | Tradução dos termos editoriais do banco para en/es, depois que o design estabilizar a redação | produto |

## F · BLOCKED_EXTERNAL (depende de serviço ou ambiente indisponível aqui)

Auditoria de dependências (registry) · imagem Docker · axe-core · entrega real de e-mail · cópia
externa de backup · carga com rede real · provedores externos em modo produtivo.

## G · DEFER_POST_DESIGN (deliberadamente fora desta rodada)

Mapeamento GRI/ISSB/IRIS+ · decaimento por idade na reputação · detecção de conluio · arte e níveis de
selo · aplicativo móvel · tradução do conteúdo editorial · procedência do preenchimento persistida ·
webhook de entrega de e-mail.

---

## H · Riscos

| Severidade | Risco | Situação |
|---|---|---|
| **CRITICAL** | Vulnerabilidade conhecida em dependência | auditoria **bloqueada**, declarada como bloqueio (C1 do registro de dívida) |
| **CRITICAL** | Nenhum provedor externo real configurado | o produto sobe em modo simulado; `/readyz` **diz qual provedor está ligado** (C2) |
| **CRITICAL** | Minutas legais sem aprovação | o banco recusa aceite de rascunho: cadastro bloqueado em produção, de propósito (C3) |
| **CRITICAL** | Imagem Docker nunca construída aqui | C4 |
| **CRITICAL** | Observabilidade sem coletor | C5 |
| **CRITICAL** | Carga medida só na mesma máquina | C6 |
| **CRITICAL** | **Cópia externa de backup ausente** (novo) | o backup roda e é conferido, mas fica no mesmo host (C7) |
| **CRITICAL** | **RPO/RTO alvo não decididos** (novo) | o que a configuração entrega está escrito; o que o negócio aceita, não (C8) |
| **HIGH** | Seis telas da camada v0.18.0 não existem | é o trabalho da próxima fase; declaradas uma a uma (H6) |
| **HIGH** | Entrega de e-mail não confirmada pelo provedor | o vocabulário já não mente (H9) |
| **MEDIUM** | Metas oficiais dos ODS e dados do IBGE não carregados | declarado na interface (H1) |
| **LOW** | Tradução do conteúdo editorial | declarado em `locales.coverage_note` (H8) |

---

## I · Matriz final de portões

| Portão | Situação | Evidência | Bloqueador |
|---|---|---|---|
| Arquitetura | **PASSA** | 20 testes arquiteturais, inclusive os que reprovaram e foram corrigidos | — |
| Banco | **PASSA** | 287 tabelas, 36 migrações, 598 políticas, 802 índices | — |
| PostgreSQL real | **PASSA** | 1.355 testes contra banco do zero | — |
| Segurança | **PASSA** | isolamento entre organizações, RLS, MFA, limites | — |
| LGPD | **PASSA** | exclusão ponta a ponta + varredura de todas as colunas de texto | — |
| Equidade | **PASSA** | 30 testes; UNKNOWN ≠ ZERO | — |
| ODS | **PARCIAL** | escada alinhado→auditado respeitada | metas oficiais não carregadas |
| ESG / materialidade | **PASSA** | dupla materialidade, sem virar selo | — |
| Evidência | **PASSA** | reportado × validado separados por CHECK | — |
| Alegação | **PASSA** | 12 regras determinísticas, revisão por convite | — |
| Match | **PASSA** | explicável, sem dependência de cobrança (guarda por AST) | — |
| Diagnóstico | **PASSA** | 8 prontidões rastreáveis | — |
| Reputação | **PASSA** | sem nota única; sem valor sem base | — |
| Selo | **PASSA** | critério conferido em SQL; app sem INSERT | — |
| Formulário inteligente | **PASSA** | origem em toda sugestão; nunca sobrescreve | — |
| Responsabilidade | **PASSA** | mandato, quatro-olhos, separada de assinatura | — |
| Assinatura | **PASSA** | ligada a documento e versão | — |
| Cobrança | **PASSA** | isolada do match, do impacto e da reputação | — |
| Pagamento | **BLOQUEADO** | arquitetura pronta | provedor real (E7) |
| Fiscal | **BLOQUEADO** | motor de regra pronto | provedor e regime (E6) |
| Segurança de IA | **PASSA** | IA sem autoridade sobre operação crítica | — |
| E2E | **PASSA** | jornada de 18 passos, sem atalho de banco | — |
| **Vocabulário** | **PASSA** | 123 termos, conferência nas duas direções | — |
| **Primeiro acesso** | **PASSA** | 12 áreas, todas com motivo e próximo passo | — |
| Acessibilidade | **PARCIAL** | 12 verificações no navegador | axe e leitor de tela (F) |
| Desempenho | **PARCIAL** | carga medida | mesma máquina (C6) |
| **Backup** | **PASSA** | agendado, executado e conferido | cópia externa (C7) |
| **Restauração** | **PASSA** | ciclo completo + conferidores da camada de operação | — |
| **E-mail** | **PASSA** | registro por tentativa; canário | entrega real (F) |
| Observabilidade | **PARCIAL** | `ops_job_runs`, `email_events`, `/v1/admin/ops/health` | coletor (C5) |
| Dependências | **BLOQUEADO** | saída de erro dos dois comandos registrada | registry (F) |
| Produção | **PARCIAL** | runbook com RPO/RTO e canário | credenciais (E7) |
| Git | **PASSA** | ver §J | — |
| ZIP | **PASSA** | ver §J | — |

---

## J · Git e pacote

| | |
|---|---|
| Ramo | `chore/v0.19.0-vocabulary-firstrun-ops` |
| Commit do trabalho | `d6306a821ffb2b56cf960865c4c388709f250f8d` |
| Árvore de trabalho | limpa após o commit de fecho |
| Manifesto de arquivos | `V0.19.0_FINAL_MANIFEST.json` — 1.046 arquivos, 28 categorias, 20,69 MB |
| Manifesto de release (§59) | `FINAL_RELEASE_MANIFEST.json` |
| Pacote | `IMPACTO_v0.19.0_VOCABULARY_FIRSTRUN_OPS.zip` |

**Sobre o sha256 do pacote:** um ZIP não pode conter o próprio hash. Ele é calculado depois do
empacotamento, informado na entrega e conferível por `python3 scripts/make_release.py --verify DIR`
contra o `RELEASE_MANIFEST.sha256` que vai dentro do pacote — que é a conferência que importa, porque
cobre **cada arquivo**, e não só o invólucro.

**Nada de segredo no pacote:** o empacotador recusa `.env` real, chaves, tokens e dumps; `unzip -t`
confere a integridade; e não há ZIP dentro de ZIP.

---

## K · Autocrítica — onde um auditor externo procuraria

Procurei de novo, nesta ordem, e o que encontrei está acima: vazamento entre organizações (teste de
isolamento no primeiro acesso), verificação falsa (nenhum selo concedido sem critério conferido em
SQL), reputação falsa (comparação antes/depois de declarar contexto), alegação sem evidência (12
regras), nota sem confiança (CHECK no banco), exclusão que quebra auditoria (a trilha sobrevive e foi
provada), **backup que nunca roda** (era verdade — corrigido), **e-mail que falha em silêncio** (era
verdade — corrigido), **enum sem tradução** (era verdade — corrigido), estado vazio quebrado (o
contrato é testado), migração inconsistente (36 aplicadas em banco do zero e em atualização com
dado), corrida (9 testes), webhook duplicado (idempotência testada), segredo vazado (varredura no
empacotador), escalada de privilégio por IA (IA sem autoridade), configuração de produção ausente
(`/readyz` declara provedor por provedor).

O que **não** consegui procurar está em §D, com o motivo, e não foi convertido em aprovação.
