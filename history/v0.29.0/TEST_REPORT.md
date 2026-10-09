# TEST_REPORT — v0.18.1 (endurecimento técnico final, 2026-10-06)

**1.298 testes, 0 falhas, 26 em passo próprio** (eram 1.223 na v0.18.0 e 961 na v0.17.0). Log
íntegro: `docs/evidence/test_run_v0.18.1.log`. Carga: `docs/evidence/loadtest_v0.18.1.json`.
Desempenho: `docs/evidence/perf_v0.18.1.log`. Integridade: `docs/evidence/db_integrity_v0.18.1.txt`.
Lint: `docs/evidence/ruff_v0.18.1.log`.

Os **75 testes novos** desta rodada existem para provar o que a versão anterior afirmava:

| Arquivo | Testes | O que ele prova |
|---|---|---|
| `test_v0181_concurrency.py` | **9** | seis sessões disparando ao mesmo tempo deixam **um** responsável corrente e **um** denominador vigente; rodada de verificação fica completa ou não fica; concessão de selo nunca grava critério não satisfeito; retrato de reputação nunca grava valor sem observação; `ROLLBACK` não deixa linha; `SAVEPOINT` preserva o trabalho anterior |
| `test_v0181_migrations.py` | **8** | banco preparado na **v0.17.0 com dado dentro** sobe para a v0.18.x: o dado anterior fica intacto, a linha de base sem fonte **sobrevive e passa a ser contável** (a trava vale para escrita nova), as 33 tabelas chegam com RLS e política, as 10 funções novas existem, migration alterada é recusada (forward-only) e migration que falha no meio **não deixa metade aplicada** |
| `test_e2e_v0181_journeys.py` | **18** | a jornada completa num único projeto: registro → login → projeto → publicação → diagnóstico (8 prontidões) → equidade → ODS → indicador com fonte → evidência → medição validada por outra organização → match (os dois sentidos) → responsabilidade → decisão → alegação marcada → alegação sustentada → revisão por convite → reputação → contestação → selo → revogação por critério caído → relatório → trilha de auditoria |
| `test_v0181_smoke.py` | **5** | o smoke de publicação roda, nenhuma verificação obrigatória falha, **provedor simulado é declarado como simulado**, verificação pulada nunca conta como aprovada, e o veredito nunca é GO quando houve pulo |
| `test_v0181_hardening.py` | **16** | a função agregada de contexto (inclusive **o que ela não devolve**: nenhuma narrativa, nada para projeto privado), a 12ª regra de alegação (cobertura 53% de 60 elegíveis não é erradicação) e os controles de dependência verificáveis offline |
| `test_e2e_v0181_accessibility.py` | **13** | no navegador real: nome acessível em todo controle, erro anunciado, atalho de conteúdo como **primeira** parada do Tab, sem armadilha de foco, foco visível, marcos e `h1` único, alternativa textual, **contraste calculado** nos temas claro e escuro, 390 px sem rolagem horizontal, alvo de toque ≥ 24 px, movimento reduzido |
| `test_impact_core_hardening.py` | **6** | (recebido no pacote externo) UNKNOWN ≠ zero, contexto remoto não perde para urbano, contrato do match, série longitudinal |

## Três testes que encontraram defeito de produto nesta rodada

1. **A jornada pediu o match como financiador** — e o sinal contextual veio UNKNOWN. A RLS das
   tabelas de equidade (corretamente) não entrega linha a terceiro: o código recebido lia direto, e
   **nenhum teste pedia o match de fora**. Virou a função `project_impact_context()`.
2. **A jornada criou um edital com `closes_at: "2026-12-05"`** — e recebeu **500**. Virou 422 com
   exemplo, em todos os schemas de uma vez.
3. **A jornada declarou "erradicamos a defasagem"** — e o verificador respondeu `substantiated`.
   Virou a 12ª regra de integridade.

E o smoke de publicação encontrou o cabeçalho `Server: uvicorn`, que só existia no harness de teste:
o servidor de teste passou a subir como o de produção sobe.

## Quatro testes MEUS que estavam medindo a coisa errada

Registrado porque é o tipo de erro que fabrica confiança falsa:

1. `_login` esperava "um heading qualquer" e casava com o título da **própria tela de login** —
   quatro verificações de acessibilidade mediam a tela de login achando que mediam a aplicação. Foi
   assim que três alvos de toque de 21–23 px apareceram: o achado é real, mas o teste estava na
   página errada.
2. Ordem alfabética outra vez: `test_a_published_project…` publicava o projeto antes de
   `test_an_unpublished_project…` rodar. Cada um ganhou o seu próprio projeto.
3. A verificação de "zero definições de selo embarcadas" contava linhas no banco compartilhado
   excluindo códigos de teste **por padrão de nome** — bastava um teste novo com outro nome para
   virar alarme falso. Passou a ler as **migrações**, que é onde a promessa vive.
4. A varredura de dependência não declarada ignorava `requirements-optional.txt` e acusava
   `pytesseract`, que está declarado e inventariado.

Nenhum teste foi enfraquecido ou removido. A única expectativa alterada foi a de
`test_funder_blockers`, que afirmava `eligible` para um projeto **sem contexto de impacto**: a
asserção foi movida para dois testes com nome próprio — "sem contexto vai para revisão humana" e
"com contexto declarado fica elegível" — mais um terceiro provando que omitir nunca é melhor que
declarar pouco.

Ambiente: **PostgreSQL 16 real criado do zero** (bootstrap + 34 migrações), servidor HTTP real
(uvicorn, agora com `server_header=False`) e Chromium (Playwright).

```
cd backend && TEST_ADMIN_DATABASE_URL="postgresql://postgres@127.0.0.1:5432/postgres" \
  PASSWORD_SCRYPT_N=16384 RATE_LIMIT_MULTIPLIER=1000 python3 -m unittest discover -s tests -t .
```

---

# Histórico — TEST_REPORT da v0.18.0

**1.223 testes, 0 falhas, 26 pulados** (eram 961 na v0.17.0, 788 na v0.16.0 e 673 na v0.15.0). Log íntegro:
`docs/evidence/test_run_v0.18.0.log`. Desempenho: `docs/evidence/perf_v0.18.0.log`. Integridade do banco:
`docs/evidence/db_integrity_v0.18.0.txt`. Lint: `docs/evidence/ruff_v0.18.0.log`.

Os **262 testes novos** desta rodada, por arquivo:

