"""A109 LAB: negative authority boundaries; no source, adapter, Worker or real effects.

New tests deliberately co-exist with the historic RED tests, unchanged.
They use only synthetic checkpoints and caller-controlled witness claims.
Passing them is NOT independent F1/T1/H0/F2 proof or release readiness.
"""
import base64
from copy import deepcopy
from datetime import timedelta
import unittest
from unittest.mock import patch

import test_atlasquant_aion_global_worker_inflight_resolution as historic
from atlasquant_aion_global_worker_inflight_resolution import (
    CONFIRMATION_PHRASE, stage_resolved_inflight_clear,
)
from atlasquant_aion_f1_t1_untrusted_witness_intake_a75 import (
    SCHEMA as WITNESS_SCHEMA, inspect_untrusted_witness_claim,
)
from atlasquant_aion_global_worker import _persist_runtime_checkpoint_cas


class A109InflightNeverClearsWithoutExternalRoot(unittest.TestCase):
    def setUp(self):
        self.f = historic.GlobalInflightResolutionTests(
            methodName="test_confirmation_is_required_before_any_staging"
        )
        self.f.setUp()
        self.claimed, self.intent = self.f.claim(self.f.due_checkpoint())
        self.assertEqual(self.intent["count"], 1)
        self.runtime = self.f.runtime(self.claimed, sha="A109_SYNTHETIC_ONLY")

    def stage(self, runtime=None, *, access=None, now=None):
        return stage_resolved_inflight_clear(
            self.f.access if access is None else access,
            self.runtime if runtime is None else runtime,
            confirmation=True,
            confirmation_phrase=CONFIRMATION_PHRASE,
            now=historic.AFTER_EXPIRY if now is None else now,
        )

    def assert_no_clear(self, result, original):
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIs(result["requires_checkpoint_save"], False)
        self.assertIs(result["external_persisted"], False)
        self.assertIs(result["executes_action"], False)
        self.assertEqual(result["checkpoint"], original)

    def test_01_empty_batch_and_expired_lease_do_not_authorize_clear(self):
        empty, intent = self.f.claim(self.f.arm({}))
        self.assertEqual(intent["count"], 0)
        before = deepcopy(empty)
        result = self.stage(self.f.runtime(empty, sha="A109_EMPTY"))
        self.assert_no_clear(result, before)
        self.assertEqual(
            result["assessment_status"],
            "UNVERIFIED_EMPTY_BATCH_REVIEW_REQUIRED",
        )
        self.assertIs(result["automatic_retry_allowed"], False)
        self.assertEqual(empty, before)

    def test_02_lost_executor_receipt_is_ambiguous_and_no_clear(self):
        before = deepcopy(self.claimed)
        result = self.stage()
        self.assert_no_clear(result, before)
        self.assertEqual(
            result["assessment_status"], "AMBIGUOUS_EXECUTION_REVIEW_REQUIRED"
        )
        self.assertIs(result["automatic_retry_allowed"], False)
        self.assertEqual(self.claimed, before)

    def test_03_fake_terminal_label_cannot_stage_even_with_admin_confirmation(self):
        before = deepcopy(self.claimed)
        with patch(
            "atlasquant_aion_global_worker_inflight_resolution."
            "assess_global_inflight_reconciliation",
            return_value={
                "status": "TERMINAL_EVIDENCE_READY_FOR_HUMAN_CLEAR",
                "terminal_proven": 999,
                "automatic_clear_allowed": True,
                "signed_by_owner": True,
                "external_source_verified": True,
            },
        ) as forged:
            result = self.stage()
        forged.assert_called_once()
        self.assert_no_clear(result, before)
        self.assertEqual(result["reason"], "INDEPENDENT_INFLIGHT_CLEAR_PROOF_NOT_ENROLLED")
        self.assertIs(result["automatic_retry_allowed"], False)
        self.assertEqual(self.claimed, before)

    def test_04_caller_witness_flags_cannot_override_external_no_go(self):
        runtime = dict(self.runtime)
        runtime.update({
            "independent_witness_verified": True,
            "source_authenticity_verified": True,
            "producer_terminal_receipt_verified": True,
            "human_owner_verified": True,
        })
        before = deepcopy(self.claimed)
        with patch(
            "atlasquant_aion_global_worker_inflight_resolution."
            "assess_global_inflight_reconciliation",
            return_value={"status": "TERMINAL_EVIDENCE_READY_FOR_HUMAN_CLEAR"},
        ):
            result = self.stage(runtime)
        self.assert_no_clear(result, before)
        self.assertEqual(result["reason"], "INDEPENDENT_INFLIGHT_CLEAR_PROOF_NOT_ENROLLED")

    def test_05_live_lease_blocks_even_with_forged_positive_assessment(self):
        before = deepcopy(self.claimed)
        with patch(
            "atlasquant_aion_global_worker_inflight_resolution."
            "assess_global_inflight_reconciliation",
            return_value={"status": "TERMINAL_EVIDENCE_READY_FOR_HUMAN_CLEAR"},
        ):
            result = self.stage(now=historic.TICK + timedelta(seconds=30))
        self.assert_no_clear(result, before)
        self.assertEqual(result["reason"], "EXPIRED_OWNED_LEASE_REQUIRED")

    def test_06_other_admin_cannot_clear_despite_forged_terminal_label(self):
        before = deepcopy(self.claimed)
        other_admin = historic._access(
            username="OTHER_A109",
            fingerprint="other-a109-admin-fingerprint-9876543210",
        )
        with patch(
            "atlasquant_aion_global_worker_inflight_resolution."
            "assess_global_inflight_reconciliation",
            return_value={"status": "TERMINAL_EVIDENCE_READY_FOR_HUMAN_CLEAR"},
        ):
            result = self.stage(access=other_admin)
        self.assert_no_clear(result, before)
        self.assertEqual(result["reason"], "GLOBAL_WORKER_CONTEXT_MISMATCH")

    def test_07_confirmation_missing_does_not_consume_positive_assessment(self):
        before = deepcopy(self.claimed)
        with patch(
            "atlasquant_aion_global_worker_inflight_resolution."
            "assess_global_inflight_reconciliation"
        ) as assessor:
            result = stage_resolved_inflight_clear(
                self.f.access, self.runtime, confirmation=False,
                confirmation_phrase=CONFIRMATION_PHRASE, now=historic.AFTER_EXPIRY
            )
        assessor.assert_not_called()
        self.assert_no_clear(result, before)
        self.assertEqual(result["reason"], "EXPLICIT_ADMIN_CONFIRMATION_REQUIRED")


