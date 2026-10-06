# Changelog
Formato Keep a Changelog. Histórico anterior (v0.1–v0.6): `history/v0.6.0/CHANGELOG.md`; snapshot dos documentos do v0.7.0: `history/v0.7.0/`.

## [0.19.0] — 2026-10-06 — VOCABULÁRIO, PRIMEIRO ACESSO E OS GATES DE PUBLICAÇÃO (snapshot do v0.18.1 em `history/v0.18.1/`)

Rodada de fechamento ANTES da camada de design. Seis itens: três que, se não fossem feitos antes,
fariam o trabalho de design ser refeito; três que fariam a publicação falhar em silêncio. Em todos,
o padrão foi o mesmo — executar o que nunca havia sido executado e corrigir o que apareceu.

### 1. Vocabulário oficial (o item que mais muda o trabalho de quem desenha)
- **`config/glossary.json` passa a ser a ORIGEM do rótulo**: 123 termos em 23 domínios, 369 rótulos
  nos três idiomas, mais a definição em pt-BR de cada termo. ADR-228.
- **Três cópias do mesmo vocabulário foram unificadas**: dicionários em doze módulos Python, uma
  cópia em TypeScript dentro de `web/src/pages/core.tsx`, e nada no catálogo de tradução. O catálogo
  passou de 98 para **221 chaves por idioma** (6 → 29 namespaces).
- **`scripts/sync_glossary.py`** gera, de uma só origem: os namespaces `g_*` de `config/i18n.json`
  (e daí a tabela `translations` e `GET /v1/public/translations`), o `GLOSSARY.md` e o
  `web/src/glossary.ts`, que a interface agora **consome** em vez de copiar. `--check` reprova fora
  de sincronia.
- **Nova rota `GET /v1/public/glossary`**: termo da API, rótulo no idioma pedido, definição em pt-BR.
- **A conferência roda nas duas direções** (`core/glossary.py`): cada domínio declara DE ONDE saem os
  valores vivos (atributo Python, coluna de migração, varredura de código). Valor de enum sem rótulo
  reprova; rótulo órfão reprova. Um dos 13 testes adultera o documento em memória de propósito, para
  provar que a guarda não é decorativa. ADR-229, ADR-230.

### 2. Primeiro acesso
- **Nova rota `GET /v1/firstrun`**: por área, o que é, por que está vazia, qual é o próximo passo, o
  que se ganha ao completar, o que é obrigatório, o que é opcional, de onde vem o dado e como se
  verifica — tudo a partir de **contagem real no banco**, nunca de valor de exemplo. ADR-231.
- **Seis áreas da camada v0.18.0 não têm tela** (equidade, ODS, alegação, reputação, selo,
  responsabilidade): são declaradas como `to_be_designed` em vez de apontarem para link morto. É o
  inventário que a camada de design recebe. ADR-232.
- **Área sem projeto escolhido devolve `counted: false`, não zero.** ADR-233.
- `EmptyArea` e `FirstRunPanel` em `web/src/ui/kit.tsx`, montados no painel inicial: referência de
  como o contrato se desenha, com hierarquia (motivo antes do botão) que resiste à reestilização.

### 3. Retorno por declarar contexto
- **Nova rota `GET /v1/projects/{id}/context-return`** com oito chaves de retorno OPERACIONAL:
  cobertura declarada peça por peça, métodos de normalização disponíveis, explicabilidade do match,
  prontidão de evidência, prontidão de selo (critério por critério, com o mesmo cálculo da
  concessão), prontidão de diagnóstico, o que um financiador vê, e o que trava elegibilidade por
  falta de dado.
- **Nenhum ganho de ranking ou de reputação**, declarado no payload e provado por teste que compara
  os retratos de reputação antes e depois de declarar contexto. ADR-234.

### 4. Exclusão de conta e retenção (LGPD)
- **A plataforma NÃO remove organização — ela fecha.** As cascatas da camada nova estavam declaradas
  nas migrações e nunca haviam sido executadas; ao executar, a remoção é recusada duas vezes (guarda
  legal da evidência, e trilha append-only da conferência de alegação). A política passou a dizer
  isso, com a classe `append_only`. ADR-236.
- **13 tabelas append-only em todo o sistema foram DESCOBERTAS pela conferência automática** e não
  tinham política que as reconhecesse (`billable_events`, `credential_verifications`,
  `diagnosis_versions`, `domain_events`, `eligibility_evaluations`, `equity_assessments`,
  `match_feedback`, `price_change_notices`, `project_snapshots`, `project_transitions`,
  `readiness_snapshots`, `trust_events`, `value_events`).
- **`config/data_retention.json` + `core/retention.py` + `DATA_RETENTION.md`** (gerado contra o banco
  real): 184 vínculos a organização ou titular, 58 declarados, classe declarada conferida contra a
  regra real da chave e contra o gatilho. Declarar uma coisa e o banco fazer outra reprova.
- **Varredura de verdade**: depois da exclusão, o e-mail do titular é procurado em TODAS as colunas
  de texto de TODAS as tabelas, numa só consulta (erro em laço com `try/except` abortaria a
  transação e esconderia justamente o que importa).

### 5. Backup agendado
- **`scripts/backup.sh` existia desde a v0.7.0 e NADA o executava.** O agendamento passou a viver no
  executor de tarefas que já existe, com janela própria. ADR-238.
- Conferência do dump em três níveis: tamanho, sha256 contra o arquivo `.sha256` gravado, e
  `pg_restore --list` (que pega o caso do arquivo que existe, tem tamanho e não é um backup válido).
- Poda com retenção (`BACKUP_KEEP`), cópia externa por comando configurável (`BACKUP_OFFSITE_CMD`) e
  recusa em declarar recuperação de desastre sem ela.
- **A janela conta do último SUCESSO, não da última tentativa.** ADR-239.

### 6. Canário de e-mail e observabilidade de envio
- **Nova tabela `email_events`**: um registro por tentativa, com identificador da mensagem, tipo,
  **domínio** do destinatário (nunca o endereço, nunca o corpo), provedor, número de tentativas,
  duração e erro. O registro é ligado **no mailer**, não nos oito pontos que enviam e-mail. ADR-242.
- **O estado de sucesso se chama `accepted_by_smtp`, nunca `delivered`**: a plataforma não recebe
  retorno de entrega do provedor, e o CHECK do banco não aceita um estado chamado entrega. ADR-241.
- **Tarefa `email_canary`** com endereço de monitoramento configurável.
- **Nova rota `GET /v1/admin/ops/health`**: última execução de cada tarefa, com veredito, e falhas de
  e-mail na janela. O estado `not_configured` é registrado como tal, nunca como ausência de linha.
  ADR-240.

### Corrigido (defeitos reais, achados por teste nesta rodada)
- **`project_ods_targets` era anunciado com o método errado** (`POST` em vez de `PUT`) e
  **`match_runs.org_id` não existe** (é `viewer_org_id`): os dois foram pegos pelo teste que exige que
  toda rota de próximo passo esteja registrada no roteador — o segundo causava erro 500.
- **Denominador de um projeto vazava para os outros projetos da mesma organização** na primeira versão
  da rota de retorno: a disponibilidade passou a sair da mesma função que o cálculo usa. ADR-235.
- **O gatilho da prova de aceite recusava o `SET NULL` que a própria chave promete** (migração 0035),
  tornando impossível remover organização com um único aceite registrado. E a regra de IP confundia
  "não pode trocar" com "tem de ficar sem IP" — a primeira versão da correção ainda quebrava. ADR-237.
- `web/src/pages/core.tsx` tinha uma terceira cópia de `BAND_LABEL`; passou a importar do glossário.

### Banco
- `0035_v0190_acceptance_org_anonymization.sql` — gatilho da prova de aceite.
- `0036_v0190_ops_observability.sql` — `ops_job_runs` e `email_events`, com RLS restrita à
  administração da plataforma.

### Configuração nova (todas opcionais; sem elas a tarefa registra `not_configured`)
`BACKUP_DIR`, `BACKUP_DATABASE_URL`, `BACKUP_INTERVAL_HOURS`, `BACKUP_KEEP`, `BACKUP_OFFSITE_CMD`,
`EMAIL_CANARY_TO`, `EMAIL_CANARY_INTERVAL_MINUTES` — documentadas em `.env.example`.

## [0.18.1] — 2026-10-06 — ENDURECIMENTO TÉCNICO FINAL E CONGELAMENTO DA BASE (snapshot do v0.18.0 em `history/v0.18.0/`)

Rodada de **prova**, não de funcionalidade. O proprietário entregou um pacote
`IMPACTO_v0.18.0_CORE_HARDENED.zip` produzido fora desta sessão, com quatro reforços de núcleo que
**não puderam ser executados contra PostgreSQL real** onde foram escritos. Esta versão integrou
aqueles reforços, rodou-os contra o banco real e encontrou o que só aparece com banco e com um
terceiro na frente.

### Integrado do pacote recebido
- **Sinal contextual de impacto no match** (`engines/match/context.py`): necessidade, barreiras,
  infraestrutura, adicionalidade, sustentabilidade e evidência, com cobertura declarada e `None`
  (UNKNOWN) quando falta contexto.
- **Oito prontidões no diagnóstico** (`READINESS_MAP`), cada uma com situação, nota e lacunas.
- **Proveniência por campo** na montagem de documento (`USER_PROVIDED` / `SYSTEM_DERIVED`).
- **Série longitudinal por indicador**, separando reportado de validado, sem afirmar causalidade.

### Corrigido (defeitos reais, achados nesta rodada)
- **O sinal contextual estava morto para todo terceiro.** Quem pede o match é o financiador, e a RLS
  das tabelas de equidade — corretamente — só devolve linha para a organização dona. Nova função
  `project_impact_context()` (migração 0034), `SECURITY DEFINER`, devolve **apenas números**, nunca
  a narrativa, e **nada** para projeto não publicado. ADR-221.
- **A "referência neutra" de 0,5 premiava quem não declarava contexto**: projeto com contexto
  declarado e nota baixa ficaria atrás de projeto sem contexto nenhum. Sinal ausente voltou a ser
  UNKNOWN, reduzindo cobertura e confiança (ADR-026). ADR-222.
- **Prazo sem fuso horário devolvia 500.** `closes_at: "2026-12-05"` — o que um seletor de data
  produz — quebrava no driver. Agora é **422 com exemplo**, e a plataforma continua sem adivinhar
  fuso: 23h59 em Rio Branco não é o mesmo instante que 23h59 em Brasília. ADR-223.
