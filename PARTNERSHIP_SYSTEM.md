# PARTNERSHIP_SYSTEM — parcerias e demonstrações (v0.12.0)

**Entrada pública** (`POST /v1/help/partnerships`, `/v1/help/demo-requests`): sem login, **consentimento obrigatório** (versão e data gravadas), campo-isca anti-bot (`website`), limite de taxa por IP (5/h), validação de e-mail. Receber a proposta **não cria parceria nem compromisso**; a tela diz isso.

**CRM interno** (`/admin/central/parcerias`, só administração): etapas `received → qualification → contact → meeting → proposal → negotiation → approved → active` (+ `rejected`, `archived`), responsável, notas e **linha do tempo** (`partnership_activities`). Mover etapa registra de→para, autor e nota; o registro em `partnerships` só nasce quando a etapa vira `active`.

**Demonstrações**: fila com agendar (data/hora + link) e concluir; agendar envia e-mail à pessoa. Pedido vinculado ao usuário quando logado (aparece em “Minhas atividades”).

**LGPD:** e-mail/telefone/nome só para atender o pedido; visíveis apenas à administração; sem rastreamento de visitante; exclusão/anonimização seguem o fluxo de privacidade (**retenção de propostas não definida pelo jurídico — pendente**).

Limites: sem integração com CRM externo, sem agenda automática (o horário é combinado por e-mail), sem assinatura de termo de parceria (documento jurídico fora da plataforma).
