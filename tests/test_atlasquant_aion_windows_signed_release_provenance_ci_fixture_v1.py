"""AION synthetic release provenance V1: 45 adversarial Ed25519 tests.

Keys are ephemeral, in-process, and never exported to disk or accepted as
real publisher identities. Artifacts are inert byte strings, never executed.
"""
import copy
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from atlasquant_aion_windows_signed_release_provenance_ci_fixture_v1 import (
    SCHEMA, SCOPE, KEY_SOURCE, BLOCKED, RELEASE_READY, HANDOFF_READY,
    FILE_KEYS, MANIFEST_KEYS, EXPECTED_KEYS, MAX_FILE_BYTES, MAX_FILES,
    _bytes_digest, _canonical_bytes, _digest,
    verify_ci_detached_release, build_ci_release_handoff_plan,
    provenance_policy,
)

D = lambda c: "sha256:" + c * 64

class AIONWindowsSignedReleaseProvenanceCIFixtureV1Tests(unittest.TestCase):
    def setUp(self):
        self.private = Ed25519PrivateKey.generate()
        self.public = self.private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.artifacts = {
            "bin/aion-ci-simulated.exe": b"MZ" + b"INERT_CI_BYTES" * 7,
            "config/manifest-fixture.json": b'{"fixture_only":true}',
        }
        self.manifest = self.make_manifest()
        self.expected = self.make_expected(self.manifest)

    def make_manifest(self):
        files = [{
            "path": path,
            "size_bytes": len(raw),
            "sha256": _bytes_digest(raw),
        } for path, raw in sorted(self.artifacts.items())]
        return {
            "schema": SCHEMA,
            "scope": SCOPE,
            "release_id": "ci-aion-demo-0001",
            "version": "0.1.0-ci.17",
            "source_commit": "a" * 40,
            "build_workflow_digest": D("1"),
            "build_run_id": "778899",
            "build_environment_digest": D("2"),
            "ci_signer_public_key_sha256": _bytes_digest(self.public),
            "publisher_policy_digest": D("3"),
            "release_challenge_digest": D("4"),
            "files": files,
            "key_source": KEY_SOURCE,
            "publisher_identity_authorized": False,
            "build_provenance_independently_attested": False,
            "owner_install_authorization_present": False,
        }

    def make_expected(self, m):
        return {
            **{k: m[k] for k in EXPECTED_KEYS if k != "file_table_digest"},
            "file_table_digest": _digest(m["files"]),
        }

    def verify(self, manifest=None, artifacts=None, public=None, signature=None,
               expected=None, resign=True):
        m = self.manifest if manifest is None else manifest
        a = self.artifacts if artifacts is None else artifacts
        pub = self.public if public is None else public
        sig = (self.private.sign(_canonical_bytes(m)) if resign else bytes(64)) if signature is None else signature
        e = self.expected if expected is None else expected
        return verify_ci_detached_release(m, a, pub, sig, expected=e)

    def deny(self, r, code=None):
        self.assertEqual(r["state"], BLOCKED, r)
        self.assertFalse(r["aion_release_approved"])
        self.assertFalse(r["aion_package_installed"])
        if code:
            self.assertIn(code, r["blockers"])

    def handoff(self, v=None, **overrides):
        args = {
            "expected_installation_binding_digest": D("a"),
            "approved_publisher_registry_digest": D("b"),
            "independent_build_attestor_manifest_digest": D("c"),
            "package_ingest_policy_digest": D("d"),
            "owner_review_policy_digest": D("e"),
        }
        args.update(overrides)
        return build_ci_release_handoff_plan(self.verify() if v is None else v, **args)

    def test_valid_ephemeral_ed25519_and_manifest_only_crypto(self):
        r = self.verify()
        self.assertEqual(r["state"], RELEASE_READY, r)
        self.assertTrue(r["signature_verified_with_supplied_ci_key"])
        self.assertTrue(r["artifact_bytes_match_manifest_ci_only"])
        self.assertTrue(r["ci_key_ephemeral_untrusted"])
        for key in ("signed_by_authorized_aion_publisher",
                    "trusted_source_commit_attested", "slsa_build_provenance_trusted",
                    "reproducible_build_verified",
                    "certificate_chain_and_revocation_trusted",
                    "aion_release_approved", "aion_package_installed",
                    "install_token_consumed", "deploy_executed", "worker_activated"):
            self.assertFalse(r[key], key)

    def test_artifact_byte_tamper_is_detected(self):
        a = dict(self.artifacts)
        a["bin/aion-ci-simulated.exe"] += b"X"
        self.deny(self.verify(artifacts=a), "ARTIFACT_READBACK_DIGEST_MISMATCH:bin/aion-ci-simulated.exe")

    def test_artifact_same_size_byte_flip_detected(self):
        a = dict(self.artifacts)
        raw = bytearray(a["bin/aion-ci-simulated.exe"])
        raw[6] ^= 1
        a["bin/aion-ci-simulated.exe"] = bytes(raw)
        self.deny(self.verify(artifacts=a), "ARTIFACT_READBACK_DIGEST_MISMATCH:bin/aion-ci-simulated.exe")

    def test_detached_signature_from_wrong_key_fails(self):
        other = Ed25519PrivateKey.generate()
        self.deny(self.verify(signature=other.sign(_canonical_bytes(self.manifest))), "DETACHED_SIGNATURE_INVALID")

    def test_signed_manifest_modified_after_signature_fails(self):
        s = self.private.sign(_canonical_bytes(self.manifest))
        m = copy.deepcopy(self.manifest)
        m["version"] = "0.1.0-ci.18"
        expected = self.make_expected(m)
        self.deny(self.verify(manifest=m, signature=s, expected=expected), "DETACHED_SIGNATURE_INVALID")

    def test_signature_zero_bytes_fails(self):
        self.deny(self.verify(signature=bytes(64)), "DETACHED_SIGNATURE_INVALID")

    def test_wrong_public_key_digest_fails(self):
        other = Ed25519PrivateKey.generate()
        pub = other.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.deny(self.verify(public=pub), "PUBLIC_KEY_DIGEST_MISMATCH")

    def test_short_public_key_fails(self):
        self.deny(self.verify(public=b"x" * 31), "ED25519_PUBLIC_KEY_LENGTH_INVALID")

    def test_short_signature_fails(self):
        self.deny(self.verify(signature=b"x" * 63), "ED25519_SIGNATURE_LENGTH_INVALID")

    def test_missing_artifact_rejected(self):
        a = dict(self.artifacts)
        del a["bin/aion-ci-simulated.exe"]
        self.deny(self.verify(artifacts=a), "MISSING_OR_UNDECLARED_ARTIFACT")

    def test_unlisted_artifact_rejected(self):
        a = dict(self.artifacts)
        a["bin/extra.dll"] = b"surprise"
        self.deny(self.verify(artifacts=a), "MISSING_OR_UNDECLARED_ARTIFACT")

    def test_unsorted_manifest_paths_rejected(self):
        m = copy.deepcopy(self.manifest)
        m["files"].reverse()
        self.deny(self.verify(manifest=m, expected=self.make_expected(m)), "ARTIFACT_ORDER_OR_CASE_COLLISION")

    def test_windows_parent_traversal_rejected(self):
        m = copy.deepcopy(self.manifest)
        m["files"][0]["path"] = "../evil.exe"
        self.deny(self.verify(manifest=m, expected=self.make_expected(m)), "WINDOWS_ARTIFACT_PATH_UNSAFE:0")

    def test_windows_backslash_traversal_rejected(self):
        m = copy.deepcopy(self.manifest)
        m["files"][0]["path"] = r"..\evil.exe"
        self.deny(self.verify(manifest=m, expected=self.make_expected(m)), "WINDOWS_ARTIFACT_PATH_UNSAFE:0")

    def test_windows_reserved_device_filename_rejected(self):
        m = copy.deepcopy(self.manifest)
        m["files"][0]["path"] = "bin/con.txt"
        self.deny(self.verify(manifest=m, expected=self.make_expected(m)), "WINDOWS_ARTIFACT_PATH_UNSAFE:0")

    def test_absolute_path_rejected(self):
        m = copy.deepcopy(self.manifest)
        m["files"][0]["path"] = "/windows/system32/aion.exe"
        self.deny(self.verify(manifest=m, expected=self.make_expected(m)), "WINDOWS_ARTIFACT_PATH_UNSAFE:0")

    def test_drive_designator_rejected(self):
        m = copy.deepcopy(self.manifest)
        m["files"][0]["path"] = "c:/aion.exe"
        self.deny(self.verify(manifest=m, expected=self.make_expected(m)), "WINDOWS_ARTIFACT_PATH_UNSAFE:0")

    def test_trailing_dot_segment_rejected(self):
        m = copy.deepcopy(self.manifest)
        m["files"][0]["path"] = "bin./aion.exe"
        self.deny(self.verify(manifest=m, expected=self.make_expected(m)), "WINDOWS_ARTIFACT_PATH_UNSAFE:0")

    def test_unicode_filename_rejected_for_ci_fixture(self):
        m = copy.deepcopy(self.manifest)
        m["files"][0]["path"] = "bin/áion.exe"
        self.deny(self.verify(manifest=m, expected=self.make_expected(m)), "WINDOWS_ARTIFACT_PATH_UNSAFE:0")

    def test_file_casefold_collision_rejected(self):
        m = copy.deepcopy(self.manifest)
        m["files"][1]["path"] = m["files"][0]["path"].upper()
        self.deny(self.verify(manifest=m, expected=self.make_expected(m)))

    def test_empty_manifest_file_table_rejected(self):
        m = copy.deepcopy(self.manifest)
        m["files"] = []
        self.deny(self.verify(manifest=m, expected=self.make_expected(m)), "ARTIFACT_TABLE_COUNT_INVALID")

    def test_oversized_manifest_file_table_rejected(self):
        m = copy.deepcopy(self.manifest)
        m["files"] = [{
            "path": f"bin/file-{n:02}.bin",
            "size_bytes": 1,
            "sha256": D("1"),
        } for n in range(MAX_FILES + 1)]
        self.deny(self.verify(manifest=m, expected=self.make_expected(m)), "ARTIFACT_TABLE_COUNT_INVALID")

    def test_unbounded_fixture_file_bytes_rejected(self):
        a = dict(self.artifacts)
        a["bin/aion-ci-simulated.exe"] = b"x" * (MAX_FILE_BYTES + 1)
        self.deny(self.verify(artifacts=a), "ARTIFACT_BYTES_INVALID:bin/aion-ci-simulated.exe")

    def test_no_zero_byte_artifacts(self):
        a = dict(self.artifacts)
        a["bin/aion-ci-simulated.exe"] = b""
        self.deny(self.verify(artifacts=a), "ARTIFACT_BYTES_INVALID:bin/aion-ci-simulated.exe")

    def test_invalid_file_digest_format_rejected(self):
        m = copy.deepcopy(self.manifest)
        m["files"][0]["sha256"] = "NOT_SHA"
        self.deny(self.verify(manifest=m, expected=self.make_expected(m)), "ARTIFACT_DIGEST_INVALID:0")

    def test_manifest_file_size_bool_rejected(self):
        m = copy.deepcopy(self.manifest)
        m["files"][0]["size_bytes"] = True
        self.deny(self.verify(manifest=m, expected=self.make_expected(m)), "ARTIFACT_SIZE_INVALID:0")

    def test_manifest_file_extra_metadata_rejected(self):
        m = copy.deepcopy(self.manifest)
        m["files"][0]["executable_trusted"] = True
        self.deny(self.verify(manifest=m, expected=self.make_expected(m)), "EXACT_FILE_FIELDS_REQUIRED:0")

    def test_manifest_extra_owner_approval_rejected(self):
        m = copy.deepcopy(self.manifest)
        m["owner_approval_implicitly_granted"] = True
        self.deny(self.verify(manifest=m, expected=self.make_expected(m)), "EXACT_MANIFEST_FIELDS_REQUIRED")

    def test_manifest_missing_required_trust_denial_rejected(self):
        m = copy.deepcopy(self.manifest)
        del m["publisher_identity_authorized"]
        self.deny(self.verify(manifest=m, expected=self.make_expected(m)), "EXACT_MANIFEST_FIELDS_REQUIRED")

    def test_manifest_publisher_claim_fails(self):
        m = copy.deepcopy(self.manifest)
        m["publisher_identity_authorized"] = True
        self.deny(self.verify(manifest=m, expected=self.make_expected(m)), "FORBIDDEN_CI_TRUST_PROMOTION:publisher_identity_authorized")

    def test_builder_attestation_claim_fails(self):
        m = copy.deepcopy(self.manifest)
        m["build_provenance_independently_attested"] = True
        self.deny(self.verify(manifest=m, expected=self.make_expected(m)), "FORBIDDEN_CI_TRUST_PROMOTION:build_provenance_independently_attested")

    def test_owner_install_claim_fails(self):
        m = copy.deepcopy(self.manifest)
        m["owner_install_authorization_present"] = True
        self.deny(self.verify(manifest=m, expected=self.make_expected(m)), "FORBIDDEN_CI_TRUST_PROMOTION:owner_install_authorization_present")

    def test_bad_release_id_rejected(self):
        m = copy.deepcopy(self.manifest)
        m["release_id"] = "REAL_PRODUCTION_AION"
        self.deny(self.verify(manifest=m, expected=self.make_expected(m)), "CI_RELEASE_ID_INVALID")

    def test_bad_version_rejected(self):
        m = copy.deepcopy(self.manifest)
        m["version"] = "1.0.0"
        self.deny(self.verify(manifest=m, expected=self.make_expected(m)), "CI_RELEASE_VERSION_INVALID")

    def test_bad_source_commit_rejected(self):
        m = copy.deepcopy(self.manifest)
        m["source_commit"] = "not-a-git-sha"
        self.deny(self.verify(manifest=m, expected=self.make_expected(m)), "SOURCE_COMMIT_INVALID")

    def test_invalid_build_run_rejected(self):
        m = copy.deepcopy(self.manifest)
        m["build_run_id"] = "0"
        self.deny(self.verify(manifest=m, expected=self.make_expected(m)), "BUILD_RUN_ID_INVALID")

    def test_wrong_signing_key_source_rejected(self):
        m = copy.deepcopy(self.manifest)
        m["key_source"] = "PRODUCTION_OWNER_SIGNER"
        self.deny(self.verify(manifest=m, expected=self.make_expected(m)), "EPHEMERAL_TEST_SIGNER_ONLY")

    def test_wrong_external_source_commit_rejected(self):
        e = dict(self.expected)
        e["source_commit"] = "b" * 40
        self.deny(self.verify(expected=e), "RELEASE_EXPECTED_BINDING_MISMATCH:source_commit")

    def test_wrong_expected_run_id_rejected(self):
        e = dict(self.expected)
        e["build_run_id"] = "888"
        self.deny(self.verify(expected=e), "RELEASE_EXPECTED_BINDING_MISMATCH:build_run_id")

    def test_wrong_expected_publisher_policy_rejected(self):
        e = dict(self.expected)
        e["publisher_policy_digest"] = D("e")
        self.deny(self.verify(expected=e), "RELEASE_EXPECTED_BINDING_MISMATCH:publisher_policy_digest")

    def test_wrong_expected_challenge_rejected(self):
        e = dict(self.expected)
        e["release_challenge_digest"] = D("f")
        self.deny(self.verify(expected=e), "RELEASE_EXPECTED_BINDING_MISMATCH:release_challenge_digest")

    def test_wrong_expected_signer_digest_rejected(self):
        e = dict(self.expected)
        e["ci_signer_public_key_sha256"] = D("f")
        self.deny(self.verify(expected=e), "RELEASE_EXPECTED_BINDING_MISMATCH:ci_signer_public_key_sha256")

    def test_missing_external_expected_binding_rejected(self):
        e = dict(self.expected)
        del e["source_commit"]
        self.deny(self.verify(expected=e), "EXACT_EXTERNAL_EXPECTATIONS_REQUIRED")

    def test_extra_external_expected_binding_rejected(self):
        e = dict(self.expected)
        e["owner_approval"] = True
        self.deny(self.verify(expected=e), "EXACT_EXTERNAL_EXPECTATIONS_REQUIRED")

    def test_handoff_plan_is_untrusted_and_never_installs(self):
        p = self.handoff()
        self.assertEqual(p["state"], HANDOFF_READY, p)
        for flag in ("aion_authorized_publisher_proven", "release_bytes_trusted",
                     "independent_build_attestation_verified",
                     "release_approved_for_owner", "installation_authorized",
                     "files_written", "owner_device_accessed",
                     "deploy_executed", "worker_activated"):
            self.assertFalse(p[flag], flag)

    def test_handoff_rejects_invalid_candidate(self):
        p = self.handoff(v=self.verify(signature=bytes(64)))
        self.assertEqual(p["state"], BLOCKED)

    def test_handoff_rejects_tampered_evidence_digest(self):
        v = self.verify()
        v["source_commit"] = "b" * 40
        p = self.handoff(v)
        self.assertEqual(p["state"], BLOCKED)
        self.assertIn("CI_CRYPTO_CANDIDATE_TAMPERED", p["blockers"])

    def test_handoff_rejects_claimed_authorized_publisher(self):
        v = self.verify()
        v["signed_by_authorized_aion_publisher"] = True
        p = self.handoff(v)
        self.assertEqual(p["state"], BLOCKED)

    def test_handoff_rejects_missing_independent_builder_policy(self):
        p = self.handoff(independent_build_attestor_manifest_digest="")
        self.assertEqual(p["state"], BLOCKED)

    def test_handoff_rejects_misrepresented_ephemeral_key(self):
        v = self.verify()
        v["ci_key_ephemeral_untrusted"] = False
        self.assertEqual(self.handoff(v)["state"], BLOCKED)

    def test_policy_allows_no_real_install_or_publisher_trust(self):
        p = provenance_policy()
        self.assertTrue(p["fixture_only"])
        for name in ("ci_key_proves_authorized_publisher",
                     "matching_source_commit_proves_build_integrity",
                     "signature_without_key_registry_is_trusted",
                     "signature_matching_aion_release_is_known",
                     "manifest_without_artifact_bytes_is_sufficient",
                     "extra_artifacts_allowed", "unsafe_windows_paths_allowed",
                     "self_attested_builder_allowed",
                     "automatic_install_on_crypto_success",
                     "owner_device_accessed", "owner_authorization_consumed",
                     "install_token_consumed", "production_signing_key_generated",
                     "production_signed_release_created", "package_installed",
                     "deploy_executed", "worker_activated"):
            self.assertIs(p[name], False, name)

if __name__ == "__main__":
    unittest.main()
