# Prontidão da liberação — v0.18.1

Este documento responde a uma pergunta por vez, com GREEN / YELLOW / RED e o motivo. Não há "parcialmente verde".

## 1. Portões de liberação

| # | Portão | Situação | Prova |
|---|---|---|---|
| 1 | Suíte completa verde, banco criado do zero | 🟢 | **1.298** testes, 0 falhas, 26 em passo próprio · `docs/evidence/test_run_v0.18.1.log` |
| 2 | Lint do backend sem apontamento | 🟢 | `ruff`, "All checks passed" · `docs/evidence/ruff_v0.18.1.log` |
| 3 | Tipos do frontend sem erro | 🟢 | `tsc --noEmit` limpo |
| 4 | Build do frontend | 🟢 | `node build.mjs` · 14 arquivos no pré-cache |
| 5 | Compilação de todo o Python | 🟢 | `python3 -m compileall impacto` |
| 6 | OpenAPI gerado do código | 🟢 | **749** operações · `docs/openapi.json` |
| 7 | Migrações só para frente, com checksum | 🟢 | **24** migrações, nenhuma liberada foi editada |
| 8 | Caminho de atualização v0.12.1 → **v0.17.0** com dado dentro | 🟢 | `test_v0150_upgrade.py` (**11** testes; o novo confere que as travas chegaram, não só as tabelas: aceite de minuta e aprovação sem revisor são recusados no banco **atualizado**) |
| 9 | Esquema atualizado **idêntico** ao criado do zero | 🟢 | `test_10_schema_matches_a_database_built_from_scratch` |
| 10 | RLS em toda tabela de dado de organização | 🟢 | **251 de 253** com política; as duas exceções são `schema_migrations` e `chain_heads`, nomeadas |
| 11 | Matriz de isolamento A → recurso de B | 🟢 | varredura automática + matriz explícita + SQL direto; na v0.17.0 a matriz passou a ser **linha a linha** nas 22 tabelas novas, com o **teste par** que falha se o filtro do próprio teste não achar nada |
| 12 | Nenhum segredo no repositório nem no ZIP | 🟢 | teste estático + varredura no empacotador |
| 13 | Jornadas de ponta a ponta | 🟢 | 8 + **7** jornadas · `test_e2e_v0150_journeys.py`, `test_e2e_v0160_journeys.py` |
| 14 | Navegador real nas telas novas | 🟡 | 6 testes cobrem as telas da v0.15.0; **as 27 telas da v0.16.0 e a camada econômica da v0.17.0 não têm Playwright** — a v0.17.0 é camada de domínio e API, sem tela nova |
| 15 | Invariantes do produto | 🟢 | 21 + **28** testes · `test_v0150_invariants.py`, `test_v0160_invariants.py` |
| 16 | Desempenho medido com volume de alvo | 🟡 | medido em duas execuções; **o feed piorou de 1,5–1,7 s para 1,87–2,04 s** e a folga caiu para 1,2× — declarado em `PERFORMANCE_REPORT.md` §7 |
| 17 | Compatibilidade: nada que existia quebrou | 🟢 | suíte inteira anterior continua verde |
| 18 | Dependência externa ausente produz recusa explícita | 🟢 | 501/estado `unavailable`, nunca sucesso falso |
| 19 | Nenhum `TODO`/`FIXME`/`MOCK`/`STUB` no caminho de produção | 🟢 | ver §3 |
| 20 | Dado de demonstração separado de dado de produção | 🟢 | ver §4 |
| 21 | Documentação da versão completa e versionada | 🟢 | **9 documentos novos** + 14 atualizados + snapshot em `history/v0.16.0/`, **e 17 testes que conferem os números dos documentos contra o banco** |
| 22 | ZIP completo, sem ZIP aninhado, validado por extração | 🟢 | `scripts/make_release.py` + `--verify` |
| 23 | **Pacote sem despejo de banco nem dado local**, garantido por teste | 🟢 | `test_architecture.ReleasePackageTests` (2 testes) |

