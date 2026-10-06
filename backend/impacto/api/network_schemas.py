"""Entradas da camada de rede (relação, proposta, anúncio, recado, relatório, perfil, persona).

O que está deliberadamente FORA destes modelos, porque é o servidor quem apura:
  * `status`/`publication_state` na criação — proposta, anúncio e relatório nascem em rascunho (gatilho no banco);
  * `version`, `sent_at`, `viewed_at`, `decided_at`, `decided_by`, `published_at`, `reviewed_by`, `submitted_at` —
    derivados da transição;
  * `metrics`, `milestones`, `evidence_count` do relatório — apurados de `indicator_values`, `milestones` e
    `evidences` no envio;
  * `confidence`, `priority` e `evidence` da recomendação — calculados pelo motor;
  * `public_fields` do perfil — projeção montada pelo servidor; o cliente só liga e desliga os interruptores;
  * `verified_badge` e `suspended` — da administração.
Deixar esses campos fora do contrato de entrada é o que impede "número bonito digitado à mão".
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import Field

from .schemas import Cents, In, Ods, Slug, Territory, Uuid

Note = Annotated[str, Field(min_length=3, max_length=2000)]
Handle = Annotated[str, Field(min_length=3, max_length=30)]

RelKind = Literal["favorite", "watchlist", "follow", "block", "contact", "partnership", "investment", "sponsorship",
                  "service", "mentorship", "volunteer", "collaboration", "support", "government_support",
                  "project_member", "project_partner", "project_sponsor", "project_investor", "referral",
                  "verified_by"]
TargetType = Literal["org", "user", "project", "solution", "call", "need", "idea"]
Visibility = Literal["private", "participants", "organization", "network", "public"]
RelStatus = Literal["pending", "active", "paused", "ended", "declined", "revoked"]

ProposalKind = Literal["investment", "sponsorship", "service", "partnership", "mentorship", "volunteer",
                       "collaboration", "project_support", "government_support"]
ProposalStatus = Literal["draft", "sent", "viewed", "in_review", "changes_requested", "accepted", "declined",
                         "expired", "withdrawn", "cancelled"]
SupportMode = Literal["financial", "service", "equipment", "knowledge", "volunteer", "sponsorship", "mentorship",
                      "other"]
Compensation = Literal["paid", "pro_bono", "volunteer", "partnership", "mentorship"]

SubjectType = Literal["project", "opportunity", "need", "service", "solution", "partnership", "sponsorship"]
Seeking = Literal["investment", "sponsorship", "partner", "professional", "volunteer", "mentorship", "equipment",
                  "knowledge", "quota"]
ListingState = Literal["draft", "review", "approved", "published", "paused", "expired", "archived", "suspended"]


# ---------------------------------------------------------------- relação
class RelationshipIn(In):
    kind: RelKind
    target_type: TargetType
    target_id: Uuid
    context_project_id: Uuid | None = None
    role: Slug | None = None
    # pedida, não garantida: `cap_visibility` rebaixa ao teto do tipo (bloqueio e favorito são sempre privados)
    visibility: Visibility = "private"
    note: Annotated[str | None, Field(max_length=2000)] = None
    evidence_document_id: Uuid | None = None


class RelationshipTransitionIn(In):
    to: RelStatus
    reason: Annotated[str | None, Field(max_length=500)] = None


class VisibilityIn(In):
    visibility: Visibility


class RelationshipQ(In):
    kind: RelKind | None = None
    status: RelStatus | None = None
    direction: Literal["in", "out", "all"] = "all"
    limit: Annotated[int, Field(ge=1, le=100)] = 50
    offset: Annotated[int, Field(ge=0, le=100000)] = 0


class GraphQ(In):
    depth: Annotated[int, Field(ge=1, le=2)] = 1
    limit: Annotated[int, Field(ge=1, le=200)] = 100


# ---------------------------------------------------------------- proposta
class ProposalIn(In):
    kind: ProposalKind
    receiver_org_id: Uuid
    title: Annotated[str, Field(min_length=3, max_length=200)]
    purpose: Annotated[str, Field(min_length=10, max_length=4000)]
    terms: Annotated[str | None, Field(max_length=8000)] = None
    amount_cents: Cents | None = None
    currency: Annotated[str, Field(pattern=r"^[A-Za-z]{3}$")] = "BRL"
    support_mode: SupportMode | None = None
    compensation: Compensation | None = None
    # ao menos um contexto é obrigatório — validado no motor, com mensagem que diz quais servem
    project_id: Uuid | None = None
    need_id: Uuid | None = None
    call_id: Uuid | None = None
    solution_id: Uuid | None = None
    expires_at: datetime | None = None


class ProposalPatch(In):
    title: Annotated[str | None, Field(min_length=3, max_length=200)] = None
    purpose: Annotated[str | None, Field(min_length=10, max_length=4000)] = None
    terms: Annotated[str | None, Field(max_length=8000)] = None
    amount_cents: Cents | None = None
    currency: Annotated[str | None, Field(pattern=r"^[A-Za-z]{3}$")] = None
    support_mode: SupportMode | None = None
    compensation: Compensation | None = None
    expires_at: datetime | None = None


class ProposalTransitionIn(In):
    to: Literal["sent", "viewed", "in_review", "changes_requested", "accepted", "declined", "withdrawn",
                "cancelled"]
    note: Annotated[str | None, Field(max_length=2000)] = None


class ProposalAttachIn(In):
    document_id: Uuid
    label: Annotated[str | None, Field(max_length=200)] = None


class ProposalQ(In):
    box: Literal["received", "sent", "all"] = "received"
    status: ProposalStatus | Literal["open"] | None = None
    kind: ProposalKind | None = None
    limit: Annotated[int, Field(ge=1, le=100)] = 50
    offset: Annotated[int, Field(ge=0, le=100000)] = 0


# ---------------------------------------------------------------- marketplace
class ListingIn(In):
    subject_type: SubjectType
    subject_id: Uuid
    headline: Annotated[str, Field(min_length=10, max_length=200)]
    summary: Annotated[str | None, Field(max_length=2000)] = None
    seeking: Annotated[list[Seeking], Field(max_length=9)] = []
    amount_target_cents: Cents | None = None
    currency: Annotated[str, Field(pattern=r"^[A-Za-z]{3}$")] = "BRL"
    territory: Territory | None = None
    causes: Annotated[list[Slug], Field(max_length=10)] = []
    ods: Annotated[list[Ods], Field(max_length=17)] = []
    esg_tags: Annotated[list[Slug], Field(max_length=10)] = []
    stage: Literal["idea", "building", "ready", "seeking", "executing", "completed"] | None = None
    expires_at: datetime | None = None


class ListingPatch(In):
    headline: Annotated[str | None, Field(min_length=10, max_length=200)] = None
    summary: Annotated[str | None, Field(max_length=2000)] = None
    seeking: Annotated[list[Seeking], Field(max_length=9)] | None = None
    amount_target_cents: Cents | None = None
    currency: Annotated[str | None, Field(pattern=r"^[A-Za-z]{3}$")] = None
    territory: Territory | None = None
    causes: Annotated[list[Slug], Field(max_length=10)] | None = None
    ods: Annotated[list[Ods], Field(max_length=17)] | None = None
    esg_tags: Annotated[list[Slug], Field(max_length=10)] | None = None
    stage: Literal["idea", "building", "ready", "seeking", "executing", "completed"] | None = None
    expires_at: datetime | None = None


class ListingTransitionIn(In):
    to: ListingState
    note: Annotated[str | None, Field(max_length=500)] = None


class ListingQ(In):
    state: ListingState | None = None
    limit: Annotated[int, Field(ge=1, le=100)] = 50
    offset: Annotated[int, Field(ge=0, le=100000)] = 0


class FeedQ(In):
    subject_type: SubjectType | None = None
    seeking: Seeking | None = None
    territory: Territory | None = None
    cause: Slug | None = None
    ods: Ods | None = None
    q: Annotated[str | None, Field(max_length=120)] = None
    limit: Annotated[int, Field(ge=1, le=50)] = 20
    offset: Annotated[int, Field(ge=0, le=10000)] = 0


# ---------------------------------------------------------------- conversa
class ThreadIn(In):
    other_org_id: Uuid
    subject: Annotated[str | None, Field(max_length=200)] = None
    project_id: Uuid | None = None
    proposal_id: Uuid | None = None
    need_id: Uuid | None = None
    call_id: Uuid | None = None
    # `false` só para contato social; relação profissional exige contexto e o motor recusa sem ele
    professional: bool = True


class MessageIn(In):
    body: Annotated[str, Field(min_length=1, max_length=8000)]
    kind: Literal["text", "proposal_ref", "document_ref"] = "text"
    ref_type: Literal["proposal", "document", "project", "relationship", "impact_update", "milestone"] | None = None
    ref_id: Uuid | None = None
    document_ids: Annotated[list[Uuid], Field(max_length=10)] = []


class ThreadQ(In):
    status: Literal["open", "archived", "closed"] | None = "open"
    project_id: Uuid | None = None
    limit: Annotated[int, Field(ge=1, le=50)] = 30
    offset: Annotated[int, Field(ge=0, le=10000)] = 0


class MessagesQ(In):
    limit: Annotated[int, Field(ge=1, le=100)] = 50
    before: datetime | None = None


class ThreadStatusIn(In):
    status: Literal["open", "archived", "closed"]


# ---------------------------------------------------------------- relatório de impacto
class ImpactUpdateIn(In):
    project_id: Uuid
    period_start: date
    period_end: date
    summary: Annotated[str, Field(min_length=20, max_length=8000)]
    outputs: Annotated[str | None, Field(max_length=4000)] = None
    outcomes: Annotated[str | None, Field(max_length=4000)] = None
    # dizer o que o dado NÃO prova é parte do relatório, não um extra
    limitations: Annotated[str | None, Field(max_length=2000)] = None
    risks_note: Annotated[str | None, Field(max_length=2000)] = None


class ImpactUpdatePatch(In):
    summary: Annotated[str | None, Field(min_length=20, max_length=8000)] = None
    outputs: Annotated[str | None, Field(max_length=4000)] = None
    outcomes: Annotated[str | None, Field(max_length=4000)] = None
    limitations: Annotated[str | None, Field(max_length=2000)] = None
    risks_note: Annotated[str | None, Field(max_length=2000)] = None
    document_id: Uuid | None = None


class ImpactUpdateTransitionIn(In):
    to: Literal["submitted", "under_review", "changes_requested", "accepted", "published", "draft"]
    note: Annotated[str | None, Field(max_length=2000)] = None


class ImpactUpdateQ(In):
    project_id: Uuid | None = None
    status: Literal["draft", "submitted", "under_review", "changes_requested", "accepted", "published"] | None = None
    limit: Annotated[int, Field(ge=1, le=50)] = 30
    offset: Annotated[int, Field(ge=0, le=10000)] = 0


class GatherQ(In):
    project_id: Uuid
    period_start: date
    period_end: date


# ---------------------------------------------------------------- perfil público
class ProfileIn(In):
    handle: Handle
    display_name: Annotated[str, Field(min_length=2, max_length=120)]
    headline: Annotated[str | None, Field(max_length=160)] = None
    bio: Annotated[str | None, Field(max_length=4000)] = None
    owner: Literal["org", "user"] = "org"


class ProfileLink(In):
    label: Annotated[str, Field(min_length=1, max_length=60)]
    url: Annotated[str, Field(pattern=r"^https?://", max_length=300)]


class ProfilePatch(In):
    handle: Handle | None = None
    display_name: Annotated[str | None, Field(min_length=2, max_length=120)] = None
    headline: Annotated[str | None, Field(max_length=160)] = None
    bio: Annotated[str | None, Field(max_length=4000)] = None
    visibility: Literal["public", "network", "private"] | None = None
    show_territory: bool | None = None
    show_projects: bool | None = None
    show_credentials: bool | None = None
    show_organizations: bool | None = None
    show_impact_history: bool | None = None
    show_contact: bool | None = None
    links: Annotated[list[ProfileLink], Field(max_length=8)] | None = None


class HandleQ(In):
    handle: Handle


class SuggestQ(In):
    base: Annotated[str, Field(min_length=2, max_length=120)]


# ---------------------------------------------------------------- persona e workspace
class PersonaIn(In):
    persona: Slug
    primary: bool = False


class WorkspaceQ(In):
    persona: Slug | None = None


class ReadinessQ(In):
    project_id: Uuid | None = None


class RecommendationQ(In):
    status: Literal["open", "done", "dismissed", "superseded", "expired"] = "open"
    limit: Annotated[int, Field(ge=1, le=50)] = 30


class RecommendationResolveIn(In):
    status: Literal["done", "dismissed"]
    reason: Annotated[str | None, Field(max_length=500)] = None


# ---------------------------------------------------------------- taxonomia e território
class TaxonomyQ(In):
    taxonomy: Slug | None = None
    include_inactive: bool = False


class TerritoryNeedIn(In):
    territory: Territory
    title: Annotated[str, Field(min_length=5, max_length=200)]
    description: Annotated[str | None, Field(max_length=4000)] = None
    cause: Slug | None = None
    ods: Annotated[list[Ods], Field(max_length=17)] = []
    # grupo beneficiário é atributo da NECESSIDADE, nunca de pessoa (ver usage_policy da taxonomia)
    beneficiary_groups: Annotated[list[Slug], Field(max_length=10)] = []
    # número exige fonte: o CHECK da tabela recusa estimativa sem origem declarada
    people_estimate: Annotated[int | None, Field(ge=0, le=100_000_000)] = None
    source_name: Annotated[str | None, Field(max_length=200)] = None
    source_url: Annotated[str | None, Field(pattern=r"^https?://", max_length=500)] = None
    source_date: date | None = None
    priority: Annotated[int, Field(ge=1, le=5)] = 3


class TerritoryNeedQ(In):
    territory: Territory | None = None
    cause: Slug | None = None
    status: Literal["open", "addressed", "closed"] | None = None
    limit: Annotated[int, Field(ge=1, le=100)] = 50
    offset: Annotated[int, Field(ge=0, le=10000)] = 0


# ---------------------------------------------------------------- experiência profissional
class ExperienceIn(In):
    org_name: Annotated[str, Field(min_length=2, max_length=200)]
    role: Annotated[str, Field(min_length=2, max_length=120)]
    org_id: Uuid | None = None
    project_id: Uuid | None = None
    description: Annotated[str | None, Field(max_length=2000)] = None
    started_on: date
    ended_on: date | None = None
    evidence_document_id: Uuid | None = None
    visibility: Literal["private", "network", "public"] = "network"


class ExperienceDecisionIn(In):
    decision: Literal["confirmed", "disputed"]
    note: Annotated[str | None, Field(max_length=1000)] = None


# ---------------------------------------------------------------- eventos de domínio
class EventQ(In):
    project_id: Uuid | None = None
    limit: Annotated[int, Field(ge=1, le=100)] = 50
    offset: Annotated[int, Field(ge=0, le=10000)] = 0
