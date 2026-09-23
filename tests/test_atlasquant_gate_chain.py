from atlasquant_gate_chain import evaluate_gate_chain,execution_gate_passed

def full():
 return {"DATA":"PASS","DIRECTION":"PASS_SHORT","MACRO":"ALIGNED_SHORT","STRATEGY":"TRIGGERED",
 "TRIGGER":"CONFIRMED","SESSION":"OPTIMAL","NEWS":"CLEAR","MARKET_CONDITION":"NORMAL","RISK":"APPROVED"}

def test_full_chain_passes():
 r=evaluate_gate_chain(full()); assert execution_gate_passed(r)

def test_unknown_critical_gate_blocks():
 g=full(); del g["RISK"]; r=evaluate_gate_chain(g)
 assert r["overall"]=="BLOCKED" and "RISK_GATE_UNKNOWN" in r["hard_blocks"]

def test_news_lock_blocks_even_everything_else_passes():
 g=full(); g["NEWS"]="LOCKED"; assert evaluate_gate_chain(g)["overall"]=="BLOCKED"

def test_waiting_trigger_waits_not_passes():
 g=full(); g["TRIGGER"]="WAITING"; assert evaluate_gate_chain(g)["overall"]=="WAIT"
