# Contrato de Pagamento — Plataforma Impacto

> **MINUTA — DRAFT FOR LEGAL REVIEW — [VALIDAR JURÍDICO]**. Rascunho técnico escrito a partir do funcionamento real do
> software (v0.17.0), não de um modelo de contrato. **Não é aconselhamento jurídico e não pode ser publicado, exibido como
> vigente nem aceito por nenhum usuário sem revisão de advogado(a).** Campos entre `{{ }}` dependem de decisão do
> proprietário. Enquanto esta minuta não for aprovada, o banco se recusa a registrar aceite dela (ver
> `docs/LEGAL_FRAMEWORK.md`).

Versão da minuta: 2026-10-06 · Aplica-se à versão de software 0.17.0 · Chave: `payment`

## 0. ESTADO REAL, HOJE: PRODUCTION PAYMENT NOT CONFIGURED
0.1. **Não há provedor de pagamento configurado.** Sem conta, sem chave, sem identificador de preço, sem webhook assinado.
0.2. Logo: **nenhuma cobrança real foi processada por este software**. Todas as cobranças existentes no banco nascem
marcadas como simuladas, por coluna derivada do provedor (`is_simulated`), que ninguém consegue escrever à mão.
0.3. O relatório de receita mantém o simulado em colunas próprias e **nunca** o soma ao real.
0.4. Esta minuta descreve as condições que valerão **quando** o provedor for contratado e ligado. Até então, ela não pode
ser exibida como contrato vigente.

## 1. Objeto
Condições de cobrança da Plataforma contra a organização usuária: assinatura, cobrança avulsa, parcelamento, PIX e boleto.

## 2. Meios previstos na arquitetura
| Meio | Situação técnica | Observação |
|---|---|---|
| Cartão (avulso) | implementado na camada da Plataforma, **sem provedor** | token do provedor; a Plataforma não guarda número de cartão |
| Cartão recorrente (assinatura) | implementado desde a v0.11.0, **sem provedor** | ciclo e fatura em `invoices` |
| **Parcelamento** | implementado, **sem provedor** | modelado **à parte** da assinatura: número fixo de parcelas, vencimentos próprios, não renova, e a soma das parcelas tem de fechar com o total |
| PIX | instrução e prazo modelados, **sem provedor** | sem provedor não há cobrança de PIX: QR/copia-e-cola vem do provedor |
| Boleto | instrução e vencimento modelados, **sem provedor** | linha digitável vem do provedor |

2.1. Parcelamento **não é assinatura**, e a diferença é contratual, não só técnica: assinatura renova por prazo
indeterminado e pode reajustar; parcelamento é preço fechado dividido em parcelas, sem renovação.

## 3. Dados de cartão
3.1. A Plataforma **não armazena número de cartão, CVV nem validade**. Guarda apenas o token do provedor, a bandeira e os
**quatro últimos dígitos** — e há trava no banco que recusa qualquer tentativa de gravar mais que quatro dígitos nesse campo.
3.2. A administração da Plataforma **não lê** o token de cartão do cliente.

## 4. Confirmação de pagamento
4.1. Quem confirma pagamento é o **webhook assinado do provedor**. A tela nunca é fonte de verdade.
4.2. Evento sem assinatura conferida é **registrado e não produz efeito** (há restrição no banco impedindo que ele chegue a
"processado").
4.3. Reentrega do mesmo evento não duplica efeito; apenas conta a reentrega para a reconciliação.

## 5. Nota fiscal
5.1. **A Plataforma não emite nota fiscal hoje.** Não há provedor fiscal contratado nem integração com prefeitura.
5.2. Emissão de NFS-e sobre a assinatura é obrigação a cumprir pelo proprietário e depende de inscrição municipal, regime
tributário e provedor — decisões que não são de software.

## 6. Inadimplência
6.1. Fatura em aberto após o vencimento: `{{PRAZO DE TOLERÂNCIA}}`.
6.2. Consequência prevista: suspensão de recursos pagos, **com preservação do acesso gratuito e dos dados já criados**.
6.3. Multa e juros: `{{DECISÃO — limites legais aplicáveis}}`.

## 7. Perguntas abertas para o jurídico
1. Qual provedor será contratado, e sob qual contrato (adquirência, subadquirência, instituição de pagamento)? A resposta
   muda quem é responsável por chargeback.
2. Parcelamento com juros exige informação de CET — a Plataforma pretende cobrar juros? Se sim, há dever de informação
   específico.
3. PIX: a conta de recebimento é do proprietário ou de terceiro? Receber em conta de terceiro muda a natureza da operação.
4. Nota fiscal: município, código de serviço e regime — `{{CONTADOR}}`.
