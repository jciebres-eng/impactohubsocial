# Relatório final de execução — IMPACTO v0.28.0

**Data:** 09/10/2026 · **Ramo:** `main` · **Tag:** `v0.28.0` (a criar no GitHub pelo proprietário no
commit indicado em §3 — o proxy deste ambiente recusa envio de tag) · **Pacote:**
`IMPACTO_TRUST_FINAL_RELEASE_0.28.0.zip` (SHA-256 no `.sha256` ao lado) · **Auditoria:**
`FINAL_EXECUTION_AUDIT.md` · **Relatório técnico (DOCX):** `IMPACTO_v0.28.0_RELATORIO_TECNICO.docx`
(entregue ao lado do pacote; conteúdo derivado deste relatório e da auditoria)

## 1. Executive Summary

A rodada tornou a IA do IMPACTO **governável e financeiramente sustentável** e entregou o **motor de
originalidade, complementaridade, sobreposição territorial e integridade do financiamento** — sem
assinatura (ADR-341), sem fintech dentro do produto (ADR-284), sem inventar preço, parecer,
integração ou publicação:

- **Inventário antes de construir** (`docs/execution/AI_INVENTORY.md`): a camada de IA já tinha prompt
  versionado, faixa de risco, uso registrado, tabela de preço (vazia), orçamento em dinheiro e razão
  de créditos — mas **nenhuma chamada consumia crédito**, a cota era fixa no pacote e não havia prévia,
  fonte de custeio, patrocínio, pedido de crédito, execução com estado nem conciliação.
- **Camada central de uso e custo** (`engines/ai/usage_control.py`, migração 0068): catálogo
  versionado de 12 operações (categorias A–F; 9 executáveis, 3 declaradas → 501); execução com máquina
  de estados `created → authorized → reserved → running → succeeded/failed/partial/cancelled →
  reconciled` guardada pelo banco; **débito só em sucesso**; idempotência; concorrência sem
  ultrapassar saldo; prévia obrigatória com custo, fonte, saldo e critério de conclusão.
- **Quatro fontes de custeio, nesta ordem:** gratuito → patrocínio institucional → cota promocional
  (boas-vindas 60, uma vez por organização E por pessoa; mensal leve 10) → crédito comprado → recusa
  `402` com opções. Razão por lote, com validade, escrito só por função com portão.
- **Créditos pré-pagos via PIX, sem venda real ainda:** pedidos em **modo piloto** (aprovação manual,
  crédito promocional, R$ 0,00) enquanto a regra `ai.credits_prepaid` (11ª do catálogo, carta amarela)
  estiver inativa e não houver provedor; **modo real** exige webhook HMAC idempotente (ou conciliação
  manual com referência) E regra ativa — cobrança simulada **nunca** credita.
- **Claude API × assinatura verificadas na documentação oficial:** a assinatura Claude.ai de ninguém
  paga nem autoriza chamadas do IMPACTO; o sistema nunca pede senha/sessão/token de assinatura.
  **BYOK não liberado** (requisitos documentados, ADR-351). Escolha: híbrido A + C + D-local.
- **Similaridade por dimensões, local, explicável, contestável, sem bloqueio e sem efeito
  reputacional** (`similarity@1.0`): texto, escopo, público, território, tempo, orçamento,
  financiamento, indicadores — leituras separadas (reprodução textual ≠ sobreposição de escopo ≠
  duplicidade territorial ≠ duplicidade de despesa ≠ complementaridade), recomendações, confiança,
  cache por versão, trilha de autoria; outra organização só vê contagem k-anônima (k ≥ 3). Conjunto
  de avaliação rotulado (6 pares; P/R = 1,0 nas duas leituras de alto impacto) — **pequeno e
  sintético, não é desempenho em base real**.
- **Painel financeiro** medido × NÃO MEDIDO (créditos vendidos ≠ receita; GMV ≠ receita); **modelo de
  custo derivado** de hipóteses declaradas e de medição real do piloto local (par 0,75 ms; 200
  candidatos 153 ms), 3 cenários × 12 meses, doze perguntas, teto de subsídio declarado.
