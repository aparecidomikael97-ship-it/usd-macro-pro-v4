"""Synthetic owner registry tests: independent pinned root and revocation preflight."""
from __future__ import annotations

import base64
from copy import deepcopy
from hashlib import sha256
import json
from unittest import TestCase

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from atlasquant_aion_owner_signed_key_registry_preflight_v1 import (
    SCHEMA, PURPOSE, DOMAIN, MAX_REGISTRY_TTL,
    parse_registry_snapshot, root_signing_message,
    verify_owner_registry_for_host_review,
)


def _sha(b: bytes) -> str:
    return "sha256:" + sha256(b).hexdigest()


def _raw(document) -> bytes:
    return json.dumps(
        document, ensure_ascii=True, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def _pub(key):
    return key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


class RootSignedOwnerRegistryPreflightTests(TestCase):
    def setUp(self):
        self.root = Ed25519PrivateKey.generate()
        self.owner1 = Ed25519PrivateKey.generate()
        self.owner2 = Ed25519PrivateKey.generate()
        self.root_public = _pub(self.root)
        self.now = 2000000000
        self.device_hash = _sha(b"registered-ci-desktop")
        self.mobile_hash = _sha(b"registered-ci-mobile")
        self.snapshot = {
            "schema": SCHEMA,
            "purpose": PURPOSE,
            "registry_id": "atlasquant-owner-keys-ci",
            "owner_subject": "mikael",
            "host_issuer": "host-ci",
            "epoch": 1,
            "issued_at": self.now - 100,
            "expires_at": self.now + 3600,
            "owner_keys": [
                {
                    "key_id": "owner-key-001",
                    "public_key_b64": _b64(_pub(self.owner1)),
                    "enrolled_epoch": 1,
                    "revoked_epoch": None,
                    "supersedes": None,
                },
            ],
            "devices": [
                {
                    "device_id": "desktop-ci",
                    "binding_digest": self.device_hash,
                    "enrolled_epoch": 1,
                    "revoked_epoch": None,
                },
                {
                    "device_id": "mobile-ci",
                    "binding_digest": self.mobile_hash,
                    "enrolled_epoch": 1,
                    "revoked_epoch": None,
                },
            ],
        }

    def sign_raw(self, raw, signer=None):
        # Used to test malicious but authentically root-signed JSON documents.
        if isinstance(raw, dict):
            raw = _raw(raw)
        doc = json.loads(raw.decode("utf-8"))
        msg = DOMAIN + _raw(doc)
        return _b64((self.root if signer is None else signer).sign(msg))

    def evaluate(self, snap=None, *, raw=None, signature=None, **overrides):
        snap = self.snapshot if snap is None else snap
        raw = _raw(snap) if raw is None else raw
        args = dict(
            pinned_root_public_key=self.root_public,
            expected_root_fingerprint=_sha(self.root_public),
            expected_registry_id="atlasquant-owner-keys-ci",
            expected_owner_subject="mikael",
            expected_host_issuer="host-ci",
            expected_device_id="desktop-ci",
            expected_device_binding_digest=self.device_hash,
            minimum_epoch=1,
            now_epoch=self.now,
        )
        args.update(overrides)
        return verify_owner_registry_for_host_review(
            raw, self.sign_raw(snap) if signature is None else signature, **args,
        )

    def assert_rejected(self, result, reason=None):
        self.assertEqual(result["state"], "BLOCKED", result)
        self.assertFalse(result["registry_signature_verified"])
        self.assertFalse(result["owner_key_resolved"])
        self.assertFalse(result["device_enrolled"])
        self.assertFalse(result["authorizes_execution"])
        self.assertFalse(result["authorizes_deploy"])
        self.assertFalse(result["authorizes_payment"])
        if reason:
            self.assertEqual(result["reason"], reason)

    def test_root_signed_first_key_and_desktop_resolves_for_review(self):
        result = self.evaluate()
        self.assertEqual(result["state"], "SIGNED_REGISTRY_VERIFIED_FOR_HOST_REVIEW")
        self.assertTrue(result["registry_signature_verified"])
        self.assertEqual(result["registry_epoch"], 1)
        self.assertEqual(result["owner_key_id"], "owner-key-001")
        self.assertEqual(result["resolved_owner_public_key"], _pub(self.owner1))
        self.assertEqual(result["owner_key_fingerprint"], _sha(_pub(self.owner1)))
        self.assertEqual(result["device_binding_digest"], self.device_hash)
        self.assertFalse(result["production_root_authenticated"])
        self.assertFalse(result["host_identity_authenticated"])
        self.assertFalse(result["authorizes_execution"])
        self.assertNotIn("private_key", result)

    def test_mobile_device_registered_independently(self):
        result = self.evaluate(
            expected_device_id="mobile-ci",
            expected_device_binding_digest=self.mobile_hash,
        )
        self.assertEqual(result["state"], "SIGNED_REGISTRY_VERIFIED_FOR_HOST_REVIEW")

    def test_repeated_nonsecret_registry_verification_no_side_effects(self):
        self.assertEqual(self.evaluate(), self.evaluate())

    def test_canonical_message_has_domain(self):
        message = root_signing_message(self.snapshot)
        self.assertTrue(message.startswith(DOMAIN))
        self.assertEqual(len(message), len(DOMAIN) + len(_raw(self.snapshot)))

    def test_public_root_signature_does_not_accept_unrelated_signer(self):
        signer = Ed25519PrivateKey.generate()
        self.assert_rejected(
            self.evaluate(signature=self.sign_raw(self.snapshot, signer)),
            "REGISTRY_SIGNATURE_INVALID",
        )

    def test_attacker_root_with_forged_out_of_band_pin_denied(self):
        attacker = Ed25519PrivateKey.generate()
        self.assert_rejected(self.evaluate(
            signature=self.sign_raw(self.snapshot, attacker),
            pinned_root_public_key=_pub(attacker),
        ), "UNPINNED_REGISTRY_ROOT")

    def test_mismatching_trusted_root_fingerprint_denied(self):
        self.assert_rejected(self.evaluate(
            expected_root_fingerprint=_sha(b"wrong-pin")
        ), "UNPINNED_REGISTRY_ROOT")

    def test_invalid_root_public_key_denied(self):
        self.assert_rejected(self.evaluate(
            pinned_root_public_key=b""
        ), "UNPINNED_REGISTRY_ROOT")

    def test_owner_key_swap_does_not_survive_existing_signature(self):
        changed = deepcopy(self.snapshot)
        changed["owner_keys"][0]["public_key_b64"] = _b64(_pub(self.owner2))
        self.assert_rejected(self.evaluate(
            changed, signature=self.sign_raw(self.snapshot)
        ), "REGISTRY_SIGNATURE_INVALID")

    def test_device_binding_swap_does_not_survive_signature(self):
        changed = deepcopy(self.snapshot)
        changed["devices"][0]["binding_digest"] = _sha(b"other-device")
        self.assert_rejected(self.evaluate(
            changed, signature=self.sign_raw(self.snapshot)
        ), "REGISTRY_SIGNATURE_INVALID")

    def test_device_missing_or_wrong_binding_denied(self):
        for change in (
            {"expected_device_id": "fake-desktop"},
            {"expected_device_binding_digest": _sha(b"other-device")},
            {"expected_device_id": "mobile-ci"},
        ):
            with self.subTest(change=change):
                self.assert_rejected(
                    self.evaluate(**change), "DEVICE_NOT_ENROLLED_OR_REVOKED"
                )

    def test_registered_mobile_can_be_revoked(self):
        changed = deepcopy(self.snapshot)
        changed["epoch"] = 2
        changed["devices"][1]["revoked_epoch"] = 2
        self.assert_rejected(self.evaluate(
            changed, expected_device_id="mobile-ci",
            expected_device_binding_digest=self.mobile_hash,
            minimum_epoch=2,
        ), "DEVICE_NOT_ENROLLED_OR_REVOKED")
        self.assertEqual(self.evaluate(
            changed, expected_device_id="desktop-ci", minimum_epoch=2,
        )["state"], "SIGNED_REGISTRY_VERIFIED_FOR_HOST_REVIEW")

    def test_all_devices_revoked_denied(self):
        changed = deepcopy(self.snapshot)
        changed["epoch"] = 2
        for device in changed["devices"]:
            device["revoked_epoch"] = 2
        self.assert_rejected(self.evaluate(changed), "DEVICE_NOT_ENROLLED_OR_REVOKED")

    def test_owner_rotation_requires_previous_key_revoked(self):
        changed = deepcopy(self.snapshot)
        changed["epoch"] = 2
        changed["owner_keys"][0]["revoked_epoch"] = 2
        changed["owner_keys"].append({
            "key_id": "owner-key-002",
            "public_key_b64": _b64(_pub(self.owner2)),
            "enrolled_epoch": 2,
            "revoked_epoch": None,
            "supersedes": "owner-key-001",
        })
        result = self.evaluate(changed, minimum_epoch=2)
        self.assertEqual(result["state"], "SIGNED_REGISTRY_VERIFIED_FOR_HOST_REVIEW")
        self.assertEqual(result["owner_key_id"], "owner-key-002")
        self.assertEqual(result["resolved_owner_public_key"], _pub(self.owner2))
        self.assertNotEqual(result["resolved_owner_public_key"], _pub(self.owner1))

    def test_stale_epoch_denied_even_with_correct_signature(self):
        self.assert_rejected(
            self.evaluate(minimum_epoch=2), "ROLLBACK_BELOW_TRUSTED_FLOOR"
        )

    def test_revoked_only_owner_keys_denied(self):
        changed = deepcopy(self.snapshot)
        changed["epoch"] = 2
        changed["owner_keys"][0]["revoked_epoch"] = 2
        self.assert_rejected(self.evaluate(changed), "NO_ACTIVE_OWNER_KEY")

    def test_two_active_keys_rejected_before_signature(self):
        changed = deepcopy(self.snapshot)
        changed["epoch"] = 2
        changed["owner_keys"].append({
            "key_id": "owner-key-002",
            "public_key_b64": _b64(_pub(self.owner2)),
            "enrolled_epoch": 2,
            "revoked_epoch": None,
            "supersedes": "owner-key-001",
        })
        self.assert_rejected(self.evaluate(changed), "REGISTRY_MALFORMED")

    def test_wrong_rotation_chain_rejected(self):
        changed = deepcopy(self.snapshot)
        changed["epoch"] = 2
        changed["owner_keys"][0]["revoked_epoch"] = 2
        changed["owner_keys"].append({
            "key_id": "owner-key-002",
            "public_key_b64": _b64(_pub(self.owner2)),
            "enrolled_epoch": 2,
            "revoked_epoch": None,
            "supersedes": "nonexistent-key",
        })
        self.assert_rejected(self.evaluate(changed), "REGISTRY_MALFORMED")

    def test_reused_owner_public_key_denied(self):
        changed = deepcopy(self.snapshot)
        changed["epoch"] = 2
        changed["owner_keys"][0]["revoked_epoch"] = 2
        changed["owner_keys"].append({
            "key_id": "owner-key-002",
            "public_key_b64": changed["owner_keys"][0]["public_key_b64"],
            "enrolled_epoch": 2,
            "revoked_epoch": None,
            "supersedes": "owner-key-001",
        })
        self.assert_rejected(self.evaluate(changed), "REGISTRY_MALFORMED")

    def test_reused_owner_key_identifier_denied(self):
        changed = deepcopy(self.snapshot)
        changed["epoch"] = 2
        changed["owner_keys"][0]["revoked_epoch"] = 2
        changed["owner_keys"].append({
            "key_id": "owner-key-001",
            "public_key_b64": _b64(_pub(self.owner2)),
            "enrolled_epoch": 2,
            "revoked_epoch": None,
            "supersedes": "owner-key-001",
        })
        self.assert_rejected(self.evaluate(changed), "REGISTRY_MALFORMED")

    def test_duplicate_device_id_or_binding_denied(self):
        for field, value in (
            ("device_id", "desktop-ci"), ("binding_digest", self.device_hash),
        ):
            with self.subTest(field=field):
                changed = deepcopy(self.snapshot)
                changed["devices"][1][field] = value
                self.assert_rejected(self.evaluate(changed), "REGISTRY_MALFORMED")

    def test_device_epoch_out_of_range_denied(self):
        changed = deepcopy(self.snapshot)
        changed["devices"][1]["enrolled_epoch"] = 3
        self.assert_rejected(self.evaluate(changed), "REGISTRY_MALFORMED")

    def test_bool_epoch_rejected(self):
        changed = deepcopy(self.snapshot)
        changed["epoch"] = True
        self.assert_rejected(self.evaluate(changed), "REGISTRY_MALFORMED")

    def test_bool_revoke_epoch_rejected(self):
        changed = deepcopy(self.snapshot)
        changed["devices"][0]["revoked_epoch"] = True
        self.assert_rejected(self.evaluate(changed), "REGISTRY_MALFORMED")

    def test_schema_or_purpose_or_extra_fields_rejected(self):
        for field, value in (
            ("schema", "wrong"), ("purpose", "payment-auth"), ("extra", True),
        ):
            with self.subTest(field=field):
                changed = deepcopy(self.snapshot)
                changed[field] = value
                self.assert_rejected(self.evaluate(changed), "REGISTRY_MALFORMED")

    def test_duplicate_json_fields_denied_without_verifying_signature(self):
        malformed = _raw(self.snapshot).decode("utf-8").replace(
            '"schema":"', '"schema":"INJECTED","schema":"', 1
        ).encode("utf-8")
        self.assert_rejected(self.evaluate(
            raw=malformed, signature=self.sign_raw(self.snapshot)
        ), "REGISTRY_MALFORMED")

    def test_non_utf8_and_nonbytes_raw_denied(self):
        for raw in (b"\xff\xfe", b"{}", "", 12):
            with self.subTest(raw=repr(raw)[:20]):
                self.assert_rejected(
                    self.evaluate(raw=raw, signature=self.sign_raw(self.snapshot)),
                    "REGISTRY_MALFORMED",
                )

    def test_oversized_snapshot_rejected(self):
        self.assert_rejected(self.evaluate(
            raw=b" " * 17000, signature=self.sign_raw(self.snapshot)
        ), "REGISTRY_MALFORMED")

    def test_canonical_base64_enforced_on_root_signature(self):
        for sig in ("invalid!", "AAAA", "A"*200, "", True, 42):
            with self.subTest(sig=str(sig)[:10]):
                self.assert_rejected(
                    self.evaluate(signature=sig), "REGISTRY_SIGNATURE_INVALID"
                )

    def test_host_expectation_mismatch_denied(self):
        for field, new in (
            ("expected_registry_id", "other-registry"),
            ("expected_owner_subject", "delegated-admin"),
            ("expected_host_issuer", "other-host"),
        ):
            with self.subTest(field=field):
                self.assert_rejected(
                    self.evaluate(**{field: new}), "REGISTRY_IDENTITY_MISMATCH"
                )

    def test_host_invalid_minimum_epoch_and_clock_denied(self):
        for changes in (
            {"minimum_epoch": 0}, {"minimum_epoch": True},
            {"now_epoch": True}, {"now_epoch": "2000000000"},
            {"expected_root_fingerprint": "bad"},
        ):
            with self.subTest(changes=changes):
                self.assert_rejected(
                    self.evaluate(**changes), "TRUSTED_HOST_EXPECTATIONS_REQUIRED"
                )

    def test_future_and_expired_registry_denied(self):
        for t in (self.now-101, self.now+3601):
            with self.subTest(time=t):
                self.assert_rejected(
                    self.evaluate(now_epoch=t), "REGISTRY_NOT_CURRENT"
                )

    def test_max_registry_ttl_enforced(self):
        changed = deepcopy(self.snapshot)
        changed["expires_at"] = changed["issued_at"] + MAX_REGISTRY_TTL + 1
        self.assert_rejected(self.evaluate(changed), "REGISTRY_MALFORMED")

    def test_invalid_public_key_format_denied(self):
        changed = deepcopy(self.snapshot)
        changed["owner_keys"][0]["public_key_b64"] = "AAAA"
        self.assert_rejected(self.evaluate(changed), "REGISTRY_MALFORMED")

    def test_revoked_device_can_never_resolve_even_when_root_signs(self):
        changed = deepcopy(self.snapshot)
        changed["epoch"] = 3
        changed["devices"][0]["revoked_epoch"] = 2
        self.assert_rejected(
            self.evaluate(changed, minimum_epoch=3),
            "DEVICE_NOT_ENROLLED_OR_REVOKED",
        )

    def test_signed_snapshot_does_not_enroll_owner_automatically(self):
        result = self.evaluate()
        self.assertFalse(result["production_root_authenticated"])
        self.assertFalse(result["host_identity_authenticated"])
        for key in ("authorizes_payment", "authorizes_execution", "authorizes_deploy"):
            self.assertFalse(result[key])
