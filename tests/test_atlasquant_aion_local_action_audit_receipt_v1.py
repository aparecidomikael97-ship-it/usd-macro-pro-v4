import copy
import unittest

from atlasquant_aion_local_action_audit_receipt_v1 import (
    ADAPTER_OBSERVATION_SCHEMA,
    build_local_action_audit_receipt,
    dispatch_readiness_digest,
    local_action_audit_policy,
    local_action_bindings,
    local_action_set_digest,
    verify_local_action_audit_receipt,
)
from atlasquant_aion_owner_experience_v1 import command_plan
from atlasquant_aion_secure_local_agent_v1 import (
    build_local_action_request,
    evaluate_dispatch_readiness,
)


BINDING_DIGEST = "sha256:" + ("a" * 64)
ADAPTER_BINARY_DIGEST = "sha256:" + ("b" * 64)
EVIDENCE_BUNDLE_DIGEST = "sha256:" + ("c" * 64)
ISSUED = "2026-10-08T10:00:00+00:00"
EXPIRES = "2026-10-08T10:00:30+00:00"
STARTED = "2026-10-08T10:00:10+00:00"
COMPLETED = "2026-10-08T10:00:12+00:00"
OBSERVED = "2026-10-08T10:00:13+00:00"


def digest_char(char):
    return "sha256:" + (char * 64)


