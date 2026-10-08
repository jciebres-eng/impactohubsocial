# Relatório final — IMPACT NETWORK CORE (v0.16.0)

Relatório honesto da rodada. **🟢 VERDE** = provado por teste ou execução nesta máquina. **🟡 AMARELO** = implementado,
depende de ação externa ou de validação que não houve. **🔴 VERMELHO** = ausente.

Escopo pedido: transformar a plataforma em *infraestrutura digital de conexão, estruturação, financiamento, execução,
acompanhamento e comprovação de impacto*, com **um núcleo** e experiência por papel, **sem começar pelo visual**.

---

## A. Veredito

**🟢 VERDE, com cinco amarelos declarados e quatro vermelhos que não são de engenharia interna.**

| Camada | Veredito |
|---|---|
| Grafo de impacto e modelo de relação | 🟢 |
| Motor de propostas | 🟢 |
| Marketplace e separação público/privado | 🟢 |
| Mensagem com contexto | 🟢 |
| Notificação para a equipe envolvida | 🟢 |
| Prontidão e recomendação | 🟢 |
| Workspace por persona (10 personas) | 🟢 |
| Perfil público `@identificador` | 🟢 |
| Relatório de impacto com números colhidos | 🟢 |
| Escada de moderação com contestação | 🟢 |
| Banco, integridade e caminho de atualização | 🟢 |
| API (704 operações) | 🟢 |
| Isolamento entre organizações | 🟢 |
| Frontend funcional (27 telas novas) | 🟢 |
| **Cobrança** | 🟡 toda a camada da plataforma pronta e testada; **sem conta, chave ou preço real no provedor** |
| **Navegação horizontal retrátil** | 🟡 pedida em rodada anterior, **não atendida**; é entrega de design, especificada |
| **E2E de navegador nas 27 telas novas** | 🟡 têm cobertura de API e de jornada, não de Playwright |
| **Desempenho do workspace da OSC** | 🟡 341–436 ms, dentro do orçamento com folga de 5×, mas é a tela de abertura |
| **Exportação de dados pessoais** | 🟡 ainda não cobre as entidades novas da rede |
| **Design System "Convergência"** | 🔴 **NÃO FOI RECEBIDO** — ver §B |
| Validação de segurança por terceiro | 🔴 nunca houve |
| Aplicativo nativo compilado e assinado | 🔴 não iniciado |
| Push nativo no aparelho | 🔴 não existe |

**🔴 de engenharia interna: 0.**

---

## B. O que NÃO foi executado, e por quê

Primeiro, porque muda o escopo entregue.

O pedido pressupõe, nos passos 8 e 9 da sequência de 13, a **integração de um pacote de Design System
("Convergência")**. Esse pacote **não chegou**. Verificação feita: não existe arquivo correspondente no repositório,
o diretório de anexos (`/mnt/user-data/uploads`) está **vazio**, e uma busca por nome em todo o contêiner não
encontrou nada.

**Consequência honesta: as seções de integração de Design System desta rodada não foram executadas.** Nada foi
inventado para preencher a lacuna — não há tokens "Convergência" no CSS, não há componente renomeado e não há
afirmação de conformidade com um sistema que ninguém viu.

O que foi feito no lugar foi o insumo que um Design System consome: a camada de produto que ele precisa representar
(onze motores, dez personas, 27 telas) e os documentos de arquitetura da informação e de navegação
(`INFORMATION_ARCHITECTURE.md`, `NAVIGATION_MODEL.md`), que decidem *o que* os componentes precisam representar
antes de decidir como se parecem. Quando o pacote chegar, o trabalho é mapear tokens e componentes sobre uma AI já
decidida — que é a ordem correta.

---

## C. Números

