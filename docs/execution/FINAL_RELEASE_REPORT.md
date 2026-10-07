# RELATÓRIO FINAL DE RELEASE — IMPACTO v0.23.0

Os 25 itens que o pacote de execução exige, na ordem em que os exige. Cada número vem de uma
execução desta rodada; onde algo não foi executado, está dito como não executado.

---

### 1. Versão

**0.23.0** — e os quatro declarantes concordam, o que nesta rodada deixou de ser verdade por acidente
e passou a ser verdade por teste: `VERSION`, `backend/pyproject.toml`, `web/package.json` e
`docs/openapi.json`.

Os dois do meio diziam **0.14.0** — nove versões atrás. O runtime lê `VERSION` (`config.py:15`),
então o produto funcionava e ninguém notou. `test_v0230_release_gate.py` passa a reprovar a
divergência.

### 2. Commit

`67bc6aa` · branch `audit/v0.23.0-completion` · base `chore/v0.19.0-vocabulary-firstrun-ops`

| Commit | Escopo |
|---|---|
| `9ca75f1` | Gates 0-4: as quatro matrizes, derivadas do código e travadas por teste |
| `b4c6958` | Gate 5: dez conferências de segurança, nove executadas e uma declarada bloqueada |
| `5d0ce11` | Gate 6: dados e infraestrutura, executados contra PostgreSQL real do zero |
| `7b286d7` | Gates 7 e 8: integrações inertes, modal testado, achado de tabela que não resistiu |
| `67bc6aa` | Regressão completa: quatro testes que vazavam estado entre arquivos |

### 3. Tag

`v0.23.0-audit-completion`, anotada, criada localmente. **O envio da tag ao remoto é recusado neste
ambiente** — a tag existe no repositório e precisa de `git push --tags` de onde houver permissão.

### 4. Data

2026-10-07 (UTC).

### 5. Ambiente de execução

PostgreSQL **16.15** · Python **3.13.16** · TypeScript **6.0.3** · esbuild **0.28.2** · React
**19.2.8** · Chromium (Playwright) presente.

Limites do ambiente, declarados: registry **npm responde 403**; índice **PyPI indisponível**; sem
Docker; envio de tag ao remoto recusado; nenhuma base de vulnerabilidade alcançável.

### 6. Testes executados

**2.184** na regressão completa, mais **17** de desempenho em passo próprio. **115 são novos desta
rodada.**

### 7. Testes aprovados

**2.184 de 2.184.** Falhas: 0. Erros: 0. Duração: 585 s.

### 8. Falhas corrigidas

**5**, todas na primeira execução completa desta rodada, e **nenhuma era defeito do produto**:

| Falha | O que era | Correção |
|---|---|---|
| cadeia do ledger quebrada | `test_ledger_tampering_is_detected` forja um ledger com privilégio de DBA para provar a detecção, e deixava a forja | restaura o valor original em `addCleanup` |
| cadeia de auditoria quebrada | dois testes do motor de auditoria forjam a cadeia pelo mesmo motivo | idem, nos dois |
| varredura de segredo acusando | o controle negativo escrevia chaves reais como literais e a varredura acusou o próprio arquivo que a verifica | amostras montadas em pedaços |
| idem, no teste de arquitetura | mesma causa | mesma correção |
| manifesto desatualizado | 20 arquivos novos | manifesto regenerado |

**Nenhum teste foi enfraquecido ou removido para obter verde.** Os três testes de adulteração
continuam provando a detecção; passaram a limpar o que sujam.

### 9. Cobertura

Não há número de cobertura de linha, e inventar um seria pior que não ter. O que existe é **cobertura
declarada e conferida por conjunto**:

| Conjunto | Cobertura |
|---|---|
| Operações de API | **888 de 888** classificadas, com o ponto de estrangulamento exercitado por classe |
| Motores | **42 de 42** com teste, caso de dado faltante, caso adversarial e rotas conferidas |
| Passos de jornada | **49 de 49**, todos ponta a ponta |
| Tabelas com RLS | **321 de 322** (a exceção é `schema_migrations`, com motivo escrito) |
| Integrações com teste de contrato | **14 de 14** |

