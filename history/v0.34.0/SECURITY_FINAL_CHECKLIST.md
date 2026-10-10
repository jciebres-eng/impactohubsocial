# Lista final de segurança — v0.15.0

Cada linha tem a prova ao lado. Onde não há prova, está escrito "não verificado" — e isso vale como pendência, não
como aprovação.

## 1. Autenticação

| Item | Situação | Prova |
|---|---|---|
| Senha com `scrypt` (N configurável, 2^17 em produção) | ✅ | `security/passwords.py` · `test_api_auth` |
| Segundo fator TOTP com segredo cifrado e códigos de recuperação | ✅ | `security/totp.py` · `test_api_auth` |
| Administração **exige** segundo fator verificado na sessão | ✅ | `test_security_tenancy.test_admin_without_mfa_is_blocked` · `test_v0150_security.test_admin_without_mfa_cannot_touch_keys` |
| Sessão com refresh rotativo e revogação | ✅ | `test_api_auth.test_session_revocation` |
| Cookies `__Host-`/`__Secure-` com `SameSite` e CSRF por token | ✅ | `http.cookie_names` · `test_api_auth` |
| Token de portador (Bearer) para aplicativo, com modo explícito | ✅ | `X-Auth-Mode: token` |
| Confirmação de e-mail obrigatória para publicar, candidatar e convidar | ✅ | `test_api_features` |
| Reautenticação por senha para eliminar a conta | ✅ | `privacy_routes.delete_account` |
| OIDC com `state`/`nonce` e expiração | ✅ | `test_oidc.py` |
| Rotas públicas são uma lista **fechada**, conferida por teste | ✅ | `test_architecture.test_handlers_declare_auth` |

## 2. Autorização

| Item | Situação | Prova |
|---|---|---|
| Papel mínimo por rota (`viewer` < `member` < `analyst` < `manager` < `admin` < `owner`) | ✅ | `http.RouteSpec.min_role` · `test_role_and_kind_enforcement` |
| Tipo de organização por rota (`kinds`) | ✅ | idem |
| Papéis internos (editor/revisor/suporte) separados de administração de plataforma | ✅ | `staff` em `RouteSpec` |
| Separação de funções: quem valida indicador ≠ quem informou | ✅ | `CHECK` no banco |
| Separação de funções: quem aprova montagem ≠ quem montou | ✅ | `CHECK` + 409 `four_eyes` · `test_four_eyes_the_author_cannot_approve_their_own_assembly` |
| Regra fiscal exige duas aprovações distintas | ✅ | `CHECK` em `fiscal_rules` |
| Organização não valida o próprio documento institucional | ✅ | `test_v0100_institutional` |

## 3. Isolamento entre organizações (a matriz A → recurso de B)

### Varredura automática

`test_v0150_security.WriteRouteSweep` percorre **todas** as rotas de escrita com identificador no caminho
(POST/PUT/PATCH/DELETE, autenticadas) e chama cada uma com um identificador que não existe para ninguém. **Nenhuma
pode responder 2xx nem 5xx.**

Isso pega rota nova que esqueça de conferir a dona do recurso — inclusive rota acrescentada depois desta versão.
Um segundo teste confere que as 14 rotas novas da v0.15.0 estão dentro da varredura, para que ninguém a esvazie sem
perceber.

**Cinco exceções, nomeadas e justificadas:** `DELETE` idempotente da própria relação (desfavoritar, deixar de
seguir, desbloquear, remover solução salva, desfazer intenção). Apagar "o que eu marquei" quando nada está marcado
responde com sucesso, e isso não vaza nada: um teste dedicado
(`IdempotentDeleteTests`) confere que a resposta é **indistinguível** entre identificador existente e inexistente.

### Matriz explícita

`test_v0150_security.CrossTenantMatrix` usa identificadores **reais** da organização B e confere, com a organização
A:

