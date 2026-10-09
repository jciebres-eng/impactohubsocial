# Matriz legal e fiscal da monetização (v0.17.0)

**Isto não é parecer jurídico.** É pesquisa de base normativa em fonte oficial, com a fonte nomeada, o
texto conferido e a data da verificação. O grau de certeza declarado é o **da pesquisa**, não de um
parecer. Todas as nove receitas exigem advogado, e as que têm questão tributária aberta exigem contador.

Os documentos desta rodada são explícitos, e esta matriz os obedece ao pé da letra:

> "Não invente legislação. Não trate opinião do modelo como parecer jurídico."
> "NUNCA afirmar que uma estrutura é legal apenas porque não foi encontrada uma proibição."

**Resultado da auditoria: nenhuma carta é verde.** Cinco amarelas, quatro vermelhas. Como
`monetization_rule_gate()` recusa ativar regra sem carta verde, o estado do produto é **nada cobrável**
— e isso é o resultado honesto, não uma pendência de implementação.

As cartas vivem no banco (`monetization_legal_cards`, append-only) e são legíveis por quem tem conta em
`GET /v1/monetization/legal-cards`. Quem paga tem direito de ver a base da cobrança.

---

## Quadro geral

| # | Receita | Pagador | Carta | Situação da regra | Risco central |
|---|---|---|---|---|---|
| 1 | SaaS institucional (assinatura) | fundação, instituto, financiador | 🔴 | **recusada na v0.27.0 (ADR-341): não existe assinatura** | nenhuma — modalidade encerrada por decisão de produto |
| 2 | B2G — governança territorial | órgão público | 🔴 | **recusada** | contratação pública exige licitação como regra |
| 3 | Enterprise / ESG | empresa | 🟡 | revisão necessária | responsabilidade por afirmação de impacto |
| 4 | Implantação e integração | organização contratante | 🟡 | revisão necessária | enquadramento varia com o escopo |
| 5 | Marketplace — comissão | contratante ou prestador | 🔴 | **recusada** | enquadramento como instituição de pagamento |
| 6 | Taxa de êxito | quem recebeu o financiamento | 🔴 | **recusada** | instituição de pagamento, recurso público, CVM |
| 7 | Premium — prontidão avançada | organização que propõe | 🟡 | revisão necessária | arrependimento (CDC art. 49), nota por operação |
| 7 | Premium — preparação de documento | organização que propõe | 🟡 | revisão necessária | fronteira com profissão regulamentada |
| 8 | Inteligência territorial | órgão público, empresa | 🔴 | **recusada** | reidentificação; LGPD art. 12 |
| 3 | Taxa de serviço contratada no acordo (v0.26.0) | financiador (ou quem o acordo indicar) | 🟡 | revisão necessária | parecer de não configuração de arranjo de pagamento (Lei 12.865/2013); ISS; nota fiscal |

`refused` é mais forte que `review_required`: não significa "ainda não analisado", significa
**"analisado, e não implementar assim"**.

---

## Fontes consultadas

Texto literal conferido em **2026-10-06**, direto da fonte oficial:

| Fonte | O que foi lido |
|---|---|
| [Lei Complementar 116/2003](https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp116.htm) | lista anexa, itens **1.03** (processamento, armazenamento ou hospedagem de dados), **1.04** (elaboração de programas), **1.05** (licenciamento ou cessão de direito de uso de programas de computação) e **1.07** (suporte técnico em informática) |
| STF, **ADI 1945** e **ADI 5659** | julgadas em **18/02/2021**: incide **ISS**, e não ICMS, sobre o licenciamento de software; modulação de efeitos aprovada em **24/02/2021** |
| [Lei 12.865/2013](https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2013/lei/l12865.htm) | **art. 6º** (define "arranjo de pagamento" e "instituição de pagamento") e **art. 9º, V** (compete ao Banco Central autorizar a constituição e o funcionamento de instituição de pagamento) |
| [Lei 14.133/2021](https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2021/lei/l14133.htm) | **art. 2º, VII**: a Lei aplica-se a "contratações de tecnologia da informação e de comunicação" |
| [Lei 13.709/2018 — LGPD](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm) | **art. 5º, III e XI** (dado anonimizado, anonimização) e **art. 12** (dado anonimizado não é dado pessoal, salvo se a reversão for possível com esforços razoáveis) |

---

## Matriz "quem pode ser cobrado"

