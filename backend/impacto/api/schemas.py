"""Modelos de entrada (pydantic v2). Todos rejeitam campos desconhecidos e aparam espaços."""
from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

Str = Annotated[str, StringConstraints(strip_whitespace=True)]
Email = Annotated[str, StringConstraints(strip_whitespace=True, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]
Territory = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^(INT|[A-Z]{2}(-[A-Z]{2}(-[0-9]{7})?)?)$")]
UF = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Z]{2}$")]
Slug = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[a-z0-9_]{2,60}$")]
Cents = Annotated[int, Field(ge=0, le=10_000_000_000_00)]
Uuid = Annotated[str, StringConstraints(pattern=r"^[0-9a-fA-F-]{36}$")]
Ods = Annotated[int, Field(ge=1, le=17)]


class In(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("*", mode="after")
    @classmethod
    def _refuse_naive_datetime(cls, value):
        """Prazo sem fuso é recusado com 422 — e NÃO é convertido por adivinhação.

        ACHADO DA JORNADA DE PONTA A PONTA (v0.18.1): `POST /v1/calls` com
        `closes_at: "2026-12-05"` — exatamente o que um seletor de data produz — devolvia **500**.
        O driver recusa `datetime` sem fuso (e está certo: o banco guarda `timestamptz`), mas a
        recusa chegava como erro interno em vez de erro de entrada.

        Adivinhar o fuso seria pior que o 500: deslocaria o vencimento de um edital em horas, e o
        encerramento às 23h59 de Rio Branco não é o mesmo instante que o de Brasília. Então a
        plataforma diz o que falta, com exemplo, e deixa a decisão com quem tem a informação.
        """
        itens = value if isinstance(value, (list, tuple)) else (value,)
        for item in itens:
            if isinstance(item, datetime) and item.tzinfo is None:
                raise ValueError(
                    "informe o fuso horário no prazo (ex.: 2026-12-05T23:59:00-03:00). A "
                    "plataforma não adivinha fuso: 23h59 em Rio Branco não é o mesmo instante "
                    "que 23h59 em Brasília, e a diferença muda quem consegue inscrever a tempo.")
        return value


# ---------------------------------------------------------------- auth
class OrgIn(In):
    kind: Literal["osc", "company", "provider", "government", "individual"]
    legal_name: Annotated[str, Field(min_length=2, max_length=200)]
    trade_name: Annotated[str | None, Field(max_length=200)] = None
    cnpj: Annotated[str | None, Field(max_length=20)] = None
    uf: UF | None = None
    city: Annotated[str | None, Field(max_length=120)] = None
    legal_nature_code: Slug | None = None


class RegisterIn(In):
    email: Email
    password: Annotated[str, Field(min_length=1, max_length=256)]
    full_name: Annotated[str, Field(min_length=2, max_length=160)]
    accept_terms: bool
    organization: OrgIn | None = None


class LoginIn(In):
    email: Email
    password: Annotated[str, Field(min_length=1, max_length=256)]
    org_id: Uuid | None = None


class MfaLoginIn(In):
    mfa_token: Annotated[str, Field(min_length=10, max_length=200)]
    code: Annotated[str | None, Field(max_length=10)] = None
    recovery_code: Annotated[str | None, Field(max_length=20)] = None


class RefreshIn(In):
    refresh_token: Annotated[str | None, Field(max_length=200)] = None


class TokenIn(In):
    token: Annotated[str, Field(min_length=10, max_length=200)]


class EmailIn(In):
    email: Email


class ResetIn(In):
    token: Annotated[str, Field(min_length=10, max_length=200)]
    password: Annotated[str, Field(min_length=1, max_length=256)]


class ChangePasswordIn(In):
    current_password: Annotated[str, Field(min_length=1, max_length=256)]
    new_password: Annotated[str, Field(min_length=1, max_length=256)]


class CodeIn(In):
    code: Annotated[str, Field(min_length=6, max_length=10)]


class MfaDisableIn(In):
    password: Annotated[str, Field(min_length=1, max_length=256)]
    code: Annotated[str, Field(min_length=6, max_length=10)]


class SwitchOrgIn(In):
    org_id: Uuid


class InviteIn(In):
    email: Email
    role: Literal["admin", "manager", "analyst", "member", "viewer"]


class RoleIn(In):
    role: Literal["admin", "manager", "analyst", "member", "viewer"]


# ---------------------------------------------------------------- organizações e perfis
class OrgProfileIn(In):
    legal_name: Annotated[str | None, Field(min_length=2, max_length=200)] = None
    trade_name: Annotated[str | None, Field(max_length=200)] = None
    legal_nature: Annotated[str | None, Field(max_length=120)] = None
    founded_on: date | None = None
    description: Annotated[str | None, Field(max_length=5000)] = None
    website: Annotated[str | None, Field(max_length=300, pattern=r"^https?://")] = None
    contact_email: Email | None = None
    phone: Annotated[str | None, Field(max_length=40)] = None
    city: Annotated[str | None, Field(max_length=120)] = None
    uf: UF | None = None
    ibge_code: Annotated[str | None, Field(pattern=r"^[0-9]{7}$")] = None
    territories: list[Territory] | None = Field(default=None, max_length=50)
    causes: list[Slug] | None = Field(default=None, max_length=20)
    ods: list[Ods] | None = Field(default=None, max_length=17)
    esg_focus: list[Slug] | None = Field(default=None, max_length=20)
    certifications: list[Slug] | None = Field(default=None, max_length=20)
    team_size: Annotated[int | None, Field(ge=0, le=1_000_000)] = None
    annual_revenue_cents: Cents | None = None


class FunderProfileIn(In):
    accepted_legal_natures: list[Slug] = Field(default_factory=list, max_length=20)
    required_qualifications: list[Slug] = Field(default_factory=list, max_length=20)
    min_maturity: Annotated[int | None, Field(ge=0, le=6)] = None
    funding_modalities: list[Slug] = Field(default_factory=list, max_length=20)
    causes: list[Slug] = Field(default_factory=list, max_length=30)
    ods: list[Ods] = Field(default_factory=list, max_length=17)
    esg_focus: list[Slug] = Field(default_factory=list, max_length=20)
    territories: list[Territory] = Field(default_factory=list, max_length=50)
    excluded_causes: list[Slug] = Field(default_factory=list, max_length=30)
    excluded_territories: list[Territory] = Field(default_factory=list, max_length=50)
    ticket_min_cents: Cents | None = None
    ticket_max_cents: Cents | None = None
    annual_budget_cents: Cents | None = None
    required_document_types: list[Slug] = Field(default_factory=list, max_length=30)
    min_org_age_months: Annotated[int | None, Field(ge=0, le=1200)] = None
    accepts_fractioning: bool = True
    policies: Annotated[str | None, Field(max_length=5000)] = None
    public_name: bool = False   # PF: só mostra o nome às OSCs com opt-in explícito


class ProviderProfileIn(In):
    services: list[Annotated[str, Field(min_length=2, max_length=120)]] = Field(default_factory=list, max_length=30)
    categories: list[Slug] = Field(default_factory=list, max_length=10)
    remote: bool = True
    territories: list[Territory] = Field(default_factory=list, max_length=50)
    languages: list[Annotated[str, Field(max_length=10)]] = Field(default_factory=lambda: ["pt-BR"], max_length=10)
    accessibility: Annotated[str | None, Field(max_length=500)] = None
    price_info: Annotated[str | None, Field(max_length=500)] = None
    accepting_requests: bool = True


class CredentialIn(In):
    council: Annotated[str, Field(pattern=r"^[A-Z]{2,8}$")]
    number: Annotated[str, Field(min_length=1, max_length=40)]
    uf: UF | None = None
    holder_name: Annotated[str, Field(min_length=2, max_length=160)]
    valid_until: date | None = None
    document_id: Uuid | None = None


class TaxProfileIn(In):
    regime: Literal["lucro_real", "lucro_presumido", "simples", "isenta", "unknown"]
    fiscal_year: Annotated[int | None, Field(ge=2000, le=2100)] = None
    estimated_ir_due_cents: Cents | None = None
    uf: UF | None = None


# ---------------------------------------------------------------- chamadas / editais
class Requirement(In):
    code: Slug
    label: Annotated[str, Field(min_length=2, max_length=200)]
    detail: Annotated[str | None, Field(max_length=1000)] = None
    mandatory: bool = True
    how_to_fix: Annotated[str | None, Field(max_length=500)] = None


class StepTemplate(In):
    code: Slug
    title: Annotated[str, Field(min_length=2, max_length=200)]
    description: Annotated[str | None, Field(max_length=2000)] = None
    kind: Literal["requirement", "document", "writing", "review", "signature", "submission", "followup"] = "writing"
    mandatory: bool = True


class CallIn(In):
    title: Annotated[str, Field(min_length=3, max_length=300)]
    funder_name: Annotated[str | None, Field(min_length=2, max_length=200)] = None
    summary: Annotated[str | None, Field(max_length=2000)] = None
    description: Annotated[str | None, Field(max_length=20000)] = None
    url: Annotated[str | None, Field(max_length=500, pattern=r"^https?://")] = None
    sphere: Literal["private", "federal", "state", "municipal", "local", "international"] = "private"
    instrument: Literal["grant", "edital", "fund", "financing", "prize", "incentive_law", "donation", "other"] = "edital"
    causes: list[Slug] = Field(default_factory=list, max_length=20)
    ods: list[Ods] = Field(default_factory=list, max_length=17)
    territories: list[Territory] = Field(default_factory=list, max_length=100)
    eligible_org_types: list[Literal["osc", "company", "provider", "government"]] = Field(default_factory=lambda: ["osc"])
    funding_modality: Slug | None = None
    accepted_legal_natures: list[Slug] = Field(default_factory=list, max_length=20)
    min_maturity: Annotated[int | None, Field(ge=0, le=6)] = None
    budget_total_cents: Cents | None = None
    ticket_min_cents: Cents | None = None
    ticket_max_cents: Cents | None = None
    counterpart_pct: Annotated[float | None, Field(ge=0, le=100)] = None
    min_org_age_months: Annotated[int | None, Field(ge=0, le=1200)] = None
    required_document_types: list[Slug] = Field(default_factory=list, max_length=30)
    required_certifications: list[Slug] = Field(default_factory=list, max_length=20)
    requirements: list[Requirement] = Field(default_factory=list, max_length=50)
    steps_template: list[StepTemplate] = Field(default_factory=list, max_length=40)
    opens_at: datetime | None = None
    closes_at: datetime | None = None
    status: Literal["draft", "open", "closed", "archived"] = "draft"
    managed_on_platform: bool = True
    weights: dict[str, Annotated[float, Field(ge=0, le=100)]] | None = None

    @field_validator("ticket_max_cents")
    @classmethod
    def _tickets(cls, v, info):
        mn = info.data.get("ticket_min_cents")
        if v is not None and mn is not None and v < mn:
            raise ValueError("ticket máximo menor que o mínimo")
        return v


class CallSearchQ(In):
    q: Annotated[str | None, Field(max_length=120)] = None
    sphere: Annotated[str | None, Field(max_length=200)] = None
    instrument: Annotated[str | None, Field(max_length=200)] = None
    cause: Annotated[str | None, Field(max_length=300)] = None
    territory: Territory | None = None
    status: Literal["open", "closed", "all"] = "open"
    closes_before: date | None = None
    min_amount_cents: Cents | None = None
    mine: bool = False
    limit: Annotated[int, Field(ge=1, le=100)] = 25
    offset: Annotated[int, Field(ge=0, le=100000)] = 0


class SavedSearchIn(In):
    name: Annotated[str, Field(min_length=1, max_length=120)]
    filters: dict = Field(default_factory=dict)
    notify: bool = True
    frequency: Literal["instant", "daily", "weekly"] = "daily"


class MaterialIn(In):
    title: Annotated[str, Field(min_length=3, max_length=300)]
    summary: Annotated[str | None, Field(max_length=3000)] = None
    category: Literal["guide", "legislation", "template", "data", "manual", "training", "other"]
    url: Annotated[str | None, Field(max_length=500, pattern=r"^https?://")] = None
    document_id: Uuid | None = None
    territories: list[Territory] = Field(default_factory=list, max_length=50)
    causes: list[Slug] = Field(default_factory=list, max_length=20)
    status: Literal["draft", "published", "archived"] = "draft"


# ---------------------------------------------------------------- projetos
class Indicator(In):
    name: Annotated[str, Field(min_length=2, max_length=120)]
    unit: Annotated[str | None, Field(max_length=40)] = None
    baseline: float | None = None
    target: float | None = None


class ProjectIn(In):
    title: Annotated[str, Field(min_length=3, max_length=200)]
    summary: Annotated[str | None, Field(max_length=2000)] = None
    problem: Annotated[str | None, Field(max_length=8000)] = None
    objectives: Annotated[str | None, Field(max_length=8000)] = None
    methodology: Annotated[str | None, Field(max_length=12000)] = None
    causes: list[Slug] = Field(default_factory=list, max_length=10)
    ods: list[Ods] = Field(default_factory=list, max_length=17)
    esg_tags: list[Slug] = Field(default_factory=list, max_length=10)
    territory: Territory
    beneficiaries_count: Annotated[int | None, Field(ge=0, le=100_000_000)] = None
    beneficiaries_description: Annotated[str | None, Field(max_length=2000)] = None
    budget_total_cents: Cents | None = None
    urgency: Literal["low", "medium", "high"] = "medium"
    starts_on: date | None = None
    ends_on: date | None = None
    indicators: list[Indicator] = Field(default_factory=list, max_length=20)
    ai_assisted: bool = False


class ProjectPatch(ProjectIn):
    title: Annotated[str | None, Field(min_length=3, max_length=200)] = None
    territory: Territory | None = None
    urgency: Literal["low", "medium", "high"] | None = None


class BudgetItemIn(In):
    description: Annotated[str, Field(min_length=1, max_length=300)]
    category: Literal["material", "service", "personnel", "equipment", "infrastructure", "travel", "administrative", "other"] = "material"
    quantity: Annotated[float, Field(gt=0, le=10_000_000)]
    unit_cost_cents: Cents


class MilestoneIn(In):
    title: Annotated[str, Field(min_length=2, max_length=200)]
    description: Annotated[str | None, Field(max_length=4000)] = None
    amount_cents: Cents
    due_on: date | None = None


# ---------------------------------------------------------------- candidaturas e execução
class ApplyIn(In):
    call_id: Uuid
    project_id: Uuid | None = None
    requested_cents: Cents | None = None
    track_external: bool = False


class InterestIn(In):
    project_id: Uuid
    call_id: Uuid | None = None
    note: Annotated[str | None, Field(max_length=2000)] = None


class TransitionIn(In):
    to_status: Literal["draft", "submitted", "screening", "due_diligence", "approved", "rejected", "withdrawn",
                       "committed", "in_execution", "reporting", "closed"]
    note: Annotated[str | None, Field(max_length=2000)] = None
    external_protocol: Annotated[str | None, Field(max_length=120)] = None


class StepPatch(In):
    status: Literal["todo", "in_progress", "done", "blocked", "not_applicable"]
    note: Annotated[str | None, Field(max_length=2000)] = None
    document_id: Uuid | None = None


class ConflictIn(In):
    has_conflict: bool
    description: Annotated[str | None, Field(max_length=2000)] = None


class CommitmentIn(In):
    amount_cents: Annotated[int, Field(gt=0, le=10_000_000_000_00)]
    milestone_id: Uuid | None = None
    reference: Annotated[str | None, Field(max_length=200)] = None


class CommitmentStatusIn(In):
    status: Literal["disbursed", "confirmed", "cancelled"]
    reference: Annotated[str | None, Field(max_length=200)] = None


class ExpenseIn(In):
    description: Annotated[str, Field(min_length=2, max_length=500)]
    amount_cents: Annotated[int, Field(gt=0, le=10_000_000_000_00)]
    paid_on: date
    supplier_name: Annotated[str | None, Field(max_length=200)] = None
    supplier_cnpj: Annotated[str | None, Field(max_length=20)] = None
    milestone_id: Uuid | None = None
    commitment_id: Uuid | None = None
    budget_item_id: Uuid | None = None
    document_id: Uuid | None = None
    procurement_request_id: Uuid | None = None


class ReviewDecisionIn(In):
    status: Literal["accepted", "rejected", "needs_info", "validated", "questioned"]
    note: Annotated[str | None, Field(max_length=2000)] = None


class EvidenceIn(In):
    kind: Literal["photo", "video", "report", "attendance", "invoice", "result", "other"]
    title: Annotated[str, Field(min_length=2, max_length=200)]
    description: Annotated[str | None, Field(max_length=4000)] = None
    occurred_on: date | None = None
    milestone_id: Uuid | None = None
    application_id: Uuid | None = None
    document_id: Uuid | None = None
    indicator_name: Annotated[str | None, Field(max_length=120)] = None
    indicator_value: float | None = None


class FeedbackIn(In):
    kind: Literal["funder_feedback", "progress_report", "final_report"]
    body: Annotated[str, Field(min_length=2, max_length=8000)]
    rating: Annotated[int | None, Field(ge=1, le=5)] = None
    application_id: Uuid | None = None
    document_id: Uuid | None = None


# ---------------------------------------------------------------- documentos, rascunhos, revisão profissional
class DraftIn(In):
    kind: Literal["project_proposal", "work_plan", "budget_justification", "cover_letter", "progress_report", "final_report", "other"]
    title: Annotated[str, Field(min_length=2, max_length=200)]
    content: Annotated[str, Field(min_length=1, max_length=100000)]
    project_id: Uuid | None = None
    application_id: Uuid | None = None
    ai_assisted: bool = False


class DraftPatch(In):
    title: Annotated[str | None, Field(min_length=2, max_length=200)] = None
    content: Annotated[str | None, Field(min_length=1, max_length=100000)] = None


class ReviewRequestIn(In):
    professional_org_id: Uuid
    subject_type: Literal["draft", "document", "application", "project"]
    subject_id: Uuid
    scope: Annotated[str, Field(min_length=3, max_length=2000)]
    due_on: date | None = None


class ReviewRespondIn(In):
    status: Literal["accepted", "declined", "changes_requested", "approved", "cancelled"]
    note: Annotated[str | None, Field(max_length=4000)] = None
    credential_id: Uuid | None = None


class SignIn(In):
    subject_type: Literal["draft", "document"]
    subject_id: Uuid
    role: Literal["professional", "legal_representative", "funder"]
    statement: Annotated[str, Field(min_length=10, max_length=2000)]
    review_id: Uuid | None = None
    credential_id: Uuid | None = None
    password: Annotated[str, Field(min_length=1, max_length=256)]
    # Segunda camada (v0.14.0): código de uso único pedido em POST /v1/signatures/challenge e ligado ao hash do conteúdo.
    code: Annotated[str, Field(min_length=4, max_length=12)]


class DocPatch(In):
    title: Annotated[str | None, Field(min_length=1, max_length=200)] = None
    valid_until: date | None = None
    visibility: Literal["private", "parties", "public"] | None = None


# ---------------------------------------------------------------- IA
class AiStructureIn(In):
    text: Annotated[str, Field(min_length=10, max_length=20000)]


class AiDraftIn(In):
    kind: Literal["project_proposal", "work_plan", "budget_justification", "cover_letter", "progress_report", "final_report"]
    project_id: Uuid
    call_id: Uuid | None = None
    instructions: Annotated[str | None, Field(max_length=2000)] = None


class AiSummarizeIn(In):
    project_id: Uuid


# ---------------------------------------------------------------- billing
class AgreementJoinIn(In):
    code: Annotated[str, Field(min_length=6, max_length=40)]


class VoucherRedeemIn(In):
    code: Annotated[str, Field(min_length=6, max_length=40)]


class ReportIn(In):
    target_type: Literal["organization", "project", "call", "document", "user", "message", "solution"]
    target_id: Uuid
    reason: Literal["fraud", "inappropriate", "incorrect_data", "conflict", "privacy", "other"]
    details: Annotated[str | None, Field(max_length=4000)] = None
    #: Colunas que existiam no banco desde a v0.16.0 e que NENHUMA rota escrevia. A categoria é a
    #: mesma lista do CHECK da tabela e de ENF.CATEGORIES — uma só, desde a migração 0038.
    category: Annotated[str | None, Field(pattern="^[a-z_]{3,30}$")] = None
    evidence_document_id: Uuid | None = None


class FeedFeedbackIn(In):
    action: Literal["dismiss", "save"]
    reason: Annotated[str | None, Field(max_length=300)] = None


class Pagination(In):
    limit: Annotated[int, Field(ge=1, le=100)] = 25
    offset: Annotated[int, Field(ge=0, le=100000)] = 0


class FeedQ(Pagination):
    call_id: Uuid | None = None
    cause: Annotated[str | None, Field(max_length=60)] = None
    territory: Territory | None = None
    include_blocked: bool = False


# ---------------------------------------------------------------- v0.8.0: impacto, ODS, indicadores, grafo, diagnóstico
Code = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[a-z0-9_.-]{2,80}$")]
TargetCode = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[0-9]{1,2}\.[0-9a-z]{1,2}$")]
LinkType = Literal["observed_evidence", "correlation", "hypothesis", "association", "inference", "validated_causality"]


class OdsTargetItem(In):
    ods: Ods
    target_code: TargetCode | None = None
    rationale: Annotated[str | None, Field(max_length=2000)] = None


class OdsTargetsIn(In):
    items: list[OdsTargetItem] = Field(max_length=40)


class IndicatorCatalogIn(In):
    code: Code
    name: Annotated[str, Field(min_length=3, max_length=200)]
    unit: Annotated[str, Field(min_length=1, max_length=40)]
    definition: Annotated[str | None, Field(max_length=2000)] = None
    esg_dimension: Literal["E", "S", "G"] | None = None
    ods: Ods | None = None
    ods_target: TargetCode | None = None


class ProjectIndicatorIn(In):
    indicator_id: Uuid
    baseline: Annotated[float | None, Field(ge=-1e12, le=1e12)] = None
    #: Obrigatória quando há linha de base (gatilho na 0025). Número de partida sem fonte é número
    #: inventado, e o projeto inteiro passa a medir o progresso contra ele.
    baseline_source: Annotated[str | None, Field(min_length=3, max_length=300)] = None
    baseline_date: date | None = None
    target: Annotated[float | None, Field(ge=-1e12, le=1e12)] = None
    target_date: date | None = None
    method: Annotated[str | None, Field(max_length=1000)] = None


class IndicatorValueIn(In):
    value: Annotated[float, Field(ge=-1e12, le=1e12)]
    measured_on: date
    evidence_id: Uuid | None = None
    note: Annotated[str | None, Field(max_length=2000)] = None


class IndicatorValueReviewIn(In):
    status: Literal["validated", "rejected"]
    note: Annotated[str | None, Field(max_length=2000)] = None


class NodeIn(In):
    kind: Literal["need", "activity", "output", "outcome", "impact", "population", "context"]
    label: Annotated[str, Field(min_length=2, max_length=200)]
    description: Annotated[str | None, Field(max_length=2000)] = None


class EdgeIn(In):
    from_node: Uuid
    to_node: Uuid
    link_type: LinkType = "hypothesis"
    evidence_id: Uuid | None = None
    note: Annotated[str | None, Field(max_length=2000)] = None


class EdgeValidateIn(In):
    evidence_id: Uuid
    note: Annotated[str, Field(min_length=10, max_length=2000)]


class DiagnosisIn(In):
    title: Annotated[str, Field(min_length=3, max_length=200)]
    project_id: Uuid | None = None
    need_statement: Annotated[str | None, Field(max_length=6000)] = None
    affected_group: Annotated[str | None, Field(max_length=2000)] = None
    root_causes: list[dict] = Field(default_factory=list, max_length=20)
    objective: Annotated[str | None, Field(max_length=4000)] = None
    goals: list[dict] = Field(default_factory=list, max_length=20)
    action_plan: list[dict] = Field(default_factory=list, max_length=40)
    risks: list[dict] = Field(default_factory=list, max_length=20)
    data_sources: list[dict] = Field(default_factory=list, max_length=20)

    @field_validator("root_causes", "goals", "action_plan", "risks", "data_sources")
    @classmethod
    def _small_items(cls, v):
        for it in v:
            if len(str(it)) > 2000:
                raise ValueError("item muito grande")
        return v


# ---------------------------------------------------------------- compras
class ProcurementPolicyIn(In):
    min_quotes: Annotated[int, Field(ge=1, le=10)] = 3
    quote_threshold_cents: Cents = 0
    outlier_pct: Annotated[float, Field(ge=1, le=500)] = 30
    exception_needs_approval: bool = True


class SupplierIn(In):
    name: Annotated[str, Field(min_length=2, max_length=200)]
    cnpj: Annotated[str | None, Field(max_length=20)] = None
    category: Annotated[str | None, Field(max_length=80)] = None


class ProcurementRequestIn(In):
    description: Annotated[str, Field(min_length=3, max_length=500)]
    estimated_cents: Annotated[int, Field(gt=0, le=10_000_000_000_00)]
    budget_item_id: Uuid | None = None


class QuotationIn(In):
    supplier_name: Annotated[str, Field(min_length=2, max_length=200)]
    supplier_cnpj: Annotated[str | None, Field(max_length=20)] = None
    amount_cents: Annotated[int, Field(gt=0, le=10_000_000_000_00)]
    valid_until: date | None = None
    document_id: Uuid | None = None
    notes: Annotated[str | None, Field(max_length=1000)] = None


class ProcurementDecisionIn(In):
    quotation_id: Uuid | None = None
    reason: Annotated[str | None, Field(max_length=2000)] = None
    exception_reason: Annotated[str | None, Field(max_length=2000)] = None


# ---------------------------------------------------------------- contribuição e pagamentos
class ContributionModelIn(In):
    kind: Literal["donation", "sponsorship", "quota", "incentive_law", "impact_investment"]
    title: Annotated[str, Field(min_length=3, max_length=200)]
    description: Annotated[str | None, Field(max_length=4000)] = None
    legal_structure: Annotated[str | None, Field(max_length=1000)] = None
    refundable: bool = False
    refund_policy: Annotated[str | None, Field(max_length=2000)] = None
    min_contribution_cents: Cents | None = None
    quota_value_cents: Annotated[int | None, Field(gt=0, le=10_000_000_000_00)] = None
    quotas_total: Annotated[int | None, Field(gt=0, le=1_000_000)] = None


class LegalDecisionIn(In):
    approve: bool
    note: Annotated[str, Field(min_length=10, max_length=4000)]


class PaymentIn(In):
    amount_cents: Annotated[int, Field(gt=0, le=10_000_000_000_00)]
    method: Literal["bank_transfer", "pix", "boleto", "check", "other"] = "bank_transfer"
    external_ref: Annotated[str | None, Field(max_length=200)] = None
    contribution_model_id: Uuid | None = None


class PaymentMoveIn(In):
    to: Literal["awaiting_confirmation", "confirmed", "failed", "cancelled", "disputed"]
    note: Annotated[str | None, Field(max_length=1000)] = None


class RefundIn(In):
    amount_cents: Annotated[int, Field(gt=0, le=10_000_000_000_00)]
    reason: Annotated[str, Field(min_length=3, max_length=1000)]


class RefundDecisionIn(In):
    decision: Literal["approved", "rejected", "completed"]


class StatementIn(In):
    filename: Annotated[str, Field(min_length=1, max_length=255)]
    csv: Annotated[str, Field(min_length=10, max_length=1_000_000)]


class ManualMatchIn(In):
    line_id: Uuid


# ---------------------------------------------------------------- rede, necessidades e profissionais
class NeedIn(In):
    category: Slug
    title: Annotated[str, Field(min_length=3, max_length=200)]
    description: Annotated[str | None, Field(max_length=3000)] = None
    remote_ok: bool = True
    language: Annotated[str, Field(max_length=10)] = "pt-BR"


class OfferIn(In):
    message: Annotated[str | None, Field(max_length=2000)] = None


class OfferDecisionIn(In):
    decision: Literal["accepted", "declined"]


class MessageIn(In):
    body: Annotated[str, Field(min_length=1, max_length=2000)]


class LocationIn(In):
    precision: Literal["exact", "approximate", "neighborhood", "municipality", "region"]
    lat: Annotated[float | None, Field(ge=-90, le=90)] = None
    lng: Annotated[float | None, Field(ge=-180, le=180)] = None


# ---------------------------------------------------------------- admin (risco, erros, moderação)
class RiskScanIn(In):
    org_id: Uuid | None = None


class RiskReviewIn(In):
    status: Literal["reviewed_relevant", "dismissed"]
    note: Annotated[str, Field(min_length=5, max_length=2000)]


class RiskBlockIn(In):
    note: Annotated[str, Field(min_length=10, max_length=2000)]


class MessageRemoveIn(In):
    reason: Annotated[str, Field(min_length=5, max_length=500)]


# ---------------------------------------------------------------- biblioteca de soluções (v0.9.0)
SolKind = Literal["project", "idea", "methodology", "social_tech", "academic"]
SolStage = Literal["idea", "proposal", "developing", "running", "completed"]
SolLicense = Literal["cc_by", "cc_by_sa", "cc_by_nc", "cc_by_nc_sa", "public_domain", "all_rights_reserved", "custom"]
SourceType = Literal["author", "osc", "university", "government", "document", "audit", "public_source", "partner", "external_system"]
Short = Annotated[str, Field(max_length=200)]


class SolutionIn(In):
    kind: SolKind
    stage: SolStage = "proposal"
    title: Annotated[str, Field(min_length=5, max_length=200)]
    summary: Annotated[str, Field(min_length=20, max_length=1500)]
    problem: Annotated[str | None, Field(max_length=4000)] = None
    approach: Annotated[str | None, Field(max_length=6000)] = None
    objectives: Annotated[str | None, Field(max_length=3000)] = None
    learnings: Annotated[str | None, Field(max_length=4000)] = None
    challenges: Annotated[str | None, Field(max_length=4000)] = None
    limitations: Annotated[str | None, Field(max_length=4000)] = None
    themes: list[Slug] = Field(default_factory=list, max_length=12)
    population: list[Slug] = Field(default_factory=list, max_length=12)
    institutions: list[Slug] = Field(default_factory=list, max_length=12)
    ods: list[Ods] = Field(default_factory=list, max_length=17)
    esg: list[Literal["E", "S", "G"]] = Field(default_factory=list, max_length=3)
    uf: UF | None = None
    city: Annotated[str | None, Field(max_length=120)] = None
    ibge_code: Annotated[str | None, Field(pattern=r"^[0-9]{7}$")] = None
    modality: Literal["presencial", "remoto", "hibrido"] | None = None
    duration_months: Annotated[int | None, Field(ge=1, le=240)] = None
    period_start: date | None = None
    period_end: date | None = None
    team_size: Annotated[int | None, Field(ge=1, le=100000)] = None
    beneficiaries_count: Annotated[int | None, Field(ge=0, le=1_000_000_000)] = None
    budget_cents: Cents | None = None
    raised_cents: Cents = 0
    needed_cents: Cents | None = None
    seeking_funding: bool = False
    goals: list[dict] = Field(default_factory=list, max_length=30)
    schedule: list[dict] = Field(default_factory=list, max_length=60)
    license: SolLicense = "all_rights_reserved"
    allow_replication: bool = False
    allow_adaptation: bool = False
    attribution_required: bool = True
    usage_conditions: Annotated[str | None, Field(max_length=2000)] = None
    ip_notes: Annotated[str | None, Field(max_length=2000)] = None
    rights_holder: Annotated[str | None, Field(max_length=300)] = None
    ownership_type: Literal["author", "organization", "joint", "institution", "third_party", "unknown"] = "unknown"
    confidentiality: Literal["public", "shareable", "shareable_on_request", "confidential", "restricted_use"] = "public"
    authorization_publish: bool = False
    authorization_contact: bool = True
    compatible_modalities: list[Slug] = Field(default_factory=list, max_length=12)
    legal_requirements: Annotated[str | None, Field(max_length=3000)] = None
    source_type: SourceType = "author"
    source_name: Annotated[str | None, Field(max_length=300)] = None
    source_date: date | None = None
    project_id: Uuid | None = None


class SolutionPatch(In):
    stage: SolStage | None = None
    title: Annotated[str | None, Field(min_length=5, max_length=200)] = None
    summary: Annotated[str | None, Field(min_length=20, max_length=1500)] = None
    problem: Annotated[str | None, Field(max_length=4000)] = None
    approach: Annotated[str | None, Field(max_length=6000)] = None
    objectives: Annotated[str | None, Field(max_length=3000)] = None
    learnings: Annotated[str | None, Field(max_length=4000)] = None
    challenges: Annotated[str | None, Field(max_length=4000)] = None
    limitations: Annotated[str | None, Field(max_length=4000)] = None
    themes: list[Slug] | None = Field(default=None, max_length=12)
    population: list[Slug] | None = Field(default=None, max_length=12)
    institutions: list[Slug] | None = Field(default=None, max_length=12)
    ods: list[Ods] | None = Field(default=None, max_length=17)
    esg: list[Literal["E", "S", "G"]] | None = Field(default=None, max_length=3)
    uf: UF | None = None
    city: Annotated[str | None, Field(max_length=120)] = None
    modality: Literal["presencial", "remoto", "hibrido"] | None = None
    duration_months: Annotated[int | None, Field(ge=1, le=240)] = None
    team_size: Annotated[int | None, Field(ge=1, le=100000)] = None
    beneficiaries_count: Annotated[int | None, Field(ge=0, le=1_000_000_000)] = None
    budget_cents: Cents | None = None
    raised_cents: Cents | None = None
    needed_cents: Cents | None = None
    seeking_funding: bool | None = None
    goals: list[dict] | None = Field(default=None, max_length=30)
    schedule: list[dict] | None = Field(default=None, max_length=60)
    license: SolLicense | None = None
    allow_replication: bool | None = None
    allow_adaptation: bool | None = None
    attribution_required: bool | None = None
    usage_conditions: Annotated[str | None, Field(max_length=2000)] = None
    ip_notes: Annotated[str | None, Field(max_length=2000)] = None
    rights_holder: Annotated[str | None, Field(max_length=300)] = None
    ownership_type: Literal["author", "organization", "joint", "institution", "third_party", "unknown"] | None = None
    confidentiality: Literal["public", "shareable", "shareable_on_request", "confidential", "restricted_use"] | None = None
    authorization_publish: bool | None = None
    authorization_contact: bool | None = None
    compatible_modalities: list[Slug] | None = Field(default=None, max_length=12)
    legal_requirements: Annotated[str | None, Field(max_length=3000)] = None
    source_type: SourceType | None = None
    source_name: Annotated[str | None, Field(max_length=300)] = None
    source_date: date | None = None
    project_id: Uuid | None = None


class SolutionSearchIn(Pagination):
    text: Annotated[str | None, Field(max_length=500)] = None
    kinds: list[SolKind] | None = Field(default=None, max_length=5)
    stages: list[Literal["idea", "proposal", "developing", "running", "completed"]] | None = Field(default=None, max_length=5)
    themes: list[Slug] | None = Field(default=None, max_length=12)
    population: list[Slug] | None = Field(default=None, max_length=12)
    ods: list[Ods] | None = Field(default=None, max_length=17)
    esg: list[Literal["E", "S", "G"]] | None = None
    ufs: list[UF] | None = Field(default=None, max_length=27)
    budget_min_cents: Cents | None = None
    budget_max_cents: Cents | None = None
    seeking_funding: bool | None = None
    replicable: bool | None = None
    proven: bool | None = None
    trust_min: Literal["self_declared", "documented", "evidenced", "verified"] | None = None
    legal_natures: list[Slug] | None = Field(default=None, max_length=10)
    qualifications: list[Slug] | None = Field(default=None, max_length=10)
    modalities: list[Slug] | None = Field(default=None, max_length=10)
    funding_ready: bool | None = None
    sharing: list[Literal["public", "shareable", "shareable_on_request", "restricted_use"]] | None = Field(default=None, max_length=4)
    sort: Literal["relevance", "recent", "evidence", "budget"] = "relevance"
    view: Literal["card", "list", "map", "ods", "case", "funding", "research"] = "card"


class SolutionTextIn(In):
    text: Annotated[str, Field(min_length=2, max_length=500)]


class SolutionIdsIn(In):
    ids: Annotated[list[Uuid], Field(min_length=2, max_length=4)]


class SolutionCombineIn(SolutionIdsIn):
    title: Annotated[str, Field(min_length=3, max_length=200)]


class SolutionPersonIn(In):
    name: Annotated[str, Field(min_length=2, max_length=200)]
    role: Literal["author", "coauthor", "researcher", "collaborator", "institution"]
    institution: Annotated[str | None, Field(max_length=200)] = None


class SolutionPeopleIn(In):
    people: Annotated[list[SolutionPersonIn], Field(max_length=30)]


class SolutionEvidenceIn(In):
    kind: Literal["document", "photo", "video", "report", "publication", "audit", "external_source"]
    title: Annotated[str, Field(min_length=3, max_length=200)]
    description: Annotated[str | None, Field(max_length=2000)] = None
    url: Annotated[str | None, Field(pattern=r"^https://[^\s]{3,500}$")] = None
    document_id: Uuid | None = None
    source_type: SourceType = "author"
    source_date: date | None = None


class SolutionResultIn(In):
    indicator: Annotated[str, Field(min_length=2, max_length=200)]
    unit: Annotated[str | None, Field(max_length=40)] = None
    baseline: float | None = None
    value: float
    period: Annotated[str | None, Field(max_length=80)] = None
    evidence_id: Uuid | None = None


class SolutionReplProfileIn(In):
    simplicity: Annotated[int | None, Field(ge=1, le=5)] = None
    cost_level: Literal["low", "moderate", "high"] | None = None
    infra_dependency: Literal["low", "medium", "high"] | None = None
    territorial_dependency: Literal["low", "medium", "high"] | None = None
    specialists_needed: Literal["none", "some", "many"] | None = None
    documented: bool | None = None
    training_available: bool | None = None
    adaptable: list[Literal["population", "territory", "budget", "duration", "scale", "methodology", "partners"]] = Field(default_factory=list)
    min_budget_cents: Cents | None = None
    max_budget_cents: Cents | None = None
    min_months: Annotated[int | None, Field(ge=1, le=240)] = None
    required_infra: list[Short] = Field(default_factory=list, max_length=20)
    required_partners: list[Short] = Field(default_factory=list, max_length=20)
    notes: Annotated[str | None, Field(max_length=3000)] = None


class SolutionRelationIn(In):
    to_id: Uuid
    rel_type: Literal["derived_from", "replicates", "complements", "combined_with"]
    note: Annotated[str | None, Field(max_length=500)] = None


class SolutionRequestIn(In):
    kind: Literal["info", "contact", "adaptation", "replication", "budget"]
    message: Annotated[str, Field(min_length=5, max_length=3000)]
    params: dict = Field(default_factory=dict)


class SolutionRequestRespondIn(In):
    status: Literal["seen", "accepted", "declined"]
    response: Annotated[str | None, Field(max_length=3000)] = None


class SolutionIntentIn(In):
    stage: Literal["discovery", "interested", "reviewing"] = "interested"
    public_identity: bool = False


class SolutionReplicationIn(In):
    target_uf: UF
    target_city: Annotated[str, Field(min_length=2, max_length=120)]
    public_identity: bool = False


class SolutionReplicationPatch(In):
    status: Literal["info_requested", "adaptation_requested", "started", "completed", "cancelled"] | None = None
    public_identity: bool | None = None


class SolutionReviewIn(In):
    rating: Annotated[int, Field(ge=1, le=5)]
    body: Annotated[str | None, Field(max_length=2000)] = None


class SolutionDisputeIn(In):
    claim: Annotated[str, Field(min_length=20, max_length=4000)]
    supporting_note: Annotated[str | None, Field(max_length=4000)] = None


class SolutionAdaptIn(In):
    uf: UF | None = None
    city: Annotated[str | None, Field(max_length=120)] = None
    budget_cents: Cents | None = None
    months: Annotated[int | None, Field(ge=1, le=240)] = None
    infra: list[Short] | None = Field(default=None, max_length=20)
    partners: list[Short] | None = Field(default=None, max_length=20)
    population_size: Annotated[int | None, Field(ge=1, le=1_000_000_000)] = None
    notes: Annotated[str | None, Field(max_length=1000)] = None


class SolutionEventIn(In):
    event_type: Literal["solution_shared", "solution_compared"]


class SolutionPrefsIn(In):
    personalization_opt_in: bool


class FunderSolutionPrefsIn(In):
    populations: list[Slug] = Field(default_factory=list, max_length=12)
    kinds: list[SolKind] = Field(default_factory=list, max_length=5)
    horizon_months: Annotated[int | None, Field(ge=1, le=240)] = None
    prefer_proven: bool = False
    risk_tolerance: Literal["low", "medium", "high"] | None = None


class SolutionVerifyIn(In):
    trust_level: Literal["unverified", "self_declared", "in_review", "documented", "evidenced", "verified"]
    note: Annotated[str, Field(min_length=5, max_length=2000)]


class SolutionEvidenceReviewIn(In):
    status: Literal["accepted", "rejected"]
    note: Annotated[str, Field(min_length=3, max_length=2000)]


class SolutionDisputeDecideIn(In):
    status: Literal["upheld", "rejected"]
    note: Annotated[str, Field(min_length=5, max_length=2000)]


class SolutionRemoveIn(In):
    reason: Annotated[str, Field(min_length=5, max_length=2000)]


class SolutionStageIn(In):
    to: Literal["negotiating", "commitment_started", "funded", "implementing", "completed"]



# ---------------------------------------------------------------- camada institucional do terceiro setor (v0.10.0)
GeoScope = Literal["local", "municipal", "regional", "state", "national", "international"]


class InstProfileIn(In):
    legal_nature_code: Slug | None = None
    institutional_profile: Slug | None = None
    legal_nature: Annotated[str | None, Field(max_length=120)] = None
    mission: Annotated[str | None, Field(max_length=3000)] = None
    vision: Annotated[str | None, Field(max_length=3000)] = None
    geographic_scope: GeoScope | None = None
    operating_regions: list[Territory] | None = Field(default=None, max_length=50)
    founded_on: date | None = None


class QualificationIn(In):
    qualification_type: Slug
    issuing_authority: Annotated[str | None, Field(max_length=300)] = None
    protocol: Annotated[str | None, Field(max_length=120)] = None
    certificate_number: Annotated[str | None, Field(max_length=120)] = None
    issue_date: date | None = None
    expiration_date: date | None = None
    verification_url: Annotated[str | None, Field(max_length=500, pattern=r"^https://")] = None
    document_id: Uuid | None = None
    notes: Annotated[str | None, Field(max_length=2000)] = None
    areas: list[Slug] | None = Field(default=None, max_length=20)


class QualificationPatch(In):
    issuing_authority: Annotated[str | None, Field(max_length=300)] = None
    protocol: Annotated[str | None, Field(max_length=120)] = None
    certificate_number: Annotated[str | None, Field(max_length=120)] = None
    issue_date: date | None = None
    expiration_date: date | None = None
    verification_url: Annotated[str | None, Field(max_length=500, pattern=r"^https://")] = None
    document_id: Uuid | None = None
    notes: Annotated[str | None, Field(max_length=2000)] = None
    areas: list[Slug] | None = Field(default=None, max_length=20)


# ---------------------------------------------------------------- v0.10.1: instrumentos, formalização, mentoria
AgreementType = Literal["management_contract", "partnership_term", "collaboration_term", "fomento_term", "cooperation_agreement", "other"]
AgreementStatus = Literal["draft", "active", "completed", "terminated", "suspended"]


class AgreementIn(In):
    agreement_type: AgreementType
    counterpart_name: Annotated[str, Field(min_length=2, max_length=300)]
    counterpart_authority: Annotated[str | None, Field(max_length=300)] = None
    instrument_number: Annotated[str | None, Field(max_length=120)] = None
    object_summary: Annotated[str | None, Field(max_length=2000)] = None
    start_date: date | None = None
    end_date: date | None = None
    value_cents: Cents | None = None
    agreement_status: AgreementStatus = "active"
    qualification_id: Uuid | None = None
    verification_url: Annotated[str | None, Field(max_length=500, pattern=r"^https://")] = None
    document_id: Uuid | None = None


class AgreementPatch(In):
    counterpart_name: Annotated[str | None, Field(min_length=2, max_length=300)] = None
    counterpart_authority: Annotated[str | None, Field(max_length=300)] = None
    instrument_number: Annotated[str | None, Field(max_length=120)] = None
    object_summary: Annotated[str | None, Field(max_length=2000)] = None
    start_date: date | None = None
    end_date: date | None = None
    value_cents: Cents | None = None
    agreement_status: AgreementStatus | None = None
    qualification_id: Uuid | None = None
    verification_url: Annotated[str | None, Field(max_length=500, pattern=r"^https://")] = None
    document_id: Uuid | None = None


class AgreementDecisionIn(In):
    decision: Literal["verify", "reject"]
    note: Annotated[str, Field(min_length=5, max_length=1000)]


class FormalizationStepIn(In):
    state: Literal["not_started", "in_progress", "done_declared"]
    note: Annotated[str | None, Field(max_length=1000)] = None


MentoringTopic = Literal["formalization", "documentation", "project", "fundraising", "accountability", "institutional", "other"]


class MentoringIn(In):
    topic: MentoringTopic
    message: Annotated[str, Field(min_length=10, max_length=2000)]


class MentoringAdminIn(In):
    status: Literal["open", "in_progress", "scheduled", "done", "cancelled"]
    admin_note: Annotated[str | None, Field(max_length=2000)] = None


class MentoringAdminQ(Pagination):
    status: Literal["open", "in_progress", "scheduled", "done", "cancelled"] | None = None


class AgreementAdminQ(Pagination):
    status: Literal["declared", "document_submitted", "verified", "rejected"] | None = "document_submitted"


class EligibilityIn(In):
    subject_type: Literal["call", "modality", "funder"]
    subject_id: Annotated[str, Field(min_length=2, max_length=80)]
    org_id: Uuid | None = None


class EligibilityHistoryQ(Pagination):
    org_id: Uuid | None = None
    subject_type: Literal["call", "modality", "funder", "solution"] | None = None


class ProponentNeedIn(In):
    need_type: Literal["financing", "partner", "replication", "technical", "institutional", "territorial_expansion"]
    detail: Annotated[str | None, Field(max_length=1500)] = None
    amount_cents: Cents | None = None
    territory: Territory | None = None
    solution_id: Uuid | None = None


class ProponentNeedPatch(In):
    detail: Annotated[str | None, Field(max_length=1500)] = None
    amount_cents: Cents | None = None
    status: Literal["open", "met", "closed"] | None = None


CatalogName = Literal["legal_nature", "qualification_type", "institutional_profile", "institutional_status", "funding_modality", "badge"]
WorkflowStatus = Literal["draft", "review", "approved", "published", "archived"]


class CatalogItemIn(In):
    catalog: CatalogName
    code: Slug
    label: Annotated[str, Field(min_length=2, max_length=160)]
    description: Annotated[str | None, Field(max_length=2000)] = None
    attributes: dict = Field(default_factory=dict)
    source_citation: Annotated[str | None, Field(max_length=600)] = None
    source_url: Annotated[str | None, Field(max_length=500, pattern=r"^https://")] = None
    source_date: date | None = None
    confidence: Literal["high", "medium", "low"] = "medium"
    needs_professional_validation: bool = True
    change_note: Annotated[str | None, Field(max_length=1000)] = None


class RuleIn(In):
    code: Annotated[str, Field(pattern=r"^[A-Z0-9-]{3,60}$")]
    name: Annotated[str, Field(min_length=3, max_length=200)]
    description: Annotated[str | None, Field(max_length=2000)] = None
    scope_type: Literal["global", "modality", "call", "funder"]
    scope_ref: Annotated[str | None, Field(max_length=80)] = None
    requirement: dict
    mandatory: bool = True
    how_to_fix: Annotated[str | None, Field(max_length=1000)] = None
    source_citation: Annotated[str, Field(min_length=5, max_length=600)]
    source_url: Annotated[str | None, Field(max_length=500, pattern=r"^https://")] = None
    source_consulted_on: date | None = None
    confidence: Literal["high", "medium", "low"] = "medium"
    needs_professional_validation: bool = True
    effective_from: date | None = None
    effective_to: date | None = None
    change_note: Annotated[str | None, Field(max_length=1000)] = None


class WorkflowIn(In):
    action: Literal["submit", "approve", "publish", "archive", "return_to_draft"]
    note: Annotated[str | None, Field(max_length=2000)] = None
    source_consulted_on: date | None = None


class AdminInstListQ(Pagination):
    status: WorkflowStatus | None = None
    catalog: CatalogName | None = None
    scope_type: Literal["global", "modality", "call", "funder"] | None = None


class QualDecisionIn(In):
    decision: Literal["verify", "reject", "revoke", "request_info"]
    note: Annotated[str | None, Field(max_length=1000)] = None
    validation_date: date | None = None


class DocValidationIn(In):
    decision: Literal["validate", "reject"]
    note: Annotated[str | None, Field(max_length=1000)] = None
    issued_on: date | None = None


InstStatus = Literal["in_structuring", "registered", "documents_pending", "regular", "partially_regular", "irregular", "under_review", "suspended", "archived"]


class InstStatusIn(In):
    status: InstStatus
    note: Annotated[str | None, Field(min_length=3, max_length=1000)] = None


class AdminQualQ(Pagination):
    status: Literal["declared", "document_submitted", "under_review", "verified", "rejected", "revoked"] | None = None


class AdminDocQ(Pagination):
    validation: Literal["pending", "validated", "rejected"] = "pending"
    # a fila cresce; quem revisa precisa poder olhar uma organização ou um tipo por vez
    org_id: Uuid | None = None
    doc_type: Annotated[str | None, Field(max_length=60)] = None


# --- v0.21.0 — oferta comercial e período gratuito ---------------------------------------------

class CommercialOfferIn(In):
    """Proposta de CONTRATO (rota administrativa, alçada financeira). v0.27.0: sem recorrência.

    O valor vem de quem tem alçada, com motivo auditado — nunca da organização que paga e nunca de um
    catálogo de mensalidades (não existe mais, ADR-341).
    """
    org_id: Uuid
    plan_key: Annotated[str, StringConstraints(min_length=2, max_length=40)]
    amount_cents: Annotated[int, Field(ge=0, le=10**11)]
    amount_reason: Annotated[str, StringConstraints(min_length=5, max_length=500)]
    contract_ref: Annotated[str | None, StringConstraints(max_length=200)] = None
    billing_frequency: Literal["one_time", "installment"] = "one_time"
    payment_method: Literal["card", "boleto", "pix", "manual"] = "pix"
    installments: int | None = Field(default=None, ge=2, le=24)
    free_period_months: int | None = Field(default=None, ge=1, le=60)


class CommercialAcceptIn(In):
    """O aceite. `consent_status` é escolha explícita, nunca deduzida da oferta.

    free_access = aceito usar de graça; authorized = autorizo cobrar. Deduzir o segundo a partir
    da existência de uma oferta é como a cobrança surpresa nasce.
    """
    consent_status: Literal["free_access", "authorized"]


class ConsentRevokeIn(In):
    reason: Annotated[str, StringConstraints(min_length=3, max_length=500)]


class FreePeriodGrantIn(In):
    """Concessão manual de período gratuito. Motivo é obrigatório: cortesia sem motivo registrado
    é indistinguível de erro de operação quando alguém for auditar."""
    org_id: str
    source: Literal["PROMOTION", "GRANT", "PARTNERSHIP", "MANUAL_EXCEPTION"]
    months: int = Field(ge=1, le=60)
    reason: Annotated[str, StringConstraints(min_length=3, max_length=500)]
    plan_key: Annotated[str, StringConstraints(min_length=2, max_length=40)] | None = None


class FreePeriodCancelIn(In):
    reason: Annotated[str, StringConstraints(min_length=3, max_length=500)]


class SpendLimitIn(In):
    """Teto de gasto mensal da organização. `action` diz o que fazer ao bater o teto."""
    limit_cents: int | None = Field(default=None, ge=0)
    action: Literal["warn", "hard_stop"] = "warn"


# --- v0.22.0 — contexto de acesso e reautenticação -----------------------------------------------

class AccessCheckIn(In):
    """Pergunta ao motor: posso executar esta ação? Devolve decisão COM MOTIVO.

    Existe para que a tela possa perguntar antes de tentar — e, ao receber não, dizer à pessoa o
    que fazer (pedir permissão a quem, mudar de plano, confirmar identidade) em vez de mostrar um
    botão que falha.
    """
    permission: Annotated[str, StringConstraints(min_length=3, max_length=60)] | None = None
    feature: Annotated[str, StringConstraints(min_length=2, max_length=60)] | None = None
    min_role: Literal["viewer", "member", "analyst", "manager", "admin", "owner"] | None = None


class ReauthIn(In):
    """Confirmação de identidade para operação sensível.

    A senha é sempre exigida. O código de MFA é exigido quando a pessoa tem MFA ativo — não aceitar
    só a senha de quem tem segundo fator seria oferecer o fator mais fraco justamente na operação
    mais perigosa.
    """
    password: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    mfa_code: Annotated[str, StringConstraints(min_length=6, max_length=8)] | None = None


# --- v0.22.0 — operação interna: contabilidade, despesa, instrução, aprovação ---------------------

class PlatformExpenseIn(In):
    """Despesa da PRÓPRIA plataforma. Quem registra não aprova (restrição de tabela)."""
    period: str                     # AAAA-MM-01
    account_code: Annotated[str, StringConstraints(min_length=1, max_length=12)]
    cost_center: Annotated[str, StringConstraints(min_length=2, max_length=20)]
    description: Annotated[str, StringConstraints(min_length=3, max_length=300)]
    amount_cents: int = Field(gt=0)
    supplier_name: Annotated[str, StringConstraints(min_length=2, max_length=160)] | None = None
    supplier_doc: Annotated[str, StringConstraints(pattern=r"^[0-9]{11,14}$")] | None = None
    due_on: date | None = None
    document_ref: Annotated[str, StringConstraints(max_length=200)] | None = None
    recurring: bool = False


class AccountingEntryIn(In):
    """Uma linha de lançamento.

    Era `list[dict]` sem validação nenhuma, e caía direto no SQL: `{"foo": 1}` virava KeyError e
    `period: "nao-e-data"` virava erro de conversão — os dois como HTTP 500. E `side` inválido só
    era pego pela restrição do banco, que responde 422 com nome de constraint em vez de dizer à
    pessoa qual campo está errado.
    """
    period: date
    account_code: Annotated[str, StringConstraints(pattern=r"^[0-9](\.[0-9]{1,2}){0,3}$")]
    side: Literal["debit", "credit"]
    amount_cents: int = Field(gt=0, le=10**12)
    description: Annotated[str, StringConstraints(min_length=3, max_length=300)]
    # `source_kind`/`source_id` ficam de fora de propósito: o lote manual é MANUAL. Deixar o
    # chamador escolher a origem permitiria forjar `source_kind='manual'` com o id de uma despesa,
    # que é exatamente o campo que a conciliação de "despesa paga sem lançamento" lê — e a
    # conferência passaria a confirmar a si mesma.
    cost_center: Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9_]{1,19}$")] | None = None
    cash_date: date | None = None


