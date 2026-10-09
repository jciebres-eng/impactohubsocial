# Infraestrutura — Railway + Supabase + Cloudflare R2 + Cloudflare (v0.31.0)

> **SUPERADO EM PARTE pela v0.32.0 (09/10/2026, noite).** Este documento descreve o estado de antes de a infraestrutura
> ser montada na outra conversa. O estado em uso está no `CLAUDE.md`; os passos atuais, em `docs/03-checklist-demo.md` e
> `docs/04-roadmap.md`. Mantido sem alteração no restante, como registro.

> **O que este documento é:** o estado **comprovado** da infraestrutura em 09/10/2026, a configuração-alvo
> de cada serviço derivada do código real, e o que falta — com quem faz. **Não é prova de que o sistema está
> publicado.** Cada linha diz de onde veio a evidência. Nada foi alterado em produção, DNS, cobrança ou
> dados nesta rodada; a única operação contra o Supabase foi **leitura** (diagnóstico e `pg_dump`).

## 1. Identidade do código (Gate A)

| Item | Valor | Evidência |
|---|---|---|
| Repositório | `jciebres-eng/impactohubsocial` | `git remote` |
| Branch de trabalho | `infra/v0.31.0` (o `main` é o que o Railway publica — trabalho em andamento fica fora dele) | `git branch` |
| Baseline do pacote | `IMPACTO_TRUST_FINAL_RELEASE_0.29.01_BASELINE.zip` = SHA-256 `d8aec424…a940c3` = **o mesmo ZIP da v0.29.0** entregue em 08/10 (tag `dd2f8c3`) | `sha256sum`; ver `docs/release/REPO_BASELINE_DIFF.md` |
| "0.29.01" × "v0.29.0" | o nome do arquivo foi alterado fora do repositório; o conteúdo é a v0.29.0 | mesmo SHA-256 |
| Repositório × baseline | o repositório está à frente: v0.30.0 (tag `5d46e50`) + análise econômica (`171d8b4`) + esta rodada | `git log dd2f8c3..HEAD` |

## 2. O que existe de fato em cada serviço

### 2.1 Supabase (PostgreSQL gerenciado) — **comprovado por leitura**

