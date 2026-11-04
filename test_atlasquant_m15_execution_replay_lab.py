"""Causal-clock and conservative-cost regression tests; synthetic OHLC only."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from atlasquant_m15_execution_replay_lab import SCHEMA, OUTPUT_SCHEMA, replay_m15_setup

NOW = datetime(2026, 11, 4, 14, tzinfo=timezone.utc)
START = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)


def bar(index, opening, high, low, close):
    return {
        "time": (START + timedelta(minutes=15 * index)).isoformat(),
        "open": opening, "high": high, "low": low, "close": close,
    }


def fixture():
    return {
        "schema": SCHEMA, "state": "OFFLINE_RESEARCH",
        "timeframe": "M15", "pair": "EUR/USD",
        "side": "BUY", "setup_kind": "FVG",
        "signal_bar_index": 2,
        "signal_confirmed_at": (START + timedelta(minutes=45)).isoformat(),
        "stop_mid": 98.0, "target_mid": 104.0,
        "point_size": 0.01,
        "spread_points_assumed": 2,
        "slippage_points_assumed": 1,
        "bars": [
            bar(0, 100, 101, 99, 100),
            bar(1, 100, 101, 99, 100),
            bar(2, 100, 101, 99, 100),
            bar(3, 100, 102, 99, 101),
            bar(4, 101, 105, 100, 104),
        ],
    }


def replay(data):
    return replay_m15_setup(data, now=NOW)


def test_next_bar_entry_target_net_r_after_conservative_costs():
    sample = fixture()
    before = deepcopy(sample)
    result = replay(sample)
    assert sample == before
    assert result["schema"] == OUTPUT_SCHEMA
    assert result["state"] == "RESEARCH_ONLY"
    assert result["outcome"] == "TARGET"
    assert result["entry_bar_start"] == "2026-11-04T12:45:00+00:00"
    assert result["entry_fill"] == pytest.approx(100.02)
    assert result["target_fill_assumed"] == pytest.approx(103.98)
    assert result["risk_per_unit_assumed"] == pytest.approx(2.04)
    assert result["net_r"] == pytest.approx(3.96 / 2.04, abs=1e-6)
    assert result["costs_are_assumptions"]
    assert not result["signal_causal_verified"]
    assert not result["spread_slippage_verified"]
    assert not result["profitability_verified"]
    assert not result["trade_authorized"] and not result["publishable"]


def test_stop_first_if_both_levels_touch_same_m15_bar():
    sample = fixture()
    sample["bars"][3] = bar(3, 100, 105, 97, 100)
    result = replay(sample)
    assert result["outcome"] == "AMBIGUOUS_STOP_FIRST"
    assert result["net_r"] == -1
    assert result["exit_bar_start"] == "2026-11-04T12:45:00+00:00"


def test_sell_target_with_costs_and_stop_loss():
    sample = fixture()
    sample.update({"side": "SELL", "stop_mid": 102, "target_mid": 96})
    sample["bars"][3] = bar(3, 100, 101, 99, 100)
    sample["bars"][4] = bar(4, 100, 101, 95, 96)
    result = replay(sample)
    assert result["outcome"] == "TARGET"
    assert result["entry_fill"] == pytest.approx(99.98)
    assert result["net_r"] == pytest.approx(3.96 / 2.04, abs=1e-6)
    sample["bars"][3] = bar(3, 100, 103, 99, 102)
    assert replay(sample)["outcome"] == "STOP"
    assert replay(sample)["net_r"] == -1


def test_no_exit_stays_unresolved_not_counted_as_win():
    sample = fixture()
    sample["bars"][4] = bar(4, 101, 103, 99, 101)
    result = replay(sample)
    assert result["outcome"] == "UNRESOLVED_NO_EXIT"
    assert result["net_r"] is None


@pytest.mark.parametrize("edit,why", [
    (lambda p: p.update({"signal_bar_index": 4}), "SIGNAL_NOT_BEFORE_ENTRY"),
    (lambda p: p.update({"signal_bar_index": True}), "SIGNAL_NOT_BEFORE_ENTRY"),
    (lambda p: p.update({"signal_confirmed_at": "2026-11-04T13:00:00Z"}), "SIGNAL_CONFIRMATION_TIME_INVALID"),
    (lambda p: p.update({"stop_mid": 101}), "INVALID_RISK_GEOMETRY"),
    (lambda p: p.update({"target_mid": 100.01}), "INVALID_RISK_GEOMETRY"),
    (lambda p: p.update({"spread_points_assumed": -1}), "MISSING_OR_INVALID_COSTS_OR_LEVELS"),
    (lambda p: p.update({"point_size": 0}), "MISSING_OR_INVALID_COSTS_OR_LEVELS"),
    (lambda p: p.update({"pair": "USD/EUR"}), "INVALID_PAIR"),
    (lambda p: p.update({"timeframe": "M5"}), "INVALID_CONTRACT"),
    (lambda p: p["bars"][3].update({"time": "2026-11-04T13:00:00Z"}), "M15_GAP_OR_ORDER"),
    (lambda p: p["bars"][1].update({"high": 90}), "INVALID_OHLC_OR_BAR_TIME"),
])
def test_invalid_hindsight_timing_risk_and_costs_fail_closed(edit, why):
    sample = fixture()
    edit(sample)
    result = replay(sample)
    assert result["state"] == "BLOCKED"
    assert result["reason"] == why
    assert result["net_r"] is None
    assert not result["trade_authorized"]


def test_future_candle_and_naive_clock_refused():
    sample = fixture()
    sample["bars"][4]["time"] = "2026-11-04T14:00:00+00:00"
    assert replay(sample)["reason"] == "FUTURE_OR_OPEN_BAR"
    with pytest.raises(ValueError):
        replay_m15_setup(fixture(), now=NOW.replace(tzinfo=None))


def test_radar_daily_gate_never_promotes_replay_result():
    from atlasquant_trader_radar_compact_ui import _daily
    assert _daily(replay(fixture()))["pairs"] == {}
