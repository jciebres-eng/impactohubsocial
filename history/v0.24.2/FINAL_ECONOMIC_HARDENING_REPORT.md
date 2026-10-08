# Relatório final — v0.17.0: camada econômica, legal e de pagamento

Data: 2026-10-06 · Versão: **0.17.0** · Ramo: `chore/v0.16.0-impact-network-core` · Último commit desta rodada
registrado em `RELEASE_MANIFEST.sha256`.

Este relatório responde, em ordem, ao que a rodada pediu. Onde algo **não** foi entregue, o item diz o que falta e
quem resolve. Não há "parcialmente verde".

---

## A. O que a rodada pediu, e o que foi feito

O pedido inverteu o roteiro: **monetização, pagamento e auditoria legal antes do design** (que é a fase 20 de 20).
A tese econômica é uma só, e está citada aqui porque tudo decorre dela: **o proponente não pode ser o pagador
principal.**

| Fase | Entrega | Situação |
|---|---|---|
| 1 | Auditoria econômica do que existia | 🟢 `SAAS_ECONOMIC_AUDIT.md` — 16 itens do mapa com evidência real, 6 camadas ausentes, 16 pendências EC-01…EC-16 |
| 2 | Programa como entidade | 🟢 migração 0018, 6 tabelas, 19 testes |
| 3 | Value Ledger separado do Billing | 🟢 migração 0019, 11 tipos de evento, 16 testes |
| 4 | Eventos cobráveis com elegibilidade | 🟢 migração 0020, `billable_events` com 6 estados e motivo escrito |
| 5 | Regras de receita com problema caro declarado | 🟢 9 regras; `problem_solved` e `substitution_answer` NOT NULL |
| 6 | Cartão legal por receita, com fonte e data | 🟢 `MONETIZATION_LEGAL_MATRIX.md` — **0 verdes**, 5 amarelas, 4 vermelhas |
| 7–8 | Arquitetura de pagamento | 🟢 migração 0022, 29+1 testes, tudo `PRODUCTION PAYMENT NOT CONFIGURED` |
| 9 | Termos e consentimento versionado | 🟢 migração 0023, 11 documentos, 27 testes |
| 10 | IA como motor operacional | 🟢 `engines/registry.py`, 28 motores, `docs/AI_ENGINES.md`, 13 testes |
| 11–12 | Segurança, LGPD e QA das tabelas novas | 🟢 18 testes; o conflito prova × eliminação resolvido |
| 13 | Desempenho dos caminhos novos | 🟡 medido; **regressão do feed declarada** |
| 14 | Git, documentação e versionamento | 🟢 este relatório, CHANGELOG, 18 ADRs novos |
| 15 | Implantação | 🔴 **não executável aqui** — ver §T |
| 16 | Teste de fumaça em produção | 🔴 **não executável aqui** — ver §T |
| 17–19 | Auditoria final, pacote, entrega | 🟢 este relatório + ZIP + manifesto |
| 20 | **DESIGN** | ⏭️ é a próxima rodada, por desenho do pedido |

---

## B. A inversão que a rodada implementou

A regra comercial da v0.16.0 (teste de 14 dias, US$ 1,99 nos três primeiros meses, depois US$ 19,99/mês) **foi
substituída** por decisão expressa do proprietário. A nova regra, em uma frase: **entrada gratuita de forma
permanente, e quem paga é instituição.**

Concretamente, no código:

- `config/plans.json` → `plans@2.0`, plano `osc_basic` renomeado **"OSC — gratuito"**;
- limites do plano gratuito são **técnicos** (10 projetos ativos, 20 requisições de IA/mês, 1 GB, 5 assentos, 3
  buscas salvas) e **não removem acesso ao que já foi criado**;
- moeda padrão de volta a **BRL**;
- `test_the_commercial_rule_is_declared_in_configuration` falha se a regra sair da configuração para o código.

ADR-173.

---

## C. Quem paga, segundo o que está no banco

