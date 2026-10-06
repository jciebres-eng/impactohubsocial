"""Schemas da camada de impacto contextualizado (v0.18.0)."""
from __future__ import annotations

from datetime import date
from typing import Annotated

from pydantic import Field

from .schemas import In, Uuid

Note = Annotated[str, Field(min_length=10, max_length=2000)]
LongNote = Annotated[str, Field(min_length=20, max_length=2000)]
SourceName = Annotated[str, Field(min_length=3, max_length=300)]
Url = Annotated[str, Field(pattern=r"^https?://", max_length=500)]
Slug = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{2,40}$")]
Territory = Annotated[str, Field(pattern=r"^(INT|[A-Z]{2}(-[A-Z]{2}(-[0-9]{7})?)?)$")]
Standing = Annotated[str, Field(pattern="^(declared|documented|evidenced)$")]


class EquityContextIn(In):
    need_statement: LongNote
    additionality: LongNote
    counterfactual: LongNote | None = None
    additionality_standing: Standing = "declared"
    additionality_evidence_id: Uuid | None = None
    need_source_name: SourceName | None = None
    need_source_url: Url | None = None
    need_source_date: date | None = None
    context_note: Annotated[str, Field(max_length=4000)] | None = None


class BarrierIn(In):
    barrier_code: Slug
    note: Note
    standing: Standing = "declared"
    source_name: SourceName | None = None
    source_url: Url | None = None
    source_date: date | None = None
    evidence_id: Uuid | None = None
    document_id: Uuid | None = None


class DenominatorIn(In):
    #: `territory` só é aceito na rota administrativa: denominador de território é bem comum.
    scope: Annotated[str, Field(pattern="^(project|program)$")] = "project"
    project_id: Uuid | None = None
    program_id: Uuid | None = None
    kind: Annotated[str, Field(pattern="^(eligible_population|reference_population|households"
                                       "|enrolled|area_km2|service_units|resource_cents)$")]
    value: Annotated[float, Field(gt=0, le=1e15)]
    unit: Annotated[str, Field(min_length=1, max_length=40)]
    reference_date: date
    source_name: SourceName
    source_url: Url | None = None
    source_date: date
    method_note: Note


class TerritoryDenominatorIn(In):
    territory: Territory
    kind: Annotated[str, Field(pattern="^(reference_population|households|enrolled|area_km2"
                                       "|service_units)$")]
    value: Annotated[float, Field(gt=0, le=1e15)]
    unit: Annotated[str, Field(min_length=1, max_length=40)]
    reference_date: date
    source_name: SourceName
    source_url: Url | None = None
    source_date: date
    method_note: Note


class NormalizeQ(In):
    indicator_id: Uuid | None = None


class AssessIn(In):
    indicator_id: Uuid | None = None


class CompareIn(In):
    project_ids: Annotated[list[Uuid], Field(min_length=2, max_length=5)]
    indicator_code: Annotated[str, Field(max_length=60)] | None = None


class DenominatorQ(In):
    project_id: Uuid | None = None
    program_id: Uuid | None = None
    territory: Territory | None = None
    include_closed: bool = False


class HistoryQ(In):
    limit: Annotated[int, Field(ge=1, le=100)] = 24


# ================================================================================================ frameworks
class RegistryQ(In):
    status: Annotated[str, Field(pattern="^(in_use|mappable|registry_only)$")] | None = None


class MappingIn(In):
    framework_key: Slug
    indicator_id: Uuid
    relation: Annotated[str, Field(min_length=3, max_length=20)]
    rationale: LongNote
    external_code: Annotated[str, Field(min_length=1, max_length=60)] | None = None
    external_name: SourceName | None = None
    source_name: SourceName | None = None
    reviewer_org_id: Uuid | None = None
    reviewer_user_id: Uuid | None = None


class MappingQ(In):
    framework_key: Slug | None = None
    indicator_id: Uuid | None = None
    mine: bool = False


class MaterialityIn(In):
    scope: Annotated[str, Field(pattern="^(organization|program|project)$")] = "organization"
    program_id: Uuid | None = None
    project_id: Uuid | None = None
    period_label: Annotated[str, Field(min_length=4, max_length=60)]
    method_note: Annotated[str, Field(min_length=20, max_length=4000)]
    lens: Annotated[str, Field(pattern="^(impact_only|financial_only|double)$")] = "double"
    threshold: Annotated[int, Field(ge=1, le=5)] = 4
    framework_key: Slug | None = None


class MaterialityEntryIn(In):
    topic_code: Slug
    rationale: LongNote
    impact_score: Annotated[int, Field(ge=1, le=5)] | None = None
    financial_score: Annotated[int, Field(ge=1, le=5)] | None = None
    stakeholder_note: Annotated[str, Field(max_length=2000)] | None = None
    evidence_id: Uuid | None = None
    indicator_id: Uuid | None = None


# ================================================================================================ alegações
class ClaimIn(In):
    subject_type: Annotated[str, Field(
        pattern="^(project|program|organization|solution|impact_update)$")]
    subject_id: Uuid
    claim_kind: Annotated[str, Field(pattern="^(result|ods_contribution|esg|environmental|social|"
                                             "governance|efficiency|financial|comparative|"
                                             "certification)$")]
    statement: Annotated[str, Field(min_length=10, max_length=4000)]
    scope_note: Annotated[str, Field(max_length=2000)] | None = None
    period_start: date | None = None
    period_end: date | None = None
    indicator_id: Uuid | None = None
    evidence_id: Uuid | None = None


