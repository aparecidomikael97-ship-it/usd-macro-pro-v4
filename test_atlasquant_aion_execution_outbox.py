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


def _fixture_simulate_independent_positive_review(outbox, key, effect_ref):
    """Only a raw SQLite fixture for stale-CAS race tests.

    NOT a producer receipt, approval function, or production recovery API.
    This must never be imported by an operating AION host.
    """
    current = outbox.get(key)
    if current["state"] not in {"SENT", "UNCERTAIN"}:
        raise AssertionError("fixture positive review expects an uncertain effect")
    with outbox.db:
        args = (key, outbox.scope.owner_id, outbox.scope.tenant_id, outbox.scope.workspace_id)
        outbox.db.execute(
            """INSERT INTO action_effects(
                idempotency_key,owner,tenant,workspace,effect_ref,confirmed_at,data
            ) VALUES (?,?,?,?,?,?,?)""",
            (*args, effect_ref, NOW.isoformat(), "{}"),
        )
        changed = outbox.db.execute(
            """UPDATE action_outbox
               SET state='CONFIRMED',effect_ref=?,confirmed_at=?,
                   lease_owner='',lease_until='',last_error=''
               WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?
                 AND state=? AND lease_owner=? AND lease_until=?""",
            (effect_ref, NOW.isoformat(), *args, current["state"],
             current["lease_owner"], current["lease_until"]),
        )
        if changed.rowcount != 1:
            raise AssertionError("stale fixture review; refusing to overwrite")


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
        """Legacy name retained for audit; no real first attempt may happen.

        Simulate an old UNCERTAIN local row ONLY after showing that the actual
        adapter is blocked before send. A synthetic marker is not a receipt.
        """
        with tempfile.TemporaryDirectory() as raw:
            store, outbox = self._outbox(raw)
            try:
                item = self._enqueue(outbox)
                key = item["idempotency_key"]
                outbox.claim_next("worker-1", now=NOW, lease_seconds=60)
                adapter = FakeIdempotentAdapter("lose-after-effect")
                with self.assertRaisesRegex(
                    PermissionError, "INDEPENDENT_PRODUCER_NOT_ENROLLED",
                ):
                    outbox.dispatch_claimed(
                        key, worker_id="worker-1",
                        authorize=policy(self.scope), adapter=adapter,
                        now=NOW + timedelta(seconds=1),
                    )
                self.assertEqual(outbox.get(key)["state"], "BLOCKED_PRODUCER")
                self.assertEqual(adapter.send_calls, 0)
                self.assertEqual(adapter.effects, {})
                # Fixture ONLY: model an older ambiguous snapshot, not proof
                # that anything was sent or that a provider exists.
                with store.db:
                    store.db.execute(
                        "UPDATE action_outbox SET state='UNCERTAIN', "
                        "dispatch_started_at=? WHERE idempotency_key=?",
                        (NOW.isoformat(), key),
                    )
                before = outbox.get(key)
                with self.assertRaisesRegex(
                    PermissionError, "INDEPENDENT_PRODUCER_NOT_ENROLLED",
                ):
                    outbox.reconcile(
                        key, adapter=adapter, authorize=policy(self.scope),
                        now=NOW + timedelta(seconds=2),
                    )
                self.assertEqual(outbox.get(key), before)
                self.assertEqual(adapter.reconcile_calls, 0)
                self.assertEqual(adapter.send_calls, 0)
                self.assertEqual(outbox.effect_count(), 0)
                self.assertIsNone(outbox.claim_next(
                    "worker-2", now=NOW + timedelta(seconds=3),
                ))
            finally:
                store.close()

    def test_unverified_absence_never_allows_retry_even_if_fixture_knows_no_effect(self):
        """Simulated absence must not permit readback, release or a second send."""
        with tempfile.TemporaryDirectory() as raw:
            store, outbox = self._outbox(raw)
            try:
                item = self._enqueue(outbox)
                key = item["idempotency_key"]
                outbox.claim_next("worker-1", now=NOW, lease_seconds=60)
                adapter = FakeIdempotentAdapter("lose-before-effect")
                with self.assertRaisesRegex(
                    PermissionError, "INDEPENDENT_PRODUCER_NOT_ENROLLED",
                ):
                    outbox.dispatch_claimed(
                        key, worker_id="worker-1",
                        authorize=policy(self.scope), adapter=adapter,
                        now=NOW + timedelta(seconds=1),
                    )
                self.assertEqual(outbox.get(key)["state"], "BLOCKED_PRODUCER")
                self.assertEqual(adapter.send_calls, 0)
                self.assertFalse(adapter.effects)
                # The raw fixture has no producer origin or late-effect fence.
                with store.db:
                    store.db.execute(
                        "UPDATE action_outbox SET state='UNCERTAIN', "
                        "dispatch_started_at=? WHERE idempotency_key=?",
                        (NOW.isoformat(), key),
                    )
                before = outbox.get(key)
                with self.assertRaisesRegex(
                    PermissionError, "INDEPENDENT_PRODUCER_NOT_ENROLLED",
                ):
                    outbox.reconcile(
                        key, adapter=adapter, authorize=policy(self.scope),
                        now=NOW + timedelta(seconds=2),
                    )
                self.assertEqual(outbox.get(key), before)
                self.assertEqual(adapter.reconcile_calls, 0)
                self.assertIsNone(outbox.claim_next(
                    "worker-2", now=NOW + timedelta(seconds=3),
                ))
                self.assertEqual(outbox.effect_count(), 0)
            finally:
                store.close()

    def test_same_aggregate_is_ordered_until_previous_intent_is_terminal(self):
        """A BLOCKED_PRODUCER predecessor remains nonterminal for FIFO."""
        with tempfile.TemporaryDirectory() as raw:
            store, outbox = self._outbox(raw)
            try:
                first = self._enqueue(outbox, ref="intent-1", aggregate="customer-7")
                second = self._enqueue(
                    outbox, ref="intent-2", aggregate="customer-7",
                    payload={"to": "client@example.com", "template": "second"},
                )
                self.assertEqual(first["aggregate_seq"], 1)
                self.assertEqual(second["aggregate_seq"], 2)
                claimed = outbox.claim_next(
                    "worker-1", now=NOW, lease_seconds=60,
                )
                self.assertEqual(claimed["idempotency_key"], first["idempotency_key"])
                self.assertIsNone(outbox.claim_next(
                    "worker-2", now=NOW + timedelta(seconds=1),
                ))
                adapter = FakeIdempotentAdapter()
                with self.assertRaisesRegex(
                    PermissionError, "INDEPENDENT_PRODUCER_NOT_ENROLLED",
                ):
                    outbox.dispatch_claimed(
                        first["idempotency_key"], worker_id="worker-1",
                        authorize=policy(self.scope), adapter=adapter,
                        now=NOW + timedelta(seconds=2),
                    )
                self.assertEqual(
                    outbox.get(first["idempotency_key"])["state"], "BLOCKED_PRODUCER",
                )
                self.assertIsNone(outbox.claim_next(
                    "worker-2", now=NOW + timedelta(seconds=3),
                ))
                self.assertEqual(
                    outbox.get(second["idempotency_key"])["state"], "PENDING",
                )
                self.assertEqual(adapter.send_calls, 0)
                self.assertEqual(outbox.effect_count(), 0)
            finally:
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
        """Historical SENT fixture stays blocked before untrusted reconcile."""
        with tempfile.TemporaryDirectory() as raw:
            store, outbox = self._outbox(raw)
            try:
                item = self._enqueue(outbox)
                key = item["idempotency_key"]
                outbox.claim_next("worker-1", now=NOW, lease_seconds=60)
                adapter = FakeIdempotentAdapter("sent")
                with self.assertRaisesRegex(
                    PermissionError, "INDEPENDENT_PRODUCER_NOT_ENROLLED",
                ):
                    outbox.dispatch_claimed(
                        key, worker_id="worker-1",
                        authorize=policy(self.scope), adapter=adapter,
                        now=NOW + timedelta(seconds=1),
                    )
                self.assertEqual(adapter.send_calls, 0)
                # Local historical reconstruction, NOT a real accepted send.
                with store.db:
                    store.db.execute(
                        "UPDATE action_outbox SET state='SENT', "
                        "dispatch_started_at=?, sent_at=? "
                        "WHERE idempotency_key=?",
                        (NOW.isoformat(), NOW.isoformat(), key),
                    )
                before = outbox.get(key)
                with self.assertRaisesRegex(
                    PermissionError, "INDEPENDENT_PRODUCER_NOT_ENROLLED",
                ):
                    outbox.reconcile(
                        key, adapter=adapter, authorize=policy(self.scope),
                        now=NOW + timedelta(seconds=3),
                    )
                self.assertEqual(outbox.get(key), before)
                self.assertEqual(adapter.reconcile_calls, 0)
                self.assertEqual(adapter.send_calls, 0)
                self.assertEqual(outbox.effect_count(), 0)
                self.assertIsNone(outbox.claim_next(
                    "worker-2", now=NOW + timedelta(seconds=4),
                ))
            finally:
                store.close()

    def test_module_has_no_built_in_external_execution_capability(self):
        source = Path("atlasquant_aion_execution_outbox.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("import requests", source)
        self.assertNotIn("import socket", source)
        self.assertNotIn("import subprocess", source)
        self.assertNotIn("os.system", source)
        self.assertIn('getattr(adapter, "send"', source)
        self.assertIn('getattr(adapter, "reconcile"', source)


# V16-A.14: isolate callback scope-binding regressions inside existing Quality suite.
class CountingAdapter:
    def __init__(self):
        self.calls = 0

    def send(self, _decision, _key):
        self.calls += 1
        raise AssertionError("external boundary must never be crossed")


class OutboxScopeBindingP0Tests(unittest.TestCase):
    def setUp(self):
        self.scope = Scope("owner-test", "tenant-a", "workspace-a")
        self.outbox = ExecutionOutbox.__new__(ExecutionOutbox)
        self.outbox.scope = self.scope
        self.decision = {
            "policy_version": "policy-v1",
            "authorization_ref": "approval-1",
            "valid_until": (NOW + timedelta(minutes=5)).isoformat(),
            "requires_reauth": False,
        }

    def grant(self):
        return {
            "allowed": True,
            "actor_id": self.scope.owner_id,
            "tenant_id": self.scope.tenant_id,
            "workspace_id": self.scope.workspace_id,
            "policy_version": "policy-v1",
            "authorization_ref": "approval-1",
        }

    def check(self, grant, *, decision=None):
        return self.outbox._authorization_gate(
            {"decision": decision or self.decision},
            lambda _decision: dict(grant),
            NOW + timedelta(seconds=1),
        )

    def assert_denied(self, grant, expected_reason):
        allowed, state, details = self.check(grant)
        self.assertFalse(allowed)
        self.assertEqual(state, "REVOKED")
        self.assertEqual(details["reason"], expected_reason)

    def test_missing_tenant_is_denied(self):
        grant = self.grant()
        del grant["tenant_id"]
        self.assert_denied(grant, "TENANT_ID_MISSING")

    def test_blank_tenant_is_denied(self):
        for value in ("", "   ", None):
            with self.subTest(value=value):
                grant = self.grant()
                grant["tenant_id"] = value
                self.assert_denied(grant, "TENANT_ID_MISSING")

    def test_missing_workspace_is_denied(self):
        grant = self.grant()
        del grant["workspace_id"]
        self.assert_denied(grant, "WORKSPACE_ID_MISSING")

    def test_blank_workspace_is_denied(self):
        for value in ("", "   ", None):
            with self.subTest(value=value):
                grant = self.grant()
                grant["workspace_id"] = value
                self.assert_denied(grant, "WORKSPACE_ID_MISSING")

    def test_wrong_tenant_is_denied(self):
        grant = self.grant()
        grant["tenant_id"] = "tenant-b"
        self.assert_denied(grant, "TENANT_ID_MISMATCH")

    def test_wrong_workspace_is_denied(self):
        grant = self.grant()
        grant["workspace_id"] = "workspace-b"
        self.assert_denied(grant, "WORKSPACE_ID_MISMATCH")

    def test_complete_scope_is_still_allowed_by_this_method(self):
        allowed, state, _details = self.check(self.grant())
        self.assertTrue(allowed)
        self.assertEqual(state, "ALLOW")

    def test_actor_mismatch_still_denied(self):
        grant = self.grant()
        grant["actor_id"] = "different-owner"
        self.assert_denied(grant, "ACTOR_MISMATCH")

    def test_policy_change_still_requires_reapproval(self):
        grant = self.grant()
        grant["policy_version"] = "policy-v2"
        allowed, state, details = self.check(grant)
        self.assertFalse(allowed)
        self.assertEqual(state, "BLOCKED_REAPPROVAL")
        self.assertEqual(details["reason"], "POLICY_VERSION_CHANGED")

    def test_expired_authority_still_denied(self):
        expired = dict(self.decision, valid_until=(NOW - timedelta(seconds=1)).isoformat())
        allowed, state, details = self.check(self.grant(), decision=expired)
        self.assertFalse(allowed)
        self.assertEqual(state, "BLOCKED_REAPPROVAL")
        self.assertEqual(details["reason"], "AUTHORITY_EXPIRED")

    def test_missing_scope_never_crosses_send_boundary(self):
        for missing_field, reason in (
            ("tenant_id", "TENANT_ID_MISSING"),
            ("workspace_id", "WORKSPACE_ID_MISSING"),
        ):
            with self.subTest(missing_field=missing_field):
                with tempfile.TemporaryDirectory() as raw:
                    store = SQLiteChatStore(Path(raw) / "chat.sqlite3")
                    try:
                        outbox = ExecutionOutbox(store, self.scope)
                        item = outbox.enqueue(
                            intent_ref="intent-scope-1",
                            action="send_email",
                            payload={"fixture": "strict-scope"},
                            aggregate_key="aggregate-1",
                            policy_version="policy-v1",
                            authorization_ref="approval-1",
                            created_at=NOW,
                            valid_until=NOW + timedelta(minutes=5),
                        )
                        outbox.claim_next("worker-1", now=NOW, lease_seconds=60)
                        grant = self.grant()
                        grant.pop(missing_field)
                        adapter = CountingAdapter()
                        result = outbox.dispatch_claimed(
                            item["idempotency_key"],
                            worker_id="worker-1",
                            authorize=lambda _decision: dict(grant),
                            adapter=adapter,
                            now=NOW + timedelta(seconds=1),
                        )
                        self.assertEqual(result["state"], "REVOKED")
                        self.assertEqual(result["last_error"], reason)
                        self.assertEqual(adapter.calls, 0)
                        self.assertEqual(outbox.effect_count(), 0)
                    finally:
                        store.close()




class OutboxTimeOfUseFenceP0Tests(unittest.TestCase):
    """Inert staged checks: no real producer, witness, or trusted clock."""

    def setUp(self):
        self.scope = Scope("owner-test", "tenant-a", "workspace-a")

    def fixture(self, *, ttl=100, lease_seconds=60):
        root = tempfile.TemporaryDirectory()
        store = SQLiteChatStore(Path(root.name) / "chat.sqlite3")
        outbox = ExecutionOutbox(store, self.scope)
        item = outbox.enqueue(
            intent_ref="intent-time-of-use",
            action="send_email",
            payload={"fixture": "no-network"},
            aggregate_key="client-time-of-use",
            policy_version="policy-v1",
            authorization_ref="approval-1",
            created_at=NOW,
            valid_until=NOW + timedelta(seconds=ttl),
        )
        outbox.claim_next("worker-1", now=NOW, lease_seconds=lease_seconds)
        return root, store, outbox, item

    def policy_grant(self, **changes):
        grant = policy(self.scope)({})
        grant.update(changes)
        return grant

    def test_authority_expired_during_first_callback_blocks_send(self):
        root, store, outbox, item = self.fixture(ttl=3)
        try:
            tick = [NOW + timedelta(seconds=1)]
            def authorize(_decision):
                tick[0] = NOW + timedelta(seconds=4)
                return self.policy_grant()
            adapter = CountingAdapter()
            result = outbox.dispatch_claimed(
                item["idempotency_key"], worker_id="worker-1",
                authorize=authorize, adapter=adapter, now=lambda: tick[0],
            )
            self.assertEqual(result["state"], "BLOCKED_REAPPROVAL")
            self.assertEqual(result["last_error"], "AUTHORITY_EXPIRED")
            self.assertEqual(adapter.calls, 0)
        finally:
            store.close()
            root.cleanup()

    def test_lease_expired_during_first_callback_blocks_send(self):
        root, store, outbox, item = self.fixture(lease_seconds=3)
        try:
            tick = [NOW + timedelta(seconds=1)]
            def authorize(_decision):
                tick[0] = NOW + timedelta(seconds=4)
                return self.policy_grant()
            adapter = CountingAdapter()
            with self.assertRaisesRegex(TimeoutError, "lease expired"):
                outbox.dispatch_claimed(
                    item["idempotency_key"], worker_id="worker-1",
                    authorize=authorize, adapter=adapter, now=lambda: tick[0],
                )
            self.assertEqual(outbox.get(item["idempotency_key"])["state"], "CLAIMED")
            self.assertEqual(adapter.calls, 0)
        finally:
            store.close()
            root.cleanup()

    def test_revoked_by_second_authorization_callback_blocks_send(self):
        root, store, outbox, item = self.fixture()
        try:
            calls = [0]
            def authorize(_decision):
                calls[0] += 1
                return self.policy_grant(allowed=(calls[0] == 1))
            adapter = CountingAdapter()
            result = outbox.dispatch_claimed(
                item["idempotency_key"], worker_id="worker-1",
                authorize=authorize, adapter=adapter,
                now=NOW + timedelta(seconds=1),
            )
            self.assertEqual(calls[0], 2)
            self.assertEqual(result["state"], "REVOKED")
            self.assertEqual(result["last_error"], "AUTHORITY_REVOKED")
            self.assertEqual(adapter.calls, 0)
        finally:
            store.close()
            root.cleanup()

    def test_lease_expires_during_second_callback_blocks_send(self):
        root, store, outbox, item = self.fixture(lease_seconds=3)
        try:
            tick, calls = [NOW + timedelta(seconds=1)], [0]
            def authorize(_decision):
                calls[0] += 1
                if calls[0] == 2:
                    tick[0] = NOW + timedelta(seconds=4)
                return self.policy_grant()
            adapter = CountingAdapter()
            with self.assertRaisesRegex(TimeoutError, "lease expired"):
                outbox.dispatch_claimed(
                    item["idempotency_key"], worker_id="worker-1",
                    authorize=authorize, adapter=adapter, now=lambda: tick[0],
                )
            self.assertEqual(calls[0], 2)
            self.assertEqual(adapter.calls, 0)
        finally:
            store.close()
            root.cleanup()

    def test_cas_rejects_lease_changed_during_callback(self):
        root, store, outbox, item = self.fixture()
        try:
            calls = [0]
            def authorize(_decision):
                calls[0] += 1
                if calls[0] == 1:
                    with store.db:
                        store.db.execute(
                            "UPDATE action_outbox SET lease_until=? WHERE idempotency_key=?",
                            ((NOW + timedelta(seconds=45)).isoformat(),
                             item["idempotency_key"]),
                        )
                return self.policy_grant()
            adapter = CountingAdapter()
            with self.assertRaisesRegex(TimeoutError, "changed before send"):
                outbox.dispatch_claimed(
                    item["idempotency_key"], worker_id="worker-1",
                    authorize=authorize, adapter=adapter,
                    now=NOW + timedelta(seconds=1),
                )
            self.assertEqual(adapter.calls, 0)
            self.assertEqual(outbox.get(item["idempotency_key"])["state"], "CLAIMED")
        finally:
            store.close()
            root.cleanup()

    def test_cas_rejects_persisted_authority_deadline_changed(self):
        root, store, outbox, item = self.fixture()
        try:
            calls = [0]
            def authorize(_decision):
                calls[0] += 1
                if calls[0] == 1:
                    with store.db:
                        store.db.execute(
                            "UPDATE action_decisions SET valid_until=? WHERE decision_id=?",
                            (NOW.isoformat(), item["decision"]["decision_id"]),
                        )
                return self.policy_grant()
            adapter = CountingAdapter()
            with self.assertRaisesRegex(TimeoutError, "changed before send"):
                outbox.dispatch_claimed(
                    item["idempotency_key"], worker_id="worker-1",
                    authorize=authorize, adapter=adapter,
                    now=NOW + timedelta(seconds=1),
                )
            self.assertEqual(adapter.calls, 0)
            self.assertEqual(outbox.get(item["idempotency_key"])["state"], "CLAIMED")
        finally:
            store.close()
            root.cleanup()

    def test_unexpired_claim_still_dispatches_once(self):
        """Historical method ID: an unexpired claim NEVER sends without issuer."""
        root, store, outbox, item = self.fixture()
        try:
            adapter = FakeIdempotentAdapter()
            key = item["idempotency_key"]
            with self.assertRaisesRegex(
                PermissionError, "INDEPENDENT_PRODUCER_NOT_ENROLLED",
            ):
                outbox.dispatch_claimed(
                    key, worker_id="worker-1",
                    authorize=policy(self.scope), adapter=adapter,
                    now=NOW + timedelta(seconds=1),
                )
            blocked = outbox.get(key)
            self.assertEqual(blocked["state"], "BLOCKED_PRODUCER")
            self.assertEqual(
                blocked["last_error"], "INDEPENDENT_PRODUCER_NOT_ENROLLED",
            )
            self.assertEqual(adapter.send_calls, 0)
            self.assertEqual(adapter.effects, {})
            self.assertEqual(outbox.effect_count(), 0)
            self.assertIsNone(outbox.claim_next(
                "worker-2", now=NOW + timedelta(seconds=2),
            ))
            # A second caller cannot re-dispatch the quarantined intent.
            with self.assertRaisesRegex(ValueError, "intent must be CLAIMED"):
                outbox.dispatch_claimed(
                    key, worker_id="worker-1",
                    authorize=policy(self.scope), adapter=adapter,
                    now=NOW + timedelta(seconds=3),
                )
            self.assertEqual(adapter.send_calls, 0)
            self.assertEqual(outbox.effect_count(), 0)
        finally:
            store.close()
            root.cleanup()

class OutboxStaleStateBlockCASP0Tests(unittest.TestCase):
    """Synthetic interleavings expose stale status/lease overwrite risks."""

    def setUp(self):
        self.scope = Scope("owner-test", "tenant-a", "workspace-a")
        self.tempdir = tempfile.TemporaryDirectory()
        self.store = SQLiteChatStore(Path(self.tempdir.name) / "chat.sqlite3")
        self.outbox = ExecutionOutbox(self.store, self.scope)
        self.item = self.outbox.enqueue(
            intent_ref="intent-stale-block",
            action="send_email",
            payload={"fixture": "no-network"},
            aggregate_key="client-stale-block",
            policy_version="policy-v1",
            authorization_ref="approval-1",
            created_at=NOW,
            valid_until=NOW + timedelta(minutes=5),
        )
        self.key = self.item["idempotency_key"]
        self.outbox.claim_next("worker-1", now=NOW, lease_seconds=60)

    def tearDown(self):
        self.store.close()
        self.tempdir.cleanup()

    def test_late_revocation_does_not_clobber_confirmed_effect(self):
        def changed_while_callback(_decision):
            # Simulate another actor confirming before this old callback replies.
            # Synthetic peer updates an independently observed terminal row.
            # A fresh _confirm from CLAIMED is intentionally forbidden.
            with self.store.db:
                self.store.db.execute(
                    """INSERT INTO action_effects(
                        idempotency_key,owner,tenant,workspace,effect_ref,confirmed_at,data
                    ) VALUES (?,?,?,?,?,?,?)""",
                    (
                        self.key, self.scope.owner_id, self.scope.tenant_id,
                        self.scope.workspace_id, "EFFECT-PROVEN",
                        (NOW + timedelta(seconds=1)).isoformat(), "{}",
                    ),
                )
                self.store.db.execute(
                    """UPDATE action_outbox SET state='CONFIRMED',
                        confirmed_at=?,effect_ref=?,lease_owner='',lease_until=''
                        WHERE idempotency_key=?""",
                    ((NOW + timedelta(seconds=1)).isoformat(), "EFFECT-PROVEN", self.key),
                )
            return policy(self.scope, allowed=False)({})
        adapter = CountingAdapter()
        with self.assertRaisesRegex(RuntimeError, "stale outbox state/lease"):
            self.outbox.dispatch_claimed(
                self.key, worker_id="worker-1",
                authorize=changed_while_callback,
                adapter=adapter, now=NOW + timedelta(seconds=1),
            )
        self.assertEqual(self.outbox.get(self.key)["state"], "CONFIRMED")
        self.assertEqual(self.outbox.effect_count(), 1)
        self.assertEqual(adapter.calls, 0)

    def test_late_revocation_cannot_revoke_reclaimed_claim(self):
        def changed_while_callback(_decision):
            with self.store.db:
                self.store.db.execute(
                    "UPDATE action_outbox SET lease_owner=?,lease_until=? "
                    "WHERE idempotency_key=?",
                    ("worker-2", (NOW + timedelta(seconds=55)).isoformat(), self.key),
                )
            return policy(self.scope, allowed=False)({})
        adapter = CountingAdapter()
        with self.assertRaisesRegex(RuntimeError, "stale outbox state/lease"):
            self.outbox.dispatch_claimed(
                self.key, worker_id="worker-1",
                authorize=changed_while_callback,
                adapter=adapter, now=NOW + timedelta(seconds=1),
            )
        unchanged = self.outbox.get(self.key)
        self.assertEqual(unchanged["state"], "CLAIMED")
        self.assertEqual(unchanged["lease_owner"], "worker-2")
        self.assertEqual(adapter.calls, 0)

    def test_reconcile_late_block_cannot_clobber_confirmation(self):
        """Historical readback and late negative cannot overwrite peer state.

        No independent producer is enrolled: both send and readback deny.
        A later local CONFIRMED is only a synthetic stale-CAS fixture.
        """
        adapter = FakeIdempotentAdapter(mode="sent")
        with self.assertRaisesRegex(
            PermissionError, "^INDEPENDENT_PRODUCER_NOT_ENROLLED$",
        ):
            self.outbox.dispatch_claimed(
                self.key, worker_id="worker-1",
                authorize=policy(self.scope), adapter=adapter,
                now=NOW + timedelta(seconds=1),
            )
        self.assertEqual(self.outbox.get(self.key)["state"], "BLOCKED_PRODUCER")
        self.assertEqual(adapter.send_calls, 0)
        with self.store.db:
            self.store.db.execute(
                "UPDATE action_outbox SET state='SENT',sent_at=?,"
                "dispatch_started_at=? WHERE idempotency_key=?",
                (NOW.isoformat(), NOW.isoformat(), self.key),
            )
        class LateNegative:
            reconcile_calls = 0
            def reconcile(self, _key, _decision):
                self.reconcile_calls += 1
                return {"found": False, "authoritative_absence": True}
        negative = LateNegative()
        before = self.outbox.get(self.key)
        with self.assertRaisesRegex(
            PermissionError, "^INDEPENDENT_PRODUCER_NOT_ENROLLED$",
        ):
            self.outbox.reconcile(
                self.key, adapter=negative,
                authorize=policy(self.scope, allowed=False),
                now=NOW + timedelta(seconds=3),
            )
        self.assertEqual(self.outbox.get(self.key), before)
        self.assertEqual(negative.reconcile_calls, 0)
        # Local peer state simulation tests terminal immutability, not real
        # external evidence of an effect.
        _fixture_simulate_independent_positive_review(
            self.outbox, self.key, "EFFECT-TEST-ONLY-PEER",
        )
        final = self.outbox.get(self.key)
        with self.assertRaisesRegex(ValueError, "only SENT or UNCERTAIN"):
            self.outbox.reconcile(
                self.key, adapter=negative,
                authorize=policy(self.scope, allowed=False),
                now=NOW + timedelta(seconds=4),
            )
        self.assertEqual(self.outbox.get(self.key), final)
        self.assertEqual(final["state"], "CONFIRMED")
        self.assertEqual(negative.reconcile_calls, 0)
        self.assertEqual(adapter.send_calls, 0)
        self.assertEqual(self.outbox.effect_count(), 1)

    def test_current_revocation_remains_functional(self):
        result = self.outbox.dispatch_claimed(
            self.key, worker_id="worker-1",
            authorize=policy(self.scope, allowed=False),
            adapter=CountingAdapter(), now=NOW + timedelta(seconds=1),
        )
        self.assertEqual(result["state"], "REVOKED")
        self.assertEqual(result["last_error"], "AUTHORITY_REVOKED")



class OutboxReconcileStaleRetryCASP0Tests(unittest.TestCase):
    """NO-GO reconstruction of old snapshots; no real readback or issuer."""

    def setUp(self):
        self.scope = Scope("owner-test", "tenant-a", "workspace-a")
        self.tempdir = tempfile.TemporaryDirectory()
        self.store = SQLiteChatStore(Path(self.tempdir.name) / "chat.sqlite3")
        self.outbox = ExecutionOutbox(self.store, self.scope)
        self.item = self.outbox.enqueue(
            intent_ref="intent-stale-retry",
            action="send_email",
            payload={"fixture": "local-only"},
            aggregate_key="client-stale-retry",
            policy_version="policy-v1",
            authorization_ref="approval-1",
            created_at=NOW,
            valid_until=NOW + timedelta(minutes=5),
        )
        self.key = self.item["idempotency_key"]
        self.outbox.claim_next("worker-1", now=NOW, lease_seconds=60)
        self.adapter = FakeIdempotentAdapter("sent")
        with self.assertRaisesRegex(
            PermissionError, "^INDEPENDENT_PRODUCER_NOT_ENROLLED$",
        ):
            self.outbox.dispatch_claimed(
                self.key, worker_id="worker-1",
                authorize=policy(self.scope), adapter=self.adapter,
                now=NOW + timedelta(seconds=1),
            )
        self.assertEqual(self.adapter.send_calls, 0)
        self.assertEqual(self.outbox.get(self.key)["state"], "BLOCKED_PRODUCER")
        # Test ONLY: emulate a preexisting historical SENT row. Not a real
        # send, not an enrolled source, not a replacement for provenance.
        with self.store.db:
            self.store.db.execute(
                "UPDATE action_outbox SET state='SENT',sent_at=?,"
                "dispatch_started_at=?,last_error='AION_TEST_ONLY_SYNTHETIC_SENT' "
                "WHERE idempotency_key=?",
                (NOW.isoformat(), NOW.isoformat(), self.key),
            )
        self.assertEqual(self.outbox.get(self.key)["state"], "SENT")
        self.assertEqual(self.outbox.effect_count(), 0)

    def tearDown(self):
        self.store.close()
        self.tempdir.cleanup()

    def test_stale_absence_must_not_reopen_confirmed_effect(self):
        # Reconciliation is not trusted BEFORE accessing the adapter method.
        class NoReconcileProperty:
            property_reads = 0

            @property
            def reconcile(self):
                self.property_reads += 1
                raise AssertionError("untrusted descriptor must never be accessed")

        adapter = NoReconcileProperty()
        before = self.outbox.get(self.key)
        with self.assertRaisesRegex(
            PermissionError, "^INDEPENDENT_PRODUCER_NOT_ENROLLED$",
        ):
            self.outbox.reconcile(
                self.key, adapter=adapter,
                authorize=policy(self.scope),
                now=NOW + timedelta(seconds=2),
            )
        self.assertEqual(adapter.property_reads, 0)
        self.assertEqual(self.outbox.get(self.key), before)
        # Synthetic peer review is an inert stale-CAS fixture, not an
        # issuer receipt. A local confirmed state cannot be reopened.
        _fixture_simulate_independent_positive_review(
            self.outbox, self.key, "EFFECT-TEST-ONLY",
        )
        confirmed = self.outbox.get(self.key)
        with self.assertRaisesRegex(ValueError, "only SENT or UNCERTAIN"):
            self.outbox.reconcile(
                self.key, adapter=adapter,
                authorize=policy(self.scope),
                now=NOW + timedelta(seconds=3),
            )
        self.assertEqual(self.outbox.get(self.key), confirmed)
        self.assertEqual(self.outbox.get(self.key)["state"], "CONFIRMED")
        self.assertEqual(adapter.property_reads, 0)
        self.assertEqual(self.adapter.send_calls, 0)
        self.assertEqual(self.outbox.effect_count(), 1)

    def test_stale_absence_cannot_reopen_revoked_state(self):
        class HostileAdapter:
            calls = 0
            def reconcile(self, _key, _decision):
                self.calls += 1
                raise AssertionError("untrusted readback")

        adapter = HostileAdapter()
        before = self.outbox.get(self.key)
        with self.assertRaisesRegex(
            PermissionError, "^INDEPENDENT_PRODUCER_NOT_ENROLLED$",
        ):
            self.outbox.reconcile(
                self.key, adapter=adapter,
                authorize=policy(self.scope),
                now=NOW + timedelta(seconds=2),
            )
        self.assertEqual(self.outbox.get(self.key), before)
        # Simulate local revocation by a peer only AFTER an earlier
        # denied readback, never by an adapter callback.
        with self.store.db:
            self.store.db.execute(
                "UPDATE action_outbox SET state='REVOKED' "
                "WHERE idempotency_key=?", (self.key,),
            )
        revoked = self.outbox.get(self.key)
        with self.assertRaisesRegex(ValueError, "only SENT or UNCERTAIN"):
            self.outbox.reconcile(
                self.key, adapter=adapter,
                authorize=policy(self.scope),
                now=NOW + timedelta(seconds=3),
            )
        self.assertEqual(self.outbox.get(self.key), revoked)
        self.assertEqual(revoked["state"], "REVOKED")
        self.assertEqual(self.outbox.effect_count(), 0)
        self.assertEqual(self.adapter.send_calls, 0)
        self.assertEqual(adapter.calls, 0)

    def test_unverified_absence_cannot_invoke_authorize_or_reopen_retry(self):
        class Absence:
            reconcile_calls = 0
            def reconcile(self, _key, _decision):
                self.reconcile_calls += 1
                return {"found": False, "authoritative_absence": True}

        adapter = Absence()
        authorize_calls = []
        def observed_authorize(_decision):
            authorize_calls.append("unexpected")
            return policy(self.scope)({})
        before = self.outbox.get(self.key)
        with self.assertRaisesRegex(
            PermissionError, "^INDEPENDENT_PRODUCER_NOT_ENROLLED$",
        ):
            self.outbox.reconcile(
                self.key, adapter=adapter,
                authorize=observed_authorize,
                now=NOW + timedelta(seconds=3),
            )
        self.assertEqual(authorize_calls, [])
        self.assertEqual(adapter.reconcile_calls, 0)
        self.assertEqual(self.adapter.send_calls, 0)
        self.assertEqual(self.outbox.get(self.key), before)
        self.assertEqual(self.outbox.get(self.key)["state"], "SENT")
        self.assertEqual(self.outbox.effect_count(), 0)
        self.assertIsNone(self.outbox.claim_next(
            "worker-after-untrusted-absence", now=NOW + timedelta(seconds=4),
        ))


class OutboxPostSendStateCASP0Tests(unittest.TestCase):
    """Post-send race fixtures; adapter callbacks are not external evidence."""

    def setUp(self):
        self.scope = Scope("owner-test", "tenant-a", "workspace-a")
        self.tempdir = tempfile.TemporaryDirectory()
        self.store = SQLiteChatStore(Path(self.tempdir.name) / "chat.sqlite3")
        self.outbox = ExecutionOutbox(self.store, self.scope)
        self.item = self.outbox.enqueue(
            intent_ref="intent-post-send-cas",
            action="send_email",
            payload={"fixture": "inert-only"},
            aggregate_key="client-post-send",
            policy_version="policy-v1",
            authorization_ref="approval-1",
            created_at=NOW,
            valid_until=NOW + timedelta(minutes=5),
        )
        self.key = self.item["idempotency_key"]
        self.outbox.claim_next("worker-1", now=NOW, lease_seconds=60)

    def tearDown(self):
        self.store.close()
        self.tempdir.cleanup()

    def dispatch(self, adapter):
        return self.outbox.dispatch_claimed(
            self.key, worker_id="worker-1",
            authorize=policy(self.scope), adapter=adapter,
            now=NOW + timedelta(seconds=1),
        )

    def peer_state(self, state, *, record_effect=False):
        # Pure SQL fixture simulates a concurrent state owner, not a real producer.
        with self.store.db:
            if record_effect:
                self.store.db.execute(
                    """INSERT INTO action_effects(
                        idempotency_key,owner,tenant,workspace,effect_ref,confirmed_at,data
                    ) VALUES (?,?,?,?,?,?,?)""",
                    (
                        self.key, self.scope.owner_id, self.scope.tenant_id,
                        self.scope.workspace_id, "EFFECT-PEER",
                        (NOW + timedelta(seconds=2)).isoformat(), "{}",
                    ),
                )
            self.store.db.execute(
                "UPDATE action_outbox SET state=?,effect_ref=?,lease_owner='',lease_until='' "
                "WHERE idempotency_key=?",
                (state, "EFFECT-PEER" if record_effect else "", self.key),
            )

    def test_confirmed_adapter_response_cannot_overwrite_revoked(self):
        fixture = self
        class Adapter:
            def send(self, _decision, _key):
                fixture.peer_state("REVOKED")
                return {"accepted": True, "confirmed": True, "effect_ref": "EFFECT-OLD"}
        with self.assertRaisesRegex(RuntimeError, "stale unverified adapter claim"):
            self.dispatch(Adapter())
        self.assertEqual(self.outbox.get(self.key)["state"], "REVOKED")
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_stale_adapter_reject_cannot_reopen_confirmed_as_retry_or_failed(self):
        for retryable in (True, False):
            with self.subTest(retryable=retryable):
                # Reset fixture state between the two independent simulations.
                if self.outbox.get(self.key)["state"] != "CLAIMED":
                    with self.store.db:
                        self.store.db.execute(
                            "DELETE FROM action_effects WHERE idempotency_key=?", (self.key,),
                        )
                        self.store.db.execute(
                            """UPDATE action_outbox
                               SET state='CLAIMED',lease_owner='worker-1',lease_until=?,
                                   effect_ref='',last_error=''
                               WHERE idempotency_key=?""",
                            ((NOW + timedelta(seconds=60)).isoformat(), self.key),
                        )
                fixture = self
                class Adapter:
                    def send(self, _decision, _key):
                        fixture.peer_state("CONFIRMED", record_effect=True)
                        return {
                            "accepted": False, "retryable": retryable,
                            "reason": "stale adapter claim",
                        }
                with self.assertRaisesRegex(RuntimeError, "stale unverified adapter claim"):
                    self.dispatch(Adapter())
                self.assertEqual(self.outbox.get(self.key)["state"], "CONFIRMED")
                self.assertEqual(self.outbox.get(self.key)["effect_ref"], "EFFECT-PEER")
                self.assertEqual(self.outbox.effect_count(), 1)

    def test_stale_sent_response_cannot_overwrite_confirmed(self):
        fixture = self
        class Adapter:
            def send(self, _decision, _key):
                fixture.peer_state("CONFIRMED", record_effect=True)
                return {"accepted": True, "confirmed": False, "effect_ref": "EFFECT-OLD"}
        with self.assertRaisesRegex(RuntimeError, "stale send result"):
            self.dispatch(Adapter())
        self.assertEqual(self.outbox.get(self.key)["state"], "CONFIRMED")
        self.assertEqual(self.outbox.effect_count(), 1)

    def test_exception_after_peer_confirmation_never_clobbers_it(self):
        fixture = self
        class Adapter:
            def send(self, _decision, _key):
                fixture.peer_state("CONFIRMED", record_effect=True)
                raise TimeoutError("fixture lost response after peer confirmation")
        with self.assertRaisesRegex(RuntimeError, "stale send error"):
            self.dispatch(Adapter())
        self.assertEqual(self.outbox.get(self.key)["state"], "CONFIRMED")
        self.assertEqual(self.outbox.effect_count(), 1)

    def test_reconcile_confirmed_cannot_revive_revoked(self):
        fixture = self
        class Adapter:
            def send(self, _decision, _key):
                return {"accepted": True, "confirmed": False, "effect_ref": "EFFECT-PENDING"}
            def reconcile(self, _key, _decision):
                fixture.peer_state("REVOKED")
                return {"found": True, "confirmed": True, "effect_ref": "EFFECT-STALE"}
        adapter = Adapter()
        self.assertEqual(self.dispatch(adapter)["state"], "SENT")
        observed = self.outbox.reconcile(
            self.key, adapter=adapter, authorize=policy(self.scope),
            now=NOW + timedelta(seconds=2),
        )
        self.assertEqual(observed["reconcile_state"], "STALE_OBSERVATION_IGNORED")
        self.assertEqual(self.outbox.get(self.key)["state"], "REVOKED")
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_confirm_rejects_claimed_without_send(self):
        with self.assertRaisesRegex(PermissionError, "INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED"):
            self.outbox._confirm(
                self.key, expected=self.outbox.get(self.key),
                effect_ref="EFFECT-FAKE", confirmed_at=NOW,
            )
        self.assertEqual(self.outbox.get(self.key)["state"], "CLAIMED")
        self.assertEqual(self.outbox.effect_count(), 0)



class OutboxUnverifiedAdapterResultP0Tests(unittest.TestCase):
    """Untrusted negative answers must NOT certify no effect or allow a resend."""

    def test_adapter_rejection_boolean_does_not_release_aggregate(self):
        """A negative adapter boolean never bypasses enrollment or FIFO."""
        for retryable in (True, False):
            with self.subTest(retryable=retryable):
                with tempfile.TemporaryDirectory() as raw:
                    scope = Scope("owner-test", "tenant-a", "workspace-a")
                    store = SQLiteChatStore(Path(raw) / "chat.sqlite3")
                    try:
                        outbox = ExecutionOutbox(store, scope)
                        first = outbox.enqueue(
                            intent_ref="intent-first", action="send_email",
                            payload={"fixture": 1}, aggregate_key="client-1",
                            policy_version="policy-v1", authorization_ref="approval-1",
                            created_at=NOW, valid_until=NOW + timedelta(minutes=5),
                        )
                        second = outbox.enqueue(
                            intent_ref="intent-second", action="send_email",
                            payload={"fixture": 2}, aggregate_key="client-1",
                            policy_version="policy-v1", authorization_ref="approval-1",
                            created_at=NOW, valid_until=NOW + timedelta(minutes=5),
                        )
                        outbox.claim_next("worker-1", now=NOW, lease_seconds=60)

                        class RejectingAdapter:
                            send_calls = 0
                            def send(self, _decision, _key):
                                self.send_calls += 1
                                return {
                                    "accepted": False, "retryable": retryable,
                                    "reason": "unverified adapter rejection",
                                }

                        adapter = RejectingAdapter()
                        with self.assertRaisesRegex(
                            PermissionError, "^INDEPENDENT_PRODUCER_NOT_ENROLLED$",
                        ):
                            outbox.dispatch_claimed(
                                first["idempotency_key"], worker_id="worker-1",
                                authorize=policy(scope), adapter=adapter,
                                now=NOW + timedelta(seconds=1),
                            )
                        first_state = outbox.get(first["idempotency_key"])
                        self.assertEqual(first_state["state"], "BLOCKED_PRODUCER")
                        self.assertEqual(
                            first_state["last_error"],
                            "INDEPENDENT_PRODUCER_NOT_ENROLLED",
                        )
                        self.assertEqual(adapter.send_calls, 0)
                        self.assertEqual(outbox.effect_count(), 0)
                        self.assertIsNone(outbox.claim_next(
                            "worker-2", now=NOW + timedelta(seconds=2),
                        ))
                        self.assertEqual(
                            outbox.get(second["idempotency_key"])["state"], "PENDING",
                        )
                    finally:
                        store.close()

    def test_false_authoritative_absence_remains_quarantined(self):
        """A forged authoritative_absence cannot reopen a historical uncertainty."""
        with tempfile.TemporaryDirectory() as raw:
            scope = Scope("owner-test", "tenant-a", "workspace-a")
            store = SQLiteChatStore(Path(raw) / "chat.sqlite3")
            try:
                outbox = ExecutionOutbox(store, scope)
                item = outbox.enqueue(
                    intent_ref="intent-ambiguous", action="send_email",
                    payload={"fixture": 1}, aggregate_key="client-1",
                    policy_version="policy-v1", authorization_ref="approval-1",
                    created_at=NOW, valid_until=NOW + timedelta(minutes=5),
                )
                key = item["idempotency_key"]
                outbox.claim_next("worker-1", now=NOW, lease_seconds=60)

                class AdversarialAdapter:
                    send_calls = 0
                    reconcile_calls = 0
                    def send(self, _decision, _key):
                        self.send_calls += 1
                        raise TimeoutError("effect may have occurred")
                    def reconcile(self, _key, _decision):
                        self.reconcile_calls += 1
                        return {"found": False, "authoritative_absence": True}

                adapter = AdversarialAdapter()
                with self.assertRaisesRegex(
                    PermissionError, "^INDEPENDENT_PRODUCER_NOT_ENROLLED$",
                ):
                    outbox.dispatch_claimed(
                        key, worker_id="worker-1",
                        authorize=policy(scope), adapter=adapter,
                        now=NOW + timedelta(seconds=1),
                    )
                self.assertEqual(outbox.get(key)["state"], "BLOCKED_PRODUCER")
                self.assertEqual(adapter.send_calls, 0)
                # Fabricated local UNCERTAIN mirrors a possible older database.
                # Its existence cannot prove that a remote effect never occurred.
                with store.db:
                    store.db.execute(
                        "UPDATE action_outbox SET state='UNCERTAIN',"
                        "dispatch_started_at=? WHERE idempotency_key=?",
                        (NOW.isoformat(), key),
                    )
                before = outbox.get(key)
                with self.assertRaisesRegex(
                    PermissionError, "^INDEPENDENT_PRODUCER_NOT_ENROLLED$",
                ):
                    outbox.reconcile(
                        key, adapter=adapter, authorize=policy(scope),
                        now=NOW + timedelta(seconds=2),
                    )
                self.assertEqual(outbox.get(key), before)
                self.assertIsNone(outbox.claim_next(
                    "worker-2", now=NOW + timedelta(seconds=3),
                ))
                self.assertEqual(adapter.send_calls, 0)
                self.assertEqual(adapter.reconcile_calls, 0)
                self.assertEqual(outbox.effect_count(), 0)
            finally:
                store.close()

# A.21: RED negative proof of untrusted positive callback admission on real Outbox.
def fixture_authority(scope):
    """Synthetic authorization ONLY; it confers zero productive authority."""
    def check(_decision):
        return {
            "allowed": True,
            "actor_id": scope.owner_id,
            "tenant_id": scope.tenant_id,
            "workspace_id": scope.workspace_id,
            "policy_version": "policy-v1",
            "authorization_ref": "approval-fixture-only",
        }
    return check


class ClaimsConfirmedWithoutProducer:
    def __init__(self):
        self.calls = 0
        self.real_effects = 0

    def send(self, _decision, _key):
        self.calls += 1
        # Deliberately fabricates claims, never calls a producer.
        return {
            "accepted": True,
            "confirmed": True,
            "effect_ref": "CALLER-FORGED-POSITIVE",
        }


class ClaimsReconciledWithoutProducer:
    def __init__(self):
        self.send_calls = 0
        self.reconcile_calls = 0
        self.real_effects = 0

    def send(self, _decision, _key):
        self.send_calls += 1
        return {
            "accepted": True,
            "confirmed": False,
            "effect_ref": "UNVERIFIED-SEND-REF",
        }

    def reconcile(self, _key, _decision):
        self.reconcile_calls += 1
        # Deliberately forges a positive receipt instead of citing any issuer.
        return {
            "found": True,
            "confirmed": True,
            "effect_ref": "CALLER-FORGED-RECONCILE-POSITIVE",
        }


class RejectsWithoutProducer:
    def __init__(self):
        self.calls = 0

    def send(self, _decision, _key):
        self.calls += 1
        return {"accepted": False, "retryable": True, "reason": "fixture negative"}


class AionUntrustedPositiveAdmissionRedTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.store = SQLiteChatStore(Path(self.root.name) / "chat.sqlite3")
        self.scope = Scope("fixture-owner", "tenant-a", "workspace-a")
        self.outbox = ExecutionOutbox(self.store, self.scope)
        self.item = self.outbox.enqueue(
            intent_ref="intent-false-positive-A21",
            action="send_email",
            payload={"fixture": "no producer exists"},
            aggregate_key="client-false-positive-A21",
            policy_version="policy-v1",
            authorization_ref="approval-fixture-only",
            created_at=NOW,
            valid_until=NOW + timedelta(minutes=5),
        )
        self.key = self.item["idempotency_key"]
        self.outbox.claim_next("worker-fixture", now=NOW, lease_seconds=60)

    def tearDown(self):
        self.store.close()
        self.root.cleanup()

    def _dispatch(self, adapter):
        return self.outbox.dispatch_claimed(
            self.key,
            worker_id="worker-fixture",
            authorize=fixture_authority(self.scope),
            adapter=adapter,
            now=NOW + timedelta(seconds=1),
        )

    def test_unverified_positive_from_send_must_not_record_real_effect(self):
        """Caller-forged positive must never reach an unenrolled sender."""
        adapter = ClaimsConfirmedWithoutProducer()
        with self.assertRaisesRegex(
            PermissionError, "^INDEPENDENT_PRODUCER_NOT_ENROLLED$",
        ):
            self._dispatch(adapter)
        row = self.outbox.get(self.key)
        self.assertEqual(row["state"], "BLOCKED_PRODUCER")
        self.assertEqual(row["last_error"], "INDEPENDENT_PRODUCER_NOT_ENROLLED")
        self.assertEqual(adapter.calls, 0)
        self.assertEqual(adapter.real_effects, 0)
        self.assertEqual(self.outbox.effect_count(), 0)
        self.assertIsNone(self.outbox.claim_next(
            "worker-fake-issuer", now=NOW + timedelta(seconds=2),
        ))

    def test_unverified_positive_from_reconcile_must_not_record_real_effect(self):
        """Historical uncertain state cannot use an untrusted reconciler."""
        adapter = ClaimsReconciledWithoutProducer()
        self._stage_uncertain_readback_without_producer()
        before = self.outbox.get(self.key)
        with self.assertRaisesRegex(
            PermissionError, "^INDEPENDENT_PRODUCER_NOT_ENROLLED$",
        ):
            self.outbox.reconcile(
                self.key, adapter=adapter,
                authorize=fixture_authority(self.scope),
                now=NOW + timedelta(seconds=2),
            )
        self.assertEqual(self.outbox.get(self.key), before)
        self.assertEqual(adapter.send_calls, 0)
        self.assertEqual(adapter.reconcile_calls, 0)
        self.assertEqual(adapter.real_effects, 0)
        self.assertEqual(self.outbox.effect_count(), 0)
        self.assertIsNone(self.outbox.claim_next(
            "worker-no-positive", now=NOW + timedelta(seconds=3),
        ))

    def test_existing_unverified_negative_remains_quarantined(self):
        """Even a benign-looking negative return cannot be consulted pre-enrollment."""
        adapter = RejectsWithoutProducer()
        with self.assertRaisesRegex(
            PermissionError, "^INDEPENDENT_PRODUCER_NOT_ENROLLED$",
        ):
            self._dispatch(adapter)
        row = self.outbox.get(self.key)
        self.assertEqual(row["state"], "BLOCKED_PRODUCER")
        self.assertEqual(row["last_error"], "INDEPENDENT_PRODUCER_NOT_ENROLLED")
        self.assertEqual(adapter.calls, 0)
        self.assertEqual(self.outbox.effect_count(), 0)
        self.assertIsNone(self.outbox.claim_next(
            "worker-negative", now=NOW + timedelta(seconds=2),
        ))

    def test_private_confirm_is_closed_without_independent_producer_receipt(self):
        """No Python-private method is a replacement for producer-origin proof."""
        adapter = ClaimsReconciledWithoutProducer()
        first = self.outbox.get(self.key)
        self.assertEqual(first["state"], "CLAIMED")
        with self.assertRaisesRegex(
            PermissionError, "^INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED$",
        ):
            self.outbox._confirm(
                self.key, expected=first,
                effect_ref="CALLER-INVENTED",
                confirmed_at=NOW + timedelta(seconds=1),
            )
        self.assertEqual(self.outbox.get(self.key), first)
        with self.assertRaisesRegex(
            PermissionError, "^INDEPENDENT_PRODUCER_NOT_ENROLLED$",
        ):
            self._dispatch(adapter)
        blocked = self.outbox.get(self.key)
        self.assertEqual(blocked["state"], "BLOCKED_PRODUCER")
        with self.assertRaisesRegex(
            PermissionError, "^INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED$",
        ):
            self.outbox._confirm(
                self.key, expected=blocked,
                effect_ref="CALLER-SECOND-INVENTED",
                confirmed_at=NOW + timedelta(seconds=2),
            )
        self.assertEqual(self.outbox.get(self.key), blocked)
        self.assertEqual(adapter.send_calls, 0)
        self.assertEqual(adapter.reconcile_calls, 0)
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_no_enrolled_producer_must_block_before_adapter_send(self):
        """A.26 RED: no independent issuer/producer enrollment exists.

        Reaching send is a potential real external effect, even if CONFIRMED
        admission has been disabled. This assertion is a security contract,
        NOT a fixture permission or an A.12/A.16 original test.
        """
        adapter = ClaimsConfirmedWithoutProducer()
        with self.assertRaisesRegex(
            PermissionError, "INDEPENDENT_PRODUCER_NOT_ENROLLED",
        ):
            self._dispatch(adapter)
        self.assertEqual(
            adapter.calls, 0,
            "the external send callback must never run without producer enrollment",
        )
        self.assertEqual(self.outbox.effect_count(), 0)
        self.assertEqual(self.outbox.get(self.key)["state"], "BLOCKED_PRODUCER")

    def test_self_attested_adapter_enrollment_cannot_enable_send(self):
        """A.27: adapter-provided enrollment metadata confers no authority."""
        class FakeEnrolledAdapter:
            producer_enrolled = True
            issuer_id = "CALLER_SELF_ATTESTED_NOT_PINNED"
            trusted = True
            signed_receipt = "CALLER_FORGED_NOT_VERIFIED"
            def __init__(self):
                self.calls = 0
            def send(self, _decision, _key):
                self.calls += 1
                raise AssertionError("untrusted adapter must not reach send")
        adapter = FakeEnrolledAdapter()
        with self.assertRaisesRegex(
            PermissionError, "INDEPENDENT_PRODUCER_NOT_ENROLLED",
        ):
            self._dispatch(adapter)
        self.assertEqual(adapter.calls, 0)
        self.assertEqual(self.outbox.get(self.key)["state"], "BLOCKED_PRODUCER")
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_pre_send_gate_rejects_before_accessing_adapter_descriptor(self):
        """A.27: even a dynamic send property may have dangerous side effects."""
        class DangerousDescriptor:
            def __init__(self):
                self.property_reads = 0
                self.calls = 0
            @property
            def send(self):
                self.property_reads += 1
                raise AssertionError("send property must not be evaluated")
        adapter = DangerousDescriptor()
        with self.assertRaisesRegex(
            PermissionError, "INDEPENDENT_PRODUCER_NOT_ENROLLED",
        ):
            self._dispatch(adapter)
        self.assertEqual(adapter.property_reads, 0)
        self.assertEqual(adapter.calls, 0)
        self.assertEqual(self.outbox.get(self.key)["state"], "BLOCKED_PRODUCER")
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_fake_positive_cannot_release_followup_same_aggregate(self):
        """Fake positive must neither send nor release dependent FIFO action."""
        later = self.outbox.enqueue(
            intent_ref="intent-second-after-forged-positive",
            action="send_email",
            payload={"fixture": "second never dispatched"},
            aggregate_key="client-false-positive-A21",
            policy_version="policy-v1",
            authorization_ref="approval-fixture-only",
            created_at=NOW + timedelta(seconds=1),
            valid_until=NOW + timedelta(minutes=5),
        )
        adapter = ClaimsConfirmedWithoutProducer()
        with self.assertRaisesRegex(
            PermissionError, "^INDEPENDENT_PRODUCER_NOT_ENROLLED$",
        ):
            self._dispatch(adapter)
        self.assertEqual(self.outbox.get(self.key)["state"], "BLOCKED_PRODUCER")
        self.assertEqual(adapter.calls, 0)
        self.assertEqual(adapter.real_effects, 0)
        self.assertIsNone(self.outbox.claim_next(
            "worker-followup", now=NOW + timedelta(seconds=2),
        ))
        self.assertEqual(
            self.outbox.get(later["idempotency_key"])["state"], "PENDING",
        )
        self.assertEqual(self.outbox.effect_count(), 0)

    def _stage_uncertain_readback_without_producer(self):
        """TEST-ONLY historical ambiguity; never crosses any adapter boundary."""
        before = self.outbox.get(self.key)
        self.assertEqual(before["state"], "CLAIMED")
        with self.outbox.db:
            row = self.outbox.db.execute(
                """UPDATE action_outbox
                   SET state='UNCERTAIN',lease_owner='',lease_until='',
                       last_error='A32_TEST_ONLY_UNKNOWN_SOURCE'
                   WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?
                     AND state='CLAIMED' AND lease_owner=? AND lease_until=?
                     AND NOT EXISTS (
                         SELECT 1 FROM action_effects e
                         WHERE e.idempotency_key=action_outbox.idempotency_key
                           AND e.owner=action_outbox.owner
                           AND e.tenant=action_outbox.tenant
                           AND e.workspace=action_outbox.workspace
                     )""",
                (self.key, self.scope.owner_id, self.scope.tenant_id,
                 self.scope.workspace_id, before["lease_owner"], before["lease_until"]),
            )
            self.assertEqual(row.rowcount, 1)
        self.assertEqual(self.outbox.get(self.key)["state"], "UNCERTAIN")
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_unenrolled_reconcile_must_not_access_dynamic_adapter_descriptor(self):
        """A.32 RED: a malicious reconcile property can itself create effects."""
        self._stage_uncertain_readback_without_producer()

        class DangerousReconcileAttribute:
            def __init__(self):
                self.property_reads = 0

            @property
            def reconcile(self):
                self.property_reads += 1
                raise AssertionError("untrusted descriptor evaluated before enrollment")

        adapter = DangerousReconcileAttribute()
        with self.assertRaisesRegex(
            PermissionError, "INDEPENDENT_PRODUCER_NOT_ENROLLED",
        ):
            self.outbox.reconcile(
                self.key, adapter=adapter,
                authorize=fixture_authority(self.scope),
                now=NOW + timedelta(seconds=2),
            )
        self.assertEqual(adapter.property_reads, 0)
        self.assertEqual(self.outbox.get(self.key)["state"], "UNCERTAIN")
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_unenrolled_reconcile_must_not_invoke_side_effecting_callback(self):
        """A.32 RED: reconcile callback is not a trusted read-only operation."""
        self._stage_uncertain_readback_without_producer()

        class DangerousReconcileCallable:
            def __init__(self):
                self.reconcile_calls = 0

            def reconcile(self, _key, _decision):
                self.reconcile_calls += 1
                return {"found": True, "confirmed": True, "effect_ref": "FORGED"}

        adapter = DangerousReconcileCallable()
        with self.assertRaisesRegex(
            PermissionError, "INDEPENDENT_PRODUCER_NOT_ENROLLED",
        ):
            self.outbox.reconcile(
                self.key, adapter=adapter,
                authorize=fixture_authority(self.scope),
                now=NOW + timedelta(seconds=2),
            )
        self.assertEqual(adapter.reconcile_calls, 0)
        self.assertEqual(self.outbox.get(self.key)["state"], "UNCERTAIN")
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_unenrolled_block_survives_lease_expiry_and_store_reopen(self):
        """A.31: denied intents must never churn CLAIMED/RETRY across restarts."""
        adapter = ClaimsConfirmedWithoutProducer()
        with self.assertRaisesRegex(
            PermissionError, "INDEPENDENT_PRODUCER_NOT_ENROLLED",
        ):
            self._dispatch(adapter)
        before = self.outbox.get(self.key)
        self.assertEqual(before["state"], "BLOCKED_PRODUCER")
        self.assertEqual(before["attempts"], 1)
        self.assertEqual(before["lease_owner"], "")
        self.assertEqual(before["lease_until"], "")
        self.assertEqual(before["last_error"], "INDEPENDENT_PRODUCER_NOT_ENROLLED")
        self.assertEqual(self.outbox.effect_count(), 0)
        self.assertEqual(adapter.calls, 0)

        self.assertEqual(
            self.outbox.release_expired_claims(now=NOW + timedelta(days=1)), 0,
        )
        self.assertIsNone(
            self.outbox.claim_next("other-worker", now=NOW + timedelta(days=1)),
        )
        reopened = SQLiteChatStore(Path(self.root.name) / "chat.sqlite3")
        try:
            another = ExecutionOutbox(reopened, self.scope)
            persisted = another.get(self.key)
            self.assertEqual(persisted["state"], "BLOCKED_PRODUCER")
            self.assertEqual(persisted["attempts"], 1)
            self.assertIsNone(
                another.claim_next("worker-after-restart", now=NOW + timedelta(days=2)),
            )
        finally:
            reopened.close()
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_block_keeps_same_aggregate_fifo_but_not_unrelated_work(self):
        """A.31: no hidden terminal release; independently ordered work survives."""
        same = self.outbox.enqueue(
            intent_ref="intent-followup-must-not-overtake",
            action="send_email",
            payload={"fixture": "same aggregate still blocked"},
            aggregate_key="client-false-positive-A21",
            policy_version="policy-v1",
            authorization_ref="approval-fixture-only",
            created_at=NOW + timedelta(seconds=1),
            valid_until=NOW + timedelta(minutes=5),
        )
        other = self.outbox.enqueue(
            intent_ref="intent-independent-aggregate",
            action="send_email",
            payload={"fixture": "unrelated aggregate"},
            aggregate_key="other-client",
            policy_version="policy-v1",
            authorization_ref="approval-fixture-only",
            created_at=NOW + timedelta(seconds=2),
            valid_until=NOW + timedelta(minutes=5),
        )
        adapter = ClaimsConfirmedWithoutProducer()
        with self.assertRaisesRegex(
            PermissionError, "INDEPENDENT_PRODUCER_NOT_ENROLLED",
        ):
            self._dispatch(adapter)
        self.assertEqual(adapter.calls, 0)
        self.assertEqual(self.outbox.get(self.key)["state"], "BLOCKED_PRODUCER")
        claimed = self.outbox.claim_next(
            "other-worker", now=NOW + timedelta(seconds=4),
        )
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["idempotency_key"], other["idempotency_key"])
        self.assertEqual(self.outbox.get(same["idempotency_key"])["state"], "PENDING")
        self.assertEqual(self.outbox.effect_count(), 0)


if __name__ == "__main__":
    unittest.main()
