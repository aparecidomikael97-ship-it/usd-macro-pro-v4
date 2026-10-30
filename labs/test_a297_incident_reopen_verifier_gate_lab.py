"""A297 LAB: no independent root, incident reopening and unknown ACK veto."""
import copy
import time
import unittest

from labs.a297_incident_reopen_verifier_gate_lab import (
    ACK_UNCERTAIN, INCIDENT_OPEN, PLAN_FIELDS, ROOT_ABSENT, SCHEMA,
    IsolatedIncidentAuthorityGate,
    probe_incident_reopening_cancels_stale_plan,
    probe_unknown_ack_and_restart,
)
from labs.a296_external_authority_evidence_contract_lab import (
    synthetic_forged_complete_pack,
)


class A297IncidentReopeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = probe_incident_reopening_cancels_stale_plan()

    def test_local_epoch_and_effect_do_not_create_external_authority(self):
        self.assertTrue(self.data["initial_local_epoch_never_authorized"])
        self.assertTrue(self.data["normal_effect_denied_without_external_root"])

    def test_one_incident_blocks_all_real_effects(self):
        self.assertTrue(self.data["first_incident_vetoed"])
        self.assertTrue(self.data["effect_denied_after_reopen"])

    def test_eight_plausible_fake_obligations_remain_no_go(self):
        self.assertTrue(self.data["complete_fake_evidence_rejected"])
        self.assertTrue(self.data["new_fake_evidence_still_denied"])

    def test_reopening_advances_generation_and_invalidates_prior_plan(self):
        self.assertTrue(self.data["incident_reopened_generation_advanced"])
        self.assertTrue(self.data["old_recovery_plan_stale"])
        self.assertGreaterEqual(self.data["journal_count"], 3)

    def test_lab_metadata_contains_no_p0_authority(self):
        self.assertTrue(self.data["hard_no_go"])
        self.assertFalse(self.data["can_authorize_real_effect"])
        self.assertFalse(self.data["owner_consent_authenticated"])
        self.assertFalse(self.data["durable_off_host_incident_journal"])
        self.assertEqual(self.data["p0_homologated"], 0)


class A297UnknownAcknowledgementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = probe_unknown_ack_and_restart()

    def test_uncertain_ack_requires_no_auto_resend(self):
        self.assertTrue(self.data["unknown_ack_denied"])
        self.assertTrue(self.data["recovery_veto_persists"])
        self.assertTrue(self.data["effect_blocked_before_reopen"])
        self.assertTrue(self.data["zero_auto_resend"])

    def test_incident_reopening_never_clears_uncertainty(self):
        self.assertTrue(self.data["incident_reopening_cannot_clear_uncertainty"])

    def test_fresh_same_host_process_has_no_real_authority(self):
        self.assertTrue(self.data["reset_instance_still_denies_production"])
        self.assertTrue(self.data["in_memory_journal_is_not_offhost_custody"])