| Medida | v0.15.0 | **v0.16.0** |
|---|---|---|
| Testes (banco criado do zero em cada execução) | 673 | **788** · 0 falhas · 12 pulados (volume, passo próprio) |
| Operações de API | 625 | **704** |
| Tabelas | 205 | **231** |
| Migrações | 15 | **17** |
| Políticas de RLS | 408 | **466** |
| Gatilhos | 118 | **161** |
| Funções `SECURITY DEFINER` | 53 | **63** (todas com `search_path` fixo) |
| Chaves estrangeiras | 529 | **627** |
| Restrições `CHECK` | 922 | **1.082** |
| Índices | 552 | **643** |
| Tabelas append-only | 17 | **22** |
| Telas registradas no roteador | 151 | **178** |
| Consultas SQL conferidas por `PREPARE` | — | **185 · 0 erros** |

---

## D. A cadeia de impacto, elo por elo

O pedido enuncia a mudança conceitual: *Pessoa/Organização → Contexto → Necessidade/Objetivo → Rede → Match →
Proposta → Relação → Projeto → Execução → Evidência → Resultado → Novo Match*. Cada elo é tabela e rota:

| Elo | Onde |
|---|---|
| Pessoa/Organização | `users`, `organizations`, `memberships` *(já existia)* |
| Contexto | `diagnoses`, `org_personas`, `professional_credentials` |
| Necessidade/Objetivo | `territory_needs`, `marketplace_listings`, `projects` |
| Rede | **`relationships`** |
| Match | `match_runs` *(v0.9.0, intocado)* + **`recommendations`** |
| Proposta | **`proposals`**, `proposal_events` |
| Relação | **`relationships`** com situação ativa |
| Projeto | `projects`, `project_status_graph` |
| Execução | `milestones`, `indicator_values`, `evidences` |
| Evidência → Resultado | **`impact_updates`** com números colhidos pelo banco |
| Novo Match | **`recommendations`** realimentada pelo estado |

---

## E. Um núcleo, não quatro aplicações

O que o pedido mandava provar: que investidor, organização, profissional e governo participam do mesmo ciclo **sem
duplicar domínio, quebrar permissões ou criar quatro produtos**.

Prova: **um** esquema, **uma** tabela de relação, **um** motor de proposta, **um** de prontidão, **um** de
recomendação. As dez personas mudam **seleção e ordem** de seções — nada mais. Nenhuma rota tem persona na
assinatura; `kinds=` e `min_role=` continuam sendo os controles. Dois testes guardam isso:
`test_persona_does_not_grant_permission` (o mapa de capacidades é idêntico antes e depois de declarar persona) e
`test_persona_must_match_the_organization_kind` (persona fora do tipo é recusada com 422).

Ver `ROLE_BASED_EXPERIENCE.md` e `WORKSPACE_ARCHITECTURE.md`.

---

## F. Como a honestidade virou estrutura

O ponto central desta rodada. Cada regra que o pedido enuncia em palavras foi traduzida em algo que **recusa**, em
vez de algo que avisa:

