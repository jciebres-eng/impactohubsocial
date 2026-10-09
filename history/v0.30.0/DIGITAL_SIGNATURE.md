# DIGITAL_SIGNATURE — assinatura eletrônica na plataforma

## 1. O que a plataforma faz: assinatura eletrônica **avançada**
Duas camadas, e as duas são obrigatórias:

| Camada | O que é | Por que existe |
|---|---|---|
| 1 — reautenticação | a senha da pessoa, pedida no ato de assinar | sessão aberta em máquina alheia não assina |
| 2 — código de uso único | 6 dígitos enviados por e-mail, válidos por 10 minutos, **amarrados ao hash exato do conteúdo** | prova posse de outro canal e mata o código se o documento mudar |

Mais o que já existia e foi preservado: hash da **versão exata** assinada, credencial profissional quando aplicável,
papel declarado, declaração escrita, IP, agente do navegador, selo HMAC do servidor e trilha de auditoria encadeada.
A v0.14.0 acrescentou `challenge_id` (qual código foi queimado) e `identity_level` (qual era o nível de identidade da
pessoa no momento da assinatura) — ambos gravados **no INSERT**, porque `signatures` é append-only desde a migração 0002.

## 2. O código morre quando o conteúdo muda
O desafio guarda `subject_sha256`. Na hora de assinar, o servidor relê o hash atual e compara. Se o documento foi
substituído entre pedir o código e assinar, a resposta é `409 challenge_content_changed` com a mensagem
"O conteúdo mudou depois que o código foi enviado. Peça um novo código e confira o documento."
Isso impede a troca do documento entre a conferência e a assinatura.

## 3. Estados e erros
| Situação | Resposta |
|---|---|
| assinar sem pedir código | `401 challenge_no_challenge` |
| código errado | `401 challenge_wrong_code` (com tentativas restantes; 5 no máximo) |
| código já usado | `409 challenge_already_used` |
| código expirado (10 min) | `409 challenge_expired` |
| conteúdo mudou | `409 challenge_content_changed` |
| senha errada | `401 reauth_failed` (a senha é conferida **antes** do código) |
| canal SMS | `501 channel_unavailable` — não há provedor de SMS |

## 4. Revogação
`POST /v1/signatures/{id}/revoke` (papel `owner`, motivo obrigatório). A assinatura **não é apagada**: entra uma linha em
`signature_revocations` (append-only), a cadeia de custódia recebe `signature_revoked` e a verificação pública passa a
marcar aquele signatário como "assinatura revogada". Revogar duas vezes devolve `409 already_revoked`.

## 5. Acordos multiassinatura
`signed_agreements` + `signed_agreement_parties`. Regras garantidas no banco e por teste:
- o acordo nasce `draft`; as partes são definidas nessa fase;
- publicar exige **pelo menos duas partes obrigatórias** (`409 parties_missing`) e congela o hash do documento
  (`content_sha256` é coluna guardada);
- cada parte assina com as mesmas duas camadas; quem não é parte **não consegue nem pedir o código** (o acordo é
  invisível para a organização dela);
- o acordo vira `active` só quando **todas** as partes obrigatórias assinaram — nunca por decisão de uma parte;
- uma parte não marca a outra como assinada (`signed_at` é coluna guardada, e a linha da outra parte é invisível para
  escrita por RLS);
- recusa de qualquer parte cancela o acordo, com motivo registrado;
- entregas (`signed_agreement_milestones`) dão o acompanhamento longitudinal do que foi combinado.

## 6. O que a plataforma **NÃO** faz
| Capacidade | Estado | Por quê |
|---|---|---|
| Assinatura **qualificada** (ICP-Brasil) | **NÃO IMPLEMENTADA** | exige certificado A1/A3 da pessoa ou da organização, biblioteca de assinatura PAdES/CAdES e homologação. É dependência externa + homologação. |
| Assinatura via **gov.br** | **NÃO IMPLEMENTADA** | exige credenciamento no gov.br. **AUTORIZAÇÃO EXTERNA NECESSÁRIA.** |
| Carimbo de tempo de **ACT** (RFC 3161) | **NÃO IMPLEMENTADO** | exige Autoridade de Carimbo de Tempo contratada. A função recusa com `501 tsa_not_configured` em vez de simular. |
| **SMS** como segunda camada | **NÃO IMPLEMENTADO** | não há provedor de SMS na plataforma. |

O enum `signatures.method` aceita `icp_brasil` e `govbr` desde a v0.7.0, mas **nenhum código produz esses valores** — era
e continua sendo um espaço reservado. Toda assinatura da plataforma é `platform_advanced`.

## 7. Base legal (não é parecer jurídico)
A MP 2.200-2/2001 reconhece assinatura eletrônica não-ICP quando as partes a admitem como válida, e a Lei 14.063/2020
classifica assinaturas em simples, avançada e qualificada. O que está implementado aqui tem as características de uma
**assinatura avançada**: identificação do signatário, controle exclusivo (senha + código), e detecção de qualquer
alteração posterior (hash + cadeia encadeada).
Para atos que a lei exige em assinatura **qualificada**, isto não serve. A resposta da API diz isso em texto, em toda
assinatura, e a página pública também. **VALIDAÇÃO JURÍDICA NECESSÁRIA** para definir, por tipo de documento, o que a
organização pode aceitar.
