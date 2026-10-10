# Demonstração — o que dá para mostrar, e o que não dá

Este documento serve a quem vai **apresentar** a plataforma: investidor, conselho, OSC parceira,
órgão público, designer. Ele diz o que uma demonstração honesta pode mostrar hoje e nomeia, item a
item, o que **não** pode ser mostrado porque depende de terceiro ou de pessoa.

> **A regra desta demonstração:** nada é encenado. Se uma integração não está ligada, a tela mostra
> que não está — não uma tela de sucesso falsa. Encenar pagamento, nota fiscal, assinatura
> qualificada, gov.br ou biometria seria mentir para quem decide com base na demonstração.

---

## 1. O ambiente da demonstração

Use **staging**, nunca produção, e deixe isso visível na URL e na fala. O procedimento está em
[`PUBLICACAO.md`](PUBLICACAO.md); são dez passos, e nenhum pode ser pulado.

Para desenvolvimento local há `IMPACTO_SEED_DEMO=true` e o subcomando `seed-demo`, que povoam o banco
com organizações e projetos fictícios. Os dois são **recusados em staging e produção** — a
inicialização aborta com `IMPACTO_SEED_DEMO não é permitido em staging/production`. É deliberado:
dado fictício em ambiente que parece oficial é a origem clássica da demonstração que engana.

Portanto, a escolha é consciente:

| Ambiente | Dados | Serve para |
|---|---|---|
| Local (`development`) | fictícios, do `seed-demo` | mostrar fluxo completo sem depender de ninguém |
| Staging | reais, inseridos à mão por quem apresenta | mostrar o produto como ele se comporta de verdade |
| Produção | reais | não é lugar de demonstração |

## 1.1 As contas de demonstração (v0.24.0)

`seed-demo` cria 15 contas fictícias (a Apoiadora, pessoa física, entrou na v0.25.0), todas com a senha de `DEMO_PASSWORD` (se a variável não for
definida, o padrão escrito em `backend/impacto/seed_dev.py`, que só vale onde o seed roda):

| Perfil | E-mail | Entra com |
|---|---|---|
| OSC | `osc@demo.impacto.local` | senha |
| Empresa | `empresa@demo.impacto.local` | senha |
| Profissional (contadora) | `contador@demo.impacto.local` | senha |
| Governo | `governo@demo.impacto.local` | senha |
| Apoiadora (pessoa física) | `apoiador@demo.impacto.local` | senha |
| Administrador da plataforma | `admin@demo.impacto.local` | senha **+ aplicativo autenticador** |
| Editora, Revisor, Suporte | `editor@`, `revisor@`, `suporte@demo.impacto.local` | senha **+ aplicativo autenticador** |
| Controladoria, Financeiro, Contabilidade, Tesouraria, Operações, Auditoria | `controladoria@`, `financeiro@`, `contabilidade@`, `tesouraria@`, `operacoes@`, `auditoria@demo.impacto.local` | senha **+ aplicativo autenticador** |

**O segundo fator é de verdade.** A administração exige MFA verificado na sessão, e isso não é
relaxado para demonstração — relaxar seria desligar uma trava para a tela ficar bonita. O seed
cadastra um TOTP nas dez contas internas com o segredo de `DEMO_TOTP_SECRET` (base32); se a variável
não existir, gera um e o imprime na saída do `seed-demo` **uma única vez**. Quem for demonstrar
coloca esse segredo no aplicativo autenticador (ou gera o código com qualquer TOTP padrão de 6
dígitos/30 s) e passa pela verificação como um administrador real passaria.

Até a v0.23.1 o seed criava essas contas sem segundo fator, e a área administrativa inteira
respondia 403 na demonstração — 40 das 53 telas do menu do administrador. O produto estava certo; a
demonstração é que estava incompleta.

**A demonstração está provada por teste, não por roteiro.** `backend/tests/test_v0240_demo_completa.py`
sobe o servidor real, semeia, e percorre no Chromium as 14 contas: 295 telas de menu abertas, zero
5xx, zero erro de JavaScript, marca oficial renderizada em todas, temas claro e escuro, largura de
telefone. As capturas e o relatório por persona ficam em `docs/evidence/demo_v0240/`.

