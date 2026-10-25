"""G67 RED-first: sensitive aliases, atomic container snapshot, shared redactor, Unicode.

Disposable SQLite and FAKE markers only. No Worker, real SEND/provider, customer,
secrets, funds, merges or deploy. Save tests BEFORE runtime corrections.
"""
from collections.abc import Mapping
from datetime import datetime,timedelta,timezone
from pathlib import Path
import json,tempfile,unittest

from aion_chat.models import Scope, Message
from aion_chat.privacy import redact
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

NOW=datetime(2026,10,25,23,tzinfo=timezone.utc)
SCOPE=Scope("g67-owner","g67-tenant","g67-workspace")
EVENT="g67-fake-business-event"
REF="g67-fake-local-receipt"

class TwoReadMapping(Mapping):
    """Fake untrusted collection whose second .items() result is different."""
    def __init__(self,first,second):
        self.first=first
        self.second=second
        self.reads=0
    def items(self):
        self.reads+=1
        return (self.first if self.reads==1 else self.second).items()
    def __getitem__(self,k):
        return self.first[k]
    def __iter__(self):
        return iter(self.first)
    def __len__(self):
        return len(self.first)

class SQLWatch:
    def __init__(self,db):
        self.db=db
        self.begins=0
    def execute(self,sql,*args,**kwargs):
        if sql=="BEGIN IMMEDIATE":self.begins+=1
        return self.db.execute(sql,*args,**kwargs)
    def __getattr__(self,k):
        return getattr(self.db,k)

