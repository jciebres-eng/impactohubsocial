# LIMPEZA v0.28.0 — o que saiu, o que ficou e por quê

Regra: remover só o que não serve mais E cuja remoção é provada segura pela suíte (nenhum teste enfraquecido);
tudo o mais fica, com o motivo escrito. Classificação: **REMOVIDO**, **MOVIDO**, **UNIFICADO**, **MANTIDO**.

| Item | Classificação | Motivo / prova |
| --- | --- | --- |
| `V0.15.0…V0.21.0_FINAL_MANIFEST.json`, `FINAL_TRUST_MANIFEST.json`, `FINAL_INTEGRATION_MANIFEST.json`, `FINAL_MONETIZATION_RELEASE_MANIFEST.json`, `IMPACTO_v0.23.0…v0.27.0_TRACEABILITY.json` (19 arquivos, 5,3 MB na raiz) | **MOVIDO** → `history/manifests/` | registros de versões anteriores que poluíam a raiz; conteúdo intacto (histórico é imutável); `scripts/make_release.py` (REQUIRED) e `make_version_manifest.py` atualizados; `test_v0230_release_gate` continua lendo só o manifesto da versão corrente na raiz |
| `ai_credit_consume()` (0058) | **UNIFICADO** | virou invólucro de `ai_credit_consume_bucket()` (0068): uma implementação de consumo atômico; `test_v0230_ai_governance` (atomicidade, idempotência, concorrência) continua verde |
| Cota fixa `ai_requests_month` nos pacotes | **MANTIDO** | é teto de CHAMADAS do pacote de capacidades (ADR-331); a cota de CRÉDITOS é outra régua. Remover mudaria o contrato dos pacotes sem pedido |
| Documentos SUPERADO da assinatura (`BILLING_V2`, `TRIAL_SYSTEM`, `FULL_FREE_2026`, `COMMERCIAL_TERMS`, `docs/billing.md`, `docs/BUSINESS_MODEL.md`, `BILLING_ARCHITECTURE`, `MONETIZATION_ARCHITECTURE`, `COMMERCIAL_UX_SPEC`, `DESIGNER_HANDOFF_MONETIZATION`, `BILLING_SECURITY`) | **MANTIDO** (com banner SUPERADO) | referenciados por 60+ documentos/manifestos históricos e por `make_release.REQUIRED`; mover quebraria rastreabilidade de versões anteriores. Candidatos a `history/superseded/` numa rodada dedicada, com atualização de referências |
| Vouchers de desconto (`percent_off`/`amount_off`) no código | **MANTIDO** (aposentados, resgate recusa 409) | linhas históricas no banco; a recusa explícita é melhor que um 500 |
| Tela `/ia` antiga (`PainelDeIa`: orçamento em dinheiro, política de risco) | **MANTIDO** em `/ia/orcamento` | continua sendo o único lugar do orçamento em dinheiro e da leitura da política por faixa |
| `services/billing.py`, `test_v0160_billing.py` | já REMOVIDOS na v0.27.0 | — |
| Código morto / flags sem leitor / funções sem chamador | **nenhum encontrado** | `test_v0200_cleanup` (NoDeadCodeReturnsTests, FlagsAndInvariantsAreRealTests) verde |
| Diretórios de evidência antigos (`docs/evidence/*_v0240`, `telas_v0260`, logs de regressão) | **MANTIDO** | evidência é histórico; o empacotador inclui `.log` versionados desde a v0.27.0 |
| `backend/.tmp_entry_storage*` | **REMOVIDO** do disco antes do pacote (não versionado) | lixo de execução de teste |

O que NÃO foi feito: apagar tabelas ou colunas aposentadas (migrações são forward-only; `legacy_subscription_archive`
continua guardando o que caiu na v0.27.0); mover documentos SUPERADO (ver acima).
