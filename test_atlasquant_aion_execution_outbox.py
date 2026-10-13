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
            self.assertEqual(reconciled["state"], "UNCERTAIN")
            self.assertEqual(
                reconciled["reconcile_state"], "INDEPENDENT_POSITIVE_PROOF_REQUIRED",
            )
            self.assertEqual(adapter.send_calls, 1)
            self.assertEqual(outbox.effect_count(), 0)
            self.assertIsNone(
                outbox.claim_next("worker-2", now=NOW + timedelta(seconds=4))
            )
            store.close()

    def test_unverified_absence_never_allows_retry_even_if_fixture_knows_no_effect(self):
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

            # Fixture knowledge is not an authenticated receipt from a real
            # external producer. The adapter's bool cannot reopen the action.
            retry = outbox.reconcile(
                item["idempotency_key"],
                adapter=adapter,
                authorize=policy(self.scope),
                now=NOW + timedelta(seconds=2),
            )
            self.assertEqual(retry["state"], "UNCERTAIN")
            self.assertEqual(retry["reconcile_state"], "INDEPENDENT_ABSENCE_PROOF_REQUIRED")
            self.assertIsNone(outbox.claim_next(
                "worker-2", now=NOW + timedelta(seconds=3), lease_seconds=60,
            ))
            self.assertEqual(adapter.send_calls, 1)
            self.assertEqual(outbox.effect_count(), 0)
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
            self.assertEqual(outbox.get(first["idempotency_key"])["state"], "UNCERTAIN")
            self.assertIsNone(outbox.claim_next(
                "worker-2",
                now=NOW + timedelta(seconds=3),
                lease_seconds=60,
            ))
            self.assertEqual(outbox.get(second["idempotency_key"])["state"], "PENDING")
            self.assertEqual(outbox.effect_count(), 0)
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
            self.assertEqual(confirmed["state"], "SENT")
            self.assertEqual(
                confirmed["reconcile_state"], "INDEPENDENT_POSITIVE_PROOF_REQUIRED",
            )
            self.assertEqual(adapter.send_calls, 1)
            self.assertEqual(outbox.effect_count(), 0)
            self.assertIsNone(
                outbox.claim_next("worker-2", now=NOW + timedelta(seconds=4))
            )
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
        root, store, outbox, item = self.fixture()
        try:
            adapter = FakeIdempotentAdapter()
            result = outbox.dispatch_claimed(
                item["idempotency_key"], worker_id="worker-1",
                authorize=policy(self.scope), adapter=adapter,
                now=NOW + timedelta(seconds=1),
            )
            self.assertEqual(result["state"], "UNCERTAIN")
            self.assertEqual(result["dispatch_state"], "UNCERTAIN_PROOF_REQUIRED")
            self.assertEqual(result["last_error"], "ADAPTER_POSITIVE_EFFECT_UNVERIFIED")
            self.assertEqual(adapter.send_calls, 1)
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
        sent_adapter = FakeIdempotentAdapter(mode="sent")
        sent = self.outbox.dispatch_claimed(
            self.key, worker_id="worker-1",
            authorize=policy(self.scope), adapter=sent_adapter,
            now=NOW + timedelta(seconds=1),
        )
        self.assertEqual(sent["state"], "SENT")
        outbox = self.outbox
        key = self.key

        class StaleAbsenceAdapter:
            def reconcile(self, _key, _decision):
                # Another observation wins while the old result is pending.
                _fixture_simulate_independent_positive_review(
                    outbox, key, "EFFECT-RECONCILED",
                )
                return {"found": False, "authoritative_absence": True}

        observed = self.outbox.reconcile(
            self.key, adapter=StaleAbsenceAdapter(),
            authorize=policy(self.scope, allowed=False),
            now=NOW + timedelta(seconds=3),
        )
        self.assertEqual(observed["reconcile_state"], "STALE_OBSERVATION_IGNORED")
        self.assertEqual(self.outbox.get(self.key)["state"], "CONFIRMED")
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
    """Reentrant fixture interleavings. No real provider/authoritative receipt."""

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
        self.assertEqual(self.outbox.dispatch_claimed(
            self.key, worker_id="worker-1",
            authorize=policy(self.scope), adapter=self.adapter,
            now=NOW + timedelta(seconds=1),
        )["state"], "SENT")

    def tearDown(self):
        self.store.close()
        self.tempdir.cleanup()

    def test_stale_absence_must_not_reopen_confirmed_effect(self):
        outbox, key = self.outbox, self.key

        class LateAbsence:
            def reconcile(self, _key, _decision):
                _fixture_simulate_independent_positive_review(
                    outbox, key, "EFFECT-VERIFIED",
                )
                return {"found": False, "authoritative_absence": True}

        observed = outbox.reconcile(
            key, adapter=LateAbsence(),
            authorize=policy(self.scope),
            now=NOW + timedelta(seconds=3),
        )
        self.assertEqual(observed["reconcile_state"], "STALE_OBSERVATION_IGNORED")
        self.assertEqual(outbox.get(key)["state"], "CONFIRMED")
        self.assertEqual(outbox.get(key)["effect_ref"], "EFFECT-VERIFIED")
        self.assertEqual(outbox.effect_count(), 1)
        self.assertEqual(self.adapter.send_calls, 1)

    def test_stale_absence_cannot_reopen_revoked_state(self):
        outbox, key = self.outbox, self.key

        class LateAbsence:
            def reconcile(self, _key, _decision):
                with outbox.db:
                    outbox.db.execute(
                        "UPDATE action_outbox SET state='REVOKED' "
                        "WHERE idempotency_key=?",
                        (key,),
                    )
                return {"found": False, "authoritative_absence": True}

        observed = outbox.reconcile(
            key, adapter=LateAbsence(),
            authorize=policy(self.scope),
            now=NOW + timedelta(seconds=3),
        )
        self.assertEqual(observed["reconcile_state"], "STALE_OBSERVATION_IGNORED")
        self.assertEqual(outbox.get(key)["state"], "REVOKED")
        self.assertEqual(self.adapter.send_calls, 1)

    def test_unverified_absence_cannot_invoke_authorize_or_reopen_retry(self):
        outbox, key = self.outbox, self.key

        class Absence:
            def reconcile(self, _key, _decision):
                return {"found": False, "authoritative_absence": True}

        authorize_calls = []
        def observed_authorize(_decision):
            authorize_calls.append("unexpected")
            return policy(self.scope)({})

        outcome = outbox.reconcile(
            key, adapter=Absence(), authorize=observed_authorize,
            now=NOW + timedelta(seconds=3),
        )
        self.assertEqual(outcome["state"], "SENT")
        self.assertEqual(outcome["reconcile_state"], "INDEPENDENT_ABSENCE_PROOF_REQUIRED")
        self.assertEqual(authorize_calls, [])
        self.assertEqual(outbox.get(key)["state"], "SENT")
        self.assertEqual(self.adapter.send_calls, 1)




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
                        result = outbox.dispatch_claimed(
                            first["idempotency_key"], worker_id="worker-1",
                            authorize=policy(scope), adapter=adapter,
                            now=NOW + timedelta(seconds=1),
                        )
                        self.assertEqual(result["state"], "UNCERTAIN")
                        self.assertEqual(result["dispatch_state"], "UNCERTAIN_PROOF_REQUIRED")
                        self.assertEqual(result["last_error"], "ADAPTER_REJECTION_EFFECT_UNVERIFIED")
                        self.assertEqual(adapter.send_calls, 1)
                        self.assertEqual(outbox.effect_count(), 0)
                        self.assertIsNone(outbox.claim_next(
                            "worker-2", now=NOW + timedelta(seconds=2),
                        ))
                        self.assertEqual(outbox.get(second["idempotency_key"])["state"], "PENDING")
                    finally:
                        store.close()

    def test_false_authoritative_absence_remains_quarantined(self):
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
                outbox.claim_next("worker-1", now=NOW, lease_seconds=60)

                class AdversarialAdapter:
                    send_calls = 0
                    def send(self, _decision, _key):
                        self.send_calls += 1
                        raise TimeoutError("effect may have occurred")
                    def reconcile(self, _key, _decision):
                        return {"found": False, "authoritative_absence": True}

                adapter = AdversarialAdapter()
                original = outbox.dispatch_claimed(
                    item["idempotency_key"], worker_id="worker-1",
                    authorize=policy(scope), adapter=adapter,
                    now=NOW + timedelta(seconds=1),
                )
                self.assertEqual(original["state"], "UNCERTAIN")
                observed = outbox.reconcile(
                    item["idempotency_key"], adapter=adapter,
                    authorize=policy(scope), now=NOW + timedelta(seconds=2),
                )
                self.assertEqual(observed["state"], "UNCERTAIN")
                self.assertEqual(observed["reconcile_state"], "INDEPENDENT_ABSENCE_PROOF_REQUIRED")
                self.assertIsNone(outbox.claim_next(
                    "worker-2", now=NOW + timedelta(seconds=3),
                ))
                self.assertEqual(adapter.send_calls, 1)
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
        """EXPECTED RED: caller can currently forge CONFIRMED and effect ledger."""
        adapter = ClaimsConfirmedWithoutProducer()
        result = self._dispatch(adapter)
        self.assertEqual(adapter.calls, 1)
        self.assertEqual(adapter.real_effects, 0)
        self.assertIn(
            result["state"], ("UNCERTAIN", "SENT"),
            "an adapter-supplied bool must not be admitted as producer proof",
        )
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_unverified_positive_from_reconcile_must_not_record_real_effect(self):
        """EXPECTED RED: caller can currently forge the reconciling receipt."""
        adapter = ClaimsReconciledWithoutProducer()
        sent = self._dispatch(adapter)
        self.assertEqual(sent["state"], "SENT")
        reconciled = self.outbox.reconcile(
            self.key,
            adapter=adapter,
            authorize=fixture_authority(self.scope),
            now=NOW + timedelta(seconds=2),
        )
        self.assertEqual(adapter.send_calls, 1)
        self.assertEqual(adapter.reconcile_calls, 1)
        self.assertEqual(adapter.real_effects, 0)
        self.assertIn(
            reconciled["state"], ("SENT", "UNCERTAIN"),
            "a self-attested reconciliation must not prove a real effect",
        )
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_existing_unverified_negative_remains_quarantined(self):
        """EXPECTED GREEN control: A.20 does not trust negative adapter claims."""
        adapter = RejectsWithoutProducer()
        result = self._dispatch(adapter)
        self.assertEqual(result["state"], "UNCERTAIN")
        self.assertEqual(result["dispatch_state"], "UNCERTAIN_PROOF_REQUIRED")
        self.assertEqual(adapter.calls, 1)
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_private_confirm_is_closed_without_independent_producer_receipt(self):
        """Direct calls cannot bypass the missing external trust boundary."""
        adapter = ClaimsReconciledWithoutProducer()
        sent = self._dispatch(adapter)
        self.assertEqual(sent["state"], "SENT")
        with self.assertRaisesRegex(
            PermissionError, "INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED",
        ):
            self.outbox._confirm(
                self.key, expected=self.outbox.get(self.key),
                effect_ref="CALLER-INVENTED",
                confirmed_at=NOW + timedelta(seconds=2),
            )
        self.assertEqual(self.outbox.get(self.key)["state"], "SENT")
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_fake_positive_cannot_release_followup_same_aggregate(self):
        """No next aggregate action may run on a merely asserted effect."""
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
        result = self._dispatch(ClaimsConfirmedWithoutProducer())
        self.assertEqual(result["state"], "UNCERTAIN")
        self.assertIsNone(self.outbox.claim_next(
            "worker-followup", now=NOW + timedelta(seconds=2),
        ))
        self.assertEqual(
            self.outbox.get(later["idempotency_key"])["state"], "PENDING",
        )
        self.assertEqual(self.outbox.effect_count(), 0)


if __name__ == "__main__":
    unittest.main()