| Regra pedida (em palavras) | O que a recusa, no banco |
|---|---|
| "nunca dizer 'investido' quando apenas houve intenção" | três estágios distintos (`investment_intents` → `commitments` → `payments`) + invariante que impede somá-los |
| "nunca permitir que projeto privado apareça no marketplace por erro de query" | `PUBLIC_STATES = ("published",)` em **um** lugar + `listing_publish_guard()` |
| "a página pública nunca deve ler diretamente tabelas privadas" | a rota lê **só** `public_fields`; `_assert_no_private()` falha na gravação |
| "nunca criar chat sem contexto quando a relação é profissional" | `ux_conv_pair_context` + `messaging.PROFESSIONAL` |
| "nunca criar punição automática irreversível baseada somente em heurística" | `escalation_ok()` (`MAX_JUMP = 2`), `decided_by` obrigatório, nenhuma rota automática |
| "a existência de uma relação não implica que ela seja publica" | `visibility` em 5 níveis + `cap_visibility()` com teto por tipo |
| "nunca mudar preço em silêncio" | `price_notice_guard()` (30 dias) + `price_apply_guard()` + `price_version_immutable()` |
| "preço não hard-coded; backend é a autoridade" | `config/plans.json` → `plan_price_versions` + `test_prices_are_not_hard_coded` |
| "nota de prontidão sempre com explicação" | `_Check` devolve explicação e o que falta por dimensão |
| números de impacto com lastro | `app_impact_metrics()` apura; as colunas estão em `guard_columns` — **nem o motor** escreve |
| "quem revisa não é quem escreveu" | `CHECK (reviewed_by <> created_by)`, recusado até em SQL direto |
| "quem julga a contestação não é quem aplicou" | `CHECK (appeal_decided_by <> decided_by)` |
| identidade do denunciante protegida | `target_view()` não seleciona a coluna; teste confere a ausência |
| `BeneficiaryProfile ≠ SensitivePersonalData` | a coluna existe em **uma** tabela, nunca é filtro de busca, com política de uso gravada no banco |
| autoria de fato de rede não forjável | `REVOKE INSERT ON domain_events` + `app_record_event()` |

Quinze guardas que **o contexto privilegiado não atravessa** (eram 5 na v0.15.0).

---

## G. Notificação para toda a equipe envolvida

Pedido textual: *"trabalhar e implementar notificações para toda a equipe envolvida em cada evolução ou modificação
ou alteração de etapas do processo ou documentos juntados"*.

Entregue: 14 grupos de notificação, 4 prioridades, e o destinatário é **a equipe**, não o dono — `project_team()`
reúne quem é da organização dona com papel relevante **mais** quem apoia o projeto; `notify_org_members()` cobre o
caso organizacional. Cada aviso carrega rótulo de ação e destino clicável. Preferência por grupo **e** canal.

**Um fato, um aviso por pessoa** (`dedupe()`, sha256). A primeira versão avisava a organização *e* a equipe, e quem
era das duas recebia dois — corrigido ao fazer cada fato emitir um único anúncio.

E o invariante que mais importa: **silenciar o aviso não apaga o fato**
(`test_the_fact_survives_the_silenced_notice`). A notificação é entrega; o registro é história.

Ver `NOTIFICATION_ARCHITECTURE.md`.

---

## H. A decisão de não usar banco de grafos

Pedida como decisão explícita, e tomada por **medição**, não por preferência: a travessia de profundidade 2 — o caso
que justificaria um armazenamento especializado — responde em **14–15 ms** com mil organizações e o volume de rede
semeado, usando CTE recursiva e índices em `relationships(source_org_id)` e `(target_org_id)`.

Um segundo armazenamento significaria segunda cópia da verdade, segundo modelo de permissão (e a RLS é o controle
central aqui) e segunda chance de divergir. O teste de desempenho fica no lugar para reabrir a decisão se a travessia
chegar a profundidade 3 em volume. ADR-141.

---

## I. Defeitos encontrados e corrigidos nesta rodada

Os que valem registro, com o que cada um ensina:

