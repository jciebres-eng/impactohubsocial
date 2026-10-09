# IMPACTO Trust v0.26.0 — Master Knowledge Base

**Versão documental:** 0.26.0  
**Data da pesquisa consolidada:** 2026-10-08  
**Estado de publicação:** **não publicado; base técnica fechada, com condições**  
**Escopo:** conhecimento operacional, jurídico-regulatório, de dados, risco e governança para implantação segura.  
**Não é parecer jurídico, fiscal, contábil, de proteção de dados, segurança, impacto ou certificação.**

> **Regra de segurança editorial:** nenhum texto desta base autoriza, sozinho, publicação, cobrança, aceite contratual, integração governamental, tratamento de dados de alto risco, claim de conformidade ou lançamento público. A decisão exige o profissional responsável, a evidência correspondente e o registro de vigência.

## 1. Decisão executiva

O v0.26.0 pode ser tratado como **fundação técnica fechada para continuar a implantação**, não como produto publicado, certificado ou conforme. O README declara base técnica fechada, ausência de domínio/lojas públicas e ausência de provedores de pagamento, fiscal, WhatsApp, mapas e IA ligados; também descreve arquitetura não custodial e contratos como regra de operação [R01, R05, R08, R09]. Os 12 relatórios confirmam que os controles internos são uma base útil, mas a maior parte das alegações externas ainda depende de decisão jurídica, configuração, contratação, homologação, evidência independente ou conteúdo aprovado.

**Bloqueios absolutos antes de qualquer piloto comercial ou governamental:**

1. manter o aceite de todas as minutas legais bloqueado até revisão, aprovação, vigência, versão efetiva, hash e referência registradas [R01, R02, R10];
2. manter pagamento, taxa, estorno, NFS-e, Pix, cartão, boleto, split, repasse, wallet, escrow e liquidação de terceiros inativos enquanto não houver escopo, provedor, contrato, configuração fiscal/regulatória e teste real [R01, R05];
3. não chamar `platform_advanced` de ICP-Brasil, assinatura qualificada, Gov.br ou certificada pelo ITI; acceptance de documento, signature comercial e approval interno são atos diferentes [R01];
4. não ativar integração governamental, PNCP, Transferegov, Gov.br, eSocial ou assinatura do ente sem órgão, finalidade, autorização, credenciais, ambiente, contrato de dados, testes e reconciliação externos [R04, R09];
5. não publicar conteúdo como oficial/vigente, não alegar WCAG/ABNT, impacto comprovado, ESG/GRI/ISSB, SROI, anonimização, ausência de transferência internacional, revisão humana ou conformidade LGPD sem escopo e prova específica [R02, R06, R07, R10, R12].

### 1.1 Contradições a resolver antes do release externo

| Contradição | O que consta | Tratamento obrigatório |
|---|---|---|
| Inventário de motores | README v0.26.0 menciona **45 motores**; `TECHNICAL_FINALIZATION_STATUS.md` registra **42**; a pesquisa de IA também encontra 42 versus 45 [R07]. | Congelar um manifesto gerado do código, com nome, versão, dono, teste e estado; corrigir todos os documentos e claims. Até lá, usar “motores declarados; contagem em reconciliação”. |
| Escopo documental | Há arquivos atuais, históricos e documentos com versões v0.12.0, v0.17.0, v0.18.1, v0.22.0 e v0.26.0; as pesquisas 01, 02 e 10 apontam stale docs e minutas antigas. | Não apagar históricos. Marcar `HISTORICAL`, `DRAFT`, `EFFECTIVE` ou `SUPERSEDED`; toda tela/endpoint deve apontar para a versão efetiva. |
| Estado legal | Os onze documentos de `docs/legal` são minutas; o README usa linguagem comercial mais avançada que a prova jurídica disponível [R01, R05, R10]. | Exigir registro de aprovação, vigência, jurisdição, aprovador, hash e changelog. O estado padrão é `DRAFT/BLOCKED`. |
| Estado de integração | A matriz atual marca `government_api` como `SCAFFOLDED/BLOCKED`; não há fonte governamental viva conectada [R04, R09]. | Exibir `NOT_CONNECTED`/`BLOCKED_EXTERNAL`, nunca “integrado”, “homologado” ou “oficial”. |
| Estado de acessibilidade | O README fala em axe/WCAG; a pesquisa 10 registra divergência e axe não verificado como cobertura integral. | Manter axe como evidência parcial; complementar teclado, leitor de tela, zoom/reflow, documentos, vídeo e teste humano antes de qualquer claim. |
| Data de corte | Os relatórios foram entregues com data de corte 2026-10-08 e podem mencionar atos de 2026. | Revalidar vigência em cada revisão; a data da pesquisa não substitui a conferência da fonte oficial na data de decisão. |

## 2. Como usar esta base

- A base mestre define vocabulário, precedência e gates; os relatórios em `knowledge-base/research/` preservam a análise detalhada.
- A matriz CSV é a fila operacional: cada linha tem obrigação/hipótese, controle, teste, responsável, revisão e status.
- `KNOWLEDGE-MANIFEST.json` é o contrato de inventário desta entrega; qualquer alteração de domínio, relatório, periodicidade ou status exige atualização do manifesto.
- `CHANGELOG.md` é o plano priorizado P0/P1/P2; não é prova de conclusão.
- `CLAUDE-HANDOFF.md` contém regras de continuidade para agentes e editores.
- “Implementado” significa apenas mecanismo interno verificado no escopo declarado; não significa integração externa, eficácia jurídica ou conformidade.

## 3. Inventário operacional do release

O inventário abaixo combina nomes da documentação e dos relatórios com o estado explicitamente observado. Ele não substitui uma enumeração automática do código; itens não confirmados como executados permanecem declarados/condicionais.

### 3.1 Núcleo de identidade, organização e autorização

