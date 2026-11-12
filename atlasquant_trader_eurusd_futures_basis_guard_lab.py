"""LAB-only USD/EUR rate-futures quotation and basis comparability guard.

CME ZQ has a monthly average overnight-rate underlying; Eurex FST3 has a
three-month compounded €STR underlying. Even authenticated quoted prices
would not be a normalized policy-expectations differential without a proven
economic mapping, liquidity and publication provenance. No HTTP or trades.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import re
from typing import Any

SCHEMA = "ATLASQUANT_TRADER_EURUSD_FUTURES_BASIS_GUARD_LAB_V1"
RESEARCH_VISIBLE_FROM_UTC = datetime(2026, 11, 11, tzinfo=timezone.utc)
MAX_CAPTURE_DELAY = timedelta(hours=24)
MAX_CURRENT_AGE = timedelta(days=3)
MIN_VINTAGE_GAP = timedelta(hours=24)
MAX_VINTAGE_GAP = timedelta(days=14)
_MONTH = re.compile(r"\d{4}-(0[1-9]|1[0-2])\Z")
_SHA = re.compile(r"[a-f0-9]{64}\Z")

PRODUCTS = {
    "USD": {"code": "ZQ", "underlying": "30_DAY_AVERAGE_EFFR",
            "source": "https://www.cmegroup.com/markets/interest-rates/stirs/30-day-federal-fund"},
    "EUR": {"code": "FST3", "underlying": "THREE_MONTH_COMPOUNDED_ESTR",
            "source": "https://www.eurex.com/ex-en/markets/int/mon/3m-euro-str-futures"},
}


@dataclass(frozen=True)
class RateFuturesQuoteClaim:
    currency: str
    product_code: str
    delivery_month: str
    published_at_utc: datetime
    captured_at_utc: datetime
    futures_price_index: str
    session_volume: int
    source_sha256_claim: str


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _price(value: Any) -> Decimal | None:
    if not isinstance(value, str) or not 1 <= len(value) <= 24:
        return None
    try:
        price = Decimal(value)
    except InvalidOperation:
        return None
    return price if price.is_finite() and Decimal("50") <= price <= Decimal("150") else None


def _blocked(state: str, reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": state, "reason": reason,
        "as_of_utc": None, "underlying_basis_different": True,
        "quote_rows": {}, "eurusd_normalized_differential_change_bps": None,
        "eurusd_directional_bias": None, "calibrated_direction_probability": None,
        "publisher_bytes_independently_archived": False,
        "licensed_data_redistribution_verified": False,
        "original_publication_timestamps_independently_attested": False,
        "cross_currency_rate_basis_normalized": False,
        "market_data_authenticated": False,
        "usable_as_policy_expectations_vintage": False,
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "trade_authorized": False, "publishable": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "http_requests": 0, "file_writes": 0, "new_cost_brl": 0,
    }


def _inspect_pair_of_claims(raw: Any, currency: str, asof: datetime) -> dict[str, Any]:
    unavailable = {"status": "FUTURES_QUOTE_EVIDENCE_UNAVAILABLE", "index_implied_rate_change_bps_claim": None}
    if not isinstance(raw, (tuple, list)) or len(raw) != 2:
        return unavailable
    a, b = raw
    if not isinstance(a, RateFuturesQuoteClaim) or not isinstance(b, RateFuturesQuoteClaim):
        return unavailable
    p = PRODUCTS[currency]
    if any(x.currency != currency or x.product_code != p["code"]
           or not isinstance(x.delivery_month, str) or _MONTH.fullmatch(x.delivery_month) is None
           or not isinstance(x.source_sha256_claim, str) or _SHA.fullmatch(x.source_sha256_claim) is None
           or type(x.session_volume) is not int or x.session_volume <= 0
           for x in (a, b)):
        return unavailable
    if a.delivery_month != b.delivery_month or a.source_sha256_claim == b.source_sha256_claim:
        return unavailable
    # This is only a coarse month check; exact product expiry still requires
    # independently verified contract-specific settlement calendars.
    if b.delivery_month < asof.strftime("%Y-%m"):
        return unavailable
    old_pub, new_pub = _utc(a.published_at_utc), _utc(b.published_at_utc)
    old_cap, new_cap = _utc(a.captured_at_utc), _utc(b.captured_at_utc)
    if any(x is None for x in (old_pub, new_pub, old_cap, new_cap)):
        return unavailable
    if (not old_pub <= old_cap < new_pub <= new_cap <= asof
            or old_cap - old_pub > MAX_CAPTURE_DELAY
            or new_cap - new_pub > MAX_CAPTURE_DELAY
            or not MIN_VINTAGE_GAP <= new_pub - old_pub <= MAX_VINTAGE_GAP
            or asof - new_cap > MAX_CURRENT_AGE):
        return unavailable
    old_price, new_price = _price(a.futures_price_index), _price(b.futures_price_index)
    if old_price is None or new_price is None:
        return unavailable
    # Both quote as 100 minus futures underlying rate.  This is a movement
    # in each distinct futures reference rate, NOT a policy-rate forecast.
    move_bps = (old_price - new_price) * 100
    return {
        "status": "SELF_CLAIMED_ACTIVE_FUTURES_QUOTES_NOT_AUTHENTICATED",
        "index_implied_rate_change_bps_claim": str(move_bps),
        "contract_delivery_month": b.delivery_month,
        "contract_underlying": p["underlying"],
        "publisher_url": p["source"],
        "new_claimed_publication_utc": new_pub.isoformat(),
        "new_claimed_capture_utc": new_cap.isoformat(),
    }


def inspect_eurusd_futures_basis_guard_lab(*, claims_by_currency: Any, as_of_utc: Any) -> dict[str, Any]:
    """Check synthetic individual futures moves; never compute USD-EUR policy differential."""
    now = _utc(as_of_utc)
    if (now is None or not isinstance(claims_by_currency, dict)
            or set(claims_by_currency) != set(PRODUCTS)):
        return _blocked("LAB_INVALID_INPUT", "INVALID_CLOCK_OR_USD_EUR_CLAIMS")
    if now < RESEARCH_VISIBLE_FROM_UTC:
        return _blocked("LAB_RESEARCH_NOT_VISIBLE_AS_OF", "NO_HISTORICAL_RESEARCH_PROOF")
    rows = {c: _inspect_pair_of_claims(claims_by_currency[c], c, now) for c in PRODUCTS}
    out = _blocked("LAB_FUTURES_BASIS_UNNORMALIZED_NO_GO", "MONTHLY_AVERAGE_VERSUS_THREE_MONTH_COMPOUNDING")
    out.update(as_of_utc=now.isoformat(), quote_rows=rows)
    return out
