import json
import tempfile
import unittest
from pathlib import Path

from atlasquant_build_identity import (
    compare_deploy_identity,
    identity_marker_html,
    runtime_build_identity,
    source_fingerprint,
    short_source_fingerprint,
)


class AtlasQuantBuildIdentityTests(unittest.TestCase):
    def test_fingerprint_is_deterministic_and_changes_with_executable_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"a.py").write_text("A=1\n",encoding="utf-8")
            (root/"requirements.txt").write_text("streamlit\n",encoding="utf-8")
            first=source_fingerprint(root)
            self.assertEqual(first,source_fingerprint(root))
            (root/"a.py").write_text("A=2\n",encoding="utf-8")
            self.assertNotEqual(first,source_fingerprint(root))

    def test_tests_and_runtime_data_do_not_change_production_bundle_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"app.py").write_text("VALUE=1\n",encoding="utf-8")
            first=source_fingerprint(root)
            (root/"test_app.py").write_text("assert True\n",encoding="utf-8")
            (root/"dados").mkdir()
            (root/"dados"/"runtime.json").write_text('{"x":1}',encoding="utf-8")
            self.assertEqual(first,source_fingerprint(root))

    def test_short_identity_is_safe_non_secret_hex(self):
        value=short_source_fingerprint(Path(__file__).resolve().parent,16)
        self.assertEqual(len(value),16)
        self.assertTrue(all(ch in "0123456789abcdef" for ch in value))

    def test_missing_git_metadata_stays_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            identity=runtime_build_identity(
                env={},
                root=Path(tmp),
                release_id="",
                source_build="ab",
            )
        self.assertEqual(identity["commit_sha"],"UNKNOWN")
        self.assertEqual(identity["branch"],"UNKNOWN")
        self.assertEqual(identity["environment"],"UNKNOWN")
        self.assertEqual(identity["build_timestamp"],"UNKNOWN")
        self.assertEqual(identity["release_id"],"UNKNOWN")
        self.assertFalse(identity["commit_observed"])
        self.assertNotIn("RENDER_DEPLOY_HOOK_URL", identity)

    def test_invalid_commit_does_not_fall_through_to_another_value(self):
        identity=runtime_build_identity(
            env={
                "RENDER_GIT_COMMIT":"not-a-sha",
                "GIT_COMMIT":"a"*40,
                "RENDER_GIT_BRANCH":"main",
                "ATLASQUANT_BUILD_TIMESTAMP":"yesterday",
                "SOURCE_DATE_EPOCH":"1700000000",
            },
            root=Path(__file__).resolve().parent,
            release_id="11.0.8 — STRENGTH",
            source_build="0123456789abcdef",
        )
        self.assertEqual(identity["commit_sha"],"UNKNOWN")
        self.assertEqual(identity["branch"],"main")
        self.assertEqual(identity["build_timestamp"],"UNKNOWN")
        self.assertEqual(identity["release_id"],"11.0.8 — STRENGTH")
        self.assertEqual(identity["source_build"],"0123456789abcdef")

    def test_explicit_sha_and_epoch_are_reported(self):
        sha="9f6a9574e58b89b90c0e441dcb317bc37d7efe50"
        identity=runtime_build_identity(
            env={
                "RENDER_GIT_COMMIT":sha.upper(),
                "RENDER":"true",
                "SOURCE_DATE_EPOCH":"1700000000",
            },
            root=Path(__file__).resolve().parent,
            source_build="0123456789abcdef",
        )
        self.assertEqual(identity["commit_sha"],sha)
        self.assertEqual(identity["environment"],"render")
        self.assertEqual(identity["build_timestamp"],"2023-11-14T22:13:20Z")
        html=identity_marker_html(identity)
        self.assertIn(f'data-commit="{sha}"', html)
        self.assertIn("AQSHA:"+sha, html)
        self.assertNotIn("<script", html)
        poisoned=runtime_build_identity(
            env={
                "RENDER_GIT_COMMIT":sha,
                "RENDER_DEPLOY_HOOK_URL":"https://example.invalid/deploy-hook",
            },
            root=Path(__file__).resolve().parent,
            source_build="0123456789abcdef",
        )
        rendered=identity_marker_html(poisoned)
        self.assertNotIn("example.invalid", rendered)
        self.assertNotIn("deploy-hook", json.dumps(poisoned))

    def test_sha_match_mismatch_and_localhost(self):
        sha="9f6a9574e58b89b90c0e441dcb317bc37d7efe50"
        other="2c9dade6a87d6f618f05cbb628eb35cee2f3a8a1"
        matched=compare_deploy_identity(
            sha,
            sha,
            target_url="https://atlasquant-private.onrender.com",
        )
        self.assertEqual(matched["state"],"MATCH")
        self.assertTrue(matched["proves_production"])
        mismatched=compare_deploy_identity(
            sha,
            other,
            target_url="https://atlasquant-private.onrender.com",
        )
        self.assertEqual(mismatched["state"],"DEPLOY_IDENTITY_MISMATCH")
        self.assertFalse(mismatched["proves_production"])
        missing=compare_deploy_identity(
            sha,
            "",
            target_url="https://atlasquant-private.onrender.com",
        )
        self.assertEqual(missing["state"],"SHA_UNAVAILABLE")
        self.assertFalse(missing["proves_production"])
        local=compare_deploy_identity(
            sha,
            sha,
            target_url="http://127.0.0.1:8501",
        )
        self.assertEqual(local["state"],"LOCAL_OBSERVATION")
        self.assertFalse(local["proves_production"])


if __name__=="__main__":
    unittest.main()
