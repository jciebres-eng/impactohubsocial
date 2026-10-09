# INTEGRATION_PROVIDER_GUIDE — como adicionar uma integração

O núcleo nunca importa um fornecedor. Tudo passa pelos contratos de `backend/impacto/integrations/contracts.py`.

## 1. Novo adapter (REST)
1. Criar `backend/impacto/integrations/adapters/meu_erp.py` herdando `BaseAdapter`:
```python
class MeuErpAdapter(BaseAdapter):
    code = "meu_erp"
    auth_kinds = (AuthKind.API_KEY, AuthKind.BEARER_TOKEN)
    capabilities = {Capability.PULL: CapabilityLevel.CONTRACT_TESTED, ...}
    required_config = ("base_url", "paths")

    def validate_config(self, config): ...      # devolve lista de problemas legíveis
    def health_check(self, ctx): ...            # SOMENTE leitura, nunca escreve
    def pull(self, ctx, entity, since): ...     # devolve AdapterResult com CanonicalRecord
    def push(self, ctx, entity, records): ...
    def handle_webhook(self, ctx, headers, body): ...
```
2. Registrar em `adapters/__init__.py` (`ADAPTERS`).
3. Declarar o provedor em `config/integration_providers.json` com **maturidade honesta** (`scaffolded` se nada foi exercitado). `sync_integration_providers` aplica na migração e **nunca rebaixa** uma maturidade já promovida com evidência.
4. Testar: uma classe nova na suíte com `FakeTransport`, cobrindo configuração inválida, saúde, pull, push, erro temporário, erro permanente e isolamento entre organizações.

## 2. Regras que o adapter deve respeitar
- Todas as chamadas por `ctx.caller.call(...)` — é lá que vivem a guarda de SSRF, o tempo limite, o disjuntor e o traço sem corpo nem segredo.
- Erro externo vira `IntegrationError(code, message, kind="temporary"|"permanent")`. Repetir algo que nunca vai funcionar é defeito.
- `health_check` não escreve nada no sistema externo.
- O adapter **não** lê credencial do banco: recebe o segredo já decifrado em `ctx`.
- O adapter **não** emite evento nem grava job: isso é do hub.
- Nada de acesso direto ao banco do ERP como estratégia (só API/arquivo/fila). Se o cliente insistir, é exceção documentada, não arquitetura.

## 3. SOAP/XML
Usar `xmlsafe.soap_envelope(operation, params, namespace)` e `xmlsafe.parse(...)`. Nunca montar XML com formatação de texto: valores são escapados pela função. `SeniorSapiensAdapter` é o exemplo híbrido (REST para catálogo, SOAP para operações).

## 4. Novo evento de saída
Acrescentar em `events.CATALOG` (código `DOMÍNIO.OBJETO.AÇÃO`), emitir com `events.emit(conn, org_id, tipo, payload, correlation_id=...)` **dentro da transação do fato** (padrão outbox: o evento e o fato caem ou passam juntos). Documentar o payload em `INTEGRATION_HUB.md`.

## 5. Novo mapeamento/transformação
Transformações são um conjunto fechado em `mapping.py` (`none, trim, upper, lower, digits_only, date_iso, date_br, decimal_comma, cents_from_decimal, boolean, enum, split_list`). Para acrescentar, implementar em `apply_transform`, cobrir com teste e documentar. **Nunca** aceitar expressão do cliente: não há `eval`.

## 6. Novo dataset de exportação
Acrescentar em `adapters/bi.py` (`DATASETS`) com colunas fixas e consulta por organização. Sem acesso direto ao banco pelo cliente: exportação gera documento com URL temporária.

## 7. Checklist antes de dizer "pronto"
- [ ] `validate_config` recusa configuração incompleta com mensagem legível
- [ ] credencial só pela abstração; nenhum segredo em log, auditoria, resposta ou teste
- [ ] erro classificado (temporário × permanente)
- [ ] RLS: testes de organização cruzada
- [ ] idempotência na entrada e nos jobs
- [ ] maturidade declarada igual à realidade
- [ ] documentação atualizada (`INTEGRATION_CAPABILITY_MATRIX.md`, `INTEGRATION_INVENTORY.md`)
