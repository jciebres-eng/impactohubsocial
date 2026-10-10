# Baseline de autenticação e autorização (adendo de login, §1)

Auditado no commit `b50c4e0` (v0.35.0). Estados: IMPLEMENTADO E TESTADO · PARCIAL · AUSENTE · NÃO VERIFICADO.

| Item | Estado | Onde (código) | Teste |
|---|---|---|---|
| Login, logout, logout de todas as sessões | IMPLEMENTADO E TESTADO | `api/auth_routes.py`, `services/auth.py` | `test_api_auth` |
| Cadastro sem revelar e-mail existente (202 + aviso ao titular) | IMPLEMENTADO E TESTADO | `services/auth.py::register` | `test_api_auth` |
| Recuperação de senha com resposta genérica; token 30 min, uso único | IMPLEMENTADO E TESTADO | `services/auth.py` (`auth_tokens`, só hash) | `test_api_auth` |
| Login de conta bloqueada responde `429 account_locked` (só existe para conta real) | PARCIAL (enumeração possível) | `services/auth.py::login` | sem teste — achado P2 |
| Verificação de e-mail (48 h); escrita de organização exige e-mail confirmado | IMPLEMENTADO E TESTADO | `http.py::authorize` | `test_api_auth` |
| MFA/TOTP, código não reutilizável; equipe ativa com código do app + e-mail; equipe não desliga | IMPLEMENTADO E TESTADO | `security/totp.py`, `services/auth.py`, `0051`, `0074` | `test_v0350_security` |
| Confirmação de identidade (step-up) de 15 min | IMPLEMENTADO E TESTADO | `core/access.py`, `http.py::require_fresh_identity` | `test_v0220_authorization`, `test_v0350_security` |
| Sessões: acesso 15 min, renovação 30 dias, inatividade 14 dias, rotação com detecção de reuso; cookies `__Host-`/`__Secure-`; CSRF | IMPLEMENTADO E TESTADO | `services/auth.py`, `http.py` | `test_v0230_session_hardening` |
| Limites por IP (ponta confiável do proxy) e bloqueio por conta (8 falhas/15 min, inclui MFA) | IMPLEMENTADO E TESTADO | `services/ratelimit.py`, `http.py` | `test_v0350_security` |
| OIDC (code + PKCE, JWKS), um provedor por instalação | PARCIAL (contract test) | `services/oidc.py` | `test_oidc` (provedor falso) |
| SAML, LDAP, provedor por IES | AUSENTE | — | — |
| Organização, vínculo (6 papéis), organização ativa revalidada a cada requisição | IMPLEMENTADO E TESTADO | `0001`, `http.py::load_principal` | `test_security_tenancy`, `test_v0220_authorization` |
| Papel com escopo menor que a organização (curso, turma) | AUSENTE | — | — |
| Convite de equipe (hash, 7 dias, revogação, uso único com bloqueio de linha) | IMPLEMENTADO; reuso/expiração/revogação **sem teste** | `services/auth.py::invite/accept_invite` | `test_api_auth` (só fluxo feliz e e-mail errado) |
| Pessoa sem organização usa o produto | AUSENTE (tela obriga a criar organização) | `web/src/app.tsx` (`CreateOrg`) | — |
| Escolha de contexto após o login | IMPLEMENTADO | `access_routes.py::dashboard_for`, `portal.tsx` | E2E de portal |
| Acesso temporário de terceiro com escopo e revogação | AUSENTE como mecanismo genérico (há casos específicos: diligência, revisão profissional, registro verificável) | `0074`, `0001`, `trust/verifiable.py` | — |
| Trilha de auditoria (encadeada, só inclusão), log de acesso privilegiado | IMPLEMENTADO E TESTADO | `services/audit.py`, `0046` | vários |
| Testes de isolamento entre organizações (porta e muro) | IMPLEMENTADO E TESTADO | — | `test_v0230_authorization_matrix`, `test_security_tenancy` |

**Consequência para a IES:** reaproveitar tudo acima; criar (1) vínculo acadêmico com escopo, (2) uso sem organização para quem só
tem vínculo acadêmico, (3) concessão temporária de leitura (avaliador), (4) testes de convite que faltam — no padrão do núcleo.
