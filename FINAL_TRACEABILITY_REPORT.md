# Relatório final — v0.23.0 · Rastreabilidade, proveniência, governança de IA e emergência

**Data:** 7 de outubro de 2026 · **Versão:** 0.23.0 · **Pacote:** `IMPACTO_v0.23.0_TRACEABILITY.zip`
**sha256:** `dd0e46928b8b023f07b7c4874932de5fa313813251e980f4b557c068d1d63823`

---

## ⚠️ A regra absoluta desta rodada, respeitada

> **Não se declara, em nenhum ponto deste relatório ou do código, que o sistema está "100% impossível
> de invadir". Nenhum sistema conectado à internet pode receber essa garantia.**

O que este relatório afirma é mais estreito e verificável: cada controle listado **existe no código,
está coberto por teste que falha se ele for removido, e as ausências estão nomeadas**.

---

## 1. Veredito: 🟡 **AMARELO — GO COM CONDIÇÕES**

**Por que não VERDE:** há uma dívida externa não fechada (`web/package-lock.json`, bloqueio de rede
deste ambiente) e quatro itens dos prompts recusados por desenho ou não implementados, cada um
declarado. **Nenhum deles bloqueia o Designer nem a publicação web.**

**Por que não VERMELHO:** a suíte está verde com 2 070 testes, nenhuma trava foi afrouxada para
chegar ao verde, e os quatro defeitos de segurança mais graves que a auditoria encontrou estão
corrigidos com teste de catraca.

---

## 2. O que a rodada fez antes de construir

Os quatro prompts pediram camada de IA transversal (170 seções), motor de auditoria, infraestrutura
Supabase/Vercel/R2 e frontend. **A primeira coisa foi auditar o que já existia.** Duas conclusões
decidiram o escopo:

**1. A base é mais madura do que os prompts supõem.** Antes desta rodada: 745 rotas, 1 806 testes,
RLS em 312 de 313 tabelas com 653 políticas, 41 tabelas append-only, cadeia de hash em duas trilhas,
60 testes adversariais, 319 chamadas de auditoria. Pedir "crie um motor de auditoria" a uma base com
trilha append-only encadeada por hash levaria a refazer o que funciona.

**2. A pilha de referência dos prompts não é a desta plataforma.** Os prompts descrevem
Supabase + Supabase Auth + Vercel + Next.js + Cloudflare R2. Esta plataforma é Python 3.13/Starlette,
PostgreSQL 16 auto-hospedado, React/esbuild, armazenamento abstrato. **A infraestrutura não foi
trocada** — e isso segue a primeira regra do próprio prompt de infraestrutura: *"não substitua
componentes que já estejam funcionando corretamente apenas por preferência"*. Os requisitos de
segurança dele foram aplicados à pilha real. Registrado em `PLATFORM_AUDIT_v0230.md` §0.

---

## 3. Os quatro defeitos de segurança mais graves, corrigidos

### 3.1 🔴 O refresh token não vencia

`issue_session()` gravava `refresh_expires_at = now() + 30 dias` em **toda** rotação, inclusive nas
da mesma família. Trinta dias contados sempre do último uso **nunca vencem para quem está usando** —
então um refresh token roubado e renovado dentro da janela sobrevivia indefinidamente.

**Correção:** a FAMÍLIA tem idade máxima própria (`family_started_at`, propagada nas rotações) e
limite de inatividade. Os dois são configuração, não constante, e há teste exigindo que ambas tenham
leitor fora de `config.py` — a lição de `LOGIN_MAX_ATTEMPTS`, configuração que parecia ligada e não
tinha leitor.

**Prova:** `test_v0230_session_hardening.py`, 10 testes, incluindo
`test_the_family_birth_is_carried_across_rotations` e `test_the_expiry_is_recorded_in_the_audit_trail`.

### 3.2 🔴 O código TOTP servia duas vezes

`verify()` devolvia o contador aceito e o docstring dela dizia *"para impedir reuso"* **desde
sempre** — e nenhum dos quatro chamadores usava o valor.

