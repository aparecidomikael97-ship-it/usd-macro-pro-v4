"""G119: provider-like signed statements never elevate a LAB operation to GO.

Both Ed25519 private keys are test-owned on one host. The 'provider' is NOT
a provider and no execution occurred. Prove the contract refuses witness
signatures, replays, mismatched originals and missing signed reservations.
"""
import base64
from copy import deepcopy
from dataclasses import FrozenInstanceError
from hashlib import sha256

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from aion_chat.first_attempt_witness_lab import _effect_digest
from aion_chat.signed_receipt_lab import canonical_bytes
from labs.a190.g113_subprocess_witness_client_lab import WitnessProcessUnavailableLab
from labs.a190.g118_signed_witness_recovery_lab import G118SignedWitnessRecoveryLab
from labs.a190.g119_provider_evidence_separate_root_lab import (
    G119SyntheticProviderEvidenceVerifierLab,
    PROVIDER_SCHEMA, PROVIDER_DOMAIN,
)
from labs.a190.test_g115_cross_process_outbox_guard_lab import G115CrossProcessOutboxLab


class G119ProviderStatementTests(G115CrossProcessOutboxLab):
    PROVIDER_ISSUER = "synthetic-provider-g119"

    def verifier(self, *, floor=0, public_key=None):
        recovery = G118SignedWitnessRecoveryLab(
            witness_client=self.client, event_id=self.business_event_id,
            original_decision=self.original_row["decision"],
            original_sha256=self.original_digest, retained_high_water=floor,
        )
        signing = Ed25519PrivateKey.from_private_bytes(b"\x73" * 32)
        public = signing.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        return G119SyntheticProviderEvidenceVerifierLab(
            recovery_reader=recovery,
            provider_public_key=public if public_key is None else public_key,
            provider_issuer=self.PROVIDER_ISSUER,
        )

    def reserve(self, *, lost_ack=False):
        kwargs = {
            "event_id": self.business_event_id,
            "original_sha256": self.original_digest,
            "effect_digest": _effect_digest(self.original_row["decision"]),
            "idempotency_key": self.original_row["idempotency_key"],
            "owner_id": self.scope.owner_id,
            "tenant_id": self.scope.tenant_id,
            "workspace_id": self.scope.workspace_id,
        }
        return self.client.reserve(**kwargs, lost_response=lost_ack)

    def sign(self, nonce, *, claim="EXECUTED", signer=None, changes=None,
             domain=PROVIDER_DOMAIN):
        payload = {
            "schema": PROVIDER_SCHEMA,
            "issuer": self.PROVIDER_ISSUER,
            "challenge": nonce,
            "event_id": self.business_event_id,
            "original_sha256": self.original_digest,
            "owner_id": self.scope.owner_id,
            "tenant_id": self.scope.tenant_id,
            "workspace_id": self.scope.workspace_id,
            "effect_digest": _effect_digest(self.original_row["decision"]),
            "idempotency_key": self.original_row["idempotency_key"],
            "sequence": 1,
            "provider_event_ref": "synthetic-provider-ref-0001",
            "claim": claim,
        }
        if changes:
            payload.update(changes)
        signer = signer or Ed25519PrivateKey.from_private_bytes(b"\x73" * 32)
        sig = signer.sign(domain + canonical_bytes(payload))
        return {"payload": payload, "signature": base64.b64encode(sig).decode("ascii")}

    def assert_no_operational_permission(self, result):
        self.assertFalse(result.verified_real_provider)
        self.assertEqual(result.provider_outcome, "UNKNOWN")
        self.assertFalse(result.allow_send)
        self.assertFalse(result.allow_retry)
        self.assertFalse(result.may_mark_provider_confirmed)

    def test_12_signed_executed_claim_cannot_confirm_real_operation(self):
        self.reserve()
        verifier = self.verifier(floor=1)
        observed = verifier.inspect_statement(self.sign(verifier.challenge()))
        self.assertTrue(observed.signed_statement)
        self.assertEqual(observed.provider_claim, "EXECUTED")
        self.assertEqual(observed.disposition, "G119_SYNTHETIC_PROVIDER_CLAIM_ONLY")
        self.assert_no_operational_permission(observed)
        print("G119_SYNTHETIC_EXECUTED=NOT_REAL_PROVIDER_CONFIRMATION")

    def test_13_signed_rejected_claim_does_not_authorize_retry(self):
        self.reserve()
        verifier = self.verifier(floor=1)
        verdict = verifier.inspect_statement(
            self.sign(verifier.challenge(), claim="REJECTED")
        )
        self.assertEqual(verdict.provider_claim, "REJECTED")
        self.assert_no_operational_permission(verdict)
        print("G119_SYNTHETIC_REJECTED=NO_AUTOMATIC_RETRY")

    def test_14_pending_provider_claim_does_not_authorize_send(self):
        self.reserve()
        verifier = self.verifier(floor=1)
        verdict = verifier.inspect_statement(
            self.sign(verifier.challenge(), claim="PENDING")
        )
        self.assertEqual(verdict.provider_claim, "PENDING")
        self.assert_no_operational_permission(verdict)
        print("G119_SYNTHETIC_PENDING=PROVIDER_UNKNOWN_NO_SEND")

    def test_15_witness_signature_cannot_impersonate_provider(self):
        self.reserve()
        verifier = self.verifier(floor=1)
        witness_signer = Ed25519PrivateKey.from_private_bytes(self.seed)
        forged = self.sign(verifier.challenge(), signer=witness_signer)
        verdict = verifier.inspect_statement(forged)
        self.assertFalse(verdict.signed_statement)
        self.assert_no_operational_permission(verdict)
        print("G119_WITNESS_ROOT_SIGNATURE=NOT_PROVIDER_ROOT")

    def test_16_domain_separator_prevents_cross_protocol_acceptance(self):
        self.reserve()
        verifier = self.verifier(floor=1)
        forged = self.sign(verifier.challenge(), domain=b"OTHER-PROTOCOL\x00")
        verdict = verifier.inspect_statement(forged)
        self.assertFalse(verdict.signed_statement)
        self.assert_no_operational_permission(verdict)
        print("G119_OTHER_SIGNATURE_DOMAIN=DENIED")

    def test_17_old_challenge_cannot_be_replayed_or_reopened(self):
        self.reserve()
        verifier = self.verifier(floor=1)
        nonce = verifier.challenge()
        old = self.sign(nonce)
        first = verifier.inspect_statement(old)
        self.assertEqual(first.provider_claim, "EXECUTED")
        replay_without_challenge = verifier.inspect_statement(old)
        self.assertFalse(replay_without_challenge.signed_statement)
        fresh_nonce = verifier.challenge()
        with self.assertRaisesRegex(RuntimeError, "G119_OUTSTANDING_CHALLENGE"):
            verifier.challenge()
        self.assertNotEqual(fresh_nonce, nonce)
        repeated = verifier.inspect_statement(old)
        self.assertFalse(repeated.signed_statement)
        self.assert_no_operational_permission(repeated)
        print("G119_REPLAYED_PROVIDER_STATEMENT=DENIED_WITH_FRESH_NONCE")

    def test_18_signed_original_identity_scope_request_and_sequence_bound(self):
        self.reserve()
        altered = {
            "event_id": sha256(b"other-event").hexdigest(),
            "original_sha256": "f" * 64,
            "effect_digest": "e" * 64,
            "idempotency_key": "d" * 64,
            "owner_id": "forged-owner",
            "tenant_id": "forged-tenant",
            "workspace_id": "forged-workspace",
            "sequence": 2,
        }
        for field, value in altered.items():
            with self.subTest(field=field):
                verifier = self.verifier(floor=1)
                statement = self.sign(
                    verifier.challenge(), changes={field: value}
                )
                verdict = verifier.inspect_statement(statement)
                self.assertFalse(verdict.signed_statement)
                self.assertEqual(verdict.provider_claim, "UNVERIFIED")
                self.assert_no_operational_permission(verdict)
        print("G119_SIGNED_OTHER_BUSINESS_EVENT=DENIED_ALL_FIELDS")

    def test_19_signed_provider_statement_without_reservation_denied(self):
        verifier = self.verifier(floor=0)
        result = verifier.inspect_statement(self.sign(verifier.challenge()))
        self.assertEqual(result.disposition, "G119_WITNESS_RESERVATION_NOT_VERIFIED")
        self.assert_no_operational_permission(result)
        print("G119_PROVIDER_CLAIM_WITHOUT_WITNESS_COMMIT=DENIED")

    def test_20_witness_rollback_after_statement_forbids_any_claim(self):
        original = self.witness_db.read_bytes()
        self.reserve()
        verifier = self.verifier(floor=1)
        signed = self.sign(verifier.challenge())
        self.witness_db.write_bytes(original)
        result = verifier.inspect_statement(signed)
        self.assertEqual(result.disposition, "G119_WITNESS_RESERVATION_NOT_VERIFIED")
        self.assert_no_operational_permission(result)
        print("G119_HOST_ROLLBACK_BEFORE_RECONCILIATION=DENIED")

    def test_21_malformed_invalid_status_and_signature_denied(self):
        self.reserve()
        for change in (
            {"claim": "CANCEL_AND_RETRY"},
            {"provider_event_ref": ""},
            {"provider_event_ref": "unsafe\nref"},
            {"issuer": "attacker"},
            {"schema": "AION:G113:PROCESS_WITNESS:V1"},
            {"sequence": True},
        ):
            verifier = self.verifier(floor=1)
            verdict = verifier.inspect_statement(
                self.sign(verifier.challenge(), changes=change)
            )
            self.assertFalse(verdict.signed_statement)
            self.assert_no_operational_permission(verdict)
        verifier = self.verifier(floor=1)
        unsigned = self.sign(verifier.challenge())
        unsigned["signature"] = "not-base64***"
        verdict = verifier.inspect_statement(unsigned)
        self.assertFalse(verdict.signed_statement)
        self.assert_no_operational_permission(verdict)
        print("G119_MALFORMED_OR_WRONG_PROVIDER_ISSUER=DENIED")

    def test_22_missing_provider_pin_and_reused_witness_pin_denied(self):
        with self.assertRaisesRegex(ValueError, "G119_PROVIDER_PUBLIC_PIN_REQUIRED"):
            self.verifier(public_key=b"")
        with self.assertRaisesRegex(ValueError, "G119_PROVIDER_WITNESS_KEY_MUST_DIFFER"):
            self.verifier(public_key=self.pinned_public_key)
        self.assertEqual(self.client.status(self.business_event_id)["count"], 0)
        print("G119_PROVIDER_AND_WITNESS_PINS_MUST_DIFFER")

    def test_23_lost_witness_ack_then_statement_does_not_reopen_send(self):
        with self.assertRaises(WitnessProcessUnavailableLab):
            self.reserve(lost_ack=True)
        verifier = self.verifier(floor=1)
        claim = verifier.inspect_statement(self.sign(verifier.challenge()))
        self.assertEqual(claim.provider_claim, "EXECUTED")
        self.assert_no_operational_permission(claim)
        self.assertEqual(self.client.status(self.business_event_id)["count"], 1)
        print("G119_LOST_ACK_AND_SYNTHETIC_PROVIDER_CLAIM=NO_SEND_NO_CONFIRM")


if __name__ == "__main__":
    import unittest
    unittest.main()
