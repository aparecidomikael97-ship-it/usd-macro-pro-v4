"""Adversarial reference one-shot UNKNOWN_OUTCOME test; no paid provider."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from copy import deepcopy
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from atlasquant_aion_v2_one_shot_unknown_outcome_journal_reference import (
    SCHEMA,INTENT_SCHEMA,STATE_PREPARED,STATE_CLAIMED,
    STATE_UNKNOWN,STATE_CANCELLED,REPLAY_BLOCKED,LOCAL_CLAIM,
    NO_AUTHORITY,ReferenceOneShotUnknownOutcomeJournal,
)


class OneShotUnknownOutcomeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/"aion-local-reference-dispatch.db"
        self.config={
            "owner_id":"owner","tenant_id":"tenant",
            "workspace_id":"workspace","period_id":"2026-10",
            "policy_generation":9,"max_period_micro_usd":300,
        }
        self.journal=self.open_journal()
        self.intent=self.build_intent()

    def tearDown(self):
        self.journal.close()
        self.temp.cleanup()

    def open_journal(self,*,config=None):
        return ReferenceOneShotUnknownOutcomeJournal(
            self.path,config=self.config if config is None else config,
        )

    def build_intent(self,*,n=1,override=None):
        intent={
            "schema":INTENT_SCHEMA,
            "owner_id":"owner","tenant_id":"tenant","workspace_id":"workspace",
            "conversation_id":"conversation-ci",
            "message_id":f"message-{n}",
            "nonce_hex":f"{n:064x}",
            "signed_v2_intent_sha256":"a"*64,
            "full_provider_request_sha256":"b"*64,
            "primary_witness_receipt_sha256":"c"*64,
            "secondary_anchor_receipt_sha256":"d"*64,
            "key_registry_roster_sha256":"e"*64,
            "policy_generation":9,"period_id":"2026-10",
            "max_cost_micro_usd":80,
        }
        if override:
            intent.update(override)
        return intent

    def check(self, result):
        self.assertEqual(result["schema"],SCHEMA)
        for key,expected in NO_AUTHORITY.items():
            self.assertIs(result[key],expected,key)
        return result

    def prepare(self,intent=None):
        return self.check(self.journal.prepare_reference_only(
            self.intent if intent is None else intent,
        ))

    def claim(self,intent=None):
        return self.check(self.journal.claim_reference_only(
            intent=self.intent if intent is None else intent,
        ))

    def test_prepare_creates_only_unapproved_reference(self):
        r=self.prepare()
        self.assertEqual(r["state"],"PREPARED_REFERENCE_ONLY")
        self.assertEqual(r["stored_reference_state"],STATE_PREPARED)
        self.assertFalse(r["network_invocation_authorized"])
        self.assertFalse(r["provider_called"])

    def test_one_reference_claim_never_grants_network_authority(self):
        self.prepare()
        r=self.claim()
        self.assertEqual(r["state"],LOCAL_CLAIM)
        self.assertEqual(r["stored_reference_state"],STATE_CLAIMED)
        self.assertTrue(r["must_not_automatically_retry"])
        self.assertFalse(r["paid_dispatch_authorized"])
        self.assertFalse(r["paid_dispatch_performed"])

    def test_second_claim_exact_intent_denied_even_without_response(self):
        self.prepare()
        self.claim()
        o=self.claim()
        self.assertEqual(o["state"],REPLAY_BLOCKED)
        self.assertTrue(o["must_not_automatically_retry"])
        self.assertEqual(self.journal.read_reference_only(
            nonce_hex=self.intent["nonce_hex"])["stored_reference_state"],
            STATE_CLAIMED)

    def test_crash_after_claim_reopens_as_unknown_do_not_resend(self):
        self.prepare()
        self.claim()  # simulated crash before HTTP; no real call
        self.journal.close()
        self.journal=self.open_journal()
        recovered=self.check(self.journal.read_reference_only(
            nonce_hex=self.intent["nonce_hex"]))
        self.assertEqual(recovered["state"],"READ_ONLY_UNKNOWN_IF_CLAIMED")
        self.assertTrue(recovered["must_not_automatically_retry"])
        self.assertEqual(self.claim()["state"],REPLAY_BLOCKED)

    def test_mark_unknown_after_lost_response_idempotent_and_irreversible(self):
        self.prepare()
        self.claim()
        self.assertEqual(self.check(self.journal.mark_unknown_reference_only(
            nonce_hex=self.intent["nonce_hex"]))["stored_reference_state"],
            STATE_UNKNOWN)
        self.assertEqual(self.check(self.journal.mark_unknown_reference_only(
            nonce_hex=self.intent["nonce_hex"]))["state"],REPLAY_BLOCKED)
        self.assertEqual(self.claim()["state"],REPLAY_BLOCKED)
        self.journal.close()
        self.journal=self.open_journal()
        self.assertEqual(self.claim()["state"],REPLAY_BLOCKED)

    def test_mark_unknown_without_claim_disallowed(self):
        self.prepare()
        self.assertEqual(self.journal.mark_unknown_reference_only(
            nonce_hex=self.intent["nonce_hex"])["state"],"BLOCKED")

    def test_cancel_never_claimed_burns_nonce(self):
        self.prepare()
        r=self.check(self.journal.cancel_never_claimed_reference_only(
            nonce_hex=self.intent["nonce_hex"]))
        self.assertEqual(r["stored_reference_state"],STATE_CANCELLED)
        self.assertEqual(self.claim()["state"],REPLAY_BLOCKED)
        self.assertEqual(self.prepare()["state"],REPLAY_BLOCKED)
        self.assertEqual(self.journal.mark_unknown_reference_only(
            nonce_hex=self.intent["nonce_hex"])["state"],"BLOCKED")

    def test_cancel_after_claim_cannot_claim_never_sent(self):
        self.prepare()
        self.claim()
        self.assertEqual(self.journal.cancel_never_claimed_reference_only(
            nonce_hex=self.intent["nonce_hex"])["state"],"BLOCKED")

    def test_prepare_exact_retry_never_new_dispatch(self):
        self.prepare()
        r=self.prepare()
        self.assertEqual(r["state"],"ALREADY_PREPARED_REFERENCE_ONLY")
        self.assertFalse(r["reference_claim_written"])
        self.assertEqual(self.journal.local_snapshot_reference_only()["intent_count"],1)

    def test_same_nonce_for_different_provider_request_rejected(self):
        self.prepare()
        evil=self.build_intent(override={"full_provider_request_sha256":"f"*64})
        self.assertEqual(self.prepare(evil)["reason"],"NONCE_OR_MESSAGE_REBOUND_DETECTED")
        self.assertEqual(self.claim(evil)["reason"],"INTENT_REBOUND_AFTER_PREPARE")

    def test_same_message_with_new_nonce_or_intent_rejected(self):
        self.prepare()
        rebound=self.build_intent(n=2,override={"message_id":"message-1"})
        self.assertEqual(self.prepare(rebound)["reason"],"NONCE_OR_MESSAGE_REBOUND_DETECTED")

    def test_same_signed_digest_different_nonce_no_unsafe_reuse(self):
        self.prepare()
        other=self.build_intent(n=2)
        self.assertEqual(self.prepare(other)["state"],"BLOCKED")
        self.assertEqual(self.claim(other)["state"],"BLOCKED")

    def test_external_fingerprint_or_witness_digest_switch_blocked(self):
        self.prepare()
        for field in (
            "signed_v2_intent_sha256","full_provider_request_sha256",
            "primary_witness_receipt_sha256","secondary_anchor_receipt_sha256",
            "key_registry_roster_sha256","max_cost_micro_usd",
        ):
            with self.subTest(field=field):
                tampered=deepcopy(self.intent)
                tampered[field]=90 if field=="max_cost_micro_usd" else "f"*64
                self.assertEqual(self.claim(tampered)["state"],"BLOCKED")

    def test_invalid_scope_generation_nonce_or_cap_fails_closed(self):
        self.assertEqual(self.prepare(self.build_intent(
            override={"tenant_id":"attacker"}))["state"],"BLOCKED")
        self.assertEqual(self.prepare(self.build_intent(
            override={"policy_generation":True}))["state"],"BLOCKED")
        self.assertEqual(self.prepare(self.build_intent(
            override={"nonce_hex":"0"*64}))["state"],"BLOCKED")
        self.assertEqual(self.prepare(self.build_intent(
            override={"max_cost_micro_usd":301}))["state"],"BLOCKED")

    def test_new_request_after_claim_may_prepare_but_does_not_authorize(self):
        self.prepare()
        self.claim()
        new=self.build_intent(
            n=2,override={"signed_v2_intent_sha256":"1"*64},
        )
        self.assertEqual(self.prepare(new)["state"],"PREPARED_REFERENCE_ONLY")
        self.assertEqual(self.journal.local_snapshot_reference_only()["intent_count"],2)
        self.assertFalse(self.claim(new)["paid_dispatch_authorized"])

    def test_concurrent_different_processlike_connections_single_claim(self):
        self.prepare()
        def worker(_):
            instance=self.open_journal()
            try:
                return instance.claim_reference_only(intent=self.intent)["state"]
            finally:
                instance.close()
        with ThreadPoolExecutor(max_workers=5) as pool:
            results=list(pool.map(worker,range(12)))
        self.assertEqual(results.count(LOCAL_CLAIM),1)
        self.assertEqual(results.count(REPLAY_BLOCKED),11)

    def test_concurrent_prepare_single_row_same_nonce(self):
        def worker(_):
            instance=self.open_journal()
            try:
                return instance.prepare_reference_only(self.intent)["state"]
            finally:
                instance.close()
        with ThreadPoolExecutor(max_workers=5) as pool:
            results=list(pool.map(worker,range(10)))
        self.assertEqual(results.count("PREPARED_REFERENCE_ONLY"),1)
        self.assertEqual(results.count("ALREADY_PREPARED_REFERENCE_ONLY"),9)

    def test_insert_evidence_hash_not_provider_confirmation(self):
        self.prepare()
        self.claim()
        evidence="f"*64
        result=self.check(self.journal.append_evidence_digest_reference_only(
            nonce_hex=self.intent["nonce_hex"],evidence_sha256=evidence))
        self.assertEqual(result["state"],"EVIDENCE_DIGEST_NOTED_UNTRUSTED")
        self.assertFalse(result["provider_response_confirmed"])
        self.assertFalse(result["actual_cost_verified"])
        self.assertEqual(self.check(self.journal.append_evidence_digest_reference_only(
            nonce_hex=self.intent["nonce_hex"],evidence_sha256=evidence))["state"],
            "EVIDENCE_DIGEST_ALREADY_NOTED_REFERENCE_ONLY")
        self.assertEqual(self.claim()["state"],REPLAY_BLOCKED)

    def test_evidence_before_claim_forbidden(self):
        self.prepare()
        self.assertEqual(self.journal.append_evidence_digest_reference_only(
            nonce_hex=self.intent["nonce_hex"],evidence_sha256="f"*64)["state"],"BLOCKED")

    def test_same_after_restart_snapshot_commitment_stable(self):
        self.prepare()
        self.claim()
        prior=self.journal.local_snapshot_reference_only()
        self.journal.close()
        self.journal=self.open_journal()
        now=self.journal.local_snapshot_reference_only()
        self.assertEqual(now["snapshot_sha256"],prior["snapshot_sha256"])
        self.assertEqual(now["journal_sequence"],prior["journal_sequence"])
        self.assertFalse(now["journal_rollback_protection_verified"])

    def test_restore_older_sqlite_can_reclaim_negative_security_control(self):
        self.prepare()
        backup=Path(self.temp.name)/"older.db"
        with closing(sqlite3.connect(str(backup))) as db:
            self.journal.db.backup(db)
        self.claim()
        latest=self.journal.local_snapshot_reference_only()
        self.assertEqual(latest["journal_sequence"],2)
        self.journal.close()
        shutil.copyfile(backup,self.path)
        self.journal=self.open_journal()
        old=self.journal.local_snapshot_reference_only()
        self.assertEqual(old["journal_sequence"],1)
        self.assertNotEqual(latest["snapshot_sha256"],old["snapshot_sha256"])
        self.assertFalse(old["journal_rollback_protection_verified"])
        # Deliberate counterexample! This is WHY a separately protected
        # high-watermark is mandatory BEFORE enabling any paid HTTP.
        self.assertEqual(self.claim()["state"],LOCAL_CLAIM)
        self.assertFalse(self.journal.read_reference_only(
            nonce_hex=self.intent["nonce_hex"])["paid_dispatch_authorized"])

    def test_tampered_intent_or_sequence_detected_and_no_claim(self):
        self.prepare()
        self.journal.db.execute(
            "UPDATE aion_dispatch_intents SET intent_sha256=?",
            ("f"*64,),
        )
        self.assertEqual(self.claim()["state"],"BLOCKED")
        self.assertEqual(self.journal.local_snapshot_reference_only()["state"],"BLOCKED")

    def test_unknown_state_without_claim_rejected_by_integrity_check(self):
        self.prepare()
        self.journal.db.execute(
            "UPDATE aion_dispatch_intents SET state=?",
            (STATE_UNKNOWN,),
        )
        self.assertEqual(self.claim()["state"],"BLOCKED")

    def test_commit_storage_fault_atomic_no_partial_claim(self):
        self.prepare()
        self.journal.db.execute("""
            CREATE TRIGGER synthetic_fault BEFORE UPDATE ON aion_dispatch_intents
            BEGIN SELECT RAISE(ABORT,'fault'); END
        """)
        self.assertEqual(self.claim()["state"],"BLOCKED")
        self.journal.db.execute("DROP TRIGGER synthetic_fault")
        self.assertEqual(self.journal.read_reference_only(
            nonce_hex=self.intent["nonce_hex"])["stored_reference_state"],
            STATE_PREPARED)
        self.assertEqual(self.claim()["state"],LOCAL_CLAIM)

    def test_config_tamper_or_missing_state_no_rebootstrap(self):
        self.prepare()
        cfg=deepcopy(self.config)
        cfg["period_id"]="2026-11"
        with self.assertRaises(ValueError):
            self.open_journal(config=cfg)
        self.journal.db.execute("DELETE FROM aion_dispatch_config")
        self.assertEqual(self.claim()["state"],"BLOCKED")
        self.journal.close()
        with self.assertRaises(ValueError):
            self.open_journal()
        # tearDown needs a usable handle, restore a fresh disposable DB
        self.path=Path(self.temp.name)/"new-disposable.db"
        self.journal=self.open_journal()

    def test_claim_without_prepare_or_missing_nonce_never_sent(self):
        self.assertEqual(self.claim()["state"],"BLOCKED")
        self.assertEqual(self.journal.read_reference_only(
            nonce_hex=self.intent["nonce_hex"])["state"],"BLOCKED")

    def test_no_network_gateway_or_private_key_called(self):
        self.prepare()
        with patch("requests.post",side_effect=AssertionError("paid API")), \
             patch("atlasquant_aion_provider.execute_openai_answer",
                   side_effect=AssertionError("model")):
            self.assertEqual(self.claim()["state"],LOCAL_CLAIM)
            self.assertEqual(self.journal.mark_unknown_reference_only(
                nonce_hex=self.intent["nonce_hex"])["stored_reference_state"],
                STATE_UNKNOWN)
        self.assertFalse(self.claim()["provider_called"])
        self.assertFalse(self.claim()["billing_authorized"])


if __name__ == "__main__":
    unittest.main()
