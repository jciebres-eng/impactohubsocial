# Contrato de Assinatura (SaaS) — Plataforma Impacto

> **MINUTA — DRAFT FOR LEGAL REVIEW — [VALIDAR JURÍDICO]**. Rascunho técnico escrito a partir do funcionamento real do
> software (v0.17.0), não de um modelo de contrato. **Não é aconselhamento jurídico e não pode ser publicado, exibido como
> vigente nem aceito por nenhum usuário sem revisão de advogado(a).** Campos entre `{{ }}` dependem de decisão do
> proprietário. Enquanto esta minuta não for aprovada, o banco se recusa a registrar aceite dela (ver
> `docs/LEGAL_FRAMEWORK.md`).

Versão da minuta: 2026-10-06 · Aplica-se à versão de software 0.17.0 · Chave: `subscription`

## 1. Objeto
1.1. Licença de uso, não exclusiva e não transferível, da Plataforma Impacto em regime de software como serviço, no plano
contratado, pelo prazo e pelo preço vigentes no momento da contratação.
1.2. A assinatura é **da organização**, não da pessoa que a contratou. A saída da pessoa não encerra o contrato.

## 2. O que é gratuito e permanece gratuito
2.1. Cadastro, perfil, criação de projeto, descoberta de oportunidades, participação na rede e acompanhamento básico são
**gratuitos e permanecem gratuitos** (plano `osc_basic`, "OSC — gratuito", declarado em `config/plans.json`).
2.2. A gratuidade acima não é promoção nem cortesia por prazo determinado: é o modelo econômico da Plataforma. A OSC
proponente não é a pagadora principal.
2.3. O plano gratuito tem limites técnicos declarados (projetos ativos, requisições de IA por mês, armazenamento, assentos e
buscas salvas). Limite técnico não é cobrança: ao atingi-lo, a organização continua com acesso ao que já criou.

## 3. Planos, preço e reajuste
3.1. O preço vigente de cada plano é o registrado em `plan_price_versions`, com início de vigência, moeda e motivo.
**Nenhum preço está embutido no código**; há teste automatizado que falha se alguém embutir.
3.2. Alteração de preço **não atinge vigência em curso**: abre nova versão, com vigência futura.
3.3. Aviso prévio de reajuste: `{{PRAZO — a minuta sugere 30 dias}}`, por notificação na Plataforma e por e-mail.
3.4. Moeda: BRL.

## 4. Pagamento
4.1. **Nenhum provedor de pagamento está configurado nesta instalação.** Não há conta, chave nem identificador de preço de
provedor. Em consequência, **a Plataforma não pode, hoje, receber pagamento de assinatura**, e toda cobrança existente no
sistema está marcada como simulada (`platform_charges.is_simulated`).
4.2. Enquanto 4.1 for verdadeiro, a contratação de plano pago depende de acerto fora da Plataforma e de registro manual pela
administração, com fatura em provedor `manual`.
4.3. Quando houver provedor, aplicam-se as condições do **Contrato de Pagamento** (`payment`).

## 5. Vigência, renovação e encerramento
5.1. Ciclo: `{{mensal | anual}}`, com renovação automática, salvo cancelamento.
5.2. O cancelamento segue a **Política de Cancelamento** (`cancellation`) e a **Política de Reembolso** (`refund`).
5.3. Encerrada a assinatura, a organização **não perde os dados**: volta ao plano gratuito, com os limites dele. Exclusão de
dados só ocorre por pedido do titular (LGPD) ou pela política de retenção documentada.

## 6. Disponibilidade
6.1. **Não há SLA contratado.** A Plataforma não promete percentual de disponibilidade, janela de manutenção nem prazo de
restabelecimento, porque nenhum desses números foi medido em operação real nem contratado com fornecedor de infraestrutura.
6.2. Afirmar disponibilidade que não foi medida seria falso. Qualquer compromisso de SLA exige decisão do proprietário,
contrato de infraestrutura e instrumentação — e deve entrar como anexo a este contrato.

## 7. Suporte
7.1. Canal: `{{E-MAIL / CANAL}}`. **Sem prazo de resposta contratado** pelo mesmo motivo da cláusula 6.

## 8. Obrigações da contratante
8.1. Manter dados e documentos verdadeiros e atualizados.
8.2. Responder pelo conteúdo que publica, inclusive por projetos, prestações de contas e evidências.
8.3. Não usar a Plataforma para fraude, nem inserir dado falso em prestação de contas.

## 9. Limites de responsabilidade
9.1. A Plataforma **não garante aprovação** em edital, chamamento ou processo de seleção.
9.2. A Plataforma **não é parte** dos acordos entre organizações e financiadores e **não custodia nem processa aportes**.
9.3. Textos gerados com assistência de IA são **rascunhos** sob responsabilidade de quem os aprova.
9.4. Estimativas fiscais são informativas e não substituem contador.

## 10. Perguntas abertas para o jurídico
1. A OSC/empresa contratante é **consumidora** para fins do CDC? A resposta muda cláusulas 5, 9 e toda a política de
   reembolso. A minuta **não** assume a resposta.
2. Limite de responsabilidade por valor (teto) é admissível no cenário escolhido em (1)?
3. Foro e cláusula de mediação: `{{DECISÃO DO PROPRIETÁRIO}}`.
4. A gratuidade permanente declarada em 2.2 cria direito adquirido? Como redigir sem criar obrigação perpétua e sem
   enganar a OSC?
