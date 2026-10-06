import unittest

from atlasquant_aion_temporal_memory_v2 import (
    build_timeline,
    legacy_commitments_to_events,
    normalize_event,
    query_timeline,
)


def event(event_id, day, *, state="DECIDED", truth="CONFIRMED", supersedes=(), superseded_by=()):
    return {
        "event_id": event_id,
        "date": day,
        "kind": "DECISION",
        "state": state,
        "truth_state": truth,
        "domain": "aion-core",
        "topic": "authority",
        "title": event_id,
        "summary": "Historical decision with evidence.",
        "authority": "HUMAN_OWNER",
        "source_type": "CHECKPOINT",
        "evidence_refs": ["issue:953"] if truth == "CONFIRMED" else [],
        "supersedes": list(supersedes),
        "superseded_by": list(superseded_by),
    }


class TemporalMemoryV2Tests(unittest.TestCase):
    def test_confirmed_event_requires_evidence(self):
        raw = event("e1", "2026-09-15")
        raw["evidence_refs"] = []
        with self.assertRaises(ValueError):
            normalize_event(raw)

    def test_duplicate_id_is_rejected(self):
        with self.assertRaises(ValueError):
            build_timeline([event("e1", "2026-09-15"), event("e1", "2026-09-16")])

    def test_unknown_relationship_blocks_timeline(self):
        timeline = build_timeline([event("e1", "2026-09-15", supersedes=("missing",))])
        self.assertEqual(timeline["state"], "BLOCKED")
        self.assertTrue(timeline["blockers"])
        self.assertFalse(timeline["executes_action"])
        self.assertFalse(timeline["runtime_write"])

    def test_query_distinguishes_unknown_from_fabricated_answer(self):
        timeline = build_timeline([event("e1", "2026-09-15")])
        result = query_timeline(timeline, exact_date="2026-09-19")
        self.assertEqual(result["state"], "UNKNOWN")
        self.assertEqual(result["results"], [])
        self.assertTrue(result["unknown_means_no_ingested_evidence"])

    def test_date_range_and_topic_query(self):
        timeline = build_timeline([
            event("e1", "2026-09-15"),
            event("e2", "2026-09-16"),
            event("e3", "2026-09-18"),
        ])
        result = query_timeline(
            timeline,
            start_date="2026-09-16",
            end_date="2026-09-18",
            topic="authority",
        )
        self.assertEqual([x["event_id"] for x in result["results"]], ["e2", "e3"])


    def test_nonreciprocal_supersession_blocks_timeline(self):
        timeline = build_timeline([
            event("old", "2026-09-15"),
            event("new", "2026-09-16", supersedes=("old",)),
        ])
        self.assertEqual(timeline["state"], "BLOCKED")
        self.assertTrue(any(x.startswith("NON_RECIPROCAL_SUPERSESSION") for x in timeline["blockers"]))

    def test_superseded_can_be_hidden_without_erasing_history(self):
        timeline = build_timeline([
            event("old", "2026-09-15", state="SUPERSEDED", superseded_by=("new",)),
            event("new", "2026-09-16", supersedes=("old",)),
        ])
        all_rows = query_timeline(timeline, topic="authority")
        current = query_timeline(timeline, topic="authority", include_superseded=False)
        self.assertEqual(all_rows["result_count"], 2)
        self.assertEqual([x["event_id"] for x in current["results"]], ["new"])

    def test_legacy_manifest_conversion_preserves_pending(self):
        rows = legacy_commitments_to_events({
            "commitments": [{
                "id": "D-1",
                "source_date": "2026-09-15",
                "state": "APROVADO / PENDENTE",
                "domain": "memory",
                "title": "Historical memory",
                "summary": "Keep the project history.",
                "evidence": ["checkpoint.md"],
                "implemented": False,
                "validated": False,
            }]
        })
        self.assertEqual(rows[0]["state"], "PENDING")
        self.assertEqual(rows[0]["truth_state"], "CONFIRMED")


if __name__ == "__main__":
    unittest.main()