| Defeito | O que ensina |
|---|---|
| **`date.today()` × banco em UTC** — o contêiner roda em UTC-4, então por algumas horas de cada dia a plataforma gravava **um dia a menos**. 28 ocorrências em 15 arquivos | o erro mais barato de escrever e o mais caro de descobrir: só aparece numa janela do dia |
| **Sete destinos de recomendação apontavam para telas inexistentes** | recomendação que leva a lugar nenhum é pior que nenhuma recomendação. Agora há teste de arquitetura conferindo cada destino contra o roteador real |
| **Organização nova recebia zero recomendações** | todas as regras dependiam de já haver projeto ou proposta — a tela de abertura ficava vazia justamente para quem mais precisa de direção |
| **O alvo de uma medida de moderação conseguia escrever `status`** | GRANT de coluna **adiciona** privilégio e não consegue restringir; restrição é gatilho |
| **Métricas de impacto calculadas em Python e gravadas em coluna guardada** | a trava funcionou: o código que tentava burlar a própria regra não passou |
| **`guard_columns` bloqueava a organização de publicar o próprio anúncio** | guarda boa demais vira defeito; a resposta foi **derivar** as colunas de situação por gatilho |
| **`guard_columns` em `plan_price_versions` era inútil** | ela isenta `app_priv()`, que ali é o único escritor. Guarda que não guarda é pior que nenhuma, porque dá falsa segurança |
| **`notify.PRIORITIES` dizia `urgent`, o banco diz `critical`** | vocabulário duplicado divergiu. Agora um invariante compara **onze** listas Python aos CHECKs reais |
| **`app_related()` permissivo deixava seguir unilateral abrir conversa** | quebrava a reciprocidade da v0.8.0. Pego por **teste de regressão antigo**, não por revisão — a suíte velha é que protege a decisão velha |
| **`forbid_mutation` tornava o aviso de preço insatisfazível** | append-only absoluto impedia até o "ciente" de quem foi avisado |
| **Aviso duplicado** (organização + equipe) | fan-out precisa de chave de idempotência por pessoa, não por destino |
| **Cinco defeitos de nome de coluna** achados por `PREPARE` | revisão de código **não** pega isso. Foi por isso que `scripts/sql_prepare_check.py` passou a existir |
| **`AND` em plpgsql não faz curto-circuito** | `TG_TABLE_NAME = 'x' AND NEW.coluna_de_x` quebra nas outras tabelas que compartilham o gatilho |
| **`INSERT ... RETURNING` exige a política de SELECT** | era a razão de aceitar proposta responder 403 |
| **`DELETE /v1/workspace/personas/{persona}` respondia 200 com "removidas: 0"** | sucesso que não fez nada é pior que erro |

---

## J. O que ficou pendente, nomeado

| Pendência | Classificação | O que falta |
|---|---|---|
| Design System "Convergência" | 🔴 | o pacote em si (§B) |
| Navegação horizontal retrátil com área de trabalho ampla | 🟡 | entrega de design; mapeamento item-a-item já escrito em `NAVIGATION_MODEL.md` |
| E2E de navegador nas 27 telas novas | 🟡 | estender `test_e2e_v0150_web.py` |
| Verificação de viewport e contraste nas telas novas | 🟡 | mesma razão; as antigas têm 25 combinações verificadas |
| Cobrança real | 🟡 | conta no provedor, chave, dois preços criados, gravar `provider_price_id` |
| Exportação de dados pessoais nas entidades novas | 🟡 | decisão jurídica antes de técnica: o que de uma proposta entre duas organizações pertence ao titular pessoa física |
| Política de privacidade descrevendo a página pública e a rede | 🟡 | texto jurídico |
| Logotipos oficiais dos ODS | 🟡 | autorização de uso de marca (número, nome e cor oficial já estão em `sdg_goals`) |
| Hub de integração sem tela | 🟡 | 36 rotas funcionais, interface não desenhada |
| Workspace da OSC a 341–436 ms | 🟡 | avaliação de prontidão em lote, se incomodar |
| Push nativo | 🔴 | FCM + APNs + tabela de token; o canal já existe nas preferências |
| Aplicativo compilado e assinado | 🔴 | keystore, conta Apple Developer, macOS |
| Compra dentro do app | 🔴 **decisão do proprietário** | análise das regras de Apple e Google |
| Auditoria de dependências | 🟡 | `npm audit` e `pip-audit` **bloqueados neste ambiente** pelo registro de pacotes; obrigatórios em CI |
| Teste de intrusão independente | 🔴 | nunca houve |
| DPO nomeado, ROPA, RIPD | 🔴 | ação do proprietário |
| Conteúdo oficial (Central, regras fiscais) | 🔴 | só exemplos rotulados `demo` |

