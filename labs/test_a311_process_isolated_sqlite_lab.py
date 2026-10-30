"""A311: real disposable subprocess SQLite, negative custody/ACK probes.

All commands use synthetic A311 TEST strings, no resident Worker or network.
"""
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from labs.a311_process_isolated_sqlite_lab import (
    SCHEMA, FIXTURE_CONTENT, FIXTURE_MARKER, DB_NAME, MAX_REQUEST_BYTES,
    create_fixture, execute_fixture_request, fixture_root_valid,
    run_lab_request,
)


def request(action, request_id="fixture-req-1", **kwargs):
    return {"schema": SCHEMA, "action": action,
            "request_id": request_id, **kwargs}


class A311SubprocessBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix="a311-lab-")
        self.addCleanup(self.temp.cleanup)
        self.root = create_fixture(self.temp.name)

    def ask(self, action, **kwargs):
        return run_lab_request(self.root, request(action, **kwargs))

    def new_conversation(self):
        result = self.ask(
            "CREATE_SYNTHETIC_CONVERSATION", title="A311 TEST new conversation"
        )
        self.assertEqual(result["status"], "LOCAL_ACKED", result)
        return result["conversation_id"]

    def append(self, cid, message_id, intent_id="a311-intent-1", *,
               injected_ack_loss=False):
        return run_lab_request(
            self.root, request(
                "APPEND_SYNTHETIC_MESSAGE", conversation_id=cid,
                message_id=message_id, intent_id=intent_id,
                content="A311 TEST synthetic one-time message",
            ), inject_ack_after_commit=injected_ack_loss,
        )

    def assert_hard_no_go(self, result):
        self.assertEqual(result["schema"], SCHEMA)
        self.assertTrue(result["research_only"])
        self.assertTrue(result["sqlite_handle_not_returned"])
        self.assertFalse(result["independent_os_storage_isolation"])
        self.assertFalse(result["native_sqlite_fd_attested"])
        self.assertFalse(result["independent_authority_proven"])
        self.assertFalse(result["off_host_intent_ledger_proven"])
        self.assertFalse(result["semantic_exactly_once_proven"])
        self.assertFalse(result["can_authorize_real_effect"])
        self.assertFalse(result["can_resume"])
        self.assertFalse(result["can_resend"])
        self.assertEqual(result["automatic_retries"], 0)
        self.assertTrue(result["zero_auto_resend"])
        self.assertTrue(result["hard_no_go"])
        self.assertEqual(result["p0_homologated"], 0)
        self.assertFalse(result["new_paid_services"])
        self.assertTrue(result["no_worker_deploy_provider_calls"])

    def test_synthetic_fixture_and_private_handle(self):
        self.assertTrue(fixture_root_valid(self.root))
        result = self.ask("READ_SYNTHETIC_HEALTH")
        self.assertEqual(result["status"], "READ_ONLY_RESULT")
        self.assertEqual(result["local_health"], "healthy")
        self.assertTrue(result["strict_authorizer"])
        self.assertNotEqual(result["child_pid"], os.getpid())
        self.assertNotIn("db", result)
        self.assertNotIn("connection", result)
        self.assertNotIn("store", result)
        self.assert_hard_no_go(result)

    def test_one_process_per_request_not_resident_worker(self):
        a = self.ask("READ_SYNTHETIC_HEALTH", request_id="one")
        b = self.ask("READ_SYNTHETIC_HEALTH", request_id="two")
        self.assertEqual(a["status"], "READ_ONLY_RESULT")
        self.assertEqual(b["status"], "READ_ONLY_RESULT")
        self.assertNotEqual(a["child_pid"], os.getpid())
        self.assertNotEqual(b["child_pid"], os.getpid())
        self.assert_hard_no_go(a)
        self.assert_hard_no_go(b)

    def test_two_processes_write_then_read_synthetic_message(self):
        cid = self.new_conversation()
        r = self.append(cid, "a311-message-1")
        self.assertEqual(r["status"], "LOCAL_ACKED", r)
        self.assertEqual(r["message_sequence"], 1)
        looked = self.ask("READ_SYNTHETIC_MESSAGES", conversation_id=cid)
        self.assertEqual(looked["status"], "READ_ONLY_RESULT")
        self.assertEqual(looked["message_ids"], ["a311-message-1"])
        self.assertEqual(looked["message_sequences"], [1])
        self.assertFalse(looked["has_more"])
        self.assert_hard_no_go(r)

    def test_direct_arbitrary_sql_command_is_not_in_protocol(self):
        r = self.ask("EXECUTE_SQL", sql="DELETE FROM conversations")
        self.assertEqual(r["status"], "REQUEST_DENIED")
        self.assert_hard_no_go(r)
        self.assertFalse((self.root / DB_NAME).exists())

    def test_raw_sql_argument_to_allowed_action_is_denied(self):
        r = self.ask("CREATE_SYNTHETIC_CONVERSATION",
                     title="A311 TEST allowed", sql="DROP TABLE messages")
        self.assertEqual(r["status"], "REQUEST_DENIED")
        self.assertFalse((self.root / DB_NAME).exists())

    def test_unauthorized_resume_resend_deploy_actions_are_denied(self):
        for forbidden in (
            "RESUME", "RESEND", "RESTORE", "DEPLOY", "START_WORKER",
            "SEND_ORDER", "PROVIDER_CALL",
        ):
            with self.subTest(action=forbidden):
                r = self.ask(forbidden, request_id="forbidden")
                self.assertEqual(r["status"], "REQUEST_DENIED")
                self.assert_hard_no_go(r)
        self.assertFalse((self.root / DB_NAME).exists())

    def test_override_owner_scope_is_not_accepted(self):
        r = self.ask(
            "CREATE_SYNTHETIC_CONVERSATION", title="A311 TEST synthetic",
            owner_id="untrusted-new-owner",
        )
        self.assertEqual(r["status"], "REQUEST_DENIED")

    def test_unsynthetic_content_is_denied(self):
        cid = self.new_conversation()
        r = self.ask(
            "APPEND_SYNTHETIC_MESSAGE",
            conversation_id=cid, message_id="m1", intent_id="intent-1",
            content="real customer data",
        )
        self.assertEqual(r["status"], "REQUEST_DENIED")

    def test_oversized_payload_rejected_before_child_started(self):
        r = self.ask("CREATE_SYNTHETIC_CONVERSATION",
                     title="A311 TEST " + "x" * MAX_REQUEST_BYTES)
        self.assertEqual(r["status"], "MALFORMED_REQUEST")
        self.assert_hard_no_go(r)
        self.assertFalse((self.root / DB_NAME).exists())

    def test_same_message_id_on_second_request_denied(self):
        cid = self.new_conversation()
        first = self.append(cid, "fixed-message-id")
        second = self.append(cid, "fixed-message-id")
        self.assertEqual(first["status"], "LOCAL_ACKED")
        self.assertEqual(second["status"],
                         "DUPLICATE_OR_CONSTRAINT_DENIED")
        read = self.ask("READ_SYNTHETIC_MESSAGES", conversation_id=cid)
        self.assertEqual(read["message_ids"], ["fixed-message-id"])
        self.assert_hard_no_go(second)

    def test_same_semantic_intent_new_message_id_is_still_a_gap(self):
        cid = self.new_conversation()
        a = self.append(cid, "message-A", "same-semantic-intent")
        b = self.append(cid, "message-B", "same-semantic-intent")
        self.assertEqual(a["status"], "LOCAL_ACKED")
        self.assertEqual(b["status"], "LOCAL_ACKED")
        records = self.ask("READ_SYNTHETIC_MESSAGES", conversation_id=cid)
        self.assertEqual(records["message_ids"], ["message-A", "message-B"])
        self.assertFalse(records["semantic_exactly_once_proven"])
        self.assert_hard_no_go(records)

    def test_ack_lost_after_commit_prevents_new_child_from_retrying(self):
        cid = self.new_conversation()
        uncertain = self.append(cid, "once", injected_ack_loss=True)
        self.assertEqual(uncertain["status"], "ACK_UNKNOWN_QUARANTINE")
        self.assertTrue(
            (self.root / (DB_NAME + ".aion-message-commit-pending")).is_file()
        )
        retry = self.append(cid, "retry-with-another-id")
        self.assertEqual(retry["status"], "LOCAL_STORE_QUARANTINED_OR_DENIED")
        self.assert_hard_no_go(uncertain)
        self.assert_hard_no_go(retry)
        with closing(sqlite3.connect(self.root / DB_NAME)) as db:
            n = db.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        self.assertEqual(n, 1)

    def test_ack_unknown_cannot_be_misread_as_definite_failure(self):
        cid = self.new_conversation()
        uncertain = self.append(cid, "uncertain", injected_ack_loss=True)
        self.assertNotEqual(uncertain["status"], "DUPLICATE_OR_CONSTRAINT_DENIED")
        self.assertEqual(uncertain["status"], "ACK_UNKNOWN_QUARANTINE")
        self.assertFalse(uncertain["can_resend"])
        self.assertEqual(uncertain["automatic_retries"], 0)

    def test_read_after_uncertain_ack_refused_on_new_process(self):
        cid = self.new_conversation()
        self.append(cid, "uncertain", injected_ack_loss=True)
        read = self.ask("READ_SYNTHETIC_MESSAGES", conversation_id=cid)
        self.assertEqual(read["status"], "LOCAL_STORE_QUARANTINED_OR_DENIED")
        self.assert_hard_no_go(read)

    def test_host_can_delete_marker_and_reissue_new_message_id(self):
        """Counterexample: separate process is not independent file custody."""
        cid = self.new_conversation()
        uncertain = self.append(cid, "sent-once", injected_ack_loss=True)
        self.assertEqual(uncertain["status"], "ACK_UNKNOWN_QUARANTINE")
        marker = self.root / (DB_NAME + ".aion-message-commit-pending")
        marker.unlink()  # adversarial same-host deletion, not an approved flow
        second = self.append(cid, "new-unique-message-id",
                             "same-semantic-intent")
        self.assertEqual(second["status"], "LOCAL_ACKED", second)
        with closing(sqlite3.connect(self.root / DB_NAME)) as db:
            n = db.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        self.assertEqual(n, 2)
        self.assertFalse(second["off_host_intent_ledger_proven"])
        self.assert_hard_no_go(second)

    def test_parent_can_open_database_file_by_same_os_account(self):
        """Counterexample: no OS ACL/process sandbox in this laboratory."""
        cid = self.new_conversation()
        with closing(sqlite3.connect(self.root / DB_NAME)) as direct:
            direct.execute(
                "UPDATE conversations SET title=? WHERE id=?",
                ("same-host-direct-writer", cid),
            )
            direct.commit()
        with closing(sqlite3.connect(self.root / DB_NAME)) as verify:
            title = verify.execute(
                "SELECT title FROM conversations WHERE id=?", (cid,)
            ).fetchone()[0]
        self.assertEqual(title, "same-host-direct-writer")
        self.assertFalse(
            (self.root / (DB_NAME + ".aion-message-commit-pending")).exists()
        )
        health = self.ask("READ_SYNTHETIC_HEALTH")
        self.assertEqual(health["status"], "READ_ONLY_RESULT")
        self.assertFalse(health["independent_os_storage_isolation"])
        self.assert_hard_no_go(health)

    def test_invalid_fixture_missing_marker_cannot_open_db(self):
        (self.root / FIXTURE_MARKER).unlink()
        r = self.ask("CREATE_SYNTHETIC_CONVERSATION",
                     title="A311 TEST forbidden")
        self.assertEqual(r["status"], "FIXTURE_REFUSED")
        self.assertFalse((self.root / DB_NAME).exists())

    def test_invalid_fixture_modified_marker_refused(self):
        (self.root / FIXTURE_MARKER).write_text(
            "untrusted changed marker\n", encoding="utf-8"
        )
        r = self.ask("READ_SYNTHETIC_HEALTH")
        self.assertEqual(r["status"], "FIXTURE_REFUSED")

    def test_outside_lab_directory_denied(self):
        with TemporaryDirectory(prefix="other-dir-") as other:
            r = run_lab_request(
                other, request("CREATE_SYNTHETIC_CONVERSATION",
                               title="A311 TEST must refuse"),
            )
            self.assertEqual(r["status"], "FIXTURE_REFUSED")
            self.assertFalse((Path(other) / DB_NAME).exists())

    def test_fault_injection_only_allowed_for_message_append(self):
        r = run_lab_request(
            self.root,
            request("CREATE_SYNTHETIC_CONVERSATION",
                    title="A311 TEST no fault here"),
            inject_ack_after_commit=True,
        )
        self.assertEqual(r["status"], "FAULT_INJECTION_RESTRICTED")
        self.assertFalse((self.root / DB_NAME).exists())

    def test_malformed_json_duplicate_keys_refused(self):
        raw = (b'{"schema":"' + SCHEMA.encode() +
               b'","action":"READ_SYNTHETIC_HEALTH",'
               b'"request_id":"a","request_id":"b"}')
        p = subprocess.run(
            [sys.executable, "-u", "-m",
             "labs.a311_process_isolated_sqlite_lab",
             "--fixture-child", str(self.root)],
            input=raw, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=15, check=False,
        )
        self.assertEqual(p.returncode, 0, p.stderr)
        out = json.loads(p.stdout.decode())
        self.assertEqual(out["status"], "MALFORMED_REQUEST")
        self.assertFalse((self.root / DB_NAME).exists())

    def test_read_without_conversation_is_denied(self):
        r = self.ask("READ_SYNTHETIC_MESSAGES",
                     conversation_id="0" * 32)
        self.assertEqual(r["status"], "LOCAL_STORE_QUARANTINED_OR_DENIED")
        self.assert_hard_no_go(r)

    def test_boolean_and_nested_types_not_promoted(self):
        samples = [None, True, 12, [], {"nested": True}]
        for sample in samples:
            with self.subTest(value=repr(sample)):
                q = request("CREATE_SYNTHETIC_CONVERSATION",
                            title=sample)
                r = run_lab_request(self.root, q)
                self.assertEqual(r["status"], "REQUEST_DENIED")
                self.assert_hard_no_go(r)

    def test_ipc_bad_timeout_does_not_execute(self):
        with self.assertRaises(ValueError):
            run_lab_request(self.root,
                            request("READ_SYNTHETIC_HEALTH"),
                            timeout_seconds=True)
        self.assertFalse((self.root / DB_NAME).exists())

    def test_status_payload_never_claims_real_authority(self):
        cid = self.new_conversation()
        outcomes = [
            self.ask("READ_SYNTHETIC_HEALTH"),
            self.ask("READ_SYNTHETIC_MESSAGES", conversation_id=cid),
            self.append(cid, "a311-one"),
            self.ask("EXECUTE_SQL"),
        ]
        for result in outcomes:
            self.assert_hard_no_go(result)

    def test_child_direct_handler_is_not_a_real_trust_boundary(self):
        # A code owner can import the handler itself; process separation by
        # convention does not authenticate a permission or a principal.
        raw = json.dumps(request("READ_SYNTHETIC_HEALTH")).encode()
        value = execute_fixture_request(self.root, raw)
        self.assertEqual(value["child_pid"], os.getpid())
        self.assertFalse(value["independent_os_storage_isolation"])
        self.assert_hard_no_go(value)


if __name__ == "__main__":
    unittest.main()
