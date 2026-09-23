from datetime import datetime,timezone,timedelta
import pytest
from atlasquant_aion_action_approval import build_pending_action,approve_pending_action,validate_adapter_execution

NOW=datetime(2026,9,23,18,tzinfo=timezone.utc)

def test_external_write_approval_is_exact_and_expiring():
 a=build_pending_action(provider="spotify",action_class="WRITE",payload={"question":"tocar playlist"},now=NOW,ttl_seconds=300)
 approved=approve_pending_action(a,approved_by="Mikael",now=NOW+timedelta(seconds=10))
 ok=validate_adapter_execution(approved,provider="spotify",payload={"question":"tocar playlist"},now=NOW+timedelta(seconds=20))
 assert ok["allowed"] and ok["real_orders_enabled"] is False

def test_payload_change_invalidates_approval():
 a=build_pending_action(provider="youtube",action_class="PUBLISH",payload={"title":"A"},now=NOW)
 approved=approve_pending_action(a,approved_by="Mikael",now=NOW+timedelta(seconds=1))
 r=validate_adapter_execution(approved,provider="youtube",payload={"title":"B"},now=NOW+timedelta(seconds=2))
 assert not r["allowed"] and "PAYLOAD_MISMATCH" in r["reasons"]

def test_expired_pending_action_cannot_be_approved():
 a=build_pending_action(provider="spotify",action_class="WRITE",payload={"x":1},now=NOW,ttl_seconds=30)
 with pytest.raises(ValueError):approve_pending_action(a,approved_by="Mikael",now=NOW+timedelta(seconds=31))

def test_read_action_does_not_create_pending_write_approval():
 with pytest.raises(ValueError):build_pending_action(provider="youtube",action_class="READ",payload={"q":"x"},now=NOW)
