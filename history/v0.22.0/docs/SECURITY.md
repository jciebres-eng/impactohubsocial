# Segurança — controles implementados (v0.7.0)

Cada controle indica **onde está no código** e **qual teste o prova**. Itens sem teste automatizado estão marcados.
Relatório de auditoria e riscos residuais: `SECURITY_AUDIT.md` (raiz).

## Autenticação (`services/auth.py`, `security/`)
| Controle | Implementação | Teste |
|---|---|---|
| Hash de senha | scrypt N=2^17, r=8, p=1, sal 16 B; PBKDF2 legado só verificado e re-hasheado no login | `test_unit`, `test_api_auth` |
| Política de senha | mínimo 10 caracteres, lista de senhas comuns, não pode conter o e-mail | `test_api_auth` |
| Sessão web | token de acesso opaco (15 min) em cookie `__Host-` httpOnly; renovação 30 dias em cookie `__Secure-` restrito a `/v1/auth`; tokens guardados **só como hash** | `test_api_auth` |
| Rotação de refresh | cada uso emite novo par; reuso de token antigo **revoga a família inteira** | `test_api_auth` (reuse detection) |
| CSRF | token HMAC vinculado à sessão no header `X-CSRF-Token` + verificação de `Origin` em métodos não seguros | `test_api_auth`, `test_e2e_web` |
| App nativo | `X-Auth-Mode: token` → tokens Bearer no corpo, sem cookies | `test_api_auth` |
| Logout / revogação | logout revoga a sessão; "sair de todos os dispositivos"; troca de senha revoga as demais sessões | `test_api_auth` |
| MFA | TOTP RFC 6238 (janela ±1), segredo cifrado (Fernet), 10 códigos de recuperação com hash, uso único; **obrigatório para rotas de administração** | `test_unit` (vetores RFC), `test_api_auth` |
| Força bruta | bloqueio da conta após 8 falhas (15 min) + rate limit por IP/e-mail persistido no banco | `test_api_auth` |
| Anti-enumeração | login, reset e reenvio respondem igual para e-mail existente/inexistente | `test_api_auth` |
| Verificação de e-mail, reset, convite | tokens de uso único, com hash e expiração | `test_api_auth` |
| SSO OIDC | Authorization Code + PKCE (S256), `state` e `nonce` no banco, validação de assinatura via JWKS, `iss`/`aud`/`exp`; MFA considerado só se `amr` indicar | `test_oidc` (IdP falso local) |
| Modo demo | seed fictício e `MAIL_PROVIDER=console` **recusados no boot** em staging/production | `test_unit` (config) |

## Autorização (`http.py`, `services/entitlements.py`)
- Ordem fixa: autenticação → tipo de organização → papel mínimo (owner/admin/member/viewer) → MFA admin → feature do plano → **só então** validação do corpo (evita vazar esquema a quem não pode).
- Parâmetros UUID inválidos → 404 (nunca 500).
- Plano/voucher **não alteram** match, elegibilidade, ordenação ou ranking de prestadores (teste AST em `test_architecture`).

## Multi-tenant (banco)
RLS em todas as tabelas com papel `impacto_app` sem `BYPASSRLS`; o boot recusa (staging/production) papel superusuário,
com BYPASSRLS ou dono das tabelas. Detalhes em `DATABASE.md`. Testes cruzados em `test_security_tenancy.py`.

## Arquivos (`services/documents.py`, `adapters/antivirus.py`, `adapters/storage.py`)
Lista de extensões permitidas; verificação de *magic bytes*; PDF com JavaScript/ação automática/arquivo embutido recusado;
DOCX/XLSX com macro recusado e proteção contra zip bomb; limite de tamanho; nome de arquivo saneado; armazenamento privado
(chave aleatória, nunca o nome original); download só após antivírus `clean` (salvo `ALLOW_UNSCANNED_DOWNLOADS` em dev);
antivírus via clamd INSTREAM. **Antivírus real não testado aqui** (daemon indisponível) — protocolo coberto por servidor falso.

## SSRF (`adapters/http_client.py`)
Só https; IP privado/link-local/reservado/loopback recusado (loopback http apenas em development/test); redirecionamentos não seguidos; resposta limitada em tamanho. Teste: `test_unit.SsrfTests`.

## Cabeçalhos HTTP (`app.py`)
CSP `default-src 'self'` sem `unsafe-inline`/`unsafe-eval`, `frame-ancestors 'none'`, X-Frame-Options DENY, nosniff,
Referrer-Policy strict-origin-when-cross-origin, Permissions-Policy restritiva, COOP same-origin, HSTS (2 anos, preload)
em staging/production. CORS somente para `CORS_ORIGINS`.

## Segredos
Nenhum segredo no repositório. `.env.example` só com marcadores. `python -m impacto.cli gen-secrets` gera valores.
O boot recusa segredos ausentes, curtos (<32) ou com valor de exemplo em staging/production.
Segredos esperados: `SECRET_KEY`, `VOUCHER_HMAC_KEY`, `FIELD_ENCRYPTION_KEY`, `METRICS_TOKEN` + credenciais de
provedores ativados (S3, SMTP, Stripe, IA, OIDC, Portal da Transparência).

## Auditoria
`audit_events` encadeado por hash por organização (login, MFA, troca de papel, decisões de compliance, aportes,
assinaturas, vouchers, regras fiscais…); `GET /v1/admin/audit/verify` recalcula a cadeia.

## Pagamentos
Sem dados de cartão na plataforma (Stripe Checkout hospedado). Webhook com verificação de assinatura HMAC, tolerância
de 300 s e idempotência por `event.id`. Provedor `sandbox` proibido em produção.

## Pendências (não implementado / não verificável aqui)
- Pentest externo, SAST/DAST em CI com ferramentas de terceiros (pip-audit/npm audit estão no CI, não executados aqui).
- WAF/CDN, proteção DDoS, gestão de segredos em cofre (KMS/Vault) — infraestrutura.
- Armazenamento seguro de tokens no app (Keychain/Keystore) — hoje `@capacitor/preferences` (ver `MOBILE.md`).
- WebAuthn/passkeys — não implementado.

## v0.9.0
Controles da Biblioteca (RLS, gatilhos, funções `SECURITY DEFINER`, privacidade da intenção) em `SECURITY_AUDIT.md`.
