"""A179 synthetic dual-key witness receipt tests. Never call a live provider."""
import base64
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from aion_chat.witness_admission_lab import (
    DOMAIN, SCHEMA, WitnessedReceiptGateLab,
)
from aion_chat.signed_receipt_lab import canonical_bytes
from atlasquant_aion_execution_outbox import ExecutionOutbox
from test_atlasquant_aion_signed_receipt_a178_lab import (
    NOW, LAB_PRIVATE, LAB_ISSUER, LAB_KEY_ID, LAB_EFFECT,
    public_bytes, receipt_for, SignedAdapter,
)
from test_atlasquant_aion_execution_outbox import policy, synthetic_lab_first_attempt_reservation


WITNESS_PRIVATE = Ed25519PrivateKey.from_private_bytes(b"\x09" * 32)
ATTACKER_PRIVATE = Ed25519PrivateKey.from_private_bytes(b"\x0a" * 32)
WITNESS_KEY_ID = "witness-key-lab"
WITNESS_ISSUER = "independent-witness-synthetic"


class SyntheticWitness:
    """Fake in-memory custodian: NOT rollback-resistant or independently run."""
    def __init__(self):
        self.seen = set()
        self.sequence = 0
        self.calls = 0
        self.offline = False
        self.stale_reply = False
        self.saved = None
        self.patch = {}
        self.tamper_after_signature = {}
        self.signer = WITNESS_PRIVATE

    def __call__(self, challenge, request):
        self.calls += 1
        if self.offline:
            raise OSError("witness unreachable")
        if self.stale_reply and self.saved:
            return self.saved
        if request["receipt_id"] in self.seen:
            return {"denied": "ALREADY_RESERVED"}
        self.sequence += 1
        payload = {
            "schema": SCHEMA,
            "issuer": WITNESS_ISSUER,
            "key_id": WITNESS_KEY_ID,
            "challenge": challenge,
            "witness_sequence": self.sequence,
            "issued_at": NOW.isoformat(),
            "expires_at": (NOW + timedelta(seconds=50)).isoformat(),
            "admission": "RESERVED",
            **request,
        }
        payload.update(self.patch)
        signature = base64.b64encode(
            self.signer.sign(DOMAIN + canonical_bytes(payload))).decode("ascii")
        payload.update(self.tamper_after_signature)
        proof = {"payload": payload, "signature": signature}
        self.saved = proof
        self.seen.add(request["receipt_id"])
        return proof


