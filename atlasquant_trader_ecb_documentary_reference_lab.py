"""Two official-looking ECB EUR reference observations: document-only LAB arithmetic.

This is a *research calculation*, not an ECB API client, quote ingest,
historical receipt witness, D1 bias, OOS evaluator or broker feed.
A caller can forge the documents and timestamps: no result authenticates a source.
ECB publishes ~16:00 Europe central time on its working days; 18:00 UTC
is a deliberately later research gate across summer and winter, never
evidence of actual publication. No time-zone database is required.
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from decimal import Decimal, InvalidOperation
from math import log, isfinite
from typing import Any, Mapping

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair

SCHEMA = "ATLASQUANT_TRADER_ECB_DOCUMENTARY_G8_REFERENCE_LAB_V1"
SEVEN = frozenset(CURRENCIES) - {"EUR"}
PAGE = "https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html"
METHOD = "G8_TWO_ECB_EUR_REFERENCE_DATES_EXPOST_V1"
DOCUMENT_FIELDS = frozenset(("state", "date", "source_name", "source_page", "eur_quotes"))
PROVIDER = "European Central Bank (ECB)"
DOCUMENT_STATE = "LAB_PUBLIC_ECB_REFERENCE_DOCUMENT_REVIEW_CANDIDATE"


def _deny(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_ECB_DOCUMENT_REVIEW_REFUSED",
        "reason": reason, "original_eur_quotes": None, "pair_cross_reference_changes": {},
        "currency_reference_ranking": [], "real_currency_strength": None,
        "independent_spot_quotes_verified": 0, "original_bytes_custodied": False,
        "publication_time_independently_verified": False,
        "actual_historical_capture_attested": False,
        "real_predictive_accuracy_proven": False, "can_feed_live_radar": False,
        "can_feed_real_oos": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
    }


def _read_doc(raw: Any) -> tuple[date, dict[str, Decimal]] | str:
    if not isinstance(raw, Mapping) or set(raw) != DOCUMENT_FIELDS:
        return "Document contract missing or unexpected field"
    if (raw["state"] != DOCUMENT_STATE or raw["source_name"] != PROVIDER or
            raw["source_page"] != PAGE):
        return "Research document source/identity not admitted"
    try:
        day = date.fromisoformat(raw["date"])
        if raw["date"] != day.isoformat() or day.weekday() > 4:
            return "Date invalid, noncanonical, or weekend"
    except (ValueError, TypeError):
        return "Date not ISO or outside calendar"
    rates = raw["eur_quotes"]
    if not isinstance(rates, Mapping) or set(rates) != SEVEN:
        return "Exactly seven ECB EUR-denominated currencies required"
    output = {}
    for currency in SEVEN:
        value = rates[currency]
        if not isinstance(value, str) or not 1 <= len(value) <= 24:
            return "Rate must preserve official text precision"
        try:
            number = Decimal(value)
        except InvalidOperation:
            return "Invalid ECB reference rate"
        if not number.is_finite() or not Decimal("0.0001") <= number <= Decimal("100000"):
            return "ECB reference rate out of allowed numeric range"
        output[currency] = number
    return day, output


def compare_ecb_g8_documentary_reference_lab(
    previous: Any, current: Any, *, evaluated_at: datetime,
) -> dict[str, Any]:
    """Compare exact G8 documentary EUR references, never issue a bias."""
    if not isinstance(evaluated_at, datetime) or evaluated_at.tzinfo is None:
        raise ValueError("Research evaluation clock must include timezone")
    now = evaluated_at.astimezone(timezone.utc)
    a, b = _read_doc(previous), _read_doc(current)
    if isinstance(a, str):
        return _deny(a)
    if isinstance(b, str):
        return _deny(b)
    d0, r0 = a
    d1, r1 = b
    if not 1 <= (d1 - d0).days <= 5:
        return _deny("Observation dates must increase within a short research window")
    # 18:00 UTC is later than the usual ECB 16:00 central European release
    # in both summer and winter. This is NOT proof of an actual receipt.
    # Avoid ZoneInfo dependency on bare Windows installations.
    gate = datetime.combine(d1, time(18), tzinfo=timezone.utc)
    if now < gate.astimezone(timezone.utc):
        return _deny("Same-day documentary rate cannot be used before evening cutoff")
    zero = {**{c: Decimal("1") for c in ("EUR",)}, **r0}
    one = {**{c: Decimal("1") for c in ("EUR",)}, **r1}
    # Positive EUR/C change means C weakened vs EUR, not strengthened.
    changed = {c: log(float(one[c] / zero[c])) for c in CURRENCIES}
    if any(not isfinite(v) or abs(v) >= .3 for v in changed.values()):
        return _deny("Excessive reference move or nonfinite log return")
    mean = sum(changed.values()) / len(CURRENCIES)
    relative = {c: mean - changed[c] for c in CURRENCIES}
    crosses = {}
    direct = 0
    for pair in OFFICIAL_PAIRS:
        base, quote = split_pair(pair)
        old = zero[quote] / zero[base]
        new = one[quote] / one[base]
        direct_eur = "EUR" in (base, quote)
        direct += int(direct_eur)
        crosses[pair] = {
            "previous_implied_reference": str(round(old, 8)),
            "current_implied_reference": str(round(new, 8)),
            "reference_change_pct": round(float((new / old - 1) * 100), 6),
            "origin": ("EUR_ECB_REFERENCE_OR_INVERSE" if direct_eur
                       else "ALGEBRAIC_CROSS_FROM_SEVEN_EUR_QUOTES"),
            "independent_spot_quote": False, "trade_authorized": False,
        }
    ordered = sorted(CURRENCIES, key=lambda code: (-relative[code], code))
    return {
        "schema": SCHEMA, "state": "LAB_ECB_DOCUMENTARY_REFERENCE_MATH_ONLY",
        "method": METHOD, "previous_date": d0.isoformat(), "current_date": d1.isoformat(),
        "reference_publication_evening_gate_utc": gate.astimezone(timezone.utc).isoformat(),
        "source_attribution": "Source: ECB statistics. Derived arithmetic: AtlasQuant research.",
        "original_eur_quotes": {
            d0.isoformat(): {c: str(r0[c]) for c in sorted(SEVEN)},
            d1.isoformat(): {c: str(r1[c]) for c in sorted(SEVEN)},
        },
        "currency_reference_log_change_bp": {
            c: round(10000 * relative[c], 6) for c in CURRENCIES
        },
        "currency_reference_ranking": ordered,
        "pair_cross_reference_changes": crosses,
        "official_eur_reference_legs": len(SEVEN),
        "algebraically_derived_non_eur_crosses": len(OFFICIAL_PAIRS)-direct,
        "independent_spot_quotes_verified": 0,
        "original_bytes_custodied": False,
        "publication_time_independently_verified": False,
        "actual_historical_capture_attested": False,
        "historical_revision_vintage_attested": False,
        "real_currency_strength": None,
        "real_predictive_accuracy_proven": False,
        "can_feed_live_radar": False, "can_feed_real_oos": False,
        "trade_authorized": False, "worker_enabled": False, "scheduler_enabled": False,
        "why_not": "Two public documentary reference dates, not independently captured "
                   "live spot quotes or an ex-ante forecast. Crosses share seven "
                   "underlying EUR legs and therefore cannot independently corroborate "
                   "triangular consistency or establish trading accuracy.",
    }


__all__ = ["SCHEMA", "compare_ecb_g8_documentary_reference_lab"]
