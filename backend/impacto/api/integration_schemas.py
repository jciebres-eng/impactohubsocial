"""Esquemas de entrada do Integration Hub (validação estrita: campos extras são rejeitados)."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field

from .schemas import In, Pagination, Uuid

Entity = Literal["person", "organization", "document", "course", "certificate", "event", "invoice", "payment", "partner", "call"]
Env = Literal["development", "sandbox", "homologation", "production"]
CredKind = Literal["api_key", "bearer_token", "basic_auth", "oauth2_client_credentials", "oauth2_refresh", "certificate", "secret_ref"]
Transform = Literal["none", "trim", "upper", "lower", "digits_only", "date_iso", "date_br", "decimal_comma", "cents_from_decimal", "boolean", "enum", "split_list"]


class ConnectionIn(In):
    provider_key: Annotated[str, Field(pattern=r"^[a-z0-9_]{3,40}$")]
    name: Annotated[str, Field(min_length=2, max_length=120)]
    environment: Env = "sandbox"
    endpoint: Annotated[str | None, Field(pattern=r"^https?://", max_length=500)] = None
    external_system_id: Annotated[str | None, Field(max_length=200)] = None
    config: dict[Annotated[str, Field(max_length=60)], object] = {}


class ConnectionPatchIn(In):
    name: Annotated[str | None, Field(min_length=2, max_length=120)] = None
    endpoint: Annotated[str | None, Field(pattern=r"^https?://", max_length=500)] = None
    external_system_id: Annotated[str | None, Field(max_length=200)] = None
    config: dict[Annotated[str, Field(max_length=60)], object] | None = None
    status: Literal["draft", "active", "paused", "revoked"] | None = None


class CredentialIn(In):
    kind: CredKind
    secret: Annotated[str | None, Field(min_length=8, max_length=4096)] = None
    secret_ref: Annotated[str | None, Field(max_length=300)] = None
    username: Annotated[str | None, Field(max_length=200)] = None
    scopes: Annotated[list[Annotated[str, Field(max_length=80)]], Field(max_length=30)] = []
    expires_at: datetime | None = None


class MappingItem(In):
    entity: Entity
    direction: Literal["inbound", "outbound", "both"] = "inbound"
    source_path: Annotated[str, Field(min_length=1, max_length=200)]
    target_field: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,99}$")]
    transform: Transform = "none"
    enum_map: dict[Annotated[str, Field(max_length=100)], Annotated[str, Field(max_length=200)]] = {}
    required: bool = False
    default_value: Annotated[str | None, Field(max_length=200)] = None


class MappingsIn(In):
    items: Annotated[list[MappingItem], Field(max_length=200)]


class JobIn(In):
    operation: Literal["pull", "push", "health_check"]
    entity: Entity | None = None
    direction: Literal["inbound", "outbound", "bidirectional"] = "inbound"
    strategy: Literal["full", "incremental", "event_driven", "scheduled", "manual"] = "manual"
    request: dict[Annotated[str, Field(max_length=60)], object] = {}
    idempotency_key: Annotated[str | None, Field(min_length=8, max_length=200)] = None
    max_attempts: Annotated[int, Field(ge=1, le=10)] = 3


class JobsQ(Pagination):
    connection_id: Uuid | None = None
    status: Literal["pending", "running", "succeeded", "partial", "failed", "retrying", "canceled"] | None = None


class SubscriptionIn(In):
    name: Annotated[str, Field(min_length=2, max_length=120)]
    url: Annotated[str, Field(pattern=r"^https://", max_length=500)]
    event_types: Annotated[list[Annotated[str, Field(pattern=r"^[A-Z]+(\.[A-Z_]+)+$")]], Field(min_length=1, max_length=40)]
    secret: Annotated[str, Field(min_length=16, max_length=256)]
    connection_id: Uuid | None = None
    headers: dict[Annotated[str, Field(pattern=r"^[A-Za-z0-9-]{1,60}$")], Annotated[str, Field(max_length=200)]] = {}


class SubscriptionPatchIn(In):
    name: Annotated[str | None, Field(min_length=2, max_length=120)] = None
    url: Annotated[str | None, Field(pattern=r"^https://", max_length=500)] = None
    event_types: Annotated[list[Annotated[str, Field(pattern=r"^[A-Z]+(\.[A-Z_]+)+$")]] | None, Field(max_length=40)] = None
    status: Literal["active", "paused", "disabled"] | None = None


class DeliveriesQ(Pagination):
    subscription_id: Uuid | None = None
    status: Literal["pending", "delivered", "retrying", "dead_letter", "skipped"] | None = None


class EventsQ(Pagination):
    event_type: Annotated[str | None, Field(pattern=r"^[A-Z]+(\.[A-Z_]+)+$")] = None


class ImportIn(In):
    entity: Entity
    format: Literal["csv", "xlsx", "json", "xml"]
    document_id: Uuid
    connection_id: Uuid | None = None


class ApproveImportIn(In):
    connection_id: Uuid | None = None


class ExportIn(In):
    dataset: Annotated[str, Field(pattern=r"^[a-z_]{2,60}$")]
    format: Literal["csv", "json"] = "csv"
    filters: dict[Annotated[str, Field(max_length=60)], object] = {}


class LinksQ(Pagination):
    entity: Entity | None = None
    sync_status: Literal["linked", "pending", "conflict", "stale", "deleted_externally"] | None = None
    connection_id: Uuid | None = None


class MaturityIn(In):
    maturity: Literal["scaffolded", "contract_tested", "sandbox", "homologated", "production_active"]
    evidence: Annotated[str, Field(min_length=20, max_length=2000)]   # documento/evidência externa que justifica a promoção
