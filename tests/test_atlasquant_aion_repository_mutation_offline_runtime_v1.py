import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from atlasquant_aion_repository_mutation_authorization_receipt_v1 import (
    MECHANISM,
    PURPOSE,
    RECEIPT_SCHEMA,
)
from atlasquant_aion_repository_mutation_offline_runtime_v1 import (
    PROVIDER_IDENTITY,
    SIGNATURE_CONTEXT,
    LocalRepositoryMutationStore,
    OfflineRepositoryMutationRuntime,
    OfflineRuntimeError,
    SyntheticPullRequest,
    SyntheticRepositoryMutationAdapter,
    SyntheticRepositoryState,
    offline_runtime_policy,
    owner_public_key_fingerprint,
    verify_external_owner_ed25519_signature,
)


D = lambda c: "sha256:" + (c * 64)


def canonical(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=str,
    )


def digest(value):
    return "sha256:" + hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


class AionRepositoryMutationOfflineRuntimeV1Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "runtime.sqlite3"
        self.store = LocalRepositoryMutationStore(self.db)
        self.private_key = Ed25519PrivateKey.generate()
        raw_public = self.private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.public_b64 = base64.b64encode(raw_public).decode("ascii")
        self.fingerprint = owner_public_key_fingerprint(self.public_b64)
        self.repository = SyntheticRepositoryState(
            repository_id="repo://atlasquant/offline",
            main_sha="a" * 40,
            main_tree_sha="b" * 40,
            pull_requests={
                1015: SyntheticPullRequest(
                    number=1015,
                    head_sha="c" * 40,
                    base_branch="main",
                    draft=True,
                    open=True,
                ),
                1016: SyntheticPullRequest(
                    number=1016,
                    head_sha="d" * 40,
                    base_branch="impl/parent-v1",
                    draft=True,
                    open=True,
                ),
            },
        )
        self.adapter = SyntheticRepositoryMutationAdapter(self.repository)
        self.runtime = OfflineRepositoryMutationRuntime(
            store=self.store,
            adapter=self.adapter,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def receipt(
        self,
        *,
        receipt_id="receipt-local-1",
        pr_number=1015,
        mutation="PR_DRAFT_TO_READY",
        main_sha=None,
        main_tree_sha=None,
        head_sha=None,
        base_branch=None,
        issued_at="2026-10-08T10:00:00+00:00",
        expires_at="2026-10-08T10:02:00+00:00",
        verified_at="2026-10-08T10:00:05+00:00",
    ):
        pr = self.repository.get_pr(pr_number)
        material = {
            "receipt_id": receipt_id,
            "purpose": PURPOSE,
            "mechanism": MECHANISM,
            "pr_number": pr_number,
            "requested_mutation": mutation,
            "owner_subject": "owner://mikael",
            "owner_binding_digest": D("1"),
            "owner_key_fingerprint": D("2"),
            "challenge_digest": D("3"),
            "signature_attestation_digest": D("4"),
            "decision_digest": D("5"),
            "live_rebuilt_preflight_digest": D("6"),
            "main_sha": main_sha or self.repository.main_sha,
            "main_tree_sha": main_tree_sha or self.repository.main_tree_sha,
            "head_branch": f"synthetic/pr-{pr_number}",
            "head_sha": head_sha or pr.head_sha,
            "base_branch": base_branch or pr.base_branch,
            "file_delta_digest": D("7"),
            "workflow_snapshot_digest": D("8"),
            "readiness_digest": D("9"),
            "rollback_plan_digest": D("a"),
            "authorization_nonce_digest": D("b"),
            "persistent_authorization_nonce_replay_guard_verified": True,
            "authorization_nonce_single_use_claimed": True,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "verified_at": verified_at,
        }
        return {
            "schema": RECEIPT_SCHEMA,
            "state": "REPOSITORY_MUTATION_AUTHORIZATION_VERIFIED",
            "blockers": [],
            **material,
            "authorization_receipt_digest": digest(material),
            "repository_mutation_authorized": True,
            "authorized_for_exactly_one_mutation": True,
            "authorization_single_use": True,
            "authorization_persisted": False,
            "persistence_attested": False,
            "authorization_consumed": False,
            "authorization_reuse_allowed": False,
            "authorization_scope_expansion_allowed": False,
            "authorization_pr_change_allowed": False,
            "authorization_mutation_change_allowed": False,
            "authorization_head_change_allowed": False,
            "authorization_main_change_allowed": False,
            "authorization_base_change_allowed": False,
            "execution_time_state_rebuild_required": True,
            "execution_time_exact_receipt_match_required": True,
            "atomic_authorization_consumption_required": True,
            "repository_mutation_performed": False,
            "merge_executed": False,
            "retarget_executed": False,
            "draft_transition_executed": False,
            "branch_deleted": False,
            "deploy_executed": False,
            "worker_activated": False,
            "provider_activated": False,
            "production_persistence_activated": False,
            "executes_action": False,
        }

    def sign_receipt(self, receipt):
        message = SIGNATURE_CONTEXT + receipt[
            "authorization_receipt_digest"
        ].encode("ascii")
        signature = self.private_key.sign(message)
        out = verify_external_owner_ed25519_signature(
            authorization_receipt=receipt,
            owner_public_key_b64=self.public_b64,
            signature_b64=base64.b64encode(signature).decode("ascii"),
            expected_owner_key_fingerprint=self.fingerprint,
        )
        self.assertEqual(out["state"], "OWNER_SIGNATURE_VERIFIED", out["blockers"])
        return out

    def open_kill_switch(self, at="2026-10-08T09:59:00+00:00"):
        return self.store.set_kill_switch(
            enabled=False,
            reason="OFFLINE_SYNTHETIC_TEST",
            updated_at=at,
        )

    def test_store_bootstraps_fail_closed_with_kill_switch_enabled(self):
        status = self.store.kill_switch_status()
        self.assertTrue(status["enabled"])
        self.assertEqual(status["reason"], "BOOTSTRAP_FAIL_CLOSED")
        self.assertEqual(self.store.schema_version(), 1)
        policy = offline_runtime_policy()
        self.assertTrue(policy["kill_switch_default_enabled"])
        self.assertTrue(policy["kill_switch_implemented"])

    def test_external_ed25519_signature_is_real_verify_only(self):
        receipt = self.receipt()
        att = self.sign_receipt(receipt)
        self.assertTrue(att["signature_verified"])
        self.assertEqual(att["owner_key_fingerprint"], self.fingerprint)
        self.assertFalse(att["private_key_loaded"])
        self.assertFalse(att["private_key_generated"])
        self.assertFalse(att["signature_generated_by_this_module"])
        self.assertFalse(att["github_api_called"])
        self.assertFalse(att["network_called"])

        tampered = dict(receipt)
        tampered["authorization_receipt_digest"] = D("0")
        bad = verify_external_owner_ed25519_signature(
            authorization_receipt=tampered,
            owner_public_key_b64=self.public_b64,
            signature_b64=base64.b64encode(
                self.private_key.sign(
                    SIGNATURE_CONTEXT
                    + receipt["authorization_receipt_digest"].encode("ascii")
                )
            ).decode("ascii"),
            expected_owner_key_fingerprint=self.fingerprint,
        )
        self.assertEqual(bad["state"], "BLOCKED")
        self.assertIn("OWNER_SIGNATURE_NOT_VERIFIED", bad["blockers"])

    def test_nonce_registry_rejects_replay_durably(self):
        self.store.reserve_nonce_once(
            scope="runtime-attempt",
            nonce_digest=D("c"),
            reserved_at="2026-10-08T10:00:00+00:00",
            expires_at="2026-10-08T10:01:00+00:00",
        )
        with self.assertRaises(OfflineRuntimeError) as ctx:
            self.store.reserve_nonce_once(
                scope="runtime-attempt",
                nonce_digest=D("c"),
                reserved_at="2026-10-08T10:00:01+00:00",
                expires_at="2026-10-08T10:01:00+00:00",
            )
        self.assertEqual(ctx.exception.code, "NONCE_REPLAY_REJECTED")

        reopened = LocalRepositoryMutationStore(self.db)
        with self.assertRaises(OfflineRuntimeError) as ctx2:
            reopened.reserve_nonce_once(
                scope="runtime-attempt",
                nonce_digest=D("c"),
                reserved_at="2026-10-08T10:00:02+00:00",
                expires_at="2026-10-08T10:01:00+00:00",
            )
        self.assertEqual(ctx2.exception.code, "NONCE_REPLAY_REJECTED")

    def test_kill_switch_blocks_before_authorization_consumption(self):
        receipt = self.receipt()
        signature = self.sign_receipt(receipt)
        with self.assertRaises(OfflineRuntimeError) as ctx:
            self.runtime.execute_once(
                authorization_receipt=receipt,
                owner_signature_attestation=signature,
                runtime_nonce_scope="attempt/1015/1",
                runtime_nonce_digest=D("c"),
                attempt_id="attempt-1015-1",
                behavior="SUCCESS",
                now="2026-10-08T10:00:10+00:00",
            )
        self.assertEqual(ctx.exception.code, "KILL_SWITCH_ENABLED")
        self.assertEqual(self.store.counts()["authorizations"], 0)
        self.assertTrue(self.repository.get_pr(1015).draft)

    def test_successful_offline_attempt_consumes_once_and_mutates_only_synthetic(self):
        self.open_kill_switch()
        receipt = self.receipt()
        signature = self.sign_receipt(receipt)
        out = self.runtime.execute_once(
            authorization_receipt=receipt,
            owner_signature_attestation=signature,
            runtime_nonce_scope="attempt/1015/1",
            runtime_nonce_digest=D("c"),
            attempt_id="attempt-1015-success-1",
            behavior="SUCCESS",
            now="2026-10-08T10:00:10+00:00",
        )
        self.assertEqual(out["state"], "OFFLINE_SYNTHETIC_ATTEMPT_RECORDED")
        self.assertEqual(out["provider_identity"], PROVIDER_IDENTITY)
        self.assertEqual(
            out["adapter_result"]["primary_outcome"],
            "CONFIRMED_SUCCESS",
        )
        self.assertTrue(out["authorization_consumed"])
        self.assertTrue(out["synthetic_local_mutation_performed"])
        self.assertFalse(self.repository.get_pr(1015).draft)
        self.assertFalse(out["github_api_called"])
        self.assertFalse(out["network_called"])
        self.assertFalse(out["live_repository_mutation_performed"])
        self.assertFalse(out["automatic_retry_allowed"])
        counts = self.store.counts()
        self.assertEqual(counts["authorizations"], 1)
        self.assertEqual(counts["attempts"], 1)

        persisted = self.store.get_authorization(
            receipt["authorization_receipt_digest"]
        )
        self.assertTrue(persisted["consumed_at"])
        self.assertTrue(persisted["consumption_digest"].startswith("sha256:"))

    def test_same_authorization_cannot_execute_twice(self):
        self.open_kill_switch()
        receipt = self.receipt()
        signature = self.sign_receipt(receipt)
        self.runtime.execute_once(
            authorization_receipt=receipt,
            owner_signature_attestation=signature,
            runtime_nonce_scope="attempt/1015/first",
            runtime_nonce_digest=D("c"),
            attempt_id="attempt-1015-first",
            behavior="SUCCESS",
            now="2026-10-08T10:00:10+00:00",
        )
        with self.assertRaises(OfflineRuntimeError) as ctx:
            self.runtime.execute_once(
                authorization_receipt=receipt,
                owner_signature_attestation=signature,
                runtime_nonce_scope="attempt/1015/second",
                runtime_nonce_digest=D("d"),
                attempt_id="attempt-1015-second",
                behavior="SUCCESS",
                now="2026-10-08T10:00:11+00:00",
            )
        self.assertEqual(ctx.exception.code, "AUTHORIZATION_CONSUMPTION_CONFLICT")
        self.assertEqual(self.store.counts()["attempts"], 1)

    def test_identical_consumption_digest_replay_is_already_consumed(self):
        self.open_kill_switch()
        receipt = self.receipt()
        signature = self.sign_receipt(receipt)
        persisted = self.store.persist_authorization_once(
            receipt=receipt,
            signature_attestation=signature,
            persisted_at="2026-10-08T10:00:05+00:00",
        )
        consumption_digest = D("f")
        self.store.consume_authorization_once(
            receipt_digest=persisted["receipt_digest"],
            consumption_digest=consumption_digest,
            consumed_at="2026-10-08T10:00:10+00:00",
        )
        with self.assertRaises(OfflineRuntimeError) as ctx:
            self.store.consume_authorization_once(
                receipt_digest=persisted["receipt_digest"],
                consumption_digest=consumption_digest,
                consumed_at="2026-10-08T10:00:11+00:00",
            )
        self.assertEqual(ctx.exception.code, "AUTHORIZATION_ALREADY_CONSUMED")

    def test_terminal_failure_records_no_synthetic_effect(self):
        self.open_kill_switch()
        receipt = self.receipt()
        signature = self.sign_receipt(receipt)
        out = self.runtime.execute_once(
            authorization_receipt=receipt,
            owner_signature_attestation=signature,
            runtime_nonce_scope="attempt/1015/failure",
            runtime_nonce_digest=D("c"),
            attempt_id="attempt-1015-failure",
            behavior="TERMINAL_FAILURE",
            now="2026-10-08T10:00:10+00:00",
        )
        self.assertEqual(
            out["adapter_result"]["primary_outcome"],
            "CONFIRMED_TERMINAL_FAILURE",
        )
        self.assertFalse(out["synthetic_local_mutation_performed"])
        self.assertTrue(self.repository.get_pr(1015).draft)
        audit = self.runtime.persist_terminal_audit(
            attempt_id="attempt-1015-failure",
            persisted_at="2026-10-08T10:00:20+00:00",
        )
        self.assertEqual(
            audit["terminal_audit"]["terminal_outcome"],
            "CERTIFIED_FINAL_TERMINAL_FAILURE",
        )
        self.assertTrue(audit["terminal_closed"])
        self.assertFalse(audit["new_attempt_authorized"])

    def test_unknown_after_apply_reconciles_success_without_replay(self):
        self.open_kill_switch()
        receipt = self.receipt()
        signature = self.sign_receipt(receipt)
        out = self.runtime.execute_once(
            authorization_receipt=receipt,
            owner_signature_attestation=signature,
            runtime_nonce_scope="attempt/1015/unknown-applied",
            runtime_nonce_digest=D("c"),
            attempt_id="attempt-1015-unknown-applied",
            behavior="UNKNOWN_AFTER_APPLY",
            now="2026-10-08T10:00:10+00:00",
        )
        self.assertEqual(
            out["adapter_result"]["primary_outcome"],
            "OUTCOME_UNKNOWN",
        )
        self.assertTrue(out["synthetic_local_mutation_performed"])
        self.assertFalse(self.repository.get_pr(1015).draft)
        self.assertFalse(out["automatic_retry_allowed"])

        recon = self.runtime.reconcile_unknown(
            attempt_id="attempt-1015-unknown-applied",
            reconciled_at="2026-10-08T10:00:20+00:00",
        )
        self.assertEqual(
            recon["reconciliation"]["reconciled_outcome"],
            "RECONCILED_CONFIRMED_SUCCESS",
        )
        self.assertFalse(recon["repository_mutation_replayed"])
        self.assertFalse(recon["automatic_retry_allowed"])
        self.assertFalse(recon["new_attempt_authorized"])
        self.assertFalse(recon["github_queried"])
        self.assertFalse(recon["network_called"])

        audit = self.runtime.persist_terminal_audit(
            attempt_id="attempt-1015-unknown-applied",
            persisted_at="2026-10-08T10:00:30+00:00",
        )
        self.assertEqual(
            audit["terminal_audit"]["terminal_outcome"],
            "CERTIFIED_FINAL_SUCCESS",
        )
        self.assertTrue(audit["terminal_closed"])

    def test_unknown_no_effect_reconciles_terminal_failure_without_retry(self):
        self.open_kill_switch()
        receipt = self.receipt()
        signature = self.sign_receipt(receipt)
        out = self.runtime.execute_once(
            authorization_receipt=receipt,
            owner_signature_attestation=signature,
            runtime_nonce_scope="attempt/1015/unknown-no-effect",
            runtime_nonce_digest=D("c"),
            attempt_id="attempt-1015-unknown-no-effect",
            behavior="UNKNOWN_NO_EFFECT",
            now="2026-10-08T10:00:10+00:00",
        )
        self.assertEqual(
            out["adapter_result"]["primary_outcome"],
            "OUTCOME_UNKNOWN",
        )
        self.assertFalse(out["synthetic_local_mutation_performed"])
        self.assertTrue(self.repository.get_pr(1015).draft)

        recon = self.runtime.reconcile_unknown(
            attempt_id="attempt-1015-unknown-no-effect",
            reconciled_at="2026-10-08T10:00:20+00:00",
        )
        self.assertEqual(
            recon["reconciliation"]["reconciled_outcome"],
            "RECONCILED_CONFIRMED_TERMINAL_FAILURE",
        )
        self.assertFalse(recon["automatic_retry_allowed"])
        self.assertFalse(recon["new_attempt_authorized"])

        audit = self.runtime.persist_terminal_audit(
            attempt_id="attempt-1015-unknown-no-effect",
            persisted_at="2026-10-08T10:00:30+00:00",
        )
        self.assertEqual(
            audit["terminal_audit"]["terminal_outcome"],
            "CERTIFIED_FINAL_TERMINAL_FAILURE",
        )
        self.assertTrue(audit["terminal_closed"])

    def test_unknown_before_reconciliation_persists_open_ambiguous_audit(self):
        self.open_kill_switch()
        receipt = self.receipt()
        signature = self.sign_receipt(receipt)
        self.runtime.execute_once(
            authorization_receipt=receipt,
            owner_signature_attestation=signature,
            runtime_nonce_scope="attempt/1015/open-unknown",
            runtime_nonce_digest=D("c"),
            attempt_id="attempt-1015-open-unknown",
            behavior="UNKNOWN_NO_EFFECT",
            now="2026-10-08T10:00:10+00:00",
        )
        audit = self.runtime.persist_terminal_audit(
            attempt_id="attempt-1015-open-unknown",
            persisted_at="2026-10-08T10:00:20+00:00",
        )
        self.assertEqual(
            audit["terminal_audit"]["terminal_outcome"],
            "CERTIFIED_OPEN_AMBIGUOUS",
        )
        self.assertFalse(audit["terminal_closed"])
        self.assertTrue(audit["reconciliation_required"])
        self.assertFalse(audit["automatic_retry_allowed"])
        self.assertFalse(audit["new_attempt_authorized"])

    def test_runtime_store_survives_reopen_with_consumption_and_audit(self):
        self.open_kill_switch()
        receipt = self.receipt()
        signature = self.sign_receipt(receipt)
        self.runtime.execute_once(
            authorization_receipt=receipt,
            owner_signature_attestation=signature,
            runtime_nonce_scope="attempt/1015/reopen",
            runtime_nonce_digest=D("c"),
            attempt_id="attempt-1015-reopen",
            behavior="SUCCESS",
            now="2026-10-08T10:00:10+00:00",
        )
        self.runtime.persist_terminal_audit(
            attempt_id="attempt-1015-reopen",
            persisted_at="2026-10-08T10:00:20+00:00",
        )

        reopened = LocalRepositoryMutationStore(self.db)
        counts = reopened.counts()
        self.assertEqual(counts["authorizations"], 1)
        self.assertEqual(counts["attempts"], 1)
        self.assertEqual(counts["terminal_audits"], 1)
        stored = reopened.get_authorization(
            receipt["authorization_receipt_digest"]
        )
        self.assertTrue(stored["consumed_at"])

    def test_synthetic_full_ready_retarget_merge_sequence(self):
        self.open_kill_switch()
        pr = self.repository.get_pr(1016)

        ready_receipt = self.receipt(
            receipt_id="receipt-1016-ready",
            pr_number=1016,
            mutation="PR_DRAFT_TO_READY",
            base_branch="impl/parent-v1",
        )
        self.runtime.execute_once(
            authorization_receipt=ready_receipt,
            owner_signature_attestation=self.sign_receipt(ready_receipt),
            runtime_nonce_scope="attempt/1016/ready",
            runtime_nonce_digest=D("c"),
            attempt_id="attempt-1016-ready",
            behavior="SUCCESS",
            now="2026-10-08T10:00:10+00:00",
        )
        self.assertFalse(pr.draft)
        self.assertEqual(pr.base_branch, "impl/parent-v1")

        retarget_receipt = self.receipt(
            receipt_id="receipt-1016-retarget",
            pr_number=1016,
            mutation="PR_RETARGET_TO_MAIN",
            base_branch="impl/parent-v1",
        )
        self.runtime.execute_once(
            authorization_receipt=retarget_receipt,
            owner_signature_attestation=self.sign_receipt(retarget_receipt),
            runtime_nonce_scope="attempt/1016/retarget",
            runtime_nonce_digest=D("d"),
            attempt_id="attempt-1016-retarget",
            behavior="SUCCESS",
            now="2026-10-08T10:00:20+00:00",
        )
        self.assertEqual(pr.base_branch, "main")
        self.assertFalse(pr.draft)

        old_main = self.repository.main_sha
        merge_receipt = self.receipt(
            receipt_id="receipt-1016-merge",
            pr_number=1016,
            mutation="SQUASH_MERGE_TO_MAIN",
            main_sha=old_main,
            main_tree_sha=self.repository.main_tree_sha,
            base_branch="main",
        )
        merged = self.runtime.execute_once(
            authorization_receipt=merge_receipt,
            owner_signature_attestation=self.sign_receipt(merge_receipt),
            runtime_nonce_scope="attempt/1016/merge",
            runtime_nonce_digest=D("e"),
            attempt_id="attempt-1016-merge",
            behavior="SUCCESS",
            now="2026-10-08T10:00:30+00:00",
        )
        self.assertEqual(
            merged["adapter_result"]["primary_outcome"],
            "CONFIRMED_SUCCESS",
        )
        self.assertTrue(pr.merged)
        self.assertFalse(pr.open)
        self.assertTrue(pr.merge_commit_sha)
        self.assertNotEqual(self.repository.main_sha, old_main)
        self.assertEqual(self.repository.main_sha, pr.merge_commit_sha)
        self.assertFalse(merged["github_api_called"])
        self.assertFalse(merged["network_called"])
        self.assertFalse(merged["live_repository_mutation_performed"])

    def test_kill_switch_blocks_reconciliation_too(self):
        self.open_kill_switch()
        receipt = self.receipt()
        self.runtime.execute_once(
            authorization_receipt=receipt,
            owner_signature_attestation=self.sign_receipt(receipt),
            runtime_nonce_scope="attempt/1015/kill-recon",
            runtime_nonce_digest=D("c"),
            attempt_id="attempt-1015-kill-recon",
            behavior="UNKNOWN_NO_EFFECT",
            now="2026-10-08T10:00:10+00:00",
        )
        self.store.set_kill_switch(
            enabled=True,
            reason="EMERGENCY_LOCAL_STOP",
            updated_at="2026-10-08T10:00:15+00:00",
        )
        with self.assertRaises(OfflineRuntimeError) as ctx:
            self.runtime.reconcile_unknown(
                attempt_id="attempt-1015-kill-recon",
                reconciled_at="2026-10-08T10:00:20+00:00",
            )
        self.assertEqual(ctx.exception.code, "KILL_SWITCH_ENABLED")

    def test_policy_separates_offline_runtime_from_live_github(self):
        policy = offline_runtime_policy()
        self.assertEqual(policy["provider_identity"], PROVIDER_IDENTITY)
        self.assertTrue(policy["sqlite_local_store_implemented"])
        self.assertTrue(policy["durable_nonce_replay_registry_implemented"])
        self.assertTrue(policy["durable_authorization_store_implemented"])
        self.assertTrue(policy["atomic_authorization_consumption_implemented"])
        self.assertTrue(
            policy["external_ed25519_public_key_verification_implemented"]
        )
        self.assertFalse(policy["real_owner_private_signer_implemented"])
        self.assertTrue(policy["kill_switch_implemented"])
        self.assertTrue(policy["synthetic_provider_implemented"])
        self.assertTrue(
            policy["synthetic_postcondition_readback_implemented"]
        )
        self.assertTrue(policy["synthetic_unknown_reconciliation_implemented"])
        self.assertTrue(policy["local_terminal_audit_store_implemented"])
        self.assertFalse(policy["live_github_state_reader_implemented"])
        self.assertFalse(policy["live_github_adapter_implemented"])
        self.assertFalse(policy["runtime_credential_broker_implemented"])
        self.assertFalse(policy["live_github_transport_executor_implemented"])
        self.assertFalse(
            policy["live_authoritative_postcondition_reader_implemented"]
        )
        self.assertFalse(
            policy["live_reconciliation_evidence_collector_implemented"]
        )
        self.assertFalse(policy["github_endpoint_material_included"])
        self.assertFalse(policy["credential_material_included"])
        self.assertFalse(policy["real_github_credentials_loaded"])
        self.assertFalse(policy["real_github_network_path_enabled"])
        self.assertFalse(policy["github_api_called"])
        self.assertFalse(policy["network_called"])
        self.assertFalse(policy["live_repository_mutation_authorized"])
        self.assertFalse(policy["live_repository_mutation_performed"])
        self.assertFalse(policy["production_repository_mutation_performed"])
        self.assertFalse(policy["automatic_retry_allowed"])
        self.assertFalse(policy["deploy_executed"])
        self.assertFalse(policy["worker_activated"])
        self.assertFalse(policy["provider_activated"])
        self.assertFalse(policy["production_persistence_activated"])


if __name__ == "__main__":
    unittest.main()
