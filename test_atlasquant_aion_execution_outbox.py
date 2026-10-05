from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import (
    MAX_AUTHORITY_TTL_SECONDS,
    ExecutionOutbox,
)


NOW = datetime(2026, 10, 5, 5, 0, tzinfo=timezone.utc)


def policy(
    scope,
    *,
    allowed=True,
    policy_version="policy-v1",
    authorization_ref="approval-1",
    reauthenticated=True,
    reauth_ref="reauth-1",
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


class FakeIdempotentAdapter:
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
                "reason": "rejected",
            }
        if self.mode == "retryable-reject":
            return {
                "accepted": False,
                "retryable": True,
                "reason": "temporary",
            }
        if self.mode == "lose-before-effect" and not self._lost_once:
            self._lost_once = True
            raise TimeoutError("response lost before effect")

        effect = self.effects.setdefault(
            idempotency_key,
            "EFF-" + idempotency_key[:20].upper(),
        )
        if self.mode == "lose-after-effect" and not self._lost_once:
            self._lost_once = True
            raise TimeoutError("response lost after effect")
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


class ExecutionOutboxTests(unittest.TestCase):
    def setUp(self):
        self.scope = Scope("mikael", "tenant-a", "workspace-a")

    def _outbox(self, root):
        store = SQLiteChatStore(Path(root) / "chat.sqlite3")
        return store, ExecutionOutbox(store, self.scope)

    def _enqueue(self, outbox, *, ref="intent-1", payload=None, aggregate="client-1",
                 valid_until=None, requires_reauth=False, reauth_ref=""):
        return outbox.enqueue(
            intent_ref=ref,
            action="send_email",
            payload=payload or {"to": "client@example.com", "template": "followup"},
            aggregate_key=aggregate,
            policy_version="policy-v1",
            authorization_ref="approval-1",
            created_at=NOW,
            valid_until=valid_until or NOW + timedelta(minutes=5),
            requires_reauth=requires_reauth,
            reauth_ref=reauth_ref,
        )

    def test_enqueue_is_transactional_idempotent_and_collision_safe(self):
        with tempfile.TemporaryDirectory() as raw:
            store, outbox = self._outbox(raw)
            first = self._enqueue(outbox)
            second = self._enqueue(outbox)
            self.assertEqual(first["enqueue_state"], "ENQUEUED")
            self.assertEqual(second["enqueue_state"], "IDEMPOTENT")
            self.assertEqual(first["idempotency_key"], second["idempotency_key"])
            self.assertEqual(len(outbox.list()), 1)
            with self.assertRaisesRegex(ValueError, "idempotency collision"):
                self._enqueue(
                    outbox,
                    payload={"to": "different@example.com", "template": "followup"},
                )
            self.assertEqual(len(outbox.list()), 1)
            store.close()

    def test_decision_and_outbox_insert_roll_back_together(self):
        with tempfile.TemporaryDirectory() as raw:
            store, outbox = self._outbox(raw)
            store.db.executescript("""
            CREATE TRIGGER force_outbox_failure
            BEFORE INSERT ON action_outbox
            BEGIN
                SELECT RAISE(ABORT, 'forced outbox failure');
            END;
            """)
            with self.assertRaises(sqlite3.IntegrityError):
                self._enqueue(outbox)
            decisions = store.db.execute(
                "SELECT count(*) FROM action_decisions"
            ).fetchone()[0]
            rows = store.db.execute(
                "SELECT count(*) FROM action_outbox"
            ).fetchone()[0]
            self.assertEqual(decisions, 0)
            self.assertEqual(rows, 0)
            store.close()

    def test_two_workers_race_and_only_one_claims(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "chat.sqlite3"
            seed = SQLiteChatStore(path)
            seed_outbox = ExecutionOutbox(seed, self.scope)
            item = self._enqueue(seed_outbox)
            seed.close()

            def claim(index):
                local = SQLiteChatStore(path)
                try:
                    candidate = ExecutionOutbox(local, self.scope).claim_next(
                        f"worker-{index}",
                        now=NOW,
                        lease_seconds=60,
                    )
                    return candidate
                finally:
                    local.close()

            with ThreadPoolExecutor(max_workers=8) as pool:
                claimed = [row for row in pool.map(claim, range(8)) if row is not None]

            self.assertEqual(len(claimed), 1)
            self.assertEqual(claimed[0]["idempotency_key"], item["idempotency_key"])
            reopened = SQLiteChatStore(path)
            state = ExecutionOutbox(reopened, self.scope).get(item["idempotency_key"])
            self.assertEqual(state["state"], "CLAIMED")
            self.assertEqual(state["attempts"], 1)
            reopened.close()

    def test_revocation_at_use_blocks_without_calling_adapter(self):
        with tempfile.TemporaryDirectory() as raw:
            store, outbox = self._outbox(raw)
            item = self._enqueue(outbox)
            claimed = outbox.claim_next("worker-1", now=NOW, lease_seconds=60)
            adapter = FakeIdempotentAdapter()
            result = outbox.dispatch_claimed(
                claimed["idempotency_key"],
                worker_id="worker-1",
                authorize=policy(self.scope, allowed=False),
                adapter=adapter,
                now=NOW + timedelta(seconds=1),
            )
            self.assertEqual(result["state"], "REVOKED")
            self.assertEqual(result["last_error"], "AUTHORITY_REVOKED")
            self.assertEqual(adapter.send_calls, 0)
            self.assertEqual(outbox.effect_count(), 0)
            store.close()

    def test_policy_change_forces_reapproval_before_external_boundary(self):
        with tempfile.TemporaryDirectory() as raw:
            store, outbox = self._outbox(raw)
            self._enqueue(outbox)
            claimed = outbox.claim_next("worker-1", now=NOW, lease_seconds=60)
            adapter = FakeIdempotentAdapter()
            result = outbox.dispatch_claimed(
                claimed["idempotency_key"],
                worker_id="worker-1",
                authorize=policy(self.scope, policy_version="policy-v2"),
                adapter=adapter,
                now=NOW + timedelta(seconds=1),
            )
            self.assertEqual(result["state"], "BLOCKED_REAPPROVAL")
            self.assertEqual(result["last_error"], "POLICY_VERSION_CHANGED")
            self.assertEqual(adapter.send_calls, 0)
            store.close()

    def test_transaction_reauthentication_is_bound_to_the_intent(self):
        with tempfile.TemporaryDirectory() as raw:
            store, outbox = self._outbox(raw)
            self._enqueue(
                outbox,
                requires_reauth=True,
                reauth_ref="reauth-expected",
            )
            claimed = outbox.claim_next("worker-1", now=NOW, lease_seconds=60)
            adapter = FakeIdempotentAdapter()
            result = outbox.dispatch_claimed(
                claimed["idempotency_key"],
                worker_id="worker-1",
                authorize=policy(
                    self.scope,
                    reauthenticated=True,
                    reauth_ref="reauth-other",
                ),
                adapter=adapter,
                now=NOW + timedelta(seconds=1),
            )
            self.assertEqual(result["state"], "BLOCKED_REAPPROVAL")
            self.assertEqual(result["last_error"], "REAUTH_TRANSACTION_MISMATCH")
            self.assertEqual(adapter.send_calls, 0)
            store.close()

    def test_authority_expiry_blocks_even_if_policy_callback_allows(self):
        with tempfile.TemporaryDirectory() as raw:
            store, outbox = self._outbox(raw)
            self._enqueue(outbox, valid_until=NOW + timedelta(seconds=40))
            claimed = outbox.claim_next("worker-1", now=NOW, lease_seconds=120)
            adapter = FakeIdempotentAdapter()
            result = outbox.dispatch_claimed(
                claimed["idempotency_key"],
                worker_id="worker-1",
                authorize=policy(self.scope),
                adapter=adapter,
                now=NOW + timedelta(seconds=41),
            )
            self.assertEqual(result["state"], "BLOCKED_REAPPROVAL")
            self.assertEqual(result["last_error"], "AUTHORITY_EXPIRED")
            self.assertEqual(adapter.send_calls, 0)
            store.close()

    def test_lost_response_after_effect_requires_reconcile_and_never_blind_resends(self):
        with tempfile.TemporaryDirectory() as raw:
            store, outbox = self._outbox(raw)
            item = self._enqueue(outbox)
            outbox.claim_next("worker-1", now=NOW, lease_seconds=60)
            adapter = FakeIdempotentAdapter("lose-after-effect")
            first = outbox.dispatch_claimed(
                item["idempotency_key"],
                worker_id="worker-1",
                authorize=policy(self.scope),
                adapter=adapter,
                now=NOW + timedelta(seconds=1),
            )
            self.assertEqual(first["state"], "UNCERTAIN")
            self.assertEqual(first["dispatch_state"], "UNCERTAIN_RECONCILE_REQUIRED")
            self.assertEqual(adapter.send_calls, 1)
            self.assertEqual(len(adapter.effects), 1)
            self.assertIsNone(
                outbox.claim_next("worker-2", now=NOW + timedelta(seconds=2))
            )

            reconciled = outbox.reconcile(
                item["idempotency_key"],
                adapter=adapter,
                authorize=policy(self.scope),
                now=NOW + timedelta(seconds=3),
            )
            self.assertEqual(reconciled["state"], "CONFIRMED")
            self.assertEqual(reconciled["reconcile_state"], "CONFIRMED")
            self.assertEqual(adapter.send_calls, 1)
            self.assertEqual(outbox.effect_count(), 1)
            store.close()

    def test_authoritative_absence_allows_retry_after_lost_pre_effect_attempt(self):
        with tempfile.TemporaryDirectory() as raw:
            store, outbox = self._outbox(raw)
            item = self._enqueue(outbox)
            outbox.claim_next("worker-1", now=NOW, lease_seconds=60)
            adapter = FakeIdempotentAdapter("lose-before-effect")
            first = outbox.dispatch_claimed(
                item["idempotency_key"],
                worker_id="worker-1",
                authorize=policy(self.scope),
                adapter=adapter,
                now=NOW + timedelta(seconds=1),
            )
            self.assertEqual(first["state"], "UNCERTAIN")
            self.assertEqual(len(adapter.effects), 0)

            retry = outbox.reconcile(
                item["idempotency_key"],
                adapter=adapter,
                authorize=policy(self.scope),
                now=NOW + timedelta(seconds=2),
            )
            self.assertEqual(retry["state"], "RETRY")

            claimed = outbox.claim_next(
                "worker-2",
                now=NOW + timedelta(seconds=3),
                lease_seconds=60,
            )
            adapter.mode = "confirmed"
            final = outbox.dispatch_claimed(
                claimed["idempotency_key"],
                worker_id="worker-2",
                authorize=policy(self.scope),
                adapter=adapter,
                now=NOW + timedelta(seconds=4),
            )
            self.assertEqual(final["state"], "CONFIRMED")
            self.assertEqual(adapter.send_calls, 2)
            self.assertEqual(len(adapter.effects), 1)
            self.assertEqual(outbox.effect_count(), 1)
            store.close()

    def test_same_aggregate_is_ordered_until_previous_intent_is_terminal(self):
        with tempfile.TemporaryDirectory() as raw:
            store, outbox = self._outbox(raw)
            first = self._enqueue(outbox, ref="intent-1", aggregate="customer-7")
            second = self._enqueue(
                outbox,
                ref="intent-2",
                aggregate="customer-7",
                payload={"to": "client@example.com", "template": "second"},
            )
            self.assertEqual(first["aggregate_seq"], 1)
            self.assertEqual(second["aggregate_seq"], 2)

            claimed_first = outbox.claim_next("worker-1", now=NOW, lease_seconds=60)
            self.assertEqual(claimed_first["idempotency_key"], first["idempotency_key"])
            self.assertIsNone(
                outbox.claim_next("worker-2", now=NOW + timedelta(seconds=1))
            )

            adapter = FakeIdempotentAdapter()
            outbox.dispatch_claimed(
                first["idempotency_key"],
                worker_id="worker-1",
                authorize=policy(self.scope),
                adapter=adapter,
                now=NOW + timedelta(seconds=2),
            )
            claimed_second = outbox.claim_next(
                "worker-2",
                now=NOW + timedelta(seconds=3),
                lease_seconds=60,
            )
            self.assertEqual(claimed_second["idempotency_key"], second["idempotency_key"])
            store.close()

    def test_expired_claim_before_dispatch_is_retryable_because_boundary_not_crossed(self):
        with tempfile.TemporaryDirectory() as raw:
            store, outbox = self._outbox(raw)
            item = self._enqueue(outbox)
            outbox.claim_next("worker-1", now=NOW, lease_seconds=5)
            released = outbox.release_expired_claims(
                now=NOW + timedelta(seconds=6)
            )
            self.assertEqual(released, 1)
            retry = outbox.claim_next(
                "worker-2",
                now=NOW + timedelta(seconds=7),
                lease_seconds=60,
            )
            self.assertEqual(retry["idempotency_key"], item["idempotency_key"])
            self.assertEqual(retry["attempts"], 2)
            store.close()

    def test_cross_scope_cannot_read_or_claim_foreign_intent(self):
        with tempfile.TemporaryDirectory() as raw:
            store, outbox = self._outbox(raw)
            item = self._enqueue(outbox)
            other = ExecutionOutbox(
                store,
                Scope("mikael", "tenant-b", "workspace-a"),
            )
            self.assertEqual(other.list(), [])
            with self.assertRaises(LookupError):
                other.get(item["idempotency_key"])
            self.assertIsNone(other.claim_next("worker-x", now=NOW))
            store.close()

    def test_authority_ttl_is_bounded_and_reauth_ref_required(self):
        with tempfile.TemporaryDirectory() as raw:
            store, outbox = self._outbox(raw)
            with self.assertRaisesRegex(ValueError, "validity exceeds"):
                self._enqueue(
                    outbox,
                    valid_until=NOW + timedelta(
                        seconds=MAX_AUTHORITY_TTL_SECONDS + 1
                    ),
                )
            with self.assertRaisesRegex(ValueError, "reauthentication"):
                self._enqueue(
                    outbox,
                    ref="intent-reauth",
                    requires_reauth=True,
                    reauth_ref="",
                )
            self.assertEqual(outbox.list(), [])
            store.close()

    def test_sent_without_confirmation_is_reconciled_not_redispatched(self):
        with tempfile.TemporaryDirectory() as raw:
            store, outbox = self._outbox(raw)
            item = self._enqueue(outbox)
            outbox.claim_next("worker-1", now=NOW, lease_seconds=60)
            adapter = FakeIdempotentAdapter("sent")
            sent = outbox.dispatch_claimed(
                item["idempotency_key"],
                worker_id="worker-1",
                authorize=policy(self.scope),
                adapter=adapter,
                now=NOW + timedelta(seconds=1),
            )
            self.assertEqual(sent["state"], "SENT")
            self.assertEqual(adapter.send_calls, 1)
            self.assertIsNone(
                outbox.claim_next("worker-2", now=NOW + timedelta(seconds=2))
            )
            confirmed = outbox.reconcile(
                item["idempotency_key"],
                adapter=adapter,
                authorize=policy(self.scope),
                now=NOW + timedelta(seconds=3),
            )
            self.assertEqual(confirmed["state"], "CONFIRMED")
            self.assertEqual(adapter.send_calls, 1)
            self.assertEqual(outbox.effect_count(), 1)
            store.close()

    def test_module_has_no_built_in_external_execution_capability(self):
        source = Path("atlasquant_aion_execution_outbox.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("import requests", source)
        self.assertNotIn("import socket", source)
        self.assertNotIn("import subprocess", source)
        self.assertNotIn("os.system", source)
        self.assertIn("adapter.send", source)
        self.assertIn("adapter.reconcile", source)


if __name__ == "__main__":
    unittest.main()