class AionLocalActionAuditReceiptV1Tests(unittest.TestCase):
    def request_and_dispatch(self, message="AION, abre o ChatGPT"):
        plan = command_plan(message, device="desktop", owner_bound=True)
        request = build_local_action_request(
            plan,
            command_text=message,
            owner_subject="mikael",
            owner_binding_digest=BINDING_DIGEST,
            command_id="cmd-audit-1",
            command_nonce="nonce-audit-1",
            device_id="windows-owner-desktop-1",
            platform="WINDOWS",
            issued_at=ISSUED,
            expires_at=EXPIRES,
        )
        self.assertEqual(request["state"], "REQUEST_READY")

        host = {
            "verified": True,
            "source": "TRUSTED_OWNER_DESKTOP_HOST",
            "mechanism": "WINDOWS_HELLO",
            "fresh_owner_command": True,
            "generic_chat_acknowledgement": False,
            "owner_subject": request["owner_subject"],
            "owner_binding_digest": request["owner_binding_digest"],
            "request_digest": request["request_digest"],
            "command_nonce_digest": request["command_nonce_digest"],
            "cryptographic_verification_performed": True,
        }
        replay = {
            "verified": True,
            "request_digest": request["request_digest"],
            "command_nonce_digest": request["command_nonce_digest"],
            "fresh": True,
            "single_use_claimed": True,
            "durable_replay_rejection": True,
        }
        dispatch = evaluate_dispatch_readiness(
            request,
            trusted_host_authorization=host,
            replay_guard_attestation=replay,
            now=STARTED,
        )
        self.assertTrue(dispatch["dispatch_ready"])
        return request, dispatch

    def action_result(
        self,
        binding,
        *,
        outcome="CONFIRMED_SUCCESS",
        evidence_kind=None,
        evidence_char="d",
        ambiguity="",
    ):
        if evidence_kind is None:
            if outcome == "CONFIRMED_SUCCESS":
                evidence_kind = (
                    "MEDIA_SESSION_CONFIRMATION"
                    if binding["action"] == "MEDIA_PLAYBACK"
                    else "OS_APP_ACTIVATION_CONFIRMATION"
                )
            elif outcome == "CONFIRMED_TERMINAL_FAILURE":
                evidence_kind = (
                    "MEDIA_SESSION_TERMINAL_ERROR"
                    if binding["action"] == "MEDIA_PLAYBACK"
                    else "OS_APP_LAUNCH_TERMINAL_ERROR"
                )
            else:
                evidence_kind = "AMBIGUOUS_OS_OBSERVATION"

        return {
            "action": binding["action"],
            "logical_app_id": binding["logical_app_id"],
            "parameters_digest": binding["parameters_digest"],
            "outcome_state": outcome,
            "evidence_kind": evidence_kind,
            "evidence_digest": digest_char(evidence_char),
            "postcondition_verified": outcome == "CONFIRMED_SUCCESS",
            "terminal_failure_verified": outcome == "CONFIRMED_TERMINAL_FAILURE",
            "ambiguity_trigger": ambiguity,
        }

    def observation(
        self,
        request,
        dispatch,
        action_results,
        *,
        declared_outcome="",
        completed_at=COMPLETED,
        **changes,
    ):
        value = {
            "schema": ADAPTER_OBSERVATION_SCHEMA,
            "verified": True,
            "source": "SIGNED_LOCAL_ADAPTER",
            "adapter_signature_verified": True,
            "adapter_instance_id": "owner-windows-agent-1",
            "attempt_id": "attempt-1",
            "adapter_binary_digest": ADAPTER_BINARY_DIGEST,
            "evidence_bundle_digest": EVIDENCE_BUNDLE_DIGEST,
            "request_digest": request["request_digest"],
            "dispatch_readiness_digest": dispatch_readiness_digest(dispatch),
            "action_set_digest": local_action_set_digest(request),
            "attempt_started_at": STARTED,
            "attempt_completed_at": completed_at,
            "declared_outcome_state": declared_outcome,
            "action_results": action_results,
        }
        value.update(changes)
        return value

    def test_confirmed_success_requires_positive_postcondition_evidence(self):
        request, dispatch = self.request_and_dispatch()
        bindings = local_action_bindings(request)
        observation = self.observation(
            request,
            dispatch,
            [self.action_result(bindings[0])],
            declared_outcome="CONFIRMED_SUCCESS",
        )
        receipt = build_local_action_audit_receipt(
            request,
            dispatch,
            observation,
            observed_at=OBSERVED,
        )
        self.assertEqual(receipt["state"], "RECEIPT_READY")
        self.assertEqual(receipt["outcome_state"], "CONFIRMED_SUCCESS")
        self.assertTrue(receipt["physical_effect_confirmed"])
        self.assertFalse(receipt["outcome_unknown"])
        self.assertFalse(receipt["automatic_retry_allowed"])
        self.assertFalse(receipt["receipt_builder_executed_action"])
        self.assertFalse(receipt["external_action_executed_by_this_module"])
        self.assertTrue(
            verify_local_action_audit_receipt(receipt)["valid"]
        )

    def test_spotify_partial_is_not_mislabeled_as_success(self):
        request, dispatch = self.request_and_dispatch(
            "AION, abre Spotify e toca sertanejo"
        )
        bindings = local_action_bindings(request)
        self.assertEqual(len(bindings), 2)
        results = [
            self.action_result(bindings[0], evidence_char="e"),
            self.action_result(
                bindings[1],
                outcome="CONFIRMED_TERMINAL_FAILURE",
                evidence_char="f",
            ),
        ]
        observation = self.observation(
            request,
            dispatch,
            results,
            declared_outcome="CONFIRMED_PARTIAL",
        )
        receipt = build_local_action_audit_receipt(
            request,
            dispatch,
            observation,
            observed_at=OBSERVED,
        )
        self.assertEqual(receipt["outcome_state"], "CONFIRMED_PARTIAL")
        self.assertTrue(receipt["partial_effect_confirmed"])
        self.assertTrue(receipt["physical_effect_confirmed"])
        self.assertFalse(receipt["terminal_failure_confirmed"])
        self.assertFalse(receipt["outcome_unknown"])

    def test_action_parameters_are_bound_to_outcome_evidence(self):
        request, dispatch = self.request_and_dispatch(
            "AION, abre Spotify e toca sertanejo"
        )
        bindings = local_action_bindings(request)
        results = [
            self.action_result(bindings[0], evidence_char="1"),
            self.action_result(bindings[1], evidence_char="2"),
        ]
        results[1]["parameters_digest"] = digest_char("9")
        receipt = build_local_action_audit_receipt(
            request,
            dispatch,
            self.observation(request, dispatch, results),
            observed_at=OBSERVED,
        )
        self.assertEqual(receipt["state"], "BLOCKED")
        self.assertIn(
            "ACTION_PARAMETERS_DIGEST_MISMATCH",
            receipt["blockers"],
        )

    def test_outcome_unknown_is_immutable_and_never_auto_retried(self):
        request, dispatch = self.request_and_dispatch()
        bindings = local_action_bindings(request)
        unknown = self.action_result(
            bindings[0],
            outcome="OUTCOME_UNKNOWN",
            ambiguity="IPC_LOST_AFTER_DISPATCH",
            evidence_char="3",
        )
        observation = self.observation(
            request,
            dispatch,
            [unknown],
            declared_outcome="OUTCOME_UNKNOWN",
            completed_at="",
        )
        receipt = build_local_action_audit_receipt(
            request,
            dispatch,
            observation,
            observed_at=OBSERVED,
        )
        self.assertEqual(receipt["state"], "RECEIPT_READY")
        self.assertEqual(receipt["outcome_state"], "OUTCOME_UNKNOWN")
        self.assertTrue(receipt["outcome_unknown"])
        self.assertTrue(receipt["separate_reconciliation_required"])
        self.assertFalse(receipt["automatic_retry_allowed"])
        self.assertFalse(receipt["automatic_reconciliation_allowed"])
        self.assertFalse(receipt["physical_effect_confirmed"])
        self.assertTrue(receipt["new_attempt_requires_fresh_owner_command"])
        self.assertTrue(receipt["new_attempt_requires_new_nonce"])

    def test_unknown_cannot_be_declared_success(self):
        request, dispatch = self.request_and_dispatch()
        bindings = local_action_bindings(request)
        unknown = self.action_result(
            bindings[0],
            outcome="OUTCOME_UNKNOWN",
            ambiguity="POSTCONDITION_NOT_OBSERVED",
            evidence_char="4",
        )
        receipt = build_local_action_audit_receipt(
            request,
            dispatch,
            self.observation(
                request,
                dispatch,
                [unknown],
                declared_outcome="CONFIRMED_SUCCESS",
                completed_at="",
            ),
            observed_at=OBSERVED,
        )
        self.assertEqual(receipt["state"], "BLOCKED")
        self.assertIn("DECLARED_OUTCOME_MISMATCH", receipt["blockers"])

    def test_terminal_failure_requires_authoritative_failure_evidence(self):
        request, dispatch = self.request_and_dispatch()
        bindings = local_action_bindings(request)
        failed = self.action_result(
            bindings[0],
            outcome="CONFIRMED_TERMINAL_FAILURE",
            evidence_char="5",
        )
        receipt = build_local_action_audit_receipt(
            request,
            dispatch,
            self.observation(
                request,
                dispatch,
                [failed],
                declared_outcome="CONFIRMED_TERMINAL_FAILURE",
            ),
            observed_at=OBSERVED,
        )
        self.assertEqual(
            receipt["outcome_state"],
            "CONFIRMED_TERMINAL_FAILURE",
        )
        self.assertTrue(receipt["terminal_failure_confirmed"])
        self.assertFalse(receipt["physical_effect_confirmed"])

        invalid_result = dict(failed)
        invalid_result["terminal_failure_verified"] = False
        blocked = build_local_action_audit_receipt(
            request,
            dispatch,
            self.observation(request, dispatch, [invalid_result]),
            observed_at=OBSERVED,
        )
        self.assertEqual(blocked["state"], "BLOCKED")
        self.assertIn(
            "TERMINAL_FAILURE_EVIDENCE_REQUIRED",
            blocked["blockers"],
        )

    def test_adapter_signature_and_exact_dispatch_binding_are_required(self):
        request, dispatch = self.request_and_dispatch()
        bindings = local_action_bindings(request)
        result = self.action_result(bindings[0], evidence_char="6")

        bad_signature = build_local_action_audit_receipt(
            request,
            dispatch,
            self.observation(
                request,
                dispatch,
                [result],
                adapter_signature_verified=False,
            ),
            observed_at=OBSERVED,
        )
        self.assertIn(
            "ADAPTER_SIGNATURE_NOT_VERIFIED",
            bad_signature["blockers"],
        )

        bad_dispatch = build_local_action_audit_receipt(
            request,
            dispatch,
            self.observation(
                request,
                dispatch,
                [result],
                dispatch_readiness_digest=digest_char("7"),
            ),
            observed_at=OBSERVED,
        )
        self.assertIn(
            "OBSERVATION_DISPATCH_DIGEST_MISMATCH",
            bad_dispatch["blockers"],
        )

    def test_raw_process_output_or_executable_material_is_rejected(self):
        request, dispatch = self.request_and_dispatch()
        bindings = local_action_bindings(request)
        result = self.action_result(bindings[0], evidence_char="8")

        for injected in (
            {"stdout": "process output"},
            {"executable": "C:/unsafe/app.exe"},
            {"command_line": "unsafe --arg"},
            {"token": "secret"},
        ):
            with self.subTest(injected=injected):
                observation = self.observation(
                    request,
                    dispatch,
                    [result],
                    **injected,
                )
                receipt = build_local_action_audit_receipt(
                    request,
                    dispatch,
                    observation,
                    observed_at=OBSERVED,
                )
                self.assertEqual(receipt["state"], "BLOCKED")
                self.assertIn(
                    "ADAPTER_OBSERVATION_CONTAINS_FORBIDDEN_MATERIAL",
                    receipt["blockers"],
                )

    def test_receipt_digest_detects_tampering(self):
        request, dispatch = self.request_and_dispatch()
        bindings = local_action_bindings(request)
        receipt = build_local_action_audit_receipt(
            request,
            dispatch,
            self.observation(
                request,
                dispatch,
                [self.action_result(bindings[0], evidence_char="a")],
            ),
            observed_at=OBSERVED,
        )
        self.assertTrue(verify_local_action_audit_receipt(receipt)["valid"])

        tampered = copy.deepcopy(receipt)
        tampered["action_results"][0]["evidence_digest"] = digest_char("0")
        verified = verify_local_action_audit_receipt(tampered)
        self.assertFalse(verified["valid"])
        self.assertIn("RECEIPT_DIGEST_MISMATCH", verified["blockers"])

    def test_receipt_policy_is_fail_closed(self):
        policy = local_action_audit_policy()
        self.assertTrue(
            policy["success_requires_positive_postcondition_evidence"]
        )
        self.assertTrue(
            policy["terminal_failure_requires_authoritative_failure_evidence"]
        )
        self.assertTrue(policy["partial_outcome_is_explicit"])
        self.assertTrue(policy["ambiguity_always_becomes_outcome_unknown"])
        self.assertFalse(policy["absence_of_error_is_success"])
        self.assertFalse(policy["absence_of_response_is_terminal_failure"])
        self.assertFalse(policy["outcome_unknown_automatic_retry"])
        self.assertFalse(policy["outcome_unknown_automatic_reconciliation"])
        self.assertTrue(
            policy["outcome_unknown_separate_reconciliation_required"]
        )
        self.assertTrue(policy["new_attempt_requires_fresh_owner_command"])
        self.assertTrue(policy["new_attempt_requires_new_nonce"])
        self.assertFalse(policy["raw_process_output_allowed"])
        self.assertFalse(policy["executable_material_allowed"])
        self.assertFalse(policy["credential_material_allowed"])
        self.assertFalse(policy["receipt_persisted"])
        self.assertFalse(policy["receipt_signed"])
        self.assertFalse(policy["physical_action_performed_by_contract"])
        self.assertFalse(policy["network_called"])
        self.assertFalse(policy["worker_armed"])
        self.assertFalse(policy["deploy_executed"])
        self.assertFalse(policy["core_checkpoint_write"])
        self.assertFalse(policy["executes_action"])


if __name__ == "__main__":
    unittest.main()
