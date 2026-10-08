# ESTADO DO PROJETO — leia antes de executar a etapa de demo/QA

Este documento existe por um motivo específico: **impedir que a próxima sessão refaça trabalho já
concluído e verificado.** O prompt mestre da etapa de virtualização/QA/demo tem 25 fases; **19 já
estão feitas neste repositório**, com evidência executada e versionada.

Gastar sessão repetindo auditoria, seed, RBAC, multi-tenancy, E2E, regressão e empacotamento seria
desperdício. O que falta é específico, e está na seção final.

**Estado:** v0.23.0 · branch `main` · commit `8a30d93` · 2.205 testes, 0 falhas, 0 erros.

---

## As 25 fases, uma a uma

| Fase | Situação | Evidência no repositório |
|---|---|---|
| **01** Auditoria | **FEITA** | `docs/execution/` — 11 relatórios; três auditorias independentes já executadas (externa + duas internas), com os achados tratados em `IMPLEMENTATION_LOG.md` |
| **02** Checkpoint Git | **FEITA** | 110 commits rastreáveis; `GIT_EVIDENCE.md` prova que o pacote É a árvore do commit, arquivo por arquivo |
| **03** Arquitetura do ambiente local | **FEITA** | `ENVIRONMENT_SETUP.md`, `docs/PUBLICACAO.md` (10 passos com verificação), `docs/ARCHITECTURE.md` |
| **04** Docker / virtualização | **PARCIAL — gap real** | `Dockerfile` e `infra/compose/docker-compose.yml` existem e **nunca foram construídos**: não há daemon Docker no ambiente onde foram escritos |
| **05** Banco + migrations + seed | **FEITA** | 62 migrações aplicadas do zero; 322 tabelas; 321 com RLS; 667 políticas; `seed-demo` cria 14 usuários de 14 perfis |
| **06** Perfis + RBAC | **FEITA** | 888 operações classificadas em 7 classes; **221 chamadas HTTP reais** de organização-cliente contra a porta da plataforma, todas 403; 83 rotas com permissão nomeada recusando papel sem ela, com contraprova |
| **07** Todas as telas | **FEITO na v0.23.1** | **218** telas (não 232: havia três tabelas de rota e só uma era lida), inventariadas em `screen_inventory.json` e cruzadas com as 894 operações em `screen_backend_map.json`; nenhuma tela sem backend (o "defeito" da v0.23.1 era do instrumento) |
| **08** Fluxos | **FEITA** | 49 passos em 7 jornadas e 5 personas — `PERSONA_E2E_MATRIX.csv` |
| **09** E2E | **FEITA** | 91 testes de ponta a ponta com Chromium real (Playwright) |
| **10** Multi-tenancy | **FEITA** | `test_security_tenancy.py` (25 testes): IDOR/BOLA de leitura, escrita, remoção e listagem recusados **pela parede (RLS)**, não só pela porta; atribuição em massa de `org_id` recusada |
| **11** Transações simuladas | **FEITA** | `billing_provider=none` embarcado; `platform_charges.is_simulated`; o restore recusa dump com cobrança real |
| **12** Logs / auditoria | **FEITA** | 4 cadeias de hash (`audit_verify`, `ledger_verify`, `value_verify`, `trust_verify`); 43 tabelas append-only; 6 protegidas contra TRUNCATE |
| **13** UX / responsividade | **PARCIAL** | 390 px verificado (sem rolagem horizontal, alvos de toque); **tablet não exercitado** |
| **14** Segurança | **FEITA** | 165 testes: SSRF em 22 grafias, CRLF por socket cru, injeção de SQL provada pela carga que volta idêntica, travessia de caminho, desserialização, cabeçalhos, CSP sem escape |
| **15** Performance | **FEITA** | Escala cheia: 10.000 soluções, 100.000 documentos, 100.000 avaliações; 17 testes, todos abaixo do orçamento de 2.500 ms |
| **16** Regressão | **FEITA** | 2.205 testes · 0 falhas · 0 erros · 623 s |
| **17** Instalação limpa | **NÃO FEITA — gap real** | Exige `npm ci` e `pip install` com rede; o registry npm responde 403 e o índice PyPI está indisponível no ambiente atual |
| **18** Compartilhamento externo | **NÃO FEITA — gap real** | Exige túnel e rede de saída |
| **19** Documentação | **PARCIAL** | Existem: `README`, `ARCHITECTURE`, `SECURITY`, `TESTING`, `OPERATIONS`, `PUBLICACAO`, `ENVIRONMENT_SETUP`, `DEPLOYMENT_CHECKLIST`, `ACCESSIBILITY_REPORT`, `PERFORMANCE_REPORT`. Faltam: `DEMO.md`, `TESTER_GUIDE.md`, `TROUBLESHOOTING.md` |
| **20** Release candidate | **FEITA** | v0.23.0, veredito 🟡 AMARELO — GO COM CONDIÇÕES |
| **21** ZIP | **FEITA** | `IMPACTO_v0.23.0_AUDIT_COMPLETION.zip` (1.816 arquivos) + pacote de auditoria |
| **22** Testar o ZIP | **PARCIAL — gap real** | Verificado por **duas cadeias independentes** (sha256 do manifesto e sha1 dos objetos Git), mas **nunca extraído e EXECUTADO** numa máquina limpa |
| **23** Checksum | **FEITA** | sha256 dos dois pacotes, publicado fora deles |
| **24** Git final | **FEITA** | `main` em `8a30d93`, árvore limpa, publicada |
| **25** Relatório final | **FEITA** | `docs/execution/FINAL_RELEASE_REPORT.md` — 25 itens exigidos pelo pacote de execução |

