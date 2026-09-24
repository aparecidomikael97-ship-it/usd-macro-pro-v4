import unittest

from atlasquant_aion_operations import (
    approve_task,
    approval_requirement,
    executable_decision,
    new_task,
    queue_summary,
    transition_task,
    upsert_task,
)


class AtlasQuantAionOperationsTests(unittest.TestCase):
    def setUp(self):
        self.admin={"role":"ADMIN","username":"admin.01"}

    def test_new_task_is_normalized_and_zero_cost(self):
        task=new_task("  Revisar   interface  ",domain="development",priority="P1")
        self.assertEqual(task["title"],"Revisar interface")
        self.assertEqual(task["domain"],"development")
        self.assertEqual(task["priority"],"P1")
        self.assertEqual(task["status"],"TODO")
        self.assertEqual(task["estimated_monthly_cost_usd"],0.0)

    def test_sensitive_publish_requires_approval_and_feature_flag(self):
        task=new_task("Publicar vídeo",domain="studio",action="publish_social")
        req=approval_requirement(task,self.admin,feature_flags={"social_publish":False})
        self.assertTrue(req["required"])
        queue=approve_task([task],task["task_id"],self.admin,feature_flags={"social_publish":False})
        self.assertEqual(queue[0]["status"],"BLOCKED")
        self.assertTrue(queue[0]["approval"]["attempted"])
        self.assertFalse(queue[0]["approval"]["approved"])
        decision_after_flag_change=executable_decision(
            queue[0],
            self.admin,
            feature_flags={"social_publish":True},
        )
        self.assertFalse(decision_after_flag_change["allowed"])
        queue=approve_task(
            queue,
            task["task_id"],
            self.admin,
            feature_flags={"social_publish":True},
        )
        self.assertTrue(queue[0]["approval"]["approved"])

    def test_blocked_approval_cannot_be_reused_after_feature_flag_changes(self):
        task=new_task("Publicar catálogo",domain="business",action="publish_marketplace")
        queue=approve_task(
            [task],
            task["task_id"],
            self.admin,
            feature_flags={"marketplace_publish":False},
        )
        self.assertFalse(queue[0]["approval"]["approved"])
        self.assertFalse(
            executable_decision(
                queue[0],
                self.admin,
                feature_flags={"marketplace_publish":True},
            )["allowed"]
        )
        queue=approve_task(
            queue,
            task["task_id"],
            self.admin,
            feature_flags={"marketplace_publish":True},
        )
        self.assertTrue(queue[0]["approval"]["approved"])
        self.assertTrue(
            executable_decision(
                queue[0],
                self.admin,
                feature_flags={"marketplace_publish":True},
            )["allowed"]
        )


    def test_approval_never_executes_action(self):
        task=new_task("Publicar vídeo",domain="studio",action="publish_social")
        queue=approve_task([task],task["task_id"],self.admin,feature_flags={"social_publish":True})
        decision=executable_decision(queue[0],self.admin,feature_flags={"social_publish":True})
        self.assertTrue(decision["allowed"])
        self.assertFalse(decision["executes_action"])

    def test_real_trade_stays_blocked_after_approval(self):
        task=new_task("Enviar ordem real",domain="trading",action="real_trade")
        queue=approve_task([task],task["task_id"],self.admin,feature_flags={"real_broker_execution":True})
        decision=executable_decision(queue[0],self.admin,feature_flags={"real_broker_execution":True})
        self.assertFalse(decision["allowed"])
        self.assertEqual(queue[0]["status"],"BLOCKED")
        self.assertTrue(queue[0]["approval"]["attempted"])
        self.assertFalse(queue[0]["approval"]["approved"])

    def test_positive_cost_requires_explicit_approval(self):
        task=new_task("Usar serviço pago",action="read",estimated_monthly_cost_usd=25)
        req=approval_requirement(task,self.admin)
        self.assertTrue(req["required"])
        queue=approve_task([task],task["task_id"],self.admin)
        self.assertTrue(queue[0]["approval"]["approved"])

    def test_queue_upsert_transition_and_summary(self):
        a=new_task("A",priority="P2",created_at="2026-09-23T20:00:00+00:00")
        b=new_task("B",priority="P0",created_at="2026-09-23T20:01:00+00:00")
        queue=upsert_task([],a)
        queue=upsert_task(queue,b)
        queue=transition_task(queue,b["task_id"],"WAITING_APPROVAL")
        summary=queue_summary(queue)
        self.assertEqual(summary["total"],2)
        self.assertEqual(summary["waiting_approval"],1)
        self.assertEqual(summary["next_actions"][0]["task_id"],b["task_id"])


if __name__=="__main__":
    unittest.main()
