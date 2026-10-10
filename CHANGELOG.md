# Changelog
Formato Keep a Changelog. Histórico anterior (v0.1–v0.6): `history/v0.6.0/CHANGELOG.md`; snapshot dos documentos do v0.7.0: `history/v0.7.0/`.

## [0.35.0] — 2026-10-10

### Segurança, antifraude e integridade financeira: correções da auditoria (pacote IMPACTO MASTER Security 1.0.0, ADR-385 a ADR-392)

Fase 1 (somente leitura) em `docs/security/AUDITORIA_SEGURANCA_FASE1.md`; fase 2 (correções, lotes A–I, autorizadas pelo
responsável) em `docs/security/RELATORIO_CORRECOES_FASE2.md`. **84 testes novos** (`test_v0350_security`), cada lote provado
no código anterior (`docs/security/evidencias/`). Nada publicado; nenhuma ação contra a produção.

- **Documentos na diligência** (FILE-07, provado): financiador vê só os tipos institucionais da OSC (ou o que ela compartilhar);
  nunca exportação de dados, documento de dirigente ou de identidade; o acesso termina com a candidatura.
- **Papel mínimo** nas rotas comerciais (só a dona autoriza cobrança, revoga, muda teto) e varredura de toda rota de escrita;
  **nome civil** de apoiador pessoa física mascarado na página pública sem opt-in.
- **Integridade financeira**: conciliação com fonte declarada (provedor real exige extrato; extrato manual só concilia com
  aprovação de outra pessoa); "permitir" após revisão confirma pelo caminho normal; confirmação sem valor não confirma; evento
  antes da confirmação fica adiado e é reaplicado; teto de 10 tentativas; mesma chave de idempotência com outro valor → 409;
  origem pública do recurso prevalece sobre o doador; verificação do beneficiário revogável, com titularidade e quatro olhos.
- **Equipe**: escrita administrativa pede identidade confirmada há < 15 min; MFA da equipe com código do aplicativo + código
  por e-mail e sem desativação; código errado conta no bloqueio; avisos de segurança por e-mail; produção recusa
  `REQUIRE_MFA_FOR_ADMINS=false`; `create-admin` não promove conta existente em silêncio; IP do cliente pela ponta confiável.
- **Webhooks**: assinatura com carimbo de tempo (300 s), segredo por endpoint, sem segredo de reserva, sandbox nunca em produção;
  **achado novo**: evento sem assinatura não ocupa mais o identificador do verdadeiro.
- **Chave PIX de repasse**: identidade confirmada, aviso a todas as partes, trava depois da primeira assinatura, carência de 24 h.
- **Banco**: `search_path` com `pg_temp` em toda função privilegiada (provado: tabela temporária mudava `identity_level()`),
  EXECUTE só para a aplicação, visão com `security_invoker`, TRUNCATE travado nas tabelas só-inclusão, testes de catálogo.
- **Arquivos, web e IA**: PDF conferido pela estrutura; antivírus fora do ar vira quarentena; exclusão de conta apaga arquivos
  pessoais; JSON profundo/Content-Length inválido → 400; 409 sem nome de restrição; `/readyz` público resumido; SSRF por
  `is_global`; logs sem segredo nem dado pessoal; política da IA aplicada (esquema obrigatório, revisão humana no resumo).
- **Antifraude e identidade**: limiares lidos do arquivo de regras (2026-10.2); fracionamento; chave PIX repetida; destino de
  repasse mudado; caso com revisor, evidências, recurso e encerramento; restrição de organização com duas pessoas; verificação de
  identidade com suspensa/revogada/vencida e sem autodecisão.
- **Cadeia de entrega**: actions por SHA; gitleaks no push; `.gitignore` amplo; `npm audit` completo; Dependabot; SBOM e varredura
  da imagem (informativos); **backup externo com cifra autenticada** (`.dump.aead`, autorizado pelo responsável); 7 runbooks.
- Migração `0074_v0350_security.sql`. Variáveis novas: `TRUST_PROXY_HEADERS`, `TRUSTED_PROXY_HOPS`, `CLIENT_IP_HEADER`,
  `DONATION_WEBHOOK_SECRET`, `PAYMENT_SANDBOX_ENABLED` — ver `docs/security/PUBLICATION_CHECKLIST_v0350.md`.
- **Não feito por decisão do responsável:** recusar a produção sem antivírus; teste de IP no demo; diagnóstico do banco de
  produção. **Não feito por impossibilidade verificável:** imagens por digest e hashes Python.
- **Fechamento:** o CI do PR #8 (axe-core com trava) achou o filtro da fila de identidade (`/admin/identidade`) sem nome
  acessível — corrigido, com `test_e2e_v0350_admin_screens` (falha no front anterior). O teste antigo de pagamentos que procurava
  o evento não assinado pelo id alegado passou a procurá-lo pelo identificador próprio (PAY-13).

## [0.34.0] — 2026-10-10

### Ecossistema financeiro: gratuito até gerar valor, obrigações de remuneração, recurso público, conciliação com exceções (ADR-377 a ADR-384)

- **Obrigações de remuneração** (`remuneration_obligations`): uma por fato × regra, valor congelado, cadeia calculada → devida →
  faturada → cobrada → recebida → liquidada (desvios: estornada, vencida, em disputa, dispensada, isenta), histórico só-inserção;
  liquidar/decidir/dispensar/autorizar exigem `finance.approve`. Receita prevista × devida × recebida × liquidada nunca somadas.
- **Gratuito até gerar valor** (`monetization_policy_versions` v1, hipótese): franquia de R$ 20.000 LIQUIDADOS em 12 meses, aviso
  prévio de 30 dias registrado (`remuneration_notices`), mínimo de fatura R$ 20, teto de 5 % do liquidado; `evaluate` só torna
  devida com regra ativa + franquia + aviso + teto, e registra o motivo de cada obrigação que não virou devida.
- **Recurso público** (`funding_source`, `public_instrument_ref`): obrigação nasce isenta; elegível só com instrumento e
  autorização registrada por `finance.approve` (correção do responsável: depende do instrumento, não é proibição universal).
- **Reserva institucional** (1,5 %) e fundo (4 %): destinação contábil da organização; motor `success_fee`, que o banco recusa
  ativar — nunca receita da plataforma. Taxa de serviço (1 % e 3,5 % institucional) reclassificada para `enterprise`
  (fatura à parte), INATIVA.
- **Estado comercial separado da prestação de contas**: `never_blocks`; vencida não bloqueia nada; teste varre as rotas.
- **Liquidado ≠ confirmado** (`settled_at`), **estorno parcial** (`refunded_cents`, `partially_refunded`), **compromissos de
  doação** (`donation_pledges`) e **recursos declarados fora da plataforma** (`external_resources`) — nunca na barra nem no razão;
  **painel do financiador** (`/v1/org/contributions`, doação em nome da organização).
- **Conciliação com fila de exceções** (`reconciliation_exceptions`, 9 tipos, prioridade, responsável, histórico; índice único por
  fato aberto; snapshot do provedor; sandbox deriva dos eventos assinados). Webhook recebido ≠ conciliado.
- **Totais por estado** na página pública e na gestão (pendente, confirmado, liquidado, em análise, estornado, compromissos,
  declarado fora), política de contagem e data da última atualização financeira válida.
- Telas: `/remuneracao`, `/contribuicoes`, `/admin/remuneracao`, `/admin/conciliacao`; gestão e página pública ampliadas.
- Documentos em `docs/finance/`: arquitetura (diagramas SVG/PNG), fluxos, razão e estados, política, matriz de monetização,
  matriz de riscos, jurídico/fiscal com as três correções do responsável, API/webhooks, cobertura dos 40 cenários, inventário,
  checklist de publicação/reversão, modelo de 24 meses em 3 cenários com sensibilidade (planilha + gráficos).
- **Etapa E6 — os 40 cenários com teste** (ADR-384, `test_v0340_open_scenarios`, 8 testes):
  - **cartão no sandbox**: faltava a tabela de tarifa do sandbox para cartão e toda doação por cartão era recusada
    (`provider_fee_unknown`) — achado do próprio teste; corrigido;
  - **falha temporária do provedor**: 503 `provider_unavailable`, nada gravado, a mesma chave repete com sucesso;
  - **webhook em duas fases**: o evento é gravado antes de ser aplicado; erro interno deixa o evento `failed`, abre exceção
    `event_processing_failed` e responde 500 (o provedor reenvia); a rotina reaplica; reentrega posterior é `duplicate`;
  - **liquidação acumulada** (`settled_cents`): parcial ≠ total, com exceção `settlement_partial` (esperado × observado);
    **falha de liquidação** vira exceção `settlement_failed` sem desconfirmar o pagamento;
  - **contribuição voluntária do doador** (`donation.platform_contribution`, hipótese INATIVA): valor A MAIS, começa em zero,
    separado no total e fora da arrecadação da campanha; é a única operação elegível a split (nada sai da doação); com split
    confirmado no evento a obrigação nasce recebida; sem split vira obrigação devida da organização, faturada à parte;
  - **recorrência**: autorização com consentimento por hash ≠ tentativa ≠ confirmado ≠ falha; pausa após 3 falhas seguidas;
    cancelamento pelo doador; rota de autorização desligada pela configuração até instrumento homologado;
  - **reembolso** do que a plataforma recebeu (integral, `finance.approve`; parcial é ajuste) e devolução da cobrança pelo
    provedor revertem a obrigação; **a organização não move a fatura da plataforma** (403 `platform_invoice`) — antes ela
    podia, pela rota de cobranças, marcar como paga ou devolvida a própria fatura;
  - **rotina `financial_ops`** no worker: reprocessa eventos, marca vencidas, concilia campanhas com movimento recente e cria as
    tentativas de recorrência (só com a recorrência ligada).
- **Etapa E7 — CI do pull request** (depois da primeira entrega do pacote, antes da tag): o job `pilha-do-zero` (pilha Docker do
  zero + jornadas + 218 telas + axe) estava **vermelho desde a v0.33.0** sem causa visível. Causa: na jornada "Captação" a
  pessoa anônima que doa era `Client()` — o cliente que sobe o servidor DE TESTE —, que não existe na pilha; a jornada parava
  no meio. Correção: `Http(self.base)`; teste-guarda (`test_the_journeys_never_start_the_test_server`, falha no código antigo);
  `scripts/demo_stack.py` põe cada falha de jornada/tela nas anotações do job (o log do job não é legível pela API aqui).
  Ao refazer o pacote: `FINAL_RELEASE_MANIFEST.json` listava como "novas" a migração e os módulos de teste da v0.30.0 (listas
  escritas à mão no gerador desde a v0.30.0); agora são derivadas da versão, com teste.
  Só código de teste/CI e o gerador do manifesto mudaram; o produto é o mesmo. O pacote 0.34.0 foi refeito e o anterior está
  registrado como substituído.
- Migração `0073_v0340_financial_ecosystem.sql`; +26 operações (962 → 988); `test_v0340_financial_ecosystem` (13),
  `test_v0340_open_scenarios` (8), `test_v0340_release_docs`.
- **Não feito, de propósito**: provedor real, split real, recorrência cobrada de verdade, cobrança ativa, NFS-e, assinaturas de
  plano (ADR-341), marketplace com take rate (recusado pelo responsável).

## [0.33.0] — 2026-10-10

### Doações, vaquinha e QR Pix como módulo isolado — sem custódia, sem provedor real, taxas inativas (ADR-372 a ADR-376)

- **Campanhas de doação** (`campaigns.kind = 'donation'`): meta, período, finalidade, "se a meta não for atingida" e política de
  estorno; fluxo rascunho → revisão (quatro olhos: quem criou não aprova) → aprovada → publicada; publicar exige termos
  aceitos e beneficiário verificado (`org_kyb_verifications`). O `PATCH status=published` legado responde 409.
- **Página pública `/campanha/:slug`** com barra de arrecadação só de pagamentos confirmados, formulário Pix com "cobrir
  custos" desmarcado, preço total e aviso "taxa = hipótese INATIVA" antes de pagar, QR versionado que aponta para a
  própria página (nunca para chave Pix), atualizações, gastos declarados e "o que esta campanha NÃO é".
- **Doação** (`donations`): idempotente, e-mail cifrado, anônimo nunca exposto; confirmação **só** por evento assinado do
  provedor no `POST /v1/webhooks/donations/{provider}` (idempotente por `provider+event_id`, valor conferido, reversão
  uma vez só); comprovante `IMP-DOA-…` com SHA-256, anulado em estorno — e que diz não ser recibo dedutível.
- **Razão em partidas dobradas** (`donation_ledger_entries`, só inserção, soma zero por transação): totais são "saldo
  contábil estimado — não é dinheiro guardado". **Nenhuma coluna de saldo.** `is_simulated` derivado por gatilho.
- **Provedor**: só `SandboxProvider` (`PIX-SANDBOX-NAO-PAGAVEL|…`). Matriz Asaas × Mercado Pago a partir das docs oficiais
  em `docs/donations/DONATIONS_PROVIDER_MATRIX.md`. Travas `LIVE_PAYMENT_PROVIDER_ENABLED`, `SPLIT_ENABLED`,
  `RECURRING_DONATIONS_ENABLED`, `RISK_HOLD_ENABLED` recusam `true` na configuração.
- **Taxas**: `donation.platform_fee` (1 %) e `donation.beneficiary_fund` (≤ 4 %) no catálogo, INATIVAS, com cartões
  jurídicos amarelos; versão congelada por doação; devido = R$ 0,00.
- **Risco (PLD proporcional)**: regras `donation-risk-2026-10.1` (`config/donation_risk_rules.json`), casos com decisão
  justificada; `payout_hold` não existe. Administração pode tirar do ar uma campanha publicada com justificativa.
- **Telas**: `/doacao/:id`, `/minhas-doacoes`, gestão em `/campanha-gestao`, `/admin/doacoes`, `/admin/doacoes/risco`.
- **Documentos** em `docs/donations/`: BASELINE_REPORT, IMPLEMENTATION_REPORT, SECURITY_REVIEW (modelo de ameaças),
  LEGAL_AND_PROVIDER_CHECKLIST, RUNBOOK, 24_MONTH_DONATIONS_NOTE (sem receita projetada).
