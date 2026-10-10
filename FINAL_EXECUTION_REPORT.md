# Relatório final de execução — IMPACTO v0.34.0

**Data:** 10/10/2026 · **Ramo:** `ecossistema-v0340` (PR #7, sobre `doacoes-v0330` / PR #6; PR #5 da v0.32.0 ainda aberto) · **Tag:** `v0.34.0`
(a criar no GitHub pelo responsável no commit indicado em §3 — o ambiente das sessões não envia tags) · **Pacote:**
`IMPACTO_TRUST_FINAL_RELEASE_0.34.0.zip` (SHA-256 no `.sha256` ao lado) · **Auditoria:** `FINAL_EXECUTION_AUDIT.md` ·
**Relatório técnico (DOCX):** `IMPACTO_v0.34.0_RELATORIO_TECNICO.docx`

## 1. Executive Summary

O PROMPT MASTER FULL pediu, sobre a base de doações da v0.33.0, a **base de um ecossistema financeiro confiável**: arrecadação
rastreável, remuneração do SaaS calculável e cobrável, dados auditáveis, regras configuráveis, operações juridicamente compatíveis —
sem transformar cada operação social em cobrança automática. O responsável acrescentou três correções (MROSC por instrumento; nunca
reter prestação de contas; reserva sem custódia) e o modelo "gratuito até gerar valor" com gatilhos auditáveis. Entregue:

- **Obrigações de remuneração** com a cadeia completa (calculada → devida → faturada → cobrada → recebida → liquidada; estornada,
  vencida, em disputa, dispensada, isenta), valor congelado, histórico só-inserção, liquidação segregada (`finance.approve`).
  Receita prevista × devida × recebida × liquidada **nunca somadas**.
- **Gratuito até gerar valor** como política versionada (hipótese v1): nada é devido sem regra ativa, franquia de valor LIQUIDADO
  ultrapassada, aviso prévio registrado dentro do prazo e teto — e a avaliação diz por que cada obrigação NÃO virou devida.
- **Recurso público isento por padrão**, elegível só com instrumento e autorização registrada. **Reserva/fundo** do beneficiário no
  motor que o banco recusa ativar: nunca receita da plataforma. **Nenhuma obrigação condiciona prestação de contas** (teste vigia).
- **Estados do dinheiro** separados (pendente, confirmado, liquidado, em análise, estornado total/parcial, compromisso, recurso
  declarado fora), política de contagem, data da última atualização válida; **painel do financiador**.
- **Conciliação com fila de exceções** (9 tipos, prioridade, responsável, histórico; reexecutar não duplica); webhook ≠ conciliado.
- **Etapa E6 — os 40 cenários do pacote com teste** (o pedido era não deixar nada sem resolver): cartão (que nunca tinha
  funcionado no sandbox — achado do próprio teste), falha temporária do provedor, webhook em duas fases com reprocessamento,
  liquidação parcial e falha de liquidação, contribuição voluntária do doador com split SIMULADO e cobrança sem split,
  recorrência (autorização ≠ tentativa ≠ confirmado), reembolso do que a plataforma recebeu; rotina `financial_ops` no worker;
  e uma brecha fechada: a organização podia marcar como paga ou devolvida a própria fatura da plataforma.
- Documentos, matrizes, diagramas, modelo de 24 meses em 3 cenários e cobertura dos 40 cenários de teste em `docs/finance/`.

**Decisão: GO WITH CONDITIONS** (§27) para o sandbox. **Qualquer cobrança real: NO-GO** até parecer, contrato e cartas verdes —
o próprio banco recusa ativar as regras sem isso.

## 2. Version

0.34.0 — `VERSION`, `backend/pyproject.toml`, `web/package.json`, `web/package-lock.json`, `README.md`, `docs/openapi.json`.
Documentos da v0.33.0 preservados em `history/v0.33.0/`; manifestos anteriores em `history/manifests/`.

## 3. Commit

Ramo `ecossistema-v0340` sobre `103c643` (v0.33.0). Commits por etapa: E1 backend (`47e2564`), E2 testes (`dfd3a54`), E3 telas
(`761de0f`), E4 documentos (`696e220`), E5 portões (`d646a71`), E6 cenários pendentes (`5e380b8`) e documentos/portões da E6
(`b14c6e7`), e o commit final dos manifestos, para o qual a tag `v0.34.0` deve
apontar e do qual o pacote é construído byte a byte (`verify_package_against_git.py`). Nenhuma operação na produção. O CI do pull
request é a evidência externa (ver `FINAL_EXECUTION_AUDIT.md` §6).

## 4. Architecture Status

Camada financeira isolada sobre a v0.33.0: `remuneration.py` e `reconciliation.py` novos; `donations.py` estendido; nenhuma
dependência circular (os serviços de doação importam remuneração só em funções, e remuneração não importa rotas). Diagramas em
`docs/finance/diagramas/`. Operação inalterada (`CLAUDE.md`).

## 5. Engines Status

50 motores, inalterados; `MOTOR_COVERAGE_MATRIX.md` VERDE 37 · AMARELO 13 · VERMELHO 0.

## 6. Contract Intelligence

PASS (inalterado). A taxa de serviço do acordo (`contract.platform_service_fee`) continua INATIVA; o desenho de obrigações desta
versão aceita `source_kind = agreement_allocation` para unificá-la numa versão futura (não ligado agora).

## 7. Match

PASS (inalterado); sem pay-to-rank; nenhuma regra comercial influencia o matching.

## 8. Diagnostic

PASS (inalterado).

## 9. Equity

PASS (inalterado). Franquia e isenção de recurso público protegem as organizações pequenas por desenho.

## 10. Evidence

PASS (inalterado). Recursos externos aceitam `evidence_document_id`; `status = documented` quando há documento.

## 11. Responsibility

PARTIAL (inalterado).

## 12. Reputation

PASS (inalterado). Doações, compromissos e obrigações não alimentam reputação.

## 13. Seals

PASS (inalterado).

## 14. Government Data

Inalterado. Governos e empresas têm o painel de contribuições.

## 15. Marketplace

Inalterado: `marketplace.take_rate` recusada pelo responsável; a matriz de monetização registra o exemplo 90/10 do pacote como
hipótese a validar comercial e juridicamente; liberação por entregável NÃO (custódia).

## 16. Payments

Sandbox apenas. Novos estados: liquidação (`settled_at`) e liquidação ACUMULADA (`settled_cents`: parcial ≠ total), falha de
liquidação (exceção), estorno parcial (`refunded_cents`), `partially_refunded`; cartão funcional no sandbox (E6); falha temporária
do provedor responde 503 sem gravar nada; webhook em duas fases (evento nunca se perde; reprocessado pela rotina). Eventos
reconhecidos em `docs/finance/DONATIONS_API.md`. `payment_records` da v0.28.0 intocado; `platform_charges` reutilizado para a fatura
própria (kind `operation`, provedor manual, simulado por derivação).

## 17. Distribution

PASS (inalterado).

## 18. Billing

Sem assinatura de plano (ADR-341). 16 regras no catálogo, **0 ativas** (a 16ª, `donation.platform_contribution`, é a
contribuição voluntária do doador, ADR-384); política `free_until_value` v1 (hipótese). Reembolso integral do recebido segregado
(`finance.approve`); a organização não move a fatura da plataforma (403 `platform_invoice`).

## 19. Fiscal

BLOCKED_EXTERNAL. `LEGAL_FISCAL_MATRIX.md` lista documento provável por tipo de receita; NFS-e não implementada.

## 20. Vouchers

Inalterado.

## 21. Identity

PARTIAL (inalterado). KYB do beneficiário registrado; processo depende do provedor e do parecer.

## 22. Security

Modelo de ameaças da v0.33.0 (19 linhas) + matriz de riscos da v0.34.0 (28 linhas, `docs/finance/RISK_MATRIX.md`). Achado e
corrigido na E6: a rota de cobranças deixava a organização mover a fatura de remuneração da plataforma (marcar paga/devolvida) —
agora 403, com teste. Segregação:
liquidar, decidir disputa, dispensar e autorizar recurso público exigem `finance.approve` com confirmação de identidade. Concorrência
de webhooks provada (6 entregas simultâneas → 1 confirmação). Campo estranho no corpo → 422. Nenhum segredo em código, workflow,
documento ou pacote (`secrets_scan.py`). **Nenhum sistema ligado à internet é invulnerável, e este não é exceção.**

## 23. LGPD

Inalterado em relação à v0.33.0 (e-mail cifrado, anônimo protegido, bruto redigido). Novo: `donor_org_id` identifica a organização
doadora apenas quando ela escolhe doar em nome próprio; compromissos e recursos externos não expõem dados pessoais em público.

## 24. Tests

```text
REGRESSÃO COMPLETA LOCAL (docs/evidence/test_run_v0.34.0.log):
  Ran 2478 tests in 2257.161s — 8 falhas, 1 erro, 31 pulados (dependem de credencial ou do servidor S3 do CI)
  → 6 de fechamento (manifesto, marcador e linha de testes deste relatório, notas/manifesto da versão, 2 matrizes geradas antes
    da rodada, formato da tabela §7 da auditoria); 1 real: a regra da contribuição declarava preço fixado (corrigido: modo
    `contract`, sem preço); 1 erro de navegador causado por eu reconstruir o front no meio da suíte (módulo reexecutado: verde).
    Correções reexecutadas e portões de fechamento ao fim do mesmo log
PRIMEIRA RODADA (E5, antes da E6): Ran 2470 tests — 9 falhas: 3 reais (retenção, catálogo polimórfico, função morta) + 6 de
  fechamento; causas e correções em FINAL_EXECUTION_AUDIT.md §7
MÓDULOS NOVOS: test_v0340_financial_ecosystem (13) · test_v0340_open_scenarios (8) · test_v0340_release_docs (6)
PORTÕES PRÉ-REGRESSÃO (arquitetura, permissões, matriz de autorização, ícones, adversarial, conhecimento, jornadas): 241 testes OK
LINT: ruff 0 · TYPECHECK: tsc --noEmit 0 erros · BUILD: esbuild ok
TELAS: capturas reais em docs/evidence/screens_v0340/ (6 telas, fluxo completo no servidor de teste, sandbox)
COBERTURA DOS 40 CENÁRIOS DO PACOTE: docs/finance/TEST_SCENARIO_COVERAGE.md — 40 com teste (split e recorrência SIMULADOS no
  teste, ditos como tal; nenhum finge provedor real). Primeira rodada: 32 ✅ · 4 🟡 · 4 ⛔ — fechados na E6
```

## 25. External Dependencies

| Dependência | Exige | Efeito hoje |
|---|---|---|
| Parecer jurídico/contábil → cartas legais verdes → regras validadas | jurídico/contábil + responsável | nenhuma obrigação pode virar devida |
| Contrato com provedor de pagamento; modelo de titularidade | responsável + provedor | só sandbox |
| Termos (campanha, doador, política, contrato institucional, autorização de despesa pública) | jurídico | textos em rascunho |
| NFS-e | contábil + integração | não implementada |
| Publicar o worker (`pleasing-trust`) junto | responsável | sem a publicação, a rotina `financial_ops` (reprocessamento, vencidas, conciliação periódica) não roda |
| Instrumento recorrente homologado (Pix Automático/cartão) e split no provedor | responsável + provedor | recorrência e split ficam desligados pela configuração |
| Juntar PRs #5, #6 e este ramo; publicar demo e produção | responsável | módulo fora do ar |
| Pendências da v0.32.0 (worker, token do backup, repositório privado, monitor externo) | responsável | inalteradas |
| Tag v0.34.0 | o ambiente não envia tags | criar no GitHub |

## 26. Known Limitations

- Obrigações nascem de doações (taxa e contribuição voluntária); acordo, serviço e crédito de IA têm `source_kind` previsto mas
  não ligado.
- O snapshot do provedor no sandbox deriva dos próprios eventos — prova o mecanismo, não a API de um provedor real.
- Split e recorrência: caminhos testados com o provedor SIMULADO no teste; continuam recusados pela configuração até contrato e
  homologação.
- Reembolso parcial do que a plataforma recebeu é ajuste por decisão humana, não automático.
- Modelo de 24 meses: premissas sem histórico; a taxa sobre doações não sustenta a operação em nenhum cenário.
- Textos dos avisos e termos são rascunhos.

## 27. GO / GO WITH CONDITIONS / NO-GO

```text
GO WITH CONDITIONS
```

Para juntar e publicar no demo e, depois de conferido, na produção — onde nenhuma cobrança é possível e nenhuma variável nova é
obrigatória. Condições: as da v0.32.0 e v0.33.0 continuam. **Cobrança real, split, recorrência cobrada, regra ativa: NO-GO** até
parecer, contrato, cartas verdes e ADR nova.

## 28. Exact Next Step

1. Ordem dos merges (PR #5 → PR #6 → este ramo) ou um só sobre o PR #5.
2. No demo: percorrer `docs/finance/PUBLICATION_ROLLBACK_CHECKLIST.md` (inclui o runbook da v0.33.0).
3. Levar `docs/finance/LEGAL_FISCAL_MATRIX.md` e `docs/donations/LEGAL_AND_PROVIDER_CHECKLIST.md` ao jurídico/contábil; escolher
   o provedor pela matriz. Nada disso é código.
