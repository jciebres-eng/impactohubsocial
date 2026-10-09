# Cibersegurança, identidade, auditoria e confiança — v0.26.0

**Data de corte da pesquisa:** 8 de outubro de 2026.  
**Escopo:** Marco Civil da Internet, Lei Geral de Proteção de Dados, PNCiber/E-Ciber, normas e guias oficiais aplicáveis, NIST CSF 2.0, OWASP ASVS/Top 10, identidade, autenticação multifator, logs, incidentes, backup, RLS, segregação multitenant e evidência auditável.  
**Natureza:** relatório de pesquisa e de requisitos de produto. Não é parecer jurídico personalizado, certificação, auditoria independente ou declaração de conformidade.

## Escopo e classificação das fontes

Este relatório separa quatro planos que não podem ser misturados:

1. **Lei e regulamento vigente.** Incluem a Lei nº 12.965/2014 (Marco Civil da Internet), sua regulamentação pelo Decreto nº 8.771/2016 na redação atual, a Lei nº 13.709/2018 (LGPD), a Resolução CD/ANPD nº 15/2024 e, conforme o contexto institucional, os Decretos nº 11.856/2023 e nº 12.573/2025. São obrigações jurídicas ou atos normativos, mas sua incidência concreta depende do papel exercido, do tratamento realizado, do setor regulado e dos fatos.
2. **Orientação administrativa.** O Guia de segurança da ANPD para agentes de pequeno porte e as páginas do GSI/ANPD explicam controles e procedimentos. Orientação não deve ser promovida como lei, mas é evidência relevante de diligência e de expectativa regulatória.
3. **Padrões voluntários e documentação técnica.** NIST CSF 2.0, NIST SP 800-63B-4, SP 800-61 Rev. 3, SP 800-92, SP 800-34 Rev. 1 e SP 800-57 Part 1, OWASP ASVS/Top 10, documentação do PostgreSQL e guia da AWS não substituem a legislação brasileira. Servem para converter obrigações abertas, como segurança adequada e gestão de risco, em controles verificáveis.
4. **Hipótese de produto.** A associação entre esses controles e os motores `TRUST_SECURITY`, `SECURITY_AUDIT`, `AUTHORIZATION`, `KEY_ROTATION` e `TRUST_TESTING` é uma especificação de engenharia do IMPACTO. Ela pode tornar alegações mais demonstráveis, mas não transforma o produto em certificado, provedor de identidade, autoridade de certificação ou órgão regulador.

## Estado atual do release e correções necessárias

O v0.26.0 está documentado como **GO WITH CONDITIONS**. O relatório de execução registra 2.295 testes na regressão final, 14 jornadas com 195 passos, 220 rotas visitadas no Chromium e a pilha do zero exercitada no CI. A arquitetura declarada é Starlette + PostgreSQL, com RLS em 324 de 325 tabelas, 677 políticas e cadeias de hash em auditoria, razão, valor e confiança. A própria documentação afirma que nenhum sistema conectado à internet é “impossível de invadir”. [Artefatos internos: [`FINAL_EXECUTION_REPORT.md`](../../FINAL_EXECUTION_REPORT.md), [`FINAL_EXECUTION_AUDIT.md`](../../FINAL_EXECUTION_AUDIT.md).]

Isso é uma base técnica relevante, mas não é uma conclusão jurídica de conformidade. Há diferenças entre o que foi provado localmente e o que seria necessário para operação pública. A auditoria final ainda registra dependências externas bloqueadas: pagamento real, nota fiscal, assinatura qualificada/ICP-Brasil ou gov.br, biometria/KYC, SMS/WhatsApp, provedores de integração, minutas jurídicas aprovadas e endereço público. A identidade é `PARTIAL`; biometria, KYC e gov.br não estão ligados nem simulados. [Artefatos internos: [`FINAL_EXECUTION_REPORT.md`](../../FINAL_EXECUTION_REPORT.md) §21 e §25; [`FINAL_EXECUTION_AUDIT.md`](../../FINAL_EXECUTION_AUDIT.md) §8–§10.]

O estado de segurança do release deve ser corrigido e republicado em uma fonte única, porque os documentos existentes têm rótulos de versões anteriores: `TRUST_SECURITY.md` é v0.14.0, `SECURITY_AUDIT.md` é v0.18.1, `docs/SECURITY.md` é v0.7.0 e `SECURITY_FINAL_CHECKLIST.md` é v0.15.0. Eles continuam úteis como histórico de controles e defeitos encontrados, mas não podem ser lidos isoladamente como declaração do v0.26.0. A nova base de conhecimento deve apontar sempre para o relatório de execução atual, para a evidência gerada e para a data de validade de cada afirmação.

Há também uma correção normativa imediata: a E-Ciber de 2020 não é a estratégia vigente. O Decreto nº 12.573/2025 revogou expressamente o Decreto nº 10.222/2020 e instituiu a E-Ciber atual, com quatro eixos. A página oficial do GSI confirma a substituição. [5] [6] Portanto, qualquer texto do release que trate o Decreto nº 10.222/2020 como vigente deve ser alterado para “histórico/revogado”; referências operacionais devem apontar para o Decreto nº 12.573/2025 e para a PNCiber do Decreto nº 11.856/2023.

### O que o release já demonstra, em termos estreitos

