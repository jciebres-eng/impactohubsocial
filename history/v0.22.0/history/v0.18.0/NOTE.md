# Snapshot da v0.18.0 (impacto contextualizado, equidade e confiança)

Documentos como estavam ao fim da v0.18.0, antes do endurecimento final da v0.18.1.

**Por que a v0.18.1 existe:** o proprietário recebeu um pacote `IMPACTO_v0.18.0_CORE_HARDENED.zip`
produzido fora desta sessão, com quatro reforços de núcleo (sinal contextual no match, oito
prontidões no diagnóstico, proveniência por campo na montagem de documento, série longitudinal) que
**não puderam ser executados contra PostgreSQL real** no ambiente onde foram escritos — o próprio
relatório daquele pacote declara isso e conclui GO WITH CONDITIONS.

A v0.18.1 integrou aqueles reforços, rodou-os contra o banco real, e encontrou quatro defeitos que
só aparecem com banco e com terceiro na frente: o sinal contextual estava morto para todo
financiador (RLS), a "referência neutra" de 0,5 premiava quem não declarava contexto, prazo sem fuso
devolvia 500, e a regra de linguagem absoluta deixava "erradicamos" passar. Os quatro estão
corrigidos e cobertos por teste na v0.18.1.

Nada aqui foi sobrescrito: os arquivos desta pasta são o estado da v0.18.0.
