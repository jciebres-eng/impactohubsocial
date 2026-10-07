# BLOQUEIOS — v0.23.0

Este arquivo lista o que NÃO pôde ser executado nesta rodada e por quê. A regra que o governa é a do
pacote de execução: *se algo não puder ser executado por falta de ambiente, NÃO mascarar como PASS*.

Cada bloqueio declara: identificador, o que está bloqueado, a causa, quem pode desbloquear, o risco de
seguir sem ele, e o que foi feito para reduzir esse risco. Um bloqueio sem causa verificável não é
bloqueio — é pendência, e pendência não entra em release.

Nenhum bloqueio aqui é interno ao produto. Todos dependem de conta, credencial ou registro de terceiro,
e nenhum pode ser resolvido escrevendo código.

---

## D-SUP1 — Registro npm indisponível (403)

**Bloqueado:** `npm ci`, geração de `package-lock.json`, instalação de `@types/react` e
`@types/react-dom`, e a verificação de tipos pelo `tsconfig.json` oficial.

**Causa:** o registro npm responde 403 neste ambiente. Não há lockfile no repositório porque não houve
instalação bem-sucedida que o produzisse.

**Quem desbloqueia:** quem tiver rede com acesso ao registro npm — uma execução de `npm install` em
qualquer máquina com acesso gera o lockfile, que então é versionado.

**Risco de seguir sem ele:** sem lockfile, duas instalações podem resolver versões diferentes das
dependências de desenvolvimento. O que vai a produção não é afetado: o `build.mjs` empacota a partir
do que está em `web/src`, e o resultado é um pacote estático.

**Redução do risco:**
- `web/tsconfig.offline.json` declara stubs mínimos em `web/types/react/index.d.ts` e roda com
  `strict: true` e `noImplicitAny: true`. A verificação de tipos acontece — sob stubs, e isso está
  dito aqui e no relatório.
- A divergência entre `tsconfig.json` e `tsconfig.offline.json` é UMA causa raiz (ausência dos
  pacotes de tipos), verificada categoria por categoria: dos 8.274 erros do arquivo oficial, 8.022
  são TS7026, 114 TS7016, 80 TS7006, 43 TS2322, 9 TS2503, 3 TS7031, 2 TS18046 e 1 TS2339 — todos
  cascata da mesma ausência. Nenhum é defeito de código da aplicação.
- O fluxo de CI (`.github/workflows/ci.yml`) executa `npm ci` quando existe lockfile e publica o
  lockfile gerado como artefato quando não existe, para que a primeira execução com rede o produza.

---

## D-INT1 a D-INT14 — Homologação de integração exige conta de fornecedor

**Bloqueado:** o estado `sandbox` e `homologated` das 14 integrações listadas em
`INTEGRATION_HOMOLOGATION_MATRIX.csv`. Todas estão em `scaffolded` (2) ou `contract_tested` (12), e
nenhuma em `production_active`.

**Causa:** homologar exige credencial real do fornecedor e um ambiente de sandbox dele. A regra
permanente deste projeto proíbe simular provedor fiscal, Stripe real, KYC real, identidade
governamental, gov.br, ICP-Brasil, ACT, biometria, assinatura qualificada e SMS. Marcar `sandbox` sem
credencial seria exatamente a simulação proibida, e marcar `production_active` sem evidência real é
vedado pelo pacote de execução.

**Quem desbloqueia:** quem contratar cada fornecedor e fornecer as credenciais de sandbox. As
variáveis necessárias por integração estão na coluna `activation_vars` da matriz — nenhuma delas tem
valor neste repositório, e nenhum segredo é versionado.

**Risco de seguir sem ele:** o comportamento contra o fornecedor real pode divergir do contrato
testado. É o risco que nenhum teste local elimina.

**Redução do risco:**
- As 14 têm teste de contrato executado (coluna `contract_test`) e teste negativo.
- Os cinco interruptores de provedor estão em valor inerte e versionados assim:
  `mail_provider=console`, `storage_provider=local`, `antivirus_provider=none`,
  `billing_provider=none`, `ai_provider=local`. Nenhum caminho de código chama fornecedor externo
  nesta configuração.
- `credentials` é `ausentes` nas 14 linhas, e um teste recusa o commit de credencial.
