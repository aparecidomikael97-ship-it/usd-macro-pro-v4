"""GitHub write URL validator plus strict 21 real callsites no-redirect policy."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from atlasquant_aion_v2_github_write_url_guard import (
    guard_github_write_destination,
    GITHUB_ORIGIN,
)
from atlasquant_aion_v2_legacy_github_destination_source_review import (
    review_legacy_github_write_destinations,PASS,BLOCK,
    KNOWN_SITES,
)

VALID=(
    "https://api.github.com/repos/acme/aion/contents/data.json",
    "https://api.github.com/repos/acme/aion/contents/dados/sinais_v84.csv",
    "https://api.github.com/repos/a-b/.github/actions/variables",
    "https://api.github.com/repos/a-b/.github/actions/variables/AION_GLOBAL_WORKER",
    "https://api.github.com/repos/A_1/repo.2/contents/a/b/C-D_1.json",
)
BAD=(
    "http://api.github.com/repos/a/r/contents/file",
    "https://api.github.com.evil.invalid/repos/a/r/contents/file",
    "https://api.openai.com/repos/a/r/contents/file",
    "https://api.github.com:443/repos/a/r/contents/file",
    "https://api.github.com@evil.invalid/repos/a/r/contents/file",
    "https://a@api.github.com/repos/a/r/contents/file",
    "https://api.github.com/repos/a/r/contents/file?to=other",
    "https://api.github.com/repos/a/r/contents/file#anchor",
    "https://api.github.com/repos/a/r/contents/%2e%2e/secret",
    "https://api.github.com/repos/a/r/contents/../secret",
    "https://api.github.com/repos/a/r/contents/./secret",
    "https://api.github.com/repos/a/r/contents//secret",
    "https://api.github.com/repos/a/r/contents/foo\\bar",
    "https://api.github.com/repos/a/r/contents/file name",
    "https://api.github.com/repos/a/r/contents/naïve",
    "https://api.github.com/repos/a/r/contents/file\nAuthorization:Bearer",
    "https://api.github.com/repos/a/r/contents/file\r",
    "https://api.github.com/repos/a/r/contents/",
    "https://api.github.com/repos/a/r/contents",
    "https://api.github.com/repos/a/r/actions/variables/flag/extra",
    "https://api.github.com/repos/a/r/actions/variable",
    "https://api.github.com/repos/a/r/models",
    "https://api.github.com/repos/a/r/issues/123",
    "https://api.github.com/repos//r/contents/file",
    "https://api.github.com/repos/a//contents/file",
    "https://api.github.com/repos/a/r/contents/:malformed",
    "https://api.github.com/repos/a/r/contents/file;%2F",
    "HTTPS://api.github.com/repos/a/r/contents/file",
    "//api.github.com/repos/a/r/contents/file",
    "https://API.github.com/repos/a/r/contents/file",
)
FIXTURE_SITE=frozenset({
    ("atlasquant_shadow_store.py","persist_shadow_samples","requests.put"),
})
SOURCE = '''from atlasquant_aion_v2_github_write_url_guard import guard_github_write_destination
def _url(repo):
    return f"https://api.github.com/repos/{repo}/contents/dados/shadow.csv"
def persist_shadow_samples(repo):
    return requests.put(guard_github_write_destination(_url(repo)),
                        allow_redirects=False,timeout=6)
'''


class GitHubWriteURLRuntimeGuardTests(unittest.TestCase):
    def test_exact_https_fixed_origin_valid_git_contents_and_actions_routes(self):
        for url in VALID:
            with self.subTest(url=url):
                self.assertEqual(guard_github_write_destination(url),url)

    def test_mutated_urls_rejected_before_any_network(self):
        for url in BAD:
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    guard_github_write_destination(url)

    def test_non_string_and_overlong_destination_rejected(self):
        for url in (None,True,False,0,12,{},[],b"https://api.github.com",
                    GITHUB_ORIGIN+"/repos/a/r/contents/"+"x"*2050):
            with self.subTest(url=repr(url)[:100]):
                with self.assertRaises(ValueError):
                    guard_github_write_destination(url)

    def test_no_http_transport_even_for_valid_url(self):
        with patch("requests.sessions.Session.send",
                   side_effect=AssertionError("NO NETWORK")), \
             patch("requests.put",side_effect=AssertionError("NO WRITE")):
            self.assertEqual(guard_github_write_destination(VALID[0]),
                             VALID[0])

    def test_invalid_base_root_same_string_prefix_denied(self):
        malicious=(
            "https://api.github.com/repos/a/r/contents/../../models",
            "https://api.github.com/repos/a/r/contents/%252e%252e",
            "https://api.github.com/repos/a/r/contents/abc?redirect=https://evil",
            "https://api.github.com/repos/a/r/actions/variables/x/y",
        )
        for url in malicious:
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    guard_github_write_destination(url)

    def test_no_scope_credentials_or_backend_authorization_conferred(self):
        self.assertFalse(hasattr(guard_github_write_destination,"paid_dispatch_authorized"))
        self.assertEqual(guard_github_write_destination(VALID[0]),VALID[0])

    def test_every_real_legacy_write_ast_has_guard_and_no_redirect(self):
        root=Path(__file__).resolve().parents[1]
        result=review_legacy_github_write_destinations(root)
        self.assertEqual(result["state"],PASS,repr(result["findings"]))
        self.assertEqual(result["analyzed_legacy_write_callsites"],21)
        self.assertEqual(result["github_origin_and_route_bound_sites"],21)
        self.assertTrue(result["write_sites_require_guard_and_no_redirect"])
        self.assertTrue(result["write_redirects_explicitly_disabled"])
        self.assertFalse(result["network_called"])
        self.assertFalse(result["github_writes_authorized"])
        self.assertFalse(result["redirect_chain_verified_closed"])
        self.assertEqual(len(KNOWN_SITES),21)

    def test_working_valid_source_fixture_enforces_both_guards(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/"atlasquant_shadow_store.py"
            p.write_text(SOURCE,"utf-8")
            output=review_legacy_github_write_destinations(
                Path(temp),sites=FIXTURE_SITE,require_runtime_guards=True,
            )
            self.assertEqual(output["state"],PASS,output["findings"])

    def _mutation(self,text,reason):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/"atlasquant_shadow_store.py"
            p.write_text(text,"utf-8")
            output=review_legacy_github_write_destinations(
                Path(temp),sites=FIXTURE_SITE,require_runtime_guards=True,
            )
            self.assertEqual(output["state"],BLOCK)
            self.assertIn(reason,{x["reason"] for x in output["findings"]})

    def test_source_removing_runtime_url_guard_fails_ci(self):
        self._mutation(SOURCE.replace(
            "guard_github_write_destination(_url(repo))","_url(repo)"
        ),"REQUIRED_RUNTIME_GITHUB_DESTINATION_GUARD_MISSING")

    def test_source_removing_no_redirect_flag_fails_ci(self):
        self._mutation(SOURCE.replace("allow_redirects=False,",""),
                       "EXPLICIT_REDIRECT_POLICY_UNSAFE")

    def test_source_adding_true_redirect_flag_fails_ci(self):
        self._mutation(SOURCE.replace("allow_redirects=False",
                                     "allow_redirects=True"),
                       "EXPLICIT_REDIRECT_POLICY_UNSAFE")

    def test_source_using_caller_redirect_bool_fails_ci(self):
        self._mutation(SOURCE.replace("allow_redirects=False",
                                     "allow_redirects=allow"),
                       "EXPLICIT_REDIRECT_POLICY_UNSAFE")

    def test_source_removing_import_fails_ci(self):
        self._mutation(SOURCE.replace(
            "from atlasquant_aion_v2_github_write_url_guard import guard_github_write_destination\n",
            "",
        ),"GITHUB_WRITE_GUARD_IMPORT_NOT_TRUSTED")

    def test_source_rebinding_host_after_guard_fails_ci(self):
        self._mutation(SOURCE.replace(
            "https://api.github.com","https://api.openai.com",
        ),"DESTINATION_NOT_GITHUB_SOURCE_BOUND")

    def test_source_missing_file_fails_ci(self):
        with tempfile.TemporaryDirectory() as temp:
            result=review_legacy_github_write_destinations(
                Path(temp),sites=FIXTURE_SITE,require_runtime_guards=True,
            )
            self.assertEqual(result["state"],BLOCK)

    def test_source_runtime_guard_fails_if_wrapped_call_is_wrong(self):
        self._mutation(SOURCE.replace(
            "guard_github_write_destination(_url(repo))",
            "unknown_transport_url_guard(_url(repo))",
        ),"REQUIRED_RUNTIME_GITHUB_DESTINATION_GUARD_MISSING")

    def test_source_new_redirect_argument_duplicate_fails_ci(self):
        self._mutation(SOURCE.replace(
            "allow_redirects=False,timeout=6",
            "allow_redirects=False,allow_redirects=False,timeout=6",
        ),"EXPLICIT_REDIRECT_POLICY_UNSAFE")


if __name__=="__main__":
    unittest.main()
