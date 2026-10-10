# Relatório final de execução — IMPACTO v0.33.0

**Data:** 10/10/2026 · **Ramo:** `doacoes-v0330` (PR #6, sobre `correcoes-auditoria` / PR #5 ainda aberto) · **Tag:** `v0.33.0` (a criar no
GitHub pelo responsável no commit indicado em §3 — o ambiente das sessões não envia tags) · **Pacote:**
`IMPACTO_TRUST_FINAL_RELEASE_0.33.0.zip` (SHA-256 no `.sha256` ao lado) · **Auditoria:** `FINAL_EXECUTION_AUDIT.md` ·
**Relatório técnico (DOCX):** `IMPACTO_v0.33.0_RELATORIO_TECNICO.docx`

## 1. Executive Summary

O pacote `IMPACTO_TRUST_v0.31.0_MONETIZACAO_DOACOES_MASTER_FULL` pediu doações, vaquinha, QR Pix, recorrência, "carteira
visual", PLD/KYC, comprovantes e prestação de contas — como módulo isolado, sem fintech dentro do SaaS, com provedor
sandbox e taxas como hipótese. Feito, com estas fronteiras:

- **Sem custódia, sem provedor real.** Nenhuma coluna de saldo em lugar algum; totais vêm de um razão em partidas dobradas
  (só inserção, soma zero por transação) e são rotulados "saldo contábil estimado — não é dinheiro guardado". O único
  provedor é o `SandboxProvider`; as travas `LIVE_PAYMENT_PROVIDER_ENABLED`, `SPLIT_ENABLED`,
  `RECURRING_DONATIONS_ENABLED`, `RISK_HOLD_ENABLED` recusam subir com `true`.
- **Confirmação só vem de fora.** Uma doação é confirmada exclusivamente por evento assinado do provedor no webhook —
  idempotente por `provider+event_id`, valor conferido, reversão lançada uma única vez.
- **Publicar passa por quatro olhos**: termos aceitos, aprovação por outra pessoa da equipe e beneficiário verificado; o
  atalho `PATCH status=published` responde 409. O QR leva à própria página (versionada), nunca a uma chave Pix.
- **Taxas inativas.** `donation.platform_fee` (1 %) e `donation.beneficiary_fund` (≤ 4 %) estão no catálogo como hipóteses
  `review_required`; devido = R$ 0,00; versão congelada por doação; preço total mostrado antes de pagar.
- **Risco proporcional**: três regras versionadas abrem casos para decisão humana justificada; `payout_hold` não existe.
- **Provedores pesquisados** (Asaas e Mercado Pago) nas docs oficiais em 10/10/2026; nada contratado.

**Decisão: GO WITH CONDITIONS** (§27) para o sandbox — juntar e publicar no demo; a produção recebe o módulo sem nenhuma
doação real possível. **Provedor real: NO-GO** até o checklist jurídico/provedor (`docs/donations/LEGAL_AND_PROVIDER_CHECKLIST.md`).

## 2. Version

0.33.0 — `VERSION`, `backend/pyproject.toml`, `web/package.json`, `web/package-lock.json`, `README.md`, `docs/openapi.json`.
Documentos da v0.32.0 preservados em `history/v0.32.0/`; manifestos anteriores em `history/manifests/`.

## 3. Commit

Ramo `doacoes-v0330` sobre `24793bb` (`correcoes-auditoria`, v0.32.0). Commits: módulo (migração 0072, serviço, rotas,
flags, testes), interface e documentos, correções dos portões de fechamento, e o commit final dos manifestos, para o qual a
tag `v0.33.0` deve apontar e do qual o pacote é construído byte a byte (`verify_package_against_git.py`). Nenhuma operação
na produção nesta versão. O CI do pull request fica como evidência externa (ver `FINAL_EXECUTION_AUDIT.md` §6).

## 4. Architecture Status

Módulo novo `donations` (serviço + rotas + migração), isolado: nenhum outro módulo depende dele; ele depende de
`campaigns`, `monetization_rules`, `organizations`, cifra de campo e QR já existentes. Operação inalterada (`CLAUDE.md`).

## 5. Engines Status

50 motores, inalterados; `MOTOR_COVERAGE_MATRIX.md` VERDE 37 · AMARELO 13 · VERMELHO 0. Doações não são "motor": são
fluxo de arrecadação com conciliação.

## 6. Contract Intelligence

PASS (inalterado).

## 7. Match

PASS (inalterado); sem pay-to-rank.

## 8. Diagnostic

PASS (inalterado).

## 9. Equity

PASS (inalterado).

## 10. Evidence

PASS (inalterado). Gastos de campanha (`campaign_expenses`) reutilizam `document_id` para evidência; validação documental
fica para quando houver revisor definido.

## 11. Responsibility

PARTIAL (inalterado).

## 12. Reputation

PASS (inalterado). Doações não alimentam reputação.

## 13. Seals

PASS (inalterado).

## 14. Government Data

Inalterado.

## 15. Marketplace

Inalterado (comissão recusada).

## 16. Payments

**Mudou, dentro da regra:** doações em sandbox, confirmadas só por webhook assinado; nenhum pagamento real; nenhum provedor
ligado; `payment_records` da v0.28.0 intocado. `NON_CUSTODIAL_ARCHITECTURE.md` continua valendo (ADR-284, ADR-372).

## 17. Distribution

PASS (inalterado).

## 18. Billing