- **"Erradicamos" passava como alegação sustentada.** Havia uma medição validada no projeto, e isso
  bastava para a regra de linguagem absoluta. Nasceu a **12ª regra**,
  `totality_claim_without_coverage` (migração 0033): totalidade exige denominador vigente com fonte
  **e** cobertura medida ≥ 99%, e a mensagem diz a cobertura real. ADR-224.
- **Cabeçalho `Server: uvicorn`** no harness de teste (produção já usava `--no-server-header`):
  o servidor de teste passou a subir igual, e o Nginx ganhou `server_tokens off` +
  `proxy_hide_header Server`.
- **Três alvos de toque com 21–23 px** em 390 px (WCAG 2.2 AA 2.5.8): link solto, atalho de
  conteúdo e ação de painel passaram a ter 24 px mínimos.
- **Série longitudinal sem declarar a janela**: `window`, `total_known` e `window_truncated`
  entraram no payload — série truncada sem aviso é série que mente de boa-fé.

### Acrescentado (prova)
- `test_v0181_concurrency.py` (9): corrida real em designação, denominador, rodada de verificação,
  concessão de selo, retrato de reputação, transação abortada e savepoint.
- `test_v0181_migrations.py` (8): atualização v0.17.0 → v0.18.x **com dado dentro**, checksum
  forward-only e migration que falha no meio.
- `test_e2e_v0181_journeys.py` (18): a jornada completa, 18 passos, um projeto, uma trilha.
- `scripts/smoke_test.py` (20 verificações) + `test_v0181_smoke.py` (5).
- `test_v0181_hardening.py` (16): a função agregada (inclusive o que ela **não** devolve), a regra
  de totalidade e os controles de dependência verificáveis offline.
- `test_e2e_v0181_accessibility.py` (13): acessibilidade no navegador, contraste calculado nos dois
  temas, teclado, foco, marcos, 390 px e movimento reduzido.
- `scripts/loadtest.py` estendido às rotas da camada de impacto, com o tipo de organização correto
  por rota.
- `restore_test.sh` com seis conferidores novos da camada de impacto.

### Declarado como bloqueado (e não como aprovado)
- **`npm audit` e `pip-audit` não executaram**: registry npm devolve `403 Forbidden` e o índice PyPI
  não responde. A saída de erro está em `SECURITY_AUDIT.md` §0, classificada
  **BLOCKED BY ENVIRONMENT**. Nenhuma afirmação sobre CVE é feita nesta versão.
- **`axe-core` e leitor de tela**: NOT VERIFIED, com o motivo, em `ACCESSIBILITY_REPORT.md` §2.
- **Docker, coletor de métricas e carga fora da máquina do banco**: condições do GO de publicação,
  listadas em `TECHNICAL_BASELINE_LOCK.md`.

### Entregas de documento
`TECHNICAL_BASELINE_LOCK.md` (as duas decisões), `REQUIREMENTS_MATRIX.md` (reconciliação histórica
com classes A–I), `TECHNICAL_DEBT_REGISTER.md`, `PRODUCTION_RELEASE_RUNBOOK.md`,
`ACCESSIBILITY_REPORT.md`, `DESIGN_HANDOFF_FINAL.md` reescrito para esta baseline.

**Suíte: 1.223 → 1.298 testes verdes, 26 em passo próprio. ADR-221 a ADR-227.**

## [0.18.0] — 2026-10-06 — IMPACTO CONTEXTUALIZADO: EQUIDADE, REFERENCIAIS E CONFIANÇA (cumulativo; snapshot do v0.17.0 em `history/v0.17.0/`)

A v0.17.0 havia declarado DESIGN como a próxima fase. Esta rodada reordena outra vez, pela mesma razão da anterior:
**o que o design vai representar ainda estava sendo decidido.** Uma tela de "impacto" desenhada antes de existir o
modelo de equidade desenharia o número errado com capricho.

A tese que a rodada implementa: **impacto não é quantidade; impacto é resultado contextualizado.**

### Adicionado
- **Motor de equidade e contexto** (`equity_contexts`, `equity_denominators`, `equity_barrier_catalog`,
  `project_barriers`, `equity_assessments`): sete métodos de normalização, cada um declarando o denominador que
  exige; **sem denominador com fonte, data e método, nenhum método está disponível** (a resposta é "indisponível"
  com o motivo, nunca uma estimativa); a avaliação **não produz nota**; `compare()` devolve `comparable: false` com
  os motivos e **nunca um veredito**. Escada de prova das barreiras: declarada → documentada → com evidência.
  ADR-191 a ADR-193.
- **Território como catálogo** (`territories`, `determinant_indicator_defs`, `territory_indicators`) com
  `from_official_load` separando carga oficial de conhecimento da plataforma — as 27 UFs semeadas dizem, na própria
  linha, "conhecimento da plataforma; conferir na carga oficial". `territory_profile()` devolve **toda** definição
  ativa com `measured` booleano: território sem dado aparece como sem dado. Dois importadores que exigem fonte, URL
  e data, e recusam o arquivo inteiro se uma linha for inválida. ADR-194.
- **Registro de 19 referenciais de impacto** (`impact_frameworks`) — 4 em uso, 7 mapeáveis, 8 só registrados, cada
  um destes com `license_note` dizendo por que não é mapeado — e **mapeamento de indicador** (`framework_mappings`)
  com escada de seis degraus: `aligned`, `mapped`, `assessed`, `reported`, `verified`, `audited`. **`certified` é
  recusado por gatilho**: a plataforma não é organismo certificador. `coverage()` responde "consigo relatar?" com
  número. ADR-195.
- **Materialidade** (`materiality_topics`, `materiality_assessments`, `materiality_entries`) com as três lentes
  (impacto, financeira, dupla), limiar declarado e `is_material` **derivada** por `materiality_derive()` — nunca
  escrita. ADR-196.
- **Integridade de alegação** (`claims`, `claim_rules`, `claim_checks`, `claim_review_requests`, `claim_reviews`):
  11 regras **determinísticas** (consulta SQL e léxico declarado em código, com `CHECK rules_are_deterministic`), o
  léxico **público** na rota do catálogo, e a situação **derivada** por `claim_status()` — **não existe coluna de
  situação em `claims`**, de propósito. O verificador devolve `attention`/`serious` e **nunca "fraude"**; alegação
  marcada exige revisão humana de OUTRA organização, **por convite nomeado**, e aceitar produz
  `flagged_accepted_by_review`: a marca é qualificada, não apagada. ADR-197 a ADR-200.
- **Reputação explicável** (`reputation_dimensions`, `reputation_snapshots`, `reputation_disputes`,
  `reputation_dispute_resolutions`): seis dimensões, **sem nota única** — divergência consciente dos prompts, porque
  nota única vira ranking e ranking vira critério de acesso. Dimensão sem base suficiente **não tem valor**
  (organização nova começa sem medida, não com nota baixa); órgão público recebe **perfil de governança e
  transparência** sem nota; pessoa física **não tem perfil público**; nenhum sinal comercial entra (varredura AST);
  contestação **aparece no perfil** e correção gera **ponto novo** em vez de reescrever o antigo. ADR-201 a ADR-206.
- **Motor de selos** (`seal_rules`, `seal_definitions`, `seal_criteria`, `seal_awards`, `seal_revocations`,
  `seal_evaluations`): o critério é avaliado **em SQL** (`seal_evaluate()`), e `app_award_seal()` o reavalia antes de
  inserir — **a aplicação não tem INSERT em `seal_awards`**, então nenhuma rota concede selo sem critério. Definição
  **versionada e imutável** depois de publicada, validade igual ao **menor** prazo entre definição e critérios,
  revogação como **fato novo**, avaliação recusada **também registrada** ("por que eu não recebi"), e **zero
  definições embarcadas**. ADR-207 a ADR-211.
- **Busca incremental com procedência** (13 buscas) e **componente de autocomplete** que mostra a origem de cada
  sugestão (carga oficial ≠ conhecimento da plataforma ≠ lista editorial ≠ histórico da própria organização) e
  **nunca sobrescreve** em silêncio o que a pessoa escreveu: pergunta, mostra a origem e oferece voltar. Formulário
  em etapas que **não esconde trabalho já feito**. ADR-212 a ADR-215.
- **Responsabilidade designada** (`responsibility_roles`, `responsibility_assignments`,
  `responsibility_decision_kinds`, `responsibility_decisions`): responsável × papel × escopo × período × decisão ×
  **versão**, **separada da assinatura**. Designação não é reescrita, encerrar exige motivo, decisão fora do período
  é recusada, decisão sobre documento aponta para a **versão**, quatro-olhos é declarado em dado e exige **pessoas**
  diferentes, e pessoa externa entra por **nome, sem CPF**. ADR-216 a ADR-220.

### Corrigido
- **Linha de base de indicador sem fonte** passava no banco (dívida herdada da v0.17.0, onde a trava existia só para
  programas): `project_indicator_baseline_source()` passou a recusar, a API recusa antes do banco com
  `baseline_source_required`, e a visão `project_baselines_without_source` torna a dívida **contável** em vez de
  silenciosa.
- **Valor de reputação publicado com faixa de confiança insuficiente**: havia observações bastando e verificação por
  terceiro baixa, e o perfil publicava número que a própria faixa dizia não sustentar. A restrição
  `insufficient_has_no_value` recusou a gravação; **corrigiu-se o cálculo, não a restrição**.
- **A recusa de selo desfazia o registro da própria recusa**: a exceção dentro da função levava embora o
  `seal_evaluations` recém-inserido. A função passou a devolver `NULL` e o 422 é levantado **fora** da transação.
  ADR-208.

### Segurança e privacidade
- RLS e política em **todas as 33 tabelas novas**, com inventário declarado das que têm leitura aberta **de
  propósito** e o motivo de cada uma.
- **Nenhuma coluna de CPF, RG ou documento** nas tabelas desta rodada (teste lê `information_schema`); a única
  coluna de nome de pessoa é `responsibility_assignments.external_name`, sem documento ao lado.
- Trilhas append-only sem `UPDATE` nem `DELETE` para o papel da aplicação; escrita por função `SECURITY DEFINER`
  onde a invenção de dado seria possível (`app_record_reputation`, `app_award_seal`).
- Testes de **viés** (projeto pequeno e território remoto não são penalizados; reputação é proporção, não volume;
  organização nova não começa com nota baixa) e de **gaming** (alegação não verificada não conta; retirar alegação
  marcada não limpa o registro; autovalidação recusada; revisão sem convite recusada; selo não autoconcedido;
  denominador mínimo não fabrica veredito).

### Não entregue, com nome
- **169 metas oficiais dos ODS** e **dados do IBGE**: a rede do ambiente alcança só registros de pacote. Estrutura e
  importadores entregues; o dado entra quando houver o arquivo.
