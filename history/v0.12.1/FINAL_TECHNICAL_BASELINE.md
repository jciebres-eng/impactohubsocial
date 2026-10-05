# FINAL_TECHNICAL_BASELINE — Plataforma Impacto

**Veredito: TECHNICAL BASELINE APPROVED** para receber a camada de design.
**Não é** “pronto para produção aberta” nem “pronto para as lojas” — o que falta é externo (conteúdo oficial, jurídico, credenciais, provedores, publicação) e está declarado item por item.
Legenda: **PROVADO** (teste/execução neste ambiente) · **NÃO PROVADO** · **PENDENTE** · **BLOQUEADO POR SERVIÇO EXTERNO** · **PENDENTE DE VALIDAÇÃO HUMANA/JURÍDICA**.

## 1. Versão
`VERSION` = **0.12.1** (PATCH sobre 0.12.0: correções e endurecimento, sem nova capacidade nem mudança de contrato). `backend/pyproject.toml` e `web/package.json` acompanham. Snapshot dos documentos do v0.12.0 em `history/v0.12.0/`.

## 2. Commit e 3. Branch
Branch de trabalho: `inc/v0.12.0-central-conhecimento` (sincronizada com `origin`). Savepoints anteriores preservados: `savepoint/v0.10.0-base`, `savepoint/v0.10.1-ok`, `savepoint/v0.11.0-ok`, `savepoint/v0.12.0-ok`. O commit e a tag desta baseline constam em `FINAL_RELEASE_MANIFEST.json` (gerado ao final) e no relatório de entrega.

## 4. Arquitetura
Monólito modular em Python 3.13 (sem framework web pesado): Starlette para ASGI, roteador tipado próprio em `backend/impacto/http.py` onde **cada rota declara** autenticação, tipos de organização, papel mínimo, esquema de corpo/consulta, limite de taxa e papéis internos. Driver PostgreSQL próprio sobre libpq (`impacto/db/pq.py`). Camadas: `api/` (rotas) → `services/` (regras) → `engines/` (motores determinísticos e versionados: match, fiscal, elegibilidade, intenção, busca de soluções, `help-search@1.0.0`) → `db/`. Adaptadores isolados para storage, antivírus, e-mail e HTTP. Frontend React 19 + TypeScript com roteador próprio, empacotado por esbuild, servido como SPA/PWA pela própria API. Jobs operacionais em `impacto/jobs.py` (cobrança, varredura, `hub_ops`, retenção).

## 5. Banco
PostgreSQL 16, **152 tabelas**, **RLS em todas** (exceção: `schema_migrations`, sem privilégio para o papel da aplicação — provado por teste). Dois papéis: `impacto_owner` (dono do esquema) e `impacto_app` (aplicação, **sem BYPASSRLS**, provado). 10 migrations forward-only com checksum e lock consultivo. **PROVADO**: banco criado do zero (bootstrap + migrations) em **cada** execução da suíte; migração incremental `0010` aplicada sobre banco já populado; `migrate --check` sem pendências nem checksum alterado. Garantias de integridade no banco, não só na aplicação: quatro olhos por CHECK, imutabilidade de versões por gatilho, guardas de suporte/qualificação/cobrança, append-only de avaliações, gabarito de quiz inacessível à aplicação.

## 6. APIs
**475 operações** em `/v1`, documentadas a partir do código (`docs/API.md`, `docs/openapi.json`, `GET /v1/openapi.json`). **PROVADO**: o catálogo de rotas e o OpenAPI conferem (475 = 475). Erros em RFC 7807 (`type`, `title`, `status`, `code`, `request_id`; `error_id` em erro interno). Paginação uniforme (`items`, `limit`, `offset`, `has_more`, `next_offset`, limite 100). Dinheiro sempre inteiro em centavos; datas em ISO 8601 com fuso (**PROVADO** por teste).

## 7. Autenticação
scrypt para senhas, sessões com refresh rotativo e detecção de reuso, MFA TOTP com códigos de recuperação, OIDC opcional, cookie httpOnly + CSRF na web e Bearer para app nativo, limites de taxa por IP, bloqueio por tentativas, confirmação de e-mail e redefinição por token de curta duração. **PROVADO** por 19 testes de autenticação + jornada de navegador (cadastro → confirmação → login → logout encerrando a sessão).

