# TECHNICAL BASELINE LOCK — v0.18.1

> Este documento responde a UMA pergunta, com evidência: **a base técnica está pronta para ser
> congelada e entregue ao Designer, e depois publicada na web?**
>
> A resposta vem em duas decisões separadas, porque são decisões diferentes.

---

## DECISÃO 1 — ENTREGA AO DESIGNER: **GO**

A base está congelada para fins de design. O que o Designer vai representar não muda mais nesta
janela: entidades, estados, permissões, rotas e mensagens estão fixos e cobertos por teste.

**Prova:**

| Portão | Resultado | Evidência |
|---|---|---|
| Suíte completa em PostgreSQL real, banco criado do zero | **1.298 testes, 0 falhas, 26 em passo próprio** | `docs/evidence/test_run_v0.18.1.log` |
| Caminho de atualização v0.17.0 → v0.18.x **com dado dentro** | aplica limpo; dado anterior intacto | `test_v0181_migrations.py` (8) |
| Migration que falha no meio | não deixa metade aplicada | mesmo arquivo |
| Concorrência nas entidades novas | 1 responsável corrente, 1 denominador vigente, rodada completa ou nenhuma | `test_v0181_concurrency.py` (9) |
| Jornada completa de ponta a ponta (18 passos, 1 projeto, 1 trilha) | verde | `test_e2e_v0181_journeys.py` |
| Smoke de publicação (20 verificações) | 17 passaram, 0 falharam, 3 pulados **com motivo** | `scripts/smoke_test.py`, `test_v0181_smoke.py` |
| Isolamento entre organizações nas 33 tabelas novas | nenhuma linha atravessa | `test_v0180_security.py` (24) |
| Carga concorrente (12 threads, 20 s) | 3.207 requisições, **0 erro**, p95 máximo 335 ms | `docs/evidence/loadtest_v0.18.1.json` |
| Acessibilidade no navegador (12 verificações) | verde | `test_e2e_v0181_accessibility.py` |
| Lint, tipos e build da interface | limpos | `docs/evidence/ruff_v0.18.1.log`, `tsc` + `node build.mjs` |
| Integridade do banco | 0 FK quente sem índice; 0 `SECURITY DEFINER` sem `search_path` | `docs/evidence/db_integrity_v0.18.1.txt` |
| Backup → restauração → integridade | restaura 34 migrações, cadeias íntegras, camadas desligadas/íntegras | `scripts/restore_test.sh` |

**O que o Designer recebe de insumo:** `DESIGN_HANDOFF_FINAL.md` (atualizado nesta rodada),
`REQUIREMENTS_MATRIX.md`, `INFORMATION_ARCHITECTURE.md`, `NAVIGATION_MODEL.md`,
`PRIVACY_VISIBILITY_MATRIX.md` e os cinco documentos da camada de impacto
(`CLAIM_INTEGRITY.md`, `REPUTATION_ARCHITECTURE.md`, `SEAL_ENGINE.md`, `SMART_FORMS.md`,
`RESPONSIBILITY_ENGINE.md`).

**Nenhum item do registro de dívida bloqueia o design** — a única linha marcada "bloqueia design" é
H6, que **é** o trabalho do Designer (as telas da camada v0.18.0 não existem).

---

## DECISÃO 2 — PUBLICAÇÃO WEB: **GO WITH CONDITIONS**

Seis condições, nenhuma delas de código. Todas são credencial, ambiente, decisão externa ou
verificação que só existe fora deste sandbox.

| # | CONDIÇÃO | POR QUÊ | COMO RESOLVER | QUEM | DEPENDÊNCIA | TESTE / CRITÉRIO DE ACEITE | BLOQUEIA DESIGN? | BLOQUEIA WEB? |
|---|---|---|---|---|---|---|---|---|
| 1 | **Auditoria de dependências** | `npm audit` e `pip-audit` **não executaram**: registry npm devolve 403 e o índice PyPI não responde (saída anexada em `SECURITY_AUDIT.md` §0). "Não consegui executar" não é "sem vulnerabilidades" | rodar em ambiente com registry; anexar saída em `docs/evidence/`; exceção formal por achado não corrigido | D + I | registry acessível | saída anexada, zero achado crítico sem exceção assinada | Não | **Sim** |
| 2 | **Provedores externos reais** | SMTP, S3, antivírus, pagamento, fiscal e IdP estão em modo simulado. `/readyz` **declara** isso hoje (`antivirus: none`, `ai: local`, `billing: sandbox`) | configurar por ambiente e rodar o smoke contra o ambiente real | P (credenciais) + I | contas do proprietário | smoke com `ready_declares_providers` sem "modo não produtivo" | Não | **Sim** |
| 3 | **Aprovação jurídica das 11 minutas** | o banco **recusa** registrar aceite de documento não revisado: sem aprovação, ninguém se cadastra em produção. É trava de propósito (ADR-187) | revisão e aprovação com revisor registrado | J + P | advogado(a) | `legal_documents` com `status='approved'` e revisor; `GET /v1/legal/pending` vazio para conta nova | Não | **Sim** |
| 4 | **Imagem Docker construída e executada** | o `Dockerfile` está correto na leitura (usuário não-root, `--no-server-header`, `--proxy-headers`), mas **não foi construído aqui** | `docker build` + `run` + `/healthz` + `/readyz` + migrations no contêiner | I | docker | healthcheck verde e migrations aplicadas pelo contêiner | Não | **Sim** |
| 5 | **Observabilidade com coletor e alertas** | logs estruturados e `/metrics` existem; ninguém está lendo. Os nove alertas mínimos estão na §5 do runbook | Prometheus/Grafana (ou equivalente) + alertas | I | infraestrutura | alerta dispara em teste induzido (parar o worker) | Não | **Sim** |
| 6 | **Carga fora da máquina do banco** | os 160 rps medidos têm cliente, API e PostgreSQL no mesmo host: serve para pegar regressão, não para dimensionar | repetir contra homologação, com rede real | I | ambiente de homologação | p95 < 1 s com a concorrência esperada, 0 erro | Não | **Sim** |

