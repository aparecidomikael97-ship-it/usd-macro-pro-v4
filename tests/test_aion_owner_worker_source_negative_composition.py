"""Cross-stack NEGATIVE composition; no enrollment, secrets, or worker activation.

This validates on one source tree both the staged Owner/Chat contracts
and the permanently blocked (not enrolled) Global Worker checkpoint source.
It cannot prove real source authenticity, physical owner/device, or deployment.
"""
import unittest

from aion_chat.models import Scope
from atlasquant_access_control import (
    AccessUser, authenticate, hash_password, session_is_current,
)
from atlasquant_aion_owner_experience_v1 import (
    owner_binding, continuity_handoff,
)
from atlasquant_aion_chat_product_bridge import validate_product_binding
from atlasquant_aion_global_worker_source_gate_v1 import (
    independent_worker_source_preflight,
)
from atlasquant_aion_v2_four_role_key_enrollment_reference import (
    FALSE_GATES,
)


class AionOwnerWorkerSourceCompositionNoGo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pwd = "synthetic-password-only-composition"
        cls.user = AccessUser(
            username="test-owner", role="ADMIN",
            password_hash=hash_password(
                cls.pwd, salt=b"composition-salt-v1", iterations=200000,
            ),
        )
        cls.registry = {"test-owner": cls.user}

    def access(self):
        session = authenticate("test-owner", self.pwd, self.registry)
        self.assertIsNotNone(session)
        self.assertTrue(session_is_current(session, self.registry))
        return {
            "allowed": True, "mode": "AUTHENTICATED",
            "role": "ADMIN", "session": session,
        }

    @staticmethod
    def assertion():
        # Caller-built test fixture, deliberately NOT a genuine owner proof.
        return {
            "verified": True, "principal": "HUMAN_OWNER",
            "subject": "test-owner", "issuer": "synthetic-fixture",
        }

    def assertSourceDenied(self, config):
        result = independent_worker_source_preflight(config)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "INDEPENDENT_CHECKPOINT_SOURCE_UNAVAILABLE")
        for k in ("source_verified", "worker_authorized", "network_called", "safe_to_retry"):
            self.assertIs(result[k], False, k)
        self.assertTrue(result["reconciliation_required"])

    def test_admin_login_and_synthetic_owner_binding_cannot_admit_worker_source(self):
        access = self.access()
        self.assertTrue(
            validate_product_binding(
                access, Scope("test-owner", "synthetic-tenant", "synthetic-workspace")
            )["bound"]
        )
        owner = owner_binding(access, self.assertion())
        # Owner contract accepts caller-supplied verified assertion only as
        # a PLAN; it cannot be promoted to a real installed trust root.
        self.assertTrue(owner["bound"])
        self.assertFalse(owner["grants_authority"])
        self.assertFalse(owner["executes_action"])
        self.assertSourceDenied({
            "access": access, "owner": owner, "source_verified": True,
            "worker_authorized": True, "provider_approved": True,
        })

    def test_unbound_owner_and_rogue_root_are_still_blocked(self):
        access = self.access()
        self.assertFalse(owner_binding(access, None)["bound"])
        for cfg in (
            None,
            {},
            {"verified": True, "principal": "HUMAN_OWNER", "issuer": "user-input"},
            {"source_pin": "self-enrolled", "expected_generation": 100},
            {"checkpoint_sha": "a" * 40, "token": "synthetic-not-real"},
            {"witness": {"status": "READY", "proof": "self-reported"}},
            {"owner_approved": True, "device_attested": True, "admin_override": True},
        ):
            with self.subTest(cfg=cfg):
                self.assertSourceDenied(cfg)

    def test_handoff_digest_and_owner_credential_rotation_never_admit_source(self):
        access = self.access()
        owner = owner_binding(access, self.assertion())
        plan = continuity_handoff(
            source_device="DESKTOP", target_device="MOBILE",
            owner_subject="test-owner", conversation_id="a" * 32,
            last_turn_id="AION-TURN-" + "B" * 24,
            context={"mode": "TEACHING", "topic": "CRM", "slide": 2},
        )
        self.assertEqual(plan["state"], "HANDOFF_PREPARED_UNVERIFIED")
        self.assertFalse(plan["authorization_granted"])
        self.assertFalse(plan["can_resume_conversation"])
        self.assertFalse(plan["handoff_digest_is_signature"])
        self.assertSourceDenied({"owner_binding_digest": owner["binding_digest"],
                                 "handoff_digest": plan["handoff_digest"]})
        access["session"]["credential_fingerprint"] = "rotated-synthetic-fingerprint"
        rotated = owner_binding(access, self.assertion())
        self.assertNotEqual(owner["binding_digest"], rotated["binding_digest"])
        self.assertSourceDenied({"owner_binding_digest": rotated["binding_digest"]})

    def test_crypto_math_reference_never_claims_real_enrollment(self):
        for key in (
            "genesis_owner_identity_verified",
            "trusted_human_owner_consent",
            "owner_presence_verified",
            "owner_key_custody_verified",
            "collector_key_custody_verified",
            "physical_key_enrollment_performed",
            "externally_anchored_generation_verified",
            "public_key_registry_protected",
            "installer_authorized",
            "safe_to_resume",
        ):
            self.assertIs(FALSE_GATES[key], False, key)
        self.assertSourceDenied({"four_role_roster_math_valid": True})

    def test_revoked_or_expired_administrator_never_becomes_source_authority(self):
        a = self.access()
        self.assertTrue(owner_binding(a, self.assertion())["bound"])
        deactivated = AccessUser(
            username="test-owner", role="ADMIN",
            password_hash=self.user.password_hash, active=False,
        )
        self.assertFalse(session_is_current(a["session"], {"test-owner": deactivated}))
        denied_access = {**a, "allowed": False}
        self.assertFalse(owner_binding(denied_access, self.assertion())["bound"])
        self.assertSourceDenied({"revoked_admin_claim": a["session"],
                                 "owner_approved": True})


if __name__ == "__main__":
    unittest.main()