- Migração `0072_v0330_donations.sql` (11 tabelas, 5 funções, GRANTs mínimos); 22 operações novas (940 → 962);
  testes `test_v0330_donations` (11) e `test_v0330_release_docs`.
- **Não feito, de propósito**: provedor real, split, recorrência cobrada, cobrança de taxa, recibo fiscal, e-mail ao
  doador — cada um com o bloqueio nomeado em `LEGAL_AND_PROVIDER_CHECKLIST.md`.

## [0.32.0] — 2026-10-09

### Correções da auditoria inicial: produção limpa, backup que restaura, worker com menor privilégio, CI verde (ADR-368 a ADR-371)

Decisões do responsável (09/10/2026): desativar as 15 contas de demonstração da produção; demo aberto a quem tiver o link;
código privado; trazer a branch `infra/v0.31.0` e resolver os achados da auditoria.

**Feito na produção (com autorização, pelo workflow `supabase`):** 15 contas `@demo.impacto.local` desativadas (sessões
encerradas na hora), 5 organizações só de demonstração suspensas, 11 itens de conteúdo público fictício fora do ar
(1 projeto, 7 soluções, 1 material, 2 editais); nada apagado; reversível (`contas-demo-reativar`). Execuções 37996712177,
37997211737, 37997481695.

**Backup:** o backup cifrado do R2 (20:43 UTC) foi baixado, conferido, decifrado e **restaurado** num PostgreSQL 17 descartável
com os verificadores de integridade (execução 37997867650). Novo job `ensaio-restauracao` (todo dia 1º e à mão); as instruções
de restauração do `backup-supabase.yml` foram corrigidas (um `pg_restore` direto falha); `managed_backup_restore.sh` aceita
`DUMP_FILE`.

**Código:** `scripts/demo_accounts.py` (listar/desativar/reativar, igual à tela de administração, auditoria, uma transação);
faixa "Ambiente de demonstração" no site quando o servidor está em `development` (`web/src/ui/demobanner.tsx`).

**CI:** teste de RLS reconhece a 0071 (nenhuma tabela sem RLS); matriz de integrações regenerada; manifesto da versão inclui a
análise econômica e os documentos novos. Para o repositório privado: suíte completa só em pull request; monitor de hora em hora.

**Operação:** `CLAUDE.md` com o novo comando do worker (`sh /app/start_worker.sh`), as ferramentas de operação e as regras
novas. Documentos `docs/ops/*_v0310.md` marcados como superados onde a realidade mudou.

**Testes novos:** `test_v0320_demo_accounts` (2), `test_v0320_release_docs`.

## v0.1 – auditoria inicial — 2026-10-09

> Numeração própria da série de documentos de auditoria (`docs/01` a `docs/04`). **Não muda a versão do produto**, que
> continua 0.30.0 no arquivo `VERSION` (o último commit da `main` se chama "v0.30.1"; ver `docs/02-auditoria.md`, M5).

Somente documentação, na branch `auditoria-inicial`. Nenhum código, configuração de deploy, variável ou chave alterado.

- `docs/01-estado-atual.md`: o que a plataforma faz hoje, o que está desligado de propósito, tecnologias, onde roda,
  estrutura de pastas e o resultado da suíte de testes executada nesta auditoria.
- `docs/02-auditoria.md`: problemas por gravidade — 2 críticos (contas de demonstração no banco de produção; chaves do
  backup expostas num chat), 6 altos, 11 médios, 4 baixos — cada um com prova e correção. Nenhum segredo no repositório.
- `docs/03-checklist-demo.md`: o demo já está no ar; passos para deixá-lo seguro para mostrar e separado da produção.
- `docs/04-roadmap.md`: 19 incrementos em ordem de urgência e 5 decisões do responsável.
## [0.31.0] — 2026-10-09

### Infraestrutura Railway Pro + Supabase Pro + Cloudflare R2 + Cloudflare: auditoria, prova de backup e preparação — sem publicar (ADR-364 a ADR-367)

Pedido do proprietário (pacote `IMPACTO_FINAL_FULL_RAILWAY_SUPABASE_R2_CLOUDFLARE_CLAUDE`): auditar o estado real antes de
alterar, provar o que puder, preparar staging e deixar produção bloqueada até aprovação humana.

**Comprovado:** baseline do pacote = tag v0.29.0 byte a byte (`docs/release/REPO_BASELINE_DIFF.md`); estado do Supabase por
leitura (runs 37974779816, 37975067994); **backup + restauração** do Supabase num banco descartável (run 37975650545: 341
tabelas, 2.577 linhas idênticas, RTO 15,1 s); imagem com o worker constrói no CI; adaptador S3 contra servidor S3 real.
**Não comprovado (sem acesso):** Railway, R2, DNS/Cloudflare, SMTP.

**Código**: `backend/start_worker.sh` (worker: `migrate --check` em laço, `impacto_app`, `jobs loop`; não migra nem rotaciona);
`config.validate` recusa região AWS com endpoint R2 e http em produção; `config.storage_is_ephemeral` → `/readyz`
`storage_durable` + aviso no log; `/healthz` → `commit` (`RAILWAY_GIT_COMMIT_SHA` / `IMPACTO_GIT_SHA`); Dockerfile copia o worker.

**Scripts**: `managed_backup_restore.sh` (dump de `public`, extensões recriadas no schema da origem, restauração com
`restore_test.sh`, contagem de todas as tabelas, recusa destino = origem); `restore_test.sh` ganha `RESTORE_KEEP_DB` e
`RESTORE_TOC_LIST` (padrão inalterado); `storage_smoke.py` (8 verificações com o adaptador do produto);
`supabase_check.py` mostra a linha do tempo dos lotes de migração e as sessões por papel/aplicação.

**Workflows**: `supabase` modo `backup-restaurar`; `ci` com job `armazenamento` (servidor S3 que valida SigV4 — as imagens
públicas do MinIO deixaram de ser baixáveis) e disparo manual; `armazenamento` (bucket R2 real, por ambiente); `pos-deploy`
substitui `deploy.yml` (que era modelo terminando em `echo`). Sem `railway.json`: Config as Code do Railway descontinuado.

**Documentos**: `docs/ops/INFRA_RAILWAY_SUPABASE_R2_v0310.md` (estado comprovado, configuração por serviço, variáveis,
16 achados P0/P1/P2, gates), `docs/ops/CHECKLIST_PROPRIETARIO_v0310.md`, `docs/release/REPO_BASELINE_DIFF.md`; a análise
econômica de 120 meses (`docs/analysis/economia_v0300/`, proposta) entra no manifesto desta versão.

**Testes novos**: `test_v0310_storage` (7 + 1 de protocolo no CI), `test_v0310_release_docs` (11), `test_v0300_economic_analysis` (6).

**O que NÃO foi feito** (declarado): deploy, DNS, criação de bucket, troca de senha, migração em produção — dependem do
proprietário; separação staging/produção do Supabase (decisão P0 do proprietário).

## [0.30.1] — 2026-10-09

### Feita em outra conversa, sem entrada no changelog na época (registrada aqui na v0.32.0)

- Migração 0071: revoga de `anon`/`authenticated` tudo no esquema `public` e liga RLS em `schema_migrations` (leitura para
  `impacto_app`) — resolve os 3 alertas críticos do Security Advisor do Supabase. PR #1.
- `jobs.pending_scans`: arquivo ausente no armazenamento não derruba a rotina (fica em quarentena como ilegível). PR #1.
- Workflows `backup-supabase` (diário, cifrado, R2) e `monitor`. PR #2. `CLAUDE.md` com a infraestrutura em uso. PR #3.

## [0.30.0] — 2026-10-09

### Pacote "Superprompts Master": baseline, evidência de primeira classe, dossiê longitudinal, mudança metodológica, economia do SaaS (ADR-360 a ADR-363)

Pedido do proprietário (pacote de 10 superprompts): inspecionar a base real antes de alterar, inventariar em quatro estados,
planejar P0/P1/P2 com evidência e critério de aceite, implementar o viável com testes, e fechar com regressão, versão, ZIP e
relatório — sem presumir que documento, rota, mock ou tela signifiquem funcionalidade pronta.

**Baseline** (`docs/execution/BASELINE_v0300.md`): inventário por contexto delimitado (PROVADO / PARCIAL / SÓ DOCUMENTADO / AUSENTE)
com o teste que prova cada linha; conflitos do material do pacote com decisões vinculantes registrados e **não implementados**
(escrow, retenção automática, assinatura, selo pago — ADR-363).

**Banco** (`migrations/0070_v0300_evidence_object.sql`): evidência com método de coleta, nível de acesso, base de consentimento,
classe de retenção, versão/substituição, contestação com motivo, máquina de estados no banco, histórico append-only
(`evidence_events`); `indicator_method_changes` + gatilho que exige motivo para mudar o método; tipos de lançamento
`evidence_contested`/`evidence_superseded`.

**Backend**: `GET /v1/evidences/{id}` (origem, uso, hash do documento, histórico, classificação, lacunas, aviso),
`POST /v1/evidences/{id}/contest`, rejeição exige justificativa (API + CHECK), substituição por `supersedes_id`;
`services/dossier.py` + `GET /v1/projects/{id}/dossier` (só para as partes); `PATCH /v1/projects/{id}/indicators/{pi}/method`.

**Front**: `/projetos/:id/dossie` (prontidão, marcos/obrigações, evidências por estado com qualidade, indicadores reportado ×
validado com método/unidade/descontinuidade, aportes e repasses, diligências, trilha — cada bloco com origem e atualidade;
"o que este dossiê não é" no topo); link na ficha do projeto para dona, candidato e financiador.

**Documentos gerados/novos**: `docs/execution/PROFILE_JOURNEY_MATRIX_v0300.md` (perfil × jornada × permissão × dado × ação, 16
jornadas / 256 passos), `docs/SAAS_ECONOMY.md` (pagador → valor → evento → preço-hipótese → custo → margem → alternativa, a partir
do catálogo real; matriz de elegibilidade de cobrança), sensibilidade do take rate 2–5 % em `24_MONTH_FINANCIAL_MODEL.md`
(hipóteses; o catálogo não mudou), `docs/execution/MILESTONE_FUNDING_STATES_v0300.md` (cada estado pedido → objeto/coluna/teste real).

**Contagens** (ADR-340): 940 operações (+4), 227 telas (+1), 70 migrações.

**Testes novos**: `test_v0300_evidence_object` (7), `test_v0300_dossier` (4), `test_v0300_release_docs` (8), `test_e2e_v0300_dossier` (1).
Expectativa atualizada com motivo: `test_v0190_lgpd_deletion` (evidência não é mais apagável — histórico append-only).

**O que NÃO foi feito** (declarado): escrow/BaaS, assinatura, selo pago (ADR-363); conflito de interesse por serviço profissional
(P2); versão das regras de elegibilidade guardada no resultado do match (P2); tudo o que depende de parceiro, parecer ou DPO.

## [0.29.0] — 2026-10-09

### Engenharia da base de conhecimento e ajuda contextual (ADR-353 a ADR-359)

Pedido do proprietário: incorporar a base de conhecimento v0.26.0 (58 controles O/A/V/H/D, 12 pesquisas) SEM retroceder a
release mais nova; governança editorial de ponta a ponta (fonte → direitos → citação → publicação → retirada → busca →
assistente → interface); busca medida antes de mudada; e um sistema global de tooltip, popover e glossário conceitual.

**Reconciliação** (`knowledge-base/`, `CONTROL-RECONCILIATION.json`): base versionada no git sem alteração; cada controle
LEG-001..058 classificado contra o código com os testes que o provam (IMPLEMENTED_TESTED 6 · PARTIAL 27 ·
BLOCKED_EXTERNAL 13 · NOT_IMPLEMENTED 12; 237 referências conferidas por AST).

**Banco** (`migrations/0069_v0290_knowledge_provenance.sql`): `kb_sources` (classe O/A/V/H/D, jurisdição, vigência, licença,
direitos de uso por operação com allowed/denied/unknown, verificação por outra pessoa, revisão marcada, hash, supersedes);
`kb_citations` (append-only; trecho só com direito permitido e hash conferido; só em rascunho); estado `retracted` terminal
com motivo em artigos/FAQs/recursos; `kb_work_items` + `kb_work_open()` (fila editorial deduplicada, só hash + tópicos);
RLS, grants, categoria de auditoria `kb`; 11 fontes semeadas `unverified` com revisão em 2026-11-07.

**Backend**: `services/kb_provenance.py`; 13 rotas (`/v1/help/sources`, `/v1/help/sources/{key}`, `/v1/public/concepts`,
`/v1/help/report-incorrect`, 9 de equipe editorial em `/v1/admin/content/*`); `knowledge.search()` abre `search_gap`;
`set_feedback()` abre `unhelpful`; `assistant()` reescrito: só publicado + oficial/educacional + não demo + não vencido,
uma fonte usada com citações, `excluded` com motivo, `ambiguous` em empate, abstenção explícita, `assistant_gap`.

**Busca medida**: `config/search_eval.json` (35 consultas), `engines/knowledge/evaluation.py`, baseline gravado como piso,
evidência `docs/evidence/search_eval_v0290.json`; tesauro 1.1 (hit@1 0,84 → 0,875; MRR 0,91 → 0,94). Sem embeddings.

**Ajuda contextual**: `config/concepts.json` (33 conceitos) → `scripts/sync_concepts.py` → `web/src/concepts.ts`;
`web/src/ui/help.tsx` (`Tooltip`, `InfoPopover`, `GlossaryTerm`, `ContextualHelp`, `GlossaryContent`) sem biblioteca nova;
página `/ajuda/glossario` (busca, filtro por área, âncora); aplicado em 11 telas reais; E2E Playwright (mouse, teclado,
toque, escuro, movimento reduzido, a11y, contraste). Correção colateral: `.pill-muted` no tema escuro (1,27:1 → ok).

