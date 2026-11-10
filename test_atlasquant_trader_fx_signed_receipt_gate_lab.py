"""Ephemeral local test keys only; no real external timestamp authority used."""
import base64
from dataclasses import replace
from datetime import timedelta, timezone
from hashlib import sha256
import unittest

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    HAS_ED25519_VERIFIER = True
except ImportError:
    HAS_ED25519_VERIFIER = False

from atlasquant_trader_fx_forecast_precommit_lab import build_fx_precommit_chain_lab
from atlasquant_trader_fx_signed_receipt_gate_lab import (
    SignedTimestampReceiptClaim, canonical_signed_receipt_payload_lab,
    inspect_signed_fx_receipt_lab as inspect,
)
from test_atlasquant_trader_fx_forecast_price_join_lab import setup

NONCE = "a" * 32
SIGNER = "LAB_TEST_SIGNER"


def signed_fixture(*, row=None, chain=None, accepted_at=None, side="UP"):
    if row is None or chain is None:
        row, chain, _, _, _, evaluation = setup(side=side)
    else:
        evaluation = row.outcome_end_at + timedelta(hours=1)
    key = Ed25519PrivateKey.generate()
    pub_raw = key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    receipt = SignedTimestampReceiptClaim(
        receipt_id="LAB_REC_001", signer_id=SIGNER,
        opportunity_id=row.opportunity_id,
        entry_sha256_claim=chain["chain_entries"][0]["entry_sha256_claim"],
        nonce_hex=NONCE,
        accepted_at=accepted_at or row.prediction_issued_at + timedelta(seconds=30),
        signature_b64="",
    )
    payload = canonical_signed_receipt_payload_lab(receipt)
    assert payload is not None
    receipt = replace(receipt, signature_b64=base64.b64encode(key.sign(payload)).decode("ascii"))
    return row, chain, receipt, pub_raw, evaluation


def run(row, chain, receipt, pub_raw, evaluation, *,
        provided_head=None, expected_nonce=NONCE, expected_signer=SIGNER,
        supplied_fingerprint=None):
    return inspect(
        [row], chain["chain_entries"],
        chain["head_sha256_claim"] if provided_head is None else provided_head,
        opportunity_id=row.opportunity_id, signed_receipt=receipt,
        expected_nonce_hex=expected_nonce,
        expected_signer_id=expected_signer,
        supplied_public_key_raw=pub_raw,
        supplied_public_key_sha256=(
            sha256(pub_raw).hexdigest()
            if supplied_fingerprint is None else supplied_fingerprint),
        evaluated_at_utc=evaluation)


