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


NOW = datetime(2026, 10, 5, 10, 0, tzinfo=timezone.utc)


def policy(
    scope,
    *,
    allowed=True,
    policy_version="policy-v1",
    authorization_ref="approval-forward",
    reauthenticated=True,
    reauth_ref="",
):
    def check(_decision):
        return {
            "allowed": allowed,
            "actor_id": scope.owner_id,
            "tenant_id": scope.tenant_id,
            "workspace_id": scope.workspace_id,
            "policy_version": policy_version,
            "authorization_ref": authorization_ref,
            "reauthenticated": reauthenticated,
            "reauth_ref": reauth_ref,
        }
    return check


class FakeAdapter:
    def __init__(self, mode="confirmed"):
        self.mode = mode
        self.effects = {}
        self.send_calls = 0
        self.reconcile_calls = 0
        self._lost_once = False

    def send(self, decision, idempotency_key):
        self.send_calls += 1
        if self.mode == "reject":
            return {
                "accepted": False,
                "retryable": False,
                "reason": "synthetic rejection",
            }
        if self.mode == "retry":
            return {
                "accepted": False,
                "retryable": True,
                "reason": "synthetic retry",
            }
        effect = self.effects.setdefault(
            idempotency_key,
            "EFF-" + idempotency_key[:20].upper(),
        )
        if self.mode == "lose-after-effect" and not self._lost_once:
            self._lost_once = True
            raise TimeoutError("synthetic lost response")
        if self.mode == "sent":
            return {
                "accepted": True,
                "confirmed": False,
                "effect_ref": effect,
            }
        return {
            "accepted": True,
            "confirmed": True,
            "effect_ref": effect,
        }

    def reconcile(self, idempotency_key, decision):
        self.reconcile_calls += 1
        if idempotency_key in self.effects:
            return {
                "found": True,
                "confirmed": True,
                "effect_ref": self.effects[idempotency_key],
            }
        return {
            "found": False,
            "authoritative_absence": True,
        }


