from pathlib import Path
import unittest

import atlasquant_aion_action_receipt as action_receipt
import atlasquant_aion_approval_inbox as approval_inbox
import atlasquant_aion_background_executor as background_executor
import atlasquant_aion_capabilities as capabilities
import atlasquant_aion_continuity as continuity
import atlasquant_aion_dev_fusion as dev_fusion
import atlasquant_aion_digital_twin as digital_twin
import atlasquant_aion_event_journal as event_journal
import atlasquant_aion_evaluation_lab as evaluation_lab
import atlasquant_aion_fortress as fortress
import atlasquant_aion_global_worker as global_worker
import atlasquant_aion_learning as learning
import atlasquant_aion_model_registry as model_registry
import atlasquant_aion_operations as operations
import atlasquant_aion_provider as provider
import atlasquant_aion_release_confidence as release_confidence
import atlasquant_aion_skill_certification as skill_certification
import atlasquant_aion_resilience as resilience
import atlasquant_aion_specialist_session as specialist_session
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


class GuardedList(list):
    def __init__(self, values, *, max_reads):
        super().__init__(values)
        self.max_reads=max_reads
        self.reads=0

    def __iter__(self):
        parent=super().__iter__()
        while True:
            if self.reads>=self.max_reads:
                raise AssertionError("list consumed beyond explicit prefix bound")
            try:
                value=next(parent)
            except StopIteration:
                return
            self.reads+=1
            yield value


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


    def test_executor_due_selection_keeps_only_batch_in_memory_and_preserves_count(self):
        source=GuardedIterable(
            (
                {
                    "due":True,
                    "due_at":f"2026-09-29T12:{59-(i%60):02d}:00+00:00",
                    "schedule_id":f"schedule-{i:03d}",
                }
                for i in range(100)
            ),
            max_reads=100,
        )
        selected,total=background_executor._select_due_schedules(source,3)
        self.assertEqual(total,100)
        self.assertEqual(len(selected),3)
        self.assertEqual(source.reads,100)
        keys=[
            (str(row.get("due_at") or ""),str(row.get("schedule_id") or ""))
            for row in selected
        ]
        self.assertEqual(keys,sorted(keys))

        source_text=Path("atlasquant_aion_background_executor.py").read_text(encoding="utf-8")
        self.assertNotIn('list(scheduler.get("schedules") or [])',source_text)
        self.assertIn("_select_due_schedules(",source_text)
        self.assertNotIn("for schedule in due[:max_jobs]",source_text)

    def test_approval_rows_do_not_duplicate_materialize_items(self):
        source=Path("atlasquant_aion_approval_inbox.py").read_text(encoding="utf-8")
        self.assertNotIn("for item in list(items or []):",source)
        self.assertIn("for item in items or []:",source)


    def test_global_worker_claim_rejects_oversized_intent_without_full_materialization(self):
        source=GuardedIterable(({} for _ in range(100)),max_reads=global_worker.MAX_JOBS+1)
        with self.assertRaises(ValueError):
            global_worker._claim_state(
                global_worker._default_state(),
                runtime_id="resource-bound-test",
                now=global_worker._now(),
                work_intent={"occurrences":source},
            )
        self.assertEqual(source.reads,global_worker.MAX_JOBS+1)

        source_text=Path("atlasquant_aion_global_worker.py").read_text(encoding="utf-8")
        self.assertNotIn('list(scheduler.get("schedules") or [])',source_text)
        self.assertIn("nsmallest(",source_text)
        self.assertIn('islice(work.get("occurrences") or (), MAX_JOBS + 1)',source_text)


    def test_skill_certification_unique_does_not_duplicate_full_list(self):
        values=GuardedList((f"scope-{i}" for i in range(100)),max_reads=6)
        normalized=skill_certification._unique(values,limit=3)
        self.assertEqual(normalized,["scope-0","scope-1","scope-2"])
        self.assertEqual(values.reads,3)

        source=Path("atlasquant_aion_skill_certification.py").read_text(encoding="utf-8")
        self.assertNotIn("list(values)[:limit * 2]",source)
        self.assertIn("islice(values, max(0, limit * 2))",source)
        self.assertNotIn('list(tool.get("required_scopes") or [])',source)


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


    def test_additional_explicit_prefix_bounds_do_not_overread(self):
        refs=GuardedIterable((f"ref-{i}" for i in range(100)),max_reads=6)
        self.assertEqual(resilience._refs(refs,limit=3),["ref-0","ref-1","ref-2"])
        self.assertLessEqual(refs.reads,6)

        caps_source=GuardedIterable(
            (resilience.CAPABILITIES[i % len(resilience.CAPABILITIES)] for i in range(200)),
            max_reads=100,
        )
        caps=resilience._caps(caps_source)
        self.assertTrue(caps)
        self.assertEqual(caps_source.reads,100)

        signals=GuardedIterable(
            (
                {
                    "kind":f"signal-{i}",
                    "severity":"LOW",
                    "evidence_state":"CONFIRMED",
                }
                for i in range(300)
            ),
            max_reads=200,
        )
        plan=fortress.cyber_immune_plan(signals)
        self.assertEqual(len(plan["signals"]),200)
        self.assertEqual(signals.reads,200)

        memory_hits=GuardedIterable(
            (
                {"path":f"memory/{i}","excerpt":f"excerpt-{i}"}
                for i in range(20)
            ),
            max_reads=5,
        )
        lines=provider._evidence_lines(memory_hits)
        self.assertEqual(len(lines),5)
        self.assertEqual(memory_hits.reads,5)

    def test_additional_known_prefix_materializations_are_absent(self):
        resilience_src=Path("atlasquant_aion_resilience.py").read_text(encoding="utf-8")
        capabilities_src=Path("atlasquant_aion_capabilities.py").read_text(encoding="utf-8")
        fortress_src=Path("atlasquant_aion_fortress.py").read_text(encoding="utf-8")
        provider_src=Path("atlasquant_aion_provider.py").read_text(encoding="utf-8")
        specialist_src=Path("atlasquant_aion_specialist_session.py").read_text(encoding="utf-8")

        self.assertNotIn("list(values or [])[:limit*2]",resilience_src)
        self.assertNotIn("list(values or [])[:100]",resilience_src)
        self.assertIn("islice(values or (), max(0, limit*2))",resilience_src)
        self.assertIn("islice(values or (), 100)",resilience_src)

        self.assertNotIn("list(items)[:limit]",capabilities_src)
        self.assertIn("islice(items, max(0, limit))",capabilities_src)

        self.assertNotIn("list(signals or [])[:200]",fortress_src)
        self.assertIn("islice(signals or (), 200)",fortress_src)

        self.assertNotIn("list(memory_hits or [])[:5]",provider_src)
        self.assertIn("islice(memory_hits or (), 5)",provider_src)

        self.assertNotIn("list(value)[:300]",specialist_src)
        self.assertNotIn('list(conflict.get("values") or [])[:2]',specialist_src)
        self.assertIn("value[:300]",specialist_src)
        self.assertIn('islice(conflict.get("values") or (), 2)',specialist_src)


if __name__=="__main__":
    unittest.main()
