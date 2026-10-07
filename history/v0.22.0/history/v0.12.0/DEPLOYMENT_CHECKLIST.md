# DEPLOYMENT_CHECKLIST — Web, Google Play e App Store

Marque cada item **com evidência** (link, captura, log). Estados: ☐ pendente · ☑ feito. Nada foi feito pelo release v0.7.0 além de “código pronto”.

## A. Contas e decisões do proprietário (ninguém pode fazer por você)
☐ Razão social/CNPJ do operador · ☐ nome/marca (busca INPI) · ☐ domínio e DNS · ☐ provedor de nuvem/região (Brasil recomendado) · ☐ conta Stripe (ou outro) · ☐ provedor SMTP · ☐ provedor de IA (ou manter local) · ☐ API de CNPJ e chave Portal da Transparência · ☐ DPO/encarregado · ☐ advogado (termos, privacidade, assinatura, aportes) · ☐ tributarista (regras fiscais) · ☐ preços dos planos.

## B. Infraestrutura
☐ PostgreSQL 16 gerenciado, rede privada, backup/PITR · ☐ papéis `impacto_owner`/`impacto_app` (`infra/db/bootstrap.sql`) · ☐ bucket S3 privado (sem acesso público, criptografia) · ☐ ClamAV · ☐ cofre de segredos · ☐ proxy TLS (`infra/nginx/impacto.conf`) · ☐ egress restrito · ☐ monitoramento/alertas.

## C. Configuração (`.env.example` → ambiente, nunca em git)
☐ `python -m impacto.cli gen-secrets` · ☐ `IMPACTO_ENV=production` · ☐ `PUBLIC_BASE_URL` https · ☐ `COOKIE_SECURE=true` · ☐ `MAIL_PROVIDER=smtp` · ☐ `STORAGE_PROVIDER=s3` · ☐ `ANTIVIRUS_PROVIDER=clamd` · ☐ `ALLOW_UNSCANNED_DOWNLOADS=false` · ☐ `IMPACTO_SEED_DEMO` ausente · ☐ boot sem erros de `config.validate`.

## D. Build, testes e liberação (Web)
☐ `make test` verde no CI (Postgres de serviço) · ☐ `npx tsc -p tsconfig.json --noEmit` com tipos oficiais · ☐ `pip-audit` / `npm audit` sem críticos · ☐ `docker build` + teste fail-fast · ☐ migrações aplicadas em homologação · ☐ restore testado (`scripts/restore_test.sh`) · ☐ smoke: cadastro → e-mail → login → MFA admin · ☐ deploy · ☐ `/healthz` `/readyz` · ☐ Lighthouse/axe · ☐ **Publicado (Web)**.

## E. Google Play (Android)
☐ Conta Google Play Console (taxa única) + verificação · ☐ `IMPACTO_API_BASE` de produção; `CORS_ORIGINS` com origens do app · ☐ `bash mobile/setup.sh` · ☐ trocar `appId` (`web/capacitor.config.json`) · ☐ keystore de upload (fora do git) + Play App Signing · ☐ `assetlinks.json` com SHA-256 em `/.well-known/` · ☐ armazenamento seguro de tokens · ☐ `./gradlew bundleRelease` (AAB) · ☐ testar em dispositivo · ☐ ficha da loja (descrição, capturas, ícone 512, feature graphic) · ☐ **Data safety** · ☐ política de privacidade pública · ☐ classificação de conteúdo · ☐ teste fechado (exigido a contas novas) · ☐ envio para revisão (**SUBMITTED**) · ☐ aprovação (**APPROVED**) · ☐ **PUBLISHED**.

## F. App Store (iOS)
☐ Apple Developer Program · ☐ macOS + Xcode · ☐ Bundle ID, certificados e perfis · ☐ `apple-app-site-association` com Team ID · ☐ Capacitor `cap add ios`, ícones/launch · ☐ **App Privacy** (labels) · ☐ política de privacidade · ☐ exclusão de conta no app (existe: `POST /v1/privacy/delete-account`) · ☐ conta de demonstração para revisão · ☐ política de compra: assinaturas dentro do app podem exigir In‑App Purchase — decidir (web-only ou IAP) · ☐ TestFlight · ☐ Archive/assinatura (**SIGNED**) · ☐ submissão · ☐ aprovação · ☐ **PUBLISHED**.

## G. Pós-publicação
☐ Monitorar erros/latência/filas · ☐ rotina de backup e restore · ☐ rotação de segredos · ☐ revisão trimestral das regras fiscais · ☐ resposta a incidentes (ANPD) · ☐ calibrar match com dados reais.

## G. Camada institucional (v0.10.0)
☐ Aplicar `0006_v0100_institutional.sql` em homologação e conferir `schema_migrations` · ☐ revisão jurídica dos catálogos iniciais (`needs_professional_validation`) · ☐ importar candidatas (`/v1/admin/institutional/rules/import-candidates`) e **publicar só o que tiver fonte consultada e 2 aprovadores** · ☐ calibrar `config/institutional_maturity.json` com dados reais · ☐ definir equipe e SLA da fila de qualificações/documentos · ☐ definir retenção de documentos institucionais (LGPD) · ☐ canal de revisão humana para contestação de elegibilidade/situação · ☐ comunicar a mudança: certificação exigida em edital só vale **verificada**

