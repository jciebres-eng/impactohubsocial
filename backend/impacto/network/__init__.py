"""IMPACT NETWORK — a camada de rede sobre o núcleo que a v0.15.0 fechou.

O núcleo (`impacto.core`) responde "o que este projeto é e o que falta nele". A rede responde "quem pode ajudar, como
a conversa começa, o que foi proposto, o que foi combinado, quem precisa saber e o que o apoio produziu".

Os motores, na ordem da cadeia que o pedido desenhou
(Pessoa/Organização → Contexto → Necessidade → Rede → Match → Proposta → Relação → Projeto → Execução → Evidência →
Resultado → Novo Match):

    relationships   relação unificada (22 tipos), com visibilidade própria e espelho da camada antiga
    messaging       conversa COM contexto — nunca chat solto em relação profissional
    proposals       proposta ≠ contrato ≠ compromisso ≠ pagamento, com máquina de estados e versão
    marketplace     publicação governada por ESTADO, não por condição de consulta
    impact_report   o ciclo que devolve resultado a quem apoiou, com números apurados pelo servidor
    readiness       seis prontidões, cada número com os critérios que o compuseram
    recommendation  próxima ação com razão e evidência — separado do motor de match
    profiles        @identificador e projeção pública curada; a página pública não lê tabela privada
    workspace       o ambiente de cada persona (não "dashboard"), um núcleo e várias experiências
    notify          fan-out para TODA a equipe, idempotente, respeitando preferência
    events          o fato gravado uma vez, na transação em que aconteceu

Dois princípios atravessam todos eles:

1. **A existência de uma relação não implica que ela seja visível.** `visibility` decide; nenhum motor autoriza por
   "existe relação".
2. **Atributo de projeto ≠ dado pessoal sensível.** "Este projeto atende mulheres em situação de vulnerabilidade" é
   atributo do projeto e vive em `territory_needs.beneficiary_groups` e nas taxonomias. "Esta pessoa pertence a
   determinado grupo vulnerável" é dado pessoal sensível, e nenhum motor daqui o infere, armazena ou usa como filtro —
   a `usage_policy` do termo `beneficiary_group` registra essa proibição no próprio banco.
"""
