"""A178: signed receipt tests with deterministic synthetic keys and no egress.

The all-7 test private keys here are PUBLIC LAB FIXTURES and never real issuer
credentials. A green test does not establish production provider trust.
"""
import base64
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from aion_chat.signed_receipt_lab import (
    SCHEMA, DOMAIN, PinnedEd25519ReceiptLab, canonical_bytes, decision_sha256,
)
from atlasquant_aion_execution_outbox import ExecutionOutbox
from test_atlasquant_aion_execution_outbox import NOW, policy


LAB_PRIVATE = Ed25519PrivateKey.from_private_bytes(b"\x07" * 32)
ATTACKER_PRIVATE = Ed25519PrivateKey.from_private_bytes(b"\x08" * 32)
LAB_ISSUER = "lab-synthetic-issuer"
LAB_KEY_ID = "issuer-lab-key-1"
LAB_EFFECT = "fake-effect-1"


def public_bytes(private):
    return private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw)


def receipt_for(intent, *, private=LAB_PRIVATE, kind="EFFECT_CONFIRMED",
                issuer=LAB_ISSUER, key_id=LAB_KEY_ID, effect_ref=LAB_EFFECT,
                sequence=10, issued_at=None, expires_at=None, overrides=None):
    dec = intent["decision"]
    payload = {
        "schema": SCHEMA,
        "kind": kind,
        "issuer": issuer,
        "key_id": key_id,
        "receipt_id": "receipt-lab-1",
        "nonce": "nonce-lab-000001",
        "sequence": sequence,
        "issued_at": issued_at or NOW.isoformat(),
        "expires_at": expires_at or (NOW + timedelta(minutes=3)).isoformat(),
        "idempotency_key": intent["idempotency_key"],
        "decision_sha256": decision_sha256(dec),
        "owner_id": dec["owner_id"],
        "tenant_id": dec["tenant_id"],
        "workspace_id": dec["workspace_id"],
        "effect_ref": effect_ref if kind == "EFFECT_CONFIRMED" else "",
    }
    payload.update(overrides or {})
    signature = base64.b64encode(
        private.sign(DOMAIN + canonical_bytes(payload))).decode("ascii")
    return {"payload": payload, "signature": signature}


class SignedAdapter:
    def __init__(self, receipt, *, mode="confirmed", effect_ref=LAB_EFFECT):
        self.receipt = receipt
        self.mode = mode
        self.effect_ref = effect_ref
        self.send_calls = 0
        self.reconcile_calls = 0

    def send(self, decision, key):
        self.send_calls += 1
        if self.mode == "unknown":
            raise TimeoutError("simulated lost reply")
        if self.mode == "negative":
            return {"accepted": False, "retryable": False,
                    "receipt": self.receipt}
        return {"accepted": True, "confirmed": True,
                "effect_ref": self.effect_ref, "receipt": self.receipt}

    def reconcile(self, key, decision):
        self.reconcile_calls += 1
        return {"found": True, "confirmed": True,
                "effect_ref": self.effect_ref, "receipt": self.receipt}


