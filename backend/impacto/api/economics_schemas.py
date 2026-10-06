"""Entradas da camada econômica (programa, Value Ledger, evento faturável, carta legal).

O que está deliberadamente FORA destes modelos, porque é o servidor quem apura:

  * `status` do programa na criação — todo programa nasce em rascunho (gatilho no banco);
  * `published_at`, `published_by`, `closed_at` — derivados da transição;
  * **todo o dinheiro apurado** do programa: comprometido, desembolsado, confirmado, executado e
    comprovado vêm de `program_financials()`. O cliente só declara `budget_total_cents` (o orçamento
    que ele diz ter) e `allocated_cents` (o que diz destinar). A diferença entre declarado e apurado é
    o produto;
  * `minutes_saved_estimate` do Value Ledger — calculado de uma tabela de referência versionada, com
    fonte e data. Estimativa digitável seria número inventado com cara de medição;
  * `cost_cents_estimate` da IA — calculado da tabela de preço do provedor, versionada;
  * `legal_status` de uma regra de monetização — só a administração escreve, e o gatilho recusa ativar
    regra que não esteja marcada como validada.
"""
from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import Field

from .schemas import Cents, In, Ods, Slug, Territory, Uuid

Title = Annotated[str, Field(min_length=5, max_length=200)]
Summary = Annotated[str, Field(min_length=10, max_length=2000)]
Objective = Annotated[str, Field(min_length=10, max_length=2000)]
LongText = Annotated[str, Field(max_length=20000)]
Note = Annotated[str, Field(min_length=3, max_length=2000)]
Reason = Annotated[str, Field(min_length=10, max_length=2000)]
Source = Annotated[str, Field(min_length=3, max_length=200)]

ProgramStatus = Literal["draft", "open", "in_execution", "suspended", "closed", "archived"]
ProgramVisibility = Literal["organization", "network", "public"]
ProjectRole = Literal["candidate", "selected", "funded", "monitored", "declined", "withdrawn"]
Sphere = Literal["federal", "state", "municipal", "private", "mixed", "international"]


# ---------------------------------------------------------------- programa
class ProgramIn(In):
    title: Title
    summary: Summary
    #: Exigido: programa sem objetivo declarado não é programa, é uma pasta de projetos.
    objective: Objective
    description: LongText | None = None
    budget_total_cents: Cents | None = None
    currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")] = "BRL"
    territories: list[Territory] = Field(default_factory=list, max_length=200)
    causes: list[Slug] = Field(default_factory=list, max_length=30)
    ods: list[Ods] = Field(default_factory=list, max_length=17)
    sphere: Sphere | None = None
    instrument: Annotated[str, Field(max_length=80)] | None = None
    starts_on: date | None = None
    ends_on: date | None = None


class ProgramPatch(In):
    title: Title | None = None
    summary: Summary | None = None
    objective: Objective | None = None
    description: LongText | None = None
    budget_total_cents: Cents | None = None
    currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")] | None = None
    territories: list[Territory] | None = Field(default=None, max_length=200)
    causes: list[Slug] | None = Field(default=None, max_length=30)
    ods: list[Ods] | None = Field(default=None, max_length=17)
    sphere: Sphere | None = None
    instrument: Annotated[str, Field(max_length=80)] | None = None
    starts_on: date | None = None
    ends_on: date | None = None
    visibility: ProgramVisibility | None = None


class ProgramTransitionIn(In):
    to_status: ProgramStatus
    reason: Reason | None = None


class ProgramQ(In):
    status: ProgramStatus | None = None
    limit: Annotated[int, Field(ge=1, le=100)] = 25
    offset: Annotated[int, Field(ge=0, le=100000)] = 0


class ProgramFeedQ(In):
    territory: Territory | None = None
    cause: Slug | None = None
    limit: Annotated[int, Field(ge=1, le=100)] = 25
    offset: Annotated[int, Field(ge=0, le=100000)] = 0


class ProgramCallIn(In):
    call_id: Uuid


class ProgramProjectIn(In):
    project_id: Uuid
    role: ProjectRole
    allocated_cents: Cents | None = None
    note: Note | None = None


class ProgramIndicatorIn(In):
    indicator_id: Uuid
    target_value: float | None = None
    target_date: date | None = None
    baseline_value: float | None = None
    baseline_date: date | None = None
    #: Linha de base exige fonte (CHECK no banco). Número de partida sem fonte é número inventado, e o
    #: programa inteiro passa a medir contra ele.
    baseline_source: Source | None = None
    note: Note | None = None


class ProgramNeedIn(In):
    need_id: Uuid


class GapQ(In):
    #: Prefixo de território: "BR-MT" devolve o estado; "BR" devolve o país.
    territory_prefix: Annotated[str, Field(max_length=16, pattern=r"^[A-Z0-9-]*$")] | None = None


# ---------------------------------------------------------------- Value Ledger
class ValueFeedQ(In):
    event_type: Annotated[str, Field(max_length=60, pattern=r"^[a-z][a-z0-9_.]*$")] | None = None
    limit: Annotated[int, Field(ge=1, le=100)] = 50
    offset: Annotated[int, Field(ge=0, le=100000)] = 0