- **Autenticação e MFA:** senha com scrypt, TOTP cifrado, códigos de recuperação de uso único, MFA obrigatório para administração, rotação e revogação de refresh tokens, proteção CSRF, OIDC com `state`/`nonce` e reautenticação para operações sensíveis. Os testes da v0.23.0 registraram correção de reuso de TOTP e de expiração de família de refresh token. Isso sustenta “há controles e testes automatizados para estes cenários”, não “MFA resistente a phishing” nem “identidade verificada” em sentido forte.
- **Autorização:** `AUTHORIZATION.md` separa autenticação, contexto, autorização e entitlement; registra 14 papéis internos, catálogo de 43 permissões, step-up e quatro olhos no banco. A mesma documentação registra lacunas: ABAC por atributo de linha além de `org_id`, risco de IP/dispositivo e sessão interna dedicada mais curta. Ela também registra que 150 de 212 rotas `auth="admin"` permaneciam sem permissão nomeada no estado documentado. O release v0.26.0 deve atualizar essa contagem ou marcá-la como “não revalidada”, nunca apagá-la por diferença de versão.
- **Segregação multitenant:** há RLS e testes de matriz A→recurso de B, inclusive por SQL direto; há funções `SECURITY DEFINER` com portões internos. Entretanto, a documentação do PostgreSQL lembra que owner, superuser e `BYPASSRLS` podem atravessar RLS e que `TRUNCATE` não está sujeito a ela. [22] O relatório atual registra a remoção de `FORCE RLS` para não quebrar o backup do owner. A conclusão correta é “isolamento testado sob papéis e caminhos definidos”, não “RLS, sozinha, impede todo acesso cruzado”.
- **Auditoria:** `audit_events` é append-only para o papel da aplicação, tem hash encadeado, ator, status, severidade, origem, correlação, antes/depois redigidos e verificação. `privileged_access_log` registra leitura privilegiada, e exportação da trilha é auditada. Isso atende a uma hipótese forte de evidência auditável, desde que a retenção, o acesso ao ambiente, a cobertura de eventos e a restauração sejam demonstrados continuamente.
- **Chaves:** `KEY_ROTATION.md` documenta inventário por finalidade, fingerprint sem guardar a chave, estados `active`/`decrypt_only`/`retired`, recifragem idempotente e auditada. KMS/HSM, rotação automática por calendário e proteção fora do processo não estão implementados. O banco também não tem cifragem de coluna geral; a proteção em repouso depende da infraestrutura. [Artefato interno: [`KEY_ROTATION.md`](../../KEY_ROTATION.md).]
- **Backup e restauração:** o release afirma que `pg_dump`, restauração e integridade das cadeias foram testados. A dívida técnica histórica ainda registra que cópia off-site, RPO e RTO não foram decididos/provados como objetivos operacionais. Até que haja evidência atual de destino externo, restauração a partir dele e metas aprovadas, o claim deve ser “backup e restauração testados neste ambiente”, e não “disaster recovery garantido”.

## Mapa de obrigações e consequências de produto