| Arquivo | Testes | O que ele protege |
|---|---|---|
| `test_v0180_equity.py` | **30** | impacto não é quantidade: sem denominador com fonte, data e método, nenhum método de normalização está disponível (resposta "indisponível" com motivo, nunca estimativa); avaliação **sem nota**; `compare()` com `comparable: false` e **nunca** veredito; denominador versionado e imutável; barreira com escada de prova |
| `test_v0180_territory.py` | **20** | `from_official_load` separando carga oficial de conhecimento da plataforma; as 27 UFs semeadas dizendo "conferir na carga oficial"; perfil territorial mostrando o **não medido** com peso igual; importadores recusando arquivo sem fonte, URL e data, e recusando o arquivo inteiro por uma linha inválida |
| `test_v0180_frameworks.py` | **24** | 19 referenciais com o que a plataforma **não** mapeia; escada de seis degraus; **`certified` recusado por gatilho**; `verified` exigindo outro revisor; cobertura respondendo "consigo relatar?" com número; `is_material` **derivada** e não escrevível |
| `test_v0180_claims.py` | **42** | **não existe coluna de situação em `claims`** (lido do `information_schema`); as 11 regras determinísticas e o mesmo veredito para o mesmo texto; linguagem absoluta punida só **sem base**; causalidade sobre elo fraco; rodada nova que não apaga a anterior; revisão **por convite nomeado** de outra organização; aceitar que **qualifica sem apagar** a marca |
| `test_v0180_reputation.py` | **30** | **nenhum campo agregado** na resposta nem coluna agregada no banco; organização nova **sem medida**, não com nota baixa; faixa insuficiente que não publica número; varredura AST recusando sinal comercial; plano pago que não muda dimensão; órgão público sem nota; pessoa física sem perfil público; contestação que aparece no perfil; correção que gera ponto novo |
| `test_v0180_seals.py` | **23** | **a aplicação não concede selo**: INSERT direto recusado, e `app_award_seal()` recusando até para o dono do banco; definição publicada imutável; versão nova aposentando a anterior; validade igual ao **menor** prazo; recusa **registrada** para quem foi recusado; revogação como fato novo; varredura de sinal comercial no módulo **e** na migração |
| `test_v0180_lookups.py` | **17** | origem em **toda** sugestão de **todas** as buscas; UFs semeadas como conhecimento da plataforma; `%` e `_` como texto; isolamento de fornecedor, projeto e indicador próprio; e o componente lido do arquivo (pergunta antes de substituir, mostra origem, devolve procedência, não esconde trabalho feito) |
| `test_v0180_responsibility.py` | **25** | um papel por escopo; papel fora do escopo recusado pelo banco; designação **não reescrita**; encerramento com motivo e imutável; decisão fora do período recusada; decisão sobre documento apontando para a **versão**; quatro-olhos exigindo **pessoas** diferentes; pessoa externa sem coluna de documento |
| `test_v0180_security.py` | **24** | RLS e política nas **33 tabelas novas**; inventário declarado do que é aberto de propósito; nenhuma coluna de CPF/RG/documento; trilhas append-only sem UPDATE nem DELETE; matriz de isolamento linha a linha **com o teste par**; **gaming** (alegação não verificada, retirada de alegação marcada, autovalidação, revisão sem convite, autoconcessão de selo, denominador mínimo); **viés** (projeto pequeno, território remoto, reputação proporcional, organização nova) |
| `test_v0180_docs.py` | **18** | **os números dos documentos conferidos contra o banco**: 11 regras, 6 dimensões, 12 critérios de selo, 8 papéis, 6 tipos de decisão, 13 buscas, zero definições de selo embarcadas, zero metas de ODS carregadas; cada código do banco citado no documento; ADR sem duplicata e com consequência |
| `test_v0180_performance.py` | **9** | as consultas com `CROSS JOIN LATERAL` sobre função, que funcionam com dez linhas e param com dez mil: listagem de alegação, perfil de reputação, listagem e avaliação de selo, designações e a busca incremental (medida em percepção: abaixo de 800 ms) |

Ambiente: **PostgreSQL 16 real criado do zero em cada execução** (bootstrap + 32 migrações), servidor HTTP real
(uvicorn) e Chromium (Playwright). Comando:
```
cd backend && TEST_ADMIN_DATABASE_URL="postgresql://postgres@127.0.0.1:5432/postgres" \
  PASSWORD_SCRYPT_N=16384 RATE_LIMIT_MULTIPLIER=1000 python3 -m unittest discover -s tests -t .
```

Os **26 pulados** são as duas suítes de volume (v0.15.0 com 17, v0.18.0 com 9), que rodam em passo próprio porque o
dado sintético muda o resultado de testes de ranking e de paginação no mesmo banco (ADR-138):
```
cd backend && PERF=1 TEST_ADMIN_DATABASE_URL="..." python3 -m unittest tests.test_v0180_performance
cd backend && PERF_FULL=1 TEST_ADMIN_DATABASE_URL="..." python3 -m unittest tests.test_v0150_performance
```

## Dois defeitos que os testes desta rodada pegaram no produto

1. **Reputação publicando número que a confiança não sustentava.** Havia observações bastando e verificação por
   terceiro baixa; a restrição `insufficient_has_no_value` recusou a gravação do snapshot. Corrigiu-se o **cálculo**,
   não a restrição, e o caso virou teste
   (`test_a_dimension_with_enough_observations_but_low_verification_publishes_no_value`).
2. **A recusa de selo apagava o registro da própria recusa.** `test_the_refused_evaluation_is_recorded_for_whoever_was_refused`
   veio vazio: a exceção dentro da função desfazia a transação e levava embora o `seal_evaluations` recém-inserido.
   A função passou a devolver `NULL` e o 422 é levantado fora da transação (ADR-208).

Nenhum teste foi enfraquecido ou removido para fechar esta rodada. Quatro testes **meus** foram corrigidos porque
mediam a coisa errada: varredura por substring acusando `org_id` (contém "rg") e `name_pt` (contém "name"); lista de
parâmetros maior que a consulta; e expectativa de exceção onde o desenho correto passou a devolver `NULL`.

---

# Histórico — TEST_REPORT da v0.17.0

**961 testes, 0 falhas, 17 pulados** (eram 788 na v0.16.0 e 673 na v0.15.0). Log íntegro:
`docs/evidence/test_run_v0.17.0.log`. Desempenho: `docs/evidence/perf_v0.17.0.log` (duas execuções). Integridade do
banco: `docs/evidence/db_integrity_v0.17.0.txt`.

Os **161 testes novos** desta rodada, por arquivo:

| Arquivo | Testes | O que ele protege |
|---|---|---|
| `test_v0170_payments.py` | **30** | a cobrança simulada nunca passa por real; `is_simulated` derivada e irreescrevível; transição fora do grafo recusada; trilha escrita por gatilho e append-only; parcelamento com soma conferida no COMMIT; nenhuma coluna para número de cartão; webhook idempotente; evento sem assinatura registrado e **sem efeito**; e a fatura com `provider='stripe'` que **não** conta como receita real sem provedor configurado |
| `test_v0170_legal.py` | **27** | as onze minutas registradas, **nenhuma aprovada**; aceite de minuta recusado pela API e pelo SQL direto; aprovação sem revisor recusada; texto de versão imutável; aceite guardando o sha256; versão nova superando a anterior e voltando a pendente; o aceite antigo continuando a provar o texto antigo |
| `test_v0170_monetization.py` | **26** | o portão legal; cartão verde sem fonte recusado; as quatro recusas; a mensagem da ADR-022 chegando à API; quem pode ser cobrado |
| `test_v0170_programs.py` | **19** | situação como grafo; datas derivadas; visibilidade que não bloqueia moderação; linha de base de indicador exigindo fonte; declarado × medido; notificação à equipe executora |
| `test_v0170_security.py` | **18** | RLS e política em todas as 22 tabelas novas; matriz de isolamento linha a linha **com o teste par**; nenhuma coluna nova com dado pessoal sem justificativa; a anonimização que não destrói a prova; retenção |
| `test_v0170_value.py` | **16** | entrega separada de cobrança; estimativa só com linha de base declarada; `app_record_value()` como porta única |
| `test_v0170_docs.py` | **17** | **os documentos conferidos contra o banco**: chaves de regra, cores dos cartões, tipos de evento, arestas do grafo de cobrança, documentos legais registrados |
| `test_v0170_engines.py` | **7** | o registro de motores pela API; os assistentes declarados como extração e **respondendo com `ai_used: false`** |
| `test_architecture.py` (novos) | **6** | motor declarado resolve para código; versão declarada bate com a do módulo; rota declarada existe; determinístico não importa o gateway; **só os pontos declarados chamam o modelo** |
| `test_v0150_performance.py` (novos) | **5** | feed de programas, resumo de valor, cobranças, registro legal e as cinco funções SQL da camada econômica |

Ambiente: **PostgreSQL 16 real criado do zero em cada execução** (bootstrap + 24 migrações), servidor HTTP real
(uvicorn) e Chromium (Playwright). Comando:
```
cd backend && TEST_ADMIN_DATABASE_URL="postgresql://postgres@127.0.0.1:5432/postgres" \
  PASSWORD_SCRYPT_N=16384 RATE_LIMIT_MULTIPLIER=1000 python3 -m unittest discover -s tests -t . -v
```

Os **17 pulados** são a suíte de volume inteira, que roda em passo próprio porque o dado sintético muda o resultado
de testes de ranking e de paginação no mesmo banco (ADR-138). Eram 12 na v0.16.0; cresceu com as cinco medições da
camada econômica. Com `PERF_FULL=1` os 17 rodam e passam:
```
cd backend && PERF_FULL=1 TEST_ADMIN_DATABASE_URL="..." python3 -m unittest tests.test_v0150_performance -v
```

Contagem por suíte, da maior para a menor (métodos `def test_*`). A tabela abaixo é da v0.16.0 e somava
**788**; os arquivos da v0.17.0 estão na tabela do início deste documento:

| Suíte | Testes | Suíte | Testes |
|---|---|---|---|
| `test_v0140_trust` | 88 | `test_v0101_institutional` | 20 |
| `test_v0130_integrations` | 76 | `test_api_features` | 19 |
| `test_v0120_knowledge` | 62 | `test_api_auth` | 19 |
| **`test_v0160_network`** | **55** | `test_v0150_security` | 16 |
| `test_v0100_institutional` | 48 | **`test_v0160_billing`** | **15** |
| `test_v0150_core` | 39 | `test_architecture` | 13 |
| `test_v080` | 34 | `test_v0150_performance` | 12 *(passo próprio)* |
| `test_v0110_monetization` | 34 | `test_v0150_upgrade` | 10 |
| `test_unit` | 33 | `test_e2e_knowledge` | 9 |
| `test_v090_solutions` | 31 | `test_e2e_v0150_journeys` | 8 |
| **`test_v0160_invariants`** | **28** | `test_e2e_v0140_trust` | 8 |
| `test_v0120_hardening` | 27 | **`test_e2e_v0160_journeys`** | **7** |
| `test_security_tenancy` | 25 | `test_e2e_v0150_web` | 6 |
| `test_v0150_invariants` | 21 | demais `test_e2e_*` + `test_api_workflow` + `test_oidc` | 25 |

## As suítes novas e ampliadas desta rodada

| Suíte | Testes | O que prova |
|---|---|---|
| `test_v0160_network.py` | **55** | cada motor da rede pela API real: relação idempotente e com teto de visibilidade · transição recusada fora do grafo · proposta aceita cria relação e intenção (**nunca "investido"**) · anúncio não publica com projeto privado · conversa profissional exige contexto · prontidão devolve explicação e o que falta · recomendação com razão e destino · perfil público sem campo privado e **404** quando suspenso · relatório com números colhidos pelo banco · persona não dá permissão · escada de moderação recusando banimento como primeira resposta |
| `test_v0160_invariants.py` | **28** | o que não pode mudar, incluindo a **matriz entre inquilinos** (toda rota de escrita da rede chamada com identificador existente **de outra organização**) · `beneficiary_groups` só existe em uma tabela e não é filtro de busca em nenhuma das 704 rotas · os três estágios financeiros não se somam · onze listas Python conferidas contra os CHECKs reais do banco · visibilidade travada percorrida nos cinco níveis · identidade do denunciante ausente da resposta ao alvo |
| `test_v0160_billing.py` | **15** | versão de preço imutável · duas versões vigentes impossíveis · aumento sem aviso de 30 dias recusado · redução livre · "ciente" é a única escrita do avisado · entrada e cupom **não** se somam (vale o melhor) · checkout recusa sem `provider_price_id` quando o provedor exige · webhook reentregue não duplica nem estoura o contador de entrada |
| `test_e2e_v0160_journeys.py` | **7** | as quatro personas do pedido percorrendo a cadeia inteira pela API real, mais marketplace público sem sessão, ciclo completo de relatório e uma jornada de moderação com contestação |
| `test_architecture.py` | 6 → **13** | acrescentados: nenhuma rota duplicada (a segunda ficaria inalcançável em silêncio) · motor da rede nunca notifica direto · datas de produto em UTC · **todo destino de recomendação existe no roteador** · preço nunca em literal de código |
| `test_v0150_performance.py` | 7 → **12** | acrescentados: workspace (duas personas), grafo em profundidade 2, marketplace público, caixa de propostas e relações, com volume de rede semeado |
| `test_v0150_upgrade.py` | 10 (ampliado) | o caminho v0.12.1 → … → **0016 → 0017** com dado dentro; as 26 estruturas novas chegam com RLS e política; **esquema atualizado idêntico ao criado do zero** |

