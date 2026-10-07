# Controle de progresso — fechamento da base técnica

> Uma linha por fase, com o que foi implementado, testado, auditado e documentado — e o que
> **permanece pendente**. Pendência oculta é pendência que explode na fase seguinte.
> Atualizado em 2026-10-06, versão 0.22.0.

## Legenda

- **DONE** — implementado, integrado, testado e documentado para o escopo da fase.
- **DONE (escopo declarado)** — fechado dentro de um escopo explicitamente mais estreito do que o
  pedido, com a diferença escrita.
- **BLOQUEADA (externa)** — tudo que podia ser feito sem terceiros está feito; o que falta exige
  credencial, contrato, conta ou decisão jurídica.

## Números desta versão

| medida | valor |
| --- | --- |
| rotas no roteador tipado | 873 |
| rotas com permissão granular declarada | 75 |
| rotas `auth="admin"` | 212 |
| rotas públicas (`auth="none"`) | 51 |
| migrações aplicadas (forward-only, sha256 por arquivo) | 50 |
| arquivos de teste | 84 |
| linhas de teste | 29.013 |
| módulos Python de produção | 226 |
| arquivos TypeScript/TSX | 52 |
| motores declarados | 42 |

---

## FASE 01 — AUDITORIA DA BASE — **DONE**

- **Implementado:** varredura das 872 rotas, 49 migrações, 226 módulos e 52 arquivos de frontend.
  Achados centrais desta rodada: (a) **um booleano para toda a equipe interna**; (b) **224 rotas sem
  tela**; (c) **duas tabelas de execução de tarefa** com respostas divergentes; (d) controles de
  quatro olhos **declarados e não implementados** em `core/risk_levels.py`.
- **Testado:** `test_architecture.py` (20 guardas), `test_v0200_cleanup.py`.
- **Auditado:** sim — cada achado virou teste de ratchet, não item de relatório.
- **Documentado:** `AUTHORIZATION.md` §0, `INTERNAL_OPERATIONS.md` §0.
- **Pendente:** nada.

## FASE 02 — MAPEAMENTO DA ARQUITETURA — **DONE**

- **Implementado:** `ARCHITECTURE.md` e `NON_CUSTODIAL_ARCHITECTURE.md` (ADR-284), que fixa a
  arquitetura CALCULA / INSTRUI / CONCILIA e prova, com contagem no código, que a plataforma não
  custodia.
- **Testado:** teste estrutural — nenhuma tabela cujo nome contenha
  `wallet|payout|split|escrow|custod|repasse` ou termine em `_balance(s)`.
- **Documentado:** `NON_CUSTODIAL_ARCHITECTURE.md`, `FINANCIAL_ENGINE.md` §0.
- **Pendente:** nada.

## FASE 03 — RECONCILIAÇÃO COM OS REQUISITOS — **DONE**

- **Implementado:** `REQUIREMENTS_MATRIX.md` e `PRICING_RECONCILIATION.md` (39 regras comerciais
  auditadas regra → localização → status → gap → implementação → teste).
- **Pendente:** nada.

## FASE 04 — MODELO DE DADOS — **DONE**

- **Implementado:** 4 migrações novas nesta versão (0046–0049): papéis internos e catálogo de
  permissões; motor financeiro (plano de contas, centros de custo, competência, partida dobrada,
  despesa, orçamento, instrução, alçada); unificação da trilha de tarefas; carimbo de aprovação de
  despesa.
- **Testado:** RLS em toda tabela (guarda endurecido nesta versão para não se derrotar com
  espaçamento); retenção declarada e **conferida contra o banco** (`DATA_RETENTION.md`).
- **Pendente:** nada.

## FASE 05 — AUTH / RBAC / PERFIS — **DONE**

- **Implementado:** 14 papéis internos, 43 permissões no catálogo, 69 mapeamentos, permissão como
  chave na porta da API, step-up de **19** permissões, trilha de acesso privilegiado que registra
  também a tentativa **recusada**, `AccessContext` numa consulta, `/v1/access/check`, três cópias
  de reautenticação unificadas em uma.
- **Testado:** `test_v0220_authorization.py` (34), `test_v0220_internal_ui.py` (31).
- **Documentado:** `AUTHORIZATION.md`.
- **Pendente (declarado em `AUTHORIZATION.md` §12):** ABAC por atributo de linha além do `org_id`;
  risco por IP/dispositivo; sessão curta dedicada à área interna.

