# PUBLIC_VERIFICATION — verificação pública por terceiro

É a característica que o proprietário fez questão de ter: **qualquer pessoa autorizada pode conferir se o documento é
genuíno, qual versão foi assinada e se a integridade permanece intacta** — sem ter conta na plataforma.

## 1. Como alguém verifica
1. Lê o código no documento (`IMP-XXXX-XXXX-XXXX`) ou aponta a câmera no QR Code.
2. Abre `/verificar` e digita o código, ou vai direto em `/verificar/{codigo}`.
3. Recebe a resposta de `GET /v1/public/verify/{code}` — rota pública, com limite de 120 consultas por IP por hora.

O código é tolerante ao que a pessoa digita: aceita minúsculas, sem hífen, com espaços, e troca `I`→`1` e `O`→`0`
(confusão clássica ao copiar de papel). O alfabeto não tem `I`, `O` nem `U`, justamente para evitar ambiguidade.
O código é **aleatório**, não sequencial: ter um código não ajuda a descobrir outro.

## 2. O que a resposta diz
| Campo | Significado |
|---|---|
| `genuine` | existe registro e ele não está revogado nem expirado |
| `status` | `active` · `superseded` (existe versão mais nova) · `revoked` · `expired` |
| `signed_version` × `current_version` | **qual versão foi assinada** e qual é a versão atual na plataforma |
| `version_is_current` | se a assinatura cobre a versão que está em uso hoje |
| `integrity.intact` | o hash registrado continua sendo o hash do documento |
| `integrity.storage_verified` | o **arquivo guardado** foi relido e recontado agora, e bate com o hash |
| `content_sha256` | a impressão digital, para conferência independente (`sha256sum` no arquivo) |
| `signers[]` | papel, data, método e, em assinatura profissional, nome e registro no conselho |
| `timestamps[]` | carimbos aplicados (internos; ACT não está contratada) |
| `custody_chain` | quantos fatos a cadeia tem e se o encadeamento está íntegro |
| `revoked_at`, `revocation_reason` | quando e por quê, quando revogado |

## 3. O que a página NÃO mostra (LGPD por construção)
Nenhum conteúdo do documento. Nenhum e-mail, identificador interno, telefone, endereço ou dado de beneficiário.
Nome de pessoa aparece **apenas** em assinatura profissional com credencial verificada — porque é exatamente o que consta
do documento assinado e o registro no conselho é informação pública. Nos demais papéis, o público vê "Representante legal
— <organização>", sem nome.
Isso não é filtro de apresentação: o payload público é **montado e gravado** na criação do registro, e a consulta pública
lê só ele. Um erro futuro em consulta do domínio não consegue vazar campo novo na página.

## 4. Revogação
`POST /v1/verifiable-records/{id}/revoke` (papel `owner`, motivo obrigatório com no mínimo 10 caracteres).
A página pública passa a dizer **REVOGADO**, com data e motivo. O código continua existindo — quem recebeu o papel
antigo precisa descobrir que ele não vale mais, e para isso o código tem de continuar respondendo.
Revogar uma **assinatura** é diferente de revogar o registro: a assinatura é append-only e permanece no histórico,
marcada como revogada.

## 5. QR Code
`GET /v1/public/verify/{code}/qr` devolve SVG (cache de 1 hora). O PDF gerado pela plataforma imprime o QR e o código
em texto — papel molhado, QR rasgado e impressora ruim são a razão de imprimir os dois.
O gerador é próprio (`trust/qr.py`), porque os registros npm/PyPI estão bloqueados neste ambiente. Ele implementa
ISO/IEC 18004 para versões 1–10 no nível M: Reed-Solomon sobre GF(256), intercalação de blocos, padrões de posição,
alinhamento e temporização, informação de formato e de versão por BCH, e escolha de máscara pela menor penalidade.
**Validado por teste de ida e volta** (o teste remonta os códigos a partir da matriz e recupera o texto) e por conferência
estrutural. **Não foi lido por um leitor comercial neste ambiente** — ver `TRUST_TESTING.md`.

## 6. Contador de acesso
Cada consulta pública incrementa `access_count` e grava um fato `verified_public` na cadeia de custódia. A organização vê
quantas vezes o documento foi conferido e quando foi a última — útil para saber se o documento está circulando.
O contador é coluna guardada: a aplicação não o reescreve.

## 7. Limites
- A verificação prova **o que a plataforma registrou**. Não prova que o conteúdo do documento é verdadeiro.
- `storage_verified` só existe para documentos; rascunhos e acordos verificam o hash do conteúdo em banco.
- Não há assinatura qualificada (ICP-Brasil/gov.br). Para exigência legal de assinatura qualificada, o documento precisa
  ser assinado com certificado próprio fora da plataforma — ver `DIGITAL_SIGNATURE.md` §limites.
