# Política de Cancelamento — Plataforma Impacto

> **MINUTA — DRAFT FOR LEGAL REVIEW — [VALIDAR JURÍDICO]**. Rascunho técnico escrito a partir do funcionamento real do
> software (v0.17.0), não de um modelo de contrato. **Não é aconselhamento jurídico e não pode ser publicado, exibido como
> vigente nem aceito por nenhum usuário sem revisão de advogado(a).** Campos entre `{{ }}` dependem de decisão do
> proprietário. Enquanto esta minuta não for aprovada, o banco se recusa a registrar aceite dela (ver
> `docs/LEGAL_FRAMEWORK.md`).

Versão da minuta: 2026-10-06 · Aplica-se à versão de software 0.17.0 · Chave: `cancellation`

## 1. Como cancelar
1.1. Pela própria Plataforma, pela organização, sem precisar falar com ninguém e sem retenção por telefone.
1.2. O cancelamento é registrado com data, autoria e situação anterior, em trilha append-only.

## 2. Efeito
2.1. O cancelamento encerra a **renovação**. O acesso ao plano pago segue até o fim do ciclo já pago.
2.2. Ao fim do ciclo, a organização **volta ao plano gratuito** e continua com acesso ao que já criou, nos limites do plano
gratuito. Cancelar **não apaga dados**.
2.3. Recurso pago acima do limite gratuito deixa de aceitar **nova** criação; o que já existe continua legível e exportável.

## 3. Exportação antes de sair
3.1. A organização pode exportar seus dados antes e depois do cancelamento, pelos recursos de exportação e de pedido de
titular (LGPD).

## 4. Direito de arrependimento (CDC art. 49)
4.1. **Questão aberta, não decidida nesta minuta**: o art. 49 garante 7 dias para desistir de contratação feita fora do
estabelecimento, **ao consumidor**. Se a contratante for OSC ou empresa usando a Plataforma como insumo da própria
atividade, pode não ser consumidora, e o prazo pode não incidir.
4.2. Enquanto o jurídico não responder, a Plataforma **não afirma** ter nem não ter esse prazo. A regra operacional
provisória proposta é a mais favorável à contratante: 7 dias, com devolução integral — ver Política de Reembolso.

## 5. Cancelamento pela Plataforma
5.1. Hipóteses: fraude, inserção de dado falso em prestação de contas, uso para fim ilícito, inadimplência após o prazo de
tolerância.
5.2. Em qualquer hipótese: aviso com motivo, prazo para exportar os dados e preservação do acervo pelo prazo de retenção.

## 6. Perguntas abertas para o jurídico
1. A resposta de 4.1 (consumidora ou não).
2. Cancelamento imediato com pro rata é obrigatório em algum cenário?
3. Qual prazo de guarda após o encerramento — e como ele se concilia com a minimização da LGPD?
