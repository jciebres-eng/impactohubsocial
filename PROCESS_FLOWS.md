# PROCESSOS E FLUXOS VISUAIS — POR PERFIL (v0.21.0)

**O que este documento responde:** quais processos a plataforma mapeia, onde cada um aparece em
tela, e o que ainda não tem mapa.

---

## 1. O COMPONENTE

Há **um** elemento de fluxo visual: `Trail` (`web/src/ui/trail.tsx`). Lista ordenada com bolinhas
numeradas, ✓ no concluído, anel na etapa atual, `aria-current="step"`, linha conectora em CSS.

Até a v0.21.0 ele aparecia em **uma tela só** — o detalhe de candidatura —, e três trilhas definidas
no próprio arquivo nunca chegavam a lugar nenhum. Um componente de identidade usado uma vez é um
componente que a próxima tela esquece. Há teste que trava isso
(`test_the_trail_is_used_in_more_than_one_place` e `test_every_trail_defined_is_actually_rendered`).

---

## 2. OS CINCO FLUXOS, E ONDE APARECEM

| Fluxo | Etapas | Origem das etapas | Onde aparece |
| --- | ---: | --- | --- |
| **Jornada do perfil** | 4 a 15 | `config/onboarding_paths.json` | `/area` (entrada de todo perfil) e `/ajuda/comece-aqui` |
| **Candidatura** | 9 / 7 / 6 | `PLATFORM_TRAIL`, `INTEREST_TRAIL`, `EXTERNAL_TRAIL` | `/candidaturas/:id` |
| **Ciclo do projeto** | 4 fases | `core/lifecycle.py::phase()` sobre 17 situações | `/projetos/:id/situacao` |
| **Montagem de documento** | 6 | `document_assemblies.status` | `/documentos/montagens/:id` |
| **Formalização da OSC** | variável | `config/formalization_path.json` | `/instituicao` (aba) |

Nenhuma dessas etapas é inventada para a tela: cada uma é um valor que o backend já produzia. A
tela desenha o que o servidor decide.

---

## 3. JORNADA POR PERFIL

De `config/onboarding_paths.json`, com `detector` por **dado real** — não por autodeclaração. Uma
etapa só fica concluída quando existe o dado que ela produz.

| Perfil | Título | Etapas |
| --- | --- | ---: |
| `osc` | Primeiros passos da OSC | 15 |
| `company` | Primeiros passos do financiador (empresa/instituto) | 7 |
| `provider` | Primeiros passos do profissional | 5 |
| `individual` | Primeiros passos do financiador (pessoa física) | 4 |
| `government` | Primeiros passos do órgão/instituição | 4 |
| `platform` | **não existe** | — |

A cobertura é desigual por um motivo que vale dizer: a plataforma foi construída a partir da
jornada da OSC, e os outros perfis vieram depois. Quinze etapas contra quatro não é equilíbrio de
produto, é ordem de construção — e o arquivo se declara **HIPÓTESE**, não jornada validada.

A tela repete essa declaração ("Jornada em validação editorial") em vez de deixar a trilha passar
por validada só porque ficou bonita. Há teste para isso.

---

## 4. MODELOS DE DOCUMENTO, POR LADO DA PARCERIA

| Modelo | Lado | Campos | Fonte |
| --- | --- | ---: | --- |
| `projeto_tecnico_base` | quem propõe | 26 | estrutura própria da plataforma |
| `plano_trabalho_mrosc` | quem propõe | 12 | art. 22 da Lei 13.019/2014 |
| `plano_monitoramento_base` | quem propõe | 11 | estrutura própria |
| `edital_chamamento_mrosc` | **quem fomenta** | 24 | art. 24 da Lei 13.019/2014 |
| `termo_parceria_mrosc` | **quem fomenta** | 27 | art. 42 da Lei 13.019/2014 |

Os dois últimos são da v0.21.0. Até então só havia modelos do lado de quem propõe — quem publica
edital e quem formaliza a parceria não tinha nenhum.

### Por que não há modelo para empresa, financiador privado e profissional

Pela mesma razão, invertida. Os dois modelos novos existem porque há **fonte legal citável** para a
estrutura deles. Não existe texto normativo dizendo o que uma política de investimento social
privado, uma carta de intenção de financiador ou uma proposta técnica de consultoria precisa
conter.

Inventar essa estrutura produziria um modelo que **parece** padrão e não é padrão de nada — e
alguém o usaria achando que segue alguma norma. Fica como lacuna declarada, não como entrega.

Qualquer organização pode criar os próprios modelos (`POST /v1/document-templates`, papel `admin`),
com a mesma estrutura de seções, tipos de campo, obrigatoriedade, derivação do domínio e exigência
de evidência.

---

## 5. VISIBILIDADE POR PERFIL

| Perfil | Itens no menu | Documentos | Montagens | Modelos |
| --- | ---: | --- | --- | --- |
| `osc` | 41 | sim | sim | sim |
| `company` | 30 | sim | sim | sim |
| `government` | 27 | sim | **sim (novo)** | **sim (novo)** |
| `provider` | 26 | sim | **sim (novo)** | **sim (novo)** |
| `individual` | 18 | não | não | não |
| `platform` | 27 | não | não | não |

Antes da v0.21.0, `/documentos/modelos` **não estava no menu de nenhum perfil** — só se chegava a
ela por um link dentro de `/documentos`. E `/documentos/montagens` aparecia só para `osc` e
`company`, embora a rota sempre tenha permitido todos os perfis. Funcionalidade permitida e
invisível é funcionalidade que não existe para quem usa.

`individual` e `platform` continuam sem cofre de documentos **por desenho**: a pessoa física apoia
e acompanha, não monta documento de projeto; a organização da plataforma administra, não propõe.
Há teste que exige a regra, e não o resultado: *todo perfil que tem `/documentos` também alcança
montagens e modelos*.

---

## 6. O QUE AINDA NÃO TEM MAPA

Honestidade de fechamento:

| Processo | Situação |
| --- | --- |
| Negociação (proposta → acordo → aporte) | existe como rotas soltas no menu; **sem trilha** |
| Marketplace (anúncio → contato → contratação) | idem |
| Prestação de contas | idem |
| Denúncia e apuração | máquina de estados existe (v0.20.0); **sem trilha** |
| Jornada do perfil `platform` | **não existe** em `onboarding_paths.json` |

Cada um desses tem máquina de estados ou sequência real no backend. O que falta é desenhá-los — e
`Trail` já aceita qualquer lista de etapas, então o custo de cada um é pequeno. Não foram feitos
nesta rodada por escolha de escopo, e ficam registrados em vez de passarem por concluídos.

### Nenhum diagrama renderizado

Não há mermaid, grafo ou fluxograma desenhado em lugar nenhum da interface. As 58 transições do
ciclo de vida do projeto e as 27 do grafo de cobrança estão documentadas em **tabela**
(`PROJECT_LIFECYCLE.md`) e expostas como lista de transições possíveis. Desenhar um grafo de 17
nós numa tela de celular é um problema de design que esta rodada não resolveu — e resolver mal
seria pior do que a tabela.
