# DESIGN_HANDOFF_FINAL — o que o designer recebe (v0.16.0)

**Baseline:** 0.16.0 · **Branch:** `chore/v0.16.0-impact-network-core` · **Suíte:** 788 testes, 0 falhas
(12 de volume rodam em passo próprio com `PERF=1`) · Substitui `DESIGN_HANDOFF.md` (v0.15.0), que fica em
`history/v0.15.0/`.

## Leitura mínima, nesta ordem

1. **este arquivo**
2. `IMPACT_NETWORK_ARCHITECTURE.md` — a cadeia de impacto e os onze motores
3. `INFORMATION_ARCHITECTURE.md` — o inventário real e os sete domínios
4. `NAVIGATION_MODEL.md` — o modelo horizontal proposto, com o mapeamento item-a-item
5. `WORKSPACE_ARCHITECTURE.md` + `ROLE_BASED_EXPERIENCE.md` — o que cada persona precisa ver primeiro
6. `PRIVACY_VISIBILITY_MATRIX.md` — **obrigatório**: o que pode aparecer em tela pública
7. `BILLING_V2.md` — o que o checkout tem de mostrar

## 1 · O pacote "Design System Convergência" NÃO foi recebido

Primeiro ponto, porque muda o escopo desta entrega.

O pedido desta rodada pressupõe um pacote de Design System ("Convergência") a ser integrado nos passos 8–9 da
sequência de 13. **Esse pacote não chegou.** Verificado: não há arquivo correspondente no repositório, no diretório de
anexos (`/mnt/user-data/uploads` está vazio) nem em qualquer caminho do contêiner.

Consequência honesta: **as seções de integração de Design System desta rodada não foram executadas** — não por
dificuldade técnica, mas por ausência do insumo. Nada foi inventado para preencher o buraco: não há tokens
"Convergência" no CSS, não há componentes renomeados, não há afirmação de conformidade com um sistema que ninguém
viu.

O que **foi** feito no lugar: a camada de produto que o Design System precisava representar (os onze motores, as dez
personas, as 26 telas novas) e os documentos de AI e navegação acima, que são o insumo que o Design System consome.
Quando o pacote chegar, o trabalho é mapear tokens e componentes sobre uma AI já decidida — que é a ordem correta.

## 2 · O que está pronto e provado

| Camada | Estado | Prova |
|---|---|---|
| API `/v1` | **704 rotas**, contrato estável, OpenAPI gerado do código | `docs/API.md`, `GET /v1/openapi.json` |
| Banco | PostgreSQL 16, **231 tabelas**, RLS em todas (exceto `schema_migrations`), **17 migrations** forward-only | `DATABASE_INTEGRITY_REPORT.md` |
| Rede de impacto | 11 motores, 22 tipos de relação, 9 tipos de proposta, grafo até profundidade 2 | `backend/impacto/network/` |
| Workspace | 10 personas, 24 seções, 15 capacidades | `WORKSPACE_ARCHITECTURE.md` |
| Notificação | 14 grupos, 4 prioridades, fan-out para a equipe, idempotente | `NOTIFICATION_ARCHITECTURE.md` |
| Moderação | escada de 10 degraus com proporcionalidade e contestação | `MODERATION_LADDER.md` |
| Cobrança | preço versionado, aviso de 30 dias, imposto no checkout | `BILLING_V2.md` |
| Perfil público | `impacto.app/@identificador`, projeção curada | `PRIVACY_VISIBILITY_MATRIX.md` |
| Testes | 788, 0 falhas | `TEST_REPORT.md` |
| Desempenho | escala cheia, maior caminho 1497 ms (orçamento 2500 ms) | `PERFORMANCE_REPORT.md` |

## 3 · As 26 telas novas desta rodada

Funcionais, sem tratamento visual — é o que o designer vai vestir:

`/area` workspace · `/rede/relacoes` relações · `/rede/grafo` grafo · `/rede/atividade` atividade ·
`/rede/experiencias` experiências · `/propostas` caixa de propostas · `/propostas/:id` proposta ·
`/propostas/nova` nova proposta · `/marketplace` descobrir · `/marketplace/meus` meus anúncios ·
`/marketplace/:id` anúncio · `/marketplace/novo` novo anúncio · `/conversas` conversas · `/conversas/:id` conversa ·
`/relatorios-impacto` relatórios · `/relatorios-impacto/:id` relatório · `/relatorios-impacto/novo` novo ·
`/perfil-publico` meu perfil público · `/perfil-publico/experiencias` experiências · `/prontidao/finalidades`
prontidão por finalidade · `/territorio/necessidades` necessidades · `/vocabulario` taxonomias ·
`/admin/denuncias` denúncias · `/admin/medidas` medidas · `/@:identificador` **página pública** ·
`/marketplace` público (sem sessão).

