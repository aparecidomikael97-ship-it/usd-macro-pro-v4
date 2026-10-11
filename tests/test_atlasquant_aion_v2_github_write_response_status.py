"""Synthetic response status and source mutation tests, no real GitHub traffic."""
from __future__ import annotations
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import tempfile
import unittest

from atlasquant_aion_v2_github_write_response_guard import (
    reject_github_write_unexpected_status, MODE_SUCCESS, MODE_CONFLICT,
    GitHubWriteOutcomeUnconfirmedError,
)
from atlasquant_aion_v2_github_write_response_audit import (
    PASS,BLOCK,audit_github_write_response_status,
)

FILE="atlasquant_flight_recorder_store.py"
SITE=frozenset({(FILE,"persist_records","requests.put")})
SOURCE="""from atlasquant_aion_v2_github_write_response_guard import reject_github_write_unexpected_status
import requests
def persist_records():
    return reject_github_write_unexpected_status(requests.put('https://api.github.com/repos/a/b/contents/f',headers={'Authorization':'fake'},timeout=7,allow_redirects=False),'contents_put')
"""

class GitHubWriteResponseTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.path=self.root/FILE
        self.path.write_text(SOURCE,encoding="utf-8")
    def tearDown(self):
        self.tmp.cleanup()
    def report(self):
        return audit_github_write_response_status(self.root,sites=SITE)
    def rejected(self,reason):
        report=self.report()
        self.assertEqual(report["state"],BLOCK,report)
        self.assertIn(reason,{f["reason"] for f in report["findings"]})

    def test_all_21_real_existing_write_sources_immediately_check_response(self):
        result=audit_github_write_response_status(Path(__file__).resolve().parents[1])
        self.assertEqual(result["state"],PASS,result["findings"])
        self.assertEqual(result["expected_write_sites"],21)
        self.assertEqual(result["exact_response_wrapped_sites"],21)
        self.assertEqual(result["files_reviewed"],14)
        self.assertFalse(result["safe_to_retry"])
        self.assertFalse(result["write_success_certified"])
        self.assertFalse(result["safe_to_deploy"])

    def test_documented_success_and_legacy_conflict_are_preserved(self):
        for mode in MODE_SUCCESS:
            for code in MODE_SUCCESS[mode]|MODE_CONFLICT[mode]:
                with self.subTest(mode=mode,code=code):
                    obj=SimpleNamespace(status_code=code)
                    self.assertIs(reject_github_write_unexpected_status(obj,mode),obj)

    def test_3xx_never_claims_success_even_when_body_is_forged(self):
        for mode in MODE_SUCCESS:
            for code in range(300,400):
                with self.subTest(mode=mode,code=code):
                    obj=SimpleNamespace(status_code=code,json=lambda:{"commit":{"sha":"FAKE"}})
                    with self.assertRaisesRegex(GitHubWriteOutcomeUnconfirmedError,"NO_RETRY_AUTHORITY"):
                        reject_github_write_unexpected_status(obj,mode)

    def test_ambiguous_success_and_wrong_operation_status_block(self):
        for mode in MODE_SUCCESS:
            for code in (None,True,False,"201",0,100,202,203,204,205,206,207,299,400,401,403,405,429,500,502,503,599):
                if type(code) is int and (code in MODE_SUCCESS[mode] or code in MODE_CONFLICT[mode]):
                    continue
                with self.subTest(mode=mode,code=code),self.assertRaises(GitHubWriteOutcomeUnconfirmedError):
                    reject_github_write_unexpected_status(SimpleNamespace(status_code=code),mode)
        with self.assertRaises(GitHubWriteOutcomeUnconfirmedError):
            reject_github_write_unexpected_status(SimpleNamespace(status_code=201),"unreviewed_mode")

    def test_variable_delete_fallback_404_compatible_but_not_success(self):
        obj=SimpleNamespace(status_code=404)
        self.assertIs(reject_github_write_unexpected_status(obj,"variable_patch"),obj)
        with self.assertRaises(GitHubWriteOutcomeUnconfirmedError):
            reject_github_write_unexpected_status(obj,"variable_post")
        with self.assertRaises(GitHubWriteOutcomeUnconfirmedError):
            reject_github_write_unexpected_status(obj,"contents_put")

    def test_malicious_204_on_file_write_is_rejected_before_legacy_raise_for_status(self):
        forged=SimpleNamespace(status_code=204,raise_for_status=lambda:None)
        with patch("requests.put",return_value=forged):
            import requests
            with self.assertRaises(GitHubWriteOutcomeUnconfirmedError):
                reject_github_write_unexpected_status(requests.put("https://example.invalid"),"contents_put")

    def test_unconfirmed_write_is_not_misclassified_as_corrupt_remote_json(self):
        # Legacy flight/research/shadow stores catch ValueError as remote
        # content corruption; the new transport outcome must bypass that.
        self.assertTrue(issubclass(GitHubWriteOutcomeUnconfirmedError,RuntimeError))
        self.assertFalse(issubclass(GitHubWriteOutcomeUnconfirmedError,ValueError))
        try:
            reject_github_write_unexpected_status(SimpleNamespace(status_code=302),"contents_put")
        except ValueError:
            self.fail("Transport uncertainty must not be labeled corrupt JSON")
        except GitHubWriteOutcomeUnconfirmedError:
            pass

    def test_synthetic_fixture_pinned(self):
        self.assertEqual(self.report()["state"],PASS)
        self.assertEqual(self.report()["exact_response_wrapped_sites"],1)
    def test_remove_wrapper_blocks(self):
        self.path.write_text(SOURCE.replace(
            "reject_github_write_unexpected_status(requests.put(","requests.put(")
            .replace("),'contents_put')",")"),encoding="utf-8")
        self.rejected("WRITE_RESULT_NOT_IMMEDIATELY_CHECKED")
    def test_wrong_method_mode_blocks(self):
        self.path.write_text(SOURCE.replace("'contents_put'","'variable_post'"),encoding="utf-8")
        self.rejected("WRITE_RESULT_NOT_IMMEDIATELY_CHECKED")
    def test_fake_wrapper_blocks(self):
        self.path.write_text(SOURCE.replace(
            "return reject_github_write_unexpected_status(","return always_allow("),encoding="utf-8")
        self.rejected("WRITE_RESULT_NOT_IMMEDIATELY_CHECKED")
    def test_alias_import_blocks(self):
        self.path.write_text(SOURCE.replace(
            "import reject_github_write_unexpected_status",
            "import reject_github_write_unexpected_status as insecure"),encoding="utf-8")
        self.rejected("RESPONSE_GUARD_PINNED_IMPORT_REQUIRED")
    def test_duplicate_write_blocks(self):
        self.path.write_text(SOURCE.replace(
            "    return reject_github",
            "    requests.put('https://evil.invalid')\n    return reject_github"),encoding="utf-8")
        self.rejected("EXACT_WRITE_SITE_NOT_UNIQUE")
    def test_unparseable_file_blocks(self):
        self.path.write_text("def incomplete(\n",encoding="utf-8")
        self.rejected("MISSING_OR_INVALID_SOURCE")
    def test_deleted_source_blocks(self):
        self.path.unlink()
        self.rejected("MISSING_OR_INVALID_SOURCE")

if __name__=="__main__":
    unittest.main()
