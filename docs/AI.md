# IA — arquitetura provider-agnostic (v0.7.0)

Código: `backend/impacto/engines/ai/gateway.py` (gateway) e `local.py` (regras locais). Rotas: `api/ai_routes.py`.

## Provedores (`AI_PROVIDER`)
| Valor | Comportamento |
|---|---|
| `local` (padrão) | regras determinísticas offline (extração de necessidade → orçamento, modelos de rascunho com `[COMPLETAR]`, resumo extrativo, classificação de documento por palavras-chave). **Nada sai do servidor.** |
| `anthropic` | Messages API (`anthropic-version: 2023-06-01`), modelo em `AI_MODEL`, chave em `AI_API_KEY` |
| `openai_compatible` | `/v1/chat/completions` em `AI_BASE_URL` |
| `disabled` | endpoints respondem 503 `ai_disabled` |
Nenhum nome de modelo ou chave está no código.

## Capacidades implementadas
1. **Estruturar necessidade** (texto livre → título, resumo, itens de orçamento, perguntas de lacuna).
2. **Rascunhos de documentos** (plano de trabalho, justificativa, carta, relatório…) a partir de dados reais do projeto/edital.
3. **Resumo do projeto** para financiador.
4. **Classificação de documento** (tipo provável) para organizar o cofre.
Fora de escopo hoje: OCR de produção, visão computacional, embeddings, moderação, copilotos conversacionais.
(Pytesseract existe no ambiente de build, mas não está ligado ao fluxo.)

## Controles
| Controle | Como |
|---|---|
| Cota | `ai_requests_month` do plano; excedido → 402 `ai_quota_exceeded` |
| Privacidade | antes de enviar a provedor externo, redação por padrões de CPF, e-mail, telefone, CEP e RG; limite `AI_MAX_INPUT_CHARS` |
| Log | `ai_usage`: feature, provedor, modelo, status, tamanhos, tokens, latência, **SHA-256 da entrada** (nunca o texto) |
| Timeout/retry | `HttpClient` (timeout `AI_TIMEOUT_SECONDS`, 2 retries) |
| Fallback | falha do provedor externo → resultado local + registro `local-fallback` |
| Resposta inválida | JSON externo inválido é descartado; o motor local prevalece |
| Rotulagem | toda saída vem com `draft: true`, `human_review_required: true` e `engine` |
| Anti-alucinação | prompt de sistema proíbe inventar números/fontes/leis e exige `[COMPLETAR: …]`; a IA **não decide** elegibilidade, não aprova, não assina, não envia |

## Revisão humana e assinatura
Rascunho (`drafts`) → `professional_reviews` → decisão do profissional → `signatures` (append-only, com credencial verificada:
conselho, número, UF) . A assinatura aqui é **registro de conferência pela plataforma**; **não é** assinatura digital ICP-Brasil
(ADR em `DECISIONS.md`) — valor jurídico a validar com advogado se o edital exigir ICP.

## Testes
`test_api_features.py` (cota, rascunho, revisão), `test_unit.py` (redação, extração). **Provedores externos testados só com servidor HTTP falso** — nenhuma chamada real a Anthropic/OpenAI foi feita.

## Biblioteca de Soluções (v0.9.0)
A busca e o copiloto **não chamam IA**; ver `AI_SEARCH_ARCHITECTURE.md` (o que existe, o que não existe, slot de LLM restrito ao tesauro).
