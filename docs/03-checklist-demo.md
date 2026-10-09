# 03 — Checklist do ambiente DEMO (dados fictícios)

**Boa notícia:** o DEMO **já existe e está no ar** — Railway, ambiente `demo`, serviço `ideal-delight`, endereço
`https://ideal-delight-demo-76bb.up.railway.app`, com **banco próprio do Railway** (não usa o Supabase) e dados
fictícios. Ele se atualiza sozinho a cada mudança na `main`. O monitor testou o `/healthz` dele com sucesso hoje às
20:03 UTC (execução manual do workflow `monitor`).

Então o que falta não é "publicar o demo", e sim **deixá-lo seguro para mostrar a outras pessoas** e **separá-lo de vez
da produção**. Os passos estão em ordem. Onde houver senha ou chave, **você cola direto no painel** (Railway, GitHub ou
Cloudflare) — nunca no chat.

> Por que o demo usa um banco separado do Supabase: assim, nada do demo cai na produção por engano. Recomendo manter.

---

## 0. Antes de tudo: duas pendências de segurança (valem para os dois ambientes)

- [ ] **Trocar o token do backup** (as chaves do `github-backup-3` apareceram num chat):
  1. Cloudflare → R2 → *Manage R2 API Tokens* → *Create API token* → permissão **Object Read & Write**, só no bucket
     `impacto-backups`.
  2. GitHub → repositório → *Settings* → *Secrets and variables* → *Actions* → editar `R2_BACKUP_ACCESS_KEY_ID`
     (32 caracteres) e `R2_BACKUP_SECRET_ACCESS_KEY` (64 caracteres) — cole os valores novos.
  3. GitHub → *Actions* → **backup-supabase** → *Run workflow*. Tem de terminar em verde (me avise que eu confiro).
  4. Cloudflare → apagar os tokens `github-backup`, `github-backup-2` e `github-backup-3`.
- [ ] **Publicar a produção** para aplicar a proteção 0071: Railway → ambiente `production` → serviço
      `impactohubsocial` → `Ctrl+K` → "Deploy latest commit"; repetir no serviço `pleasing-trust`.
      Depois eu rodo o diagnóstico do banco e confirmo "0 pendentes".

## 1. Conferir o que o demo tem hoje

- [ ] Abrir `https://ideal-delight-demo-76bb.up.railway.app/healthz` no navegador. Deve aparecer `"status": "ok"` e
      `"env": "development"`.
- [ ] Abrir `/readyz`. Deve aparecer `"status": "ready"`, `"database": "ok"`, `"storage": "local"`, `"mail": "console"`.
- [ ] Entrar com uma conta de demonstração (as senhas estão no seu gerenciador, não aqui) e percorrer: painel, projeto,
      candidatura, dossiê.

## 2. Deixar claro para quem visita que é DEMO

- [ ] **Hoje o site não mostra nenhum aviso de demonstração** (conferi no código: a tela só lê o modo de execução para o
      login com SSO). E, no modo `development`, o cadastro funciona sem os termos aprovados — então **qualquer visitante
      pode criar conta**, e alguém pode digitar dados reais. Colocar uma faixa fixa "Ambiente de demonstração — dados
      fictícios — não cadastre dados reais" é o primeiro item do próximo incremento (`04-roadmap.md`, item 4).
- [ ] Decidir quem pode ver o demo: (a) aberto a qualquer pessoa com o link; (b) só convidados. Ver decisões em
      `04-roadmap.md`.

## 3. Endereço bonito para o demo (opcional — sua pendência 2)

Fazer **depois** que o domínio principal estiver funcionando (pendência 1).

- [ ] Railway → ambiente `demo` → serviço `ideal-delight` → *Settings* → *Networking* → *Custom Domain* →
      `demo.impactohubsocial.com.br`. O Railway mostra um registro **CNAME** (e às vezes um TXT de verificação).
- [ ] Cloudflare → `impactohubsocial.com.br` → *DNS* → *Add record* → copiar exatamente o que o Railway mostrou.
      Nuvem **cinza** ("DNS only") até o Railway mostrar o certificado emitido.
- [ ] Testar `https://demo.impactohubsocial.com.br/healthz`.
- [ ] GitHub → *Settings* → *Secrets and variables* → *Actions* → *Variables* → `MONITOR_URLS`: incluir o endereço novo.

## 4. Recriar os dados fictícios quando precisar

O comando abaixo só funciona no modo de demonstração — em produção ele se recusa a rodar.

- [ ] No seu computador, com a CLI do Railway (`railway login` e `railway link`, escolhendo o ambiente `demo`):
      `railway ssh --service ideal-delight` e, dentro dele, `python3 -m impacto.cli seed-demo`.
      (Se preferir, me chame nessa hora que eu guio tela a tela.)
- [ ] Ele cria 15 contas (uma por perfil: OSC, empresa, governo, apoiador, prestador, administração, revisão, suporte,
      financeiro…) e mostra os e-mails. As senhas vêm da variável `DEMO_PASSWORD` do serviço (você define no painel).

## 5. Separar de vez o demo da produção

- [ ] **Limpar a produção** (problema C1 da auditoria): hoje o banco de produção tem as 15 contas de demonstração.
      Decisão sua — desativar essas contas ou recriar o banco de produção. Eu preparo o procedimento, testo no demo e só
      executo com o seu "pode fazer".
- [ ] Confirmar no Railway que o serviço `ideal-delight` **não** tem nenhuma variável apontando para o Supabase
      (`DATABASE_URL` tem de ser a do Postgres do próprio demo).
- [ ] Confirmar que o demo **não** usa o bucket `impacto-arquivos` da produção (hoje usa disco local — certo para demo,
      com a ressalva de que os arquivos somem a cada atualização).

## 6. Pronto para mostrar

- [ ] Itens 0, 1, 2 e 5 concluídos.
- [ ] Um roteiro curto de demonstração (quem é cada conta e o que mostrar) — posso escrever no próximo incremento.

---

**O que NÃO é deste checklist (é da produção):** domínio `www` (pendência 1), e-mail autenticado (pendência 3),
revisão jurídica (pendência 6), subir o Supabase para Micro (pendência 7).
