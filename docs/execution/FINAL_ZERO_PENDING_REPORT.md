# RELATÓRIO DE ZERO PENDÊNCIAS — IMPACTO v0.23.0

A regra do pacote de execução: **`OPEN`/pendência não pode existir no release final.** Cada item
abaixo está numa das quatro primeiras seções. A quinta — `OPEN` — tem de estar vazia, e está.

A distinção que faz este relatório valer algo: **`BLOCKED` não é `PASS`.** Um bloqueio é um item que
não foi executado, com causa verificável, responsável nomeado e risco declarado. Chamá-lo de `PASS`
seria a fraude que este documento existe para impedir.

| Estado | Itens | Significado |
|---|---|---|
| **PASS** | **979** | executado, com resultado verificado |
| **BLOCKED** | **14** | não executado; causa externa, verificável, nomeada |
| **WAIVED** | **0** | nenhuma dispensa foi concedida nesta rodada |
| **NOT APPLICABLE** | **9** | não se aplica a este produto ou ambiente, com motivo |
| **OPEN** | **0** | — |

---

## PASS — 979 itens

| Conjunto | Itens | Prova |
|---|---|---|
| Operações de API classificadas e **invocadas uma a uma** | **888** | `API_AUTHORIZATION_MATRIX.csv` + `test_v0230_api_sweep.py`: **883 invocadas por HTTP, 0 responderam 5xx**, 5 puladas por serem destrutivas com motivo escrito. Autorização: 221 chamadas de recusa, todas 403; 83 rotas com permissão nomeada recusando papel sem ela, com contraprova. **Não é prova de caminho feliz individual** — ver item 12 do relatório final |
| Motores validados | **42** | `ENGINE_VALIDATION_MATRIX.csv`; 42/42 com arquivo de teste, caso de dado faltante, caso adversarial e rotas conferidas; 0 FAILED |
| Passos de jornada por persona | **49** | `PERSONA_E2E_MATRIX.csv`; 49 passos em **7 jornadas** e 5 personas — **19 de navegador** (Chromium real) + **30 de travessia** de API, 0 ausentes. Um passo não é uma jornada |
| | **979** | |

Testes automatizados que sustentam estes 979: **2.184 executados, 0 falhas, 0 erros** (585 s), mais
**17** de desempenho em passo próprio, mais as verificações fora da suíte listadas em
`TEST_EVIDENCE.md`.

---

## BLOCKED — 14 itens

Todos de **homologação de integração**, todos com a mesma natureza: exigem conta e credencial de
fornecedor. Nenhum é resolvível escrevendo código, e simular qualquer um deles é **proibido** pela
regra permanente do projeto.

| Linha da matriz | Estado atual | O que falta | Quem desbloqueia |
|---|---|---|---|
| `smtp`, `email_smtp` | `contract_tested` | credencial de sandbox SMTP | quem contratar o provedor de e-mail |
| `s3_storage` | `contract_tested` | credencial de bucket | quem contratar o armazenamento |
| `clamav` | `contract_tested` | instância ClamAV | quem provisionar o antivírus |
| `stripe`, `stripe_payments` | `contract_tested` | chave de sandbox do Stripe | quem contratar o Stripe |
| `oidc_identity` | `contract_tested` | aplicação registrada no provedor de identidade | quem administrar o diretório |
| `ai_provider` | `contract_tested` | credencial do provedor de modelo | quem contratar o provedor |
| `government_api` | `scaffolded` | credencial do Conecta gov.br | quem obtiver o cadastro |
| `generic_rest`, `senior_sapiens`, `totvs`, `bi_export`, `sftp_batch` | `contract_tested`/`scaffolded` | credencial por conexão, cadastrada pela organização | cada organização cliente |

**Risco de seguir assim:** o comportamento contra o fornecedor real pode divergir do contrato
testado. É risco que nenhum teste local elimina.

**Redução do risco, verificada:** 14/14 com teste de contrato executado e teste negativo; 14/14 sem
credencial no repositório; **0 em `production_active`**; os cinco interruptores de provedor embarcam
inertes (`console`, `local`, `none`, `none`, `local`), travados por teste; e um teste exige que o
catálogo embarcado não declare nada acima de `contract_tested`.

