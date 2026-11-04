"""Pure offline OANDA v20 response normalization; never contacts a broker."""
from copy import deepcopy
from datetime import timedelta

import pytest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_oanda_m15_export_lab import ADAPTER, analyze_oanda_m15_export
from test_atlasquant_fx_m15_candle_lab import NOW, fixture


def oanda_fixture(*, include_open: bool = False):
    normalized = fixture()
    out = []
    for pair in OFFICIAL_PAIRS:
        sample = normalized["pairs"][pair]
        candles = deepcopy(sample["candles"])
        if include_open:
            opening = deepcopy(candles[-1])
            opening["time"] = (NOW.replace(minute=0, second=0)).isoformat()
            opening["complete"] = False
            candles.append(opening)
        out.append({
            "instrument": pair.replace("/", "_"), "granularity": "M15",
            "candles": candles,
        })
    return out


def analyze(responses):
    return analyze_oanda_m15_export(
        responses, captured_at=NOW.isoformat(), now=NOW,
    )


def test_28_oanda_shaped_responses_are_research_only_and_do_not_mutate():
    samples = oanda_fixture(include_open=True)
    before = deepcopy(samples)
    result = analyze(samples)
    assert samples == before
    assert result["state"] == "RESEARCH_ONLY"
    assert result["complete_pairs"] == 28
    assert result["reason"] == "PROVIDER_NOT_AUTHENTICATED"
    assert result["offline_adapter"] == ADAPTER
    assert result["latest_candle_end"] == "2026-11-04T13:00:00+00:00"
    assert not result["provider_authenticated"]
    assert not result["independent_observations_verified"]
    assert not result["publishable"] and not result["trade_authorized"]
    assert not result["has_executable_bid_ask"]


def test_a_missing_or_duplicate_response_is_blocked_atomically():
    assert analyze(oanda_fixture()[:-1])["reason"] == "OANDA_EXPORT_REQUIRES_28_RESPONSES"
    samples = oanda_fixture()
    samples[-1] = deepcopy(samples[0])
    result = analyze(samples)
    assert result["reason"] == "OANDA_DUPLICATE_INSTRUMENT"
    assert result["complete_pairs"] == 0


@pytest.mark.parametrize("edit,expected", [
    (lambda r: r.update({"instrument": "USD_EUR"}), "OANDA_INSTRUMENT_INVALID"),
    (lambda r: r.update({"instrument": "eur_usd"}), "OANDA_INSTRUMENT_INVALID"),
    (lambda r: r.update({"granularity": "M5"}), "OANDA_GRANULARITY_INVALID"),
    (lambda r: r.update({"candles": []}), "OANDA_CANDLE_HISTORY_INVALID"),
    (lambda r: r["candles"][0].update({"complete": False}), "OANDA_INCOMPLETE_OR_MISSING_CLOSED_CANDLES"),
    (lambda r: r["candles"][1].pop("ask"), "INVALID_OHLC_OR_INCOMPLETE_CANDLE"),
    (lambda r: r["candles"][1]["bid"].update({"o": "NaN"}), "INVALID_OHLC_OR_INCOMPLETE_CANDLE"),
    (lambda r: r.update({"api_key": "DO_NOT_READ"}), "OANDA_SENSITIVE_FIELD_REJECTED"),
])
def test_single_invalid_oanda_response_blocks_everything(edit, expected):
    samples = oanda_fixture()
    edit(samples[0])
    result = analyze(samples)
    assert result["state"] == "BLOCKED"
    assert result["reason"] == expected
    assert result["pair_changes_pct"] == {}
    assert not result["publishable"]


def test_time_misalignment_and_old_capture_stay_blocked():
    samples = oanda_fixture()
    samples[0]["candles"][1]["time"] = "2026-11-04T12:30:00+00:00"
    assert analyze(samples)["state"] == "BLOCKED"
    result = analyze_oanda_m15_export(
        oanda_fixture(), captured_at=(NOW-timedelta(minutes=20)).isoformat(),
        now=NOW,
    )
    assert result["reason"] == "STALE_OR_FUTURE_CAPTURE"


def test_m15_adapter_never_promotes_to_daily_live_radar():
    from atlasquant_trader_radar_compact_ui import _daily
    assert _daily(analyze(oanda_fixture()))["pairs"] == {}
