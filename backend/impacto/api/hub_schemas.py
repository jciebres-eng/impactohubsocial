"""Modelos de entrada da Central de Conhecimento (v0.12.0)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import Field

from .schemas import In, Pagination, Uuid

Slug = Annotated[str, Field(pattern=r"^[a-z0-9-]{3,100}$")]
CtxKey = Annotated[str, Field(pattern=r"^[a-z0-9_.-]{2,80}$")]
Origin = Literal["official", "educational", "third_party"]
Visibility = Literal["public", "authenticated", "audience"]
Audience = list[Literal["osc", "company", "individual", "provider", "government"]]
Url = Annotated[str, Field(pattern=r"^https://", max_length=500)]
Reason = Annotated[str, Field(min_length=5, max_length=500)]


# ---------------------------------------------------------------- leitura / busca
class HelpSearchQ(In):
    q: Annotated[str | None, Field(max_length=200)] = None
    ctx: CtxKey | None = None
    type: Literal["article", "faq", "resource", "course", "event"] | None = None
    audience: Literal["osc", "company", "individual", "provider", "government"] | None = None
    category: Annotated[str | None, Field(max_length=60)] = None
    limit: Annotated[int, Field(ge=1, le=50)] = 20


class CtxQ(In):
    key: CtxKey


class AssistantIn(In):
    question: Annotated[str, Field(min_length=3, max_length=300)]
    ctx: CtxKey | None = None


class FeedbackIn(In):
    target_type: Literal["article", "faq", "resource", "course", "lesson", "event"]
    target_id: Uuid
    helpful: bool
    reason: Literal["not_found", "hard_to_understand", "outdated", "need_support", "other"] | None = None
    comment: Annotated[str | None, Field(max_length=1000)] = None


class ChecklistIn(In):
    scope: Annotated[str, Field(pattern=r"^[a-z0-9:_-]{3,140}$")]
    project_id: Uuid | None = None
    checked: Annotated[list[int], Field(max_length=200)]


class ResourcesQ(Pagination):
    kind: Literal["template", "document", "checklist", "video", "report", "bulletin", "spreadsheet", "other"] | None = None
    category: Annotated[str | None, Field(max_length=60)] = None
    q: Annotated[str | None, Field(max_length=120)] = None


class TemplateUseIn(In):
    values: dict[str, Annotated[str, Field(max_length=5000)]]
    title: Annotated[str | None, Field(max_length=200)] = None
    project_id: Uuid | None = None


# ---------------------------------------------------------------- suporte
class TicketIn(In):
    category: Literal["question", "bug", "technical", "document", "payment", "compliance", "project", "funding", "report", "partnership", "other"]
    subject: Annotated[str, Field(min_length=3, max_length=200)]
    message: Annotated[str, Field(min_length=5, max_length=8000)]
    context: dict[Literal["page", "field", "project_id", "article", "app"], Annotated[str, Field(max_length=200)]] = {}
    document_ids: Annotated[list[Uuid], Field(max_length=5)] = []


class TicketReplyIn(In):
    body: Annotated[str, Field(min_length=1, max_length=8000)]
    document_ids: Annotated[list[Uuid], Field(max_length=5)] = []
    internal: bool = False


class TicketRateIn(In):
    score: Annotated[int, Field(ge=1, le=5)]


class TicketStaffIn(In):
    status: Literal["open", "in_progress", "waiting_user", "waiting_internal", "resolved", "closed"] | None = None
    priority: Literal["low", "normal", "high", "critical"] | None = None
    assigned_to: Uuid | None = None
    assign: bool = False


class TicketQ(Pagination):
    status: Literal["open", "in_progress", "waiting_user", "waiting_internal", "resolved", "closed", "active"] | None = None
    priority: Literal["low", "normal", "high", "critical"] | None = None
    overdue: bool = False


class SlaIn(In):
    first_response_minutes: Annotated[int, Field(ge=5, le=100000)]
    resolution_minutes: Annotated[int, Field(ge=5, le=1000000)]
    escalate_after_minutes: Annotated[int, Field(ge=5, le=1000000)]


# ---------------------------------------------------------------- eventos / academia
class EventsQ(Pagination):
    when: Literal["upcoming", "past", "all"] = "upcoming"
    kind: Literal["webinar", "training", "workshop", "oficina", "mentoring", "demo", "institutional", "community"] | None = None


class EventRateIn(In):
    satisfaction: Annotated[int, Field(ge=1, le=5)]


class LessonDoneIn(In):
    answers: Annotated[list[Annotated[int, Field(ge=0, le=20)]] | None, Field(max_length=100)] = None


# ---------------------------------------------------------------- parcerias, demonstração, teste, boletim
class PartnershipIn(In):
    org_name: Annotated[str, Field(min_length=2, max_length=200)]
    contact_name: Annotated[str, Field(min_length=2, max_length=200)]
    contact_email: Annotated[str, Field(max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]
    contact_phone: Annotated[str | None, Field(max_length=40)] = None
    kind: Literal["institutional", "academic", "government", "business", "technology", "osc", "media", "research", "training", "distribution", "territorial"]
    objective: Annotated[str, Field(min_length=10, max_length=3000)]
    proposal: Annotated[str | None, Field(max_length=6000)] = None
    territory: Annotated[str | None, Field(max_length=300)] = None
    audience: Annotated[str | None, Field(max_length=500)] = None
    resources_offered: Annotated[str | None, Field(max_length=2000)] = None
    counterpart: Annotated[str | None, Field(max_length=2000)] = None
    target_date: date | None = None
    consent: bool
    website: Annotated[str | None, Field(max_length=100)] = None      # isca anti-bot (deve ficar vazio)


class DemoIn(In):
    org_name: Annotated[str, Field(min_length=2, max_length=200)]
    contact_name: Annotated[str, Field(min_length=2, max_length=200)]
    contact_email: Annotated[str, Field(max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]
    contact_phone: Annotated[str | None, Field(max_length=40)] = None
    audience_kind: Literal["osc", "company", "individual", "provider", "government", "other"]
    org_size: Literal["1-10", "11-50", "51-200", "200+"] | None = None
    interest: Annotated[str | None, Field(max_length=1000)] = None
    preferred_slots: Annotated[list[datetime], Field(max_length=3)] = []
    notes: Annotated[str | None, Field(max_length=2000)] = None
    consent: bool
    website: Annotated[str | None, Field(max_length=100)] = None


class TrialRequestIn(In):
    users_count: Annotated[int, Field(ge=1, le=10000)]
    purpose: Annotated[str, Field(min_length=10, max_length=2000)]
    modules: Annotated[list[Annotated[str, Field(max_length=60)]], Field(max_length=20)] = []
    period_days: Annotated[int, Field(ge=7, le=60)] = 14
    responsible: Annotated[str, Field(min_length=2, max_length=200)]


class DecisionIn(In):
    approve: bool
    reason: Annotated[str, Field(min_length=5, max_length=1000)]


class NewsletterIn(In):
    email: Annotated[str, Field(max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]
    topics: Annotated[list[Literal["platform", "opportunities", "events", "legislation", "technology", "esg", "ods", "cases", "trends", "results"]], Field(min_length=1, max_length=10)] = ["platform"]
    frequency: Literal["weekly", "monthly"] = "monthly"
    consent: bool
    website: Annotated[str | None, Field(max_length=100)] = None


class TokenIn(In):
    token: Annotated[str, Field(min_length=20, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")]


class PrefItem(In):
    grp: Literal["billing", "content", "events", "support", "partnerships", "opportunities",
                 "network", "proposal", "message", "funding", "report", "project", "document", "account",
                 "program"]
    in_app: bool
    email: bool
    # v0.20.0 — §23: quiet period, rate limit e agrupamento. Nulo significa "use o da plataforma",
    # que está declarado em `notification_policy` e sai na rota do catálogo.
    quiet_from: Annotated[str | None, Field(pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$")] = None
    quiet_to: Annotated[str | None, Field(pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$")] = None
    max_per_day: Annotated[int | None, Field(ge=1, le=1000)] = None
    digest: Literal["off", "daily"] = "off"


class PrefsIn(In):
    items: Annotated[list[PrefItem], Field(min_length=1, max_length=15)]   # 15 grupos desde a 0018


class PartnershipMoveIn(In):
    to: Literal["received", "qualification", "contact", "meeting", "proposal", "negotiation", "approved", "active", "completed", "archived", "rejected"]
    note: Annotated[str | None, Field(max_length=2000)] = None
    owner_id: Uuid | None = None


class NoteIn(In):
    body: Annotated[str, Field(min_length=1, max_length=4000)]


class DemoHandleIn(In):
    status: Literal["scheduled", "done", "cancelled"]
    scheduled_at: datetime | None = None
    meeting_url: Url | None = None


# ---------------------------------------------------------------- CMS (editorial)
class StepItem(In):
    title: Annotated[str, Field(min_length=1, max_length=200)]
    text: Annotated[str, Field(max_length=2000)] = ""


class RefItem(In):
    label: Annotated[str, Field(max_length=200)]
    url: Url
    source_date: date | None = None


class ArticleIn(In):
    slug: Slug
    kind: Literal["start", "how_it_works", "guide", "article", "policy", "glossary", "procedure"]
    category: Annotated[str | None, Field(max_length=60)] = None
    audience: Audience = []
    visibility: Visibility = "authenticated"
    origin: Origin = "official"
    tags: Annotated[list[Annotated[str, Field(max_length=40)]], Field(max_length=20)] = []
    ctx_keys: Annotated[list[CtxKey], Field(max_length=20)] = []
    est_minutes: Annotated[int | None, Field(ge=1, le=600)] = None
    required_docs: Annotated[list[Annotated[str, Field(max_length=120)]], Field(max_length=20)] = []
    action_label: Annotated[str | None, Field(max_length=80)] = None
    action_link: Annotated[str | None, Field(pattern=r"^/", max_length=200)] = None
    related_articles: Annotated[list[Slug], Field(max_length=20)] = []
    related_resources: Annotated[list[Slug], Field(max_length=20)] = []
    related_courses: Annotated[list[Slug], Field(max_length=20)] = []
    review_every_days: Annotated[int, Field(ge=7, le=1095)] = 180
    demo: bool = False
    title: Annotated[str, Field(min_length=3, max_length=200)]
    summary: Annotated[str | None, Field(max_length=600)] = None
    body: Annotated[str, Field(min_length=1, max_length=60000)]
    steps: Annotated[list[StepItem], Field(max_length=30)] = []
    checklist: Annotated[list[Annotated[str, Field(max_length=300)]], Field(max_length=50)] = []
    common_mistakes: Annotated[list[Annotated[str, Field(max_length=300)]], Field(max_length=20)] = []
    refs: Annotated[list[RefItem], Field(max_length=20)] = []
    regulatory: bool = False
    regulatory_source: Annotated[str | None, Field(max_length=500)] = None
    regulatory_date: date | None = None
    valid_until: date | None = None
    change_note: Annotated[str | None, Field(max_length=500)] = None


class VersionIn(In):
    title: Annotated[str, Field(min_length=3, max_length=200)]
    summary: Annotated[str | None, Field(max_length=600)] = None
    body: Annotated[str, Field(min_length=1, max_length=60000)]
    steps: Annotated[list[StepItem], Field(max_length=30)] = []
    checklist: Annotated[list[Annotated[str, Field(max_length=300)]], Field(max_length=50)] = []
    common_mistakes: Annotated[list[Annotated[str, Field(max_length=300)]], Field(max_length=20)] = []
    refs: Annotated[list[RefItem], Field(max_length=20)] = []
    regulatory: bool = False
    regulatory_source: Annotated[str | None, Field(max_length=500)] = None
    regulatory_date: date | None = None
    valid_until: date | None = None
    change_note: Annotated[str | None, Field(min_length=3, max_length=500)] = None


class TemplateField(In):
    key: Annotated[str, Field(pattern=r"^[a-z0-9_]{1,40}$")]
    label: Annotated[str, Field(max_length=120)]
    type: Literal["text", "textarea", "number", "date"] = "text"
    required: bool = False
    help: Annotated[str | None, Field(max_length=300)] = None


class TemplateSchema(In):
    draft_kind: Annotated[str, Field(max_length=40)]
    fields: Annotated[list[TemplateField], Field(min_length=1, max_length=40)]


class ResourceIn(In):
    slug: Slug
    kind: Literal["template", "document", "checklist", "video", "report", "bulletin", "spreadsheet", "other"]
    category: Annotated[str | None, Field(max_length=60)] = None
    title: Annotated[str, Field(min_length=3, max_length=200)]
    summary: Annotated[str | None, Field(max_length=1000)] = None
    audience: Audience = []
    visibility: Visibility = "authenticated"
    origin: Origin = "official"
    tags: Annotated[list[Annotated[str, Field(max_length=40)]], Field(max_length=20)] = []
    url: Url | None = None
    document_id: Uuid | None = None
    template_schema: TemplateSchema | None = None
    checklist_items: Annotated[list[Annotated[str, Field(max_length=300)]], Field(max_length=60)] = []
    duration_min: Annotated[int | None, Field(ge=1, le=1000)] = None
    period_start: date | None = None
    period_end: date | None = None
    ods: Annotated[list[Annotated[int, Field(ge=1, le=17)]], Field(max_length=17)] = []
    territories: Annotated[list[Annotated[str, Field(max_length=40)]], Field(max_length=30)] = []
    themes: Annotated[list[Annotated[str, Field(max_length=60)]], Field(max_length=20)] = []
    ctx_keys: Annotated[list[CtxKey], Field(max_length=20)] = []
    regulatory: bool = False
    regulatory_source: Annotated[str | None, Field(max_length=500)] = None
    regulatory_date: date | None = None
    valid_until: date | None = None
    change_note: Annotated[str | None, Field(max_length=500)] = None
    review_every_days: Annotated[int, Field(ge=7, le=1095)] = 365
    demo: bool = False


class FaqIn(In):
    question: Annotated[str, Field(min_length=5, max_length=300)]
    answer: Annotated[str, Field(min_length=5, max_length=8000)]
    category: Annotated[str | None, Field(max_length=60)] = None
    audience: Audience = []
    visibility: Visibility = "public"
    origin: Origin = "official"
    tags: Annotated[list[Annotated[str, Field(max_length=40)]], Field(max_length=20)] = []
    ctx_keys: Annotated[list[CtxKey], Field(max_length=20)] = []
    related_article: Slug | None = None
    review_every_days: Annotated[int, Field(ge=7, le=1095)] = 180
    sort: Annotated[int, Field(ge=0, le=10000)] = 100
    revises_id: Uuid | None = None
    demo: bool = False


class QuizQuestion(In):
    q: Annotated[str, Field(min_length=3, max_length=500)]
    options: Annotated[list[Annotated[str, Field(max_length=300)]], Field(min_length=2, max_length=8)]
    answer: Annotated[int, Field(ge=0, le=7)]
    explanation: Annotated[str | None, Field(max_length=500)] = None


class LessonIn(In):
    title: Annotated[str, Field(min_length=2, max_length=200)]
    kind: Literal["text", "video", "quiz", "activity"] = "text"
    body: Annotated[str | None, Field(max_length=40000)] = None
    video_url: Url | None = None
    captions_url: Url | None = None
    transcript: Annotated[str | None, Field(max_length=40000)] = None
    minutes: Annotated[int | None, Field(ge=1, le=600)] = None
    materials: Annotated[list[dict[str, Annotated[str, Field(max_length=300)]]], Field(max_length=20)] = []
    quiz: Annotated[list[QuizQuestion], Field(max_length=50)] = []


class ModuleIn(In):
    title: Annotated[str, Field(min_length=2, max_length=200)]
    description: Annotated[str | None, Field(max_length=1000)] = None
    lessons: Annotated[list[LessonIn], Field(min_length=1, max_length=40)]


class CourseIn(In):
    slug: Slug
    title: Annotated[str, Field(min_length=3, max_length=200)]
    summary: Annotated[str | None, Field(max_length=1000)] = None
    audience: Audience = []
    visibility: Visibility = "authenticated"
    origin: Origin = "educational"
    level: Literal["beginner", "intermediate", "advanced"] = "beginner"
    hours: Annotated[float | None, Field(gt=0, le=400)] = None
    pass_score: Annotated[int, Field(ge=0, le=100)] = 70
    cert_enabled: bool = False
    tags: Annotated[list[Annotated[str, Field(max_length=40)]], Field(max_length=20)] = []
    review_every_days: Annotated[int, Field(ge=7, le=1095)] = 365
    demo: bool = False
    modules: Annotated[list[ModuleIn], Field(min_length=1, max_length=30)]


class PathIn(In):
    slug: Slug
    title: Annotated[str, Field(min_length=3, max_length=200)]
    description: Annotated[str | None, Field(max_length=1000)] = None
    audience: Audience = []
    visibility: Visibility = "authenticated"
    items: Annotated[list[dict[Literal["type", "slug", "title"], Annotated[str, Field(max_length=200)]]], Field(min_length=1, max_length=30)]
    demo: bool = False


class EventIn(In):
    slug: Slug
    kind: Literal["webinar", "training", "workshop", "oficina", "mentoring", "demo", "institutional", "community"]
    title: Annotated[str, Field(min_length=3, max_length=200)]
    description: Annotated[str | None, Field(max_length=6000)] = None
    starts_at: datetime
    duration_min: Annotated[int, Field(ge=5, le=1440)]
    speaker: Annotated[str | None, Field(max_length=300)] = None
    modality: Literal["online", "in_person", "hybrid"] = "online"
    location: Annotated[str | None, Field(max_length=300)] = None
    join_url: Url | None = None
    capacity: Annotated[int | None, Field(ge=1)] = None
    registration_open: bool = True
    audience: Audience = []
    visibility: Visibility = "public"
    demo: bool = False


class EventPatchIn(In):
    description: Annotated[str | None, Field(max_length=6000)] = None
    starts_at: datetime | None = None
    duration_min: Annotated[int | None, Field(ge=5, le=1440)] = None
    capacity: Annotated[int | None, Field(ge=1)] = None
    registration_open: bool | None = None
    recording_url: Url | None = None
    summary: Annotated[str | None, Field(max_length=4000)] = None
    status: Literal["cancelled", "completed"] | None = None
    join_url: Url | None = None


class AttendanceIn(In):
    user_ids: Annotated[list[Uuid], Field(max_length=500)]


class TransitionIn(In):
    to: Literal["draft", "review", "approved", "published", "archived"]
    note: Annotated[str | None, Field(max_length=1000)] = None


class ReviewedIn(In):
    note: Annotated[str | None, Field(max_length=500)] = None


class CategoryIn(In):
    slug: Annotated[str, Field(pattern=r"^[a-z0-9-]{2,60}$")]
    name: Annotated[str, Field(min_length=2, max_length=120)]
    description: Annotated[str | None, Field(max_length=500)] = None
    sort: Annotated[int, Field(ge=0, le=10000)] = 100


class StaffRoleIn(In):
    email: Annotated[str, Field(max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]
    role: Literal["editor", "reviewer", "support"]


class AdminListQ(Pagination):
    status: Annotated[str | None, Field(max_length=30)] = None
    q: Annotated[str | None, Field(max_length=100)] = None


class RevokeCertIn(In):
    reason: Reason
