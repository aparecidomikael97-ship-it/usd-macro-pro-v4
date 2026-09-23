from atlasquant_aion_connectors import aion_connector_registry,connector_action_policy,sanitize_connector_context

def test_youtube_and_spotify_are_priority_connectors():
 r=aion_connector_registry()["connectors"]
 assert "youtube" in r and "spotify" in r
 assert r["youtube"]["auth"]=="OAUTH" and r["spotify"]["auth"]=="OAUTH"

def test_read_can_be_allowed_only_when_connected():
 assert connector_action_policy("youtube","READ",connected=True)["allowed"]
 r=connector_action_policy("youtube","READ",connected=False)
 assert not r["allowed"] and r["reason"]=="CONNECTOR_NOT_CONNECTED"

def test_writes_require_confirmation():
 r=connector_action_policy("spotify","WRITE",connected=True)
 assert r["allowed"] and r["confirmation_required"] is True

def test_money_and_trading_are_blocked_from_connector_voice_path():
 for action in ("MONEY","TRADING"):
  r=connector_action_policy("youtube",action,connected=True)
  assert not r["allowed"] and r["confirmation_required"] is True
  assert r["real_orders_enabled"] is False and r["voice_can_authorize_orders"] is False

def test_secrets_are_removed_before_context_reaches_aion():
 clean=sanitize_connector_context({"title":"x","access_token":"secret","refresh_token":"secret2","api_key":"k"})
 assert clean=={"title":"x"}
