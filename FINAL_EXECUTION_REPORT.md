# Relatório final de execução — IMPACTO v0.35.0

**Data:** 10/10/2026 · **Ramo:** `seguranca-v0350` (PR #8, sobre `ecossistema-v0340` / PR #7; PRs #5, #6 e #7 abertos, nenhum juntado) · **Tag:** `v0.35.0`
(a criar no GitHub pelo responsável no commit indicado em §3 — o ambiente das sessões não envia tags) · **Pacote:**
`IMPACTO_TRUST_FINAL_RELEASE_0.35.0.zip` (SHA-256 no `.sha256` ao lado) · **Auditoria:** `FINAL_EXECUTION_AUDIT.md` ·
**Relatório técnico (DOCX):** `IMPACTO_v0.35.0_RELATORIO_TECNICO.docx` · **Documentos de segurança:** `docs/security/`

## 1. Executive Summary

O pacote IMPACTO MASTER Security & Financial Integrity 1.0.0 pediu duas fases: **auditoria somente leitura** (fase 1) e,
com autorização, **correções** (fase 2). A fase 1 (`docs/security/AUDITORIA_SEGURANCA_FASE1.md`) provou três falhas no código
e listou os controles por domínio. O responsável autorizou em 10/10/2026 "Sim, lotes A a I" numa branch própria, sem publicar,
e — das ações extras — **só** a nova cifra do backup. Entregue nesta versão (detalhe controle por controle em
`docs/security/RELATORIO_CORRECOES_FASE2.md`):

- **As três falhas provadas estão fechadas:** o financiador não vê mais documentos internos da OSC na diligência (FILE-07); só a
  dona autoriza atos comerciais (AUTHZ-02); a conciliação passou a comparar com fonte declarada e o extrato manual só concilia
  depois da aprovação de outra pessoa (PAY-07).
- **Dois achados novos, provados no código anterior e corrigidos:** um evento de pagamento sem assinatura enviado antes do
  verdadeiro ocupava o identificador e a doação nunca confirmava (PAY-13); uma tabela temporária criada pela conexão da
  aplicação fazia a função de nível de identidade responder "biometria" (DB-03).
- **Dinheiro e identidade com quatro olhos:** confirmação do beneficiário, aprovação de extrato manual, liquidar/estornar/decidir
  obrigações de remuneração, recurso de caso de risco e restrição de organização exigem uma segunda pessoa.
- **Equipe:** escrita administrativa pede identidade confirmada há menos de 15 minutos; MFA obrigatório e não desligável;
  ativação do MFA com código do aplicativo e do e-mail; avisos ao titular; trilha de falhas de segundo fator.
- **Webhooks** com carimbo de tempo (300 s), segredos próprios e mínimos; **sandbox nunca em produção**; **chave PIX de repasse**
  travada depois da primeira assinatura, com carência de 24 h e aviso a todas as partes.
- **Banco:** `search_path` seguro em toda função privilegiada, EXECUTE só para a aplicação, visão com RLS, TRUNCATE travado em
  toda tabela só-inclusão. **Arquivos, web, IA, antifraude, cadeia de entrega, backup com cifra autenticada e 7 runbooks.**
- 91 testes novos; para cada lote, os testes novos foram rodados no código anterior e **falharam** (saídas em
  `docs/security/evidencias/`). No fechamento, o CI do PR achou um seletor sem nome acessível numa tela nova; corrigido com
  teste que falha no front anterior (§24).

**Decisão: GO WITH CONDITIONS** (§27) para juntar e publicar no demo; a produção depende das variáveis do checklist e das
pendências P0 que só o responsável executa. **Isto não é certificação nem teste de intrusão.**

## 2. Version

0.35.0 — `VERSION`, `backend/pyproject.toml`, `web/package.json`, `web/package-lock.json`, `README.md`, `docs/openapi.json`.
Documentos da v0.34.0 preservados em `history/v0.34.0/`; manifestos anteriores em `history/manifests/`.

## 3. Commit

Ramo `seguranca-v0350` sobre `16d837b` (v0.34.0). Um commit por lote: A `2b44b58`, B `82ed19e`, C `4f8bcf6`, D `a8ba87e`,
E `b587bf3`, F `54e06dd`, G `2e41dd9`, H `3eecfea`, I `14b758b`; fechamento `e9a892d`; ensaio local da pilha e teste antigo de
pagamentos alinhado `fd1c86c`; correção de acessibilidade achada pelo CI, evidências regeneradas pela regressão e documentos de
fechamento; e o commit final dos manifestos, para o qual a tag `v0.35.0` deve apontar e do qual o pacote é construído byte a
byte (`verify_package_against_git.py`). Nenhuma operação na produção. O CI do pull request é a evidência externa
(`FINAL_EXECUTION_AUDIT.md` §6).

## 4. Architecture Status

Sem módulo novo de domínio: as correções entram nos serviços existentes (`donations.py`, `payments.py`, `trust/economy.py`,
`trust/identity.py`, `risk.py`, `documents.py`, `observability.py`, `http_client.py`, `ai/gateway.py`) e numa migração só
(`0074_v0350_security.sql`). Novos: `require_fresh_identity` e `parse_json_body` em `http.py`; `scripts/backup_crypt.py`;
`config/donation_risk_rules.json` passou a ser a fonte dos limiares. Operação inalterada (`CLAUDE.md`).

## 5. Engines Status

50 motores, inalterados; `MOTOR_COVERAGE_MATRIX.md` VERDE 37 · AMARELO 13 · VERMELHO 0.

## 6. Contract Intelligence

PASS. A chave PIX de repasse de uma parte fica travada depois da primeira assinatura do acordo (serviço + gatilho no banco,
`pix_locked_after_signature`); mudar só por nova versão do acordo. Chave informada depois de assinatura: carência de 24 h, com
aviso às demais partes.

## 7. Match

PASS (inalterado); sem pay-to-rank.

## 8. Diagnostic

PASS (inalterado).

## 9. Equity

PASS (inalterado). Sinais de risco são itens para revisão humana; nenhum bloqueio automático por pontuação.

## 10. Evidence

PASS. Diligência de financiador vê só documentos institucionais (lista fechada) ou os compartilhados com as partes; nunca
exportação, documento de dirigente ou de identidade; o acesso termina com a candidatura (`app_document_access`).

## 11. Responsibility

PARTIAL (inalterado).

## 12. Reputation

PASS (inalterado).

## 13. Seals

PASS (inalterado).

## 14. Government Data

Inalterado.

## 15. Marketplace

Inalterado. Atos comerciais da organização exigem o papel de dona (`min_role="owner"`), com varredura que obriga toda rota de
escrita da organização a declarar papel mínimo.

## 16. Payments

Sandbox apenas — e agora **recusado em produção** (`PAYMENT_SANDBOX_ENABLED=true` impede a subida). Assinatura
`t=…,v1=HMAC(t.corpo)` com janela de 300 s nos dois webhooks; segredo próprio para doações (`DONATION_WEBHOOK_SECRET`), mínimo de
32 caracteres, sem segredo de reserva. Evento não assinado guardado sob identificador próprio (PAY-13). Mesma chave de
idempotência com outro valor → 409. Evento antes da confirmação fica adiado e é reaplicado; desiste após 10 tentativas (fila de
exceções). "Permitir" após revisão confirma pelo caminho normal. Conciliação com fonte declarada; extrato manual com aprovação de
outra pessoa (hash do extrato conferido). Origem pública da campanha prevalece sobre o que o doador declara.

## 17. Distribution

PASS (inalterado).

## 18. Billing

Sem assinatura de plano (ADR-341). Obrigações de remuneração: quem registrou o recebimento não liquida, não estorna, não decide
(quatro olhos). Nenhuma regra de cobrança ativa.

## 19. Fiscal

BLOCKED_EXTERNAL (inalterado).

## 20. Vouchers

Inalterado.

## 21. Identity

PARTIAL. Verificação de identidade: ninguém decide a própria (o banco confere), decisão não é reescrita, estados suspensa /
revogada / vencida (rotina `risk_scan` marca as vencidas). Verificação do beneficiário: vale a decisão mais recente; "verificado"
exige titularidade e segunda pessoa; recusa posterior tira as campanhas do ar. KYC/KYB por provedor continua BLOCKED_EXTERNAL
(contrato e parecer). Nenhuma biometria, gov.br ou ICP-Brasil simulados.

## 22. Security

Fase 1: auditoria por domínio (`docs/security/AUDITORIA_SEGURANCA_FASE1.md`); fase 2: lotes A–I. Achados novos provados e corrigidos: PAY-13 e DB-03 (§1). IP do
cliente pela ponta confiável do `X-Forwarded-For` (desligado até o responsável configurar e conferir no demo). `/readyz` público
resumido em produção. JSON profundo e `Content-Length` inválido → 400; conflito sem nome de restrição. Saída HTTP só para
endereço global. Logs sem segredo, e-mail mascarado e CPF redigido. Cadeia de entrega: actions por SHA, gitleaks também no push,
SBOM e varredura da imagem (informativos), Dependabot, cifra AUTENTICADA do backup. Nenhum segredo em código, workflow,
documento ou pacote (`secrets_scan.py`). **Nenhum sistema ligado à internet é invulnerável, e este não é exceção.**

## 23. LGPD

Apoiador pessoa física aparece mascarado na página pública até optar por mostrar o nome (ID-01). Excluir a conta apaga os
arquivos pessoais (identidade, dirigente, exportações); documentos institucionais ficam — prazos por tipo são pergunta ao
jurídico/DPO (FILE-09, PARCIAL). Logs redigidos (WEB-07). Nomes e endereços ainda podem sair para um provedor de IA externo
(nenhum ligado hoje; AI-03 PARCIAL).

## 24. Tests

```text
REGRESSÃO COMPLETA LOCAL (docs/evidence/test_run_v0.35.0.log), commit e9a892d:
  Ran 2570 tests in 2757.669s — 9 falhas, 1 erro, 31 pulados (dependem de credencial ou do servidor S3 do CI)
  → 1 real: test_v0170_payments esperava achar o evento NÃO assinado pelo id que ele alegava — o PAY-13 guarda esse evento
    sob identificador próprio de propósito; o teste antigo passou a procurá-lo pelo prefixo `unverified:` (fd1c86c);
    9 de fechamento: manifesto de rastreabilidade da versão, relatório/auditoria/manifesto/notas da v0.34.0 ainda no lugar,
    e 3 matrizes geradas antes da regressão (autorização, cobertura, jornadas por perfil) — regeneradas com a evidência
    que a própria regressão produziu. Correções e portões de fechamento reexecutados AO FIM DO MESMO LOG
CI DO PR #8, mesmo commit e9a892d (execução 38070321577): backend com as MESMAS 9 falhas e 1 erro (2570 testes) — a
  regressão local e a do CI concordam; auditoria, armazenamento, docker e segredos VERDES; pilha-do-zero VERMELHO:
  axe-core `select-name` em /admin/identidade (seletor do lote H sem nome acessível). Corrigido; teste novo
  test_e2e_v0350_admin_screens falha no front anterior (docs/security/evidencias/a11y_admin_identidade_antes_fd1c86c.txt)
CI DO PR #8, commit fd1c86c (execução 38071340835): backend 2570 testes, 0 erros (correção de test_v0170_payments confirmada),
  as 9 falhas de fechamento ainda presentes (documentos regenerados só no commit seguinte); pilha-do-zero: a mesma tela
PORTÕES DE FECHAMENTO, 1ª passagem (commit 56ceb6f + manifestos, ao fim do mesmo log): Ran 246 tests — 1 falha: a matriz de
  integrações não listava o módulo E2E novo (gerada antes dele); regenerada. 2ª passagem ao fim do log (matrizes, manifesto,
  cobertura, documentos de fechamento, matriz de autorização): Ran 88 tests — OK
MÓDULOS NOVOS: test_v0350_security (84, 32 classes) · test_v0350_release_docs (5) · test_e2e_v0350_admin_screens (2)
FALHA ANTES, PASSA DEPOIS: para cada lote A–I, os testes novos rodados no commit anterior ao lote (docs/security/evidencias/)
LINT: ruff 0 · TYPECHECK: tsc --noEmit 0 erros · BUILD: esbuild ok
PILHA LOCAL DO ZERO (roteiro do CI, sem Docker): 16 jornadas, 280 passos, 0 falha; 235 rotas de tela, 857 visitas, 235 abertas
  com dado real; 0 respostas 5xx; persistência após reiniciar: contagens iguais (docs/evidence/pilha_local_v0350.txt)
```

## 25. External Dependencies

| Dependência | Exige | Efeito hoje |
|---|---|---|
| Trocar o token do R2 do backup exposto ("C2") | responsável (Cloudflare + GitHub Secrets) | P0 independente da versão |
| Repositório privado; proteger a `main`; alertas do Dependabot | responsável (GitHub) | P0/P1 |
| Variáveis novas no Railway (`TRUST_PROXY_HEADERS`, `TRUSTED_PROXY_HOPS`, …) e conferência do IP no demo | responsável | sem elas, limites por IP seguem contornáveis por cabeçalho forjado |
| Juntar PRs #5 → #6 → #7 → #8; publicar demo e produção (com o worker) | responsável | correções fora do ar (produção na v0.30.0) |
| Backup no formato novo e ensaio de restauração depois do merge | responsável (Actions) | ensaio real pendente |
| Diagnóstico do banco de produção; antivírus da produção | autorização do responsável | NÃO VERIFICÁVEL |
| KYC/KYB por provedor, poderes de representação, beneficiário final | contrato + parecer | BLOCKED_EXTERNAL |
| Prazos de guarda por tipo de documento; comunicação de incidente | jurídico/DPO | perguntas abertas |
| Tag v0.35.0 | o ambiente não envia tags | criar no GitHub |

## 26. Known Limitations

- Produção recusar subir sem antivírus: **não feito por decisão do responsável**; o `pos-deploy` avisa se estiver desligado.
- Imagens de base por digest e hashes dos pacotes Python: não feitos (Docker Hub inacessível aqui; nada é fixado sem conferir).
- SBOM e varredura da imagem não bloqueiam nesta versão (a primeira execução mede a linha de base).
- Cifra da chave PIX em repouso (SEC-02): versão futura.
- 35 rotas editoriais da equipe seguem sem confirmação de identidade (não mexem em dinheiro, identidade nem permissão).
- Fracionamento por doador anônimo não é detectável sem identificar a pessoa (escolha de privacidade).
- Itens P2/P3 da fase 1 fora dos lotes A–I (CSRF sem Origin em rota anônima, OIDC, índices, rótulos) seguem abertos.
- Nenhum teste de intrusão externo foi feito.

## 27. GO / GO WITH CONDITIONS / NO-GO

```text
GO WITH CONDITIONS
```

Para juntar e publicar no demo e, depois de conferido, na produção. Condições: P0 do responsável (token "C2", repositório
privado); variáveis do `PUBLICATION_CHECKLIST_v0350.md` antes da produção (`PAYMENT_SANDBOX_ENABLED` e `REQUIRE_MFA_FOR_ADMINS`
erradas impedem a subida — o Railway mantém o deploy anterior); conferir o IP no demo; publicar o worker junto; backup e ensaio
no formato novo logo depois. As condições das v0.32.0–v0.34.0 continuam. **Cobrança real: NO-GO** (inalterado). A decisão de
publicar é humana.

## 28. Exact Next Step

1. P0: trocar o token "C2" e tornar o repositório privado (`docs/security/runbooks/RB-01-vazamento-de-segredo.md`).
2. Ordem dos merges (PR #5 → #6 → #7 → #8); no demo, percorrer `docs/security/PUBLICATION_CHECKLIST_v0350.md` (inclui a conferência
   do IP).
3. Produção: variáveis, "Deploy latest commit" no `impactohubsocial` e no `pleasing-trust`, `pos-deploy`, backup e
   `ensaio-restauracao`.
