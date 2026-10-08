"""Adversarial synthetic CI tests of exact host-policy provenance gate."""
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

import test_atlasquant_aion_owner_cosigned_collector_root_ceremony_v1 as existing
from atlasquant_aion_rooted_collector_raw_evidence_preflight_v1 import (
    SQLiteCollectorChallengeReplay,
)
from atlasquant_aion_protected_host_policy_provenance_v1 import (
    POLICY_SCHEMA, POLICY_PURPOSE, POLICY_DOMAIN, STATE,
    host_policy_signing_material,
    verify_anchored_host_policy_and_collector_ceremony,
)


def canonical(obj):
    return json.dumps(obj, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def b64(raw):
    return base64.b64encode(raw).decode("ascii")


def public(key):
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def digest(raw):
    return "sha256:" + sha256(raw).hexdigest()


class HostPolicyProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.fixture = existing.OwnerCollectorCeremonyTests()
        self.fixture.setUp()
        self.now = self.fixture.now
        self.authority = Ed25519PrivateKey.generate()

    def case(self, *, policy_epoch=1, previous_policy=None,
             collector_epoch=0, previous_collector_root=None):
        f = self.fixture
        old_case = f.build(
            previous=collector_epoch, prior_root=previous_collector_root)
        policy = {
            "schema": POLICY_SCHEMA, "purpose": POLICY_PURPOSE,
            "authority_id": "aion-host-provenance-root",
            "policy_epoch": policy_epoch,
            "previous_policy_digest": previous_policy,
            "issued_at": self.now - 10,
            "expires_at": self.now + 600,
            "owner_registry_root_fingerprint": digest(public(f.reg_root)),
            "owner_registry_id": "owner-host-registry",
            "owner_subject": "synthetic-human-owner",
            "owner_host_issuer": "synthetic-host-policy",
            "owner_device_id": "owner-windows-device-1",
            "minimum_owner_registry_epoch": 4,
            "host_binding_digest": f.host_digest,
            "device_binding_digest": f.device_digest,
            "collector_id": "aion-collector",
            "protected_collector_epoch": collector_epoch,
            "previous_collector_root_fingerprint": previous_collector_root,
            "witness_public_key_b64": b64(public(f.witness)),
            "witness_fingerprint": digest(public(f.witness)),
            "approved_collector_binary_digest": f.binary_digest,
            "approved_collector_manifest_digest": f.manifest_digest,
        }
        return {"old_case": old_case, "policy": policy}

    def invoke(self, td, *, case=None, authority=None, root_policy=None,
               authority_signature=None, expected_authority_fp=None,
               protected_digest=None, protected_epoch=None,
               owner_registry_root=None, ceremony_owner_signature=None,
               ceremony_witness_signature=None,
               ceremony_root_pop_signature=None, ceremony_snapshot_signature=None,
               ceremony_proposal_raw=None, owner_registry_raw=None,
               raw_policy=None, now=None, store="auto"):
        f = self.fixture
        case = self.case() if case is None else case
        old = case["old_case"]
        policy = case["policy"]
        raw = canonical(policy) if raw_policy is None else raw_policy
        authority = self.authority if authority is None else authority
        root_policy = public(self.authority) if root_policy is None else root_policy
        authority_signature = (b64(authority.sign(POLICY_DOMAIN + raw))
                               if authority_signature is None else authority_signature)
        old_reg = old["registry"] if owner_registry_raw is None else owner_registry_raw
        original_proposal = canonical(old["proposal"])
        prop = original_proposal if ceremony_proposal_raw is None else ceremony_proposal_raw
        owner_sig = (b64(f.owner.sign(existing.DOMAIN + prop))
                     if ceremony_owner_signature is None else ceremony_owner_signature)
        witness_sig = (b64(f.witness.sign(existing.DOMAIN + prop))
                       if ceremony_witness_signature is None else ceremony_witness_signature)
        root_sig = (b64(f.proposed_root.sign(existing.POP_DOMAIN + prop))
                    if ceremony_root_pop_signature is None else ceremony_root_pop_signature)
        snap_sig = (b64(f.proposed_root.sign(existing.ENROLL_DOMAIN + old["snapshot"]))
                    if ceremony_snapshot_signature is None else ceremony_snapshot_signature)
        if store == "auto":
            store = SQLiteCollectorChallengeReplay(Path(td) / "nonce.sqlite3")
        return verify_anchored_host_policy_and_collector_ceremony(
            raw,
            authority_signature,
            prop,
            owner_sig, witness_sig,
            root_sig,
            old["snapshot"], snap_sig,
            old_reg, b64(f.reg_root.sign(existing.REGISTRY_DOMAIN + old_reg)),
            independently_pinned_policy_authority_public_key=root_policy,
            expected_policy_authority_fingerprint=(
                digest(public(self.authority))
                if expected_authority_fp is None else expected_authority_fp
            ),
            protected_exact_policy_digest=(
                digest(POLICY_DOMAIN + canonical(self.case()["policy"]))
                if protected_digest is None else protected_digest
            ),
            protected_exact_policy_epoch=(
                1 if protected_epoch is None else protected_epoch
            ),
            independently_pinned_owner_registry_root_public_key=(
                public(f.reg_root) if owner_registry_root is None else owner_registry_root
            ),
            now=self.now if now is None else now,
            ceremony_nonce_store=store,
        )

    def anchored(self, case):
        return {
            "protected_digest": digest(POLICY_DOMAIN + canonical(case["policy"])),
            "protected_epoch": case["policy"]["policy_epoch"],
        }

    def no_authority(self, result):
        for key in (
            "protected_host_source_independently_verified",
            "hardware_antirollback_verified", "owner_real_identity_enrolled",
            "collector_root_enrolled_in_production", "collector_launch_authorized",
            "physical_attestation_verified", "network_deny_verified",
            "safe_to_resume", "installer_authorized", "build_authorized",
            "deploy_authorized", "host_trust_state_modified",
        ):
            self.assertIs(result[key], False, key)

    def test_exact_pinned_genesis_prepare_is_still_untrusted(self):
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td)
        self.assertEqual(result["state"], STATE, result)
        self.assertTrue(result["authority_signature_valid"])
        self.assertTrue(result["policy_digest_matches_protected_anchor"])
        self.assertTrue(result["ceremony_prepared_cryptographically"])
        self.no_authority(result)

    def test_policy_epoch_rotation_proposal_also_stays_untrusted(self):
        case = self.case(
            policy_epoch=5, previous_policy=digest(b"host-pinned-prev-policy"),
            collector_epoch=4,
            previous_collector_root=digest(b"host-pinned-previous-collector-root"),
        )
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, case=case, **self.anchored(case))
        self.assertEqual(result["state"], STATE, result)
        self.assertEqual(result["verified_policy_epoch"], 5)
        self.no_authority(result)

    def test_rollback_to_old_policy_rejected_even_if_validly_signed(self):
        case = self.case()
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, case=case, protected_epoch=2,
                                 protected_digest=digest(b"future-pinned-policy"))
        self.assertEqual(result["reason"], "HOST_POLICY_EPOCH_ROLLBACK_OR_MISMATCH")
        self.no_authority(result)

    def test_same_epoch_fork_with_valid_signature_is_rejected(self):
        case = self.case()
        case["policy"]["expires_at"] += 60
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, case=case)
        self.assertEqual(result["reason"], "HOST_POLICY_DIGEST_NOT_PROTECTED")

    def test_policy_substitution_with_wrong_anchor_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, protected_digest=digest(b"wrong-anchor"))
        self.assertEqual(result["reason"], "HOST_POLICY_DIGEST_NOT_PROTECTED")

    def test_authority_attacker_key_swap_rejected(self):
        attacker = Ed25519PrivateKey.generate()
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, authority=attacker)
        self.assertEqual(result["reason"], "HOST_POLICY_AUTHORITY_SIGNATURE_INVALID")

    def test_wrong_pinned_authority_public_key_rejected(self):
        attacker = Ed25519PrivateKey.generate()
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, root_policy=public(attacker))
        self.assertEqual(result["reason"], "HOST_POLICY_AUTHORITY_KEY_UNPINNED")

    def test_wrong_expected_root_fingerprint_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, expected_authority_fp=digest(b"fake"))
        self.assertEqual(result["reason"], "HOST_POLICY_AUTHORITY_KEY_UNPINNED")

    def test_owner_registry_root_swapped_rejected(self):
        attacker = Ed25519PrivateKey.generate()
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, owner_registry_root=public(attacker))
        self.assertEqual(result["reason"], "OWNER_REGISTRY_ROOT_NOT_IN_SIGNED_POLICY")

    def test_witness_substitution_in_signed_policy_cannot_use_prior_anchor(self):
        case = self.case()
        key = Ed25519PrivateKey.generate()
        case["policy"]["witness_public_key_b64"] = b64(public(key))
        case["policy"]["witness_fingerprint"] = digest(public(key))
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, case=case)
        self.assertEqual(result["reason"], "HOST_POLICY_DIGEST_NOT_PROTECTED")

    def test_role_collision_policy_authority_and_witness_rejected(self):
        case = self.case()
        case["policy"]["witness_public_key_b64"] = b64(public(self.authority))
        case["policy"]["witness_fingerprint"] = digest(public(self.authority))
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, case=case, **self.anchored(case))
        self.assertEqual(result["reason"], "HOST_POLICY_SIGNER_ROLE_COLLISION")

    def test_bad_owner_signature_rejected_downstream(self):
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(
                td, ceremony_owner_signature=b64(b"x" * 64))
        self.assertEqual(result["reason"],
                         "CEREMONY_REJECTED:ROOTED_OWNER_APPROVAL_SIGNATURE_INVALID")

    def test_bad_witness_signature_rejected_downstream(self):
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(
                td, ceremony_witness_signature=b64(b"x" * 64))
        self.assertEqual(result["reason"],
                         "CEREMONY_REJECTED:INDEPENDENT_WITNESS_SIGNATURE_INVALID")

    def test_bad_proposed_root_pop_rejected_downstream(self):
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(
                td, ceremony_root_pop_signature=b64(b"x" * 64))
        self.assertEqual(result["reason"],
                         "CEREMONY_REJECTED:PROPOSED_ROOT_PROOF_OR_SNAPSHOT_SIGNATURE_INVALID")

    def test_bad_proposed_snapshot_signature_rejected_downstream(self):
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(
                td, ceremony_snapshot_signature=b64(b"x" * 64))
        self.assertEqual(result["reason"],
                         "CEREMONY_REJECTED:PROPOSED_ROOT_PROOF_OR_SNAPSHOT_SIGNATURE_INVALID")

    def test_policy_expiry_blocks(self):
        case = self.case()
        case["policy"]["issued_at"] = self.now - 86420
        case["policy"]["expires_at"] = self.now - 30
        # Invalid TTL or stale both fail closed, never gain authority.
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, case=case)
        self.assertEqual(result["state"], "BLOCKED")
        self.no_authority(result)

    def test_current_policy_expired_at_timestamp_blocks(self):
        case = self.case()
        case["policy"]["issued_at"] = self.now - 600
        case["policy"]["expires_at"] = self.now - 1
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, case=case, **self.anchored(case))
        self.assertEqual(result["reason"], "HOST_POLICY_STALE")

    def test_bad_policy_epoch_bool_rejected(self):
        case = self.case()
        case["policy"]["policy_epoch"] = True
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, case=case)
        self.assertEqual(result["reason"], "HOST_POLICY_MALFORMED")

    def test_genesis_cannot_claim_previous_policy_digest(self):
        case = self.case()
        case["policy"]["previous_policy_digest"] = digest(b"forged")
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, case=case)
        self.assertEqual(result["reason"], "HOST_POLICY_MALFORMED")

    def test_policy_epoch_gt_one_requires_previous_digest(self):
        case = self.case(policy_epoch=2)
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, case=case)
        self.assertEqual(result["reason"], "HOST_POLICY_MALFORMED")

    def test_collector_epoch_gt_zero_requires_prior_root(self):
        case = self.case()
        case["policy"]["protected_collector_epoch"] = 4
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, case=case)
        self.assertEqual(result["reason"], "HOST_POLICY_MALFORMED")

    def test_duplicate_json_field_rejected(self):
        case = self.case()
        corrupted = canonical(case["policy"]).replace(
            b'"schema":', b'"schema":"other","schema":', 1)
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, case=case, raw_policy=corrupted)
        self.assertEqual(result["reason"], "HOST_POLICY_MALFORMED")

    def test_extra_self_authorization_field_rejected(self):
        case = self.case()
        case["policy"]["installer_authorized"] = True
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, case=case)
        self.assertEqual(result["reason"], "HOST_POLICY_MALFORMED")

    def test_noncanonical_json_whitespace_rejected(self):
        case = self.case()
        loose = json.dumps(case["policy"]).encode("utf-8")
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, case=case, raw_policy=loose)
        self.assertEqual(result["reason"], "HOST_POLICY_MALFORMED")

    def test_oversized_policy_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, raw_policy=b"x" * 8193)
        self.assertEqual(result["reason"], "HOST_POLICY_MALFORMED")

    def test_no_nonce_store_cannot_prepare(self):
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, store=None)
        self.assertEqual(result["reason"],
                         "CEREMONY_REJECTED:DURABLE_CEREMONY_REPLAY_REQUIRED")

    def test_same_nonce_replay_rejected_after_store_reopen(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "nonce.sqlite3"
            first = self.invoke(td, store=SQLiteCollectorChallengeReplay(db))
            second = self.invoke(td, store=SQLiteCollectorChallengeReplay(db))
        self.assertEqual(first["state"], STATE)
        self.assertEqual(second["reason"],
                         "CEREMONY_REJECTED:CEREMONY_NONCE_REPLAY_OR_STORE_FAILURE")

    def test_bad_authority_signature_does_not_burn_ceremony_nonce(self):
        with tempfile.TemporaryDirectory() as td:
            db = SQLiteCollectorChallengeReplay(Path(td) / "nonce.sqlite3")
            bad = self.invoke(td, authority_signature=b64(b"x" * 64), store=db)
            good = self.invoke(td, store=db)
        self.assertEqual(bad["reason"], "HOST_POLICY_AUTHORITY_SIGNATURE_INVALID")
        self.assertEqual(good["state"], STATE)

    def test_stale_owner_registration_rejected(self):
        case = self.case()
        bad = json.loads(case["old_case"]["registry"])
        bad["epoch"] = 3
        bad["owner_keys"][0]["enrolled_epoch"] = 3
        bad["devices"][0]["enrolled_epoch"] = 3
        reg = canonical(bad)
        # Proposal will reject rooted owner's stale trust even with a re-signed registry.
        # The proposal itself is unchanged, preventing a self-asserted downgrade.
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, case=case, owner_registry_raw=reg)
        self.assertEqual(result["state"], "BLOCKED")
        self.no_authority(result)

    def test_host_policy_is_data_only_and_never_enrolls(self):
        case = self.case()
        message = host_policy_signing_material(case["policy"])
        self.assertEqual(message, POLICY_DOMAIN + canonical(case["policy"]))
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td)
        self.no_authority(result)


if __name__ == "__main__":
    unittest.main()