| Fonte e natureza | Regra ou orientação que sustenta | Consequência para o IMPACTO | Estado/ação do v0.26.0 |
|---|---|---|---|
| Marco Civil, lei vigente [1] | A disciplina da internet inclui estabilidade, segurança e funcionalidade por medidas técnicas compatíveis com padrões internacionais e boas práticas; a guarda e disponibilização de registros, dados pessoais e comunicações devem preservar intimidade, sigilo e privacidade. | Classificar o IMPACTO como provedor de aplicação, ou outro papel, por fluxo; documentar quais registros são coletados, finalidade, acesso e resposta a ordem judicial. | Há logs e controles, mas falta uma matriz jurídica de papéis, registros e responsáveis para o release público. |
| Marco Civil, art. 15 [1] | Provedor de aplicações pessoa jurídica, profissional e com fins econômicos deve guardar registros de acesso a aplicações sob sigilo, em ambiente controlado e seguro, por seis meses; disponibilização depende de autorização judicial. | Separar registro de acesso de log de segurança; aplicar retenção, acesso restrito, exportação estruturada e fluxo de ordem judicial. Não apagar o registro legal por confundi-lo com telemetria operacional. | O produto possui retenção e trilha, mas não deve afirmar que a retenção do art. 15 está fechada sem validar escopo, data de início, campos e procedimento jurídico. |
| Marco Civil, arts. 10–11 [1] | Guarda/disponibilização de registros e dados deve preservar intimidade; operações com um ato no Brasil respeitam lei brasileira e direitos de privacidade, dados e sigilo. | Registro de requisição, base legal/ordem judicial, titularidade do pedido, escopo e resposta; minimização e acesso por necessidade. | Parcial; a documentação de privacidade ainda marca base legal, RIPD/DPIA, contratos com operadores e encarregado como decisões pendentes. |
| Decreto nº 8.771/2016, texto atualizado [2] | Art. 13 exige controle estrito de acesso, responsabilidades e privilégios exclusivos; autenticação dupla como exemplo; inventário detalhado de acessos com momento, duração, identidade e arquivo; criptografia ou medida equivalente. | `AUTHORIZATION` deve emitir decisão individualizada; `SECURITY_AUDIT` deve registrar leitura e mudança com actor, duração/início/fim, objeto e motivo; MFA não pode ser só uma tela. | Boa aderência estrutural com MFA, papéis e `privileged_access_log`; confirmar duração, “arquivo acessado” e cobertura de todos os registros. |
| Decreto nº 8.771/2016, art. 13 §2º e arts. 15–16, redação atual [2] | Reter a menor quantidade possível e eliminar quando terminada a finalidade ou o prazo legal; manter dados em formato interoperável/estruturado; divulgar padrões de segurança de forma clara, preservando segredo empresarial. | Política de retenção por campo e finalidade; exportação estruturada; página pública de segurança sem expor segredos; prova de eliminação ou anonimização. | Existe matriz de retenção e exportação; falta documento público atual que explique escopo, limites e papel do provedor. |
| Decreto nº 12.975/2026 [3] | Inclui porta lógica de origem quando necessária à identificação inequívoca e deveres gerais de provedores de aplicações, inclusive sede/representação, canal permanente e segurança/transparência, conforme o âmbito de aplicação. | Fazer análise de aplicabilidade por papel e volume; se aplicável, preparar capacidade de registro de porta lógica e fluxo de atendimento. Não inventar guarda de porta lógica se o IMPACTO não for provedor de conexão ou não precisar desse dado. | Não tratado especificamente no v0.26.0; é lacuna jurídica e de arquitetura a ser decidida antes da publicação pública. |
| LGPD, arts. 44, 46–50 [8] | Tratamento irregular inclui segurança inferior à expectativa razoável; medidas técnicas e administrativas devem proteger contra acesso não autorizado, perda, alteração e tratamento ilícito desde a concepção até a execução; segurança permanece após o término; incidente relevante deve ser comunicado; sistemas devem atender segurança, boas práticas e governança. | Privacy/security by design, matriz de riscos, incident response, retenção, controle de fornecedores, RIPD quando aplicável, prova de efetividade e governança contínua. | Existem controles de minimização, RLS, logs e incidentes em nível técnico; RIPD, DPO/encarregado, bases legais e fornecedores estão pendentes. |
| Resolução CD/ANPD nº 15/2024 [10] | Incidente que possa causar risco/dano relevante deve ser comunicado; prazo de três dias úteis contado do conhecimento de que afetou dados pessoais; titular também; comunicação contém categorias, titulares, medidas, riscos, mitigação, datas, controlador/operador e causa; todo incidente, comunicado ou não, deve ser registrado por cinco anos. | Criar registro durável de incidente com relógio de conhecimento, avaliação de risco, dados afetados, decisões, notificações e retenção mínima de cinco anos; workflow do controlador e operador; evidência de comunicação. | A plataforma tem detecção e alerta, mas o release não demonstra um registro regulatório dedicado com todos os campos e retenção de cinco anos. |
| Resolução CD/ANPD nº 2/2022 [9] | Pequeno porte pode usar registro simplificado e política simplificada, mas deve adotar medidas essenciais e necessárias; prazos de incidentes podem ser em dobro, salvo exceções. | Não assumir que “pequeno porte” elimina segurança, registro ou canal; parametrizar prazo apenas após classificar o agente e documentar a base. | A classificação do controlador/operador do produto não está decidida; tratar os prazos normais como default até decisão jurídica. |
| PNCiber, Decreto nº 11.856/2023 [7] | Política pública orienta segurança; princípios incluem direitos fundamentais, prevenção, resiliência e cooperação; objetivos incluem confidencialidade, integridade, autenticidade, disponibilidade e gestão de riscos; CNCiber propõe prevenção, detecção, análise e resposta. | Usar CIA+A, risco e resposta como vocabulário de governança e produto; não alegar que o decreto certifica a plataforma privada. | Alinhamento conceitual; não é evidência de conformidade ou autorização regulatória. |
| E-Ciber atual, Decreto nº 12.573/2025 e GSI [5] [6] | Estratégia atual tem eixos cidadão/sociedade; serviços essenciais/infraestruturas críticas; cooperação; soberania/governança; inclui autenticação, contingência, testes, incidentes e maturidade. Revoga 10.222/2020. | Atualizar base normativa, claims e testes para citar 2025; separar metas nacionais de obrigação contratual da plataforma. | Correção urgente de documentação; 10.222 deve ser histórico, não vigente. |
| NIST CSF 2.0 [13] | Taxonomia voluntária de resultados para qualquer organização, com GOVERN, IDENTIFY, PROTECT, DETECT, RESPOND e RECOVER; não prescreve como alcançar os resultados. | Criar perfil do IMPACTO: ativos/tenants/identidades; políticas; proteção; detecção; resposta; recuperação; evidências e lacunas por outcome. | Aplicação recomendada; não usar “NIST-compliant” como certificação. |
| NIST SP 800-63B-4 [14] | Requisitos técnicos de autenticação e gestão de autenticadores em três níveis de garantia; edição de julho de 2025 substitui 800-63B anterior. | Mapear cada fluxo a assurance, registro de autenticador, recuperação, reautenticação, resistência a phishing e revogação. | TOTP e OIDC são existentes; passkeys/WebAuthn e proofing forte não. Não alegar nível de garantia NIST sem avaliação formal. |
| NIST SP 800-61 Rev. 3 [15] | Integra resposta a incidentes ao CSF 2.0 e cobre preparação, detecção, resposta, recuperação e melhoria. | Plano, papéis, severidade, relógios, coleta forense, comunicação, lições aprendidas e exercícios. | Detecção/alerta existem; plano operacional e exercício externo ainda não demonstrados. |
| NIST SP 800-92 [16] | Guia institucional para infraestrutura, coleta, análise e processos de gestão de logs. | Inventário de fontes, sincronização temporal, normalização, proteção, retenção, correlação e uso em alerta. | `audit_events` é forte; 10 motores de leitura não deixam rastro durável e métricas não cobrem todos os motores. |
| NIST SP 800-34 Rev. 1 [17] | Guia de planejamento de contingência e resiliência; orienta identificar prioridades, dependências e recuperação. | BIA, RPO/RTO, backup externo, restauração, dependências de chave e exercícios periódicos. | Restauração local provada; off-site, metas e teste de recuperação a partir do destino externo permanecem lacunas. |
| NIST SP 800-57 Part 1 Rev. 5 [18] | Recomendação de gestão de chaves: proteção, inventário, ciclo de vida, uso, comprometimento, recuperação e destruição. | `KEY_ROTATION` deve ter custodiante, versionamento, rotação, revogação, perda, comprometimento, criptoperíodo e prova de restauração. | Inventário e recifragem existem; KMS/HSM e rotação de calendário não. |
| OWASP ASVS 5.0.0 [19] | Padrão aberto voluntário que fornece requisitos de desenvolvimento e base de teste de controles técnicos; referências devem identificar versão. | Usar versão fixa e IDs nos requisitos de autenticação, autorização, criptografia, logging, integridade e APIs; cada requisito deve apontar teste/evidência. | Não há matriz ASVS v5 formal do release; criar antes de claim de verificação. |
| OWASP Top 10:2025/2021 [20] [21] | Catálogos de conscientização de riscos, não lei; destacam controle de acesso, configuração, cadeia de software, criptografia, autenticação, integridade e logging/alerting. | Usar como triagem e linguagem de risco, não como checklist de conformidade ou certificado. | A base cobre vários riscos, mas a versão e os resultados precisam ser fixados em matriz. |
| PostgreSQL 18 docs [22] | RLS exige policy para acesso normal; sem policy o padrão é negar; owner normalmente, superuser e `BYPASSRLS` sempre atravessam; `FORCE RLS` sujeita owner; `TRUNCATE` não é RLS. | Separar owner/migração/app; `NOBYPASSRLS`; testar RLS por API e SQL direto; proteger operações fora de RLS; controlar `SECURITY DEFINER` e `search_path`. | O release removeu FORCE para manter backup do owner e testa portões; a exceção `chain_heads` e operações do owner precisam aparecer na matriz pública de limites. |
| AWS Prescriptive Guidance [23] | Tenant isolation não é sinônimo de autenticação/autorização; usuário autenticado pode receber autorização para recurso do tenant errado sem isolamento explícito. | Modelar isolamento como controle independente em banco, API, jobs, cache, exportação, arquivos e integrações; registrar PDP/PEP e decisões. | RLS e testes cruzados cobrem o núcleo; cache, filas, armazenamento e integrações reais exigem provas específicas antes da publicação. |

