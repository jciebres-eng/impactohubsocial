# PRODUCTION_READINESS — v0.16.0

**Veredito: REDE DE IMPACTO FECHADA E PRONTA PARA A ETAPA DE DESIGN. Pronta para homologação / piloto
controlado. NÃO pronta para produção aberta.**

O semáforo portão por portão, com a prova de cada um e a lista fechada do que esta versão **não** entrega, está em
**`RELEASE_READINESS.md`**. Em resumo: **30 portões**, 29 verdes e um amarelo declarado (navegador real nas 27
telas novas); os vermelhos continuam sendo os mesmos e **nenhum é de engenharia interna** — validação de segurança
externa que não foi contratada, camada de design que é a etapa seguinte, aplicativo nativo que não foi iniciado.

**Acrescentado em v0.16.0, e que pesa na decisão de produção:** a **cobrança real não está integrada**. Não há conta
no provedor, chave, nem preço criado — `provider_price_id` é nulo e o checkout **recusa cobrar** (503
`provider_price_missing`) em vez de tentar com valor inventado. Toda a camada da plataforma está pronta e testada
(versão de preço imutável, vigência, aviso obrigatório de 30 dias, aceite registrado, cotação com imposto,
idempotência de webhook); ligar o provedor é criar os dois preços na conta, gravar os identificadores e configurar a
chave — **sem mudança de código**. Ver `BILLING_V2.md`.

O que falta é majoritariamente externo (contas, provedores, jurídico, tributário) e de validação operacional (carga, pentest, build de contêiner/apps).

## Semáforo por área
| Área | Status | Evidência | Pendência para produção |
|---|---|---|---|
| Backend/API | GREEN | 625 operações; suíte verde (673 testes) | — |
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
| Monetização: trial, tiers, vouchers, convênios, licenças (v0.11.0) | GREEN (lógica) | 34 testes + 256 herdados | divisão PLUS×PREMIUM é hipótese |
| Cobrança Stripe (checkout, webhooks, portal, upgrade/downgrade) | YELLOW | testado só com dublê | conta Stripe, endpoint do webhook, Billing Portal, homologação em modo de teste; verificar mínimo de `trial_end` |
| Preços dos planos | RED | `plan_prices` NULL; contratação online recusada | proprietário define e cadastra (admin) |
| Avisos de trial/cobrança por e-mail | RED | só in-app | provedor de e-mail transacional |
| Nota fiscal, reembolso, chargeback, conciliação | RED | fora do escopo | tributário/financeiro |
| Perfis OS/OSCIP, instrumentos, trilha e mentoria (v0.10.1) | YELLOW | 23 testes novos + E2E admin com MFA | revisão jurídica da trilha e dos rótulos; validação de qualificações pela equipe; atendimento humano da mentoria |
| Cruzamento fiscal × elegibilidade (v0.10.1) | YELLOW | testes de isolamento e estados | regras fiscais/institucionais **reais** aprovadas por profissional |
| Rede da solução (v0.10.1) | GREEN (backend) / YELLOW (a11y) | testes de privacidade; lista acessível; sem grafo visual | usabilidade; grafo visual opcional |
| IA sobre documentos | RED (não implementada) | — | provedor, DPA, avaliação |

## Condições mínimas para um piloto fechado
1. Domínio + TLS + PostgreSQL + S3 + SMTP + clamd configurados (`docs/DEPLOYMENT.md`). 2. Primeiro admin com MFA. 3. `BILLING_PROVIDER=none`, planos pagos sem preço (tudo gratuito) **ou** Stripe homologado. 4. Minutas legais revisadas e publicadas. 5. Sem dados reais sensíveis até o RIPD. 6. Regras fiscais ocultas (nenhuma aprovada → tela vazia por design). 7. Editais reais cadastrados com URL oficial por curadoria. 8. Biblioteca: remover/ocultar dados DEMO, definir quem cura e quem aprova níveis de confiança, e publicar regras de moderação.

## Não declarar
Não declarar "solução comprovada" sem nível `evidenced/verified` concedido pela administração, nem "busca com IA/semântica vetorial". Não declarar "compliance", "segurança total", "benefício fiscal", "impacto comprovado" ou "publicado". A plataforma exibe disclaimers e só mostra dados cadastrados/verificados.

## Central de Conhecimento (v0.12.0) — acréscimo ao semáforo
| Área | Status | Evidência | Pendência |
|---|---|---|---|
| Central: backend/API | GREEN | 62 testes de domínio, 475 operações | — |
| Central: frontend | GREEN (funcional) / YELLOW (design, acessibilidade formal) | `tsc`, build, 5 E2E (4 jornadas) | auditoria axe/leitor de tela; camada de design |
| Conteúdo oficial | **RED** | só exemplos `demo` | redação, revisão jurídica/técnica e publicação pela equipe |
| Assistente / IA | YELLOW | extrativo e ancorado, `ai_used:false` | escolher provedor se quiser IA generativa (com DPA e testes) |
| Busca | YELLOW | vocabulário + FTS; pesos hipótese | calibrar com buscas reais; embeddings opcionais |
| Suporte/SLA | YELLOW | testado; SLA inicial hipótese; SMTP real não exercitado | validar metas com a equipe |
| Parcerias/demo/boletim | YELLOW | testado | base legal, retenção, SMTP real |
| Lint Python | GREEN | `ruff` limpo (`docs/evidence/ruff_v0.12.0.log`) | rodar em CI |
| Auditoria de dependências | YELLOW | **não executada** | `npm audit`/`pip-audit` em CI |

