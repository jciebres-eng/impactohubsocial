# Planos e direitos (entitlements)

Fonte de verdade técnica: `config/plans.v0.1.json`. Números = **placeholders**.

## Níveis
- **Básico (gratuito):** acesso geral.
- **Premium (assinatura):** recursos VIP/premium do papel.
- **Enterprise (contrato):** apenas Empresa.
- **Grant:** direito concedido por **voucher de gratuidade** (equivale a um plano por tempo/escopo definidos).

## Matriz resumida (o que é geral × premium)
| Área / recurso | Empresa | OSC | Prestador |
|---|---|---|---|
| Perfil, onboarding, notificações, LGPD self-service | Geral | Geral | Geral |
| Catálogo curado (consulta) | Geral | Geral (oportunidades dos programas) | — |
| Cofre de documentos e estados de verificação | Geral | Geral (armazenamento limitado) | Geral |
| Explicação do match (por quê/por que não) | Geral | Geral | — |
| Programas/chamadas | 1 (Básico) · múltiplos (Premium/Ent.) | — | — |
| Workflow de aprovação customizável, conflito/abstenção | Premium | — | — |
| Relatórios ESG avançados, exportações para auditoria | Premium | Exportação básica geral | — |
| Analytics territorial/causas (do próprio programa) | Premium | — | — |
| SSO/SCIM, API, SLA, white-label | Enterprise | — | — |
| Oportunidades/projetos ativos | — | 1 (Básico) · mais (Premium) | — |
| Assistente de IA (extração/rascunho) | cota Básica · maior no Premium | cota Básica · maior no Premium | cota Básica |
| Armazenamento de evidências | limite Básico · maior Premium | limite Básico · maior Premium | limite Básico |
| Modelos reutilizáveis de proposta/relatório | Premium | Premium | Premium |
| Analytics das **próprias** propostas | — | Premium | Premium |
| Convites/propostas por mês | — | — | cota Básica · maior Premium |
| Suporte prioritário (fila de atendimento) | Premium | Premium | Premium |

## Exceção explícita — prestadores
**Escalonamento, posição, destaque, selos e níveis do perfil de prestador não pertencem a nenhum plano nem a voucher.** Premium de prestador amplia **capacidade de trabalho** (cotas, modelos, analytics próprios), nunca **exposição** ou **posição**. Ver `PROVIDERS.md`.

## Invariantes
1. Plano/voucher/pagamento **nunca** altera elegibilidade, score, ordenação, shortlist ou visibilidade (match e diretório).
2. Direitos são lidos só via `EntitlementService`.
3. Rebaixamento (fim de assinatura/voucher): dados **nunca** são apagados; excedentes ficam somente-leitura por carência (hipótese: 60 dias) e exportáveis.
4. Segurança, LGPD, acessibilidade e trilha de auditoria são **sempre gerais**.
5. Quando coexistem assinatura, voucher e flag: prevalece o direito **mais favorável** por `featureKey`; descontos de voucher não acumulam com outro voucher salvo regra explícita.
6. OSC e Prestador Premium ficam atrás de `flag.premium_osc` / `flag.premium_provider` (desligadas no piloto); vouchers de gratuidade podem ativar o direito mesmo com a flag de cobrança desligada (grant).

## Testes obrigatórios
Para cada `featureKey`: Básico nega/limita, Premium permite, expiração derruba, grant concede, flag desligada nega cobrança. Teste de dependência: `matching` e `providers` não importam `billing`.
