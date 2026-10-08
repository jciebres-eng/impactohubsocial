# Triagem do pacote `IMPACTO_CLAUDE_UI_FULL_DEMO_WORKSPACE.zip`

O pacote recebido tem duas partes: `app/` (este repositório em v0.23.1 **mais 29 arquivos novos e 11
modificados** por outro agente, que publicou uma instância em `*.manus.space`) e
`reference/IMPACTO_DESIGN_SYSTEM_FULL_CORRETO_v2.3` (a identidade oficial). Nada entrou no repositório
sem passar por esta lista. Cada decisão tem o motivo; onde a decisão foi "aceitar com correção", a
correção está nomeada.

Conferência de origem: dos 1982 arquivos em comum, 1971 são byte a byte iguais ao commit `7ccc58a`.
Os 16 que só existem aqui são logs de evidência, que o empacotador exclui de propósito.

## A. Modificados pelo outro agente

| Arquivo | Decisão | Motivo |
|---|---|---|
| `Dockerfile` | **RECUSADO** | Troca `IMPACTO_ENV=production` por `development` com `IMPACTO_SEED_DEMO=true` e fixa `PUBLIC_BASE_URL=https://…manus.space`. Isso desliga as travas de `config.validate()` — scrypt mínimo, limite de tentativas, e-mail real, proibição de seed — **rotulando produção como desenvolvimento**. É a simulação que a regra proíbe. O que estava certo (entrypoint com etapas) entrou pelo `start_container.sh`, abaixo. |
| `backend/impacto/security/crypto.py` | **RECUSADO** | Se `FIELD_ENCRYPTION_KEY` estiver presente mas inválida, em desenvolvimento passa a usar silenciosamente uma chave derivada. Esconde configuração errada e, pior, dado cifrado com a chave derivada fica ilegível quando alguém corrigir a variável. Falhar alto é o comportamento certo também em desenvolvimento. |
| `backend/impacto/db/pq.py` | **ACEITO COM CORREÇÃO** | `SET search_path TO public, extensions` em toda conexão, para o Supabase (pgcrypto mora em `extensions`). A correção definitiva está na migração (abaixo); a sessão passa a incluir `extensions` **só se o schema existir**, e isso fica escrito no código. |
| `web/src/api.ts` | **RECUSADO** | Resposta 2xx sem JSON passa a lançar 502. Existe para o mock estático responder "indisponível". No produto real, uma rota que devolva texto/CSV/PDF quebraria. Não há caso de uso legítimo fora do mock. |
| `web/src/session.tsx` | **ACEITO** | Checagem defensiva de `/v1/me` antes de usar `csrf_token`. Inofensiva e correta. |
| `Makefile` | **RECUSADO** | Alvo `share` com recuo em espaços (o `make` exige tabulação — não roda) e aponta para o mock estático. |
| `RELEASE_MANIFEST.*`, `web/dist/*` | **IGNORADOS** | Gerados; são regenerados aqui. |

## B. Novos, vindos do outro agente

