# Changelog de conhecimento — IMPACTO Trust v0.26.0

**Data da consolidação:** 2026-10-08  
**Estado:** plano de correção e governança; uma recomendação não é evidência de implementação.  
**Regra:** não apagar históricos. Marcar versões antigas como `HISTORICAL`, `DRAFT`, `SUPERSEDED` ou `RETRACTED`; publicar somente após o gate correspondente.

## 2026-10-09 — v0.29.0: reconciliação com a release (código, banco e testes)

- A base entrou no repositório do produto **sem alteração** dos arquivos de 2026-10-08 (são a fonte; nada foi reescrito).
- `CONTROL-RECONCILIATION.json`: cada controle LEG-001..058 classificado contra o CÓDIGO da release v0.29.0 — `IMPLEMENTED_TESTED` 6, `PARTIAL` 27, `BLOCKED_EXTERNAL` 13, `NOT_IMPLEMENTED` 12 — com os testes que provam cada estado (237 referências conferidas por análise estática; teste `test_v0290_knowledge_base`).
- O que a release implementou a partir desta base: registro de fontes com classe O/A/V/H/D e direitos de uso (`kb_sources`), citações com trecho só por direito permitido, retirada terminal com motivo, fila editorial, assistente que cita e se abstém, busca medida (ADR-353 a ADR-358). Isso **não** muda o status dos controles bloqueados por terceiro (parecer, provedor, DPO): eles continuam `P0_BLOCKED`/`BLOCKED_EXTERNAL`.
- As 11 fontes semeadas no banco a partir desta base estão `unverified`, revisão marcada para 2026-11-07.

## 2026-10-08 — consolidação das 12 pesquisas

- Criada a base mestre operacional com inventário de módulos, hierarquia de fontes, taxonomia **O/A/V/H/D**, ciclo de vida, claims, gaps, checklist de go-live, perguntas profissionais e URLs preservadas.
- Criado o manifesto JSON com data de pesquisa, domínios, relatórios, tags, periodicidade, status e contradições conhecidas.
- Criada a matriz CSV com obrigação, classificação, fonte, controle, teste, responsável, revisão e status.
- Registrado que o produto está **não publicado**, que não há cobrança/provedor fiscal/IA/governo efetivos e que minutas legais permanecem draft conforme as pesquisas e documentação disponível.
- Registradas as divergências **42 versus 45 motores**, contagens/versionamentos históricos e a diferença entre evidência interna, homologação externa e claim público.

## P0 — bloquear lançamento, cobrança, decisões externas e claims

1. **Legal release gate:** revisar/aprovar as onze minutas legais; registrar versão efetiva, jurisdição, vigência, aprovador, hash, changelog e referência. Manter `DRAFT/BLOCKED` até conclusão. [R01, R02, R10]
2. **Matriz civil/consumerista:** decidir CDC por persona, finalidade, destinatário final e vulnerabilidade; definir assinatura/representação/B2G/cancelamento/responsabilidade/retenção por fluxo. [R01, R11]
3. **LGPD/DPO:** fechar ROPA, bases, papéis, RIPDs, encarregado, direitos, incidentes, retenções, suboperadores, transferências e crianças. [R02]
4. **Claim gate/editorial:** bloquear “conforme”, “certificado”, “oficial”, “homologado”, “impacto comprovado”, “sem transferência”, “sem dados sensíveis” e equivalentes sem evidência específica. [R02, R06, R07, R08, R10, R12]
5. **Não custódia e comercial:** manter taxa, checkout, wallet, saldo, split, payout, escrow, repasse, liquidação e retorno financeiro bloqueados; abrir revisão BCB/CVM se o escopo mudar. [R05]
6. **Fiscal real:** definir entidade/CNPJ, município, item LC 116, regime, retenções, emissor NFS-e e contador antes de `platform_service_fee`; sem provedor não emitir nem prometer NFS-e. [R05]
7. **Integrações governamentais:** manter `government_api`/PNCP/Transferegov/Gov.br/eSocial como `BLOCKED_EXTERNAL` ou fora do escopo até órgão, finalidade, credenciais, contrato de dados, sandbox e reconciliação. [R04, R09]
8. **Incidentes/segurança:** separar logs, implementar registro regulatório, relógio de conhecimento, comunicações e retenção; fechar backup off-site, RPO/RTO, restore, KMS/HSM ou decisão de risco. [R02, R08]
9. **Autorização:** revisar ABAC por recurso/linha e testar API, SQL/RLS, funções privilegiadas, jobs, cache, arquivos, webhooks e exportações. [R08]
10. **Reconciliação documental:** gerar manifesto único do código e corrigir contagem de motores/rotas/operações/telas e links v0.17/v0.26 antes de comunicação externa. [R07, R08, R10]

