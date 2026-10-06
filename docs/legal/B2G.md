# Contrato com o Poder Público (B2G) — Plataforma Impacto

> **MINUTA — DRAFT FOR LEGAL REVIEW — [VALIDAR JURÍDICO]**. Rascunho técnico escrito a partir do funcionamento real do
> software (v0.17.0), não de um modelo de contrato. **Não é aconselhamento jurídico e não pode ser publicado, exibido como
> vigente nem aceito por nenhum usuário sem revisão de advogado(a).** Campos entre `{{ }}` dependem de decisão do
> proprietário. Enquanto esta minuta não for aprovada, o banco se recusa a registrar aceite dela (ver
> `docs/LEGAL_FRAMEWORK.md`).

Versão da minuta: 2026-10-06 · Aplica-se à versão de software 0.17.0 · Chave: `b2g`

## 1. Objeto
Uso da Plataforma por órgão ou entidade pública para **publicar chamamento, receber e analisar proposta, acompanhar
execução e receber prestação de contas** de organizações da sociedade civil.

## 2. O problema que este contrato resolve
2.1. O órgão compra **trilha auditável de chamamento público**: edital publicado com data, propostas recebidas com hora,
análise com motivo registrado, execução acompanhada com evidência anexada e prestação de contas organizada.
2.2. O que o órgão leva: trilha append-only de cada ato; distinção entre o que foi declarado e o que foi comprovado;
lacuna territorial do conjunto de projetos apoiados; notificação a toda a equipe envolvida em cada etapa.

## 3. O que este contrato NÃO inclui — e aqui está a parte que não pode ser maquiada
3.1. **Não inclui assinatura digital qualificada, ICP-Brasil, integração gov.br, certificado digital nem biometria.** Nada
disso está implementado, e nada disso será simulado. Ato que exija assinatura qualificada **tem de ser praticado fora da
Plataforma** enquanto isso for verdade.
3.2. **Não inclui** integração com SICONV/Transferegov, SIAFI, Portal da Transparência, e-SIC nem sistema de compras
governamental. Não há credencial, convênio técnico nem documentação de integração contratada.
3.3. **Não inclui** processo eletrônico oficial (SEI ou equivalente). A Plataforma não é sistema de processo administrativo.
3.4. **Não inclui** publicação em diário oficial.
3.5. **Não inclui** parecer jurídico nem de controle interno.
3.6. **Não inclui** SLA nem plano de continuidade contratado.
3.7. A Plataforma **não substitui** o procedimento legal do chamamento. Ela o organiza e o documenta.

## 4. Contratação pelo órgão
4.1. A contratação depende do procedimento da Lei 14.133/2021 aplicável ao caso, cuja escolha é do órgão e de sua
assessoria jurídica. **A Plataforma não afirma caber em dispensa, em inexigibilidade nem em qualquer hipótese específica**:
essa afirmação, feita por quem vende, é exatamente o tipo de alegação que compromete o processo.
4.2. A Plataforma fornece, quando solicitada, descrição técnica verdadeira do que o software faz e do que não faz —
inclusive esta cláusula 3 inteira.

## 5. Dados públicos e acesso à informação
5.1. Dado de chamamento é público por natureza e assim é tratado.
5.2. Dado pessoal de proponente segue a LGPD, inclusive o art. 7º, III (execução de política pública), cuja aplicação ao
caso concreto é decisão do órgão.
5.3. Pedido de acesso à informação é respondido pelo órgão. A Plataforma fornece o dado ao órgão.

## 6. Preço
6.1. `{{DEFINIR}}`. Não há preço de B2G declarado no sistema e nenhum embutido no código.
6.2. Referência pública de preço, quando usada, é citada com fonte e data — nunca estimada de cabeça.

## 7. Perguntas abertas para o jurídico
1. Qual o enquadramento da contratação na Lei 14.133/2021 para cada perfil de órgão? Pergunta para a assessoria do órgão,
   não para o fornecedor.
2. A ausência de assinatura qualificada (3.1) impede qual ato, exatamente, em qual etapa do chamamento?
3. É necessário Acordo de Cooperação Técnica em vez de contrato de serviço em algum cenário?
4. Guarda e eliminação de documento público na Plataforma: qual tabela de temporalidade se aplica?
