"""Offline semantic CPI custody check after the G8+FX Precision Gate join.

Reparse actual caller-supplied bytes with eight existing CPI source readers.
A matching value/period is only LOCAL DOCUMENT CONSISTENCY, not authentic
publisher data, a point-in-time vintage or comparable bilateral economics.
No HTTP, broker, I/O, score, signal, worker or trading activity.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import re
from typing import Any

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_trader_fx_macro_precision_byte_join_lab import (
    inspect_fx_macro_precision_bytes_lab,
)
from atlasquant_trader_g8_numeric_inflation_coverage_lab import (
    OBSERVED, SUPPLIED_TEXT, build_g8_numeric_inflation_coverage_lab,
)

SCHEMA = "ATLASQUANT_TRADER_G8_CPI_LOCAL_BYTE_SEMANTIC_PRECISION_LAB_V1"
CPI_FIELD = "CPI_YOY"
POLICY_FIELD = "POLICY_RATE"
KNOWN = frozenset(CURRENCIES)
PERIOD = re.compile(r"(?:20\d\d-(?:0[1-9]|1[0-2])|20\d\d-Q[1-4])\Z")
NUMBER = re.compile(r"-?(?:0|[1-9]\d{0,2})(?:\.\d{1,6})?\Z")
CAPTURE_FIELDS = {
    "EUR": ("eur_jsonstat_raw", "eur_capture_utc"),
    "USD": ("usd_bls_raw", "usd_capture_utc"),
    "GBP": ("gbp_ons_raw", "gbp_capture_utc"),
    "JPY": ("jpy_national_page_text_raw", "jpy_capture_utc"),
    "CAD": ("cad_nsa_table_text_raw", "cad_capture_utc"),
    "NZD": ("nzd_quarter_page_text_raw", "nzd_capture_utc"),
    "AUD": ("aud_monthly_page_text_raw", "aud_capture_utc"),
    "CHF": ("chf_national_page_text_raw", "chf_capture_utc"),
}


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _stamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.endswith("Z"):
        return None
    try:
        return _utc(datetime.fromisoformat(value[:-1] + "+00:00"))
    except (ValueError, OverflowError):
        return None


def _decimal(value: Any) -> Decimal | None:
    if not isinstance(value, str) or NUMBER.fullmatch(value) is None:
        return None
    try:
        parsed = Decimal(value)
        return parsed if parsed.is_finite() and -50 <= parsed <= 100 else None
    except (InvalidOperation, ValueError):
        return None


def _empty(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_G8_CPI_SEMANTIC_JOIN_ABSTAIN",
        "reason": reason, "asset": None, "currency_count": 0, "pair_count": 0,
        "currency_checks": {}, "pair_rows": {},
        "cpi_values_locally_reconciled_currencies": 0,
        "cpi_values_locally_reconciled_pairs": 0,
        "cpi_values_attested_by_original_issuer": False,
        "individual_release_instant_authenticated": False,
        "historical_vintage_available_at_decision_verified": False,
        "official_issuer_value_independently_verified": False,
        "cpi_and_hicp_methods_comparable": False,
        "cross_currency_policy_instruments_comparable": False,
        "policy_rate_values_semantically_extracted": False,
        "cpi_price_causality_verified": False,
        "macro_bias": None, "calibrated_probability": None,
        "validated_accuracy": None, "research_candidate_direction": None,
        "operational_bias": "AGUARDAR", "trade_authorized": False,
        "can_feed_live_radar": False, "live_alert_allowed": False,
        "publishable": False, "worker_enabled": False,
        "scheduler_enabled": False, "http_requests": 0,
        "file_writes": 0, "new_cost_brl": 0,
    }


def _check_cpi_currency(*, currency: str, receipts: Any, bodies: Any,
                        as_of_utc: datetime) -> dict[str, Any]:
    result = {
        "currency": currency, "state": "LAB_CPI_VALUE_WAIT",
        "reason": "MISSING_OR_UNPARSEABLE_CPI_SOURCE",
        "local_value_matches_original_bytes": False,
        "value_claim_in_receipt": None,
        "value_extracted_from_supplied_bytes": None,
        "observation_period_from_bytes": None,
        "observation_frequency_from_bytes": None,
        "publication_stage_finality_verified": False,
        "original_issuer_authenticated": False,
        "pre_event_vintage_authenticated": False,
        "source_sha256_matched_locally": False,
        "preliminary_estimate_flag_from_content": None,
    }
    if not isinstance(receipts, list) or not isinstance(bodies, dict):
        return result
    selected = [r for r in receipts if isinstance(r, dict) and r.get("indicator") == CPI_FIELD]
    if len(selected) != 1:
        result["reason"] = "MISSING_OR_DUPLICATED_CPI_VINTAGE"
        return result
    row = selected[0]
    raw = bodies.get(CPI_FIELD)
    if not isinstance(raw, bytes) or not raw or len(raw) > 2_000_000:
        result["reason"] = "MISSING_OR_BAD_SOURCE_BYTES"
        return result
    if not isinstance(row.get("source_sha256"), str) or sha256(raw).hexdigest() != row["source_sha256"]:
        result["reason"] = "SOURCE_HASH_NOT_MATCHED"
        return result
    result["source_sha256_matched_locally"] = True
    parsed_time = _stamp(row.get("captured_at_utc"))
    if parsed_time is None or parsed_time > as_of_utc:
        result["reason"] = "INVALID_OR_FUTURE_CAPTURE_CLOCK"
        return result
    keys = CAPTURE_FIELDS[currency]
    args = {"eur_jsonstat_raw": None, "usd_bls_raw": None,
            "eur_capture_utc": None, "usd_capture_utc": None,
            "as_of_utc": parsed_time}
    args[keys[0]] = raw
    args[keys[1]] = parsed_time
    try:
        report = build_g8_numeric_inflation_coverage_lab(**args)
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        result["reason"] = "CPI_SOURCE_PARSER_FAILED_CLOSED"
        return result
    if report.get("state") != "LAB_G8_NUMERIC_INFLATION_COVERAGE_ONLY":
        result["reason"] = "CPI_SOURCE_PARSER_REJECTED"
        return result
    x = report.get("currencies", {}).get(currency, {})
    if x.get("status") not in (OBSERVED, SUPPLIED_TEXT) or x.get("source_raw_sha256") != sha256(raw).hexdigest():
        result["reason"] = "CPI_SERIES_OR_LOCAL_BYTE_BINDING_INVALID"
        return result
    period = x.get("observation_period")
    claimed_period = row.get("observation_period")
    if (not isinstance(period, str) or PERIOD.fullmatch(period) is None
            or period != claimed_period):
        result["reason"] = "CPI_PERIOD_OR_FREQUENCY_NOT_SAME_AS_RECEIPT"
        result["observation_period_from_bytes"] = period
        return result
    if currency == "NZD" and x.get("observation_frequency") != "QUARTERLY":
        result["reason"] = "NZD_MUST_BE_QUARTERLY_CPI"
        return result
    if currency != "NZD" and x.get("observation_frequency") != "MONTHLY":
        result["reason"] = "NON_NZD_CPI_MUST_BE_MONTHLY"
        return result
    observed_value = x.get("rate_yoy_percent_claim")
    source_value = _decimal(str(observed_value)) if type(observed_value) in (str, float, int) else None
    receipt_value = _decimal(row.get("value"))
    if source_value is None:
        result["reason"] = "ANNUAL_CPI_NUMBER_NOT_DERIVABLE_FROM_SOURCE"
        return result
    if receipt_value is None:
        result["reason"] = "CPI_RECEIPT_NUMERIC_CLAIM_INVALID"
        return result
    result["value_claim_in_receipt"] = str(receipt_value)
    result["value_extracted_from_supplied_bytes"] = str(source_value)
    result["observation_period_from_bytes"] = period
    result["observation_frequency_from_bytes"] = x["observation_frequency"]
    result["preliminary_estimate_flag_from_content"] = x.get("estimated_observation")
    if source_value != receipt_value:
        result["reason"] = "CPI_RECEIPT_VALUE_CONTRADICTS_SOURCE_CONTENT"
        return result
    result.update({
        "state": "LAB_CPI_VALUE_MATCHES_LOCAL_BYTES_UNATTESTED",
        "reason": "CONTENT_MATCHES_CLAIM_BUT_ORIGINAL_PUBLISHER_AND_VINTAGE_NOT_AUTHENTICATED",
        "local_value_matches_original_bytes": True,
    })
    return result


def inspect_g8_cpi_value_custody_precision_lab(
    *, packet: Any, receipts_by_currency: Any,
    original_source_bytes_by_currency: Any,
    d1_archive_root: Any = None,
    inspected_at_utc: Any,
) -> dict[str, Any]:
    """Recalculate G8 macro+precision AND CPI source semantics for all G8.

    This auditor never promotes an economic value to a directional forecast.
    """
    now = _utc(inspected_at_utc)
    if (now is None or not isinstance(receipts_by_currency, dict)
            or not isinstance(original_source_bytes_by_currency, dict)
            or set(receipts_by_currency) != KNOWN
            or set(original_source_bytes_by_currency) != KNOWN):
        return _empty("BAD_G8_INPUT_OR_INSPECTION_CUTOFF")
    try:
        macro = inspect_fx_macro_precision_bytes_lab(
            packet=packet, receipts_by_currency=receipts_by_currency,
            original_source_bytes_by_currency=original_source_bytes_by_currency,
            d1_archive_root=d1_archive_root, inspected_at_utc=now)
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        return _empty("MACRO_PRECISION_COMPOSITION_ERROR")
    if macro.get("pair_count") != 28 or set(macro.get("pair_rows", {})) != set(OFFICIAL_PAIRS):
        return _empty("G8_MACRO_PRECISION_ENVELOPE_BLOCKED")
    audit = {}
    for currency in CURRENCIES:
        audit[currency] = _check_cpi_currency(
            currency=currency, receipts=receipts_by_currency[currency],
            bodies=original_source_bytes_by_currency[currency],
            as_of_utc=now)
    all_pairs = {}
    for pair in OFFICIAL_PAIRS:
        base, quote = split_pair(pair)
        both = bool(audit[base]["local_value_matches_original_bytes"] and
                    audit[quote]["local_value_matches_original_bytes"])
        initial_pair = macro["pair_rows"][pair]
        macro_ready = initial_pair.get("state") == "LAB_PAIR_MACRO_BYTES_LOCALLY_BOUND_UNATTESTED"
        all_pairs[pair] = {
            "state": ("LAB_TWO_CPI_VALUES_MATCH_LOCAL_CONTENT_NO_BIAS" if both and macro_ready
                      else "LAB_PAIR_CPI_SEMANTIC_ABSTAIN"),
            "two_cpi_values_locally_reconciled": both,
            "existing_macro_asof_bytes_research_eligible": macro_ready,
            "blocking_reasons": ([] if both and macro_ready else
                [reason for reason in (
                    (f"{base}:{audit[base]['reason']}" if not audit[base]["local_value_matches_original_bytes"] else ""),
                    (f"{quote}:{audit[quote]['reason']}" if not audit[quote]["local_value_matches_original_bytes"] else ""),
                    ("MACRO_OR_PRECISION_ABSTAIN" if not macro_ready else "")) if reason]),
            "country_inflation_methodologies_harmonized": False,
            "inflation_differential_allowed": False,
            "operational_bias": "AGUARDAR", "trade_authorized": False,
        }
    out = _empty("SOME_CURRENCIES_MISSING_OR_UNVERIFIED_CPI_SEMANTICS")
    matched_currencies = sum(x["local_value_matches_original_bytes"] for x in audit.values())
    paired = sum(x["two_cpi_values_locally_reconciled"] for x in all_pairs.values())
    out.update({
        "state": ("LAB_G8_CPI_SEMANTIC_ALL_LOCAL_CONTENT_RECONCILED_NO_BIAS"
                  if matched_currencies == 8 else "LAB_G8_CPI_PARTIAL_SEMANTIC_RECONCILIATION_ABSTAIN"),
        "reason": "SEMANTIC_MATCH_ALONE_DOES_NOT_PROVE_RELEASE_AUTHENTICITY_OR_FX_EDGE",
        "asset": macro.get("asset"), "currency_count": len(audit),
        "pair_count": len(all_pairs),
        "currency_checks": audit, "pair_rows": all_pairs,
        "cpi_values_locally_reconciled_currencies": matched_currencies,
        "cpi_values_locally_reconciled_pairs": paired,
        "upstream_precision_stage_reports": macro.get("precision_stage_reports", {}),
        "upstream_precision_blocking_stages": macro.get("precision_blocking_stages", []),
        "upstream_macro_structural_state": macro.get("state"),
        "upstream_d1_archive_bytes_gate_state": macro.get("d1_archive_bytes_gate_state"),
        "upstream_d1_archive_bytes_gate_reason": macro.get("d1_archive_bytes_gate_reason"),
        "upstream_d1_archive_bytes_pit_authenticated": False,
        "upstream_economic_values_still_unverified": True,
    })
    return out


__all__ = ("SCHEMA", "inspect_g8_cpi_value_custody_precision_lab")