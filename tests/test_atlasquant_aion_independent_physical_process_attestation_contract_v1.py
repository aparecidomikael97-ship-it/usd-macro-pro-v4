"""Adversarial tests for independent physical-process attestation contract."""
from __future__ import annotations

import base64
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from atlasquant_aion_independent_physical_process_attestation_contract_v1 import (
    ATTESTATION_SCHEMA,
    CANDIDATE,
    SQLitePhysicalAttestationReplayStore,
    attestation_signing_message,
    build_physical_process_challenge,
    challenge_digest,
    verify_independent_physical_process_attestation,
)
from atlasquant_aion_windows_sandbox_physical_probe_plan_evidence_v1 import (
    PROBE_REQUIREMENTS,
)


def pub(key: Ed25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def digest(raw: bytes) -> str:
    return "sha256:" + sha256(raw).hexdigest()


def b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


class IndependentPhysicalProcessAttestationTests(unittest.TestCase):
    def setUp(self):
        self.collector = Ed25519PrivateKey.generate()
        self.collector_public = pub(self.collector)
        self.collector_fingerprint = digest(self.collector_public)
        self.now = 1_800_100_000

    def challenge(self, **changes):
        values = {
            "challenge_nonce": "12" * 32,
            "owner_preflight_digest": digest(b"owner-rooted-binary-preflight"),
            "sandbox_preflight_digest": digest(b"sandbox-preflight"),
            "probe_plan_digest": digest(b"physical-probe-plan"),
            "host_binding_digest": digest(b"host-binding"),
            "collector_manifest_digest": digest(b"collector-manifest"),
            "collector_binary_digest": digest(b"collector-binary"),
            "collector_key_fingerprint": self.collector_fingerprint,
            "expected_image_path_digest": digest(b"normalized-pinned-image-path"),
            "expected_image_sha256": sha256(b"pinned-image-bytes").hexdigest(),
            "issued_at": self.now - 5,
            "expires_at": self.now + 90,
        }
        values.update(changes)
        return build_physical_process_challenge(**values)

    def requirement_evidence(self):
        rows = []
        for index, requirement in enumerate(PROBE_REQUIREMENTS, start=1):
            rows.append({
                "sequence": index,
                "requirement": requirement,
                "positive_evidence_digest": digest(
                    ("positive:" + requirement).encode("utf-8")
                ),
                "negative_evidence_digest": digest(
                    ("negative:" + requirement).encode("utf-8")
                ),
            })
        return rows

    def attestation(self, challenge=None, **changes):
        challenge = self.challenge() if challenge is None else challenge
        row = {
            "schema": ATTESTATION_SCHEMA,
            "challenge_digest": challenge_digest(challenge),
            "challenge_nonce": challenge["challenge_nonce"],
            "collector_key_fingerprint": challenge["collector_key_fingerprint"],
            "observed_image_path_digest": challenge["expected_image_path_digest"],
            "observed_image_sha256": challenge["expected_image_sha256"],
            "file_identity_digest": digest(b"volume-file-index-size-lastwrite"),
            "process_handle_provenance_digest": digest(
                b"held-process-handle-provenance"
            ),
            "token_evidence_digest": digest(b"token-readback"),
            "job_evidence_digest": digest(b"job-object-readback"),
            "requirement_evidence": self.requirement_evidence(),
            "raw_bundle_ref": "evidence://aion-physical/run-001",
            "raw_bundle_digest": digest(b"raw-evidence-bundle"),
            "collected_at": self.now - 2,
            "valid_until": self.now + 30,
        }
        row.update(changes)
        return row

    def signed(self, challenge=None, attestation=None, key=None):
        challenge = self.challenge() if challenge is None else challenge
        attestation = self.attestation(challenge) if attestation is None else attestation
        key = self.collector if key is None else key
        message = attestation_signing_message(
            attestation, challenge=challenge, now=self.now
        )
        return b64(key.sign(message))

    def call(
        self,
        tempdir,
        *,
        challenge=None,
        attestation=None,
        signature=None,
        public_key=None,
        fingerprint=None,
        replay_store="default",
        now=None,
    ):
        challenge = self.challenge() if challenge is None else challenge
        attestation = self.attestation(challenge) if attestation is None else attestation
        signature = (
            self.signed(challenge, attestation)
            if signature is None else signature
        )
        public_key = self.collector_public if public_key is None else public_key
        fingerprint = (
            self.collector_fingerprint if fingerprint is None else fingerprint
        )
        if replay_store == "default":
            replay_store = SQLitePhysicalAttestationReplayStore(
                Path(tempdir) / "physical-attestation-replay.sqlite3"
            )
        return verify_independent_physical_process_attestation(
            challenge,
            attestation,
            signature,
            pinned_collector_public_key=public_key,
            expected_collector_key_fingerprint=fingerprint,
            now=self.now if now is None else now,
            replay_store=replay_store,
        )

    def assert_no_physical_authority(self, result):
        for field in (
            "collector_key_enrolled_in_production",
            "collector_binary_independently_trusted",
            "raw_evidence_independently_reviewed",
            "physical_probe_executed",
            "physical_attestation_verified",
            "windows_sandbox_verified",
            "network_deny_verified",
            "safe_to_resume",
            "installer_authorized",
            "build_authorized",
            "deploy_authorized",
        ):
            self.assertIs(result[field], False, field)

    def test_signed_candidate_binds_all_12_requirements_without_authority(self):
        self.assertEqual(len(PROBE_REQUIREMENTS), 12)
        with tempfile.TemporaryDirectory() as td:
            result = self.call(td)
        self.assertEqual(result["state"], CANDIDATE, result)
        self.assertEqual(result["requirement_count"], 12)
        for field in (
            "challenge_bound",
            "collector_signature_cryptographically_valid",
            "collector_key_pinned",
            "image_identity_bound",
            "canonical_12_requirements_bound",
            "positive_negative_evidence_bound",
            "challenge_replay_consumed",
        ):
            self.assertIs(result[field], True, field)
        self.assert_no_physical_authority(result)

    def test_same_challenge_replay_is_rejected(self):
        challenge = self.challenge()
        attestation = self.attestation(challenge)
        signature = self.signed(challenge, attestation)
        with tempfile.TemporaryDirectory() as td:
            store = SQLitePhysicalAttestationReplayStore(Path(td) / "r.sqlite3")
            first = self.call(
                td,
                challenge=challenge,
                attestation=attestation,
                signature=signature,
                replay_store=store,
            )
            second = self.call(
                td,
                challenge=challenge,
                attestation=attestation,
                signature=signature,
                replay_store=store,
            )
        self.assertEqual(first["state"], CANDIDATE)
        self.assertEqual(second["reason"], "CHALLENGE_REPLAY_OR_STORE_FAILURE")
        self.assert_no_physical_authority(second)

    def test_replay_rejected_after_database_reopen(self):
        challenge = self.challenge()
        attestation = self.attestation(challenge)
        signature = self.signed(challenge, attestation)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "r.sqlite3"
            first = self.call(
                td, challenge=challenge, attestation=attestation,
                signature=signature,
                replay_store=SQLitePhysicalAttestationReplayStore(path),
            )
            second = self.call(
                td, challenge=challenge, attestation=attestation,
                signature=signature,
                replay_store=SQLitePhysicalAttestationReplayStore(path),
            )
        self.assertEqual(first["state"], CANDIDATE)
        self.assertEqual(second["reason"], "CHALLENGE_REPLAY_OR_STORE_FAILURE")

    def test_attacker_self_signed_collector_key_is_rejected(self):
        attacker = Ed25519PrivateKey.generate()
        challenge = self.challenge()
        attestation = self.attestation(challenge)
        signature = self.signed(challenge, attestation, key=attacker)
        with tempfile.TemporaryDirectory() as td:
            result = self.call(
                td, challenge=challenge, attestation=attestation,
                signature=signature,
            )
        self.assertEqual(result["reason"], "COLLECTOR_SIGNATURE_INVALID")
        self.assertEqual(result["state"], "BLOCKED")
        self.assert_no_physical_authority(result)

    def test_unpinned_collector_public_key_is_rejected(self):
        attacker = Ed25519PrivateKey.generate()
        with tempfile.TemporaryDirectory() as td:
            result = self.call(td, public_key=pub(attacker))
        self.assertEqual(result["reason"], "UNPINNED_COLLECTOR_KEY")

    def test_wrong_expected_collector_fingerprint_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            result = self.call(td, fingerprint=digest(b"other-collector"))
        self.assertEqual(result["reason"], "COLLECTOR_FINGERPRINT_CHALLENGE_MISMATCH")

    def test_signature_bitflip_is_rejected(self):
        challenge = self.challenge()
        attestation = self.attestation(challenge)
        raw = bytearray(base64.b64decode(self.signed(challenge, attestation)))
        raw[0] ^= 1
        signature = base64.b64encode(bytes(raw)).decode("ascii")
        with tempfile.TemporaryDirectory() as td:
            result = self.call(
                td, challenge=challenge, attestation=attestation,
                signature=signature,
            )
        self.assertEqual(result["state"], "BLOCKED")
        self.assert_no_physical_authority(result)

    def test_challenge_change_breaks_existing_attestation_binding(self):
        original = self.challenge()
        attestation = self.attestation(original)
        signature = self.signed(original, attestation)
        changed = self.challenge(
            collector_binary_digest=digest(b"other-collector-binary")
        )
        with tempfile.TemporaryDirectory() as td:
            result = self.call(
                td, challenge=changed, attestation=attestation,
                signature=signature,
            )
        self.assertEqual(result["reason"], "CHALLENGE_DIGEST_MISMATCH")

    def test_observed_image_path_digest_must_match_challenge(self):
        challenge = self.challenge()
        attestation = self.attestation(
            challenge,
            observed_image_path_digest=digest(b"other-path"),
        )
        with tempfile.TemporaryDirectory() as td:
            result = self.call(
                td, challenge=challenge, attestation=attestation,
                signature=b64(b"x" * 64),
            )
        self.assertEqual(result["reason"], "OBSERVED_IMAGE_PATH_MISMATCH")

    def test_observed_image_sha_must_match_challenge(self):
        challenge = self.challenge()
        attestation = self.attestation(
            challenge,
            observed_image_sha256="0" * 64,
        )
        with tempfile.TemporaryDirectory() as td:
            result = self.call(
                td, challenge=challenge, attestation=attestation,
                signature=b64(b"x" * 64),
            )
        self.assertEqual(result["reason"], "OBSERVED_IMAGE_SHA256_MISMATCH")

    def test_missing_requirement_is_rejected(self):
        challenge = self.challenge()
        evidence = self.requirement_evidence()[:-1]
        attestation = self.attestation(
            challenge,
            requirement_evidence=evidence,
        )
        with self.assertRaises(ValueError):
            self.signed(challenge, attestation)

    def test_requirement_reordering_is_rejected(self):
        challenge = self.challenge()
        evidence = self.requirement_evidence()
        evidence[0], evidence[1] = evidence[1], evidence[0]
        attestation = self.attestation(
            challenge,
            requirement_evidence=evidence,
        )
        with self.assertRaises(ValueError):
            self.signed(challenge, attestation)

    def test_positive_and_negative_evidence_cannot_be_same_digest(self):
        challenge = self.challenge()
        evidence = self.requirement_evidence()
        evidence[0]["negative_evidence_digest"] = evidence[0]["positive_evidence_digest"]
        attestation = self.attestation(
            challenge,
            requirement_evidence=evidence,
        )
        with self.assertRaises(ValueError):
            self.signed(challenge, attestation)

    def test_all_canonical_requirement_names_are_bound(self):
        challenge = self.challenge()
        attestation = self.attestation(challenge)
        actual = [row["requirement"] for row in attestation["requirement_evidence"]]
        self.assertEqual(actual, list(PROBE_REQUIREMENTS))
        self.assertIn("WINDOWS_NETWORK_DENY_PHYSICAL_PROOF_REQUIRED", actual)

    def test_extra_self_attestation_boolean_is_rejected(self):
        challenge = self.challenge()
        attestation = self.attestation(challenge)
        attestation["physical_attestation_verified"] = True
        with self.assertRaises(ValueError):
            self.signed(challenge, attestation)

    def test_attestation_window_over_60_seconds_is_rejected(self):
        challenge = self.challenge()
        attestation = self.attestation(
            challenge,
            collected_at=self.now - 1,
            valid_until=self.now + 60,
        )
        with self.assertRaises(ValueError):
            self.signed(challenge, attestation)

    def test_attestation_outside_challenge_window_is_rejected(self):
        challenge = self.challenge(expires_at=self.now + 20)
        attestation = self.attestation(
            challenge,
            collected_at=self.now - 1,
            valid_until=self.now + 30,
        )
        with self.assertRaises(ValueError):
            self.signed(challenge, attestation)

    def test_expired_attestation_is_rejected(self):
        challenge = self.challenge()
        attestation = self.attestation(
            challenge,
            collected_at=self.now - 40,
            valid_until=self.now - 1,
        )
        with tempfile.TemporaryDirectory() as td:
            result = self.call(
                td,
                challenge=challenge,
                attestation=attestation,
                signature="AA==",
            )
        self.assertEqual(result["reason"], "ATTESTATION_WINDOW_INVALID")

    def test_invalid_raw_bundle_reference_is_rejected(self):
        challenge = self.challenge()
        attestation = self.attestation(challenge, raw_bundle_ref="contains spaces")
        with self.assertRaises(ValueError):
            self.signed(challenge, attestation)

    def test_missing_replay_store_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            result = self.call(td, replay_store=None)
        self.assertEqual(result["reason"], "DURABLE_CHALLENGE_REPLAY_STORE_REQUIRED")
        self.assert_no_physical_authority(result)

    def test_memory_and_uri_replay_databases_are_forbidden(self):
        for value in (":memory:", "file:volatile?mode=memory&cache=shared", ""):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    SQLitePhysicalAttestationReplayStore(value)

    def test_challenge_rejects_fake_authority_fields(self):
        challenge = self.challenge()
        attestation = self.attestation(challenge)
        mutated = deepcopy(challenge)
        mutated["installer_authorized"] = True
        with tempfile.TemporaryDirectory() as td:
            result = self.call(
                td, challenge=mutated, attestation=attestation,
                signature=b64(b"x" * 64),
            )
        self.assertEqual(result["reason"], "TRUSTED_CHALLENGE_INVALID")
        self.assert_no_physical_authority(result)


if __name__ == "__main__":
    unittest.main()
