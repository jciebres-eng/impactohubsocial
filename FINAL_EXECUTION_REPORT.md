# Relatório final de execução — IMPACTO v0.26.0

**Data:** 08/10/2026 · **Ramo:** `main` · **Tag:** `v0.26.0` (local; envio recusado pelo proxy — criar
no GitHub no commit indicado em §3) · **Pacote:** `IMPACTO_TRUST_FINAL_RELEASE_0.26.0.zip` (SHA-256 no
`.sha256` ao lado) · **Auditoria:** `FINAL_EXECUTION_AUDIT.md`

## 1. Executive Summary

A rodada transformou a tese econômica em produto funcional, sem fintech dentro do IMPACTO
(ADR-284) e sem inventar preço, parecer, integração ou publicação:

- **O contrato virou regra de operação.** O acordo assinado carrega as cláusulas (taxa, quem paga,
  modo, prazo de aceite em dias úteis, contestação), ganha versão imutável, deriva obrigações
  (entregar, aceitar, pagar) com prazo, exige aceite a quatro olhos no banco e, ao mudar, vira versão
  nova que invalida a aprovação anterior.
- **A distribuição é calculada na origem e não custodiada.** R$ 100.000 com 3% → R$ 100.000 ao
  projeto e R$ 3.000 de taxa (ou 97.000/3.000 no modo descontado), matriz gravada com hash; a taxa é
  cobrança própria da plataforma ao financiador, nunca descontada de dinheiro em trânsito, e **só
  cobrável com a regra `contract.platform_service_fee` ativa** — que nasce desligada, com carta legal
  amarela e sem percentual fixo (o percentual é do contrato). GMV ≠ receita, provado.
- **Duas torres de controle**, só leitura, que apontam para onde se decide: a do financiador (meu
  capital → onde está → para quem → para quê → executado → evidência → mudou → atrasos → riscos → o
  que preciso decidir) e a do governo (território → programas → editais → OSCs → projetos → recursos
  → indicadores declarados × validados → atrasos → territórios descobertos; k-anonimato ≥ 3).
- **"Projeto IMPACTO Ready"** como estado verificável, não selo: 15 critérios com a tabela e a
  contagem que sustentam cada um, desconhecido ≠ zero, hash reproduzível, mesmo resultado para dono e
  financiador, 404 para quem não enxerga o projeto.
- Tudo provado por HTTP e PostgreSQL reais (16 testes novos), pela jornada de demonstração nova
  (14 jornadas, 195 passos, 0 falha), pelas 220 telas no Chromium por perfil, e pela regressão
  completa — que na primeira passagem acusou uma regressão real (seis tipos do razão perdidos ao
  reescrever um CHECK) e duas decisões erradas de migração (FORCE RLS), todas corrigidas sem tocar
  em teste.

**Decisão: GO WITH CONDITIONS** (§27).

## 2. Version

0.26.0 — `VERSION`, `backend/pyproject.toml`, `web/package.json`, `web/package-lock.json`,
`README.md`, `docs/openapi.json`. Documentos da v0.25.0 preservados em `history/v0.25.0/`.

## 3. Commit

Commits da rodada (sobre `7d2730d`): `5780a25` (backend do contrato), `de83b1e` (tela do acordo e
jornada), `0be39bd` (torres, Ready, telas), `c132eab` (correções da regressão, motores, documentos,
versão), `e69231c` (fechamento: auditoria e relatório), `ce3579e` (correção de tipo acusada pelo
typecheck do CI) e o commit do manifesto de release, para o qual a tag `v0.26.0` aponta e cujo hash é
registrado em `FINAL_RELEASE_MANIFEST.json` e no `.sha256` do pacote (não cabe dentro do próprio commit).