## Requisitos de produto

### 1. `TRUST_SECURITY`: confiança como claim verificável

`TRUST_SECURITY` não deve ser uma página com selo genérico. Deve publicar uma **matriz de afirmação → controle → evidência → escopo → data de validade**. Cada linha precisa dizer:

- qual propriedade é alegada: confidencialidade, integridade, autenticidade, disponibilidade, não repúdio técnico ou segregação;
- qual ativo e qual tenant estão abrangidos;
- qual papel e qual caminho foram testados;
- qual evidência foi gerada, com hash, versão do código/esquema, data e executor;
- o que não foi coberto: owner do banco, infraestrutura, provedor externo, cliente, dispositivo, rede, pentest ou volume de produção;
- quando a evidência expira e qual evento exige revalidação.

Formulação recomendada: “O v0.26.0 contém RLS e testes adversariais de isolamento em PostgreSQL para os cenários documentados; a evidência não equivale a pentest, certificação, invulnerabilidade ou garantia para qualquer configuração.” Formulação proibida: “tenant isolation garantido em todos os ambientes”.

### 2. `AUTHORIZATION`: decisão separada de identidade

A porta deve conservar quatro decisões separadas: **autenticação** (quem apresenta autenticador), **contexto** (em nome de qual organização), **autorização** (qual ação sobre qual recurso) e **entitlement** (qual recurso está contratado). A autorização deve ser avaliada no servidor, no banco e nos jobs, e não apenas no menu ou no frontend.

Requisitos mínimos:

- escopo de tenant derivado de sessão/servidor, nunca de `org_id` livre enviado pelo cliente;
- `impacto_app` sem `SUPERUSER` e sem `BYPASSRLS`; owner de migração separado da aplicação; política de `FORCE RLS` decidida por tabela, sem quebrar backup silenciosamente;
- policies explícitas por `SELECT`, `INSERT`, `UPDATE` e `DELETE`, com `WITH CHECK` para impedir criação em tenant errado;
- teste de leitura, escrita, exportação, arquivo, cache, job, webhook e `SECURITY DEFINER` entre A e B;
- ABAC para recurso quando a regra depender de projeto, relação, parte, estado ou atributo além de `org_id`; RBAC sozinho não cobre esse caso;
- step-up e MFA para administração, exportação de auditoria, alteração de chaves, alteração de alçada e operações financeiras;
- log de decisões permitidas e recusadas, sem registrar segredo nem corpo desnecessário;
- sincronização menu↔rota↔permission catalog, com teste que não seja tautológico: o teste deve chamar a rota real com o papel real.

A distinção da AWS entre isolamento e autorização é essencial: ser um usuário legítimo não elimina o risco de acessar dados de outro tenant. [23]

### 3. `SECURITY_AUDIT`: trilha, não narrativa

O sistema de auditoria deve registrar, na mesma transação do fato crítico, pelo menos: ator e tipo de ator; tenant; ação; objeto; decisão; motivo; origem; sessão; request/correlation ID; data/hora UTC; estado anterior e posterior redigidos; versão da política; resultado; severidade; e vínculo com incidente ou aprovação. Deve registrar também leitura privilegiada, tentativa recusada, exportação e mudança de permissão.

A trilha precisa ter controles independentes:

- append-only por gatilho para a aplicação;
- hash encadeado ou mecanismo de integridade equivalente, com verificador que informa a primeira quebra;
- proteção contra `TRUNCATE`, não apenas contra `UPDATE`/`DELETE`;
- `SECURITY DEFINER` com `search_path` fixo e escopo explícito;
- segregação entre quem administra o produto, quem usa a organização e quem audita;
- retenção por finalidade, anonimização compatível com direitos do titular e preservação do fato necessário para obrigação legal;
- exportação limitada, estruturada, com a própria exportação auditada;
- alerta operacional para eventos de alto risco, não apenas registro consultável.

O Decreto nº 8.771 exige inventário detalhado de acessos a registros, incluindo momento, duração, identidade e arquivo acessado. [2] A tabela atual do IMPACTO aproxima-se disso, mas a evidência deve confirmar se a duração é realmente medida e se `object_type/object_id` cobre o conceito de arquivo quando o recurso for documento.

### 4. `KEY_ROTATION`: ciclo de vida, não só recifragem

O motor deve manter, por finalidade e ambiente: versão, fingerprint, estado, criptoperíodo, custodiante, data de ativação, data de aposentadoria, motivo, dependências, algoritmo, política de uso e evidência de rotação. O segredo nunca deve aparecer em banco, log, manifesto, exportação, teste ou mensagem de erro.

