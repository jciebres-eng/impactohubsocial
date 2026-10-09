# Handoff para continuidade — IMPACTO Trust v0.26.0

**Objetivo:** permitir que Claude/agentes/editores continuem a implantação sem inventar fatos, compliance, integrações ou decisões profissionais.  
**Leitura obrigatória antes de alterar:**

1. `knowledge-base/MASTER-KNOWLEDGE-BASE.md`
2. `knowledge-base/KNOWLEDGE-MANIFEST.json`
3. `knowledge-base/LEGAL-APPLICABILITY-MATRIX.csv`
4. `knowledge-base/CHANGELOG.md`
5. os relatórios de `knowledge-base/research/01-*.md` a `12-*.md`
6. `README.md`, `VERSION`, `TECHNICAL_FINALIZATION_STATUS.md`, `docs/RELEASE_READINESS.md`, `docs/legal/*`, `docs/execution/INTEGRATION_HOMOLOGATION_MATRIX.csv`

## 1. Estado que não pode ser alterado por inferência

- O release é **v0.26.0**, com base técnica declarada/fechada, mas **não publicado**.
- Não há, no estado pesquisado, cobrança real, PSP/fiscal/WhatsApp/mapas/IA externos ativos ou integração governamental homologada; a matriz atual marca provedores e `government_api` como `BLOCKED`/`SCAFFOLDED`.
- Os documentos legais em `docs/legal` são **minutas** até haver aprovação, vigência, versão efetiva, hash e referência.
- `platform_advanced` não é automaticamente ICP-Brasil, assinatura qualificada, Gov.br, certificação ITI ou carimbo de tempo externo.
- Arquitetura não custodial significa CALCULA/INSTRUI/CONCILIA; não adicionar wallet, saldo de terceiro, split, payout, escrow, repasse ou liquidação sem nova decisão jurídica/regulatória e mudança explícita de escopo.
- `Ready`, maturidade, score, reputação, additionality, elegibilidade, impacto e thresholds são estados/hipóteses de produto, nunca certificados, fatos jurídicos ou garantia de financiamento.
- `unknown` não é zero; autodeclarado não é validado; teste interno não é homologação, auditoria independente ou certificação.
- Há contradições abertas: 42 versus 45 motores; outras contagens de telas/operações/rotas; documentos em versões históricas; alegação de axe com escopo divergente. Não “corrigir” escolhendo um número: gerar manifesto do código e registrar a decisão.

## 2. Protocolo evidence-first

Para cada alteração:

1. **Defina a pergunta e o escopo:** persona, fluxo, jurisdição, período, finalidade, dados, dinheiro, conteúdo e efeito material.
2. **Classifique O/A/V/H/D:** obrigação normativa; autoridade/orientação; voluntário; hipótese; decisão/dependência/evidência pendente.
3. **Leia a fonte primária:** preservar URL, órgão/autor, título, data, artigo/seção, edição, vigência, jurisdição, licença e data de acesso.
4. **Não use snippet como prova:** abrir a fonte e conferir o texto. Se indisponível, marcar `D` e não completar.
5. **Mapeie implementação e teste:** arquivo/rota/migração, teste positivo, teste negativo, escopo, evidência, hash e data.
6. **Peça decisão profissional:** advogado para jurídico/contratos/consumer/B2G; DPO/encarregado para LGPD; contador para fiscal; segurança independente para segurança; responsável de impacto para método/claims de impacto.
7. **Atualize o conjunto:** master, matriz, manifest, changelog, documentação de versão e claim registry; não alterar só um arquivo.
8. **Relate incerteza:** “não encontrado”, “não verificado”, “depende de ente/contrato”, “hipótese interna” e “revisão requerida” são resultados válidos.

## 3. Regras para pesquisar e citar

- Priorizar Planalto, Diário Oficial, ANPD, BCB, CVM, TCU, Governo Digital, PNCP, Transferegov, Receita, ITI, Senacon, MTE, STF/STJ, W3C/NIST/OWASP/IFRS/GRI/ILO/ONU e fontes acadêmicas institucionais.
- Preservar os URLs fornecidos pelos 12 relatórios; se uma página redirecionar, salvar URL original e URL efetiva.
- Não transformar guia, FAQ, manual, padrão voluntário, jurisprudência isolada ou literatura em lei.
- Não tratar uma decisão judicial como regra universal sem analisar fatos, tribunal, data e limites.
- Para atos de 2025/2026 mencionados nos relatórios, revalidar vigência e texto consolidado antes de marcar `O`.
- Citar perto da afirmação com `[R01]`…`[R12]` e manter a URL no relatório/master/matriz.

## 4. Regras por domínio

### Jurídico e contrato

