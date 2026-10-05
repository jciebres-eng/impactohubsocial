# Plataforma de Impacto Social — Pacote de Documentação v0.1

**Estado:** DOCUMENTAÇÃO (checkpoint v0.1, 2026-10-04). **Não há software, build, testes de código nem publicação neste pacote.**

## O que é o produto (decisão vigente)
SaaS B2B (web/PWA primeiro) para gestão de programas de investimento social e grants: descoberta curada, due diligence, aprovação, evidências e prestação de contas, conectando **Empresas/Financiadores**, **OSCs** e **Prestadores de serviço**. O "match" é um recurso explicável, não um swipe automático. Sem custódia de dinheiro de aportes no MVP.

## Premissas comerciais deste pacote
1. O produto **será vendido** (SaaS por assinatura + implantação).
2. O proprietário **emite vouchers** (desconto ou gratuidade); **OSCs (e demais perfis) resgatam no site**. Ver `docs/VOUCHERS.md`.
3. **Três tipos de usuário** (Empresa, OSC, Prestador) com **acesso geral** a algumas áreas e **recursos VIP/premium por assinatura**. Ver `docs/PLANS_AND_ENTITLEMENTS.md`.
4. **Exceção:** o **escalonamento/posição/nível dos perfis de prestadores NUNCA é vendido** nem depende de plano ou voucher. Ver `docs/PROVIDERS.md`.
5. Regra global: **nenhum plano ou voucher altera elegibilidade, score, ordenação ou visibilidade no match.**

## Mapa do pacote
| Arquivo | Conteúdo |
|---|---|
| `CHECKPOINT_v0.1.md` | Estado exato, o que existe, o que falta, como retomar |
| `NEXT_STEPS.md` | Prompt de continuação + fila de tarefas priorizada |
| `VERSIONING.md` / `CHANGELOG.md` / `DECISIONS.md` | Versionamento, histórico, registro de decisões (ADR) |
| `RELEASE_AUDIT.md` | Auditoria GREEN/YELLOW/RED honesta |
| `docs/` | Produto, arquitetura, dados, API, match, fiscal, IA, segurança, LGPD, ledger, negócio, planos, vouchers, prestadores, deploy, mobile/web, testes, admin, guia, roadmap, PI, dependências, publicação, rastreabilidade |
| `config/` | Matriz de planos/direitos e pesos padrão do match (JSON, versionados) |
| `database/draft/` | Esquema SQL **rascunho, não executado** |
| `scripts/make_release.py` | Gera manifesto SHA-256 e o zip |
| `sources/` | Estratégia original (PDF Manus AI) |

## Ordem de leitura
`CHECKPOINT_v0.1` → `DECISIONS` → `docs/PRODUCT` → `docs/PLANS_AND_ENTITLEMENTS` → `docs/VOUCHERS` → `docs/ARCHITECTURE` → restante.

## Aviso
Nada aqui é parecer jurídico, fiscal ou contábil. Itens que exigem validação profissional estão marcados **[VALIDAR]**.

## Atualização v0.3

Este pacote agora inclui um **MVP local executável** em `src/impacto/app.py` e um painel em `web/`. Consulte `docs/LOCAL_MVP.md` para os fluxos implementados, execução, credenciais de demonstração e limitações. O status de produção permanece bloqueado até concluir os itens externos e de segurança descritos em `FINAL_RELEASE_AUDIT.md`.

### API

- Código: `src/impacto/app.py`
- Contrato OpenAPI: `openapi.yaml`
- Documentação dos endpoints implementados: `docs/API_IMPLEMENTED.md`


## Handoff v0.6 para Claude
Esta release foi endurecida após revisão independente do pacote v0.5. Ela deve ser tratada como uma base de referência e não como prova de produção. O próximo agente deve comparar o código real com a documentação e substituir o MVP local por arquitetura de produção, mantendo o que estiver comprovadamente correto.
