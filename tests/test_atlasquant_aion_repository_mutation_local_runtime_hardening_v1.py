import base64
import hashlib
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from atlasquant_aion_repository_mutation_authorization_receipt_v1 import (
    MECHANISM,
    PURPOSE,
    RECEIPT_SCHEMA,
)
from atlasquant_aion_repository_mutation_offline_runtime_v1 import (
    SIGNATURE_CONTEXT,
    OfflineRuntimeError,
    SyntheticPullRequest,
    SyntheticRepositoryMutationAdapter,
    SyntheticRepositoryState,
    verify_external_owner_ed25519_signature,
)
from atlasquant_aion_repository_mutation_local_runtime_hardening_v1 import (
    KILL_SWITCH_CONTEXT,
    HardenedLocalRepositoryMutationStore,
    HardenedOfflineRepositoryMutationRuntime,
    build_kill_switch_control_challenge,
    build_windows_owner_acl_attestation,
    local_runtime_hardening_policy,
    resolve_windows_runtime_layout,
    verify_and_apply_signed_kill_switch_change,
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
    return "sha256:" + hashlib.sha256(
        canonical(value).encode("utf-8")
    ).hexdigest()


class AionRepositoryMutationLocalRuntimeHardeningV1Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "runtime.sqlite3"
        self.store = HardenedLocalRepositoryMutationStore(self.db)

        self.private_key = Ed25519PrivateKey.generate()
        raw_public = self.private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.public_b64 = base64.b64encode(raw_public).decode("ascii")
        self.fingerprint = "sha256:" + hashlib.sha256(raw_public).hexdigest()

        self.repository = SyntheticRepositoryState(
            repository_id="repo://atlasquant/hardened-offline",
            main_sha="a" * 40,
            main_tree_sha="b" * 40,
            pull_requests={
                1015: SyntheticPullRequest(
                    number=1015,
                    head_sha="c" * 40,
                    base_branch="main",
                    draft=True,
                    open=True,
                )
            },
        )
        self.adapter = SyntheticRepositoryMutationAdapter(self.repository)
        self.runtime = HardenedOfflineRepositoryMutationRuntime(
            store=self.store,
            adapter=self.adapter,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def receipt(
        self,
        *,
        receipt_id="hardening-receipt-1",
        owner_key_fingerprint=None,
        owner_binding_digest=D("1"),
        expires_at="2026-10-08T10:10:00+00:00",
    ):
        material = {
            "receipt_id": receipt_id,
            "purpose": PURPOSE,
            "mechanism": MECHANISM,
            "pr_number": 1015,
            "requested_mutation": "PR_DRAFT_TO_READY",
            "owner_subject": "owner://mikael",
            "owner_binding_digest": owner_binding_digest,
            "owner_key_fingerprint": (
                owner_key_fingerprint or self.fingerprint
            ),
            "challenge_digest": D("2"),
            "signature_attestation_digest": D("3"),
            "decision_digest": D("4"),
            "live_rebuilt_preflight_digest": D("5"),
            "main_sha": self.repository.main_sha,
            "main_tree_sha": self.repository.main_tree_sha,
            "head_branch": "synthetic/pr-1015",
            "head_sha": self.repository.get_pr(1015).head_sha,
            "base_branch": self.repository.get_pr(1015).base_branch,
            "file_delta_digest": D("6"),
            "workflow_snapshot_digest": D("7"),
            "readiness_digest": D("8"),
            "rollback_plan_digest": D("9"),
            "authorization_nonce_digest": D("a"),
            "persistent_authorization_nonce_replay_guard_verified": True,
            "authorization_nonce_single_use_claimed": True,
            "issued_at": "2026-10-08T10:00:00+00:00",
            "expires_at": expires_at,
            "verified_at": "2026-10-08T10:00:05+00:00",
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

    def enroll_owner(self):
        return self.store.enroll_owner_public_key_once(
            owner_subject="owner://mikael",
            owner_binding_digest=D("1"),
            device_binding_digest=D("b"),
            public_key_b64=self.public_b64,
            enrollment_nonce_digest=D("c"),
            enrolled_at="2026-10-08T09:55:00+00:00",
            physical_owner_presence_verified=True,
            owner_only_acl_verified=True,
        )

    def signed_kill_switch_change(
        self,
        *,
        action_id,
        desired_enabled,
        nonce_digest,
        issued_at,
        expires_at,
        now,
        reason,
    ):
        challenge = build_kill_switch_control_challenge(
            self.store,
            action_id=action_id,
            desired_enabled=desired_enabled,
            reason=reason,
            nonce_digest=nonce_digest,
            issued_at=issued_at,
            expires_at=expires_at,
        )
        message = base64.b64decode(
            challenge["signature_message_b64"],
            validate=True,
        )
        self.assertTrue(message.startswith(KILL_SWITCH_CONTEXT))
        signature = self.private_key.sign(message)
        return challenge, base64.b64encode(signature).decode("ascii"), now

    def open_kill_switch_signed(self):
        challenge, signature, now = self.signed_kill_switch_change(
            action_id="kill-switch-open-1",
            desired_enabled=False,
            nonce_digest=D("d"),
            issued_at="2026-10-08T09:56:00+00:00",
            expires_at="2026-10-08T09:58:00+00:00",
            now="2026-10-08T09:56:10+00:00",
            reason="OFFLINE_HARDENED_TEST",
        )
        return verify_and_apply_signed_kill_switch_change(
            self.store,
            challenge,
            signature_b64=signature,
            now=now,
        )

    def test_windows_layout_is_per_user_and_network_share_is_blocked(self):
        layout = resolve_windows_runtime_layout(
            local_app_data=r"C:\Users\Mikael\AppData\Local",
            owner_subject="owner://mikael",
        )
        self.assertEqual(layout["state"], "WINDOWS_RUNTIME_LAYOUT_READY")
        self.assertTrue(layout["per_user_location"])
        self.assertFalse(layout["program_data_used"])
        self.assertFalse(layout["system_account_required"])
        self.assertFalse(layout["network_share_allowed"])
        self.assertFalse(layout["filesystem_modified"])
        self.assertFalse(layout["windows_service_installed"])
        self.assertTrue(
            layout["db_path"].endswith(
                r"AtlasQuant\AION\RepositoryMutationRuntime\repository_mutation_runtime.sqlite3"
            )
        )

        blocked = resolve_windows_runtime_layout(
            local_app_data=r"\\server\share\runtime",
            owner_subject="owner://mikael",
        )
        self.assertEqual(blocked["state"], "BLOCKED")
        self.assertIn("UNC_RUNTIME_ROOT_FORBIDDEN", blocked["blockers"])

    def test_windows_acl_attestation_requires_owner_only_boundary(self):
        layout = resolve_windows_runtime_layout(
            local_app_data=r"C:\Users\Mikael\AppData\Local",
            owner_subject="owner://mikael",
        )
        ready = build_windows_owner_acl_attestation(
            layout,
            owner_sid_digest=D("e"),
            acl_evidence_digest=D("f"),
            current_user_owner_match=True,
            owner_full_control_verified=True,
            inheritance_disabled_verified=True,
            broad_write_aces_absent=True,
            service_account_is_current_user=True,
        )
        self.assertEqual(ready["state"], "WINDOWS_OWNER_ACL_ATTESTED")
        self.assertFalse(ready["acl_modified_by_this_module"])
        self.assertFalse(ready["filesystem_modified"])

        blocked = build_windows_owner_acl_attestation(
            layout,
            owner_sid_digest=D("e"),
            acl_evidence_digest=D("f"),
            current_user_owner_match=True,
            owner_full_control_verified=True,
            inheritance_disabled_verified=False,
            broad_write_aces_absent=False,
            service_account_is_current_user=True,
        )
        self.assertEqual(blocked["state"], "BLOCKED")
        self.assertIn(
            "ACL_INHERITANCE_MUST_BE_DISABLED",
            blocked["blockers"],
        )
        self.assertIn("BROAD_WRITE_ACES_MUST_BE_ABSENT", blocked["blockers"])

    def test_owner_public_key_enrollment_is_single_active_and_persistent(self):
        enrolled = self.enroll_owner()
        self.assertEqual(enrolled["state"], "OWNER_PUBLIC_KEY_ENROLLED")
        self.assertEqual(enrolled["public_key_fingerprint"], self.fingerprint)
        self.assertTrue(enrolled["enrollment_digest"].startswith("sha256:"))
        self.assertFalse(enrolled["private_key_material_present"])
        self.assertFalse(enrolled["replay"])

        replay = self.enroll_owner()
        self.assertTrue(replay["replay"])
        self.assertEqual(replay["public_key_fingerprint"], self.fingerprint)

        reopened = HardenedLocalRepositoryMutationStore(self.db)
        key = reopened.get_active_owner_key()
        self.assertEqual(key["public_key_fingerprint"], self.fingerprint)
        self.assertFalse(key["private_key_material_present"])

        other = Ed25519PrivateKey.generate()
        raw = other.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        with self.assertRaises(OfflineRuntimeError) as ctx:
            reopened.enroll_owner_public_key_once(
                owner_subject="owner://mikael",
                owner_binding_digest=D("1"),
                device_binding_digest=D("b"),
                public_key_b64=base64.b64encode(raw).decode("ascii"),
                enrollment_nonce_digest=D("0"),
                enrolled_at="2026-10-08T09:56:00+00:00",
                physical_owner_presence_verified=True,
                owner_only_acl_verified=True,
            )
        self.assertEqual(ctx.exception.code, "OWNER_KEY_ALREADY_ENROLLED_CONFLICT")

    def test_enrollment_requires_physical_presence_and_acl_attestation(self):
        with self.assertRaises(OfflineRuntimeError) as ctx:
            self.store.enroll_owner_public_key_once(
                owner_subject="owner://mikael",
                owner_binding_digest=D("1"),
                device_binding_digest=D("b"),
                public_key_b64=self.public_b64,
                enrollment_nonce_digest=D("c"),
                enrolled_at="2026-10-08T09:55:00+00:00",
                physical_owner_presence_verified=False,
                owner_only_acl_verified=True,
            )
        self.assertEqual(ctx.exception.code, "PHYSICAL_OWNER_PRESENCE_REQUIRED")

        with self.assertRaises(OfflineRuntimeError) as ctx2:
            self.store.enroll_owner_public_key_once(
                owner_subject="owner://mikael",
                owner_binding_digest=D("1"),
                device_binding_digest=D("b"),
                public_key_b64=self.public_b64,
                enrollment_nonce_digest=D("c"),
                enrolled_at="2026-10-08T09:55:00+00:00",
                physical_owner_presence_verified=True,
                owner_only_acl_verified=False,
            )
        self.assertEqual(ctx2.exception.code, "OWNER_ONLY_ACL_VERIFICATION_REQUIRED")

    def test_signed_kill_switch_change_is_atomic_and_replay_protected(self):
        self.enroll_owner()
        out = self.open_kill_switch_signed()
        self.assertEqual(out["state"], "SIGNED_KILL_SWITCH_CHANGE_APPLIED")
        self.assertFalse(out["kill_switch_status"]["enabled"])
        self.assertTrue(out["owner_signature_verified"])
        self.assertTrue(out["nonce_consumed"])
        self.assertTrue(out["state_compare_and_set_verified"])
        self.assertFalse(out["private_key_loaded"])
        self.assertFalse(out["github_api_called"])
        self.assertFalse(out["network_called"])

        challenge, signature, now = self.signed_kill_switch_change(
            action_id="kill-switch-close-reused-nonce",
            desired_enabled=True,
            nonce_digest=D("d"),
            issued_at="2026-10-08T09:57:00+00:00",
            expires_at="2026-10-08T09:59:00+00:00",
            now="2026-10-08T09:57:10+00:00",
            reason="REUSE_SHOULD_BLOCK",
        )
        with self.assertRaises(OfflineRuntimeError) as ctx:
            verify_and_apply_signed_kill_switch_change(
                self.store,
                challenge,
                signature_b64=signature,
                now=now,
            )
        self.assertEqual(ctx.exception.code, "KILL_SWITCH_NONCE_REPLAY_REJECTED")

    def test_kill_switch_challenge_is_bound_to_previous_state(self):
        self.enroll_owner()
        challenge, signature, now = self.signed_kill_switch_change(
            action_id="kill-switch-state-bound-1",
            desired_enabled=False,
            nonce_digest=D("e"),
            issued_at="2026-10-08T09:56:00+00:00",
            expires_at="2026-10-08T09:58:00+00:00",
            now="2026-10-08T09:56:10+00:00",
            reason="STATE_BOUND_TEST",
        )
        self.store.set_kill_switch(
            enabled=True,
            reason="TEST_HARNESS_CHANGED_STATE",
            updated_at="2026-10-08T09:56:05+00:00",
        )
        with self.assertRaises(OfflineRuntimeError) as ctx:
            verify_and_apply_signed_kill_switch_change(
                self.store,
                challenge,
                signature_b64=signature,
                now=now,
            )
        self.assertEqual(
            ctx.exception.code,
            "KILL_SWITCH_STATE_CHANGED_AFTER_CHALLENGE",
        )

    def test_hardened_runtime_binds_receipt_signature_and_enrollment(self):
        self.enroll_owner()
        self.open_kill_switch_signed()

        receipt = self.receipt()
        signature = self.sign_receipt(receipt)
        out = self.runtime.execute_once(
            authorization_receipt=receipt,
            owner_signature_attestation=signature,
            runtime_nonce_scope="hardened-attempt/1015/1",
            runtime_nonce_digest=D("e"),
            attempt_id="hardened-attempt-1015-1",
            behavior="SUCCESS",
            now="2026-10-08T10:00:10+00:00",
        )
        self.assertTrue(out["hardened_owner_key_binding_verified"])
        self.assertEqual(
            out["enrolled_owner_key_fingerprint"],
            self.fingerprint,
        )
        self.assertFalse(out["github_api_called"])
        self.assertFalse(out["network_called"])
        self.assertFalse(out["live_repository_mutation_performed"])

    def test_hardened_runtime_rejects_receipt_bound_to_other_key(self):
        self.enroll_owner()
        self.open_kill_switch_signed()
        receipt = self.receipt(owner_key_fingerprint=D("0"))
        signature = self.sign_receipt(receipt)
        with self.assertRaises(OfflineRuntimeError) as ctx:
            self.runtime.execute_once(
                authorization_receipt=receipt,
                owner_signature_attestation=signature,
                runtime_nonce_scope="hardened-attempt/1015/wrong-key",
                runtime_nonce_digest=D("e"),
                attempt_id="hardened-attempt-1015-wrong-key",
                behavior="SUCCESS",
                now="2026-10-08T10:00:10+00:00",
            )
        self.assertEqual(ctx.exception.code, "RECEIPT_OWNER_KEY_NOT_ENROLLED_KEY")
        self.assertTrue(self.repository.get_pr(1015).draft)

    def test_sqlite_integrity_report_is_read_only_and_survives_reopen(self):
        self.enroll_owner()
        first = self.store.integrity_report()
        self.assertEqual(first["state"], "LOCAL_RUNTIME_INTEGRITY_OK")
        self.assertTrue(first["integrity_ok"])
        self.assertEqual(first["journal_mode"], "wal")
        self.assertGreaterEqual(first["synchronous_level"], 2)
        self.assertTrue(first["owner_key_enrolled"])
        self.assertFalse(first["database_repaired"])
        self.assertFalse(first["data_mutated_by_report"])

        reopened = HardenedLocalRepositoryMutationStore(self.db)
        second = reopened.integrity_report()
        self.assertTrue(second["integrity_ok"])
        self.assertEqual(
            second["owner_key_fingerprint"],
            self.fingerprint,
        )

    def _persist_authorization_for_recovery(
        self,
        *,
        receipt_id,
        consumption_digest=None,
        expires_at="2026-10-08T10:10:00+00:00",
    ):
        receipt = self.receipt(
            receipt_id=receipt_id,
            expires_at=expires_at,
        )
        sig = self.sign_receipt(receipt)
        self.store.persist_authorization_once(
            receipt=receipt,
            signature_attestation=sig,
            persisted_at="2026-10-08T10:00:05+00:00",
        )
        if consumption_digest:
            self.store.consume_authorization_once(
                receipt_digest=receipt["authorization_receipt_digest"],
                consumption_digest=consumption_digest,
                consumed_at="2026-10-08T10:00:10+00:00",
            )
        return receipt

    def test_recovery_scan_never_releases_or_retries_ambiguous_state(self):
        consumed_only = self._persist_authorization_for_recovery(
            receipt_id="recovery-consumed-no-attempt",
            consumption_digest=D("2"),
        )
        unknown = self._persist_authorization_for_recovery(
            receipt_id="recovery-unknown",
            consumption_digest=D("3"),
        )
        self.store.record_attempt_once(
            attempt_id="recovery-attempt-unknown",
            receipt_digest=unknown["authorization_receipt_digest"],
            pr_number=1015,
            requested_mutation="PR_DRAFT_TO_READY",
            behavior="UNKNOWN_NO_EFFECT",
            before_state_digest=D("4"),
            after_state_digest=D("4"),
            primary_outcome="OUTCOME_UNKNOWN",
            evidence_digest=D("5"),
            attempted_at="2026-10-08T10:00:11+00:00",
        )
        success = self._persist_authorization_for_recovery(
            receipt_id="recovery-success",
            consumption_digest=D("6"),
        )
        self.store.record_attempt_once(
            attempt_id="recovery-attempt-success",
            receipt_digest=success["authorization_receipt_digest"],
            pr_number=1015,
            requested_mutation="PR_DRAFT_TO_READY",
            behavior="SUCCESS",
            before_state_digest=D("7"),
            after_state_digest=D("8"),
            primary_outcome="CONFIRMED_SUCCESS",
            evidence_digest=D("9"),
            attempted_at="2026-10-08T10:00:12+00:00",
        )
        self.store.persist_terminal_audit_once(
            attempt_id="recovery-attempt-success",
            terminal_outcome="CERTIFIED_FINAL_SUCCESS",
            manifest_digest=D("a"),
            certificate_digest=D("b"),
            persisted_at="2026-10-08T10:00:20+00:00",
        )
        self._persist_authorization_for_recovery(
            receipt_id="recovery-expired-unconsumed",
            expires_at="2026-10-08T10:01:00+00:00",
        )

        before = self.store.counts()
        scan = self.store.recovery_scan(now="2026-10-08T10:05:00+00:00")
        after = self.store.counts()
        states = {row["recovery_state"] for row in scan["findings"]}

        self.assertIn("CONSUMED_WITHOUT_ATTEMPT_EVIDENCE", states)
        self.assertIn("OUTCOME_UNKNOWN_RECONCILIATION_REQUIRED", states)
        self.assertIn("CLOSED", states)
        self.assertIn("UNCONSUMED_AUTHORIZATION_EXPIRED", states)
        self.assertTrue(scan["manual_attention_required"])
        self.assertFalse(scan["automatic_retry_allowed"])
        self.assertFalse(scan["consumed_authorization_released"])
        self.assertFalse(scan["repository_mutation_replayed"])
        self.assertFalse(scan["database_mutated_by_scan"])
        self.assertEqual(before, after)

        consumed_row = next(
            row for row in scan["findings"]
            if row["receipt_digest"]
            == consumed_only["authorization_receipt_digest"]
        )
        self.assertFalse(consumed_row["automatic_retry_allowed"])
        self.assertFalse(consumed_row["authorization_release_allowed"])
        self.assertFalse(consumed_row["repository_mutation_replay_allowed"])

    def test_concurrent_consumption_allows_exactly_one_winner(self):
        receipt = self.receipt(receipt_id="concurrent-consume-1")
        sig = self.sign_receipt(receipt)
        self.store.persist_authorization_once(
            receipt=receipt,
            signature_attestation=sig,
            persisted_at="2026-10-08T10:00:05+00:00",
        )

        def consume(index):
            try:
                self.store.consume_authorization_once(
                    receipt_digest=receipt["authorization_receipt_digest"],
                    consumption_digest=digest({"consumer": index}),
                    consumed_at="2026-10-08T10:00:10+00:00",
                )
                return "SUCCESS"
            except OfflineRuntimeError as exc:
                return exc.code

        with ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(consume, range(24)))

        self.assertEqual(results.count("SUCCESS"), 1)
        blocked = [
            value for value in results if value != "SUCCESS"
        ]
        self.assertEqual(len(blocked), 23)
        self.assertTrue(
            all(
                value in (
                    "AUTHORIZATION_ALREADY_CONSUMED",
                    "AUTHORIZATION_CONSUMPTION_CONFLICT",
                    "AUTHORIZATION_CAS_FAILED",
                )
                for value in blocked
            )
        )
        persisted = self.store.get_authorization(
            receipt["authorization_receipt_digest"]
        )
        self.assertTrue(persisted["consumed_at"])
        self.assertTrue(persisted["consumption_digest"])

    def test_policy_keeps_windows_and_live_github_fail_closed(self):
        policy = local_runtime_hardening_policy()
        self.assertEqual(policy["windows_service_mode"], "CURRENT_USER_ONLY")
        self.assertTrue(policy["windows_runtime_is_per_user"])
        self.assertTrue(policy["program_data_runtime_forbidden"])
        self.assertTrue(policy["unc_runtime_root_forbidden"])
        self.assertTrue(policy["owner_only_acl_required"])
        self.assertTrue(policy["acl_inheritance_disabled_required"])
        self.assertTrue(policy["broad_write_aces_absent_required"])
        self.assertFalse(policy["real_windows_acl_modified_by_this_module"])
        self.assertFalse(policy["windows_service_installed"])
        self.assertTrue(policy["single_sqlite_runtime_truth"])
        self.assertTrue(policy["second_runtime_database_forbidden"])
        self.assertTrue(policy["owner_public_key_enrollment_implemented"])
        self.assertTrue(
            policy["hardened_execution_requires_enrolled_key_binding"]
        )
        self.assertTrue(
            policy["receipt_signature_enrollment_fingerprint_must_match"]
        )
        self.assertFalse(policy["owner_key_rotation_implemented"])
        self.assertFalse(policy["owner_private_key_generated"])
        self.assertFalse(policy["owner_private_key_stored"])
        self.assertTrue(policy["signed_kill_switch_control_implemented"])
        self.assertTrue(policy["kill_switch_change_requires_owner_signature"])
        self.assertTrue(policy["kill_switch_change_requires_single_use_nonce"])
        self.assertTrue(policy["kill_switch_change_binds_previous_state"])
        self.assertTrue(policy["kill_switch_change_is_atomic_with_audit"])
        self.assertTrue(policy["restart_recovery_scan_implemented"])
        self.assertTrue(policy["restart_recovery_scan_is_read_only"])
        self.assertTrue(policy["consumed_without_attempt_never_auto_released"])
        self.assertTrue(policy["outcome_unknown_never_auto_retried"])
        self.assertFalse(policy["automatic_retry_allowed"])
        self.assertFalse(policy["repository_mutation_replay_allowed"])
        self.assertFalse(policy["live_github_state_reader_implemented"])
        self.assertFalse(policy["live_github_adapter_implemented"])
        self.assertFalse(policy["runtime_credential_broker_implemented"])
        self.assertFalse(policy["real_github_credentials_loaded"])
        self.assertFalse(policy["real_github_network_path_enabled"])
        self.assertFalse(policy["github_api_called"])
        self.assertFalse(policy["network_called"])
        self.assertFalse(policy["live_repository_mutation_authorized"])
        self.assertFalse(policy["live_repository_mutation_performed"])
        self.assertFalse(policy["production_repository_mutation_performed"])
        self.assertFalse(policy["deploy_executed"])
        self.assertFalse(policy["worker_activated"])
        self.assertFalse(policy["provider_activated"])
        self.assertFalse(policy["production_persistence_activated"])


if __name__ == "__main__":
    unittest.main()
