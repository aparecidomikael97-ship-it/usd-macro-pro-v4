"""Read-only audit bridge between archived AUD/NZD CPI bytes and V2 series claims.

This links a value/period/series/hash to known archive copies, not to a
historically available issuer vintage. It MUST NEVER be an FX bias or signal.
All publication and capture instants are asserted by a caller, not attested.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from atlasquant_audnzd_cpi_archive_receipt_lab import inspect_archived_audnzd_cpi_lab
from atlasquant_cpi_series_contract_lab import audit_cpi_series_lab

SCHEMA = "ATLASQUANT_AUDNZD_ARCHIVE_TO_SERIES_LINK_LAB_V1"
ARCHIVE_OK = "LAB_TWO_DOCUMENT_VALUES_MATCH_ARCHIVED_BYTES_UNATTESTED"
SERIES_OK = "LAB_CPI_SAME_FREQUENCY_UNATTESTED"
SERIES_KEYS = {"AUD": "AUD_QUARTERLY_CPI_YOY", "NZD": "NZD_QUARTERLY_CPI_YOY"}


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_BLOCKED",
        "reason": reason,
        "pair": "AUD/NZD",
        "economic_period": "2026-Q3",
        "archive_values_linked_to_series": False,
        "archive_byte_integrity_verified": False,
        "bilateral_series_cadence": None,
        "research_comparison": None,
        "issuer_origin_independently_authenticated": False,
        "release_instant_independently_attested": False,
        "capture_instant_independently_attested": False,
        "historical_point_in_time_verified": False,
        "methodology_equivalent_proven": False,
        "out_of_sample_accuracy_verified": False,
        "probability_of_directional_move": None,
        "score_0_to_10": None,
        "operational_bias": "AGUARDAR",
        "can_feed_live_radar": False,
        "automatic_alert_enabled": False,
        "trade_authorized": False,
        "broker_command": None,
        "new_cost_brl": 0,
    }


def inspect_archived_cpi_series_link_lab(
    *, aud_xlsx: Any, nzd_pdf: Any, series_payload: Any,
    as_of_utc: Any,
) -> dict[str, Any]:
    """Cross-check archive contents against externally asserted series receipts.

    The archive inspection is independently executed on supplied bytes, but
    matching pinned bytes is NOT authentication of the issuer's original file.
    Thus this result is a *research linkage*, never PIT/backtest authorization.
    """
    result = _blocked("SOURCE_SERIES_LINK_UNVERIFIED")
    archive = inspect_archived_audnzd_cpi_lab(
        aud_xlsx=aud_xlsx, nzd_pdf=nzd_pdf, as_of_utc=as_of_utc)
    if archive["state"] != ARCHIVE_OK:
        result["reason"] = "ARCHIVE_GATE:" + archive["reason"]
        return result
    # The V2 contract validates both receipts, clock ordering, frequencies,
    # period recency, URL form, caller-provided SHA format, and 2 currencies.
    series = audit_cpi_series_lab(series_payload, as_of_utc=as_of_utc)
    if series["state"] != SERIES_OK:
        result["reason"] = "SERIES_GATE:" + series["reason"]
        return result

    try:
        receipt = archive["source_receipts"]
        extracted = archive["inflation_comparison"]
        expected_values = {
            "AUD": Decimal(extracted["AUD_annual_yoy_pct_derived_from_rounded_index"]),
            "NZD": Decimal(extracted["NZD_annual_yoy_pct_publisher_reported"]),
        }
        rows = {row["currency"]: row for row in series_payload["records"]}
    except (KeyError, ValueError, InvalidOperation, TypeError):
        result["reason"] = "ARCHIVE_RECEIPT_SHAPE_OR_VALUE_INVALID"
        return result
    for currency in ("AUD", "NZD"):
        row = rows[currency]
        metadata = series["coverage"][currency]
        if (row["atlasquant_series_key"] != SERIES_KEYS[currency]
                or metadata["frequency"] != "QUARTERLY"
                or row["observation_period"] != "2026-09"):
            result["reason"] = currency + ":WRONG_SERIES_OR_REFERENCE_PERIOD"
            return result
        if row["source_sha256"] != receipt[currency]["archive_sha256"]:
            result["reason"] = currency + ":ARCHIVE_HASH_NOT_LINKED"
            return result
        # The archived document records the release *date* only. Match the
        # asserted date, but explicitly leave exact timing unverified.
        if row["published_at_utc"][:10] != receipt[currency]["published_release_date_claim"]:
            result["reason"] = currency + ":RELEASE_DATE_CLAIM_MISMATCH"
            return result
        try:
            observed = Decimal(row["value"])
        except (ValueError, InvalidOperation, TypeError):
            result["reason"] = currency + ":INVALID_VALUE"
            return result
        if observed != expected_values[currency]:
            result["reason"] = currency + ":ECONOMIC_VALUE_NOT_LINKED"
            return result

    result.update({
        "state": "LAB_ARCHIVED_CPI_VALUES_LINKED_UNATTESTED",
        "reason": "MATCHED_ARCHIVE_BYTES_AND_METADATA_NOT_HISTORICAL_PIT",
        "archive_values_linked_to_series": True,
        "archive_byte_integrity_verified": True,
        "bilateral_series_cadence": "QUARTERLY",
        "research_comparison": {
            "AUD_2026_Q3_CPI_YOY_pct_from_rounded_index": str(expected_values["AUD"]),
            "NZD_2026_Q3_CPI_YOY_pct_reported": str(expected_values["NZD"]),
            "difference_pp_descriptive_only": str(expected_values["AUD"] - expected_values["NZD"]),
            "may_infer_fx_direction": False,
        },
    })
    return result


__all__ = ["SCHEMA", "inspect_archived_cpi_series_link_lab"]