- **Mapeamento para GRI, ISSB e IRIS+**: depende de decisão de produto **e** jurídica, porque as minutas legais da
  v0.17.0 excluem expressamente esses relatórios.
- **Nenhuma definição de selo publicada** e nenhuma arte de selo.
- **Decaimento por idade nas dimensões de reputação**: observação de três anos pesa como a de ontem.
- **Detecção de conluio**: duas organizações que validam medições uma da outra sobem nas dimensões; o sinal existe
  no banco desde a v0.8.0, a detecção não.

## [0.17.0] — 2026-10-06 — CAMADA ECONÔMICA, LEGAL E DE PAGAMENTO (cumulativo; snapshot do v0.16.0 em `history/v0.16.0/`)

Esta rodada inverte a ordem do roteiro a pedido do proprietário: **monetização, pagamento e auditoria legal vêm
ANTES do design.** A tese que ela implementa é uma só — **o proponente não pode ser o pagador principal** — e a
consequência é que cadastro, perfil, projeto, descoberta, rede e acompanhamento básico são gratuitos e permanecem
gratuitos (ADR-173, que muda a regra comercial da v0.16.0).

### Adicionado
- **Programa como entidade de primeira classe** (`programs` + chamadas, carteira, indicadores e necessidades):
  a unidade com que instituto, fundação e secretaria pensam o próprio dinheiro, e o que torna o institucional
  vendável. Situação é grafo no banco (11 arestas); `objective` é obrigatório; linha de base de indicador exige
  fonte. Três funções separam o que foi declarado do que foi medido: `program_financials()` (gasto ≠ comprovado),
  `result_chain()` (força declarada de cada elo, sem promover hipótese a evidência) e `territorial_gap()` (com a
  qualidade da evidência por território). ADR-174.
- **Value Ledger** (`value_events`, 11 tipos com o campo `what_counts`): o registro do que a Plataforma entregou,
  **separado** do registro do que ela cobrou. A aplicação **não tem INSERT** na tabela — só `app_record_value()`,
  `SECURITY DEFINER` — então a estimativa de tempo nunca pode ser passada como parâmetro. Nenhuma linha de base
  nasce com número, e o evento fica `no_baseline` até alguém declarar o número com fonte, data e método.
  ADR-175/176.
- **Monetização com portão legal** (`monetization_rules`, `monetization_legal_cards`, `billable_events`): nove
  regras cadastradas, **zero verdes, nenhuma ativa**. `monetization_rule_gate()` recusa ativar receita sem cartão
  legal verde; `green_needs_evidence` recusa verde sem fonte citada, porque ausência de proibição não é permissão.
  `problem_solved` e `substitution_answer` são NOT NULL: regra que não diz qual problema caro resolve não entra no
  banco. ADR-177.
- **Arquitetura de pagamento da Plataforma** (`platform_charges` e companhia), com **PRODUCTION PAYMENT NOT
  CONFIGURED** em todas as respostas porque é o estado verdadeiro: cartão avulso, cartão recorrente, **parcelamento
  modelado à parte da assinatura** (soma das parcelas conferida no COMMIT por `CONSTRAINT TRIGGER`), PIX e boleto.
  Máquina de estados de 27 arestas, trilha escrita por gatilho `SECURITY DEFINER`, webhook idempotente com
  contagem de reentrega. ADR-180 a 185.
- **Onze documentos legais versionados** (`legal_documents`), oito deles novos — Assinatura, Marketplace,
  Intermediação, Pagamento, Cancelamento, Reembolso, B2B e B2G —, escritos a partir do que o software FAZ e com uma
  seção de perguntas abertas para o jurídico em cada um. A migração é **gerada** de `docs/legal/*.md`, e há teste
  que recalcula o sha256 dos arquivos e compara com o banco. ADR-186.
- **Aceite com prova**: documento, versão, **sha256 do texto aceito** (copiado pelo gatilho, nunca informado pelo
  cliente), titular, data e origem. Versão nova é linha nova e texto de versão é imutável, então o aceite de ontem
  continua provando o texto de ontem.
- **Registro de motores operacionais** (`engines/registry.py`, `GET /v1/engines`, `docs/AI_ENGINES.md`): 28 motores
  declarados com o que produzem e **o que nunca decidem**, e cinco testes que tornam a declaração verificável —
  entre eles a varredura que impede uma chamada nova ao modelo entrar de carona. 23 determinísticos, 2 que
  respondem por extração do conteúdo cadastrado (`ai_used: false`) e 3 que chamam modelo sobre base determinística.
  ADR-189.
- **Job `payment_deadlines`**: PIX e boleto vencidos fecham pela transição do grafo.
- **Retenção nova**: corpo de webhook esvaziado após 18 meses (o evento fica, por idempotência) e IP de aceite
  vencido apagado.

### Alterado
- **Moeda padrão de cobrança passou a BRL** (era USD), e `config/plans.json` foi para `plans@2.0` com o plano
  `osc_basic` renomeado "OSC — gratuito".
- **`GET /v1/legal/{doc}`** passou a servir do registro versionado e a declarar a situação do documento no
  cabeçalho. Até a v0.16.0 ela se chamava "textos legais VIGENTES" e nenhum deles estava vigente.
- **O caminho de webhook da v0.11.0** passou a registrar `signature_verified` e a contar reentrega.
- **A portabilidade de dados** (`/v1/privacy/export`) passou a incluir a prova de aceite, com o hash.

### Corrigido
- **Receita inexistente no relatório**: a apuração classificava fatura como real pelo **nome** do provedor, e os
  cenários da v0.11.0 gravam `provider='stripe'` com chave falsa — apareciam R$ 396,00 que não existem. Sem
  provedor configurado, nenhuma fatura conta como real. ADR-182.
- **Comentário citando função que nunca existiu** (`services/solutions.refine_with_ai`) em
  `engines/solutions/intent.py`: referência órfã em comentário vira prova documental falsa no dia em que alguém a
  lê como implementada.
- **`VALUE_LEDGER.md` afirmava que a tabela de linhas de base nasce vazia.** Ela nasce com uma linha por tipo e
  **sem número** — a diferença importa, e o teste que confere documentos contra o banco pegou o erro.
- **Teste de índice que exigia ausência de varredura sequencial sem olhar o tamanho da tabela**: varredura
  sequencial em 150 linhas é o planejador acertando. ADR-190.

### Segurança e LGPD
- Revisão das 22 tabelas novas lida do catálogo do PostgreSQL: todas com RLS e política, nenhuma com DELETE
  injustificado para a aplicação, `value_events` e `charge_events` sem INSERT para a aplicação.
- **O conflito entre prova append-only e direito de eliminação** foi resolvido estreitando o append-only:
  `acceptance_anonymize_only()` permite exatamente apagar IP e agente de usuário, e o GRANT de coluna recusa antes
  ainda. A prova sobrevive sem eles. ADR-188.
- Matriz de isolamento por tabela e por linha, com o teste par que falha se o filtro do próprio teste não achar nada.

### Desempenho
- Caminhos novos medidos na escala cheia: feed de programas 40 ms, resumo de valor 12–13 ms, cobranças 14–20 ms,
  registro legal 40–43 ms; `platform_revenue()` 5–8 ms varrendo 10.000 cobranças.
- **Regressão declarada**: o feed do financiador foi de 1.508–1.724 ms para **1.874–2.041 ms** com a mesma consulta,
  e a folga até o orçamento caiu de 1,5× para 1,2×. Os carregadores em lote deixaram de ser opcionais.

### Não entregue, e por quê
- **Nenhuma receita está ativa** — falta parecer jurídico para as cinco amarelas; quatro são recusadas.
- **Nenhum aceite é registrável** — nenhuma das onze minutas foi revisada por advogado(a).
- **Nenhum provedor de pagamento configurado** — não há conta, chave nem identificador de preço.
- **Sem nota fiscal, sem SLA, sem assinatura qualificada, sem integração governamental.**
- **FASE 15 (deploy) e 16 (teste de fumaça em produção) não são executáveis neste ambiente**: não há domínio,
  credencial nem saída de rede além dos registros de pacote.

## [0.16.0] — 2026-10-05 — IMPACT NETWORK CORE (cumulativo; snapshot do v0.15.0 em `history/v0.15.0/`)

Esta rodada transforma o produto de "plataforma de projetos" em **infraestrutura de conexão, estruturação,
financiamento, execução, acompanhamento e comprovação de impacto** — com **um núcleo** e experiências por papel, não
quatro aplicações.

### Adicionado
- **Grafo de impacto como entidade relacional** (`relationships`): **uma** tabela de aresta, 22 tipos, 5 níveis de
  visibilidade, máquina de estados própria, espelho das relações antigas (seguir, favoritar, bloquear) por gatilho.
  Travessia até profundidade 2 por CTE recursiva — **15 ms** medidos na escala cheia, que é a razão documentada de
  **não** adotar banco de grafos (ADR-141).
- **Motor de propostas** (`proposals`): 9 tipos, 10 situações, grafo de transições como dado, versão, anexos, trilha
  de eventos, reenvio, expiração por prazo. **Proposta ≠ contrato ≠ investimento ≠ pagamento** — aceitar cria
  relação e, quando o tipo é financeiro, **intenção**; nunca "investido".
- **Marketplace de impacto** (`marketplace_listings`): 7 situações, `publication_status`, e **um único** lugar que
  filtra o que é público (`PUBLIC_STATES = ("published",)`). Anúncio só vai ao ar se o projeto também estiver
  publicado — recusado no gatilho, não na rota.
- **Mensagem com contexto obrigatório**: conversa profissional nasce **referenciando** proposta, projeto, anúncio ou
  relação. Não há "abrir conversa" solto quando a relação é profissional.
- **Notificação para toda a equipe envolvida**: 14 grupos, 4 prioridades (`low`/`normal`/`high`/`critical`), fan-out
  por `project_team()` e `notify_org_members()`, idempotência por `dedupe()` (sha256), rótulo de ação e destino em
  cada aviso. **Um fato, um aviso por pessoa.**
- **Prontidão de impacto** (`readiness@1.0.0`): 6 dimensões (documentos, projeto, financiamento, governança,
  execução, evidência), cada verificação com explicação e o que falta. Nota **nunca** sem porquê.
- **Recomendação ≠ Match** (`recommendation@1.0.0`): 19 ações com razão, destino e prioridade, calculadas sobre o
  estado real. O motor de match da v0.9.0 **não foi tocado**.
- **Workspace por persona** (não "dashboard por perfil"): 10 personas, 24 seções ordenadas pelo servidor, 15
  capacidades. `WorkspaceContext` devolve **próximas ações com destino e razão**, numa chamada.
