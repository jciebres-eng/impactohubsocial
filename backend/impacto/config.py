"""Configuração por ambiente (development | test | staging | production).

Regras *secure by default*:
* Em staging/production, segredos obrigatórios ausentes ou com valor de exemplo impedem a inicialização.
* Seeds de demonstração nunca rodam fora de development/test.
* Provedores "sandbox"/"console" só são aceitos fora de production.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # raiz do repositório
VERSION = (ROOT / "VERSION").read_text().strip() if (ROOT / "VERSION").exists() else "0.0.0"

_PLACEHOLDER_MARKERS = ("change-me", "changeme", "gere-fora", "example", "exemplo", "xxx")


class ConfigError(RuntimeError):
    pass


def _env(name: str, default: str | None = None) -> str | None:
    v = os.getenv(name)
    return v if v not in (None, "") else default


def _bool(name: str, default: bool = False) -> bool:
    v = _env(name)
    return default if v is None else v.strip().lower() in ("1", "true", "yes", "on")


def _int(name: str, default: int) -> int:
    v = _env(name)
    return default if v is None else int(v)


def _list(name: str) -> list[str]:
    v = _env(name, "") or ""
    return [x.strip() for x in v.split(",") if x.strip()]


@dataclass
class Settings:
    env: str = "development"
    version: str = VERSION
    port: int = 8080
    public_base_url: str = "http://localhost:8080"
    database_url: str = ""
    database_pool_size: int = 10
    secret_key: str = ""                 # HMAC de URLs assinadas, CSRF etc.
    voucher_hmac_key: str = ""
    field_encryption_key: str = ""       # Fernet (MFA secrets)
    access_token_ttl: int = 900           # 15 min
    refresh_token_ttl: int = 30 * 86400   # 30 dias (vida de UMA credencial de renovação)
    # v0.23.0 — os dois prazos que faltavam. `refresh_token_ttl` era contado da ÚLTIMA rotação, o
    # que significa que uma sessão em uso nunca vencia: 30 dias a partir de agora, sempre.
    session_absolute_ttl: int = 30 * 86400    # idade máxima da FAMÍLIA de sessão
    session_idle_ttl: int = 14 * 86400        # inatividade máxima antes de pedir login de novo
    cookie_secure: bool = True
    cors_origins: list[str] = field(default_factory=list)
    trust_proxy_headers: bool = False
    # v0.35.0 (auditoria, AUTH-02): quantos proxies CONFIÁVEIS acrescentam ao X-Forwarded-For (o IP do cliente é o
    # N-ésimo a partir da DIREITA; o primeiro valor é quem faz o pedido que escreve). E, opcionalmente, um cabeçalho
    # que a borda sobrescreve (ex.: cf-connecting-ip) — só se a origem não for alcançável sem passar pela borda.
    trusted_proxy_hops: int = 1
    client_ip_header: str = ""
    max_body_bytes: int = 1_048_576
    max_upload_bytes: int = 15 * 1_048_576
    login_max_attempts: int = 8
    login_window_seconds: int = 900
    require_mfa_for_admins: bool = True
    require_email_verification: bool = True
    seed_demo: bool = False
    # Provedores
    mail_provider: str = "console"        # console | smtp
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "no-reply@localhost"
    storage_provider: str = "local"       # local | s3
    storage_local_dir: str = str(ROOT / "data" / "storage")

    # ---- operação (v0.19.0): backup agendado e canário de e-mail.
    #: Destino dos dumps. Vazio = backup NÃO roda, e a tarefa registra `not_configured` em vez de
    #: deixar a ausência de registro parecer sucesso.
    backup_dir: str = ""
    #: DSN com papel capaz de ler tudo (pg_dump). Vazio = não roda.
    backup_database_url: str = ""
    backup_interval_hours: int = 24
    backup_keep: int = 14
    #: Cópia externa: comando que recebe o arquivo como $1. Vazio = só cópia local, declarado como tal.
    backup_offsite_cmd: str = ""
    #: Endereço do canário. Vazio = canário não roda.
    email_canary_to: str = ""
    email_canary_interval_minutes: int = 60
    s3_endpoint: str = ""
    s3_region: str = "us-east-1"
    s3_bucket: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    antivirus_provider: str = "none"      # none | clamd
    clamd_host: str = "127.0.0.1"
    clamd_port: int = 3310
    allow_unscanned_downloads: bool = False
    # v0.27.0 (ADR-341): não há assinatura nem provedor de cobrança recorrente. As chaves do Stripe ficam
    # apenas para `economics/payments.py` dizer se há provedor REAL configurado (sem chave = simulado).
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    payment_webhook_secret: str = ""      # v0.28.0: HMAC dos webhooks de pagamento em /v1/webhooks/payments/{provider}
    # v0.33.0 — doações e campanhas: padrões SEGUROS. Nada de cobrança real, split, recorrência ou retenção sem decisão.
    donations_enabled: bool = True                 # módulo ligado (só provedor sandbox existe)
    campaign_publication_enabled: bool = True      # publicar campanhas (exige revisão + beneficiário verificado)
    live_payment_provider_enabled: bool = False    # provedor real: NUNCA sem adaptador, credencial no cofre e ADR
    split_enabled: bool = False                    # split no provedor: exige contrato e KYB de subconta
    recurring_donations_enabled: bool = False      # recorrência: exige instrumento do provedor e consentimento
    risk_hold_enabled: bool = False                # payout_hold: só se o contrato com o provedor permitir
    # v0.27.0 — chave PIX da própria plataforma para a linha "infraestrutura e inteligência" das instruções de repasse.
    # Vazia = "NÃO CONFIGURADA": a instrução sai sem chave e diz isso. Nunca é usada para mover dinheiro.
    platform_pix_key: str = ""
    platform_pix_key_type: str = ""
    ai_provider: str = "local"            # local | anthropic | openai_compatible | disabled
    ai_base_url: str = ""
    ai_api_key: str = ""
    ai_model: str = ""
    ai_timeout_seconds: int = 30
    ai_max_input_chars: int = 12000
    cnpj_lookup_url: str = ""             # ex.: https://brasilapi.com.br/api/cnpj/v1/{cnpj}
    oidc_issuer: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_redirect_uri: str = ""
    metrics_token: str = ""
    log_level: str = "INFO"
    terms_version: str = "2026-10-draft"
    privacy_version: str = "2026-10-draft"
    web_dist_dir: str = str(ROOT / "web" / "dist")

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def is_hardened(self) -> bool:
        return self.env in ("staging", "production")


def load_settings() -> Settings:
    env = (_env("IMPACTO_ENV", "development") or "development").lower()
    if env not in ("development", "test", "staging", "production"):
        raise ConfigError(f"IMPACTO_ENV inválido: {env}")
    hardened = env in ("staging", "production")
    s = Settings(
        env=env,
        port=_int("PORT", 8080),
        public_base_url=_env("PUBLIC_BASE_URL", "http://localhost:8080"),
        database_url=_env("DATABASE_URL", "") or "",
        database_pool_size=_int("DATABASE_POOL_SIZE", 10),
        secret_key=_env("SECRET_KEY", "dev-only-secret-key-change-me" if not hardened else "") or "",
        voucher_hmac_key=_env("VOUCHER_HMAC_KEY", "dev-only-voucher-key-change-me" if not hardened else "") or "",
        field_encryption_key=_env("FIELD_ENCRYPTION_KEY", "") or "",
        access_token_ttl=_int("ACCESS_TOKEN_TTL_SECONDS", 900),
        refresh_token_ttl=_int("REFRESH_TOKEN_TTL_SECONDS", 30 * 86400),
        session_absolute_ttl=_int("SESSION_ABSOLUTE_TTL_SECONDS", 30 * 86400),
        session_idle_ttl=_int("SESSION_IDLE_TTL_SECONDS", 14 * 86400),
        cookie_secure=_bool("COOKIE_SECURE", hardened),
        cors_origins=_list("CORS_ORIGINS"),
        trust_proxy_headers=_bool("TRUST_PROXY_HEADERS", False),
        trusted_proxy_hops=max(1, int(_env("TRUSTED_PROXY_HOPS", "1") or "1")),
        client_ip_header=(_env("CLIENT_IP_HEADER", "") or "").strip().lower(),
        max_body_bytes=_int("MAX_BODY_BYTES", 1_048_576),
        max_upload_bytes=_int("MAX_UPLOAD_BYTES", 15 * 1_048_576),
        login_max_attempts=_int("LOGIN_MAX_ATTEMPTS", 8),
        login_window_seconds=_int("LOGIN_WINDOW_SECONDS", 900),
        require_mfa_for_admins=_bool("REQUIRE_MFA_FOR_ADMINS", True),
        require_email_verification=_bool("REQUIRE_EMAIL_VERIFICATION", True),
        seed_demo=_bool("IMPACTO_SEED_DEMO", False),
        mail_provider=_env("MAIL_PROVIDER", "console"),
        smtp_host=_env("SMTP_HOST", "") or "",
        smtp_port=_int("SMTP_PORT", 587),
        smtp_user=_env("SMTP_USER", "") or "",
        smtp_password=_env("SMTP_PASSWORD", "") or "",
        smtp_from=_env("SMTP_FROM", "no-reply@localhost"),
        storage_provider=_env("STORAGE_PROVIDER", "local"),
        storage_local_dir=_env("STORAGE_LOCAL_DIR", str(ROOT / "data" / "storage")),
        backup_dir=_env("BACKUP_DIR", "") or "",
        backup_database_url=_env("BACKUP_DATABASE_URL", "") or "",
        backup_interval_hours=_int("BACKUP_INTERVAL_HOURS", 24),
        backup_keep=_int("BACKUP_KEEP", 14),
        backup_offsite_cmd=_env("BACKUP_OFFSITE_CMD", "") or "",
        email_canary_to=_env("EMAIL_CANARY_TO", "") or "",
        email_canary_interval_minutes=_int("EMAIL_CANARY_INTERVAL_MINUTES", 60),
        s3_endpoint=_env("S3_ENDPOINT", "") or "",
        s3_region=_env("S3_REGION", "us-east-1"),
        s3_bucket=_env("S3_BUCKET", "") or "",
        s3_access_key_id=_env("S3_ACCESS_KEY_ID", "") or "",
        s3_secret_access_key=_env("S3_SECRET_ACCESS_KEY", "") or "",
        antivirus_provider=_env("ANTIVIRUS_PROVIDER", "none"),
        clamd_host=_env("CLAMD_HOST", "127.0.0.1"),
        clamd_port=_int("CLAMD_PORT", 3310),
        allow_unscanned_downloads=_bool("ALLOW_UNSCANNED_DOWNLOADS", not hardened),
        stripe_secret_key=_env("STRIPE_SECRET_KEY", "") or "",
        stripe_webhook_secret=_env("STRIPE_WEBHOOK_SECRET", "") or "",
        payment_webhook_secret=_env("PAYMENT_WEBHOOK_SECRET", "") or "",
        donations_enabled=_bool("DONATIONS_ENABLED", True),
        campaign_publication_enabled=_bool("CAMPAIGN_PUBLICATION_ENABLED", True),
        live_payment_provider_enabled=_bool("LIVE_PAYMENT_PROVIDER_ENABLED", False),
        split_enabled=_bool("SPLIT_ENABLED", False),
        recurring_donations_enabled=_bool("RECURRING_DONATIONS_ENABLED", False),
        risk_hold_enabled=_bool("RISK_HOLD_ENABLED", False),
        platform_pix_key=_env("PLATFORM_PIX_KEY", "") or "",
        platform_pix_key_type=_env("PLATFORM_PIX_KEY_TYPE", "") or "",
        ai_provider=_env("AI_PROVIDER", "local"),
        ai_base_url=_env("AI_BASE_URL", "") or "",
        ai_api_key=_env("AI_API_KEY", "") or "",
        ai_model=_env("AI_MODEL", "") or "",
        ai_timeout_seconds=_int("AI_TIMEOUT_SECONDS", 30),
        ai_max_input_chars=_int("AI_MAX_INPUT_CHARS", 12000),
        cnpj_lookup_url=_env("CNPJ_LOOKUP_URL", "") or "",
        oidc_issuer=_env("OIDC_ISSUER", "") or "",
        oidc_client_id=_env("OIDC_CLIENT_ID", "") or "",
        oidc_client_secret=_env("OIDC_CLIENT_SECRET", "") or "",
        oidc_redirect_uri=_env("OIDC_REDIRECT_URI", "") or "",
        metrics_token=_env("METRICS_TOKEN", "") or "",
        log_level=_env("LOG_LEVEL", "INFO"),
        web_dist_dir=_env("WEB_DIST_DIR", str(ROOT / "web" / "dist")),
    )
    validate(s)
    return s


def _looks_placeholder(v: str) -> bool:
    lv = v.lower()
    return any(m in lv for m in _PLACEHOLDER_MARKERS)


def is_r2_endpoint(endpoint: str) -> bool:
    """Endpoint S3 do Cloudflare R2 (`https://<conta>.r2.cloudflarestorage.com`, inclusive jurisdição `.eu.`)."""
    from urllib.parse import urlsplit
    host = (urlsplit(endpoint).hostname or "") if endpoint else ""
    return host.endswith(".r2.cloudflarestorage.com")


def storage_is_ephemeral(s: Settings) -> bool:
    """Arquivos em disco local num contêiner sem volume declarado se perdem no próximo deploy (v0.31.0).

    Não recusa subir — uma instância de demonstração pode aceitar isso —, mas a condição aparece no
    log de inicialização e em /readyz, para ninguém descobrir depois do primeiro redeploy. Declarar
    STORAGE_LOCAL_PERSISTENT=true é afirmar que há um volume montado em STORAGE_LOCAL_DIR."""
    return s.storage_provider == "local" and s.is_hardened and os.getenv("STORAGE_LOCAL_PERSISTENT", "false") != "true"


def validate(s: Settings) -> None:
    errors: list[str] = []
    if not s.database_url:
        errors.append("DATABASE_URL é obrigatório")
    if s.is_hardened:
        for name in ("secret_key", "voucher_hmac_key", "field_encryption_key"):
            v = getattr(s, name)
            if not v or len(v) < 32 or _looks_placeholder(v):
                errors.append(f"{name.upper()} ausente, curto (<32) ou com valor de exemplo")
        if not s.cookie_secure:
            errors.append("COOKIE_SECURE deve ser true em staging/production")
        if s.seed_demo:
            errors.append("IMPACTO_SEED_DEMO não é permitido em staging/production")
        if s.mail_provider == "console":
            errors.append("MAIL_PROVIDER=console não é permitido em staging/production (use smtp)")
        if int(os.getenv("RATE_LIMIT_MULTIPLIER", "1")) != 1:
            errors.append("RATE_LIMIT_MULTIPLIER deve ser 1 em staging/production")
        if int(os.getenv("PASSWORD_SCRYPT_N", str(2 ** 17))) < 2 ** 17:
            errors.append("PASSWORD_SCRYPT_N abaixo de 2^17 não é permitido em staging/production")
        if s.oidc_issuer and not s.oidc_issuer.startswith("https://"):
            errors.append("OIDC_ISSUER deve usar https em staging/production")
        if s.cnpj_lookup_url and not s.cnpj_lookup_url.startswith("https://"):
            errors.append("CNPJ_LOOKUP_URL deve usar https")
        if not s.public_base_url.startswith("https://"):
            errors.append("PUBLIC_BASE_URL deve usar https em staging/production")
        if not s.require_mfa_for_admins:
            # v0.35.0 (auditoria, AUTH-03): a variável existia e podia desligar o MFA da equipe em produção sem aviso
            errors.append("REQUIRE_MFA_FOR_ADMINS=false não é permitido em staging/production")
    if s.storage_provider == "s3" and not (s.s3_bucket and s.s3_access_key_id and s.s3_secret_access_key):
        errors.append("STORAGE_PROVIDER=s3 exige S3_BUCKET, S3_ACCESS_KEY_ID e S3_SECRET_ACCESS_KEY")
    # v0.31.0 — Cloudflare R2: a assinatura SigV4 usa a região; o R2 só reconhece `auto` (e aceita
    # `us-east-1` ou vazio como apelido — documentação do R2, "S3 API compatibility"). Com a região de
    # exemplo do .env (sa-east-1) toda URL assinada falharia em produção, em silêncio, no primeiro upload.
    if s.storage_provider == "s3" and is_r2_endpoint(s.s3_endpoint) and s.s3_region not in ("auto", "us-east-1", ""):
        errors.append("S3_ENDPOINT é do Cloudflare R2: S3_REGION deve ser `auto` (R2 não tem região AWS)")
    if s.storage_provider == "s3" and s.s3_endpoint and not s.s3_endpoint.startswith("https://") and s.is_hardened:
        errors.append("S3_ENDPOINT deve usar https em staging/production")
    if bool(s.stripe_secret_key) != bool(s.stripe_webhook_secret):
        errors.append("STRIPE_SECRET_KEY e STRIPE_WEBHOOK_SECRET vêm juntas ou nenhuma")
    if s.ai_provider in ("anthropic", "openai_compatible") and not (s.ai_api_key and s.ai_model):
        errors.append("AI_PROVIDER externo exige AI_API_KEY e AI_MODEL")
    if s.mail_provider == "smtp" and not s.smtp_host:
        errors.append("MAIL_PROVIDER=smtp exige SMTP_HOST")
    if s.live_payment_provider_enabled:
        errors.append("LIVE_PAYMENT_PROVIDER_ENABLED=true sem adaptador real: nenhum provedor de doações existe nesta versão (ADR-375)")
    if s.split_enabled or s.recurring_donations_enabled or s.risk_hold_enabled:
        errors.append("SPLIT_ENABLED/RECURRING_DONATIONS_ENABLED/RISK_HOLD_ENABLED exigem provedor real, contrato e ADR (ADR-375)")
    if errors:
        raise ConfigError("Configuração inválida:\n- " + "\n- ".join(errors))
