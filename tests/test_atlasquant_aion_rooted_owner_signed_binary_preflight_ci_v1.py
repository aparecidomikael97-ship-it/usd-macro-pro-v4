"""Adversarial tests for rooted owner -> signed pinned binary preflight."""
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

from atlasquant_aion_rooted_owner_signed_binary_preflight_ci_v1 import (
    REGISTRY_PURPOSE,
    REGISTRY_SCHEMA,
    STATE,
    SQLiteBinaryAuthorizationReplayStore,
    registry_signing_message,
    verify_rooted_owner_signed_binary_preflight,
)
from atlasquant_aion_windows_signed_binary_ci_negative_intent_v1 import (
    OPERATION,
    SCHEMA as BINARY_SCHEMA,
    canonical_intent,
)


def pub(key: Ed25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def digest(raw: bytes) -> str:
    return "sha256:" + sha256(raw).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


class RootedOwnerBinaryPreflightTests(unittest.TestCase):
    def setUp(self):
        self.root = Ed25519PrivateKey.generate()
        self.owner = Ed25519PrivateKey.generate()
        self.device_binding = digest(b"synthetic-device-binding")
        self.now = 1_800_000_000

    def registry(
        self,
        *,
        owner_key=None,
        epoch=7,
        issued_at=None,
        expires_at=None,
        device_revoked=None,
        owner_keys=None,
    ):
        owner_key = self.owner if owner_key is None else owner_key
        issued_at = self.now - 10 if issued_at is None else issued_at
        expires_at = self.now + 300 if expires_at is None else expires_at
        if owner_keys is None:
            owner_keys = [{
                "key_id": "owner-key-7",
                "public_key_b64": b64(pub(owner_key)),
                "enrolled_epoch": epoch,
                "revoked_epoch": None,
                "supersedes": None,
            }]
        return {
            "schema": REGISTRY_SCHEMA,
            "purpose": REGISTRY_PURPOSE,
            "registry_id": "atlasquant-owner-registry",
            "owner_subject": "HUMAN_OWNER_MIKAEL",
            "host_issuer": "atlasquant-trusted-host",
            "epoch": epoch,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "owner_keys": owner_keys,
            "devices": [{
                "device_id": "owner-device-ci-fixture",
                "binding_digest": self.device_binding,
                "enrolled_epoch": 1,
                "revoked_epoch": device_revoked,
            }],
        }

    def signed_registry(self, registry=None, *, root=None):
        registry = self.registry() if registry is None else registry
        root = self.root if root is None else root
        raw = canonical(registry)
        sig = root.sign(registry_signing_message(registry))
        return raw, b64(sig)

    def manifest(self, **changes):
        result = {
            "schema": BINARY_SCHEMA,
            "operation": OPERATION,
            "nonce": "ab" * 16,
            "image_path": r"C:\Pinned\AION\candidate.exe",
            "image_sha256": sha256(b"candidate-executable").hexdigest(),
            "issued_at": self.now - 5,
            "expires_at": self.now + 60,
            "expected_token_verdict": "TOKEN_NOT_APPCONTAINER",
        }
        result.update(changes)
        return result

    def call(
        self,
        tempdir,
        *,
        registry=None,
        registry_raw=None,
        registry_sig=None,
        owner_signing_key=None,
        manifest=None,
        manifest_sig=None,
        root_public=None,
        root_fingerprint=None,
        minimum_epoch=7,
        expected_owner_subject="HUMAN_OWNER_MIKAEL",
        expected_device_binding=None,
        observed_path=None,
        observed_sha=None,
        replay_store="default",
        now=None,
    ):
        registry = self.registry() if registry is None else registry
        if registry_raw is None or registry_sig is None:
            generated_raw, generated_sig = self.signed_registry(registry)
            registry_raw = generated_raw if registry_raw is None else registry_raw
            registry_sig = generated_sig if registry_sig is None else registry_sig
        manifest = self.manifest() if manifest is None else manifest
        owner_signing_key = self.owner if owner_signing_key is None else owner_signing_key
        if manifest_sig is None:
            manifest_sig = owner_signing_key.sign(canonical_intent(manifest))
        root_public = pub(self.root) if root_public is None else root_public
        root_fingerprint = digest(root_public) if root_fingerprint is None else root_fingerprint
        expected_device_binding = (
            self.device_binding if expected_device_binding is None
            else expected_device_binding
        )
        observed_path = (
            manifest.get("image_path", "") if observed_path is None else observed_path
        )
        observed_sha = (
            manifest.get("image_sha256", "") if observed_sha is None else observed_sha
        )
        if replay_store == "default":
            replay_store = SQLiteBinaryAuthorizationReplayStore(
                Path(tempdir) / "replay.sqlite3"
            )
        return verify_rooted_owner_signed_binary_preflight(
            registry_raw,
            registry_sig,
            manifest,
            manifest_sig,
            pinned_root_public_key=root_public,
            expected_root_fingerprint=root_fingerprint,
            expected_registry_id="atlasquant-owner-registry",
            expected_owner_subject=expected_owner_subject,
            expected_host_issuer="atlasquant-trusted-host",
            expected_device_id="owner-device-ci-fixture",
            expected_device_binding_digest=expected_device_binding,
            minimum_registry_epoch=minimum_epoch,
            observed_image_path=observed_path,
            observed_image_sha256=observed_sha,
            now=self.now if now is None else now,
            replay_store=replay_store,
        )

    def assert_no_execution_authority(self, result):
        for field in (
            "production_owner_identity_verified",
            "trusted_host_attached",
            "physical_attestation_verified",
            "appcontainer_verified",
            "network_deny_verified",
            "safe_to_resume",
            "installer_authorized",
            "build_authorized",
            "deploy_authorized",
        ):
            self.assertIs(result[field], False, field)

    def test_rooted_owner_signature_and_replay_candidate_only(self):
        with tempfile.TemporaryDirectory() as td:
            result = self.call(td)
        self.assertEqual(result["state"], STATE, result)
        for field in (
            "root_registry_verified",
            "owner_key_resolved",
            "device_enrolled",
            "owner_manifest_signature_verified",
            "binary_path_digest_bound",
            "durable_replay_guard_consumed",
            "owner_identity_bound_to_rooted_registry",
        ):
            self.assertIs(result[field], True, field)
        self.assertEqual(result["owner_subject"], "HUMAN_OWNER_MIKAEL")
        self.assertEqual(result["owner_key_id"], "owner-key-7")
        self.assert_no_execution_authority(result)

    def test_same_signed_authorization_replay_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            store = SQLiteBinaryAuthorizationReplayStore(Path(td) / "r.sqlite3")
            first = self.call(td, replay_store=store)
            second = self.call(td, replay_store=store)
        self.assertEqual(first["state"], STATE)
        self.assertEqual(second["reason"], "REPLAY_OR_STORE_FAILURE")
        self.assert_no_execution_authority(second)

    def test_replay_rejected_after_store_reopen(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "r.sqlite3"
            first = self.call(td, replay_store=SQLiteBinaryAuthorizationReplayStore(path))
            second = self.call(td, replay_store=SQLiteBinaryAuthorizationReplayStore(path))
        self.assertEqual(first["state"], STATE)
        self.assertEqual(second["reason"], "REPLAY_OR_STORE_FAILURE")

    def test_attacker_self_signed_manifest_is_not_owner_authority(self):
        attacker = Ed25519PrivateKey.generate()
        with tempfile.TemporaryDirectory() as td:
            result = self.call(td, owner_signing_key=attacker)
        self.assertEqual(
            result["binary_reason"], "ED25519_SIGNATURE_INVALID", result
        )
        self.assert_no_execution_authority(result)

    def test_unpinned_root_is_rejected(self):
        other_root = Ed25519PrivateKey.generate()
        with tempfile.TemporaryDirectory() as td:
            result = self.call(
                td,
                root_public=pub(other_root),
                root_fingerprint=digest(pub(other_root)),
            )
        self.assertEqual(result["registry_reason"], "REGISTRY_SIGNATURE_INVALID")
        self.assert_no_execution_authority(result)

    def test_client_cannot_swap_root_and_registry_together(self):
        attacker_root = Ed25519PrivateKey.generate()
        raw, sig = self.signed_registry(root=attacker_root)
        with tempfile.TemporaryDirectory() as td:
            result = self.call(td, registry_raw=raw, registry_sig=sig)
        self.assertEqual(result["registry_reason"], "REGISTRY_SIGNATURE_INVALID")

    def test_registry_rollback_below_host_floor_is_rejected(self):
        registry = self.registry(epoch=7)
        with tempfile.TemporaryDirectory() as td:
            result = self.call(td, registry=registry, minimum_epoch=8)
        self.assertEqual(result["registry_reason"], "ROLLBACK_BELOW_TRUSTED_FLOOR")

    def test_revoked_device_is_rejected(self):
        registry = self.registry(device_revoked=7)
        with tempfile.TemporaryDirectory() as td:
            result = self.call(td, registry=registry)
        self.assertEqual(result["registry_reason"], "DEVICE_NOT_ENROLLED_OR_REVOKED")

    def test_wrong_device_binding_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            result = self.call(td, expected_device_binding=digest(b"other-device"))
        self.assertEqual(result["registry_reason"], "DEVICE_NOT_ENROLLED_OR_REVOKED")

    def test_wrong_owner_subject_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            result = self.call(td, expected_owner_subject="HUMAN_OWNER_OTHER")
        self.assertEqual(result["registry_reason"], "REGISTRY_IDENTITY_MISMATCH")

    def test_rotated_revoked_old_owner_key_cannot_sign(self):
        old = Ed25519PrivateKey.generate()
        new = Ed25519PrivateKey.generate()
        owner_keys = [
            {
                "key_id": "owner-key-6",
                "public_key_b64": b64(pub(old)),
                "enrolled_epoch": 6,
                "revoked_epoch": 7,
                "supersedes": None,
            },
            {
                "key_id": "owner-key-7",
                "public_key_b64": b64(pub(new)),
                "enrolled_epoch": 7,
                "revoked_epoch": None,
                "supersedes": "owner-key-6",
            },
        ]
        registry = self.registry(owner_keys=owner_keys)
        manifest = self.manifest()
        old_sig = old.sign(canonical_intent(manifest))
        with tempfile.TemporaryDirectory() as td:
            rejected = self.call(
                td, registry=registry, manifest=manifest, manifest_sig=old_sig
            )
            accepted = self.call(
                td,
                registry=registry,
                manifest=self.manifest(nonce="cd" * 16),
                owner_signing_key=new,
            )
        self.assertEqual(rejected["binary_reason"], "ED25519_SIGNATURE_INVALID")
        self.assertEqual(accepted["state"], STATE)

    def test_path_swap_is_rejected_before_replay_consumption(self):
        manifest = self.manifest()
        with tempfile.TemporaryDirectory() as td:
            store = SQLiteBinaryAuthorizationReplayStore(Path(td) / "r.sqlite3")
            bad = self.call(
                td,
                manifest=manifest,
                observed_path=r"C:\Pinned\AION\evil.exe",
                replay_store=store,
            )
            good = self.call(td, manifest=manifest, replay_store=store)
        self.assertEqual(
            bad["binary_reason"], "SUSPENDED_PROCESS_IMAGE_PATH_MISMATCH"
        )
        self.assertEqual(good["state"], STATE)

    def test_digest_swap_is_rejected_before_replay_consumption(self):
        manifest = self.manifest()
        with tempfile.TemporaryDirectory() as td:
            store = SQLiteBinaryAuthorizationReplayStore(Path(td) / "r.sqlite3")
            bad = self.call(
                td, manifest=manifest, observed_sha="0" * 64, replay_store=store
            )
            good = self.call(td, manifest=manifest, replay_store=store)
        self.assertEqual(
            bad["binary_reason"], "SUSPENDED_PROCESS_IMAGE_DIGEST_MISMATCH"
        )
        self.assertEqual(good["state"], STATE)

    def test_manifest_tamper_after_owner_signature_is_rejected(self):
        manifest = self.manifest()
        signature = self.owner.sign(canonical_intent(manifest))
        tampered = deepcopy(manifest)
        tampered["image_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as td:
            result = self.call(
                td,
                manifest=tampered,
                manifest_sig=signature,
                observed_sha="0" * 64,
            )
        self.assertEqual(result["binary_reason"], "ED25519_SIGNATURE_INVALID")

    def test_operation_cannot_be_upgraded_to_execution(self):
        for operation in ("RESUME_PROCESS", "INSTALL_AION", "DEPLOY", "ALLOW_NETWORK"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as td:
                manifest = self.manifest(operation=operation)
                result = self.call(td, manifest=manifest)
                self.assertEqual(
                    result["binary_reason"], "CI_NEGATIVE_ONLY_OPERATION_REQUIRED"
                )
                self.assert_no_execution_authority(result)

    def test_expired_manifest_is_rejected(self):
        manifest = self.manifest(issued_at=self.now - 200, expires_at=self.now - 1)
        with tempfile.TemporaryDirectory() as td:
            result = self.call(td, manifest=manifest)
        self.assertEqual(
            result["binary_reason"], "SIGNATURE_WINDOW_INVALID_OR_EXPIRED"
        )

    def test_expired_registry_is_rejected(self):
        registry = self.registry(
            issued_at=self.now - 500,
            expires_at=self.now - 1,
        )
        with tempfile.TemporaryDirectory() as td:
            result = self.call(td, registry=registry)
        self.assertEqual(result["registry_reason"], "REGISTRY_NOT_CURRENT")

    def test_missing_replay_store_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            result = self.call(td, replay_store=None)
        self.assertEqual(result["reason"], "DURABLE_REPLAY_STORE_REQUIRED")
        self.assert_no_execution_authority(result)

    def test_memory_and_uri_replay_databases_are_forbidden(self):
        for value in (":memory:", "file:volatile?mode=memory&cache=shared", ""):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    SQLiteBinaryAuthorizationReplayStore(value)

    def test_registry_signature_tamper_is_rejected(self):
        registry = self.registry()
        raw, sig = self.signed_registry(registry)
        signature = bytearray(base64.b64decode(sig))
        signature[0] ^= 1
        tampered = base64.b64encode(bytes(signature)).decode("ascii")
        with tempfile.TemporaryDirectory() as td:
            result = self.call(td, registry_raw=raw, registry_sig=tampered)
        self.assertEqual(result["registry_reason"], "REGISTRY_SIGNATURE_INVALID")

    def test_result_never_mutates_manifest_or_registry(self):
        registry = self.registry()
        manifest = self.manifest()
        before_registry = deepcopy(registry)
        before_manifest = deepcopy(manifest)
        with tempfile.TemporaryDirectory() as td:
            self.call(td, registry=registry, manifest=manifest)
        self.assertEqual(registry, before_registry)
        self.assertEqual(manifest, before_manifest)


if __name__ == "__main__":
    unittest.main()
