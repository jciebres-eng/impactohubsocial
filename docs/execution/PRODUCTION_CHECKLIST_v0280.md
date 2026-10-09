# Checklist de validação de produção — v0.28.0

Estado de cada item nesta instalação de referência (sem produção): **FEITO** (provado por teste ou
execução registrada), **PENDENTE DO PROPRIETÁRIO** (credencial, conta, parecer, decisão) ou
**PENDENTE DO PILOTO** (só a medição real responde). Nada aqui foi marcado FEITO por suposição.

## A. Antes de subir a v0.28.0

| # | Item | Estado | Como conferir |
|---|---|---|---|
| A1 | Backup da base anterior guardado fora do host (`pg_dump -Fc`) | PENDENTE DO PROPRIETÁRIO | `docs/execution/ROLLBACK_v0280.md` §0 |
| A2 | Migração 0068 aplicada do zero e sobre cópia da v0.27.0 com ROLLBACK (dry-run) | FEITO | suíte (`tests/support`) e `impacto_m68`; `test_v0230_data_infra_gate` (nenhum DROP) |
| A3 | Regressão completa verde (2ª passagem) e portões de fechamento | FEITO | `docs/evidence/test_run_v0.28.0.log`; `FINAL_EXECUTION_REPORT.md` §24 |
| A4 | CI do GitHub (auditoria, backend, docker, pilha-do-zero) verde no commit final | FEITO (`ff31622`, run `37884629991`, 4/4 verdes) | `FINAL_EXECUTION_REPORT.md` §3 |
| A5 | Pacote confere byte a byte com o git; sem segredo; sem ZIP aninhado | FEITO no fechamento | `verify_package_against_git.py`, `secrets_scan.py`, `unzip -t` |
| A6 | Tag `v0.28.0` no commit de fechamento | PENDENTE DO PROPRIETÁRIO (proxy recusa push de tag) | GitHub → Releases |

## B. Configuração de ambiente (nenhum valor no repositório)

| # | Variável / item | Estado | Regra |
|---|---|---|---|
| B1 | `AI_PROVIDER` | PENDENTE DO PROPRIETÁRIO (padrão `local`) | `local` para o piloto sem custo externo; `anthropic`/`openai_compatible` só com `AI_API_KEY`, `AI_MODEL` e **preço cadastrado em `ai_price_table`** — sem preço, o custo externo fica NÃO MEDIDO (nunca zero) |
| B2 | `AI_API_KEY` | PENDENTE DO PROPRIETÁRIO | só por ambiente/segredo do host; nunca no navegador, nunca no git; conta de API da plataforma (a assinatura Claude.ai de ninguém paga isto — `AI_PROVIDERS_EVALUATION.md` §1) |
| B3 | `PAYMENT_WEBHOOK_SECRET` | PENDENTE DO PROPRIETÁRIO (vazio = webhook 404) | só quando houver provedor de PIX; segredo do provedor, rotacionável |
| B4 | Regra `ai.credits_prepaid` | **inativa** (padrão) — PENDENTE DO PARECER | ativar só com parecer jurídico/contábil registrado em `monetization_legal_cards` (carta verde) e provedor configurado; até lá pedidos são só de piloto |
| B5 | Preços de pacote e de operação | hipóteses (`status = hypothesis`) — PENDENTE DO PILOTO | substituir por versão `active` via `POST /v1/admin/ai/credit-packs` e `/operations` (`finance.approve`) depois da medição |
| B6 | Cotas (`welcome.v1` 60, `monthly.light.v1` 10) e teto de subsídio (R$ 500/mês, hipótese) | PENDENTE DO PILOTO | `PUT /v1/admin/ai/quota-policies/{key}`; teto em `config/ai_economics.json` |
| B7 | `PLATFORM_PIX_KEY`, aceite de termos (minutas), hospedagem, SMTP e demais itens da v0.27.0 | PENDENTE DO PROPRIETÁRIO | `EXTERNAL_INTEGRATIONS.md` |

