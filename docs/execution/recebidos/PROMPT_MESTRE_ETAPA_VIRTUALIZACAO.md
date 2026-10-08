# PROMPT MESTRE — ETAPA DE VIRTUALIZAÇÃO, QA, DEMO, TESTES FULL E RELEASE LOCAL

## MISSÃO

Você está entrando na próxima etapa crítica de desenvolvimento do SaaS IMPACTO.

O objetivo desta etapa NÃO é simplesmente continuar programando funcionalidades.

Sua missão é transformar o estado atual do projeto em uma **release completa, reproduzível, testável e demonstrável**, permitindo que:

1. Todo o SaaS seja executado localmente.
2. Todas as telas disponíveis no código possam ser acessadas.
3. Todos os perfis de usuário possam ser simulados/testados.
4. Todos os dashboards e painéis possam ser navegados.
5. Todos os fluxos e transações não financeiras reais possam ser testados.
6. Dados de demonstração possam ser criados de forma segura.
7. O sistema possa ser compartilhado temporariamente para testes externos.
8. O projeto possa ser posteriormente hospedado/publicado com segurança.
9. O estado final possa ser entregue em um ZIP FULL e reproduzível em outra máquina.
10. Cada etapa seja versionada no Git, com commits organizados e reversíveis.

Você deve trabalhar como:

* Senior Software Architect
* Senior Full-Stack Engineer
* QA Engineer
* DevOps Engineer
* Security Engineer
* Release Engineer
* Product Engineer
* UX/UI QA
* Database Engineer
* Test Automation Engineer

Não faça trabalho superficial.

Faça uma auditoria técnica real do projeto antes de modificar qualquer coisa.

---

# 1. REGRA ABSOLUTA DE PRESERVAÇÃO

ANTES DE ALTERAR O PROJETO:

* examine toda a estrutura;
* identifique stack;
* identifique frontend;
* identifique backend;
* identifique banco;
* identifique autenticação;
* identifique APIs;
* identifique integrações;
* identifique variáveis de ambiente;
* identifique scripts;
* identifique testes;
* identifique documentação;
* identifique Docker/containers;
* identifique configurações de build;
* identifique configurações de deploy;
* identifique rotas;
* identifique páginas;
* identifique componentes;
* identifique perfis;
* identifique permissões;
* identifique fluxos;
* identifique funcionalidades incompletas.

NÃO apague funcionalidades existentes apenas porque parecem incompletas.

Primeiro compreenda.

Depois proponha.

Depois implemente.

---

# 2. GIT — OBRIGATÓRIO DURANTE TODO O TRABALHO

Git deve ser utilizado como mecanismo de segurança e rastreabilidade.

Antes do trabalho:

```bash
git status
git branch
git log --oneline -20
```

Crie uma branch apropriada para esta etapa, por exemplo:

```text
release/local-demo-qa
```

Faça um commit inicial de segurança antes de alterações significativas.

Exemplo:

```text
chore: checkpoint before full local demo and QA
```

## REGRA

NUNCA acumule centenas de alterações sem commit.

Faça commits por etapas lógicas.

Exemplos:

```text
chore: prepare local demo environment
feat: add deterministic demo seed
feat: complete role-based demo access
test: add end-to-end navigation coverage
fix: resolve authentication flow issues
fix: resolve dashboard rendering issues
test: validate transaction workflows
security: harden demo environment
docs: document local installation
chore: cleanup production artifacts
release: prepare local release package
```

Depois de cada etapa importante:

```bash
git status
git diff
git add .
git commit
```

Antes de cada nova etapa, confirme que o working tree está compreensível.

NÃO faça commits artificiais apenas para gerar quantidade.

Os commits precisam representar unidades reais de trabalho.

---

# 3. PRIMEIRO OBJETIVO: AUDITORIA FULL DO ESTADO ATUAL

Antes de implementar, produza um relatório interno detalhado contendo:

## Frontend

* framework;
* versão;
* rotas;
* páginas;
* layouts;
* componentes;
* formulários;
* dashboards;
* tabelas;
* gráficos;
* modais;
* estados;
* loading states;
* empty states;
* error states;
* responsividade;
* acessibilidade;
* navegação;
* autenticação;
* autorização.

## Backend

