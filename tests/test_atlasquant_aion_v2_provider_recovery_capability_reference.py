"""Offline documentation-backed provider recovery capability negative tests."""
from __future__ import annotations

from copy import deepcopy
import unittest
from unittest.mock import patch

from atlasquant_aion_v2_provider_recovery_capability_reference import (
    SCHEMA,DOCUMENTED_MODES,READ_CANDIDATE,NO_SAFE_GET,FALSE_FLAGS,
    MODE_OPENAI_BACKGROUND,MODE_OPENAI_STORED,MODE_OPENAI_UNSTORED,
    MODE_ANTHROPIC_BATCH,MODE_ANTHROPIC_SYNC,MODE_GEMINI_SYNC,
    review_provider_read_only_recovery_reference,
    classify_read_only_recovery_observation_reference,
)


class ProviderRecoveryCapabilityReferenceTests(unittest.TestCase):
    def intent(self,mode=MODE_OPENAI_BACKGROUND,**changes):
        providers={
            MODE_OPENAI_BACKGROUND:"openai",MODE_OPENAI_STORED:"openai",
            MODE_OPENAI_UNSTORED:"openai",MODE_ANTHROPIC_BATCH:"anthropic",
            MODE_ANTHROPIC_SYNC:"anthropic",MODE_GEMINI_SYNC:"gemini",
        }
        doc={
            "provider":providers[mode],"mode":mode,
            "owner_id":"owner","tenant_id":"tenant","workspace_id":"workspace",
            "nonce_hex":"a"*64,"signed_intent_sha256":"b"*64,
            "full_provider_request_sha256":"c"*64,
            "journal_state":"UNKNOWN_OUTCOME",
            "documented_retention_opt_in":False,
            "transport_auto_retry_enabled":False,
        }
        doc.update(changes)
        return doc

    def locator(self,**kwargs):
        v={
            "response_id":"","batch_id":"","batch_custom_id":"",
            "diagnostic_request_id":"",
        }
        v.update(kwargs)
        return v

    def check(self,intent,locator):
        out=review_provider_read_only_recovery_reference(
            intent=intent,locator=locator,
        )
        self.assertEqual(out["schema"],SCHEMA)
        self.assertTrue(out["must_not_automatically_retry"])
        self.assertTrue(out["recovery_does_not_prove_no_charge"])
        for k,v in FALSE_FLAGS.items():
            self.assertIs(out[k],v,k)
        return out

    def test_known_background_response_id_permits_only_read_planning(self):
        r=self.check(
            self.intent(),self.locator(response_id="resp_known_ci"))
        self.assertEqual(r["state"],READ_CANDIDATE)
        self.assertTrue(r["read_only_planning_candidate"])
        self.assertEqual(r["documented_identifier_kind"],"response_id")
        self.assertFalse(r["model_post_authorized"])

    def test_stored_foreground_response_id_and_optin_required(self):
        i=self.intent(MODE_OPENAI_STORED,documented_retention_opt_in=True)
        self.assertEqual(self.check(
            i,self.locator(response_id="resp_known_ci"))["state"],READ_CANDIDATE)
        no_optin=deepcopy(i)
        no_optin["documented_retention_opt_in"]=False
        self.assertEqual(self.check(
            no_optin,self.locator(response_id="resp_known_ci"))["reason"],
            "STORED_RESPONSE_OPT_IN_NOT_EVIDENCED")

    def test_background_when_create_reply_with_id_lost_blocks(self):
        self.assertEqual(self.check(
            self.intent(),self.locator())["reason"],
            "NO_KNOWN_RESPONSE_ID_OR_IDENTIFIERS_REBOUND")

    def test_openai_request_debug_id_does_not_replace_response_id(self):
        self.assertEqual(self.check(
            self.intent(),self.locator(
                diagnostic_request_id="req_ci_http_header",
            ))["state"],"BLOCKED")

    def test_openai_unstored_no_response_retrieval_assumed(self):
        i=self.intent(MODE_OPENAI_UNSTORED)
        self.assertEqual(self.check(
            i,self.locator(response_id="resp_after_expiry"))["state"],
            NO_SAFE_GET)

    def test_anthropic_batch_known_batch_and_custom_id_only(self):
        i=self.intent(MODE_ANTHROPIC_BATCH)
        r=self.check(i,self.locator(
            batch_id="msgbatch_known_ci",batch_custom_id="custom-one",
        ))
        self.assertEqual(r["state"],READ_CANDIDATE)
        self.assertEqual(r["documented_identifier_kind"],
                         "batch_id_plus_custom_id")
        self.assertFalse(r["provider_side_exactly_once_verified"])

    def test_anthropic_batch_without_batch_id_not_recoverable_by_custom_id(self):
        i=self.intent(MODE_ANTHROPIC_BATCH)
        self.assertEqual(self.check(i,self.locator(
            batch_custom_id="custom-one"))["state"],"BLOCKED")
        self.assertEqual(self.check(i,self.locator(
            batch_id="msgbatch_known_ci"))["state"],"BLOCKED")

    def test_anthropic_sync_request_id_is_debugging_not_messages_get(self):
        i=self.intent(MODE_ANTHROPIC_SYNC)
        result=self.check(i,self.locator(
            diagnostic_request_id="req_foo_ci"))
        self.assertEqual(result["state"],NO_SAFE_GET)
        self.assertFalse(result["read_only_planning_candidate"])

    def test_gemini_response_id_not_claimed_to_have_documented_get(self):
        i=self.intent(MODE_GEMINI_SYNC)
        result=self.check(i,self.locator(response_id="responseId_ci"))
        self.assertEqual(result["state"],NO_SAFE_GET)
        self.assertFalse(result["model_post_authorized"])

    def test_no_automatic_sdk_retries_for_any_provider(self):
        for mode in DOCUMENTED_MODES:
            with self.subTest(mode=mode):
                i=self.intent(mode,transport_auto_retry_enabled=True)
                self.assertEqual(self.check(
                    i,self.locator())["reason"],
                    "AUTO_RETRY_MUST_BE_DISABLED_BEFORE_INTEGRATION")

    def test_prepared_or_cancelled_state_no_potential_dispatch(self):
        for state in ("PREPARED","CANCELLED_UNSENT_REFERENCE"):
            with self.subTest(state=state):
                self.assertEqual(self.check(self.intent(
                    journal_state=state
                ),self.locator(response_id="resp_known_ci"))[
                    "reason"],"NO_POTENTIAL_PAID_DISPATCH_TO_RECOVER")

    def test_claimed_state_still_does_not_authorize_post(self):
        r=self.check(
            self.intent(journal_state="DISPATCH_CLAIMED"),
            self.locator(response_id="resp_known_ci"))
        self.assertEqual(r["state"],READ_CANDIDATE)
        self.assertFalse(r["model_post_performed"])
        self.assertFalse(r["safe_to_resume"])

    def test_provider_mode_swap_is_rejected(self):
        self.assertEqual(self.check(
            self.intent(provider="anthropic"),
            self.locator(response_id="resp_known_ci"))["state"],"BLOCKED")

    def test_signed_intent_or_full_request_not_64_lower_hex(self):
        for field in ("signed_intent_sha256","full_provider_request_sha256",
                      "nonce_hex"):
            with self.subTest(field=field):
                self.assertEqual(self.check(
                    self.intent(**{field:"unsafe"}),
                    self.locator(response_id="resp_known_ci"))["state"],
                    "BLOCKED")

    def test_unknown_provider_mode_rejected(self):
        doc=self.intent()
        doc["mode"]="GENERIC_PROVIDER_SEND_AGAIN"
        self.assertEqual(self.check(doc,self.locator())["state"],"BLOCKED")

    def test_injected_authority_field_rejected(self):
        doc=self.intent()
        doc["request_approved"]=True
        self.assertEqual(self.check(doc,self.locator())["state"],"BLOCKED")
        loc=self.locator(response_id="resp_ci",billing_confirmed=True)
        self.assertEqual(self.check(self.intent(),loc)["state"],"BLOCKED")

    def test_boolean_instead_of_true_string_fields_blocks(self):
        self.assertEqual(self.check(self.intent(owner_id=True),
                                    self.locator(response_id="resp_ci"))["state"],
                         "BLOCKED")
        self.assertEqual(self.check(self.intent(
            documented_retention_opt_in=1),self.locator(
                response_id="resp_ci"))["state"],"BLOCKED")

    def test_stored_response_id_format_never_guess_or_invent(self):
        i=self.intent(MODE_OPENAI_STORED,documented_retention_opt_in=True)
        for ident in ("", "req_debug", "made-up-unknown", "resp with spaces"):
            with self.subTest(ident=ident):
                r=self.check(i,self.locator(response_id=ident))
                self.assertEqual(r["state"],"BLOCKED")

    def test_read_response_completed_does_not_prove_charge_or_retry(self):
        pre=self.check(self.intent(),self.locator(response_id="resp_ci"))
        obs={
            "response_status":"COMPLETED",
            "identifier_matches":True,"request_digest_matches":True,
        }
        o=classify_read_only_recovery_observation_reference(
            preflight=pre,observation=obs,
        )
        self.assertEqual(o["state"],
                         "READ_ONLY_OBSERVATION_INCONCLUSIVE_UNTRUSTED")
        self.assertFalse(o["billing_settlement_verified"])
        self.assertFalse(o["provider_object_retrieved"])
        self.assertTrue(o["must_not_automatically_retry"])

    def test_get_404_not_found_does_not_mean_not_processed(self):
        pre=self.check(self.intent(),self.locator(response_id="resp_ci"))
        for status in ("NOT_FOUND","EXPIRED","FAILED","ERROR","PENDING"):
            with self.subTest(status=status):
                obs={
                    "response_status":status,"identifier_matches":True,
                    "request_digest_matches":True,
                }
                o=classify_read_only_recovery_observation_reference(
                    preflight=pre,observation=obs,
                )
                self.assertEqual(o["state"],
                                 "READ_ONLY_OBSERVATION_INCONCLUSIVE_UNTRUSTED")
                self.assertFalse(o["same_nonce_reusable"])

    def test_read_object_with_mismatched_id_or_request_digest_blocks(self):
        pre=self.check(self.intent(),self.locator(response_id="resp_ci"))
        for field in ("identifier_matches","request_digest_matches"):
            with self.subTest(field=field):
                obs={
                    "response_status":"COMPLETED",
                    "identifier_matches":True,"request_digest_matches":True,
                }
                obs[field]=False
                self.assertEqual(
                    classify_read_only_recovery_observation_reference(
                        preflight=pre,observation=obs,
                    )["state"],"BLOCKED")

    def test_no_read_observation_without_qualifying_get_candidate(self):
        pre=self.check(
            self.intent(MODE_ANTHROPIC_SYNC),
            self.locator(diagnostic_request_id="req_ci"))
        self.assertEqual(
            classify_read_only_recovery_observation_reference(
                preflight=pre,observation={
                    "response_status":"COMPLETED",
                    "identifier_matches":True,"request_digest_matches":True,
                },
            )["state"],"BLOCKED")

    def test_no_live_network_even_for_read_candidate(self):
        with patch("requests.post",side_effect=AssertionError("HTTP")), \
             patch("atlasquant_aion_provider.execute_openai_answer",
                   side_effect=AssertionError("paid-model")):
            r=self.check(self.intent(),self.locator(response_id="resp_ci"))
            self.assertEqual(r["state"],READ_CANDIDATE)
        self.assertFalse(r["network_called"])

    def test_matrix_contains_official_sources_and_never_post_permission(self):
        for mode,entry in DOCUMENTED_MODES.items():
            with self.subTest(mode=mode):
                self.assertTrue(entry["source_url"].startswith("https://"))
                self.assertIn(entry["provider"],{"openai","anthropic","gemini"})
                self.assertIn(entry["can_plan_read_only_by_id"],(True,False))


if __name__=="__main__":
    unittest.main()
