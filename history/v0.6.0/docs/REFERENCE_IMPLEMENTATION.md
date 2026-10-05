# Implementação de referência v0.2

Esta entrega adiciona uma fatia vertical executável, sem alegar que substitui o produto de produção.

## Executar

```bash
./run_local.sh
curl http://localhost:8080/healthz
curl -X POST http://localhost:8080/v1/matches/evaluate \\
  -H 'content-type: application/json' \\
  -d '{"call_status":"open","signals":{"cause_alignment":1,"territory":0.8}}'
```

## Endpoints implementados

- `GET /healthz`
- `POST /v1/matches/evaluate`
- `POST /v1/entitlements`
- `POST /v1/vouchers/redeem` (voucher local de demonstração `DEV-DEMO-2026`; substituir a chave)
- `GET /v1/audit-events`

## Limites explícitos

SQLite local, autenticação ausente, tenant isolation apenas como requisito futuro, sem frontend, sem storage de documentos, sem billing, sem IA/fiscal/compliance de produção. A implementação é adequada para validar contratos e invariantes localmente, não para receber dados reais.