## FASE 06 — WORKSPACES — **DONE (escopo declarado)**

- **Implementado:** `/area` com persona, capacidades e ordem das seções resolvidas no servidor;
  `/portal` novo nesta versão resolvendo a cadeia de acesso; menu interno autorado pelo backend.
- **Pendente:** o menu **do cliente** continua declarado no frontend (`NAV` por tipo de
  organização). Só o menu **interno** passou a vir do servidor. A diferença importa e está dita:
  a assimetria de autorização que esta rodada corrigiu estava na equipe interna.

## FASE 07 — PROJECTS / IDEAS / OPPORTUNITIES — **DONE**

Implementado e testado em versões anteriores; sem alteração estrutural nesta.

## FASE 08 — MATCH ENGINE — **DONE**

42 motores declarados e com cobertura derivada do código (`docs/AI_ENGINES.md`,
`scripts/make_engine_coverage.py`). Sem alteração nesta versão.

## FASE 09 — DIAGNOSTIC ENGINE — **DONE**

Sem alteração nesta versão.

## FASE 10 — DOCUMENT INTELLIGENCE — **DONE**

Sem alteração nesta versão. Modelos de documento existem onde há fonte citável (ADR-281).

## FASE 11 — LONGITUDINAL DATA — **DONE**

Sem alteração nesta versão.

## FASE 12 — GOVERNMENT DATA — **DONE (escopo declarado)**

Adaptadores e procedência por conjunto de dados (`external_datasets`, ADR-246); prazo de validade
declarado pela carga, com `undeclared` quando não há declaração (ADR-247). **Nenhuma fonte
governamental ao vivo está conectada.**

## FASE 13 — ODS / ESG / IMPACT — **DONE**

Sem alteração nesta versão.

## FASE 14 — GEO / MAPS — **DONE (escopo declarado)**

Geografia é de primeira classe no modelo; o provedor de mapas é abstrato e **nenhum está
configurado** (requer chave).

## FASE 15 — PARTNERS / INTERACTIONS — **DONE**

Sem alteração nesta versão.

## FASE 16 — MONETIZATION — **DONE**

- **Implementado (v0.21.0):** catálogo de preços 2027.01 com 8 versões vigentes, 2 pisos de
  proposta, 5 planos gratuitos, períodos gratuitos por conta, aceite comercial separando **acesso
  gratuito** de **autorização de cobrança**.
- **Implementado (v0.22.0):** taxa de marketplace **calculada** e declarada **não cobrável**, com o
  motivo (`FINANCIAL_ENGINE.md` §8).
- **Pendente:** a regra de take rate permanece `active = false` por decisão registrada, não por
  falta de código.

## FASE 17 — PIX / PAYMENTS / LEDGER — **BLOQUEADA (externa)**

- **Implementado:** máquina de estados de cobrança, idempotência, trilha de eventos por gatilho,
  conciliação, adaptador e contrato de PIX.
- **NÃO implementado, de propósito:** o **gerador de PIX**, removido na v0.20.0 (ADR-263) — sem
  provedor, a única forma de chamá-lo seria passando valor inventado.
- **Pendente (externo):** contratação de provedor de pagamento e credencial de produção.

## FASE 18 — RECEIPTS / FISCAL — **BLOQUEADA (externa)**

Adaptador, configuração, eventos, estados e tratamento de erro existem. `fiscal.issue` e
`fiscal.cancel` existem no catálogo de permissões. **Nenhum provedor fiscal está ligado:** a
permissão existe, a emissão não.

## FASE 19 — EMAIL / WHATSAPP — **BLOQUEADA (externa)**

E-mail: provedor, modelos, política de silêncio, limite diário, retentativa e canário operacional
implementados e testados; vocabulário do banco **recusa** `delivered`/`read`/`opened` (ADR-251).
WhatsApp: adaptador e contrato; **sem provedor oficial contratado**.

## FASE 20 — VOUCHERS / LICENSES / ENTITLEMENTS — **DONE**

- **Implementado nesta versão:** a **tela** de períodos gratuitos. O FULL FREE 2026 tinha rota,
  serviço, banco e teste desde a v0.21.0 e **nenhuma tela** — encontrado pelo teste de cobertura de
  menu, não por inspeção.

## FASE 21 — SUPERADMIN / CONTROL TOWER — **DONE (escopo declarado)**

- **Implementado:** 16 telas internas novas (`INTERNAL_OPERATIONS.md` §2), Health Center, Central de
  Alertas, matriz de permissões lida do banco, trilha de acesso privilegiado, `super_admin`
  concedido por gatilho de banco.
