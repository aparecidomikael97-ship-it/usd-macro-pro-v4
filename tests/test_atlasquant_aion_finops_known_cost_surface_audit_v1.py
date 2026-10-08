"""Static known real-cost audit tests; never access live provider/account data."""
import copy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from atlasquant_aion_finops_known_cost_surface_audit_v1 import (
    SCHEMA,SOURCE_PATHS,CHECKS,FLAG_FIELDS,MAX_TEXT,known_cost_source_audit,
)
from scripts.aion_finops_known_cost_surface_audit_v1 import run_static_audit,ROOT


class AIONKnownCostSourceAuditV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.actual={
            path:(ROOT/path).read_text("utf-8")
            for path in SOURCE_PATHS
        }

    def audit(self, edits=None):
        src=dict(self.actual)
        if edits:
            src.update(edits)
        return known_cost_source_audit(src)

    def test_actual_known_sources_validate_without_authorizing_cost(self):
        r=self.audit()
        self.assertEqual(r["schema"],SCHEMA)
        self.assertEqual(r["state"],"KNOWN_COST_SURFACES_STATIC_REVIEW_REQUIRED",r)
        self.assertEqual(r["source_file_count"],len(SOURCE_PATHS))
        self.assertEqual(set(r["checks"]),set(CHECKS))
        self.assertTrue(r["static_source_only"])
        for flag in FLAG_FIELDS:
            self.assertIs(r[flag],False,flag)

    def test_actual_openai_post_spend_gap_reported_high(self):
        r=self.audit()
        self.assertTrue(r["checks"]["KNOWN_OPENAI_HTTP_POST"])
        self.assertTrue(r["checks"]["OPENAI_ADAPTER_HAS_USD_ESTIMATE_GATE"])
        self.assertFalse(r["checks"]["OPENAI_ADAPTER_CONNECTED_TO_BRL200_OWNER_PREFLIGHT"])
        self.assertFalse(r["checks"]["OPENAI_ADAPTER_CONNECTED_TO_DURABLE_OWNER_RESERVATION"])
        findings={f["code"]:f for f in r["findings"]}
        self.assertEqual(
            findings["LIVE_OPENAI_POST_NOT_DIRECTLY_BOUND_TO_OWNER_BRL200_PREFLIGHT"]["priority"],"HIGH"
        )
        self.assertEqual(
            findings["LIVE_OPENAI_POST_NOT_DIRECTLY_BOUND_TO_DURABLE_OWNER_RESERVATION"]["priority"],"HIGH"
        )

    def test_real_render_blueprint_is_manual_deploy(self):
        r=self.audit()
        self.assertTrue(r["checks"]["RENDER_AUTODEPLOY_EXPLICITLY_OFF"])
        self.assertTrue(r["checks"]["RENDER_REAL_WEB_SERVICE_DEFINED"])
        self.assertFalse(r["cloud_service_billing_proven_zero"])

    def test_postgres_mentioned_is_not_a_verified_paid_db(self):
        r=self.audit()
        self.assertTrue(r["checks"]["CHAT_PRODUCTION_PERSISTENCE_OPT_IN"])
        self.assertFalse(r["real_provider_invoice_inventory_complete"])
        self.assertIn("POTENTIAL_POSTGRES_MONTHLY_CHARGE_AND_CREDENTIAL_SCOPE_REVIEW",
                      {f["code"] for f in r["findings"]})

    def test_local_deterministic_gateway_is_not_certified_local_llm(self):
        r=self.audit()
        self.assertTrue(r["checks"]["MODEL_GATEWAY_LOCAL_DETERMINISTIC_LANE"])
        self.assertTrue(r["checks"]["MODEL_GATEWAY_PRICE_DENOMINATED_USD"])
        self.assertFalse(r["local_llm_model_running_on_owner_pc"])
        self.assertIn("LOCAL_DETERMINISTIC_IS_NOT_PROOF_OF_LOCAL_LLM_INFERENCE",
                      {f["code"] for f in r["findings"]})

    def test_owner_monthly_brl_cap_is_present_but_not_live_enforcement(self):
        r=self.audit()
        self.assertTrue(r["checks"]["OWNER_BRL200_CONTRACT_PRESENT"])
        self.assertFalse(r["owner_brl200_cap_enforced_on_actual_openai_post"])

    def test_ephemeral_sqlite_is_not_real_production_reservation(self):
        r=self.audit()
        self.assertTrue(r["checks"]["OWNER_RESERVATION_CI_ONLY"])
        self.assertFalse(r["real_paid_api_spend_intercepted"])

    def test_existing_usd_metering_is_detected(self):
        r=self.audit()
        self.assertTrue(r["checks"]["FINOPS_EXISTING_USD_ADMISSION"])
        self.assertTrue(r["checks"]["REQUIREMENTS_CONTAINS_HTTP_CLIENT"])

    def test_exact_source_allowlist_fail_closed_on_missing_config(self):
        src=dict(self.actual)
        del src["render.yaml"]
        r=known_cost_source_audit(src)
        self.assertEqual(r["state"],"BLOCKED")
        self.assertIn("EXACT_KNOWN_SOURCE_SET_REQUIRED",r["blockers"])

    def test_unlisted_extra_file_blocks_scanner_scope_expansion(self):
        r=self.audit({"../../.env":"not allowed"})
        self.assertEqual(r["state"],"BLOCKED")

    def test_invalid_nontext_source_fails_closed(self):
        r=self.audit({"render.yaml":None})
        self.assertEqual(r["state"],"BLOCKED")
        self.assertIn("SOURCE_NOT_TEXT_OR_TOO_LARGE:render.yaml",r["blockers"])

    def test_oversized_source_blocks(self):
        r=self.audit({"render.yaml":"x"*(MAX_TEXT+1)})
        self.assertEqual(r["state"],"BLOCKED")

    def test_python_syntax_error_blocks(self):
        r=self.audit({"atlasquant_aion_provider.py":"def bad(:\n pass"})
        self.assertEqual(r["state"],"BLOCKED")
        self.assertIn("SOURCE_PYTHON_AST_INVALID:atlasquant_aion_provider.py",r["blockers"])

    def test_live_call_disappearing_causes_audit_block(self):
        src=self.actual["atlasquant_aion_provider.py"]
        self.assertIn("response=client.post(",src)
        r=self.audit({"atlasquant_aion_provider.py":src.replace("response=client.post(","response=client.dead_call(",1)})
        self.assertEqual(r["state"],"BLOCKED")
        self.assertIn("KNOWN_EXTERNAL_CALL_TARGET_UNRESOLVED",r["blockers"])

    def test_price_gate_removed_causes_audit_block(self):
        src=self.actual["atlasquant_aion_provider.py"]
        self.assertIn("cost=budget_decision(",src)
        r=self.audit({"atlasquant_aion_provider.py":src.replace("cost=budget_decision(","cost=skip_price_gate(",1)})
        self.assertEqual(r["state"],"BLOCKED")
        self.assertIn("EXISTING_PROVIDER_COST_GATE_UNRESOLVED",r["blockers"])

    def test_render_autodeploy_on_fails_closed(self):
        src=self.actual["render.yaml"]
        self.assertIn("autoDeployTrigger: off",src)
        r=self.audit({"render.yaml":src.replace("autoDeployTrigger: off","autoDeployTrigger: on")})
        self.assertEqual(r["state"],"BLOCKED")
        self.assertIn("RENDER_AUTODEPLOY_NOT_DEMONSTRABLY_OFF",r["blockers"])

    def test_missing_brl_cap_fails_closed(self):
        src=self.actual["atlasquant_aion_owner_brl200_finops_ceiling_v1.py"]
        self.assertIn("HARD_CAP_CENTS = 20_000",src)
        r=self.audit({"atlasquant_aion_owner_brl200_finops_ceiling_v1.py":src.replace(
            "HARD_CAP_CENTS = 20_000","HARD_CAP_CENTS = 99_000",1)})
        self.assertEqual(r["state"],"BLOCKED")
        self.assertIn("OWNER_200_CAP_CONTRACT_NOT_FOUND",r["blockers"])

    def test_owner_reservation_github_ci_flag_missing_blocks(self):
        src=self.actual["atlasquant_aion_finops_ephemeral_sqlite_reservation_cas_v1.py"]
        r=self.audit({"atlasquant_aion_finops_ephemeral_sqlite_reservation_cas_v1.py":
                      src.replace("AION_FINOPS_CI_EPHEMERAL","AION_NOT_CI_GUARDED",1)})
        self.assertEqual(r["state"],"BLOCKED")
        self.assertIn("CI_RESERVATION_BOUNDARY_UNEXPECTED",r["blockers"])

    def test_missing_model_local_router_fails_closed(self):
        src=self.actual["atlasquant_aion_model_gateway_v2.py"]
        r=self.audit({"atlasquant_aion_model_gateway_v2.py":src.replace(
            "def route_model_request(","def route_removed(",1)})
        self.assertEqual(r["state"],"BLOCKED")
        self.assertIn("LOCAL_DETERMINISTIC_ROUTER_NOT_FOUND",r["blockers"])

    def test_source_code_values_never_echoed_in_audit_output(self):
        src=self.actual["render.yaml"]
        fake="FAKE_SECRET_DO_NOT_ECHO_TEST_ONLY_12345"
        r=self.audit({"render.yaml":src+f"\n# {fake}\n"})
        self.assertNotIn(fake,str(r))
        self.assertFalse(r["secrets_examined_or_exported"])

    def test_no_live_prices_or_amounts_fabricated(self):
        r=self.audit()
        self.assertTrue(r["no_real_spend_or_invoice_amounts_discovered"])
        self.assertNotIn("monthly_spend_brl",r)
        self.assertNotIn("render_price",r)
        self.assertNotIn("paid_provider_invoice",r)

    def test_source_hashes_are_deterministic(self):
        a=self.audit()["source_sha256"]
        b=self.audit()["source_sha256"]
        self.assertEqual(a,b)
        self.assertEqual(set(a),set(SOURCE_PATHS))
        self.assertTrue(all(len(v)==64 for v in a.values()))

    def test_cli_reads_exact_known_repopaths_and_emits_nonsecret_json(self):
        proc=subprocess.run(
            [sys.executable,"scripts/aion_finops_known_cost_surface_audit_v1.py"],
            capture_output=True,text=True,timeout=15,cwd=ROOT
        )
        self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr)
        import json
        x=json.loads(proc.stdout)
        self.assertEqual(x["state"],"KNOWN_COST_SURFACES_STATIC_REVIEW_REQUIRED")
        self.assertFalse(x["billable_api_called_during_scan"])

    def test_cli_missing_source_fails_closed_without_directory_listing(self):
        with tempfile.TemporaryDirectory() as folder:
            r=run_static_audit(Path(folder))
        self.assertEqual(r["state"],"BLOCKED")
        self.assertEqual(r["blockers"],["REQUIRED_KNOWN_SOURCE_NOT_READABLE"])

    def test_report_does_not_claim_covers_all_external_calls(self):
        r=self.audit()
        self.assertFalse(r["full_codebase_network_effects_audited"])
        self.assertFalse(r["live_paid_provider_allowlist_complete"])

if __name__ == "__main__":
    unittest.main()
