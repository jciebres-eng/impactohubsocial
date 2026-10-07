# Motor de propostas (v0.16.0)

Antes desta versão havia **três** fluxos paralelos de "proposta": `need_offers` (oferta a uma necessidade),
`solution_intents` (intenção sobre uma solução) e `partnership_requests` (pedido de parceria). Três vocabulários de
estado, nenhuma versão, e uma OSC que recebesse as três não tinha caixa única para responder.

## A distinção que o motor torna impossível de confundir

```
proposta   ≠   relação formalizada   ≠   compromisso financeiro   ≠   dinheiro recebido
proposals      relationships            commitments                 transactions
```

`proposals.amount_cents` é valor **proposto**. Aceitar uma proposta de investimento cria uma relação ativa e uma
**intenção** (`investment_intents` com `status='in_negotiation'`, `commitment_id` nulo). Não cria compromisso, e muito
menos recebimento. O CHECK `(status='committed') = (commitment_id IS NOT NULL)` impede uma intenção dizer-se
comprometida sem compromisso, e há invariante que aceita uma proposta de R$ 50 milhões e verifica que
`project_funding()` continua em zero.

## Os nove tipos

`investment` · `sponsorship` · `service` · `partnership` · `mentorship` · `volunteer` · `collaboration` ·
`project_support` · `government_support`

Cada um, ao ser aceito, cria a relação correspondente (`ON_ACCEPT_RELATION`) com visibilidade `participants`.

## Contexto obrigatório

A proposta exige **ao menos um** de `project_id`, `need_id`, `call_id`, `solution_id`. Proposta sem contexto é um
e-mail frio com outro nome, e a mensagem de erro (422) diz quais contextos servem. O motor também verifica que o
contexto citado **pertence** a quem vai receber — sem isso, uma proposta "sobre" o projeto de um terceiro passaria.

Sob RLS, propor sobre projeto privado de outra organização devolve **404**: não se deve nem saber que o projeto
existe. O fluxo real é descobrir no marketplace (publicado) e então propor.

## A máquina de estados, como dado

`proposal_status_graph` tem 19 transições, cada uma com o **ator** que pode fazê-la (`sender`, `receiver`, `either`,
`system`) e se **exige motivo**. A interface desenha os botões a partir dessa tabela; ninguém a reescreve em
TypeScript.

```
draft ──→ sent ──→ viewed ──→ in_review ──→ accepted
  │        │         │           │      └──→ declined           (exige motivo)
  │        │         │           └─────────→ changes_requested  (exige motivo)
  │        │         └─────────────────────→ accepted/declined/changes_requested
  │        └──→ withdrawn (exige motivo) · expired (plataforma)
  └──→ cancelled

changes_requested ──→ sent    (nova VERSÃO)
```

Duas camadas, deliberadamente: o gatilho `proposal_status_guard()` no banco recusa transição fora do grafo **mesmo em
SQL direto**, e o motor valida antes para devolver 409 com a lista do que é possível. A de cima explica; a de baixo
garante.

## Versão no reenvio, e por que o valor antigo fica

Pedir ajuste não apaga o que foi proposto. `changes_requested → sent` incrementa `version`, limpa visto/decidido, e o
histórico guarda o valor que estava em análise.

Detalhe que custou um defeito: na primeira versão, o registro do valor anterior era feito **no reenvio** — e lia o
valor já corrigido, registrando o novo como se fosse o antigo. O teste de versão apanhou. Agora o valor é registrado
**no momento do pedido de ajuste**, enquanto ainda é o que a outra parte viu.

## Carimbos que o cliente não pode forjar

`sent_at`, `viewed_at`, `decided_at`, `decided_by` e `version` são **derivados** pelo gatilho a partir da transição, e
protegidos por `guard_columns` — o cliente não tem como dizer quando a proposta foi vista nem quem decidiu. "Quando
esta proposta foi vista" deixou de ser um campo que alguém preenche e passou a ser consequência de a proposta ter
sido aberta. Há invariante que tenta forjar `viewed_at` pelo papel da aplicação e verifica a recusa.

## Quem decide

* **Só o lado de destino** aceita, recusa ou pede ajuste. Quem propôs recebe 403 (`wrong_side`) nas três.
* Recusar e pedir ajuste **exigem justificativa** (≥ 3 caracteres): decisão sem motivo não é devolutiva.
* Abrir a proposta marca como vista — mas só para quem tem papel que decide, para que um acesso de leitura não
  consuma o estado "ainda não vista" de quem apenas conferiu.
* Bloqueio entre as organizações impede propor (403 `blocked`), verificado por `app_blocked_between`.

## Avisos

**Um aviso por fato, para cada pessoa.** A primeira versão avisava a organização destinatária E a equipe do projeto,
e quem está nos dois conjuntos recebia dois avisos do mesmo fato — "avisar toda a equipe" tinha virado "avisar duas
vezes". Agora: havendo projeto, o aviso vai para a **equipe** (conjunto maior, cada pessoa uma vez); sem projeto, vai
para a contraparte. "Vista" não avisa ninguém: seria ruído, e quem enviou vê na própria caixa.

## Anexos

`proposal_attachments` reusa o cofre (`documents`): não há segundo armazenamento. Anexar avisa a outra parte **e** a
equipe do projeto — "documentos juntados" é um dos eventos que o pedido manda avisar.
