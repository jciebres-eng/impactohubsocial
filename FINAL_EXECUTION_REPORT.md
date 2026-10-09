# Relatório final de execução — IMPACTO v0.27.0

**Data:** 08/10/2026 · **Ramo:** `main` · **Tag:** `v0.27.0` (a criar no GitHub pelo proprietário no
commit indicado em §3 — o proxy deste ambiente recusa envio de tag) · **Pacote:**
`IMPACTO_TRUST_FINAL_RELEASE_0.27.0.zip` (SHA-256 no `.sha256` ao lado) · **Auditoria:**
`FINAL_EXECUTION_AUDIT.md`

## 1. Executive Summary

A rodada retirou a assinatura do modelo econômico e fez o IMPACTO valer por **estar nele** — sem
fintech dentro do produto (ADR-284) e sem inventar preço, parecer, integração ou publicação:

- **Não existem mais assinaturas (ADR-341).** Sem plano pago, trial, checkout, reajuste, paywall ou
  cobrança recorrente. Cada ocorrência foi inventariada e classificada KEEP / MIGRATE / DEPRECATE /
  DELETE antes de qualquer remoção; tudo o que caiu foi arquivado em `legacy_subscription_archive`.
  Planos viraram **pacotes de capacidades**, obtidos por concessão, convênio, voucher de concessão,
  licença ou contrato avulso/parcelado.
- **A receita nasce da operação financiada.** 5% do valor financiado = **3,5%** taxa de serviço da
  plataforma + **1,5%** participação de autoria do proponente — só quando contratualmente elegível,
  nunca automática, nunca dominante. Percentuais do catálogo versionado (`economic_rules`, Pricing
  Version 2027.02), congelados no acordo, recusados se vierem do cliente (422).
- **Um aporte só, direcionado.** A matriz de distribuição (imutável, com hash, soma fechada por
  CHECK) diz quem recebe, quanto e para qual **chave PIX informada no contrato**; a transferência é
  registrada por quem paga e confirmada por quem recebe; instrução ≠ custódia (ADR-343).
- **Reconhecimentos só na quitação** (entregas aceitas + repasses devidos confirmados); trajetória
  pública cumulativa em contagens e datas, nunca valores; nada se ganha por pagar a plataforma.
- **Torre MASTER** (`/controladoria/torre`): GMV × camada registrada/devida/paga, participação,
  marketplace sem percentual, uso, contratos, a receber, **banco: DADO FINANCEIRO NÃO CONECTADO**,
  captura de valor NÃO MEDIDA sem denominador. **GMV ≠ receita**, provado. Receita real desta
  instalação: **R$ 0,00**.
- Cartões do dia, selos e trajetória na página inicial e no perfil público; simulação de 24 meses
  derivada de hipóteses declaradas (documento = gerador, conferido por teste).
- Tudo provado por HTTP e PostgreSQL reais (`test_v0270_economy`, `test_v0270_no_subscription`,
  `test_v0270_financial_model`), pela jornada "Caminho dourado" (15 jornadas, 244 passos, 0 falha),
  pelas 221 telas no Chromium por perfil (805 visitas, 0 falha) e pela regressão completa, cuja
  primeira passagem acusou 23 falhas e 2 erros — todos com causa e correção escritas (auditoria §7),
  nenhum resolvido afrouxando teste.

**Decisão: GO WITH CONDITIONS** (§27).

## 2. Version

0.27.0 — `VERSION`, `backend/pyproject.toml`, `web/package.json`, `web/package-lock.json`,
`README.md`, `docs/openapi.json`. Documentos da v0.26.0 preservados em `history/v0.26.0/`.

## 3. Commit

Commits da rodada (sobre `014c83f`, v0.26.0): `bdde94b` (F3–F6: migração 0067, backend sem
assinatura, camada econômica, torre MASTER, cartões do dia, telas, testes, documentos), `d781943`
(correções da primeira regressão, matrizes regeneradas, snapshot `history/v0.26.0/`, versão 0.27.0,
CHANGELOG), `0a44b31` (fechamento: auditoria, relatório, notas de versão, `test_v0270_release_docs`,
evidência da regressão), `a94475c` (manifestos), `881ece9` (empacotador passa a incluir toda evidência
`.log` versionada) e o **commit final dos manifestos**, para o qual a tag `v0.27.0` deve apontar e do
qual o pacote é construído byte a byte (`verify_package_against_git.py`); o hash desse commit é
registrado no `.sha256` do pacote e não cabe dentro do próprio commit. `FINAL_RELEASE_MANIFEST.json`
registra `881ece9` como último commit de conteúdo.