---

## K. O que continua NÃO simulado

Lista mantida porque é a espinha dorsal do acordo desta construção. Nenhum destes é simulado em **nenhum** caminho do
código; onde o produto depende deles, há recusa explícita e declarada:

biometria · assinatura qualificada · ICP-Brasil · gov.br · SMS · carimbo de tempo de ACT · Stripe real ·
provedor fiscal real · KYC real · identidade governamental real.

`signature_provider_guard()` recusa **no banco** assinatura com provedor fora de `production` — não é disciplina de
quem escreve código, é estrutura. E a cobrança recusa cobrar sem `provider_price_id` real em vez de tentar com um
valor inventado.

---

## L. Verificações executadas nesta rodada

| Verificação | Resultado |
|---|---|
| Suíte completa, banco criado do zero | **788 testes · 0 falhas · 12 pulados** |
| Suíte de volume em escala cheia | **12 testes · 0 falhas**, duas execuções |
| `ruff check impacto tests` | **All checks passed** |
| `tsc --noEmit` (`tsconfig.offline.json`) | **PASS** |
| `node build.mjs` | **PASS** |
| `migrate --check` | sem pendências, sem checksum alterado |
| Caminho de atualização v0.12.1 → v0.16.0 com dado dentro | **esquema idêntico ao criado do zero** |
| `scripts/sql_prepare_check.py` | **185 consultas · 0 erros** |
| `scripts/db_integrity_report.py` | `security_definer_without_search_path` **vazio** · `fk_without_index_hot` **vazio** · `tables_without_primary_key` **vazio** |
| Geração de documentação da API a partir do código | **704 operações** |
| Backup e teste de restauração | ver §M |

---

## M. Entrega, versionamento e backup

| Item | Estado |
|---|---|
| `VERSION` | `0.16.0` |
| Documentos da v0.15.0 preservados | `history/v0.15.0/` (28 arquivos + `NOTE.md`) |
| Branch de trabalho | `chore/v0.16.0-impact-network-core` |
| Branch de savepoint | `savepoint/v0.16.0-impact-network-core` |
| Tag anotada local | `v0.16.0` |
| **Envio da tag ao remoto** | **BLOQUEADO PELO AMBIENTE** — o proxy recusa `git push --tags` com 403. Registrado como `TAG_PUSH_BLOCKED_BY_ENVIRONMENT`; a branch de savepoint cumpre o papel de marco imutável até alguém com acesso direto enviar a tag |
| Pacote | `IMPACTO_v0.16.0_IMPACT_NETWORK_CORE.zip` + `RELEASE_MANIFEST.sha256` + `V0.16.0_FINAL_MANIFEST.json` |
| Verificação do pacote | extraído em diretório limpo e conferido por `make_release.py --verify` |
| Backup e restauração | `scripts/backup.sh` + `scripts/restore_test.sh` executados |

---

## N. Conclusão

A camada de domínio está fechada, provada e documentada. O que falta antes de publicar não é engenharia interna: é
design, contratação de provedores, revisão jurídica e validação por terceiro — tudo nomeado em §J, com o que falta
em cada caso.

Sobre o pacote de Design System: ele não chegou, as seções que dependiam dele não foram executadas, e nada foi
inventado no lugar. Se o pacote vier, a próxima rodada tem onde encaixá-lo — a arquitetura da informação e o modelo
de navegação já estão decididos e escritos.

---

**v0.16.0 — IMPACT NETWORK CORE está tecnicamente pronta para DESIGN.**

<sub>Nota sobre o número: o pedido pede que a frase de encerramento cite "v0.15.0", mas pede também que a versão
suba de forma coerente — e esta rodada entrega uma capacidade nova grande sobre a v0.15.0, portanto é v0.16.0
(SemVer MINOR, ver `VERSIONING.md`). A v0.15.0 está preservada, íntegra, em `history/v0.15.0/`.</sub>