- **Limpeza:** 19 manifestos antigos (5,3 MB) para `history/manifests/`; consumo de crédito unificado;
  inventário do que ficou e por quê.
- Tudo provado por HTTP e PostgreSQL reais (45 testes novos em 4 módulos), por 3 jornadas no
  navegador, pela jornada demo "Central de IA" (16 jornadas, 256 passos, 0 falha), pelas 225 telas no Chromium por
  perfil (825 visitas, 0 falha) e pela regressão completa, cuja primeira passagem acusou 14 falhas — todas com causa e
  correção escritas (auditoria §7), nenhuma resolvida afrouxando teste. **Receita real de IA desta
  instalação: R$ 0,00.**

**Decisão: GO WITH CONDITIONS** (§27) — piloto com medição real antes de qualquer cobrança real.

## 2. Version

0.28.0 — `VERSION`, `backend/pyproject.toml`, `web/package.json`, `web/package-lock.json`,
`README.md`, `docs/openapi.json`. Documentos da v0.27.0 preservados em `history/v0.27.0/` (164
arquivos de `227c9aa`); manifestos de todas as versões anteriores em `history/manifests/`.

## 3. Commit

Commits da rodada (sobre `227c9aa`, v0.27.0): `1e56233` (F2–F4: migração 0068, camada de uso,
similaridade, rotas da Central de IA, 38 testes), `a86a566` (F5: Central de IA no front, painel na
ficha do projeto, E2E, jornada demo), `128b50a` (F6: modelo de custo, inventário da IA, avaliação de
provedores/BYOK, ADR-347..352, limpeza), `a8c358e` (versão 0.28.0, snapshot `history/v0.27.0/`,
matrizes regeneradas), `82dec72` (correções da primeira regressão, matrizes), o commit de fechamento
(auditoria, relatório, checklist, rollback, guia de monitoramento, evidência da regressão) e o
**commit final dos manifestos**, para o qual a tag `v0.28.0` deve apontar e do qual o pacote é
construído byte a byte (`verify_package_against_git.py`); o hash desse commit é registrado no
`.sha256` do pacote e não cabe dentro do próprio commit. `FINAL_RELEASE_MANIFEST.json` registra o
último commit de conteúdo.

**GitHub Actions:** o resultado da run do commit final é relatado no parágrafo acrescentado ao fim
desta seção depois da run (como na v0.27.0); até lá, nada aqui afirma que o CI passou.

## 4. Architecture Status

Starlette + PostgreSQL 16 com RLS em toda tabela (exceção: `schema_migrations`; nenhuma FORCE), hash
encadeado em auditoria/razão/valor/confiança, sem custódia. Mudanças: 11 tabelas novas de IA e
similaridade; `ai_credit_ledger` ganha lote/validade/execução e passa a ser escrito só por função com
portão; `platform_charges.kind` ganha `ai_credits`; `charge_requires_authorization` v3;
`engines/ai/usage_control.py`, `engines/similarity/`, `services/similarity.py`,
`services/ai_center.py`, `api/ai_center_routes.py` (28 rotas) novos; gateway de IA passa pela camada
de uso. Documentos canônicos: `docs/execution/AI_INVENTORY.md`, `AI_PROVIDERS_EVALUATION.md`,
`AI_COST_MODEL.md`, `docs/execution/CLEANUP_INVENTORY_v0280.md`.

## 5. Engines Status

50 motores (48 + `ai_usage_control`, `similarity`): implemented/integrated/tested 50/50;
`MOTOR_COVERAGE_MATRIX.md` (gerado) VERDE 37 · AMARELO 13 (motores de leitura sem rastro durável ou
sem rota própria, por desenho, com motivo listado) · VERMELHO 0; 45 determinísticos.
`ENGINE_COVERAGE.md`, `docs/execution/ENGINE_VALIDATION_MATRIX.csv`, `docs/AI_ENGINES.md`.

## 6. Contract Intelligence

PASS (inalterado da v0.26.0/v0.27.0): o acordo de financiamento recebe percentuais do catálogo; mudar
o contrato cria versão nova e estorna instruções abertas. A similaridade **não lê nem escreve** no
contrato; a leitura "integridade do financiamento" só declara múltiplas fontes, nunca acusa
(`test_multiple_funding_sources_are_declared_not_accused`).

