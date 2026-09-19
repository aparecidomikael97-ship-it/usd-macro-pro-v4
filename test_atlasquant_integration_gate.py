import unittest

from atlasquant_integration_gate import (
    evaluate_integration_candidate,
    integration_manifest_json,
)


GOOD_SHA="a"*40
BASE_SHA="b"*40


class AtlasQuantIntegrationGateTests(unittest.TestCase):
    def good(self, paths=None, **kw):
        data=dict(
            changed_paths=paths or ["atlasquant_ui_v1.py","test_atlasquant_ui_v1.py"],
            main_is_ancestor=True,
            compile_ok=True,
            preflight_ok=True,
            candidate_sha=GOOD_SHA,
            base_sha=BASE_SHA,
        )
        data.update(kw)
        return evaluate_integration_candidate(**data)

    def test_clean_source_only_candidate_is_reviewable_but_never_auto_merges(self):
        out=self.good()
        self.assertEqual(out["status"],"REVIEWABLE_SOURCE_ONLY")
        self.assertFalse(out["automatic_merge_allowed"])
        self.assertFalse(out["automatic_promotion_allowed"])
        self.assertFalse(out["runtime_data_copy_allowed"])
        self.assertTrue(out["manual_review_required"])
        self.assertTrue(out["quality_suite_external_required"])
        self.assertTrue(out["source_checkpoint_external_required"])

    def test_any_dados_change_blocks_source_candidate(self):
        out=self.good(["atlasquant_ui_v1.py","dados/autopilot_status_v107.json"])
        self.assertEqual(out["status"],"BLOCKED")
        self.assertTrue(out["runtime_or_data_files"])
        self.assertTrue(any("runtime/data" in x for x in out["blockers"]))

    def test_secret_like_paths_block_candidate(self):
        for path in (
            ".env",".env.production",".streamlit/secrets.toml","secrets.toml",
            "cert/private.pem","keys/app.key","credentials-prod.json",
            "service-account-prod.json",
        ):
            with self.subTest(path=path):
                out=self.good([path])
                self.assertEqual(out["status"],"BLOCKED")
                self.assertIn(path,out["secret_like_files"])

    def test_env_example_is_allowed(self):
        out=self.good([".env.example"])
        self.assertEqual(out["status"],"REVIEWABLE_SOURCE_ONLY")

    def test_candidate_must_include_current_main_ancestry(self):
        out=self.good(main_is_ancestor=False)
        self.assertEqual(out["status"],"BLOCKED")
        self.assertTrue(any("current main" in x for x in out["blockers"]))

    def test_compile_and_preflight_are_fail_closed(self):
        for field in ("compile_ok","preflight_ok"):
            with self.subTest(field=field):
                out=self.good(**{field:False})
                self.assertEqual(out["status"],"BLOCKED")

    def test_boolean_evidence_must_be_real_bool(self):
        for field in ("main_is_ancestor","compile_ok","preflight_ok"):
            for bad in ("true",1,None):
                with self.subTest(field=field,bad=bad):
                    out=self.good(**{field:bad})
                    self.assertEqual(out["status"],"BLOCKED")
                    self.assertTrue(any("Invalid boolean evidence" in x for x in out["blockers"]))

    def test_sha_identity_is_strict_and_candidate_cannot_equal_base(self):
        for candidate,base in (("abc",BASE_SHA),(GOOD_SHA,"bad"),(GOOD_SHA,GOOD_SHA)):
            with self.subTest(candidate=candidate,base=base):
                out=self.good(candidate_sha=candidate,base_sha=base)
                self.assertEqual(out["status"],"BLOCKED")

    def test_path_traversal_or_absolute_path_blocks(self):
        for path in ("../dados/x.json","/tmp/secret.txt","a/../../b"):
            with self.subTest(path=path):
                out=self.good([path])
                self.assertEqual(out["status"],"BLOCKED")
                self.assertTrue(any("Unsafe path" in x for x in out["blockers"]))

    def test_manifest_preserves_manual_contract(self):
        raw=integration_manifest_json(self.good())
        self.assertIn('"automatic_merge_allowed": false',raw)
        self.assertIn('"manual_review_required": true',raw)
        self.assertIn('"runtime_data_copy_allowed": false',raw)


if __name__=="__main__":
    unittest.main()
