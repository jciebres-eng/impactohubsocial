# Arquitetura da informação (v0.16.0)

Documento escrito **para o designer**. Diz o que o produto tem, como está organizado hoje, e onde a organização atual
é insuficiente — porque, nas palavras do pedido, "o problema maior não é mais 'qual cor usar'. É **qual produto esses
componentes precisam representar**".

## O inventário real

| | Quantidade |
|---|---|
| Rotas de API | 704 |
| Telas registradas no roteador (`app.tsx`) | 178 |
| Arquivos de página (`web/src/pages/*.tsx`) | 35 |
| Tabelas | 231 |
| Itens de menu, por tipo de organização | OSC 36 · Empresa 26 · Governo 22 · Profissional 22 · Apoiador 18 · Administração 27 |

**Os números acima são o problema de design desta rodada.** Trinta e seis itens numa lista plana não é navegação; é um
índice. O backend está pronto e provado; a hierarquia visual não está.

## A espinha dorsal: a cadeia de impacto

Toda a informação do produto pendura-se numa cadeia única, que o pedido enuncia assim:

```
Pessoa/Organização → Contexto → Necessidade/Objetivo → Rede → Match → Proposta
    → Relação → Projeto → Execução → Evidência → Resultado → Novo Match
```

Isto **não** é uma metáfora: cada elo é tabela e rota (ver `IMPACT_NETWORK_ARCHITECTURE.md` §cadeia). A consequência
para a AI é direta: **a navegação deveria refletir a cadeia, não o histórico de versões do produto.** O menu de hoje
reflete a ordem em que as funções foram construídas (v0.1 a v0.16), e é por isso que "Prontidão" e "Prontidão por
finalidade" aparecem separadas por doze itens.

## Os sete domínios de informação

Proposta de agrupamento, derivada da cadeia — é a decisão de AI que o designer deve acolher ou contestar:

**1 · Identidade** — quem a organização é.
Instituição · perfil institucional · diagnóstico · identidade · credenciais · perfil público e identificador `@` ·
experiências declaradas · verificação pública · conquistas.

**2 · Necessidade e oferta** — o que se procura e o que se oferece.
Marketplace (descobrir) · meus anúncios · necessidades do território · editais e programas · oportunidades ·
oportunidades profissionais · ideias.

**3 · Rede** — com quem.
Relações · atividade da rede · conversas · profissionais parceiros · mensagens.

**4 · Negociação** — como se combina.
Propostas (recebidas e enviadas) · candidaturas · acordos · rascunhos.

**5 · Execução** — o que se faz.
Projetos · prontidão · prontidão por finalidade · documentos · montagem de documentos · minhas atividades ·
validações · campanha · cotas.

**6 · Resultado** — o que se prova.
Relatórios de impacto · relatórios · carteira e resultados · mapa · dados do território · determinantes sociais ·
biblioteca de soluções · replicação · materiais.

**7 · Administração** — a conta e a plataforma.
Pagamentos · cobrança · equipe · vocabulário · e o conjunto de administração da plataforma (denúncias, medidas,
filas, chaves, auditoria).

Cada item de menu existente cabe em **exatamente um** desses sete. Nenhum ficou de fora; nenhum caiu em dois.

## Os três níveis de leitura

A informação tem três densidades, e hoje a interface só distingue duas:

| Nível | Pergunta | Onde vive |
|---|---|---|
| **Decidir** | "o que faço agora?" | `GET /v1/workspace` — próximas ações com razão e destino |
| **Trabalhar** | "deixe-me fazer esta coisa" | as 178 telas |
| **Comprovar** | "mostre-me o que aconteceu" | linha do tempo, ledger, relatório publicado, atividade da rede |

O nível **decidir** foi construído nesta rodada (o workspace) e é o que ainda não tem forma visual à altura: hoje ele
é uma página entre trinta e seis.

## O que é público e o que não é

Dois mundos que nunca se misturam, e a AI tem de deixar isso óbvio na interface:

* **Público** — a vitrine (`/`, landing), o marketplace publicado, a página `impacto.app/@identificador`, a
  verificação pública. Lê **só** projeções curadas. Ver `PRIVACY_VISIBILITY_MATRIX.md`.
* **Privado** — todo o resto, com RLS por organização.

Risco de design a evitar: usar o mesmo cartão visual para um projeto publicado e um projeto em rascunho. A pessoa
precisa **ver** que ainda não publicou.

## Taxonomias centralizadas

Nada de listas soltas em cada tela. `taxonomies` + `taxonomy_terms`, versionadas, com rótulo em pt e en: causas, ODS,
tipos de organização, tipos de apoio, estágios de projeto, categorias de denúncia, grupos de beneficiário (com
`usage_policy` gravada). A interface **lê** a taxonomia; não a recria em constante de componente.

Para o designer: isso significa que listas de chips e filtros devem ser componentes **dirigidos por dados**, não
enumerações desenhadas à mão — os termos mudam sem publicar frontend novo.

## Vazios, erros e primeira vez

Estados que a interface precisa tratar e que a AI já contempla:

* **Primeira abertura** — há três recomendações de primeiro passo (completar cadastro, criar projeto, convidar
  equipe), justamente para que ninguém veja um vazio sem saída.
* **Marketplace sem resultado** — distinguir "nada corresponde ao filtro" de "ainda não há anúncios".
* **Sem plano** — o produto completo nos 14 dias de teste; depois, o que exige plano precisa dizer **o que** exige e
  **quanto custa**, nunca só "indisponível".
* **Medida de moderação ativa** — o alvo vê a medida, o efeito em português, a regra e o prazo. Não é um 403 cego.
