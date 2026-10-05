# Pacote de publicação, continuidade e segurança

## Conteúdo do release

Este pacote contém o frontend web/PWA em `web/`, o backend/API em `src/impacto/app.py`, os contratos em `openapi.yaml`, testes em `tests/`, migrações de referência em `database/`, adapters de provedores em `src/impacto/providers.py`, CI em `.github/workflows/`, Dockerfile, scripts operacionais e documentação em `docs/`.

## Execução local

```bash
./run_local.sh
# acessar http://localhost:8080
PYTHONPATH=. python3 -m unittest discover -s tests -v
```

Não usar a conta demo nem SQLite para dados reais.

## Publicação Web

1. Provisionar ambiente de produção, domínio, TLS e DNS em conta da organização.
2. Configurar PostgreSQL com a migration `database/postgres/0001_rls.sql` e validar RLS com testes negativos entre tenants.
3. Configurar OIDC/MFA, storage privado S3/KMS, antivírus, e-mail, observabilidade e secrets manager.
4. Executar CI, SAST/SCA/secret scan, testes de integração, carga, restore drill e pentest autorizado.
5. Migrar dados apenas após backup verificado e aprovação do runbook.
6. Publicar primeiro em staging, executar smoke/E2E e promover com rollback preparado.
7. Atualizar `docs/PUBLISHING_CHECKLIST.md` e registrar o estado como `BUILT`, `TESTED`, `SIGNED`, `SUBMITTED` ou `PUBLISHED` somente com evidência.

O estado atual deste pacote é **READY FOR LOCAL VALIDATION**, não `PUBLISHED`.

## Android e iOS

O produto atual é uma PWA responsiva. Não há build nativo assinado neste release. Para criar os apps: escolher React Native/Expo ou wrapper PWA após demonstrar necessidade de push/offline/câmera; criar contas de loja em nome da organização; configurar bundle ID/application ID, certificados em vault, ícones, splash, privacy labels, Data Safety e URL de exclusão de conta; executar testes internos/TestFlight; e somente então submeter.

Não declarar `SIGNED`, `SUBMITTED`, `APPROVED` ou `PUBLISHED` sem evidência das lojas.

## Continuidade operacional

- Backup: `IMPACTO_DB=... ./scripts/backup.sh backups/arquivo.sqlite3`.
- Restauração: `./scripts/restore.sh backups/arquivo.sqlite3 data/restored.sqlite3`.
- Validar `integrity_check=ok` e comparar SHA-256 do artefato.
- Guardar backups em conta/região separada e imutável quando migrar para produção.
- Definir RPO/RTO, responsáveis, contatos de incidente e janela de restore antes de dados reais.
- Manter `DECISIONS.md`, `CHANGELOG.md`, migrations e manifesto versionados.

## Segurança mínima antes de produção

- OIDC e MFA para usuários privilegiados.
- RBAC por função e autorização por objeto.
- RLS PostgreSQL forçada.
- Rate limiting, headers de segurança, TLS e rotação de secrets.
- Upload privado com allowlist, limite, antivírus e URLs temporárias.
- Logs estruturados sem PII desnecessária, métricas, tracing, alertas e health checks.
- SAST, SCA, secret scan, DAST e pentest autorizado.
- Política de retenção, DPA, LGPD, resposta a incidentes e revisão profissional fiscal/compliance.

## Dependências externas e responsabilidade

Gateway de billing, IdP, S3/KMS, antivírus, IA, observabilidade, domínio, contas de loja e certificados não são fornecidos neste ZIP. Eles precisam ser contratados/configurados pelo proprietário. Regras fiscais, termos legais e compliance precisam de revisão profissional; o sistema não os inventa nem os trata como aprovados.
