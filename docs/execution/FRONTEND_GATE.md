# GATES 7 E 8 — INTEGRAÇÕES E FRENTE · EVIDÊNCIA DE EXECUÇÃO

## Gate 7 — Integrações

| Integração nomeada pelo pacote | Linha(s) na matriz | Estado | Credencial | Teste de contrato |
|---|---|---|---|---|
| **Stripe** | `stripe`, `stripe_payments` | `contract_tested` | ausente | sim |
| **SMTP** | `smtp`, `email_smtp` | `contract_tested` | ausente | sim |
| **S3** | `s3_storage` | `contract_tested` | ausente | sim |
| **ClamAV** | `clamav` | `contract_tested` | ausente | sim |
| **OIDC** | `oidc_identity` | `contract_tested` | ausente | sim |
| **APIs governamentais** | `government_api` | `scaffolded` | ausente | sim |

14 integrações no total: 12 `contract_tested`, 2 `scaffolded`, **0 `sandbox`**, **0 `homologated`**,
**0 `production_active`**. **129 testes de integração executados, verdes.**

### Os cinco interruptores embarcam inertes

Uma integração que saia do pacote apontando para um fornecedor real cobra dinheiro, manda e-mail e
grava arquivo em nome de alguém, e ninguém pediu. Os valores de fábrica, travados por teste:

| Interruptor | Valor de fábrica | O que isso desliga |
|---|---|---|
| `mail_provider` | `console` | e-mail vai para o log, não para a caixa de ninguém |
| `storage_provider` | `local` | arquivo em disco local, nenhum bucket de terceiro |
| `antivirus_provider` | `none` | sem ClamAV; download de não escaneado governado por `allow_unscanned_downloads` |
| `billing_provider` | `none` | nenhuma cobrança real é possível |
| `ai_provider` | `local` | nenhuma chamada a modelo de terceiro |

Um teste confere ainda que **nenhum campo de credencial de `Settings` embarca com valor** — o caminho
mais curto entre um descuido e uma cobrança real no cartão de alguém.

### O que o Gate 7 NÃO afirma

Nenhuma integração está homologada. Homologar exige credencial real e sandbox do fornecedor, e a
regra permanente proíbe simular provedor fiscal, Stripe real, KYC, identidade governamental, gov.br,
ICP-Brasil, ACT, biometria, assinatura qualificada e SMS. As 14 linhas estão **BLOCKED** em
`INTEGRATION_HOMOLOGATION_MATRIX.csv`, com causa em `BLOCKERS.md` (D-INT1..14). Marcar `sandbox` sem
credencial seria exatamente a simulação proibida.

A matriz passou a ler `config/integration_providers.json` — o catálogo **embarcado** — em vez do
banco, e um teste exige que nada embarque acima de `contract_tested`. O motivo está em
`IMPLEMENTATION_LOG.md`: lendo o banco, a matriz dependia de qual `DATABASE_URL` estava no ambiente,
e um teste de integração promove `totvs` a `homologated` no meio da suíte sem restaurar em caso de
falha — uma matriz gerada naquele instante declararia homologação **real** de um provedor jamais
homologado.

---

## Gate 8 — Frente

| Item | Resultado |
|---|---|
| **typecheck** | `tsc -p tsconfig.offline.json --noEmit` → **0 erros** |
| **build** | `node build.mjs` → `app-GK55KUHJ.js` 972,6 kB · `styles-MY6XPEWL.css` 33,3 kB · 14 arquivos no pré-cache · 203 ms |
| **E2E** | **91 testes**, verdes, com Chromium real |
| **loading / empty / error / permission** | `StateView` (carregando com `aria-busy`, erro com `role="alert"` e "Tentar novamente", vazio), `EmptyArea` (por que está vazio, o que se ganha, campos obrigatórios, de onde vem o dado, o que bloqueia), e recusa por papel conferida em `test_v0230_frontend.py` |
| **mobile** | sem rolagem horizontal em 390 px; tamanho de alvo de toque conferido |
| **WCAG 2.2 AA** | 13 conferências no navegador + **4 novas de modal** |

