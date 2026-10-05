# Rastreabilidade — prompt mestre (39 seções) × este pacote

| Seção do prompt | Onde está | Estado |
|---|---|---|
| 1 Auditar tudo / 4 Análise | `DECISIONS`, `RELEASE_AUDIT` | Doc |
| 2–3, 5 Visão/Produto/PMF | `PRODUCT`, `BUSINESS_MODEL` | Doc |
| 6 Match | `MATCH_ENGINE`, `config/match_weights` | Doc |
| 7 IA | `AI` | Doc |
| 8 Fiscal | `FISCAL_ENGINE` | Doc (regras não verificadas) |
| 9 Compliance | `PRODUCT`, `LGPD` | Doc |
| 10 Ledger | `IMPACT_LEDGER` | Doc |
| 11–13 OSC/Empresa/Feed | `PRODUCT` | Doc |
| 14, 26 Dashboards/Admin | `ADMIN` | Doc |
| 15 Monetização | `BUSINESS_MODEL`, `PLANS_AND_ENTITLEMENTS`, `VOUCHERS` | Doc |
| 16, 30 Arquitetura/anti lock-in | `ARCHITECTURE` | Doc |
| 17–18 Segurança/LGPD | `SECURITY`, `LGPD` | Doc |
| 19–22 Qualidade/Testes/Perf/A11y | `TESTING`, `MOBILE_AND_WEB` | Doc |
| 23 Design | **não coberto** (identidade visual pendente) | RED |
| 24–25 Mobile/Web | `MOBILE_AND_WEB` | Doc |
| 27–28 Observabilidade/CI-CD | `DEPLOYMENT` | Doc |
| 29 PI | `IP_REGISTER` | Doc |
| 31–32 Estrutura/Documentação | este pacote (parcial: faltam `FINAL_RELEASE_AUDIT` de código) | Parcial |
| 33–34 Release audit/Pronto | `RELEASE_AUDIT` | Doc |
| 35 Publicação | `PUBLISHING_CHECKLIST` | Doc |
| 36 Empacotamento | `scripts/make_release.py` (zip de documentação) | Parcial |
| 37–39 Autonomia/Regra de ouro | `DECISIONS` | — |
**Novos requisitos do proprietário (esta sessão):** venda, vouchers, planos por papel, exceção de prestadores → ADR 004, 007–010; `PLANS_AND_ENTITLEMENTS`, `VOUCHERS`, `PROVIDERS`.
