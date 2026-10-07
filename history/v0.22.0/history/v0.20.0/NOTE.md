# Retrato dos documentos da v0.20.0

Cópia congelada em 06/10/2026, no momento do corte da **v0.21.0**. Os arquivos são exatamente como
estavam no commit da v0.20.0 — nenhum deles foi editado aqui.

## Por que este diretório existe

A regra do projeto é não sobrescrever documento em silêncio. Quando a versão sobe, os documentos
mudam; sem este retrato, a frase que a v0.20.0 afirmava desapareceria junto com a mudança, e
ninguém conseguiria mais responder "o que a plataforma declarava quando foi entregue ao Designer?".

## O que mudou da v0.20.0 para a v0.21.0

A v0.20.0 entregou a engenharia com uma lacuna declarada: **nenhum preço estava definido**. Os
documentos deste diretório afirmam isso, e estavam certos quando foram escritos. A v0.21.0 publicou
a Pricing Version 2027.01 por decisão do proprietário, registrada em `PRICING_BIBLE.md`.

Dois documentos desta pasta ficaram desatualizados por essa razão, e não por erro:

* `BILLING_V2.md` — descrevia a regra em dólar da v0.16.0, já aposentada na v0.17.0; a versão atual
  no repositório ganhou um aviso no topo apontando para a regra vigente;
* qualquer trecho que diga "nenhum preço institucional foi fixado" — verdadeiro até 06/10/2026.

Os testes que afirmavam aquela realidade foram **reescritos**, não removidos: eles passaram a
afirmar a invariante que permanece em qualquer versão de preço — que todo valor declarado nomeie a
decisão que o criou, e que um plano sem preço anual publicado não ganhe economia anual inventada.