Os 4xx que o relatório registra são achados para o produto, não falhas da demo — estão listados em
`TESTER_GUIDE.md`, seção 6.

## 1.2 A demonstração inteira, do zero, com Docker (v0.25.0)

```bash
cp infra/compose/demo/.env.example infra/compose/demo/.env      # preencha as cinco variáveis
mkdir -p dist-stack/data && chmod 777 dist-stack/data
docker compose -f infra/compose/demo/compose.yml --env-file infra/compose/demo/.env up -d --build
# depois de /readyz responder 200, os dados das jornadas (opcional, mas é o que torna a demo rica):
DEMO_PASSWORD=... DEMO_TOTP_SECRET=... python3 scripts/demo_stack.py \
  --base http://127.0.0.1:8080 --outbox dist-stack/data/outbox --saida dist-stack/out
```

Sobe um banco **vazio** com o mesmo desenho do Supabase (administrador sem superusuário, pgcrypto em
`extensions`), a imagem do produto, as migrações, o seed e a aplicação conectada como `impacto_app`.
`scripts/demo_stack.py` executa as jornadas pela API — OSC, financiador, profissional, governo,
apoiadora, captação, documentos, marketplace, suporte, banco de ideias, administração e pendências —
e deixa a demonstração com projetos, diagnóstico, candidaturas aprovadas, aporte, pagamento,
medições validadas em série, proposta, conversa, relatório de impacto, acordo assinado, registro
verificável, campanha pública, cotas apoiadas e itens pendentes. Os e-mails ficam em
`dist-stack/data/outbox` (é demonstração: nenhum e-mail sai).

**Isto é provado a cada push** pelo job `pilha-do-zero` do CI: o mesmo arquivo, do zero, com as
jornadas, as 227 telas no Chromium com cada perfil, o axe-core e um reinício conferindo que os dados
continuam. O que ainda não existe é um **endereço público**: depende de conta de hospedagem em nome do
dono do projeto (D-PUB1 em `execution/BLOCKERS.md`).

## 2. Por onde navegar

São **235 telas** servidas pelo roteador (a v0.34.0 acrescentou `/remuneracao`, `/contribuicoes`, `/admin/remuneracao` e `/admin/conciliacao`; a v0.33.0 acrescentou `/doacao/:id`, `/minhas-doacoes`, `/admin/doacoes` e `/admin/doacoes/risco`; a v0.30.0, `/projetos/:id/dossie`). O mapa delas — rota, componente, arquivo, quais tipos de
organização alcançam, se está em menu e quais operações de API cada uma chama — está em
[`execution/screen_inventory.json`](execution/screen_inventory.json) e
[`execution/screen_backend_map.json`](execution/screen_backend_map.json), e em forma navegável no
painel gerado por `scripts/make_screen_panel.py`.

Os seis tipos de organização veem menus diferentes. Uma demonstração que troca de tipo no meio mostra
a tese do produto melhor que qualquer slide:

| Tipo | Itens de menu | Onde a demonstração costuma render |
|---|---|---|
| OSC | 43 | diagnóstico → prontidão → projeto → candidatura → prestação de contas |
| Empresa | 33 | explorar projetos → carteira → relatórios recebidos |
| Governo | 30 | necessidades do território → edital → execução |
| Profissional | 28 | marketplace → proposta → acordo → validação |
| Apoiador | 21 | apoiar → carteira → prestação de contas recebida |
| Administração | 32 | compliance, auditoria, integridade, interruptor |

**85 das 235 telas não estão em menu nenhum** — abrem só por link direto (até a v0.24.2 o gerador do
inventário lia só a primeira linha de cada menu e dizia 119; corrigido na v0.25.0). Em boa parte é correto
(detalhe de item, formulário de edição), mas é a primeira pergunta que o Designer vai querer
responder, e o painel permite marcá-las uma a uma.

## 3. O que a demonstração mostra de verdade

