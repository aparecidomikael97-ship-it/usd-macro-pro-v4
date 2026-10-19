"""P0 read-only Twilio-style provider reconciliation scenarios.

All SIDs, phone numbers and readbacks are synthetic. Tests never contact
Twilio, send a message, store credentials, edit a real outbox or authorize
retry. "sent", "delivered", "failed", "canceled" remain untrusted status hints.
"""
from copy import deepcopy
import unittest

from atlasquant_aion_p0_twilio_readback_triage_lab import inspect_twilio_message_readback_lab

AC = "AC" + "a" * 32
SID1 = "SM" + "1" * 32
SID2 = "SM" + "2" * 32
SID3 = "SM" + "3" * 32
FROM = "+15550100001"
TO = "+15550100002"
OTHER = "+15550100003"


class ProviderReadbackLabTests(unittest.TestCase):
    def setUp(self):
        self.expected = {
            "operation_ref": "lab-operation-001",
            "account_sid": AC, "to": TO, "from": FROM,
            "known_message_sid": "",
        }
        self.message = {
            "sid": SID1, "account_sid": AC,
            "to": TO, "from": FROM, "status": "queued"
        }
        self.observation = {
            "source": "MESSAGE_LIST", "pagination_complete": True,
            "source_error": None, "messages": [],
        }

    def check(self, reason, *, expected=None, observation=None):
        expected = self.expected if expected is None else expected
        observation = self.observation if observation is None else observation
        before = deepcopy((expected, observation))
        out = inspect_twilio_message_readback_lab(expected, observation)
        self.assertEqual((expected, observation), before)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertEqual(out["reason"], reason)
        for key in (
            "provider_identity_authenticated", "provider_readback_authenticated",
            "provider_completeness_proven", "current_external_effect_verified",
            "definitive_no_effect_fence_verified", "unknown_outcome_cleared",
            "attempt_state_mutated", "automatic_retry_allowed", "resend_authorized",
            "outbox_release_authorized", "effect_ledger_authorized",
            "worker_armed", "network_called", "external_action_executed",
            "executes_action",
        ):
            self.assertIs(out[key], False, key)
        return out

    def obs(self, messages, **overrides):
        row = deepcopy(self.observation)
        row["messages"] = deepcopy(messages)
        row.update(overrides)
        return row

    def test_01_complete_empty_list_is_not_no_effect(self):
        self.check("NO_MATCH_IS_NOT_NO_EFFECT")

    def test_02_incomplete_empty_list_is_not_no_effect(self):
        self.check("LIST_INCOMPLETE_NO_MATCH_PROOF", observation=self.obs([], pagination_complete=False))

    def test_03_matching_message_is_only_unverified_candidate(self):
        out = self.check("POSSIBLE_EXISTING_MESSAGE_UNAUTHENTICATED", observation=self.obs([self.message]))
        self.assertEqual(out["observed_sids"], (SID1,))
        self.assertEqual(out["observed_statuses"], ("queued",))

    def test_04_matching_sent_is_not_proof_of_delivery(self):
        msg=deepcopy(self.message); msg["status"]="sent"
        out=self.check("POSSIBLE_EXISTING_MESSAGE_UNAUTHENTICATED",observation=self.obs([msg]))
        self.assertFalse(out["current_external_effect_verified"])

    def test_05_matching_delivered_still_needs_authenticated_provider(self):
        msg=deepcopy(self.message); msg["status"]="delivered"
        out=self.check("POSSIBLE_EXISTING_MESSAGE_UNAUTHENTICATED",observation=self.obs([msg]))
        self.assertEqual(out["review"], "RECONCILE_EXACT_SID_WITH_AUTHENTICATED_PROVIDER")

    def test_06_matching_failed_is_not_a_no_effect_fence(self):
        msg=deepcopy(self.message); msg["status"]="failed"
        out=self.check("POSSIBLE_EXISTING_MESSAGE_UNAUTHENTICATED",observation=self.obs([msg]))
        self.assertFalse(out["definitive_no_effect_fence_verified"])

    def test_07_matching_canceled_does_not_authorize_retry(self):
        msg=deepcopy(self.message); msg["status"]="canceled"
        out=self.check("POSSIBLE_EXISTING_MESSAGE_UNAUTHENTICATED",observation=self.obs([msg]))
        self.assertFalse(out["automatic_retry_allowed"])

    def test_08_multiple_matches_are_ambiguous(self):
        second=deepcopy(self.message); second["sid"]=SID2
        out=self.check("MULTIPLE_CANDIDATES_AMBIGUOUS",observation=self.obs([second,self.message]))
        self.assertEqual(out["observed_candidate_count"],2)
        self.assertEqual(out["observed_sids"], (SID1,SID2))

    def test_09_two_matching_rows_with_duplicate_sid_ambiguous(self):
        self.check("READBACK_DUPLICATE_SID_AMBIGUOUS",observation=self.obs([self.message,self.message]))

    def test_10_other_account_message_does_not_match(self):
        other=deepcopy(self.message); other["account_sid"]="AC"+"b"*32
        self.check("NO_MATCH_IS_NOT_NO_EFFECT",observation=self.obs([other]))

    def test_11_other_recipient_message_does_not_match(self):
        other=deepcopy(self.message); other["to"]=OTHER
        self.check("NO_MATCH_IS_NOT_NO_EFFECT",observation=self.obs([other]))

    def test_12_other_sender_message_does_not_match(self):
        other=deepcopy(self.message); other["from"]=OTHER
        self.check("NO_MATCH_IS_NOT_NO_EFFECT",observation=self.obs([other]))

    def test_13_incomplete_page_with_match_still_incomplete(self):
        self.check("POSSIBLE_MATCH_FROM_INCOMPLETE_LIST",observation=self.obs([self.message],pagination_complete=False))

    def test_14_known_sid_match_still_not_authenticated(self):
        expected=deepcopy(self.expected); expected["known_message_sid"]=SID1
        out=self.check("POSSIBLE_EXISTING_MESSAGE_UNAUTHENTICATED",expected=expected,observation=self.obs([self.message]))
        self.assertFalse(out["provider_readback_authenticated"])

    def test_15_known_sid_not_present_not_negative_fence(self):
        expected=deepcopy(self.expected); expected["known_message_sid"]=SID2
        self.check("NO_MATCH_IS_NOT_NO_EFFECT",expected=expected,observation=self.obs([self.message]))

    def test_16_known_sid_account_mismatch_is_conflict(self):
        expected=deepcopy(self.expected); expected["known_message_sid"]=SID1
        other=deepcopy(self.message); other["account_sid"]="AC"+"b"*32
        self.check("KNOWN_SID_ACCOUNT_SCOPE_CONFLICT",expected=expected,observation=self.obs([other]))

    def test_17_known_sid_to_mismatch_is_conflict(self):
        expected=deepcopy(self.expected); expected["known_message_sid"]=SID1
        other=deepcopy(self.message); other["to"]=OTHER
        self.check("KNOWN_SID_DESTINATION_SCOPE_CONFLICT",expected=expected,observation=self.obs([other]))

    def test_18_fetch_without_known_sid_is_not_reconciliation(self):
        self.check("FETCH_WITHOUT_DURABLY_KNOWN_SID_UNSUPPORTED",observation=self.obs([self.message],source="MESSAGE_FETCH"))

    def test_19_fetch_known_sid_candidate_only(self):
        expected=deepcopy(self.expected); expected["known_message_sid"]=SID1
        self.check("POSSIBLE_EXISTING_MESSAGE_UNAUTHENTICATED",expected=expected,observation=self.obs([self.message],source="MESSAGE_FETCH"))

    def test_20_fetch_two_resources_invalid(self):
        expected=deepcopy(self.expected); expected["known_message_sid"]=SID1
        second=deepcopy(self.message); second["sid"]=SID2
        self.check("FETCH_MUST_RETURN_AT_MOST_ONE",expected=expected,observation=self.obs([self.message,second],source="MESSAGE_FETCH"))

    def test_21_status_callback_alone_not_authenticated(self):
        self.check("CALLBACK_ALONE_UNTRUSTED",observation=self.obs([self.message],source="STATUS_CALLBACK"))

    def test_22_timeout_does_not_enable_replay(self):
        self.check("READBACK_FAILED_OR_UNAVAILABLE",observation=self.obs([],source_error="TIMEOUT"))

    def test_23_auth_error_does_not_enable_replay(self):
        self.check("READBACK_FAILED_OR_UNAVAILABLE",observation=self.obs([],source_error="AUTH_ERROR"))

    def test_24_rate_limit_does_not_enable_replay(self):
        self.check("READBACK_FAILED_OR_UNAVAILABLE",observation=self.obs([],source_error="RATE_LIMIT"))

    def test_25_404_lookup_does_not_prove_absence(self):
        self.check("READBACK_FAILED_OR_UNAVAILABLE",observation=self.obs([],source_error="NOT_FOUND"))

    def test_26_malformed_row_rejected(self):
        bad=deepcopy(self.message); bad["claimed_confirmed"]=True
        self.check("READBACK_ROW_MALFORMED",observation=self.obs([bad]))

    def test_27_fake_provider_trust_flag_rejected(self):
        bad=self.obs([self.message]); bad["verified"]=True
        self.check("READBACK_SHAPE_INVALID",observation=bad)

    def test_28_bool_pagination_flag_rejected(self):
        self.check("PAGINATION_TYPE_INVALID",observation=self.obs([],pagination_complete="true"))

    def test_29_unknown_status_rejected(self):
        bad=deepcopy(self.message);bad["status"]="confirmed_provider_no_effect"
        self.check("READBACK_ROW_VALUES_INVALID",observation=self.obs([bad]))

    def test_30_invalid_sid_rejected(self):
        bad=deepcopy(self.message);bad["sid"]="SM_fake"
        self.check("READBACK_ROW_VALUES_INVALID",observation=self.obs([bad]))

    def test_31_invalid_expected_account(self):
        expected=deepcopy(self.expected);expected["account_sid"]="wrong"
        self.check("EXPECTED_ATTEMPT_BINDING_INVALID",expected=expected)

    def test_32_unknown_operation_cannot_be_matched_by_phone_alone(self):
        expected=deepcopy(self.expected);expected["operation_ref"]=""
        self.check("EXPECTED_ATTEMPT_BINDING_INVALID",expected=expected,observation=self.obs([self.message]))

    def test_33_missing_expected_scope_rejected(self):
        expected=deepcopy(self.expected);expected.pop("known_message_sid")
        self.check("EXPECTED_ATTEMPT_SCOPE_INVALID",expected=expected)

    def test_34_status_row_type_not_string_rejected(self):
        bad=deepcopy(self.message);bad["status"]=True
        self.check("READBACK_ROW_TYPES_INVALID",observation=self.obs([bad]))

    def test_35_bounded_page_enforced(self):
        self.check("READBACK_MESSAGES_INVALID",observation=self.obs([self.message]*101))

    def test_36_duplicate_json_keys_not_available_to_caller_as_trusted_origin(self):
        # Pure data boundary cannot prove decoded JSON authenticity: it only
        # accepts strict dict and the source remains untrusted even when valid.
        out=self.check("POSSIBLE_EXISTING_MESSAGE_UNAUTHENTICATED",observation=self.obs([self.message]))
        self.assertFalse(out["provider_completeness_proven"])
