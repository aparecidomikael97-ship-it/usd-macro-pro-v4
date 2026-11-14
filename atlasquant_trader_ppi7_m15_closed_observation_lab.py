"""PPI-2026-11-13 closed M15/H1/H4 reaction; 7 USD pairs, MT5 read-only LAB.

This is an optional, explicit, one-shot in-process call using an already-open
terminal. There is NO background worker or on-import MT5 connection. Neither
the prices nor the terminal labels independently attest Pepperstone origin,
first-seen history, execution costs, causal PPI impact, or a forecast.
Each horizon independently blocks until its closed M15 candle inventory is
complete (M15 13:45Z; H1 14:30Z; H4 17:30Z). One observation never promotes
another horizon. The pre-registered macro directional call was ABSTAIN.
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

SCHEMA = "ATLASQUANT_TRADER_PPI7_CLOSED_HORIZON_REACTION_READONLY_LAB_V2"
M15_CLOSE_UTC = EVENT_UTC + timedelta(minutes=15)
H1_CLOSE_UTC = EVENT_UTC + timedelta(minutes=60)
H4_CLOSE_UTC = EVENT_UTC + timedelta(minutes=240)
CLOSE_UTC = {"M15": M15_CLOSE_UTC, "H1": H1_CLOSE_UTC, "H4": H4_CLOSE_UTC}
BARS_REQUIRED = {"M15": 2, "H1": 5, "H4": 17}
EXPECTED_OPEN_TIMES = (
    int(BASELINE_OPEN_UTC.timestamp()),
    int(EVENT_UTC.timestamp()),
)


def _expected_opens(horizon: str) -> tuple[int, ...]:
    return tuple(int(BASELINE_OPEN_UTC.timestamp()) + 900 * i
                 for i in range(BARS_REQUIRED[horizon]))


def _base(reason: str, state: str = "LAB_PPI7_M15_OBSERVATION_BLOCKED",
          *, horizon: str = "M15") -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": state, "reason": reason,
        "event_release_utc": EVENT_UTC.isoformat(),
        "required_m15_close_utc": M15_CLOSE_UTC.isoformat(),
        "requested_horizon": horizon,
        "required_horizon_close_utc": (CLOSE_UTC[horizon].isoformat()
                                      if horizon in CLOSE_UTC else None),
        "pre_event_m15_open_utc": BASELINE_OPEN_UTC.isoformat(),
        "post_event_m15_open_utc": EVENT_UTC.isoformat(),
        "horizon_observed": None,
        "h1_window_closed_and_observed": False,
        "h4_window_closed_and_observed": False,
        "expected_symbols": list(USD_FX),
        "validated_symbols": 0, "validated_m15_candles": 0,
        "usd_normalized_m15_bps_by_pair": None,
        "usd_normalized_horizon_bps_by_pair": None,
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


def _extract_closed_candles(
    rates: Any, *, digits: int, horizon: str
) -> tuple[Decimal, Decimal]:
    """Validate EVERY closed M15 bar, never select only first/last from gaps."""
    expected = _expected_opens(horizon)
    if rates is None or len(rates) != len(expected):
        raise ValueError("REQUIRE_EXACT_TWO_M15_CANDLES" if horizon == "M15"
                         else "REQUIRE_EXACT_%d_M15_CANDLES" % len(expected))
    closes = []
    for i, row in enumerate(rates):
        try:
            stamp = _integer(row["time"], strictly_positive=True)
            if stamp != expected[i]:
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
    return closes[0], closes[-1]


def observe_ppi7_closed_horizon_lab(
    api: Any, *, terminal_path: Any, clock: Callable[[], datetime],
    horizon: str,
) -> dict[str, Any]:
    """One-shot read only; exact M15 bar inventory for requested closed horizon.

    API accesses only initialize, terminal_info, symbol_info,
    copy_rates_range and shutdown. No local storage, network, account,
    positions, orders, Market Watch changes or live trading.
    """
    if type(horizon) is not str or horizon not in CLOSE_UTC:
        return _base("UNSUPPORTED_HORIZON", horizon=str(horizon)[:25])
    out = _base("INVALID_TERMINAL_OR_CLOCK", horizon=horizon)
    if not _terminal_path_ok(terminal_path) or not callable(clock):
        return out
    try:
        now = _utc(clock())
    except (TypeError, ValueError, OverflowError, RuntimeError):
        return out
    if now is None:
        return out
    if now < CLOSE_UTC[horizon]:
        return _base(
            horizon + "_WINDOW_NOT_YET_CLOSED",
            "LAB_WAIT_PPI7_" + horizon + "_CLOSE",
            horizon=horizon,
        )
    try:
        connected = api.initialize(path=terminal_path, timeout=10000)
    except (AttributeError, TypeError, OSError, ValueError, RuntimeError):
        return _base("MT5_INITIALIZATION_EXCEPTION", horizon=horizon)
    if connected is not True:
        return _base("MT5_NOT_CONNECTED", horizon=horizon)

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
                from datetime import datetime as _datetime
                last_open = _datetime.fromtimestamp(
                    _expected_opens(horizon)[-1], tz=timezone.utc)
                rates = api.copy_rates_range(
                    sym, api.TIMEFRAME_M15, BASELINE_OPEN_UTC, last_open)
                after = api.symbol_info(sym)
                if (after is None or type(getattr(after, "visible", None)) is not bool
                        or after.visible != visible):
                    failure, failed_symbol = "SYMBOL_VISIBILITY_CHANGED_OR_UNKNOWN", sym
                    break
                try:
                    before, after_close = _extract_closed_candles(
                        rates, digits=spec["digits_claim"], horizon=horizon)
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
        result = _base(failure, horizon=horizon)
        if failed_symbol is not None:
            result["failed_symbol"] = failed_symbol
        return result
    if set(observations) != set(USD_FX):
        return _base("ALL_SEVEN_M15_SERIES_REQUIRED", horizon=horizon)
    numbers = {sym: Decimal(obs) for sym, obs in observations.items()}
    result = _base(
        "POST_EVENT_" + horizon + "_OBSERVATION_ONLY_NO_PPI_CAUSALITY_OR_BROKER_ATTESTATION",
        state="LAB_PPI7_CLOSED_" + horizon + "_DOCUMENTARY_OBSERVATION_NO_GO",
        horizon=horizon,
    )
    result.update({
        "horizon_observed": horizon + "_ONLY",
        "h1_window_closed_and_observed": horizon == "H1",
        "h4_window_closed_and_observed": horizon == "H4",
        "validated_symbols": 7,
        "validated_m15_candles": 7 * BARS_REQUIRED[horizon],
        "usd_normalized_m15_bps_by_pair": observations if horizon == "M15" else None,
        "usd_normalized_horizon_bps_by_pair": observations,
        "usd_stronger_pair_count": sum(v > 0 for v in numbers.values()),
        "usd_weaker_pair_count": sum(v < 0 for v in numbers.values()),
        "unchanged_pair_count": sum(v == 0 for v in numbers.values()),
        "independent_economic_events_observed": 1,
    })
    return result


def observe_ppi7_closed_m15_lab(
    api: Any, *, terminal_path: Any, clock: Callable[[], datetime],
) -> dict[str, Any]:
    """Backwards-compatible M15-only reader, still no H1/H4 lookahead."""
    return observe_ppi7_closed_horizon_lab(
        api, terminal_path=terminal_path, clock=clock, horizon="M15")


__all__ = [
    "SCHEMA", "M15_CLOSE_UTC", "H1_CLOSE_UTC", "H4_CLOSE_UTC",
    "observe_ppi7_closed_m15_lab", "observe_ppi7_closed_horizon_lab",
]
