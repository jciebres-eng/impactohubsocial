# PROMPT PARA A SESSÃO NA NUVEM — etapa de virtualização, demo e instalação limpa

> Cole o texto abaixo da linha. Ele é deliberadamente curto: o estado detalhado está no repositório,
> em `docs/execution/ESTADO_PARA_SESSAO_NUVEM.md`, e mandar a sessão lê-lo custa menos do que colar
> tudo aqui.

---

Você está no repositório **jciebres-eng/impactohubsocial**, branch `main`, versão v0.23.0.

**PRIMEIRO, ANTES DE QUALQUER COISA:** leia `docs/execution/ESTADO_PARA_SESSAO_NUVEM.md`. Ele mapeia
as 25 fases da etapa de demo/QA e mostra que **19 já estão feitas e verificadas**. Não as refaça.
Refazer auditoria, seed, RBAC, multi-tenancy, E2E ou empacotamento é desperdício de sessão.

Sua missão é fechar **exatamente seis lacunas**, nesta ordem, porque todas dependem de rede e de
Docker — que é o que o ambiente anterior não tinha.

## 1. Docker (o maior risco não medido)

`docker build -t impacto:0.23.0 .` e `docker compose -f infra/compose/docker-compose.yml up`.

O `Dockerfile` declara no cabeçalho que nunca foi construído. Ele roda o typecheck **oficial**
(`tsconfig.json` com `@types/react`), que hoje só roda sob stubs mínimos por falta de registry npm.

**BLOQUEIO:** só prossiga quando `docker build` concluir, a pilha subir, `/healthz` e `/readyz`
responderem 200 e `python3 scripts/smoke_test.py --base http://localhost:PORTA --email … --password …`
der **GO** ou **GO WITH CONDITIONS** com zero falhas obrigatórias.

Se o build falhar, **corrija o Dockerfile** — não contorne com build manual.

## 2. Instalação limpa, do zero

Extraia `IMPACTO_v0.23.0_AUDIT_COMPLETION.zip` (ou clone) num diretório vazio e siga
`docs/PUBLICACAO.md` **exatamente como está escrito**, do passo 1 ao 10.

**BLOQUEIO:** qualquer passo que não funcione como escrito é defeito **do guia** — corrija o guia,
não improvise em volta. Terminar com aplicação navegável e `smoke_test.py` em GO.

Atenção ao passo 6 (`create-admin`) e ao passo 7 (portão jurídico): o cadastro responde
**503 `legal_documents_not_published`** até aprovar `terms_of_use` e `privacy_policy` com
`python3 -m impacto.cli legal-approve`. Isso é desenho, não defeito.

## 3. SCA — o único item de segurança ainda BLOCKED

```
pip-audit -r backend/requirements.txt
cd web && npm audit --omit=dev --audit-level=high
```

**BLOQUEIO:** zero vulnerabilidade crítica ou alta sem exceção escrita em `docs/execution/BLOCKERS.md`.
São 11 pacotes Python fixados com `==` e 6 Node. Ao terminar, mova **D-SUP2** de BLOCKED para PASS em
`BLOCKERS.md`, `SECURITY_GATE.md` e `FINAL_ZERO_PENDING_REPORT.md` — ou registre o que encontrou.

## 4. Lockfile — o outro bloqueio de reprodutibilidade

```
cd web && npm install --package-lock-only
```

**BLOQUEIO:** `package-lock.json` versionado e `npm ci` funcionando. Ao terminar, atualize **D-SUP1**.
`web/INSTALLED_TREE.json` (que NÃO é um lockfile e diz isso) pode então ser removido, ou mantido como
registro — decida e escreva por quê.

## 5. Acessibilidade — feche o que a rede permite

```
cd web && npm i -D @axe-core/playwright
python -m playwright install firefox webkit
```

`ACCESSIBILITY_REPORT.md` tem **6 pendências nomeadas**. Feche com axe-core, com o segundo navegador
e com zoom a 200%.

