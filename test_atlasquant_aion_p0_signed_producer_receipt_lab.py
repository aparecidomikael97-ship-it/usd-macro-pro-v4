"""Adversarial signed producer receipt P0 contracts: ALWAYS DENY operational effect.

Ephemeral Ed25519 keys are generated only within runner fixtures. Even perfectly
signed COMMITTED/NO_EFFECT claims do not establish provider custody, real
commit, provider-enforced late-effect fence, durable nonce/high-water, or retry.
"""
import base64
from copy import deepcopy
import unittest
from datetime import datetime

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from atlasquant_aion_p0_signed_producer_receipt_lab import (
    SCHEMA, canonical_receipt_bytes, inspect_signed_producer_receipt_lab,
)

NOW = "2026-10-19T18:00:00Z"


def b64(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


class SignedReceiptP0LabTests(unittest.TestCase):
    def setUp(self):
        self.secret = Ed25519PrivateKey.generate()
        pub = self.secret.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        self.pin = {
            "issuer_id": "synthetic-issuer",
            "key_id": "synthetic-key-01",
            "public_key_b64": b64(pub),
            "status": "ACTIVE",
            "key_version": 1,
        }
        self.row = {
            "schema": SCHEMA, "kind": "POSITIVE_COMMITTED",
            "owner_id": "owner-fixture", "tenant_id": "tenant-a",
            "workspace_id": "workspace-a", "host_id": "host-a",
            "producer_issuer_id": "synthetic-issuer",
            "producer_account_id": "account-a",
            "producer_key_id": "synthetic-key-01", "producer_key_version": 1,
            "action_class": "send_email", "intent_digest": "a" * 64,
            "idempotency_key": "idem-test-001", "attempt": 1, "epoch": 1,
            "witness_sequence": 1, "witness_head": "b" * 64,
            "nonce": "receipt-nonce-001", "receipt_id": "receipt-001",
            "effect_or_fence_ref": "effect-ref-001",
            "issued_at": "2026-10-19T17:59:30Z",
            "expires_at": "2026-10-19T18:01:30Z",
        }
        self.scope_keys = (
            "owner_id", "tenant_id", "workspace_id", "host_id",
            "producer_issuer_id", "producer_account_id", "producer_key_id",
            "producer_key_version", "action_class", "intent_digest",
            "idempotency_key", "attempt", "epoch",
        )
        self.scope = {k: self.row[k] for k in self.scope_keys}

    def sign(self, row=None, signer=None):
        row = deepcopy(row if row is not None else self.row)
        return {
            "receipt": row,
            "signature_b64": b64((signer or self.secret).sign(canonical_receipt_bytes(row))),
        }

    def evaluate(self, claim, *, pin=None, scope=None, witness_head=None,
                 sequence=0, used=frozenset(), now=NOW):
        pin = self.pin if pin is None else pin
        scope = self.scope if scope is None else scope
        before = deepcopy((claim, pin, scope))
        result = inspect_signed_producer_receipt_lab(
            claim, pinned_issuer=pin, expected_scope=scope,
            expected_witness_head=witness_head if witness_head is not None else "b"*64,
            previous_witness_sequence=sequence,
            used_receipt_ids=used, now=now
        )
        self.assertEqual((claim, pin, scope), before)
        self.assertEqual(result["state"], "BLOCKED")
        for key in (
            "issuer_authenticated", "independent_witness_verified",
            "producer_effect_confirmed", "producer_no_effect_fence_confirmed",
            "nonce_durably_consumed", "high_water_independently_verified",
            "receipt_admitted", "unknown_outcome_cleared",
            "automatic_retry_allowed", "effect_ledger_authorized",
            "saga_advance_authorized", "writer_called", "external_action_executed",
            "executes_action",
        ):
            self.assertIs(result[key], False, key)
        return result

    def expects(self, reason, claim, **kwargs):
        result = self.evaluate(claim, **kwargs)
        self.assertEqual(result["reason"], reason)
        return result

    def test_01_signed_positive_is_only_math_consistent(self):
        r=self.expects("P0_CRYPTO_CONSISTENT_EXTERNAL_EFFECT_UNVERIFIED", self.sign())
        self.assertTrue(r["signature_math_consistent"])

    def test_02_signed_negative_fence_claim_cannot_authorize_retry(self):
        row = deepcopy(self.row)
        row["kind"] = "NEGATIVE_NO_EFFECT_FENCED"
        row["effect_or_fence_ref"] = "alleged-fence-001"
        r=self.expects("P0_CRYPTO_CONSISTENT_EXTERNAL_EFFECT_UNVERIFIED", self.sign(row))
        self.assertTrue(r["signature_math_consistent"])
        self.assertFalse(r["automatic_retry_allowed"])
        self.assertFalse(r["producer_no_effect_fence_confirmed"])

    def test_03_attacker_key_is_rejected(self):
        attacker=Ed25519PrivateKey.generate()
        self.expects("P0_SIGNATURE_INVALID", self.sign(signer=attacker))

    def test_04_issuer_key_replacement_invalidates_signature(self):
        alternate=Ed25519PrivateKey.generate()
        bad=deepcopy(self.pin)
        bad["public_key_b64"]=b64(alternate.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw))
        self.expects("P0_SIGNATURE_INVALID", self.sign(), pin=bad)

    def test_05_signature_does_not_survive_receipt_change(self):
        claimed=self.sign()
        claimed["receipt"]["effect_or_fence_ref"]="another-ref"
        self.expects("P0_SIGNATURE_INVALID", claimed)

    def test_06_wrong_kind_even_if_resigned_is_domain_rejected(self):
        row=deepcopy(self.row); row["kind"]="OUTCOME_UNKNOWN"
        self.expects("P0_DOMAIN_OR_OUTCOME_KIND_INVALID", self.sign(row))

    def test_07_wrong_schema_rejected(self):
        row=deepcopy(self.row); row["schema"]="OTHER_DOMAIN"
        self.expects("P0_DOMAIN_OR_OUTCOME_KIND_INVALID", self.sign(row))

    def test_08_positive_cannot_relabel_negative_with_same_signature(self):
        claimed=self.sign()
        claimed["receipt"]["kind"]="NEGATIVE_NO_EFFECT_FENCED"
        claimed["receipt"]["effect_or_fence_ref"]="fake-fence"
        self.expects("P0_SIGNATURE_INVALID", claimed)

    def test_09_nonce_replayed_in_fixture_registry(self):
        self.expects("P0_RECEIPT_REPLAYED", self.sign(), used=frozenset({"receipt-001"}))

    def test_10_counter_rollback(self):
        self.expects("P0_WITNESS_SEQUENCE_ROLLBACK_OR_GAP", self.sign(), sequence=1)

    def test_11_counter_gap(self):
        row=deepcopy(self.row); row["witness_sequence"]=3
        self.expects("P0_WITNESS_SEQUENCE_ROLLBACK_OR_GAP", self.sign(row))

    def test_12_witness_head_not_canonical(self):
        self.expects("P0_WITNESS_HEAD_MISMATCH", self.sign(), witness_head="c"*64)

    def test_13_untrusted_key_revoked(self):
        pin=deepcopy(self.pin); pin["status"]="REVOKED"
        self.expects("P0_ISSUER_REVOKED_OR_INACTIVE", self.sign(), pin=pin)

    def test_14_wrong_issuer_id(self):
        pin=deepcopy(self.pin); pin["issuer_id"]="another-issuer"
        self.expects("P0_ISSUER_PIN_MISMATCH", self.sign(), pin=pin)

    def test_15_wrong_issuer_key_version(self):
        pin=deepcopy(self.pin); pin["key_version"]=2
        self.expects("P0_ISSUER_PIN_MISMATCH", self.sign(), pin=pin)

    def test_16_wrong_issuer_key_id(self):
        pin=deepcopy(self.pin); pin["key_id"]="other-key"
        self.expects("P0_ISSUER_PIN_MISMATCH", self.sign(), pin=pin)

    def test_17_tenant_crossed(self):
        row=deepcopy(self.row); row["tenant_id"]="tenant-b"
        self.expects("P0_SCOPE_MISMATCH:tenant_id", self.sign(row))

    def test_18_owner_crossed(self):
        row=deepcopy(self.row); row["owner_id"]="attacker"
        self.expects("P0_SCOPE_MISMATCH:owner_id", self.sign(row))

    def test_19_action_changed(self):
        row=deepcopy(self.row); row["action_class"]="send_message"
        self.expects("P0_SCOPE_MISMATCH:action_class", self.sign(row))

    def test_20_intent_changed(self):
        row=deepcopy(self.row); row["intent_digest"]="c"*64
        self.expects("P0_SCOPE_MISMATCH:intent_digest", self.sign(row))

    def test_21_idempotency_changed(self):
        row=deepcopy(self.row); row["idempotency_key"]="another-key"
        self.expects("P0_SCOPE_MISMATCH:idempotency_key", self.sign(row))

    def test_22_expired(self):
        self.expects("P0_TIME_WINDOW_INVALID", self.sign(), now="2026-10-19T18:01:30Z")

    def test_23_too_long_window(self):
        row=deepcopy(self.row); row["expires_at"]="2026-10-19T18:09:30Z"
        self.expects("P0_TIME_WINDOW_INVALID", self.sign(row))

    def test_24_future_timestamp(self):
        row=deepcopy(self.row); row["issued_at"]="2026-10-19T18:00:01Z"
        self.expects("P0_TIME_WINDOW_INVALID", self.sign(row))

    def test_25_missing_receipt(self):
        self.expects("P0_ENVELOPE_INVALID", {"signature_b64":"bogus"})

    def test_26_fake_proof_flag(self):
        claimed=self.sign(); claimed["receipt"]["signature_verified"]=True
        self.expects("P0_RECEIPT_FIELDS_INVALID", claimed)

    def test_27_bool_attempt_blocked(self):
        row=deepcopy(self.row); row["attempt"]=True
        self.expects("P0_COUNTER_INVALID:attempt", self.sign(row))

    def test_28_fake_local_failed_does_not_clear_unknown(self):
        row=deepcopy(self.row); row["kind"]="FAILED"
        self.expects("P0_DOMAIN_OR_OUTCOME_KIND_INVALID", self.sign(row))

    def test_29_nonce_state_is_just_fixture_and_replays_remain_denied(self):
        claim=self.sign()
        a=self.evaluate(claim)
        b=self.evaluate(claim)
        self.assertTrue(a["signature_math_consistent"] and b["signature_math_consistent"])
        self.assertFalse(a["nonce_durably_consumed"])
        self.assertFalse(b["automatic_retry_allowed"])

    def test_30_extra_untrusted_private_key_blocked(self):
        claim=self.sign(); claim["private_key"]="NEVER_CAPTURE"
        self.expects("P0_ENVELOPE_INVALID", claim)

    def test_31_fake_claimed_positive_without_signature(self):
        claim=self.sign(); claim["signature_b64"]="a"*86
        self.expects("P0_SIGNATURE_INVALID", claim)

    def test_32_missing_prior_witness_sequence_blocks(self):
        self.expects("P0_WITNESS_SEQUENCE_ROLLBACK_OR_GAP", self.sign(), sequence=-1)
