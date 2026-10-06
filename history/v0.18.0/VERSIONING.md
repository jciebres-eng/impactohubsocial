# Versionamento

Produto: SemVer (`VERSION` = `0.18.0`; pré-1.0 = sem garantia de compatibilidade). API: prefixo `/v1`. Migrações: sequenciais, só para frente, com checksum
(migração **liberada** nunca é editada — crie a seguinte; `0005_v090_solutions.sql` foi editada em desenvolvimento porque nunca foi aplicada fora do ambiente de construção). Motores: o registro completo e versionado está em `backend/impacto/engines/registry.py` e em
`GET /v1/engines`, com teste conferindo cada versão declarada contra a constante do módulo; pesos `weights@1.0`; planos `plans@2.0`
(gravados em cada `match_run`/regra). Regras fiscais, planos e termos **não são editados**: publica-se nova versão.

**Por que 0.7.0 e não 0.6.1:** o v0.6.0 era uma referência local; o v0.7.0 troca a base de execução (PostgreSQL, auth real, portais). Mudança estrutural → MINOR.
O v0.6.0 **não foi sobrescrito**: está íntegro em `history/v0.6.0/` (com seu `MANIFEST.sha256` original).

Release: `python3 scripts/make_release.py` gera `RELEASE_MANIFEST.sha256` e `FINAL_FULL_RELEASE.zip` (sem ZIP aninhado, sem segredos, sem `node_modules`); `--verify` confere o manifesto.
Histórico: `history/v0.17.0/` (documentos do release anterior, snapshot de 31 arquivos), `history/v0.6.0/`, `history/v0.7.0/`, `history/v0.8.0/` (documentos e log de um estado **nunca empacotado**; ver `NOTE.md`) (documentos e log do release anterior, não sobrescritos). Git recomendado: tag assinada `v0.9.0`, Conventional Commits, `main` protegida.

**Por que 0.9.0:** nova capacidade grande (Biblioteca de Soluções, +60 operações, +20 tabelas) sobre o 0.8.0 → MINOR. Motores novos versionados: `intent-parser@1.0.0`, `solution-match@1.0.0`, `adaptation@1.0.0`, `combine@1.0.0`, `replicability@1.0`; pesos em `config/solution_weights.json`.

**Por que 0.10.0:** nova camada funcional (institucional) e mudança de comportamento do match (certificação verificada). `0006_v0100_institutional.sql` ainda não foi aplicada fora de ambientes de desenvolvimento e foi editada durante o desenvolvimento; após esta liberação é imutável (crie `0007`). O v0.9.0 não foi sobrescrito: documentos-chave em `history/v0.9.0/`.

**Por que 0.10.1 (PATCH):** fecha pendências do 0.10.0 sem mudar o contrato existente (adições compatíveis: rotas novas, campo `areas`, bloco extra na estimativa fiscal). `0007_v0101_institutional_extras.sql` é nova (a 0006 liberada **não** foi editada). Snapshot do v0.10.0 em `history/v0.10.0/`. A Central de Conhecimento será 0.11.0 (módulo novo ⇒ MINOR).

**Por que 0.11.0 (MINOR):** nova capacidade grande (monetização: trial, tiers, vouchers/convênios, webhooks) com mudança de comportamento (cancelar mantém acesso até o fim do período) e `0008_v0110_monetization.sql` (6 tabelas). Snapshot dos documentos do 0.10.1 em `history/v0.10.1/`; nada foi sobrescrito. Planos: `plans@1.1`.

**v0.12.0** (MINOR): nova capacidade de produto (Central de Conhecimento). Migração `0009` (ainda não liberada → editada em desenvolvimento e banco recriado; a partir da liberação, só migrações novas). Motor novo: `help-search@1.0.0` (gravado nos logs de busca). Snapshot dos documentos do v0.11.0: `history/v0.11.0/`. Configs versionadas: `config/help_synonyms.json`, `config/onboarding_paths.json` (hipóteses editoriais).

**v0.12.1** (PATCH): correções de defeito e endurecimento, sem nova capacidade de produto nem mudança de contrato da API (475 operações, mesmos campos). Migração `0010_v0121_indexes.sql` só adiciona índices — a `0009` já havia sido liberada e **não** foi editada. Snapshot dos documentos do v0.12.0: `history/v0.12.0/`.

