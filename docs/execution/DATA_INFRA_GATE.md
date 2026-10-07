# GATE 6 — DADOS E INFRAESTRUTURA · EVIDÊNCIA DE EXECUÇÃO

Tudo abaixo foi **executado nesta rodada** contra PostgreSQL 16.15 real, num banco criado do zero
para esta verificação (`impacto_g6`) e descartado depois. Nenhum número vem de documentação: cada um
foi consultado no banco.

**Testes automatizados:** 38 (16 novos em `test_v0230_data_infra_gate.py` + 22 em
`test_v0230_observability_gate.py`), todos verdes.

---

## 1. Migração do zero · **PASS**

Banco novo, `python3 -m impacto.db.migrate`:

| Medida | Valor |
|---|---|
| Migrações aplicadas | **62** (0001 → 0062, sem buraco na sequência, sem duplicata) |
| Tabelas criadas | **322** |
| Tabelas com RLS | **321** |
| Tabelas sem RLS | **1** — `schema_migrations`, e o motivo é escrito: é lida pelo `/readyz` e pelo migrador antes de existir qualquer sessão de organização |
| Políticas RLS | **667** |
| Tabelas com `FORCE ROW LEVEL SECURITY` | **0** |
| Dados de referência sincronizados | 12 planos, 8 versões de preço, 9 provedores de integração, 909 traduções |

Cada migração aplicada tem o **sha256 do arquivo** registrado em `schema_migrations.checksum`, e um
teste confere arquivo por arquivo: uma migração que mude de conteúdo **depois** de aplicada reprova.

## 2. Migração incremental · **PASS**

Reexecução no mesmo banco: nenhuma migração nova, 62 antes e 62 depois, 0 versões de preço novas.
Idempotente.

## 3. Semente · **PASS**

`python3 -m impacto.cli seed-demo`: 14 usuários de demonstração criados (OSC, empresa, profissional,
governo, admin, editor, revisor, suporte, controladoria, financeiro, contabilidade, tesouraria,
operações, auditoria). Senha vem de `DEMO_PASSWORD`, **nunca** versionada.

## 4. Backup · **PASS**

`scripts/backup.sh`: `pg_dump --format=custom --no-owner --no-privileges` + `sha256sum`.

| Medida | Valor |
|---|---|
| Banco com semente | 32 MB |
| Dump | 2,1 MB |
| Tempo | **515 ms** |

## 5. Restauração em ambiente limpo · **PASS**

`scripts/restore_test.sh` cria um banco **descartável**, nunca toca o original:

```
sha256: OK
62 migrations
ledger e auditoria íntegros
camada econômica restaurada DESLIGADA: nenhuma receita ativa, nenhum cartão verde,
                                      nenhuma minuta aprovada, nenhuma cobrança real
camada de impacto restaurada ÍNTEGRA: nenhum denominador sem fonte, nenhum selo sem
                                      evidência ou de rascunho, nenhuma linha de base
                                      sem fonte, nenhuma reputação sem observação
camada de operação restaurada ÍNTEGRA: 23 namespaces de glossário, registro de tarefa
                                      e de e-mail presentes, nenhum endereço guardado
restore OK
```

Tempo de restauração **com a verificação completa**: **5,68 s**. Nenhum banco de restauração ficou
para trás (`impacto_restore_%`: 0).

Um restore que ligasse receita, aprovasse uma minuta ou concedesse um selo em silêncio seria **pior**
que um restore que falha — a restauração é justamente o momento em que ninguém olha. Por isso o
script confere 15 invariantes de estado, não só a integridade estrutural.

### Controle negativo do backup · **PASS**

Dump adulterado em **um byte** (posição 900.000): `sha256sum -c` acusa `FAILED`, o script sai com
**código 1**, e nenhum banco é criado. Um backup cuja verificação não falha não é um backup
verificado.

## 6. Integridade pós-restauração · **PASS**

`scripts/db_integrity_report.py` no banco construído do zero:

| Medida | Valor |
|---|---|
| Restrições `CHECK` | 1.550 |
| Restrições `UNIQUE` | 426 |
| Índices | 926 |
| Tabelas sem chave primária | **nenhuma** |
| Tabelas *append-only* (recusam UPDATE/DELETE) | **43** |
| Tabelas protegidas contra `TRUNCATE` | **6** |
| Tabelas com colunas guardadas (`guard_columns`) | 30 |
| Linhas órfãs | **nenhuma** |
| Deriva do catálogo polimórfico | **nenhuma** (26 colunas catalogadas) |
| Tipos de referência não resolvidos | **nenhum** |
| Medições validadas **sem** evidência | **0** (tem de ser 0) |