## C. Fumaça após subir (10 minutos, com uma organização de teste)

| # | Passo | Esperado | Estado |
|---|---|---|---|
| C1 | `GET /readyz` | `status = ready`, `billing = none-subscription`, `ai` = provedor configurado, sem `pending_migrations` | FEITO na pilha do zero (CI) |
| C2 | Entrar como OSC → `/ia` | saldo promocional 60 (boas-vindas, uma vez por pessoa e por organização), operações com preço e "quem paga", nenhum preço marcado como vigente | FEITO (`test_e2e_v0280_ai_center`) |
| C3 | Ficha de um projeto publicado → "Originalidade, similaridade e complementaridade" → prévia | diálogo diz custo, fonte, saldo, critério de conclusão e "se falhar, nada é cobrado" | FEITO (E2E) |
| C4 | Confirmar | análise por dimensões, leituras separadas, recomendações, aviso de limite; extrato debita exatamente os créditos reservados | FEITO (E2E + `test_v0280_ai_usage_control`) |
| C5 | Repetir com os mesmos insumos | `funding = cached`, nenhum débito | FEITO |
| C6 | Contestar a análise | registrada; aparece em `GET /v1/admin/ai/disputes` | FEITO |
| C7 | Sem saldo → prévia | 402 `ai_funding_required` com opções (pedido de crédito em modo piloto, patrocínio); nada executa | FEITO |
| C8 | Pedido de crédito (modo piloto) → aprovação por `billing.write` com confirmação de identidade | crédito PROMOCIONAL; "Receita recebida" continua R$ 0,00 | FEITO (E2E) |
| C9 | `POST /v1/webhooks/payments/pix` sem segredo configurado | 404 `webhook_not_configured`; nada creditado | FEITO |
| C10 | `/admin/ia/financeiro` | medido × NÃO MEDIDO explícitos; alertas; nenhum número estimado | FEITO |
| C11 | Outra organização tenta ler execuções/créditos/análises da primeira | 404/403; sobreposição só como contagem k ≥ 3 | FEITO |

## D. Piloto (antes de qualquer cobrança real) — passos 1–6 do proprietário

| # | Passo | Estado | Evidência exigida |
|---|---|---|---|
| D1 | Rodar com cota + patrocínio + pedidos em modo piloto por um ciclo (sugestão: 30 dias) | PENDENTE DO PILOTO | painel semanal exportado (`AI_COST_MONITORING_GUIDE.md` §3) |
| D2 | Medir custo real por operação (provedor, se houver; CPU local) e comparar com `config/ai_economics.json` | PENDENTE DO PILOTO | `ai_executions` agregado; `AI_COST_MODEL.md` regenerado |
| D3 | Medir uso da cota × teto de subsídio | PENDENTE DO PILOTO | modelo §3 recalculado com medição |
| D4 | Ampliar o conjunto de avaliação da similaridade com casos reais rotulados (inclusive contestações revisadas) e recalcular precisão/recall | PENDENTE DO PILOTO | `docs/evidence/similarity_eval_v0280.json` com mais de 6 casos |
| D5 | Decidir preços (pacotes, operações) e cotas definitivas | PENDENTE DO PROPRIETÁRIO | versões `active` publicadas no catálogo |
| D6 | Parecer jurídico/contábil da regra `ai.credits_prepaid`; contratar provedor de PIX; configurar `PAYMENT_WEBHOOK_SECRET`; ativar a regra | PENDENTE DO PROPRIETÁRIO | carta verde; `test_v0280_ai_usage_control` continua verde com a regra ativa (`WebhookWithSecretTests` simula exatamente esse estado em teste) |

## E. O que esta lista NÃO afirma

Que o sistema é "100% impossível de invadir"; que há provedor de pagamento, provedor de modelo,
NFS-e, BYOK ou venda real de créditos; que as hipóteses de preço são preços.
