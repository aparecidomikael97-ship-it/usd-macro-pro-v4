import unittest

from atlasquant_aion_developer_engine import (
    MAX_CORRECTION_ATTEMPTS,
    definition_of_done,
    new_development_workflow,
    record_adversarial_review,
    record_phase,
    record_test_attempt,
)


class AionDeveloperEngineTests(unittest.TestCase):
    def workflow(self):
        return new_development_workflow(
            "Adicionar contrato seguro",
            branch="cursor/aion-test",
            baseline_ref="abc123",
            requested_by="admin",
            components=["core"],
            dependencies=["guardian"],
        )

    def pass_phase(self, workflow, phase, actor):
        return record_phase(
            workflow,
            phase,
            state="PASS",
            actor=actor,
            summary=f"{phase} concluído",
            evidence_refs=[f"evidence:{phase.lower()}"],
        )

    def test_workflow_is_sandboxed_and_never_releases_automatically(self):
        workflow = self.workflow()
        self.assertTrue(workflow["sandbox_only"])
        self.assertFalse(workflow["automatic_merge"])
        self.assertFalse(workflow["automatic_deploy"])
        self.assertFalse(workflow["production_change_allowed"])
        self.assertFalse(workflow["real_trading_enabled"])

    def test_phases_must_pass_in_order(self):
        with self.assertRaises(ValueError):
            self.pass_phase(self.workflow(), "IMPLEMENT", "builder")

    def test_non_pass_phase_cannot_start_out_of_order(self):
        workflow=self.workflow()
        for state in ("RUNNING","WAITING_HUMAN","BLOCKED","FAIL"):
            with self.assertRaises(ValueError):
                record_phase(
                    workflow,"IMPLEMENT",state=state,actor="builder",
                    summary="fora de ordem",evidence_refs=["evidence:1"],
                )

    def test_forbidden_production_branch_families_are_rejected(self):
        for branch in ("main","MAIN","main/hotfix","production/fix","refs/heads/prod","origin/main"):
            with self.assertRaises(ValueError):
                new_development_workflow(
                    "unsafe",branch=branch,baseline_ref="abc",
                    requested_by="admin",
                )

    def test_reviewer_and_critic_must_be_independent(self):
        workflow = self.pass_phase(self.workflow(), "PLAN", "architect")
        workflow = self.pass_phase(workflow, "IMPLEMENT", "builder")
        with self.assertRaises(ValueError):
            self.pass_phase(workflow, "REVIEW", "builder")
        with self.assertRaises(ValueError):
            record_adversarial_review(
                workflow,
                critic_actor="builder",
                findings=[],
                evidence_refs=["review"],
            )

        workflow = self.pass_phase(workflow, "TEST", "test-runner")
        workflow = self.pass_phase(workflow, "REVIEW", "Reviewer")
        with self.assertRaises(ValueError):
            record_adversarial_review(
                workflow,
                critic_actor=" reviewer ",
                findings=[],
                evidence_refs=["review:adv"],
            )
        with self.assertRaises(ValueError):
            record_adversarial_review(
                workflow,
                critic_actor="critic",
                findings=[],
                evidence_refs=[],
            )

    def test_auto_correction_has_hard_attempt_limit(self):
        workflow = self.workflow()
        for index in range(MAX_CORRECTION_ATTEMPTS):
            workflow = record_test_attempt(
                workflow,
                command_label="unit suite",
                state="FAIL",
                error_type="AssertionError",
                hypothesis=f"hypothesis {index}",
                evidence_refs=[f"log:{index}"],
            )
        self.assertEqual(workflow["status"], "BLOCKED")
        self.assertEqual(workflow["blocker"], "AUTO_CORRECTION_LIMIT_REACHED")
        unchanged = record_test_attempt(workflow, command_label="again", state="PASS")
        self.assertEqual(len(unchanged["test_attempts"]), MAX_CORRECTION_ATTEMPTS)
        self.assertEqual(unchanged["status"], "BLOCKED")

    def test_test_attempt_never_confirms_root_cause_from_free_text(self):
        workflow=record_test_attempt(
            self.workflow(),
            command_label="unit suite",
            state="FAIL",
            error_type="AssertionError",
            hypothesis="maybe cache",
            cause="definitely cache",
            evidence_refs=["log:1"],
        )
        attempt=workflow["test_attempts"][-1]
        self.assertEqual(attempt["cause"],"definitely cache")
        self.assertEqual(attempt["cause_truth"],"UNKNOWN")
        self.assertEqual(attempt["cause_source"],"UNVERIFIED_TEST_ATTEMPT")

    def test_logs_and_error_metadata_are_redacted(self):
        workflow = record_test_attempt(
            self.workflow(),
            command_label="request api_key=super-secret-value",
            state="FAIL",
            error_type="Bearer abcdefghijklmnopqrstuvwxyz",
            hypothesis="token=another-secret-value",
        )
        rendered = str(workflow["test_attempts"])
        self.assertIn("[REDACTED]", rendered)
        self.assertNotIn("super-secret-value", rendered)
        self.assertNotIn("another-secret-value", rendered)

    def test_earlier_phase_cannot_change_after_downstream_progress(self):
        workflow=self.pass_phase(self.workflow(),"PLAN","architect")
        workflow=self.pass_phase(workflow,"IMPLEMENT","builder-a")
        workflow=record_phase(
            workflow,"TEST",state="RUNNING",actor="test-runner",
            summary="running",evidence_refs=[],
        )
        with self.assertRaises(ValueError):
            record_phase(
                workflow,"IMPLEMENT",state="PASS",actor="builder-b",
                summary="IMPLEMENT concluído",evidence_refs=["evidence:implement"],
            )

    def test_high_adversarial_finding_blocks_definition_of_done(self):
        workflow = self.pass_phase(self.workflow(), "PLAN", "architect")
        workflow = self.pass_phase(workflow, "IMPLEMENT", "builder")
        workflow = record_adversarial_review(
            workflow,
            critic_actor="critic",
            findings=[{"check": "secret_exposure", "severity": "CRITICAL", "finding": "leak", "resolved": False}],
            evidence_refs=["review:1"],
        )
        self.assertEqual(workflow["status"], "BLOCKED")
        done = definition_of_done(workflow, rollback_plan="git revert <sha>", documentation_refs=["docs/aion"])
        self.assertEqual(done["status"], "INCOMPLETE")

    def test_definition_of_done_requires_tests_review_rollback_and_docs(self):
        workflow = self.pass_phase(self.workflow(), "PLAN", "architect")
        workflow = self.pass_phase(workflow, "IMPLEMENT", "builder")
        workflow = record_test_attempt(
            workflow, command_label="unit suite", state="PASS", evidence_refs=["test:log"],
        )
        workflow = self.pass_phase(workflow, "TEST", "test-runner")
        workflow = self.pass_phase(workflow, "REVIEW", "reviewer")
        workflow = record_adversarial_review(
            workflow,
            critic_actor="critic",
            findings=[{"check": "edge_cases", "severity": "LOW", "finding": "covered", "resolved": True}],
            evidence_refs=["review:adversarial"],
        )
        done = definition_of_done(
            workflow,
            rollback_plan="git revert <commit>",
            documentation_refs=["docs/aion/ARCHITECTURE.md"],
        )
        self.assertEqual(done["status"], "HUMAN_RELEASE_REVIEW")
        self.assertTrue(all(done["definition_of_done"].values()))
        self.assertFalse(done["automatic_merge"])
        self.assertFalse(done["automatic_deploy"])


if __name__ == "__main__":
    unittest.main()