**v0.13.0** (MINOR): nova capacidade (camada de integração) com 13 tabelas, 36 rotas e migração `0011_v0130_integration_hub.sql`. A `0010` já estava liberada e **não** foi editada; a `0011` foi editada durante o desenvolvimento (nunca aplicada fora do ambiente de construção) e a partir desta liberação é imutável. Nenhum contrato existente mudou — só adições. Snapshot dos documentos do v0.12.1: `history/v0.12.1/`. A tag `v0.12.1-final-baseline` continua sendo a baseline auditada da camada funcional; o v0.13.0 a estende sem alterá-la.

**v0.14.0** (MINOR): nova capacidade (confiança, identidade e assinatura digital) com 26 tabelas, migração `0012_v0140_trust_layer.sql` e **uma mudança de contrato**: `POST /v1/signatures` passou a exigir o campo `code` (segunda camada da assinatura). Em pré-1.0 isso cabe em MINOR, e está destacado no CHANGELOG porque quebra integração que assinava com senha apenas. A `0011` já estava liberada e **não** foi editada; a `0012` foi editada durante o desenvolvimento (nunca aplicada fora do ambiente de construção) e a partir desta liberação é imutável. Snapshot dos documentos do v0.13.0: `history/v0.13.0/`. Config versionada: `config/i18n.json` (catálogo de tradução do núcleo).

**v0.15.0** (MINOR): fecha o NÚCLEO DO PRODUTO antes da etapa de design — ideia → diagnóstico → projeto → documento → match → acompanhamento compartilhando o mesmo vocabulário de evidência, as mesmas versões e a mesma trilha. 15 tabelas novas (205 no total), 51 rotas novas (625 operações), três migrações (`0013_v0150_core_product.sql`, `0014_v0150_platform_templates.sql`, `0015_v0150_fk_indexes.sql`). A `0012` já estava liberada e **não** foi editada. Motores novos versionados: `diagnostic-engine@1.0.0`, `document-assembly@1.0.0`, `risk-rules@1.0`, `freshness@1.0`, `snapshot@1.0`; o match foi a `match-engine@1.2.0` e passou a gravar `rules_version` (`match-rules@1.1`) e `taxonomy_version` junto de motor e pesos. **Nenhum contrato existente mudou** — as 51 rotas são adições. Uma tabela foi REMOVIDA: `sdg_goals`, duplicata que nós mesmos criamos na v0.14.0, consolidada em `ods_goals` (a remoção é verificada pelo teste de caminho de atualização, que também confere que o esquema atualizado é **idêntico** ao criado do zero). Snapshot dos documentos do v0.14.0: `history/v0.14.0/`.

**Tag `v0.15.0-final-pre-design`: `TAG_PUSH_BLOCKED_BY_ENVIRONMENT`.** A tag existe **localmente** e aponta para
`67aa058`. O envio para o remoto é recusado pelo proxy do ambiente de construção com `HTTP 403` (mesmo
comportamento das tags `v0.12.1-final-baseline`, `v0.13.0-integration-baseline` e `v0.14.0-trust-baseline`). Em
substituição, o mesmo commit está publicado em dois ramos: `chore/v0.15.0-final-pre-design-hardening` (trabalho) e
`savepoint/v0.15.0-final-pre-design` (ponto de salvamento imutável por convenção). Quem tiver permissão de push de
tag pode criá-la com:

```
git tag -a v0.15.0-final-pre-design 67aa058 -m "v0.15.0 — núcleo do produto fechado, baseline técnica pré-design"
git push origin v0.15.0-final-pre-design
```

**v0.16.0** (MINOR): IMPACT NETWORK CORE — a rede de impacto, as personas e a cobrança versionada. **26** tabelas novas
(**231** no total), 79 rotas novas (**704** operações), duas migrações (`0016_v0160_impact_network.sql`,
`0017_v0160_billing_v2.sql`). A `0015` já estava liberada e **não** foi editada; as `0016`/`0017` foram editadas
durante o desenvolvimento (nunca aplicadas fora do ambiente de construção) e a partir desta liberação são imutáveis.

