# RB-06 — Queda de provedor e interruptor de emergência

## Interruptor de emergência

Tela `/admin/interruptor` (permissão `security.kill_switch`, com confirmação de identidade). Para a plataforma
inteira ou só uma área (por exemplo: envio de documentos, doações, IA). As rotas de auditoria e do próprio
interruptor continuam funcionando. Todo acionamento e liberação fica na trilha (`security.kill_switch_engaged` /
`released`) e dispara o alerta `InterruptorDeEmergenciaAcionado`.

**Quando acionar:** vazamento em andamento, falha que grava dado errado, ataque em curso, provedor devolvendo dado
inconsistente. **Liberar** só depois de entender a causa — e anotar.

## Queda de provedor

| Provedor | O que para | Onde ver o estado | O que fazer |
|---|---|---|---|
| Railway | site e API (`impactohubsocial`), rotinas (`pleasing-trust`), antivírus (`clamav`) | status.railway.com; painel do projeto | aguardar; não fazer deploy durante a queda; conferir depois com o workflow `pos-deploy` |
| Supabase | banco — o site responde 503 em `/readyz` | status.supabase.com | aguardar; se houver perda de dados → [RB-07](RB-07-perda-do-banco.md) |
| Cloudflare (DNS) | o domínio não resolve | cloudflarestatus.com | aguardar; não mexer no DNS no meio da queda |
| Cloudflare R2 | envio e download de documentos | cloudflarestatus.com | interruptor para documentos, se as falhas confundirem as pessoas |
| Brevo (e-mail) | e-mails de cadastro, redefinição, avisos de segurança | status.brevo.com | os e-mails falhos ficam no log (`mail_failed`); avisar que podem atrasar |
| ClamAV (serviço `clamav`) | varredura de arquivos | painel do Railway | arquivos novos ficam em **quarentena** (download bloqueado) até o antivírus voltar — a rotina `pending_scans` tenta de novo sozinha (v0.35.0) |

## Monitor

O monitor externo (UptimeRobot/Better Stack) é o principal; o workflow `monitor` (de hora em hora) é reserva.
Se ninguém foi avisado da queda, revise os contatos do monitor externo.