- **Identidade e acesso:** login, tokens de e-mail, MFA TOTP para administração, perfis/personas, `TRUST_IDENTITY`, `AUTHORIZATION`, RLS, permissões granulares e step-up. A pesquisa de segurança aponta necessidade residual de ABAC por recurso/linha, revisão de rotas sem permissão nomeada e isolamento em jobs, cache, arquivos, webhooks e exportações [R08].
- **Organizações e elegibilidade:** `INSTITUTIONAL_ELIGIBILITY_ENGINE`, `THIRD_SECTOR_MODEL`, `RESPONSIBILITY_ENGINE`, qualificações, compliance checks, determinantes e `PROJECT_READY`. Ready e maturidade 0–6 são estados/hipóteses internos, não selos, certificações, legalidade ou ausência de risco [R03, R12].
- **Personas e ciclo:** `ROLE_BASED_EXPERIENCE`, workspaces, projetos, oportunidades, propostas, parcerias e jornadas para OSC, empresa, fundação, profissional, financiador e órgão público. A finalidade de cada fluxo deve determinar controlador, base legal, obrigação e prova.

### 3.2 Conhecimento, conteúdo e evidência

- **Conhecimento:** `KNOWLEDGE_HUB`, `KNOWLEDGE_DATA_MODEL`, `PUBLICACAO`, `INFORMATION_ARCHITECTURE`, assistente extrativo e catálogo de fontes.
- **Documentos e proveniência:** cofre com arquivo/hash/versionamento, `PROVENANCE_ENGINE`, `AUDIT_ENGINE`, `VALUE_LEDGER`, evidências e cadeia de auditoria. A cadeia existente não equivale a carimbo externo RFC 3161, verificação pública de terceiro, KYC ou assinatura ICP-Brasil [R03, R08, R10].
- **Publicação e acessibilidade:** `ACCESSIBILITY`, `TRAINING_ACADEMY`, `PUBLIC_VERIFICATION`, SEO, licença, revisão, retração, linguagem simples, WCAG/eMAG/ABNT como metas/standards conforme escopo escolhido; não há claim automático de conformidade [R10].

### 3.3 Impacto, ESG, ODS e avaliação

- **Impacto:** `IMPACT_FRAMEWORK`, `IMPACT_REPORTING`, teoria da mudança, indicadores, `LONGITUDINAL_TRACKING`, `IMPACT_GRAPH`, evidência e resultados negativos.
- **Taxonomias:** `SDG_ESG_TAXONOMY`, ODS, ESG editorial, TSB, GRI, ISSB/IFRS S1-S2, CBPS, IRIS+ e SROI. Cada framework deve ser registry versionado com steward, código, fonte, edição, licença, data e hash. `ods_targets` permanece vazio segundo a pesquisa 06; frameworks externos estão em `registry_only`; additionality numérico é hipótese interna, não prova [R06].
- **Safeguarding e direitos:** denúncias/moderação, direitos humanos, trabalho decente, não discriminação, acessibilidade, participação e remediação. Beneficiary counts devem ter unidade, período, denominador, método, fonte, qualidade e incerteza; `unknown` não é zero [R12].

### 3.4 IA, busca, match, reputação e moderação

- **Motores:** `AI.md`, `AI_ENGINES.md`, `AI_FINAL_AUDIT.md`, `INTENT_ENGINE`, `MATCH_ENGINE`, `SOLUTION_MATCH_ENGINE`, busca, recomendação, scoring e assistente. Há divergência documental 42 versus 45 motores [R07].
- **Guardrails:** provedor local/disabled por padrão; provedor externo bloqueado até base legal, RIPD/DPIA quando aplicável, contrato, transferência, retenção/deleção, subprocessadores e configuração sem treinamento. Elegibilidade deve permanecer separada de score; thresholds 55/75 e confiança mínima 50 são hipóteses de produto até validação. Reputação não deve virar nota única nem decidir busca, match, recomendação, elegibilidade ou exposição [R07].
- **Conteúdo de terceiros:** distinguir `official`, `educational`, `third_party` e `demo`; não copiar substancialmente; fonte pública não implica licença de treino; direitos de upload, indexação, resumo, embedding, treino e saída precisam de ledger [R07, R10].

### 3.5 Marketplace, parcerias e OSCs

- `MARKETPLACE`, `PARTNERSHIP_SYSTEM`, `MODERATION_LADDER`, `REPUTATION_ARCHITECTURE`, `RISK_FRAUD` e fluxos de oferta, candidatura, parceria, publicidade e denúncia.
- As obrigações variam conforme finalidade, vulnerabilidade, destinatário final, setor regulado, publicidade, dados e atuação efetiva da plataforma. Não presumir CDC nem sua exclusão para pessoa jurídica/OSC; aplicar a matriz de incidência por fluxo [R01, R11].
- A tese do STF sobre responsabilização de plataformas e decisões STJ sobre marketplace/links patrocinados devem ser tratadas como orientação jurisprudencial aplicável conforme fatos, não como autorização automática de modelo [R11].

### 3.6 Contratos, finanças, fiscal e não custódia

- **Contratos:** `docs/legal/*`, `SIGNATURE_VALIDATION_MATRIX`, acceptance de documento, signature de acordo comercial, approval interno, obrigações `deliver/accept/pay`, quatro olhos, hash, versionamento e invalidação de aprovações antigas.
- **Comercial:** `MONETIZATION`, `MONETIZATION_ARCHITECTURE`, `PRICING_BIBLE`, catálogo de preços, acesso gratuito e autorização de cobrança separados; `contract.platform_service_fee` permanece desligada até os gates jurídicos/fiscais/comerciais [R01, R05].
- **Financeiro:** `FINANCIAL_ENGINE`, `FISCAL_ENGINE`, `PAYMENT_ARCHITECTURE`, `NON_CUSTODIAL_ARCHITECTURE`, ledger append-only, instrução de pagamento e conciliação. A plataforma calcula/instrui/concilia, mas não deve custodiar, liquidar, fazer split, payout, repasse, wallet ou escrow [R05].
- **Fiscal:** classificação do SaaS/taxa, município, regime, retenção, NFS-e, EFD-Reinf/DCTFWeb e exportação para contador exigem entidade/CNPJ, fatos e provedor definidos; não há emissão automática configurada [R05].

### 3.7 Compras públicas e integrações governamentais

