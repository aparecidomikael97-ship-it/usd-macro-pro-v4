from atlasquant_gate_chain import evaluate_gate_chain,execution_gate_passed
BASE={"DATA":"PASS","DIRECTION":"PASS_LONG","MACRO":"NEUTRAL","STRATEGY":"TRIGGERED","TRIGGER":"CONFIRMED","SESSION":"OPTIMAL","NEWS":"CLEAR","MARKET_CONDITION":"NORMAL","RISK":"APPROVED"}
def test_neutral_macro_waits_by_default(): assert evaluate_gate_chain(BASE)["overall"]=="WAIT"
def test_strategy_can_explicitly_allow_neutral_macro(): assert execution_gate_passed(evaluate_gate_chain(BASE,macro_policy="PASS"))
def test_strategy_can_block_divergent_macro():
 x=dict(BASE); x["MACRO"]="DIVERGENT"; assert evaluate_gate_chain(x,macro_policy="BLOCK")["overall"]=="BLOCKED"
