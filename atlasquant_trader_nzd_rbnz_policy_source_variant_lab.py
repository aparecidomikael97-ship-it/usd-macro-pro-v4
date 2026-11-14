"""Admit the official October RBNZ decision article as NZD policy SOURCE.

The retired/denied OCR overview URL remains blocked for any new live HTTP
capture. Historical ORIGINALS from that page can still be replayed.

The RBNZ official RSS feed and article (real GitHub Actions #43590310919
and #43591408477 on 14 Nov 2026) provide an alternative *published OCR
decision* source whose source-bytes and HTTP receipt can be archived only
with explicit manual request. Do not claim that a prior ephemeral Action
already saved its original bytes on the user's AM12 computer.

The Oct 28 2026 4:3 HOLD at 2.75% is potentially the currently decided
policy rate only UNTIL the next scheduled RBNZ OCR decision on 9 Dec 2026
01:00Z. At/after the next event, an October decision ARTICLE is stale
even when captured in the last 24h. A new RBNZ release must be separately
validated after the event. Do not substitute bank forecasts or NZOR for
an issuer decided OCR.

This adapter is ONLY for offline evidence checking. A receipt's timestamp,
issuer URL and SHA are self-reported, not independent issuer first-seen
attestation, forecast, directional FX effect or trading authorization.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from atlasquant_trader_nzd_rbnz_ocr_receipt_lab import (
    URL as LEGACY_OVERVIEW_URL,
    inspect_rbnz_official_ocr_receipt_lab,
)
from atlasquant_trader_nzd_rbnz_ocr_decision_article_lab import (
    OCTOBER as OCTOBER_ARTICLE_URL,
    inspect_rbnz_ocr_decision_article_bytes_lab,
)
from atlasquant_trader_nzd_rbnz_dec9_three_bank_forecast_context_lab import (
    EVENT_UTC as NEXT_SCHEDULED_RBNZ_DECISION_UTC,
)

SCHEMA = "ATLASQUANT_NZD_RBNZ_POLICY_SOURCE_VARIANT_ADMISSION_LAB_V1"
ADMITTED_STATE = "LAB_NZD_RBNZ_POLICY_SOURCE_VARIANT_LOCALLY_CHECKED_NO_GO"
VARIANT_OCTOBER = "RBNZ_OCTOBER_OCR_HOLD_DECISION_ARTICLE_2026"
VARIANT_LEGACY = "RBNZ_LEGACY_OCR_OVERVIEW_HTML"
VARIANT_UNKNOWN = "UNRECOGNIZED_OR_UNTRUSTED_RBNZ_SOURCE"


def _utc(raw: Any) -> datetime | None:
    if type(raw) is not datetime or raw.tzinfo is None or raw.microsecond:
        return None
    try:
        return raw.astimezone(timezone.utc) if raw.utcoffset() is not None else None
    except (TypeError, ValueError, OverflowError):
        return None


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_NZD_RBNZ_POLICY_SOURCE_VARIANT_BLOCKED_NO_GO",
        "reason": reason,
        "source_variant": VARIANT_UNKNOWN,
        "source_original_sha256_locally_reconciled": False,
        "local_receipt_is_not_issuer_first_seen": True,
        "locally_checked_policy_event_month": None,
        "policy_action_claim": None,
        "policy_ocr_pct_claim": None,
        "source_variant_is_not_live_policy_feed": True,
        "next_rbnz_decision_utc": NEXT_SCHEDULED_RBNZ_DECISION_UTC.isoformat(),
        "policy_decided_rate_not_market_expectation": True,
        "upcoming_rbnz_forecast_not_issuer_ocr_actual": True,
        "source_bytes_saved_on_am12_by_this_function": False,
        "historical_point_in_time_first_seen_authenticated": False,
        "actual_market_consensus_verified": False,
        "calibrated_directional_fx_probability": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False,
        "publishable": False,
        "live_alert_allowed": False,
        "scheduler_enabled": False,
        "worker_enabled": False,
        "http_requests": 0,
        "file_writes": 0,
        "new_cost_brl": 0,
        "research_only": True,
    }


def inspect_nzd_rbnz_policy_variant_lab(
    *, original_html: Any, receipt: Any, decision_at_utc: Any
) -> dict[str, Any]:
    """Test original byte+local receipt. The next policy event is a HARD cut."""
    out = _base("INVALID_SOURCE_BYTES_RECEIPT_OR_CUTOFF")
    cutoff = _utc(decision_at_utc)
    if (type(original_html) is not bytes or type(receipt) is not dict
            or cutoff is None):
        return out
    source_url = receipt.get("source_url")
    if type(source_url) is not str:
        return out

    if source_url == LEGACY_OVERVIEW_URL:
        out["source_variant"] = VARIANT_LEGACY
        checked = inspect_rbnz_official_ocr_receipt_lab(
            original_html=original_html,
            receipt=receipt, decision_at_utc=cutoff)
        if checked["state"] != "LAB_NZD_RBNZ_OCR_HTML_LOCALLY_CHECKED_NO_GO":
            out["reason"] = checked["reason"]
            return out
        out.update({
            "state": ADMITTED_STATE,
            "reason": "LEGACY_OCR_OVERVIEW_DOCUMENT_CHECKED_NOT_A_TRADE",
            "source_original_sha256_locally_reconciled": True,
            "locally_checked_policy_event_month": "ISSUER_OVERVIEW_DATED_CARD",
            "policy_action_claim": None,
            "policy_ocr_pct_claim": checked["official_cash_rate_pct_claim"],
        })
        return out

    if source_url != OCTOBER_ARTICLE_URL:
        out["reason"] = "UNRECOGNIZED_OR_UNTRUSTED_RBNZ_SOURCE_URL"
        return out
    out["source_variant"] = VARIANT_OCTOBER
    # A decided rate published in OCTOBER is not current policy after the
    # next scheduled December OCR meeting, regardless of capture recency.
    if cutoff >= NEXT_SCHEDULED_RBNZ_DECISION_UTC:
        out["reason"] = "OCTOBER_POLICY_RELEASE_SUPERSEDED_AT_NEXT_DECISION"
        return out
    stamp = receipt.get("finished_at_utc")
    if type(stamp) is not str:
        return out
    try:
        capture_at = datetime.strptime(
            stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        out["reason"] = "RBNZ_OCTOBER_RECEIPT_FINISH_CLOCK_INVALID"
        return out
    if capture_at > cutoff:
        out["reason"] = "RBNZ_OCTOBER_CAPTURE_AFTER_REPLAY_CUTOFF"
        return out
    # This semantic validator requires an inspection within 30s of the
    # original receipt. Replaying months later must validate against the
    # CAPTURE clock first; cutoff has a separate order/supersession check.
    checked = inspect_rbnz_ocr_decision_article_bytes_lab(
        event_month="2026-10", original_html=original_html,
        receipt=receipt, inspected_at_utc=capture_at)
    if (checked["state"] !=
            "LAB_RBNZ_OCR_ACTUAL_DECISION_SENTENCE_EPHEMERAL_CHECKED_NO_GO"
            or checked.get("action") != "HOLD"
            or checked.get("ocr_percent_claim") != "2.75"
            or checked.get("committee_votes_to_hold") != 4
            or checked.get("committee_votes_against_hold") != 3
            or checked.get("article_original_sha256_local")
               != receipt.get("body_sha256")):
        out["reason"] = checked["reason"]
        return out
    out.update({
        "state": ADMITTED_STATE,
        "reason": "OCTOBER_OCR_HOLD_RELEASE_CHECKED_NOT_A_PREDICTION",
        "source_original_sha256_locally_reconciled": True,
        "locally_checked_policy_event_month": "2026-10",
        "policy_action_claim": "HOLD",
        "policy_ocr_pct_claim": "2.75",
    })
    return out


__all__ = (
    "SCHEMA", "ADMITTED_STATE", "VARIANT_OCTOBER", "VARIANT_LEGACY",
    "inspect_nzd_rbnz_policy_variant_lab",
)
