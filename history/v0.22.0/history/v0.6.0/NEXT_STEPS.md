# Próximos passos e prompt de continuação

## Fila priorizada
1. Proprietário confirma as 4 hipóteses de `CHECKPOINT_v0.1.md`.
2. Escolher nome/domínio, território e causa do piloto, comprador âncora.
3. Contratar revisão jurídica/contábil: termos, privacidade, termos de voucher, gratuidades, cobrança, rede de prestadores.
4. **Fase 1 de código** (monorepo TS): `packages/match-engine`, `packages/entitlements`, `packages/vouchers`, `packages/ledger`, `packages/fiscal-rules` (esquema, sem regras ativas) + testes + `schema` executado em Postgres descartável.
5. API, auth/tenancy/RLS, web/PWA, admin, billing sandbox, IA, CI/CD.
6. Identidade visual.

## Prompt para colar numa nova conversa (anexe o zip)
> Retome o projeto "Plataforma de Impacto Social" a partir do checkpoint v0.1 anexo. Leia `CHECKPOINT_v0.1.md`, `DECISIONS.md` e `RELEASE_AUDIT.md` primeiro. Premissas: produto será vendido; vouchers de desconto/gratuidade emitidos pelo proprietário e resgatados no site; planos Básico/Premium por papel (Empresa, OSC, Prestador); escalonamento/posição de prestadores nunca é vendável; nenhum plano/voucher afeta match. Execute a Fase 1 de código (itens 4 de `NEXT_STEPS.md`), com testes que realmente rodem, e atualize `CHANGELOG`, `RELEASE_AUDIT` e gere o checkpoint v0.2. Não declare nada como pronto sem teste executado.