**Correção:** `verify_once()` queima o contador na mesma instrução condicional; o gatilho
`totp_counter_moves_forward` recusa retrocesso **inclusive para o dono do banco**.

**O defeito encontrou o teste.** `test_mfa_flow_and_recovery_code` reaproveitava o MESMO código para
ligar o MFA e reautenticar, e só passava porque o reuso era possível. Cinco auxiliares de teste
dependiam disso; `fresh_totp()` emite um código por passo distinto e recusa o quarto na mesma janela
de 30 segundos com mensagem explícita, em vez de produzir um 401 misterioso.

### 3.3 🔴 O evento de segurança mais grave não alertava ninguém da operação

`auth.refresh_reuse_detected` — o sinal mais forte de roubo de sessão que a plataforma sabe produzir
— era detectado, a família de sessões era revogada, o evento ia para a trilha imutável e o **titular**
era notificado. **Ninguém da operação era alertado.** O evento mais grave do sistema esperava que
alguém abrisse uma tela.

**Correção:** duas séries emitidas em dois pontos de estrangulamento
(`services/audit.py::record()` e `ops/runs.py::_fechar()`) e 16 regras de alerta. Emitir no ponto de
passagem — e não em cada chamador — garante que nenhum evento de segurança novo nasça invisível.

**Catraca:** `EveryAlertReadsASeriesThatExistsTests` reprova se um alerta ler série que nada emite,
se um rótulo `action` não for ação declarada, ou se um nome em `SECURITY_ACTIONS` não tiver produtor
no código.

### 3.4 🔴 O script de restauração que ninguém executava

`scripts/restore_test.sh` confere o sha256 do dump, restaura num banco descartável, verifica as três
cadeias de hash e prova que o restore não traz estado que não deveria existir. **Nada o chamava** —
nem CI, nem Makefile, nem suíte. É literalmente o defeito que `ops/backup.py` critica na primeira
linha: *"script que ninguém executa não é backup"*.

**Correção:** o CI roda o ciclo completo com os papéis reais (`impacto_owner`, não superusuário) **e**
com um dump adulterado de propósito que a restauração tem de recusar — conferir o hash de um arquivo
que ninguém alterou prova pouco.

**Verificado localmente:** 62 migrações restauradas, cadeias de ledger e auditoria íntegras, camada
econômica restaurada DESLIGADA, dump adulterado recusado.

---

## 4. O que foi construído, por etapa

| Etapa | Entrega | Testes |
|---|---|---|
| E1 | Quatro auditorias (`AI_AUDIT.md`, `PLATFORM_AUDIT_v0230.md`) | — |
| E2 | Vida de sessão · antirreuso de TOTP · varredura de segredo no CI · restauração conferida · 16 alertas · redação recursiva | 42 |
| E3 | Interruptor de emergência (5 escopos) | 36 |
| E4 + E7 | Proveniência de indicador · correção no Impact Ledger · cadeia no Value Ledger · motor de integridade · máquina de estados no banco | 49 |
| E5 | Motor de auditoria: 11 campos, árvore de causa, categoria como dado, anti-TRUNCATE, exportação auditada | 37 |
| E6 | Governança de IA: registro de prompt, faixas de risco, `status` real, esquema conferido, crédito ≠ token, orçamento | 75 |
| E8 | Seis telas novas + contrato tela↔rota | 19 |
| E9 | Documentos, ADRs, versão, snapshot, ZIP | — |

**Todas as nove etapas foram executadas.** Nenhuma ficou pendente.

---

## 5. Números

| | v0.22.0 | v0.23.0 |
|---|---|---|
| Testes | 1 806 | **2 070** |
| Rotas | 745 | **888** |
| Tabelas | 313 | **322** |
| Tabelas com RLS | 312 | **321** (a única sem é `schema_migrations`) |
| Políticas de RLS | 653 | **667** |
| Tabelas append-only | 41 | **43** |
| Tabelas protegidas contra TRUNCATE | 0 | **6** |
| Migrações | 50 | **62** |
| Permissões declaradas em rota | 30 | **33** |
| Documentos | 141 | **149** |
| Regras de alerta | 4 | **16** |

