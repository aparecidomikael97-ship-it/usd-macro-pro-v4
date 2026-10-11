"""Offline cross-stack contract tests: owner login, AION chat and safe handoff.

No external owner attestation, tenant enrollment, Worker, provider or desktop
agent is created by this test. All identities and credentials are synthetic.
"""
import unittest

from aion_chat.models import Scope
from atlasquant_access_control import (
    AccessUser, authenticate, hash_password, session_is_current,
)
from atlasquant_aion_chat_product_bridge import validate_product_binding
from atlasquant_aion_owner_experience_v1 import (
    continuity_handoff, owner_binding, command_plan,
)


class OwnerChatContractIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password = "synthetic-local-password-only"
        user = AccessUser(
            username="test-owner", role="ADMIN",
            password_hash=hash_password(
                cls.password, salt=b"synthetic-salt-16", iterations=200000
            ),
        )
        cls.registry = {"test-owner": user}

    def access(self):
        session = authenticate("test-owner", self.password, self.registry)
        self.assertIsNotNone(session)
        self.assertTrue(session_is_current(session, self.registry))
        return {
            "allowed": True,
            "mode": "AUTHENTICATED",
            "role": session["role"],
            "session": session,
        }

    @staticmethod
    def synthetic_assertion():
        # This is TEST input, not a trustworthy production owner attestation.
        return {
            "verified": True, "principal": "HUMAN_OWNER",
            "subject": "test-owner", "issuer": "synthetic-test-issuer",
        }

    def test_authenticated_login_matches_owner_and_chat_structural_contracts(self):
        access = self.access()
        scope = Scope("test-owner", "synthetic-tenant", "synthetic-workspace")
        self.assertTrue(validate_product_binding(access, scope)["bound"])
        # A successful ADMIN login alone must never self-enroll HUMAN_OWNER.
        self.assertFalse(owner_binding(access, None)["bound"])
        owner = owner_binding(access, self.synthetic_assertion())
        self.assertTrue(owner["bound"])
        self.assertFalse(owner["grants_authority"])
        self.assertFalse(owner["executes_action"])
        self.assertFalse(
            validate_product_binding(
                access, Scope("other-owner", "synthetic-tenant", "synthetic-workspace")
            )["bound"]
        )
        self.assertFalse(
            owner_binding(access, {**self.synthetic_assertion(), "subject": "other-owner"})["bound"]
        )

    def test_stale_login_or_open_mode_cannot_bind_owner_or_scoped_chat(self):
        access = self.access()
        scope = Scope("test-owner", "synthetic-tenant", "synthetic-workspace")
        bad = [
            {**access, "mode": "OPEN"},
            {**access, "allowed": False},
            {**access, "role": "USER"},
            {**access, "session": {**access["session"], "permissions": ["app:read"]}},
            {**access, "session": {**access["session"], "credential_fingerprint": ""}},
        ]
        for value in bad:
            with self.subTest(mode=value.get("mode"), role=value.get("role")):
                self.assertFalse(owner_binding(value, self.synthetic_assertion())["bound"])
                self.assertFalse(validate_product_binding(value, scope)["bound"])

    def test_handoff_contains_only_enumerated_metadata_and_no_session_material(self):
        result = continuity_handoff(
            source_device="desktop", target_device="mobile",
            owner_subject="test-owner", conversation_id="b" * 32,
            last_turn_id="AION-TURN-" + "B" * 24,
            context={"mode": "teaching", "topic": "CRM", "slide": 7},
        )
        self.assertEqual(
            result["context"], {"mode": "TEACHING", "topic": "CRM", "slide": 7}
        )
        self.assertTrue(result["requires_target_reauthentication"])
        self.assertFalse(result["authentication_transferred"])
        self.assertFalse(result["session_token_transferred"])
        self.assertFalse(result["executes_action"])
        self.assertNotIn(self.access()["session"]["credential_fingerprint"], str(result))

    def test_unknown_or_secret_bearing_context_is_rejected_not_silently_redacted(self):
        cases = (
            {"accessToken": "TEST_PRIVATE_TOKEN"},
            {"sessionId": "TEST_PRIVATE_TOKEN"},
            {"topic": "Bearer TEST_PRIVATE_TOKEN"},
            {"notes": {"accessToken": "TEST_PRIVATE_TOKEN"}},
            {"notes": ["TEST_PRIVATE_TOKEN"]},
            {"session": {"permissions": ["aion:admin"]}},
            {"topic": {"raw": "CRM"}},
            {"topic": "arbitrary internal client notes"},
            {"mode": "OWNER_BYPASS"},
            {"slide": True},
            {"slide": -1},
            {"slide": 10001},
            {"topic": None},
            {"mode": 123},
        )
        for context in cases:
            with self.subTest(context=context):
                with self.assertRaises(ValueError):
                    continuity_handoff(
                        source_device="desktop", target_device="mobile",
                        owner_subject="test-owner", conversation_id="b" * 32,
                        context=context,
                    )

    def test_local_app_launch_remains_plan_only_even_when_synthetic_owner_bound(self):
        for cmd in ("AION abre WhatsApp", "AION abre ChatGPT", "AION abre Spotify"):
            with self.subTest(cmd=cmd):
                plan = command_plan(cmd, device="desktop", owner_bound=True)
                self.assertEqual(plan["adapter_required"], "SECURE_LOCAL_AGENT")
                self.assertFalse(plan["physical_execution"])
                self.assertTrue(plan["requires_explicit_approval"])


    def test_identifier_strings_cannot_smuggle_arbitrary_private_text(self):
        legitimate = {
            "source_device": "desktop", "target_device": "mobile",
            "owner_subject": "test-owner", "conversation_id": "a" * 32,
            "last_turn_id": "AION-TURN-" + "B" * 24,
            "context": {"mode": "TEACHING", "topic": "CRM", "slide": 7},
        }
        invalid_overrides = (
            {"owner_subject": "Bearer synthetic-owner-token"},
            {"owner_subject": {"username": "test-owner"}},
            {"owner_subject": "test-owner\nAuthorization: fake"},
            {"conversation_id": "Bearer synthetic-secret"},
            {"conversation_id": {"token": "synthetic-secret"}},
            {"conversation_id": "conv-test-1"},
            {"conversation_id": "AION-CONV-" + "Z" * 24},
            {"conversation_id": "https://example.invalid/private"},
            {"conversation_id": "a" * 1000},
            {"last_turn_id": "turn-test-1"},
            {"last_turn_id": "synthetic-session-token"},
            {"last_turn_id": {"session": "fake"}},
            {"last_turn_id": "AION-TURN-" + "Z" * 24},
            {"last_turn_id": 0},
            {"source_device": {"device": "DESKTOP"}},
            {"target_device": ["MOBILE"]},
        )
        for override in invalid_overrides:
            with self.subTest(override=override):
                with self.assertRaises(ValueError):
                    continuity_handoff(**{**legitimate, **override})

    def test_real_chat_identifier_forms_are_references_without_authority(self):
        from aion_chat.models import Conversation, Message
        conversation = Conversation(
            owner_id="test-owner",
            tenant_id="synthetic-tenant",
            workspace_id="synthetic-workspace",
        )
        message = Message(conversation_id=conversation.id, role="user", content="fixture")
        for conv_id, turn_id in (
            (conversation.id, message.id),
            ("AION-CONV-" + "A" * 24, "AION-TURN-" + "B" * 24),
            (conversation.id, ""),
        ):
            with self.subTest(conv=conv_id, turn=turn_id):
                plan = continuity_handoff(
                    source_device="desktop", target_device="mobile",
                    owner_subject="test-owner", conversation_id=conv_id,
                    last_turn_id=turn_id,
                    context={"mode": "TEACHING", "topic": "CRM", "slide": 2},
                )
                self.assertEqual(plan["state"], "HANDOFF_PREPARED_UNVERIFIED")
                self.assertFalse(plan["source_owner_verified"])
                self.assertFalse(plan["target_owner_verified"])
                self.assertFalse(plan["tenant_membership_verified"])
                self.assertFalse(plan["target_device_authenticated"])
                self.assertFalse(plan["authorization_granted"])
                self.assertFalse(plan["can_resume_conversation"])
                self.assertFalse(plan["handoff_digest_is_signature"])
                self.assertTrue(plan["requires_target_reauthentication"])
                self.assertFalse(plan["executes_action"])


if __name__ == "__main__":
    unittest.main()
