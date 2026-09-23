from atlasquant_dow_segment_analysis import segment_dow_evidence,dow_research_report

def row(pair,strategy,tf,session,aligned,r):
 return {"pair":pair,"strategy":strategy,"timeframe":tf,"session":session,"dow_aligned":aligned,"net_r":r}

def test_segments_pair_without_cross_contamination():
 rows=[row("EURUSD","FVG","M15","LONDON",True,1) for _ in range(2)]
 rows += [row("EURUSD","FVG","M15","LONDON",False,-1) for _ in range(2)]
 rows += [row("GBPUSD","FVG","M15","LONDON",True,-2)]
 out=segment_dow_evidence(rows,dimension="pair",min_per_cohort=2)
 eur=next(x for x in out["segments"] if x["pair"]=="EURUSD")
 gbp=next(x for x in out["segments"] if x["pair"]=="GBPUSD")
 assert eur["sample_sufficient"] is True and eur["observed_expectancy_delta_r"]==2.0
 assert gbp["sample_sufficient"] is False and gbp["observed_expectancy_delta_r"] is None

def test_invalid_dimension_is_rejected():
 try:segment_dow_evidence([],dimension="profit")
 except ValueError:pass
 else:raise AssertionError("must reject unsupported dimension")

def test_report_covers_approved_dimensions_and_never_changes_model():
 rows=[row("EURUSD","AMD_PO3","H1","NEW_YORK",True,1)]
 r=dow_research_report(rows,min_per_cohort=1)
 assert set(r["by_dimension"])=={"pair","strategy","timeframe","session"}
 assert r["automatic_model_selection"] is False
 assert r["quality_score_change_allowed"] is False
 assert r["gate_change_allowed"] is False
 assert r["real_orders_enabled"] is False

def test_unresolved_results_are_not_counted():
 out=segment_dow_evidence([{"pair":"EURUSD","dow_aligned":True,"net_r":None}],dimension="pair")
 assert out["segments"]==[]
