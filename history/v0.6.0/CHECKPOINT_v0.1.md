# Checkpoint v0.1 — 2026-10-04

## Estado em uma frase
Documentação-base completa e coerente; **zero software implementado**.

## Feito
- Escopo de produto reconciliado entre o prompt mestre e o relatório Manus AI (ver `DECISIONS.md`).
- Modelo comercial: assinatura + vouchers + implantação, com direitos por plano e papel.
- Especificações: match, fiscal, IA, segurança, LGPD, ledger, dados, API.
- Rastreabilidade das 39 seções do prompt mestre (`docs/REQUIREMENTS_TRACEABILITY.md`).

## Não feito (RED)
Código, banco real, autenticação, API, front, admin, testes, CI/CD, billing real, apps nativos, publicação, regras fiscais verificadas, pareceres jurídicos.

## Hipóteses que precisam de confirmação do proprietário
1. "Exceto o escalonamento dos perfis de prestadores" foi interpretado como: **posição, destaque, selos e níveis de prestadores não são comercializáveis e não variam por plano/voucher** (ADR-007). Confirme.
2. Seguir a linha do relatório Manus (SaaS B2B, PWA, sem pagamentos de aporte) em vez do marketplace/swipe/nativo do prompt (ADR-001..003). Confirme.
3. Premium para OSC e Prestador existe no modelo, mas fica **atrás de feature flag** no piloto (ADR-009). Confirme.
4. Valores de preço e limites numéricos em `config/` são **placeholders**.

## Pendências externas
Jurídico/contábil (itens **[VALIDAR]**), comprador âncora e território do piloto, escolha de cloud/gateway, nome/marca (busca INPI), domínio.

## Como retomar
Abra `NEXT_STEPS.md`, cole o prompt de continuação em nova conversa e anexe o zip.
