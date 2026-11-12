"""Competing macro calendar context for the one-event US PPI study (LAB).

Never claim that no other news occurred based on one incomplete calendar.
A pre-event, caller-supplied snapshot is documentary only; its publisher
bytes, coverage, captures, actual occurrence and clock are NOT authenticated.
Reports candidate co-releases and baseline contamination, not causality,
direction, forecast skill, executable prices or risk approvals.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any

from atlasquant_fx_universe import CURRENCIES
from atlasquant_trader_ppi_usd_fx_forward_reaction_lab import (
    BASELINE_OPEN_UTC, EVENT_UTC, LAST_REQUIRED_CLOSE_UTC, WINDOWS,
)

SCHEMA = "ATLASQUANT_TRADER_PPI_COMPETING_MACRO_CALENDAR_LAB_V1"
ROOT = "US_PPI_OCT2026"
HEX = re.compile(r"[a-f0-9]{64}\Z")
IDENT = re.compile(r"[A-Z0-9][A-Z0-9_-]{2,79}\Z")
CATEGORIES = frozenset(("MACRO_DATA", "CENTRAL_BANK", "POLICY_SPEECH",
                        "GEOPOLITICAL", "OTHER_MARKET_CATALYST"))
IMPACTS = frozenset(("HIGH", "MEDIUM", "LOW", "UNASSESSED"))
ALLOWED_CURRENCIES = frozenset(CURRENCIES) | {"GLOBAL"}
MAX_EVENTS = 150


@dataclass(frozen=True)
class CompetingEventClaim:
    root_id: str
    scheduled_at_utc: datetime
    currency_or_global: str
    category: str
    impact_claim: str


@dataclass(frozen=True)
class PreEventCalendarClaim:
    captured_at_utc: datetime
    covered_from_utc: datetime
    covered_until_utc: datetime
    source_sha256_claim: str
    claims_complete_for_covered_period: bool
    events: tuple[CompetingEventClaim, ...]


def _utc(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None or value.microsecond):
        return None
    return value.astimezone(timezone.utc)


def _base(reason: str, state: str = "LAB_PPI_COMPETING_CALENDAR_BLOCKED") -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": state, "reason": reason,
        "event_root_id": ROOT, "economic_event_count": 1,
        "calendar_captured_pre_release_claim": False,
        "calendar_period_claims_complete_unattested": False,
        "calendar_sha256_format_valid_only": False,
        "candidate_competing_root_count_documentary": None,
        "candidate_baseline_contamination_roots_documentary": None,
        "candidate_competing_roots_by_reaction_window": None,
        "candidate_competing_events_detail": None,
        "causal_isolation_of_ppi_verified": False,
        "clean_event_window_independently_verified": False,
        "calendar_source_and_actual_event_times_authenticated": False,
        "no_competing_events_proven": False,
        "missing_or_uncertain_calendar_requires_review": True,
        "price_or_macro_bias": None, "validated_accuracy": None,
        "calibrated_probability": None,
        "operational_bias": "AGUARDAR", "trade_authorized": False,
        "publishable": False, "live_alert_allowed": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "http_requests": 0, "file_writes": 0, "new_cost_brl": 0,
    }


def audit_ppi_competing_calendar_lab(
    *, calendar: Any, as_of_utc: Any,
) -> dict[str, Any]:
    """Classify claimed contemporaneous event roots without hindsight.

    Baseline bar is [13:15, 13:30), post-event windows are [13:30, end).
    Exclude only the target PPI root from competing events. Other metrics
    at the same minute, if a different root, remain possible confounders.
    """
    now = _utc(as_of_utc)
    if now is None:
        return _base("INVALID_INSPECTION_CLOCK")
    if calendar is None:
        return _base("NO_PRE_EVENT_CALENDAR_CUSTODY_SUPPLIED",
                     "LAB_PPI_COMPETING_CALENDAR_UNKNOWN_REVIEW_REQUIRED")
    if not isinstance(calendar, PreEventCalendarClaim):
        return _base("INVALID_CALENDAR_CLAIM_TYPE")
    captured = _utc(calendar.captured_at_utc)
    begin = _utc(calendar.covered_from_utc)
    end = _utc(calendar.covered_until_utc)
    if (captured is None or begin is None or end is None
            or captured > now or captured >= EVENT_UTC
            or begin > BASELINE_OPEN_UTC or end < LAST_REQUIRED_CLOSE_UTC
            or begin >= end
            or calendar.claims_complete_for_covered_period is not True
            or not isinstance(calendar.source_sha256_claim, str)
            or HEX.fullmatch(calendar.source_sha256_claim) is None
            or not isinstance(calendar.events, tuple)
            or len(calendar.events) > MAX_EVENTS):
        return _base("PRE_EVENT_CALENDAR_CAPTURE_COVERAGE_OR_HASH_INVALID")

    by_root: dict[str, tuple[datetime, str, str, str]] = {}
    for event in calendar.events:
        if not isinstance(event, CompetingEventClaim):
            return _base("INVALID_COMPETING_EVENT_RECORD")
        when = _utc(event.scheduled_at_utc)
        if (when is None or not isinstance(event.root_id, str)
                or IDENT.fullmatch(event.root_id) is None
                or event.currency_or_global not in ALLOWED_CURRENCIES
                or event.category not in CATEGORIES
                or event.impact_claim not in IMPACTS
                or not begin <= when < end):
            return _base("INVALID_EVENT_ID_CURRENCY_CATEGORY_OR_TIME")
        signature = (when, event.currency_or_global,
                     event.category, event.impact_claim)
        # Multiple economic metrics with same root are ONE underlying cause,
        # but conflicting timestamps/metadata cannot be silently collapsed.
        if event.root_id in by_root and by_root[event.root_id] != signature:
            return _base("SAME_ROOT_WITH_CONFLICTING_TIME_OR_METADATA")
        by_root[event.root_id] = signature
    anchor = by_root.get(ROOT)
    if (anchor is not None and
            (anchor[0] != EVENT_UTC or anchor[1] != "USD"
             or anchor[2] != "MACRO_DATA")):
        return _base("PPI_ROOT_RELABELED_OR_WRONG_RELEASE_TIME")
    competing = {
        root: signature for root, signature in by_root.items()
        if root != ROOT and BASELINE_OPEN_UTC <= signature[0] < LAST_REQUIRED_CLOSE_UTC
    }
    baseline = sorted(root for root, (when, *_rest) in competing.items()
                      if BASELINE_OPEN_UTC <= when < EVENT_UTC)
    per_window = {}
    for label, minutes in WINDOWS:
        cutoff = EVENT_UTC.timestamp() + minutes * 60
        per_window[label] = sorted(
            root for root, (when, *_rest) in competing.items()
            if EVENT_UTC <= when and when.timestamp() < cutoff
        )
    detail = [
        {
            "root_id": root,
            "scheduled_at_utc_claim": signature[0].isoformat(),
            "currency_or_global": signature[1],
            "category": signature[2],
            "impact_claim_unverified": signature[3],
            "occurrence_and_market_relevance_not_confirmed": True,
        } for root, signature in sorted(competing.items())
    ]
    has_competing = bool(competing)
    out = _base(
        "CONCURRENT_EVENT_CANDIDATES_NOT_CAUSAL_ESTIMATES" if has_competing
        else "NO_COMPETING_ROOTS_LISTED_IN_ONE_UNVERIFIED_CALENDAR",
        "LAB_PPI_COMPETING_ROOTS_DOCUMENTARY_REVIEW_REQUIRED" if has_competing
        else "LAB_PPI_EMPTY_COMPETING_LIST_UNATTESTED_REVIEW_REQUIRED",
    )
    out.update({
        "calendar_captured_pre_release_claim": True,
        "calendar_period_claims_complete_unattested": True,
        "calendar_sha256_format_valid_only": True,
        "candidate_competing_root_count_documentary": len(competing),
        "candidate_baseline_contamination_roots_documentary": baseline,
        "candidate_competing_roots_by_reaction_window": per_window,
        "candidate_competing_events_detail": detail,
    })
    return out


__all__ = ("SCHEMA", "CompetingEventClaim", "PreEventCalendarClaim",
           "audit_ppi_competing_calendar_lab")
