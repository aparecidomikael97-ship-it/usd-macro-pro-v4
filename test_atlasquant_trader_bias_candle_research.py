"""Offline-only research trend tests. No provider, account or deployment."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_bias_candle_research import (
    MIN_BARS, build_ohlc_bias_research, research_bias_from_bars,
)
from atlasquant_trader_bias_matrix import TIMEFRAMES, read_bias_matrix

NOW = datetime(2026, 11, 3, 16, tzinfo=timezone.utc)
SPAN = {
    "M15": timedelta(minutes=15), "H4": timedelta(hours=4),
    "D1": timedelta(days=1), "W1": timedelta(days=7),
}


def candles(tf="M15", trend=1, count=MIN_BARS, now=NOW):
    step = SPAN[tf]
    last_close = now - timedelta(minutes=5)
    result = []
    for i in range(count):
        start = last_close - (count - i) * step
        end = start + step
        px = 1.20 + trend * i * 0.00015
        close = px + trend * 0.00006
        result.append({
            "datetime": start.isoformat(),
            "closed_at": end.isoformat(),
            "open": px,
            "high": max(px, close) + 0.00020,
            "low": min(px, close) - 0.00020,
            "close": close,
        })
    return result


@pytest.mark.parametrize("tf", TIMEFRAMES)
@pytest.mark.parametrize("trend,wanted", [(1, "ALTA"), (-1, "BAIXA"), (0, "NEUTRO")])
def test_trend_research_classifies_only_closed_recent_bars(tf, trend, wanted):
    result = research_bias_from_bars(candles(tf, trend), timeframe=tf, now=NOW)
    assert result["state"] == "READY_RESEARCH"
    assert result["bias"] == wanted
    assert result["reason"] == "EMA20_EMA50_INCLINAÇÃO_ATR"


def test_missing_history_and_ambiguous_closing_time_waits():
    assert research_bias_from_bars([], timeframe="M15", now=NOW)["bias"] == "AGUARDAR"
    short = candles(count=MIN_BARS - 1)
    assert research_bias_from_bars(short, timeframe="M15", now=NOW)["reason"] == "HISTÓRICO_INSUFICIENTE"
    missing = candles()
    missing[-1].pop("closed_at")
    assert research_bias_from_bars(missing, timeframe="M15", now=NOW)["reason"] == "CANDLE_INVÁLIDO"


def test_duplicate_scrambled_or_overlapping_candles_refused():
    for edit in ("duplicate", "reverse", "overlap"):
        rows = candles()
        if edit == "duplicate":
            rows[-1]["datetime"] = rows[-2]["datetime"]
        if edit == "reverse":
            rows = list(reversed(rows))
        if edit == "overlap":
            rows[-1]["datetime"] = rows[-2]["datetime"]
        out = research_bias_from_bars(rows, timeframe="M15", now=NOW)
        assert out["state"] == "NOT_READY"
        assert out["bias"] == "AGUARDAR"


@pytest.mark.parametrize("field,value", [
    ("high", -2), ("close", float("nan")), ("low", 5),
    ("open", "abc"), ("high", True), ("open", 0),
])
def test_invalid_ohlc_values_are_rejected(field, value):
    rows = candles()
    rows[-1][field] = value
    assert research_bias_from_bars(rows, timeframe="M15", now=NOW)["state"] == "NOT_READY"


def test_future_incomplete_and_stale_bars_all_wait():
    rows = candles()
    rows[-1]["closed_at"] = (NOW + timedelta(seconds=1)).isoformat()
    assert research_bias_from_bars(rows, timeframe="M15", now=NOW)["reason"] == "CANDLE_NÃO_FECHADO"
    rows = candles(now=NOW - timedelta(hours=5))
    assert research_bias_from_bars(rows, timeframe="M15", now=NOW)["reason"] == "DADOS_VENCIDOS"


def test_all_28_x_four_timeframes_are_never_misrepresented_as_live_data():
    one = {tf: candles(tf, 1) for tf in TIMEFRAMES}
    source = {"source": "Synthetic test data", "pairs": {pair: one for pair in OFFICIAL_PAIRS}}
    result = build_ohlc_bias_research(source, now=NOW)
    assert result["complete_pairs"] == 28
    assert len(result["rows"]) == 28
    assert result["state"] == "RESEARCH_ONLY"
    assert result["publishable"] is False
    assert result["real_orders_enabled"] is False
    assert result["provider_calls"] == 0
    assert result["producer_verified"] is False
    # A test series must NEVER satisfy the live validation contract.
    assert read_bias_matrix(result, now=NOW)["state"] == "NO_DATA"


def test_partial_coverage_remains_explicit_for_all_pairs():
    source = {"source": "LAB", "pairs": {OFFICIAL_PAIRS[0]: {"M15": candles("M15")}}}
    report = build_ohlc_bias_research(source, now=NOW)
    assert report["complete_pairs"] == 0
    assert len(report["rows"]) == 28
    assert report["rows"][OFFICIAL_PAIRS[0]]["M15"]["state"] == "READY_RESEARCH"
    assert report["rows"][OFFICIAL_PAIRS[0]]["H4"]["reason"] == "HISTÓRICO_INSUFICIENTE"


def test_non_timezone_now_is_disallowed():
    with pytest.raises(ValueError):
        research_bias_from_bars(candles(), timeframe="M15", now=NOW.replace(tzinfo=None))
    with pytest.raises(ValueError):
        build_ohlc_bias_research({}, now=NOW.replace(tzinfo=None))


def test_unknown_timeframe_is_refused_and_no_probabilities_returned():
    with pytest.raises(ValueError):
        research_bias_from_bars(candles(), timeframe="M5", now=NOW)
    row = research_bias_from_bars(candles(), timeframe="M15", now=NOW)
    assert "confidence" not in row and "probability" not in row
