# Release notes — v0.7.0

**Resumo:** a Plataforma Impacto passa de uma referência local (v0.6.0) a uma aplicação executável sobre PostgreSQL com isolamento por RLS,
autenticação de produção e o fluxo completo **OSC → edital/fundo → candidatura assistida → documentos e projeto com IA + validação profissional → aporte → execução → prestação de contas → empresa/governo**.

## Para a OSC
Banco de editais/fundos/chamamentos (federal, estadual, municipal, internacional e privados) · compatibilidade explicada (requisitos, pré-requisitos, o que falta, riscos) · candidatura passo a passo com acompanhamento ·
projeto estruturado a partir de texto livre · rascunhos assistidos revisados e assinados por profissional · cofre de documentos com vencimento · evidências e despesas por etapa · devolutivas.
Planos pagos: buscas salvas, rastreio e alertas (preço a definir pelo proprietário).

## Para a empresa
Feed de projetos com compatibilidade e bloqueios explicados · comparação · interesse/diligência · declaração de conflito · aportes e carteira · revisão de evidências/despesas · relatórios e CSV · estimativas fiscais **informativas** (somente com regras aprovadas).

## Para o governo
Publicação de editais e materiais; estatísticas territoriais agregadas (k-anonimato).

## Para a administração
Compliance/KYB, credenciais, editais e fontes, regras fiscais e vouchers com dupla aprovação, cobrança manual, denúncias, auditoria verificável, flags.

## Não incluído (ver auditoria §3)
Rede social/mensagens, Impact Graph, cotações de compras, antifraude, mapas, push, gráficos avançados, intermediação de pagamentos.

## Status de publicação
Web/PWA: pronto e construído, **não publicado**. Android/iOS: código pronto, **não construídos**. Nenhuma conta, loja, domínio ou provedor externo foi configurado.

## Atualização desde v0.6.0
Não há migração de dados (v0.6.0 usava SQLite de demonstração). Instale do zero conforme `ENVIRONMENT_SETUP.md` e `docs/DEPLOYMENT.md`.
