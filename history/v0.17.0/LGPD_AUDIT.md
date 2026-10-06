# LGPD_AUDIT — v0.17.0 (técnico; não é parecer jurídico)

A matriz por categoria de dado — base legal, finalidade, prazo, o que acontece no fim do prazo e quem tem acesso —
está em **`DATA_RETENTION_MATRIX.md`**, inclusive a lista do que a plataforma **deliberadamente não coleta** (sem
cadastro nominal de beneficiário, sem dado sensível, sem dado biométrico, sem rastreamento publicitário) e as
**5 pendências honestas** (prazo de retenção de documento após encerramento, remoção física do objeto no
armazenamento, DPO nomeado, RIPD e ROPA formal).




## v0.17.0 — o conflito entre prova e eliminação, e como ele foi resolvido

A rodada criou a primeira estrutura do produto em que **a prova precisa sobreviver ao titular**:
`legal_acceptances` registra quem aceitou qual documento, em qual versão, com o sha256 do texto — e guarda IP e
agente de usuário, que são dado pessoal.

A tabela é append-only, porque prova que pode ser editada não prova nada. Mas a exclusão de conta anonimiza o
titular. Com um gatilho que proíbe qualquer alteração, a anonimização seria **recusada pelo banco**: o produto teria
de escolher entre a prova e o direito do titular.

**A escolha foi estreitar o append-only em vez de afrouxá-lo.** `acceptance_anonymize_only()` permite exatamente
uma alteração — apagar IP e agente de usuário — e recusa todas as outras; o GRANT de coluna recusa antes ainda,
porque a aplicação só tem `UPDATE (ip, user_agent)`. A prova sobrevive sem eles: ela é o documento, a versão, o hash
do texto e o titular pseudonimizado.

| Item LGPD | Situação |
|---|---|
| Portabilidade (art. 18, V) | 🟢 `/v1/privacy/export` passou a incluir a prova de aceite **com o hash**, que é o que permite a quem recebe o arquivo verificar o que foi aceito |
| Eliminação (art. 18, VI) | 🟢 a exclusão de conta apaga IP e agente de usuário do aceite e mantém a prova pseudonimizada |
| Minimização (art. 6º, III) | 🟢 retenção nova: IP de aceite com mais de 18 meses apagado; corpo bruto de webhook esvaziado no mesmo prazo (o evento fica, por idempotência) |
| Dado pessoal nas tabelas novas | 🟢 varredura do catálogo com quatro exceções declaradas; `value_events`, `billable_events` e `platform_charges` não guardam dado de pessoa além de `actor_user_id` |
| Finalidade na venda de dado agregado | 🔴 **receita recusada**: dado anonimizado deixa de estar fora da LGPD se a anonimização puder ser revertida com esforços razoáveis (art. 12), e agregado territorial com contagem pequena é exatamente onde a reidentificação acontece |
| Encarregado(a) nomeado (art. 41) | 🟡 continua pendência do proprietário; é um campo `{{ }}` nas onze minutas |

### O corpo do webhook

`billing_events.payload` guarda o que o provedor manda, e isso pode conter nome e e-mail do pagador. O evento
precisa ser guardado para sempre (idempotência e reconciliação); o **corpo** dele, não. Depois de 18 meses o corpo é
esvaziado e o evento fica.

## v0.16.0 — a rede, o perfil público e o grupo beneficiário

Esta rodada criou a primeira superfície **pública por escolha da pessoa** (`impacto.app/@identificador`) e a
primeira coluna que chega perto de categoria especial (`beneficiary_groups`). As duas foram tratadas como o centro
da revisão de privacidade.

### A página pública

| Controle | Como |
|---|---|
| Publicar é **ato explícito** | o perfil nasce `private`; nada vai ao ar sem a pessoa ligar |
| A página não consulta tabela privada | lê **só** `public_fields`, uma projeção curada montada pelo servidor |
| Lista fechada do que pode ser projetado | `PROJECTABLE`, 18 chaves |
| Lista do que **nunca** é público | `NEVER_PUBLIC`: CNPJ, e-mail, telefone, endereço, número de documento, situação e risco de conformidade, grupo beneficiário, CPF, data de nascimento, dados bancários, receita |
| Rede de segurança na gravação | `_assert_no_private()` **falha a gravação** se qualquer chave proibida entrar na projeção |
| Contato desligado por padrão | `show_contact` falso; ligar é escolha |
| Número de registro profissional não vai ao ar | a página diz "tem CREA/SP verificado", não qual é o número |
| Credencial não verificada e experiência não confirmada não aparecem | a plataforma não repassa afirmação sem conferência |
| Perfil suspenso responde **404** | "existe, mas está suspenso" é informação sobre a moderação |
| Histórico de identificadores é append-only e legível pela dona | quem confiou no endereço `@nome` tem como saber que ele mudou de mãos |

### `BeneficiaryProfile ≠ SensitivePersonalData`

A distinção pedida, aplicada:

> "Este projeto atende mulheres em situação de vulnerabilidade" → **atributo do projeto**.
> "Esta pessoa é mulher e pertence a determinado grupo vulnerável" → **dado pessoal sensível**, e a plataforma não
> coleta.

