# Relatório técnico final — v0.20.0

> Fechamento da engenharia antes da camada de Designer.
> Commit `ccb0799` · 06/10/2026 · **1.557 testes, 0 falhas** no estado final.
> Decisão: **GO** para o Designer · **NO-GO** para publicação web (os motivos não são de código).

---

## 1. Resumo executivo

Esta rodada não acrescentou produto. Ela procurou, em onze etapas, a diferença entre o que a
plataforma **afirmava** e o que ela **fazia** — e o que encontrou foi quase sempre a mesma coisa:
**mecanismo escrito, testado e inalcançável.**

Os cinco achados que resumem a rodada:

1. **Quinze tipos de aviso não pertenciam a interruptor nenhum.** A pessoa desligava todas as
   preferências de notificação que a tela oferecia e continuava recebendo aviso de conformidade,
   candidatura, pagamento, evidência, validação profissional e situação institucional — porque 29
   chamadas espalhadas pelo produto usavam prefixos que não casavam com nenhum grupo de
   preferência. Interruptor que não desliga é pior que interruptor nenhum: quem o usa acredita ter
   escolhido.

2. **Três funções existiam e nunca eram chamadas.** Proposta com prazo vencido ficava em "enviada"
   para sempre, e o evento que avisaria as duas partes nunca acontecia. Anúncio vencido não saía
   do ar. Selo cujo critério caiu continuava sendo exibido — e o docstring da função que o
   revogaria diz, com estas palavras, que isso "é pior que não ter selo".

3. **Dezoito eventos de domínio declarados e nunca emitidos**, incluindo `Document.attached` —
   literalmente o caso que originou o módulo de notificação, cujo próprio cabeçalho dizia: "quando
   um documento era anexado, ninguém além de quem anexou sabia".

4. **Doze motores existiam fora do inventário**, entre eles a camada de impacto inteira:
   afirmações, equidade, reputação e selos. Registro incompleto é pior que registro nenhum, porque
   dá a impressão de inventário.

5. **O importador de metas dos ODS que um documento afirmava ter entregue não existia.** A tabela
   `ods_targets` estava vazia desde a v0.8.0 e não tinha nenhum caminho para deixar de estar.

E implementou o que o escopo pedia: **denúncia em quatro níveis** com gatilho no banco impedindo
medida sem apuração concluída; **procedência** de dado público em que "prazo não declarado" nunca
vira "atual"; **qualidade de dado** que jamais se converte em desempenho; **nível de risco** das 837
operações com o controle humano que cada uma exige; **benchmark de preço** por pesquisa real; e as
**seis telas** que faltavam.

---

## 2. Arquitetura

Monólito modular em Python 3.13 sobre Starlette, com roteador tipado próprio e **837 operações**.
PostgreSQL 16.15 com **293 tabelas**, **41 migrações** forward-only (sha256 por arquivo), **607
políticas de RLS** e **817 índices**. Nenhum teste usa banco em memória: a suíte cria o banco do
zero a cada execução.

A autorização vive no banco, não na aplicação. A aplicação não tem `INSERT` em `domain_events`, em
`seal_awards`, em `reputation_snapshots` nem em `charge_events` — todos passam por função
`SECURITY DEFINER` estreita ou por gatilho. Essa escolha produziu, nesta rodada, uma correção
instrutiva: eu acrescentei um `INSERT INTO charge_events` em `payments.transition`, convencido por
um `count(*)` zerado em banco de desenvolvimento vazio de que ninguém escrevia a trilha. Escrevia —
por gatilho, desde a v0.17.0. A suíte reprovou, o código foi revertido, e há agora um teste que
impede **qualquer** código de aplicação de escrever naquela trilha. Tabela vazia em desenvolvimento
não é prova de que ninguém escreve nela.

**Vinte guardas de arquitetura** em teste. Três reprovaram a suíte nesta rodada e encontraram
defeito real: rotas que eu havia suposto ao declarar motores novos, e uma rota pública sem revisão
declarada.

---

## 3. Mudanças implementadas

### ETAPA 1 — Aceite legal no cadastro
A conta era criada **sem registrar aceite nenhum**. `register()` passou a gravar o aceite dos
documentos pendentes, amarrado ao sha256 da versão exata, e em ambiente endurecido **recusa** o
cadastro se houver documento que bloqueia o produto sem publicação.

### ETAPA 2 — Denúncia em quatro níveis
Antes, abrir denúncia tinha efeito: entrava na pontuação de conformidade. Agora os quatro níveis são
separados e o banco os separa:

| Nível | O que é | O que autoriza |
|---|---|---|
| **denúncia** | alguém relatou | **nada** — nem medida, nem ponto de reputação |
| **suspeita** | em apuração (`under_review`) | apenas informa; explicitamente não é achado |
| **infração apurada** | `substantiated`, decidido por pessoa com fundamentação escrita | **medida** |
| **consequência jurídica** | encaminhamento registrado | nunca declara crime |

`enforcement_needs_substantiated_report()` é um **gatilho**: medida sem denúncia apurada é recusada
pelo banco, não pela disciplina de quem programa. Direito de manifestação e recurso implementados
por funções `SECURITY DEFINER` estreitas, porque a escrita atravessa fronteira de visibilidade.
E a escada de dez degraus passou a **restringir sete capacidades** de verdade, pela primeira vez.

### ETAPA 3 — Procedência de dado de governo
`external_datasets` com publicador, conjunto, versão, licença, URL, sha256 do arquivo e as **duas**
datas (publicação e consulta), imutável por gatilho. `data_freshness()` com quatro estados, e o que
importa é `undeclared`: **sem prazo declarado pela carga, a resposta é "não declarado" — nunca
"atual"**. `scripts/import_ods_targets.py` escrito, e a afirmação falsa corrigida no documento que a
fazia, sem apagar o erro.

### ETAPA 4 — Motor de notificação
Catálogo de 30 tipos, cada um ligado a um dos 15 interruptores. A correção não foi reescrever 29
chamadas: foi um **gatilho no INSERT da tabela**, por onde os três caminhos passam — e por onde
passará o quarto que alguém escrever sem ler isto. §23 inteiro: preferência, prioridade,
agrupamento, deduplicação, rate limit, quiet period, retry e delivery status. Janela de silêncio e
teto diário **retêm** o aviso, nunca o descartam; aviso crítico atravessa os dois.

Três tarefas ligadas (proposta vencida, anúncio vencido, reavaliação de selo), varredura de cinco
prazos em D-30/D-7/D-1, e a camada de impacto — que não avisava **ninguém** sobre **nada** — passou
a avisar selo concedido, selo revogado com o motivo, mudança de **faixa** de reputação (não de cada
ponto) e convite para revisar afirmação.

### ETAPA 5 — Inventário de motores e a tabela de seis colunas
42 motores. `ENGINE_COVERAGE.md` e `GET /v1/engines/coverage` traem seis colunas —
**implemented, integrated, tested, E2E, security, observability** — e **nenhuma delas é declarada**.
Todas derivam do código, do roteador, da suíte e do esquema. Há teste provando que nenhuma coluna
pode ser um campo do motor que ela avalia.

### ETAPA 6 — Qualidade de dado e nível de risco
Sete achados sobre o dado (não preenchido, contado duas vezes, não fecha, parado no tempo, fora da
unidade, contraditório, sem como conferir), cada um apontando para a **linha exata**. E
deliberadamente **nenhuma nota, faixa ou percentual** — cinco testes travam isso, dois deles
estruturais.

Inventário de risco das 837 operações: 383 LOW, 273 MEDIUM, 171 HIGH, **10 CRITICAL**. As dez
críticas têm o controle humano conferido no código. Duas não tinham e foram corrigidas.

### ETAPA 7 — As seis telas (§94)
Reputação, selos, afirmações, equidade, ODS e responsabilidade tinham API, serviço, banco, eventos,
permissões, testes e documentação — e nenhuma tela. Entregues como **UI mínima funcional**, com
todo rótulo vindo do glossário gerado. Cada tela carrega a recusa que a define.

### ETAPA 8 — Benchmark de preço
12 linhas lidas **nas páginas dos próprios fornecedores**. Faixa publicada: US$ 10,99 a US$ 285 por
usuário/mês, mediana US$ 24,99. Um terço não publica preço algum — e **entra na tabela** com o
motivo, porque omiti-los faria o mercado parecer mais transparente do que é.

### ETAPA 9 — Testes adversariais
Duas varreduras que não existiam: por **`min_role`** e por **`kinds`**. A suíte provava que uma
estranha não entra e não provava que quem já está dentro não faz o que não deve — e é dessa metade
que vêm os incidentes reais.

### ETAPA 10 — Limpeza
Onze funções removidas, duas delas escritas por mim nesta rodada. Duas ligadas (os leitores de
`.docx`/`.odt`, e a nota de sistema na conversa). Uma bandeira que não ligava nada, ligada. Três
invariantes que eram só strings, apontando agora para o teste que os verifica.

---

## 4. Componentes removidos