class AccountingBatchIn(In):
    """Lote de lançamentos. Tem de FECHAR: débitos iguais a créditos."""
    entries: list[AccountingEntryIn] = Field(min_length=2, max_length=200)


class ClosePeriodIn(In):
    period: str
    note: Annotated[str, StringConstraints(min_length=5, max_length=300)] | None = None


class InstructionIn(In):
    """INSTRUÇÃO de pagamento — documento, não transferência (ADR-284)."""
    kind: Literal["supplier", "reimbursement", "tax", "payroll", "marketplace_fee", "refund", "other"]
    payee_name: Annotated[str, StringConstraints(min_length=2, max_length=160)]
    amount_cents: int = Field(gt=0)
    due_on: date
    reference: Annotated[str, StringConstraints(min_length=3, max_length=200)]
    payee_doc: Annotated[str, StringConstraints(pattern=r"^[0-9]{11,14}$")] | None = None
    account_code: Annotated[str, StringConstraints(max_length=12)] | None = None
    cost_center: Annotated[str, StringConstraints(max_length=20)] | None = None
    idempotency_key: Annotated[str, StringConstraints(min_length=8, max_length=200)] | None = None


class ExecutionEvidenceIn(In):
    """Evidência de que QUEM PAGA executou. Obrigatória: a plataforma não vê o pagamento."""
    evidence_doc: Annotated[str, StringConstraints(min_length=3, max_length=300)]


