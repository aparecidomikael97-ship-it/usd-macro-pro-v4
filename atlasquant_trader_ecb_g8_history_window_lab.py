"""ECB G8 archived historical-window adapter, offline LAB/HARD NO-GO.

A 30-120 calendar-day official EXR request can be *planned* without HTTP.
On later manual capture, original response bytes plus a caller-declared
manifest can be internally validated using the strict existing ECB parser.

A passing archive remains UNATTESTED: no signature, historical availability,
independent FX spot, 90% proof, live bias or trading permission is granted.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Mapping
import re

from atlasquant_trader_ecb_sdmx_archive_lab import (
    RAW_PATH as LEGACY_RAW_PATH, SCHEMA as ARCHIVE_SCHEMA,
    STATE as ARCHIVE_STATE, expected_url, validate_ecb_archived_csv_lab,
)
from atlasquant_trader_ecb_reference_forward_outcomes_lab import (
    build_ecb_reference_forward_outcomes_lab,
)

SCHEMA = "ATLASQUANT_TRADER_ECB_G8_HISTORY_WINDOW_LAB_V1"
STATE = "LAB_ECB_HISTORY_ARCHIVE_STRUCTURALLY_VALID_EXPOST_ONLY"
PLAN_ONLY = "LAB_OFFLINE_HISTORY_CAPTURE_PLAN_ONLY"
DENIED = "LAB_ECB_HISTORY_WINDOW_REFUSED"
MIN_WINDOW_DAYS = 30
MAX_WINDOW_DAYS = 120
PATH_RE = re.compile(r"^docs/continuidade/ecb_exr_g8_[0-9]{8}_[0-9]{8}_raw\.csv$")


def _date(x: Any) -> date | None:
    if not isinstance(x, str) or len(x) != 10:
        return None
    try:
        d = date.fromisoformat(x)
    except ValueError:
        return None
    return d if d.isoformat() == x else None


def _window(start: Any, end: Any) -> tuple[date, date] | None:
    a, b = _date(start), _date(end)
    if (a is None or b is None or a.weekday() >= 5 or b.weekday() >= 5
            or not MIN_WINDOW_DAYS <= (b - a).days <= MAX_WINDOW_DAYS):
        return None
    return a, b


def archive_path(start: str, end: str) -> str:
    """Deterministic offline relative path; never accepts arbitrary paths."""
    dates = _window(start, end)
    if dates is None:
        raise ValueError("A historical window needs published-weekday endpoints and 30-120 days")
    a, b = dates
    return (f"docs/continuidade/ecb_exr_g8_{a:%Y%m%d}_"
            f"{b:%Y%m%d}_raw.csv")


def _refuse(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": DENIED, "reason": reason,
        "original_eur_series": 0, "observation_dates": [],
        "reference_quotes_by_date": {}, "monthly_outcome_anchor_dates": [],
        "archive_hash_internally_matched": False,
        "official_origin_cryptographically_verified": False,
        "historical_as_of_capture_independently_attested": False,
        "official_daily_revisions_tracked": False,
        "independent_spot_quotes_verified": 0,
        "can_feed_real_oos": False, "can_feed_live_bias": False,
        "probability_calibrated": False, "accuracy_90_proven": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "trade_authorized": False,
    }


def plan_ecb_g8_history_window_lab(
    start: str, end: str, *, planned_at: datetime,
) -> dict[str, Any]:
    """Generate exact manual official source request; performs no download."""
    if not isinstance(planned_at, datetime) or planned_at.tzinfo is None:
        raise ValueError("Planning instant must be timezone aware")
    dates = _window(start, end)
    if dates is None:
        return _refuse("Invalid endpoints or interval outside 30-120 calendar days")
    a, b = dates
    if b > planned_at.astimezone(timezone.utc).date():
        return _refuse("Cannot plan a historical snapshot extending into the future")
    return {
        **_refuse(""), "state": PLAN_ONLY, "reason": None,
        "query_start": a.isoformat(), "query_end": b.isoformat(),
        "expected_official_url": expected_url(a.isoformat(), b.isoformat()),
        "required_raw_path": archive_path(a.isoformat(), b.isoformat()),
        "manifest_schema": ARCHIVE_SCHEMA,
        "required_original_currencies_per_day": 7,
        "minimum_original_reference_dates_for_real_oos": None,
        "manual_capture_required": True,
        "http_performed": False, "data_downloaded": False,
        "forecast_issued": False,
    }


def validate_ecb_g8_history_window_lab(
    raw: bytes, manifest: Any, *, evaluated_at: datetime,
) -> dict[str, Any]:
    """Validate archived raw response structure, never historical authenticity.

    The strict legacy parser has one fixed raw path. This adapter validates
    the historical window's path first, then substitutes that path only in an
    ephemeral copy, reusing every existing field/clock/CSV/hash guard.
    Original archive bytes, source URL and manifest are never modified.
    """
    if not isinstance(evaluated_at, datetime) or evaluated_at.tzinfo is None:
        raise ValueError("Audit instant must be timezone aware")
    if not isinstance(manifest, Mapping):
        return _refuse("Archive manifest missing")
    start, end = manifest.get("query_start"), manifest.get("query_end")
    if _window(start, end) is None:
        return _refuse("History manifest window invalid or outside 30-120 days")
    path = manifest.get("raw_path")
    required_path = archive_path(start, end)
    if not isinstance(path, str) or not PATH_RE.fullmatch(path) or path != required_path:
        return _refuse("Archive path must match the exact official query window")
    # Expected URL/date/status/hash verification remains in the stricter core.
    normalized = dict(manifest)
    normalized["raw_path"] = LEGACY_RAW_PATH
    verified = validate_ecb_archived_csv_lab(
        raw, normalized, evaluated_at=evaluated_at,
    )
    if verified["state"] != ARCHIVE_STATE:
        return _refuse("Core ECB archive refused: " + str(verified["reason"]))
    observations = [date.fromisoformat(x) for x in verified["observation_dates"]]
    monthly = []
    for anchor in observations:
        begin, last = anchor + timedelta(days=30), anchor + timedelta(days=42)
        if any(begin <= settled <= last for settled in observations):
            monthly.append(anchor.isoformat())
    return {
        **_refuse(""), "state": STATE, "reason": None,
        "raw_path": path,
        "source_url": manifest["source_url"],
        "query_start": start, "query_end": end,
        "archive_body_sha256": verified["body_sha256"],
        "archive_hash_internally_matched": True,
        "original_eur_series": verified["original_eur_series"],
        "derived_crosses_not_independent": 21,
        "observation_dates": verified["observation_dates"],
        "reference_quotes_by_date": verified["reference_quotes_by_date"],
        "monthly_outcome_anchor_dates": monthly,
        "monthly_outcome_anchors_possible_expost": len(monthly),
        "archive_timestamp_evidence": (
            "Caller-declared metadata only; capture time, server headers "
            "and earlier availability have not been independently attested."
        ),
    }


def build_ecb_g8_history_outcomes_lab(
    raw: bytes, manifest: Any, *, anchor_date: str, evaluated_at: datetime,
) -> dict[str, Any]:
    """Reuse fixed D1/W1/MN1 ex-post labels after full window validation."""
    verified = validate_ecb_g8_history_window_lab(
        raw, manifest, evaluated_at=evaluated_at,
    )
    if verified["state"] != STATE:
        return _refuse("Cannot compute history labels: " + str(verified["reason"]))
    normalized = dict(manifest)
    normalized["raw_path"] = LEGACY_RAW_PATH
    outcomes = build_ecb_reference_forward_outcomes_lab(
        raw, normalized, anchor_date=anchor_date, evaluated_at=evaluated_at,
    )
    return {
        **outcomes,
        "history_window_schema": SCHEMA,
        "history_archive_state": STATE,
        "history_original_raw_path": manifest["raw_path"],
        "history_origin_independently_attested": False,
        "can_feed_real_oos": False,
        "can_feed_live_bias": False,
        "trade_authorized": False,
    }


__all__ = [
    "SCHEMA", "STATE", "PLAN_ONLY", "DENIED",
    "MIN_WINDOW_DAYS", "MAX_WINDOW_DAYS", "archive_path",
    "plan_ecb_g8_history_window_lab",
    "validate_ecb_g8_history_window_lab",
    "build_ecb_g8_history_outcomes_lab",
]
