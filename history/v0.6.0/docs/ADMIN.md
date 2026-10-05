# Painel administrativo (especificação)

Módulos: usuários · empresas · OSCs · prestadores · projetos/necessidades · matches (leitura) · denúncias · documentos/compliance · auditoria · **regras fiscais (dupla aprovação)** · critérios · configurações · conteúdo · métricas.

## Billing e vouchers (Super Admin)
Planos e versões · assinaturas (status, cancelar/estender com motivo) · **criar lote de vouchers** (tipo, valor, escopo, limites, validade, campanha) · aprovar gratuidade acima do limiar · pausar/revogar · exportar lote (protegido) · relatórios de resgate e conversão · flags (`premium_osc`, `premium_provider`, `billing_live`).

## Controles
MFA obrigatório; papéis mínimos (Super Admin, Financeiro, Suporte, Compliance, Conteúdo); acesso a conteúdo sensível de cliente só excepcional e auditado; toda ação administrativa gera `audit_event`; admin **sem** ferramenta para alterar posição de prestador ou score.
