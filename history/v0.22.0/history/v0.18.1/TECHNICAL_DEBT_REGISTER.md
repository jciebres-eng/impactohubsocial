# Registro de dívida técnica — v0.18.1

> Uma linha por item, com impacto, solução, esforço, dependência, risco de não corrigir e as duas
> perguntas que decidem a fase: **bloqueia o Designer?** **bloqueia a publicação web?**
>
> Severidade: **CRITICAL** (corrigir antes de publicar) · **HIGH** (corrigir na primeira janela
> depois do design) · **MEDIUM** · **LOW** · **FUTURE**.

## CRITICAL — nada aqui bloqueia o Designer; tudo aqui bloqueia a publicação

| # | Item | Impacto | Solução | Esforço | Dependência | Risco de não corrigir | Bloqueia design? | Bloqueia web? |
|---|---|---|---|---|---|---|---|---|
| C1 | **Auditoria de dependências não executada** (`npm audit`, `pip-audit` bloqueados pelo ambiente) | CVE conhecido pode estar no bundle sem ninguém saber | rodar em ambiente com registry, anexar saída em `docs/evidence/`, exceção formal por achado não corrigido | 1–2 h | registry acessível | publicar com vulnerabilidade conhecida de terceiro | **Não** | **Sim** |
| C2 | **Nenhum provedor externo real configurado** (SMTP, S3, antivírus, pagamento, fiscal, IdP) | o produto funciona em modo simulado; e-mail não sai, arquivo não sobe para armazenamento durável, vírus não é barrado | configurar por ambiente e rodar o smoke com `--base` do ambiente real | 1–2 dias | contas e credenciais do proprietário | publicar um produto que não entrega e-mail nem guarda arquivo | **Não** | **Sim** |
| C3 | **Minutas legais sem aprovação de advogado(a)** (11 documentos em rascunho) | o banco **recusa** registrar aceite de rascunho: sem aprovação, ninguém se cadastra em produção | revisão jurídica + aprovação com revisor registrado | depende do jurídico | advogado(a) | cadastro bloqueado em produção (trava de propósito) | **Não** | **Sim** |
| C4 | **Docker não construído nem executado neste ambiente** | `Dockerfile` existe e está correto na leitura, mas build/run/healthcheck não foram exercitados aqui | `docker build` + `docker run` + `/healthz` + `/readyz` + migrations no contêiner | 2–4 h | docker disponível | descobrir no dia da publicação que a imagem não sobe | **Não** | **Sim** |
| C5 | **Observabilidade sem coletor** | logs estruturados e `/metrics` existem; ninguém está lendo | Prometheus/Grafana (ou equivalente) + alertas da §41 do pedido | 4–8 h | infraestrutura | falha silenciosa em produção: fila parada, webhook falhando, e-mail não entregue | **Não** | **Sim** |
| C6 | **Carga medida só na mesma máquina** | 160 rps com 12 threads, 0 erro — mas cliente, API e banco no mesmo host | repetir contra o ambiente de homologação, com rede real e banco separado | 2–4 h | ambiente de homologação | dimensionar errado e cair na primeira campanha | **Não** | **Sim** |

## HIGH — não bloqueia a publicação; bloqueia a *maturidade* do produto