- `PROCUREMENT`, `INTEGRATION_ARCHITECTURE`, `INTEGRATION_HUB`, `INTEGRATION_CAPABILITY_MATRIX`, `INTEGRATION_SECURITY`, `INTEGRATION_TESTING`, `INTEGRATION_OPERATIONS`, `PUBLIC_VERIFICATION`, adapters e contratos de dados.
- Fluxo previsto: DFD/PCA → ETP → pesquisa de preços → TR/edital → seleção → contrato → PNCP → execução → aceite → pagamento. Benchmark interno de três cotações não substitui pesquisa formal de preços; inovação não infere automaticamente diálogo competitivo/CPSI [R04].
- `government_api` é scaffolded/blocked; separar login Gov.br, assinatura Gov.br e Conecta gov.br; SICONV é legado histórico; PNCP público para consulta não implica permissão de escrita [R09].

### 3.8 Segurança, privacidade, auditoria e continuidade

- `TRUST_SECURITY`, `SECURITY_AUDIT`, `SECURITY_FINAL_CHECKLIST`, `TRUST_TESTING`, `KEY_ROTATION`, `PRIVACY_VISIBILITY_MATRIX`, `LGPD_AUDIT`, incidentes, autorização, logs, backup e restauração.
- Usar o Decreto 12.573/2025 como E-Ciber vigente; o Decreto 10.222/2020 é histórico/revogado segundo a pesquisa 08. Separar registros do Marco Civil, logs de segurança, auditoria e registro regulatório de incidentes [R08].
- Ainda precisam de decisão/prova: destino off-site, RPO/RTO, restauração independente, KMS/HSM, rotação/destruição de chaves, ASVS 5, SAST/DAST, dependências, pentest e endereço/on-call público [R08].

## 4. Taxonomia O/A/V/H/D

A taxonomia é editorial e operacional; não altera a força jurídica da fonte.

| Código | Classe | Significado | Como usar |
|---|---|---|---|
| **O** | Obrigação normativa | Constituição, lei, decreto, resolução vinculante, obrigação contratual aprovada ou regra judicial aplicável aos fatos. | Só marcar “obrigatório” após conferir artigo, jurisdição, vigência e escopo. |
| **A** | Autoridade/orientação | Guia, manual, FAQ, ato administrativo, padrão de órgão, entendimento de autoridade ou jurisprudência não automaticamente vinculante. | Tratar como orientação/risco interpretativo; registrar órgão, data e suporte. |
| **V** | Voluntário/boa prática | WCAG, NIST, OWASP, ISO, GRI, ISSB, IRIS+, OECD, ILO ou literatura, salvo quando incorporado por contrato/norma. | Declarar meta, escopo e método; nunca chamar de certificação por usar o padrão. |
| **H** | Hipótese de produto | Threshold, score, modelo de impacto, Ready, additionality, preço, ranking, heurística ou regra interna sem fonte normativa. | Exigir owner, versão, dados, validação, contestação e revisão; não comunicar como fato legal. |
| **D** | Decisão/dependência/evidência pendente | Escolha jurídica/contábil/DPO, contrato, provedor, credencial, homologação, evidência externa ou pergunta aberta. | Bloqueia o gate correspondente; não preencher por suposição. |

**Regra de conflito:** O vigente prevalece sobre A/V/H; A orienta interpretação e risco, mas não substitui O; V melhora controle, mas não cria obrigação; H nunca prova conformidade; D exige decisão/evidência antes de mudar o status.

## 5. Hierarquia de fontes e proveniência

1. **Fonte normativa primária vigente:** Constituição, lei, decreto, resolução e texto oficial no Planalto/Diário Oficial; registrar artigo, redação, jurisdição e vigência.
2. **Ato ou orientação da autoridade competente:** ANPD, BCB, CVM, TCU, Governo Digital, Transferegov, PNCP, Receita, ITI, Senacon, MTE, órgãos locais; registrar se é obrigatório, orientação ou manual.
3. **Jurisprudência e decisões:** STF/STJ/tribunal competente, número, data, ratio e limites fáticos; não generalizar uma decisão a qualquer fluxo.
4. **Padrões e literatura:** W3C, NIST, OWASP, ISO, GRI, ISSB/IFRS, OECD, ILO, ONU, Ipea, literatura acadêmica; registrar edição/licença e escopo.
5. **Contrato e decisão profissional:** minuta aprovada, parecer, ata de decisão, aditivo, credencial e homologação; o contrato pode criar obrigação entre partes, mas não revoga lei.
6. **Evidência interna:** código, migração, teste, log, hash, snapshot, relatório e resultado de restauração; prova somente o cenário, versão e data observados.

Todo item de conhecimento deve conter: `id`, classe O/A/V/H/D, título, autor/órgão, URL, artigo/seção quando aplicável, jurisdição, vigência, versão, data de acesso, hash do arquivo/trecho, licença, owner, revisor, `review_due`, status e limites. Para conteúdo público, registrar canonical/robots, acessibilidade, direitos, retração e dependências.

## 6. Matriz operacional módulo → domínio → fonte → risco → controle → teste

A matriz completa e rastreável está em [`LEGAL-APPLICABILITY-MATRIX.csv`](./LEGAL-APPLICABILITY-MATRIX.csv). As linhas abaixo resumem os controles que devem ser fechados juntos; `PENDING/BLOCKED` é estado deliberado, não defeito oculto.

