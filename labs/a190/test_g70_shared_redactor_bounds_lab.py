"""G70 RED-first: shared chat privacy redactor must bound native Python graphs.

Local disposable SQLite and FAKE strings only. Not a universal DLP or an
execution sandbox. No provider, Worker, SEND, funds, client data or deploy.
"""
from collections import UserDict
from pathlib import Path
import json, tempfile, unittest

from aion_chat.models import Message, Scope
from aion_chat.privacy import redact
from aion_chat.store import SQLiteChatStore

SCOPE=Scope("g70-owner","g70-tenant","g70-space")

def nest(levels,leaf="ordinary"):
    data=leaf
    for _ in range(levels):
        data=[data]
    return data

class G70SharedRedactorBounds(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix="g70-synthetic-sqlite-")
        self.addCleanup(tmp.cleanup)
        self.store=SQLiteChatStore(Path(tmp.name)/"g70.sqlite3")
        self.addCleanup(self.store.close)
        self.db=self.store.db

    def test_01_direct_self_referential_dict_stably_denied(self):
        obj={}
        obj["self"]=obj
        with self.assertRaisesRegex(ValueError,"G70_REDACT_CYCLE_DENY"):
            redact(obj)
        print("G70_DICT_CYCLE_GREEN=STABLE_DENIAL")

    def test_02_direct_self_referential_list_stably_denied(self):
        obj=[]
        obj.append(obj)
        with self.assertRaisesRegex(ValueError,"G70_REDACT_CYCLE_DENY"):
            redact(obj)
        print("G70_LIST_CYCLE_GREEN=STABLE_DENIAL")

    def test_03_tuple_list_indirect_cycle_stably_denied(self):
        obj=[]
        ref=(obj,)
        obj.append(ref)
        with self.assertRaisesRegex(ValueError,"G70_REDACT_CYCLE_DENY"):
            redact(ref)

    def test_04_userdict_indirect_cycle_stably_denied(self):
        obj=UserDict()
        obj["other"]=[obj]
        with self.assertRaisesRegex(ValueError,"G70_REDACT_CYCLE_DENY"):
            redact(obj)
        print("G70_USERDICT_CYCLE_GREEN=STABLE_DENIAL")

    def test_05_container_depth_64_allowed(self):
        value={"wrapped":nest(63)}
        safe=redact(value)
        self.assertEqual(safe["wrapped"],nest(63))
        print("G70_DEPTH64_GREEN=ACCEPTED")

    def test_06_container_depth_65_denied(self):
        value={"wrapped":nest(64)}
        with self.assertRaisesRegex(ValueError,"G70_REDACT_DEPTH_DENY"):
            redact(value)
        print("G70_DEPTH65_GREEN=DENIED")

    def test_07_exact_4096_visits_allowed_for_list(self):
        result=redact([0]*4095)
        self.assertEqual(len(result),4095)
        print("G70_NODE4096_GREEN=ACCEPTED")

    def test_08_4097_visits_denied_for_list(self):
        with self.assertRaisesRegex(ValueError,"G70_REDACT_NODE_BUDGET_DENY"):
            redact([0]*4096)
        print("G70_NODE4097_GREEN=DENIED")

    def test_09_repeated_shared_dag_expansion_budgeted(self):
        shared={"normal":"green"}
        wide=[shared for _ in range(2000)]
        with self.assertRaisesRegex(ValueError,"G70_REDACT_NODE_BUDGET_DENY"):
            redact(wide)
        print("G70_DAG_GREEN=BOUNDED_EXPANSION")

    def test_10_shared_acyclic_object_accepted(self):
        shared={"public":[1,2]}
        done=redact({"one":shared,"two":shared})
        self.assertEqual(done["one"],{"public":[1,2]})
        self.assertEqual(done["two"],done["one"])
        print("G70_SHARED_ACYCLIC_GREEN=COMPATIBLE")

    def test_11_sensitive_field_cycle_is_denied_even_if_hidden(self):
        secret=[]
        secret.append(secret)
        with self.assertRaisesRegex(ValueError,"G70_REDACT_CYCLE_DENY"):
            redact({"password":secret,"public":"okay"})
        print("G70_HIDDEN_CYCLE_GREEN=NO_BYPASS")

    def test_17_normal_sensitive_container_is_masked(self):
        safe=redact({"password":["synthetic-one","synthetic-two"],
                     "public":"okay"})
        self.assertEqual(safe,{"password":"[REDACTED]","public":"okay"})
        print("G70_HIDDEN_SAFE_GREEN=VALUE_MASKED")

    def test_12_shared_chat_message_deep_metadata_rolled_back(self):
        conv=self.store.create_conversation(SCOPE,title="g70 synthetic")
        # metadata mapping itself is the root, 64 nested lists exceed redactor cap.
        message=Message(conversation_id=conv.id,role="user",
                        content="synthetic-public",metadata={"wrapped":nest(66)})
        with self.assertRaisesRegex(ValueError,"G70_REDACT_DEPTH_DENY"):
            self.store.append_message(SCOPE,message)
        self.assertFalse(self.db.in_transaction)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM messages").fetchone()[0],0)
        self.assertEqual(self.store.get_conversation(SCOPE,conv.id).message_count,0)
        self.assertEqual(self.store.storage_health()["state"],"healthy")
        print("G70_CHAT_DEPTH_GREEN=ROLLED_BACK")

    def test_13_shared_chat_wide_metadata_rolled_back(self):
        conv=self.store.create_conversation(SCOPE,title="g70 synthetic")
        msg=Message(conversation_id=conv.id,role="user",
                    content="synthetic-public",metadata={"wide":list(range(4300))})
        with self.assertRaisesRegex(ValueError,"G70_REDACT_NODE_BUDGET_DENY"):
            self.store.append_message(SCOPE,msg)
        self.assertFalse(self.db.in_transaction)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM messages").fetchone()[0],0)
        print("G70_CHAT_BUDGET_GREEN=ROLLED_BACK")

    def test_14_normal_chat_message_still_persists_masked_value(self):
        conv=self.store.create_conversation(SCOPE,title="g70 synthetic")
        msg=Message(conversation_id=conv.id,role="user",
                    content='{"refresh_token":"G70_FAKE","public":"hello"}',
                    metadata={"note":"ordinary"})
        self.store.append_message(SCOPE,msg)
        content=self.db.execute("SELECT content FROM messages").fetchone()[0]
        self.assertEqual(json.loads(content),
                         {"refresh_token":"[REDACTED]","public":"hello"})
        self.assertFalse(self.db.in_transaction)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM messages").fetchone()[0],1)
        print("G70_NORMAL_CHAT_GREEN=MASKED_AND_PERSISTED")

    def test_15_g69_string_boundaries_still_intact(self):
        self.assertEqual(redact("["*64+'"safe"'+"]"*64),"["*64+'"safe"'+"]"*64)
        with self.assertRaisesRegex(ValueError,"G69_CHAT_JSON_NESTING_DENY"):
            redact("["*65+'"safe"'+"]"*65)

    def test_16_shared_redactor_numeric_key_error_unchanged(self):
        with self.assertRaisesRegex(ValueError,"G67_NONSTRING_REDACT_KEY_DENY"):
            redact({17:"synthetic"})

if __name__=="__main__":
    unittest.main()
