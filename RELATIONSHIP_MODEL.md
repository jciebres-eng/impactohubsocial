# A relação única (v0.16.0)

`relationships` substitui seis tabelas improvisadas por uma. Este documento é a referência de quem vai usar ou revisar
a tabela: os tipos, o que cada um aceita como destino, o teto de visibilidade, quem pode mudar o quê.

## Os 22 tipos

### Unilaterais — nascem ativos, não dependem de o outro lado aceitar

Seguir alguém não é pedir permissão. Favoritar é estratégia de quem favoritou.

| Tipo | Rótulo | Destinos aceitos | Teto de visibilidade |
|---|---|---|---|
| `favorite` | Favorito | projeto, solução, edital, organização, ideia | **privado** |
| `watchlist` | Acompanhamento | projeto, organização, edital | **privado** |
| `follow` | Seguindo | organização, pessoa | rede |
| `block` | Bloqueio | organização, pessoa | **privado** |
| `referral` | Indicação | organização, pessoa, projeto | rede |

### Com consentimento — nascem `pending`, viram `active` quando o destino aceita

| Tipo | Rótulo | Destinos aceitos |
|---|---|---|
| `contact` | Contato | organização, pessoa |
| `partnership` | Parceria | organização |
| `investment` | Investimento | projeto, organização |
| `sponsorship` | Patrocínio | projeto, organização |
| `service` | Prestação de serviço | organização, projeto |
| `mentorship` | Mentoria | organização, pessoa |
| `volunteer` | Voluntariado | projeto, organização |
| `collaboration` | Colaboração | organização, projeto |
| `support` | Apoio | projeto, organização |
| `government_support` | Apoio governamental | projeto, organização |
| `verified_by` | Verificada por | organização, pessoa |

### Participação em projeto — criada por quem administra o projeto, nasce ativa

`project_member`, `project_partner`, `project_sponsor`, `project_investor` — todas com destino `project`.

### Criada só por motor

`proposal` — nasce do motor de propostas e não é criável pela rota direta (`ENGINE_ONLY`).

## Visibilidade: cinco níveis, com teto por tipo

| Nível | Quem vê |
|---|---|
| `private` | somente a organização que criou |
| `participants` | as partes da relação |
| `organization` | membros da organização dona |
| `network` | quem tem conta na plataforma |
| `public` | qualquer pessoa, inclusive sem conta |

`cap_visibility()` **rebaixa em silêncio** ao teto do tipo, em vez de recusar. A escolha é deliberada: quem pede
"público" num bloqueio provavelmente errou o campo, e o custo de atender o pedido é vazar um juízo sobre terceiro; o
custo de rebaixar é um aviso a menos. Há um invariante que percorre os cinco níveis para os três tipos privados e
verifica que nenhum deles chega a `network`.

## A máquina de estados

```
pending ──→ active ──→ paused ──→ active
   │           │          │
   │           └──────────┴──→ ended      (exige motivo)
   ├──→ declined   (exige motivo, só o lado de DESTINO)
   └──→ revoked    (exige motivo, só o lado de ORIGEM)
```

`ended`, `declined` e `revoked` são **terminais** — relação encerrada não ressuscita, e há um invariante que verifica
que as três não têm saída. Para retomar, cria-se outra relação, que é honesto: o histórico mostra as duas.

Quem pode o quê:

* `pending → active` ou `declined`: **só o lado de destino**. Sem isso, uma organização poderia declarar-se parceira
  de outra sozinha — e a plataforma existe para que uma afirmação dessas valha algo.
* `→ revoked`: só quem criou.
* `→ paused`/`ended`: qualquer das partes, **com motivo** (mínimo 3 caracteres). Encerramento sem motivo é o que torna
  um histórico de rede inútil seis meses depois.

No banco, a política `rel_update` permite que o destino escreva, e o gatilho `counterpart_columns` limita a
contraparte a mudar **apenas** `status`, `ended_at` e `ended_reason` — sem ele, quem recebe uma proposta de parceria
poderia reescrever a observação da outra parte ao aceitar.

## O espelho da camada antiga

`follows`, `favorites` e `org_blocks` continuam sendo a fonte das rotas que já existiam. O gatilho `rel_mirror`
(SECURITY DEFINER, em INSERT e DELETE) cria e remove a relação correspondente, com `mirrored_from` dizendo de onde
veio. Relação espelhada **não aceita transição pelo motor** (responde 422 apontando a tabela de origem), porque mudar
o espelho sem mudar a fonte produziria duas verdades.

Isso é o que permitiu a migração ser aditiva: nenhuma rota existente parou, e a rede passou a ver tudo.

## O grafo

`relationships.graph(org_id, depth)` devolve a vizinhança em profundidade 1 ou 2, por consulta recursiva, somente com
relações **ativas**, de visibilidade `network`/`public`/`organization`, e **excluindo bloqueios**. Medição com 10 mil
relações: 12 ms em profundidade 2. A razão de não haver banco de grafos está em `IMPACT_NETWORK_ARCHITECTURE.md`.