**GitHub Actions** no commit `ce3579e` (run `37827919094`): `auditoria`, `docker` (com o typecheck
oficial) e `pilha-do-zero` (banco vazio → imagem → migrações → seed → jornadas → 220 telas → axe →
reinício) **verdes**; `backend` com 2.295 testes e apenas as 2 conferências do manifesto de
rastreabilidade reprovadas — porque o manifesto é gerado no fechamento, depois desse commit (a run
anterior, `37827524521`, acusou o erro de tipo `active_org`, corrigido em `ce3579e`).

## 4. Architecture Status

Inalterada no essencial: Starlette + PostgreSQL com RLS em 324 das 325 tabelas (a exceção é
`chain_heads`, revisada; 677 políticas; nenhuma com FORCE), hash encadeado em auditoria/razão/valor/confiança, sem custódia. Novidades: duas funções
SECURITY DEFINER com portão interno (`project_ready_facts`, `gov_territory_overview`), três tabelas
(`agreement_versions`, `agreement_obligations`, `agreement_allocations`), um módulo só leitura
(`network/control_tower.py`) e um motor de regra contratual (`trust/contract_rules.py`). Matriz
completa: `docs/execution/SYSTEM_INTEGRATION_MATRIX.md`; linha de base:
`docs/execution/TECHNICAL_BASELINE_BEFORE_EXECUTION.md`.

## 5. Engines Status

45 motores (42 + 3): implemented/integrated/tested 45/45; E2E 40 sim, 2 não (motores internos sem
rota), 3 n/a; observability 35 sim, 10 não (motores de leitura, incluindo as torres e o Ready, que
por desenho não escrevem). `ENGINE_COVERAGE.md`, `docs/execution/ENGINE_VALIDATION_MATRIX.csv`.

## 6. Contract Intelligence

PASS. Cláusulas → obrigações → prazos → aceite a quatro olhos → matriz de distribuição → versão
nova. `backend/tests/test_v0260_contract_rules.py` (8/8), jornada "Contrato como regra" (0 falha),
tela `/acordos/:id` (captura em `docs/evidence/telas_v0260/company-acordo-financiamento.png`).
Faltam: varredura que grave `obligation_overdue` (hoje calculado na leitura); redação jurídica da
cláusula (externo).

## 7. Match

PASS (inalterado): `match-engine@1.2.0` explica critério a critério (`signals[]` com peso,
contribuição, evidência e frescor; `why_match`, `why_not`, `missing_data`, `next_action`). O estado
IMPACTO Ready é mostrado ao lado do match na ficha do projeto, **não** como entrada dele — decisão
registrada (não acoplar antes de validar os critérios com usuários).

## 8. Diagnostic

PASS (inalterado): `diagnostic-engine@1.0.0`, 8 dimensões, versões publicadas e comparáveis. O
critério "diagnóstico realizado" do Ready lê `diagnoses.status IN ('complete','applied')`.

## 9. Equity

PASS (inalterado desde a v0.18.0): sem nota única, denominador com fonte, `comparable: false` com
motivos. Não tocado nesta rodada.

## 10. Evidence

PASS: o critério "evidências disponíveis" exige evidência **aceita por outra parte**; a torre do
financiador mostra aceitas × aguardando e lista evidências a analisar em "o que preciso decidir";
a torre do governo mostra contagens, nunca valores de pessoa.

## 11. Responsibility

PARTIAL: o Ready lê `responsibility_assignments` (escopo projeto, vigentes) **ou** `project_team`;
atribuição formal continua opcional. Inalterado o módulo de responsabilidade.

## 12. Reputation

Inalterado (v0.18.0). Não usado pelo Ready de propósito — reputação é dimensão observada, não
critério de prontidão.

## 13. Seals

Inalterado. O Ready **não é selo**: não é concedido, não expira, não tem definição publicada; é
recalculado a cada leitura e verificável por hash. Selos continuam com regra em SQL e zero definições
embarcadas.

## 14. Government Data

PASS: `gov_territory_overview` (só governo/plataforma; só projetos publicados; k ≥ 3; recusa 42501
a outros tipos — testado), lacunas territoriais, programas e editais do órgão, por causa, indicadores
declarados × validados. Dados do IBGE/ODS oficiais continuam fora (rede do ambiente), como antes.

