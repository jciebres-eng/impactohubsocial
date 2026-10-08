# Relatório final — v0.18.1: endurecimento técnico e congelamento da base

> Relatório honesto, em português, com VERDE / AMARELO / VERMELHO e o motivo de cada cor. Todo
> número vem de execução nesta rodada, não de documento anterior.
>
> **A regra que organizou o trabalho:** código existente ≠ funcionalidade implementada ≠
> funcionalidade validada ≠ pronta para produção. O pacote recebido estava na terceira categoria
> para quatro reforços; esta rodada o levou à quarta — e descobriu que a terceira não era verdade.

**Data:** 2026-10-06 · **Versão:** 0.18.1 · **Ramo:** `chore/v0.18.1-final-technical-hardening`
**Suíte:** 1.298 testes, 0 falhas, 26 em passo próprio · **Banco:** 285 tabelas, 34 migrações
**API:** 815 operações · **Carga:** 3.207 requisições, 160 req/s, 0 erro

---

## A. O veredito, primeiro

| Decisão | Resultado |
|---|---|
| **Entrega ao Designer** | 🟢 **GO** — base congelada, nada do que o Designer vai representar muda nesta janela |
| **Publicação web** | 🟡 **GO WITH CONDITIONS** — seis condições, **nenhuma de código** |

As seis condições, na íntegra e com responsável, estão em `TECHNICAL_BASELINE_LOCK.md`. Resumo:
auditoria de dependências num ambiente com registry · provedores externos reais · aprovação
jurídica das 11 minutas · imagem Docker construída e executada · coletor de métricas com alertas ·
carga repetida fora da máquina do banco.

---

## B. O que recebi, e o que fiz com isso

O pacote `IMPACTO_v0.18.0_CORE_HARDENED.zip` (964 arquivos, sha256 `fd0a74db…`) é a v0.18.0 que eu
havia entregado **mais** quatro reforços de núcleo e um relatório, produzidos fora desta sessão. O
relatório daquele pacote é honesto no ponto decisivo:

> "Os testes que exigem PostgreSQL real não puderam ser executados neste sandbox… Portanto, o estado
> correto é **GO WITH CONDITIONS**, não GO."

Então a primeira coisa que fiz **não** foi escrever código: foi integrar os quatro reforços no
repositório e rodar a suíte inteira contra PostgreSQL 16 real. O resultado está em §C.

| Reforço recebido | Situação depois da verificação |
|---|---|
| Sinal contextual de impacto no match | 🔴 **estava morto para todo terceiro** (RLS) — corrigido |
| "Referência neutra" de 0,5 quando falta contexto | 🔴 **premiava quem não declarava** — removido |
| Oito prontidões no diagnóstico | 🟢 funciona; a jornada confere as oito chaves |
| Proveniência por campo na montagem de documento | 🟢 funciona |
| Série longitudinal por indicador | 🟡 funcionava **sem declarar a janela** de 24 medições — corrigido |

---

## C. Os sete defeitos encontrados, e como cada um apareceu