* framework;
* APIs;
* endpoints;
* serviços;
* middlewares;
* autenticação;
* autorização;
* validação;
* tratamento de erros;
* logs;
* jobs;
* filas;
* webhooks;
* integrações.

## Banco

* tecnologia;
* schema;
* migrations;
* seed;
* relacionamentos;
* constraints;
* índices;
* auditoria;
* integridade referencial.

## Infraestrutura

Identifique:

* Docker;
* Docker Compose;
* containers;
* scripts;
* variáveis de ambiente;
* serviços externos;
* storage;
* cache;
* filas;
* banco;
* observabilidade.

## Segurança

Avalie:

* autenticação;
* autorização;
* sessão;
* cookies;
* CSRF;
* XSS;
* SQL injection;
* validação;
* rate limiting;
* secrets;
* CORS;
* headers;
* upload;
* exposição de dados;
* logs;
* permissões;
* isolamento entre organizações/tenants.

---

# 4. INVENTÁRIO COMPLETO DA INTERFACE

Crie um inventário real de TODAS as telas existentes.

Classifique:

| Tela | Rota | Perfil | Status | Dados | Ação | Testável |
| ---- | ---- | ------ | ------ | ----- | ---- | -------- |

Não invente telas que não existem.

Porém, se existir funcionalidade no backend sem interface, identifique isso.

Se existir interface sem backend funcional, identifique isso.

Se existir botão sem implementação, identifique isso.

Se existir fluxo parcial, identifique isso.

---

# 5. OBJETIVO CENTRAL: AMBIENTE DE DEMONSTRAÇÃO COMPLETO

Crie, quando tecnicamente apropriado, um **Demo/Local Environment** separado do ambiente de produção.

O ambiente deverá permitir navegar pelo SaaS como se fosse uma instalação real.

Deve existir uma forma simples de inicializar:

```bash
npm install
npm run setup
npm run dev
```

OU, se Docker for mais apropriado:

```bash
docker compose up --build
```

A solução final deve documentar exatamente o procedimento.

---

# 6. VIRTUALIZAÇÃO / CONTAINERIZAÇÃO

Avalie primeiro se é possível criar uma infraestrutura reproduzível.

Prioridade:

### Opção A — Docker Compose

Se possível, criar:

```text
frontend
backend
database
redis/cache (se necessário)
worker (se necessário)
```

com comunicação interna correta.

### Opção B — Ambiente virtualizado

Se fizer sentido para o projeto, preparar:

* VM;
* container;
* dev container;
* ambiente reproducível;
* scripts de bootstrap.

Não crie virtualização apenas por criar.

Escolha a solução que permita que outra máquina reproduza o projeto com o menor atrito possível.

---

# 7. AMBIENTE DE DEMONSTRAÇÃO

Criar um ambiente explicitamente identificado como:

```text
DEMO / LOCAL / TEST
```

Nunca misture dados de demonstração com produção.

O ambiente de demonstração deve utilizar:

* banco separado;
* secrets separados;
* usuários de teste;
* dados sintéticos;
* transações fictícias;
* documentos fictícios;
* organizações fictícias.

NÃO utilizar dados pessoais ou financeiros reais.

---

# 8. SISTEMA DE USUÁRIOS DE TESTE

Crie um mecanismo seguro de seed para gerar todos os perfis necessários.

Exemplo conceitual:

```text
SUPER_ADMIN
ADMIN
ORG_ADMIN
MANAGER
AUDITOR
ANALYST
FINANCE
COMPLIANCE
USER
VIEWER
```

MAS:

Não invente perfis se o sistema já possui RBAC definido.

Primeiro descubra os perfis existentes.

Para cada perfil:

* usuário;
* organização;
* permissões;
* dashboard;
* menus;
* páginas;
* ações;
* restrições.

Crie contas DEMO somente para ambiente local/teste.

Não coloque credenciais reais no código.

---

# 9. "LOGIN COMO PERFIL" PARA TESTES

Se for seguro e apropriado, criar um mecanismo exclusivo de DEMO para facilitar testes.

Exemplo:

```text
Demo Users

[Administrador]
[Gestor]
[Auditor]
[Analista]
[Usuário]
```

Isso deve existir SOMENTE em:

```text
development
test
demo
```

NUNCA em produção.

Não criar backdoor.

