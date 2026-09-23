from atlasquant_radar_views import build_radar_views

def test_legacy_home_cannot_become_released_without_new_risk_gate():
    rows=[{"pair":"EUR/USD","bias":"COMPRA","quality":95,"data_score":100,"data_ready":True,
           "signal_status_code":"CONFIRMED","gate":"SEARCH_ENTRY","priority":99}]
    out=build_radar_views(rows)
    top=out["TOP_AGORA"][0]
    assert top["executable"] is False
    assert "RISK_GATE_AINDA_NAO_INTEGRADO" in top["hard_blocks"]

def test_explicit_risk_approval_can_release_only_with_other_conditions():
    rows=[{"pair":"EUR/USD","bias":"COMPRA","quality":88,"data_score":95,"data_ready":True,
           "signal_status_code":"CONFIRMED","gate":"PASS","priority":90,"risk_gate":"APPROVED"}]
    out=build_radar_views(rows)
    assert out["TOP_AGORA"][0]["executable"] is True
