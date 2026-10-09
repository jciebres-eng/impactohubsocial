# Match Engine — v1.1.0 (camada institucional)

Código: `backend/impacto/engines/match/engine.py`; contexto em `services/matching.py` (`inst_context`, `institutional_requirements`). Descrição geral anterior: `docs/MATCH_ENGINE.md`.

## O que mudou na v0.10.0
1. **HARD BLOCKERS explicados.** Requisito institucional obrigatório **não atendido** vira bloqueio com `code`, `message` e `how_to_fix` — o par não é pontuado como "bom", e a razão aparece em `why_not`.
2. **Obrigatório desconhecido** ⇒ `needs_review` (nunca "elegível").
3. **Certificação exigida = qualificação VERIFICADA e vigente.** Mudança de comportamento: antes bastava a certificação declarada em `certifications`; agora declarada **não** satisfaz requisito de certificação. O campo legado `certifications` (PATCH) cria qualificações **declaradas** e nunca apaga existentes.
4. **Natureza jurídica aceita** (edital e perfil do financiador), **maturidade mínima** e **modalidade** entram como requisitos institucionais.
5. Saída: `eligibility` (eligible | needs_review | blocked), `blockers`, `requirements`, `why_match`, `why_not`, `risks`, `missing`, `next_action`, versão do motor e dos pesos.

## O que NÃO faz
Plano contratado **nunca** influencia match nem busca (testado). Pontuação sem dados é "sem dados". Sinais de IA não existem neste motor.