## 7. Match

PASS (inalterado): nenhum pacote, voucher, convênio, contrato, crédito, patrocínio ou análise de
similaridade altera match, elegibilidade ou ranking
(`test_similarity_touches_neither_match_nor_reputation_nor_funding`, `test_architecture`). Sem
pay-to-rank. A complementaridade é **sugestão** ao proponente, não critério de ranking.

## 8. Diagnostic

PASS (inalterado): `diagnostic-engine@1.0.0`, 8 dimensões. Não tocado.

## 9. Equity

PASS (inalterado): sem nota única, denominador com fonte. Não tocado.

## 10. Evidence

PASS (inalterado): quitação exige entrega aceita E repasse confirmado. A análise de similaridade é
registro append-only com hash dos insumos e versão do motor — serve como **evidência de
originalidade do próprio projeto** para quem a pediu; nunca como prova contra terceiro.

## 11. Responsibility

PARTIAL (inalterado): atribuição formal continua opcional.

## 12. Reputation

PASS: inalterada — e **blindada** desta rodada: nenhuma leitura de similaridade produz efeito
reputacional, selo negativo, bloqueio ou alerta a terceiros (`test_textual_reproduction_is_an_indication_never_a_verdict`).

## 13. Seals

PASS (inalterado): selos só na quitação. Nenhum selo por comprar crédito, patrocinar ou usar IA.

## 14. Government Data

Inalterado: torre territorial com k-anonimato ≥ 3; a sobreposição territorial oculta da similaridade
usa o **mesmo limiar** (`similarity_hidden_overlap`, k ≥ 3). Dados IBGE/ODS oficiais continuam fora.

## 15. Marketplace

Inalterado: comissão recusada. Patrocínio de IA não é marketplace: o patrocinador compra créditos da
plataforma (regra `ai.credits_prepaid`) e os aponta a beneficiários; nenhum repasse entre organizações.

## 16. Payments

PASS / BLOCKED_EXTERNAL: pedidos de crédito com `platform_charges.kind = 'ai_credits'` (PIX com
validade de 2 dias); webhook `POST /v1/webhooks/payments/{provider}` com HMAC sobre o corpo cru,
idempotente por evento, 404 sem segredo; modo real exige referência de pagamento E regra ativa; modo
piloto não movimenta dinheiro. **Nenhum pagamento real**: sem provedor, `PAYMENT_WEBHOOK_SECRET`
vazio, regra inativa. Camada 3,5% / 1,5% da v0.27.0 **inalterada e independente** (ADR-350).

## 17. Distribution

PASS (inalterado): matriz de distribuição imutável, soma fechada por CHECK. Créditos de IA não
entram na matriz (são serviço próprio da plataforma, fora da operação financiada).

## 18. Billing

MIGRATE (inalterado) + novo: **créditos pré-pagos por operação** como único modelo de cobrança da IA —
sem assinatura, sem plano de IA, sem cobrança por capacidade. Preços e pacotes são hipóteses marcadas
`hypothesis` no catálogo e `[PREMISSA]` no modelo; a interface diz "preço de teste". GET `/v1/ai/center`
mostra saldo por lote, cotas, operações, pedidos, patrocínios, regras.

## 19. Fiscal

BLOCKED_EXTERNAL: NFS-e não implementada. A carta `ai.credits_prepaid` lista as perguntas fiscais
abertas (natureza do crédito pré-pago, ISS × software, estorno de crédito não usado, validade) —
`MONETIZATION_LEGAL_MATRIX.md`.

## 20. Vouchers

Inalterado: vouchers de concessão continuam; de desconto aposentados. Crédito promocional de IA **não
é voucher**: é lançamento no razão com validade, concedido por política de cota ou aprovação de
piloto.

## 21. Identity

PARTIAL (inalterado): biometria, KYC, gov.br BLOCKED_EXTERNAL. Novo: a cota de boas-vindas é uma por
pessoa (anti-abuso de contas) — limite por identidade interna, não KYC.

## 22. Security

