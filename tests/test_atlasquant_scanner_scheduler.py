from datetime import datetime,timezone,timedelta
from atlasquant_scanner_scheduler import build_scan_plan, plan_summary

NOW=datetime(2026,9,23,12,0,tzinfo=timezone.utc)

def test_plan_always_contains_28_and_three_hot_by_default():
    jobs=build_scan_plan({},{"EUR/USD":99,"GBP/JPY":98,"AUD/NZD":97},now=NOW)
    s=plan_summary(jobs)
    assert s["universe"]==28 and s["hot"]==3 and s["background"]==25
    assert s["automatic_execution_enabled"] is False

def test_hot_and_background_use_different_cadence():
    stamp=(NOW-timedelta(minutes=100)).timestamp()
    fetch={j:{"m15":stamp} for j in ("EUR/USD","GBP/JPY","AUD/NZD","USD/CHF")}
    jobs=build_scan_plan(fetch,{"EUR/USD":99,"GBP/JPY":98,"AUD/NZD":97},now=NOW)
    by={j.display_pair:j for j in jobs}
    assert by["EUR/USD"].tier=="HOT" and by["EUR/USD"].due is True
    assert by["USD/CHF"].tier=="BACKGROUND" and by["USD/CHF"].due is False

def test_future_timestamp_fails_closed_as_due():
    future=(NOW+timedelta(minutes=5)).timestamp()
    jobs=build_scan_plan({"EUR/USD":{"m15":future}},{"EUR/USD":99},now=NOW)
    eur=next(j for j in jobs if j.display_pair=="EUR/USD")
    assert eur.age_minutes is None and eur.due is True
