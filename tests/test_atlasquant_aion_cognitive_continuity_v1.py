import copy
import unittest

from aion_core.memory_architecture import (
    create_record,
    new_store,
    put_record,
    validate_record,
)
from atlasquant_aion_chat_resume_bridge import SCHEMA as CHAT_RESUME_SCHEMA
from atlasquant_aion_cognitive_continuity_v1 import (
    cognitive_continuity_policy,
    cognitive_memory_snapshot,
    prepare_cognitive_continuity,
    verify_cognitive_memory_snapshot,
)
from atlasquant_aion_continuity import new_mission
from atlasquant_aion_memory_layers import default_memory_layers, remember


class AionCognitiveContinuityV1Tests(unittest.TestCase):
    def layered_memory(self):
        memory = default_memory_layers()
        memory = remember(
            memory,
            layer="knowledge",
            content="CRM is the canonical customer relationship workspace.",
            origin="admin-decision",
            category="semantic_fact",
            confidence=0.98,
            truth_state="CONFIRMED",
            domain="CORE",
            source_refs=["decision:crm-canonical"],
            memory_key="semantic:crm",
            promotion_state="PROMOTED",
        )
        memory = remember(
            memory,
            layer="episodic",
            content="Owner reviewed the AION greeting flow on 2026-10-08.",
            origin="owner-session",
            category="episode",
            confidence=1.0,
            truth_state="CONFIRMED",
            domain="CORE",
            source_refs=["session:2026-10-08"],
            memory_key="episode:greeting-review",
            promotion_state="PROMOTED",
        )
        memory = remember(
            memory,
            layer="decision",
            content="External desktop applications require the secure local agent.",
            origin="owner-decision",
            category="decision",
            confidence=1.0,
            truth_state="CONFIRMED",
            domain="CORE",
            source_refs=["owner-experience-v1"],
            memory_key="decision:secure-local-agent",
            promotion_state="PROMOTED",
        )
        return memory

    def architecture_store(self):
        record = create_record(
            layer="PROCEDURAL",
            content="Plan action, require authorization when applicable, verify result, record evidence.",
            domain_id="CORE",
            source_ref="aion-operating-procedure",
            confidence=1.0,
        )
        record = validate_record(record, reviewer="test-suite")
        return put_record(new_store(), record)

    def snapshot(self):
        return cognitive_memory_snapshot(
            self.layered_memory(),
            self.architecture_store(),
            domain="CORE",
            accessor_profile="AION_CORE",
            explicit_domains=["CORE"],
            limit_per_channel=10,
        )

    def resume_envelope(self, **changes):
        value = {
            "schema": CHAT_RESUME_SCHEMA,
            "state": "READY",
            "conversation_id": "conv-owner-1",
            "identity_binding_complete": True,
            "identity_binding_digest": "sha256:identity",
            "context_digest": "sha256:resume",
            "checkpoint_id": "cp-7",
            "summary_id": "sum-3",
            "automatic_compaction": False,
            "automatic_checkpoint_write": False,
            "core_checkpoint_write": False,
            "automatic_memory_promotion": False,
            "memory_promoted": False,
            "provider_called": False,
            "network_called": False,
            "tool_executed": False,
            "external_action_executed": False,
            "grants_authority": False,
            "executes_action": False,
        }
        value.update(changes)
        return value

    def test_snapshot_unifies_four_cognitive_channels(self):
        snapshot = self.snapshot()
        self.assertEqual(snapshot["state"], "READY")
        self.assertEqual(
            list(snapshot["channels"]),
            ["SEMANTIC", "EPISODIC", "PROCEDURAL", "DECISION"],
        )
        self.assertEqual(snapshot["counts"]["SEMANTIC"], 1)
        self.assertEqual(snapshot["counts"]["EPISODIC"], 1)
        self.assertEqual(snapshot["counts"]["PROCEDURAL"], 1)
        self.assertEqual(snapshot["counts"]["DECISION"], 1)
        self.assertTrue(
            snapshot["channels"]["SEMANTIC"][0]["used_as_current_fact"]
        )
        self.assertTrue(
            snapshot["channels"]["PROCEDURAL"][0]["used_as_current_fact"]
        )

    def test_snapshot_is_read_only_and_does_not_promote_or_persist(self):
        snapshot = self.snapshot()
        self.assertFalse(snapshot["authentication_embedded"])
        self.assertFalse(snapshot["credentials_embedded"])
        self.assertFalse(snapshot["automatic_memory_promotion"])
        self.assertFalse(snapshot["memory_promoted"])
        self.assertFalse(snapshot["memory_persisted"])
        self.assertFalse(snapshot["automatic_checkpoint_write"])
        self.assertFalse(snapshot["core_checkpoint_write"])
        self.assertFalse(snapshot["provider_called"])
        self.assertFalse(snapshot["external_action_executed"])
        self.assertFalse(snapshot["executes_action"])

    def test_snapshot_digest_detects_tampering(self):
        snapshot = self.snapshot()
        verified = verify_cognitive_memory_snapshot(snapshot)
        self.assertTrue(verified["valid"])

        tampered = copy.deepcopy(snapshot)
        tampered["channels"]["SEMANTIC"][0]["content"] = "tampered"
        rejected = verify_cognitive_memory_snapshot(tampered)
        self.assertFalse(rejected["valid"])
        self.assertIn("MEMORY_DIGEST_MISMATCH", rejected["blockers"])

    def test_cross_device_continuity_transfers_digests_not_raw_memory(self):
        snapshot = self.snapshot()
        mission = new_mission(
            "Finish owner experience integration",
            domain="development",
            next_action="Validate the stacked Draft PR",
            created_at="2026-10-08T09:45:00+00:00",
        )
        result = prepare_cognitive_continuity(
            snapshot,
            self.resume_envelope(),
            source_device="desktop",
            target_device="mobile",
            owner_subject="mikael",
            conversation_id="conv-owner-1",
            last_turn_id="turn-42",
            missions=[mission],
            checkpoint_digest="checkpoint-abc",
            mode="TEACHING",
            topic="CRM",
            slide=7,
        )

        self.assertEqual(result["state"], "READY")
        self.assertEqual(result["source_device"], "DESKTOP")
        self.assertEqual(result["target_device"], "MOBILE")
        self.assertFalse(result["cognitive_memory"]["raw_memory_transferred"])
        self.assertFalse(result["resume"]["raw_context_transferred"])
        self.assertEqual(
            result["cognitive_memory"]["digest"],
            snapshot["memory_digest"],
        )
        self.assertNotIn("channels", result["cognitive_memory"])
        self.assertTrue(result["requires_target_reauthentication"])
        self.assertFalse(result["authentication_transferred"])
        self.assertFalse(result["session_token_transferred"])
        self.assertFalse(result["credentials_transferred"])
        self.assertFalse(result["memory_promoted"])
        self.assertFalse(result["memory_persisted"])
        self.assertFalse(result["core_checkpoint_write"])
        self.assertFalse(result["external_action_executed"])

    def test_resume_rehydration_state_is_preserved(self):
        result = prepare_cognitive_continuity(
            self.snapshot(),
            self.resume_envelope(state="REHYDRATION_REQUIRED"),
            source_device="mobile",
            target_device="desktop",
            owner_subject="mikael",
            conversation_id="conv-owner-1",
        )
        self.assertEqual(result["state"], "REHYDRATION_REQUIRED")
        self.assertEqual(result["resume"]["state"], "REHYDRATION_REQUIRED")

    def test_resume_identity_binding_is_required(self):
        with self.assertRaises(ValueError):
            prepare_cognitive_continuity(
                self.snapshot(),
                self.resume_envelope(identity_binding_complete=False),
                source_device="desktop",
                target_device="mobile",
                owner_subject="mikael",
                conversation_id="conv-owner-1",
            )

    def test_resume_cannot_smuggle_authentication_material(self):
        with self.assertRaises(ValueError):
            prepare_cognitive_continuity(
                self.snapshot(),
                self.resume_envelope(token="forbidden"),
                source_device="desktop",
                target_device="mobile",
                owner_subject="mikael",
                conversation_id="conv-owner-1",
            )

    def test_resume_cannot_claim_execution_or_authority(self):
        for key in (
            "memory_promoted",
            "core_checkpoint_write",
            "provider_called",
            "external_action_executed",
            "grants_authority",
        ):
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    prepare_cognitive_continuity(
                        self.snapshot(),
                        self.resume_envelope(**{key: True}),
                        source_device="desktop",
                        target_device="mobile",
                        owner_subject="mikael",
                        conversation_id="conv-owner-1",
                    )

    def test_policy_forbids_second_database_and_auth_transfer(self):
        policy = cognitive_continuity_policy()
        self.assertTrue(policy["reuses_existing_memory_systems"])
        self.assertFalse(policy["creates_second_memory_database"])
        self.assertFalse(policy["cross_device_raw_memory_transfer"])
        self.assertFalse(policy["cross_device_raw_chat_context_transfer"])
        self.assertFalse(policy["cross_device_authentication_transfer"])
        self.assertTrue(policy["target_reauthentication_required"])
        self.assertFalse(policy["automatic_memory_promotion"])
        self.assertFalse(policy["core_checkpoint_write"])
        self.assertFalse(policy["worker_armed"])
        self.assertFalse(policy["deploy_executed"])
        self.assertFalse(policy["external_action_executed"])


if __name__ == "__main__":
    unittest.main()
