from __future__ import annotations

from pathlib import Path
import unittest

import atlasquant_aion_durable_tasks as durable
import atlasquant_aion_knowledge_graph as graph
import atlasquant_aion_observability as observability


class GuardedIterable:
    """Raises if a prefix consumer asks for one element past its budget."""

    def __init__(self, values, *, max_reads):
        self._values = iter(values)
        self._max_reads = max_reads
        self.reads = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self.reads >= self._max_reads:
            raise AssertionError("iterator over-consumed past configured bound")
        value = next(self._values)
        self.reads += 1
        return value


class AionCoreResourceBoundsTests(unittest.TestCase):
    def test_durable_refs_do_not_materialize_entire_iterable(self):
        source = GuardedIterable(
            (f"ref-{i}" for i in range(100)),
            max_reads=6,
        )
        result = durable._refs(source, limit=3)
        self.assertEqual(result, ["ref-0", "ref-1", "ref-2"])
        self.assertLessEqual(source.reads, 6)

    def test_durable_steps_stop_at_max_steps_without_overread(self):
        original = durable.MAX_STEPS
        durable.MAX_STEPS = 3
        try:
            source = GuardedIterable(
                (
                    {
                        "step_id": f"s{i}",
                        "title": f"Step {i}",
                        "state": "PENDING",
                    }
                    for i in range(20)
                ),
                max_reads=3,
            )
            result = durable.normalize_steps(source)
        finally:
            durable.MAX_STEPS = original
        self.assertEqual(len(result), 3)
        self.assertEqual([row["step_id"] for row in result], ["s0", "s1", "s2"])
        self.assertEqual(source.reads, 3)

    def test_durable_task_generator_preserves_recent_tail(self):
        rows = [
            durable.new_durable_task(
                f"Task {i}",
                created_at=f"2026-09-29T{(i % 24):02d}:00:00+00:00",
            )
            for i in range(durable.MAX_TASKS + 5)
        ]
        result = durable.normalize_durable_tasks(iter(rows))
        self.assertEqual(len(result), durable.MAX_TASKS)
        self.assertEqual(
            result[0]["durable_task_id"],
            rows[5]["durable_task_id"],
        )
        self.assertEqual(
            result[-1]["durable_task_id"],
            rows[-1]["durable_task_id"],
        )

    def test_observability_generator_preserves_recent_tail(self):
        rows = [
            observability.new_event(
                f"event-{i}",
                f"message-{i}",
                created_at=f"2026-09-29T00:{(i % 60):02d}:00+00:00",
            )
            for i in range(observability.MAX_EVENTS + 5)
        ]
        result = observability.normalize_events(iter(rows))
        self.assertEqual(len(result), observability.MAX_EVENTS)
        self.assertEqual(result[0]["event_type"], "event-5")
        self.assertEqual(result[-1]["event_type"], f"event-{observability.MAX_EVENTS + 4}")

    def test_graph_refs_do_not_materialize_entire_iterable(self):
        source = GuardedIterable(
            (f"evidence-{i}" for i in range(100)),
            max_reads=6,
        )
        result = graph._refs(source, limit=3)
        self.assertEqual(result, ["evidence-0", "evidence-1", "evidence-2"])
        self.assertLessEqual(source.reads, 6)

    def test_graph_source_derivation_has_hard_record_budget(self):
        original = graph.MAX_DERIVE_RECORDS_PER_SOURCE
        graph.MAX_DERIVE_RECORDS_PER_SOURCE = 3
        try:
            source = GuardedIterable(
                (
                    {
                        "ref_id": f"research:{i}",
                        "kind": "test",
                        "strategy": "bounded",
                    }
                    for i in range(20)
                ),
                max_reads=3,
            )
            result = graph.derive_graph(research_refs=source)
        finally:
            graph.MAX_DERIVE_RECORDS_PER_SOURCE = original
        self.assertEqual(source.reads, 3)
        self.assertEqual(len(result["nodes"]), 3)

    def test_resource_bound_implementations_avoid_unbounded_list_before_slice(self):
        durable_source = Path("atlasquant_aion_durable_tasks.py").read_text(encoding="utf-8")
        observability_source = Path("atlasquant_aion_observability.py").read_text(encoding="utf-8")
        graph_source = Path("atlasquant_aion_knowledge_graph.py").read_text(encoding="utf-8")

        self.assertNotIn("list(values or [])[:", durable_source)
        self.assertNotIn("list(rows or [])[:MAX_STEPS", durable_source)
        self.assertNotIn("list(rows or [])[-MAX_TASKS", durable_source)
        self.assertIn("deque(rows or (), maxlen=MAX_TASKS*2)", durable_source)

        self.assertNotIn("list(events or [])[-MAX_EVENTS", observability_source)
        self.assertNotIn("list(value.items())[:100]", observability_source)
        self.assertIn("deque(events or (), maxlen=MAX_EVENTS*2)", observability_source)

        self.assertNotIn("list(values or [])[:", graph_source)
        self.assertNotIn("list(rows or [])[:MAX_NODES", graph_source)
        self.assertNotIn("list(rows or [])[:MAX_EDGES", graph_source)
        self.assertIn("islice(wisdom_entries or (), MAX_DERIVE_RECORDS_PER_SOURCE)", graph_source)
        self.assertIn("islice(research_refs or (), MAX_DERIVE_RECORDS_PER_SOURCE)", graph_source)


if __name__ == "__main__":
    unittest.main()