## 4 · Oito invariantes de design — quebrar qualquer um destes é defeito, não escolha estética

1. **"Investido" ≠ "intenção".** Três estágios distintos (intenção → compromisso → transação) e a interface precisa
   nomear qual está mostrando. Nunca somar os três num número chamado "captado".
2. **Projeto privado nunca aparece em vitrine.** Só `publication_status = published` alcança área pública. Cartão de
   projeto publicado e de rascunho **não podem** ter a mesma aparência.
3. **Relação existir ≠ relação ser pública.** Cinco níveis de visibilidade; a interface mostra qual está ativo e quem
   alcança.
4. **Proposta ≠ contrato ≠ investimento ≠ pagamento.** Quatro coisas, quatro telas, quatro vocabulários. Aceitar
   proposta **não** é assinar contrato.
5. **Recomendação ≠ Match.** Match é o motor de compatibilidade (v0.9.0, intocado). Recomendação é "faça isto agora".
   Rotular recomendação como "match" promete precisão que ela não tem.
6. **Prontidão sempre com explicação.** Seis dimensões; nunca mostrar a nota sem o porquê e sem o que falta.
   Número sozinho é julgamento sem recurso.
7. **Número de impacto é colhido, não digitado.** O relatório exibe `metrics` apurado pelo banco. Se a interface
   oferecer campo editável para esses números, está desfazendo a trava.
8. **Nenhum padrão obscuro no checkout.** Total sempre visível, imposto declarado, cancelar é um botão.

## 5 · Modo claro e escuro

Pedido em rodada anterior e **entregue**: `prefers-color-scheme` com tokens em `:root` e redefinição sob
`@media (prefers-color-scheme: dark)`, mais alternância manual. O que o designer recebe é o **mecanismo**; a paleta
definitiva é decisão de design. Os tokens atuais são funcionais e deliberadamente neutros — não são proposta de
identidade visual.

## 6 · ODS

Os 17 Objetivos estão no banco na tabela `sdg_goals` (desde v0.14.0): número, código `ODS1`…`ODS17`, nome em
português e inglês e a **cor oficial** em hexadecimal (`#E5243B` para o ODS 1, e assim por diante), com CHECK de
formato. As colunas `ods smallint[]` de organizações, projetos, soluções e editais referenciam esse catálogo.

**Os emblemas e logotipos da ONU não estão embutidos no pacote** — são marcas protegidas, com regras de uso próprias,
e incorporar a arte sem conferir a licença seria exatamente o tipo de invenção que o projeto proíbe. O aviso está
escrito na própria migração, acima da tabela. Para o designer: número, nome e cor estão prontos; obter a autorização
de uso da arte oficial é tarefa externa, registrada em `IP_REGISTER.md` e detalhada em `SDG_ESG_TAXONOMY.md`.

## 7 · Pendências que NÃO são bugs

* **Navegação lateral plana** — AMARELO consciente; é a entrega de design, especificada em `NAVIGATION_MODEL.md`.
* **`provider_price_id` nulo** — não há conta Stripe real. O checkout recusa cobrar em vez de inventar.
* **Hub de integração sem tela** — 36 rotas funcionais, interface ainda não desenhada.
* **E2E de navegador cobre as telas de v0.15.0** — as 26 novas têm cobertura de API e de jornada, não de Playwright.
  Registrado em `TEST_REPORT.md`.
* **Nada de biometria, assinatura qualificada, ICP-Brasil, gov.br, SMS, ACT, Stripe real, provedor fiscal real, KYC
  real ou identidade governamental real.** Nenhum desses está simulado em nenhum caminho; onde o produto depende
  deles, há dublê explícito e marcado.

## 8 · O que o designer **não** precisa refazer

Backend, banco, autenticação, autorização, multi-tenancy, cobrança, notificação, moderação, taxonomias, perfil
público e os onze motores. Se algo parecer faltar, conferir primeiro a seção 7.