| Ator | Produto | Evento | Pode cobrar? | Base consultada | Risco | Situação |
|---|---|---|---|---|---|---|
| Organização que propõe (OSC) | entrada: cadastro, perfil, projeto, descoberta, rede, prontidão básica | — | **Não se cobra** | decisão de produto | — | ✅ gratuito por desenho, sem prazo |
| Organização que propõe | prontidão avançada, preparação de documento | operação entregue | **Provavelmente sim**, como serviço de software | LC 116/2003 itens 1.03/1.05 | médio | 🟡 revisar arrependimento e nota por operação |
| Fundação, instituto, financiador | Taxa de serviço contratada no acordo (3,5%) — substitui o SaaS por assinatura (v0.27.0) | acordo de financiamento assinado com a cláusula | **Provavelmente sim** | LC 116/2003 + ADI 1945/5659; Lei 12.865/2013 (parecer pendente) | baixo/médio | 🟡 parecer sobre não configuração de arranjo de pagamento; alíquota, município e nota |
| Empresa / ESG | portfólio e comprovação | contrato vigente | **Provavelmente sim** | idem | médio | 🟡 responsabilidade por afirmação de impacto |
| Órgão público | plataforma de governança | contrato administrativo | **Não por autosserviço** | Lei 14.133/2021 art. 2º, VII | **alto** | 🔴 exige licitação ou enquadramento em dispensa/inexigibilidade |
| Prestador / contratante | comissão de marketplace | contratação concluída | **Não assumir** | Lei 12.865/2013 arts. 6º e 9º | **alto** | 🔴 bloqueada pela ADR-022 |
| Quem recebeu financiamento | taxa de êxito | operação concluída | **Não assumir** | Lei 12.865/2013; recurso público; CVM | **muito alto** | 🔴 bloqueada pela ADR-022 |
| Órgão público, empresa | inteligência agregada | acesso contratado | **Não antes de RIPD** | LGPD art. 12 | **alto** | 🔴 reidentificação e definição de controlador |

---

## As cinco recusas, e por quê

### 🔴 SaaS por assinatura — recusa de PRODUTO, não jurídica (v0.27.0, ADR-341)

O proprietário retirou a assinatura do modelo econômico: o IMPACTO não vende acesso. A regra
`saas.institutional.funder` fica no catálogo como `refused`, com carta vermelha cuja base é a própria
decisão (DECISIONS.md, ADR-341). Nada a validar; o que havia de pendência tributária migra para a taxa de
serviço contratada no acordo (`contract.platform_service_fee`, amarela).


### 🔴 Taxa de êxito — o risco mais alto do produto

Cobrar percentual sobre recurso que transita pela plataforma pode caracterizar atividade de
**instituição de pagamento**: a Lei 12.865/2013, art. 6º, define instituição de pagamento como a pessoa
jurídica que, aderindo a um arranjo, tenha como atividade principal **ou acessória** executar instruções
de pagamento, gerir conta de pagamento ou executar remessa de fundos; e o art. 9º, V, atribui ao Banco
Central autorizar a constituição e o funcionamento dessas instituições.

Somam-se, se o recurso for **público**, as regras de parceria e de prestação de contas; e, se houver
captação junto a investidores, a discussão sobre oferta de valores mobiliários e a competência da CVM.
**Nenhuma dessas hipóteses foi analisada, e nenhuma pode ser descartada aqui.**

Há ainda um risco que não é jurídico e importa igualmente: **conflito de interesse**. Quem recomenda a
oportunidade sendo remunerado pelo êxito dela tem incentivo para recomendar a que paga mais. Os
documentos desta rodada listam isso entre os conflitos de monetização a tratar.

**A ADR-022 e a ADR-031 existem precisamente para evitar esse enquadramento:** a plataforma não custodia
nem processa aporte. Logo não existe transação dela sobre a qual cobrar percentual. Ativar esta regra
exige **antes desfazer a ADR-022**, que é decisão jurídica e não técnica — e o gatilho
`monetization_rule_gate()` recusa a ativação citando a ADR pelo nome.

### 🔴 Comissão de marketplace — mesma barreira, um passo antes

O marketplace hoje é **vitrine**: anúncio e contato. Não há contratação com pagamento dentro da
plataforma, então não existe transação sobre a qual cobrar. Construir a contratação com pagamento
reabre exatamente a questão da instituição de pagamento.

Pergunta aberta que vale pesquisa dedicada: se a plataforma pode cobrar comissão **sem tocar no
dinheiro** — faturando a comissão separadamente da parte, por fora da transação — e se isso muda o
enquadramento. Exige advogado especializado em meios de pagamento.

### 🔴 B2G — o produto está pronto, a forma de contratar não