| Prioridade | Motor | Pagador | Cartão legal |
|---|---|---|---|
| 1 | `saas_institutional` | empresa, instituto, fundação | 🟡 amarelo |
| 2 | `b2g` | órgão público | 🔴 **vermelho** — a recusa é do **checkout de autosserviço**, não do cliente |
| 3 | `enterprise` | grande empresa (ESG) | 🟡 amarelo |
| 4 | `implementation` | quem contrata implantação | 🟡 amarelo |
| 5 | `marketplace_take_rate` | profissional anunciante | 🔴 vermelho (ADR-022/178) |
| 6 | `success_fee` | financiador | 🔴 vermelho (ADR-022/178) |
| 7 | `proponent_premium` (2 regras) | OSC, por escolha | 🟡 amarelo — **aquisição, nunca o núcleo** |
| 8 | `data_intelligence` | quem compra dado agregado | 🔴 vermelho — reidentificação |

**Zero verdes. Nenhuma ativa.** Não por esquecimento: `monetization_rule_gate()` recusa ativar regra sem cartão
verde, e `green_needs_evidence` recusa cartão verde que não cite fonte — porque **ausência de proibição não é
permissão**.

---

## D. A cadeia que nenhuma cobrança pode furar

```
evento de valor → elegibilidade → regra → VALIDAÇÃO LEGAL → cobrança
```

Cada seta é uma trava real no banco, não um passo de processo:

| Trava | Onde | O que impede |
|---|---|---|
| `value_events` sem INSERT para a aplicação | migração 0019 | que quem vai cobrar informe o valor entregue |
| `app_record_value()` SECURITY DEFINER | 0019 | que a estimativa de tempo venha por parâmetro |
| `app_promote_billable()` | 0020 | que evento vire cobrável sem regra ativa |
| `monetization_rule_gate()` | 0020 | que regra sem cartão verde seja ativada |
| `green_needs_evidence` / `green_has_no_open_questions` | 0020 | cartão verde sem fonte ou com pergunta aberta |
| `charge_simulated_flag()` | 0022 | que cobrança de teste passe por real |
| `platform_revenue()` | 0022 | que simulado seja somado ao real |
| `acceptance_stamp()` | 0023 | que aceite de minuta seja registrado |

---

## E. Programa: o que torna o institucional vendável

`programs` + chamadas + carteira + indicadores + necessidades. `objective` é **NOT NULL**: programa sem objetivo
declarado não é programa, é uma pasta de projetos.

As três funções que separam o declarado do medido:

- **`program_financials()`** — orçamento, comprometido, **gasto** e **comprovado** em colunas distintas. Despesa
  registrada sem comprovante no cofre conta em `spent` e **não** conta em `evidenced`. Somar as duas daria um
  número maior, mais bonito, e correspondente a nada.
- **`result_chain()`** — a força **declarada** de cada elo, separando forte de fraco, com nota dizendo que elo
  declarado não é resultado comprovado.
- **`territorial_gap()`** — a lacuna com `evidence_quality`: necessidade sem fonte citada vem marcada como tal.

---

## F. Value Ledger: entrega separada de cobrança

Onze tipos de evento, cada um com `what_counts` dizendo o que conta. Inclui `document.blocked_incomplete` — **a
recusa é valor entregue**: quando a plataforma se nega a gerar uma prestação de contas incompleta, ela impediu um
problema, e isso é registrado antes de a exceção subir.

A trava que mais incomoda, e é precisa: **nenhuma linha de base tem número.** Existe uma linha por tipo, com
`minutes_per_unit` nulo e a nota "não definida", para que a ausência seja **visível** em vez de silenciosa. Até
alguém declarar o número com fonte, data e método, o evento fica `no_baseline` e a estimativa é nula.

(Esta precisão custou uma correção: o documento afirmava "a tabela nasce vazia", o que é falso. Quem pegou foi o
teste que confere documentos contra o banco — ver §R.)

---

## G. Pagamento: o que está pronto e o que não existe