Revisada: RLS em toda tabela nova; razão de créditos só por SECURITY DEFINER com portão por motivo;
débito só em sucesso; webhook HMAC idempotente; pedido/confirmação exigem `billing.write` com
confirmação de identidade; contestação admin exige `support.write` (endurecimento desta rodada);
contexto de sistema restrito; nenhum segredo em código/documento/pacote (`secrets_scan.py`, gitleaks
no CI); nenhum uso de credencial de assinatura Claude.ai; similaridade local (nada sai). **Nenhum
sistema ligado à internet é "impossível de invadir", e este não é exceção.**

## 23. LGPD

`config/data_retention.json` cobre `ai_credit_orders`, `ai_executions`, `ai_quota_grants` (retidas
por organização, anonimizáveis por pessoa) e `similarity_analyses`/`similarity_disputes` (retidas);
a similaridade roda em faixa 3 (nada sai da instalação); o resumo de IA passa pela redação de dado
pessoal já existente; a prestação de contas de patrocínio é agregada, sem texto dos projetos
beneficiados; outra organização nunca vê texto, só contagem k-anônima.

## 24. Tests

```text
PRIMEIRA REGRESSÃO COMPLETA (código novo, antes das correções, scratchpad/suite/full_v0280_a.log):
  Ran 2342 tests — 14 falhas, 0 erro, 29 pulados
  → causas e correções em FINAL_EXECUTION_AUDIT.md §7 (1 endurecimento real: contestação admin exige
    support.write; 1 defeito de ferramenta: sed do bump de versão alterou o package-lock; o resto:
    retenção declarada, mapas, matrizes, documentos de fechamento e dois testes novos que dependiam
    do estado de outros testes na mesma base — corrigidos para ler o banco, sem afrouxar a prova)
SEGUNDA REGRESSÃO COMPLETA (após correções, docs/evidence/test_run_v0.28.0.log):
  Ran 2342 tests in 1953.844s — 0 erro, 29 pulados (dependem de credencial), 5 falhas, TODAS de fechamento:
    4× test_v0270_release_docs (lê auditoria, relatório e manifesto no início da execução — ainda os da v0.27.0
       naquele instante; reescritos durante a execução; reexecutado depois: 11/12, só o manifesto faltava),
    test_v0230_release_gate.test_the_manifest_exists_for_this_version (manifesto é gerado no fechamento).
  Manifestos gerados em seguida; os portões de fechamento reexecutados verdes (saída anexada ao fim do mesmo log).
MÓDULOS NOVOS: test_v0280_ai_usage_control (25) · test_v0280_similarity (13) · test_v0280_ai_cost_model (4) · test_e2e_v0280_ai_center (3)
JORNADAS: 16 jornadas, 256 passos, 0 falha (nova: Central de IA) · TELAS: 825 visitas, 225 rotas, 0 falha · TELEFONE: no CI (pilha do zero)
LINT: ruff 0 · BUILD: esbuild ok · TYPECHECK: no CI (npm ci); local sem @types/react, sem aviso nos arquivos tocados
```

Testes que fixam contagem foram atualizados com a razão escrita ao lado (923 operações, 229 de
plataforma, 94 com permissão, 51 públicas, 225 telas, 50 motores, 11 regras): ADR-340. Nenhum teste
foi removido ou enfraquecido.

## 25. External Dependencies

BLOCKED_EXTERNAL_DEPENDENCY, com o que cada uma exige (tabela completa em `EXTERNAL_INTEGRATIONS.md`):