| 24 | **SQL do código conferido por `PREPARE`** contra o esquema real | 🟢 | `scripts/sql_prepare_check.py` · 185 (rede) + 66 (econômica) + 11 (legal) consultas, 0 erros |
| 25 | **Preço nunca em literal de código** | 🟢 | `test_prices_are_not_hard_coded` lê `config/plans.json` e varre backend e frontend |
| 26 | **Nenhuma rota duplicada** (a segunda ficaria inalcançável em silêncio) | 🟢 | `test_no_duplicate_routes` |
| 27 | **Todo destino de recomendação existe no roteador** | 🟢 | `test_recommendation_links_exist_in_the_app` |
| 28 | **Datas de produto em UTC**, não no fuso do processo | 🟢 | `test_product_dates_are_utc` · `backend/impacto/clock.py` |
| 29 | Backup e **teste de restauração** com ledger íntegro | 🟢 | `scripts/backup.sh` + `scripts/restore_test.sh` executados nesta rodada |
| 30 | **Nenhuma rota pública nova sem revisão** | 🟢 | `test_handlers_declare_auth` com lista de permissão explícita (**4** rotas públicas novas na v0.17.0: feed e ficha de programa, registro legal e texto de documento) |

| 31 | **Nenhuma receita ativável sem cartão legal verde** | 🟢 | portão no banco (`monetization_rule_gate()`); 9 regras, **zero verdes, nenhuma ativa** · `test_v0170_monetization.py` |
| 32 | **Nenhum aceite de documento não revisado por advogado(a)** | 🟢 | `acceptance_stamp()` recusa; 27 testes · trava o produto **de propósito** |
| 33 | **Pagamento simulado nunca passa por real** | 🟢 | `is_simulated` derivada e irreescrevível; `platform_revenue()` com o simulado em coluna própria · 30 testes |
| 34 | **Receita real nunca inferida do nome do provedor** | 🟢 | `provider_configured` entra na apuração · `test_a_paid_invoice_with_a_real_provider_name_is_still_not_real_money` |
| 35 | **Nenhuma estimativa de tempo sem linha de base com fonte** | 🟢 | `app_record_value()` deriva; nenhuma linha de base nasce com número · 16 testes |
| 36 | **Só os pontos declarados chamam o modelo de linguagem** | 🟢 | varredura em `test_architecture`; registro de 28 motores com o que cada um nunca decide |
| 37 | **Os números dos documentos conferidos contra o banco** | 🟢 | `test_v0170_docs.py` (17 testes) — pegou três afirmações falsas minhas nesta rodada |
| 38 | **A prova de aceite sobrevive à exclusão da conta, sem o dado pessoal** | 🟢 | `acceptance_anonymize_only()`; portabilidade inclui o hash · `test_v0170_security.py` |
| 39 | **Nenhum número normalizado sem denominador declarado com fonte** | 🟢 | sete métodos, cada um exigindo o denominador; resposta "indisponível" com motivo · `test_v0180_equity.py` (30 testes) |
| 40 | **Nenhuma comparação entre projetos devolve veredito** | 🟢 | `compare()` com `comparable: false` + motivos; `verdict` sempre nulo · teste de viés com projeto remoto × urbano |
| 41 | **Carga oficial nunca confundida com conhecimento da plataforma** | 🟢 | `from_official_load`; as 27 UFs semeadas dizem "conferir na carga oficial" · `test_v0180_territory.py` |
| 42 | **A escada de referencial para em `audited`; `certified` é recusado** | 🟢 | `framework_relation_gate()` com a mensagem explicando · `test_v0180_frameworks.py` |
| 43 | **A situação da alegação não é escrevível** | 🟢 | `claims` sem coluna de situação (lido do `information_schema`); `claim_status()` deriva · `test_v0180_claims.py` (42 testes) |
| 44 | **Nenhuma alegação é classificada como fraude, e nada é automático** | 🟢 | `attention`/`serious`; revisão humana por convite de outra organização; aceitar **qualifica sem apagar** |
| 45 | **Não existe nota única de reputação, nem coluna agregada** | 🟢 | resposta sem campo agregado; `information_schema` sem coluna agregada · ADR-201 |
| 46 | **Organização nova não começa com nota baixa** | 🟢 | `insufficient_has_no_value`; `value` nulo com motivo escrito · teste de viés |
| 47 | **Nenhum sinal comercial entra em reputação ou em selo** | 🟢 | varredura AST nos dois módulos **e** no SQL da migração de selos · ADR-203 e ADR-211 |
| 48 | **Nenhuma rota concede selo sem critério** | 🟢 | critério avaliado em SQL; app sem INSERT em `seal_awards`; recusa até para o dono do banco · ADR-207 |
| 49 | **Toda sugestão de formulário declara a origem, e nenhuma sobrescreve em silêncio** | 🟢 | `origin`/`origin_label` em todas as buscas; componente que pergunta e oferece voltar · ADR-212/213 |
| 50 | **Responsabilidade registrada sem CPF e separada da assinatura** | 🟢 | nenhuma coluna de documento (lido do `information_schema`); `signature_id` opcional nos dois sentidos · ADR-216/220 |
| 51 | **Os números dos documentos desta rodada conferidos contra o banco** | 🟢 | `test_v0180_docs.py` (18 testes), incluindo "zero definições de selo embarcadas" e "zero metas de ODS carregadas" |
| 52 | **Nenhuma chave estrangeira quente sem índice** | 🟢 | achado do relatório (`materiality_assessments.project_id`) corrigido na migração 0032 · `docs/evidence/db_integrity_v0.18.1.txt` |
| 53 | **Caminho de atualização da v0.17.0 com dado dentro** | 🟢 | `test_v0181_migrations.py` (8): dado intacto, 33 tabelas com RLS, 10 funções, forward-only recusando alteração |
| 54 | **Migration que falha não deixa metade aplicada** | 🟢 | teste com migração deliberadamente quebrada em diretório temporário |
| 55 | **Concorrência: um responsável, um denominador, rodada íntegra** | 🟢 | `test_v0181_concurrency.py` (9) com 6 threads soltas ao mesmo tempo |
| 56 | **Jornada completa de ponta a ponta** | 🟢 | `test_e2e_v0181_journeys.py` (18 passos, 1 projeto, 1 trilha de auditoria) |
| 57 | **Smoke de publicação executável** | 🟢 | 20 verificações; 0 falha obrigatória; provedor simulado **declarado** |
| 58 | **Acessibilidade medida no navegador** | 🟡 | 12 verificações verdes (contraste calculado nos 2 temas, teclado, foco, 390 px, toque ≥ 24 px); **axe e leitor de tela: NOT VERIFIED** |
| 59 | **Carga concorrente sem erro** | 🟡 | 12 threads, 3.207 req, 160 rps, **0 erro**; mesma máquina — **não** é capacidade de produção |
| 60 | **Auditoria de dependências** | 🔴 | **BLOCKED BY ENVIRONMENT** (npm 403, PyPI indisponível), com a saída em `SECURITY_AUDIT.md` §0. Controles offline verificados; nenhuma afirmação sobre CVE |
| 61 | **Imagem Docker construída e executada** | 🔴 | `Dockerfile` correto na leitura (não-root, `--no-server-header`); **docker indisponível neste ambiente** |
| 62 | **Observabilidade com coletor e alertas** | 🔴 | `/metrics` e logs estruturados existem; **ninguém lendo** — 9 alertas mínimos no runbook §5 |
| 63 | **Provedores externos reais** | 🔴 | SMTP, S3, antivírus, pagamento, fiscal e IdP em modo simulado — e o `/readyz` **diz isso** |
| 64 | **Aprovação jurídica das 11 minutas** | 🔴 | o banco recusa aceite de rascunho (ADR-187): sem aprovação, cadastro travado em produção, de propósito |