Motores novos versionados: `readiness@1.0.0`, `recommendation@1.0.0`. Planos: **`plans@1.2`**, com a regra comercial
desta rodada (14 dias de teste · US$ 1,99/mês nos 3 primeiros meses pagos · depois US$ 19,99/mês ou US$ 179,88/ano).

**Mudanças de contrato, declaradas:**

1. `money()` no frontend passou a receber a moeda — mudança interna do cliente, não da API.
2. `GET /v1/readiness` continua igual; a avaliação **por finalidade** ganhou rota própria
   (`/v1/readiness/purposes`) porque a anterior colidia com o padrão de caminho.
3. `monetization.quote()` devolve campos **novos** (`base_cents`, `first_cents`, `first_price_source`,
   `intro_cents`, `currency`, `tax_behavior`, `provider_configured`). Nenhum campo anterior saiu.
4. `conversations` trocou `UNIQUE(org_a, org_b)` por `ux_conv_pair_context`: o mesmo par pode ter conversas sobre
   assuntos diferentes. Conversa antiga continua válida — é relaxamento, não quebra.
5. A moeda padrão da cobrança passou de **BRL** para **USD**, por decisão comercial desta rodada. Isto **muda
   comportamento** e está destacado aqui e no CHANGELOG. Planos antigos sem versão de preço em USD continuam
   recusando contratação online em vez de inventar conversão.

**Nenhuma tabela foi removida.** As 79 rotas são adições.

**v0.17.0** (MINOR): CAMADA ECONÔMICA, LEGAL E DE PAGAMENTO. **22** tabelas novas (**253** no total), 749
operações de rota, sete migrações (`0018`–`0024`). As `0016`/`0017` já estavam liberadas e **não** foram editadas;
as `0018`–`0024` foram editadas durante o desenvolvimento (nunca aplicadas fora do ambiente de construção) e a
partir desta liberação são imutáveis. A `0023_v0170_legal.sql` é **gerada** por
`scripts/gen_legal_registry.py` a partir de `docs/legal/*.md` — editá-la à mão dessincroniza o banco dos arquivos, e
há teste que pega isso.

Planos: **`plans@2.0`**, com a regra comercial desta rodada — **o proponente não é o pagador principal** e a entrada
é gratuita de forma permanente (ADR-173). Isto **muda** a regra da v0.16.0, por decisão expressa do proprietário.

**Mudanças de contrato, declaradas:**

1. A moeda padrão da cobrança voltou de **USD** para **BRL**. Isto **muda comportamento** e está destacado aqui e no
   CHANGELOG. Foi a v0.16.0 que havia trocado para dólar; esta rodada reverte, junto com a regra comercial.
2. `GET /v1/legal/{doc}` continua no mesmo caminho e passou a servir do registro versionado, acrescentando os
   cabeçalhos `X-Legal-Status`, `X-Legal-Version` e `X-Legal-Sha256`. Nenhum campo saiu; o corpo continua Markdown.
3. `GET /v1/privacy/export` ganhou a chave `legal_acceptances`. Adição.
4. `GET /v1/admin/payments/revenue` nasce nesta versão e já traz `provider_configured`,
   `total_real_paid_cents_by_currency` e o bloco `subscriptions` em separado.
5. `billing_events` ganhou o estado `rejected_signature` e as colunas `signature_verified`, `charge_id` e
   `duplicate_count`. O webhook da v0.11.0 continua respondendo 200 para evento válido e passou a responder **202
   `rejected_signature`** quando `process_event` é chamado por um caminho que não conferiu a assinatura.
6. `notification_prefs` ganhou o grupo `program` (15 grupos).

**Nenhuma tabela foi removida.** As rotas novas são adições.

Snapshot dos documentos do v0.16.0: `history/v0.16.0/`.

Snapshot dos documentos do v0.15.0: `history/v0.15.0/` (28 arquivos, com `NOTE.md` explicando que a v0.16.0 mudou
contagens de tabela, de rota e de teste, e a regra comercial para dólar).

**Datas de produto são UTC** a partir desta versão (`backend/impacto/clock.py`), com teste de arquitetura. Antes
disso, `date.today()` usava o fuso local do processo — o que, num contêiner em UTC-4, gravava o dia anterior durante
algumas horas de cada dia.
