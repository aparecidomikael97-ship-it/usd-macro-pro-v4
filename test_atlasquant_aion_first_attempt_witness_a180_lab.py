"""A180 synthetic witness-before-send tests. NO provider/network effects."""
import base64
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from aion_chat.first_attempt_witness_lab import (
    DOMAIN, SCHEMA, PinnedFirstAttemptWitnessLab,
    _effect_digest,
)
from aion_chat.signed_receipt_lab import canonical_bytes
from atlasquant_aion_execution_outbox import ExecutionOutbox
from test_atlasquant_aion_execution_outbox import NOW, policy
from test_atlasquant_aion_signed_receipt_a178_lab import public_bytes


WITNESS_PRIVATE = Ed25519PrivateKey.from_private_bytes(b"\x0b" * 32)
ATTACKER_PRIVATE = Ed25519PrivateKey.from_private_bytes(b"\x0c" * 32)
ISSUER = "first-attempt-lab-witness"
KEY_ID = "first-attempt-lab-key"


class SyntheticReserveWitness:
    """Ephemeral witness deliberately vulnerable to rollback and repinning."""
    def __init__(self):
        self.reserved = set()
        self.seq = 0
        self.calls = 0
        self.offline = False
        self.lost_reply = False
        self.stale = None
        self.return_stale = False
        self.tamper = {}
        self.signer = WITNESS_PRIVATE
        self.seen_requests = []

    def __call__(self, challenge, request):
        self.calls += 1
        self.seen_requests.append(dict(request))
        if self.offline:
            raise OSError("synthetic witness unreachable")
        if self.return_stale and self.stale is not None:
            return self.stale
        digest = request["effect_digest"]
        if digest in self.reserved:
            return {"status": "ALREADY_RESERVED"}
        self.reserved.add(digest)
        self.seq += 1
        if self.lost_reply:
            raise TimeoutError("reservation committed, answer lost")
        proof = {
            "schema": SCHEMA, "status": "RESERVED",
            "issuer": ISSUER, "key_id": KEY_ID,
            "challenge": challenge, "sequence": self.seq,
            "issued_at": NOW.isoformat(),
            "expires_at": (NOW+timedelta(seconds=40)).isoformat(),
            **request,
        }
        proof.update(self.tamper)
        signature = base64.b64encode(
            self.signer.sign(DOMAIN + canonical_bytes(proof))).decode("ascii")
        self.stale = {"payload":proof,"signature":signature}
        return self.stale


class LabAdapter:
    def __init__(self):
        self.send_calls = 0
    def send(self, decision, key):
        self.send_calls += 1
        return {"accepted":True,"confirmed":True,"effect_ref":"fake-1"}


def fake_confirmed(kind, intent, result):
    """Explicitly synthetic receipt verifier; no real provider provenance."""
    return kind == "EFFECT_CONFIRMED" and result.get("effect_ref") == "fake-1"