- **Perfil público `impacto.app/@identificador`**: projeção curada (`public_fields`), lista fechada de 18 campos
  projetáveis, lista do que **nunca** é público, e `_assert_no_private()` que falha na gravação. A página pública
  **não consulta nenhuma tabela privada**. Histórico de identificadores, identificadores reservados.
- **Ciclo de relatório de impacto** (`impact_updates`): 6 situações, quem revisa ≠ quem escreveu (CHECK no banco),
  campo de **limitações** de primeira classe, e os números **colhidos pelo banco** (`app_impact_metrics()`), não
  digitados.
- **Escada de moderação de 10 degraus** com severidade declarada, `MAX_JUMP = 2`, regra e motivo obrigatórios, prazo
  obrigatório nas medidas temporárias, contestação julgada por quem não aplicou, e **nada automático**. 12 categorias
  de denúncia. A identidade de quem denuncia nunca chega ao alvo.
- **Separação financeira em três estágios**: intenção (`investment_intents`) → compromisso (`commitments`) →
  transação (`payments`). Teste de invariante impede somar os três num número só.
- **Necessidades de território** (`territory_needs`) com `beneficiary_groups` — **atributo do projeto, nunca da
  pessoa**, com `usage_policy` gravada no banco e invariante que verifica que a coluna não existe em nenhuma outra
  tabela nem em nenhum filtro de busca.
- **Taxonomias centralizadas e versionadas** (`taxonomies`, `taxonomy_terms`) com rótulo em pt/en, sensibilidade e
  política de uso.
- **Experiências profissionais declaradas** (`professional_experiences`): entram no perfil público **só** depois de a
  organização citada confirmar.
- **Eventos de domínio** (`domain_events`): 37 fatos no formato `Entidade.fato`, gravados por
  `app_record_event()` (SECURITY DEFINER, porque um fato de rede envolve **duas** organizações e uma política de
  inquilino o recusaria), com `REVOKE INSERT` direto.
- **Cobrança v2**: `plan_price_versions` com vigência e **imutabilidade** por gatilho, `price_change_notices` com
  **30 dias** de aviso obrigatório, `subscription_prices` registrando o preço aceito, imposto declarado no checkout,
  moeda no formatador do frontend. Regra comercial: **14 dias de teste com o produto completo · US$ 1,99/mês nos 3
  primeiros meses pagos · depois US$ 19,99/mês ou US$ 179,88/ano (equivalente a US$ 14,99/mês)**, declarada em
  `config/plans.json` e **nunca** em código.
- **`impacto/clock.py`**: `now()` e `today()` em UTC. 28 usos de `date.today()` substituídos em 15 arquivos.
- **79 rotas novas (704 no total)**, **27 telas funcionais** novas, `migrations/0016_v0160_impact_network.sql`
  (23 tabelas) e `0017_v0160_billing_v2.sql` (3 tabelas).
- **788 testes no total** (eram 673): rede (55), invariantes (28), cobrança (15), jornadas de ponta a ponta (7),
  arquitetura (6 → 13), desempenho (7 → 12).
- **`scripts/sql_prepare_check.py`**: extrai o SQL do código por AST e roda `PREPARE` em cada consulta. **185
  consultas conferidas, 0 erros** — encontrou 5 defeitos reais de nome de coluna que a leitura de código não pegou.
- Documentos: `IMPACT_NETWORK_ARCHITECTURE.md`, `IMPACT_GRAPH.md`, `RELATIONSHIP_MODEL.md`, `PROPOSAL_ENGINE.md`,
  `IMPACT_MARKETPLACE.md`, `MESSAGING_ARCHITECTURE.md`, `NOTIFICATION_ARCHITECTURE.md`, `IMPACT_REPORTING.md`,
  `ROLE_BASED_EXPERIENCE.md`, `WORKSPACE_ARCHITECTURE.md`, `PRIVACY_VISIBILITY_MATRIX.md`, `MODERATION_LADDER.md`,
  `BILLING_V2.md`, `INFORMATION_ARCHITECTURE.md`, `NAVIGATION_MODEL.md`, `DESIGN_HANDOFF_FINAL.md`,
  `MOBILE_READINESS_FINAL.md`, `FINAL_IMPACT_NETWORK_HARDENING_REPORT.md`.

### Alterado
- `app_related()` passou a conhecer os vínculos de rede, com **lista explícita de tipos** — não "todos menos
  bloqueio". A versão permissiva deixava um seguir unilateral abrir conversa, quebrando a regra de reciprocidade da
  v0.8.0 (pego por teste de regressão).
- `conversations` trocou `UNIQUE(org_a, org_b)` por `ux_conv_pair_context`: o mesmo par pode conversar sobre
  assuntos diferentes, e a conversa antiga continua válida.
- Políticas `ledger_insert`/`ledger_read`, `impupd_read`/`impupd_update` e `rel_read` passaram a reconhecer
  `app_project_supporter()`: quem apoia o projeto precisa poder registrar o próprio aceite.
- `money()` no frontend passou a receber a moeda (`money(cents, currency)`), com cache de formatador.
- `match()` do roteador passou a aceitar prefixo literal antes do parâmetro, para `/@identificador` funcionar.
- `monetization.quote()` devolve `base_cents`, `first_cents`, `first_price_source`, `intro_cents`, `currency`,
  `tax_behavior` e `provider_configured`. **Preço de entrada e cupom não se somam: vale o melhor dos dois.**
- `VERSION` → `0.16.0`; 28 documentos da v0.15.0 preservados em `history/v0.15.0/` com `NOTE.md`.

### Corrigido
- **`date.today()` × banco em UTC**: o contêiner roda em UTC-4, então por algumas horas de cada dia a plataforma
  gravava um dia a menos. 28 ocorrências em 15 arquivos, com teste de arquitetura para não voltar.
- **Aviso duplicado**: cada fato notificava a organização **e** a equipe. Agora é um aviso por fato.
- **Sete destinos de recomendação apontavam para telas inexistentes.** Corrigidos, com teste de arquitetura que
  confere cada destino contra o roteador real.
- **Organização nova recebia zero recomendações** (todas as regras dependiam de já haver projeto ou proposta). Três
  recomendações de primeiro passo acrescentadas.
- **O alvo de uma medida de moderação conseguia escrever `status`** — ou seja, anular a própria punição. GRANT de
  coluna *adiciona* privilégio e não restringe; a correção foi o gatilho `enforcement_target_guard()`.
- **Métricas de impacto eram calculadas em Python e gravadas em coluna guardada** — não passava. Movidas para
  `app_impact_metrics()`, usada pela prévia e pelo gatilho, para que as duas nunca divirjam.
- **`guard_columns` bloqueava a organização de publicar o próprio anúncio e enviar o próprio relatório.** Colunas de
  situação saíram da guarda e passaram a ser **derivadas** por gatilho.
- **`notify.PRIORITIES` dizia `urgent`; o CHECK do banco diz `critical`.** Corrigido, com invariante que compara
  **onze** listas Python aos CHECKs reais do banco.
- **`forbid_mutation` tornava o aviso de preço insatisfazível** (bloqueava até o "ciente"). `price_notice_ack_only()`.
- **`provider_price_missing` bloqueava o provedor de desenvolvimento.** Condicionado a `needs_price_id`.
- **`guard_columns` em `plan_price_versions` era inútil** (ela isenta `app_priv()`, o único contexto que escreve ali).
  Substituída por `price_version_immutable()`.
- **`DELETE /v1/workspace/personas/{persona}` respondia 200 com "removidas: 0".** Agora 404.
- **Colisão de rota em `/v1/readiness`** → `/v1/readiness/purposes`.
- Defeitos de nome de coluna encontrados por `sql_prepare_check.py`: `organizations.name` (usar
  `coalesce(trade_name, legal_name)`), `calls.org_id` → `owner_org_id`, `diagnosis_versions.project_id` (junta via
  `diagnoses`), `max(uuid)`/`min(uuid)` (não existem), `territory_needs.theme` → `cause`, `match_results` (não
  existe: `match_runs` **é** uma linha por par), `taxonomies.label_en`, as colunas reais de
  `professional_credentials` e de `professional_experiences`, `commitments.osc_org_id` +
  `application_id NOT NULL`, `documents.uploaded_by` (não `created_by`).
- **`network_initial_state()` falhava em tabelas que compartilham o gatilho**: `AND` em plpgsql **não** faz
  curto-circuito, então `TG_TABLE_NAME = 'x' AND NEW.coluna_de_x` quebra nas outras. Reescrito com `IF` aninhado.
- Variável plpgsql `grp` colidia com a coluna `grp` ("column reference is ambiguous") → `v_grp`.
- **`INSERT ... RETURNING` exige que a política de SELECT passe**: era a razão de aceitar proposta responder 403 —
  `rel_read` não incluía a organização dona do projeto.

