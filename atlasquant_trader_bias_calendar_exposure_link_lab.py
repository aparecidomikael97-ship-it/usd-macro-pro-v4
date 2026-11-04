"""Explanatory join of synthetic FX bias and partial documentary event risk.

The result is never an operational bias. Neither the synthetic strength matrix
nor either manually curated calendar vintage has authenticated market custody.
Rolling event windows are not chart candles or D1/W1/MN1 return forecasts.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Mapping

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_trader_bias_priority_bridge_lab import SCHEMA as BIAS_SCHEMA
from atlasquant_trader_macro_event_exposure_lab import (
    SCHEMA as CALENDAR_SCHEMA, build_macro_event_exposure_lab,
)
from atlasquant_trader_macro_event_exposure_v2_lab import (
    SCHEMA as CALENDAR_V2_SCHEMA, build_macro_event_exposure_v2_lab,
)

SCHEMA = "ATLASQUANT_TRADER_BIAS_CALENDAR_EXPOSURE_LINK_LAB_V1"
HORIZONS = ("D1", "W1", "MN1")
HYPOTHESES = frozenset(("ALTA", "BAIXA", "NEUTRO", "AGUARDAR"))
COMPARISONS = frozenset((
    "DADOS_INCOMPLETOS", "HIPOTESES_SINTETICAS_CONCORDAM",
    "NEUTRALIDADE_OU_DIVERGENCIA", "CONFLITO_ENTRE_HIPOTESES",
))
EVIDENCE_DIMENSIONS = frozenset((
    "macro", "micro", "geopolitics", "news", "economic_calendar",
    "relative_strength_origin",
))


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "rows": [], "pair_count": 0, "calendar_complete": False,
        "real_sources_attested": False, "live_prices_verified": False,
        "source_original_bytes_archived": False,
        "real_direction_inferred": False, "probability_calibrated": None,
        "no_event_means_no_risk": False, "can_feed_live_radar": False,
        "trade_authorized": False, "worker_enabled": False,
        "scheduler_enabled": False, "publishable": False,
    }


def _expected_comparison(strength: str, macro: str) -> str:
    if "AGUARDAR" in (strength, macro):
        return "DADOS_INCOMPLETOS"
    if strength == macro and strength in ("ALTA", "BAIXA"):
        return "HIPOTESES_SINTETICAS_CONCORDAM"
    if "NEUTRO" in (strength, macro):
        return "NEUTRALIDADE_OU_DIVERGENCIA"
    return "CONFLITO_ENTRE_HIPOTESES"


def build_bias_calendar_exposure_link_lab(
    bias_report: Any, calendar_report: Any, *, at: datetime,
) -> dict[str, Any]:
    """Produce 28 x D1/W1/MN1 context cards, preserving an unconditional wait.

    The selected partial calendar vintage is reproduced at ``at`` to reject
    event injection, missing events and forged claims of complete coverage.
    """
    if (not isinstance(at, datetime) or at.tzinfo is None
            or at.utcoffset() is None):
        raise ValueError("Evaluation needs a timezone-aware clock")
    now = at.astimezone(timezone.utc)
    if not isinstance(bias_report, Mapping) or not isinstance(calendar_report, Mapping):
        return _blocked("REQUIRED_REPORTS_MISSING")
    if (bias_report.get("schema") != BIAS_SCHEMA
            or bias_report.get("state") != "LAB_EXPLANATION_ONLY"
            or calendar_report.get("schema") not in (CALENDAR_SCHEMA, CALENDAR_V2_SCHEMA)
            or calendar_report.get("state") != "LAB_CALENDAR_RISK_EXPOSURE_ONLY"):
        return _blocked("ONLY_UNPROMOTED_LAB_REPORTS_SUPPORTED")
    # Never accept reports advertising operational or independently verified
    # authority. The join cannot establish provenance of upstream inputs.
    if (any(bias_report.get(key) is not False for key in (
            "trade_authorized", "can_feed_live_radar", "publishable",
            "real_sources_attested", "market_forecast_verified",
            "historical_vintage_attested", "accuracy_90_proven", "worker_enabled",
            "scheduler_enabled"))
            or any(calendar_report.get(key) is not False for key in (
                "trade_authorized", "can_feed_live_radar", "calendar_complete",
                "calendar_realtime_refreshed", "source_original_bytes_archived",
                "independent_source_receipt_verified", "consensus_verified",
                "actual_releases_verified", "market_price_reaction_verified",
                "worker_enabled", "scheduler_enabled"))
            or bias_report.get("probability_calibrated") is not None):
        return _blocked("FORGED_AUTHORITY_OR_COMPLETENESS")
    if bias_report.get("issued_at_utc") != now.isoformat():
        return _blocked("BIAS_TIMESTAMP_NOT_FROZEN_AT_EVALUATION")
    rankings = bias_report.get("relative_currency_rankings")
    if (not isinstance(rankings, Mapping) or set(rankings) != set(HORIZONS)):
        return _blocked("INVALID_SYNTHETIC_CURRENCY_RANKINGS")
    for rank in rankings.values():
        if not isinstance(rank, Mapping):
            return _blocked("INVALID_SYNTHETIC_CURRENCY_RANKINGS")
        if (rank.get("state") == "SINTETICO"
                and isinstance(rank.get("strongest"), str)
                and isinstance(rank.get("weakest"), str)
                and rank.get("strongest") in CURRENCIES
                and rank.get("weakest") in CURRENCIES):
            continue
        if (rank.get("state") == "AGUARDAR"
                and rank.get("strongest") is None
                and rank.get("weakest") is None):
            continue
        return _blocked("INVALID_SYNTHETIC_CURRENCY_RANKINGS")
    # This is a canonical, documentary schedule. Equality also rejects
    # omissions, reordered records, added events and fabricated release times.
    try:
        expected_calendar = (
            build_macro_event_exposure_v2_lab(at=now)
            if calendar_report["schema"] == CALENDAR_V2_SCHEMA
            else build_macro_event_exposure_lab(at=now)
        )
    except ValueError:
        return _blocked("CALENDAR_RESEARCH_NOT_AVAILABLE_AS_OF_TIME")
    if dict(calendar_report) != expected_calendar:
        return _blocked("CALENDAR_REPORT_NOT_REPRODUCIBLE")
    incoming = bias_report.get("rows")
    if (bias_report.get("pair_count") != len(OFFICIAL_PAIRS)
            or not isinstance(incoming, list)
            or len(incoming) != len(OFFICIAL_PAIRS)
            or any(not isinstance(row, Mapping) for row in incoming)):
        return _blocked("INVALID_28_PAIR_MATRIX")
    # Guard against duplicates and unhashable external data without exceptions.
    if (any(not isinstance(row.get("pair"), str)
            or row.get("pair") not in OFFICIAL_PAIRS for row in incoming)
            or len({row["pair"] for row in incoming}) != len(OFFICIAL_PAIRS)):
        return _blocked("DUPLICATE_OR_UNKNOWN_PAIR")
    bias_by_pair = {row["pair"]: row for row in incoming}
    event_by_key = {(row["pair"], row["horizon"]): row
                    for row in expected_calendar["fx_rows"]}
    joined = []
    for pair in OFFICIAL_PAIRS:
        source_row = bias_by_pair[pair]
        base, quote = split_pair(pair)
        periods = source_row.get("horizons")
        if (source_row.get("base") != base
                or source_row.get("quote") != quote
                or source_row.get("trade_authorized") is not False
                or not isinstance(periods, Mapping)
                or set(periods) != set(HORIZONS)):
            return _blocked("INVALID_BIAS_ROW_OR_HORIZONS")
        horizon_rows: dict[str, dict[str, Any]] = {}
        for horizon in HORIZONS:
            raw = periods[horizon]
            if not isinstance(raw, Mapping):
                return _blocked("MALFORMED_BIAS_HORIZON")
            strength = raw.get("relative_strength_hypothesis")
            macro = raw.get("macro_conditional_hypothesis")
            if (not isinstance(strength, str) or strength not in HYPOTHESES
                    or not isinstance(macro, str) or macro not in HYPOTHESES
                    or not isinstance(raw.get("comparison"), str)
                    or raw.get("comparison") not in COMPARISONS
                    or raw.get("comparison") != _expected_comparison(strength, macro)
                    or raw.get("operational_bias") != "AGUARDAR"
                    or raw.get("as_of_utc") != now.isoformat()
                    or not isinstance(raw.get("evidence_ready"), Mapping)
                    or set(raw["evidence_ready"]) != EVIDENCE_DIMENSIONS
                    or any(value is not False
                           for value in raw["evidence_ready"].values())):
                return _blocked("UNSAFE_OR_INCONSISTENT_BIAS_HYPOTHESIS")
            event = event_by_key[(pair, horizon)]
            horizon_rows[horizon] = {
                "relative_strength_hypothesis": strength,
                "macro_conditional_hypothesis": macro,
                "comparison": raw["comparison"],
                "event_exposures": deepcopy(event["event_exposures"]),
                "event_risk_status": event["risk_status"],
                "operational_bias": "AGUARDAR",
                "event_exposure_is_not_direction": True,
                "no_event_from_partial_calendar_is_not_no_risk": True,
                "windows_are_rolling_not_price_candles": True,
                "why_wait": ("Forca e macro sao hipoteses sinteticas; os "
                             "eventos catalogados nao esgotam o calendario "
                             "nem provam direcao, reacao ou preco de mercado."),
            }
        joined.append({"pair": pair, "base": base, "quote": quote,
                       "horizons": horizon_rows, "trade_authorized": False})
    out = _blocked("PARTIAL_CALENDAR_AND_SYNTHETIC_BIAS_NOT_TRADING")
    out.update({
        "state": "LAB_EXPLANATION_ONLY", "as_of_utc": now.isoformat(),
        "rows": joined, "pair_count": len(joined),
        "relative_currency_rankings": deepcopy(rankings),
        "curated_event_count": expected_calendar["curated_event_count"],
        "calendar_version": expected_calendar.get("calendar_version", "V1_20261103"),
        "event_exposure_windows_seconds": deepcopy(
            expected_calendar["rolling_windows"]),
        "bias_horizons": list(HORIZONS),
        "note": ("D1/W1/MN1 de vies e risco de eventos nas proximas "
                 "24h/7d/30d sao conceitos diferentes. "
                 "Eventos documentais nao significam calendario completo."),
    })
    return out


__all__ = ["SCHEMA", "HORIZONS", "build_bias_calendar_exposure_link_lab"]
