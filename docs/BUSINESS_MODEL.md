# Modelo de negócio (hipóteses a validar — nenhum valor é dado observado)

Planos no código: `config/plans.json` (8 planos). **Preços de planos pagos estão `null` (“sob consulta”) — o proprietário define.**
Tentar contratar plano sem preço retorna 409 `price_not_defined`. Cobrança real só com `BILLING_PROVIDER=stripe` homologado (`billing_live`).

## Planos e o que liberam
| Papel | Plano | Preço | Destaques |
|---|---|---|---|
| OSC | Essencial | grátis | catálogo, match explicável, candidatura assistida, cofre, evidências, 2 projetos, 20 usos de IA/mês |
| OSC | Captação (premium) | a definir | **buscas salvas, alertas e rastreio de editais**, IA avançada, relatórios, 20 projetos |
| Empresa | Essencial | grátis | feed de projetos, match, carteira, relatórios básicos |
| Empresa | Impacto (premium) | a definir | relatórios avançados/exportação, alertas, gestão de conflito, **estimativas fiscais**, analytics territorial |
| Empresa | Enterprise | sob consulta | + SSO, exportação de auditoria, API |
| Profissional | Parceiro / Parceiro Plus | grátis / a definir | diretório, revisões, assinaturas (Plus atrás de flag desligada) |
| Governo | Governo | grátis | publicar editais/materiais, dados agregados |

## Regras de confiança (testadas)
`never_sellable`: posição de prestador, destaque, selo, **boost de match**, override de elegibilidade. Nenhum plano ou voucher altera match,
ordenação ou elegibilidade. Rebaixar plano **não apaga dados** (carência de 60 dias).

## Fontes de receita sugeridas
1. Assinatura B2B (empresas/institutos) — motor principal. 2. Planos premium de OSC (alertas e rastreio). 3. Implantação. 4. Vouchers como aquisição.
Evitar: comissão sobre aportes (a plataforma **não custodia nem intermedia** recursos), pagamento por posição, venda de selos.

## Serviços com profissionais parceiros
Contadores/advogados/elaboradores atuam como prestadores independentes (revisão e assinatura). Modelo de repasse/contratação **não implementado** — hoje o fluxo é solicitação → revisão → assinatura registrada. Definir contrato e responsabilidade com advogado.

## Economia unitária (medir, não presumir)
ACV, margem bruta, CAC, payback, retenção, conversão voucher→pago. Faixas citadas no relatório-fonte (piloto, essencial, enterprise) são **hipóteses de teste**, não preços.
Contabilização de gratuidade/desconto e emissão fiscal: **[VALIDAR com contador]**.

## Biblioteca de Soluções — notas de monetização (hipóteses, nenhuma ativa)
Permitido (capacidade, nunca ranking): limites maiores de rascunhos/comparações/combinações, alertas de novas soluções, relatórios de funil para autores, serviços profissionais de curadoria/validação. **Proibido por regra testada:** vender posição, destaque algorítmico, nota ou "selo" de comprovação. A busca, o match e as recomendações não leem plano/assinatura.

## v0.11.0 — níveis e trial
FREE · PLUS · PREMIUM (FULL) · GOV (contrato institucional). Trial de 14 dias FULL por organização, sem cartão. Preços mensal/anual **não definidos** (decisão do proprietário); a divisão de recursos PLUS × PREMIUM é **hipótese** a validar. Plano nunca influencia match/busca/ranking.
