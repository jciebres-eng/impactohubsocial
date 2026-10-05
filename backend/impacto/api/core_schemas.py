"""Entradas do núcleo do produto (ideia → projeto → diagnóstico → documento → acompanhamento).

Todo campo que o servidor calcula — completude, falta, situação de montagem, severidade de risco apontado por regra,
versão de diagnóstico — está FORA destes modelos de propósito: o cliente não dita o que a plataforma apura.
"""
from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import Field

from .schemas import In, Ods, Slug, Str, Territory, Uuid

Title = Annotated[str, Field(min_length=3, max_length=200)]
Reason = Annotated[str, Field(min_length=3, max_length=2000)]


# ---------------------------------------------------------------- ideias
class IdeaIn(In):
    title: Title
    problem: Annotated[str | None, Field(max_length=6000)] = None
    hypothesis: Annotated[str | None, Field(max_length=4000)] = None
    audience: Annotated[str | None, Field(max_length=2000)] = None
    territory: Territory | None = None
    solution_idea: Annotated[str | None, Field(max_length=6000)] = None
    expected_impact: Annotated[str | None, Field(max_length=4000)] = None
    causes: Annotated[list[Slug], Field(max_length=10)] = []
    ods: Annotated[list[Ods], Field(max_length=17)] = []
    # 'promoted' nunca é declarado: só a promoção para projeto coloca a ideia nesse estágio.
    stage: Literal["raw", "shaping", "ready", "archived"] = "raw"


class PromoteIn(In):
    title: Title | None = None
    summary: Annotated[str | None, Field(max_length=2000)] = None


# ---------------------------------------------------------------- ciclo de vida
class TransitionIn(In):
    to_status: Slug
    reason: Annotated[str | None, Field(max_length=2000)] = None
    evidence_document_id: Uuid | None = None


class SnapshotIn(In):
    label: Annotated[str, Field(min_length=2, max_length=120)]
    reason: Annotated[str, Field(max_length=200)] = "manual"


class CompareQ(In):
    a: Uuid
    b: Uuid


class RiskIn(In):
    category: Literal["financial", "operational", "legal", "documentary", "eligibility", "reputational", "technical",
                      "partnership", "timeline", "other"]
    title: Title
    description: Annotated[str | None, Field(max_length=4000)] = None
    probability: Literal["low", "medium", "high"] = "medium"
    impact: Literal["low", "medium", "high"] = "medium"
    mitigation: Annotated[str | None, Field(max_length=4000)] = None
    owner_user_id: Uuid | None = None
    review_date: date | None = None


class RiskUpdateIn(In):
    description: Annotated[str | None, Field(max_length=4000)] = None
    probability: Literal["low", "medium", "high"] | None = None
    impact: Literal["low", "medium", "high"] | None = None
    mitigation: Annotated[str | None, Field(max_length=4000)] = None
    owner_user_id: Uuid | None = None
    review_date: date | None = None
    status: Literal["open", "mitigating", "accepted", "resolved", "materialized", "dismissed"] | None = None
    resolution_note: Annotated[str | None, Field(max_length=2000)] = None


# ---------------------------------------------------------------- diagnóstico
class VersionCompareQ(In):
    a: Annotated[int, Field(ge=1, le=10000)]
    b: Annotated[int, Field(ge=1, le=10000)]


class ActionIn(In):
    """Ação declarada pela equipe. A ação apontada por regra nasce com a versão do diagnóstico, não por aqui."""

    title: Title
    detail: Annotated[str | None, Field(max_length=2000)] = None
    priority: Literal["critical", "high", "medium", "low"] = "medium"
    owner_user_id: Uuid | None = None
    due_on: date | None = None


class ActionUpdateIn(In):
    status: Literal["open", "in_progress", "done", "dismissed"] | None = None
    owner_user_id: Uuid | None = None
    due_on: date | None = None
    document_id: Uuid | None = None
    dismissed_reason: Annotated[str | None, Field(max_length=500)] = None


class AnalysisQ(In):
    project_id: Uuid | None = None


