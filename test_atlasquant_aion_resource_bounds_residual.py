from pathlib import Path
import unittest

import atlasquant_aion_continuity as continuity
import atlasquant_aion_learning as learning
import atlasquant_aion_operations as operations


class GuardedIterable:
    def __init__(self, values, *, max_reads):
        self._values=iter(values)
        self.max_reads=max_reads
        self.reads=0

    def __iter__(self):
        return self

    def __next__(self):
        if self.reads>=self.max_reads:
            raise AssertionError("iterator consumed beyond explicit prefix bound")
        value=next(self._values)
        self.reads+=1
        return value


class AionResidualResourceBoundsTests(unittest.TestCase):
    def test_operations_queue_stops_at_scan_budget(self):
        original=operations.MAX_TASKS
        operations.MAX_TASKS=3
        try:
            source=GuardedIterable(
                (
                    operations.new_task(
                        f"Task {i}",
                        domain="development",
                        action="read",
                        created_at=f"2026-09-29T12:00:0{i}+00:00",
                    )
                    for i in range(20)
                ),
                max_reads=6,
            )
            rows=operations.normalize_queue(source)
        finally:
            operations.MAX_TASKS=original
        self.assertEqual(len(rows),3)
        self.assertEqual(source.reads,3)

    def test_continuity_generator_uses_bounded_tail_buffers(self):
        mission_total=continuity.MAX_MISSIONS+5
        missions=(
            continuity.new_mission(
                f"Mission {i}",
                created_at=f"2026-09-29T12:{i%60:02d}:00+00:00",
            )
            for i in range(mission_total)
        )
        normalized=continuity.normalize_missions(missions)
        self.assertEqual(len(normalized),continuity.MAX_MISSIONS)
        self.assertEqual(normalized[0]["title"],"Mission 5")
        self.assertEqual(normalized[-1]["title"],f"Mission {mission_total-1}")

        handoff_total=continuity.MAX_HANDOFFS+5
        handoffs=(
            {
                "created_at":f"2026-09-29T13:{i%60:02d}:00+00:00",
                "current_focus":f"Focus {i}",
                "checkpoint_digest":f"digest-{i}",
            }
            for i in range(handoff_total)
        )
        normalized_handoffs=continuity.normalize_handoffs(handoffs)
        self.assertEqual(len(normalized_handoffs),continuity.MAX_HANDOFFS)
        self.assertEqual(normalized_handoffs[0]["current_focus"],"Focus 5")
        self.assertEqual(normalized_handoffs[-1]["current_focus"],f"Focus {handoff_total-1}")

    def test_continuity_prefix_helpers_do_not_overread(self):
        refs=GuardedIterable((f"ref-{i}" for i in range(50)),max_reads=6)
        out=continuity._refs(refs,limit=3)
        self.assertEqual(out,["ref-0","ref-1","ref-2"])
        self.assertLessEqual(refs.reads,6)

        tasks=GuardedIterable(
            (
                {"title":f"Task {i}","status":"TODO"}
                for i in range(60)
            ),
            max_reads=8,
        )
        handoff=continuity.build_session_handoff([],tasks=tasks,events=[])
        self.assertEqual(len(handoff["next_steps"]),8)
        self.assertEqual(tasks.reads,8)

    def test_learning_generators_preserve_recent_tail_with_bounded_memory(self):
        episode_total=learning.MAX_EPISODES+5
        episodes=(
            learning.new_learning_episode(
                f"Subject {i}",
                forecast_type="CATEGORICAL",
                prediction="UP",
                confidence_pct=50,
                created_at=f"2026-09-29T10:{i%60:02d}:00+00:00",
            )
            for i in range(episode_total)
        )
        normalized=learning.normalize_learning_episodes(episodes)
        self.assertEqual(len(normalized),learning.MAX_EPISODES)
        self.assertEqual(normalized[0]["subject"],"Subject 5")
        self.assertEqual(normalized[-1]["subject"],f"Subject {episode_total-1}")

        research_total=learning.MAX_RESEARCH_REFS+5
        refs=(
            learning.new_research_reference(
                "BACKTEST",
                f"ref-{i}",
                created_at=f"2026-09-29T11:{i%60:02d}:00+00:00",
            )
            for i in range(research_total)
        )
        normalized_refs=learning.normalize_research_references(refs)
        self.assertEqual(len(normalized_refs),learning.MAX_RESEARCH_REFS)
        self.assertEqual(normalized_refs[0]["ref_id"],"ref-5")

        experiment_total=learning.MAX_EXPERIMENTS+5
        experiments=(
            learning.new_learning_experiment(
                "champion",
                f"challenger-{i}",
                rationale="bounded-memory regression",
                created_at=f"2026-09-29T14:{i%60:02d}:00+00:00",
            )
            for i in range(experiment_total)
        )
        normalized_experiments=learning.normalize_learning_experiments(experiments)
        self.assertEqual(len(normalized_experiments),learning.MAX_EXPERIMENTS)
        self.assertEqual(
            normalized_experiments[0]["challenger_version"],
            "challenger-5",
        )

    def test_known_unbounded_materialization_patterns_are_absent(self):
        operations_src=Path("atlasquant_aion_operations.py").read_text(encoding="utf-8")
        continuity_src=Path("atlasquant_aion_continuity.py").read_text(encoding="utf-8")
        learning_src=Path("atlasquant_aion_learning.py").read_text(encoding="utf-8")

        self.assertNotIn("list(tasks or [])[:MAX_TASKS",operations_src)
        self.assertNotIn("list(rows or [])[-MAX_MISSIONS",continuity_src)
        self.assertNotIn("list(rows or [])[-MAX_HANDOFFS",continuity_src)
        self.assertNotIn("list(tasks or [])[:50]",continuity_src)
        self.assertNotIn("list(events or [])[-30:]",continuity_src)
        self.assertNotIn("list(rows or [])[-MAX_EPISODES",learning_src)
        self.assertNotIn("list(rows or [])[-MAX_RESEARCH_REFS",learning_src)
        self.assertNotIn("list(rows or [])[-MAX_EXPERIMENTS",learning_src)


if __name__=="__main__":
    unittest.main()