Portões 31 a 38 são da v0.17.0. O 37 nasceu de um achado embaraçoso: o documento do Value Ledger afirmava que a
tabela de linhas de base "nasce vazia", e ela nasce com uma linha por tipo **sem número**. A diferença importa, e
nenhuma revisão humana pegaria — o teste pegou.

Portões 24 a 30 são da rodada anterior. O 24 nasceu de um achado real: a revisão de código **não** pegava nome de coluna
errado, e cinco defeitos só apareceram quando o SQL passou a ser conferido por `PREPARE`.

Portão 23 foi acrescentado depois de um achado real: `backups/` não estava excluído do empacotamento, e o despejo do banco de desenvolvimento entraria no ZIP na próxima construção. Corrigido no `.gitignore`, no empacotador e com teste.

## 2. Veredito por camada

| Camada | Veredito | Observação |
|---|---|---|
| Banco e integridade | 🟢 | `DATABASE_INTEGRITY_REPORT.md` |
| Núcleo do produto (6 motores) | 🟢 | `CORE_PRODUCT_ARCHITECTURE.md` |
| API | 🟢 | **749** operações, contrato estável, erro RFC 7807 |
| Segurança da aplicação | 🟢 | `SECURITY_FINAL_CHECKLIST.md` §1–8 |
| Validação de segurança por terceiro | 🔴 | **nenhuma** — nunca houve teste de intrusão independente |
| Chaves e cifragem | 🟡 | funciona e é auditado; **KMS/HSM não existe** e isso está declarado |
| Assinatura digital | 🟡 | avançada funciona; **qualificada (ICP-Brasil) e Gov.br indisponíveis** |
| Integrações externas | 🟡 | o mais maduro é `contract_tested`; **nenhuma em produção real** |
| Desempenho | 🟡 | caminhos da rede entre 9 e 82 ms; camada econômica entre 1 e 43 ms; workspace da OSC 451–497 ms; **feed do financiador 1,87–2,04 s** — limite declarado na resposta |
| Frontend funcional | 🟢 | sem erro de console, um `<h1>` por página, caminhos críticos testados no navegador |
| Frontend visual | 🔴 | **não existe camada de design** — é propositalmente a próxima etapa; e o pacote "Convergência" **não foi recebido** (`DESIGN_HANDOFF_FINAL.md` §1) |
| Mobile nativo | 🔴 | não iniciado; PWA funciona (`STORE_READINESS.md`) |
| LGPD | 🟡 | matriz de retenção escrita, direitos do titular funcionam; **RIPD e DPO pendentes** |
| Benefício fiscal | 🟡 | motor funciona; tabelas nascem **vazias** e exigem fonte, URL e data |