### O escopo do typecheck, medido e não presumido

`tsconfig.offline.json` existe porque `@types/react` não é instalável aqui (D-SUP1). Ele herda
`strict: true` e `noUnusedLocals` e acrescenta `noImplicitAny`. Mas herdar `strict` não diz o que ele
**realmente pega**; os stubs mínimos em `web/types/` decidem isso. A diferença foi medida plantando um
erro de cada tipo:

| Erro plantado | Resultado |
|---|---|
| Lógica / hook — `setNome(42)` num estado `string` | **pega** (TS2345) |
| Prop tipada de componente — `variant="roxo"` | **pega** (TS2322) |
| Atributo de elemento DOM — `<a href={42}>` | **não pega** |

O terceiro é limitação declarada do stub (`JSX.IntrinsicElements` é `[tag: string]: any`). Escrever
"typecheck passa" sem dizer isso seria afirmar cobertura que não existe.

Os 8.274 erros do `tsconfig.json` oficial foram investigados categoria por categoria — 8.022 TS7026,
114 TS7016, 80 TS7006, 43 TS2322, 9 TS2503, 3 TS7031, 2 TS18046, 1 TS2339 — e **todos** são cascata
da mesma ausência de `@types/react`. Nenhum é defeito do código da aplicação.

### Modal — era o item sem teste

Modal é onde acessibilidade costuma quebrar. O componente usa `<dialog>` nativo com `showModal()`,
que resolve as quatro quebras clássicas por construção — mas "resolve por construção" é hipótese até
alguém medir. Medido no navegador, com o modal "Anotar ideia" de `/ideias`:

| Quebra clássica | Resultado |
|---|---|
| Modal sem nome acessível | **tem** nome, via `aria-labelledby` → `<h2>` |
| Foco não entra no modal ao abrir | **entra** |
| Página de trás continua alcançável | **inerte** — elemento externo não recebe foco |
| Escape não fecha / foco não volta | **fecha**, e o foco **volta** (não cai em `<body>`) |

A última importa mais do que parece: foco que cai em `<body>` faz quem navega por teclado recomeçar
do topo da página a cada modal fechado.

### Tabelas — o achado que não resistiu à conferência

A primeira medição acusou **411 `<th>` sem `scope`** e parecia defeito sério. Dois erros de
instrumento depois, o número real é outro:

* o padrão `<th[^>]*>` casa com `<thead>` também, porque `<th` é prefixo de `<thead`;
* `<th>` sem `scope` **dentro de `<thead>`** não é ambíguo: a inferência de cabeçalho do HTML associa
  a coluna de forma confiável.

| Contagem correta | |
|---|---|
| `<th>` com `scope` explícito | 4 |
| `<th />` vazios (coluna de ações) | 16 |
| sem `scope`, dentro de `<thead>` | 318 |
| **ambíguos de verdade** | **0** |

**Não havia defeito.** O que havia era a ausência da trava para o caso que importa: um `<th>` de
cabeçalho de **linha**, fora de `<thead>`, sem `scope="row"` — aí o leitor não tem como saber se o
cabeçalho governa a linha ou a coluna. O teste permite os 318 e recusa o primeiro ambíguo que
aparecer. Reescrever 318 marcações por estética seria risco de regressão sem ganho.

### O que o Gate 8 NÃO afirma

`ACCESSIBILITY_REPORT.md` declara 6 pendências com nome e motivo, e nenhuma delas é alcançável deste
ambiente: **axe-core** (registry npm 403), **leitor de tela real** (NVDA/VoiceOver/Orca exigem sistema
operacional com o leitor instalado e operação manual), **segundo navegador** (só Chromium está
instalado), **zoom de texto a 200%**, **simulação de daltonismo** e **navegação por voz**.

O que foi verificado é a **estrutura que o leitor consome** — nome acessível, marcos, `aria-live`,
contraste computado — e não a experiência auditiva. Conformidade WCAG 2.2 AA plena exige as seis
pendências acima e permanece **não afirmada**.
