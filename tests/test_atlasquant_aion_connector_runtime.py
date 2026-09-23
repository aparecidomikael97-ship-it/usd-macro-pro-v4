from datetime import datetime,timezone,timedelta
import pytest

from atlasquant_aion_action_approval import build_pending_action,approve_pending_action
from atlasquant_aion_connector_runtime import connector_runtime_status,build_connector_adapter

NOW=datetime(2026,9,23,18,tzinfo=timezone.utc)

class Resp:
 def __init__(self,status_code=200,data=None):
  self.status_code=status_code;self._data=data or {}
 def json(self):return self._data

def test_gateway_missing_is_not_configured():
 r=connector_runtime_status({})
 assert not r["gateway_configured"] and r["credentials_exposed"] is False

def test_production_rejects_plain_http_gateway():
 r=connector_runtime_status({"ATLASQUANT_ENV":"PRODUCTION","AION_CONNECTOR_GATEWAY_URL":"http://example.com"})
 assert not r["gateway_configured"] and not r["gateway_url_valid"]

def test_read_action_calls_gateway_without_approval():
 calls=[]
 def post(url,**kwargs):
  calls.append(kwargs)
  return Resp(200,{"ok":True,"result":{"items":[1]}})
 adapter=build_connector_adapter(
  env={"AION_CONNECTOR_GATEWAY_URL":"https://aion.example.com/connectors","AION_CONNECTOR_GATEWAY_TOKEN":"secret"},
  request_post=post,
 )
 out=adapter(provider="youtube",action_class="READ",payload={"question":"procure macro"})
 assert out["ok"] and out["provider"]=="youtube"
 assert calls[0]["headers"]["Authorization"]=="Bearer secret"
 assert calls[0]["json"]["approval_id"] is None

def test_write_action_requires_exact_approval():
 def post(url,**kwargs):return Resp(200,{"ok":True})
 adapter=build_connector_adapter(
  env={"AION_CONNECTOR_GATEWAY_URL":"https://aion.example.com/connectors"},
  request_post=post,
 )
 with pytest.raises(PermissionError):
  adapter(provider="spotify",action_class="WRITE",payload={"question":"toque x"})

 pending=build_pending_action(provider="spotify",action_class="WRITE",payload={"question":"toque x"},now=NOW)
 approved=approve_pending_action(pending,approved_by="Mikael",now=NOW+timedelta(seconds=1))
 out=adapter(provider="spotify",action_class="WRITE",payload={"question":"toque x"},approved_action=approved)
 assert out["ok"] and out["action_class"]=="WRITE"

def test_changed_payload_is_rejected_after_approval():
 adapter=build_connector_adapter(
  env={"AION_CONNECTOR_GATEWAY_URL":"https://aion.example.com/connectors"},
  request_post=lambda *a,**k:Resp(200,{"ok":True}),
 )
 pending=build_pending_action(provider="youtube",action_class="PUBLISH",payload={"title":"A"},now=NOW)
 approved=approve_pending_action(pending,approved_by="Mikael",now=NOW+timedelta(seconds=1))
 with pytest.raises(PermissionError):
  adapter(provider="youtube",action_class="PUBLISH",payload={"title":"B"},approved_action=approved)

def test_money_and_trading_are_always_blocked():
 adapter=build_connector_adapter(
  env={"AION_CONNECTOR_GATEWAY_URL":"https://aion.example.com/connectors"},
  request_post=lambda *a,**k:Resp(200,{"ok":True}),
 )
 for action in ("MONEY","TRADING","SECURITY"):
  with pytest.raises(PermissionError):
   adapter(provider="youtube",action_class=action,payload={})

def test_tokens_from_provider_response_are_stripped():
 adapter=build_connector_adapter(
  env={"AION_CONNECTOR_GATEWAY_URL":"https://aion.example.com/connectors"},
  request_post=lambda *a,**k:Resp(200,{"ok":True,"access_token":"x","refresh_token":"y"}),
 )
 out=adapter(provider="youtube",action_class="READ",payload={"question":"x"})
 assert "access_token" not in out and "refresh_token" not in out