| # | Defeito | Gravidade | Como apareceu | Correção |
|---|---|---|---|---|
| 1 | **Contexto de impacto invisível para o financiador** | 🔴 alta | a jornada pediu o match como financiador; a RLS das tabelas de equidade (corretamente) não devolve linha a terceiro, e o código lia direto. **Nenhum teste pedia o match de fora** | `project_impact_context()` (migração 0034), `SECURITY DEFINER`, devolve **só números e booleanos**, nunca a narrativa, e **nada** para projeto não publicado. 5 testes, um deles confere o que a função **não** devolve |
| 2 | **Omitir contexto rendia mais que declarar pouco** | 🔴 alta | leitura do diff: 0,5 "neutro" > 0,35 declarado | sinal ausente volta a UNKNOWN (ADR-026); 3 testes, incluindo "omitir não pode ser melhor que declarar pouco" |
| 3 | **Prazo sem fuso horário → HTTP 500** | 🔴 alta | a jornada criou um edital com `closes_at: "2026-12-05"` (o que um seletor de data produz) | validador na base de **todos** os schemas: 422 com exemplo. A plataforma não adivinha fuso — 23h59 em Rio Branco não é 23h59 em Brasília |
| 4 | **"Erradicamos" passava como sustentada** | 🔴 alta | a jornada declarou a alegação exagerada de propósito; havia **uma** medição validada e isso bastava para a regra de linguagem absoluta | 12ª regra `totality_claim_without_coverage` (migração 0033): totalidade exige denominador com fonte **e** cobertura ≥ 99%; a mensagem diz a cobertura real ("53% de 60 elegíveis") |
| 5 | **`Server: uvicorn` no harness de teste** | 🟡 média | smoke de publicação | produção já usava `--no-server-header`; o teste passou a subir igual, e o Nginx ganhou `server_tokens off` + `proxy_hide_header` |
| 6 | **Três alvos de toque de 21–23 px** | 🟡 média | teste de acessibilidade em 390 px | 24 px mínimos em link solto, atalho de conteúdo e ação de painel (WCAG 2.2 AA 2.5.8) |
| 7 | **Série longitudinal sem declarar a janela** | 🟡 média | leitura do código recebido | `window`, `total_known`, `window_truncated` no payload, com aviso no texto |

**Nenhum teste foi enfraquecido para fechar a rodada.** A única expectativa alterada foi a de
`test_funder_blockers` (afirmava `eligible` para projeto **sem** contexto de impacto): virou dois
testes com nome próprio mais um terceiro contra o incentivo perverso. Quatro testes **meus**
estavam medindo a coisa errada e estão corrigidos, com o motivo escrito no arquivo — o pior deles
fazia quatro verificações de acessibilidade medirem a tela de login.

---

## D. O que foi provado nesta rodada (as 75 provas novas)

| Área | Prova | Resultado |
|---|---|---|
| **PostgreSQL real, banco do zero** | suíte completa, 34 migrações | 🟢 1.298 testes, 0 falhas |
| **Caminho de atualização** | v0.17.0 **com dado dentro** → v0.18.x | 🟢 dado intacto; linha de base sem fonte sobrevive e passa a ser **contável** |
| **Forward-only** | migration aplicada e alterada | 🟢 recusada com mensagem |
| **Falha no meio da migração** | migração deliberadamente quebrada | 🟢 nada meio aplicado, nada registrado |
| **Concorrência** | 6 threads soltas ao mesmo tempo | 🟢 1 responsável corrente, 1 denominador vigente, rodada completa ou nenhuma, selo nunca com critério não satisfeito |
| **Transação** | `ROLLBACK` e `SAVEPOINT` | 🟢 nada vaza; o trabalho anterior ao savepoint permanece |
| **Jornada completa** | 18 passos, 1 projeto, 1 trilha | 🟢 inclui as recusas esperadas |
| **Cross-tenant** | 33 tabelas novas, linha a linha | 🟢 nenhuma linha atravessa; o que é aberto é **declarado** com motivo |
| **Smoke de publicação** | 20 verificações | 🟢 17 passaram, 0 falharam, 3 pulados **com motivo** |
| **Acessibilidade** | 12 verificações no navegador | 🟢 incluindo contraste **calculado** nos dois temas |
| **Carga** | 12 threads, 21 rotas | 🟢 3.207 req, 160 rps, **0 erro** |
| **Backup e restauração** | dump → restore em banco descartável | 🟢 34 migrações, cadeias íntegras, camada econômica **desligada**, camada de impacto **íntegra** (6 conferidores novos) |

---

## E. O que continua vermelho, com nome