## Verificação de SQL por `PREPARE`, não por leitura

`scripts/sql_prepare_check.py` extrai por AST todo literal de SQL do código (inclusive f-strings, com mapa de
preenchimento por arquivo) e roda `PREPARE` em cada consulta contra o banco real. **185 consultas conferidas, 0
erros.**

Foi construído depois de perceber que revisão de código **não** pega nome de coluna errado, e achou 5 defeitos
reais no primeiro uso. Não substitui teste: prova que a consulta é válida contra o esquema, não que o resultado está
certo. Rodar com:
```
DB="postgresql://impacto_owner@127.0.0.1:5432/impacto_dev" python3 scripts/sql_prepare_check.py backend/impacto/network
```

## As 7 jornadas de ponta a ponta desta rodada

1. **Organização**: cadastro → persona → recomendação de primeiro passo → anúncio publicado → proposta recebida →
   aceite (nasce a relação) → execução → relatório enviado → aceito por quem apoia → publicado → visível no perfil.
2. **Investidor**: descoberta no marketplace → lista de acompanhamento (privada por força do teto) → leitura da
   prontidão → conversa **com contexto** → proposta de investimento → aceite cria **intenção** → relatório analisado.
3. **Profissional**: credencial → experiência declarada (pendente) → identificador `@` → perfil público ligado →
   proposta de serviço aceita → a experiência só entra no perfil **depois** de confirmada pela organização citada.
4. **Governo**: necessidade de território → edital publicado → candidatura → convênio proposto → acompanhamento →
   relatório analisado.
5. **Marketplace público sem sessão**: só o que está `published` aparece; projeto privado é invisível mesmo com o
   identificador em mãos.
6. **Ciclo completo de relatório**, incluindo o pedido de ajuste e a volta.
7. **Moderação**: denúncia → medida proporcional → contestação → julgamento por quem não aplicou.

## O que continua NÃO testado

| Item | Por quê |
|---|---|
| **E2E de navegador para as 27 telas novas** | têm cobertura de API e de jornada, não de Playwright. É a lacuna mais relevante desta rodada, e está aqui declarada |
| Verificação de viewport e contraste nas telas novas | o mesmo motivo; as telas antigas têm (25 combinações) |
| Carga concorrente em ambiente dimensionado | 2 vCPU no ambiente de construção produziria número enganoso |
| Integração contra sistema externo real | depende de acesso a instância de cliente ou órgão |
| **Cobrança real** | não há conta Stripe, chave nem preço criado no provedor. O que está testado é o lado da plataforma |
| Assinatura qualificada, Gov.br, ACT, biometria, SMS, KYC, identidade governamental | dependem de contratação; o que existe é o teste da **recusa explícita** |
| `axe` e leitor de tela | registro npm bloqueado neste ambiente |
| Teste de intrusão independente | nunca houve |
| Push nativo | não existe (ver `MOBILE_READINESS_FINAL.md`) |

---

# TEST_REPORT — v0.15.0 (Núcleo do produto, 2026-10-05)

**v0.15.0: 673 testes, 0 falhas, 7 pulados** (564 do v0.14.0 + **109** do núcleo do produto). Log íntegro:
`docs/evidence/test_run_v0.15.0.log`. Lint: `docs/evidence/ruff_v0.15.0.log`. Desempenho:
`docs/evidence/perf_v0.15.0.log`. Integridade do banco: `docs/evidence/db_integrity_v0.15.0.txt`.

Ambiente: **PostgreSQL 16 real criado do zero em cada execução** (bootstrap + 15 migrações), servidor HTTP real
(uvicorn) e Chromium (Playwright). Comando:
```
cd backend && TEST_ADMIN_DATABASE_URL="postgresql://postgres@127.0.0.1:5432/postgres" \
  PASSWORD_SCRYPT_N=16384 RATE_LIMIT_MULTIPLIER=1000 python3 -m unittest discover -s tests -t . -v
```

Os **7 pulados** são a suíte de volume, que roda em passo próprio porque o dado sintético muda o resultado de
testes de ranking e paginação no mesmo banco:
```
cd backend && PERF_FULL=1 TEST_ADMIN_DATABASE_URL="..." python3 -m unittest tests.test_v0150_performance -v
```

| Categoria | v0.13.0 | v0.14.0 | v0.15.0 |
|---|---|---|---|
| Unidade (puros) | 39 | 49 | 55 |
| API/integração (HTTP + PostgreSQL reais) | 395 | 471 | 554 |
| Arquitetura (invariantes do código) | 6 | 8 | 10 |
| E2E de navegador (Chromium) | 28 | 36 | 42 |
| Volume (passo próprio) | — | — | 7 |
| Caminho de atualização de banco | — | — | 10 |
| **Total** | **468** | **564** | **673** |

## Novos no v0.15.0 (109)

| Suíte | Testes | O que prova |
|---|---|---|
| `test_v0150_core.py` | 39 | comportamento de cada capacidade nova, pela API real: ideia sobrevive à promoção · transição inválida recusada com as opções · motivo obrigatório · trilha encadeada · retratos comparáveis · risco de regra separado do declarado e não reaberto · versão de diagnóstico imutável e diff do servidor · montagem bloqueada diz o que falta · quatro olhos · provedor indisponível recusado no banco · inventário de chave sem expor chave |
| `test_v0150_invariants.py` | 21 | mesma entrada + mesmas versões = mesmo resultado · plano não influencia match nem diagnóstico · bloqueado nunca sai elegível e sem pontuação · declaração nunca é verificada · frescura reduz confiança e não pontuação · `insufficient_data` é faixa própria · fonte melhor vence o conflito · hash de documento gerado imutável · varredura de risco idempotente · retrato de projeto imutável tem o mesmo hash |
| `test_v0150_security.py` | 16 | **varredura automática de TODAS as rotas de escrita** com identificador inexistente (nenhuma 2xx, nenhuma 5xx) · matriz explícita A → recurso de B em 12 leituras e 15 escritas · RLS em SQL direto nas tabelas novas · funções `SECURITY DEFINER` não vazam · tabelas de chave invisíveis · rotas de administração exigem segundo fator · `DELETE` idempotente é indistinguível |
| `test_v0150_upgrade.py` | 10 | atualização v0.12.1 → v0.13.0 → v0.14.0 → v0.15.0 **com dado dentro**: dado sobreviveu · trilha íntegra · transições legadas no grafo · ODS consolidados sem referência quebrada · estruturas novas com RLS · **esquema atualizado idêntico ao criado do zero** (colunas, índices, políticas e gatilhos) |
| `test_e2e_v0150_journeys.py` | 8 | as 8 jornadas de ponta a ponta pela API real (ver abaixo) |
| `test_e2e_v0150_web.py` | 6 | navegador real: páginas novas com um `<h1>` e sem erro de console · ideia vira projeto pela interface · **bloqueio de montagem visível com o botão desabilitado** · recusa de transição mostrada · desconhecido separado de lacuna · indisponibilidade de provedor declarada na tela |
| `test_v0150_performance.py` | 7 | volume de alvo (1.000 orgs · 10.000 projetos · 100.000 documentos · 100.000 avaliações), orçamento de tempo por requisição, detector de N+1 por tamanho de página, `EXPLAIN` sem varredura sequencial |