### 10. Segurança

**9 de 10 itens do Gate 5 executados, 1 bloqueado.** 165 testes verdes. Detalhe em
`SECURITY_GATE.md`.

SSRF recusa **22 grafias** do mesmo destino interno (link-local IPv4/IPv6, mapeado, decimal, octal,
loopback, privadas, unique-local) e a isenção de loopback do desenvolvedor é conferida **morrendo em
produção**. CRLF testado **por socket cru**, porque o cliente do Python se recusa a montar o
cabeçalho malformado e isso nada prova sobre o servidor. Injeção de SQL provada pela carga que volta
**idêntica** — se voltasse alterada, alguém teria escapado, e escapar é o caminho errado. Varredura
de segredo própria, **com controle negativo**.

**SCA não executado** (D-SUP2).

**⚠️ Nenhuma garantia de inviolabilidade é dada.** Nenhum sistema conectado à internet pode
recebê-la. Não houve teste de intrusão por terceiro.

### 11. Os 42 motores

42 no registro: **37 determinísticos, 2 de recuperação ancorada, 3 assistidos por modelo**. Todos com
arquivo de teste, caso de dado faltante, caso adversarial e rotas conferidas. **0 FAILED.** 41
alcançados diretamente; 1 (`solution_scoring`) pelo chamador, registrado em `reached_via`.

### 12. As 888 operações

Classificadas em 7 classes de acesso, lidas do **roteador** e não do OpenAPI (que é derivado dele):
organização 220 · organização por papel 186 · plataforma 138 · organização por tipo e papel 112 ·
usuário sem organização 97 · plataforma com permissão 83 · pública 52.

A prova é o exercício: **221 chamadas HTTP reais** de organização-cliente contra a porta da
plataforma, **todas 403**; 83 rotas com permissão nomeada recusando papel que não a tem, **com
contraprova** de que o mesmo papel alcança o que lhe cabe; IDOR/BOLA de leitura, escrita, remoção e
listagem recusados **pela parede (RLS)**, não só pela porta.

### 13. Personas

Cinco, como o pacote exige: **OSC · financiador/empresa · profissional · administração/moderação ·
público sem sessão**. 49 passos, **49 ponta a ponta** (6 por navegador real, 43 por travessia de
API), **0 ausentes**.

Duas travessias foram escritas nesta rodada, pelo que a matriz mostrou faltar: **denúncia → análise →
contraditório → manifestação → conclusão → medida → recurso → julgamento**, e o **incidente do
interruptor de emergência**. Cada regra já estava provada isolada; o caminho nunca era percorrido.

### 14. Integrações

**14 mapeadas: 12 `contract_tested`, 2 `scaffolded`, 0 `sandbox`, 0 `homologated`, 0
`production_active`.** 14/14 com teste de contrato e teste negativo. 14/14 **sem credencial** no
repositório. 129 testes de integração verdes.

Os cinco interruptores de provedor embarcam inertes — `mail_provider=console`,
`storage_provider=local`, `antivirus_provider=none`, `billing_provider=none`, `ai_provider=local` —
travados por teste, e nenhum campo de credencial de `Settings` embarca com valor.

**Nenhuma integração está homologada** (D-INT1..14).

### 15. Desempenho

**17 testes, OK em escala cheia** (10.000 soluções, 100.000 documentos, 100.000 avaliações; volume
criado em 1.072 s). Orçamento declarado: **2.500 ms por consulta**, e todas ficam abaixo.

| Mais lentas (escala cheia) | ms | % do orçamento |
|---|---|---|
| feed do financiador | 1.552 | 62% |
| projetos (100 por página) | 1.361 | 54% |
| projetos (5 por página) | 1.307 | 52% |
| área da OSC | 329 | 13% |
| demais 18 consultas | ≤ 72 | ≤ 3% |

Um teste confere que a lista **não cresce linearmente com o tamanho da página** (20× maior não pode
custar mais de 8×), que é o indício de consulta por linha.