| Módulo/área | Domínio legal ou de confiança | Fonte principal | Risco | Controle mínimo | Teste/artefato |
|---|---|---|---|---|---|
| Contratos/acceptance/signature | Código Civil, CDC, Decreto 7.962, MP 2.200-2, Lei 14.063 | [R01] | aceite de draft, claim falso de assinatura, prova insuficiente | estado `DRAFT` bloqueia; hash, versão, identidade, poder, papel, declaração, desafio, timestamp, método, revogação e cadeia | teste de draft recusado; supersede invalida aceites; verificação de hash; auditoria quatro olhos |
| Incidência CDC | CDC/STJ | [R01, R11] | classificar pessoa/OSC/empresa de modo errado | matriz finalidade/destinatário final/vulnerabilidade por fluxo; cópia, sumário, arrependimento/cancelamento quando aplicável | cenários PF, OSC, empresa insumo/destinatária final; revisão jurídica |
| Privacidade/Ropa | LGPD; Res. ANPD 2, 15, 18, 19 | [R02] | base legal, papel, retenção, transferência ou incidente sem governança | ROPA, RIPD, portal de direitos, encarregado, retenção, suboperadores, mecanismo de transferência | testes de autorização/direitos; simulação de incidente e prazos |
| Crianças/vulneráveis | ECA Digital/Lei 15.211, proteção reforçada | [R02, R07, R12] | acesso provável, profiling, dano, revitimização | classificação de público/conteúdo, safeguarding, canal, encaminhamento, minimização e revisão humana | teste de idade/acesso; denúncia; escalonamento; não publicação sem rota |
| OSC/MROSC | Lei 13.019, Decreto 8.726, atos locais | [R03, R12] | elegibilidade universal, instrumento/conta/contas errados | aplicabilidade por ente/edital, evidência, plano, chamamento, execução, monitoramento, transparência | casos colaboração/fomento/acordo; unknown≠zero; snapshot |
| Compras públicas | Lei 14.133, LC 182, PNCP, IN/atos locais | [R04] | chamar checklist de contratação de sistema oficial | roteador DFD/PCA→ETP→TR; prova de ente/jurisdição; exportação rotulada | teste de rota; sem claim PNCP; reconciliação externa quando houver |
| Fiscal | LC 116/175, NFS-e, EFD-Reinf/DCTFWeb | [R05] | cobrança sem fato, município ou emissão | gate entidade/CNPJ/regime, regra fiscal versionada, contador, provedor; export-only até lá | bloqueio de fee; classificação por município; não emitir sem provedor |
| Pagamentos/não custódia | Lei 12.865, BCB, CVM, PLD | [R05, R11] | atuar como IP, custodiar/repassar ou ofertar valor mobiliário | CALCULA/INSTRUI/CONCILIA; sem saldo de terceiros; PSP externo; revisão regulatória | grep/schema anti-wallet; webhooks idempotentes; teste de não custódia |
| Impacto/ESG/ODS | CVM 193/244/218, TSB, ODS, GRI/ISSB/IRIS | [R06] | impacto/ESG/ODS ou SROI apresentado como comprovado | registry versionado, proveniência, método, revisão independente, negative results | medição sem evidência recusada como validada; additionality não exposto como prova |
| IA/scoring/match | LGPD, ANPD, copyright, princípios/padrões | [R02, R07] | decisão automática, discriminação, transferência, copyright | local/disabled; finalidade/base; explicação, contestação, revisão; thresholds como H; rights ledger | fairness/reidentificação; score≠eligibility; abstinência do assistente |
| Reputação/moderação | LGPD, CDC, Marco Civil/STF/STJ, direitos | [R08, R11, R12] | reputação única, remoção sem devido processo, dano | dimensões separadas, fatos/proveniência, denúncia→apuração→consequência, contestação | denúncia sem consequência automática; recurso e snapshot |
| Integrações gov | LGPD, Lei 14.063, Lei 14.129/14.133, contratos de API | [R09] | login/tokens tratados como assinatura; escrita não autorizada | contrato de dados, credencial, ambiente, rate limit, finalidade, evidência, status | adapter dublê separado de homologação; reconciliação; Retry-After |
| Conteúdo/publicação | LAI, Lei 14.129, Lei 15.263, LBI, Lei 9.610, WCAG | [R10] | oficialidade, licença, acessibilidade e vigência falsas | portão editorial, quatro olhos, source/version/hash/license, retração, testes humanos | página inteira + teclado/leitor; rights ledger; source labeling |
| Segurança/auditoria | Marco Civil, LGPD, ANPD 15, E-Ciber, NIST/OWASP | [R08] | retenção errada, incidente não comunicado, falsa certificação | separar logs; registro de incidente 5 anos; off-site/RPO/RTO; ASVS/SAST/DAST/pentest | restauração independente; incident drill; matriz ASVS; negative tests |
| Direitos humanos/trabalho | Constituição, LBI, ECA, igualdade, Lei Anticorrupção, ILO/ONU | [R12] | exclusão digital, discriminação, culpabilização, safeguarding ausente | participação acessível, contestação, remediação, due process, counts com incerteza | fairness/accessibility/safeguarding tests; não ranquear por contagem isolada |

## 7. Obrigações por ciclo de vida

### Fase 0 — descoberta e classificação

- Identificar persona, finalidade, ente, jurisdição, setor, destinatário final, vulnerabilidade, dados, dinheiro, conteúdo e efeito da decisão.
- Classificar cada regra O/A/V/H/D e guardar fonte, artigo/edição, URL, vigência, owner, revisor e data de revisão.
- **Stop:** sem aplicabilidade definida, não ativar fluxo, não chamar API e não publicar claim.

### Fase 1 — onboarding, identidade e representação

- Separar autenticação, identificação, autoridade, representação, procuração e assinatura.
- Para organização, conservar CNPJ/documento permitido, pessoa representante, poderes, procuração, validade, fonte e revisão; nunca inferir poderes apenas do login.
- Para órgão público, registrar ente, órgão, autoridade, edital/processo, fiscal, publicação, medição, aditivo e extinção quando aplicável [R01, R04].
- **Stop:** autoridade/poder/escopo não verificados ou dados sensíveis sem finalidade/base/controle.

### Fase 2 — dados, documentos e conteúdo

- Criar ROPA por finalidade, base legal, controlador/operador, categorias, crianças/sensíveis, países, suboperadores, retenção, eliminação e RIPD.
- No documento: arquivo/texto, versão, hash derivado pelo servidor, cadeia, licença, autor/órgão, identidade/poderes, método, timestamp e estado.
- No conteúdo: origem, vigência, canonical, revisão, acessibilidade, direitos, trecho citável e retração.
- **Stop:** origem/licença/retention/consentimento/base legal não registrados.

### Fase 3 — proposta, contrato e aceite

- Apresentar cópia conservável, sumário e limitações; corrigir erros antes da confirmação; oferecer canal de cancelamento/arrependimento quando aplicável.
- Separar `acceptance` do texto legal, `signature` do acordo comercial e `approval` interno. Quatro olhos: quem entrega não aceita; rejeição registra ator, data e motivo.
- Nova versão cria novo hash, invalida aprovações, exige novas assinaturas e recalcula obrigação/preço/taxa. Pagamento só abre após condição contratual.
- **Stop:** minuta/draft, claim de assinatura qualificada, obrigação sem prazo/pagador, preço/taxa sem base.

### Fase 4 — execução, medição e decisão

