"""Esquemas de entrada da camada de confiança (validação estrita: campo extra é rejeitado)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import Field

from .schemas import In, Pagination, Uuid

IdentityLevel = Literal["email", "phone", "document", "professional", "biometric"]
IdDocKind = Literal["official_id", "drivers_license", "passport", "proof_of_address", "council_card", "other"]
AgreementKind = Literal["service", "partnership", "funding", "volunteer", "data_sharing", "other"]
PartyRole = Literal["contractor", "provider", "funder", "professional", "witness", "beneficiary_rep"]
Taxonomy = Literal["sdg", "esg", "determinant"]
TagSubject = Literal["project", "solution", "diagnosis", "need", "call", "organization", "agreement"]
FeeUnit = Literal["hour", "session", "document", "report", "visit", "month", "project", "other"]


# ---------------------------------------------------------------- identidade
class IdentityRequestIn(In):
    level: IdentityLevel
    method: Literal["platform_token", "human_review", "council_document", "external_provider"] = "human_review"


class IdentityDocumentIn(In):
    document_id: Uuid
    kind: IdDocKind


class DecisionIn(In):
    approve: bool
    note: Annotated[str, Field(min_length=5, max_length=2000)]
    expires_at: datetime | None = None


class CredentialDecisionIn(In):
    approve: bool
    note: Annotated[str, Field(min_length=5, max_length=2000)]
    valid_until: date | None = None


class RevokeIn(In):
    reason: Annotated[str, Field(min_length=10, max_length=500)]


# ---------------------------------------------------------------- assinatura
class ChallengeIn(In):
    subject_type: Literal["document", "draft", "agreement"]
    subject_id: Uuid
    channel: Literal["email", "sms"] = "email"


class VerifiableIn(In):
    subject_type: Literal["document", "draft", "agreement"]
    subject_id: Uuid
    title: Annotated[str | None, Field(min_length=2, max_length=200)] = None
    expires_at: datetime | None = None


class CustodyQ(In):
    subject_type: Literal["document", "draft", "agreement", "credential", "identity"]
    subject_id: Uuid


# ---------------------------------------------------------------- acordos
class AgreementIn(In):
    kind: AgreementKind
    title: Annotated[str, Field(min_length=3, max_length=200)]
    summary: Annotated[str | None, Field(max_length=4000)] = None
    document_id: Uuid
    project_id: Uuid | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    value_cents: Annotated[int | None, Field(ge=0, le=10**13)] = None


class AgreementPatch(In):
    title: Annotated[str | None, Field(min_length=3, max_length=200)] = None
    summary: Annotated[str | None, Field(max_length=4000)] = None
    effective_from: date | None = None
    effective_to: date | None = None
    value_cents: Annotated[int | None, Field(ge=0, le=10**13)] = None


class PartyIn(In):
    org_id: Uuid
    role: PartyRole
    required: bool = True
    user_id: Uuid | None = None


class AgreementSignIn(In):
    statement: Annotated[str, Field(min_length=10, max_length=2000)]
    password: Annotated[str, Field(min_length=1, max_length=256)]
    code: Annotated[str, Field(min_length=4, max_length=12)]


class MilestoneIn(In):
    title: Annotated[str, Field(min_length=2, max_length=200)]
    due_on: date | None = None
    note: Annotated[str | None, Field(max_length=2000)] = None


class MilestonePatch(In):
    status: Literal["planned", "in_progress", "delivered", "accepted", "rejected", "canceled"]
    document_id: Uuid | None = None
    note: Annotated[str | None, Field(max_length=2000)] = None


# ---------------------------------------------------------------- taxonomia
class TagIn(In):
    subject_type: TagSubject
    subject_id: Uuid
    taxonomy: Taxonomy
    code: Annotated[str, Field(min_length=1, max_length=40)]
    is_primary: bool = False
    note: Annotated[str | None, Field(max_length=500)] = None


class TagQ(In):
    subject_type: TagSubject
    subject_id: Uuid


# ---------------------------------------------------------------- preferências
class PrefsIn(In):
    locale: Annotated[str | None, Field(pattern=r"^[a-z]{2}(-[A-Z]{2})?$")] = None
    theme: Literal["system", "light", "dark"] | None = None


class TranslationsQ(In):
    locale: Annotated[str, Field(pattern=r"^[a-z]{2}(-[A-Z]{2})?$")] = "pt-BR"
    namespace: Annotated[str | None, Field(pattern=r"^[a-z0-9_]{2,40}$")] = None


# ---------------------------------------------------------------- cotas e campanha
class QuotaIn(In):
    project_id: Uuid
    label: Annotated[str, Field(min_length=2, max_length=120)]
    description: Annotated[str | None, Field(max_length=2000)] = None
    quota_cents: Annotated[int, Field(gt=0, le=10**11)]
    total_quotas: Annotated[int, Field(gt=0, le=100000)]
    min_per_backer: Annotated[int, Field(ge=1, le=1000)] = 1
    max_per_backer: Annotated[int | None, Field(ge=1, le=100000)] = None
    deadline: date | None = None


class QuotaPatch(In):
    status: Literal["draft", "open", "paused", "closed"] | None = None
    label: Annotated[str | None, Field(min_length=2, max_length=120)] = None
    description: Annotated[str | None, Field(max_length=2000)] = None
    deadline: date | None = None


class PledgeIn(In):
    quantity: Annotated[int, Field(ge=1, le=100000)]
    display_name: Annotated[str | None, Field(max_length=120)] = None
    is_anonymous: bool = False
    note: Annotated[str | None, Field(max_length=1000)] = None


class CampaignIn(In):
    project_id: Uuid
    slug: Annotated[str, Field(pattern=r"^[a-z0-9-]{4,80}$")]
    title: Annotated[str, Field(min_length=4, max_length=200)]
    summary: Annotated[str, Field(min_length=20, max_length=600)]
    story: Annotated[str | None, Field(max_length=20000)] = None
    cover_document_id: Uuid | None = None
    show_backers: bool = False


class CampaignPatch(In):
    title: Annotated[str | None, Field(min_length=4, max_length=200)] = None
    summary: Annotated[str | None, Field(min_length=20, max_length=600)] = None
    story: Annotated[str | None, Field(max_length=20000)] = None
    cover_document_id: Uuid | None = None
    show_backers: bool | None = None
    status: Literal["draft", "published", "closed"] | None = None


# ---------------------------------------------------------------- honorários e serviços
class FeeTableIn(In):
    council_code: Annotated[str, Field(pattern=r"^[A-Z]{2,10}$")]
    title: Annotated[str, Field(min_length=4, max_length=200)]
    version: Annotated[str, Field(min_length=1, max_length=40)]
    reference_year: Annotated[int | None, Field(ge=2000, le=2100)] = None
    source_name: Annotated[str | None, Field(max_length=200)] = None
    source_url: Annotated[str | None, Field(pattern=r"^https://", max_length=500)] = None
    source_date: date | None = None
    notes: Annotated[str | None, Field(max_length=2000)] = None


class FeeItemIn(In):
    service_code: Annotated[str, Field(pattern=r"^[a-z0-9_.-]{2,60}$")]
    description: Annotated[str, Field(min_length=3, max_length=300)]
    unit: FeeUnit
    reference_cents: Annotated[int | None, Field(ge=0, le=10**11)] = None
    min_cents: Annotated[int | None, Field(ge=0, le=10**11)] = None
    max_cents: Annotated[int | None, Field(ge=0, le=10**11)] = None
    negotiable: bool = True
    note: Annotated[str | None, Field(max_length=500)] = None


class ServiceIn(In):
    title: Annotated[str, Field(min_length=3, max_length=200)]
    description: Annotated[str | None, Field(max_length=4000)] = None
    modality: Literal["online", "in_person", "hybrid"] = "hybrid"
    unit: FeeUnit = "session"
    credential_id: Uuid | None = None
    fee_item_id: Uuid | None = None
    price_cents: Annotated[int | None, Field(ge=0, le=10**11)] = None
    negotiable: bool = True
    duration_min: Annotated[int | None, Field(ge=5, le=1440)] = None


class ServicePatch(ServiceIn):
    title: Annotated[str | None, Field(min_length=3, max_length=200)] = None
    status: Literal["draft", "published", "paused"] | None = None


# ---------------------------------------------------------------- georreferência
class GeoIn(In):
    lat: Annotated[float, Field(ge=-90, le=90)]
    lng: Annotated[float, Field(ge=-180, le=180)]
    precision: Literal["exact", "approximate", "city"] = "city"
    public: bool = False


# ---------------------------------------------------------------- diagnóstico guiado
class StageIn(In):
    answers: dict = Field(default_factory=dict)
    document_ids: list[Uuid] = Field(default_factory=list, max_length=20)
    complete: bool = False
    skip_reason: Annotated[str | None, Field(max_length=500)] = None


class DirectoryQ(Pagination):
    q: Annotated[str | None, Field(max_length=120)] = None
    uf: Annotated[str | None, Field(pattern=r"^[A-Z]{2}$")] = None
    council: Annotated[str | None, Field(pattern=r"^[A-Z]{2,10}$")] = None
    sdg: Annotated[str | None, Field(pattern=r"^ODS[0-9]{1,2}$")] = None
