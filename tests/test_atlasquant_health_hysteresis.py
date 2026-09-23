from atlasquant_health_hysteresis import stabilize_health

def test_escalation_is_immediate():
 r=stabilize_health("NORMAL",{"state":"PROTECTED"})
 assert r["state"]=="PROTECTED" and not r["new_entries_allowed"] and r["normal_streak"]==0

def test_one_healthy_tick_does_not_reopen_after_protection():
 r=stabilize_health("PROTECTED",{"state":"NORMAL"},normal_streak=0,recovery_checks=2)
 assert r["state"]=="PROTECTED" and r["recovery_pending"] and not r["new_entries_allowed"]
 r2=stabilize_health("PROTECTED",{"state":"NORMAL"},normal_streak=r["normal_streak"],recovery_checks=2)
 assert r2["state"]=="NORMAL" and not r2["recovery_pending"] and r2["new_entries_allowed"]

def test_bad_recovery_config_halts():
 r=stabilize_health("PROTECTED",{"state":"NORMAL"},recovery_checks=0)
 assert r["state"]=="HALTED" and not r["new_entries_allowed"]
