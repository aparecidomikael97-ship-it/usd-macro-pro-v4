from atlasquant_evidence_isolation import isolate_environment
def test_paper_never_absorbs_backtest_or_live():
 rows=[{"environment":"PAPER","id":1},{"environment":"BACKTEST","id":2},{"environment":"LIVE","id":3}]
 r=isolate_environment(rows,"PAPER");assert not r["ok"] and [x["id"] for x in r["rows"]]==[1] and len(r["rejected"])==2
def test_unknown_expected_environment_fails_closed(): assert not isolate_environment([],"SIM")["ok"]
