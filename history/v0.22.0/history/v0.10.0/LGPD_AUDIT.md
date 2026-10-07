# LGPD_AUDIT — v0.10.0 (técnico; não é parecer jurídico)

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
| Dados institucionais (v0.10.0): qualificações, documentos, necessidades, situação | YELLOW (técnico) | acesso restrito à organização e à administração (RLS); perfil público só com campos públicos/verificados; histórico de eventos | definir retenção e base legal; documentos podem conter dados pessoais de dirigentes — orientar OSCs |
| Decisão automatizada (v0.10.0) | GREEN (técnico) | elegibilidade e maturidade são **indicadores explicáveis**, sem efeito jurídico; situação institucional é decisão humana justificada; sem IA | direito de revisão: canal à administração (processo a definir) |
| Titularidade/IP e autorização de contato em soluções (v0.10.0) | YELLOW | campos declarados; `summary_only` quando restrito | verificação de titularidade é do autor; cláusulas nos termos |
| Governança | RED | — | DPO nomeado, RIPD/DPIA, registro de operações (ROPA), plano de resposta a incidentes |
| Logs sem dados desnecessários | GREEN | logs sem corpo; IA logada por hash | — |
| Histórico de busca (v0.9.0) | GREEN (técnico) | só hash SHA-256 + intenção estruturada; opt-in para personalização; opt-out apaga | definir retenção |
| Identidade de financiadores/replicadores (v0.9.0) | GREEN (técnico) | privada por padrão; autor só vê com opt-in ou pedido direto; agregados por organizações distintas | base legal do compartilhamento no pedido |
| Autoria/equipe de soluções (v0.9.0) | YELLOW | nomes cadastrados pelo autor (pode incluir terceiros) | orientar autores a ter consentimento; processo de remoção/contestação existe |
| Localização pública (v0.8.0) | GREEN (técnico) | precisão configurável; coordenadas exatas nunca vazam | validar padrões com o jurídico |
Conclusão: **mecanismos técnicos presentes; conformidade LGPD não declarada** — depende de governança, jurídico e DPO.
