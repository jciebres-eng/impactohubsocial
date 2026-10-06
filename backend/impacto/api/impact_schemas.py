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