**Nenhum 🔴 é de engenharia interna.** Os três são: validação externa que não foi contratada, design que é a etapa
seguinte, e aplicativo nativo que não foi iniciado.

## 3. Limpeza de arquitetura

| Verificação | Resultado |
|---|---|
| `TODO` / `FIXME` em `backend/impacto` | **0** |
| `MOCK` / `STUB` / `FAKE` em caminho de produção | **0** (os duplos de teste estão em `backend/tests`, onde devem estar) |
| `except Exception` em `backend/impacto` | **35 ocorrências, todas com comentário dizendo por quê**. 11 relançam depois de limpar (apagar objeto órfão, desfazer transação, devolver vaga do pool). 24 devolvem valor seguro de propósito, em três famílias: (a) recurso **opcional** falhou e o fluxo principal continua — OCR, extração de texto, resumo por IA, busca auxiliar da Central; (b) entrada **malformada** é entrada inválida, não erro do servidor — hash legado, token, corpo JSON; (c) efeito **secundário** não pode derrubar o principal — envio de e-mail, camada institucional no match, registro de analytics, adaptador de integração (que registra a falha na própria conexão). Nenhuma das 24 esconde falha do caminho crítico: todas registram ou expõem o estado. |
| `except` com `pass` nu | 1 ocorrência, **justificada em comentário** (`migrate.py`): `ROLLBACK` de melhor esforço, com a exceção original relançada em seguida |
| Rota duplicada | **0** (conferido no registro de rotas) |
| Rota sem declaração de autenticação | **0** (`test_handlers_declare_auth`, com lista fechada de rotas públicas) |
| Uso de contexto de sistema fora dos módulos revisados | **0** (`test_system_context_only_in_allowed_modules`, lista explícita) |
| Importação de cobrança por módulo de match/diretório | **0** (`test_match_and_directory_never_import_billing`) |

