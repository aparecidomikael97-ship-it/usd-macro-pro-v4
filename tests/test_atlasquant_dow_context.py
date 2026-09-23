from atlasquant_dow_context import dow_context,apply_dow_context

def test_aligned_primary_and_secondary_create_context_not_entry():
 r=dow_context(weekly="alta",daily="BULLISH",h4="COMPRA",h1="BUY")
 assert r["primary_trend"]=="BULLISH" and r["secondary_trend"]=="BULLISH"
 assert r["status"]=="CONFIRMED_CONTEXT"
 assert r["entry_setup"] is False and r["execution_authorized"] is False
 assert r["real_orders_enabled"] is False

def test_misaligned_secondary_waits():
 r=dow_context(weekly="BULLISH",daily="BULLISH",h4="BEARISH",h1="BEARISH")
 assert r["status"]=="WAIT" and "PRIMARY_SECONDARY_NOT_ALIGNED" in r["blockers"]

def test_unknown_structure_fails_closed():
 r=dow_context(weekly=None,daily="BULLISH",h4="BULLISH",h1="BULLISH")
 assert r["status"]=="INSUFFICIENT_DATA"
 assert r["execution_authorized"] is False

def test_cross_market_divergence_prevents_confirmation():
 r=dow_context(weekly="BEARISH",daily="BEARISH",h4="BEARISH",h1="BEARISH",
               confirmation={"available":True,"aligned":False,"source":"validated-related-market"})
 assert r["aligned"] is True and r["status"]=="WAIT"
 assert "CROSS_MARKET_DIVERGENCE" in r["evidence"]

def test_volume_is_optional_but_nonconfirming_valid_volume_waits():
 base=dow_context(weekly="BULLISH",daily="BULLISH",h4="BULLISH",h1="BULLISH")
 assert base["status"]=="CONFIRMED_CONTEXT"
 with_volume=dow_context(weekly="BULLISH",daily="BULLISH",h4="BULLISH",h1="BULLISH",
                         volume={"available":True,"supports_trend":False,"source":"validated-volume"})
 assert with_volume["status"]=="WAIT"

def test_attach_preserves_upstream_execution_and_score():
 row={"pair":"EURUSD","quality_score":82,"executable":False,"risk_gate":"BLOCKED"}
 ctx=dow_context(weekly="BULLISH",daily="BULLISH",h4="BULLISH",h1="BULLISH")
 out=apply_dow_context(row,ctx)
 assert out["quality_score"]==82 and out["executable"] is False and out["risk_gate"]=="BLOCKED"
 assert out["dow_status"]=="CONFIRMED_CONTEXT"
