# Procedimento de rollback — v0.30.0 → v0.29.0

Vale para a instalação que já aplicou `0070_v0300_evidence_object.sql`. As migrações do IMPACTO são **forward-only** (`impacto/db/migrate.py`
só aplica; não há "down"), portanto o rollback é de **código** com o banco mantido, ou de **banco por restauração de backup**. Nada aqui
foi executado em produção — não existe produção desta versão; o procedimento foi conferido contra o conteúdo da 0070 e o dry-run `impacto_m70`.

## 0. Antes de atualizar (pré-condição do rollback)

1. `pg_dump -Fc` da base (ou snapshot do volume) **antes** de aplicar a 0070, guardado fora do host.
2. Anotar o commit da imagem anterior (`dd2f8c3`, v0.29.0) e o hash da imagem em execução.

## 1. Rollback de código (banco mantido) — o caminho normal

Quando usar: defeito no backend/front da v0.30.0, sem corrupção de dados.

1. Reimplantar a imagem/commit `dd2f8c3` (v0.29.0). O que a 0070 alterou e como o código antigo convive:
   * `evidences`: colunas novas com DEFAULT — o código antigo não as lê nem escreve. **Atenção aos gatilhos novos**, que continuam
     ativos no banco e valem para o código antigo:
     - `evidence_state_guard`: o código antigo só faz `submitted → accepted/rejected/needs_info` (permitidos). Evidências que a
       v0.30.0 deixou em `contested`/`under_review`/`superseded` **não** podem ser revisadas pelo código antigo (o gatilho recusa
       saltos fora do grafo e `superseded` é terminal) — ficam paradas até a reimplantação da v0.30.0;
     - `evidences_rejection_has_reason` (NOT VALID): o código antigo aceita `rejected` sem nota → o banco recusa (409/500 na rota
       antiga). Operadores devem escrever a nota (o que a v0.30.0 já exige na API);
     - conteúdo imutável depois de enviado: o código antigo nunca editava evidência; sem efeito.
   * `evidence_events` e `indicator_method_changes`: só crescem por gatilho; o código antigo não as conhece.
   * `project_indicators.method_change_reason`: o código antigo não altera `method` (não havia rota); sem efeito.
   * `ledger_entries` CHECK: dois tipos a mais; linhas antigas intactas.
2. Verificar `GET /readyz`, `GET /v1/projects/{id}` e `GET /v1/projects/{id}/evidences` com uma conta de teste.
3. O que se perde no período em v0.29.0: `GET /v1/evidences/{id}` (404 na rota), contestação, substituição, dossiê
   (`/projetos/:id/dossie` → "não encontrado"), mudança de método com motivo. Nada é apagado.

## 2. Rollback de banco (restauração) — só se houver corrupção de dados

1. Parar o backend. 2. Restaurar o dump do passo 0 numa base nova e trocar o apontamento. 3. Reimplantar `dd2f8c3`.
4. **Perda:** tudo o que foi escrito após o dump — inclusive evidências, contestações e medições. Último recurso.

## 3. Rollback parcial sem reimplantar

* **Contestação em excesso:** quem revisa decide (`accepted`/`rejected` com motivo); não há como "desligar" a contestação sem
  reimplantar — e desligar silenciosamente tiraria o direito de resposta da executora (por isso não há interruptor).
* **Evidência substituída por engano:** a anterior continua legível; a nova pode ser rejeitada com motivo; não há "des-substituir"
  (terminal por desenho) — envie outra versão.
* **Dossiê com bloco errado:** é leitura; corrija a fonte (evidência, indicador, marco). Nenhum dado nasce no dossiê.

## 4. Como voltar a avançar

Reimplantar a v0.30.0: a 0070 já está registrada (checksum conferido por `migrate.py`); nenhuma migração roda de novo.

## 5. O que NÃO fazer

* Não executar `DROP TABLE evidence_events` / `indicator_method_changes` à mão (FKs, `schema_migrations` com checksum órfão).
* Não `DROP TRIGGER` dos gatilhos novos para "liberar" o código antigo: isso reabriria edição silenciosa de evidência.
* Não apagar linhas de `evidence_events` (append-only por gatilho; é o histórico).
