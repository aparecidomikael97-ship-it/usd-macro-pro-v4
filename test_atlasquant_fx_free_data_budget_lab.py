"""No-network quota math for free-tier FX research, not a data connection."""
import pytest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_fx_free_data_budget_lab import (
    SCHEMA, EUR_ANCHORS, estimate_free_fx_collection,
)


def test_28_m15_cannot_fit_basic_daily_limit():
    r = estimate_free_fx_collection(OFFICIAL_PAIRS, poll_minutes=15)
    assert r["schema"] == SCHEMA
    assert r["state"] == "BLOCKED"
    assert r["reason"] == "EXCEEDS_FREE_DAILY_CREDITS"
    assert r["polls_per_24h"] == 96
    assert r["credits_per_24h"] == 2688
    assert r["minute_quota_windows_for_all_pairs"] == 4
    assert not r["fits_daily_credit_budget"]
    assert not r["fits_one_minute_capture"]
    assert r["all_28_direct_pair_slots"]
    assert not r["market_data_connected"]
    assert not r["publishable"]


def test_28_hourly_fits_day_but_not_synchronized_minute():
    r = estimate_free_fx_collection(OFFICIAL_PAIRS, poll_minutes=60)
    assert r["credits_per_24h"] == 672
    assert r["fits_daily_credit_budget"]
    assert not r["fits_one_minute_capture"]
    assert r["state"] == "BLOCKED"
    assert r["reason"] == "CANNOT_COLLECT_WITHIN_ONE_MINUTE_QUOTA"
    assert not r["operational_m15_radar_ready"]


def test_seven_eur_anchors_fit_only_internal_non_display_research():
    r = estimate_free_fx_collection(sorted(EUR_ANCHORS), poll_minutes=15)
    assert len(EUR_ANCHORS) == 7
    assert r["state"] == "RESEARCH_CAPACITY_ONLY"
    assert r["credits_per_24h"] == 672
    assert r["remaining_credits_per_24h"] == 128
    assert r["fits_one_minute_capture"]
    assert r["seven_eur_anchor_slots"]
    assert not r["all_28_direct_pair_slots"]
    assert r["other_crosses_mathematically_derivable"] == 21
    assert not r["derived_crosses_are_independent_quotes"]
    assert not r["data_coverage_verified"]
    assert not r["display_authorized"]
    assert not r["provider_authenticated"]
    assert not r["trade_authorized"]


def test_eight_pairs_fit_capacity_but_nine_over_day_limit():
    good = estimate_free_fx_collection(OFFICIAL_PAIRS[:8], poll_minutes=15)
    bad = estimate_free_fx_collection(OFFICIAL_PAIRS[:9], poll_minutes=15)
    assert good["credits_per_24h"] == 768
    assert good["state"] == "RESEARCH_CAPACITY_ONLY"
    assert not good["seven_eur_anchor_slots"]
    assert good["other_crosses_mathematically_derivable"] == 0
    assert bad["credits_per_24h"] == 864
    assert bad["state"] == "BLOCKED"
    assert bad["reason"] == "EXCEEDS_FREE_DAILY_CREDITS"


@pytest.mark.parametrize("symbols,minutes", [
    ([], 15), (["EUR/USD", "EUR/USD"], 15),
    (["USD/EUR"], 15), (["EUR/XXX"], 15),
    ("EUR/USD", 15), (None, 15), ([123], 15),
    (OFFICIAL_PAIRS, 0), (OFFICIAL_PAIRS, True),
    (OFFICIAL_PAIRS, -15), (OFFICIAL_PAIRS, 17),
    (OFFICIAL_PAIRS, 1500), (OFFICIAL_PAIRS, 15.0),
])
def test_invalid_or_noncanonical_requests_are_atomic_block(symbols, minutes):
    r = estimate_free_fx_collection(symbols, poll_minutes=minutes)
    assert r["state"] == "BLOCKED"
    assert r["reason"] == "INVALID_RESEARCH_REQUEST"
    assert not r["publishable"]
    assert not r["market_data_connected"]


def test_never_grants_market_or_licensing_authority():
    for symbols in (sorted(EUR_ANCHORS), OFFICIAL_PAIRS[:8], OFFICIAL_PAIRS):
        r = estimate_free_fx_collection(symbols, poll_minutes=15)
        assert not any(r[key] for key in (
            "publishable", "display_authorized", "provider_authenticated",
            "data_coverage_verified", "price_accuracy_verified",
            "market_data_connected", "trade_authorized", "operational_m15_radar_ready",
        ))
