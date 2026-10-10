# Runbooks de incidente — Plataforma Impacto

Versão 0.35.0 (auditoria de segurança, IR-01). Linguagem simples, passos na ordem em que se faz.
**Nenhum runbook tem senha, chave ou token** — onde aparece "a chave", ela está no Railway, no GitHub, no
Cloudflare ou no gerenciador de senhas do responsável.

| Nº | Quando usar | Arquivo |
|---|---|---|
| 1 | Uma senha, chave ou token apareceu onde não devia (chat, commit, print, e-mail) | [RB-01-vazamento-de-segredo.md](RB-01-vazamento-de-segredo.md) |
| 2 | Dado pessoal pode ter sido visto, copiado ou apagado por quem não devia | [RB-02-vazamento-de-dados-pessoais.md](RB-02-vazamento-de-dados-pessoais.md) |
| 3 | Uma conta (da equipe ou de organização) parece estar nas mãos de outra pessoa | [RB-03-tomada-de-conta.md](RB-03-tomada-de-conta.md) |
| 4 | Arquivos sumiram, foram cifrados ou o bucket foi apagado (ransomware) | [RB-04-perda-de-arquivos-ransomware.md](RB-04-perda-de-arquivos-ransomware.md) |
| 5 | Pagamento, doação ou repasse com sinal de fraude ou abuso | [RB-05-abuso-de-pagamento.md](RB-05-abuso-de-pagamento.md) |
| 6 | Railway, Supabase, Cloudflare, R2 ou Brevo fora do ar — ou é preciso PARAR a plataforma | [RB-06-queda-de-provedor-e-interruptor.md](RB-06-queda-de-provedor-e-interruptor.md) |
| 7 | O banco de dados foi perdido, corrompido ou alterado por engano | [RB-07-perda-do-banco.md](RB-07-perda-do-banco.md) |

## Regras que valem para todos

1. **Primeiro conter, depois investigar.** Trocar uma chave ou parar uma rota é reversível; dado vazado não volta.
2. **Anotar tudo com hora** (horário de Brasília) num documento do incidente: o que se viu, o que se fez, quem fez.
3. **Não apagar rastro**: a trilha de auditoria (`audit_events`) e os registros do Railway são a prova. Exportar,
   nunca limpar.
4. **Alerta não é acusação.** Ninguém é chamado de fraudador por causa de um sinal; a decisão é humana, com prova.
5. **Nada de afirmar "100% seguro"** a ninguém — nem durante, nem depois.
6. Quem decide comunicar a terceiros (ANPD, titulares, financiadores, imprensa) é o responsável, com o
   encarregado de dados (DPO) e o jurídico.

## Contatos que precisam existir ANTES do incidente (preencher fora do repositório)

- Responsável pela plataforma (decide) e um substituto.
- Encarregado de dados (DPO) — LGPD.
- Jurídico.
- Suporte de cada provedor: Railway, Supabase, Cloudflare (DNS e R2), Brevo, Registro.br.
