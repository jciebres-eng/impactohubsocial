# Motor de Elegibilidade Institucional — `institutional-eligibility@1.0.0`

Arquivo: `backend/impacto/engines/institutional/eligibility.py`. Puro e determinístico (mesma entrada → mesma saída). Não acessa rede nem IA.

## Pergunta que responde
"Esta organização pode concorrer a **esta** oportunidade?" e "o que falta para ela se tornar elegível?".

## Cinco estados (nunca apenas sim/não)
ELEGÍVEL · PROVAVELMENTE ELEGÍVEL · ELEGIBILIDADE PENDENTE · NÃO ELEGÍVEL · REQUER VALIDAÇÃO PROFISSIONAL.

Invariantes:
1. **Ausência de requisitos/regras jamais produz "elegível"** — produz PENDENTE.
2. Regra de origem legal (`needs_professional_validation`) nunca vira certeza: mesmo tudo comprovado, o estado é REQUER VALIDAÇÃO PROFISSIONAL.
3. Requisito obrigatório desconhecido ⇒ no máximo PENDENTE.
4. Cada requisito retorna `met | unmet | unknown | pending_validation | expired`, com explicação, "como resolver", fonte (citação/URL) e data de consulta.

## Tipos de requisito (conjunto fechado, validado na API)
`legal_nature_in`, `qualification_any`, `qualification_all`, `maturity_min`, `org_status_in`, `document_valid`, `org_age_min`, `cnpj_required`, `compliance_approved`. Tipo desconhecido é recusado — o motor não "adivinha".

## Origem dos requisitos
- Regras **publicadas** (`eligibility_rules`, escopo global/modalidade/edital/financiador).
- Campos do próprio edital (`accepted_legal_natures`, `min_maturity`, modalidade) e do perfil do financiador.
Todo resultado persiste em `eligibility_evaluations` (motor, versão, regras e versões usadas, data).

## Fluxo editorial das regras
DRAFT → REVIEW → APPROVED → PUBLISHED → ARCHIVED. **Quatro olhos**: criador ≠ aprovador. Publicar exige `source_consulted_on`; publicar uma nova versão arquiva a anterior. Regras jurídicas exigem validação profissional marcada. `config/institutional_rules.candidates.json` traz **candidatas em rascunho** (importar ≠ publicar).

## API
`POST /v1/institutional/eligibility` · `GET /v1/institutional/eligibility` (histórico) · `GET /v1/institutional/rules`. Admin: `/v1/admin/institutional/rules*`.

## Limitações
Qualidade depende das regras cadastradas; sem regras publicadas o resultado é PENDENTE. Não substitui o edital nem profissional habilitado.
