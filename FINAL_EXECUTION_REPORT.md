# Relatório final de execução — IMPACTO v0.31.0

**Data:** 09/10/2026 · **Ramo:** `infra/v0.31.0` · **Tag:** `v0.31.0` (a criar no GitHub pelo proprietário no commit indicado em §3 —
o proxy deste ambiente recusa envio de tag) · **Pacote:** `IMPACTO_TRUST_FINAL_RELEASE_0.31.0.zip` (SHA-256 no `.sha256` ao lado) ·
**Auditoria:** `FINAL_EXECUTION_AUDIT.md` · **Relatório técnico (DOCX):** `IMPACTO_v0.31.0_RELATORIO_TECNICO.docx`

## 1. Executive Summary

A rodada executou o pacote de infraestrutura (Railway Pro + Supabase Pro + Cloudflare R2 + Cloudflare Pro + GitHub) do jeito que
ele manda: **auditoria read-only primeiro**, prova de tudo o que dava para provar sem as contas do proprietário, correções seguras
com teste, e **nenhuma** publicação, migração em produção, mudança de DNS, troca de senha ou cobrança.

- **Identidade:** a "baseline 0.29.01" do pacote é, byte a byte, a tag v0.29.0 (`dd2f8c3`); o repositório está à frente
  (`docs/release/REPO_BASELINE_DIFF.md`). Nada dela foi copiado — regrediria o código.
- **Supabase comprovado por leitura:** PostgreSQL 17.11, `impacto_app` sem superusuário e sem bypass de RLS, 71 migrações em dia,
  cadeia de auditoria válida. Achados: **15 contas de demonstração e 1 real no mesmo projeto** (P0: separar staging e produção);
  o lote 0064–0070 foi aplicado em 09/10 18:24 UTC **fora** do GitHub, junto com a troca da senha de `impacto_app` — o padrão do
  entrypoint do contêiner (hipótese: primeira implantação do Railway), a confirmar com o proprietário.
- **Backup com restauração real** (o pacote declara NO-GO sem isso): dump do Supabase restaurado num PostgreSQL 17 descartável com
  os verificadores de integridade do CI — **341 tabelas, 2.577 linhas idênticas, RTO medido 15,1 s**, nada exportado.
- **Correções no código:** serviço `worker` próprio (`start_worker.sh`: não migra, espera o esquema, roda como `impacto_app`);
  validação do R2 (região `auto`); disco local efêmero sinalizado em `/readyz` e no log; commit implantado em `/healthz`;
  adaptador S3 provado contra servidor S3 real no CI; `deploy.yml` (modelo com `echo`) substituído por `pos-deploy` (só verifica);
  workflows `armazenamento` (bucket R2 real) e `backup-restaurar`.
- **Sem `railway.json`, de propósito:** o Config as Code do Railway está descontinuado (corte em 2026-12-01).
- **Não comprovado (sem acesso):** Railway, R2, ClamAV, SMTP, Cloudflare. Tudo com passo exato em
  `docs/ops/CHECKLIST_PROPRIETARIO_v0310.md`.

**Decisão: NO-GO para produção hoje** (§27) — dois P0 abertos que dependem do proprietário. Staging pode ser montado já.

## 2. Version

0.31.0 — `VERSION`, `backend/pyproject.toml`, `web/package.json`, `web/package-lock.json`, `README.md`, `docs/openapi.json`.
Documentos da v0.30.0 preservados em `history/v0.30.0/` (166 arquivos); manifestos anteriores em `history/manifests/`.

## 3. Commit

Commits da rodada (sobre `171d8b4`), no ramo `infra/v0.31.0`: diagnóstico estendido do Supabase; backup e restauração de banco
gerenciado; worker, R2, `/healthz`/`/readyz`, workflows; correções do job `armazenamento`; versão/ADRs/documentos; e o commit final
dos manifestos, para o qual a tag `v0.31.0` deve apontar e do qual o pacote é construído byte a byte (`verify_package_against_git.py`).
O hash desse commit é registrado no `.sha256` do pacote. A junção no `main` **não foi feita**: o Railway publica o `main`, e publicar
depende da aprovação do proprietário.