| # | Item | Por que é vermelho | Bloqueia design? | Bloqueia web? |
|---|---|---|---|---|
| 1 | **Auditoria de dependências** | `npm audit` → `403 Forbidden`; `pip-audit` → indisponível. **Não executou**, e isso não é "sem vulnerabilidades" | Não | **Sim** |
| 2 | **Provedores externos reais** | SMTP, S3, antivírus, pagamento, fiscal, IdP simulados — e o `/readyz` declara isso | Não | **Sim** |
| 3 | **Aprovação jurídica das minutas** | o banco recusa aceite de rascunho (trava de propósito) | Não | **Sim** |
| 4 | **Docker não construído aqui** | arquivo correto na leitura; build/run não exercitados | Não | **Sim** |
| 5 | **Observabilidade sem coletor** | `/metrics` e logs existem; ninguém lendo | Não | **Sim** |
| 6 | **Carga só na mesma máquina** | serve para regressão, não para dimensionar | Não | **Sim** |
| 7 | **axe-core e leitor de tela** | NOT VERIFIED, com o motivo | Não | Não (declarado) |
| 8 | **Metas dos ODS e dados do IBGE** | não carregados; a interface **declara** a ausência | Não | Não (declarado) |
| 9 | **Mapeamento GRI/ISSB/IRIS+** | decisão de produto **e** jurídica | Não | Não |
| 10 | **Telas da camada v0.18.0** | é o trabalho do Designer | **É a fase dele** | Sim |

O registro completo, com esforço e risco por item, está em `TECHNICAL_DEBT_REGISTER.md`
(6 CRITICAL, 8 HIGH, 7 MEDIUM, 6 LOW/FUTURE).

---

## F. Entregas desta rodada

| Documento | Para quê |
|---|---|
| `TECHNICAL_BASELINE_LOCK.md` | as duas decisões, com as seis condições em formato acionável |
| `REQUIREMENTS_MATRIX.md` | reconciliação histórica v0.7.0 → v0.18.1, 60 requisitos com classes A–I |
| `TECHNICAL_DEBT_REGISTER.md` | dívida por severidade, com "bloqueia design?" e "bloqueia web?" |
| `PRODUCTION_RELEASE_RUNBOOK.md` | publicação passo a passo, com validação e rollback por item |
| `ACCESSIBILITY_REPORT.md` | 12 verificações verdes e 6 NOT VERIFIED, com o motivo |
| `DESIGN_HANDOFF_FINAL.md` | reescrito: as 8 telas novas, os 2 componentes a reaproveitar e os **estados de exceção** |
| `scripts/smoke_test.py` | 20 verificações contra instância em execução, com veredito próprio |

---

## G. Como conferir

```bash
ADMIN_DATABASE_URL="postgresql://postgres@127.0.0.1:5432/postgres" bash scripts/dev_reset_db.sh
cd backend && TEST_ADMIN_DATABASE_URL="postgresql://postgres@127.0.0.1:5432/postgres" \
  PASSWORD_SCRYPT_N=16384 RATE_LIMIT_MULTIPLIER=1000 python3 -m unittest discover -s tests -t .
cd backend && PERF=1 TEST_ADMIN_DATABASE_URL="..." python3 -m unittest tests.test_v0180_performance
python3 scripts/smoke_test.py --base http://127.0.0.1:PORTA --email ... --password ...
python3 scripts/loadtest.py --base http://127.0.0.1:PORTA --threads 12 --seconds 20
REPORT_DATABASE_URL="postgresql://impacto_owner@127.0.0.1:5432/impacto_dev" python3 scripts/db_integrity_report.py
BACKUP_DATABASE_URL=... bash scripts/backup.sh && ADMIN_DATABASE_URL=... bash scripts/restore_test.sh backups/X.dump
```

## H. A frase que resume a rodada

A versão anterior afirmava coisas verdadeiras **e** uma coisa que não era: que o impacto
contextualizado valia para quem olha de fora. Não valia — e só um banco real com um financiador na
frente podia mostrar isso. É por isso que "rodar a suíte" não é burocracia: foi a suíte que
transformou quatro afirmações em dois defeitos corrigidos, e é ela que vai avisar na próxima vez.
