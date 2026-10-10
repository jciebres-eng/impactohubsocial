# Direito, contratos e fiscalidade — análise documentada e modelos (v0.34.0, pacote PARTE XIII)

> Não é parecer jurídico. É o mapa do que precisa de parecer, com o que o código já faz e os modelos de texto que exigem
> revisão profissional antes de qualquer publicação. Legislação citada pelo nome; a vigência e as orientações oficiais devem ser
> conferidas pelo advogado/contador no momento da ativação. Complementa `docs/donations/LEGAL_AND_PROVIDER_CHECKLIST.md`.

## 1. As três correções do responsável (10/10/2026) e como entraram no desenho

| Correção | O que o pacote presumia | O que vale agora | Onde |
|---|---|---|---|
| MROSC e repasses públicos | "todo repasse público exige conta em banco público e qualquer split para SaaS é proibido" | **não é regra universal**: o instrumento (termo de fomento/colaboração, convênio, edital), o regulamento do ente e a natureza da despesa decidem; licença de software só com recurso do projeto quando elegível, prevista ou autorizada e comprovada | ADR-379; `funding_source` + `public_instrument_ref`; obrigação nasce `exempt`; `authorize-public` com instrumento e justificativa (`finance.approve`); `test_05` |
| Certificação e prestação de contas | — | o IMPACTO **não retém** relatórios, evidências ou documentos para forçar pagamento; estado comercial separado da integridade, exportação e acesso | ADR-381; `never_blocks`; `test_11` |
| Reserva de 1,5 % e rendimento | plataforma poderia reter, manter em carteira ou render | **reserva é destinação contábil/contratual** da organização, sem custódia; a plataforma não retém nem remunera | ADR-380; regra no motor `success_fee` (inativável); nenhuma coluna de saldo |

## 2. Operações juridicamente distintas (não são a mesma coisa)

| Operação | Natureza | Documento provável | Quem emite | Evento |
|---|---|---|---|---|
| Doação de pessoa a OSC via provedor | liberalidade; não é receita da plataforma | comprovante de doação (não dedutível salvo caso); recibo da OSC conforme sua natureza | OSC (recibo); plataforma (comprovante informativo) | confirmação pelo provedor |
| Taxa de serviço da plataforma | prestação de serviço de software (LC 116/2003, itens 1.03/1.05/1.07) | NFS-e à organização | plataforma | obrigação devida → faturada |
| Patrocínio empresarial | contrapartida publicitária/institucional | nota fiscal/contrato | OSC | contrato |
| Aporte institucional em campanha | depende do instrumento (doação, patrocínio, convênio privado) | conforme instrumento | OSC | confirmação |
| Transferência pública (MROSC/convênio) | Lei 13.019/2014; Decreto 11.531/2023; regras do ente | plano de trabalho; prestação de contas no sistema do ente | ente / OSC | repasse |
| Serviço profissional no marketplace | prestação de serviço entre contratante e profissional; CDC quando aplicável | NFS-e do profissional; fatura da plataforma pelo fee (se houver) | profissional; plataforma | aceite de entrega |
| Crédito de IA pré-pago | serviço de software por uso | NFS-e | plataforma | compra do pacote / operação entregue |
| Financiamento (acordo) | contrato civil; sem custódia | contrato assinado; instrução de repasse | partes | ativação/quitação |

## 3. Temas por operação (o que o parecer precisa responder)

- **LGPD**: base legal do e-mail do doador (comprovante), do nome público (consentimento), dos dados exigidos pelo provedor
  (execução de contrato com o provedor — e a anonimidade perante o público, não perante o provedor); retenção dos registros
  financeiros (obrigações contábeis); registro de operações de tratamento.
- **CDC**: doador pessoa física × plataforma/OSC — informação prévia do preço total, política de devolução, atendimento; marketplace
  de serviços (quando o contratante é consumidor).
- **Arranjos de pagamento (Lei 12.865/2013; BCB)**: confirmar que a plataforma, sem receber/repassar valores, não é participante;
  o que muda se houver split na conta da plataforma (modelo recusado no código).
- **PLD/FT (Lei 9.613/1998; Circular BCB 3.978/2020)**: obrigações do provedor; o que a plataforma registra e como coopera
  (`donation_risk_cases`, sem retenção).
- **Tributário**: ISS sobre serviço de software; regime da pessoa jurídica titular; retenções em serviços profissionais; NFS-e.
- **Doações e financiamento coletivo**: natureza jurídica da "vaquinha" de OSC; regras de reembolso quando a meta não é atingida
  (termos exibidos ao doador); contrapartidas (se houver) e CDC.
- **MROSC / convênios / contratação pública**: elegibilidade de despesa com licença de software; vedação de taxa sobre repasse;
  contratação do SaaS pelo ente (Lei 14.133/2021).
- **Profissionais**: regras de conselho (psicologia, contabilidade…), responsabilidade, publicidade.
- **Reembolso, contestação, cancelamento**: política por modalidade; prazos do provedor; chargeback.
- **Transparência**: o que a página pública mostra (valores, estados, última atualização) e o que não mostra (identidade do doador
  anônimo, documentos privados).

## 4. Modelos de texto preparados (RASCUNHOS — exigem revisão profissional)

| Modelo | Onde está | Situação |
|---|---|---|
| Termos de campanha (`campaign-terms-2026-10-draft`) | aceitos no envio para revisão; texto a redigir | rascunho de versão, sem texto final |
| Avisos da política "gratuito até gerar valor" (7 tipos) | `impacto/services/remuneration.py` `NOTICE_TEXTS` | rascunho em linguagem simples |
| "O que esta campanha NÃO é" (página pública) | `donations.public_campaign` | rascunho |
| Comprovante de doação (`what_this_is`) | `donations.receipt_view` | rascunho |
| Aviso de preço antes de pagar (`costs_disclosure`) | página pública | rascunho |
| Política de doações e reembolso | não existe | a redigir com o jurídico |
| Contrato de serviço institucional (3,5 %) | não existe | a redigir |
| Termo de autorização de despesa com recurso público | registro `authorize-public` (instrumento + justificativa) | modelo de texto a redigir |

## 5. Condições para qualquer cobrança real

Ver `FREE_UNTIL_VALUE_POLICY.md` §7 e `docs/donations/LEGAL_AND_PROVIDER_CHECKLIST.md`. Resumo: contrato com provedor;
modelo de titularidade; parecer por tipo de receita; cartas legais verdes; termos aceitos; aviso prévio; NFS-e.
