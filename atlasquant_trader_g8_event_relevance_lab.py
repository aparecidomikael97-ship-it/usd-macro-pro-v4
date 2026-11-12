"""Route G8 economic event *relevance* to the 28 crosses, never a bias.

Events and their clock fields are caller-supplied, NOT authenticated feed data.
The module distinguishes pre-event consensus, post-event unverified actual,
and the arithmetic difference. No economic surprise is automatically a
currency-strength sign, index bias, probability or trade instruction.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import re
from typing import Any

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair

SCHEMA = "ATLASQUANT_TRADER_G8_EVENT_RELEVANCE_READONLY_LAB_V1"
METRIC_UNITS = {
    "CPI_MOM": "PERCENT_MOM_SA",
    "CPI_CORE_MOM": "PERCENT_MOM_SA",
    "CPI_YOY": "PERCENT_YOY_NSA",
    "CPI_CORE_YOY": "PERCENT_YOY_NSA",
    "PCE_MOM": "PERCENT_MOM_SA",
    "PCE_YOY": "PERCENT_YOY_NSA",
    "PCE_CORE_MOM": "PERCENT_MOM_SA",
    "PCE_CORE_YOY": "PERCENT_YOY_NSA",
    "PPI_MOM": "PERCENT_MOM_SA",
    "PPI_CORE_MOM": "PERCENT_MOM_SA",
    "NFP_CHANGE": "PERSONS_CHANGE_SA",
    "POLICY_RATE": "PERCENT_POLICY_RATE",
    "UNEMPLOYMENT_RATE": "PERCENT_RATE",
    "GDP_QOQ": "PERCENT_QOQ_SA",
}
IMPORTANCE = frozenset(("HIGH", "MEDIUM", "LOW"))
PPI_RELEASE_METRICS = frozenset(("PPI_MOM", "PPI_CORE_MOM"))
_ID = re.compile(r"[A-Z0-9][A-Z0-9_\-]{2,63}\Z")
_MONTH = re.compile(r"\d{4}-(0[1-9]|1[0-2])\Z")
_QUARTER = re.compile(r"\d{4}-Q[1-4]\Z")
_DATE = re.compile(r"\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])\Z")
_HEX = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class EventSnapshot:
    event_id: str
    currency: str
    metric: str
    target_period: str
    unit: str
    importance: str
    scheduled_release_at: datetime
    calendar_captured_at: datetime
    consensus_value: str | None = None
    consensus_captured_at: datetime | None = None
    actual_value: str | None = None
    actual_published_at: datetime | None = None
    actual_captured_at: datetime | None = None
    original_sha256_claim: str | None = None
    previous_value: str | None = None
    previous_reference_period: str | None = None
    previous_published_at: datetime | None = None
    previous_captured_at: datetime | None = None


def _utc(v: Any) -> datetime | None:
    if not isinstance(v, datetime) or v.tzinfo is None or v.utcoffset() is None:
        return None
    return v.astimezone(timezone.utc)


def _num(v: Any) -> Decimal | None:
    if not isinstance(v, str) or not 1 <= len(v) <= 32:
        return None
    try:
        d = Decimal(v)
    except InvalidOperation:
        return None
    return d if d.is_finite() and abs(d) <= Decimal("1000000000") else None


def _matching_period(metric: str, period: str) -> bool:
    if metric == "GDP_QOQ":
        return _QUARTER.fullmatch(period) is not None
    if metric != "POLICY_RATE":
        return _MONTH.fullmatch(period) is not None
    if _MONTH.fullmatch(period):
        return True
    if not _DATE.fullmatch(period):
        return False
    try:
        return datetime.strptime(period, "%Y-%m-%d").date().isoformat() == period
    except ValueError:
        return False


def _economic_period_not_after_release(metric: str, period: str,
                                       scheduled: datetime) -> bool:
    """Reject impossible future economic periods without claiming true release.

    CPI/PCE/labour reference months cannot follow their purported release
    month; a GDP quarter cannot even end after the purported release month.
    Same-month flash estimates remain documentary and source-unattested.
    Policy meeting/effective-date semantics need a separate issuer gate.
    """
    if metric == "POLICY_RATE":
        return True
    if metric == "GDP_QOQ":
        match = _QUARTER.fullmatch(period)
        return (match is not None and
                (int(period[:4]), int(period[-1]) * 3) <=
                (scheduled.year, scheduled.month))
    match = _MONTH.fullmatch(period)
    return (match is not None and
            (int(period[:4]), int(period[5:7])) <=
            (scheduled.year, scheduled.month))


def _previous_period_is_immediately_before(metric: str, current: str,
                                           previous: str) -> bool:
    """A stale month/quarter is not the 'previous result' for this event."""
    if metric == "POLICY_RATE":
        # Meeting intervals are irregular. Enforce older date with matching
        # precision, never infer which meeting was the actual predecessor.
        return (len(current) == len(previous)
                and _matching_period(metric, previous)
                and previous < current)
    if metric == "GDP_QOQ":
        if not _QUARTER.fullmatch(current) or not _QUARTER.fullmatch(previous):
            return False
        current_index = int(current[:4]) * 4 + int(current[-1])
        prior_index = int(previous[:4]) * 4 + int(previous[-1])
        return current_index - prior_index == 1
    if not _MONTH.fullmatch(current) or not _MONTH.fullmatch(previous):
        return False
    current_index = int(current[:4]) * 12 + int(current[5:7])
    prior_index = int(previous[:4]) * 12 + int(previous[5:7])
    return current_index - prior_index == 1


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_EVENT_ROUTER_BLOCKED", "reason": reason,
        "as_of_utc": None, "currency_count": 0, "pair_count": 0,
        "event_count": 0, "events": [], "pair_rows": [],
        "claimed_release_root_count": 0, "independent_event_trial_count": None,
        "event_calendar_completeness_verified": False,
        "source_original_bytes_authenticated": False,
        "pre_event_consensus_independently_attested": False,
        "post_event_actual_independently_attested": False,
        "market_reaction_direction_validated": False,
        "relative_currency_strength_available": False,
        "calibrated_direction_probability": None,
        "fx_bias": None, "index_bias": None,
        "operational_bias": "AGUARDAR", "publishable": False,
        "trade_authorized": False, "live_alert_allowed": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "http_requests": 0, "new_cost_brl": 0,
        "research_only": True,
    }


def _event_row(v: EventSnapshot, now: datetime) -> dict[str, Any] | None:
    scheduled = _utc(v.scheduled_release_at)
    calendar = _utc(v.calendar_captured_at)
    if (scheduled is None or calendar is None or calendar > now
            or calendar > scheduled
            or not isinstance(v.event_id, str) or _ID.fullmatch(v.event_id) is None
            or v.currency not in CURRENCIES or not isinstance(v.metric, str)
            or METRIC_UNITS.get(v.metric) != v.unit
            or not isinstance(v.target_period, str)
            or not _matching_period(v.metric, v.target_period)
            or not _economic_period_not_after_release(
                v.metric, v.target_period, scheduled)
            or not isinstance(v.importance, str)
            or v.importance not in IMPORTANCE):
        return None
    if (v.original_sha256_claim is not None
            and (not isinstance(v.original_sha256_claim, str)
                 or _HEX.fullmatch(v.original_sha256_claim) is None)):
        return None

    has_consensus = v.consensus_value is not None
    has_actual = v.actual_value is not None
    consensus = _num(v.consensus_value) if has_consensus else None
    actual = _num(v.actual_value) if has_actual else None
    consensus_at = _utc(v.consensus_captured_at)
    published_at = _utc(v.actual_published_at)
    actual_at = _utc(v.actual_captured_at)
    has_previous = v.previous_value is not None
    previous = _num(v.previous_value) if has_previous else None
    previous_published = _utc(v.previous_published_at)
    previous_at = _utc(v.previous_captured_at)
    if ((has_consensus and (consensus is None or consensus_at is None
                            or consensus_at > now or consensus_at >= scheduled))
            or (not has_consensus and v.consensus_captured_at is not None)
            or (has_actual and (actual is None or published_at is None or actual_at is None
                                or published_at < scheduled or published_at > actual_at
                                or actual_at > now))
            or (not has_actual and (v.actual_published_at is not None
                                    or v.actual_captured_at is not None))
            or (has_previous and (
                previous is None or not isinstance(v.previous_reference_period, str)
                or not _previous_period_is_immediately_before(
                    v.metric, v.target_period, v.previous_reference_period)
                or previous_published is None or previous_at is None
                or previous_published > previous_at
                or previous_at > now or previous_at >= scheduled))
            or (not has_previous and (
                v.previous_reference_period is not None
                or v.previous_published_at is not None
                or v.previous_captured_at is not None))):
        return None

    # A snapshot containing actual data cannot exist before the release as-of.
    # This is not the same as validating that the caller's timestamp is true.
    if has_actual:
        phase = ("POST_RELEASE_DIFFERENCE_DOCUMENTARY_UNATTESTED"
                 if has_consensus else "POST_RELEASE_ACTUAL_WITHOUT_CONSENSUS")
    elif now >= scheduled:
        phase = "RELEASE_PASSED_ACTUAL_NOT_AVAILABLE"
    else:
        phase = "PRE_RELEASE_CALENDAR_AND_CONSENSUS_CLAIM_ONLY"
    return {
        "event_id": v.event_id, "currency": v.currency,
        "metric": v.metric, "target_period": v.target_period, "unit": v.unit,
        # Headline/core PPI are components of ONE report, not two trials.
        # A root identifier is a caller-metadata claim, NOT causal evidence.
        "claimed_release_root": (
            f"{v.currency}_PPI_{v.target_period}"
            if v.metric in PPI_RELEASE_METRICS else v.event_id),
        "importance": v.importance, "scheduled_release_utc": scheduled.isoformat(),
        "phase": phase,
        "consensus_documentary": str(consensus) if consensus is not None else None,
        "previous_documentary": str(previous) if previous is not None else None,
        "previous_reference_period": (v.previous_reference_period
                                       if previous is not None else None),
        "previous_claimed_captured_utc": (previous_at.isoformat()
                                          if previous_at is not None else None),
        "actual_documentary": str(actual) if actual is not None else None,
        "actual_minus_consensus_documentary": (
            str(actual - consensus) if actual is not None and consensus is not None else None),
        "actual_minus_previous_documentary": (
            str(actual - previous) if actual is not None and previous is not None else None),
        "calendar_claimed_captured_utc": calendar.isoformat(),
        "consensus_claimed_captured_utc": (consensus_at.isoformat()
                                            if consensus_at is not None else None),
        "actual_claimed_captured_utc": (actual_at.isoformat()
                                         if actual_at is not None else None),
        "source_hash_claim_only_not_authenticated": v.original_sha256_claim is not None,
        "previous_result_or_revision_independently_attested": False,
        "surprise_is_currency_strength_direction": False,
        "release_time_is_independently_verified": False,
    }


def inspect_g8_event_relevance_lab(events: Any, *, as_of_utc: Any) -> dict[str, Any]:
    """Create documentary per-pair event context; no feed, signals or alerts."""
    out = _blocked("INVALID_CLOCK_EVENTS_OR_UNIVERSE")
    now = _utc(as_of_utc)
    if (now is None or not isinstance(events, (list, tuple))
            or len(events) > 32 or len(CURRENCIES) != 8
            or len(OFFICIAL_PAIRS) != 28):
        return out
    rows = []
    seen_ids = set()
    seen_metric_periods = set()
    ppi_release_times = {}
    for item in events:
        if not isinstance(item, EventSnapshot):
            return out
        row = _event_row(item, now)
        if row is None or row["event_id"] in seen_ids:
            out["reason"] = "INVALID_EVENT_SEMANTICS_PIT_OR_DUPLICATE"
            return out
        seen_ids.add(row["event_id"])
        key = (row["currency"], row["metric"], row["target_period"])
        if key in seen_metric_periods:
            out["reason"] = "DUPLICATE_ECONOMIC_METRIC_PERIOD_NOT_NEW_EVIDENCE"
            return out
        seen_metric_periods.add(key)
        if row["metric"] in PPI_RELEASE_METRICS:
            root = row["claimed_release_root"]
            previous_clock = ppi_release_times.setdefault(root, row["scheduled_release_utc"])
            if previous_clock != row["scheduled_release_utc"]:
                out["reason"] = "PPI_HEADLINE_CORE_RELEASE_CLOCK_CONFLICT"
                return out
        rows.append(row)

    pairs = []
    for pair in OFFICIAL_PAIRS:
        base, quote = split_pair(pair)
        relevant = [
            {"event_id": row["event_id"], "currency": row["currency"],
             "claimed_release_root": row["claimed_release_root"],
             "role": "BASE" if row["currency"] == base else "QUOTE",
             "phase": row["phase"],
             "high_impact": row["importance"] == "HIGH",
             "actual_minus_consensus_documentary": row[
                 "actual_minus_consensus_documentary"],
             "previous_documentary": row["previous_documentary"],
             "actual_minus_previous_documentary": row[
                 "actual_minus_previous_documentary"],
             "fx_direction_from_event": None}
            for row in rows if row["currency"] in (base, quote)
        ]
        pairs.append({
            "pair": pair, "base": base, "quote": quote,
            "relevant_events_documentary_only": relevant,
            "event_count": len(relevant),
            "claimed_release_root_count": len({
                item["claimed_release_root"] for item in relevant}),
            "needs_actual_or_source_review": any(
                x["phase"] == "RELEASE_PASSED_ACTUAL_NOT_AVAILABLE"
                for x in relevant),
            "macro_bilateral_impact_score": None,
            "D1": "AGUARDAR", "W1": "AGUARDAR", "MN1": "AGUARDAR",
            "fx_bias": None, "trade_authorized": False,
        })

    out.update({
        "state": "LAB_G8_EVENT_RELEVANCE_DOCUMENTARY_ONLY_NO_BIAS",
        "reason": "EVENT_RELEVANCE_NOT_CAUSAL_FX_DIRECTION_OR_VERIFIED_SURPRISE",
        "as_of_utc": now.isoformat(),
        "currency_count": 8, "pair_count": len(pairs),
        "event_count": len(rows), "events": rows, "pair_rows": pairs,
        "claimed_release_root_count": len({
            item["claimed_release_root"] for item in rows}),
        "independent_event_trial_count": None,
    })
    return out


__all__ = ["SCHEMA", "EventSnapshot", "inspect_g8_event_relevance_lab"]