class A297GateContractTests(unittest.TestCase):
    def setUp(self):
        self.gate = IsolatedIncidentAuthorityGate()

    def test_fresh_gate_is_locked_and_never_authorized(self):
        status = self.gate.status()
        self.assertEqual(status["state"], ROOT_ABSENT)
        self.assertEqual(status["incident_generation"], 0)
        self.assertEqual(status["incident_journal_entries"], 0)
        self.assertFalse(status["can_deploy"])
        self.assertFalse(status["can_start_worker"])
        self.assertFalse(status["can_authorize_real_effect"])
        self.assertEqual(status["decision"], "HARD_NO_GO")

    def test_initial_record_is_untrusted_not_an_activation(self):
        result = self.gate.record_lab_epoch("a" * 64)
        self.assertFalse(result["approved"])
        self.assertEqual(result["reason"], "UNTRUSTED_LOCAL_EPOCH_NOT_AUTHORITY")
        self.assertEqual(
            self.gate.record_lab_epoch("b" * 64)["reason"],
            "LOCAL_EPOCH_ALREADY_RECORDED",
        )
        self.assertEqual(self.gate.status()["historical_epoch_bound"], "a"*64)

    def test_reopened_event_replay_is_denied_without_new_generation(self):
        self.gate.reopen_incident(incident_id="incident-1", reason="first")
        self.assertEqual(self.gate.generation, 1)
        replay = self.gate.reopen_incident(
            incident_id="incident-1", reason="replay",
        )
        self.assertEqual(replay["reason"], "INCIDENT_EVENT_REPLAY")
        self.assertEqual(self.gate.generation, 1)
        self.assertEqual(self.gate.state, INCIDENT_OPEN)

    def test_no_incident_plan_is_not_a_recovery(self):
        plan = self.gate.make_plan()
        self.assertEqual(frozenset(plan), PLAN_FIELDS)
        self.assertEqual(
            self.gate.review_recovery(plan)["reason"],
            "NO_REOPENED_INCIDENT_CONTEXT",
        )

    def test_plan_missing_field_or_wrong_schema_is_rejected(self):
        self.gate.reopen_incident(incident_id="incident-2", reason="test")
        plan = self.gate.make_plan()
        bad = {k: v for k, v in plan.items() if k != "nonce"}
        self.assertEqual(
            self.gate.review_recovery(bad)["reason"],
            "RECOVERY_PLAN_FIELDS_INVALID",
        )
        self.assertEqual(
            self.gate.review_recovery(dict(plan, schema="fake"))["reason"],
            "RECOVERY_PLAN_SCHEMA_INVALID",
        )

    def test_bad_bindings_expiry_and_wrong_generation_are_denied(self):
        self.gate.reopen_incident(incident_id="incident-3", reason="test")
        plan = self.gate.make_plan()
        variations = [
            ({"incident_generation": 2}, "STALE_OR_WRONG_INCIDENT_GENERATION"),
            ({"incident_id": "elsewhere"}, "STALE_OR_WRONG_INCIDENT_GENERATION"),
            ({"requested_epoch": "bad"}, "RECOVERY_EPOCH_INVALID"),
            ({"intent_digest": "bad"}, "RECOVERY_INTENT_BINDING_INVALID"),
            ({"nonce": "bad"}, "RECOVERY_NONCE_INVALID"),
            ({"expires_at": 1}, "RECOVERY_EXPIRED_OR_UNBOUNDED"),
            (
                {"expires_at": int(time.time()) + 3600},
                "RECOVERY_EXPIRED_OR_UNBOUNDED",
            ),
        ]
        for mutation, expected in variations:
            with self.subTest(mutation=mutation):
                response = self.gate.review_recovery(
                    dict(plan, **mutation)
                )
                self.assertEqual(response["reason"], expected)
                self.assertFalse(response["can_authorize_real_effect"])

    def test_bad_manifest_is_rejected_even_with_valid_plan(self):
        self.gate.reopen_incident(incident_id="incident-4", reason="test")
        plan = self.gate.make_plan()
        bad = copy.deepcopy(plan)
        bad["evidence_pack"]["claims"] = []
        response = self.gate.review_recovery(bad)
        self.assertEqual(
            response["reason"], "EXTERNAL_EVIDENCE_CONTRACT_INVALID"
        )
        self.assertTrue(response["evidence_issues"])

    def test_fake_complete_evidence_never_resumes(self):
        self.gate.reopen_incident(incident_id="incident-5", reason="test")
        plan = self.gate.make_plan(
            evidence_pack=synthetic_forged_complete_pack()
        )
        response = self.gate.review_recovery(plan)
        self.assertEqual(
            response["reason"], "STRUCTURAL_EVIDENCE_NOT_EXTERNAL_AUTHORITY"
        )
        self.assertEqual(response["structural_obligations"], 8)
        self.assertEqual(response["authenticated_obligations"], 0)

    def test_unknown_ack_is_sticky_even_through_another_reopen(self):
        self.gate.reopen_incident(incident_id="incident-6", reason="test")
        self.gate.mark_effect_ack_uncertain(intent_id="synthetic-intent")
        self.assertEqual(self.gate.state, ACK_UNCERTAIN)
        self.assertEqual(
            self.gate.attempt_effect(intent_digest="f"*64)["reason"],
            "ACK_OUTCOME_UNKNOWN_ZERO_AUTO_RESEND",
        )
        self.gate.reopen_incident(
            incident_id="incident-7", reason="reopened"
        )
        self.assertEqual(
            self.gate.review_recovery(self.gate.make_plan())["reason"],
            "ACK_OUTCOME_UNKNOWN_ZERO_AUTO_RESEND",
        )

    def test_bad_incident_and_ack_identifiers_rejected(self):
        for bad in ("", " "*3, 123, "x"*129):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    self.gate.reopen_incident(
                        incident_id=bad, reason="test"
                    )
                with self.assertRaises(ValueError):
                    self.gate.mark_effect_ack_uncertain(intent_id=bad)

    def test_real_effect_cannot_be_authorized_even_with_fake_plan(self):
        self.gate.reopen_incident(incident_id="incident-8", reason="test")
        plan = self.gate.make_plan()
        result = self.gate.attempt_effect(
            intent_digest="d"*64, plan=plan,
        )
        self.assertEqual(result["decision"], "HARD_NO_GO")
        self.assertFalse(result["approved"])
        self.assertFalse(result["can_authorize_real_effect"])
        self.assertTrue(result["zero_auto_resend"])


if __name__ == "__main__":
    unittest.main()
