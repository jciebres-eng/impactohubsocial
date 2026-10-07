# MVP local executável — v0.3

## Implementado

- Painel web responsivo em `web/index.html`.
- Manifesto PWA e service worker.
- Cadastro de organização e usuário.
- Login com PBKDF2-HMAC-SHA256, salt individual e sessão bearer expirada.
- Isolamento lógico por `org_id` em todas as consultas de negócio.
- Papéis `admin`, `owner` e `analyst`.
- CRUD de programas e oportunidades.
- Registro de metadados e SHA-256 de documentos.
- Avaliação de match persistida com blockers, score, confiança, lacunas, riscos e próxima ação.
- Vouchers com HMAC, uso único, entitlements e ledger encadeado.
- Visão geral, programas, oportunidades, match e documentos no painel.
- Endpoint fiscal deliberadamente bloqueado em `pending_review`.
- Health check e endpoint de visão administrativa.

## Executar

```bash
cp .env.example .env # preencher uma chave aleatória em ambientes reais
./run_local.sh
# abrir http://localhost:8080
```

Conta local de demonstração: `admin@impacto.local` / `Admin@123`. Troque/remova essa conta antes de qualquer uso real.

## Testes

```bash
PYTHONPATH=. python3 -m unittest discover -s tests -v
```

Há também um cenário HTTP end-to-end validado manualmente para login → programa → oportunidade → match → documento → auditoria.

## Limitações não mascaradas

SQLite é adequado apenas para demonstração e desenvolvimento local. Ainda faltam PostgreSQL/RLS real, OIDC/MFA, RBAC completo por objeto, upload binário privado com antivírus, storage S3/KMS, jobs, e-mail, IA, billing, compliance/KYB, regras fiscais aprovadas, observabilidade, backup/restore testado, CI/CD e pentest. O painel não deve receber dados reais.
