"""Eurostat HICP first-publication metadata: EA21, full != flash, no PIT.

The official dataset page describes an API query plan; this code has NEVER
received a prc_hicp_fpd data response. A historical first-release dataset
also had a documented 2026 alteration/restoration, so its CURRENT presence
does not authenticate an original historical API receipt or release clock.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any

from atlasquant_trader_eurusd_nov6_official_asof_lab import (
    inspect_eurusd_nov6_official_asof_lab,
)

SCHEMA = "ATLASQUANT_TRADER_EUROSTAT_FPD_EA21_DOCUMENTARY_METADATA_LAB_V1"
KIND = "RETROSPECTIVE_OFFICIAL_DATASET_METADATA_NOT_ORIGINAL_DATA_RESPONSE"
FIXED_CASEBOOK_SHA256 = "83634077ccdf9220515b84e2668a12e781c5f7852378738c0e17beb4a91937e4"
DIMENSIONS = ("freq", "unit", "coicop", "release", "geo", "TIME_PERIOD")
DOC_STATES = frozenset((
    "LAB_FOUR_DOCUMENT_REFERENCES_VISIBLE_BUT_PIT_UNATTESTED",
    "LAB_PARTIAL_DOCUMENT_CONTEXT_ONLY_NO_FX_BIAS",
))
SEPTEMBER_FULL_DOC_GATE = datetime(2026, 10, 17, tzinfo=timezone.utc)


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "accepted_casebook_sha256": None,
        "dataset_id": "prc_hicp_fpd",
        "2026_euro_area_geo_candidate": "EA21",
        "2025_euro_area_geo_historical": "EA20",
        "api_dimension_labels_documented_only": [],
        "sep2026_full_dataset_metadata_reference_visible_asof": False,
        "documentary_latest_full_reference_period_asof": None,
        "oct2026_flash_reference_visible_in_separate_case": False,
        "oct2026_full_release_data_in_this_lab": False,
        "jan2026_first_released_dataset_had_2026_erratum": True,
        "original_feb2026_first_release_bytes_witnessed": False,
        "dataset_api_payload_captured": False,
        "schema_dimension_codes_verified": False,
        "original_historical_release_time_witnessed": False,
        "flash_and_final_same_observation_assumed": False,
        "valid_oct2026_full_inferred_from_scheduled_date": False,
        "historical_first_released_data_immutable_verified": False,
        "can_supply_pit_macroeconomic_vintage": False,
        "validated_prediction_count": 0, "validated_accuracy": None,
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "can_feed_live_radar": False, "trade_authorized": False,
        "publishable": False, "worker_enabled": False,
        "scheduler_enabled": False, "http_requests": 0, "new_cost_brl": 0,
    }


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for k, v in pairs:
        if k in result:
            raise ValueError("duplicate metadata key")
        result[k] = v
    return result


def inspect_eurostat_fpd_ea21_metadata_gate_lab(
    metadata_casebook_raw: Any, *, eurusd_casebook_raw: Any,
    as_of_utc: Any,
) -> dict[str, Any]:
    """Admit only dated official-page *metadata*; never make a CPI reading."""
    out = _blocked("INVALID_METADATA_OR_CLOCK_OR_EURUSD_CASEBOOK")
    if (not isinstance(as_of_utc, datetime) or as_of_utc.tzinfo is None
            or as_of_utc.utcoffset() is None
            or not isinstance(metadata_casebook_raw, bytes)
            or not 400 <= len(metadata_casebook_raw) <= 10000
            or sha256(metadata_casebook_raw).hexdigest() != FIXED_CASEBOOK_SHA256):
        return out
    now = as_of_utc.astimezone(timezone.utc)
    eurusd = inspect_eurusd_nov6_official_asof_lab(
        eurusd_casebook_raw, as_of_utc=now)
    if eurusd["state"] not in DOC_STATES:
        return out
    try:
        case = json.loads(metadata_casebook_raw.decode("utf-8", "strict"),
                          object_pairs_hook=_unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))
        geo = case["euro_area_geographical_rules"]
        erratum = case["historical_erratum"]
        if (case["schema"] != SCHEMA or case["kind"] != KIND
                or case["research_date"] != "2026-11-06"
                or case["dataset_id"] != "prc_hicp_fpd"
                or tuple(case["documented_dimension_names_not_actual_api_codes"]) != DIMENSIONS
                or geo["through_2025_12"] != "EA20"
                or geo["from_2026_01"] != "EA21"
                or geo["bulgaria_joined_date"] != "2026-01-01"
                or geo["evolving_ea_aggregate_requires_composition_method"] is not True
                or geo["ea20_is_2026_target_geo"] is not False
                or case["classification_2026"] != "ECOICOP_VERSION_2_COICOP2018"
                or case["dataset_documentary_last_full_period_seen_on_2026_11_06"] != "2026-09"
                or case["last_full_dataset_update_claim_calendar_date"] != "2026-10-16"
                or case["conservative_sep2026_documentary_gate_utc"] != "2026-10-17T00:00:00Z"
                or case["october_2026_full_release_scheduled_date"] != "2026-11-18"
                or case["october_2026_full_release_value_captured"] is not False
                or case["october_flash_is_not_fpd_full_release"] is not True
                or case["full_dataset_response_received"] is not False
                or case["real_dimension_code_values_read_from_response"] is not False
                or case["api_unit_code_for_annual_rate_verified"] is not False
                or case["api_release_dimension_codes_verified"] is not False
                or case["historical_original_response_bytes_archived"] is not False
                or case["independently_witnessed_original_release_instant"] is not False
                or erratum != {
                    "reference_period": "2026-01",
                    "initial_full_release_date": "2026-02-25",
                    "incorrect_fpd_update_date": "2026-03-03",
                    "original_fpd_restored_date": "2026-04-24",
                    "feb25_original_bytes_witnessed_by_this_lab": False,
                    "historical_first_published_dataset_never_changed_claim": False,
                }):
            return out
    except (UnicodeDecodeError, ValueError, KeyError, TypeError, AttributeError,
            RecursionError):
        return out

    flash_visible = any(
        d["record_id"] == "EUR_EUROSTAT_OCT2026_HICP_FLASH"
        for d in eurusd["visible_documents_as_retrospective_references"])
    sep_metadata_visible = now >= SEPTEMBER_FULL_DOC_GATE
    out.update({
        "state": "LAB_EUROSTAT_EA21_FPD_METADATA_ONLY_NOT_API_PAYLOAD",
        "reason": "FIRST_PUBLISHED_VALUES_ARE_NOT_INDEPENDENT_HISTORICAL_RELEASE_RECEIPTS",
        "accepted_casebook_sha256": sha256(metadata_casebook_raw).hexdigest(),
        "api_dimension_labels_documented_only": list(DIMENSIONS),
        "sep2026_full_dataset_metadata_reference_visible_asof": sep_metadata_visible,
        "documentary_latest_full_reference_period_asof": (
            "2026-09" if sep_metadata_visible else None),
        "oct2026_flash_reference_visible_in_separate_case": flash_visible,
    })
    return out


__all__ = ["SCHEMA", "FIXED_CASEBOOK_SHA256",
           "inspect_eurostat_fpd_ea21_metadata_gate_lab"]
