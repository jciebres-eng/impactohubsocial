# Operação interna da plataforma — Impacto Trust

> As telas que a própria plataforma usa para se operar. Separadas do painel do cliente, por
> permissão, não por aparência. Documento da v0.22.0.

## 0. Por que existe

Duas lacunas da auditoria desta rodada:

1. **Não havia controladoria, contabilidade nem tesouraria da própria plataforma.** O "financeiro"
   era um punhado de rotas soltas atrás de um booleano de administrador.
2. **224 das 848 rotas (26,4%) não tinham tela nenhuma** — incluindo a saúde do sistema, a receita
   apurada, as tarefas agendadas e o Integration Hub inteiro. Construído, funcionando, invisível.
   Funcionalidade permitida que ninguém alcança não existe para quem usa.

## 1. Entrada: `/portal`

O login sem destino pedido leva a `/portal`, que **mostra** a resolução feita no servidor:

```
quem entra → organização → perfil → função → plano → recursos
           → situação financeira → papéis internos → painel
```

Com um único vínculo e nada a decidir, o portal encaminha direto ao painel — não há portal a
mostrar. Com mais de uma organização, oferece a troca de contexto antes de entrar; trocar
recarrega o `AccessContext` inteiro no servidor.

O endereço final vem de `GET /v1/me/context` (campo `dashboard`). O frontend **mostra** a decisão;
não a recalcula. Recalcular seria criar uma segunda regra para discordar da primeira.

## 2. As telas

| caminho | área | permissão | o que mostra |
| --- | --- | --- | --- |
| `/controladoria` | Controladoria | `metrics.read` | MRR, ARR, receita por competência, caixa, despesa, custo de IA, queima, autonomia, GMV, conversão, pendências |
| `/controladoria/conciliacao` | Controladoria | `finance.read` | esperado contra acontecido, em quatro blocos; aponta, não corrige |
| `/aprovacoes` | Controladoria | `finance.read` | pedidos pendentes com quantas faltam e quais permissões servem; faixas vigentes |
| `/financeiro` | Financeiro | `finance.read` | a receber, a pagar, vencido, caixa, despesa por centro de custo, instruções em aberto |
| `/financeiro/despesas` | Financeiro | `finance.read` | registra despesa (abre aprovação) e lista a competência, com quem registrou e quem aprovou |
| `/financeiro/instrucoes` | Financeiro | `instruction.read` | cria, emite e registra execução com evidência |
| `/v1/financeiro/instructions` | (rota) | `instruction.read` | a leitura própria da tela: ela lia o resumo financeiro, e o menu a oferecia por uma permissão que nenhuma rota exigia |
| `/financeiro/periodos-gratuitos` | Financeiro | `free_period.write` | quem está sem pagar, por qual motivo, concedido por quem, até quando |
| `/contabilidade` | Contabilidade | `accounting.read` | balancete, situação da competência, lotes que não fecham, fechamento |
| `/contabilidade/plano-de-contas` | Contabilidade | `accounting.read` | 43 contas (sintética × analítica) e 11 centros de custo |
| `/tesouraria` | Tesouraria | `treasury.read` | disponível, aplicado, a receber, a pagar, posição líquida — patrimônio **próprio** |
| `/administrativo/orcamento` | Administrativo | `budget.read` | orçado × realizado por mês, conta e centro de custo, com alertas em 80% |
| `/operacoes` | Operações | `health.read` | Health Center: banco, migrações, tarefas, backup, canário de e-mail, cobrança presa, integrações |
| `/operacoes/alertas` | Operações | `health.read` | Central de Alertas por prioridade |
| `/auditoria` | Auditoria | `security.audit.read` | quem entrou com papel interno, quando, em qual rota, com qual permissão |
| `/admin/permissoes` | Segurança | `admin.users.read` | matriz papel → permissão, lida do banco |
| `/admin/integracoes` | Operações | `integration.read` | provedores declarados com a maturidade real de cada um |

A barra lateral interna é montada a partir de `GET /v1/me/context`, agrupada, **derivada das
permissões**. O que não aparece também não passa pela porta da API (`AUTHORIZATION.md` §9).

A lista fixa que restou de `NAV.platform` só é oferecida a quem tem `is_platform_admin` — porque
são exatamente as rotas que ainda exigem o booleano e não têm permissão nomeada.

## 3. Health Center

Reúne numa resposta o que estava em três rotas sem tela nenhuma
(`/v1/admin/ops/health`, `/v1/admin/jobs`, `/v1/admin/integrations/overview`). Um painel de saúde
que ninguém abre não informa nada.

Seis serviços, cada um com estado (`ok` / `warn` / `fail` / `unknown`) e o detalhe que justifica o
estado: banco de dados, tarefas agendadas, backup, canário de e-mail, cobrança, integrações.

A tela diz, na própria tela: *nenhum provedor está em produção; o backup local conferido não é
recuperação de desastre sem cópia externa.*

## 4. Central de Alertas

