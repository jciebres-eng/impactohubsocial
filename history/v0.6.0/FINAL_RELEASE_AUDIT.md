# Auditoria final da entrega — Plataforma de Impacto Social v0.2

**Data:** 2026-10-04  |  **Escopo:** transformação do blueprint v0.1 em release de referência executável.

## Veredito

**Não é Production Ready.** É uma entrega executável para validação técnica local. O material original não continha frontend, backend, banco de produção, autenticação, mobile, CI/CD ou integrações; nenhum desses itens foi falsamente marcado como concluído.

## O que foi encontrado

- 38 arquivos documentais, PDF estratégico e um SQL explicitamente marcado como rascunho.
- Nenhum `package.json`, código TypeScript/Python de aplicação, build, migration executada, teste, Dockerfile ou pipeline.
- Manifesto SHA-256 original íntegro.
- Boa coerência estratégica: SaaS B2B, PWA primeiro, sem custódia de aportes, match explicável, fiscal cauteloso e prestadores sem ranking pago.
- Lacuna crítica: especificação não equivalia a software executável.

## O que foi corrigido/adicionado

- API local em `src/impacto/app.py` usando biblioteca padrão Python.
- Match determinístico com bloqueios, score, confiança, explicações, riscos e próxima ação.
- Entitlements e voucher com hash HMAC, resgate único, transação e evento de auditoria.
- Testes executáveis em `tests/`.
- `.env.example`, script de execução, notas de release e documentação da implementação.
- Este relatório substitui a classificação ambígua de “documentação completa” por estados verificáveis.

## Testes executados

Comando: `PYTHONPATH=. python3 -m unittest discover -s tests -v`

Resultado esperado e executado no empacotamento: **4 testes, 0 falhas**.

## Matriz final

| Área | Estado | Evidência/limite |
|---|---|---|
| Documentação/decisões | GREEN | Pacote original auditado e preservado |
| Match engine de referência | GREEN | Código + 3 invariantes/testes |
| Voucher/ledger de referência | GREEN | HMAC, uso único, transação, auditoria; sem auth |
| API local | YELLOW | Executa localmente; sem autenticação/tenant real |
| Banco de produção/RLS | RED | SQLite local; PostgreSQL não executado |
| Frontend/PWA | RED | Inexistente |
| Admin | RED | Inexistente |
| Auth/RBAC/MFA | RED | Inexistente |
| Upload/documentos | RED | Inexistente |
| IA | RED | Interface documentada, sem provedor |
| Fiscal | RED | Nenhuma regra aprovada/verificada |
| Compliance/KYB | RED | Não implementado |
| Billing real | RED | Sem gateway/credenciais |
| Segurança de produção | RED | Controles ainda não verificados |
| Observabilidade/CI/CD | RED | Não implementado |
| Web | RED | Não há aplicação web |
| Android/iOS | RED | Não há apps/builds |
| Publicação | RED | Nada submetido |

## Decisões arquiteturais

1. Preservar o SaaS B2B como núcleo e o match como componente explicável.
2. Entregar uma fatia vertical local em Python padrão para permitir execução sem inventar dependências ou credenciais.
3. Não chamar SQLite de banco de produção; a migração para PostgreSQL/RLS continua obrigatória.
4. Não ativar pagamentos, fiscal, IA ou publicação sem provedores, validação e testes correspondentes.

## Riscos e pendências reais

- Implementar autenticação OIDC, RBAC, isolamento multi-tenant e RLS.
- Migrar para PostgreSQL e executar migrations/integrações em ambiente descartável.
- Construir web/PWA, admin, upload privado e fluxo de documentos.
- Definir cloud, IdP, e-mail, storage, gateway e provedor de IA.
- Revisão jurídica, fiscal, contábil e LGPD; regras fiscais somente após fonte oficial e dupla aprovação.
- Testes de segurança, concorrência real, carga, restore e pentest.
- Contas organizacionais, domínio, assinatura, metadados e builds para lojas.

