# Relatório de desempenho — v0.16.0

Medido, não estimado. O coletor é `backend/tests/test_v0150_performance.py`; a saída bruta está em
`docs/evidence/perf_v0.16.0.log` (a da versão anterior ficou em `docs/evidence/perf_v0.15.0.log`).

## 1. Como foi medido

**Volume sintético, escala cheia** (`PERF_FULL=1`):

| Entidade | Quantidade |
|---|---|
| Organizações | 1.000 |
| Projetos publicados | 10.000 |
| Soluções | 10.000 |
| Documentos | 100.000 |
| Avaliações de match (`match_runs`) | 100.000 |
| Entradas de trilha | 10.000 |

Tempo para criar o volume: **12 s** (SQL em lote, no papel dono).

**Máquina**: 2 vCPU Intel Xeon @ 2.80 GHz, 7 GB de RAM, PostgreSQL 16.15 local, container Linux 6.18 x86_64.
Aplicação e banco na **mesma** máquina — em produção separada, a latência de rede entra por cima.

**Não há cadastro nominal de beneficiário na plataforma** (decisão de LGPD), então o volume "de registros por
organização" usa soluções, que é a tabela grande de conteúdo.

A suíte roda em **passo próprio** (`PERF=1` ou `PERF_FULL=1`), não junto com a suíte funcional: o dado sintético
mudaria o resultado de testes que dependem de ranking e de paginação — e mudou, quando tentamos juntar.

## 2. Resultado

| Requisição | Tempo | Orçamento | Situação |
|---|---|---|---|
| `GET /v1/documents?limit=25` (100.000 documentos na base) | **11 ms** | 2.500 ms | ✅ |
| `GET /v1/readiness` (diagnóstico completo da organização) | **11 ms** | 2.500 ms | ✅ |
| `GET /v1/projects/{id}/timeline?limit=50` | **8 ms** | 2.500 ms | ✅ |
| `GET /v1/feed/projects?limit=25` (10.000 projetos publicados) | **1.615 ms** | 2.500 ms | ⚠️ passa, e é o mais lento por larga margem |

### Detector de N+1

A mesma consulta com `limit=5` e com `limit=100`:

| | Antes da v0.15.0 | Depois |
|---|---|---|
| `limit=5` | 2.985 ms | 1.474 ms |
| `limit=100` | 3.416 ms | 1.655 ms |
| Razão | 1,14× | 1,12× |

A razão próxima de 1 mostra que o custo **não** cresce com o tamanho da página: não há consulta por linha na
montagem da resposta. O teste falha se a razão passar de 8×.

### Planos de execução

O teste roda `EXPLAIN` nas consultas quentes e **falha** se aparecer `Seq Scan`:

- documentos por projeto · projetos da organização · trilha do projeto · avaliações da organização → todas por
  índice.

## 3. O que foi corrigido nesta versão

O feed do financiador custava **3.126 ms**. Diagnóstico por medição (não por intuição): ~10 idas ao banco por
candidato, 400 candidatos.

| Correção | Efeito |
|---|---|
| **Elegibilidade dura que cabe em SQL entra no `WHERE`** — compliance reprovado, causa excluída pela política, território excluído | esses candidatos seriam descartados depois de qualquer forma; avaliá-los era trabalho jogado fora. Com `include_blocked=true`, nada é pré-filtrado |
| **Carga em lote** (`load_projects` + `project_funding_many`) | 3 consultas no total, em vez de 3 por candidato |
| **Memória por organização na requisição** (`FeedCache`) | organização, documentos, histórico, conflito e contexto institucional carregados uma vez por organização, não uma vez por projeto |
| **Carga em lote das organizações da página** | uma consulta em vez de uma por linha exibida |
| **Janela de pontuação de 200**, escolhida por afinidade barata em SQL | e **declarada na resposta** (`scoring_window`, `candidates_scored`, `window_note`) |

Resultado: **3.126 ms → 1.615 ms** (1,9× mais rápido), no mesmo volume e na mesma máquina.

A migração `0015_v0150_fk_indexes.sql` (92 índices de chave estrangeira) entrou pelo mesmo caminho: a medição
mostrou FK de caminho de acesso sem índice. Ver `DATABASE_INTEGRITY_REPORT.md` §4.

## 4. Custo de escrita dos índices novos

| | Antes da 0015 | Depois |
|---|---|---|
| Suíte completa (673 testes, muita escrita) | 268 s | 268 s |

Nesta escala, o custo é indistinguível do ruído. Em volume de produção com escrita intensa, 92 índices têm custo
real — e é por isso que a regra foi restritiva (só coluna de inquilino ou de pai percorrido), e não "índice em toda
FK".

## 5. Limite conhecido e declarado: o feed a 1,6 s

O feed do financiador continua sendo o caminho mais caro, e **1,6 s é lento** para uma tela de navegação.

**Por que ainda custa isso:** a avaliação explicável de um candidato precisa de organização, documentos
(metadados por função `SECURITY DEFINER`), histórico de execução, conflito de interesse e contexto institucional.
Com 200 candidatos de 200 organizações distintas — o pior caso, que é exatamente o do volume sintético — a memória
por organização não ajuda, e sobram ~200 × 5 chamadas.

**O que fecharia isso**, em ordem de custo/benefício:

1. **Carregadores em lote para os dados por organização**: `org_track_record_many(uuid[])`,
   `org_document_metadata_many(uuid[], uuid[])` e uma versão em lote do contexto institucional. Estimativa: de
   ~1.000 idas ao banco para ~5. É o caminho certo, e exige cuidado com `SECURITY DEFINER` — foi justamente ali que
   apareceram os defeitos de RLS das versões anteriores (ADR 103, 104, 105), então não entra sem matriz de
   isolamento e teste dedicado.
