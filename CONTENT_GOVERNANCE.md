# CONTENT_GOVERNANCE — governança editorial (v0.12.0)

| Regra | Onde é garantida |
|---|---|
| Fluxo `draft → review → approved → published → archived` | `kb.transition` + CHECK/trigger; transições fora da tabela → 409 |
| **Quatro olhos**: quem criou não aprova (nem administrador) | CHECK `approved_by ≠ author_id` **no banco** (teste faz UPDATE direto e falha) + 403 `four_eyes` na API |
| Aprovar/publicar/arquivar exige papel `reviewer` (ou administrador) | `_transition` |
| Versões **imutáveis** depois da revisão | trigger; editar versão não-rascunho → 409; alterar = nova versão |
| Conteúdo regulatório exige **fonte e data** | CHECK `regulatory ⇒ source+date`; `valid_until` vencido ⇒ “Revisão necessária” |
| Revisão periódica | `review_every_days` + `last_reviewed_at`; painel “Revisão em atraso”; “Marcar revisado” fica no histórico |
| Histórico de quem fez o quê | `content_history` (de→para, autor, nota, data) |
| Papéis internos | `staff_roles` (`editor`, `reviewer`, `support`); só administrador concede; MFA exigido |
| Rotulagem | origem + selo “Exemplo” (`demo`) em todo item; exemplos nunca indexáveis |
| Feedback | “Ajudou?”, motivo, FAQs com baixa resolução, lacunas de busca → fila editorial |

**Limites:** administradores da plataforma, quando agindo em modo administrativo, têm privilégio amplo no banco; os manipuladores só tocam o domínio da Central, mas isso é **disciplina de código revisada**, não barreira de banco. Os papéis `editor/reviewer/support` hoje são concedidos a contas de organização comuns com MFA (o painel é acessado como administração) — a separação de contas internas é decisão operacional pendente. Não há workflow de comentários por trecho nem agendamento de publicação.