- **Isolamento entre organizações.** 324 das 325 tabelas têm RLS, com 677 políticas (v0.26.0). Entrar com duas
  organizações lado a lado e tentar alcançar o dado da outra é a demonstração mais convincente que
  esta plataforma tem, porque o banco recusa, não a aplicação.
- **Proveniência de um número de impacto.** `GET /v1/indicator-values/{id}/provenance` devolve a
  cadeia inteira **e os elos que faltam**. Mostre um indicador com `gaps` preenchido: a plataforma
  dizendo o que o próprio número não prova é o diferencial, não um defeito a esconder.
- **Cadeias de hash.** `audit_verify`, `ledger_verify`, `value_verify` e `trust_verify` recalculam a
  cadeia na hora. Adultere uma linha pelo banco e rode de novo na frente de quem assiste.
- **Interruptor de emergência** (`/admin/interruptor`): desligar uma capacidade e ver a API recusar.
- **A trava jurídica**, abaixo. Ela parece um defeito e é o oposto.
- **A identidade oficial** (v0.24.0): a interface veste os tokens de `web/brand/tokens.json` —
  amarelo de ação, navy estrutural, três temas — e o lockup transparente oficial, nos tamanhos que o
  raster de origem permite. O que a identidade não cobre está dito em `web/brand/README.md`: licença
  da marca não comprovada, logo master em raster, fontes não embarcadas (renderiza Inter).

## 4. O que NÃO dá para mostrar — e por quê

| Não demonstrável hoje | Motivo | De quem depende |
|---|---|---|
| Cobrança real, assinatura paga | Nenhum provedor de pagamento ligado | Conta Stripe aprovada |
| Nota fiscal, retenção, incentivo | Nenhum provedor fiscal ligado | Contrato com provedor fiscal |
| gov.br, ICP-Brasil, assinatura qualificada | Exige credencial e certificado | Órgão emissor / AC |
| Biometria, KYC, verificação de identidade real | Exige provedor homologado | Contrato com provedor |
| SMS e WhatsApp | Exige conta e número aprovado | Operadora / Meta |
| As 14 integrações do catálogo | Todas em `BLOCKED` por falta de credencial | Cada fornecedor |
| **Aceite de termos pelo usuário** | As 11 minutas jurídicas não passaram por advogado | Advogado(a) |

A última merece explicação na própria demonstração, porque ela **bloqueia o cadastro em produção**:

```
POST /v1/auth/register  →  503  legal_documents_not_published
```

O gatilho do banco recusa aceite de documento que não esteja aprovado e vigente. Enquanto
`terms_of_use` e `privacy_policy` forem minutas, ninguém se cadastra em produção. Isso foi escolhido
em vez da alternativa — coletar aceite de rascunho, que não vale nada e dá aparência de prova. Para
ver a situação: `python3 -m impacto.cli legal-list`.

## 5. Roteiro de 20 minutos

1. **(2 min)** Abrir com o problema, não com a tela: o dinheiro de impacto não falta, falta prova de
   que chegou e de que funcionou.
2. **(4 min)** Entrar como OSC. Diagnóstico → prontidão → projeto. Mostrar que a prontidão é
   calculada, não declarada.
3. **(4 min)** Trocar para Empresa. Explorar, apoiar, carteira. Mostrar que é o mesmo projeto, outro
   ângulo — um núcleo, não dois produtos.
4. **(5 min)** O indicador e a proveniência, com `gaps` à vista. **Este é o centro da apresentação.**
5. **(3 min)** Administração: auditoria, integridade das cadeias, interruptor.
6. **(2 min)** Fechar pelo que falta: ler em voz alta a tabela da seção 4. Quem decide precisa saber
   o que ainda depende de contrato e de advogado antes de qualquer promessa de data.

## 6. Antes de apresentar

- [ ] `python3 scripts/smoke_test.py --base <url>` — 27 verificações, todas verdes
- [ ] `python3 -m impacto.cli legal-list` — saber de cor quantas minutas bloqueiam
- [ ] Confirmar que a URL deixa claro que é staging
- [ ] Reler a seção 4 em voz alta; quem apresenta tem que conseguir dizer "isto não está ligado" sem
      hesitar
