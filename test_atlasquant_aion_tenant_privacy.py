import unittest
from datetime import datetime, timezone

from atlasquant_aion_tenant import tenant_memory_seed, tenant_namespace
from atlasquant_aion_tenant_privacy import (
    credential_rotation_cleanup_plan,
    tenant_deletion_plan,
    tenant_export_bundle,
    tenant_memory_privacy_audit,
    tenant_privacy_policy_snapshot,
    tenant_privacy_readiness,
    tenant_retention_review,
)


class AtlasQuantAionTenantPrivacyTests(unittest.TestCase):
    def access(self, fingerprint="a"*32):
        return {
            "session":{
                "username":"cliente.01",
                "role":"USER",
                "credential_fingerprint":fingerprint,
            }
        }

    def memory(self):
        return tenant_memory_seed(self.access())

    def test_policy_is_readiness_only_and_never_claims_legal_compliance(self):
        policy=tenant_privacy_policy_snapshot()
        self.assertFalse(policy["retention_enforcement_enabled"])
        self.assertFalse(policy["automatic_deletion"])
        self.assertFalse(policy["automatic_export"])
        self.assertFalse(policy["admin_memory_inherited"])
        self.assertFalse(policy["project_docs_inherited"])
        self.assertFalse(policy["cross_tenant_copy"])
        self.assertFalse(policy["real_trading_enabled"])
        self.assertFalse(policy["legal_compliance_claimed"])
        self.assertFalse(policy["executes_action"])

    def test_matching_tenant_memory_passes_boundary_audit(self):
        audit=tenant_memory_privacy_audit(self.memory(),self.access())
        self.assertEqual(audit["state"],"CONFIRMED")
        self.assertTrue(audit["tenant_match"])
        self.assertTrue(audit["export_safe"])
        self.assertFalse(audit["admin_memory_detected"])
        self.assertFalse(audit["project_docs_detected"])
        self.assertFalse(audit["other_tenant_data_detected"])

    def test_cross_tenant_memory_is_blocked(self):
        other=self.memory()
        other["tenant_id"]="b"*32
        audit=tenant_memory_privacy_audit(other,self.access())
        self.assertEqual(audit["state"],"BLOCKED")
        self.assertEqual(audit["reason"],"TENANT_ID_MISMATCH")
        self.assertFalse(audit["export_safe"])
        self.assertTrue(audit["other_tenant_data_detected"])

    def test_unexpected_or_forbidden_admin_data_is_blocked(self):
        memory=self.memory()
        memory["admin_memory"]={"project":"private"}
        audit=tenant_memory_privacy_audit(memory,self.access())
        self.assertEqual(audit["state"],"BLOCKED")
        self.assertIn("admin_memory",audit["unexpected_fields"])
        self.assertTrue(audit["admin_memory_detected"])
        self.assertFalse(audit["export_safe"])

    def test_export_contains_only_personal_tenant_fields(self):
        memory=self.memory()
        memory["profile"]["display_name"]="Cliente"
        memory["watchlist"]=["EUR/USD","DXY"]
        memory["conversation_notes"]=[{
            "text":"Prefere explicações simples.",
            "created_at":"2026-09-24T10:00:00+00:00",
            "truth_state":"CONFIRMED",
        }]
        result=tenant_export_bundle(memory,self.access())
        self.assertEqual(result["status"],"READY")
        self.assertFalse(result["automatic_download"])
        self.assertFalse(result["external_transfer"])
        bundle=result["bundle"]
        self.assertEqual(bundle["tenant_id"],tenant_namespace(self.access())["tenant_id"])
        self.assertEqual(
            set(bundle["data"].keys()),
            {"profile","conversation_notes","academy_progress","watchlist"},
        )
        self.assertTrue(bundle["excluded"]["admin_memory"])
        self.assertTrue(bundle["excluded"]["project_docs"])
        self.assertTrue(bundle["excluded"]["credentials"])
        self.assertNotIn("permissions",bundle["data"])
        self.assertTrue(bundle["digest"])

    def test_export_refuses_cross_tenant_memory(self):
        memory=self.memory()
        memory["tenant_id"]="c"*32
        result=tenant_export_bundle(memory,self.access())
        self.assertEqual(result["status"],"BLOCKED")
        self.assertIsNone(result["bundle"])

    def test_retention_only_flags_review_and_never_deletes(self):
        memory=self.memory()
        memory["conversation_notes"]=[
            {
                "text":"nota antiga",
                "created_at":"2026-01-01T00:00:00+00:00",
                "truth_state":"CONFIRMED",
            },
            {
                "text":"nota nova",
                "created_at":"2026-09-20T00:00:00+00:00",
                "truth_state":"CONFIRMED",
            },
        ]
        result=tenant_retention_review(
            memory,
            self.access(),
            now=datetime(2026,9,24,tzinfo=timezone.utc),
        )
        self.assertEqual(result["state"],"CONFIRMED")
        self.assertEqual(result["review_due"],1)
        self.assertFalse(result["automatic_deletion"])
        self.assertFalse(result["retention_enforcement_enabled"])
        self.assertEqual(result["review_items"][0]["state"],"RETENTION_REVIEW_DUE")

    def test_deletion_plan_requires_explicit_request_and_never_executes(self):
        memory=self.memory()
        waiting=tenant_deletion_plan(memory,self.access(),explicit_request=False)
        self.assertEqual(waiting["status"],"AWAITING_EXPLICIT_REQUEST")
        self.assertFalse(waiting["executes_action"])

        ready=tenant_deletion_plan(memory,self.access(),explicit_request=True)
        self.assertEqual(ready["status"],"PLAN_READY")
        self.assertFalse(ready["automatic_deletion"])
        self.assertFalse(ready["deletion_executed"])
        self.assertTrue(ready["requires_fresh_identity_confirmation"])
        self.assertTrue(ready["requires_explicit_execution_approval"])
        self.assertIn(tenant_namespace(self.access())["tenant_id"],ready["runtime_path"])
        self.assertTrue(any("ADMIN" in step for step in ready["steps"]))

    def test_credential_rotation_does_not_migrate_memory_automatically(self):
        old=tenant_namespace(self.access("a"*32))["tenant_id"]
        new_access=self.access("b"*32)
        new=tenant_namespace(new_access)["tenant_id"]
        self.assertNotEqual(old,new)
        plan=credential_rotation_cleanup_plan(old,new_access)
        self.assertEqual(plan["status"],"CLEANUP_REVIEW_REQUIRED")
        self.assertTrue(plan["cleanup_required"])
        self.assertFalse(plan["automatic_migration"])
        self.assertFalse(plan["automatic_deletion"])
        self.assertTrue(any("Não copiar memória antiga automaticamente" in x for x in plan["steps"]))

    def test_readiness_does_not_enable_personal_runtime(self):
        out=tenant_privacy_readiness()
        self.assertTrue(out["policy_defined"])
        self.assertTrue(out["export_contract_ready"])
        self.assertTrue(out["deletion_plan_contract_ready"])
        self.assertTrue(out["cross_tenant_audit_ready"])
        self.assertFalse(out["persistence_enabled"])
        self.assertFalse(out["subscriber_shell_enabled"])
        self.assertFalse(out["automatic_deletion"])
        self.assertFalse(out["legal_compliance_claimed"])
        self.assertFalse(out["executes_action"])


if __name__=="__main__":
    unittest.main()
