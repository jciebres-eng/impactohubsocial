# Termos do Marketplace de Serviços — Plataforma Impacto

> **MINUTA — DRAFT FOR LEGAL REVIEW — [VALIDAR JURÍDICO]**. Rascunho técnico escrito a partir do funcionamento real do
> software (v0.17.0), não de um modelo de contrato. **Não é aconselhamento jurídico e não pode ser publicado, exibido como
> vigente nem aceito por nenhum usuário sem revisão de advogado(a).** Campos entre `{{ }}` dependem de decisão do
> proprietário. Enquanto esta minuta não for aprovada, o banco se recusa a registrar aceite dela (ver
> `docs/LEGAL_FRAMEWORK.md`).

Versão da minuta: 2026-10-06 · Aplica-se à versão de software 0.17.0 · Chave: `marketplace`

## 1. Objeto
1.1. Regras de uso do espaço em que **profissionais e empresas parceiras** (contadores, advogados, elaboradores de projeto,
auditores, avaliadores) publicam serviços, e organizações os encontram e os contratam.
1.2. A navegação no marketplace é **gratuita** para quem procura.

## 2. O que a Plataforma é e o que não é
2.1. A Plataforma é **espaço de anúncio e de contato**. O contrato de prestação de serviço é entre a organização
contratante e o profissional.
2.2. A Plataforma **não presta** os serviços anunciados, **não garante** resultado, **não arbitra** disputa contratual e
**não recebe** o pagamento do serviço.
2.3. **Não há comissão (take rate) ativa.** A infraestrutura de cálculo existe e está **desligada por decisão
arquitetural** (ADR-022): cobrar percentual sobre transação que a Plataforma não processa exigiria custodiar ou processar
valor, o que a Plataforma não faz. Ligar isso depende de parecer jurídico e de revisão daquela decisão.

## 3. Quem pode anunciar
3.1. Profissional com registro em conselho, quando a atividade exigir (CRC, OAB), com o número do registro declarado.
3.2. A Plataforma **confere o que é conferível automaticamente** e exibe o estado da conferência. Conferência automática
não é atestado de idoneidade nem de capacidade técnica.
3.3. Anúncio com registro vencido ou inválido é despublicado.

## 4. Conteúdo do anúncio
4.1. Preço, escopo, prazo e forma de contratação são declarados pelo anunciante, que responde por eles.
4.2. É vedado: prometer aprovação em edital; prometer benefício fiscal; usar o nome de órgão público de modo a sugerir
credenciamento; anunciar serviço que exija registro que o anunciante não tem.
4.3. A Plataforma pode despublicar anúncio que viole 4.2, pela escada de moderação documentada.

## 5. Avaliações
5.1. Avaliação só pode ser feita por quem teve relação registrada na Plataforma. Avaliação inventada é fraude.

## 6. Responsabilidade
6.1. Pela execução do serviço: do profissional.
6.2. Pela escolha do profissional: da contratante.
6.3. Da Plataforma: pelo funcionamento do espaço de anúncio, nos limites do Contrato de Assinatura.

## 7. Perguntas abertas para o jurídico
1. A Plataforma é **marketplace** ou **portal de classificados**? A resposta muda o grau de responsabilidade solidária.
2. Se o CDC incidir, qual o dever de retirada de anúncio após notificação?
3. Take rate: existe desenho em que a Plataforma cobre percentual **sem** processar o valor (cobrança do profissional pelo
   serviço de intermediação, e não sobre a transação)? É a pergunta que destrava ou enterra essa receita.
