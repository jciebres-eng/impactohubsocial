# Política de Cookies — Plataforma Impacto

> **MINUTA — [VALIDAR JURÍDICO]**. Lista extraída do código v0.7.0 (`backend/impacto/api/auth_routes.py`, `web/sw.template.js`).

A Plataforma usa **somente cookies e armazenamentos estritamente necessários** ao funcionamento e à segurança.
Não há cookies de publicidade, rastreamento ou análise de terceiros; por isso não exibimos banner de consentimento.
Se o proprietário adicionar ferramentas de análise no futuro, esta política e um mecanismo de consentimento deverão ser atualizados.

| Nome | Tipo | Finalidade | Duração | Acessível por JavaScript |
|---|---|---|---|---|
| `__Host-impacto_at` | cookie de sessão | token de acesso opaco | 15 minutos | não (httpOnly, Secure, SameSite=Lax) |
| `__Secure-impacto_rt` | cookie | token de renovação, restrito ao caminho `/v1/auth` | 30 dias, rotativo | não (httpOnly, Secure, SameSite=Strict) |
| `__Host-impacto_csrf` | cookie | proteção contra CSRF (vinculado à sessão) | 30 dias (igual ao token de renovação) | sim (necessário para o cabeçalho X-CSRF-Token) |
| Cache do Service Worker | Cache Storage | funcionamento offline da interface (HTML/CSS/JS/fontes) | até nova versão | — (nunca armazena respostas da API `/v1`) |

Em ambiente de desenvolvimento sem HTTPS os cookies usam nomes sem os prefixos `__Host-`/`__Secure-`.

No aplicativo móvel (Android/iOS) não há cookies: os tokens ficam no armazenamento do dispositivo
(`@capacitor/preferences`); para produção recomenda-se armazenamento seguro (Keychain/Keystore) — ver `docs/MOBILE.md`.
