"""AION P0 LAB: prove internal Saga helpers cannot read or alter another scope.

Use genuine SQLiteChatStore/CumulativeAuthorityBudget/ExecutionOutbox/Saga
instances sharing a throwaway database. Access the private helper deliberately
as an adversarial in-process call. This is NOT a network exploit or credential
boundary; it hardens internal calls against scope-confused code.
No Worker, external adapter, message send, merge or effect registration.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_cumulative_authority_budget import CumulativeAuthorityBudget
from atlasquant_aion_execution_outbox import ExecutionOutbox
from atlasquant_aion_execution_saga import ExecutionSagaCoordinator

NOW = datetime(2026, 10, 21, 16, 0, tzinfo=timezone.utc)
ALPHA = Scope("alpha-owner", "shared-tenant", "shared-workspace")
VARIANTS = (
    ("owner", Scope("beta-owner", "shared-tenant", "shared-workspace")),
    ("tenant", Scope("alpha-owner", "beta-tenant", "shared-workspace")),
    ("workspace", Scope("alpha-owner", "shared-tenant", "beta-workspace")),
)


class AIONP0SagaScopedInternalHelpersLab(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix="aion-saga-scoped-internals-")
        self.addCleanup(tmp.cleanup)
        self.store=SQLiteChatStore(Path(tmp.name)/"isolation.sqlite3")
        self.addCleanup(self.store.close)
        self.alpha=self._coordinator(ALPHA)

    def _coordinator(self, scope):
        outbox=ExecutionOutbox(self.store,scope)
        budget=CumulativeAuthorityBudget(
            self.store,scope,authority_budget_ref="budget-lab-only",
            policy_version="lab-policy",
        )
        return ExecutionSagaCoordinator(
            self.store,scope,outbox=outbox,authority_budget=budget,
        )

    def _make(self, coord, sid, payload_marker):
        return coord.create(saga_id=sid,created_at=NOW,steps=[{
            "step_key": "one",
            "action": "prepare_lab_note",
            "payload": {"marker": payload_marker, "lab_only": True},
            "capability_class": "LOW_RISK",
            "risk_points": 1,
            "reversible": False,
            "compensation_payload": {},
        }])

    def _setup_other(self, variant):
        foreign=self._coordinator(variant)
        self._make(self.alpha,"saga-alpha","alpha-secret")
        self._make(foreign,"saga-foreign","foreign-secret")
        return foreign

    def test_01_private_step_reader_denies_other_owner(self):
        self._setup_other(VARIANTS[0][1])
        self.assertEqual(self.alpha._step_rows("saga-foreign"),[])

    def test_02_private_step_reader_denies_other_tenant(self):
        self._setup_other(VARIANTS[1][1])
        self.assertEqual(self.alpha._step_rows("saga-foreign"),[])

    def test_03_private_step_reader_denies_other_workspace(self):
        self._setup_other(VARIANTS[2][1])
        self.assertEqual(self.alpha._step_rows("saga-foreign"),[])

    def test_04_direct_event_append_denies_other_owner(self):
        self._check_denied_event(VARIANTS[0][1])

    def test_05_direct_event_append_denies_other_tenant(self):
        self._check_denied_event(VARIANTS[1][1])

    def test_06_direct_event_append_denies_other_workspace(self):
        self._check_denied_event(VARIANTS[2][1])

    def _check_denied_event(self, variant):
        foreign=self._setup_other(variant)
        before=tuple(self.store.db.execute(
            "SELECT sequence,event_hash FROM aion_execution_saga_events "
            "WHERE saga_id='saga-foreign' ORDER BY sequence"
        ).fetchall())
        with self.assertRaisesRegex(LookupError,"saga unavailable"):
            self.alpha._append_event(
                "saga-foreign",event_type="SCOPE_CONFUSION",
                state="PLANNED",created_at=NOW,
            )
        after=tuple(self.store.db.execute(
            "SELECT sequence,event_hash FROM aion_execution_saga_events "
            "WHERE saga_id='saga-foreign' ORDER BY sequence"
        ).fetchall())
        self.assertEqual(after,before)
        self.assertEqual(foreign.integrity_report("saga-foreign")["state"],"MATCH")

    def test_07_own_scoped_steps_remain_visible(self):
        self._make(self.alpha,"saga-alpha","alpha-secret")
        rows=self.alpha._step_rows("saga-alpha")
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["step_key"],"one")

    def test_08_own_scoped_event_append_remains_valid(self):
        self._make(self.alpha,"saga-alpha","alpha-secret")
        before=self.alpha.integrity_report("saga-alpha")
        self.assertEqual(before["state"],"MATCH")
        self.alpha._append_event(
            "saga-alpha",event_type="LOCAL_AUDIT_NOTE",
            state="PLANNED",created_at=NOW,
        )
        after=self.alpha.integrity_report("saga-alpha")
        self.assertEqual(after["state"],"MATCH")
        self.assertEqual(after["events"],before["events"]+1)
        self.assertFalse(after["independent_witness_verified"])

    def test_09_public_get_foreign_saga_already_denies(self):
        self._setup_other(VARIANTS[0][1])
        with self.assertRaises(LookupError):
            self.alpha.get("saga-foreign")

    def test_10_other_tenant_still_reads_its_own_steps(self):
        foreign=self._setup_other(VARIANTS[1][1])
        self.assertEqual(len(foreign._step_rows("saga-foreign")),1)
        view=foreign.get("saga-foreign")
        self.assertEqual(view["steps"][0]["payload"]["marker"],"foreign-secret")

    def test_11_unknown_saga_id_does_not_create_an_event(self):
        self._make(self.alpha,"saga-alpha","alpha-secret")
        before=self.store.db.execute(
            "SELECT COUNT(*) FROM aion_execution_saga_events"
        ).fetchone()[0]
        with self.assertRaisesRegex(LookupError,"saga unavailable"):
            self.alpha._append_event(
                "saga-unknown",event_type="FAKE",
                state="PLANNED",created_at=NOW,
            )
        self.assertEqual(before,self.store.db.execute(
            "SELECT COUNT(*) FROM aion_execution_saga_events"
        ).fetchone()[0])

    def test_12_no_external_effect_registered_by_scope_tests(self):
        self._setup_other(VARIANTS[2][1])
        self.assertEqual(self.alpha.outbox.effect_count(),0)
        self.assertEqual(self.store.db.execute(
            "SELECT COUNT(*) FROM action_effects"
        ).fetchone()[0],0)


if __name__=="__main__":
    unittest.main()
