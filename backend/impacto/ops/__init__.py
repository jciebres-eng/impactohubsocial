"""Tarefas operacionais com registro durável: backup e canário de e-mail.

As duas existem pelo mesmo motivo. Antes da v0.19.0 a plataforma tinha um script de backup que nada
executava e um envio de e-mail que podia falhar em silêncio. Nos dois casos o problema não era a
funcionalidade — era não haver registro, e portanto não haver pergunta possível: "o backup rodou?",
"o provedor está aceitando nossas mensagens?".

Aqui cada execução grava em `ops_job_runs` com resultado, inclusive o resultado `not_configured`, que
é o mais importante dos quatro: ele diz que a tarefa NÃO rodou por falta de credencial ou destino, em
vez de deixar a ausência de linha parecer sucesso.
"""
