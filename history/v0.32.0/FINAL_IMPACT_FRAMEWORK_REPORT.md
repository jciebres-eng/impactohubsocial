# Relatório final — v0.18.0: impacto contextualizado, equidade e confiança

> Relatório honesto, em português, com VERDE / AMARELO / VERMELHO e o motivo de cada cor. Não há
> "parcialmente verde". Todo número vem de consulta ao banco, de teste executado ou de arquivo do
> repositório — nenhum vem de memória.

**Data:** 2026-10-06 · **Versão:** 0.18.0 · **Ramo:** `chore/v0.18.0-impact-framework-equity`
**Suíte:** 1.223 testes, 0 falhas, 26 pulados (os dois passos de volume)
**Banco:** 285 tabelas, 32 migrações, PostgreSQL 16.15 criado do zero
**API:** 815 operações, 70 delas desta rodada

---

## A. A tese, e o que ela custou

A rodada implementa uma frase:

> **Impacto não é quantidade. Impacto é resultado contextualizado.**
> 50 pessoas numa comunidade indígena remota ≠ automaticamente menos impacto que 5.000 pessoas num
> centro urbano com infraestrutura.

Implementar isso honestamente **tira** funcionalidade em vez de acrescentar:

| O que a plataforma **não** faz mais | Por quê |
|---|---|
| Não normaliza número sem denominador declarado com **fonte, data e método** | número por população sem população declarada é número inventado com aparência de precisão |
| Não dá **nota** de equidade | nota de equidade seria usada para ranquear comunidade, que é o oposto da tese |
| Não devolve **veredito** ao comparar dois projetos | `compare()` responde `comparable: false` com os motivos; comparar denominadores de fontes diferentes produz número que parece objetivo e não é |
| Não chama `certified` nada que não seja certificação | a escada de referencial para em `audited`, com gatilho que explica; a plataforma não é organismo certificador |
| Não tem **nota única** de reputação | nota única vira ranking, e ranking vira critério de acesso a financiamento |
| Não pontua **órgão público** nem expõe reputação de **pessoa física** | pontuar ente público é pontuar política pública; reputação pública de pessoa é cadastro restritivo com outro nome |
| Não **concede selo** pela aplicação | o critério é avaliado em SQL, e a aplicação não tem `INSERT` na concessão |
| Não **sobrescreve** o que a pessoa escreveu num formulário | sugestão pergunta, mostra a origem e oferece voltar |

---

## B. Situação por entrega

