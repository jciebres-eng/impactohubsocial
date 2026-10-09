# 02 — Auditoria (problemas encontrados, do mais grave ao menos grave)

**Data:** 09/10/2026 · **Branch analisada:** `main` no commit `906d383` · **Feita por:** Claude, a pedido do responsável

Como ler: cada problema tem **o que é** (em linguagem simples), **por que importa**, **como eu sei** (a prova) e
**como resolver**. Nada aqui foi corrigido nesta branch — ela só traz documentos. Nenhuma senha, chave ou token
foi copiado para este arquivo.

Níveis: **CRÍTICO** (resolver antes de qualquer outra coisa) · **ALTO** (antes de receber dados reais) ·
**MÉDIO** (próximas semanas) · **BAIXO** (quando houver tempo).

---

## CRÍTICO

### C1. O banco de PRODUÇÃO tem 15 contas de demonstração

- **O que é:** o banco do Supabase — que é o da produção — tem 17 usuários: **15 são contas de demonstração**
  (as do ambiente de testes) e 2 são contas reais. A regra combinada é "a produção começa limpa, sem dados do demo".
- **Por que importa:** as senhas das contas de demonstração são conhecidas por quem gerou os dados de teste; uma delas
  é de administrador. Numa produção com dados reais, isso é uma porta aberta.
- **Como eu sei:** diagnóstico somente-leitura do banco de hoje, execução do GitHub Actions `37992280274`
  ("17 usuários (15 de demonstração) · 7 organizações").
- **Como resolver:** decisão sua entre (a) desativar as 15 contas e as organizações fictícias, ou (b) recriar o banco
  de produção do zero. Apagar dados é irreversível: eu preparo o procedimento, testo no demo e só executo com a sua
  autorização expressa.

### C2. Chaves do backup expostas numa conversa

- **O que é:** as chaves do token R2 `github-backup-3` (o que grava os backups) foram mostradas num chat.
- **Por que importa:** quem tiver essas chaves pode ler e apagar os backups do banco.
- **Como eu sei:** informação sua (pendência 4). **Não estão no código** — a varredura do repositório não achou nenhum
  segredo (ver "O que está bem", no fim).
- **Como resolver:** criar um token novo só para o bucket `impacto-backups`, colar no GitHub, testar o backup e apagar
  os três tokens antigos (passo a passo no `03-checklist-demo.md`, seção 0).

---

## ALTO

### A1. A proteção nova do banco ainda não está na produção

- **O que é:** a migração 0071 (fecha o acesso direto ao banco pela internet, via API do Supabase) está no código,
  mas **não foi aplicada na produção**.
- **Por que importa:** até lá, continuam abertos os 3 alertas críticos do painel de segurança do Supabase (uma tabela
  técnica e duas visões legíveis por qualquer pessoa que tenha o identificador do projeto — e o repositório é público).
- **Como eu sei:** diagnóstico de hoje: "71 aplicadas · **1 pendente**".
- **Como resolver:** publicar a produção ("Deploy latest commit" no `impactohubsocial` e no `pleasing-trust`) — é a sua
  pendência 5. Depois, rodar o diagnóstico de novo e conferir "0 pendentes".

### A2. O jeito de restaurar o backup, como está escrito, não funciona

- **O que é:** o workflow `backup-supabase` faz a cópia diária, cifra e envia ao R2 — isso está certo e funcionou hoje
  (`37988830616`). Mas as instruções de **restauração** no cabeçalho dele levariam a erro: o banco novo não teria as
  extensões que o sistema usa (`pgcrypto` no esquema `extensions`, `citext`, `unaccent`, `pg_trgm`) e a restauração
  tropeça na criação do esquema `public`.
- **Por que importa:** backup que ninguém consegue restaurar no dia do problema não é backup. E **nenhuma restauração
  dos backups cifrados foi testada até hoje**.
- **Como eu sei:** reproduzi exatamente esses erros hoje, com um dump igual (`--schema=public`), num PostgreSQL de
  teste. A correção existe e foi provada: na branch `infra/v0.31.0`, o script `scripts/managed_backup_restore.sh`
  restaurou o banco do Supabase de verdade (341 tabelas, contagens idênticas, execução `37975650545`).
