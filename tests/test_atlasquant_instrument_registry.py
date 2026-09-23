from atlasquant_instrument_registry import (
    FX_28, FX_CURRENCIES, FX_INSTRUMENTS, get_fx_instrument, normalize_fx_symbol,
)

def test_fx_universe_is_exactly_28_unique_combinations():
    assert len(FX_CURRENCIES) == 8
    assert len(FX_28) == 28
    assert len(set(FX_28)) == 28
    assert len({frozenset((x.base, x.quote)) for x in FX_INSTRUMENTS}) == 28

def test_every_currency_pair_combination_exists_once():
    expected = {
        frozenset((a, b))
        for idx, a in enumerate(FX_CURRENCIES)
        for b in FX_CURRENCIES[idx + 1:]
    }
    actual = {frozenset((x.base, x.quote)) for x in FX_INSTRUMENTS}
    assert actual == expected

def test_normalization_and_canonical_id():
    assert normalize_fx_symbol("eur/usd") == "EURUSD"
    assert normalize_fx_symbol("FX:GBPJPY") == "GBPJPY"
    assert get_fx_instrument("usd-jpy").canonical_id == "FX:USDJPY"