Inalterado: sem assinatura (ADR-341); 0 regras ativas (13 no catálogo, as 2 de doação inativas).

## 19. Fiscal

BLOCKED_EXTERNAL (inalterado). Comprovante de doação diz não ser recibo dedutível; parecer contábil pendente.

## 20. Vouchers

Inalterado.

## 21. Identity

PARTIAL (inalterado). KYB do beneficiário: a plataforma registra o estado (`org_kyb_verifications`); quem verifica e com
quais documentos depende do provedor e do parecer.

## 22. Security

Modelo de ameaças em `docs/donations/SECURITY_REVIEW.md` (19 ameaças, 15 cobertas por teste). Novas rotas públicas e o uso
de contexto de sistema no módulo foram registrados nas listas revisadas de `test_architecture.py` com a razão de cada um.
Nenhum segredo em código, workflow, documento ou pacote (`secrets_scan.py`). **Nenhum sistema ligado à internet é
"impossível de invadir", e este não é exceção.**

## 23. LGPD

E-mail do doador cifrado em repouso e só se ele quiser comprovante; doador anônimo nunca aparece em público nem para a
organização; bruto do webhook redigido (CPF, e-mail, telefone, IP, cartão, nome) antes de guardar. Base legal, aviso de
privacidade e dados exigidos pelo provedor estão no checklist jurídico (item 7) — pendentes.

## 24. Tests

```text
REGRESSÃO COMPLETA LOCAL (docs/evidence/test_run_v0.33.0.log):
  Ran 2451 tests in 1807.781s — 8 falhas, 0 erro, 31 pulados (dependem de credencial ou do servidor S3 do CI)
  → as 8: manifesto da versão, marcador de preenchimento e linha de testes deste relatório, notas da versão lidas antes do bump,
    3 matrizes geradas antes da rodada, e /doacao/:id sem registro na demonstração (a jornada "Captação" ganhou a
    doação pública em sandbox); corrigidas no fechamento e reexecutadas ao fim do mesmo log
PRIMEIRA RODADA (antes das correções dos portões): Ran 2444 tests — 21 falhas + 1 erro, todas em portões de fechamento
  (listas revisadas, contagens fixadas, matrizes, atalho legado de publicação) — causa e correção em
  FINAL_EXECUTION_AUDIT.md §7. Nenhum teste removido ou enfraquecido.
MÓDULOS NOVOS: test_v0330_donations (11) · test_v0330_release_docs (6)
LINT: ruff 0 · TYPECHECK: tsc --noEmit 0 erros · BUILD: esbuild ok
TELAS: capturas reais em docs/evidence/screens_v0330/ (fluxo completo no servidor de teste, sandbox)
```

## 25. External Dependencies

| Dependência | Exige | Efeito hoje |
|---|---|---|
| Contrato com provedor de pagamento (Pix) e tarifa escrita | responsável | só sandbox |
| Modelo de titularidade da cobrança (conta do beneficiário × plataforma com split) | responsável + jurídico | código só suporta conta do beneficiário |
| Parecer sobre taxa de serviço, fundo, comprovante/dedutibilidade, termos | jurídico/contábil | taxas inativas; termos em rascunho |
| LGPD do doador e dados exigidos pelo provedor | DPO/jurídico | anônimo pode não ser possível com certos provedores |
| Processo de KYB do beneficiário | compliance | só o registro existe |
| Juntar PR #5 (v0.32.0) e este ramo; publicar demo e produção | responsável | módulo fora do ar |
| Pendências da v0.32.0 (worker, token do backup, repositório privado, monitor externo) | responsável | inalteradas |
| Tag v0.33.0 | o ambiente não envia tags | criar no GitHub |

## 26. Known Limitations

- Doação recorrente: só tabela e cancelamento; cobrança recorrente desligada.
- Taxa institucional 3,5 %/1,5 % do pacote: sem definição de "institucional" nem de base — ficou como texto, não como regra.
- E-mail ao doador não é enviado nesta versão (entra com o provedor real).
- Validação documental de gastos (`evidence_status = validated`) sem rotina de revisão.
- A assinatura do sandbox não tem carimbo de tempo; o adaptador real deve validar janela temporal (SECURITY_REVIEW #15).
- Modelo de 24 meses sem linha de doações, de propósito (`docs/donations/24_MONTH_DONATIONS_NOTE.md`).

## 27. GO / GO WITH CONDITIONS / NO-GO

```text
GO WITH CONDITIONS
```

Para o módulo em sandbox: juntar na `main` (o demo publica sozinho), testar o fluxo do `RUNBOOK.md` §1 no demo e, depois
de conferido, publicar a produção — onde nenhuma doação real é possível e nenhuma variável nova é obrigatória. Condições:
as da v0.32.0 continuam; nenhuma falha crítica foi convertida em "condição". **Provedor real, split, recorrência cobrada e
taxa ativa: NO-GO** até o checklist jurídico/provedor e uma ADR nova que remova a recusa em `config.validate()`.

## 28. Exact Next Step

1. Decidir a ordem: juntar o PR #5 (v0.32.0) e depois este ramo, ou este ramo já sobre o PR #5 (ele contém a v0.32.0).
2. Abrir o demo depois do merge e percorrer o `docs/donations/RUNBOOK.md` §1 (criar → revisar → verificar → publicar → doar).
3. Escolher o provedor a partir de `docs/donations/DONATIONS_PROVIDER_MATRIX.md` e iniciar o contrato; levar o checklist ao
   jurídico. Nada disso é código.