## P1 — fechar antes de piloto com usuários reais

1. Implementar matriz de aplicabilidade por ente/jurisdição para MROSC, procurement, diálogo competitivo, CPSI e contratos locais. [R03, R04]
2. Completar portal de direitos, contestação de score/reputação, revisão humana independente e logs de decisão material. [R02, R07, R12]
3. Implantar rights/provenance ledger por documento/arquivo para upload, indexação, resumo, embedding, treino, tradução/adaptação e saída. [R07, R10]
4. Corrigir assistente extrativo: fonte vencida/terceira/demo, rótulo oficial, cópia substancial, abstinência e isolamento por tenant. [R07, R10]
5. Versionar ODS/IBGE, TSB, GRI, ISSB/CBPS, IRIS+ e SROI; manter `ods_targets` indisponível até importação verificável; retirar additionality numérico público. [R06]
6. Fechar beneficiary counts: unidade, período, denominador, método, fonte, qualidade, incerteza, snapshot e não-ranqueamento isolado. [R12]
7. Adotar WCAG 2.2 AA como meta com teste de teclado, leitor de tela, zoom/reflow, documentos, vídeo e humano; reconciliar axe/relatório. [R10]
8. Criar safeguarding, canais de denúncia, encaminhamento, reparação, acessibilidade e anti-revitimização. [R07, R12]
9. Completar contratos de dados por API: finalidade, base, papel, campos, schema, freshness, retenção, países, rate limit, Retry-After, idempotência, observabilidade, recovery e saída. [R09]
10. Definir cancelamento, pro rata, arrependimento, indisponibilidade, retenção por uso e estorno; testar somente com provedor real quando contratado. [R01, R05]
11. Executar ASVS 5, SAST/DAST, dependências e revisão/pentest independente; declarar apenas escopo testado. [R08]

## P2 — escala, maturidade e diferenciação

1. Se necessário ao caso de uso, contratar/homologar TSA RFC 3161, verificação pública, QR, revogação, KYC e assinatura ICP-Brasil/Gov.br; nunca simular essas capacidades. [R01, R03]
2. Implementar metodologia de avaliação SROI/contrafactual/contribuição, sensibilidade, deadweight, atribuição, deslocamento e revisão independente. [R06]
3. Promover adapters oficiais PNCP/Transferegov/eSocial somente após autorização e testes reais por módulo/ambiente. [R09]
4. Construir governança de fornecedores/suboperadores, países, retenção, deleção, modelos de IA, licenças e plano de saída. [R02, R05, R07]
5. Reavaliar fairness, reidentificação, acessibilidade, participação digital, direitos humanos e safeguarding com dados reais e revisão independente. [R07, R12]
6. Automatizar lint de claims, stale sources, versão legal, licença, review_due, manifest de motores e consistência entre README/documentação/código.

## Definition of done de cada item

Um item só pode ir para `DONE` quando houver: (a) decisão do owner profissional quando aplicável; (b) fonte/contrato/edição vigente; (c) implementação no escopo; (d) teste positivo e negativo; (e) evidência anexada com data e hash; (f) revisão independente proporcional; (g) wording público limitado ao que a evidência sustenta; (h) atualização de manifesto, matriz e handoff.
