# Changelog
Formato: Keep a Changelog. Datas AAAA-MM-DD.

## [v0.1] — 2026-10-04 — Checkpoint de documentação
### Adicionado
- Pacote inicial de documentação (produto, arquitetura, dados, API, match, fiscal, IA, segurança, LGPD, ledger, negócio).
- Modelo de planos/direitos (Empresa, OSC, Prestador) e sistema de vouchers (desconto e gratuidade).
- Regra de não-venda de escalonamento/posição de prestadores.
- Esquema SQL rascunho (não executado), JSON de planos e pesos do match.
- Registro de decisões (ADR 001–012), auditoria de release, prompt de continuação.
### Não incluído
- Qualquer código executável, testes, build, deploy, publicação.

## [v0.3] — 2026-10-04 — MVP local executável
### Adicionado
- API integrada com autenticação, sessões, organizações, papéis e isolamento lógico por tenant.
- CRUD de programas e oportunidades, documentos por hash, match persistido e auditoria.
- Painel web responsivo, manifesto PWA e service worker.
- Dockerfile, Makefile, migração de referência e testes ampliados.
### Limites
- Produção continua bloqueada sem PostgreSQL/RLS, OIDC/MFA, storage seguro, serviços externos e validações profissionais.
