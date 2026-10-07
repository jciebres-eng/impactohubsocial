# Versionamento

Produto: SemVer (`VERSION` = `0.7.0`; pré-1.0 = sem garantia de compatibilidade). API: prefixo `/v1`. Migrações: sequenciais, só para frente, com checksum
(migração aplicada nunca é editada — crie `0004_…`). Motores: `match-engine@1.0.0`, `fiscal-engine@1.0.0`; pesos `weights@1.0`; planos `plans@1.0`
(gravados em cada `match_run`/regra). Regras fiscais, planos e termos **não são editados**: publica-se nova versão.

**Por que 0.7.0 e não 0.6.1:** o v0.6.0 era uma referência local; o v0.7.0 troca a base de execução (PostgreSQL, auth real, portais). Mudança estrutural → MINOR.
O v0.6.0 **não foi sobrescrito**: está íntegro em `history/v0.6.0/` (com seu `MANIFEST.sha256` original).

Release: `python3 scripts/make_release.py` gera `RELEASE_MANIFEST.sha256` e `FINAL_FULL_RELEASE.zip` (sem ZIP aninhado, sem segredos, sem `node_modules`); `--verify` confere o manifesto.
Git recomendado: tag assinada `v0.7.0`, Conventional Commits, `main` protegida.