class A180FirstAttemptWitnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "outbox.sqlite3"
        self.store = SQLiteChatStore(self.path)
        self.addCleanup(self.store.close)
        self.scope = Scope("owner-lab","tenant-lab","workspace-lab")
        self.witness = SyntheticReserveWitness()

    def guard(self, *, reserve=None, key=None, revoked=False, high_water=0):
        return PinnedFirstAttemptWitnessLab(
            issuer=ISSUER,key_id=KEY_ID,
            public_key=public_bytes(key or WITNESS_PRIVATE),
            reserve=self.witness if reserve is None else reserve,
            now=NOW+timedelta(seconds=2),
            high_water=high_water, revoked=revoked)

    def claim(self, *, guard="DEFAULT", intent_ref="event-a", payload=None,
              evidence_verifier=fake_confirmed):
        opts={"evidence_verifier":evidence_verifier}
        if guard != "DEFAULT":
            opts["first_attempt_guard"]=guard
        outbox=ExecutionOutbox(self.store,self.scope,**opts)
        item=outbox.enqueue(
            intent_ref=intent_ref, action="send_email",
            payload=payload or {"to":"example.invalid","template":"lab"},
            aggregate_key="same-target",policy_version="policy-v1",
            authorization_ref="approval-1",created_at=NOW,
            valid_until=NOW+timedelta(minutes=5))
        self.assertIsNotNone(outbox.claim_next("worker1",now=NOW,lease_seconds=60))
        return outbox,item

    def send(self,outbox,item,adapter=None):
        a=adapter or LabAdapter()
        r=outbox.dispatch_claimed(
            item["idempotency_key"],worker_id="worker1",
            authorize=policy(self.scope),adapter=a,
            now=NOW+timedelta(seconds=1))
        return r,a

    def test_01_no_witness_guard_denies_before_send(self):
        out,item=self.claim()
        result,adapter=self.send(out,item)
        self.assertEqual(result["state"],"UNCERTAIN")
        self.assertEqual(adapter.send_calls,0)
        self.assertIsNone(out.claim_next("worker2",now=NOW+timedelta(seconds=3)))
        print("A180_DEFAULT_NO_FIRST_WITNESS=NO_SEND")

    def test_02_valid_witness_reserves_first_then_sends_once(self):
        out,item=self.claim(guard=self.guard())
        result,adapter=self.send(out,item)
        self.assertEqual(result["state"],"CONFIRMED")
        self.assertEqual(adapter.send_calls,1)
        self.assertEqual(self.witness.calls,1)
        self.assertEqual(len(self.witness.reserved),1)
        self.assertEqual(out.effect_count(),1)
        print("A180_WITNESSED_RESERVE_BEFORE_SEND=ONE_LAB_EFFECT")

    def test_03_witness_offline_fails_closed_without_send(self):
        self.witness.offline=True
        out,item=self.claim(guard=self.guard())
        result,adapter=self.send(out,item)
        self.assertEqual(result["state"],"UNCERTAIN")
        self.assertEqual(adapter.send_calls,0)
        self.assertEqual(out.effect_count(),0)
        print("A180_OFFLINE_WITNESS=NO_SEND")

    def test_04_witness_commits_but_reply_lost_no_send(self):
        self.witness.lost_reply=True
        out,item=self.claim(guard=self.guard())
        result,adapter=self.send(out,item)
        self.assertEqual(result["state"],"UNCERTAIN")
        self.assertEqual(adapter.send_calls,0)
        self.assertEqual(len(self.witness.reserved),1)
        print("A180_UNCERTAIN_RESERVATION_REPLY=NO_SEND")

    def test_05_restart_after_uncertain_preflight_never_claims(self):
        self.witness.lost_reply=True
        out,item=self.claim(guard=self.guard())
        self.assertEqual(self.send(out,item)[0]["state"],"UNCERTAIN")
        self.store.close()
        reopened=SQLiteChatStore(self.path)
        try:
            new=ExecutionOutbox(reopened,self.scope,first_attempt_guard=self.guard())
            self.assertEqual(new.get(item["idempotency_key"])["state"],"UNCERTAIN")
            self.assertIsNone(new.claim_next("worker2",now=NOW+timedelta(seconds=4)))
        finally:
            reopened.close()
        print("A180_PREFLIGHT_CRASH_REOPEN=UNKNOWN_NO_RETRY")

    def test_06_same_semantic_effect_new_intent_ref_denied_by_witness(self):
        out,item=self.claim(guard=self.guard(),intent_ref="event-a")
        self.assertEqual(self.send(out,item)[0]["state"],"CONFIRMED")
        second=out.enqueue(intent_ref="event-b", action="send_email",
            payload={"to":"example.invalid","template":"lab"},
            aggregate_key="same-target",policy_version="policy-v1",
            authorization_ref="approval-1",created_at=NOW,
            valid_until=NOW+timedelta(minutes=5))
        self.assertNotEqual(second["idempotency_key"],item["idempotency_key"])
        self.assertIsNotNone(out.claim_next("worker1",now=NOW+timedelta(seconds=2)))
        adapter=LabAdapter()
        result=out.dispatch_claimed(second["idempotency_key"],worker_id="worker1",
            authorize=policy(self.scope),adapter=adapter,
            now=NOW+timedelta(seconds=3))
        self.assertEqual(result["state"],"UNCERTAIN")
        self.assertEqual(adapter.send_calls,0)
        print("A180_NEW_TECHNICAL_ID_SAME_SEMANTIC_DIGEST=DENIED")

    def test_07_expired_signature_blocks_without_send(self):
        self.witness.tamper={"issued_at":(NOW-timedelta(minutes=4)).isoformat(),
                             "expires_at":(NOW-timedelta(seconds=1)).isoformat()}
        out,item=self.claim(guard=self.guard())
        result,adapter=self.send(out,item)
        self.assertEqual(result["state"],"UNCERTAIN")
        self.assertEqual(adapter.send_calls,0)

    def test_08_replayed_witness_challenge_fails_closed(self):
        # First obtain a valid but unrelated signed response.
        self.witness("0"*64,{"idempotency_key":"old",
            "effect_digest":"e"*64,"decision_sha256":"a"*64,
            "owner_id":"owner-lab","tenant_id":"tenant-lab",
            "workspace_id":"workspace-lab"})
        self.witness.return_stale=True
        out,item=self.claim(guard=self.guard())
        result,adapter=self.send(out,item)
        self.assertEqual(result["state"],"UNCERTAIN")
        self.assertEqual(adapter.send_calls,0)
        print("A180_REPLAYED_PRE_FLIGHT_CHALLENGE=DENIED")

    def test_09_untrusted_signature_denied(self):
        self.witness.signer=ATTACKER_PRIVATE
        out,item=self.claim(guard=self.guard())
        result,adapter=self.send(out,item)
        self.assertEqual(result["state"],"UNCERTAIN")
        self.assertEqual(adapter.send_calls,0)

    def test_10_revoked_witness_denied_without_callback(self):
        out,item=self.claim(guard=self.guard(revoked=True))
        result,adapter=self.send(out,item)
        self.assertEqual(result["state"],"UNCERTAIN")
        self.assertEqual(self.witness.calls,0)
        self.assertEqual(adapter.send_calls,0)

    def test_11_stale_sequence_denied_before_send(self):
        out,item=self.claim(guard=self.guard(high_water=1))
        result,adapter=self.send(out,item)
        self.assertEqual(result["state"],"UNCERTAIN")
        self.assertEqual(adapter.send_calls,0)

    def test_12_signature_wrong_intent_denied(self):
        self.witness.tamper={"idempotency_key":"other"}
        out,item=self.claim(guard=self.guard())
        result,adapter=self.send(out,item)
        self.assertEqual(result["state"],"UNCERTAIN")
        self.assertEqual(adapter.send_calls,0)

    def test_13_restored_witness_state_allows_same_effect_again_known_bypass(self):
        out,item=self.claim(guard=self.guard(),intent_ref="event-a")
        self.assertEqual(self.send(out,item)[0]["state"],"CONFIRMED")
        self.witness.reserved.clear()
        self.witness.seq=0
        second=out.enqueue(intent_ref="event-b",action="send_email",
            payload={"to":"example.invalid","template":"lab"},
            aggregate_key="same-target",policy_version="policy-v1",
            authorization_ref="approval-1",created_at=NOW,
            valid_until=NOW+timedelta(minutes=5))
        out_after=ExecutionOutbox(self.store,self.scope,
            evidence_verifier=fake_confirmed,first_attempt_guard=self.guard())
        self.assertIsNotNone(out_after.claim_next("worker1",now=NOW+timedelta(seconds=2)))
        sent=LabAdapter()
        r=out_after.dispatch_claimed(second["idempotency_key"],worker_id="worker1",
            authorize=policy(self.scope),adapter=sent,
            now=NOW+timedelta(seconds=3))
        self.assertEqual(r["state"],"CONFIRMED")
        self.assertEqual(sent.send_calls,1)
        print("A180_RESTORED_WITNESS=REPEATED_SEMANTIC_EFFECT_NOT_ATTESTED")

    def test_14_caller_forged_witness_key_bypasses_trust_known_limit(self):
        self.witness.signer=ATTACKER_PRIVATE
        out,item=self.claim(guard=self.guard(key=ATTACKER_PRIVATE))
        r,a=self.send(out,item)
        self.assertEqual(r["state"],"CONFIRMED")
        self.assertEqual(a.send_calls,1)
        print("A180_CALLER_REPINS_FIRST_WITNESS=FALSE_AUTHORITY_ACCEPTED")

    def test_15_missing_signature_envelope_denied(self):
        out,item=self.claim(guard=self.guard(reserve=lambda c,r:{"ok":True}))
        r,a=self.send(out,item)
        self.assertEqual(r["state"],"UNCERTAIN")
        self.assertEqual(a.send_calls,0)

    def test_16_forged_business_identity_remains_unprotected_known_limit(self):
        # Different real-world event alias produced by modifying the claimed
        # aggregate and payload can evade the LAB digest.
        d1={"owner_id":"owner-lab","tenant_id":"tenant-lab",
            "workspace_id":"workspace-lab","action":"send_email",
            "aggregate_key":"same-target","payload_digest":"a"*64}
        d2={**d1,"aggregate_key":"other-target"}
        self.assertNotEqual(_effect_digest(d1),_effect_digest(d2))
        print("A180_ALTERED_SEMANTIC_DESCRIPTOR=UNDETECTABLE_AS_SAME_EFFECT")

    def test_17_legitimate_distinct_payload_does_not_block(self):
        out,item=self.claim(guard=self.guard())
        self.assertEqual(self.send(out,item)[0]["state"],"CONFIRMED")
        second=out.enqueue(intent_ref="event-b",action="send_email",
            payload={"to":"different.invalid","template":"lab"},
            aggregate_key="same-target",policy_version="policy-v1",
            authorization_ref="approval-1",created_at=NOW,
            valid_until=NOW+timedelta(minutes=5))
        self.assertIsNotNone(out.claim_next("worker1",now=NOW+timedelta(seconds=2)))
        a=LabAdapter()
        r=out.dispatch_claimed(second["idempotency_key"],worker_id="worker1",
            authorize=policy(self.scope),adapter=a,
            now=NOW+timedelta(seconds=3))
        self.assertEqual(r["state"],"CONFIRMED")
        self.assertEqual(a.send_calls,1)

    def test_18_no_witness_fail_closed_after_claim_lease_expiry(self):
        out,item=self.claim()
        self.assertEqual(self.send(out,item)[0]["state"],"UNCERTAIN")
        self.assertIsNone(out.claim_next("worker2",now=NOW+timedelta(minutes=6)))
        self.assertEqual(out.get(item["idempotency_key"])["state"],"UNCERTAIN")


if __name__=="__main__":
    unittest.main()
