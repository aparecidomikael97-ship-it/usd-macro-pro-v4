"""A190 G48 RED->GREEN: reused Outbox intents must not launder altered reauth.

Disposable synthetic SQLite only. No Worker, provider, network send or
automatic transaction repair. A valid LOCAL hash is not owner authentication.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

NOW = datetime(2026, 10, 24, 19, tzinfo=timezone.utc)
SCOPE = Scope("g48-owner", "g48-tenant", "g48-space")


class G48ReuseReauthorization(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="g48-reuse-")
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "synthetic.sqlite3"
        self.store = SQLiteChatStore(self.path)
        self.addCleanup(self.store.close)
        self.outbox = ExecutionOutbox(self.store, SCOPE)
        self.strict = ExecutionOutbox(
            self.store, SCOPE, strict_binding_integrity_lab=True
        )

    def enqueue(self, engine=None, *, intent="g48-request", required=True,
                ref="g48-challenge"):
        return (engine or self.outbox).enqueue(
            intent_ref=intent,
            action="synthetic_no_provider",
            payload={"amount_minor": 1000},
            aggregate_key="g48-aggregate",
            policy_version="p1",
            authorization_ref="g48-authorization",
            created_at=NOW,
            valid_until=NOW + timedelta(minutes=5),
            requires_reauth=required,
            reauth_ref=ref,
        )

    def tamper(self, key, edit):
        decision_id = self.outbox.get(key)["decision_id"]
        old = self.store.db.execute(
            "SELECT data FROM action_decisions WHERE decision_id=?",
            (decision_id,),
        ).fetchone()[0]
        document = json.loads(old)
        edit(document)
        self.store.db.execute(
            "UPDATE action_decisions SET data=? WHERE decision_id=?",
            (json.dumps(document), decision_id),
        )
        self.store.db.commit()

    def assert_reuse_denied(self, engine, *, marker):
        with self.assertRaisesRegex(
            RuntimeError, "G48_EXISTING_BINDING_DENIED:" + marker
        ):
            self.enqueue(engine)
        self.assertEqual(self.outbox.effect_count(), 0)

    def authorize(self, _, *, reauth=False, ref=""):
        return {
            "allowed": True, "actor_id": SCOPE.owner_id,
            "tenant_id": SCOPE.tenant_id,
            "workspace_id": SCOPE.workspace_id,
            "policy_version": "p1",
            "authorization_ref": "g48-authorization",
            "reauthenticated": reauth,
            "reauth_ref": ref,
        }

    def test_01_genuine_reuse_keeps_same_key(self):
        a = self.enqueue()
        b = self.enqueue(self.strict)
        self.assertEqual(a["idempotency_key"], b["idempotency_key"])
        self.assertEqual(b["enqueue_state"], "IDEMPOTENT")
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_02_strict_reuse_denies_true_to_false(self):
        key = self.enqueue()["idempotency_key"]
        self.tamper(key, lambda d: d.update(requires_reauth=False))
        self.assert_reuse_denied(
            self.strict, marker="DECISION_REAUTH_MATERIAL_INVALID"
        )
        print("G48_STRICT_REUSE_GREEN=NO_TAMPERED_IDEMPOTENT")

    def test_03_ordinary_reuse_denies_true_to_false(self):
        key = self.enqueue()["idempotency_key"]
        self.tamper(key, lambda d: d.update(requires_reauth=False))
        self.assert_reuse_denied(
            self.outbox, marker="DECISION_REAUTH_MATERIAL_INVALID"
        )

    def test_04_reuse_denies_double_downgrade(self):
        key = self.enqueue()["idempotency_key"]
        self.tamper(key, lambda d: d.update(
            requires_reauth=False, reauth_ref=""
        ))
        self.assert_reuse_denied(
            self.strict, marker="DECISION_IDEMPOTENCY_MATERIAL_MISMATCH"
        )
        print("G48_DOUBLE_DOWNGRADE_GREEN=NO_TAMPERED_REUSE")

    def test_05_reuse_denies_changed_reference(self):
        key = self.enqueue()["idempotency_key"]
        self.tamper(key, lambda d: d.update(reauth_ref="foreign-challenge"))
        self.assert_reuse_denied(
            self.strict, marker="DECISION_REAUTH_MATERIAL_MISMATCH"
        )

    def test_06_reuse_denies_integer_as_boolean(self):
        key = self.enqueue()["idempotency_key"]
        self.tamper(key, lambda d: d.update(requires_reauth=1))
        self.assert_reuse_denied(
            self.strict, marker="DECISION_REAUTH_MATERIAL_INVALID"
        )

    def test_07_reuse_denies_missing_reauth_flag(self):
        key = self.enqueue()["idempotency_key"]
        self.tamper(key, lambda d: d.pop("requires_reauth"))
        self.assert_reuse_denied(
            self.strict, marker="DECISION_REAUTH_MATERIAL_INVALID"
        )

    def test_08_auth_gate_denies_nonboolean_not_silent_false(self):
        intent = self.enqueue()
        decision = dict(intent["decision"])
        decision["requires_reauth"] = "false"
        result = self.outbox._authorization_gate(
            {"decision":decision},
            lambda d:self.authorize(d), NOW+timedelta(seconds=1),
        )
        self.assertEqual(result[:2], (False, "BLOCKED_REAPPROVAL"))
        self.assertEqual(result[2]["reason"], "REAUTH_MATERIAL_INVALID")
        print("G48_GATE_TYPE_GREEN=NO_NONBOOL_BYPASS")

    def test_09_auth_gate_denies_false_with_reference(self):
        intent = self.enqueue(required=False,ref="")
        decision = dict(intent["decision"])
        decision["reauth_ref"] = "injected-reference"
        result = self.outbox._authorization_gate(
            {"decision":decision},
            lambda d:self.authorize(d),NOW+timedelta(seconds=1),
        )
        self.assertEqual(result[:2], (False, "BLOCKED_REAPPROVAL"))
        self.assertEqual(result[2]["reason"], "REAUTH_MATERIAL_INVALID")

    def test_10_valid_required_reauth_allows_only_matching_callback(self):
        intent=self.enqueue()
        r=self.outbox._authorization_gate(
            {"decision":intent["decision"]},
            lambda d:self.authorize(d,reauth=True,ref="g48-challenge"),
            NOW+timedelta(seconds=1),
        )
        self.assertEqual(r[:2], (True, "ALLOW"))
        r2=self.outbox._authorization_gate(
            {"decision":intent["decision"]},
            lambda d:self.authorize(d,reauth=False),
            NOW+timedelta(seconds=1),
        )
        self.assertEqual(r2[:2], (False, "BLOCKED_REAPPROVAL"))

    def test_11_plain_false_empty_stays_compatible(self):
        intent=self.enqueue(required=False,ref="")
        r=self.outbox._authorization_gate(
            {"decision":intent["decision"]},
            lambda d:self.authorize(d),
            NOW+timedelta(seconds=1),
        )
        self.assertEqual(r[:2], (True, "ALLOW"))


if __name__=="__main__":
    unittest.main()
