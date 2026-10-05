# Versionamento

Produto: SemVer (`VERSION` = `0.13.0`; pré-1.0 = sem garantia de compatibilidade). API: prefixo `/v1`. Migrações: sequenciais, só para frente, com checksum
(migração **liberada** nunca é editada — crie a seguinte; `0005_v090_solutions.sql` foi editada em desenvolvimento porque nunca foi aplicada fora do ambiente de construção). Motores: `match-engine@1.0.0`, `fiscal-engine@1.0.0`; pesos `weights@1.0`; planos `plans@1.0`
(gravados em cada `match_run`/regra). Regras fiscais, planos e termos **não são editados**: publica-se nova versão.

**Por que 0.7.0 e não 0.6.1:** o v0.6.0 era uma referência local; o v0.7.0 troca a base de execução (PostgreSQL, auth real, portais). Mudança estrutural → MINOR.
O v0.6.0 **não foi sobrescrito**: está íntegro em `history/v0.6.0/` (com seu `MANIFEST.sha256` original).

Release: `python3 scripts/make_release.py` gera `RELEASE_MANIFEST.sha256` e `FINAL_FULL_RELEASE.zip` (sem ZIP aninhado, sem segredos, sem `node_modules`); `--verify` confere o manifesto.
Histórico: `history/v0.6.0/`, `history/v0.7.0/`, `history/v0.8.0/` (documentos e log de um estado **nunca empacotado**; ver `NOTE.md`) (documentos e log do release anterior, não sobrescritos). Git recomendado: tag assinada `v0.9.0`, Conventional Commits, `main` protegida.

**Por que 0.9.0:** nova capacidade grande (Biblioteca de Soluções, +60 operações, +20 tabelas) sobre o 0.8.0 → MINOR. Motores novos versionados: `intent-parser@1.0.0`, `solution-match@1.0.0`, `adaptation@1.0.0`, `combine@1.0.0`, `replicability@1.0`; pesos em `config/solution_weights.json`.

**Por que 0.10.0:** nova camada funcional (institucional) e mudança de comportamento do match (certificação verificada). `0006_v0100_institutional.sql` ainda não foi aplicada fora de ambientes de desenvolvimento e foi editada durante o desenvolvimento; após esta liberação é imutável (crie `0007`). O v0.9.0 não foi sobrescrito: documentos-chave em `history/v0.9.0/`.

**Por que 0.10.1 (PATCH):** fecha pendências do 0.10.0 sem mudar o contrato existente (adições compatíveis: rotas novas, campo `areas`, bloco extra na estimativa fiscal). `0007_v0101_institutional_extras.sql` é nova (a 0006 liberada **não** foi editada). Snapshot do v0.10.0 em `history/v0.10.0/`. A Central de Conhecimento será 0.11.0 (módulo novo ⇒ MINOR).

**Por que 0.11.0 (MINOR):** nova capacidade grande (monetização: trial, tiers, vouchers/convênios, webhooks) com mudança de comportamento (cancelar mantém acesso até o fim do período) e `0008_v0110_monetization.sql` (6 tabelas). Snapshot dos documentos do 0.10.1 em `history/v0.10.1/`; nada foi sobrescrito. Planos: `plans@1.1`.

**v0.12.0** (MINOR): nova capacidade de produto (Central de Conhecimento). Migração `0009` (ainda não liberada → editada em desenvolvimento e banco recriado; a partir da liberação, só migrações novas). Motor novo: `help-search@1.0.0` (gravado nos logs de busca). Snapshot dos documentos do v0.11.0: `history/v0.11.0/`. Configs versionadas: `config/help_synonyms.json`, `config/onboarding_paths.json` (hipóteses editoriais).

**v0.12.1** (PATCH): correções de defeito e endurecimento, sem nova capacidade de produto nem mudança de contrato da API (475 operações, mesmos campos). Migração `0010_v0121_indexes.sql` só adiciona índices — a `0009` já havia sido liberada e **não** foi editada. Snapshot dos documentos do v0.12.0: `history/v0.12.0/`.

**v0.13.0** (MINOR): nova capacidade (camada de integração) com 13 tabelas, 36 rotas e migração `0011_v0130_integration_hub.sql`. A `0010` já estava liberada e **não** foi editada; a `0011` foi editada durante o desenvolvimento (nunca aplicada fora do ambiente de construção) e a partir desta liberação é imutável. Nenhum contrato existente mudou — só adições. Snapshot dos documentos do v0.12.1: `history/v0.12.1/`. A tag `v0.12.1-final-baseline` continua sendo a baseline auditada da camada funcional; o v0.13.0 a estende sem alterá-la.
