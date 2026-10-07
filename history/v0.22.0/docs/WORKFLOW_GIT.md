# Fluxo de trabalho no Git (a partir de v0.10.0)

Fonte da verdade: `github.com/jciebres-eng/impactohubsocial`. Cada incremento segue:

1. **Savepoint antes de começar:** tag anotada `savepoint/<versão>-<incremento>-pre` na branch de trabalho.
2. **Branch por incremento:** `inc/<n>-<nome>`; commits pequenos com mensagem em português.
3. **Auditoria do incremento:** atualizar `FINAL_RELEASE_AUDIT.md` (nova seção 3-x), `SECURITY_AUDIT.md`, `LGPD_AUDIT.md`, `TEST_REPORT.md` com evidência (log em `docs/evidence/test_run_v<versão>.log`).
4. **Versionamento:** SemVer coerente (`VERSION`, `backend/pyproject.toml`, `web/package.json`), `CHANGELOG.md`, `RELEASE_NOTES.md`, ADR em `DECISIONS.md`; snapshot dos documentos anteriores em `history/v<anterior>/`. Migração liberada nunca é editada: crie a seguinte.
5. **Savepoint depois:** tag `savepoint/<versão>-<incremento>-ok` e tag de release `v<versão>`.
6. **Backup:** o ZIP completo (`python3 scripts/make_release.py`, verificação com `--verify`) é a cópia local; o histórico do Git é o backup remoto.
7. **Entrega:** `FINAL_FULL_RELEASE.zip` com todos os documentos, sem segredos e sem ZIP dentro de ZIP, com `RELEASE_MANIFEST.sha256`.
