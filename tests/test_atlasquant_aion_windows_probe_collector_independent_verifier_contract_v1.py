import base64
import copy
import hashlib
import json
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from atlasquant_aion_windows_offline_build_sandbox_input_mount_v1 import (
    PREFLIGHT_SCHEMA,
)
from atlasquant_aion_windows_sandbox_physical_probe_plan_evidence_v1 import (
    PROBE_REQUIREMENTS,
    build_probe_plan,
)
from atlasquant_aion_windows_probe_collector_independent_verifier_contract_v1 import (
    COLLECTOR_SIGNATURE_CONTEXT,
    VERIFIER_SIGNATURE_CONTEXT,
    READY_COLLECTOR_STATE,
    READY_VERIFIER_STATE,
    READY_SEPARATION_STATE,
    READY_REVIEW_STATE,
    build_collector_manifest,
    build_verifier_manifest,
    attest_collector_release,
    attest_verifier_release,
    build_collector_verifier_separation,
    build_unissued_verification_receipt_template,
    build_implementation_review,
    collector_verifier_policy,
    public_key_fingerprint,
)


D = lambda c: "sha256:" + (c * 64)


def canonical_digest(value):
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=str,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


class AionWindowsProbeCollectorIndependentVerifierContractV1Tests(unittest.TestCase):
    def setUp(self):
        self.collector_private = Ed25519PrivateKey.generate()
        self.verifier_private = Ed25519PrivateKey.generate()
        self.collector_public_b64 = self._public_b64(self.collector_private)
        self.verifier_public_b64 = self._public_b64(self.verifier_private)
        self.collector_fp = public_key_fingerprint(
            self.collector_public_b64,
            label="COLLECTOR",
        )
        self.verifier_fp = public_key_fingerprint(
            self.verifier_public_b64,
            label="VERIFIER",
        )

    def _public_b64(self, private):
        raw = private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return base64.b64encode(raw).decode("ascii")

    def plan(self):
        preflight = {
            "schema": PREFLIGHT_SCHEMA,
            "state": "WINDOWS_OFFLINE_BUILD_SANDBOX_READY_FOR_PHYSICAL_PROBE",
            "sandbox_preflight_digest": D("1"),
            "required_physical_proofs": list(PROBE_REQUIREMENTS),
        }
        plan = build_probe_plan(
            preflight,
            host_binding_digest=D("2"),
            collector_manifest_digest=D("3"),
            evidence_store_root_digest=D("4"),
            plan_created_at="2026-10-08T15:30:00+00:00",
        )
        self.assertEqual(
            plan["state"],
            "WINDOWS_SANDBOX_PHYSICAL_PROBE_PLAN_READY",
            plan["blockers"],
        )
        return plan

    def collector(self, plan=None, **changes):
        plan = plan or self.plan()
        kwargs = {
            "plan": plan,
            "collector_id": "collector://aion-windows-probe-v1",
            "collector_source_digest": D("5"),
            "collector_test_digest": D("6"),
            "collector_binary_digest": D("7"),
            "build_provenance_digest": D("8"),
            "package_attestation_digest": D("9"),
            "collector_public_key_b64": self.collector_public_b64,
            "expected_collector_key_fingerprint": self.collector_fp,
        }
        kwargs.update(changes)
        return build_collector_manifest(**kwargs)

    def verifier(self, plan, collector, **changes):
        kwargs = {
            "plan": plan,
            "collector_manifest": collector,
            "verifier_id": "verifier://aion-windows-probe-v1",
            "verifier_source_digest": D("a"),
            "verifier_test_digest": D("b"),
            "verifier_binary_digest": D("c"),
            "raw_evidence_decoder_digest": D("d"),
            "verification_policy_digest": D("e"),
            "trust_policy_digest": D("f"),
            "verifier_public_key_b64": self.verifier_public_b64,
            "expected_verifier_key_fingerprint": self.verifier_fp,
        }
        kwargs.update(changes)
        return build_verifier_manifest(**kwargs)

    def _release_signature(self, manifest, component, private_key):
        if component == "COLLECTOR":
            payload = {
                "component": "COLLECTOR",
                "manifest_digest": manifest["collector_manifest_digest"],
                "source_digest": manifest["collector_source_digest"],
                "test_digest": manifest["collector_test_digest"],
                "binary_digest": manifest["collector_binary_digest"],
                "key_fingerprint": manifest["collector_key_fingerprint"],
            }
            context = COLLECTOR_SIGNATURE_CONTEXT
        else:
            payload = {
                "component": "VERIFIER",
                "manifest_digest": manifest["verifier_manifest_digest"],
                "source_digest": manifest["verifier_source_digest"],
                "test_digest": manifest["verifier_test_digest"],
                "binary_digest": manifest["verifier_binary_digest"],
                "key_fingerprint": manifest["verifier_key_fingerprint"],
            }
            context = VERIFIER_SIGNATURE_CONTEXT
        message = context + canonical_digest(payload).encode("ascii")
        return base64.b64encode(private_key.sign(message)).decode("ascii")

    def signed_components(self):
        plan = self.plan()
        collector = self.collector(plan)
        verifier = self.verifier(plan, collector)
        collector_release = attest_collector_release(
            collector,
            collector_public_key_b64=self.collector_public_b64,
            signature_b64=self._release_signature(
                collector,
                "COLLECTOR",
                self.collector_private,
            ),
        )
        verifier_release = attest_verifier_release(
            verifier,
            verifier_public_key_b64=self.verifier_public_b64,
            signature_b64=self._release_signature(
                verifier,
                "VERIFIER",
                self.verifier_private,
            ),
        )
        return plan, collector, collector_release, verifier, verifier_release

    def test_collector_manifest_is_measurement_only(self):
        collector = self.collector()
        self.assertEqual(
            collector["state"],
            READY_COLLECTOR_STATE,
            collector["blockers"],
        )
        self.assertEqual(len(collector["measurement_contract"]), 12)
        self.assertEqual(
            [row["requirement"] for row in collector["measurement_contract"]],
            list(PROBE_REQUIREMENTS),
        )
        self.assertTrue(
            collector["may_collect_raw_evidence_in_future_physical_phase"]
        )
        self.assertFalse(collector["may_verify_own_evidence"])
        self.assertFalse(collector["may_issue_verification_receipt"])
        self.assertFalse(collector["may_authorize_build"])
        self.assertFalse(collector["collector_implemented"])
        self.assertFalse(collector["collector_executed"])
        self.assertFalse(collector["evidence_collected"])
        self.assertFalse(collector["process_spawned"])
        self.assertFalse(collector["network_called"])
        self.assertFalse(collector["build_authorized"])

    def test_collector_key_fingerprint_mismatch_blocks(self):
        collector = self.collector(
            expected_collector_key_fingerprint=D("0"),
        )
        self.assertEqual(collector["state"], "BLOCKED")
        self.assertIn(
            "COLLECTOR_KEY_FINGERPRINT_MISMATCH",
            collector["blockers"],
        )

    def test_verifier_is_separate_and_cannot_collect(self):
        plan = self.plan()
        collector = self.collector(plan)
        verifier = self.verifier(plan, collector)
        self.assertEqual(
            verifier["state"],
            READY_VERIFIER_STATE,
            verifier["blockers"],
        )
        self.assertNotEqual(
            collector["collector_id"],
            verifier["verifier_id"],
        )
        self.assertNotEqual(
            collector["collector_source_digest"],
            verifier["verifier_source_digest"],
        )
        self.assertNotEqual(
            collector["collector_binary_digest"],
            verifier["verifier_binary_digest"],
        )
        self.assertNotEqual(
            collector["collector_key_fingerprint"],
            verifier["verifier_key_fingerprint"],
        )
        self.assertFalse(verifier["may_collect_evidence"])
        self.assertFalse(verifier["may_modify_evidence"])
        self.assertFalse(verifier["may_execute_probe"])
        self.assertFalse(verifier["may_authorize_build"])
        self.assertFalse(verifier["verifier_implemented"])
        self.assertFalse(verifier["verifier_executed"])
        self.assertFalse(verifier["evidence_verified"])
        self.assertFalse(verifier["verification_receipt_issued"])
        self.assertFalse(verifier["network_called"])

    def test_shared_identity_source_binary_or_key_blocks_verifier(self):
        plan = self.plan()
        collector = self.collector(plan)
        cases = (
            (
                {"verifier_id": collector["collector_id"]},
                "COLLECTOR_VERIFIER_IDENTITY_MUST_DIFFER",
            ),
            (
                {
                    "verifier_source_digest":
                        collector["collector_source_digest"]
                },
                "COLLECTOR_VERIFIER_SOURCE_MUST_DIFFER",
            ),
            (
                {
                    "verifier_binary_digest":
                        collector["collector_binary_digest"]
                },
                "COLLECTOR_VERIFIER_BINARY_MUST_DIFFER",
            ),
            (
                {
                    "verifier_public_key_b64": self.collector_public_b64,
                    "expected_verifier_key_fingerprint": self.collector_fp,
                },
                "COLLECTOR_VERIFIER_SIGNING_KEYS_MUST_DIFFER",
            ),
        )
        for changes, expected in cases:
            with self.subTest(expected=expected):
                verifier = self.verifier(plan, collector, **changes)
                self.assertEqual(verifier["state"], "BLOCKED")
                self.assertIn(expected, verifier["blockers"])

    def test_collector_release_signature_verifies_and_tamper_blocks(self):
        plan = self.plan()
        collector = self.collector(plan)
        signature = self._release_signature(
            collector,
            "COLLECTOR",
            self.collector_private,
        )
        release = attest_collector_release(
            collector,
            collector_public_key_b64=self.collector_public_b64,
            signature_b64=signature,
        )
        self.assertEqual(
            release["state"],
            "COLLECTOR_RELEASE_SIGNATURE_VERIFIED",
            release["blockers"],
        )
        self.assertTrue(release["signature_verified"])
        self.assertFalse(release["collector_executed"])
        self.assertFalse(release["evidence_collected"])
        self.assertFalse(release["build_authorized"])

        tampered = copy.deepcopy(collector)
        tampered["collector_binary_digest"] = D("0")
        bad = attest_collector_release(
            tampered,
            collector_public_key_b64=self.collector_public_b64,
            signature_b64=signature,
        )
        self.assertEqual(bad["state"], "BLOCKED")
        self.assertIn("COLLECTOR_RELEASE_SIGNATURE_INVALID", bad["blockers"])

    def test_verifier_release_signature_verifies_and_wrong_signer_blocks(self):
        plan = self.plan()
        collector = self.collector(plan)
        verifier = self.verifier(plan, collector)
        signature = self._release_signature(
            verifier,
            "VERIFIER",
            self.verifier_private,
        )
        release = attest_verifier_release(
            verifier,
            verifier_public_key_b64=self.verifier_public_b64,
            signature_b64=signature,
        )
        self.assertEqual(
            release["state"],
            "VERIFIER_RELEASE_SIGNATURE_VERIFIED",
            release["blockers"],
        )
        self.assertTrue(release["signature_verified"])
        self.assertFalse(release["verifier_executed"])
        self.assertFalse(release["evidence_verified"])
        self.assertFalse(release["build_authorized"])

        wrong = attest_verifier_release(
            verifier,
            verifier_public_key_b64=self.collector_public_b64,
            signature_b64=signature,
        )
        self.assertEqual(wrong["state"], "BLOCKED")
        self.assertIn("VERIFIER_KEY_FINGERPRINT_MISMATCH", wrong["blockers"])

    def test_separation_requires_process_state_and_read_only_handoff(self):
        plan, collector, collector_release, verifier, verifier_release = (
            self.signed_components()
        )
        separation = build_collector_verifier_separation(
            collector,
            collector_release,
            verifier,
            verifier_release,
            separate_process_boundary_required=True,
            separate_writable_state_required=True,
            verifier_raw_evidence_read_only_required=True,
        )
        self.assertEqual(
            separation["state"],
            READY_SEPARATION_STATE,
            separation["blockers"],
        )
        self.assertFalse(separation["collector_can_mark_verified"])
        self.assertFalse(separation["verifier_can_collect"])
        self.assertFalse(separation["verifier_can_modify_raw_evidence"])
        self.assertFalse(separation["shared_private_key_allowed"])
        self.assertFalse(separation["shared_binary_allowed"])
        self.assertFalse(separation["shared_writable_state_allowed"])
        self.assertFalse(separation["physical_separation_verified"])
        self.assertFalse(separation["build_authorized"])

        blocked = build_collector_verifier_separation(
            collector,
            collector_release,
            verifier,
            verifier_release,
            separate_process_boundary_required=False,
            separate_writable_state_required=True,
            verifier_raw_evidence_read_only_required=True,
        )
        self.assertEqual(blocked["state"], "BLOCKED")
        self.assertIn(
            "SEPARATE_PROCESS_BOUNDARY_REQUIRED",
            blocked["blockers"],
        )

    def test_receipt_template_has_zero_verified_requirements(self):
        plan, collector, collector_release, verifier, verifier_release = (
            self.signed_components()
        )
        separation = build_collector_verifier_separation(
            collector,
            collector_release,
            verifier,
            verifier_release,
            separate_process_boundary_required=True,
            separate_writable_state_required=True,
            verifier_raw_evidence_read_only_required=True,
        )
        receipt = build_unissued_verification_receipt_template(
            plan,
            collector,
            verifier,
            separation,
        )
        self.assertEqual(
            receipt["state"],
            "VERIFICATION_RECEIPT_TEMPLATE_READY_UNISSUED",
            receipt["blockers"],
        )
        self.assertEqual(receipt["required_total"], 12)
        self.assertEqual(receipt["verified_total"], 0)
        self.assertEqual(len(receipt["requirements"]), 12)
        self.assertTrue(
            all(
                row["verification_state"] == "NOT_VERIFIED"
                for row in receipt["requirements"]
            )
        )
        self.assertFalse(receipt["all_requirements_verified"])
        self.assertFalse(receipt["receipt_issued"])
        self.assertFalse(receipt["receipt_signed"])
        self.assertFalse(receipt["physical_proof_verified"])
        self.assertFalse(receipt["windows_sandbox_verified"])
        self.assertFalse(receipt["build_authorized"])
        self.assertFalse(receipt["build_started"])

    def test_implementation_review_stops_before_pc_execution(self):
        plan, collector, collector_release, verifier, verifier_release = (
            self.signed_components()
        )
        separation = build_collector_verifier_separation(
            collector,
            collector_release,
            verifier,
            verifier_release,
            separate_process_boundary_required=True,
            separate_writable_state_required=True,
            verifier_raw_evidence_read_only_required=True,
        )
        receipt = build_unissued_verification_receipt_template(
            plan,
            collector,
            verifier,
            separation,
        )
        review = build_implementation_review(
            plan,
            collector,
            verifier,
            separation,
            receipt,
            collector_windows_adapter_design_digest=D("1"),
            verifier_evidence_parser_design_digest=D("2"),
            verifier_trust_store_design_digest=D("3"),
            immutable_evidence_handoff_design_digest=D("4"),
        )
        self.assertEqual(
            review["state"],
            READY_REVIEW_STATE,
            review["blockers"],
        )
        self.assertEqual(
            review["next_pc_phase"],
            "IMPLEMENT_WINDOWS_COLLECTOR_AND_INDEPENDENT_VERIFIER_WITH_SYNTHETIC_PROBES",
        )
        self.assertFalse(review["collector_implemented"])
        self.assertFalse(review["collector_executed"])
        self.assertFalse(review["verifier_implemented"])
        self.assertFalse(review["verifier_executed"])
        self.assertFalse(review["physical_evidence_collected"])
        self.assertFalse(review["verification_receipt_issued"])
        self.assertFalse(review["physical_proof_verified"])
        self.assertFalse(review["windows_sandbox_verified"])
        self.assertFalse(review["build_authorized"])
        self.assertFalse(review["build_started"])
        self.assertFalse(review["package_built"])
        self.assertFalse(review["package_installed"])

    def test_policy_preserves_strict_two_party_separation(self):
        policy = collector_verifier_policy()
        self.assertEqual(policy["requirement_count"] if "requirement_count" in policy else len(policy["requirements"]), 12)
        self.assertTrue(policy["collector_and_verifier_ids_must_differ"])
        self.assertTrue(policy["collector_and_verifier_source_must_differ"])
        self.assertTrue(policy["collector_and_verifier_binary_must_differ"])
        self.assertTrue(
            policy["collector_and_verifier_signing_keys_must_differ"]
        )
        self.assertTrue(policy["collector_release_signature_required"])
        self.assertTrue(policy["verifier_release_signature_required"])
        self.assertTrue(policy["separate_process_boundary_required"])
        self.assertTrue(policy["separate_writable_state_required"])
        self.assertTrue(policy["verifier_raw_evidence_read_only_required"])
        self.assertFalse(policy["collector_can_mark_verified"])
        self.assertFalse(policy["collector_can_issue_verification_receipt"])
        self.assertFalse(policy["verifier_can_collect_evidence"])
        self.assertFalse(policy["verifier_can_modify_raw_evidence"])
        self.assertTrue(policy["verification_receipt_unissued"])
        self.assertFalse(policy["collector_implemented"])
        self.assertFalse(policy["collector_executed"])
        self.assertFalse(policy["verifier_implemented"])
        self.assertFalse(policy["verifier_executed"])
        self.assertFalse(policy["physical_evidence_collected"])
        self.assertFalse(policy["physical_proof_verified"])
        self.assertFalse(policy["windows_sandbox_verified"])
        self.assertFalse(policy["build_authorized"])
        self.assertFalse(policy["build_started"])
        self.assertFalse(policy["package_built"])
        self.assertFalse(policy["package_installed"])
        self.assertFalse(policy["process_spawned"])
        self.assertFalse(policy["filesystem_modified"])
        self.assertFalse(policy["network_called"])
        self.assertFalse(policy["github_api_called"])
        self.assertFalse(policy["live_repository_mutation_authorized"])
        self.assertFalse(policy["live_repository_mutation_performed"])
        self.assertFalse(policy["production_repository_mutation_performed"])
        self.assertFalse(policy["deploy_executed"])
        self.assertFalse(policy["worker_activated"])
        self.assertFalse(policy["provider_activated"])
        self.assertFalse(policy["production_persistence_activated"])


if __name__ == "__main__":
    unittest.main()
