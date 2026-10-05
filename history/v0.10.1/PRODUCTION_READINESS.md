# PRODUCTION_READINESS — v0.10.1

**Veredito: PRONTO PARA HOMOLOGAÇÃO / PILOTO CONTROLADO. NÃO pronto para produção aberta.**
O que falta é majoritariamente externo (contas, provedores, jurídico, tributário) e de validação operacional (carga, pentest, build de contêiner/apps).

## Semáforo por área
| Área | Status | Evidência | Pendência para produção |
|---|---|---|---|
| Backend/API | GREEN | 358 operações; suíte verde | — |
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
| Frontend/PWA | GREEN | build + E2E (v0.7–v0.9) | auditoria de acessibilidade (axe/leitor de tela), teste cross-browser |
| Android | YELLOW (CODE READY) | `mobile/setup.sh` | gerar, assinar, testar, publicar |
| iOS | YELLOW (CODE READY) | idem | macOS + Apple Developer |
| Observabilidade | YELLOW | logs/métricas/alertas de exemplo | Prometheus/Grafana/alertas, error tracking, traces |
| DevOps/CI/CD | YELLOW | arquivos escritos | **executar** build Docker, compose, CI, deploy |
| Backup/DR | GREEN (script) / YELLOW (operação) | restore verificado | agendamento, cópia fora da região, RTO/RPO |
| Performance/escala | YELLOW | `loadtest_v0.8.0.json` (núcleo) e `search_perf_v0.9.0.json` (busca: p95 ≈ 474 ms, 5.000 soluções sintéticas, 1 processo) | carga concorrente, hardware de produção, cache, particionamento de eventos |
| Biblioteca de Soluções (backend) | GREEN | 31 testes + SQL direto + RLS | calibração com dados reais |
| Biblioteca — busca/relevância | YELLOW | qualidade em 9 consultas; sensibilidade dos pesos | **sem embeddings**; pesos = hipótese; avaliação com usuários reais |
| Biblioteca — IA | RED (não implementada) | copiloto ancorado e rascunho por regras (`ai_used:false`) | provedor, política de dados, avaliação |
| Biblioteca — confiança/curadoria | YELLOW | fluxo e travas testados | **equipe humana de curadoria** é requisito operacional |
| Biblioteca — conteúdo | RED | só 7 soluções DEMO | cadastro/curadoria de conteúdo real |
| Biblioteca — frontend | GREEN / YELLOW (a11y) | build + 3 E2E | axe/leitor de tela, teste de usabilidade |
| Segurança externa | YELLOW | auditoria interna | pentest, varredura de dependências, WAF |
| Camada institucional (v0.10.0) | YELLOW | 51 testes novos; motor e fluxo editorial verdes | **revisão jurídica dos catálogos e regras**, publicar regras reais (2 aprovadores), calibrar maturidade, bases governamentais inexistentes |
| Perfis OS/OSCIP, instrumentos, trilha e mentoria (v0.10.1) | YELLOW | 23 testes novos + E2E admin com MFA | revisão jurídica da trilha e dos rótulos; validação de qualificações pela equipe; atendimento humano da mentoria |
| Cruzamento fiscal × elegibilidade (v0.10.1) | YELLOW | testes de isolamento e estados | regras fiscais/institucionais **reais** aprovadas por profissional |
| Rede da solução (v0.10.1) | GREEN (backend) / YELLOW (a11y) | testes de privacidade; lista acessível; sem grafo visual | usabilidade; grafo visual opcional |
| IA sobre documentos | RED (não implementada) | — | provedor, DPA, avaliação |

## Condições mínimas para um piloto fechado
1. Domínio + TLS + PostgreSQL + S3 + SMTP + clamd configurados (`docs/DEPLOYMENT.md`). 2. Primeiro admin com MFA. 3. `BILLING_PROVIDER=none`, planos pagos sem preço (tudo gratuito) **ou** Stripe homologado. 4. Minutas legais revisadas e publicadas. 5. Sem dados reais sensíveis até o RIPD. 6. Regras fiscais ocultas (nenhuma aprovada → tela vazia por design). 7. Editais reais cadastrados com URL oficial por curadoria. 8. Biblioteca: remover/ocultar dados DEMO, definir quem cura e quem aprova níveis de confiança, e publicar regras de moderação.

## Não declarar
Não declarar "solução comprovada" sem nível `evidenced/verified` concedido pela administração, nem "busca com IA/semântica vetorial". Não declarar "compliance", "segurança total", "benefício fiscal", "impacto comprovado" ou "publicado". A plataforma exibe disclaimers e só mostra dados cadastrados/verificados.
