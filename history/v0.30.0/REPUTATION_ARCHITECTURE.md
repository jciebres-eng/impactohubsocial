# Reputação explicável — FASE 6 da v0.18.0

> Documento lido do código. Cada regra citada tem linha em `backend/impacto/impact/reputation.py`,
> restrição em `backend/migrations/0029_v0180_reputation.sql` e teste em
> `backend/tests/test_v0180_reputation.py`.

## 1. A frase que governa o desenho

Os documentos desta rodada pedem um sistema de reputação baseado em evidência, e dizem o limite:

> "NUNCA transformar o score em uma caixa-preta que determina automaticamente acesso a
> financiamento, contratação, benefícios, oportunidades ou exposição pública."

Tudo abaixo existe para que essa frase seja verdadeira **por construção**, e não por promessa de
documentação.

## 2. As seis decisões

### 2.1 Não existe nota única — divergência declarada dos prompts

Os prompts falam de "score de reputação". A implementação **recusa** o número único. Nota única é o
que vira ranking, e ranking é o que vira critério de acesso: basta uma tela ordenando OSCs por
reputação para que a OSC pequena, nova e sem histórico fique estruturalmente atrás.

A saída é por dimensão. Quem quiser compor as dimensões numa nota só vai ter de fazer isso **fora**
da plataforma, assinando a escolha dos pesos — que é exatamente o ato que a nota única esconde.

Dois testes sustentam isso: a resposta não tem campo agregado (`score`, `overall`, `rank`,
`rating`, `grade`), e nenhuma coluna do banco guarda agregado.

### 2.2 Dimensão sem base suficiente não tem valor

`value` é `null` e a faixa é `insufficient` enquanto as observações não atingem o mínimo da dimensão.
**Organização nova não começa ruim: começa sem medida.** Nota baixa por ausência de histórico seria
uma barreira de entrada construída por acidente, e cairia exatamente sobre a OSC pequena que esta
plataforma existe para atender. No banco: `CHECK insufficient_has_no_value`.

### 2.3 Entra fato com ato de terceiro; autodeclaração é contada à parte

Medição validada por organização **diferente**, evidência aceita, documento validado, despesa com
comprovante, aporte confirmado pelas duas pontas, alegação sustentada no confronto determinístico.
Toda dimensão devolve `observations`, `verified_observations` e `self_declared_observations`
separados — a terceira nunca é somada à segunda.

### 2.4 Nada de plano, assinatura ou pagamento

Reafirma a ADR-042 para a reputação. O teste é uma **varredura AST** no módulo: qualquer
identificador ou consulta que mencione `entitlement`, `plan_key`, `subscription`, `invoice`,
`billable`, `price` ou `premium` reprova o teste. Há também o teste que concede plano pago e compara
dimensão por dimensão: nada muda.

### 2.5 Órgão público não recebe nota

`kind = 'government'` recebe **Perfil de Governança e Transparência**: os mesmos fatos em contagem,
sem valor de 0 a 100 e sem faixa comparável. Pontuar ente público é pontuar política pública, e esta
plataforma não tem mandato para isso.

### 2.6 Pessoa física não tem perfil público de reputação

`kind = 'individual'`: `GET /v1/organizations/{id}/reputation` devolve 403
`no_public_profile_for_person` para qualquer terceiro. A própria pessoa vê o seu perfil marcado
`private: true`.

## 3. As seis dimensões

| Código | Mede | Conta como |
|---|---|---|
| `evidence_discipline` | medições validadas **com** evidência sobre medições reportadas | proporção |
| `financial_transparency` | despesa com comprovante; aporte confirmado pelas duas pontas | média das razões disponíveis |
| `claim_integrity` | alegações sustentadas (mais metade das em atenção e das marcadas **aceitas em revisão**) sobre alegações verificadas | proporção |
| `institutional_formality` | documento validado, qualificação verificada e vigente, compliance aprovado | média das razões disponíveis |
| `delivery_record` | marco com evidência aceita; projeto concluído sobre projeto publicado | média das razões disponíveis |
| `contribution_to_others` | atos em que a organização serviu de terceiro para outra | **contagem, sem valor** |

Quatro propriedades que o catálogo declara e os testes verificam:

- **Toda dimensão diz o que NÃO mede.** `what_it_does_not_measure` é `NOT NULL` com mínimo de 20
  caracteres, porque é a parte que some quando alguém resume o indicador numa tela.
