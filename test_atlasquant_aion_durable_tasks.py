from __future__ import annotations
import unittest

from atlasquant_aion_durable_tasks import (
    durable_tasks_digest,
    durable_tasks_summary,
    new_durable_task,
    pause_durable_task,
    prepare_resume,
    record_resume,
    update_step,
)


class AtlasQuantAionDurableTasksTests(unittest.TestCase):
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
        task=update_step(task,"spec","DONE",result_note="Spec pronta.")
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
        task=update_step(task,"spec","DONE")
        self.assertEqual(task["cursor"],1)
        task=update_step(task,"test","DONE")
        self.assertEqual(task["cursor"],2)
        task=update_step(task,"merge","DONE")
        self.assertEqual(task["state"],"DONE")
        self.assertEqual(task["cursor"],3)

    def test_waiting_approval_is_persisted_not_bypassed(self):
        task=self._task()
        task=update_step(task,"spec","DONE")
        task=update_step(task,"test","DONE")
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
        self.assertEqual(task["state"],"PAUSED")

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


if __name__=="__main__":
    unittest.main()
