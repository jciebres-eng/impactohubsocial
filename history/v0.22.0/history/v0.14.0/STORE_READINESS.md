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

## Atualização v0.12.1
- **Acessibilidade:** contraste AA corrigido e agora verificado automaticamente (claro e escuro); rótulos, foco, cabeçalhos, IDs e ausência de rolagem horizontal a 390 px provados em 25 combinações de página/viewport. **Ainda falta** axe e leitor de tela.
- **Auditoria de dependências:** tentada e **bloqueada** neste ambiente (`npm install --package-lock-only` → 403 do registry; `pip install pip-audit` → “no matching distribution”). Sem lockfile não há `npm audit`. **Obrigatório rodar em CI antes de publicar.** Dependências de execução são pinadas em `backend/requirements.txt` e `web/package.json`.
- **Jornadas de navegador** agora incluem logout, área bloqueada por perfil, página Plano (voucher + cancelamento) e administração com MFA — o fluxo de cobrança deixou de ser “só API”.
- **Conclusão inalterada:** pronto para a camada de design e para piloto; **não** pronto para publicação nas lojas (builds assinados, regras de compra das lojas, revisão jurídica e conteúdo oficial continuam pendentes).

## v0.13.0 — efeito nas lojas
A camada de integração **não muda nada do ponto de vista das lojas**: não há tela, não há SDK de terceiro no app, não há nova permissão de dispositivo e nenhum dado novo é coletado do aparelho. Continuam valendo os bloqueios já listados: apps não construídos nem assinados, sem conta de desenvolvedor, sem política de privacidade publicada em domínio próprio.
Quando a integração ganhar tela, a política de privacidade precisará declarar o **compartilhamento com terceiros** que a organização configurar (ver `LGPD_AUDIT.md` — base legal por assinatura).

## v0.14.0 — efeito nas lojas
Duas coisas passam a importar para a revisão das lojas:
1. **Verificação pública é uma tela sem login** dentro do app. Isso é permitido (é consulta de autenticidade, não conteúdo
   gerado por terceiro), mas a descrição da loja deve dizer o que a tela faz, para não parecer funcionalidade oculta.
2. **Envio de documento de identidade** no fluxo de identificação. Apple e Google exigem, na ficha do app, declarar a
   coleta de "Identifiers"/"Sensitive info" e apontar a política de privacidade. A política precisa descrever: o que é
   guardado (referência ao arquivo e resultado da conferência), o que **não** é (número, imagem extraída, biometria) e
   por quanto tempo — este último ainda **depende de decisão jurídica**.
Não há SDK novo, não há permissão nova de dispositivo e **nenhuma biometria** é usada (o que elimina a exigência de
declarar dado biométrico). Os bloqueios anteriores continuam: apps não construídos nem assinados, sem conta de
desenvolvedor, sem política publicada em domínio próprio.

