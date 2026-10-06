from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_chaos_campaign import (
    DOMAINS,
    chaos_campaign_contract,
    evaluate_chaos_campaign,
)
from atlasquant_aion_cumulative_authority_budget import CumulativeAuthorityBudget
from atlasquant_aion_durable_task_repository import (
    DurableTaskRepository,
    SimulatedTaskStoreCrash,
)
from atlasquant_aion_durable_tasks import new_durable_task, pause_durable_task
from atlasquant_aion_execution_outbox import ExecutionOutbox
from atlasquant_aion_execution_saga import ExecutionSagaCoordinator
from atlasquant_aion_memory import checkpoint_integrity_report, default_checkpoint
from atlasquant_aion_resilience import circuit_breaker, safe_mode_posture, watchdog
from atlasquant_aion_verification_ledger import verify_ledger_integrity

NOW = datetime(2026, 10, 5, 13, 30, tzinfo=timezone.utc)
CHECKED = "2026-10-05T13:31:00Z"
SCOPE_MAP = {"owner_id": "mikael", "tenant_id": "tenant-a", "workspace_id": "workspace-a"}


def policy():
    return {
        "state": "VERIFIED",
        "policy_id": "chaos-v1",
        "revision": 1,
        **SCOPE_MAP,
        "required_domains": list(DOMAINS),
        "max_observation_age_seconds": 3600,
        "max_recovery_seconds_by_domain": {domain: 900 for domain in DOMAINS},
    }


def observation(domain, *, failure_mode, containment, recovery, seconds=10, refs=None):
    return {
        **SCOPE_MAP,
        "domain": domain,
        "failure_observed": True,
        "containment_verified": True,
        "recovery_verified": True,
        "production_mutation": False,
        "external_action_executed": False,
        "automatic_authority": False,
        "failure_mode": failure_mode,
        "containment": containment,
        "recovery": recovery,
        "observed_at": "2026-10-05T13:30:00Z",
        "recovery_seconds": seconds,
        "evidence_refs": refs or [f"chaos:{domain.lower()}:test"],
    }


def authorization(scope, *, allowed=True, authorization_ref="approval-1"):
    def check(_decision):
        return {
            "allowed": allowed,
            "actor_id": scope.owner_id,
            "tenant_id": scope.tenant_id,
            "workspace_id": scope.workspace_id,
            "policy_version": "policy-v1",
            "authorization_ref": authorization_ref,
            "reauthenticated": True,
            "reauth_ref": "reauth-1",
        }
    return check


class ChaosAdapter:
    def __init__(self, mode):
        self.mode = mode
        self.effects = {}
        self.send_calls = 0
        self.reconcile_calls = 0
        self._lost_once = False

    def send(self, decision, idempotency_key):
        self.send_calls += 1
        if self.mode == "reject":
            return {"accepted": False, "retryable": False, "reason": "synthetic tool failure"}
        if self.mode == "lose-before-effect" and not self._lost_once:
            self._lost_once = True
            raise TimeoutError("synthetic network timeout before effect")
        effect = self.effects.setdefault(idempotency_key, "EFF-" + idempotency_key[:20].upper())
        if self.mode == "lose-after-effect" and not self._lost_once:
            self._lost_once = True
            raise TimeoutError("synthetic queue response loss after effect")
        return {"accepted": True, "confirmed": True, "effect_ref": effect}

    def reconcile(self, idempotency_key, decision):
        self.reconcile_calls += 1
        if idempotency_key in self.effects:
            return {
                "found": True,
                "confirmed": True,
                "effect_ref": self.effects[idempotency_key],
            }
        return {"found": False, "authoritative_absence": True}