## [0.15.0] — 2026-10-05 — Núcleo do produto, endurecimento final pré-design (cumulativo; snapshot do v0.14.0 em `history/v0.14.0/`)
### Adicionado
- **Vocabulário comum de evidência** (`core/evidence.py`): 9 fontes, `verified` **derivado da fonte** (não dá para marcar declaração como verificada), frescura com meia-vida por tipo de dado, decaimento que reduz **confiança e não pontuação**, e `insufficient_data` como faixa própria de confiança (cobertura abaixo de 40% não vira "confiança baixa", vira "não dá para dizer").
- **Ideia → projeto sem apagar a ideia**: `ideas` (5 estágios) e `projects.origin_idea_id`. A ideia continua registrada e aponta para o projeto; promover duas vezes responde 409. Ideia não consome cota de projeto; a promoção consome.
- **Máquina de situações do projeto como DADO**: 17 situações e 58 transições em `project_status_graph`, com gatilho que recusa o que não está no grafo **inclusive em SQL direto e no contexto privilegiado**. Transição que exige motivo responde 422 sem ele; transição inválida responde 409 **dizendo para onde é possível ir**. As transições que o produto já fazia desde a v0.7.0 estão no grafo.
- **Linha de tempo do projeto** reusando `ledger_entries` (append-only, encadeada por hash desde a 0002), com 20 tipos de entrada novos e verificação de integridade exposta na API. Nenhuma segunda tabela de histórico.
- **Retratos comparáveis** (`project_snapshots`): estado canônico com hash, `ledger_seq`, e comparação campo a campo (`changed`/`added`/`removed`). O mesmo estado produz o mesmo hash.
- **Registro de riscos** (`project_risks`) com `declared` × `system_identified` separados, 8 regras publicadas (`risk-rules@1.0`), severidade por matriz, varredura **idempotente** que auto-resolve o que deixou de valer e **nunca reabre** risco encerrado pela organização. Encerrar exige motivo.
- **Diagnóstico longitudinal** (`diagnostic-engine@1.0.0`): 20 lacunas em 8 dimensões ponderadas; saída separada em FATO / INFERÊNCIA / RECOMENDAÇÃO / **DESCONHECIDO**; versões imutáveis com `what_changed` calculado pelo servidor; publicar sem mudança não cria versão; lacuna gera ação e ação fecha quando a lacuna fecha.
- **Montagem de documento** (`document-assembly@1.0.0`): modelo publicado imutável, campo derivado por **lista fechada** de 14 caminhos de domínio, completude e bloqueio calculados pelo servidor, **recusa explicada** ao gerar incompleto (409 com o que falta), geração para PDF/DOCX/ODT no cofre com hash, e revisão com **quatro olhos**. Três modelos da plataforma publicados, cada um com a fonte declarada.
- **Inventário e rotação de chave** (`core/keys.py`): impressão digital de 16 hex (a chave **nunca** é gravada), estados `active`/`decrypt_only`/`retired`, recifragem em lote idempotente e auditada. KMS/HSM **declarado ausente** na API e na tela.
- **Provedores de assinatura com estado REAL** (`signature_providers`): `platform_advanced` em produção (avançada, selo HMAC), `govbr` e `icp_brasil` **indisponíveis** com a dependência nomeada. Gatilho no banco recusa assinatura com provedor fora de produção. Política de assinatura por tipo de documento, que **recusa** exigir nível que nenhum provedor entrega.
- **Match `match-engine@1.2.0`**: evidência nos sinais, confiança ajustada por frescura, faixa de confiança, **quatro versões** (motor/pesos/regras/taxonomia) viajando com cada resultado, e **retorno humano** (`match_feedback`, 7 valores, um por avaliação) com base de calibração sem dado pessoal — **sem treino automático**.
- **Indicadores por nível de resultado**: `indicator_catalog.result_kind` (`output`/`outcome`/`impact`), com comentário na coluna: "Meta atingida NÃO é impacto".
- **51 rotas novas** (625 operações) e **13 telas funcionais** (`web/src/pages/core.tsx`) — sem nenhuma decisão de design, de propósito.
- `migrations/0013_v0150_core_product.sql` (15 tabelas novas), `0014_v0150_platform_templates.sql` (modelos da plataforma + correções), `0015_v0150_fk_indexes.sql` (92 índices).
- **+109 testes (673 no total)**: núcleo (39), invariantes (21), isolamento (16), caminho de atualização (10), jornadas de ponta a ponta (8), navegador (6), volume (7, em passo próprio).
- Documentos: `CORE_PRODUCT_ARCHITECTURE.md`, `MATCH_ENGINE_FINAL.md`, `DIAGNOSTIC_ENGINE.md`, `PROJECT_LIFECYCLE.md`, `DOCUMENT_ASSEMBLY.md`, `LONGITUDINAL_TRACKING.md`, `KEY_ROTATION.md`, `SIGNATURE_VALIDATION_MATRIX.md`, `EXTERNAL_DEPENDENCIES.md`, `HOMOLOGATION_MATRIX.md`, `DATA_RETENTION_MATRIX.md`, `DATABASE_INTEGRITY_REPORT.md`, `SECURITY_FINAL_CHECKLIST.md`, `PERFORMANCE_REPORT.md`, `RELEASE_READINESS.md`, `FINAL_PRE_DESIGN_HARDENING_REPORT.md`. `DESIGN_HANDOFF.md` ganhou a seção 13 com os **fluxos A–I** e os **20 invariantes de design**.
### Alterado
- **Consolidação dos ODS**: `sdg_goals`, criada por engano na v0.14.0, foi **REMOVIDA**; `ods_goals` (que existe desde a 0001 e é referenciada por `indicator_catalog` e `ods_targets`) ganhou `code`, `name_en`, `color_hex` e `active`. `/v1/taxonomy` passou a `/v1/impact-taxonomy` (já existia `/v1/meta/taxonomy` com outro significado).
- **Feed do financiador 1,9× mais rápido** (3.126 ms → 1.615 ms com 10.000 projetos): elegibilidade dura que cabe em SQL entra no `WHERE`, carga em lote (`load_projects` + `project_funding_many`), memória por organização na requisição, e janela de pontuação de 200 **declarada na resposta**.
- `GET /v1/admin/institucional/documents` aceita filtro por organização e por tipo (a fila cresce com o uso).
- `migrate()` aceita `upto=` para preparar um banco em versão anterior e conferir o caminho de atualização.
- `archived → monitoring` passou a **exigir motivo**: reabrir projeto arquivado é exceção.
- Identidade do arquivo em `documents` (`sha256`, `size_bytes`, `storage_key`, `mime_type`) ficou **imutável para todo papel da aplicação**, privilegiado incluído.
### Corrigido
- **Lacuna de documento nunca fechava**: o diagnóstico usava as chaves `doc.estatuto` e `doc.ata_eleicao`, mas o tipo real no cofre é `estatuto_social` e `ata_eleicao_diretoria`. Por mais documento que a organização enviasse, a lacuna continuava aberta.
- **Versão de diagnóstico nascia a cada segundo**: `generated_at` entrava no hash de comparação, então "congelar versão" criava versão nova mesmo sem nada ter mudado.
- **Retorno de match escrevia na trilha do projeto**, expondo no histórico lido pela organização a decisão de um financiador terceiro. Removido.
- **Orçamento `0` e público `0` contavam como "informado"** no diagnóstico.
- **Evidência exigida bloqueava campo opcional em branco**, travando a geração para sempre.
- `build_state` lia `projects.funded_cents`, coluna que não existe — a captação vem de `project_funding()`.
- Promoção de ideia violava `projects.territory NOT NULL` quando a ideia não tinha território.
- `EnvKeyProvider` não enxergava a chave realmente em uso (derivada do `SECRET_KEY` quando não há `FIELD_ENCRYPTION_KEY`): o inventário mostrava "nenhuma chave" com dado cifrado existindo.
- **Campo opcional em branco** na interface enviava `""` e o servidor recusava com erro de padrão de formato.
- **92 chaves estrangeiras de caminho de acesso sem índice** (`org_id`, `project_id`, `application_id`, …): varredura de tabela inteira no filtro de inquilino e no `ON DELETE CASCADE`.
- Todos os 35 `except Exception` em `backend/impacto` passaram a ter comentário dizendo por quê.
- **O empacotador levaria o despejo do banco de desenvolvimento para dentro do ZIP**: `scripts/backup.sh` escreve em `backups/`, que não estava excluído nem em `collect()` nem no `.gitignore`. O pacote sairia com o dado de quem usou o ambiente. `backups/` e os sufixos de despejo (`.dump`, `.bak`, `.tar`, `.gz`, …) passaram a ser excluídos nos dois lugares, e **dois testes de arquitetura** falham se dado local ou arquivo compactado voltar a entrar.

