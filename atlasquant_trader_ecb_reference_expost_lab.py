"""LAB: ECB euro FX reference rates -> G8 relative movement, EX-POST ONLY.

Passive CSV research adapter for *synthetic* ECB-shaped input. No HTTP,
provider credential, trade execution, publication, live bias, P&L or forecasting.
ECB daily reference rates are informative, generally published around 16:00
Central European local time; they are not tradable spot closing quotes.
The ECB disseminates EUR base: 1 EUR = N units of foreign currency C.
Sources: https://data.ecb.europa.eu/help/api/data-examples
         https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html
"""
from __future__ import annotations

import csv
from datetime import date, datetime, time, timezone, timedelta
from io import StringIO
from math import isfinite, log
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair

SCHEMA = "ATLASQUANT_ECB_G8_REFERENCE_EXPOST_LAB_V1"
REQUIRED = ("FREQ", "CURRENCY", "CURRENCY_DENOM", "EXR_TYPE",
            "EXR_SUFFIX", "TIME_PERIOD", "OBS_VALUE")
ECB_QUOTES = frozenset(CURRENCIES) - {"EUR"}
METHOD = "ECB_EUR_REFERENCE_RATE_CENTERED_LOG_CHANGE_LAB_V1"
MAX_CSV_BYTES = 20_000
# A conservative research clock boundary, NOT the actual ECB release instant.
# ECB says "usually around 16:00" Europe Central, with holidays and exceptions.
HYPOTHETICAL_NOT_BEFORE_HOUR_LOCAL = 18


