# Responsabilidade designada — FASE 9 da v0.18.0

> `backend/migrations/0031_v0180_responsibility.sql`,
> `backend/impacto/impact/responsibility.py`, `backend/tests/test_v0180_responsibility.py`.

## 1. Por que é separado da assinatura

A assinatura (v0.14.0) amarra uma **pessoa** a um **conteúdo** (`subject_sha256`) e responde "quem
conferiu este texto exato". A responsabilidade responde outra pergunta: **"quem responde por esta
decisão, em que papel, em que escopo e em que período"**.

Misturar as duas produz os dois erros clássicos: documento assinado por quem não tinha competência
para decidir, e decisão tomada por quem tinha competência mas sem registro nenhum. Por isso
`responsibility_decisions.signature_id` é **opcional nos dois sentidos**: existe decisão sem
assinatura (registro de responsabilidade) e assinatura sem decisão (conferência de conteúdo).

## 2. O modelo: responsável × papel × escopo × período × decisão × versão

```
responsibility_roles         (8 papéis, cada um com o que NÃO responde)
        │
responsibility_assignments   (org × papel × escopo × sujeito × pessoa × período × base do mandato)
        │
responsibility_decisions     (tipo × declaração × documento+VERSÃO × segunda confirmação × data)
        │
responsibility_decision_kinds (6 tipos; `requires_two` é quatro-olhos declarado em DADO)
```

Os oito papéis: coordenação do projeto, responsabilidade técnica, responsabilidade financeira,
representação legal, encarregado de dados pessoais, validação de medição, titularidade do programa,
responsabilidade pelo documento. **Cada um declara o que não responde** — é a parte que desaparece
quando alguém lê só o nome do papel.

## 3. As travas, todas no banco

| Trava | Como | Por quê |
|---|---|---|
| Designação não é reescrita | `responsibility_end_only()` | reescrever apagaria quem respondia **no dia do fato** |
| Um papel por escopo tem um responsável corrente | `ux_responsibility_current` (índice parcial) | dois responsáveis pelo mesmo papel é ninguém responsável |
| Encerrar exige motivo | `ended_has_reason` | responsabilidade não se transfere em silêncio |
| Encerramento não muda de data | `responsibility_end_only()` | a data do encerramento é o que delimita o período |
| O papel só vale nos escopos dele | `responsibility_scope_guard()` | "representação legal do projeto" não existe |
| Decisão fora do período é recusada | `responsibility_decision_guard()` | quem respondia ontem não decide hoje, e quem responde hoje não decide por ontem |
| Quatro-olhos exige pessoas diferentes | mesmo gatilho | a mesma pessoa em dois papéis não é dupla conferência |
| Decisão sobre documento é sobre uma VERSÃO | mesmo gatilho | decisão sobre "o documento" é decisão sobre alvo que muda depois |
| Documento tem de ser da organização | mesmo gatilho | — |
| Decisão é append-only | `forbid_mutation()` | — |

## 4. Pessoa externa entra por nome, sem CPF

Consultora, avaliadora externa, contadora terceirizada: entram com `external_name` +
`external_note`. **Não existe coluna de CPF, RG ou documento** nesta tabela, e um teste lê
`information_schema` para garantir que não apareça. O registro de quem respondeu não precisa do
número do documento, e guardá-lo aqui criaria dado pessoal sem necessidade (minimização, LGPD).

Pessoa da plataforma precisa ser **membro da organização**; quem é de fora entra como pessoa
externa. Isso evita o cadastro-fantasma de alguém que nunca aceitou nada.

## 5. Ausência de responsável é informação

`GET /v1/responsibility/current` devolve duas listas: quem responde e **quais papéis estão sem
responsável**. Papel vago aparece com o que ele responderia, em vez de ficar como espaço em branco
na tela — ausência de responsável é informação, não lacuna de interface.

## 6. Rotas

| Método | Rota | Para quê |
|---|---|---|
| GET | `/v1/responsibility/roles` | papéis, limites e tipos de decisão (com quatro-olhos) |
| POST | `/v1/responsibility/assignments` | designa |
| POST | `/v1/responsibility/assignments/{id}/end` | encerra com motivo |
| GET | `/v1/responsibility/current` | quem responde agora + papéis vagos |
| GET | `/v1/responsibility/history` | histórico com períodos e motivos |
| GET | `/v1/responsibility/mine` | o que eu respondo e o que respondi |
| POST | `/v1/responsibility/decisions` | registra decisão (documento + versão, quatro-olhos) |
| GET | `/v1/responsibility/decisions` | decisões com papel, pessoa e segunda confirmação |

Quem tem aporte no projeto lê as designações dele: saber quem responde pelo projeto que você
financia é o mínimo.

## 7. O que esta fase NÃO faz

- **Não cria poder de representação.** Designar `legal_representative` aqui não substitui estatuto,
  ata, procuração ou contrato social, e o catálogo diz isso na própria linha do papel.
- **Não exige credencial profissional.** Responsabilidade técnica não confere registro em conselho;
  a camada de credenciais (v0.14.0) existe à parte e não está amarrada a esta.
- **Não bloqueia ação por falta de responsável.** Nenhuma rota do produto hoje exige designação
  para funcionar. Amarrar, por exemplo, publicação de relatório à existência de
  `authorization_to_publish` é a continuação natural — e é dívida declarada, não feito.
- **Não notifica a pessoa designada.** A notificação existe no produto (v0.16.0) e não foi ligada
  aqui.