## [0.14.0] — 2026-10-05 — Trust, Identity & Digital Signature (cumulativo; snapshot do v0.13.0 em `history/v0.13.0/`)
### Adicionado
- **Verificação pública por terceiro** (`GET /v1/public/verify/{code}`, sem login): responde se o documento é genuíno, **qual versão foi assinada**, se a integridade permanece (hash declarado × arquivo recontado agora), quem assinou, carimbos e se está revogado. A página pública lê **somente** um registro público curado — nunca tabela privada. Código legível `IMP-XXXX-XXXX-XXXX` tolerante a digitação errada e **QR Code** gerado pela própria plataforma.
- **Assinatura eletrônica avançada em DUAS camadas**: senha + código de uso único enviado por e-mail e **amarrado ao hash exato do conteúdo** (se o documento muda, o código morre). A assinatura passou a guardar qual código foi queimado e **qual era o nível de identidade** da pessoa naquele momento.
- **Revogação sem apagar nada**: `signature_revocations` (append-only) e revogação do registro público com motivo e data visíveis na página pública.
- **Cadeia de custódia por objeto** (`trust_events`): cada fato (criação, versão, assinatura, carimbo, consulta pública, conferência de integridade, revogação) encadeado por hash em gatilho SECURITY DEFINER, append-only, com função de verificação que aponta o `seq` exato da quebra.
- **Identidade por níveis** (`none→email→phone→document→professional→biometric`) com envio de documento ao cofre e **decisão humana** registrada; ninguém promove a própria identidade (coluna guardada no banco). Biometria, prova de vida e SMS **recusam explicitamente** (dependência externa) em vez de simular.
- **Credencial profissional**: catálogo de 20 conselhos, fluxo documental com histórico append-only, revogação, e elevação automática da identidade ao aprovar. "Verificada" significa **documento conferido pela equipe** — a plataforma não consulta conselho on-line, e diz isso na própria resposta.
- **Acordos multiassinatura** (`signed_agreements`): hash congelado ao publicar, cada parte assina com as duas camadas, vira vigente só quando **todas** as obrigatórias assinaram, recusa cancela com motivo, e entregas dão o acompanhamento longitudinal.
- **Carimbo de tempo interno** (selo HMAC do servidor, conferível); RFC 3161 recusa com `501 tsa_not_configured`.
- **Taxonomia ODS/ESG/determinantes sociais**: 17 ODS com código, nome e cor oficial (os **emblemas da ONU não acompanham** a plataforma — marca protegida), 3 pilares ESG, 11 determinantes sociais, e marcadores aplicáveis a projeto, solução, diagnóstico, necessidade, edital, organização e acordo, com integridade garantida por gatilho.
- **Idioma e tema**: 3 idiomas com **cobertura declarada por idioma** (pt-BR 100%, en/es núcleo), catálogo versionado em `config/i18n.json` com teste garantindo as mesmas chaves nos três; tema claro/escuro/sistema escolhido pela pessoa e aplicado antes do primeiro render.
- **Financiamento em cotas e campanha pública**: cotas com valor definido pela organização, reserva que o banco impede de estourar (inclusive sob concorrência), confirmação de recebimento pela equipe e página pública com "faltam N cotas".
- **Honorários por conselho**: publicar exige nome da fonte, URL e data de consulta (CHECK no banco). A tabela **nasce vazia** — a plataforma não estima honorário. Mais catálogo de atividades do profissional com preço próprio e margem de negociação, e busca por atividade com card completo.
- **Georreferência de organização** com consentimento registrado: a localização só aparece publicamente depois do consentimento, e a precisão é declarada.
- **Diagnóstico guiado em 8 etapas** (hipótese editorial declarada), com perguntas obrigatórias, documentos exigidos por etapa, progresso real e motivo registrado ao pular.
- **Formatos de documento**: docx, xlsx, odt, ods e xml escritos à mão (sem biblioteca nova — registros bloqueados), PDF com QR de verificação, leitura de docx/odt, e exportação dos datasets nos 8 formatos.
- `migrations/0012_v0140_trust_layer.sql`: 26 tabelas novas (191 no total), RLS em todas.
- **+96 testes (564 no total)**: 88 de API/unidade e 8 de navegador.
- Documentos: `TRUST_INVENTORY.md`, `TRUST_ARCHITECTURE.md`, `TRUST_IDENTITY.md`, `DIGITAL_SIGNATURE.md`, `PUBLIC_VERIFICATION.md`, `TRUST_SECURITY.md`, `TRUST_TESTING.md`, `SDG_ESG_TAXONOMY.md`, `I18N.md`, `DOCUMENT_FORMATS.md`, `FINAL_TRUST_HARDENING_REPORT.md`.
### Alterado (mudança de contrato)
- **`POST /v1/signatures` passou a exigir o campo `code`** (segunda camada). É mudança deliberada de contrato: assinar com senha apenas deixou de ser possível. O fluxo novo é `POST /v1/signatures/challenge` e depois `POST /v1/signatures`.
- `POST /v1/integrations/exports` aceita 8 formatos (antes: csv e json).
### Corrigido
- **Gatilho de capacidade de cotas passava em silêncio**: `SELECT ... FOR UPDATE` aplica também a política de UPDATE, a cota desaparecia para quem apoia e os `NULL` resultantes anulavam todas as checagens — era possível reservar cota inexistente. Agora a função é SECURITY DEFINER (e soma **todas** as reservas) e tem checagem explícita de `NULL`.
- **Payload da verificação pública só continha as assinaturas visíveis a quem pediu o código** — num acordo entre organizações diferentes, a página pública sairia incompleta. Passou a ser montado em contexto de sistema.
- **Recursão infinita de política de RLS** entre acordos e partes (as duas tabelas se consultavam) — travessia movida para funções SECURITY DEFINER.
- Unicidade global do endereço da campanha era checada sob RLS, então duas organizações conseguiam o mesmo endereço (o banco barrava com erro genérico).
- Leitor de docx/odt não desfazia entidades XML (`&amp;` voltava literal).
- Páginas novas do frontend passavam o erro cru para o `StateView`, que espera texto: a mensagem da API não aparecia.
### Não feito / pendente (declarado)
- **Assinatura qualificada ICP-Brasil e gov.br: NÃO IMPLEMENTADAS** (dependência externa + homologação). O enum aceita os valores desde a v0.7.0, mas nenhum código os produz.
- **Biometria, prova de vida e SMS: NÃO IMPLEMENTADOS** (exigem provedor contratado). Nenhum dado biométrico é armazenado.
- **Carimbo RFC 3161: NÃO IMPLEMENTADO** (exige ACT contratada).
- **Consulta on-line a conselho profissional: não existe** — nenhum conselho expõe API pública contratada.
- **Edição on-line de Office/LibreOffice: NÃO IMPLEMENTADA** (exige servidor WOPI — dependência externa).
- **Emblemas oficiais da ONU não acompanham a plataforma** (marca protegida); as 169 metas dos ODS não foram incluídas.
- Nenhum arquivo foi aberto no Office/LibreOffice e nenhum QR foi lido por leitor comercial neste ambiente.
- `npm audit`/`pip-audit` continuam bloqueados pelo ambiente; pentest e teste de carga pendentes.
- Expurgo de `trust_events` e `verifiable_records` sem prazo definido — **VALIDAÇÃO JURÍDICA NECESSÁRIA**.

## [0.13.0] — 2026-10-05 — Integration Hub (fundação) — cumulativo; snapshot do v0.12.1 em `history/v0.12.1/`
### Adicionado
- **Camada de integração desacoplada** (`backend/impacto/integrations/`): contratos internos (`Environment`, `Capability`, `AuthKind`, `SyncStrategy`, `Maturity`, `CanonicalRecord`, `IntegrationError`, protocolo `IntegrationAdapter`), transporte resiliente (classificação temporário × permanente, espera crescente com variação, disjuntor por conexão), abstração de credencial cifrada, mapeamento de campos com 12 transformações declaradas (sem `eval`), correspondência de ID externo, caixa de saída de eventos de domínio, entrada de webhook deduplicada, jobs idempotentes e integração por arquivo (CSV/XLSX/JSON/XML). **O núcleo não importa nenhum fornecedor.**
- `migrations/0011_v0130_integration_hub.sql`: 13 tabelas com RLS (165 no total), unicidades de idempotência, `integration_secret()` SECURITY DEFINER e GRANTs por coluna — a coluna do segredo **não é legível** pelo papel da aplicação.
- **36 rotas** `/v1/integrations/*` e `/v1/admin/integrations/*` (511 operações no total): catálogo, conexões, credencial (escreve, nunca lê), mapeamentos, saúde não destrutiva, jobs, correspondências, eventos, assinaturas de webhook, entregas e reenvio, entrada pública assinada, importação com aprovação humana, exportação e painel de operação.
- **Adapters de fundação**: `generic_rest`, `generic_webhook`, `senior_sapiens` (híbrido REST+SOAP), `totvs` (Protheus/RM/Datasul), `government_api` (recusa agir enquanto não autorizado), `bi_export` (6 datasets), `file_batch`. 9 provedores em `config/integration_providers.json` com **maturidade honesta**.
- **+76 testes (468 no total)**: ciclo de vida, segurança de credencial, isolamento entre organizações (IDOR), mapeamento e conflito de ID, idempotência e concorrência (4 trabalhadores = 1 execução; 4 entradas = 1 processamento), webhooks de entrada e saída, arquivos, saúde/operação, segurança (SSRF, XXE, bomba XML, injeção SOAP) e contrato dos adapters.
- Documentos: `INTEGRATION_INVENTORY.md`, `INTEGRATION_ARCHITECTURE.md`, `INTEGRATION_HUB.md`, `INTEGRATION_SECURITY.md`, `INTEGRATION_OPERATIONS.md`, `INTEGRATION_TESTING.md`, `INTEGRATION_PROVIDER_GUIDE.md`, `INTEGRATION_CAPABILITY_MATRIX.md`, `FINAL_INTEGRATION_HARDENING_REPORT.md`. `DESIGN_HANDOFF.md` ganhou a seção 11 (camada de integração: entidades, estados, 12 telas necessárias).
### Corrigido
- Hub: política de RLS de `integration_deliveries` impedia a própria emissão de evento; evento de domínio exigia privilégio e quebrava a caixa de saída na transação da organização; GRANT amplo expunha o segredo da assinatura; gatilho de maturidade bloqueava a própria migração; faltava GRANT para a promoção de maturidade pela administração. Todos corrigidos **antes da liberação** da migração 0011.
- Validação de endpoint deixou de resolver DNS na gravação (impedia configurar host ainda não provisionado e tornava o salvamento dependente de DNS); a guarda autoritativa de SSRF continua no momento da chamada.
- `GET /v1/integrations/jobs/{id}` consultava `audit_events.created_at` (a coluna é `at`).
### Não feito / pendente (declarado)
- **Nenhuma integração homologada ou executada contra sistema externo real** — só contra dublê. SFTP **não implementado**. Gov.br/Conecta exige credenciamento (AUTORIZAÇÃO EXTERNA NECESSÁRIA).
- Sem interface: a camada de integração não tem nenhuma tela (é trabalho da etapa de design).
- Sem fila distribuída (o trabalhador é o agendador do processo); sem teste de carga; `npm audit`/`pip-audit` continuam bloqueados pelo ambiente.
- Expurgo de jobs e eventos sem prazo definido — **VALIDAÇÃO JURÍDICA NECESSÁRIA**.

## [0.12.1] — 2026-10-05 — Baseline técnica para a camada de design (cumulativo; snapshot do v0.12.0 em `history/v0.12.0/`)
### Corrigido
- **Vazamento de detalhes do banco nas respostas da API**: violações de CHECK/FK/NOT NULL devolviam o texto interno do PostgreSQL (nome de tabela, de constraint e, em violação de unicidade, valores). Agora a resposta é genérica com `error_id`, e o detalhe fica só no log; **mensagens autoradas pelos gatilhos do projeto continuam visíveis** (chegam com o mesmo código de erro e são distinguidas por padrão de texto).
- **Desconto de voucher reservado nunca aparecia** na página Plano: `GET /v1/billing` montava `pending_discounts` com JOIN em `vouchers`, tabela invisível à organização por RLS — o resultado era **sempre vazio**. Passou a ser lido em contexto de sistema restrito ao `org_id` da sessão, expondo só tipo/valor/plano (nunca código ou hash).
- **Boletim podia ser perdido**: `last_sent_at` era consumido ANTES do envio, então uma falha de SMTP fazia a inscrita perder a edição do período inteiro. Agora o período só avança quando o envio sai; o job devolve `failed` e reenvia no ciclo seguinte.
- **Contraste reprovado (WCAG AA)**: o texto secundário (`--texto-3`) tinha 4.19:1 sobre o fundo das páginas (exigido 4.5:1). Token ajustado para 4.63:1 **preservando matiz e saturação**; tema escuro já passava. Há teste automático de contraste em tema claro e escuro.
### Adicionado
- `migrations/0010_v0121_indexes.sql`: 6 índices de cobertura para consultas reais em tabelas de crescimento (`course_enrollments.course_id`, `partnership_activities(request_id, created_at)`, `trial_requests` por organização e por usuária, `partnership_requests.user_id`, `demo_requests.user_id`). Cada índice cita a consulta que o justifica e foi verificado por `EXPLAIN`.
- **+33 testes (392 no total)**: varredura de autorização sobre as 475 operações, IDOR de escrita, 6 testes de concorrência real com threads, higiene de erros, invariantes de dinheiro/fuso, entrega de e-mail, 4 jornadas de navegador que faltavam (logout, área bloqueada, página Plano com voucher e cancelamento, administração com MFA) e 2 de acessibilidade medida no navegador.
- Documentos: `FINAL_TECHNICAL_BASELINE.md`, `DESIGN_HANDOFF.md`, `FINAL_RELEASE_MANIFEST.json`.
### Não feito / pendente (declarado)
- `npm audit` e `pip-audit` **não executados**: registries npm e PyPI bloqueados neste ambiente (403 / “no matching distribution”) — comandos e erros registrados em `FINAL_TECHNICAL_BASELINE.md`. Rodar em CI.
- Sem axe/leitor de tela; sem Stripe real, nota fiscal ou preços; sem conteúdo oficial; sem IA generativa/embeddings; apps móveis não compilados; pentest e carga em volume de produção pendentes.

