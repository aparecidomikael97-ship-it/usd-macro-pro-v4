"""CI-only adversarial tests for triple-signed PREPARE-only enrollment ceremony."""
from __future__ import annotations

import base64
import copy
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from atlasquant_aion_rooted_owner_signed_binary_preflight_ci_v1 import (
    REGISTRY_SCHEMA, REGISTRY_PURPOSE, REGISTRY_DOMAIN,
    registry_signing_message,
)
from atlasquant_aion_rooted_collector_raw_evidence_preflight_v1 import (
    ENROLL_SCHEMA, ENROLL_PURPOSE, ENROLL_DOMAIN,
    SQLiteCollectorChallengeReplay,
)
from atlasquant_aion_owner_cosigned_collector_root_ceremony_v1 import (
    SCHEMA, PURPOSE, STATE, DOMAIN, POP_DOMAIN,
    proposal_signing_material, verify_owner_cosigned_collector_root_ceremony,
)


def canonical(x):
    return json.dumps(x, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def b64(b):
    return base64.b64encode(b).decode("ascii")


def pub(k):
    return k.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def digest(b):
    return "sha256:" + sha256(b).hexdigest()


class OwnerCollectorCeremonyTests(unittest.TestCase):
    def setUp(self):
        self.now = 1800200000
        self.reg_root = Ed25519PrivateKey.generate()
        self.owner = Ed25519PrivateKey.generate()
        self.witness = Ed25519PrivateKey.generate()
        self.proposed_root = Ed25519PrivateKey.generate()
        self.collector = Ed25519PrivateKey.generate()
        self.host_digest = digest(b"HOST-MEASURED-CI-ONLY")
        self.device_digest = digest(b"DEVICE-ENROLLED-CI-ONLY")
        self.binary_digest = digest(b"INDEPENDENT-BINARY-OBSERVATION-CI-ONLY")
        self.manifest_digest = digest(b"INDEPENDENT-MANIFEST-OBSERVATION-CI-ONLY")

    def owner_registry(self):
        return {
            "schema": REGISTRY_SCHEMA,
            "purpose": REGISTRY_PURPOSE,
            "registry_id": "owner-host-registry",
            "owner_subject": "synthetic-human-owner",
            "host_issuer": "synthetic-host-policy",
            "epoch": 4, "issued_at": self.now - 60,
            "expires_at": self.now + 900,
            "owner_keys": [{
                "key_id": "owner-active-4",
                "public_key_b64": b64(pub(self.owner)),
                "enrolled_epoch": 4, "revoked_epoch": None, "supersedes": None,
            }],
            "devices": [{
                "device_id": "owner-windows-device-1",
                "binding_digest": self.device_digest,
                "enrolled_epoch": 4, "revoked_epoch": None,
            }],
        }

    def snapshot(self, epoch=1):
        return {
            "schema": ENROLL_SCHEMA, "purpose": ENROLL_PURPOSE,
            "registry_id": "owner-host-registry",
            "host_issuer": "synthetic-host-policy",
            "host_binding_digest": self.host_digest,
            "device_binding_digest": self.device_digest,
            "epoch": epoch,
            "issued_at": self.now - 20,
            "expires_at": self.now + 400,
            "collector": {
                "collector_id": "aion-collector",
                "key_id": "collected-ephemeral-key",
                "public_key_b64": b64(pub(self.collector)),
                "binary_digest": self.binary_digest,
                "manifest_digest": self.manifest_digest,
                "enrolled_epoch": epoch,
                "revoked_epoch": None,
            },
        }

    def proposal(self, owner_reg_raw, snapshot_raw, *,
                 mode="INITIAL_ENROLLMENT", previous=0, prior_root=None):
        return {
            "schema": SCHEMA, "purpose": PURPOSE,
            "mode": mode,
            "owner_registry_digest": digest(REGISTRY_DOMAIN + owner_reg_raw),
            "owner_key_id": "owner-active-4",
            "host_binding_digest": self.host_digest,
            "device_binding_digest": self.device_digest,
            "registry_id": "owner-host-registry",
            "host_issuer": "synthetic-host-policy",
            "collector_id": "aion-collector",
            "collector_epoch": previous + 1,
            "protected_previous_epoch": previous,
            "prior_root_fingerprint": prior_root,
            "proposed_root_public_key_b64": b64(pub(self.proposed_root)),
            "proposed_root_fingerprint": digest(pub(self.proposed_root)),
            "witness_fingerprint": digest(pub(self.witness)),
            "collector_binary_digest": self.binary_digest,
            "collector_manifest_digest": self.manifest_digest,
            "proposed_snapshot_digest": digest(snapshot_raw),
            "challenge_nonce": "d4" * 32,
            "issued_at": self.now - 2,
            "expires_at": self.now + 80,
        }

    def build(self, *, previous=0, prior_root=None):
        reg = canonical(self.owner_registry())
        snap = canonical(self.snapshot(epoch=previous + 1))
        proposal = self.proposal(
            reg, snap, mode="ROTATION" if previous else "INITIAL_ENROLLMENT",
            previous=previous, prior_root=prior_root)
        return {"registry": reg, "snapshot": snap, "proposal": proposal}

    def invoke(self, td, *, case=None, registry_sig=None,
               owner_sig=None, witness_sig=None,
               proposed_pop_sig=None, snapshot_sig=None,
               root_policy=None, owner_registry_root=None, witness_key=None,
               previous_epoch=0, previous_root=None, now=None,
               minimum_owner_epoch=4, snapshot_raw=None, proposal_raw=None,
               store="auto", observed_binary=None, observed_manifest=None):
        case = case if case is not None else self.build(
            previous=previous_epoch, prior_root=previous_root)
        reg_raw = case["registry"]
        snap_raw = case["snapshot"] if snapshot_raw is None else snapshot_raw
        raw = canonical(case["proposal"]) if proposal_raw is None else proposal_raw
        registry_sig = registry_sig or b64(
            self.reg_root.sign(REGISTRY_DOMAIN + reg_raw))
        owner_sig = owner_sig or b64(self.owner.sign(DOMAIN + raw))
        witness_sig = witness_sig or b64(self.witness.sign(DOMAIN + raw))
        proposed_pop_sig = proposed_pop_sig or b64(
            self.proposed_root.sign(POP_DOMAIN + raw))
        snapshot_sig = snapshot_sig or b64(
            self.proposed_root.sign(ENROLL_DOMAIN + snap_raw))
        root_policy = pub(self.reg_root) if root_policy is None else root_policy
        witness_key = pub(self.witness) if witness_key is None else witness_key
        if store == "auto":
            store = SQLiteCollectorChallengeReplay(
                Path(td) / "ceremony-nonces.sqlite3")
        return verify_owner_cosigned_collector_root_ceremony(
            raw, owner_sig, witness_sig, proposed_pop_sig,
            snap_raw, snapshot_sig, reg_raw, registry_sig,
            pinned_owner_registry_root_public_key=root_policy,
            expected_owner_registry_root_fingerprint=digest(root_policy),
            expected_owner_registry_id="owner-host-registry",
            expected_owner_subject="synthetic-human-owner",
            expected_host_issuer="synthetic-host-policy",
            expected_device_id="owner-windows-device-1",
            expected_device_binding_digest=self.device_digest,
            minimum_owner_registry_epoch=minimum_owner_epoch,
            expected_host_binding_digest=self.host_digest,
            expected_collector_id="aion-collector",
            pinned_independent_witness_public_key=witness_key,
            expected_independent_witness_fingerprint=digest(witness_key),
            protected_previous_collector_epoch=previous_epoch,
            pinned_previous_collector_root_fingerprint=previous_root,
            independently_observed_collector_binary_digest=(
                self.binary_digest if observed_binary is None else observed_binary),
            independently_observed_collector_manifest_digest=(
                self.manifest_digest if observed_manifest is None else observed_manifest),
            now=self.now if now is None else now, nonce_store=store,
        )

    def no_authority(self, result):
        self.assertEqual(result["trusted_host_policy_mutated"], False)
        for field in (
            "physical_root_custody_verified",
            "root_enrolled_in_production",
            "collector_enrolled_in_production",
            "collector_launch_authorized",
            "physical_attestation_verified",
            "network_deny_verified",
            "installer_authorized", "build_authorized",
            "deploy_authorized", "safe_to_resume",
        ):
            self.assertIs(result[field], False, field)

    def test_valid_bootstrap_is_untrusted_prepare_only(self):
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td)
        self.assertEqual(result["state"], STATE, result)
        for field in (
            "rooted_owner_signature_checked",
            "independent_witness_signature_checked",
            "proposed_root_proof_of_possession_checked",
            "proposed_snapshot_signature_checked", "nonce_consumed",
        ):
            self.assertTrue(result[field], field)
        self.assertEqual(result["collector_epoch"], 1)
        self.no_authority(result)

    def test_valid_rotation_is_also_prepare_only(self):
        prior = digest(b"PINNED-PREVIOUS-COLLECTOR-ROOT")
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(
                td, previous_epoch=4, previous_root=prior)
        self.assertEqual(result["state"], STATE, result)
        self.assertEqual(result["collector_epoch"], 5)
        self.no_authority(result)

    def test_replay_after_reopen_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "nonces.db"
            a = self.invoke(td, store=SQLiteCollectorChallengeReplay(p))
            b = self.invoke(td, store=SQLiteCollectorChallengeReplay(p))
        self.assertEqual(a["state"], STATE)
        self.assertEqual(b["reason"], "CEREMONY_NONCE_REPLAY_OR_STORE_FAILURE")
        self.no_authority(b)

    def test_replay_when_payload_changed_but_signatures_renewed(self):
        with tempfile.TemporaryDirectory() as td:
            store = SQLiteCollectorChallengeReplay(Path(td) / "nonces.db")
            a = self.invoke(td, store=store)
            changed = self.build()
            changed["proposal"]["expires_at"] = self.now + 90
            b = self.invoke(td, case=changed, store=store)
        self.assertEqual(a["state"], STATE)
        self.assertEqual(b["reason"], "CEREMONY_NONCE_REPLAY_OR_STORE_FAILURE")

    def test_owner_signature_cannot_be_attacker_self_signature(self):
        with tempfile.TemporaryDirectory() as td:
            c = self.build()
            sig = b64(Ed25519PrivateKey.generate().sign(
                DOMAIN + canonical(c["proposal"])))
            result = self.invoke(td, case=c, owner_sig=sig)
        self.assertEqual(result["reason"], "ROOTED_OWNER_APPROVAL_SIGNATURE_INVALID")
        self.no_authority(result)

    def test_owner_registry_root_signature_cannot_be_substituted(self):
        with tempfile.TemporaryDirectory() as td:
            c = self.build()
            sig = b64(Ed25519PrivateKey.generate().sign(
                REGISTRY_DOMAIN + c["registry"]))
            result = self.invoke(td, case=c, registry_sig=sig)
        self.assertTrue(result["reason"].startswith("PREEXISTING_OWNER_TRUST_FAILED:"))
        self.no_authority(result)

    def test_expired_owner_registry_fails(self):
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, now=self.now + 2000)
        self.assertEqual(result["state"], "BLOCKED")
        self.no_authority(result)

    def test_witness_signature_required(self):
        with tempfile.TemporaryDirectory() as td:
            sig = b64(Ed25519PrivateKey.generate().sign(
                DOMAIN + canonical(self.build()["proposal"])))
            result = self.invoke(td, witness_sig=sig)
        self.assertEqual(result["reason"], "INDEPENDENT_WITNESS_SIGNATURE_INVALID")

    def test_different_host_pinned_witness_rejects_signature(self):
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, witness_key=pub(Ed25519PrivateKey.generate()))
        self.assertEqual(result["reason"], "PROPOSAL_NOT_EQUAL_INDEPENDENT_HOST_POLICY")

    def test_proposed_root_must_possess_private_key(self):
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, proposed_pop_sig=b64(
                Ed25519PrivateKey.generate().sign(
                    POP_DOMAIN + canonical(self.build()["proposal"]))))
        self.assertEqual(result["reason"], "PROPOSED_ROOT_PROOF_OR_SNAPSHOT_SIGNATURE_INVALID")

    def test_proposed_root_must_sign_exact_snapshot(self):
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, snapshot_sig=b64(
                Ed25519PrivateKey.generate().sign(
                    ENROLL_DOMAIN + self.build()["snapshot"])))
        self.assertEqual(result["reason"], "PROPOSED_ROOT_PROOF_OR_SNAPSHOT_SIGNATURE_INVALID")

    def test_no_protected_prior_epoch_bypass(self):
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, previous_epoch=5)
        self.assertEqual(result["reason"], "CEREMONY_MALFORMED")

    def test_bootstrap_with_existing_root_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, previous_root=digest(b"prior"))
        self.assertEqual(result["reason"], "CEREMONY_MALFORMED")

    def test_rotation_downgrade_to_bootstrap_rejected(self):
        prior = digest(b"PRIOR_ROOT")
        with tempfile.TemporaryDirectory() as td:
            case = self.build()
            result = self.invoke(
                td, case=case, previous_epoch=1, previous_root=prior)
        self.assertEqual(result["reason"], "PROPOSAL_NOT_EQUAL_INDEPENDENT_HOST_POLICY")

    def test_root_rotation_cannot_reuse_same_key(self):
        with tempfile.TemporaryDirectory() as td:
            prior = digest(pub(self.proposed_root))
            result = self.invoke(
                td, previous_epoch=1, previous_root=prior)
        self.assertEqual(result["reason"], "ROOT_ROTATION_REUSES_OLD_KEY")

    def test_wrong_observed_binary_not_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, observed_binary=digest(b"other"))
        self.assertEqual(result["reason"], "PROPOSAL_NOT_EQUAL_INDEPENDENT_HOST_POLICY")

    def test_wrong_observed_manifest_not_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, observed_manifest=digest(b"other"))
        self.assertEqual(result["reason"], "PROPOSAL_NOT_EQUAL_INDEPENDENT_HOST_POLICY")

    def test_signed_proposal_changes_detection(self):
        with tempfile.TemporaryDirectory() as td:
            case = self.build()
            case["proposal"]["expires_at"] = self.now + 75
            sig = b64(self.owner.sign(
                DOMAIN + canonical(self.build()["proposal"])))
            result = self.invoke(td, case=case, owner_sig=sig)
        self.assertEqual(result["reason"], "ROOTED_OWNER_APPROVAL_SIGNATURE_INVALID")

    def test_mismatched_snapshot_digest(self):
        with tempfile.TemporaryDirectory() as td:
            case = self.build()
            case["proposal"]["proposed_snapshot_digest"] = digest(b"wrong-snapshot")
            result = self.invoke(td, case=case)
        self.assertEqual(result["reason"], "PROPOSED_SNAPSHOT_MISMATCH")

    def test_mismatched_collector_id(self):
        with tempfile.TemporaryDirectory() as td:
            case = self.build()
            case["snapshot"] = canonical({
                **self.snapshot(), "collector": {
                    **self.snapshot()["collector"], "collector_id": "different"}})
            case["proposal"]["proposed_snapshot_digest"] = digest(case["snapshot"])
            result = self.invoke(td, case=case)
        self.assertEqual(result["reason"], "PROPOSED_SNAPSHOT_MISMATCH")

    def test_swapped_snapshot_key_role_cannot_be_reused(self):
        with tempfile.TemporaryDirectory() as td:
            case = self.build()
            snapshot = self.snapshot()
            snapshot["collector"]["public_key_b64"] = b64(pub(self.proposed_root))
            case["snapshot"] = canonical(snapshot)
            case["proposal"]["proposed_snapshot_digest"] = digest(case["snapshot"])
            result = self.invoke(td, case=case)
        self.assertEqual(result["reason"], "COLLECTOR_SIGNER_ROLE_REUSE")

    def test_same_owner_and_witness_key_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            case = self.build()
            case["proposal"]["witness_fingerprint"] = digest(pub(self.owner))
            result = self.invoke(td, case=case, witness_key=pub(self.owner),
                                 witness_sig=b64(self.owner.sign(
                                     DOMAIN + canonical(case["proposal"]))))
        self.assertEqual(result["reason"], "SEPARATE_SIGNER_ROLES_REQUIRED")

    def test_nonce_store_required(self):
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, store=None)
        self.assertEqual(result["reason"], "DURABLE_CEREMONY_REPLAY_REQUIRED")

    def test_expired_ceremony_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            case = self.build()
            case["proposal"]["expires_at"] = self.now - 1
            result = self.invoke(td, case=case)
        self.assertEqual(result["reason"], "CEREMONY_MALFORMED")

    def test_epoch_is_strict_increment(self):
        with tempfile.TemporaryDirectory() as td:
            case = self.build()
            case["proposal"]["collector_epoch"] = 500
            result = self.invoke(td, case=case)
        self.assertEqual(result["reason"], "CEREMONY_MALFORMED")

    def test_duplicate_json_properties_block(self):
        with tempfile.TemporaryDirectory() as td:
            case = self.build()
            malformed = canonical(case["proposal"]).replace(
                b'"schema":', b'"schema":"fake","schema":', 1)
            result = self.invoke(td, case=case, proposal_raw=malformed)
        self.assertEqual(result["reason"], "CEREMONY_MALFORMED")

    def test_extra_self_approval_field_block(self):
        with tempfile.TemporaryDirectory() as td:
            case = self.build()
            case["proposal"]["activate_collector_root"] = True
            result = self.invoke(td, case=case)
        self.assertEqual(result["reason"], "CEREMONY_MALFORMED")

    def test_empty_or_bad_public_key_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            case = self.build()
            case["proposal"]["proposed_root_public_key_b64"] = "bad"
            result = self.invoke(td, case=case)
        self.assertEqual(result["reason"], "CEREMONY_MALFORMED")

    def test_bounded_input_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, proposal_raw=b"x" * 6145)
        self.assertEqual(result["reason"], "CEREMONY_MALFORMED")

    def test_bad_signature_does_not_consume_nonce(self):
        with tempfile.TemporaryDirectory() as td:
            store = SQLiteCollectorChallengeReplay(Path(td) / "ceremony.db")
            bad = self.invoke(td, owner_sig=b64(b"z" * 64), store=store)
            good = self.invoke(td, store=store)
        self.assertEqual(bad["reason"], "ROOTED_OWNER_APPROVAL_SIGNATURE_INVALID")
        self.assertEqual(good["state"], STATE)

    def test_owner_device_revoked_denied(self):
        with tempfile.TemporaryDirectory() as td:
            case = self.build()
            old = json.loads(case["registry"])
            old["devices"][0]["revoked_epoch"] = 4
            case["registry"] = canonical(old)
            case["proposal"]["owner_registry_digest"] = digest(
                REGISTRY_DOMAIN + case["registry"])
            result = self.invoke(td, case=case)
        self.assertTrue(result["reason"].startswith("PREEXISTING_OWNER_TRUST_FAILED:"))

    def test_owner_epoch_rollback_denied(self):
        with tempfile.TemporaryDirectory() as td:
            result = self.invoke(td, minimum_owner_epoch=5)
        self.assertTrue(result["reason"].startswith("PREEXISTING_OWNER_TRUST_FAILED:"))


if __name__ == "__main__":
    unittest.main()
