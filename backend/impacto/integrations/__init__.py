"""INTEGRATION HUB — fronteira entre o núcleo da IMPACTO e sistemas externos.

O núcleo NUNCA importa fornecedor: depende dos contratos deste pacote (`contracts.py`). Cada fornecedor é um adapter
registrado em `adapters/` que traduz entre o modelo canônico da IMPACTO e o formato externo.

Reutiliza, de propósito, o que já existia: `adapters/http_client.py` (guarda de SSRF e retries), `defusedxml` (XXE),
`security/crypto.FieldCipher` (cifra de campo, já usada no MFA), `services/documents` (validação de arquivo),
`services/audit` (auditoria), `observability` (logs com redação, correlação) e RLS por organização.
"""
