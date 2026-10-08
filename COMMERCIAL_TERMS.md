# TERMOS COMERCIAIS — v0.21.0

> ⚠️ **SUPERADO EM PARTE — v0.27.0 (ADR-341): NÃO EXISTE MAIS ASSINATURA.** Tudo o que este documento diz
> sobre mensalidade, plano pago, trial, checkout, reajuste, portal e cancelamento descreve um modelo que o
> proprietário retirou do IMPACTO em 08/10/2026. O que continua valendo: núcleo gratuito por desenho, o que
> o dinheiro nunca compra, acesso gratuito ≠ autorização de cobrança, regras transacionais desligadas. O
> modelo vigente está em `docs/ECONOMIC_MODEL.md` e `MONETIZATION.md`; o inventário do que foi mantido,
> migrado, aposentado e removido está em `docs/execution/SUBSCRIPTION_INVENTORY.md`. O texto abaixo fica
> como histórico — ele explica contratos e decisões anteriores — e NÃO deve ser lido como regra atual.


**Pricing Version:** 2027.01
**Situação jurídica:** ⚠️ **as 11 minutas estão em `draft`.** Nenhuma foi aprovada, nenhuma está
vigente, e enquanto assim for o banco **recusa** registrar aceite legal (gatilho `acceptance_stamp`).
Este documento descreve o que o SISTEMA faz — não substitui parecer jurídico.

---

## 1. OS DOIS ATOS

| | **Acesso gratuito** | **Autorização de cobrança** |
| --- | --- | --- |
| O que a pessoa diz | "aceito usar, de graça, sob estes termos" | "autorizo cobrar este valor, nesta frequência, neste meio" |
| Exige meio de pagamento | não | sim |
| Registro | `offer_acceptances.consent_status = 'free_access'` | `... = 'authorized'` |
| Permite cobrar | **não** | sim, enquanto não for revogada |

**Um não implica o outro.** Aceitar os termos para usar a plataforma de graça não autoriza nenhum
débito, e o fim de um período gratuito não transforma um aceite no outro.

---

## 2. O QUE FICA REGISTRADO NO ACEITE

| Campo | O que prova |
| --- | --- |
| `offer_id` | qual oferta exatamente |
| `pricing_version` | que tabela de preço vigia |
| `plan_key` | qual plano |
| `price_version_id` | qual versão do preço — não o preço de hoje, o de então |
| `free_period_id` | qual gratuidade estava incluída |
| `billing_frequency` | única, parcelada ou recorrente |
| `payment_method` | cartão, boleto, pix ou combinado |
| `terms_version` | versão dos termos de uso aceitos |
| `privacy_version` | versão da política de privacidade |
| `commercial_terms_version` | versão dos termos comerciais |
| `accepted_at` | quando |
| `accepted_by` | quem (usuário) |
| `ip` / `user_agent` | de onde |
| `consent_status` | **se autorizou cobrança** |

Mais `revoked_at`, `revoked_by` e `revoke_reason` quando houver revogação.

O aceite é **imutável**: um gatilho recusa qualquer alteração, para todos. A reescrita mais
tentadora — transformar `free_access` em `authorized` depois do fato — é a primeira que ele barra.

---

## 3. REVOGAÇÃO

O cliente revoga a autorização quando quiser, por `POST /v1/commercial/consent/revoke` ou pela tela.
A partir daí nenhuma cobrança nova é feita — o gatilho de banco recusa.

Revogar **não apaga** o aceite. A prova de que ele autorizou em março continua existindo, e a de que
revogou em maio entra ao lado. Apagar a primeira destruiria a justificativa das cobranças já
ocorridas.

---

## 4. PERÍODO GRATUITO

| | |
| --- | --- |
| **2026** | tudo gratuito até 31/12/2026 23:59:59 (`America/Sao_Paulo`) |
| **Assinatura nova a partir de 2027** | 3 meses de **calendário** |
| **Ao terminar, sem autorização** | a conta volta ao plano gratuito permanente |
| **Ao terminar, com autorização** | a assinatura segue e a primeira fatura sai |

**Ao terminar sem autorização, a conta não é cobrada, não é suspensa e não perde dados.** Essa frase
está no produto, nos avisos e nos testes — não só aqui.

---

## 5. AVISOS ANTES DE QUALQUER COBRANÇA

90, 60, 30, 7 e 1 dia antes do fim do período gratuito, mais lembrete semanal nos últimos 30 dias,
mais um aviso no fim. Cada aviso diz, em letras, se haverá cobrança e o que acontece se a pessoa
não fizer nada.

---

## 6. REAJUSTE

Aumento para quem já assina exige **aviso de 30 dias** registrado em `price_change_notices`, imposto
por gatilho de banco: a tentativa de aplicar aumento sem aviso vigente é **recusada pelo banco**.

Redução não exige aviso. A carência protege quem paga, não a plataforma.

O preço aceito fica **congelado** em `subscription_prices`: um reajuste de tabela não altera
retroativamente o que alguém contratou.

---

## 7. MEIOS DE PAGAMENTO E PARCELAMENTO

| Frequência | O que é |
| --- | --- |
| `one_time` | cobrança única |
| `installment` | **uma** dívida dividida em N parcelas; acaba na última |
| `recurring` | cobrança que se repete enquanto a assinatura existir; não acaba sozinha |

Parcelamento **não é** recorrência. Confundir os dois é o que faz alguém achar que comprou em 12x e
descobrir que assinou 12 meses — por isso são campos distintos, e uma oferta recorrente com número
de parcelas é recusada.

**Boleto parcelado é exclusivo para pessoa jurídica com CNPJ.** Parcelamento em boleto é venda a
prazo, sem a garantia que a bandeira de cartão oferece; para pessoa física isso seria concessão de
crédito. Validado no servidor.

**Boleto não é oferecido como recorrente**: ele não tem débito automático, e chamar isso de
recorrência prometeria um automatismo que o meio de pagamento não tem.

---

## 8. CANCELAMENTO

Cancelar é um clique, sem obstáculo e sem multa. O acesso continua até o fim do período já pago.
Nenhum dado é apagado no cancelamento.

---

## 9. USO E EXCEDENTE

Avisos em 70%, 90% e 100% do limite do plano. O cliente pode definir um **teto de gasto mensal** e
escolher avisar ou parar ao atingi-lo.

**Exceder o limite do plano não gera cobrança adicional.** O excedente é interrompido. Não há preço
de excedente publicado, e sem preço a plataforma bloqueia em vez de inventar.

---

## 10. O QUE O PAGAMENTO NÃO COMPRA

Reputação, selo de verificação, impacto, evidência, veracidade de afirmação, elegibilidade a edital,
qualidade ou posição em match, destaque em ranking ou vitrine.

Isto é invariante de produto, travado por teste que varre o código: nenhum módulo de reputação,
impacto, match, selo, afirmação, equidade ou elegibilidade consulta qualquer tabela comercial.

---

## 11. PENDÊNCIAS JURÍDICAS

| Documento | Situação |
| --- | --- |
| `terms_of_use`, `privacy_policy` | `draft` — exigem aceite, e hoje o aceite é recusado |
| `subscription`, `payment`, `cancellation`, `refund` | `draft` |
| `b2b`, `b2g`, `marketplace`, `intermediation`, `cookies` | `draft` |

Aprovar minuta é ato humano com responsabilidade profissional. O sistema não aprova sozinho, e
`MONETIZATION_LEGAL_MATRIX.md` mantém as perguntas abertas visíveis.
