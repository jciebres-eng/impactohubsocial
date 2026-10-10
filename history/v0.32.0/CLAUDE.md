# Plataforma Impacto: contexto para sessões do Claude

Leia antes de mexer em código, deploy ou infraestrutura. Nenhum segredo neste arquivo, só onde cada coisa mora.

## Infraestrutura em uso (PaaS, montada em 2026-10-09)

| Peça | Onde | Observação |
|---|---|---|
| Backend (site/API) | Railway Pro, projeto `ac7c5eae-5a4d-4369-b163-ae198cf7efc4`, ambiente **production**, serviço `impactohubsocial`, região US West | `start_container.sh` roda migrações como admin e depois troca para o papel `impacto_app` |
| Worker (rotinas) | mesmo ambiente, serviço `pleasing-trust` | **Start Command `sh /app/start_worker.sh`** (v0.32.0): espera o banco estar atualizado e troca para `impacto_app` antes de `impacto.jobs loop` — o comando antigo (`python3 -m impacto.jobs loop` direto) rodava com a conexão ADMINISTRATIVA; variáveis são referências `${{impactohubsocial.*}}` |
| Antivírus | mesmo ambiente, serviço `clamav` | usado por `pending_scans` |
| Banco | Supabase Pro, projeto `efhhwjhrlbbmtuwjsbkk` (us-west-2) | conexão pelo **pooler de sessão** (porta 5432). `IMPACTO_APP_ROTATE_PASSWORD=false` (o pooler guarda senha em cache) |
| Arquivos | Cloudflare R2, bucket `impacto-arquivos` | endpoint `https://a3be721284ccd50cd9a7514140f7b85a.r2.cloudflarestorage.com`, região `auto` |
| Backups externos | R2, bucket `impacto-backups`, prefixo `supabase/` | workflow `backup-supabase` (diário 06:17 UTC), cifrado com `BACKUP_PASSPHRASE`; retenção 30 dias por regra de ciclo de vida. **Ensaio de restauração** do backup cifrado mais recente todo dia 1º (e à mão: modo `ensaio-restauracao`); restaurar só com `scripts/managed_backup_restore.sh` (um `pg_restore` direto falha) |
| Monitor de queda | **externo (UptimeRobot/Better Stack) como principal** + workflow `monitor` de hora em hora como reserva | URLs na variável `MONITOR_URLS` |
| DNS/segurança | Cloudflare, zona `impactohubsocial.com.br` | domínio comprado no Registro.br; site final `https://www.impactohubsocial.com.br` |
| E-mail | Brevo SMTP `smtp-relay.brevo.com:587` | chave renova em 2027-09 |
| Demo | Railway, ambiente **demo**, serviço `ideal-delight` | Postgres próprio, dados fictícios, `IMPACTO_ENV=development`, storage local, e-mail no console. Aberto a quem tiver o link; o site mostra a faixa "Ambiente de demonstração" em toda tela |

## Como uma mudança chega ao ar

1. Commit/merge na `main` do GitHub.
2. O **demo** publica sozinho.
3. A **produção** precisa de um clique: Railway, serviço `impactohubsocial`, Ctrl+K, "Deploy latest commit". Repita no `pleasing-trust` quando mexer em `impacto/jobs.py` ou no worker.
4. Migrações novas vão em `backend/migrations/NNNN_*.sql`, só para frente. Teste no demo antes da produção.

## Ferramentas de operação (GitHub → Actions → Run workflow)

| Workflow | Modo | O que faz |
|---|---|---|
| `supabase` | `verificar` | diagnóstico somente leitura do banco de produção (migrações pendentes, papéis, contas) |
| `supabase` | `backup-restaurar` | `pg_dump` do banco e restauração num PostgreSQL descartável, com verificação de integridade |
| `supabase` | `contas-demo-listar` / `-desativar` / `-reativar` | contas `@demo.impacto.local` no banco de produção (desativadas em 09/10/2026; frases de confirmação no próprio workflow) |
| `backup-supabase` | `backup` / `ensaio-restauracao` | cópia cifrada diária / restauração de teste do backup mais recente |
| `pos-deploy` | — | confere de fora a instância publicada: commit no ar, `/readyz`, cabeçalhos, smoke |
| `armazenamento` | — | testa o bucket R2 com o adaptador do produto (precisa dos segredos `R2_*` no ambiente do GitHub) |
| `ci` | — | no pull request: suíte completa; no merge na `main`: só auditoria e imagem (cota de minutos do repositório privado) |

## Regras desta instalação

- Segredos ficam só no Railway (variáveis), no GitHub (Actions secrets) e no gerenciador de senhas do responsável. Nunca em commit, chat ou arquivo.
- A produção só recebe dados reais depois da revisão jurídica dos termos de uso e da política de privacidade.
- A API REST pública do Supabase fica fechada (migração 0071). Todo acesso ao banco passa pelo backend.
- O banco de produção não tem contas de demonstração ativas: as 15 `@demo.impacto.local` foram desativadas e o conteúdo
  público das 5 organizações fictícias saiu do ar em 09/10/2026 (reversível pelo workflow `supabase`, modo `contas-demo-reativar`).
- Repositório PRIVADO por decisão do responsável (09/10/2026); a troca é um clique dele em Settings → General → Danger Zone →
  Change visibility. Com ele privado, cada minuto de Actions sai da cota da conta — por isso o monitor é horário e a suíte
  completa só roda em pull request.