A primeira execução em escala cheia desta rodada parecia **melhor** — feed do financiador 6 ms — e
estava medindo respostas **401**: a sessão do arranjo expirava durante a própria preparação. Corrigido
e registrado em `IMPLEMENTATION_LOG.md`; os números acima são os reais.

### 16. Acessibilidade

**13 conferências no navegador + 4 novas de modal.** Contraste WCAG AA calculado sobre o estilo
**computado** (não sobre os tokens do CSS, que é onde essa verificação costuma passar quando não
deveria), em tema claro e escuro. Nome acessível de todo controle, erro anunciado a tecnologia
assistiva, link de pular, navegação só por teclado, foco visível, marcos e um único H1, alternativa
textual, sem rolagem horizontal em 390 px, alvos de toque, movimento reduzido.

Modal: nome acessível, foco entra, página de trás **inerte**, Escape fecha e **o foco volta**.

Tabelas: **0 cabeçalhos ambíguos** — o achado inicial de "411 `<th>` sem `scope`" não resistiu à
conferência (ver `FRONTEND_GATE.md`).

**Conformidade WCAG 2.2 AA plena NÃO é afirmada.** Seis pendências declaradas com nome e motivo:
axe-core, leitor de tela real, segundo navegador, zoom a 200%, daltonismo, navegação por voz.

### 17. Backup e restauração

Executados nesta rodada contra PostgreSQL real, em banco criado do zero:

| | |
|---|---|
| Backup | 2,1 MB de um banco de 32 MB em **515 ms** |
| Restauração em banco limpo, **com verificação completa** | **5,68 s** |
| O que a verificação cobre | sha256 do dump, 62 migrações, as 4 cadeias de hash, e **15 invariantes de estado** |
| Controle negativo | dump adulterado em **1 byte** → recusado, código de saída 1, nenhum banco criado |

A restauração recusa um dump que traga estado que não deveria existir: regra de receita ativa, cartão
verde, minuta aprovada, cobrança real, denominador sem fonte, selo sem evidência. Um restore que
ligasse receita em silêncio seria **pior** que um restore que falha — a restauração é o momento em
que ninguém olha.

### 18. Observabilidade

**22 testes verdes.** 16 regras de alerta em 3 grupos, cobrindo erro e latência de API, API fora,
falha de IA, reúso de token de renovação, pico de login falho, entrada privilegiada recusada em
série, sessões expirando em massa, MFA desligado em série, papel interno concedido, **interruptor
acionado**, operações recusadas pelo interruptor, **backup falhou**, **backup sem sucesso há tempo
demais**, tarefa falhando e tarefa presa.

Prontidão: `/readyz` passa a ter **os dois ramos de 503 testados** (migração pendente, nomeando
quais; e banco inalcançável). Antes só o caminho feliz era coberto — e uma sonda que nunca devolve
503 é pior que nenhuma.

### 19. Riscos residuais

1. **Rebind de DNS.** `check_destination` resolve o nome e depois conecta: dois passos, e um DNS
   hostil pode responder diferente entre eles. Escrito na própria função; mitiga-se na camada de
   rede/egress, não no código.
2. **SCA não executado.** Uma das nove dependências de terceiro pode ter aviso publicado não
   conferido nesta rodada.
3. **Sem teste de intrusão.** Nenhum teste automatizado substitui.
4. **Integração não homologada.** O comportamento contra o fornecedor real pode divergir do contrato.
5. **O typecheck offline não confere atributo de elemento DOM** — limitação medida, não presumida.
6. **O interruptor de emergência é uma defesa, não uma garantia.** Ele para a escrita; não impede a
   invasão.
7. **RTO/RPO não são prometidos** porque dependem do provedor contratado, não do código.

### 20. Bloqueios externos

**D-SUP1** (registry npm 403) · **D-SUP2** (nenhuma base de vulnerabilidade alcançável) ·
**D-INT1..14** (homologação exige credencial de fornecedor). Nenhum resolvível por código. Detalhe,
com causa, responsável, risco e mitigação, em `BLOCKERS.md`.

