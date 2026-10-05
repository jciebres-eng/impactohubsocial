# Fiscal Engine — `fiscal-engine@1.0.0`

Código: `backend/impacto/engines/fiscal/engine.py`; regras: tabela `fiscal_rules`; administração: `/v1/admin/fiscal-rules*`.

## Princípio
**Nenhuma legislação é presumida.** O motor só avalia regras com `status = approved` **e** vigentes na data de referência.
A aprovação exige **dois revisores distintos** (CHECK no banco), fonte oficial citada e data de consulta.
O arquivo `config/fiscal_rules.candidates.json` traz 5 regras **candidatas em rascunho** (FIA/ECA art. 260, Fundo do Idoso,
Rouanet, Lei de Incentivo ao Esporte, PRONON); são carregadas como `draft`, **não produzem nenhum resultado** até aprovação humana,
e vários percentuais estão `null` de propósito (`[VALIDAR]`).

## Saída — quatro rótulos sempre separados
| Rótulo | Conteúdo |
|---|---|
| `REGRA` | código, versão, nome, mecanismo, jurisdição, citação da fonte, URL, vigência, nota de limite |
| `ELEGIBILIDADE PROVÁVEL` | `provavel | improvavel | indeterminada` + motivos (regime, UF, causa do projeto, requisitos não verificáveis) |
| `ESTIMATIVA` | teto de dedução = limite % × IR devido **informado pela empresa**; só existe se o limite foi validado; nunca "economia garantida"; informa grupo de limite combinado |
| `VALIDAÇÃO PROFISSIONAL` | `required: true`, sempre |
Mais `checklist[]` de requisitos (`a_verificar`) e `disclaimer` (não é aconselhamento tributário).

## Separação do Match
O fiscal **não entra** no score de compatibilidade (ADR-011). É exibido em tela própria (Incentivos fiscais) e restrito ao plano com `fiscal.estimates`.

## Fluxo de governança de regra
`draft` → `pending_review` → `approved` (dois revisores distintos `approved_by_1 ≠ approved_by_2`; fonte, `source_consulted_on`, `effective_from/to`) → `retired`. Tudo auditado.

## Pendências (dependem de profissional tributarista)
Validar e aprovar as regras candidatas; modelar regras estaduais/municipais e limites combinados; documentar vigências.
Sem isso, a tela fiscal exibirá "nenhuma regra aprovada" — comportamento correto.
