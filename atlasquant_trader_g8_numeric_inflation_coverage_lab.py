"""Offline G8/28-pair inflation coverage from supplied EUR, USD, GBP bytes.

An observed source response is not a historical release vintage. CPI-U NSA
derived YoY and HICP YoY do not establish a directional currency signal.
No HTTP, ranking, trading, execution or cross-method subtraction.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_trader_bls_us_cpiu_once_lab import parse_current_bls_cpiu_lab
from atlasquant_trader_eurostat_eur_hicp_once_lab import (
    parse_current_eur_hicp_jsonstat_lab,
)
from atlasquant_trader_g8_official_source_receipt_lab import SOURCES
from atlasquant_trader_ons_gbp_cpi_current_lab import parse_current_ons_gbp_d7g7_lab
from atlasquant_trader_jp_national_cpi_summary_text_lab import (
    parse_jp_national_cpi_summary_text_lab,
)
from atlasquant_trader_statcan_cad_cpi_table_text_lab import (
    parse_statcan_cad_all_items_table_text_lab,
)
from atlasquant_trader_statsnz_nzd_cpi_quarter_text_lab import (
    parse_statsnz_nzd_cpi_sep2026_quarter_text_lab,
)

SCHEMA = "ATLASQUANT_TRADER_G8_NUMERIC_INFLATION_COVERAGE_LAB_V1"
MISSING = "NO_NUMERIC_INFLATION_CAPTURE_SUPPLIED"
OBSERVED = "CURRENT_NUMERIC_CAPTURE_STRUCTURALLY_PARSED_UNATTESTED"
SUPPLIED_TEXT = "SUPPLIED_OFFICIAL_PAGE_TEXT_STRUCTURALLY_PARSED_UNATTESTED"


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "currency_count": 0, "pair_count": 0,
        "currencies": {}, "pairs": [], "pair_count_by_numeric_sides": {},
        "authentic_release_instant_verified": False,
        "point_in_time_vintage_verified": False,
        "consensus_pre_event_attested": False,
        "historical_backtest_accuracy_verified": False,
        "cross_source_methodologically_comparable": False,
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "trade_authorized": False, "can_feed_live_radar": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "publishable": False, "external_http_requests": 0,
        "new_cost_brl": 0,
    }


def _utc(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None):
        return None
    return value.astimezone(timezone.utc)


def _capture(
    raw: Any, captured: Any, as_of: datetime, currency: str,
) -> dict[str, Any] | None:
    """None denotes invalid; an absent raw+clock is a legitimate missing input."""
    if raw is None and captured is None:
        return {"status": MISSING, "observation_month": None,
                "observation_period": None, "observation_frequency": None,
                "rate_yoy_percent_claim": None, "estimated_observation": None,
                "series_kind": None, "source_raw_sha256": None,
                "captured_at_local_system_utc": None,
                "has_valid_same_month_prior_year": None}
    stamp = _utc(captured)
    if not isinstance(raw, bytes) or stamp is None or stamp > as_of:
        return None
    try:
        if currency == "EUR":
            parsed = parse_current_eur_hicp_jsonstat_lab(raw, observed_at_utc=stamp)
        elif currency == "USD":
            parsed = parse_current_bls_cpiu_lab(raw, observed_at_utc=stamp)
        elif currency == "GBP":
            parsed = parse_current_ons_gbp_d7g7_lab(raw, observed_at_utc=stamp)
        elif currency == "JPY":
            parsed = parse_jp_national_cpi_summary_text_lab(raw, observed_at_utc=stamp)
        elif currency == "CAD":
            parsed = parse_statcan_cad_all_items_table_text_lab(raw, observed_at_utc=stamp)
        else:
            parsed = parse_statsnz_nzd_cpi_sep2026_quarter_text_lab(raw, observed_at_utc=stamp)
    except (TypeError, ValueError, OverflowError):
        return None
    if currency == "EUR":
        if (parsed.get("state") != "LAB_EUR_HICP_CURRENT_JSONSTAT_QUARANTINED"
                or parsed.get("source_dataset") != "prc_hicp_minr"
                or parsed.get("currency") != "EUR"):
            return None
        rows = parsed.get("historical_months_observed_not_historical_vintages")
        if not isinstance(rows, list) or not rows or not isinstance(rows[-1], dict):
            return None
        latest = rows[-1]
        month = latest.get("period")
        rate = latest.get("annual_inflation_percent")
        estimated = latest.get("status_flag") == "e"
        kind = "EUROSTAT_HICP_YOY_ECOICOP_V2"
        prior_year = None
    elif currency == "USD":
        if (parsed.get("state") != "LAB_CURRENT_US_BLS_CPIU_INDEX_QUARANTINED"
                or parsed.get("series_id") != "CUUR0000SA0"
                or parsed.get("currency") != "USD"):
            return None
        month = parsed.get("latest_period")
        rate = parsed.get("derived_yoy_percent_from_same_month_indices")
        estimated = None
        kind = "BLS_CPI_U_NSA_INDEX_YOY_DERIVED"
        prior_year = parsed.get("prior_year_month_observed") is True
        if (rate is not None and not prior_year):
            return None
    elif currency == "GBP":
        if (parsed.get("state") != "LAB_CURRENT_GBP_ONS_D7G7_QUARANTINED"
                or parsed.get("series_id") != "D7G7"
                or parsed.get("source_dataset") != "MM23"
                or parsed.get("currency") != "GBP"):
            return None
        month = parsed.get("latest_period")
        rate = parsed.get("latest_annual_cpi_rate_percent")
        estimated = None
        kind = "ONS_D7G7_CPI_ALL_ITEMS_YOY_DIRECT"
        prior_year = None
    elif currency == "JPY":
        if (parsed.get("state") != "LAB_JP_NATIONAL_CPI_SUPPLIED_TEXT_QUARANTINED"
                or parsed.get("currency") != "JPY"
                or parsed.get("base_year") != 2025):
            return None
        row = parsed.get("national_headline_all_items")
        if not isinstance(row, dict):
            return None
        month = parsed.get("reference_period")
        rate = row.get("reported_yoy_percent_claim")
        estimated = None
        kind = "JP_NATIONAL_CPI_ALL_ITEMS_2025_BASE_YOY_TRANSCRIBED_TEXT"
        prior_year = None
    elif currency == "CAD":
        if (parsed.get("state") != "LAB_CANADA_CPI_SUPPLIED_TABLE_TEXT_QUARANTINED"
                or parsed.get("currency") != "CAD"
                or parsed.get("base_year") != 2002
                or parsed.get("seasonally_adjusted") is not False):
            return None
        month = parsed.get("reference_period")
        rate = parsed.get("published_yoy_percent_claim")
        estimated = None
        kind = "STATCAN_CAD_CPI_ALL_ITEMS_NSA_2002_BASE_YOY_TRANSCRIBED_TEXT"
        prior_year = None
    else:
        if (parsed.get("state") != "LAB_NZD_QUARTERLY_CPI_TEXT_QUARANTINED"
                or parsed.get("currency") != "NZD"
                or parsed.get("observation_frequency") != "QUARTERLY"):
            return None
        month = None  # Quarter ending Sep is NOT a September monthly observation.
        rate = parsed.get("headline_cpi_all_groups_annual_change_percent_claim")
        estimated = None
        kind = "STATS_NZ_CPI_ALL_GROUPS_QUARTERLY_YOY_TRANSCRIBED_TEXT"
        prior_year = None
    frequency = "QUARTERLY" if currency == "NZD" else "MONTHLY"
    period = parsed.get("observation_period") if currency == "NZD" else month
    return {
        "status": SUPPLIED_TEXT if currency in ("JPY", "CAD", "NZD") else OBSERVED,
        "observation_month": month,
        "observation_period": period,
        "observation_frequency": frequency,
        "rate_yoy_percent_claim": rate,
        "estimated_observation": estimated,
        "series_kind": kind,
        "source_raw_sha256": sha256(raw).hexdigest(),
        "captured_at_local_system_utc": stamp.isoformat(),
        "has_valid_same_month_prior_year": prior_year,
    }


def build_g8_numeric_inflation_coverage_lab(
    *, eur_jsonstat_raw: Any, usd_bls_raw: Any,
    eur_capture_utc: Any, usd_capture_utc: Any, as_of_utc: Any,
    gbp_ons_raw: Any = None, gbp_capture_utc: Any = None,
    jpy_national_page_text_raw: Any = None, jpy_capture_utc: Any = None,
    cad_nsa_table_text_raw: Any = None, cad_capture_utc: Any = None,
    nzd_quarter_page_text_raw: Any = None, nzd_capture_utc: Any = None,
) -> dict[str, Any]:
    """Inventory source coverage for all canonical 28 crosses, no FX bias."""
    as_of = _utc(as_of_utc)
    if as_of is None:
        return _blocked("AS_OF_UTC_REQUIRED")
    eur = _capture(eur_jsonstat_raw, eur_capture_utc, as_of, "EUR")
    usd = _capture(usd_bls_raw, usd_capture_utc, as_of, "USD")
    gbp = _capture(gbp_ons_raw, gbp_capture_utc, as_of, "GBP")
    jpy = _capture(jpy_national_page_text_raw, jpy_capture_utc, as_of, "JPY")
    cad = _capture(cad_nsa_table_text_raw, cad_capture_utc, as_of, "CAD")
    nzd = _capture(nzd_quarter_page_text_raw, nzd_capture_utc, as_of, "NZD")
    if any(x is None for x in (eur, usd, gbp, jpy, cad, nzd)):
        return _blocked("MALFORMED_OR_FUTURE_SOURCE_CAPTURE")

    source_leads = {
        value["currency"]: key for key, value in SOURCES.items()
        if value["family"] == "INFLATION"
    }
    if (set(source_leads) != set(CURRENCIES) or len(OFFICIAL_PAIRS) != 28):
        return _blocked("G8_REGISTRY_OR_SOURCE_LEADS_INCOMPLETE")
    currencies = {}
    for currency in CURRENCIES:
        row = (eur if currency == "EUR" else usd if currency == "USD"
               else gbp if currency == "GBP" else jpy if currency == "JPY"
               else cad if currency == "CAD" else nzd if currency == "NZD" else {
            "status": MISSING, "observation_month": None,
            "observation_period": None, "observation_frequency": None,
            "rate_yoy_percent_claim": None, "estimated_observation": None,
            "series_kind": None, "source_raw_sha256": None,
            "captured_at_local_system_utc": None,
            "has_valid_same_month_prior_year": None,
        })
        currencies[currency] = {
            "currency": currency,
            "official_documentation_lead_only": source_leads[currency],
            **row,
            "release_instant_attested": False,
            "pre_event_vintage_attested": False,
            "original_source_authenticity_independently_verified": False,
            "commercial_redistribution_rights_verified": False,
        }

    pairs = []
    counts = {0: 0, 1: 0, 2: 0}
    for symbol in OFFICIAL_PAIRS:
        base, quote = split_pair(symbol)
        b, q = currencies[base], currencies[quote]
        numeric_sides = int(b["status"] in (OBSERVED, SUPPLIED_TEXT)) + int(
            q["status"] in (OBSERVED, SUPPLIED_TEXT))
        counts[numeric_sides] += 1
        blockers = []
        if b["status"] not in (OBSERVED, SUPPLIED_TEXT):
            blockers.append("BASE_INFLATION_DATA_MISSING")
        if q["status"] not in (OBSERVED, SUPPLIED_TEXT):
            blockers.append("QUOTE_INFLATION_DATA_MISSING")
        same_month = None
        same_period = None
        frequencies_aligned = None
        if numeric_sides == 2:
            frequencies_aligned = b["observation_frequency"] == q["observation_frequency"]
            if not frequencies_aligned:
                blockers.append("OBSERVATION_FREQUENCIES_DIFFER")
            same_period = (frequencies_aligned
                           and b["observation_period"] == q["observation_period"])
            same_month = (frequencies_aligned
                          and b["observation_frequency"] == "MONTHLY"
                          and b["observation_month"] == q["observation_month"])
            if not same_month:
                blockers.append("OBSERVATION_MONTHS_DIFFER")
            if "QUARTERLY" in (b["observation_frequency"], q["observation_frequency"]):
                blockers.append("QUARTERLY_CPI_MUST_NOT_MASQUERADE_AS_MONTHLY")
            if (b["rate_yoy_percent_claim"] is None
                    or q["rate_yoy_percent_claim"] is None):
                blockers.append("ANNUAL_RATE_DENOMINATOR_MISSING")
            if {base, quote} == {"EUR", "USD"}:
                blockers.append("HICP_AND_CPI_U_METHODS_NOT_IDENTICAL")
            else:
                blockers.append("CROSS_COUNTRY_INFLATION_METHODS_NOT_HARMONIZED")
        blockers.extend(("RELEASE_VINTAGES_AND_CONSENSUS_UNATTESTED",
                         "INDEPENDENT_SPOT_PRICE_AND_OOS_MISSING"))
        pairs.append({
            "pair": symbol, "base": base, "quote": quote,
            "numeric_observation_sides": numeric_sides,
            "base_latest_month": b["observation_month"],
            "quote_latest_month": q["observation_month"],
            "base_latest_period": b["observation_period"],
            "quote_latest_period": q["observation_period"],
            "base_frequency": b["observation_frequency"],
            "quote_frequency": q["observation_frequency"],
            "observation_frequencies_aligned_if_both": frequencies_aligned,
            "observation_periods_aligned_if_both": same_period,
            "observation_months_aligned_if_both": same_month,
            "methods_comparable": False,
            "inflation_difference_percentage_points": None,
            "currency_strength_rank": None,
            "comparison_blockers": blockers,
            "D1": "AGUARDAR", "W1": "AGUARDAR", "MN1": "AGUARDAR",
            "fx_bias": None, "trade_authorized": False,
        })

    out = _blocked("NUMERIC_COVERAGE_NOT_A_DIRECT_FX_BIAS")
    out.update({
        "state": "LAB_G8_NUMERIC_INFLATION_COVERAGE_ONLY",
        "as_of_utc": as_of.isoformat(),
        "currency_count": len(currencies), "pair_count": len(pairs),
        "currencies": currencies, "pairs": pairs,
        "pair_count_by_numeric_sides": {str(k): v for k, v in counts.items()},
        "no_other_currencies_inferred_from_eur_or_usd": True,
        "raw_source_capture_is_not_release_vintage": True,
    })
    return out


__all__ = ["SCHEMA", "MISSING", "OBSERVED", "SUPPLIED_TEXT",
           "build_g8_numeric_inflation_coverage_lab"]
