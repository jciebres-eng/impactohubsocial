# Procedimento de rollback — v0.28.0 → v0.27.0

Vale para a instalação que já aplicou `0068_v0280_ai_usage_control.sql`. As migrações do IMPACTO são
**forward-only** (`impacto/db/migrate.py` só aplica; não há "down"), portanto o rollback é de
**código** com o banco mantido, ou de **banco por restauração de backup**. Nada aqui foi executado em
produção — não existe produção desta versão; o procedimento foi conferido contra o conteúdo da 0068
(o que ela cria e o que ela altera) e contra o dry-run `impacto_m68`.

## 0. Antes de atualizar (pré-condição do rollback)

1. `pg_dump -Fc` da base (ou snapshot do volume) **antes** de aplicar a 0068, guardado fora do host.
2. Anotar o commit da imagem anterior (`227c9aa`, v0.27.0) e o hash da imagem em execução.
3. Confirmar que `PAYMENT_WEBHOOK_SECRET` está **vazio** até haver provedor (o webhook responde 404 e
   nada é creditado; não há o que reverter de pagamentos).

## 1. Rollback de código (banco mantido) — o caminho normal

Quando usar: defeito no backend/front da v0.28.0, sem corrupção de dados.

1. Reimplantar a imagem/commit `227c9aa` (v0.27.0). O backend da v0.27.0 **não** conhece as tabelas
   novas e não as toca; a migração 0068 fica registrada em `schema_migrations` e as tabelas ficam
   paradas. O que a 0068 alterou em tabelas pré-existentes é compatível com o código antigo:
   * `ai_credit_ledger`: colunas novas com DEFAULT (`bucket = 'promotional'`), `expires_at` e
     `execution_id` nulos; a função `ai_credit_consume(...)` da 0058 continua existindo com a mesma
     assinatura (virou invólucro). O código v0.27.0 nunca a chamava.
   * `platform_charges`: o CHECK de `kind` só ganhou o valor `ai_credits`; cobranças antigas intactas.
   * `charge_requires_authorization` v3: continua aceitando o que a v2 aceitava (contrato aceito ou
     acordo assinado); a cláusula nova só se aplica a `kind = 'ai_credits'`.
   * `monetization_rules`: a linha `ai.credits_prepaid` fica (`active = false`); `test_v0150_upgrade`
     da v0.27.0 fixa 10 regras e passaria a contar 11 — é a única diferença visível para o código
     antigo e não afeta a execução (nenhuma regra ativa).
2. Verificar `GET /readyz` e `GET /v1/me` com uma conta de teste; abrir `/projetos` e `/conta`.
3. Comunicar aos usuários do piloto que a Central de IA (`/ia`) voltará a ser a tela de orçamento
   da v0.27.0; créditos promocionais concedidos no piloto permanecem no razão (append-only) e voltam a
   valer na reimplantação da v0.28.0.

O que se perde no período em v0.27.0: prévia/execução com estado, Central de IA, similaridade,
pedidos de crédito, patrocínio, painel financeiro. Nada é apagado.

## 2. Rollback de banco (restauração) — só se houver corrupção de dados

Quando usar: dado inconsistente que o código antigo não tolera (não foi observado em nenhum teste;
o razão e as execuções são append-only ou guardados por gatilho).

1. Parar o backend.
2. Restaurar o dump do passo 0 (`pg_restore -c` numa base nova e trocar o apontamento, ou restaurar
   o snapshot do volume).
3. Reimplantar `227c9aa`.
4. **Perda:** tudo o que foi escrito após o dump — inclusive dados que não são de IA. Por isso este
   caminho é o último; prefira o §1.

## 3. Rollback parcial sem reimplantar (desligar a IA)

* `AI_PROVIDER=disabled` desliga as chamadas a modelo; o motor local de similaridade continua.
* Para parar uma operação sem reimplantar, publique uma versão nova dela no catálogo com
  `status = "planned"` (`POST /v1/admin/ai/operations`, permissão `finance.approve`): a versão
  anterior é aposentada, toda prévia passa a responder 501 (declarada, não executável), execuções já
  autorizadas terminam com a versão e o preço com que foram autorizadas; nada novo é cobrado.
  (`status = "retired"` numa versão nova responde 410 `ai_operation_retired`.)
* Para parar pedidos de crédito: deixar a regra `ai.credits_prepaid` inativa (já está) — pedidos só
  nascem em modo piloto, sem dinheiro.

## 4. Como voltar a avançar

Reimplantar a v0.28.0: a 0068 já está registrada (checksum conferido por `migrate.py`); nenhuma
migração roda de novo; os dados criados no piloto continuam válidos.

## 5. O que NÃO fazer

* Não executar `DROP TABLE` das tabelas da 0068 à mão: `ai_credit_ledger.execution_id` tem FK para
  `ai_executions`, `polymorphic_refs` e `audit_action_categories` têm linhas que apontam para elas, e
  `schema_migrations` ficaria com um checksum de algo que não existe mais — a próxima subida da
  v0.28.0 falharia.
* Não apagar linhas do razão de créditos (gatilho `forbid_mutation`; é o livro).