A próxima versão deve adicionar:

- provedor de KMS/Key Vault/HSM ou decisão documentada de risco sobre `EnvKeyProvider`;
- rotação planejada e disparada por calendário, comprometimento, mudança de operador ou incidente;
- janela `decrypt_only`, recifragem idempotente, contagem de falhas e prova de leitura pós-rotação;
- teste de restauração de backup que dependa de chave antiga e nova;
- revogação e destruição com evidência, inclusive para credenciais de integração;
- plano de perda de chave sem backdoor: reconfiguração de MFA, bloqueio e recuperação autorizada.

O NIST SP 800-57 trata gestão de chaves como ciclo de vida, incluindo proteção, inventário, comprometimento, recuperação e destruição, e não como simples troca de variável de ambiente. [18]

### 5. `TRUST_TESTING`: o teste como limite do claim

`TRUST_TESTING` deve ser uma suíte de invariantes com escopo declarado, não um contador de testes. Todo claim de segurança deve apontar para um teste que falha quando o controle é removido, um artefato de execução e uma limitação.

A matriz mínima é:

| ID | Invariante | Evidência exigida | Situação v0.26.0 |
|---|---|---|---|
| TT-01 | Usuário de A não lê/escreve/exporta/baixa recurso de B | API, SQL direto, arquivo, job e integração, com dados de A e B reais | Parte forte no banco/API; ampliar para caches, jobs e integrações reais. |
| TT-02 | Owner/superuser/BYPASSRLS não é caminho ordinário de aplicação | catálogo de roles, boot fail-fast, `pg_authid`/configuração protegida e teste de migração | Há portões e separação; documentar a exceção `chain_heads` e operações de backup. |
| TT-03 | Toda rota sensível tem autorização granular, step-up/MFA quando exigido e log de decisão | varredura de rotas + chamada real com cada papel + teste menu↔rota | Há 75 permissões nomeadas e histórico de 150/212 admin sem nome; atualizar e fechar ou marcar. |
| TT-04 | MFA e sessão resistem a reuso previsível | TOTP usado uma vez, recovery code usado uma vez, refresh reuse revoga família, idade máxima não se renova | Provado em testes da v0.23.0; ainda não equivale a WebAuthn/phishing resistance. |
| TT-05 | Auditoria detecta adulteração e não é apagada por `TRUNCATE` | desabilitar gatilho apenas em teste controlado, adulterar linha/truncar e verificar falha | Cadeia e anti-TRUNCATE documentados; repetir no esquema final v0.26.0. |
| TT-06 | Rotação preserva leitura legítima e não expõe chave | old/new key, `decrypt_only`, recifragem parcial/falha, inventário e logs redigidos | Recifragem idempotente provada; KMS/HSM e calendário ausentes. |
| TT-07 | Backup restaura integridade e não inclui dado proibido | dump íntegro/adulterado, banco descartável, papéis reais, hash de cadeia, restauração externa | Restauração local provada; falta prova off-site/RPO/RTO. |
| TT-08 | Incidente gera registro regulatório completo e relógio de comunicação | evento de conhecimento, classificação, campos mínimos, 3 dias úteis, titular/ANPD, complemento, retenção 5 anos | Alertas existem; registro específico e workflow regulatório não demonstrados. |
| TT-09 | Controles de aplicação cobrem OWASP ASVS v5 | matriz de requisito versionado, testes automatizados, revisão manual e DAST/pentest | Não há matriz ASVS formal nem pentest independente. |
| TT-10 | Logs de todas as fontes críticas chegam e geram alerta útil | inventário de produtores, métrica, alerta acionável, teste de evento morto e replay | 16 alertas e catracas existem; dez motores de leitura sem rastro durável e coletor de produção pendentes. |

## Requisitos de dados e evidência

### Inventário mínimo

O produto deve manter um inventário de dados que relacione: categoria; titular; controlador/operador; finalidade; base jurídica a validar; origem; tenant; local de armazenamento; fornecedor; criptografia; retenção; acesso; exportação; eliminação/anonimização; risco; evidência e responsável. O registro deve distinguir:

- **registro de acesso a aplicação** sujeito ao Marco Civil;
- **log de segurança** para detectar e responder;
- **trilha de auditoria** para provar ação/decisão;
- **registro regulatório de incidente**;
- **dado de negócio/evidência**;
- **segredo, autenticador ou material de chave**.

Misturar as categorias produz retenção errada, exportação excessiva e claims indevidos.

### Identidade e autenticadores

Para cada usuário e autenticador, guardar apenas o necessário: método, estado, versão, data de vinculação, última utilização, contador/janela quando necessário, recovery material em hash, eventos de revogação e prova de reautenticação. Segredo TOTP pode ser cifrado para validação, mas não deve ser logado ou exportado. Identity proofing humano, documento, KYC, biometria e gov.br precisam de campos de nível, fonte, data, revisor, escopo e expiração; o melhor nível de um administrador não deve ser apresentado como verificação da organização inteira.

O NIST SP 800-63B-4 descreve requisitos de autenticadores e níveis de garantia, mas seu escopo institucional não confere automaticamente um nível ao IMPACTO. [14] Portanto, usar `identity_level` interno é hipótese de produto, não “NIST AAL” ou “identidade oficial”.

### Tenant e autorização

Cada linha sensível deve ter `org_id` ou uma relação de pertencimento explicitamente verificável. Recursos compartilhados devem registrar visibilidade, origem da decisão, partes autorizadas, data de início/fim e motivo. Políticas de RLS precisam ser enumeráveis por tabela e operação; uma tabela sem RLS deve ter razão documentada, exposição intencional, owner controlado e teste de não-vazamento.

Para arquivos, tenant deve existir na chave de armazenamento, no registro, na policy, no token de download e no job de exclusão. Para filas, cache e exportações, o tenant deve ser parte da chave e da verificação, não apenas do payload. Para funções `SECURITY DEFINER`, o tenant deve ser derivado de identidade e visibilidade no próprio corpo da função, como os novos portões do v0.26.0 tentam fazer.

