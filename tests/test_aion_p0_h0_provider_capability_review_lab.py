"""Negative-only H0 provider assessment: caller manifests are never authority."""
from __future__ import annotations

from copy import deepcopy
import unittest

from atlasquant_aion_p0_h0_provider_capability_review_lab import (
    CAPABILITIES, MANIFEST_SCHEMA, AUTHORITY_FALSE, SCHEMA,
    inspect_provider_capability_review_lab as inspect,
)


def fixture(*, symptom="UNKNOWN", surface="OTHER", state="UNKNOWN"):
    return {
        "schema": MANIFEST_SCHEMA,
        "provider_id": "fixture-provider-001",
        "api_surface": surface,
        "claims": {key: state for key in CAPABILITIES},
        "source_refs": [],
        "symptom": symptom,
    }


class ProviderCapabilityReviewLab(unittest.TestCase):
    def deny(self, value, *, valid=True, path=None, meaning=None):
        result = inspect(value)
        self.assertEqual(result["schema"], SCHEMA)
        self.assertEqual(result["state"], "HARD_NO_GO")
        self.assertIs(result["allowed"], False)
        self.assertIs(result["simulation_only"], True)
        self.assertIs(result["read_only"], True)
        self.assertEqual(result["external_truth"], "UNKNOWN")
        self.assertEqual(result["reconciliation_state"], "UNKNOWN_BLOCKED")
        self.assertIs(result["profile_shape_valid_lab"], valid)
        for name in AUTHORITY_FALSE:
            self.assertIs(result[name], False, name)
        if path is not None:
            self.assertEqual(result["recommended_path"], path)
        if meaning is not None:
            self.assertEqual(result["symptom_interpretation"], meaning)
        return result

    def test_01_all_unknown_never_proves_no_effect(self):
        r = self.deny(fixture(), path="PROTOCOL_AND_INDEPENDENT_ATTESTATION_REQUIRED_NO_RESEND")
        self.assertEqual(len(r["unresolved_claims"]), len(CAPABILITIES))

    def test_02_all_claimed_supported_still_unverified(self):
        r = self.deny(fixture(state="CLAIMED_SUPPORTED"))
        self.assertEqual(len(r["stated_supported_but_unverified"]), len(CAPABILITIES))
        self.assertFalse(r["provider_capabilities_independently_verified"])

    def test_03_idempotency_declared_unsupported_routes_supervised_only(self):
        p=fixture();p["claims"]["server_side_idempotency"]="DECLARED_UNSUPPORTED"
        self.deny(p,path="SUPERVISED_RECONCILIATION_NO_RESEND")

    def test_04_no_fence_declared_routes_supervised_only(self):
        p=fixture();p["claims"]["fenced_no_effect"]="DECLARED_UNSUPPORTED"
        self.deny(p,path="SUPERVISED_RECONCILIATION_NO_RESEND")

    def test_05_no_offhost_first_attempt_routes_supervised_only(self):
        p=fixture();p["claims"]["atomically_offhost_first_attempt"]="DECLARED_UNSUPPORTED"
        self.deny(p,path="SUPERVISED_RECONCILIATION_NO_RESEND")

    def test_06_no_dedup_after_timeout_routes_supervised_only(self):
        p=fixture();p["claims"]["replay_dedup_after_timeout"]="DECLARED_UNSUPPORTED"
        self.deny(p,path="SUPERVISED_RECONCILIATION_NO_RESEND")

    def test_07_noncritical_unsupported_still_denied(self):
        p=fixture();p["claims"]["latest_head_authenticated"]="DECLARED_UNSUPPORTED"
        self.deny(p,path="PROTOCOL_AND_INDEPENDENT_ATTESTATION_REQUIRED_NO_RESEND")

    def test_08_http_404_cannot_certify_no_effect(self):
        self.deny(fixture(symptom="HTTP_404"),meaning="NOT_FOUND_NOT_PROOF_OF_NO_EFFECT")

    def test_09_timeout_cannot_certify_no_effect(self):
        self.deny(fixture(symptom="POST_TIMEOUT"),meaning="TIMEOUT_NOT_PROOF_OF_NO_EFFECT")

    def test_10_empty_list_cannot_certify_no_effect(self):
        self.deny(fixture(symptom="EMPTY_LIST"),meaning="ABSENT_FROM_SEARCH_NOT_PROOF_OF_NO_EFFECT")

    def test_11_unfinished_pagination_cannot_certify_no_effect(self):
        self.deny(fixture(symptom="PAGINATED_LIST_INCOMPLETE"),
                  meaning="INCOMPLETE_HISTORY_NOT_PROOF_OF_NO_EFFECT")

    def test_12_ack_http_2xx_not_causal_proof(self):
        self.deny(fixture(symptom="HTTP_2XX"),
                  meaning="ACK_NOT_INDEPENDENT_CAUSAL_EFFECT_ATTESTATION")

    def test_13_delivery_status_not_offhost_nonce(self):
        self.deny(fixture(symptom="STATUS_DELIVERED"),
                  meaning="STATUS_NOT_ATOMIC_FIRST_ATTEMPT_CUSTODY")

    def test_14_cancel_schedule_not_late_effect_fence(self):
        self.deny(fixture(symptom="SCHEDULED_CANCELLED"),
                  meaning="SCHEDULE_CANCEL_NOT_GENERAL_EFFECT_FENCE")

    def test_15_caller_signed_receipt_not_origin(self):
        self.deny(fixture(symptom="CALLER_SIGNED_RECEIPT"),
                  meaning="CALLER_KEY_NOT_PROVIDER_ORIGIN")

    def test_16_twilio_classic_is_distinct_api_surface(self):
        p=fixture(surface="TWILIO_PROGRAMMABLE_MESSAGING_CLASSIC")
        r=self.deny(p)
        self.assertEqual(r["api_surface"],p["api_surface"])

    def test_17_twilio_comms_v1_is_distinct_surface(self):
        p=fixture(surface="TWILIO_COMMS_V1")
        r=self.deny(p)
        self.assertEqual(r["api_surface"],p["api_surface"])

    def test_18_vendor_docs_link_does_not_authorize(self):
        p=fixture(state="CLAIMED_SUPPORTED")
        p["source_refs"]=["https://www.twilio.com/docs/messaging/api/message-resource"]
        r=self.deny(p)
        self.assertEqual(r["source_links_supplied_not_verified"],1)
        self.assertIn("LINKS_ARE_NOT_VALIDATED_RECEIPTS_OR_FENCES",r["findings"])
        self.assertNotIn(p["source_refs"][0],str(r))

    def test_19_missing_profile_denied(self):
        self.deny(None,valid=False)

    def test_20_evil_dict_subclass_denied_without_lookup(self):
        class Hostile(dict):
            def __getitem__(self, key):
                raise AssertionError("hostile dict touched")
        self.deny(Hostile(fixture()),valid=False)

    def test_21_missing_claim_denied(self):
        p=fixture();p["claims"].pop("fenced_no_effect")
        self.deny(p,valid=False)

    def test_22_injected_authorized_true_denied(self):
        p=fixture();p["authorized"]=True
        self.deny(p,valid=False)

    def test_23_injected_verified_claim_denied(self):
        p=fixture();p["claims"]["verified_external_producer"]=True
        self.deny(p,valid=False)

    def test_24_bool_claim_denied(self):
        p=fixture();p["claims"]["fenced_no_effect"]=True
        self.deny(p,valid=False)

    def test_25_claim_as_object_denied(self):
        p=fixture();p["claims"]["fenced_no_effect"]=object()
        self.deny(p,valid=False)

    def test_26_provider_identifier_invalid(self):
        p=fixture();p["provider_id"]="../secrets"
        self.deny(p,valid=False)

    def test_27_claims_dict_subclass_denied(self):
        class Hostile(dict):
            def keys(self):
                raise AssertionError("should not touch dict subclass")
        p=fixture();p["claims"]=Hostile(p["claims"])
        self.deny(p,valid=False)

    def test_28_surface_alias_unknown_denied(self):
        p=fixture();p["api_surface"]="TWILIO"
        self.deny(p,valid=False)

    def test_29_no_effect_symptom_fake_denied(self):
        p=fixture();p["symptom"]="NO_EFFECT_CONFIRMED"
        self.deny(p,valid=False)

    def test_30_source_list_subclass_denied(self):
        class Hostile(list):
            def __iter__(self):
                raise AssertionError("source list subclass iterated")
        p=fixture();p["source_refs"]=Hostile()
        self.deny(p,valid=False)

    def test_31_duplicate_source_denied(self):
        p=fixture();p["source_refs"]=["https://example.org/doc"]*2
        self.deny(p,valid=False)

    def test_32_unsorted_sources_denied(self):
        p=fixture();p["source_refs"]=["https://z.example/a","https://a.example/a"]
        self.deny(p,valid=False)

    def test_33_more_than_eight_sources_denied(self):
        p=fixture();p["source_refs"]=[f"https://example.org/{i:02}" for i in range(9)]
        self.deny(p,valid=False)

    def test_34_ftp_or_file_ref_denied(self):
        for url in ("file:///secrets", "http://example.org", "ftp://example.org"):
            p=fixture();p["source_refs"]=[url]
            self.deny(p,valid=False)

    def test_35_source_with_space_denied(self):
        p=fixture();p["source_refs"]=["https://example.org/private token"]
        self.deny(p,valid=False)

    def test_36_bool_is_not_api_surface(self):
        p=fixture();p["api_surface"]=True
        self.deny(p,valid=False)

    def test_37_nonstring_manifest_key_denied(self):
        p=fixture();p[123]="forged"
        self.deny(p,valid=False)

    def test_38_hostile_key_eq_not_called(self):
        class Poison:
            def __hash__(self):
                return hash("claims")
            def __eq__(self, _):
                raise AssertionError("nonstring key must not be compared")
        p=fixture();p[Poison()]="fake"
        self.deny(p,valid=False)

    def test_39_expected_supported_set_not_evidence_of_owner_approval(self):
        p=fixture(state="CLAIMED_SUPPORTED")
        r=self.deny(p)
        self.assertFalse(r["human_owner_authenticated"])
        self.assertFalse(r["worker_arming_allowed"])

    def test_40_pinning_fake_provider_keys_cannot_mark_verified(self):
        p=fixture(state="CLAIMED_SUPPORTED")
        p["claims"]["producer_origin_receipt"]="CLAIMED_SUPPORTED"
        r=self.deny(p)
        self.assertFalse(r["provider_effect_authenticated"])
        self.assertFalse(r["outbox_terminal_transition_allowed"])

    def test_41_payload_combinations_keep_no_go(self):
        for symptom in (
            "UNKNOWN","POST_TIMEOUT","HTTP_404","EMPTY_LIST",
            "PAGINATED_LIST_INCOMPLETE","HTTP_2XX","STATUS_DELIVERED",
            "SCHEDULED_CANCELLED","CALLER_SIGNED_RECEIPT"
        ):
            for state in ("UNKNOWN","CLAIMED_SUPPORTED","DECLARED_UNSUPPORTED"):
                with self.subTest(symptom=symptom,state=state):
                    self.deny(fixture(symptom=symptom,state=state))

    def test_42_valid_profile_does_not_mutate_caller(self):
        p=fixture(state="CLAIMED_SUPPORTED")
        p["source_refs"]=["https://example.org/a","https://example.org/b"]
        before=deepcopy(p)
        self.deny(p)
        self.assertEqual(before,p)

    def test_43_https_fake_authority_ref_has_no_operational_effect(self):
        p=fixture(state="CLAIMED_SUPPORTED")
        p["source_refs"]=["https://example.org/claims/all-green"]
        r=self.deny(p)
        self.assertFalse(r["supplier_documentation_authenticated"])
        self.assertFalse(r["manual_resend_allowed"])

    def test_44_all_declared_unsupported_still_no_go(self):
        p=fixture(state="DECLARED_UNSUPPORTED")
        r=self.deny(p,path="SUPERVISED_RECONCILIATION_NO_RESEND")
        self.assertEqual(len(r["stated_unsupported_not_independently_confirmed"]),len(CAPABILITIES))


if __name__ == "__main__":
    unittest.main()
