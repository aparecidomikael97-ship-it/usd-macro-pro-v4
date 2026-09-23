from datetime import datetime, timezone, timedelta
from atlasquant_instrument_registry import FX_28
from atlasquant_legacy_scanner_adapter import coverage_from_legacy_state

NOW = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)

def _raw(minutes=10, available=True):
    return {
        "m15_fetched_at": (NOW - timedelta(minutes=minutes)).timestamp(),
        "tecnico": {"disponivel": available},
    }

def test_legacy_seven_major_state_is_truthfully_seven_of_28():
    majors = ("EUR/USD","GBP/USD","AUD/USD","NZD/USD","USD/JPY","USD/CHF","USD/CAD")
    state = {"resultados": {p: _raw() for p in majors}}
    out = coverage_from_legacy_state(state, now=NOW)
    assert out["healthy"] == 7
    assert out["claim_28_of_28"] is False
    assert len(out["missing"]) == 21

def test_full_legacy_state_can_prove_28_only_when_fresh():
    state = {"resultados": {s: _raw() for s in FX_28}}
    out = coverage_from_legacy_state(state, now=NOW)
    assert out["healthy"] == 28
    assert out["claim_28_of_28"] is True

def test_future_or_boundary_timestamp_fails_closed():
    state = {"resultados": {s: _raw() for s in FX_28}}
    state["resultados"][FX_28[0]] = _raw(minutes=60)
    state["resultados"][FX_28[1]] = {
        "m15_fetched_at": (NOW + timedelta(minutes=1)).timestamp(),
        "tecnico": {"disponivel": True},
    }
    out = coverage_from_legacy_state(state, now=NOW)
    assert out["healthy"] == 26
    assert out["claim_28_of_28"] is False
