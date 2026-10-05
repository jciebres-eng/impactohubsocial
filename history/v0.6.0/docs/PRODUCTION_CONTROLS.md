# Controles de produção — v0.4

## Resolvido localmente

A aplicação agora possui contratos de provider para IA, storage, antivirus, billing e notificações; storage local privado em quarentena; scanner local por allowlist/hash; billing sandbox com assinatura HMAC; backup SQLite com `integrity_check`; restauração; CI GitHub Actions; varredura local de segredos; migração PostgreSQL com RLS; e configuração `.env.example` sem credenciais.

## O que permanece dependente de ambiente externo

**OIDC/MFA real:** requer IdP, client ID/secret e política de recuperação. **S3/KMS:** requer bucket, região, chaves e IAM. **Antivírus completo:** requer ClamAV/serviço gerenciado. **Billing:** requer gateway, webhooks públicos e contrato. **IA:** requer provedor, política de retenção e chave. **Fiscal/compliance:** requer especialista e fontes oficiais. **Observabilidade:** requer endpoint OTEL/Sentry e alertas. **Pentest:** exige profissional/escopo autorizado. **Publicação:** exige domínio, contas de loja, certificados e aprovação das lojas.

Nenhuma dessas dependências pode ser legitimamente inventada ou marcada como concluída sem as credenciais, contratos ou validações correspondentes.