class ApprovalDecisionIn(In):
    approve: bool
    permission_used: Annotated[str, StringConstraints(min_length=3, max_length=60)]
    note: Annotated[str, StringConstraints(max_length=500)] | None = None


class KillSwitchIn(In):
    """Acionamento do interruptor de emergência. O motivo é obrigatório e tem piso de 10 caracteres.

    O piso existe no schema E no banco (`kill_switch_events_reason_check`). Duplicar a trava é
    deliberado: o schema dá mensagem boa a quem está respondendo a um incidente sob pressão, e a
    trava do banco garante que nenhum caminho — inclusive uma migração futura ou um script de
    operação — consiga gravar "teste" como justificativa de parada da plataforma.
    """
    scope: Literal["mutations", "logins", "uploads", "integrations", "maintenance"]
    action: Literal["engage", "release"]
    reason: Annotated[str, StringConstraints(min_length=10, max_length=2000)]


class AiEstimateQ(In):
    """Parâmetros da estimativa de custo. `input_chars` em vez do texto: estimar não precisa do
    conteúdo, e pedir o conteúdo faria a rota de ESTIMATIVA receber o dado que a operação real
    processaria — dobrando a superfície sem necessidade."""
    prompt_key: Annotated[str, StringConstraints(min_length=3, max_length=60, pattern=r"^[a-z][a-z0-9_.]*$")]
    input_chars: int = Field(ge=1, le=1_000_000)


class AiBudgetIn(In):
    """Orçamento de IA da organização, em centavos.

    `hard_stop` tem padrão FALSO de propósito: um limite que para o trabalho sem a organização ter
    pedido para parar é a plataforma escolhendo por ela. Quem quiser parada rígida pede.
    """
    limit_cents: int = Field(ge=100, le=100_000_000)
    warn_at_pct: int = Field(default=80, ge=1, le=100)
    hard_stop: bool = False
    note: Annotated[str, StringConstraints(max_length=400)] | None = None
