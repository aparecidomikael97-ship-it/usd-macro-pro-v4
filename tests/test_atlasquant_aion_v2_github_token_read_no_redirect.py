"""Adversarial tests: GitHub token-bearing GETs must not auto-redirect.

Pure source fixtures and an exact no-network URL validator. DOES NOT
authenticate actual GitHub identity or grant permissions to read/write.
"""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from atlasquant_aion_v2_github_write_url_guard import (
    guard_github_token_read_destination,
)
from atlasquant_aion_v2_github_token_read_no_redirect_audit import (
    PASS,BLOCK,audit_token_github_read_sites,SITES,
)

FILE="atlasquant_shadow_store.py"
SITES_FIXTURE={FILE:("_fetch",)}
SOURCE='''from atlasquant_aion_v2_github_write_url_guard import guard_github_token_read_destination
import requests
def _fetch(repo,token,branch):
    url=f"https://api.github.com/repos/{repo}/contents/data.txt"
    return requests.get(
        guard_github_token_read_destination(url),
        headers={"Authorization":token},params={"ref":branch},
        timeout=7,allow_redirects=False,
    )
'''


class GitHubReadNoRedirectTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.write(SOURCE)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self,text):
        (self.root/FILE).write_text(text,encoding="utf-8")

    def review(self):
        return audit_token_github_read_sites(self.root,sites=SITES_FIXTURE)

    def rejected(self,reason):
        result=self.review()
        self.assertEqual(result["state"],BLOCK,result)
        self.assertIn(reason,{x["reason"] for x in result["findings"]})

    def test_known_source_satisfies_exact_session_token_get_guard(self):
        result=self.review()
        self.assertEqual(result["state"],PASS)
        self.assertEqual(result["exact_url_guard_and_no_redirect_sites"],1)
        self.assertFalse(result["network_called"])
        self.assertFalse(result["safe_to_deploy"])

    def test_actual_branch_enforces_27_github_token_gets(self):
        root=Path(__file__).resolve().parents[1]
        result=audit_token_github_read_sites(root)
        self.assertEqual(result["state"],PASS,str(result["findings"]))
        self.assertEqual(result["expected_token_github_get_sites"],27)
        self.assertEqual(result["exact_url_guard_and_no_redirect_sites"],27)
        self.assertEqual(result["production_files_reviewed"],12)
        self.assertTrue(result["token_redirects_disabled_in_source"])
        self.assertFalse(result["paid_dispatch_authorized"])

    def test_missing_import_blocks(self):
        self.write(SOURCE.replace(
            "from atlasquant_aion_v2_github_write_url_guard import guard_github_token_read_destination\n",""))
        self.rejected("PINNED_RUNTIME_READ_GUARD_IMPORT_MISSING")

    def test_import_alias_blocks(self):
        self.write(SOURCE.replace(
            "import guard_github_token_read_destination",
            "import guard_github_token_read_destination as untrusted",
        ))
        self.rejected("PINNED_RUNTIME_READ_GUARD_IMPORT_MISSING")

    def test_missing_guard_blocks(self):
        self.write(SOURCE.replace(
            "guard_github_token_read_destination(url)","url"))
        self.rejected("GITHUB_RUNTIME_READ_URL_GUARD_MISSING")

    def test_bypass_via_other_guard_blocks(self):
        self.write(SOURCE.replace(
            "guard_github_token_read_destination(url)","fake_guard(url)"))
        self.rejected("GITHUB_RUNTIME_READ_URL_GUARD_MISSING")

    def test_unsafe_redirect_true_blocks(self):
        self.write(SOURCE.replace("allow_redirects=False","allow_redirects=True"))
        self.rejected("GITHUB_READ_REDIRECT_MUST_BE_LITERAL_FALSE")

    def test_redirect_environment_variable_blocks(self):
        self.write(SOURCE.replace("allow_redirects=False","allow_redirects=enabled"))
        self.rejected("GITHUB_READ_REDIRECT_MUST_BE_LITERAL_FALSE")

    def test_redirect_default_missing_blocks(self):
        self.write(SOURCE.replace(",allow_redirects=False",""))
        self.rejected("GITHUB_READ_REDIRECT_MUST_BE_LITERAL_FALSE")

    def test_duplicate_redirect_keyword_blocks_even_if_both_false(self):
        self.write(SOURCE.replace(
            "allow_redirects=False","allow_redirects=False,allow_redirects=False"))
        self.rejected("GITHUB_READ_REDIRECT_MUST_BE_LITERAL_FALSE")

    def test_read_with_query_ref_missing_blocks(self):
        self.write(SOURCE.replace('params={"ref":branch},',""))
        self.rejected("GITHUB_GET_AUTH_REF_TIMEOUT_SHAPE_CHANGED")

    def test_read_without_explicit_headers_blocks(self):
        self.write(SOURCE.replace('headers={"Authorization":token},',""))
        self.rejected("GITHUB_GET_AUTH_REF_TIMEOUT_SHAPE_CHANGED")

    def test_read_without_timeout_blocks(self):
        self.write(SOURCE.replace("timeout=7,",""))
        self.rejected("GITHUB_GET_AUTH_REF_TIMEOUT_SHAPE_CHANGED")

    def test_duplicate_get_same_function_fails_closed(self):
        self.write(SOURCE.replace(
            "    return requests.get(","    requests.get('https://bad.invalid')\n    return requests.get("))
        self.rejected("EXACT_GITHUB_GET_SITE_MISSING_OR_DUPLICATED")

    def test_unknown_get_with_branch_ref_requires_review(self):
        self.write(SOURCE+'''
def intruder():
    return requests.get("https://unknown.invalid",params={"ref":"main"})
''')
        self.rejected("UNREVIEWED_REF_SCOPED_GET_ADDED")

    def test_source_invalid_syntax_blocks(self):
        self.write("def bad(\n")
        self.rejected("MISSING_OR_INVALID_SOURCE")

    def test_source_missing_file_blocks(self):
        (self.root/FILE).unlink()
        self.rejected("MISSING_OR_INVALID_SOURCE")

    def test_guard_rejects_host_spoofing_with_token_in_hand(self):
        for url in (
            "https://api.github.com.evil.test/repos/a/r/contents/f",
            "https://api.openai.com/repos/a/r/contents/f",
            "http://api.github.com/repos/a/r/contents/f",
            "https://api.github.com@evil.test/repos/a/r/contents/f",
            "https://api.github.com/repos/a/r/contents/%2e%2e",
            "https://api.github.com/repos/a/r/contents/../../secret",
            "https://api.github.com/repos/a/r/contents/x?ref=main",
            "https://api.github.com/repos/a/r/contents/x#redirect",
        ):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    guard_github_token_read_destination(url)

    def test_valid_known_github_content_read_route_is_inert(self):
        expected="https://api.github.com/repos/org/repo/contents/data/receipt.json"
        with patch("requests.get",side_effect=AssertionError("UNEXPECTED HTTP")), \
             patch("requests.sessions.Session.send",
                   side_effect=AssertionError("UNEXPECTED SEND")):
            self.assertEqual(guard_github_token_read_destination(expected),expected)

    def test_non_github_public_market_gets_are_not_rewritten_by_this_reference(self):
        root=Path(__file__).resolve().parents[1]
        txt=(root/"autopilot_v107.py").read_text("utf-8")
        self.assertIn('requests.get("https://api.twelvedata.com/time_series"',txt)
        txt2=(root/"currency_news_v107.py").read_text("utf-8")
        self.assertIn("https://newsapi.org/v2/everything",txt2)
        self.assertEqual(self.review()["state"],PASS)

    def test_token_read_schema_does_not_claim_owner_or_idp(self):
        result=self.review()
        self.assertFalse(result["idp_owner_trust_enrolled"])
        self.assertFalse(result["real_github_writes_authorized"])
        self.assertFalse(result["live_request_redirect_tested"])


if __name__=="__main__":
    unittest.main()
