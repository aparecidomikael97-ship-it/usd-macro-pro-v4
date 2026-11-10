"""Offline SR3/ESR aligned IMM-quarter *claims* audit, never FX signals.

CME three-month SOFR (SR3) and euro STR (ESR) share IMM accrual
calendar, but secured vs unsecured benchmarks and currency basis differ.
No source bytes, licenses, trades or timestamps are independently attested.
No I/O, network, order or production integration is performed.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import re
from typing import Any

from atlasquant_trader_cme_settlement_release_gate_lab import (
    inspect_cme_settlement_release_gate_lab,
)

SCHEMA = "ATLASQUANT_TRADER_EURUSD_SR3_ESR_IMM_QUARTER_LAB_V1"
RESEARCH_VISIBLE_FROM_UTC = datetime(2026, 11, 11, tzinfo=timezone.utc)
CME_PRODUCT_SLATE_TRADE_DATE = date(2026, 10, 30)
# Product-level PRELIMINARY figures cited from CME's page in 2026-11-10
# research. Never attribute these totals to any named futures delivery.
PRELIMINARY_PRODUCT_TOTALS = {
    "SR3": {"volume": 4735231, "open_interest": 13040799},
    "ESR": {"volume": 185, "open_interest": 21169},
}
PRODUCTS = {
    "USD": {"code": "SR3", "benchmark": "SOFR_SECURED_OVERNIGHT_3M"},
    "EUR": {"code": "ESR", "benchmark": "ESTR_UNSECURED_OVERNIGHT_3M"},
}
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_MONTH = re.compile(r"\d{4}-(?:03|06|09|12)\Z")


@dataclass(frozen=True)
class QuarterFuturesQuoteClaim:
    currency: str
    product_code: str
    reference_start_month: str  # e.g. "2026-09", *not* 2026-12 final settlement
    trade_date: date
    observed_at_utc: datetime
    published_at_utc: datetime
    captured_at_utc: datetime
    futures_price_index: str
    contract_session_volume: int | None
    source_sha256_claim: str
    quote_kind: str = "TRADE"  # or SETTLEMENT (which need not be a trade)
    settlement_publication_channel: str = "UNVERIFIED"


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _price(value: Any) -> Decimal | None:
    if not isinstance(value, str) or not 1 <= len(value) <= 24:
        return None
    try:
        d = Decimal(value)
    except InvalidOperation:
        return None
    return d if d.is_finite() and Decimal("50") <= d <= Decimal("150") else None


def _third_wednesday(year: int, month: int) -> date:
    # weekday() Monday=0; Wednesday=2. First Wednesday is day 1..7.
    first = date(year, month, 1)
    day = 1 + ((2 - first.weekday()) % 7) + 14
    return date(year, month, day)


def imm_quarter_window(reference_start_month: Any) -> tuple[date, date] | None:
    """Start and end IMM dates for a *quarterly* SR3/ESR contract.

    This is a month-level calendar validation, not independent verification
    of exchange-specific holiday variations or executable last-trade time.
    """
    if not isinstance(reference_start_month, str) or _MONTH.fullmatch(reference_start_month) is None:
        return None
    year, month = map(int, reference_start_month.split("-"))
    if not 2000 <= year <= 2099:
        return None
    end_year = year + (month + 2) // 12
    end_month = ((month + 2) % 12) + 1
    try:
        return _third_wednesday(year, month), _third_wednesday(end_year, end_month)
    except ValueError:
        return None


def _blocked(state: str, reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": state,
        "reason": reason,
        "as_of_utc": None,
        "cme_product_slate_trade_date": CME_PRODUCT_SLATE_TRADE_DATE.isoformat(),
        "cme_product_slate_type": "PRELIMINARY_PRODUCT_LEVEL_NOT_CONTRACT_LEVEL",
        "cme_product_slate_volumes": PRELIMINARY_PRODUCT_TOTALS,
        "cme_product_slate_proves_contract_liquidity": False,
        "same_imm_reference_quarter_documented": True,
        "same_benchmark_or_policy_rate": False,
        "benchmark_basis_adjusted": False,
        "evidence_by_currency": {},
        "both_claimed_quotes_same_quarter": False,
        "claimed_sofr_minus_estr_change_bps": None,
        "independent_issuer_bytes_archived": False,
        "quote_timestamps_independently_attested": False,
        "licensed_reuse_verified": False,
        "contract_specific_liquidity_attested": False,
        "forward_fx_basis_verified": False,
        "forward_exchange_rate_verified": False,
        "point_in_time_backtest_ready": False,
        "eurusd_spot_direction": None,
        "calibrated_direction_probability": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False,
        "publishable": False,
        "scheduler_enabled": False,
        "http_requests": 0,
        "file_writes": 0,
        "new_cost_brl": 0,
    }


def _check_currency_claims(items: Any, currency: str, now: datetime) -> dict[str, Any]:
    failure = {"status": "CLAIMS_INVALID_OR_UNAVAILABLE", "claimed_underlying_rate_change_bps": None}
    if not isinstance(items, (list, tuple)) or len(items) != 2 or not all(
        isinstance(x, QuarterFuturesQuoteClaim) for x in items
    ):
        return failure
    a, b = items
    spec = PRODUCTS[currency]
    if (any(x.currency != currency or x.product_code != spec["code"] or
            type(x.trade_date) is not date or x.quote_kind not in {"TRADE", "SETTLEMENT"} or
            type(x.contract_session_volume) not in {int, type(None)} or
            (x.contract_session_volume is not None and x.contract_session_volume < 0) or
            not isinstance(x.source_sha256_claim, str) or
            _SHA256.fullmatch(x.source_sha256_claim) is None or
            _price(x.futures_price_index) is None for x in (a, b))):
        return failure
    if (a.reference_start_month != b.reference_start_month or
            a.source_sha256_claim == b.source_sha256_claim or
            a.trade_date >= b.trade_date):
        return failure
    window = imm_quarter_window(a.reference_start_month)
    if window is None:
        return failure
    start, end = window
    # Start-month code can be EARLIER than observation date while contract
    # accrues: e.g. Sep-2026 SR3/ESR is active in November 2026.
    if now.date() >= end or any(x.trade_date >= end for x in (a, b)):
        return failure
    old_obs, old_pub, old_cap = (_utc(a.observed_at_utc), _utc(a.published_at_utc), _utc(a.captured_at_utc))
    new_obs, new_pub, new_cap = (_utc(b.observed_at_utc), _utc(b.published_at_utc), _utc(b.captured_at_utc))
    if any(x is None for x in (old_obs, old_pub, old_cap, new_obs, new_pub, new_cap)):
        return failure
    if (not old_obs <= old_pub <= old_cap < new_obs <= new_pub <= new_cap <= now or
            old_obs.date() != a.trade_date or new_obs.date() != b.trade_date or
            old_cap - old_pub > timedelta(hours=36) or
            new_cap - new_pub > timedelta(hours=36) or
            not timedelta(hours=12) <= new_obs - old_obs <= timedelta(days=14) or
            now - new_cap > timedelta(days=3)):
        return failure
    if any(x.quote_kind == "TRADE" and (x.contract_session_volume is None or x.contract_session_volume <= 0)
           for x in (a, b)):
        return failure
    # A publicly viewed end-of-day settlement has a *later* release clock
    # than its underlying trade date. Do not let self-claimed timestamps
    # manufacture a settlement known during the preceding trading session.
    for x in (a, b):
        if x.quote_kind == "SETTLEMENT":
            gate = inspect_cme_settlement_release_gate_lab(
                trade_date=x.trade_date,
                channel=x.settlement_publication_channel,
                published_at_utc=x.published_at_utc,
                captured_at_utc=x.captured_at_utc,
                as_of_utc=now,
            )
            if gate["state"] != "SELF_CLAIMED_PUBLIC_TIMING_PLAUSIBLE_NOT_AUTHENTICATED":
                return failure
    move = (_price(a.futures_price_index) - _price(b.futures_price_index)) * 100
    return {
        "status": "SELF_CLAIMED_VINTAGES_ONLY_NOT_AUTHENTICATED",
        "reference_start_month": a.reference_start_month,
        "imm_reference_start": start.isoformat(),
        "imm_reference_end_exclusive": end.isoformat(),
        "new_trade_date": b.trade_date.isoformat(),
        "new_observed_at_utc": new_obs.isoformat(),
        "new_published_at_utc": new_pub.isoformat(),
        "new_captured_at_utc": new_cap.isoformat(),
        "claimed_underlying_rate_change_bps": str(move),
        "quote_kind": b.quote_kind,
        "volume_from_named_contract_authenticated": False,
        "observed_contract_session_volume_claim": b.contract_session_volume,
        "issuer_archived_original": False,
    }


def inspect_eurusd_sr3_esr_imm_quarter_lab(*, quotes_by_currency: Any, as_of_utc: Any) -> dict[str, Any]:
    """Check matched claimed rate futures vintages; never derive spot EUR/USD bias."""
    now = _utc(as_of_utc)
    if now is None or not isinstance(quotes_by_currency, dict) or set(quotes_by_currency) != set(PRODUCTS):
        return _blocked("LAB_INVALID_INPUT", "INVALID_CLOCK_OR_REQUIRED_QUOTES")
    if now < RESEARCH_VISIBLE_FROM_UTC:
        return _blocked("LAB_RESEARCH_NOT_VISIBLE_AS_OF", "NO_HISTORIC_RESEARCH_DISCOVERY_ATTESTATION")
    rows = {c: _check_currency_claims(quotes_by_currency[c], c, now) for c in PRODUCTS}
    out = _blocked("LAB_SR3_ESR_MATCHED_QUARTER_NOT_AUTHENTICATED", "NO_AUDITED_CONTRACT_QUOTES_OR_SPOT_BASIS")
    out["as_of_utc"] = now.isoformat()
    out["evidence_by_currency"] = rows
    if all(x.get("status") == "SELF_CLAIMED_VINTAGES_ONLY_NOT_AUTHENTICATED" for x in rows.values()):
        old = rows["USD"]
        eur = rows["EUR"]
        # On the exact same reference quarter, rates are economically
        # comparable as overnight *benchmarks*, NOT identical policy rates.
        if (old["imm_reference_start"] == eur["imm_reference_start"] and
                old["imm_reference_end_exclusive"] == eur["imm_reference_end_exclusive"] and
                old["new_trade_date"] == eur["new_trade_date"] and
                old["reference_start_month"] == eur["reference_start_month"]):
            out["both_claimed_quotes_same_quarter"] = True
            # Deliberately keep differential unset until independent issuer
            # snapshots/quote rights/basis are authenticated.
    return out