**Contagens** (ADR-340): 936 operações (+13), 238 de plataforma, 54 públicas, 226 telas (+1), 69 migrações.

**Testes novos**: `test_v0290_knowledge_base` (27), `test_v0290_search_eval` (4), `test_e2e_v0290_contextual_help` (6).
Expectativas atualizadas com motivo: mensagem de abstenção do assistente (`test_v0120_knowledge`, `test_e2e_knowledge`);
lista de rotas públicas revisadas (`test_architecture`); contagens (`test_v0230_authorization_matrix`, `frontend_gate`).

**O que NÃO foi feito** (declarado): embeddings/vector DB/reranking (sem ganho medido); verificação das 11 fontes
(exige pessoa da área); retirada automática de conteúdo quando a fonte é retirada (decisão editorial); tradução dos
conceitos (en/es); conceitos em telas administrativas internas.

## [0.28.0] — 2026-10-09

### IA sustentável: catálogo de operações, cotas configuráveis, créditos por PIX, patrocínio, similaridade por dimensão (ADR-347 a ADR-352)

Pedido do proprietário: IA útil, acessível, governável e financeiramente sustentável — sem consumo ilimitado pago
pela plataforma, sem assinatura, sem excluir quem não pode pagar, sem cobrar o que não executou, sem confundir o
preço do cliente com o custo do fornecedor; e um motor de originalidade, similaridade, complementaridade e
integridade do financiamento que ajude a direcionar recursos sem penalizar projetos legítimos.

**Inspeção primeiro** (`docs/execution/AI_INVENTORY.md`): a camada de IA já tinha prompt versionado, faixa de risco,
uso registrado, tabela de preço (vazia), orçamento em dinheiro e razão de créditos — mas nenhuma chamada consumia
crédito, a cota era fixa no pacote e não havia prévia, fonte de custeio, patrocínio, pedido de crédito, execução com
estado nem conciliação.

**Banco** (`migrations/0068_v0280_ai_usage_control.sql`): catálogo versionado `ai_operations` (12 operações: 9
executáveis, 3 declaradas e NÃO implementadas → 501); `ai_executions` + `ai_execution_events` + grafo de estados
(`created → authorized → reserved → running → succeeded/failed/partial/cancelled → reconciled`); `ai_credit_ledger`
com lote (`purchased`/`promotional`), validade e motivos `purchase`/`sponsor_commit`/`release`; escrita só por
`ai_credit_post`/`ai_credit_consume_bucket` (SECURITY DEFINER com portão por motivo); `ai_quota_policies` +
`ai_quota_grants` (boas-vindas 60 — uma por organização E por pessoa; mensal leve 10); `ai_sponsorships` com
consumo e prestação de contas agregada por função SECURITY DEFINER; `ai_credit_packs` (3 hipóteses) e
`ai_credit_orders` (piloto/real) com grafo de estados; `platform_charges.kind = 'ai_credits'` e
`charge_requires_authorization` v3 (pedido consentido + regra ativa); 11ª regra de monetização `ai.credits_prepaid`
(review_required, carta amarela); `similarity_analyses` (append-only, cache por insumo+versão) e
`similarity_disputes`; `similarity_hidden_overlap` (k-anonimato ≥ 3); categoria de auditoria `ai`; `ai_credit_consume`
da 0058 vira invólucro da função por lote.

**Backend:** `engines/ai/usage_control.py` (prévia → autoriza → reserva → executa → liquida; débito só em sucesso;
idempotência; ordem de custeio gratuito → patrocínio → cota → comprado → recusa com opções);
`engines/similarity/engine.py` (local, oito dimensões, leituras separadas, recomendações, confiança);
`services/similarity.py` (RLS, cache, contestação); `services/ai_center.py` (central, pedidos, webhook, patrocínio,
painel financeiro medido × NÃO MEDIDO); `api/ai_center_routes.py` (+28 rotas: `/v1/ai/center`, `/preview`,
`/executions`, `/credit-packs`, `/credit-orders`, `/sponsorships`, `/v1/projects/{id}/similarity`,
`/v1/similarity/analyses`, `/v1/webhooks/payments/{provider}`, `/v1/admin/ai/finance|credit-orders|operations|
credit-packs|quota-policies|disputes`); gateway: `structure_need`, `draft` e `summarize` passam pela camada de uso
(provedor externo que falha = parcial, não cobra); `PAYMENT_WEBHOOK_SECRET`; dois motores novos no registro (50).

