# Plataforma Impacto — v0.18.0

**Infraestrutura digital de conexão, estruturação, financiamento, execução, acompanhamento e comprovação de
impacto** para OSCs, empresas e fundações, profissionais e órgãos públicos. Um núcleo, várias experiências: cada
papel entra no mesmo ciclo de impacto — do contexto à evidência — sem produto separado, sem domínio duplicado e sem
permissão frouxa.

> **Estado:** camada de impacto contextualizado fechada (equidade, território, referenciais, integridade de alegação, reputação, selos, formulários inteligentes e responsabilidade); **tecnicamente pronta para a etapa de design**, que é a próxima; para piloto controlado, leia primeiro `RELEASE_READINESS.md` §5 (o que esta versão NÃO entrega). **Não publicado** em nenhuma loja ou domínio. Android/iOS: código pronto, **não construídos**. Leia `PRODUCTION_READINESS.md` e `FINAL_RELEASE_AUDIT.md` antes de qualquer decisão.

**Novo no v0.18.0 (interoperabilidade de referenciais de impacto, equidade e confiança):** a rodada implementa uma
tese só — **impacto não é quantidade; impacto é resultado contextualizado.** "50 pessoas numa comunidade indígena
remota" não é automaticamente menos impacto que "5.000 pessoas num centro urbano", e a consequência é
desconfortável de propósito: **sem denominador declarado com fonte, data e método, não existe número normalizado**
(sete métodos, cada um dizendo qual denominador exige), a avaliação de equidade **não produz nota**, e a comparação
entre projetos devolve `comparable: false` com os motivos — **nunca um veredito**. Entram: **território como
catálogo** separando `from_official_load` do conhecimento da plataforma (as 27 UFs semeadas dizem "conferir na carga
oficial"); **registro de 19 referenciais** (ODS, ESG, GRI, ISSB, TCFD, TNFD, IRIS+, SROI, MCDA, LCA e outros) com
escada de relação de **seis degraus que para em `audited`** — `certified` é recusado por gatilho, porque a
plataforma não é organismo certificador; **materialidade** com `is_material` **derivada** da lente e do limiar;
**integridade de alegação** com 11 regras determinísticas e situação **derivada** (não existe coluna de situação em
`claims`), revisão humana **por convite nomeado** de outra organização, e a marca que a revisão qualifica sem
apagar; **reputação explicável em seis dimensões e SEM nota única** (divergência declarada dos prompts: nota única
vira ranking, e ranking vira critério de acesso), em que organização nova **começa sem medida, não com nota baixa**,
órgão público recebe perfil de governança sem nota e pessoa física não tem perfil público, com contestação que
aparece no próprio perfil e correção que gera ponto novo; **motor de selos** cujo critério é avaliado **em SQL** —
a aplicação não tem INSERT em `seal_awards`, então nenhuma rota concede selo sem critério — com definição
versionada e imutável, revogação como fato novo e **zero definições embarcadas**; **busca incremental com
procedência em cada sugestão** e componente que **nunca sobrescreve** o que a pessoa escreveu em silêncio; e
**responsabilidade** como responsável × papel × escopo × período × decisão × **versão**, separada da assinatura,
com quatro-olhos declarado em dado.

**1.223 testes, 815 operações, 285 tabelas, 31 migrações.** O que esta versão **não** entrega continua escrito com
nome: as 169 metas oficiais dos ODS e os dados do IBGE **não foram carregados** (a rede do ambiente alcança só
registros de pacote — a estrutura e os importadores estão prontos); mapeamento para GRI/ISSB/IRIS+ depende de
decisão de produto **e** jurídica; nenhum selo publicado; nenhuma arte de selo. Comece por
`IMPACT_FRAMEWORK_AUDIT.md`, `CLAIM_INTEGRITY.md`, `REPUTATION_ARCHITECTURE.md`, `SEAL_ENGINE.md`,
`SMART_FORMS.md`, `RESPONSIBILITY_ENGINE.md` e `FINAL_IMPACT_FRAMEWORK_REPORT.md`.

**Novo no v0.17.0 (camada econômica, legal e de pagamento):** a rodada inverte a ordem do roteiro a pedido do
proprietário — **monetização, pagamento e auditoria legal vêm antes do design** — e implementa uma tese só: **o
proponente não pode ser o pagador principal.** Cadastro, perfil, projeto, descoberta, rede e acompanhamento básico
são **gratuitos e permanecem gratuitos** (ADR-173, que muda a regra comercial da v0.16.0). Entram: **Programa** como
entidade de primeira classe, com objetivo obrigatório e três funções que separam o declarado do medido
(`program_financials` distingue **gasto** de **comprovado**; `result_chain` carrega a força declarada de cada elo
sem promover hipótese a evidência; `territorial_gap` leva a qualidade da evidência por território); **Value Ledger**
separado da cobrança, com a aplicação **sem INSERT** na tabela e nenhuma linha de base nascendo com número;
**monetização com portão legal no banco** — nove regras, **zero verdes, nenhuma ativa**, e `green_needs_evidence`
recusando verde sem fonte porque ausência de proibição não é permissão; **arquitetura de pagamento** com cartão,
recorrente, **parcelamento modelado à parte da assinatura**, PIX e boleto, toda marcada `PRODUCTION PAYMENT NOT
CONFIGURED` porque é o estado verdadeiro, com `is_simulated` derivada do provedor e irreescrevível; **onze documentos
legais versionados** com aceite que guarda o **sha256 do texto aceito** — e o banco **recusando registrar aceite de
minuta não revisada por advogado(a)**, o que trava o produto de propósito; e o **registro de 28 motores
operacionais** com cinco testes que provam que IA aqui é motor, não chatbot.

**(v0.17.0: 961 testes, 749 operações, 253 tabelas, 24 migrações.)** O que aquela versão **não** entregou está escrito com nome:
nenhuma receita ativa, nenhum aceite registrável, nenhum provedor de pagamento, nenhuma nota fiscal, nenhum SLA.
Comece por `ECONOMICS.md`, `MONETIZATION_LEGAL_MATRIX.md` e `FINAL_ECONOMIC_HARDENING_REPORT.md`.

**Novo no v0.16.0 (IMPACT NETWORK CORE):** a plataforma deixou de ser "um lugar com projetos" e passou a ser
**infraestrutura de conexão, estruturação, financiamento, execução, acompanhamento e comprovação de impacto** — com
**um núcleo** e experiências por papel, não quatro aplicações. A cadeia inteira existe como dado: Pessoa/Organização
→ Contexto → Necessidade → Rede → Match → Proposta → Relação → Projeto → Execução → Evidência → Resultado → Novo
Match. **Grafo de impacto** relacional (uma tabela de aresta, 22 tipos, 5 níveis de visibilidade, travessia de
profundidade 2 em 15 ms — a razão medida de **não** adotar banco de grafos); **motor de propostas** (9 tipos, 10
situações, grafo de transições no banco) onde *proposta ≠ contrato ≠ investimento ≠ pagamento*; **marketplace** com
um único lugar que decide o que é público; **conversa com contexto obrigatório**; **notificação para toda a equipe
envolvida** em cada evolução (14 grupos, idempotente, um aviso por fato); **prontidão** em 6 dimensões sempre com
explicação; **recomendação ≠ match**; **workspace por persona** (10 personas, 24 seções, 15 capacidades) que devolve
próximas ações, não números; **perfil público `impacto.app/@identificador`** que lê só uma projeção curada;
**relatório de impacto** cujos números são **colhidos pelo banco**, não digitados; **escada de moderação** de 10
degraus com proporcionalidade e contestação; **cobrança versionada** com aviso de 30 dias e imposto no checkout.
788 testes, 704 operações, 231 tabelas e 17 migrações à época. O pacote de Design System "Convergência" **não foi
recebido** — as seções que dependiam dele não foram executadas, e isso está escrito em
`DESIGN_HANDOFF_FINAL.md` §1. Comece por `IMPACT_NETWORK_ARCHITECTURE.md`, `DESIGN_HANDOFF_FINAL.md` e
`FINAL_IMPACT_NETWORK_HARDENING_REPORT.md`.

**Novo no v0.15.0 (Núcleo do produto):** as seis peças passaram a ser **um sistema**, não seis telas — ideia → diagnóstico → projeto → documento → match → acompanhamento compartilhando o mesmo vocabulário de evidência (com fonte, data e frescura), as mesmas versões de motor e a mesma trilha encadeada por hash. A **ideia não é apagada** ao virar projeto; a **máquina de 17 situações é dado no banco**, com gatilho que recusa transição inválida até em SQL direto; a **linha de tempo** é a trilha que já existia, verificável; **retratos comparáveis** respondem "o que mudou entre março e setembro"; o **diagnóstico** separa FATO, INFERÊNCIA, RECOMENDAÇÃO e **DESCONHECIDO**, com versões imutáveis e `o que mudou` calculado pelo servidor; a **montagem de documento** recusa gerar incompleto, dizendo o que falta, e exige **quatro olhos** para aprovar; o **match** carrega quatro versões e aceita retorno humano **sem treinar nada automaticamente**. 673 testes, 625 operações, 205 tabelas. **Não há assinatura qualificada (ICP-Brasil/Gov.br), KMS/HSM, integração contra sistema real nem teste de intrusão independente** — tudo isso está listado com nome e motivo. Comece por `CORE_PRODUCT_ARCHITECTURE.md`, `FINAL_PRE_DESIGN_HARDENING_REPORT.md` e `DESIGN_HANDOFF.md` §13.

**Novo no v0.14.0 (Confiança, identidade e assinatura digital):** **qualquer pessoa autorizada pode verificar um documento da plataforma sem ter conta** — pelo código impresso ou pelo QR, em `/verificar`: diz se é genuíno, **qual versão foi assinada**, se a integridade continua intacta, quem assinou e se foi revogado. Mais: assinatura eletrônica avançada em **duas camadas** (senha + código de uso único amarrado ao hash do conteúdo), cadeia de custódia encadeada por objeto, identidade por níveis com conferência humana, credencial profissional com catálogo de 20 conselhos, acordos multiassinatura com acompanhamento, carimbo de tempo interno, taxonomia ODS/ESG/determinantes sociais, idioma e tema por usuária, financiamento em cotas com campanha pública, honorários exigindo fonte, georreferência com consentimento, diagnóstico guiado em 8 etapas e exportação em docx/xlsx/odt/ods/xml/pdf. 564 testes. **Não há assinatura qualificada (ICP-Brasil/gov.br), biometria, SMS nem carimbo de ACT** — essas dependem de contratação externa e a plataforma **recusa explicitamente** em vez de simular. Comece por `PUBLIC_VERIFICATION.md`, `DIGITAL_SIGNATURE.md` e `FINAL_TRUST_HARDENING_REPORT.md`.

**Novo no v0.13.0 (Integration Hub):** camada de integração desacoplada — conexões por ambiente, credenciais cifradas que a API nunca devolve, mapeamento de campos, correspondência de ID externo com conflito explícito, jobs idempotentes com repetição e disjuntor, webhooks de entrada e saída assinados, importação CSV/XLSX com aprovação humana, exportação e painel de operação. 13 tabelas, 36 rotas, 9 provedores declarados com **maturidade honesta**, 468 testes. **Nenhuma integração foi executada contra sistema externo real** e **não há nenhuma tela** — comece por `INTEGRATION_HUB.md`, `FINAL_INTEGRATION_HARDENING_REPORT.md` e `DESIGN_HANDOFF.md` §11.

**Novo no v0.12.1 (baseline técnica):** endurecimento final antes da camada de design — varredura de autorização nas 475 operações, testes de concorrência, correção de vazamento de esquema em erros, do desconto de voucher que não aparecia, da perda de boletim em falha de SMTP e do contraste reprovado (WCAG AA). 392 testes. Comece por `FINAL_TECHNICAL_BASELINE.md` e `DESIGN_HANDOFF.md`.

**Novo no v0.12.0:** Central de Conhecimento — `/ajuda` (busca, guias, biblioteca, FAQ, assistente ancorado), Academia, eventos, suporte com SLA, parcerias, demonstração, solicitação de teste, boletim e CMS em `/admin/central`. Começa em `KNOWLEDGE_HUB.md`. **Sem conteúdo oficial real ainda (só exemplos rotulados).**

**Novo no v0.11.0:** monetização SaaS — trial de 14 dias FULL sem cartão, níveis FREE/PLUS/PREMIUM/GOV, cobrança mensal/anual (Stripe, só simulado em testes), vouchers, licenças e convênios. Comece por `docs/billing.md`. **Preços não definidos; Stripe não homologado.**

**Novo no v0.10.1:** fecha pendências da camada institucional — perfis OS/OSCIP, instrumentos, trilha de formalização e mentoria, cruzamento fiscal × elegibilidade, rede da solução, tesauro de 67 conceitos. Veja `CHANGELOG.md` e `FINAL_RELEASE_AUDIT.md` §3-C.

**Novo no v0.10.0:** camada institucional do terceiro setor — natureza jurídica × qualificações × situação × elegibilidade por oportunidade, com explicação e fonte. Comece por `THIRD_SECTOR_MODEL.md`, `INSTITUTIONAL_ELIGIBILITY_ENGINE.md` e `FINAL_RELEASE_AUDIT.md` §3-B.

**Novo no v0.9.0:** Biblioteca de Soluções de Impacto — busca por intenção, relevância/match explicáveis, replicação, intenção de financiamento com privacidade. Comece por `SOLUTION_LIBRARY.md`.

## Comece aqui
| Biblioteca de Soluções | `SOLUTION_LIBRARY.md`, `SOLUTION_SEARCH.md`, `SOLUTION_MATCH_ENGINE.md`, `REPLICATION_ENGINE.md`, `INTENT_ENGINE.md`, `AI_SEARCH_ARCHITECTURE.md`, `SOLUTION_DATA_MODEL.md`, `API_DOCUMENTATION.md`, `TEST_REPORT.md` |
| Quero… | Leia |
|---|---|
| rodar localmente | `ENVIRONMENT_SETUP.md` |
| saber o que funciona e o que falta | `FINAL_RELEASE_AUDIT.md`, `PRODUCTION_READINESS.md` |
| publicar (Web, Google Play, App Store) | `DEPLOYMENT_CHECKLIST.md`, `docs/DEPLOYMENT.md`, `docs/MOBILE.md` |
| continuar o desenvolvimento | `CLAUDE_HANDOFF_FINAL.md`, `DECISIONS.md` |
| entender o núcleo do produto | `CORE_PRODUCT_ARCHITECTURE.md`, `MATCH_ENGINE_FINAL.md`, `DIAGNOSTIC_ENGINE.md`, `PROJECT_LIFECYCLE.md`, `DOCUMENT_ASSEMBLY.md`, `LONGITUDINAL_TRACKING.md` |
| fazer o design | **`DESIGN_HANDOFF_FINAL.md`** (v0.16.0), `INFORMATION_ARCHITECTURE.md`, `NAVIGATION_MODEL.md`; histórico em `DESIGN_HANDOFF.md` §13 |
| entender a rede de impacto | `IMPACT_NETWORK_ARCHITECTURE.md`, `IMPACT_GRAPH.md`, `RELATIONSHIP_MODEL.md`, `PROPOSAL_ENGINE.md`, `IMPACT_MARKETPLACE.md`, `IMPACT_REPORTING.md` |
| entender as personas e o workspace | `ROLE_BASED_EXPERIENCE.md`, `WORKSPACE_ARCHITECTURE.md` |
| saber quem vê o quê | **`PRIVACY_VISIBILITY_MATRIX.md`** |
| entender moderação e cobrança | `MODERATION_LADDER.md`, `BILLING_V2.md` |
| publicar no celular | `MOBILE_READINESS_FINAL.md`, `STORE_READINESS.md` |
| saber o que depende de terceiro | `EXTERNAL_DEPENDENCIES.md`, `HOMOLOGATION_MATRIX.md`, `SIGNATURE_VALIDATION_MATRIX.md` |
| auditar segurança, banco e desempenho | `SECURITY_FINAL_CHECKLIST.md`, `DATABASE_INTEGRITY_REPORT.md`, `PERFORMANCE_REPORT.md` |
| rotacionar chave de cifragem | `KEY_ROTATION.md` |
| saber o que é guardado e por quanto tempo | `DATA_RETENTION_MATRIX.md` |
| segurança / LGPD | `SECURITY_AUDIT.md`, `docs/SECURITY.md`, `LGPD_AUDIT.md`, `docs/LGPD.md`, `docs/legal/` |
| licenças e PI | `THIRD_PARTY_DEPENDENCIES.md`, `IP_REGISTER.md` |
| integridade do pacote | `RELEASE_MANIFEST.sha256` (`python3 scripts/make_release.py --verify .`) |

## Estrutura
```
backend/     API (Starlette), serviços, engines (match, fiscal, IA), adapters, jobs, migrações SQL, testes
web/         SPA/PWA React+TypeScript (src/), build esbuild (dist/ já construído), Capacitor (Android/iOS)
mobile/      scripts, ícones/splash e modelos de deep link
config/      planos, taxonomia, pesos do match, regras fiscais candidatas (rascunho)
infra/       bootstrap do banco, compose, nginx, alertas
scripts/     backup/restore, reset do banco de dev, gerador de API docs, make_release
docs/        arquitetura, banco, API (gerada), segurança, LGPD, match, fiscal, IA, compliance, pagamentos, operação, mobile, testes, admin, negócio, a11y, ESG/ODS, legal/, evidence/
history/     v0.6.0, v0.7.0 e v0.8.0 preservados (sem sobrescrever)
```
Mapa dos documentos pedidos: `AI_ARCHITECTURE` = `docs/AI.md` · `MATCH_ENGINE`, `DATABASE`, `API` (gerada de 306 operações), `SECURITY`, `LGPD`, `DEPLOYMENT`, `TESTING`, `ADMIN`, `BUSINESS_MODEL` em `docs/`.

## Princípios (verificáveis no código)
- **Isolamento no banco** (RLS) — não só na API. · **Match independe de plano/voucher** (teste AST). · **Sem nota sem dados suficientes.**
- **IA só rascunha**; revisão e assinatura por profissional verificado. · **Fiscal só com regra aprovada por dois revisores.**
- **Aportes não passam pela plataforma** (registrados e conferidos). · **Sem pagamento falso**; **sem segredos** no repositório.

## Início rápido (dev)
```bash
make db && make web && IMPACTO_SEED_DEMO=true make dev     # http://localhost:8080 — dados FICTÍCIOS
make test                                                   # suíte completa (Postgres + navegador)
```
Licença do código: **a definir pelo proprietário** (ver `IP_REGISTER.md`). Dependências: `THIRD_PARTY_DEPENDENCIES.md`.
