# Segurança

Referências: OWASP ASVS (versão vigente) e OWASP API Security Top 10.

## Controles de projeto
| Ameaça | Controle |
|---|---|
| Acesso cruzado (BOLA) | autorização por objeto/tenant em toda rota; RLS; testes negativos |
| Escalada via plano/voucher | direitos só via `EntitlementService`; admin com MFA; dupla aprovação em gratuidade acima do limiar |
| Enumeração/brute-force de voucher | códigos de alta entropia, hash em repouso, rate limit por IP/conta/CNPJ, resposta genérica, lockout progressivo |
| Abuso de vouchers (revenda, multi-conta) | vínculo opcional ao CNPJ, 1 resgate por organização, detecção de padrões, revogação |
| Upload malicioso | allowlist, antivírus, isolamento, URLs curtas |
| Prompt injection | ver `AI.md` |
| Conta de revisor/admin comprometida | MFA, privilégio mínimo, alertas |
| Webhook de billing falsificado | assinatura verificada, idempotência, reconciliação |
| Segredos | vault; `.env.example` sem valores; secret scanning no CI |
| Ransomware/indisponibilidade | backups imutáveis e restore testado; RPO ≤ 24 h / RTO ≤ 8 h (metas do piloto, não SLA) |

## Práticas
TLS moderno; criptografia em repouso/KMS; logs estruturados sem PII; auditoria append-only; SAST/DAST/dependências; pentest **antes** de ativar cobrança real ou escalar dados; plano de resposta a incidentes com comunicação à ANPD quando devida **[VALIDAR]**.

## Não verificado
Nada disso foi implementado ou testado. Status: RED.
