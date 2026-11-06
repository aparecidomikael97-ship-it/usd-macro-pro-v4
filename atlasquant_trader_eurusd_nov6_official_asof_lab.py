"""EUR/USD four official retrospective pages: document-level as-of only.

BLS Sep CPI, Fed Oct FOMC, ECB Oct decision and Eurostat Oct FLASH are
distinct observations. A source date or official web page is NOT original
PIT capture testimony, a pre-event consensus, comparable inflation series,
rate spread, currency impulse, price prediction or historical hit rate.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any

from atlasquant_fx_universe import OFFICIAL_PAIRS

SCHEMA = "ATLASQUANT_TRADER_EURUSD_NOV6_FOUR_OFFICIAL_DOCUMENTS_ASOF_LAB_V1"
KIND = "RETROSPECTIVE_OFFICIAL_PAGE_REFERENCES_NOT_HISTORICALLY_WITNESSED"
FIXED_CASEBOOK_SHA256 = "bd43145380f6bb4a2db1a227f816f2a416375c8b7f38ff07c302d3dadc30a017"
RECORD_IDS = (
    "USD_BLS_CPI_SEP2026", "USD_FED_OCT2026_FOMC",
    "EUR_ECB_OCT2026_POLICY_DECISION", "EUR_EUROSTAT_OCT2026_HICP_FLASH",
)
FAMILY_CURRENCY = frozenset((
    ("USD", "INFLATION"), ("USD", "POLICY"),
    ("EUR", "INFLATION"), ("EUR", "POLICY"),
))
MAX_BYTES = 6_000


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "fixed_casebook_sha256": FIXED_CASEBOOK_SHA256,
        "accepted_casebook_sha256": None,
        "visible_document_count": 0,
        "visible_documents_as_retrospective_references": [],
        "not_yet_admissible_record_ids": list(RECORD_IDS),
        "two_sided_inflation_and_policy_documentary_coverage": False,
        "inflation_observation_periods_match": False,
        "inflation_statistical_methods_comparable": False,
        "policy_rate_instruments_directly_comparable": False,
        "future_oct2026_us_cpi_number_in_casebook": False,
        "us_oct2026_cpi_schedule_utc": "2026-11-10T13:30:00Z",
        "source_original_bytes_independently_archived": False,
        "independent_historical_page_timestamp_witnessed": False,
        "pre_event_consensus_available_and_attested": False,
        "historical_macroeconomic_vintage_attested": False,
        "macro_surprise_quantified": False,
        "relative_usd_eur_strength_verified": False,
        "d1_w1_directional_accuracy_verified": False,
        "validated_prediction_count": 0, "validated_accuracy": None,
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "can_feed_live_radar": False, "trade_authorized": False,
        "publishable": False, "worker_enabled": False,
        "scheduler_enabled": False, "http_requests": 0, "new_cost_brl": 0,
    }


def _utc(dt: Any) -> datetime | None:
    if not isinstance(dt, datetime) or dt.tzinfo is None or dt.utcoffset() is None:
        return None
    return dt.astimezone(timezone.utc)


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for k, v in pairs:
        if k in obj:
            raise ValueError("duplicate key")
        obj[k] = v
    return obj


def inspect_eurusd_nov6_official_asof_lab(
    raw: Any, *, as_of_utc: Any,
) -> dict[str, Any]:
    """Expose only documents past their conservative admissibility gates.

    As-of is a simulated study clock. The fixed pages were consulted after
    publication and have no independently archived original source bytes.
    """
    out = _blocked("INVALID_CASEBOOK_OR_RESEARCH_CLOCK")
    asof = _utc(as_of_utc)
    if (asof is None or not isinstance(raw, bytes)
            or not 200 <= len(raw) <= MAX_BYTES
            or "EUR/USD" not in OFFICIAL_PAIRS
            or sha256(raw).hexdigest() != FIXED_CASEBOOK_SHA256):
        return out
    try:
        obj = json.loads(raw.decode("utf-8", "strict"),
                         object_pairs_hook=_unique,
                         parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))
        if (not isinstance(obj, dict) or obj["schema"] != SCHEMA
                or obj["kind"] != KIND or len(obj["records"]) != 4
                or tuple(r["record_id"] for r in obj["records"]) != RECORD_IDS
                or {(r["currency"], r["family"]) for r in obj["records"]}
                   != FAMILY_CURRENCY
                or obj["original_pages_archived_with_server_receipt"] is not False
                or obj["historical_page_vintages_independently_witnessed"] is not False):
            return out
        visible = [r for r in obj["records"]
                   if asof >= datetime.strptime(r["admissibility_gate_utc"],
                                                "%Y-%m-%dT%H:%M:%SZ").replace(
                                                    tzinfo=timezone.utc)]
        withheld = [r["record_id"] for r in obj["records"] if r not in visible]
    except (UnicodeDecodeError, ValueError, TypeError, KeyError, RecursionError):
        return out
    complete = len(visible) == 4
    out.update({
        "state": ("LAB_FOUR_DOCUMENT_REFERENCES_VISIBLE_BUT_PIT_UNATTESTED"
                  if complete else "LAB_PARTIAL_DOCUMENT_CONTEXT_ONLY_NO_FX_BIAS"),
        "reason": "RETROSPECTIVE_PAGES_AND_INCOMPATIBLE_OBSERVATION_PERIODS",
        "accepted_casebook_sha256": sha256(raw).hexdigest(),
        "visible_document_count": len(visible),
        "visible_documents_as_retrospective_references": [
            {"record_id": r["record_id"], "currency": r["currency"],
             "family": r["family"], "reference_period": r["reference_period"],
             "measurement_kind": r["measurement_kind"],
             "gate_basis": r["gate_basis"],
             "source_url": r["source_url"],
             "reported_values_percent_document_claim": r["reported_values_percent"]}
            for r in visible],
        "not_yet_admissible_record_ids": withheld,
        "two_sided_inflation_and_policy_documentary_coverage": complete,
        # USD September CPI-U and EUR October FLASH HICP never describe
        # the same period or methodology, despite being percentage values.
        "inflation_observation_periods_match": False,
        "inflation_statistical_methods_comparable": False,
        # Deposit facility rate != US federal-funds target-range boundaries.
        "policy_rate_instruments_directly_comparable": False,
    })
    return out


__all__ = ["SCHEMA", "KIND", "FIXED_CASEBOOK_SHA256",
           "inspect_eurusd_nov6_official_asof_lab"]