| # | Entrega | Situação | O que sustenta a cor |
|---|---|---|---|
| 1 | **Motor de equidade e contexto** | 🟢 VERDE | 7 métodos, denominador versionado com fonte obrigatória, escada de prova das barreiras, avaliação sem nota · `test_v0180_equity.py` (30) |
| 2 | **Normalização rotulada** | 🟢 VERDE | sem denominador, todo método responde "indisponível" **com motivo**; nenhuma estimativa |
| 3 | **Comparação que se recusa** | 🟢 VERDE | `comparable: false`, `reasons[]`, `verdict` sempre nulo, aviso de fontes diferentes |
| 4 | **Território como catálogo** | 🟡 AMARELO | estrutura, perfil com `measured` e dois importadores prontos; **o dado do IBGE não entrou** (rede do ambiente) · as 27 UFs semeadas dizem "conferir na carga oficial" |
| 5 | **Determinantes sociais com indicador** | 🟡 AMARELO | 15 definições editoriais com direção e fonte usual; `territory_indicators` **nasce vazia** e a rota diz isso |
| 6 | **Registro de referenciais** | 🟡 AMARELO | 19 referenciais, 4 em uso, 7 mapeáveis, 8 só registrados com `license_note`; **nenhum mapeamento de terceiro inventado** — depende de decisão de produto e jurídica |
| 7 | **Escada de relação sem `certified`** | 🟢 VERDE | 6 degraus; `framework_relation_gate()` recusa com a razão escrita; `verified` exige outro revisor |
| 8 | **Materialidade** | 🟢 VERDE | 3 lentes, limiar declarado, `is_material` **derivada** por gatilho e não escrevível |
| 9 | **Integridade de alegação** | 🟢 VERDE | 11 regras determinísticas, léxico público, **situação sem coluna**, revisão por convite nomeado · `test_v0180_claims.py` (42) |
| 10 | **Reputação explicável** | 🟢 VERDE | 6 dimensões, sem nota única, sem valor sem base, contestação no perfil, correção como ponto novo · `test_v0180_reputation.py` (30) |
| 11 | **Motor de selos** | 🟢 VERDE | critério em SQL, app sem `INSERT`, definição imutável, revogação como fato, recusa registrada · `test_v0180_seals.py` (23) |
| 12 | **Selos publicados** | 🔴 VERMELHO | **zero definições embarcadas**, de propósito: critério de selo é decisão de produto (como regra fiscal, ADR-025). Sem decisão do proprietário, nenhum selo existe |
| 13 | **Busca incremental com procedência** | 🟢 VERDE | 13 buscas, origem em toda linha, isolamento testado, `%`/`_` como texto · `test_v0180_lookups.py` (17) |
| 14 | **Componente que não sobrescreve** | 🟢 VERDE | pergunta, mostra origem, oferece voltar; aplicado em dois campos reais como prova de ponta a ponta |
| 15 | **Formulário em etapas** | 🟡 AMARELO | componente pronto e com a regra de não esconder trabalho feito; **aplicado em nenhum formulário longo ainda** — é trabalho da fase de design |
| 16 | **Responsabilidade designada** | 🟢 VERDE | responsável × papel × escopo × período × decisão × versão, separada da assinatura, quatro-olhos em dado · `test_v0180_responsibility.py` (25) |
| 17 | **Segurança e isolamento das 33 tabelas** | 🟢 VERDE | RLS e política em todas, inventário do que é aberto de propósito, matriz de isolamento com teste par · `test_v0180_security.py` (24) |
| 18 | **LGPD da camada nova** | 🟢 VERDE | nenhuma coluna de CPF/RG/documento; único nome de pessoa é o da designação externa; barreira é atributo do projeto, não da pessoa |
| 19 | **Testes de viés** | 🟢 VERDE | projeto pequeno e território remoto não penalizados; reputação é **proporção**, não volume; organização nova sem medida |
| 20 | **Testes de gaming** | 🟢 VERDE | alegação não verificada não conta; retirar marcada não limpa; autovalidação, revisão sem convite e autoconcessão recusadas; denominador mínimo não fabrica veredito |
| 21 | **Desempenho** | 🟢 VERDE | 7 operações medidas, a mais lenta em 48 ms com orçamento de 2.500; busca incremental em 9 ms com orçamento de 800 |
| 22 | **Documentação conferida contra o banco** | 🟢 VERDE | `test_v0180_docs.py` (18) confere 11 regras, 6 dimensões, 12 critérios, 8 papéis, 6 tipos, 13 buscas, zero selos, zero metas |
| 23 | **Metas oficiais dos ODS (169)** | 🔴 VERMELHO | **não carregadas**: a rede do ambiente alcança só registros de pacote e o pedido de permissão de busca na web expirou. Estrutura e importador prontos; `GET /v1/lookups/ods_targets` devolve lista vazia, e um teste fixa esse estado |
| 24 | **Mapeamento para GRI / ISSB / IRIS+** | 🔴 VERMELHO | depende de decisão de **produto e jurídica**: as minutas da v0.17.0 excluem expressamente relatório pronto para CVM, GRI, SASB e ISSB. Mapear mudaria o que as minutas prometem |
| 25 | **Decaimento por idade na reputação** | 🔴 VERMELHO | observação de três anos pesa como a de ontem. `core/evidence.py` já tem decaimento para evidência; aplicá-lo às dimensões é a dívida mais importante desta fase |
| 26 | **Detecção de conluio** | 🔴 VERMELHO | duas organizações que validam medições uma da outra sobem em duas dimensões. O sinal existe no banco desde a v0.8.0; a detecção não existe |
| 27 | **Verificação pública dos selos novos** | 🔴 VERMELHO | `/v1/public/verify/{code}` continua servindo os registros verificáveis da v0.14.0; ligar os selos desta fase a ela não foi feito |
| 28 | **Procedência do preenchimento persistida** | 🔴 VERMELHO | o componente devolve `{filled_by, origin, replaced_text}`; nenhum formulário grava isso ainda |

**Contagem:** 16 verdes · 4 amarelos · 8 vermelhos. Nenhum vermelho é surpresa: cada um está escrito
também no documento da fase correspondente e, onde cabia, num teste que fixa o estado.

