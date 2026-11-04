"""Two Ed25519 signatures prove only math under caller-configured keys."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from atlasquant_trader_calendar_document_bytes_gate_lab import (
    audit_three_daily_calendar_document_bytes_lab,
)
from atlasquant_trader_calendar_witness_signatures_lab import (
    SCHEMA, _signed_payload, verify_calendar_two_witness_signatures_lab,
)
from test_atlasquant_trader_calendar_document_bytes_gate_lab import (
    NEW_BODY, NOW, OLD_BODY, with_document,
)

CHALLENGE = {"nonce_hex": "01" * 16,
             "issued_at_utc": "2026-11-04T20:50:00Z"}
SIGNED_AT = "2026-11-04T20:55:00Z"
IDS = ("TEST_FETCH_1", "TEST_REVIEW_2")
ROLES = ("SOURCE_FETCH_OBSERVER", "INDEPENDENT_REVIEW_OBSERVER")


def fixture(captures=None, *, challenge=None):
    captures = [with_document(0)] if captures is None else captures
    challenge = deepcopy(CHALLENGE) if challenge is None else challenge
    keys = [Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()]
    configured = {
        ids: {"role": role, "public_key_hex": key.public_key().public_bytes_raw().hex()}
        for ids, role, key in zip(IDS, ROLES, keys)
    }
    audit = audit_three_daily_calendar_document_bytes_lab(captures, at=NOW)
    msg = _signed_payload(audit, challenge)
    witnesses = [
        {"key_id": ids, "role": role, "signed_at_utc": SIGNED_AT,
         "signature_hex": key.sign(msg).hex()}
        for ids, role, key in zip(IDS, ROLES, keys)
    ]
    return captures, challenge, witnesses, configured


def verify(data):
    captures, challenge, witnesses, configured = data
    return verify_calendar_two_witness_signatures_lab(
        captures, challenge, witnesses, configured, at=NOW)


class CalendarWitnessSignaturesLabTests(unittest.TestCase):
    def test_two_distinct_math_signatures_no_official_source_promotion(self):
        data = fixture()
        before = deepcopy(data)
        out = verify(data)
        self.assertEqual(data, before)
        self.assertEqual((out["schema"], out["state"]),
                         (SCHEMA, "LAB_TWO_SIGNATURES_MATH_ONLY"))
        self.assertTrue(out["signature_math_verified"])
        self.assertTrue(out["distinct_configured_keys_verified"])
        self.assertEqual(out["configured_key_ids"], sorted(IDS))
        self.assertEqual(out["document_audit"]["checked_document_count"], 1)
        self.assertFalse(out["independent_signer_identities_verified"])
        self.assertFalse(out["official_publisher_origin_verified"])
        self.assertFalse(out["tls_custody_verified"])
        self.assertFalse(out["witnessed_external_timestamp_verified"])
        self.assertFalse(out["replay_prevention_operational"])

    def test_replaying_old_signatures_for_new_document_chain_is_rejected(self):
        data = list(fixture())
        newer = with_document(0, NEW_BODY)
        data[0] = [newer]
        out = verify(data)
        self.assertEqual((out["state"], out["reason"]),
                         ("LAB_BLOCKED", "INVALID_OR_REPLAYED_WITNESS_SIGNATURE"))
        self.assertFalse(out["signature_math_verified"])

    def test_nonce_change_invalidates_two_old_signatures(self):
        data = list(fixture())
        data[1] = {**CHALLENGE, "nonce_hex": "02" * 16}
        self.assertEqual(verify(data)["reason"],
                         "INVALID_OR_REPLAYED_WITNESS_SIGNATURE")

    def test_expired_future_and_unbounded_nonce_challenges_refused(self):
        changes = (
            {**CHALLENGE, "issued_at_utc": "2026-11-04T20:44:00Z"},
            {**CHALLENGE, "issued_at_utc": "2026-11-04T21:01:00Z"},
            {**CHALLENGE, "nonce_hex": "bad"},
        )
        for challenge in changes:
            with self.subTest(challenge=challenge):
                data = list(fixture())
                data[1] = challenge
                self.assertEqual(verify(data)["state"], "LAB_BLOCKED")

    def test_duplicate_witness_key_rejected_without_signature_acceptance(self):
        data = list(fixture())
        data[2][1] = deepcopy(data[2][0])
        self.assertEqual(verify(data)["reason"],
                         "UNKNOWN_DUPLICATE_OR_INVALID_WITNESS")

    def test_duplicate_public_keys_or_same_roles_rejected(self):
        one = list(fixture())
        one[3][IDS[1]]["public_key_hex"] = one[3][IDS[0]]["public_key_hex"]
        self.assertEqual(verify(one)["reason"],
                         "PUBLIC_KEYS_OR_SIGNER_ROLES_NOT_DISTINCT")
        two = list(fixture())
        two[3][IDS[1]]["role"] = ROLES[0]
        self.assertEqual(verify(two)["reason"],
                         "PUBLIC_KEYS_OR_SIGNER_ROLES_NOT_DISTINCT")

    def test_public_key_or_signature_tampering_is_rejected(self):
        altered_key = list(fixture())
        altered_key[3][IDS[0]]["public_key_hex"] = Ed25519PrivateKey.generate().public_key().public_bytes_raw().hex()
        self.assertEqual(verify(altered_key)["state"], "LAB_BLOCKED")
        altered_sig = list(fixture())
        altered_sig[2][1]["signature_hex"] = "00" * 64
        self.assertEqual(verify(altered_sig)["state"], "LAB_BLOCKED")

    def test_role_mismatch_or_unreviewed_fields_rejected(self):
        mismatched = list(fixture())
        mismatched[2][0]["role"] = ROLES[1]
        self.assertEqual(verify(mismatched)["state"], "LAB_BLOCKED")
        extra = list(fixture())
        extra[2][0]["officially_verified"] = True
        self.assertEqual(verify(extra)["reason"], "UNSUPPORTED_SIGNATURE_FIELDS")
        invalid = list(fixture())
        invalid[3][IDS[1]]["role"] = []
        self.assertEqual(verify(invalid)["state"], "LAB_BLOCKED")

    def test_no_document_cannot_receive_meaningless_witness_acceptance(self):
        data = list(fixture())
        data[0] = []
        out = verify(data)
        self.assertEqual((out["state"], out["reason"]),
                         ("LAB_BLOCKED", "NO_DOCUMENTS_TO_WITNESS"))

    def test_mismatching_raw_body_is_blocked_before_signature_verification(self):
        data = list(fixture())
        data[0][0]["document_receipts"][0]["body"] = NEW_BODY
        out = verify(data)
        self.assertEqual(out["reason"], "DOCUMENT_BYTES_AUDIT_NOT_ACCEPTABLE")
        self.assertFalse(out["signature_math_verified"])

    def test_two_signatures_do_not_prove_three_daily_updates(self):
        data = fixture(captures=[with_document(0), with_document(1, NEW_BODY)])
        out = verify(data)
        self.assertTrue(out["signature_math_verified"])
        self.assertFalse(out["three_daily_updates_verified"])
        self.assertFalse(out["source_data_real_time_verified"])
        self.assertEqual(out["document_audit"]["calendar_review"]["claimed_capture_count"], 2)

    def test_cost_deployment_and_operational_flags_remain_hard_disabled(self):
        out = verify(fixture())
        for k in ("publishable", "can_feed_live_radar", "trade_authorized",
                  "worker_enabled", "scheduler_enabled"):
            self.assertFalse(out[k], k)
        self.assertEqual(out["currency_bias"], "AGUARDAR")
        self.assertEqual((out["external_http_requests"], out["new_cost_brl"]), (0, 0))

    def test_naive_clock_and_malformed_keys_fail_closed(self):
        data = fixture()
        with self.assertRaises(ValueError):
            verify_calendar_two_witness_signatures_lab(*data,
                                                       at=datetime(2026, 11, 4, 21))
        altered = list(fixture())
        altered[3] = {"SINGLE": altered[3][IDS[0]]}
        self.assertEqual(verify(altered)["state"], "LAB_BLOCKED")


if __name__ == "__main__":
    unittest.main()
