"""Offline, non-operational first-install NO-GO regression for the currently unenrolled state."""
from __future__ import annotations
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from atlasquant_aion_global_worker_source_gate_v1 import independent_worker_source_preflight

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/"docs/aion/evidence/AION_WITNESS_EXTERNAL_ENROLLMENT_GATE_V1.json"
WORKER=ROOT/"atlasquant_aion_global_worker.py"
READINESS=ROOT/"atlasquant_aion_global_worker_readiness.py"
WORKFLOW=ROOT/".github/workflows/aion-global-worker-readiness.yml"
REQUIRED_IDS={
    "SOURCE_ROOT_ENROLLMENT","OWNER_IDENTITY_CEREMONY",
    "TENANT_RESOURCE_REGISTRY","ADMIN_FAILURE_DOMAIN_SEPARATION",
    "COORDINATOR_ATOMIC_CAS","COORDINATOR_ROLLBACK_TEST",
    "SECOND_DOMAIN_IMMUTABLE_HISTORY","SECOND_DOMAIN_CURRENT_HEAD",
    "FRESH_NONCE_CHALLENGE","INDEPENDENT_KEY_CUSTODY",
    "CROSS_DOMAIN_PARTIAL_COMMIT","B2B_CROSS_TENANT_NEGATIVE_TESTS",
    "OWNER_WINDOWS_PHYSICAL_VALIDATION","RECOVERY_REVOCATION_BREAK_GLASS",
    "LGPD_RESIDENCY_AND_OPERATORS","FULL_BRL_BUDGET_QUOTE",
    "CLOUDFLARE_SECURITY_ROUTE_NO_BYPASS",
    "CLOUDFLARE_DO_SINGLE_OBJECT_STORAGE_HEADROOM",
    "FINANCIAL_SPEND_APPROVAL","RELEASE_MERGE_DEPLOY_APPROVAL",
}
AUTHORITY_FLAGS=(
    "production_trust_verified","worker_authorized",
    "remote_witness_configured","independent_custody_verified",
    "full_quote_brl_verified","provider_approved",
    "owner_approved_spend","owner_approved_deploy",
    "automatic_retry_authorized",
)

class FirstInstallEvidenceNoGoTests(unittest.TestCase):
    def read_manifest(self):
        return json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_manifest_is_explicitly_unenrolled_and_without_authority(self):
        data=self.read_manifest()
        self.assertEqual(data["schema"],"AION_EXTERNAL_CHECKPOINT_WITNESS_EVIDENCE_MANIFEST_V1")
        self.assertEqual(data["status"],"HARD_NO_GO")
        self.assertEqual(data["mode"],"NO_AUTHORITY")
        self.assertEqual(data["purpose"],"PRE-ENROLLMENT PROCUREMENT AND EXTERNAL EVIDENCE TRACKING ONLY")
        for name in AUTHORITY_FLAGS:
            with self.subTest(flag=name):
                self.assertIs(data[name],False)

    def test_all_twenty_evidence_gates_remain_without_independent_receipts(self):
        rows=self.read_manifest()["evidence_gates"]
        ids=[r["id"] for r in rows]
        self.assertEqual(len(ids),20)
        self.assertEqual(len(ids),len(set(ids)))
        self.assertEqual(set(ids),REQUIRED_IDS)
        for row in rows:
            with self.subTest(gate=row["id"]):
                self.assertEqual(row["state"],"BLOCKED")
                self.assertIsNone(row["evidence_uri"])
                self.assertIsNone(row["evidence_sha256"])
                self.assertIsNone(row["independent_verifier"])
                self.assertTrue(row.get("evidence_class"))
                self.assertTrue(row.get("description"))

    def test_forged_caller_owner_admin_or_enrollment_cannot_unlock_source(self):
        cases=(None,{},object(),
               {"status":"VERIFIED","source_verified":True,"owner_approved_deploy":True},
               SimpleNamespace(role="HUMAN_OWNER",approved=True,authenticated=True,
                               repo="fake/repo",branch="atlasquant-runtime",
                               tenant_id="synthetic-tenant",worker_authorized=True))
        with patch("socket.socket.connect",side_effect=AssertionError("NO_NETWORK")), \
             patch("socket.socket.connect_ex",side_effect=AssertionError("NO_NETWORK")):
            for cfg in cases:
                with self.subTest(type=str(type(cfg))):
                    out=independent_worker_source_preflight(cfg)
                    self.assertEqual(out["status"],"BLOCKED")
                    self.assertEqual(out["reason"],"INDEPENDENT_CHECKPOINT_SOURCE_UNAVAILABLE")
                    for field in ("source_verified","worker_authorized","network_called","safe_to_retry"):
                        self.assertIs(out[field],False)
                    self.assertIs(out["reconciliation_required"],True)

    def test_worker_source_preflight_is_before_first_private_read_and_execution(self):
        src=WORKER.read_text(encoding="utf-8")
        body=src[src.index("def run_global_worker_once("):]
        idx=body.index("independent_worker_source_preflight(cfg)")
        self.assertLess(idx,body.index("load_runtime_checkpoint(cfg"))
        self.assertLess(idx,body.index("_persist_runtime_checkpoint_cas("))
        self.assertLess(idx,body.index("_execute_due_local_work_authorized("))
        self.assertIn('origin.get("status") != "VERIFIED"',body)
        self.assertIn('origin.get("source_verified") is not True',body)

    def test_readiness_cli_does_not_read_credential_before_source_gate(self):
        src=READINESS.read_text(encoding="utf-8")
        cli=src[src.index("def _cli() -> int:"):]
        self.assertLess(cli.index("independent_worker_source_preflight(config)"),
                        cli.index('os.getenv("GITHUB_TOKEN_HISTORICO"'))
        self.assertIn('runtime = {"status": "SOURCE_UNBOUND"}',cli)
        self.assertIn('"SKIPPED_SOURCE_UNBOUND"',cli)

    def test_operational_readiness_blocked_exit_is_not_masked(self):
        wf=WORKFLOW.read_text(encoding="utf-8")
        step=wf.split("- name: Run read-only activation readiness",1)[1].split(
            "- name: Readiness summary",1)[0]
        self.assertIn("set -o pipefail",step)
        self.assertIn("atlasquant_aion_global_worker_readiness.py --check-runtime",step)
        self.assertNotIn("|| true",step)
        self.assertNotIn("continue-on-error: true",step)
        self.assertNotIn("exit 0",step)
        self.assertIn("permissions:\n  contents: read",wf)

if __name__=="__main__":
    unittest.main()
