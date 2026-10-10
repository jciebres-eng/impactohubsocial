# Doações no modelo de 24 meses — nota de hipóteses (v0.33.0)

Esta nota NÃO acrescenta receita ao `24_MONTH_FINANCIAL_MODEL.md` nem ao modelo de 120 meses (`docs/analysis/economia_v0300`).
Motivo: a taxa sobre doações está INATIVA no catálogo (ADR-373) e não há provedor contratado. Receita que depende de
parecer e contrato não entra em projeção. O que fica registrado é só a aritmética, para quando (e se) a regra for ativada.

## Hipóteses do pacote (não validadas)

| Hipótese | Valor | Estado |
|---|---|---|
| Taxa de serviço sobre microdoações | 1,00 % (100 bps) | catálogo, inativa |
| Fundo de apoio ao beneficiário (opcional, exibido antes de pagar) | até 4,00 % (400 bps) | catálogo, inativa |
| Taxa sobre campanhas institucionais | 3,5 % / 1,5 % | **não está no catálogo**: o pacote não define o que distingue "institucional" nem a base; fica como texto |
| Tarifa Pix do provedor | desconhecida (tabela comercial, por contrato) | `provider_fee_schedules` = 0 bps no sandbox |
| Verba pública | nenhuma dedução automática | regra do pacote; sem código de cobrança não há o que deduzir |

## Aritmética (só para dimensionar — não é previsão)

Com a regra ativa a 1 %, cada R$ 100.000 de doações confirmadas gerariam R$ 1.000 de taxa calculada **antes** da
tarifa do provedor, de estornos e de impostos. Para a taxa cobrir um custo fixo mensal de R$ X, o volume mensal
confirmado precisaria ser 100 × X. Nenhum volume é assumido aqui porque não existe histórico: a plataforma não tem
nenhuma doação real.

O fundo de 4 % é opt-in do doador e, pelo desenho, pertence ao beneficiário (conta `beneficiary_fund` no razão), não à
plataforma — portanto não é receita.

## O que precisa existir para esta nota virar linha do modelo

1. Regra ativa com parecer (checklist jurídico itens 1–3).
2. Tarifa do provedor por contrato (entra como custo direto por transação).
3. Três meses de volume confirmado no provedor real, para estimar ticket médio e taxa de estorno a partir de dados, não
   de suposição.

Até lá, o modelo de 24 meses continua sem linha de doações, e o relatório econômico da v0.30.0 permanece válido.