---

## 6. Matriz dos motores — o que cada um tem

Leitura: **impl** = implementado · **integ** = ligado ao resto do produto · **test** = teste próprio ·
**E2E** = exercitado numa jornada de ponta a ponta · **seg** = teste adversarial · **obs** = emite
série ou registro consultável.

| Motor | impl | integ | test | E2E | seg | obs |
|---|---|---|---|---|---|---|
| Autenticação e sessão | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| MFA / TOTP | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Autorização (14 papéis, 43 permissões) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Interruptor de emergência | ✅ | ✅ | ✅ | ⬜ | ✅ | ✅ |
| Auditoria e rastreabilidade | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Proveniência de indicador | ✅ | ✅ | ✅ | ✅ | ✅ | ⬜ |
| Integridade relacional | ✅ | ✅ | ✅ | ⬜ | ✅ | ✅ |
| Máquina de estados (candidatura) | ✅ | ✅ | ✅ | ✅ | ✅ | ⬜ |
| Impact Ledger (com correção) | ✅ | ✅ | ✅ | ✅ | ✅ | ⬜ |
| Value Ledger (com cadeia) | ✅ | ✅ | ✅ | ✅ | ✅ | ⬜ |
| Camada de IA (governança) | ✅ | ✅ | ✅ | ⬜ | ✅ | ✅ |
| Avaliação de IA (conjunto de referência) | ✅ | ✅ | ✅ | ⬜ | ⬜ | ⬜ |
| Motor financeiro (CALCULA/INSTRUI/CONCILIA) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Contabilidade | ✅ | ✅ | ✅ | ⬜ | ✅ | ✅ |
| Alçada e aprovação (8 faixas) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Diagnóstico · Prontidão · Compatibilidade · Equidade · Reputação · Selo · Alegação · Fiscal · Institucional · Longitudinal · Replicação | ✅ | ✅ | ✅ | ✅ | ✅ | ⬜ |
| Backup e restauração | ✅ | ✅ | ✅ | ⬜ | ✅ | ✅ |
| Notificação | ✅ | ✅ | ✅ | ✅ | ⬜ | ✅ |
| Integração (hub) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

**Lacunas de observabilidade declaradas:** sete motores de impacto não emitem série própria. Eles
emitem registro consultável (Value Ledger e auditoria); o que falta é métrica de Prometheus, e isso
está no registro de dívida como item de média gravidade.

---

## 7. Distinção rígida entre denúncia, suspeita, infração apurada e consequência

Mantida da v0.20.0, e nesta rodada estendida à trilha de auditoria:

| Estado | Pode gerar medida? | Onde |
|---|---|---|
| **Denúncia aberta** | ❌ Não | `reports`, nível de risco MEDIUM, declarado: *"abrir denúncia NÃO tem efeito por si"* |
| **Suspeita / sinal de risco** | ❌ Não | `risk_signals`, item de revisão, nunca acusação |
| **Infração APURADA** | ✅ Sim, é o único estado que autoriza | `reports.conclude`, fundamentação obrigatória, nível CRITICAL |
| **Consequência** | — | `enforcement`, com apuração anterior obrigatória |

Novidade desta rodada: `audit_events.status` distingue `success`, `denied` e `failed`. Uma tentativa
RECUSADA é registrada como recusada — não como fato consumado nem como ausência. Trilha que só
registra sucesso descreve um sistema em que nada é recusado.

---

## 8. O que esta versão NÃO entrega

### 8.1 Dívida com bloqueio externo

**`web/package-lock.json` não existe.** O registro npm devolve 403 neste ambiente e
`npm install --package-lock-only` falha no primeiro pacote:

```
npm error 403 403 Forbidden - GET https://registry.npmjs.org/@capacitor%2fandroid
```

A árvore de dependências do frontend **não é reprodutível**, e `npm audit --omit=dev` audita a
árvore que acabou de ser resolvida. Escrever um lockfile à mão com hashes de integridade que ninguém
verificou seria inventar justamente o artefato cuja única função é ser verificável.

