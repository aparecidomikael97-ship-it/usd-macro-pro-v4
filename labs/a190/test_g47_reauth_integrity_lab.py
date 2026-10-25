"""A190 G47: reauthorization integrity must bind to deterministic intent ID.

Disposable synthetic SQLite only. Never send, call a provider or repair history.
"""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import json
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox, _digest
from atlasquant_aion_outbox_binding_lab import binding_issue_lab, audit_binding_readonly_lab

NOW = datetime(2026, 10, 24, 18, tzinfo=timezone.utc)
SCOPE = Scope("g47-owner", "g47-tenant", "g47-space")


class G47ReauthIntegrity(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="g47-reauth-")
        self.addCleanup(temp.cleanup)
        self.dbpath = Path(temp.name) / "synthetic.sqlite3"
        self.store = SQLiteChatStore(self.dbpath)
        self.addCleanup(self.store.close)
        self.outbox = ExecutionOutbox(self.store, SCOPE)
        self.strict = ExecutionOutbox(
            self.store, SCOPE, strict_binding_integrity_lab=True
        )

    def enqueue(self, intent="test-reauth", required=True, ref="challenge-1"):
        return self.outbox.enqueue(
            intent_ref=intent, action="synthetic_no_provider",
            payload={"amount_minor": 1000},
            aggregate_key="synthetic-group", policy_version="p1",
            authorization_ref="local-auth-ref",
            created_at=NOW, valid_until=NOW+timedelta(minutes=5),
            requires_reauth=required, reauth_ref=ref,
        )

    def scope(self):
        return (SCOPE.owner_id, SCOPE.tenant_id, SCOPE.workspace_id)

    def binding(self, key):
        return binding_issue_lab(self.store.db, key, self.scope())

    def rewrite_decision(self, key, edit):
        decision_id = self.outbox.get(key)["decision_id"]
        old = self.store.db.execute(
            "SELECT data FROM action_decisions WHERE decision_id=?",
            (decision_id,),
        ).fetchone()["data"]
        doc=json.loads(old)
        edit(doc)
        self.store.db.execute(
            "UPDATE action_decisions SET data=? WHERE decision_id=?",
            (json.dumps(doc),decision_id),
        )
        self.store.db.commit()

    def test_01_genuine_required_reauth_is_structurally_bound(self):
        key=self.enqueue()["idempotency_key"]
        self.assertEqual(self.binding(key),"OK")
        print("G47_AUTH_BOUND_GREEN=ORIGINAL_DECISION_VALID")

    def test_02_downgrade_requires_reauth_refused(self):
        key=self.enqueue()["idempotency_key"]
        self.rewrite_decision(key,lambda d:d.update(requires_reauth=False))
        self.assertEqual(self.binding(key),"DECISION_REAUTH_MATERIAL_INVALID")
        print("G47_DOWNGRADE_GREEN=FALSE_CANNOT_ERASE_TRUE")

    def test_03_substitute_reauth_reference_refused(self):
        key=self.enqueue()["idempotency_key"]
        self.rewrite_decision(key,lambda d:d.update(reauth_ref="stolen-assertion"))
        self.assertEqual(self.binding(key),"DECISION_REAUTH_MATERIAL_MISMATCH")
        print("G47_REFERENCE_GREEN=CHANGED_REFERENCE_REFUSED")

    def test_04_legacy_false_empty_key_material_is_unchanged(self):
        item=self.enqueue(intent="plain",required=False,ref="")
        key=item["idempotency_key"]
        decision=self.outbox.get(key)["decision"]
        canonical={
            "scope": list(self.scope()),
            "intent_ref":decision["intent_ref"],"action":decision["action"],
            "aggregate_key":decision["aggregate_key"],
            "payload_digest":decision["payload_digest"],
            "transaction_id":"","authority_budget_ref":"",
            "risk_points":0,"capability_class":"",
        }
        self.assertEqual(key,_digest(canonical))
        self.assertEqual(self.binding(key),"OK")
        print("G47_LEGACY_PLAIN_GREEN=IDENTICAL_KEY_MATERIAL")

    def test_05_false_with_injected_reference_refused(self):
        key=self.enqueue(intent="plain",required=False,ref="")["idempotency_key"]
        self.rewrite_decision(key,lambda d:d.update(reauth_ref="foreign-claim"))
        self.assertEqual(self.binding(key),"DECISION_REAUTH_MATERIAL_INVALID")

    def test_06_nonboolean_reauth_is_invalid(self):
        key=self.enqueue()["idempotency_key"]
        self.rewrite_decision(key,lambda d:d.update(requires_reauth="false"))
        self.assertEqual(self.binding(key),"DECISION_REAUTH_MATERIAL_INVALID")
        print("G47_TYPE_GREEN=NONBOOLEAN_CANNOT_DISABLE_REAUTH")

    def test_07_nonstring_reference_is_invalid(self):
        key=self.enqueue()["idempotency_key"]
        self.rewrite_decision(key,lambda d:d.update(reauth_ref=42))
        self.assertEqual(self.binding(key),"DECISION_REAUTH_MATERIAL_INVALID")

    def test_08_same_intent_changed_reauth_ref_is_not_idempotent(self):
        self.enqueue(intent="same-intent",ref="first-challenge")
        with self.assertRaisesRegex(ValueError,"intent_ref idempotency collision"):
            self.enqueue(intent="same-intent",ref="second-challenge")
        print("G47_ALIAS_GREEN=CHANGED_REAUTH_NOT_IDEMPOTENT")

    def test_09_strict_claim_denies_downgrade_before_adapter(self):
        key=self.enqueue()["idempotency_key"]
        self.rewrite_decision(key,lambda d:d.update(requires_reauth=False))
        with self.assertRaisesRegex(RuntimeError,
                                    "G44_BINDING_INTEGRITY_DENIED:DECISION_REAUTH_MATERIAL_INVALID"):
            self.strict.claim_next("g47-worker",now=NOW,lease_seconds=60)
        self.assertEqual(self.outbox.get(key)["state"],"PENDING")
        self.assertEqual(self.outbox.effect_count(),0)
        print("G47_PRE_SEND_GREEN=ZERO_EFFECT_ZERO_ADAPTER")

    def test_10_same_full_reauth_intent_remains_idempotent(self):
        a=self.enqueue(intent="same-intent",ref="same-challenge")
        b=self.enqueue(intent="same-intent",ref="same-challenge")
        self.assertEqual(a["idempotency_key"],b["idempotency_key"])
        self.assertEqual(b["enqueue_state"],"IDEMPOTENT")
        self.assertEqual(self.binding(a["idempotency_key"]),"OK")

    def test_11_readonly_g44_audit_classifies_downgrade_without_payload(self):
        key=self.enqueue()["idempotency_key"]
        self.rewrite_decision(key,lambda d:d.update(requires_reauth=False))
        result=audit_binding_readonly_lab(
            self.dbpath,owner=SCOPE.owner_id,
            tenant=SCOPE.tenant_id,workspace=SCOPE.workspace_id,
        )
        self.assertEqual(result["counts"],{"DECISION_REAUTH_MATERIAL_INVALID":1})
        self.assertNotIn("amount_minor",json.dumps(result))

    def test_12_nonboolean_producer_requires_reauth_rejected(self):
        with self.assertRaises((TypeError,ValueError)):
            self.enqueue(intent="bad-type",required="true",ref="ref")
        self.assertEqual(self.outbox.effect_count(),0)

    def test_13_remove_both_reauth_fields_cannot_match_original_key(self):
        key=self.enqueue()["idempotency_key"]
        self.rewrite_decision(key, lambda d:d.update(
            requires_reauth=False, reauth_ref=""))
        self.assertEqual(self.binding(key),
                         "DECISION_IDEMPOTENCY_MATERIAL_MISMATCH")
        print("G47_DOUBLE_DOWNGRADE_GREEN=ORIGINAL_KEY_CANNOT_MATCH")

    def test_14_plain_decision_upgraded_without_new_key_denied(self):
        key=self.enqueue(intent="plain",required=False,ref="")["idempotency_key"]
        self.rewrite_decision(key, lambda d:d.update(
            requires_reauth=True, reauth_ref="forged-ref"))
        self.assertEqual(self.binding(key),"DECISION_REAUTH_MATERIAL_MISMATCH")

    def test_15_missing_required_flag_refused(self):
        key=self.enqueue()["idempotency_key"]
        self.rewrite_decision(key,lambda d:d.pop("requires_reauth"))
        self.assertEqual(self.binding(key),"DECISION_REAUTH_MATERIAL_INVALID")

    def test_16_changed_reauth_requirement_same_intent_collision(self):
        self.enqueue(intent="same-intent",required=True,ref="r1")
        with self.assertRaisesRegex(ValueError,"intent_ref idempotency collision"):
            self.enqueue(intent="same-intent",required=False,ref="")

    def test_17_producer_false_nonempty_reference_denied(self):
        with self.assertRaisesRegex(ValueError,"reauth_ref without"):
            self.enqueue(intent="bad-false",required=False,ref="unneeded")
        self.assertEqual(self.outbox.effect_count(),0)

    def test_18_producer_nonstring_reference_denied(self):
        with self.assertRaises(TypeError):
            self.enqueue(intent="bad-reference",required=True,ref=1000)


if __name__ == "__main__":
    unittest.main()
