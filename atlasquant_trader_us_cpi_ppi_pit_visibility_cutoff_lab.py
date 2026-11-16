"""One-time CPI/PPI visibility fence for Motor A research-only D1/W1/M1.

All data is caller-supplied (original bytes + local HTTP metadata CLAIMS).
A CPI or PPI RELEASE SCHEDULE is never its actual first-seen time. A
post-event first-print value does not become a pre-event model input.
The only evidence available for a cutoff is what was *captured before it*,
and a consensus captured after release is not pre-event witnessed.
Even a fully reproducible local sha256 is not independent publisher proof.

This is NOT a price/FX model; it produces NO forecast, direction, 80%
accuracy, probabilistic bias, alerts, order, broker quote or deploy.
No HTTP, disk, MT5, background task, GitHub write, or market I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from typing import Any
from urllib.parse import urlsplit
import re

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_fx28_macro_event_surprise_reaction_contract_lab import (
    MetricIdentity, PreEventConsensus, OfficialActual,
)
from atlasquant_trader_us_cpi_source_custody_lab import RELEASE as CPI_RELEASE
from atlasquant_trader_us_ppi_oct2026_actual_table_guard_lab import (
    RELEASE_UTC as PPI_RELEASE,
)

SCHEMA = "ATLASQUANT_TRADER_US_CPI_PPI_PIT_CUTOFF_NO_LOOKAHEAD_LAB_V1"
UTC = timezone.utc
_PERIOD = "2026-10"
_SCHEDULE = {"CPI": CPI_RELEASE, "PPI": PPI_RELEASE}
_IDS = {
    "CPI": "US_CPI_U_HEADLINE",
    "PPI": "US_PPI_FINAL_DEMAND",
}
_NUM = re.compile(r"-?(?:0|[1-9][0-9]{0,2})(?:\.[0-9]{1,3})?\Z")
_MAX_SOURCE = 512_000
_HORIZONS = frozenset(("D1", "W1", "M1"))
_LOOKBACK = timedelta(days=60)


@dataclass(frozen=True)
class EventVintageClaim:
    kind: str
    consensus: PreEventConsensus | None
    consensus_source_bytes: bytes | None
    actual: OfficialActual | None
    actual_source_bytes: bytes | None


def _utc(t: Any) -> datetime | None:
    if type(t) is not datetime or t.tzinfo is None or t.microsecond:
        return None
    try:
        return t.astimezone(UTC) if t.utcoffset() is not None else None
    except (TypeError, ValueError, OverflowError):
        return None


def _pct(v: Any) -> Decimal | None:
    if type(v) is not str or _NUM.fullmatch(v) is None:
        return None
    try:
        x = Decimal(v)
        return x if x.is_finite() and abs(x) < Decimal("100") else None
    except (TypeError, ValueError, InvalidOperation):
        return None


def _sha_ok(data: Any, digest: Any) -> bool:
    return (type(data) is bytes and 1 <= len(data) <= _MAX_SOURCE
            and type(digest) is str
            and sha256(data).hexdigest() == digest)


def _origin(url: Any, *, bls: bool) -> bool:
    if type(url) is not str or not 15 <= len(url) <= 500:
        return False
    try:
        u = urlsplit(url)
        return (u.scheme == "https" and u.hostname is not None
                and (not bls or u.hostname == "www.bls.gov")
                and u.port is None and u.username is None and u.password is None
                and not u.fragment and bool(u.path) and not u.query
                and u.netloc.lower() == u.hostname.lower()
                and u.hostname not in ("localhost", "127.0.0.1")
                and "." in u.hostname)
    except (TypeError, ValueError):
        return False


def _metric(m: Any, kind: str) -> bool:
    return (type(m) is MetricIdentity
            and m.currency == "USD"
            and m.series_id == _IDS[kind]
            and m.reference_period == _PERIOD
            and m.transformation == "MOM"
            and m.seasonal_adjustment == "SA"
            and m.unit == "PERCENT")


def _blocked(reason: str, *, cutoff: datetime | None = None,
             horizon: str | None = None) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_US_CPI_PPI_PIT_VISIBILITY_BLOCKED_NO_GO",
        "reason": reason,
        "feature_cutoff_utc": cutoff.isoformat() if cutoff is not None else None,
        "requested_research_horizon": horizon,
        "horizon_M1_not_a_slot_in_original_672_fx28_campaign": True,
        "economic_event_roster": ["CPI", "PPI"],
        "economic_events_reconciled": 0,
        "feature_rows": [],
        "research_events_with_pre_release_consensus_visible": 0,
        "research_events_with_first_print_visible_at_cutoff_claim_only": 0,
        "documentary_surprises_comparable_after_release_only": 0,
        "release_time_is_not_source_first_seen": True,
        "local_sha256_is_not_independent_issuer_attestation": True,
        "pre_event_feature_contaminated_by_future_actual": False,
        "consensus_captured_after_release_used_as_pre_event": False,
        "cpi_ppi_mom_sa_are_distinct_metrics": True,
        "ppi_event_not_seven_independent_fx_trials": True,
        "us_release_direct_leg_pairs": 7,
        "non_usd_direct_leg_pairs": 21,
        "original_672_campaign_slots_modified": False,
        "source_first_seen_independently_authenticated": False,
        "pre_event_consensus_independently_authenticated": False,
        "calibrated_directional_probability": None,
        "validated_fx_accuracy": None,
        "directional_bias": None,
        "live_signal_authorized": False,
        "trade_authorized": False,
        "publishable": False,
        "scheduler_enabled": False,
        "mt5_calls": 0, "http_requests": 0, "file_writes": 0,
        "operational_bias": "AGUARDAR",
    }


def inspect_us_cpi_ppi_pit_cutoff_lab(
    *, decision_cutoff_utc: Any, research_horizon: Any,
    event_claims: Any,
) -> dict[str, Any]:
    """Compare immutable locally claimed vintages at a single decision cutoff.

    Original bytes validate only the supplied SHA field. Visibility requires
    source captured before or AT decision; actual also requires decision at
    or later than the documented release. Never use result of later events.
    """
    cutoff = _utc(decision_cutoff_utc)
    out = _blocked("INVALID_DECISION_CUTOFF_OR_EVENT_ROSTER",
                   cutoff=cutoff,
                   horizon=research_horizon if research_horizon in _HORIZONS else None)
    if (cutoff is None or research_horizon not in _HORIZONS
            or type(event_claims) not in (tuple, list)
            or len(event_claims) != 2 or len(OFFICIAL_PAIRS) != 28):
        return out

    by_kind: dict[str, EventVintageClaim] = {}
    for row in event_claims:
        if (type(row) is not EventVintageClaim
                or row.kind not in _SCHEDULE or row.kind in by_kind):
            out["reason"] = "DUPLICATE_UNKNOWN_OR_UNTYPED_MACRO_EVENT"
            return out
        by_kind[row.kind] = row
    if set(by_kind) != set(_SCHEDULE):
        out["reason"] = "INCOMPLETE_CPI_PPI_TWO_EVENT_ROSTER"
        return out

    event_rows = []
    consensus_visible_count = actual_visible_count = surprise_count = 0
    for kind in ("CPI", "PPI"):
        claim = by_kind[kind]
        release = _SCHEDULE[kind]
        consensus = claim.consensus
        actual = claim.actual
        if (consensus is None) != (claim.consensus_source_bytes is None):
            out["reason"] = "CONSENSUS_VALUE_OR_RAW_BYTES_MISSING"
            return out
        if (actual is None) != (claim.actual_source_bytes is None):
            out["reason"] = "ACTUAL_VALUE_OR_RAW_BYTES_MISSING"
            return out
        consensus_capture = actual_capture = None
        consensus_value = actual_value = None
        if consensus is not None:
            consensus_pub = _utc(consensus.published_at_utc)
            consensus_capture = _utc(consensus.locally_captured_at_utc)
            consensus_value = _pct(consensus.numeric_value)
            if (not _metric(consensus.metric, kind)
                    or consensus_pub is None or consensus_capture is None
                    or consensus_value is None
                    or not release - _LOOKBACK <= consensus_pub
                            <= consensus_capture < release
                    or not _origin(consensus.source_url, bls=False)
                    or not _sha_ok(claim.consensus_source_bytes,
                                   consensus.original_sha256_claim)):
                out["reason"] = "INVALID_PRE_RELEASE_CONSENSUS_VINTAGE_OR_METRIC"
                return out
        if actual is not None:
            actual_pub = _utc(actual.published_at_utc)
            actual_capture = _utc(actual.locally_captured_at_utc)
            actual_scheduled = _utc(actual.scheduled_release_at_utc)
            actual_value = _pct(actual.numeric_value)
            if (not _metric(actual.metric, kind)
                    or actual_pub is None or actual_capture is None
                    or actual_scheduled != release
                    or not release <= actual_pub <= actual_capture
                    or actual_value is None
                    or actual.first_print_vintage_claim != "FIRST_PRINT_CLAIM_ONLY"
                    or not _origin(actual.official_source_url, bls=True)
                    or not _sha_ok(claim.actual_source_bytes,
                                   actual.original_sha256_claim)):
                out["reason"] = "INVALID_FIRST_PRINT_OR_WRONG_METRIC_OR_RELEASE_CLOCK"
                return out

        c_vis = (consensus_capture is not None
                 and consensus_capture <= cutoff)
        a_vis = (actual_capture is not None
                 and release <= cutoff and actual_capture <= cutoff)
        if cutoff < release:
            stage = ("PRE_RELEASE_CONSENSUS_LOCAL_CLAIM_VISIBLE_NO_GO" if c_vis
                     else "PRE_RELEASE_CONSENSUS_NOT_YET_VISIBLE")
        elif a_vis and c_vis:
            stage = "POST_RELEASE_DOCUMENTARY_COMPARISON_ONLY_NO_GO"
        elif a_vis:
            stage = "POST_RELEASE_ACTUAL_ONLY_WITHOUT_PRE_EVENT_CONSENSUS"
        else:
            stage = "RELEASE_PASSED_BUT_ACTUAL_NOT_VISIBLE_AT_CUTOFF"

        surprise = str(actual_value - consensus_value) if a_vis and c_vis else None
        consensus_visible_count += int(c_vis)
        actual_visible_count += int(a_vis)
        surprise_count += int(surprise is not None)
        event_rows.append({
            "kind": kind,
            "metric_id": _IDS[kind],
            "reference_period": _PERIOD,
            "metric_transform": "MOM_SA_PERCENT",
            "scheduled_release_utc": release.isoformat(),
            "cutoff_stage": stage,
            "consensus_percent_local_claim_visible": (
                str(consensus_value) if c_vis else None),
            "actual_first_print_percent_local_claim_visible": (
                str(actual_value) if a_vis else None),
            "actual_minus_consensus_percentage_points_documentary": surprise,
            "consensus_source_bytes_sha256_locally_reconciled":
                bool(c_vis),
            "actual_source_bytes_sha256_locally_reconciled":
                bool(a_vis),
            "true_source_first_seen_independently_attested": False,
            "eligible_for_tradable_fx28_factor": False,
        })
    out.update({
        "state": "LAB_US_CPI_PPI_CUTOFF_LOCALLY_RECONCILED_UNATTESTED_NO_GO",
        "reason": "LOCAL_ORIGINAL_BYTES_AND_CLOCK_CLAIMS_NOT_INDEPENDENT_PIT_EVIDENCE",
        "economic_events_reconciled": 2,
        "feature_rows": event_rows,
        "research_events_with_pre_release_consensus_visible": consensus_visible_count,
        "research_events_with_first_print_visible_at_cutoff_claim_only": actual_visible_count,
        "documentary_surprises_comparable_after_release_only": surprise_count,
    })
    return out


__all__ = (
    "SCHEMA", "EventVintageClaim", "inspect_us_cpi_ppi_pit_cutoff_lab",
)