### As 8 jornadas

1. Ideia → diagnóstico → projeto → documento montado → assinado → **verificado publicamente sem login**.
2. Projeto publicado → financiador avalia → retorno → captação → execução.
3. Organização sem dado nenhum → tudo desconhecido → preenche evidência → **lacunas fecham e a versão registra**.
4. Montagem bloqueada → completa → gerada → recusada na revisão → corrigida → aprovada → assinada com as duas camadas.
5. Acompanhamento no tempo: retratos, comparação, integridade da trilha.
6. Risco: regra aponta → equipe mitiga → encerramento com motivo.
7. Retorno humano sobre recomendação → base de calibração para a administração, **sem treino automático**.
8. Duas organizações percorrendo a mesma jornada: **nenhuma vê qualquer passo da outra**.

## O que continua NÃO testado

| Item | Por quê |
|---|---|
| Carga concorrente em ambiente dimensionado | 2 vCPU no ambiente de construção produziria número enganoso |
| Integração contra sistema externo real | depende de acesso a instância de cliente ou órgão |
| Assinatura qualificada, Gov.br, ACT, biometria, SMS | dependem de contratação; o que existe é o teste da **recusa explícita** |
| Leitura dos arquivos gerados pelo Microsoft Office e LibreOffice | os testes reabrem o ZIP e conferem o XML, mas nenhum aplicativo comercial abriu os arquivos aqui (ADR 110) |
| Leitura do QR por leitor comercial | o teste é de ida e volta pelo próprio codificador (ADR 111) |
| Teste de intrusão independente | nunca houve |

---

## Novos no v0.14.0 (96)
`tests/test_v0140_trust.py` (88) e `tests/test_e2e_v0140_trust.py` (8). Resumo do que é **provado**:
assinatura em duas camadas (sem código não assina; código morre quando o conteúdo muda; 4 tentativas simultâneas com o
mesmo código ⇒ **1** assinatura) · verificação pública sem login **sem dado pessoal no corpo da resposta nem na página
renderizada** · arquivo adulterado detectado pela recontagem do hash · revogação visível e nada apagado · cadeia de
custódia encadeada, **irreescrevível pela aplicação e pelo contexto de sistema**, com adulteração detectada no `seq`
exato · autopromoção de identidade e de credencial bloqueadas no banco · biometria, SMS e RFC 3161 **recusando** ·
acordo só vigente com todas as partes, hash congelado, parte não marca a outra · isolamento entre organizações nas
tabelas novas · cotas que não estouram nem sob concorrência · honorário sem fonte recusado · geo pública só com
consentimento · taxonomia com código inválido recusado pelo banco · catálogo de tradução com as mesmas chaves nos três
idiomas · 8 formatos de arquivo reabertos e com XML conferido · ida e volta do QR Code · tema escolhido aplicado antes do
primeiro render com contraste AA medido no navegador.

## Novos no v0.13.0 (76) — `tests/test_v0130_integrations.py`
Detalhamento por classe, o que o dublê prova e o que **não** prova: `INTEGRATION_TESTING.md`. Resumo:
ciclo de vida da conexão (9) · segurança de credencial (7) · isolamento entre organizações/IDOR (10) · mapeamento, transformações e conflito de ID externo (9) · jobs, idempotência, repetição, disjuntor e **4 trabalhadores em paralelo = 1 execução** (8) · webhooks de saída, assinatura HMAC, dead-letter e reenvio (7) · webhooks de entrada, janela de 300 s, deduplicação e **4 entradas em paralelo = 1 processamento** (6) · importação/exportação de arquivo, incluindo recusa explicada de JSON/XML e neutralização de fórmula (8) · saúde não destrutiva, painel de operação, latência e retenção (5) · segurança: SSRF (169.254.169.254), XXE, bomba XML, injeção em SOAP, mapeamento sem execução de código (5) · contrato dos 6 adapters, com o de governo **recusando agir** enquanto não autorizado (6) · jornada completa simulada e queda do sistema externo sem afetar o núcleo (2).
**Nenhum sistema externo foi chamado**: o transporte é substituído por dublê. Isto prova o nosso lado do contrato, **não** compatibilidade com Senior, TOTVS, Gov.br ou Stripe reais.

