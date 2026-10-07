# Contrato Institucional (B2B / Enterprise / ESG) — Plataforma Impacto

> **MINUTA — DRAFT FOR LEGAL REVIEW — [VALIDAR JURÍDICO]**. Rascunho técnico escrito a partir do funcionamento real do
> software (v0.17.0), não de um modelo de contrato. **Não é aconselhamento jurídico e não pode ser publicado, exibido como
> vigente nem aceito por nenhum usuário sem revisão de advogado(a).** Campos entre `{{ }}` dependem de decisão do
> proprietário. Enquanto esta minuta não for aprovada, o banco se recusa a registrar aceite dela (ver
> `docs/LEGAL_FRAMEWORK.md`).

Versão da minuta: 2026-10-06 · Aplica-se à versão de software 0.17.0 · Chave: `b2b`

## 1. Objeto
Uso institucional da Plataforma por empresa, instituto, fundação ou financiador para **gerir o próprio portfólio de
investimento social**: programas, chamadas, carteira de projetos apoiados, indicadores, prestação de contas recebida e
relatório de impacto consolidado.

## 2. O problema que este contrato resolve
2.1. A contratante compra **a gestão do portfólio e a prestação de contas auditável**, não um pacote de telas. A Plataforma
substitui planilha paralela, pasta de e-mail e relatório montado à mão no fim do ano.
2.2. O que a contratante leva: programa com chamadas e carteira; indicadores com linha de base **e fonte**; distinção
mantida entre valor **declarado** e valor **medido**, e entre despesa **registrada** e despesa **comprovada**; cadeia de
resultado com a força de cada elo declarada; lacuna territorial da carteira; trilha append-only de cada mudança, com
notificação a toda a equipe envolvida.

## 3. O que este contrato NÃO inclui
3.1. **Não inclui** repasse, custódia ou processamento de aporte. O dinheiro circula fora da Plataforma.
3.2. **Não inclui** auditoria independente, parecer contábil nem atestado de impacto. A Plataforma organiza a evidência;
não assina laudo.
3.3. **Não inclui** SLA: não há disponibilidade contratada (ver Contrato de Assinatura, cláusula 6).
3.4. **Não inclui** emissão de nota fiscal automatizada: não há provedor fiscal integrado.
3.5. **Não inclui** relatório regulatório pronto para CVM, GRI, SASB ou ISSB. A Plataforma exporta dado estruturado e
rastreável; a conformidade do relatório com um referencial específico depende de trabalho adicional e de decisão da
contratante. Afirmar aderência a referencial não implementado seria falso.

## 4. Preço
4.1. Por contrato, com base em escopo: número de programas, carteira, assentos, integrações e necessidade de implantação.
4.2. **Nenhum preço institucional está declarado no sistema**, e nenhum está embutido no código. O preço de contrato é
decisão comercial do proprietário e entra como anexo.
4.3. Implantação (migração de carteira histórica, modelagem de indicadores, treinamento) é escopo **separado**, com preço
próprio.

## 5. Dados e LGPD
5.1. Cada organização enxerga os próprios dados. O isolamento é imposto pelo banco (RLS), não pela interface, e há teste
automatizado de isolamento entre organizações.
5.2. A contratante é controladora dos dados que insere; a Plataforma é operadora quanto a esses dados. O inverso vale para
os dados de cadastro da própria contratante.
5.3. Subcontratação de infraestrutura e transferência internacional: `{{DECLARAR — depende da hospedagem escolhida}}`.

## 6. Propriedade
6.1. O dado da contratante é da contratante, exportável em formato aberto a qualquer momento, durante e após o contrato.
6.2. O software é da Plataforma. Nada aqui transfere código.

## 7. Perguntas abertas para o jurídico
1. Quem é controlador e quem é operador em cada fluxo? A minuta propõe 5.2 e precisa de conferência.
2. É necessário Acordo de Processamento de Dados anexo? A minuta assume que sim.
3. Cláusula de auditoria pela contratante: até onde vai (log? ambiente? código?).
4. Teto de responsabilidade e seguro: `{{DECISÃO DO PROPRIETÁRIO}}`.
