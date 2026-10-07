# Motor de compatibilidade — especificação v0.1

## Quatro saídas separadas (nunca fundidas)
1. **Elegibilidade** (determinística): `eligible | blocked | needs_review`.
2. **Compatibilidade** (0–100) ou `insufficient_data`.
3. **Confiança dos dados** (% de campos críticos com evidência vigente + origem).
4. **Estado recomendado:** prioritária · compatível · potencial com lacunas · revisão humana · bloqueada.

## Hard blockers
Cada bloqueio grava: regra, versão, evidência, data, origem. Exemplos: chamada encerrada; território obrigatório incompatível; entidade fora da definição; valor fora de faixa inegociável; conflito não resolvido; impedimento confirmado por fonte + política aprovada; documento obrigatório inválido. **Sinal incerto → `needs_review`, nunca bloqueio.**

## Soft criteria (pesos padrão, hipótese — `config/match_weights.default.json`)
Causa/objetivo 20 · território 15 · orçamento/ticket 15 · mecanismo/programa 15 · capacidade/prontidão 10 · evidência/indicadores 10 · preferência do financiador 5 · cronograma/urgência 5 · risco operacional residual 5. Pesos configuráveis **por programa**, versionados com `criteria_version`; sem otimização automática.

## Fórmula
`score = Σ (peso_i × nota_i[0..1]) × fator_de_evidência`, arredondado só na interface. Dado obrigatório ausente → intervalo ou `insufficient_data` (sem nota fictícia). Compliance é porta de entrada, **não** compensável por afinidade.

## Explicação (obrigatória)
2–3 fatores positivos · 1–3 lacunas · como melhorar · versão do motor/critérios · data. **Why this match / Why not / Risks / Missing information / Next action.** Nunca exibir % sem critérios e versão.

## Invariantes
- Não recebe como entrada: plano, assinatura, voucher, pagamentos, tier do usuário (ADR-008).
- Não usa atributos sensíveis (raça, religião, saúde individual etc.).
- Ordena apenas dentro do programa configurado; decisão final humana.
- Cada execução é um `match_run` imutável e reproduzível (mesmos inputs + versões = mesmo resultado).

## Avaliação
Conjunto sintético + conjunto consentido/de-identificado; comparar com decisões justificadas de avaliadores; auditar viés por porte, território, causa; acompanhar distribuição da shortlist.

## Casos de teste obrigatórios
OSC válida/irregular; documento expirado; conflito de interesse; empresa elegível/não elegível; combinação forte/fraca; hard blocker; dado ausente; **mesma OSC com e sem voucher/plano → resultado idêntico**.
