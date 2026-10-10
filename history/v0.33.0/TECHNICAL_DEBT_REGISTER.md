# Registro de dívida técnica — v0.19.0

> Uma linha por item, com impacto, solução, esforço, dependência, risco de não corrigir e as duas
> perguntas que decidem a fase: **bloqueia o Designer?** **bloqueia a publicação web?**
>
> Severidade: **CRITICAL** (corrigir antes de publicar) · **HIGH** (corrigir na primeira janela
> depois do design) · **MEDIUM** · **LOW** · **FUTURE**.

## v0.20.0 — dívida encontrada pelo inventário de risco (§40)

### D1 · Dezesseis operações de alto risco sem controle conferível de perto

`GET /v1/admin/risk-levels` classifica as 836 operações da API e confere, no código alcançável a
UMA chamada da rota, se o controle humano que o nível exige existe. **As 10 operações CRÍTICAS têm
o controle.** Dezesseis operações de alto risco não têm controle conferível nessa distância:

* `POST /v1/billing/quote`, `/cancel`, `/reactivate`, `/change-plan`, `/portal`
* `POST /v1/billing/webhooks/stripe`
* `PUT /v1/admin/content/article-versions/{id}`, `/resources/{id}`, `/faqs/{id}`, `/courses/{id}`
* `POST /v1/admin/content/events/{id}/attendance`
* `POST /v1/admin/support/tickets/{id}/to-article`
* `POST /v1/integrations/inbound/{connection_id}`
* `POST /v1/admin/fee-tables/{table_id}/items`
* `PUT /v1/payments/charges/{charge_id}/installments`
* `POST /v1/payments/charges/{charge_id}/transition`

Parte disto é limitação da varredura, não da operação: a transição de cobrança, por exemplo, tem
a trilha escrita por GATILHO (`charge_record_event`, migração 0022), e varredura estática não
enxerga gatilho. Parte pode ser ausência real de registro. **Não foi conferido caso a caso**, e
dizer que foi seria o tipo de afirmação que esta rodada inteira existe para evitar.

Há catraca: `test_the_high_risk_gap_cannot_grow` reprova a suíte se o número passar de 16.

### D2 · Oito motores não deixam rastro durável

`ENGINE_COVERAGE.md`, coluna `observability`: `funding_readiness`, `document_classification`,
`evidence`, `report_center`, `solution_scoring`, `intent_parser`, `glossary_drift` e
`retention_policy` calculam e não registram que rodaram. Depois do fato, não há como responder
"este motor rodou? com qual versão?". São todos motores de leitura/derivação, o que explica a
ausência mas não a resolve.

### D3 · Uma correção que esta rodada quase introduziu como defeito

Acrescentei um `INSERT INTO charge_events` em `economics/payments.transition`, convencido por uma
contagem zerada em banco de desenvolvimento vazio de que a trilha da cobrança não era escrita por
ninguém. Era: pelo gatilho `charge_record_event()`, desde a v0.17.0. A suíte reprovou
(`test_the_trail_is_written_by_the_trigger_and_is_append_only`) e o código foi revertido. Fica
registrado porque o erro é instrutivo: **tabela vazia em ambiente de desenvolvimento não é prova
de que ninguém escreve nela.** Há agora um teste que impede qualquer código de aplicação de
escrever nessa trilha.


## CRITICAL — nada aqui bloqueia o Designer; tudo aqui bloqueia a publicação

