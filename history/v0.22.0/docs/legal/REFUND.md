# Política de Reembolso — Plataforma Impacto

> **MINUTA — DRAFT FOR LEGAL REVIEW — [VALIDAR JURÍDICO]**. Rascunho técnico escrito a partir do funcionamento real do
> software (v0.17.0), não de um modelo de contrato. **Não é aconselhamento jurídico e não pode ser publicado, exibido como
> vigente nem aceito por nenhum usuário sem revisão de advogado(a).** Campos entre `{{ }}` dependem de decisão do
> proprietário. Enquanto esta minuta não for aprovada, o banco se recusa a registrar aceite dela (ver
> `docs/LEGAL_FRAMEWORK.md`).

Versão da minuta: 2026-10-06 · Aplica-se à versão de software 0.17.0 · Chave: `refund`

## 0. Aviso indispensável
**Nenhum provedor de pagamento está configurado.** Não há, hoje, pagamento real a devolver: toda cobrança existente no
sistema é simulada. Esta minuta descreve a regra que valerá quando houver pagamento de verdade.

## 1. Hipóteses de devolução
| Hipótese | Proposta da minuta | Situação |
|---|---|---|
| Arrependimento em 7 dias (se o CDC incidir) | devolução integral | **depende de parecer** |
| Cobrança em duplicidade | devolução integral, sem discussão | regra clara |
| Cobrança de valor diferente do preço vigente | devolução da diferença | regra clara |
| Indisponibilidade prolongada | `{{DECISÃO}}` — sem SLA contratado, não há parâmetro | **depende de decisão** |
| Insatisfação após uso do ciclo | sem devolução; cancelamento encerra a renovação | regra clara |

## 2. Devolução parcial
2.1. O sistema registra devolução parcial com valor **entre zero e o total**, e recusa valor fora desse intervalo.
2.2. Devolução integral marca o valor devolvido como o total, por derivação — não por digitação.

## 3. Prazo
3.1. Da decisão: `{{PRAZO}}` a contar do pedido.
3.2. Do crédito: depende do meio e do provedor. A Plataforma **não promete** prazo de estorno de cartão, que não é dela.

## 4. Como pedir
Pela Plataforma, com registro de data, autoria e motivo. A decisão é registrada com fundamento, não com "negado".

## 5. Perguntas abertas para o jurídico
1. Incidência do CDC (a mesma pergunta das demais minutas, e a mais importante de todas).
2. Devolução por indisponibilidade sem SLA contratado: existe parâmetro legal supletivo?
3. Retenção de valor por uso proporcional é admissível?
