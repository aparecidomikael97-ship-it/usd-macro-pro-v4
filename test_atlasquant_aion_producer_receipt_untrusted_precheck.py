"""AION A.37 denial-only offline tests; no provider/witness enrolled."""
from __future__ import annotations

from copy import deepcopy
import unittest

from atlasquant_aion_producer_receipt_untrusted_precheck import (
    SCHEMA, POSITIVE, NEGATIVE, inspect_untrusted_receipt_shape,
)

BOUND = {
    "owner_id": "fixture-owner",
    "tenant_id": "tenant-a",
    "workspace_id": "workspace-a",
    "host_id": "fixture-host",
    "producer_issuer_id": "fixture-issuer",
    "producer_account_id": "fixture-account",
    "action_class": "send_email",
    "intent_digest": "a" * 64,
    "idempotency_key": "idem-fixture-001",
    "attempt": 1,
    "epoch": 1,
    "witness_sequence": 1,
    "witness_head": "b" * 64,
    "nonce": "nonce-fixture-001",
}


def synthetic_claim(kind=POSITIVE):
    return {
        "schema": SCHEMA,
        "domain": (
            "ATLASQUANT:AION:COMMITTED_EFFECT_CLAIM:V1:UNTRUSTED"
            if kind == POSITIVE
            else "ATLASQUANT:AION:NO_EFFECT_FENCED_CLAIM:V1:UNTRUSTED"
        ),
        "kind": kind,
        "receipt_id": "receipt-test-001",
        "issued_at": "2026-10-13T14:00:00Z",
        "claimed_signature": "c" * 128,  # not verified, not an authentic key
        **BOUND,
        ("claimed_effect_ref" if kind == POSITIVE else "claimed_terminal_fence_ref"):
            "fake-positive" if kind == POSITIVE else "fake-fence",
    }


def assert_denied(tc, result):
    tc.assertIn(result["status"], {
        "BLOCKED_INVALID_UNTRUSTED_CLAIM",
        "BLOCKED_EXTERNAL_PROOF_UNAVAILABLE",
    })
    for key in (
        "issuer_authenticated",
        "signature_verified",
        "current_external_witness_verified",
        "producer_commit_verified",
        "producer_terminal_no_effect_fence_verified",
        "external_action_authorized",
        "effect_ledger_authorized",
        "retry_authorized",
        "saga_advance_authorized",
    ):
        tc.assertIs(result[key], False, key)


