"""Offline MT5-shaped M15 bars: historical research, never live Forex."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_mt5_m15_history_lab import SCHEMA, OUTPUT_SCHEMA, analyze_mt5_m15_history

NOW = datetime(2026, 11, 4, 13, 3, tzinfo=timezone.utc)
START = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)


def bar(when, mid):
    return {
        "time": int(when.timestamp()),
        "open": mid, "high": mid * 1.0002,
        "low": mid * .9998, "close": mid,
        "tick_volume": 120, "spread": 12, "real_volume": 0,
    }


def fixture(times=None):
    dates = times or [START + timedelta(minutes=15*i) for i in range(3)]
    return {
        "schema": SCHEMA, "state": "OFFLINE_RESEARCH", "timeframe": "M15",
        "terminal_claim": "SYNTHETIC_MT5_EXPORT_NOT_AUTHENTICATED",
        "pairs": {
            symbol: [bar(when, 1.0 + idx * .001) for when in dates]
            for idx, symbol in enumerate(OFFICIAL_PAIRS)
        },
    }


def analyze(sample):
    return analyze_mt5_m15_history(sample, now=NOW)


def test_complete_28_m15_history_research_does_not_claim_live_or_profit():
    sample = fixture()
    original = deepcopy(sample)
    r = analyze(sample)
    assert sample == original
    assert r["schema"] == OUTPUT_SCHEMA
    assert r["state"] == "RESEARCH_ONLY"
    assert r["reason"] == "UNAUTHENTICATED_MT5_HISTORY_RESEARCH_ONLY"
    assert r["complete_pairs"] == 28
    assert r["bars_per_pair"] == 3
    assert r["last_bar_end_utc"] == "2026-11-04T12:45:00+00:00"
    assert len(r["last_close"]) == 28
    assert len(r["last_tick_volume"]) == 28
    assert len(r["last_spread_points"]) == 28
    assert r["last_spread_points"]["EUR/USD"] == 12
    assert r["volume_kind"] == "BROKER_TICK_COUNT_NOT_CENTRALIZED_FOREX_VOLUME"
    assert not r["publishable"] and not r["trade_authorized"]
    assert not r["provider_authenticated"] and not r["price_accuracy_verified"]
    assert not r["historical_bid_ask_verified"] and not r["spread_cost_verified"]
    assert not r["backtest_performance_verified"] and not r["market_feed_connected"]


def test_missing_or_extra_pair_blocks_all_history():
    sample = fixture()
    sample["pairs"].pop(OFFICIAL_PAIRS[0])
    assert analyze(sample)["reason"] == "INCOMPLETE_28_PAIR_UNIVERSE"
    sample = fixture()
    sample["pairs"]["EUR/XXX"] = sample["pairs"][OFFICIAL_PAIRS[0]]
    assert analyze(sample)["reason"] == "INCOMPLETE_28_PAIR_UNIVERSE"


def test_m5_mislabel_cannot_pass_as_m15():
    sample = fixture()
    sample["timeframe"] = "M5"
    assert analyze(sample)["reason"] == "INVALID_CONTRACT"


@pytest.mark.parametrize("edit,reason", [
    (lambda bars: bars.pop(), "BAR_HISTORY_LENGTH_INVALID"),
    (lambda bars: bars[0].update({"open": -1}), "MT5_OHLC_OR_FIELDS_INVALID"),
    (lambda bars: bars[0].update({"high": 0.2}), "MT5_OHLC_OR_FIELDS_INVALID"),
    (lambda bars: bars[0].update({"close": float("nan")}), "MT5_OHLC_OR_FIELDS_INVALID"),
    (lambda bars: bars[0].update({"tick_volume": True}), "MT5_OHLC_OR_FIELDS_INVALID"),
    (lambda bars: bars[0].update({"spread": -3}), "MT5_OHLC_OR_FIELDS_INVALID"),
    (lambda bars: bars[0].update({"time": True}), "MT5_OHLC_OR_FIELDS_INVALID"),
    (lambda bars: bars[1].update({"time": bars[0]["time"]}), "DUPLICATE_OR_OUT_OF_ORDER_BAR"),
    (lambda bars: bars[2].update({"time": int(NOW.replace(minute=0, second=0).timestamp())}), "FUTURE_OR_OPEN_HISTORY_BAR"),
])
def test_single_bad_bar_blocks_all_28(edit, reason):
    sample = fixture()
    edit(sample["pairs"][OFFICIAL_PAIRS[0]])
    r = analyze(sample)
    assert r["state"] == "BLOCKED" and r["reason"] == reason
    assert r["complete_pairs"] == 0 and r["last_close"] == {}


def test_mixed_interior_timeline_cannot_look_synchronized():
    sample = fixture([
        START, START + timedelta(minutes=15), START + timedelta(minutes=45),
    ])
    sample["pairs"][OFFICIAL_PAIRS[0]][1]["time"] = int((START+timedelta(minutes=30)).timestamp())
    r = analyze(sample)
    assert r["reason"] == "MIXED_28_PAIR_HISTORY_WINDOWS"


def test_weekend_gap_is_counted_without_inventing_candles():
    dates = [
        datetime(2026, 10, 30, 12, tzinfo=timezone.utc),
        datetime(2026, 11, 2, 12, tzinfo=timezone.utc),
        datetime(2026, 11, 2, 12, 15, tzinfo=timezone.utc),
    ]
    r = analyze(fixture(dates))
    assert r["state"] == "RESEARCH_ONLY"
    assert r["total_history_gaps"] == 28
    assert not r["publishable"]


def test_reject_passwords_and_future_or_naive_clock():
    sample = fixture()
    sample["token"] = "NOT_A_REAL_TOKEN"
    assert analyze(sample)["reason"] == "SENSITIVE_FIELD_NOT_ALLOWED"
    with pytest.raises(ValueError):
        analyze_mt5_m15_history(fixture(), now=NOW.replace(tzinfo=None))
    assert analyze_mt5_m15_history(
        fixture(), now=START + timedelta(minutes=10),
    )["reason"] == "FUTURE_OR_OPEN_HISTORY_BAR"


def test_mt5_histories_do_not_pass_live_daily_gate():
    from atlasquant_trader_radar_compact_ui import _daily
    r = analyze(fixture())
    assert _daily(r)["pairs"] == {}