def _instant(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    return value.astimezone(timezone.utc)


def _reject(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_REFUSED_UNVERIFIED_ECB_REFERENCE",
        "reason": reason, "eur_quoted_rates": {},
        "currency_relative_moves_bp": {}, "pair_reference_moves_bp": {},
        "actual_ecb_publication_proven": False,
        "independent_spot_quotes_verified": 0,
        "forecasts_issued": 0,
        "live_bias_validated": False, "accuracy_proven": False,
        "feed_enabled": False, "worker_enabled": False,
        "scheduler_enabled": False, "trade_authorized": False,
    }


def describe_ecb_g8_reference_change_lab(
    payload: Any, *, previous: str, current: str,
    declared_captured_at: datetime, evaluated_at: datetime,
) -> dict[str, Any]:
    """Compare TWO synthetic ECB reference days, never issue a forecast.

    The capture clock is caller-supplied and NOT immutable evidence; a
    hindsight CSV plus a fabricated capture cannot prove historical
    availability for an out-of-sample test.
    """
    captured = _instant(declared_captured_at)
    now = _instant(evaluated_at)
    if captured is None or now is None:
        raise ValueError("Capture and evaluation clocks must include timezone")
    if captured > now:
        return _reject("Declared capture lies in the future")
    if not isinstance(payload, Mapping) or payload.get("state") != "LAB_SYNTHETIC_ECB_CSV":
        return _reject("Only explicitly synthetic, offline ECB-shaped CSV is permitted")
    try:
        prev_date = date.fromisoformat(previous)
        curr_date = date.fromisoformat(current)
    except (ValueError, TypeError):
        return _reject("Observation dates must be ISO calendar dates")
    if (prev_date >= curr_date or
            (curr_date - prev_date).days > 10 or
            any(d.weekday() >= 5 for d in (prev_date, curr_date)) or
            curr_date > captured.date()):
        return _reject("Missing, reversed, weekend or future observation dates")
    # This is an intentionally conservative lower bound only. Real
    # historical publication/receipt must be independently attested.
    publication_clock_hypothesis = datetime.combine(
        curr_date, time(HYPOTHETICAL_NOT_BEFORE_HOUR_LOCAL),
        tzinfo=ZoneInfo("Europe/Frankfurt")).astimezone(timezone.utc)
    if captured < publication_clock_hypothesis:
        return _reject("Capture precedes conservative ECB publication-time hypothesis")
    text = payload.get("csv_text")
    if (not isinstance(text, str) or not 1 <= len(text.encode("utf-8")) <= MAX_CSV_BYTES
            or "\x00" in text):
        return _reject("CSV is missing or too large")
    try:
        reader = csv.DictReader(StringIO(text.lstrip("\ufeff")))
        if reader.fieldnames is None or not set(REQUIRED).issubset(reader.fieldnames):
            return _reject("Missing required ECB SDMX CSV column")
        if len(set(reader.fieldnames)) != len(reader.fieldnames):
            return _reject("Duplicate CSV column")
        rows = list(reader)
    except (csv.Error, UnicodeError, ValueError):
        return _reject("Invalid ECB-shaped CSV")
    if len(rows) != 2 * len(ECB_QUOTES):
        return _reject("Need exactly two complete days of seven EUR quotes")
    quotes: dict[str, dict[str, float]] = {previous: {}, current: {}}
    for row in rows:
        if not isinstance(row, Mapping) or None in row:
            return _reject("Malformed CSV row")
        d, currency = row.get("TIME_PERIOD"), row.get("CURRENCY")
        if (d not in quotes or currency not in ECB_QUOTES
                or row.get("FREQ") != "D"
                or row.get("CURRENCY_DENOM") != "EUR"
                or row.get("EXR_TYPE") != "SP00"
                or row.get("EXR_SUFFIX") != "A"):
            return _reject("Unexpected series, denomination or date")
        if "KEY" in row and row["KEY"] not in (None, "", f"D.{currency}.EUR.SP00.A"):
            return _reject("SDMX series key contradicts currency metadata")
        if currency in quotes[d]:
            return _reject("Duplicate observation cannot be used")
        try:
            val = float(row.get("OBS_VALUE") or "")
        except (TypeError, ValueError, OverflowError):
            return _reject("Non-numeric ECB observation")
        if not isfinite(val) or not 0 < val < 1_000_000:
            return _reject("Non-finite, zero or invalid ECB observation")
        quotes[d][currency] = val
    if any(set(rates) != ECB_QUOTES for rates in quotes.values()):
        return _reject("Incomplete set of currencies per date")
    delta = {c: log(quotes[current][c] / quotes[previous][c])
             for c in ECB_QUOTES}
    if any(not isfinite(z) or abs(z) > 0.3 for z in delta.values()):
        return _reject("Excessive reference movement needs separate investigation")
    # x_EUR - x_C = log[(EUR/C)_today / (EUR/C)_previous];
    # center all 8 values to avoid arbitrary "strength of one currency".
    eur = sum(delta.values()) / len(CURRENCIES)
    fx = {"EUR": eur}
    for c in ECB_QUOTES:
        fx[c] = eur - delta[c]
    if abs(sum(fx.values())) > 1e-10:
        return _reject("Centered G8 consistency invariant failed")
    ref = {}
    directly_eur_quoted = set()
    for pair in OFFICIAL_PAIRS:
        base, quote = split_pair(pair)
        directly_eur = base == "EUR" or quote == "EUR"
        if directly_eur:
            directly_eur_quoted.add(pair)
        ref[pair] = {
            "relative_reference_change_bp": round(10_000 * (fx[base] - fx[quote]), 6),
            "origin": ("DERIVED_FROM_ECB_EUR_REFERENCE_QUOTES"
                       if not directly_eur else "EUR_QUOTE_REFERENCE_NOT_SPOT_CLOSE"),
            "verified_independent_spot_quote": False,
            "forecast": False, "trade_authorized": False,
        }
    rank = sorted(CURRENCIES, key=lambda c: (-fx[c], c))
    return {
        "schema": SCHEMA, "state": "LAB_SYNTHETIC_ECB_EXPOST_ONLY",
        "method": METHOD, "previous_date": previous, "current_date": current,
        "hypothetical_publication_not_before_utc": publication_clock_hypothesis.isoformat(),
        "declared_captured_at_utc": captured.isoformat(),
        "declared_capture_independently_attested": False,
        "actual_ecb_publication_proven": False,
        "source_attribution": "BCE/ECB; taxas de referência (dados sintéticos nesta demonstração)",
        "source_url": "https://data.ecb.europa.eu/help/api/data-examples",
        "ecb_reference_rates_informational_only": True,
        "eur_quoted_rates": quotes,
        "currency_relative_moves_bp": {c: round(10_000 * fx[c], 6) for c in CURRENCIES},
        "currency_expost_ranking_not_a_prediction": rank,
        "pair_reference_moves_bp": ref,
        "observed_ecb_eur_reference_series": len(directly_eur_quoted),
        "algebraically_derived_other_pairs": len(OFFICIAL_PAIRS) - len(directly_eur_quoted),
        "independent_spot_quotes_verified": 0,
        "real_historical_data_verified": False,
        "future_return_backtested": False,
        "forecasts_issued": 0, "live_bias_validated": False,
        "accuracy_proven": False,
        "feed_enabled": False, "worker_enabled": False,
        "scheduler_enabled": False, "trade_authorized": False,
        "why_not": "ECB EUR reference changes are historical cross-reference arithmetic,"
                   " not trading prices, real-time strength forecasts or OOS evidence.",
    }


__all__ = ["SCHEMA", "describe_ecb_g8_reference_change_lab"]
