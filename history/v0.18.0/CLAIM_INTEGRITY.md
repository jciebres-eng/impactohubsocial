# Integridade de alegação — FASE 5 da v0.18.0 (atualizado na v0.18.1)

> Documento lido do código. Toda regra citada aqui tem linha em
> `backend/impacto/impact/claims.py` e teste em `backend/tests/test_v0180_claims.py`.
> O que não existe está dito como não existindo.

## 1. O problema

Um relatório de impacto é feito de **alegações**: "atendemos 1.200 pessoas", "contribuímos para o
ODS 4", "reduzimos em 30% o consumo de água", "nosso projeto é neutro em carbono". Cada frase pode
ser verdadeira, exagerada ou inventada — e até esta fase nada no produto confrontava a frase com o
que o banco sabe.

Os documentos desta rodada chamam isso de detecção de *greenwashing*, *social washing* e *impact
washing*. A implementação recusa esse vocabulário como saída: ela não acusa ninguém de lavagem de
imagem. Ela **confronta a frase com o registro** e mostra a divergência.

## 2. As três decisões de desenho

### 2.1 A situação da alegação NÃO é uma coluna

`claims` não tem `status`, `verified` nem `substantiated`. A situação é derivada por
`claim_status(p_claim)` a partir da **última rodada** registrada em `claim_checks`.

O motivo é simples depois de escrito: coluna de situação é escrevível, e no dia em que alguém
precisar que a alegação apareça como comprovada, ela apareceria. Não existindo a coluna, não existe
o que falsificar — nem por administrador, nem por erro de rota, nem por migração futura distraída.
O teste `test_there_is_no_status_column_to_write_to` lê `information_schema` e falha se a coluna
aparecer.

Os oito valores derivados:

| Situação | Quando | O que significa |
|---|---|---|
| `unchecked` | nunca verificada | não verificada |
| `substantiated` | nenhuma regra reprovada | sustentada **pelo que está registrado** — não é atestado de verdade |
| `attention` | só reprovações de atenção | pontos de atenção |
| `flagged` | ao menos uma reprovação grave, sem revisão | exige revisão humana de outra organização |
| `flagged_accepted_by_review` | grave + revisão `accepted` | marcada **e** aceita: a marca permanece |
| `needs_change` | revisão `needs_change` | a revisão pediu alteração |
| `rejected_by_review` | revisão `rejected` | recusada em revisão |
| `withdrawn` | retirada por quem declarou | retirada; o histórico permanece legível |

### 2.2 O verificador NÃO acusa fraude

As regras devolvem `attention` ou `serious`. Nenhuma produz consequência automática: nenhuma
suspende conta, nenhuma remove projeto da descoberta, nenhuma altera reputação. Alegação `serious`
abre a possibilidade de **revisão humana por organização diferente**, e essa revisão:

- é registrada com motivo obrigatório (20 a 2.000 caracteres);
- é append-only (`forbid_mutation()` em `claim_reviews`);
- vale para **uma rodada** — verificar de novo exige convite novo, pelo mesmo princípio que faz
  assinatura não valer para versão nova de documento;
- **não apaga a marca.** Aceitar produz `flagged_accepted_by_review`, não `substantiated`.

Classificar automaticamente alguém como fraudador a partir de casamento de léxico seria pior que o
problema que o verificador resolve.

### 2.3 Revisão é por CONVITE

A primeira versão deixava qualquer organização revisar qualquer alegação marcada. Duas consequências,
as duas ruins: revisar exige **ler** a alegação e a verificação, então "qualquer um revisa" equivale
a tornar pública toda alegação marcada; e revisão não solicitada é canal para pressionar concorrente.

Então quem declarou **convida** uma organização nomeada para a rodada (`claim_review_requests`), e é
o convite que abre a leitura. Sem convite: `GET /v1/claims/{id}` devolve 404 para a outra
organização, e a revisão é recusada com `not_invited`.

A política de `claims` precisa olhar o convite e a política do convite precisa olhar a alegação —
recursão que o PostgreSQL recusa inteira, e com razão. A saída é `app_claim_invited(uuid)`,
`SECURITY DEFINER`, que responde **apenas** "esta organização foi convidada a esta alegação?", não
devolve conteúdo e não responde sobre outra organização.

### 2.4 É determinístico

Nenhuma regra chama modelo de linguagem. São consultas SQL e léxicos declarados em
`claims.py` — não em configuração, porque mudar o que a plataforma considera linguagem absoluta é
mudança de comportamento e tem de aparecer em revisão de código e em teste. O `CHECK`
`rules_are_deterministic` impede cadastrar regra probabilística no catálogo.

Os léxicos são **públicos** em `GET /v1/claims/rules` — quatro listas desde a v0.18.1 (`absolute`,
`totality`, `certification`, `causality`, `comparative`): quem é marcado tem direito de saber por
qual palavra. As flexões de plural estão listadas uma a uma de propósito — casamento por radical pegaria
"gerenciamos" dentro de "gerou", e verificação que erra por regra frouxa não serve nem para
contestar nem para defender.