| # | Item | Impacto | Solução | Esforço | Bloqueia design? | Bloqueia web? |
|---|---|---|---|---|---|---|
| H1 | **Metas oficiais dos ODS (169) e dados do IBGE não carregados** | o catálogo territorial diz "conferir na carga oficial"; `ods_targets` responde vazio | rodar os dois importadores com os arquivos oficiais (exigem fonte, URL e data) | 2–4 h | **Não** | **Não** (está declarado na interface) |
| H2 | **Mapeamento para GRI, ISSB e IRIS+ ausente** | relatório para esses referenciais não é possível; os três estão `registry_only` | decisão de produto + jurídica (as minutas da v0.17.0 os excluem), depois mapear indicador a indicador | dias | **Não** | **Não** |
| H3 | **Decaimento por idade na reputação** | observação de três anos pesa como a de ontem | aplicar `core/evidence.freshness()` às dimensões, versionando o motor | 4–8 h | **Não** | **Não** |
| H4 | **Detecção de conluio** | duas organizações que validam medições uma da outra sobem em duas dimensões | grafo de validação recíproca + marca de revisão humana (nunca acusação automática) | 1–2 dias | **Não** | **Não** |
| H5 | **Sinal de impacto só no sentido financiador→projeto** | a OSC que olha um edital não vê o contexto de equidade influenciar o match dela | decidir se contexto entra como prontidão no sentido OSC→edital (não é critério de aderência ao edital) | 4–8 h | **Não** | **Não** |
| H6 | **Telas da camada v0.18.0 não existem** | reputação, selo, alegação, responsabilidade e equidade só existem por API | é a fase de design, com o handoff desta rodada | — | **É o trabalho dele** | **Sim** (sem tela não há produto publicável) |
| H7 | **Procedência do preenchimento não é persistida** | `Suggest` devolve `{filled_by, origin, replaced_text}` e nenhum formulário grava | coluna/jsonb de procedência nos formulários que importam | 4–8 h | **Não** | **Não** |
| H8 | **Verificação pública dos selos novos** | `/v1/public/verify/{code}` serve os registros da v0.14.0, não os selos da v0.18.0 | ligar `seal_awards` à verificação pública com código curto | 4–8 h | **Não** | **Não** |

## MEDIUM

| # | Item | Observação |
|---|---|---|
| M1 | **`axe-core` e leitor de tela não verificados** | 12 verificações de acessibilidade feitas à mão no navegador; o resto está em `ACCESSIBILITY_REPORT.md` §2 |
| M2 | **Segundo navegador não testado** | só Chromium instalado |
| M3 | **`/v1/reputation/me` é a rota mais lenta** (p95 335 ms sob 12 threads) | são 11 consultas de sinal; cabe cache por organização com invalidação por evento |
| M4 | **Dependências web em faixa aberta** (`@types/*`, `@capacitor/*`) | declaradas como **NOT VERIFIED** no inventário; fixar exige registry |
| M5 | **384 chaves estrangeiras sem índice** | de propósito (regra da 0015: só coluna de inquilino ou pai percorrido); revisitar se aparecer consulta nova |
| M6 | **Retenção das trilhas novas sem prazo** | fato sobre organização, não sobre pessoa; prazo é decisão do responsável pelo tratamento |
| M7 | **Taxonomias editoriais sem revisão técnica** | 12 barreiras, 15 determinantes, 15 temas, 8 papéis — cada linha declara que é editorial |

## LOW / FUTURE

| # | Item |
|---|---|
| L1 | Busca incremental é `ILIKE`: "Cuiaba" sem acento não encontra "Cuiabá" (exige `unaccent`/`pg_trgm`) |
| L2 | Série longitudinal lê as 24 medições mais recentes; a janela é declarada no payload (`window_truncated`) |
| L3 | Selo não tem arte nem nível (bronze/prata/ouro foi recusado: nível é ranking com outro nome) |
| L4 | Emblemas oficiais dos ODS dependem de licença de marca da ONU |
| F1 | App mobile: código pronto (Capacitor), **nunca construído** |
| F2 | Internacionalização além de pt-BR: 294 traduções existem; segundo idioma não foi revisado |

## Como esta lista foi feita

Não é uma lista de impressões. Cada item CRITICAL e HIGH veio de uma destas três fontes:

1. **Tentativa real que falhou** nesta rodada (C1: os dois comandos de auditoria, com a saída de
   erro anexada em `SECURITY_AUDIT.md` §0);
2. **Teste que fixa o estado** (H1: um teste exige que `ods_targets` esteja vazio enquanto o dado
   não entrar — se alguém carregar, o teste avisa);
3. **Achado de código ou de execução** (H5 saiu da jornada de ponta a ponta; M3 saiu do teste de
   carga).
