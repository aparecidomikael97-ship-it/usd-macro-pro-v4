"""G8 28-pair observed daily reference moves, 2-4 November 2026, LAB.

Seven EUR-based rates for each date are manually transcribed from Banca
d'Italia's official daily reference pages. They are NOT original HTTP bytes,
an authenticated point-in-time vintage, a broker trade quote, an M15 price,
or a forecast of future market movement. No trading, worker or ranking.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Any

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_trader_ecb_g8_reference_day_lab import EUR_QUOTES as NOV_04

SCHEMA = "ATLASQUANT_TRADER_ECB_G8_3DAY_OBSERVED_REFERENCE_MOVES_LAB_V1"
SOURCE_PREFIX = "https://www.bancaditalia.it/compiti/operazioni-cambi/cambio/"
REFS = {
    "2026-11-02": {
        "EUR": "1", "USD": "1.1216", "JPY": "177.10",
        "GBP": "0.83580", "CHF": "0.9193", "AUD": "1.6004",
        "CAD": "1.5673", "NZD": "1.9934",
    },
    "2026-11-03": {
        "EUR": "1", "USD": "1.1179", "JPY": "176.95",
        "GBP": "0.83358", "CHF": "0.9166", "AUD": "1.6007",
        "CAD": "1.5623", "NZD": "1.9876",
    },
    "2026-11-04": dict(NOV_04),
}
DAYS = tuple(REFS)
SOURCE_PAGES = {
    d: SOURCE_PREFIX + "cambi_rif_" + d.replace("-", "") + "/"
    for d in DAYS
}
NEXT_DAY_BOUND = datetime(2026, 11, 5, tzinfo=timezone.utc)
MOVE_PRECISION = Decimal("0.0001")
RATE_PRECISION = Decimal("0.00000001")


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "research_as_of_utc": None, "observed_dates": list(DAYS),
        "official_daily_page_urls": SOURCE_PAGES,
        "origin": "OFFICIAL_PAGE_VALUES_MANUALLY_TRANSCRIBED_UNATTESTED",
        "original_http_bytes_obtained": False,
        "original_source_sha256": None,
        "publication_instant_attested": False,
        "point_in_time_vintage_verified": False,
        "independent_broker_m15_price_verified": False,
        "executable_bid_ask_verified": False,
        "historical_backtest_eligible": False,
        "historical_predictive_accuracy_verified": False,
        "is_predictive_fx_bias": False,
        "currency_count": 0, "pair_count": 0,
        "reference_observation_count": 0,
        "observed_interval_count": 0,
        "currency_reference_values": {},
        "pairs": [],
        "currency_strength_rank": None,
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "trade_authorized": False, "can_feed_live_radar": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "publishable": False, "external_http_requests": 0,
        "new_cost_brl": 0,
    }


def _fixed(value: Decimal, precision: Decimal) -> str:
    return format(value.quantize(precision, rounding=ROUND_HALF_EVEN), "f")


def build_ecb_g8_three_day_reference_moves_lab(*, as_of_utc: Any) -> dict[str, Any]:
    """Compute only observed 02->03, 03->04 and 02->04 reference returns."""
    out = _blocked("INVALID_OR_PREMATURE_RESEARCH_AS_OF")
    if (not isinstance(as_of_utc, datetime)
            or as_of_utc.tzinfo is None or as_of_utc.utcoffset() is None):
        return out
    stamp = as_of_utc.astimezone(timezone.utc)
    if stamp < NEXT_DAY_BOUND:
        return out
    if (tuple(sorted(REFS)) != DAYS
            or DAYS != ("2026-11-02", "2026-11-03", "2026-11-04")
            or len(OFFICIAL_PAIRS) != 28
            or len({frozenset(split_pair(x)) for x in OFFICIAL_PAIRS}) != 28
            or any(set(x) != set(CURRENCIES) for x in REFS.values())):
        return _blocked("G8_REGISTRY_OR_SOURCE_DAY_INCOMPLETE")
    try:
        rates = {d: {k: Decimal(v) for k, v in row.items()}
                 for d, row in REFS.items()}
        if any(not x.is_finite() or x <= 0 for day in rates.values()
               for x in day.values()):
            return _blocked("INVALID_REFERENCE_INPUT")
        if any(day["EUR"] != 1 for day in rates.values()):
            return _blocked("EUR_BASE_NOT_ONE")
        intervals = (("2026-11-02", "2026-11-03"),
                     ("2026-11-03", "2026-11-04"),
                     ("2026-11-02", "2026-11-04"))
        pairs = []
        for pair in OFFICIAL_PAIRS:
            base, quote = split_pair(pair)
            # ECB units per EUR; quote/base gives quote units per one base.
            exact = {d: rates[d][quote] / rates[d][base] for d in DAYS}
            derived = {d: _fixed(exact[d], RATE_PRECISION) for d in DAYS}
            moves = {}
            for first, last in intervals:
                # Calculate from unrounded ratios; round for display only.
                pct = (exact[last] / exact[first] - Decimal("1")) * 100
                moves[f"{first}_to_{last}"] = _fixed(pct, MOVE_PRECISION)
            pairs.append({
                "pair": pair, "base": base, "quote": quote,
                "quoted_unit": f"{quote}_PER_1_{base}",
                "daily_references": derived,
                "observed_reference_moves_percent": moves,
                "moves_are_retrospective_not_predictions": True,
                "historical_signal_was_recorded_pre_move": False,
                "independent_execution_price_verified": False,
                "currency_strength_rank": None,
                "fx_bias": None, "trade_authorized": False,
                "D1": "AGUARDAR", "W1": "AGUARDAR",
            })
        out.update({
            "state": "LAB_ECB_G8_3DAY_OBSERVED_REFERENCE_MOVES_ONLY",
            "reason": "OFFICIAL_DAILY_REFERENCE_NOT_BROKER_PRICE_OR_EX_ANTE_BIAS",
            "research_as_of_utc": stamp.isoformat(),
            "currency_count": 8,
            "pair_count": len(pairs),
            "reference_observation_count": 8 * len(DAYS),
            "observed_interval_count": len(OFFICIAL_PAIRS) * len(intervals),
            "currency_reference_values": {d: dict(row) for d, row in REFS.items()},
            "pairs": pairs,
        })
        return out
    except (ValueError, ArithmeticError, OverflowError):
        return _blocked("INVALID_REFERENCE_ARITHMETIC")


__all__ = ["SCHEMA", "REFS", "SOURCE_PAGES",
           "build_ecb_g8_three_day_reference_moves_lab"]
