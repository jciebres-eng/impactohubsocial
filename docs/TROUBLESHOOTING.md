# Quando dá errado

Falhas que realmente acontecem nesta plataforma, com a mensagem exata, a causa e o que fazer. Está em
ordem de quando aparecem: primeiro as que impedem subir, depois as que aparecem usando.

Procure pela **mensagem** ou pelo **código** — eles são o índice deste documento.

---

## A. Não sobe

### `Configuração inválida: - DATABASE_URL é obrigatório`

Falta a variável. É a única exigida em todo ambiente.

### `Configuração inválida: - SECRET_KEY ausente, curto (<32) ou com valor de exemplo`

Em `staging` e `production` a aplicação **recusa iniciar** com segredo ausente, curto ou de exemplo.
Vale para `SECRET_KEY`, `VOUCHER_HMAC_KEY` e `FIELD_ENCRYPTION_KEY`. Gere os três:

```bash
python3 -m impacto.cli gen-secrets
```

Não contorne isso. A recusa existe porque chave de exemplo em ambiente que parece oficial é a falha
que ninguém descobre até o dia ruim.

### `MAIL_PROVIDER=console não é permitido em staging/production (use smtp)`

Sem envio de e-mail a aplicação não sobe fora de desenvolvimento: confirmação de cadastro,
recuperação de senha e alerta de segurança dependem dele. Configure `MAIL_PROVIDER=smtp` e
`SMTP_HOST`. Não há modo "sem e-mail".

### Outras recusas da mesma família

| Mensagem | O que fazer |
|---|---|
| `COOKIE_SECURE deve ser true em staging/production` | Ligue; cookie de sessão sem `Secure` vaza em qualquer ponto sem TLS |
| `IMPACTO_SEED_DEMO não é permitido em staging/production` | Desligue; dado fictício em ambiente oficial é o que faz demonstração enganar |
| `RATE_LIMIT_MULTIPLIER deve ser 1` | É folga de teste; em staging/produção desativaria o limite de tentativas |
| `PASSWORD_SCRYPT_N abaixo de 2^17 não é permitido` | É folga de teste; abaixa o custo de quebrar senha |
| `PUBLIC_BASE_URL deve usar https` | Corrija a URL |
| `BILLING_PROVIDER=stripe exige STRIPE_SECRET_KEY e STRIPE_WEBHOOK_SECRET` | Ou configure os dois, ou volte o provedor |

### `503 {"status":"unavailable","pending_migrations":[…]}`

O banco está atrás do código. Rode as migrações **antes** de liberar tráfego. A lista nomeia quais
faltam.

### `503 Frontend não compilado. Rode: cd web && node build.mjs`

O backend subiu, o `web/dist` não existe. Compile o front antes.

### `503 {"status":"unavailable","database":"down"}`

A aplicação não alcança o PostgreSQL. Confira rede privada, credencial de `impacto_app` e se a
instância está no ar.

---

## B. Sobe, mas ninguém entra

### `503 legal_documents_not_published` no cadastro

**Não é defeito.** As 11 minutas jurídicas não passaram por advogado, e o gatilho do banco recusa
aceite de documento que não esteja aprovado e vigente. Enquanto `terms_of_use` e `privacy_policy`
forem minutas, o cadastro em produção responde isso.

```bash
python3 -m impacto.cli legal-list      # situação de cada minuta, com o id
```

Depois da revisão jurídica de verdade, e só depois:

```bash
python3 -m impacto.cli legal-approve \
  --doc-key terms_of_use \
  --reviewed-by "Nome e registro de quem revisou" \
  --review-reference "parecer, processo ou contrato que embasa"
```

Os dois argumentos são exigidos pela função **e** por um `CHECK` do banco. Isso não impede inventar
um nome — impede inventar sem deixar autor.

### `403 bad_origin` — "Origem não permitida"

O navegador mandou um `Origin` que não está em `PUBLIC_BASE_URL` nem em `CORS_ORIGINS`. Acontece
sempre que o front é servido de um domínio e a API de outro. Acerte a configuração; não relaxe a
verificação.

### `403 csrf` — "Token CSRF ausente ou inválido"

Sessão por cookie exige o cabeçalho `X-CSRF-Token` em POST, PUT, PATCH e DELETE. Em cliente próprio,
leia o cookie `__Host-impacto_csrf` (ou `impacto_csrf` sem TLS) e reenvie o valor no cabeçalho.

### `429 rate_limited` — "Muitas tentativas"

O limite está valendo. Em teste automatizado use `RATE_LIMIT_MULTIPLIER` — **só em teste**: fora de
`development`/`test` a aplicação recusa subir com ele diferente de 1.

---

