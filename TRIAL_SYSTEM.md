# TRIAL_SYSTEM — solicitação de teste (v0.12.0)

O **trial de 14 dias** do cadastro já existia (v0.11.0; `TRIAL`/`billing.md`). A v0.12.0 acrescenta o **pedido de teste/extensão pela Central** sem criar segunda estrutura:

1. Dono da organização envia `POST /v1/help/trial-requests` (pessoas, finalidade, módulos, 7–60 dias, responsável). Um pedido em análise por vez.
2. Pedido fica **`requested`**. **Nunca é automático.**
3. Administrador decide (`POST /v1/admin/hub/trial-requests/{id}/decide`, **motivo obrigatório**): aprovar chama `monetization.start_trial`/estende `org_trials`; organização que já usou o trial recebe **409 `trial_used`** (anti-abuso do v0.11.0 preservado); recusar registra o motivo.
4. A pessoa é avisada (in-app e e-mail conforme preferência). Painel `/admin/central/testes`: pedidos, ativos, vencendo, convertidos/encerrados, uso por organização **derivado das tabelas reais**.
- “Conversão” = assinatura paga confirmada pelo provedor (**Stripe real não exercitado**).
- Limites: sem limite de uso por módulo durante o teste (os direitos seguem o plano efetivo); sem cobrança; preços continuam **não definidos**.
