"""Adversarial collector root + signed raw-byte evidence tests (CI only)."""
from __future__ import annotations

import base64
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from atlasquant_aion_rooted_collector_raw_evidence_preflight_v1 import (
    ENROLL_SCHEMA, ENROLL_PURPOSE, RAW_SCHEMA, CANDIDATE,
    enrollment_signing_message, SQLiteCollectorChallengeReplay,
    verify_rooted_collector_raw_evidence,
)
from atlasquant_aion_independent_physical_process_attestation_contract_v1 import (
    ATTESTATION_SCHEMA, build_physical_process_challenge,
    challenge_digest, attestation_signing_message,
)
from atlasquant_aion_windows_sandbox_physical_probe_plan_evidence_v1 import PROBE_REQUIREMENTS


def canonical(data):
    return json.dumps(data, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def b64(data):
    return base64.b64encode(data).decode("ascii")


def public(key):
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)


def digest(data):
    return "sha256:" + sha256(data).hexdigest()


class CollectorRawEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.now = 1_800_200_000
        self.root = Ed25519PrivateKey.generate()
        self.collector = Ed25519PrivateKey.generate()
        self.host_binding = digest(b"synthetic-independent-host")
        self.device_binding = digest(b"synthetic-device-binding")
        self.collector_binary = digest(b"collector-image")
        self.collector_manifest = digest(b"collector-signed-manifest")

    def registry(self, **overrides):
        row = {
            "schema": ENROLL_SCHEMA,
            "purpose": ENROLL_PURPOSE,
            "registry_id": "aion-owner-host-registry",
            "host_issuer": "atlasquant-owner-host",
            "host_binding_digest": self.host_binding,
            "device_binding_digest": self.device_binding,
            "epoch": 4,
            "issued_at": self.now - 20,
            "expires_at": self.now + 300,
            "collector": {
                "collector_id": "aion-physical-collector",
                "key_id": "ephemeral-collector-key-4",
                "public_key_b64": b64(public(self.collector)),
                "binary_digest": self.collector_binary,
                "manifest_digest": self.collector_manifest,
                "enrolled_epoch": 4,
                "revoked_epoch": None,
            },
        }
        row.update(overrides)
        return row

    def signed_registry(self, row=None, *, signing_key=None):
        row = self.registry() if row is None else row
        key = self.root if signing_key is None else signing_key
        return canonical(row), b64(key.sign(enrollment_signing_message(row)))

    def challenge(self, **overrides):
        fields = {
            "challenge_nonce": "ac" * 32,
            "owner_preflight_digest": digest(b"rooted-owner-preflight"),
            "sandbox_preflight_digest": digest(b"sandbox-contract"),
            "probe_plan_digest": digest(b"exact-probe-plan"),
            "host_binding_digest": self.host_binding,
            "collector_manifest_digest": self.collector_manifest,
            "collector_binary_digest": self.collector_binary,
            "collector_key_fingerprint": digest(public(self.collector)),
            "expected_image_path_digest": digest(b"image-path"),
            "expected_image_sha256": sha256(b"image").hexdigest(),
            "issued_at": self.now - 3,
            "expires_at": self.now + 75,
        }
        fields.update(overrides)
        return build_physical_process_challenge(**fields)

    def bundle_and_attestation(self, challenge=None, *, entries=None):
        challenge = self.challenge() if challenge is None else challenge
        if entries is None:
            entries = [{
                "sequence": index,
                "requirement": req,
                "positive_evidence_b64": b64(("POS-" + req).encode()),
                "negative_evidence_b64": b64(("NEG-" + req).encode()),
            } for index, req in enumerate(PROBE_REQUIREMENTS, start=1)]
        bundle = {
            "schema": RAW_SCHEMA,
            "challenge_digest": challenge_digest(challenge),
            "entries": entries,
        }
        raw = canonical(bundle)
        signed_entries = [{
            "sequence": item["sequence"], "requirement": item["requirement"],
            "positive_evidence_digest": digest(base64.b64decode(item["positive_evidence_b64"])),
            "negative_evidence_digest": digest(base64.b64decode(item["negative_evidence_b64"])),
        } for item in entries]
        attestation = {
            "schema": ATTESTATION_SCHEMA,
            "challenge_digest": challenge_digest(challenge),
            "challenge_nonce": challenge["challenge_nonce"],
            "collector_key_fingerprint": challenge["collector_key_fingerprint"],
            "observed_image_path_digest": challenge["expected_image_path_digest"],
            "observed_image_sha256": challenge["expected_image_sha256"],
            "file_identity_digest": digest(b"file-info"),
            "process_handle_provenance_digest": digest(b"held-process"),
            "token_evidence_digest": digest(b"token"),
            "job_evidence_digest": digest(b"job"),
            "requirement_evidence": signed_entries,
            "raw_bundle_ref": "fixture://synthetic-raw-evidence-only",
            "raw_bundle_digest": digest(raw),
            "collected_at": self.now - 1,
            "valid_until": self.now + 30,
        }
        return raw, attestation

    def signed_attestation(self, challenge, attestation, key=None):
        key = self.collector if key is None else key
        return b64(key.sign(attestation_signing_message(
            attestation, challenge=challenge, now=self.now)))

    def invoke(self, td, *, record=None, record_raw=None, record_sig=None,
               challenge=None, attestation=None, raw=None, attestation_sig=None,
               root=None, root_fingerprint=None, host_binding=None,
               device_binding=None, minimum_epoch=4, now=None, store="auto"):
        if record_raw is None or record_sig is None:
            r, s = self.signed_registry(record)
            record_raw = r if record_raw is None else record_raw
            record_sig = s if record_sig is None else record_sig
        challenge = self.challenge() if challenge is None else challenge
        if raw is None or attestation is None:
            default_raw, default_attestation = self.bundle_and_attestation(challenge)
            raw = default_raw if raw is None else raw
            attestation = default_attestation if attestation is None else attestation
        if attestation_sig is None:
            attestation_sig = self.signed_attestation(challenge, attestation)
        root = public(self.root) if root is None else root
        root_fingerprint = digest(root) if root_fingerprint is None else root_fingerprint
        if store == "auto":
            store = SQLiteCollectorChallengeReplay(Path(td) / "nonces.sqlite3")
        return verify_rooted_collector_raw_evidence(
            record_raw, record_sig, challenge, attestation,
            attestation_sig, raw,
            pinned_enrollment_root_public_key=root,
            expected_root_fingerprint=root_fingerprint,
            expected_registry_id="aion-owner-host-registry",
            expected_host_issuer="atlasquant-owner-host",
            expected_host_binding_digest=host_binding or self.host_binding,
            expected_device_binding_digest=device_binding or self.device_binding,
            expected_collector_id="aion-physical-collector",
            minimum_enrollment_epoch=minimum_epoch,
            now=self.now if now is None else now,
            replay_store=store,
        )

    def no_authority(self, result):
        for name in ("root_enrolled_in_production", "collector_enrolled_in_production",
                     "raw_evidence_independently_observed",
                     "physical_attestation_verified", "network_deny_verified",
                     "safe_to_resume", "installer_authorized",
                     "build_authorized", "deploy_authorized"):
            self.assertIs(result[name], False, name)

    def test_rooted_raw_candidate_but_no_physical_authority(self):
        with tempfile.TemporaryDirectory() as td:
            r = self.invoke(td)
        self.assertEqual(r["state"], CANDIDATE, r)
        self.assertEqual(r["requirement_count"], 12)
        for name in ("enrollment_root_signature_valid",
                     "collector_key_resolved_from_registry",
                     "raw_bundle_bytes_bound",
                     "signed_positive_negative_bytes_bound",
                     "single_use_challenge_consumed"):
            self.assertIs(r[name], True, name)
        self.no_authority(r)

    def test_same_challenge_nonce_rejected_after_store_reopen(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "nonces.sqlite3"
            first = self.invoke(td, store=SQLiteCollectorChallengeReplay(p))
            second = self.invoke(td, store=SQLiteCollectorChallengeReplay(p))
        self.assertEqual(first["state"], CANDIDATE)
        self.assertEqual(second["reason"], "NONCE_REPLAY_OR_STORE_FAILURE")
        self.no_authority(second)

    def test_same_nonce_different_signed_challenge_still_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "nonces.sqlite3"
            first = self.invoke(td, store=SQLiteCollectorChallengeReplay(p))
            different = self.challenge(
                expected_image_path_digest=digest(b"other-allowed-path"))
            raw, att = self.bundle_and_attestation(different)
            second = self.invoke(
                td, challenge=different, raw=raw, attestation=att,
                store=SQLiteCollectorChallengeReplay(p))
        self.assertEqual(first["state"], CANDIDATE)
        self.assertEqual(second["reason"], "NONCE_REPLAY_OR_STORE_FAILURE")

    def test_invalid_registration_root_cannot_be_self_substituted(self):
        attacker = Ed25519PrivateKey.generate()
        rr, sig = self.signed_registry(signing_key=attacker)
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, record_raw=rr, record_sig=sig)
        self.assertEqual(result["reason"], "ENROLLMENT_ROOT_SIGNATURE_INVALID")

    def test_wrong_root_public_key_rejected(self):
        attacker = Ed25519PrivateKey.generate()
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, root=public(attacker))
        self.assertEqual(result["reason"], "ENROLLMENT_ROOT_SIGNATURE_INVALID")

    def test_unpinned_root_fingerprint_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, root_fingerprint=digest(b"not-our-root"))
        self.assertEqual(result["reason"], "ENROLLMENT_ROOT_NOT_PINNED")

    def test_revoke_collector_is_fail_closed(self):
        row = self.registry()
        row["collector"]["revoked_epoch"] = 4
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, record=row)
        self.assertEqual(result["reason"], "COLLECTOR_REVOKED")

    def test_old_enrollment_epoch_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, minimum_epoch=5)
        self.assertEqual(result["reason"], "ENROLLMENT_ROLLBACK")

    def test_wrong_host_binding_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, host_binding=digest(b"another-host"))
        self.assertEqual(result["reason"], "ENROLLMENT_HOST_OR_DEVICE_MISMATCH")

    def test_wrong_device_binding_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, device_binding=digest(b"another-device"))
        self.assertEqual(result["reason"], "ENROLLMENT_HOST_OR_DEVICE_MISMATCH")

    def test_challenge_binds_enrolled_binary_digest(self):
        ch = self.challenge(collector_binary_digest=digest(b"different-binary"))
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, challenge=ch)
        self.assertEqual(result["reason"], "CHALLENGE_NOT_BOUND_TO_ENROLLED_COLLECTOR")

    def test_challenge_binds_enrolled_manifest_digest(self):
        ch = self.challenge(collector_manifest_digest=digest(b"different-manifest"))
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, challenge=ch)
        self.assertEqual(result["reason"], "CHALLENGE_NOT_BOUND_TO_ENROLLED_COLLECTOR")

    def test_attacker_collector_signature_rejected(self):
        ch = self.challenge()
        raw, att = self.bundle_and_attestation(ch)
        signature = self.signed_attestation(ch, att, key=Ed25519PrivateKey.generate())
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, challenge=ch, raw=raw, attestation=att,
                                 attestation_sig=signature)
        self.assertEqual(result["reason"], "COLLECTOR_SIGNATURE_INVALID")

    def test_raw_bytes_tampered_after_signing_rejected(self):
        ch = self.challenge()
        raw, att = self.bundle_and_attestation(ch)
        edited = raw.replace(b"POS-", b"FAKE", 1)
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, raw=edited, attestation=att)
        self.assertEqual(result["reason"], "RAW_BUNDLE_SHA256_MISMATCH")

    def test_raw_entry_tamper_even_with_recomputed_bundle_digest_is_rejected(self):
        ch = self.challenge()
        raw, att = self.bundle_and_attestation(ch)
        bundle = json.loads(raw)
        bundle["entries"][0]["positive_evidence_b64"] = b64(b"modified raw evidence")
        edited = canonical(bundle)
        att["raw_bundle_digest"] = digest(edited)
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, raw=edited, attestation=att)
        self.assertEqual(result["reason"], "ATTESTATION_OR_RAW_EVIDENCE_INVALID")

    def test_duplicate_json_properties_rejected(self):
        ch = self.challenge()
        raw, att = self.bundle_and_attestation(ch)
        duplicate = raw.replace(b'"schema":', b'"schema":"fake","schema":', 1)
        att["raw_bundle_digest"] = digest(duplicate)
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, raw=duplicate, attestation=att)
        self.assertEqual(result["reason"], "ATTESTATION_OR_RAW_EVIDENCE_INVALID")

    def test_reordered_requirements_rejected(self):
        ch = self.challenge()
        raw, att = self.bundle_and_attestation(ch)
        bundle = json.loads(raw)
        bundle["entries"][0], bundle["entries"][1] = bundle["entries"][1], bundle["entries"][0]
        edited = canonical(bundle)
        att["raw_bundle_digest"] = digest(edited)
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, raw=edited, attestation=att)
        self.assertEqual(result["reason"], "ATTESTATION_OR_RAW_EVIDENCE_INVALID")

    def test_missing_evidence_item_rejected(self):
        ch = self.challenge()
        raw, att = self.bundle_and_attestation(ch)
        bundle = json.loads(raw)
        bundle["entries"].pop()
        edited = canonical(bundle)
        att["raw_bundle_digest"] = digest(edited)
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, raw=edited, attestation=att)
        self.assertEqual(result["reason"], "ATTESTATION_OR_RAW_EVIDENCE_INVALID")

    def test_same_positive_negative_bytes_rejected(self):
        ch = self.challenge()
        raw, att = self.bundle_and_attestation(ch)
        bundle = json.loads(raw)
        bundle["entries"][0]["negative_evidence_b64"] = bundle["entries"][0]["positive_evidence_b64"]
        edited = canonical(bundle)
        att["raw_bundle_digest"] = digest(edited)
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, raw=edited, attestation=att)
        self.assertEqual(result["reason"], "ATTESTATION_OR_RAW_EVIDENCE_INVALID")

    def test_fake_authority_json_field_rejected(self):
        ch = self.challenge()
        raw, att = self.bundle_and_attestation(ch)
        bundle = json.loads(raw)
        bundle["physical_attestation_verified"] = True
        edited = canonical(bundle)
        att["raw_bundle_digest"] = digest(edited)
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, raw=edited, attestation=att)
        self.assertEqual(result["reason"], "ATTESTATION_OR_RAW_EVIDENCE_INVALID")

    def test_missing_replay_store_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, store=None)
        self.assertEqual(result["reason"], "DURABLE_NONCE_STORE_REQUIRED")

    def test_expired_registry_rejected(self):
        row = self.registry(expires_at=self.now - 1)
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, record=row)
        self.assertEqual(result["reason"], "ENROLLMENT_NOT_CURRENT")

    def test_missing_extra_registry_fields_rejected(self):
        row = self.registry()
        row["signed_by_owner"] = True
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, record_raw=canonical(row),
                                 record_sig=b64(b"x" * 64))
        self.assertEqual(result["reason"], "ENROLLMENT_SNAPSHOT_MALFORMED")

    def test_memory_and_uri_sqlite_storage_disallowed(self):
        for path in (":memory:", "", "file:memory?mode=memory"):
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    SQLiteCollectorChallengeReplay(path)

    def test_null_and_oversized_raw_bundle_fail_closed(self):
        ch = self.challenge()
        _, att = self.bundle_and_attestation(ch)
        raw_reg, root_sig = self.signed_registry()
        sig = self.signed_attestation(ch, att)
        with tempfile.TemporaryDirectory() as td:
            for raw in (None, b"x" * 131073):
                with self.subTest(size=len(raw) if raw else None):
                    result = verify_rooted_collector_raw_evidence(
                        raw_reg, root_sig, ch, att, sig, raw,
                        pinned_enrollment_root_public_key=public(self.root),
                        expected_root_fingerprint=digest(public(self.root)),
                        expected_registry_id="aion-owner-host-registry",
                        expected_host_issuer="atlasquant-owner-host",
                        expected_host_binding_digest=self.host_binding,
                        expected_device_binding_digest=self.device_binding,
                        expected_collector_id="aion-physical-collector",
                        minimum_enrollment_epoch=4, now=self.now,
                        replay_store=SQLiteCollectorChallengeReplay(
                            Path(td) / "invalid-nonces.sqlite3"),
                    )
                    self.assertEqual(result["state"], "BLOCKED")
                    self.no_authority(result)

    def test_bad_signature_does_not_burn_nonce(self):
        ch = self.challenge()
        raw, att = self.bundle_and_attestation(ch)
        bad_signature = b64(b"x" * 64)
        with tempfile.TemporaryDirectory() as td:
            store = SQLiteCollectorChallengeReplay(Path(td) / "r.sqlite3")
            bad = self.invoke(td, challenge=ch, raw=raw, attestation=att,
                              attestation_sig=bad_signature, store=store)
            good = self.invoke(td, challenge=ch, raw=raw, attestation=att, store=store)
        self.assertEqual(bad["reason"], "COLLECTOR_SIGNATURE_INVALID")
        self.assertEqual(good["state"], CANDIDATE)


if __name__ == "__main__":
    unittest.main()