@unittest.skipUnless(HAS_ED25519_VERIFIER, "optional cryptography library unavailable")
class SignedReceiptGateLabTests(unittest.TestCase):
    def no_go(self, r):
        for key in ("signer_identity_independently_authenticated",
                    "public_key_previously_pinned_independently",
                    "timestamp_authority_independently_trusted",
                    "server_clock_independently_authenticated",
                    "historical_pre_event_prediction_proven",
                    "economic_vintages_independently_verified",
                    "can_feed_validated_backtest", "publishable",
                    "trade_authorized", "worker_enabled", "scheduler_enabled"):
            self.assertIs(r[key], False, key)
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertIsNone(r["validated_accuracy"])
        self.assertIsNone(r["calibrated_probability"])
        self.assertEqual((r["http_requests"], r["file_writes"],
                          r["new_cost_brl"]), (0, 0, 0))

    def blocked(self, result, reason):
        self.assertEqual(result["state"], "LAB_SIGNED_RECEIPT_BLOCKED")
        self.assertEqual(result["reason"], reason)
        self.assertIs(result["detached_ed25519_signature_valid_for_supplied_key"], False)
        self.no_go(result)

    def test_valid_detached_signature_but_no_independent_time_proof(self):
        result = run(*signed_fixture())
        self.assertEqual(result["state"],
                         "LAB_SIGNED_RECEIPT_CRYPTO_MATCH_UNTRUSTED_SIGNER")
        self.assertTrue(result["locally_valid_precommit_chain"])
        self.assertTrue(result["detached_ed25519_signature_valid_for_supplied_key"])
        self.assertTrue(result["supplied_public_key_matches_supplied_fingerprint"])
        self.assertTrue(result["signed_time_claim_precedes_outcome"])
        self.no_go(result)

    def test_adulterated_signature_is_rejected(self):
        row, chain, receipt, pub, eval_at = signed_fixture()
        raw = bytearray(base64.b64decode(receipt.signature_b64))
        raw[0] ^= 1
        changed = replace(receipt, signature_b64=base64.b64encode(raw).decode())
        self.blocked(run(row, chain, changed, pub, eval_at),
                     "DETACHED_SIGNATURE_DOES_NOT_VERIFY")

    def test_post_signature_accepted_at_edit_rejected(self):
        row, chain, receipt, pub, eval_at = signed_fixture()
        changed = replace(receipt, accepted_at=receipt.accepted_at + timedelta(seconds=1))
        self.blocked(run(row, chain, changed, pub, eval_at),
                     "DETACHED_SIGNATURE_DOES_NOT_VERIFY")

    def test_signed_but_after_outcome_start_rejected(self):
        row, chain, _, _, _ = signed_fixture()
        data = signed_fixture(row=row, chain=chain,
                              accepted_at=row.outcome_start_at + timedelta(seconds=1))
        self.blocked(run(*data), "SIGNED_TIME_CLAIM_NOT_IN_PRE_EVENT_WINDOW")

    def test_signed_but_before_forecast_issuance_rejected(self):
        row, chain, _, _, _ = signed_fixture()
        data = signed_fixture(row=row, chain=chain,
                              accepted_at=row.prediction_issued_at - timedelta(seconds=1))
        self.blocked(run(*data), "SIGNED_TIME_CLAIM_NOT_IN_PRE_EVENT_WINDOW")

    def test_wrong_nonce_or_signer_expected_by_caller_rejected(self):
        data = signed_fixture()
        self.blocked(run(*data, expected_nonce="b" * 32),
                     "RECEIPT_ENTRY_SIGNER_OR_NONCE_MISMATCH")
        self.blocked(run(*data, expected_signer="OTHER_SIGNER"),
                     "RECEIPT_ENTRY_SIGNER_OR_NONCE_MISMATCH")

    def test_unlinked_forecast_head_or_entry_rejected(self):
        row, chain, receipt, pub, ev = signed_fixture()
        self.blocked(run(row, chain, receipt, pub, ev, provided_head="d" * 64),
                     "FORECAST_CHAIN_NOT_LOCALLY_VERIFIED")
        altered = replace(receipt, entry_sha256_claim="d" * 64)
        self.blocked(run(row, chain, altered, pub, ev),
                     "RECEIPT_ENTRY_SIGNER_OR_NONCE_MISMATCH")

    def test_wrong_public_key_or_fingerprint_rejected(self):
        data = signed_fixture()
        self.blocked(run(*data, supplied_fingerprint="d" * 64),
                     "PUBLIC_KEY_OR_CALLER_FINGERPRINT_INVALID")
        row, chain, receipt, pub, ev = data
        other_pub = Ed25519PrivateKey.generate().public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.blocked(run(row, chain, receipt, other_pub, ev),
                     "DETACHED_SIGNATURE_DOES_NOT_VERIFY")

    def test_bad_base64_and_incorrect_size_rejected(self):
        row, chain, receipt, pub, ev = signed_fixture()
        for signature, reason in (("!notbase64", "INVALID_DETACHED_SIGNATURE_ENCODING"),
                                  (base64.b64encode(b"x" * 12).decode(),
                                   "INVALID_DETACHED_SIGNATURE_SIZE")):
            with self.subTest(signature=signature):
                self.blocked(run(row, chain, replace(receipt, signature_b64=signature),
                                 pub, ev), reason)

    def test_future_accepted_time_after_evaluation_rejected(self):
        row, chain, _, _, _ = signed_fixture()
        late = signed_fixture(row=row, chain=chain,
                              accepted_at=row.outcome_start_at - timedelta(seconds=1))
        self.blocked(run(*late[:-1], row.prediction_issued_at),
                     "SIGNED_TIME_CLAIM_NOT_IN_PRE_EVENT_WINDOW")

    def test_abstention_receipts_do_not_become_hit_or_signal(self):
        result = run(*signed_fixture(side="ABSTAIN"))
        self.assertEqual(result["state"],
                         "LAB_SIGNED_RECEIPT_CRYPTO_MATCH_UNTRUSTED_SIGNER")
        self.no_go(result)

    def test_a_newly_forged_key_and_receipt_still_do_not_establish_trust(self):
        # Complete synthetic key substitution signs successfully but can never
        # set the independent trust-root flags to True.
        row, chain, receipt, pub, ev = signed_fixture()
        result = run(row, chain, receipt, pub, ev)
        self.assertTrue(result["detached_ed25519_signature_valid_for_supplied_key"])
        self.assertIs(result["public_key_previously_pinned_independently"], False)
        self.no_go(result)

    def test_bad_canonical_fields_rejected(self):
        row, chain, receipt, pub, ev = signed_fixture()
        bad_receipt = replace(receipt, receipt_id="INVALID SPACES")
        self.blocked(run(row, chain, bad_receipt, pub, ev),
                     "INVALID_CANONICAL_RECEIPT_FIELDS")

    def test_public_key_missing_is_hard_blocker(self):
        row, chain, receipt, _, ev = signed_fixture()
        self.blocked(run(row, chain, receipt, b"", ev),
                     "PUBLIC_KEY_OR_CALLER_FINGERPRINT_INVALID")

    def test_signature_payload_is_timezone_canonical(self):
        row, chain, receipt, pub, ev = signed_fixture()
        equivalent_time = receipt.accepted_at.astimezone(timezone(timedelta(hours=-4)))
        original = canonical_signed_receipt_payload_lab(receipt)
        changed = canonical_signed_receipt_payload_lab(replace(receipt, accepted_at=equivalent_time))
        self.assertEqual(original, changed)
        result = run(row, chain, replace(receipt, accepted_at=equivalent_time), pub, ev)
        self.assertTrue(result["detached_ed25519_signature_valid_for_supplied_key"])
        self.no_go(result)


if __name__ == "__main__":
    unittest.main()