**GitHub Actions:** primeira run no commit `ec0e926` (`37861052570`): `auditoria` verde; `backend`,
`docker` e `pilha-do-zero` vermelhos por duas causas, ambas corrigidas no commit seguinte — um achado do
gitleaks já revisado (texto da matriz de homologação, sem valor) e um `DemoRow` sem uso que escondia uma
regressão real (painel de demonstrações sem tela; restaurado em `/admin/central/parcerias`). Detalhe em
`FINAL_EXECUTION_AUDIT.md` §7. O resultado da run do commit final **não é afirmado aqui**: é conferido no
GitHub depois do envio.

## 4. Architecture Status

Starlette + PostgreSQL 16 com RLS em 323 das 324 tabelas (a exceção é `schema_migrations`; 675
políticas; nenhuma com FORCE), hash encadeado em auditoria/razão/valor/confiança, sem custódia.
Mudanças: sete tabelas de assinatura/trial/preço removidas (arquivadas), `legacy_subscription_archive`
nova, `org_commercial_state` e `charge_requires_authorization` reescritas, `economics/master_tower.py`
e `network/today.py` novos, `services/billing.py` removido. Documento canônico do modelo:
`docs/ECONOMIC_MODEL.md`; inventário: `docs/execution/SUBSCRIPTION_INVENTORY.md`.

## 5. Engines Status

48 motores (45 + `economic_layer`, `master_tower`, `today_cards`): implemented/integrated/tested
48/48; `MOTOR_COVERAGE_MATRIX.md` (gerado) VERDE 35 · AMARELO 13 (motores de leitura sem rastro
durável ou sem rota própria, por desenho, com motivo listado) · VERMELHO 0. `ENGINE_COVERAGE.md`,
`docs/execution/ENGINE_VALIDATION_MATRIX.csv`.

## 6. Contract Intelligence

PASS (v0.26.0, estendido): o acordo de FINANCIAMENTO recebe do catálogo `platform_fee_bps`,
`proponent_participation_bps` e `economic_rule_version`; mudar o contrato cria versão nova e
**estorna** as instruções abertas no livro econômico (`reversal` obrigatório). Prova:
`test_v0260_contract_rules`, `test_G_changing_the_contract_after_funding_creates_a_new_version_and_reverses_open_instructions`.

## 7. Match

PASS (inalterado): explicado critério a critério. **Nenhum** pacote, voucher, convênio ou contrato
altera match, elegibilidade ou ranking (`test_plan_has_no_effect_on_match_architecture`;
`test_architecture`: motores não importam `billing`/`entitlements`/`voucher`). Sem pay-to-rank.

## 8. Diagnostic

PASS (inalterado): `diagnostic-engine@1.0.0`, 8 dimensões. Não tocado.

## 9. Equity

PASS (inalterado): sem nota única, denominador com fonte. Não tocado.

## 10. Evidence

PASS: a quitação exige entrega **aceita por outra parte** E repasse confirmado por quem recebe; o
reconhecimento só nasce daí (`test_golden_path_settles_the_operation_and_grants_recognition_only_then`,
`test_B_an_operation_is_not_settled_until_every_due_payout_is_confirmed_by_the_recipient`).

## 11. Responsibility

PARTIAL (inalterado): atribuição formal continua opcional.

## 12. Reputation

PASS: a projeção pública ganha `trajectory` cumulativa (operações quitadas, financiamentos quitados,
participações pagas — contagens e datas, nunca valores), reconstruída a cada reconhecimento
(`network/profiles.py`, `TrajectoryCard` em `/p/:slug`).

## 13. Seals

PASS: selos e reconhecimentos **só na quitação** (`operation_settled`, `funding_settled`,
`participation_paid`); nunca por pagar a plataforma, plano ou voucher; `/v1/me/today` lista os selos
da organização a partir de registros (`test_cards_and_badges_come_from_records_and_sell_nothing`).

## 14. Government Data

Inalterado (v0.26.0): torre territorial com k-anonimato ≥ 3. Dados do IBGE/ODS oficiais continuam
fora (rede do ambiente).

## 15. Marketplace

Inalterado: comissão recusada (ADR-022/178). A torre MASTER mostra o marketplace **sem percentual**
(contagem de contratações; receita = 0 por desenho).

## 16. Payments