- Iniciar obrigações apenas com contrato vigente e aceites válidos; registrar deliver/accept/pay, prazo, evidência, contestação, glosa, aditivo e encerramento.
- Separar autodeclarado de validado; cadeia faltante aparece em `gaps`; desconhecido não vira zero.
- Scores, Ready, reputação, elegibilidade e recomendações devem ser explicáveis, contestáveis, versionados e revisáveis; nenhuma decisão exclusivamente automática sem base e salvaguardas [R02, R07, R12].
- **Stop:** evidência ausente, resultado negativo oculto, efeito material sem revisão humana/contestação.

### Fase 5 — dinheiro, fiscal e integrações

- Antes de cobrar: contrato aprovado/vigente, pagador, fato gerador, regra fiscal, município/regime, NFS-e/provedor, autorização e teste.
- Antes de pagamento: PSP, papel regulatório, webhooks assinados/idempotentes, conciliação, estorno e retenção definidos; sem custódia ou repasse por padrão.
- Antes de integração: autorização do órgão, credencial do ambiente, escopo, rate budget, schema, finalidade, controlador/operador, evidência e saída.
- **Stop:** qualquer linguagem de “processado”, “emitido”, “homologado”, “oficial” ou “conectado” sem prova externa.

### Fase 6 — publicação e claims

- Portão editorial com quatro olhos, proveniência, licença, acessibilidade, SEO, review_due, status e retração.
- Claims devem apontar fato observável, escopo, data, método e limitações; o claim é bloqueado se depender de fonte não vigente ou de hipótese não rotulada.
- **Stop:** conteúdo draft/demo/privado/superseded/retracted, fonte terceira apresentada como oficial ou acessibilidade não testada no escopo.

### Fase 7 — direitos, incidentes, retenção e saída

- Portal de direitos com autenticação proporcional, prazos, exceções e trilha; direitos de contestação para scores/reputação e decisões.
- Incidente: relógio de conhecimento, risco, dados/pessoas, contenção, comunicação à ANPD/titulares, complemento, evidência e retenção mínima definida pela regra aplicável; pesquisa 02 exige pipeline com 3 dias úteis (6 quando pequeno porte aplicável) e registro de cinco anos, sujeito à conferência do caso [R02].
- Conciliar prova contratual, Marco Civil, LGPD, fiscal, tabela pública, backups e legal hold; não apagar evidência sob hold; anonimizar quando possível.
- **Stop:** restauração não testada, retenção sem base, incidente sem owner/canal ou saída sem exportação/eliminação verificável.

## 8. Catálogo de claims

### 8.1 Claims permitidos, condicionados e seu formato

| Claim seguro | Condição mínima de publicação |
|---|---|
| “A plataforma tem **base técnica fechada** no escopo descrito.” | apontar versão, testes e limites; não converter em produção/conformidade. |
| “O fluxo usa **hash SHA-256 derivado pelo servidor** para este documento.” | documento/rota/timestamp e teste correspondente disponíveis. |
| “O relatório é **autodeclarado/validado** conforme o estado mostrado.” | mostrar fonte, revisor, cadeia, `gaps`, data e escopo; nunca esconder elo ausente. |
| “A integração está **scaffolded/blocked external**.” | credencial, ambiente e homologação ausentes explicitamente. |
| “A taxa está **calculada, não cobrável** neste estado.” | regra `active=false`, ausência de PSP/fiscal e teste de bloqueio. |
| “O conteúdo é uma **síntese extrativa de fonte identificada**.” | trecho, fonte, versão, hash, data, licença, abstinência e status publicado. |
| “Meta de produto: WCAG 2.2 AA no escopo X.” | escopo, ferramenta, testes manuais, exceções e data; sem “conforme”. |
| “Threshold/Ready/additionality é **hipótese interna de produto**.” | owner, versão, método, dados, validação e revisão. |
| “Controle testado no cenário Y na versão Z.” | evidência reprodutível e limites do cenário. |

### 8.2 Claims proibidos sem evidência e aprovação específica

- “100% conforme”, “certificado pela ANPD/ITI/ONU/TCU/MEC”, “homologado pelo PNCP/Transferegov”, “oficial”, “aprovado” ou “autorizado” sem ato/contrato verificável.
- “Assinatura ICP-Brasil, qualificada, Gov.br ou validada pelo ITI” quando o método é `platform_advanced` ou interno.
- “Pix/cartão/boleto processado”, “NFS-e emitida”, “estorno garantido”, “SLA garantido”, “pagamento custodiado”, “investimento”, “PLD compliant”, “subcredenciador”, “iniciador Pix”, “payout/split/escrow”.
- “Sem dados sensíveis”, “dados anonimizados”, “sem transferência internacional”, “sem treinamento externo”, “revisão humana sempre”, “sem viés”, “decisão neutra” ou “RIPD concluído” sem evidência por fluxo.
- “Elegível”, “aprovado”, “financiável”, “alto impacto”, “ESG compliant”, “GRI/ISSB”, “SROI validado”, “ODS alinhado” ou “Ready” como garantia/selo.
- “Conteúdo oficial/vigente”, “livre de direitos”, “licença autorizada”, “WCAG/ABNT conforme”, “certificado oficial” ou “aconselhamento jurídico”.
- “Sem risco”, “trabalho decente garantido”, “beneficiário comprovado” ou atribuição de culpa sem evidência, processo, contestação e órgão competente.

## 9. Gaps críticos e plano de correção

### P0 — bloquear publicação, cobrança e decisões externas

1. **Aprovação legal e versionamento:** onze minutas em draft; consolidar versão efetiva, changelog, vigência, jurisdição, aprovador e hash; bloquear aceite [R01, R02, R10].
2. **Incidência por fluxo:** decidir CDC, poderes, assinaturas, responsabilidade, cancelamento, retenção e B2G por persona/ente; não usar um termo universal [R01, R11].
3. **LGPD/DPO:** ROPA, bases, controlador/operador, RIPD quando necessário, encarregado, portal de direitos, incidentes, retenção, transferências e crianças [R02].
4. **Claims e publicação:** portão editorial, fonte/vigência/licença, acessibilidade, retratação e gate de claims; corrigir conteúdo oficial/stale [R06, R10].
5. **Não custódia/financeiro:** manter fee/pagamento/fiscal bloqueados; decisão regulatória se o escopo mudar para transação, saldo, captação, retorno ou valor mobiliário [R05].
6. **Segurança operacional:** registro de incidentes, backup off-site, RPO/RTO, restauração, KMS/HSM ou decisão de risco, autorização ABAC e revisão independente [R08].
7. **Contradição do inventário:** resolver 42/45 motores, 873/894 operações/telas e versões documentais antes de comunicação externa [R07, R08].