## 4. Dado de demonstração × dado de produção

| Tipo | Como é separado |
|---|---|
| **Dado de referência** (planos, ODS, catálogo de indicadores, provedores de integração, provedores de assinatura, modelos de documento, traduções) | sincronizado por `sync_reference_data` em toda migração; é dado do produto, não demonstração |
| **Dado de demonstração** | só por `impacto.seed_dev`, que **não roda** em staging nem produção; soluções de exemplo têm a coluna `is_demo` |
| **Conteúdo editorial** | fluxo rascunho → revisão → aprovado → publicado, com quatro olhos; nada é publicado por migração |
| **Regras fiscais** | nascem em `draft`, exigem **duas** aprovações distintas e fonte com URL e data |
| **Tabelas de honorários** | nascem **vazias**; exigem fonte, URL e data de publicação |

A validação de configuração **recusa a subida** em staging/produção com `MAIL_PROVIDER=console` ou
`BILLING_PROVIDER=sandbox`.

## 5. O que esta liberação NÃO entrega

Lista fechada, para que ninguém descubra depois:

1. Assinatura qualificada (ICP-Brasil) e assinatura via Gov.br — ambas `unavailable`, recusadas no banco.
2. Carimbo de tempo com validade externa (RFC 3161) — 501 explícito.
3. Verificação biométrica de identidade e confirmação por SMS — 501 explícito.
4. Qualquer integração exercitada contra sistema real de cliente ou órgão.
5. KMS/HSM.
6. Camada de design.
7. Aplicativo nativo em loja.
8. Teste de intrusão independente.
9. RIPD e DPO nomeado.
10. Operação em múltiplas instâncias com armazenamento local.
11. Desempenho verificado sob concorrência em ambiente dimensionado.
12. Feed do financiador abaixo de 1 s sem filtro, em base de 10.000 projetos.

**Acrescentado na v0.16.0:**

13. **Cobrança real.** Não há conta no provedor, chave, nem preço criado. `provider_price_id` é nulo e o checkout
    responde 503 `provider_price_missing` em vez de tentar com valor inventado. Toda a camada da plataforma —
    versão de preço, vigência, aviso de 30 dias, aceite registrado, cotação, imposto, idempotência de webhook —
    está pronta e testada.
14. **O pacote de Design System "Convergência"**, que não foi recebido: as seções que dependiam dele não foram
    executadas, e nada foi inventado no lugar (`DESIGN_HANDOFF_FINAL.md` §1).
15. **Navegação horizontal retrátil com área de trabalho ampla**, pedida em rodada anterior: é entrega de design, e
    está especificada item a item em `NAVIGATION_MODEL.md`.
16. **E2E de navegador nas 27 telas novas** e verificação de viewport/contraste nelas.
17. **Push nativo no aparelho.** A notificação existe dentro do produto (14 grupos, fan-out para a equipe); FCM e
    APNs não existem.
18. **Exportação de dados pessoais cobrindo as entidades novas da rede** — decisão jurídica antes de técnica.
19. **Logotipos oficiais dos ODS.** Número, nome e cor oficial estão em `sdg_goals`; a arte depende de autorização
    de uso de marca.
20. **Decisão sobre compra dentro do app** (Apple/Google) — comercial e jurídica, do proprietário.

**Acrescentado na v0.17.0:**

21. **Nenhuma receita ativa.** Nove regras cadastradas, **zero verdes**: cinco esperam parecer jurídico e quatro
    são recusadas (success fee, take rate de marketplace, cobrança automática de órgão público e venda de dado
    agregado). O portão está no banco, não na interface.
22. **Nenhum aceite de documento legal é registrável.** As onze minutas são minutas; o banco recusa registrar
    aceite de documento não aprovado por revisor nomeado. **Isto trava o produto de propósito**, e destravar é
    contratar revisão jurídica, não programar.