## 15. Marketplace

Inalterado. A mesma matriz de distribuição serve a um acordo `service` (prestador recebe o valor;
taxa, se contratada, por quem o contrato indicar) — `marketplace.take_rate` continua recusada pelo
banco (ADR-022).

## 16. Payments

PASS/BLOCKED_EXTERNAL: compromisso → desembolso → confirmação → despesa → evidência (sem custódia)
inalterado e exercitado pela jornada; cobrança própria da taxa aberta em `platform_charges` com
provedor `manual`, `is_simulated = true` declarado na API. **Nenhum pagamento real** (Stripe e
provedor fiscal: BLOCKED).

## 17. Distribution

PASS: `agreement_allocations` — bruto, projeto, taxa, terceiros, `fee_mode`, `fee_bps`, pagador,
`fee_chargeable` + motivo, `pricing_version`, linhas (quem paga a quem, por qual meio), hash,
cobrança associada; prévia antes da vigência (`GET …/allocation`). Soma fechada por CHECK nos dois
modos. Sem escrow, sem carteira, sem saldo.

## 18. Billing

Inalterado (v0.21–v0.22): oferta, aceite, período gratuito, uso. A regra nova entra no catálogo
desligada e segue o mesmo portão (`monetization_rule_gate`). `GET /v1/monetization/rules` lista 10.

## 19. Fiscal

BLOCKED_EXTERNAL (inalterado): nota fiscal de serviço não implementada e sem provedor; a carta da
taxa registra ISS como base provável e **não analisa** alíquota/município.

## 20. Vouchers

Inalterado (`/v1/vouchers/redeem`, administração). Não tocado.

## 21. Identity

PARTIAL (inalterado + uma decisão): `identity_level` por usuário (`none … biometric`); o Ready usa o
melhor nível entre donos/administradores da organização e exige `document`. Biometria, KYC, gov.br:
BLOCKED_EXTERNAL; nada simulado.

## 22. Security

Revisada: RLS em toda tabela nova; nenhuma FORCE (o backup do dono continua íntegro — `pg_dump`
testado em `test_v0190_ops`); portões internos nas funções SECURITY DEFINER; contexto de sistema
restrito aos módulos revisados; nenhum segredo em código/documento/pacote (`secrets_scan.py`,
gitleaks no CI); recusa por perfil conferida nas telas novas. **Nenhum sistema ligado à internet é
"impossível de invadir", e este não é exceção.**

## 23. LGPD

Inalterado no desenho; novidades respeitam-no: a torre do governo devolve contagens por projeto
publicado e suprime território com < 3 projetos; indicadores saem como contagens de medições;
risco de projeto sai como contagem (o registro é da OSC); o Ready devolve contagens, nunca linhas,
e só a quem enxerga o projeto.

## 24. Tests

```text
PRIMEIRA REGRESSÃO COMPLETA (código novo, antes das correções): 2.295 testes — 11 falhas, 3 erros
  → causas e correções em FINAL_EXECUTION_AUDIT.md §6 (uma regressão real: seis tipos do razão)
SEGUNDA REGRESSÃO COMPLETA (após correções):                 2.295 testes — 0 falha técnica (1 falha esperada: o manifesto de
  rastreabilidade é gerado no fechamento, depois da execução; o portão de release foi reexecutado
  verde em seguida — ver docs/evidence/test_run_v0.26.0.log); 29 pulados (dependem de credencial)
MÓDULOS NOVOS: test_v0260_contract_rules (8/8) · test_v0260_control_towers (8/8)
JORNADAS: 14 jornadas, 195 passos, 0 falha · TELAS: 796 visitas, 220 rotas, 0 falha · TELEFONE: 233 telas, 0 falha
LINT: ruff 0 · BUILD: esbuild ok · TYPECHECK: no CI (npm ci)
LOG: docs/evidence/test_run_v0.26.0.log
```

