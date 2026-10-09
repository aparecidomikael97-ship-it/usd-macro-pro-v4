"""Adversarial local recovery ID capture + no-network GET route reference tests."""
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
    INTENT_SCHEMA,ReferenceOneShotUnknownOutcomeJournal,
)
from atlasquant_aion_v2_readonly_recovery_id_capture_reference import (
    SCHEMA,CAPTURE_SCHEMA,CAPTURED,EXISTING,GET_PLAN,
    ReferenceDurableRecoveryIdCapture,
)
from atlasquant_aion_v2_provider_recovery_capability_reference import (
    MODE_OPENAI_BACKGROUND,MODE_OPENAI_STORED,MODE_ANTHROPIC_BATCH,
    MODE_OPENAI_UNSTORED,MODE_ANTHROPIC_SYNC,MODE_GEMINI_SYNC,
)


class RecoveryCaptureAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        root=Path(self.tmp.name)
        self.capture_path=root/"local-recovery-ids.db"
        self.journal_path=root/"local-dispatch.db"
        self.config={
            "owner_id":"owner","tenant_id":"tenant",
            "workspace_id":"workspace","period_id":"2026-10",
            "policy_generation":9,"max_period_micro_usd":500,
        }
        self.intent={
            "schema":INTENT_SCHEMA,"owner_id":"owner",
            "tenant_id":"tenant","workspace_id":"workspace",
            "conversation_id":"conversation","message_id":"message-one",
            "nonce_hex":"a"*64,
            "signed_v2_intent_sha256":"b"*64,
            "full_provider_request_sha256":"c"*64,
            "primary_witness_receipt_sha256":"d"*64,
            "secondary_anchor_receipt_sha256":"e"*64,
            "key_registry_roster_sha256":"f"*64,
            "policy_generation":9,"period_id":"2026-10",
            "max_cost_micro_usd":100,
        }
        self.journal=ReferenceOneShotUnknownOutcomeJournal(
            self.journal_path,config=self.config,
        )
        self.capture_db=self.open_capture()
        self.assertEqual(self.journal.prepare_reference_only(
            self.intent)["state"],"PREPARED_REFERENCE_ONLY")
        self.assertEqual(self.journal.claim_reference_only(
            intent=self.intent)["state"],"LOCAL_REFERENCE_CLAIM_RECORDED_UNTRUSTED")
        self.cap=self.observation()

    def tearDown(self):
        self.capture_db.close()
        self.journal.close()
        self.tmp.cleanup()

    def open_capture(self):
        return ReferenceDurableRecoveryIdCapture(
            self.capture_path,journal=self.journal,
        )

    def observation(self,mode=MODE_OPENAI_BACKGROUND,**kwargs):
        prov="anthropic" if mode==MODE_ANTHROPIC_BATCH else "openai"
        loc={
            "response_id":"resp_ci_known_1" if prov=="openai" else "",
            "batch_id":"msgbatch_ci_1" if prov=="anthropic" else "",
            "batch_custom_id":"custom_ci_1" if prov=="anthropic" else "",
            "diagnostic_request_id":"",
        }
        cap={
            "schema":CAPTURE_SCHEMA,
            "source_kind":"CI_SYNTHETIC_PROVIDER_ID_ALREADY_RECEIVED",
            "provider":prov,"mode":mode,
            "owner_id":"owner","tenant_id":"tenant","workspace_id":"workspace",
            "nonce_hex":self.intent["nonce_hex"],
            "signed_v2_intent_sha256":self.intent["signed_v2_intent_sha256"],
            "full_provider_request_sha256":self.intent["full_provider_request_sha256"],
            "key_registry_roster_sha256":self.intent["key_registry_roster_sha256"],
            "claim_sequence":2,
            "documented_retention_opt_in":mode==MODE_OPENAI_STORED,
            "locator":loc,
        }
        cap.update(kwargs)
        return cap

    def check(self,o):
        self.assertEqual(o["schema"],SCHEMA)
        self.assertTrue(o["must_not_automatically_retry"])
        for field in (
            "real_response_id_captured","real_response_id_provenance_verified",
            "paid_model_post_authorized","paid_model_post_sent",
            "network_called","get_performed","billing_settlement_verified",
            "journal_externally_anchored","safe_to_resume",
        ):
            self.assertFalse(o[field],field)
        self.assertFalse(o["same_nonce_reusable"])
        return o

    def capture(self,cap=None,*,journal=None,intent=None,db=None):
        return self.check((db or self.capture_db).capture_reference_only(
            journal=self.journal if journal is None else journal,
            intent=self.intent if intent is None else intent,
            observed_capture=self.cap if cap is None else cap,
        ))

    def plan(self,*,db=None,intent=None):
        return self.check((db or self.capture_db).plan_recovery_get_reference_only(
            journal=self.journal,
            intent=self.intent if intent is None else intent,
        ))

    def test_capture_already_observed_response_id_no_http(self):
        r=self.capture()
        self.assertEqual(r["state"],CAPTURED)
        self.assertEqual(r["local_sequence"],1)
        self.assertFalse(r["real_response_id_captured"])

    def test_plan_is_relative_get_only_with_never_post_permission(self):
        self.capture()
        p=self.plan()
        self.assertEqual(p["state"],GET_PLAN)
        self.assertEqual(p["relative_get_paths_for_offline_review"],[
            {"method":"GET","relative_path":"/v1/responses/resp_ci_known_1"}
        ])
        self.assertFalse(p["get_performed"])

    def test_capture_after_restart_persisted_and_plan_still_no_network(self):
        self.capture()
        original=self.capture_db.local_snapshot_reference_only()
        self.capture_db.close()
        self.capture_db=self.open_capture()
        self.assertEqual(self.plan()["state"],GET_PLAN)
        self.assertEqual(
            self.capture_db.local_snapshot_reference_only()["snapshot_sha256"],
            original["snapshot_sha256"],
        )

    def test_recapture_exact_same_id_is_read_only_not_second_record(self):
        self.capture()
        r=self.capture()
        self.assertEqual(r["state"],EXISTING)
        self.assertEqual(r["local_sequence"],1)

    def test_rebind_same_nonce_to_other_provider_response_id_rejected(self):
        self.capture()
        altered=deepcopy(self.cap)
        altered["locator"]["response_id"]="resp_other_result"
        r=self.capture(altered)
        self.assertEqual(r["state"],"BLOCKED")
        self.assertEqual(r["reason"],"CAPTURE_NONCE_SIGNED_INTENT_OR_ID_REBOUND")

    def test_cannot_store_if_provider_id_not_received_before_crash(self):
        unknown=deepcopy(self.cap)
        unknown["locator"]["response_id"]=""
        self.assertEqual(self.capture(unknown)["state"],"BLOCKED")
        self.assertEqual(self.plan()["reason"],"NO_PREVIOUSLY_STORED_RESPONSE_ID")

    def test_prepared_state_cannot_capture_provider_response(self):
        i=deepcopy(self.intent)
        i["message_id"]="message-two"
        i["nonce_hex"]="1"*64
        i["signed_v2_intent_sha256"]="2"*64
        self.journal.prepare_reference_only(i)
        o=self.observation(
            nonce_hex=i["nonce_hex"],signed_v2_intent_sha256=i[
                "signed_v2_intent_sha256"],
        )
        self.assertEqual(self.capture(o,intent=i)["reason"],
                         "JOURNAL_CLAIM_ABSENT_RESTORED_OR_CORRUPT")

    def test_capture_after_unknown_outcome_is_only_alleged_response(self):
        self.journal.mark_unknown_reference_only(nonce_hex=self.intent["nonce_hex"])
        r=self.capture()
        self.assertEqual(r["state"],CAPTURED)
        self.assertFalse(r["provider_object_retrieved"])
        self.assertEqual(self.plan()["state"],GET_PLAN)

    def test_anthropic_batch_plan_only_known_batch_plus_custom(self):
        o=self.observation(MODE_ANTHROPIC_BATCH)
        self.assertEqual(self.capture(o)["state"],CAPTURED)
        plan=self.plan()
        self.assertEqual(plan["state"],GET_PLAN)
        self.assertEqual(plan["relative_get_paths_for_offline_review"],[
            {"method":"GET","relative_path":"/v1/messages/batches/msgbatch_ci_1"},
            {"method":"GET","relative_path":"/v1/messages/batches/msgbatch_ci_1/results"},
        ])

    def test_stored_openai_response_optin_required(self):
        stored=self.observation(MODE_OPENAI_STORED)
        self.assertEqual(self.capture(stored)["state"],CAPTURED)
        self.assertEqual(self.plan()["state"],GET_PLAN)

    def test_no_supported_http_get_for_sync_anthropic_or_gemini(self):
        for mode,provider in (
            (MODE_ANTHROPIC_SYNC,"anthropic"),
            (MODE_GEMINI_SYNC,"gemini"),
            (MODE_OPENAI_UNSTORED,"openai"),
        ):
            with self.subTest(mode=mode):
                x=self.observation(mode,provider=provider)
                self.assertEqual(self.capture(x)["state"],"BLOCKED")

    def test_hostile_locator_path_traversal_and_query_injection_refused(self):
        values=(
            "../admin","resp_../../secret","resp_%2e%2e",
            "resp_ok?method=POST","resp_ok#fragment",
            "resp_ABC/../../v1/chat/completions",
            "resp_a\\b","resp_a%2Ffoo",
        )
        for value in values:
            with self.subTest(value=value):
                x=deepcopy(self.cap)
                x["locator"]["response_id"]=value
                self.assertEqual(self.capture(x)["state"],"BLOCKED")

    def test_wrong_owner_tenant_request_hash_roster_or_claim_sequence_rejected(self):
        for name,value in (
            ("owner_id","attacker"),("tenant_id","other"),
            ("nonce_hex","1"*64),("signed_v2_intent_sha256","2"*64),
            ("full_provider_request_sha256","3"*64),
            ("key_registry_roster_sha256","4"*64),
            ("claim_sequence",3),
        ):
            with self.subTest(field=name):
                x=deepcopy(self.cap)
                x[name]=value
                self.assertEqual(self.capture(x)["state"],"BLOCKED")

    def test_no_claim_replay_via_new_signed_request_nonce(self):
        self.capture()
        i=deepcopy(self.intent)
        i["nonce_hex"]="1"*64
        i["message_id"]="message-two"
        i["signed_v2_intent_sha256"]="2"*64
        self.assertEqual(self.plan(intent=i)["state"],"BLOCKED")

    def test_source_kind_fake_claim_must_be_exact_no_other_claimed_provenance(self):
        x=deepcopy(self.cap)
        x["source_kind"]="REAL_PROVIDER_SIGNED_RECEIPT"  # forged claim
        self.assertEqual(self.capture(x)["state"],"BLOCKED")

    def test_unhashable_or_nontext_mode_fails_closed_without_exception(self):
        for value in (["OPENAI_RESPONSES_BACKGROUND"],{"mode":"openai"},True,None,42):
            with self.subTest(value=repr(value)):
                candidate=deepcopy(self.cap)
                candidate["mode"]=value
                result=self.capture(candidate)
                self.assertEqual(result["state"],"BLOCKED")
                self.assertEqual(result["reason"],"INVALID_CAPTURABLE_ID_OBSERVATION")

    def test_unsupported_method_or_unexpected_field_cannot_be_persisted(self):
        x=deepcopy(self.cap)
        x["method"]="POST"
        self.assertEqual(self.capture(x)["state"],"BLOCKED")
        x=deepcopy(self.cap)
        x["locator"]["api_key"]="secret"
        self.assertEqual(self.capture(x)["state"],"BLOCKED")

    def test_simulated_id_can_be_forged_by_callers_negative_control(self):
        o=self.observation()
        self.assertEqual(self.capture(o)["state"],CAPTURED)
        self.assertFalse(self.plan()["real_response_id_provenance_verified"])
        self.assertFalse(self.plan()["trusted_witness_heads_live_verified"])

    def test_concurrent_identical_capture_only_one_write(self):
        def work(_):
            independent_journal=ReferenceOneShotUnknownOutcomeJournal(
                self.journal_path,config=self.config,
            )
            inst=ReferenceDurableRecoveryIdCapture(
                self.capture_path,journal=independent_journal,
            )
            try:
                return inst.capture_reference_only(
                    journal=independent_journal,intent=self.intent,
                    observed_capture=self.cap,
                )["state"]
            finally:
                inst.close()
                independent_journal.close()
        with ThreadPoolExecutor(max_workers=5) as pool:
            results=list(pool.map(work,range(10)))
        self.assertEqual(results.count(CAPTURED),1)
        self.assertEqual(results.count(EXISTING),9)
        self.assertEqual(self.capture_db.local_snapshot_reference_only()[
            "local_sequence"],1)

    def test_local_capture_corruption_denies_get_plan(self):
        self.capture()
        self.capture_db.db.execute(
            "UPDATE aion_recovery_ids_ref SET capture_sha256=?",
            ("0"*64,),
        )
        self.assertEqual(self.plan()["state"],"BLOCKED")

    def test_sqlite_error_during_capture_rolls_back_atomic_row(self):
        self.capture_db.db.execute("""
            CREATE TRIGGER ci_fail BEFORE UPDATE ON aion_recovery_policy_ref
            BEGIN SELECT RAISE(ABORT,'fail'); END
        """)
        self.assertEqual(self.capture()["state"],"BLOCKED")
        self.capture_db.db.execute("DROP TRIGGER ci_fail")
        self.assertEqual(self.capture_db.local_snapshot_reference_only()[
            "local_sequence"],0)
        self.assertEqual(self.capture()["state"],CAPTURED)

    def test_local_capture_rollback_loses_response_id_negative_control(self):
        backup=Path(self.tmp.name)/"older-capture.db"
        with closing(sqlite3.connect(str(backup))) as conn:
            self.capture_db.db.backup(conn)
        self.capture()
        current=self.capture_db.local_snapshot_reference_only()
        self.capture_db.close()
        shutil.copyfile(backup,self.capture_path)
        self.capture_db=self.open_capture()
        self.assertEqual(self.plan()["state"],"BLOCKED")
        self.assertEqual(self.capture_db.local_snapshot_reference_only()[
            "local_sequence"],0)
        self.assertFalse(current["journal_externally_anchored"])

    def test_local_journal_rollback_may_rebind_intent_claim_negative_control(self):
        self.capture()
        # The same captured ID paired to an independently restored journal
        # can still pass local math. This cannot establish protected freshness.
        self.assertEqual(self.plan()["state"],GET_PLAN)
        self.assertFalse(self.plan()["journal_externally_anchored"])

    def test_different_local_policy_no_silent_rebootstrap(self):
        self.capture()
        wrong=deepcopy(self.config)
        wrong["period_id"]="2026-11"
        fake_journal=ReferenceOneShotUnknownOutcomeJournal(
            Path(self.tmp.name)/"different-journal.db",config=wrong,
        )
        try:
            with self.assertRaises(ValueError):
                ReferenceDurableRecoveryIdCapture(
                    self.capture_path,journal=fake_journal,
                )
        finally:
            fake_journal.close()

    def test_no_provider_or_http_call_even_with_route_plan(self):
        with patch("requests.post",side_effect=AssertionError("POST")), \
             patch("requests.get",side_effect=AssertionError("GET")), \
             patch("atlasquant_aion_provider.execute_openai_answer",
                   side_effect=AssertionError("paid model")):
            self.capture()
            r=self.plan()
            self.assertEqual(r["state"],GET_PLAN)
            self.assertEqual({x["method"] for x in r[
                "relative_get_paths_for_offline_review"]},{"GET"})
        self.assertFalse(r["network_called"])


if __name__=="__main__":
    unittest.main()
