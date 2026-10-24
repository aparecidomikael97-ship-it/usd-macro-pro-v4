"""G44: integrity contract of real Outbox/Decision/Effect on disposable SQLite.

G44 tests structural local bindings, NOT authenticated provider/commercial
event truth. No external SEND, Worker, customer data, keys or spending.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from hashlib import sha256
import json
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox
from atlasquant_aion_outbox_binding_lab import binding_issue_lab, audit_binding_readonly_lab

NOW=datetime(2026,10,24,16,tzinfo=timezone.utc)
SCOPE=Scope("g44-owner","g44-tenant","g44-space")
WORKER="g44-worker"

class NoExternalAdapter:
    def __init__(self):self.reads=0
    @property
    def send(self):
        self.reads+=1
        raise AssertionError("G44_NO_EXTERNAL_SEND")
    @property
    def reconcile(self):
        self.reads+=1
        raise AssertionError("G44_NO_EXTERNAL_RECONCILE")

class G44BindingIntegrity(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix="g44-binding-")
        self.addCleanup(temp.cleanup)
        self.file=Path(temp.name)/"outbox.sqlite3"
        self.store=SQLiteChatStore(self.file)
        self.addCleanup(lambda:self.store.close())
        self.base=ExecutionOutbox(self.store,SCOPE)
        self.strict=ExecutionOutbox(self.store,SCOPE,strict_binding_integrity_lab=True)
        row=self.base.enqueue(intent_ref="synthetic-order-42",action="synthetic_no_provider",
            payload={"amount_minor":1000,"business_event_id":"synthetic-commercial-event"},
            aggregate_key="synthetic-group",policy_version="p1",
            authorization_ref="auth1",created_at=NOW,
            valid_until=NOW+timedelta(minutes=5))
        self.key=row["idempotency_key"]
        self.trap=NoExternalAdapter()

    def binding(self,key=None):
        return binding_issue_lab(self.store.db,key or self.key,
            (SCOPE.owner_id,SCOPE.tenant_id,SCOPE.workspace_id))

    def audit(self):
        return audit_binding_readonly_lab(self.file,
            owner=SCOPE.owner_id,tenant=SCOPE.tenant_id,workspace=SCOPE.workspace_id)

    def mutate(self,table,expr,params=(),where=""):
        if not where:
            where="idempotency_key=?" if table!="action_decisions" else "decision_id=?"
        key=self.key if table!="action_decisions" else self.base.get(self.key)["decision_id"]
        self.store.db.execute(f"UPDATE {table} SET {expr} WHERE {where}",(*params,key))
        self.store.db.commit()

    def decision(self):
        return self.store.db.execute(
            "SELECT data FROM action_decisions WHERE decision_id=?",
            (self.base.get(self.key)["decision_id"],)).fetchone()[0]

    def with_claim(self):
        claimed=self.base.claim_next(WORKER,now=NOW,lease_seconds=60)
        self.assertIsNotNone(claimed)
        return claimed

    def authorize(self,_):
        return {"allowed":True,"actor_id":SCOPE.owner_id,
                "tenant_id":SCOPE.tenant_id,"workspace_id":SCOPE.workspace_id,
                "policy_version":"p1","authorization_ref":"auth1"}

    def confirm_synthetic(self):
        return self.base._confirm(self.key,effect_ref="synthetic-local-effect",
            confirmed_at=NOW+timedelta(seconds=2),
            result={"proof":"UNTRUSTED_LOCAL_LAB"})

    def test_01_fresh_binding_matches_derived_key_and_digest(self):
        self.assertEqual(self.binding(),"OK")
        self.assertEqual(self.audit()["counts"],{"OK":1})
        print("G44_DECISION_BINDING_GREEN=SCOPED_HASH_AND_JSON_MATCH")

    def test_02_different_scope_has_no_scoped_rows(self):
        report=audit_binding_readonly_lab(self.file,owner=SCOPE.owner_id,
            tenant=SCOPE.tenant_id,workspace="other-space")
        self.assertEqual(report["rows"],0)
        self.assertEqual(report["findings"],[])
        self.assertNotIn("synthetic-commercial-event",json.dumps(report))

    def test_03_foreign_decision_scope_denied_with_no_leak(self):
        self.mutate("action_decisions","owner='another-owner'")
        self.assertEqual(self.binding(),"DECISION_SCOPE_MISMATCH")
        self.assertEqual(self.strict.list(),[])
        with self.assertRaises(LookupError):
            self.strict.get(self.key)
        self.assertEqual(self.audit()["counts"],{"DECISION_SCOPE_MISMATCH":1})
        print("G44_FOREIGN_SCOPE_GREEN=CROSS_OWNER_DECISION_NOT_EXPOSED")

    def test_04_foreign_workspace_of_decision_denied(self):
        self.mutate("action_decisions","workspace='other'")
        self.assertEqual(self.binding(),"DECISION_SCOPE_MISMATCH")
        self.assertEqual(self.strict.list(),[])

    def test_05_forged_decision_json_owner_denied(self):
        doc=json.loads(self.decision())
        doc["owner_id"]="invented-owner"
        self.mutate("action_decisions","data=?",(json.dumps(doc),))
        self.assertEqual(self.binding(),"DECISION_COLUMN_JSON_MISMATCH")

    def test_06_payload_changed_without_digest_rejected(self):
        doc=json.loads(self.decision())
        doc["payload"]["amount_minor"]=999999
        self.mutate("action_decisions","data=?",(json.dumps(doc),))
        self.assertEqual(self.binding(),"DECISION_PAYLOAD_DIGEST_MISMATCH")
        print("G44_PAYLOAD_DIGEST_GREEN=MODIFIED_BUSINESS_VALUE_REFUSED")

    def test_07_decision_material_modified_with_matching_json_refused(self):
        doc=json.loads(self.decision())
        doc["action"]="synthetic-different-action"
        self.mutate("action_decisions","action=?,data=?",
            ("synthetic-different-action",json.dumps(doc)))
        self.assertEqual(self.binding(),"DECISION_IDEMPOTENCY_MATERIAL_MISMATCH")

    def test_08_malformed_decision_json_denied(self):
        self.mutate("action_decisions","data='not-json'")
        self.assertEqual(self.binding(),"DECISION_JSON_INVALID")

    def test_09_tampered_outbox_json_identity_denied(self):
        self.mutate("action_outbox","data='{\"idempotency_key\":\"forged\","
                    "\"decision_id\":\"forged\",\"state\":\"PENDING\"}'")
        self.assertEqual(self.binding(),"OUTBOX_JSON_IDENTITY_MISMATCH")

    def test_10_outbox_invalid_json_denied(self):
        self.mutate("action_outbox","data='not-json'")
        self.assertEqual(self.binding(),"OUTBOX_JSON_INVALID")

    def test_11_negative_claim_generation_denied(self):
        self.mutate("action_outbox","attempts=-1")
        self.assertEqual(self.binding(),"OUTBOX_STATE_OR_EPOCH_INVALID")

    def test_12_bad_state_enum_denied(self):
        self.mutate("action_outbox","state='SENT_OR_CONFIRMED'")
        self.assertEqual(self.binding(),"OUTBOX_STATE_OR_EPOCH_INVALID")

    def test_13_verified_scoped_local_effect_row_matches(self):
        self.confirm_synthetic()
        self.assertEqual(self.binding(),"OK")
        self.assertEqual(self.audit()["counts"],{"OK":1})

    def test_14_effect_owner_mismatch_denied(self):
        self.confirm_synthetic()
        self.mutate("action_effects","owner='outside-scope'")
        self.assertEqual(self.binding(),"EFFECT_SCOPE_MISMATCH")

    def test_15_confirmed_without_ledger_denied(self):
        self.confirm_synthetic()
        self.store.db.execute("DELETE FROM action_effects WHERE idempotency_key=?",
                              (self.key,))
        self.store.db.commit()
        self.assertEqual(self.binding(),"CONFIRMED_EFFECT_ABSENT")
        print("G44_MISSING_LEDGER_GREEN=CONFIRMED_WITHOUT_EFFECT_DENIED")

    def test_16_effect_receipt_reference_mismatch_denied(self):
        self.confirm_synthetic()
        self.mutate("action_effects","effect_ref='contradictory'")
        self.assertEqual(self.binding(),"EFFECT_COLUMN_MISMATCH")

    def test_17_effect_timestamp_mismatch_denied(self):
        self.confirm_synthetic()
        self.mutate("action_effects","confirmed_at='1900-01-01T00:00:00+00:00'")
        self.assertEqual(self.binding(),"EFFECT_COLUMN_MISMATCH")

    def test_18_effect_when_not_confirmed_denied(self):
        self.store.db.execute(
            """INSERT INTO action_effects
               (idempotency_key,owner,tenant,workspace,effect_ref,confirmed_at,data)
               VALUES(?,?,?,?,?,?,?)""",
            (self.key,SCOPE.owner_id,SCOPE.tenant_id,SCOPE.workspace_id,
             "fake","fake","{}"))
        self.store.db.commit()
        self.assertEqual(self.binding(),"NONCONFIRMED_EFFECT_PRESENT")

    def test_19_strict_claim_refuses_tampered_pending(self):
        self.mutate("action_decisions","data='malformed'")
        before=self.store.db.execute(
            "SELECT state FROM action_outbox WHERE idempotency_key=?",
            (self.key,)).fetchone()["state"]
        with self.assertRaisesRegex(RuntimeError,
                                    "G44_BINDING_INTEGRITY_DENIED:DECISION_JSON_INVALID"):
            self.strict.claim_next(WORKER,now=NOW)
        self.assertEqual(self.store.db.execute(
            "SELECT state FROM action_outbox WHERE idempotency_key=?",
            (self.key,)).fetchone()["state"],before)
        self.assertEqual(self.trap.reads,0)
        print("G44_CLAIM_BLOCK_GREEN=NO_CLAIM_ON_INVALID_DECISION")

    def test_20_strict_dispatch_refuses_before_adapter_getter(self):
        claim=self.with_claim()
        self.mutate("action_decisions","data='corrupted'")
        with self.assertRaisesRegex(RuntimeError,"G44_BINDING_INTEGRITY_DENIED"):
            self.strict.dispatch_claimed(self.key,worker_id=WORKER,
                authorize=self.authorize,adapter=self.trap,
                now=NOW+timedelta(seconds=1))
        self.assertEqual(self.trap.reads,0)
        self.assertEqual(self.store.db.execute(
            "SELECT state FROM action_outbox WHERE idempotency_key=?",
            (self.key,)).fetchone()["state"],"CLAIMED")
        print("G44_PRE_SEND_GREEN=BAD_BINDING_ZERO_ADAPTER_ACCESS")

    def test_21_authorization_callback_reentry_poisons_decision(self):
        self.with_claim()
        def authorize_then_tamper(d):
            self.mutate("action_decisions","data='corrupted'")
            return self.authorize(d)
        with self.assertRaisesRegex(RuntimeError,"G44_BINDING_INTEGRITY_DENIED"):
            self.strict.dispatch_claimed(self.key,worker_id=WORKER,
                authorize=authorize_then_tamper,adapter=self.trap,
                now=NOW+timedelta(seconds=1))
        self.assertEqual(self.trap.reads,0)
        self.assertEqual(self.store.db.execute(
            "SELECT state FROM action_outbox WHERE idempotency_key=?",
            (self.key,)).fetchone()["state"],"CLAIMED")
        print("G44_CALLBACK_REENTRY_GREEN=BAD_DECISION_NO_SEND")

    def test_22_strict_reconcile_denies_bad_ledger_before_getter(self):
        self.confirm_synthetic()
        self.mutate("action_effects","effect_ref='wrong'")
        with self.assertRaisesRegex(RuntimeError,"G44_BINDING_INTEGRITY_DENIED"):
            self.strict.reconcile(self.key,authorize=self.authorize,
                                  adapter=self.trap,now=NOW+timedelta(minutes=2))
        self.assertEqual(self.trap.reads,0)
        print("G44_RECONCILE_PREGETTER_GREEN=BAD_RECEIPT_ZERO_LOOKUP")

    def test_23_readonly_audit_preserves_database_bytes_and_no_payload(self):
        before=sha256(self.file.read_bytes()).hexdigest()
        report=self.audit()
        after=sha256(self.file.read_bytes()).hexdigest()
        self.assertEqual(before,after)
        self.assertNotIn("amount_minor",json.dumps(report))
        self.assertNotIn("synthetic-commercial-event",json.dumps(report))
        print("G44_READONLY_AUDIT_GREEN=NO_SCHEMA_CREATION_OR_DATA_WRITE")

    def test_24_missing_file_denied_without_creation(self):
        missing=self.file.parent/"missing.sqlite3"
        with self.assertRaisesRegex(RuntimeError,"G44_AUDIT_FILE_ABSENT"):
            audit_binding_readonly_lab(missing,owner=SCOPE.owner_id,
                tenant=SCOPE.tenant_id,workspace=SCOPE.workspace_id)
        self.assertFalse(missing.exists())

    def test_25_strict_flag_must_be_boolean(self):
        with self.assertRaises(TypeError):
            ExecutionOutbox(self.store,SCOPE,strict_binding_integrity_lab=1)

    def test_26_valid_local_binding_does_not_prove_event_truth_red(self):
        self.assertEqual(self.binding(),"OK")
        self.assertEqual(self.base.effect_count(),0)
        print("G44_AUTHENTICITY_RED=CORRECT_LOCAL_HASH_NOT_VERIFIED_EXTERNAL_EVENT")

    def test_27_semantic_lock_change_is_detected(self):
        item=self.base.enqueue(intent_ref="semantically-strict",
            action="synthetic_no_provider",
            payload={"business_event_id":"g44-new-event","amount_minor":1000},
            aggregate_key="synthetic-group",policy_version="p1",
            authorization_ref="auth1",created_at=NOW,
            valid_until=NOW+timedelta(minutes=5),
            semantic_event_id_lab="g44-new-event")
        key=item["idempotency_key"]
        self.assertEqual(self.binding(key),"OK")
        self.store.db.execute(
            "UPDATE semantic_reservations_lab SET payload_digest='fake'"
            " WHERE idempotency_key=?", (key,))
        self.store.db.commit()
        self.assertEqual(self.binding(key),"SEMANTIC_RESERVATION_MISMATCH")


    def test_28_duplicate_decision_json_key_denied(self):
        original = self.decision()
        ambiguous = original.replace('"decision_id":', '"decision_id":"fake",'
                                     '"decision_id":', 1)
        self.mutate("action_decisions","data=?",(ambiguous,))
        self.assertEqual(self.binding(),"DECISION_JSON_INVALID")
        print("G44_DUPLICATE_JSON_GREEN=AMBIGUOUS_DECISION_KEYS_DENIED")

    def test_29_duplicate_outbox_json_key_denied(self):
        old=self.store.db.execute(
            "SELECT data FROM action_outbox WHERE idempotency_key=?",
            (self.key,)).fetchone()["data"]
        ambiguous=old.replace('"state":','"state":"CONFIRMED","state":',1)
        self.mutate("action_outbox","data=?",(ambiguous,))
        self.assertEqual(self.binding(),"OUTBOX_JSON_INVALID")

    def test_30_reused_decision_across_two_outbox_rows_denied(self):
        ref=self.base.get(self.key)["decision_id"]
        fake_key="g44-duplicate-binding-row"
        fake_doc=json.dumps({"idempotency_key":fake_key,
                             "decision_id":ref,"state":"PENDING"})
        self.store.db.execute(
            """INSERT INTO action_outbox
               (idempotency_key,decision_id,owner,tenant,workspace,state,data)
               VALUES(?,?,?,?,?,'PENDING',?)""",
            (fake_key,ref,SCOPE.owner_id,SCOPE.tenant_id,
             SCOPE.workspace_id,fake_doc))
        self.store.db.commit()
        self.assertEqual(self.binding(),"DECISION_SHARED_BY_MULTIPLE_OUTBOXES")
        self.assertEqual(self.binding(fake_key),"DECISION_SHARED_BY_MULTIPLE_OUTBOXES")
        print("G44_SHARED_DECISION_GREEN=SECOND_OUTBOX_REFUSED")

    def test_31_orphan_decision_is_classified_without_auto_repair(self):
        ref=self.base.get(self.key)["decision_id"]
        self.store.db.execute(
            """INSERT INTO action_decisions(
               decision_id,owner,tenant,workspace,intent_ref,action,
               aggregate_key,aggregate_seq,payload_digest,policy_version,
               authorization_ref,valid_until,created_at,data)
               SELECT 'DEC-G44-ORPHAN',owner,tenant,workspace,
                      'g44-orphan-intent',action,aggregate_key,
                      aggregate_seq+100,payload_digest,policy_version,
                      authorization_ref,valid_until,created_at,data
               FROM action_decisions WHERE decision_id=?""",
            (ref,))
        self.store.db.commit()
        self.assertEqual(self.binding(),"OK")
        report=self.audit()
        self.assertEqual(report["counts"]["ORPHAN_DECISION"],1)
        self.assertEqual(report["rows"],1)
        print("G44_ORPHAN_DECISION_GREEN=READONLY_CLASSIFICATION_NO_REPAIR")


    def test_32_unicode_payload_canonicalization_matches_real_producer(self):
        item=self.base.enqueue(
            intent_ref="unicode42",action="synthetic_no_provider",
            payload={"descrição":"ação e inflação","amount_minor":1000},
            aggregate_key="synthetic-group",policy_version="p1",
            authorization_ref="auth1",created_at=NOW,
            valid_until=NOW+timedelta(minutes=5))
        key=item["idempotency_key"]
        self.assertEqual(self.binding(key),"OK")
        print("G44_UNICODE_GREEN=PRODUCER_AUDITOR_CANONICAL_DIGEST_MATCH")

    def test_33_reconcile_getter_reentry_denies_before_callback(self):
        self.with_claim()
        state=self.base.dispatch_claimed(self.key,worker_id=WORKER,
            authorize=self.authorize,adapter=self.trap,
            now=NOW+timedelta(seconds=1))
        self.assertEqual(state["state"],"UNCERTAIN")
        reviewer=ExecutionOutbox(self.store,SCOPE,
            unsafe_allow_synthetic_lab_callbacks=True,
            strict_binding_integrity_lab=True,evidence_verifier=lambda *_:True)
        parent=self
        class GetterPoison:
            calls=0
            @property
            def reconcile(self):
                parent.mutate("action_decisions","data='g44-malformed'")
                return self._call
            def _call(self,key,decision):
                self.calls+=1
                raise AssertionError("G44_GETTER_MUST_BLOCK_BEFORE_CALLBACK")
        trap=GetterPoison()
        with self.assertRaisesRegex(RuntimeError,"G44_BINDING_INTEGRITY_DENIED"):
            reviewer.reconcile(self.key,adapter=trap,
                authorize=self.authorize,now=NOW+timedelta(minutes=2))
        self.assertEqual(trap.calls,0)
        self.assertEqual(self.store.db.execute(
            "SELECT state FROM action_outbox WHERE idempotency_key=?",
            (self.key,)).fetchone()["state"],"UNCERTAIN")
        print("G44_RECONCILE_GETTER_GREEN=REENTRY_DENIED_ZERO_CALLBACK")

    def test_34_orphaned_predecessor_prevents_successor_claim(self):
        successor=self.base.enqueue(
            intent_ref="synthetic-order-43",action="synthetic_no_provider",
            payload={"amount_minor":2000},
            aggregate_key="synthetic-group",policy_version="p1",
            authorization_ref="auth1",created_at=NOW+timedelta(seconds=1),
            valid_until=NOW+timedelta(minutes=5))
        self.store.db.execute("DELETE FROM action_outbox WHERE idempotency_key=?",
                              (self.key,))
        self.store.db.commit()
        self.assertIsNone(self.strict.claim_next(WORKER,now=NOW))
        self.assertEqual(self.base.get(successor["idempotency_key"])["state"],"PENDING")
        self.assertEqual(self.audit()["counts"].get("ORPHAN_DECISION"),1)
        print("G44_ORPHAN_PREDECESSOR_GREEN=NO_SUCCESSOR_CLAIM")

    def test_35_repeated_confirmation_keeps_original_timestamp(self):
        first=self.confirm_synthetic()
        original_at=first["confirmed_at"]
        repeated=self.strict._confirm(self.key,effect_ref="synthetic-local-effect",
            confirmed_at=NOW+timedelta(hours=1),result={"synthetic":"repeated"})
        self.assertEqual(repeated["confirmed_at"],original_at)
        ledger=self.store.db.execute(
            "SELECT confirmed_at FROM action_effects WHERE idempotency_key=?",
            (self.key,)).fetchone()
        self.assertEqual(ledger["confirmed_at"],original_at)
        self.assertEqual(self.binding(),"OK")
        print("G44_RECONFIRM_GREEN=IMMUTABLE_LOCAL_LEDGER_TIME")

    def test_36_unsupported_decision_schema_denied(self):
        doc=json.loads(self.decision())
        doc["schema"]="ATLASQUANT_AION_UNREVIEWED_V2"
        self.mutate("action_decisions","data=?",(json.dumps(doc),))
        self.assertEqual(self.binding(),"DECISION_SCHEMA_OR_AUTHORITY_INVALID")

    def test_37_deceptive_authority_grant_in_json_denied(self):
        doc=json.loads(self.decision())
        doc["grants_authority"]=True
        self.mutate("action_decisions","data=?",(json.dumps(doc),))
        self.assertEqual(self.binding(),"DECISION_SCHEMA_OR_AUTHORITY_INVALID")

    def test_38_terminal_predecessor_missing_effect_denies_successor(self):
        successor=self.base.enqueue(
            intent_ref="synthetic-order-43",action="synthetic_no_provider",
            payload={"amount_minor":2000},aggregate_key="synthetic-group",
            policy_version="p1",authorization_ref="auth1",
            created_at=NOW+timedelta(seconds=1),
            valid_until=NOW+timedelta(minutes=5))
        prior=self.base.claim_next(WORKER,now=NOW)
        self.assertEqual(prior["idempotency_key"],self.key)
        self.confirm_synthetic()
        self.store.db.execute(
            "DELETE FROM action_effects WHERE idempotency_key=?", (self.key,))
        self.store.db.commit()
        self.assertEqual(self.binding(),"CONFIRMED_EFFECT_ABSENT")
        with self.assertRaisesRegex(RuntimeError,
                                    "G44_BINDING_INTEGRITY_DENIED:CONFIRMED_EFFECT_ABSENT"):
            self.strict.claim_next(WORKER,now=NOW+timedelta(seconds=3))
        self.assertEqual(self.base.get(successor["idempotency_key"])["state"],"PENDING")
        print("G44_TERMINAL_PREDECESSOR_GREEN=MISSING_LEDGER_BLOCKS_SUCCESSOR")

    def test_39_consistent_confirmed_predecessor_allows_successor_claim(self):
        successor=self.base.enqueue(
            intent_ref="synthetic-order-43",action="synthetic_no_provider",
            payload={"amount_minor":2000},aggregate_key="synthetic-group",
            policy_version="p1",authorization_ref="auth1",
            created_at=NOW+timedelta(seconds=1),
            valid_until=NOW+timedelta(minutes=5))
        prior=self.base.claim_next(WORKER,now=NOW)
        self.assertEqual(prior["idempotency_key"],self.key)
        self.confirm_synthetic()
        self.assertEqual(self.binding(),"OK")
        accepted=self.strict.claim_next(WORKER,now=NOW+timedelta(seconds=3))
        self.assertEqual(accepted["idempotency_key"],successor["idempotency_key"])
        self.assertEqual(accepted["state"],"CLAIMED")
        self.assertEqual(self.base.effect_count(),1)
        print("G44_VALID_PREDECESSOR_GREEN=CONSISTENT_TERMINAL_PERMITS_CLAIM")
if __name__=="__main__":
    unittest.main()