- Não editar minuta para “parecer aprovada”. Criar nova versão, submeter ao advogado e manter estado `DRAFT/BLOCKED`.
- Separar acceptance, signature e approval; registrar poderes/procuração; não prometer assinatura qualificada ou prova pública.
- Não escolher CDC, responsabilidade, cancelamento, estorno, retenção ou assinatura para todas as personas sem análise por fluxo.

### DPO/LGPD

- Não declarar “conforme LGPD”, “sem dados sensíveis”, “sem transferência”, “RIPD concluído” ou “revisão humana” sem ROPA, base, papel, evidência e aprovação.
- Não habilitar modelo externo por configurar uma chave. Exigir provider register, país, subprocessadores, contrato, retenção/deleção, base legal e RIPD quando necessário.
- Direitos, crianças, incidentes e transferências têm gates próprios; o prazo do relatório é uma orientação de implementação, não autorização para omitir análise do caso.

### Fiscal, financeiro e pagamentos

- Não criar cobrança, QR, Pix, boleto, NFS-e, estorno ou webhook real sem provedor, credencial, contrato, papel e testes.
- Não classificar o serviço fiscalmente por analogia; contador deve decidir CNPJ, município, regime, item, retenção e obrigação acessória.
- Se aparecer retorno, participação, dívida, captação, conta de terceiro ou custódia, parar e abrir revisão BCB/CVM/PLD.

### IA, impacto e reputação

- Não usar score, reputação, Ready, elegibilidade, prioridade ou recommendation para decidir ou prometer financiamento sem finalidade, base, explicação, revisão, contestação, fairness e dados calibrados.
- Não apresentar `additionality_score`, SROI, ODS, ESG, GRI, ISSB ou impacto como prova sem método, fonte, incerteza e revisão independente.
- O assistente é extrativo: citar fonte aprovada, versão, data, hash e trecho; abster-se para fonte vencida/terceira/demo/privada ou licença incerta.

### Governo e conteúdo

- Não dizer “PNCP/Transferegov/Gov.br integrado” porque existe um adapter ou mock. Só promoção após autorização, sandbox/produção, credencial, contrato de dados, reconciliação e evidência externa.
- Não dizer “oficial”, “vigente”, “homologado”, “WCAG conforme”, “ABNT conforme” ou “livre de direitos” sem prova do escopo.
- Conteúdo deve ter source/version/hash/license/reviewer/review_due/accessibility/canonical/retraction; quatro olhos na publicação.

### Segurança

- Não converter testes internos em certificação, invulnerabilidade, DR garantido, MFA resistente a phishing, KMS/HSM ou isolamento absoluto.
- Manter separados registros do Marco Civil, logs de segurança, auditoria e incidentes; não ampliar retenção por conveniência.
- Testar tenant isolation, RLS, funções SECURITY DEFINER, jobs, cache, arquivos, webhooks, exportações, restore, rotação e destruição de chaves.

## 5. Formato mínimo de uma decisão nova

```text
ID:
Data:
Owner:
Pergunta/fluxo:
Persona/ente/jurisdição:
Classificação O/A/V/H/D:
Fonte primária e URL:
Artigo/seção/edição/vigência:
Estado atual verificado:
Decisão profissional (nome, função, data):
Implementação/arquivo/rota:
Teste positivo:
Teste negativo:
Evidência e hash:
Claim público permitido:
Claim proibido/limite:
Review_due:
Status: DRAFT | CONDITIONAL | ACTIVE | BLOCKED | SUPERSEDED | RETRACTED
```

## 6. Ordem de execução recomendada

1. Resolver P0 em `CHANGELOG.md`: legal gate, LGPD/DPO, claims, não custódia/fiscal, integrações, incidentes/backup, autorização e reconciliação documental.
2. Gerar o manifesto real de módulos/motores/rotas/telas a partir do código; atualizar README e documentos sem apagar históricos.
3. Obter decisões de advogado, DPO, contador e responsável de impacto; anexar registros e versionar.
4. Implementar gates e testes negativos antes de adicionar UX/integrações.
5. Homologar uma única rota/ente/provedor de cada vez; manter todos os outros bloqueados.
6. Executar revisão independente e go-live checklist; publicar apenas claims que a evidência sustenta.
7. Agendar revisão conforme o manifesto; mudança legal, incidente, provedor, modelo, contrato ou framework dispara revisão extraordinária.

## 7. Resposta esperada ao reportar progresso

Sempre informar: **feito**, **não feito**, **evidência**, **escopo**, **risco residual**, **decisão requerida**, **status da matriz**, **claim permitido** e **próxima revisão**. Nunca responder apenas “conforme”, “seguro”, “homologado”, “oficial”, “pronto” ou “certificado”.

> Se a evidência não existe, a resposta correta é: **“não verificado; permanece bloqueado; esta é a decisão/prova necessária.”**