## [0.12.0] — 2026-10-05 — Central de Conhecimento (cumulativo; snapshot do v0.11.0 em `history/v0.11.0/`)
### Adicionado
- **Central de Conhecimento** (`/ajuda`): busca híbrida (FTS + trigrama + assuntos + tela + público, com “por que apareceu”), ajuda contextual, guias com checklist/passos/ação, biblioteca (modelos preenchíveis → rascunho, checklists, documentos, versões), FAQ com votos, **assistente extrativo e ancorado** (recusa quando não há base; sem IA generativa), “Comece aqui” e pendências **medidos por dados reais**, “Minhas atividades”.
- **Academia**: cursos, quiz corrigido no servidor (gabarito inacessível), trilhas, certificado **não oficial** com verificação pública e revogação.
- **Eventos** (vagas, lista de espera com promoção, link só para inscritas, presença, avaliação, gravação), **suporte** (chamados, SLA com escalonamento, notas internas, recorrência), **parcerias** (CRM) e **demonstração** (públicos, com consentimento e anti-bot), **solicitação de teste** (decisão humana com motivo; reaproveita `org_trials`), **boletim** (duplo opt-in), preferências de notificação.
- **Governança editorial**: fluxo rascunho→revisão→aprovado→publicado→arquivado, **quatro olhos no banco**, versões imutáveis, regulatório exige fonte+data, “Revisão necessária”, histórico, papéis `editor/reviewer/support`.
- **E-mail** para avisos de cobrança, suporte e eventos (job `hub_ops`, respeita preferências, sem repetição) — fecha o pendente “avisos de cobrança só in-app”.
- Migração `0009_v0120_knowledge_hub.sql` (32 tabelas; banco de desenvolvimento: 152). API: **475** operações (+102). Frontend: `/ajuda/*` (público e logado) e `/admin/central/*`.
- Testes: **357** (290 + 62 de domínio + 5 E2E de navegador, 4 jornadas). Documentos: `KNOWLEDGE_HUB`, `USER_GUIDES`, `TRAINING_ACADEMY`, `SUPPORT_SYSTEM`, `PARTNERSHIP_SYSTEM`, `TRIAL_SYSTEM`, `CONTENT_GOVERNANCE`, `KNOWLEDGE_DATA_MODEL`, `STORE_READINESS`.
### Alterado
- **Lint Python**: `ruff` instalado e executado (`docs/evidence/ruff_v0.12.0.log`); ~40 arquivos receberam correções que preservam o comportamento (suíte verde antes e depois).
- `Principal.staff_roles`, `RouteSpec.staff`; `/v1/me` devolve `staff_roles`; `jobs.py` ganhou `hub_ops`.
### Não feito / pendente (declarado)
- **Nenhum conteúdo real**: só exemplos `demo=true`; nenhuma regra fiscal/jurídica aprovada. Sem IA generativa; sem embeddings; pesos de busca e SLA inicial são **hipótese**. Preços, nota fiscal e Stripe real seguem pendentes. Editor de curso/recurso/FAQ/evento é JSON validado. Curso publicado não é editado no lugar. Botão de ajuda contextual ligado em 3 telas. Auditoria de dependências npm/pip **não executada** (rede bloqueada). Sem axe/leitor de tela; apps móveis não compilados.

## [0.11.0] — 2026-10-05 — Monetização SaaS (cumulativo; snapshot do v0.10.1 em `history/v0.10.1/`)
### Adicionado
- **Níveis FREE / PLUS / PREMIUM(FULL) / GOV** (`plans.tier`, `config/plans@1.1`; planos `osc_plus`, `company_plus`, `gov_institutional`) e função central de direitos (`entitlements.effective/get_entitlements/has_access`). Preços **não definidos** (nunca inventados).
- **Trial de 14 dias FULL por organização**, iniciado no cadastro, sem cartão; cancelar mantém o acesso até o fim e não cobra; nada é apagado. Anti-abuso por HMAC de e-mail normalizado e CNPJ (`trial_claims`). Avisos nos dias 1/7/11/13/14, fim, conversão, falha e cancelamento (in-app, sem repetição).
- **Cobrança mensal/anual** com economia real (`plan_prices`), cotação calculada no servidor (`POST /v1/billing/quote`), checkout Stripe com `trial_end` (nunca cobra antes do fim do trial), troca de plano com proration (`/change-plan`), portal do provedor (`/portal`), cancelar/reativar.
- **Webhooks Stripe** idempotentes, assinados e tolerantes a eventos fora de ordem; estados TRIALING/ACTIVE/PAST_DUE/CANCELED/INCOMPLETE/EXPIRED + `payment_issue` (`payment_failed`/`action_required`).
- **Vouchers** de desconto percentual e valor fixo (duração única/recorrente/permanente), 100% = licença, sem duração = permanente, por plano e por organização. **Licenças** com origem e revogação com motivo. **Convênios/GOV** (código, vagas, período, plano e/ou desconto; domínio só restringe; ativação por 2º admin).
- Admin: vouchers estendidos, convênios, cobrança por organização (licença, revogação, trial, preço do plano). Frontend: `/conta/plano` (alias `/settings/billing`) reescrita — alternância mensal/anual, cotação, trial, cancelamento com confirmação, voucher, convênio, faturas.
- Migração `0008_v0110_monetization.sql` (6 tabelas: `plan_prices`, `org_trials`, `trial_claims`, `billing_notices`, `agreements`, `agreement_members`; colunas novas; RLS e gatilho `billing_guard`). API: **373** operações. Banco de desenvolvimento: **120** tabelas.
- +34 testes (290 no total) em `test_v0110_monetization.py`. Documentação: `docs/billing.md`.
### Alterado (comportamento)
- Cancelar assinatura (sandbox/manual) mantém o acesso até o fim do período pago (antes: imediato). `invoice.paid` com valor > 0 converte o trial e confirma o plano.
- Job `billing_lifecycle` (lembretes, fim de trial, conversão de assinaturas sandbox, fim de períodos cancelados, limpeza de `trial_claims` > 24 meses).
### Não feito / pendente (declarado)
- **Stripe nunca foi chamado de verdade** (só dublê): conta, preços, endpoint do webhook, Billing Portal e homologação são externos. O mínimo de `trial_end` do Checkout (~48 h) **não foi verificado** na API real. Divisão PLUS × PREMIUM é **hipótese**. Avisos só in-app (sem e-mail). Sem nota fiscal/reembolso/chargeback. Sem linter Python.

## [0.10.1] — 2026-10-05 — Pendências institucionais (cumulativo; snapshot do v0.10.0 em `history/v0.10.0/`)
### Adicionado
- **Cruzamento fiscal × elegibilidade institucional**: `GET /v1/insights/fiscal-estimates` aceita `osc_org_id` e devolve `institutional_eligibility` (estado, resumo, o que falta, camadas fiscais) como camada **separada** da estimativa; aviso quando a OSC é NÃO ELEGÍVEL.
- **Perfis OS / OSCIP / OSC / iniciativa em estruturação** (`GET /v1/institutional/persona`): qualificações, autoridade qualificadora, **áreas de atuação** (`areas` em qualificações), instrumentos, alertas de validade (30/90 dias) e próximos passos.
- **Instrumentos** (contrato de gestão, termo de parceria/colaboração/fomento, acordo de cooperação): cadastro **declarado**; verificação só pela administração (número + comprovante validado ou URL oficial + nota).
- **Trilha de formalização** (11 etapas; automáticas derivadas dos dados, manuais só declaradas; `config/formalization_path.json`, hipótese a validar) e **pedidos de mentoria** (limite de taxa e de abertos; atendimento humano).
- **Rede da solução** (`GET /v1/solutions/{id}/network`): autor, território, ODS, temas, soluções relacionadas e demanda **agregada** (sem identidades); visão em lista acessível.
- **Tesauro** de 44 → 67 conceitos (`concepts@1.0+0.10.1`). Alguns termos comuns continuam resolvendo para conceitos mais amplos já existentes (ex.: "creche" → crianças; "primeira infância" → crianças; "teatro" → artes; "alfabetização" → educação) — termos conflitantes foram retirados dos conceitos novos de propósito.
- **Dados DEMO institucionais** no seed (rotulados `[DEMO]`, qualificação **fictícia**; coletivo sem CNPJ).
- Frontend: abas Instituição "OS / OSCIP", "Instrumentos", "Formalização e mentoria"; campo "Áreas de atuação"; admin Institucional "Instrumentos" e "Mentoria"; botão "Ver rede de relações" na solução.
- Migração `0007_v0101_institutional_extras.sql` (3 tabelas: `organization_agreements`, `formalization_steps`, `mentoring_requests`; coluna `areas`; RLS e gatilhos de proteção). API: **358** operações; **114** tabelas.
- +23 testes (256 no total): 17 institucionais, 2 de rede, 1 de tesauro, 3 E2E (inclui **painel admin com MFA real** no Chromium).
### Alterado (comportamento)
- Verificar instrumento sem número/comprovante validado/URL oficial é recusado (422).
### Não feito / pendente (inalterado ou declarado)
- Validação jurídica de catálogos/regras/trilha; **IA sobre documentos não implementada** (só regras); Android/iOS não construídos; sem linter (só `tsc` e `compileall`); embeddings, intenção por LLM, tiles de mapa externos e importação Lattes/Plataforma Brasil dependem de infraestrutura externa.

