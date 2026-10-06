# ENTREGA AO DESIGNER — CAMADA COMERCIAL (v0.21.0)

Complementa `DESIGN_HANDOFF_FINAL.md` (v0.20.0), que cobre o produto. Este cobre a camada comercial,
que não existia naquela entrega.

---

## 1. O QUE MUDOU DESDE A ENTREGA ANTERIOR

Na v0.20.0 a plataforma **não tinha preço**. Todos os planos pagos mostravam "Preço não divulgado" e
o botão de contratar estava desabilitado. Não havia período gratuito, não havia distinção entre
aceitar e autorizar, não havia medição de uso para fins comerciais e **não havia uma única chave de
tradução comercial** nos três idiomas.

Agora há tudo isso. São quatro telas novas ou alteradas.

---

## 2. TELAS

| Tela | Rota | Estado |
| --- | --- | --- |
| **Preços** | `/planos` (pública) | nova |
| **Situação comercial** | `/conta/comercial` | nova |
| **Consumo** | `/conta/consumo` | nova |
| **Plano e cobrança** | `/conta/plano` | alterada — ganhou a faixa de período gratuito |

Todas construídas em `web/src/pages/commercial.tsx`, com os componentes do `ui/kit` existente. O CSS
novo está em `styles.css` (`.plan-grid`, `.plan-card`, `.plan-features`, `.plan-note`,
`.public-page`, `.row-warn`), seguindo a mesma folha e as mesmas variáveis.

---

## 3. A REGRA QUE NÃO PODE SER QUEBRADA NO REDESENHO

> **A interface não calcula data, prazo, preço, percentual nem estado comercial.**

Tudo chega pronto: `free_period_end`, `days_remaining`, `state`, `on_expiry`, `amount_cents`,
`percent`. Há teste que varre o frontend em busca de aritmética de datas e falha se encontrar.

Se o redesenho precisar de um dado que o backend não manda, **peça o campo** — não o calcule.

---

## 4. O QUE PRECISA CONTINUAR VISÍVEL

Quatro declarações que deixam a tela menos limpa e o produto mais honesto. Nenhuma pode ser
escondida atrás de um ícone, um tooltip ou um acordeão fechado:

1. **Modo sandbox** — "nenhuma cobrança real acontece", enquanto o provedor não for real;
2. **Tributos indefinidos** — onde houver preço;
3. **"a partir de … sob proposta"** — piso não é preço contratável;
4. **O que nenhum plano compra** — reputação, selo, evidência, match.

---

## 5. OS DOIS BOTÕES QUE NÃO PODEM VIRAR UM

Numa oferta aberta:

```
[ Aceitar acesso ]  (secundário)        [ Autorizar cobrança ]  (primário)
```

Aceitar acesso gratuito e autorizar cobrança são atos **diferentes**, com registros diferentes no
banco e consequências diferentes. Juntá-los num botão só — "Começar agora", "Continuar" — desfaria,
na tela, a separação que o produto inteiro protege, e o fim do período gratuito voltaria a ser
cobrança por omissão.

Pelo mesmo motivo, **revogar autorização** fica visível, não escondido em submenu.

---

## 6. AS TRÊS LINHAS DO CHECKOUT

```
Hoje você paga          R$ 0,00
Preço do plano          R$ 799,00 / mês
Primeira cobrança em    15 de maio de 2027
```

Mostrar só a primeira esconde o que vem depois. Mostrar só a segunda esconde que hoje não se paga
nada. As duas omissões produzem a mesma reclamação, em momentos diferentes.

---

## 7. TOM

A faixa de período gratuito **não é um alerta**. Quando não há autorização de cobrança, não existe
nada de ruim prestes a acontecer com aquela pessoa: se ela não fizer nada, continua no plano
gratuito, sem perder dados.

Sem vermelho, sem contagem regressiva ansiosa, sem "última chance". Destaque a partir de 30 dias
restantes, e a frase que acompanha é informativa:

> Você não precisa fazer nada: sem autorização de cobrança, a conta volta ao plano gratuito e nenhum
> dado é apagado.

Urgência artificial numa tela de cobrança é padrão escuro, e esta plataforma tem uma invariante
escrita contra isso.

---

## 8. ESTADOS A DESENHAR

Dez estados comerciais, todos com rótulo em português:

`FREE` · `FREE_EXPIRING` · `PAYMENT_METHOD_REQUIRED` · `COMMERCIAL_TERM_PENDING` · `PAID_ACTIVE` ·
`CANCELLED` · `SUSPENDED` · `PAST_DUE` · `GRACE_PERIOD` · `TERMINATED`

`PAYMENT_METHOD_REQUIRED` **não é erro**: é "faltam 30 dias ou menos e ninguém autorizou cobrança".
Desenhá-lo como falha assustaria quem está exatamente onde deveria estar.

Um estado sem rótulo aparece pelo código, nunca em branco — e há teste que confere a lista contra o
backend.

---

## 9. i18n

Dez namespaces, 82 chaves, três idiomas (`pt-BR`, `en`, `es`): `billing`, `pricing`, `subscription`,
`free_period`, `commercial`, `checkout`, `invoice`, `payment`, `cancellation`, `usage`.

O texto novo do redesenho entra no catálogo, não no componente. Há teste que exige o mesmo conjunto
de chaves nos três idiomas.

---

## 10. O QUE AINDA NÃO DÁ PARA DESENHAR

| Tela | Por quê |
| --- | --- |
| Formulário de cartão | o checkout redireciona ao provedor; não há captura própria |
| Boleto e Pix emitidos | exigem provedor contratado |
| Nota fiscal | exige provedor fiscal |
| Estorno e disputa | estados existem; fluxo não exercitado com provedor real |

Desenhar essas telas agora seria desenhar contra um backend que ainda não existe.

---

## 11. ACESSIBILIDADE

Vale o que já valia na v0.20.0: foco visível por teclado, contraste, movimento reduzido respeitado,
sem rolagem horizontal a 390px. O guard de largura (`min-width: 0`, `max-width: 100%`,
`overflow-wrap: anywhere`, tabela com rolagem própria) continua aplicado, e a grade de preços cai
para uma coluna no celular.

Nenhuma informação comercial pode depender **só** de cor — nem o destaque de 90% de consumo, nem o
estado da autorização.
