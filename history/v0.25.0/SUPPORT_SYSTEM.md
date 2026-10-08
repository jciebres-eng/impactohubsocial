# SUPPORT_SYSTEM — suporte e chamados (v0.12.0)

**Fluxo:** pessoa abre chamado (`POST /v1/support/tickets`, categoria, assunto, mensagem, contexto da tela/artigo e até 5 anexos já enviados via `documents`) → fila da equipe (`/admin/central/suporte`) → resposta pública ou **nota interna** → resolvido → pessoa avalia (1–5) ou encerra.

- **Número sequencial** do chamado; estados: `open`, `in_progress`, `waiting_user`, `waiting_internal`, `resolved`, `closed`; prioridades `low|normal|high|critical`.
- **A pessoa não define prioridade/estado/SLA/responsável**: trigger `support_guard` normaliza inserções e restringe updates; RLS isola chamados por usuária; notas internas **não** são devolvidas à pessoa (teste).
- **SLA** (`support_sla`): primeira resposta, resolução e escalonamento por prioridade. **Valores iniciais são HIPÓTESE** (ex.: normal = 24 h / 5 dias / escala em 36 h) — ajustáveis por administradores (`PUT /v1/admin/support/sla/{priority}`); a tela do chamado mostra “meta interna, não é garantia contratual”.
- **Escalonamento**: job `hub_ops` marca `escalated_at`, eleva prioridade e registra nota interna.
- **Recorrência**: `recurring_candidates` lista (categoria, tela) com ≥ 3 chamados em 60 dias **sem artigo** → candidatos a novo guia/FAQ; a equipe vincula o chamado a um artigo (`to-article`).
- **E-mail**: respostas e mudanças geram aviso in-app e e-mail (respeitando `notification_prefs`), uma vez por evento (`notification_emails`). **SMTP real não foi exercitado** (outbox testado).
- Papéis: `support` (atende), `editor`, `reviewer` (via `staff_roles`; MFA obrigatório nas rotas internas); administradores veem tudo.
- Limites: sem canal de chat/telefone, sem SLA contratual por plano, sem integração com ferramenta de helpdesk, sem anexos na resposta da equipe além dos documentos existentes, sem pesquisa de satisfação além da nota 1–5.