class A178SignedReceiptLabTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = SQLiteChatStore(Path(self.tmp.name) / "intent.sqlite")
        self.addCleanup(self.store.close)
        self.scope = Scope("owner-lab", "tenant-lab", "workspace-lab")

    def verifier(self, *, raw=None, revoked=(), high_water=0, issuer=LAB_ISSUER):
        return PinnedEd25519ReceiptLab(
            trusted_keys={LAB_KEY_ID: {
                "issuer": issuer,
                "public_key": public_bytes(LAB_PRIVATE) if raw is None else raw,
            }},
            revoked_keys=revoked, high_water=high_water,
            now=NOW + timedelta(seconds=2),
        )

    def create_outbox(self, verifier, *, scope=None, ref="only-intent"):
        sc = scope or self.scope
        outbox = ExecutionOutbox(self.store, sc, evidence_verifier=verifier)
        item = outbox.enqueue(
            intent_ref=ref, action="send_email",
            payload={"to":"example.invalid", "template":"demo"},
            aggregate_key="account-"+ref, policy_version="policy-v1",
            authorization_ref="approval-1", created_at=NOW,
            valid_until=NOW+timedelta(minutes=5),
        )
        self.assertEqual(
            outbox.claim_next("worker1", now=NOW, lease_seconds=60)["idempotency_key"],
            item["idempotency_key"])
        return outbox, item

    def dispatch(self, outbox, item, adapter, *, scope=None):
        return outbox.dispatch_claimed(
            item["idempotency_key"],worker_id="worker1",
            authorize=policy(scope or self.scope),adapter=adapter,
            now=NOW+timedelta(seconds=1))

    def test_01_valid_pinned_signature_produces_lab_confirmation(self):
        outbox,item=self.create_outbox(self.verifier())
        adapter=SignedAdapter(receipt_for(item))
        result=self.dispatch(outbox,item,adapter)
        self.assertEqual(result["state"],"CONFIRMED")
        self.assertEqual(outbox.effect_count(),1)
        self.assertEqual(adapter.send_calls,1)
        print("A178_VALID_PINNED_LAB_SIGNATURE=CONFIRMED_SYNTHETIC_ONLY")

    def test_02_valid_reconcile_after_unknown_never_resends(self):
        outbox,item=self.create_outbox(self.verifier())
        adapter=SignedAdapter(receipt_for(item),mode="unknown")
        self.assertEqual(self.dispatch(outbox,item,adapter)["state"],"UNCERTAIN")
        output=outbox.reconcile(item["idempotency_key"],adapter=adapter,
                                 authorize=policy(self.scope),
                                 now=NOW+timedelta(seconds=2))
        self.assertEqual(output["state"],"CONFIRMED")
        self.assertEqual(adapter.send_calls,1)
        self.assertEqual(outbox.effect_count(),1)
        print("A178_SIGNED_RECONCILIATION=CONFIRMED_NO_RESEND_LAB")

    def test_03_unpinned_signing_key_cannot_authorize_receipt(self):
        outbox,item=self.create_outbox(self.verifier())
        fake=receipt_for(item,private=ATTACKER_PRIVATE,key_id="attacker-key-2",
                         issuer="fake-issuer")
        result=self.dispatch(outbox,item,SignedAdapter(fake))
        self.assertEqual(result["state"],"SENT")
        self.assertEqual(outbox.effect_count(),0)
        print("A178_UNPINNED_KEY=DENIED")

    def test_04_issuer_mismatch_even_with_valid_signature_denied(self):
        outbox,item=self.create_outbox(self.verifier())
        fake=receipt_for(item,issuer="forged-issuer")
        self.assertEqual(self.dispatch(outbox,item,SignedAdapter(fake))["state"],"SENT")
        self.assertEqual(outbox.effect_count(),0)

    def test_05_tampered_signed_effect_ref_is_denied(self):
        outbox,item=self.create_outbox(self.verifier())
        fake=receipt_for(item)
        fake["payload"]["effect_ref"]="modified-effect"
        self.assertEqual(self.dispatch(outbox,item,SignedAdapter(fake))["state"],"SENT")
        self.assertEqual(outbox.effect_count(),0)

    def test_06_cross_scope_replay_of_signed_receipt_is_denied(self):
        outbox,item=self.create_outbox(self.verifier())
        borrowed=receipt_for(item)
        other_scope=Scope("other-owner","tenant-other","workspace-other")
        second,item2=self.create_outbox(self.verifier(),scope=other_scope,ref="only-intent")
        self.assertEqual(
            self.dispatch(second,item2,SignedAdapter(borrowed),scope=other_scope)["state"],
            "SENT")
        self.assertEqual(second.effect_count(),0)
        print("A178_CROSS_SCOPE_REPLAY=DENIED")

    def test_07_cross_intent_replay_in_same_scope_is_denied(self):
        original,item=self.create_outbox(self.verifier())
        borrowed=receipt_for(item)
        second,item2=self.create_outbox(self.verifier(),ref="another-event")
        self.assertNotEqual(item2["idempotency_key"],item["idempotency_key"])
        self.assertEqual(self.dispatch(second,item2,SignedAdapter(borrowed))["state"],"SENT")
        self.assertEqual(second.effect_count(),0)

    def test_08_expired_receipt_is_denied(self):
        outbox,item=self.create_outbox(self.verifier())
        fake=receipt_for(item, issued_at=(NOW-timedelta(minutes=5)).isoformat(),
                         expires_at=(NOW-timedelta(seconds=1)).isoformat())
        self.assertEqual(self.dispatch(outbox,item,SignedAdapter(fake))["state"],"SENT")
        self.assertEqual(outbox.effect_count(),0)

    def test_09_revoked_pinned_key_is_denied(self):
        outbox,item=self.create_outbox(self.verifier(revoked=(LAB_KEY_ID,)))
        self.assertEqual(self.dispatch(outbox,item,
                         SignedAdapter(receipt_for(item)))["state"],"SENT")
        self.assertEqual(outbox.effect_count(),0)
        print("A178_REVOKED_KEY=DENIED")

    def test_10_high_water_blocks_stale_receipt_sequence(self):
        outbox,item=self.create_outbox(self.verifier(high_water=10))
        self.assertEqual(self.dispatch(outbox,item,
                         SignedAdapter(receipt_for(item)))["state"],"SENT")
        self.assertEqual(outbox.effect_count(),0)
        print("A178_STALE_SEQUENCE=DENIED_WITH_LAB_SNAPSHOT")

    def test_11_invalid_signature_encoding_is_denied(self):
        outbox,item=self.create_outbox(self.verifier())
        bad=receipt_for(item)
        bad["signature"]="@invalid!"
        self.assertEqual(self.dispatch(outbox,item,SignedAdapter(bad))["state"],"SENT")
        self.assertEqual(outbox.effect_count(),0)

    def test_12_signed_effect_zero_terminal_no_retry(self):
        outbox,item=self.create_outbox(self.verifier())
        negative=receipt_for(item,kind="EFFECT_ZERO")
        out=self.dispatch(outbox,item,SignedAdapter(negative,mode="negative"))
        self.assertEqual(out["state"],"FAILED")
        self.assertIsNone(outbox.claim_next("worker2",now=NOW+timedelta(seconds=2)))
        print("A178_SIGNED_EFFECT_ZERO=FAILED_NO_AUTO_RETRY_LAB_ONLY")

    def test_13_wrong_signing_key_for_pinned_id_fails(self):
        outbox,item=self.create_outbox(self.verifier())
        fake=receipt_for(item,private=ATTACKER_PRIVATE)
        self.assertEqual(self.dispatch(outbox,item,SignedAdapter(fake))["state"],"SENT")
        self.assertEqual(outbox.effect_count(),0)

    def test_14_signature_reused_with_other_effect_response_fails(self):
        outbox,item=self.create_outbox(self.verifier())
        fake=receipt_for(item)
        self.assertEqual(
            self.dispatch(outbox,item,SignedAdapter(fake,effect_ref="other-effect"))["state"],
            "SENT")
        self.assertEqual(outbox.effect_count(),0)

    def test_15_attacker_controlled_pinning_still_bypasses_independence(self):
        # CRITICAL NEGATIVE RESULT: cryptographic validity is not independent
        # attestation when the verifier's trusted root is caller-controlled.
        verifier=self.verifier(raw=public_bytes(ATTACKER_PRIVATE),issuer="fake-issuer")
        outbox,item=self.create_outbox(verifier)
        fake=receipt_for(item,private=ATTACKER_PRIVATE,issuer="fake-issuer")
        self.assertEqual(self.dispatch(outbox,item,SignedAdapter(fake))["state"],
                         "CONFIRMED")
        print("A178_CALLER_CONTROLS_TRUST_ROOT=FAKE_PROOF_ACCEPTED_NOT_EXTERNAL")

    def test_16_self_attested_high_water_not_rollback_resistant(self):
        # New verifier object with lower local min_sequence can reaccept an
        # old signed receipt; no independent monotonic witness exists.
        receipt=None
        first=self.verifier(high_water=10)
        outbox,item=self.create_outbox(first)
        receipt=receipt_for(item,sequence=10)
        self.assertEqual(self.dispatch(outbox,item,SignedAdapter(receipt))["state"],"SENT")
        restarted=self.verifier(high_water=0)
        self.assertTrue(restarted("EFFECT_CONFIRMED",item,{
            "confirmed":True, "effect_ref":LAB_EFFECT,"receipt":receipt}))
        print("A178_ROLLBACK_OF_TRUST_SNAPSHOT=REPLAY_ACCEPTED_NOT_ATTESTED")


if __name__ == "__main__":
    unittest.main()