| Recurso de B | Leitura | Escrita |
|---|---|---|
| ideia | 404 | 404 (editar, promover) |
| ciclo de vida, linha de tempo, integridade, estado | 404 | 404 (transição) |
| retratos | 404 | 404 (criar, comparar) |
| riscos | 404 | 404 (criar, atualizar, varrer) |
| diagnóstico: análise, versões, versão N, ações | 404 | 404 (publicar versão, criar/atualizar ação) |
| montagem de documento | 404 | 404 (editar, gerar, revisar) |
| modelo de documento da organização B | — | 404 (acrescentar campo, publicar) |
| avaliação de match de B | — | 404 (dar retorno) |

Mais: montagem **não pode apontar** para projeto de outra organização (404), e evidência de montagem **tem que ser**
documento da mesma organização (404).

### No banco, sem passar pela API

`test_rls_blocks_the_new_tables_directly_in_sql` abre uma transação no contexto da organização A e confere, em
`ideas`, `project_risks`, `project_snapshots`, `diagnosis_versions`, `diagnosis_actions` e `document_assemblies`:
linha de B invisível, contagem por `org_id` de B igual a zero, `UPDATE` em linha de B afeta zero linhas.

`test_security_definer_helpers_do_not_leak_other_tenant` confere que as funções `SECURITY DEFINER` — o caminho
clássico de fuga da RLS — não entregam dado de outra organização.

## 4. Segredos e cifragem

| Item | Situação | Prova |
|---|---|---|
| Nenhum segredo no repositório | ✅ | `test_architecture.test_no_secrets_committed` (6 padrões) |
| Nenhum segredo no ZIP de entrega | ✅ | `scripts/make_release.py` varre os mesmos padrões e **falha** |
| Chave **nunca** gravada no banco; só impressão digital de 16 hex | ✅ | `test_inventory_never_exposes_the_key_and_declares_no_kms` |
| Rotação idempotente e auditada | ✅ | `test_reencrypt_is_auditable_and_idempotent` |
| Tabelas de chave invisíveis para a organização | ✅ | `test_key_tables_are_invisible_to_the_organization_context` |
| Segredo de integração ilegível pelo papel da aplicação (`GRANT` por coluna) | ✅ | `test_integration_secret_column_is_not_readable_by_the_app_role` |
| KMS/HSM | ❌ **não implementado**, declarado na API e na interface | `KEY_ROTATION.md` §6 |

## 5. Entrada e saída

| Item | Situação | Prova |
|---|---|---|
| Toda entrada validada por modelo que **recusa campo desconhecido** | ✅ | `In(extra="forbid")` em todos os esquemas |
| Consulta sempre parametrizada (`$1`), nunca concatenada | ✅ | revisão + `test_injection_payloads_are_stored_literally` |
| Identificador no caminho validado antes de ir ao banco | ✅ | `test_object_ids_are_validated` |
| Paginação com limite máximo (100) | ✅ | `S.Pagination` |
| Erro no padrão RFC 7807 **sem** vazar interno do PostgreSQL | ✅ | `_PG_INTERNAL` sanitiza · `test_v0120_hardening` |
| Erro 500 traz `error_id` para correlação, sem rastreamento de pilha | ✅ | `http.py` |
| Controle de taxa por IP nas rotas sensíveis | ✅ | `rate=(bucket, limite, janela)` |
| `derived_from` de modelo de documento é lista **fechada** | ✅ | `test_derived_field_path_is_a_closed_list` (tenta `users.password_hash`) |

## 6. Upload de arquivo

| Item | Situação | Prova |
|---|---|---|
| Tipo verificado pelo conteúdo, não pela extensão | ✅ | `test_executable_disguised_as_pdf` |
| Extensão fora da lista recusada | ✅ | `test_disallowed_extension` |
| PDF com JavaScript recusado | ✅ | `test_pdf_with_javascript_rejected` |
| DOCX com macro recusado | ✅ | `test_docx_with_macro_rejected` |
| Tamanho máximo | ✅ | `test_oversize_rejected` |
| Travessia de caminho no nome neutralizada | ✅ | `test_filename_traversal_is_neutralized` |
| Download por token assinado, de curta duração | ✅ | `test_download_token_is_short_lived_and_tamper_proof` |
| Arquivo servido com `Content-Security-Policy: sandbox; default-src 'none'` e `nosniff` | ✅ | `document_routes.py` |
| Identidade do arquivo (hash, tamanho, tipo, chave) imutável | ✅ | `document_identity_guard` · `test_generated_document_hash_does_not_change` |
| Antivírus | ⚠️ opcional; sem ele o documento fica `pending_scan` e não é promovido | `EXTERNAL_DEPENDENCIES.md` §2 |

