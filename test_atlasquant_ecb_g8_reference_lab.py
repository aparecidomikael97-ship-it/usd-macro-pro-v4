"""Regression tests for offline ECB G8 reference adapter."""
from datetime import datetime, timezone
import pytest
from atlasquant_ecb_g8_reference_lab import analyze_ecb_reference_xml, SCHEMA
from atlasquant_fx_universe import OFFICIAL_PAIRS, CURRENCIES

NOW = datetime(2026, 11, 4, 13, tzinfo=timezone.utc)
OLD = dict(USD=1.10, JPY=160.0, GBP=.88, CHF=.94, AUD=1.64, CAD=1.52, NZD=1.79)
NEW = dict(USD=1.12, JPY=161.0, GBP=.86, CHF=.93, AUD=1.65, CAD=1.53, NZD=1.80)


def fixture(old=None, new=None, latest="2026-11-03", previous="2026-11-02"):
    def row(date, rates):
        return '<Cube time="' + date + '">' + "".join(
            '<Cube currency="' + c + '" rate="' + str(n) + '"/>' for c,n in rates.items()
        ) + '</Cube>'
    return ('<Envelope xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref"><Cube>'
            + row(latest, NEW if new is None else new)
            + row(previous, OLD if old is None else old)
            + '</Cube></Envelope>').encode()


def test_7_eur_fixes_derive_28_only_research():
    r=analyze_ecb_reference_xml(fixture(),now=NOW)
    assert r["schema"]==SCHEMA and r["state"]=="RESEARCH_ONLY"
    assert r["complete_pairs"]==28 and r["direct_eur_fixes"]==7
    assert r["derived_non_eur_crosses"]==21
    assert set(r["pair_returns_pct"])==set(OFFICIAL_PAIRS)
    assert set(r["rates"])==set(CURRENCIES)
    assert len(r["top10"])==10
    assert r["max_algebraic_residual_log_pp"]==0
    assert not r["publishable"] and not r["trade_authorized"]
    assert not r["provider_authenticated"] and not r["accuracy_verified"]
    assert not r["has_executable_bid_ask"]


def test_cross_orientation_and_strength():
    r=analyze_ecb_reference_xml(fixture(),now=NOW)
    assert r["pair_returns_pct"]["EUR/USD"]==pytest.approx((1.12/1.10-1)*100,abs=1e-6)
    assert r["pair_returns_pct"]["GBP/USD"]==pytest.approx(((1.12/.86)/(1.10/.88)-1)*100,abs=1e-6)
    assert r["currency_strength_log_pp"]["GBP"]>r["currency_strength_log_pp"]["USD"]
    assert sum(r["currency_strength_log_pp"].values())==pytest.approx(0,abs=1e-5)
    assert all(a["change_pct"]>=b["change_pct"] for a,b in zip(r["top10"],r["top10"][1:]))


@pytest.mark.parametrize("bad", [{}, {"USD":1.1}, {**NEW,"GBP":0},
                                {**NEW,"GBP":-1}, {**NEW,"GBP":"nan"},
                                {**NEW,"GBP":"error"}])
def test_missing_or_bad_currency_blocks_entire_ranking(bad):
    r=analyze_ecb_reference_xml(fixture(new=bad),now=NOW)
    assert r["state"]=="BLOCKED" and r["complete_pairs"]==0 and r["top10"]==[]


@pytest.mark.parametrize("data", [b"", b"not xml", b"<Envelope>", b"x"*600001, "text", None])
def test_bad_xml_never_publishable(data):
    r=analyze_ecb_reference_xml(data,now=NOW)
    assert r["state"]=="BLOCKED" and not r["publishable"]


def test_future_duplicate_and_stale():
    assert analyze_ecb_reference_xml(fixture(latest="2026-11-06"),now=NOW)["state"]=="BLOCKED"
    assert analyze_ecb_reference_xml(fixture(latest="2026-11-02"),now=NOW)["state"]=="BLOCKED"
    r=analyze_ecb_reference_xml(fixture(latest="2026-09-17",previous="2026-09-16"),now=NOW)
    assert r["state"]=="RESEARCH_ONLY" and r["reference_age_days"]>30
    assert not r["publishable"]
    with pytest.raises(ValueError):
        analyze_ecb_reference_xml(fixture(),now=NOW.replace(tzinfo=None))


def test_not_a_live_daily_ui_contract():
    from atlasquant_trader_radar_compact_ui import _daily
    r=analyze_ecb_reference_xml(fixture(),now=NOW)
    assert _daily(r)["pairs"]=={}
    assert r["reason"]=="REFERENCE_ONLY_NOT_TRADEABLE"