## 8. Autorização
Quatro níveis por rota (`none`/`user`/`org`/`admin`), tipos de organização, hierarquia de papéis (viewer→owner), papéis internos (`editor`/`reviewer`/`support`), entitlements por funcionalidade e **RLS no banco** como última linha. **PROVADO em TODAS as 475 operações** (varredura automatizada): anônimo recebe 401; usuária comum recebe 403 em toda rota administrativa; administrador **sem MFA** recebe 403 em toda rota administrativa; nenhuma rota devolve 5xx a entrada anônima. IDOR de leitura **e de escrita** entre organizações: **PROVADO** bloqueado.

## 9. Billing · 10. Trial · 11. Vouchers · 12. Licenças
Tiers FREE/PLUS/PREMIUM/GOV, trial de 14 dias por organização (um só, anti-abuso por HMAC de e-mail/CNPJ), cobrança mensal/anual com cálculo **exclusivamente no servidor**, vouchers (percentual, valor fixo, licença, período), convênios e licenças administrativas com motivo e revogação, webhooks assinados e idempotentes. **PROVADO**: cliente não define preço/desconto/direito (422 em campo extra); voucher de uso único sob concorrência é aplicado uma vez; webhook duplicado concorrente grava uma linha; decisão de trial concorrente vale uma; cancelar mantém o acesso já pago; desconto nunca excede a base e é sempre inteiro. **BLOQUEADO POR SERVIÇO EXTERNO**: Stripe real nunca foi chamado (dublê HTTP), **preços não definidos**, sem nota fiscal, sem reembolso/chargeback.

## 13. Knowledge Hub · 14. CMS
Busca híbrida (FTS `pt_unaccent` + trigrama + vocabulário de assuntos + tela + público, com “por que apareceu”), ajuda contextual, guias com passo a passo/checklist/ação, biblioteca com modelos preenchíveis e versões, FAQ com votos, assistente **extrativo e ancorado** (`ai_used:false`, recusa explícita quando não há base), “Comece aqui” e pendências medidos por dados reais, academia com quiz corrigido no servidor e certificado **não oficial** verificável, eventos com lista de espera, suporte com SLA e escalonamento, CRM de parcerias, demonstração, pedido de teste, boletim com duplo opt-in, analytics sem texto livre (hash + tópicos, retenção 18 meses). CMS com fluxo rascunho→revisão→aprovado→publicado→arquivado, **quatro olhos garantido no banco**, versões imutáveis, conteúdo regulatório exigindo fonte e data, “revisão necessária” por validade/periodicidade e histórico de quem fez o quê. **PROVADO** por 62 testes de domínio + 9 de navegador. **PENDENTE DE VALIDAÇÃO HUMANA**: não existe conteúdo oficial — só exemplos rotulados (14 guias, 8 FAQs, 4 materiais, 1 curso, 1 evento, todos `demo=true`).

## 15. Testes · 16. E2E
**392 testes, 0 falhas, 0 ignorados** (`docs/evidence/test_run_v0.12.1.log`): 33 de unidade, 325 de API/integração com PostgreSQL e HTTP reais, 6 de arquitetura, **28 de navegador** (Chromium). Detalhe e método em `TEST_REPORT.md`. ANTES desta etapa: 359. DEPOIS: **392** (PASS 392, FAIL 0, SKIP 0). Jornadas de navegador cobertas: visitante (cadastro→confirmação→login→logout), busca→guia→assistente→demonstração, OSC com checklist/feedback/chamado respondido, academia com quiz e certificado verificado publicamente, evento com lista de espera e pedido de teste, CMS (editor não aprova o próprio conteúdo; revisor publica), administração com MFA real, página Plano com voucher e cancelamento, área bloqueada por perfil, rota inexistente, acessibilidade e contraste.

## 17. Segurança
Varredura de autorização completa, IDOR de escrita, concorrência, injeção, travessia, higiene de erros e redação de logs — detalhe em `SECURITY_AUDIT.md`. **Dois achados corrigidos nesta etapa** (vazamento de esquema em erros; leitura indevidamente vazia por RLS). **NÃO PROVADO**: pentest externo. **Nota de desenho**: a URL assinada de download é uma capability de 5 minutos (como URL pré-assinada de S3).

