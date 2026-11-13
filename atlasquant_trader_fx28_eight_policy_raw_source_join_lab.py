"""Eight-bank raw policy source admission gate for 28 FX pairs: LAB only.

A bank's contract/module existing in GitHub is NEVER a captured document.
Given exact caller-supplied source bytes and local HTTP receipts, run the
appropriate existing issuer-specific parser/byte-hash/clock checks.
Build a documentary per-currency and per-pair *policy-source coverage*
matrix without normalizing different interest rate instruments, inferring
CPI, claiming source authenticity or forecasting currency direction.

This gate does not read the AM12, make HTTP calls, authenticate issuer
publication, confirm storage on disk or certify retroactive PIT vintage.
The caller may forge the original bytes and local timestamps; even 8/8
locally checked NEVER means a witnessed/accurate forecast. No broker,
account, positions, MT5 orders, auto worker or production operations.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_trader_us_fed_board_target_range_receipt_lab import (
    inspect_fed_board_policy_target_range_receipt_lab,
)
from atlasquant_trader_eur_ecb_dfr_sdmx_receipt_lab import (
    inspect_ecb_dfr_change_date_csv_receipt_lab,
)
from atlasquant_trader_gbp_boe_bank_rate_history_receipt_lab import (
    inspect_boe_bank_rate_history_receipt_lab,
)
from atlasquant_trader_jpy_boj_guideline_source_receipt_lab import (
    inspect_boj_home_guideline_receipt_lab,
)
from atlasquant_trader_chf_snb_current_policy_receipt_lab import (
    inspect_snb_current_policy_receipt_lab,
)
from atlasquant_trader_cad_boc_valet_policy_receipt_lab import (
    inspect_boc_valet_policy_receipt_lab,
)
from atlasquant_trader_aud_rba_cash_target_receipt_lab import (
    inspect_rba_cash_target_current_receipt_lab,
)
from atlasquant_trader_nzd_rbnz_ocr_receipt_lab import (
    inspect_rbnz_official_ocr_receipt_lab,
)

SCHEMA = "ATLASQUANT_FX28_EIGHT_BANK_POLICY_RAW_SOURCE_JOIN_LAB_V1"
PACKET_KEYS = frozenset(("original_bytes", "receipt"))
_VALIDATORS: dict[str, tuple[Callable[..., dict[str, Any]], str, str]] = {
    "USD": (
        inspect_fed_board_policy_target_range_receipt_lab,
        "original_html", "LAB_USD_FED_BOARD_ORIGINAL_HTML_LOCALLY_CHECKED_NO_GO",
    ),
    "EUR": (
        inspect_ecb_dfr_change_date_csv_receipt_lab,
        "original_csv", "LAB_EUR_ECB_SDMX_ORIGINAL_BYTES_LOCALLY_CHECKED_NO_GO",
    ),
    "GBP": (
        inspect_boe_bank_rate_history_receipt_lab,
        "original_html", "LAB_GBP_BOE_ORIGINAL_HISTORY_HTML_LOCALLY_CHECKED_NO_GO",
    ),
    "JPY": (
        inspect_boj_home_guideline_receipt_lab,
        "original_html", "LAB_JPY_BOJ_CURRENT_GUIDELINE_HTML_LOCALLY_CHECKED_NO_GO",
    ),
    "CHF": (
        inspect_snb_current_policy_receipt_lab,
        "original_html", "LAB_CHF_SNB_CURRENT_POLICY_HTML_LOCALLY_CHECKED_NO_GO",
    ),
    "CAD": (
        inspect_boc_valet_policy_receipt_lab,
        "original_body", "LAB_CAD_BOC_ORIGINAL_BYTES_LOCALLY_CHECKED_NO_GO",
    ),
    "AUD": (
        inspect_rba_cash_target_current_receipt_lab,
        "original_html", "LAB_AUD_RBA_CASH_TARGET_HTML_LOCALLY_CHECKED_NO_GO",
    ),
    "NZD": (
        inspect_rbnz_official_ocr_receipt_lab,
        "original_html", "LAB_NZD_RBNZ_OCR_HTML_LOCALLY_CHECKED_NO_GO",
    ),
}


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_FX28_POLICY_RAW_SOURCE_JOIN_BLOCKED",
        "reason": reason,
        "currency_universe_size": len(CURRENCIES),
        "source_parser_contracts_available": len(_VALIDATORS),
        "source_packets_provided": 0,
        "local_source_bytes_reconciled_currency_count": 0,
        "locally_checked_currencies": [],
        "missing_currencies": sorted(CURRENCIES),
        "rejected_currencies": {},
        "pair_horizon_independent_claims": False,
        "fx28_official_pair_count": len(OFFICIAL_PAIRS),
        "pairs_with_both_policy_sources_locally_checked_count": 0,
        "pairs_missing_or_rejecting_any_policy_source_count": len(OFFICIAL_PAIRS),
        "pair_policy_source_coverage": [],
        "source_bytes_retained_on_am12_independently_verified": False,
        "actual_issuer_origin_independently_authenticated": False,
        "source_local_http_receipt_is_independent_witness": False,
        "policy_first_release_timestamp_authenticated": False,
        "historical_asof_vintage_authenticated": False,
        "full_bilateral_CPI_YOY_sources_authenticated": False,
        "economic_policy_rate_instruments_harmonized": False,
        "pre_event_forecast_witnessed": False,
        "ny17_m15_pair_outcomes_verified": False,
        "directional_bias": None,
        "calibrated_directional_probability": None,
        "historical_accuracy": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False,
        "publishable": False,
        "live_alert_allowed": False,
        "worker_enabled": False,
        "scheduler_enabled": False,
        "http_requests": 0,
        "files_written": 0,
        "new_cost_brl": 0,
        "research_only": True,
    }


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    try:
        if value.utcoffset() is None or value.microsecond:
            return None
        return value.astimezone(timezone.utc)
    except (OverflowError, ValueError, TypeError):
        return None


def inspect_eight_bank_policy_raw_source_join_lab(
    *, source_packets_by_currency: Any, decision_at_utc: Any,
) -> dict[str, Any]:
    """Eight original-byte validators; all outputs remain research-only NO-GO.

    Each packet has EXACT keys:
      {"original_bytes": bytes, "receipt": <issuer-specific receipt dict>}

    Missing currency = not present; rejected = malformed or invalid source.
    A matching hash only certifies coherence of caller-controlled inputs.
    """
    result = _base("INVALID_SOURCE_PACKET_MAP_OR_CLOCK")
    decision = _utc(decision_at_utc)
    if (decision is None or type(source_packets_by_currency) is not dict
            or len(source_packets_by_currency) > len(CURRENCIES)
            or not all(type(c) is str and c in _VALIDATORS
                       for c in source_packets_by_currency)):
        return result

    accepted = []
    rejected: dict[str, str] = {}
    for currency in sorted(source_packets_by_currency):
        packet = source_packets_by_currency[currency]
        if type(packet) is not dict or set(packet) != PACKET_KEYS:
            rejected[currency] = "SOURCE_PACKET_SHAPE_INVALID"
            continue
        if type(packet["original_bytes"]) is not bytes:
            rejected[currency] = "MISSING_OR_NONBYTE_ORIGINAL_SOURCE"
            continue
        parser, source_key, accepted_state = _VALIDATORS[currency]
        try:
            checked = parser(
                **{source_key: packet["original_bytes"]},
                receipt=packet["receipt"],
                decision_at_utc=decision,
            )
        except (TypeError, ValueError, KeyError, OverflowError, UnicodeError,
                RecursionError, IndexError):
            rejected[currency] = "ISSUER_PARSER_RAISED_ON_MALFORMED_INPUT"
            continue
        if (type(checked) is not dict
                or checked.get("state") != accepted_state
                or checked.get("trade_authorized") is not False
                or checked.get("publishable") is not False):
            rejected[currency] = (
                checked.get("reason", "ISSUER_RAW_SOURCE_GATE_REJECTED")
                if type(checked) is dict else "INVALID_ISSUER_GATE_RESPONSE"
            )
            continue
        accepted.append(currency)

    good = set(accepted)
    pair_coverage = []
    good_pairs = 0
    for pair in OFFICIAL_PAIRS:
        base, quote = split_pair(pair)
        both = base in good and quote in good
        good_pairs += int(both)
        pair_coverage.append({
            "pair": pair,
            "base_policy_original_locally_checked": base in good,
            "quote_policy_original_locally_checked": quote in good,
            "both_policy_sources_locally_checked": both,
            "cpi_both_currencies_authenticated": False,
            "fx_direction_admissible": False,
        })

    result.update({
        "state": (
            "LAB_FX28_EIGHT_POLICY_ORIGINAL_BYTES_LOCAL_ONLY_NO_GO"
            if len(good) == len(CURRENCIES) else
            "LAB_FX28_PARTIAL_OR_REJECTED_POLICY_ORIGINAL_BYTES_NO_GO"
        ),
        "reason": (
            "EIGHT_LOCAL_CHECKS_NEVER_PROVE_ISSUER_PIT_OR_CPI_BILATERAL"
            if len(good) == len(CURRENCIES) else
            "MISSING_OR_INVALID_POLICY_RAW_OR_RECEIPT_PER_CURRENCY"
        ),
        "source_packets_provided": len(source_packets_by_currency),
        "local_source_bytes_reconciled_currency_count": len(good),
        "locally_checked_currencies": accepted,
        "missing_currencies": sorted(set(CURRENCIES) - set(source_packets_by_currency)),
        "rejected_currencies": rejected,
        "pairs_with_both_policy_sources_locally_checked_count": good_pairs,
        "pairs_missing_or_rejecting_any_policy_source_count":
            len(OFFICIAL_PAIRS) - good_pairs,
        "pair_policy_source_coverage": pair_coverage,
    })
    return result


__all__ = ("SCHEMA", "inspect_eight_bank_policy_raw_source_join_lab")
