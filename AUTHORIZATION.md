# Autorização — Impacto Trust

> Como a plataforma decide quem pode o quê. Documento da v0.22.0. Descreve o que está
> implementado e testado; o que não está, está dito como não estando.

## 0. O defeito que esta versão corrigiu

Até a v0.21.0 a equipe interna da plataforma tinha **um booleano**: `users.is_platform_admin`.
Quem o tivesse alcançava as 193 rotas `auth="admin"` então existentes — receita apurada, custo de
IA, fatura, tabela de preços — **sem nenhum papel financeiro no caminho**. Os três papéis nomeados
que existiam (`editor`, `reviewer`, `support`) eram todos de conteúdo.

Numa equipe de uma pessoa isso não aparece. Na primeira contratação aparece de uma vez, e a
correção às pressas é conceder tudo a todos.

Três consequências concretas do booleano único:

1. `ctx.admin_mode = True` era um desvio global: ligado na porta, valia para toda a requisição.
2. `core/risk_levels.py` **declarava** controles por rota sem implementá-los. O docstring dele
   dizia: *"Dizer que uma operação exige quatro olhos e não implementar os quatro olhos é a forma
   mais cara de mentir nesta plataforma."*
3. A barra lateral da administração era uma lista fixa no frontend, igual para todos: quem atendia
   chamado via "Cobrança por organização" e "Auditoria" no menu e levava 403 ao clicar.

## 1. As quatro perguntas, em ordem

Toda requisição autenticada passa por quatro perguntas distintas. Elas não se substituem:

| pergunta | o que responde | onde mora |
| --- | --- | --- |
| **Autenticação** | Quem é a pessoa? | `load_principal()` em `http.py` |
| **Contexto** | Em nome de qual organização ela age agora? | `Principal.org_id`, `org_kind`, `role` |
| **Autorização** | Esta operação é permitida a ela? | `authorize()` + `core/access.py` |
| **Entitlement** | O plano dela inclui este recurso? | `AccessContext.features` / `limits` |

Autorização e entitlement são perguntas diferentes de propósito: *não poder* e *não ter contratado*
exigem respostas diferentes para a pessoa (403 contra 402) e caminhos diferentes para resolver.

## 2. Perfil, função, papel interno

Três eixos independentes. Confundi-los é o que produz "administrador que vê tudo".

- **Perfil** (`organizations.kind`): `osc`, `company`, `individual`, `provider`, `government`,
  `platform`. É a natureza da conta.
- **Função na organização** (`memberships.role`): `viewer` → `member` → `analyst` → `manager` →
  `admin` → `owner`, hierárquicos (`ROLE_ORDER` em `http.py`).
- **Papel interno** (`staff_roles.role`): 14 papéis, **não hierárquicos**. Quem é da contabilidade
  não é "mais" nem "menos" do que quem é da tesouraria: faz outra coisa.

Papel interno **não** depende do perfil da organização ativa. Quem é da controladoria continua
sendo da controladoria com a própria OSC ativa — o tipo da organização nunca disse nada sobre isso.

## 3. Os 14 papéis internos

`super_admin`, `controller`, `finance`, `accounting`, `treasury`, `billing`, `fiscal` (reservado),
`operations`, `compliance`, `audit`, `security`, `support`, `analyst`, `editor`, `reviewer`.

`super_admin` é concedido **pelo banco**, não pela aplicação: o gatilho
`platform_admin_implies_super()` o concede quando `users.is_platform_admin` passa a verdadeiro e o
remove quando deixa de ser. O gatilho cobre migração, linha de comando, seed e console do banco —
quatro caminhos que uma concessão feita na aplicação deixaria de fora.

## 4. A matriz de permissões é DADO

Duas tabelas, com papéis distintos:

