"""V16-A.14 negative scope-binding regressions, staged only.

Proves the Outbox authorization callback must echo the exact tenant and
workspace; it does not attest the callback's issuer, HUMAN_OWNER or hardware.
No provider, network, secrets, Worker, Render or deployment is used.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

NOW = datetime(2026, 10, 13, 13, 0, tzinfo=timezone.utc)


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


if __name__ == "__main__":
    unittest.main()
