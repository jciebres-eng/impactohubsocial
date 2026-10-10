# Chaves, cifragem e rotação

Código: `backend/impacto/core/keys.py`, `backend/impacto/security/crypto.py` · dados: `encryption_keys`,
`encryption_rotations` · rotas: `/v1/admin/encryption/*`.

## 1. O que está cifrado hoje

| Tabela.coluna | O que guarda | Mecanismo | Legível pela aplicação? |
|---|---|---|---|
| `users.mfa_secret_enc` | segredo TOTP do segundo fator | `FieldCipher` (Fernet/MultiFernet, AES-128-CBC + HMAC-SHA256) | sim (a aplicação precisa validar o código) |
| `integration_credentials.secret_cipher` | segredo de integração externa | `bytea` cifrado | **não** — `GRANT` por coluna, só o papel dono do banco lê |

O resto do banco **não é cifrado em coluna**. A proteção do dado em repouso é do volume/infra (fora do escopo do
código) e a proteção de acesso é RLS + `GRANT` por coluna. Dizer "o banco é criptografado" sem isso ser verdade na
coluna seria falso; o que existe está na tabela acima.

## 2. Inventário: a impressão digital, nunca a chave

`encryption_keys` guarda `purpose`, `version`, **`fingerprint` (16 hex)**, `state`, datas e nota. A chave **nunca**
é gravada no banco.

```
fingerprint = sha256("impacto-key-fingerprint-v1|" || chave)[0:16]
```

O rótulo de domínio existe para que a impressão digital não sirva de oráculo para outro sistema que use o mesmo
SHA-256 da mesma chave.

Estados: `active` (a chave corrente, uma por finalidade) · `decrypt_only` (ainda decifra dado antigo) · `retired`
(saiu da configuração; fica no inventário para explicar dado antigo).

As tabelas `encryption_keys` e `encryption_rotations` são **invisíveis para o contexto da organização** (política
`app_priv()`), conferido por teste
(`test_v0150_security.EncryptionIsolationTests.test_key_tables_are_invisible_to_the_organization_context`).

### O inventário diz a verdade sobre a chave em uso

Quando `FIELD_ENCRYPTION_KEY` não está configurada e o ambiente não está endurecido, o `FieldCipher` deriva a chave
do `SECRET_KEY`. O provedor de chave do inventário **espelha exatamente essa derivação** — porque um inventário que
mostra "nenhuma chave" enquanto existe dado cifrado é pior que inventário nenhum.

## 3. Finalidades

| `purpose` | Origem da chave | Usada em |
|---|---|---|
| `field` | `FIELD_ENCRYPTION_KEY` (ou derivada do `SECRET_KEY` em ambiente não endurecido) | `users.mfa_secret_enc` |
| `integration` | `INTEGRATION_SECRET_KEY` ou `SECRET_KEY` | `integration_credentials.secret_cipher` |
| `signature_seal` | `SECRET_KEY` | selo HMAC de assinatura e carimbo interno de tempo |

Várias chaves por finalidade, separadas por vírgula: a **primeira** é a corrente, as demais ficam `decrypt_only`.
É assim que a rotação acontece sem parada.

## 4. Como rotacionar `users.mfa_secret_enc`

1. **Gerar** a chave nova: `python3 -c "from impacto.security.crypto import generate_key; print(generate_key())"`.
2. **Configurar** `FIELD_ENCRYPTION_KEY=<nova>,<antiga>` e reiniciar a aplicação. A partir daqui, tudo que é
   gravado usa a nova e tudo que já existe continua sendo lido com a antiga.
3. **Registrar** no inventário: `POST /v1/admin/encryption/keys {"purpose": "field"}`. A nova fica `active`, a
   antiga `decrypt_only`.
4. **Recifrar**: `POST /v1/admin/encryption/reencrypt {"table": "users"}`. Lê em lotes de 500, decifra com qualquer
   chave configurada, regrava com a corrente. **É idempotente**: rodar de novo não causa dano.
5. **Conferir** a rotação em `GET /v1/admin/encryption/keys` → `rotations`: `rows_total`, `rows_reencrypted`,
   `rows_failed`, `status` (`completed` / `partial` / `failed`) e até 5 exemplos de falha.
6. **Aposentar** a antiga: remover da variável, reiniciar, registrar de novo. Ela vira `retired`.

