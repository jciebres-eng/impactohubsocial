# Compras, cotações e benchmark (v0.8.0)

Código: `services/procurement.py`, tabelas `procurement_policies`, pedidos de compra e cotações (migração 0004).
- **Política configurável por organização** (padrão: 3 cotações, limite de valor, desvio máximo 30% da mediana, exceção exige segunda aprovação).
- **Benchmark**: mediana como referência (robusta a extremos), média, mín/máx, desvio, amplitude; `comparable` só com ≥ 3 cotações.
- **Sinal "preço possivelmente fora do padrão"** — nunca "fraude". Exceção à política exige justificativa e 2ª aprovação; vínculo despesa ↔ compra.
- Integra com risco (`price_outlier`, `quotes_below_policy`) e com a prestação de contas.
**Não é** base de preços de mercado nem validação de orçamento; compara apenas as cotações do próprio pedido.
