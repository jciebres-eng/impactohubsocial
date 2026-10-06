"""Camada econômica do produto (v0.17.0).

Esta camada existe porque a auditoria (`SAAS_ECONOMIC_AUDIT.md`) encontrou uma lacuna conceitual, não
um defeito de código: o produto media **uso** (`ai_usage`, limites de plano) e cobrava **acesso**
(assinatura por organização), mas não registrava em lugar nenhum **quanto trabalho ele evitou**. Sem
isso não há ROI demonstrável e a venda institucional fica sem lastro.

A ordem dos módulos é a ordem da cadeia que os documentos desta rodada exigem, e ela é deliberadamente
mais longa que `valor → cobrança`:

    evento de valor  →  regra de elegibilidade  →  regra de monetização  →  validação jurídica  →  cobrança
    (value_ledger)      (billable)                (billable)               (legal)                (billing)

Cada seta é uma recusa possível. Um evento de valor **não** produz cobrança: produz um candidato, que
só vira cobrança se houver regra ativa e essa regra estiver marcada como juridicamente validada. A
trava é no banco, não na disciplina de quem escreve a rota.

`programs` é produto, não cobrança — está aqui porque é a unidade de valor que o cliente institucional
administra, e é sobre ela que a maior parte dos eventos de valor acontece.
"""
