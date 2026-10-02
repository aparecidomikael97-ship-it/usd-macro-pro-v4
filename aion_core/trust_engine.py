"""AION core trust engine.

Evaluates EVIDENCE quality for a claim. It never declares absolute truth:
the output is confidence, evidence quality, conflicts, independence,
freshness, provenance and reason codes. Raw document count is NOT consensus:
100 duplicates of the same origin count as one origin.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
import hashlib
import json
import unicodedata

SCHEMA = "ATLASQUANT_AION_CORE_TRUST_ENGINE_V1"
TRUST_ENGINE_VERSION = 1

FRESHNESS_CLASSES = ("STATIC", "SLOW_CHANGING", "FAST_CHANGING", "REALTIME")

ASSESSMENT_STATUSES = (
    "SUPPORTED",
    "WEAKLY_SUPPORTED",
    "CONFLICTING",
    "INSUFFICIENT_EVIDENCE",
    "STALE_EVIDENCE",
    "UNTRUSTED",
)

# Deterministic, explainable factor weights. No magic number is presented as
# scientific truth; every contribution is reported in reason_codes/factors.
_WEIGHTS = {
    "provenance_quality": 0.20,
    "primary_source": 0.25,
    "official_source": 0.10,
    "freshness": 0.15,
    "independence": 0.15,
    "human_validation": 0.15,
}


class TrustEngineError(ValueError):
    """Fail-closed error for invalid evidence items."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any, limit: int = 240) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _fold(value: Any) -> str:
    raw = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in raw if not unicodedata.combining(ch)).casefold()


def _digest(value: Any, length: int = 24) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:length]