---

## C. As decisões difíceis, e por que foram tomadas assim

### C.1 Recusar a nota única de reputação (ADR-201)

Os prompts pedem "score de reputação". A implementação recusa o número único, e essa é a divergência
mais importante da rodada. O raciocínio:

1. Nota única é **ordenável**. Basta uma tela ordenando OSCs por reputação.
2. Ordenação é **critério de acesso**: quem está embaixo não é visto, e quem não é visto não capta.
3. A OSC pequena, nova e sem histórico fica embaixo **por não ter histórico**, não por ter falhado.

A saída é por dimensão, cada uma com valor, confiança, número de observações, quanto disso foi
verificado por terceiro e a lista do que entrou na conta. Compor as dimensões numa nota só continua
possível — **fora** da plataforma, por quem assinar a escolha dos pesos. Que é exatamente o ato que a
nota única esconde.

### C.2 Organização nova começa sem medida, não com nota baixa (ADR-202)

`value` nulo e faixa `insufficient` enquanto a dimensão não tem o mínimo de observações. É a decisão
que mais muda o resultado na prática: nota baixa por ausência de histórico seria uma barreira de
entrada construída por acidente, e cairia exatamente sobre quem a plataforma existe para atender.

### C.3 A situação da alegação não é uma coluna (ADR-197)

A tentação era guardar `status` em `claims`. O problema fica óbvio depois de escrito: coluna de
situação é escrevível, e no dia em que alguém precisar que a alegação apareça como comprovada, ela
apareceria. `claim_status()` deriva da última rodada de verificação. Um teste lê o
`information_schema` e falha se a coluna reaparecer.

### C.4 O critério de selo é avaliado em SQL (ADR-207)

Se a avaliação morasse em Python e o resultado fosse gravado por uma rota, bastaria uma chamada com o
corpo certo para conceder selo sem critério — e nenhuma revisão de código pega isso um ano depois.
`seal_evaluate()` consulta os fatos; `app_award_seal()` a reexecuta antes de inserir; a aplicação não
tem `INSERT` na tabela. Nem o dono do banco escapa da avaliação, e há teste para isso.

### C.5 Revisão de alegação é por convite nomeado (ADR-200)

A primeira versão deixava qualquer organização revisar qualquer alegação marcada. Duas consequências
ruins: revisar exige **ler**, então "qualquer um revisa" equivale a publicar toda alegação marcada; e
revisão não solicitada é canal para pressionar concorrente. O convite nomeado abre a leitura e vale
para **uma rodada** — como assinatura vale para uma versão.

### C.6 Pessoa externa sem CPF (ADR-220)

Consultora, avaliadora, contadora terceirizada entram por **nome**. Não existe coluna de documento
nesta camada, e um teste lê o `information_schema` para garantir. O registro de quem respondeu não
precisa do número do documento.

---

## D. Dois defeitos que os próprios testes encontraram

1. **Reputação publicava número que a confiança não sustentava.** Havia observações bastando e
   verificação por terceiro baixa; a restrição `insufficient_has_no_value` recusou a gravação do
   snapshot. Corrigiu-se o **cálculo**, não a restrição — e o caso virou teste com nome.
2. **A recusa de selo apagava o registro da própria recusa.** A exceção dentro de
   `app_award_seal()` desfazia a transação e levava embora o `seal_evaluations` recém-gravado,
   justamente o registro que responde "por que eu não recebi". A função passou a devolver `NULL` e o
   422 é levantado fora da transação (ADR-208).

Nenhum teste foi enfraquecido ou removido. Quatro testes **meus** foram corrigidos porque mediam a
coisa errada — varredura por substring acusando `org_id` (contém "rg") e `name_pt` (contém "name"),
lista de parâmetros maior que a consulta, e expectativa de exceção onde o desenho correto passou a
devolver `NULL`.

---

## E. O que depende do proprietário