**Interface:** `/ia` (Central de IA: saldo por lote, cotas, operações com preço e quem paga, pedidos, patrocínio,
histórico, extrato, regras), `/ia/orcamento` (orçamento em dinheiro e política), `/ia/analises/:id` (dimensões,
leituras, recomendações, contestação), `/ia/patrocinios/:id` (prestação de contas), `/admin/ia/financeiro`
(menu Controladoria, `finance.read`); painel "Originalidade, similaridade e complementaridade" na ficha do projeto
com confirmação ANTES de executar (o que será feito, custo, quem paga, saldo, critério de conclusão, "se falhar nada
é cobrado"). 225 telas.

**Testes:** `test_v0280_ai_usage_control.py` (25: autorização/isolamento, cota uma vez por pessoa, prévia, débito só
em sucesso, concorrência, idempotência, portão do razão, pedidos piloto/real, webhook HMAC válido/inválido/repetido,
cobrança simulada nunca credita, patrocínio esgotado não migra, painel), `test_v0280_similarity.py` (13: conjunto de
avaliação rotulado com precisão/recall em `docs/evidence/similarity_eval_v0280.json`, confidencialidade k-anônima,
cache por versão, contestação, 50 candidatos < 2 s, arquitetura), `test_v0280_ai_cost_model.py` (4),
`test_e2e_v0280_ai_center.py` (3 jornadas no navegador); jornada demo "Central de IA" (16 jornadas, 256 passos);
contagens fixadas atualizadas com a razão escrita (923 operações, 229 de plataforma, 94 com permissão, 51 públicas,
225 telas, 50 motores, 11 regras).

**Documentos:** `AI_COST_MODEL.md` (gerado: piloto MEDIDO + hipóteses, 3 cenários × 12 meses, sensibilidades, as
doze perguntas, operação deficitária nomeada), `AI_PROVIDERS_EVALUATION.md` (fatos verificados na documentação
oficial: assinatura Claude.ai não paga API de terceiros; BYOK NÃO liberado), `docs/execution/AI_INVENTORY.md`,
`docs/execution/CLEANUP_INVENTORY_v0280.md`, `config/ai_economics.json`, `scripts/make_ai_cost_model.py`,
`scripts/measure_ai_pilot.py`, `DECISIONS.md` ADR-347..352, MONETIZATION §10, MONETIZATION_LEGAL_MATRIX (11ª
carta), EXTERNAL_INTEGRATIONS (webhook), AI_ENGINES (50). Snapshot da v0.27.0 em `history/v0.27.0/`.

**Limpeza:** 19 manifestos de versões anteriores (5,3 MB) movidos da raiz para `history/manifests/`; função de
consumo de crédito unificada; inventário do que ficou e por quê.

**O que NÃO foi feito, de propósito:** venda real de créditos (regra inativa até parecer; provedor de pagamento
ausente → modo piloto); BYOK; lote, monitoramento recorrente e relatório institucional (declarados `planned`,
rota 501); preço de produção (hipóteses de teste); custo de provedor (tabela vazia); NFS-e. Tag `v0.28.0` a criar no
GitHub pelo proprietário.

## [0.27.0] — 2026-10-08

### Não existem mais assinaturas: a receita nasce da operação financiada (ADR-341)

Pedido do proprietário: retirar a assinatura do modelo econômico — sem planos pagos, trial, checkout,
reajuste, paywall ou cobrança recorrente — e fazer o IMPACTO valer por **estar nele**: acesso a
recursos, demonstração e comprovação de evidência. 5% da operação financiada = 3,5% taxa de serviço
da plataforma + 1,5% participação de autoria do proponente (só quando contratualmente elegível, nunca
automática); percentuais do catálogo versionado, nunca em código; um aporte só do financiador,
direcionado a cada parte pela chave PIX do contrato; selos e reconhecimentos só na quitação.

**Inventário antes de apagar** (`docs/execution/SUBSCRIPTION_INVENTORY.md`): cada ocorrência de
assinatura/trial/preço/plano/checkout/paywall classificada KEEP / MIGRATE / DEPRECATE / DELETE, com
destino. Nada foi apagado às cegas.

**Banco** (`migrations/0067_v0270_no_subscription.sql`):
- §0 `legacy_subscription_archive` (append-only, só leitura privilegiada): antes de qualquer DROP,
  arquiva as linhas inteiras de `subscriptions`, `subscription_prices`, `price_change_notices`,
  `org_trials`, `trial_requests`, `plan_prices`, `plan_price_versions` e os valores das colunas que
  caem (`invoices/platform_charges/free_periods.subscription_id`,
  `voucher_redemptions.consumed_by_subscription`, `commercial_offers/offer_acceptances.price_version_id`,
  `commercial_offers.interval`, `plans.price_cents/interval`). Nenhum dado se perde;
- DELETE: as sete tabelas de assinatura/trial/preço e `price_current()`;
- MIGRATE: `plans` vira pacote de capacidades (sem preço, sem intervalo); `org_commercial_state` v2
  responde "de onde vem o acesso?" (FREE_ACCESS / FREE_GRANT / GRANT_EXPIRING / CONTRACTED);
  `commercial_offers` vira CONTRATO (avulso ou parcelado, `amount_reason`, `contract_ref`; nunca
  recorrente); `charge_requires_authorization` v2 aceita contrato aceito OU acordo de financiamento
  assinado pelo financiador com taxa (ADR-342); `entitlement_grants.source` ganha `contract`;
  `saas.institutional.funder` passa a `contract`/`contract`, recusada com carta vermelha;
- `economic_rules` Pricing Version **2027.02** (350/150 bps; 2027.01 permanece no histórico);
  `audit_action_categories` ganha `participation` e `payout`; `polymorphic_refs` cobre `recognitions`;
  plano de contas e categoria da central de ajuda renomeados.

**Backend:** `services/billing.py` removido; `monetization.py` reduzido a concessões (vouchers de
desconto aposentados — resgate recusa 409 `voucher_type_retired`); `entitlements.py`, `offers.py`,
`free_period.py`, `commercial_routes.py`, `monetization_routes.py`, `admin_routes.py`
(`POST /v1/admin/organizations/{id}/license` substitui `manual-subscription`), `auth.me`
(`subscription: null`), `economics/metrics.py` (`operation_revenue` substitui `recurring_revenue`),
`economics/payments.py` (sem `subscription`), `jobs.py` (sem `billing_lifecycle`), `config.py` (sem
`billing_provider`, `stripe_prices`, `trial_*`), eventos de integração `OPERATION.ACTIVATED/SETTLED`,
`PAYOUT.CONFIRMED`. Novos: `economics/master_tower.py` + `GET /v1/control-tower/master`
(`finance.read`): GMV × camada registrada/devida/paga por mês, participação, marketplace sem
percentual, uso, contratos, a receber, **banco: DADO FINANCEIRO NÃO CONECTADO**, captura de valor
(`NÃO MEDIDO` sem denominador); `network/today.py` + `GET /v1/me/today` (cartões do dia, selos,
progresso de onboarding, trajetória); reconhecimentos reconstroem a projeção pública
(`trajectory` cumulativa, contagens e datas, nunca valores); rotas financeiras (PIX, transferências,
confirmação, recusa, conciliação) exigem `OWNER`; ledger/reconhecimentos referenciam
`proponent_participation`, `allocation_payout`, `signed_agreement`, `agreement_allocation`.

**Interface:** `/conta/acesso` ("Acesso e concessões", sem checkout; `/conta/plano` redireciona),
`/controladoria/torre` (Torre MASTER), cartões do dia na página inicial (`TodayCards`, dispensa por
pessoa), trajetória no perfil público, "Como o IMPACTO se sustenta" na área comercial, painel de licença
na administração; `/ajuda/teste` e `/admin/central/testes` removidos (o painel de **demonstrações**, KEEP, passou para
`/admin/central/parcerias` — "Parcerias e demonstrações"); namespaces i18n
`subscription/checkout/cancellation` removidos. 221 telas.

**Testes:** `test_v0270_no_subscription.py` (nenhuma assinatura em lugar nenhum; torre master; cartões
do dia), `test_v0270_economy.py` (anti-bypass A–O), `test_v0270_financial_model.py` (documento =
gerador; percentuais = catálogo; aritmética), `test_v0270_release_docs.py` (matriz de motores = gerador;
28 seções do relatório; auditoria sem FAIL; integrações externas nunca declaradas ativas), `test_v0160_billing.py` removido com o módulo; 20
módulos reescritos para o modelo sem assinatura (ADR-340: contagens fixadas atualizadas com a razão
escrita ao lado — 895 operações, 220 de plataforma, 85 com permissão, 221 telas, 48 motores, 15 tipos
de evento de valor). Jornada `caminho_dourado` nas jornadas de demonstração.

**Documentos:** `docs/ECONOMIC_MODEL.md` (canônico), `docs/execution/SUBSCRIPTION_INVENTORY.md`,
`EXTERNAL_INTEGRATIONS.md`, `MOTOR_COVERAGE_MATRIX.md` (gerado: 48 motores, VERDE 35, AMARELO 13,
VERMELHO 0), `24_MONTH_FINANCIAL_MODEL.md` (gerado por `scripts/make_24_month_model.py` a partir de
`config/economic_model.json`: 3 cenários, 3 clientes/mês, sensibilidade R$ 50 mil → R$ 10 milhões, GMV
para R$ 1/5/10 milhões; receita real: R$ 0,00), `DECISIONS.md` ADR-341/342/343, PRICING_BIBLE (2027.02),
PRICING_RECONCILIATION R-40..R-43, MONETIZATION §9, VALUE_LEDGER (15 tipos), AI_ENGINES (48);
documentos de assinatura marcados SUPERADO (BILLING_V2, TRIAL_SYSTEM, FULL_FREE_2026, COMMERCIAL_TERMS,
docs/billing.md, docs/BUSINESS_MODEL.md, BILLING_ARCHITECTURE, MONETIZATION_ARCHITECTURE,
COMMERCIAL_UX_SPEC, DESIGNER_HANDOFF_MONETIZATION, BILLING_SECURITY). Snapshot da v0.26.0 em
`history/v0.26.0/`.

**O que NÃO foi feito, de propósito:** cobrança real (regra comercial desligada até parecer jurídico/
contábil externo); chave PIX real da plataforma (`PLATFORM_PIX_KEY` vazia → "NÃO CONFIGURADA");
provedor de pagamento/banco (conciliação continua manual, registrada e confirmada pelas partes);
preço de contrato (negociado por quem tem alçada; piso publicado não é preço). Tag `v0.27.0` a criar
no GitHub pelo proprietário (envio de tag recusado pelo proxy).

## [0.26.0] — 2026-10-08

### A tese econômica virou produto: contrato como regra, distribuição sem custódia, torres de controle, IMPACTO Ready

Pedido: transformar a tese ("infraestrutura de confiança, inteligência e execução; monetização como
consequência do valor; utilidade real, não dependência artificial") em produto funcional, sem
fintech dentro do IMPACTO (ADR-284) e sem inventar preço, parecer ou integração.

**Contrato como regra de operação** (`migrations/0064`, `trust/contract_rules.py`):
- cláusulas no acordo: `platform_fee_bps`, `fee_payer_role`, `fee_mode` (additional/deducted),
  `review_days`, `calendar_type` (dias úteis/corridos), `auto_accept`, `dispute_days`; congeladas
  após o rascunho por gatilho (`agreement_terms_frozen`);
- `agreement_versions` (append-only, RLS por parte): o `publish` registra a versão; `new-version`
  cria rascunho v+1, copia partes e marcos, marca a anterior `superseded`, dispensa as obrigações
  dela, e a assinatura antiga é recusada (409);
- `agreement_obligations` derivadas na ativação (entregar/aceitar/pagar por marco), com prazo pela
  política de aceite; `GET /v1/agreements/pending` lista o que espera decisão da organização;
- marcos com `seq`, `amount_cents`, `delivered_at`, `acceptance_due_on`, `accepted_at`,
  `rejection_reason`; `agreement_milestone_guard`: grafo de estados, quem reporta não aceita, quem
  aceita é parte do acordo, recusa exige motivo;
- razão do projeto recebe `agreement_activated`, `allocation_computed`, `milestone_delivered`,
  `milestone_accepted`, `milestone_rejected` (o aceite do financiador é escrito em contexto de
  sistema com o ator real).

**Matriz de distribuição e taxa na origem:**
- `agreement_allocations` (imutável, `CHECK allocation_sums`, hash): bruto, projeto, taxa, terceiros,
  linhas com quem paga a quem e por qual meio, versão de preços; `GET /v1/signed-agreements/{id}/allocation`
  devolve prévia antes da vigência e a matriz gravada depois;
- regra comercial `contract.platform_service_fee` (décima regra): `percentage = NULL` — o percentual
  é do contrato; nasce `active = false`, `review_required`, carta legal amarela com as perguntas
  abertas (arranjo de pagamento, ISS, nota fiscal). Com a regra ativa, a taxa vira **cobrança própria**
  (`platform_charges`, `manual`, simulada e declarada como tal) ao pagador; sem ela, fica registrada
  como "não cobrável" com o motivo. GMV não entra em receita.

**Torres de controle** (`migrations/0065`, `network/control_tower.py`, `api/tower_routes.py`):
- `GET /v1/control-tower/funder` + tela `/torre` (empresa, apoiadora): capital (= carteira), onde
  está/para quem/para quê, executado, evidência, o que mudou em 30 dias, atrasos, riscos (contagem
  por projeto + sinais), e "o que precisa da minha decisão" (obrigações, candidaturas, relatórios de
  impacto, evidências) com o link da tela onde se decide;
- `GET /v1/control-tower/government` + tela `/torre-territorial` (governo, plataforma):
  `gov_territory_overview` (SECURITY DEFINER, só governo/plataforma, só projetos publicados,
  k-anonimato ≥ 3), programas e editais do órgão, OSCs, por causa, indicadores declarados × validados,
  atrasos, lacunas territoriais.

**"Projeto IMPACTO Ready"** — `project_ready_facts` (SECURITY DEFINER que repete a regra de
visibilidade de `projects`), `GET /v1/projects/{id}/ready`, painel na ficha do projeto: 15 critérios
com tabela e contagem, `met`/`unmet`/`unknown`, `ready` só com todos atendidos, hash reproduzível;
quem não enxerga o projeto recebe 404. Não é selo.

**Interface:** `/acordos/novo` com as cláusulas; `/acordos/:id` reescrita (regras, matriz, partes,
entregas e aceite com botões por papel, recusa com motivo, obrigações, histórico de versões, nova
versão); `/torre`; `/torre-territorial`; painel Ready em `/projetos/:id`. Robô de telas ganhou
`TELAS_PRINT_DIR` (capturas em `docs/evidence/telas_v0260/`).

**Jornadas de demonstração:** nova jornada "Contrato como regra" (financiamento → vigência →
entrega → tentativa de autoaceite recusada → aceite → recusa com motivo → razão → nova versão →
assinatura antiga recusada) e, na jornada do governo, terceiro projeto publicado em MT (a torre
territorial sai do k-anonimato), torres e Ready.

**Testes:** `test_v0260_contract_rules.py` (8) e `test_v0260_control_towers.py` (8). Contagens
fixadas atualizadas com razão escrita: 894 operações, 220 telas, 45 motores (ADR-340).

**Documentos:** `docs/execution/TECHNICAL_BASELINE_BEFORE_EXECUTION.md`,
`SYSTEM_INTEGRATION_MATRIX.md`, `FINAL_EXECUTION_AUDIT.md`, `FINAL_EXECUTION_REPORT.md`;
`MONETIZATION.md` §8; `MONETIZATION_LEGAL_MATRIX.md` (décima carta); `NON_CUSTODIAL_ARCHITECTURE.md`
§4; `DECISIONS.md` ADR-336 a 340; `AI_ENGINES.md` e `ENGINE_COVERAGE.md` (45 motores).

**O que NÃO foi feito, de propósito:** cobrança real da taxa (regra desligada até parecer); nota
fiscal; snapshot histórico do estado Ready; o estado Ready como entrada do match; varredura que
marque obrigações `overdue` (hoje calculado na leitura); correções fora do escopo encontradas na
leitura da base (B1, B2 em `TECHNICAL_BASELINE_BEFORE_EXECUTION.md`). Tag `v0.26.0` criada
localmente; o envio continua recusado pelo proxy, como na v0.25.0.

## [0.25.0] — 2026-10-08

### Validação operacional de baixo para cima: banco → API → tela → jornada → resultado

Pedido: não basta "a rota abre". Provar, perfil por perfil, que o produto funciona do banco vazio
até o resultado da jornada, com Docker como teste de reprodutibilidade e o Supabase como modelo.

**O que passou a existir (e roda no CI):**
- **Robô das 218 telas** (`tests/screen_crawler.py`, `test_v0250_todas_as_telas.py`). Abre no Chromium
  todas as rotas do roteador, inclusive as que só abrem por link e as 52 com `:id` (usando registro
  real do qual o perfil participa), com os 6 perfis de demonstração e sem login. Toda tela restrita é
  aberta também por um perfil que não deve vê-la. Acusa erro de JavaScript, 5xx, "não encontrada",
  recusa indevida ou ausente, **chamada recusada escondida** por trás de tela que parece vazia, e
  **botão ou link sem ação** (com controle positivo: o detector acusa um botão morto plantado).
  Matriz: `docs/execution/ROUTE_RUNTIME_MATRIX.csv`.
- **13 jornadas pela API real** (`tests/demo_journeys.py`, `test_v0250_jornadas.py`): OSC (projeto →
  diagnóstico → equidade → indicador → 4 medições), financiador (edital → candidatura assinada →
  aprovação → aporte → pagamento → validação das medições), rede (proposta, conversa, relatório de
  impacto aceito), profissional (necessidade → oferta → revisão técnica aprovada), governo
  (chamamento → candidatura avaliada → necessidade do território), captação (cotas, apoios, campanha
  pública), documentos (montagem → acordo assinado pelas duas partes → registro verificável →
  compra com 3 orçamentos), marketplace, suporte e curso com certificado, banco de ideias (ideia →
  projeto), administração (com confirmação de identidade) e pendências. **Nenhuma escrita direta no
  banco** — até o plano das contas de demonstração vem da administração pela API.
- **Pilha do zero** (`infra/compose/demo/`, job `pilha-do-zero`): banco VAZIO com o desenho do
  Supabase (administrador sem superusuário, pgcrypto em `extensions`), PostgreSQL 17, imagem do
  produto, bootstrap do `impacto_app`, migrações, seed, aplicação como `impacto_app`; contra ela, as
  jornadas, as 218 telas, o **axe-core 4.10.2** (WCAG A/AA) e um reinício conferindo persistência.
- **Telefone** (`test_v0250_responsivo.py`): telas de menu dos 6 perfis em 390 px, sem rolagem
  lateral da página (com controle positivo).

**Defeitos que essas provas acharam, e que foram corrigidos:**
- `GET /v1/billing` respondia **500** para a administração (KeyError `tier`).
- `/projetos/:id/equidade` **quebrava** ao abrir (`methods` é objeto, a tela tratava como lista) e lia
  campos que a API não devolve.
- `/responsabilidade` chamava a API **sem os parâmetros obrigatórios** (422 para todo perfil) e lia
  campos inexistentes.
- **Confirmação de identidade (step-up) não existia na interface**: o servidor exigia, nenhuma tela
  pedia — interruptor de emergência, fechamento contábil e aprovações financeiras inalcançáveis
  pela tela. Agora o cliente da API abre a confirmação e repete a chamada (`ui/stepup.tsx`).
- 21 telas internas sem marcador de equipe mostravam erro com "Tentar novamente" a quem não é da
  equipe; agora mostram "área não disponível" (a permissão fina continua no servidor).
- 4 telas pediam a lista de projetos a quem não é OSC e levavam 403 escondido.
- `/solucoes/comparar` sem itens mostrava "Dados inválidos"; `/instituicoes/:id` mostrava o 403 cru
  a OSC e profissional; páginas de link de e-mail sem token mostravam 422.
- "Tentar novamente" em erro que não muda tentando (403/404/402/422) — removido.
- Concordância: "Conversa não encontrado", e frases já prontas viravam "não encontrada não encontrado".
- Central de Conhecimento: visitante sem login em conteúdo restrito via "não encontrado"; agora é
  convidado a entrar.
- **Acessibilidade (axe-core no CI):** 13 seletores sem nome acessível, barra de progresso sem papel,
  áreas com rolagem fora do alcance do teclado.
- **Inventário de telas errado:** o gerador lia só o ÚLTIMO tipo de cada rota e só a PRIMEIRA linha
  de cada menu. "119 telas só por link" eram 82; "OSC tem 19 itens de menu" eram 43.
- `infra/compose/docker-compose.yml` (homologação, não testado) passava ao entrypoint a conexão
  errada; corrigido e ainda declarado não testado.

**Demonstração:** nova persona Apoiadora (pessoa física, tipo `individual`) — sem ela, telas restritas
a "Apoiador" não eram alcançáveis por conta nenhuma.

**O que continua fora (AMARELO):** endereço público da demonstração (D-PUB1: exige conta de
hospedagem do dono); leitor de tela real; homologação das 14 integrações (credenciais de fornecedor).

## [0.24.2] — 2026-10-08

### Supabase verificado e aplicado de verdade, pelo GitHub

O dono do projeto cadastrou os segredos e rodou o fluxo `supabase` (detalhe e números de execução em
`docs/PUBLICACAO.md` §1-B). Resultado do `aplicar` (run 37727468920): migração `0063_v0240_…`
aplicada, `impacto_app` rotacionado e com uso de `extensions`, e a **imagem Docker subiu contra o
banco real** em `staging` endurecido — `readyz` 200, entrypoint completo, sonda das cadeias de hash
válida. Primeira prova de compatibilidade com **PostgreSQL 17.11** (a suíte roda na 16).

### O diagnóstico não dizia por que não conectava

As duas primeiras verificações falharam e o resumo só mostrava "exit code 1"; o motivo ficava no log.
- `scripts/supabase_check.py`: falha de conexão vira anotação de erro + resumo, com a causa provável
  (senha, usuário/região, host, porta) e o próximo passo. A mensagem do libpq não contém a senha.
- Segredo que não começa com `postgresql://` é recusado **antes** de conectar, sem repetir nada do
  conteúdo — na 1ª tentativa o rótulo "Valor:" do passo a passo foi colado junto e o libpq ecoou um
  pedaço do texto.
- Teste novo em `test_v0240_managed_db.py` (três URLs ruins; a senha nunca aparece; sem traceback).

### Consequência registrada

A instância publicada pelo terceiro parou de conectar: a senha do administrador foi trocada e a do
`impacto_app` rotacionada, por decisão do dono. O banco tem 1 usuário que não é de demonstração.

## [0.24.1] — 2026-10-07

### A suíte de testes nunca tinha rodado no GitHub

Pedido: construir a imagem Docker e resolver o que fosse preciso para o Supabase. Ao conferir o CI —
o GitHub tem Docker, este ambiente não —, todas as execuções recentes estavam vermelhas e ninguém
sabia em quê: o log bruto do Actions fica num blob da Azure, ilegível fora do navegador do GitHub.

Duas mudanças para enxergar: cada teste que falha vira **anotação** do check run, legível pela API
(`scripts/ci_annotate_failures.py`); e o job `docker` deixou de depender da suíte (`needs: backend`
escondia a resposta "a imagem constrói?" atrás de qualquer teste quebrado).

O que apareceu: o primeiro passo, `gitleaks/gitleaks-action@v2`, morria com "missing gitleaks
license" (a action exige licença paga em conta de organização). **Tudo depois dele ficava
"skipped" — lint, build do front, a suíte inteira, auditoria de dependências, o ciclo de
backup/restauração.** Toda afirmação de que "o CI valida X" valia só para este ambiente local.
Troca: o binário oficial (MIT), versão 8.30.1, conferido contra o arquivo de checksums da release.

### A primeira execução real: 105 erros que este ambiente escondia

`impacto_owner` e `impacto_app` são papéis da INSTÂNCIA, e três classes de teste lhes davam senha
própria sem restaurar — derrubando a conexão de todo teste seguinte. Aqui nunca apareceu porque o
PostgreSQL local autentica em `trust` (aceita qualquer senha); no CI ele confere. Uma das três era
minha, da v0.24.0. Agora há uma senha por processo em `support.py`, usada por todos. A correção foi
**reproduzida aqui** antes de ir ao CI: o PostgreSQL local passou a exigir senha (`scram-sha-256`),
como o do CI, e a suíte foi de 105 erros para zero.

Com senha exigida apareceu também uma corrida no auxiliar `fresh_totp`: ele gerava o código do passo
ANTERIOR, e quando a requisição cruzava a virada de 30 s o servidor já não o aceitava. Agora parte do
passo atual e, se os códigos da janela acabam, espera a próxima.

### Imagem e dependências — com prova do CI

- **A imagem Docker constrói** e recusa subir em produção sem segredos (job `docker`, verde).
- **D-SUP1 fechado**: `npm ci` instalou a árvore travada e o typecheck com `@types/react` oficial
  passou no GitHub (execução `37712067072`).

### gitleaks: 15 achados no histórico, nenhum é credencial

Senhas e segredos fictícios de teste, o literal de placeholder da Stripe com cliente HTTP falso, a
lista de senhas FRACAS que o cadastro recusa, uma linha de texto. `.gitleaksignore` libera por
impressão digital — um achado por linha, cada grupo com motivo, teste exigindo formato e contagem. O
comentário que escrevi explicando o placeholder citava o literal e foi achado também; está lá, com
motivo, porque o commit já estava publicado.

### Supabase

Este ambiente **não alcança o Supabase** (nem resolve o nome; a porta 5432 não passa pelo proxy), e
a conexão direta `db.<ref>.supabase.co` é IPv6 — que o GitHub Actions não tem. O caminho é o pooler
de sessão, por um workflow manual com a senha em segredo do repositório:

- `.github/workflows/supabase.yml`: `verificar` (transação READ ONLY + sonda que grava e desfaz) e
  `aplicar` (imagem em pé contra o banco em `staging` endurecido, com Mailpit descartável; migra,
  irreversível; exige digitar a confirmação). Nunca roda em push; nenhum input ou segredo é
  interpolado no shell.
- `impacto/db/app_url.py`: pelo pooler o usuário é `postgres.<ref>`, e o papel da aplicação tem de ir
  como `impacto_app.<ref>`; a troca antiga, embutida no shell, não sabia disso.
- `scripts/supabase_check.py`: diz o que falta migrar, o que o repositório não conhece (a
  `0063_v0231_…` de terceiro), se `impacto_app` é seguro e se **aceita a senha do administrador** —
  o defeito da publicação de terceiro. `IMPACTO_APP_ROTATE_PASSWORD=true` corrige, e derruba aquela
  instância.
- **O layout do Supabase foi reproduzido em teste** (pgcrypto em `extensions` antes da primeira
  migração): 63 migrações aplicam e as cadeias de hash calculam e validam; sem a 0063, `chain_audit`
  e `audit_verify` falham com o erro exato da publicação no Supabase. O modo `aplicar` foi ensaiado
  aqui sem Docker, em `staging` endurecido: `readyz` pronto, só `impacto_app` conectado.

### Segurança: a primeira auditoria de dependências achou vulnerabilidades reais

O passo de auditoria do CI também nunca tinha rodado. Com job próprio (`auditoria`, ~1 min) e
resumo por pacote, ele achou duas dependências de EXECUÇÃO com vulnerabilidades conhecidas:

- **PyJWT 2.14.0** — 2 vulnerabilidades; valida o `id_token` do login corporativo. → **2.15.0**.
- **pypdf 5.9.0** — 49 vulnerabilidades; lê **PDF enviado por usuário** para extrair texto. → **6.19.0**.

Versões de destino tiradas do próprio relatório. Depois da troca, a auditoria relatou 0 itens
(`pip-audit` e `npm audit --omit=dev`), a imagem construiu com as versões novas e a suíte rodou com
elas no CI. `SECURITY_AUDIT.md` deixou de dizer "bloqueado pelo ambiente" e passou a dizer o que foi
achado, em que execução, e o que mudou — sem afirmar ausência de falha.

### A segunda execução real: 6 problemas, todos de ambiente

- **PyYAML não estava em `requirements-dev.txt`**: o portão que lê os workflows nunca tinha sido
  importado no CI. Fixado em 6.0.3, a versão instalada aqui.
- **Os sete pacotes em faixa (`^`) foram fixados nas versões do lockfile** (`@types/react` 19.3.0,
  `@capacitor/*` 7.6.9 e 7.0.4). Antes isso seria inventar versão; o lockfile instalado por `npm ci`
  no CI é a fonte. O teste que tinha uma armadilha ("tudo está instalado, reveja este teste") foi
  revisto: agora exige que toda dependência declarada esteja no lockfile com a mesma versão exata,
  em qualquer máquina.
- **`GLOSSARY.md` embutia a data de hoje** e "saía de sincronia" a cada virada de dia — no CI, em UTC,
  isso acontece à noite no Brasil. O arquivo gerado passou a ser função só da fonte.
- **O inventário `web/INSTALLED_TREE.json`** registra a árvore que compila o build versionado aqui;
  no CI a árvore é outra (completa). A versão de cada pacote registrado é conferida em qualquer
  ambiente; o arquivo inteiro, com os hashes, só onde o conjunto de pacotes é o mesmo — o script de
  instalação do esbuild pode mudar o conteúdo entre duas instalações da mesma versão.
- `THIRD_PARTY_DEPENDENCIES.md` ainda listava a fonte Lora (removida na v0.24.0) e dizia que os
  ícones eram "próprios, gerados programaticamente"; agora diz de onde vêm e que a licença não está
  comprovada.

### Um gerador que perdia evidência

A matriz de personas buscava evidência por trecho só quando não havia casamento exato — e meu teste
novo, por conter a string `"verificar"`, desligou a busca que achava o teste de navegador de
`/verificar`. Agora busca sempre as duas; 49/49 seguem em PASS, e um passo subiu de travessia para
navegador (20 + 29).

## [0.24.0] — 2026-10-07

### Correção de registro, antes de qualquer novidade

A v0.23.1 anunciou "1 defeito real: `/entrar` chama `GET /v1/meta/config`, que o backend não
registra", em quatro documentos e num teste. **Estava errado.** A rota existe desde sempre, como
`Route` crua em `app.py` (`_infra_routes`, junto com `/healthz`, `/readyz`, `/metrics`,
`/v1/openapi.json` e `/v1/meta/taxonomy`), fora do registro `@route` que o cruzamento tela × backend
lia. O instrumento ignorava seis rotas e acusou o produto. Quem desmentiu foi o teste que sobe o
entrypoint do contêiner de verdade e recebeu a resposta completa da rota "inexistente".

O cruzamento passou a ler as duas fontes (894 operações: 888 registradas + 6 cruas), os guias dizem o
que aconteceu em vez de apagar, e a rota duplicada que esta versão chegou a criar foi removida antes
de entrar. Fica como lição escrita: um instrumento que lê um registro parcial produz acusações
precisas sobre a parte errada.

### Identidade oficial integrada

`web/brand/` é a fonte: `tokens.json` → `tokens.css` (gerado; um teste exige que seja exatamente a
saída do gerador), `components.css`, 75 ícones com catálogo, lockups transparentes, favicons, PWA,
Android/iOS, e os guias de origem inalterados. Os nomes que o CSS do produto sempre usou
(`--tinta`, `--ipe`, `--papel`, `--mata`…) viraram **aliases** dos `--pi-*` — toda regra de componente
vestiu a identidade de uma vez, nos três temas, sem reescrita regra a regra. Marca = imagem oficial
escolhida pela superfície (`ui/brand.tsx`), nunca desenhada em CSS; 48 ícones inline
(`ui/icon.tsx`), com **toda** rota de menu mapeada (teste). Lora saiu — a identidade não tem serifa;
Inter continua sendo o que renderiza, porque as fontes não vêm no pacote. Zero cor literal no CSS; as
duas ocorrências de texto branco sobre amarelo foram corrigidas, e a regra é conferida no botão
renderizado, não só no CSS.

Um defeito achado ao medir, não ao olhar: a barra lateral é flex em coluna com `overflow`, e os
filhos encolhiam — o logo oficial ficou com 24px e vazou por cima da caixa da organização.

O que a fonte declara sobre si e vale aqui sem suavizar: **licença da marca não comprovada**, **logo
master em raster** (303×240; nada é ampliado), **fontes não embarcadas**.

### A demonstração completa, provada no navegador

`test_v0240_demo_completa.py`: servidor real, seed, Chromium. 14 contas entram, **295 telas de menu**
abrem, zero 5xx, zero erro de JavaScript, marca renderizada em todas, temas claro e escuro, 390px sem
rolagem horizontal. As 10 contas internas passam pela **verificação em duas etapas de verdade**: o
seed cadastra TOTP nelas (segredo de `DEMO_TOTP_SECRET` ou gerado e impresso uma vez). Até aqui o
seed as criava sem segundo fator e 40 das 53 telas do administrador respondiam 403 `mfa_required` —
o produto estava certo, a demo é que estava incompleta. Relaxar o MFA para a demo não foi cogitado.

O teste precisou de duas correções nele mesmo: contava zero telas para persona sem menu e seguia
verde; e casava o `h1` "Entrar" ainda na tela, pulando a etapa do código. Os 4xx que sobraram
(`/documentos/montagens` em três tipos, sub-chamadas de permissão granular em perfis internos,
`/responsabilidade` sem período) estão no relatório de evidência e no guia do testador como achados.

### Contêiner e banco gerenciado, sem desligar travas

O pacote recebido trazia uma publicação no Supabase feita com o Dockerfile em `IMPACTO_ENV=development`,
seed ligado e domínio de terceiro fixado na imagem. Nada disso entrou (`TRIAGEM_PACOTE_UI_DEMO.md`,
item a item). Entrou, corrigido: `backend/start_container.sh` (bootstrap → migrações → troca para
`impacto_app` → ASGI; `IMPACTO_APP_PASSWORD` obrigatória, nunca derivada da URL administrativa),
`bootstrap_external.py`, e a migração `0063` cobrindo as **nove** funções que chamam `digest()` (a
recebida cobria cinco). `test_v0240_container_entrypoint.py` executa o script contra um banco limpo
criado pelo administrador: 63 migrações, `/readyz`, aplicação conectada como `impacto_app` e não
como administrador, seed e login. O Dockerfile volta a `production`; demonstração é decisão de quem
sobe, nunca da imagem.

### Lockfile

`web/package-lock.json` versionado (veio de fora, gerado com rede): coerente com `package.json`, 128
pacotes com `integrity`, versões instaladas aqui conferem — testes. `npm ci` continua sem execução
aqui (D-SUP1 parcialmente fechado).

## [0.23.1] — 2026-10-07

### O inventário de telas estava incompleto, e o teste que o guardava não guardava nada

Esta versão não muda o produto. Muda o que a documentação afirma sobre ele — e corrige uma afirmação
que estava errada.

**179 telas eram 218.** `web/src/app.tsx` tem TRÊS tabelas de rota, tentadas nesta ordem: `PUBLIC`
(9 telas, abrem sem login), `HELP` (30, Central de Conhecimento) e `ROUTES` (179, aplicação
autenticada). O extrator lia só a última. As 39 de fora não sumiam com erro: um inventário menor
continua parecendo um inventário.

**E o teste que deveria pegar isso conferia a contagem contra o mesmo recorte que o extrator lia.**
Passava com 179 de 218 sem reclamar. Instrumento que se confere contra o próprio recorte não confere
nada. A conferência passou a varrer a região inteira das rotas por um método que não é o do extrator,
e a exigir que as três tabelas apareçam. O número foi confirmado por três caminhos independentes:
extrator, `grep` direto, e a subtração dos itens de menu do total de ocorrências no arquivo.

Quatro defeitos de extração, todos silenciosos, estão agora escritos no código que os causou: âncora
no fim da linha (perdia a segunda rota de linhas com duas), `[` do tipo `R[]` em vez do da lista
(zero telas), terceiro elemento exigido como lista (perdia as 30 de `HELP`, cujo terceiro elemento é
`true`), e primeiro `=` depois de `const` (que em `[string, () => ReactNode][]` é o `=` de `=>`,
perdendo as 9 de `PUBLIC`).

### Cruzamento tela × backend: o que tem interface, o que não tem, o que não é chamado

`scripts/make_screen_backend_map.py` lê as chamadas dentro do corpo de cada componente exportado e
confere contra as 888 operações registradas por `impacto.http.ROUTES`.

- **157 telas** chamam operação registrada; **60** não chamam a API diretamente.
- **231 das 888 operações** não têm nenhuma referência no front. O backend está à frente da interface,
  e agora isso é um número medido em vez de uma impressão.
- **1 defeito real encontrado:** `/entrar` chama `GET /v1/meta/config`, que o backend não registra —
  só existe `GET /v1/meta/platform-status`. A chamada está dentro de um `.catch(() => {})`, então
  falha calada e o botão de SSO nunca aparece. Travado por teste: corrigir o produto passa a exigir
  atualizar o que foi dito publicamente sobre ele.

Seis "telas sem backend" que o primeiro cruzamento acusou eram defeito do cruzamento, não do produto:
uma era template aninhado (``…${pid ? `?x=${pid}` : ""}``) cortado na crase de dentro, cinco eram
`${mode}` interpolando um literal que o backend registra. E "569 operações sem interface" virou 231
quando o extrator passou a enxergar `useLoad(caminho)`, o envoltório por onde o front faz quase todo
GET.

### Painel navegável das telas, compartilhável e anotável

`scripts/make_screen_panel.py` monta uma página só, gerada do inventário, para publicar como artefato:
filtro por tipo de organização, por alcance e por estado de backend, busca, e revisão por tela —
verde (aprovada), amarelo (ajustar), vermelho (bloqueada) — com nota, salva fora da página e
compartilhada entre quem abre o link. O cabeçalho da página diz, antes de tudo, que aquilo é o
inventário do roteador e **não** a aplicação rodando.

### Três documentos que faltavam

`docs/DEMO.md` (o que dá para mostrar e, item a item, o que não dá e de quem depende),
`docs/TESTER_GUIDE.md` (como testar, o que já se sabe que está quebrado, e o que o teste manual não
prova) e `docs/TROUBLESHOOTING.md` (falha por falha, com a mensagem exata do código, a causa e o que
fazer). Os números que os três citam são conferidos contra os JSON gerados por um teste — documento
que cita número gerado e não é conferido envelhece calado.

## [0.23.0] — 2026-10-07

### Rodada de conclusão da auditoria (pacote de execução, 11 portões)

Uma auditoria externa foi convertida em backlog de engenharia com 11 portões e 4 matrizes
obrigatórias. Todos os portões foram percorridos; o que não pôde ser executado está `BLOCKED` com
causa escrita, nunca mascarado como `PASS`.

**Divergência de versão, real e corrigida.** `backend/pyproject.toml` e `web/package.json`
declaravam `0.14.0` enquanto `VERSION` dizia `0.23.0`. O runtime lê `VERSION`, então o produto
funcionava e os dois arquivos ficaram parados por nove versões. Corrigidos, com teste exigindo que os
quatro declarantes concordem.

**Quatro matrizes, geradas do produto e travadas contra deriva.** 888 operações de API (lidas do
ROTEADOR, não do OpenAPI, que é derivado), 42 motores, 14 integrações, 49 passos de persona. Cada uma
é regerada em diretório temporário e comparada byte a byte com a versionada — um CSV versionado sem
essa trava é uma fotografia que continua parecendo completa no dia em que alguém adiciona uma rota.

**A matriz de integrações parou de ler o banco.** `maturity` é promovível pela administração, e um
teste promove `totvs` a `homologated` no meio da suíte. Uma matriz gerada naquele instante declararia
homologação real de um provedor jamais homologado. Passa a ler o catálogo embarcado, com teste
exigindo que nada embarque acima de `contract_tested`.

**Duas travessias novas**, pelo que a matriz de personas mostrou faltar: denúncia → análise →
contraditório → manifestação → conclusão → medida → recurso → julgamento, e o incidente do
interruptor de emergência. Cada regra já estava provada isolada; o CAMINHO nunca era percorrido.

**Segurança: 9 de 10 executados.** 165 testes. SSRF recusa 22 grafias do mesmo destino interno e a
isenção de loopback é conferida morrendo em produção; CRLF testado por socket cru; injeção de SQL
provada pela carga que volta IDÊNTICA. Varredura de segredo própria (gitleaks ausente) **com controle
negativo**. SCA **não executado** — nenhuma base de vulnerabilidade é alcançável do ambiente.

**Dados e infraestrutura, executados do zero** contra PostgreSQL 16.15: 62 migrações, 322 tabelas,
321 com RLS, 667 políticas, 0 com `FORCE RLS`; backup, restauração em banco limpo com verificação
completa, e controle negativo com dump adulterado em um byte. `/readyz` passa a ter os dois ramos de
503 testados — o caminho feliz era o único coberto.

**Quatro testes que vazavam estado entre arquivos** foram corrigidos sem serem enfraquecidos: três
forjam cadeias de hash para provar detecção e agora restauram o valor original.

**O que esta rodada NÃO afirma:** nenhuma homologação de integração, nenhuma conformidade WCAG 2.2 AA
plena, nenhum teste de intrusão, nenhum SCA, e **nenhuma garantia de inviolabilidade** — nenhum
sistema conectado à internet pode recebê-la.

### O que esta rodada fez, e o que ela recusou fazer

Quatro prompts mestres pediram: camada de IA transversal (170 seções), motor de auditoria e
rastreabilidade, infraestrutura (Vercel/Supabase/R2) e frontend. Mais um portão de segurança com a
regra absoluta *"não declare que o sistema está 100% impossível de invadir"*.

A primeira coisa que esta rodada fez foi **auditar o que já existia**, e o resultado está em
`AI_AUDIT.md` e `PLATFORM_AUDIT_v0230.md`. Duas conclusões organizaram todo o resto:

1. **A base é mais madura do que os prompts supõem.** 745 rotas, 1 806 testes, RLS em 312 de 313
   tabelas com 653 políticas, 41 tabelas append-only, cadeia de hash em duas trilhas, 60 testes
   adversariais, 319 chamadas de auditoria. Pedir "crie um motor de auditoria" a uma base que já
   tem trilha append-only encadeada por hash levaria a refazer o que funciona.
2. **A pilha de referência do prompt não é a desta plataforma.** O prompt descreve
   Supabase + Vercel + Next.js + R2; esta plataforma é Python/Starlette com PostgreSQL 16
   auto-hospedado e React/esbuild. O próprio prompt diz, na primeira regra, *"não substitua
   componentes que já estejam funcionando corretamente apenas por preferência"* — então a
   infraestrutura **não foi trocada**, e os requisitos de segurança dela foram aplicados à pilha
   real. Está escrito em `PLATFORM_AUDIT_v0230.md` §0.

As lacunas reais eram específicas e quase todas pouco glamourosas. Seguem.

### Segurança: o token de renovação que não vencia

`issue_session()` gravava `refresh_expires_at = now() + 30 dias` em **toda** rotação, inclusive na
mesma família. Efeito: trinta dias contados sempre do último uso nunca vencem para quem está usando
— **um refresh token roubado e renovado dentro da janela sobrevivia indefinidamente**. A família
passa a ter idade máxima própria (`family_started_at`, propagada nas rotações) e limite de
inatividade, os dois configuráveis, com teste exigindo que ambas as configurações tenham leitor
fora de `config.py` (a lição de `LOGIN_MAX_ATTEMPTS`).

`verify()` devolvia o contador TOTP aceito e o docstring dela dizia *"para impedir reuso"* desde
sempre — e **nenhum dos quatro chamadores usava o valor**. `verify_once()` queima o contador, e o
gatilho `totp_counter_moves_forward` recusa retrocesso inclusive para o dono do banco.

O defeito encontrou o teste: `test_mfa_flow_and_recovery_code` reaproveitava o MESMO código para
ligar o MFA e reautenticar, e só passava porque o reuso era possível. Cinco auxiliares de teste
dependiam disso.

### Segurança: o alerta que não existia

A plataforma **detectava** reuso de refresh token — o sinal mais forte de roubo de sessão que ela
sabe produzir —, revogava a família de sessões, auditava e notificava o **titular**. Ninguém da
operação era alertado.

Duas séries passam a sair de dois pontos de estrangulamento (`services/audit.py::record()` e
`ops/runs.py::_fechar()`), e há 16 regras de alerta com catraca provando que toda série citada
existe, que todo rótulo é ação declarada e que todo nome em `SECURITY_ACTIONS` tem produtor.

### Segurança: o script de restauração que ninguém executava

`scripts/restore_test.sh` confere o sha256 do dump, restaura num banco descartável, verifica as três
cadeias de hash e prova que o restore não traz estado que não deveria existir. **Nada o chamava** —
nem CI, nem Makefile, nem suíte. É literalmente o defeito que `ops/backup.py` critica na primeira
linha: *"script que ninguém executa não é backup"*.

Agora o CI roda o ciclo completo com os papéis reais **e** com um dump adulterado de propósito que a
restauração tem de recusar. Conferir o hash de um arquivo que ninguém alterou prova pouco.
Verificado localmente: 62 migrações restauradas, cadeias íntegras, dump adulterado recusado.

E o CI ganhou varredura de segredo (gitleaks, com histórico completo). Não havia nenhuma, em lugar
nenhum: o fail-fast de `config.py` protege o BOOT, não o histórico do git.

### Interruptor de emergência

Cinco escopos. Histórico append-only; o estado é **derivado** por gatilho SECURITY DEFINER e a
aplicação não tem UPDATE na tabela de estado — é isso que torna impossível parar a plataforma sem
deixar o evento. Super-administrador, reautenticação, motivo de no mínimo 10 caracteres travado no
banco.

As três formas de errar um interruptor de emergência, cada uma com teste:

* **cegar a auditoria** — isenta em todos os escopos, leitura e escrita;
* **trancar-se do lado de fora** — a rota que libera não é bloqueada pelo que ela libera;
* **trancar a equipe que responde** — o escopo `logins` é aplicado em `issue_session()`, depois de
  saber quem entra, e deixa a equipe interna passar.

A porta de entrada ficou fora do ponto de estrangulamento HTTP de propósito: a primeira versão
tratava login como escrita qualquer, e o modo somente leitura **prometia** "consultas seguem
disponíveis" enquanto ninguém podia entrar para consultar.

### Proveniência: de onde veio este número

`indicator_values.evidence_id` era nulo permitido e a tabela não tinha gatilho nenhum. Um valor
chegava a `validated` — o estado que o produto apresenta como conferido — sem apontar documento
algum. A trava que existia conferia QUEM validou, não **com base em quê**.

Agora: origem declarada, `validated` **exige** evidência (CHECK, que nem o dono do banco escapa),
origem congelada depois da validação. Medição autodeclarada continua permitida; autodeclarada
apresentada como validada, não.

`GET /v1/indicator-values/{id}/provenance` devolve a cadeia inteira — projeto, indicador, linha de
base e fonte, documento com sha256 e versão, quem enviou, evidência, quem revisou, medição, quem
validou e de qual organização, lançamentos do Impact Ledger com `seq` e hash, eventos de auditoria —
**e `gaps`**, que nomeia cada elo ausente com o efeito dele sobre o que o número prova. Cadeia que
esconde o elo que falta transforma ausência de prova em aparência de prova.

A regra do motor de alegação que detectava "medição validada sem evidência" **não foi removida** por
ter virado impossível: virou detector de manipulação, e o teste simula o único caminho que ainda o
produz — acesso ao banco removendo a restrição.

### Integridade: a verificação que era uma string

`scripts/db_integrity_report.py` publicava, como resultado da verificação de órfãos:

```
SELECT 'nenhuma verificação de órfão aplicável: toda referência é FK declarada'
```

Uma **string literal**. Não consultava nada, e a afirmação é falsa: há **25 colunas de referência
polimórfica** no banco, nenhuma pode ter chave estrangeira, e eram exatamente as que precisavam de
verificação.

Agora há catálogo das 26 colunas, resolução tipo→tabela conferida contra o catálogo do PostgreSQL,
exceções com motivo escrito, e três relatórios: órfãos, tipos não resolvidos e **deriva de
catálogo**. O terceiro é o que mantém os dois primeiros honestos — e já provou o próprio valor:
acusou `ai_credit_ledger.ref_id` no instante em que a coluna nasceu, nesta mesma rodada.

### Correção no Impact Ledger e cadeia no Value Ledger

`ledger_entries` é append-only e encadeada, e **não havia caminho para corrigir**: só restava o
UPDATE que a tabela recusa, ou deixar o erro. O tipo `correction` aponta o lançamento que corrige,
exige valor oposto exato, motivo escrito, uma correção por lançamento e recusa correção de correção.

`value_events` — a tabela que sustenta o número principal do posicionamento do produto — era a
**única das três sem cadeia de hash**. Linhas anteriores ficam sem cadeia de propósito e isso é
relatado: hash calculado para trás produz uma cadeia que parece verificada sem nunca ter protegido
nada.

### Máquina de estados no banco

O grafo de transição de candidatura existia em Python e protegia **uma** rota. `rascunho →
encerrada` por UPDATE direto passava. Agora vale no banco, com erro que diz quais transições são
permitidas, e candidatura não nasce aprovada. A duplicação Python/banco é autorizada por um teste
que compara aresta por aresta.

### Motor de auditoria: onze campos e uma árvore

`actor_type`, `session_id`, `user_agent`, `correlation_id`, `parent_event_id`, `resource_name`,
`severity`, `status`, `source`, `before_state`, `after_state`. **Nenhum dos 319 chamadores foi
alterado**: quem preenche é `Ctx.audit()`, o ponto por onde todos passam.

A cadeia de hash sobreviveu à mudança de esquema por **material versionado**: a versão 1 é
literalmente a fórmula anterior, a 2 acrescenta os campos novos. Calcular o material novo sobre
linhas antigas seria reescrever a história para que ela feche.

`GET /v1/admin/audit/timeline` responde "tudo o que aconteceu com ESTE documento";
`/trail` responde "que acontecimento levou a qual", com profundidade. E `POST /v1/admin/audit/export`
**registra a própria exportação na trilha** — era a única leitura privilegiada sem registro nela, e
é a que mais interessa a quem pretende apagar rastro depois.

`forbid_mutation` é gatilho DE LINHA e não vê **TRUNCATE**, que não dispara gatilho de linha nenhum.
Quem tivesse privilégio de dono apagava a trilha inteira numa instrução sem quebrar hash algum,
porque não sobrava hash para quebrar. Seis tabelas ganharam gatilho `BEFORE TRUNCATE`.

A categoria do evento virou **dado**: a primeira versão derivava de um `CASE` no código e cobria as
nove categorias do prompt — e o teste mostrou que a base tem 86 prefixos de ação com **68 caindo em
OTHER**. Filtro que joga 79% dos eventos em "outros" não é filtro.

### Camada de IA: governança do que existe

Dos 42 motores, **3 chamam modelo**. Isso é desenho, não lacuna — um motor de diagnóstico que
inventa a nota é pior que um que a calcula. O que faltava não era mais IA; era governança.

* **Registro de prompt com versão.** As instruções viviam em literal no gateway: mudar uma frase
  mudava o resultado de todo cliente sem registro, e nada ligava uma saída guardada à instrução que
  a produziu. Os cinco prompts foram publicados com o texto **exato** que estava no código.
* **Política por faixa de risco**, do USO e não do modelo. A faixa 3 (afirmação sobre terceiro) não
  sai da instalação; a faixa 4 (efeito jurídico) é **inoperante por construção**, para dizer que
  nenhum uso dela está implementado.
* **`status` que diz a verdade.** O código gravava `'ok'` sempre, inclusive descartando a resposta
  externa por inválida — e a tabela dizia que o provedor externo funcionou.
* **Crédito ≠ token**, com razão append-only, consumo atômico por bloqueio consultivo e
  idempotência. Dez consumos simultâneos de 10 contra saldo de 50 deixam passar exatamente cinco.
* **Orçamento em dinheiro**, separado da cota: uma chamada de 200 mil caracteres consome o mesmo da
  cota que uma de 200. Padrão é **avisar**, não parar.
* **CNPJ** entrou na redação de dado pessoal. CPF estava e CNPJ não — e CNPJ aparece em todo
  documento desta plataforma.
* **Conjunto de referência** com 10 casos sobre os motores determinísticos, fixando invariantes e
  não saída exata, com contraprova para cada invariante.

O que **não** foi feito, com motivo, risco e o que seria necessário: embeddings, cache semântico,
fallback entre provedores, lote, ferramentas e agentes. Está em `AI_FINAL_AUDIT.md` §3.

### Frontend

Seis telas novas: Centro de Segurança da conta, painel de IA da organização, linha do tempo de
entidade, cadeia de causa, proveniência e interruptor de emergência. Mais integridade dos dados.

Nenhuma tem dado de exemplo: **tela de auditoria com dado fictício é pior que tela ausente**, porque
treina quem opera a confiar no que está vendo. E nenhuma usa cor como único sinal — quem confere um
acesso suspeito pode ser daltônico, ou estar num celular ao sol.

Os dois defeitos que a v0.22.0 encontrou por auditoria (menu que prometia o que a porta recusava;
tela lendo sete chaves que o servidor não devolvia) viraram testes nesta versão:
`TheScreensCallRoutesThatExistTests` e `TheResponseKeysTheScreensReadAreActuallyReturnedTests`.

### Defeitos que a própria suíte encontrou nesta rodada

Vale registrar, porque nenhum foi contornado afrouxando trava:

* **Guarda de código morto derrotado por acento.** A expressão `[A-Za-z_][A-Za-z0-9_]*` não casa
  identificador acentuado: `_é_equipe` era tokenizado como `_` + `_equipe` e a função aparecia como
  morta sendo chamada. A mesma classe de defeito do guarda de RLS derrotado por espaço em branco.
* **Guarda de contagem única da cota de IA reprovando por coincidência.** Procurava duas frases no
  mesmo ARQUIVO. Guarda que reprova por coincidência é guarda que alguém afrouxa.
* **Interruptor que nunca bloqueava.** A primeira versão de `killswitch.py` usava `c.all()`, que não
  existe nesta camada de banco: a leitura do estado falhava, caía no ramo de erro e devolvia
  "liberado". O ramo que engoliu o defeito agora CONTA a falha, porque um interruptor que não
  consegue ler o próprio estado é incidente de segurança, não aviso de log.
* **Toda rota de IA devolvendo 500.** O gateway lê o prompt dentro da transação da organização, e a
  RLS de `ai_prompts` é privilegiada.
* **Interferência entre arquivos de teste.** O teste do verificador de alegação forja uma medição
  validada sem evidência e deixava a linha no banco, fazendo a cobertura de proveniência reprovar em
  OUTRO arquivo.

### Dívida declarada

`web/package-lock.json` **não existe**: o registro npm devolve 403 neste ambiente e
`npm install --package-lock-only` falha no primeiro pacote. Escrever um lockfile à mão com hashes de
integridade que ninguém verificou seria inventar justamente o artefato cuja única função é ser
verificável. Está em `TECHNICAL_DEBT_REGISTER.md` como **D-SUP1**, com o erro real, o comando que a
fecha e o que foi feito no lugar: as quatro dependências que entram no pacote construído estão em
versão exata, e o CI gera o lockfile como artefato para commit.

### Migrações

0051 (sessão e TOTP) · 0052 (interruptor) · 0053 (proveniência e correção) · 0054 (integridade) ·
0055 (máquina de estados) · 0056 (auditoria) · 0057 (categorias e TRUNCATE) · 0058 (governança de
IA) · 0059 (publicação dos prompts) · 0060 (visão pública de prompt) · 0061 (acesso ao prompt) ·
0062 (catálogo de integridade).

### Números

| | v0.22.0 | v0.23.0 |
|---|---|---|
| Testes | 1 806 | **2 069** |
| Migrações | 50 | **62** |
| Documentos | 141 | **144** |

### Documentos novos

`AI_AUDIT.md` · `PLATFORM_AUDIT_v0230.md` · `AUDIT_ENGINE.md` · `PROVENANCE_ENGINE.md` ·
`AI_FINAL_AUDIT.md`

## [0.22.0] — 2026-10-06

### A regra que governou esta rodada

> *"Não implemente uma fintech dentro do IMPACTO só porque isso parece aumentar a monetização.
> Primeiro prove que a mesma receita e garantia operacional podem ser obtidas com uma arquitetura
> de software/orquestração muito mais simples."*

A auditoria dessa exigência encontrou algo melhor do que uma lista de coisas a remover: **a regra já
era verdadeira no código**. `split`, `payout`, `recipient`, `repasse`, `escrow`, `wallet` e saldo de
terceiro têm **zero ocorrências** em 325 módulos Python e 45 arquivos de frontend, e **zero** nas
298 tabelas. A v0.20.0 havia *removido* `attach_pix()` e `attach_boleto()` justamente porque, sem
provedor, chamá-las exigiria valor inventado.

O trabalho desta rodada foi, então, **provar, documentar e travar** isso — e decidir item por item
quais pedidos de fintech recusar. `NON_CUSTODIAL_ARCHITECTURE.md` (ADR-284) é o resultado, e está
acima dos outros documentos de arquitetura.

### Autorização: o fim do booleano único de administrador

O achado central: havia **um booleano** para toda a equipe interna. Quem tivesse
`users.is_platform_admin` alcançava as 193 rotas administrativas então existentes — receita apurada,
custo de IA, fatura, tabela de preços — **sem nenhum papel financeiro no caminho**. Os três papéis
nomeados que existiam eram todos de conteúdo.

- **14 papéis internos**, não hierárquicos, independentes do tipo da organização ativa.
- **`permission_catalog`** (o que existe: 43 permissões, 3 exclusivas com motivo escrito obrigatório)
  separado de **`staff_permissions`** (quem tem o quê: 65 mapeamentos com nota), ligados por chave
  estrangeira.
- **A permissão é chave na porta** (`permission=` em 62 rotas), com recusa diferente para quem é da
  equipe e para quem não é.
- **Step-up**: 17 permissões exigem identidade confirmada nos últimos 15 minutos. Três cópias de
  reautenticação viraram uma, e a exclusão de conta ganhou MFA de brinde.
- **`privileged_access_log`** append-only responde *quem olhou*, e não só *quem mudou*.
- **`super_admin` concedido por gatilho de banco**, cobrindo migração, linha de comando, seed e
  console — quatro caminhos que uma concessão na aplicação deixaria de fora.

### Motor financeiro: CALCULA, INSTRUI, CONCILIA

- **Contabilidade por competência** com partida dobrada de verdade: lote que não fecha é recusado;
  conta sintética, conta inativa e competência fechada recusam lançamento; lançamento é indelével;
  fechamento recusa competência com lote torto.
- **43 contas**, **11 centros de custo**, despesa da plataforma com *quem registra não aprova* por
  restrição de tabela, orçamento versionado com orçado × realizado.
- **Instrução de pagamento é documento**: congela valor e beneficiário na emissão, exige evidência
  para ser registrada como executada, e exige aprovação concluída na faixa do valor.
- **Alçada por valor** com 8 faixas em dado no banco; dois gatilhos: quem pede não aprova, e faixa
  de duas assinaturas recusa a mesma permissão duas vezes.
- **Conciliação que aponta e não corrige**, em quatro conferências.
- **Métricas que dizem de onde vieram** — e que respondem `available: false` **com o motivo** no
  lugar de zero. Churn, LTV, CAC e custo de IA estão nesse estado, declaradamente.
- **Take rate: nem alíquota declarada, nem cobrança.** A regra `marketplace.take_rate` existe com
  `percentage = NULL` e `active = false`, e a função devolve `fee_cents: null` com motivo
  `percentage_not_declared` — porque devolver um número sem alíquota seria inventar a alíquota.
  Quando houver decisão comercial, o percentual entra no dado e a função passa a calcular, ainda
  recusando a cobrança enquanto a regra estiver desligada: cobrar percentual sobre contrato de
  terceiro sem contrato assinado e sem nota fiscal própria é receita inventada.

### Operação interna: 16 telas para 224 rotas que não tinham nenhuma

26,4% das rotas não tinham tela — a saúde do sistema, a receita apurada, as tarefas agendadas e o
Integration Hub inteiro. Construído, funcionando, invisível.

- **`/portal`**: a cadeia *quem entra → organização → perfil → função → plano → recursos → situação
  financeira → painel* resolvida no servidor e **mostrada** na tela.
- **Controladoria, Financeiro, Contabilidade, Tesouraria, Administrativo, Operações, Auditoria**,
  mais plano de contas, despesas, instruções, períodos gratuitos, aprovações, conciliação, matriz de
  permissões, alertas e integrações.
- **Health Center** reunindo três rotas que nenhuma tela chamava.
- **Central de Alertas derivada do estado real**: não há tabela de alerta, porque não há alerta sem
  causa — cada linha aponta o registro que a originou e desaparece quando a causa é corrigida.
- **O menu interno passou a vir do servidor**, derivado das permissões. A barra lateral era lista
  fixa no frontend, igual para toda a equipe: quem atendia chamado via "Cobrança por organização" e
  "Auditoria" no menu e levava 403 ao clicar.

### Limpeza

- **Duas tabelas de trilha de tarefa → uma.** `job_runs` (22 tarefas, sem duração e sem campo de
  erro) e `ops_job_runs` (2 tarefas, com as duas coisas) davam respostas diferentes para "o backup
  rodou?". Histórico migrado, tabela antiga **removida** do esquema, um só gravador.
- **Dicionário `SUPER_ADMIN_ONLY` em Python apagado**: discordava do banco.
- **Nome de tarefa montado a partir de dado** (`import:<nome da fonte>`) virou nome constante.

### Demonstração

`seed-demo` passou a criar **seis contas internas por função** e dados em todas as telas
financeiras: três competências (a mais antiga fechada), nove lotes balanceados, cinco despesas,
orçamento com 48 linhas, quatro instruções e quatro aprovações pendentes. Era impossível abrir
qualquer tela financeira e ver algo — e, com um administrador único, a separação entre quem atende
chamado e quem vê receita existia no banco e não aparecia para ninguém.

### Auditoria independente, depois de a suíte estar verde

Com 1.772 testes passando, a rodada passou por uma **auditoria independente** feita por quem não
produziu o trabalho, com instrução de verificar cada afirmação contra o código e o banco em vez de
ler a documentação. Ela encontrou onze defeitos reais, e os quatro primeiros tornavam telas
financeiras inúteis ou enganosas:

1. **A decisão de aprovação nunca chegava ao objeto aprovado.** O pedido fechava como `approved` e
   a despesa ficava em `registered` para sempre: não existia um único `UPDATE platform_expenses` em
   todo o código. O painel mostrava "A pagar R$ 0,00" ao lado da despesa total, a posição líquida
   da tesouraria **superestimava** o caixa, e a conferência de "despesa paga sem lançamento"
   apontava para um estado inalcançável. Corrigido no gatilho (migração 0050), não no handler —
   porque o handler é um caminho e o gatilho é o único.
2. **O menu oferecia o que a porta recusava**, em quatro papéis — exatamente o defeito que esta
   versão declarava ter fechado. E o teste citado como prova era **tautológico**: comparava a
   permissão do item com a lista de permissões da pessoa, que é a mesma lista por onde o menu já
   filtra. Cinco itens exigiam permissão que nenhuma rota declarava.
3. **A tela de orçamento chamava `/v1/administrativo/orcamento` e a rota era `/budget`**: erro em
   toda abertura, e nenhum teste conferia as chamadas de API das telas.
4. **Sete indicadores do painel executivo liam chaves que a resposta não tem** — `revenue.gross` em
   vez de `gross_revenue`, `cash.inflow` em vez de `cash_in`, `burn.*` em vez de `result.*`. O
   componente devolvia `null` para chave ausente, então não havia erro visível: receita bruta,
   receita líquida, entradas, saídas, queima e autonomia simplesmente **desapareciam** do painel.
5. **O custo de IA respondia zero, disponível** — a condição curto-circuitava com zero chamadas.
6. **`last_updated` estava prometido na documentação e ausente da resposta.**
7. **Oito rotas devolviam HTTP 500** por parâmetro de URL malformado (`?period=abacaxi`), e
   `?days=-5` virava uma janela no futuro em que a conciliação não achava divergência nenhuma.
8. **`billing.write` e `free_period.write` estavam isentas de reautenticação** sob um comentário que
   dizia o contrário: a primeira dá baixa em fatura de cliente, a segunda concede gratuidade.
9. **Tentativa de acesso privilegiado recusada não deixava rastro em lugar nenhum** — nem na trilha
   (não chegava) nem em `audit_events` (que só registra alteração).
10. **A documentação afirmava "a regra de 10%"** e não existe alíquota nenhuma no banco.
11. **Nove testes não rodavam na execução direta do arquivo**: `unittest.main()` estava no meio
    dele, antes de três classes serem definidas.

Tudo corrigido, e **cada achado virou teste**. Nove testes fracos foram reescritos para exercitar
o que o nome deles afirma: o da taxa confere o valor em dois ramos; o do MRR cria a assinatura em
sandbox em vez de ler a frase do campo `calculation`; o do GMV lança receita e confere que o GMV
não se move; o dos quatro olhos confere a restrição **nomeada**, porque o INSERT violava duas e
remover a certa deixaria o teste verde.

### Defeitos encontrados e corrigidos

Treze, todos por teste. Os mais instrutivos:

1. **`admin.users.write` era inalcançável por todos.** Permissões exclusivas não estão em
   `staff_permissions` por definição, e `staff_permissions_of()` lia o mapeamento — então nem o
   super administrador as recebia. Corrigido separando catálogo de mapeamento.
2. **Ter a permissão não bastava para passar pela porta.** Criar o papel `finance` dava acesso a
   nada.
3. **Precedência de operador mandava a contabilidade para a controladoria.**
   `"finance.approve" in p or "finance.read" in p and "accounting.read" in p` é `A or (B and C)`.
4. **Guarda de RLS derrotado por espaçamento.** `test_every_table_has_rls` lia
   `CREATE POLICY \w+ ON (\w+)`; duas declarações alinhadas com espaços sumiam da conferência — e,
   pior, alinhar um `CREATE TABLE` faria a *tabela* sumir, deixando passar uma tabela sem RLS.
   Corrigidos a formatação **e** o guarda.
5. **`close_period()` passava um parâmetro a menos** do que a consulta pedia: a função nunca
   registrou quem fechou a competência. Encontrado no primeiro teste que a exercitou.
6. **`budget.write` e `cost_center.write` estavam fora do step-up.** Quem muda a régua muda o
   resultado de todas as medições feitas depois.
7. **A unificação da trilha estourou em `import:<nome da fonte>`** e revelou que o nome da tarefa
   carregava parâmetro em texto livre vindo do cadastro.

### Testes

**1.806 testes, verde, 26 ignorados** (454 s). **123 novos nesta versão**, em três arquivos:
`test_v0220_authorization.py` (34), `test_v0220_financial_engine.py` (53),
`test_v0220_internal_ui.py` (36).

**Nenhum teste foi enfraquecido ou removido.** Dois ficaram obsoletos pela unificação da trilha de
tarefas e foram **reescritos mais exigentes**: passaram a cobrar duração de execução e ausência de
erro — exatamente o que a tabela antiga não sabia registrar. E um guarda de arquitetura foi
**endurecido** no mesmo movimento em que o defeito que ele deixou passar foi corrigido.

### Banco de dados

Migrações **0046** (papéis e permissões), **0047** (motor financeiro), **0048** (trilha única de
tarefas) e **0049** (carimbo de aprovação de despesa).

### Pendências externas (inalteradas)

Provedor de pagamento, provedor fiscal, provedor de WhatsApp, chave de mapas, chave de IA e fonte
governamental ao vivo. Todas com adaptador, contrato, configuração e tratamento de erro prontos.

## [0.21.0] — 2026-10-06

### Monetização: a infraestrutura comercial deixou de estar vazia

A auditoria desta rodada encontrou **toda a infraestrutura de preço construída e sem um único
valor**: versionamento com gatilho de imutabilidade, aviso de 30 dias, aceite congelado — e
`plan_price_versions` com 0 linhas, 7 planos pagos com `price_cents = NULL`. E nenhuma ocorrência de
"FULL FREE" no repositório inteiro.

### Adicionado

- **`PRICING_BIBLE.md`** no repositório como fonte de verdade comercial, e
  **`PRICING_RECONCILIATION.md`** com a matriz REGRA → LOCALIZAÇÃO → STATUS → GAP → IMPLEMENTAÇÃO →
  TESTE (39 regras auditadas).
- **Pricing Version 2027.01**: 8 versões de preço vigentes em BRL, 2 pisos de proposta publicados,
  5 planos gratuitos. Nenhum valor escrito em código — teste varre Python e TSX.
- **`free_periods`** (migração 0042): gratuidade temporal **por conta**, com origem, motivo, versão
  de preço e autor. FULL FREE 2026 e 3 meses de calendário para assinaturas novas de 2027.
  `ends_at` exclusivo; fuso comercial `America/Sao_Paulo` na fronteira, UTC no armazenamento.
- **`commercial_offers` + `offer_acceptances`** (migração 0043): **ACESSO GRATUITO ≠ AUTORIZAÇÃO DE
  COBRANÇA**, com os 14 campos do aceite e gatilho de banco que recusa cobrança sem autorização
  vigente.
- **Parcelamento distinto de recorrência**; boleto parcelado exclusivo para CNPJ, validado no
  servidor; `idempotency_key` escopada por organização em eventos financeiros.
- **Motor de uso** (migração 0044): `usage_counters`, `usage_alerts` com limiares de 70/90/100%,
  `spend_limits` com `warn` ou `hard_stop`.
- **Avisos comerciais** 90/60/30/7/1 dia + semanal nos últimos 30, a partir de `FREE_PERIOD_END`
  como fonte única; tarefas `commercial_sweep` e `usage_alerts`.
- **Interface comercial**: página pública de preços (`/planos`), situação comercial, consumo e faixa
  de período gratuito. **82 chaves de i18n comercial em 10 namespaces, nos três idiomas** — antes
  havia zero.
- **108 testes novos** (`test_v0210_*`), incluindo fronteira temporal segundo a segundo na virada
  2026→2027 e as cinco datas de assinatura exigidas.
- Documentos: `FULL_FREE_2026.md`, `MONETIZATION_ARCHITECTURE.md`, `BILLING_ARCHITECTURE.md`,
  `PRICING_VERSION_2027_01.md`, `PRICING_CATALOG.md` (gerado), `COMMERCIAL_TERMS.md`,
  `COMMERCIAL_UX_SPEC.md`, `BILLING_SECURITY.md`, `PRICING_BENCHMARKS.md`, `UNIT_ECONOMICS.md`,
  `24_MONTH_FINANCIAL_MODEL.md`, `DESIGNER_HANDOFF_MONETIZATION.md`.

### Corrigido

- **Exigência de autorização podia ser burlada.** Gatilhos `BEFORE INSERT` disparam em ordem
  alfabética, e o de autorização vinha antes do que deriva `is_simulated` do provedor: bastava
  enviar `is_simulated = true` com provedor real para escapar. Ambos passaram a consultar
  `charge_is_simulated(provider)`.
- **`FORCE ROW LEVEL SECURITY` quebrava o `pg_dump`.** Nenhuma outra migração do projeto usava; a
  proteção real é o gatilho de imutabilidade, que vale para todos. Achado pelo teste de backup.
- **Reajuste agendado quebrava a migração.** Fechar vigência em `now()` viola
  `effective_until > effective_from` quando a versão ainda não começou — defeito presente desde a
  v0.16.0, invisível enquanto o catálogo estava vazio.
- **Cota de IA contada de dois jeitos**: o painel podia mostrar mais consumo do que o que de fato
  bloqueava. Função única `ai_usage_this_month()`.
- **`company_premium` com intervalo errado**: o catálogo anunciaria R$ 1.490 **por ano** para um
  plano de R$ 1.490 por mês.
- **`BILLING_V2.md`** descrevia a regra em dólar da v0.16.0, aposentada na v0.17.0 — divergência
  entre documento e código, agora declarada no topo do arquivo.

### Alterado

- `config/plans.json` → `plans@3.0`, com `pricing_version: "2027.01"` e `quote_floor_cents`.
- Testes que afirmavam a realidade comercial da v0.17.0 ("nenhum preço fixado") foram **reescritos
  para afirmar a invariante que permanece**, não removidos: todo preço declarado nomeia a versão e a
  decisão que o criou, e um plano sem preço anual publicado continua sem economia anual.

### Não feito, e por quê

- **Take rate de 10% permanece inativo.** A ADR-022 é barreira estrutural: sem custódia do valor, a
  cobrança não é verificável e o repasse pode exigir autorização do Bacen (Lei 12.865/2013). A
  própria `PRICING_BIBLE.md` §20 condiciona o take rate a `service + contract + transaction`.
- **As 11 minutas jurídicas continuam em `draft`.** Aprovar minuta é ato humano.
- **Sem valor anual** para PROFESSIONAL PRO e FUNDER PRO — a Bíblia não publica, e não foi inventado.
- **Unit economics sem números** — ver ADR-280.

## [0.20.0] — 2026-10-06

**Fechamento da engenharia antes do Designer.** Rodada de auditoria, não de funcionalidade,
dividida em onze etapas. Cada etapa procurou a diferença entre o que a plataforma **afirmava** e o
que ela **fazia** — e encontrou, quase sempre, mecanismo escrito, testado e **inalcançável**.

**1.557 testes, 0 falhas** · 837 operações · 42 motores · 41 migrações · 293 tabelas.
Decisão: **GO** para o Designer · **NO-GO** para publicação web (motivos contratuais e jurídicos,
não de código).

### Corrigido — mecanismos que existiam e não alcançavam nada

- **Quinze tipos de aviso não pertenciam a interruptor nenhum.** 29 chamadas a `app_notify` usavam
  prefixos que não casavam com grupo de preferência algum: a pessoa desligava todas as preferências
  que a tela oferecia e continuava recebendo aviso de conformidade, candidatura, pagamento,
  evidência, validação profissional e situação institucional. Corrigido por **catálogo + gatilho no
  INSERT** (migração 0041), não por 29 reescritas — o gatilho vale também para o quarto caminho que
  alguém escrever sem ler.
- **Três funções existiam e nunca eram chamadas:** `proposals.expire_due` (proposta vencida ficava
  em `sent` para sempre e `Proposal.expired`, que notifica, nunca acontecia),
  `marketplace.expire_due` e `seals.recheck` (selo cujo critério caiu continuava exibido). Ligadas
  como tarefas.
- **Dezoito eventos de domínio declarados e nunca emitidos**, incluindo `Document.attached` — o caso
  que originou o módulo de notificação. Dezessete passaram a ser emitidos; o décimo oitavo
  (`Security.session_reuse_detected`) foi **retirado da declaração**, porque o caminho não consegue
  emiti-lo.
- **Doze motores fora do inventário**, entre eles a camada de impacto inteira.
- **`scripts/import_ods_targets.py` não existia** — `IMPACT_FRAMEWORK_AUDIT.md` afirmava desde a
  v0.18.0 que a rodada o entregava. Escrito; a afirmação falsa corrigida sem apagar o erro.
- **`.docx` era aceito no envio e subia sem texto extraído:** os leitores existiam, nenhum estava
  ligado ao extrator.
- **A bandeira `public_directory_providers` não ligava nada.**
- **O reuso de credencial de sessão** derrubava todas as sessões da família e não avisava a dona da
  conta.
- **`charge_events`:** a rota de detalhe de cobrança lia uma trilha que eu concluí, erradamente, que
  ninguém escrevia (o `count(*)` era zero porque o banco de desenvolvimento estava vazio). A suíte
  pegou a duplicata que eu introduzi, o código foi revertido, e há teste impedindo que código de
  aplicação escreva ali.

### Acrescentado

- **Denúncia em quatro níveis** (migrações 0038, 0039): denúncia → suspeita → infração apurada →
  consequência jurídica. `enforcement_needs_substantiated_report()` é **gatilho**: medida sem
  apuração concluída é recusada pelo banco. Direito de manifestação e recurso. A escada de dez
  degraus passou a restringir sete capacidades de verdade.
- **Procedência de dado externo** (migração 0040): `external_datasets` imutável, com publicador,
  licença, sha256 e as duas datas. `data_freshness()` com quatro estados — `undeclared` **nunca**
  vira `current`.
- **Aceite legal no cadastro** (migração 0037): a conta era criada sem registrar aceite nenhum.
- **Motor de qualidade de dado** (§69): sete achados sobre o dado, cada um apontando para a linha
  exata, e **nenhuma nota** — cinco testes impedem que baixa qualidade de dado vire baixo desempenho
  de projeto.
- **Inventário de risco por operação** (§40): 383 LOW, 273 MEDIUM, 171 HIGH, 10 CRITICAL, com o
  controle humano que cada nível exige e conferência no código. As dez críticas têm o controle.
- **Tabela de cobertura dos motores** (§99): seis colunas — implemented, integrated, tested, E2E,
  security, observability — **todas derivadas do código**, nenhuma declarada.
- **As seis telas que faltavam** (§94): reputação, selos, afirmações, equidade, ODS,
  responsabilidade.
- **Benchmark de preço** (§47–48, §89): 12 linhas lidas nas páginas dos próprios fornecedores;
  `PRICE_FINALIZATION_REQUIRED` ligado e planos com preço nulo.
- **Varredura de prazos**: a plataforma registrava cinco prazos e varria um.
- **`GET /v1/privacy/retention`**: a política de retenção que o titular dos dados não conseguia ler.

### Removido

`attach_pix()` e `attach_boleto()` (gravavam instrução de pagamento que só provedor brasileiro
produz — sem provedor, código que se ligado mente), `retry_serializable()` (contradizia a estratégia
escolhida) e mais nove funções nunca chamadas, duas delas escritas nesta própria rodada.

### Testes

+180 testes: `test_v0200_legal_acceptance` (7), `test_v0200_complaints` (28),
`test_v0200_provenance` (22), `test_v0200_notifications` (25), `test_v0200_engines` (16),
`test_v0200_quality_risk` (23), `test_v0200_screens` (15), `test_v0200_pricing` (13),
`test_v0200_adversarial` (35), `test_v0200_cleanup` (14). Duas varreduras estruturais novas: por
`min_role` e por `kinds` — a suíte provava que uma estranha não entra e não provava que quem já está
dentro não faz o que não deve.

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
