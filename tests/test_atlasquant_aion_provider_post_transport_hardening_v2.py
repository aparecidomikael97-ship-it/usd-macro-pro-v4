"""Offline test of the hardened REAL provider POST boundary.

No live HTTP: Session.send and provider execution are patched or inspected.
A single logical post is not production proof of exactly-once remote billing.
"""
from __future__ import annotations

from copy import deepcopy
from unittest.mock import patch
import unittest

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import atlasquant_aion_provider as provider


class FakeResponse:
    def __init__(self, code=200):
        self.status_code=code
    def json(self):
        return {"id":"resp_ci_no_network","output_text":"resposta sintética"}


class NoRetryPostHardeningTests(unittest.TestCase):
    def env(self):
        return {
            "AION_MODEL_PROVIDER":"openai",
            "OPENAI_API_KEY":"ci-inert-placeholder-never-network",
            "AION_OPENAI_FAST_MODEL":"fixture-fast",
            "AION_OPENAI_REASONING_MODEL":"fixture-reasoning",
            "AION_OPENAI_INPUT_USD_PER_MTOK":"1",
            "AION_OPENAI_OUTPUT_USD_PER_MTOK":"2",
            "AION_OPENAI_MAX_OUTPUT_TOKENS":"500",
            "AION_OPENAI_TIMEOUT_SECONDS":"8",
        }

    def invoke(self,*,session=None,sha=None):
        values=self.env()
        review=provider.preview_openai_request_binding(
            "Texto público de teste",lane="EXTERNAL_FAST",values=values,
        )
        return provider.execute_openai_answer(
            "Texto público de teste",lane="EXTERNAL_FAST",
            budget={"allow_paid":True,"monthly_limit_usd":10},
            external_feature_enabled=True,request_approved=True,
            values=values,
            expected_request_sha256=review["request_sha256"] if sha is None else sha,
            session=session,
        )

    def check_safe_configuration(self,s):
        self.assertIs(type(s),requests.sessions.Session)
        self.assertIs(s.trust_env,False)
        self.assertIs(s.verify,True)
        self.assertEqual(s.max_redirects,0)
        for prefix in ("https://","http://"):
            adapter=s.get_adapter(prefix+"api.openai.com")
            self.assertIs(type(adapter),HTTPAdapter)
            retry=adapter.max_retries
            self.assertIs(type(retry),Retry)
            for key in ("total","connect","read","redirect","status","other"):
                self.assertEqual(getattr(retry,key),0)
                self.assertIs(type(getattr(retry,key)),int)
            self.assertIsNone(retry.allowed_methods)
            self.assertFalse(retry.respect_retry_after_header)

    def test_sealed_http_session_has_no_retries_redirects_or_proxy_env(self):
        with provider._sealed_provider_transport() as s:
            self.check_safe_configuration(s)

    def test_existing_signed_request_digest_includes_transport_controls(self):
        view=provider.preview_openai_request_binding(
            "Texto público de teste",lane="EXTERNAL_FAST",
            values=self.env(),
        )
        self.assertEqual(view["state"],"BOUND_REQUEST_PREVIEW_UNTRUSTED")
        self.assertEqual(view["transport_policy"],{
            "allow_redirects":False,"trust_env":False,"verify_tls":True,
            "http_retry_total":0,"http_retry_connect":0,
            "http_retry_read":0,"http_retry_status":0,
            "http_retry_other":0,"max_redirects":0,"max_app_attempts":1,
        })
        self.assertFalse(view["model_invocation_authorized"])
        self.assertFalse(view["human_owner_identity_verified"])

    def test_original_provider_post_one_observed_send_and_no_redirects(self):
        calls=[]
        def fake_send(s,request,**kwargs):
            self.check_safe_configuration(s)
            calls.append((request,dict(kwargs)))
            return FakeResponse()
        with patch.object(requests.sessions.Session,"send",autospec=True,
                          side_effect=fake_send):
            result=self.invoke()
        self.assertEqual(result["state"],"ANSWER_READY")
        self.assertEqual(len(calls),1)
        req,kwargs=calls[0]
        self.assertEqual(req.method,"POST")
        self.assertEqual(req.url,"https://api.openai.com/v1/responses")
        self.assertIs(kwargs["allow_redirects"],False)
        self.assertTrue(kwargs["verify"])
        self.assertEqual(kwargs["timeout"],8.0)
        self.assertEqual(dict(kwargs["proxies"]),{})
        self.assertEqual(result["response_id"],"resp_ci_no_network")

    def test_mock_redirect_302_and_307_are_blocked_never_followed(self):
        for status in (301,302,303,307,308):
            with self.subTest(status=status):
                n=[]
                def fake_send(s,request,**kwargs):
                    n.append(request)
                    return FakeResponse(status)
                with patch.object(requests.sessions.Session,"send",autospec=True,
                                  side_effect=fake_send):
                    o=self.invoke()
                self.assertEqual(o["state"],"PROVIDER_REDIRECT_BLOCKED")
                self.assertEqual(o["http_status"],status)
                self.assertEqual(len(n),1)

    def test_mock_429_503_do_not_retrigger_generation(self):
        for status in (408,409,429,500,503,504):
            with self.subTest(status=status):
                n=[]
                def fake_send(s,request,**kwargs):
                    n.append(request)
                    return FakeResponse(status)
                with patch.object(requests.sessions.Session,"send",autospec=True,
                                  side_effect=fake_send):
                    o=self.invoke()
                self.assertEqual(o["state"],"PROVIDER_HTTP_ERROR")
                self.assertEqual(len(n),1)

    def test_timeout_or_connection_error_not_retried_at_python_session_layer(self):
        for error in (requests.exceptions.Timeout("timeout"),
                      requests.exceptions.ConnectionError("lost")):
            with self.subTest(error=type(error).__name__):
                attempts=[]
                def failing(s,request,**kwargs):
                    attempts.append(request)
                    raise error
                with patch.object(requests.sessions.Session,"send",autospec=True,
                                  side_effect=failing):
                    o=self.invoke()
                self.assertEqual(o["state"],"PROVIDER_NETWORK_ERROR")
                self.assertEqual(len(attempts),1)
                self.assertTrue(o["called"])
                # called=True conservatively means an attempt MAY have reached
                # the provider and MUST NOT automatically be repeated.

    def test_injected_sessions_are_denied_prior_to_transport_creation(self):
        class MaliciousSession:
            def __init__(self):self.called=0
            def post(self,*a,**kw):
                self.called+=2
                raise AssertionError("never call malicious transport")
        malicious=MaliciousSession()
        with patch.object(provider,"_sealed_provider_transport",
                          side_effect=AssertionError("never construct transport")):
            o=self.invoke(session=malicious)
        self.assertEqual(o["state"],"BLOCKED_UNVERIFIED_TRANSPORT")
        self.assertFalse(o["called"])
        self.assertEqual(malicious.called,0)

    def test_injected_requests_session_retry_adapter_is_rejected(self):
        client=requests.Session()
        try:
            client.mount("https://",HTTPAdapter(max_retries=Retry(
                total=5,read=5,allowed_methods={"POST"})))
            with patch.object(provider,"_sealed_provider_transport",
                              side_effect=AssertionError("do not create network")):
                o=self.invoke(session=client)
            self.assertEqual(o["state"],"BLOCKED_UNVERIFIED_TRANSPORT")
            self.assertFalse(o["called"])
        finally:
            client.close()

    def test_signed_digest_mismatch_blocks_before_transport_construction(self):
        with patch.object(provider,"_sealed_provider_transport",
                          side_effect=AssertionError("no send")):
            o=self.invoke(sha="0"*64)
        self.assertEqual(o["state"],"BLOCKED_REQUEST_BINDING")
        self.assertFalse(o["called"])

    def test_transport_factory_exception_fails_closed_without_network(self):
        with patch.object(provider,"_sealed_provider_transport",
                          side_effect=RuntimeError("no session")):
            o=self.invoke()
        self.assertEqual(o["state"],"PROVIDER_NETWORK_ERROR")
        self.assertTrue(o["called"])
        self.assertNotIn("ci-inert-placeholder",repr(o))

    def test_real_requests_post_function_is_not_used_by_hardened_path(self):
        with patch("requests.post",side_effect=AssertionError(
                "module-level post prohibited")), \
             patch.object(requests.sessions.Session,"send",autospec=True,
                          return_value=FakeResponse()):
            o=self.invoke()
        self.assertEqual(o["state"],"ANSWER_READY")

    def test_no_implicit_trust_proof_or_real_billing_from_mocked_provider(self):
        view=provider.preview_openai_request_binding(
            "Texto público de teste",lane="EXTERNAL_FAST",
            values=self.env(),
        )
        self.assertFalse(view["signed_request_verified"])
        self.assertFalse(view["human_owner_identity_verified"])
        self.assertFalse(view["independent_witness_verified"])
        self.assertFalse(view["budget_reserved"])
        self.assertFalse(view["model_invocation_authorized"])


if __name__=="__main__":
    unittest.main()
