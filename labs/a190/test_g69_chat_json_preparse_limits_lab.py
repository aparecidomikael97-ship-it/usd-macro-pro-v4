"""A190 G69 RED-first: bounded full-JSON chat parsing and escaped partial JSON.

Only synthetic fake strings/disposable SQLite. No real credentials, provider,
Worker, SEND, customer data, funds, spending, main merge or deployment.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import tempfile
import unittest

from aion_chat.models import Message, Scope
from aion_chat.privacy import redact
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

LIMIT=262144
NOW=datetime(2026,10,25,23,tzinfo=timezone.utc)
SCOPE=Scope("g69-owner","g69-tenant","g69-space")
EVENT="g69-synthetic-event"

def json_body_exact_size(n):
    shell='{"public":""}'
    return '{"public":"' + "x"*(n-len(shell.encode("utf-8"))) + '"}'

class BeginWatch:
    def __init__(self,real):
        self.real=real
        self.begins=0
    def execute(self,sql,*a,**kw):
        if sql=="BEGIN IMMEDIATE":
            self.begins+=1
        return self.real.execute(sql,*a,**kw)
    def __getattr__(self,name):
        return getattr(self.real,name)

class G69JSONPreparseGuards(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix="a190-g69-synthetic-")
        self.addCleanup(tmp.cleanup)
        self.dbfile=Path(tmp.name)/"g69.sqlite3"
        self.store=SQLiteChatStore(self.dbfile)
        self.addCleanup(self.store.close)
        self.db=self.store.db
        self.box=ExecutionOutbox(self.store,SCOPE)

    def counts(self):
        return tuple(self.db.execute("SELECT COUNT(*) FROM "+t).fetchone()[0]
                     for t in ("action_decisions","action_outbox",
                               "semantic_reservations_lab","action_effects"))

    def stage(self,notes):
        return self.box.enqueue(
            intent_ref="g69-first",action="synthetic-no-provider",
            payload={"business_event_id":EVENT,"notes":notes},
            aggregate_key="g69-synthetic",policy_version="p1",
            authorization_ref="synthetic-authority",
            created_at=NOW,valid_until=NOW+timedelta(minutes=5),
            semantic_event_id_lab=EVENT,
        )

    def test_01_full_json_262144_input_bytes_allowed(self):
        doc=json_body_exact_size(LIMIT)
        self.assertEqual(len(doc.encode("utf-8")),LIMIT)
        self.assertEqual(redact(doc),doc)
        print("G69_JSON_INPUT_262144_GREEN=BOUNDARY_ALLOWED")

    def test_02_full_json_262145_input_bytes_denied(self):
        doc=json_body_exact_size(LIMIT+1)
        with self.assertRaisesRegex(ValueError,"G69_CHAT_JSON_INPUT_BYTES_DENY"):
            redact(doc)
        print("G69_JSON_INPUT_262145_GREEN=DENIED_BEFORE_PARSE")

    def test_03_multibyte_json_over_budget_denied(self):
        doc='{"public":"' + '🧪'*66000 + '"}'
        self.assertLess(len(doc),LIMIT)
        self.assertGreater(len(doc.encode("utf-8")),LIMIT)
        with self.assertRaisesRegex(ValueError,"G69_CHAT_JSON_INPUT_BYTES_DENY"):
            redact(doc)
        print("G69_JSON_MULTIBYTE_GREEN=CHECK_UTF8_NOT_CHARS")

    def test_04_nested_json_level_64_accepted(self):
        doc='['*64+'"safe"'+']'*64
        self.assertEqual(redact(doc),doc)
        print("G69_JSON_DEPTH64_GREEN=ALLOW")

    def test_05_nested_json_level_65_denied(self):
        doc='['*65+'"safe"'+']'*65
        with self.assertRaisesRegex(ValueError,"G69_CHAT_JSON_NESTING_DENY"):
            redact(doc)
        print("G69_JSON_DEPTH65_GREEN=DENY_BEFORE_PARSE")

    def test_06_brackets_inside_quoted_value_do_not_count_depth(self):
        doc=json.dumps({"public":"["*75 + "}"*75,"refresh_token":"G69_FAKE_KEEP_OUT"})
        safe=json.loads(redact(doc))
        self.assertEqual(safe["public"],"["*75 + "}"*75)
        self.assertEqual(safe["refresh_token"],"[REDACTED]")
        print("G69_JSON_QUOTED_BRACKETS_GREEN=NOT_STRUCTURAL")

    def test_07_escaped_quote_and_slash_do_not_corrupt_depth(self):
        doc=json.dumps({"public":r'quoted "\" with [ { delimiter',"private_key":"G69_FAKE"})
        safe=json.loads(redact(doc))
        self.assertEqual(safe["public"],r'quoted "\" with [ { delimiter')
        self.assertEqual(safe["private_key"],"[REDACTED]")

    def test_08_large_json_in_outbox_refused_without_begin(self):
        watch=BeginWatch(self.db)
        self.box.db=watch
        with self.assertRaisesRegex(ValueError,"G69_CHAT_JSON_INPUT_BYTES_DENY"):
            self.stage(json_body_exact_size(LIMIT+1))
        self.assertEqual(watch.begins,0)
        self.assertEqual(self.counts(),(0,0,0,0))
        print("G69_OUTBOX_PREBEGIN_GREEN=NO_LOCAL_RESERVATION")

    def test_09_oversize_json_chat_message_rolls_back(self):
        conv=self.store.create_conversation(SCOPE,title="g69 synthetic")
        with self.assertRaisesRegex(ValueError,"G69_CHAT_JSON_INPUT_BYTES_DENY"):
            self.store.append_message(
                SCOPE,Message(conversation_id=conv.id,role="user",
                              content=json_body_exact_size(LIMIT+1)))
        self.assertFalse(self.db.in_transaction)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM messages").fetchone()[0],0)
        self.assertEqual(self.store.get_conversation(SCOPE,conv.id).message_count,0)
        print("G69_CHAT_ROLLBACK_GREEN=NO_PARTIAL_MESSAGE")

    def test_10_partial_prose_unicode_escaped_refresh_field_redacted(self):
        raw='Nota: {"refresh\\u005ftoken":"G69_FAKE_PROSE_TOKEN"} continuação.'
        safe=redact(raw)
        self.assertNotIn("G69_FAKE_PROSE_TOKEN",safe)
        self.assertIn("[REDACTED]",safe)
        print("G69_PARTIAL_ESCAPED_GREEN=MASK_WITHOUT_FULL_PARSE")

    def test_11_partial_prose_unicode_escaped_private_key_masked(self):
        raw='Exemplo {"private\\u005fkey" : "G69_FAKE_PRIVATE"} restante.'
        safe=redact(raw)
        self.assertNotIn("G69_FAKE_PRIVATE",safe)
        self.assertIn("[REDACTED]",safe)

    def test_12_partial_prose_escaped_member_with_escaped_quote(self):
        raw='Prefixo {"refresh\\u005ftoken":"G69_FAKE_\\"QUOTED"} sufixo'
        safe=redact(raw)
        self.assertNotIn("G69_FAKE_",safe)
        self.assertIn("[REDACTED]",safe)

    def test_13_partial_prose_public_member_unchanged(self):
        raw='Exemplo: {"public":"ordinary text"} é só um exemplo.'
        self.assertEqual(redact(raw),raw)
        print("G69_PUBLIC_FALLBACK_GREEN=NO_OVERREDACTION")

    def test_14_plain_assignment_legacy_mask_still_works(self):
        self.assertNotIn("G69_FAKE",redact("refresh_token=G69_FAKE"))
        print("G69_LEGACY_ASSIGN_GREEN=STILL_MASKED")

    def test_15_normal_full_json_nested_redaction_and_duplicates(self):
        doc='{"wrapped":{"refresh_token":"G69_FAKE"},"public":2}'
        self.assertEqual(json.loads(redact(doc)),
                         {"wrapped":{"refresh_token":"[REDACTED]"},"public":2})
        with self.assertRaisesRegex(ValueError,"G68_DUPLICATE_CHAT_JSON_KEY_DENY"):
            redact('{"a":1,"a":2}')
        print("G69_G68_COMPAT_GREEN=STRUCTURE_AND_DUPLICATES")

    def test_17_malformed_unclosed_2000_brackets_denied_before_json_loads(self):
        text="["*2000 + "0"
        with self.assertRaisesRegex(ValueError,"G69_CHAT_JSON_NESTING_DENY"):
            redact(text)
        print("G69_MALFORMED_DEEP_GREEN=DENIED_BEFORE_JSON_PARSER")

    def test_18_incomplete_quoted_escaped_secret_in_prose_masked(self):
        source='Nota {"refresh\\u005ftoken":"G69_FAKE_UNCLOSED'
        masked=redact(source)
        self.assertNotIn("G69_FAKE_UNCLOSED",masked)
        self.assertIn("[REDACTED]",masked)
        print("G69_UNFINISHED_MEMBER_GREEN=FAKE_VALUE_REMOVED")

    def test_19_unfinished_secret_in_chat_is_masked_not_persisted(self):
        conv=self.store.create_conversation(SCOPE,title="g69 disposable")
        value='Nota {"private\\u005fkey":"G69_FAKE_CHAT_UNCLOSED'
        self.store.append_message(SCOPE,Message(
            conversation_id=conv.id,role="user",content=value))
        saved=self.db.execute("SELECT content FROM messages").fetchone()[0]
        self.assertNotIn("G69_FAKE_CHAT_UNCLOSED",saved)
        self.assertIn("[REDACTED]",saved)
        self.assertFalse(self.db.in_transaction)
        print("G69_UNFINISHED_CHAT_GREEN=MASKED_LOCAL_STORE")

    def test_16_nonjson_large_prose_unmodified_by_json_only_limit(self):
        # Deliberately documents scope: not a universal string memory cap.
        data="Just public prose "+"x"*(LIMIT+2)
        self.assertEqual(redact(data),data)

if __name__=="__main__":
    unittest.main()
