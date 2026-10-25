"""G66 RED-first: inherited sensitive field names, custom Mapping and UTF-8 boundaries.

Synthetic disposable SQLite only. All markers are fake strings, not secrets.
No external provider, Worker, SEND, customer data, funds or deployment.
"""
from collections import UserDict
from datetime import datetime,timedelta,timezone
from pathlib import Path
import json,tempfile,unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

NOW=datetime(2026,10,25,23,tzinfo=timezone.utc)
SCOPE=Scope("g66-owner","g66-tenant","g66-space")
EVENT="g66-fake-economic-event"
REF="g66-fake-ledger-effect"
MAX=262144

class SQLWatch:
    def __init__(self,db):
        self.db=db
        self.begins=0
        self.reservations=0
        self.rollbacks=0
    def execute(self,sql,*args,**kwargs):
        if sql=="BEGIN IMMEDIATE":
            self.begins+=1
        if "INSERT INTO semantic_reservations_lab" in sql:
            self.reservations+=1
        return self.db.execute(sql,*args,**kwargs)
    def rollback(self):
        self.rollbacks+=1
        return self.db.rollback()
    def __getattr__(self,name):
        return getattr(self.db,name)

class G66PrivacyAndUTF8(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory(prefix="g66-local-disposable-")
        self.addCleanup(t.cleanup)
        self.store=SQLiteChatStore(Path(t.name)/"isolated.sqlite3")
        self.addCleanup(self.store.close)
        self.db=self.store.db
        self.box=ExecutionOutbox(self.store,SCOPE)

    def counts(self):
        return tuple(self.db.execute(
            "SELECT COUNT(*) FROM "+table).fetchone()[0] for table in (
            "action_decisions","action_outbox","semantic_reservations_lab","action_effects"))

    def stage(self,extra=None,request="req-A"):
        p={"business_event_id":EVENT,"amount_minor":66}
        if extra:
            p.update(extra)
        return self.box.enqueue(
            intent_ref=request,action="synthetic-no-external-provider",
            payload=p,aggregate_key="g66-aggregate",
            policy_version="p1",authorization_ref="synthetic-owner-only",
            created_at=NOW,valid_until=NOW+timedelta(minutes=5),
            semantic_event_id_lab=EVENT)

    def uncertain(self):
        key=self.stage()["idempotency_key"]
        self.db.execute("UPDATE action_outbox SET state='UNCERTAIN' WHERE idempotency_key=?",(key,))
        self.db.commit()
        return key

    def confirm(self,key,result):
        return self.box._confirm(key,effect_ref=REF,confirmed_at=NOW+timedelta(minutes=1),result=result)

    def test_01_authorization_access_token_client_secret_staging_redacted(self):
        fake="G66_FAKEMARKER_MUST_DISAPPEAR"
        record=self.stage({"authorization":fake,
                           "access_token":fake,"client_secret":fake,
                           "api-key":fake,"apiKey":fake,"accessToken":fake})
        self.assertEqual(record["enqueue_state"],"ENQUEUED")
        doc=json.loads(self.db.execute("SELECT data FROM action_decisions").fetchone()[0])
        for field in ("authorization","access_token","client_secret","api-key","apiKey","accessToken"):
            self.assertEqual(doc["payload"][field],"[REDACTED]")
        self.assertNotIn(fake,json.dumps(doc))
        print("G66_FIELD_NAMES_GREEN=ALL_SENSITIVE_VALUES_MASKED")

    def test_02_nested_tuple_secret_field_names_redacted_on_confirm(self):
        key=self.uncertain()
        fake="G66_FAKE_NESTED_VALUE"
        self.confirm(key,{"items":({"access_token":fake,"client_secret":fake},)})
        doc=json.loads(self.db.execute("SELECT data FROM action_effects").fetchone()[0])
        self.assertEqual(doc["items"],[{"access_token":"[REDACTED]",
                                        "client_secret":"[REDACTED]"}])
        self.assertNotIn(fake,json.dumps(doc))
        print("G66_CONFIRM_FIELDS_GREEN=NESTED_PROTECTED")

    def test_03_custom_userdict_on_enqueue_redacted_structurally(self):
        fake="G66_FAKE_USERDICT_TOKEN"
        self.stage({"wrapped":UserDict({"access_token":fake,"visible":"ordinary"})})
        doc=json.loads(self.db.execute("SELECT data FROM action_decisions").fetchone()[0])
        self.assertEqual(doc["payload"]["wrapped"],
                         {"access_token":"[REDACTED]","visible":"ordinary"})
        self.assertNotIn(fake,json.dumps(doc))
        print("G66_MAPPING_STAGE_GREEN=NO_OBJECT_STRING_BYPASS")

    def test_04_custom_userdict_on_confirmation_redacted_structurally(self):
        key=self.uncertain()
        fake="G66_FAKE_USERDICT_CONFIRM_TOKEN"
        self.confirm(key,{"wrapped":UserDict({"authorization":fake,"visible":"ordinary"})})
        doc=json.loads(self.db.execute("SELECT data FROM action_effects").fetchone()[0])
        self.assertEqual(doc["wrapped"],{"authorization":"[REDACTED]",
                                          "visible":"ordinary"})
        self.assertNotIn(fake,json.dumps(doc))
        print("G66_MAPPING_CONFIRM_GREEN=NO_LEAK")

    def test_05_nonstring_nested_key_denied_before_begin(self):
        watch=SQLWatch(self.db)
        self.box.db=watch
        with self.assertRaisesRegex(ValueError,"G66_NONSTRING_JSON_KEY_DENY"):
            self.stage({"nested":{1:"fake"}})
        self.assertEqual(watch.begins,0)
        self.assertEqual(self.counts(),(0,0,0,0))
        self.assertFalse(self.db.in_transaction)
        print("G66_NONSTRING_KEY_GREEN=EXPLICIT_FAIL_CLOSED")

    def test_06_nonstring_mapping_key_in_confirm_denied_before_begin(self):
        key=self.uncertain()
        watch=SQLWatch(self.db)
        self.box.db=watch
        with self.assertRaisesRegex(ValueError,"G66_NONSTRING_JSON_KEY_DENY"):
            self.confirm(key,{"nested":UserDict({1:"fake"})})
        self.assertEqual(watch.begins,0)
        self.assertEqual(self.counts(),(1,1,1,0))

    def test_07_exact_262144_ascii_confirm_bytes_accepted(self):
        key=self.uncertain()
        # json.dumps({"v":"..."}, separators=(",",":"), ensure_ascii=False)
        # adds exactly 8 bytes to a plain ASCII string.
        value="x"*(MAX-8)
        encoded=json.dumps({"v":value},sort_keys=True,separators=(",",":"),ensure_ascii=False)
        self.assertEqual(len(encoded.encode("utf-8")),MAX)
        done=self.confirm(key,{"v":value})
        self.assertEqual(done["state"],"CONFIRMED")
        self.assertEqual(self.counts(),(1,1,1,1))
        print("G66_UTF8_262144_GREEN=BOUNDARY_ALLOWED")

    def test_08_exact_262145_ascii_confirm_bytes_denied(self):
        key=self.uncertain()
        watch=SQLWatch(self.db)
        self.box.db=watch
        with self.assertRaisesRegex(ValueError,"G65_SERIALIZED_BYTES_DENY"):
            self.confirm(key,{"v":"x"*(MAX-7)})
        self.assertEqual(watch.begins,0)
        self.assertEqual(self.counts(),(1,1,1,0))
        print("G66_UTF8_262145_GREEN=BOUNDARY_DENIED")

    def test_09_multibyte_emoji_utf8_boundary_accepted(self):
        key=self.uncertain()
        value="🧪"*((MAX-8)//4)
        self.assertEqual(len(json.dumps({"v":value},ensure_ascii=False,
                       sort_keys=True,separators=(",",":")).encode("utf-8")),MAX)
        done=self.confirm(key,{"v":value})
        self.assertEqual(done["state"],"CONFIRMED")
        self.assertEqual(self.counts(),(1,1,1,1))
        print("G66_UTF8_MULTIBYTE_GREEN=COUNT_BYTES_NOT_CHARS")

    def test_10_multibyte_excess_denied_without_begin(self):
        key=self.uncertain()
        watch=SQLWatch(self.db)
        self.box.db=watch
        with self.assertRaisesRegex(ValueError,"G65_SERIALIZED_BYTES_DENY"):
            self.confirm(key,{"v":"🧪"*((MAX-8)//4+1)})
        self.assertEqual(watch.begins,0)
        self.assertEqual(self.counts(),(1,1,1,0))

    def test_11_final_decision_oversize_after_reservation_rolls_back(self):
        # The redacted payload itself fits in 256 KiB; the decision envelope
        # and its metadata exceed the cap only AFTER reservation insertion.
        watch=SQLWatch(self.db)
        self.box.db=watch
        with self.assertRaisesRegex(ValueError,"G65_SERIALIZED_BYTES_DENY"):
            self.stage({"blob":"x"*261900})
        self.assertEqual(watch.begins,1)
        self.assertEqual(watch.reservations,1)
        self.assertEqual(watch.rollbacks,1)
        self.assertEqual(self.counts(),(0,0,0,0))
        self.assertFalse(self.db.in_transaction)
        print("G66_FINAL_DECISION_GREEN=ROLLBACK_NO_PARTIAL_RESERVATION")

    def test_12_normal_sensitive_key_name_with_redacted_value_is_preserved(self):
        rec=self.stage({"password":"synthetic-not-a-real-password","secret":"synthetic-not-secret"})
        self.assertEqual(rec["enqueue_state"],"ENQUEUED")
        doc=json.loads(self.db.execute("SELECT data FROM action_decisions").fetchone()[0])
        self.assertEqual(doc["payload"]["password"],"[REDACTED]")
        self.assertEqual(doc["payload"]["secret"],"[REDACTED]")

if __name__=="__main__":
    unittest.main()
