"""Adversarial source-only GitHub write URL provenance mutation checks."""
from __future__ import annotations
from pathlib import Path
import tempfile
import unittest

from atlasquant_aion_v2_legacy_github_destination_source_review import (
    PASS,BLOCK,SCHEMA,review_legacy_github_write_destinations,
)

FILE="atlasquant_shadow_store.py"
SITE=frozenset({(FILE,"persist_samples","requests.put")})
BASE='''
def persist_samples(repo, token):
    url=f"https://api.github.com/repos/{repo}/contents/dados/shadow.csv"
    r=requests.put(url, headers={"Authorization":token}, timeout=5)
    return r
'''
ACTIONS="atlasquant_aion_global_worker_activation.py"
ACT_SITE=frozenset({(
    ACTIONS,"write_repository_feature_flag_enabled","requests.patch",
)})
ACT_SRC='''
def _variable_collection_url(config):
    return f"https://api.github.com/repos/{config.repo}/actions/variables"
def _variable_url(config):
    name=quote(FEATURE_FLAG_NAME,safe="")
    return f"{_variable_collection_url(config)}/{name}"
def write_repository_feature_flag_enabled(config):
    return requests.patch(_variable_url(config),json={"value":"true"})
'''


class GitHubDestinationSourceReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.write(FILE,BASE)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self,path,text):
        p=self.root/path
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(text,"utf-8")

    def check(self,sites=SITE):
        r=review_legacy_github_write_destinations(self.root,sites=sites)
        self.assertEqual(r["schema"],SCHEMA)
        self.assertFalse(r["network_called"])
        self.assertFalse(r["github_writes_authorized"])
        self.assertFalse(r["safe_to_deploy"])
        self.assertFalse(r["real_provider_called"])
        self.assertFalse(r["interpolated_repo_and_path_sanitized"])
        return r

    def denied(self,reason,sites=SITE):
        r=self.check(sites)
        self.assertEqual(r["state"],BLOCK)
        self.assertIn(reason,{x["reason"] for x in r["findings"]})

    def test_fixed_github_https_origin_and_contents_path_accepted_as_math(self):
        r=self.check()
        self.assertEqual(r["state"],PASS)
        self.assertEqual(r["github_origin_and_route_bound_sites"],1)
        self.assertFalse(r["redirect_chain_verified_closed"])

    def test_github_origin_changed_to_paid_vendor_rejected(self):
        self.write(FILE,BASE.replace("https://api.github.com",
                                    "https://api.openai.com"))
        self.denied("DESTINATION_NOT_GITHUB_SOURCE_BOUND")

    def test_fake_github_subdomain_rejected(self):
        self.write(FILE,BASE.replace("https://api.github.com",
                                    "https://api.github.com.evil.invalid"))
        self.denied("DESTINATION_NOT_GITHUB_SOURCE_BOUND")

    def test_http_instead_of_https_denied(self):
        self.write(FILE,BASE.replace("https://api.github.com",
                                    "http://api.github.com"))
        self.denied("DESTINATION_NOT_GITHUB_SOURCE_BOUND")

    def test_query_only_url_denied(self):
        self.write(FILE,BASE.replace(
            "f\"https://api.github.com/repos/{repo}/contents/dados/shadow.csv\"",
            "f\"https://api.github.com/repos/{repo}?private=true\"",
        ))
        self.denied("DESTINATION_NOT_GITHUB_SOURCE_BOUND")

    def test_attacker_controlled_url_variable_denied(self):
        self.write(FILE,BASE.replace(
            'url=f"https://api.github.com/repos/{repo}/contents/dados/shadow.csv"',
            'url=repo',
        ))
        self.denied("DESTINATION_NOT_GITHUB_SOURCE_BOUND")

    def test_second_url_reassignment_denied(self):
        self.write(FILE,BASE.replace(
            "    r=requests.put",
            '    url="https://other.invalid/stolen"\n    r=requests.put',
        ))
        self.denied("DESTINATION_NOT_GITHUB_SOURCE_BOUND")

    def test_direct_unaudited_url_expression_denied(self):
        self.write(FILE,BASE.replace(
            "requests.put(url,","requests.put(make_url(repo),",
        ))
        self.denied("DESTINATION_NOT_GITHUB_SOURCE_BOUND")

    def test_explicit_redirect_true_denied(self):
        self.write(FILE,BASE.replace(
            "timeout=5","timeout=5,allow_redirects=True",
        ))
        self.denied("EXPLICIT_REDIRECT_POLICY_UNSAFE")

    def test_explicit_redirect_from_env_denied(self):
        self.write(FILE,BASE.replace(
            "timeout=5","timeout=5,allow_redirects=trusted",
        ))
        self.denied("EXPLICIT_REDIRECT_POLICY_UNSAFE")

    def test_explicit_redirect_false_allowed_but_network_still_not_authorized(self):
        self.write(FILE,BASE.replace(
            "timeout=5","timeout=5,allow_redirects=False",
        ))
        self.assertEqual(self.check()["state"],PASS)
        self.assertFalse(self.check()["github_writes_authorized"])

    def test_other_path_which_is_not_github_contents_denied(self):
        self.write(FILE,BASE.replace("/contents/","/models/"))
        self.denied("DESTINATION_NOT_GITHUB_SOURCE_BOUND")

    def test_missing_file_denied(self):
        (self.root/FILE).unlink()
        self.denied("UNREADABLE_SOURCE_OR_MISSING_FILE")

    def test_syntax_error_denied(self):
        self.write(FILE,"def broken(\n")
        self.denied("UNREADABLE_SOURCE_OR_MISSING_FILE")

    def test_duplicate_network_call_denied(self):
        self.write(FILE,BASE.replace("    return r",
                                    "    requests.put(url)\n    return r"))
        self.denied("EXACT_NETWORK_WRITE_NOT_UNIQUE")

    def test_missing_network_call_denied(self):
        self.write(FILE,BASE.replace("requests.put(","requests.get("))
        self.denied("EXACT_NETWORK_WRITE_NOT_UNIQUE")

    def test_valid_github_url_helper_is_source_checked(self):
        self.write(FILE,'''
def _url(repo):
    return f"https://api.github.com/repos/{repo}/contents/data.json"
def persist_samples(repo,token):
    return requests.put(_url(repo))
''')
        self.assertEqual(self.check()["state"],PASS)

    def test_modified_helper_to_vendored_destination_denied(self):
        self.write(FILE,'''
def _url(repo):
    return f"https://api.openai.com/repos/{repo}/contents/data.json"
def persist_samples(repo,token):
    return requests.put(_url(repo))
''')
        self.denied("DESTINATION_NOT_GITHUB_SOURCE_BOUND")

    def test_unrecognized_helper_function_denied(self):
        self.write(FILE,'''
def fallback_url(repo):
    return f"https://api.github.com/repos/{repo}/contents/a"
def persist_samples(repo):
    return requests.put(fallback_url(repo))
''')
        self.denied("DESTINATION_NOT_GITHUB_SOURCE_BOUND")

    def test_variable_flag_helper_with_urlencoding_passes_math(self):
        self.write(ACTIONS,ACT_SRC)
        self.assertEqual(self.check(ACT_SITE)["state"],PASS)
        self.assertEqual(self.check(ACT_SITE)["github_actions_variable_sites"],1)

    def test_variable_flag_helper_rebinding_to_other_host_denied(self):
        self.write(ACTIONS,ACT_SRC.replace(
            "https://api.github.com","https://api.openai.com",
        ))
        self.denied("DESTINATION_NOT_GITHUB_SOURCE_BOUND",ACT_SITE)

    def test_variable_flag_helper_requires_percent_encoding(self):
        self.write(ACTIONS,ACT_SRC.replace(
            'quote(FEATURE_FLAG_NAME,safe="")','FEATURE_FLAG_NAME',
        ))
        self.denied("DESTINATION_NOT_GITHUB_SOURCE_BOUND",ACT_SITE)

    def test_duplicate_github_helper_function_denied(self):
        self.write(ACTIONS,ACT_SRC.replace(
            "def _variable_url(config):",
            "def _variable_collection_url(config):\n"
            '    return "https://external.invalid/"\n'
            "def _variable_url(config):",
        ))
        self.denied("DESTINATION_NOT_GITHUB_SOURCE_BOUND",ACT_SITE)

    def test_never_executes_injected_malicious_source(self):
        self.write(FILE,"raise RuntimeError('never execute me')\n"+BASE)
        self.assertEqual(self.check()["state"],PASS)

    def test_actual_21_caller_source_bindings_on_checked_out_branch(self):
        root=Path(__file__).resolve().parents[1]
        r=review_legacy_github_write_destinations(root)
        self.assertEqual(r["analyzed_legacy_write_callsites"],21)
        self.assertEqual(r["github_repository_contents_sites"],17)
        self.assertEqual(r["github_actions_variable_sites"],4)
        self.assertEqual(r["state"],PASS,str(r["findings"]))
        self.assertEqual(r["github_origin_and_route_bound_sites"],21)
        self.assertFalse(r["redirect_chain_verified_closed"])


if __name__=="__main__":
    unittest.main()
