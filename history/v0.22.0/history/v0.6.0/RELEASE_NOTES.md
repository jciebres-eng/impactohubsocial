# Release notes v0.2 — referência executável

- Adicionada API local sem dependências externas.
- Implementado match determinístico com hard blockers, score, confiança, lacunas, riscos e próxima ação.
- Garantida a invariância de plano/voucher no motor de match por construção e teste.
- Implementado resgate atômico de voucher com HMAC, uso único e auditoria encadeada.
- Adicionados testes unittest executáveis.
- Mantidas como RED as áreas que exigem produção real, credenciais ou revisão profissional.

## v0.3 — MVP local integrado

- Substituída a API mínima por um fluxo local completo de autenticação, tenancy lógico, programas, oportunidades, documentos, match e auditoria.
- Adicionado painel web responsivo com experiência PWA.
- Adicionado cadastro/login, PBKDF2, sessões expiráveis e papéis básicos.
- Adicionados Dockerfile, Makefile e migração de referência.
- Validado cenário HTTP E2E: login → programa → oportunidade → match → documento → auditoria.

## v0.4 — preparação operacional

Foram adicionados adapters desacoplados de IA, storage, antivirus e billing; quarentena local; backup/restore com verificação de integridade; CI; security scan; migration PostgreSQL com RLS; template completo de ambiente; e checklist de deployment. Integrações reais e validações profissionais permanecem bloqueadas até receberem configuração e autorização apropriadas.

## v0.5 — núcleo SaaS

Adicionados catálogo de planos, assinatura sandbox, entitlements por organização e dashboard operacional do tenant. O gateway real continua separado e explicitamente identificado como dependência externa.

## v0.6.0 — revisão/hardening para handoff Claude
- Hardening HTTP, validação, rate limiting de login e logout.
- Match com validação de vínculo tenant/programa/oportunidade.
- Seed demo opt-in.
- Guard de segredo em produção.
- Testes ampliados para 8 casos.
- Handoff explícito para próxima etapa de produção.
