"""G41 real SQLite claim generation CAS / callback reentry adversarial LAB.

Uses the already persisted attempts field as LOCAL claim generation; proof of
external uniqueness, genuine provider effect and antirollback are ABSENT.
All fake adapter calls stay inside synthetic disposable tests.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import shutil
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

NOW=datetime(2026,10,24,15,tzinfo=timezone.utc)
SCOPE=Scope("g41-owner","g41-tenant","g41-workspace")
WORKER="g41-worker"


class Trap:
    def __init__(self): self.lookups=0
    @property
    def send(self):
        self.lookups+=1
        raise AssertionError("G41_SEND_MUST_NOT_BE_CALLED")


class Synthetic:
    def __init__(self, response=None):
        self.getters=0
        self.calls=0
        self.response=response if response is not None else {"accepted":True,"effect_ref":"test-only"}

    @property
    def send(self):
        self.getters+=1
        return self._send

    def _send(self, decision, key):
        self.calls+=1
        return dict(self.response)


class G41PersistentClaimFencing(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="g41-fence-")
        self.addCleanup(self.temp.cleanup)
        self.file=Path(self.temp.name)/"outbox.sqlite3"
        self.store=SQLiteChatStore(self.file)
        self.addCleanup(lambda:self.store.close())
        self.outbox=ExecutionOutbox(self.store,SCOPE,
            strict_claim_fencing_lab=True,
            strict_authority_scope_lab=True,
            fresh_dispatch_clock_lab=lambda:NOW+timedelta(seconds=2))
        self.adapter=Trap()

    def stage(self, *, lease=60):
        row=self.outbox.enqueue(
            intent_ref="invoice-42", action="synthetic_no_provider",
            payload={"amount_minor":1000}, aggregate_key="synthetic-aggregate",
            policy_version="p1", authorization_ref="a1",
            created_at=NOW, valid_until=NOW+timedelta(minutes=5))
        claim=self.outbox.claim_next(WORKER,now=NOW,lease_seconds=lease)
        self.assertEqual(claim["idempotency_key"],row["idempotency_key"])
        return claim

    def auth(self,d):
        return {"allowed":True,"actor_id":SCOPE.owner_id,
                "tenant_id":SCOPE.tenant_id,"workspace_id":SCOPE.workspace_id,
                "policy_version":"p1","authorization_ref":"a1"}

    def dispatch(self,row,*,token=None,auth=None,adapter=None):
        return self.outbox.dispatch_claimed(
            row["idempotency_key"],worker_id=WORKER,
            claim_generation_lab=row["attempts"] if token is None else token,
            authorize=self.auth if auth is None else auth,
            adapter=self.adapter if adapter is None else adapter,
            now=NOW+timedelta(seconds=1))

    def confirm_fake(self,row,effect="synthetic-confirmed"):
        return self.outbox._confirm(row["idempotency_key"],
            effect_ref=effect,confirmed_at=NOW+timedelta(seconds=1),
            result={"source":"LAB_SYNTHETIC_NOT_PROVIDER"})

    def test_01_first_generation_is_durable_positive_integer(self):
        claim=self.stage()
        self.assertEqual(claim["attempts"],1)
        self.assertEqual(self.outbox.get(claim["idempotency_key"])["attempts"],1)
        print("G41_PERSISTED_EPOCH_GREEN=CLAIM_GENERATION_IN_REAL_SQLITE")

    def test_02_strict_fencing_option_requires_bool(self):
        with self.assertRaises(TypeError):
            ExecutionOutbox(self.store,SCOPE,strict_claim_fencing_lab=1)

    def test_03_missing_token_fails_before_any_callback(self):
        claim=self.stage()
        called=[]
        with self.assertRaisesRegex(ValueError,"FENCE_GENERATION_REQUIRED"):
            self.outbox.dispatch_claimed(claim["idempotency_key"],
                worker_id=WORKER,authorize=lambda x:called.append(1),
                adapter=self.adapter,now=NOW+timedelta(seconds=1))
        self.assertEqual(called,[])
        self.assertEqual(self.adapter.lookups,0)

    def test_04_wrong_epoch_fails_before_authorize(self):
        claim=self.stage()
        with self.assertRaisesRegex(RuntimeError,"FENCE_STALE_GENERATION"):
            self.dispatch(claim,token=claim["attempts"]+1)
        self.assertEqual(self.adapter.lookups,0)

    def test_05_same_worker_new_claim_generation_fences_old_handle(self):
        old=self.stage(lease=10)
        self.assertEqual(self.outbox.release_expired_claims(
            now=NOW+timedelta(seconds=11)),1)
        new=self.outbox.claim_next(
            WORKER,now=NOW+timedelta(seconds=11),lease_seconds=60)
        self.assertEqual(new["attempts"],old["attempts"]+1)
        with self.assertRaisesRegex(RuntimeError,"FENCE_STALE_GENERATION"):
            self.dispatch(old)
        self.assertEqual(self.outbox.get(new["idempotency_key"])["state"],"CLAIMED")
        print("G41_SAME_WORKER_GREEN=STALE_EPOCH_DENIED_AFTER_RECLAIM")

    def test_06_reopen_persists_new_fence_counter(self):
        old=self.stage(lease=10)
        self.outbox.release_expired_claims(now=NOW+timedelta(seconds=11))
        new=self.outbox.claim_next(WORKER,
            now=NOW+timedelta(seconds=11),lease_seconds=60)
        self.store.close()
        self.store=SQLiteChatStore(self.file)
        self.outbox=ExecutionOutbox(self.store,SCOPE,strict_claim_fencing_lab=True,
            strict_authority_scope_lab=True,
            fresh_dispatch_clock_lab=lambda:NOW+timedelta(seconds=12))
        self.assertEqual(self.outbox.get(new["idempotency_key"])["attempts"],2)
        with self.assertRaisesRegex(RuntimeError,"FENCE_STALE_GENERATION"):
            self.dispatch(old)
        print("G41_REOPEN_GREEN=PERSISTENT_NEW_EPOCH_OLD_HANDLE_REFUSED")

    def test_07_auth_callback_mutates_epoch_is_denied(self):
        claim=self.stage()
        def hijack(decision):
            self.outbox.db.execute("UPDATE action_outbox SET attempts=attempts+1 "
                "WHERE idempotency_key=?", (claim["idempotency_key"],))
            self.outbox.db.commit()
            return self.auth(decision)
        with self.assertRaisesRegex(RuntimeError,"FENCE_STALE_GENERATION"):
            self.dispatch(claim,auth=hijack)
        self.assertEqual(self.outbox.get(claim["idempotency_key"])["state"],"CLAIMED")
        self.assertEqual(self.adapter.lookups,0)

    def test_08_denial_callback_confirms_does_not_overwrite(self):
        claim=self.stage()
        def confirm_then_deny(decision):
            self.confirm_fake(claim)
            return {"allowed":False}
        with self.assertRaisesRegex(RuntimeError,"FENCE_STALE_GENERATION"):
            self.dispatch(claim,auth=confirm_then_deny)
        row=self.outbox.get(claim["idempotency_key"])
        self.assertEqual(row["state"],"CONFIRMED")
        self.assertEqual(self.outbox.effect_count(),1)
        print("G41_AUTH_REENTRY_GREEN=CONFIRMED_NOT_REVOKED")

    def test_09_normal_denial_cas_transitions_to_revoked(self):
        claim=self.stage()
        result=self.dispatch(claim,auth=lambda _:{"allowed":False})
        self.assertEqual(result["state"],"REVOKED")
        self.assertEqual(self.adapter.lookups,0)

    def test_10_default_first_witness_denies_even_with_good_epoch(self):
        claim=self.stage()
        result=self.dispatch(claim)
        self.assertEqual(result["state"],"UNCERTAIN")
        self.assertEqual(result["last_error"],"FIRST_ATTEMPT_WITNESS_UNVERIFIED_NO_SEND")
        self.assertEqual(self.outbox.effect_count(),0)
        self.assertEqual(self.adapter.lookups,0)

    def enable_test_witness(self,gate=None,verifier=None):
        self.outbox=ExecutionOutbox(self.store,SCOPE,strict_claim_fencing_lab=True,
            strict_authority_scope_lab=True,
            fresh_dispatch_clock_lab=lambda:NOW+timedelta(seconds=2),
            unsafe_allow_synthetic_lab_callbacks=True,
            first_attempt_guard=gate or (lambda _:True),
            evidence_verifier=verifier)

    def test_11_witness_callback_confirms_cannot_clear_terminal(self):
        claim=self.stage()
        def confirm_witness(_):
            self.confirm_fake(claim)
            return False
        self.enable_test_witness(gate=confirm_witness)
        with self.assertRaisesRegex(RuntimeError,"FENCE_STALE_GENERATION"):
            self.dispatch(claim)
        self.assertEqual(self.outbox.get(claim["idempotency_key"])["state"],"CONFIRMED")
        self.assertEqual(self.outbox.effect_count(),1)
        print("G41_WITNESS_REENTRY_GREEN=CONFIRMED_NOT_REPLACED")

    def test_12_getter_changes_epoch_before_send(self):
        claim=self.stage()
        self.enable_test_witness()
        parent=self
        class Hijack:
            calls=0
            @property
            def send(self):
                parent.outbox.db.execute(
                    "UPDATE action_outbox SET attempts=attempts+1 "
                    "WHERE idempotency_key=?", (claim["idempotency_key"],))
                parent.outbox.db.commit()
                return self._send
            def _send(self,d,k):
                self.calls+=1
                raise AssertionError("G41_GETTER_SHOULD_NOT_SEND")
        fake=Hijack()
        with self.assertRaisesRegex(RuntimeError,"FENCE_STALE_GENERATION"):
            self.dispatch(claim,adapter=fake)
        self.assertEqual(fake.calls,0)
        print("G41_GETTER_EPOCH_GREEN=REENTRY_DENIED_BEFORE_SEND")

    def test_13_send_callback_confirms_then_returns_no_overwrite(self):
        claim=self.stage()
        self.enable_test_witness()
        parent=self
        class Reentrant:
            calls=0
            @property
            def send(self):return self._send
            def _send(self,d,k):
                self.calls+=1
                parent.confirm_fake(claim)
                return {"accepted":True,"effect_ref":"stale-effect"}
        fake=Reentrant()
        with self.assertRaisesRegex(RuntimeError,"FENCE_STALE_GENERATION"):
            self.dispatch(claim,adapter=fake)
        self.assertEqual(fake.calls,1)
        self.assertEqual(self.outbox.get(claim["idempotency_key"])["state"],"CONFIRMED")
        self.assertEqual(self.outbox.effect_count(),1)
        print("G41_SEND_REENTRY_GREEN=CONFIRMED_NOT_SENT")

    def test_14_send_callback_confirms_then_raises_preserves_ledger(self):
        claim=self.stage()
        self.enable_test_witness()
        parent=self
        class ReentrantError:
            @property
            def send(self):return self._send
            def _send(self,d,k):
                parent.confirm_fake(claim)
                raise OSError("synthetic-after-effect-ack-unknown")
        with self.assertRaisesRegex(RuntimeError,"FENCE_STALE_SEND_EXCEPTION"):
            self.dispatch(claim,adapter=ReentrantError())
        self.assertEqual(self.outbox.get(claim["idempotency_key"])["state"],"CONFIRMED")
        self.assertEqual(self.outbox.effect_count(),1)

    def test_15_confirm_verifier_reenters_then_second_effect_rolled_back(self):
        claim=self.stage()
        def evidence(kind,intent,result):
            self.confirm_fake(claim,effect="trusted-by-test-prior")
            return True
        self.enable_test_witness(verifier=evidence)
        fake=Synthetic({"accepted":True,"confirmed":True,
                        "effect_ref":"late-different-ref"})
        with self.assertRaisesRegex(ValueError,"effect ledger idempotency collision"):
            self.dispatch(claim,adapter=fake)
        self.assertEqual(self.outbox.get(claim["idempotency_key"])["state"],"CONFIRMED")
        self.assertEqual(self.outbox.effect_count(),1)

    def test_16_successful_test_stub_only_is_sent_not_effect_ledger(self):
        claim=self.stage()
        self.enable_test_witness()
        fake=Synthetic()
        result=self.dispatch(claim,adapter=fake)
        self.assertEqual(result["state"],"SENT")
        self.assertEqual(fake.calls,1)
        self.assertEqual(self.outbox.effect_count(),0)
        self.assertFalse(result["executes_action"])
        print("G41_LAB_STUB_LIMIT=SENT_ROW_NOT_REAL_PROVIDER_EFFECT")

    def test_17_after_uncertain_no_auto_reclaim(self):
        claim=self.stage()
        self.dispatch(claim)
        self.assertIsNone(self.outbox.claim_next(
            WORKER,now=NOW+timedelta(minutes=1)))
        self.assertEqual(self.outbox.get(claim["idempotency_key"])["state"],"UNCERTAIN")

    def test_18_host_rollback_reuses_generation_red(self):
        claim=self.stage()
        self.store.close()
        backup=Path(self.temp.name)/"previous.sqlite3"
        shutil.copyfile(self.file,backup)
        self.store=SQLiteChatStore(self.file)
        self.outbox=ExecutionOutbox(self.store,SCOPE,strict_claim_fencing_lab=True,
            strict_authority_scope_lab=True)
        self.outbox.release_expired_claims(now=NOW+timedelta(minutes=2))
        newer=self.outbox.claim_next(
            WORKER,now=NOW+timedelta(minutes=2),lease_seconds=30)
        self.assertEqual(newer["attempts"],2)
        self.store.close()
        shutil.copyfile(backup,self.file)
        self.store=SQLiteChatStore(self.file)
        self.outbox=ExecutionOutbox(self.store,SCOPE,strict_claim_fencing_lab=True,
            strict_authority_scope_lab=True)
        recovered=self.outbox.get(claim["idempotency_key"])
        self.assertEqual(recovered["attempts"],1)
        self.assertEqual(recovered["state"],"CLAIMED")
        print("G41_SAME_HOST_ROLLBACK_RED=OLD_GENERATION_RESTORED_WITH_SQLITE")

if __name__=="__main__":
    unittest.main()