A Lei 14.133/2021, art. 2º, VII, deixa claro que "contratações de tecnologia da informação e de
comunicação" estão sob a Lei. A regra geral é **licitação**; contratação direta depende de enquadramento
em dispensa (art. 75) ou inexigibilidade (art. 74), que **não foi analisado**.

Consequência direta para a implementação, e ela é concreta: **a plataforma não deve oferecer checkout de
autosserviço a órgão público.** Faturar um órgão sem procedimento prévio é o risco central desta
modalidade, e é um risco do cliente tanto quanto nosso.

### 🔴 Inteligência territorial — o maior ticket e o maior risco de privacidade

A LGPD, art. 12, diz que dado anonimizado **não é** dado pessoal — mas deixa de valer essa regra quando
a anonimização puder ser revertida com esforços razoáveis, considerando custo, tempo e tecnologias
disponíveis (art. 5º, III e XI).

E agregado territorial com contagem pequena é **exatamente** onde a reidentificação acontece: "um
beneficiário, neste bairro, com esta característica" identifica a pessoa sem citar o nome dela.

Antes de qualquer produto de dado é preciso: definir o **limite mínimo de agregação**, definir **quem é
controlador** (a organização que inseriu o dado ou a plataforma), estabelecer a **base legal** do
tratamento para finalidade de produto, verificar se os contratos com as organizações **permitem** uso
agregado, e produzir **RIPD** — com DPO nomeado, que o projeto ainda não tem.

---

## As cinco amarelas, e o que falta em cada

| Receita | O que está razoavelmente claro | O que falta |
|---|---|---|
| Enterprise / ESG | mesmo enquadramento tributário | responsabilidade da plataforma sobre afirmação de impacto que a empresa publique; acordo de tratamento de dados; regras de divulgação aplicáveis ao cliente |
| Implantação | é serviço técnico | **o item da lista de serviços varia com o escopo** (1.04 elaboração, 1.07 suporte); forma de contratação de quem executa, com risco trabalhista |
| Premium — prontidão | serviço de software por operação | direito de arrependimento (CDC art. 49) em serviço digital de execução imediata; nota fiscal por operação de valor pequeno e volume alto; se a OSC pode lançar como despesa de projeto |
| Premium — documento | idem | **fronteira com atividade privativa de profissão regulamentada** conforme o tipo de documento; responsabilidade por erro no documento gerado |
| Taxa de serviço contratada (v0.26.0) | prestação de serviço de software (orquestração, obrigações, conciliação, evidência) com percentual do valor contratado como **base de cálculo**; o financiador paga a taxa em cobrança própria e paga o projeto diretamente — nenhum valor de terceiro passa pela plataforma (ADR-284) | parecer confirmando que o desenho **não** configura arranjo de pagamento (Lei 12.865/2013) nem intermediação; alíquota e município do ISS; redação da cláusula no acordo; nota fiscal de serviço (não implementada); tratamento de cancelamento/devolução/financiamento parcial conforme o acordo |

Sobre a última: a plataforma já marca a saída como **rascunho sujeito a revisão humana** e exige
aprovação a quatro olhos (ADR-128). Isso mitiga, mas não resolve a pergunta de onde termina software e
começa peça técnica de responsabilidade profissional.

---

## O que falta, em uma lista

**Para o proprietário contratar:**

1. **Advogado** — as nove receitas. Prioridade: as quatro vermelhas.
2. **Contador** — enquadramento do ISS, município competente, regime tributário, emissão de nota fiscal.
3. **DPO** — pré-requisito do RIPD, que é pré-requisito do produto de dados.

**Para a engenharia, depois do parecer:**

4. Emissão de **nota fiscal** — não existe em nenhuma modalidade.
5. Redação final dos **Termos**: Uso, Assinatura, Cancelamento, Reembolso, e os específicos de
   marketplace e de administração pública.
6. **Limite mínimo de agregação** no produto de dados, se ele for construído.

**Nenhum desses itens é bloqueio técnico.** O que a engenharia entregou nesta fase é a estrutura que
impede cobrar antes de o parecer existir: a cobrança não liga sem carta verde, e duas receitas não ligam
de jeito nenhum enquanto a ADR-022 valer.

---

## Como isto é mantido

A carta é **append-only**: corrigir é emitir carta nova, porque a carta de ontem explica a decisão de
ontem. Marcar verde exige, por CHECK no banco, base normativa **mais** fonte nomeada **mais** data
**mais** certeza alta **mais** `needs_lawyer = false` — e um segundo CHECK recusa carta verde que tenha
pergunta aberta.

Quer dizer: não há caminho, nem para a administração da plataforma, que marque uma receita como liberada
sem antes registrar a base e dispensar o advogado por escrito. Era o que esta fase precisava produzir.