**19 feitas · 4 parciais · 2 não feitas.**

---

## O que a próxima sessão deve atacar

Em ordem de valor. Os quatro primeiros dependem de **rede e Docker**, que é precisamente o que o
ambiente anterior não tinha — por isso são o alvo certo de uma sessão com rede.

### 1. Construir e rodar o Dockerfile (fase 04) — o maior risco não medido

O `Dockerfile` existe, declara no próprio cabeçalho que nunca foi testado, e roda o **typecheck
oficial** (`tsconfig.json` com `@types/react`) no estágio de build. Hoje esse typecheck só roda sob
stubs mínimos, porque `@types/react` não é instalável sem registry.

**Critério objetivo de bloqueio:** `docker build` conclui, `docker compose up` sobe a pilha,
`/healthz` e `/readyz` respondem 200, e `scripts/smoke_test.py` dá GO contra o contêiner.

### 2. Instalação limpa do zero (fases 17 e 22)

`git clone` → `.env` → instalar → migrar → semear → construir → rodar → navegar. Sem depender de
nada que já esteja na máquina.

**Critério objetivo:** o ZIP extraído num diretório vazio chega a uma aplicação navegável, e o
procedimento de `docs/PUBLICACAO.md` funciona **como está escrito** — qualquer passo que não
funcione é defeito do guia e deve ser corrigido nele.

### 3. As quatro verificações de acessibilidade que exigem rede ou outro navegador (fase 13)

- `axe-core` via `@axe-core/playwright` — hoje `NOT VERIFIED` por causa do 403 do npm
- Firefox e WebKit — só Chromium está instalado
- Zoom de texto a 200% e tablet

**Critério objetivo:** zero violações `serious`/`critical` do axe nas telas principais, ou cada uma
registrada com severidade, tela e correção. `ACCESSIBILITY_REPORT.md` tem as 6 pendências nomeadas —
feche as que a rede permitir e **mantenha declaradas** as que exigem pessoa (leitor de tela real,
navegação por voz).

### 4. SCA de verdade (bloqueio D-SUP2)

`pip-audit -r backend/requirements.txt` e `npm audit --omit=dev --audit-level=high`. Hoje é o único
item do Gate 5 de segurança que está **BLOCKED** em vez de PASS.

**Critério objetivo:** zero vulnerabilidade crítica ou alta sem exceção escrita. São 11 pacotes
Python fixados com `==` e 6 Node — superfície pequena por desenho.

### 5. Inventário de telas (fase 07)

FEITO na v0.23.1 — 218 entradas de rota (o 232 estava errado). Tabela: tela · rota · perfis que alcançam ·
estado (completa/parcial/sem backend) · testável.

**Critério objetivo:** toda rota classificada; nenhuma inventada; funcionalidade de backend sem
interface e botão sem implementação **identificados**, não escondidos.

### 6. Documentos que faltam (fase 19)

`DEMO.md`, `TESTER_GUIDE.md`, `TROUBLESHOOTING.md`. E, se a etapa criar túnel, o procedimento de
compartilhamento (fase 18) com o aviso de ambiente de teste.

---

## O que NÃO refazer

A regra do prompt mestre vale aqui ao contrário: *não desperdice crédito com análises superficiais e
reescritas desnecessárias*. Especificamente, **não refaça**:

- a auditoria de código — três já foram feitas, e os achados estão tratados e registrados;
- a suíte de testes — 2.205 passam; **rode-a** para confirmar, não a reescreva;
- o seed — funciona e cria os 14 perfis;
- as quatro matrizes obrigatórias — são **geradas do produto** e travadas por teste contra deriva;
  se divergirem, regenere com os scripts, não edite o CSV;
- o empacotamento — `scripts/make_release.py` e `scripts/verify_package_against_git.py` existem e
  funcionam.

## Regras permanentes que continuam valendo

1. **Nenhuma integração pode ser marcada como homologada.** As 14 estão `BLOCKED` porque exigem
   credencial de fornecedor. Marcar `sandbox` sem credencial é a simulação proibida.
2. **Nada de simular** provedor fiscal, Stripe real, KYC, identidade governamental, gov.br,
   ICP-Brasil, ACT, biometria, assinatura qualificada ou SMS.
3. **Nunca enfraquecer ou remover teste para obter verde.** Se um teste falhar, investigue: nesta
   rodada, cinco "falhas" eram testes honestos deixando para trás estado que forjam de propósito.
4. **Não declarar inviolabilidade.** Nenhum sistema conectado à internet pode receber essa garantia.
5. **Nenhum segredo em entregável.** `scripts/secrets_scan.py` roda na suíte, com controle negativo.
