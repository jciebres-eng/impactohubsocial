# Plataforma Impacto: contexto para sessões do Claude

Leia antes de mexer em código, deploy ou infraestrutura. Nenhum segredo neste arquivo, só onde cada coisa mora.

## Infraestrutura em uso (PaaS, montada em 2026-10-09)

| Peça | Onde | Observação |
|---|---|---|
| Backend (site/API) | Railway Pro, projeto `ac7c5eae-5a4d-4369-b163-ae198cf7efc4`, ambiente **production**, serviço `impactohubsocial`, região US West | `start_container.sh` roda migrações como admin e depois troca para o papel `impacto_app` |
| Worker (rotinas) | mesmo ambiente, serviço `pleasing-trust` | `python3 -m impacto.jobs loop`; variáveis são referências `${{impactohubsocial.*}}` |
| Antivírus | mesmo ambiente, serviço `clamav` | usado por `pending_scans` |
| Banco | Supabase Pro, projeto `efhhwjhrlbbmtuwjsbkk` (us-west-2) | conexão pelo **pooler de sessão** (porta 5432). `IMPACTO_APP_ROTATE_PASSWORD=false` (o pooler guarda senha em cache) |
| Arquivos | Cloudflare R2, bucket `impacto-arquivos` | endpoint `https://a3be721284ccd50cd9a7514140f7b85a.r2.cloudflarestorage.com`, região `auto` |
| Backups externos | R2, bucket `impacto-backups`, prefixo `supabase/` | workflow `backup-supabase` (diário 06:17 UTC), cifrado com `BACKUP_PASSPHRASE`; retenção 30 dias por regra de ciclo de vida |
| Monitor de queda | workflow `monitor` (a cada 10 min) | URLs na variável `MONITOR_URLS` |
| DNS/segurança | Cloudflare, zona `impactohubsocial.com.br` | domínio comprado no Registro.br; site final `https://www.impactohubsocial.com.br` |
| E-mail | Brevo SMTP `smtp-relay.brevo.com:587` | chave renova em 2027-09 |
| Demo | Railway, ambiente **demo**, serviço `ideal-delight` | Postgres próprio, dados fictícios, `IMPACTO_ENV=development`, storage local, e-mail no console |

## Como uma mudança chega ao ar

1. Commit/merge na `main` do GitHub.
2. O **demo** publica sozinho.
3. A **produção** precisa de um clique: Railway, serviço `impactohubsocial`, Ctrl+K, "Deploy latest commit". Repita no `pleasing-trust` quando mexer em `impacto/jobs.py` ou no worker.
4. Migrações novas vão em `backend/migrations/NNNN_*.sql`, só para frente. Teste no demo antes da produção.

## Regras desta instalação

- Segredos ficam só no Railway (variáveis), no GitHub (Actions secrets) e no gerenciador de senhas do responsável. Nunca em commit, chat ou arquivo.
- A produção só recebe dados reais depois da revisão jurídica dos termos de uso e da política de privacidade.
- A API REST pública do Supabase fica fechada (migração 0071). Todo acesso ao banco passa pelo backend.
