"""BoJ October 2026 archived decision: conservative scheduled-cycle EXPIRY.

An already checked historic PDF can remain valid *as an archived document*
after the next scheduled policy meeting. It cannot automatically remain a
current decision-context candidate. This module adds a time-bound label
WITHOUT adding any current issuer packet, direction, certainty or trade.

No API, network, MT5, broker, accounts, files, scheduling or deployment.
The BOJ's official 2026 meeting calendar can change, and unscheduled
decisions are possible; a calendar alone never authenticates "latest".
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from atlasquant_trader_fx28_historical_release_overlay_lab import (
    SCHEMA as OVERLAY_SCHEMA,
)

SCHEMA = "ATLASQUANT_JPY_BOJ_ARCHIVED_RELEASE_CYCLE_EXPIRY_LAB_V1"

# Primary sources, publicly reviewed on 2026-11-15:
# Oct 30 2026 12:02 JST (03:02 UTC) press release, rate ~1.25%, vote 8:1.
OFFICIAL_DECISION_URL = "https://www.boj.or.jp/en/mopo/mpmdeci/mpr_2026/k261030a.pdf"
OFFICIAL_MEETING_CALENDAR_URL = "https://www.boj.or.jp/en/mopo/mpmsche_minu/"
DECISION_PUBLICATION_DATE_UTC = datetime(2026, 10, 30, 3, 2, tzinfo=timezone.utc)
# Next regular MPM is December 17-18 JST. Expire at the START of
# December 17 in Japan, deliberately before any monetary decision,
# rather than making assumptions about the actual release hour.
NEXT_SCHEDULED_MEETING_EARLIEST_UTC = datetime(
    2026, 12, 16, 15, 0, tzinfo=timezone.utc
)

def _time(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    try:
        if value.utcoffset() is None:
            return None
        return value.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None

def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_JPY_BOJ_RELEASE_CYCLE_INPUT_BLOCKED_NO_GO",
        "reason": reason,
        "official_statement_url": OFFICIAL_DECISION_URL,
        "official_calendar_url": OFFICIAL_MEETING_CALENDAR_URL,
        "decision_publication_utc": DECISION_PUBLICATION_DATE_UTC.isoformat(),
        "next_scheduled_meeting_start_guard_utc":
            NEXT_SCHEDULED_MEETING_EARLIEST_UTC.isoformat(),
        "archived_october_documentary_source_locally_checked_claim": False,
        "scheduled_context_window_not_expired": False,
        "calendar_snapshot_might_change": True,
        "intermeeting_unscheduled_policy_decision_excluded_by_calendar": False,
        "issuer_latest_policy_independently_authenticated": False,
        "issuer_current_policy_homepage_accepted": False,
        "source_origin_independently_authenticated": False,
        "policy_statement_is_not_new_event_surprise": True,
        "source_was_captured_before_oct30_release_authenticated": False,
        "rate_is_not_currency_direction": True,
        "signed_fx_effects_calibrated": 0,
        "usd_jpy_or_seven_yen_crosses_directional_bias": None,
        "fx_accuracy": None,
        "trade_authorized": False,
        "operational_bias": "AGUARDAR",
        "publishable": False,
        "http_calls": 0, "mt5_calls": 0, "file_writes": 0,
    }

def review_jpy_october_release_cycle_lab(
    *, historical_overlay_report: Any, inspected_at_utc: Any
) -> dict[str, Any]:
    out = _base("OVERLAY_OR_AS_OF_INVALID")
    at = _time(inspected_at_utc)
    r = historical_overlay_report
    if at is None or type(r) is not dict:
        return out
    if (r.get("schema") != OVERLAY_SCHEMA
            or r.get("state") != "LAB_FX28_DOCUMENTARY_OVERLAY_RECONCILED_NO_GO"
            or r.get("trade_authorized") is not False
            or r.get("publishable") is not False
            or r.get("calibrated_probability") is not None
            or r.get("directional_bias") is not None
            or type(r.get("base_current_source_currencies")) is not list
            or type(r.get("new_historical_docs_checked")) is not list
            or type(r.get("new_historical_docs_rejected")) is not dict
            or r.get("signed_fx_macro_direction_effects_accepted") != 0):
        return out
    current = r["base_current_source_currencies"]
    hist = r["new_historical_docs_checked"]
    if (any(type(c) is not str for c in current + hist)
            or len(set(current)) != len(current)
            or len(set(hist)) != len(hist)
            or "JPY" in current):
        out["reason"] = "JPY_CURRENT_HOMEPAGE_MUST_BE_A_SEPARATE_SOURCE_CONTRACT"
        return out
    if "JPY" not in hist or "JPY" in r["new_historical_docs_rejected"]:
        out["reason"] = "JPY_ARCHIVED_RELEASE_NOT_CHECKED"
        return out
    out["archived_october_documentary_source_locally_checked_claim"] = True
    if at < DECISION_PUBLICATION_DATE_UTC:
        out["reason"] = "BEFORE_OCT30_DECISION_PUBLICATION_CANNOT_USE_HINDSIGHT"
        return out
    if at >= NEXT_SCHEDULED_MEETING_EARLIEST_UTC:
        out.update({
            "state": "LAB_JPY_BOJ_ARCHIVED_CONTEXT_EXPIRED_NO_GO",
            "reason": "NEXT_SCHEDULED_POLICY_MEETING_HAS_BEGUN_REVALIDATE_SOURCE",
        })
        return out
    out.update({
        "state": "LAB_JPY_BOJ_ARCHIVED_CONTEXT_WITHIN_SCHEDULED_CYCLE_ONLY_NO_GO",
        "reason": "OCT30_DOCUMENT_CHECKED_BUT_LATEST_POLICY_NOT_AUTHENTICATED",
        "scheduled_context_window_not_expired": True,
    })
    return out

__all__ = ("SCHEMA", "review_jpy_october_release_cycle_lab")