**Pronto e testado** (30 testes): máquina de 27 arestas; trilha append-only escrita por gatilho `SECURITY DEFINER`;
parcelamento **à parte da assinatura**, com a soma conferida no COMMIT por restrição postergada; instrução de PIX
com prazo e de boleto com vencimento; webhook idempotente com contagem de reentrega; evento sem assinatura
registrado e **sem efeito**, com CHECK no banco impedindo que ele chegue a "processado"; job que fecha vencidos
pela transição do grafo; `last4` recusando mais de quatro dígitos e **nenhuma coluna** para número de cartão.

**Não existe:** provedor. Sem conta, sem chave, sem identificador de preço, sem segredo de webhook. Logo **nenhuma
cobrança real foi processada por este código**, e `GET /v1/payments/status` responde `configured: false` com o
banner `PRODUCTION PAYMENT NOT CONFIGURED`.

A honestidade aqui é estrutural: `is_simulated` é **derivada** do provedor, contra lista **explícita** de provedores
reais, e a tentativa de alterá-la é **recusada** — não sobrescrita em silêncio, porque silêncio deixaria quem tentou
sem sinal de que a tentativa foi ignorada.

---

## H. Legal: onze minutas, nenhuma vigente, nenhum aceite registrável

Oito documentos novos — Assinatura, Marketplace, Intermediação, Pagamento, Cancelamento, Reembolso, B2B e B2G —
escritos a partir do que o software **faz**, não de modelo de contrato. Cada um lista o que **não** está incluído e
termina com perguntas abertas para o jurídico.

E a trava que trava o produto **de propósito**: `acceptance_stamp()` recusa registrar aceite de documento que não
esteja aprovado e vigente, e `approved_needs_review` recusa aprovação sem quem revisou, quando e sob qual
referência. Como nenhuma minuta passou por advogado(a), **nenhum aceite é registrável hoje**.

A alternativa — coletar aceite de rascunho — foi recusada: "o usuário aceitou os termos" dito sobre um rascunho é
afirmação falsa **com aparência de prova**, pior que não ter registro.

A prova, quando houver, guarda o **sha256 do texto aceito**, copiado do documento pelo gatilho. Sem o hash, "aceitou
os termos" não diz **quais** termos.

---

## I. IA: motor operacional, e o teste que prova

28 motores declarados em `engines/registry.py` com módulo, função, natureza, versão, rotas, o que produzem e **o que
nunca decidem**. Cinco testes tornam a declaração verificável; o mais importante **impede uma chamada nova ao modelo
entrar de carona** sem ser declarada.

O estado real: **23 determinísticos**, **2 que respondem por extração** do conteúdo cadastrado (devolvendo
`ai_used: false` e **recusando responder** abaixo da confiança mínima) e **3 que chamam modelo** — todos sobre base
determinística que continua valendo se o modelo falhar, todos devolvendo rascunho para revisão humana.

Toda chamada ao modelo passa por: cota por organização, **redação de dado pessoal antes do envio**, limite de
contexto, timeout com queda para o provedor local, e registro **sem conteúdo**.

---

## J. Segurança das 22 tabelas novas

Lido do catálogo do PostgreSQL, não do código: RLS em todas, política em todas, `value_events` e `charge_events` sem
INSERT para a aplicação, nenhuma função `SECURITY DEFINER` sem `search_path` fixo, nenhuma FK quente sem índice
(uma foi achada e criada), nenhuma coluna nova com dado pessoal sem justificativa declarada, token de cartão
invisível para a administração da plataforma, e **nenhuma coluna** para número de cartão, CVV ou validade.

Matriz de isolamento **linha a linha**, com o **teste par** que falha se o filtro do próprio teste não achar nada —
porque isolamento que passa por não haver dado é isolamento que não foi testado.

---

## K. LGPD: o conflito entre prova e eliminação

`legal_acceptances` é append-only, porque prova editável não prova nada. Mas guarda IP e agente de usuário, que são
dado pessoal, e a exclusão de conta anonimiza o titular. Com um gatilho que proíbe qualquer alteração, a
anonimização seria **recusada pelo banco**.

