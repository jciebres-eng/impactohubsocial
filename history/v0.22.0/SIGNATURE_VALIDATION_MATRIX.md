# Matriz de validade da assinatura

Quem assina na IMPACTO precisa saber **o que a assinatura dele vale** diante de um terceiro. Este documento diz
isso sem eufemismo.

## 1. Os dois eixos que costumam ser confundidos

| Eixo | Pergunta | Valores |
|---|---|---|
| **Nível jurídico** | que presunção a lei dá a isso? | `simple` · `advanced` · `qualified` (Lei 14.063/2020) |
| **Nível criptográfico** | o que tecnicamente foi feito? | `server_hmac` · `asymmetric_pkcs7` · `asymmetric_pades` · `none` |

Misturar os dois é o erro clássico: "assinatura digital" vira guarda-chuva para coisas com valor jurídico muito
diferente. Na plataforma eles são **colunas separadas** em `signature_providers`, e nenhuma delas pode ser escrita
pelo papel da aplicação (`GRANT` por coluna — testado em
`test_app_role_cannot_change_the_legal_level_of_a_provider`).

## 2. A matriz

| Provedor | Jurídico | Criptográfico | Identificação exigida | Carimbo de tempo | Consulta de revogação | Certificado | Estado REAL |
|---|---|---|---|---|---|---|---|
| `platform_advanced` | **avançada** | **selo HMAC do servidor** | e-mail confirmado | interno (HMAC) | sim (registro na plataforma) | não | **produção** |
| `govbr` | **avançada** | PKCS#7 assimétrica | documento conferido | sim | não | sim | **indisponível** |
| `icp_brasil` | **qualificada** | PAdES assimétrica | documento conferido | sim | sim | sim | **indisponível** |

### O que cada estado significa

- **produção**: funciona agora, nesta instalação.
- **indisponível**: **depende de contratação/credenciamento que não foi feito.** Não há código esperando uma
  variável de ambiente; não há caminho que produza assinatura com este provedor.

## 3. O que a assinatura da plataforma É

`platform_advanced`, hoje em produção:

- **Duas camadas**: a senha de quem assina **e** um código de uso único enviado por e-mail, que é **preso ao hash do
  conteúdo**. Se o documento mudar entre pedir o código e assinar, o código morre (409
  `challenge_content_changed`).
- **Selo HMAC do servidor** sobre o hash do conteúdo + identificador do signatário + declaração + momento. Isso
  prova que *este servidor* registrou aquele ato, com aquele conteúdo, naquele instante.
- **Append-only**: `signatures` não aceita UPDATE nem DELETE. Revogação é **fato novo** em
  `signature_revocations`.
- **Declaração registrada**: o texto que a pessoa escreveu ao assinar fica junto e aparece na verificação pública.
- **Nível de identificação gravado na assinatura**: `identity_level` (de `none` a `biometric`) é escrito no INSERT,
  não depois. Uma assinatura feita com e-mail confirmado não "melhora" porque a pessoa verificou documento depois.
- **Versão assinada ≠ versão atual**: a verificação pública diz `signed_version` e `current_version`. Documento com
  versão nova aparece como `superseded`, e a assinatura antiga continua verificável.

## 4. O que ela NÃO é

**Não é assinatura com certificado ICP-Brasil.** Não há par de chaves do signatário, não há certificado, não há
cadeia de confiança de Autoridade Certificadora, não há PAdES nem CAdES. Um selo HMAC do servidor é prova de
**registro pela plataforma**, não prova criptográfica de autoria pelo titular de um certificado.

Consequência prática: para ato que exija assinatura **qualificada** por lei ou por edital, a assinatura da
plataforma **não serve**. A política de assinatura da organização permite exigir nível mínimo por tipo de documento
— e exigir `qualified` hoje é recusado com 409 `level_unavailable`, porque nenhum provedor em produção entrega esse
nível e a exigência bloquearia toda assinatura daquele tipo.

## 5. Como a plataforma impede a mentira estruturalmente

Não é disciplina de quem escreve código. É gatilho no banco:

