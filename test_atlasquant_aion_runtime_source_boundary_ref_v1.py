"""Negative/adversarial offline tests; ephemeral synthetic Ed25519 keys only."""
import copy
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from atlasquant_aion_runtime_source_boundary_ref_v1 import (
    SCHEMA, WITNESS_SCHEMA, SOURCE_DOMAIN, WITNESS_DOMAIN,
    IndependentlyPinnedSource, canonical_bytes,
    guarded_checkpoint_reference_read, verify_source_preflight,
)

NOW = datetime(2026, 10, 10, 16, 0, tzinfo=timezone.utc)
SHA = "a" * 40


def fmt(value):
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def pub(key):
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def sign(record, key, domain):
    row = dict(record)
    row["signature"] = key.sign(canonical_bytes(row, domain=domain)).hex()
    return row


class RuntimeSourceBoundaryOfflineTests(unittest.TestCase):
    def setUp(self):
        self.k1 = Ed25519PrivateKey.generate()
        self.k2 = Ed25519PrivateKey.generate()
        self.trust = IndependentlyPinnedSource(
            owner_id="owner-a", tenant_id="company-a", workspace_id="ws-a",
            repo="owner/repo", branch="atlasquant-runtime",
            path="dados/aion/checkpoint_master.json",
            source_key_id="root-a", source_public_key=pub(self.k1),
            witness_key_id="head-b", witness_public_key=pub(self.k2),
            floor_sequence=10,
            floor_observed_at=NOW - timedelta(seconds=15),
        )
        self.config = SimpleNamespace(
            repo=self.trust.repo,
            branch=self.trust.branch,
            path=self.trust.path,
            token="synthetic-token-must-never-be-logged",
        )
        shared = {
            "owner_id": self.trust.owner_id,
            "tenant_id": self.trust.tenant_id,
            "workspace_id": self.trust.workspace_id,
            "repo": self.trust.repo,
            "branch": self.trust.branch,
            "path": self.trust.path,
            "content_sha": SHA,
            "sequence": 10,
        }
        self.proof = sign({
            **shared, "schema": SCHEMA,
            "issued_at": fmt(NOW - timedelta(minutes=1)),
            "expires_at": fmt(NOW + timedelta(minutes=2)),
            "key_id": "root-a",
        }, self.k1, SOURCE_DOMAIN)
        self.witness = sign({
            **shared, "schema": WITNESS_SCHEMA,
            "observed_at": fmt(NOW - timedelta(seconds=15)),
            "key_id": "head-b",
        }, self.k2, WITNESS_DOMAIN)
        self.reader = Mock(return_value={
            "status": "CONFIRMED", "sha": SHA,
            "checkpoint": {"project": "synthetic-safe"},
            "integrity": {"state": "CONFIRMED"},
        })

    def read(self, **overrides):
        opts = {
            "source_proof": self.proof,
            "witness_head": self.witness,
            "trusted": self.trust,
            "reader": self.reader,
            "now": NOW,
        }
        opts.update(overrides)
        return guarded_checkpoint_reference_read(self.config, **opts)

    def denied(self, **overrides):
        self.reader.reset_mock()
        decision = self.read(**overrides)
        self.assertEqual(decision["status"], "BLOCKED", decision)
        self.assertFalse(decision["admitted"])
        self.assertFalse(decision["worker_authorized"])
        self.assertFalse(decision["automatic_retry_allowed"])
        self.assertIsNone(decision["checkpoint"])
        self.reader.assert_not_called()
        self.assertNotIn("synthetic-token", str(decision))

    def test_valid_synthetic_signatures_only_verify_reference_not_ownership(self):
        d = self.read()
        self.reader.assert_called_once_with(self.config)
        self.assertEqual(d["status"], "REFERENCE_VERIFIED")
        self.assertTrue(d["admitted"])
        self.assertFalse(d["source_trust_production_verified"])
        self.assertFalse(d["worker_authorized"])
        self.assertEqual(d["sequence"], 10)

    def test_missing_proof_witness_and_trust_deny_before_reader(self):
        for payload in [
            {"trusted": None}, {"source_proof": None}, {"witness_head": None},
            {"source_proof": {}}, {"witness_head": {}},
            {"source_proof": []}, {"witness_head": []},
            {"trusted": "self asserted"},
        ]:
            with self.subTest(payload=str(payload)[:40]):
                self.denied(**payload)

    def test_config_cannot_redirect_to_other_repo_branch_or_path(self):
        for override in [
            {"repo": "attacker/repo"}, {"branch": "main"},
            {"path": "other/company.json"}, {"path": "../checkpoint.json"},
            {"repo": "owner/repo@attacker"}, {"branch": ""},
        ]:
            with self.subTest(override=override):
                bad = SimpleNamespace(**{**vars(self.config), **override})
                self.reader.reset_mock()
                d = guarded_checkpoint_reference_read(
                    bad, source_proof=self.proof, witness_head=self.witness,
                    trusted=self.trust, reader=self.reader, now=NOW,
                )
                self.assertEqual(d["status"], "BLOCKED")
                self.reader.assert_not_called()

    def test_owner_tenant_workspace_source_and_witness_avoid_cross_company(self):
        for key, value in (
            ("owner_id", "owner-b"), ("tenant_id", "company-b"),
            ("workspace_id", "ws-b"), ("repo", "other/repo"),
            ("branch", "main"), ("path", "other/secret.json"),
        ):
            for which in ("source", "witness"):
                with self.subTest(key=key, which=which):
                    proof, witness = copy.deepcopy(self.proof), copy.deepcopy(self.witness)
                    if which == "source":
                        proof[key] = value
                    else:
                        witness[key] = value
                    self.denied(source_proof=proof, witness_head=witness)

    def test_extra_authority_fields_and_wrong_payload_types_fail_closed(self):
        for which in ("source", "witness"):
            row = copy.deepcopy(self.proof if which == "source" else self.witness)
            row["approved"] = True
            with self.subTest(which=which):
                self.denied(**({"source_proof": row} if which == "source" else {"witness_head": row}))
        for bad in (True, "10", 10.0, 0, -1):
            with self.subTest(sequence=bad):
                row = copy.deepcopy(self.proof)
                row["sequence"] = bad
                self.denied(source_proof=row)

    def test_cryptographic_tamper_or_key_rotation_without_pin_denied(self):
        row = copy.deepcopy(self.proof)
        row["signature"] = "0" * 128
        self.denied(source_proof=row)
        row = copy.deepcopy(self.witness)
        row["signature"] = "f" * 128
        self.denied(witness_head=row)
        self.denied(trusted=replace(self.trust, source_public_key=pub(self.k2)))
        self.denied(trusted=replace(self.trust, witness_public_key=pub(self.k1)))
        self.denied(trusted=replace(self.trust, witness_key_id="root-a"))

    def test_sha_or_sequence_mismatch_denies_before_reader(self):
        proof = copy.deepcopy(self.proof)
        proof["content_sha"] = "b" * 40
        self.denied(source_proof=proof)
        witness = copy.deepcopy(self.witness)
        witness["sequence"] = 11
        self.denied(witness_head=witness)
        witness = copy.deepcopy(self.witness)
        witness["content_sha"] = "b" * 40
        self.denied(witness_head=witness)

    def test_rollback_floor_and_witness_freshness_denied(self):
        self.denied(trusted=replace(self.trust, floor_sequence=11))
        self.denied(trusted=replace(self.trust, floor_sequence=True))
        self.denied(trusted=replace(self.trust, floor_observed_at=NOW-timedelta(minutes=8)))
        self.denied(trusted=replace(self.trust, floor_observed_at=NOW+timedelta(minutes=1)))
        self.denied(now=NOW+timedelta(minutes=7))
        self.denied(now=NOW-timedelta(minutes=4))
        self.denied(now=NOW.replace(tzinfo=None))

    def test_signed_but_expired_replayed_or_future_proof_is_denied(self):
        old_proof = sign({
            **{k: v for k, v in self.proof.items() if k not in ("signature", "issued_at", "expires_at")},
            "issued_at": fmt(NOW-timedelta(minutes=8)),
            "expires_at": fmt(NOW-timedelta(minutes=4)),
        }, self.k1, SOURCE_DOMAIN)
        self.denied(source_proof=old_proof)
        future = sign({
            **{k: v for k, v in self.proof.items() if k not in ("signature", "issued_at", "expires_at")},
            "issued_at": fmt(NOW+timedelta(minutes=1)),
            "expires_at": fmt(NOW+timedelta(minutes=2)),
        }, self.k1, SOURCE_DOMAIN)
        self.denied(source_proof=future)
        old_head = sign({
            **{k: v for k, v in self.witness.items() if k not in ("signature", "observed_at")},
            "observed_at": fmt(NOW-timedelta(minutes=9)),
        }, self.k2, WITNESS_DOMAIN)
        self.denied(witness_head=old_head)

    def test_verified_signature_wrong_source_schema_key_or_owner_denied(self):
        wrong = sign({
            **{k: v for k, v in self.proof.items() if k != "signature"},
            "schema": "OLD_SCHEMA",
        }, self.k1, SOURCE_DOMAIN)
        self.denied(source_proof=wrong)
        wrong = sign({
            **{k: v for k, v in self.proof.items() if k != "signature"},
            "key_id": "another-key",
        }, self.k1, SOURCE_DOMAIN)
        self.denied(source_proof=wrong)
        wrong = sign({
            **{k: v for k, v in self.witness.items() if k != "signature"},
            "owner_id": "owner-b",
        }, self.k2, WITNESS_DOMAIN)
        self.denied(witness_head=wrong)

    def test_invalid_resource_and_trust_scope_fail_closed(self):
        self.denied(trusted=replace(self.trust, path="x/../y"))
        self.denied(trusted=replace(self.trust, repo="http://other/repo"))
        self.denied(trusted=replace(self.trust, tenant_id=""))
        self.denied(trusted=replace(self.trust, workspace_id=" wrong"))
        self.denied(trusted=replace(self.trust, floor_sequence=0))

    def test_readback_sha_content_and_integrity_require_exact_confirmed(self):
        failures = [
            {"status": "UNAVAILABLE"},
            {"status": "NOT_FOUND"},
            {"status": "ERROR"},
            {"status": "UNKNOWN_OUTCOME"},
            {"sha": "b" * 40},
            {"sha": ""},
            {"sha": True},
            {"checkpoint": None},
            {"checkpoint": []},
            {"integrity": {"state": "MISMATCH"}},
            {"integrity": {"state": "UNKNOWN"}},
            {"integrity": {"state": "MIGRATION_REQUIRED"}},
            {"integrity": {}},
        ]
        base = self.reader.return_value
        for change in failures:
            with self.subTest(change=change):
                self.reader.return_value = {**base, **change}
                d = self.read()
                self.assertEqual(d["status"], "BLOCKED")
                self.assertIsNone(d["checkpoint"])
                self.assertFalse(d["worker_authorized"])
        self.reader.return_value = base

    def test_read_exception_and_missing_reader_keep_data_hidden(self):
        self.reader.side_effect = TimeoutError("private secret in network exception")
        d = self.read()
        self.assertEqual(d["status"], "BLOCKED")
        self.assertEqual(d["reason"], "READ_EXCEPTION")
        self.assertNotIn("private secret", str(d))
        self.reader.side_effect = None
        self.denied(reader=None)

    def test_no_http_or_write_apis_in_reference(self):
        # Network dependencies are deliberately not installed in this isolated CI.
        # The denied reference read cannot invoke an injected reader.
        self.denied(source_proof=None)
        import ast
        from pathlib import Path
        source = Path("atlasquant_aion_runtime_source_boundary_ref_v1.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(source)
        network_roots = {"requests", "urllib", "http", "socket", "subprocess"}
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertFalse(imported & network_roots)

    def test_reader_called_once_only_after_two_independent_signatures(self):
        self.reader.reset_mock()
        d = self.read()
        self.assertEqual(d["status"], "REFERENCE_VERIFIED")
        self.assertEqual(self.reader.call_count, 1)
        self.reader.reset_mock()
        self.denied(witness_head=None)
        self.reader.assert_not_called()


if __name__ == "__main__":
    unittest.main()