## Baseline v0.12.1 (mantida, continua passando)
### Novos no v0.12.1 (33)
**`tests/test_v0120_hardening.py` (27) — testes que tentam QUEBRAR o sistema:**
- **Varredura de autorização sobre TODAS as 475 operações** (não por amostragem): toda rota não pública recusa anônimo com 401; toda rota administrativa recusa usuária comum com 403; **toda** rota administrativa recusa administrador **sem MFA**; nenhuma rota devolve 5xx a entrada anônima/placeholder; o catálogo de rotas **confere com o OpenAPI** (475 = 475).
- **IDOR de leitura e de ESCRITA** entre organizações: chamado de outra organização não pode ser lido, respondido, avaliado nem encerrado; pedidos de teste e progresso de checklist são isolados; projeto de outra organização não vaza por UUID.
- **Concorrência real (threads):** capacidade de evento nunca estoura (2 vagas, 5 inscrições simultâneas → 2 inscritas + 3 lista de espera); certificado emitido 4x em paralelo gera **um**; voucher de uso único resgatado por 4 organizações em paralelo é aplicado **uma vez**; webhook duplicado entregue 4x em paralelo grava **uma** linha e processa uma vez; webhook sem assinatura válida nunca é gravado; decisão de trial aplicada 3x em paralelo vale **uma**.
- **Higiene de erros:** IDs malformados, travessia de caminho, JSON inválido, media type errado, campos desconhecidos e limites de paginação → 4xx tratado, nunca 5xx, com `request_id` e **sem vazar esquema, SQL, traceback ou segredo**; carga de SQL/XSS é armazenada literalmente.
- **Dinheiro e tempo:** desconto é sempre inteiro em centavos, nunca negativo, nunca maior que a base; economia anual nunca é inventada; plano sem preço **recusa venda**; prazos de SLA nascem no futuro e todo carimbo de tempo sai em ISO 8601 **com fuso**.
- **Entrega de e-mail:** falha de SMTP não consome o período do boletim e não marca o aviso como enviado (reenvia no ciclo seguinte, sem duplicar depois).
- **Regressão do desconto reservado** (ver `FINAL_TECHNICAL_BASELINE.md` §Bugs).
**`tests/test_e2e_baseline.py` (4) — jornadas de navegador que faltavam:** cadastro → confirmação → login → **Sair** (sessão encerrada de fato); área permitida × **área bloqueada pelo tipo de organização** × rota inexistente; **página Plano** (estado do teste, voucher aplicado pela interface, cancelamento que mantém o acesso já concedido); **administração com MFA real (TOTP)** → troca de organização ativa → visão geral, auditoria, CMS e fila de suporte.
**`tests/test_e2e_knowledge.py` (+2):** **contraste WCAG AA medido no navegador** em 7 páginas × tema claro e escuro; ausência de IDs duplicados, de salto de nível de cabeçalho e presença de `lang="pt-BR"`.

## Verificações estáticas e de build
`ruff check impacto tests` → **All checks passed** (`docs/evidence/ruff_v0.14.0.log`) · `tsc --noEmit` → **PASS** · `node build.mjs` → **PASS** (180 KB gzip) · `python -m compileall` → **PASS** · `migrate --check` → sem pendências e sem checksum alterado.

## Medição de desempenho (fluxos críticos, dados de desenvolvimento)
p50/p95 por requisição, servidor real: `/v1/me` 12/13 ms · `/v1/help/start` (15 detectores) 17/19 ms · `/v1/help/pending` 16/23 ms · `/v1/help/recommendations` 19/25 ms · `/v1/help/search` 24/27 ms · `/v1/documents` 7/8 ms · `/v1/projects` 9/16 ms. Consultas por requisição: 8 a 28 (inclui sessão/RLS). **Limite honesto:** volume de desenvolvimento, 1 processo — não substitui teste de carga em produção.

## Limites desta suíte (não mudaram)
Acessibilidade é verificada por **checagens próprias** (rótulos, foco, contraste, cabeçalhos, IDs, overflow), **sem axe e sem leitor de tela** — registry npm bloqueado neste ambiente. Stripe, SMTP, antivírus, S3 e IdP são **dublês**. Sem teste cross-browser, sem carga concorrente em volume de produção, sem apps móveis compilados. Qualidade da busca provada apenas nas frases testadas.

---
# TEST_REPORT — v0.12.0 (anterior)

**v0.12.0: 359 testes, 0 falhas, 0 ignorados** (290 herdados + **62** de domínio em `backend/tests/test_v0120_knowledge.py` + **7** E2E de navegador em `backend/tests/test_e2e_knowledge.py`). Log completo: `docs/evidence/test_run_v0.12.0.log` (`python3 -m unittest discover -s tests -t . -v`, PostgreSQL 16 real, servidor HTTP real, Chromium/Playwright). Lint: `ruff check impacto tests` → **All checks passed** (`docs/evidence/ruff_v0.12.0.log`); `tsc --noEmit` e `compileall` limpos.

**Domínio (62):** fluxo editorial e quatro olhos (inclusive UPDATE direto no banco), versões imutáveis, regulatório, papéis e MFA; visibilidade e sitemap; busca por sinônimos com explicação, vazio, entrada inválida e log só com hash; assistente ancorado/recusa/sem conteúdo não publicado; FAQ e votos; biblioteca (modelo→rascunho, versões, download temporário); checklists; “Comece aqui” e pendências por dados reais; suporte (ciclo, guardas, IDOR, anexos, SLA, escalonamento, recorrência, preferências); eventos (lista de espera, link privado, lembrete idempotente, presença/avaliação); academia (gabarito, progresso, certificado, revogação); captação (consentimento, honeypot, privacidade, demo, boletim duplo opt-in); pedido de teste; analytics/retenção; e-mails (uma vez, preferências, conta não verificada); seed só `demo`.
**E2E (7):** (1) visitante: busca→guia→assistente recusa→demonstração com consentimento (viewport 390 px); (2) OSC: checklist persiste, “Ajudou?”, chamado, resposta da equipe; (3) Academia: matrícula, aula, quiz reprovado/aprovado, certificado e verificação pública; (4) evento (inscrição + lista de espera) e pedido de teste ficando “Solicitada”; (5) CMS: editor com MFA cria guia, **não consegue aprovar o próprio**, revisor publica, visitante lê; (6) verificações básicas de acessibilidade (h1 único, `main`, rótulos, `lang`) em 8 páginas públicas; (7) página privada redireciona ao login.
**Limites:** verificações de acessibilidade são **próprias** (não substituem axe/leitor de tela); sem teste cross-browser; Stripe/SMTP/antivírus/S3 são dublês; sem carga concorrente nas rotas novas; auditoria de dependências (`npm audit`/`pip-audit`) **não executada** (rede bloqueada); apps móveis não testados; qualidade da busca só provada nas frases testadas.

---

# TEST_REPORT — v0.11.0 (anterior)
**v0.11.0: 290 testes, 0 falhas, 0 ignorados** (256 herdados + **34** em `backend/tests/test_v0110_monetization.py`). Log completo: `docs/evidence/test_run_v0.11.0.log` (comando: `python3 -m unittest discover -s tests -t . -v` em `backend/`, PostgreSQL 16 real).
Cobertura nova: trial (início/14 dias/FULL/avisos/cancelamento dia 1 e dia 13/FREE após o fim/anti-abuso/lembretes sem duplicar), tiers (FREE/PLUS/PREMIUM/GOV), vouchers (20%, expirado, esgotado, 100%, permanente, valor fixo), checkout com `trial_end`, webhooks (duplicado, assinatura inválida, replay, fora de ordem), mensal/anual, cancelar impede renovação e preserva histórico, upgrade/downgrade, falha de pagamento/ação requerida/portal, convênios (vagas, domínio, 2º admin, GOV, revogação), revogação de licença, isolamento entre organizações e escrita direta bloqueada no banco.
**Limite:** o Stripe é um **dublê HTTP** — prova o que a plataforma envia/decide/registra, não o comportamento da API real. **Não há E2E de navegador do fluxo de cobrança** (frontend validado por `tsc` + build). Sem linter Python.