## 18. Dependências
**BLOQUEADO POR SERVIÇO EXTERNO — não executado, não declarado.**
```
cd web && npm install --package-lock-only --ignore-scripts
  → npm error 403 Forbidden - GET https://registry.npmjs.org/@capacitor%2fandroid
     "a package version that is forbidden by your security policy"
cd web && npm audit --omit=dev
  → npm error audit This command requires an existing lockfile.
pip install pip-audit  → ERROR: No matching distribution found for pip-audit
pip download requests  → ERROR: No matching distribution found for requests   (PyPI também bloqueado)
npm view axe-core version → 403
```
Impacto: **não há afirmação sobre vulnerabilidades de dependências**. Alternativa usada: versões pinadas e revisão da superfície (execução depende de `starlette`, `uvicorn`, `pydantic`, `PyJWT`, `cryptography`, `python-multipart`, `pypdf`, `reportlab`, `defusedxml`, `anyio` e libpq do sistema; o frontend de produção depende apenas de `react` e `react-dom`). **Ação obrigatória em CI antes de publicar:** `npm audit` e `pip-audit -r backend/requirements.txt`.

## 19. Acessibilidade
**PROVADO** por verificação automatizada em navegador, 25 combinações de página/viewport (1280 px e 390 px), tema claro e escuro: nome acessível em todo controle/botão/link, `lang="pt-BR"`, sem IDs duplicados, sem salto de nível de cabeçalho, foco visível, sem rolagem horizontal no celular, **contraste WCAG AA** (corrigido nesta etapa: 4.19:1 → 4.63:1) e zero erros de console. **BLOQUEADO**: axe-core (registry npm). **NÃO PROVADO**: leitor de tela, navegação completa por teclado em fluxos longos, zoom 200%, preferências de movimento.

## 20. Prontidão para mobile/API
**PROVADO**: autenticação por Bearer reutilizável por cliente nativo, refresh rotativo, CORS por allowlist (sem curinga, com `Vary: Origin`), contratos estáveis em OpenAPI, paginação e erros previsíveis, upload/download por URL temporária assinada, nenhum endpoint depende de HTML. **NÃO PROVADO**: nenhum app foi compilado, assinado ou publicado (Capacitor configurado em `mobile/`).

## 21. Build
`ruff check impacto tests` → **PASS** (`docs/evidence/ruff_v0.12.1.log`) · `tsc --noEmit` → **PASS** · `node build.mjs` → **PASS** (180 KB gzip, minificado, PWA com pré-cache) · `python -m compileall` → **PASS** · suíte completa → **PASS** · `migrate --check` → **PASS** · release (`scripts/make_release.py`) com verificação de manifesto → **PASS**.

## 22. Limitações (técnicas, nossas)
1. Conteúdo da Central é todo de exemplo; nenhuma regra fiscal aprovada. 2. Busca por vocabulário, sem embeddings; pesos são hipótese. 3. Assistente sem IA generativa. 4. SLA inicial é hipótese configurável. 5. Editor do CMS por JSON para curso/material/FAQ/evento. 6. Curso publicado não é editado no lugar. 7. `ContextHelp` ligado em 3 telas. 8. Bundle único sem code splitting (180 KB gzip). 9. Aviso multi-destinatário pode repetir para quem já recebeu quando um destinatário falha (escolha consciente: não perder aviso). 10. Desempenho medido só em volume de desenvolvimento. 11. Modo administrativo tem privilégio amplo no banco (contido por disciplina de código revisada e por testes).
## 23. Pendências externas (não dependem de código)
Conteúdo oficial e revisão jurídica/tributária · preços, nota fiscal e homologação do Stripe · SMTP com SPF/DKIM/DMARC · clamd e S3 reais · IdP real para SSO · pentest · auditoria de dependências em CI · axe e leitor de tela · contas e certificados Apple/Google, builds assinados e regras de compra das lojas · domínio, TLS, PostgreSQL gerenciado, backup fora da região e observabilidade de produção · RIPD/DPO e base legal por tratamento.

## 24. Instruções para o próximo agente (design)
Leia `DESIGN_HANDOFF.md` primeiro: ele lista rotas, componentes, estados (carregando/erro/vazio/sessão expirada/sem permissão), formatos de dado, o que não pode ser alterado e o que **não** é bug. Em resumo: trabalhe em tokens e componentes (`src/styles.css`, `src/ui/kit.tsx`) e nas páginas; **não** reimplemente backend, banco, autenticação, permissões ou cobrança; preserve os rótulos de honestidade (exemplo, origem, certificado não oficial, revisão necessária, preço não definido, SLA como meta interna); mantenha `tsc`, build e `make test` verdes — se um teste de contraste ou acessibilidade falhar, o design quebrou um invariante e o ajuste é no token, não no teste.
