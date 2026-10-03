import unittest

from atlasquant_aion_memory import (
    checkpoint_integrity_report,
    default_checkpoint,
    ensure_operating_checkpoint,
)
from atlasquant_aion_persona_memory import append_persona_entry
from datetime import datetime, timezone

from atlasquant_aion_memory_layers import (
    default_memory_layers,
    memory_integrity_report,
    memory_layer_summary,
    normalize_memory_entry,
    normalize_memory_layers,
    recall,
    remember,
)


class AionMemoryLayersTests(unittest.TestCase):
    def test_all_required_layers_are_versioned_in_checkpoint(self):
        checkpoint = default_checkpoint()
        self.assertEqual(checkpoint["checkpoint_version"], 18)
        summary = memory_layer_summary(checkpoint["memory_layers"])
        self.assertEqual(
            set(summary["by_layer"]),
            {"session", "working", "project", "decision", "knowledge", "user_preference", "episodic", "checkpoint"},
        )

    def test_exact_duplicate_is_not_stored_twice(self):
        memory = default_memory_layers()
        params = {
            "layer": "project",
            "content": "Guardian permanece fail-closed.",
            "origin": "docs/aion/security.md",
            "category": "security",
            "confidence": 100,
            "truth_state": "CONFIRMED",
            "tags": ["guardian"],
        }
        once = remember(memory, **params)
        twice = remember(once, **params)
        self.assertEqual(len(twice["entries"]), 1)
        self.assertEqual(once["digest"], twice["digest"])

    def test_update_supersedes_instead_of_erasing_history(self):
        first = remember(
            None, layer="decision", content="Use schema v1", origin="admin",
            category="schema", memory_key="decision:schema", truth_state="CONFIRMED",
        )
        second = remember(
            first, layer="decision", content="Use schema v2", origin="admin",
            category="schema", memory_key="decision:schema", truth_state="CONFIRMED",
        )
        self.assertEqual(len(second["entries"]), 2)
        old, new = second["entries"]
        self.assertEqual(old["status"], "SUPERSEDED")
        self.assertEqual(old["superseded_by"], new["memory_id"])
        self.assertEqual([row["content"] for row in recall(second)], ["Use schema v2"])

    def test_persona_memory_never_crosses_context(self):
        memory = remember(
            None, layer="working", content="Patch privado do dev", origin="task",
            category="task", persona="developer", truth_state="INFERENCE",
        )
        self.assertEqual(recall(memory, persona="trader"), [])
        self.assertEqual(len(recall(memory, persona="developer")), 1)
        self.assertEqual(recall(memory), [])

    def test_corrupt_or_incompatible_payload_recovers_empty(self):
        recovered = normalize_memory_layers({"schema": "OLD", "entries": [{"bad": True}]})
        self.assertEqual(recovered["entries"], [])
        self.assertEqual(recovered["recovery"]["state"], "RECOVERED_EMPTY")

    def test_checkpoint_upgrade_preserves_old_sections_and_adds_layers(self):
        old = {"checkpoint_version": 4, "project": "AtlasQuant", "pending": ["x"]}
        upgraded = ensure_operating_checkpoint(old)
        self.assertEqual(upgraded["checkpoint_version"], 18)
        self.assertEqual(upgraded["project"], "AtlasQuant")
        self.assertEqual(upgraded["pending"], ["x"])
        self.assertEqual(upgraded["memory_layers"]["schema"], "ATLASQUANT_AION_MEMORY_LAYERS_V1")

    def test_checkpoint_integrity_covers_layered_and_persona_memory(self):
        checkpoint = default_checkpoint()
        self.assertEqual(checkpoint_integrity_report(checkpoint)["state"], "CONFIRMED")
        checkpoint["memory_layers"]["entries"].append({
            "layer": "project",
            "content": "tampered",
            "origin": "unknown",
            "category": "test",
        })
        report = checkpoint_integrity_report(checkpoint)
        self.assertEqual(report["state"], "MISMATCH")
        self.assertIn("memory_layers", report["mismatches"])

        persona_checkpoint = default_checkpoint()
        persona_checkpoint["persona_memory"] = append_persona_entry(
            persona_checkpoint["persona_memory"],
            "developer",
            kind="decision",
            message="valid entry",
        )
        persona_checkpoint["persona_memory"]["personas"]["developer"]["entries"][0]["message"] = "tampered"
        persona_report = checkpoint_integrity_report(persona_checkpoint)
        self.assertEqual(persona_report["state"], "MISMATCH")
        self.assertIn("persona_memory", persona_report["mismatches"])

    def test_corrupt_layers_are_not_intact(self):
        self.assertEqual(memory_integrity_report({"schema": "OTHER", "version": 1})["state"], "REJECTED")
        self.assertFalse(memory_integrity_report({"schema": "ATLASQUANT_AION_MEMORY_LAYERS_V1", "version": 9})["intact"])
        fresh = remember(None, layer="working", content="bound", origin="test", category="task", tenant="tenant-a")
        tampered = dict(fresh)
        tampered["digest"] = "0" * 24
        self.assertEqual(memory_integrity_report(tampered)["state"], "MISMATCH")
        self.assertEqual(recall(fresh, tenant="tenant-b"), [])
        self.assertEqual(len(recall(fresh, tenant="tenant-a")), 1)

    def test_bad_timestamps_truth_and_shape_fail_closed(self):
        invalid = remember(
            None, layer="working", content="broken clock", origin="test", category="task",
            truth_state="CONFIRMED", created_at="not-a-time",
        )
        self.assertEqual(invalid["entries"][-1]["truth_state"], "UNKNOWN")
        self.assertEqual(recall(invalid), [])
        future = remember(
            None, layer="working", content="future", origin="test", category="task",
            created_at="2999-01-01T00:00:00+00:00",
        )
        self.assertEqual(recall(future, now=datetime(2026, 9, 30, tzinfo=timezone.utc)), [])
        self.assertEqual(normalize_memory_entry({
            "layer": "working", "content": "x", "origin": "test", "category": "task", "truth_state": "MAYBE",
        })["truth_state"], "UNKNOWN")
        self.assertEqual(normalize_memory_entry({
            "layer": "working", "content": "x", "origin": "test", "category": "task", "status": "LIVE",
        })["status"], "REJECTED")
        with self.assertRaises(ValueError):
            normalize_memory_entry({"layer": "working", "content": "x", "origin": "", "category": "task"})
        with self.assertRaises(ValueError):
            normalize_memory_entry({"layer": "working", "content": "x", "origin": "test", "category": ""})
        nested = remember(None, layer="working", content={"deep": {"n": list(range(3))}}, origin="test", category="task")
        self.assertLessEqual(len(nested["entries"][-1]["content"]), 4000)
        huge = "y" * 5000
        stored = remember(None, layer="working", content=huge, origin="test", category="task", truth_state="CONFIRMED")
        self.assertTrue(stored["entries"][-1]["truncated"])
        self.assertEqual(stored["entries"][-1]["truth_state"], "UNKNOWN")
        self.assertNotEqual(recall(
            remember(None, layer="working", content="trader", origin="test", category="task", domain="TRADER"),
            domain="BUSINESS",
        ), recall(
            remember(None, layer="working", content="trader", origin="test", category="task", domain="TRADER"),
            domain="TRADER",
        ))


if __name__ == "__main__":
    unittest.main()