**Resultado: 256 testes, 0 falhas, 0 ignorados** (233 herdados do v0.10.0 + 17 em `test_v0101_institutional.py` (instrumentos, perfis, trilha, mentoria, cruzamento fiscal) + 2 de rede da solução + 1 de tesauro + 3 E2E em `test_e2e_v0101.py`). Log integral: `docs/evidence/test_run_v0.10.1.log` (anteriores preservados). Ambiente: PostgreSQL 16 real, servidor HTTP real, Chromium (Playwright).

**Novo no v0.10.1:** o E2E do **painel administrativo** (antes não testado no navegador) agora roda com **login MFA real (TOTP)** e prova que verificar um instrumento sem comprovante é recusado pelo servidor e que a fila de mentoria atualiza o estado no banco. Verificações de acessibilidade são **próprias** (não substituem axe/leitor de tela).
**Verificações estáticas:** `tsc --noEmit` (frontend) e `python -m compileall` — **não há linter Python instalado** (ruff/pyflakes ausentes); não afirmar lint.
**Ainda não testado:** Android/iOS; carga concorrente das novas rotas; axe/leitor de tela; validade jurídica de catálogos/regras/trilha; qualidade da busca fora das frases testadas (conceitos novos não passaram por avaliação com usuários).

---
# TEST_REPORT — v0.10.0 (anterior, 2026-10-05)

**Resultado: 233 testes, 0 falhas** (182 herdados do v0.9.0 + 48 de `test_v0100_institutional.py` + 3 E2E em `test_e2e_v0100.py`) — log integral em `docs/evidence/test_run_v0.10.0.log` (v0.9.0 preservado em `docs/evidence/test_run_v0.9.0.log`). Descrição do ambiente do v0.9.0 (ainda válida): Banco PostgreSQL 16 **real** descartável + servidor HTTP real (uvicorn) + Chromium (Playwright) para E2E. Nada é simulado exceto onde indicado.

## Como reproduzir
```
cd backend && TEST_ADMIN_DATABASE_URL="postgresql://postgres@127.0.0.1:5432/postgres" PASSWORD_SCRYPT_N=16384 RATE_LIMIT_MULTIPLIER=1000 python3 -m unittest discover -s tests -t . -v
```
(`RATE_LIMIT_MULTIPLIER` apenas afrouxa limites para a suíte; o teste de rate limit da busca usa o limite real.)

## Evolução da suíte
v0.7.0: 111 · v0.8.0: 144 · v0.9.0: **182** (31 de domínio da Biblioteca em `test_v090_solutions.py`, 3 E2E em `test_e2e_v090.py`, ampliações em `test_architecture.py`, +1 regressão `/v1/me`).

## Cobertura da Biblioteca de Soluções (v0.9.0)
| Área | Testes (nomes reais) |
|---|---|
| Motores puros | `test_intent_parser_examples`, `test_replicability_and_evidence_never_invented`, `test_truth_labels`, `test_adaptation_rules`, `test_combine_bounds`, `test_solution_match_blocks_excluded_and_has_no_plan_input` |
| Cadastro/publicação | `test_create_defaults_and_validation`, `test_publish_gates_and_owner_only`, `test_idea_is_not_a_case_and_has_no_results`, `test_develop_idea_requires_authorization_and_human_review` |
| Verdade/confiança | `test_trust_progression_needs_accepted_evidence_and_resets_on_edit`, `test_owner_cannot_forge_trust_demo_or_verification`, `test_evidence_and_results_status_cannot_be_set_by_owner`, `test_demo_seed_is_marked_demo_and_never_proven` |
| Busca | `test_search_quality` (artes caps · arte saúde mental · arte e centro de atenção psicossocial · projeto idosos · educação rural · mulheres violência · PcD tecnologia · erro de digitação · singular/plural · filtros · penalidade), `test_search_is_plan_independent_and_log_has_no_raw_text`, `test_search_rate_limited_and_validates`, `test_aggregates_and_vocabulary` |
| Análise | `test_profile_similar_compare_adapt_combine`, `test_funder_match_and_recommendations`, `test_personalization_is_opt_in_and_deletable` |
| Intenção/fluxos | `test_view_never_creates_intent_and_events_are_deduplicated`, `test_intent_privacy_and_stage_forging`, `test_intent_stage_cannot_be_forged_in_database`, `test_requests_antispam_and_permissions`, `test_replication_flow_reviews_and_disputes` |
| Multi-tenant/RLS | `test_cross_tenant_writes_blocked`, `test_other_org_cannot_modify_or_see_drafts`, `test_append_only_and_rls_on_events_and_requests` (+ `test_every_table_has_rls` do núcleo, agora sobre 105 tabelas) |
| Admin | `test_admin_only_and_removal` |
| Regressão | `test_regression_me_works_for_platform_org` |
| E2E navegador | busca → perfil → comparar → salvar/pedir; autor cadastra; administração verifica (3 testes, sem erros de console/CSP e com verificações próprias de acessibilidade) |

## Cobertura da camada institucional (v0.10.0)
| Classe de teste | O que prova |
|---|---|
| ModelTests | catálogos publicados, natureza jurídica no cadastro (incl. coletivo sem CNPJ), perfil institucional, RLS das tabelas novas |
| QualificationTests | declarada ≠ verificada; verificar exige autoridade/número/comprovante/vigência/justificativa; só admin verifica; eventos registrados |
| DocumentStateTests | 5 estados com rótulos exatos; aprovado no antivírus ≠ validado; expirado/rejeitado |
| RuleWorkflowTests | DRAFT→REVIEW→APPROVED→PUBLISHED→ARCHIVED; criador ≠ aprovador; publicar exige fonte consultada; nova versão arquiva a anterior; tipo de requisito inválido recusado |
| EligibilityMatchTests | cinco estados; ausência de regra ⇒ PENDENTE; regra jurídica ⇒ REQUER VALIDAÇÃO PROFISSIONAL; hard blockers explicados no match; certificação declarada não satisfaz |
| MaturityBadgeTests | maturidade 0–6 com listas "pode / ainda precisa"; badges com critério, fonte, validade e aviso |
| SolutionIPTests | portão de publicação (titularidade + autorização), confidencialidade/`summary_only`, filtros, prontidão |
| StatementAndCandidatesTests | declaração só afirma o cadastrado; candidatas importam como rascunho |
| ArchitectureInstitutionalTests | rotas declaram autorização; plano não influencia match |
| E2E (Chromium) | página Instituição sem erros de console e com verificações próprias de acessibilidade; viewport de 375 px sem rolagem horizontal; cadastro exibe natureza jurídica |