### P1 — fechar antes de piloto com usuários reais

- Matriz aplicabilidade por ente/jurisdição e primeiro caso governamental; sem connector PNCP/Transferegov até autorização [R03, R04, R09].
- Dataset ODS/IBGE versionado; separar ODS/ESG/TSB/GRI/ISSB/IRIS/SROI e substituir `additionality_score` exposto por nível de suporte [R06].
- IA/assistente: corrigir 42/45, relevance confidence, fontes vencidas, copyright ledger, intents, explicação, contestação, calibragem e fairness [R07].
- Conteúdo e acessibilidade: WCAG 2.2 AA como meta explícita, testes manuais/humanos, documentos/vídeo/treinamento e licença de assets [R10].
- Safeguarding, participação acessível, encaminhamento e remediação para crianças/vulneráveis; counts com incerteza [R12].
- Fiscal/PSP/contador: classificar serviço, município, regime, NFS-e, EFD-Reinf/DCTFWeb e contrato de operador/PSP [R05].
- Homologar credenciais e testes de todos os provedores pretendidos; distinguir dublê, contract test, sandbox e produção [R09].

### P2 — maturidade, escala e melhoria contínua

- SAST/DAST, ASVS 5, dependências, pentest, observabilidade/on-call, exercício de incidente e restauração recorrente [R08].
- Verificação pública de documentos/assinaturas, TSA RFC 3161, revogação, QR, KYC e cadeia por documento, se o caso de uso exigir [R01, R03].
- Metodologia SROI/contrafactual, revisão independente, TSB/setores, métricas oficiais e transparência de resultados negativos [R06, R12].
- Adapters oficiais e reconciliação de PNCP/Transferegov/eSocial apenas depois do caso aprovado; rate limits e contratos de dados por API [R09].
- Governança de fornecedores, suboperadores, países, licenças, modelos de IA, retenção e saída; revisão periódica e legal hold [R02, R05, R07].

## 10. Checklist de go-live

Marcar somente com evidência anexada. Um único item P0 aberto produz **NO-GO**.

### Jurídico e comercial

- [ ] Persona, finalidade, destinatário final, vulnerabilidade, jurisdição e incidência CDC analisados por fluxo.
- [ ] Termos e anexos aprovados, vigentes, versionados, com hash, changelog, owner e referência; nenhum `DRAFT` no caminho de aceite.
- [ ] Acceptance, signature e approval separados; poderes/procurações verificados; quatro olhos e invalidação de supersede testados.
- [ ] Responsabilidade, carve-outs, indenização, seguro, SLA, força maior, cancelamento, pro rata, arrependimento, estorno e retenção aprovados.
- [ ] B2G tem ente, autoridade, processo, edital, fiscal, regra de assinatura e requisitos da Lei 14.133 definidos; sem checkout genérico.

### Dados, DPO e direitos

- [ ] ROPA, bases legais, papéis, categorias, sensíveis/crianças, retenção, países, suboperadores e RIPD/DPIA quando aplicável aprovados.
- [ ] Encarregado/canal e portal de direitos testados; contestação de score/reputação/decisão registrada.
- [ ] Incident runbook com relógio, 3/6 dias quando aplicável, comunicação, cinco anos de registro e exercício simulado.
- [ ] Transferência internacional conforme Resolução ANPD 19 e contratos aprovados; nenhum provedor externo habilitado por padrão.

### Produto, impacto e publicação

- [ ] Cada entidade/score/Ready/beneficiary count tem definição, unidade, período, método, fonte, incerteza e revisão.
- [ ] ODS/ESG/TSB/GRI/ISSB/IRIS/SROI versionados; dados oficiais têm licença/proveniência; resultados negativos e gaps visíveis.
- [ ] Conteúdo com status, fonte, vigência, hash, licença, autor/órgão, canonical, review_due, acessibilidade e retração.
- [ ] Assistente é extrativo e abstém-se de fonte vencida, não oficial, não publicada ou de terceiros sem autorização; copyright ledger completo.
- [ ] Testes de teclado, leitor, zoom/reflow, documentos, vídeo, axe e usuários/humanos executados no escopo; exceções registradas.

### Segurança, infraestrutura e continuidade

- [ ] Autorização por recurso/tenant/linha, RLS, funções privilegiadas, cache, jobs, arquivos, webhooks, exportações e rotas sem permissão testados.
- [ ] Logs de acesso, segurança, auditoria e incidentes separados; minimização, acesso, exportação, anonimização e descarte testados.
- [ ] Backup off-site, dependência de chaves, RPO/RTO, restauração independente, rotação e destruição/revogação exercitados.
- [ ] ASVS 5, SAST/DAST, dependências e revisão/pentest independente executados; resultado não é certificado.
- [ ] On-call, endereço público, observabilidade, alertas, escalonamento e procedimento de saída definidos.

### Integrações e dinheiro

- [ ] Cada adapter tem ambiente, credencial, contrato de dados, finalidade, schema, rate limit, Retry-After, idempotência, webhook e prova externa.
- [ ] PNCP/Transferegov/Gov.br/eSocial estão `NOT_CONNECTED` até autorização/homologação; consulta pública não é escrita autorizada.
- [ ] PSP, fiscal, contador e papel regulatório aprovados; fee somente com contrato, pagador, regra fiscal, NFS-e e autorização reais.
- [ ] Teste anti-custódia confirma ausência de wallet/saldo/split/payout/escrow/repasse; nenhuma instrução de pagamento é apresentada como liquidação.

## 11. Perguntas que precisam de decisão profissional

### Advogado(a) civil, consumidor e administrativo

