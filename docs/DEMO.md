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

## 2. Por onde navegar

São **218 telas** servidas pelo roteador. O mapa delas — rota, componente, arquivo, quais tipos de
organização alcançam, se está em menu e quais operações de API cada uma chama — está em
[`execution/screen_inventory.json`](execution/screen_inventory.json) e
[`execution/screen_backend_map.json`](execution/screen_backend_map.json), e em forma navegável no
painel gerado por `scripts/make_screen_panel.py`.

Os seis tipos de organização veem menus diferentes. Uma demonstração que troca de tipo no meio mostra
a tese do produto melhor que qualquer slide:

| Tipo | Itens de menu | Onde a demonstração costuma render |
|---|---|---|
| OSC | 19 | diagnóstico → prontidão → projeto → candidatura → prestação de contas |
| Empresa | 14 | explorar projetos → carteira → relatórios recebidos |
| Governo | 16 | necessidades do território → edital → execução |
| Profissional | 25 | marketplace → proposta → acordo → validação |
| Apoiador | 12 | apoiar → carteira → prestação de contas recebida |
| Administração | 8 | compliance, auditoria, integridade, interruptor |

**119 das 218 telas não estão em menu nenhum** — abrem só por link direto. Em boa parte é correto
(detalhe de item, formulário de edição), mas é a primeira pergunta que o Designer vai querer
responder, e o painel permite marcá-las uma a uma.

## 3. O que a demonstração mostra de verdade

- **Isolamento entre organizações.** 321 das 322 tabelas têm RLS, com 667 políticas. Entrar com duas
  organizações lado a lado e tentar alcançar o dado da outra é a demonstração mais convincente que
  esta plataforma tem, porque o banco recusa, não a aplicação.
- **Proveniência de um número de impacto.** `GET /v1/indicator-values/{id}/provenance` devolve a
  cadeia inteira **e os elos que faltam**. Mostre um indicador com `gaps` preenchido: a plataforma
  dizendo o que o próprio número não prova é o diferencial, não um defeito a esconder.
- **Cadeias de hash.** `audit_verify`, `ledger_verify`, `value_verify` e `trust_verify` recalculam a
  cadeia na hora. Adultere uma linha pelo banco e rode de novo na frente de quem assiste.
- **Interruptor de emergência** (`/admin/interruptor`): desligar uma capacidade e ver a API recusar.
- **A trava jurídica**, abaixo. Ela parece um defeito e é o oposto.

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
