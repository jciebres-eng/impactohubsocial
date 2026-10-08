# Arquitetura de notificação (v0.16.0)

## O pedido, literal

> "trabalhar e implementar notificações para toda a equipe envolvida em cada evolução ou modificação ou alteração de
> etapas do processo ou documentos juntados"

## O que havia antes

Três maneiras de notificar, cada chamador decidindo por conta própria:

| Função | Alcance | Idempotência |
|---|---|---|
| `notify_user` | **uma** pessoa | não |
| `notify_counterpart` | a contraparte de uma candidatura | não |
| `notify_once` | organização | sim, mas só para cobrança (`billing_notices`) |

Nenhuma delas sabia o que é "a equipe de um projeto". Resultado prático: quando um documento era anexado, ninguém além
de quem anexou ficava sabendo.

## O que é "a equipe"

`project_team(p_project)` — função SECURITY DEFINER no banco — devolve três grupos unidos:

1. quem é membro da **organização dona** do projeto;
2. quem é membro de organização com **relação de participação ativa** no projeto (parceira, executora, apoiadora…);
3. quem é membro de organização **financiadora** com candidatura aceita.

A equipe **cresce sozinha** quando uma relação nasce — sem recadastro. Na jornada 6, o financiador entra na equipe no
instante em que a proposta é aceita, e passa a ser avisado das etapas seguintes.

`GET /v1/projects/{id}/team` expõe a lista, porque "quem será avisado" é informação que a organização precisa ver.

## As três garantias

### 1. Idempotência

`notifications.dedupe_key` é único por pessoa (`ux_notif_dedupe` sobre `(coalesce(user_id, zero), dedupe_key)`).
Reprocessar um webhook, repetir um PATCH ou rodar um job duas vezes **não** gera dois avisos. Sem isso, "avisar toda a
equipe" viraria "irritar toda a equipe". A chave é `sha256(evento, projeto, referência, …)[:40]`, e quem chama pode
refinar as partes quando o mesmo evento repete legitimamente (dois marcos no mesmo projeto).

### 2. Quem agiu não é avisado

`notify_team` filtra `t.user_id IS DISTINCT FROM p_actor`. Ninguém recebe notificação do próprio clique.

### 3. Um aviso por pessoa, por fato

A primeira versão do motor de propostas avisava a organização destinatária **e** a equipe do projeto. Quem está nos
dois conjuntos recebia dois avisos do mesmo fato, com chaves de idempotência diferentes — então a trava não pegava. O
teste `test_whole_team_is_notified_once_and_the_actor_is_not` apanhou (8 avisos para 4 pessoas), e a regra passou a ser
uma só: **havendo projeto, avisa a equipe; sem projeto, avisa a contraparte**.

## Preferência respeitada, fato preservado

`notification_prefs.in_app = false` silencia o grupo para aquela pessoa. O **fato continua** em `domain_events` — só o
aviso não chega. A distinção importa: silenciar aviso é escolha de quem recebe; apagar fato seria perda de histórico.

Os grupos eram seis (`billing`, `content`, `events`, `support`, `partnerships`, `opportunities`) e a 0016 somou oito:
`network`, `proposal`, `message`, `funding`, `report`, `project`, `document`, `account`. Alguém precisa poder silenciar
"propostas" sem silenciar "cobrança".

## O fato, separado do aviso

`domain_events` grava **o fato**, uma vez, na mesma transação em que aconteceu. 37 tipos no formato `Entidade.fato`
(`Proposal.sent`, `Document.attached`, `Milestone.completed`…). O campo `notified` guarda **quantas pessoas o fato
efetivamente avisou** — e zero é resposta legítima (equipe de uma pessoa, que foi quem agiu), que fica visível em vez
de ser maquiada.

A escrita passa por `app_record_event()` (SECURITY DEFINER). A razão é estrutural: um fato da rede envolve **duas**
organizações — "proposta enviada" interessa ao histórico de quem recebeu — e uma política de inquilino recusaria
exatamente esse registro, enquanto abrir a política deixaria qualquer organização escrever no histórico de outra. A
função aceita o fato da contraparte e, em troca, amarra a autoria a `app_uid()`. `INSERT` em `domain_events` está
**revogado** para o papel da aplicação.

## Fatos de alto volume

`notify.fact_only()` registra o fato **sem** avisar. Existe para o que é frequente (cada recado numa conversa) e para
o que a pessoa já está vendo acontecer. Gravar o fato ainda importa: a linha de tempo, a auditoria e as recomendações
leem o evento, não a caixa de avisos.

Na conversa, o aviso usa como chave o **recado mais antigo não lido** daquele remetente: cinco recados seguidos geram
**um** aviso, e um novo só depois que a pessoa lê. Os cinco fatos ficam registrados.

## Um só caminho

Há um teste de arquitetura (`test_network_engines_never_notify_directly`) que verifica que nenhum motor ou rota da rede
chama `app_notify`, `notify_user` ou `notify_once` diretamente. Aviso sai só por `network.notify`, que tem a chave de
idempotência. Rota que notifica por conta própria é rota que avisa duas vezes no reprocessamento.

## Prioridade e ação

`priority` (`low`/`normal`/`high`/`critical`) muda ordenação e destaque, **nunca o canal**. `action_label`
("Analisar", "Revisar", "Contestar") é o que transforma o aviso em algo acionável — sem ele, a pessoa lê que algo
aconteceu e tem de descobrir sozinha o que fazer.

Nota de método: `notify.PRIORITIES` dizia `urgent` enquanto o CHECK do banco diz `critical`. A divergência passava por
lint, type-check e pela suíte inteira, e só apareceria na primeira notificação de prioridade máxima — que é o caminho
da moderação. Hoje há um invariante que compara **onze** listas de Python com os CHECKs correspondentes no banco.
