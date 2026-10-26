"""G73 RED first: store.dump() must never asdict-expand untrusted graphs.

LAB synthetic fake values, disposable SQLite, no providers/Worker/SEND.
"""
from pathlib import Path
from dataclasses import dataclass
from unittest.mock import patch
import json
import tempfile
import unittest

from aion_chat.models import (
    Scope, Conversation, ConversationCheckpoint, ContextSummary,
    Message, Attachment,
)
from aion_chat.store import SQLiteChatStore, dump

SCOPE=Scope("g73-owner","g73-tenant","g73-workspace")

def chain(depth, leaf="public"):
    value=leaf
    for _ in range(depth):
        value=[value]
    return value

def compact_dag(depth):
    item=["leaf"]
    for _ in range(depth):
        item=[item,item]
    return item

class G73ChatDumpPrecopy(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix="g73-synthetic-disposable-")
        self.addCleanup(tmp.cleanup)
        self.store=SQLiteChatStore(Path(tmp.name)/"lab.sqlite3")
        self.addCleanup(self.store.close)
        self.db=self.store.db

    def conv(self):
        return self.store.create_conversation(SCOPE,title="lab-only")

    def assert_no_partial(self, cid):
        self.assertFalse(self.db.in_transaction)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM records").fetchone()[0],0)
        self.assertEqual(self.store.get_conversation(SCOPE,cid).message_count,0)
        self.assertEqual(self.store.storage_health()["state"],"healthy")

    def test_01_direct_dump_cycle_denied_by_guard_not_asdict(self):
        loop={}
        loop["self"]=loop
        cp=ConversationCheckpoint(conversation_id="fake",through_sequence=0,
                                   decisions=loop)
        with self.assertRaisesRegex(ValueError,"G70_REDACT_CYCLE_DENY"):
            dump(cp)
        print("G73_DUMP_CYCLE_GREEN=STABLE_DENIAL")

    def test_02_direct_dump_indirect_list_cycle_denied(self):
        loop=[]
        loop.append({"again":loop})
        cp=ConversationCheckpoint(conversation_id="fake",through_sequence=0,
                                   open_tasks={"items":loop})
        with self.assertRaisesRegex(ValueError,"G70_REDACT_CYCLE_DENY"):
            dump(cp)
        print("G73_DUMP_LIST_CYCLE_GREEN=STABLE_DENIAL")

    def test_03_direct_dump_excessive_depth_denied(self):
        cp=ConversationCheckpoint(conversation_id="fake",through_sequence=0,
                                   decisions={"deep":chain(67)})
        with self.assertRaisesRegex(ValueError,"G70_REDACT_DEPTH_DENY"):
            dump(cp)
        print("G73_DUMP_DEPTH_GREEN=BEFORE_ASDICT")

    def test_04_direct_dump_wide_graph_denied(self):
        cp=ConversationCheckpoint(conversation_id="fake",through_sequence=0,
                                   decisions={"wide":list(range(4300))})
        with self.assertRaisesRegex(ValueError,"G70_REDACT_NODE_BUDGET_DENY"):
            dump(cp)
        print("G73_DUMP_WIDE_GREEN=NO_EXPANSION")

    def test_05_compact_dag_exponential_expansion_denied(self):
        cp=ConversationCheckpoint(conversation_id="fake",through_sequence=0,
                                   decisions={"dag":compact_dag(20)})
        with self.assertRaisesRegex(ValueError,"G70_REDACT_NODE_BUDGET_DENY"):
            dump(cp)
        print("G73_DUMP_DAG_GREEN=BOUNDED_EXPANSION")

    def test_06_checkpoint_cycle_inside_write_rolls_back(self):
        conv=self.conv()
        loop={}
        loop["back"]=loop
        cp=ConversationCheckpoint(conversation_id=conv.id,through_sequence=0,
                                   decisions=loop)
        with self.assertRaisesRegex(ValueError,"G70_REDACT_CYCLE_DENY"):
            self.store.save_checkpoint(SCOPE,cp)
        self.assert_no_partial(conv.id)
        self.assertIsNone(self.store.get_latest_checkpoint(SCOPE,conv.id))
        print("G73_CHECKPOINT_ROLLBACK_GREEN=ZERO_RECORDS")

    def test_07_checkpoint_compact_dag_write_rolls_back(self):
        conv=self.conv()
        cp=ConversationCheckpoint(conversation_id=conv.id,through_sequence=0,
                                   decisions={"dag":compact_dag(20)})
        with self.assertRaisesRegex(ValueError,"G70_REDACT_NODE_BUDGET_DENY"):
            self.store.save_checkpoint(SCOPE,cp)
        self.assert_no_partial(conv.id)
        print("G73_CHECKPOINT_DAG_GREEN=NO_PARTIAL_INSERT")

    def test_08_dump_does_not_call_recursive_asdict(self):
        cp=ConversationCheckpoint(conversation_id="fake",through_sequence=0,
                                   decisions={"public":"ordinary"})
        with patch("aion_chat.store.asdict",side_effect=RuntimeError(
            "G73_ASDICT_PRECOPY_SENTINEL")):
            data=json.loads(dump(cp))
        self.assertEqual(data["decisions"],{"public":"ordinary"})
        print("G73_NO_ASDICT_GREEN=SHALLOW_DATACLASS_FIELDS")

    def test_09_normal_checkpoint_persists_and_reads_redacted(self):
        conv=self.conv()
        cp=ConversationCheckpoint(conversation_id=conv.id,through_sequence=0,
                                   decisions={"access_token":"G73_FAKE_VALUE"})
        self.store.save_checkpoint(SCOPE,cp)
        saved=self.store.get_latest_checkpoint(SCOPE,conv.id)
        self.assertEqual(saved.decisions,{"access_token":"[REDACTED]"})
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM records").fetchone()[0],1)
        self.assertFalse(self.db.in_transaction)
        print("G73_CHECKPOINT_NORMAL_GREEN=MASKED_AND_PERSISTED")

    def test_10_summary_and_message_dump_backward_compatible(self):
        conv=self.conv()
        sm=ContextSummary(conversation_id=conv.id,through_sequence=0,
                          content="ordinary text")
        self.store.save_context_summary(SCOPE,sm)
        got=self.store.get_latest_summary(SCOPE,conv.id)
        self.assertEqual(got.content,"ordinary text")
        msg=Message(conversation_id=conv.id,role="user",
                    content='{"refresh_token":"G73_FAKE"}',
                    metadata={"display":"public"})
        self.store.append_message(SCOPE,msg)
        last=self.store.list_messages(SCOPE,conv.id).items[0]
        self.assertEqual(json.loads(last.content)["refresh_token"],"[REDACTED]")
        self.assertEqual(last.metadata,{"display":"public"})
        self.assertFalse(self.db.in_transaction)
        print("G73_SUMMARY_MESSAGE_GREEN=COMPATIBLE")

    def test_11_normal_conversation_dump_flat_metadata(self):
        conv=Conversation(**{"owner_id":SCOPE.owner_id,
                             "tenant_id":SCOPE.tenant_id,
                             "workspace_id":SCOPE.workspace_id},
                          title="synthetic",metadata={"secret":"G73_FAKE"})
        saved=json.loads(dump(conv))
        self.assertEqual(saved["metadata"],{"secret":"[REDACTED]"})
        self.assertEqual(saved["title"],"synthetic")

    def test_12_dump_rejects_non_dataclass_input(self):
        with self.assertRaises(TypeError):
            dump({"metadata":"ordinary"})

    def test_13_small_shared_acyclic_graph_stays_valid(self):
        shared={"public":["x","y"]}
        cp=ConversationCheckpoint(conversation_id="fake",through_sequence=0,
                                   decisions={"one":shared,"two":shared})
        saved=json.loads(dump(cp))
        self.assertEqual(saved["decisions"]["one"],{"public":["x","y"]})
        self.assertEqual(saved["decisions"]["two"],saved["decisions"]["one"])
        print("G73_SHARED_DAG_GREEN=SMALL_GRAPH_ALLOWED")

    def test_15_nested_dataclass_is_explicitly_denied(self):
        nested=Message(conversation_id="fake",role="user",content="ordinary")
        cp=ConversationCheckpoint(conversation_id="fake",through_sequence=0,
                                  decisions={"nested_model":nested})
        with self.assertRaisesRegex(ValueError,"G73_UNSUPPORTED_NESTED_DATACLASS_DENY"):
            dump(cp)
        print("G73_NESTED_DATACLASS_GREEN=EXPLICIT_DENIAL")

    def test_16_failed_later_checkpoint_preserves_prior_pointer(self):
        conv=self.conv()
        self.store.append_message(SCOPE,Message(conversation_id=conv.id,
                                  role="user",content="ordinary"))
        old=ConversationCheckpoint(conversation_id=conv.id,through_sequence=0,
                                   decisions={"status":"valid"})
        self.store.save_checkpoint(SCOPE,old)
        loop={}
        loop["self"]=loop
        attempted=ConversationCheckpoint(conversation_id=conv.id,through_sequence=1,
                                          decisions={"bad":loop})
        with self.assertRaisesRegex(ValueError,"G70_REDACT_CYCLE_DENY"):
            self.store.save_checkpoint(SCOPE,attempted)
        self.assertFalse(self.db.in_transaction)
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM records WHERE kind='checkpoint'").fetchone()[0],1)
        current=self.store.get_conversation(SCOPE,conv.id)
        self.assertEqual(current.latest_checkpoint,old.id)
        self.assertEqual(current.message_count,1)
        self.assertEqual(self.store.get_latest_checkpoint(SCOPE,conv.id).id,old.id)
        self.assertEqual(self.store.storage_health()["state"],"healthy")
        print("G73_POINTER_GREEN=PRIOR_CHECKPOINT_IMMUTABLE")

    def test_17_checkpoint_dag_denial_before_serializer_recursion(self):
        val=ConversationCheckpoint(conversation_id="fake",through_sequence=0,
                                   decisions={"graph":compact_dag(24)})
        # The recursive dataclass copy must not run even on a compact DAG.
        with patch("aion_chat.store.asdict",side_effect=RuntimeError(
            "G73_ASDICT_PRECOPY_SENTINEL")):
            with self.assertRaisesRegex(ValueError,"G70_REDACT_NODE_BUDGET_DENY"):
                dump(val)
        print("G73_DAG_PRECOPY_GREEN=ASDICT_NOT_EXECUTED")

    def test_18_nested_dataclass_under_sensitive_key_denied(self):
        nested=Message(conversation_id="fake",role="user",
                       content="synthetic-not-secret")
        cp=ConversationCheckpoint(conversation_id="fake",through_sequence=0,
                                  decisions={"password":nested})
        with self.assertRaisesRegex(ValueError,"G73_UNSUPPORTED_NESTED_DATACLASS_DENY"):
            dump(cp)
        print("G73_HIDDEN_DATACLASS_GREEN=NOT_MASKED_SILENTLY")

    def test_19_hidden_nested_dataclass_checkpoint_preserves_prior(self):
        conv=self.conv()
        self.store.append_message(SCOPE,Message(conversation_id=conv.id,
                                  role="user",content="synthetic"))
        prior=ConversationCheckpoint(conversation_id=conv.id,through_sequence=0,
                                     decisions={"public":"prior"})
        self.store.save_checkpoint(SCOPE,prior)
        attempted=ConversationCheckpoint(
            conversation_id=conv.id,through_sequence=1,
            decisions={"secret":Message(conversation_id=conv.id,
                                       role="user",content="synthetic")})
        with self.assertRaisesRegex(ValueError,"G73_UNSUPPORTED_NESTED_DATACLASS_DENY"):
            self.store.save_checkpoint(SCOPE,attempted)
        self.assertEqual(self.store.get_latest_checkpoint(SCOPE,conv.id).id,prior.id)
        self.assertEqual(self.store.get_conversation(SCOPE,conv.id).latest_checkpoint,prior.id)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM records").fetchone()[0],1)
        self.assertFalse(self.db.in_transaction)
        print("G73_HIDDEN_POINTER_GREEN=ROLLED_BACK")

    def test_20_dump_dataclass_class_not_instance_is_denied(self):
        @dataclass
        class ClassWithDefaults:
            public: str="ordinary"
        with self.assertRaisesRegex(TypeError,"dataclass instance"):
            dump(ClassWithDefaults)
        print("G73_CLASS_INPUT_GREEN=ONLY_INSTANCES")

    def test_14_direct_hidden_cyclic_value_still_denied(self):
        loop=[]
        loop.append(loop)
        cp=ConversationCheckpoint(conversation_id="fake",through_sequence=0,
                                   decisions={"password":loop})
        with self.assertRaisesRegex(ValueError,"G70_REDACT_CYCLE_DENY"):
            dump(cp)
        print("G73_HIDDEN_CYCLE_GREEN=NO_REDACTION_BYPASS")

if __name__=="__main__":
    unittest.main()