2. **Pré-cálculo da afinidade barata** em tabela materializada, atualizada por job, para que a janela seja escolhida
   sem ordenar a base inteira.
3. **Cache por financiador** do resultado da avaliação, invalidado por mudança no projeto ou no perfil. Tem custo de
   coerência: resultado em cache com régua antiga é exatamente o que as quatro versões existem para evitar.

**Em produção real isto dói menos do que parece**: um financiador quase nunca olha "todos os projetos publicados do
Brasil" — ele filtra por causa, território ou edital, e o filtro entra no SQL antes da janela. O pior caso medido é
o uso sem filtro nenhum.

Enquanto o caminho 1 não for feito, o limite está **escrito na resposta da API** e repetido em
`MATCH_ENGINE_FINAL.md` §6. Limite declarado é limite; limite escondido é defeito.

## 6. Os caminhos novos da v0.16.0

Volume de rede acrescentado ao mesmo cenário: relações entre as 1.000 organizações, anúncios publicados, propostas
em várias situações e eventos de domínio. Orçamento de **2.500 ms** para todos.

**Duas execuções**, na mesma máquina e no mesmo volume, para mostrar a variação real em vez de um número único:

| Caminho | Execução A | Execução B | Orçamento |
|---|---|---|---|
| `GET /v1/network/graph?depth=2` | 15 ms | **14 ms** | 2.500 ms |
| `GET /v1/relationships` | 11 ms | **11 ms** | 2.500 ms |
| `GET /v1/marketplace` (público, sem sessão) | 17 ms | **18 ms** | 2.500 ms |
| `GET /v1/readiness` | 8 ms | **12 ms** | 2.500 ms |
| `GET /v1/readiness/purposes` | 8 ms | **10 ms** | 2.500 ms |
| `GET /v1/projects/{id}/timeline` | 10 ms | **9 ms** | 2.500 ms |
| `GET /v1/documents` | 13 ms | **11 ms** | 2.500 ms |
| `GET /v1/proposals` (caixa de entrada) | 60 ms | **56 ms** | 2.500 ms |
| `GET /v1/workspace` (investidor) | 71 ms | **82 ms** | 2.500 ms |
| `GET /v1/workspace` (OSC) | 341 ms | **436 ms** | 2.500 ms |
| `GET /v1/feed/projects` | 1.724 ms | **1.508 ms** | 2.500 ms |

Duas leituras importantes:

**O grafo a 14–15 ms é a razão documentada de NÃO adotar banco de grafos** (ADR-141). A travessia de profundidade 2
é exatamente o caso que justificaria um armazenamento especializado, e com índices em `relationships(source_org_id)`
e `(target_org_id)` ela é barata. Se a travessia chegar a profundidade 3 em volume, a decisão deve ser reaberta — e
o teste já está no lugar para medir.

**O workspace da OSC (341–436 ms) é o ponto a observar.** É a tela de abertura, e é o mais caro dos novos porque
agrega oito seções, uma delas avaliando a prontidão de cada projeto da organização. A variação de ~100 ms entre
execuções é ruído de máquina compartilhada, não regressão. O que fecharia isso, se incomodar:

1. **Avaliação de prontidão em lote** por organização, em vez de por projeto — o mesmo padrão de carregador em lote
   que resolveu o feed.
2. **Retrato de prontidão em cache** (`readiness_snapshots` já existe e é append-only), lido na abertura e
   recalculado por job ou por mudança no projeto. O cuidado é o mesmo de sempre: nota em cache com régua antiga é o
   que as versões do motor existem para evitar.
3. **Carregar as seções abaixo da dobra sob demanda** — decisão de design, não de banco.

Nada disso foi feito nesta rodada porque **341–436 ms cabe no orçamento com folga de 5×**, e otimizar antes de doer
é como a complexidade entra.

## 7. O que NÃO foi medido

| Item | Por quê |
|---|---|
| Carga concorrente (muitos usuários ao mesmo tempo) | o ambiente de construção tem 2 vCPU; medir concorrência aqui produziria número enganoso. `scripts/loadtest.py` existe para rodar em ambiente dimensionado |
| Latência de rede entre aplicação e banco | mesma máquina na medição |
| Desempenho com armazenamento S3 real | `STORAGE_PROVIDER=local` na medição |
| Tempo de resposta do antivírus | `ANTIVIRUS_PROVIDER=none` na medição |
| Crescimento ao longo de meses (fragmentação, bloat, vacuum) | exige ambiente de longa duração |
| Grafo em profundidade 3 ou mais | a API expõe profundidade 1 e 2 (limite declarado); medir o que não é oferecido não diria nada |
| Notificação em fan-out para equipe muito grande | o volume sintético usa equipes de poucos membros; uma organização com centenas de pessoas por projeto não foi simulada |

Essas lacunas são de **medição**, não de implementação. Dizer "a plataforma aguenta X usuários simultâneos" sem ter
medido seria invenção.

## 8. Como reproduzir

```bash
# escala reduzida (rápida)
cd backend && PERF=1 TEST_ADMIN_DATABASE_URL="postgresql://postgres@127.0.0.1:5432/postgres" \
  python3 -m unittest tests.test_v0150_performance -v

# escala cheia (a deste relatório)
cd backend && PERF_FULL=1 TEST_ADMIN_DATABASE_URL="postgresql://postgres@127.0.0.1:5432/postgres" \
  python3 -m unittest tests.test_v0150_performance -v
```

A última linha da saída traz os tempos medidos naquela execução.