PASS / BLOCKED_EXTERNAL: compromisso → desembolso → confirmação → despesa → evidência (sem custódia)
inalterado; **instruções de repasse** por linha da matriz (`allocation_payouts`) e **transferências**
registradas/confirmadas/recusadas/conciliadas pelas partes (`payout_transfers`), idempotentes por
referência, soma limitada à linha, estados com gatilho. Cobrança própria (`platform_charges`) só com
autorização (contrato aceito ou acordo assinado pelo pagador — ADR-342). **Nenhum pagamento real**:
sem provedor, sem banco, `PLATFORM_PIX_KEY` vazia → "NÃO CONFIGURADA".

## 17. Distribution

PASS: `agreement_allocations` — bruto, projeto, plataforma (3,5%), proponente (1,5% dividido pelas
frações aceitas, resto na última), terceiros; `fee_mode` deducted/additional; hash; soma fechada por
CHECK (R$ 100.000 → 95.000 / 3.500 / 1.500; centavos fecham em valores quebrados, resto ao projeto).
Sem escrow, sem carteira, sem saldo.

## 18. Billing

MIGRATE: não há cobrança por acesso. Oferta comercial = **contrato** avulso/parcelado criado por
quem tem `finance.approve`, com valor e razão; aceite autorizado concede o pacote (`entitlement_grants`
origem `contract`); revogar revoga. Licença manual: `POST /v1/admin/organizations/{id}/license`.
`GET /v1/billing` responde acesso/estado/contratos/avisos — `no_subscription`.

## 19. Fiscal

BLOCKED_EXTERNAL (inalterado): NFS-e não implementada e sem provedor; plano de contas renomeado
(4.1 receita da camada econômica da operação; 2.2.1 taxa instruída e não quitada).

## 20. Vouchers

PASS/DEPRECATE: vouchers de **concessão** (`grant_plan`, `grant_feature`, `free_period`) continuam
(`/v1/vouchers/redeem`, `/conta/acesso`); vouchers de **desconto** aposentados — criação recusada
pelo schema, resgate legado 409 `voucher_type_retired`; desconto de convênio recusado (422
`discount_retired`).

## 21. Identity

PARTIAL (inalterado): biometria, KYC, gov.br BLOCKED_EXTERNAL; nada simulado.

## 22. Security

Revisada: RLS em toda tabela nova; nenhuma FORCE; rotas de PIX/transferência/confirmação/recusa/
conciliação exigem `OWNER`; confirmação da linha da plataforma exige `billing.write`; nenhuma cobrança
própria real sem autorização; contexto de sistema restrito; nenhum segredo, chave PIX real ou
credencial em código/documento/pacote (`secrets_scan.py`, gitleaks no CI). **Nenhum sistema ligado à
internet é "impossível de invadir", e este não é exceção.**

## 23. LGPD

Inalterado no desenho; novidades respeitam-no: `legacy_subscription_archive` só para `app_priv`;
`economic_events.org_id` anonimizável e `recognitions` append-only em `data_retention.json`; a
trajetória pública publica contagens e datas, nunca valores nem chaves PIX; a torre MASTER é só da
administração com `finance.read`.

## 24. Tests

```text
PRIMEIRA REGRESSÃO COMPLETA (código novo, antes das correções): 2.250 testes — 23 falhas, 2 erros, 26 pulados
  → causas e correções em FINAL_EXECUTION_AUDIT.md §7 (1 defeito real de interface: botão "Dispensar";
    1 endurecimento real: rotas financeiras só OWNER; o resto: contagens, matrizes e sobras da assinatura)
SEGUNDA REGRESSÃO COMPLETA (após correções, docs/evidence/test_run_v0.27.0.log):
  Ran 2285 tests in 1890.687s — 0 erro, 29 pulados (dependem de credencial), 4 falhas, TODAS de fechamento:
    2× test_v0230_execution_matrices (ENGINE_VALIDATION_MATRIX.csv e INTEGRATION_HOMOLOGATION_MATRIX.csv
       citam os módulos de teste por nome; o módulo novo test_v0270_release_docs.py nasceu depois da geração),
    test_v0230_release_gate.test_the_manifest_exists_for_this_version (manifesto é gerado no fechamento),
    test_v0230_release_gate.test_the_openapi_document_carries_the_same_version (openapi regenerado no fechamento).
  Matrizes, openapi e manifesto regenerados em seguida; os portões de fechamento reexecutados verdes
  (saída anexada ao fim do mesmo log).
MÓDULOS NOVOS: test_v0270_economy (15) · test_v0270_no_subscription (10) · test_v0270_financial_model (4) · test_v0270_release_docs (12)
JORNADAS: 15 jornadas, 244 passos, 0 falha · TELAS: 805 visitas, 221 rotas, 0 falha · TELEFONE: 236 telas, 0 falha
LINT: ruff 0 · BUILD: esbuild ok · TYPECHECK: no CI (npm ci)
```