class NoExternalReceiptAdmissionTests(unittest.TestCase):
    def test_pos_and_neg_perfectly_matching_claims_remain_blocked(self):
        for kind in (POSITIVE, NEGATIVE):
            with self.subTest(kind=kind):
                result = inspect_untrusted_receipt_shape(synthetic_claim(kind), BOUND)
                self.assertTrue(result["shape_matched"])
                self.assertEqual(result["reason"], "INDEPENDENT_PRODUCER_AND_WITNESS_NOT_ENROLLED")
                assert_denied(self, result)

    def test_untrusted_signature_claim_never_authenticates_issuer(self):
        claim = synthetic_claim()
        claim["claimed_signature"] = "f" * 128  # attacker-chosen hex
        result = inspect_untrusted_receipt_shape(claim, BOUND)
        self.assertTrue(result["shape_matched"])
        self.assertFalse(result["signature_verified"])
        self.assertFalse(result["issuer_authenticated"])
        assert_denied(self, result)

    def test_all_fourteen_binding_fields_cannot_be_mismatched(self):
        for key, value in BOUND.items():
            claim = synthetic_claim()
            if type(value) is int:
                claim[key] = value + 1
            elif key in ("intent_digest", "witness_head"):
                claim[key] = "d" * 64
            else:
                claim[key] = "other-attacker"
            with self.subTest(key=key):
                result = inspect_untrusted_receipt_shape(claim, BOUND)
                self.assertFalse(result["shape_matched"])
                self.assertEqual(result["reason"], "LOCAL_BINDING_MISMATCH_" + key.upper())
                assert_denied(self, result)

    def test_wrong_domain_or_signature_kind_rejected(self):
        cases = []
        x = synthetic_claim()
        x["domain"] = "ATLASQUANT:AION:COMMITTED_EFFECT_CLAIM:V1:UNTRUSTED"
        x["kind"] = NEGATIVE
        cases.append(x)
        x = synthetic_claim(NEGATIVE)
        x["claimed_effect_ref"] = x.pop("claimed_terminal_fence_ref")
        cases.append(x)
        x = synthetic_claim()
        x["domain"] = "ATLASQUANT:V5:FIXTURE:READ"
        cases.append(x)
        x = synthetic_claim()
        x["kind"] = "PRE_SEND_ENROLLED"
        cases.append(x)
        x = synthetic_claim()
        x["schema"] = "SOME_REAL_PROVIDER_V1"
        cases.append(x)
        for index, claim in enumerate(cases):
            with self.subTest(index=index):
                result = inspect_untrusted_receipt_shape(claim, BOUND)
                self.assertFalse(result["shape_matched"])
                assert_denied(self, result)

    def test_fake_trust_flags_and_receipt_extra_fields_rejected(self):
        for extra in (
            {"trusted": True},
            {"signature_valid": True},
            {"provider_enrolled": True},
            {"authoritative_absence": True},
            {"found": True, "confirmed": True},
            {"retryable": True},
            {"fenced": True},
        ):
            claim = synthetic_claim()
            claim.update(extra)
            with self.subTest(extra=extra):
                result = inspect_untrusted_receipt_shape(claim, BOUND)
                self.assertEqual(result["reason"], "CLAIM_FIELDS_MISMATCH")
                assert_denied(self, result)

    def test_bool_as_counter_and_malformed_identifiers_rejected(self):
        cases = []
        x = synthetic_claim()
        x["attempt"] = True
        cases.append(x)
        x = synthetic_claim()
        x["witness_sequence"] = 0
        cases.append(x)
        x = synthetic_claim()
        x["intent_digest"] = "not-a-digest"
        cases.append(x)
        x = synthetic_claim()
        x["witness_head"] = "A" * 64
        cases.append(x)
        x = synthetic_claim()
        x["nonce"] = "../unsafe"
        cases.append(x)
        x = synthetic_claim()
        x["receipt_id"] = "\x00private"
        cases.append(x)
        x = synthetic_claim()
        x["claimed_signature"] = "fake-signature"
        cases.append(x)
        x = synthetic_claim()
        x["issued_at"] = "2026-02-30T14:00:00Z"
        cases.append(x)
        x = synthetic_claim()
        x["issued_at"] = "2026-10-13T14:00:00-04:00"
        cases.append(x)
        x = synthetic_claim()
        x["producer_account_id"] = "Z" * 300
        cases.append(x)
        for i, claim in enumerate(cases):
            with self.subTest(i=i):
                result = inspect_untrusted_receipt_shape(claim, BOUND)
                self.assertFalse(result["shape_matched"])
                assert_denied(self, result)

    def test_missing_fields_and_extra_local_context_are_rejected(self):
        claim = synthetic_claim()
        del claim["tenant_id"]
        result = inspect_untrusted_receipt_shape(claim, BOUND)
        self.assertEqual(result["reason"], "CLAIM_FIELDS_MISMATCH")
        assert_denied(self, result)
        bad_expected = deepcopy(BOUND)
        bad_expected["self_enrolled"] = True
        result = inspect_untrusted_receipt_shape(synthetic_claim(), bad_expected)
        self.assertEqual(result["reason"], "EXPECTED_BINDING_FIELDS_MISMATCH")
        assert_denied(self, result)

    def test_nonplain_containers_and_dynamic_comparison_objects_rejected(self):
        class Dangerous:
            calls = 0
            def __hash__(self):
                return 123456
            def __eq__(self, other):
                self.calls += 1
                raise AssertionError("untrusted object should not be compared")

        evil = Dangerous()
        for claim, expected in (
            (None, BOUND),
            ([synthetic_claim()], BOUND),
            (synthetic_claim(), None),
            (dict(synthetic_claim(), schema=evil), BOUND),
            ({**synthetic_claim(), evil: 7}, BOUND),
            (synthetic_claim(), {**BOUND, evil: 7}),
        ):
            with self.subTest(claim=type(claim).__name__, expected=type(expected).__name__):
                result = inspect_untrusted_receipt_shape(claim, expected)
                assert_denied(self, result)
        self.assertEqual(evil.calls, 0)

    def test_all_result_paths_have_closed_authorization_fields(self):
        cases = [
            (synthetic_claim(POSITIVE), BOUND),
            (synthetic_claim(NEGATIVE), BOUND),
            ({}, BOUND),
            (synthetic_claim(), {}),
            (synthetic_claim(), BOUND | {"extra": 1}),
        ]
        for claim, bound in cases:
            with self.subTest(claim_type=type(claim).__name__):
                result = inspect_untrusted_receipt_shape(claim, bound)
                assert_denied(self, result)


if __name__ == "__main__":
    unittest.main()
