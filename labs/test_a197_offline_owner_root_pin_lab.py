"""A197: actual Ed25519 and SQLite with a local manifest PIN, red-team LAB."""
import base64
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from atlasquant_aion_authority_verifier import (
    SCHEMA as STATEMENT_SCHEMA, canonical_statement_bytes,
    verify_authority_statement,
)
from atlasquant_aion_nonce_registry import PersistentNonceRegistry
from atlasquant_aion_trust_root import TrustRootRegistry
from labs.a197_offline_owner_root_pin_lab import (
    SCHEMA, canonical_manifest_digest, assess_pinned_authority_locally,
)

NOW = "2026-10-27T19:00:00Z"
BINDING = {
    "subject_id": "aion-core",
    "tenant_id": "owner-synthetic",
    "domain": "CORE",
    "policy_id": "AION_CORE_POLICY_V1",
}


def b64(raw):
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def root_manifest(key, *, root_id="root-owner", status="ACTIVE"):
    raw = key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    return {
        "schema": "ATLASQUANT_AION_TRUST_ROOT_V1",
        "roots": [{
            "key_id": root_id,
            "key_version": 1,
            "algorithm": "Ed25519",
            "public_key_b64": b64(raw),
            "status": status,
            "not_before": "2026-01-01T00:00:00Z",
            "not_after": "2027-12-31T23:59:59Z",
        }],
        "revoked_key_ids": [],
    }


def statement(*, root_id="root-owner", nonce="nonce-001", **changes):
    data = {
        "schema": STATEMENT_SCHEMA,
        "statement_id": "stmt-synthetic-001",
        "authority_id": "human-owner-synthetic",
        **BINDING,
        "capabilities": ["core.read"],
        "issued_at": "2026-10-27T18:30:00Z",
        "expires_at": "2026-10-27T21:00:00Z",
        "nonce": nonce,
        "key_id": root_id,
        "key_version": 1,
        "grant_kind": "CAPABILITY_GRANT",
    }
    data.update(changes)
    return data


def sign(key, data):
    return b64(key.sign(canonical_statement_bytes(data)))