Não criar mecanismo que possa ser ativado em produção.

---

# 10. SEED DETERMINÍSTICO

Criar seed reproduzível.

Executar:

```bash
npm run db:seed:demo
```

ou equivalente.

Toda execução deverá produzir um ambiente conhecido.

Criar dados suficientes para demonstrar:

* organizações;
* usuários;
* projetos;
* trilhas;
* indicadores;
* ESG;
* documentos;
* auditoria;
* registros financeiros fictícios;
* transações simuladas;
* notificações;
* logs;
* tarefas;
* dashboards;
* relacionamentos.

Somente se essas entidades realmente existirem no sistema.

---

# 11. TODAS AS TELAS DEVEM SER NAVEGÁVEIS

Percorra sistematicamente:

* login;
* onboarding;
* dashboard;
* organizações;
* usuários;
* perfis;
* permissões;
* projetos;
* ESG;
* indicadores;
* Value Ledger;
* auditoria;
* relatórios;
* documentos;
* configurações;
* notificações;
* administração;
* integrações;
* qualquer outro módulo existente.

Para cada tela:

1. abrir;
2. carregar dados;
3. testar links;
4. testar botões;
5. testar formulários;
6. testar validações;
7. testar estados vazios;
8. testar erros;
9. testar loading;
10. testar navegação;
11. testar permissões.

---

# 12. TESTE DE FLUXO COMPLETO

Não testar apenas páginas isoladas.

Testar jornadas completas.

Exemplo:

```text
LOGIN
↓
DASHBOARD
↓
CRIAR/ABRIR ORGANIZAÇÃO
↓
CRIAR PROJETO
↓
ADICIONAR DADOS
↓
EXECUTAR FLUXO
↓
AUDITORIA
↓
RELATÓRIO
↓
LOG
```

Crie jornadas equivalentes para cada perfil relevante.

---

# 13. TESTES END-TO-END

Se a stack permitir, configurar:

* Playwright;
* Cypress;
* ou ferramenta equivalente.

Criar testes automatizados para os principais fluxos.

No mínimo:

```text
01 - login
02 - logout
03 - autorização
04 - navegação
05 - criação
06 - edição
07 - exclusão segura
08 - filtros
09 - pesquisa
10 - dashboards
11 - auditoria
12 - transações simuladas
13 - isolamento entre organizações
14 - permissões
15 - erros
```

Não marcar teste como aprovado apenas porque a página abriu.

Verificar comportamento real.

---

# 14. TESTE DE TODOS OS PERFIS

Para cada perfil:

```text
LOGIN
→ DASHBOARD
→ MENU
→ PÁGINAS
→ AÇÕES PERMITIDAS
→ AÇÕES NEGADAS
→ LOGOUT
```

Validar:

* acesso autorizado;
* acesso proibido;
* menus;
* endpoints;
* APIs;
* UI;
* dados.

IMPORTANTE:

Não confiar apenas na ocultação de botões.

A autorização deve existir também no backend.

---

# 15. MULTI-TENANCY

Se o SaaS possuir organizações/tenants, executar testes específicos.

Criar:

```text
ORG-A
ORG-B
```

Criar usuários para ambas.

Validar que:

```text
ORG-A NÃO consegue acessar dados da ORG-B.
ORG-B NÃO consegue acessar dados da ORG-A.
```

Testar:

* frontend;
* backend;
* API;
* banco;
* buscas;
* relatórios;
* exportações;
* logs;
* arquivos.

Este é um teste CRÍTICO.

---

# 16. TRANSAÇÕES

Todas as transações disponíveis no código devem ser testadas.

Por "transação" considerar:

* criação;
* atualização;
* exclusão;
* aprovação;
* rejeição;
* movimentação;
* cálculo;
* registro;
* geração;
* integração;
* webhook;
* processamento assíncrono.

Se existir movimentação financeira real ou integração com dinheiro:

NÃO utilizar dinheiro real.

Criar modo:

```text
SIMULATION
```

para testes.

Toda transação simulada deve ser claramente marcada como:

```text
DEMO
SIMULATED
TEST
```

---

# 17. AUDITORIA E LOGS

Validar se ações importantes geram logs.

Exemplo:

