# ESPECIFICAÇÃO DE UX COMERCIAL — v0.21.0

Para o designer. Descreve **o que a interface precisa dizer** e **de onde cada dado vem**. O
tratamento visual é decisão do designer; o conteúdo e a procedência não.

---

## 1. A REGRA QUE VALE PARA TUDO

> **A interface nunca calcula data, prazo, preço, percentual nem estado comercial.**

Tudo vem pronto do backend. Quando duas camadas calculam a mesma coisa, elas divergem — e divergem
na fronteira, que é quando a pessoa está olhando. A tela que mostra "faltam 3 dias" enquanto a
cobrança acha que faltam 2 não é arredondamento: é um cliente cobrado num dia em que a plataforma
dizia que ele não seria.

Há teste que varre o frontend em busca de aritmética de datas perto de `free`/`period`/`trial` e
falha se encontrar.

---

## 2. TELAS

| Tela | Rota | Fonte |
| --- | --- | --- |
| Preços (pública) | `/planos` | `GET /v1/plans` |
| Situação comercial | `/conta/comercial` | `GET /v1/commercial/state` |
| Consumo | `/conta/consumo` | `GET /v1/commercial/usage` |
| Plano e cobrança | `/conta/plano` | `GET /v1/billing` + faixa de período gratuito |

---

## 3. FAIXA DE PERÍODO GRATUITO

Aparece em toda tela de conta enquanto houver período vigente.

**Dados:** `free_period_end`, `days_remaining`, `charge_authorized`, `on_expiry` — todos do servidor.

**Deve dizer, nesta ordem:**
1. até quando é gratuito (data por extenso, fuso `America/Sao_Paulo`);
2. quantos dias faltam;
3. o que acontece no fim — e isto muda conforme `charge_authorized`:
   * **sem autorização:** "Você não será cobrado. Se não fizer nada, sua conta continua no plano
     gratuito, sem perder dados."
   * **com autorização:** "A primeira fatura sai no fim do período gratuito. Você pode cancelar
     antes, sem custo."

**Tratamento:** destaque a partir de 30 dias restantes. Não usar vermelho nem linguagem de urgência
quando não há autorização de cobrança — não há nada de ruim prestes a acontecer com essa pessoa.

---

## 4. PÁGINA PÚBLICA DE PREÇOS

**Deve mostrar:** nome do plano; preço mensal ou anual conforme o seletor; **"a partir de R$ X — sob
proposta"** para planos com piso; "Preço não divulgado" quando não houver nem preço nem piso;
"Tributos ainda não definidos para este valor" onde houver preço; funcionalidades.

**Deve conter, em texto:** o que nenhum plano compra — reputação, selo, evidência, match. Esta é a
seção mais importante da página e a que mais custa escrever.

**Não deve:** criar urgência artificial, comparar com concorrente, nem exibir "mais popular" sem
dado que sustente.

---

## 5. SITUAÇÃO COMERCIAL

Dez estados, todos com rótulo em português (`ESTADO` em `web/src/pages/commercial.tsx`). Um estado
sem rótulo aparece pelo código — nunca em branco. Há teste que confere a lista contra
`free_period.STATES`.

**Autorização de cobrança** é uma seção própria, com a frase que o produto inteiro protege:

> Aceitar acesso gratuito e autorizar cobrança são atos diferentes. Aceitar os termos para usar a
> plataforma de graça não autoriza nenhum débito.

Quando há autorização, o botão de **revogar** fica visível — não escondido em submenu.

**Ofertas abertas** oferecem dois botões lado a lado, com peso visual diferente:
`Aceitar acesso` (secundário) e `Autorizar cobrança` (primário). Nunca um só botão que faça as duas
coisas.

---

## 6. CHECKOUT

Antes do clique, a tela precisa mostrar **três linhas separadas**:

```
Hoje você paga          R$ 0,00
Preço do plano          R$ 799,00 / mês
Primeira cobrança em    15 de maio de 2027
```

Mostrar só o preço do plano esconde que hoje não se paga nada; mostrar só "R$ 0,00" esconde o que
vem depois. As duas omissões produzem a mesma reclamação, em momentos diferentes.

Para parcelamento, acrescentar: "Parcelamento divide uma única cobrança. Não é assinatura."

---

## 7. CONSUMO

Tabela por métrica: recurso, usado, limite ("Ilimitado" quando `null`), percentual. Destaque a
partir de 90%.

**Deve dizer, em faixa:** "Exceder o limite do plano não gera cobrança adicional: o excedente é
interrompido."

**Teto de gasto:** campo de valor e escolha entre "Avisar e continuar" e "Parar o consumo". O padrão
é avisar — parar o trabalho de alguém sem que essa pessoa tenha pedido é pior do que avisá-la.

---

## 8. MENSAGENS DE ERRO

Toda mensagem comercial diz **a alternativa**, não só a recusa.

| Código | O que a mensagem precisa oferecer |
| --- | --- |
| `price_not_defined` | "solicite proposta comercial" |
| `boleto_installments_require_cnpj` | "para pessoa física, use cartão ou boleto à vista" |
| `installments_not_applicable` | explicar que recorrência não é parcelamento |
| `boleto_not_recurring` | "para cobrança recorrente use cartão" |
| `plan_limit_reached` | qual limite e como aumentá-lo |
| `spend_limit_reached` | "altere o teto para continuar" |

---

## 9. i18n

Dez namespaces comerciais, 82 chaves, nos três idiomas (pt-BR, en, es): `billing`, `pricing`,
`subscription`, `free_period`, `commercial`, `checkout`, `invoice`, `payment`, `cancellation`,
`usage`. Há teste que exige o mesmo conjunto de chaves nos três.

Antes da v0.21.0 havia **zero** chaves comerciais e toda a tela de cobrança estava em português
escrito no código.

---

## 10. O QUE A INTERFACE DEVE DECLARAR SEM QUE NINGUÉM PERGUNTE

1. **Modo sandbox** — enquanto o provedor não for real, a faixa fica visível: "nenhuma cobrança real
   acontece";
2. **Tributos indefinidos** — onde houver preço;
3. **Minutas em rascunho** — os documentos legais ainda não foram aprovados;
4. **Piso não é preço** — "a partir de" sempre acompanhado de "sob proposta".

Esconder qualquer um dos quatro deixaria a tela mais limpa e o produto menos honesto.