- **Como resolver:** trazer esse script para a `main`, corrigir as instruções e fazer um ensaio mensal de restauração
  de um backup cifrado do R2.

### A3. O worker roda com a senha de administrador do banco

- **O que é:** o serviço `pleasing-trust` executa `python3 -m impacto.jobs loop` com as variáveis copiadas do serviço
  principal. A variável `DATABASE_URL` do serviço principal é a conexão **administrativa** — o site só troca para o
  usuário limitado (`impacto_app`) *dentro* do seu próprio script de início, e o worker não passa por esse script.
- **Por que importa:** o administrador ignora as regras de isolamento entre organizações (RLS). Um defeito numa rotina
  do worker poderia ler ou alterar dados de qualquer organização.
- **Como eu sei:** `CLAUDE.md` (comando e variáveis do worker) + `backend/start_container.sh` (a troca de usuário acontece
  só ali). **Provável — confirmar** no painel do Railway.
- **Como resolver:** usar um script de início próprio do worker, que troca para `impacto_app` e espera o banco estar
  atualizado (`backend/start_worker.sh`, pronto e testado na branch `infra/v0.31.0`); mudar o comando do serviço.

### A4. Os testes automáticos da `main` estão falhando (3 de 2.408)

- **O que é:** desde 09/10 à tarde, a verificação automática (CI) da `main` termina em vermelho.
- **Por que importa:** com o CI vermelho, ninguém consegue saber se a próxima mudança quebrou algo.
- **Como eu sei:** execução `37988354371`; reproduzi localmente. Causas:
  1. a migração 0071 ligou a proteção (RLS) numa tabela técnica que o teste listava como "a única exceção" — a mudança
     é boa, o teste ficou desatualizado;
  2. o teste novo da v0.30.1 entrou sem regenerar a matriz de integrações (`INTEGRATION_HOMOLOGATION_MATRIX.csv`);
  3. arquivos novos (análise econômica, workflows, `CLAUDE.md`) fora do manifesto da versão.
- **Como resolver:** um incremento pequeno de correção (atualizar o teste com o motivo escrito, regenerar a matriz,
  gerar o manifesto). Não fiz aqui porque esta branch é só de documentos.

### A5. Revisão jurídica e encarregado de dados (LGPD) pendentes

- **O que é:** os Termos de Uso e a Política de Privacidade são minutas. Não há encarregado de dados (DPO) nomeado.
- **Por que importa:** é a condição que você mesmo definiu para dados reais. Já existem 2 contas reais no banco.
- **Como eu sei:** `docs/PUBLICACAO.md` §7 (o cadastro responde "503" em produção enquanto os documentos não forem
  aprovados com revisor nomeado) e documentos de LGPD do repositório (`LGPD_AUDIT.md`).
- **Como resolver:** advogado(a) revisa; aprovação registrada com nome e OAB (`python3 -m impacto.cli legal-approve`);
  nomear o encarregado e publicar o contato dele.

### A6. Senha do usuário da aplicação diferente no GitHub e no banco

- **O que é:** o segredo `IMPACTO_APP_PASSWORD` do GitHub não abre o banco ("senha não confere").
- **Por que importa:** o workflow `supabase` (modo "aplicar") usaria a senha errada. Não afeta o site hoje.
- **Como eu sei:** diagnóstico `37992280274`.
- **Como resolver:** copiar do Railway para o GitHub o mesmo valor (você cola direto no GitHub).

---

## MÉDIO

