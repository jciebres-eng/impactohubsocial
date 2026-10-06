"""A data e a hora da plataforma, em UTC. Uma definição, usada em todo lugar.

DEFEITO QUE ORIGINOU ESTE MÓDULO (encontrado na v0.16.0 por um teste de conteúdo regulatório que falhou de madrugada):
o produto comparava uma coluna `date` vinda do PostgreSQL — que opera em UTC (`current_date`, `now()`) — com
`date.today()`, que usa o fuso LOCAL do processo do servidor. No contêiner de desenvolvimento o fuso é UTC-4, e às
00:40 UTC `date.today()` ainda devolvia o dia anterior. Resultado: um documento regulatório vencido ontem era
considerado válido, e um certificado válido até hoje poderia ser recusado.

O erro é de um dia e aparece numa janela de poucas horas por dia — o pior tipo: não quebra em teste de meio-dia, mas
dá resposta errada em produção sempre que o servidor não estiver em UTC. E são 28 lugares que comparam data: validade
de documento, prazo de edital, vigência de termo, elegibilidade, maturidade institucional, honorário por tabela.

Daqui para frente a regra é: **data do produto é data UTC**, porque é o que o banco guarda e compara. Quem precisa
mostrar a data no fuso de quem lê faz isso na interface, não no cálculo.
"""
from __future__ import annotations

from datetime import UTC, date, datetime


def now() -> datetime:
    """Agora, com fuso. Equivale ao `now()` do PostgreSQL."""
    return datetime.now(UTC)


def today() -> date:
    """Hoje em UTC. Equivale ao `current_date` do PostgreSQL — use isto, nunca `date.today()`."""
    return datetime.now(UTC).date()
