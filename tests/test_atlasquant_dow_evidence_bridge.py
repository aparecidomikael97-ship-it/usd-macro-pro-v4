from atlasquant_dow_evidence_bridge import join_dow_outcomes

def test_strict_identity_join_carries_resolved_result():
 r=join_dow_outcomes([{"opportunity_id":"o1","pair":"EURUSD","dow_aligned":True}],
 [{"opportunity_id":"o1","result_id":"r1","net_r":1.2,"outcome":"WIN"}])
 assert r["joined_count"]==1 and r["joined"][0]["net_r"]==1.2
 assert r["fuzzy_matching"] is False and r["real_orders_enabled"] is False

def test_missing_identity_or_outcome_is_excluded():
 r=join_dow_outcomes([{"pair":"EURUSD"},{"opportunity_id":"o2"}],[])
 assert r["joined_count"]==0
 assert r["excluded_no_identity"]==1 and r["excluded_missing_outcome"]==1

def test_duplicate_result_identity_is_ambiguous_and_excluded():
 obs=[{"paper_request_id":"p1","dow_aligned":True}]
 outcomes=[{"paper_request_id":"p1","net_r":1},{"paper_request_id":"p1","net_r":-1}]
 r=join_dow_outcomes(obs,outcomes)
 assert r["joined_count"]==0 and r["excluded_ambiguous_identity"]==1

def test_no_time_nearest_or_pair_only_join():
 r=join_dow_outcomes([{"opportunity_id":"x","pair":"EURUSD","observed_at":"2026-01-01"}],
 [{"opportunity_id":"y","pair":"EURUSD","observed_at":"2026-01-01","net_r":5}])
 assert r["joined_count"]==0