| Dependência | Exige | Efeito hoje |
|---|---|---|
| Parecer jurídico e contábil da regra `ai.credits_prepaid` (e da taxa de serviço 3,5%) | advogado(a) e contador(a): natureza do crédito pré-pago, ISS, NFS-e, estorno, validade | regra desligada; pedidos só em modo piloto; **nenhuma venda** |
| Provedor de pagamento PIX com webhook | contrato + `PAYMENT_WEBHOOK_SECRET` | webhook responde 404; nada creditado por pagamento |
| Provedor de modelo + tabela de preço | `AI_API_KEY`, `AI_MODEL`, linhas em `ai_price_table` | `AI_PROVIDER=local`; custo externo zero MEDIDO porque não há chamada externa; com provedor e sem preço: NÃO MEDIDO |
| BYOK | decisão do proprietário + cofre por tenant | não existe; a interface não promete |
| Piloto com medição real | 30 dias com cota + patrocínio + pedidos piloto | preços, cotas e teto de subsídio continuam hipóteses |
| Chave PIX da plataforma, banco, nota fiscal, assinatura qualificada, gov.br, biometria, KYC, SMS/WhatsApp, minutas, hospedagem | como na v0.27.0 | inalterado |
| Tag `v0.28.0` no GitHub | o proxy recusa push de tag e API de escrita | criar manualmente no commit de fechamento |

## 26. Known Limitations

- Receita real de IA R$ 0,00 por construção até parecer + provedor + regra ativa.
- Conjunto de avaliação da similaridade: 6 pares sintéticos; precisão/recall de 1,0 ali **não** é
  desempenho em base real; alertas de alto impacto exigem revisão humana (o resultado diz isso).
- Motor de similaridade é léxico/estrutural (shingles, Jaccard, dimensões declaradas) — sem
  embeddings; paráfrase profunda pode escapar da leitura textual e cair só em escopo/público.
- Lote, monitoramento recorrente e relatório institucional: declarados `planned`, rota 501.
- Cache do resumo de IA por versão de projeto: parcial (hash de entrada em `ai_usage`).
- Custo de infraestrutura, tarifa de PIX e impostos: NÃO MEDIDOS (painel diz).
- Documentos SUPERADO da assinatura continuam no repositório com banner (movê-los exige atualizar
  60+ referências — rodada dedicada).
- Typecheck oficial do front só no CI.
- Defeitos pré-existentes B1/B2 (`TECHNICAL_BASELINE_BEFORE_EXECUTION.md` §4) continuam fora do escopo.

## 27. GO / GO WITH CONDITIONS / NO-GO

```text
GO WITH CONDITIONS
```

Nenhuma falha técnica interna crítica em aberto: catálogo versionado, execução com estado e débito só
em sucesso, razão por lote com portão, cotas com anti-abuso, patrocínio, pedidos piloto × real, webhook
idempotente, similaridade por dimensão sem bloqueio e sem efeito reputacional, isolamento k-anônimo,
painel medido × não medido, projeção derivada, autorização, tenancy, persistência e fluxo completo têm
teste executado e verde na segunda regressão. As condições são externas ou de piloto (§25): parecer,
provedor de pagamento, provedor de modelo com preço, **medição real do piloto antes de cobrança real**,
tag no GitHub. Nenhuma falha crítica foi convertida em "condição". Checklist operacional:
`docs/execution/PRODUCTION_CHECKLIST_v0280.md`; rollback: `docs/execution/ROLLBACK_v0280.md`;
monitoramento: `docs/execution/AI_COST_MONITORING_GUIDE.md`.

## 28. Exact Next Step

1. Criar a tag `v0.28.0` no GitHub (Releases → nova tag no commit de fechamento) e anexar
   `IMPACTO_TRUST_FINAL_RELEASE_0.28.0.zip` + `.sha256` + o relatório DOCX.
2. Iniciar o piloto (checklist §D): cota + patrocínio + pedidos em modo piloto, `AI_PROVIDER=local`,
   30 dias, rotina do guia de monitoramento; ao fim, atualizar `config/ai_economics.json` com a
   medição e regenerar `AI_COST_MODEL.md`.
3. Levar `MONETIZATION_LEGAL_MATRIX.md` (carta `ai.credits_prepaid`) a advogado(a) e contador(a) com a
   pergunta exata: "crédito pré-pago consumido por operação de software é serviço (ISS) ou
   licença/software? como se fatura, estorna e trata o crédito vencido?". Só com a resposta a regra
   pode ficar verde — e só então contratar o provedor de PIX e configurar o segredo do webhook.
4. Próxima rodada técnica (sem dependência externa): ampliar o conjunto de avaliação com casos reais
   rotulados; cache do resumo por versão de projeto; fila para lote quando houver volume; mover
   documentos SUPERADO para `history/`.