- **`permission_catalog`** — o que EXISTE. 43 permissões, cada uma com domínio, verbo e descrição.
  Três são exclusivas de `super_admin` (`admin.users.write`, `fiscal.issue`, `fiscal.cancel`) e cada
  uma dessas carrega um `only_reason` obrigatório de 30 caracteres ou mais.
- **`staff_permissions`** — QUEM tem o quê. 65 mapeamentos papel → permissão, com nota explicando
  cada concessão. Chave estrangeira para o catálogo: não se concede permissão que não existe.

`super_admin` recebe o **catálogo**, não o mapeamento. A diferença importa: uma lista explícita
esqueceria a permissão criada no mês seguinte, e foi exatamente isso que aconteceu na primeira
versão desta migração — `admin.users.write` estava declarada em rota, não estava em
`staff_permissions` (por ser exclusiva), e a rota ficou **inalcançável para todos**, inclusive para
o super administrador.

Uma segunda fonte foi **removida** por isso: havia um dicionário `SUPER_ADMIN_ONLY` em Python que
discordava do banco sobre `admin.organizations.write`. O dicionário foi apagado; o catálogo no banco
é a fonte única, e o teste lê `permission_catalog.super_admin_only`.

## 5. A porta

Rotas declaram a exigência na própria assinatura:

```python
@route("GET", "/v1/controladoria/summary", auth="admin", permission="metrics.read", ...)
```

`authorize()` aceita a requisição quando **qualquer** destes é verdadeiro:

1. `is_platform_admin`;
2. a pessoa tem um dos papéis listados em `staff=`;
3. a pessoa tem a permissão declarada em `permission=`.

A terceira condição é a novidade da v0.22.0. Antes dela, criar o papel `finance` não dava acesso a
nada: a porta só reconhecia o booleano e a lista de papéis.

A mensagem de recusa é diferente conforme quem bate:

- quem **é** da equipe e não tem a permissão recebe `permission_denied` com
  `required_permission` — pode pedir a permissão a quem a concede;
- quem **não é** da equipe recebe `admin_only` e nada mais. A existência da área não é informação
  que se dê a quem não tem nenhum papel nela.

Depois da porta, `auth="admin"` ainda exige MFA verificado **na sessão** quando
`require_mfa_for_admins` está ligado.

## 6. Step-up: reautenticação para operação sensível

17 permissões exigem identidade confirmada nos últimos 15 minutos (`STEP_UP_PERMISSIONS` em
`core/access.py`): aprovar, escrever ou fechar em finanças e contabilidade, estornar, emitir ou
cancelar documento fiscal, mexer em chaves, exportar auditoria, escrever usuários ou organizações,
executar manutenção, **e alterar orçamento ou centro de custo** — quem muda a régua muda o
resultado de todas as medições feitas depois.

`POST /v1/auth/reauth` confere senha e, **obrigatoriamente**, o segundo fator de quem o tem.
Aceitar só a senha de quem tem MFA seria oferecer o fator mais fraco justamente na operação mais
perigosa. O carimbo fica em `sessions.reauth_at`.

Havia **três cópias** de confirmação de identidade (privacidade, confiança, documentos), cada uma
conferindo a senha no próprio handler. Três cópias de uma regra de segurança divergem na primeira
vez que alguém endurece uma e esquece as outras. Agora há uma: `ACCESS.verify_identity()`. A
exclusão de conta ganhou MFA de brinde — antes, apagar a conta de quem tem segundo fator pedia
apenas a senha.

## 7. Alçada: quatro olhos de verdade

`approval_policies` / `approval_rules` / `approval_requests` / `approval_decisions`.

A alçada é **dado no banco**, não constante em código: mudar faixa é decisão de governança, e
exigir implantação para isso faz a decisão ser tomada por quem tem acesso ao servidor em vez de por
quem responde pelo dinheiro.

Oito faixas vigentes, por operação e valor. Duas regras são **gatilho**, não conferência de tela:

