"""Offline broker-candle contract tests; no real broker or executable prices."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from math import exp

import pytest

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_fx_m15_candle_lab import (
    SCHEMA, OUTPUT_SCHEMA, analyze_m15_candle_export,
)

NOW = datetime(2026, 11, 4, 13, 3, tzinfo=timezone.utc)
SOURCE = "SYNTHETIC_PROVIDER_CLAIM_NOT_AUTHENTICATED"
M15_STRENGTH = {
    "EUR": .12, "USD": .05, "GBP": .09, "JPY": -.12,
    "CHF": .04, "CAD": -.03, "AUD": -.07, "NZD": -.08,
}


def _bar(start, mid):
    spread = mid * 0.00004
    bid, ask = mid - spread / 2, mid + spread / 2
    return {
        "time": start.isoformat(), "complete": True,
        "bid": {key: str(bid) for key in ("o", "h", "l", "c")},
        "ask": {key: str(ask) for key in ("o", "h", "l", "c")},
    }


def fixture():
    previous = NOW.replace(hour=12, minute=30, second=0)
    latest = NOW.replace(hour=12, minute=45, second=0)
    pairs = {}
    for symbol in OFFICIAL_PAIRS:
        base, quote = split_pair(symbol)
        mid = exp((M15_STRENGTH[base] - M15_STRENGTH[quote]) / 100)
        pairs[symbol] = {
            "source_claim": SOURCE, "granularity": "M15",
            "candles": [_bar(previous, 1.0), _bar(latest, mid)],
        }
    return {
        "schema": SCHEMA, "state": "OFFLINE_RESEARCH",
        "kind": "MARKET_CANDLE_EXPORT",
        "source_claim": SOURCE, "captured_at": NOW.isoformat(),
        "pairs": pairs,
    }


def test_complete_m15_28_pair_contract_is_research_not_trading():
    sample = fixture()
    original = deepcopy(sample)
    result = analyze_m15_candle_export(sample, now=NOW)
    assert sample == original
    assert result["schema"] == OUTPUT_SCHEMA
    assert result["state"] == "RESEARCH_ONLY"
    assert result["reason"] == "PROVIDER_NOT_AUTHENTICATED"
    assert result["complete_pairs"] == 28
    assert set(result["pair_changes_pct"]) == set(OFFICIAL_PAIRS)
    assert set(result["spreads_pct"]) == set(OFFICIAL_PAIRS)
    assert set(result["currency_strength_log_pp"]) == set(CURRENCIES)
    assert result["currency_order"][0] == "EUR"
    assert result["currency_order"][-1] == "JPY"
    assert result["pair_changes_pct"]["EUR/JPY"] > 0
    assert result["max_consistency_residual_log_pp"] < 0.00001
    assert result["latest_candle_end"] == "2026-11-04T13:00:00+00:00"
    assert len(result["top10"]) == 10
    assert not result["publishable"]
    assert not result["provider_authenticated"]
    assert not result["trade_authorized"]
    assert not result["accuracy_verified"]
    assert not result["independent_observations_verified"]
    assert not result["has_executable_bid_ask"]
    assert result["candle_bid_ask_is_historical"]


def test_missing_or_extra_pairs_block_everything():
    for change in (
        lambda s: s["pairs"].pop(OFFICIAL_PAIRS[0]),
        lambda s: s["pairs"].update({"EUR/XXX": {}}),
    ):
        sample = fixture()
        change(sample)
        result = analyze_m15_candle_export(sample, now=NOW)
        assert result["state"] == "BLOCKED"
        assert result["reason"] == "INCOMPLETE_28_PAIR_UNIVERSE"
        assert result["pair_changes_pct"] == {}
        assert result["complete_pairs"] == 0


@pytest.mark.parametrize("edit,reason", [
    (lambda r: r.update({"granularity":"M5"}), "WRONG_TIMEFRAME"),
    (lambda r: r.update({"source_claim":"OTHER"}), "CANDLE_SOURCE_MISMATCH"),
    (lambda r: r["candles"][1].update({"complete": False}), "INVALID_OHLC_OR_INCOMPLETE_CANDLE"),
    (lambda r: r["candles"][1]["bid"].update({"c": "-1"}), "INVALID_OHLC_OR_INCOMPLETE_CANDLE"),
    (lambda r: r["candles"][1]["ask"].update({"h": "nan"}), "INVALID_OHLC_OR_INCOMPLETE_CANDLE"),
    (lambda r: r["candles"][1]["bid"].update({"h": "0.5"}), "INVALID_OHLC_OR_INCOMPLETE_CANDLE"),
    (lambda r: r["candles"][1]["bid"].update({"c": "100"}), "INVALID_OHLC_OR_INCOMPLETE_CANDLE"),
    (lambda r: r["candles"].pop(), "REQUIRE_TWO_COMPLETED_CANDLES"),
    (lambda r: r["candles"][0].update({"time":"2026-11-04T12:15:00+00:00"}), "M15_CANDLE_GAP_OR_ORDER"),
    (lambda r: r["candles"][1].update({"time":"2026-11-04T12:47:00+00:00"}), "INVALID_OHLC_OR_INCOMPLETE_CANDLE"),
    (lambda r: r["candles"][1].update({"time":"2026-11-04T13:00:00+00:00"}), "M15_CANDLE_GAP_OR_ORDER"),
])
def test_any_bad_pair_is_atomic_block(edit, reason):
    sample = fixture()
    edit(sample["pairs"][OFFICIAL_PAIRS[0]])
    result = analyze_m15_candle_export(sample, now=NOW)
    assert result["state"] == "BLOCKED"
    assert result["reason"] == reason
    assert result["complete_pairs"] == 0
    assert result["top10"] == []


def test_fabricated_cross_move_is_rejected():
    sample = fixture()
    record = sample["pairs"]["EUR/USD"]["candles"][1]
    for key in ("bid", "ask"):
        for part in ("o", "h", "l", "c"):
            record[key][part] = str(float(record[key][part]) * 1.04)
    result = analyze_m15_candle_export(sample, now=NOW)
    assert result["reason"] == "M15_CROSS_RATE_INCONSISTENCY"


def test_stale_future_and_mixed_windows_rejected():
    sample = fixture()
    sample["captured_at"] = (NOW - timedelta(minutes=6)).isoformat()
    assert analyze_m15_candle_export(sample, now=NOW)["reason"] == "STALE_OR_FUTURE_CAPTURE"
    sample = fixture()
    sample["captured_at"] = (NOW + timedelta(seconds=1)).isoformat()
    assert analyze_m15_candle_export(sample, now=NOW)["reason"] == "STALE_OR_FUTURE_CAPTURE"
    sample = fixture()
    record = sample["pairs"][OFFICIAL_PAIRS[0]]
    record["candles"][0]["time"] = "2026-11-04T12:15:00+00:00"
    record["candles"][1]["time"] = "2026-11-04T12:30:00+00:00"
    assert analyze_m15_candle_export(sample, now=NOW)["reason"] == "MIXED_CANDLE_WINDOWS"
    sample = fixture()
    later = NOW + timedelta(hours=2)
    sample["captured_at"] = later.isoformat()
    assert analyze_m15_candle_export(sample, now=later)["reason"] == "STALE_OR_FUTURE_M15_CANDLE"


def test_sensitive_fields_and_ecb_references_do_not_pass_m15_gate():
    sample = fixture()
    sample["access_token"] = "should-never-be-used"
    assert analyze_m15_candle_export(sample, now=NOW)["reason"] == "SENSITIVE_FIELD_NOT_ALLOWED"
    assert analyze_m15_candle_export({
        "schema":"ATLASQUANT_ECB_G8_REFERENCE_LAB_V1", "state":"RESEARCH_ONLY",
        "pair_returns_pct": {symbol: 0.1 for symbol in OFFICIAL_PAIRS},
    }, now=NOW)["reason"] == "INVALID_CONTRACT"


def test_radar_daily_gate_must_ignore_m15_research():
    from atlasquant_trader_radar_compact_ui import _daily
    result = analyze_m15_candle_export(fixture(), now=NOW)
    assert _daily(result)["pairs"] == {}


def test_naive_clock_is_rejected_without_publishing():
    with pytest.raises(ValueError):
        analyze_m15_candle_export(fixture(), now=NOW.replace(tzinfo=None))
