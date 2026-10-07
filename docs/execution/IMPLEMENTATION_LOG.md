# REGISTRO DE IMPLEMENTAÇÃO — v0.23.0 (rodada de conclusão da auditoria)

Ordem cronológica do que foi feito, o que foi encontrado e o que foi decidido. Escrito para quem
precisa auditar a decisão, não só o resultado.

---

## O tema desta rodada: o instrumento de medição como defeito

**Oito vezes** nesta rodada uma medição acusou defeito e a investigação mostrou que o defeito estava
no instrumento, não no produto. Em nenhuma delas a resposta foi aceitar a leitura falsa; em todas, o
instrumento ficou mais preciso e a razão ficou escrita no código.

| # | A medição acusou | O defeito real era | Correção |
|---|---|---|---|
| 1 | 2 motores sem teste (`data_quality`) | a varredura procurava o caminho literal `/v1/projects/{project_id}/data-quality`, que nenhum teste escreve | casar o sufixo literal depois do último `}` |
| 2 | …e `solution_scoring` | `routes = ()`; é alcançado só por `services/solutions.py::search()` | rastreio de importação de um nível + coluna `reached_via` |
| 3 | 4 provedores sem teste de contrato | a chave do hub (`stripe_payments`) não é o vocabulário do código (`stripe`) | casar partes da chave com 4+ letras |
| 4 | 11 passos de persona AUSENTE | a varredura só olhava `test_e2e*.py`; as jornadas estavam em `test_api_workflow.py` e outros | varrer todos os testes, classificando o TIPO de cobertura |
| 5 | passos "só de rota" em excesso | medir comprimento (5+ rotas) punia a persona pública, cuja jornada é curta por natureza | classificar por TIPO: navegador / travessia / rota |
| 6 | jornada da OSC fragmentada | `FullImpactJourney` parte a travessia em `test_01…test_12` com estado de classe compartilhado | classe com 3+ métodos numerados é travessia por construção |
| 7 | 24 segredos no repositório | referência a variável (`${VAR}`), alfabeto Base32, credencial fictícia de teste, captura que atravessou o fim da string | uma regra escrita por classe, nenhuma isenção genérica |
| 8 | 411 `<th>` sem `scope` | `<th` é prefixo de `<thead>`; e `<th>` dentro de `<thead>` não é ambíguo | contagem correta: **0 ambíguos**; trava só no caso que importa |

---

## Gate 2 — a divergência de versão era real

`backend/pyproject.toml` e `web/package.json` declaravam **0.14.0** enquanto `VERSION` dizia
**0.23.0**. O runtime lê `VERSION` (`config.py:15`), então o produto funcionava e os dois arquivos
ficaram parados por nove versões sem ninguém notar.

Corrigidos os dois, e `test_v0230_release_gate.py` passa a exigir que os quatro declarantes concordem
(`VERSION`, `pyproject.toml`, `package.json`, `openapi.json`), que o CHANGELOG tenha a seção da
versão, que a versão anterior esteja em `history/` e a atual **não**, e que nenhum literal de versão
apareça no código da aplicação.

## Gate 3 — a matriz vem do ROTEADOR, não do OpenAPI

`docs/openapi.json` é **derivado** do roteador. Gerar a matriz de autorização a partir dele mediria a
derivação, não o produto: uma rota que o gerador de OpenAPI esquecesse sumiria da matriz e da
conferência ao mesmo tempo. `scripts/make_authorization_matrix.py` lê `impacto.http.ROUTES`.

As 888 operações caem em 7 classes de acesso: organização (220), organização por papel (186),
plataforma (138), organização por tipo e papel (112), usuário sem organização (97), plataforma com
permissão (83), pública (52).

A prova não é a classificação — é o exercício: **221 chamadas HTTP reais** de uma organização-cliente
contra a porta da plataforma, todas 403 (`respostas: {403: 221}`).

## Gate 4 — 42 motores, e o que a matriz NÃO afirma

42 motores (37 determinísticos, 2 de recuperação ancorada, 3 assistidos por modelo), todos com
arquivo de teste, caso de dado faltante, caso adversarial e rotas conferidas. 41 alcançados
diretamente, 1 pelo chamador (`solution_scoring`), registrado em `reached_via`.

## Gate 5 — segurança

165 testes (139 já existentes + 26 novos). Seis dos dez itens já tinham cobertura sob outro nome;
quatro não tinham teste que os nomeasse (travessia de caminho, redirecionamento aberto, injeção de
cabeçalho, desserialização) e **nenhum revelou defeito no produto** — as defesas existiam, faltava a
trava que impede removê-las em silêncio.

Duas decisões que mudaram o teste em vez do produto:

* **Loopback no SSRF.** A isenção de loopback existe para o desenvolvedor e é intencional. O teste
  certo não é recusá-la: é conferir que ela **morre em produção**. Conferida nos dois sentidos.
