# Relatório final de execução — IMPACTO v0.32.0

**Data:** 09/10/2026 · **Ramo:** `correcoes-auditoria` (PR #5 para a `main`) · **Tag:** `v0.32.0` (a criar no GitHub pelo
responsável no commit indicado em §3 — o ambiente das sessões não envia tags) · **Pacote:**
`IMPACTO_TRUST_FINAL_RELEASE_0.32.0.zip` (SHA-256 no `.sha256` ao lado) · **Auditoria:** `FINAL_EXECUTION_AUDIT.md` ·
**Relatório técnico (DOCX):** `IMPACTO_v0.32.0_RELATORIO_TECNICO.docx`

## 1. Executive Summary

Depois da auditoria inicial (`docs/01`–`04`), o responsável decidiu: desativar as contas de demonstração da produção, deixar o
demo aberto a quem tiver o link, tornar o código privado e trazer a branch `infra/v0.31.0` resolvendo os achados. Feito:

- **Produção limpa (na própria produção, com autorização):** 15 contas `@demo.impacto.local` desativadas — as sessões abertas
  caíram na hora —, 5 organizações fictícias suspensas, 11 itens públicos fictícios fora do ar (1 projeto, 7 soluções,
  1 material, 2 editais). Nada apagado; reversível; tudo na trilha de auditoria.
- **Backup que restaura:** o backup cifrado do R2 foi baixado, conferido, decifrado e restaurado num banco descartável com os
  verificadores de integridade; o ensaio passa a rodar todo dia 1º; as instruções de restauração (que falhariam) foram corrigidas.
- **Worker com menor privilégio:** início próprio (`start_worker.sh`) que usa o usuário limitado do banco — falta trocar o
  comando no Railway.
- **Demo com aviso** em toda tela; **CI de volta ao verde**; rotinas do GitHub ajustadas para o repositório privado.
- Junta v0.30.1 (proteção 0071, backup diário, monitor — feitos em outra conversa e agora registrados no CHANGELOG), v0.31.0
  (infraestrutura) e a auditoria inicial.

**Decisão: GO WITH CONDITIONS** (§27) — para juntar na `main` e publicar a produção; as condições são cliques e decisões do
responsável, não defeitos.

## 2. Version

0.32.0 — `VERSION`, `backend/pyproject.toml`, `web/package.json`, `web/package-lock.json`, `README.md`, `docs/openapi.json`.
Documentos da v0.31.0 preservados em `history/v0.31.0/`; manifestos anteriores em `history/manifests/`.

## 3. Commit

Ramo `correcoes-auditoria` sobre `906d383` (main) + `auditoria-inicial` + merge da `infra/v0.31.0` (`dc03db1`). Commits: contas de
demonstração (script, modos do workflow, testes), CI (RLS, matriz), backup (ensaio e instruções), faixa do demo, rotinas para
repositório privado, versão e documentos, e o commit final dos manifestos, para o qual a tag `v0.32.0` deve apontar e do qual o
pacote é construído byte a byte (`verify_package_against_git.py`). PR #5. Execuções na produção: 37996712177, 37997211737,
37997481695 (contas e conteúdo), 37997867650 (ensaio de restauração).

