"""Oct-2026 US NFP pre/post documentary case: real arithmetic, NO FX bias.

Reuters' dated pre-release economists' survey is distinct from ADP private
payrolls, BLS JOLTS September, and the official BLS NFP October release.
The fixed casebook is manually transcribed after all events; this audit
cannot certify that these exact pages were captured before 2026-11-06 13:30Z.
No paid feed, Reuters content redistribution, automatic HTTP or trading.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
from typing import Any

from atlasquant_fx_universe import OFFICIAL_PAIRS, split_pair

SCHEMA = "ATLASQUANT_TRADER_US_NFP_OCT2026_PREPOST_DOCUMENTARY_PIT_LAB_V1"
KIND = "MANUAL_POST_EVENT_RESEARCH_NO_HISTORICAL_WITNESS"
MAX_BYTES = 8000
TARGET = "BLS_OCT2026_NFP"
RECORDS = [
    {
        "record_id": "BLS_SEP2026_JOLTS_RELEASE",
        "document_role": "PRIOR_MONTH_JOB_OPENINGS_NOT_NFP_FORECAST",
        "reference_period": "2026-09",
        "public_not_before_utc": "2026-11-03T15:00:00Z",
        "source_url": "https://www.bls.gov/news.release/archives/jolts_11032026.htm",
        "reported_values": {"job_openings_rounded_millions": "7.5"},
    },
    {
        "record_id": "ADP_OCT2026_PRIVATE_PAYROLL_RELEASE",
        "document_role": "INDEPENDENT_PRIVATE_PAYROLL_NOT_NFP_FORECAST",
        "reference_period": "2026-10",
        "public_not_before_utc": "2026-11-04T13:15:00Z",
        "source_url": "https://www.prnewswire.com/news-releases/adp-national-employment-report-private-sector-employment-increased-by-86-000-jobs-in-october-302929216.html",
        "reported_values": {"private_payroll_change_persons": "86000"},
    },
    {
        "record_id": "REUTERS_NFP_SURVEY_STATED_NOV4",
        "document_role": "REUTERS_ECONOMIST_SURVEY_PRE_NFP_RELEASE",
        "reference_period": "2026-10",
        # Reuters page displays 13:27 UTC; LAB rounds the earliest admissible
        # time UP to 14:00 UTC. This is not an independent historical witness.
        "public_not_before_utc": "2026-11-04T14:00:00Z",
        "source_url": "https://www.reuters.com/business/us-private-payrolls-rise-october-adp-says-2026-11-04/",
        "reported_values": {
            "nonfarm_payroll_forecast_persons_sa": "65000",
            "unemployment_forecast_percent_sa": "4.2",
        },
    },
    {
        "record_id": TARGET,
        "document_role": "BLS_ACTUAL_NONFARM_PAYROLL_RELEASE",
        "reference_period": "2026-10",
        "public_not_before_utc": "2026-11-06T13:30:00Z",
        "source_url": "https://www.bls.gov/news.release/archives/empsit_11062026.htm",
        "reported_values": {
            "nonfarm_payroll_actual_persons_sa": "165000",
            "unemployment_actual_percent_sa": "4.1",
        },
    },
]
EXPECTED = {
    "schema": SCHEMA, "data_kind": KIND,
    "retrospective_research_date": "2026-11-06",
    "target_release_id": TARGET,
    "records": RECORDS,
    "original_source_bytes_archived": False,
    "pre_event_page_capture_independently_witnessed": False,
    "source_content_product_license_verified": False,
}


def _unique(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, val in items:
        if key in result:
            raise ValueError("DUPLICATE_JSON_FIELD")
        result[key] = val
    return result


def _asof(t: Any) -> datetime | None:
    if not isinstance(t, datetime) or t.tzinfo is None or t.utcoffset() is None:
        return None
    return t.astimezone(timezone.utc)


def _clock(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "casebook_sha256": None,
        "documentary_records_not_before_asof": [],
        "future_documentary_records_excluded": [],
        "pre_release_independent_leads_available_as_documents": [],
        "reuters_pre_release_survey_document_present": False,
        "bls_nfp_result_after_release_document_present": False,
        "documentary_nfp_forecast_persons": None,
        "documentary_nfp_actual_persons": None,
        "nfp_result_minus_reuters_survey_persons_unverified": None,
        "unemployment_result_minus_reuters_survey_pp_unverified": None,
        "usd_canonical_pair_count": 0,
        "adp_and_nfp_populations_identical": False,
        "jolts_and_nfp_periods_identical": False,
        "pre_release_survey_page_historically_witnessed": False,
        "bls_release_original_bytes_authenticated": False,
        "consensus_data_product_license_verified": False,
        "market_price_reaction_independently_verified": False,
        "surprise_transmission_to_usd_direction_verified": False,
        "forward_predictive_accuracy_verified": False,
        "validated_prediction_count": 0, "validated_accuracy": None,
        "market_surprise_independently_verified": None,
        "policy_repricing_impulse": None,
        "usd_strength": None, "fx_bias": None,
        "operational_bias": "AGUARDAR", "trade_authorized": False,
        "can_feed_live_radar": False, "publishable": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "http_requests": 0, "new_cost_brl": 0,
    }


def inspect_us_nfp_oct2026_prepost_lab(
    casebook_raw: Any, *, as_of_utc: Any,
) -> dict[str, Any]:
    """Count pre-release context vs post-release results; no inferred trade.

    `as_of_utc` is a SIMULATED research clock, not a historical screenshot or
    trusted HTTP receipt; earlier timestamps are possible, not proven.
    """
    out = _blocked("INVALID_CASEBOOK_OR_CLOCK")
    now = _asof(as_of_utc)
    if (now is None or not isinstance(casebook_raw, bytes)
            or not 500 <= len(casebook_raw) <= MAX_BYTES):
        return out
    try:
        obj = json.loads(
            casebook_raw.decode("utf-8", "strict"), object_pairs_hook=_unique,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("NONFINITE")),
        )
    except (ValueError, TypeError, UnicodeDecodeError, RecursionError):
        out["reason"] = "INVALID_JSON_DUPLICATE_KEYS_OR_NONFINITE"
        return out
    if obj != EXPECTED:
        out["reason"] = "FIXED_DOCUMENTARY_RECORDS_CHANGED_OR_FALSE_PROVENANCE"
        return out
    if len(OFFICIAL_PAIRS) != 28:
        out["reason"] = "G8_UNIVERSE_INVALID"
        return out
    usd_count = sum("USD" in split_pair(p) for p in OFFICIAL_PAIRS)
    if usd_count != 7:
        out["reason"] = "USD_CROSS_COVERAGE_INVALID"
        return out
    visible = [r["record_id"] for r in RECORDS
               if now >= _clock(r["public_not_before_utc"])]
    invisible = [r["record_id"] for r in RECORDS
                 if r["record_id"] not in visible]
    survey = RECORDS[2]
    bls = RECORDS[3]
    survey_seen, actual_seen = survey["record_id"] in visible, TARGET in visible
    survey_values = survey["reported_values"]
    actual_values = bls["reported_values"]
    # Arithmetic only: do NOT name it a proven market surprise or predictor.
    nfp_gap = (str(int(actual_values["nonfarm_payroll_actual_persons_sa"])
                   - int(survey_values["nonfarm_payroll_forecast_persons_sa"]))
               if survey_seen and actual_seen else None)
    unemployment_gap = (
        str(Decimal(actual_values["unemployment_actual_percent_sa"])
            - Decimal(survey_values["unemployment_forecast_percent_sa"]))
        if survey_seen and actual_seen else None)
    out.update({
        "state": ("LAB_POST_RELEASE_SURVEY_GAP_ARITHMETIC_UNATTESTED" if actual_seen
                  else "LAB_PRE_RELEASE_CONTEXT_ONLY_NO_OUTCOME"),
        "reason": "RETROSPECTIVE_DOCUMENTS_NO_HISTORICAL_WITNESS_OR_LICENSE",
        "casebook_sha256": sha256(casebook_raw).hexdigest(),
        "documentary_records_not_before_asof": visible,
        "future_documentary_records_excluded": invisible,
        "pre_release_independent_leads_available_as_documents": [
            r["record_id"] for r in RECORDS[:2] if r["record_id"] in visible],
        "reuters_pre_release_survey_document_present": survey_seen,
        "bls_nfp_result_after_release_document_present": actual_seen,
        "documentary_nfp_forecast_persons": (
            survey_values["nonfarm_payroll_forecast_persons_sa"] if survey_seen else None),
        "documentary_nfp_actual_persons": (
            actual_values["nonfarm_payroll_actual_persons_sa"] if actual_seen else None),
        "nfp_result_minus_reuters_survey_persons_unverified": nfp_gap,
        "unemployment_result_minus_reuters_survey_pp_unverified": unemployment_gap,
        "usd_canonical_pair_count": usd_count,
    })
    return out


__all__ = ["SCHEMA", "KIND", "RECORDS", "EXPECTED",
           "inspect_us_nfp_oct2026_prepost_lab"]