A escolha foi **estreitar** o append-only, não afrouxá-lo: `acceptance_anonymize_only()` permite exatamente apagar
IP e agente de usuário, e o GRANT de coluna recusa antes ainda. A prova sobrevive sem eles.

Mais: a prova entra na **portabilidade** (com o hash, que é o que a torna verificável por quem recebe o arquivo), a
exclusão de conta apaga IP e agente, e a retenção apaga IP de aceite com mais de 18 meses e **esvazia o corpo bruto
do webhook** no mesmo prazo — o evento fica, por idempotência; o conteúdo, que pode trazer nome e e-mail do pagador,
sai.

---

## L. Desempenho

| Caminho novo | Execução A | Execução B |
|---|---|---|
| `GET /v1/programs/feed` | 40 ms | 40 ms |
| `GET /v1/value/summary` | 13 ms | 12 ms |
| `GET /v1/payments/charges` | 14 ms | 20 ms |
| `GET /v1/legal/registry` | 40 ms | 43 ms |
| `platform_revenue()` (10.000 cobranças) | 8 ms | 5 ms |
| `program_financials()` | 3 ms | 4 ms |
| `territorial_gap(NULL)` | 8 ms | 31 ms |

**A regressão que não vou esconder:** o feed do financiador foi de 1.508–1.724 ms para **1.874–2.041 ms**, com a
**mesma consulta**. O que mudou foi o volume total do banco (~130.000 linhas novas) somado a ruído de máquina de 2
vCPU — e não dá para separar as duas com o instrumento que existe aqui. A folga até o orçamento caiu de 1,5× para
1,2×, então os carregadores em lote deixaram de ser opcionais: são o **primeiro item de desempenho da próxima
rodada**. Detalhe em `PERFORMANCE_REPORT.md` §7.

---

## M. Testes

**961 testes, 0 falhas, 17 pulados** (eram 788). Os 17 pulados são a suíte de volume, que roda em passo próprio.
161 testes novos nesta rodada; a distribuição por arquivo está em `TEST_REPORT.md`.

Nenhum teste foi enfraquecido nem removido para ficar verde. Três testes **meus** foram corrigidos porque estavam
errados — e cada correção está explicada no próprio teste, com o motivo:

1. a varredura de "coluna com dado pessoal" procurava substring e acusava `subscription_id` (contém "ip");
2. o teste de isolamento exigia contagem **zero** e falhava na suíte completa, porque outra suíte publica programa
   com visibilidade de rede, que a política expõe **de propósito**;
3. o teste de índice exigia ausência de varredura sequencial sem olhar o tamanho da tabela.

---

## N. Os defeitos que a suíte achou, e o que cada um ensinou

| Defeito | A lição |
|---|---|
| `BEGIN/COMMIT` dentro de migração | o executor já envolve o arquivo em transação; o `COMMIT` interno acabava com ela e uma falha no meio deixaria a migração aplicada **pela metade sem rollback** |
| `guard_columns` sobre coluna derivada por gatilho | gatilhos disparam em ordem alfabética: guardar o que outro gatilho deriva rejeita a transição **legítima**. Mesmo erro da v0.16.0, cometido de novo |
| trava de visibilidade bloqueando a moderação | trava que impede o abuso e o remédio ao mesmo tempo é trava mal desenhada |
| `ctx.org_id` levantando 409 na leitura anônima | "selecione uma organização" em resposta a recurso inexistente é **vazamento de existência** |
| índice único parcial conferido antes do gatilho AFTER | "fechar a versão anterior" tem de ser BEFORE INSERT |
| `try/except` sem SAVEPOINT em volta de função de banco | capturar exceção de banco sem SAVEPOINT deixa a transação **abortada**: o trabalho do usuário morre no COMMIT, em silêncio |
| o SAVEPOINT escondendo um segundo defeito meu | trava que engole erro sem avisar é trava que mente |
| mensagem do portão legal perdida pelo tratador global | 403 genérico protege o esquema e **apaga a razão** |
| receita classificada pelo **nome** do provedor | coluna dizendo 'stripe' não é prova de chave ao vivo. Apareceram **R$ 396,00 de receita inexistente** |
| trilha de cobrança sem permissão para a aplicação | a saída certa foi `SECURITY DEFINER` no gatilho, **não** GRANT de INSERT |
| CHECK novo quebrando o caminho da v0.11.0 | restrição nova quebra caminho antigo; o antigo passou a declarar `signature_verified` |

