# Motor de regras fiscais — especificação v0.1

## Posição
O MVP **não calcula economia tributária, não afirma dedutibilidade e não dá parecer**. Mostra: "possível mecanismo a validar" + fontes oficiais + checklist + encaminhamento a especialista.

## Aviso sobre dados
O relatório-fonte cita normas de 2025–2026 (ex.: LC 222/2025, IN MinC 29/2026, Lei 15.513/2026). **Elas não foram verificadas nesta etapa** e podem ter mudado. **Nenhum percentual, limite ou vigência está codificado neste pacote.** Toda regra entra como `pending_review`. **[VALIDAR]**

## Estrutura de uma regra (imutável por versão)
jurisdição · mecanismo · contribuinte · beneficiário · programa · artigo/modalidade · limites/percentuais · condições · vigência (início/fim/transição/revogação) · **fonte (URL oficial, trecho, data de consulta)** · responsável técnico · anexos · pacote de versão (`BR-FED-<ESCOPO>-<ANO>.<NN>`).

## Estados da regra
`draft → pending_review → approved (dupla aprovação) → active → expired/revoked`. Regra sem revisão vigente em produção = 0 (indicador de bloqueio de release). Alerta antes de vencer.

## Rótulos de interface (sempre distintos)
**Regra** (texto oficial citado) · **Estimativa** (informativa, com hipóteses e lacunas) · **Elegibilidade provável** · **Validação profissional necessária**. Nunca juntar em um número único.

## Escopo inicial sugerido (a escolher com especialista) **[VALIDAR]**
1–2 mecanismos reais do piloto. Demais (FIA, Pessoa Idosa, Pronon/Pronas, Audiovisual, Reciclagem, Cultura, Esporte) apenas cadastrados como "a validar".

## Relação com o match
Fiscal **não entra no score**. Só vira filtro determinístico quando fonte, ano-calendário, contribuinte e elegibilidade do projeto estiverem confirmados.

## Testes
Regressão por pacote de versão; property-based em elegibilidade; teste de que regra expirada/revogada nunca é `active`.