# ---------------------------------------------------------------- montagem de documento
class TemplateIn(In):
    code: Annotated[str, Field(min_length=3, max_length=60, pattern=r"^[a-z0-9_.-]{3,60}$")]
    version: Annotated[str, Field(min_length=1, max_length=20)]
    title: Title
    kind: Literal["project_technical", "work_plan", "budget", "schedule", "goal_matrix", "indicator_matrix",
                  "monitoring_plan", "report", "accountability", "presentation", "term", "contract", "letter",
                  "form", "annex", "other"]
    description: Annotated[str | None, Field(max_length=2000)] = None
    data_sources: Annotated[list[Slug], Field(max_length=12)] = []
    output_formats: Annotated[list[Literal["pdf", "docx", "odt"]], Field(min_length=1, max_length=3)] = ["pdf", "docx", "odt"]
    source_note: Annotated[str | None, Field(max_length=500)] = None


class TemplateFieldIn(In):
    section: Annotated[str, Field(min_length=1, max_length=120)]
    position: Annotated[int, Field(ge=1, le=500)]
    key: Annotated[str, Field(pattern=r"^[a-z0-9_.]{2,60}$")]
    label: Annotated[str, Field(min_length=2, max_length=200)]
    help: Annotated[str | None, Field(max_length=500)] = None
    field_type: Literal["text", "textarea", "number", "money", "date", "boolean", "enum", "list", "table", "ods",
                        "determinants", "indicator_ref", "document_ref"]
    options: Annotated[list[Str], Field(max_length=50)] = []
    required: bool = False
    derived_from: Annotated[str | None, Field(max_length=120)] = None
    requires_evidence: bool = False


class TemplateQ(In):
    kind: Slug | None = None
    status: Literal["draft", "published", "archived"] | None = None
    limit: Annotated[int, Field(ge=1, le=100)] = 25
    offset: Annotated[int, Field(ge=0, le=100000)] = 0


class AssemblyIn(In):
    template_id: Uuid
    title: Title
    project_id: Uuid | None = None
    diagnosis_id: Uuid | None = None
    application_id: Uuid | None = None


class AssemblyUpdateIn(In):
    title: Title | None = None
    values: dict[str, object] | None = None
    evidence: dict[str, Uuid] | None = None


class GenerateIn(In):
    format: Literal["pdf", "docx", "odt"] = "pdf"


class ReviewIn(In):
    approve: bool
    note: Annotated[str, Field(min_length=3, max_length=2000)]


class AssemblyQ(In):
    project_id: Uuid | None = None
    status: Literal["drafting", "ready", "blocked", "generated", "in_review", "approved", "rejected", "signed",
                    "archived"] | None = None
    limit: Annotated[int, Field(ge=1, le=100)] = 25
    offset: Annotated[int, Field(ge=0, le=100000)] = 0


# ---------------------------------------------------------------- match: retorno humano
class MatchFeedbackIn(In):
    feedback: Literal["accepted", "rejected", "ignored", "not_relevant", "contacted", "converted", "expired"]
    reason: Annotated[str | None, Field(max_length=1000)] = None


# ---------------------------------------------------------------- chaves e assinatura (administração)
class KeyRegisterIn(In):
    purpose: Literal["field", "integration", "signature_seal"]
    note: Annotated[str | None, Field(max_length=500)] = None


class ReencryptIn(In):
    table: Slug


class ProviderUpdateIn(In):
    state: Literal["unavailable", "configured", "sandbox", "homologation", "production", "degraded", "disabled"] | None = None
    activation_note: Annotated[str | None, Field(max_length=1000)] = None
    health_state: Literal["unknown", "healthy", "degraded", "unavailable"] | None = None
    health_detail: Annotated[str | None, Field(max_length=500)] = None


class SignaturePolicyIn(In):
    doc_kind: Annotated[str, Field(min_length=2, max_length=60)]
    min_legal_level: Literal["simple", "advanced", "qualified"]
    min_identity_level: Literal["none", "email", "phone", "document", "professional", "biometric"] = "email"
    require_timestamp: bool = False
    note: Annotated[str | None, Field(max_length=500)] = None
