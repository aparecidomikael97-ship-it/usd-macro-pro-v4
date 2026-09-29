from __future__ import annotations
import json
import unittest

from atlasquant_aion_durable_tasks import (
    DurableTaskError,
    cancel_durable_task,
    durable_tasks_digest,
    durable_tasks_summary,
    MAX_STEPS,
    MAX_TASKS,
    new_durable_task,
    normalize_durable_task,
    normalize_durable_tasks,
    normalize_steps,
    pause_durable_task,
    prepare_resume,
    record_resume,
    retry_step,
    update_step,
)


class AtlasQuantAionDurableTasksTests(unittest.TestCase):
    def _finish(self,task,step_id,**kwargs):
        task=update_step(task,step_id,"RUNNING",access={"role":"ADMIN"},approved=True)
        return update_step(task,step_id,"DONE",access={"role":"ADMIN"},approved=True,**kwargs)

    def _task(self):
        return new_durable_task(
            "Portable Core",
            objective="Fechar módulo com validação.",
            steps=[
                {"step_id":"spec","title":"Especificar","state":"PENDING"},
                {"step_id":"test","title":"Rodar testes","state":"PENDING"},
                {"step_id":"merge","title":"Mesclar","state":"PENDING","requires_approval":True},
            ],
            checkpoint_digest="cp-a",
            created_at="2026-09-25T16:00:00+00:00",
        )

    def test_resume_restores_cursor_without_executing(self):
        task=self._task()
        task=self._finish(task,"spec",result_note="Spec pronta.")
        task=pause_durable_task(task,checkpoint_digest="cp-a")
        view=prepare_resume(
            task,
            expected_revision=task["revision"],
            checkpoint_digest="cp-a",
        )
        self.assertEqual(view["state"],"RESUME_READY")
        self.assertEqual(view["next_step"]["step_id"],"test")
        self.assertTrue(view["restores_state_only"])
        self.assertFalse(view["executes_action"])

    def test_revision_conflict_blocks_resume(self):
        task=self._task()
        view=prepare_resume(task,expected_revision=999,checkpoint_digest="cp-a")
        self.assertEqual(view["state"],"BLOCK")
        self.assertIn("REVISION_CONFLICT",view["blockers"])

    def test_checkpoint_change_blocks_resume_when_both_digests_known(self):
        task=self._task()
        view=prepare_resume(
            task,
            expected_revision=task["revision"],
            checkpoint_digest="cp-b",
        )
        self.assertEqual(view["state"],"BLOCK")
        self.assertIn("CHECKPOINT_CHANGED",view["blockers"])

    def test_completed_steps_advance_cursor_and_done_state(self):
        task=self._task()
        task=self._finish(task,"spec")
        self.assertEqual(task["cursor"],1)
        task=self._finish(task,"test")
        self.assertEqual(task["cursor"],2)
        task=self._finish(task,"merge")
        self.assertEqual(task["state"],"DONE")
        self.assertEqual(task["cursor"],3)

    def test_waiting_approval_is_persisted_not_bypassed(self):
        task=self._task()
        task=self._finish(task,"spec")
        task=self._finish(task,"test")
        task=update_step(task,"merge","WAITING_APPROVAL",blocker="Aprovação necessária.")
        self.assertEqual(task["state"],"WAITING_APPROVAL")
        view=prepare_resume(task,expected_revision=task["revision"],checkpoint_digest="cp-a")
        self.assertEqual(view["state"],"RESUME_READY")
        self.assertEqual(view["task_state"],"WAITING_APPROVAL")
        self.assertEqual(view["next_step"]["step_id"],"merge")
        self.assertFalse(view["executes_action"])
        resumed=record_resume(task,checkpoint_digest="cp-a")
        self.assertEqual(resumed["state"],"WAITING_APPROVAL")

    def test_future_blocker_does_not_skip_current_cursor(self):
        task=self._task()
        task=update_step(task,"merge","BLOCKED",blocker="Ainda não.")
        self.assertEqual(task["cursor"],0)
        self.assertEqual(task["next_action"],"Especificar")
        self.assertEqual(task["state"],"PLANNED")

    def test_record_resume_only_changes_state_metadata(self):
        task=self._task()
        resumed=record_resume(task,checkpoint_digest="cp-a")
        self.assertEqual(resumed["resume_generation"],1)
        self.assertEqual(resumed["state"],"PAUSED")
        self.assertFalse(resumed["automatic_resume_executes"])

    def test_invalid_numeric_metadata_normalizes_fail_safe(self):
        task=self._task()
        task["cursor"]="not-a-number"
        task["revision"]="bad"
        task["resume_generation"]="bad"
        task["steps"][0]["attempts"]="bad"
        view=prepare_resume(task,checkpoint_digest="cp-a")
        self.assertEqual(view["cursor"],0)
        self.assertEqual(view["revision"],1)

    def test_summary_and_digest_are_deterministic(self):
        task=self._task()
        self.assertEqual(durable_tasks_digest([task]),durable_tasks_digest([task]))
        summary=durable_tasks_summary([task])
        self.assertEqual(summary["tasks"],1)
        self.assertEqual(summary["resumable"],1)
        self.assertFalse(summary["automatic_resume_executes"])

    def test_terminal_done_and_canceled_tasks_do_not_run_again(self):
        done=self._task()
        done=self._finish(done,"spec")
        done=self._finish(done,"test")
        done=self._finish(done,"merge")
        with self.assertRaises(DurableTaskError) as done_error:
            retry_step(done,"spec",idempotency_key="again")
        self.assertEqual(done_error.exception.result["error_code"],"TASK_TERMINAL")
        self.assertFalse(done_error.exception.result["executes_action"])

        canceled=cancel_durable_task(self._task())
        with self.assertRaises(DurableTaskError) as canceled_error:
            update_step(canceled,"spec","RUNNING",access={"role":"ADMIN"},approved=True)
        self.assertEqual(canceled_error.exception.result["error_code"],"TASK_TERMINAL")

    def test_retry_is_idempotent_for_same_key_and_rejects_conflict(self):
        task=self._task()
        task=update_step(task,"spec","RUNNING",access={"role":"ADMIN"},approved=True)
        task=update_step(task,"spec","FAILED",blocker="timeout")
        first=retry_step(task,"spec",access={"role":"ADMIN"},approved=True,idempotency_key="spec-1")
        self.assertEqual(first["steps"][0]["state"],"RUNNING")
        self.assertEqual(first["steps"][0]["attempts"],2)
        again=retry_step(first,"spec",access={"role":"ADMIN"},approved=True,idempotency_key="spec-1")
        self.assertEqual(again["revision"],first["revision"])
        self.assertEqual(again["steps"][0]["attempts"],2)
        with self.assertRaises(DurableTaskError) as conflict:
            retry_step(first,"spec",access={"role":"ADMIN"},approved=True,idempotency_key="spec-2")
        self.assertEqual(conflict.exception.result["error_code"],"IDEMPOTENCY_CONFLICT")

    def test_unsafe_or_exhausted_retry_fails_closed(self):
        task=new_durable_task(
            "Unsafe retry",
            steps=[{"step_id":"write","title":"Write","guardian_action":"save_checkpoint","external_side_effects":True}],
            created_at="2026-09-25T16:00:00+00:00",
        )
        task=update_step(task,"write","RUNNING",access={"role":"ADMIN"},approved=True)
        task=update_step(task,"write","FAILED",blocker="provider down")
        with self.assertRaises(DurableTaskError) as unsafe:
            retry_step(task,"write",access={"role":"ADMIN"},approved=True,idempotency_key="write-1")
        self.assertEqual(unsafe.exception.result["error_code"],"RETRY_UNSAFE")

    def test_string_approval_cannot_release_waiting_step(self):
        task=self._finish(self._finish(self._task(),"spec"),"test")
        task=update_step(task,"merge","WAITING_APPROVAL",blocker="Aprovação necessária.")
        for flag in ("yes","true",1):
            with self.subTest(flag=flag):
                with self.assertRaises(DurableTaskError) as blocked:
                    update_step(task,"merge","RUNNING",access={"role":"ADMIN"},approved=flag)
                self.assertEqual(blocked.exception.result["error_code"],"APPROVAL_REQUIRED")

    def test_out_of_order_and_stale_revision_fail_closed(self):
        task=self._task()
        with self.assertRaises(DurableTaskError) as order:
            update_step(task,"test","RUNNING",access={"role":"ADMIN"},approved=True)
        self.assertEqual(order.exception.result["error_code"],"STEP_OUT_OF_ORDER")
        with self.assertRaises(DurableTaskError) as stale:
            update_step(task,"spec","RUNNING",access={"role":"ADMIN"},approved=True,expected_revision=99)
        self.assertEqual(stale.exception.result["error_code"],"REVISION_CONFLICT")

    def _fail(self,task,step_id="spec"):
        task=update_step(task,step_id,"RUNNING",access={"role":"ADMIN"},approved=True)
        return update_step(task,step_id,"FAILED",blocker="timeout")

    def test_consumed_retry_key_does_not_start_another_attempt_after_later_failure(self):
        task=self._fail(self._task())
        started=retry_step(task,"spec",access={"role":"ADMIN"},approved=True,idempotency_key="k1")
        failed=update_step(started,"spec","FAILED",blocker="timeout again")
        attempts=failed["steps"][0]["attempts"]
        revision=failed["revision"]
        replay=retry_step(failed,"spec",access={"role":"ADMIN"},approved=True,idempotency_key="k1")
        self.assertEqual(replay["steps"][0]["state"],"FAILED")
        self.assertEqual(replay["steps"][0]["attempts"],attempts)
        self.assertEqual(replay["revision"],revision)
        self.assertIn("k1",replay["steps"][0]["consumed_idempotency_keys"])

        second=retry_step(failed,"spec",access={"role":"ADMIN"},approved=True,idempotency_key="k2")
        self.assertEqual(second["steps"][0]["state"],"RUNNING")
        self.assertEqual(second["steps"][0]["attempts"],attempts+1)
        failed_again=update_step(second,"spec","FAILED",blocker="third")
        replay_k2=retry_step(failed_again,"spec",access={"role":"ADMIN"},approved=True,idempotency_key="k2")
        self.assertEqual(replay_k2["steps"][0]["attempts"],second["steps"][0]["attempts"])
        self.assertEqual(replay_k2["revision"],failed_again["revision"])

    def test_consumed_key_survives_pause_resume_normalize_and_snapshot(self):
        task=self._fail(self._task())
        task=retry_step(task,"spec",access={"role":"ADMIN"},approved=True,idempotency_key="k1")
        task=update_step(task,"spec","FAILED",blocker="again")
        paused=pause_durable_task(task,checkpoint_digest="cp-a")
        resumed=record_resume(paused,checkpoint_digest="cp-a")
        replay=retry_step(resumed,"spec",access={"role":"ADMIN"},approved=True,idempotency_key="k1")
        self.assertEqual(replay["steps"][0]["attempts"],task["steps"][0]["attempts"])
        normalized=normalize_durable_task(replay)
        self.assertEqual(normalized["steps"][0]["consumed_idempotency_keys"],["k1"])
        snapshot=json.loads(json.dumps(normalized))
        restored=normalize_durable_task(snapshot)
        self.assertEqual(restored["steps"][0]["consumed_idempotency_keys"],["k1"])
        again=retry_step(restored,"spec",access={"role":"ADMIN"},approved=True,idempotency_key="k1")
        self.assertEqual(again["steps"][0]["attempts"],restored["steps"][0]["attempts"])

    def test_retry_key_edges_and_history_limit_fail_closed(self):
        task=self._fail(self._task())
        for key in ("",None):
            with self.subTest(key=key):
                with self.assertRaises(DurableTaskError) as empty:
                    retry_step(task,"spec",access={"role":"ADMIN"},approved=True,idempotency_key=key)
                self.assertEqual(empty.exception.result["error_code"],"IDEMPOTENCY_KEY_REQUIRED")
        with self.assertRaises(DurableTaskError) as huge:
            retry_step(task,"spec",access={"role":"ADMIN"},approved=True,idempotency_key="k"*129)
        self.assertEqual(huge.exception.result["error_code"],"IDEMPOTENCY_KEY_INVALID")

        limited=new_durable_task(
            "Limited",
            steps=[{
                "step_id":"spec",
                "title":"Spec",
                "state":"FAILED",
                "attempts":2,
                "max_attempts":2,
                "guardian_action":"read",
            }],
            created_at="2026-09-25T16:00:00+00:00",
        )
        with self.assertRaises(DurableTaskError) as limit:
            retry_step(limited,"spec",access={"role":"ADMIN"},approved=True,idempotency_key="k2")
        self.assertEqual(limit.exception.result["error_code"],"RETRY_LIMIT")

        full=new_durable_task(
            "Full history",
            steps=[{
                "step_id":"spec",
                "title":"Spec",
                "state":"FAILED",
                "attempts":1,
                "max_attempts":100,
                "guardian_action":"read",
                "consumed_idempotency_keys":[f"k{i:02d}" for i in range(32)],
            }],
            created_at="2026-09-25T16:00:00+00:00",
        )
        replay=retry_step(full,"spec",access={"role":"ADMIN"},approved=True,idempotency_key="k00")
        self.assertEqual(replay["steps"][0]["attempts"],1)
        with self.assertRaises(DurableTaskError) as history:
            retry_step(full,"spec",access={"role":"ADMIN"},approved=True,idempotency_key="new-key")
        self.assertEqual(history.exception.result["error_code"],"IDEMPOTENCY_HISTORY_FULL")

    def test_numeric_and_string_approval_flags_do_not_approve_retry_gate(self):
        task=self._finish(self._finish(self._task(),"spec"),"test")
        task=update_step(task,"merge","WAITING_APPROVAL",blocker="Aprovação necessária.")
        for flag in ("true","yes",1,None):
            with self.subTest(flag=flag):
                with self.assertRaises(DurableTaskError) as blocked:
                    update_step(task,"merge","RUNNING",access={"role":"ADMIN"},approved=flag)
                self.assertEqual(blocked.exception.result["error_code"],"APPROVAL_REQUIRED")


    def test_step_generator_is_not_consumed_past_step_limit(self):
        consumed={"count":0}
        def rows():
            for index in range(MAX_STEPS+1):
                if index>=MAX_STEPS:
                    raise AssertionError("step iterable consumed past limit")
                consumed["count"]+=1
                yield {"step_id":f"s{index}","title":"Step","state":"PENDING"}
        normalized=normalize_steps(rows())
        self.assertEqual(len(normalized),MAX_STEPS)
        self.assertEqual(consumed["count"],MAX_STEPS)

    def test_task_generator_preserves_recent_tail_with_bounded_buffer(self):
        total=MAX_TASKS+25
        def rows():
            for index in range(total):
                yield new_durable_task(
                    f"Task {index}",
                    created_at=f"2026-09-25T16:{index%60:02d}:00+00:00",
                )
        normalized=normalize_durable_tasks(rows())
        self.assertEqual(len(normalized),MAX_TASKS)
        self.assertEqual(normalized[0]["title"],"Task 25")
        self.assertEqual(normalized[-1]["title"],f"Task {total-1}")


if __name__=="__main__":
    unittest.main()
