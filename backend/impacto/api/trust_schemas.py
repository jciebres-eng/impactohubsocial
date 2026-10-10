"""Esquemas de entrada da camada de confiança (validação estrita: campo extra é rejeitado)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import Field

from .schemas import In, Pagination, Uuid

IdentityLevel = Literal["email", "phone", "document", "professional", "biometric"]
IdDocKind = Literal["official_id", "drivers_license", "passport", "proof_of_address", "council_card", "other"]
AgreementKind = Literal["service", "partnership", "funding", "volunteer", "data_sharing", "other"]
PartyRole = Literal["contractor", "provider", "funder", "professional", "witness", "beneficiary_rep", "proponent"]
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
    # v0.26.0 — termos operacionais do contrato (congelam ao publicar)
    platform_fee_bps: Annotated[int | None, Field(ge=0, le=10000)] = None
    fee_payer_role: Literal["funder", "contractor", "provider"] | None = None
    fee_mode: Literal["additional", "deducted"] | None = None
    review_days: Annotated[int | None, Field(ge=1, le=120)] = None
    calendar_type: Literal["calendar", "business"] | None = None
    auto_accept: bool | None = None
    dispute_days: Annotated[int | None, Field(ge=0, le=60)] = None


class AgreementPatch(In):
    title: Annotated[str | None, Field(min_length=3, max_length=200)] = None
    summary: Annotated[str | None, Field(max_length=4000)] = None
    effective_from: date | None = None
    effective_to: date | None = None
    value_cents: Annotated[int | None, Field(ge=0, le=10**13)] = None
    # v0.26.0 — termos operacionais do contrato (congelam ao publicar)
    platform_fee_bps: Annotated[int | None, Field(ge=0, le=10000)] = None
    fee_payer_role: Literal["funder", "contractor", "provider"] | None = None
    fee_mode: Literal["additional", "deducted"] | None = None
    review_days: Annotated[int | None, Field(ge=1, le=120)] = None
    calendar_type: Literal["calendar", "business"] | None = None
    auto_accept: bool | None = None
    dispute_days: Annotated[int | None, Field(ge=0, le=60)] = None


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
    seq: Annotated[int | None, Field(ge=1, le=500)] = None
    amount_cents: Annotated[int | None, Field(ge=0, le=10**13)] = None


class AgreementNewVersionIn(In):
    document_id: Uuid
    reason: Annotated[str, Field(min_length=10, max_length=1000)]
    title: Annotated[str | None, Field(min_length=3, max_length=200)] = None
    summary: Annotated[str | None, Field(max_length=4000)] = None
    effective_from: date | None = None
    effective_to: date | None = None
    value_cents: Annotated[int | None, Field(ge=0, le=10**13)] = None
    platform_fee_bps: Annotated[int | None, Field(ge=0, le=10000)] = None
    fee_payer_role: Literal["funder", "contractor", "provider"] | None = None
    fee_mode: Literal["additional", "deducted"] | None = None
    review_days: Annotated[int | None, Field(ge=1, le=120)] = None
    calendar_type: Literal["calendar", "business"] | None = None
    auto_accept: bool | None = None
    dispute_days: Annotated[int | None, Field(ge=0, le=60)] = None


class PartyPixIn(In):
    pix_key: Annotated[str, Field(min_length=3, max_length=120)]
    pix_key_type: Literal["cpf", "cnpj", "email", "phone", "evp"]


class TransferIn(In):
    amount_cents: Annotated[int, Field(gt=0, le=10**13)]
    reference: Annotated[str, Field(min_length=3, max_length=120)]
    paid_on: date
    method: Literal["pix", "bank_transfer", "other"] = "pix"
    evidence_document_id: Uuid | None = None


class ParticipationIn(In):
    proponent_org_id: Uuid
    proponent_user_id: Uuid | None = None
    idea_ref_type: Literal["solution", "idea"]
    idea_ref_id: Uuid
    authorship_type: Literal["author", "coauthor"] = "author"
    share_bps: Annotated[int, Field(ge=1, le=10000)] = 10000
    contribution: Annotated[str, Field(min_length=20, max_length=2000)]


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


class GlossaryQ(In):
    locale: Annotated[str, Field(pattern=r"^[a-z]{2}(-[A-Z]{2})?$")] = "pt-BR"
    domain: Annotated[str | None, Field(pattern=r"^[a-z0-9_]{2,40}$")] = None


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
    project_id: Uuid | None = None   # v0.33.0: campanha de organização/fundo não tem projeto
    kind: Literal["project_crowdfunding", "emergency", "institutional_fund", "recurring", "organization"] = "project_crowdfunding"
    target_cents: Annotated[int | None, Field(gt=0)] = None
    starts_on: date | None = None
    ends_on: date | None = None
    purpose: Annotated[str | None, Field(max_length=2000)] = None
    contingency_policy: Annotated[str | None, Field(max_length=2000)] = None
    refund_policy: Annotated[str | None, Field(max_length=2000)] = None
    min_donation_cents: Annotated[int, Field(ge=100)] = 500
    allow_recurring: bool = False
    funding_source: Literal["private", "public", "mixed"] = "private"     # v0.34.0 (ADR-379)
    public_instrument_ref: Annotated[str | None, Field(max_length=300)] = None
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
    target_cents: Annotated[int | None, Field(gt=0)] = None
    ends_on: date | None = None
    purpose: Annotated[str | None, Field(max_length=2000)] = None
    contingency_policy: Annotated[str | None, Field(max_length=2000)] = None
    refund_policy: Annotated[str | None, Field(max_length=2000)] = None
    min_donation_cents: Annotated[int | None, Field(ge=100)] = None


# ---------------------------------------------------------------- doações (v0.33.0)
class CampaignReviewIn(In):
    approve: bool
    note: Annotated[str, Field(min_length=10, max_length=2000)]


class CampaignSuspendIn(In):
    note: Annotated[str, Field(min_length=10, max_length=2000)]
    reinstate: bool = False


class DonationStartIn(In):
    amount_cents: Annotated[int, Field(ge=100, le=100_000_000)]
    method: Literal["pix", "card"] = "pix"
    donor_display: Annotated[str | None, Field(max_length=120)] = None
    donor_email: Annotated[str | None, Field(max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")] = None
    public_anonymous: bool = False
    cover_costs: bool = False          # NUNCA pré-marcada no front
    idempotency_key: Annotated[str | None, Field(max_length=80, pattern=r"^[A-Za-z0-9_-]+$")] = None
    as_organization: bool = False      # v0.34.0: doar em nome da organização ativa (painel do financiador)
    funding_source: Literal["private", "public", "mixed"] | None = None   # v0.34.0: origem declarada pelo doador institucional


class RiskDecisionIn(In):
    action: Literal["allow", "request_information", "reject", "report_to_provider"]
    note: Annotated[str, Field(min_length=10, max_length=2000)]


class CampaignExpenseIn(In):
    description: Annotated[str, Field(min_length=3, max_length=500)]
    budget_line: Annotated[str | None, Field(max_length=120)] = None
    amount_cents: Annotated[int, Field(gt=0)]
    spent_on: date
    document_id: Uuid | None = None


class CampaignUpdateIn(In):
    title: Annotated[str, Field(min_length=3, max_length=200)]
    body: Annotated[str, Field(min_length=10, max_length=8000)]
    evidence_ids: list[Uuid] = []
    is_public: bool = True


class BeneficiaryVerificationIn(In):
    status: Literal["documents_requested", "under_review", "verified", "rejected"]
    note: Annotated[str, Field(min_length=10, max_length=2000)]
    account_holder_matches: bool | None = None
    evidence_document_ids: list[Uuid] = []


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


# ---------------------------------------------------------------- v0.34.0 — ecossistema financeiro
class ExternalResourceIn(In):
    kind: Literal["public_transfer", "grant", "offline_donation", "sponsorship", "in_kind", "own_funds", "other"]
    source_name: Annotated[str, Field(min_length=2, max_length=200)]
    funding_source: Literal["private", "public", "mixed"]
    instrument_ref: Annotated[str, Field(max_length=300)] | None = None
    amount_cents: Annotated[int, Field(gt=0, le=100_000_000_000)] | None = None
    in_kind_description: Annotated[str, Field(max_length=1000)] | None = None
    received_on: date
    evidence_document_id: Uuid | None = None
    note: Annotated[str, Field(max_length=1000)] | None = None


class DonationPledgeIn(In):
    amount_cents: Annotated[int, Field(ge=100, le=100_000_000)]
    display: Annotated[str, Field(max_length=120)] | None = None
    expected_on: date | None = None
    note: Annotated[str, Field(max_length=500)] | None = None
    as_organization: bool = False


class PledgeFulfillIn(In):
    donation_id: Uuid


class ObligationDisputeIn(In):
    reason: Annotated[str, Field(min_length=10, max_length=2000)]


class ObligationDecisionIn(In):
    outcome: Literal["uphold", "waive", "exempt"]
    note: Annotated[str, Field(min_length=10, max_length=2000)]


class ObligationWaiveIn(In):
    reason: Annotated[str, Field(min_length=10, max_length=2000)]


class ObligationInvoiceIn(In):
    obligation_ids: Annotated[list[Uuid], Field(min_length=1, max_length=200)]


class ObligationReceiptIn(In):
    received_cents: Annotated[int, Field(gt=0, le=100_000_000_000)]
    reference: Annotated[str, Field(min_length=3, max_length=120)]


class ObligationSettleIn(In):
    note: Annotated[str, Field(min_length=3, max_length=2000)]


class PublicFeeAuthorizationIn(In):
    instrument_ref: Annotated[str, Field(min_length=5, max_length=300)]
    note: Annotated[str, Field(min_length=10, max_length=2000)]


class NoticeIn(In):
    kind: Literal["free_until_value_intro", "allowance_approaching", "charging_starts"]
    body: Annotated[str, Field(min_length=20, max_length=4000)] | None = None
    channel: Literal["in_app", "email", "both"] = "in_app"


class ReconciliationResolveIn(In):
    outcome: Literal["resolved", "dismissed"]
    note: Annotated[str, Field(min_length=10, max_length=2000)]


class ReconciliationSnapshotIn(In):
    """Snapshot do provedor enviado à mão (ferramenta de operação) quando o adaptador não consulta a API."""
    charges: list[dict] = []