`forbid_mutation` é gatilho de **linha** e não vê `TRUNCATE`; por isso existe o par
`forbid_truncate` nas 6 tabelas onde apagar tudo com um comando seria o ataque óbvio.

### As quatro cadeias de hash · **PASS**

`audit_verify`, `ledger_verify`, `value_verify` e `trust_verify` existem e verificam. Nenhuma
organização com cadeia de auditoria quebrada; nenhum projeto com ledger quebrado.

### Provedores de assinatura — a regra permanente, conferida

| Provedor | Nível legal | Estado | Certificado |
|---|---|---|---|
| `platform_advanced` | advanced | **production** | **não** |
| `icp_brasil` | qualified | **unavailable** | sim |
| `govbr` | advanced | **unavailable** | sim |

O único provedor em produção é a assinatura **avançada própria da plataforma** (reautenticação por
senha + código de uso único amarrado ao hash do conteúdo), que declara `supports_certificate = false`
e nível `advanced`. **ICP-Brasil (qualificada) e gov.br estão `unavailable`** — nada é simulado,
exatamente como a regra permanente exige.

## 7. RTO / RPO / PITR / retenção · **PASS (documentado)**

Documentado em `docs/OPERATIONS.md` → *Recuperação: RTO, RPO, PITR e retenção*.

**Nenhum número de RTO ou RPO é prometido aqui**, e isso é deliberado: ambos dependem do provedor de
PostgreSQL contratado, da janela de PITR habilitada nele e da frequência de agendamento de
`backup.sh` — nada disso é controlado pelo código. O documento entrega o procedimento, a tabela de
parâmetros que o operador precisa decidir, como verificar cada um, e as medições reais de referência
(em escala de demonstração, dito como tal: um banco de 32 GB não restaura em 5,7 s).

## 8. Observabilidade · **PASS**

| Medida | Valor |
|---|---|
| Testes do portão de observabilidade | **22**, verdes |
| Regras de alerta declaradas (`infra/monitoring/alerts.yml`) | **16**, em 3 grupos |

Os alertas cobrem erro e latência de API, API fora, falha de IA, reúso de token de renovação, pico de
login falho, entrada privilegiada recusada em série, sessões expirando em massa, MFA desligado em
série, papel interno concedido, **interruptor de emergência acionado**, operações recusadas pelo
interruptor, **backup falhou**, **backup sem sucesso há tempo demais**, tarefa operacional falhando e
tarefa presa em execução.

"Quando foi o último backup bem-sucedido?" é respondível por `ops_job_runs` e por
`GET /v1/operacoes/health` — a pergunta que mais importa depois de um incidente é a que o sistema
precisa saber responder **durante** o incidente.

## 9. Prontidão e vivacidade · **PASS** · *era o item sem teste*

`/readyz` tinha **um** teste: o do caminho feliz. O ramo que decide se a plataforma sobrevive a um
incidente é o outro — o **503**. Uma sonda de prontidão que nunca devolve 503 é pior que nenhuma: o
orquestrador acha que a instância está boa, manda tráfego, e cada requisição morre no banco.

Agora os dois motivos de 503 que o produto declara são exercitados:

| Cenário | Resultado |
|---|---|
| Migração pendente (código espera o que o banco não tem) | **503**, `pending_migrations` nomeia quais |
| Banco inalcançável | **503**, `database: "down"` |
| Prontidão caída, vivacidade consultada | `/healthz` segue **200** |
| `/healthz` toca o banco? | **não** — conferido estruturalmente |

A separação não é formalidade. Reiniciar o processo não ressuscita o banco: prontidão **tira do
balanceador**, vivacidade **reinicia**. Confundir as duas transforma uma queda de banco numa
tempestade de reinícios, trocando instâncias ruins por instâncias ruins, mais devagar.

## 10. Migração destrutiva · **PASS** · *uma remoção real, declarada*

Avanço-somente não é só a ordem dos arquivos: é não destruir dado em silêncio. A varredura encontrou
**uma** remoção em 62 migrações: `DROP TABLE sdg_goals` em `0013_v0150_core_product.sql`. Ela é
legítima e agora está **declarada com motivo** em
`test_v0230_data_infra_gate.py::REMOCOES_DECLARADAS`: as linhas 15-16 da mesma migração copiam
`code`, `name_en` e `color_hex` para `ods_goals` **antes** da remoção, e o gatilho de validação de
`impact_tags` é recriado apontando para a tabela nova. Nenhum dado se perde.

A lista é a trava: uma remoção **nova** reprova até que alguém a inscreva deliberadamente, o que
obriga a pensar em migração de dado em vez de descobrir a perda em produção. E um segundo teste
impede a lista de envelhecer — uma entrada que não corresponda a nenhuma migração real reprova,
porque exceção obsoleta faz a próxima pessoa confiar numa trava que não trava nada.
