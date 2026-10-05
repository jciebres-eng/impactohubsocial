# SECURITY_AUDIT — v0.7.0 (2026-10-05)

Escopo: código do repositório + execução local. **Não é pentest.** Controles detalhados e testes: `docs/SECURITY.md`.
Resultado: **GREEN** = verificado por teste · **YELLOW** = implementado, depende de config/serviço real · **RED** = ausente.

## Achados do v0.6.0 (corrigidos)
| # | Achado | Severidade | Correção |
|---|---|---|---|
| S1 | RLS só em arquivo SQL, nunca aplicado/testado | Crítica | RLS aplicado, papel sem BYPASSRLS, teste via SQL direto — GREEN |
| S2 | Autenticação de demonstração | Crítica | scrypt + sessões + refresh rotativo + MFA — GREEN |
| S3 | Ausência de proteção CSRF/brute force/enumeração | Alta | implementados e testados — GREEN |
| S4 | Upload sem validação | Alta | allowlist, magic bytes, conteúdo ativo, zip bomb, antivírus — GREEN (clamd real: YELLOW) |
| S5 | Segredos/config sem validação | Alta | fail-fast em staging/production — GREEN |

## Bugs de segurança/autorização encontrados e corrigidos na construção
Body validado antes da autorização (vazava esquema) · UUID inválido gerava 500 · falta de política UPDATE · contadores de lockout/MFA/reuso revertidos por rollback (permitia tentativas ilimitadas) · plano sem preço comprável · voucher com falha de serialização.

## OWASP Top 10 (mapa)
| Risco | Estado |
|---|---|
| A01 Broken Access Control | GREEN — RLS + RouteSpec + testes IDOR/escalonamento |
| A02 Cryptographic Failures | GREEN/YELLOW — scrypt, Fernet, HMAC, TLS depende do proxy; criptografia em repouso do disco/S3 é da infraestrutura |
| A03 Injection | GREEN — somente consultas parametrizadas (`PQexecParams`); teste de arquitetura contra SQL concatenado; CSP; saída escapada pelo React |
| A04 Insecure Design | YELLOW — threat model informal (este documento); sem modelagem formal STRIDE |
| A05 Security Misconfiguration | GREEN — fail-fast, headers, CORS allowlist |
| A06 Vulnerable Components | **YELLOW — sem varredura (rede bloqueada)**; pip-audit/npm audit no CI |
| A07 Identification & Auth Failures | GREEN — ver S2/S3; WebAuthn ausente |
| A08 Integrity Failures | GREEN — cadeias de hash, webhook assinado; supply chain de CI não endurecida |
| A09 Logging & Monitoring | YELLOW — logs JSON/métricas/auditoria; sem SIEM, traces ou alertas ativos |
| A10 SSRF | GREEN/YELLOW — `HttpClient` só aceita https, bloqueia IPs privados/link-local (metadados de nuvem)/reservados/loopback e **não segue redirecionamentos** (teste `SsrfTests`); risco residual de DNS rebinding → restringir *egress* na rede |

## Lacunas / recomendações antes de produção
1. Pentest independente e varredura de dependências. 2. Restrição de *egress* de rede do contêiner (complementa o bloqueio SSRF da aplicação). 3. KMS/cofre de segredos e rotação. 4. Armazenamento seguro de tokens no app móvel. 5. WAF/CDN e DDoS. 6. Revisão do CSP quando adicionar mapas/analytics. 7. Política de retenção de logs e acesso. 8. Teste de carga e de resiliência. 9. Plano de resposta a incidentes (ANPD art. 48). 10. Revisão do usuário `postgres`/rede do banco (somente rede privada).

## Declaração
Nenhuma afirmação de "seguro" é feita além do que os testes provam. Os testes cobrem os controles listados; **ausência de falhas nos testes não implica ausência de vulnerabilidades**.
