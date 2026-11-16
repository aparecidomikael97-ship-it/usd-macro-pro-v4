"""Fixed four-event US CPI/PPI original-byte documentary census: Sep/Oct 2026.

This is NOT an OOS trial ledger and NEVER fabricates a pre-release consensus
or FX prediction from documents obtained after the economic publication.
Every missing/future source stays in the fixed denominator 4, with the
first locally claimed capture time respected to the microsecond. Feed REAL
BLS bytes to existing strict issuer-specific release parsers, not another
caller-entered actual number. No network, filesystem, MT5, broker, orders.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from atlasquant_trader_us_bls_sep2026_original_pair_once_lab import (
    SPECS as SEP_SPECS, inspect_sep2026_bls_release_body_lab,
)
from atlasquant_trader_us_oct2026_cpi_release_text_guard_lab import (
    ClaimedBLSHtmlReceipt, URL as OCT_CPI_URL,
    RELEASE_FLOOR_UTC as OCT_CPI_RELEASE, inspect_bls_oct2026_release_text_lab,
)
from atlasquant_trader_us_ppi_oct2026_actual_table_guard_lab import (
    ClaimedPostReleaseHTTP, OFFICIAL_URL as OCT_PPI_URL,
    RELEASE_UTC as OCT_PPI_RELEASE, inspect_ppi_oct2026_first_print_lab,
)

SCHEMA = "ATLASQUANT_BLS_CPI_PPI_SEP_OCT2026_FOUR_EVENT_CENSUS_LAB_V1"
ROOTS = (
    ("2026-09", "CPI", "US_CPI_SEP2026",
     datetime.fromisoformat(SEP_SPECS["CPI"]["release_utc"]),
     SEP_SPECS["CPI"]["url"], "0.6"),
    ("2026-09", "PPI", "US_PPI_SEP2026",
     datetime.fromisoformat(SEP_SPECS["PPI"]["release_utc"]),
     SEP_SPECS["PPI"]["url"], "1.3"),
    ("2026-10", "CPI", "US_CPI_OCT2026", OCT_CPI_RELEASE,
     OCT_CPI_URL, "0.4"),
    ("2026-10", "PPI", "US_PPI_OCT2026", OCT_PPI_RELEASE,
     OCT_PPI_URL, "0.3"),
)


@dataclass(frozen=True)
class OriginalBlsReleaseClaim:
    reference_period: str
    indicator: str
    source_url: str
    html_original_bytes: bytes
    http_status: int
    content_type: str
    capture_started_at_utc: datetime
    capture_finished_at_utc: datetime
    original_sha256_claim: str


def _utc(value: Any) -> datetime | None:
    if type(value) is not datetime or value.tzinfo is None:
        return None
    try:
        return value.astimezone(timezone.utc) if value.utcoffset() is not None else None
    except (TypeError, ValueError, OverflowError):
        return None


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLS_FOUR_EVENT_CENSUS_BLOCKED_NO_GO",
        "reason": reason, "frozen_documentary_release_denominator": 4,
        "events": [
            {
                "root_id": root, "period": period, "indicator": kind,
                "scheduled_release_utc": time.isoformat(),
                "doc_status": "MISSING_OR_NOT_YET_CAPTURED",
                "actual_headline_sa_mom_pct_documentary": None,
                "original_sha256": None,
                "local_capture_utc_claim": None,
                "historical_pre_event_consensus_verified": False,
                "precommitted_directional_forecast_verified": False,
            }
            for period, kind, root, time, _, _ in ROOTS
        ],
        "documentary_originals_reconciled_at_cutoff": 0,
        "documentary_originals_not_yet_visible_or_missing": 4,
        "economic_event_roots_in_universe": 4,
        "historical_consensus_events_independently_authenticated": 0,
        "independent_precommitted_forex_predictions_verified": 0,
        "sample_size_for_validated_oos_scoring": 0,
        "out_of_sample_directional_accuracy": None,
        "calibrated_probability": None, "forex_bias": None,
        "source_first_seen_independently_authenticated": False,
        "broker_bid_ask_independently_authenticated": False,
        "cross_metric_double_counting_prevented": True,
        "missing_economic_events_cannot_be_dropped": True,
        "trade_authorized": False, "publishable": False,
        "operational_bias": "AGUARDAR",
        "fx28_672_campaign_slots_modified": False,
        "http_requests": 0, "mt5_calls": 0, "file_writes": 0,
    }


def inspect_four_bls_original_documentary_events_lab(
    *, source_claims: Any, research_cutoff_utc: Any,
) -> dict[str, Any]:
    now = _utc(research_cutoff_utc)
    out = _blocked("INVALID_DOCUMENTARY_ROSTER_OR_RESEARCH_CUTOFF")
    if (now is None or type(source_claims) not in (tuple, list)
            or len(source_claims) > 4):
        return out
    docs = {}
    for source in source_claims:
        if type(source) is not OriginalBlsReleaseClaim:
            return out
        key = (source.reference_period, source.indicator)
        if key in docs or key not in {(p, k) for p, k, *_ in ROOTS}:
            out["reason"] = "DUPLICATE_OR_UNKNOWN_ORIGINAL_RELEASE"
            return out
        docs[key] = source
    rows = out["events"]
    checks = 0
    digests = set()
    for i, (period, kind, root, release, expected_url, expected_value) in enumerate(ROOTS):
        src = docs.get((period, kind))
        if src is None:
            continue
        first = _utc(src.capture_started_at_utc)
        finish = _utc(src.capture_finished_at_utc)
        if (first is None or finish is None or first > finish
                or first < release or (finish-first).total_seconds() > 180):
            out["reason"] = "IMPOSSIBLE_CAPTURE_TIME_OR_PRE_RELEASE_SOURCE"
            return out
        # Critical: do not parse a future raw HTML body or expose its headline.
        if finish > now:
            continue
        if (type(src.http_status) is not int or src.http_status != 200
                or src.source_url != expected_url
                or type(src.content_type) is not str
                or src.content_type.split(";")[0].strip().lower() != "text/html"
                or type(src.html_original_bytes) is not bytes
                or type(src.original_sha256_claim) is not str
                or sha256(src.html_original_bytes).hexdigest() != src.original_sha256_claim
                or src.original_sha256_claim in digests):
            out["reason"] = "SOURCE_URL_HTTP_SHA_OR_REUSED_ORIGINAL_INVALID"
            return out
        if period == "2026-09":
            parsed = inspect_sep2026_bls_release_body_lab(
                kind=kind, raw_html=src.html_original_bytes)
            value = parsed.get("sa_mom_pct_body_claim") if parsed else None
        elif kind == "CPI":
            receipt = ClaimedBLSHtmlReceipt(
                expected_url, 200, src.content_type, finish, src.original_sha256_claim)
            parsed = inspect_bls_oct2026_release_text_lab(
                raw_html=src.html_original_bytes,receipt=receipt,as_of_utc=now)
            value = (parsed.get("headline_oct2026_sa_mom_pct_body_claim")
                     if parsed.get("state") == "LAB_BLS_OCT2026_CPI_RELEASE_HTML_LOCAL_CLAIM_NO_TRADE"
                     else None)
        else:
            receipt = ClaimedPostReleaseHTTP(
                expected_url,200,src.content_type,first,finish,src.original_sha256_claim)
            parsed = inspect_ppi_oct2026_first_print_lab(
                raw_html=src.html_original_bytes,receipt=receipt,as_of_utc=now)
            value = (parsed.get("headline_final_demand_sa_mom_pct_body_claim")
                     if parsed.get("state") == "LAB_PPI_OCT2026_BLS_TABLE1_BODY_VALUES_UNATTESTED"
                     else None)
        if value != expected_value:
            out["reason"] = "BLS_RELEASE_ID_OR_HEADLINE_NOT_SEMANTICALLY_RECONCILED"
            return out
        rows[i] = {
            **rows[i],
            "doc_status": "ORIGINAL_HTML_LOCALLY_SHA_AND_METRIC_RECONCILED",
            "actual_headline_sa_mom_pct_documentary": value,
            "original_sha256": src.original_sha256_claim,
            "local_capture_utc_claim": finish.isoformat(),
        }
        digests.add(src.original_sha256_claim)
        checks += 1
    out.update({
        "state": "LAB_BLS_FOUR_EVENT_DOCUMENTARY_CENSUS_NO_GO",
        "reason": "FOUR_ROOTS_ORIGINAL_SOURCE_CUSTODY_LOCAL_ONLY_NOT_PREDICTIONS",
        "documentary_originals_reconciled_at_cutoff": checks,
        "documentary_originals_not_yet_visible_or_missing": 4-checks,
    })
    return out


__all__ = ("SCHEMA","ROOTS","OriginalBlsReleaseClaim",
           "inspect_four_bls_original_documentary_events_lab")
