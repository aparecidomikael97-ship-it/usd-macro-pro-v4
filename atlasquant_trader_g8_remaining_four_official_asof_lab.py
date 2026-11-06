"""Read-only, offline documentary case for CHF, AUD, CAD and NZD.

All values are claims on retrospectively viewed OFFICIAL PAGES. The SHA pins
the researcher-authored casebook, not original HTTP bytes nor historical PIT
availability. The result is NEVER a currency ranking or trading decision.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any

SCHEMA = "ATLASQUANT_TRADER_G8_REMAINING_FOUR_CURRENCIES_OFFICIAL_ASOF_LAB_V1"
KIND = "RETROSPECTIVE_OFFICIAL_PAGE_REFERENCES_NOT_HISTORICALLY_WITNESSED"
FIXED_CASEBOOK_SHA256 = "e454778f047f1103db7c2316cd2a4430882ee19f7d3da72369a19fdb49bb94d3"
MAX_BYTES = 14000
RECORD_IDS = (
    "CHF_FSO_CPI_OCT2026", "CHF_SNB_SEP2026_POLICY",
    "AUD_ABS_CPI_SEP2026", "AUD_RBA_NOV2026_CASH_RATE",
    "CAD_STATCAN_CPI_SEP2026", "CAD_BOC_OCT2026_OVERNIGHT_TARGET",
    "NZD_STATSNZ_CPI_SEP2026_QUARTER", "NZD_RBNZ_OCT2026_OCR",
)
CURRENCY_FAMILIES = frozenset(
    (currency, family)
    for currency in ("CHF", "AUD", "CAD", "NZD")
    for family in ("INFLATION", "POLICY")
)


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "fixed_casebook_sha256": FIXED_CASEBOOK_SHA256,
        "accepted_casebook_sha256": None,
        "visible_document_count": 0,
        "visible_documents_as_retrospective_references": [],
        "not_yet_admissible_record_ids": list(RECORD_IDS),
        "four_currency_two_family_documentary_coverage": False,
        "mixed_monthly_and_quarterly_inflation_periodicity": True,
        "inflation_methods_harmonized": False,
        "policy_instruments_directly_comparable": False,
        "future_abs_oct2026_cpi_value_in_casebook": False,
        "future_rbnz_dec2026_ocr_value_in_casebook": False,
        "official_original_http_bytes_archived": False,
        "independent_historical_publication_time_witnessed": False,
        "historical_macroeconomic_vintage_attested": False,
        "pre_event_consensus_attested": False,
        "macro_surprise_quantified": False,
        "validated_prediction_count": 0, "validated_accuracy": None,
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "can_feed_live_radar": False, "trade_authorized": False,
        "publishable": False, "worker_enabled": False,
        "scheduler_enabled": False, "http_requests": 0, "new_cost_brl": 0,
    }


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for k, v in pairs:
        if k in result:
            raise ValueError("duplicate JSON key")
        result[k] = v
    return result


def inspect_g8_remaining_four_official_asof_lab(
    raw: Any, *, as_of_utc: Any,
) -> dict[str, Any]:
    """Gate eight fixed references against explicit UTC floors; no network."""
    out = _blocked("INVALID_CASEBOOK_OR_RESEARCH_CLOCK")
    if (not isinstance(as_of_utc, datetime) or as_of_utc.tzinfo is None
            or as_of_utc.utcoffset() is None or not isinstance(raw, bytes)
            or not 200 <= len(raw) <= MAX_BYTES
            or sha256(raw).hexdigest() != FIXED_CASEBOOK_SHA256):
        return out
    now = as_of_utc.astimezone(timezone.utc)
    try:
        case = json.loads(
            raw.decode("utf-8", "strict"), object_pairs_hook=_unique_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")),
        )
        records = case["records"]
        future = case["future_scheduled_events_not_released_in_casebook"]
        if (case["schema"] != SCHEMA or case["kind"] != KIND
                or not isinstance(records, list) or len(records) != 8
                or tuple(r["record_id"] for r in records) != RECORD_IDS
                or {(r["currency"], r["family"]) for r in records}
                   != CURRENCY_FAMILIES
                or case["original_pages_archived_with_server_receipt"] is not False
                or case["historical_page_vintages_independently_witnessed"] is not False
                or case["commercial_redistribution_rights_verified"] is not False
                or len(future) != 2
                or {x["event_id"] for x in future} != {
                    "AUD_ABS_CPI_OCT2026_FUTURE", "NZD_RBNZ_DEC2026_OCR_FUTURE"}
                or any(x["released_value_available_in_casebook"] is not False
                       for x in future)):
            return out
        visible = [r for r in records if now >= datetime.strptime(
            r["admissibility_gate_utc"], "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=timezone.utc)]
        invisible = [r["record_id"] for r in records if r not in visible]
    except (UnicodeDecodeError, ValueError, KeyError, TypeError, RecursionError,
            AttributeError):
        return out

    complete = len(visible) == 8
    out.update({
        "state": ("LAB_EIGHT_DOCUMENT_REFERENCES_VISIBLE_BUT_PIT_UNATTESTED"
                  if complete else "LAB_PARTIAL_DOCUMENT_CONTEXT_ONLY_NO_FX_BIAS"),
        "reason": "RETROSPECTIVE_OFFICIAL_PAGES_NOT_INDEPENDENT_HISTORICAL_PIT_EVIDENCE",
        "accepted_casebook_sha256": sha256(raw).hexdigest(),
        "visible_document_count": len(visible),
        "visible_documents_as_retrospective_references": [
            {
                "record_id": r["record_id"], "currency": r["currency"],
                "family": r["family"], "reference_period": r["reference_period"],
                "measurement_kind": r["measurement_kind"],
                "gate_basis": r["gate_basis"], "source_url": r["source_url"],
                "reported_values_percent_document_claim": r["reported_values_percent"],
            } for r in visible
        ],
        "not_yet_admissible_record_ids": invisible,
        "four_currency_two_family_documentary_coverage": complete,
    })
    return out


__all__ = ["SCHEMA", "FIXED_CASEBOOK_SHA256",
           "inspect_g8_remaining_four_official_asof_lab"]
