# RB-03 — Tomada de conta (conta da equipe ou de organização nas mãos de outra pessoa)

**Sinais:** alerta `ReusoDeTokenDeRenovacao` (a plataforma já revogou a família de sessões sozinha);
`PicoDeLoginFalho`; `MfaDesligadoEmSerie`; `PapelInternoConcedido` sem pedido; a pessoa diz que não fez uma ação;
e-mail de "aviso de segurança" (troca de senha, MFA) que a pessoa não reconhece; chave PIX de repasse
informada/alterada sem a organização saber (todas as partes recebem aviso).

## Reuso de token de renovação

A plataforma revoga **automaticamente** toda a família de sessões quando um token de renovação já usado volta.
O alerta existe para a investigação começar: veja na trilha (`auth.refresh_reuse_detected`) de qual conta e de
qual IP; siga os passos abaixo para essa conta.

## Conter

1. **Desative a conta** (equipe: `/admin/usuarios` → desativar — revoga as sessões) ou peça à pessoa
   "Sair de todos os dispositivos" (`POST /v1/auth/logout-all`) e "Esqueci minha senha".
2. Se for **pessoa da equipe**: retire os papéis internos dela até o fim da apuração; o MFA da equipe não pode
   ser desligado pela própria pessoa (v0.35.0) — confira na trilha se houve tentativa (`auth.mfa_failed`,
   `auth.step_up_failed`).
3. Se for **dona de organização** e houver **repasse em aberto**: avise quem paga para **não transferir** até
   confirmar a chave PIX por telefone com a organização. Depois da primeira assinatura a chave não muda (v0.35.0);
   uma chave informada depois de assinatura fica 24 h em carência. O sinal `payout_destination_changed_recently`
   aparece em `/admin/risco`.

## Investigar

- Trilha de auditoria da conta (`/admin/rastro`): logins, IPs, ações, trocas de senha e de MFA.
- O que a conta fez enquanto estava tomada: documentos baixados, dados exportados, acordos, chaves PIX.
- Se houve acesso a dado pessoal de terceiros → [RB-02](RB-02-vazamento-de-dados-pessoais.md).

## Devolver a conta

A pessoa redefine a senha pelo e-mail, liga o MFA de novo (a equipe precisa também do código enviado ao e-mail)
e confere as sessões ativas. Administração reativa a conta e devolve os papéis.