```text
USER_LOGIN
USER_LOGOUT
CREATE
UPDATE
DELETE
APPROVE
REJECT
EXPORT
PERMISSION_CHANGE
TRANSACTION
```

Verificar:

* timestamp;
* usuário;
* organização;
* ação;
* recurso;
* resultado;
* correlation/request ID quando aplicável.

Não registrar secrets, tokens ou credenciais.

---

# 18. TESTE VISUAL / UX

Faça uma revisão de todas as telas.

Procurar:

* overflow;
* layout quebrado;
* textos cortados;
* botões sem ação;
* links mortos;
* inconsistência visual;
* erros de responsividade;
* problemas de contraste;
* formulários ruins;
* mensagens técnicas expostas ao usuário;
* estados vazios ruins;
* loaders ausentes;
* erros sem explicação.

Testar pelo menos:

```text
Desktop
Tablet
Mobile
```

---

# 19. ACESSIBILIDADE

Avaliar:

* keyboard navigation;
* foco;
* labels;
* aria;
* contraste;
* semântica;
* formulários;
* mensagens de erro;
* headings;
* botões;
* links.

Corrigir problemas relevantes encontrados.

---

# 20. SEGURANÇA DO AMBIENTE DEMO

Mesmo sendo ambiente de teste:

* não expor secrets;
* não usar credenciais reais;
* não expor banco desnecessariamente;
* não expor admin publicamente;
* não deixar debug perigoso;
* não permitir acesso indevido;
* não colocar chaves privadas no frontend;
* separar `.env.demo`;
* separar `.env.production`.

Adicionar:

```text
.env.example
```

sem secrets.

---

# 21. COMPARTILHAMENTO PARA TESTADORES EXTERNOS

Quero conseguir compartilhar a interface temporariamente para outras pessoas testarem.

Avalie a melhor solução.

Preferência:

```text
LOCAL
↓
TUNNEL SEGURO
↓
URL TEMPORÁRIA
↓
TESTADORES
```

Pode avaliar ferramentas como:

* Cloudflare Tunnel;
* Tailscale;
* ngrok;
* solução equivalente.

Não exponha diretamente portas sensíveis.

Se criar documentação para compartilhamento:

```text
START DEMO
↓
START TUNNEL
↓
COPY URL
↓
TEST
↓
STOP TUNNEL
```

O acesso externo deve ser claramente identificado como ambiente de TESTE.

---

# 22. NÃO PUBLICAR PRODUÇÃO AINDA

Nesta etapa:

NÃO realizar deploy irreversível em produção.

NÃO apontar para banco de produção.

NÃO utilizar credenciais de produção.

NÃO registrar domínio real.

NÃO habilitar pagamentos reais.

NÃO ativar webhooks de produção.

NÃO conectar contas financeiras reais.

O objetivo é:

```text
RELEASE CANDIDATE LOCAL / DEMO
```

---

# 23. PERFORMANCE

Executar uma avaliação inicial de:

* tempo de build;
* tempo de inicialização;
* carregamento;
* requests;
* queries;
* chamadas duplicadas;
* erros;
* memory leaks evidentes;
* assets;
* bundle.

Corrigir gargalos óbvios.

Não realizar otimizações prematuras que aumentem complexidade sem necessidade.

---

# 24. TESTES DE REGRESSÃO

Depois das correções:

Executar novamente:

```text
UNIT
INTEGRATION
E2E
AUTH
RBAC
MULTI-TENANT
DATABASE
BUILD
LINT
TYPECHECK
SECURITY
```

O resultado precisa ser registrado.

---

# 25. BUILD LIMPO

Executar uma instalação limpa.

Simular uma máquina nova.

Idealmente:

```bash
git clone
cd projeto
cp .env.example .env
npm install
npm run setup
npm run db:seed:demo
npm run build
npm run dev
```

ou equivalente.

Se Docker:

```bash
docker compose build --no-cache
docker compose up
```

Verificar que funciona sem depender de arquivos escondidos na máquina atual.

---

# 26. DOCUMENTAÇÃO OBRIGATÓRIA

Criar/atualizar:

```text
README.md
SETUP.md
DEMO.md
TESTING.md
ARCHITECTURE.md
SECURITY.md
TROUBLESHOOTING.md
RELEASE.md
```

Quando fizer sentido.

Documentar:

* requisitos;
* instalação;
* ambiente;
* banco;
* seed;
* usuários demo;
* perfis;
* comandos;
* testes;
* Docker;
* tunnel;
* troubleshooting;
* estrutura;
* arquitetura;
* limitações;
* próximos passos.

---

# 27. CHECKLIST DE RELEASE

Criar:

```text
RELEASE_CHECKLIST.md
```

Com:

### BUILD

[ ] instalação limpa
[ ] build
[ ] frontend
[ ] backend
[ ] banco

### AUTH

[ ] login
[ ] logout
[ ] sessão
[ ] recuperação
[ ] RBAC

### UX

[ ] navegação
[ ] responsividade
[ ] estados
[ ] erros

### DATA

[ ] seed
[ ] migrations
[ ] integridade
[ ] isolamento tenant

### SECURITY

[ ] secrets
[ ] CORS
[ ] auth
[ ] autorização
[ ] validação
[ ] logs

### TEST

[ ] unit
[ ] integration
[ ] E2E
[ ] regression

### DEMO

[ ] perfis
[ ] dashboards
[ ] dados demo
[ ] transações simuladas
[ ] compartilhamento

### RELEASE

[ ] Git limpo
[ ] documentação
[ ] versão
[ ] ZIP
[ ] checksum
[ ] instruções de restauração

---

# 28. MATRIZ DE COBERTURA

Criar uma matriz:

| Funcionalidade | UI | API | Banco | Teste | Perfil | Status |
| -------------- | -- | --- | ----- | ----- | ------ | ------ |

Nenhuma funcionalidade relevante deve permanecer sem classificação.

Use:

```text
PASS
PARTIAL
FAIL
BLOCKED
NOT APPLICABLE
```

---

# 29. NÃO ESCONDER PROBLEMAS

Se encontrar problemas:

NÃO mascarar.

NÃO simplesmente remover funcionalidade.

NÃO transformar erro em "mock" sem documentação.

Classificar:

```text
CRITICAL
HIGH
MEDIUM
LOW
```

Para cada problema:

```text
Problema
Impacto
Causa
Correção
Teste realizado
Resultado
```

---

# 30. REGRA DE IMPLEMENTAÇÃO

Quando encontrar uma falha:

```text
IDENTIFICAR
↓
REPRODUZIR
↓
ISOLAR
↓
CORRIGIR
↓
TESTAR
↓
REGRESSÃO
↓
COMMIT
```

Nunca:

```text
alterar
→ torcer para funcionar
→ continuar
```

---

# 31. ARTIFACTS / INTERFACE INTERATIVA

Se a plataforma permitir utilizar Artifacts ou outro mecanismo de preview/interação:

Utilize-o para criar uma experiência de demonstração quando isso realmente ajudar.

Quero poder:

* abrir a aplicação;
* navegar;
* trocar de perfil;
* visualizar dashboards;
* testar fluxos;
* visualizar estados;
* testar dados demo.

Mas o Artifact/preview NÃO deve substituir o código-fonte real.

A fonte de verdade continuará sendo o repositório.

---

# 32. AMBIENTE DE TESTE EXTERNO

Preparar uma forma documentada para eu compartilhar a aplicação com outras pessoas.

Criar instruções:

```text
1. iniciar aplicação
2. iniciar tunnel
3. obter URL
4. compartilhar URL
5. fornecer usuário DEMO
6. coletar feedback
7. encerrar ambiente
```

Se possível, criar também:

```text
TESTER_GUIDE.md
```

Explicando aos testadores:

* como entrar;
* quais perfis testar;
* o que testar;
* o que não fazer;
* como reportar bugs.

---

# 33. SISTEMA DE FEEDBACK

Se já existir mecanismo de feedback no SaaS, utilize-o.

Caso não exista, não crie uma plataforma inteira de feedback sem necessidade.

Pode ser suficiente documentar um fluxo externo simples.

O importante é que os testadores consigam relatar:

```text
Tela
Perfil
Passos
Resultado esperado
Resultado obtido
Screenshot
Prioridade
```

---

# 34. LIMPEZA FINAL

Antes da release:

remover:

* arquivos temporários;
* logs gigantes;
* caches;
* node_modules;
* secrets;
* credenciais;
* dados reais;
* dumps;
* arquivos pessoais;
* artefatos de debug;
* builds desnecessários.