## 7. Cabeçalhos e navegador

| Cabeçalho | Valor |
|---|---|
| `content-security-policy` | `default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; manifest-src 'self'; worker-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'` |
| `x-frame-options` | `DENY` |
| `x-content-type-options` | `nosniff` |
| `referrer-policy` | `strict-origin-when-cross-origin` |
| `permissions-policy` | `camera=(self), microphone=(), geolocation=(), payment=()` |
| `cross-origin-opener-policy` | `same-origin` |
| `strict-transport-security` | `max-age=63072000; includeSubDomains; preload` — **só em ambiente endurecido** |

Conferido por teste de navegador real (`test_e2e_web.test_security_headers_on_spa`), que também falha se houver
**qualquer violação de CSP** no console. Não há script embutido, não há mapa-base externo, não há CDN.

## 8. Integridade e não repúdio

| Item | Situação |
|---|---|
| 17 tabelas append-only por gatilho | ✅ |
| Encadeamento por hash em trilha, auditoria e confiança, com função de verificação | ✅ |
| Adulteração exige o papel dono do banco, e a verificação denuncia | ✅ `test_ledger_tampering_is_detected` |
| 5 guardas que nem o contexto privilegiado atravessa | ✅ `DATABASE_INTEGRITY_REPORT.md` §3 |
| Assinatura com duas camadas, código preso ao hash do conteúdo | ✅ `test_code_dies_when_content_changes` |
| Provedor de assinatura fora de produção recusado **no banco** | ✅ `test_signature_with_unavailable_provider_is_refused_by_the_database` |

## 9. Pendências de segurança — honestas

| Item | Situação |
|---|---|
| **Teste de intrusão por terceiro** | ❌ **não realizado.** Tudo acima é teste automatizado escrito por quem fez o código. |
| **Revisão de segurança independente** | ❌ não realizada |
| **Programa de recompensa por vulnerabilidade** | ❌ não existe |
| **KMS/HSM** | ❌ não implementado (declarado) |
| **Antivírus em produção** | ⚠️ opcional; sem ele, documento fica `pending_scan` |
| **Carga concorrente e negação de serviço** | ❌ não medido em ambiente dimensionado |
| **Remoção física do arquivo no armazenamento ao excluir documento** | ⚠️ exclusão é lógica; remoção do objeto é operação de infraestrutura, não automatizada |
| **Rotação automática de chave por calendário** | ⚠️ a rotação é operação humana, com procedimento em `KEY_ROTATION.md` |
| **Segredo em cofre externo** (Vault, Secrets Manager) | ❌ hoje vem da configuração do processo |

Essas nove linhas são o que separa "passou nos nossos testes" de "foi auditado por fora". A primeira delas é a mais
importante: **nenhum teste de intrusão independente foi feito**, e nada neste repositório deve ser lido como se
tivesse sido.

## 10. Resumo

| Camada | Situação |
|---|---|
| Autenticação | 🟢 |
| Autorização e papéis | 🟢 |
| Isolamento entre organizações | 🟢 (varredura automática + matriz explícita + SQL direto) |
| Entrada, saída e erro | 🟢 |
| Upload de arquivo | 🟢 (antivírus opcional: 🟡) |
| Cabeçalhos e navegador | 🟢 |
| Integridade e não repúdio | 🟢 |
| Segredos e cifragem | 🟡 (funciona; KMS/HSM ausente e declarado) |
| Validação externa | 🔴 **nenhuma** |