### Incidentes

O registro deve conter, no mínimo, os campos da Resolução nº 15/2024: data de conhecimento; circunstâncias; natureza/categoria dos dados; titulares; avaliação de risco/danos; correção/mitigação; forma e conteúdo da comunicação; justificativa de não comunicação; medidas anteriores e posteriores; controlador; operador; causa e total de titulares tratados na atividade afetada. [10]

O relógio deve começar quando o controlador conhece que o incidente afetou dados pessoais, não quando a investigação termina. O produto pode criar estados `detected`, `triaged`, `contained`, `reported`, `closed`, mas não deve apagar a versão inicial, o raciocínio da classificação ou a evidência da comunicação.

### Backup e chaves

O backup deve ser criptografado, identificado por versão de esquema, data, origem, hash e dependências de chaves. O catálogo precisa informar se é cópia local, externa, imutável, versionada e recuperável sem o mesmo host. RPO e RTO são decisões do responsável pelo serviço; o sistema pode medir e demonstrar, mas não inventar metas.

Um backup que restaura o banco, mas não permite decifrar TOTP, credenciais ou trilhas porque a chave foi perdida, não é recuperação completa. Por isso, o teste TT-07 deve usar o inventário de `KEY_ROTATION` e comprovar a recuperação autorizada de dados cifrados.

## Mapa NIST/OWASP para a arquitetura

O NIST CSF 2.0 oferece seis funções, não uma lista fechada de controles. [13] Uma tradução de produto adequada é:

- **GOVERN:** papéis, risco, políticas, exceções, contratos, claims, revisão de fontes e decisões de retenção;
- **IDENTIFY:** inventário de ativos, dados, tenants, identidades, fornecedores, chaves e dependências;
- **PROTECT:** `AUTHORIZATION`, MFA, RLS, criptografia, gestão de chaves, desenvolvimento seguro, minimização e backup;
- **DETECT:** `SECURITY_AUDIT`, logs, métricas, alertas de reuso de sessão, falha de policy, alteração de chave e restauração;
- **RESPOND:** `TRUST_TESTING` de incidente, contenção, revogação, comunicação ANPD/titular quando aplicável, preservação de evidência;
- **RECOVER:** restauração, validação de hash, reativação segura, lições aprendidas, atualização de risco e teste de continuidade.

O ASVS v5 deve ser adotado como matriz de verificação versionada, não como etiqueta. [19] Pelo menos os capítulos de autenticação, controle de acesso, proteção de dados, criptografia, validação de entrada, logging, APIs e configuração devem apontar para testes. O Top 10:2025 é triagem de risco: A01 (Broken Access Control), A04 (Cryptographic Failures), A07 (Authentication Failures), A08 (Software or Data Integrity Failures) e A09 (Security Logging and Alerting Failures) são especialmente relevantes. [20] A edição 2021 deve ficar como histórico de compatibilidade, não como versão “atual”. [21]

## Claims proibidos e linguagem permitida

| Não publicar | Linguagem permitida e verificável |
|---|---|
| “100% seguro”, “impossível de invadir”, “invulnerável” | “Controles e testes automatizados cobrem os cenários descritos; não há garantia de ausência de vulnerabilidades.” |
| “Em conformidade com LGPD/MCI/E-Ciber” sem escopo, papel e revisão | “Implementa controles técnicos relacionados a [artigo/guia], sujeitos à validação jurídica e operacional.” |
| “E-Ciber 2020 vigente” | “O Decreto nº 10.222/2020 é histórico/revogado; a E-Ciber vigente é a do Decreto nº 12.573/2025.” [5] |
| “Auditado”, “certificado”, “SOC 2/ISO/NIST compliant” | “Revisado por [escopo/data]” ou “teste interno [artefato/data]”; certificação só com organismo e escopo reais. |
| “RLS garante isolamento total de tenants” | “RLS e testes cruzados foram executados nas tabelas/cenários enumerados; owner/BYPASSRLS, funções, jobs, cache e storage têm escopos próprios.” |
| “Todas as rotas administrativas têm permissão granular” | Só afirmar após fechar a matriz atual; o histórico registra rotas administrativas sem permissão nomeada. |
| “MFA resistente a phishing”, “identidade verificada”, “KYC”, “biometria”, “gov.br” | “MFA TOTP/OIDC implementado e testado”; proofing forte só após provedor, fluxo e evidência reais. |
| “Chaves em KMS/HSM”, “banco criptografado” | “Inventário e recifragem com provedor configurado; KMS/HSM ausente”; “colunas listadas são cifradas, o restante depende da infraestrutura.” |
| “Zero vulnerabilidades/CVEs” | “Auditoria de dependências executada em [run/data] e achados tratados conforme exceções.” |
| “Backup seguro/disaster recovery garantido” | “Backup e restauração local testados”; só falar de recuperação operacional após off-site, RPO/RTO e exercício. |
| “Incidentes serão sempre evitados” | “Há detecção, contenção e processo de resposta; nenhum controle elimina risco.” |
| “Assinatura qualificada/ICP-Brasil” ou “não repúdio jurídico” | “Assinatura interna com hash/código de uso único; assinatura qualificada não ligada.” |
| “Alegação, selo ou Ready é certificação” | “Estado derivado com critérios, contagens, fonte e hash; não é selo/certificação.” |

## Lacunas prioritárias e ordem de correção