---

## O. O que a atualização garante

`test_v0150_upgrade.py` (11 testes) aplica as migrações sobre um banco na v0.12.1 **com dado dentro** e confere que
nada foi perdido, que a trilha encadeada continua íntegra e que o esquema atualizado é **idêntico** ao criado do
zero.

O teste novo desta rodada confere que a atualização trouxe **as travas, não só as tabelas**: no banco atualizado,
aceite de minuta e aprovação sem revisor são recusados, nenhuma regra chega ativa, nenhum cartão chega verde e
nenhuma linha de base chega com número. Uma migração que criasse a estrutura e deixasse o conteúdo de fora faria o
portão legal existir sem nada para barrar — e tudo "passaria".

---

## P. Backup e restauração

`scripts/backup.sh` + `scripts/restore_test.sh`, executados nesta rodada: 24 migrações restauradas, ledger e
auditoria íntegros.

E uma verificação nova: o teste de restauração passou a conferir que a camada econômica volta **desligada** —
nenhuma receita ativa, nenhum cartão verde, nenhuma minuta aprovada, nenhuma cobrança real. Um restore que ligasse
uma receita em silêncio seria pior que um restore que falha.

---

## Q. Integridade do banco

| Medida | Valor |
|---|---|
| Tabelas | **253** |
| Sem RLS | `schema_migrations` (única) |
| Políticas | 521 |
| Gatilhos | 194 |
| Funções | 277, das quais 75 `SECURITY DEFINER` |
| `SECURITY DEFINER` sem `search_path` | **nenhuma** |
| FK quente sem índice | **nenhuma** |
| CHECKs | 1.216 |
| Tabelas append-only | 26 |
| Migrações | 24 |

Saída bruta: `docs/evidence/db_integrity_v0.17.0.txt`.

---

## R. A parte mais útil desta rodada: os documentos passaram a ser testados

`test_v0170_docs.py` (17 testes) confere **números e chaves dos documentos contra o banco**. Ele pegou três
afirmações falsas minhas, que nenhuma revisão humana pegaria:

1. **a tabela de regras de monetização citava chaves que não existem**, e dava B2G como pendente quando o cartão
   legal dela é **vermelho** (a recusa é do checkout de autosserviço, não do cliente);
2. **`VALUE_LEDGER.md` afirmava que a tabela de linhas de base "nasce vazia"** — ela nasce com uma linha por tipo e
   **sem número**, e a diferença é exatamente o ponto do mecanismo;
3. **`API_DOCUMENTATION.md` citava um caminho que não existe** (`/v1/admin/monetization/billable/...`). Caminho
   errado em documentação de API é defeito entregue: quem integra tenta, recebe 404 e não sabe se o erro é dele.

Mais a correção de um número em três documentos: o grafo de situação de programa tem **11** arestas, não 12.

Documento com número errado é pior que documento sem número, porque dá a impressão de auditoria.

---

## S. O que esta versão NÃO entrega

Lista fechada, para que ninguém descubra depois (a completa está em `RELEASE_READINESS.md` §5):