class A179WitnessGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = SQLiteChatStore(Path(self.tmp.name) / "db.sqlite3")
        self.addCleanup(self.store.close)
        self.scope = Scope("lab-owner", "lab-tenant", "lab-workspace")
        self.witness = SyntheticWitness()

    def gate(self, *, witness=None, witness_key=None, provider_key=None,
             revoked=False, high_water=0):
        return WitnessedReceiptGateLab(
            trusted_provider_keys={
                LAB_KEY_ID: {"issuer": LAB_ISSUER,
                             "public_key": public_bytes(
                                 LAB_PRIVATE if provider_key is None
                                 else provider_key)}},
            witness_key_id=WITNESS_KEY_ID,
            witness_issuer=WITNESS_ISSUER,
            witness_public_key=public_bytes(
                WITNESS_PRIVATE if witness_key is None else witness_key),
            witness_provider=self.witness if witness is None else witness,
            witness_revoked=revoked, high_water=high_water,
            now=NOW + timedelta(seconds=2),
        )

    def claimed(self, gate, *, intent="once"):
        out = ExecutionOutbox(self.store, self.scope, evidence_verifier=gate,
            first_attempt_guard=synthetic_lab_first_attempt_reservation)
        row = out.enqueue(intent_ref=intent, action="send_email",
            payload={"to": "example.invalid", "body": "lab"},
            aggregate_key=intent, policy_version="policy-v1",
            authorization_ref="approval-1", created_at=NOW,
            valid_until=NOW + timedelta(minutes=5))
        claim = out.claim_next("worker1", now=NOW, lease_seconds=60)
        self.assertEqual(claim["idempotency_key"], row["idempotency_key"])
        return out, row

    def dispatch(self, out, row, receipt, *, mode="confirmed",
                 effect_ref=LAB_EFFECT):
        adapter = SignedAdapter(receipt, mode=mode, effect_ref=effect_ref)
        result = out.dispatch_claimed(
            row["idempotency_key"], worker_id="worker1",
            authorize=policy(self.scope), adapter=adapter,
            now=NOW + timedelta(seconds=1))
        return result, adapter

    def test_01_two_separate_valid_keys_accept_synthetic_receipt(self):
        out,row=self.claimed(self.gate())
        state,adapter=self.dispatch(out,row,receipt_for(row))
        self.assertEqual(state["state"],"CONFIRMED")
        self.assertEqual(out.effect_count(),1)
        self.assertEqual(adapter.send_calls,1)
        print("A179_TWO_SIGNERS_SYNTHETIC=CONFIRMED_LAB_ONLY")

    def test_02_witnessed_unknown_reconciliation_without_resend(self):
        out,row=self.claimed(self.gate())
        receipt=receipt_for(row)
        first,adapter=self.dispatch(out,row,receipt,mode="unknown")
        self.assertEqual(first["state"],"UNCERTAIN")
        recovered=out.reconcile(row["idempotency_key"],adapter=adapter,
                                authorize=policy(self.scope),
                                now=NOW+timedelta(seconds=2))
        self.assertEqual(recovered["state"],"CONFIRMED")
        self.assertEqual(adapter.send_calls,1)
        print("A179_SIGNED_WITNESS_RECONCILIATION=NO_RESEND_LAB")

    def test_03_missing_witness_denies_ledger(self):
        def missing(challenge, request):
            return None
        out,row=self.claimed(self.gate(witness=missing))
        self.assertEqual(self.dispatch(out,row,receipt_for(row))[0]["state"],"SENT")
        self.assertEqual(out.effect_count(),0)
        print("A179_WITNESS_MISSING=NO_CONFIRMATION")

    def test_04_witness_unavailable_denies_ledger(self):
        self.witness.offline=True
        out,row=self.claimed(self.gate())
        self.assertEqual(self.dispatch(out,row,receipt_for(row))[0]["state"],"SENT")
        self.assertEqual(out.effect_count(),0)
        print("A179_WITNESS_OFFLINE=NO_CONFIRMATION")

    def test_05_replayed_signed_response_challenge_denied(self):
        stale=self.witness("0"*64,{
            "kind":"EFFECT_CONFIRMED","idempotency_key":"some-id",
            "receipt_id":"stale-id","receipt_sequence":7,
            "receipt_sha256":"x"*64,"trust_sha256":"z"*64})
        self.witness.stale_reply=True
        out,row=self.claimed(self.gate())
        self.assertEqual(self.dispatch(out,row,receipt_for(row))[0]["state"],"SENT")
        self.assertEqual(out.effect_count(),0)
        print("A179_STALE_WITNESS_CHALLENGE=DENIED")

    def test_06_wrong_witness_signature_denied(self):
        self.witness.signer=ATTACKER_PRIVATE
        out,row=self.claimed(self.gate())
        self.assertEqual(self.dispatch(out,row,receipt_for(row))[0]["state"],"SENT")
        self.assertEqual(out.effect_count(),0)

    def test_07_same_key_used_by_both_signers_is_denied(self):
        with self.assertRaisesRegex(ValueError, "WITNESS_KEY_NOT_SEPARATE"):
            self.gate(witness_key=LAB_PRIVATE)

    def test_08_revoked_witness_denies(self):
        out,row=self.claimed(self.gate(revoked=True))
        self.assertEqual(self.dispatch(out,row,receipt_for(row))[0]["state"],"SENT")
        self.assertEqual(self.witness.calls,0)

    def test_09_mismatched_trust_digest_denied(self):
        self.witness.patch={"trust_sha256":"0"*64}
        out,row=self.claimed(self.gate())
        self.assertEqual(self.dispatch(out,row,receipt_for(row))[0]["state"],"SENT")

    def test_10_invalid_signature_after_signed_body_mutation_denied(self):
        self.witness.tamper_after_signature={"receipt_sha256":"f"*64}
        out,row=self.claimed(self.gate())
        self.assertEqual(self.dispatch(out,row,receipt_for(row))[0]["state"],"SENT")

    def test_11_witness_ordinal_not_above_high_water_denied(self):
        out,row=self.claimed(self.gate(high_water=1))
        self.assertEqual(self.dispatch(out,row,receipt_for(row))[0]["state"],"SENT")

    def test_12_expired_witness_proof_denied(self):
        self.witness.patch={
            "issued_at":(NOW-timedelta(minutes=3)).isoformat(),
            "expires_at":(NOW-timedelta(seconds=1)).isoformat()}
        out,row=self.claimed(self.gate())
        self.assertEqual(self.dispatch(out,row,receipt_for(row))[0]["state"],"SENT")

    def test_13_wrong_receipt_id_in_witness_proof_denied(self):
        self.witness.patch={"receipt_id":"other-receipt"}
        out,row=self.claimed(self.gate())
        self.assertEqual(self.dispatch(out,row,receipt_for(row))[0]["state"],"SENT")

    def test_14_wrong_intent_key_in_witness_proof_denied(self):
        self.witness.patch={"idempotency_key":"wrong-key"}
        out,row=self.claimed(self.gate())
        self.assertEqual(self.dispatch(out,row,receipt_for(row))[0]["state"],"SENT")

    def test_15_witness_cannot_admit_same_receipt_twice_same_process(self):
        gate=self.gate()
        out,row=self.claimed(gate)
        receipt=receipt_for(row)
        result={"accepted":True,"confirmed":True,"effect_ref":LAB_EFFECT,
                "receipt":receipt}
        self.assertTrue(gate("EFFECT_CONFIRMED",row,result))
        self.assertFalse(gate("EFFECT_CONFIRMED",row,result))

    def test_16_witness_preserves_state_across_verifier_restart(self):
        first=self.gate()
        out,row=self.claimed(first)
        result={"accepted":True,"confirmed":True,"effect_ref":LAB_EFFECT,
                "receipt":receipt_for(row)}
        self.assertTrue(first("EFFECT_CONFIRMED",row,result))
        restarted=self.gate()
        self.assertFalse(restarted("EFFECT_CONFIRMED",row,result))
        print("A179_IN_MEMORY_WITNESS_RESTART=REPLAY_DENIED_WHILE_WITNESS_INTACT")

    def test_17_witness_state_rollback_reopens_receipt_known_bypass(self):
        first=self.gate()
        out,row=self.claimed(first)
        result={"accepted":True,"confirmed":True,"effect_ref":LAB_EFFECT,
                "receipt":receipt_for(row)}
        self.assertTrue(first("EFFECT_CONFIRMED",row,result))
        # Attacker rolls back the witness's own reservation/high water state.
        self.witness.seen.clear()
        self.witness.sequence=0
        reset_gate=self.gate()
        self.assertTrue(reset_gate("EFFECT_CONFIRMED",row,result))
        print("A179_WITNESS_STATE_ROLLBACK=REPLAY_ACCEPTED_NOT_ATTESTED")

    def test_18_caller_replaces_witness_root_known_bypass(self):
        self.witness.signer=ATTACKER_PRIVATE
        out,row=self.claimed(self.gate(witness_key=ATTACKER_PRIVATE))
        self.assertEqual(self.dispatch(out,row,receipt_for(row))[0]["state"],
                         "CONFIRMED")
        print("A179_CALLER_REPINS_WITNESS_ROOT=FAKE_AUTHORITY_ACCEPTED")

    def test_19_invalid_witness_shape_denies(self):
        out,row=self.claimed(self.gate(witness=lambda c,r:{"ok":True}))
        self.assertEqual(self.dispatch(out,row,receipt_for(row))[0]["state"],"SENT")

    def test_20_witnessed_effect_zero_does_not_create_retry(self):
        out,row=self.claimed(self.gate())
        proof=receipt_for(row,kind="EFFECT_ZERO")
        state,adapter=self.dispatch(out,row,proof,mode="negative")
        self.assertEqual(state["state"],"FAILED")
        self.assertIsNone(out.claim_next("worker2",now=NOW+timedelta(seconds=2)))
        self.assertEqual(adapter.send_calls,1)
        print("A179_TWO_SIGNATURE_EFFECT_ZERO=TERMINAL_NO_RETRY_LAB")

    def test_21_negative_provider_signature_denies_without_witness(self):
        out,row=self.claimed(self.gate())
        bad=receipt_for(row,private=ATTACKER_PRIVATE)
        self.assertEqual(self.dispatch(out,row,bad)[0]["state"],"SENT")
        self.assertEqual(self.witness.calls,0)


if __name__ == "__main__":
    unittest.main()
