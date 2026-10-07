# Impact Ledger (trilha de integridade)

Cadeia: oportunidade → submissão → revisão → decisão → compromisso → execução → entrega do prestador → evidência → aceite → resultado → prestação de contas.

## Implementação alvo
Tabela `audit_event` append-only: `id, tenant_id, actor_id, action, object_type, object_id, payload_hash, prev_hash, event_hash, at`. `event_hash = SHA-256(prev_hash || canonical(payload))`. Privilégios UPDATE/DELETE revogados; verificação periódica da cadeia; âncoras diárias do último hash em armazenamento externo imutável (WORM).

## Garantias e limites
Hash prova que o arquivo **não mudou** após o registro; **não prova** que o conteúdo era verdadeiro. Assinatura eletrônica apenas onde necessária, com autoria humana identificável e análise jurídica do tipo de ato **[VALIDAR]**. IA não assina. Correção = nova versão (histórico preservado).

## Blockchain
Não adotado (ADR-012): entidade única controla o banco; ganho inexistente.

## Eventos de billing no ledger
Emissão, resgate, revogação de voucher e concessão de gratuidade geram `audit_event`.