| # | Problema | Por que importa | Prova | Como resolver |
|---|---|---|---|---|
| M1 | O monitor de queda **ainda não rodou sozinho** (só a execução manual das 20:03 UTC) | se o site cair, ninguém é avisado | lista de execuções do workflow `monitor` | esperar até amanhã; se continuar sem execuções agendadas, usar um serviço externo gratuito (UptimeRobot) — o próprio arquivo já recomenda |
| M2 | Domínio próprio ainda não ativo; `PUBLIC_BASE_URL` aponta para `…up.railway.app` | links de e-mail e redirecionamentos usam o endereço provisório | sua pendência 1 | concluir a pendência 1 (DNS → certificado → variável → publicar) |
| M3 | E-mail (Brevo) sem domínio autenticado (SPF/DKIM) | e-mails da plataforma tendem a cair no spam | sua pendência 3 | registros SPF/DKIM na Cloudflare; remetente `no-reply@impactohubsocial.com.br` |
| M4 | 4 documentos no banco sem o arquivo correspondente no armazenamento | o documento existe na tela, mas o arquivo sumiu | commit `a71aab5` (rotina passou a marcá-los "ilegíveis") | identificar de quem são e pedir novo envio; investigar como se perderam |
| M5 | A versão não foi atualizada: o commit diz "v0.30.1", o arquivo `VERSION` diz 0.30.0 e o CHANGELOG não tem a entrada | confunde quem procura "o que mudou" | `VERSION`, `git log` | registrar a v0.30.1 no próximo incremento |
| M6 | Trabalho pronto e não juntado: branch `infra/v0.31.0` (worker seguro, restauração testada, validação do R2, teste do armazenamento contra servidor real, verificação pós-publicação) | correções úteis paradas | `git log origin/main..infra/v0.31.0` (16 commits; junta sem conflito) | trazer em partes, já ajustadas ao que está no ar (ver roadmap) |
| M7 | `deploy.yml` é só um modelo (termina num aviso "implemente aqui") | parece um caminho de publicação, mas não publica nada | arquivo | remover; o caminho real é o Railway (`CLAUDE.md`) |
| M8 | Backup cifrado com AES-CBC sem verificação de autenticidade; o hash fica no mesmo bucket | quem conseguir escrever no bucket poderia trocar arquivo e hash juntos | `backup-supabase.yml` | guardar o hash também fora do bucket (resumo do GitHub) ou usar cifra autenticada |
| M9 | Antivírus (ClamAV) dentro da rede do Railway não verificado | sem ele, arquivos enviados ficam em quarentena e não podem ser baixados | sem prova de execução | conferir nos logs do worker depois de publicar (pendência 5) |
| M10 | O DEMO não avisa que é demonstração e aceita cadastro de qualquer visitante (no modo `development` a trava dos termos não vale) | alguém pode digitar dados pessoais reais num ambiente sem as proteções da produção | `web/src` não tem aviso global; `services/auth.py` só trava em staging/produção | faixa fixa "ambiente de demonstração" + decidir se o demo fica aberto ou só para convidados |
| M11 | Supabase no plano de máquina Nano | pouca memória para crescer | sua pendência 7 | subir para Micro antes de abrir ao público |

---

## BAIXO

| # | Problema | Como resolver |
|---|---|---|
| B1 | O repositório é **público**: o `CLAUDE.md` mostra os identificadores dos projetos (Railway, Supabase, conta R2). Não são senhas, mas ajudam quem quer atacar | decidir se o repositório fica privado (decisão sua; ver `04-roadmap.md`) |
| B2 | Ações do GitHub em Node 20 (aviso de descontinuação nas execuções) | atualizar as versões das ações num incremento de manutenção |
| B3 | ~166 documentos na raiz do repositório, alguns antigos (Compose/VPS; `UNIT_ECONOMICS.md` ainda cita mensalidades, abolidas pela ADR-341) | marcar como "superado" e mover para `history/` |
| B4 | Avisos de estilo no código em `scripts/` (fora da verificação automática) | limpeza num incremento de manutenção |

---

## O que está bem (verificado)

- **Nenhum segredo no repositório:** `scripts/secrets_scan.py` sobre 1.003 arquivos — "nenhum segredo encontrado"; o
  `gitleaks` do CI varre também o histórico e passou.
- **Dependências:** poucas e com versão fixa (Python: Starlette, Uvicorn, Pydantic, PyJWT, cryptography…; site:
  React 19). A auditoria de vulnerabilidades conhecidas (`pip-audit` + `npm audit`) passou no CI de hoje.
- **Banco:** o usuário da aplicação não é superusuário e não ignora o isolamento entre organizações; trilha de
  auditoria com encadeamento de hash válida.
- **Backup diário externo e cifrado** funcionando (falta só a restauração testada — A2).
- **Cobrança:** nenhuma regra de cobrança ativa; nenhum pagamento real possível.
