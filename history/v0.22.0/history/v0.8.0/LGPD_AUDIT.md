# LGPD_AUDIT — v0.7.0 (técnico; não é parecer jurídico)

| Requisito | Estado | Evidência | Pendência |
|---|---|---|---|
| Inventário de dados | YELLOW | `docs/legal/PRIVACY_POLICY.md` §2 (derivado do esquema) | validar com DPO |
| Minimização | GREEN | beneficiários só agregados; nenhum dado sensível solicitado | revisar campos livres e documentos enviados |
| Base legal/finalidade | YELLOW | propostas na política | **decisão jurídica por tratamento** |
| Consentimento (quando aplicável) | GREEN (mecanismo) | `consents`, `/v1/privacy/consents`, aceite no cadastro | textos finais |
| Acesso/portabilidade | GREEN | `/v1/privacy/export` (testado) | cobrir dados de organização (hoje: dados do usuário e vínculos) |
| Eliminação/anonimização | GREEN (usuário) / YELLOW | `/v1/privacy/delete-account` anonimiza; cadeia de auditoria preservada pseudonimizada | política para dados de organização e documentos; prazos legais |
| Correção | GREEN | edição de perfil | — |
| Retenção | YELLOW | job `retention` para dados técnicos | prazos de documentos/ledger definidos pelo jurídico |
| Segurança | YELLOW | ver `SECURITY_AUDIT.md` | pentest, KMS |
| Transferência internacional | YELLOW | provedores externos desligados por padrão (IA local) | cláusulas se ativar provedores fora do Brasil |
| Operadores/suboperadores | YELLOW | lista na política (campos `{{}}`) | contratos (DPA) |
| Crianças/adolescentes e sensíveis | YELLOW | não coletados pela plataforma; OSC é controladora de dados em documentos | orientação às OSCs; verificação de uploads |
| Governança | RED | — | DPO nomeado, RIPD/DPIA, registro de operações (ROPA), plano de resposta a incidentes |
| Logs sem dados desnecessários | GREEN | logs sem corpo; IA logada por hash | — |
| Localização pública configurável | RED | território UF/município fixo | granularidade por projeto |
Conclusão: **mecanismos técnicos presentes; conformidade LGPD não declarada** — depende de governança, jurídico e DPO.
