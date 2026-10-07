# GATE 5 — SEGURANÇA · EVIDÊNCIA DE EXECUÇÃO

**O que este documento não afirma.** Nada aqui é teste de intrusão. Nenhuma ferramenta destrutiva
foi usada, nada rodou contra produção, e nenhum resultado abaixo substitui pentest por terceiro
independente. A regra permanente do projeto vale inteira: **nenhum sistema conectado à internet pode
receber a garantia de ser impossível de invadir, e este documento não a dá.**

O que ele faz é registrar, item por item do Gate 5, *qual conferência foi executada, por qual teste,
com qual resultado* — e dizer, sem rodeio, o único item que não foi executado e por quê.

**Total executado nesta rodada:** 165 testes de segurança (139 das suítes já existentes + 26 novos),
todos verdes. `ruff check impacto tests` limpo.

---

| # | Item do Gate 5 | Conferência executada | Evidência | Estado |
|---|---|---|---|---|
| 1 | **SAST** | Regras `S` do ruff (flake8-bandit) selecionadas em `backend/pyproject.toml`; `ruff check impacto tests` passa limpo. Teste exige que a seleção `"S"` permaneça e que cada regra ignorada tenha motivo escrito na própria linha. | `test_v0230_security_gate.py::SastIsSelectedInTheLintConfigurationTests` | **PASS** |
| 2 | **SCA** | **NÃO EXECUTADO.** Nenhuma base de vulnerabilidade é alcançável deste ambiente. Inventário exato versionado e fixado (`requirements.txt`, 11 pacotes, todos `==`); CI executa `pip-audit` e `npm audit`. | `BLOCKERS.md` → D-SUP2 | **BLOCKED** |
| 3 | **Varredura de segredo** | `scripts/secrets_scan.py` executada: 731 arquivos de texto rastreados, 0 achados. Procura formato conhecido (AWS, GitHub, Stripe, PEM, JWT, Slack, Google, SendGrid, DSN com senha), atribuição suspeita e entropia alta. **Com controle negativo**: um teste planta 4 segredos reais e exige que todos sejam acusados. | `test_v0230_security_gate.py::TheSecretsScanRunsAndFindsNothingTests` (2 testes) | **PASS** |
| 4 | **SSRF** | 22 destinos internos recusados, em todas as grafias: link-local IPv4 e IPv6, IPv4 mapeado em IPv6, inteiro decimal, octal, loopback IPv4/IPv6, redes privadas A/B/C, unique-local, não especificado. Só HTTPS sai; `file://`, `gopher://`, `ftp://` e http para host externo recusados. Redirecionamento **nunca seguido** (manipulador verificado). A guarda roda no **transporte**, não na rota. A isenção de loopback é conferida nos dois sentidos: vale em `test`, **morre em `production` e `staging`**. | `test_v0230_security_gate.py::TheSsrfGuardRefusesEveryWayOfSpellingTheInsideTests` (5 testes) + `test_v0130_integrations.py::test_ssrf_guard_blocks_at_call_time_even_if_dns_points_inside` | **PASS** |
| 5 | **XSS** | CSP sem `unsafe-inline`, sem `unsafe-eval` e sem `*`, com `default-src 'self'`, `object-src 'none'`, `frame-ancestors 'none'`, `base-uri 'self'`, `form-action 'self'`. Presente em resposta pública, autenticada, 404 e 422. Download de documento serve com `Content-Security-Policy: sandbox; default-src 'none'` e `X-Content-Type-Options: nosniff`. | `test_v0230_security_gate.py::EveryResponseCarriesTheSecurityHeadersTests` (3 testes) + `test_v0120_hardening.py` | **PASS** |
| 6 | **CSRF** | Sessão por cookie com `SameSite`, `HttpOnly` e `Secure` conforme configuração; reautenticação exigida nas operações privilegiadas. | `test_v0150_security.py`, `test_v0230_session_hardening.py` | **PASS** |
| 7 | **Injeção** | **SQL**: 6 cargas clássicas (`' OR '1'='1`, `DROP TABLE`, `UNION SELECT`, `pg_sleep`, escape invertido, percent-encoding) não casam com nada, a tabela responde depois, e a carga gravada como título **volta idêntica** — prova de que foi tratada como dado, não escapada. **Cabeçalho**: CRLF testado **por socket cru**, porque o cliente do Python se recusa a montar o cabeçalho malformado e isso não prova nada sobre o servidor; `x-injetado` não aparece na resposta. **XML**: nenhum módulo usa `xml.etree` sem `defusedxml`. **Comando**: nenhum `eval`, `exec`, `compile`, `pickle`, `marshal`, `shelve` ou `dill` em `impacto/` (verificação por AST, vale para arquivo que ainda não existe). | `test_v0230_security_gate.py::SqlInjectionPayloadsAreDataNotCodeTests` (3), `::HeaderInjectionIsImpossibleTests` (2), `::NothingInThisCodebaseDeserializesUntrustedInputTests` (3) | **PASS** |
| 8 | **Uploads** | Extensão em lista fechada (`ALLOWED`), assinatura binária conferida (*magic bytes*), conteúdo ativo recusado, teto de tamanho (`MAX_UPLOAD_BYTES`, 15 MiB), antivírus por configuração (`ANTIVIRUS_PROVIDER`, inerte em `none`), download de não escaneado governado por `ALLOW_UNSCANNED_DOWNLOADS` (falso quando endurecido). **Travessia de caminho**: a chave de armazenamento é **gerada**, nunca derivada do nome enviado; 5 nomes de travessia (`../`, `..\`, `....//`, absoluto, com byte nulo) não escapam nem sobrevivem como caminho. | `test_v0230_security_gate.py::PathTraversalNeverEscapesTheOrganizationFolderTests` (2) + `test_v0120_hardening.py` | **PASS** |
| 9 | **Cabeçalhos / TLS** | `x-content-type-options: nosniff`, `x-frame-options: DENY`, `referrer-policy: strict-origin-when-cross-origin`, `cross-origin-opener-policy: same-origin`, `permissions-policy` restritiva e CSP — em **toda** resposta, inclusive de erro. HSTS (`max-age=63072000; includeSubDomains; preload`) ligado à configuração `is_hardened` e **ausente** fora dela, conferido nos dois sentidos: HSTS num ambiente sem TLS trancaria o desenvolvedor fora. CORS restrito a `CORS_ORIGINS`. TLS em si é terminado pela infraestrutura, não pela aplicação. | `test_v0230_security_gate.py::EveryResponseCarriesTheSecurityHeadersTests` (3 testes) | **PASS** |
| 10 | **Permissões** | 888 operações classificadas em 7 classes de acesso; **221 chamadas HTTP reais** de organização-cliente contra a porta da plataforma, **todas 403**; 83 rotas com permissão nomeada recusam papel que não a tem, com contraprova de que o mesmo papel alcança o que lhe cabe; IDOR/BOLA de leitura, escrita, remoção e listagem recusados pela **parede (RLS)** e não só pela porta; atribuição em massa de `org_id` recusada; `security.kill_switch` é `super_admin_only` e nem o papel `security` o alcança. | `test_v0230_authorization_matrix.py` (33 testes), `test_security_tenancy.py` (25), `API_AUTHORIZATION_MATRIX.csv` | **PASS** |

---

## Itens do Gate 5 que já tinham cobertura sob outro nome

Seis dos dez itens não precisavam de teste novo — precisavam que alguém dissesse QUAL teste os cobre,
porque "a defesa existe no código" e "a defesa foi exercitada" são afirmações diferentes. A busca por
nome encontrou cobertura para SSRF, CSRF, cabeçalhos, uploads, multilocação e permissões.

Quatro não tinham teste que os nomeasse — **travessia de caminho**, **redirecionamento aberto**,
**injeção de cabeçalho** e **desserialização** — e são os que motivaram
`test_v0230_security_gate.py`. Nenhum deles revelou defeito no produto: as defesas existiam
(chave de armazenamento gerada, nenhuma rota aceitando destino externo, nenhum `pickle`), e o que
faltava era a trava que impede alguém de removê-las sem a suíte acusar.

## Risco residual declarado

1. **Rebind de DNS.** `check_destination` resolve o nome e depois conecta: são dois passos, e um
   servidor DNS hostil pode responder diferente entre eles. Está escrito na própria função e mitiga-se
   na camada de rede/egress da infraestrutura, não no código da aplicação.
2. **SCA não executado** (D-SUP2). Uma das nove dependências pode ter aviso publicado não conferido
   nesta rodada.
3. **Pentest por terceiro não realizado.** Nenhum teste automatizado substitui isto, e esta é uma
   das validações humanas que permanecem fora do alcance desta rodada.
4. **O interruptor de emergência é uma defesa, não uma garantia.** Ele para a escrita, não impede a
   invasão.
