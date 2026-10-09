# Matriz de privacidade e visibilidade (v0.16.0)

Este documento existe para que a pergunta "quem vê o quê" tenha **uma** resposta consultável, e para que a revisão de
privacidade não dependa de ler onze motores.

## O princípio

> **A existência de uma relação não implica que ela seja visível.**

Nenhum motor da rede decide autorização por "existe relação". Autorização é RLS mais papel; visibilidade é o campo
`visibility`. São coisas diferentes, e confundi-las é como se vaza.

## Matriz por entidade

| Entidade | Anônimo | Quem tem conta | A organização | As partes | Administração |
|---|---|---|---|---|---|
| `relationships` `private` | — | — | — | dona | ✓ |
| `relationships` `participants` | — | — | dona | ambas as partes | ✓ |
| `relationships` `organization` | — | — | membros da dona | partes | ✓ |
| `relationships` `network` | — | ✓ | ✓ | ✓ | ✓ |
| `relationships` `public` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `proposals` | — | — | — | **só as duas partes** | ✓ |
| `proposal_events` | — | — | — | só as partes | ✓ |
| `conversations` / `messages` | — | — | — | só as duas organizações | ✓ |
| `marketplace_listings` `draft`…`approved` | — | — | dona | — | ✓ |
| `marketplace_listings` `published` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `marketplace_listings` `suspended` | — | — | dona (com o motivo) | — | ✓ |
| `impact_updates` até `accepted` | — | — | dona | quem apoia o projeto | ✓ |
| `impact_updates` `published` | ✓ (via projeto publicado) | ✓ | ✓ | ✓ | ✓ |
| `investment_intents` | — | — | investidora | partes do projeto | ✓ |
| `readiness_snapshots` | — | — | dona | — | ✓ |
| `recommendations` | — | — | dona | — | ✓ |
| `domain_events` | — | — | dona | parte do projeto | ✓ |
| `notifications` | — | — | a pessoa | — | ✓ |
| `public_profiles` `public` | ✓ (só `public_fields`) | ✓ | ✓ | ✓ | ✓ |
| `public_profiles` `network` | 401 | ✓ | ✓ | ✓ | ✓ |
| `public_profiles` `private`/suspenso | **404** | 404 | dona | — | ✓ |
| `enforcement_actions` | — | — | **o alvo vê a sua** | — | ✓ |
| `price_change_notices` | — | — | a organização avisada | — | ✓ |
| `territory_needs` | conforme `visibility` | ✓ | dona | — | ✓ |
| `taxonomies` / `personas` | — | ✓ | ✓ | ✓ | ✓ |

## Teto de visibilidade por tipo de relação

| Tipo | Teto | Por quê |
|---|---|---|
| `block` | `private` | publicar um bloqueio é expor um juízo sobre terceiro |
| `favorite` | `private` | é a estratégia de quem investe |
| `watchlist` | `private` | idem |
| `contact` | `participants` | o convite para conversar é entre as duas |
| `proposal` | `participants` | idem |
| `follow` | `network` | seguir é ato público entre quem tem conta |
| `referral` | `network` | indicação é referência, não contrato |
| demais | `public` (se a dona escolher) | parceria e apoio podem ser afirmados publicamente |

`cap_visibility()` rebaixa em silêncio. Invariante: percorre os cinco níveis para os três tipos privados e verifica
que nenhum chega a `network`.

## A página pública

`public_profiles.public_fields` é uma **projeção curada** montada pelo servidor em `rebuild_projection()`. A rota
pública lê **só essa coluna** — nenhuma tabela privada entra naquela consulta. Consequência prática: se amanhã alguém
acrescentar uma coluna sensível a `organizations`, ela não aparece na página pública por descuido, porque a página não
consulta `organizations`.

Três camadas:

1. **`PROJECTABLE`** — lista fechada do que *pode* entrar (18 chaves).
2. **`NEVER_PUBLIC`** — lista do que *nunca* entra: `cnpj`, `email`, `phone`, `address`, `document_number`,
   `compliance_status`, `compliance_risk`, `beneficiary_group`, `sensitive`, `cpf`, `birth_date`, `bank`, `revenue`.
3. **`_assert_no_private()`** — rede de segurança que **falha na gravação** se qualquer chave proibida aparecer na
   projeção. Não substitui a lista fechada: é a segunda tranca, para que um refactor futuro erre em desenvolvimento e
   não em produção.

O que a projeção **nunca** inclui, mesmo com o interruptor ligado:

* **número** de registro profissional — a página diz "tem CREA/SP verificado", não qual é o número;
* credencial **não verificada** — a página pública não repassa afirmação sem conferência;
* experiência **não confirmada** por quem administra a organização citada;
* relatório de impacto não **publicado** (e publicar só acontece depois de alguém de fora aceitar);
* relação que não seja `public`;
* contato, salvo se `show_contact` estiver ligado (padrão **desligado**).

Perfil suspenso responde **404**, não 403: dizer "existe, mas está suspenso" é informação sobre a moderação.

## Grupo beneficiário

> "Este projeto atende mulheres em situação de vulnerabilidade" → atributo do projeto/necessidade.
> "Esta pessoa é mulher e pertence a determinado grupo vulnerável" → **dado pessoal sensível**.

A coluna `beneficiary_groups` existe em **uma** tabela: `territory_needs`. Há um invariante que consulta
`information_schema` e falha se ela aparecer em qualquer outra. Nenhuma rota a aceita como filtro de **busca** (o
invariante percorre os modelos de `query` de todas as 704 rotas); aceitá-la no **corpo** de "registrar necessidade" é
o uso legítimo, e a diferença entre os dois é exatamente o ponto.

A `usage_policy` do termo está gravada no banco: "não pode ser usado para filtrar, segmentar ou inferir
característica de pessoa". A plataforma **não infere** atributo pessoal sensível em nenhum caminho.

## Quem denuncia

`reports.reporter_anonymous` é verdadeiro por padrão, com COMMENT na coluna dizendo que o alvo nunca vê o denunciante.
`enforcement.target_view()` — a única leitura que o alvo tem — não seleciona nenhuma coluna de denunciante, e há teste
que verifica a ausência da palavra na resposta.

## Travessia sem recursão

Políticas que precisam consultar outra tabela usam função SECURITY DEFINER (`rel_is_party`, `proposal_is_party`,
`app_project_supporter`, `project_team`). A razão está no ADR-104: política que consulta outra tabela diretamente
produz "infinite recursion detected in policy". São 63 funções SECURITY DEFINER, **todas** com `search_path` fixo
(verificado pelo relatório de integridade).