```sql
-- signature_provider_guard(), migração 0013
IF (SELECT state FROM signature_providers WHERE key = NEW.provider_key) <> 'production' THEN
  RAISE EXCEPTION '... provedor ... não está em produção ...';
END IF;
```

Qualquer INSERT em `signatures` com `provider_key = 'icp_brasil'` **falha**, venha de onde vier: rota, job, script,
SQL direto no papel da aplicação. Testado em
`test_v0150_core.test_signature_with_unavailable_provider_is_refused_by_the_database`.

E promover `icp_brasil` a produção pela rota de administração também é recusado enquanto o nível criptográfico não
for assimétrico real (409 `cannot_promote`): *"Marcar como produção sem isso seria declarar validade que a
plataforma não entrega."*

Não existe, e não pode passar a existir por descuido, uma "assinatura ICP-Brasil simulada".

## 6. O que falta para cada nível ficar disponível

### `govbr` — assinatura avançada via Gov.br

1. Credenciamento no gov.br (Conecta/Assinatura Eletrônica) com `client_id` e escopo aprovados.
2. Implementar o fluxo OIDC do provedor + chamada de assinatura.
3. Receber e guardar o PKCS#7 devolvido, junto do hash do conteúdo.
4. Mudar o estado para `homologation`, rodar a homologação (`HOMOLOGATION_MATRIX.md`), depois `production`.

**Atenção ao nome:** Gov.br é assinatura **avançada**, não qualificada. Chamar o Gov.br de ICP-Brasil é erro comum e
é uma das invariantes de design que a interface não pode violar (`DESIGN_HANDOFF.md` §4).

### `icp_brasil` — assinatura qualificada

1. Certificado A1 (arquivo) ou A3 (token/cartão) emitido por AC credenciada na ICP-Brasil.
2. Biblioteca de assinatura PAdES/CAdES e política de assinatura escolhida.
3. Serviço de carimbo de tempo (ACT) — hoje `POST /v1/trust/timestamps` com RFC 3161 responde **501
   `tsa_not_configured`**, com a dependência nomeada.
4. Consulta de revogação (LCR/OCSP).
5. Homologação e só então `production`.

Nenhum desses passos é código que já está escrito esperando configuração. São **implementações a fazer**.

## 7. Outras dependências de confiança, no mesmo padrão

| Recurso | Estado | Resposta hoje |
|---|---|---|
| Carimbo de tempo RFC 3161 (ACT) | não contratado | 501 `tsa_not_configured` |
| Verificação biométrica de identidade | não contratado | 501 `provider_not_configured` |
| Confirmação de telefone por SMS | não contratado | 501 `channel_unavailable` |
| Carimbo de tempo interno (HMAC do servidor) | **funciona** | registrado com a assinatura |

**Biometria de dispositivo ≠ biometria de identificação.** Desbloquear o aplicativo com digital é conveniência do
aparelho e não eleva o nível de identificação da pessoa na plataforma; verificação biométrica de identidade exige
provedor contratado. A distinção está em `TRUST_IDENTITY.md` e repetida em `MOBILE.md`.

## 8. Política de assinatura da organização

`signature_policies` define, por tipo de documento: nível jurídico mínimo, nível de identificação mínimo e se exige
carimbo de tempo. Política da organização prevalece sobre a padrão da plataforma para o mesmo tipo.

A plataforma **recusa** política que exija nível que nenhum provedor em produção entrega — em vez de aceitar a
configuração e depois falhar em toda tentativa de assinar, sem explicação.

## 9. Verificação por terceiro

`GET /v1/public/verify/{code}`, sem login. Devolve apenas os campos curados em `verifiable_records.public_fields`:
quem assinou (nome e papel), a declaração, a versão assinada, a versão atual, o hash, o estado (`active`,
`revoked`, `superseded`) e o motivo da revogação quando houver.

Não devolve: conteúdo do documento, e-mail, chave de armazenamento, dado de outra organização. Conferido em teste
(`test_e2e_v0150_journeys.J1` verifica que a resposta pública não contém `storage_key` nem o e-mail de quem
assinou).
