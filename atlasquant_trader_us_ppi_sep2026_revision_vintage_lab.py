"""Distinguish the Sep-2026 PPI first print from its Nov-2026 revision.

This is an offline, pure, caller-supplied DOCUMENTARY research gate. A URL,
a clock and a SHA string supplied by a caller never establish first-seen
provenance. This does not fetch source bytes, backtest, signal, or trade.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import re
from typing import Any

SCHEMA = "ATLASQUANT_TRADER_US_PPI_SEP2026_REVISION_VINTAGE_LAB_V1"
INITIAL_RELEASE_UTC = datetime(2026, 10, 15, 12, 30, tzinfo=timezone.utc)
REVISION_RELEASE_UTC = datetime(2026, 11, 13, 13, 30, tzinfo=timezone.utc)
INITIAL_URL = "https://www.bls.gov/news.release/archives/ppi_10152026.htm"
REVISION_URL = "https://www.bls.gov/news.release/archives/ppi_11132026.htm"
SHA = re.compile(r"[0-9a-f]{64}\Z")
PCT = re.compile(r"[+-]?(?:0|[1-9][0-9]?)(?:\.[0-9]{1,3})?\Z")


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _parse_utc(value: Any) -> datetime | None:
    if type(value) is not str:
        return None
    try:
        return _utc(datetime.fromisoformat(value))
    except (ValueError, TypeError, OverflowError):
        return None


def _number(value: Any) -> Decimal | None:
    if type(value) is not str or PCT.fullmatch(value) is None:
        return None
    try:
        n = Decimal(value)
        return n if n.is_finite() and abs(n) <= 20 else None
    except (InvalidOperation, ValueError):
        return None


def _block(reason: str, state: str = "LAB_PPI_VINTAGE_RECONCILIATION_BLOCKED") -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": state, "reason": reason,
        "reference_month": "2026-09",
        "first_print_released_at_utc": INITIAL_RELEASE_UTC.isoformat(),
        "revision_released_at_utc": REVISION_RELEASE_UTC.isoformat(),
        "first_print_headline_sa_mom_pct_claim": None,
        "first_print_core_sa_mom_pct_claim": None,
        "revision_headline_sa_mom_pct_claim": None,
        "revision_core_sa_mom_pct_claim": None,
        "headline_revision_delta_pp": None, "core_revision_delta_pp": None,
        "release_vintages_retained_separately": False,
        "original_issuer_bytes_retained_and_verified": False,
        "first_seen_time_independently_attested": False,
        "document_originality_authenticated": False,
        "revision_eligible_for_prior_date_prediction": False,
        "historical_backtest_eligible": False,
        "directional_bias": None, "calibrated_probability": None,
        "operational_bias": "AGUARDAR", "trade_authorized": False,
        "publishable": False, "live_alert_allowed": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "http_requests": 0, "file_writes": 0, "new_cost_brl": 0,
    }


def _packet(packet: Any, *, expected_url: str,
            release_utc: datetime, as_of: datetime,
            first: bool) -> tuple[dict[str, Any] | None, str]:
    if type(packet) is not dict or set(packet) != {
        "reference_month", "release_at_utc", "capture_at_utc",
        "source_url", "source_sha256_claim",
        "headline_sa_mom_pct", "core_ex_food_energy_sa_mom_pct",
    }:
        return None, "VINTAGE_PACKET_KEYS_MISSING_OR_EXTRA"
    if packet["reference_month"] != "2026-09" or packet["source_url"] != expected_url:
        return None, "VINTAGE_SOURCE_OR_REFERENCE_MONTH_MISMATCH"
    if packet["release_at_utc"] != release_utc.isoformat():
        return None, "VINTAGE_RELEASE_CUTOFF_CHANGED"
    capture = _parse_utc(packet["capture_at_utc"])
    if capture is None or not release_utc <= capture <= as_of:
        return None, "VINTAGE_CAPTURE_CLOCK_INVALID"
    if first and capture >= REVISION_RELEASE_UTC:
        # No claim of a Sep-2026 first print may be reconstructed after the
        # November release and treated as an observed pre-revision vintage.
        return None, "FIRST_PRINT_NOT_CAPTURED_BEFORE_REVISION"
    digest = packet["source_sha256_claim"]
    if type(digest) is not str or SHA.fullmatch(digest) is None:
        return None, "VINTAGE_DOCUMENT_SHA_CLAIM_MALFORMED"
    headline = _number(packet["headline_sa_mom_pct"])
    core = _number(packet["core_ex_food_energy_sa_mom_pct"])
    if headline is None or core is None:
        return None, "VINTAGE_MONTHLY_SA_VALUES_MISSING_OR_INVALID"
    return {"headline": headline, "core": core,
            "capture": capture.isoformat(), "sha": digest}, ""


def inspect_sep2026_ppi_revision_lineage_lab(
    *, september_first_print: Any, november_release_revision: Any,
    as_of_utc: Any,
) -> dict[str, Any]:
    """Compare two distinct publisher-release claims; never overwrite old data."""
    as_of = _utc(as_of_utc)
    if as_of is None:
        return _block("INVALID_AS_OF_CLOCK")
    if as_of < REVISION_RELEASE_UTC:
        return _block("REVISION_NOT_YET_RELEASED", "LAB_WAIT_PPI_NOV2026_REVISION")
    first, reason = _packet(september_first_print,
                            expected_url=INITIAL_URL,
                            release_utc=INITIAL_RELEASE_UTC,
                            as_of=as_of, first=True)
    if reason:
        return _block("FIRST_" + reason)
    revised, reason = _packet(november_release_revision,
                             expected_url=REVISION_URL,
                             release_utc=REVISION_RELEASE_UTC,
                             as_of=as_of, first=False)
    if reason:
        return _block("REVISION_" + reason)
    assert first is not None and revised is not None
    if first["sha"] == revised["sha"]:
        return _block("TWO_SEPARATE_RELEASES_CANNOT_SHARE_DOCUMENT_DIGEST")
    result = _block("LOCAL_TWO_VINTAGE_COMPARISON_NOT_AUTHENTICATION",
                    "LAB_PPI_SEP2026_REVISION_COMPARISON_UNATTESTED")
    result.update({
        "release_vintages_retained_separately": True,
        "first_print_headline_sa_mom_pct_claim": str(first["headline"]),
        "first_print_core_sa_mom_pct_claim": str(first["core"]),
        "revision_headline_sa_mom_pct_claim": str(revised["headline"]),
        "revision_core_sa_mom_pct_claim": str(revised["core"]),
        "headline_revision_delta_pp": str(revised["headline"] - first["headline"]),
        "core_revision_delta_pp": str(revised["core"] - first["core"]),
        "first_print_capture_claim_utc": first["capture"],
        "revision_capture_claim_utc": revised["capture"],
        "first_print_source_sha256_claim": first["sha"],
        "revision_source_sha256_claim": revised["sha"],
    })
    return result


__all__ = ["SCHEMA", "INITIAL_URL", "REVISION_URL", "INITIAL_RELEASE_UTC",
           "REVISION_RELEASE_UTC", "inspect_sep2026_ppi_revision_lineage_lab"]
