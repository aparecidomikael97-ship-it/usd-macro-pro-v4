"""G64 RED-first: reject secrets emitted by opaque confirm-result __str__,
and bounded depth before any LAB BEGIN or partial staging.
Synthetic disposable SQLite only; markers below are FAKE and not credentials.
No customer, provider, Worker, send, remote effects, finance or deploy.
"""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import json,tempfile,unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

NOW=datetime(2026,10,25,23,tzinfo=timezone.utc)
SCOPE=Scope("g64-owner","g64-tenant","g64-workspace")
EVENT="g64-synthetic-event"
REF="g64-synthetic-only-effect"

class OpaqueString:
    def __init__(self,value):
        self.value=value
        self.calls=0
    def __str__(self):
        self.calls+=1
        return self.value

class BeginWatch:
    """Observe BEGIN without modifying its normal execution."""
    def __init__(self,real):
        self.real=real
        self.begins=0
    def execute(self,sql,*args,**kwargs):
        if sql=="BEGIN IMMEDIATE":
            self.begins+=1
        return self.real.execute(sql,*args,**kwargs)
    def __getattr__(self,name):
        return getattr(self.real,name)

def chain(depth,leaf="synthetic-leaf"):
    node=leaf
    for _ in range(depth):
        node=[node]
    return node

