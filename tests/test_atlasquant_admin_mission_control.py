from atlasquant_admin_mission_control import admin_mission_control
def test_admin_never_promotes_protected_system():
 r=admin_mission_control({"state":"PROTECTED","management_mode":"SAFE_ONLY","reasons":["DATA"]},{"release_state":"RC_ELIGIBLE"})
 assert not r["rc_eligible"] and not r["new_entries_allowed"] and not r["production_promotion_allowed"] and not r["real_orders_enabled"]
def test_admin_normal_still_never_auto_promotes_production():
 r=admin_mission_control({"state":"NORMAL","management_mode":"NORMAL"},{"release_state":"RC_ELIGIBLE"})
 assert r["rc_eligible"] and r["production_promotion_allowed"] is False and r["real_orders_enabled"] is False
