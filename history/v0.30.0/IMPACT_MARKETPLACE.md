# Marketplace de impacto (v0.16.0)

## O achado que originou esta entidade

Antes desta versão, a visibilidade pública de um projeto era a combinação de `projects.visibility` com
`projects.status`, **avaliada em cada consulta de feed**. Isso significa que um `WHERE` esquecido em qualquer rota nova
expõe rascunho — exatamente o cenário que o pedido proíbe: "nunca permitir que projeto privado apareça no marketplace
por erro de query".

A correção é estrutural, não cuidadosa.

## Publicação é estado da entidade

Existe `marketplace_listings`, com `publication_state` em oito estados, e a consulta pública lê
`WHERE publication_state = 'published'`. O projeto privado **não tem anúncio publicado**; não há condição a esquecer.

```
draft ──→ review ──→ approved ──→ published ──→ paused ──→ published
  │                                   │  │         └──→ archived
  │                                   │  └──→ expired (plataforma) ──→ draft
  └──→ archived                       └──→ suspended (ADMINISTRAÇÃO, exige motivo) ──→ draft/archived
```

Três travas no banco, não na rota:

1. **`listing_publish_guard()`** recusa publicar anúncio cujo sujeito (projeto, solução) não esteja publicado. A
   recusa chega como 403, vinda do banco.
2. **`listing_state_guard()`** valida a transição contra `network_status_graph` e deriva `published_at`/`published_by`.
   Suspender e liberar são `actor='admin'`: a organização recebe 403 `admin_only` se tentar.
3. **`network_initial_state()`** garante que nada nasce publicado, mesmo por SQL do papel da aplicação.

E `CHECK ((publication_state = 'published') = (published_at IS NOT NULL))` impede os dois estados inconsistentes.

## O filtro vive em um lugar só

`marketplace.public_feed()` é a **única** leitura pública, e `publication_state = 'published'` está escrito ali. Quem
precisa contar anúncios no ar chama `has_published_listing()` ou `published_count()` — e há um invariante que falha se
a condição aparecer em qualquer outro módulo de `api/`, `network/` ou `services/`. É assim que um `WHERE` se perde, e
é por isso que o teste existe.

A seção "descobrir" de **todos** os workspaces passa por essa função. Nenhuma persona tem consulta própria de
descoberta.

## O que se anuncia e o que se busca

Sete tipos de sujeito (`project`, `opportunity`, `need`, `service`, `solution`, `partnership`, `sponsorship`), com
`CHECK` garantindo exatamente um; e nove buscas (`seeking`): investimento, patrocínio, parceira, profissional,
voluntariado, mentoria, equipamento, conhecimento, cotas. Um anúncio por sujeito (`ux_listing_subject`): dois anúncios
do mesmo projeto seriam duas verdades sobre o que ele precisa.

`amount_target_cents` é **nulo** quando não há valor. A plataforma não inventa número.

## Suspensão

Só a administração suspende, **com motivo** (`CHECK` exige ≥ 3 caracteres), e o motivo não se apaga ao liberar — o
gatilho preserva `suspended_reason`. O motivo nunca sai no feed público: `public_feed()` e `view()` removem a coluna da
resposta, porque anúncio suspenso não aparece em público e o motivo é interno.

## Visualizações

`views` é coluna protegida por `guard_columns`: o número de visualizações é apuração da plataforma, não valor que a
organização possa inflar.
