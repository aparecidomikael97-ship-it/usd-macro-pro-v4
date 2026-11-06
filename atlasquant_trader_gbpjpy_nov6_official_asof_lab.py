"""GBP/JPY four official retrospective documents with strict as-of gating.

Distinguishes UK CPI from CPIH, Japan NATIONAL CPI from preliminary Tokyo,
BoE Bank Rate from BoJ overnight-call guideline, and dated pages from an
independently witnessed historical vintage. Never produces FX strength/bias.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any

from atlasquant_fx_universe import OFFICIAL_PAIRS

SCHEMA = "ATLASQUANT_TRADER_GBPJPY_NOV6_FOUR_OFFICIAL_DOCUMENTS_ASOF_LAB_V1"
KIND = "RETROSPECTIVE_OFFICIAL_PAGE_REFERENCES_NOT_HISTORICALLY_WITNESSED"
FIXED_CASEBOOK_SHA256 = "9ea8f5a8d363e02aa0402fd1e2a5d39d3781a8e654e9d7528ca66e55d657f2bd"
RECORD_IDS = (
    "GBP_ONS_CPI_SEP2026", "JPY_STAT_CPI_SEP2026",
    "JPY_BOJ_OCT2026_MONETARY_DECISION", "GBP_BOE_NOV2026_BANK_RATE",
)
FAMILY_CURRENCY = frozenset((
    ("GBP", "INFLATION"), ("GBP", "POLICY"),
    ("JPY", "INFLATION"), ("JPY", "POLICY"),
))
MAX_BYTES = 6500


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "fixed_casebook_sha256": FIXED_CASEBOOK_SHA256,
        "accepted_casebook_sha256": None, "visible_document_count": 0,
        "visible_documents_as_retrospective_references": [],
        "not_yet_admissible_record_ids": list(RECORD_IDS),
        "two_sided_inflation_and_policy_documentary_coverage": False,
        "inflation_observation_periods_match": False,
        "inflation_statistical_methods_comparable": False,
        "policy_rate_instruments_directly_comparable": False,
        "future_uk_oct2026_cpi_number_in_casebook": False,
        "future_boj_summary_of_opinions_in_casebook": False,
        "source_original_bytes_independently_archived": False,
        "independent_historical_page_timestamp_witnessed": False,
        "pre_event_consensus_available_and_attested": False,
        "historical_macroeconomic_vintage_attested": False,
        "macro_surprise_quantified": False,
        "relative_gbp_jpy_strength_verified": False,
        "d1_w1_directional_accuracy_verified": False,
        "validated_prediction_count": 0, "validated_accuracy": None,
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "can_feed_live_radar": False, "trade_authorized": False,
        "publishable": False, "worker_enabled": False,
        "scheduler_enabled": False, "http_requests": 0, "new_cost_brl": 0,
    }


def _clock(dt: Any) -> datetime | None:
    if not isinstance(dt, datetime) or dt.tzinfo is None or dt.utcoffset() is None:
        return None
    return dt.astimezone(timezone.utc)


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for k, v in pairs:
        if k in result:
            raise ValueError("duplicate key")
        result[k] = v
    return result


def inspect_gbpjpy_nov6_official_asof_lab(raw: Any, *, as_of_utc: Any) -> dict[str, Any]:
    """Expose only four source-page references after their documented floors."""
    out = _blocked("INVALID_CASEBOOK_OR_RESEARCH_CLOCK")
    now = _clock(as_of_utc)
    if (now is None or not isinstance(raw, bytes)
            or not 200 <= len(raw) <= MAX_BYTES
            or "GBP/JPY" not in OFFICIAL_PAIRS
            or sha256(raw).hexdigest() != FIXED_CASEBOOK_SHA256):
        return out
    try:
        case = json.loads(raw.decode("utf-8", "strict"),
                          object_pairs_hook=_unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))
        if (not isinstance(case, dict) or case["schema"] != SCHEMA
                or case["kind"] != KIND or len(case["records"]) != 4
                or tuple(r["record_id"] for r in case["records"]) != RECORD_IDS
                or {(r["currency"], r["family"]) for r in case["records"]}
                   != FAMILY_CURRENCY
                or case["original_pages_archived_with_server_receipt"] is not False
                or case["historical_page_vintages_independently_witnessed"] is not False):
            return out
        visible = [r for r in case["records"]
                   if now >= datetime.strptime(r["admissibility_gate_utc"],
                                               "%Y-%m-%dT%H:%M:%SZ").replace(
                                                   tzinfo=timezone.utc)]
        invisible = [r["record_id"] for r in case["records"] if r not in visible]
    except (UnicodeDecodeError, ValueError, TypeError, KeyError, RecursionError):
        return out
    complete = len(visible) == 4
    periods = [r["reference_period"] for r in visible if r["family"] == "INFLATION"]
    out.update({
        "state": ("LAB_FOUR_DOCUMENT_REFERENCES_VISIBLE_BUT_PIT_UNATTESTED"
                  if complete else "LAB_PARTIAL_DOCUMENT_CONTEXT_ONLY_NO_FX_BIAS"),
        "reason": "RETROSPECTIVE_PAGES_ARE_NOT_INDEPENDENT_PIT_WITNESSES",
        "accepted_casebook_sha256": sha256(raw).hexdigest(),
        "visible_document_count": len(visible),
        "visible_documents_as_retrospective_references": [
            {"record_id": r["record_id"], "currency": r["currency"],
             "family": r["family"], "reference_period": r["reference_period"],
             "measurement_kind": r["measurement_kind"],
             "gate_basis": r["gate_basis"], "source_url": r["source_url"],
             "reported_values_percent_document_claim": r["reported_values_percent"]}
            for r in visible],
        "not_yet_admissible_record_ids": invisible,
        "two_sided_inflation_and_policy_documentary_coverage": complete,
        "inflation_observation_periods_match": len(periods) == 2 and periods[0] == periods[1],
        # Same month still does not authenticate or normalize methodology.
        "inflation_statistical_methods_comparable": False,
        "policy_rate_instruments_directly_comparable": False,
    })
    return out


__all__ = ["SCHEMA", "FIXED_CASEBOOK_SHA256",
           "inspect_gbpjpy_nov6_official_asof_lab"]
