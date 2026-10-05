"""Contratos internos do Integration Hub: o núcleo depende DESTES tipos, nunca de um fornecedor.

Modelo canônico: entidades que JÁ existem no domínio da IMPACTO (pessoa, organização, documento, curso, certificado,
evento, fatura, pagamento, parceiro, edital). Nada fictício. Externo → adapter → mapping → canônico → núcleo (e o inverso).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable


class Environment(StrEnum):
    DEVELOPMENT = "development"
    SANDBOX = "sandbox"
    HOMOLOGATION = "homologation"
    PRODUCTION = "production"


class HealthState(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNCONFIGURED = "unconfigured"
    UNAUTHORIZED = "unauthorized"
    UNKNOWN = "unknown"


class Capability(StrEnum):
    CONNECT = "connect"
    PULL = "pull"
    PUSH = "push"
    WEBHOOK = "webhook"
    BATCH = "batch"
    ASYNC = "async"
    HEALTH = "health"


class CapabilityLevel(StrEnum):
    YES = "yes"
    NO = "no"
    PARTIAL = "partial"
    UNKNOWN = "unknown"
    NOT_IMPLEMENTED = "not_implemented"


class AuthKind(StrEnum):
    API_KEY = "api_key"
    BEARER_TOKEN = "bearer_token"      # noqa: S105 - nome do TIPO de credencial, não um segredo
    BASIC_AUTH = "basic_auth"
    OAUTH2_CLIENT_CREDENTIALS = "oauth2_client_credentials"
    OAUTH2_REFRESH = "oauth2_refresh"
    CERTIFICATE = "certificate"
    SECRET_REF = "secret_ref"          # noqa: S105 - nome do TIPO de credencial, não um segredo


class SyncStrategy(StrEnum):
    FULL = "full"
    INCREMENTAL = "incremental"
    EVENT_DRIVEN = "event_driven"
    SCHEDULED = "scheduled"
    MANUAL = "manual"


class Maturity(StrEnum):
    """Maturidade REAL. `PRODUCTION_ACTIVE` exige evidência externa e nunca é definida por código de aplicação."""
    SCAFFOLDED = "scaffolded"
    CONTRACT_TESTED = "contract_tested"
    SANDBOX = "sandbox"
    HOMOLOGATED = "homologated"
    PRODUCTION_ACTIVE = "production_active"


ENTITIES = ("person", "organization", "document", "course", "certificate", "event", "invoice", "payment", "partner", "call")


class IntegrationError(Exception):
    """Falha de integração classificada: `temporary` pode ser repetida; `permanent` não deve ser repetida indefinidamente."""

    def __init__(self, code: str, message: str, *, kind: str = "temporary", status: int | None = None, detail: str | None = None):
        super().__init__(message)
        self.code, self.kind, self.status, self.detail = code, kind, status, (detail or "")[:1000]

    @property
    def temporary(self) -> bool:
        return self.kind == "temporary"


# ------------------------------------------------------------------------------------------------ modelo canônico
@dataclass(slots=True)
class CanonicalRecord:
    """Registro canônico mínimo: entidade do domínio + campos + identificação externa (nunca substitui o ID interno)."""
    entity: str
    fields: dict[str, Any] = field(default_factory=dict)
    external_id: str | None = None
    external_version: str | None = None

    def __post_init__(self):
        if self.entity not in ENTITIES:
            raise ValueError(f"entidade fora do domínio: {self.entity}")


@dataclass(slots=True)
class ImpactoPerson:
    name: str
    document: str | None = None          # CPF, apenas dígitos
    email: str | None = None
    phone: str | None = None
    birth_date: date | None = None
    role: str | None = None


@dataclass(slots=True)
class ImpactoOrganization:
    legal_name: str
    cnpj: str | None = None
    trade_name: str | None = None
    kind: str | None = None
    uf: str | None = None
    city: str | None = None


@dataclass(slots=True)
class ImpactoInvoice:
    description: str
    amount_cents: int                    # dinheiro é SEMPRE inteiro em centavos
    currency: str = "BRL"
    status: str | None = None
    due_on: date | None = None
    issued_at: datetime | None = None


@dataclass(slots=True)
class AdapterContext:
    """O que o adapter recebe: conexão, credencial já decifrada (em memória), mapeamentos e transporte resiliente."""
    connection: dict
    secret: str | None
    username: str | None
    mappings: list[dict]
    transport: Any                       # integrations.transport.ResilientCaller
    correlation_id: str
    config: dict = field(default_factory=dict)


@dataclass(slots=True)
class AdapterResult:
    ok: bool
    records: list[CanonicalRecord] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)
    detail: str = ""
    external_ids: dict[str, str] = field(default_factory=dict)


@runtime_checkable
class IntegrationAdapter(Protocol):
    """Contrato de adapter. Implementações vivem em `integrations/adapters/` e NUNCA são importadas pelo núcleo.

    `health_check` jamais executa operação destrutiva. `pull`/`push` devolvem registros canônicos e estatísticas;
    falhas externas viram `IntegrationError` classificada (temporária × permanente) — o hub decide repetir ou não.
    """

    key: str
    category: str
    api_style: str
    auth_kinds: tuple[str, ...]
    capabilities: dict[str, str]

    def validate_config(self, connection: dict) -> list[str]:
        """Devolve a lista de problemas de configuração (vazia = pronta para conectar)."""
        ...

    def health_check(self, ctx: AdapterContext) -> tuple[str, str]:
        """(HealthState, detalhe). Somente leitura."""
        ...

    def pull(self, ctx: AdapterContext, entity: str, *, since: datetime | None = None, limit: int = 200) -> AdapterResult:
        ...

    def push(self, ctx: AdapterContext, entity: str, records: list[CanonicalRecord]) -> AdapterResult:
        ...

    def handle_webhook(self, ctx: AdapterContext, headers: dict, body: bytes) -> tuple[str, str, dict]:
        """(external_event_id, event_type, payload normalizado). Deve verificar a assinatura quando o provedor assina."""
        ...
