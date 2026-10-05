# STORE_READINESS — prontidão para camada de design, implementação web e publicação em lojas (v0.12.0)

Avaliação honesta (GREEN = provado por teste/execução; YELLOW = código pronto, falta ação externa ou validação; RED = ausente).

| Item | Estado | Evidência / o que falta |
|---|---|---|
| API estável e documentada (475 operações, OpenAPI) | GREEN | `docs/API.md`, `docs/openapi.json`; 357 testes verdes |
| Frontend web/PWA (React + build esbuild) | GREEN | `tsc` + build; E2E Chromium (8 testes web+Central). **Sem axe/leitor de tela, sem teste cross-browser** (YELLOW) |
| **Camada de design** | YELLOW | UI funcional com tokens CSS próprios (`styles.css`); **não há design system formal, nem identidade visual aprovada, nem protótipos**. As páginas novas usam as classes existentes — um redesign deve trocar tokens/componentes de `ui/kit.tsx` sem tocar na lógica |
| Responsividade/acessibilidade básica | YELLOW | menu móvel, foco visível, `aria-*`, skip-link, rótulos; verificação própria apenas |
| Apps Android/iOS (Capacitor) | YELLOW (CODE READY) | `mobile/setup.sh`; **nunca compilados, assinados nem enviados**; exige macOS+Apple Developer (iOS), keystore e conta Play (Android) |
| Requisitos de loja (política de privacidade, exclusão de conta, rótulos de dados) | YELLOW | exclusão de conta e exportação existem; **textos legais são minutas sem revisão jurídica**; formulários de “Data safety”/App Privacy não preenchidos |
| Pagamentos in-app/assinatura nas lojas | RED/decisão | cobrança é Stripe (web); regras de compra dentro do app (Apple/Google) **não foram analisadas** — decisão do proprietário |
| Provedores reais (Stripe, SMTP, antivírus, S3, IdP) | YELLOW | só dublês nos testes |
| Conteúdo real (Central, Biblioteca, regras fiscais) | RED | só exemplos `demo`; nenhuma regra fiscal aprovada |
| Preços, nota fiscal | RED | planos sem preço; sem emissão de NF |
| Auditoria de dependências (npm/pip) | YELLOW | **não executada aqui**: o registro npm bloqueou a criação do lockfile (HTTP 403) e `pip-audit` não pôde ser instalado. Rodar `npm i --package-lock-only && npm audit` e `pip-audit -r backend/requirements.txt` em CI |
| Pentest, carga concorrente, DR | YELLOW | ver `PRODUCTION_READINESS.md` |

**Conclusão:** o produto está pronto para **receber a camada de design e para homologação/piloto**. **Não está pronto para publicação nas lojas** — faltam builds assinados, decisões de monetização nas lojas, revisão jurídica e conteúdo oficial.