1. **Atualizar a base normativa:** trocar referências operacionais ao Decreto nº 10.222/2020 por nº 12.573/2025; registrar o Decreto nº 12.975/2026 e fazer análise de aplicabilidade do art. 15-A e dos deveres de provedor de aplicação.
2. **Unificar a fonte de verdade:** publicar uma `SECURITY_TRUST_BASELINE_v0.26.0` com números, data, testes, escopo e status; marcar documentos v0.14–v0.23 como históricos.
3. **Fechar inventário e retenção:** separar logs do Marco Civil, logs de segurança, auditoria e incidentes; conferir seis meses para registros de acesso quando aplicável e cinco anos para registros de incidentes; validar eliminação/anonimização.
4. **Criar o registro regulatório de incidentes:** incluir relógio de conhecimento, classificação, comunicação, evidência, complemento e retenção de cinco anos; definir controlador, operador, encarregado/canal e RACI.
5. **Provar backup externo:** configurar destino off-site, criptografia, imutabilidade/versionamento, restauração independente e RPO/RTO aprovados. O histórico de dívida técnica não fecha esses itens.
6. **Endurecer chaves:** contratar/selecionar KMS/HSM ou registrar decisão formal de risco; implementar calendário/comprometimento, revogação, destruição e teste de restauração com chaves rotacionadas.
7. **Completar autorização:** atualizar o inventário de rotas, fechar permissões sem nome, decidir ABAC por recurso e testar jobs, cache, files, webhooks, exportações e `SECURITY DEFINER`.
8. **Formalizar ASVS e pentest:** criar matriz ASVS v5 com IDs versionados; executar SAST/DAST, auditoria de dependências em ambiente com registries e teste de intrusão independente. O teste interno não deve ser anunciado como auditoria externa.
9. **Fechar observabilidade:** fornecer coletor, retenção, alertas acionáveis, on-call e exercício de falha; dar rastro durável ou justificar formalmente os dez motores de leitura sem observabilidade.
10. **Resolver identidade e fornecedores:** decidir escopo de proofing, WebAuthn/passkeys, IdP, KMS, storage, antivírus, SMTP e deployment público; nenhum desses componentes deve ser simulado em claim de produção.
11. **Revisar privacidade e governança:** definir controlador/operador, encarregado ou canal, bases legais, RIPD/DPIA quando aplicável, contratos de operador, dados transfronteiriços e política de retenção.
12. **Exercitar continuidade:** tabletop de incidente, restauração, rotação, perda de chave, tenant breach e comunicação; guardar evidências e lições aprendidas como eventos de auditoria.

## Artefatos internos consultados

- [`README.md`](../../README.md): estado e limites históricos do release.
- [`FINAL_EXECUTION_REPORT.md`](../../FINAL_EXECUTION_REPORT.md) e [`FINAL_EXECUTION_AUDIT.md`](../../FINAL_EXECUTION_AUDIT.md): estado v0.26.0, testes, GO WITH CONDITIONS e bloqueios externos.
- [`TRUST_SECURITY.md`](../../TRUST_SECURITY.md): controles da camada de confiança, v0.14.0, histórico e limitações.
- [`SECURITY_AUDIT.md`](../../SECURITY_AUDIT.md), [`SECURITY_FINAL_CHECKLIST.md`](../../SECURITY_FINAL_CHECKLIST.md) e [`docs/SECURITY.md`](../../docs/SECURITY.md): controles, testes e pendências em versões anteriores.
- [`AUTHORIZATION.md`](../../AUTHORIZATION.md): RBAC, permissões, step-up, quatro olhos e lacunas ABAC.
- [`AUDIT_ENGINE.md`](../../AUDIT_ENGINE.md): trilha, hash, correlação, redação e verificação.
- [`KEY_ROTATION.md`](../../KEY_ROTATION.md): inventário e rotação atual de chaves.
- [`docs/LGPD.md`](../../docs/LGPD.md), [`docs/LEGAL_FRAMEWORK.md`](../../docs/LEGAL_FRAMEWORK.md) e [`docs/PROCUREMENT.md`](../../docs/PROCUREMENT.md): privacidade, estado das minutas e requisitos de controle/documentação.

## Referências

[1]: https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2014/lei/l12965.htm "Presidência da República — Lei nº 12.965, de 23 de abril de 2014 — Marco Civil da Internet — 23/04/2014; sustenta princípios de segurança, guarda de registros, sigilo, aplicação territorial e retenção de registros de acesso a aplicações por seis meses quando art. 15 for aplicável."

[2]: https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2016/decreto/d8771.htm "Presidência da República — Decreto nº 8.771, de 11 de maio de 2016, texto atualizado — 11/05/2016, com redação posterior; sustenta padrões de segurança, autenticação dupla, inventário de acessos, criptografia, minimização, formato estruturado e divulgação de padrões."

[3]: https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2026/decreto/d12975.htm "Presidência da República — Decreto nº 12.975, de 20 de maio de 2026 — 20/05/2026; sustenta a alteração vigente do Decreto nº 8.771, inclusive porta lógica de origem quando necessária e novos deveres gerais de provedores de aplicações."

[4]: https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2020/decreto/d10222.htm "Presidência da República — Decreto nº 10.222, de 5 de fevereiro de 2020 — 05/02/2020, revogado; sustenta apenas o conteúdo histórico da primeira E-Ciber e não deve ser tratado como norma vigente."

[5]: https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2025/decreto/d12573.htm "Presidência da República — Decreto nº 12.573, de 4 de agosto de 2025 — 04/08/2025; institui a E-Ciber vigente, define quatro eixos, autenticação, contingência, testes e revoga expressamente o Decreto nº 10.222/2020."

[6]: https://www.gov.br/gsi/pt-br/assuntos/seguranca-da-informacao-e-cibernetica/estrategia-nacional-de-ciberseguranca-eciber "Gabinete de Segurança Institucional — E-Ciber: Estratégia Nacional de Cibersegurança — página consultada em 08/10/2026, atualizada após 04/08/2025; confirma a substituição da estratégia de 2020 e resume governança, riscos, incidentes, serviços essenciais e maturidade."

[7]: https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2023/decreto/d11856.htm "Presidência da República — Decreto nº 11.856, de 26 de dezembro de 2023 — 26/12/2023; institui a PNCiber e o CNCiber, com princípios de direitos, prevenção, resiliência, cooperação e objetivos de confidencialidade, integridade, autenticidade, disponibilidade e gestão de riscos."