| # | Decisão | Por que não posso tomar | Consequência de não decidir |
|---|---|---|---|
| 1 | **Carga oficial do IBGE e das 169 metas dos ODS** | depende de arquivo oficial; a rede deste ambiente alcança só registros de pacote | o catálogo territorial continua marcado "conferir na carga oficial" e `ods_targets` continua vazio |
| 2 | **Mapear indicadores para GRI, ISSB e IRIS+** | é decisão de produto **e** jurídica: as minutas da v0.17.0 excluem esses relatórios | os três referenciais continuam `registry_only`, sem nenhum mapeamento |
| 3 | **Quais selos existem, com que critério e validade** | critério de selo é política da plataforma | zero selos concedíveis (o motor funciona; a definição falta) |
| 4 | **Licença de uso dos emblemas oficiais dos ODS** | autorização de marca da ONU | número, nome e cor oficiais existem; a arte, não |
| 5 | **Revisão técnica das listas editoriais** (12 barreiras, 15 determinantes, 15 temas de materialidade, 8 papéis) | a redação é nossa e está declarada como editorial em cada linha | as listas continuam dizendo, no próprio dado, que não são classificação oficial |
| 6 | **Prazo de retenção das trilhas novas** | prazo de prova é decisão do responsável pelo tratamento | as trilhas permanecem sem prazo (declarado em `LGPD_AUDIT.md`) |

---

## F. Como conferir tudo isto

```bash
# banco do zero (32 migrações)
ADMIN_DATABASE_URL="postgresql://postgres@127.0.0.1:5432/postgres" bash scripts/dev_reset_db.sh

# suíte completa
cd backend && TEST_ADMIN_DATABASE_URL="postgresql://postgres@127.0.0.1:5432/postgres" \
  PASSWORD_SCRYPT_N=16384 RATE_LIMIT_MULTIPLIER=1000 python3 -m unittest discover -s tests -t .

# volume desta rodada
cd backend && PERF=1 TEST_ADMIN_DATABASE_URL="..." python3 -m unittest tests.test_v0180_performance

# lint, tipos e construção da interface
/root/.local/bin/ruff check backend/impacto backend/tests
cd web && node node_modules/typescript/bin/tsc -p tsconfig.offline.json --noEmit && node build.mjs

# integridade do banco e consultas preparadas
REPORT_DATABASE_URL="postgresql://impacto_owner@127.0.0.1:5432/impacto_dev" \
  python3 scripts/db_integrity_report.py
DB="postgresql://impacto_owner@127.0.0.1:5432/impacto_dev" \
  python3 scripts/sql_prepare_check.py backend/impacto/impact
```

---

## G. Próxima fase

**Design.** Agora com o modelo de impacto decidido: o que a tela vai mostrar como "impacto" tem
denominador, fonte e faixa de confiança; o que ela vai mostrar como "reputação" tem seis dimensões e
nenhuma nota; o que ela vai mostrar como "selo" tem critério legível e data de validade; e o que ela
vai mostrar como "sugestão" tem origem.

As quatro telas que a fase de design herda prontas em dado, e que não existiam antes desta rodada:
perfil de reputação com contestação visível, ficha de selo com critério e evidência, verificação de
alegação com as regras que falharam, e quadro de responsabilidade com papéis vagos aparecendo como
informação.

---

## H. O pacote

`dist-release/IMPACTO_v0.18.0_IMPACT_CONTEXT_EQUITY_TRUST.zip` — 952 arquivos, sem ZIP aninhado, sem
segredo, sem `node_modules`, sem despejo de banco. O hash está no `.sha256` ao lado, e o manifesto
por arquivo em `V0.18.0_FINAL_MANIFEST.json` (951 arquivos em 28 categorias; o manifesto não contém
o próprio hash).

Para conferir o pacote recebido:

```bash
sha256sum -c IMPACTO_v0.18.0_IMPACT_CONTEXT_EQUITY_TRUST.zip.sha256
unzip -q IMPACTO_v0.18.0_IMPACT_CONTEXT_EQUITY_TRUST.zip -d /tmp/conferir
python3 scripts/make_release.py --verify /tmp/conferir/plataforma-impacto-v0.18.0
```

Backup e restauração conferidos nesta rodada (`scripts/backup.sh` + `scripts/restore_test.sh`): as
32 migrações voltam, as cadeias de hash do ledger e da auditoria continuam íntegras, a camada
econômica volta **desligada** e a camada de impacto volta **íntegra** — nenhum denominador sem
fonte, nenhum selo sem evidência ou de rascunho, nenhuma linha de base sem fonte, nenhuma reputação
sem observação, nenhuma relação fora da escada. Os seis conferidores novos foram acrescentados nesta
rodada ao `restore_test.sh`, porque a restauração é exatamente o momento em que ninguém olha.
