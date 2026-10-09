# TRUST_INVENTORY — auditoria real antes de implementar (v0.14.0)

Método: leitura do **código do repositório**, não dos documentos. Nenhuma capacidade foi classificada como `IMPLEMENTED` sem teste que a exercite.
Classificação: `IMPLEMENTED` · `PARTIAL` · `SCAFFOLDED` (existe, nunca exercitado) · `MOCK` (dublê) · `NOT_IMPLEMENTED` · `BLOCKED` (ambiente) · `EXTERNAL_DEPENDENCY` · `REQUIRES_HOMOLOGATION`.

## 1. O que JÁ EXISTIA (e não vou reescrever)
| Capacidade | Onde | Classificação antes | Evidência |
|---|---|---|---|
| Hash SHA-256 de todo documento | `documents.sha256` (CHECK de formato) | **IMPLEMENTED** | cofre calcula no upload; teste de upload |
| Versionamento de documento | `documents.version` + `supersedes_id` | **IMPLEMENTED** | testes de documento |
| Cofre com validação de arquivo | `services/documents.py` (allowlist, magic bytes, conteúdo ativo em PDF, zip bomb, antivírus) | **IMPLEMENTED** (clamd real: `EXTERNAL_DEPENDENCY`) | testes |
| Trilha de auditoria **encadeada por hash** | `audit_events` + `ledger_entries` + `chain_heads` + gatilhos `audit_material`/`ledger_material` e função de verificação de cadeia | **IMPLEMENTED** | `0002_security.sql`; testes de integridade |
| Assinatura eletrônica avançada da plataforma | `POST /v1/signatures`: reautenticação por **senha**, hash exato do conteúdo, credencial, papel, declaração, IP, agente, HMAC do servidor | **PARTIAL** | existe e é testada, mas **uma camada só** (senha) e **sem verificação pública** |
| Verificação de integridade | `GET /v1/signatures/verify` | **PARTIAL** | exige login e mesma organização — não serve a terceiro |
| Credencial profissional | `professional_credentials` (conselho, número, UF, validade, estados `self_declared→document_submitted→verified→rejected→expired`) | **PARTIAL** | o modelo existe; **não há fluxo de verificação** nem registro de conselhos |
| Revisão profissional de conteúdo | `professional_reviews` + `drafts` assinados | **IMPLEMENTED** | testes |
| Qualificação institucional | `organization_qualifications` + histórico append-only + gatilho que impede autopromoção | **IMPLEMENTED** | testes |
| Compliance da organização | `compliance_checks` / `compliance_reviews` | **IMPLEMENTED** | testes |
| Tokens por e-mail | `auth_tokens` (`verify_email`, `reset_password`, `mfa_challenge`), hash do token, expiração, tentativas | **IMPLEMENTED** | testes |
| MFA TOTP | administração obrigatória | **IMPLEMENTED** | testes |
| Cifragem de campo | `security/crypto.FieldCipher` (Fernet com rotação) | **IMPLEMENTED** | usada em credenciais de integração |
| Consentimento LGPD | `consents` + `/v1/privacy/*` | **IMPLEMENTED** | testes |
| Geração de PDF | `services/documents.render_pdf` (reportlab, BSD) | **IMPLEMENTED** | exportação de rascunho |
| Integration Hub | `integrations/*` (v0.13.0) | **IMPLEMENTED** | 76 testes |

## 2. O que NÃO existia (lacunas confirmadas por busca no código)
| # | Lacuna | Verificação feita |
|---|---|---|
| L1 | **Verificação pública por terceiro** | nenhuma rota pública de verificação de documento/assinatura (lista de `auth="none"` conferida) |
| L2 | **Código de verificação + QR Code** | `grep` por `qrcode/QRCode/qr_code` em backend e frontend → **zero** ocorrências |
| L3 | **Revogação de assinatura/documento** | nenhum campo ou rota de revogação |
| L4 | **Carimbo de tempo confiável (RFC 3161)** | nenhuma referência a TSA/timestamp externo |
| L5 | **Assinatura em duas camadas** | só reautenticação por senha; nenhum desafio por e-mail/celular no ato de assinar |
| L6 | **Verificação de identidade da pessoa (KYC)** | `compliance_checks` é da **organização**; não há nível de identidade por pessoa |
| L7 | **Biometria facial / prova de vida** | zero ocorrências; nenhum provedor |
| L8 | **Registro de conselhos profissionais** | `professional_credentials.council` é texto livre `^[A-Z]{2,8}$`; não há catálogo de conselhos nem regra de formato por conselho |
| L9 | **Cadeia de custódia do documento** (eventos encadeados por documento) | a cadeia existe para auditoria e para projeto, **não** por documento |
| L10 | **Acordo/contrato assinado entre partes** (profissional ↔ organização) | não existe objeto de acordo multiassinatura |
| L11 | **Assinatura qualificada (ICP-Brasil/gov.br)** | `signatures.method` aceita `icp_brasil`/`govbr` mas **nenhum código** produz esses valores → era **SCAFFOLDED** (enum sem implementação) |
| L12 | **Taxonomia ODS/ESG/determinantes sociais** | nenhuma coluna `sdg`; menções em texto de IA apenas |
| L13 | **Idioma / i18n** | nenhum catálogo, nenhum `Accept-Language`, nenhuma preferência de idioma |
| L14 | **Exportação docx/xlsx/odt/ods/xml** | só PDF (rascunho) e CSV/JSON (integração) |
| L15 | **Preferência de tema (claro/escuro) por usuária** | o CSS respeita `prefers-color-scheme`; não há escolha salva |
| L16 | **Financiamento em cotas + campanha pública** | `quotations` é **cotação de compra**, não cota de financiamento — nome parecido, domínio diferente |
| L17 | **Tabela de honorários por conselho** | não existe |
| L18 | **Diagnóstico guiado etapa a etapa** | `diagnoses` é um formulário único; não há etapas, progresso nem documentos por etapa |
| L19 | **Georreferência de organização/profissional** | `projects.lat/lng` existe; organizações e profissionais **não** têm coordenadas |
| L20 | **Edição on-line de Office/OpenOffice** | nenhuma referência a WOPI/Collabora/OnlyOffice |

## 3. Decisão de preservação (não reescrever)
Aproveitados como base da camada de confiança: hash do cofre · versionamento de documento · cadeia de hash de auditoria/razão · `signatures` (estendida, não substituída) · `professional_credentials` (estendida) · `auth_tokens` (novo propósito) · `FieldCipher` · `render_pdf` · RLS · `audit_events` · Integration Hub (adapters de identidade e de assinatura qualificada entram como provedores).
Motivo: são mecanismos testados e auditados; substituí-los seria risco sem ganho.

## 4. O que esta etapa NÃO vai poder provar (declarado antes de começar)
- **Assinatura qualificada ICP-Brasil / gov.br**: `EXTERNAL_DEPENDENCY` + `REQUIRES_HOMOLOGATION` (exige certificado, credenciamento e homologação).
- **Biometria facial e prova de vida**: `EXTERNAL_DEPENDENCY` (exige provedor contratado). Não vou simular biometria.
- **Carimbo de tempo RFC 3161**: `EXTERNAL_DEPENDENCY` (exige ACT). Carimbo interno assinado é o que fica implementado.
- **SMS como segunda camada**: `NOT_IMPLEMENTED` (não há provedor de SMS na plataforma; a segunda camada será e-mail).
- **Consulta on-line a conselho profissional**: `EXTERNAL_DEPENDENCY` (CFP/CRC/CRM/OAB não expõem API pública contratada).