## Baseline técnica v0.12.1 — atualização do semáforo
| Área | Status | Evidência | Pendência |
|---|---|---|---|
| Autorização de **todas** as 475 operações | GREEN | varredura automatizada (anônimo, usuária comum, admin sem MFA) | — |
| Concorrência (eventos, certificados, vouchers, webhooks, trial) | GREEN | 6 testes com threads | carga concorrente em volume de produção |
| Higiene de erros / vazamento de esquema | GREEN | corrigido + teste de regressão | — |
| Índices de consultas reais | GREEN | `0010_v0121_indexes.sql` + `EXPLAIN` por índice | medição em volume de produção |
| Desempenho dos fluxos críticos | GREEN (dev) | p95 < 30 ms em 10 fluxos | teste de carga real |
| Migrations (zero e incremental) | GREEN | banco criado do zero em cada suíte + 0010 aplicada em banco existente; `--check` limpo | — |
| Acessibilidade base (incl. contraste AA claro/escuro) | GREEN | testes de navegador | axe + leitor de tela |
| Entrega de e-mail (outbox, reenvio sem duplicar) | GREEN (outbox) | 2 testes | **SMTP real** |
| Auditoria de dependências | **BLOQUEADA no ambiente** | npm 403; PyPI sem versões | executar em CI |
| Cobrança real, preços, nota fiscal, conteúdo oficial, IA generativa | RED/externo | — | decisão do proprietário / jurídico / provedor |

## Camada de integração (v0.13.0)
| Área | Status | Evidência | Pendência para produção |
|---|---|---|---|
| Fundação do hub (contratos, jobs, eventos, correspondências) | GREEN | 76 testes; `INTEGRATION_TESTING.md` | — |
| Segurança da camada (SSRF, XXE, HMAC, credencial, IDOR) | GREEN | `INTEGRATION_SECURITY.md` | egress controlado na infraestrutura (DNS rebinding); pentest |
| Adapters REST/SOAP (genérico, Senior, TOTVS) | **YELLOW** | só contra dublê | credencial de sandbox do cliente + homologação |
| Adapter de governo | **RED** | recusa agir por decisão de projeto | **AUTORIZAÇÃO EXTERNA NECESSÁRIA** (credenciamento Gov.br/Conecta) |
| SFTP | **RED** | contrato declarado, **não implementado** | implementar quando houver cliente real |
| Execução assíncrona | **YELLOW** | trabalhador no agendador do processo, `SKIP LOCKED` | fila dedicada se `queue_depth` crescer — **DEPENDÊNCIA DE INFRAESTRUTURA** |
| Retenção de jobs/eventos | **YELLOW** | só entregas têm expurgo (180 dias) | **VALIDAÇÃO JURÍDICA NECESSÁRIA** |
| Interface das integrações | **RED** | nenhuma tela | etapa de design (`DESIGN_HANDOFF.md` §11) |
| Carga/volume real | **RED** | não testado | teste de carga antes do piloto com parceiro |

## Camada de confiança (v0.14.0)
| Área | Status | Evidência | Pendência para produção |
|---|---|---|---|
| Verificação pública por terceiro | GREEN | 10 testes de API + 3 de navegador; sem dado pessoal | — |
| Assinatura avançada em duas camadas | GREEN | 7 testes + concorrência | — |
| Cadeia de custódia e integridade | GREEN | 4 testes, incluindo detecção de adulteração | — |
| Identidade por níveis (documento) | GREEN | conferência humana testada | treinar a equipe que vai conferir |
| Credencial profissional | GREEN | fluxo documental testado | definir com o proprietário quem confere |
| Acordos multiassinatura | GREEN | 8 testes | modelo de minuta é do cliente |
| Taxonomia, idioma, tema, cotas, honorários, geo, diagnóstico guiado | GREEN | 28 testes | conteúdo e tabelas de fonte a cadastrar |
| Formatos docx/xlsx/odt/ods/xml/pdf | **YELLOW** | ZIP reaberto e XML conferido | **abrir amostra no Office e no LibreOffice** (não existem neste ambiente) |
| QR Code | **YELLOW** | ida e volta no próprio pipeline | **ler com leitor comercial** antes de imprimir em escala |
| Assinatura qualificada (ICP-Brasil/gov.br) | **RED** | não implementada | **AUTORIZAÇÃO EXTERNA + HOMOLOGAÇÃO** |
| Biometria e prova de vida | **RED** | não implementadas (recusam) | provedor contratado |
| Carimbo de tempo de ACT (RFC 3161) | **RED** | não implementado (recusa) | ACT contratada |
| SMS como segunda camada | **RED** | não implementado | provedor de SMS |
| Edição on-line de Office/LibreOffice | **RED** | não implementada | **servidor WOPI** (Collabora/OnlyOffice/M365) |
| Rotação da chave do servidor | **YELLOW** | selos antigos deixam de conferir se a chave mudar | gerenciador de segredos + versionamento de chave |
| Retenção de custódia e identidade | **YELLOW** | sem expurgo automático | **VALIDAÇÃO JURÍDICA NECESSÁRIA** (apagar prova pode ser pior que guardar) |
| Pentest e carga | **RED** | não executados | antes do piloto aberto |
