"""A190 G68 RED-first LAB: quoted JSON chat secrecy and top-level Mapping.

Only fake markers and disposable SQLite. No network/provider/Worker/SEND,
financial operations, client info, main merge or deployment.
"""
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import tempfile
import unittest

from aion_chat.models import Message, Scope
from aion_chat.privacy import redact
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

NOW = datetime(2026, 10, 25, 23, tzinfo=timezone.utc)
SCOPE = Scope("g68-owner", "g68-tenant", "g68-space")
EVENT = "g68-disposable-event"
EFFECT = "g68-disposable-receipt"

class TopLevelMapping(Mapping):
    """Expose uses of implicit dict() conversion instead of .items snapshot."""
    def __init__(self, data):
        self.data = data
        self.item_calls = 0
        self.getitem_calls = 0
    def __len__(self):
        return len(self.data)
    def __iter__(self):
        return iter(self.data)
    def __getitem__(self, key):
        self.getitem_calls += 1
        raise AssertionError("G68_UNBOUNDED_TOP_LEVEL_GETITEM")
    def items(self):
        self.item_calls += 1
        return self.data.items()

class ExplodingMapping(TopLevelMapping):
    def items(self):
        self.item_calls += 1
        raise ValueError("G68_FAKE_MAPPING_ITERATION_ERROR")

class BeginWatch:
    def __init__(self, real):
        self.real = real
        self.begins = 0
    def execute(self, sql, *args, **kwargs):
        if sql == "BEGIN IMMEDIATE":
            self.begins += 1
        return self.real.execute(sql, *args, **kwargs)
    def __getattr__(self, name):
        return getattr(self.real, name)

