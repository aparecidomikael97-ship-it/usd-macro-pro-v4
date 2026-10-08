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
    PROBE_SPECS,
    build_probe_plan,
)
from atlasquant_aion_windows_probe_collector_independent_verifier_contract_v1 import (
    COLLECTOR_SIGNATURE_CONTEXT,
    VERIFIER_SIGNATURE_CONTEXT,
    build_collector_manifest,
    build_verifier_manifest,
    attest_collector_release,
    attest_verifier_release,
    build_collector_verifier_separation,
    build_unissued_verification_receipt_template,
    public_key_fingerprint,
)
from atlasquant_aion_windows_immutable_evidence_receipt_persistence_v1 import (
    READY_STORE_STATE,
    READY_EVIDENCE_STATE,
    READY_CHAIN_STATE,
    READY_RECEIPT_PERSISTENCE_STATE,
    READY_ATTESTATION_SHAPE_STATE,
    READY_REVIEW_STATE,
    build_store_contract,
    build_evidence_record_candidate,
    build_evidence_chain_candidate,
    classify_append_replay,
    build_receipt_persistence_contract,
    validate_future_persistence_attestation_shape,
    build_implementation_review,
    evidence_persistence_policy,
)


def H(text):
    return "sha256:" + hashlib.sha256(str(text).encode("utf-8")).hexdigest()


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


