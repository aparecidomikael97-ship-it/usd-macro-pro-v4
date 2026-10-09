"""Offline HTTP transport shape, redirect/retry and provider adapter AST checks."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from atlasquant_aion_v2_http_retry_redirect_boundary_reference import (
    GET_PLAN,TRACE,AUDIT,
    review_offline_get_transport_shape,
    review_mock_transport_trace,
    audit_existing_provider_source,
)


_NO_HEAD_ARGUMENT=object()


class HTTPRetryRedirectAuditTests(unittest.TestCase):
    def policy(self,**override):
        base={
            "method":"GET","allow_redirects":False,
            "trust_env":False,"verify_tls":True,
            "max_attempts":1,"http_adapter_retry_total":0,
            "sdk_auto_retry_enabled":False,"proxy_configured":False,
            "follow_location_header":False,"allow_method_fallback":False,
        }
        base.update(override)
        return base

    def heads(self,provider="openai",**override):
        paths=(
            [{"method":"GET","relative_path":"/v1/responses/resp_ci_test_one"}]
            if provider=="openai" else [
                {"method":"GET","relative_path":"/v1/messages/batches/msgbatch_ci_one"},
                {"method":"GET","relative_path":"/v1/messages/batches/msgbatch_ci_one/results"},
            ]
        )
        head={
            "state":"TWO_SIGNED_CAPTURE_HEADS_MATH_MATCH_UNTRUSTED_NO_NETWORK",
            "reference_only":True,
            "real_get_authorized":False,
            "real_get_performed":False,
            "network_called":False,
            "offline_relative_get_paths":paths,
        }
        head.update(override)
        return head

    def plan(self,provider="openai",heads=_NO_HEAD_ARGUMENT,policy=None,timeout=10):
        result=review_offline_get_transport_shape(
            capture_witness_review=(
                self.heads(provider) if heads is _NO_HEAD_ARGUMENT else heads
            ),
            provider=provider,
            timeout_seconds=timeout,
            transport_policy=self.policy() if policy is None else policy,
        )
        self.no_authority(result)
        return result

    def no_authority(self,result):
        self.assertTrue(result["must_not_automatically_retry"])
        for name in (
            "verified_live_sdk_config","verified_network_retry_disabled",
            "verified_live_redirect_block","verified_network_tls",
            "verified_proxy_environment_disabled","owner_identity_enrolled",
            "two_independent_fresh_witnesses_verified",
            "captured_response_id_authentic","get_authorized",
            "get_performed","post_authorized","post_performed",
            "automatic_retry_permitted","billing_settlement_verified",
            "safe_to_resume","network_called",
        ):
            self.assertIs(result[name],False,name)
        return result

    def test_openai_exact_get_route_offline_only(self):
        r=self.plan()
        self.assertEqual(r["state"],GET_PLAN)
        self.assertEqual(r["offline_plans"],[{
            "method":"GET","origin":"https://api.openai.com",
            "relative_path":"/v1/responses/resp_ci_test_one",
            "timeout_seconds":10,
            "allow_redirects":False,"trust_env":False,"verify_tls":True,
            "max_attempts":1,"http_adapter_retry_total":0,
            "sdk_auto_retry_enabled":False,"proxy_configured":False,
            "follow_location_header":False,"allow_method_fallback":False,
        }])
        self.assertFalse(r["get_authorized"])

    def test_anthropic_two_exact_get_steps_and_no_post(self):
        result=self.plan("anthropic")
        self.assertEqual(result["state"],GET_PLAN)
        self.assertEqual([x["method"] for x in result["offline_plans"]],
                         ["GET","GET"])
        self.assertEqual(result["offline_plans"][-1]["relative_path"],
                         "/v1/messages/batches/msgbatch_ci_one/results")
        self.assertEqual(len(result["offline_plans"]),2)
        self.assertTrue(result["must_not_automatically_retry"])

    def test_missing_witness_math_or_false_external_authority_rejected(self):
        for modified in (
            self.heads(state="BLOCKED"),
            self.heads(reference_only=False),
            self.heads(real_get_authorized=True),
            self.heads(real_get_performed=True),
            self.heads(network_called=True),
            {},
            None,
        ):
            with self.subTest(value=repr(modified)[:80]):
                self.assertEqual(self.plan(heads=modified)["state"],"BLOCKED")

    def test_redirection_proxy_retry_tls_and_post_fallback_rejected(self):
        attempts=(
            {"method":"POST"},{"method":"HEAD"},
            {"allow_redirects":True},{"trust_env":True},
            {"verify_tls":False},{"max_attempts":2},
            {"http_adapter_retry_total":1},
            {"sdk_auto_retry_enabled":True},
            {"proxy_configured":True},
            {"follow_location_header":True},
            {"allow_method_fallback":True},
            {"max_attempts":False},{"http_adapter_retry_total":False},
            {"sdk_auto_retry_enabled":0},
        )
        for change in attempts:
            with self.subTest(change=change):
                result=self.plan(policy=self.policy(**change))
                self.assertEqual(result["state"],"BLOCKED")
                self.assertEqual(
                    result["reason"],
                    "REDIRECT_RETRY_PROXY_METHOD_OR_TLS_POLICY_INVALID",
                )

    def test_late_unknown_headers_and_extra_credentials_rejected(self):
        proposed=self.policy()
        proposed["Authorization"]="Bearer should-not-be-in-plan"
        self.assertEqual(self.plan(policy=proposed)["state"],"BLOCKED")

    def test_timeout_must_be_bounded_finite_and_not_boolean(self):
        for timeout in (None,0,-2,31,float("inf"),float("nan"),"10",True,False):
            with self.subTest(timeout=repr(timeout)):
                self.assertEqual(self.plan(timeout=timeout)["state"],"BLOCKED")

    def test_unsafe_get_paths_blocked_without_network(self):
        bad_paths=(
            "/v1/chat/completions","/v1/responses/resp_ok/../secret",
            "/v1/responses/resp_ok?method=POST",
            "/v1/responses/resp_ok#fragment",
            "/v1/responses/resp_ok%2fadmin",
            "https://evil.example/v1/responses/resp_ok",
            "//evil.example/v1/responses/resp_ok",
            "/v1/responses/resp_ok\\evil",
            "/v1/responses/resp_ok/extra",
            "/v1/responses/req_diagnostic",
            "",
        )
        for path in bad_paths:
            with self.subTest(path=path):
                head=self.heads(
                    offline_relative_get_paths=[
                        {"method":"GET","relative_path":path},
                    ],
                )
                self.assertEqual(self.plan(heads=head)["state"],"BLOCKED")

    def test_provider_host_route_crossbinding_blocks(self):
        self.assertEqual(self.plan(
            "anthropic",heads=self.heads("openai"))["state"],"BLOCKED")
        self.assertEqual(self.plan(
            "openai",heads=self.heads("anthropic"))["state"],"BLOCKED")
        self.assertEqual(self.plan(
            "gemini",heads=self.heads("openai"))["state"],"BLOCKED")

    def test_batch_results_alone_or_wrong_order_blocked(self):
        paths=[
            {"method":"GET","relative_path":"/v1/messages/batches/msgbatch_a/results"},
        ]
        self.assertEqual(self.plan(
            "anthropic",heads=self.heads("anthropic",
                                       offline_relative_get_paths=paths))[
                                           "state"],"BLOCKED")
        reversed_paths=list(reversed(self.heads("anthropic")[
            "offline_relative_get_paths"]))
        self.assertEqual(self.plan(
            "anthropic",heads=self.heads("anthropic",
                    offline_relative_get_paths=reversed_paths))["state"],"BLOCKED")

    def test_two_openai_get_routes_or_duplicate_route_blocked(self):
        route={"method":"GET","relative_path":"/v1/responses/resp_ci"}
        self.assertEqual(self.plan(
            heads=self.heads(offline_relative_get_paths=[route,route])
        )["state"],"BLOCKED")

    def test_wrong_route_schema_and_post_injection_blocked(self):
        for route in (
            {"method":"POST","relative_path":"/v1/responses/resp_test"},
            {"method":"GET","relative_path":"/v1/responses/resp_test",
             "redirect":True},
            {"relative_path":"/v1/responses/resp_test"},
        ):
            with self.subTest(route=route):
                self.assertEqual(self.plan(
                    heads=self.heads(offline_relative_get_paths=[route]))[
                        "state"],"BLOCKED")

    def test_ordinary_single_response_trace_still_untrusted(self):
        plan=self.plan()
        x=review_mock_transport_trace(
            offline_plan_result=plan,
            observed_attempts=[self.event(plan)],
        )
        self.no_authority(x)
        self.assertEqual(x["state"],TRACE)
        self.assertFalse(x["verified_network_retry_disabled"])

    def event(self,plan,index=0,**changes):
        entry=plan["offline_plans"][index]
        r={
            "method":"GET","origin":entry["origin"],
            "relative_path":entry["relative_path"],
            "event":"RESPONSE","http_status":200,"attempt_no":1,
        }
        r.update(changes)
        return r

    def test_all_get_404_429_503_still_no_paid_retry(self):
        plan=self.plan()
        for status in (404,408,409,429,500,502,503,504):
            with self.subTest(status=status):
                out=review_mock_transport_trace(
                    offline_plan_result=plan,
                    observed_attempts=[self.event(plan,http_status=status)],
                )
                self.assertEqual(out["state"],TRACE)
                self.no_authority(out)

    def test_single_timeout_connect_error_tls_error_stop(self):
        plan=self.plan()
        for e in ("TIMEOUT","CONNECTION_ERROR","TLS_ERROR"):
            out=review_mock_transport_trace(
                offline_plan_result=plan,
                observed_attempts=[
                    self.event(plan,event=e,http_status=0)
                ],
            )
            self.assertEqual(out["state"],TRACE)
            self.assertTrue(out["must_not_automatically_retry"])

    def test_redirect_location_and_cross_host_not_followed(self):
        plan=self.plan()
        for status in (301,302,303,307,308):
            out=review_mock_transport_trace(
                offline_plan_result=plan,
                observed_attempts=[self.event(plan,http_status=status)],
            )
            self.assertEqual(out["state"],"BLOCKED")
        self.assertEqual(review_mock_transport_trace(
            offline_plan_result=plan,
            observed_attempts=[self.event(plan,event="REDIRECT",http_status=0)],
        )["state"],"BLOCKED")
        self.assertEqual(review_mock_transport_trace(
            offline_plan_result=plan,
            observed_attempts=[self.event(plan,origin="https://evil.invalid")],
        )["state"],"BLOCKED")

    def test_double_get_retry_same_response_id_fails_closed(self):
        plan=self.plan()
        one=self.event(plan)
        self.assertEqual(review_mock_transport_trace(
            offline_plan_result=plan,
            observed_attempts=[one,one],
        )["state"],"BLOCKED")
        self.assertEqual(review_mock_transport_trace(
            offline_plan_result=plan,
            observed_attempts=[self.event(plan,attempt_no=2)],
        )["state"],"BLOCKED")

    def test_no_post_fallback_after_timeout_or_error(self):
        plan=self.plan()
        self.assertEqual(review_mock_transport_trace(
            offline_plan_result=plan,
            observed_attempts=[self.event(plan,method="POST")],
        )["state"],"BLOCKED")

    def test_anthropic_batch_requires_first_http_200_for_results(self):
        plan=self.plan("anthropic")
        for code in (201,400,404,429,503):
            with self.subTest(code=code):
                result=review_mock_transport_trace(
                    offline_plan_result=plan,
                    observed_attempts=[
                        self.event(plan,0,http_status=code),
                        self.event(plan,1),
                    ],
                )
                self.assertEqual(result["state"],"BLOCKED")
        self.assertEqual(review_mock_transport_trace(
            offline_plan_result=plan,
            observed_attempts=[
                self.event(plan,0,http_status=200),
                self.event(plan,1,http_status=200),
            ],
        )["state"],TRACE)

    def test_anthropic_no_second_step_after_failed_connection(self):
        plan=self.plan("anthropic")
        result=review_mock_transport_trace(
            offline_plan_result=plan,
            observed_attempts=[
                self.event(plan,0,event="CONNECTION_ERROR",http_status=0),
                self.event(plan,1),
            ],
        )
        self.assertEqual(result["state"],"BLOCKED")

    def test_invalid_trace_shapes_rejected(self):
        plan=self.plan()
        for observations in (
            [],[None],[{}],[{"method":"GET"}],
            [self.event(plan,attempt_no=True)],
            [self.event(plan,http_status="200")],
            [self.event(plan,event="POST_FALLBACK")],
            [self.event(plan,http_status=900)],
            [self.event(plan,event="TIMEOUT",http_status=200)],
            [self.event(plan,method="HEAD")],
        ):
            with self.subTest(payload=repr(observations)[:100]):
                self.assertEqual(review_mock_transport_trace(
                    offline_plan_result=plan,observed_attempts=observations,
                )["state"],"BLOCKED")

    def test_ast_audit_findings_for_current_real_provider_adapter(self):
        code=(Path(__file__).resolve().parents[1]/
              "atlasquant_aion_provider.py").read_text("utf-8")
        result=audit_existing_provider_source(code)
        self.no_authority(result)
        self.assertEqual(result["state"],AUDIT)
        self.assertEqual(result["findings"],[
            "STATIC_POST_SITE_LOOKS_BOUND_BUT_NOT_LIVE_ATTESTED",
        ])
        self.assertFalse(result["verified_live_sdk_config"])
        self.assertFalse(result["verified_network_retry_disabled"])

    def test_ast_source_malformed_closed_no_exec(self):
        for content in (None,"def nope(): pass","def execute_openai_answer(",42):
            self.assertEqual(
                audit_existing_provider_source(content)["state"],"BLOCKED")

    def test_unsafe_adapter_call_signature_detected_in_ast(self):
        source="""
