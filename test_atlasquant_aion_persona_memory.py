import unittest

from atlasquant_aion_persona_memory import (
    PERSONAS,
    SCHEMA,
    append_persona_entry,
    default_persona_memory,
    normalize_persona_memory,
    persona_entries,
)


class PersonaMemoryTests(unittest.TestCase):
    def test_default_has_versioned_isolated_persona_sections(self):
        memory = default_persona_memory()
        self.assertEqual(memory["schema"], SCHEMA)
        self.assertEqual(memory["version"], 1)
        self.assertEqual(set(memory["personas"]), set(PERSONAS))
        self.assertTrue(all(memory["personas"][p]["entries"] == [] for p in PERSONAS))

    def test_writing_one_persona_never_leaks_into_another(self):
        memory = append_persona_entry(
            default_persona_memory(),
            "trader",
            kind="technical_state",
            message="Radar 28 pares: 7 com técnica.",
            truth_state="CONFIRMED",
            source="atlasquant_radar_board",
        )
        self.assertEqual(len(persona_entries(memory, "trader")), 1)
        for persona in set(PERSONAS) - {"trader"}:
            self.assertEqual(persona_entries(memory, persona), [], persona)

    def test_cross_persona_entry_is_rejected_during_recovery(self):
        memory = default_persona_memory()
        memory["personas"]["trader"]["entries"] = [{
            "persona": "developer",
            "kind": "decision",
            "message": "must not cross",
        }]
        recovered = normalize_persona_memory(memory)
        self.assertEqual(persona_entries(recovered, "trader"), [])
        self.assertEqual(persona_entries(recovered, "developer"), [])
        self.assertEqual(recovered["recovery"]["state"], "RECOVERED_PARTIAL")

    def test_corrupt_or_incompatible_memory_recovers_empty(self):
        for payload in (None, [], {"schema": "V99", "version": 99, "personas": {}}):
            recovered = normalize_persona_memory(payload)
            self.assertEqual(recovered["recovery"]["state"], "RECOVERED_EMPTY")
            self.assertTrue(all(not persona_entries(recovered, p) for p in PERSONAS))

    def test_unknown_persona_and_invalid_entry_fail_closed(self):
        with self.assertRaises(KeyError):
            append_persona_entry({}, "root", kind="decision", message="x")
        with self.assertRaises(ValueError):
            append_persona_entry({}, "admin", kind="secret", message="x")
        self.assertEqual(persona_entries({}, "root"), [])


if __name__ == "__main__":
    unittest.main()
