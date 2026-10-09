"""Synthetic no-network 3xx/body forgery + all 28 production sources audit."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import tempfile
import unittest

from atlasquant_aion_v2_github_read_response_guard import reject_github_read_unexpected_status
from atlasquant_aion_v2_github_read_response_audit import (
    PASS,BLOCK,audit_github_get_response_status,
)

FILE="atlasquant_shadow_store.py"
FIXTURE={FILE:("_fetch",)}
SOURCE="""from atlasquant_aion_v2_github_read_response_guard import reject_github_read_unexpected_status
import requests
def _fetch():
    return reject_github_read_unexpected_status(requests.get('https://api.github.com/repos/x/y/contents/state', headers={'Authorization':'synthetic'}, params={'ref':'main'}, timeout=7, allow_redirects=False))
"""

class GitHubGetResponseStatusTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.path=self.root/FILE
        self.path.write_text(SOURCE,encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def review(self):
        return audit_github_get_response_status(self.root,sites=FIXTURE)

    def rejected(self,reason):
        report=self.review()
        self.assertEqual(report["state"],BLOCK,report)
        self.assertIn(reason,{v["reason"] for v in report["findings"]})

    def test_200_and_404_preserved_identity(self):
        for status in (200,404):
            obj=SimpleNamespace(status_code=status,json=lambda:{"content":"synthetic"})
            self.assertIs(reject_github_read_unexpected_status(obj),obj)
        self.assertEqual(self.review()["state"],PASS)

    def test_all_3xx_including_forged_json_are_blocked(self):
        for status in range(300,400):
            obj=SimpleNamespace(status_code=status,json=lambda:{"sha":"spoofed","content":"fake"})
            with self.subTest(status=status),self.assertRaisesRegex(ValueError,"BLOCKED_GITHUB_GET_UNEXPECTED_STATUS"):
                reject_github_read_unexpected_status(obj)

    def test_every_other_status_and_bad_status_type_are_blocked(self):
        for status in (None,True,False,"200","302",0,100,201,202,204,206,299,400,401,403,500,599,600):
            with self.subTest(status=status),self.assertRaises(ValueError):
                reject_github_read_unexpected_status(SimpleNamespace(status_code=status))

    def test_mocked_requests_302_can_not_become_confirmed(self):
        forged=SimpleNamespace(status_code=302,json=lambda:{"content":"fake"})
        with patch("requests.get",return_value=forged):
            import requests
            with self.assertRaises(ValueError):
                reject_github_read_unexpected_status(requests.get("https://api.github.com/repos/x/y/contents/dummy"))

    def test_actual_branch_28_sites_are_guarded(self):
        report=audit_github_get_response_status(Path(__file__).resolve().parents[1])
        self.assertEqual(report["state"],PASS,report["findings"])
        self.assertEqual(report["expected_github_token_get_sites"],28)
        self.assertEqual(report["exact_response_status_wrapped_sites"],28)
        self.assertEqual(report["files_scanned"],12)
        self.assertFalse(report["paid_provider_authorized"])
        self.assertFalse(report["safe_to_deploy"])

    def test_missing_import_fails(self):
        self.path.write_text(SOURCE.replace(
            "from atlasquant_aion_v2_github_read_response_guard import reject_github_read_unexpected_status\n",""),encoding="utf-8")
        self.rejected("STATUS_GUARD_PINNED_IMPORT_REQUIRED")

    def test_alias_import_fails(self):
        self.path.write_text(SOURCE.replace(
            "import reject_github_read_unexpected_status","import reject_github_read_unexpected_status as ignored"),encoding="utf-8")
        self.rejected("STATUS_GUARD_PINNED_IMPORT_REQUIRED")

    def test_missing_wrapper_fails(self):
        self.path.write_text(SOURCE.replace(
            "reject_github_read_unexpected_status(requests.get(","requests.get(").replace(
            "allow_redirects=False))","allow_redirects=False)"),encoding="utf-8")
        self.rejected("GITHUB_GET_RESPONSE_NOT_WRAPPED_IMMEDIATELY")

    def test_fake_wrapper_fails(self):
        self.path.write_text(SOURCE.replace(
            "return reject_github_read_unexpected_status(requests.get(",
            "return pretend_safe(requests.get("),encoding="utf-8")
        self.rejected("GITHUB_GET_RESPONSE_NOT_WRAPPED_IMMEDIATELY")

    def test_duplicate_get_fails(self):
        self.path.write_text(SOURCE.replace(
            "    return reject_github",
            "    requests.get('https://evil.invalid')\n    return reject_github"),encoding="utf-8")
        self.rejected("EXACT_AUTHENTICATED_GET_NOT_UNIQUE")

    def test_missing_file_fails(self):
        self.path.unlink()
        self.rejected("SOURCE_NOT_AVAILABLE_OR_INVALID")

    def test_no_production_authority_claimed(self):
        report=self.review()
        self.assertFalse(report["github_response_provenance_verified"])
        self.assertFalse(report["external_proxy_tls_verified"])
        self.assertFalse(report["real_github_write_authorized"])

if __name__=="__main__":
    unittest.main()
