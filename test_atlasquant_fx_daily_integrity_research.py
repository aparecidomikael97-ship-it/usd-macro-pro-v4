"""Offline research tests: full G8 FX cross-market integrity, no live publishing."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from math import exp, isclose

import pytest

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_fx_daily_integrity_research import (
    SCHEMA, OUTPUT_SCHEMA, analyze_fx_daily_snapshot,
)

NOW = datetime(2026, 11, 4, 13, 0, tzinfo=timezone.utc)
RELATIVE_LOG_PCT = {
    "USD": 0.35, "EUR": 0.70, "GBP": 0.55, "JPY": -0.80,
    "CHF": 0.20, "CAD": -0.10, "AUD": -0.40, "NZD": -0.50,
}
SOURCE = "LAB_TEST_ONLY"


def fixture():
    ref = (NOW - timedelta(days=1)).isoformat()
    pairs = {}
    for index, pair in enumerate(OFFICIAL_PAIRS):
        base, quote = split_pair(pair)
        prev = 1.0
        mid = prev * exp((RELATIVE_LOG_PCT[base] - RELATIVE_LOG_PCT[quote]) / 100.0)
        spread = mid * 0.00004
        pairs[pair] = {
            "source": SOURCE, "bid": mid - spread / 2,
            "ask": mid + spread / 2, "previous_close": prev,
            "observed_at": (NOW - timedelta(seconds=45 + index % 4)).isoformat(),
            "reference_at": ref,
        }
    return {
        "schema": SCHEMA, "state": "OFFLINE_RESEARCH", "source": SOURCE,
        "as_of": NOW.isoformat(), "pairs": pairs,
    }


def test_full_universe_returns_normalized_strength_not_win_probability():
    result = analyze_fx_daily_snapshot(fixture(), now=NOW)
    assert result["schema"] == OUTPUT_SCHEMA
    assert result["state"] == "RESEARCH_ONLY"
    assert result["reason"] == "PROVIDER_NOT_AUTHENTICATED"
    assert result["complete_pairs"] == 28
    assert result["total_pairs"] == 28
    assert set(result["pair_returns_pct"]) == set(OFFICIAL_PAIRS)
    assert set(result["currencies"]) == set(CURRENCIES)
    assert len(result["top10"]) == 10
    assert result["currency_order"][0] == "EUR"
    assert result["currency_order"][-1] == "JPY"
    assert isclose(sum(result["currencies"].values()), 0.0, abs_tol=0.00001)
    assert result["max_consistency_residual_log_pp"] < 0.00001
    assert result["method"] == "G8_MEAN_SIGNED_LOG_RETURN_V1"
    assert result["publishable"] is False
    assert result["provider_authenticated"] is False
    assert result["trade_authorized"] is False
    assert result["accuracy_verified"] is False
    assert "probabilidade" in result["notice"].lower()


def test_pair_orientation_and_top_ten_are_simple_pct_not_directional_score():
    result = analyze_fx_daily_snapshot(fixture(), now=NOW)
    eurjpy = result["pair_returns_pct"]["EUR/JPY"]
    assert eurjpy > 0
    assert result["currencies"]["EUR"] > result["currencies"]["JPY"]
    assert result["top10"][0]["pair"] == "EUR/JPY"
    assert all(
        a["change_pct"] >= b["change_pct"]
        for a, b in zip(result["top10"], result["top10"][1:])
    )
    assert all(x["pair"] in OFFICIAL_PAIRS for x in result["top10"])


def test_atomic_rejection_missing_extra_and_wrong_state():
    for change, why in [
        (lambda p: p["pairs"].pop(OFFICIAL_PAIRS[0]), "INCOMPLETE_28_PAIR_UNIVERSE"),
        (lambda p: p["pairs"].update({"EUR/ABC": {}}), "INCOMPLETE_28_PAIR_UNIVERSE"),
        (lambda p: p.update({"state": "VALIDATED_DAILY"}), "INVALID_CONTRACT"),
        (lambda p: p.update({"schema": "INVALID"}), "INVALID_CONTRACT"),
    ]:
        snap = fixture()
        change(snap)
        result = analyze_fx_daily_snapshot(snap, now=NOW)
        assert result["state"] == "BLOCKED"
        assert result["reason"] == why
        assert result["currencies"] == {}
        assert result["pair_returns_pct"] == {}
        assert result["top10"] == []
        assert result["publishable"] is False


@pytest.mark.parametrize("mutate,reason", [
    (lambda x: x.update({"source":"OTHER"}), "QUOTE_OR_SOURCE_INVALID"),
    (lambda x: x.update({"bid": None}), "QUOTE_FIELDS_INVALID"),
    (lambda x: x.update({"ask": False}), "QUOTE_FIELDS_INVALID"),
    (lambda x: x.update({"bid": float("nan")}), "QUOTE_FIELDS_INVALID"),
    (lambda x: x.update({"ask": 10**500}), "QUOTE_FIELDS_INVALID"),
    (lambda x: x.update({"bid": -1.0}), "QUOTE_FIELDS_INVALID"),
    (lambda x: x.update({"previous_close": 0.0}), "QUOTE_FIELDS_INVALID"),
    (lambda x: x.update({"observed_at": "2026-11-04 12:00"}), "QUOTE_FIELDS_INVALID"),
    (lambda x: x.update({"bid": 1.1, "ask": 1.0}), "BID_ASK_INVERTED"),
    (lambda x: x.update({"bid": 0.90, "ask": 1.10}), "SPREAD_TOO_WIDE"),
    (lambda x: x.update({"reference_at": NOW.isoformat()}), "QUOTE_TIME_INVALID"),
    (lambda x: x.update({"observed_at": (NOW + timedelta(seconds=1)).isoformat()}), "QUOTE_TIME_INVALID"),
    (lambda x: x.update({"observed_at": (NOW-timedelta(minutes=25)).isoformat()}), "QUOTE_TIME_INVALID"),
    (lambda x: x.update({"reference_at": (NOW-timedelta(days=8)).isoformat()}), "REFERENCE_STALE_OR_FUTURE"),
])
def test_single_corrupt_quote_blocks_all_28(mutate, reason):
    sample = fixture()
    mutate(sample["pairs"][OFFICIAL_PAIRS[0]])
    result = analyze_fx_daily_snapshot(sample, now=NOW)
    assert result["reason"] == reason
    assert result["complete_pairs"] == 0
    assert result["top10"] == []


def test_non_overlapping_quotes_rejected_without_partial_ranking():
    sample=fixture()
    sample["pairs"][OFFICIAL_PAIRS[0]]["observed_at"] = (NOW - timedelta(minutes=2,seconds=35)).isoformat()
    assert analyze_fx_daily_snapshot(sample, now=NOW)["reason"] == "MIXED_QUOTE_TIMES"


def test_mixed_reference_sessions_rejected():
    sample=fixture()
    sample["pairs"][OFFICIAL_PAIRS[0]]["reference_at"] = (NOW - timedelta(days=2)).isoformat()
    assert analyze_fx_daily_snapshot(sample, now=NOW)["reason"] == "MIXED_REFERENCE_SESSION"


def test_one_abnormal_cross_disagrees_with_other_seven_and_blocks():
    sample=fixture()
    first=sample["pairs"][OFFICIAL_PAIRS[0]]
    first["bid"] *= 1.04
    first["ask"] *= 1.04
    result=analyze_fx_daily_snapshot(sample, now=NOW)
    assert result["reason"] == "CROSS_RATE_INCONSISTENCY"
    assert result["max_consistency_residual_log_pp"] > 0.3
    assert result["complete_pairs"] == 0
    assert result["top10"] == []


@pytest.mark.parametrize("snapshot_age", [timedelta(seconds=-1), timedelta(minutes=16)])
def test_stale_future_snapshot_never_claims_current_market(snapshot_age):
    sample=fixture()
    sample["as_of"]=(NOW - snapshot_age).isoformat()
    assert analyze_fx_daily_snapshot(sample, now=NOW)["reason"] == "STALE_OR_FUTURE_SNAPSHOT"


def test_naive_time_and_invalid_now_fail_closed():
    sample=fixture()
    sample["as_of"] = "2026-11-04T13:00:00"
    assert analyze_fx_daily_snapshot(sample, now=NOW)["reason"] == "STALE_OR_FUTURE_SNAPSHOT"
    with pytest.raises(ValueError):
        analyze_fx_daily_snapshot(fixture(), now=NOW.replace(tzinfo=None))


def test_old_cached_september_dataset_cannot_pass_new_contract():
    sample={"pairs": {"EUR/USD": {"change_pct": 0.4}},
            "updated_at": "2026-09-17T06:28:09+00:00"}
    result=analyze_fx_daily_snapshot(sample, now=NOW)
    assert result["state"] == "BLOCKED"
    assert result["publishable"] is False


def test_valid_fixture_isolated_and_never_mutates_input():
    sample=fixture()
    before=deepcopy(sample)
    analyze_fx_daily_snapshot(sample, now=NOW)
    assert sample == before


def test_research_contract_is_incompatible_with_live_daily_ui_gate():
    from atlasquant_trader_radar_compact_ui import _daily, trader_radar_html
    result=analyze_fx_daily_snapshot(fixture(), now=NOW)
    assert result["state"]=="RESEARCH_ONLY"
    assert _daily(result)["pairs"] == {}
    html=trader_radar_html(selected="radar",daily_data=result)
    assert "Top 10 aguardando" in html
    assert "Dados diários ainda não conectados" in html
    assert "Como será calculada a força das moedas?" in html
    assert "coerência entre cruzamentos" in html
    assert '<details class="aqr-guide" aria-label="Metodologia da força das moedas">' in html


def test_snapshot_max_age_cannot_hide_old_individual_quotes():
    sample=fixture()
    sample["as_of"]=NOW.isoformat()
    for item in sample["pairs"].values():
        item["observed_at"]=(NOW-timedelta(minutes=15,seconds=2)).isoformat()
    assert analyze_fx_daily_snapshot(sample,now=NOW)["reason"]=="QUOTE_TIME_INVALID"


def test_no_allowed_source_is_automatically_trusted():
    sample=fixture()
    sample["source"]="LIVE_PROVIDER"
    for item in sample["pairs"].values():
        item["source"]="LIVE_PROVIDER"
    result=analyze_fx_daily_snapshot(sample,now=NOW)
    assert result["state"]=="RESEARCH_ONLY"
    assert not result["provider_authenticated"]
    assert not result["publishable"]