## [0.10.0] — 2026-10-05 — Camada institucional do terceiro setor (cumulativo; snapshot do v0.9.0 em `history/v0.9.0/`)
### Adicionado
- **Modelo em 5 camadas** (natureza jurídica × qualificações × perfil de atuação × situação institucional × elegibilidade calculada) — `THIRD_SECTOR_MODEL.md`. Migração `0006_v0100_institutional.sql` (6 tabelas novas: `inst_catalog_items`, `eligibility_rules`, `organization_qualifications`, `organization_qualification_events`, `proponent_needs`, `eligibility_evaluations`; colunas novas em `organizations`, `documents`, `calls`, `funder_profiles`, `solutions`; RLS em todas).
- **Motor de Elegibilidade Institucional** `institutional-eligibility@1.0.0` (5 estados, explicação, fonte, data; ausência de regra ⇒ PENDENTE) e **maturidade 0–6** (`config/institutional_maturity.json`, hipótese a calibrar).
- **Fluxo editorial** de catálogos e regras DRAFT→REVIEW→APPROVED→PUBLISHED→ARCHIVED com quatro olhos; **importação de regras candidatas em rascunho** (`config/institutional_rules.candidates.json`).
- **Qualificações** declaradas × verificadas (verificar exige autoridade, número, comprovante validado ou URL, vigência, justificativa); **documentos institucionais** com 5 estados; **badges** calculados com critério/fonte/validade.
- **Match Engine 1.1.0**: hard blockers explicados, natureza jurídica/maturidade/modalidade; **camadas fiscais** (estimativa, regra identificada, possível elegibilidade, elegibilidade documental, validação profissional).
- **Banco de Ideias**: IP/confidencialidade/titularidade, portão de publicação, rótulos de compartilhamento, acesso limitado, proponente e prontidão para financiamento nos resultados, filtros institucionais.
- Frontend: páginas Instituição (OSC/financiador/governo/profissional), perfil público, painel admin institucional, cadastro com natureza jurídica (coletivos sem CNPJ), formulários de edital/financiador/solução e filtros da Biblioteca.
- +37 operações de API (343 no total). +51 testes (233 no total).
### Alterado (comportamento)
- **Requisito de certificação no match agora exige qualificação VERIFICADA e vigente**; certificação apenas declarada não satisfaz. O campo legado `certifications` (PATCH `/v1/org`) passa a criar qualificações **declaradas** e nunca apaga existentes.
- Publicar solução exige titularidade declarada e autorização de publicação.
- `.content` do layout com `min-width: 0` (corrige rolagem horizontal em celular em páginas com abas).
### Corrigido
- Teste instável `test_signed_tokens` (adulteração podia gerar o mesmo token).
### Não feito / pendente
- Rota de estimativa fiscal sem cruzamento com `osc_org_id`; dados DEMO institucionais no seed; E2E do painel admin institucional (exige fluxo MFA no navegador); validação jurídica de todos os catálogos/regras iniciais; integração com bases governamentais (inexistente).

## [0.9.0] — 2026-10-05 — Biblioteca de Soluções de Impacto (cumulativo com 0.8.0, que não foi lançado separadamente)
### Adicionado
- **Banco de ideias, projetos, metodologias, tecnologias sociais e projetos acadêmicos** (`/v1/solutions`, 60 operações; migração `0005_v090_solutions.sql`: 20 tabelas, RLS em todas, gatilhos de regra de verdade).
- **Busca por intenção** híbrida sem IA (tesauro de 44 conceitos, FTS `pt_unaccent`, trigramas, filtros estruturados), relevância 0–100 **explicável** com pesos configuráveis (`config/solution_weights.json`, hipótese) e análise de sensibilidade (`docs/evidence/weights_sensitivity_v0.9.0.json`).
- **Match financiador↔solução** (`solution-match@1.0.0`), recomendações por tese ou por opt-in, independente do plano (teste AST).
- **Replicabilidade** (score só com confiança ≥ 50), **adaptação para território**, **desenvolver ideia** (rascunho por regras, revisão humana obrigatória no banco), **combinar soluções**, **comparador** (2–4), 7 modos de visão, "Quero algo como este", copiloto ancorado (sem IA).
- **Intenção de financiamento** em 10 etapas com privacidade e anti-manipulação (funções `SECURITY DEFINER`, gatilhos, eventos append-only), pedidos ao autor, **marketplace de replicação** com confirmação do autor, avaliações restritas, contestação de autoria.
- **Níveis de confiança** (não verificado → verificado) só pela administração; evidências/resultados com revisão; dados DEMO marcados.
- Frontend: Biblioteca, Perfil com proveniência, Comparar, Combinar, Minhas soluções, Pedidos, Replicações, Preferências, Admin de soluções; componente acessível `Group`.
### Alterado
- API 246 → **306** operações; banco 85 → **105** tabelas, 163 → **207** políticas RLS; 53 gatilhos.
- Roteamento ordenado por especificidade (literal antes de `{param}`) em `app.py`.
### Corrigido (descoberto na construção)
- `/v1/me` retornava 500 para a organização da plataforma (faltava `plan_names`) — bug pré-existente; teste de regressão.
- Opt-out de personalização não apagava o histórico de buscas (faltava política DELETE).
- Perfil de financiador vazio (PF/empresa) gerava recomendações sem base; agora `funder_profile_missing`.
- Chips dentro de `<label>` poluíam nomes acessíveis; temas exibiam slug sem acento.
### Testes
182 testes (31 + 3 E2E novos da Biblioteca), 0 falhas — `docs/evidence/test_run_v0.9.0.log`. Busca: p50 ≈ 181 ms / p95 ≈ 474 ms com 5.000 soluções sintéticas (local).
### Observação de versão
O v0.8.0 foi desenvolvido na mesma sessão mas não foi empacotado; seus documentos estão em `history/v0.8.0/`. O v0.9.0 é o primeiro pacote a incluí-lo.

## [0.8.0] — 2026-10-05 — Impacto, compras, pagamentos registrados, risco, rede, mapa, relatórios
### Adicionado
- **Financiador pessoa física** (`organizations.kind = individual`, sem CNPJ): nome mascarado para as OSCs por padrão (`org_display`), opt-in explícito para mostrar o nome.
- **ODS 1–17** normalizados e **catálogo de indicadores** (13 da plataforma; metas oficiais ODS NÃO são embutidas — importar de fonte oficial). Valores **reportados × validados** (validação por outra organização, com evidência; o banco recusa auto-validação). Dimensões ESG por indicador.
- **Impact Graph**: relações tipadas (hipótese, associação, correlação, inferência, evidência observada, causalidade validada); só a última afirma causa e exige evidência + revisão externa (CHECK no banco).
- **Diagnóstico social** (problema → causas → metas → plano) aplicável ao projeto; **determinantes sociais** (mapeamento próprio, k≥3, sem estatística populacional).
- **Compras**: política configurável (padrão 3 cotações), benchmark por mediana, sinal "preço possivelmente fora do padrão" (nunca "fraude"), exceção com 2ª aprovação, vínculo despesa↔compra.
- **Modelos de contribuição** (portão jurídico: só admin aprova; termos aprovados imutáveis) e **pagamentos** como *registro* (máquina de estados no banco, estorno com dupla parte, eventos append-only, ledger), **extrato CSV + conciliação**. A plataforma continua sem custódia (ADR-022).
- **Risco e antifraude** (8 detectores → sinais para revisão humana; bloqueio só por decisão humana com justificativa).
- **Rede**: seguir, bloquear, mensagens entre organizações com relação, moderação por denúncia, necessidades de apoio profissional + **Match profissional** (professional-match@1.0.0, plano não interfere), conquistas objetivas sem ranking.
- **Mapa** sem provedor externo (SVG) e localização com precisão configurável (região/município/aproximada/bairro/exata); coordenadas exatas nunca vazam.
- **Central de relatórios** (8 tipos, impressão/PDF pelo navegador, CSV com proteção contra injeção de fórmula).
- **Observabilidade**: `traceparent` W3C, spans de banco, agregação de erros sem PII (`/v1/admin/errors`), job `risk_scan`; `scripts/loadtest.py` com medição real.
- 15+ páginas novas no frontend; `ErrorBoundary` (evita tela em branco).
### Alterado
- API: 165 → 246 operações; banco: 56 → 85 tabelas, 163 políticas RLS. Migração `0004_v080_modules.sql` (a 0003 não foi editada; `org_document_metadata` redefinida na 0004 para `individual`).
### Corrigido durante a construção
Função de metadados documentais negava o financiador PF; página em branco por uso incorreto da taxonomia (hoje há ErrorBoundary); rótulo duplicado quebrava o seletor do E2E de cadastro.
### Testes
144 testes (34 novos de domínio + 3 E2E novos), 0 falhas — `docs/evidence/test_run_v0.8.0.log`; carga: `docs/evidence/loadtest_v0.8.0.json`.

## [0.7.0] — 2026-10-05 — Execução real sobre PostgreSQL
### Adicionado
- Backend Python (Starlette) com 165 operações `/v1`, OpenAPI e `docs/API.md` gerados do código.
- PostgreSQL 16: 56 tabelas, RLS em todas, triggers de integridade, cadeias de hash (auditoria e ledger), papéis `impacto_owner`/`impacto_app`.
- Autenticação de produção: scrypt, sessões opacas, refresh rotativo com detecção de reuso, MFA TOTP, OIDC (PKCE), lockout, rate limit, CSRF.
- Catálogo unificado de editais/fundos (privado, federal, estadual, municipal, internacional), importação de fontes, busca, buscas salvas e alertas (premium).
- Match Engine 1.0 (duas direções, bloqueadores, explicabilidade, confiança mínima), Fiscal Engine 1.0 (somente regras aprovadas), compliance/KYB, IA provider-agnostic.
- Candidatura assistida passo a passo, rascunhos com IA, revisão e assinatura de profissional habilitado, cofre de documentos com antivírus/storage privado.
- Execução: aportes (confirmação dupla), despesas, evidências, marcos, devolutivas, relatório de projeto, CSV; carteira da empresa; portal do governo (agregados k-anônimos).
- Cobrança (none/sandbox/Stripe/manual), planos, vouchers com dupla aprovação, entitlements.
- Frontend React/TS (PWA), cinco portais, tema claro/escuro; Capacitor (Android/iOS) preparado.
- LGPD técnico: exportação, eliminação, consentimentos, retenção; minutas legais [VALIDAR JURÍDICO].
- DevOps: Dockerfile, compose, nginx, CI, backup/restore verificado, métricas Prometheus.
- 111 testes automatizados (unit, integração, RLS/segurança, OIDC, E2E em Chromium).
### Segurança adicional
- Cliente HTTP com proteção SSRF (destinos internos bloqueados, sem redirecionamentos); verificação no boot de que o papel do banco respeita RLS.
### Alterado
- Match: sem nota quando a confiança < 50; datas dd/mm/aaaa; projetos bloqueados aparecem com motivos (`hidden_blocked`).
### Removido / substituído
- SQLite e autenticação de demonstração do v0.6.0 (preservados em `history/v0.6.0/`).
### Corrigido durante a construção (cada um com teste de regressão)
Corpo validado antes da autorização; UUID inválido → 500; falta de política UPDATE em `conflict_declarations`; nomes de assinantes ocultos pela RLS;
voucher sob SERIALIZABLE retornava 500; plano sem preço era comprável no sandbox; contadores de falha de login revertidos por rollback; raízes de palavras de segurança alimentar ausentes.
### Limites conhecidos
Ver `FINAL_RELEASE_AUDIT.md` §3 e `PRODUCTION_READINESS.md`.