1. **Nenhuma receita ativa** — cinco esperam parecer, quatro são recusadas.
2. **Nenhum aceite de documento legal registrável** — nenhuma minuta foi revisada por advogado(a).
3. **Nenhum provedor de pagamento** — sem conta, chave, identificador de preço ou segredo de webhook.
4. **Nenhuma cobrança real processada.**
5. **Sem nota fiscal** — sem provedor fiscal, inscrição municipal ou código de serviço.
6. **Sem SLA** — nenhum número medido em operação nem contratado.
7. **Sem assinatura qualificada, ICP-Brasil, gov.br, biometria, SMS ou ACT.**
8. **Sem integração governamental** (SICONV/Transferegov, SIAFI, Portal da Transparência, e-SIC, compras).
9. **Sem relatório pronto para CVM, GRI, SASB ou ISSB.**
10. **Sem preço institucional declarado** — é decisão comercial do proprietário.
11. **Sem estimativa de tempo economizado** — nenhuma linha de base tem número com fonte.
12. **Sem verificação de assinatura de webhook contra provedor real** — só contra assinatura inválida.
13. **Sem camada de design** — é a próxima fase, por desenho do pedido.
14. **Sem teste de intrusão independente.**
15. **Sem `npm audit` / `pip-audit`** — os registros estão bloqueados neste ambiente.

---

## T. As duas fases que NÃO são executáveis neste ambiente

**FASE 15 (implantação)** e **FASE 16 (teste de fumaça em produção)** do roteiro pedido não podem ser executadas
aqui, e isso é declarado em vez de simulado:

- não há **domínio** nem DNS;
- não há **credencial de nuvem** (a ADR-015, escolha de nuvem, continua aberta e depende do proprietário);
- a rede de saída deste ambiente alcança **só os registros de pacote**: qualquer requisição a outro endereço é
  recusada antes de chegar ao destino;
- não há conta em provedor de pagamento, de e-mail, de antivírus ou de armazenamento.

O procedimento está escrito e pronto em `DEPLOYMENT_CHECKLIST.md`. Executá-lo exige as credenciais que só o
proprietário tem. **Simular um deploy e chamá-lo de feito seria a pior coisa que este relatório poderia fazer.**

---

## U. O que o proprietário precisa contratar para destravar

Em ordem de quanto cada item destrava:

1. **Advogado(a)** — revisar as onze minutas e responder a pergunta que atravessa todas: *a organização contratante
   é consumidora para fins do CDC?* Sem isso, nenhum aceite é coletável e nenhuma receita sai do amarelo.
2. **Provedor de pagamento** — contratar e decidir o modelo (adquirência, subadquirência, instituição de
   pagamento), que define quem responde por chargeback. Depois é configuração: chave, preços, segredo de webhook.
3. **Contador(a)** — regime tributário, município de prestação, código de serviço, emissão de NFS-e.
4. **Encarregado(a) de dados (LGPD art. 41)** — nomear; hoje é um campo `{{ }}` nas minutas.
5. **Decisões de identidade jurídica** — razão social, CNPJ, endereço, foro, canais de contato.
6. **Nuvem e domínio** (ADR-015) — para as fases 15 e 16.
7. **Preço institucional** — decisão comercial; nada no sistema inventa um número.

---

## V. Veredito, por camada

| Camada | Veredito |
|---|---|
| Programa e portfólio institucional | 🟢 |
| Registro de valor entregue | 🟢 |
| Regras de monetização e portão legal | 🟢 **construído e deliberadamente desligado** |
| Validação jurídica das receitas | 🔴 **0 verdes** — depende de advogado(a) |
| Camada de pagamento da plataforma | 🟢 construída e testada |
| Cobrança real | 🔴 **sem provedor** |
| Documentos legais versionados | 🟢 |
| Aceite de documento legal | 🔴 **nenhum registrável** — depende de advogado(a) |
| IA como motor operacional | 🟢 com teste provando |
| Segurança das tabelas novas | 🟢 |
| LGPD das estruturas novas | 🟢 |
| Desempenho | 🟡 regressão do feed declarada |
| Documentação | 🟢 e, nesta rodada, **testada** |
| Implantação e produção | 🔴 **não executável aqui** |
| Design | ⏭️ próxima fase |

---

## W. Como conferir tudo, do zero