| # | Item | Impacto | Solução | Esforço | Dependência | Risco de não corrigir | Bloqueia design? | Bloqueia web? |
|---|---|---|---|---|---|---|---|---|
| C1 | **Auditoria de dependências não executada** (`npm audit`, `pip-audit` bloqueados pelo ambiente) | CVE conhecido pode estar no bundle sem ninguém saber | rodar em ambiente com registry, anexar saída em `docs/evidence/`, exceção formal por achado não corrigido | 1–2 h | registry acessível | publicar com vulnerabilidade conhecida de terceiro | **Não** | **Sim** |
| C2 | **Nenhum provedor externo real configurado** (SMTP, S3, antivírus, pagamento, fiscal, IdP) | o produto funciona em modo simulado; e-mail não sai, arquivo não sobe para armazenamento durável, vírus não é barrado | configurar por ambiente e rodar o smoke com `--base` do ambiente real | 1–2 dias | contas e credenciais do proprietário | publicar um produto que não entrega e-mail nem guarda arquivo | **Não** | **Sim** |
| C3 | **Minutas legais sem aprovação de advogado(a)** (11 documentos em rascunho) | o banco **recusa** registrar aceite de rascunho: sem aprovação, ninguém se cadastra em produção | revisão jurídica + aprovação com revisor registrado | depende do jurídico | advogado(a) | cadastro bloqueado em produção (trava de propósito) | **Não** | **Sim** |
| C4 | **Docker não construído nem executado neste ambiente** | `Dockerfile` existe e está correto na leitura, mas build/run/healthcheck não foram exercitados aqui | `docker build` + `docker run` + `/healthz` + `/readyz` + migrations no contêiner | 2–4 h | docker disponível | descobrir no dia da publicação que a imagem não sobe | **Não** | **Sim** |
| C5 | **Observabilidade sem coletor** | logs estruturados e `/metrics` existem; ninguém está lendo | Prometheus/Grafana (ou equivalente) + alertas da §41 do pedido | 4–8 h | infraestrutura | falha silenciosa em produção: fila parada, webhook falhando, e-mail não entregue | **Não** | **Sim** |
| C6 | **Carga medida só na mesma máquina** | 160 rps com 12 threads, 0 erro — mas cliente, API e banco no mesmo host | repetir contra o ambiente de homologação, com rede real e banco separado | 2–4 h | ambiente de homologação | dimensionar errado e cair na primeira campanha | **Não** | **Sim** |
| C7 | **Cópia externa de backup não configurada** (novo na v0.19.0) | o backup agora roda e é conferido, mas fica no mesmo host: um incidente leva o banco e os dumps juntos | definir `BACKUP_OFFSITE_CMD` para um destino fora da máquina (bucket versionado) e provar uma restauração a partir dele | 2–4 h | conta e credencial de armazenamento do proprietário | perder banco e backup no mesmo incidente | **Não** | **Sim** |
| C8 | **RPO e RTO alvo não decididos** (novo na v0.19.0) | o que a configuração entrega está escrito no runbook §4-A; o que o negócio aceita perder, não | decidir os dois números e ajustar `BACKUP_INTERVAL_HOURS` (e contratar PITR do provedor, se o alvo for de minutos) | decisão | proprietário | descobrir o RPO real no dia do incidente | **Não** | **Sim** |
## HIGH — não bloqueia a publicação; bloqueia a *maturidade* do produto