1. Para cada persona/fluxo, quem é destinatário final e quando CDC, Decreto 7.962 e vulnerabilidade incidem?
2. Qual assinatura é exigida por órgão/ato: simples, avançada, qualificada, Gov.br, ICP-Brasil ou testemunhas?
3. Qual responsabilidade, carve-out, indenização, seguro, SLA, força maior, cancelamento, estorno e retenção será aprovada por modalidade?
4. Qual evidência de poderes/procurações e qual prazo de prova contratual/Marco Civil/fiscal/temporalidade/legal hold?
5. Qual primeiro ente B2G, edital, fiscal, publicação, medição e processo de aditivo/extinção será suportado?
6. O texto comercial pode dizer “não custodial”, “calculado” e “instruído” sem sugerir atividade regulada em cada fluxo?

### DPO/encarregado

1. Quem é controlador, operador, controlador independente ou conjunto em cada fluxo e contrato?
2. Quais bases legais, categorias, países, suboperadores, retenções e mecanismos da Resolução ANPD 19 serão aprovados?
3. Há acesso provável por crianças/adolescentes? Que controles ECA Digital/safeguarding serão exigidos?
4. Quais scores, elegibilidade, match, reputação e recomendações produzem efeito material; qual revisão humana independente, explicação e contestação?
5. Quais RIPDs, incidentes, comunicação ANPD/titulares, retenção de cinco anos e testes serão realizados?
6. O agente/grupo se enquadra como pequeno porte por operação, e quais exceções de alto risco realmente se aplicam?

### Contador(a)/fiscal/financeiro

1. Qual CNPJ, município, regime, item LC 116, retenções e emissor NFS-e correspondem à assinatura e à taxa?
2. Quando EFD-Reinf/DCTFWeb são exigíveis e o que será apenas exportado ao contador?
3. Qual PSP e qual papel regulatório: merchant, credenciador, subcredenciador, iniciador ou nenhum?
4. A operação seguirá exclusivamente pagamento direto financiador–projeto, sem custódia, split, repasse ou liquidação pela plataforma?
5. Quais eventos de cancelamento, pro rata, estorno, indisponibilidade e conciliação serão reais e testados?
6. Se houver retorno, dívida, participação, captação ou valor mobiliário, qual revisão CVM será aberta antes de qualquer UX?

### Responsável de impacto/ESG/direitos humanos

1. Qual unidade oficial de beneficiário, denominador, período, método e incerteza será adotada?
2. Quem valida evidência, resultados negativos, contrafactual/contribuição, direitos humanos e safeguarding?
3. Quais frameworks e edições serão realmente oferecidos: ODS/IBGE, ESG editorial, TSB, GRI, ISSB/CBPS, IRIS+ ou SROI?
4. Como claims públicos serão revisados, contestados, retraídos e separados de hipótese `Ready`/additionality?
5. Como participarão pessoas sem meios digitais, pessoas com deficiência, povos indígenas/tradicionais, vítimas e menores?
6. Há auditor independente ou certificador real? Se não, qual redação explícita de “não certificado/verificado”? 

## 12. Referências consolidadas

### Relatórios primários desta consolidação

- **[R01]** `knowledge-base/research/01-civil-consumer-contracts.md` — direito civil, contratos, CDC e assinaturas; fontes oficiais: Código Civil, CDC, Decreto 7.962/2013, MP 2.200-2/2001, Lei 14.063/2020, CPC, Marco Civil e Lei 14.133; jurisprudência STJ sobre assinatura, pessoa jurídica consumidora e cláusula limitativa.
- **[R02]** `knowledge-base/research/02-lgpd-anpd.md` — LGPD, ANPD, Resoluções 2/2022, 4/2023, 15/2024, 18/2024 e 19/2024, ECA Digital/Lei 15.211/2025 e Lei 15.352/2026 conforme data de corte informada.
- **[R03]** `knowledge-base/research/03-osc-mro-sc.md` — Lei 13.019/2014, Decreto 8.726/2016 e Decreto 11.948/2024, MROSC, Transferegov, OSCIP, CEBAS e fundos patrimoniais.
- **[R04]** `knowledge-base/research/04-public-procurement-innovation.md` — Lei 14.133/2021, LC 182/2021/CPSI, PNCP, TIC/nuvem, DFD/PCA/ETP/TR e diálogo competitivo.
- **[R05]** `knowledge-base/research/05-finance-tax-payment.md` — LC 116/2003, LC 175/2020, NFS-e, EFD-Reinf/DCTFWeb, Lei 12.865/2013, BCB, CVM, PLD e não custódia.
- **[R06]** `knowledge-base/research/06-impact-esg-sdg.md` — CVM 193/244/218, IFRS S1-S2, GRI, IRIS+, ODS/IBGE, OECD, TSB, direitos humanos e SROI.
- **[R07]** `knowledge-base/research/07-ai-algorithmic-governance.md` — IA, LGPD, ANPD, copyright, Marco Civil, ECA Digital, Decretos 12.975/12.976, OECD, UNESCO, NIST, ISO 42001 e governança de scoring.
- **[R08]** `knowledge-base/research/08-cybersecurity-trust.md` — Marco Civil, LGPD, E-Ciber (Decreto 12.573/2025), Decreto 12.975/2026, ANPD 15/2024, NIST CSF 2.0, SP 800-63B-4, SP 800-61r3, OWASP ASVS 5 e PostgreSQL RLS.
- **[R09]** `knowledge-base/research/09-integrations-egov.md` — Conecta gov.br, Transferegov, PNCP, Portal da Transparência, eSocial condicional, ePING, LGPD no Poder Público, Lei 14.129/2021, Lei 14.133/2021, Lei 14.063/2020.
- **[R10]** `knowledge-base/research/10-knowledge-content-publishing.md` — LAI, Governo Digital, Linguagem Simples, direitos autorais, LBI, eMAG 3.1, WCAG 2.2, ABNT NBR 17225, SEO e governança editorial.
- **[R11]** `knowledge-base/research/11-marketplace-partnerships.md` — CDC, Decreto 7.962/2013, Marco Civil, tese STF 2025, STJ Mercado Livre/links patrocinados, LGPD, COAF, BCB, CONAR e Senacon.
- **[R12]** `knowledge-base/research/12-governance-impact-workers-rights.md` — Constituição, MROSC, direitos humanos, ECA, LBI, não discriminação, integridade, trabalho decente, ILO, ONU e Mapa das OSC.

### URLs oficiais e institucionais preservadas

