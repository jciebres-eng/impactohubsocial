# RB-07 — Perda, corrupção ou alteração indevida do banco de dados

**Sinais:** alerta `BackupFalhou` ou `BackupSemSucessoEm26h`; dados sumiram; `/readyz` aponta migrações pendentes
sem deploy; alguém rodou comando no banco por engano.

## Conter

1. Acione o interruptor de emergência ([RB-06](RB-06-queda-de-provedor-e-interruptor.md)) para ninguém gravar
   por cima de um banco em estado errado.
2. **Não restaure por cima da produção sem decisão do responsável.** Restauração é feita primeiro num banco NOVO.

## Onde estão as cópias

| Cópia | Onde | Retenção |
|---|---|---|
| Backups diários do Supabase | dentro do próprio Supabase | 7 dias (plano Pro) |
| Cópia externa diária, cifrada | R2, bucket `impacto-backups`, prefixo `supabase/` | 30 dias (regra de ciclo de vida) |

Desde a v0.35.0 a cópia externa usa **cifra autenticada** (`.dump.aead`, `scripts/backup_crypt.py`): arquivo
alterado, truncado ou com frase errada **falha** ao decifrar. O SHA-256 de cada cópia fica também no resumo da
execução do workflow `backup-supabase` no GitHub (fora do bucket). Cópias antigas `.dump.enc` (openssl) continuam
legíveis até sair da retenção.

## Restaurar (sempre num banco novo primeiro)

1. Rode o workflow `backup-supabase` no modo `ensaio-restauracao`: ele baixa a cópia mais recente, confere o hash,
   decifra e restaura num PostgreSQL descartável com os verificadores de integridade. Se passar, a cópia é boa.
2. Para restaurar de verdade: siga os comandos no cabeçalho de `.github/workflows/backup-supabase.yml`
   (`backup_crypt.py decrypt` → `scripts/managed_backup_restore.sh`). Um `pg_restore` direto **falha** (extensões
   no esquema `extensions`).
3. Aponte a aplicação para o banco restaurado só com decisão do responsável, e anote a janela de dados perdida
   (entre a cópia e o incidente).

## Depois

Conte o que se perdeu, avise quem foi afetado (se houver dado pessoal → [RB-02](RB-02-vazamento-de-dados-pessoais.md))
e registre a causa e a correção.
