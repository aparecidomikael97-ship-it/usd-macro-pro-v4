"""RED-FIRST: Outbox get/list must never publish incoherent decision JSON.

The real local SQLite outbox already checks canonical decision data on
claim_next, but read projections currently emit the unverified serialized
decision. This is a LOCAL corruption test, not proof of external receipt,
remote attack, or a permission to dispatch. An invalid row must be reported
as suspicious instead of silently hidden as an empty list/no-effect.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

NOW = datetime(2026, 10, 21, 16, 0, tzinfo=timezone.utc)
SCOPE = Scope("owner-lab", "tenant-lab", "workspace-lab")
DENY = "OUTBOX_LOCAL_DECISION_INTEGRITY_MISMATCH"


class OutboxReadIntegrityHardstopLab(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix="aion-outbox-read-integrity-")
        self.addCleanup(tmp.cleanup)
        self.store=SQLiteChatStore(Path(tmp.name)/"test.sqlite3")
        self.addCleanup(self.store.close)
        self.db=self.store.db
        self.outbox=ExecutionOutbox(self.store,SCOPE)
        self.intent=self._enqueue("one")
        self.key=self.intent["idempotency_key"]

    def _enqueue(self, label):
        return self.outbox.enqueue(
            intent_ref="intent-"+label, action="stage_only",
            payload={"label":label,"test_only":True},
            aggregate_key="aggregate-"+label, policy_version="lab-policy",
            authorization_ref="local-lab-only-not-authority",
            created_at=NOW, valid_until=NOW+timedelta(minutes=5),
        )

    def _raw(self, key=None):
        key=self.key if key is None else key
        return self.db.execute(
            "SELECT d.data FROM action_decisions d JOIN action_outbox o "
            "ON o.decision_id=d.decision_id WHERE o.idempotency_key=?",
            (key,),
        ).fetchone()[0]

    def _alter_data(self, modifier, *, key=None):
        key=self.key if key is None else key
        original=self._raw(key)
        record=json.loads(original)
        raw=modifier(original,record)
        with self.db:
            self.db.execute(
                "UPDATE action_decisions SET data=? WHERE decision_id=("
                "SELECT decision_id FROM action_outbox WHERE idempotency_key=?)",
                (raw,key),
            )

    def _field(self, name, value):
        def changer(_raw,record):
            record[name]=value
            return json.dumps(record,sort_keys=True,separators=(",",":"),ensure_ascii=False)
        self._alter_data(changer)

    def _alter_column(self,name,value):
        if name not in ("action","payload_digest","authorization_ref","valid_until"):
            raise AssertionError("test column not allowlisted")
        with self.db:
            self.db.execute(
                "UPDATE action_decisions SET "+name+"=? WHERE decision_id=("
                "SELECT decision_id FROM action_outbox WHERE idempotency_key=?)",
                (value,self.key),
            )

    def _denied_both(self, *, assert_no_claim=True):
        before=tuple(self.db.iterdump())
        with self.assertRaisesRegex(PermissionError,DENY):
            self.outbox.get(self.key)
        with self.assertRaisesRegex(PermissionError,DENY):
            self.outbox.list()
        with self.assertRaisesRegex(PermissionError,DENY):
            self.outbox.list(state="PENDING")
        self.assertEqual(before,tuple(self.db.iterdump()))
        self.assertEqual(self.outbox.effect_count(),0)
        if assert_no_claim:
            self.assertIsNone(self.outbox.claim_next("lab-worker",now=NOW))

    def test_01_healthy_local_read_projections_unchanged(self):
        self.assertEqual(self.outbox.get(self.key)["decision"]["payload"]["label"],"one")
        self.assertEqual(len(self.outbox.list()),1)
        self.assertEqual(len(self.outbox.list(state="PENDING")),1)
        self.assertEqual(self.outbox.effect_count(),0)

    def test_02_forged_grants_authority_true_is_rejected(self):
        self._field("grants_authority",True)
        self._denied_both()

    def test_03_decision_payload_mismatch_is_rejected(self):
        obj=json.loads(self._raw())
        obj["payload"]={"label":"forged","test_only":True}
        self._alter_data(lambda _raw,_record:json.dumps(obj,sort_keys=True,separators=(",",":")))
        self._denied_both()

    def test_04_wrong_decision_id_is_rejected(self):
        self._field("decision_id","DEC-MALICIOUS")
        self._denied_both()

    def test_05_changed_owner_claim_is_rejected(self):
        self._field("owner_id","other-owner")
        self._denied_both()

    def test_06_changed_tenant_claim_is_rejected(self):
        self._field("tenant_id","other-tenant")
        self._denied_both()

    def test_07_changed_workspace_claim_is_rejected(self):
        self._field("workspace_id","other-workspace")
        self._denied_both()

    def test_08_changed_policy_version_is_rejected(self):
        self._field("policy_version","replaced-policy")
        self._denied_both()

    def test_09_changed_authorization_ref_is_rejected(self):
        self._field("authorization_ref","fake-approval")
        self._denied_both()

    def test_10_changed_valid_until_is_rejected(self):
        self._field("valid_until","2099-01-01T00:00:00+00:00")
        self._denied_both()

    def test_11_changed_idempotency_material_is_rejected(self):
        self._field("transaction_id","fake-transaction")
        self._denied_both()

    def test_12_changed_action_column_is_rejected(self):
        self._alter_column("action","untrusted-action")
        self._denied_both()

    def test_13_changed_payload_digest_column_is_rejected(self):
        self._alter_column("payload_digest","0"*64)
        self._denied_both()

    def test_14_changed_authorization_column_is_rejected(self):
        self._alter_column("authorization_ref","column-fake-approval")
        self._denied_both()

    def test_15_changed_deadline_column_is_rejected(self):
        self._alter_column("valid_until","2099-01-01T00:00:00+00:00")
        self._denied_both()

    def test_16_malformed_json_is_denied_without_parser_exception(self):
        self._alter_data(lambda _raw,_record:'{"bad":')
        self._denied_both()

    def test_17_json_array_is_denied(self):
        self._alter_data(lambda _raw,_record:"[]")
        self._denied_both()

    def test_18_noncanonical_whitespace_is_denied(self):
        self._alter_data(lambda raw,_record:" "+raw)
        self._denied_both()

    def test_19_duplicate_json_keys_are_denied(self):
        self._alter_data(lambda raw,_record:raw[:-1]+',"grants_authority":true}')
        self._denied_both()

    def test_20_one_corrupt_row_cannot_be_hidden_by_another_healthy_row(self):
        second=self._enqueue("two")
        self.assertEqual(len(self.outbox.list()),2)
        self._field("grants_authority",True)
        # A second independent, healthy aggregate may still be locally
        # claimable; integrity of list() does not imply disabling it.
        self._denied_both(assert_no_claim=False)
        self.assertEqual(self.outbox.get(second["idempotency_key"])["decision"]["payload"]["label"],"two")

    def test_21_invalid_row_is_not_misreported_as_no_effect(self):
        self._field("grants_authority",True)
        with self.assertRaisesRegex(PermissionError,DENY):
            self.outbox.list()
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM action_outbox").fetchone()[0],1)
        self.assertEqual(self.outbox.effect_count(),0)

    def test_22_missing_key_still_raises_lookup_error(self):
        with self.assertRaises(LookupError):
            self.outbox.get("f"*64)

    def test_23_read_only_healthy_result_preserves_store(self):
        before=tuple(self.db.iterdump())
        self.outbox.get(self.key)
        self.outbox.list()
        self.assertEqual(before,tuple(self.db.iterdump()))

    def test_24_local_claim_does_not_authorize_provider_on_healthy_row(self):
        claimed=self.outbox.claim_next("lab-worker",now=NOW)
        self.assertEqual(claimed["state"],"CLAIMED")
        self.assertFalse(claimed["executes_action"])
        self.assertEqual(self.outbox.effect_count(),0)


if __name__ == "__main__":
    unittest.main()
