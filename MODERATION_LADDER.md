# Escada de moderação (v0.16.0)

Medida proporcional, com regra, motivo e direito de contestar. Motor: `backend/impacto/network/enforcement.py` ·
Tabela: `enforcement_actions` · Rotas: `/v1/moderation/*` · Tela: `web/src/pages/moderation.tsx`

O pedido é textual: **"nunca criar punição automática irreversível baseada somente em heurística"**. Abaixo está como
isso virou estrutura e não boa intenção.

## Os dez degraus

| # | Medida | Sev. | Prazo | Efeito prático |
|---|---|---|---|---|
| 1 | Orientação | 1 | — | Registro de orientação, sem restrição. Diz o que mudar antes de qualquer sanção. |
| 2 | Advertência | 2 | — | Fica no histórico e conta na proporcionalidade da próxima medida. |
| 3 | Notificação formal | 3 | — | Prazo para correção, sem restringir o uso. |
| 4 | Restrição parcial | 4 | **exige** | Restringe parte do uso (publicar, propor, enviar recado) mantendo acesso aos próprios dados. |
| 5 | Encaminhamento a autoridade | 5 | — | Dever de comunicar, não punição da plataforma. |
| 6 | Suspensão temporária | 6 | **exige** | Suspende o uso por prazo determinado; dados preservados e acessíveis. |
| 7 | Bloqueio cautelar | 7 | **exige** | Congela operações durante a apuração. Cautelar: não é juízo de mérito. |
| 8 | Desvinculação | 8 | — | Encerra relações ativas com terceiros, para proteger quem está do outro lado. |
| 9 | Cancelamento | 9 | — | Encerra conta/organização, preservando o que a lei exige preservar. |
| 10 | Banimento | 10 | — | Impede novo cadastro. Última medida, nunca a primeira resposta a fato isolado. |

## As sete travas

**1 · Proporcionalidade com degrau.** `escalation_ok()` recusa pular mais de `MAX_JUMP = 2` degraus de severidade
acima da medida mais grave já aplicada ao mesmo alvo. Banimento (10) contra alvo sem histórico é **recusado com 422**.
Há caminho de exceção — `override_reason` — e ele é obrigatoriamente escrito, auditado e visível no histórico: a
exceção existe para o fato grave citado explicitamente, não para contornar a regra em silêncio.

**2 · Regra e motivo obrigatórios.** `rule_ref` e `reason` (≥ 10 caracteres) com CHECK no banco. Medida sem regra é
arbítrio, e a plataforma não **consegue** registrar arbítrio.

**3 · Temporária exige prazo.** CHECK no banco: as três medidas de `NEEDS_END` sem `ends_at` são recusadas.
"Suspenso até nova ordem" não existe aqui.

**4 · Nada é automático.** Não há rota, trabalho agendado ou gatilho que aplique medida por heurística. `apply()`
exige `decided_by`, derivado de `app_uid()` de administrador autenticado. O que a heurística faz é **priorizar a
fila** (`reports.priority`) — nunca decidir. Teste de arquitetura verifica que nenhum caminho automático chama
`apply()`.

**5 · Quem julga a contestação não é quem aplicou.** CHECK no banco: `appeal_decided_by <> decided_by`.

**6 · Reversibilidade.** `lift()` encerra a medida com motivo; `decide_appeal()` pode `overturned` (anula) ou `upheld`
(mantém). `expire_due()` encerra por decurso de prazo. Nenhum estado da escada é terminal sem caminho de volta, exceto
os efeitos que a lei obriga a preservar.

**7 · A identidade de quem denunciou nunca chega ao alvo.** `reports.reporter_anonymous` é verdadeiro por padrão, com
COMMENT na coluna. `target_view()` — a única leitura que o alvo tem — não seleciona nenhuma coluna de denunciante, e
há teste que verifica a ausência.

## As doze categorias de denúncia

`fraud` (fraude ou falsidade) · `abuse` (abuso) · `harassment` (assédio) · `hate_speech` (discurso de ódio) ·
`spam` (spam ou abordagem em massa) · `impersonation` (falsa identidade) · `misinformation` (informação falsa) ·
`privacy` (violação de privacidade) · `intellectual_property` (propriedade intelectual) · `illegal_content`
(conteúdo ilícito) · `child_safety` (risco a criança ou adolescente) · `other` (outro).

`child_safety` e `illegal_content` entram na fila com prioridade máxima por regra fixa, não por heurística.

## Estados de uma medida

`active` → `expired` (prazo) · `lifted` (encerrada com motivo) · `under_appeal` → `upheld` | `overturned`.

## O que o alvo vê

`target_view()` devolve, para a organização alvo: a medida, o rótulo, a severidade, o **efeito em português**, a regra
citada, o motivo, quando começa, quando termina, o estado, e se ainda cabe contestação. Não devolve: quem denunciou,
quantas denúncias houve, o texto das denúncias, nem quem decidiu.

Uma trava específica: a GRANT de coluna deixava o **alvo** escrever `status` — ou seja, anular a própria medida.
GRANT de coluna *adiciona* privilégio e não consegue restringir, então a correção foi um gatilho,
`enforcement_target_guard()`, que permite ao alvo escrever **apenas** os campos de contestação
(`appeal_text`, `appealed_at`) e recusa qualquer outra coluna.

## Limites honestos

* A plataforma **não** faz detecção automática de conteúdo ilícito, discurso de ódio ou fraude. Não há classificador.
  A fila é alimentada por denúncia humana, e priorizada por regra declarada.
* A plataforma **não** comunica autoridade automaticamente. `referral` registra a decisão de encaminhar; o
  encaminhamento em si é ato humano fora do sistema.
* Não há escada aplicável a **pessoa física** fora de organização: o alvo é sempre `organization` ou `user`, e as
  medidas de rede (desvinculação) só fazem sentido no primeiro caso.