NÃO remover arquivos necessários para reprodução.

Criar um `.gitignore` robusto.

---

# 35. ZIP FINAL

Ao terminar, gerar um pacote:

```text
IMPACTO-SAAS-LOCAL-RELEASE-[VERSION].zip
```

O ZIP deve conter tudo que é necessário e pertencente ao SaaS para reprodução local.

Incluir:

```text
source code
configuration examples
database migrations
demo seed
tests
scripts
documentation
Docker files
deployment preparation
assets
package manifests
```

NÃO incluir:

```text
node_modules
.git
secrets
.env reais
tokens
senhas
credenciais
dados pessoais
cache
logs temporários
```

A menos que exista uma razão técnica explícita e documentada.

---

# 36. ZIP DEVE SER TESTADO

Não basta criar o ZIP.

Depois de gerar:

1. extrair em diretório limpo;
2. instalar;
3. configurar;
4. executar seed;
5. executar testes;
6. iniciar;
7. navegar;
8. verificar principais fluxos.

Somente depois considerar o ZIP válido.

---

# 37. CHECKSUM

Gerar checksum do pacote final.

Por exemplo:

```text
SHA256
```

Documentar:

```text
arquivo
versão
data
SHA256
```

---

# 38. VERSIONAMENTO

Definir versão apropriada.

Exemplo:

```text
v0.9.0-demo
v0.9.0-rc1
```

Escolha de acordo com o estado real.

NÃO declarar:

```text
production-ready
```

se ainda existirem blockers.

---

# 39. RELEASE REPORT FINAL

Criar:

```text
FINAL_RELEASE_REPORT.md
```

Com:

## 1. Resumo executivo

## 2. Estado atual

## 3. O que foi implementado

## 4. O que foi corrigido

## 5. Testes realizados

## 6. Testes aprovados

## 7. Testes falhos

## 8. Problemas conhecidos

## 9. Riscos

## 10. Segurança

## 11. Perfis testados

## 12. Telas testadas

## 13. APIs testadas

## 14. Multi-tenancy

## 15. Transações simuladas

## 16. Performance

## 17. Como executar localmente

## 18. Como compartilhar para testes

## 19. Como gerar nova instalação

## 20. O que ainda falta antes de produção

---

# 40. TABELA FINAL DE PENDÊNCIAS

Criar:

| Item | Prioridade | Motivo | Solução | Status |
| ---- | ---------- | ------ | ------- | ------ |

Separar:

```text
BLOCKER
HIGH
MEDIUM
LOW
FUTURE
```

---

# 41. CRITÉRIO DE CONCLUSÃO

NÃO considere a tarefa concluída simplesmente porque:

```text
build passou
```

A tarefa somente estará concluída quando:

```text
Código auditado
+
Ambiente local reproduzível
+
Banco funcionando
+
Seed funcionando
+
Perfis funcionando
+
Telas navegáveis
+
RBAC testado
+
Multi-tenancy testado
+
Fluxos principais testados
+
Transações simuladas testadas
+
E2E funcionando
+
Regressão executada
+
Segurança revisada
+
Documentação atualizada
+
Git versionado
+
ZIP criado
+
ZIP testado
+
Checksum criado
+
Relatório final criado
```

---

# 42. ORDEM OBRIGATÓRIA DE EXECUÇÃO

Siga esta ordem:

```text
FASE 01
Auditoria

↓

FASE 02
Checkpoint Git

↓

FASE 03
Arquitetura do ambiente local

↓

FASE 04
Docker/virtualização/reprodutibilidade

↓

FASE 05
Banco + migrations + seed

↓

FASE 06
Perfis + RBAC

↓

FASE 07
Todas as telas

↓

FASE 08
Fluxos

↓

FASE 09
E2E

↓

FASE 10
Multi-tenancy

↓

FASE 11
Transações simuladas

↓

FASE 12
Logs/auditoria

↓

FASE 13
UX/responsividade

↓

FASE 14
Segurança

↓

FASE 15
Performance

↓

FASE 16
Regressão

↓

FASE 17
Instalação limpa

↓

FASE 18
Compartilhamento externo

↓

FASE 19
Documentação

↓

FASE 20
Release Candidate

↓

FASE 21
ZIP

↓

FASE 22
Testar o ZIP

↓

FASE 23
Checksum

↓

FASE 24
Git final

↓

FASE 25
FINAL_RELEASE_REPORT.md
```