| # | Item | Impacto | Solução | Esforço | Bloqueia design? | Bloqueia web? |
|---|---|---|---|---|---|---|
| H1 | **Metas oficiais dos ODS (169) e dados do IBGE não carregados** | o catálogo territorial diz "conferir na carga oficial"; `ods_targets` responde vazio | rodar os dois importadores com os arquivos oficiais (exigem fonte, URL e data) | 2–4 h | **Não** | **Não** (está declarado na interface) |
| H2 | **Mapeamento para GRI, ISSB e IRIS+ ausente** | relatório para esses referenciais não é possível; os três estão `registry_only` | decisão de produto + jurídica (as minutas da v0.17.0 os excluem), depois mapear indicador a indicador | dias | **Não** | **Não** |
| H3 | **Decaimento por idade na reputação** | observação de três anos pesa como a de ontem | aplicar `core/evidence.freshness()` às dimensões, versionando o motor | 4–8 h | **Não** | **Não** |
| H4 | **Detecção de conluio** | duas organizações que validam medições uma da outra sobem em duas dimensões | grafo de validação recíproca + marca de revisão humana (nunca acusação automática) | 1–2 dias | **Não** | **Não** |
| H5 | **Sinal de impacto só no sentido financiador→projeto** — *parcialmente endereçada na v0.19.0* | a assimetria do SINAL continua; o que mudou é que a OSC passou a ver o retorno OPERACIONAL de declarar contexto (`GET /v1/projects/{id}/context-return`, ADR-234), então o formulário mais caro do produto deixou de não devolver nada | decidir se contexto entra como prontidão no sentido OSC→edital (não é critério de aderência ao edital) | 4–8 h | **Não** | **Não** |
| H6 | **Seis telas da camada v0.18.0 não existem** | equidade, ODS, alegação, reputação, selo e responsabilidade só existem por API. Na v0.19.0 isso deixou de ser conhecimento tácito: a própria API declara `screen_status: to_be_designed` e um teste garante que a lista não mente | é a fase de design, com `DESIGN_HANDOFF_FINAL.md` §3 (tabela tela a tela, com a rota que cada uma consome) | — | **É o trabalho dele** | **Sim** (sem tela não há produto publicável) |
| H7 | **Procedência do preenchimento não é persistida** | `Suggest` devolve `{filled_by, origin, replaced_text}` e nenhum formulário grava | coluna/jsonb de procedência nos formulários que importam | 4–8 h | **Não** | **Não** |
| H8 | **Verificação pública dos selos novos** | `/v1/public/verify/{code}` serve os registros da v0.14.0, não os selos da v0.18.0 | ligar `seal_awards` à verificação pública com código curto | 4–8 h | **Não** | **Não** |
| H8 | **Tradução do conteúdo editorial do banco** (novo na v0.19.0) | as 12 regras de alegação, 12 de selo, 6 dimensões de reputação, 8 papéis e o catálogo de barreiras só existem em pt-BR | traduzir os textos de catálogo para en/es depois que o design estabilizar a redação | 1–2 dias | **Não** | **Não** (declarado em `locales.coverage_note`) |
| H9 | **Entrega de e-mail não é confirmada pelo provedor** (novo na v0.19.0) | a plataforma sabe que o SMTP ACEITOU, não que a pessoa recebeu; bounce e caixa de spam são invisíveis | receber webhook de bounce/entrega do provedor e acrescentar os estados correspondentes a `email_events` | 4–8 h | provedor de e-mail escolhido | **Não** | **Não** (o vocabulário já não mente: `accepted_by_smtp`) |
| H10 | **Procedência do preenchimento do primeiro acesso não é medida** (novo na v0.19.0) | não se sabe quais áreas vazias viram ação e quais são abandonadas | registrar evento ao executar a ação sugerida por `GET /v1/firstrun` | 2–4 h | **Não** | **Não** |
## MEDIUM

| # | Item | Observação |
|---|---|---|
| M1 | **`axe-core` e leitor de tela não verificados** | 12 verificações de acessibilidade feitas à mão no navegador; o resto está em `ACCESSIBILITY_REPORT.md` §2 |
| M2 | **Segundo navegador não testado** | só Chromium instalado |
| M3 | **`/v1/reputation/me` é a rota mais lenta** (p95 335 ms sob 12 threads) | são 11 consultas de sinal; cabe cache por organização com invalidação por evento |
| M4 | **Dependências web em faixa aberta** (`@types/*`, `@capacitor/*`) | declaradas como **NOT VERIFIED** no inventário; fixar exige registry |
| M5 | **384 chaves estrangeiras sem índice** | de propósito (regra da 0015: só coluna de inquilino ou pai percorrido); revisitar se aparecer consulta nova |
| M6 | **Retenção das trilhas novas sem prazo** | fato sobre organização, não sobre pessoa; prazo é decisão do responsável pelo tratamento |
| M7 | **Taxonomias editoriais sem revisão técnica** | 12 barreiras, 15 determinantes, 15 temas, 8 papéis — cada linha declara que é editorial |

## LOW / FUTURE

| # | Item |
|---|---|
| L1 | Busca incremental é `ILIKE`: "Cuiaba" sem acento não encontra "Cuiabá" (exige `unaccent`/`pg_trgm`) |
| L2 | Série longitudinal lê as 24 medições mais recentes; a janela é declarada no payload (`window_truncated`) |
| L3 | Selo não tem arte nem nível (bronze/prata/ouro foi recusado: nível é ranking com outro nome) |
| L4 | Emblemas oficiais dos ODS dependem de licença de marca da ONU |
| F1 | App mobile: código pronto (Capacitor), **nunca construído** |
| F2 | Internacionalização além de pt-BR: 294 traduções existem; segundo idioma não foi revisado |

## v0.23.0 — cadeia de suprimentos do frontend (bloqueio externo, não decisão de projeto)

