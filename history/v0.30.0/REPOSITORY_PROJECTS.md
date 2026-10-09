# Banco de Ideias / Projetos × Camada Institucional (v0.10.0)

Evolui `SOLUTION_LIBRARY.md` (v0.9.0). Mudanças:

- **Propriedade intelectual e confidencialidade** (por solução): `ownership_type` (autor, organização, coautoria, instituição, terceiro, desconhecido), `rights_holder`, `confidentiality` (pública, compartilhável, sob solicitação, confidencial, uso restrito), `authorization_publish`, `authorization_contact`, `ip_notes`, `legal_requirements`, `compatible_modalities`.
- **Portão de publicação:** só publica com titularidade declarada e autorização de publicação; a resposta traz aviso: a plataforma **não verifica** a titularidade nem concede licença além da escolhida.
- **Rótulos de compartilhamento** nos cartões (`sharing_label`) e **acesso limitado** (`access.level = summary_only`) quando o conteúdo completo depende de autorização do autor.
- **Proponente** em cada resultado: natureza jurídica declarada e quantidade de qualificações **verificadas** (sem expor dados privados).
- **Prontidão para financiamento** (`engines/institutional/readiness.py`): lista de critérios `met/unmet` (valor necessário, orçamento, metas/cronograma, resultados, evidência aceita, titularidade, modalidades, situação do proponente, qualificações). É **indicador de preenchimento**, não aprovação.
- **Busca:** filtros por natureza jurídica, qualificações verificadas, modalidades, compartilhamento e "prontas para financiamento"; interpretação de intenção continua sem IA.
- **Necessidades do proponente** (`/v1/institutional/needs`): financiamento, parceria, voluntariado etc., persistidas.
- Resultado nunca prometido: "pode participar" ≠ "vai receber".

## v0.10.1
Novos: `backend/impacto/api/institutional_extra_routes.py`, `engines/institutional/{persona,formalization}.py`, `config/formalization_path.json`, `migrations/0007_*.sql`, `web/src/pages/institution_extra.tsx`, `tests/test_v0101_institutional.py`, `tests/test_e2e_v0101.py`.
