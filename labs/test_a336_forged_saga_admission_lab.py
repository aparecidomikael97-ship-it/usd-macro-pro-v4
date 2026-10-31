"""A336 LAB — local Saga SQLite projections are not producer or owner proof.

All rows and claims are synthetic in temporary SQLite stores. No real adapter,
network, provider, HUMAN_OWNER ceremony, compensation, or external effect.
"""
from contextlib import contextmanager
from copy import deepcopy
from datetime import timedelta
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

import test_atlasquant_aion_execution_saga as fixture_module


SAGA_ID = "saga-1"
NOW = fixture_module.NOW


class A336ForgedSagaAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture_module.ExecutionSagaTests()
        self.fixture.setUp()

    @contextmanager
    def lab(self):
        with TemporaryDirectory() as directory:
            store, outbox, budget, saga = self.fixture._components(directory)
            try:
                self.fixture._create(saga)
                yield outbox, budget, saga
            finally:
                store.close()

    def _snapshot(self, outbox, budget, saga):
        return {
            "saga": deepcopy(saga.get(SAGA_ID)),
            "saga_events": saga.db.execute(
                "SELECT COUNT(*) FROM aion_execution_saga_events WHERE saga_id=?",
                (SAGA_ID,),
            ).fetchone()[0],
            "outbox_rows": outbox.db.execute(
                "SELECT COUNT(*) FROM action_outbox"
            ).fetchone()[0],
            "authority_effects": budget.snapshot(
                SAGA_ID, now=NOW
            )["transaction_effects"],
        }

    def _deny_without_mutation(self, outbox, budget, saga, callback, reason):
        before = self._snapshot(outbox, budget, saga)
        with patch.object(
            outbox, "enqueue", side_effect=AssertionError("A336_OUTBOX_MUST_NOT_ENQUEUE")
        ) as enqueue, patch.object(
            budget, "record_confirmed",
            side_effect=AssertionError("A336_BUDGET_MUST_NOT_RECORD"),
        ) as record:
            with self.assertRaisesRegex(PermissionError, reason):
                callback()
            enqueue.assert_not_called()
            record.assert_not_called()
        self.assertEqual(self._snapshot(outbox, budget, saga), before)

    def _forge_forward_confirmation(self, saga):
        with saga.db:
            saga.db.execute(
                "UPDATE aion_execution_sagas SET state='RUNNING' WHERE saga_id=?",
                (SAGA_ID,),
            )
            saga.db.execute(
                """UPDATE aion_execution_saga_steps
                   SET state='CONFIRMED',effect_ref='LOCAL_NOT_PRODUCER_RECEIPT'
                   WHERE saga_id=? AND step_key='one'""",
                (SAGA_ID,),
            )

    def _forge_compensation_required(self, saga):
        with saga.db:
            saga.db.execute(
                "UPDATE aion_execution_sagas SET state='COMPENSATION_REQUIRED' WHERE saga_id=?",
                (SAGA_ID,),
            )
            saga.db.execute(
                """UPDATE aion_execution_saga_steps
                   SET state='CONFIRMED',effect_ref='LOCAL_NOT_PRODUCER_RECEIPT'
                   WHERE saga_id=? AND step_key='one'""",
                (SAGA_ID,),
            )
            saga.db.execute(
                """UPDATE aion_execution_saga_steps SET state='FAILED'
                   WHERE saga_id=? AND step_key='two'""",
                (SAGA_ID,),
            )

    def _forge_compensating(self, saga, *, both=False, approval="LOCAL_OWNER", reauth="LOCAL_REAUTH"):
        with saga.db:
            saga.db.execute(
                """UPDATE aion_execution_sagas
                   SET state='COMPENSATING',
                       compensation_approval_ref=?,
                       compensation_reauth_ref=?
                   WHERE saga_id=?""",
                (approval, reauth, SAGA_ID),
            )
            saga.db.execute(
                """UPDATE aion_execution_saga_steps
                   SET state='COMPENSATION_PENDING',effect_ref='LOCAL_NOT_PRODUCER_RECEIPT'
                   WHERE saga_id=? AND step_key='one'""",
                (SAGA_ID,),
            )
            saga.db.execute(
                """UPDATE aion_execution_saga_steps SET state=?
                   WHERE saga_id=? AND step_key='two'""",
                ("COMPENSATION_PENDING" if both else "FAILED", SAGA_ID),
            )

    def test_01_unforged_first_forward_step_stages_only_a_pending_intent(self):
        with self.lab() as (outbox, budget, saga):
            result = self.fixture._enqueue_forward(saga)
            self.assertEqual(result["saga"]["steps"][0]["state"], "ENQUEUED")
            self.assertEqual(self._snapshot(outbox, budget, saga)["outbox_rows"], 1)
            self.assertEqual(budget.snapshot(SAGA_ID, now=NOW)["transaction_effects"], 0)

    def test_02_forged_prior_confirmed_cannot_stage_second_forward_step(self):
        with self.lab() as (outbox, budget, saga):
            self._forge_forward_confirmation(saga)
            self._deny_without_mutation(
                outbox, budget, saga,
                lambda: saga.enqueue_next(
                    SAGA_ID,
                    authorization_ref="LOCAL_APPROVAL",
                    valid_until=NOW + timedelta(minutes=5),
                    created_at=NOW,
                ),
                "INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED",
            )

    def test_03_forged_confirmed_and_local_owner_refs_cannot_prepare_compensation(self):
        with self.lab() as (outbox, budget, saga):
            self._forge_compensation_required(saga)
            self._deny_without_mutation(
                outbox, budget, saga,
                lambda: saga.prepare_compensation(
                    SAGA_ID,
                    explicit_human_approval=True,
                    approval_ref="LOCAL_OWNER_APPROVAL",
                    reauth_ref="LOCAL_OWNER_REAUTH",
                    now=NOW,
                ),
                "INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED",
            )

    def test_04_various_claimed_owner_refs_do_not_become_independent_proof(self):
        with self.lab() as (outbox, budget, saga):
            self._forge_compensation_required(saga)
            for owner_ref in ("APPROVED", "HUMAN_OWNER", "external-looking-reference"):
                with self.subTest(owner_ref=owner_ref):
                    self._deny_without_mutation(
                        outbox, budget, saga,
                        lambda owner_ref=owner_ref: saga.prepare_compensation(
                            SAGA_ID,
                            explicit_human_approval=True,
                            approval_ref=owner_ref,
                            reauth_ref=owner_ref,
                            now=NOW,
                        ),
                        "INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED",
                    )

    def test_05_non_boolean_or_false_owner_flag_remains_rejected(self):
        with self.lab() as (outbox, budget, saga):
            self._forge_compensation_required(saga)
            for approval in (False, 1, "true", None):
                with self.subTest(approval=approval):
                    before = self._snapshot(outbox, budget, saga)
                    with self.assertRaisesRegex(ValueError, "explicit human approval"):
                        saga.prepare_compensation(
                            SAGA_ID, explicit_human_approval=approval,
                            approval_ref="LOCAL", reauth_ref="LOCAL", now=NOW,
                        )
                    self.assertEqual(self._snapshot(outbox, budget, saga), before)

    def test_06_forged_compensating_and_pending_cannot_enqueue_rollback(self):
        with self.lab() as (outbox, budget, saga):
            self._forge_compensating(saga)
            self._deny_without_mutation(
                outbox, budget, saga,
                lambda: saga.enqueue_next_compensation(
                    SAGA_ID, valid_until=NOW + timedelta(minutes=5), created_at=NOW,
                ),
                "INDEPENDENT_PRODUCER_COMPENSATION_NOT_ENROLLED",
            )

    def test_07_reverse_order_candidate_cannot_be_used_as_producer_proof(self):
        with self.lab() as (outbox, budget, saga):
            self._forge_compensating(saga, both=True)
            self.assertEqual(
                [step["state"] for step in saga.get(SAGA_ID)["steps"]],
                ["COMPENSATION_PENDING", "COMPENSATION_PENDING"],
            )
            self._deny_without_mutation(
                outbox, budget, saga,
                lambda: saga.enqueue_next_compensation(
                    SAGA_ID, valid_until=NOW + timedelta(minutes=5), created_at=NOW,
                ),
                "INDEPENDENT_PRODUCER_COMPENSATION_NOT_ENROLLED",
            )

    def test_08_empty_or_partial_owner_claims_do_not_unlock_compensation(self):
        with self.lab() as (outbox, budget, saga):
            for approval, reauth in (("", ""), ("LOCAL", ""), ("", "LOCAL")):
                with self.subTest(approval=approval, reauth=reauth):
                    self._forge_compensating(saga, approval=approval, reauth=reauth)
                    self._deny_without_mutation(
                        outbox, budget, saga,
                        lambda: saga.enqueue_next_compensation(
                            SAGA_ID, valid_until=NOW + timedelta(minutes=5), created_at=NOW,
                        ),
                        "INDEPENDENT_PRODUCER_COMPENSATION_NOT_ENROLLED",
                    )

    def test_09_invalid_compensation_state_still_fails_without_any_write(self):
        with self.lab() as (outbox, budget, saga):
            before = self._snapshot(outbox, budget, saga)
            with self.assertRaisesRegex(ValueError, "not in compensation mode"):
                saga.enqueue_next_compensation(
                    SAGA_ID, valid_until=NOW + timedelta(minutes=5), created_at=NOW,
                )
            self.assertEqual(self._snapshot(outbox, budget, saga), before)


if __name__ == "__main__":
    unittest.main()