**CI do commit candidato à tag `8aec7d1` (execução 38002549412, no PR #5): `backend` (suíte completa), `pilha-do-zero`, `docker`,
`auditoria` e `armazenamento` — os cinco verdes.** Pacote `IMPACTO_TRUST_FINAL_RELEASE_0.32.0.zip`, SHA-256
`add013b96658348eff823e45108f4c39133667572fdf72461a64320eec9d866b`, byte a byte o commit `8aec7d1`. Este parágrafo foi
acrescentado depois da execução, no commit seguinte; a tag `v0.32.0` aponta para `8aec7d1`.

## 4. Architecture Status

Inalterada no produto. Operação documentada no `CLAUDE.md`: Railway (`impactohubsocial`, `pleasing-trust`, `clamav`; demo
`ideal-delight`), Supabase só como PostgreSQL, R2 para arquivos e backups, Cloudflare, Brevo.

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

PASS (inalterado).

## 11. Responsibility

PARTIAL (inalterado).

## 12. Reputation

PASS (inalterado).

## 13. Seals

PASS (inalterado).

## 14. Government Data

Inalterado.

## 15. Marketplace

Inalterado (comissão recusada). Soluções fictícias fora do ar na produção.

## 16. Payments

Inalterado: nenhum pagamento real; nenhum provedor ligado.

## 17. Distribution

PASS (inalterado).

## 18. Billing

Inalterado: sem assinatura (ADR-341); 0 regras ativas.

## 19. Fiscal

BLOCKED_EXTERNAL (inalterado).

## 20. Vouchers

Inalterado.

## 21. Identity

PARTIAL (inalterado). Contas de demonstração da produção desativadas pelo mesmo caminho da tela de administração.

## 22. Security

Nenhum segredo em código, workflow, documento ou pacote (`secrets_scan.py`, gitleaks no CI). Contas com senha conhecida (as de
demonstração) sem acesso à produção. Backup e ensaio sem artefato publicado. Pendentes do responsável: trocar o token do backup
exposto num chat; publicar a produção (aplica a 0071); trocar o comando do worker; tornar o repositório privado. **Nenhum sistema
ligado à internet é "impossível de invadir", e este não é exceção.**

## 23. LGPD

Produção sem contas fictícias ativas e sem conteúdo fictício público; o backup tem dado pessoal e por isso é cifrado e nunca vira
artefato. Revisão jurídica dos termos e da política e encarregado de dados continuam pendentes (bloqueiam dados reais).

## 24. Tests

```text
REGRESSÃO COMPLETA LOCAL (docs/evidence/test_run_v0.32.0.log):
  Ran 2434 tests in 1945.779s — 5 falhas, 0 erro, 31 pulados (dependem de credencial ou do servidor S3 do CI)
  → mapa tela × API (regenerado), manifesto e 3 verificações deste relatório (completados no fechamento)
CI DO PR #5 (execução 37998628082): Ran 2434 tests in 1797.986s — as mesmas falhas de fechamento + a auditoria ainda da v0.31.0
MÓDULOS NOVOS: test_v0320_demo_accounts (2) · test_v0320_release_docs (5)
PROVAS NA PRODUÇÃO: contas/conteúdo (37996712177, 37997211737, 37997481695) · ensaio de restauração (37997867650)
LINT: ruff 0 · TYPECHECK: tsc --noEmit 0 erros · BUILD: esbuild ok · IMAGEM: job docker verde
```

Portões de fechamento reexecutados após gerar os manifestos (fim do mesmo log). Nenhum teste removido ou enfraquecido; a
exceção de RLS mudou com o motivo escrito ao lado (a 0071 protegeu a tabela).

## 25. External Dependencies

| Dependência | Exige | Efeito hoje |
|---|---|---|
| Publicar a produção ("Deploy latest commit" no `impactohubsocial` e no `pleasing-trust`) | responsável | 0071 e worker novo fora da produção |
| Start Command do `pleasing-trust` = `sh /app/start_worker.sh` | responsável | worker com conexão administrativa |
| Token novo do backup (o antigo foi exposto num chat) | responsável (Cloudflare + GitHub) | risco sobre os backups |
| Repositório privado | responsável (Settings) | código público |
| Monitor externo (UptimeRobot/Better Stack) | responsável | só o monitor horário do GitHub |
| Senha de `impacto_app` igual no GitHub | responsável | modo `aplicar` do workflow recusaria |
| Domínio, e-mail autenticado, revisão jurídica, encarregado de dados | responsável e terceiros | sem domínio próprio; sem dados reais |
| Tags v0.31.0 e v0.32.0 | o ambiente não envia tags | criar no GitHub |

## 26. Known Limitations

- Conteúdo de nível "rede" (visível só a membros logados) das organizações fictícias não foi alterado — o cadastro em produção
  está bloqueado pela trava jurídica, então não há membros externos para vê-lo.
- O plano do GitHub da conta não foi verificado (cota de minutos estimada pelo plano gratuito).
- O monitor agendado do GitHub não disparou nas primeiras horas; por isso o externo é o principal.
- RPO do banco depende do plano do Supabase e não foi conferido no painel.

## 27. GO / GO WITH CONDITIONS / NO-GO

```text
GO WITH CONDITIONS
```

Para juntar o PR #5 na `main` (o demo publica sozinho) e, depois de conferido o demo, publicar a produção. Os críticos internos
da auditoria inicial estão resolvidos com prova na própria produção (contas e conteúdo fictícios; restauração do backup real).
Condições: trocar o comando do worker na mesma publicação; trocar o token do backup; tornar o repositório privado; monitor
externo. Dados reais continuam bloqueados até a revisão jurídica. Nenhuma falha crítica foi convertida em "condição".

## 28. Exact Next Step

1. Juntar o PR #5 (eu faço com o seu "pode juntar", ou você clica em "Merge").
2. Abrir o demo e conferir a faixa "Ambiente de demonstração" e o login.
3. Railway → produção → `impactohubsocial` → Ctrl+K → "Deploy latest commit"; no `pleasing-trust`, trocar o Start Command para
   `sh /app/start_worker.sh` e publicar. Depois eu rodo o diagnóstico ("0 pendentes") e confiro os logs do worker.
4. Trocar o token do backup; tornar o repositório privado; criar o monitor externo.
