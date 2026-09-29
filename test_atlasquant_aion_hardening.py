"""Offline regressions for durable state, safety and Checkpoint Mestre V18 round trips."""
from copy import deepcopy
import json
import unittest

from atlasquant_aion_durable_tasks import (
    DurableTaskError, cancel_durable_task, durable_tasks_digest, new_durable_task,
    normalize_durable_task, pause_durable_task, prepare_resume, record_resume,
    retry_step, transition_durable_task, update_step, upsert_durable_task,
)
from atlasquant_aion_continuity import new_mission, mission_task_consistency
from atlasquant_aion_memory import (
    default_checkpoint, ensure_operating_checkpoint, update_durable_tasks_checkpoint,
    checkpoint_source_digest, checkpoint_integrity_report,
)
from atlasquant_aion_observability import new_event, normalize_event, sanitize_metadata

ADMIN={"role":"ADMIN"}
NOW="2026-09-27T08:00:00+00:00"


class AionHardeningTests(unittest.TestCase):
    def task(self, **step_fields):
        return new_durable_task("Local work",steps=[{"title":"Inspect","step_id":"s",**step_fields}],
                                checkpoint_digest="cp-a",created_at=NOW)

    def start(self,task):
        return update_step(task,"s","RUNNING",access=ADMIN,changed_at=NOW)

    def assertBlocked(self,code,fn,*args,**kwargs):
        before=deepcopy(args)
        with self.assertRaises(DurableTaskError) as ctx:
            fn(*args,**kwargs)
        self.assertEqual(ctx.exception.result["error_code"],code)
        self.assertEqual(args,before)

    def test_task_state_lifecycle_and_terminal(self):
        task=new_durable_task("No steps",created_at=NOW)
        for state in ("RUNNING","PAUSED","RUNNING","DONE"):
            task=transition_durable_task(task,state,access=ADMIN)
            self.assertEqual(task["state"],state)
        self.assertBlocked("INVALID_TRANSITION",transition_durable_task,task,"RUNNING",access=ADMIN)
        task=cancel_durable_task(self.task())
        self.assertBlocked("INVALID_TRANSITION",transition_durable_task,task,"RUNNING",access=ADMIN)

    def test_steps_cannot_skip_execution_or_reopen_terminal(self):
        task=self.task()
        self.assertBlocked("INVALID_TRANSITION",update_step,task,"s","DONE",access=ADMIN)
        done=update_step(self.start(task),"s","DONE",access=ADMIN)
        self.assertBlocked("TASK_TERMINAL",update_step,done,"s","RUNNING",access=ADMIN)
        skipped=update_step(task,"s","SKIPPED")
        self.assertBlocked("TASK_TERMINAL",update_step,skipped,"s","RUNNING",access=ADMIN)

    def test_pause_resume_keep_approval_and_blocker(self):
        for state in ("WAITING_APPROVAL","BLOCKED"):
            with self.subTest(state=state):
                task=update_step(self.task(),"s",state,blocker="Needs review")
                task=pause_durable_task(task,blocker="")
                resumed=record_resume(task,expected_revision=task["revision"],checkpoint_digest="cp-a")
                self.assertEqual(resumed["state"],state)
                self.assertEqual(resumed["blocker"],"Needs review")
                self.assertFalse(prepare_resume(resumed,checkpoint_digest="cp-a")["executes_action"])
                code="UNBLOCK_REQUIRED" if state=="BLOCKED" else "APPROVAL_REQUIRED"
                self.assertBlocked(code,update_step,resumed,"s","RUNNING",access=ADMIN)

    def test_resume_checks_revision_digest_and_does_not_mutate(self):
        task=self.task()
        self.assertBlocked("REVISION_CONFLICT",record_resume,task,expected_revision=99,checkpoint_digest="cp-a")
        self.assertBlocked("CHECKPOINT_CHANGED",record_resume,task,checkpoint_digest="cp-b")
        self.assertBlocked("CHECKPOINT_REQUIRED",record_resume,task)
        resumed=record_resume(task,expected_revision=1,checkpoint_digest="cp-a")
        self.assertEqual(resumed["resume_generation"],1)
        self.assertEqual(resumed["steps"][0]["attempts"],0)

    def test_mutations_reject_stale_revision(self):
        task=self.task()
        for fn, args in ((pause_durable_task,()),(cancel_durable_task,()),
                         (update_step,("s","RUNNING")),(transition_durable_task,("RUNNING",))):
            self.assertBlocked("REVISION_CONFLICT",fn,task,*args,expected_revision=9)
        newer=pause_durable_task(task)
        self.assertBlocked("REVISION_CONFLICT",upsert_durable_task,[newer],task)

    def test_retry_retains_error_and_increments_once(self):
        task=update_step(self.start(self.task(max_attempts=2)),"s","FAILED",blocker="temporary error")
        self.assertBlocked("RETRY_REQUIRED",update_step,task,"s","RUNNING",access=ADMIN,unblock_reason="fixed")
        retried=retry_step(task,"s",access=ADMIN,idempotency_key="inspect-1")
        self.assertEqual(retried["steps"][0]["attempts"],2)
        self.assertEqual(retried["steps"][0]["last_error"],"temporary error")
        self.assertTrue(any(e["event_type"]=="TASK_FAILED" for e in retried["audit_events"]))
        self.assertEqual(retry_step(retried,"s",access=ADMIN,idempotency_key="inspect-1"),retried)
        self.assertBlocked("IDEMPOTENCY_CONFLICT",retry_step,retried,"s",access=ADMIN,idempotency_key="other")
        failed=update_step(retried,"s","FAILED",blocker="again")
        replay=retry_step(failed,"s",access=ADMIN,idempotency_key="inspect-1")
        self.assertEqual(replay["steps"][0]["attempts"],failed["steps"][0]["attempts"])
        self.assertEqual(replay["steps"][0]["state"],"FAILED")
        self.assertBlocked("RETRY_LIMIT",retry_step,failed,"s",access=ADMIN,idempotency_key="inspect-2")

    def test_retry_requires_key_and_fresh_approval(self):
        task=self.task(requires_approval=True)
        task=update_step(task,"s","RUNNING",access=ADMIN,approved=True)
        task=update_step(task,"s","FAILED",blocker="retry me")
        self.assertBlocked("APPROVAL_REQUIRED",retry_step,task,"s",access=ADMIN,idempotency_key="read-1")
        self.assertBlocked("IDEMPOTENCY_KEY_REQUIRED",retry_step,task,"s",access=ADMIN,approved=True)

    def test_guardian_keeps_dangerous_actions_denied(self):
        for action in ("deploy_production","publish_social","charge_customer","write_secret","real_trade","delete_all"):
            task=self.task(guardian_action=action)
            with self.subTest(action=action):
                if action=="write_secret":
                    # Existing Guardian allows explicit secret operations; retries do not.
                    task["steps"][0]["state"]="FAILED"
                    task["state"]="BLOCKED"
                    self.assertBlocked("RETRY_UNSAFE",retry_step,task,"s",access=ADMIN,approved=True,idempotency_key="x")
                else:
                    self.assertBlocked("GUARDIAN_DENIED",update_step,task,"s","RUNNING",access=ADMIN,approved=True)
        task=self.task(external_side_effects=True)
        task["steps"][0]["state"]="FAILED"
        task["state"]="BLOCKED"
        self.assertBlocked("RETRY_UNSAFE",retry_step,task,"s",access=ADMIN,approved=True,idempotency_key="x")

    def test_cancel_preserves_evidence_artifacts_history(self):
        task=self.start(self.task())
        task["artifacts"]=["report.json"]
        task["evidence_refs"]=["test:1"]
        canceled=cancel_durable_task(task,changed_at=NOW)
        for key in ("artifacts","evidence_refs","steps"):
            self.assertEqual(canceled[key],task[key])
        self.assertEqual(canceled["canceled_at"],NOW)
        self.assertEqual(canceled["next_action"],"")
        self.assertEqual(canceled["audit_events"][-1]["event_type"],"TASK_CANCELED")
        self.assertBlocked("TASK_TERMINAL",record_resume,canceled,checkpoint_digest="cp-a")

    def test_nested_secrets_and_short_values_are_redacted(self):
        keys=("password","passwd","token","api_key","apikey","authorization","secret","cookie","credential","bearer")
        for key in keys:
            with self.subTest(key=key):
                evidence={"metadata":{"items":[{key:"xy"}],"note":f"{key}=xy"}}
                event=normalize_event(new_event("check","ok",evidence=evidence,created_at=NOW))
                self.assertNotIn("xy",json.dumps(event))
                self.assertIn("[REDACTED]",json.dumps(event))
        self.assertEqual(sanitize_metadata({"attempts":2}),{"attempts":2})

    def test_mission_task_inconsistency_is_detected(self):
        mission=new_mission("Mission",created_at=NOW)
        mission["status"]="DONE"
        task=self.start(self.task())
        task["mission_id"]=mission["mission_id"]
        report=mission_task_consistency([mission],[task])
        self.assertEqual(report["state"],"INCONSISTENT")
        self.assertEqual(report["issues"][0]["error_code"],"MISSION_TASK_STATE_MISMATCH")

    def test_checkpoint_roundtrip_preserves_context_and_integrity(self):
        task=record_resume(self.task(),checkpoint_digest="cp-a")
        cp=update_durable_tasks_checkpoint(default_checkpoint(),records=[task])
        restored=ensure_operating_checkpoint(json.loads(json.dumps(cp)))
        self.assertEqual(restored["checkpoint_version"],18)
        self.assertEqual(restored["durable_tasks"]["records"][0],task)
        self.assertEqual(checkpoint_integrity_report(restored)["state"],"CONFIRMED")
        self.assertEqual(task["correlation_id"],task["steps"][0]["correlation_id"])
        for event in task["audit_events"]:
            self.assertEqual(event["evidence"]["correlation_id"],task["correlation_id"])
        self.assertBlocked("REVISION_CHECKPOINT_CONFLICT",update_durable_tasks_checkpoint,cp,
                           records=[task],expected_checkpoint_digest="stale")
        self.assertEqual(update_durable_tasks_checkpoint(cp,records=[task],
                         expected_checkpoint_digest=checkpoint_source_digest(cp))["durable_tasks"],cp["durable_tasks"])

    def test_legacy_records_do_not_gain_fields_on_normalization(self):
        task=self.task()
        task.pop("correlation_id")
        task.pop("audit_events")
        task["steps"][0].pop("correlation_id")
        self.assertEqual(normalize_durable_task(task),task)
        self.assertEqual(durable_tasks_digest([task]),durable_tasks_digest([normalize_durable_task(task)]))

    def test_future_step_annotation_does_not_release_blocker(self):
        task=new_durable_task("Two",steps=[{"step_id":"a"},{"step_id":"b"}],created_at=NOW)
        task=pause_durable_task(task,blocker="Do not run")
        changed=update_step(task,"b","READY")
        self.assertEqual(changed["state"],"BLOCKED")
        self.assertEqual(changed["blocker"],"Do not run")

    def test_explicit_unblock_and_approval_are_required_for_start(self):
        task=update_step(self.task(),"s","BLOCKED",blocker="Check environment")
        task=update_step(task,"s","RUNNING",access=ADMIN,unblock_reason="Environment verified")
        self.assertEqual(task["state"],"RUNNING")
        waiting=update_step(self.task(),"s","WAITING_APPROVAL")
        self.assertBlocked("GUARDIAN_DENIED",update_step,waiting,"s","RUNNING",approved=True)
        started=update_step(waiting,"s","RUNNING",access=ADMIN,approved=True)
        self.assertEqual(started["state"],"RUNNING")

    def test_checkpoint_rejects_stale_task_and_divergent_mission(self):
        original=self.task()
        task=self.start(original)
        cp=update_durable_tasks_checkpoint(default_checkpoint(),records=[task])
        self.assertBlocked("REVISION_CONFLICT",update_durable_tasks_checkpoint,cp,records=[original])
        mission=new_mission("Mission",created_at=NOW)
        mission["status"]="DONE"
        cp["continuity"]["missions"]=[mission]
        task["mission_id"]=mission["mission_id"]
        task["revision"]+=1
        self.assertBlocked("MISSION_TASK_INCONSISTENT",update_durable_tasks_checkpoint,cp,records=[task])


if __name__=="__main__":
    unittest.main()
