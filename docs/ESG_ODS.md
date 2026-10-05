# ESG / ODS / impacto — o que existe e o que não existe

## Existe
- **ODS 1–17** como lista (`ods smallint[]`) em organizações, projetos, editais e perfis de financiador; entram no match (sinal ODS).
- **Causas** (taxonomia em `config/taxonomy.json`) e **indicadores do projeto** (`indicators jsonb`: nome, unidade, linha de base, meta) + **resultados informados** em devolutivas.
- **Impact Ledger** (aportes, despesas, evidências aceitas, marcos) com cadeia de hash; **relatório do projeto** e **CSV de despesas**.
- Estatísticas territoriais agregadas para governo (k-anonimato).

## Não existe (RED)
Metas e indicadores oficiais ODS normalizados (ODS_TARGET/INDICATOR) · Impact Graph (relações entre ODS, co-benefícios, hipóteses de causalidade) · dimensões/indicadores ESG estruturados (hoje “ESG” = causas/ODS e preferências do financiador) · determinantes sociais estruturados · relatórios ESG/GRI específicos · metodologia de medição de impacto.

## Princípio de verdade (aplicado)
O sistema mostra **valores informados** pela OSC e **status de revisão** do financiador; não calcula “impacto” nem afirma causalidade. Relatórios usam termos como “indicadores reportados” e “evidência aceita”, nunca “ESG compliant”. Dados demonstrativos são marcados “[EXEMPLO FICTÍCIO]”.
Populações vulneráveis: beneficiários são contagens agregadas; não há ranking de pessoas nem de “vulnerabilidade”; o match prioriza compatibilidade de causa, território, orçamento e prontidão.

## Atualização v0.9.0
Soluções carregam `ods[]` e `esg[]`; o tesauro mapeia conceitos para ODS/ESG (sugestão **declarada**, não validada). Visão "por ODS" usa contagens agregadas. Continua válido: alinhamento declarado ≠ com evidência; metas oficiais ODS **não** embutidas.
