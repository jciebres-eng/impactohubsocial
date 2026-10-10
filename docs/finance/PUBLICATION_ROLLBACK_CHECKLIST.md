# Checklist de publicação e reversão — v0.34.0

## Antes de juntar

- [ ] CI do pull request verde (backend completo, pilha do zero, docker, auditoria, armazenamento).
- [ ] `FINAL_EXECUTION_REPORT.md` §27 com decisão e §24 com o log real.
- [ ] Pacote `IMPACTO_TRUST_FINAL_RELEASE_0.34.0.zip` verificado byte a byte contra o commit; `.sha256` conferido.

## Publicar (mesmo caminho do `CLAUDE.md`)

1. Juntar na `main` → o **demo** publica sozinho e aplica a migração 0073 (só acrescenta; sem dado novo).
2. No demo: percorrer `docs/donations/RUNBOOK.md` §1 e, além disso: declarar um recurso externo, registrar um compromisso,
   abrir **Remuneração da plataforma** (organização), **Remuneração (obrigações)** e **Conciliação** (administração).
3. Produção: "Deploy latest commit" em `impactohubsocial` **e em `pleasing-trust`** — o worker ganhou a rotina `financial_ops`
   (reprocessamento de eventos, vencimento, conciliação periódica, recorrência desligada). Nenhuma variável nova é obrigatória.
4. `pos-deploy`: `/readyz`, commit no ar, `GET /v1/public/donation-campaigns/x` → 404, `GET /v1/org/remuneration` com sessão → 200.

## O que NÃO publicar

- Nenhuma regra ativa; nenhuma carta verde; `LIVE_PAYMENT_PROVIDER_ENABLED` e demais travas em `false` (o serviço recusa subir).
- Nenhum aviso `charging_starts` real: o texto é rascunho até a revisão jurídica.

## Reverter

- Código: voltar ao commit da v0.33.0 mantém o banco compatível — a 0073 só acrescenta colunas com padrão e tabelas novas.
- Dados: não apagar `remuneration_obligations`, `reconciliation_exceptions` nem históricos (trilha). Se for preciso "desligar":
  `DONATIONS_ENABLED=false` (novas doações → 503) e nenhuma rotina de `evaluate`/`invoice` é executada.
- Obrigação criada por engano: `waive` com justificativa (fica no histórico), nunca DELETE.

## Depois de publicar

- Conferir no demo que a página pública mostra "pendente", "confirmado", "liquidado" e "compromissos" separados.
- Conferir no painel de operações (`ops_job_runs`) que `financial_ops` roda a cada ciclo do worker e termina `ok`
  (conciliação periódica e `mark-overdue` agora são automáticos; continuam disponíveis à mão na administração).