def execute_openai_answer(session):
    session.post("https://api.openai.com/v1/responses",allow_redirects=True)
"""
        result=audit_existing_provider_source(source)
        self.assertIn("POST_REDIRECTS_NOT_STATIC_FALSE",result["findings"])
        self.assertIn("FULL_PROVIDER_REQUEST_DIGEST_NOT_FOUND",result["findings"])

    def test_ast_cannot_prove_hidden_transport_behaviour_negative_control(self):
        source="""
def execute_openai_answer(client):
    _full_request_sha256("a")
    client.post("https://api.openai.com/v1/responses",allow_redirects=False)
"""
        result=audit_existing_provider_source(source)
        self.assertEqual(result["state"],AUDIT)
        self.assertEqual(result["findings"],[
            "STATIC_POST_SITE_LOOKS_BOUND_BUT_NOT_LIVE_ATTESTED",
        ])
        self.assertFalse(result["verified_live_sdk_config"])

    def test_fake_witness_math_can_be_forged_still_no_get_approval(self):
        # Negative control: these forged local flags pass shape review;
        # they cannot attest that a signer, owner, or provider exists.
        witness=self.heads()
        out=self.plan(heads=witness)
        self.assertEqual(out["state"],GET_PLAN)
        self.assertFalse(out["two_independent_fresh_witnesses_verified"])
        self.assertFalse(out["get_authorized"])

    def test_no_actual_http_or_provider_even_when_get_plan_passes(self):
        with patch("requests.get",side_effect=AssertionError("live GET")), \
             patch("requests.post",side_effect=AssertionError("paid POST")), \
             patch("atlasquant_aion_provider.execute_openai_answer",
                   side_effect=AssertionError("model")):
            plan=self.plan()
            self.assertEqual(plan["state"],GET_PLAN)
            self.assertEqual(review_mock_transport_trace(
                offline_plan_result=plan,
                observed_attempts=[self.event(plan)],
            )["state"],TRACE)


if __name__=="__main__":
    unittest.main()