---

# 43. USO DOS CRÉDITOS / RECURSOS

Utilize os recursos disponíveis de forma criteriosa.

Não desperdice créditos com:

* explicações repetitivas;
* análises superficiais;
* reescritas desnecessárias;
* geração de código que não será utilizado;
* documentação duplicada.

Priorize:

1. inspeção real;
2. execução;
3. testes;
4. debugging;
5. correções;
6. regressão;
7. validação;
8. empacotamento.

Sempre que possível, valide executando o software em vez de apenas inferir pelo código.

---

# 44. REGRA CONTRA "FAKE SUCCESS"

É PROIBIDO declarar:

```text
implemented
fixed
working
tested
secure
ready
```

sem evidência.

Sempre que possível, apresentar:

```text
COMANDO EXECUTADO
RESULTADO
STATUS
```

Exemplo:

```text
npm run test:e2e
42 passed
0 failed
STATUS: PASS
```

---

# 45. NÃO PARAR NO PRIMEIRO ERRO

Se um teste falhar:

```text
investigar
→ corrigir
→ executar novamente
→ verificar regressão
```

Continue até:

* corrigir;
* ou classificar claramente como BLOCKED.

Nunca esconder uma falha para concluir a etapa.

---

# 46. ESTADO FINAL ESPERADO

Quero terminar esta etapa com uma estrutura semelhante a:

```text
IMPACTO/
│
├── apps/
├── packages/
├── frontend/
├── backend/
├── database/
├── tests/
├── e2e/
├── scripts/
├── docs/
├── public/
├── docker/
│
├── .env.example
├── docker-compose.yml
├── package.json
├── README.md
├── SETUP.md
├── DEMO.md
├── TESTING.md
├── SECURITY.md
├── ARCHITECTURE.md
├── TESTER_GUIDE.md
├── RELEASE_CHECKLIST.md
└── FINAL_RELEASE_REPORT.md
```

A estrutura acima é apenas referência.

Preserve a arquitetura real do projeto se ela já estiver bem estruturada.

---

# 47. ENTREGA FINAL

Ao terminar, NÃO apenas diga "concluído".

Entregue um resumo objetivo:

```text
VERSION:
BRANCH:
FINAL COMMIT:

BUILD:
TESTS:
E2E:
SECURITY:
MULTI-TENANT:
DEMO:
LOCAL RUN:

TELAS TESTADAS:
PERFIS TESTADOS:
FLUXOS TESTADOS:

BLOCKERS:
HIGH:
MEDIUM:
LOW:

ZIP:
SHA256:

PRÓXIMA ETAPA:
```

Também forneça o caminho/arquivo do ZIP final.

---

# 48. REGRA FINAL

Você tem autonomia para corrigir problemas encontrados.

Mas preserve o conceito e a arquitetura do SaaS IMPACTO.

Não reescreva o projeto inteiro sem necessidade.

Não introduza dependências desnecessárias.

Não transforme uma aplicação real em um mock.

Não esconda funcionalidades quebradas.

Não invente dados reais.

Não use credenciais reais.

Não faça deploy irreversível.

Trabalhe de forma incremental.

Teste.

Versione.

Corrija.

Teste novamente.

Documente.

Empacote.

Teste o pacote.

E somente então entregue a RELEASE CANDIDATE LOCAL.

## RESULTADO FINAL DESEJADO

O objetivo é que eu possa receber o ZIP, colocar em uma máquina local limpa, seguir o README e ter:

**o SaaS IMPACTO inteiro funcionando em ambiente de demonstração/teste, com todas as telas, perfis, dashboards, permissões, dados sintéticos, fluxos e transações simuladas acessíveis e testáveis, permitindo inclusive compartilhar temporariamente a interface com terceiros antes da hospedagem e publicação real.**

Comece agora pela AUDITORIA FULL do projeto.

Não pule diretamente para implementação.

Primeiro descubra exatamente o que existe, o que funciona, o que está incompleto e o que precisa ser feito para transformar o estado atual em uma RELEASE CANDIDATE LOCAL reproduzível.
