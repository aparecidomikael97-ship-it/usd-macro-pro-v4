"""Mutation tests for full-repository paid AI network egress source audit."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from atlasquant_aion_v2_repository_paid_egress_static_audit import (
    SCHEMA,STATE_PASS,STATE_FAIL,
    audit_python_paid_egress,
)

# Deliberately small synthetic copy of the critical exported provider lock;
# it validates AST structure, not actual network execution or trust enrollment.
SEALED = '''
_PAID_MODEL_DISPATCH_HARD_DENY = True

def execute_openai_answer():
    if _PAID_MODEL_DISPATCH_HARD_DENY is True:
        return {
            "state":"BLOCKED_INDEPENDENT_TRUST_NOT_ENROLLED",
            "called":False,
            "paid_dispatch_authorized":False,
            "model_invocation_authorized":False,
            "provider_called":False,
        }
    return client.post("https://fixture.invalid")
'''


class StaticPaidEgressRepositoryAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.write("atlasquant_aion_provider.py",SEALED)

    def tearDown(self):
        self.temp.cleanup()

    def write(self,name,content):
        p=self.root/name
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(content,encoding="utf-8")

    def scan(self):
        result=audit_python_paid_egress(self.root)
        self.assertEqual(result["schema"],SCHEMA)
        self.assertFalse(result["network_called"])
        self.assertFalse(result["real_provider_called"])
        self.assertFalse(result["paid_dispatch_authorized"])
        self.assertFalse(result["safe_to_merge_or_deploy"])
        return result

    def fail(self,code):
        report=self.scan()
        self.assertEqual(report["state"],STATE_FAIL)
        self.assertIn(code,
                      [v["reason"] for v in report["violations"]])
        return report

    def test_only_explicit_sealed_locked_provider_site_passes(self):
        r=self.scan()
        self.assertEqual(r["state"],STATE_PASS)
        self.assertEqual(r["expected_sealed_send_site_count"],1)
        self.assertEqual(r["recognized_potential_send_sites"],1)
        self.assertEqual(r["production_python_files_scanned"],1)

    def test_new_direct_post_in_second_module_fails(self):
        self.write("atlasquant_aion_new_adapter.py",
                   "def bypass():\n    return client.post('https://unused.invalid')\n")
        r=self.fail("POTENTIAL_HTTP_SEND_METHOD")
        self.assertEqual(r["violations"][0]["path"],
                         "atlasquant_aion_new_adapter.py")

    def test_new_requests_post_alias_fails(self):
        self.write("atlasquant_aion_alt.py",
                   "import requests as req\ndef f():\n    return req.post('https://x.invalid')\n")
        self.fail("POTENTIAL_HTTP_SEND_METHOD")

    def test_new_requests_request_alias_fails(self):
        self.write("atlasquant_aion_alt.py",
                   "from requests import request as invoke\ndef f():\n"
                   "    return invoke('POST','https://x.invalid')\n")
        self.fail("POTENTIAL_HTTP_SEND_METHOD")

    def test_new_requests_session_send_fails(self):
        self.write("atlasquant_aion_alt.py",
                   "import requests\ndef f():\n    return requests.Session().send(None)\n")
        self.fail("POTENTIAL_HTTP_TRANSPORT_METHOD")

    def test_unscoped_openai_client_creation_fails(self):
        self.write("atlasquant_aion_alt.py",
                   "from openai import OpenAI as Vendor\ndef f():\n"
                   "    return Vendor(api_key='INERT')\n")
        self.fail("VENDOR_SDK_CREATION_OR_MODEL_CALL")

    def test_anthropic_messages_create_fails(self):
        self.write("atlasquant_aion_alt.py",
                   "def f(client):\n    return client.messages.create()\n")
        self.fail("UNSCOPED_MODEL_SDK_CALL")

    def test_google_genai_request_client_fails(self):
        self.write("atlasquant_aion_alt.py",
                   "import google.generativeai as g\ndef f():\n"
                   "    return g.GenerativeModel('fake')\n")
        self.fail("VENDOR_SDK_CREATION_OR_MODEL_CALL")

    def test_unscoped_fallback_urllib_urlopen_fails(self):
        self.write("atlasquant_aion_alt.py",
                   "import urllib.request as url\ndef f():\n"
                   "    return url.urlopen('https://x.invalid')\n")
        self.fail("POTENTIAL_RAW_HTTP_CLIENT")

    def test_httpx_async_post_fails(self):
        self.write("atlasquant_aion_alt.py",
                   "import httpx\nasync def f():\n"
                   "    async with httpx.AsyncClient() as client:\n"
                   "        return await client.post('https://x.invalid')\n")
        self.fail("POTENTIAL_HTTP_SEND_METHOD")

    def test_provider_second_post_site_blocks(self):
        self.write("atlasquant_aion_provider.py",
                   SEALED+"\ndef bypass():\n    return client.post('https://x.invalid')\n")
        r=self.fail("POTENTIAL_HTTP_SEND_METHOD")
        self.assertEqual(r["expected_sealed_send_site_count"],1)

    def test_turning_literal_hard_lock_false_blocks(self):
        self.write("atlasquant_aion_provider.py",
                   SEALED.replace("_PAID_MODEL_DISPATCH_HARD_DENY = True",
                                  "_PAID_MODEL_DISPATCH_HARD_DENY = False"))
        self.fail("PROVIDER_LOCK_NOT_LITERAL_TRUE")

    def test_second_reassignment_of_lock_blocks(self):
        self.write("atlasquant_aion_provider.py",
                   SEALED+"\n_PAID_MODEL_DISPATCH_HARD_DENY = False\n")
        self.fail("PROVIDER_LOCK_NOT_EXACT_SINGLE_ASSIGNMENT")

    def test_deleting_guard_blocks(self):
        self.write("atlasquant_aion_provider.py",
                   SEALED.replace("if _PAID_MODEL_DISPATCH_HARD_DENY is True:",
                                  "if other_flag is True:"))
        self.fail("REAL_PROVIDER_LOCK_GUARD_MISSING_OR_DUPLICATED")

    def test_replacing_return_state_blocks(self):
        self.write("atlasquant_aion_provider.py",
                   SEALED.replace("BLOCKED_INDEPENDENT_TRUST_NOT_ENROLLED",
                                  "ALLOWED_PAID_POST"))
        self.fail("LOCK_RETURN_STATE_CHANGED")

    def test_changing_called_to_true_blocks(self):
        self.write("atlasquant_aion_provider.py",
                   SEALED.replace('"called":False','"called":True'))
        self.fail("LOCK_RETURN_AUTHORITY_FLAG_NOT_FALSE:called")

    def test_turning_authorization_flag_true_blocks(self):
        self.write("atlasquant_aion_provider.py",
                   SEALED.replace('"paid_dispatch_authorized":False',
                                  '"paid_dispatch_authorized":True'))
        self.fail("LOCK_RETURN_AUTHORITY_FLAG_NOT_FALSE:paid_dispatch_authorized")

    def test_moving_post_before_gate_blocks(self):
        self.write("atlasquant_aion_provider.py",
                   SEALED.replace(
                       '    if _PAID_MODEL_DISPATCH_HARD_DENY is True:',
                       '    client.post("https://fixture.invalid")\n'
                       '    if _PAID_MODEL_DISPATCH_HARD_DENY is True:'))
        self.fail("REAL_PROVIDER_POST_SITE_UNEXPECTED")

    def test_tests_and_fixtures_never_count_as_production(self):
        self.write("tests/test_bypass.py",
                   "def fake():\n    return x.post('no-network')\n")
        self.write("test_legacy_provider.py",
                   "def fake():\n    return x.post('no-network')\n")
        self.write("fixtures/remote.py",
                   "def fake():\n    return x.post('no-network')\n")
        self.assertEqual(self.scan()["state"],STATE_PASS)

    def test_python_source_not_executed_or_imported(self):
        self.write("atlasquant_aion_inert.py",
                   'raise AssertionError("must NOT execute at audit time")\n')
        self.assertEqual(self.scan()["state"],STATE_PASS)

    def test_invalid_production_python_is_not_ignored(self):
        self.write("atlasquant_aion_alt.py","def wrong(\n")
        self.fail("UNREADABLE_OR_INVALID_PYTHON_SOURCE")

    def test_no_source_lock_provider_file_blocks_even_without_network(self):
        self.write("atlasquant_aion_provider.py",
                   "def execute_openai_answer():\n    return {}\n")
        self.fail("PROVIDER_LOCK_NOT_EXACT_SINGLE_ASSIGNMENT")

    def test_regression_audits_entire_actual_repository_branch(self):
        repo=Path(__file__).resolve().parents[1]
        result=audit_python_paid_egress(repo)
        self.assertGreater(result["production_python_files_scanned"],500)
        self.assertEqual(result["state"],STATE_PASS,repr(result["violations"][:20]))
        self.assertEqual(result["expected_sealed_send_site_count"],1)
        self.assertFalse(result["runtime_dynamic_imports_verified"])
        self.assertFalse(result["javascript_typescript_scanned"])
        self.assertFalse(result["third_party_dependencies_scanned"])


if __name__=="__main__":
    unittest.main()
