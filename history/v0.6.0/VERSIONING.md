# Versionamento e checkpoints

## Esquemas de versão (cada artefato versiona separadamente)
| Artefato | Esquema | Exemplo |
|---|---|---|
| Produto | SemVer `MAJOR.MINOR.PATCH` | `0.1.0` (pré-1.0 = sem garantia de compatibilidade) |
| Pacote de docs | `vX.Y` + checkpoint | `v0.1` |
| API HTTP | prefixo de caminho | `/v1` (breaking → `/v2`) |
| Migrações de banco | sequenciais, só para frente | `0001_init.sql` |
| Match engine | SemVer próprio, gravado em cada `match_run` | `match-engine@0.1.0` |
| Conjunto de critérios | `criteria_version` imutável por programa | `PROG-12/c3` |
| Regras fiscais | pacote imutável `JURISD-ESCOPO-ANO.NN` | `BR-FED-SPORT-2026.01` (exemplo de formato) |
| Planos/direitos | `plan_version` imutável | `plans@2026.01` |
| Termos/Política | data de vigência + hash do texto | `terms@2026-10-04` |

## Regras
- Git: `main` protegida; PR com revisão; tags assinadas `vX.Y.Z`. Commits no padrão Conventional Commits.
- **Checkpoint** = tag `checkpoint/vX.Y-NN` + `CHECKPOINT_vX.Y.md` + zip com `MANIFEST.sha256`. Só se cria checkpoint com `RELEASE_AUDIT.md` atualizado.
- Regras fiscais, critérios, planos e termos **nunca são editados**: publica-se nova versão; a anterior é preservada.
- Mudança que afete cobrança, voucher ou direitos exige entrada em `CHANGELOG.md` e em `DECISIONS.md`.
- Migração destrutiva exige duas fases (expandir → migrar → contrair) e backup verificado.

## Como gerar um novo checkpoint
1. Atualize `CHANGELOG.md`, `CHECKPOINT_*.md`, `RELEASE_AUDIT.md`, `VERSION`.
2. `python3 scripts/make_release.py` (gera `MANIFEST.sha256` e `plataforma-impacto_vX.Y.zip`).
3. Guarde o zip e o hash fora do ambiente de trabalho (cofre/armazenamento da empresa).
