# Operação

## Processos
| Processo | Comando | Observação |
|---|---|---|
| API | `uvicorn impacto.main:app` (imagem Docker) | stateless; escale réplicas |
| Jobs | `python -m impacto.jobs loop` (ou `once` via cron) | uma instância (lock consultivo); intervalo `JOBS_INTERVAL_SECONDS` (900) |
| Migrações | `python -m impacto.db.migrate` | papel dono; forward-only |
| Admin/CLI | `python -m impacto.cli create-admin|gen-secrets|seed-demo` | seed só dev/test |

## Jobs (`jobs.py`)
`close_calls` (fecha editais vencidos) · `import_sources` (importa feeds JSON/RSS cadastrados) · `saved_searches` (alertas) · `pending_scans` (reprocessa antivírus pendente) · `document_expiry` (avisa vencimentos) · `retention` (limpeza). Resultado em `job_runs` (`GET /v1/admin/jobs`).

## Observabilidade
Logs JSON (`request_id`, sem corpo de requisição) · `/healthz` · `/readyz` (checa banco) · `/metrics` (Prometheus, exige `METRICS_TOKEN`; bloqueado no nginx de referência) · métricas de IA/jobs/HTTP · alertas de exemplo `infra/monitoring/alerts.yml` (**não ativos**). Ausentes: traces distribuídos, error tracking (ex.: Sentry), dashboards.

## Runbooks resumidos
- **Cadeia de hash quebrada** (`/v1/admin/audit/verify` ou `ledger_verify` inválido): isolar, comparar com último backup (`restore_test.sh`), investigar acesso privilegiado ao banco; nunca “consertar” linhas.
- **Webhook falhando**: ver `billing_events`; reenvio pelo Stripe é idempotente.
- **Antivírus indisponível**: documentos ficam `pending_scan` e **não contam** como válidos no match; job reprocessa.
- **Suspeita de vazamento de segredo**: rotacionar `SECRET_KEY` (invalida sessões), `FIELD_ENCRYPTION_KEY` (**exige recriptografar segredos MFA** — planejar), `VOUCHER_HMAC_KEY` (invalida códigos emitidos).
- **Incidente com dados pessoais**: acionar encarregado; avaliar comunicação à ANPD/titulares (art. 48).
- **Restore**: `scripts/restore_test.sh` em banco temporário antes de qualquer restauração real.

## Biblioteca de Soluções (v0.9.0)
Métricas a observar: latência de `/v1/solutions/search` (referência local p95 ≈ 474 ms com 5.000 soluções), taxa de buscas vazias, `unmatched_terms` mais frequentes (manutenção do tesauro), fila de verificação admin, pedidos sem resposta. Jobs de retenção devem limitar `solution_search_log`. Particionar `solution_events`/`solution_search_log` por mês ao crescer. Remover dados DEMO antes de abrir a usuários reais.

## Recuperação: RTO, RPO, PITR e retenção

**Estes números são decisão do operador, não do código.** Nada aqui promete um tempo de recuperação
que a aplicação não controla: RTO e RPO dependem do provedor de PostgreSQL contratado, da janela de
PITR habilitada nele e da frequência com que `scripts/backup.sh` é agendado. O que o repositório
entrega é o procedimento, a verificação e a medição; o compromisso é de quem opera.

### O que está medido (escala de demonstração, nesta rodada)

| Medida | Valor | Condição |
|---|---|---|
| Banco com semente de demonstração | 32 MB | 322 tabelas, 62 migrações |
| Dump `--format=custom` | 2,1 MB | `pg_dump --no-owner --no-privileges` |
| Tempo de backup | **0,5 s** | PostgreSQL 16.15 local, mesmo host |
| Tempo de restauração **com verificação completa** | **5,7 s** | cria banco, `pg_restore`, confere sha256, verifica as cadeias de hash e 15 invariantes de estado |

Escala de demonstração **não é escala de produção**: um banco de 32 GB não restaura em 5,7 s. Estes
valores servem para dizer que o procedimento funciona de ponta a ponta e para dar o ponto de partida
da medição que o operador precisa repetir com volume real antes de assumir qualquer RTO.

### O que o operador precisa decidir e registrar

| Parâmetro | Quem define | Como verificar |
|---|---|---|
| **RPO** (perda máxima aceitável) | Janela de PITR do provedor + frequência de `backup.sh`. Com PITR contínuo, o RPO é de segundos a minutos; com apenas o dump lógico, é o intervalo entre execuções. | `GET /v1/operacoes/health` e `ops_job_runs` dizem quando foi o último backup bem-sucedido. |
| **RTO** (tempo máximo até voltar) | Tamanho do banco, classe da instância e se a recuperação é PITR do provedor (minutos) ou `pg_restore` do dump (proporcional ao volume). | Medir com `scripts/restore_test.sh` contra um dump de produção, em banco descartável. |
| **Janela de PITR** | Configuração do provedor. | Console do provedor; não é observável pela aplicação. |
| **Retenção de backup** | Política do operador. | `DATA_RETENTION.md` (raiz) trata da retenção de DADOS (prazos legais por tabela), que é assunto diferente da retenção de ARQUIVOS DE BACKUP. |

### Procedimento de recuperação

1. **Nunca restaurar direto em produção.** `scripts/restore_test.sh <dump>` restaura num banco
   descartável, confere o sha256, conta as migrações, verifica as quatro cadeias de hash e recusa um
   restore que traga estado que não deveria existir (regra de receita ativa, cartão verde, minuta
   aprovada, cobrança real, denominador sem fonte, selo sem evidência, entre outros). Um restore que
   ligasse receita em silêncio seria pior que um restore que falha.
2. **A verificação de integridade é parte do restore, não um passo opcional.** O script sai com
   código 1 se o sha256 não casar — conferido com dump adulterado em um byte.
3. **Arquivos** (storage): snapshot do volume, ou versionamento do bucket S3. O dump do PostgreSQL
   **não** contém os arquivos do cofre de documentos.
4. **Depois de restaurar**, `/readyz` acusa migração pendente com 503 e nomeia quais faltam.

### A armadilha que este esquema evita de propósito

`FORCE ROW LEVEL SECURITY` aplica a política de RLS ao **dono** da tabela — que é exatamente quem
roda `pg_dump`. Ligar isso em qualquer tabela transformaria o backup num dump vazio que *parece* ter
funcionado, e a descoberta aconteceria no pior momento possível. Nenhuma tabela a tem, e
`test_v0230_data_infra_gate.py::test_force_row_level_security_is_nowhere` recusa que alguém a ligue.
