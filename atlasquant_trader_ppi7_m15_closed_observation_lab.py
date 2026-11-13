"""PPI-2026-11-13 M15 *closed* reaction, all 7 USD pairs, MT5 read-only LAB.

This is an optional, explicit, one-shot in-process call using an already-open
terminal. There is NO background worker or on-import MT5 connection. Neither
the prices nor the terminal labels independently attest Pepperstone origin,
first-seen history, execution costs, causal PPI impact, or a forecast.
It can report an M15 observation at 13:45 UTC WITHOUT pretending the H1/H4
windows have closed. The pre-registered macro directional call was ABSTAIN.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Callable

from atlasquant_mt5_xauusd_closedbar_capture_lab import _terminal_path_ok
from atlasquant_trader_ppi_usd_fx_forward_reaction_lab import (
    EVENT_UTC, USD_FX, BASELINE_OPEN_UTC,
)
from atlasquant_trader_ppi_mt5_m15_capture_lab import (
    _symbol_spec_for_capture, _price, _integer,
)

SCHEMA = "ATLASQUANT_TRADER_PPI7_CLOSED_M15_REACTION_READONLY_LAB_V1"
M15_CLOSE_UTC = EVENT_UTC + timedelta(minutes=15)
EXPECTED_OPEN_TIMES = (
    int(BASELINE_OPEN_UTC.timestamp()),
    int(EVENT_UTC.timestamp()),
)


def _base(reason: str, state: str = "LAB_PPI7_M15_OBSERVATION_BLOCKED") -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": state, "reason": reason,
        "event_release_utc": EVENT_UTC.isoformat(),
        "required_m15_close_utc": M15_CLOSE_UTC.isoformat(),
        "pre_event_m15_open_utc": BASELINE_OPEN_UTC.isoformat(),
        "post_event_m15_open_utc": EVENT_UTC.isoformat(),
        "horizon_observed": None,
        "h1_window_closed_and_observed": False,
        "h4_window_closed_and_observed": False,
        "expected_symbols": list(USD_FX),
        "validated_symbols": 0, "validated_m15_candles": 0,
        "usd_normalized_m15_bps_by_pair": None,
        "usd_stronger_pair_count": None,
        "usd_weaker_pair_count": None,
        "unchanged_pair_count": None,
        "independent_economic_events_observed": 0,
        "seven_pairs_are_not_independent_events": True,
        "data_from_terminal_independently_authenticated": False,
        "prices_first_available_at_event_independently_attested": False,
        "ppi_release_first_print_independently_authenticated": False,
        "observed_association_not_ppi_causality": True,
        "execution_bidask_spread_slippage_verified": False,
        "historical_out_of_sample_accuracy": None,
        "calibrated_probability": None,
        "directional_forecast": None,
        "operational_bias": "AGUARDAR", "trade_authorized": False,
        "publishable": False, "live_alert_allowed": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "files_written": 0, "http_requests": 0, "new_cost_brl": 0,
    }


def _utc(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None):
        return None
    return value.astimezone(timezone.utc)


def _extract_two_closed_candles(rates: Any, *, digits: int) -> tuple[Decimal, Decimal]:
    if rates is None or len(rates) != 2:
        raise ValueError("REQUIRE_EXACT_TWO_M15_CANDLES")
    closes = []
    for i, row in enumerate(rates):
        try:
            stamp = _integer(row["time"], strictly_positive=True)
            if stamp != EXPECTED_OPEN_TIMES[i]:
                raise ValueError("M15_EPOCH_DUPLICATE_GAP_OR_WRONG_TIMEZONE")
            op, hi, lo, cl = (
                _price(row[field], quote_digits=digits)[0]
                for field in ("open", "high", "low", "close")
            )
            if not lo <= min(op, cl) <= max(op, cl) <= hi:
                raise ValueError("M15_OHLC_INCONSISTENT")
            _integer(row["tick_volume"], strictly_positive=True)
            _integer(row["spread"])
            _integer(row["real_volume"])
        except (KeyError, TypeError, IndexError, OverflowError) as exc:
            raise ValueError("M15_MISSING_OR_MALFORMED_FIELDS") from exc
        closes.append(cl)
    return closes[0], closes[1]


def observe_ppi7_closed_m15_lab(
    api: Any, *, terminal_path: Any, clock: Callable[[], datetime],
) -> dict[str, Any]:
    """One-shot read only; all seven exact 13:15/13:30 bars or NO-GO.

    API accesses only initialize, terminal_info, symbol_info,
    copy_rates_range and shutdown. No local storage, network, account,
    positions, orders, Market Watch changes or live trading.
    """
    out = _base("INVALID_TERMINAL_OR_CLOCK")
    if not _terminal_path_ok(terminal_path) or not callable(clock):
        return out
    try:
        now = _utc(clock())
    except (TypeError, ValueError, OverflowError, RuntimeError):
        return out
    if now is None:
        return out
    if now < M15_CLOSE_UTC:
        return _base("M15_WINDOW_NOT_YET_CLOSED", "LAB_WAIT_PPI7_M15_CLOSE")
    try:
        connected = api.initialize(path=terminal_path, timeout=10000)
    except (AttributeError, TypeError, OSError, ValueError, RuntimeError):
        return _base("MT5_INITIALIZATION_EXCEPTION")
    if connected is not True:
        return _base("MT5_NOT_CONNECTED")

    observations: dict[str, str] = {}
    failure: str | None = None
    failed_symbol: str | None = None
    try:
        terminal = api.terminal_info()
        if terminal is None or getattr(terminal, "connected", None) is not True:
            failure = "MT5_TERMINAL_NOT_CONNECTED"
        else:
            for sym in USD_FX:
                info = api.symbol_info(sym)
                if info is None or type(getattr(info, "visible", None)) is not bool:
                    failure, failed_symbol = "CANONICAL_SYMBOL_METADATA_MISSING", sym
                    break
                visible = info.visible
                spec = _symbol_spec_for_capture(info, sym)
                if spec is None:
                    failure, failed_symbol = "SYMBOL_BASE_QUOTE_DIGITS_OR_POINT_INVALID", sym
                    break
                rates = api.copy_rates_range(
                    sym, api.TIMEFRAME_M15, BASELINE_OPEN_UTC, EVENT_UTC)
                after = api.symbol_info(sym)
                if (after is None or type(getattr(after, "visible", None)) is not bool
                        or after.visible != visible):
                    failure, failed_symbol = "SYMBOL_VISIBILITY_CHANGED_OR_UNKNOWN", sym
                    break
                try:
                    before, after_close = _extract_two_closed_candles(
                        rates, digits=spec["digits_claim"])
                except ValueError as exc:
                    failure, failed_symbol = str(exc), sym
                    break
                # USD as base: USDJPY rises -> stronger USD. USD as
                # quote: EURUSD falls -> stronger USD. No execution return.
                ratio = (after_close / before) if sym.startswith("USD") else (before / after_close)
                bps = (ratio - Decimal(1)) * Decimal(10_000)
                observations[sym] = str(
                    bps.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    except (AttributeError, TypeError, KeyError, OSError, ValueError, RuntimeError):
        failure = "MT5_READ_ONLY_QUERY_EXCEPTION"
    finally:
        try:
            api.shutdown()
        except (AttributeError, TypeError, OSError, RuntimeError):
            failure = "MT5_SHUTDOWN_EXCEPTION"
    if failure is not None:
        result = _base(failure)
        if failed_symbol is not None:
            result["failed_symbol"] = failed_symbol
        return result
    if set(observations) != set(USD_FX):
        return _base("ALL_SEVEN_M15_SERIES_REQUIRED")
    numbers = {sym: Decimal(obs) for sym, obs in observations.items()}
    result = _base(
        "POST_EVENT_M15_OBSERVATION_ONLY_NO_PPI_CAUSALITY_OR_BROKER_ATTESTATION",
        state="LAB_PPI7_CLOSED_M15_DOCUMENTARY_OBSERVATION_NO_GO",
    )
    result.update({
        "horizon_observed": "M15_ONLY",
        "validated_symbols": 7,
        "validated_m15_candles": 14,
        "usd_normalized_m15_bps_by_pair": observations,
        "usd_stronger_pair_count": sum(v > 0 for v in numbers.values()),
        "usd_weaker_pair_count": sum(v < 0 for v in numbers.values()),
        "unchanged_pair_count": sum(v == 0 for v in numbers.values()),
        "independent_economic_events_observed": 1,
    })
    return result


__all__ = ["SCHEMA", "M15_CLOSE_UTC", "observe_ppi7_closed_m15_lab"]