**Bugs achados pelos testes e corrigidos nesta versão:** política RLS com espaçamento fora do padrão do teste de arquitetura; schema duplicado `NeedIn` (422 em necessidades de rede); portão de publicação quebrando helpers de teste; rolagem horizontal em celular (grid `1fr` sem `min-width: 0`); rótulo do campo de natureza jurídica que continha "CNPJ" e tornava o seletor ambíguo; teste instável `test_signed_tokens` (pré-existente).

**Não testado nesta versão (não afirmar):** E2E do painel administrativo institucional no navegador (exige MFA no fluxo web; a API admin é testada); carga/concorrência da avaliação de elegibilidade; axe e leitor de tela; calibração dos limiares de maturidade com dados reais; validade jurídica dos catálogos e regras.

## Bugs encontrados *pelos testes* e corrigidos
Rota literal capturada por parâmetro · perfil de financiador vazio · opt-out sem DELETE · `why` vs `why_match` · 500 em `/v1/me` da plataforma · botões ocultos no perfil · nomes acessíveis poluídos por chips.
**Teste frágil corrigido:** `test_search_quality` falhou uma vez na suíte completa porque outros módulos publicam soluções quase idênticas no banco compartilhado; a asserção de ranking passou a considerar só as soluções criadas pelo próprio teste (produto inalterado).

## Desempenho e sensibilidade (scripts reproduzíveis)
- `scripts/bench_solution_search.py` → `docs/evidence/search_perf_v0.9.0.json`: 5.000 soluções sintéticas, 54 consultas: **p50 180,6 ms · p95 473,9 ms · máx 526,8 ms** (1 processo, local, sem cache, ponta a ponta). Não é projeção de produção; sem concorrência.
- `scripts/weights_sensitivity.py` → `docs/evidence/weights_sensitivity_v0.9.0.json`: 16/16 perturbações mantêm o esperado no top 3 (pesos achatados também em 1º) ⇒ robusto no corpus sintético, **pesos não discriminados**; calibrar com dados reais.

## O que NÃO foi testado (não afirmar)
Carga concorrente · pentest/fuzzing · axe e leitor de tela · navegadores além do Chromium · dispositivos móveis reais · clamd/S3/SMTP/Stripe/IdP/provedor de IA reais · build Docker · apps Android/iOS · qualidade de relevância com usuários reais · tipos oficiais TS (typecheck offline com *shims*; CI deve validar).


## Bugs encontrados pelos testes na v0.17.0 — e cada um ensinou algo

| Defeito | Onde a suíte pegou | A lição |
|---|---|---|
| `BEGIN/COMMIT` dentro da migração 0018 | aplicação da migração | o executor já envolve cada arquivo em transação; o `COMMIT` interno acabava com ela e uma falha no meio deixaria a migração aplicada pela metade **sem rollback** |
| `guard_columns` sobre coluna derivada por gatilho | a transição legítima da própria dona voltava 403 | gatilhos disparam em ordem alfabética; guardar coluna que outro gatilho deriva rejeita a transição legítima. **Mesmo erro da v0.16.0**, cometido de novo |
| trava de visibilidade bloqueando a moderação | suspender programa público era impossível | trava que impede o abuso e o remédio ao mesmo tempo é trava mal desenhada |
| `ctx.org_id` levantando 409 na leitura anônima | GET de programa rascunho sem sessão | "selecione uma organização" em resposta a um recurso inexistente é **vazamento de existência** |
| índice único parcial conferido antes do gatilho AFTER | criar versão nova de linha de base era impossível | o índice é conferido no fim do comando, antes dos gatilhos AFTER: "fechar a versão anterior" tem de ser BEFORE INSERT |
| `try/except` sem SAVEPOINT em volta de função de banco | `ai_usage` desaparecia no COMMIT | capturar exceção de banco sem SAVEPOINT deixa a transação **abortada** e o trabalho do usuário morre em silêncio |
| o SAVEPOINT escondendo um segundo defeito meu | nada no log | trava que engole erro sem avisar é trava que mente; virou `value_ledger_record_failed` |
| mensagem do portão legal perdida pelo tratador global | a ADR-022 não chegava à API | 403 genérico protege o esquema e apaga a razão; a recusa precisa ser 422 com a mensagem |
| receita classificada pelo **nome** do provedor | suíte completa, R$ 396,00 inexistentes | coluna dizendo 'stripe' não é prova de chave ao vivo — é o que um cenário de teste escreve |
| trilha de cobrança sem permissão para a aplicação | 403 ao abrir cobrança | a saída certa foi `SECURITY DEFINER` no gatilho, não GRANT de INSERT ao app |
| `CHECK` de `billing_events` sem o estado novo | três testes da v0.11.0 | restrição nova quebra caminho antigo: o caminho antigo passou a declarar `signature_verified` |
| varredura de "coluna com dado pessoal" por substring | `subscription_id` acusado por conter "ip" | varredura que grita com nome inocente é varredura que alguém desliga |
| isolamento exigindo contagem **zero** | suíte completa | confundir "não é meu" com "não existe" acusa vazamento onde há regra (programa com visibilidade de rede) |
| documento afirmando tabela vazia | `test_v0170_docs.py` | a tabela de linhas de base tem uma linha por tipo, **sem número**. A diferença importa, e o teste que confere documento contra banco pegou minha própria afirmação falsa |

## O que NÃO foi testado na v0.17.0 (não afirmar)

| Item | Por quê |
|---|---|
| cobrança real em qualquer meio | **não há provedor configurado**: nenhuma conta, chave ou identificador de preço |
| webhook de provedor real | sem conta, o segredo de assinatura não existe; o que é testado é a rejeição e a idempotência |
| PIX e boleto de verdade | QR, copia-e-cola e linha digitável vêm do provedor |
| emissão de nota fiscal | não há provedor fiscal nem inscrição municipal |
| aceite de documento vigente **em produção** | nenhuma minuta foi aprovada; o caminho completo é exercido sobre um documento criado **dentro do teste** |
| validade jurídica das onze minutas | é trabalho de advogado(a), não de teste |
| índice de `legal_acceptances` em volume | a tabela não chega a 500 linhas no cenário, e está declarado como inconclusivo no relatório de desempenho |
