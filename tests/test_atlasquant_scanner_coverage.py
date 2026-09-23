from atlasquant_instrument_registry import FX_28
from atlasquant_scanner_coverage import PairCoverage, scanner_coverage

def _row(symbol, *, analyzed=True, fresh=True, quality=True):
    return PairCoverage(symbol=symbol, analyzed=analyzed, data_fresh=fresh, quality_ok=quality)

def test_never_claims_28_when_only_seven_pairs_are_present():
    rows = {s: _row(s) for s in FX_28[:7]}
    result = scanner_coverage(rows)
    assert result["healthy"] == 7
    assert result["claim_28_of_28"] is False
    assert len(result["missing"]) == 21

def test_claims_28_only_when_every_pair_is_healthy():
    rows = {s: _row(s) for s in FX_28}
    result = scanner_coverage(rows)
    assert result["healthy"] == 28
    assert result["claim_28_of_28"] is True

def test_stale_pair_forces_fail_closed_coverage():
    rows = {s: _row(s) for s in FX_28}
    rows[FX_28[-1]] = _row(FX_28[-1], fresh=False)
    result = scanner_coverage(rows)
    assert result["healthy"] == 27
    assert result["claim_28_of_28"] is False
    assert FX_28[-1] in result["unhealthy"]
