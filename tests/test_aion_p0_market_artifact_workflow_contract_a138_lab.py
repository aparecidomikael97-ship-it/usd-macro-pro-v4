"""A138 conservative LAB CI contract: read-only token, no provider calls."""
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]
WF=ROOT/".github/workflows/aion-p0-market-artifact-only-a138-lab.yml"
PY=ROOT/"tools/aion_p0_market_artifact_only_a138.py"


class MarketArtifactOnlyWorkflowContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.wf=WF.read_text(encoding="utf-8")
        cls.src=PY.read_text(encoding="utf-8")

    def test_01_workflow_contents_read_only(self):
        self.assertRegex(self.wf,r"(?m)^permissions:\n  contents: read$")

    def test_02_workflow_never_declares_contents_write(self):
        self.assertNotRegex(self.wf,r"(?m)^\s+contents:\s*write\s*$")

    def test_03_no_scheduled_real_data_collection(self):
        self.assertNotRegex(self.wf,r"(?m)^  schedule:\s*$")

    def test_04_no_provider_secrets_in_offline_workflow(self):
        self.assertNotIn("secrets.",self.wf)
        self.assertNotIn("GITHUB_TOKEN_HISTORICO",self.wf)

    def test_05_no_write_credentials_passed_to_code(self):
        self.assertNotIn("github.token",self.wf)
        self.assertNotIn("GH_TOKEN_APP",self.wf)

    def test_06_checkout_token_not_persisted(self):
        self.assertIn("persist-credentials: false",self.wf)

    def test_07_artifact_written_outside_repo_in_runner_temp(self):
        self.assertIn("runner.temp",self.wf)
        self.assertIn("--source-root .",self.wf)

    def test_08_only_offline_source_and_manifest_handlers(self):
        self.assertNotIn("requests.",self.src)
        self.assertNotIn("httpx.",self.src)
        self.assertNotIn("urllib.request",self.src)
        self.assertNotIn("subprocess.",self.src)

    def test_09_no_runtime_checkpoint_selection_in_code(self):
        self.assertNotIn('dados/aion/checkpoint_master.json"',self.src)
        self.assertNotIn('dados/aion/checkpoint_master.json"',self.wf)

    def test_10_upload_artifact_retention_short(self):
        self.assertIn("retention-days: 3",self.wf)

    def test_11_does_not_invoke_existing_market_provider_scripts(self):
        for forbidden in (
            "autopilot_setup_audit_v114.py",
            "coleta_automatica_v86.py",
            "atlasquant_aion_global_worker.py",
        ):
            self.assertNotIn(forbidden,self.wf)

    def test_12_source_commit_still_not_independent_authority(self):
        self.assertIn("SELF_REPORTED_REPOSITORY_SHA_NOT_INDEPENDENT",self.src)
        self.assertIn("NOT_VERIFIED_STORED_REPOSITORY_COPY",self.src)

    def test_13_two_pinned_actions_and_persist_false(self):
        pins=re.findall(r"uses: actions/(?:checkout|setup-python)@[0-9a-f]{40}",self.wf)
        self.assertEqual(len(pins),2)

    def test_14_no_real_approval_flag_in_workflow(self):
        for forbidden in (
            "AION_RECOVERY_WITNESS_BYPASS",
            "AION_OWNER_APPROVED",
            "AION_INDEPENDENT_WITNESS_VERIFIED",
        ):
            self.assertNotIn(forbidden,self.wf)


if __name__=="__main__":
    unittest.main()