23. **Nenhum provedor de pagamento configurado.** Sem conta, chave, identificador de preço ou segredo de webhook.
    Toda a camada da plataforma — máquina de estados, trilha, parcelamento, instrução de PIX e de boleto,
    idempotência e reconciliação — está pronta e testada; **nenhuma cobrança real foi processada**.
24. **Verificação de assinatura de webhook contra provedor real.** O caminho está implementado e testado contra
    assinatura **inválida**; contra assinatura válida de provedor real, não há como testar aqui.
25. **Emissão de nota fiscal.** Sem provedor fiscal, sem inscrição municipal, sem código de serviço definido.
26. **SLA de disponibilidade.** Nenhum número foi medido em operação real nem contratado com fornecedor de
    infraestrutura; as minutas dizem isso em letras em vez de prometer um percentual.
27. **Preço institucional (B2B, B2G, Enterprise, implantação).** Não está declarado em lugar nenhum do sistema,
    porque é decisão comercial do proprietário.
28. **FASE 15 (implantação) e FASE 16 (teste de fumaça em produção) do roteiro desta rodada**, que **não são
    executáveis neste ambiente**: não há domínio, credencial de nuvem nem saída de rede além dos registros de
    pacote. Estão declaradas, não puladas em silêncio.
29. **Qualquer estimativa de tempo economizado.** Nenhuma linha de base tem número declarado com fonte, data e
    método — então o produto registra as contagens (que são verdade) e devolve a estimativa nula.
30. **Logotipos oficiais dos ODS** e **camada de design**: continuam pendentes, e o design é a próxima fase.

## 6. Para subir

`DEPLOYMENT_CHECKLIST.md` tem o procedimento. O mínimo:

```bash
# 1. banco
MIGRATION_DATABASE_URL=... python3 -m impacto.db.migrate          # aplica as 15, com lock e checksum
MIGRATION_DATABASE_URL=... python3 -m impacto.db.migrate --check  # falha se sobrou pendência

# 2. configuração (a validação recusa a subida se algo essencial faltar)
#    obrigatório em produção: DATABASE_URL, SECRET_KEY, MAIL_PROVIDER=smtp + SMTP_*
#    recomendado: FIELD_ENCRYPTION_KEY, STORAGE_PROVIDER=s3 + S3_*, ANTIVIRUS_PROVIDER=clamd

# 3. frontend
cd web && node build.mjs

# 4. depois de subir
POST /v1/admin/encryption/keys {"purpose": "field"}   # registra a chave em uso no inventário
GET  /v1/admin/encryption/keys                        # confere impressão digital e estado
GET  /v1/signature-providers                          # confere que só platform_advanced está em produção
```

## 7. Veredito

A versão está **tecnicamente pronta para receber a designer**: a rede de impacto está fechada, a camada econômica,
legal e de pagamento está implementada e travada, nada do que já existia quebrou, o caminho de atualização está
testado com as travas dentro, não há 🔴 de engenharia interna e todo limite está declarado em documento e, quando
cabe, na própria resposta da API.

**O que esta rodada mudou no veredito, e é importante ler:** os bloqueios que restam para faturar **não são
técnicos**. Falta parecer jurídico (cinco receitas amarelas e onze minutas), falta provedor de pagamento contratado
e configurado, falta contador para nota fiscal. A engenharia fez o que lhe cabia: construiu a camada inteira e a
deixou **desligada**, com o motivo de cada desligamento escrito no banco, na API e nos documentos. Ligar não é
programar.

Um limite que vale repetir no veredito: o pacote de Design System **não chegou**, então as seções que dependiam
dele não foram executadas. O que foi feito no lugar é o insumo que ele consome — a arquitetura da informação e o
modelo de navegação, em `INFORMATION_ARCHITECTURE.md` e `NAVIGATION_MODEL.md`.

Para **produção com cliente pagante**, falta o que está em §5 — e nada disso é surpresa: está escrito aqui, em
`EXTERNAL_DEPENDENCIES.md` e em `HOMOLOGATION_MATRIX.md`.