**O que foi feito no lugar:** as quatro dependências que entram no pacote construído estão em versão
exata (`react` 19.2.8, `react-dom` 19.2.8, `esbuild` 0.28.2, `typescript` 6.0.3), com 10 testes de
catraca; o CI gera o lockfile e o publica como artefato pronto para commit.

**Ação necessária, uma vez:** `cd web && npm install --package-lock-only && git add package-lock.json`

Registrado como **D-SUP1** em `TECHNICAL_DEBT_REGISTER.md`.

### 8.2 Recusado por desenho

| Item | Motivo da recusa |
|---|---|
| Ferramentas e agentes de IA | Dar ferramenta à IA é dar a ela a capacidade de MUDAR estado. A garantia central da camada é que nenhuma saída de IA vira estado sozinha. |
| Escrita assíncrona de auditoria | Fila tornaria a trilha *eventualmente* consistente com o fato. Numa trilha de auditoria, "eventualmente" é a palavra errada. |
| Fallback entre provedores externos de IA | Exige base legal POR PROVEDOR. Mandar o dado para um segundo provedor porque o primeiro caiu é tratamento que a organização não autorizou. |
| Troca da infraestrutura para Supabase/Vercel | A primeira regra do próprio prompt: não substituir componente que funciona por preferência. |
| Fintech dentro do IMPACTO | Regra acima de todas, da v0.22.0. `split`, `payout`, `recipient`, `escrow` e `wallet` continuam com **zero** ocorrências. |

### 8.3 Não implementado, com risco declarado

| Item | Risco de não ter | O que seria necessário |
|---|---|---|
| Embeddings e busca semântica | recuperação só por termo e relação, não por sentido | provedor de embedding contratado, `pgvector`, decisão sobre onde o vetor é calculado, isolamento por inquilino |
| Cache semântico de resposta | chamada repetida custa de novo | embeddings + limiar; e errar "quando duas perguntas são a mesma" entrega o dado de um projeto na resposta de outro |
| Particionamento de `audit_events` | a partir de dezenas de milhões de linhas, relatórios agregados ficam lentos | chave de particionamento, `audit_verify()` reescrita para percorrer partições, rotina de criação antecipada |
| UNIQUE em `documents.supersedes_id` | dois documentos podem declarar substituir o mesmo; a versão "atual" fica ambígua | índice único parcial, depois de conferir se algum dado existente já viola |
| Grafo de proveniência genérico | "de onde veio este aporte?" ainda exige percorrer a linha do tempo | declaração de cadeia por tipo de entidade; a infraestrutura (`correlation_id`, `parent_event_id`) já existe |
| Série de Prometheus nos motores de impacto | falha neles aparece só na tela, não no alerta | emissão no ponto de estrangulamento de cada motor |

### 8.4 Continua valendo da v0.22.0

Nenhuma cobrança real é possível: nenhum provedor de pagamento, fiscal, de WhatsApp, de mapas ou de
IA está ligado. Nada publicado em loja ou domínio. Android/iOS: código pronto, **não construídos**.
Nenhuma assinatura qualificada, ICP-Brasil, gov.br, biometria ou KYC real está simulada ou ligada.

---

## 9. Os defeitos que a própria suíte encontrou nesta rodada

Vale registrar porque **nenhum foi contornado afrouxando trava** — e porque três deles eram guardas
que pareciam funcionar:

1. **Guarda de código morto derrotado por acento.** `[A-Za-z_][A-Za-z0-9_]*` não casa identificador
   acentuado: `_é_equipe` era tokenizado como `_` + `_equipe` e a função aparecia como morta sendo
   chamada. Mesma classe do guarda de RLS derrotado por espaço em branco na v0.22.0.
2. **Guarda de contagem única da cota de IA reprovando por coincidência.** Procurava duas frases no
   mesmo ARQUIVO. Passou a conferir por INSTRUÇÃO, exigindo quatro marcas juntas.