**GitHub Actions (ramo):** `supabase` (37974779816, 37975067994: verificar; 37975650545: backup-restaurar), `ci` (37977204420:
auditoria, docker, pilha-do-zero verdes; backend 2.414 testes com 3 falhas de fechamento/segredo já corrigidas; 37978728985:
armazenamento verde contra CloudServer).

## 4. Architecture Status

Inalterada no produto (Starlette + PostgreSQL com RLS em toda tabela, hash encadeado, sem custódia). Topologia de publicação
documentada: Railway com `api` (entrypoint que migra com lock e troca para `impacto_app`), `worker` (novo entrypoint) e `clamav`;
Supabase só como PostgreSQL (nenhum uso de Auth/Storage/Realtime/Functions); R2 como armazenamento S3 privado com URL assinada;
Cloudflare como DNS/TLS/WAF. Documento canônico: `docs/ops/INFRA_RAILWAY_SUPABASE_R2_v0310.md`.

## 5. Engines Status

50 motores, inalterados; `MOTOR_COVERAGE_MATRIX.md` VERDE 37 · AMARELO 13 · VERMELHO 0.

## 6. Contract Intelligence

PASS (inalterado).

## 7. Match

PASS (inalterado); sem pay-to-rank.

## 8. Diagnostic

PASS (inalterado).

## 9. Equity

PASS (inalterado).

## 10. Evidence

PASS (inalterado desde a v0.30.0). Armazenamento dos arquivos de evidência: alvo R2 privado; não comprovado no bucket real.

## 11. Responsibility

PARTIAL (inalterado).

## 12. Reputation

PASS (inalterado).

## 13. Seals

PASS (inalterado).

## 14. Government Data

Inalterado.

## 15. Marketplace

Inalterado (comissão recusada).

## 16. Payments

Inalterado: nenhum pagamento real; nenhum provedor ligado.

## 17. Distribution

PASS (inalterado).

## 18. Billing

Inalterado: sem assinatura (ADR-341); 0 regras ativas. A análise econômica de 120 meses (`docs/analysis/economia_v0300/`) é
proposta e não alterou regra, catálogo, planos ou banco.

## 19. Fiscal

BLOCKED_EXTERNAL (inalterado).

## 20. Vouchers

Inalterado.

## 21. Identity

PARTIAL (inalterado).

## 22. Security

Revisada para o ambiente hospedado: nenhum segredo em código, workflow, documento ou pacote (`secrets_scan.py`, gitleaks no CI);
dump com dado pessoal nunca sai do job; restauração recusa destino igual à origem; worker com menor privilégio e sem rotação de
senha; `impacto_app` sem superusuário e sem bypass de RLS no Supabase (lido); contas de demonstração no banco que tem dado real
registradas como P0. **Nenhum sistema ligado à internet é "impossível de invadir", e este não é exceção.**

## 23. LGPD

O backup restaurado não gera artefato; o diagnóstico conta usuários sem ler conteúdo; nenhum endereço, IP ou consulta é impresso.
Retenção LGPD só roda com o `worker` no ar (antes desta rodada nenhum serviço a executaria no Railway). DPO continua pendente.

## 24. Tests

```text
PRIMEIRA REGRESSÃO COMPLETA LOCAL (código novo, antes do fechamento, scratchpad/full_v0310_a.log):
  Ran 2425 tests in 1874.719s — 6 falhas, 0 erro, 31 pulados
  → 1 real (web/package.json e package-lock em 0.30.0 — corrigido) e 5 de fechamento (manifesto e documentos finais gerados no
    fechamento); causas e correções em FINAL_EXECUTION_AUDIT.md §7
CI DO RAMO (run 37977204420): Ran 2414 tests in 1651.243s — 3 falhas (2 do manifesto, 1 da varredura de segredo — corrigida)
SEGUNDA REGRESSÃO COMPLETA LOCAL: ver docs/evidence/test_run_v0.31.0.log
MÓDULOS NOVOS: test_v0310_storage (8, 1 deles de protocolo S3 que roda no CI) · test_v0310_release_docs (11) ·
               test_v0300_economic_analysis (6)
PROVAS FORA DA SUÍTE: backup+restauração do Supabase (run 37975650545) · adaptador S3 × CloudServer (job armazenamento)
LINT: ruff 0 · IMAGEM: job docker verde
```