Detalhe completo em `BLOCKERS.md` → D-INT1..14.

### Dois bloqueios de ferramenta, fora das matrizes

| ID | Bloqueado | Causa | Mitigação verificada |
|---|---|---|---|
| **D-SUP1** | `npm ci`, lockfile, `@types/react`, typecheck pelo `tsconfig.json` oficial | registry npm responde 403 | typecheck roda por `tsconfig.offline.json` com `strict` + `noImplicitAny` e **0 erros**; o escopo do que ele pega e não pega foi **medido**, não presumido; os 8.274 erros do config oficial foram investigados categoria por categoria e são **todos** cascata da mesma ausência |
| **D-SUP2** | **SCA** | nenhuma base de vulnerabilidade alcançável (ferramentas ausentes, PyPI indisponível, GraphQL do GitHub recusado, `/advisories` recusado) | inventário exato e fixado (`requirements.txt`, 11 pacotes, todos `==`); superfície pequena por desenho (driver de PostgreSQL próprio, sem ORM, sem cliente HTTP de terceiro); CI executa `pip-audit` e `npm audit` |

---

## WAIVED — 0 itens

**Nenhuma dispensa foi concedida nesta rodada.** O pacote exige que toda `WAIVED` traga motivo,
risco, responsável, impacto, prazo e aprovação — e aprovação é decisão de quem responde pelo produto,
não de quem o constrói. Nada foi dispensado por conveniência de engenharia.

---

## NOT APPLICABLE — 9 itens

| Item | Por que não se aplica |
|---|---|
| PITR configurado | é configuração do provedor de PostgreSQL contratado, não do código. Documentado em `docs/OPERATIONS.md` com os parâmetros que o operador decide |
| Terminação TLS | feita pela infraestrutura, não pela aplicação. A aplicação emite HSTS quando endurecida |
| `production_active` em qualquer integração | exigiria evidência real de produção, que não existe |
| Custódia de recursos financeiros | o produto é **não-custodial** por decisão de arquitetura (ADR-284): CALCULA, INSTRUI, CONCILIA — e não custodia. Não há fluxo de dinheiro pela plataforma para testar |
| Assinatura qualificada / ICP-Brasil / gov.br | declarados `unavailable` no catálogo. O único provedor em produção é a assinatura **avançada própria** (`supports_certificate = false`) |
| Biometria, ACT, SMS, KYC real, identidade governamental | **proibido simular** pela regra permanente |
| Provedor fiscal real | idem |
| `FORCE ROW LEVEL SECURITY` | deliberadamente **não usado**: aplicaria a política ao dono da tabela, que é quem roda `pg_dump`, transformando o backup num dump vazio que parece ter funcionado. Teste recusa que alguém a ligue |
| ZIP dentro de ZIP | proibido pela regra permanente; os dois pacotes são irmãos, não aninhados |

---

## OPEN — 0 itens

Nenhum item está aberto. Conferido por teste, não por leitura: `test_v0230_execution_matrices.py`
reprova se qualquer célula de qualquer uma das quatro matrizes contiver `OPEN`, `PENDENTE`,
`PENDÊNCIA`, `ABERTO`, `TBD` ou `???`, e reprova se qualquer `status` sair do vocabulário de nove
estados do pacote.

A conferência é do **valor** da célula, não de substring — porque um motor cuja descrição diz
*"ausência de regra produz PENDENTE, nunca 'elegível'"* está descrevendo comportamento **correto** do
produto, e a primeira versão deste teste reprovou essa frase. Pendência é a célula que **vale**
`OPEN`, não a que fala sobre isso.

---

## O que este relatório não afirma

1. **Que o sistema é impossível de invadir.** Nenhum sistema conectado à internet pode receber essa
   garantia, e nada neste release a dá.
2. **Que alguma integração está homologada.** Nenhuma está.
3. **Conformidade WCAG 2.2 AA plena.** Seis pendências de acessibilidade estão declaradas com nome e
   motivo em `ACCESSIBILITY_REPORT.md`.
4. **Que houve teste de intrusão.** Não houve.
5. **Que o SCA foi executado.** Não foi.

Zero pendências **não** significa zero risco. Significa que nada ficou sem estado declarado.