`test_the_same_text_on_the_same_facts_gives_the_same_verdict` mede o determinismo; ele não é
promessa de documentação.

## 3. As 12 regras

| Código | Gravidade | O que confronta |
|---|---|---|
| `ods_without_indicator` | atenção | ODS declarado sem indicador vinculado |
| `indicator_without_measurement` | atenção | indicador sem nenhum valor validado |
| `measurement_without_evidence` | atenção | medição validada que não aponta para evidência |
| `absolute_language` | **grave** | termo de **prova** (comprovado, garantido, assegurado, indiscutível) **sem** medição validada com evidência |
| `totality_claim_without_coverage` | **grave** | termo de **totalidade** (erradicamos, 100%, zero casos, neutro, universalizamos, cobertura total) sem denominador vigente com fonte **e** medição validada cobrindo ≥ 99% dele |
| `certification_language` | **grave** | o texto afirma certificação, homologação ou aprovação oficial |
| `causality_from_weak_link` | **grave** | causalidade afirmada quando a cadeia só tem hipótese, correlação, associação ou inferência |
| `comparative_without_denominator` | atenção | comparação sem denominador declarado com fonte |
| `number_not_in_measurements` | atenção | número do texto (≥ 10) sem valor validado correspondente |
| `period_outside_execution` | atenção | período da alegação começa antes da execução do projeto |
| `financial_claim_without_receipt` | **grave** | alegação financeira com despesa sem comprovante no cofre |
| `no_basis_at_all` | **grave** | sujeito sem indicador, sem evidência e sem elo de cadeia |

Duas propriedades que os testes protegem:

- **A regra não pune a palavra; pune a palavra sem base.** "O resultado é comprovado" passa quando
  existe medição validada com evidência (`test_absolute_language_passes_when_there_is_a_measurement_with_evidence`).
- **Prova e totalidade são classes diferentes de afirmação** (acrescentado na v0.18.1). A jornada de
  ponta a ponta declarou, de propósito, "O resultado é comprovado e garantido: erradicamos a
  defasagem de leitura" — e o verificador devolveu `substantiated`, porque havia **uma** medição
  validada no projeto e isso bastava para `absolute_language` passar. "Comprovado" afirma prova, e
  uma medição com evidência sustenta a frase; "erradicamos" afirma **totalidade**, e totalidade só
  se confere por divisão: 32 de 60 elegíveis não é erradicação de nada. A regra nova exige
  denominador vigente com fonte **e** cobertura medida ≥ 99%, e a mensagem diz a cobertura real
  ("a cobertura medida é 53% de 60 elegíveis").
- **Melhorar aparece.** Registrar a medição que faltava reduz o número de reprovações na rodada
  seguinte, e as rodadas anteriores continuam legíveis para quem quiser mostrar que corrigiu.

## 4. O que a verificação publica

Toda rodada devolve `facts_used`: indicadores, valores validados, valores com evidência, evidências
aceitas, elos da cadeia por tipo, despesas sem comprovante e denominadores disponíveis — mais
`engine_version` (`claim-integrity@1.0.0`). Verificação que não mostra o que usou não pode ser
contestada, e alegação que não pode ser contestada não deveria poder ser marcada.

## 5. Rotas

| Método | Rota | Quem |
|---|---|---|
| GET | `/v1/claims/rules` | usuária autenticada |
| POST | `/v1/claims` | gestora da organização dona do sujeito |
| GET | `/v1/claims` | leitora da organização |
| GET | `/v1/claims/{claim_id}` | dona, convidada, apoiadora do projeto ou admin |
| POST | `/v1/claims/{claim_id}/check` | gestora |
| POST | `/v1/claims/{claim_id}/withdraw` | gestora |
| GET | `/v1/claims/review-requests` | leitora (fila de convites recebidos) |
| POST | `/v1/claims/{claim_id}/review-requests` | gestora que declarou |
| POST | `/v1/claims/{claim_id}/review` | gestora da organização **convidada** |

## 6. O que esta fase NÃO faz

- **Não lê o texto com IA.** Nenhuma regra é semântica. Frase que engana sem usar nenhum termo do
  léxico passa pelas regras de linguagem — o que ela não escapa é do confronto com os fatos
  (`no_basis_at_all`, `number_not_in_measurements`).
- **Não decide nada sozinha.** Nenhuma situação derivada bloqueia acesso, financiamento ou
  exposição. Essa é a trava que a FASE 6 (reputação) tem de preservar.
- **Não verifica alegação sobre programa, organização, solução ou atualização com a mesma
  profundidade do projeto.** Para esses sujeitos o banco sabe menos, e `_facts()` declara o que não
  tem em vez de inventar base: `facts_used` mostra zero onde é zero.
- **Não detecta número correto em contexto errado.** "40 pessoas" confere com a medição mesmo que a
  medição seja de outro indicador. Amarrar número a indicador exige a alegação apontar para o
  indicador, que é opcional hoje — está declarado como dívida, não como feito.