Diagnóstico somente leitura (`scripts/supabase_check.py`, transação `READ ONLY`), execuções
[`37974779816`](https://github.com/jciebres-eng/impactohubsocial/actions/runs/37974779816) e
[`37975067994`](https://github.com/jciebres-eng/impactohubsocial/actions/runs/37975067994):

| Item | Estado |
|---|---|
| Servidor | PostgreSQL 17.11 |
| Conexão administrativa | `postgres` (não é superusuário; pode criar papel), pelo **pooler de sessão** (IPv4) |
| Papel da aplicação `impacto_app` | login sim · **superusuário não · ignora RLS não** · usa `extensions` sim |
| Migrações | **71 aplicadas · 0 pendentes · 0 com conteúdo diferente** · 1 que o repositório não conhece: `0063_v0231_supabase_pgcrypto_search_path` (aplicada por uma publicação de terceiro em 07/10; inofensiva, já documentada) |
| Linha do tempo | 07/10 21:15–21:44 UTC (0001–0063) · 08/10 04:27 (0063 do repo, via workflow) · **09/10 18:24 UTC: 0064–0070 num único lote** |
| Quem aplicou o lote de 09/10 | **não foi o workflow do GitHub** (nenhuma execução `aplicar` desde 08/10) e não coincide com push (último push 16:55 UTC). O padrão — migração + troca da senha de `impacto_app` no mesmo evento — é o do `start_container.sh` com `IMPACTO_APP_ROTATE_PASSWORD=true`. **Hipótese a confirmar:** primeira implantação do Railway ao ser ligado ao repositório. |
| Senha de `impacto_app` | **não confere** com o segredo `IMPACTO_APP_PASSWORD` do GitHub — foi trocada em 09/10 |
| Sessões abertas agora | nenhuma de `impacto_app` (só as internas do Supabase: PostgREST, Supavisor, pg_cron, exporter) → **nenhuma instância do IMPACTO conectada no momento do diagnóstico** |
| Dados | 16 usuários (**15 de demonstração + 1 real**) · 7 organizações · cadeia de auditoria válida |
| Backup + restauração | **PASS** — ver §5 |

### 2.2 Railway — **não comprovado** (sem acesso)

- Nenhum *deployment* nem *check-run* do Railway aparece nos commits do GitHub (`GET /deployments`,
  `GET /commits/{sha}/check-runs`): a integração não reporta ao GitHub, ou não está ligada a este repositório.
- A única evidência indireta é o lote de migrações de 09/10 18:24 UTC (§2.1).
- **Sem `railway.json` de propósito:** o *Config as Code* do Railway está **descontinuado** — "New services cannot
  opt into Config as Code" e os arquivos deixam de ser lidos em **2026-12-01 (hard cutoff)**
  ([docs.railway.com/config-as-code](https://docs.railway.com/config-as-code)). O substituto
  (`.railway/railway.ts`) **não é lido no deploy**; só a CLI do Railway, com o login do proprietário, o aplica
  ([docs.railway.com/infrastructure-as-code](https://docs.railway.com/infrastructure-as-code)). A configuração
  abaixo vai, portanto, no painel — e `railway config pull` a exporta para auditoria (valores secretos ocultos).

### 2.3 Cloudflare R2 — **não comprovado** · 2.4 Cloudflare DNS/WAF — **não comprovado** · 2.5 SMTP — **não comprovado**

Nenhum acesso nesta sessão. Os verificadores estão prontos (§6).

## 3. Configuração-alvo no Railway (derivada do código)

Um projeto Railway com **um ambiente por estágio** (`staging`, `production`), cada um com três serviços.
Mesma imagem (o `Dockerfile` da raiz — o Railway sempre o usa quando existe) para `api` e `worker`.

| Serviço | Origem | Start command | Healthcheck | Réplicas | Observações |
|---|---|---|---|---|---|
| `api` | GitHub `jciebres-eng/impactohubsocial`, branch `main` (produção) / `staging` | (vazio = `CMD` do Dockerfile: `sh /app/start_container.sh`) | `/readyz`, timeout ≥ 300 s (o entrypoint migra antes de abrir a porta) | 1 para começar | migra com lock consultivo (réplicas extras esperam); troca para `impacto_app` antes de servir |
| `worker` | mesmo repositório e branch | `sh /app/start_worker.sh` | nenhum (não abre porta) | 1 | **não migra**; espera o esquema ficar em dia; laço de 21 tarefas (antivírus pendente, prazos, retenção LGPD, canário, backup lógico…); 2 réplicas seriam inofensivas (lock) |
| `clamav` | imagem Docker `clamav/clamav:stable` | padrão da imagem | nenhum | 1 | rede privada apenas; sem ele, arquivos ficam em quarentena e downloads são **bloqueados** (falha fechada) |

Ensaio local do worker (09/10): esquema pendente → sai para reiniciar; esquema em dia → conecta como
`impacto_app` e roda o ciclo: **18 tarefas OK, 2 "não configurado"** (`backup`: `BACKUP_DIR`; `email_canary`:
`EMAIL_CANARY_TO`).

### 3.1 Variáveis por serviço (nomes; nunca valores)

Valores só no painel do Railway, por ambiente. No `worker`, use **variáveis de referência** para as que são da
`api` (sintaxe de referência entre serviços do Railway), para haver **uma** fonte de cada segredo.

| Variável | api | worker | Observação |
|---|---|---|---|
| `IMPACTO_ENV` | `staging` / `production` | igual | endurece: exige chaves ≥ 32, cookie seguro, SMTP, https |
| `DATABASE_URL` | URL **administrativa** do **pooler de sessão** do Supabase + `?sslmode=require` | referência à da api | o entrypoint migra com ela e a troca por `impacto_app` antes de servir. **Não use o pooler de transação (6543):** migrações e tarefas usam lock consultivo de sessão |
| `IMPACTO_APP_PASSWORD` | senha de `impacto_app` (≥ 16) | referência à da api | **uma** fonte: a do Railway. O segredo homônimo do GitHub precisa ser igualado (ou o modo `aplicar` do workflow recusa/derruba) |
| `IMPACTO_BOOTSTRAP_EXTERNAL` | `true` | — | cria `impacto_app` se faltar |
| `IMPACTO_APP_ROTATE_PASSWORD` | **`false`** (só `true` numa troca planejada, e volta a `false`) | — | rotação permanente + duas fontes de senha = um serviço derruba o outro |
| `SECRET_KEY`, `VOUCHER_HMAC_KEY`, `FIELD_ENCRYPTION_KEY` | geradas uma vez por ambiente | referência | `FIELD_ENCRYPTION_KEY` perdida = dado cifrado perdido (guardar cópia no cofre) |
| `PUBLIC_BASE_URL` | `https://<domínio do ambiente>` | referência | |
| `COOKIE_SECURE` | `true` | — | |
| `WEB_CONCURRENCY` | `2` | — | conexões = réplicas × workers × `DATABASE_POOL_SIZE` + worker: caber no *pool size* do Supabase |
| `MAIL_PROVIDER`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | provedor real | referência | `console` é recusado fora de development |
| `STORAGE_PROVIDER` | `s3` | referência | `local` sem volume = arquivos somem no redeploy (agora sinalizado em `/readyz` e no log) |
| `S3_ENDPOINT`, `S3_REGION`, `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` | R2: `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`, **`auto`**, bucket do ambiente, token do bucket | referência | a configuração **recusa** região AWS com endpoint R2 |
| `ANTIVIRUS_PROVIDER`, `CLAMD_HOST`, `CLAMD_PORT` | `clamd`, `clamav.railway.internal`, `3310` | igual | |
| `EMAIL_CANARY_TO`, `BACKUP_DIR` | — | opcionais | o backup lógico da aplicação é camada **adicional** ao do Supabase |
| `IMPACTO_SEED_DEMO` | **nunca** | **nunca** | recusado em staging/production |

## 4. Achados e riscos (gap register)

| ID | Prioridade | Achado | Evidência | Correção / quem |
|---|---|---|---|---|
| G1 | **P0** | **Um único projeto Supabase** com 15 contas de demonstração e 1 conta real. Não há separação staging × produção. Contas de demonstração têm senha conhecida por quem semeou | §2.1 | **Decisão do proprietário:** (a) este projeto vira **staging** e cria-se um projeto de produção limpo; ou (b) este vira produção e as contas de demonstração são desativadas antes de abrir. Recomendação: (a) |
| G2 | **P0** | Estado do Railway desconhecido: quem migrou em 09/10, com que `IMPACTO_ENV`, armazenamento, SMTP | §2.2 | proprietário: URL pública + `railway config pull` → eu audito; `pos-deploy` verifica de fora |
| G3 | P1 | Senha de `impacto_app` divergente entre banco e segredo do GitHub | §2.1 | igualar o segredo do GitHub ao valor do Railway; `IMPACTO_APP_ROTATE_PASSWORD=false` |
| G4 | P1 | Nenhum serviço roda as tarefas periódicas (antivírus, retenção LGPD, prazos) | código: só `impacto.jobs loop` as executa | **corrigido no código:** `start_worker.sh`; proprietário cria o serviço `worker` |
| G5 | P1 | Sem antivírus implantado → uploads em quarentena, downloads bloqueados | `ANTIVIRUS_PROVIDER` padrão `none`; download recusa `pending_scan` em produção | serviço `clamav` (§3); **não testado no Railway** (rede privada) |
| G6 | P1 | Armazenamento local num contêiner sem volume perde arquivos a cada deploy, sem aviso | `STORAGE_PROVIDER=local` era aceito calado em produção | **corrigido:** `/readyz` → `storage_durable:false` + aviso no log; alvo R2 |
| G7 | P1 | Região do R2: com a região de exemplo (`sa-east-1`) toda URL assinada falharia | doc. R2: região `auto` | **corrigido:** a configuração recusa |
| G8 | P1 | Adaptador S3 nunca tinha falado com um servidor S3 | só vetor de teste da AWS | **corrigido:** job `armazenamento` no CI contra servidor que valida SigV4 (CloudServer) |
| G9 | P1 | O R2 **não documenta** `response-content-disposition` nem *path-style* (o adaptador usa ambos) | página "S3 API compatibility" do R2 | verificar no bucket real (workflow `armazenamento`); falha de nome do arquivo é informativa, não de segurança |
| G10 | P1 | `deploy.yml` era um modelo que terminava em `echo "Implemente aqui o rollout"` | arquivo | **corrigido:** removido; `pos-deploy.yml` verifica a instância (commit, readyz, cabeçalhos, smoke) sem publicar |
| G11 | P1 | Nada provava que o commit no ar é o commit testado | `/healthz` sem commit | **corrigido:** `/healthz` → `commit` (Railway: `RAILWAY_GIT_COMMIT_SHA`) |
| G12 | P1 | CI do `main` vermelho desde `171d8b4` (arquivos da análise fora do manifesto) | run 37962597399 | fechamento da v0.31.0 regenera o manifesto |
| G13 | P2 | `sslmode` não explícito nas URLs do Supabase (libpq usa `prefer`) | URL do painel | acrescentar `?sslmode=require` |
| G14 | P2 | A credencial administrativa fica no ambiente do contêiner da api (o entrypoint migra com ela) | `start_container.sh` | aceitável para começar; alternativa: comando de pré-deploy do Railway com variável própria |
| G15 | P2 | Imagens públicas do MinIO deixaram de ser baixáveis | run do CI 37978407913 | trocado por CloudServer no CI; sem efeito no produto |
| G16 | P2 | Ações do GitHub em Node 20 (aviso de descontinuação) | anotações do CI | atualizar `actions/*` numa rodada de manutenção |

## 5. Backup e restauração — **comprovado**

Execução [`37975650545`](https://github.com/jciebres-eng/impactohubsocial/actions/runs/37975650545) (modo
`backup-restaurar` do workflow `supabase`, `scripts/managed_backup_restore.sh`):

| Medida | Resultado |
|---|---|
| Versões | `pg_dump` 17.11 · origem 17.11 · destino 17.11 (descartável, dentro do job) |
| Escopo | schema `public` (o do IMPACTO) + extensões do produto recriadas no mesmo schema da origem (`pgcrypto` em `extensions`; `citext`, `unaccent`, `pg_trgm` em `public`) |
| Dump | 2,3 MB em 11,6 s; SHA-256 conferido antes de restaurar |
| Restauração + verificações | 3,3 s: 71 migrações, cadeias de hash (ledger e auditoria) íntegras, camada econômica **desligada**, travas de impacto íntegras, camada de operação íntegra |
| Contagens | **341 tabelas, 2.577 linhas — idênticas** entre origem e restauração |
| **RTO medido** | **15,1 s** (dump + restauração verificada), no volume atual |
| Dados | dump apagado ao fim; **nenhum artefato publicado** (há 1 usuário real) |

O que isto **não** cobre: o backup gerenciado do próprio Supabase (diário/PITR conforme o plano — verificar no
painel: *Database → Backups*), arquivos do R2 (usar versionamento/cópia do bucket) e o RPO (depende da frequência
escolhida). Rotina: rodar `backup-restaurar` **antes de toda migração em produção** e mensalmente.

## 6. Verificadores prontos (o proprietário dispara; nada publica)

| Workflow | O que prova | Precisa de |
|---|---|---|
| `supabase` → `verificar` | estado do banco (somente leitura) | `SUPABASE_ADMIN_URL` (existe) |
| `supabase` → `backup-restaurar` | backup **e** restauração verificados | idem |
| `armazenamento` (ambiente `staging`/`production`) | o bucket R2 real com o adaptador do produto | `R2_ENDPOINT`, `R2_BUCKET`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` no ambiente do GitHub |
| `pos-deploy` | commit no ar = commit esperado; `/readyz`; armazenamento durável; antivírus; HTTP→HTTPS; cabeçalhos; smoke de 24 verificações | URL pública; opcional `SMOKE_EMAIL`/`SMOKE_PASSWORD` (conta de TESTE) |

## 7. Cloudflare (DNS, TLS, WAF) — passos, sem execução

1. Exportar a zona atual (registros, MX, SPF, DKIM, DMARC) **antes** de mudar nameservers.
2. Domínio do ambiente no Railway (*Settings → Networking → Custom Domain*): criar o registro que o painel do
   Railway indicar; manter **DNS-only** até o certificado do Railway emitir; só então avaliar o proxy.
3. Com proxy: TLS **Full (strict)**; nenhuma regra de cache em `/v1/*`, `/readyz`, `/healthz`, `/metrics`.
4. WAF/limite de taxa: começar em modo registro; o limitador do próprio backend continua valendo.
5. Depois de qualquer mudança: `pos-deploy` contra o domínio.

## 8. Fora do alcance desta rodada

Deploy, DNS, criação de bucket, troca de senha, migração em produção, cobrança real: todos exigem a sua ação
ou aprovação. Ver `docs/ops/CHECKLIST_PROPRIETARIO_v0310.md`.