class AionChaosCampaignTests(unittest.TestCase):
    def setUp(self):
        self.scope = Scope("mikael", "tenant-a", "workspace-a")

    def _outbox(self, root):
        store = SQLiteChatStore(Path(root) / "chat.sqlite3")
        return store, ExecutionOutbox(store, self.scope)

    def _enqueue(self, outbox, ref):
        return outbox.enqueue(
            intent_ref=ref,
            action="send_email",
            payload={"to": "synthetic@example.com", "template": "chaos"},
            aggregate_key=ref,
            policy_version="policy-v1",
            authorization_ref="approval-1",
            created_at=NOW,
            valid_until=NOW + timedelta(minutes=5),
        )

    def test_provider_fault_opens_circuit_and_degrades_to_read_only(self):
        breaker = circuit_breaker(
            "provider",
            previous_state="CLOSED",
            consecutive_failures=3,
            error_rate_pct=70,
        )
        safe = safe_mode_posture(open_circuits=1)
        self.assertEqual(breaker["state"], "OPEN")
        self.assertFalse(breaker["sensitive_calls_allowed"])
        self.assertEqual(safe["mode"], "DEGRADED_READ_ONLY")
        self.assertFalse(safe["external_side_effects_allowed"])

    def test_network_timeout_never_blind_resends_without_authoritative_absence(self):
        with tempfile.TemporaryDirectory() as raw:
            store, outbox = self._outbox(raw)
            item = self._enqueue(outbox, "network-1")
            claimed = outbox.claim_next("worker-1", now=NOW, lease_seconds=60)
            adapter = ChaosAdapter("lose-before-effect")
            result = outbox.dispatch_claimed(
                claimed["idempotency_key"],
                worker_id="worker-1",
                authorize=authorization(self.scope),
                adapter=adapter,
                now=NOW + timedelta(seconds=1),
            )
            self.assertEqual(result["state"], "UNCERTAIN")
            self.assertEqual(adapter.send_calls, 1)
            reconciled = outbox.reconcile(
                item["idempotency_key"],
                adapter=adapter,
                authorize=authorization(self.scope),
                now=NOW + timedelta(seconds=2),
            )
            self.assertEqual(reconciled["state"], "RETRY")
            self.assertEqual(adapter.send_calls, 1)
            self.assertEqual(outbox.effect_count(), 0)
            store.close()

    def test_store_crash_before_commit_rolls_back_and_reopens_cleanly(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "chat.sqlite3"

            def crash(stage, context):
                if stage == "BEFORE_CAS_COMMIT":
                    raise SimulatedTaskStoreCrash(stage)

            store = SQLiteChatStore(path)
            repo = DurableTaskRepository(store, self.scope, fault_injector=crash)
            task = new_durable_task(
                "Chaos CAS",
                objective="prove rollback",
                created_at="2026-10-05T13:00:00+00:00",
                source="CHAOS_TEST",
            )
            repo.create(task)
            candidate = pause_durable_task(
                task,
                expected_revision=1,
                changed_at="2026-10-05T13:01:00+00:00",
            )
            with self.assertRaises(SimulatedTaskStoreCrash):
                repo.compare_and_swap(candidate, expected_revision=1)
            store.close()

            reopened = SQLiteChatStore(path)
            recovered = DurableTaskRepository(reopened, self.scope)
            self.assertEqual(recovered.load(task["durable_task_id"])["revision"], 1)
            self.assertEqual(recovered.integrity_report()["state"], "MATCH")
            reopened.close()

    def test_queue_lost_response_reconciles_exactly_once_without_resend(self):
        with tempfile.TemporaryDirectory() as raw:
            store, outbox = self._outbox(raw)
            item = self._enqueue(outbox, "queue-1")
            claimed = outbox.claim_next("worker-1", now=NOW, lease_seconds=60)
            adapter = ChaosAdapter("lose-after-effect")
            result = outbox.dispatch_claimed(
                claimed["idempotency_key"],
                worker_id="worker-1",
                authorize=authorization(self.scope),
                adapter=adapter,
                now=NOW + timedelta(seconds=1),
            )
            self.assertEqual(result["state"], "UNCERTAIN")
            reconciled = outbox.reconcile(
                item["idempotency_key"],
                adapter=adapter,
                authorize=authorization(self.scope),
                now=NOW + timedelta(seconds=2),
            )
            self.assertEqual(reconciled["state"], "CONFIRMED")
            self.assertEqual(adapter.send_calls, 1)
            self.assertEqual(outbox.effect_count(), 1)
            store.close()

    def test_tool_failure_after_prior_effect_requires_manual_compensation_approval(self):
        with tempfile.TemporaryDirectory() as raw:
            store = SQLiteChatStore(Path(raw) / "chat.sqlite3")
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
            saga.create(
                saga_id="chaos-saga",
                created_at=NOW,
                steps=[
                    {
                        "step_key": "one",
                        "action": "create_note",
                        "payload": {"x": 1},
                        "capability_class": "LOW_RISK",
                        "risk_points": 1,
                        "reversible": True,
                        "compensation_action": "delete_note",
                        "compensation_payload": {"x": 1},
                        "compensation_risk_points": 1,
                    },
                    {
                        "step_key": "two",
                        "action": "send_followup",
                        "payload": {"x": 2},
                        "capability_class": "LOW_RISK",
                        "risk_points": 1,
                        "reversible": True,
                        "compensation_action": "retract_followup",
                        "compensation_payload": {"x": 2},
                        "compensation_risk_points": 1,
                    },
                ],
            )
            first = saga.enqueue_next(
                "chaos-saga",
                authorization_ref="approval-1",
                valid_until=NOW + timedelta(minutes=5),
                created_at=NOW,
            )
            claimed = outbox.claim_next("worker-1", now=NOW, lease_seconds=60)
            confirmed = outbox.dispatch_claimed(
                claimed["idempotency_key"],
                worker_id="worker-1",
                authorize=authorization(self.scope),
                adapter=ChaosAdapter("confirmed"),
                cumulative_authority_guard=lambda d: budget.guard(d, now=NOW),
                now=NOW + timedelta(seconds=1),
            )
            self.assertEqual(confirmed["state"], "CONFIRMED")
            saga.sync_forward_outcome("chaos-saga", "one", now=NOW + timedelta(seconds=1))

            saga.enqueue_next(
                "chaos-saga",
                authorization_ref="approval-1",
                valid_until=NOW + timedelta(minutes=5),
                created_at=NOW + timedelta(seconds=2),
            )
            claimed = outbox.claim_next("worker-1", now=NOW + timedelta(seconds=2), lease_seconds=60)
            failed = outbox.dispatch_claimed(
                claimed["idempotency_key"],
                worker_id="worker-1",
                authorize=authorization(self.scope),
                adapter=ChaosAdapter("reject"),
                cumulative_authority_guard=lambda d: budget.guard(d, now=NOW + timedelta(seconds=2)),
                now=NOW + timedelta(seconds=3),
            )
            self.assertEqual(failed["state"], "FAILED")
            synced = saga.sync_forward_outcome(
                "chaos-saga",
                "two",
                now=NOW + timedelta(seconds=3),
            )
            self.assertEqual(synced["state"], "COMPENSATION_REQUIRED")
            with self.assertRaisesRegex(ValueError, "explicit human approval"):
                saga.prepare_compensation(
                    "chaos-saga",
                    explicit_human_approval=False,
                    approval_ref="approval-comp",
                    reauth_ref="reauth-comp",
                    now=NOW + timedelta(seconds=4),
                )
            store.close()

    def test_agent_loop_isolates_without_automatic_kill(self):
        out = watchdog(
            "agent",
            heartbeat_age_seconds=1,
            repeated_action_count=5,
            loop_limit=5,
            unhandled_error_count=3,
            error_limit=3,
        )
        self.assertEqual(out["state"], "ISOLATE_RECOMMENDED")
        self.assertFalse(out["automatic_kill"])
        self.assertFalse(out["automatic_delete"])

    def test_state_corruption_breaks_checkpoint_and_ledger_integrity(self):
        cp = default_checkpoint()
        self.assertEqual(checkpoint_integrity_report(cp)["state"], "CONFIRMED")
        tampered = deepcopy(cp)
        tampered["verification_ledger"]["digest"] = "0" * 64
        self.assertEqual(
            verify_ledger_integrity(tampered["verification_ledger"])["state"],
            "MISMATCH",
        )
        self.assertEqual(checkpoint_integrity_report(tampered)["state"], "MISMATCH")

    def test_complete_campaign_requires_all_domains_and_remains_non_authoritative(self):
        observations = [
            observation("PROVIDER", failure_mode="provider outage", containment="circuit OPEN", recovery="safe mode read-only"),
            observation("NETWORK", failure_mode="timeout before effect", containment="UNCERTAIN", recovery="authoritative absence -> RETRY"),
            observation("STORE", failure_mode="crash before CAS commit", containment="transaction rollback", recovery="reopen revision unchanged"),
            observation("QUEUE", failure_mode="response lost after effect", containment="UNCERTAIN", recovery="reconcile -> CONFIRMED exactly once"),
            observation("TOOL", failure_mode="second tool rejected", containment="COMPENSATION_REQUIRED", recovery="manual approval required"),
            observation("AGENT", failure_mode="loop/error storm", containment="ISOLATE_RECOMMENDED", recovery="read-only diagnosis"),
            observation("STATE_CORRUPTION", failure_mode="ledger digest tamper", containment="integrity MISMATCH", recovery="blocked for review"),
        ]
        out = evaluate_chaos_campaign(
            trusted_scope=SCOPE_MAP,
            policy=policy(),
            observations=observations,
            checked_at=CHECKED,
        )
        self.assertEqual(out["state"], "READY_FOR_HUMAN_REVIEW")
        self.assertEqual(set(out["covered_domains"]), set(DOMAINS))
        self.assertFalse(out["production_fault_injection_authorized"])
        self.assertFalse(out["production_recovery_authorized"])
        self.assertFalse(out["automatic_retry_authorized"])
        self.assertFalse(out["automatic_compensation_authorized"])
        self.assertFalse(out["executes_action"])

    def test_missing_domain_cross_scope_or_false_safety_claim_blocks(self):
        observations = [
            observation(domain, failure_mode="x", containment="y", recovery="z")
            for domain in DOMAINS
            if domain != "NETWORK"
        ]
        observations[0]["tenant_id"] = "tenant-b"
        observations[1]["production_mutation"] = True
        out = evaluate_chaos_campaign(
            trusted_scope=SCOPE_MAP,
            policy=policy(),
            observations=observations,
            checked_at=CHECKED,
        )
        self.assertEqual(out["state"], "BLOCKED")
        joined = " ".join(out["blockers"])
        self.assertIn("DOMAIN_MISSING:NETWORK", joined)
        self.assertIn("OBSERVATION_SCOPE_MISMATCH", joined)
        self.assertIn("PRODUCTION_MUTATION_FORBIDDEN", joined)

    def test_campaign_contract_never_authorizes_faults_or_recovery(self):
        contract = chaos_campaign_contract()
        self.assertEqual(set(contract["required_domains"]), set(DOMAINS))
        self.assertFalse(contract["production_fault_injection_allowed"])
        self.assertFalse(contract["automatic_recovery_authority"])
        self.assertFalse(contract["automatic_compensation"])
        self.assertFalse(contract["executes_action"])


if __name__ == "__main__":
    unittest.main()