class AionWindowsImmutableEvidenceReceiptPersistenceV1Tests(unittest.TestCase):
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
            "sandbox_preflight_digest": H("preflight"),
            "required_physical_proofs": list(PROBE_REQUIREMENTS),
        }
        plan = build_probe_plan(
            preflight,
            host_binding_digest=H("host"),
            collector_manifest_digest=H("collector-design"),
            evidence_store_root_digest=H("evidence-root"),
            plan_created_at="2026-10-08T15:30:00+00:00",
        )
        self.assertEqual(
            plan["state"],
            "WINDOWS_SANDBOX_PHYSICAL_PROBE_PLAN_READY",
            plan["blockers"],
        )
        return plan

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

    def components(self):
        plan = self.plan()
        collector = build_collector_manifest(
            plan,
            collector_id="collector://windows-probe-v1",
            collector_source_digest=H("collector-source"),
            collector_test_digest=H("collector-tests"),
            collector_binary_digest=H("collector-binary"),
            build_provenance_digest=H("collector-provenance"),
            package_attestation_digest=H("collector-package"),
            collector_public_key_b64=self.collector_public_b64,
            expected_collector_key_fingerprint=self.collector_fp,
        )
        self.assertEqual(
            collector["state"],
            "WINDOWS_PROBE_COLLECTOR_MANIFEST_READY",
            collector["blockers"],
        )
        verifier = build_verifier_manifest(
            plan,
            collector,
            verifier_id="verifier://windows-probe-v1",
            verifier_source_digest=H("verifier-source"),
            verifier_test_digest=H("verifier-tests"),
            verifier_binary_digest=H("verifier-binary"),
            raw_evidence_decoder_digest=H("decoder"),
            verification_policy_digest=H("verification-policy"),
            trust_policy_digest=H("trust-policy"),
            verifier_public_key_b64=self.verifier_public_b64,
            expected_verifier_key_fingerprint=self.verifier_fp,
        )
        self.assertEqual(
            verifier["state"],
            "WINDOWS_INDEPENDENT_VERIFIER_MANIFEST_READY",
            verifier["blockers"],
        )
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
        self.assertEqual(
            collector_release["state"],
            "COLLECTOR_RELEASE_SIGNATURE_VERIFIED",
            collector_release["blockers"],
        )
        self.assertEqual(
            verifier_release["state"],
            "VERIFIER_RELEASE_SIGNATURE_VERIFIED",
            verifier_release["blockers"],
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
            "COLLECTOR_VERIFIER_SEPARATION_CONFIRMED",
            separation["blockers"],
        )
        receipt_template = build_unissued_verification_receipt_template(
            plan,
            collector,
            verifier,
            separation,
        )
        self.assertEqual(
            receipt_template["state"],
            "VERIFICATION_RECEIPT_TEMPLATE_READY_UNISSUED",
            receipt_template["blockers"],
        )
        return (
            plan,
            collector,
            collector_release,
            verifier,
            verifier_release,
            separation,
            receipt_template,
        )

    def store(self):
        (
            plan,
            collector,
            collector_release,
            verifier,
            verifier_release,
            separation,
            receipt_template,
        ) = self.components()
        store = build_store_contract(
            plan,
            collector,
            verifier,
            separation,
            store_namespace="aion/windows/probe-evidence/v1",
            writer_manifest_digest=H("writer-manifest"),
            evidence_store_design_digest=H("evidence-store-design"),
            receipt_store_design_digest=H("receipt-store-design"),
        )
        self.assertEqual(store["state"], READY_STORE_STATE, store["blockers"])
        return (
            plan,
            collector,
            collector_release,
            verifier,
            verifier_release,
            separation,
            receipt_template,
            store,
        )

    def records(self, store_tuple=None):
        values = store_tuple or self.store()
        (
            plan,
            collector,
            collector_release,
            verifier,
            verifier_release,
            separation,
            receipt_template,
            store,
        ) = values
        previous = store["evidence_chain_genesis_digest"]
        records = []
        for sequence, requirement in enumerate(PROBE_REQUIREMENTS, start=1):
            measurement = next(
                row
                for row in plan["measurements"]
                if row["requirement"] == requirement
            )
            spec = PROBE_SPECS[requirement]
            record = build_evidence_record_candidate(
                store,
                plan,
                collector,
                requirement=requirement,
                sequence=sequence,
                measurement_plan_digest=measurement["measurement_plan_digest"],
                raw_evidence_digest=H("raw-" + requirement),
                evidence_payload_digest=H("payload-" + requirement),
                collector_binary_digest=collector["collector_binary_digest"],
                collector_release_payload_digest=collector_release[
                    "release_payload_digest"
                ],
                collector_signature_evidence_digest=H(
                    "collector-evidence-signature-" + requirement
                ),
                observed_value=spec["expected_observation"],
                negative_test_observed_value=spec["negative_test"],
                collected_at="2026-10-08T15:31:00+00:00",
                valid_until=(
                    "2026-10-08T15:31:30+00:00"
                    if requirement
                    == "WINDOWS_NETWORK_DENY_PHYSICAL_PROOF_REQUIRED"
                    else "2026-10-08T15:32:00+00:00"
                ),
                previous_record_digest=previous,
                expected_pre_store_revision=sequence - 1,
            )
            self.assertEqual(
                record["state"],
                READY_EVIDENCE_STATE,
                record["blockers"],
            )
            records.append(record)
            previous = record["evidence_record_digest"]
        return values, records

    def test_store_contract_is_append_only_and_nonwriting(self):
        *_, store = self.store()
        self.assertTrue(store["append_only_required"])
        self.assertTrue(store["compare_and_set_required"])
        self.assertTrue(store["exactly_once_required"])
        self.assertTrue(store["single_writer_commit_required"])
        self.assertTrue(store["read_after_write_required"])
        self.assertTrue(store["reopen_consistency_required"])
        self.assertFalse(store["delete_allowed"])
        self.assertFalse(store["replace_allowed"])
        self.assertFalse(store["truncate_allowed"])
        self.assertFalse(store["record_reorder_allowed"])
        self.assertFalse(store["receipt_rewrite_allowed"])
        self.assertTrue(store["same_identity_same_digest_is_idempotent"])
        self.assertTrue(store["same_identity_different_digest_is_conflict"])
        self.assertFalse(store["store_opened"])
        self.assertFalse(store["database_opened"])
        self.assertFalse(store["transaction_started"])
        self.assertFalse(store["cas_attempted"])
        self.assertFalse(store["record_written"])
        self.assertFalse(store["receipt_written"])
        self.assertFalse(store["filesystem_modified"])
        self.assertFalse(store["physical_persistence_verified"])
        self.assertFalse(store["build_authorized"])

    def test_exact_twelve_record_chain_is_ready_but_untrusted(self):
        values, records = self.records()
        store = values[-1]
        chain = build_evidence_chain_candidate(store, records)
        self.assertEqual(
            chain["state"],
            READY_CHAIN_STATE,
            chain["blockers"],
        )
        self.assertEqual(chain["record_count"], 12)
        self.assertEqual(
            [row["requirement"] for row in chain["records"]],
            list(PROBE_REQUIREMENTS),
        )
        self.assertEqual(
            chain["chain_head_digest"],
            records[-1]["evidence_record_digest"],
        )
        self.assertFalse(chain["physical_proof_verified"])
        self.assertFalse(chain["records_persisted"])
        self.assertFalse(chain["chain_reopened_verified"])
        self.assertFalse(chain["build_authorized"])

    def test_missing_or_reordered_record_blocks_chain(self):
        values, records = self.records()
        store = values[-1]
        missing = build_evidence_chain_candidate(store, records[:-1])
        self.assertEqual(missing["state"], "BLOCKED")
        self.assertIn(
            "EXACT_TWELVE_EVIDENCE_RECORDS_REQUIRED",
            missing["blockers"],
        )

        reordered = list(records)
        reordered[4], reordered[5] = reordered[5], reordered[4]
        blocked = build_evidence_chain_candidate(store, reordered)
        self.assertEqual(blocked["state"], "BLOCKED")
        self.assertTrue(
            any(
                item.startswith("EVIDENCE_REQUIREMENT_ORDER_MISMATCH:")
                for item in blocked["blockers"]
            )
        )

    def test_middle_link_tamper_blocks_chain(self):
        values, records = self.records()
        store = values[-1]
        tampered = copy.deepcopy(records)
        tampered[6]["previous_record_digest"] = H("forged-link")
        chain = build_evidence_chain_candidate(store, tampered)
        self.assertEqual(chain["state"], "BLOCKED")
        self.assertIn("EVIDENCE_CHAIN_LINK_MISMATCH:7", chain["blockers"])

    def test_raw_evidence_change_changes_record_digest(self):
        values = self.store()
        (
            plan,
            collector,
            collector_release,
            verifier,
            verifier_release,
            separation,
            receipt_template,
            store,
        ) = values
        requirement = PROBE_REQUIREMENTS[0]
        measurement = plan["measurements"][0]
        spec = PROBE_SPECS[requirement]
        kwargs = dict(
            store_contract=store,
            plan=plan,
            collector_manifest=collector,
            requirement=requirement,
            sequence=1,
            measurement_plan_digest=measurement["measurement_plan_digest"],
            evidence_payload_digest=H("payload"),
            collector_binary_digest=collector["collector_binary_digest"],
            collector_release_payload_digest=collector_release[
                "release_payload_digest"
            ],
            collector_signature_evidence_digest=H("signature"),
            observed_value=spec["expected_observation"],
            negative_test_observed_value=spec["negative_test"],
            collected_at="2026-10-08T15:31:00+00:00",
            valid_until="2026-10-08T15:32:00+00:00",
            previous_record_digest=store["evidence_chain_genesis_digest"],
            expected_pre_store_revision=0,
        )
        first = build_evidence_record_candidate(
            raw_evidence_digest=H("raw-a"),
            **kwargs,
        )
        second = build_evidence_record_candidate(
            raw_evidence_digest=H("raw-b"),
            **kwargs,
        )
        self.assertEqual(first["record_key"], second["record_key"])
        self.assertNotEqual(
            first["evidence_record_digest"],
            second["evidence_record_digest"],
        )

    def test_same_identity_same_digest_is_idempotent_but_changed_digest_conflicts(self):
        _, records = self.records()
        record = records[0]
        same = classify_append_replay(record, copy.deepcopy(record))
        self.assertEqual(same["state"], "IDEMPOTENT_REPLAY")
        self.assertTrue(same["idempotent_replay"])
        self.assertFalse(same["append_allowed"])
        self.assertFalse(same["conflict"])

        changed = copy.deepcopy(record)
        changed["evidence_record_digest"] = H("different-record")
        conflict = classify_append_replay(record, changed)
        self.assertEqual(conflict["state"], "BLOCKED")
        self.assertEqual(
            conflict["classification"],
            "SAME_IDENTITY_DIFFERENT_DIGEST_CONFLICT",
        )
        self.assertTrue(conflict["conflict"])
        self.assertFalse(conflict["append_allowed"])

    def test_receipt_persistence_contract_is_immutable_and_unissued(self):
        values, records = self.records()
        (
            plan,
            collector,
            collector_release,
            verifier,
            verifier_release,
            separation,
            receipt_template,
            store,
        ) = values
        chain = build_evidence_chain_candidate(store, records)
        contract = build_receipt_persistence_contract(
            store,
            chain,
            plan,
            verifier,
            separation,
            receipt_template,
        )
        self.assertEqual(
            contract["state"],
            READY_RECEIPT_PERSISTENCE_STATE,
            contract["blockers"],
        )
        self.assertTrue(contract["receipt_append_only"])
        self.assertTrue(contract["receipt_immutable"])
        self.assertTrue(contract["receipt_exactly_once"])
        self.assertTrue(contract["receipt_compare_and_set_required"])
        self.assertTrue(contract["receipt_read_after_write_required"])
        self.assertTrue(contract["receipt_reopen_consistency_required"])
        self.assertFalse(contract["receipt_delete_allowed"])
        self.assertFalse(contract["receipt_replace_allowed"])
        self.assertFalse(contract["receipt_rewrite_allowed"])
        self.assertFalse(contract["receipt_revision_increment_allowed"])
        self.assertFalse(contract["evidence_chain_mutation_after_receipt_allowed"])
        self.assertFalse(contract["receipt_issued"])
        self.assertFalse(contract["receipt_signed"])
        self.assertFalse(contract["receipt_persisted"])
        self.assertFalse(contract["physical_proof_verified"])
        self.assertFalse(contract["windows_sandbox_verified"])
        self.assertFalse(contract["build_authorized"])

    def test_receipt_contract_rejects_fake_issued_template(self):
        values, records = self.records()
        (
            plan,
            collector,
            collector_release,
            verifier,
            verifier_release,
            separation,
            receipt_template,
            store,
        ) = values
        chain = build_evidence_chain_candidate(store, records)
        fake = copy.deepcopy(receipt_template)
        fake["receipt_issued"] = True
        fake["verified_total"] = 12
        contract = build_receipt_persistence_contract(
            store,
            chain,
            plan,
            verifier,
            separation,
            fake,
        )
        self.assertEqual(contract["state"], "BLOCKED")
        self.assertIn("RECEIPT_MUST_REMAIN_UNISSUED", contract["blockers"])
        self.assertIn(
            "UNISSUED_RECEIPT_VERIFIED_TOTAL_MUST_BE_ZERO",
            contract["blockers"],
        )

    def test_persistence_attestation_shape_never_becomes_persistence_proof(self):
        *_, store = self.store()
        attestation = validate_future_persistence_attestation_shape(
            store,
            record_kind="EVIDENCE",
            record_key=H("record-key"),
            record_digest=H("record-digest"),
            expected_pre_store_revision=0,
            committed_store_revision=1,
            writer_manifest_digest=store["writer_manifest_digest"],
            write_receipt_digest=H("write-receipt"),
            cas_observation_digest=H("cas"),
            read_after_write_observation_digest=H("readback"),
            reopen_observation_digest=H("reopen"),
            persisted_at="2026-10-08T15:40:00+00:00",
        )
        self.assertEqual(
            attestation["state"],
            READY_ATTESTATION_SHAPE_STATE,
            attestation["blockers"],
        )
        self.assertTrue(attestation["shape_valid"])
        self.assertFalse(attestation["physical_persistence_verified"])
        self.assertFalse(attestation["cas_verified"])
        self.assertFalse(attestation["read_after_write_verified"])
        self.assertFalse(attestation["reopen_verified"])
        self.assertFalse(attestation["record_persisted_trusted"])
        self.assertFalse(attestation["build_authorized"])

    def test_self_asserted_persistence_verification_is_rejected(self):
        *_, store = self.store()
        attestation = validate_future_persistence_attestation_shape(
            store,
            record_kind="EVIDENCE",
            record_key=H("record-key"),
            record_digest=H("record-digest"),
            expected_pre_store_revision=0,
            committed_store_revision=1,
            writer_manifest_digest=store["writer_manifest_digest"],
            write_receipt_digest=H("write-receipt"),
            cas_observation_digest=H("cas"),
            read_after_write_observation_digest=H("readback"),
            reopen_observation_digest=H("reopen"),
            persisted_at="2026-10-08T15:40:00+00:00",
            caller_claims_persistence_verified=True,
        )
        self.assertEqual(attestation["state"], "BLOCKED")
        self.assertIn(
            "CALLER_PERSISTENCE_VERIFICATION_CLAIM_NOT_TRUSTED",
            attestation["blockers"],
        )
        self.assertFalse(attestation["physical_persistence_verified"])

    def test_wrong_writer_or_revision_transition_blocks_attestation(self):
        *_, store = self.store()
        wrong_writer = validate_future_persistence_attestation_shape(
            store,
            record_kind="EVIDENCE",
            record_key=H("record-key"),
            record_digest=H("record-digest"),
            expected_pre_store_revision=0,
            committed_store_revision=1,
            writer_manifest_digest=H("wrong-writer"),
            write_receipt_digest=H("write-receipt"),
            cas_observation_digest=H("cas"),
            read_after_write_observation_digest=H("readback"),
            reopen_observation_digest=H("reopen"),
            persisted_at="2026-10-08T15:40:00+00:00",
        )
        self.assertEqual(wrong_writer["state"], "BLOCKED")
        self.assertIn(
            "WRITER_MANIFEST_DIGEST_MISMATCH",
            wrong_writer["blockers"],
        )

        wrong_revision = validate_future_persistence_attestation_shape(
            store,
            record_kind="EVIDENCE",
            record_key=H("record-key"),
            record_digest=H("record-digest"),
            expected_pre_store_revision=2,
            committed_store_revision=4,
            writer_manifest_digest=store["writer_manifest_digest"],
            write_receipt_digest=H("write-receipt"),
            cas_observation_digest=H("cas"),
            read_after_write_observation_digest=H("readback"),
            reopen_observation_digest=H("reopen"),
            persisted_at="2026-10-08T15:40:00+00:00",
        )
        self.assertEqual(wrong_revision["state"], "BLOCKED")
        self.assertIn(
            "STORE_REVISION_TRANSITION_INVALID",
            wrong_revision["blockers"],
        )

    def test_implementation_review_stops_before_writer_execution(self):
        values, records = self.records()
        (
            plan,
            collector,
            collector_release,
            verifier,
            verifier_release,
            separation,
            receipt_template,
            store,
        ) = values
        chain = build_evidence_chain_candidate(store, records)
        receipt_contract = build_receipt_persistence_contract(
            store,
            chain,
            plan,
            verifier,
            separation,
            receipt_template,
        )
        review = build_implementation_review(
            store,
            receipt_contract,
            writer_source_digest=H("writer-source"),
            writer_test_digest=H("writer-tests"),
            reopen_verifier_design_digest=H("reopen-verifier-design"),
            crash_recovery_design_digest=H("crash-recovery-design"),
        )
        self.assertEqual(
            review["state"],
            READY_REVIEW_STATE,
            review["blockers"],
        )
        self.assertEqual(
            review["next_pc_phase"],
            "IMPLEMENT_APPEND_ONLY_EVIDENCE_WRITER_AND_REOPEN_VERIFIER_WITH_SYNTHETIC_DATA",
        )
        self.assertFalse(review["writer_implemented"])
        self.assertFalse(review["writer_executed"])
        self.assertFalse(review["database_opened"])
        self.assertFalse(review["evidence_persisted"])
        self.assertFalse(review["verification_receipt_persisted"])
        self.assertFalse(review["read_after_write_verified"])
        self.assertFalse(review["reopen_verified"])
        self.assertFalse(review["crash_recovery_verified"])
        self.assertFalse(review["physical_persistence_verified"])
        self.assertFalse(review["physical_proof_verified"])
        self.assertFalse(review["windows_sandbox_verified"])
        self.assertFalse(review["build_authorized"])
        self.assertFalse(review["build_started"])
        self.assertFalse(review["package_built"])
        self.assertFalse(review["package_installed"])

    def test_policy_is_strict_append_only_and_nonexecuting(self):
        policy = evidence_persistence_policy()
        self.assertEqual(policy["required_evidence_records"], 12)
        self.assertTrue(policy["append_only_required"])
        self.assertTrue(policy["compare_and_set_required"])
        self.assertTrue(policy["exactly_once_required"])
        self.assertTrue(policy["single_writer_commit_required"])
        self.assertTrue(policy["read_after_write_required"])
        self.assertTrue(policy["reopen_consistency_required"])
        self.assertTrue(policy["same_identity_same_digest_is_idempotent"])
        self.assertTrue(policy["same_identity_different_digest_is_conflict"])
        self.assertFalse(policy["evidence_delete_allowed"])
        self.assertFalse(policy["evidence_replace_allowed"])
        self.assertFalse(policy["evidence_reorder_allowed"])
        self.assertFalse(policy["chain_truncate_allowed"])
        self.assertFalse(policy["receipt_delete_allowed"])
        self.assertFalse(policy["receipt_replace_allowed"])
        self.assertFalse(policy["receipt_rewrite_allowed"])
        self.assertFalse(policy["receipt_revision_increment_allowed"])
        self.assertFalse(policy["evidence_chain_mutation_after_receipt_allowed"])
        self.assertFalse(policy["caller_persistence_verification_is_authority"])
        self.assertFalse(policy["document_digest_is_persistence_proof"])
        for field in (
            "store_opened",
            "database_opened",
            "transaction_started",
            "cas_attempted",
            "cas_succeeded",
            "writer_implemented",
            "writer_executed",
            "record_written",
            "evidence_persisted",
            "verification_receipt_issued",
            "verification_receipt_signed",
            "verification_receipt_persisted",
            "read_after_write_verified",
            "reopen_verified",
            "crash_recovery_verified",
            "physical_persistence_verified",
            "physical_proof_verified",
            "windows_sandbox_verified",
            "build_authorized",
            "build_started",
            "package_built",
            "package_installed",
            "process_spawned",
            "filesystem_modified",
            "network_called",
            "github_api_called",
            "live_repository_mutation_authorized",
            "live_repository_mutation_performed",
            "production_repository_mutation_performed",
            "deploy_executed",
            "worker_activated",
            "provider_activated",
            "production_persistence_activated",
        ):
            self.assertFalse(policy[field], field)


if __name__ == "__main__":
    unittest.main()