- **Proporção, não volume.** Três medições validadas pontuam igual a trezentas. É o que impede a
  reputação de ser um proxy de tamanho.
- **Projeto cancelado não conta contra.** A plataforma não sabe de quem foi a decisão de cancelar,
  então apenas o concluído conta a favor e nada conta contra.
- **`contribution_to_others` não tem valor de 0 a 100**, porque não existe denominador para "quantas
  revisões são muitas". Inventar a escala seria a arbitrariedade que o resto do arquivo evita.

### 3.1 A conta está no código, não em pesos de tabela

Peso numa tabela parece configurável e é, na prática, cálculo escondido: ninguém revisa um número
numa linha. Há uma função por dimensão em `_dimension()`, que aparece em diff e tem teste.

### 3.2 Confiança

`_confidence()` multiplica dois fatores explícitos: **cobertura** (observações, saturando em 3× o
mínimo da dimensão) e **verificação** (quanto das observações tem ato de terceiro, entre 0,5 e 1,0).
Confiança nunca é alta só por volume. A faixa vem de `core/evidence.band()`, a mesma do match e da
prontidão — uma escala de confiança só no produto.

## 4. Linha do tempo

A reputação corrente é **sempre calculada na leitura**. O snapshot existe para mostrar evolução e
para que uma correção não apague o que foi publicado antes dela:

- `reputation_snapshots` é append-only (`forbid_mutation()`);
- a aplicação **não tem INSERT** na tabela — só `app_record_reputation()`, `SECURITY DEFINER`, que
  recusa valor sem observação que o sustente;
- cada ponto carrega `engine_version`, porque comparar pontos de motores diferentes é comparar
  coisas diferentes;
- o job `reputation_timeline` registra um ponto por organização ativa e **pula** quem não tem
  nenhuma observação: linha do tempo de quem não tem base é ruído com aparência de dado.

## 5. Contestação e correção

| Passo | Quem | Onde |
|---|---|---|
| Contestar uma dimensão | a própria organização | `POST /v1/reputation/disputes` |
| Ver a contestação | qualquer pessoa autenticada que leia o perfil | o perfil, ao lado da dimensão |
| Resolver | administração da plataforma | `POST /v1/admin/reputation/disputes/{id}/resolution` |

- A contestação **aberta aparece no perfil**, ao lado da dimensão contestada, não numa fila
  interna: direito de contestar que ninguém vê não é direito.
- A contestação é append-only; a resolução é um fato **novo**, uma por contestação, e a situação é
  derivada por `dispute_status()` — não há coluna de situação para reescrever.
- Resolução que diz ter corrigido precisa dizer **o que mudou** (`what_changed_required`).
- Corrigir produz **ponto novo** na linha do tempo. O que foi publicado antes da correção continua
  legível, e é assim que se prova que a correção aconteceu.
- Ninguém resolve a própria contestação: a política de RLS exige contexto privilegiado para
  escrever a resolução.

## 5.1 Uma trava do banco que pegou um erro do cálculo

Vale registrar porque é o tipo de coisa que normalmente não aparece em relatório. A restrição
`insufficient_has_no_value` recusou uma gravação durante a implementação: havia observações
suficientes e **verificação por terceiro baixa**, e o perfil publicava um valor que a própria faixa
de confiança dizia não sustentar. O banco recusou, a recusa estava certa, e o que foi corrigido foi
o cálculo — não a restrição. O caso virou o teste
`test_a_dimension_with_enough_observations_but_low_verification_publishes_no_value`.

## 6. O que esta fase NÃO faz

- **Não calcula reputação de pessoa física**, nem privadamente além do que a própria pessoa vê.
- **Não pondera gravidade.** Uma alegação marcada pesa como qualquer outra; a plataforma não sabe
  distinguir exagero de erro, e inventar peso seria julgar.
- **Não detecta conluio.** Duas organizações que validam medições uma da outra sobem em
  `contribution_to_others` e em `evidence_discipline`. O sinal existe no banco (quem validou o quê,
  desde a v0.8.0), mas a detecção é dívida declarada, não feito.
- **Não expira o passado.** Observação de três anos atrás pesa como a de ontem; decaimento por
  idade existe em `core/evidence.py` para evidência e **não** está aplicado às dimensões. É a
  dívida mais importante desta fase.
- **Não alimenta nada.** Nenhuma rota de busca, match, recomendação, elegibilidade ou selo consulta
  reputação. Essa é a trava que a FASE 8 (selos) tem de preservar.
