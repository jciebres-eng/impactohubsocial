# CHANGELOG — IMPACTO v0.23.0

Recorte da seção v0.23.0 de `CHANGELOG.md`, para o pacote de auditoria. O histórico completo
está no arquivo original; versões anteriores à v0.7.0 estão em `history/`.

---

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