class A109IndependentSourceNeverSelfAttests(unittest.TestCase):
    def test_08_syntactically_valid_claim_is_still_untrusted_and_non_authoritative(self):
        scope = {
            "repo_id": 12345, "owner_id": 98765,
            "branch": "atlasquant-runtime",
            "path": "dados/aion/checkpoint_master.json",
            "tenant_id": "TENANT_SYNTHETIC", "workspace_id": "WORKSPACE_SYNTHETIC",
        }
        claim = {
            "schema": WITNESS_SCHEMA, **scope,
            "head_sha": "a" * 40,
            "checkpoint_blob_sha": "b" * 40,
            "checkpoint_digest": "c" * 64,
            "epoch": 1, "sequence": 1, "previous_sequence": 0,
            "previous_head_sha": "GENESIS",
            "nonce": "A109SyntheticNonce1234567890AB",
            "issued_at": "2026-10-16T11:59:00Z",
            "expires_at": "2026-10-16T12:01:00Z",
            "witness_issuer": "NOT_A_REAL_ISSUER",
            "key_id": "NOT_A_REAL_KEY",
            "signature_b64": base64.b64encode(b"x" * 64).decode("ascii"),
        }
        result = inspect_untrusted_witness_claim(
            claim, expected_scope=scope,
            now_ts="2026-10-16T12:00:00Z",
            observed_snapshot={
                "head_sha": claim["head_sha"],
                "checkpoint_blob_sha": claim["checkpoint_blob_sha"],
            },
            locally_known_high_water=0,
        )
        self.assertIs(result["local_format_consistent"], True)
        self.assertEqual(result["status"], "BLOCKED")
        for flag in (
            "claim_signature_verified",
            "external_custody_verified",
            "fresh_github_head_independently_verified",
            "monotonic_high_water_independently_verified",
            "source_authenticity_verified",
            "worker_execution_allowed",
            "external_activation_allowed",
            "network_called",
            "runtime_modified",
        ):
            self.assertIs(result[flag], False, flag)

    def test_09_writer_boundary_denies_before_reading_untrusted_config(self):
        class ExplosiveConfig:
            def __getattribute__(self, name):
                raise AssertionError("no config inspection allowed before witness enrollment")
        result = _persist_runtime_checkpoint_cas(
            {}, ExplosiveConfig(), expected_sha="synthetic_sha",
            operation="A109_DENIAL_ONLY",
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "INDEPENDENT_SOURCE_WITNESS_NOT_ENROLLED")
        for key in (
            "saved", "verified", "write_accepted", "network_called",
            "external_action_executed", "automatic_retry_allowed",
        ):
            self.assertIs(result[key], False, key)
        self.assertEqual(result["write_outcome"], "NOT_ATTEMPTED")


if __name__ == "__main__":
    unittest.main()