### 21. Dispensas (waivers)

**Nenhuma.** Nada foi dispensado por conveniência de engenharia. Aprovar uma dispensa é decisão de
quem responde pelo produto, não de quem o constrói.

### 22. Zero pendências

**`OPEN` = 0**, conferido por teste e não por leitura: `test_v0230_execution_matrices.py` reprova se
qualquer célula de qualquer uma das quatro matrizes contiver `OPEN`, `PENDENTE`, `PENDÊNCIA`,
`ABERTO`, `TBD` ou `???`, e reprova se qualquer `status` sair do vocabulário de nove estados.

Totais: **979 PASS · 14 BLOCKED · 0 WAIVED · 9 NOT APPLICABLE · 0 OPEN.** Detalhe em
`FINAL_ZERO_PENDING_REPORT.md`.

### 23. Instruções de implantação

Em `docs/DEPLOYMENT.md` e `DEPLOYMENT_CHECKLIST.md`. O essencial:

1. `IMPACTO_ENV=production` — **sem isso, a isenção de loopback do SSRF continua valendo**, e é a
   porta para todo serviço interno da máquina.
2. `python -m impacto.cli gen-secrets`; `PUBLIC_BASE_URL` em https; `COOKIE_SECURE=true`.
3. Provedores, quando e se homologados: `MAIL_PROVIDER=smtp`, `STORAGE_PROVIDER=s3`,
   `ANTIVIRUS_PROVIDER=clamd`, `ALLOW_UNSCANNED_DOWNLOADS=false`.
4. `IMPACTO_SEED_DEMO` **ausente**.
5. Migrar: `python3 -m impacto.db.migrate` (avanço-somente, sha256 por arquivo).
6. Conferir `/readyz` → 200 `ready`. Se devolver 503 com `pending_migrations`, **não** receba
   tráfego: o código espera esquema que o banco não tem.
7. `TRUST_PROXY_HEADERS=true` **somente** atrás do proxy.

### 24. Rollback

1. **Antes de qualquer coisa**, `scripts/backup.sh` e guarde o `.sha256`.
2. O código volta por `git checkout` da tag anterior e redeploy.
3. **As migrações são avanço-somente**: não há `down`. Reverter esquema é restaurar backup, por
   `scripts/restore_test.sh` **primeiro** num banco descartável — nunca direto em produção.
4. Uma remoção destrutiva de esquema exige declaração em `REMOCOES_DECLARADAS`; há **uma** em 62
   migrações, e ela copia os dados antes de remover.
5. Depois do rollback, `/readyz` acusa se o banco restaurado estiver à frente ou atrás do código.

### 25. Hashes

| Artefato | Valor |
|---|---|
| Manifesto de rastreabilidade | `IMPACTO_v0.23.0_TRACEABILITY.json` — 1.802 arquivos, 28 categorias, 32,24 MB, sha256 por arquivo |
| ZIP distribuível | sha256 em `RELEASE_MANIFEST.sha256`, dentro do pacote |
| ZIP de auditoria | sha256 publicado na entrega |
| Migrações | sha256 por arquivo em `schema_migrations.checksum`, conferido arquivo por arquivo por teste |
| Cadeias de hash | `audit_verify`, `ledger_verify`, `value_verify`, `trust_verify` — todas verificam |

---

## Veredito

**🟡 AMARELO — GO COM CONDIÇÕES.**

A engenharia desta rodada está fechada: 2.184 testes verdes, 979 itens `PASS`, zero `OPEN`, zero
dispensas, e todo bloqueio com causa externa verificável e mitigação conferida.

**Não é verde**, e não seria honesto que fosse. Falta o que não pode ser produzido por código:
homologação real de cada integração, SCA contra base de vulnerabilidade viva, teste de intrusão por
terceiro, e as seis verificações de acessibilidade que exigem dispositivo ou pessoa.

**As condições para seguir** são as validações humanas e de terceiros já nomeadas — não há tarefa de
engenharia pendente nesta rodada.
