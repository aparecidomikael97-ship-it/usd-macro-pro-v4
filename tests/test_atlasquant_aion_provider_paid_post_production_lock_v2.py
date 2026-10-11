"""Production paid POST lock: legacy booleans/digest never confer authority.

All tests exercise the EXISTING exported provider execution with no test
override of its lock. No sockets, external SDK, tokens or paid API required.
Other transport suites patch the lock only in their *test* mock/loopback
fixtures and cannot weaken this production entrypoint.
"""
from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import patch
import unittest

import requests
import atlasquant_aion_provider as provider


class PaidPOSTProductionNoGoTests(unittest.TestCase):
    def values(self):
        return {
            "AION_MODEL_PROVIDER":"openai",
            "OPENAI_API_KEY":"ci-fake-credential-never-valid",
            "AION_OPENAI_FAST_MODEL":"ci-fast",
            "AION_OPENAI_REASONING_MODEL":"ci-reason",
            "AION_OPENAI_INPUT_USD_PER_MTOK":"1",
            "AION_OPENAI_OUTPUT_USD_PER_MTOK":"2",
            "AION_OPENAI_MAX_OUTPUT_TOKENS":"400",
            "AION_OPENAI_TIMEOUT_SECONDS":"6",
        }

    def attempt(self,**overrides):
        prompt="Pedido de teste sem dados sensíveis"
        values=self.values()
        preview=provider.preview_openai_request_binding(
            prompt,lane="EXTERNAL_FAST",values=values,
        )
        self.assertEqual(preview["state"],"BOUND_REQUEST_PREVIEW_UNTRUSTED")
        cfg={
            "prompt":prompt,
            "lane":"EXTERNAL_FAST",
            "budget":{"allow_paid":True,"monthly_limit_usd":10000},
            "external_feature_enabled":True,
            "request_approved":True,
            "expected_request_sha256":preview["request_sha256"],
            "values":values,
        }
        cfg.update(overrides)
        with patch.object(requests.sessions.Session,"send",
                          side_effect=AssertionError("PRODUCTION NETWORK FORBIDDEN")), \
             patch.object(provider,"_sealed_provider_transport",
                          side_effect=AssertionError("NO SESSION SHOULD BE CREATED")), \
             patch("requests.post",side_effect=AssertionError("NO API POST")):
            return provider.execute_openai_answer(**cfg)

    def assert_no_go(self,result):
        self.assertEqual(result["state"],"BLOCKED_INDEPENDENT_TRUST_NOT_ENROLLED")
        self.assertIs(result["called"],False)
        self.assertIs(result["paid_dispatch_authorized"],False)
        self.assertIs(result["model_invocation_authorized"],False)
        self.assertIs(result["provider_called"],False)
        self.assertIs(result["safe_to_retry"],False)
        self.assertNotIn("ci-fake-credential-never-valid",repr(result))

    def test_bool_approval_and_signed_shape_match_not_paid_authorization(self):
        self.assert_no_go(self.attempt())

    def test_even_high_budget_and_true_legacy_flags_cannot_send(self):
        self.assert_no_go(self.attempt(budget={
            "allow_paid":True,"monthly_limit_usd":1000000,
            "spent_usd_estimate":0,
        }))

    def test_reasoning_lane_with_exact_digest_is_still_blocked(self):
        values=self.values()
        prompt="Solicitação sintética para reasoning"
        digest=provider.preview_openai_request_binding(
            prompt,lane="EXTERNAL_REASONING",values=values,
        )["request_sha256"]
        self.assert_no_go(self.attempt(
            prompt=prompt,lane="EXTERNAL_REASONING",
            values=values,expected_request_sha256=digest,
        ))

    def test_host_env_cannot_unlock_paid_dispatch(self):
        vals=self.values()
        vals.update({
            "AION_PAID_DISPATCH_HARD_DENY":"false",
            "AION_ENABLE_REAL_POST":"true",
            "AION_OWNER_ENROLLED":"true",
            "AION_IDP_ATTESTED":"true",
            "AION_EXTERNAL_CAS_PROVEN":"true",
        })
        self.assert_no_go(self.attempt(values=vals))

    def test_trust_root_dictionary_in_env_is_not_real_authority(self):
        vals=self.values()
        vals.update({
            "AION_ENROLLED_KEY_ID":"fake-owner",
            "AION_WITNESSES_SIGNATURES_VERIFIED":"true",
            "AION_REMOTE_FENCING_COMPLETE":"true",
        })
        self.assert_no_go(self.attempt(values=vals))

    def test_injected_custom_session_cannot_elevate_trust(self):
        class Attacker:
            def post(self,*a,**kw):
                raise AssertionError("malicious session may not send")
        self.assert_no_go(self.attempt(session=Attacker()))

    def test_even_real_requests_session_with_retry_policy_cannot_send(self):
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        client=requests.Session()
        try:
            client.mount("https://",HTTPAdapter(
                max_retries=Retry(total=5,read=5,allowed_methods={"POST"})
            ))
            self.assert_no_go(self.attempt(session=client))
        finally:
            client.close()

    def test_wrong_digest_still_blocks_earlier_than_hard_lock(self):
        result=self.attempt(expected_request_sha256="0"*64)
        self.assertEqual(result["state"],"BLOCKED_REQUEST_BINDING")
        self.assertIs(result["called"],False)

    def test_missing_legacy_approval_still_fails_before_lock(self):
        result=self.attempt(request_approved=False)
        self.assertEqual(result["state"],"BLOCKED_APPROVAL")
        self.assertIs(result["called"],False)

    def test_missing_provider_feature_still_blocks_before_lock(self):
        result=self.attempt(external_feature_enabled=False)
        self.assertEqual(result["state"],"BLOCKED_FEATURE_FLAG")
        self.assertIs(result["called"],False)

    def test_privacy_sensitive_input_not_sent(self):
        result=self.attempt(prompt="minha senha é segredo")
        self.assertEqual(result["state"],"BLOCKED_PRIVACY")
        self.assertIs(result["called"],False)

    def test_budget_denial_still_has_priority(self):
        result=self.attempt(
            budget={"allow_paid":False,"monthly_limit_usd":0},
        )
        self.assertEqual(result["state"],"BLOCKED_BUDGET")
        self.assertIs(result["called"],False)

    def test_source_lock_is_literal_true_not_environment_option(self):
        source=(
            Path(__file__).resolve().parents[1]/"atlasquant_aion_provider.py"
        ).read_text("utf-8")
        tree=ast.parse(source)
        assign=[
            node for node in tree.body
            if isinstance(node,ast.Assign)
            and any(isinstance(t,ast.Name)
                    and t.id=="_PAID_MODEL_DISPATCH_HARD_DENY"
                    for t in node.targets)
        ]
        self.assertEqual(len(assign),1)
        self.assertIsInstance(assign[0].value,ast.Constant)
        self.assertIs(assign[0].value.value,True)
        fn=next(node for node in tree.body
                if isinstance(node,ast.FunctionDef)
                and node.name=="execute_openai_answer")
        trust_guards=[
            x for x in ast.walk(fn)
            if isinstance(x,ast.If)
            and isinstance(x.test,ast.Compare)
            and isinstance(x.test.left,ast.Name)
            and x.test.left.id=="_PAID_MODEL_DISPATCH_HARD_DENY"
        ]
        self.assertEqual(len(trust_guards),1)
        network_lines=[
            n.lineno for n in ast.walk(fn)
            if isinstance(n,ast.Call)
            and isinstance(n.func,ast.Attribute)
            and n.func.attr=="post"
        ]
        self.assertEqual(len(network_lines),1)
        self.assertLess(trust_guards[0].lineno,network_lines[0])
        self.assertNotIn("os.environ.get",source[assign[0].lineno-1:
                                                assign[0].lineno+60])

    def test_lock_is_not_exported_as_host_config_feature(self):
        self.assertNotIn("_PAID_MODEL_DISPATCH_HARD_DENY",provider.__all__)
        self.assertTrue(provider._PAID_MODEL_DISPATCH_HARD_DENY)

    def test_missing_request_hash_never_enables_legacy_send(self):
        result=self.attempt(expected_request_sha256=None)
        self.assertEqual(result["state"],"BLOCKED_REQUEST_BINDING")
        self.assertFalse(result["called"])


if __name__=="__main__":
    unittest.main()