class ClaimQ(In):
    subject_type: Annotated[str, Field(
        pattern="^(project|program|organization|solution|impact_update)$")] | None = None
    subject_id: Uuid | None = None
    mine: bool = True
    limit: Annotated[int, Field(ge=1, le=100)] = 50
    offset: Annotated[int, Field(ge=0, le=10000)] = 0


class ClaimWithdrawIn(In):
    reason: Annotated[str, Field(min_length=10, max_length=2000)]


class ClaimReviewIn(In):
    decision: Annotated[str, Field(pattern="^(accepted|needs_change|rejected)$")]
    note: Annotated[str, Field(min_length=20, max_length=2000)]


class ClaimReviewRequestIn(In):
    reviewer_org_id: Uuid
    note: Annotated[str, Field(min_length=10, max_length=2000)] | None = None


# ================================================================================================ reputação
class TimelineQ(In):
    dimension: Slug | None = None
    limit: Annotated[int, Field(ge=1, le=365)] = 120


class DisputeIn(In):
    dimension: Slug
    what_is_contested: Annotated[str, Field(min_length=20, max_length=4000)]
    expected_correction: Annotated[str, Field(min_length=20, max_length=4000)]
    evidence_id: Uuid | None = None


class DisputeQ(In):
    only_open: bool = False
    all_orgs: bool = False


class DisputeResolutionIn(In):
    outcome: Annotated[str, Field(
        pattern="^(corrected|no_change|partially_corrected|needs_more_information)$")]
    rationale: Annotated[str, Field(min_length=20, max_length=4000)]
    what_changed: Annotated[str, Field(min_length=10, max_length=4000)] | None = None


# ================================================================================================ selos
class SealCriterionIn(In):
    rule_code: Slug
    params: dict | None = None


class SealDefinitionIn(In):
    code: Slug
    scope: Annotated[str, Field(pattern="^(organization|project)$")]
    title: Annotated[str, Field(min_length=5, max_length=200)]
    what_it_attests: Annotated[str, Field(min_length=20, max_length=2000)]
    what_it_does_not_attest: Annotated[str, Field(min_length=20, max_length=2000)]
    validity_days: Annotated[int, Field(ge=30, le=1095)]
    criteria: Annotated[list[SealCriterionIn], Field(min_length=1, max_length=12)]


class SealDefinitionQ(In):
    scope: Annotated[str, Field(pattern="^(organization|project)$")] | None = None
    code: Slug | None = None
    status: Annotated[str, Field(pattern="^(draft|published|retired)$")] | None = None


class SealRetireIn(In):
    """Aposentar uma definição de selo muda o que a plataforma afirma daqui para a frente."""

    reason: Annotated[str, Field(min_length=20, max_length=2000)]


class SealEvaluateIn(In):
    definition_id: Uuid
    subject_id: Uuid


class SealAwardQ(In):
    scope: Annotated[str, Field(pattern="^(organization|project)$")] | None = None
    subject_id: Uuid | None = None
    mine: bool = False
    active_only: bool = False


class SealRevokeIn(In):
    reason: Annotated[str, Field(pattern="^(criterion_no_longer_met|definition_retired|"
                                         "data_correction|request_of_holder|misconduct)$")]
    detail: Annotated[str, Field(min_length=10, max_length=2000)]


class LookupQ(In):
    q: Annotated[str, Field(max_length=120)] = ""
    limit: Annotated[int, Field(ge=1, le=25)] = 10


# ================================================================================================ responsabilidade
class AssignmentIn(In):
    scope: Annotated[str, Field(pattern="^(organization|program|project|document)$")]
    subject_id: Uuid
    role_code: Slug
    mandate_basis: Annotated[str, Field(min_length=10, max_length=2000)]
    user_id: Uuid | None = None
    external_name: Annotated[str, Field(min_length=3, max_length=200)] | None = None
    external_note: Annotated[str, Field(min_length=5, max_length=500)] | None = None
    starts_on: date | None = None


class AssignmentEndIn(In):
    reason: Annotated[str, Field(min_length=10, max_length=2000)]
    ended_on: date | None = None


class ResponsibleQ(In):
    scope: Annotated[str, Field(pattern="^(organization|program|project|document)$")]
    subject_id: Uuid


class DecisionIn(In):
    assignment_id: Uuid
    kind: Slug
    statement: Annotated[str, Field(min_length=20, max_length=4000)]
    document_id: Uuid | None = None
    document_version: Annotated[int, Field(ge=1, le=9999)] | None = None
    signature_id: Uuid | None = None
    second_assignment_id: Uuid | None = None
    second_statement: Annotated[str, Field(min_length=20, max_length=4000)] | None = None
    taken_on: date | None = None


class DecisionQ(In):
    scope: Annotated[str, Field(pattern="^(organization|program|project|document)$")] | None = None
    subject_id: Uuid | None = None
    assignment_id: Uuid | None = None
    limit: Annotated[int, Field(ge=1, le=200)] = 100


# ---------------------------------------------------------------- primeiro acesso (v0.19.0)
class FirstRunQ(In):
    """`project_id` é opcional de propósito: sem projeto escolhido, as áreas de escopo de projeto
    voltam com o pré-requisito explícito em vez de uma contagem falsa de zero."""

    project_id: Uuid | None = None
