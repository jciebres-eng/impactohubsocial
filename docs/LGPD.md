# LGPD — como o código implementa privacidade (v0.7.0)

Minuta de textos legais: `docs/legal/` (**[VALIDAR JURÍDICO]**). Este documento descreve mecanismos técnicos reais.
Nenhuma conformidade é "declarada": o que existe é um conjunto de controles verificáveis + pendências para DPO/advogado.

## Direitos do titular (`api/privacy_routes.py`)
| Direito | Endpoint | Observação |
|---|---|---|
| Acesso/portabilidade | `GET /v1/privacy/export` | |
| Eliminação | `POST /v1/privacy/delete-account`; solicitação registrada em `privacy_requests`; anonimiza usuário (e-mail → alias, nome, hash de senha, MFA, OIDC) | trilha de auditoria preservada de forma pseudonimizada (obrigação/integridade) |
| Consentimentos | `consents` (tipo, versão do texto, data, IP) | aceite de termos/privacidade no cadastro |
| Correção | edição de perfil/organização pela própria interface | |

## Minimização e finalidade
- Beneficiários entram **só como contagens agregadas** (`beneficiaries_count`), nunca lista nominal.
- Nenhum campo de dado sensível (art. 5º, II) é solicitado.
- Dados de IA: texto não é logado (hash e tamanhos); provedor padrão é local.
- `ai_usage`, `rate_events`, sessões e tokens expiram por job de retenção (`jobs.retention`: rate_events 2 dias, tokens 7 dias, sessões 30 dias, `ai_usage` 13 meses, notificações lidas 180 dias).

## Segurança dos dados
Segredo TOTP cifrado (Fernet), tokens/recovery em hash, arquivos privados, RLS multi-tenant, logs sem corpo de requisição,
backup com verificação de integridade. Detalhes em `SECURITY.md`.

## Compartilhamento controlado
Documentos de uma OSC só são visíveis a financiador após interesse/diligência (`app_document_access`); projeto só aparece a financiadores se `published`.
Governo recebe **estatísticas agregadas** por território (`gov_territory_stats`), não dados de organizações.

## Limites e riscos conhecidos
- Localização pública de projetos usa território (UF/município); **granularidade configurável por projeto não está implementada** (RED no prompt-mestre §22).
- Anonimização de beneficiários individuais não se aplica (não são coletados).
- Prazos de retenção reais, base legal por tratamento, RIPD/DPIA, contrato de operador com provedores e canal do encarregado: **pendentes de decisão jurídica** (`docs/legal/PRIVACY_POLICY.md` traz propostas marcadas [VALIDAR]).
- Dados de crianças: a plataforma não coleta; a OSC é controladora de qualquer dado que insira em documentos.

## v0.9.0
Biblioteca: log de busca só com hash + intenção estruturada; personalização opt-in e apagável; identidade de financiadores/replicadores privada por padrão. Ver `LGPD_AUDIT.md`.