class G67SnapshotPrivacy(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory(prefix="a190-g67-lab-")
        self.addCleanup(t.cleanup)
        self.path=Path(t.name)/"synthetic.sqlite3"
        self.store=SQLiteChatStore(self.path)
        self.addCleanup(self.store.close)
        self.db=self.store.db
        self.box=ExecutionOutbox(self.store,SCOPE)

    def counts(self):
        return tuple(self.db.execute("SELECT COUNT(*) FROM "+t).fetchone()[0]
                     for t in ("action_decisions","action_outbox",
                               "semantic_reservations_lab","action_effects"))
    def stage(self,extra=None):
        p={"business_event_id":EVENT,"amount_minor":67}
        if extra:p.update(extra)
        return self.box.enqueue(
            intent_ref="g67-request",action="synthetic-no-provider",
            payload=p,aggregate_key="g67-aggregate",
            policy_version="p1",authorization_ref="synthetic-auth",
            created_at=NOW,valid_until=NOW+timedelta(minutes=5),
            semantic_event_id_lab=EVENT)
    def uncertain(self):
        key=self.stage()["idempotency_key"]
        self.db.execute("UPDATE action_outbox SET state='UNCERTAIN' WHERE idempotency_key=?",(key,))
        self.db.commit()
        return key
    def confirm(self,key,result):
        return self.box._confirm(key,effect_ref=REF,
                                 confirmed_at=NOW+timedelta(minutes=1),result=result)
    def decision(self):
        return json.loads(self.db.execute("SELECT data FROM action_decisions").fetchone()[0])
    def effect(self):
        return json.loads(self.db.execute("SELECT data FROM action_effects").fetchone()[0])

    def test_01_more_sensitive_names_redacted_on_enqueue(self):
        fake="G67_FAKE_VALUE_NOT_A_CREDENTIAL"
        self.stage({"refresh_token":fake,"private_key":fake,
                    "authorization ":fake,"refreshToken":fake,"privateKey":fake})
        p=self.decision()["payload"]
        for k in ("refresh_token","private_key","authorization ","refreshToken","privateKey"):
            self.assertEqual(p[k],"[REDACTED]")
        self.assertNotIn(fake,json.dumps(p))
        print("G67_ALIASES_STAGE_GREEN=NO_FAKE_VALUE")

    def test_02_more_sensitive_names_redacted_on_confirmation(self):
        key=self.uncertain()
        fake="G67_FAKE_IN_CONFIRMATION"
        self.confirm(key,{"nested":({"refresh_token":fake,"private_key":fake},)})
        e=self.effect()["nested"][0]
        self.assertEqual(e,{"refresh_token":"[REDACTED]",
                            "private_key":"[REDACTED]"})
        self.assertNotIn(fake,json.dumps(e))
        print("G67_ALIASES_CONFIRM_GREEN=NESTED_MASKED")

    def test_03_changing_mapping_does_not_bypass_sensitive_key_gate(self):
        val=TwoReadMapping({"note":"safe-first"},
                           {"sk-G67FAKEKEY123456":"synthetic-second"})
        self.stage({"wrapped":val})
        self.assertEqual(val.reads,1)
        self.assertEqual(self.decision()["payload"]["wrapped"],{"note":"safe-first"})
        self.assertNotIn("G67FAKEKEY",json.dumps(self.decision()))
        print("G67_MUTABLE_KEY_GREEN=ONE_SNAPSHOT")

    def test_04_changing_mapping_cannot_change_confirmation_evidence(self):
        key=self.uncertain()
        val=TwoReadMapping({"note":"safe-first"},
                           {"note":"second-unaudited"})
        self.confirm(key,{"wrapped":val})
        self.assertEqual(val.reads,1)
        self.assertEqual(self.effect()["wrapped"],{"note":"safe-first"})
        print("G67_MUTABLE_CONFIRM_GREEN=ONE_SNAPSHOT")

    def test_05_redactor_direct_nonstring_key_is_explicitly_denied(self):
        with self.assertRaisesRegex(ValueError,"G67_NONSTRING_REDACT_KEY_DENY"):
            redact({7:"synthetic"})
        print("G67_REDACTOR_KEY_GREEN=STABLE_ERROR")

    def test_06_shared_chat_append_message_nonstring_metadata_rolls_back(self):
        conversation=self.store.create_conversation(SCOPE,title="synthetic")
        message=Message(conversation_id=conversation.id,role="user",
                        content="only a synthetic message",metadata={7:"fake"})
        with self.assertRaisesRegex(ValueError,"G67_NONSTRING_REDACT_KEY_DENY"):
            self.store.append_message(SCOPE,message)
        self.assertFalse(self.db.in_transaction)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM messages").fetchone()[0],0)
        self.assertEqual(self.store.get_conversation(SCOPE,conversation.id).message_count,0)
        self.assertEqual(self.store.storage_health()["state"],"healthy")
        print("G67_CHAT_ROLLBACK_GREEN=NO_PARTIAL_MESSAGE")

    def test_07_surrogate_in_enqueue_denied_before_begin(self):
        watch=SQLWatch(self.db);self.box.db=watch
        with self.assertRaisesRegex(ValueError,"G67_INVALID_UNICODE_DENY"):
            self.stage({"text":"\ud800"})
        self.assertEqual(watch.begins,0)
        self.assertEqual(self.counts(),(0,0,0,0))
        print("G67_BAD_UTF8_STAGE_GREEN=ZERO_BEGIN")

    def test_08_surrogate_in_confirmation_denied_before_begin(self):
        key=self.uncertain()
        watch=SQLWatch(self.db);self.box.db=watch
        with self.assertRaisesRegex(ValueError,"G67_INVALID_UNICODE_DENY"):
            self.confirm(key,{"text":"\udfff"})
        self.assertEqual(watch.begins,0)
        self.assertEqual(self.counts(),(1,1,1,0))
        print("G67_BAD_UTF8_CONFIRM_GREEN=ZERO_BEGIN")

    def test_09_shared_repeated_acyclic_mapping_still_allowed(self):
        val={"normal":[3,4]}
        self.stage({"first":val,"second":val})
        self.assertEqual(self.decision()["payload"]["first"],{"normal":[3,4]})
        self.assertEqual(self.counts(),(1,1,1,0))

    def test_10_known_safe_aliases_still_readable(self):
        self.stage({"title":"public","access_token":"fake-value"})
        p=self.decision()["payload"]
        self.assertEqual(p["title"],"public")
        self.assertEqual(p["access_token"],"[REDACTED]")
        print("G67_SAFE_COMPAT_GREEN=ORDINARY_FIELDS")

    def test_11_nested_cycle_original_denial_code(self):
        loop=[];loop.append(loop)
        with self.assertRaisesRegex(ValueError,"G62_CYCLIC_PAYLOAD_DENY"):
            self.stage({"loop":loop})
        self.assertEqual(self.counts(),(0,0,0,0))

    def test_12_nonstring_mapping_key_original_outbox_code(self):
        with self.assertRaisesRegex(ValueError,"G66_NONSTRING_JSON_KEY_DENY"):
            self.stage({"nested":{1:"x"}})
        self.assertEqual(self.counts(),(0,0,0,0))

if __name__=="__main__":
    unittest.main()
