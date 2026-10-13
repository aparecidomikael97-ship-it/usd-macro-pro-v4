"""AION A.42: compensation admission regressions against REAL Saga SQLite.

Every adversarial write below is explicitly TEST-ONLY local tampering. No real
provider, producer receipt, signed owner approval, adapter, network, or send.
The productive Outbox and Saga must reject before any new staged intent/effect.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_cumulative_authority_budget import CumulativeAuthorityBudget
from atlasquant_aion_execution_outbox import ExecutionOutbox
from atlasquant_aion_execution_saga import ExecutionSagaCoordinator
from atlasquant_aion_saga_sequence_policy import select_compensation_step

NOW = datetime(2026, 10, 13, 19, 0, tzinfo=timezone.utc)
SAGA = "a42-local-claims-not-proof"


class CompensationLocalForgeryDenialTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        scope = Scope("owner-a42", "tenant-a42", "workspace-a42")
        self.store = SQLiteChatStore(Path(self.tmp.name) / "chat.sqlite3")
        self.addCleanup(self.store.close)
        self.outbox = ExecutionOutbox(self.store, scope)
        self.budget = CumulativeAuthorityBudget(
            self.store, scope,
            authority_budget_ref="a42-budget",
            policy_version="a42-policy",
        )
        self.saga = ExecutionSagaCoordinator(
            self.store, scope, outbox=self.outbox,
            authority_budget=self.budget,
        )
        self.saga.create(saga_id=SAGA, created_at=NOW, steps=[
            {
                "step_key": key,
                "action": "create_crm_note",
                "payload": {"source": "TEST_ONLY"},
                "capability_class": "LOW_RISK",
                "risk_points": 1,
                "reversible": True,
                "compensation_action": "delete_crm_note",
                "compensation_payload": {"reason": "TEST_ONLY"},
                "compensation_risk_points": 1,
            }
            for key in ("one", "two")
        ])

    def _snapshot(self):
        saga = self.saga.get(SAGA)
        return {
            "saga": saga,
            "events": self.saga.db.execute(
                "SELECT COUNT(*) FROM aion_execution_saga_events WHERE saga_id=?",
                (SAGA,),
            ).fetchone()[0],
            "outbox_rows": self.saga.db.execute(
                "SELECT COUNT(*) FROM action_outbox",
            ).fetchone()[0],
            "effects": self.outbox.effect_count(),
            "authority_effects": self.budget.snapshot(
                SAGA, now=NOW,
            )["transaction_effects"],
        }

    def _assert_unchanged_on_denial(self, fn, expected):
        before = self._snapshot()
        with self.assertRaisesRegex(PermissionError, expected):
            fn()
        self.assertEqual(self._snapshot(), before)

    def _forge_prepare_claims(self):
        # Deliberately simulate tampered SQLite and fabricated "confirmed"
        # effect; neither the Outbox nor an external producer confirmed it.
        with self.saga.db:
            self.saga.db.execute(
                """UPDATE aion_execution_saga_steps
                   SET state='CONFIRMED',effect_ref='FAKE_EXTERNAL_EFFECT'
                   WHERE saga_id=? AND step_key='one'""", (SAGA,),
            )
            self.saga.db.execute(
                """UPDATE aion_execution_saga_steps
                   SET state='FAILED'
                   WHERE saga_id=? AND step_key='two'""", (SAGA,),
            )
            self.saga.db.execute(
                """UPDATE aion_execution_sagas
                   SET state='COMPENSATION_REQUIRED'
                   WHERE saga_id=?""", (SAGA,),
            )

    def _forge_compensating_claims(self, *, both=False):
        with self.saga.db:
            self.saga.db.execute(
                """UPDATE aion_execution_sagas
                   SET state='COMPENSATING',
                       compensation_approval_ref='FAKE_OWNER_APPROVAL',
                       compensation_reauth_ref='FAKE_OWNER_REAUTH'
                   WHERE saga_id=?""", (SAGA,),
            )
            self.saga.db.execute(
                """UPDATE aion_execution_saga_steps
                   SET state='COMPENSATION_PENDING',
                       effect_ref='FAKE_EXTERNAL_EFFECT'
                   WHERE saga_id=? AND step_key='one'""", (SAGA,),
            )
            self.saga.db.execute(
                """UPDATE aion_execution_saga_steps
                   SET state=CASE WHEN ? THEN 'COMPENSATION_PENDING' ELSE 'FAILED' END
                   WHERE saga_id=? AND step_key='two'""", (1 if both else 0, SAGA),
            )

    def test_01_forged_confirmed_and_unverified_owner_refs_cannot_prepare(self):
        self._forge_prepare_claims()
        self._assert_unchanged_on_denial(
            lambda: self.saga.prepare_compensation(
                SAGA, explicit_human_approval=True,
                approval_ref="LOCAL_APPROVAL_ONLY",
                reauth_ref="LOCAL_REAUTH_ONLY",
                now=NOW + timedelta(seconds=1),
            ),
            "INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED",
        )

    def test_02_forged_confirmed_cannot_prepare_even_with_different_refs(self):
        self._forge_prepare_claims()
        for ref in ("FAKE_OWNER", "APPROVED", "external-looking-ref"):
            with self.subTest(ref=ref):
                self._assert_unchanged_on_denial(
                    lambda ref=ref: self.saga.prepare_compensation(
                        SAGA, explicit_human_approval=True,
                        approval_ref=ref, reauth_ref=ref,
                        now=NOW,
                    ),
                    "INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED",
                )

    def test_03_false_or_truthy_nonboolean_owner_flag_never_approves(self):
        self._forge_prepare_claims()
        for claimed in (False, 1, "true", None):
            with self.subTest(claimed=claimed):
                before = self._snapshot()
                with self.assertRaisesRegex(ValueError, "explicit human approval"):
                    self.saga.prepare_compensation(
                        SAGA, explicit_human_approval=claimed,
                        approval_ref="owner-ref",
                        reauth_ref="reauth-ref",
                        now=NOW,
                    )
                self.assertEqual(self._snapshot(), before)

    def test_04_sql_forged_compensating_cannot_enqueue_rollback(self):
        self._forge_compensating_claims()
        self._assert_unchanged_on_denial(
            lambda: self.saga.enqueue_next_compensation(
                SAGA, valid_until=NOW + timedelta(minutes=5),
                created_at=NOW,
            ),
            "INDEPENDENT_PRODUCER_COMPENSATION_NOT_ENROLLED",
        )

    def test_05_multi_step_reverse_candidate_is_not_producer_proof(self):
        self._forge_compensating_claims(both=True)
        saga = self.saga.get(SAGA)
        idx = select_compensation_step(saga["state"], saga["steps"])
        self.assertEqual(saga["steps"][idx]["step_key"], "two")
        self._assert_unchanged_on_denial(
            lambda: self.saga.enqueue_next_compensation(
                SAGA, valid_until=NOW + timedelta(minutes=5),
                created_at=NOW,
            ),
            "INDEPENDENT_PRODUCER_COMPENSATION_NOT_ENROLLED",
        )

    def test_06_incomplete_local_owner_refs_still_never_enqueue(self):
        for approval, reauth in (("", ""), ("FAKE", ""), ("", "FAKE")):
            with self.subTest(approval=approval, reauth=reauth):
                self._forge_compensating_claims()
                with self.saga.db:
                    self.saga.db.execute(
                        """UPDATE aion_execution_sagas
                           SET compensation_approval_ref=?,
                               compensation_reauth_ref=?
                           WHERE saga_id=?""", (approval, reauth, SAGA),
                    )
                self._assert_unchanged_on_denial(
                    lambda: self.saga.enqueue_next_compensation(
                        SAGA, valid_until=NOW + timedelta(minutes=5),
                        created_at=NOW,
                    ),
                    "INDEPENDENT_PRODUCER_COMPENSATION_NOT_ENROLLED",
                )

    def test_07_simulation_like_local_effect_ref_cannot_admit_rollback(self):
        self._forge_compensating_claims()
        with self.saga.db:
            self.saga.db.execute(
                """UPDATE aion_execution_saga_steps
                   SET effect_ref='SIMULATED_ONLY_COMMITTED'
                   WHERE saga_id=? AND step_key='one'""", (SAGA,),
            )
        self._assert_unchanged_on_denial(
            lambda: self.saga.enqueue_next_compensation(
                SAGA, valid_until=NOW + timedelta(minutes=5),
                created_at=NOW,
            ),
            "INDEPENDENT_PRODUCER_COMPENSATION_NOT_ENROLLED",
        )

    def test_08_unprepared_saga_remains_ineligible_for_compensation(self):
        before = self._snapshot()
        with self.assertRaisesRegex(ValueError, "not eligible"):
            self.saga.prepare_compensation(
                SAGA, explicit_human_approval=True,
                approval_ref="FAKE", reauth_ref="FAKE",
                now=NOW,
            )
        with self.assertRaisesRegex(ValueError, "not in compensation mode"):
            self.saga.enqueue_next_compensation(
                SAGA, valid_until=NOW + timedelta(minutes=5),
                created_at=NOW,
            )
        self.assertEqual(self._snapshot(), before)


if __name__ == "__main__":
    unittest.main()
