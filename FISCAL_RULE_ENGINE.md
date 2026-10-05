# Motor de Regras Fiscais — camadas (v0.10.0)

O motor fiscal (v0.7+, `docs/FISCAL_ENGINE.md`) permanece **dirigido por dados**: nenhuma regra fiscal está embutida no código; regras vêm de `fiscal_rules` com fonte, vigência, confiança e fluxo de aprovação. A v0.10.0 acrescenta `services/institutional.fiscal_layers`, que **separa explicitamente cinco camadas** na resposta, para o usuário nunca confundir uma estimativa com direito:

| Camada | Significado | Pode afirmar benefício? |
|---|---|---|
| ESTIMATIVA | Cálculo aproximado a partir de regra publicada e dados informados | Não — é ordem de grandeza |
| REGRA IDENTIFICADA | Existe regra publicada aplicável (com fonte e data de consulta) | Não — só indica a regra |
| POSSÍVEL ELEGIBILIDADE | Resultado do motor institucional para a oportunidade | Não — "possível" |
| ELEGIBILIDADE DOCUMENTAL | Estado dos documentos exigidos (AUSENTE…VALIDADO) | Não |
| VALIDAÇÃO PROFISSIONAL | Pendente/solicitada a contador/advogado | **Só após validação humana registrada** |

Regras:
- Sem regra publicada ⇒ "Não foi possível confirmar."; sem valor ⇒ sem estimativa.
- Nada de benefício fiscal inventado: o catálogo de regras iniciais continua como **candidatas** (`config/fiscal_rules.candidates.json`) até publicação com 2 aprovadores.
- **Não integrado nesta versão:** a rota de estimativas fiscais não recebe ainda o `osc_org_id` opcional para cruzar com a elegibilidade institucional (pendência registrada).

## v0.10.1 — integração com a rota de estimativas
Resolvido o pendente do v0.10.0: `fiscal-estimates` cruza com a elegibilidade institucional da OSC (apenas alvo OSC). A estimativa continua **não sendo** direito a benefício.