```bash
# banco
ADMIN_DATABASE_URL="postgresql://postgres@127.0.0.1:5432/postgres" bash scripts/dev_reset_db.sh

# suíte completa (961 testes)
cd backend && TEST_ADMIN_DATABASE_URL="postgresql://postgres@127.0.0.1:5432/postgres" \
  PASSWORD_SCRYPT_N=16384 RATE_LIMIT_MULTIPLIER=1000 python3 -m unittest discover -s tests -t . -v

# volume e desempenho (passo próprio)
cd backend && PERF_FULL=1 TEST_ADMIN_DATABASE_URL="..." python3 -m unittest tests.test_v0150_performance -v

# lint, tipos e build
/root/.local/bin/ruff check impacto tests
cd web && node node_modules/typescript/bin/tsc -p tsconfig.offline.json --noEmit && node build.mjs

# SQL conferido por PREPARE
DB="postgresql://impacto_owner@127.0.0.1:5432/impacto_dev" python3 scripts/sql_prepare_check.py backend/impacto/economics

# integridade, migração legal em sincronia, backup e restauração
REPORT_DATABASE_URL="..." python3 scripts/db_integrity_report.py
python3 scripts/gen_legal_registry.py --check
BACKUP_DATABASE_URL="..." bash scripts/backup.sh
ADMIN_DATABASE_URL="..." bash scripts/restore_test.sh backups/<arquivo>.dump

# pacote
python3 scripts/make_release.py --name IMPACTO_v0.17.0_ECONOMIC_LEGAL_PAYMENT.zip
python3 scripts/make_release.py --verify <diretório extraído>
```

---

## X. Onde começar a leitura

| Se você é… | Leia nesta ordem |
|---|---|
| Proprietário | `ECONOMICS.md` → `MONETIZATION_LEGAL_MATRIX.md` §5 → §U deste relatório |
| Advogado(a) | `docs/LEGAL_FRAMEWORK.md` → as onze minutas em `docs/legal/` → `MONETIZATION_LEGAL_MATRIX.md` |
| Contador(a) | `docs/legal/PAYMENT.md` §5 → `MONETIZATION_LEGAL_MATRIX.md` (notas fiscais) |
| Designer | `INFORMATION_ARCHITECTURE.md` → `NAVIGATION_MODEL.md` → `DESIGN_HANDOFF_FINAL.md` |
| Pessoa de engenharia | `PROGRAM_ARCHITECTURE.md` → `VALUE_LEDGER.md` → `MONETIZATION.md` → `PAYMENT_ARCHITECTURE.md` |
| Auditoria | `RELEASE_READINESS.md` → `SECURITY_AUDIT.md` → `LGPD_AUDIT.md` → `DATABASE_INTEGRITY_REPORT.md` |

---

## Y. A frase que resume a rodada

Os documentos pediam: *"Não venda 20 funcionalidades por R$ 99. Venda um problema caro resolvido."* Isso deixou de
ser conselho e virou restrição de esquema: `problem_solved` e `substitution_answer` são **NOT NULL** em
`monetization_rules`. Regra de receita que não diz qual problema caro resolve **não entra no banco**.

E a outra frase, a que mais custou a implementar: *"Não invente. PROVE."* A prova, aqui, é o conjunto de travas que
fazem o sistema **recusar** o atalho — a cobrança que não pode nascer real, a receita que não pode ser ativada, o
aceite que não pode ser registrado, a estimativa que não pode ser produzida. Cada recusa tem o motivo escrito no
banco, na API e no documento, e cada uma tem teste.

---

## Z. Encerramento

A camada econômica, legal e de pagamento está **construída, travada e desligada** — e o motivo de cada
desligamento está escrito. Os bloqueios que restam para faturar **não são técnicos**: são parecer jurídico,
provedor de pagamento e contador.

A engenharia fez o que lhe cabia e parou onde deveria parar.

---

**v0.17.0 — CAMADA ECONÔMICA, LEGAL E DE PAGAMENTO está pronta. A próxima fase é DESIGN.**

<sub>Nota sobre o número: esta rodada entrega capacidade nova grande sobre a v0.16.0, portanto é v0.17.0 (SemVer
MINOR, ver `VERSIONING.md`). A v0.16.0 está preservada, íntegra, em `history/v0.16.0/`.</sub>
