"""D1/W1/MN1 historical G8 reference matrix, explicitly not market bias.

The ECB daily reference series arrives as caller-supplied XML bytes, is not
origin-authenticated here and is not an executable FX bid/ask feed. Every
ranking is ex-post and all 28 operational pair biases remain AGUARDAR.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from atlasquant_ecb_g8_reference_lab import analyze_ecb_reference_xml
from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair

SCHEMA = "ATLASQUANT_TRADER_ECB_THREE_HORIZON_REFERENCE_MATRIX_LAB_V1"
HORIZONS = ("D1", "W1", "MN1")
CAUSAL_GAPS = (
    "MACROECONOMICS_UNVERIFIED", "MICROECONOMICS_UNVERIFIED",
    "GEOPOLITICS_UNVERIFIED", "NEWS_AND_CALENDAR_NOT_REALTIME_VERIFIED",
    "INDEPENDENT_SPOT_PRICE_NOT_VERIFIED", "COUNTEREVIDENCE_NOT_REVIEWED",
)


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "pair_rows": [], "currency_ranking_by_horizon": {},
        "horizon_top10_reference_only": {},
        "pair_count": 0, "operational_bias": "AGUARDAR",
        "ecb_original_bytes_authenticated": False,
        "independent_fx_price_verified": False,
        "macro_causation_verified": False,
        "calendar_and_news_realtime_verified": False,
        "three_daily_updates_verified": False,
        "prediction_backtested_oos": False,
        "can_feed_live_radar": False, "publishable": False,
        "trade_authorized": False, "worker_enabled": False,
        "scheduler_enabled": False, "external_http_requests": 0,
        "new_cost_brl": 0,
    }


def build_ecb_three_horizon_reference_matrix_lab(
    xml_data: Any, *, at: datetime,
) -> dict[str, Any]:
    """Compare historical G8 euro fixes, never forecast currency strength."""
    if not isinstance(at, datetime) or at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("Timezone-aware evaluation clock required")
    now = at.astimezone(timezone.utc)
    source = analyze_ecb_reference_xml(xml_data, now=now)
    if source.get("state") != "RESEARCH_ONLY":
        return _blocked("ECB_HISTORY_REFUSED_" + source.get("reason", "UNKNOWN"))
    if (source.get("complete_pairs") != len(OFFICIAL_PAIRS)
            or source.get("direct_eur_fixes") != 7
            or source.get("derived_non_eur_crosses") != 21
            or source.get("provider_authenticated") is not False
            or source.get("publishable") is not False
            or source.get("trade_authorized") is not False):
        return _blocked("UNSAFE_ECB_SOURCE_CLASSIFICATION")

    ranks = {}
    top10 = {}
    horizon_windows = {}
    for horizon in HORIZONS:
        window = source["research_windows"].get(horizon)
        if not isinstance(window, dict) or window.get("state") not in (
                "RESEARCH_ONLY", "INSUFFICIENT_REFERENCE_HISTORY"):
            return _blocked("MISSING_OR_UNSAFE_REFERENCE_WINDOW")
        horizon_windows[horizon] = window
        if window["state"] == "RESEARCH_ONLY":
            order = window["currency_order"]
            scores = window["currency_strength_log_pp"]
            returns = window["pair_returns_pct"]
            if (len(order) != len(CURRENCIES)
                    or set(order) != set(CURRENCIES)
                    or set(scores) != set(CURRENCIES)
                    or set(returns) != set(OFFICIAL_PAIRS)):
                return _blocked("INCOMPLETE_REFERENCE_STRENGTH_WINDOW")
            ranks[horizon] = [{
                "currency": currency, "rank": i + 1,
                "relative_log_change_percentage_points": scores[currency],
                "observed_only_not_macro_cause": True,
            } for i, currency in enumerate(order)]
            top10[horizon] = list(window["top10"])
        else:
            ranks[horizon] = []
            top10[horizon] = []

    pairs = []
    for pair in OFFICIAL_PAIRS:
        base, quote = split_pair(pair)
        frames = {}
        for horizon in HORIZONS:
            window = horizon_windows[horizon]
            valid = window["state"] == "RESEARCH_ONLY"
            change = window["pair_returns_pct"].get(pair) if valid else None
            if valid:
                observed = ("BASE_OUTPERFORMED_IN_REFERENCE" if change > 0 else
                            "QUOTE_OUTPERFORMED_IN_REFERENCE" if change < 0 else
                            "UNCHANGED_IN_REFERENCE")
            else:
                observed = "NO_SUFFICIENT_REFERENCE_HISTORY"
            frames[horizon] = {
                "research_state": ("EXPOST_REFERENCE_ONLY" if valid else
                                   "INSUFFICIENT_REFERENCE_HISTORY"),
                "observed_reference_change_pct": change,
                "historical_reference_relation": observed,
                "start_reference_date": window.get("start_reference_date"),
                "end_reference_date": window.get("end_reference_date"),
                "actual_elapsed_calendar_days": window.get("calendar_days_between_fixes"),
                "reason_for_currency_strength": "NAO_COMPROVADA",
                "causal_evidence_gaps": list(CAUSAL_GAPS),
                "operational_bias": "AGUARDAR",
                "reference_is_executable_quote": False,
                "trade_authorized": False,
            }
        pairs.append({
            "pair": pair, "base": base, "quote": quote,
            "horizons": frames, "trade_authorized": False,
        })

    result = _blocked("ECB_IS_DOCUMENTARY_EXPOST_NOT_LIVE_OR_CAUSAL")
    result.update({
        "state": "LAB_EXPOST_REFERENCE_MATRIX_ONLY",
        "as_of_utc": now.isoformat(),
        "reference_date": source["reference_date"],
        "reference_age_days": source["reference_age_days"],
        "reference_age_over_four_days": source["reference_age_days"] > 4,
        "reference_source_url_documentary": source["official_documentation_url"],
        "reference_inputs_are_caller_supplied": True,
        "currency_count": len(CURRENCIES), "pair_count": len(pairs),
        "horizon_count": len(HORIZONS),
        "direct_eur_reference_legs_per_day": 7,
        "derived_non_eur_crosses": 21,
        "all_pairs_algebraically_derived_from_eur_fixes": True,
        "rolling_calendar_month_research_days": 30,
        "currency_ranking_by_horizon": ranks,
        "horizon_top10_reference_only": top10,
        "pair_rows": pairs,
        "note": ("Ranking passado de referencias BCE, nao ranking de fundamentos, "
                 "noticia em tempo real, previsao, spread, ordem ou acerto ")
                 + "comprovado. Explicacao macro/geo e preco independente pendentes.",
    })
    return result


__all__ = ["SCHEMA", "HORIZONS", "build_ecb_three_horizon_reference_matrix_lab"]
