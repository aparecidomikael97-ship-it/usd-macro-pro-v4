import copy
import unittest

from atlasquant_aion_windows_offline_build_sandbox_input_mount_v1 import (
    PREFLIGHT_SCHEMA,
)
from atlasquant_aion_windows_sandbox_physical_probe_plan_evidence_v1 import (
    BUNDLE_SCHEMA,
    EVIDENCE_SCHEMA,
    PLAN_SCHEMA,
    PROBE_REQUIREMENTS,
    PROBE_SPECS,
    READY_PLAN_STATE,
    READY_REVIEW_STATE,
    REVIEW_SCHEMA,
    build_probe_plan,
    build_uncollected_evidence_bundle,
    build_probe_implementation_review,
    physical_probe_policy,
    validate_evidence_candidate_shape,
)


D = lambda c: "sha256:" + (c * 64)


class AionWindowsSandboxPhysicalProbePlanEvidenceV1Tests(unittest.TestCase):
    def preflight(self, requirements=None):
        return {
            "schema": PREFLIGHT_SCHEMA,
            "state": "WINDOWS_OFFLINE_BUILD_SANDBOX_READY_FOR_PHYSICAL_PROBE",
            "sandbox_preflight_digest": D("1"),
            "required_physical_proofs": list(
                requirements if requirements is not None else PROBE_REQUIREMENTS
            ),
            "build_authorized": False,
            "build_started": False,
            "package_built": False,
            "package_installed": False,
        }

    def plan(self, preflight=None):
        out = build_probe_plan(
            preflight or self.preflight(),
            host_binding_digest=D("2"),
            collector_manifest_digest=D("3"),
            evidence_store_root_digest=D("4"),
            plan_created_at="2026-10-08T15:00:00+00:00",
        )
        return out

    def candidate(self, plan, requirement):
        measurement = next(
            item
            for item in plan["measurements"]
            if item["requirement"] == requirement
        )
        spec = PROBE_SPECS[requirement]
        return {
            "schema": EVIDENCE_SCHEMA,
            "requirement": requirement,
            "measurement_plan_digest": measurement["measurement_plan_digest"],
            "probe_plan_digest": plan["probe_plan_digest"],
            "sandbox_preflight_digest": plan["sandbox_preflight_digest"],
            "host_binding_digest": plan["host_binding_digest"],
            "collector_manifest_digest": plan["collector_manifest_digest"],
            "collection_state": "COLLECTED_CANDIDATE_UNTRUSTED",
            "evidence_slot_digest": D("5"),
            "observed_value": spec["expected_observation"],
            "negative_test_observed_value": spec["negative_test"],
            "raw_evidence_ref": "evidence://windows/probe/1",
            "raw_evidence_digest": D("6"),
            "collector_binary_digest": D("7"),
            "collector_signature_evidence_digest": D("8"),
            "collected_at": "2026-10-08T15:01:00+00:00",
            "valid_until": "2026-10-08T15:02:00+00:00",
            "sequence": measurement["sequence"],
            "evidence_is_physical": False,
            "independently_verified": False,
            "host_binding_verified": False,
            "preflight_binding_verified": False,
            "collector_identity_verified": False,
            "negative_test_verified": False,
            "freshness_verified": False,
            "physical_proof_verified": False,
        }

    def test_plan_inherits_exact_twelve_physical_requirements(self):
        plan = self.plan()
        self.assertEqual(plan["schema"], PLAN_SCHEMA)
        self.assertEqual(plan["state"], READY_PLAN_STATE, plan["blockers"])
        self.assertEqual(plan["requirements"], list(PROBE_REQUIREMENTS))
        self.assertEqual(len(plan["requirements"]), 12)
        self.assertEqual(len(plan["measurements"]), 12)
        self.assertTrue(plan["probe_plan_digest"].startswith("sha256:"))
        self.assertFalse(plan["physical_probe_implemented"])
        self.assertFalse(plan["physical_probe_executed"])
        self.assertFalse(plan["physical_proof_verified"])
        self.assertFalse(plan["independent_verifier_implemented"])
        self.assertFalse(plan["external_root_of_trust_available"])
        self.assertFalse(plan["build_authorized"])
        self.assertFalse(plan["build_started"])

    def test_upstream_requirement_drift_blocks_plan(self):
        requirements = list(PROBE_REQUIREMENTS)
        requirements.pop()
        plan = self.plan(self.preflight(requirements))
        self.assertEqual(plan["state"], "BLOCKED")
        self.assertIn(
            "PHYSICAL_PROBE_REQUIREMENT_SET_MISMATCH",
            plan["blockers"],
        )

        reordered = list(PROBE_REQUIREMENTS)
        reordered[0], reordered[1] = reordered[1], reordered[0]
        plan2 = self.plan(self.preflight(reordered))
        self.assertEqual(plan2["state"], "BLOCKED")
        self.assertIn(
            "PHYSICAL_PROBE_REQUIREMENT_SET_MISMATCH",
            plan2["blockers"],
        )

    def test_every_measurement_has_method_negative_test_and_freshness(self):
        plan = self.plan()
        for index, measurement in enumerate(plan["measurements"], start=1):
            requirement = measurement["requirement"]
            spec = PROBE_SPECS[requirement]
            self.assertEqual(measurement["sequence"], index)
            self.assertEqual(measurement["platform"], "WINDOWS")
            self.assertEqual(
                measurement["measurement_method"],
                spec["measurement_method"],
            )
            self.assertEqual(
                measurement["expected_observation"],
                spec["expected_observation"],
            )
            self.assertEqual(
                measurement["negative_test"],
                spec["negative_test"],
            )
            self.assertEqual(
                measurement["freshness_seconds"],
                spec["freshness_seconds"],
            )
            self.assertTrue(measurement["requires_raw_evidence"])
            self.assertTrue(measurement["requires_raw_evidence_digest"])
            self.assertTrue(measurement["requires_collector_binary_digest"])
            self.assertTrue(
                measurement["requires_collector_signature_evidence"]
            )
            self.assertTrue(measurement["requires_same_host_binding"])
            self.assertTrue(measurement["requires_preflight_binding"])
            self.assertTrue(measurement["requires_negative_test"])
            self.assertTrue(measurement["requires_recheck_before_use"])
            self.assertFalse(measurement["physical_probe_executed"])
            self.assertFalse(measurement["physical_proof_verified"])

    def test_uncollected_bundle_has_all_slots_but_zero_proof(self):
        plan = self.plan()
        bundle = build_uncollected_evidence_bundle(plan)
        self.assertEqual(bundle["schema"], BUNDLE_SCHEMA)
        self.assertEqual(
            bundle["state"],
            "PHYSICAL_PROBE_EVIDENCE_SCHEMA_READY_UNCOLLECTED",
            bundle["blockers"],
        )
        self.assertEqual(bundle["required_total"], 12)
        self.assertEqual(bundle["collected_total"], 0)
        self.assertEqual(bundle["verified_total"], 0)
        self.assertEqual(
            bundle["missing_requirements"],
            list(PROBE_REQUIREMENTS),
        )
        self.assertEqual(len(bundle["evidence"]), 12)
        for evidence in bundle["evidence"]:
            self.assertEqual(evidence["collection_state"], "NOT_COLLECTED")
            self.assertEqual(evidence["observed_value"], "NOT_MEASURED")
            self.assertEqual(
                evidence["negative_test_observed_value"],
                "NOT_MEASURED",
            )
            self.assertEqual(evidence["raw_evidence_digest"], "")
            self.assertFalse(evidence["evidence_is_physical"])
            self.assertFalse(evidence["independently_verified"])
            self.assertFalse(evidence["physical_proof_verified"])
        self.assertFalse(bundle["physical_probe_executed"])
        self.assertFalse(bundle["physical_proof_verified"])
        self.assertFalse(bundle["build_authorized"])

    def test_future_candidate_shape_can_be_valid_but_never_trusted(self):
        plan = self.plan()
        requirement = "WINDOWS_NETWORK_DENY_PHYSICAL_PROOF_REQUIRED"
        candidate = self.candidate(plan, requirement)
        out = validate_evidence_candidate_shape(plan, candidate)
        self.assertEqual(out["schema"], REVIEW_SCHEMA)
        self.assertEqual(
            out["state"],
            "EVIDENCE_CANDIDATE_SHAPE_VALID_BUT_UNTRUSTED",
            out["blockers"],
        )
        self.assertTrue(out["shape_valid"])
        self.assertFalse(out["evidence_is_physical"])
        self.assertFalse(out["independently_verified"])
        self.assertFalse(out["physical_proof_verified"])
        self.assertFalse(out["build_authorized"])

    def test_self_asserted_verification_flags_are_rejected(self):
        plan = self.plan()
        requirement = "PINNED_PYTHON_BINARY_PROOF_REQUIRED"
        for field in (
            "evidence_is_physical",
            "independently_verified",
            "host_binding_verified",
            "preflight_binding_verified",
            "collector_identity_verified",
            "negative_test_verified",
            "freshness_verified",
            "physical_proof_verified",
        ):
            with self.subTest(field=field):
                candidate = self.candidate(plan, requirement)
                candidate[field] = True
                out = validate_evidence_candidate_shape(plan, candidate)
                self.assertEqual(out["state"], "BLOCKED")
                self.assertIn(
                    "CALLER_VERIFICATION_CLAIM_NOT_TRUSTED:" + field,
                    out["blockers"],
                )
                self.assertFalse(out["physical_proof_verified"])

    def test_host_collector_preflight_and_measurement_binding_tamper_blocks(self):
        plan = self.plan()
        requirement = "WINDOWS_RESTRICTED_TOKEN_PROOF_REQUIRED"
        cases = (
            ("host_binding_digest", "EVIDENCE_HOST_BINDING_MISMATCH"),
            (
                "collector_manifest_digest",
                "EVIDENCE_COLLECTOR_MANIFEST_MISMATCH",
            ),
            (
                "sandbox_preflight_digest",
                "EVIDENCE_PREFLIGHT_BINDING_MISMATCH",
            ),
            (
                "measurement_plan_digest",
                "EVIDENCE_MEASUREMENT_BINDING_MISMATCH",
            ),
            ("probe_plan_digest", "EVIDENCE_PLAN_BINDING_MISMATCH"),
        )
        for field, expected in cases:
            with self.subTest(field=field):
                candidate = self.candidate(plan, requirement)
                candidate[field] = D("0")
                out = validate_evidence_candidate_shape(plan, candidate)
                self.assertEqual(out["state"], "BLOCKED")
                self.assertIn(expected, out["blockers"])

    def test_expected_and_negative_observations_both_must_match(self):
        plan = self.plan()
        requirement = "NO_CHILD_PROCESS_PHYSICAL_PROOF_REQUIRED"

        bad_positive = self.candidate(plan, requirement)
        bad_positive["observed_value"] = "CHILD_PROCESS_CREATION_ALLOWED"
        out = validate_evidence_candidate_shape(plan, bad_positive)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("EXPECTED_OBSERVATION_NOT_MET", out["blockers"])

        bad_negative = self.candidate(plan, requirement)
        bad_negative["negative_test_observed_value"] = "NOT_TESTED"
        out2 = validate_evidence_candidate_shape(plan, bad_negative)
        self.assertEqual(out2["state"], "BLOCKED")
        self.assertIn("NEGATIVE_TEST_OBSERVATION_NOT_MET", out2["blockers"])

    def test_evidence_freshness_window_is_requirement_specific(self):
        plan = self.plan()

        network = self.candidate(
            plan,
            "WINDOWS_NETWORK_DENY_PHYSICAL_PROOF_REQUIRED",
        )
        network["valid_until"] = "2026-10-08T15:02:01+00:00"
        blocked = validate_evidence_candidate_shape(plan, network)
        self.assertEqual(blocked["state"], "BLOCKED")
        self.assertIn(
            "EVIDENCE_VALIDITY_WINDOW_TOO_LONG",
            blocked["blockers"],
        )

        token = self.candidate(
            plan,
            "WINDOWS_RESTRICTED_TOKEN_PROOF_REQUIRED",
        )
        token["valid_until"] = "2026-10-08T15:03:00+00:00"
        ready = validate_evidence_candidate_shape(plan, token)
        self.assertEqual(
            ready["state"],
            "EVIDENCE_CANDIDATE_SHAPE_VALID_BUT_UNTRUSTED",
            ready["blockers"],
        )

    def test_raw_evidence_and_collector_digests_are_required(self):
        plan = self.plan()
        requirement = "WINDOWS_JOB_OBJECT_LIMITS_PROOF_REQUIRED"
        cases = (
            ("raw_evidence_digest", "RAW_EVIDENCE_DIGEST_REQUIRED"),
            ("collector_binary_digest", "COLLECTOR_BINARY_DIGEST_REQUIRED"),
            (
                "collector_signature_evidence_digest",
                "COLLECTOR_SIGNATURE_EVIDENCE_DIGEST_REQUIRED",
            ),
        )
        for field, expected in cases:
            with self.subTest(field=field):
                candidate = self.candidate(plan, requirement)
                candidate[field] = ""
                out = validate_evidence_candidate_shape(plan, candidate)
                self.assertEqual(out["state"], "BLOCKED")
                self.assertIn(expected, out["blockers"])

    def test_implementation_review_is_ready_only_for_collector_work(self):
        plan = self.plan()
        bundle = build_uncollected_evidence_bundle(plan)
        review = build_probe_implementation_review(
            plan,
            bundle,
            collector_source_digest=D("9"),
            collector_test_digest=D("a"),
            independent_verifier_design_digest=D("b"),
            evidence_store_design_digest=D("c"),
        )
        self.assertEqual(
            review["state"],
            READY_REVIEW_STATE,
            review["blockers"],
        )
        self.assertEqual(
            review["next_physical_phase"],
            "WINDOWS_PROBE_COLLECTOR_IMPLEMENTATION_ON_OWNER_PC",
        )
        self.assertFalse(review["collector_implemented"])
        self.assertFalse(review["collector_executed"])
        self.assertFalse(review["independent_verifier_implemented"])
        self.assertFalse(review["evidence_collected"])
        self.assertFalse(review["physical_probe_executed"])
        self.assertFalse(review["physical_proof_verified"])
        self.assertFalse(review["windows_sandbox_verified"])
        self.assertFalse(review["build_authorized"])
        self.assertFalse(review["build_started"])
        self.assertFalse(review["package_built"])

    def test_policy_never_confuses_schema_with_physical_proof(self):
        policy = physical_probe_policy()
        self.assertEqual(policy["requirement_count"], 12)
        self.assertEqual(policy["requirements"], list(PROBE_REQUIREMENTS))
        self.assertTrue(policy["preflight_requirement_set_must_match_exactly"])
        self.assertTrue(policy["host_binding_required"])
        self.assertTrue(policy["collector_manifest_binding_required"])
        self.assertTrue(policy["sandbox_preflight_binding_required"])
        self.assertTrue(policy["raw_evidence_digest_required"])
        self.assertTrue(policy["collector_binary_digest_required"])
        self.assertTrue(policy["collector_signature_evidence_required"])
        self.assertTrue(policy["negative_test_required"])
        self.assertTrue(policy["freshness_window_required"])
        self.assertTrue(policy["recheck_before_use_required"])
        self.assertFalse(policy["caller_boolean_verification_is_authority"])
        self.assertFalse(policy["document_digest_is_physical_proof"])
        self.assertFalse(policy["physical_probe_implemented"])
        self.assertFalse(policy["physical_probe_executed"])
        self.assertFalse(policy["collector_implemented"])
        self.assertFalse(policy["collector_executed"])
        self.assertFalse(policy["independent_verifier_implemented"])
        self.assertFalse(policy["external_root_of_trust_available"])
        self.assertFalse(policy["evidence_collected"])
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
