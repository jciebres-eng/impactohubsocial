# LGPD_AUDIT — v0.13.0 (técnico; não é parecer jurídico)

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
| Instrumentos, trilha e mentoria (v0.10.1): contratos/termos, etapas declaradas, mensagens de mentoria | YELLOW (técnico) | RLS por organização e administração; mensagens de mentoria só visíveis à org e à equipe; rede da solução só com agregados | definir retenção; orientar a não incluir dados pessoais sensíveis nas mensagens; contratos podem citar pessoas |
| Titularidade/IP e autorização de contato em soluções (v0.10.0) | YELLOW | campos declarados; `summary_only` quando restrito | verificação de titularidade é do autor; cláusulas nos termos |
| Governança | RED | — | DPO nomeado, RIPD/DPIA, registro de operações (ROPA), plano de resposta a incidentes |
| Logs sem dados desnecessários | GREEN | logs sem corpo; IA logada por hash | — |
| Histórico de busca (v0.9.0) | GREEN (técnico) | só hash SHA-256 + intenção estruturada; opt-in para personalização; opt-out apaga | definir retenção |
| Identidade de financiadores/replicadores (v0.9.0) | GREEN (técnico) | privada por padrão; autor só vê com opt-in ou pedido direto; agregados por organizações distintas | base legal do compartilhamento no pedido |
| Autoria/equipe de soluções (v0.9.0) | YELLOW | nomes cadastrados pelo autor (pode incluir terceiros) | orientar autores a ter consentimento; processo de remoção/contestação existe |
| Localização pública (v0.8.0) | GREEN (técnico) | precisão configurável; coordenadas exatas nunca vazam | validar padrões com o jurídico |
| Monetização (v0.11.0): e-mail/CNPJ para anti-abuso do trial | YELLOW | só HMAC (`trial_claims`), sem dado em claro, retenção 24 meses no job `billing_lifecycle`; teste garante ausência de e-mail em claro | base legal (legítimo interesse/prevenção a fraude) e RIPD a validar com DPO |
| Dados de pagamento | GREEN | a plataforma não armazena cartão (portal do provedor); faturas guardam valor/status/URL | contrato/operador (Stripe) e transferência internacional a validar |
| Cancelamento/exclusão | GREEN | cancelar não apaga dados nem histórico financeiro; exclusão de conta segue o fluxo existente | prazos de guarda fiscal a validar |

Conclusão: **mecanismos técnicos presentes; conformidade LGPD não declarada** — depende de governança, jurídico e DPO.

| Central (v0.12.0): busca/assistente | GREEN (técnico) | log guarda **hash + assuntos**, nunca o texto digitado; retenção 18 meses (`retention`) | validar prazo com o jurídico |
| Central: captação (parceria, demonstração, boletim) | YELLOW | consentimento com versão/data, finalidade clara, anti-bot, duplo opt-in, descadastro por link | **base legal, prazo de retenção de propostas/demos e texto de consentimento pendentes (jurídico/DPO)** |
| Central: chamados | YELLOW | só a pessoa e a equipe veem; anexos só documentos próprios | orientar a não enviar dados sensíveis (há aviso no formulário); prazo de guarda |
| Central: e-mail de avisos | YELLOW | respeita preferências; sem e-mail para conta não verificada | SMTP/SPF/DKIM reais |
| Certificados públicos | YELLOW | verificação pública expõe **nome do titular, curso, carga e data** (necessário à verificação) | confirmar base legal/aviso ao titular |

| Erros da API não expõem dados de outras pessoas (v0.12.1) | GREEN (técnico) | violação de unicidade não devolve mais o valor conflitante (evita enumeração de e-mail) | — |
| Desconto reservado exposto à própria organização (v0.12.1) | GREEN (técnico) | leitura em contexto de sistema **restrita ao `org_id` da sessão**; sem código/hash de voucher na resposta; teste de isolamento | — |

## Camada de integração (v0.13.0)
| Requisito | Estado | Evidência | Pendência |
|---|---|---|---|
| Inventário dos fluxos de integração | GREEN | `INTEGRATION_ARCHITECTURE.md` (6 fluxos) e `INTEGRATION_HUB.md` | — |
| Minimização no que sai | GREEN | payload de evento montado pelo servidor; datasets de BI com colunas fixas do domínio (sem segredo, sem conteúdo de mensagem de suporte) | revisar dataset a dataset com o DPO |
| Minimização no que entra | GREEN | importação **nunca cria pessoa nem organização**; só vincula e atualiza existentes, com aprovação humana | — |
| Base legal para compartilhar com terceiro | **YELLOW** | a organização cria a assinatura e responde por ela; não há registro de finalidade por assinatura | **VALIDAÇÃO JURÍDICA NECESSÁRIA**: registrar finalidade/base legal por assinatura |
| Controle de acesso | GREEN | RLS nas 13 tabelas + papéis (`owner` para credencial e aprovação); testes de organização cruzada | — |
| Segredo de terceiro | GREEN | cifrado, sem leitura pela aplicação, nunca em log, auditoria, resposta ou ZIP | rotação programada (hoje manual) |
| Rastreabilidade | GREEN | `audit_events` com quem/organização/conexão/operação/resultado/correlação, **sem segredo** | — |
| Retenção | **YELLOW** | entregas concluídas apagadas em 180 dias; dead-letter preservado | jobs, eventos e entradas **sem prazo definido** — decisão jurídica |
| Transferência internacional | **YELLOW** | depende do provedor que a organização conectar | cláusulas por provedor quando houver conexão real |
| Eliminação | GREEN | apagar correspondência não apaga dado do núcleo; exclusão de conta segue o fluxo de privacidade existente | — |