- **Pendente (declarado em `INTERNAL_OPERATIONS.md` §7):** busca global (⌘K); Quick Actions;
  fornecedores, contratos e ativos como módulos próprios; extrato navegável com saldo inicial e
  final por conta; projeção de 30/90/365 dias; modo auditoria com antes/depois campo a campo.

## FASE 22 — BI / ANALYTICS — **DONE (escopo declarado)**

- **Implementado:** `economics/metrics.py` — todo indicador com fonte, cálculo, período e última
  atualização; o que não tem base responde `available: false` **com o motivo**, nunca zero.
- **Declarado indisponível, com motivo:** churn, LTV, CAC, custo de IA (tabela de preço de IA
  vazia), autonomia de caixa sem queima.
- **Pendente:** coorte, ARPU/ARPA, margem de contribuição e projeção.

## FASE 23 — SECURITY / PRIVACY / AUDIT — **DONE**

- **Implementado nesta versão:** separação de função na porta, step-up, alçada por valor com dois
  gatilhos de banco, trilha de acesso privilegiado append-only, retenção de
  `privileged_access_log.user_id` declarada como anonimizável.
- **Testado:** varredura adversarial por `auth`, `min_role` e `kinds`; perfil × recurso × ação;
  cliente contra 8 painéis internos; três testes provando que o step-up é real.

## FASE 24 — TESTES — **DONE**

**1.806 testes**, 26 ignorados, suíte verde (454 s). **123 testes novos** nesta versão em três
arquivos. Nenhum
teste foi enfraquecido nem removido: os três que ficaram obsoletos foram **reescritos para o
invariante durável** (ver `CHANGELOG.md`).

## FASE 25 — DEBUG — **DONE**

**24 defeitos reais** corrigidos nesta versão: 13 encontrados pela própria suíte durante a
construção, e **11 por auditoria independente feita DEPOIS de a suíte estar verde** — entre eles a
decisão de aprovação que nunca chegava ao objeto aprovado, o menu que oferecia o que a porta
recusava (com um teste tautológico citado como prova), a tela de orçamento chamando uma rota
inexistente e sete indicadores do painel executivo lendo chaves que a resposta não tem.

Todos com ratchet. Os dois conjuntos estão em `CHANGELOG.md`, em seções separadas — a distinção
importa: a primeira lista é o que uma suíte bem escrita pega; a segunda é o que ela não pega, e é
a razão de a auditoria final ser feita por quem não produziu o trabalho.

## FASE 26 — CLEANUP — **DONE**

- Duas tabelas de trilha de tarefa → uma, com a antiga **removida** do esquema.
- Três cópias de reautenticação → uma.
- Dicionário `SUPER_ADMIN_ONLY` em Python **apagado**: o catálogo no banco é a fonte única.
- Nome de tarefa montado a partir de dado → nome constante, parâmetro no detalhe.

## FASE 27 — DOCUMENTAÇÃO — **DONE**

Novos: `AUTHORIZATION.md`, `FINANCIAL_ENGINE.md`, `INTERNAL_OPERATIONS.md`,
`NON_CUSTODIAL_ARCHITECTURE.md`, este arquivo. Atualizados: `CHANGELOG.md`, `DECISIONS.md`
(ADR-284 a ADR-296), `DATA_RETENTION.md` (regenerado contra o banco).

## FASE 28 — GIT — **DONE**

Ver `CHANGELOG.md` e o relatório final para o hash.

## FASE 29 — AUDITORIA FINAL — **DONE**

Feita por **agente independente**, que não produziu o trabalho, com instrução explícita de
verificar cada afirmação contra o código e o banco em vez de ler a documentação. Encontrou 11
defeitos reais e 12 testes fracos ou tautológicos; todos corrigidos antes do fechamento, e cada
achado virou teste. Nove testes foram **reescritos para exercitar o que o nome deles afirma**.

Seis perguntas por item (implementado / integrado / testado / auditado / documentado / versionado).
O resultado está no relatório final, com GO/NO-GO por frente — **não um GO único**.

## FASE 30 — ZIP FINAL — **DONE**

`scripts/make_release.py` com manifesto de versão e verificação de integridade.

## FASE 31 — RELATÓRIO FINAL — **DONE**

Entregue na resposta final da rodada, em português, com VERDE / AMARELO / VERMELHO por frente.
