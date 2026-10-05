"""Evidência: o vocabulário comum do núcleo.

Problema que isto resolve: antes, "a organização declarou que tem certidão" e "a certidão foi conferida e está vigente"
entravam no motor como o mesmo número. Agora todo sinal relevante carrega **de onde veio**, **se foi verificado**,
**quando foi observado** e **quanto disso ainda vale hoje**.

Regra que não se negocia: `DECLARED` nunca vale o mesmo que `VERIFIED`. O decaimento por idade reduz a **confiança**,
nunca inventa valor onde não há dado — ausência continua sendo `None`, não zero.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any


class Source(StrEnum):
    """De onde o sinal veio. A ordem importa: é usada para decidir qual fonte prevalece."""
    VERIFIED_CREDENTIAL = "verified_credential"   # credencial conferida pela equipe (profissional, qualificação)
    VERIFIED_DOCUMENT = "verified_document"       # documento no cofre, vigente, íntegro
    SIGNED_DOCUMENT = "signed_document"           # documento assinado (nível mais alto: tem assinatura e custódia)
    PLATFORM_RECORD = "platform_record"           # fato produzido pela própria plataforma (aporte, marco, medição)
    VALIDATED_MEASUREMENT = "validated_measurement"  # medição de indicador validada por outra organização
    OFFICIAL_CATALOG = "official_catalog"         # dado de referência com fonte e data (ODS, regra fiscal, conselho)
    DECLARED = "declared"                         # a pessoa digitou; ninguém conferiu
    INFERRED = "inferred"                         # a plataforma deduziu de outros dados
    ABSENT = "absent"                             # não há dado


# Peso de confiança por fonte: o quanto a plataforma acredita no sinal ANTES de considerar a idade.
SOURCE_TRUST: dict[Source, float] = {
    Source.SIGNED_DOCUMENT: 1.0,
    Source.VERIFIED_CREDENTIAL: 1.0,
    Source.VERIFIED_DOCUMENT: 0.95,
    Source.VALIDATED_MEASUREMENT: 0.95,
    Source.PLATFORM_RECORD: 0.9,
    Source.OFFICIAL_CATALOG: 0.9,
    Source.INFERRED: 0.5,
    Source.DECLARED: 0.4,
    Source.ABSENT: 0.0,
}
VERIFIED_SOURCES = (Source.SIGNED_DOCUMENT, Source.VERIFIED_CREDENTIAL, Source.VERIFIED_DOCUMENT,
                    Source.VALIDATED_MEASUREMENT)

# Meia-vida da frescura, em dias, por tipo de sinal. Depois da meia-vida o sinal vale metade da confiança.
# Não é regra oficial de nada: é hipótese de produto, declarada e versionada.
FRESHNESS_HALF_LIFE_DAYS: dict[str, int] = {
    "credential": 365, "document": 180, "compliance": 180, "profile": 365, "budget": 180,
    "indicator": 120, "project_activity": 90, "need": 120, "opportunity": 30, "diagnosis": 180, "default": 365,
}
FRESHNESS_VERSION = "freshness@1.0"


def _as_date(v: Any) -> date | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def freshness(observed_at: Any, *, kind: str = "default", at: date | None = None,
              expires_at: Any = None) -> tuple[float, str]:
    """(0–1, explicação). 1.0 = fresco. Expirado devolve 0.0 e diz isso — não é o mesmo que "velho"."""
    today = at or datetime.now(UTC).date()
    exp = _as_date(expires_at)
    if exp is not None and exp < today:
        return 0.0, f"expirado em {exp.isoformat()}"
    obs = _as_date(observed_at)
    if obs is None:
        return 0.5, "sem data de observação"
    age = max(0, (today - obs).days)
    half = FRESHNESS_HALF_LIFE_DAYS.get(kind, FRESHNESS_HALF_LIFE_DAYS["default"])
    value = 0.5 ** (age / half)
    if age <= half // 4:
        return round(min(1.0, value), 4), f"observado há {age} dia(s)"
    return round(value, 4), f"observado há {age} dia(s) (meia-vida de {half} dias para {kind})"


@dataclass
class Evidence:
    """Um fato conhecido pelo motor, com procedência."""
    key: str
    source: Source
    value: Any = None
    verified: bool = False
    observed_at: Any = None
    expires_at: Any = None
    kind: str = "default"
    detail: str = ""
    reference: str | None = None            # id do documento/credencial/medição que sustenta o fato

    def __post_init__(self) -> None:
        # 'verified' NÃO é declarado pelo chamador: deriva da fonte. Isso impede marcar declaração como verificada.
        self.verified = self.source in VERIFIED_SOURCES

    @property
    def present(self) -> bool:
        return self.source is not Source.ABSENT and self.value is not None

    def confidence(self, at: date | None = None) -> float:
        """Confiança no fato: confiança da fonte × frescura."""
        if not self.present:
            return 0.0
        fresh, _ = freshness(self.observed_at, kind=self.kind, at=at, expires_at=self.expires_at)
        return round(SOURCE_TRUST[self.source] * fresh, 4)

    def as_dict(self, at: date | None = None) -> dict:
        fresh, why = freshness(self.observed_at, kind=self.kind, at=at, expires_at=self.expires_at)
        return {"key": self.key, "source": self.source.value, "verified": self.verified, "present": self.present,
                "observed_at": None if self.observed_at is None else str(self.observed_at)[:10],
                "expires_at": None if self.expires_at is None else str(self.expires_at)[:10],
                "freshness": fresh, "freshness_detail": why, "confidence": self.confidence(at),
                "detail": self.detail, "reference": self.reference}


@dataclass
class EvidenceSet:
    """Conjunto de evidências de um contexto. Resolve conflito pela fonte mais confiável."""
    items: dict[str, Evidence] = field(default_factory=dict)

    def add(self, ev: Evidence) -> None:
        cur = self.items.get(ev.key)
        if cur is None or SOURCE_TRUST[ev.source] > SOURCE_TRUST[cur.source]:
            self.items[ev.key] = ev

    def get(self, key: str) -> Evidence:
        return self.items.get(key) or Evidence(key=key, source=Source.ABSENT)

    def verified(self, key: str) -> bool:
        return self.get(key).verified

    def confidence(self, key: str, at: date | None = None) -> float:
        return self.get(key).confidence(at)

    def missing(self) -> list[str]:
        return sorted(k for k, e in self.items.items() if not e.present)

    def stale(self, threshold: float = 0.5, at: date | None = None) -> list[dict]:
        out = []
        for e in self.items.values():
            if not e.present:
                continue
            fresh, why = freshness(e.observed_at, kind=e.kind, at=at, expires_at=e.expires_at)
            if fresh < threshold:
                out.append({"key": e.key, "freshness": fresh, "detail": why})
        return sorted(out, key=lambda d: d["freshness"])

    def as_dict(self, at: date | None = None) -> dict:
        return {k: e.as_dict(at) for k, e in sorted(self.items.items())}

    def summary(self, at: date | None = None) -> dict:
        present = [e for e in self.items.values() if e.present]
        verified = [e for e in present if e.verified]
        conf = (sum(e.confidence(at) for e in present) / len(present)) if present else 0.0
        return {"known": len(present), "total": len(self.items), "verified": len(verified),
                "declared_only": len([e for e in present if e.source is Source.DECLARED]),
                "mean_confidence": round(100 * conf, 1), "stale": len(self.stale(at=at)),
                "freshness_version": FRESHNESS_VERSION}


def decay_confidence(base_confidence: float, evidence: EvidenceSet, at: date | None = None) -> tuple[float, str]:
    """Aplica o decaimento das evidências sobre uma confiança já calculada.

    Importante: isto reduz a CONFIANÇA, nunca a pontuação. Dado velho não deixa de ser verdade — deixa de ser certeza.
    """
    present = [e for e in evidence.items.values() if e.present]
    if not present:
        return 0.0, "nenhuma evidência presente"
    mean_fresh = sum(freshness(e.observed_at, kind=e.kind, at=at, expires_at=e.expires_at)[0] for e in present) / len(present)
    adjusted = round(base_confidence * (0.5 + 0.5 * mean_fresh), 1)
    if mean_fresh >= 0.9:
        return adjusted, "evidências recentes"
    return adjusted, f"confiança reduzida: frescura média {round(100 * mean_fresh)}%"


class ConfidenceBand(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INSUFFICIENT_DATA = "insufficient_data"


def band(confidence: float, known: int, total: int) -> ConfidenceBand:
    """Faixa de confiança. Score alto com confiança baixa NUNCA deve aparecer como recomendação forte."""
    if total and known / total < 0.4:
        return ConfidenceBand.INSUFFICIENT_DATA
    if confidence >= 75:
        return ConfidenceBand.HIGH
    if confidence >= 50:
        return ConfidenceBand.MEDIUM
    if confidence >= 25:
        return ConfidenceBand.LOW
    return ConfidenceBand.INSUFFICIENT_DATA


BAND_LABEL = {
    ConfidenceBand.HIGH: "confiança alta",
    ConfidenceBand.MEDIUM: "confiança média",
    ConfidenceBand.LOW: "confiança baixa — trate como indício",
    ConfidenceBand.INSUFFICIENT_DATA: "dados insuficientes — não é recomendação",
}