class ValueSummaryQ(In):
    days: Annotated[int, Field(ge=1, le=730)] = 90
    program_id: Uuid | None = None


class BaselineIn(In):
    """Declara quanto trabalho humano uma unidade de evento substitui.

    Fonte, data e método são **obrigatórios** — e o CHECK no banco também recusa sem eles. Sem isso o
    número seria chute com cara de medição, e é esse o defeito que o Value Ledger existe para evitar.
    """
    event_type: Annotated[str, Field(max_length=60, pattern=r"^[a-z][a-z0-9_.]*$")]
    minutes_per_unit: Annotated[float, Field(gt=0, le=10000)]
    source_name: Source
    source_date: date
    method_note: Annotated[str, Field(min_length=20, max_length=2000)]
    source_url: Annotated[str, Field(max_length=500, pattern=r"^https?://")] | None = None


class AiPriceIn(In):
    """Preço de um modelo, por milhão de tokens, com fonte obrigatória.

    A tabela nasce vazia: nenhum preço de provedor foi inventado no pacote.
    """
    provider: Annotated[str, Field(min_length=2, max_length=40)]
    model: Annotated[str, Field(min_length=1, max_length=80)]
    input_per_mtok_cents: Annotated[float, Field(ge=0, le=1_000_000)]
    output_per_mtok_cents: Annotated[float, Field(ge=0, le=1_000_000)]
    currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")] = "USD"
    source_name: Source
    source_date: date
    source_url: Annotated[str, Field(max_length=500, pattern=r"^https?://")] | None = None


class AiCostQ(In):
    days: Annotated[int, Field(ge=1, le=365)] = 30
    org_id: Uuid | None = None


# ---------------------------------------------------------------- monetização
RevenueEngine = Literal["saas_institutional", "b2g", "enterprise", "implementation",
                        "marketplace_take_rate", "success_fee", "proponent_premium",
                        "data_intelligence"]
Certainty = Literal["low", "medium", "high"]
CardStatus = Literal["green", "yellow", "red"]
LegalStatus = Literal["review_required", "validated", "refused"]
BillableStatus = Literal["candidate", "blocked_legal", "blocked_no_price", "eligible", "billed",
                         "waived"]


class RulesQ(In):
    engine: RevenueEngine | None = None


class RulePatch(In):
    """Ajusta uma regra de receita. O portão de ativação é no banco, não aqui."""
    amount_cents: Cents | None = None
    percentage: Annotated[float, Field(gt=0, le=100)] | None = None
    currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")] | None = None
    legal_status: LegalStatus | None = None
    legal_card_id: Uuid | None = None
    active: bool | None = None
    hypothesis_min_cents: Cents | None = None
    hypothesis_max_cents: Cents | None = None
    hypothesis_note: Annotated[str, Field(max_length=2000)] | None = None


class LegalCardIn(In):
    """Pesquisa de base normativa de uma receita. NÃO é parecer jurídico.

    `certainty` é o grau de certeza da PESQUISA. `needs_lawyer` e `needs_accountant` nascem
    verdadeiros, e marcar verde exige base, fonte, data, certeza alta e `needs_lawyer = false`.
    """
    rule_key: Annotated[str, Field(max_length=60, pattern=r"^[a-z][a-z0-9_.]*$")]
    payer: Annotated[str, Field(min_length=3, max_length=200)]
    beneficiary: Annotated[str, Field(min_length=3, max_length=200)]
    billing_event: Annotated[str, Field(min_length=5, max_length=300)]
    revenue_nature: Annotated[str, Field(min_length=5, max_length=300)]
    contractual_relation: Annotated[str, Field(min_length=5, max_length=500)]
    certainty: Certainty
    status: CardStatus
    required_document: Annotated[str, Field(max_length=500)] | None = None
    required_terms: Annotated[str, Field(max_length=500)] | None = None
    cancellation_policy: Annotated[str, Field(max_length=1000)] | None = None
    refund_policy: Annotated[str, Field(max_length=1000)] | None = None
    tax_notes: Annotated[str, Field(max_length=4000)] | None = None
    invoice_notes: Annotated[str, Field(max_length=2000)] | None = None
    regulatory_notes: Annotated[str, Field(max_length=4000)] | None = None
    legal_basis: Annotated[str, Field(max_length=4000)] | None = None
    source_name: Annotated[str, Field(min_length=3, max_length=300)] | None = None
    source_url: Annotated[str, Field(max_length=500, pattern=r"^https?://")] | None = None
    verified_on: date | None = None
    needs_lawyer: bool = True
    needs_accountant: bool = True
    open_questions: Annotated[str, Field(max_length=4000)] | None = None
    note: Annotated[str, Field(max_length=4000)] | None = None


class PipelineQ(In):
    status: BillableStatus | None = None
    org_id: Uuid | None = None
    limit: Annotated[int, Field(ge=1, le=100)] = 50
    offset: Annotated[int, Field(ge=0, le=100000)] = 0


class WaiveIn(In):
    reason: Reason