[8]: https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm "Presidência da República — Lei nº 13.709, de 14 de agosto de 2018 — 14/08/2018, texto atualizado; sustenta segurança desde a concepção, proteção contra acessos/perdas/alterações, segurança após o término, comunicação de incidentes e governança em privacidade nos arts. 44 e 46–50."

[9]: https://www.in.gov.br/en/web/dou/-/resolucao-cd/anpd-n-2-de-27-de-janeiro-de-2022-376562019 "ANPD — Resolução CD/ANPD nº 2, de 27 de janeiro de 2022 — 27/01/2022; sustenta tratamento regulatório de pequeno porte, política simplificada, medidas essenciais e prazos diferenciados, sem dispensar segurança."

[10]: https://www.in.gov.br/en/web/dou/-/resolucao-cd/anpd-n-15-de-24-de-abril-de-2024-556243024 "ANPD — Resolução CD/ANPD nº 15, de 24 de abril de 2024 — 24/04/2024; sustenta critérios de risco/dano relevante, prazo de três dias úteis, conteúdo da comunicação, comunicação ao titular e registro de todo incidente por no mínimo cinco anos."

[11]: https://www.gov.br/anpd/pt-br/centrais-de-conteudo/materiais-educativos-e-publicacoes/guia-orientativo-sobre-seguranca-da-informacao-para-agentes-de-tratamento-de-pequeno-porte "ANPD — Guia orientativo sobre segurança da informação para agentes de tratamento de pequeno porte — publicado em 21/06/2024, modificado em 23/01/2025; sustenta orientação administrativa e checklist de medidas técnicas e administrativas proporcionais."

[12]: https://www.gov.br/anpd/pt-br/assuntos/comunicacao-de-incidentes-de-seguranca-cis "ANPD — Comunicação de Incidente de Segurança — publicado em 23/12/2022, modificado em 26/08/2026; sustenta procedimento de comunicação, papel do controlador e a afirmação de que comunicar apenas à ANPD não substitui comunicar titulares quando houver risco/dano relevante."

[13]: https://www.nist.gov/publications/nist-cybersecurity-framework-csf-20 "Cherilyn Pascoe, Stephen Quinn e Karen Scarfone, NIST — The NIST Cybersecurity Framework (CSF) 2.0 — 26/02/2024; sustenta a natureza voluntária, as funções GOVERN/IDENTIFY/PROTECT/DETECT/RESPOND/RECOVER e o uso de outcomes sem prescrever implementação."

[14]: https://csrc.nist.gov/pubs/sp/800/63/b/4/final "David Temoshok et al., NIST — SP 800-63B-4 Digital Identity Guidelines: Authentication and Authenticator Management — 31/07/2025; sustenta requisitos de autenticadores, gestão de ciclo de vida e níveis de garantia, substituindo a edição anterior."

[15]: https://csrc.nist.gov/pubs/sp/800/61/r3/final "Alexander Nelson et al., NIST — SP 800-61 Rev. 3 Incident Response Recommendations and Considerations — 03/04/2025; sustenta integração da resposta a incidentes ao CSF 2.0 e preparação, detecção, resposta, recuperação e melhoria."

[16]: https://csrc.nist.gov/pubs/sp/800/92/final "Karen Kent e Murugiah Souppaya, NIST — SP 800-92 Guide to Computer Security Log Management — 13/09/2006; sustenta orientação institucional para infraestrutura, coleta, análise e processos de gestão de logs."

[17]: https://csrc.nist.gov/pubs/sp/800/34/r1/upd1/final "Marianne Swanson et al., NIST — SP 800-34 Rev. 1 Contingency Planning Guide for Federal Information Systems — publicado em 05/2010, atualizado em 11/11/2010; sustenta planejamento de contingência, prioridades, resiliência, backup e recuperação."

[18]: https://csrc.nist.gov/pubs/sp/800/57/pt1/r5/final "Elaine Barker, NIST — SP 800-57 Part 1 Rev. 5 Recommendation for Key Management — 04/05/2020; sustenta inventário, proteção, ciclo de vida, comprometimento, recuperação, destruição e gestão de material criptográfico."

[19]: https://owasp.org/projects/asvs "OWASP Foundation — OWASP Application Security Verification Standard (ASVS) — versão estável 5.0.0 publicada em 2025; sustenta padrão aberto voluntário, requisitos verificáveis e necessidade de identificar a versão dos requisitos."

[20]: https://owasp.org/Top10/2025/ "OWASP Foundation — OWASP Top 10:2025 — 2025; sustenta catálogo de conscientização e riscos de aplicações, incluindo controle de acesso, configuração, cadeia de software, criptografia, autenticação, integridade e logging/alerting."

[21]: https://owasp.org/Top10/2021/ "OWASP Foundation — OWASP Top 10:2021 — 2021; sustenta referência histórica de riscos, especialmente controle de acesso, autenticação, integridade e logging/monitoramento."

[22]: https://www.postgresql.org/docs/current/ddl-rowsecurity.html "PostgreSQL Global Development Group — PostgreSQL 18 Documentation, Row Security Policies — versão atual consultada em 08/10/2026; sustenta default deny sem policy, policies por comando/role, bypass de owner/superuser/BYPASSRLS, FORCE RLS e a exclusão de TRUNCATE do mecanismo de RLS."

[23]: https://docs.aws.amazon.com/prescriptive-guidance/latest/saas-multitenant-api-access-authorization/introduction.html "Tabby Ward, Thomas Davis, Gideon Landeman e Tomas Riha, Amazon Web Services — Multi-tenant SaaS authorization and API access control: Implementation options and best practices — 06/08/2023; sustenta a distinção entre tenant isolation e autorização, além de padrões PDP/PEP/PAP e RBAC/ABAC."
