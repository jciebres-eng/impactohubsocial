# Administração da plataforma

Acesso: usuário com `is_platform_admin` **e** sessão com MFA verificado (TOTP ou `amr` do OIDC). Toda ação grava `audit_events`.
Criação do primeiro admin: `python -m impacto.cli create-admin` (não há admin padrão em produção; o admin de demonstração só existe com o seed fictício em desenvolvimento).

| Área | Endpoints (`/v1/admin/…`) | Controles |
|---|---|---|
| Visão geral | `overview` | contagens operacionais |
| Organizações | `organizations`, `…/status`, `…/compliance-checks` | suspender/reativar; executar verificações KYB |
| Compliance | `compliance-reviews`, `…/decide` | decisão humana com nota; algoritmo nunca bloqueia sozinho |
| Usuários | `users`, `…/status` | suspensão auditada |
| Credenciais profissionais | `credentials`, `…/verify` | conferência documental; sem auto-verificação |
| Editais | `calls`, `…/verify`, `…/status`, `call-sources`, `…/run` | curadoria manual e importação de fontes (JSON/RSS) com mapeamento |
| Regras fiscais | `fiscal-rules`, `…/action` | **dupla aprovação** por revisores distintos |
| Vouchers | `voucher-batches`, `…/action` | **dupla aprovação**; códigos só como HMAC |
| Cobrança manual | `manual-subscription`, `invoices`, `…/paid`, `grants` | sem pagamento falso: registra o que o operador confirma |
| Denúncias | `reports`, `reports/{id}` | triagem e resolução com texto |
| Auditoria | `audit`, `audit/verify` | consulta e verificação da cadeia de hash |
| Flags | `flags`, `flags/{key}` | `premium_osc`, `premium_provider`, `billing_live`, `public_directory_providers` |
| Jobs | `jobs` | histórico de execuções (`job_runs`) |

Interface: `/admin/*` na SPA (`web/src/pages/admin.tsx`).

## Não implementado no painel
Edição de pesos do match pela UI (versionados em arquivo/`call.weights`), moderação de mensagens (não há mensageria), painel de fraude/risco, gestão multi-tenant de “tenants” separados de organizações (a organização é a unidade de isolamento).
