"""P0 external witness procurement/evidence manifest is NOT authority.

Negative tests assert absence of real enrollment evidence and verify that
production Worker/readiness remain hard-denied despite an attractive design.
No cloud accounts, HTTP, credentials, private keys, or production checkpoint.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT/"docs/aion/evidence/AION_WITNESS_EXTERNAL_ENROLLMENT_GATE_V1.json"
PLAN = ROOT/"docs/aion/AION_EXTERNAL_WITNESS_OWNER_DECISION_PLAN_20261010.md"

GATES = frozenset({
    "SOURCE_ROOT_ENROLLMENT",
    "OWNER_IDENTITY_CEREMONY",
    "TENANT_RESOURCE_REGISTRY",
    "ADMIN_FAILURE_DOMAIN_SEPARATION",
    "COORDINATOR_ATOMIC_CAS",
    "COORDINATOR_ROLLBACK_TEST",
    "SECOND_DOMAIN_IMMUTABLE_HISTORY",
    "SECOND_DOMAIN_CURRENT_HEAD",
    "FRESH_NONCE_CHALLENGE",
    "INDEPENDENT_KEY_CUSTODY",
    "CROSS_DOMAIN_PARTIAL_COMMIT",
    "B2B_CROSS_TENANT_NEGATIVE_TESTS",
    "OWNER_WINDOWS_PHYSICAL_VALIDATION",
    "RECOVERY_REVOCATION_BREAK_GLASS",
    "LGPD_RESIDENCY_AND_OPERATORS",
    "FULL_BRL_BUDGET_QUOTE",
    "CLOUDFLARE_SECURITY_ROUTE_NO_BYPASS",
    "CLOUDFLARE_DO_SINGLE_OBJECT_STORAGE_HEADROOM",
    "FINANCIAL_SPEND_APPROVAL",
    "RELEASE_MERGE_DEPLOY_APPROVAL",
})
FLAG_FIELDS = (
    "production_trust_verified", "worker_authorized",
    "remote_witness_configured", "independent_custody_verified",
    "full_quote_brl_verified", "provider_approved",
    "owner_approved_spend", "owner_approved_deploy",
    "automatic_retry_authorized",
)

class WitnessExternalOwnerDecisionEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = MANIFEST.read_bytes()
        cls.manifest = json.loads(cls.raw.decode("utf-8"))
        cls.doc = PLAN.read_text("utf-8")

    def test_manifest_closed_identity_and_no_go(self):
        m=self.manifest
        self.assertEqual(m["schema"],"AION_EXTERNAL_CHECKPOINT_WITNESS_EVIDENCE_MANIFEST_V1")
        self.assertEqual(m["status"],"HARD_NO_GO")
        self.assertEqual(m["mode"],"NO_AUTHORITY")
        self.assertEqual(m["baseline_pr"],1184)
        self.assertEqual(m["budget_brl_monthly_cap"],200)
        self.assertEqual(set(m),{
            "schema","date","baseline_pr","baseline_sha","purpose","status","mode",
            "production_trust_verified","worker_authorized","remote_witness_configured",
            "independent_custody_verified","budget_brl_monthly_cap",
            "full_quote_brl_verified","provider_approved","owner_approved_spend",
            "owner_approved_deploy","automatic_retry_authorized",
            "evidence_gates","factual_references",
        })
        for name in FLAG_FIELDS:
            self.assertIs(m[name],False,name)

    def test_all_independent_enrollment_gates_are_explicitly_unverified(self):
        gates=self.manifest["evidence_gates"]
        self.assertEqual(len(gates),20)
        self.assertEqual({row["id"] for row in gates},GATES)
        self.assertEqual(len({row["id"] for row in gates}),len(gates))
        for gate in gates:
            with self.subTest(gate=gate["id"]):
                self.assertEqual(set(gate),{
                    "id","evidence_class","description","state","evidence_uri",
                    "evidence_sha256","independent_verifier",
                })
                self.assertEqual(gate["state"],"BLOCKED")
                self.assertIsNone(gate["evidence_uri"])
                self.assertIsNone(gate["evidence_sha256"])
                self.assertIsNone(gate["independent_verifier"])
                self.assertTrue(gate["description"])

    def test_new_route_and_storage_gates_cannot_be_falsely_certified(self):
        gate_by_id={g["id"]:g for g in self.manifest["evidence_gates"]}
        for key in (
            "CLOUDFLARE_SECURITY_ROUTE_NO_BYPASS",
            "CLOUDFLARE_DO_SINGLE_OBJECT_STORAGE_HEADROOM",
        ):
            row=gate_by_id[key]
            self.assertEqual(row["state"],"BLOCKED")
            self.assertEqual(row["evidence_class"],"external")
            self.assertIsNone(row["evidence_uri"])
            self.assertIsNone(row["independent_verifier"])
            self.assertIsNone(row["evidence_sha256"])
        self.assertIs(self.manifest["worker_authorized"],False)
        self.assertIs(self.manifest["owner_approved_deploy"],False)

    def test_budget_full_quote_is_not_confused_with_cloudflare_free(self):
        self.assertIs(self.manifest["full_quote_brl_verified"],False)
        self.assertIs(self.manifest["owner_approved_spend"],False)
        self.assertIn("R$200/mês",self.doc)
        self.assertIn("US$5/mês",self.doc)
        for text in ("AWS", "câmbio", "LGPD", "egress", "retention"):
            self.assertTrue(text.lower() in self.doc.lower(),text)

    def test_manifests_do_not_claim_cloud_service_or_owner_enrolled(self):
        for key in ("provider_approved","owner_approved_deploy",
                    "owner_approved_spend","independent_custody_verified"):
            self.assertIs(self.manifest[key],False)
        for phrase in ("NÃO", "PITR", "UNKNOWN_OUTCOME", "físic",
                       "matrícula", "consistência", "Object Lock"):
            self.assertIn(phrase.casefold(),self.doc.casefold())

    def test_source_references_have_only_allowlisted_public_domains(self):
        import urllib.parse
        links=self.manifest["factual_references"]
        self.assertEqual(len(links),len(set(links)))
        self.assertGreaterEqual(len(links),4)
        for link in links:
            host=urllib.parse.urlsplit(link)
            self.assertEqual(host.scheme,"https")
            self.assertIn(host.hostname,{"developers.cloudflare.com","docs.aws.amazon.com","aws.amazon.com"})
            self.assertNotIn("@",host.netloc)

    def test_worker_real_source_gate_remains_permanent_deny(self):
        src=(ROOT/"atlasquant_aion_global_worker_source_gate_v1.py").read_text("utf-8")
        tree=ast.parse(src)
        fn=next(x for x in tree.body if isinstance(x,ast.FunctionDef)
                and x.name=="independent_worker_source_preflight")
        self.assertEqual(len(fn.body),2)
        self.assertIsInstance(fn.body[-1],ast.Return)
        for text in ('"status": "BLOCKED"','"source_verified": False',
                     '"worker_authorized": False','"safe_to_retry": False'):
            self.assertIn(text,ast.get_source_segment(src,fn))
        self.assertNotIn("os.environ",src)
        self.assertNotIn("AION_WITNESS_EXTERNAL_ENROLLMENT_GATE",src)

    def test_runner_blocks_before_private_get_even_under_admin_role(self):
        src=(ROOT/"atlasquant_aion_global_worker.py").read_text("utf-8")
        code=ast.get_source_segment(src,next(
            x for x in ast.parse(src).body if isinstance(x,ast.FunctionDef)
            and x.name=="run_global_worker_once"
        ))
        self.assertLess(code.index("independent_worker_source_preflight(cfg)"),
                        code.index("load_runtime_checkpoint(cfg"))
        self.assertNotIn("AION_WITNESS_EXTERNAL_ENROLLMENT_GATE",src)

    def test_readiness_cli_denies_network_before_private_checkpoint_get(self):
        src=(ROOT/"atlasquant_aion_global_worker_readiness.py").read_text("utf-8")
        code=ast.get_source_segment(src,next(
            x for x in ast.parse(src).body if isinstance(x,ast.FunctionDef)
            and x.name=="_cli"
        ))
        self.assertLess(code.index("independent_worker_source_preflight(config)"),
                        code.index("load_runtime_checkpoint(config"))
        self.assertLess(code.index("independent_worker_source_preflight(config)"),
                        code.index("fetch_recent_autopilot_pulses("))
        self.assertIn("if not source_admitted:",code)

    def test_plan_no_implementation_command_or_private_key(self):
        for marker in ("BEGIN PRIVATE KEY","GITHUB_TOKEN_HISTORICO=",
                       "AWS_SECRET_ACCESS_KEY=","wrangler deploy",
                       "aws s3api put-object-lock-configuration --bucket"):
            self.assertNotIn(marker,self.doc)
        self.assertNotIn("BEGIN PRIVATE KEY",self.raw.decode("utf-8"))
        self.assertNotIn("sk-proj-",self.doc)

    def test_config_document_is_not_imported_as_authority(self):
        for path in ("atlasquant_aion_global_worker.py",
                     "atlasquant_aion_global_worker_source_gate_v1.py",
                     "atlasquant_aion_global_worker_readiness.py"):
            src=(ROOT/path).read_text("utf-8")
            self.assertNotIn("AION_WITNESS_EXTERNAL_ENROLLMENT_GATE_V1",src)
            self.assertNotIn("AION_EXTERNAL_WITNESS_OWNER_DECISION_PLAN",src)

if __name__=="__main__":
    unittest.main()
