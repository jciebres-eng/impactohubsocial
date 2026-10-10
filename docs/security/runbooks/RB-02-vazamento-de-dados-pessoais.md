# RB-02 — Vazamento de dados pessoais (incidente de segurança com dado pessoal)

**Sinais:** alguém viu dado de outra organização; exportação baixada por quem não devia; banco ou backup acessado
por terceiro; documento de identidade aberto por quem não tinha direito; aviso de um titular.

## Conter

1. Feche a porta: se é uma rota ou tela, use o interruptor de emergência para a área
   ([RB-06](RB-06-queda-de-provedor-e-interruptor.md)); se é um segredo, [RB-01](RB-01-vazamento-de-segredo.md);
   se é uma conta, [RB-03](RB-03-tomada-de-conta.md).
2. **Preserve a prova**: exporte a trilha de auditoria do período (tela `/admin/rastro` ou `POST /v1/admin/audit/export`, permissão `security.audit.export`)
   e salve os registros do Railway do período. Não apague nada.

## Avaliar (com o encarregado de dados — DPO)

- Quais dados, de quantas pessoas, de que tipo (dado sensível? documento de identidade? dado de criança?).
- Quem teve acesso, por quanto tempo, se houve cópia.
- Risco ou dano relevante aos titulares?

## Comunicar

- A LGPD (art. 48) exige comunicar à **ANPD** e aos **titulares** o incidente que possa causar risco ou dano
  relevante. O regulamento da ANPD (Resolução CD/ANPD nº 15/2024) fixa prazo curto, contado em dias úteis —
  **o prazo e o conteúdo exatos são conferidos pelo DPO/jurídico no momento do incidente**; este runbook não
  substitui essa orientação.
- Quem comunica é o responsável, com o DPO. A mensagem diz o que aconteceu, que dados, o que foi feito e o que a
  pessoa pode fazer. Sem minimizar e sem exagerar.

## Corrigir e provar

- Corrija a falha **com teste que falha antes e passa depois** (o mesmo método da auditoria v0.35.0).
- Registre o incidente: datas, decisão de comunicar ou não (e por quê), correção, teste.
