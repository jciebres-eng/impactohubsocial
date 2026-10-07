# Changelog
Formato Keep a Changelog. Histórico anterior (v0.1–v0.6): `history/v0.6.0/CHANGELOG.md`.

## [0.7.0] — 2026-10-05 — Execução real sobre PostgreSQL
### Adicionado
- Backend Python (Starlette) com 165 operações `/v1`, OpenAPI e `docs/API.md` gerados do código.
- PostgreSQL 16: 56 tabelas, RLS em todas, triggers de integridade, cadeias de hash (auditoria e ledger), papéis `impacto_owner`/`impacto_app`.
- Autenticação de produção: scrypt, sessões opacas, refresh rotativo com detecção de reuso, MFA TOTP, OIDC (PKCE), lockout, rate limit, CSRF.
- Catálogo unificado de editais/fundos (privado, federal, estadual, municipal, internacional), importação de fontes, busca, buscas salvas e alertas (premium).
- Match Engine 1.0 (duas direções, bloqueadores, explicabilidade, confiança mínima), Fiscal Engine 1.0 (somente regras aprovadas), compliance/KYB, IA provider-agnostic.
- Candidatura assistida passo a passo, rascunhos com IA, revisão e assinatura de profissional habilitado, cofre de documentos com antivírus/storage privado.
- Execução: aportes (confirmação dupla), despesas, evidências, marcos, devolutivas, relatório de projeto, CSV; carteira da empresa; portal do governo (agregados k-anônimos).
- Cobrança (none/sandbox/Stripe/manual), planos, vouchers com dupla aprovação, entitlements.
- Frontend React/TS (PWA), cinco portais, tema claro/escuro; Capacitor (Android/iOS) preparado.
- LGPD técnico: exportação, eliminação, consentimentos, retenção; minutas legais [VALIDAR JURÍDICO].
- DevOps: Dockerfile, compose, nginx, CI, backup/restore verificado, métricas Prometheus.
- 111 testes automatizados (unit, integração, RLS/segurança, OIDC, E2E em Chromium).
### Segurança adicional
- Cliente HTTP com proteção SSRF (destinos internos bloqueados, sem redirecionamentos); verificação no boot de que o papel do banco respeita RLS.
### Alterado
- Match: sem nota quando a confiança < 50; datas dd/mm/aaaa; projetos bloqueados aparecem com motivos (`hidden_blocked`).
### Removido / substituído
- SQLite e autenticação de demonstração do v0.6.0 (preservados em `history/v0.6.0/`).
### Corrigido durante a construção (cada um com teste de regressão)
Corpo validado antes da autorização; UUID inválido → 500; falta de política UPDATE em `conflict_declarations`; nomes de assinantes ocultos pela RLS;
voucher sob SERIALIZABLE retornava 500; plano sem preço era comprável no sandbox; contadores de falha de login revertidos por rollback; raízes de palavras de segurança alimentar ausentes.
### Limites conhecidos
Ver `FINAL_RELEASE_AUDIT.md` §3 e `PRODUCTION_READINESS.md`.