### D-SUP1 · `web/package-lock.json` — FECHADO na v0.24.0

**Severidade: fechada (era HIGH).**

**Como fechou, com evidência.** O lockfile está versionado (veio no pacote recebido, gerado com rede
por outro agente, e foi conferido aqui — não escrito à mão: `lockfileVersion 3`, dependências
idênticas ao `package.json`, 128 pacotes com `integrity`, versões instaladas localmente conferem).
O que faltava provar foi provado no GitHub Actions, execução `37712067072` (commit `c783577`), passo
"Frontend — dependências, typecheck (tipos oficiais) e build": **`npm ci` instalou a árvore travada
sem erro e `tsc -p tsconfig.json` com `@types/react` oficial passou.** O CI e o Dockerfile usam
`npm ci`, e o job `docker` também instalou a partir do lockfile.

Por que só agora: até a v0.24.0 a suíte do CI morria no primeiro passo (a action do gitleaks exigia
licença) e o passo do front nunca rodou no GitHub.

O texto abaixo é o registro original, mantido como histórico da dívida.

---

O que isto significa, sem suavizar: a árvore de dependências do frontend **não é reprodutível**.
Dois `npm install` em datas diferentes podem instalar versões transitivas diferentes, e
`npm audit --omit=dev` audita a árvore que acabou de ser resolvida — não necessariamente a que foi
para produção. É a lacuna clássica de cadeia de suprimentos: não há como provar que o pacote
publicado foi construído com as mesmas dependências que passaram no CI.

**Por que não foi corrigido nesta rodada.** Gerar o lockfile exige resolver a árvore contra o
registro npm. O ambiente desta rodada não tem essa rota de rede:

```
npm error 403 403 Forbidden - GET https://registry.npmjs.org/@capacitor%2fandroid
```

`npm install --package-lock-only` falha no primeiro pacote. **Isto é um bloqueio de ambiente, não
uma escolha de arquitetura, e não há maneira honesta de contorná-lo aqui:** escrever à mão um
`package-lock.json` com hashes de integridade que não foram verificados seria inventar o artefato
cuja única função é ser verificável — pior que não tê-lo.

**O que foi feito no lugar.**

1. As quatro dependências que **entram no pacote construído** estão fixadas em versão exata:
   `react` 19.2.8, `react-dom` 19.2.8, `esbuild` 0.28.2, `typescript` 6.0.3. Não há faixa `^` em
   nenhuma delas, então o bundle que o `build.mjs` produz não muda por conta de resolução.
2. Sete dependências seguem com faixa `^`: `@types/react`, `@types/react-dom` e os cinco
   `@capacitor/*`. **Nenhuma das sete está instalada neste ambiente**, logo a versão exata não pode
   ser lida nem do `node_modules`. Fixá-las em um número escolhido por mim seria inventar versão —
   exatamente o que as regras desta rodada proíbem. As sete são de tipagem (tempo de compilação) e
   de empacotamento mobile (F1: nunca construído), nenhuma vai para o bundle web.
3. O CI passou a **gerar** o lockfile quando ele não existe e a publicá-lo como artefato
   (`package-lock-para-commitar`), e a usar `npm ci` quando existe. A primeira execução do
   pipeline num ambiente com rede produz o arquivo pronto para commit.

**Ação necessária (uma vez, por pessoa com acesso ao registro npm):**

```bash
cd web && npm install --package-lock-only && git add package-lock.json
```

**Risco de não corrigir:** uma dependência transitiva comprometida entra no build sem que nada
acuse, e a auditoria de vulnerabilidade não tem árvore estável para comparar entre execuções.

## Como esta lista foi feita

Não é uma lista de impressões. Cada item CRITICAL e HIGH veio de uma destas três fontes:

1. **Tentativa real que falhou** nesta rodada (C1: os dois comandos de auditoria, com a saída de
   erro anexada em `SECURITY_AUDIT.md` §0);
2. **Teste que fixa o estado** (H1: um teste exige que `ods_targets` esteja vazio enquanto o dado
   não entrar — se alguém carregar, o teste avisa);
3. **Achado de código ou de execução** (H5 saiu da jornada de ponta a ponta; M3 saiu do teste de
   carga).