### O que **não** é condição (e por que)

- **Metas dos ODS e dados do IBGE**: a interface e a API **declaram** a ausência (`from_official_load
  = false`, `ods_targets` vazia, teste que fixa o estado). Publicar sem o dado oficial é honesto;
  publicar afirmando tê-lo não seria.
- **Mapeamento GRI/ISSB/IRIS+**: os três estão `registry_only`, sem mapeamento inventado.
- **Selos publicados**: zero definições embarcadas, por decisão (ADR-209). O motor funciona; a
  política de selo é do proprietário.
- **Telas da camada v0.18.0**: é a próxima fase, não uma pendência desta.

---

## O que esta rodada corrigiu no produto (e como foi encontrado)

| # | Defeito | Como apareceu | Correção |
|---|---|---|---|
| 1 | **Sinal contextual de impacto morto para todo terceiro** | a jornada pediu o match como FINANCIADOR e o contexto chegou vazio: a RLS das tabelas de equidade (corretamente) só devolve linha para a organização dona. O pacote recebido lia direto, e nenhum teste pedia o match de fora | `project_impact_context()` (migração 0034), `SECURITY DEFINER`, devolve **só números**, nunca a narrativa, e **nada** para projeto não publicado |
| 2 | **"Referência neutra" de 0,5 premiava quem não declarava contexto** | leitura do diff recebido: projeto com contexto declarado e nota 0,35 ficaria atrás de projeto sem contexto nenhum | sinal ausente volta a ser UNKNOWN (ADR-026): reduz cobertura e confiança, e aparece em `missing_data`. Três testes, incluindo "omitir não pode ser melhor que declarar pouco" |
| 3 | **Prazo sem fuso devolvia 500** | a jornada criou um edital com `closes_at: "2026-12-05"` — o que um seletor de data produz | validador na base de todos os schemas: **422** dizendo o que falta, com exemplo. A plataforma **não** adivinha fuso (23h59 em Rio Branco ≠ 23h59 em Brasília) |
| 4 | **"Erradicamos" passava como alegação sustentada** | a jornada declarou uma alegação exagerada de propósito e o verificador devolveu `substantiated`: havia **uma** medição validada, e isso bastava para `absolute_language` | 12ª regra: `totality_claim_without_coverage` — totalidade exige denominador com fonte **e** cobertura medida ≥ 99%; a mensagem diz a cobertura real |
| 5 | **Cabeçalho `Server: uvicorn`** | smoke de publicação | produção já usava `--no-server-header`; o **harness de teste** passou a subir igual, e o Nginx ganhou `server_tokens off` + `proxy_hide_header` |
| 6 | **Três alvos de toque com 21–23 px** | teste de acessibilidade em 390 px | CSS: 24 px mínimos em link solto, atalho de conteúdo e ação de painel (WCAG 2.2 AA 2.5.8) |
| 7 | **Série longitudinal sem declarar a janela** | leitura do código recebido: a rota lê 24 medições e o resumo parecia ser da vida do projeto | `window`, `total_known` e `window_truncated` no payload, com o aviso no texto |

Quatro testes **meus** também foram corrigidos porque mediam a coisa errada — o mais grave deles
esperava "um heading qualquer" depois do login e, por isso, quatro verificações de acessibilidade
mediam a tela de login achando que mediam a aplicação. Está escrito no arquivo, no lugar onde
alguém vai reler.

---

## Congelamento

| O quê | Valor |
|---|---|
| Versão | **0.18.1** |
| Ramo | `chore/v0.18.1-final-technical-hardening` |
| Migrações | 34 (0001 … 0034), forward-only, com checksum |
| Tabelas | 285 |
| Operações de API | 815 |
| Testes | 1.298 (0 falhas; 26 em passo próprio) |
| Pacote | `IMPACTO_v0.18.1_TECHNICAL_BASELINE.zip` |

**A partir daqui, nesta janela:** nenhuma mudança de contrato de API, de nome de campo, de estado de
entidade ou de permissão sem registro em `DECISIONS.md` e sem atualizar o handoff. Correção de
defeito continua liberada — é para isso que a suíte existe.