3. **Interruptor que nunca bloqueava.** A primeira versão usava `c.all()`, que não existe nesta
   camada de banco: a leitura do estado falhava, caía no tratamento de exceção e devolvia "liberado".
   O ramo agora **conta** a falha, porque um interruptor que não consegue ler o próprio estado é
   incidente de segurança, não aviso de log.
4. **Toda rota de IA devolvendo 500.** O gateway lê o prompt dentro da transação da organização, e a
   RLS de `ai_prompts` é privilegiada. Resolvido com função SECURITY DEFINER de escopo exato.
5. **Interferência entre arquivos de teste.** O teste do verificador de alegação forja uma medição
   validada sem evidência e deixava a linha no banco, fazendo a cobertura de proveniência reprovar
   em OUTRO arquivo.
6. **68 de 86 prefixos de ação caindo em OTHER.** A categoria derivada de um `CASE` no código cobria
   as nove categorias pedidas e jogava 79% dos eventos em "outros".
7. **Dois arranjos de teste tomando o atalho que a máquina de estados passou a proibir** (candidatura
   nascendo aprovada). Passaram a percorrer o grafo.
8. **Um teste medindo proporção com linhas que o esquema tornou impossíveis.** Passou a usar o estado
   que elas podem ocupar de verdade.

---

## 10. Entregáveis

| Arquivo | Conteúdo |
|---|---|
| `IMPACTO_v0.23.0_TRACEABILITY.zip` | 1 779 arquivos · 10,49 MB · manifesto verificado |
| `IMPACTO_v0.23.0_TRACEABILITY.json` | manifesto de versão: 1 778 arquivos em 28 categorias |
| `AUDIT_ENGINE.md` | motor de auditoria, lista de 28 itens, o que não está implementado |
| `PROVENANCE_ENGINE.md` | proveniência, integridade relacional, máquina de estados |
| `AI_FINAL_AUDIT.md` | os 11 achados, o implementado, e §3 com as recusas |
| `AI_AUDIT.md` · `PLATFORM_AUDIT_v0230.md` | as auditorias que decidiram o escopo |
| `TECHNICAL_DEBT_REGISTER.md` | D-SUP1 e o restante da dívida |
| `CHANGELOG.md` · `DECISIONS.md` | entrada da versão e 29 ADRs novos (307–335) |
| `history/v0.22.0/` | os 144 documentos da versão anterior |

Conferências do pacote: **nenhum ZIP dentro de ZIP** · **nenhum `.env`, `.pem`, `.key` ou chave
privada** · **nenhum `node_modules`** · manifesto `RELEASE_MANIFEST.sha256` verificado arquivo por
arquivo (1 779 de 1 779).

---

## 11. Próximos passos, em ordem

1. **Uma vez, com acesso ao registro npm:** gerar e commitar `web/package-lock.json` (fecha D-SUP1).
2. **Camada de Designer.** A base está fechada; as seis telas novas seguem o sistema de design
   existente e não introduzem vocabulário visual próprio.
3. **Validações humanas e de terceiros** que faltam: jurídica (minutas), contábil (plano de contas),
   fiscal (regras), e revisão de acessibilidade com ferramenta real — `axe-core` não está disponível
   neste ambiente e a conferência atual é estrutural.
4. **Publicação web**, depois do Designer.
5. **Construção mobile** para as lojas (código Capacitor pronto, nunca construído).

---

## 12. Uma observação sobre o que esta versão aprendeu

Três dos defeitos encontrados nesta rodada estavam em **guardas** — testes escritos para impedir
regressão. Um não casava identificador acentuado, um reprovava por coincidência, um escondia a
própria falha num tratamento de exceção.

É o padrão mais caro que esta base já produziu: **o controle que parece funcionar é pior que o
controle ausente**, porque ninguém o verifica. Por isso cada guarda corrigido nesta rodada ganhou
uma **contraprova** — um teste que falha se o guarda deixar de saber reprovar.

A mesma lógica vale para os números deste relatório. Eles não são afirmações sobre qualidade: são
afirmações sobre o que foi medido, com o caminho para refazer a medição. O que não foi medido está
na §8, nomeado.