- `approval_no_self()` — quem pede não aprova; e numa faixa que exige permissões diferentes, a
  mesma permissão não serve duas vezes. Duas aprovações do mesmo papel são duas pessoas com o mesmo
  ponto cego.
- `approval_settle()` — o fechamento do pedido é contado **dentro da transação**. Contar na
  aplicação é a conta que diverge quando duas aprovações chegam no mesmo instante.

## 8. Trilha de acesso privilegiado

`privileged_access_log` registra cada entrada de papel interno: quem, quando, quais papéis,
qual permissão, método, rota, requisição, IP. Append-only por gatilho `forbid_mutation()` — que
recusa alteração e remoção **inclusive para o papel proprietário do banco**, porque gatilho não
olha papel.

Responde "quem olhou", e não só "quem mudou". A trilha de auditoria (`audit_events`) continua
registrando o que mudou; são perguntas diferentes.

## 9. O menu interno vem do servidor

`GET /v1/me/context` devolve, além da identidade e dos entitlements, o **menu** agrupado que esta
pessoa pode receber — derivado da mesma matriz que a porta confere. Cada item declara a permissão
que o justifica.

Dois testes garantem que o menu não minta:

- todo item oferecido é um item que a API concede (por papel, para 12 papéis);
- todo item aponta para uma rota que existe no roteador web.

E um terceiro fecha o buraco inverso: **todo domínio de permissão usado por alguma rota tem de
aparecer em algum item de menu**. É o que transforma "224 rotas sem tela" num defeito que reprova,
em vez de uma descoberta de auditoria. Foi esse teste que encontrou o FULL FREE 2026 — rota,
serviço, banco e teste desde a v0.21.0, e nenhuma tela.

## 10. Painel inicial resolvido no servidor

`dashboard_for()` decide o destino. A ordem é por **especificidade**, e duas decisões dela foram
corrigidas por defeito encontrado em teste:

1. A auditoria vem **antes** do financeiro, embora leia o financeiro. O que define a auditoria não
   é o que ela lê — ela lê quase tudo — é que ela não altera nada. Mandá-la ao painel financeiro
   ofereceria botões que a própria permissão dela recusa.
2. O que distingue a controladoria da contabilidade não é ler mais coisas (contabilidade tem as
   duas leituras): é **aprovar**. A primeira versão usava
   `"finance.approve" in p or "finance.read" in p and "accounting.read" in p` e mandava a
   contabilidade para `/controladoria` — precedência de `or`/`and` em Python.

## 11. O que foi testado

`backend/tests/test_v0220_authorization.py` (32 testes) e
`backend/tests/test_v0220_internal_ui.py` (27 testes). Entre eles:

- suporte não vê receita, **embora alcance a área administrativa**;
- cliente não alcança nenhum painel interno (8 rotas conferidas uma a uma);
- a matriz é dado: o teste lê o banco, não uma lista no teste;
- o step-up é real: três testes usam `make_admin_without_reauth()` e provam que a operação é
  recusada sem reautenticação — inclusive para administrador;
- a trilha de acesso privilegiado grava;
- o menu casa com a porta, papel por papel.

## 12. O que NÃO está implementado

Dito explicitamente para que ninguém o conte como feito:

- **ABAC por atributo de recurso** (ex.: "só o gestor daquele projeto"). O que existe é RBAC com
  escopo de organização pela RLS. Regra por atributo de linha, além do `org_id`, não existe.
- **Risco por IP ou dispositivo** na porta administrativa. Há limite de taxa e MFA; não há
  pontuação de risco de dispositivo.
- **Sessão mais curta para área interna**. A sessão é a mesma; o que é curto é a janela de
  step-up (15 minutos).
- **`fiscal.issue` / `fiscal.cancel`** existem no catálogo como exclusivas de `super_admin`, e
  **nenhum provedor fiscal está ligado**: a permissão existe, a emissão não.
- **Busca global (⌘K)** e **Quick Actions** não foram implementadas nesta versão.
