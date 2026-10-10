# Conversa com contexto (v0.16.0)

## O pedido

> "nunca criar chat sem contexto quando a relação é profissional"

A razão não é organização visual: uma conversa sem contexto não pode ser auditada, não entra na linha de tempo do
projeto e, seis meses depois, ninguém sabe por que aquelas duas organizações estavam conversando.

## O que foi preservado, e por quê

`conversations(org_a, org_b)` **continua** com esse par de colunas. Eu havia planejado trocar por uma tabela de
participantes, e não troquei, por dois motivos concretos:

1. A RLS de `messages` se apoia na RLS de `conversations` — um recado só é legível se a conversa for legível. Esse
   encadeamento está correto, e refazê-lo introduziria risco de vazamento sem ganho.
2. Pessoa física já participa da plataforma através de uma organização `individual`/`provider`. O par de organizações
   não é limitação do modelo: é o modelo.

## O que mudou

A conversa ganhou **assunto**, **contexto** (projeto, proposta, necessidade ou edital), **situação**
(`open`/`archived`/`closed`) e carimbo do último recado. O recado ganhou **tipo** (`text`, `system`, `event`,
`proposal_ref`, `document_ref`), **referência** (`ref_type`/`ref_id`) e anexo pelo cofre (`message_attachments` —
o arquivo continua governado por `documents`; não há segundo armazenamento).

E a unicidade mudou: era `UNIQUE (org_a, org_b)` — **uma** conversa por par de organizações, para sempre. Com
contexto isso deixa de valer: a mesma empresa e a mesma OSC conversam sobre o projeto A e sobre o edital B, e misturar
as duas numa caixa só é o que torna a negociação ilegível. Agora a unicidade é por **(par, contexto)**, que é mais
permissiva — nenhuma linha existente deixou de ser válida.

## Reaproveitar, não multiplicar

`open_thread()` procura a conversa existente naquele contexto e devolve a mesma. Sem isso, cada clique em "conversar"
criaria uma caixa nova e a negociação ficaria espalhada em cinco linhas do tempo. O par é **ordenado** (`sorted`), de
modo que (A,B) e (B,A) são a mesma conversa.

## A trava anti-spam, e o que ela aprendeu nesta versão

`app_related(a, b)` existe desde a 0002: só se fala com quem já tem vínculo registrado. Ela conhecia candidatura,
avaliação profissional, oferta em necessidade e seguir-mútuo — tudo de antes da rede.

**Achado desta rodada:** com a rede, o investidor encontra o projeto no marketplace e não tem nenhum desses vínculos.
A conversa com contexto, que é como a relação deve começar, ficava impossível. A trava estava certa; a lista de
vínculos é que ficou incompleta.

A função foi estendida com os dois vínculos que a rede cria:

* **relação deliberada** pendente ou ativa — `contact` (que é literalmente "quero conversar"), parceria,
  investimento, serviço, mentoria, voluntariado, colaboração, apoio, participação em projeto, `verified_by`;
* **proposta já enviada** (rascunho não conta: não chegou a ninguém).

A lista de tipos é **explícita**, e não "tudo menos bloqueio". Motivo concreto: `follows` é espelhado em
`relationships`, então "tudo menos bloqueio" faria um **seguir unilateral** abrir conversa — desfazendo a regra do
seguir-mútuo. Uma regressão em `test_v080` apanhou isso.

O bloqueio continua decidindo por cima, em `app_blocked_between`, na própria política da conversa.

## A jornada que isso desenha

```
descobrir no marketplace → favoritar (privado) → registrar CONTATO → conversa com contexto → proposta
```

É a jornada do investidor descrita no pedido, e é a ordem que a jornada 2 dos testes E2E percorre.

## Fato dentro da conversa

`system_note()` registra um fato na conversa (proposta enviada, documento anexado, situação alterada). Serve para que
a conversa conte a história completa, e não só a parte digitada. Não dispara aviso: o fato já avisou por conta própria.
