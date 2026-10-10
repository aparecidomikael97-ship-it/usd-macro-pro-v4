"""Issue #1193: historical presence must never be promoted into verified success.

Real SQLite store, production read_product_history_page and authenticated scope.
No network/provider/executor, no changes to Core V1.
"""
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Message, Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_chat_product_bridge import read_product_history_page
from test_atlasquant_aion_chat_product_bridge import authenticated_access


class HistoricalTruthTests(unittest.TestCase):
    def _read_assistant(self, metadata):
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteChatStore(Path(directory) / "history.sqlite3")
            try:
                scope = Scope("mikael", "tenant-a", "workspace-a")
                cid = store.create_conversation(scope).id
                store.append_message(
                    scope,
                    Message(cid, "assistant", "historical claim", metadata=metadata),
                )
                result = read_product_history_page(
                    store, scope, authenticated_access(), cid
                )
                self.assertFalse(result["grants_authority"])
                self.assertFalse(result["memory_promoted"])
                self.assertFalse(result["external_action_executed"])
                return next(iter(result["turns"].values()))
            finally:
                store.close()

    def test_all_metadata_verification_states_are_unverified(self):
        for value in ("", "UNKNOWN", "STALE", "BLOCKED", "CONFIRMED", "CONFIRMED_SUCCESS"):
            with self.subTest(declared=value):
                turn = self._read_assistant({
                    "verification_state": value,
                    "receipt_id": "claimed-receipt",
                    "receipt_digest": "a" * 64,
                    "turn_id": "old-turn",
                })
                self.assertEqual(turn["state"], "UNKNOWN")
                self.assertEqual(turn["reason"], "HISTORICAL_RESULT_NOT_REVERIFIED")
                self.assertEqual(turn["stages"][0]["state"], "NOT_REVERIFIED")
                self.assertEqual(turn["stages"][1]["state"], "LOCAL_PRESENT")
                self.assertEqual(turn["declared_verification_state"], value or "UNKNOWN")
                self.assertNotIn("Receipt verificado", turn["receipt"])
                self.assertFalse(turn["historical_result_reverified"])

    def test_missing_receipt_never_claims_verification(self):
        turn = self._read_assistant({})
        self.assertEqual(turn["state"], "UNKNOWN")
        self.assertEqual(turn["receipt_state"], "NOT_PROVIDED")
        self.assertEqual(turn["declared_verification_state"], "UNKNOWN")
        self.assertFalse(turn["receipt_verified"])
        self.assertIn("não fornecido", turn["receipt"])

    def test_untrusted_receipt_claims_are_never_accepted(self):
        cases = [
            ({}, "NOT_PROVIDED"),
            ({"receipt_id": "id-only"}, "DECLARED_UNVERIFIED"),
            ({"receipt_digest": "malformed"}, "DECLARED_UNVERIFIED"),
            ({"receipt_id": "foreign", "receipt_digest": "a" * 64,
              "identity_binding_digest": "b" * 64}, "DECLARED_UNVERIFIED"),
            ({"receipt_id": "claimed", "receipt_digest": "a" * 64,
              "verification_state": "CONFIRMED_SUCCESS",
              "receipt_verified": True, "historical_result_reverified": True},
             "DECLARED_UNVERIFIED"),
        ]
        for metadata, expected in cases:
            with self.subTest(metadata=metadata):
                turn = self._read_assistant(metadata)
                self.assertEqual(turn["persistence_state"], "LOCAL_PRESENT")
                self.assertEqual(turn["receipt_state"], expected)
                self.assertFalse(turn["receipt_verified"])
                self.assertFalse(turn["historical_result_reverified"])
                self.assertEqual(turn["state"], "UNKNOWN")

    def test_arbitrary_claims_and_absent_evidence_are_not_success(self):
        turn = self._read_assistant({
            "verification_state": "UNRECOGNIZED",
            "evidence": [],
            "receipt_id": "claim",
            "receipt_digest": "invalid",
        })
        self.assertEqual(turn["declared_verification_state"], "UNRECOGNIZED")
        self.assertEqual(turn["state"], "UNKNOWN")
        self.assertIn("declarado", turn["receipt"].lower())
        self.assertFalse(turn["receipt_verified"])

    def test_tenant_isolation_and_user_message_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteChatStore(Path(directory) / "history.sqlite3")
            try:
                scope = Scope("mikael", "tenant-a", "workspace-a")
                cid = store.create_conversation(scope).id
                store.append_message(scope, Message(cid, "user", "Explique o plano"))
                result = read_product_history_page(
                    store, scope, authenticated_access(), cid
                )
                self.assertEqual(result["state"], "READY")  # page availability only
                self.assertEqual(result["entries"][0]["content"], "Explique o plano")
                self.assertEqual(result["turns"], {})
                with self.assertRaises(LookupError):
                    read_product_history_page(
                        store, Scope("mikael", "tenant-b", "workspace-a"),
                        authenticated_access(), cid
                    )
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