**BLOQUEIO:** zero violação `serious`/`critical` do axe nas telas principais, ou cada uma registrada
com severidade, tela, correção e teste de regressão. **Mantenha declaradas** as que exigem pessoa —
leitor de tela real e navegação por voz **não se fecham por software**, e afirmar que fecharam seria
mentira.

## 6. Inventário de telas e os documentos que faltam

**FEITO na v0.23.1.** O número 232 escrito aqui estava errado: eram **218**, em três tabelas de rota
(`PUBLIC` 9, `HELP` 30, `ROUTES` 179), confirmado por extrator, por `grep` e pela subtração dos itens
de menu. A tabela está em `docs/execution/screen_inventory.json` (rota, componente, arquivo, tipos que
alcançam, menu, alcance) e `docs/execution/screen_backend_map.json` (operações que cada componente
chama, cruzadas com as 888 registradas). Painel navegável: `scripts/make_screen_panel.py`.

O que o cruzamento achou: 157 telas chamam operação registrada · 60 não chamam a API diretamente ·
234 das 894 operações sem referência no front · **0 telas sem backend** (a v0.23.1 acusou
`/entrar` → `GET /v1/meta/config`; era falso: a rota é crua em `app.py` e o cruzamento não a lia). Tudo travado por teste em
`backend/tests/test_v0230_frontend_gate.py`.

`DEMO.md`, `TESTER_GUIDE.md` e `TROUBLESHOOTING.md` **já estão escritos** (v0.23.1), em `docs/`, com
os números conferidos contra os JSON gerados por teste. Atualize-os se a publicação mudar algo. Se criar túnel para testadores
externos, documente o ciclo (iniciar → URL → compartilhar → encerrar) e deixe claro que é ambiente de
teste.

---

## Regras que não se negociam

1. **Nenhuma integração homologada.** As 14 estão BLOCKED porque exigem credencial de fornecedor.
   Marcar `sandbox` sem credencial é a simulação proibida.
2. **Nada de simular** provedor fiscal, Stripe real, KYC, gov.br, ICP-Brasil, ACT, biometria,
   assinatura qualificada ou SMS.
3. **Nunca enfraquecer ou remover teste para obter verde.** Se falhar, investigue: nesta rodada cinco
   "falhas" eram testes honestos deixando para trás estado que forjam de propósito.
4. **Não declarar inviolabilidade**, nem "production-ready" enquanto houver bloqueio.
5. **Nenhum segredo em entregável.** `scripts/secrets_scan.py` roda na suíte, com controle negativo.
6. **Não refaça as matrizes à mão.** São geradas do produto e travadas por teste; se divergirem,
   regenere com os scripts em `scripts/make_*_matrix.py`.
7. **Sem deploy irreversível**, sem banco de produção, sem credencial real, sem domínio real, sem
   pagamento real.

## Como terminar

Rode a regressão completa (`python3 -m unittest discover -s tests -t .` a partir de `backend/`, com
`TEST_ADMIN_DATABASE_URL`, `PASSWORD_SCRYPT_N=16384`, `RATE_LIMIT_MULTIPLIER=1000`), regenere as
matrizes e o manifesto, reempacote, e **atualize os relatórios existentes** em `docs/execution/` —
não crie relatórios paralelos.

Entregue:

```
VERSÃO / BRANCH / COMMIT
DOCKER BUILD:        ok | falhou — por quê
INSTALAÇÃO LIMPA:    ok | falhou — qual passo
SCA:                 n vulnerabilidades · críticas/altas
LOCKFILE:            gerado | não
ACESSIBILIDADE:      pendências fechadas / mantidas
TELAS INVENTARIADAS: 218 de 218 (feito na v0.23.1)
REGRESSÃO:           n testes · falhas · erros
ZIP + SHA256
O QUE AINDA FALTA ANTES DE PRODUÇÃO
```

Cada afirmação com **o comando que a produziu e o resultado**. Nada de "implementado", "corrigido" ou
"testado" sem evidência.
