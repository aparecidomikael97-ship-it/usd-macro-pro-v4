"""FX research: do not mistake multiple reactions to one event for independent proof.

Offline, no broker/network/IO. Factor->root-catalyst links and timestamps are
caller assertions, not independently authenticated provenance or causal proofs.
Even a structurally passing audit cannot authorize a bias or a trade.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any

from atlasquant_fx_universe import OFFICIAL_PAIRS

SCHEMA = "ATLASQUANT_FX_EVENT_DEPENDENCY_ABSTENTION_LAB_V1"
HORIZONS = frozenset({"D1", "W1"})
SIDES = frozenset({"BASE_RELATIVE", "QUOTE_RELATIVE", "NEUTRAL"})
FAMILIES = frozenset({"MACRO", "POLICY", "MARKET", "GEOPOLITICAL", "RISK"})
TOKEN = re.compile(r"[A-Z0-9][A-Z0-9_-]{3,79}\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")
MAX_FACTORS = 64
# Research-only acceptance thresholds: NOT fitted on future labels.
MIN_CLAIMED_ROOTS = 3
MIN_CLAIMED_FAMILIES = 2


@dataclass(frozen=True)
class FactorClaim:
    factor_id: str
    root_catalyst_id: str
    source_family: str
    relative_side: str
    captured_at_utc: datetime
    source_sha256_claim: str


def _utc(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None):
        return None
    return value.astimezone(timezone.utc)


def _blocked(reason: str, *, asset: str | None = None) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_DEPENDENCY_BLOCKED", "reason": reason,
        "asset": asset, "factor_count": 0,
        "claimed_root_catalyst_count": 0,
        "claimed_distinct_family_count": 0,
        "claimed_root_catalyst_groups": [],
        "raw_factor_count_is_not_independent_evidence": True,
        "root_catalysts_independently_authenticated": False,
        "source_and_event_lineage_independently_verified": False,
        "statistical_independence_proven": False,
        "minimum_root_threshold_empirically_calibrated": False,
        "validated_incremental_accuracy": None,
        "calibrated_probability": None, "directional_fx_bias": None,
        "operational_bias": "AGUARDAR", "publishable": False,
        "live_alert_allowed": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "http_requests": 0, "file_writes": 0, "new_cost_brl": 0,
    }


def inspect_fx_evidence_dependency_lab(*, asset: Any, horizon: Any,
                                        factors: Any, decision_at_utc: Any,
                                        as_of_utc: Any) -> dict[str, Any]:
    """Count roots (shared causes), not indicators, before a research hypothesis.

    A root such as US_CPI_OCT_2026 can explain CPI, USD index, yields and a
    news-sentiment measure at once. Unverified caller-supplied roots do not
    prove that otherwise distinct roots are statistically independent.
    """
    decided, now = _utc(decision_at_utc), _utc(as_of_utc)
    if (not isinstance(asset, str) or asset not in OFFICIAL_PAIRS
            or horizon not in HORIZONS or decided is None or now is None
            or decided > now or not isinstance(factors, (list, tuple))
            or not 1 <= len(factors) <= MAX_FACTORS):
        return _blocked("INVALID_ASSET_HORIZON_FACTORS_OR_CLOCK",
                        asset=asset if isinstance(asset, str) else None)
    out = _blocked("UNASSESSED", asset=asset)
    ids: set[str] = set()
    roots: dict[str, dict[str, Any]] = {}
    signs: set[str] = set()
    families: set[str] = set()
    for factor in factors:
        if (not isinstance(factor, FactorClaim)
                or not isinstance(factor.factor_id, str)
                or TOKEN.fullmatch(factor.factor_id) is None
                or factor.factor_id in ids
                or not isinstance(factor.root_catalyst_id, str)
                or TOKEN.fullmatch(factor.root_catalyst_id) is None
                or factor.root_catalyst_id in ("UNKNOWN", "UNVERIFIED", "NONE")
                or factor.source_family not in FAMILIES
                or factor.relative_side not in SIDES
                or not isinstance(factor.source_sha256_claim, str)
                or SHA.fullmatch(factor.source_sha256_claim) is None):
            out["reason"] = "INVALID_OR_DUPLICATED_FACTOR_OR_UNATTRIBUTED_ROOT"
            return out
        captured = _utc(factor.captured_at_utc)
        if captured is None or captured > decided:
            out["reason"] = "SOURCE_CAPTURE_AFTER_DECISION_LOOKAHEAD"
            return out
        ids.add(factor.factor_id)
        row = roots.setdefault(factor.root_catalyst_id,
                               {"root_catalyst_id": factor.root_catalyst_id,
                                "factor_ids": [], "source_families": set(),
                                "sides": set()})
        row["factor_ids"].append(factor.factor_id)
        row["source_families"].add(factor.source_family)
        row["sides"].add(factor.relative_side)
        families.add(factor.source_family)
        if factor.relative_side != "NEUTRAL":
            signs.add(factor.relative_side)
    groups = [{"root_catalyst_id": k,
               "factor_ids": sorted(v["factor_ids"]),
               "factor_count": len(v["factor_ids"]),
               "source_families_claimed": sorted(v["source_families"]),
               "directions_claimed": sorted(v["sides"])}
              for k, v in sorted(roots.items())]
    out.update({"factor_count": len(ids),
                "claimed_root_catalyst_count": len(roots),
                "claimed_distinct_family_count": len(families),
                "claimed_root_catalyst_groups": groups})
    if len(signs) > 1:
        out.update(state="LAB_CONFLICTING_EVIDENCE_ABSTAIN",
                   reason="BASE_QUOTE_RELATIVE_EVIDENCE_DISAGREES")
    elif not signs:
        out.update(state="LAB_ONLY_NEUTRAL_FACTORS_ABSTAIN",
                   reason="NO_DIRECTIONAL_EVIDENCE_HYPOTHESIS")
    elif len(roots) < MIN_CLAIMED_ROOTS or len(families) < MIN_CLAIMED_FAMILIES:
        out.update(state="LAB_INSUFFICIENT_DISTINCT_CATALYSTS_ABSTAIN",
                   reason="REDUNDANT_ROOTS_OR_INSUFFICIENT_FAMILY_DIVERSITY")
    else:
        out.update(state="LAB_DOCUMENTARY_ROOT_DIVERSITY_CANDIDATE_NO_GO",
                   reason="DISTINCT_ROOT_CLAIMS_NOT_INDEPENDENT_PROOFS_OR_CALIBRATED_PROBABILITY")
    return out


__all__ = ("SCHEMA", "FactorClaim", "inspect_fx_evidence_dependency_lab")