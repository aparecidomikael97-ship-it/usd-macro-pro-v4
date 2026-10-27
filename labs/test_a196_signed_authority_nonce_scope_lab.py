"""A196 security regression: signed authority nonce scope collision (local LAB).

Real Ed25519 signatures, real authority verifier and real SQLite nonce registry.
Synthetic private keys never leave CI memory; no provider, deployment, external
witness, HUMAN_OWNER proof or production effects. This prevents one ambiguity
in the existing local nonce registry; it does NOT solve rollback/P0.
"""
import base64
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from atlasquant_aion_authority_verifier import (
    SCHEMA, canonical_statement_bytes, verify_authority_statement,
)
from atlasquant_aion_nonce_registry import PersistentNonceRegistry
from atlasquant_aion_trust_root import TrustRootRegistry

NOW = "2026-10-27T18:30:00Z"
BINDING = {
    "subject_id": "aion-core",
    "tenant_id": "atlasquant-owner",
    "domain": "CORE",
    "policy_id": "AION_CORE_POLICY_V1",
}
FIELDS = ("authority_id", "subject_id", "tenant_id", "domain", "policy_id")


def _b64(data):
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


class A196AuthorityScopeCollisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        # The production registry uses "with conn", which commits but does
        # not guarantee close() on Windows. This synthetic CI fixture retains
        # every REAL SQLite connection and explicitly closes it before the
        # temporary database directory is deleted.
        self._all_connections = []
        original_connect = PersistentNonceRegistry._connect
        def tracked_connect(instance):
            conn = original_connect(instance)
            self._all_connections.append(conn)
            return conn
        self.addCleanup(self._close_test_connections)
        patcher = patch.object(PersistentNonceRegistry, "_connect", tracked_connect)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.nonce_db = Path(self.temp.name) / "nonces.sqlite3"
        self.nonces = PersistentNonceRegistry(self.nonce_db)

        self.key = Ed25519PrivateKey.generate()
        public = self.key.public_key().public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw,
        )
        self.roots = TrustRootRegistry.from_mapping({
            "schema": "ATLASQUANT_AION_TRUST_ROOT_V1",
            "roots": [{
                "key_id": "synthetic-root",
                "key_version": 1,
                "algorithm": "Ed25519",
                "public_key_b64": _b64(public),
                "status": "ACTIVE",
                "not_before": "2026-01-01T00:00:00Z",
                "not_after": "2027-12-31T23:59:59Z",
            }],
            "revoked_key_ids": [],
        })

    def _close_test_connections(self):
        for conn in self._all_connections:
            conn.close()

    def statement(self, **overrides):
        values = {
            "schema": SCHEMA,
            "statement_id": "synthetic-1",
            "authority_id": "owner-control-plane",
            "subject_id": "aion-core",
            "tenant_id": "atlasquant-owner",
            "domain": "CORE",
            "policy_id": "AION_CORE_POLICY_V1",
            "capabilities": ["core.read", "core.plan"],
            "issued_at": "2026-10-27T18:00:00Z",
            "expires_at": "2026-10-27T19:30:00Z",
            "nonce": "local-synthetic-nonce-001",
            "key_id": "synthetic-root",
            "key_version": 1,
            "grant_kind": "CAPABILITY_GRANT",
        }
        values.update(overrides)
        return values

    def verify(self, stmt, expected_binding=None):
        return verify_authority_statement(
            stmt,
            signature_b64=_b64(self.key.sign(canonical_statement_bytes(stmt))),
            trust_roots=self.roots,
            nonce_registry=self.nonces,
            now_ts=NOW,
            expected_binding=BINDING if expected_binding is None else expected_binding,
        )

    def test_01_before_fix_two_different_identities_have_identical_legacy_scope(self):
        first = self.statement(authority_id="a|b", subject_id="c")
        second = self.statement(authority_id="a", subject_id="b|c")
        assert first["authority_id"] != second["authority_id"]
        assert first["subject_id"] != second["subject_id"]
        legacy = lambda v: "|".join(v[field] for field in FIELDS)
        self.assertEqual(legacy(first), legacy(second))
        print("A196_COLLIDING_LEGACY_PIPE_SCOPE=REPRODUCED_RED", flush=True)

    def test_02_legitimately_signed_pipe_in_authority_id_is_blocked(self):
        stmt = self.statement(authority_id="a|b", subject_id="c")
        expected = {**BINDING, "subject_id": "c"}
        out = self.verify(stmt, expected)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "AUTHORITY_NONCE_SCOPE_DELIMITER_RESERVED:authority_id",
            out["blockers"],
        )
        self.assertFalse(out["authority_verified"])
        self.assertFalse(out["execution_allowed"])
        self.assertEqual(self.nonces.count(), 0)

    def test_03_all_five_delimiter_bearing_fields_rejected_even_with_valid_signature(self):
        for field in FIELDS:
            with self.subTest(field=field):
                baseline = self.statement(**{field: "signed|but-ambiguous"})
                expected = {**BINDING}
                if field in expected:
                    expected[field] = baseline[field]
                result = self.verify(baseline, expected)
                self.assertEqual(result["state"], "BLOCKED")
                self.assertIn(
                    "AUTHORITY_NONCE_SCOPE_DELIMITER_RESERVED:" + field,
                    result["blockers"],
                )
                self.assertFalse(result["nonce_registered"])
                self.assertFalse(result["signature_verified"])
                self.assertFalse(result["execution_authority_granted"])
                self.assertEqual(self.nonces.count(), 0)

    def test_04_ambiguous_second_identity_also_fails_without_burning_nonce(self):
        first = self.statement(authority_id="a|b", subject_id="c")
        second = self.statement(authority_id="a", subject_id="b|c")
        for stmt in (first, second):
            outcome = self.verify(
                stmt, {**BINDING, "subject_id": stmt["subject_id"]},
            )
            self.assertEqual(outcome["state"], "BLOCKED")
            self.assertEqual(self.nonces.count(), 0)

    def test_05_normal_signed_statement_accepted_but_never_executes_action(self):
        stmt = self.statement()
        outcome = self.verify(stmt)
        self.assertEqual(outcome["state"], "VERIFIED")
        self.assertTrue(outcome["signature_verified"])
        self.assertTrue(outcome["nonce_registered"])
        self.assertFalse(outcome["execution_allowed"])
        self.assertFalse(outcome["approval_implied"])
        self.assertFalse(outcome["executes_action"])
        self.assertEqual(self.nonces.count(), 1)

    def test_06_exact_replay_remains_denied(self):
        stmt = self.statement()
        self.assertEqual(self.verify(stmt)["state"], "VERIFIED")
        again = self.verify(stmt)
        self.assertEqual(again["state"], "BLOCKED")
        self.assertIn("AUTHORITY_NONCE_REPLAYED", again["blockers"])
        self.assertEqual(self.nonces.count(), 1)

    def test_07_existing_legacy_claim_is_not_rekeyed_or_reopened(self):
        stmt = self.statement()
        legacy_scope = "|".join(stmt[f] for f in FIELDS)
        self.assertTrue(
            self.nonces.claim(
                scope=legacy_scope,
                nonce=stmt["nonce"],
                expires_at=stmt["expires_at"],
                now_ts=NOW,
            ),
        )
        self.assertEqual(
            self.nonces.schema_version(), 2,
            "Do not migrate nonce schema during this fix",
        )
        outcome = self.verify(stmt)
        self.assertEqual(outcome["state"], "BLOCKED")
        self.assertIn("AUTHORITY_NONCE_REPLAYED", outcome["blockers"])
        self.assertEqual(self.nonces.count(), 1)

    def test_08_two_unambiguous_distinct_scopes_can_reuse_same_nonce_independently(self):
        first = self.statement(authority_id="signed-owner-A")
        second = self.statement(authority_id="signed-owner-B", statement_id="synthetic-2")
        self.assertEqual(self.verify(first)["state"], "VERIFIED")
        self.assertEqual(self.verify(second)["state"], "VERIFIED")
        self.assertEqual(self.nonces.count(), 2)

    def test_09_special_pipe_is_not_fixed_by_forging_expected_binding(self):
        stmt = self.statement(tenant_id="tenant|spoof")
        expected = {**BINDING, "tenant_id": "tenant|spoof"}
        outcome = self.verify(stmt, expected)
        self.assertIn(
            "AUTHORITY_NONCE_SCOPE_DELIMITER_RESERVED:tenant_id",
            outcome["blockers"],
        )
        self.assertFalse(outcome["execution_authority_granted"])

    def test_10_local_registry_reopen_still_detects_nonambiguous_replay(self):
        stmt = self.statement()
        self.assertEqual(self.verify(stmt)["state"], "VERIFIED")
        self.nonces = PersistentNonceRegistry(self.nonce_db)
        self.assertIn("AUTHORITY_NONCE_REPLAYED", self.verify(stmt)["blockers"])

    def test_11_other_binding_mismatch_still_blocks(self):
        stmt = self.statement()
        outcome = self.verify(stmt, {**BINDING, "tenant_id": "another-tenant"})
        self.assertEqual(outcome["state"], "BLOCKED")
        self.assertIn("AUTHORITY_BINDING_MISMATCH:tenant_id", outcome["blockers"])
        self.assertEqual(self.nonces.count(), 0)

    def test_12_unknown_root_remains_red_not_authorized(self):
        stmt = self.statement(key_id="not-known")
        outcome = self.verify(stmt)
        self.assertEqual(outcome["state"], "BLOCKED")
        self.assertIn("TRUST_KEY_UNKNOWN", outcome["blockers"])
        self.assertEqual(self.nonces.count(), 0)

    def test_13_trusted_root_from_caller_is_not_independent_owner_custody(self):
        # Signature verification against caller-supplied root is cryptographically
        # valid but says nothing about whether the key belongs to HUMAN_OWNER.
        stmt = self.statement()
        self.assertEqual(self.verify(stmt)["state"], "VERIFIED")
        print(
            "A196_SELF_SUPPLIED_ROOT=NO_INDEPENDENT_HUMAN_OWNER_"
            "PROVENANCE_OR_ANTI_ROLLBACK_RED",
            flush=True,
        )


if __name__ == "__main__":
    unittest.main()