* **CRLF pelo socket.** O cliente HTTP do Python se recusa a montar o cabeçalho malformado, o que
  prova que o urllib é bem comportado e nada sobre o servidor. O teste abre um socket e escreve os
  bytes, que é como um atacante faz.

## Gate 6 — a prontidão era o item sem teste

`/readyz` tinha um teste: o do caminho feliz. O ramo que decide se a plataforma sobrevive a um
incidente é o **503**, e nunca era exercitado. Uma sonda que nunca devolve 503 é pior que nenhuma: o
orquestrador manda tráfego para uma instância cujo banco está fora.

Também ficou travada a separação entre prontidão e vivacidade — `/healthz` segue 200 com o banco
fora, e não toca o banco (conferido estruturalmente). Prontidão tira do balanceador; vivacidade
reinicia. Confundir as duas transforma queda de banco em tempestade de reinícios.

## Gate 7 — a matriz de integrações parou de ler o banco

Ela lia `integration_providers` por `psql`, o que a tornava função de qual `DATABASE_URL` estava no
ambiente — rodando sob a suíte, apontava para o banco de teste e divergia da versionada.

O problema maior apareceu na investigação: `maturity` é **promovível** pela administração, e
`test_provider_maturity_requires_admin_and_evidence` promove `totvs` a `homologated` no meio da
suíte, restaurando só na última linha do método — que não roda se uma asserção anterior falhar. Uma
matriz gerada naquele instante declararia **homologação real de um provedor jamais homologado**,
exatamente a afirmação que o pacote proíbe.

Três correções: a matriz passou a ler `config/integration_providers.json` (o catálogo **embarcado**);
um teste exige que nada embarque acima de `contract_tested`; e a restauração daquele teste virou
`addCleanup`.

## Gate 8 — modal testado, tabela inocentada

O modal usa `<dialog>` nativo com `showModal()`, que resolve as quatro quebras clássicas por
construção — mas "por construção" é hipótese até alguém medir. Medido no navegador: nome acessível,
foco entra, página de trás inerte, Escape fecha e o foco volta.

O escopo do typecheck offline foi **medido** plantando um erro de cada tipo, em vez de presumido a
partir de `strict: true`: erro de lógica/hook pega, prop tipada de componente pega, atributo de
elemento DOM **não** pega (limitação declarada do stub).

## Gate 10 — quatro testes que vazavam estado entre arquivos

A primeira execução completa (2184 testes) teve 5 falhas. Quatro eram testes honestos deixando para
trás o estado que forjam **de propósito**:

* três adulteram cadeias de hash com privilégio de DBA para provar que `ledger_verify` e
  `audit_verify` detectam — e deixavam a forja no banco, fazendo o portão de dados (que verifica
  **todas** as organizações e **todos** os projetos) reprovar por um defeito inexistente;
* o controle negativo da varredura de segredo escrevia chaves reais como literais, e a varredura
  acusava o próprio arquivo que a verifica.

Nenhum teste foi enfraquecido. Os três de adulteração continuam provando a detecção e agora restauram
o valor original em `addCleanup` — restaurar o conteúdo restaura o hash, porque o hash é calculado
sobre o conteúdo. As amostras do controle negativo passaram a ser montadas em pedaços, então o
arquivo não carrega segredo e o arquivo **plantado** continua carregando os quatro. Isentar o arquivo
teria aberto um buraco permanente num teste de segurança.

A quinta falha era o manifesto do release, resolvida na regeneração do Gate 10.

## Desempenho — a medição que cronometrava a recusa

A suíte de volume roda em passo próprio. Com `PERF=1` (escala reduzida, volume em 1,6 s) passava há
versões. A primeira execução com `PERF_FULL=1` desta rodada deu **10 falhas e 1 erro** — e nenhuma
era de desempenho: todas eram **401**.

`access_token_ttl` é 900 s; a construção do volume cheio leva ~1.072 s. As sessões criadas em
`setUpClass` morriam **antes da primeira medição**. Em um dos testes o sintoma apareceu como
`KeyError: 'id'`, lendo `.json["id"]` de uma resposta 401.

O detalhe que fazia o engano convincente: os números impressos eram **melhores** que em escala
reduzida — feed do financiador 752 ms → 6 ms, projetos (100) 826 ms → 5 ms. Pareciam uma vitória do
`ANALYZE`. Eram o tempo de o servidor recusar uma sessão expirada.

Corrigido renovando as sessões depois do volume e antes das medições. O que está sob medição é a
**consulta sob volume**, não a duração da sessão — que tem suíte própria em
`test_v0230_session_hardening.py`. Aumentar o TTL para o teste passar seria mudar o produto para
acomodar o arranjo.

Números verdadeiros, em escala cheia, todos abaixo do orçamento de 2.500 ms: feed do financiador
1.552 ms, projetos (100) 1.361 ms, projetos (5) 1.307 ms, área da OSC 329 ms, demais 18 consultas
abaixo de 72 ms.
