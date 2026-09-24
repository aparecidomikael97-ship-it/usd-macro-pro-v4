from atlasquant_instrument_registry import FX_CURRENCIES, FX_28
from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, universe_integrity

def test_legacy_and_canonical_universe_cannot_drift():
    assert CURRENCIES == FX_CURRENCIES
    assert tuple(p.replace("/","") for p in OFFICIAL_PAIRS) == FX_28
    assert universe_integrity()["valid"] is True
