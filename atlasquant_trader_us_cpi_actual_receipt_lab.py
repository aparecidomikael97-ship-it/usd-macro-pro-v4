"""Offline release fence for the *future* October-2026 US CPI actual.

Accepts only caller-provided bytes, clocks and an optional numeric claim. A
matching hash is local integrity, NOT evidence the BLS produced those bytes
or that the claimed number was extracted from them. No HTTP, MT5 or signals.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import re
from typing import Any

from atlasquant_trader_us_cpi_source_custody_lab import (
    MAX_BODY_BYTES, METRIC, RELEASE, RESEARCH_VISIBLE_AFTER,
    inspect_us_cpi_pre_event_bundle_lab,
)

SCHEMA = "ATLASQUANT_TRADER_US_OCT2026_CPI_ACTUAL_RELEASE_FENCE_LAB_V1"
EXPECTED_MONTH = "2026-10"
EXPECTED_BLS_URLS = frozenset((
    "https://www.bls.gov/news.release/cpi.htm",
    # Expected archive path; existence/publication must be checked later.
    "https://www.bls.gov/news.release/archives/cpi_11102026.htm",
))
MAX_CAPTURE_SPAN = timedelta(minutes=2)
_HEX = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class ClaimedActualDocument:
    source_url: str
    response_status: int
    content_type: str
    body: bytes
    body_sha256: str
    started_at: datetime
    finished_at: datetime
    claimed_first_published_at: datetime
    reference_month: str
    metric: str
    extracted_actual_mom_percent_claim: str | None = None


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _parse_claim(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 24 or not value:
        return None
    try:
        numeric = Decimal(value)
    except InvalidOperation:
        return None
    if not numeric.is_finite() or not -100 <= numeric <= 100:
        return None
    return str(numeric)


def _result(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_CPI_ACTUAL_BLOCKED", "reason": reason,
        "event_month": EXPECTED_MONTH,
        "scheduled_release_utc": RELEASE.isoformat(),
        "pre_event_sources_self_consistent_only": False,
        "post_release_body_self_consistent_only": False,
        "actual_documentary_claim_unattested": None,
        "actual_body_sha256": None,
        "official_actual_verified": None,
        "actual_minus_pre_release_consensus": None,
        "pre_event_forecast_score": None,
        "market_reaction_probability": None,
        "fx_bias": None, "index_bias": None,
        "operational_bias": "AGUARDAR",
        "source_publisher_independently_attested": False,
        "first_publication_clock_independently_attested": False,
        "value_extracted_from_original_independently_verified": False,
        "prerelease_consensus_methodology_verified": False,
        "trade_authorized": False, "publishable": False,
        "live_alert_allowed": False, "worker_enabled": False,
        "scheduler_enabled": False, "http_requests": 0,
        "file_writes": 0, "new_cost_brl": 0, "research_only": True,
    }


def inspect_us_oct_cpi_actual_receipt_lab(
    *, candidate: Any, previous_receipt: Any, consensus_receipt: Any,
    forecast_cutoff_utc: Any, as_of_utc: Any,
) -> dict[str, Any]:
    """Report whether an alleged post-release artifact is chronology-consistent.

    The historic forecast cutoff must remain pre-release even when this
    function is inspected after release. No source content is independently
    authenticated and no economic number is promoted to an official actual.
    """
    now, cutoff = _utc(as_of_utc), _utc(forecast_cutoff_utc)
    if now is None or cutoff is None:
        return _result("INVALID_CLOCK")
    if now < RESEARCH_VISIBLE_AFTER:
        return _result("RESEARCH_NOT_VISIBLE_BEFORE_NOV9")
    if not RESEARCH_VISIBLE_AFTER <= cutoff <= now or cutoff >= RELEASE:
        return _result("FORECAST_CUTOFF_NOT_A_VALID_PRERELEASE_INSTANT")

    out = _result("WAIT_RELEASE_OR_SOURCE_PROOF")
    prior = inspect_us_cpi_pre_event_bundle_lab(
        previous_receipt, consensus_receipt,
        as_of_utc=now, forecast_cutoff_utc=cutoff,
    )
    out["pre_event_sources_self_consistent_only"] = (
        prior["state"] == "LAB_TWO_SOURCE_DOCUMENTARY_CANDIDATE_UNATTESTED"
    )
    if now < RELEASE:
        if candidate is not None:
            out["reason"] = "ACTUAL_DOCUMENT_MUST_NOT_EXIST_BEFORE_SCHEDULED_RELEASE"
        else:
            out.update({"state": "LAB_WAIT_SCHEDULED_CPI_RELEASE",
                        "reason": "OFFICIAL_OCTOBER_ACTUAL_NOT_RELEASED_YET"})
        return out
    if candidate is None:
        out.update({"state": "LAB_WAIT_OFFICIAL_CPI_ACTUAL_DOCUMENT",
                    "reason": "RELEASE_PASSED_BUT_NO_CAPTURED_ACTUAL"})
        return out
    if not isinstance(candidate, ClaimedActualDocument):
        return _result("INVALID_POST_RELEASE_CANDIDATE")
    started = _utc(candidate.started_at)
    finished = _utc(candidate.finished_at)
    published = _utc(candidate.claimed_first_published_at)
    if (not isinstance(candidate.source_url, str)
            or candidate.source_url not in EXPECTED_BLS_URLS
            or type(candidate.response_status) is not int or candidate.response_status != 200
            or candidate.content_type != "text/html"
            or candidate.reference_month != EXPECTED_MONTH or candidate.metric != METRIC
            or started is None or finished is None or published is None
            or not RELEASE <= published <= started <= finished <= now
            or finished - started > MAX_CAPTURE_SPAN
            or not isinstance(candidate.body, bytes)
            or not 100 <= len(candidate.body) <= MAX_BODY_BYTES
            or b"october 2026" not in candidate.body.lower()
            or b"consumer price index" not in candidate.body.lower()
            or not isinstance(candidate.body_sha256, str)
            or _HEX.fullmatch(candidate.body_sha256) is None
            or sha256(candidate.body).hexdigest() != candidate.body_sha256
            or (candidate.extracted_actual_mom_percent_claim is not None
                and _parse_claim(candidate.extracted_actual_mom_percent_claim) is None)):
        out["reason"] = "POST_RELEASE_SOURCE_CONTENT_OR_CLOCK_UNATTESTED_OR_INVALID"
        return out

    out.update({
        "state": "LAB_POST_RELEASE_RAW_CPI_CANDIDATE_UNATTESTED",
        "reason": "LOCAL_HASH_AND_CLAIMED_PIT_ONLY_NO_OFFICIAL_VALUE_WITNESS",
        "post_release_body_self_consistent_only": True,
        "actual_body_sha256": candidate.body_sha256,
        "actual_documentary_claim_unattested": _parse_claim(
            candidate.extracted_actual_mom_percent_claim),
    })
    return out


__all__ = ["SCHEMA", "ClaimedActualDocument", "inspect_us_oct_cpi_actual_receipt_lab"]
