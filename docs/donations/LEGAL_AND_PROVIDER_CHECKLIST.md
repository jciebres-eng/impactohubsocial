# Doações — lista de verificação jurídica e de provedor (v0.33.0)

Nenhum item abaixo foi concluído por esta versão: são as condições para sair do sandbox. Quem decide está na coluna
"Dono". A plataforma NÃO é instituição de pagamento, NÃO tem custódia e NÃO cobra taxa até o item 3 estar fechado.
Este arquivo não é parecer jurídico.

| # | Item | Por que importa | Estado | Dono |
|---|---|---|---|---|
| 1 | Contrato com provedor de pagamento (Pix) em nome da organização responsável, com tarifa escrita | sem contrato não há Pix real; a tarifa entra em `provider_fee_schedules` | 🔴 não iniciado | responsável |
| 2 | Modelo de titularidade da cobrança: conta do beneficiário (não custodial) × conta da plataforma com split | o segundo modelo faz a plataforma intermediar valores (BCB/arranjos de pagamento); o código só suporta o primeiro | 🔴 decisão pendente | responsável + jurídico |
| 3 | Parecer sobre taxa de serviço (hipótese 1 %) e fundo de apoio (≤ 4 %) sobre doações; e 3,5 %/1,5 % para campanhas institucionais | sem parecer a regra fica INATIVA (`donation.platform_fee`); cobrar antes seria inventar preço | 🔴 | jurídico/contábil |
| 4 | Vedação de dedução automática em verba pública | regra do pacote; hoje nenhuma taxa é deduzida de nada; ao ativar, a regra precisa distinguir origem do recurso | 🟡 desenho previsto, sem ativação | jurídico |
| 5 | Termos da campanha (`campaign-terms-2026-10-draft`) e termos do doador | aceitos no envio para revisão; texto é RASCUNHO | 🔴 revisar texto | jurídico |
| 6 | Comprovante de doação: redação, numeração, dedutibilidade (Lei 9.249/95, Lei de Incentivo, OSCIP etc. — depende do beneficiário) | o comprovante diz expressamente que não é recibo dedutível | 🔴 parecer contábil | contábil |
| 7 | LGPD: base legal para e-mail do doador (cifrado), nome público opcional, dados exigidos pelo provedor (Asaas exige cadastro de cliente; Mercado Pago exige e-mail) | doação anônima pode não ser possível com certos provedores | 🔴 registro de operações + aviso de privacidade | DPO/jurídico |
| 8 | PLD/FT: definir que a obrigação de reporte é do provedor; a plataforma mantém trilha (`donation_risk_cases`) e coopera | a plataforma não é obrigada (Circular BCB 3.978 aplica-se a instituições autorizadas); confirmar com jurídico | 🟡 | jurídico |
| 9 | KYB do beneficiário: quem verifica, com quais documentos (CNPJ ativo, estatuto, representante, conta bancária no mesmo CNPJ) e validade | `org_kyb_verifications` só registra; processo não definido | 🔴 | compliance |
| 10 | Prestação de contas: a plataforma nunca bloqueia relatórios obrigatórios do beneficiário por taxa em aberto | regra do pacote; não existe bloqueio no código; teste `test_08` prova que gastos/atualizações entram sem condição financeira | 🟢 | — |
| 11 | Recorrência: instrumento do provedor (Pix automático/assinatura) + consentimento explícito + cancelamento a qualquer momento | `recurring_donations_enabled = false`; cancelamento já existe | 🔴 | responsável + provedor |
| 12 | Chargeback/estorno: fluxo com o provedor, prazos, quem avisa o beneficiário | o razão já trata reversão; o processo humano não existe | 🔴 | operação |
| 13 | Publicidade: toda campanha publicada passa por revisão humana (quatro olhos) e exibe custos antes do pagamento | implementado | 🟢 | — |
| 14 | Verba pública/Marco Regulatório das OSCs (Lei 13.019/14): doações não se misturam com recursos de termo de fomento | fora do escopo da v0.33.0; o `campaign_expenses.budget_line` permite separar linhas | 🟡 | jurídico |

## Condições para virar `LIVE_PAYMENT_PROVIDER_ENABLED=true`

Itens 1, 2, 3, 5, 6, 7 e 9 fechados + adaptador testado contra o sandbox oficial + ADR nova removendo a recusa em
`config.validate()` + ensaio no demo com dinheiro de teste do provedor + aprovação escrita do responsável.
