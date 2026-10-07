# Versionamento

Produto: SemVer (`VERSION` = `0.10.0`; pré-1.0 = sem garantia de compatibilidade). API: prefixo `/v1`. Migrações: sequenciais, só para frente, com checksum
(migração **liberada** nunca é editada — crie a seguinte; `0005_v090_solutions.sql` foi editada em desenvolvimento porque nunca foi aplicada fora do ambiente de construção). Motores: `match-engine@1.0.0`, `fiscal-engine@1.0.0`; pesos `weights@1.0`; planos `plans@1.0`
(gravados em cada `match_run`/regra). Regras fiscais, planos e termos **não são editados**: publica-se nova versão.

**Por que 0.7.0 e não 0.6.1:** o v0.6.0 era uma referência local; o v0.7.0 troca a base de execução (PostgreSQL, auth real, portais). Mudança estrutural → MINOR.
O v0.6.0 **não foi sobrescrito**: está íntegro em `history/v0.6.0/` (com seu `MANIFEST.sha256` original).

Release: `python3 scripts/make_release.py` gera `RELEASE_MANIFEST.sha256` e `FINAL_FULL_RELEASE.zip` (sem ZIP aninhado, sem segredos, sem `node_modules`); `--verify` confere o manifesto.
Histórico: `history/v0.6.0/`, `history/v0.7.0/`, `history/v0.8.0/` (documentos e log de um estado **nunca empacotado**; ver `NOTE.md`) (documentos e log do release anterior, não sobrescritos). Git recomendado: tag assinada `v0.9.0`, Conventional Commits, `main` protegida.

**Por que 0.9.0:** nova capacidade grande (Biblioteca de Soluções, +60 operações, +20 tabelas) sobre o 0.8.0 → MINOR. Motores novos versionados: `intent-parser@1.0.0`, `solution-match@1.0.0`, `adaptation@1.0.0`, `combine@1.0.0`, `replicability@1.0`; pesos em `config/solution_weights.json`.

**Por que 0.10.0:** nova camada funcional (institucional) e mudança de comportamento do match (certificação verificada). `0006_v0100_institutional.sql` ainda não foi aplicada fora de ambientes de desenvolvimento e foi editada durante o desenvolvimento; após esta liberação é imutável (crie `0007`). O v0.9.0 não foi sobrescrito: documentos-chave em `history/v0.9.0/`.