| Controle | Como se verifica |
|---|---|
| A coluna existe em **uma** tabela (`territory_needs`) | invariante que consulta `information_schema` e falha se aparecer em outra |
| **Não é filtro de busca** em nenhuma rota | invariante que percorre os modelos de `query` das 704 rotas |
| A política de uso está gravada **no banco** | `taxonomies.usage_policy`: "é proibido usar este conjunto para filtrar, segmentar ou inferir característica de usuária ou usuário" |
| Nenhuma inferência de atributo pessoal | não há caminho no código que derive característica de pessoa; a recomendação usa estado de projeto, documento e proposta |
| Continua sem cadastro nominal de beneficiário final | ADR-139, inalterado |

### Dado pessoal nas superfícies novas

| Superfície | O que guarda de pessoa | Tratamento |
|---|---|---|
| `relationships` | nenhum — liga **organizações** | o ator que criou fica em coluna de auditoria |
| `proposals` | o texto que as partes escreverem | visível **só** às duas partes; campo livre, com o aviso de sempre na interface |
| `messages` | o que as partes escreverem | só as duas organizações; conversa profissional exige contexto |
| `notifications` | destinatário (pessoa) | lida só pela própria pessoa; preferência por grupo e canal |
| `domain_events` | ator e organizações | sem dado pessoal no corpo do fato |
| `professional_experiences` | nome da pessoa e da organização citada | entra no público **só** depois de confirmada |
| `enforcement_actions` | alvo e quem decidiu | o alvo vê a sua; o denunciante **nunca** é revelado |
| `price_change_notices` | organização avisada | append-only, exceto o "ciente" |

### Direitos do titular nas tabelas novas

A exportação (`/v1/privacy/export`) e a anonimização (`/v1/privacy/delete-account`) continuam valendo. Duas notas
honestas:

1. **A exportação ainda não inclui as entidades novas da rede** (relações, propostas, recados, perfil público). É
   pendência declarada, não esquecimento: a exportação é por **usuário**, e esses registros pertencem a
   organizações — definir o que de uma proposta entre duas organizações pertence ao titular pessoa física é decisão
   jurídica antes de ser técnica.
2. **Fato de rede é append-only e não é apagado** pela anonimização; o que acontece é a pseudonimização do ator,
   como já ocorre no ledger. Apagar o fato apagaria também a história da contraparte, que não pediu nada.

### Pendências de privacidade desta rodada

| Pendência | Classificação |
|---|---|
| Exportação não cobre relações, propostas, recados e perfil público | **AMARELO** — declarada acima |
| Política de privacidade não descreve ainda a página pública nem a rede | **AMARELO** — texto jurídico pendente |
| RIPD para a superfície pública | **VERMELHO** — exige DPO nomeado |
| DPO nomeado, ROPA formal | **VERMELHO** — inalterado desde a v0.11.0 |

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

## Camada de confiança (v0.14.0)
| Requisito | Estado | Evidência | Pendência |
|---|---|---|---|
| Minimização na identificação | GREEN | guarda-se a **referência** ao documento no cofre e o resultado da conferência; **nunca** número de documento, imagem extraída ou vetor biométrico (ADR 106) | — |
| Minimização na página pública | GREEN | payload curado na criação do registro; nome de pessoa só em assinatura profissional com credencial verificada; teste prova ausência de e-mail, identificador e nome nos outros papéis | revisão do DPO sobre o nome profissional exposto |
| Biometria | GREEN (por ausência) | não implementada; nenhum dado biométrico é armazenado nem processado | se vier provedor, exige base legal própria e avaliação de impacto |
| Finalidade da verificação pública | GREEN | a organização decide publicar o código; o terceiro vê apenas o necessário para conferir autenticidade | — |
| Localização de organização/profissional | GREEN | só é pública com **consentimento registrado com data** (CHECK no banco) e com precisão declarada | orientar a usar precisão por cidade quando o endereço é residencial |
| Rastreabilidade | GREEN | cadeia de custódia por objeto + `audit_events`, sem segredo e sem conteúdo do documento | — |
| Retenção | **YELLOW** | `trust_events`, `verifiable_records`, `signature_challenges` e `identity_documents` **sem expurgo automático** | **VALIDAÇÃO JURÍDICA NECESSÁRIA**: prazo por tipo. Atenção: cadeia de custódia e assinatura têm valor probatório — apagar pode ser pior que guardar |
| Eliminação a pedido | **YELLOW** | a exclusão de conta anonimiza o usuário; a assinatura e a cadeia **permanecem** (são prova de um ato) | definir com o jurídico o que é anonimizável sem destruir a prova |
| Dado de terceiro em documento enviado | **YELLOW** | o cofre não inspeciona conteúdo; um documento de identidade contém dado sensível de quem o enviou | orientação ao usuário + prazo de descarte do documento após a conferência |
| Compartilhamento | GREEN | a verificação pública não compartilha com terceiro definido: é consulta iniciada por quem tem o código | — |