Testes que fixam contagem foram atualizados com a razão escrita ao lado (894 operações, 220 telas,
45 motores, 10 regras): ADR-340. Nenhum teste foi enfraquecido ou removido.

## 25. External Dependencies

BLOCKED_EXTERNAL_DEPENDENCY, com o que cada uma exige:

| Dependência | Exige | Efeito hoje |
|---|---|---|
| Parecer jurídico e contábil da taxa de serviço contratada | advogado(a) e contador(a): arranjo de pagamento (Lei 12.865/2013), ISS, cláusula, nota fiscal | regra desligada; taxa registrada e não cobrada |
| Pagamento real (projeto e taxa) | conta Stripe aprovada / meio escolhido pelas partes | cobrança própria simulada e declarada |
| Nota fiscal | provedor fiscal | não emitida |
| Assinatura qualificada, gov.br, ICP-Brasil, biometria, KYC, SMS/WhatsApp | credenciais e contratos | não simulados; a interface diz "não ligado" |
| Aceite de termos | 11 minutas por advogado(a) | cadastro em produção bloqueado (503) |
| Endereço público | conta de hospedagem do dono (D-PUB1) | pilha do zero provada no CI, sem URL |
| Tag `v0.26.0` no GitHub | o proxy deste ambiente recusa push de tag e API de escrita | criar manualmente no commit de fechamento |

## 26. Known Limitations

- `obligation_overdue` é calculado na leitura; não há varredura que o grave no razão.
- Sem snapshot histórico do estado Ready (é recalculado a cada leitura).
- O Ready não alimenta o match (decisão).
- Nível de identidade é por usuário; o critério usa o melhor nível entre donos/admins.
- A torre do financiador mostra risco de projeto como contagem (o registro é da OSC).
- A torre do governo não agrega por programa (`program_financials` existe na API).
- Defeitos pré-existentes encontrados na leitura da base e **não corrigidos** (fora do escopo, registrados):
  `review_inbox` filtra situações inexistentes de candidatura; `exec.progress` da prontidão por
  finalidade conta estados de marco inexistentes (`TECHNICAL_BASELINE_BEFORE_EXECUTION.md` §4).
- Motores de leitura (10, incluindo torres e Ready) sem rastro durável — por desenho.
- Typecheck oficial do front só no CI (registro npm indisponível aqui).

## 27. GO / GO WITH CONDITIONS / NO-GO

```text
GO WITH CONDITIONS
```

Nenhuma falha técnica interna crítica em aberto: integridade financeira (100k → 97k/3k rastreável,
GMV ≠ receita, idempotência, isolamento de tenant, desconhecido ≠ zero), autorização, tenancy,
persistência e fluxo de negócio completo têm teste executado e verde na segunda regressão. As
condições são todas externas (§25): parecer da taxa, pagamento real, nota fiscal, minutas, hospedagem,
tag no GitHub. Nenhuma falha crítica foi convertida em "condição".

## 28. Exact Next Step

1. Criar a tag `v0.26.0` no GitHub (Releases → nova tag no commit de fechamento) e anexar
   `IMPACTO_TRUST_FINAL_RELEASE_0.26.0.zip` + `.sha256`.
2. Levar `MONETIZATION_LEGAL_MATRIX.md` (décima carta) a advogado(a) e contador(a) com a pergunta
   exata: "o desenho financiador → projeto (direto) + financiador → plataforma (cobrança própria da
   taxa) configura arranjo de pagamento ou intermediação?". Só com a resposta a regra pode ficar
   verde — e aí a primeira cobrança real ainda exigirá provedor e nota fiscal.
3. Próxima rodada técnica (sem dependência externa): varredura de obrigações vencidas gravando no
   razão; snapshot do estado Ready; agregação por programa na torre do governo; correção dos dois
   defeitos pré-existentes (B1, B2).