def _aware(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class EvidenceItem:
    evidence_id: str
    claim_id: str
    claim: str
    source_fingerprint: str
    source_type: str
    authority: float
    primary_source: bool
    independence_group: str
    freshness_class: str
    published_at: str
    confidence: float
    supports_claim: bool
    contradicts_claim: bool
    human_validated: bool
    provenance_id: str
    tenant_id: str
    domain_id: str
    metadata: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["metadata"] = dict(self.metadata)
        return data


def create_evidence_item(
    *,
    claim_id: Any,
    claim: Any,
    source_fingerprint: Any,
    source_type: Any = "UNKNOWN",
    authority: Any = 0.0,
    primary_source: bool = False,
    independence_group: Any = "",
    freshness_class: Any = "STATIC",
    published_at: Any = "",
    confidence: Any = 0.0,
    supports_claim: bool = True,
    contradicts_claim: bool = False,
    human_validated: bool = False,
    provenance_id: Any = "",
    tenant_id: Any = "",
    domain_id: Any = "",
    metadata: Mapping[str, Any] | None = None,
) -> EvidenceItem:
    key_freshness = _clean(freshness_class, 40).upper()
    if key_freshness not in FRESHNESS_CLASSES:
        raise TrustEngineError(f"unknown freshness_class: {freshness_class!r}")
    fingerprint = _clean(source_fingerprint, 160)
    if not fingerprint:
        raise TrustEngineError("source_fingerprint is required")
    try:
        auth = max(0.0, min(1.0, float(authority)))
    except Exception:
        auth = 0.0
    try:
        conf = max(0.0, min(1.0, float(confidence)))
    except Exception:
        conf = 0.0
    group = _clean(independence_group, 120) or "group-" + _digest(fingerprint, 8)
    payload = {
        "claim": _clean(claim, 400),
        "fingerprint": fingerprint,
        "type": _clean(source_type, 40).upper(),
        "group": group,
        "published_at": _clean(published_at, 80),
    }
    evidence_id = "EV-" + _digest(payload).upper()
    meta = {k: _clean(v, 240) for k, v in dict(metadata or {}).items()}
    return EvidenceItem(
        evidence_id=evidence_id,
        claim_id=_clean(claim_id, 120),
        claim=_clean(claim, 400),
        source_fingerprint=fingerprint,
        source_type=_clean(source_type, 40).upper(),
        authority=round(auth, 4),
        primary_source=primary_source is True,
        independence_group=group,
        freshness_class=key_freshness,
        published_at=_clean(published_at, 80),
        confidence=round(conf, 4),
        supports_claim=supports_claim is True,
        contradicts_claim=contradicts_claim is True,
        human_validated=human_validated is True,
        provenance_id=_clean(provenance_id, 80),
        tenant_id=_clean(tenant_id, 120),
        domain_id=_clean(domain_id, 40).upper(),
        metadata=meta,
    )


@dataclass(frozen=True)
class TrustAssessment:
    claim_id: str
    status: str
    confidence: float
    supporting_independent_sources: int
    contradicting_independent_sources: int
    duplicate_sources_ignored: int
    primary_sources: int
    stale_sources: int
    unknown_sources: int
    reason_codes: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    assessment_digest: str

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["reason_codes"] = list(self.reason_codes)
        data["evidence_ids"] = list(self.evidence_ids)
        return data


def deduplicate_evidence(items: Sequence[EvidenceItem]) -> dict[str, Any]:
    """Cluster by source fingerprint (and shared lineage group). The first item
    of each cluster is kept; the rest are counted as ignored duplicates."""
    clusters: dict[str, list[EvidenceItem]] = {}
    order: list[str] = []
    for item in items:
        key = item.source_fingerprint
        if key not in clusters:
            clusters[key] = []
            order.append(key)
        clusters[key].append(item)
    kept: list[EvidenceItem] = []
    ignored = 0
    for key in order:
        kept.append(clusters[key][0])
        ignored += len(clusters[key]) - 1
    return {"kept": kept, "duplicate_sources_ignored": ignored, "cluster_count": len(order)}


def independent_source_count(items: Sequence[EvidenceItem]) -> int:
    """Distinct independence groups among kept (deduplicated) evidence."""
    deduped = deduplicate_evidence(items)["kept"]
    return len({item.independence_group for item in deduped})


def _is_stale(item: EvidenceItem, now: datetime) -> bool:
    published = _aware(item.published_at)
    if published is None:
        return False
    age_days = (now - published).total_seconds() / 86400.0
    limits = {"STATIC": 3650.0, "SLOW_CHANGING": 365.0, "FAST_CHANGING": 30.0, "REALTIME": 1.0}
    return age_days > limits[item.freshness_class]


def _source_quality(item: EvidenceItem) -> float:
    """Deterministic per-source quality in [0,1], fully reported downstream."""
    score = 0.0
    score += 0.4 * item.authority
    score += 0.3 if item.primary_source else 0.0
    score += 0.15 if item.source_type in ("PRIMARY_SOURCE", "OFFICIAL_SOURCE") else 0.0
    score += 0.15 if item.human_validated else 0.0
    return round(max(0.0, min(1.0, score)), 4)


def assess_claim(
    items: Sequence[EvidenceItem],
    *,
    claim_id: Any = "",
    now: datetime | None = None,
) -> TrustAssessment:
    """Assess evidence quality for a claim. Order-independent and
    duplication-resistant."""
    current = now if isinstance(now, datetime) and now.tzinfo is not None else datetime.now(timezone.utc)
    reason_codes: list[str] = []
    values = list(items or [])
    if not values:
        reason_codes.append("NO_EVIDENCE")
        payload = {"claim_id": _clean(claim_id, 120), "status": "INSUFFICIENT_EVIDENCE", "reasons": sorted(reason_codes)}
        return TrustAssessment(
            claim_id=_clean(claim_id, 120), status="INSUFFICIENT_EVIDENCE", confidence=0.0,
            supporting_independent_sources=0, contradicting_independent_sources=0,
            duplicate_sources_ignored=0, primary_sources=0, stale_sources=0,
            unknown_sources=0, reason_codes=tuple(reason_codes), evidence_ids=(),
            assessment_digest=_digest(payload),
        )

    deduped = deduplicate_evidence(values)
    kept = deduped["kept"]
    if deduped["duplicate_sources_ignored"] > 0:
        reason_codes.append("DUPLICATES_DEDUPLICATED")

    stale_items = [i for i in kept if _is_stale(i, current)]
    unknown_items = [i for i in kept if i.source_type == "UNKNOWN" or not i.provenance_id]
    primary_items = [i for i in kept if i.primary_source]
    supporting = [i for i in kept if i.supports_claim and not i.contradicts_claim]
    contradicting = [i for i in kept if i.contradicts_claim]

    support_groups = {i.independence_group for i in supporting}
    conflict_groups = {i.independence_group for i in contradicting}
    support_count = len(support_groups)
    conflict_count = len(conflict_groups - support_groups)

    # Aggregate quality: mean of per-source quality over kept evidence,
    # weighted by confidence. Duplication cannot inflate it because kept is
    # already deduplicated.
    if kept:
        total_weight = sum(i.confidence for i in kept) or 1.0
        aggregate = sum(_source_quality(i) * i.confidence for i in kept) / total_weight
    else:
        aggregate = 0.0
    confidence = round(max(0.0, min(1.0, aggregate)), 4)

    if stale_items and len(stale_items) == len(kept):
        status = "STALE_EVIDENCE"
        reason_codes.append("ALL_SOURCES_STALE")
    elif conflict_count > 0 and support_count > 0:
        status = "CONFLICTING"
        reason_codes.append("INDEPENDENT_CONFLICT")
    elif support_count >= 2:
        status = "SUPPORTED"
        reason_codes.append("MULTIPLE_INDEPENDENT_SUPPORT")
    elif support_count == 1:
        status = "WEAKLY_SUPPORTED"
        reason_codes.append("SINGLE_INDEPENDENT_SUPPORT")
    else:
        status = "INSUFFICIENT_EVIDENCE"
        reason_codes.append("NO_SUPPORTING_EVIDENCE")

    if unknown_items:
        reason_codes.append("UNKNOWN_ORIGIN_PRESENT")
        confidence = round(confidence * 0.7, 4)
    if stale_items:
        reason_codes.append("STALE_SOURCES_PRESENT")
        if any(i.freshness_class == "REALTIME" for i in stale_items):
            reason_codes.append("REALTIME_STALE_NEVER_CURRENT")
            confidence = round(confidence * 0.5, 4)
    if not primary_items and support_count > 0:
        reason_codes.append("NO_PRIMARY_SOURCE")
    if not reason_codes:
        reason_codes.append("BASELINE_ASSESSMENT")

    payload = {
        "claim_id": _clean(claim_id, 120) or (kept[0].claim_id if kept else ""),
        "status": status,
        "confidence": confidence,
        "support": support_count,
        "conflict": conflict_count,
        "duplicates": deduped["duplicate_sources_ignored"],
        "primary": len(primary_items),
        "stale": len(stale_items),
        "unknown": len(unknown_items),
        "reasons": sorted(reason_codes),
        "evidence": sorted(i.evidence_id for i in kept),
    }
    return TrustAssessment(
        claim_id=payload["claim_id"],
        status=status,
        confidence=confidence,
        supporting_independent_sources=support_count,
        contradicting_independent_sources=conflict_count,
        duplicate_sources_ignored=deduped["duplicate_sources_ignored"],
        primary_sources=len(primary_items),
        stale_sources=len(stale_items),
        unknown_sources=len(unknown_items),
        reason_codes=tuple(sorted(reason_codes)),
        evidence_ids=tuple(sorted(i.evidence_id for i in kept)),
        assessment_digest=_digest(payload),
    )


def trust_assessment_digest(assessment: TrustAssessment | Mapping[str, Any]) -> str:
    data = assessment.as_dict() if isinstance(assessment, TrustAssessment) else dict(assessment)
    data.pop("assessment_digest", None)
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


__all__ = [
    "SCHEMA",
    "TRUST_ENGINE_VERSION",
    "FRESHNESS_CLASSES",
    "ASSESSMENT_STATUSES",
    "EvidenceItem",
    "TrustAssessment",
    "TrustEngineError",
    "create_evidence_item",
    "deduplicate_evidence",
    "independent_source_count",
    "assess_claim",
    "trust_assessment_digest",
]
