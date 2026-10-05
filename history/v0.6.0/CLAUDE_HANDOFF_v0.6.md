# CLAUDE_HANDOFF_v0.6.md

## Objetivo
Receba este ZIP como base de trabalho. Não assuma que ele é production-ready. Faça uma auditoria técnica independente do código real, execute os testes, reproduza os fluxos e implemente a evolução necessária.

## Regras
1. Preserve o que estiver correto e comprovado.
2. Corrija qualquer inconsistência entre documentação e implementação.
3. Não trate SQLite/local auth como produção.
4. Evolua para PostgreSQL + RLS real, autenticação OIDC/MFA, RBAC por objeto, storage privado, upload seguro, observabilidade e CI/CD.
5. Faça testes negativos de isolamento entre tenants.
6. Transforme a UI local em produto Web/PWA de qualidade, mantendo acessibilidade e segurança contra XSS.
7. Implemente o fluxo de OSC e empresa, admin e analytics; não apenas telas demonstrativas.
8. Match Engine deve permanecer explicável, versionado e independente de plano/voucher.
9. Fiscal Engine deve permanecer versionado e baseado em fontes verificáveis; não inventar regra tributária.
10. Billing deve ter adapter real apenas quando gateway e credenciais estiverem configurados; não simular produção.
11. IA deve ser provider-agnostic e somente ativada com política de dados, chave e testes.
12. Crie migrations PostgreSQL executáveis, seeds controlados e testes de RLS.
13. Rode unit, integration, E2E, security, regression e smoke tests.
14. Faça build verificável de Web/PWA e, se o ambiente permitir, builds Android/iOS. Não alegue assinatura/publicação sem evidência.
15. Gere um novo ZIP FULL limpo, sem ZIPs aninhados e sem secrets.

## Entrega obrigatória
- FINAL_FULL_RELEASE.zip
- FINAL_RELEASE_AUDIT.md
- CHANGELOG.md
- DEPLOYMENT_CHECKLIST.md
- ENVIRONMENT_SETUP.md
- SBOM/dependency/license inventory quando possível
- matriz GREEN/YELLOW/RED
- evidência dos testes
- lista explícita do que ainda depende de conta, credencial, contrato ou validação profissional.

## Critério
Não quero uma resposta dizendo que está pronto. Quero código, testes, artefatos e evidências. Se uma parte não puder ser concluída por dependência externa, deixe a integração tecnicamente preparada e classifique-a corretamente.
