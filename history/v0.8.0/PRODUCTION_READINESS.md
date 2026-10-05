# PRODUCTION_READINESS — v0.7.0

**Veredito: PRONTO PARA HOMOLOGAÇÃO / PILOTO CONTROLADO. NÃO pronto para produção aberta.**
O que falta é majoritariamente externo (contas, provedores, jurídico, tributário) e de validação operacional (carga, pentest, build de contêiner/apps).

## Semáforo por área
| Área | Status | Evidência | Pendência para produção |
|---|---|---|---|
| Backend/API | GREEN | 165 operações; suíte verde | — |
| Banco/migrações/RLS | GREEN | testes RLS (API e SQL direto), restore verificado | PostgreSQL gerenciado, PITR, criptografia em repouso |
| Autenticação/sessões/MFA | GREEN | testes | WebAuthn opcional; política de senha corporativa |
| SSO OIDC | YELLOW | IdP falso | testar com IdP real (Google/Entra/Keycloak) |
| Autorização/multi-tenant | GREEN | testes IDOR/escalonamento | revisão externa |
| Match Engine | GREEN | testes + invariância | **calibrar pesos com dados reais** |
| Fiscal Engine | GREEN (motor) / RED (conteúdo) | motor testado; **nenhuma regra aprovada** | tributarista aprova regras; dupla aprovação |
| Compliance/KYB | YELLOW | verificações internas; CNPJ/CEIS `not_configured` | contratar/configurar fontes; fluxo manual existe |
| IA | YELLOW | fakes; provedor local padrão | escolher provedor, DPA, política de dados, testes reais |
| Arquivos/antivírus/storage | YELLOW | validações testadas; clamd/S3 fakes | clamd e S3 reais; política de retenção |
| Cobrança | YELLOW | sandbox/webhook testados; **Stripe real não** | conta, preços, nota fiscal, homologação, termos de reembolso |
| E-mail | YELLOW | outbox testado | SMTP/DKIM/SPF/DMARC |
| LGPD (técnico) | YELLOW | export/eliminação/retenção | RIPD, base legal, DPO, contratos de operador |
| Textos legais | YELLOW | minutas | **revisão jurídica obrigatória** |
| Frontend/PWA | GREEN | build + E2E | auditoria de acessibilidade (axe/leitor de tela), teste cross-browser |
| Android | YELLOW (CODE READY) | `mobile/setup.sh` | gerar, assinar, testar, publicar |
| iOS | YELLOW (CODE READY) | idem | macOS + Apple Developer |
| Observabilidade | YELLOW | logs/métricas/alertas de exemplo | Prometheus/Grafana/alertas, error tracking, traces |
| DevOps/CI/CD | YELLOW | arquivos escritos | **executar** build Docker, compose, CI, deploy |
| Backup/DR | GREEN (script) / YELLOW (operação) | restore verificado | agendamento, cópia fora da região, RTO/RPO |
| Performance/escala | RED | nenhuma medição | teste de carga, índices sob volume, pool, cache |
| Segurança externa | YELLOW | auditoria interna | pentest, varredura de dependências, WAF |

## Condições mínimas para um piloto fechado
1. Domínio + TLS + PostgreSQL + S3 + SMTP + clamd configurados (`docs/DEPLOYMENT.md`). 2. Primeiro admin com MFA. 3. `BILLING_PROVIDER=none`, planos pagos sem preço (tudo gratuito) **ou** Stripe homologado. 4. Minutas legais revisadas e publicadas. 5. Sem dados reais sensíveis até o RIPD. 6. Regras fiscais ocultas (nenhuma aprovada → tela vazia por design). 7. Editais reais cadastrados com URL oficial por curadoria.

## Não declarar
Não declarar "compliance", "segurança total", "benefício fiscal", "impacto comprovado" ou "publicado". A plataforma exibe disclaimers e só mostra dados cadastrados/verificados.
