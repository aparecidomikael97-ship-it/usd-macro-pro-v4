from atlasquant_radar_views import build_radar_views
def row():
 return {"pair":"EUR/USD","bias":"VENDA","quality":95,"data_score":100,"data_ready":True,"signal_status_code":"CONFIRMED","risk_gate":"APPROVED","gates":{"DATA":"PASS","DIRECTION":"PASS_SHORT","MACRO":"ALIGNED_SHORT","STRATEGY":"TRIGGERED","TRIGGER":"CONFIRMED","SESSION":"OPTIMAL","NEWS":"CLEAR","MARKET_CONDITION":"NORMAL","RISK":"APPROVED"}}
def test_protected_system_blocks_high_score_released_card():
 x=build_radar_views([row()],system_state="PROTECTED");r=x["TOP_AGORA"][0]
 assert not r["executable"] and "SYSTEM_HEALTH_PROTECTED" in r["hard_blocks"] and not x["execution_surface_enabled"]
def test_normal_system_can_preserve_model_executability():
 x=build_radar_views([row()],system_state="NORMAL");assert x["TOP_AGORA"][0]["executable"]