## C. Entrou, mas a tela não faz o que devia

### `409 no_active_org` — "Selecione ou crie uma organização"

O usuário existe e não tem organização ativa. Quase toda rota exige uma.

### `403 wrong_org_kind` — "Recurso indisponível para este tipo de organização"

A rota declara os tipos que a alcançam, e o seu não está na lista. **Confira no painel de telas antes
de abrir chamado**: 37 telas são só de Administração, e isso é desenho.

### `403 insufficient_role` / `403 permission_denied`

Papel abaixo do exigido pela rota. `permission_denied` com `"source": "staff_roles"` quer dizer que o
papel na equipe da plataforma não inclui aquela permissão — diferente de não ser administrador.

### `403 mfa_required` — "Administração exige MFA ativo e verificado nesta sessão"

Não basta ter segundo fator cadastrado: tem que ter sido verificado **nesta** sessão.

### `503 platform_halted`

O **interruptor de emergência** está acionado para aquele escopo. Veja o estado e o motivo em
`/admin/interruptor`; as rotas do próprio interruptor são isentas dele, de propósito — é o vidro que
se quebra por dentro.

### `402 spend_limit_reached`

Teto de gasto da organização atingido. É limite de produto, não falha.

### Botão de SSO não aparece em `/entrar`

Não é defeito: `GET /v1/meta/config` (rota crua em `app.py`, fora do registro `@route`) devolve
`sso_enabled: false` enquanto `OIDC_ISSUER`, `OIDC_CLIENT_ID` e `OIDC_REDIRECT_URI` não estiverem
configurados, e a tela esconde o botão. Configure os três (com `https`) e ele aparece.

**Correção de registro.** A v0.23.1 anunciou isto como "defeito conhecido: o backend não registra a
rota". Estava errado. O cruzamento tela × backend lia só `impacto.http.ROUTES` e ignorava as seis
rotas Starlette cruas de `app.py`; a rota existe desde sempre. Quem apontou foi o teste que sobe o
entrypoint do contêiner de verdade (`test_v0240_container_entrypoint.py`) e viu a resposta completa.

### Tela abre vazia e nada acontece

Antes de chamar de defeito, veja no painel de telas o que aquele componente chama:

- **"sem chamada direta"** (60 telas): o componente não chama a API por conta própria. Pode ser tela
  estática, pode buscar por um auxiliar compartilhado — a leitura por componente não distingue.
- **"chama backend"**: aí sim, vazio é suspeito. Abra o console do navegador e veja a resposta.

---

## D. Operando o banco

### `permission denied for table legal_documents`

`impacto_app` **não tem INSERT** nessa tabela, de propósito: documento legal entra por migração ou
pelo dono do schema, não pela aplicação. Use `impacto_owner` para a operação.

### `inconsistent types deduced for parameter $2`

O mesmo `$2` está servindo a duas colunas de tipos diferentes no mesmo comando. O PostgreSQL deduz
**um** tipo por parâmetro. Anote: `$2::uuid`, `$3::text`.

### `situação de documento legal não volta`

Gatilho recusando `approved → draft`. Não force: documento aprovado que volta a rascunho apaga a
prova de que esteve vigente. Crie uma versão nova.

### Linhas somem sem erro em consulta pelo `psql`

Você conectou como um papel sujeito à RLS, sem organização no contexto. Confira com qual papel
entrou. **Nunca** use `FORCE ROW LEVEL SECURITY` para "resolver": ela passaria a valer para o DONO da
tabela, que é quem roda `pg_dump` — o backup sairia silenciosamente incompleto.

### Verificação de cadeia de hash acusando quebra

`audit_verify`, `ledger_verify`, `value_verify` e `trust_verify` recalculam a cadeia. Se acusarem,
**não regrave a cadeia para ficar verde** — isso destrói exatamente a prova que ela existe para dar.
Descubra qual linha divergiu e por quê; a cadeia estar quebrada é informação, não um incômodo.

---

## E. Quando nada acima explica

1. Pegue o `request_id` da resposta de erro — todo `500` traz um.
2. `python3 scripts/smoke_test.py --base <url>` — 27 verificações; a que falhar já estreita muito.
3. `GET /healthz` e `GET /readyz` dizem se é banco, migração ou aplicação.
4. Olhe o log pelo `request_id`, não pelo horário.

E uma regra que vale mais que qualquer item desta lista: **quando o produto recusa alguma coisa, a
primeira hipótese é que ele está certo.** Nesta base, as recusas que mais parecem defeito — aceite de
minuta, `approved → draft`, `wrong_org_kind`, `permission denied` — são todas deliberadas, e cada uma
tem um motivo escrito no código que a implementa.
