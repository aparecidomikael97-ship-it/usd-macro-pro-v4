"""G65 RED FIRST: sensitive JSON key names, width/node budget, byte budget.

Disposable SQLite/synthetic markers only, no provider, SEND, Worker, secrets,
customers, funds, deployment or external authority.
"""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import json,tempfile,unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

NOW=datetime(2026,10,25,23,tzinfo=timezone.utc)
SCOPE=Scope("g65-owner","g65-tenant","g65-workspace")
EVENT="g65-fake-business-event"
REF="g65-fake-receipt"

def chain(n,leaf="safe"):
    node=leaf
    for _ in range(n):
        node=[node]
    return node

class BeginWatch:
    def __init__(self,real):
        self.real=real
        self.begins=0
    def execute(self,sql,*args,**kwargs):
        if sql=="BEGIN IMMEDIATE":
            self.begins+=1
        return self.real.execute(sql,*args,**kwargs)
    def __getattr__(self,name):
        return getattr(self.real,name)

class OneUseString:
    def __init__(self):
        self.calls=0
    def __str__(self):
        self.calls+=1
        return "safe-first" if self.calls==1 else "sk-G65UNEXPECTEDFAKE123456"

class G65KeyBudgetAndBoundary(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory(prefix="a190-g65-disposable-")
        self.addCleanup(t.cleanup)
        self.store=SQLiteChatStore(Path(t.name)/"test-only.sqlite3")
        self.addCleanup(self.store.close)
        self.raw=self.store.db
        self.box=ExecutionOutbox(self.store,SCOPE)

    def stage(self,extra=None,request="g65-request-A"):
        payload={"amount_minor":65,"business_event_id":EVENT}
        if extra:
            payload.update(extra)
        return self.box.enqueue(
            intent_ref=request,action="synthetic-no-external-provider",
            payload=payload,aggregate_key="g65-group",
            policy_version="p1",authorization_ref="fake-only",
            created_at=NOW,valid_until=NOW+timedelta(minutes=5),
            semantic_event_id_lab=EVENT)

    def uncertain(self):
        key=self.stage()["idempotency_key"]
        self.raw.execute(
            "UPDATE action_outbox SET state='UNCERTAIN' WHERE idempotency_key=?",
            (key,))
        self.raw.commit()
        return key

    def confirm(self,key,result):
        return self.box._confirm(key,effect_ref=REF,
                confirmed_at=NOW+timedelta(minutes=1),result=result)

    def counts(self):
        return tuple(self.raw.execute(
            "SELECT COUNT(*) FROM "+table).fetchone()[0]
            for table in ("action_decisions","action_outbox",
                          "semantic_reservations_lab","action_effects"))

    def watched_deny(self,run,code,expected_counts):
        w=BeginWatch(self.raw)
        self.box.db=w
        with self.assertRaisesRegex(ValueError,code):
            run()
        self.assertEqual(w.begins,0)
        self.assertEqual(self.counts(),expected_counts)
        self.assertFalse(self.raw.in_transaction)
        self.assertEqual(self.store.storage_health()["state"],"healthy")

    def test_01_direct_fake_secret_json_key_in_confirm_denied(self):
        key=self.uncertain()
        self.watched_deny(
            lambda:self.confirm(key,{"sk-G65FAKEKEY123456":"public"}),
            "G65_SENSITIVE_JSON_KEY_DENY",(1,1,1,0))
        print("G65_CONFIRM_KEY_GREEN=NO_SECRET_NAME_LEDGER")

    def test_02_nested_key_inside_tuple_confirm_denied(self):
        key=self.uncertain()
        self.watched_deny(
            lambda:self.confirm(key,{"values":({"Bearer G65FAKE123456":"x"},)}),
            "G65_SENSITIVE_JSON_KEY_DENY",(1,1,1,0))
        print("G65_TUPLE_KEY_GREEN=NO_BEGIN")

    def test_03_enqueue_fake_secret_json_key_denied_before_begin(self):
        self.watched_deny(
            lambda:self.stage({"sk-G65FAKESTAGINGKEY1234":"x"}),
            "G65_SENSITIVE_JSON_KEY_DENY",(0,0,0,0))
        print("G65_STAGING_KEY_GREEN=NO_RESERVATION")

    def test_04_normal_password_key_still_redacts_value(self):
        row=self.stage({"password":"synthetic-cleartext-marker"})
        self.assertEqual(row["enqueue_state"],"ENQUEUED")
        saved=self.raw.execute("SELECT data FROM action_decisions").fetchone()["data"]
        self.assertNotIn("synthetic-cleartext-marker",saved)
        self.assertEqual(json.loads(saved)["payload"]["password"],"[REDACTED]")

    def test_05_extremely_wide_enqueue_denied_by_node_budget(self):
        self.watched_deny(
            lambda:self.stage({"wide":list(range(4300))}),
            "G65_NODE_BUDGET_DENY",(0,0,0,0))
        print("G65_WIDE_STAGE_GREEN=NO_BEGIN")

    def test_06_extremely_wide_confirmation_denied(self):
        key=self.uncertain()
        self.watched_deny(
            lambda:self.confirm(key,{"wide":list(range(4300))}),
            "G65_NODE_BUDGET_DENY",(1,1,1,0))
        print("G65_WIDE_CONFIRM_GREEN=NO_EFFECT")

    def test_07_many_references_to_same_acyclic_object_have_budget(self):
        shared={"ok":"one"}
        wide=[shared for _ in range(4300)]
        self.watched_deny(
            lambda:self.stage({"wide":wide}),
            "G65_NODE_BUDGET_DENY",(0,0,0,0))
        print("G65_DAG_BUDGET_GREEN=REPEATED_WORK_BOUNDED")

    def test_08_moderate_width_still_allowed_and_idempotent(self):
        first=self.stage({"normal":list(range(512))})
        replay=self.stage({"normal":list(range(512))})
        self.assertEqual(first["idempotency_key"],replay["idempotency_key"])
        self.assertEqual(replay["enqueue_state"],"IDEMPOTENT")
        self.assertEqual(self.counts(),(1,1,1,0))
        print("G65_MODERATE_WIDTH_GREEN=IDEMPOTENT")

    def test_09_single_giant_string_enqueue_denied_by_bytes(self):
        self.watched_deny(
            lambda:self.stage({"blob":"x"*270000}),
            "G65_SERIALIZED_BYTES_DENY",(0,0,0,0))
        print("G65_STAGE_BYTES_GREEN=NO_BEGIN")

    def test_10_single_giant_string_confirm_denied_by_bytes(self):
        key=self.uncertain()
        self.watched_deny(
            lambda:self.confirm(key,{"blob":"x"*270000}),
            "G65_SERIALIZED_BYTES_DENY",(1,1,1,0))
        print("G65_CONFIRM_BYTES_GREEN=NO_BEGIN")

    def test_11_level_65_confirm_denied_with_zero_begin(self):
        key=self.uncertain()
        self.watched_deny(
            lambda:self.confirm(key,{"deep":chain(64)}),
            "G64_EXCESSIVE_NESTING_DENY",(1,1,1,0))
        print("G65_CONFIRM_DEPTH_65_GREEN=EXACT_BOUNDARY")

    def test_12_opaque_object_in_confirm_serializes_exactly_once(self):
        key=self.uncertain()
        obj=OneUseString()
        done=self.confirm(key,{"opaque":obj})
        self.assertEqual(obj.calls,1)
        self.assertEqual(done["state"],"CONFIRMED")
        data=json.loads(self.raw.execute("SELECT data FROM action_effects").fetchone()[0])
        self.assertEqual(data["opaque"],"safe-first")
        self.assertEqual(self.counts(),(1,1,1,1))
        print("G65_ONE_STR_GREEN=NO_SECOND_OPAQUE_CONVERSION")

    def test_13_shallow_cycle_specific_g63_code_unchanged(self):
        key=self.uncertain()
        cycle={}
        cycle["again"]=cycle
        self.watched_deny(
            lambda:self.confirm(key,{"loop":cycle}),
            "G63_CYCLIC_RESULT_DENY",(1,1,1,0))

    def test_14_extreme_cycle_at_depth_65_fails_closed(self):
        key=self.uncertain()
        circular=chain(63,leaf=[])
        leaf=circular
        for _ in range(63):
            leaf=leaf[0]
        leaf.append(circular)
        self.watched_deny(
            lambda:self.confirm(key,{"deep":circular}),
            "G64_EXCESSIVE_NESTING_DENY",(1,1,1,0))
        print("G65_DEPTH_CYCLE_GREEN=STABLE_FAIL_CLOSED_PRECEDENCE")

if __name__=="__main__":
    unittest.main()