Falha de decifragem **não interrompe** a rotação: conta, registra o identificador da linha e segue. Rotação que para
no primeiro erro deixa o banco meio rotacionado sem ninguém saber.

Rodar o passo 4 antes do 3 funciona (a recifragem não depende do inventário), mas o registro é o que deixa a
auditoria legível depois.

## 5. `integration_credentials.secret_cipher`: rotação manual, e por quê

A coluna é `bytea` e **não tem `GRANT` de leitura para `impacto_app`** (migração 0011). Isso é proposital: o segredo
de um sistema externo não precisa ser legível pelo papel que atende requisição HTTP.

A consequência é que a recifragem dessa coluna não pode ser feita pela rota de administração — ela roda no papel da
aplicação. O procedimento é operacional, com o papel dono do banco:

```sql
-- com o papel impacto_owner, dentro de uma transação, e com a chave nova JÁ configurada na aplicação:
-- 1. exportar os pares (id, secret_cipher) para um processo que tenha as duas chaves
-- 2. decifrar com a antiga, cifrar com a nova, regravar por id
-- 3. registrar a rotação:
INSERT INTO encryption_rotations(purpose, from_version, to_version, table_name, rows_total,
                                 rows_reencrypted, rows_failed, status, actor_user_id)
VALUES ('integration', <antiga>, <nova>, 'integration_credentials', <n>, <n>, 0, 'completed', NULL);
```

Alternativa operacionalmente mais simples e geralmente preferível: **revogar e recriar** a credencial no sistema
externo. Segredo de integração é descartável; chave de cifragem de campo não.

`ENCRYPTED_COLUMNS` em `core/keys.py` registra, em comentário no código, exatamente este motivo — para que a
próxima pessoa não ache que foi esquecimento.

## 6. KMS e HSM: NÃO implementados

A resposta de `GET /v1/admin/encryption/keys` traz, textualmente:

> *"Gerenciamento de chave em KMS/HSM depende de infraestrutura contratada (AWS KMS, GCP KMS, Azure Key Vault ou
> HSM). Não está implementado: o provedor em uso é o local, baseado na configuração do processo."*

A interface mostra isso como aviso na tela, não em letra miúda.

O que existe no código é o contrato: `KeyProvider` é um `Protocol` com `current(purpose)` e `all_keys(purpose)`, e
`EnvKeyProvider` é a implementação local. Um provedor de KMS entra implementando o mesmo protocolo —
**sem alterar** `register()`, `inventory()` nem `reencrypt()`.

O que **não** existe: módulo de segurança em hardware, atestação, chave que nunca sai do dispositivo. Inventar HSM
onde não há é exatamente o tipo de afirmação que destrói a credibilidade de todo o resto.

## 7. O que a plataforma garante e o que não garante

| Garante | Não garante |
|---|---|
| a chave não está no banco nem no Git | que a chave esteja fora do ambiente do processo |
| a impressão digital identifica a chave sem revelá-la | proteção contra quem já tem acesso ao ambiente |
| a rotação é idempotente e auditada | rotação automática por calendário (é operação humana) |
| o segredo de integração não é legível pelo papel da aplicação | que o sistema externo guarde bem o segredo dele |
| toda rotação fica registrada com totais e falhas | recuperação de dado cujo par de chaves foi perdido |

Perder a chave `field` sem ter o `decrypt_only` configurado significa perder os segredos de TOTP — as pessoas
precisam reconfigurar o segundo fator. Não há backdoor, e isso é a propriedade desejada.

## 8. Teste

| O que | Onde |
|---|---|
| inventário não expõe chave, impressão digital tem 16 hex | `test_v0150_core.test_inventory_never_exposes_the_key_and_declares_no_kms` |
| recifragem é auditada e idempotente | `test_reencrypt_is_auditable_and_idempotent` |
| tabela não rotacionável é recusada com a lista do que existe | `test_unknown_table_is_refused_with_the_available_list` |
| tabelas de chave invisíveis para a organização | `test_v0150_security.test_key_tables_are_invisible_to_the_organization_context` |
| coluna de segredo de integração ilegível pelo papel da aplicação | `test_integration_secret_column_is_not_readable_by_the_app_role` |
| rotas de chave exigem administração com segundo fator | `test_v0150_security.AdminSurfaceTests` |