## Instalação e deployment

Local: `./run_local.sh`; testes: `PYTHONPATH=. python3 -m unittest discover -s tests -v`.

Deployment de produção: **não aplicável ainda**. O próximo gate é a Fase 1 da fila em `NEXT_STEPS.md`, com Postgres, auth/tenancy e CI. Nenhuma credencial está incluída.

## Estados de publicação

Web: RED / não iniciado. Android: RED / não iniciado. iOS: RED / não iniciado. Backend: YELLOW local, RED produção. IA: RED. Fiscal: RED. Compliance: RED. Segurança: RED.

## Addendum v0.3 — atualização após implementação

O conteúdo acima descreve o estado v0.2 e é preservado como histórico. A implementação v0.3 agora entrega **Web/PWA local GREEN para desenvolvimento**, **Backend local GREEN para desenvolvimento**, e **Match, documentos por hash, autenticação local, sessões, programas, oportunidades e auditoria GREEN no escopo local**. O painel está em `web/index.html` e a API integrada em `src/impacto/app.py`.

O cenário E2E validado foi: `login → criação de programa → criação de oportunidade → avaliação de match → registro de documento → leitura de auditoria`. O teste unitário v0.3 cobre seis casos, incluindo senha com PBKDF2, hard blocker, invariância de plano e seed/tenancy.

Continuam RED e não foram mascarados: PostgreSQL/RLS de produção, OIDC/MFA, upload privado/antivírus, storage S3/KMS, billing real, IA, regras fiscais aprovadas, compliance/KYB, observabilidade, backup/restore, CI/CD, pentest e publicação Android/iOS. O MVP local não deve receber dados reais.

## Addendum v0.4 — controles operacionais implementados

Foram adicionados contratos desacoplados para IA, storage, antivírus, billing e notificações; storage privado local em quarentena; scanner local por allowlist/hash; billing sandbox com verificação HMAC; backup e restore com `integrity_check`; varredura local de segredos; pipeline CI; template completo de ambiente; e migration PostgreSQL com RLS.

Validações executadas: 6 testes unitários, compilação Python, sintaxe shell, security scan sem achados, backup com SHA-256, restore com `integrity_check=ok` e testes dos adapters.

Esses artefatos resolvem a **preparação técnica local**, não substituem os serviços externos. O gateway de produção, IdP, S3/KMS, engine antivírus, collector de observabilidade, pentest, aprovação fiscal/compliance, domínio e contas das lojas continuam bloqueados por ausência de autoridade, credenciais ou validação profissional.

## Addendum v0.5 — núcleo SaaS

Implementados o catálogo de planos, assinaturas sandbox, entitlements por organização e dashboard operacional do tenant. O fluxo validado foi `login → catálogo de planos → assinatura sandbox → leitura de entitlements → dashboard`. O retorno de assinatura informa explicitamente que requer gateway externo; não há cobrança real neste ambiente.


## Addendum v0.6 — hardening realizado nesta revisão
- Corrigida validação estrita de SHA-256 em registros documentais.
- Adicionados limites de tamanho de request JSON.
- Adicionados headers básicos de hardening HTTP.
- Adicionado rate limiting local para tentativas de login.
- Adicionado logout que invalida a sessão.
- Match agora exige programa pertencente ao tenant e, quando informado, oportunidade pertencente ao mesmo programa/tenant.
- Programas e oportunidades passaram a validar campos e estados.
- Seed de demonstração deixou de ser automático; só ocorre com `IMPACTO_SEED_DEMO=1`.
- Em `IMPACTO_ENV=production`, a chave HMAC padrão de desenvolvimento bloqueia a inicialização.
- Testes locais ampliados para 8 casos.
- Limitação preservada: esta release continua sendo referência/local e não é uma implantação de produção. PostgreSQL/RLS, OIDC/MFA, storage privado, AV, billing real, IA, observabilidade e pentest dependem de infraestrutura/credenciais/validações externas.