Os alertas são **derivados do estado real**. Não há tabela de alerta, porque não há alerta sem
causa: cada linha aponta o registro que a originou (`object_type` + `object_id`), e desaparece
quando a causa é corrigida — nunca sobrevive a ela.

Prioridades: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `INFO`. Alertas implementados: cobrança aberta há
mais de dois dias, instrução de pagamento vencida, aprovação pendente, backup nunca concluído,
chamada de IA sem preço declarado, minuta legal que exige aceite ainda em rascunho.

## 5. Uma trilha de execução de tarefa

Havia **duas tabelas** registrando a mesma coisa: `job_runs` (22 tarefas, **sem** duração e **sem**
campo de erro) e `ops_job_runs` (2 tarefas, com duração, erro e detalhe). Perguntar "o backup
rodou?" dava respostas diferentes dependendo de onde se olhava — e a tabela que cobria mais tarefas
era a que sabia menos sobre elas.

A v0.22.0 unificou: uma tabela (`ops_job_runs`), **um** gravador (`ops/runs.py::record`), o
histórico da antiga migrado para dentro dela e a antiga removida — deixá-la vazia no esquema
garantiria que alguém voltasse a escrever nela em seis meses. `running` passou a ser estado válido:
execução em curso não é "pulada".

A unificação revelou um defeito que a tabela sem restrição escondia: uma tarefa se chamava
`import:<nome da fonte>` — identidade misturada com parâmetro, em texto livre vindo do cadastro.
Não havia como perguntar "a importação rodou?", só "a importação da fonte X rodou?", para um X que
ninguém sabia enumerar. A fonte foi para o detalhe, que é onde se guarda parâmetro.

`due()` conta do **último sucesso**, não da última tentativa. Contar da tentativa faria uma falha
repetida parecer "já rodou": o backup falharia às 3h, a próxima janela só abriria no dia seguinte e
ninguém teria backup por 24 horas.

## 6. Dados de demonstração

`python -m impacto.cli seed-demo` (bloqueado fora de `development`/`test`) cria **seis contas
internas por função** — controladoria, financeiro, contabilidade, tesouraria, operações, auditoria
— além das já existentes. Com um administrador único, a separação entre quem atende chamado e quem
vê receita existe no banco e não aparece para ninguém.

E cria dados para que as telas possam ser conferidas por uma pessoa: três competências (a mais
antiga **fechada**, para a tela poder mostrar a diferença entre mês fechado e mês aberto), nove
lotes contábeis balanceados, cinco despesas, orçamento aprovado com 48 linhas, quatro instruções
(uma executada com evidência, uma vencida, uma emitida, uma aguardando aprovação) e quatro pedidos
de aprovação pendentes.

Tudo marcado como fictício. O seed é executado por teste contra os gatilhos reais: um seed que
quebra em silêncio não demonstra nada.

## 7. O que NÃO foi implementado

- **Busca global (⌘K)** e **Quick Actions**.
- **Fornecedores, contratos, ativos e depreciação** como módulos próprios. O que existe é o
  fornecedor como campo da despesa e da instrução.
- **Projeção de 30/90/365 dias** e comparação realizado × orçado × forecast. Há orçado × realizado.
- **Extrato navegável com saldo inicial e final por conta**, filtros por provedor e detalhe de
  transação com trilha. Há balancete por competência e caixa por período.
- **Payouts** — e não serão implementados: `NON_CUSTODIAL_ARCHITECTURE.md` §7 recusa.
- **Modo auditoria com antes/depois por campo.** `audit_events` guarda a ação e o objeto; a
  comparação campo a campo de valor anterior e novo não está implementada para todas as entidades.
- **Refino visual.** Esta é a camada funcional mínima: as telas existem, respondem e podem ser
  conferidas. O desenho é a fase seguinte.

## 8. Correções de auditoria independente

Depois de a suíte estar verde, uma auditoria independente conferiu cada afirmação deste documento
contra o código. Quatro correções nas telas:

- a tela de **orçamento** chamava `/v1/administrativo/orcamento` e a rota era `/budget`: erro em
  toda abertura. Agora há um teste que lê as chamadas de API das telas internas e exige que todas
  existam no roteador;
- **sete indicadores do painel executivo** liam chaves que a resposta não tem, e o componente
  devolvia `null` em silêncio — receita bruta, receita líquida, entradas, saídas, queima e
  autonomia **desapareciam** sem erro visível;
- a tela **reimplementava a alçada em JavaScript** para escolher quais permissões servem, com
  desempate diferente do SQL. A faixa passou a vir resolvida do servidor
  (`permissions_available`, `remaining`);
- a tela calculava o **saldo do balancete** no navegador e obrigava a justificativa de recusa só
  pelo botão desabilitado. O saldo passou a ser apurado no servidor, com a regra escrita na
  resposta, e a justificativa passou a ser exigida pela rota — a obrigatoriedade existia apenas no
  navegador, e a rota aceitava recusa sem motivo com 200.
