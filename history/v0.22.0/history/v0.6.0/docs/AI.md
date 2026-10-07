# Camada de IA

## Interface
`AiProvider { extract(doc, schema) ; classify(text, taxonomy) ; summarize(text, cites) ; draft(prompt, sources) ; embed(text) }` — implementações trocáveis; gateway aplica redaction de PII, limites de custo, logging sem conteúdo sensível, versionamento de prompt/modelo, fallback sem IA.

## Usos permitidos
OCR/extração (rascunho com fonte/página e confiança por campo); classificação de causa/território com taxonomia; divergência cadastro×documento; resumo com citações; assistente de escrita que não altera fatos; copiloto que redige minuta a partir de evidências já validadas; busca semântica; **explicações do motor determinístico**.

## Usos proibidos
Aprovar/declarar regularidade de OSC; decidir elegibilidade legal/fiscal; afirmar dedutibilidade; atribuir fraude sem prova; classificar beneficiários por vulnerabilidade; inventar indicadores/evidências; escrever ou assinar parecer/prestação de contas; liberar pagamento; **influenciar ranking de prestadores ou match por plano**.

## Controles
Saída marcada "rascunho assistido"; confirmação humana; documento tratado como dado não confiável (anti prompt-injection; IA sem ferramentas de escrita); avaliação por amostra rotulada; viés por porte/território/causa; botão corrigir; cota por plano (quota de uso é direito de plano, qualidade do resultado é igual).

## Governança
NIST AI RMF (Governar/Mapear/Medir/Gerenciar) como referência voluntária; contrato do provedor com não-retenção/não-treino quando possível **[VALIDAR]**.