class G64ConfirmOpaqueAndDepth(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory(prefix="aion-g64-disposable-")
        self.addCleanup(folder.cleanup)
        self.store=SQLiteChatStore(Path(folder.name)/"synthetic.sqlite3")
        self.addCleanup(self.store.close)
        self.raw=self.store.db
        self.box=ExecutionOutbox(self.store,SCOPE)

    def counts(self):
        return tuple(self.raw.execute("SELECT COUNT(*) FROM "+name).fetchone()[0]
                     for name in ("action_decisions","action_outbox",
                                  "semantic_reservations_lab","action_effects"))

    def stage(self,extra=None,request="g64-request-A"):
        payload={"business_event_id":EVENT,"amount_minor":64}
        if extra:
            payload.update(extra)
        return self.box.enqueue(
            intent_ref=request,action="synthetic-no-network",
            payload=payload,aggregate_key="g64-aggregate",
            policy_version="p1",authorization_ref="synthetic-authority",
            created_at=NOW,valid_until=NOW+timedelta(minutes=5),
            semantic_event_id_lab=EVENT)

    def prepare(self):
        key=self.stage()["idempotency_key"]
        self.raw.execute(
            "UPDATE action_outbox SET state='UNCERTAIN' WHERE idempotency_key=?",
            (key,))
        self.raw.commit()
        return key

    def confirm(self,key,result):
        return self.box._confirm(key,effect_ref=REF,
                                 confirmed_at=NOW+timedelta(minutes=1),
                                 result=result)

    def test_01_opaque_str_fake_token_denied_before_begin(self):
        key=self.prepare()
        opaque=OpaqueString("sk"+"-G64FAKETOKEN123456789")
        watch=BeginWatch(self.raw)
        self.box.db=watch
        with self.assertRaisesRegex(ValueError,"G64_CONFIRM_SERIALIZED_PRIVACY_DENY"):
            self.confirm(key,{"result":{"opaque":opaque}})
        self.assertGreaterEqual(opaque.calls,1)
        self.assertEqual(watch.begins,0)
        self.assertEqual(self.counts(),(1,1,1,0))
        self.assertEqual(self.box.get(key)["state"],"UNCERTAIN")
        self.assertFalse(self.raw.in_transaction)
        print("G64_OPAQUE_TOKEN_GREEN=NO_LEDGER_OR_BEGIN")

    def test_02_opaque_str_bearer_denied_before_begin(self):
        key=self.prepare()
        watch=BeginWatch(self.raw)
        self.box.db=watch
        with self.assertRaisesRegex(ValueError,"G64_CONFIRM_SERIALIZED_PRIVACY_DENY"):
            self.confirm(key,{"opaque":[OpaqueString("Bearer G64FAKE123456789")]})
        self.assertEqual(watch.begins,0)
        self.assertEqual(self.counts(),(1,1,1,0))
        print("G64_OPAQUE_BEARER_GREEN=NO_LEDGER")

    def test_03_opaque_str_fake_secret_under_tuple_denied(self):
        key=self.prepare()
        with self.assertRaisesRegex(ValueError,"G64_CONFIRM_SERIALIZED_PRIVACY_DENY"):
            self.confirm(key,{"tuple":(OpaqueString("sk"+"-G64ANOTHERFAKE123456"),)})
        self.assertEqual(self.counts(),(1,1,1,0))

    def test_04_ordinary_opaque_string_confirmation_still_allowed(self):
        key=self.prepare()
        obj=OpaqueString("ordinary-synthetic-safe-description")
        done=self.confirm(key,{"result":{"text":obj}})
        self.assertEqual(done["state"],"CONFIRMED")
        row=self.raw.execute("SELECT data FROM action_effects").fetchone()
        self.assertEqual(json.loads(row["data"])["result"]["text"],
                         "ordinary-synthetic-safe-description")
        self.assertEqual(self.counts(),(1,1,1,1))
        print("G64_OPAQUE_SAFE_GREEN=LEGITIMATE_SYNTHETIC_CONFIRM")

    def test_05_plain_string_fake_secret_remains_redacted_not_denied(self):
        key=self.prepare()
        done=self.confirm(key,{"message":"Bearer G64FAKE123456"})
        self.assertEqual(done["state"],"CONFIRMED")
        body=self.raw.execute("SELECT data FROM action_effects").fetchone()["data"]
        self.assertNotIn("G64FAKE123456",body)
        self.assertEqual(self.counts(),(1,1,1,1))

    def test_06_deep_acyclic_confirmation_denied_before_begin(self):
        key=self.prepare()
        watch=BeginWatch(self.raw)
        self.box.db=watch
        with self.assertRaisesRegex(ValueError,"G64_EXCESSIVE_NESTING_DENY"):
            self.confirm(key,{"deep":chain(90)})
        self.assertEqual(watch.begins,0)
        self.assertEqual(self.counts(),(1,1,1,0))
        self.assertEqual(self.box.get(key)["state"],"UNCERTAIN")
        print("G64_DEEP_CONFIRM_GREEN=DENY_BEFORE_BEGIN")

    def test_07_deep_acyclic_enqueue_denied_before_begin(self):
        watch=BeginWatch(self.raw)
        self.box.db=watch
        with self.assertRaisesRegex(ValueError,"G64_EXCESSIVE_NESTING_DENY"):
            self.stage({"deep":chain(90)})
        self.assertEqual(watch.begins,0)
        self.assertEqual(self.counts(),(0,0,0,0))
        self.assertFalse(self.raw.in_transaction)
        print("G64_DEEP_ENQUEUE_GREEN=DENY_BEFORE_BEGIN")

    def test_08_moderate_depth_remains_valid(self):
        key=self.stage({"deep":chain(12)})["idempotency_key"]
        self.raw.execute("UPDATE action_outbox SET state='UNCERTAIN' WHERE idempotency_key=?",
                         (key,))
        self.raw.commit()
        self.confirm(key,{"deep":chain(12)})
        self.assertEqual(self.counts(),(1,1,1,1))
        print("G64_MODERATE_DEPTH_GREEN=VALID_DATA")

    def test_09_shared_acyclic_subobject_remains_valid(self):
        shared={"values":[1,2,3]}
        key=self.stage({"one":shared,"two":shared})["idempotency_key"]
        self.raw.execute("UPDATE action_outbox SET state='UNCERTAIN' WHERE idempotency_key=?",
                         (key,))
        self.raw.commit()
        done=self.confirm(key,{"one":shared,"two":shared})
        self.assertEqual(done["state"],"CONFIRMED")
        self.assertEqual(self.counts(),(1,1,1,1))

    def test_10_g63_confirm_cycle_still_uses_original_specific_denial(self):
        key=self.prepare()
        cyclic={}
        cyclic["self"]=cyclic
        with self.assertRaisesRegex(ValueError,"G63_CYCLIC_RESULT_DENY"):
            self.confirm(key,{"deep":cyclic})
        self.assertEqual(self.counts(),(1,1,1,0))

    def test_11_g62_enqueue_cycle_still_uses_original_specific_denial(self):
        obj=[]
        obj.append(obj)
        with self.assertRaisesRegex(ValueError,"G62_CYCLIC_PAYLOAD_DENY"):
            self.stage({"loop":obj})
        self.assertEqual(self.counts(),(0,0,0,0))

    def test_13_depth_boundary_64_container_levels_allowed(self):
        # Root mapping (level 1) + 63 nested lists = 64 levels.
        key=self.stage({"deep":chain(63)})["idempotency_key"]
        self.raw.execute(
            "UPDATE action_outbox SET state='UNCERTAIN' WHERE idempotency_key=?",
            (key,))
        self.raw.commit()
        done=self.confirm(key,{"deep":chain(63)})
        self.assertEqual(done["state"],"CONFIRMED")
        self.assertEqual(self.counts(),(1,1,1,1))
        print("G64_DEPTH_64_GREEN=BOUNDARY_ALLOWED")

    def test_14_depth_boundary_65_container_levels_denied(self):
        # Root mapping + 64 nested lists = 65 container levels.
        watch=BeginWatch(self.raw)
        self.box.db=watch
        with self.assertRaisesRegex(ValueError,"G64_EXCESSIVE_NESTING_DENY"):
            self.stage({"deep":chain(64)})
        self.assertEqual(watch.begins,0)
        self.assertEqual(self.counts(),(0,0,0,0))
        print("G64_DEPTH_65_GREEN=BOUNDARY_DENIED")

    def test_15_hidden_deep_value_rejected_before_redact(self):
        key=self.prepare()
        watch=BeginWatch(self.raw)
        self.box.db=watch
        with self.assertRaisesRegex(ValueError,"G64_EXCESSIVE_NESTING_DENY"):
            self.confirm(key,{"password":chain(90)})
        self.assertEqual(watch.begins,0)
        self.assertEqual(self.counts(),(1,1,1,0))
        print("G64_HIDDEN_DEPTH_GREEN=NO_BYPASS")

    def test_16_existing_cyclic_confirmation_proves_zero_begin(self):
        key=self.prepare()
        obj={}
        obj["self"]=obj
        watch=BeginWatch(self.raw)
        self.box.db=watch
        with self.assertRaisesRegex(ValueError,"G63_CYCLIC_RESULT_DENY"):
            self.confirm(key,{"nested":obj})
        self.assertEqual(watch.begins,0)
        self.assertEqual(self.counts(),(1,1,1,0))
        print("G64_CYCLE_ZERO_BEGIN_GREEN=INSTRUMENTED")

    def test_12_no_result_confirmation_regression(self):
        key=self.prepare()
        done=self.confirm(key,None)
        self.assertEqual(done["state"],"CONFIRMED")
        self.assertEqual(json.loads(
            self.raw.execute("SELECT data FROM action_effects").fetchone()["data"]),{})
        self.assertEqual(self.counts(),(1,1,1,1))

if __name__=="__main__":
    unittest.main()