class G68QuotedJSONAndMapping(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory(prefix="a190-g68-synthetic-")
        self.addCleanup(t.cleanup)
        self.dbfile = Path(t.name) / "local.sqlite3"
        self.store = SQLiteChatStore(self.dbfile)
        self.addCleanup(self.store.close)
        self.real = self.store.db
        self.outbox = ExecutionOutbox(self.store, SCOPE)

    def counts(self):
        return tuple(self.real.execute("SELECT COUNT(*) FROM " + tab).fetchone()[0]
            for tab in ("action_decisions","action_outbox","semantic_reservations_lab","action_effects"))

    def payload(self, **extra):
        return {"business_event_id":EVENT,"amount_minor":68,**extra}

    def stage(self, value=None):
        return self.outbox.enqueue(
            intent_ref="g68-request", action="synthetic_no_external_adapter",
            payload=self.payload() if value is None else value,
            aggregate_key="g68-aggregate",policy_version="p1",
            authorization_ref="synthetic-auth",created_at=NOW,
            valid_until=NOW+timedelta(minutes=5),semantic_event_id_lab=EVENT)

    def uncertain(self):
        key=self.stage()["idempotency_key"]
        self.real.execute(
            "UPDATE action_outbox SET state='UNCERTAIN' WHERE idempotency_key=?",
            (key,))
        self.real.commit()
        return key

    def confirm(self,key,result):
        return self.outbox._confirm(
            key,effect_ref=EFFECT,confirmed_at=NOW+timedelta(minutes=1),
            result=result)

    def test_01_quoted_json_refresh_token_stays_valid_json(self):
        raw='{"refresh_token":"G68_FAKE_REFRESH","public":"hello"}'
        safe=redact(raw)
        doc=json.loads(safe)
        self.assertEqual(doc["refresh_token"],"[REDACTED]")
        self.assertEqual(doc["public"],"hello")
        self.assertNotIn("G68_FAKE_REFRESH",safe)
        print("G68_JSON_QUOTED_GREEN=VALID_REDACTED_JSON")

    def test_02_spaced_nested_quoted_json_fields_redacted(self):
        raw='{"wrapped": {"private_key" : "G68_FAKE_PRIVATE", "client_secret":"G68_FAKE_CLIENT"}}'
        doc=json.loads(redact(raw))
        self.assertEqual(doc["wrapped"]["private_key"],"[REDACTED]")
        self.assertEqual(doc["wrapped"]["client_secret"],"[REDACTED]")
        print("G68_JSON_NESTED_GREEN=FAKE_FIELDS_MASKED")

    def test_03_escaped_quote_in_json_secret_masked_without_corruption(self):
        raw=json.dumps({"access_token":'FAKE_"_ESCAPED', "normal":'hello "quoted"'})
        doc=json.loads(redact(raw))
        self.assertEqual(doc["access_token"],"[REDACTED]")
        self.assertEqual(doc["normal"],'hello "quoted"')
        print("G68_JSON_ESCAPED_GREEN=STRUCTURE_PRESERVED")

    def test_04_chat_message_quoted_json_value_not_persisted(self):
        conv=self.store.create_conversation(SCOPE,title="synthetic-g68")
        raw='{"refresh_token":"G68_FAKE_CHAT_JSON","public":"unchanged"}'
        self.store.append_message(SCOPE,Message(
            conversation_id=conv.id,role="user",content=raw))
        content=self.real.execute("SELECT content FROM messages").fetchone()[0]
        self.assertEqual(json.loads(content)["refresh_token"],"[REDACTED]")
        self.assertNotIn("G68_FAKE_CHAT_JSON",content)
        self.assertEqual(self.real.execute("SELECT COUNT(*) FROM messages").fetchone()[0],1)
        print("G68_JSON_CHAT_GREEN=NO_FAKE_CONTENT")

    def test_05_normal_json_without_sensitive_keys_preserved(self):
        raw='{"public":"green", "count":3, "label":"normal"}'
        self.assertEqual(redact(raw),raw)

    def test_06_plain_assignment_still_redacted(self):
        text="refresh_token=G68_FAKE_ASSIGNMENT"
        self.assertNotIn("G68_FAKE_ASSIGNMENT",redact(text))

    def test_07_top_level_mapping_enqueue_visited_once_without_getitem(self):
        top=TopLevelMapping(self.payload(note="ordinary"))
        admitted=self.stage(top)
        self.assertEqual(admitted["enqueue_state"],"ENQUEUED")
        self.assertEqual(top.item_calls,1)
        self.assertEqual(top.getitem_calls,0)
        self.assertEqual(self.counts(),(1,1,1,0))
        print("G68_TOP_ENQUEUE_GREEN=ONE_BOUNDED_SNAPSHOT")

    def test_08_top_level_mapping_confirm_visited_once(self):
        key=self.uncertain()
        top=TopLevelMapping({"status":"synthetic-success"})
        result=self.confirm(key,top)
        self.assertEqual(result["state"],"CONFIRMED")
        self.assertEqual(top.item_calls,1)
        self.assertEqual(top.getitem_calls,0)
        self.assertEqual(self.counts(),(1,1,1,1))
        print("G68_TOP_CONFIRM_GREEN=ONE_BOUNDED_SNAPSHOT")

    def test_09_top_level_mapping_error_before_begin(self):
        top=ExplodingMapping(self.payload())
        watch=BeginWatch(self.real)
        self.outbox.db=watch
        with self.assertRaisesRegex(ValueError,"G68_FAKE_MAPPING_ITERATION_ERROR"):
            self.stage(top)
        self.assertEqual(watch.begins,0)
        self.assertEqual(self.counts(),(0,0,0,0))
        self.assertFalse(self.real.in_transaction)
        print("G68_TOP_ERROR_GREEN=ZERO_BEGIN")

    def test_10_top_level_result_mapping_error_before_begin(self):
        key=self.uncertain()
        top=ExplodingMapping({"result":"synthetic"})
        watch=BeginWatch(self.real)
        self.outbox.db=watch
        with self.assertRaisesRegex(ValueError,"G68_FAKE_MAPPING_ITERATION_ERROR"):
            self.confirm(key,top)
        self.assertEqual(watch.begins,0)
        self.assertEqual(self.counts(),(1,1,1,0))
        print("G68_RESULT_ERROR_GREEN=NO_LOCAL_EFFECT")

    def test_11_top_level_nonstring_key_g66_denial_remains(self):
        top=TopLevelMapping({1:"fake","business_event_id":EVENT})
        with self.assertRaisesRegex(ValueError,"G66_NONSTRING_JSON_KEY_DENY"):
            self.stage(top)
        self.assertEqual(self.counts(),(0,0,0,0))

    def test_13_wide_top_level_mapping_denied_before_begin(self):
        data=self.payload()
        data.update({"field_%04d"%i: i for i in range(4300)})
        top=TopLevelMapping(data)
        watch=BeginWatch(self.real)
        self.outbox.db=watch
        with self.assertRaisesRegex(ValueError,"G65_NODE_BUDGET_DENY"):
            self.stage(top)
        self.assertEqual(top.item_calls,1)
        self.assertEqual(top.getitem_calls,0)
        self.assertEqual(watch.begins,0)
        self.assertEqual(self.counts(),(0,0,0,0))
        print("G68_TOP_BUDGET_GREEN=DENIED_BEFORE_BEGIN")

    def test_14_wide_top_confirmation_denied_without_effect(self):
        key=self.uncertain()
        top=TopLevelMapping({"field_%04d"%i:i for i in range(4300)})
        watch=BeginWatch(self.real)
        self.outbox.db=watch
        with self.assertRaisesRegex(ValueError,"G65_NODE_BUDGET_DENY"):
            self.confirm(key,top)
        self.assertEqual(top.item_calls,1)
        self.assertEqual(top.getitem_calls,0)
        self.assertEqual(watch.begins,0)
        self.assertEqual(self.counts(),(1,1,1,0))
        print("G68_TOP_CONFIRM_BUDGET_GREEN=NO_LEDGER_EFFECT")

    def test_15_nonmapping_top_payload_explicit_denial(self):
        watch=BeginWatch(self.real)
        self.outbox.db=watch
        with self.assertRaisesRegex(TypeError,"payload must be a Mapping"):
            self.stage([("business_event_id",EVENT)])
        self.assertEqual(watch.begins,0)
        self.assertEqual(self.counts(),(0,0,0,0))

    def test_17_unicode_escaped_sensitive_json_member_masked(self):
        raw='{"refresh\\u005ftoken":"G68_FAKE_UNICODE_ESCAPE","public":"safe"}'
        # JSON escape syntax in the source has a literal backslash-u sequence.
        parsed=json.loads(redact(raw))
        self.assertEqual(parsed["refresh_token"],"[REDACTED]")
        self.assertEqual(parsed["public"],"safe")
        self.assertNotIn("G68_FAKE_UNICODE_ESCAPE",json.dumps(parsed))
        print("G68_ESCAPED_KEY_GREEN=NORMALIZED_AND_REDACTED")

    def test_18_public_json_string_assignment_does_not_break_json(self):
        raw='{"public":"password=G68_FAKE_ASSIGNMENT","other":"hello"}'
        parsed=json.loads(redact(raw))
        self.assertEqual(parsed["public"],"[REDACTED]")
        self.assertEqual(parsed["other"],"hello")
        print("G68_PUBLIC_JSON_GREEN=VALID_STRUCTURE")

    def test_20_duplicate_escaped_json_key_fails_closed(self):
        raw='{"refresh\\u005ftoken":"G68_FAKE_DUPLICATE","refresh_token":"[REDACTED]"}'
        with self.assertRaisesRegex(ValueError,"G68_DUPLICATE_CHAT_JSON_KEY_DENY"):
            redact(raw)
        print("G68_DUP_JSON_GREEN=NO_AMBIGUOUS_KEY")

    def test_21_chat_duplicate_sensitive_json_rolls_back(self):
        conv=self.store.create_conversation(SCOPE,title="synthetic-g68")
        raw='{"refresh\\u005ftoken":"G68_FAKE_DUPLICATE","refresh_token":"[REDACTED]"}'
        with self.assertRaisesRegex(ValueError,"G68_DUPLICATE_CHAT_JSON_KEY_DENY"):
            self.store.append_message(SCOPE,Message(
                conversation_id=conv.id,role="user",content=raw))
        self.assertFalse(self.real.in_transaction)
        self.assertEqual(self.real.execute("SELECT COUNT(*) FROM messages").fetchone()[0],0)
        self.assertEqual(self.store.get_conversation(SCOPE,conv.id).message_count,0)
        print("G68_CHAT_DUP_GREEN=TRANSACTION_ROLLBACK")

    def test_19_json_array_sensitive_nested_fields_redacted(self):
        raw='[{"refresh_token":"G68_FAKE_ARRAY"},{"normal":"hello"}]'
        parsed=json.loads(redact(raw))
        self.assertEqual(parsed[0]["refresh_token"],"[REDACTED]")
        self.assertEqual(parsed[1]["normal"],"hello")
        print("G68_ARRAY_JSON_GREEN=VALID_REDACTED_ELEMENTS")

    def test_16_nonmapping_confirm_result_explicit_denial(self):
        key=self.uncertain()
        watch=BeginWatch(self.real)
        self.outbox.db=watch
        with self.assertRaisesRegex(TypeError,"confirmation result must be a Mapping"):
            self.confirm(key,[("status","fake")])
        self.assertEqual(watch.begins,0)
        self.assertEqual(self.counts(),(1,1,1,0))

    def test_12_normal_confirmation_and_replay_unchanged(self):
        key=self.uncertain()
        result=self.confirm(key,{"status":"synthetic"})
        self.assertEqual(result["state"],"CONFIRMED")
        self.assertEqual(self.counts(),(1,1,1,1))
        again=self.confirm(key,{"status":"synthetic"})
        self.assertEqual(again["state"],"CONFIRMED")
        self.assertEqual(self.counts(),(1,1,1,1))

if __name__=="__main__":
    unittest.main()
