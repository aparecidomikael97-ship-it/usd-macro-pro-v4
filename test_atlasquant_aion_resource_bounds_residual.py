from pathlib import Path
import unittest

import atlasquant_aion_action_receipt as action_receipt
import atlasquant_aion_continuity as continuity
import atlasquant_aion_dev_fusion as dev_fusion
import atlasquant_aion_digital_twin as digital_twin
import atlasquant_aion_event_journal as event_journal
import atlasquant_aion_evaluation_lab as evaluation_lab
import atlasquant_aion_learning as learning
import atlasquant_aion_model_registry as model_registry
import atlasquant_aion_operations as operations
import atlasquant_aion_release_confidence as release_confidence
import atlasquant_aion_tool_hub as tool_hub


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

    def test_cross_core_prefix_helpers_stop_without_materializing_sources(self):
        refs=GuardedIterable((f"ref-{i}" for i in range(20)),max_reads=6)
        self.assertEqual(digital_twin._refs(refs,limit=3),["ref-0","ref-1","ref-2"])
        self.assertEqual(refs.reads,3)

        fusion_refs=GuardedIterable((f"e-{i}" for i in range(20)),max_reads=6)
        self.assertEqual(dev_fusion._refs(fusion_refs,limit=3),["e-0","e-1","e-2"])
        self.assertEqual(fusion_refs.reads,3)

        evidence=GuardedIterable((f"e-{i}" for i in range(81)),max_reads=80)
        row=release_confidence.evidence_dimension(
            "QUALITY",
            confirmed=False,
            evidence_refs=evidence,
        )
        self.assertEqual(len(row["evidence_refs"]),80)
        self.assertEqual(evidence.reads,80)

        sources=GuardedIterable((f"source-{i}" for i in range(13)),max_reads=12)
        currencies=GuardedIterable((f"C{i}" for i in range(13)),max_reads=12)
        event=event_journal.compact_event({
            "headline":"bounded event",
            "sources":sources,
            "currencies":currencies,
        })
        self.assertEqual(len(event["sources"]),12)
        self.assertEqual(len(event["currencies"]),12)
        self.assertEqual(sources.reads,12)
        self.assertEqual(currencies.reads,12)

    def test_evaluation_toolhub_and_registry_prefix_bounds(self):
        eval_refs=GuardedIterable((f"ref-{i}" for i in range(10)),max_reads=3)
        self.assertEqual(evaluation_lab._refs(eval_refs,limit=3),["ref-0","ref-1","ref-2"])
        self.assertEqual(eval_refs.reads,3)

        tool_refs=GuardedIterable((f"scope-{i}" for i in range(10)),max_reads=3)
        self.assertEqual(tool_hub._unique(tool_refs,limit=3),["scope-0","scope-1","scope-2"])
        self.assertEqual(tool_refs.reads,3)

        model_texts=GuardedIterable((f"model-{i}" for i in range(10)),max_reads=3)
        self.assertEqual(model_registry._texts(model_texts,limit=3),["model-0","model-1","model-2"])
        self.assertEqual(model_texts.reads,3)

        models=GuardedIterable(
            ({"model_id":f"m-{i}"} for i in range(model_registry.MAX_MODELS+1)),
            max_reads=model_registry.MAX_MODELS,
        )
        bounded=model_registry._bounded_models(models)
        self.assertEqual(len(bounded),model_registry.MAX_MODELS)
        self.assertEqual(models.reads,model_registry.MAX_MODELS)

    def test_cross_core_tail_buffers_are_memory_bounded(self):
        sources={
            "atlasquant_aion_event_journal.py":[
                "deque(rows or (),maxlen=MAX_EVENTS*2)",
                "deque(rows or (),maxlen=MAX_HEARTBEATS*2)",
            ],
            "atlasquant_aion_wisdom.py":[
                "deque(rows or (), maxlen=MAX_ENTRIES * 2)",
            ],
            "atlasquant_aion_digital_twin.py":[
                "deque(rows or (),maxlen=MAX_TWINS*2)",
            ],
            "atlasquant_aion_release_confidence.py":[
                "deque(rows or (),maxlen=300)",
            ],
            "atlasquant_aion_dev_fusion.py":[
                "deque(rows or (),maxlen=MAX_PIPELINES*2)",
            ],
            "atlasquant_aion_evaluation_lab.py":[
                "deque(rows or (),maxlen=MAX_RUNS*2)",
            ],
        }
        for filename,needles in sources.items():
            with self.subTest(filename=filename):
                source=Path(filename).read_text(encoding="utf-8")
                for needle in needles:
                    self.assertIn(needle,source)

    def test_known_unbounded_materialization_patterns_are_absent(self):
        operations_src=Path("atlasquant_aion_operations.py").read_text(encoding="utf-8")
        continuity_src=Path("atlasquant_aion_continuity.py").read_text(encoding="utf-8")
        learning_src=Path("atlasquant_aion_learning.py").read_text(encoding="utf-8")
        business_src=Path("atlasquant_aion_business.py").read_text(encoding="utf-8")
        tenant_src=Path("atlasquant_aion_tenant.py").read_text(encoding="utf-8")
        memory_src=Path("atlasquant_aion_memory.py").read_text(encoding="utf-8")

        self.assertNotIn("list(tasks or [])[:MAX_TASKS",operations_src)
        self.assertNotIn("list(rows or [])[-MAX_MISSIONS",continuity_src)
        self.assertNotIn("list(rows or [])[-MAX_HANDOFFS",continuity_src)
        self.assertNotIn("list(tasks or [])[:50]",continuity_src)
        self.assertNotIn("list(events or [])[-30:]",continuity_src)
        self.assertNotIn("list(rows or [])[-MAX_EPISODES",learning_src)
        self.assertNotIn("list(rows or [])[-MAX_RESEARCH_REFS",learning_src)
        self.assertNotIn("list(rows or [])[-MAX_EXPERIMENTS",learning_src)
        self.assertNotIn("list(rows or [])[:MAX_PRODUCTS",business_src)
        self.assertNotIn("list(preferences.items())[:50]",tenant_src)
        self.assertNotIn("list(academy.items())[:200]",tenant_src)
        self.assertNotIn("list(redemptions_raw)[:2000]",memory_src)


    def test_action_receipt_prefix_helpers_stop_at_existing_limits(self):
        refs=GuardedIterable((f"ref-{i}" for i in range(100)),max_reads=40)
        normalized=action_receipt._refs(refs)
        self.assertEqual(len(normalized),40)
        self.assertEqual(refs.reads,40)

        children=GuardedIterable(
            (
                {
                    "receipt_id":f"receipt-{i}",
                    "schema":"TEST",
                    "fingerprint":f"fingerprint-{i}",
                }
                for i in range(100)
            ),
            max_reads=40,
        )
        normalized_children=action_receipt._child_refs(children)
        self.assertEqual(len(normalized_children),40)
        self.assertEqual(children.reads,40)

    def test_resilience_iterables_respect_existing_500_record_bounds(self):
        watchdogs=GuardedIterable(
            (
                {"component":f"component-{i}","heartbeat_age_seconds":0}
                for i in range(700)
            ),
            max_reads=500,
        )
        state=resilience.normalize_resilience({"watchdogs":watchdogs})
        self.assertEqual(len(state["watchdogs"]),500)
        self.assertEqual(watchdogs.reads,500)

        delegations=(
            {"delegation_id":f"delegation-{i}","state":"BLOCKED"}
            for i in range(505)
        )
        normalized=resilience.normalize_delegations(delegations)
        self.assertEqual(len(normalized),500)
        self.assertEqual(normalized[0]["delegation_id"],"delegation-5")
        self.assertEqual(normalized[-1]["delegation_id"],"delegation-504")

    def test_resilience_and_action_receipt_avoid_unbounded_list_before_slice(self):
        resilience_src=Path("atlasquant_aion_resilience.py").read_text(encoding="utf-8")
        receipt_src=Path("atlasquant_aion_action_receipt.py").read_text(encoding="utf-8")

        self.assertNotIn("list(rows or [])[-500:]",resilience_src)
        self.assertNotIn('list(item.get("watchdogs") or [])[:500]',resilience_src)
        self.assertNotIn('list(item.get("circuit_breakers") or [])[:500]',resilience_src)
        self.assertNotIn('list(item.get("resource_governors") or [])[:500]',resilience_src)
        self.assertIn("deque(rows or (), maxlen=500)",resilience_src)
        self.assertIn('islice(item.get("watchdogs") or (), 500)',resilience_src)
        self.assertIn('islice(item.get("circuit_breakers") or (), 500)',resilience_src)
        self.assertIn('islice(item.get("resource_governors") or (), 500)',resilience_src)
        self.assertIn("islice(watchdogs or (),500)",resilience_src)
        self.assertIn("islice(breakers or (),500)",resilience_src)
        self.assertIn("islice(governors or (),500)",resilience_src)

        self.assertNotIn("list(values or [])[:40]",receipt_src)
        self.assertIn("islice(values or (), 40)",receipt_src)


if __name__=="__main__":
    unittest.main()
