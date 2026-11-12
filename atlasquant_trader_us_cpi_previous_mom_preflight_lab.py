"""Document BLS prior-month CPI without turning research into an as-of snapshot.

This adapter deliberately refuses to create a PreReleaseSnapshot while the
original BLS bytes and exact pre-event analyst consensus remain unattested.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any


SCHEMA = "ATLASQUANT_US_CPI_PREVIOUS_MOM_PREFLIGHT_LAB_V1"
RECEIPT_SCHEMA = "ATLASQUANT_TRADER_US_CPI_PREVIOUS_MOM_RESEARCH_LAB_V1"
CASEBOOK_SHA256 = "2dcc90bf54497183c415f57abb580bbac0b56edf6e92b303dd80b5e84c1a65e6"
RESEARCH_VISIBLE = datetime(2026, 11, 9, tzinfo=timezone.utc)
RELEASE = datetime(2026, 11, 10, 13, 30, tzinfo=timezone.utc)

EXPECTED_PREVIOUS = {
    "reference_month": "2026-09",
    "source_url": "https://www.bls.gov/news.release/archives/cpi_10142026.htm",
    "bls_embargo_release_utc_from_notice_not_external_witness": "2026-10-14T12:30:00Z",
    "headline_mom_sa_percent": "0.6",
    "headline_yoy_nsa_percent": "3.7",
    "original_sha256": None,
}
EXPECTED_EARLIER = {
    "reference_month": "2026-08",
    "source_url": "https://www.bls.gov/news.release/archives/cpi_09112026.htm",
    "bls_embargo_release_utc_from_notice_not_external_witness": "2026-09-11T12:30:00Z",
    "headline_mom_sa_percent": "0.4",
    "headline_yoy_nsa_percent": "3.4",
    "original_sha256": None,
}
EXPECTED_TARGET = {
    "reference_month": "2026-10",
    "source_calendar_url": "https://www.bls.gov/schedule/2026/11_sched_list.htm",
    "scheduled_first_release_utc": "2026-11-10T13:30:00Z",
    "headline_mom_sa_actual": None,
    "headline_mom_sa_exact_event_consensus_pit_verified": None,
    "headline_yoy_nsa_publishable": False,
    "headline_yoy_unavailable_reason": "BLS_OCT2025_HEADLINE_BASELINE_MISSING",
    "missing_baseline_explainer_url": (
        "https://www.bls.gov/cpi/additional-resources/"
        "2025-federal-government-shutdown-impact-cpi-faq.htm"
    ),
}
EXPECTED_TOP = frozenset({
    "schema", "kind", "research_date", "conservative_visible_after_utc",
    "original_bls_bytes_independently_archived",
    "original_release_capture_time_attested", "previous_report", "earlier_report",
    "next_target", "may_feed_news_previous_context_nowcast", "may_feed_fx_bias",
    "claim_of_historical_prediction_accuracy",
})


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("chave JSON duplicada")
        out[key] = value
    return out


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_BLOCKED",
        "reason": reason,
        "casebook_sha256": None,
        "prior_cpi_mom_sa_percent_documentary": None,
        "earlier_cpi_mom_sa_percent_documentary": None,
        "next_oct2026_cpi_mom_consensus": None,
        "next_oct2026_cpi_mom_actual": None,
        "next_oct2026_cpi_yoy_publishable": None,
        "missing_source_originals": [
            "BLS_SEP2026_CPI_ORIGINAL_BYTES_AND_CAPTURE_TIME",
            "EXACT_OCT2026_CPI_MOM_ANALYST_CONSENSUS_ASOF",
        ],
        "previous_snapshot_for_model": None,
        "nowcast_estimate": None,
        "probabilities": None,
        "pair_bias": None,
        "operational_bias": "AGUARDAR",
        "research_only": True,
        "can_feed_live_radar": False,
        "worker_enabled": False,
        "automatic_execution": False,
        "new_cost_brl": 0,
    }


def inspect_us_cpi_previous_mom_preflight_lab(raw: Any, *, as_of_utc: Any) -> dict[str, Any]:
    """A pinned transcription is research, never self-attested original bytes."""
    out = _blocked("INVALID_CLOCK_OR_RESEARCH_RECEIPT")
    if (not isinstance(as_of_utc, datetime) or as_of_utc.tzinfo is None
            or as_of_utc.utcoffset() is None
            or not isinstance(raw, bytes)
            or not 500 <= len(raw) <= 4000
            or sha256(raw).hexdigest() != CASEBOOK_SHA256):
        return out
    now = as_of_utc.astimezone(timezone.utc)
    if now < RESEARCH_VISIBLE:
        return _blocked("NO_RESEARCH_BACKFILL_BEFORE_NOV9_UTC")
    try:
        case = json.loads(
            raw.decode("utf-8", "strict"),
            object_pairs_hook=_unique,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("não finito")),
        )
        if (not isinstance(case, dict) or case.keys() != EXPECTED_TOP
                or case["schema"] != RECEIPT_SCHEMA
                or case["kind"] != "RETROSPECTIVE_MANUAL_RESEARCH_NOT_ORIGINAL_SOURCE_BYTE_CUSTODY"
                or case["research_date"] != "2026-11-08"
                or case["conservative_visible_after_utc"] != "2026-11-09T00:00:00Z"
                or case["original_bls_bytes_independently_archived"] is not False
                or case["original_release_capture_time_attested"] is not False
                or case["previous_report"] != EXPECTED_PREVIOUS
                or case["earlier_report"] != EXPECTED_EARLIER
                or case["next_target"] != EXPECTED_TARGET
                or case["may_feed_news_previous_context_nowcast"] is not False
                or case["may_feed_fx_bias"] is not False
                or case["claim_of_historical_prediction_accuracy"] is not None):
            return out
    except (UnicodeError, ValueError, TypeError, KeyError, OverflowError, RecursionError):
        return out
    out.update({
        "state": "LAB_DOCUMENTARY_PREVIOUS_AVAILABLE_NOT_PIT_ATTESTED",
        "reason": ("WAIT_OFFICIAL_OCT2026_CPI_MOM_ACTUAL_AND_ORIGINALS"
                   if now >= RELEASE else "WAIT_PIT_PREVIOUS_AND_EVENT_CONSENSUS"),
        "casebook_sha256": CASEBOOK_SHA256,
        "prior_cpi_mom_sa_percent_documentary": 0.6,
        "earlier_cpi_mom_sa_percent_documentary": 0.4,
        "next_oct2026_cpi_yoy_publishable": False,
        "next_release_scheduled_utc": RELEASE.isoformat(),
        "reporting_metric": "CPI_U_HEADLINE_MOM_SEASONALLY_ADJUSTED_PERCENT_CHANGE",
    })
    return out


__all__ = ["SCHEMA", "CASEBOOK_SHA256", "inspect_us_cpi_previous_mom_preflight_lab"]