- **Civil/consumidor/assinaturas:** https://www.planalto.gov.br/ccivil_03/leis/2002/l10406compilada.htm ; https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm ; https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2013/decreto/d7962.htm ; https://www.planalto.gov.br/ccivil_03/mpv/antigas_2001/2200-2.htm ; https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2020/lei/l14063.htm ; https://www.gov.br/governodigital/pt-br/identidade/assinatura-eletronica/saiba-mais-sobre-a-assinatura-eletronica ; https://validar.iti.gov.br/sobre.html ; https://www.stj.jus.br/sites/portalp/Paginas/Comunicacao/Noticias/2024/03122024-Falta-de-credenciamento-da-entidade-certificadora-na-ICP-Brasil--por-si-so--nao-invalida-assinatura-eletronica-.aspx
- **LGPD/ANPD/transferência:** https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709compilado.htm ; https://www.gov.br/anpd/pt-br/documentos-e-publicacoes/regulamentacoes-da-anpd/resolucao-cd-anpd-no-2-de-27-de-janeiro-de-2022 ; https://www.in.gov.br/en/web/dou/-/resolucao-cd/anpd-n-15-de-24-de-abril-de-2024-556243024 ; https://www.gov.br/anpd/pt-br/acesso-a-informacao/institucional/atos-normativos/regulamentacoes_anpd/resolucao-cd-anpd-no-19-de-23-de-agosto-de-2024 ; https://www.gov.br/anpd/pt-br/assuntos/titular-de-dados/direito-dos-titulares ; https://www.gov.br/anpd/pt-br/assuntos/noticias/anpd-divulga-enunciado-sobre-o-tratamento-de-dados-pessoais-de-criancas-e-adolescentes/Enunciado1ANPD.pdf
- **OSCs/MROSC:** https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2014/lei/l13019compilado.htm ; https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2016/decreto/d8726.htm ; https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2024/Decreto/D11948.htm ; https://www.gov.br/transferegov/pt-br/legislacao/portarias/portaria-interministerial-sg-mgi-agu-no-197-de-11-de-agosto-de-2025 ; https://www.gov.br/transferegov/pt-br/legislacao/portarias/MANUALMROSCDoPlanejamentoPrestaodeContasreduzido13082025.pdf
- **Compras/PNCP:** https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2021/lei/l14133.htm ; https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp182.htm ; https://www.gov.br/pncp/pt-br/pncp ; https://licitacoesecontratos.tcu.gov.br/3-6-5-dialogo-competitivo-2/ ; https://sites.tcu.gov.br/cpsi/
- **Fiscal/pagamentos:** https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp116.htm ; https://www.gov.br/nfse/pt-br/municipios/produtos-disponiveis/api-de-integracao ; https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/perguntas-frequentes/sped/efd-reinf/efdr ; https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2013/lei/l12865.htm ; https://www.bcb.gov.br/estabilidadefinanceira/instituicaopagamento ; https://www.bcb.gov.br/estabilidadefinanceira/exibenormativo?tipo=Resolu%C3%A7%C3%A3o%20BCB&numero=80 ; https://www.planalto.gov.br/ccivil_03/leis/l6385compilada.htm ; https://www.planalto.gov.br/ccivil_03/leis/l9613.htm
- **Impacto/ESG/IA:** https://conteudo.cvm.gov.br/export/sites/cvm/legislacao/resolucoes/anexos/100/resol193consolid.pdf ; https://conteudo.cvm.gov.br/cvm_institucional/export/sites/cvm/legislacao/resolucoes/anexos/200/resol218.pdf ; https://www.ifrs.org/issued-standards/ifrs-sustainability-standards-navigator/ifrs-s1-general-requirements/ ; https://www.globalreporting.org/standards/standards-development/universal-standards/ ; https://iris.thegiin.org/document/iris-and-social-return-on-investment/ ; https://odsbrasil.gov.br/relatorio/sintese ; https://www.nist.gov/itl/ai-risk-management-framework ; https://www.iso.org/standard/81230.html ; https://www.planalto.gov.br/ccivil_03/leis/l9610.htm
- **Cibersegurança:** https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2025/decreto/d12573.htm ; https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2026/decreto/d12975.htm ; https://www.nist.gov/publications/nist-cybersecurity-framework-csf-20 ; https://csrc.nist.gov/pubs/sp/800/63/b/4/final ; https://csrc.nist.gov/pubs/sp/800/61/r3/final ; https://owasp.org/projects/asvs ; https://www.postgresql.org/docs/current/ddl-rowsecurity.html
- **Governo/integrações/conteúdo:** https://www.gov.br/governodigital/pt-br/infraestrutura-nacional-de-dados/interoperabilidade/conecta-gov.br ; https://www.gov.br/transferegov/pt-br/sobre/transferegov ; https://www.gov.br/transferegov/pt-br/ferramentas-gestao/api-de-dados-abertos-transferegov.br ; https://www.gov.br/pncp/ ; https://portaldatransparencia.gov.br/api-de-dados ; https://www.gov.br/esocial/pt-br/documentacao-tecnica/manuais/manualorientacaodesenvolvedoresocialv1-9.pdf ; https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2011/lei/l12527.htm ; https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2025/lei/l15263.htm ; https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2015/lei/l13146.htm ; https://www.w3.org/TR/WCAG22/ ; https://emag.governoeletronico.gov.br/ ; https://abnt.org.br/lancamento-da-abnt-nbr-17225/
- **Direitos humanos/trabalho:** https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm ; https://www.planalto.gov.br/ccivil_03/leis/l8069.htm ; https://www.planalto.gov.br/ccivil_03/leis/l9029.htm ; https://www.planalto.gov.br/ccivil_03/leis/l7716.htm ; https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2023/lei/l14611.htm ; https://www.ilo.org/topics-and-sectors/fundamental-principles-and-rights-work ; https://www.ohchr.org/en/publications/reference-publications/guiding-principles-business-and-human-rights ; https://mapaosc.ipea.gov.br/metodologia

## 13. Registro de revisão

Na próxima revisão, confrontar esta base com as fontes oficiais na data real, executar a reconciliação 42/45 e 873/894, atualizar o manifesto de módulos, validar os atos de 2026 mencionados nos relatórios, e substituir cada `D` resolvido por decisão/evidência rastreável. Qualquer alteração de wording de claim passa por advogado/DPO/contador/responsável de impacto conforme o domínio.