Testes que fixam contagem foram atualizados com a razão escrita ao lado (895 operações, 220 de
plataforma, 85 com permissão, 221 telas, 48 motores, 15 tipos de evento de valor, 10 regras):
ADR-340. `test_v0160_billing.py` foi removido junto com o módulo que testava (a assinatura não
existe mais — decisão do proprietário, documentada); nenhum outro teste foi enfraquecido ou removido.

## 25. External Dependencies

BLOCKED_EXTERNAL_DEPENDENCY, com o que cada uma exige (tabela completa em `EXTERNAL_INTEGRATIONS.md`):

| Dependência | Exige | Efeito hoje |
|---|---|---|
| Parecer jurídico e contábil da taxa de serviço (3,5%) | advogado(a) e contador(a): arranjo de pagamento (Lei 12.865/2013), ISS, cláusula, NFS-e | regra desligada; camada registrada e instruída, **nada devido, nada cobrado** |
| Chave PIX real da plataforma | pessoa jurídica titular | `PLATFORM_PIX_KEY` vazia → instrução "NÃO CONFIGURADA" |
| Banco / provedor de pagamento | integração bancária ou provedor homologado | conciliação manual, registrada e confirmada pelas partes; torre diz "DADO FINANCEIRO NÃO CONECTADO" |
| Nota fiscal | provedor fiscal | não emitida |
| Assinatura qualificada, gov.br, ICP-Brasil, biometria, KYC, SMS/WhatsApp | credenciais e contratos | não simulados; a interface diz "não ligado" |
| Aceite de termos | minutas por advogado(a) | cadastro em produção bloqueado (503) |
| Endereço público | conta de hospedagem do dono | pilha do zero provada no CI, sem URL |
| Tag `v0.27.0` no GitHub | o proxy recusa push de tag e API de escrita | criar manualmente no commit de fechamento |

## 26. Known Limitations

- Receita real R$ 0,00 por construção até a regra `contract.platform_service_fee` ficar ativa.
- Conciliação bancária manual; `value_capture_ratio` NÃO MEDIDO sem recursos de projeto confirmados.
- Preço de contrato avulso/parcelado é negociado (piso publicado não é preço); nenhuma tabela.
- `economic_rules` 2027.01 não tem `effective_until` fechado (CHECK impede data futura); a vigente é
  escolhida pela maior versão com `effective_from <= now()`.
- Documentos de assinatura permanecem no repositório marcados SUPERADO (histórico), e em `history/`.
- Motores de leitura (13) sem rastro durável — por desenho.
- Typecheck oficial do front só no CI; a reprodução local usa o `tsc` da máquina sem `@types/react` (ruído de tipos ausentes filtrado).
- Defeitos pré-existentes B1/B2 (`TECHNICAL_BASELINE_BEFORE_EXECUTION.md` §4) continuam fora do escopo.

## 27. GO / GO WITH CONDITIONS / NO-GO

```text
GO WITH CONDITIONS
```

Nenhuma falha técnica interna crítica em aberto: nenhuma assinatura; integridade econômica (3,5 +
1,5 do catálogo, distribuição fechada, instrução ≠ custódia, confirmação por quem recebe, GMV ≠
receita, reconhecimento só na quitação), autorização, tenancy, persistência e fluxo de negócio
completo têm teste executado e verde na segunda regressão. As condições são todas externas (§25):
parecer da taxa, chave PIX real, banco/provedor, nota fiscal, minutas, hospedagem, tag no GitHub.
Nenhuma falha crítica foi convertida em "condição".

## 28. Exact Next Step

1. Criar a tag `v0.27.0` no GitHub (Releases → nova tag no commit de fechamento) e anexar
   `IMPACTO_TRUST_FINAL_RELEASE_0.27.0.zip` + `.sha256`.
2. Levar `docs/ECONOMIC_MODEL.md` e `MONETIZATION_LEGAL_MATRIX.md` a advogado(a) e contador(a) com a
   pergunta exata: "o desenho financiador → projeto (direto, PIX do contrato) + financiador →
   plataforma (3,5%, cobrança própria) + financiador → proponente (1,5%) configura arranjo de
   pagamento ou intermediação, e como se fatura a taxa?". Só com a resposta a regra pode ficar verde.
3. Informar `PLATFORM_PIX_KEY` no ambiente de produção (pessoa jurídica titular) — sem ela a linha
   da plataforma continua "NÃO CONFIGURADA".
4. Próxima rodada técnica (sem dependência externa): fechamento de `effective_until` da 2027.01 por
   rotina; conciliação com extrato importado (sem banco ligado); B1/B2.