| Removido | Por quê |
|---|---|
| `attach_pix()`, `attach_boleto()` | Gravavam instrução de pagamento que só provedor brasileiro produz. Sem provedor, só poderiam ser chamadas com valor inventado: **código que, se ligado, mente**. As tabelas ficam (§55). |
| `retry_serializable()` | Contradizia a estratégia escolhida — devolver 409 e o cliente repetir. Repetir no servidor esconderia do cliente que houve conflito. |
| `read_odt_text` órfão, `solution_badges`, `json_bytes`, `to_json`, `label_of`, `server_version`, `_need`, `_dump` | Nunca chamadas. |
| `_janela`, `_persists_version` | **Escritas por mim nesta rodada** e nunca usadas. |
| `Security.session_reuse_detected` (declaração de evento) | O reuso é detectado durante a renovação do token, sem sessão autenticada; `app_record_event()` recusaria o registro. Declarar evento que o caminho não consegue emitir seria repetir o defeito. |
| `POST /v1/admin/reports/{id}` (rota antiga de decisão) | Substituída pelo trâmite de quatro níveis. |

---

## 5. Inventário de motores

42 motores. A tabela completa com as seis colunas está em **`ENGINE_COVERAGE.md`**, gerada do
código. Resumo:

| Coluna | Resultado |
|---|---|
| implemented | **42 / 42** |
| integrated | **42 / 42** |
| tested | **42 / 42** |
| E2E | 36 sim · 3 não · 3 n/a (motor sem rota própria) |
| security | 39 sim · 0 não · 3 n/a |
| observability | **34 sim · 8 não** |

Os oito sem observabilidade são motores de leitura/derivação: depois do fato, não há como responder
"este motor rodou? com qual versão?". Aparece como **NÃO** em vez de ficar escondido atrás de uma
boa descrição, e há teste exigindo que as lacunas apareçam — uma tabela em que tudo é "sim" não está
medindo coisa alguma.

---

## 6. Validação do Match

Determinístico e versionado (`match-engine@1.2.0`). Cada resultado carrega **quatro** versões
(motor, pesos, regras, taxonomia), **score e confiança em campos separados**, impedimento duro que
nunca sai elegível e explicação que sempre diz por quê e o que falta. Pesos em arquivo de
configuração, alteráveis só pela administração.

Provado nesta rodada: inflar dado declarado **não sobe nada**; nenhuma escrita de match ou
recomendação pode mirar organização alheia; o motor **não tem caminho de escrita** no banco; e plano
pago não influencia resultado (invariante agora apontando para o teste que o verifica).

---

## 7. Dependências externas

Tudo o que depende de terceiro está declarado como **bloqueado**, nunca como aprovado:
`npm audit` e `pip-audit` (registros inacessíveis — **jamais registrado como "0 vulnerabilidades"**),
`axe-core`, leitor de tela, Docker, provedor de pagamento ao vivo, PIX/boleto, assinatura
qualificada (ICP-Brasil/gov.br), provedor fiscal, KYC, biometria e SMS. **Nenhum foi simulado.**

---

## 8. Dados a confirmar

1. **Preço** de cada plano pago, moeda e período — benchmark pesquisado, decisão é do proprietário.
2. **Aprovação jurídica** das 11 minutas legais.
3. **Regras fiscais** a aprovar por dois revisores distintos.
4. **Prazo de envelhecimento** de cada conjunto de dados público carregado.
5. **Carga das 169 metas dos ODS** do arquivo da fonte.

---

## 9. Diferido para depois do Designer

Oito motores sem rastro durável · 16 operações HIGH sem controle conferível de perto · 55 rotas sem
teste próprio · `downgrade_grace_days` como declaração · PIX/boleto aguardando provedor ·
refinamento visual das seis telas novas.

---

## 10. Decisão final

### Entrega ao Designer: **GO**

A base está conceitualmente congelada. 42 motores inventariados com o que cada um **nunca** decide,
vocabulário único de 123 termos com detector de divergência provado nos dois sentidos, as seis telas
entregues, contrato de primeiro acesso respondendo nove perguntas por área a partir de contagem
real, e 1.557 testes sem falha no estado final.

### Publicação web: **NO-GO**

E a palavra é escolhida. **Não é NO-GO por defeito de código** — a suíte está verde e os guardas de
arquitetura estão de pé. É NO-GO porque falta o que engenharia não produz: preço decidido,
aprovação jurídica, provedor contratado, auditoria de dependências executável e imagem construída.

Chamar isso de "GO WITH CONDITIONS" daria a impressão de que o caminho restante é curto e técnico.
Não é: é contratual e jurídico, e depende de decisões que não são minhas nem de nenhum engenheiro.
Dizer GO condicional aqui seria o mesmo tipo de otimismo que esta rodada passou onze etapas
desmontando.
