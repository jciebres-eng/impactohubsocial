# Compliance / KYB (`services/compliance.py`)

Escopo: **organizações** (KYB). KYC de pessoa física não se aplica (a plataforma não custodia recursos — ADR-003/022).

## Verificações (`compliance_checks`: tipo, status, detalhes, fonte, data, quem)
| Check | Fonte | Estado |
|---|---|---|
| `cnpj_format` | dígitos verificadores (algoritmo) | ativo |
| `cnpj_registry` | consulta de CNPJ via `CNPJ_LOOKUP_URL` (adapter; situação ATIVA) | `not_configured` até o proprietário escolher/contratar a fonte |
| `sanctions_ceis_cnep` | Portal da Transparência (`PORTAL_TRANSPARENCIA_API_KEY`) | `not_configured` sem chave |
| `documents_basic` | cofre de documentos (por tipo de organização: estatuto, ata, cartão CNPJ, CND federal, CRF/FGTS, CNDT) | ativo |
| `documents_expiring` | validade < 30 dias | ativo |
| `profile_completeness` | cadastro | ativo |
| `open_reports` | denúncias abertas | ativo |
Status por verificação: `pass | fail | warning | error | not_configured`. **`not_configured` nunca é tratado como aprovado.**
Risco: `high` (qualquer fail) · `medium` (≥2 alertas) · `low`.

## Fluxo
Organização solicita revisão → `compliance_reviews` → **administrador decide** (aprovado/rejeitado/suspenso, com nota; auditado). O status da organização só muda por admin (coluna protegida por trigger).
O Match trata `rejected/suspended` como bloqueio e `pending` como risco.

## Fontes governamentais (arquitetura de adapters)
Cada fonte é um adapter configurável (URL/chave por env) com `HttpClient` (https, SSRF, timeout, retry). Disponibilidade das APIs **não é presumida**: sem configuração, registra-se `not_configured` e o admin faz verificação manual. Certidões (CND etc.) são **enviadas pela organização e conferidas**; não há emissão/validação automática de certidões.

## Pendências
Integração real de CNPJ/CEIS/CNEP; validação automática de certidões; verificação de dirigentes e conflitos; regras de compliance versionadas em tabela (hoje em código).