| Arquivo | Decisão | Motivo |
|---|---|---|
| `backend/start_container.sh` | **ACEITO COM CORREÇÃO** | Entrypoint com etapas nomeadas (bootstrap → migração → seed → ASGI) é o certo. Correções: `IMPACTO_APP_PASSWORD` passa a ser **obrigatória** (a versão recebida reusava a senha do administrador para o papel da aplicação, anulando a separação); o seed só roda se `IMPACTO_ENV` permitir, e a aplicação recusa subir de qualquer modo fora disso. |
| `backend/impacto/db/bootstrap_external.py` | **ACEITO COM CORREÇÃO** | Cria `impacto_app` num banco gerenciado onde `infra/db/bootstrap.sql` não pode rodar. Correção: exige `IMPACTO_APP_PASSWORD`; não deriva da URL administrativa. |
| `backend/migrations/0063_…supabase_pgcrypto_search_path.sql` | **SUBSTITUÍDA** | Direção certa, cobertura incompleta: fixa `search_path` em 5 funções, mas **9** chamam `digest()` (`trust_verify`, `legal_doc_hash`, `chain_value_event`, `value_verify` ficaram de fora). A migração deste repositório cobre as nove, e um teste varre o catálogo exigindo que toda função cujo corpo cita `digest(` tenha `extensions` no `search_path`. |
| `web/package-lock.json` | **ACEITO** | Fecha a lacuna D-SUP1 (único item que a falta de rede impedia aqui). `lockfileVersion 3`, dependências idênticas ao `package.json`, 128 pacotes, todos com `integrity`; as 6 versões instaladas neste ambiente conferem. **`npm ci` não foi executado aqui** — isso continua sendo da sessão com rede. `web/INSTALLED_TREE.json` fica como registro, com a nota de que não é lockfile. |
| `web/public/impacto-brand/*` | **SUBSTITUÍDO PELA FONTE** | Cópia parcial da identidade. Entra a identidade a partir do pacote `reference/`, com `tokens.json` canônico e ferramenta de geração, não a cópia solta. |
| `server.mjs`, `scripts/share_demo.py`, `docs/SHARED_DEMO.md`, `web/public/manus-routes.json`, `web/dist/manus-routes.json` | **RECUSADOS** | Servem o `web/dist` **sem backend**, respondendo 503 a `/v1/*`: é o mock navegável do produto. A regra é explícita: não transformar uma aplicação real em mock. A demonstração desta rodada roda o backend de verdade. |
| `app.config.ts` | **RECUSADO** | Logo apontando para CDN de terceiro (`files.manuscdn.com`). A marca é servida pelo próprio produto. |
| `package.json` (raiz), `manus-webdev.json`, `TODO.md`, `plan.md` | **RECUSADOS** | Arquivos de trabalho da plataforma do outro agente; não descrevem este produto. |
| `RELEASE_AUDIT_LIVE.md` | **RECUSADO** | Documenta uma instância pública em modo `development` e publica a senha de 14 contas dessa instância. A senha é o padrão de `seed_dev.py` (sobrescrevível por `DEMO_PASSWORD`) e só vale onde o seed roda; ainda assim, tabela de credenciais de instância pública não entra em entregável. O que esse documento descreve é operado por terceiro, fora deste repositório. |
| `RELEASE_AUDIT_LOCAL_DEMO.md` | **RECUSADO** | Auditoria do mock estático. O conteúdo verdadeiro dela (Docker e PostgreSQL ausentes no ambiente de montagem) já está em `ESTADO_PARA_SESSAO_NUVEM.md`. |
| `docs/PROMPT_MESTRE_ETAPA_VIRTUALIZACAO.md` | **ARQUIVADO** | Prompt de trabalho; guardado em `docs/execution/recebidos/` como registro, sem valer como especificação. |

## C. A identidade oficial (`reference/IMPACTO_DESIGN_SYSTEM_FULL_CORRETO_v2.3`)

Entra como **fonte**, não como pasta copiada. O que a própria documentação do pacote diz sobre seus
limites vale aqui e não é suavizado:

- **Licença da marca não comprovada** e logo master em **raster** 303×240 (não há vetor oficial). Os
  PNGs transparentes derivados são usados nos tamanhos que o guia permite (≤135×130 na barra lateral,
  ≤74 no cabeçalho móvel) e nunca ampliados.
- **Fontes não embarcadas.** A família preferida é IBM Plex Sans; o stack oficial já lista Inter como
  segunda opção, e Inter é a fonte que o produto embarca com licença OFL. Então o que renderiza hoje é
  Inter, e IBM Plex Sans entra quando o produto a embarcar. Lora (serifa de títulos) sai: a identidade
  oficial não tem serifa.
- **Amarelo é cor de ação, não de fundo**, e **texto branco sobre amarelo é proibido**. O CSS atual
  tinha duas ocorrências disso; as duas foram corrigidas.

O que entra: `tokens.json` (fonte única) e `tokens.css` gerado, `components.css`, catálogo de ícones,
logos transparentes, favicons, ícones PWA e os recursos Android/iOS. A ferramenta `generate_tokens.py`
entra também, e um teste exige que o `tokens.css` versionado seja exatamente o que ela gera.

## D. O que esta triagem não decide

- Se a instância em `*.manus.space` deve continuar no ar. Ela roda em modo de desenvolvimento, com
  seed e contas públicas; é decisão do proprietário.
- A licença da marca. Ninguém aqui pode comprová-la.