class A197OfflineRootPinLabTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        # In Python, "with sqlite3.connect()" commits but does NOT always
        # close Windows handles. Track and close test connections explicitly.
        self.connections = []
        original_connect = PersistentNonceRegistry._connect

        def tracked_connect(registry):
            conn = original_connect(registry)
            self.connections.append(conn)
            return conn

        self.addCleanup(self.close_connections)
        patcher = patch.object(PersistentNonceRegistry, "_connect", tracked_connect)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.db_path = Path(self.tmp.name) / "local_nonce.sqlite3"
        self.nonces = PersistentNonceRegistry(self.db_path)
        self.owner_key = Ed25519PrivateKey.generate()
        self.attacker_key = Ed25519PrivateKey.generate()
        self.owner_manifest = root_manifest(self.owner_key)
        self.owner_pin = canonical_manifest_digest(self.owner_manifest)
        self.owner_stmt = statement()
        self.owner_sig = sign(self.owner_key, self.owner_stmt)

    def close_connections(self):
        for c in self.connections:
            c.close()

    def check(self, *, manifest=None, pin=None, stmt=None, sig=None, registry=None, binding=None):
        return assess_pinned_authority_locally(
            manifest=self.owner_manifest if manifest is None else manifest,
            expected_manifest_sha256=self.owner_pin if pin is None else pin,
            statement=self.owner_stmt if stmt is None else stmt,
            signature_b64=self.owner_sig if sig is None else sig,
            nonce_registry=self.nonces if registry is None else registry,
            now_ts=NOW,
            expected_binding=BINDING if binding is None else binding,
        )

    def assert_non_authorizing(self, report):
        self.assertEqual(report["schema"], SCHEMA)
        self.assertFalse(report["external_owner_provenance_verified"])
        self.assertFalse(report["independent_root_custody_verified"])
        self.assertFalse(report["independent_anti_rollback_verified"])
        self.assertFalse(report["human_owner_enrollment_verified"])
        self.assertFalse(report["execution_allowed"])
        self.assertFalse(report["approval_implied"])
        self.assertFalse(report["provider_called"])
        self.assertEqual(report["p0_homologated"], 0)
        self.assertTrue(report["hard_no_go"])

    def test_01_valid_signature_under_exact_pin_is_only_local(self):
        got = self.check()
        self.assertEqual(got["state"], "LOCAL_SIGNATURE_VALID_NOT_OWNER_HOMOLOGATION")
        self.assertTrue(got["local_signature_verified"])
        self.assertTrue(got["local_manifest_pin_matched"])
        self.assert_non_authorizing(got)

    def test_02_swapped_signer_and_manifest_rejected_by_original_owner_pin(self):
        forged = root_manifest(self.attacker_key)
        fake_signature = sign(self.attacker_key, self.owner_stmt)
        got = self.check(manifest=forged, sig=fake_signature)
        self.assertEqual(got["reason"], "MANIFEST_PIN_MISMATCH")
        self.assertFalse(got["local_signature_verified"])
        self.assertEqual(self.nonces.count(), 0)
        self.assert_non_authorizing(got)

    def test_03_root_pin_absent_does_not_allow_local_signature(self):
        for pin in ("", "f" * 63, "INVALID", 0, True):
            with self.subTest(pin=str(pin)):
                got = self.check(pin=pin)
                self.assertEqual(got["reason"], "TRUSTED_PIN_NOT_CONFIGURED")
                self.assert_non_authorizing(got)
        self.assertEqual(self.nonces.count(), 0)

    def test_04_untrusted_root_and_untrusted_pin_can_both_be_swapped_red(self):
        forged = root_manifest(self.attacker_key)
        forged_pin = canonical_manifest_digest(forged)
        forged_stmt = self.owner_stmt
        fake_signature = sign(self.attacker_key, forged_stmt)
        local = self.check(manifest=forged, pin=forged_pin, sig=fake_signature)
        self.assertEqual(local["state"], "LOCAL_SIGNATURE_VALID_NOT_OWNER_HOMOLOGATION")
        self.assert_non_authorizing(local)
        print("A197_ATTACKER_CONTROLS_ROOT_AND_PIN=LOCAL_CRYPTO_SUCCEEDS_INDEPENDENT_OWNER_ROOT_RED", flush=True)

    def test_05_raw_verifier_without_independent_pin_accepts_forged_root_red(self):
        forged = root_manifest(self.attacker_key)
        result = verify_authority_statement(
            self.owner_stmt,
            signature_b64=sign(self.attacker_key, self.owner_stmt),
            trust_roots=TrustRootRegistry.from_mapping(forged),
            nonce_registry=self.nonces,
            now_ts=NOW,
            expected_binding=BINDING,
        )
        self.assertEqual(result["state"], "VERIFIED")
        self.assertFalse(result["execution_allowed"])
        print("A197_SELF_SUPPLIED_ROOT_VALID_SIGNATURE=NOT_HUMAN_OWNER_AUTHORITY_RED", flush=True)

    def test_06_revocation_manifest_edit_changes_pin(self):
        revoked = deepcopy(self.owner_manifest)
        revoked["revoked_key_ids"] = ["root-owner"]
        self.assertNotEqual(canonical_manifest_digest(revoked), self.owner_pin)
        got = self.check(manifest=revoked)
        self.assertEqual(got["reason"], "MANIFEST_PIN_MISMATCH")
        self.assertEqual(self.nonces.count(), 0)

    def test_07_root_status_edit_changes_pin(self):
        retired = deepcopy(self.owner_manifest)
        retired["roots"][0]["status"] = "RETIRED"
        self.assertNotEqual(canonical_manifest_digest(retired), self.owner_pin)
        self.assertEqual(self.check(manifest=retired)["state"], "BLOCKED")

    def test_08_caller_repin_of_revoked_root_still_rejected_by_verifier(self):
        revoked = deepcopy(self.owner_manifest)
        revoked["roots"][0]["status"] = "REVOKED"
        new_pin = canonical_manifest_digest(revoked)
        result = self.check(manifest=revoked, pin=new_pin)
        self.assertEqual(result["reason"], "LOCAL_SIGNATURE_OR_REPLAY_DENIED")
        self.assertTrue(result["local_manifest_pin_matched"])
        self.assertEqual(self.nonces.count(), 0)

    def test_09_tampered_statement_signature_rejected_without_nonce_claim(self):
        tampered = {**self.owner_stmt, "capabilities": ["core.plan"]}
        result = self.check(stmt=tampered)
        self.assertEqual(result["reason"], "LOCAL_SIGNATURE_OR_REPLAY_DENIED")
        self.assertTrue(result["local_manifest_pin_matched"])
        self.assertEqual(self.nonces.count(), 0)

    def test_10_pin_mismatch_must_not_burn_nonce(self):
        forged = root_manifest(self.attacker_key)
        self.assertEqual(self.check(manifest=forged)["state"], "BLOCKED")
        valid = self.check()
        self.assertEqual(valid["state"], "LOCAL_SIGNATURE_VALID_NOT_OWNER_HOMOLOGATION")
        self.assertEqual(self.nonces.count(), 1)

    def test_11_successful_local_signature_replay_denied(self):
        self.assertEqual(self.check()["state"], "LOCAL_SIGNATURE_VALID_NOT_OWNER_HOMOLOGATION")
        again = self.check()
        self.assertEqual(again["reason"], "LOCAL_SIGNATURE_OR_REPLAY_DENIED")
        self.assertEqual(self.nonces.count(), 1)

    def test_12_new_empty_nonce_store_reopens_exact_same_signed_grant_red(self):
        # Deleting/restoring the local nonce journal is not prevented by a
        # signature or root-pin. Fresh DB simulates a fully lost/rolled-back
        # local nonce history. This is NOT an actual external custodian test.
        self.assertEqual(self.check()["state"], "LOCAL_SIGNATURE_VALID_NOT_OWNER_HOMOLOGATION")
        fresh_db = PersistentNonceRegistry(Path(self.tmp.name) / "reset_nonce.sqlite3")
        after_loss = self.check(registry=fresh_db)
        self.assertEqual(after_loss["state"], "LOCAL_SIGNATURE_VALID_NOT_OWNER_HOMOLOGATION")
        self.assert_non_authorizing(after_loss)
        print("A197_LOCAL_NONCE_HISTORY_RESET=REPLAY_ACCEPTED_NO_EXTERNAL_WITNESS_RED", flush=True)

    def test_13_pin_is_stable_across_manifest_field_insertion_order(self):
        shuffled = {
            "revoked_key_ids": [],
            "roots": deepcopy(self.owner_manifest["roots"]),
            "schema": self.owner_manifest["schema"],
        }
        self.assertEqual(canonical_manifest_digest(shuffled), self.owner_pin)

    def test_14_additional_manifest_field_denied(self):
        weird = {**self.owner_manifest, "caller_declares_independent": True}
        self.assertEqual(self.check(manifest=weird)["reason"], "MANIFEST_INVALID")

    def test_15_invalid_public_key_denied_even_under_well_shaped_claim(self):
        bad = deepcopy(self.owner_manifest)
        bad["roots"][0]["public_key_b64"] = b64(b"short")
        self.assertEqual(self.check(manifest=bad)["reason"], "MANIFEST_INVALID")

    def test_16_other_tenant_binding_still_denied(self):
        self.assertEqual(
            self.check(binding={**BINDING, "tenant_id": "other-tenant"})["reason"],
            "LOCAL_SIGNATURE_OR_REPLAY_DENIED",
        )
        self.assertEqual(self.nonces.count(), 0)

    def test_17_pin_does_not_grant_execution_even_with_signed_plan_capability(self):
        stmt = statement(capabilities=["core.plan"], nonce="nonce-plan")
        got = self.check(stmt=stmt, sig=sign(self.owner_key, stmt))
        self.assertEqual(got["state"], "LOCAL_SIGNATURE_VALID_NOT_OWNER_HOMOLOGATION")
        self.assert_non_authorizing(got)


if __name__ == "__main__":
    unittest.main()