class ExecutionSagaTests(unittest.TestCase):
    def setUp(self):
        self.scope = Scope("mikael", "tenant-a", "workspace-a")

    def _components(self, raw, **budget_limits):
        store = SQLiteChatStore(Path(raw) / "chat.sqlite3")
        outbox = ExecutionOutbox(store, self.scope)
        budget = CumulativeAuthorityBudget(
            store,
            self.scope,
            authority_budget_ref="budget-1",
            policy_version="policy-v1",
            **budget_limits,
        )
        saga = ExecutionSagaCoordinator(
            store,
            self.scope,
            outbox=outbox,
            authority_budget=budget,
        )
        return store, outbox, budget, saga

    def _steps(self, *, irreversible_first=False, three=False):
        rows = [
            {
                "step_key": "one",
                "action": "create_crm_note",
                "payload": {"client": "c1", "note": "prepared"},
                "capability_class": "LOW_RISK",
                "risk_points": 1,
                "reversible": not irreversible_first,
                "compensation_action": "" if irreversible_first else "delete_crm_note",
                "compensation_payload": {"reason": "saga rollback"},
                "compensation_risk_points": 1,
            },
            {
                "step_key": "two",
                "action": "send_followup",
                "payload": {"client": "c1", "template": "followup"},
                "capability_class": "LOW_RISK",
                "risk_points": 1,
                "reversible": True,
                "compensation_action": "retract_followup",
                "compensation_payload": {"reason": "saga rollback"},
                "compensation_risk_points": 1,
            },
        ]
        if three:
            rows.append({
                "step_key": "three",
                "action": "create_calendar_hold",
                "payload": {"client": "c1"},
                "capability_class": "LOW_RISK",
                "risk_points": 1,
                "reversible": True,
                "compensation_action": "delete_calendar_hold",
                "compensation_payload": {"reason": "saga rollback"},
                "compensation_risk_points": 1,
            })
        return rows

    def _create(self, saga, *, saga_id="saga-1", steps=None):
        return saga.create(
            saga_id=saga_id,
            steps=steps or self._steps(),
            created_at=NOW,
        )

    def _enqueue_forward(self, saga, *, saga_id="saga-1", offset=0):
        return saga.enqueue_next(
            saga_id,
            authorization_ref="approval-forward",
            valid_until=NOW + timedelta(minutes=5),
            created_at=NOW + timedelta(seconds=offset),
        )

    def _dispatch_claimed(
        self,
        outbox,
        budget,
        adapter,
        *,
        worker="worker-1",
        offset=1,
        approval_ref="approval-forward",
        reauth_ref="",
    ):
        when = NOW + timedelta(seconds=offset)
        claimed = outbox.claim_next(worker, now=when, lease_seconds=60)
        self.assertIsNotNone(claimed)
        result = outbox.dispatch_claimed(
            claimed["idempotency_key"],
            worker_id=worker,
            authorize=policy(
                self.scope,
                authorization_ref=approval_ref,
                reauthenticated=True,
                reauth_ref=reauth_ref,
            ),
            adapter=adapter,
            cumulative_authority_guard=lambda d: budget.guard(d, now=when),
            now=when,
        )
        return result

    def _fixture_mark_confirmed_only_after_simulated_external_positive_review(
        self, outbox, key, *, allow_uncertain_send=False,
    ):
        """LOCAL SQL test fixture only. NOT a receipt, verifier or host permission.

        It models a hypothetical pre-reviewed terminal effect solely to exercise
        Saga's state-machine transitions; no producer or external trust exists.
        """
        observed = outbox.get(key)
        self.assertEqual(observed["state"], "UNCERTAIN")
        if allow_uncertain_send:
            self.assertTrue(
                observed["last_error"].startswith("SEND_RESULT_UNKNOWN:"),
                "only simulated lost-response fixtures may bypass positive claim status",
            )
        else:
            self.assertEqual(
                observed["last_error"], "ADAPTER_POSITIVE_EFFECT_UNVERIFIED",
            )
        effect_ref = "SIMULATED-NOT-TRUSTED-" + key[:24]
        with outbox.db:
            changed = outbox.db.execute(
                """UPDATE action_outbox
                   SET state='CONFIRMED',effect_ref=?,confirmed_at=?,
                       lease_owner='',lease_until='',last_error=''
                   WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?
                     AND state='UNCERTAIN'
                     AND NOT EXISTS (
                         SELECT 1 FROM action_effects e
                         WHERE e.idempotency_key=action_outbox.idempotency_key
                     )""",
                (
                    effect_ref, NOW.isoformat(), key,
                    self.scope.owner_id, self.scope.tenant_id, self.scope.workspace_id,
                ),
            )
            self.assertEqual(changed.rowcount, 1)
            outbox.db.execute(
                """INSERT INTO action_effects(
                    idempotency_key,owner,tenant,workspace,effect_ref,confirmed_at,data
                ) VALUES (?,?,?,?,?,?,?)""",
                (
                    key, self.scope.owner_id, self.scope.tenant_id,
                    self.scope.workspace_id, effect_ref, NOW.isoformat(), "{}",
                ),
            )
        self.assertEqual(outbox.get(key)["state"], "CONFIRMED")
        return outbox.get(key)

    def _fixture_dispatch_after_simulated_external_positive_review(
        self, outbox, budget, adapter, **kwargs,
    ):
        """Test-only Saga state-machine fixture, no productive approval or receipt."""
        result = self._dispatch_claimed(outbox, budget, adapter, **kwargs)
        self.assertEqual(result["dispatch_state"], "UNCERTAIN_PROOF_REQUIRED")
        return self._fixture_mark_confirmed_only_after_simulated_external_positive_review(
            outbox, result["idempotency_key"],
        )

    def _fixture_mark_failed_only_after_simulated_external_no_effect_review(self, outbox, key):
        """Synthetic test arrangement, NOT a production receipt or recovery API."""
        self.assertEqual(outbox.get(key)["state"], "UNCERTAIN")
        with outbox.db:
            changed = outbox.db.execute(
                """UPDATE action_outbox
                   SET state='FAILED',last_error='TEST_FIXTURE_EXTERNAL_NO_EFFECT_ASSUMED'
                   WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?
                     AND state='UNCERTAIN'""",
                (key, self.scope.owner_id, self.scope.tenant_id, self.scope.workspace_id),
            )
            self.assertEqual(changed.rowcount, 1)

    def test_all_forward_steps_confirm_in_order_and_complete(self):
        with tempfile.TemporaryDirectory() as raw:
            store, outbox, budget, saga = self._components(raw)
            self._create(saga)

            first = self._enqueue_forward(saga, offset=0)
            self.assertEqual(first["saga"]["steps"][0]["state"], "ENQUEUED")
            result = self._fixture_dispatch_after_simulated_external_positive_review(outbox, budget, FakeAdapter(), offset=1)
            self.assertEqual(result["state"], "CONFIRMED")
            synced = saga.sync_forward_outcome("saga-1", "one", now=NOW + timedelta(seconds=1))
            self.assertEqual(synced["state"], "RUNNING")

            self._enqueue_forward(saga, offset=2)
            result = self._fixture_dispatch_after_simulated_external_positive_review(outbox, budget, FakeAdapter(), offset=3)
            self.assertEqual(result["state"], "CONFIRMED")
            synced = saga.sync_forward_outcome("saga-1", "two", now=NOW + timedelta(seconds=3))
            self.assertEqual(synced["state"], "COMPLETED")
            self.assertEqual(
                [row["state"] for row in synced["saga"]["steps"]],
                ["CONFIRMED", "CONFIRMED"],
            )
            self.assertEqual(budget.snapshot("saga-1", now=NOW + timedelta(seconds=4))["transaction_effects"], 2)
            self.assertEqual(saga.integrity_report("saga-1")["state"], "MATCH")
            store.close()

    def test_second_step_failure_requires_explicit_compensation_then_compensates(self):
        with tempfile.TemporaryDirectory() as raw:
            store, outbox, budget, saga = self._components(raw)
            self._create(saga)

            self._enqueue_forward(saga)
            self._fixture_dispatch_after_simulated_external_positive_review(outbox, budget, FakeAdapter(), offset=1)
            saga.sync_forward_outcome("saga-1", "one", now=NOW + timedelta(seconds=1))

            self._enqueue_forward(saga, offset=2)
            failed = self._dispatch_claimed(outbox, budget, FakeAdapter("reject"), offset=3)
            self.assertEqual(failed["state"], "UNCERTAIN")
            unverified = saga.sync_forward_outcome("saga-1", "two", now=NOW + timedelta(seconds=3))
            self.assertEqual(unverified["state"], "RECONCILIATION_REQUIRED")
            with self.assertRaisesRegex(ValueError, "not eligible"):
                saga.prepare_compensation(
                    "saga-1", explicit_human_approval=True,
                    approval_ref="approval-comp", reauth_ref="reauth-comp",
                    now=NOW + timedelta(seconds=4),
                )
            # Simulate an EXTERNAL no-effect determination solely to preserve
            # coverage of the compensation engine. Not an admissible runtime proof.
            self._fixture_mark_failed_only_after_simulated_external_no_effect_review(
                outbox, failed["idempotency_key"],
            )
            synced = saga.sync_forward_outcome("saga-1", "two", now=NOW + timedelta(seconds=3))
            self.assertEqual(synced["state"], "COMPENSATION_REQUIRED")

            with self.assertRaisesRegex(ValueError, "explicit human approval"):
                saga.prepare_compensation(
                    "saga-1",
                    explicit_human_approval=False,
                    approval_ref="approval-comp",
                    reauth_ref="reauth-comp",
                    now=NOW + timedelta(seconds=4),
                )

            prepared = saga.prepare_compensation(
                "saga-1",
                explicit_human_approval=True,
                approval_ref="approval-comp",
                reauth_ref="reauth-comp",
                now=NOW + timedelta(seconds=4),
            )
            self.assertEqual(prepared["state"], "COMPENSATING")
            self.assertFalse(prepared["automatic_compensation"])

            queued = saga.enqueue_next_compensation(
                "saga-1",
                valid_until=NOW + timedelta(minutes=5),
                created_at=NOW + timedelta(seconds=5),
            )
            self.assertEqual(queued["saga"]["steps"][0]["state"], "COMPENSATION_ENQUEUED")
            result = self._fixture_dispatch_after_simulated_external_positive_review(
                outbox,
                budget,
                FakeAdapter(),
                offset=6,
                approval_ref="approval-comp",
                reauth_ref="reauth-comp",
            )
            self.assertEqual(result["state"], "CONFIRMED")
            final = saga.sync_compensation_outcome(
                "saga-1",
                "one",
                now=NOW + timedelta(seconds=6),
            )
            self.assertEqual(final["state"], "COMPENSATED")
            self.assertEqual(final["saga"]["steps"][0]["state"], "COMPENSATED")
            self.assertEqual(budget.snapshot("saga-1", now=NOW + timedelta(seconds=7))["transaction_effects"], 2)
            store.close()

    def test_three_step_failure_compensates_confirmed_effects_in_reverse_order(self):
        with tempfile.TemporaryDirectory() as raw:
            store, outbox, budget, saga = self._components(
                raw,
                max_transaction_effects=6,
                max_transaction_risk_points=10,
            )
            self._create(saga, steps=self._steps(three=True))
            for index, key in enumerate(("one", "two"), start=1):
                self._enqueue_forward(saga, offset=index * 2)
                self._fixture_dispatch_after_simulated_external_positive_review(outbox, budget, FakeAdapter(), offset=index * 2 + 1)
                saga.sync_forward_outcome(
                    "saga-1",
                    key,
                    now=NOW + timedelta(seconds=index * 2 + 1),
                )

            self._enqueue_forward(saga, offset=6)
            unknown = self._dispatch_claimed(outbox, budget, FakeAdapter("reject"), offset=7)
            self.assertEqual(unknown["state"], "UNCERTAIN")
            blocked = saga.sync_forward_outcome("saga-1", "three", now=NOW + timedelta(seconds=7))
            self.assertEqual(blocked["state"], "RECONCILIATION_REQUIRED")
            self._fixture_mark_failed_only_after_simulated_external_no_effect_review(
                outbox, unknown["idempotency_key"],
            )
            out = saga.sync_forward_outcome("saga-1", "three", now=NOW + timedelta(seconds=7))
            self.assertEqual(out["state"], "COMPENSATION_REQUIRED")

            saga.prepare_compensation(
                "saga-1",
                explicit_human_approval=True,
                approval_ref="approval-comp",
                reauth_ref="reauth-comp",
                now=NOW + timedelta(seconds=8),
            )
            first_comp = saga.enqueue_next_compensation(
                "saga-1",
                valid_until=NOW + timedelta(minutes=5),
                created_at=NOW + timedelta(seconds=9),
            )
            active = next(
                row for row in first_comp["saga"]["steps"]
                if row["state"] == "COMPENSATION_ENQUEUED"
            )
            self.assertEqual(active["step_key"], "two")

            self._fixture_dispatch_after_simulated_external_positive_review(
                outbox,
                budget,
                FakeAdapter(),
                offset=10,
                approval_ref="approval-comp",
                reauth_ref="reauth-comp",
            )
            saga.sync_compensation_outcome("saga-1", "two", now=NOW + timedelta(seconds=10))

            second_comp = saga.enqueue_next_compensation(
                "saga-1",
                valid_until=NOW + timedelta(minutes=5),
                created_at=NOW + timedelta(seconds=11),
            )
            active = next(
                row for row in second_comp["saga"]["steps"]
                if row["state"] == "COMPENSATION_ENQUEUED"
            )
            self.assertEqual(active["step_key"], "one")
            store.close()

    def test_irreversible_confirmed_effect_escalates_manual_and_never_prepares_rollback(self):
        with tempfile.TemporaryDirectory() as raw:
            store, outbox, budget, saga = self._components(raw)
            self._create(saga, steps=self._steps(irreversible_first=True))

            self._enqueue_forward(saga)
            self._fixture_dispatch_after_simulated_external_positive_review(outbox, budget, FakeAdapter(), offset=1)
            saga.sync_forward_outcome("saga-1", "one", now=NOW + timedelta(seconds=1))

            self._enqueue_forward(saga, offset=2)
            unknown = self._dispatch_claimed(outbox, budget, FakeAdapter("reject"), offset=3)
            self.assertEqual(unknown["state"], "UNCERTAIN")
            blocked = saga.sync_forward_outcome("saga-1", "two", now=NOW + timedelta(seconds=3))
            self.assertEqual(blocked["state"], "RECONCILIATION_REQUIRED")
            self._fixture_mark_failed_only_after_simulated_external_no_effect_review(
                outbox, unknown["idempotency_key"],
            )
            out = saga.sync_forward_outcome("saga-1", "two", now=NOW + timedelta(seconds=3))
            self.assertEqual(out["state"], "MANUAL_INTERVENTION_REQUIRED")
            self.assertEqual(out["saga"]["steps"][0]["state"], "MANUAL_REQUIRED")
            with self.assertRaisesRegex(ValueError, "not eligible"):
                saga.prepare_compensation(
                    "saga-1",
                    explicit_human_approval=True,
                    approval_ref="approval-comp",
                    reauth_ref="reauth-comp",
                    now=NOW + timedelta(seconds=4),
                )
            store.close()

    def test_uncertain_forward_effect_freezes_saga_until_reconciliation(self):
        with tempfile.TemporaryDirectory() as raw:
            store, outbox, budget, saga = self._components(raw)
            self._create(saga)
            self._enqueue_forward(saga)

            adapter = FakeAdapter("lose-after-effect")
            result = self._dispatch_claimed(outbox, budget, adapter, offset=1)
            self.assertEqual(result["state"], "UNCERTAIN")
            synced = saga.sync_forward_outcome("saga-1", "one", now=NOW + timedelta(seconds=1))
            self.assertEqual(synced["state"], "RECONCILIATION_REQUIRED")
            with self.assertRaisesRegex(ValueError, "state does not allow"):
                self._enqueue_forward(saga, offset=2)
            with self.assertRaisesRegex(ValueError, "not eligible"):
                saga.prepare_compensation(
                    "saga-1",
                    explicit_human_approval=True,
                    approval_ref="approval-comp",
                    reauth_ref="reauth-comp",
                    now=NOW + timedelta(seconds=2),
                )

            reconciled = outbox.reconcile(
                result["idempotency_key"],
                adapter=adapter,
                authorize=policy(self.scope),
                now=NOW + timedelta(seconds=3),
            )
            self.assertEqual(reconciled["state"], "UNCERTAIN")
            self.assertEqual(
                reconciled["reconcile_state"], "INDEPENDENT_POSITIVE_PROOF_REQUIRED",
            )
            self.assertEqual(
                saga.sync_forward_outcome(
                    "saga-1", "one", now=NOW + timedelta(seconds=3),
                )["state"],
                "RECONCILIATION_REQUIRED",
            )
            # Saga state-machine only: explicit simulated review, never a
            # productive receipt or an automatic admission from an adapter.
            self._fixture_mark_confirmed_only_after_simulated_external_positive_review(
                outbox, result["idempotency_key"], allow_uncertain_send=True,
            )
            synced = saga.sync_forward_outcome("saga-1", "one", now=NOW + timedelta(seconds=3))
            self.assertEqual(synced["state"], "RUNNING")
            store.close()

    def test_uncertain_compensation_freezes_remaining_rollback_until_reconciled(self):
        with tempfile.TemporaryDirectory() as raw:
            store, outbox, budget, saga = self._components(
                raw,
                max_transaction_effects=6,
                max_transaction_risk_points=10,
            )
            self._create(saga, steps=self._steps(three=True))
            for index, key in enumerate(("one", "two"), start=1):
                self._enqueue_forward(saga, offset=index * 2)
                self._fixture_dispatch_after_simulated_external_positive_review(outbox, budget, FakeAdapter(), offset=index * 2 + 1)
                saga.sync_forward_outcome("saga-1", key, now=NOW + timedelta(seconds=index * 2 + 1))
            self._enqueue_forward(saga, offset=6)
            unresolved = self._dispatch_claimed(outbox, budget, FakeAdapter("reject"), offset=7)
            self.assertEqual(unresolved["state"], "UNCERTAIN")
            self.assertEqual(
                saga.sync_forward_outcome("saga-1", "three", now=NOW + timedelta(seconds=7))["state"],
                "RECONCILIATION_REQUIRED",
            )
            self._fixture_mark_failed_only_after_simulated_external_no_effect_review(
                outbox, unresolved["idempotency_key"],
            )
            self.assertEqual(
                saga.sync_forward_outcome("saga-1", "three", now=NOW + timedelta(seconds=7))["state"],
                "COMPENSATION_REQUIRED",
            )
            saga.prepare_compensation(
                "saga-1",
                explicit_human_approval=True,
                approval_ref="approval-comp",
                reauth_ref="reauth-comp",
                now=NOW + timedelta(seconds=8),
            )
            saga.enqueue_next_compensation(
                "saga-1",
                valid_until=NOW + timedelta(minutes=5),
                created_at=NOW + timedelta(seconds=9),
            )
            adapter = FakeAdapter("lose-after-effect")
            result = self._dispatch_claimed(
                outbox,
                budget,
                adapter,
                offset=10,
                approval_ref="approval-comp",
                reauth_ref="reauth-comp",
            )
            self.assertEqual(result["state"], "UNCERTAIN")
            synced = saga.sync_compensation_outcome("saga-1", "two", now=NOW + timedelta(seconds=10))
            self.assertEqual(synced["state"], "RECONCILIATION_REQUIRED")
            with self.assertRaisesRegex(ValueError, "not in compensation mode"):
                saga.enqueue_next_compensation(
                    "saga-1",
                    valid_until=NOW + timedelta(minutes=5),
                    created_at=NOW + timedelta(seconds=11),
                )

            reconciled = outbox.reconcile(
                result["idempotency_key"],
                adapter=adapter,
                authorize=policy(
                    self.scope,
                    authorization_ref="approval-comp",
                    reauth_ref="reauth-comp",
                ),
                now=NOW + timedelta(seconds=12),
            )
            self.assertEqual(reconciled["state"], "UNCERTAIN")
            self.assertEqual(
                reconciled["reconcile_state"], "INDEPENDENT_POSITIVE_PROOF_REQUIRED",
            )
            self.assertEqual(
                saga.sync_compensation_outcome(
                    "saga-1", "two", now=NOW + timedelta(seconds=12),
                )["state"],
                "RECONCILIATION_REQUIRED",
            )
            self._fixture_mark_confirmed_only_after_simulated_external_positive_review(
                outbox, result["idempotency_key"], allow_uncertain_send=True,
            )
            synced = saga.sync_compensation_outcome("saga-1", "two", now=NOW + timedelta(seconds=12))
            self.assertEqual(synced["state"], "COMPENSATING")
            next_comp = saga.enqueue_next_compensation(
                "saga-1",
                valid_until=NOW + timedelta(minutes=5),
                created_at=NOW + timedelta(seconds=13),
            )
            active = next(
                row for row in next_comp["saga"]["steps"]
                if row["state"] == "COMPENSATION_ENQUEUED"
            )
            self.assertEqual(active["step_key"], "one")
            store.close()

    def test_compensation_unverified_failure_requires_external_review_before_manual_terminal(self):
        with tempfile.TemporaryDirectory() as raw:
            store, outbox, budget, saga = self._components(raw)
            self._create(saga)
            self._enqueue_forward(saga)
            self._fixture_dispatch_after_simulated_external_positive_review(outbox, budget, FakeAdapter(), offset=1)
            saga.sync_forward_outcome("saga-1", "one", now=NOW + timedelta(seconds=1))
            self._enqueue_forward(saga, offset=2)
            unknown = self._dispatch_claimed(outbox, budget, FakeAdapter("reject"), offset=3)
            self.assertEqual(unknown["state"], "UNCERTAIN")
            self.assertEqual(
                saga.sync_forward_outcome("saga-1", "two", now=NOW + timedelta(seconds=3))["state"],
                "RECONCILIATION_REQUIRED",
            )
            self._fixture_mark_failed_only_after_simulated_external_no_effect_review(
                outbox, unknown["idempotency_key"],
            )
            self.assertEqual(
                saga.sync_forward_outcome("saga-1", "two", now=NOW + timedelta(seconds=3))["state"],
                "COMPENSATION_REQUIRED",
            )
            saga.prepare_compensation(
                "saga-1",
                explicit_human_approval=True,
                approval_ref="approval-comp",
                reauth_ref="reauth-comp",
                now=NOW + timedelta(seconds=4),
            )
            saga.enqueue_next_compensation(
                "saga-1",
                valid_until=NOW + timedelta(minutes=5),
                created_at=NOW + timedelta(seconds=5),
            )
            unresolved_comp = self._dispatch_claimed(
                outbox,
                budget,
                FakeAdapter("reject"),
                offset=6,
                approval_ref="approval-comp",
                reauth_ref="reauth-comp",
            )
            self.assertEqual(unresolved_comp["state"], "UNCERTAIN")
            in_review = saga.sync_compensation_outcome(
                "saga-1", "one", now=NOW + timedelta(seconds=6),
            )
            self.assertEqual(in_review["state"], "RECONCILIATION_REQUIRED")
            self._fixture_mark_failed_only_after_simulated_external_no_effect_review(
                outbox, unresolved_comp["idempotency_key"],
            )
            final = saga.sync_compensation_outcome("saga-1", "one", now=NOW + timedelta(seconds=6))
            self.assertEqual(final["state"], "MANUAL_INTERVENTION_REQUIRED")
            self.assertEqual(final["saga"]["steps"][0]["state"], "COMPENSATION_FAILED")
            store.close()

    def test_budget_guard_blocks_external_send_before_adapter(self):
        with tempfile.TemporaryDirectory() as raw:
            store, outbox, budget, saga = self._components(
                raw,
                max_transaction_effects=4,
                max_transaction_risk_points=3,
            )
            steps = [self._steps()[0]]
            steps[0]["risk_points"] = 2
            self._create(saga, steps=steps)

            budget.record_confirmed(
                {
                    "owner_id": self.scope.owner_id,
                    "tenant_id": self.scope.tenant_id,
                    "workspace_id": self.scope.workspace_id,
                    "transaction_id": "saga-1",
                    "authority_budget_ref": "budget-1",
                    "policy_version": "policy-v1",
                    "action": "prior-approved-action",
                    "capability_class": "LOW_RISK",
                    "risk_points": 2,
                },
                idempotency_key="prior-idem",
                effect_ref="prior-effect",
                confirmed_at=NOW - timedelta(seconds=1),
            )
            self._enqueue_forward(saga)
            adapter = FakeAdapter()
            result = self._dispatch_claimed(outbox, budget, adapter, offset=1)
            self.assertEqual(result["state"], "BLOCKED_REAPPROVAL")
            self.assertIn("CUMULATIVE_AUTHORITY_BUDGET_EXCEEDED", result["last_error"])
            self.assertEqual(adapter.send_calls, 0)
            synced = saga.sync_forward_outcome("saga-1", "one", now=NOW + timedelta(seconds=1))
            self.assertEqual(synced["state"], "FAILED")
            store.close()

    def test_scope_window_budget_blocks_second_transaction_even_with_separate_approval(self):
        with tempfile.TemporaryDirectory() as raw:
            store, outbox, budget, saga = self._components(
                raw,
                max_window_effects=1,
                max_transaction_effects=4,
            )
            one_step = [self._steps()[0]]
            self._create(saga, saga_id="saga-a", steps=one_step)
            saga.enqueue_next(
                "saga-a",
                authorization_ref="approval-forward",
                valid_until=NOW + timedelta(minutes=5),
                created_at=NOW,
            )
            self._fixture_dispatch_after_simulated_external_positive_review(outbox, budget, FakeAdapter(), offset=1)
            saga.sync_forward_outcome("saga-a", "one", now=NOW + timedelta(seconds=1))

            self._create(saga, saga_id="saga-b", steps=one_step)
            saga.enqueue_next(
                "saga-b",
                authorization_ref="approval-forward",
                valid_until=NOW + timedelta(minutes=5),
                created_at=NOW + timedelta(seconds=2),
            )
            adapter = FakeAdapter()
            result = self._dispatch_claimed(outbox, budget, adapter, offset=3)
            self.assertEqual(result["state"], "BLOCKED_REAPPROVAL")
            self.assertIn("WINDOW_EFFECT_LIMIT", result["last_error"])
            self.assertEqual(adapter.send_calls, 0)
            store.close()

    def test_tagged_outbox_intent_cannot_dispatch_if_guard_is_omitted(self):
        with tempfile.TemporaryDirectory() as raw:
            store, outbox, budget, saga = self._components(raw)
            item = outbox.enqueue(
                intent_ref="tagged-1",
                action="send_email",
                payload={"x": 1},
                aggregate_key="tagged",
                policy_version="policy-v1",
                authorization_ref="approval-forward",
                valid_until=NOW + timedelta(minutes=5),
                created_at=NOW,
                transaction_id="tx-tagged",
                authority_budget_ref="budget-1",
                risk_points=1,
                capability_class="LOW_RISK",
            )
            claimed = outbox.claim_next("worker-1", now=NOW, lease_seconds=60)
            self.assertEqual(claimed["idempotency_key"], item["idempotency_key"])
            adapter = FakeAdapter()
            result = outbox.dispatch_claimed(
                item["idempotency_key"],
                worker_id="worker-1",
                authorize=policy(self.scope),
                adapter=adapter,
                now=NOW + timedelta(seconds=1),
            )
            self.assertEqual(result["state"], "BLOCKED_REAPPROVAL")
            self.assertEqual(result["last_error"], "CUMULATIVE_AUTHORITY_GUARD_REQUIRED")
            self.assertEqual(adapter.send_calls, 0)
            store.close()

    def test_event_chain_detects_tamper(self):
        with tempfile.TemporaryDirectory() as raw:
            store, outbox, budget, saga = self._components(raw)
            self._create(saga)
            self.assertEqual(saga.integrity_report("saga-1")["state"], "MATCH")
            store.db.execute(
                """UPDATE aion_execution_saga_events
                   SET state='REWRITTEN' WHERE saga_id='saga-1' AND sequence=1"""
            )
            self.assertEqual(saga.integrity_report("saga-1")["state"], "MISMATCH")
            store.close()

    def test_saga_survives_process_style_store_reopen(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "chat.sqlite3"
            store = SQLiteChatStore(path)
            outbox = ExecutionOutbox(store, self.scope)
            budget = CumulativeAuthorityBudget(
                store,
                self.scope,
                authority_budget_ref="budget-1",
                policy_version="policy-v1",
            )
            saga = ExecutionSagaCoordinator(
                store,
                self.scope,
                outbox=outbox,
                authority_budget=budget,
            )
            self._create(saga)
            self._enqueue_forward(saga)
            store.close()

            reopened = SQLiteChatStore(path)
            outbox2 = ExecutionOutbox(reopened, self.scope)
            budget2 = CumulativeAuthorityBudget(
                reopened,
                self.scope,
                authority_budget_ref="budget-1",
                policy_version="policy-v1",
            )
            saga2 = ExecutionSagaCoordinator(
                reopened,
                self.scope,
                outbox=outbox2,
                authority_budget=budget2,
            )
            recovered = saga2.get("saga-1")
            self.assertEqual(recovered["state"], "RUNNING")
            self.assertEqual(recovered["steps"][0]["state"], "ENQUEUED")
            self.assertEqual(saga2.integrity_report("saga-1")["state"], "MATCH")
            reopened.close()

    def test_saga_plan_rejects_critical_capability_and_over_budget_shape(self):
        with tempfile.TemporaryDirectory() as raw:
            store, outbox, budget, saga = self._components(
                raw,
                max_transaction_effects=4,
                max_transaction_risk_points=2,
            )
            critical = self._steps()[:1]
            critical[0]["capability_class"] = "CRITICAL"
            with self.assertRaisesRegex(ValueError, "critical capability"):
                self._create(saga, steps=critical)

            over = self._steps()
            over[0]["risk_points"] = 2
            over[1]["risk_points"] = 2
            with self.assertRaisesRegex(ValueError, "forward risk"):
                saga.create(saga_id="saga-over", steps=over, created_at=NOW)
            store.close()


if __name__ == "__main__":
    unittest.main()
