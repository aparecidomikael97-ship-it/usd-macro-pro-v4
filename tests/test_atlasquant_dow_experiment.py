from atlasquant_dow_experiment import dow_observation,compare_dow_cohorts

def test_observation_never_changes_live_decision():
 r=dow_observation({"pair":"EURUSD","quality_score":88,"executed":False},
 {"status":"CONFIRMED_CONTEXT","primary_trend":"BULLISH","secondary_trend":"BULLISH","aligned":True},
 {"net_r":1.5,"outcome":"WIN"})
 assert r["quality_score_original"]==88 and r["changed_live_decision"] is False
 assert r["research_only"] is True and r["real_orders_enabled"] is False

def test_small_sample_blocks_conclusion_and_weight_change():
 rows=[{"dow_aligned":True,"net_r":1},{"dow_aligned":False,"net_r":-1}]
 r=compare_dow_cohorts(rows,min_resolved=2)
 assert r["sample_sufficient"] is False and r["conclusion_allowed"] is False
 assert r["ranking_weight_change_allowed"] is False and r["live_gate_change_allowed"] is False

def test_sufficient_cohorts_report_descriptive_delta_only():
 rows=[]
 for _ in range(20):rows.append({"dow_aligned":True,"net_r":1.0})
 for _ in range(20):rows.append({"dow_aligned":False,"net_r":-0.5})
 r=compare_dow_cohorts(rows,min_resolved=20)
 assert r["sample_sufficient"] is True and r["observed_expectancy_delta_r"]==1.5
 assert r["ranking_weight_change_allowed"] is False and r["live_gate_change_allowed"] is False

def test_unresolved_rows_are_excluded():
 r=compare_dow_cohorts([{"dow_aligned":True,"net_r":None},{"dow_aligned":False,"net_r":"x"}])
 assert r["aligned"]["resolved"]==0 and r["not_aligned"]["resolved"]==0