Nenhum teste foi removido ou enfraquecido; nenhuma contagem fixada mudou (940 operações, 227 telas, 70 migrações, 50 motores).

## 25. External Dependencies

| Dependência | Exige | Efeito hoje |
|---|---|---|
| Separar staging × produção no Supabase (G1) | decisão do proprietário | produção bloqueada |
| URL e configuração do Railway (G2) | proprietário (`railway config pull`) | Railway não comprovado |
| Senha de `impacto_app` igual no Railway e no GitHub | proprietário | modo `aplicar` do workflow recusaria/derrubaria |
| Buckets e tokens R2 | conta Cloudflare | armazenamento em disco efêmero ou indefinido |
| Serviço ClamAV | Railway | uploads em quarentena |
| Provedor SMTP + SPF/DKIM/DMARC | proprietário | sem e-mail transacional |
| Domínio e Cloudflare | proprietário | sem domínio próprio |
| Tag `v0.31.0` e junção no `main` | proxy recusa tag; junção publica no Railway | aguardam o proprietário |

## 26. Known Limitations

- Railway, R2, ClamAV, SMTP e Cloudflare não foram tocados nem verificados por dentro.
- O servidor S3 de teste do CI não é o R2: `response-content-disposition` e *path-style* no R2 só o workflow `armazenamento` prova.
- RTO medido é do volume atual (2,3 MB); RPO não definido (depende do plano do Supabase).
- O backup gerenciado do Supabase não foi conferido (só pelo painel).
- Credencial administrativa no ambiente da `api` (o entrypoint migra com ela) — P2.
- Ações do GitHub em Node 20 (aviso de descontinuação) — P2.

## 27. GO / GO WITH CONDITIONS / NO-GO

```text
NO-GO
```

**Para publicação em produção hoje.** Dois P0 dependem do proprietário: (G1) o único projeto Supabase mistura 15 contas de
demonstração com 1 conta real — produção precisa de um projeto próprio ou das contas de demonstração desativadas; (G2) o Railway não
foi verificado — não se sabe com que ambiente, armazenamento e e-mail a instância de 09/10 subiu. O critério do pacote ("backup sem
restauração testada resulta em NO-GO") **está satisfeito**: a restauração foi feita e conferida. Nenhuma falha técnica interna fica
aberta. **Staging pode ser montado agora** com `docs/ops/CHECKLIST_PROPRIETARIO_v0310.md`; com G1 e G2 resolvidos e o `pos-deploy`
verde em produção, a decisão passa a GO WITH CONDITIONS (condições: SMTP, R2 e domínio verificados). Rollback:
`docs/ops/ROLLBACK_v0310.md`; backup: `docs/ops/BACKUP_RESTORE_RUNBOOK.md`.

## 28. Exact Next Step

1. Responder: foi você que ligou o Railway por volta de 14:20 de 09/10? E enviar a URL pública (e, se puder, a saída de
   `railway config pull`).
2. Decidir G1: este projeto Supabase vira **staging** e cria-se um projeto de **produção** (recomendado).
3. Igualar `IMPACTO_APP_PASSWORD` no GitHub ao valor do Railway; `IMPACTO_APP_ROTATE_PASSWORD=false`.
4. Autorizar a junção de `infra/v0.31.0` no `main` (o Railway publica o `main`) e criar a tag `v0.31.0` no commit de fechamento.
5. Criar os serviços `worker` e `clamav`, os buckets R2 e rodar `armazenamento` e `pos-deploy`.
