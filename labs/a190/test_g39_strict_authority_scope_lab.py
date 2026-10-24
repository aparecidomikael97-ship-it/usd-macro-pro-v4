"""G39: opt-in exact owner tenant workspace binding before any adapter access.

LAB candidate only; no real trust root and no SEND capability enabled.
Legacy mode remains for G38 RED comparators, not for production admission.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

SCOPE=Scope("g39-auth-owner","g39-auth-tenant","g39-auth-workspace")
NOW=datetime(2026,10,24,20,tzinfo=timezone.utc)
WORKER="g39-synthetic-worker"

class Trap:
    def __init__(self):self.lookups=0
    @property
    def send(self):
        self.lookups+=1
        raise AssertionError("G39_EXTERNAL_SEND_PROHIBITED")

class G39StrictAuthorityScope(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix="g39-auth-")
        self.addCleanup(tmp.cleanup)
        self.store=SQLiteChatStore(Path(tmp.name)/"real.sqlite3")
        self.addCleanup(self.store.close)
        self.outbox=ExecutionOutbox(self.store,SCOPE,strict_authority_scope_lab=True)
        self.adapter=Trap()

    def claim(self):
        row=self.outbox.enqueue(intent_ref="g39-intent",
            action="synthetic_no_provider",payload={"amount_minor":1000},
            aggregate_key="g39-aggregate",policy_version="p1",
            authorization_ref="a1",created_at=NOW,
            valid_until=NOW+timedelta(minutes=5))
        item=self.outbox.claim_next(WORKER,now=NOW,lease_seconds=60)
        self.assertEqual(row["idempotency_key"],item["idempotency_key"])
        return item

    def auth(self,**changes):
        value=dict(allowed=True,actor_id=SCOPE.owner_id,
            tenant_id=SCOPE.tenant_id,workspace_id=SCOPE.workspace_id,
            policy_version="p1",authorization_ref="a1")
        value.update(changes)
        return value

    def dispatch(self,row,auth):
        result=self.outbox.dispatch_claimed(
            row["idempotency_key"],worker_id=WORKER,
            authorize=lambda _:auth,adapter=self.adapter,
            now=NOW+timedelta(seconds=1))
        self.assertEqual(self.adapter.lookups,0)
        self.assertEqual(self.outbox.effect_count(),0)
        return result

    def test_01_missing_tenant_denies_before_witness(self):
        row=self.claim()
        a=self.auth()
        del a["tenant_id"]
        result=self.dispatch(row,a)
        self.assertEqual(result["state"],"REVOKED")
        self.assertEqual(result["last_error"],"TENANT_ID_REQUIRED")
        print("G39_AUTH_SCOPE_GREEN=MISSING_TENANT_DENIED_NO_ADAPTER")

    def test_02_missing_workspace_denies_before_witness(self):
        row=self.claim()
        a=self.auth()
        del a["workspace_id"]
        result=self.dispatch(row,a)
        self.assertEqual(result["last_error"],"WORKSPACE_ID_REQUIRED")
        print("G39_AUTH_WORKSPACE_GREEN=MISSING_WORKSPACE_DENIED_NO_ADAPTER")

    def test_03_empty_tenant_denies(self):
        row=self.claim()
        self.assertEqual(self.dispatch(row,self.auth(tenant_id=""))["last_error"],"TENANT_ID_REQUIRED")

    def test_04_empty_workspace_denies(self):
        row=self.claim()
        self.assertEqual(self.dispatch(row,self.auth(workspace_id=""))["last_error"],"WORKSPACE_ID_REQUIRED")

    def test_05_wrong_tenant_denies(self):
        row=self.claim()
        self.assertEqual(self.dispatch(row,self.auth(tenant_id="other"))["last_error"],"TENANT_ID_MISMATCH")

    def test_06_wrong_workspace_denies(self):
        row=self.claim()
        self.assertEqual(self.dispatch(row,self.auth(workspace_id="other"))["last_error"],"WORKSPACE_ID_MISMATCH")

    def test_07_wrong_actor_denies(self):
        row=self.claim()
        self.assertEqual(self.dispatch(row,self.auth(actor_id="other"))["last_error"],"ACTOR_MISMATCH")

    def test_08_matching_complete_scope_still_needs_external_witness(self):
        row=self.claim()
        result=self.dispatch(row,self.auth())
        self.assertEqual(result["state"],"UNCERTAIN")
        self.assertEqual(result["last_error"],"FIRST_ATTEMPT_WITNESS_UNVERIFIED_NO_SEND")
        print("G39_CORRECT_SCOPE_GREEN=UNCERTAIN_NOT_SEND")

    def test_09_strict_option_must_be_boolean(self):
        with self.assertRaises(TypeError):
            ExecutionOutbox(self.store,SCOPE,strict_authority_scope_lab=1)

    def test_10_callback_failure_is_revoked(self):
        row=self.claim()
        result=self.outbox.dispatch_claimed(row["idempotency_key"],
            worker_id=WORKER,authorize=lambda _:(_ for _ in ()).throw(
                RuntimeError("synthetic unavailable")),
            adapter=self.adapter,now=NOW+timedelta(seconds=1))
        self.assertEqual(result["last_error"],"AUTHORITY_REVALIDATION_FAILED")
        self.assertEqual(self.adapter.lookups,0)

    def test_11_legacy_missing_scope_behavior_not_silently_claimed_fixed(self):
        legacy=ExecutionOutbox(self.store, SCOPE)
        self.assertFalse(legacy._strict_authority_scope_lab)
        self.assertTrue(self.outbox._strict_authority_scope_lab)

    def test_12_no_external_send_even_with_full_authority(self):
        row=self.claim()
        result=self.dispatch(row,self.auth())
        self.assertFalse(result["executes_action"])
        self.assertEqual(self.adapter.lookups,0)
        self.assertEqual(self.outbox.effect_count(),0)

if __name__=="__main__":unittest.main()
