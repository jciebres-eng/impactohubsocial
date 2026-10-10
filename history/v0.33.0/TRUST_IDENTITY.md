# TRUST_IDENTITY — identificação de pessoas e credenciais profissionais

## 1. Níveis de identidade
`none` → `email` → `phone` → `document` → `professional` → `biometric`.
O nível corrente é derivado no banco por `identity_level(user_id)` (função SECURITY DEFINER): o maior nível
**verificado e não expirado**. Nada é autodeclarado: `identity_verifications.status` é coluna guardada, então nem a
própria pessoa muda o próprio estado pelo papel da aplicação.

| Nível | Como se obtém | Estado |
|---|---|---|
| `email` | confirmação de e-mail no cadastro (já existia) | **IMPLEMENTADO** |
| `phone` | SMS | **NÃO IMPLEMENTADO** — sem provedor; a API recusa com `501 provider_not_configured` |
| `document` | a pessoa envia documento ao cofre, anexa ao pedido, e **alguém da equipe confere** | **IMPLEMENTADO** |
| `professional` | credencial de conselho conferida (concedido automaticamente quando a credencial é aprovada) | **IMPLEMENTADO** |
| `biometric` | provedor externo de biometria/prova de vida | **NÃO IMPLEMENTADO** — exige provedor contratado; a API recusa |

## 2. Minimização: o que é guardado e o que não é
Guardado: a **referência** ao documento no cofre, o tipo declarado, o resultado da conferência e a justificativa de quem
decidiu.
**Nunca guardado**: número do documento, imagem extraída, vetor biométrico, resultado de consulta a base oficial.
`identity_verifications.evidence` existe para sustentar a decisão e é preenchido pelo servidor — não é campo livre do
cliente para colar dado sensível.

## 3. Fluxo
```
POST /v1/trust/identity/verifications          → pedido nasce 'pending' (forçado por gatilho)
POST /v1/documents                             → arquivo entra no cofre (antivírus, magic bytes, zip bomb)
POST .../verifications/{id}/documents          → anexa; o pedido passa a 'under_review' (passo privilegiado)
GET  /v1/admin/trust/identity/queue            → fila da equipe
POST /v1/admin/trust/identity/{id}/decide      → decisão HUMANA com justificativa ≥ 5 caracteres
                                                 → cadeia de custódia recebe 'identity_decided'
```
Documento com `pending_scan` é aceito **quando a instalação não tem antivírus configurado** (mesma regra do download,
`usable_statuses()`); `infected`/`rejected` nunca entram.

## 4. Credencial profissional
Catálogo de **20 conselhos** federais (CRP, CRM, CRO, CRF, CRN, COREN, CREFITO, CRFA, CRESS, CRC, OAB, CREA, CAU, CRMV,
CRA, CORECON, CREF, CRB, CRBM, CRBIO).

Duas decisões de honestidade:
1. **`number_pattern` e `official_site` nascem NULOS de propósito.** O formato do registro varia por conselho, UF e época;
   inventar uma expressão regular recusaria profissionais legítimos. Sem padrão configurado, vale só a sanidade genérica.
   A administração preenche com fonte. (O gatilho `credential_format_guard` aplica o padrão **quando** existir, e exige UF
   quando o conselho exige.)
2. **"Verificada" significa "documento conferido pela equipe"**, nunca "confirmado junto ao conselho". A plataforma não
   consulta conselho on-line — nenhum deles expõe API pública contratada. A API repete essa frase na resposta
   (`meaning`) e a interface mostra o mesmo texto.

Fluxo: a organização cadastra a credencial (nasce `self_declared`, forçado por gatilho desde a 0002) → anexa o documento
do conselho (`document_submitted`, passo privilegiado) → a equipe confere (`verified`/`rejected`) → aprovação eleva a
identidade da pessoa para `professional`. Todo passo entra em `credential_verifications`, que é **append-only**.
Revogação (`POST /v1/admin/trust/credentials/{id}/revoke`) exige motivo e entra no histórico e na custódia.

## 5. Para que serve o nível
- `signatures.identity_level` guarda o nível no momento da assinatura — quem recebe o documento anos depois sabe com que
  força a pessoa estava identificada **naquele dia**, mesmo que o nível mude depois.
- A verificação pública mostra nome e registro do conselho **só** em assinatura profissional com credencial verificada.

## 6. Limites declarados
Sem biometria própria e sem prova de vida (e **nenhum** dado biométrico armazenado) · sem SMS · sem consulta a base
oficial de documento (Receita, Denatran, cartório) · sem consulta on-line a conselho · a conferência é documental e
humana, então está sujeita a erro humano — por isso cada decisão exige justificativa e fica na cadeia de custódia.
